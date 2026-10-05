"""
ADFIP — Authoritative Report Readiness Negative Test Suite (Section 7)

Comprehensive tests proving that the 14 mandatory readiness gates strictly BLOCK
unready or compromised investigations from generating official forensic reports,
while allowing working exports with mandatory preliminary disclosures.

Tests:
TEST A — Valid investigation: all 14 gates pass -> official report succeeds (200)
TEST B — Tampered execution output: byte change -> Gate 9 fails -> official report blocked (422)
TEST C — Ungrounded finding: missing provenance -> Gate 10 fails -> official report blocked (422)
TEST D — Missing correlation: correlation omitted -> Gate 12 fails -> official report blocked (422)
TEST E — Bypass attempt: enforce_readiness=false sent -> STILL blocked by backend authority (422)
TEST F — Working export: incomplete case -> working export succeeds (200) with 'WORKING EXPORT — NOT FINAL'
TEST G — Unreviewed finding: pending review -> Gate 11 fails -> official report blocked (422)
TEST H — Closed case: case closed -> Gate 2 fails -> official report blocked (422)
"""

import os
import uuid
import hashlib
import tempfile
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.models import (
    Case,
    CaseMember,
    User,
    EvidenceItem,
    ChainOfCustodyEvent,
    ForensicExecution,
    ToolExecution,
    ExecutionOutput,
    StructuredArtifact,
    DeterministicFinding,
    ForensicCorrelationGroup,
    InvestigationPlan,
    InvestigatorReviewRecord,
    InvestigatorDecision,
    Report
)
from backend.app.services.report_readiness import ReportReadinessService

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _create_authorized_user_and_case(db, prefix="ready_test"):
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"{prefix}_{uuid.uuid4().hex[:6]}@adfip.local",
        name=f"Investigator {prefix}",
        organization="Forensic Testing Unit",
        role="INVESTIGATOR",
        is_active=True,
        password_hash=hash_password("Pass1234!")
    )
    db.add(user)
    db.commit()

    cid = f"case-{prefix}-{uuid.uuid4().hex[:8]}"
    case = Case(
        id=cid,
        case_number=f"CAS-{uuid.uuid4().hex[:8].upper()}",
        name=f"Case {prefix}",
        description="Negative readiness suite test case",
        created_by=user.id,
        owner_id=user.id,
        status="ACTIVE"
    )
    db.add(case)
    db.commit()

    member = CaseMember(
        id=str(uuid.uuid4()),
        case_id=case.id,
        user_id=user.id,
        role="PRIMARY_INVESTIGATOR"
    )
    db.add(member)
    db.commit()
    return user, case


def _setup_fully_valid_investigation(db, user, case, temp_dir):
    """
    Sets up a complete, forensically sound investigation that satisfies all 14 readiness gates.
    Returns a dict containing references to created records and output file paths.
    """
    # 1. Evidence item
    ev_path = os.path.join(temp_dir, "evidence.raw")
    with open(ev_path, "wb") as f:
        f.write(b"RAW_EVIDENCE_BYTES_FOR_READINESS_TEST")
    h_ev = hashlib.sha256(b"RAW_EVIDENCE_BYTES_FOR_READINESS_TEST").hexdigest()

    ev = EvidenceItem(
        id=str(uuid.uuid4()),
        case_id=case.id,
        investigation_id=case.id,
        name="evidence.raw",
        evidence_type="disk_image",
        source_kind="DISK_IMAGE",
        original_path=ev_path,
        storage_path=ev_path,
        sha256_hash=h_ev,
        sha256=h_ev,
        size_bytes=len(b"RAW_EVIDENCE_BYTES_FOR_READINESS_TEST"),
        status="ACQUIRED",
        integrity_status="VERIFIED",
        intelligence_json={"mime_type": "application/x-raw-disk-image", "format": "raw"},
        metadata_json={"source": "test_disk"},
        read_only_verified=True
    )
    db.add(ev)

    # 2. Strategy plan
    plan = InvestigationPlan(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Automated Forensic Strategy Plan",
        strategy_summary="Deterministic analysis plan",
        tasks=[{"task_id": "T1", "tool": "sleuthkit", "status": "COMPLETED"}],
        status="COMPLETED"
    )
    db.add(plan)

    # 3. Execution
    fe = ForensicExecution(
        id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=ev.id,
        task_key="DISK_PARSING",
        tool_id="sleuthkit",
        tool_version="4.12.0",
        host_platform="Linux",
        host_architecture="x86_64",
        workspace_path=temp_dir,
        execution_status="COMPLETED",
        status="COMPLETED",
        exit_code=0
    )
    db.add(fe)

    # 4. Output with real file and matching SHA-256
    out_file = os.path.join(temp_dir, "tool_output.json")
    out_bytes = b'{"files": ["/etc/passwd", "/usr/bin/login"]}'
    with open(out_file, "wb") as f:
        f.write(out_bytes)
    h_out = hashlib.sha256(out_bytes).hexdigest()

    exo = ExecutionOutput(
        id=str(uuid.uuid4()),
        case_id=case.id,
        execution_id=fe.id,
        request_id=fe.request_id,
        evidence_id=ev.id,
        tool_id="sleuthkit",
        output_type="TOOL_OUTPUT",
        filename="tool_output.json",
        relative_path="tool_output.json",
        storage_path=out_file,
        sha256_hash=h_out,
        size_bytes=len(out_bytes)
    )
    db.add(exo)

    # 5. Structured artifact
    art = StructuredArtifact(
        id=str(uuid.uuid4()),
        case_id=case.id,
        execution_id=fe.id,
        raw_output_id=exo.id,
        evidence_id=ev.id,
        parser_name="sleuthkit_fls",
        artifact_type="PERSISTENCE_ENTRY",
        normalized_data={"entry": "/etc/cron.d/job"},
        sha256_hash="c" * 64,
        source_raw_output_hash=exo.sha256_hash,
        extraction_status="EXTRACTED"
    )
    db.add(art)

    # 6. Correlation group
    cg = ForensicCorrelationGroup(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Crontab Execution Correlation",
        description="Correlated scheduled task execution",
        member_artifact_ids=[art.id],
        member_event_ids=[],
        relationship_ids=[],
        contributing_domains=["PERSISTENCE"],
        source_evidence_ids=[ev.id],
        confidence_score=0.95,
        provenance={"rule": "RULE-CRON-01"},
        sha256_hash="d" * 64
    )
    db.add(cg)

    # 7. Deterministic finding grounded in evidence and artifact
    f1 = DeterministicFinding(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Unauthorized Persistence Job Detected",
        description="Verified cron job scheduling unauthorized execution",
        observed_facts=[{"command": "/usr/local/bin/agent"}],
        finding_type="persistence_mechanism",
        severity="HIGH",
        severity_rule="RULE-HIGH-01",
        confidence=0.95,
        supporting_artifact_ids=[art.id],
        supporting_evidence_ids=[ev.id],
        supporting_group_ids=[cg.id],
        provenance={"engine": "ADFIP_Deterministic_V1"},
        sha256_hash="e" * 64
    )
    f1.verification_status = "SUPPORTED"
    db.add(f1)

    # 8. Investigator review (ACCEPT)
    rev = InvestigatorReviewRecord(
        id=str(uuid.uuid4()),
        case_id=case.id,
        investigator_id=user.id,
        investigator_name=user.name,
        target_type="FINDING",
        target_id=f1.id,
        decision="ACCEPT",
        comment="Corroborated by disk inode and cron artifact.",
        supporting_references=[art.id, ev.id],
        resulting_workflow_action="ACCEPTED_CLAIM",
        sha256_hash="f" * 64
    )
    db.add(rev)

    # 9. Investigator final authorization (CONFIRM)
    dec = InvestigatorDecision(
        id=str(uuid.uuid4()),
        case_id=case.id,
        investigator_id=user.id,
        investigator_name=user.name,
        decision="CONFIRM",
        rationale="All findings verified and corroborated.",
        timestamp=datetime.now(timezone.utc)
    )
    db.add(dec)
    db.commit()

    return {
        "user": user,
        "case": case,
        "evidence": ev,
        "execution": fe,
        "output": exo,
        "output_file": out_file,
        "artifact": art,
        "correlation": cg,
        "finding": f1,
        "review": rev,
        "decision": dec
    }


def _auth_headers(user: User) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# TESTS A THROUGH H
# =============================================================================

def test_scenario_a_valid_investigation_readiness_and_report_success(db, tmp_path):
    """
    TEST A — Valid Investigation:
    All 14 gates pass -> readiness.ready = True -> official report generation succeeds (200).
    """
    user, case = _create_authorized_user_and_case(db, "valid_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is True
    assert readiness.passed_gates == 14
    assert len(readiness.blocking_reasons) == 0

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/generate",
        headers=headers,
        json={"title": "Official Certified Incident Report"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "OFFICIAL_FINAL"
    assert "report_hash" in data and len(data["report_hash"]) == 64


def test_scenario_b_tampered_execution_output_blocks_gate_9(db, tmp_path):
    """
    TEST B — Modify Execution Output:
    Modify raw bytes after execution -> Gate 9 fails -> official report returns HTTP 422.
    """
    user, case = _create_authorized_user_and_case(db, "tamper_out_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Tamper with the execution output file on disk
    with open(setup["output_file"], "wb") as f:
        f.write(b"TAMPERED_OUTPUT_CORRUPTED_BYTES")

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is False
    g9 = next(g for g in readiness.gates if g.gate_number == 9)
    assert g9.passed is False
    assert any("EXECUTION_OUTPUT_INTEGRITY" in r.code for r in readiness.blocking_reasons)

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/generate",
        headers=headers,
        json={"title": "Attempt Report with Tampered Output"}
    )
    assert res.status_code == 422
    assert "REPORT_NOT_READY" in res.text


def test_scenario_c_ungrounded_finding_blocks_gate_10(db, tmp_path):
    """
    TEST C — Ungrounded Finding:
    Create a finding with no valid provenance -> Gate 10 fails -> official report returns HTTP 422.
    """
    user, case = _create_authorized_user_and_case(db, "ungrounded_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Add an ungrounded finding without valid supporting references
    ungrounded_f = DeterministicFinding(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Unverified Speculative Exfiltration",
        description="Speculation without supporting artifacts or evidence",
        observed_facts=[],
        finding_type="network_exfiltration",
        severity="LOW",
        severity_rule="RULE-SPEC",
        confidence=0.3,
        supporting_artifact_ids=[],
        supporting_evidence_ids=[],
        provenance={},
        sha256_hash="0" * 64
    )
    ungrounded_f.verification_status = "SUPPORTED"  # Claims to be supported but has no anchors
    db.add(ungrounded_f)
    db.commit()

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is False
    g10 = next(g for g in readiness.gates if g.gate_number == 10)
    assert g10.passed is False

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/generate",
        headers=headers,
        json={"title": "Attempt Report with Ungrounded Finding"}
    )
    assert res.status_code == 422


def test_scenario_d_missing_correlation_blocks_gate_12(db, tmp_path):
    """
    TEST D — Missing Correlation:
    Findings exist but correlation group is deleted/missing -> Gate 12 fails -> official report returns HTTP 422.
    """
    user, case = _create_authorized_user_and_case(db, "nocorr_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Remove the required correlation group
    db.delete(setup["correlation"])
    db.commit()

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is False
    g12 = next(g for g in readiness.gates if g.gate_number == 12)
    assert g12.passed is False
    assert any("CORRELATION" in r.code for r in readiness.blocking_reasons)

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/generate",
        headers=headers,
        json={"title": "Attempt Report without Correlation"}
    )
    assert res.status_code == 422


def test_scenario_e_client_bypass_attempt_is_rejected_by_backend(db, tmp_path):
    """
    TEST E — Bypass Attempt:
    Client sends options={'enforce_readiness': False} on an unready case -> backend STILL enforces gates -> HTTP 422.
    """
    user, case = _create_authorized_user_and_case(db, "bypass_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Invalidate Gate 9 by removing output file
    os.remove(setup["output_file"])

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/generate",
        headers=headers,
        json={
            "title": "Bypass Attempt Report",
            "options": {"enforce_readiness": False, "skip_checks": True}
        }
    )
    assert res.status_code == 422
    assert "REPORT_NOT_READY" in res.text


def test_scenario_f_working_export_succeeds_with_disclosure(db, tmp_path):
    """
    TEST F — Working Export:
    Incomplete investigation allowed to generate working export with 'WORKING EXPORT — NOT FINAL' disclosure.
    """
    user, case = _create_authorized_user_and_case(db, "wk_usr")
    ev_path = os.path.join(str(tmp_path), "partial.raw")
    with open(ev_path, "wb") as f:
        f.write(b"PARTIAL_EVIDENCE_FOR_WORKING_EXPORT")
    ev = EvidenceItem(
        id=str(uuid.uuid4()),
        case_id=case.id,
        investigation_id=case.id,
        name="partial.raw",
        evidence_type="disk_image",
        source_kind="DISK_IMAGE",
        original_path=ev_path,
        storage_path=ev_path,
        sha256_hash="1" * 64,
        size_bytes=len(b"PARTIAL_EVIDENCE_FOR_WORKING_EXPORT"),
        status="ACQUIRED",
        integrity_status="VERIFIED"
    )
    db.add(ev)
    db.commit()

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/working-export",
        headers=headers,
        json={"title": "Preliminary Field Export"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "WORKING_EXPORT"
    assert "WORKING EXPORT" in data["full_report_markdown"].upper()


def test_scenario_g_unreviewed_finding_blocks_gate_11(db, tmp_path):
    """
    TEST G — Unreviewed Finding:
    A finding exists with zero reviews recorded -> Gate 11 fails -> official report blocked (422).
    """
    user, case = _create_authorized_user_and_case(db, "unrev_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Add a new finding with no corresponding InvestigatorReviewRecord
    f2 = DeterministicFinding(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Second Unreviewed Finding",
        description="Pending investigator review",
        observed_facts=[{"test": 1}],
        finding_type="anomaly",
        severity="MEDIUM",
        severity_rule="RULE-MED",
        confidence=0.8,
        supporting_artifact_ids=[setup["artifact"].id],
        supporting_evidence_ids=[setup["evidence"].id],
        provenance={"engine": "test"},
        sha256_hash="9" * 64
    )
    f2.verification_status = "SUPPORTED"
    db.add(f2)
    db.commit()

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is False
    g11 = next(g for g in readiness.gates if g.gate_number == 11)
    assert g11.passed is False
    assert any("PENDING_FINDING_REVIEWS" in r.code for r in readiness.blocking_reasons)

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/generate",
        headers=headers,
        json={"title": "Attempt Report with Unreviewed Finding"}
    )
    assert res.status_code == 422


def test_scenario_h_closed_case_blocks_gate_2(db, tmp_path):
    """
    TEST H — Closed Case:
    Case is closed -> Gate 2 fails -> official report blocked (422).
    """
    user, case = _create_authorized_user_and_case(db, "closed_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Close the case
    case.status = "CLOSED"
    db.commit()

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is False
    g2 = next(g for g in readiness.gates if g.gate_number == 2)
    assert g2.passed is False
    assert any("CASE_CLOSED" in r.code for r in readiness.blocking_reasons)

    headers = _auth_headers(user)
    res = client.post(
        f"/api/v1/cases/{case.id}/reports/generate",
        headers=headers,
        json={"title": "Attempt Report on Closed Case"}
    )
    assert res.status_code == 422


def test_scenario_i_canonical_execution_missing_blocks_gate_7(db, tmp_path):
    """
    TEST I — Canonical Execution Missing:
    Only legacy ToolExecution exists, no ForensicExecution -> Gate 7 fails with CANONICAL_EXECUTION_MISSING -> 422.
    """
    user, case = _create_authorized_user_and_case(db, "legacy_exec_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Replace ForensicExecution with legacy ToolExecution
    db.delete(setup["execution"])
    db.commit()

    legacy_te = ToolExecution(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=setup["evidence"].id,
        tool_id="sleuthkit",
        status="COMPLETED"
    )
    db.add(legacy_te)
    db.commit()

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is False
    g7 = next(g for g in readiness.gates if g.gate_number == 7)
    assert g7.passed is False
    assert any(r.code == "CANONICAL_EXECUTION_MISSING" for r in readiness.blocking_reasons)


def test_scenario_j_missing_execution_outputs_blocks_gate_8(db, tmp_path):
    """
    TEST J — Missing Execution Outputs:
    Execution completed but output records are missing -> Gate 8 fails -> 422.
    """
    user, case = _create_authorized_user_and_case(db, "no_output_usr")
    setup = _setup_fully_valid_investigation(db, user, case, str(tmp_path))

    # Remove the output record
    db.delete(setup["output"])
    db.commit()

    readiness = ReportReadinessService.evaluate(db, case, user)
    assert readiness.ready is False
    g8 = next(g for g in readiness.gates if g.gate_number == 8)
    assert g8.passed is False
    assert any("OUTPUT" in r.code for r in readiness.blocking_reasons)
