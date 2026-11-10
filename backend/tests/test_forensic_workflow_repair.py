"""
ADFIP — Production Forensic Workflow Repair Regression Tests

Tests validating:
1. Canonical evidence type normalization and role distinction (RULE_RESOURCE vs TARGET_EVIDENCE).
2. Authoritative MalwareAgent compatibility (SUSPICIOUS_BINARY, PE/ELF/Mach-O executables, generic binaries).
3. Rule resources are not scanned as target evidence (RULE_RESOURCE_NOT_TARGET_EVIDENCE).
4. Case-context-first invariant: No findings produced without case_id/evidence context.
5. YARA execution contract: Real evidence + approved rule; rule cannot scan itself.
6. Deterministic confidence scoring (no hardcoded 0.85; explicit mathematical inputs).
7. Investigator review with 12 structured challenge categories, mandatory rationale, and integrity.
8. Request More Evidence pipeline re-entry with dynamic recommendations, insufficient_reason, and missing_info.
"""

import os
import json
import uuid
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import SessionLocal, engine, Base
from backend.app.core.security import hash_password, create_access_token
from backend.app.main import app
from backend.app.models.models import (
    Case,
    CaseMember,
    User,
    EvidenceItem,
    ChainOfCustodyEvent,
    StructuredArtifact,
    DeterministicFinding,
    InvestigatorReviewRecord,
    InvestigationPlan,
    AnalysisRequest
)
from backend.app.schemas.schemas import (
    InvestigatorReviewCreateRequest,
    RequestMoreEvidenceRequest,
    ChallengeCategory
)
from backend.app.services.investigator_review import InvestigatorReviewService
from forensic_tools.evidence_types import (
    EvidenceRole,
    CanonicalEvidenceClass,
    normalize_evidence_type,
    is_rule_resource,
    is_scannable_target,
    is_compatible_with_malware_analysis,
    calculate_deterministic_confidence,
    calculate_yara_match_confidence,
    get_recommended_capabilities_for_evidence
)
from agents.malware.malware_agent import MalwareAgent
from forensic_tools.yara.adapter import YaraAdapter
from forensic_tools.registry import PlatformAwareToolRegistry, ToolDefinition

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_user_and_case(db):
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"forensic_agent_{uuid.uuid4().hex[:6]}@adfir.local",
        name="Lead Forensic Investigator",
        role="INVESTIGATOR",
        is_active=True,
        password_hash=hash_password("Pass#123456")
    )
    db.add(user)
    db.commit()

    cid = f"case-fw-{uuid.uuid4().hex[:8]}"
    case = Case(
        id=cid,
        case_number=f"CAS-FW-{uuid.uuid4().hex[:8].upper()}",
        name="Forensic Workflow Case",
        description="Case for testing forensic workflow invariants",
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
    db.refresh(case)
    db.refresh(user)

    return user, case


def _get_auth_headers(user):
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. CANONICAL EVIDENCE TYPE NORMALIZATION & ROLES
# =============================================================================

def test_canonical_evidence_normalization():
    """Validates normalization of aliases, canonical classes, and roles."""
    # SUSPICIOUS_BINARY normalizes to MALWARE_SAMPLE target
    canon, role, meta = normalize_evidence_type("SUSPICIOUS_BINARY")
    assert canon == CanonicalEvidenceClass.MALWARE_SAMPLE
    assert role == EvidenceRole.TARGET_EVIDENCE
    assert meta["original_classification"] == "SUSPICIOUS_BINARY"
    assert is_scannable_target("SUSPICIOUS_BINARY") is True
    assert is_rule_resource("SUSPICIOUS_BINARY") is False

    # YARA_RULE is a RULE_RESOURCE, not a target
    canon_yr, role_yr, meta_yr = normalize_evidence_type("YARA_RULE")
    assert canon_yr == CanonicalEvidenceClass.YARA_RULE
    assert role_yr == EvidenceRole.RULE_RESOURCE
    assert is_rule_resource("YARA_RULE") is True
    assert is_scannable_target("YARA_RULE") is False

    # Executable classifications
    for ex_type in ["pe_executable", "PE_IMAGE", "ELF_EXECUTABLE", "macho_executable", "generic_binary"]:
        canon_ex, role_ex, _ = normalize_evidence_type(ex_type)
        assert role_ex == EvidenceRole.TARGET_EVIDENCE
        assert is_scannable_target(ex_type) is True


# =============================================================================
# 2. MALWARE AGENT AUTHORITATIVE COMPATIBILITY & CONCATENATION BUG FIX
# =============================================================================

def test_malware_agent_can_handle_authoritative():
    """
    Validates that MalwareAgent.can_handle():
    1. Accepts SUSPICIOUS_BINARY, GENERIC_BINARY, PE, ELF, Mach-O.
    2. Correctly rejects YARA_RULE.
    3. Has fixed the 'evtx' + 'file' string concatenation bug.
    """
    agent = MalwareAgent()

    # Supported target evidence types
    assert agent.can_handle("SUSPICIOUS_BINARY") is True
    assert agent.can_handle("suspicious_binary") is True
    assert agent.can_handle("generic_binary") is True
    assert agent.can_handle("pe_executable") is True
    assert agent.can_handle("elf_executable") is True
    assert agent.can_handle("macho_executable") is True
    assert agent.can_handle("malware_sample") is True
    assert agent.can_handle("file") is True
    assert agent.can_handle("binary") is True

    # Rule resources must NOT be accepted as scan targets
    assert agent.can_handle("YARA_RULE") is False
    assert agent.can_handle("yara_rule") is False
    assert agent.can_handle("rule") is False

    # Concatenation bug verification: 'file' must be supported individually
    assert is_compatible_with_malware_analysis("file") is True


# =============================================================================
# 3. RULE RESOURCES ARE NOT SCANNED AS TARGET EVIDENCE
# =============================================================================

def test_malware_agent_rejects_rule_resource_as_target():
    """
    Validates that MalwareAgent.analyze() rejects YARA_RULE as target evidence
    with status RULE_RESOURCE_NOT_TARGET_EVIDENCE and helpful guidance.
    """
    agent = MalwareAgent()
    evidence = {
        "investigation_id": "case-test-123",
        "id": "ev-rule-1",
        "name": "webshell.yar",
        "evidence_type": "YARA_RULE",
        "storage_path": "/vault/rules/webshell.yar"
    }

    result = agent.analyze(evidence)
    assert result["status"] == "RULE_RESOURCE_NOT_TARGET_EVIDENCE"
    assert "is a detection rule definition, not a forensic evidence scan target" in result["error"]
    assert result["artifacts"] == []
    assert result["findings"] == []
    assert result["provenance"]["role"] == "RULE_RESOURCE"


# =============================================================================
# 4. CASE-CONTEXT-FIRST INVARIANT
# =============================================================================

def test_case_context_mandatory_for_agent():
    """
    Validates that MalwareAgent.analyze() rejects execution when no verified
    case context or evidence ID is provided.
    """
    agent = MalwareAgent()

    # Missing case_id
    evidence_no_case = {
        "id": "ev-1",
        "name": "sample.exe",
        "evidence_type": "PE_EXECUTABLE",
        "storage_path": "/vault/sample.exe"
    }
    res_no_case = agent.analyze(evidence_no_case)
    assert res_no_case["status"] == "MISSING_CASE_CONTEXT"
    assert "Missing verified case context" in res_no_case["error"]
    assert res_no_case["findings"] == []

    # Missing evidence id
    evidence_no_id = {
        "investigation_id": "case-123",
        "name": "sample.exe",
        "evidence_type": "PE_EXECUTABLE",
        "storage_path": "/vault/sample.exe"
    }
    res_no_id = agent.analyze(evidence_no_id)
    assert res_no_id["status"] == "MISSING_CASE_CONTEXT"


# =============================================================================
# 5. YARA EXECUTION CONTRACT: REAL EVIDENCE + APPROVED RULE
# =============================================================================

def test_yara_execution_contract_rejects_rule_scanning_itself():
    """
    Validates that YaraAdapter rejects scanning when target path equals rule path.
    """
    from forensic_tools.yara.rules_manager import yara_rule_repo
    adapter = YaraAdapter()
    rule_info = yara_rule_repo.get_rule("adfir_webshell_indicators")
    assert rule_info is not None

    # Attempt to scan rule file using itself as the rule
    res, _ = adapter.scan_file(evidence_path=rule_info.absolute_path, rule_id="adfir_webshell_indicators")
    assert res.success is False
    assert "Target evidence is the YARA rule itself" in res.error_message


def test_yara_execution_contract_real_evidence_scan():
    """
    Validates scanning real target evidence with an approved rule file.
    """
    adapter = YaraAdapter()
    if not adapter.is_available():
        pytest.skip("Native YARA binary is not installed on host platform")
    from forensic_tools.yara.rules_manager import yara_rule_repo
    rule_info = yara_rule_repo.get_rule("adfir_webshell_indicators")
    assert rule_info is not None

    # Create target evidence containing webshell pattern
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as ef:
        ef.write(b'<?php system($_GET["cmd"]); eval(base64_decode($_POST["ev"])); ?>')
        evidence_path = ef.name

    try:
        res, info = adapter.scan_file(evidence_path=evidence_path, rule_id="adfir_webshell_indicators")
        assert res.evidence_path == evidence_path
        assert info is not None
        assert info.rule_id == "adfir_webshell_indicators"
    finally:
        os.unlink(evidence_path)


# =============================================================================
# 6. DETERMINISTIC CONFIDENCE SCORING (NO HARDCODED 0.85)
# =============================================================================

def test_deterministic_confidence_calculations():
    """
    Validates that confidence is dynamically calculated based on explicit
    mathematical factors, not a hardcoded 0.85.
    """
    # High confidence: verified integrity, high artifact confidence, corroborating sources
    high_score, high_inputs = calculate_deterministic_confidence(
        source_integrity=1.0,
        artifact_confidence=0.95,
        identifier_match_confidence=1.0,
        supporting_source_count=2,
        contradictory_evidence=False
    )
    assert 0.90 <= high_score <= 1.0
    assert high_score != 0.85
    assert high_inputs["source_integrity"] == 1.0
    assert high_inputs["contradictory_evidence"] is False

    # Lower confidence: partial confidence, contradictory evidence
    low_score, low_inputs = calculate_deterministic_confidence(
        source_integrity=0.5,
        artifact_confidence=0.5,
        identifier_match_confidence=0.5,
        supporting_source_count=0,
        contradictory_evidence=True
    )
    assert low_score < 0.35
    assert low_score != 0.85
    assert low_inputs["contradictory_evidence"] is True

    # YARA match confidence
    yara_score, yara_inputs = calculate_yara_match_confidence(
        match_count=2,
        string_count=3,
        rule_valid=True,
        source_integrity=1.0
    )
    assert 0.50 <= yara_score <= 1.0
    assert "string_matches_count" in yara_inputs


# =============================================================================
# 7. INVESTIGATOR REVIEW WITH 12 STRUCTURED CHALLENGE CATEGORIES
# =============================================================================

def test_investigator_review_challenge_categories_validation(db_session):
    """
    Validates:
    1. CHALLENGE decision requires one of 12 categories.
    2. CHALLENGE requires mandatory non-empty comment.
    3. Valid challenge persists challenge_category and maintains cryptographic integrity.
    """
    user, case = _create_user_and_case(db_session)

    # Create a deterministic finding
    df = DeterministicFinding(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Suspicious Cron Binary",
        description="Detected anomalous binary in /tmp",
        finding_type="MALWARE_INDICATOR",
        severity="HIGH",
        severity_rule="rule_cron_binary",
        confidence=0.82,
        confidence_inputs={"base": 0.8, "match_quality": "HIGH"},
        supporting_artifact_ids=[],
        supporting_evidence_ids=[],
        sha256_hash="f" * 64
    )
    db_session.add(df)
    db_session.commit()

    headers = _get_auth_headers(user)

    # 1. Invalid category should be rejected
    inv_payload = {
        "target_type": "FINDING",
        "target_id": df.id,
        "decision": "CHALLENGE",
        "challenge_category": "INVALID_NON_EXISTENT_CATEGORY",
        "comment": "Questioning this finding."
    }
    resp_inv = client.post(f"/api/v1/cases/{case.id}/review/decisions", json=inv_payload, headers=headers)
    assert resp_inv.status_code == 400
    assert "Invalid challenge category" in resp_inv.json()["detail"]

    # 2. Empty comment should be rejected for CHALLENGE
    no_comment_payload = {
        "target_type": "FINDING",
        "target_id": df.id,
        "decision": "CHALLENGE",
        "challenge_category": "CONFIDENCE",
        "comment": "   "
    }
    resp_no_com = client.post(f"/api/v1/cases/{case.id}/review/decisions", json=no_comment_payload, headers=headers)
    assert resp_no_com.status_code == 400
    assert "mandatory rationale" in resp_no_com.json()["detail"]

    # 3. Valid challenge with category CONFIDENCE
    valid_payload = {
        "target_type": "FINDING",
        "target_id": df.id,
        "decision": "CHALLENGE",
        "challenge_category": "CONFIDENCE",
        "comment": "Confidence 0.82 is unsubstantiated; binary lacks execution evidence in syslog.",
        "supporting_references": [df.id]
    }
    resp_val = client.post(f"/api/v1/cases/{case.id}/review/decisions", json=valid_payload, headers=headers)
    assert resp_val.status_code == 201
    val_data = resp_val.json()
    assert val_data["decision"] == "CHALLENGE"
    assert val_data["challenge_category"] == "CONFIDENCE"
    assert val_data["resulting_workflow_action"] == "CHALLENGED_CLAIM"

    # 4. Verify cryptographic integrity
    rev_id = val_data["id"]
    int_resp = client.get(f"/api/v1/cases/{case.id}/review/decisions/{rev_id}/integrity", headers=headers)
    assert int_resp.status_code == 200
    assert int_resp.json()["integrity_status"] == "VERIFIED"
    assert int_resp.json()["tamper_detected"] is False


# =============================================================================
# 8. REQUEST MORE EVIDENCE WORKFLOW WITH DYNAMIC RECOMMENDATIONS
# =============================================================================

def test_request_more_evidence_dynamic_pipeline(db_session):
    """
    Validates:
    1. get_review_items provides recommended_capabilities dynamically.
    2. request_more_evidence accepts insufficient_reason and missing_information.
    3. Successfully passes Governance Gate and queues AnalysisRequest.
    """
    user, case = _create_user_and_case(db_session)

    # Create evidence item
    ev = EvidenceItem(
        id=str(uuid.uuid4()),
        case_id=case.id,
        name="suspect.elf",
        evidence_type="ELF_EXECUTABLE",
        original_path="/original/evidence/suspect.elf",
        storage_path="/vault/suspect.elf",
        sha256_hash="a" * 64,
        size_bytes=1024,
        status="SECURED"
    )
    db_session.add(ev)

    df = DeterministicFinding(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Unidentified Linux Executable",
        description="Binary observed in /var/tmp",
        finding_type="SUSPICIOUS_ELF",
        severity="MEDIUM",
        severity_rule="rule_elf_tmp",
        confidence=0.65,
        confidence_inputs={"base": 0.65},
        supporting_artifact_ids=[],
        supporting_evidence_ids=[ev.id],
        sha256_hash="b" * 64
    )
    db_session.add(df)
    db_session.commit()

    headers = _get_auth_headers(user)

    # 1. Check get_review_items for dynamic recommendations
    resp_items = client.get(f"/api/v1/cases/{case.id}/review/items", headers=headers)
    assert resp_items.status_code == 200
    items_data = resp_items.json()
    finding_item = items_data["deterministic_findings"][0]
    rec_caps = finding_item["recommended_capabilities"]
    assert len(rec_caps) > 0
    # For ELF_EXECUTABLE: YARA_SCAN, STRINGS_ANALYSIS, METADATA_EXTRACTION, HASHING
    assert "YARA_SCAN" in rec_caps
    assert "STRINGS_ANALYSIS" in rec_caps

    # 2. Request More Evidence with insufficient_reason and missing_information
    rme_payload = {
        "target_type": "FINDING",
        "target_id": df.id,
        "evidence_id": ev.id,
        "analysis_objective": "Carve printable strings and extract embedded IP addresses",
        "requested_capability": "STRINGS_ANALYSIS",
        "parameters": {"min_len": 6},
        "comment": "Requesting deeper string extraction before confirming threat assessment.",
        "insufficient_reason": "ELF binary header confirmed but no IOC strings extracted.",
        "missing_information": "Embedded C2 IP addresses and function symbol names.",
        "supporting_references": [df.id, ev.id]
    }

    resp_rme = client.post(f"/api/v1/cases/{case.id}/review/request-more-evidence", json=rme_payload, headers=headers)
    assert resp_rme.status_code == 201
    rme_data = resp_rme.json()
    assert rme_data["workflow_status"] == "SCHEDULED"
    assert rme_data["governance_decision_id"] is not None
    assert rme_data["analysis_request_id"] is not None

    # Verify review record created with comment notes
    rev_record = db_session.query(InvestigatorReviewRecord).filter(
        InvestigatorReviewRecord.id == rme_data["review"]["id"]
    ).first()
    assert rev_record is not None
    assert rev_record.decision == "REQUEST_MORE_EVIDENCE"
    assert "Insufficient Reason: ELF binary header confirmed" in rev_record.comment
    assert "Missing Info: Embedded C2 IP addresses" in rev_record.comment
