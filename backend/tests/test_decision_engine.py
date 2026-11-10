import os
import tempfile
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.models import (
    User,
    Case,
    CaseMember,
    EvidenceItem,
    EvidenceIntelligence,
    InvestigationPlan,
    InvestigationTask,
    ToolSelectionRecord
)
from backend.app.services.decision_engine import (
    EvidenceDecisionEngine,
    ObjectiveArchetype,
    QuestionFeasibility
)
from forensic_tools.registry import PlatformAwareToolRegistry

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix="_decision_engine_test.db")
os.close(_test_db_fd)
TEST_ENGINE = create_engine(f"sqlite:///{_test_db_path}", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=TEST_ENGINE)
    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)


@pytest.fixture(scope="function")
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_user_and_case(db: Session, objective: str = "Investigate unauthorized credential abuse and ransomware deployment"):
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"investigator_{uuid.uuid4().hex[:6]}@dfir.org",
        name="Lead Forensic Examiner",
        role="INVESTIGATOR",
        is_active=True,
        password_hash=hash_password("ExaminerPass@123")
    )
    db.add(user)
    db.commit()

    cid = f"case-{uuid.uuid4().hex[:8]}"
    case = Case(
        id=cid,
        case_number=f"CAS-{uuid.uuid4().hex[:8].upper()}",
        name="Incident Response Alpha",
        objective=objective,
        case_type="MALWARE_ANALYSIS",
        priority="HIGH",
        status="ACTIVE",
        created_by=user.id,
        owner_id=user.id
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


def get_auth_headers(user: User) -> dict:
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# UNIT TESTS
# =============================================================================

def test_classify_objective_all_archetypes():
    """Verifies that case objectives correctly trigger corresponding ObjectiveArchetypes."""
    # 1. Unauthorized Access
    archs = EvidenceDecisionEngine.classify_objective("Investigate failed logon brute-force attempts and credential theft")
    assert ObjectiveArchetype.UNAUTHORIZED_ACCESS in archs

    # 2. Malware Infection
    archs = EvidenceDecisionEngine.classify_objective("System infected by ransomware payload and dropper executable")
    assert ObjectiveArchetype.MALWARE_INFECTION in archs

    # 3. Suspicious Execution
    archs = EvidenceDecisionEngine.classify_objective("Unusual powershell script execution and living off the land binaries")
    assert ObjectiveArchetype.SUSPICIOUS_EXECUTION in archs

    # 4. Data Exfiltration
    archs = EvidenceDecisionEngine.classify_objective("Suspected data theft, staging archive exfiltration to external server")
    assert ObjectiveArchetype.DATA_EXFILTRATION in archs

    # 5. Suspicious Network
    archs = EvidenceDecisionEngine.classify_objective("Analyze network pcap for C2 beacon traffic and DNS tunnel")
    assert ObjectiveArchetype.SUSPICIOUS_NETWORK in archs

    # 6. Browser Activity
    archs = EvidenceDecisionEngine.classify_objective("Examine web history for phishing download and visited URL")
    assert ObjectiveArchetype.BROWSER_ACTIVITY in archs

    # 7. Anti-Forensics / Deleted files
    archs = EvidenceDecisionEngine.classify_objective("Attacker wiped system logs, timestomped files, and deleted staging directory")
    assert ObjectiveArchetype.ANTI_FORENSICS_DELETED_FILES in archs

    # 8. USB device usage
    archs = EvidenceDecisionEngine.classify_objective("Check if unauthorized USB flash drive or removable thumb drive was plugged in")
    assert ObjectiveArchetype.USB_DEVICE_USAGE in archs

    # 9. Privilege escalation
    archs = EvidenceDecisionEngine.classify_objective("Investigate privilege escalation, sudo abuse, and token impersonation")
    assert ObjectiveArchetype.PRIVILEGE_ESCALATION in archs

    # 10. Insider activity
    archs = EvidenceDecisionEngine.classify_objective("Departing disgruntled employee exfiltrating intellectual property after hours")
    assert ObjectiveArchetype.INSIDER_ACTIVITY in archs

    # 11. Generic baseline is always included
    archs = EvidenceDecisionEngine.classify_objective(None)
    assert ObjectiveArchetype.GENERIC_INCIDENT in archs


def test_generate_investigative_questions():
    """Verifies decomposition of objective into structured hypothesis-neutral questions."""
    questions = EvidenceDecisionEngine.generate_investigative_questions(
        objective_text="Investigate unauthorized logon and ransomware encryption",
        case_type="RANSOMWARE"
    )
    assert len(questions) >= 3

    # Check question schema fields
    codes = [q["code"] for q in questions]
    assert "AUTH_EVENTS" in codes
    assert "SUSPICIOUS_BINARIES" in codes

    for q in questions:
        assert "question_id" in q and q["question_id"].startswith("IQ-")
        assert "question_text" in q and len(q["question_text"]) > 10
        assert "category" in q
        assert "required_evidence_domains" in q
        assert "required_capabilities" in q
        assert "hypothesis" in q


def test_evaluate_feasibility_present_vs_missing_evidence():
    """Verifies feasibility assessment assigns INVESTIGABLE vs REQUIRES_ADDITIONAL_EVIDENCE."""
    tool_reg = PlatformAwareToolRegistry()
    questions = [
        {
            "question_id": "IQ-01",
            "code": "AUTH_EVENTS",
            "required_evidence_domains": ["WINDOWS_EVENT_LOG", "LOG"],
            "required_capabilities": ["EVENT_LOG_ANALYSIS"],
            "hypothesis": "Compromised credentials used."
        },
        {
            "question_id": "IQ-02",
            "code": "NETWORK_BEACON",
            "required_evidence_domains": ["PCAP", "NETWORK_CAPTURE"],
            "required_capabilities": ["PCAP_ANALYSIS"],
            "hypothesis": "C2 communication occurred."
        }
    ]

    # Only Windows Event Log is provided, NO PCAP
    evidence_profiles = [
        {
            "evidence_id": "ev-evtx-01",
            "name": "Security.evtx",
            "category": "log",
            "subtype": "windows_event_log",
            "investigative_domains": ["WINDOWS_EVENT_LOG", "LOG"],
            "integrity_valid": True
        }
    ]

    evaluated = EvidenceDecisionEngine.evaluate_evidence_feasibility(questions, evidence_profiles, tool_reg)

    q1 = next(q for q in evaluated if q["code"] == "AUTH_EVENTS")
    assert q1["feasibility"] == QuestionFeasibility.INVESTIGABLE.value
    assert "ev-evtx-01" in q1["matching_evidence_ids"]

    q2 = next(q for q in evaluated if q["code"] == "NETWORK_BEACON")
    assert q2["feasibility"] == QuestionFeasibility.REQUIRES_ADDITIONAL_EVIDENCE.value
    assert len(q2["missing_evidence_domains"]) > 0


def test_resolve_explainable_tools():
    """Verifies plain-language rationale and limitations generation for tool selection."""
    tool_reg = PlatformAwareToolRegistry()
    ev_item = {
        "evidence_id": "ev-01",
        "name": "target_image.raw",
        "category": "disk_image",
        "detected_format": "RAW_IMAGE"
    }
    q = {"question_id": "IQ-01", "question_text": "Extract filesystem structure?"}

    res = EvidenceDecisionEngine.resolve_explainable_tools(
        capability_id="FILESYSTEM_ANALYSIS",
        evidence_item=ev_item,
        investigative_question=q,
        tool_registry=tool_reg
    )

    assert res["capability_id"] == "FILESYSTEM_ANALYSIS"
    assert "why_selected" in res and len(res["why_selected"]) > 10
    assert "risks_and_limitations" in res
    assert "expected_output" in res
    assert res["selection_status"] in ["SELECTED", "NO_COMPATIBLE_TOOL"]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

def test_decision_engine_generate_plan_integration(db_session: Session):
    """Verifies end-to-end plan generation, task sequencing, and ToolSelectionRecord persistence."""
    user, case = create_user_and_case(db_session, "Investigate malware dropper and unauthorized execution")

    # Add real test evidence item
    ev = EvidenceItem(
        id=str(uuid.uuid4()),
        case_id=case.id,
        name="suspect_sample.bin",
        evidence_type="binary",
        source_kind="malware_sample",
        size_bytes=1024,
        sha256="aa" * 32,
        original_path="/tmp/suspect_sample.bin",
        storage_path="/tmp/suspect_sample.bin",
        read_only_verified=True,
        integrity_status="VERIFIED"
    )
    db_session.add(ev)
    db_session.commit()

    plan_res = EvidenceDecisionEngine.generate_evidence_driven_plan(
        db=db_session,
        case_id=case.id,
        current_user=user
    )

    assert "plan_id" in plan_res
    assert len(plan_res["investigative_questions"]) > 0
    assert len(plan_res["tasks"]) > 0
    assert len(plan_res["tool_selections"]) > 0

    # Verify persistent records in database
    plan_db = db_session.query(InvestigationPlan).filter(InvestigationPlan.id == plan_res["plan_id"]).first()
    assert plan_db is not None
    assert plan_db.is_active is True

    tasks_db = db_session.query(InvestigationTask).filter(InvestigationTask.plan_id == plan_db.id).all()
    assert len(tasks_db) == len(plan_res["tasks"])

    selections_db = db_session.query(ToolSelectionRecord).filter(ToolSelectionRecord.plan_id == plan_db.id).all()
    assert len(selections_db) == len(plan_res["tool_selections"])


def test_investigative_questions_api_endpoint(db_session: Session):
    """Verifies GET /api/v1/cases/{case_id}/investigative-questions returns structured questions."""
    user, case = create_user_and_case(db_session, "Investigate unauthorized remote desktop logons and lateral movement")
    headers = get_auth_headers(user)

    res = client.get(f"/api/v1/cases/{case.id}/investigative-questions", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["case_id"] == case.id
    assert data["total_questions"] >= 2
    assert "questions" in data
    assert len(data["questions"]) == data["total_questions"]

    # Verify each question has feasibility evaluation
    for q in data["questions"]:
        assert q["feasibility"] in [
            QuestionFeasibility.INVESTIGABLE.value,
            QuestionFeasibility.PARTIALLY_INVESTIGABLE.value,
            QuestionFeasibility.REQUIRES_ADDITIONAL_EVIDENCE.value,
            QuestionFeasibility.UNSUPPORTED_BY_TOOLS.value,
            QuestionFeasibility.NOT_APPLICABLE.value
        ]


def test_add_custom_investigative_question(db_session: Session):
    """Verifies adding a custom question via POST /api/v1/cases/{case_id}/investigative-questions."""
    user, case = create_user_and_case(db_session, "Investigate database tamper incident")
    headers = get_auth_headers(user)

    payload = {
        "question_text": "Did unauthorized SQL queries alter the audit ledger tables?",
        "category": "DATA_INTEGRITY",
        "hypothesis": "Adversary gained direct DB credentials and bypassed application layer."
    }

    res = client.post(f"/api/v1/cases/{case.id}/investigative-questions", headers=headers, json=payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["question"]["question_text"] == payload["question_text"]
    assert data["question"]["category"] == "DATA_INTEGRITY"
    assert data["question"]["approval_status"] == "APPROVED"
    assert data["question"]["hypothesis"] == payload["hypothesis"]

    # Verify question is persisted in GET
    get_res = client.get(f"/api/v1/cases/{case.id}/investigative-questions", headers=headers)
    assert get_res.status_code == 200
    all_q = get_res.json()["questions"]
    found = [q for q in all_q if q.get("question_id") == data["question"]["question_id"]]
    assert len(found) == 1
    assert found[0]["question_text"] == payload["question_text"]


def test_patch_investigative_question_approval_and_edit(db_session: Session):
    """Verifies investigator governance: approving, rejecting, and editing questions."""
    user, case = create_user_and_case(db_session, "Phishing email investigation")
    headers = get_auth_headers(user)

    # Initial questions
    init_res = client.get(f"/api/v1/cases/{case.id}/investigative-questions", headers=headers)
    assert init_res.status_code == 200
    questions = init_res.json()["questions"]
    assert len(questions) > 0
    target_q = questions[0]
    target_id = target_q.get("question_id") or target_q.get("code")
    assert target_id is not None

    # 1. Reject question
    patch_rej = client.patch(
        f"/api/v1/cases/{case.id}/investigative-questions/{target_id}",
        headers=headers,
        json={"approval_status": "REJECTED"}
    )
    assert patch_rej.status_code == 200, patch_rej.text
    rej_data = patch_rej.json()
    assert rej_data["updated_question"]["approval_status"] == "REJECTED"

    # 2. Edit text and approve
    patch_edit = client.patch(
        f"/api/v1/cases/{case.id}/investigative-questions/{target_id}",
        headers=headers,
        json={
            "question_text": "Updated question: What was the primary email attachment hash?",
            "approval_status": "APPROVED",
            "hypothesis": "Malicious macro contained in XLSM attachment."
        }
    )
    assert patch_edit.status_code == 200, patch_edit.text
    edit_data = patch_edit.json()
    assert edit_data["updated_question"]["question_text"] == "Updated question: What was the primary email attachment hash?"
    assert edit_data["updated_question"]["approval_status"] == "APPROVED"
    assert edit_data["updated_question"]["hypothesis"] == "Malicious macro contained in XLSM attachment."

    # 3. Verify changes persist across GET
    verify_res = client.get(f"/api/v1/cases/{case.id}/investigative-questions", headers=headers)
    assert verify_res.status_code == 200
    updated_q = next(q for q in verify_res.json()["questions"] if (q.get("question_id") == target_id or q.get("code") == target_id))
    assert updated_q["question_text"] == "Updated question: What was the primary email attachment hash?"
    assert updated_q["approval_status"] == "APPROVED"


def test_bulk_save_investigative_questions(db_session: Session):
    """Verifies bulk saving questions via PUT /api/v1/cases/{case_id}/investigative-questions."""
    user, case = create_user_and_case(db_session, "Ransomware outbreak analysis")
    headers = get_auth_headers(user)

    bulk_questions = [
        {
            "question_id": "IQ-91",
            "code": "RANSOM_EXT",
            "question_text": "Which encryption extension was appended to user files?",
            "category": "RANSOMWARE_ENCRYPTION",
            "hypothesis": "Files were renamed with .lockbit extension.",
            "approval_status": "APPROVED"
        },
        {
            "question_id": "IQ-92",
            "code": "VSS_DELETE",
            "question_text": "Was volume shadow copy service deleted via vssadmin?",
            "category": "ANTI_FORENSICS",
            "hypothesis": "Shadow copies purged prior to encryption.",
            "approval_status": "APPROVED"
        }
    ]

    put_res = client.put(
        f"/api/v1/cases/{case.id}/investigative-questions",
        headers=headers,
        json={"questions": bulk_questions}
    )
    assert put_res.status_code == 200, put_res.text
    put_data = put_res.json()
    assert len(put_data["questions"]) == 2
    assert put_data["questions"][0]["question_id"] == "IQ-91"
    assert put_data["questions"][1]["question_id"] == "IQ-92"

    # Confirm persistence
    get_res = client.get(f"/api/v1/cases/{case.id}/investigative-questions", headers=headers)
    assert get_res.status_code == 200
    saved = get_res.json()["questions"]
    assert len(saved) == 2
    assert saved[0]["question_text"] == "Which encryption extension was appended to user files?"


def test_evidence_intelligence_driven_questions(db_session: Session):
    """Verifies that evidence-type specific questions are generated for disk, memory, pcap, and event logs."""
    from backend.app.models.models import EvidenceItem
    user, case = create_user_and_case(db_session, "Lateral compromise assessment")

    # Add disk image evidence with valid non-null size_bytes
    disk_ev = EvidenceItem(
        id=f"ev-disk-{uuid.uuid4().hex[:6]}",
        case_id=case.id,
        name="server_c_drive.raw",
        original_path="/tmp/server_c_drive.raw",
        storage_path="/tmp/server_c_drive.raw",
        evidence_type="DISK_IMAGE",
        detected_format="raw",
        size_bytes=1048576,
        status="PRESERVED",
        sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
    )
    # Add memory dump evidence with valid non-null size_bytes
    mem_ev = EvidenceItem(
        id=f"ev-mem-{uuid.uuid4().hex[:6]}",
        case_id=case.id,
        name="server_ram.dmp",
        original_path="/tmp/server_ram.dmp",
        storage_path="/tmp/server_ram.dmp",
        evidence_type="MEMORY_DUMP",
        detected_format="raw",
        size_bytes=2097152,
        status="PRESERVED",
        sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    )
    db_session.add(disk_ev)
    db_session.add(mem_ev)
    db_session.commit()

    questions = EvidenceDecisionEngine.get_case_investigative_questions(db_session, case.id)
    q_categories = [q.get("category") for q in questions]

    # Verify evidence-driven categories are present
    assert any("FILESYSTEM" in c or "DELETED" in c for c in q_categories)
    assert any("MEMORY" in c or "VOLATILE" in c for c in q_categories)

    # Verify questions reference file system and memory injection/unlinked processes
    disk_qs = [q for q in questions if "FILESYSTEM" in q.get("category", "") or "DELETED" in q.get("category", "")]
    mem_qs = [q for q in questions if "MEMORY" in q.get("category", "") or "VOLATILE" in q.get("category", "")]
    assert len(disk_qs) > 0
    assert len(mem_qs) > 0
    assert any("file system" in q["question_text"].lower() or "unallocated" in q["question_text"].lower() for q in disk_qs)
    assert any("memory" in q["question_text"].lower() or "injection" in q["question_text"].lower() or "unlinked" in q["question_text"].lower() for q in mem_qs)


