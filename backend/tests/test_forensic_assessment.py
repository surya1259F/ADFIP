import os
import tempfile
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.models import User, Case, EvidenceItem, InvestigationPlan

_test_db_fd, _test_db_path = tempfile.mkstemp(suffix="_assessment_test.db")
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
    app.dependency_overrides.clear()
    if os.path.exists(_test_db_path):
        os.remove(_test_db_path)


@pytest.fixture
def test_setup():
    db: Session = TestSessionLocal()
    try:
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            email=f"assessment_inv_{uuid.uuid4().hex[:6]}@agency.gov",
            name="Lead Examiner Jane Doe",
            password_hash=hash_password("Pass123!"),
            role="ADMIN",
            is_active=True,
        )
        db.add(user)

        case_id = str(uuid.uuid4())
        case = Case(
            id=case_id,
            case_number=f"CAS-{uuid.uuid4().hex[:8].upper()}",
            title="Forensic Assessment Test Case",
            description="Testing explainable assessment and investigator authority",
            owner_id=user_id,
            created_by=user_id,
            status="OPEN",
            case_type="DATA_EXFILTRATION",
            priority="HIGH",
        )
        db.add(case)

        evidence = EvidenceItem(
            id=str(uuid.uuid4()),
            case_id=case_id,
            name="disk_evidence.dd",
            original_path="/tmp/disk_evidence.dd",
            storage_path="/tmp/disk_evidence.dd",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            evidence_type="DISK_IMAGE",
            size_bytes=1048576,
        )
        db.add(evidence)

        plan = InvestigationPlan(
            id=str(uuid.uuid4()),
            case_id=case_id,
            status="PLANNED",
            strategy_summary="Test plan",
            tasks=[],
            is_active=True,
            version=1,
            resource_snapshot={
                "requirements": [
                    {
                        "requirement_id": "req-1",
                        "title": "Identify external exfiltration channels",
                        "status": "COMPLETED",
                        "priority": "HIGH",
                        "questions": ["Which external IPs were contacted?"],
                    }
                ]
            },
        )
        db.add(plan)
        db.commit()

        token = create_access_token(user_id=user.id, email=user.email, role=user.role)
        headers = {"Authorization": f"Bearer {token}"}
        return {"headers": headers, "case_id": case_id, "user_id": user_id}
    finally:
        db.close()


def test_forensic_assessment_calculation(test_setup):
    headers = test_setup["headers"]
    case_id = test_setup["case_id"]

    response = client.get(f"/api/v1/cases/{case_id}/findings/assessment", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "classification" in data
    assert data["classification"] in [
        "CONFIRMED_ATTACK",
        "LIKELY_ATTACK",
        "INCONCLUSIVE",
        "NO_ATTACK_OBSERVED",
        "INSUFFICIENT_EVIDENCE",
    ]
    assert "evidence_strength_score" in data
    assert 0.0 <= data["evidence_strength_score"] <= 100.0
    assert "score_breakdown" in data
    assert "relevance" in data["score_breakdown"]
    assert "investigation_completeness" in data
    assert data["investigation_completeness"]["total_requirements"] == 1


def test_investigator_assessment_decision_workflow(test_setup):
    headers = test_setup["headers"]
    case_id = test_setup["case_id"]

    payload = {
        "decision": "ACCEPT",
        "rationale": "Forensic observations and tool execution artifacts empirically verified.",
    }
    response = client.post(
        f"/api/v1/cases/{case_id}/findings/assessment/decision",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["investigator_decision"] == "ACCEPT"
    assert "Forensic observations and tool execution artifacts" in data["investigator_rationale"]
