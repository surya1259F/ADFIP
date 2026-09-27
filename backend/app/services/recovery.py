"""ADFIR — Investigation Recovery & Reproducibility Service (Final Backend Completion)

Enforces persistent recovery after operational failures (system crash, backend restart,
interrupted investigations, tool/agent timeouts, process kills, partial completions).

Guarantees:
1. Recovers case and investigation state deterministically from persistent SQLite/disk storage.
2. Identifies stale or interrupted RUNNING runs, tasks, and requests.
3. Never blindly reruns an already completed forensic execution when its outputs are intact and valid.
4. Verifies existing output file SHA-256 digests before reuse.
5. Verifies if forensic OS processes are still running to prevent duplicate executions.
6. Safely transitions interrupted tasks to RECOVERED or READY for seamless resumption.
7. Preserves immutable evidence vault and all raw/structured forensic artifacts.
8. Preserves cryptographic audit-chain integrity and records immutable recovery audit event.
"""

import os
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.models import (
    Case,
    InvestigationRun,
    InvestigationTask,
    AnalysisRequest,
    ForensicExecution,
    ExecutionOutput,
    StructuredArtifact,
    NormalizedArtifact,
    User
)
from backend.app.schemas.schemas import RecoveryResponse
from backend.app.services.audit import AuditService, log_audit_event
from backend.app.services.integrity import calculate_sha256
from forensic_tools.registry import get_process_start_time

logger = logging.getLogger("ADFIR_RECOVERY")


def is_execution_process_running(exec_record: Optional[ForensicExecution]) -> bool:
    """
    Reuses Step 9 PID and process-start verification to authoritatively check
    if the underlying forensic OS subprocess is still active.
    Protects against recycled PIDs.
    """
    if not exec_record or not exec_record.pid or exec_record.pid <= 0:
        return False
    current_start_time = get_process_start_time(exec_record.pid)
    if current_start_time is None:
        return False
    if exec_record.process_start_time is not None:
        return current_start_time == exec_record.process_start_time
    return True


class InvestigationRecoveryService:
    """
    Service responsible for deterministic state recovery across cases and investigation runs.
    """

    @classmethod
    def is_process_running(cls, exec_record: Optional[ForensicExecution]) -> bool:
        return is_execution_process_running(exec_record)

    @classmethod
    def recover_case(
        cls,
        db: Session,
        case_id: str,
        user: User,
        force: bool = False,
        safe_reset_stale_tasks: bool = True
    ) -> RecoveryResponse:
        """
        Scans persistent database and disk storage for the case, recovers interrupted runs and tasks,
        validates output hashes before reuse, ensures still-running processes are not duplicated,
        and logs an immutable recovery audit event.
        """
        now = datetime.now(timezone.utc)
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")

        recovered_runs_count = 0
        recovered_tasks_count = 0
        interrupted_tasks_resumed = 0
        valid_outputs_preserved = 0
        still_running_processes_count = 0
        recovery_details: Dict[str, Any] = {
            "recovered_runs": [],
            "preserved_executions": [],
            "rescheduled_requests": [],
            "still_running_executions": []
        }

        # 1. Inspect Interrupted Investigation Runs
        stale_runs = db.query(InvestigationRun).filter(
            InvestigationRun.case_id == case.id,
            InvestigationRun.status.in_(["RUNNING", "INTERRUPTED", "RECOVERED"])
        ).all()

        for run in stale_runs:
            tasks = db.query(InvestigationTask).filter(
                InvestigationTask.run_id == run.id
            ).all()

            for task in tasks:
                if task.status == "RUNNING" or (force and task.status != "COMPLETED"):
                    recovered_tasks_count += 1
                    req = db.query(AnalysisRequest).filter(
                        AnalysisRequest.task_id == task.id
                    ).order_by(AnalysisRequest.created_at.desc()).first()

                    if req:
                        exec_record = db.query(ForensicExecution).filter(
                            ForensicExecution.request_id == req.id
                        ).order_by(ForensicExecution.created_at.desc()).first()

                        # Check 1: Is the OS process still running?
                        if exec_record and cls.is_process_running(exec_record):
                            # The process is still actively running in the OS.
                            # NEVER reset task to READY while its previous forensic OS process is still running.
                            still_running_processes_count += 1
                            recovery_details["still_running_executions"].append({
                                "task_id": task.id,
                                "request_id": req.id,
                                "execution_id": exec_record.id,
                                "pid": exec_record.pid,
                                "reason": "Process is still active in operating system. Reset to READY prohibited to prevent duplicate execution."
                            })
                            continue

                        # Check 2: Verify if execution actually completed and produced valid outputs on disk
                        has_valid_outputs = False
                        if exec_record:
                            outputs = db.query(ExecutionOutput).filter(
                                ExecutionOutput.execution_id == exec_record.id
                            ).all()

                            if outputs:
                                all_outputs_intact = True
                                for out in outputs:
                                    if out.storage_path and os.path.exists(out.storage_path):
                                        try:
                                            actual_hash, _ = calculate_sha256(out.storage_path)
                                            if actual_hash.lower() != (out.sha256_hash or "").lower():
                                                all_outputs_intact = False
                                                break
                                        except Exception:
                                            all_outputs_intact = False
                                            break
                                    else:
                                        all_outputs_intact = False
                                        break

                                if all_outputs_intact:
                                    has_valid_outputs = True
                                    valid_outputs_preserved += len(outputs)
                                    exec_record.execution_status = "COMPLETED"
                                    req.scheduler_status = "COMPLETED"
                                    task.status = "COMPLETED"
                                    recovery_details["preserved_executions"].append({
                                        "execution_id": exec_record.id,
                                        "tool_id": exec_record.tool_id,
                                        "outputs_preserved": len(outputs)
                                    })

                        if not has_valid_outputs and safe_reset_stale_tasks:
                            # Safely reset task to READY only because previous process is confirmed terminated/non-running
                            task.status = "READY"
                            task.error_message = f"Recovered from interrupted state at {now.isoformat()}"
                            req.scheduler_status = "READY"
                            req.failure_reason = "Interrupted by system restart/crash. Safely reset to READY."
                            if exec_record and exec_record.execution_status == "RUNNING":
                                exec_record.execution_status = "CANCELLED"
                                exec_record.cancellation_reason = "System restart recovery."
                            interrupted_tasks_resumed += 1
                            recovery_details["rescheduled_requests"].append(req.id)

            # Transition run to RECOVERED only if no processes are still running
            run_has_active_proc = any(
                item["task_id"] in [t.id for t in tasks]
                for item in recovery_details["still_running_executions"]
            )
            if run_has_active_proc:
                run.status = "RUNNING"
                run.error_message = f"Process still running in operating system at {now.isoformat()}."
            else:
                run.status = "RECOVERED"
                run.error_message = f"Recovered from operational interruption at {now.isoformat()}."
                recovered_runs_count += 1
                recovery_details["recovered_runs"].append(run.id)

            progress = dict(run.stage_progress or {})
            progress["recovered_at"] = now.isoformat()
            run.stage_progress = progress
            db.add(run)

        # 2. Inspect orphaned AnalysisRequests with RUNNING scheduler_status
        orphan_requests = db.query(AnalysisRequest).filter(
            AnalysisRequest.case_id == case.id,
            AnalysisRequest.scheduler_status == "RUNNING"
        ).all()

        for o_req in orphan_requests:
            exec_rec = db.query(ForensicExecution).filter(
                ForensicExecution.request_id == o_req.id
            ).order_by(ForensicExecution.created_at.desc()).first()

            # Process still running check on orphaned requests too!
            if exec_rec and cls.is_process_running(exec_rec):
                still_running_processes_count += 1
                recovery_details["still_running_executions"].append({
                    "request_id": o_req.id,
                    "execution_id": exec_rec.id,
                    "pid": exec_rec.pid,
                    "reason": "Process is still active in operating system."
                })
                continue

            if safe_reset_stale_tasks:
                o_req.scheduler_status = "READY"
                o_req.failure_reason = f"Recovered from interrupted state at {now.isoformat()}"
                interrupted_tasks_resumed += 1
                recovery_details["rescheduled_requests"].append(o_req.id)

        db.commit()

        # 3. Verify audit chain
        audit_res = AuditService.verify_chain(db, case_id=case.id)

        # 4. Log recovery audit event
        log_audit_event(
            db=db,
            event_type="INVESTIGATION_RECOVERED",
            details=(
                f"Investigation recovery executed for case {case.id}. "
                f"Recovered {recovered_runs_count} runs, preserved {valid_outputs_preserved} outputs, "
                f"resumed {interrupted_tasks_resumed} tasks, still running: {still_running_processes_count}."
            ),
            case_id=case.id,
            actor_id=user.id,
            actor_name=user.name or user.email,
            metadata_json={
                "recovered_runs_count": recovered_runs_count,
                "recovered_tasks_count": recovered_tasks_count,
                "interrupted_tasks_resumed": interrupted_tasks_resumed,
                "valid_outputs_preserved": valid_outputs_preserved,
                "still_running_processes_count": still_running_processes_count,
                "audit_chain_verified": audit_res.is_valid and not audit_res.tamper_detected,
                "recovery_details": recovery_details
            },
            provenance_context={
                "case_id": case.id,
                "recovery_timestamp": now.isoformat()
            }
        )

        logger.info(
            f"[RECOVERY] Case {case.id} recovered successfully. "
            f"Runs: {recovered_runs_count}, Preserved: {valid_outputs_preserved}, Resumed: {interrupted_tasks_resumed}, "
            f"Still Running: {still_running_processes_count}."
        )

        return RecoveryResponse(
            case_id=case.id,
            status="RECOVERED",
            recovered_runs_count=recovered_runs_count,
            recovered_tasks_count=recovered_tasks_count,
            interrupted_tasks_resumed=interrupted_tasks_resumed,
            valid_outputs_preserved=valid_outputs_preserved,
            audit_chain_verified=audit_res.is_valid and not audit_res.tamper_detected,
            message=(
                f"Recovery completed successfully. {recovered_runs_count} runs recovered, "
                f"{valid_outputs_preserved} output artifacts preserved, "
                f"{interrupted_tasks_resumed} interrupted tasks reset to READY."
            ),
            recovery_details=recovery_details,
            timestamp=now
        )
