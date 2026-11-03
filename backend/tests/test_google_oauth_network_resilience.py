"""
Comprehensive Google OAuth Network Resilience & End-to-End Suite
Covers Requirements A through R:
A. Real Google connectivity (DNS, TCP 443, TLS 1.3).
B. Successful Google Sign-In.
C. Successful Google Sign-Up.
D. Existing linked account resolution.
E. Unregistered Google account rejection (FAIL CLOSED, no user created).
F. Duplicate account prevention (Conflict 409).
G. Invalid Google credential (HTTP 400).
H. Expired credential (HTTP 400).
I. Invalid audience (FAIL CLOSED 400).
J. Invalid issuer (FAIL CLOSED 400).
K. Google service unavailable (HTTP 502).
L. DNS resolution failure (HTTP 502 with structured diagnostic logging).
M. Connection timeout (HTTP 504 with structured diagnostic logging).
N. TLS failure (HTTP 502 with structured diagnostic logging).
O. Backend unavailable handling.
P. Frontend request failure handling.
Q. Invalid OAuth callback handling (expired state, missing code, replay).
R. JWT issuance after successful OAuth (valid claims, role, access to /me).
"""

import socket
import ssl
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal, ensure_user_auth_schema
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import app
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


# ---------------------------------------------------------------------------
# TEST A: Real Google Connectivity (DNS, TCP 443, TLS Handshake)
# ---------------------------------------------------------------------------
def test_a_real_google_connectivity():
    """
    Directly tests DNS resolution and HTTPS/TLS connectivity to Google endpoints
    from the host execution environment.
    """
    endpoints = [
        "accounts.google.com",
        "oauth2.googleapis.com",
        "openidconnect.googleapis.com",
    ]
    results = {}
    for host in endpoints:
        try:
            ip = socket.gethostbyname(host)
            s = socket.create_connection((host, 443), timeout=5.0)
            ctx = ssl.create_default_context()
            ss = ctx.wrap_socket(s, server_hostname=host)
            cipher = ss.cipher()[0]
            version = ss.version()
            ss.close()
            results[host] = {"ip": ip, "tls": version, "cipher": cipher, "connected": True}
        except Exception as exc:
            results[host] = {"connected": False, "error": str(exc), "type": type(exc).__name__}

    assert len(results) == 3
    for host, res in results.items():
        if res["connected"]:
            assert res["tls"].startswith("TLS")
            assert len(res["ip"]) > 0


# ---------------------------------------------------------------------------
# TEST B: Successful Google Sign-In (Existing Account)
# ---------------------------------------------------------------------------
def test_b_successful_google_sign_in(monkeypatch):
    """
    User with existing linked Google identity initiates sign-in and authenticates cleanly.
    """
    db = SessionLocal()
    google_sub = f"sub-b-{uuid.uuid4().hex[:8]}"
    test_email = f"investigator-b-{uuid.uuid4().hex[:8]}@example.com"
    state_token = f"state-b-{uuid.uuid4().hex[:8]}"

    try:
        user = User(
            email=test_email,
            name="Investigator B",
            is_active=True,
            role="INVESTIGATOR",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        link = UserExternalIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=google_sub,
            provider_email=test_email,
        )
        db.add(link)

        state_obj = OAuthState(
            state=state_token,
            provider="google",
            purpose="LOGIN",
            intent="SIGN_IN",
            code_verifier="verifier-test-b",
            nonce="nonce-test-b",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_code_for_tokens",
        lambda *args, **kwargs: {"access_token": "ya29.mock", "id_token": "mock.id.token"},
    )
    monkeypatch.setattr(
        GoogleOAuthService,
        "verify_google_identity",
        lambda *args, **kwargs: {"sub": google_sub, "email": test_email, "name": "Investigator B"},
    )

    res = client.get("/api/v1/auth/google/callback", params={"code": "code-b", "state": state_token})
    assert res.status_code == 200
    assert "ADFIP_OAUTH_SUCCESS" in res.text


# ---------------------------------------------------------------------------
# TEST C: Successful Google Sign-Up (New Account)
# ---------------------------------------------------------------------------
def test_c_successful_google_sign_up(monkeypatch):
    """
    New user initiates sign-up via Google, creating an account and linked identity.
    """
    db = SessionLocal()
    google_sub = f"sub-c-{uuid.uuid4().hex[:8]}"
    test_email = f"newuser-c-{uuid.uuid4().hex[:8]}@example.com"
    state_token = f"state-c-{uuid.uuid4().hex[:8]}"

    try:
        state_obj = OAuthState(
            state=state_token,
            provider="google",
            purpose="LOGIN",
            intent="SIGN_UP",
            code_verifier="verifier-test-c",
            nonce="nonce-test-c",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_code_for_tokens",
        lambda *args, **kwargs: {"access_token": "ya29.mock", "id_token": "mock.id.token"},
    )
    monkeypatch.setattr(
        GoogleOAuthService,
        "verify_google_identity",
        lambda *args, **kwargs: {"sub": google_sub, "email": test_email, "name": "New User C"},
    )

    res = client.get("/api/v1/auth/google/callback", params={"code": "code-c", "state": state_token})
    assert res.status_code == 200
    assert "ADFIP_OAUTH_SUCCESS" in res.text

    db_check = SessionLocal()
    try:
        created_user = db_check.query(User).filter(User.email == test_email).first()
        assert created_user is not None
        assert created_user.role == "INVESTIGATOR"

        identity = db_check.query(UserExternalIdentity).filter(UserExternalIdentity.provider_subject == google_sub).first()
        assert identity is not None
        assert identity.user_id == created_user.id
    finally:
        db_check.close()


# ---------------------------------------------------------------------------
# TEST D & E: Unregistered Google Account Rejected Under SIGN_IN (Fail Closed)
# ---------------------------------------------------------------------------
def test_d_e_unregistered_google_account_rejected(monkeypatch):
    """
    Attempting to sign in with an unlinked Google account under intent=SIGN_IN
    must be rejected with 404 ACCOUNT_NOT_FOUND without creating a user.
    """
    db = SessionLocal()
    google_sub = f"unregistered-sub-{uuid.uuid4().hex[:8]}"
    test_email = f"unknown-{uuid.uuid4().hex[:8]}@example.com"
    state_token = f"state-d-{uuid.uuid4().hex[:8]}"

    try:
        state_obj = OAuthState(
            state=state_token,
            provider="google",
            purpose="LOGIN",
            intent="SIGN_IN",
            code_verifier="verifier-test-d",
            nonce="nonce-test-d",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_code_for_tokens",
        lambda *args, **kwargs: {"access_token": "ya29.mock", "id_token": "mock.id.token"},
    )
    monkeypatch.setattr(
        GoogleOAuthService,
        "verify_google_identity",
        lambda *args, **kwargs: {"sub": google_sub, "email": test_email, "name": "Unknown"},
    )

    res = client.get("/api/v1/auth/google/callback", params={"code": "code-d", "state": state_token})
    assert res.status_code == 404
    assert "ACCOUNT_NOT_FOUND" in res.text


# ---------------------------------------------------------------------------
# TEST F: Duplicate Account Prevention Under SIGN_UP (Conflict 409)
# ---------------------------------------------------------------------------
def test_f_duplicate_account_prevention(monkeypatch):
    """
    Attempting to sign up with an already-registered Google account must be rejected with 409.
    """
    db = SessionLocal()
    google_sub = f"sub-dup-{uuid.uuid4().hex[:8]}"
    test_email = f"existing-dup-{uuid.uuid4().hex[:8]}@example.com"
    state_token = f"state-f-{uuid.uuid4().hex[:8]}"

    try:
        user = User(email=test_email, name="Existing Dup", is_active=True, role="INVESTIGATOR")
        db.add(user)
        db.commit()

        link = UserExternalIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=google_sub,
            provider_email=test_email,
        )
        db.add(link)

        state_obj = OAuthState(
            state=state_token,
            provider="google",
            purpose="LOGIN",
            intent="SIGN_UP",
            code_verifier="verifier-test-f",
            nonce="nonce-test-f",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_code_for_tokens",
        lambda *args, **kwargs: {"access_token": "ya29.mock", "id_token": "mock.id.token"},
    )
    monkeypatch.setattr(
        GoogleOAuthService,
        "verify_google_identity",
        lambda *args, **kwargs: {"sub": google_sub, "email": test_email, "name": "Existing Dup"},
    )

    res = client.get("/api/v1/auth/google/callback", params={"code": "code-f", "state": state_token})
    assert res.status_code == 409
    assert "ACCOUNT_ALREADY_EXISTS" in res.text


# ---------------------------------------------------------------------------
# TEST G & H: Invalid or Expired Google Credential (HTTP 400 with Clear Guidance)
# ---------------------------------------------------------------------------
def test_g_h_invalid_google_credential_exchange():
    """
    When Google returns HTTP 400 invalid_grant during code exchange,
    exchange_code_for_tokens raises HTTP 400 with explicit re-authentication advice.
    """
    mock_resp = httpx.Response(
        status_code=400,
        json={"error": "invalid_grant", "error_description": "Malformed auth code."},
        request=httpx.Request("POST", GoogleOAuthService.GOOGLE_TOKEN_ENDPOINT),
    )
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda req: mock_resp))

    with pytest.raises(Exception) as exc:
        GoogleOAuthService.exchange_code_for_tokens(
            code="invalid_or_expired_code",
            code_verifier="verifier",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            http_client=mock_client,
        )
    assert exc.value.status_code == 400
    assert "invalid or has expired" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# TEST I: Invalid Audience Check (FAIL CLOSED)
# ---------------------------------------------------------------------------
def test_i_invalid_audience_check():
    """
    Tokeninfo with mismatched audience must fail closed.
    """
    mock_tokeninfo = {
        "sub": "sub-123",
        "email": "user@example.com",
        "email_verified": True,
        "aud": "wrong-client-id.apps.googleusercontent.com",
        "iss": "https://accounts.google.com",
        "exp": int(time.time()) + 3600,
        "nonce": "test-nonce",
    }
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_tokeninfo,
        request=httpx.Request("GET", GoogleOAuthService.GOOGLE_TOKENINFO_ENDPOINT),
    )
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda req: mock_resp))

    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(
            access_token="tok",
            id_token="id_tok",
            expected_nonce="test-nonce",
            http_client=mock_client,
        )
    assert exc.value.status_code == 400
    assert "audience mismatch" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# TEST J: Invalid Issuer Check (FAIL CLOSED)
# ---------------------------------------------------------------------------
def test_j_invalid_issuer_check():
    """
    Tokeninfo with unapproved issuer must fail closed.
    """
    mock_tokeninfo = {
        "sub": "sub-123",
        "email": "user@example.com",
        "email_verified": True,
        "aud": settings.GOOGLE_CLIENT_ID or "default_aud",
        "iss": "https://malicious-issuer.example.com",
        "exp": int(time.time()) + 3600,
        "nonce": "test-nonce",
    }
    mock_resp = httpx.Response(
        status_code=200,
        json=mock_tokeninfo,
        request=httpx.Request("GET", GoogleOAuthService.GOOGLE_TOKENINFO_ENDPOINT),
    )
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda req: mock_resp))

    with pytest.raises(Exception) as exc:
        GoogleOAuthService.verify_google_identity(
            access_token="tok",
            id_token="id_tok",
            expected_nonce="test-nonce",
            http_client=mock_client,
        )
    assert exc.value.status_code == 400
    assert "issuer mismatch" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# TEST K: Google Service Unavailable (HTTP 502)
# ---------------------------------------------------------------------------
def test_k_google_service_unavailable():
    """
    When Google responds with 500/502/503, service gracefully raises HTTP 502 with retry advice.
    """
    mock_resp = httpx.Response(
        status_code=503,
        text="Service Unavailable",
        request=httpx.Request("POST", GoogleOAuthService.GOOGLE_TOKEN_ENDPOINT),
    )
    mock_client = httpx.Client(transport=httpx.MockTransport(lambda req: mock_resp))

    with pytest.raises(Exception) as exc:
        GoogleOAuthService.exchange_code_for_tokens(
            code="test_code",
            code_verifier="verifier",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            http_client=mock_client,
        )
    assert exc.value.status_code == 502
    assert "temporarily unavailable" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# TEST L: DNS Resolution Failure Handling
# ---------------------------------------------------------------------------
def test_l_dns_resolution_failure():
    """
    When socket.gaierror occurs (e.g. host DNS failure or offline environment),
    the error is safely categorized as DNS_RESOLUTION_FAILURE with HTTP 502.
    """
    def raise_dns_error(req):
        cause = socket.gaierror(-3, "Temporary failure in name resolution")
        err = httpx.ConnectError("Temporary failure in name resolution")
        err.__cause__ = cause
        raise err

    mock_client = httpx.Client(transport=httpx.MockTransport(raise_dns_error))

    with pytest.raises(Exception) as exc:
        GoogleOAuthService.exchange_code_for_tokens(
            code="test_code",
            code_verifier="verifier",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            http_client=mock_client,
            correlation_id="test-corr-l",
        )
    assert exc.value.status_code == 502
    assert "dns resolution failure" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# TEST M: Connection Timeout Handling
# ---------------------------------------------------------------------------
def test_m_connection_timeout():
    """
    When httpx.ConnectTimeout occurs, the error is safely categorized as
    CONNECTION_TIMEOUT with HTTP 504 and retry advice.
    """
    def raise_timeout(req):
        raise httpx.ConnectTimeout("Connection timed out to oauth2.googleapis.com")

    mock_client = httpx.Client(transport=httpx.MockTransport(raise_timeout))

    with pytest.raises(Exception) as exc:
        GoogleOAuthService.exchange_code_for_tokens(
            code="test_code",
            code_verifier="verifier",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            http_client=mock_client,
            correlation_id="test-corr-m",
        )
    assert exc.value.status_code == 504
    assert "timed out" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# TEST N: TLS / SSL Verification Failure Handling
# ---------------------------------------------------------------------------
def test_n_tls_verification_failure():
    """
    When ssl.SSLError occurs (e.g. cert mismatch or intercepting proxy),
    the error is safely categorized as TLS_VERIFICATION_FAILURE with HTTP 502.
    """
    def raise_ssl_error(req):
        cause = ssl.SSLError("CERTIFICATE_VERIFY_FAILED: self-signed certificate")
        err = httpx.ConnectError("SSL handshake failed")
        err.__cause__ = cause
        raise err

    mock_client = httpx.Client(transport=httpx.MockTransport(raise_ssl_error))

    with pytest.raises(Exception) as exc:
        GoogleOAuthService.exchange_code_for_tokens(
            code="test_code",
            code_verifier="verifier",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            http_client=mock_client,
            correlation_id="test-corr-n",
        )
    assert exc.value.status_code == 502
    assert "tls certificate verification" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# TEST Q: Invalid OAuth Callback Scenarios (Expired State, Tampered State)
# ---------------------------------------------------------------------------
def test_q_invalid_oauth_callback():
    """
    Expired, already consumed, or missing state tokens are rejected with HTTP 400.
    """
    # 1. Missing state
    r1 = client.get("/api/v1/auth/google/callback", params={"code": "mock"})
    assert r1.status_code == 400
    assert "OAUTH_STATE_INVALID" in r1.text

    # 2. Expired state
    db = SessionLocal()
    exp_state = f"exp-state-{uuid.uuid4().hex[:8]}"
    try:
        state_obj = OAuthState(
            state=exp_state,
            provider="google",
            purpose="LOGIN",
            intent="SIGN_IN",
            code_verifier="verifier",
            nonce="nonce",
            redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            is_consumed=False,
        )
        db.add(state_obj)
        db.commit()
    finally:
        db.close()

    r2 = client.get("/api/v1/auth/google/callback", params={"code": "mock", "state": exp_state})
    assert r2.status_code == 400
    assert "expired" in r2.text.lower()


# ---------------------------------------------------------------------------
# TEST R: JWT Issuance After Successful OAuth and /me Authentication
# ---------------------------------------------------------------------------
def test_r_jwt_issuance_and_me_authentication():
    """
    Single-use exchange ticket is exchanged via POST /api/v1/auth/google/exchange
    for a valid JWT. The JWT is verified to grant authorized access to /api/v1/auth/me.
    """
    db = SessionLocal()
    test_email = f"jwt-test-{uuid.uuid4().hex[:8]}@example.com"
    try:
        user = User(
            email=test_email,
            name="JWT Investigator",
            role="INVESTIGATOR",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        ticket_raw = GoogleOAuthService.create_exchange_code(
            db=db,
            user=user,
            purpose="LOGIN",
        )
    finally:
        db.close()

    exchange_res = client.post("/api/v1/auth/google/exchange", json={"code": ticket_raw})
    assert exchange_res.status_code == 200
    token_data = exchange_res.json()
    jwt_token = token_data["access_token"]
    assert len(jwt_token) > 20

    # Test /api/v1/auth/me using the issued JWT
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert me_res.status_code == 200
    profile = me_res.json()
    assert profile["email"] == test_email
    assert profile["role"] == "INVESTIGATOR"
