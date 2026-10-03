import time
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal, ensure_user_auth_schema
from backend.app.core.security import hash_password, create_access_token
from backend.app.models.models import (
    User,
    UserExternalIdentity,
    OAuthState,
    OAuthExchangeCode,
)
from backend.app.services.google_oauth import GoogleOAuthService

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides.clear()
    Base.metadata.create_all(bind=engine)
    ensure_user_auth_schema(engine)
    OAuthState.__table__.create(bind=engine, checkfirst=True)
    OAuthExchangeCode.__table__.create(bind=engine, checkfirst=True)
    UserExternalIdentity.__table__.create(bind=engine, checkfirst=True)
    yield
    app.dependency_overrides.clear()


def test_oauth_status_endpoint(monkeypatch):
    # Case 1: unconfigured
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    res = client.get("/api/v1/auth/google/status")
    assert res.status_code == 200
    data = res.json()
    assert data["google_configured"] is False
    assert data["client_id_configured"] is False
    assert "redirect_uri" in data

    # Case 2: configured
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")
    res2 = client.get("/api/v1/auth/google/status")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["google_configured"] is True
    assert data2["client_id_configured"] is True


def test_oauth_login_unconfigured_error(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    res = client.get("/api/v1/auth/google/login")
    assert res.status_code == 400
    assert "not configured" in res.json()["detail"].lower()


def test_oauth_login_generates_pkce_and_persists_state(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-id-123.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-secret-456")

    res = client.get("/api/v1/auth/google/login?redirect_url=/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["is_configured"] is True
    assert "accounts.google.com" in data["authorization_url"]
    assert "code_challenge=" in data["authorization_url"]
    assert f"state={data['state']}" in data["authorization_url"]

    # Verify state record in database
    db = SessionLocal()
    try:
        saved_state = db.query(OAuthState).filter(OAuthState.state == data["state"]).first()
        assert saved_state is not None
        assert saved_state.is_consumed is False
        assert len(saved_state.code_verifier) > 30
        assert saved_state.frontend_redirect_url == "/dashboard"
    finally:
        db.close()


def test_oauth_callback_handles_user_cancellation():
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"error": "access_denied", "error_description": "User denied access"},
    )
    assert res.status_code == 400
    assert "text/html" in res.headers["content-type"]
    assert "ADFIP_OAUTH_ERROR" in res.text
    assert "User denied access" in res.text


def test_oauth_callback_invalid_or_missing_state():
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "mock-auth-code", "state": "completely-invalid-state-token"},
    )
    assert res.status_code == 400
    assert "text/html" in res.headers["content-type"]
    assert "ADFIP_OAUTH_ERROR" in res.text
    assert "Invalid or unrecognized OAuth state token." in res.text


def test_oauth_callback_expired_state(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "mock-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-client-secret")

    db = SessionLocal()
    expired_token = f"expired_state_{uuid.uuid4().hex}"
    try:
        state_obj = OAuthState(
            state=expired_token,
            provider="google",
            code_verifier="mock_verifier",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "mock-auth-code", "state": expired_token},
    )
    assert res.status_code == 400
    assert "text/html" in res.headers["content-type"]
    assert "expired" in res.text.lower()


def test_oauth_callback_already_consumed_state(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "mock-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-client-secret")

    db = SessionLocal()
    consumed_token = f"consumed_state_{uuid.uuid4().hex}"
    try:
        state_obj = OAuthState(
            state=consumed_token,
            provider="google",
            code_verifier="mock_verifier",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            is_consumed=True,
            consumed_at=datetime.now(timezone.utc),
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "mock-auth-code", "state": consumed_token},
    )
    assert res.status_code == 400
    assert "text/html" in res.headers["content-type"]
    assert "OAuth state token has already been consumed." in res.text


def test_oauth_full_flow_new_user_and_exchange(monkeypatch):
    """
    Scenario A: New user authenticates via Google.
    - User account created with role INVESTIGATOR.
    - External identity linked.
    - Exchange code generated and single-use verified.
    """
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "mock-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-client-secret")

    db = SessionLocal()
    valid_state = f"valid_state_{uuid.uuid4().hex}"
    test_email = f"oauth_investigator_{uuid.uuid4().hex[:6]}@agency.gov"
    google_sub = f"google_sub_{uuid.uuid4().hex[:12]}"
    try:
        state_obj = OAuthState(
            state=valid_state,
            provider="google",
            code_verifier="verifier_token_secret_12345",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    # Mock external Google HTTP exchanges
    def mock_exchange_tokens(code, code_verifier, redirect_uri, http_client=None):
        assert code == "mock_google_code_123"
        assert code_verifier == "verifier_token_secret_12345"
        return {"access_token": "mock_google_access_token", "id_token": "mock_id_token"}

    def mock_verify_identity(access_token, id_token=None, http_client=None):
        return {
            "sub": google_sub,
            "email": test_email,
            "name": "Detective Sarah Miller",
            "picture": "https://avatar.example.com/sarah.jpg",
        }

    monkeypatch.setattr(GoogleOAuthService, "exchange_code_for_tokens", mock_exchange_tokens)
    monkeypatch.setattr(GoogleOAuthService, "verify_google_identity", mock_verify_identity)

    # Trigger callback
    callback_res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "mock_google_code_123", "state": valid_state},
    )
    assert callback_res.status_code == 200
    assert "text/html" in callback_res.headers["content-type"]
    assert "ADFIP_OAUTH_SUCCESS" in callback_res.text

    # Extract ticket from database
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == test_email).first()
        assert user is not None
        assert user.role == "INVESTIGATOR"  # Least-privilege default
        assert user.name == "Detective Sarah Miller"

        ext = db.query(UserExternalIdentity).filter(
            UserExternalIdentity.user_id == user.id,
            UserExternalIdentity.provider == "google",
            UserExternalIdentity.provider_subject == google_sub,
        ).first()
        assert ext is not None

        exchange_record = db.query(OAuthExchangeCode).filter(
            OAuthExchangeCode.user_id == user.id,
            OAuthExchangeCode.is_consumed == False,
        ).first()
        assert exchange_record is not None
        ticket = exchange_record.code
    finally:
        db.close()

    # Exchange ticket for JWT
    exchange_res = client.post(
        "/api/v1/auth/google/exchange",
        json={"code": ticket},
    )
    assert exchange_res.status_code == 200
    token_data = exchange_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["email"] == test_email
    assert token_data["user"]["role"] == "INVESTIGATOR"

    # Enforce single-use: replay attack attempt MUST fail with 401
    replay_res = client.post(
        "/api/v1/auth/google/exchange",
        json={"code": ticket},
    )
    assert replay_res.status_code == 401
    assert "already been consumed" in replay_res.json()["detail"].lower()


def test_oauth_scenario_c_prevents_silent_account_takeover(monkeypatch):
    """
    Scenario C: An unlinked password account already exists with the Google email.
    Attempting OAuth MUST return HTTP 409 and NOT silently link accounts.
    """
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "mock-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-client-secret")

    # Create password-authenticated user
    target_email = f"agent_bob_{uuid.uuid4().hex[:6]}@agency.gov"
    db = SessionLocal()
    try:
        existing_user = User(
            email=target_email,
            name="Agent Bob",
            organization="Federal Forensics",
            role="INVESTIGATOR",
            is_active=True,
            password_hash=hash_password("LegitPassword123!"),
        )
        db.add(existing_user)
        db.commit()

        valid_state = f"scenario_c_state_{uuid.uuid4().hex}"
        state_obj = OAuthState(
            state=valid_state,
            provider="google",
            code_verifier="verifier_token_secret_takeover",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    def mock_exchange_tokens(code, code_verifier, redirect_uri, http_client=None):
        return {"access_token": "mock_google_access_token"}

    def mock_verify_identity(access_token, id_token=None, http_client=None):
        return {
            "sub": "unlinked_google_sub_attempt",
            "email": target_email,
            "name": "Attacker or unlinked identity",
        }

    monkeypatch.setattr(GoogleOAuthService, "exchange_code_for_tokens", mock_exchange_tokens)
    monkeypatch.setattr(GoogleOAuthService, "verify_google_identity", mock_verify_identity)

    callback_res = client.get(
        "/api/v1/auth/google/callback",
        params={"code": "mock_google_code_takeover", "state": valid_state},
    )
    # Returns 409 conflict HTML
    assert callback_res.status_code == 409
    assert "text/html" in callback_res.headers["content-type"]
    assert "already exists" in callback_res.text
    assert "ADFIP_OAUTH_ERROR" in callback_res.text

    # Verify no external identity was silently linked
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == target_email).first()
        links = db.query(UserExternalIdentity).filter(UserExternalIdentity.user_id == user.id).all()
        assert len(links) == 0
    finally:
        db.close()


def test_unlink_google_account_lockout_protection():
    """
    A user with NO password cannot unlink their Google account (would cause permanent lockout).
    """
    db = SessionLocal()
    test_email = f"oauth_only_{uuid.uuid4().hex[:6]}@agency.gov"
    try:
        user = User(
            email=test_email,
            name="OAuth Only User",
            organization="Forensics",
            role="INVESTIGATOR",
            is_active=True,
            password_hash=None,  # No password set!
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        ext = UserExternalIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=f"sub_{uuid.uuid4().hex}",
            provider_email=test_email,
        )
        db.add(ext)
        db.commit()

        token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    finally:
        db.close()

    res = client.delete(
        "/api/v1/auth/google/unlink",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400, f"Got {res.status_code}: {res.text}"
    assert "locked out" in res.json()["detail"].lower()
