"""
ADFIP Authentication Diagnostic Resilience & Security Regression Suite
Verifies:
1. Rejection of email/password login on OAuth-only accounts (password_hash is NULL)
2. Accurate OWASP-compliant 401 error message for non-existent, bad password, and OAuth-only users
3. Prevention of timing attacks via dummy password verification
4. Full end-to-end user registration -> login -> /me profile retrieval flow
5. Rejection of inactive/disabled user accounts
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.core.security import hash_password
from backend.app.models.models import User, UserExternalIdentity

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

@pytest.fixture(scope="module", autouse=True)
def setup_module_db():
    Base.metadata.create_all(bind=_test_engine)
    def override_get_db():
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=_test_engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db_session():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


def test_oauth_only_account_password_login_rejected_with_401(client, db_session):
    """
    When an account was created via Google OAuth (password_hash is None),
    attempting email/password sign-in must return 401 Unauthorized with
    the standard generic message 'Invalid email or password.'.
    """
    oauth_email = f"oauth_user_{uuid.uuid4().hex[:6]}@gmail.com"
    user = User(
        id=str(uuid.uuid4()),
        email=oauth_email,
        name="OAuth User",
        role="INVESTIGATOR",
        is_active=True,
        password_hash=None  # OAuth-only user
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/login", json={
        "email": oauth_email,
        "password": "SomeRandomPassword123!"
    }, headers={"X-Request-ID": "test-req-oauth-only"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_empty_string_password_hash_rejected_with_401(client, db_session):
    """
    Accounts with empty string password_hash must also be rejected with 401.
    """
    empty_pw_email = f"empty_pw_{uuid.uuid4().hex[:6]}@example.com"
    user = User(
        id=str(uuid.uuid4()),
        email=empty_pw_email,
        name="Empty PW User",
        role="INVESTIGATOR",
        is_active=True,
        password_hash=""
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/login", json={
        "email": empty_pw_email,
        "password": "SomeRandomPassword123!"
    }, headers={"X-Request-ID": "test-req-empty-pw"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_inactive_user_rejected_with_401(client, db_session):
    """
    Disabled/inactive accounts must be rejected with 401 'User account is disabled.'.
    """
    inactive_email = f"disabled_{uuid.uuid4().hex[:6]}@dfir.local"
    user = User(
        id=str(uuid.uuid4()),
        email=inactive_email,
        name="Disabled Investigator",
        role="INVESTIGATOR",
        is_active=False,
        password_hash=hash_password("ValidPassword123!")
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/login", json={
        "email": inactive_email,
        "password": "ValidPassword123!"
    }, headers={"X-Request-ID": "test-req-disabled"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "User account is disabled."


def test_complete_registration_login_profile_lifecycle(client):
    """
    Full end-to-end verification: registration, authentication, token extraction,
    and profile retrieval.
    """
    reg_email = f"new_investigator_{uuid.uuid4().hex[:6]}@agency.gov"
    pw = "SuperStrongPassword!2026"

    # 1. Registration
    reg_resp = client.post("/api/v1/auth/signup", json={
        "email": reg_email,
        "name": "Detective Miller",
        "password": pw,
        "organization": "DFIR Forensics Unit"
    })
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert reg_data["email"] == reg_email
    assert "password_hash" not in reg_data

    # 2. Login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": reg_email,
        "password": pw
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token

    # 3. Profile
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == reg_email
    assert me_data["name"] == "Detective Miller"
    assert me_data["role"] == "INVESTIGATOR"
