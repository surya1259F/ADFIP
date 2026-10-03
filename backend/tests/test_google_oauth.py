import hashlib
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

    # Extract ticket from callback response (raw ticket returned once to client)
    import re
    match = re.search(r'const ticket = "([^"]+)";', callback_res.text)
    assert match is not None
    ticket = match.group(1)

    # Verify user and hashed ticket in database
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
        # Ensure raw ticket is not stored in plaintext; only hash is stored
        assert exchange_record.code_hash is not None
        assert hashlib.sha256(ticket.encode("utf-8")).hexdigest() == exchange_record.code_hash
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


def test_redirect_url_security_allowlist(monkeypatch):
    """
    Verify strict allowlist validation for redirect_url:
    - /dashboard and /auth/callback allowed
    - Protocol schemes, protocol-relative URLs, external domains rejected with 400
    """
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")

    # Accepted routes
    res1 = client.get("/api/v1/auth/google/login?redirect_url=/dashboard")
    assert res1.status_code == 200

    res2 = client.get("/api/v1/auth/google/login?redirect_url=/auth/callback")
    assert res2.status_code == 200

    # Rejected targets
    invalid_targets = [
        "https://evil.example",
        "http://evil.example",
        "//evil.example",
        "javascript:alert(1)",
        "data:text/html,evil",
        "/unauthorized_path",
        "https://evil.example/dashboard",
    ]
    for target in invalid_targets:
        res = client.get(f"/api/v1/auth/google/login?redirect_url={target}")
        assert res.status_code == 400, f"Expected 400 for redirect target '{target}', got {res.status_code}"
        assert "redirect url" in res.json()["detail"].lower()


def test_oauth_state_invalid_or_missing_fails():
    """
    Missing or malformed OAuth state token returns 400 bad request.
    """
    # Empty state parameter
    res1 = client.get("/api/v1/auth/google/callback", params={"code": "mock-code", "state": ""})
    assert res1.status_code == 400
    assert "text/html" in res1.headers["content-type"]
    assert "ADFIP_OAUTH_ERROR" in res1.text

    # Missing state parameter
    res2 = client.get("/api/v1/auth/google/callback", params={"code": "mock-code"})
    assert res2.status_code == 400
    assert "ADFIP_OAUTH_ERROR" in res2.text


def test_oauth_state_atomic_double_consumption_blocked():
    """
    Atomic check: consuming the same state token twice fails immediately on the 2nd attempt.
    """
    db = SessionLocal()
    st_val = f"atomic_test_{uuid.uuid4().hex}"
    try:
        obj = OAuthState(
            state=st_val,
            provider="google",
            code_verifier="test_verifier_atomic",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_consumed=False,
        )
        db.add(obj)
        db.commit()

        # First consumption must succeed
        consumed = GoogleOAuthService.verify_and_consume_state(db=db, state=st_val)
        assert consumed is not None
        assert consumed.is_consumed is True

        # Second consumption MUST fail with HTTPException(400)
        with pytest.raises(Exception) as exc_info:
            GoogleOAuthService.verify_and_consume_state(db=db, state=st_val)
        assert "already been consumed" in str(exc_info.value.detail).lower()
    finally:
        db.close()


def test_oidc_nonce_validation_success_and_failures(monkeypatch):
    """
    Verify OIDC nonce validation:
    - Matching nonce succeeds
    - Mismatched nonce fails closed
    - Missing nonce fails closed
    """
    import httpx
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

    expected_nonce = "crypto_nonce_abc123"
    target_email = "investigator_nonce@agency.gov"
    target_sub = "google_sub_nonce_999"

    def make_mock_client(tokeninfo_nonce):
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "userinfo" in url_str:
                return httpx.Response(200, json={
                    "sub": target_sub,
                    "email": target_email,
                    "email_verified": True,
                    "name": "Nonce Investigator",
                })
            elif "tokeninfo" in url_str:
                token_data = {
                    "aud": settings.GOOGLE_CLIENT_ID,
                    "iss": "https://accounts.google.com",
                    "sub": target_sub,
                    "email": target_email,
                    "email_verified": True,
                    "exp": int(time.time()) + 3600,
                }
                if tokeninfo_nonce is not None:
                    token_data["nonce"] = tokeninfo_nonce
                return httpx.Response(200, json=token_data)
            return httpx.Response(404)
        return httpx.Client(transport=httpx.MockTransport(handler))

    # Case A: Correct nonce succeeds
    client_ok = make_mock_client(tokeninfo_nonce=expected_nonce)
    identity = GoogleOAuthService.verify_google_identity(
        access_token="mock_access",
        id_token="mock_id_token",
        expected_nonce=expected_nonce,
        http_client=client_ok,
    )
    assert identity["sub"] == target_sub
    assert identity["email"] == target_email

    # Case B: Incorrect nonce fails
    client_wrong = make_mock_client(tokeninfo_nonce="attacker_injected_nonce")
    with pytest.raises(Exception) as exc_wrong:
        GoogleOAuthService.verify_google_identity(
            access_token="mock_access",
            id_token="mock_id_token",
            expected_nonce=expected_nonce,
            http_client=client_wrong,
        )
    assert "nonce mismatch" in str(exc_wrong.value.detail).lower()

    # Case C: Missing nonce fails when expected_nonce is required
    client_missing = make_mock_client(tokeninfo_nonce=None)
    with pytest.raises(Exception) as exc_missing:
        GoogleOAuthService.verify_google_identity(
            access_token="mock_access",
            id_token="mock_id_token",
            expected_nonce=expected_nonce,
            http_client=client_missing,
        )
    assert "nonce mismatch" in str(exc_missing.value.detail).lower()


def test_id_token_claims_fail_closed_checks(monkeypatch):
    """
    Verify fail-closed enforcement for all ID token claims:
    - Non-200 tokeninfo response -> fails closed
    - Wrong issuer -> fails closed
    - Wrong audience -> fails closed
    - Expired token -> fails closed
    - Sub mismatch between userinfo and tokeninfo -> fails closed
    - Email unverified -> fails closed
    """
    import httpx
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")

    target_email = "investigator_claims@agency.gov"
    target_sub = "google_sub_claims_888"

    def make_mock_client(tokeninfo_status=200, tokeninfo_overrides=None, userinfo_overrides=None):
        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "userinfo" in url_str:
                data = {
                    "sub": target_sub,
                    "email": target_email,
                    "email_verified": True,
                    "name": "Claims Investigator",
                }
                if userinfo_overrides:
                    data.update(userinfo_overrides)
                return httpx.Response(200, json=data)
            elif "tokeninfo" in url_str:
                if tokeninfo_status != 200:
                    return httpx.Response(tokeninfo_status, json={"error": "invalid_token"})
                data = {
                    "aud": settings.GOOGLE_CLIENT_ID,
                    "iss": "https://accounts.google.com",
                    "sub": target_sub,
                    "email": target_email,
                    "email_verified": True,
                    "exp": int(time.time()) + 3600,
                }
                if tokeninfo_overrides:
                    data.update(tokeninfo_overrides)
                return httpx.Response(200, json=data)
            return httpx.Response(404)
        return httpx.Client(transport=httpx.MockTransport(handler))

    # 1. Tokeninfo HTTP failure (e.g. 400 or 500) fails closed
    c_fail = make_mock_client(tokeninfo_status=400)
    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(access_token="tok", id_token="id", http_client=c_fail)
    assert "token validation failed" in str(exc.value.detail).lower()

    # 2. Wrong issuer
    c_iss = make_mock_client(tokeninfo_overrides={"iss": "https://attacker.example.com"})
    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(access_token="tok", id_token="id", http_client=c_iss)
    assert "issuer mismatch" in str(exc.value.detail).lower()

    # 3. Wrong audience
    c_aud = make_mock_client(tokeninfo_overrides={"aud": "unauthorized-client-id"})
    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(access_token="tok", id_token="id", http_client=c_aud)
    assert "audience mismatch" in str(exc.value.detail).lower()

    # 4. Expired token
    c_exp = make_mock_client(tokeninfo_overrides={"exp": int(time.time()) - 300})
    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(access_token="tok", id_token="id", http_client=c_exp)
    assert "expired" in str(exc.value.detail).lower()

    # 5. Missing or mismatched subject
    c_sub = make_mock_client(tokeninfo_overrides={"sub": "different_subject_id"})
    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(access_token="tok", id_token="id", http_client=c_sub)
    assert "subject mismatch" in str(exc.value.detail).lower()

    # 6. Unverified email (in tokeninfo)
    c_unverified = make_mock_client(tokeninfo_overrides={"email_verified": False})
    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(access_token="tok", id_token="id", http_client=c_unverified)
    assert "not verified" in str(exc.value.detail).lower()


def test_exchange_ticket_lifecycle_and_purpose_enforcement():
    """
    Verify exchange ticket security:
    - Single-use consumption
    - Replay protection (401)
    - Expired ticket rejection (401)
    - Invalid ticket rejection (401)
    - Purpose mismatch: LINK ticket rejected from LOGIN endpoint (403)
    """
    db = SessionLocal()
    test_email = f"ticket_investigator_{uuid.uuid4().hex[:6]}@agency.gov"
    try:
        user = User(
            email=test_email,
            name="Ticket User",
            organization="Forensics Unit",
            role="INVESTIGATOR",
            is_active=True,
        )
        db.add(user)
        db.commit()

        # 1. Valid LOGIN ticket exchange
        raw_ticket = GoogleOAuthService.create_exchange_code(db=db, user=user, purpose="LOGIN")
        res1 = client.post("/api/v1/auth/google/exchange", json={"code": raw_ticket})
        assert res1.status_code == 200
        assert "access_token" in res1.json()

        # 2. Replay of consumed ticket fails with 401
        res_replay = client.post("/api/v1/auth/google/exchange", json={"code": raw_ticket})
        assert res_replay.status_code == 401
        assert "already been consumed" in res_replay.json()["detail"].lower()

        # 3. Invalid ticket fails with 401
        res_invalid = client.post("/api/v1/auth/google/exchange", json={"code": "completely-bogus-ticket"})
        assert res_invalid.status_code == 401

        # 4. Expired ticket fails with 401
        raw_exp_ticket = GoogleOAuthService.create_exchange_code(db=db, user=user, purpose="LOGIN")
        # Backdate expiration
        h = hashlib.sha256(raw_exp_ticket.encode()).hexdigest()
        db.query(OAuthExchangeCode).filter(OAuthExchangeCode.code_hash == h).update(
            {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=10)}
        )
        db.commit()

        res_exp = client.post("/api/v1/auth/google/exchange", json={"code": raw_exp_ticket})
        assert res_exp.status_code == 401
        assert "expired" in res_exp.json()["detail"].lower()

        # 5. Purpose mismatch: LINK ticket cannot be used for LOGIN exchange
        raw_link_ticket = GoogleOAuthService.create_exchange_code(
            db=db,
            purpose="LINK",
            target_user_id=user.id,
            google_sub="google_sub_purpose_test",
            google_email=test_email,
        )
        res_purpose = client.post("/api/v1/auth/google/exchange", json={"code": raw_link_ticket})
        assert res_purpose.status_code == 403
        assert "not issued for login" in res_purpose.json()["detail"].lower()
    finally:
        db.close()


def test_account_linking_complete_security_flow(monkeypatch):
    """
    Comprehensive account linking security tests:
    - User A links with valid password -> 200 OK, role intact
    - Cross-account abuse: User B tries to use User A's ticket -> 403 Forbidden
    - User attempts to use LOGIN ticket for linking -> 403 Forbidden
    - Duplicate Google identity -> 409 Conflict
    - Wrong password -> 401 Unauthorized
    """
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "test-client-secret")

    db = SessionLocal()
    email_a = f"investigator_a_{uuid.uuid4().hex[:6]}@agency.gov"
    email_b = f"investigator_b_{uuid.uuid4().hex[:6]}@agency.gov"
    pass_a = "SecretPassA123!"
    pass_b = "SecretPassB456!"

    try:
        user_a = User(
            email=email_a,
            name="Investigator A",
            organization="Forensics",
            role="INVESTIGATOR",
            is_active=True,
            password_hash=hash_password(pass_a),
        )
        user_b = User(
            email=email_b,
            name="Investigator B",
            organization="Forensics",
            role="INVESTIGATOR",
            is_active=True,
            password_hash=hash_password(pass_b),
        )
        db.add_all([user_a, user_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)

        token_a = create_access_token(user_id=user_a.id, email=user_a.email, role=user_a.role)
        token_b = create_access_token(user_id=user_b.id, email=user_b.email, role=user_b.role)

        # 1. User A initiates LINK flow
        google_sub_a = f"sub_google_{uuid.uuid4().hex[:8]}"
        ticket_for_a = GoogleOAuthService.create_exchange_code(
            db=db,
            purpose="LINK",
            target_user_id=user_a.id,
            google_sub=google_sub_a,
            google_email=email_a,
        )

        # 2. Cross-account abuse: User B tries to link User A's ticket
        cross_res = client.post(
            "/api/v1/auth/google/link",
            json={"exchange_code": ticket_for_a, "password": pass_b},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert cross_res.status_code == 403
        assert "cross-account" in cross_res.json()["detail"].lower()

        # 3. Wrong password for User A
        wrong_pw_res = client.post(
            "/api/v1/auth/google/link",
            json={"exchange_code": ticket_for_a, "password": "WrongPassword999!"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert wrong_pw_res.status_code == 401
        assert "incorrect account password" in wrong_pw_res.json()["detail"].lower()

        # 4. Valid linking by User A with correct password
        ok_res = client.post(
            "/api/v1/auth/google/link",
            json={"exchange_code": ticket_for_a, "password": pass_a},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert ok_res.status_code == 200
        data = ok_res.json()
        assert data["provider"] == "google"
        assert data["provider_subject"] == google_sub_a

        # Verify user role remains least-privilege INVESTIGATOR
        db.refresh(user_a)
        assert user_a.role == "INVESTIGATOR"

        # 5. Duplicate Google identity: User B tries to link google_sub_a
        ticket_for_b = GoogleOAuthService.create_exchange_code(
            db=db,
            purpose="LINK",
            target_user_id=user_b.id,
            google_sub=google_sub_a,
            google_email=email_a,
        )
        dup_res = client.post(
            "/api/v1/auth/google/link",
            json={"exchange_code": ticket_for_b, "password": pass_b},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert dup_res.status_code == 409
        assert "already linked" in dup_res.json()["detail"].lower()

        # 6. Purpose mismatch: Trying to link using a LOGIN ticket
        login_ticket = GoogleOAuthService.create_exchange_code(
            db=db,
            user=user_b,
            purpose="LOGIN",
        )
        purpose_res = client.post(
            "/api/v1/auth/google/link",
            json={"exchange_code": login_ticket, "password": pass_b},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert purpose_res.status_code == 403
        assert "invalid ticket purpose" in purpose_res.json()["detail"].lower()
    finally:
        db.close()


def test_callback_xss_protection_prevents_script_breakout():
    """
    Verify callback error HTML neutralizes injection payloads:
    Ensures </script> tags cannot break out of inline scripts.
    """
    xss_payload = '</script><script>alert("xss")</script><img src=x onerror=alert(1)>'
    res = client.get(
        "/api/v1/auth/google/callback",
        params={"error": "access_denied", "error_description": xss_payload},
    )
    assert res.status_code == 400
    assert "text/html" in res.headers["content-type"]

    # Security check 1: Raw </script> MUST NOT appear within script block
    # It must be Unicode-escaped as \u003c/script\u003e
    assert "</script><script>" not in res.text

    # Security check 2: HTML body text is properly escaped
    assert "&lt;/script&gt;" in res.text or "\\u003c/script\\u003e" in res.text

    # Security check 3: Security headers present
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert "no-store" in res.headers.get("cache-control", "").lower()

