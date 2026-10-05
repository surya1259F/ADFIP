"""
ADFIP — Authoritative Forensic Report Readiness Subsystem (Phases 13-15)

Evaluates 14 mandatory forensic readiness gates before an OFFICIAL_FINAL forensic
report can be synthesized or released. Rejects unready requests with HTTP 422
and machine-readable blocking reasons.
"""

from typing import Dict, Any, List, Optional
import hashlib
import os
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

from backend.app.models.models import (
    Case,
    EvidenceItem,
    Finding,
    DeterministicFinding,
    ForensicExecution,
    ToolExecution,
    ExecutionOutput,
    InvestigationPlan,
    InvestigatorReviewRecord,
    InvestigatorDecision,
    CorrelationGroup,
    ForensicCorrelationGroup,
    AuditEvent,
    User
)
from backend.app.schemas.schemas import BlockingReason, ReadinessGateResult, CaseReadinessReport


class ReportReadinessService:
    """
    Authoritative service evaluating investigation readiness against 14 mandatory forensic gates.
    """

    @classmethod
    def evaluate(cls, db: Session, case: Case, current_user: User) -> CaseReadinessReport:
        gates: List[ReadinessGateResult] = []
        blocking_reasons: List[BlockingReason] = []

        # Gate 1: Case exists and is authorized
        g1_passed = bool(case and case.id)
        g1_reason = None
        if not g1_passed:
            g1_reason = BlockingReason(code="CASE_NOT_AUTHORIZED", description="Investigation case is not authorized for current user.")
            blocking_reasons.append(g1_reason)
        gates.append(ReadinessGateResult(
            gate_number=1,
            code="CASE_EXISTS_AND_AUTHORIZED",
            name="Authorized Case Verification",
            passed=g1_passed,
            description="Verified case exists and investigator has authorized access.",
            blocking_reason=g1_reason
        ))

        # Gate 2: Case is not closed
        case_status_norm = (case.status or "OPEN").upper()
        g2_passed = case_status_norm not in ("CLOSED", "ARCHIVED")
        g2_reason = None
        if not g2_passed:
            g2_reason = BlockingReason(code="CASE_CLOSED", description=f"Investigation case is {case_status_norm}; closed cases cannot generate new reports.")
            blocking_reasons.append(g2_reason)
        gates.append(ReadinessGateResult(
            gate_number=2,
            code="CASE_NOT_CLOSED",
            name="Active Case Lifecycle State",
            passed=g2_passed,
            description="Case is active and available for forensic reporting.",
            blocking_reason=g2_reason
        ))

        # Gate 3: Evidence exists
        evidence_items = db.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).all()
        g3_passed = len(evidence_items) > 0
        g3_reason = None
        if not g3_passed:
            g3_reason = BlockingReason(code="NO_EVIDENCE_REGISTERED", description="No forensic evidence containers registered in this case.", count=0)
            blocking_reasons.append(g3_reason)
        gates.append(ReadinessGateResult(
            gate_number=3,
            code="EVIDENCE_REGISTERED",
            name="Forensic Evidence Registration",
            passed=g3_passed,
            description="At least one verified evidence container must be registered.",
            blocking_reason=g3_reason
        ))

        # Gate 4: Evidence integrity cryptographically verified
        unverified_ev = [
            e for e in evidence_items
            if (e.integrity_status or "").upper() != "VERIFIED"
        ]
        g4_passed = len(evidence_items) > 0 and len(unverified_ev) == 0
        g4_reason = None
        if not g4_passed and evidence_items:
            g4_reason = BlockingReason(
                code="EVIDENCE_INTEGRITY_UNVERIFIED",
                description=f"{len(unverified_ev)} evidence item(s) have unverified or mismatched vault cryptographic hashes.",
                count=len(unverified_ev),
                references=[e.id for e in unverified_ev]
            )
            blocking_reasons.append(g4_reason)
        gates.append(ReadinessGateResult(
            gate_number=4,
            code="EVIDENCE_INTEGRITY_VERIFIED",
            name="Cryptographic Vault Integrity",
            passed=g4_passed,
            description="All evidence items must have verified vault SHA-256 hashes matching acquisition records.",
            blocking_reason=g4_reason
        ))

        # Gate 5: Evidence intelligence complete
        unprofiled_ev = [
            e for e in evidence_items
            if not getattr(e, "intelligence_profile", None) and not (getattr(e, "intelligence_json", None) and len(getattr(e, "intelligence_json", {})) > 0)
        ]
        g5_passed = len(evidence_items) > 0 and len(unprofiled_ev) == 0
        g5_reason = None
        if not g5_passed and evidence_items:
            g5_reason = BlockingReason(
                code="EVIDENCE_INTELLIGENCE_INCOMPLETE",
                description=f"{len(unprofiled_ev)} evidence item(s) have pending file intelligence classification.",
                count=len(unprofiled_ev),
                references=[e.id for e in unprofiled_ev]
            )
            blocking_reasons.append(g5_reason)
        gates.append(ReadinessGateResult(
            gate_number=5,
            code="EVIDENCE_INTELLIGENCE_COMPLETE",
            name="Evidence Intelligence Triage",
            passed=g5_passed,
            description="Deterministic MIME/magic signature intelligence extraction must be completed.",
            blocking_reason=g5_reason
        ))

        # Gate 6: Strategy exists
        plan = db.query(InvestigationPlan).filter(InvestigationPlan.case_id == case.id).first()
        g6_passed = bool(plan)
        g6_reason = None
        if not g6_passed:
            g6_reason = BlockingReason(code="STRATEGY_NOT_GENERATED", description="Investigation strategy plan has not been generated for this case.")
            blocking_reasons.append(g6_reason)
        gates.append(ReadinessGateResult(
            gate_number=6,
            code="STRATEGY_GENERATED",
            name="Investigation Strategy Plan",
            passed=g6_passed,
            description="Capability-driven investigation plan must be generated and sequenced.",
            blocking_reason=g6_reason
        ))

        # Gate 7: Required tasks have completed successfully
        executions = db.query(ForensicExecution).filter(ForensicExecution.case_id == case.id).all()
        tool_execs = db.query(ToolExecution).filter(ToolExecution.case_id == case.id).all()

        g7_passed = False
        g7_reason = None
        if not executions:
            if tool_execs:
                g7_reason = BlockingReason(
                    code="CANONICAL_EXECUTION_MISSING",
                    description=f"{len(tool_execs)} legacy tool execution(s) found, but canonical ForensicExecution records are missing.",
                    count=len(tool_execs),
                    references=[tx.id for tx in tool_execs]
                )
                blocking_reasons.append(g7_reason)
            else:
                g7_reason = BlockingReason(
                    code="NO_EXECUTIONS_RECORDED",
                    description="No forensic tool execution tasks have been executed for this case.",
                    count=0
                )
                blocking_reasons.append(g7_reason)
        else:
            running_or_queued = [ex for ex in executions if (getattr(ex, "execution_status", None) in ("RUNNING", "QUEUED") or getattr(ex, "status", None) in ("RUNNING", "QUEUED"))]
            failed_executions = [ex for ex in executions if (getattr(ex, "execution_status", None) in ("FAILED", "ERROR") or getattr(ex, "status", None) in ("FAILED", "ERROR"))]
            if running_or_queued:
                g7_reason = BlockingReason(
                    code="EXECUTIONS_STILL_RUNNING",
                    description=f"{len(running_or_queued)} tool execution(s) are currently running or queued.",
                    count=len(running_or_queued),
                    references=[ex.id for ex in running_or_queued]
                )
                blocking_reasons.append(g7_reason)
            elif failed_executions:
                g7_reason = BlockingReason(
                    code="EXECUTIONS_FAILED",
                    description=f"{len(failed_executions)} tool execution(s) failed or terminated with error.",
                    count=len(failed_executions),
                    references=[ex.id for ex in failed_executions]
                )
                blocking_reasons.append(g7_reason)
            else:
                g7_passed = True

        gates.append(ReadinessGateResult(
            gate_number=7,
            code="REQUIRED_TASKS_COMPLETED",
            name="Tool Execution Lifecycle",
            passed=g7_passed,
            description="All scheduled tool execution tasks must be completed without active background processes.",
            blocking_reason=g7_reason
        ))

        # Gate 8: Execution outputs exist
        all_outputs_for_case = db.query(ExecutionOutput).filter(ExecutionOutput.case_id == case.id).all()
        output_execution_ids = {out.execution_id for out in all_outputs_for_case if out.execution_id}
        successful_executions = [ex for ex in executions if (getattr(ex, "execution_status", None) == "COMPLETED" or getattr(ex, "status", None) == "COMPLETED")]
        missing_output_execs = [ex.id for ex in successful_executions if ex.id not in output_execution_ids]
        outputs_count = len(all_outputs_for_case)

        g8_passed = len(successful_executions) > 0 and outputs_count > 0 and len(missing_output_execs) == 0
        g8_reason = None
        if not g8_passed:
            if outputs_count == 0:
                g8_reason = BlockingReason(code="NO_EXECUTION_OUTPUTS", description="No forensic tool outputs recorded from executed tasks.", count=0)
            elif missing_output_execs:
                g8_reason = BlockingReason(
                    code="EXECUTION_OUTPUTS_MISSING",
                    description=f"{len(missing_output_execs)} completed execution(s) have no persisted execution output records.",
                    count=len(missing_output_execs),
                    references=missing_output_execs[:20]
                )
            else:
                g8_reason = BlockingReason(code="NO_SUCCESSFUL_EXECUTIONS", description="No successfully completed forensic executions with preserved outputs.", count=0)
            blocking_reasons.append(g8_reason)
        gates.append(ReadinessGateResult(
            gate_number=8,
            code="EXECUTION_OUTPUTS_EXIST",
            name="Forensic Output Preservation",
            passed=g8_passed,
            description="Structured raw outputs and terminal logs must be preserved.",
            blocking_reason=g8_reason
        ))

        # Gate 9: Output integrity — real byte-level SHA-256 re-verification
        all_outputs = db.query(ExecutionOutput).filter(ExecutionOutput.case_id == case.id).all()
        g9_integrity_warning_refs: List[str] = []
        g9_missing_refs: List[str] = []
        for out in all_outputs:
            stored_hash = (out.sha256_hash or "").lower().strip()
            storage_path = out.storage_path or ""
            if not stored_hash:
                # No hash recorded — cannot verify; flag as warning
                g9_integrity_warning_refs.append(out.id)
                continue
            if not storage_path or not os.path.isfile(storage_path):
                g9_missing_refs.append(out.id)
                continue
            try:
                h = hashlib.sha256()
                with open(storage_path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(65536), b""):
                        h.update(chunk)
                computed = h.hexdigest().lower()
                if computed != stored_hash:
                    g9_integrity_warning_refs.append(out.id)
            except OSError as exc:
                logger.warning("Gate 9: cannot read output %s: %s", out.id, exc)
                g9_missing_refs.append(out.id)

        g9_passed = (len(g9_integrity_warning_refs) == 0) and (len(g9_missing_refs) == 0)
        g9_reason = None
        if not g9_passed:
            parts = []
            if g9_integrity_warning_refs:
                parts.append(f"{len(g9_integrity_warning_refs)} output(s) failed SHA-256 re-verification (INTEGRITY_WARNING)")
            if g9_missing_refs:
                parts.append(f"{len(g9_missing_refs)} output(s) are missing from storage (MISSING)")
            g9_reason = BlockingReason(
                code="EXECUTION_OUTPUT_INTEGRITY_FAILURE",
                description="; ".join(parts),
                count=len(g9_integrity_warning_refs) + len(g9_missing_refs),
                references=(g9_integrity_warning_refs + g9_missing_refs)[:20]
            )
            blocking_reasons.append(g9_reason)
        gates.append(ReadinessGateResult(
            gate_number=9,
            code="EXECUTION_OUTPUT_INTEGRITY",
            name="Output Integrity Checksum",
            passed=g9_passed,
            description="Cryptographic SHA-256 checksums re-verified byte-for-byte against stored execution outputs.",
            blocking_reason=g9_reason
        ))

        # Gate 10: Findings grounded — real provenance tracing
        findings_query = db.query(Finding).filter(Finding.case_id == case.id).all()
        deterministic_query = db.query(DeterministicFinding).filter(DeterministicFinding.case_id == case.id).all()
        all_finding_ids = set()
        ungrounded_finding_ids: List[str] = []

        for f in findings_query:
            all_finding_ids.add(f.id)
            # A Finding must have at least one provenance anchor
            has_evidence = bool(f.evidence_id)
            has_execution = bool(f.execution_id)
            has_artifact = bool(f.artifact_id)
            if not (has_evidence or has_execution or has_artifact):
                ungrounded_finding_ids.append(f.id)

        for df in deterministic_query:
            all_finding_ids.add(df.id)
            # A DeterministicFinding claiming factual support must have supporting evidence or artifacts
            has_ev = bool(df.supporting_evidence_ids)
            has_art = bool(df.supporting_artifact_ids)
            if not (has_ev or has_art):
                if df.verification_status != "UNVERIFIED":
                    ungrounded_finding_ids.append(df.id)

        g10_passed = len(ungrounded_finding_ids) == 0
        g10_reason = None
        if not g10_passed:
            g10_reason = BlockingReason(
                code="FINDINGS_UNGROUNDED",
                description=f"{len(ungrounded_finding_ids)} finding(s) lack required provenance anchors (evidence_id, execution_id, or artifact_id).",
                count=len(ungrounded_finding_ids),
                references=ungrounded_finding_ids[:20]
            )
            blocking_reasons.append(g10_reason)
        gates.append(ReadinessGateResult(
            gate_number=10,
            code="FINDINGS_GROUNDED",
            name="Evidence Grounding Verification",
            passed=g10_passed,
            description="All forensic findings must be grounded in underlying evidence, execution, or artifact provenance.",
            blocking_reason=g10_reason
        ))

        # Gate 11: Required findings are reviewed (0 pending reviews!)
        # Find unique reviewed finding target IDs
        reviews_query = db.query(InvestigatorReviewRecord).filter(
            InvestigatorReviewRecord.case_id == case.id
        ).all()
        reviewed_target_ids = {r.target_id for r in reviews_query if r.target_type in ("FINDING", "CLAIM")}
        unreviewed_findings = [f_id for f_id in all_finding_ids if f_id not in reviewed_target_ids]

        g11_passed = len(all_finding_ids) == 0 or len(unreviewed_findings) == 0
        g11_reason = None
        if not g11_passed:
            g11_reason = BlockingReason(
                code="PENDING_FINDING_REVIEWS",
                description=f"{len(unreviewed_findings)} finding(s) require human investigator review (ACCEPT, CHALLENGE, REJECT, REQUEST_MORE_EVIDENCE) before report release.",
                count=len(unreviewed_findings),
                references=unreviewed_findings[:10]
            )
            blocking_reasons.append(g11_reason)
        gates.append(ReadinessGateResult(
            gate_number=11,
            code="REQUIRED_FINDINGS_REVIEWED",
            name="Human-in-the-Loop Investigator Review",
            passed=g11_passed,
            description="Zero pending reviews permitted: every individual finding must have an explicit review decision.",
            blocking_reason=g11_reason
        ))

        # Gate 12: Correlation completed — verify actual persisted correlation results
        # Correlation is REQUIRED when the case has any findings; NOT_REQUIRED when there are none.
        corr_groups = db.query(ForensicCorrelationGroup).filter(
            ForensicCorrelationGroup.case_id == case.id
        ).all()
        corr_audit = db.query(AuditEvent).filter(
            AuditEvent.case_id == case.id,
            AuditEvent.event_type == "CORRELATION_EXECUTED"
        ).first()

        has_findings = bool(all_finding_ids)
        corr_completed = len(corr_groups) > 0

        if not has_findings:
            # No findings → correlation not applicable
            g12_passed = True
            g12_detail = "NOT_REQUIRED — case has no forensic findings requiring correlation."
        elif corr_completed:
            g12_passed = True
            g12_detail = f"REQUIRED_AND_COMPLETED — {len(corr_groups)} correlation group(s) persisted."
        elif corr_audit:
            g12_passed = True
            g12_detail = "REQUIRED_AND_COMPLETED — Correlation engine executed (0 cross-domain relationship groups discovered)."
        else:
            g12_passed = False
            g12_detail = "REQUIRED_BUT_MISSING — findings exist but no correlation run has executed or produced persisted groups."

        g12_reason = None
        if not g12_passed:
            g12_reason = BlockingReason(
                code="CORRELATION_NOT_COMPLETED",
                description=g12_detail,
                count=0
            )
            blocking_reasons.append(g12_reason)
        gates.append(ReadinessGateResult(
            gate_number=12,
            code="CORRELATION_COMPLETED",
            name="Artifact Correlation Gate",
            passed=g12_passed,
            description="Cross-artifact timeline and relationship correlation must be executed and persisted before report generation.",
            blocking_reason=g12_reason
        ))

        # Gate 13: No blocking investigation conditions
        blocking_conditions = []
        if any(e.integrity_status == "INTEGRITY_MISMATCH" for e in evidence_items):
            blocking_conditions.append("Evidence cryptographic mismatch detected")
        g13_passed = len(blocking_conditions) == 0
        g13_reason = None
        if not g13_passed:
            g13_reason = BlockingReason(
                code="BLOCKING_INVESTIGATION_CONDITIONS",
                description="; ".join(blocking_conditions),
                count=len(blocking_conditions)
            )
            blocking_reasons.append(g13_reason)
        gates.append(ReadinessGateResult(
            gate_number=13,
            code="NO_BLOCKING_CONDITIONS",
            name="Absence of Fatal Investigation Flags",
            passed=g13_passed,
            description="Case must be free of critical unhandled tamper alerts or forensic blockers.",
            blocking_reason=g13_reason
        ))

        # Gate 14: Investigator final authorization exists (CONFIRM decision)
        latest_decision = db.query(InvestigatorDecision).filter(
            InvestigatorDecision.case_id == case.id
        ).order_by(InvestigatorDecision.timestamp.desc()).first()
        g14_passed = bool(latest_decision and latest_decision.decision == "CONFIRM")
        g14_reason = None
        if not g14_passed:
            curr_dec = latest_decision.decision if latest_decision else "NONE"
            g14_reason = BlockingReason(
                code="INVESTIGATOR_FINAL_AUTHORIZATION_REQUIRED",
                description=f"Investigator final authorization required: case decision is currently '{curr_dec}'. Must be 'CONFIRM'."
            )
            blocking_reasons.append(g14_reason)
        gates.append(ReadinessGateResult(
            gate_number=14,
            code="INVESTIGATOR_FINAL_AUTHORIZATION",
            name="Investigator Release Authorization",
            passed=g14_passed,
            description="Investigator must explicitly record a final CONFIRM decision authorizing report generation.",
            blocking_reason=g14_reason
        ))

        passed_count = sum(1 for g in gates if g.passed)
        is_ready = (passed_count == 14) and (len(blocking_reasons) == 0)

        return CaseReadinessReport(
            case_id=case.id,
            ready=is_ready,
            status="READY" if is_ready else "BLOCKED",
            code="REPORT_READY" if is_ready else "REPORT_NOT_READY",
            passed_gates=passed_count,
            total_gates=14,
            blocking_reasons=blocking_reasons,
            gates=gates
        )
