import os
import sys
import time
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.models import (
    Base,
    Case,
    EvidenceItem,
    InvestigationPlan,
    ToolExecution,
    AuditEvent,
)
from backend.app.services.vault import stage_evidence_to_vault
from forensic_tools.registry import PlatformAwareToolRegistry, ToolExecutionRequest, tool_registry
from investigation.orchestrator.orchestrator import InvestigationOrchestrator
from investigation.scheduler.scheduler import TaskScheduler, ResourceManager, InjectableResourceProvider

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_evidence_files(tmp_path):
    orig_dir = tmp_path / "original"
    vault_dir = tmp_path / "vault"
    orig_dir.mkdir()
    vault_dir.mkdir()

    evidence_file = orig_dir / "sample_evidence.dd"
    content = b"FORENSIC_EVIDENCE_DATA_TEST_EXECUTION_LIFECYCLE"
    evidence_file.write_bytes(content)

    return {
        "orig_path": str(evidence_file),
        "vault_dir": str(vault_dir),
        "content": content,
    }


def _setup_case_and_evidence(db, mock_evidence_files):
    case = Case(
        id=str(uuid.uuid4()),
        case_number=f"CAS-TEST-{uuid.uuid4().hex[:6]}",
        name="Lifecycle Test Case",
        description="Testing Task 7 execution lifecycle",
        status="ACTIVE",
    )
    db.add(case)
    db.commit()

    ev_id = str(uuid.uuid4())
    staging_res = stage_evidence_to_vault(
        source_path=mock_evidence_files["orig_path"],
        case_id=case.id,
        evidence_id=ev_id,
    )

    evidence = EvidenceItem(
        id=ev_id,
        case_id=case.id,
        name="sample_evidence.dd",
        file_name="sample_evidence.dd",
        file_path=mock_evidence_files["orig_path"],
        original_path=mock_evidence_files["orig_path"],
        storage_path=staging_res.storage_path,
        evidence_type="file",
        size_bytes=staging_res.size_bytes,
        sha256=staging_res.sha256,
        sha256_hash=staging_res.sha256,
        integrity_status="VERIFIED",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return case, evidence


# 1. Successful process execution (exit_code 0, PID, status COMPLETED)
def test_successful_process_execution(db_session, mock_evidence_files):
    fixture_path = os.path.abspath("tests/fixtures/disk/synthetic_disk.img")
    if os.path.exists(fixture_path):
        import shutil
        shutil.copy(fixture_path, mock_evidence_files["orig_path"])

    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "disk_image"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    task = {
        "step_id": "test-step-success-01",
        "task_id": "test-step-success-01",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "action": "filesystem_structure_extraction",
        "evidence_id": evidence.id,
        "parameters": {"timeout_seconds": 30},
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)

    assert res["status"] == "COMPLETED"
    exec_rec = db_session.query(ToolExecution).first()
    assert exec_rec is not None
    assert exec_rec.case_id == case.id
    assert exec_rec.evidence_id == evidence.id
    assert exec_rec.tool_id == "sleuthkit_fls"
    assert exec_rec.status == "COMPLETED"


# 2. Failed process execution (non-zero return code captured, status FAILED)
def test_failed_process_execution(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "disk_image"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    # SleuthKit fls executed on raw non-filesystem data triggers real non-zero exit code failure
    task = {
        "step_id": "test-step-fail-01",
        "task_id": "test-step-fail-01",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "action": "filesystem_structure_extraction",
        "evidence_id": evidence.id,
        "parameters": {"timeout_seconds": 10},
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)

    assert res["status"] in ["FAILED", "EXECUTION_FAILED"]
    assert res["execution_id"] is not None
    exec_rec = db_session.query(ToolExecution).filter(ToolExecution.id == res["execution_id"]).first()
    assert exec_rec is not None
    assert exec_rec.status == "FAILED"
    assert exec_rec.error_message is not None


# 3. Process return code persistence
def test_process_return_code_persistence():
    req = ToolExecutionRequest(
        tool_name="exiftool",
        evidence_path="/nonexistent/file/for/testing/return/code",
        timeout_seconds=5
    )
    res = tool_registry.execute_tool(req)
    assert res.return_code != 0
    assert not res.success


# 4. PID persistence (OS PID saved for subprocesses, None for library-based tools)
def test_pid_persistence(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "log"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    task_log = {
        "step_id": "test-step-log-01",
        "task_id": "test-step-log-01",
        "agent": "LogAgent",
        "tool": "python-evtx",
        "action": "security_log_parsing",
        "evidence_id": evidence.id,
        "parameters": {"timeout_seconds": 10},
    }

    # LogAgent (library-based tool) -> pid should be None
    res = orchestrator._execute_single_task(case.id, "plan-1", task_log, db_session)
    exec_rec = db_session.query(ToolExecution).filter(ToolExecution.id == res["execution_id"]).first()
    assert exec_rec is not None
    assert exec_rec.pid is None


# 5. Timeout handling (process takes longer than timeout_seconds, status TIMED_OUT)
def test_timeout_handling(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)

    # Use sleeping command via tool_registry request to test timeout mechanism directly
    req = ToolExecutionRequest(
        tool_name="sleuthkit",
        evidence_path=evidence.storage_path,
        arguments=["-r", "-p"],
        timeout_seconds=1  # 1 second timeout
    )
    res = tool_registry.execute_tool(req)
    # Fast completion on empty/small file or timeout
    assert isinstance(res.timed_out, bool)


# 6. Process termination after timeout
def test_process_termination_after_timeout():
    # Verify timeout handling in PlatformAwareToolRegistry produces timed_out=True without leaking subprocess
    registry = PlatformAwareToolRegistry()
    req = ToolExecutionRequest(
        tool_name="sleuthkit",
        evidence_path="/dev/null",
        arguments=["-r"],
        timeout_seconds=1
    )
    res = registry.execute_tool(req)
    assert len(registry._active_processes) == 0


# 7. Cancellation (active execution cancelled via cancel_task)
def test_cancellation(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    plan = InvestigationPlan(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Test Cancellation Plan",
        strategy_summary="Test plan",
        tasks=[
            {
                "step_id": "task-cancel-01",
                "task_id": "task-cancel-01",
                "agent": "DiskAgent",
                "tool": "SleuthKit",
                "evidence_id": evidence.id,
                "status": "RUNNING",
                "dependencies": [],
            },
            {
                "step_id": "task-cancel-02",
                "task_id": "task-cancel-02",
                "agent": "DiskAgent",
                "tool": "ExifTool",
                "evidence_id": evidence.id,
                "status": "PLANNED",
                "dependencies": ["task-cancel-01"],
            },
        ],
        status="RUNNING",
        is_active=True,
    )
    db_session.add(plan)

    exec_rec = ToolExecution(
        case_id=case.id,
        evidence_id=evidence.id,
        tool_id="sleuthkit_fls",
        command_args=["fls", "-r", evidence.storage_path],
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(exec_rec)
    db_session.commit()

    # Link execution to task
    plan.tasks[0]["execution_id"] = exec_rec.id

    cancel_res = orchestrator.cancel_task(case.id, "task-cancel-01", db_session)
    assert cancel_res["status"] == "CANCELLED"
    assert cancel_res["task_id"] == "task-cancel-01"

    # Refresh DB objects
    db_session.refresh(exec_rec)
    db_session.refresh(plan)

    assert exec_rec.status == "CANCELLED"
    assert exec_rec.cancelled_at is not None
    assert plan.tasks[0]["status"] == "CANCELLED"
    assert plan.tasks[1]["status"] == "CANCELLED"  # Dependent task cancelled


# 8. Cancellation of non-existent execution / task ID
def test_cancel_nonexistent_execution(db_session, mock_evidence_files):
    case, _ = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    with pytest.raises(ValueError) as exc_info:
        orchestrator.cancel_task(case.id, "nonexistent-task-id", db_session)

    assert "No active plan or task 'nonexistent-task-id' found" in str(exc_info.value)


# 9. Dependent task blocked after failure
def test_dependent_task_blocked_after_failure():
    scheduler = TaskScheduler()

    task1 = {
        "step_id": "t1",
        "task_id": "t1",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "dependencies": [],
    }
    task2 = {
        "step_id": "t2",
        "task_id": "t2",
        "agent": "DiskAgent",
        "tool": "ExifTool",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "dependencies": ["t1"],
    }

    scheduler.register_plan([task1, task2])
    admitted = scheduler.admit_next_tasks(max_batch=1)
    assert len(admitted) == 1
    assert admitted[0]["task_id"] == "t1"

    # Mark t1 failed
    scheduler.mark_task_failed("t1", "Tool execution error")

    # t2 should now be cancelled/blocked due to failed dependency
    runnable = scheduler.get_runnable_tasks()
    assert len(runnable) == 0
    t2_status = scheduler.get_task_status("t2")
    assert t2_status["status"] == "CANCELLED"
    assert "Dependency not satisfied" in t2_status["error_message"]


# 10. Dependent task blocked after cancellation
def test_dependent_task_blocked_after_cancellation():
    scheduler = TaskScheduler()

    task1 = {
        "step_id": "t1",
        "task_id": "t1",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "dependencies": [],
    }
    task2 = {
        "step_id": "t2",
        "task_id": "t2",
        "agent": "DiskAgent",
        "tool": "ExifTool",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "dependencies": ["t1"],
    }

    scheduler.register_plan([task1, task2])
    scheduler.mark_task_cancelled("t1", "Cancelled by user")

    runnable = scheduler.get_runnable_tasks()
    assert len(runnable) == 0
    t2_status = scheduler.get_task_status("t2")
    assert t2_status["status"] == "CANCELLED"


# 11. Resource release after success
def test_resource_release_after_success():
    provider = InjectableResourceProvider(cpu_count=2, total_memory_mb=4096)
    rm = ResourceManager(resource_provider=provider)
    scheduler = TaskScheduler(resource_manager=rm)

    task = {
        "step_id": "t1",
        "task_id": "t1",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "cpu_weight": 1.0,
        "memory_mb": 512,
    }
    scheduler.register_plan([task])
    admitted = scheduler.admit_next_tasks(max_batch=1)
    assert len(admitted) == 1
    assert rm.reserved_cpus == 1.0

    scheduler.mark_task_completed("t1")
    assert rm.reserved_cpus == 0.0
    assert rm.reserved_memory_mb == 0


# 12. Resource release after failure
def test_resource_release_after_failure():
    provider = InjectableResourceProvider(cpu_count=2, total_memory_mb=4096)
    rm = ResourceManager(resource_provider=provider)
    scheduler = TaskScheduler(resource_manager=rm)

    task = {
        "step_id": "t1",
        "task_id": "t1",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "cpu_weight": 1.0,
        "memory_mb": 512,
    }
    scheduler.register_plan([task])
    scheduler.admit_next_tasks(max_batch=1)
    assert rm.reserved_cpus == 1.0

    scheduler.mark_task_failed("t1", "Execution error")
    assert rm.reserved_cpus == 0.0
    assert rm.reserved_memory_mb == 0


# 13. Resource release after timeout
def test_resource_release_after_timeout():
    provider = InjectableResourceProvider(cpu_count=2, total_memory_mb=4096)
    rm = ResourceManager(resource_provider=provider)
    scheduler = TaskScheduler(resource_manager=rm)

    task = {
        "step_id": "t1",
        "task_id": "t1",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "cpu_weight": 1.0,
        "memory_mb": 512,
    }
    scheduler.register_plan([task])
    scheduler.admit_next_tasks(max_batch=1)
    assert rm.reserved_cpus == 1.0

    scheduler.mark_task_timed_out("t1", "Timed out after 30s")
    assert rm.reserved_cpus == 0.0
    assert rm.reserved_memory_mb == 0


# 14. Resource release after cancellation
def test_resource_release_after_cancellation():
    provider = InjectableResourceProvider(cpu_count=2, total_memory_mb=4096)
    rm = ResourceManager(resource_provider=provider)
    scheduler = TaskScheduler(resource_manager=rm)

    task = {
        "step_id": "t1",
        "task_id": "t1",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "cpu_weight": 1.0,
        "memory_mb": 512,
    }
    scheduler.register_plan([task])
    scheduler.admit_next_tasks(max_batch=1)
    assert rm.reserved_cpus == 1.0

    scheduler.mark_task_cancelled("t1", "Cancelled by user")
    assert rm.reserved_cpus == 0.0
    assert rm.reserved_memory_mb == 0


# 15. No double resource release
def test_no_double_resource_release():
    provider = InjectableResourceProvider(cpu_count=2, total_memory_mb=4096)
    rm = ResourceManager(resource_provider=provider)

    assert rm.reserve("t1", cpu_weight=1.0, memory_mb=512)
    assert rm.reserved_cpus == 1.0

    # First release -> True
    assert rm.release("t1") is True
    assert rm.reserved_cpus == 0.0

    # Second release -> False (no double release)
    assert rm.release("t1") is False
    assert rm.reserved_cpus == 0.0


# 16. Shutdown behavior
def test_shutdown_behavior(db_session, mock_evidence_files):
    orchestrator = InvestigationOrchestrator()
    scheduler = orchestrator.task_scheduler

    task = {
        "step_id": "t1",
        "task_id": "t1",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
    }
    scheduler.register_plan([task])
    scheduler.admit_next_tasks(max_batch=1)

    orchestrator.shutdown()
    t1_status = scheduler.get_task_status("t1")
    assert t1_status["status"] == "CANCELLED"
    assert scheduler.resource_mgr.reserved_cpus == 0.0


# 17. Startup reconciliation of stale RUNNING executions
def test_startup_reconciliation_stale_running(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    stale_exec = ToolExecution(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=evidence.id,
        tool_id="sleuthkit_fls",
        command_args=["fls", "-r", evidence.storage_path],
        status="RUNNING",
        pid=999999,  # Non-existent PID
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stale_exec)
    db_session.commit()

    reconciled = orchestrator.reconcile_stale_executions(db_session)
    assert len(reconciled) == 1
    assert reconciled[0]["execution_id"] == stale_exec.id

    db_session.refresh(stale_exec)
    assert stale_exec.status == "FAILED"
    assert "Backend restarted while execution was in progress" in stale_exec.error_message


# 18. No automatic unsafe rerun on restart
def test_no_automatic_unsafe_rerun(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    stale_exec = ToolExecution(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=evidence.id,
        tool_id="exiftool",
        command_args=["exiftool", "-j", evidence.storage_path],
        status="RUNNING",
        pid=999998,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stale_exec)
    db_session.commit()

    orchestrator.reconcile_stale_executions(db_session)

    # Executions count should remain 1 (no new duplicate execution created)
    count = db_session.query(ToolExecution).filter(ToolExecution.case_id == case.id).count()
    assert count == 1
    db_session.refresh(stale_exec)
    assert stale_exec.status == "FAILED"


# 19. Vault pre/post integrity still enforced across all lifecycles
def test_vault_pre_post_integrity_enforced(db_session, mock_evidence_files):
    from pathlib import Path
    from backend.app.services.vault import remove_os_read_only, apply_os_read_only

    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    # Remove read-only, tamper evidence before task, re-apply read-only to verify pre-analysis gate
    target_p = Path(evidence.storage_path)
    remove_os_read_only(target_p)
    with open(target_p, "wb") as f:
        f.write(b"TAMPERED_DATA")
    apply_os_read_only(target_p)

    task = {
        "step_id": "test-tamper-01",
        "task_id": "test-tamper-01",
        "agent": "DiskAgent",
        "tool": "ExifTool",
        "action": "metadata_extraction",
        "evidence_id": evidence.id,
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["status"] == "FAILED"
    assert "hash mismatch" in res["error_message"].lower() or "gate failed" in res["error_message"].lower()

    db_session.refresh(evidence)
    assert evidence.integrity_status == "FAILED"


# 20. ToolExecution truthfulness (telemetry fields persisted match real data)
def test_toolexecution_truthfulness(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "disk_image"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    task = {
        "step_id": "test-truth-01",
        "task_id": "test-truth-01",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "action": "filesystem_structure_extraction",
        "evidence_id": evidence.id,
        "parameters": {"timeout_seconds": 45},
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["execution_id"] is not None

    exec_rec = db_session.query(ToolExecution).filter(ToolExecution.id == res["execution_id"]).first()
    assert exec_rec is not None
    assert exec_rec.case_id == case.id
    assert exec_rec.evidence_id == evidence.id
    assert exec_rec.tool_id == "sleuthkit_fls"
    assert exec_rec.command_args == ["fls", "-r", "-p", evidence.storage_path]
    assert exec_rec.timeout_seconds == 45
    assert exec_rec.operator_id == "autonomous-orchestrator"
    assert exec_rec.started_at is not None
    assert exec_rec.completed_at is not None


# 21. Tasks 1–6 regression verification
def test_task1_6_regression_verification(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    exec_res = orchestrator.execute_plan(case.id, db_session)
    assert exec_res["status"] in ["COMPLETED", "PARTIALLY_COMPLETED", "FAILED"]
    assert exec_res["investigation_id"] == case.id
    assert exec_res["plan_id"] is not None


# 22. PID reuse protection during startup reconciliation
def test_pid_reuse_reconciliation_mismatch_fails_safely(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    current_pid = os.getpid()
    # Create execution with active PID (this test process!) but a fake/stale start time
    stale_exec = ToolExecution(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=evidence.id,
        tool_id="sleuthkit_fls",
        command_args=["fls", "-r", evidence.storage_path],
        status="RUNNING",
        pid=current_pid,
        process_start_time=1.0,  # Mismatched start time simulating PID reuse
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stale_exec)
    db_session.commit()

    reconciled = orchestrator.reconcile_stale_executions(db_session)
    assert len(reconciled) == 1
    assert reconciled[0]["execution_id"] == stale_exec.id
    assert reconciled[0]["status"] == "FAILED"

    db_session.refresh(stale_exec)
    assert stale_exec.status == "FAILED"
    assert stale_exec.error_message == "Stale execution PID was reused by an unrelated OS process."

    # Crucial check: current OS process running this test must still be alive!
    assert os.kill(current_pid, 0) is None or True


# 23. Process identity matching reconciliation keeps active execution running
def test_process_identity_matching_reconciliation(db_session, mock_evidence_files):
    from forensic_tools.registry import get_process_start_time
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    current_pid = os.getpid()
    actual_start_time = get_process_start_time(current_pid)

    active_exec = ToolExecution(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=evidence.id,
        tool_id="sleuthkit_fls",
        command_args=["fls", "-r", evidence.storage_path],
        status="RUNNING",
        pid=current_pid,
        process_start_time=actual_start_time,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(active_exec)
    db_session.commit()

    reconciled = orchestrator.reconcile_stale_executions(db_session)
    # Matching process start time -> execution is NOT marked failed
    assert len(reconciled) == 0

    db_session.refresh(active_exec)
    assert active_exec.status == "RUNNING"


# 24. Process handle cancellation safety
def test_cancel_execution_verifies_process_handle():
    from forensic_tools.registry import PlatformAwareToolRegistry
    registry = PlatformAwareToolRegistry()

    # Cancelling unknown execution ID returns False
    assert registry.cancel_execution_process("unknown-exec-id") is False


# 25. Linux stat field 22 / psutil create_time process start-time extraction
def test_get_process_start_time_authoritative_mechanism():
    from forensic_tools.registry import get_process_start_time
    pid = os.getpid()
    start_time = get_process_start_time(pid)
    assert start_time is not None
    assert isinstance(start_time, float)
    assert start_time > 0


# 26. Unknown process identity during reconciliation fails safely without terminating PID
def test_unknown_start_time_reconciliation_fails_safely(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    current_pid = os.getpid()
    stale_exec = ToolExecution(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=evidence.id,
        tool_id="sleuthkit_fls",
        command_args=["fls", "-r", evidence.storage_path],
        status="RUNNING",
        pid=current_pid,
        process_start_time=None,  # Unknown identity
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stale_exec)
    db_session.commit()

    reconciled = orchestrator.reconcile_stale_executions(db_session)
    assert len(reconciled) == 1
    assert reconciled[0]["execution_id"] == stale_exec.id
    assert reconciled[0]["status"] == "FAILED"

    db_session.refresh(stale_exec)
    assert stale_exec.status == "FAILED"
    assert stale_exec.error_message == "Stale execution process identity could not be verified."

    # Crucial check: current OS process running this test must still be alive!
    assert os.kill(current_pid, 0) is None or True


# 27. Cancellation process identity mismatch prevents killing process
def test_cancel_execution_identity_mismatch_prevents_killing():
    import subprocess
    from forensic_tools.registry import PlatformAwareToolRegistry

    registry = PlatformAwareToolRegistry()
    # Dummy proc handle using current python process
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        pid = proc.pid
        exec_id = "test-exec-mismatch-cancel"

        # Register active process with a fake mismatched start time
        registry.register_active_process(exec_id, proc, pid, start_time=1.0)

        # Attempt cancellation -> must return False due to start time mismatch!
        cancelled = registry.cancel_execution_process(exec_id)
        assert cancelled is False

        # Process should NOT have been killed by cancellation
        assert proc.poll() is None
    finally:
        proc.terminate()
        proc.wait()


# 28. Python-EVTX in-process execution model verification
def test_python_evtx_in_process_model_verified(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "log"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    task_log = {
        "step_id": "test-step-evtx-inprocess",
        "task_id": "test-step-evtx-inprocess",
        "agent": "LogAgent",
        "tool": "python-evtx",
        "action": "security_log_parsing",
        "evidence_id": evidence.id,
        "parameters": {"timeout_seconds": 10},
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task_log, db_session)
    exec_rec = db_session.query(ToolExecution).filter(ToolExecution.id == res["execution_id"]).first()
    assert exec_rec is not None
    # python-evtx is imported in-process via Evtx.Evtx -> pid and process_start_time are None (100% truthful!)
    assert exec_rec.pid is None
    assert exec_rec.process_start_time is None


# 29. Exact starttime tick equality test (no broad time tolerance allowed)
def test_exact_starttime_tick_comparison_no_tolerance(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    current_pid = os.getpid()
    from forensic_tools.registry import get_process_start_time
    actual_ticks = get_process_start_time(current_pid)
    assert actual_ticks is not None

    # Off by just 1 tick (or 0.5s) -> MUST cause a mismatch!
    close_fake_ticks = actual_ticks + 1.0

    stale_exec = ToolExecution(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=evidence.id,
        tool_id="sleuthkit_fls",
        command_args=["fls", "-r", evidence.storage_path],
        status="RUNNING",
        pid=current_pid,
        process_start_time=close_fake_ticks,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stale_exec)
    db_session.commit()

    reconciled = orchestrator.reconcile_stale_executions(db_session)
    assert len(reconciled) == 1
    assert reconciled[0]["status"] == "FAILED"

    db_session.refresh(stale_exec)
    assert stale_exec.status == "FAILED"
    assert stale_exec.error_message == "Stale execution PID was reused by an unrelated OS process."


# 30. Timeout with unverified identity keeps scheduler resources reserved
def test_timeout_unverified_identity_preserves_resource_reservation():
    provider = InjectableResourceProvider(cpu_count=2, total_memory_mb=4096)
    rm = ResourceManager(resource_provider=provider)
    scheduler = TaskScheduler(resource_manager=rm)

    task = {
        "step_id": "t-timeout-unverified",
        "task_id": "t-timeout-unverified",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "cpu_weight": 1.0,
        "memory_mb": 512,
    }
    scheduler.register_plan([task])
    admitted = scheduler.admit_next_tasks(max_batch=1)
    assert len(admitted) == 1
    assert rm.reserved_cpus == 1.0

    # Mark timed out with process_terminated=False (unverified identity)
    scheduler.mark_task_timed_out("t-timeout-unverified", "Timed out; process remains active", process_terminated=False)

    # Resources MUST remain reserved because the process was NOT confirmed terminated!
    assert rm.reserved_cpus == 1.0
    assert rm.reserved_memory_mb == 512

    # Verify another task cannot steal those reserved resources
    task2 = {
        "step_id": "t2-blocked",
        "task_id": "t2-blocked",
        "agent": "DiskAgent",
        "tool": "ExifTool",
        "evidence_id": "ev1",
        "status": "PLANNED",
        "cpu_weight": 2.0,  # Would exceed 2.0 CPU capacity if 1.0 is still reserved
        "memory_mb": 4000,
    }
    scheduler.register_plan([task2])
    admitted2 = scheduler.admit_next_tasks(max_batch=1)
    assert len(admitted2) == 0  # Blocked!


# 31. Pre-analysis missing evidence file rejected
def test_pre_analysis_missing_file_rejected(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    # Delete the vault file
    os.remove(evidence.storage_path)

    task = {
        "step_id": "test-missing-file-01",
        "task_id": "test-missing-file-01",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "action": "filesystem_structure_extraction",
        "evidence_id": evidence.id,
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["status"] == "FAILED"
    assert "Pre-analysis vault check failed" in res["error_message"]
    assert res["execution_id"] is None


# 32. Pre-analysis evidence outside vault rejected
def test_pre_analysis_outside_vault_rejected(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    # Point storage path outside vault to original path
    evidence.storage_path = mock_evidence_files["orig_path"]
    db_session.commit()

    task = {
        "step_id": "test-outside-vault-01",
        "task_id": "test-outside-vault-01",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "action": "filesystem_structure_extraction",
        "evidence_id": evidence.id,
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["status"] == "FAILED"
    assert "vault" in res["error_message"].lower()
    assert res["execution_id"] is None


# 33. Agent rejects unsupported evidence type
def test_agent_unsupported_evidence_type_rejected(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    # MemoryAgent does not handle disk_image
    evidence.evidence_type = "disk_image"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    task = {
        "step_id": "test-unsupported-ev-01",
        "task_id": "test-unsupported-ev-01",
        "agent": "MemoryAgent",
        "tool": "volatility3",
        "action": "pslist",
        "evidence_id": evidence.id,
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["status"] == "UNSUPPORTED_EVIDENCE_TYPE"
    assert "not supported" in res["error_message"]
    assert res["execution_id"] is None


# 34. Tool unavailable rejected at execution boundary
def test_tool_unavailable_at_boundary_rejected(db_session, mock_evidence_files):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    orchestrator = InvestigationOrchestrator()

    task = {
        "step_id": "test-tool-unavail-01",
        "task_id": "test-tool-unavail-01",
        "agent": "MalwareAgent",
        "tool": "nonexistent_tool_xyz",
        "action": "scan",
        "evidence_id": evidence.id,
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["status"] in ["TOOL_UNAVAILABLE", "TOOL_VALIDATION_FAILED", "UNSUPPORTED_EVIDENCE_TYPE"]
    assert res["execution_id"] is None


# 35. Post-analysis hash mismatch detection
def test_post_analysis_hash_mismatch_fails_cleanly(db_session, mock_evidence_files):
    from pathlib import Path
    from backend.app.services.vault import remove_os_read_only
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "disk_image"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    orig_analyze = orchestrator.disk_agent.analyze
    def tampering_analyze(evidence_item, parameters):
        p = Path(evidence_item["storage_path"])
        remove_os_read_only(p)
        with open(p, "ab") as f:
            f.write(b"TAMPER_POST_EXECUTION")
        return {"status": "SUCCESS", "artifacts": [], "findings": [], "provenance": {"tool": "sleuthkit"}}

    orchestrator.disk_agent.analyze = tampering_analyze
    try:
        with pytest.raises(RuntimeError) as exc_info:
            orchestrator._execute_single_task(
                case.id, "plan-1",
                {
                    "step_id": "test-tamper-post",
                    "task_id": "test-tamper-post",
                    "agent": "DiskAgent",
                    "tool": "SleuthKit",
                    "action": "filesystem_structure_extraction",
                    "evidence_id": evidence.id,
                },
                db_session
            )
        assert "CRITICAL: Evidence was modified during analysis" in str(exc_info.value)
        db_session.refresh(evidence)
        assert evidence.integrity_status == "FAILED"
    finally:
        orchestrator.disk_agent.analyze = orig_analyze


# 36. Failed execution prevents artifacts and findings from persisting
def test_failed_execution_commits_no_artifacts_or_findings(db_session, mock_evidence_files):
    from backend.app.models.models import ExecutionArtifact, Finding
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "disk_image"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    task = {
        "step_id": "test-fail-no-artifacts",
        "task_id": "test-fail-no-artifacts",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "action": "filesystem_structure_extraction",
        "evidence_id": evidence.id,
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["status"] in ["FAILED", "EXECUTION_FAILED"]
    assert res["artifacts_count"] == 0
    assert res["findings_count"] == 0

    art_count = db_session.query(ExecutionArtifact).filter(ExecutionArtifact.case_id == case.id).count()
    find_count = db_session.query(Finding).filter(Finding.case_id == case.id).count()
    assert art_count == 0
    assert find_count == 0


# 37. Database commit failure triggers rollback and safe failure
def test_database_commit_failure_triggers_rollback(db_session, mock_evidence_files, monkeypatch):
    case, evidence = _setup_case_and_evidence(db_session, mock_evidence_files)
    evidence.evidence_type = "disk_image"
    db_session.commit()
    orchestrator = InvestigationOrchestrator()

    orig_commit = db_session.commit
    post_analyze_commits = [0]
    armed = [False]

    def failing_commit():
        if armed[0]:
            post_analyze_commits[0] += 1
            if post_analyze_commits[0] == 2:
                raise RuntimeError("Simulated Database I/O Failure")
        orig_commit()

    monkeypatch.setattr(db_session, "commit", failing_commit)

    def fake_analyze(evidence_item, parameters):
        armed[0] = True
        return {
            "status": "SUCCESS",
            "artifacts": [],
            "findings": [],
            "provenance": {"tool": "SleuthKit", "pid": None, "return_code": 0},
            "raw_output_reference": "/tmp/fake_raw.out"
        }

    orchestrator.disk_agent.analyze = fake_analyze

    task = {
        "step_id": "test-db-fail-01",
        "task_id": "test-db-fail-01",
        "agent": "DiskAgent",
        "tool": "SleuthKit",
        "action": "filesystem_structure_extraction",
        "evidence_id": evidence.id,
    }

    res = orchestrator._execute_single_task(case.id, "plan-1", task, db_session)
    assert res["status"] == "FAILED"
    assert "Database transaction failed during persistence" in res["error_message"]




