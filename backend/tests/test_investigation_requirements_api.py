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
    InvestigationPlan
)

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix="_requirements_test.db")
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


@pytest.fixture
def test_user_and_case():
    db = TestSessionLocal()
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"req_investigator_{uuid.uuid4().hex[:6]}@agency.gov",
        name="Agent Mulder",
        password_hash=hash_password("Password123!"),
        role="ADMIN",
        is_active=True
    )
    db.add(user)
    db.commit()

    case_id = str(uuid.uuid4())
    case = Case(
        id=case_id,
        case_number=f"CAS-REQ-{uuid.uuid4().hex[:6].upper()}",
        name="Unauthorized Access and Data Exfiltration",
        description="Forensic investigation into lateral movement and unauthorized logins.",
        case_type="UNAUTHORIZED_ACCESS",
        objective="Determine initial access vector, credential compromise, and lateral movement.",
        priority="HIGH",
        status="ACTIVE",
        created_by=user_id,
        owner_id=user_id
    )
    db.add(case)
    db.commit()

    member = CaseMember(
        case_id=case_id,
        user_id=user_id,
        role="PRIMARY_INVESTIGATOR"
    )
    db.add(member)

    ev1 = EvidenceItem(
        id=str(uuid.uuid4()),
        case_id=case_id,
        name="Security_DC01.evtx",
        original_path="/evidence/Security_DC01.evtx",
        storage_path="/evidence/Security_DC01.evtx",
        evidence_type="WINDOWS_EVENT_LOG",
        detected_format="EVTX",
        size_bytes=1048576,
        sha256="1111111111111111111111111111111111111111111111111111111111111111",
        status="VERIFIED"
    )
    ev2 = EvidenceItem(
        id=str(uuid.uuid4()),
        case_id=case_id,
        name="triage_mem.raw",
        original_path="/evidence/triage_mem.raw",
        storage_path="/evidence/triage_mem.raw",
        evidence_type="MEMORY_DUMP",
        detected_format="RAW_IMAGE",
        size_bytes=4194304,
        sha256="2222222222222222222222222222222222222222222222222222222222222222",
        status="VERIFIED"
    )
    db.add(ev1)
    db.add(ev2)
    db.commit()

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "user": user,
        "case": case,
        "evidence": [ev1, ev2],
        "headers": headers,
        "db": db
    }
    db.close()


def test_get_case_requirements_generates_defaults(test_user_and_case):
    fixture = test_user_and_case
    case_id = fixture["case"].id
    headers = fixture["headers"]

    resp = client.get(f"/api/v1/cases/{case_id}/requirements", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["case_id"] == case_id
    assert len(data["requirements"]) >= 1
    assert len(data["available_evidence"]) == 2
    assert len(data["available_templates"]) == 13

    # First requirement should correspond to Windows login or auth
    first_req = data["requirements"][0]
    assert "id" in first_req
    assert "title" in first_req
    assert first_req["approval_status"] == "APPROVED"


def test_add_custom_requirement(test_user_and_case):
    fixture = test_user_and_case
    case_id = fixture["case"].id
    headers = fixture["headers"]
    ev_ids = [e.id for e in fixture["evidence"]]

    payload = {
        "title": "Check for PowerShell encoded command executions",
        "description": "Inspect process launch events and script block logs for Base64 encoded payloads.",
        "category": "COMMAND_EXECUTION",
        "selected_evidence_ids": [ev_ids[0]],
        "scope": {
            "time_range_start": "2026-01-01T00:00:00Z",
            "relevant_processes": ["powershell.exe", "pwsh.exe"]
        },
        "expected_outputs": ["TIMELINE_EVENTS", "SCRIPT_BLOCK_RECORDS"],
        "approval_status": "APPROVED"
    }

    resp = client.post(f"/api/v1/cases/{case_id}/requirements", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    reqs = data["requirements"]
    custom_req = next((r for r in reqs if r["title"] == payload["title"]), None)
    assert custom_req is not None
    assert custom_req["category"] == "COMMAND_EXECUTION"
    assert custom_req["selected_evidence_ids"] == [ev_ids[0]]
    assert custom_req["scope"]["relevant_processes"] == ["powershell.exe", "pwsh.exe"]


def test_patch_requirement_approval_and_scope(test_user_and_case):
    fixture = test_user_and_case
    case_id = fixture["case"].id
    headers = fixture["headers"]

    # First fetch current requirements
    get_resp = client.get(f"/api/v1/cases/{case_id}/requirements", headers=headers)
    assert get_resp.status_code == 200
    reqs = get_resp.json()["requirements"]
    req_to_modify = reqs[0]
    target_id = req_to_modify["id"]

    patch_payload = {
        "approval_status": "REJECTED",
        "description": "Investigator deemed this inquiry out of current operational scope.",
        "expected_outputs": ["FILTERED_LOGS"]
    }

    resp = client.patch(f"/api/v1/cases/{case_id}/requirements/{target_id}", json=patch_payload, headers=headers)
    assert resp.status_code == 200, resp.text
    updated_data = resp.json()

    updated_req = next(r for r in updated_data["requirements"] if r["id"] == target_id)
    assert updated_req["approval_status"] == "REJECTED"
    assert updated_req["description"] == "Investigator deemed this inquiry out of current operational scope."
    assert updated_req["expected_outputs"] == ["FILTERED_LOGS"]


def test_delete_requirement(test_user_and_case):
    fixture = test_user_and_case
    case_id = fixture["case"].id
    headers = fixture["headers"]

    get_resp = client.get(f"/api/v1/cases/{case_id}/requirements", headers=headers)
    reqs = get_resp.json()["requirements"]
    initial_count = len(reqs)
    to_delete = reqs[-1]["id"]

    resp = client.delete(f"/api/v1/cases/{case_id}/requirements/{to_delete}", headers=headers)
    assert resp.status_code == 200, resp.text
    updated_data = resp.json()

    assert len(updated_data["requirements"]) == initial_count - 1
    assert not any(r["id"] == to_delete for r in updated_data["requirements"])


def test_generate_plan_from_requirements(test_user_and_case):
    fixture = test_user_and_case
    case_id = fixture["case"].id
    headers = fixture["headers"]

    # Re-approve all requirements first
    get_resp = client.get(f"/api/v1/cases/{case_id}/requirements", headers=headers)
    reqs = get_resp.json()["requirements"]
    for r in reqs:
        r["approval_status"] = "APPROVED"

    save_resp = client.put(f"/api/v1/cases/{case_id}/requirements", json={"requirements": reqs, "objective": "Full intrusion analysis"}, headers=headers)
    assert save_resp.status_code == 200

    plan_resp = client.post(f"/api/v1/cases/{case_id}/requirements/generate-plan", headers=headers)
    assert plan_resp.status_code == 200, plan_resp.text
    plan_data = plan_resp.json()

    assert "id" in plan_data
    assert plan_data["case_id"] == case_id
    assert len(plan_data["tasks"]) > 0
    # Verify tasks have requirement_id or rationale with requirement details
    tasks_with_reqs = [t for t in plan_data["tasks"] if t.get("requirement_id") or (t.get("rationale") and t["rationale"].get("requirement_id"))]
    assert len(tasks_with_reqs) > 0
