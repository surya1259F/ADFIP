import hashlib
import io
import os
import stat
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import Base, engine, SessionLocal, get_db
from backend.app.services.vault import verify_os_read_only, remove_os_read_only

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db():
    from backend.app.core.config import settings
    settings.JWT_SECRET_KEY = "adfir-test-jwt-secret-key-production-hardening-32bytes"
    app.dependency_overrides.clear()
    Base.metadata.create_all(bind=engine)
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from backend.app.models.models import User, Case, CaseMember, EvidenceItem, ChainOfCustodyEvent

@pytest.fixture
def auth_headers(db_session: Session):
    email = f"investigator_{os.urandom(4).hex()}@adfip.local"
    signup_res = client.post("/api/v1/auth/signup", json={
        "email": email,
        "name": "Lead Forensic Investigator",
        "password": "InvestigationPass123!"
    })
    assert signup_res.status_code in (200, 201), signup_res.text
    user_id = signup_res.json()["id"]

    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "InvestigationPass123!"
    })
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    user = db_session.query(User).filter(User.id == user_id).first()
    return {"Authorization": f"Bearer {token}"}, user

@pytest.fixture
def active_case(auth_headers):
    headers, user = auth_headers
    case_res = client.post(
        "/api/v1/cases/",
        headers=headers,
        json={
            "name": f"Forensic Case {os.urandom(3).hex()}",
            "description": "Verifying complete forensic evidence acquisition boundary"
        }
    )
    assert case_res.status_code in (200, 201), case_res.text
    case_data = case_res.json()
    return case_data

def test_real_file_stream_acquisition_into_vault(auth_headers, active_case, db_session: Session):
    """
    Test 1, 3, 4, 5, 6, 7:
    Investigator selects real file -> multipart upload acquires bytes ->
    backend calculates SHA-256 -> vault copy stored -> independent vault hash verified ->
    read-only protection applied -> custody recorded.
    """
    headers, user = auth_headers
    case = active_case

    # Real sample evidence bytes (simulating screenshot or document)
    sample_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xff\xa4" + os.urandom(1024)
    expected_sha256 = hashlib.sha256(sample_bytes).hexdigest()
    filename = "investigator_screenshot_sample.png"

    files = {
        "file": (filename, io.BytesIO(sample_bytes), "image/png")
    }
    data = {
        "case_id": case["id"],
        "name": filename,
        "evidence_type": "screenshot",
        "notes": "Acquired via desktop Browse Evidence workflow"
    }

    res = client.post(
        f"/api/v1/cases/{case["id"]}/evidence/intake",
        headers=headers,
        files=files,
        data=data
    )

    assert res.status_code == 201, f"Failed: {res.text}"
    ev_data = res.json()

    # 1. Evidence record properties
    assert ev_data["case_id"] == case["id"]
    assert ev_data["name"] == filename
    assert ev_data["sha256"] == expected_sha256
    assert ev_data["size_bytes"] == len(sample_bytes)
    assert ev_data["status"] == "REGISTERED"
    assert ev_data["integrity_status"] == "VERIFIED"
    assert ev_data["read_only_verified"] is True
    assert ev_data["storage_path"] is not None

    vault_file = Path(ev_data["storage_path"])
    assert vault_file.exists(), "Vault file must exist on disk"
    assert vault_file.is_file(), "Vault target must be a regular file"

    # 2. Independent disk hash verification
    vault_hasher = hashlib.sha256()
    with open(vault_file, "rb") as f:
        while chunk := f.read(65536):
            vault_hasher.update(chunk)
    disk_hash = vault_hasher.hexdigest()
    assert disk_hash == expected_sha256, "Independent vault disk hash must exactly match acquisition SHA-256"

    # 3. Read-only verification
    assert verify_os_read_only(vault_file) is True, "Vault file must be protected with OS read-only permissions"

    # 4. Chain of custody verification
    custody_events = db_session.query(ChainOfCustodyEvent).filter(
        ChainOfCustodyEvent.evidence_id == ev_data["id"]
    ).all()
    assert len(custody_events) >= 1
    reg_event = custody_events[0]
    assert reg_event.event_type == "EVIDENCE_REGISTERED"
    assert reg_event.sha256 == expected_sha256
    assert reg_event.destination_path == str(vault_file.resolve())
    assert reg_event.actor_id == user.id

    # Clean up read-only file so temp directory can be removed if needed
    remove_os_read_only(vault_file)

def test_real_path_intake_unaltered_source(auth_headers, active_case, db_session: Session):
    """
    Test Option A: Valid host path intake preserves original file without altering it,
    creates distinct vault copy, hashes, and sets read-only on vault copy only.
    """
    headers, _ = auth_headers
    case = active_case

    with tempfile.NamedTemporaryFile(suffix=".dd", delete=False) as tmp:
        source_content = b"ORIGINAL_SUSPECT_DISK_DATA_" + os.urandom(2048)
        tmp.write(source_content)
        tmp_path = Path(tmp.name)

    try:
        source_sha256 = hashlib.sha256(source_content).hexdigest()
        source_mtime_before = tmp_path.stat().st_mtime

        res = client.post(
            f"/api/v1/cases/{case["id"]}/evidence/intake",
            headers=headers,
            json={
                "file_path": str(tmp_path),
                "name": tmp_path.name,
                "evidence_type": "disk_image"
            }
        )

        assert res.status_code == 201, f"Failed: {res.text}"
        ev_data = res.json()
        assert ev_data["sha256"] == source_sha256

        # Source file must NOT be modified or moved
        assert tmp_path.exists(), "Original source file must remain intact outside vault"
        with open(tmp_path, "rb") as f:
            assert f.read() == source_content, "Original source bytes must not be modified"
        assert tmp_path.stat().st_mtime == source_mtime_before, "Source file mtime must be untouched"

        # Vault copy must exist and be distinct from source
        vault_file = Path(ev_data["storage_path"])
        assert vault_file.resolve() != tmp_path.resolve(), "Vault copy must be separate from original source"
        assert vault_file.exists()
        assert verify_os_read_only(vault_file) is True

        remove_os_read_only(vault_file)
    finally:
        tmp_path.unlink(missing_ok=True)

def test_nonexistent_source_path_fails_safely(auth_headers, active_case):
    """
    Test 8: Nonexistent source path fails safely with HTTP 400.
    """
    headers, _ = auth_headers
    case = active_case

    res = client.post(
        f"/api/v1/cases/{case["id"]}/evidence/intake",
        headers=headers,
        json={
            "file_path": "/nonexistent/path/to/evidence_sample_does_not_exist.raw",
            "name": "sample.raw",
            "evidence_type": "disk_image"
        }
    )
    assert res.status_code == 400
    assert "not found on disk" in res.text.lower() or "not found" in res.text.lower()

def test_empty_stream_fails_safely(auth_headers, active_case):
    """
    Empty evidence stream (0 bytes) must fail safely.
    """
    headers, _ = auth_headers
    case = active_case

    files = {
        "file": ("empty.png", io.BytesIO(b""), "image/png")
    }
    data = {
        "case_id": case["id"],
        "name": "empty.png"
    }

    res = client.post(
        f"/api/v1/cases/{case["id"]}/evidence/intake",
        headers=headers,
        files=files,
        data=data
    )
    assert res.status_code in (400, 422)
    assert "empty" in res.text.lower() or "0 bytes" in res.text.lower()


def test_unauthenticated_evidence_intake_rejected(active_case):
    """
    Intake without auth token must be rejected with HTTP 401.
    """
    case = active_case
    files = {"file": ("test.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")}
    res = client.post(
        f"/api/v1/cases/{case['id']}/evidence/intake",
        files=files,
        data={"name": "test.png"}
    )
    assert res.status_code == 401


def test_unauthorized_case_evidence_intake_rejected(auth_headers, active_case, db_session: Session):
    """
    Another investigator who is not a member of the case must be rejected with HTTP 403.
    """
    other_email = f"other_{os.urandom(4).hex()}@adfip.local"
    signup_res = client.post("/api/v1/auth/signup", json={
        "email": other_email,
        "name": "Other Investigator",
        "password": "InvestigationPass123!"
    })
    assert signup_res.status_code in (200, 201)
    login_res = client.post("/api/v1/auth/login", json={
        "email": other_email,
        "password": "InvestigationPass123!"
    })
    other_token = login_res.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    case = active_case
    files = {"file": ("test.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + os.urandom(64)), "image/png")}
    res = client.post(
        f"/api/v1/cases/{case['id']}/evidence/intake",
        headers=other_headers,
        files=files,
        data={"name": "test.png"}
    )
    assert res.status_code in (403, 404)


def test_cors_preflight_and_error_headers(auth_headers, active_case):
    """
    OPTIONS preflight and error responses must include CORS headers for frontend origins.
    """
    case = active_case
    url = f"/api/v1/cases/{case['id']}/evidence/intake"

    # Preflight
    options_res = client.options(
        url,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"
        }
    )
    assert options_res.status_code == 200
    assert options_res.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Error response (empty payload) must also include CORS
    headers, _ = auth_headers
    headers["Origin"] = "http://localhost:5173"
    bad_res = client.post(url, headers=headers, json={})
    assert bad_res.status_code == 400
    assert bad_res.headers.get("access-control-allow-origin") == "http://localhost:5173"

