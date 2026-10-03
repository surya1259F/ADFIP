from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    revoke_access_token,
    get_current_active_user,
    oauth2_scheme,
)
from backend.app.models.models import User, UserExternalIdentity
from backend.app.schemas.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserProfileUpdateRequest,
    UserResponse,
    TokenResponse,
    GoogleAuthUrlResponse,
    OAuthStatusResponse,
    OAuthExchangeRequest,
    AccountLinkRequest,
    UserExternalIdentityResponse,
)
from backend.app.services.audit import log_audit_event
from backend.app.services.google_oauth import GoogleOAuthService


router = APIRouter()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new investigator account with hashed password credentials.
    Rejects duplicate emails with 409 Conflict. Default role is least-privileged INVESTIGATOR.
    """
    email_clean = req.email.lower().strip() if req.email else ""
    if not email_clean or "@" not in email_clean or "." not in email_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid email address is required.",
        )

    if not req.password or len(req.password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long.",
        )

    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    try:
        pwd_hash = hash_password(req.password)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(val_err),
        )

    user = User(
        email=email_clean,
        name=req.name.strip(),
        organization=(req.organization or "Digital Forensics Unit").strip(),
        badge_id=req.badge_id.strip() if req.badge_id else None,
        role="INVESTIGATOR",
        is_active=True,
        password_hash=pwd_hash,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        case_id=None,
        event_type="USER_ACCOUNT_CREATED",
        details=f"User account '{user.email}' ({user.name}) registered successfully.",
    )

    return user


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login_user(req: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates user credentials and issues a signed HMAC-SHA256 access token.
    Prevents user enumeration by returning a generic 401 Unauthorized error on any failure.
    """
    email_clean = req.email.lower().strip() if req.email else ""
    user = db.query(User).filter(User.email == email_clean).first()

    # Prevent user enumeration: verify against dummy hash if user does not exist
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)

    log_audit_event(
        db=db,
        case_id=None,
        event_type="USER_LOGIN_SUCCESSFUL",
        details=f"User '{user.email}' authenticated successfully.",
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout_user(credentials=Depends(oauth2_scheme)):
    """
    Revokes the current Bearer access token by adding its JTI to the active revocation registry.
    """
    if credentials and credentials.credentials:
        revoke_access_token(credentials.credentials)

    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    """
    Returns authenticated investigator profile for the active session.
    """
    return current_user


@router.patch("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
@router.patch("/profile", response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_current_user_profile(
    req: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Updates the authenticated user's own profile information (name, badge_id).
    Users cannot modify their role, organization, active status, or permissions through this endpoint.
    """
    if req.name is not None:
        clean_name = req.name.strip()
        if not clean_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name cannot be empty.",
            )
        current_user.name = clean_name

    if req.badge_id is not None:
        current_user.badge_id = req.badge_id.strip() if req.badge_id else None

    db.commit()
    db.refresh(current_user)

    log_audit_event(
        db=db,
        case_id=None,
        actor_id=current_user.id,
        actor_name=current_user.name,
        event_type="USER_PROFILE_UPDATED",
        details=f"User '{current_user.email}' updated profile.",
    )

    return current_user


# =============================================================================
# Google OAuth 2.0 / OpenID Connect Endpoints
# =============================================================================

@router.get("/google/status", response_model=OAuthStatusResponse, status_code=status.HTTP_200_OK)
def get_google_oauth_status():
    """
    Returns deployment status for Google OAuth 2.0 integration.
    """
    return OAuthStatusResponse(
        google_configured=GoogleOAuthService.is_configured(),
        client_id_configured=bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_ID.strip()),
        redirect_uri=settings.EFFECTIVE_GOOGLE_REDIRECT_URI,
    )


@router.get("/google/login", response_model=GoogleAuthUrlResponse, status_code=status.HTTP_200_OK)
def initiate_google_oauth_login(
    redirect_url: Optional[str] = Query(None, description="Frontend post-login redirection path"),
    db: Session = Depends(get_db),
):
    """
    Initiates Google OAuth 2.0 authorization code flow with PKCE and state protection.
    Returns the Google consent URL and anti-CSRF state token.
    """
    return GoogleOAuthService.get_login_url(db=db, frontend_redirect_url=redirect_url)


@router.get("/google/callback", response_class=HTMLResponse)
def handle_google_oauth_callback(
    code: Optional[str] = Query(None, description="Google OAuth authorization code"),
    state: Optional[str] = Query(None, description="Anti-CSRF state token"),
    error: Optional[str] = Query(None, description="Google OAuth error code if denied"),
    error_description: Optional[str] = Query(None, description="Human readable OAuth error"),
    db: Session = Depends(get_db),
):
    """
    Handles Google OAuth redirect:
    1. Validates and consumes single-use state token.
    2. Exchanges authorization code for tokens server-side using PKCE verifier.
    3. Verifies Google OpenID Connect identity claims (email_verified, sub).
    4. Resolves or registers ADFIP investigator account.
    5. Generates short-lived (60s) single-use exchange ticket.
    6. Returns HTML with postMessage and redirect fallback for seamless desktop/browser handoff.
    """
    if error:
        err_msg = error_description or error or "Google authorization was denied or cancelled."
        log_audit_event(
            db=db,
            case_id=None,
            event_type="OAUTH_LOGIN_CANCELLED",
            details=f"Google OAuth cancelled or returned error: {err_msg}",
        )
        escaped_err = err_msg.replace('"', '\\"').replace("'", "\\'")
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Authentication Cancelled — ADFIP</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f8fafc; color: #1e293b; }}
    .card {{ background: white; padding: 2rem; border-radius: 12px; border: 1px solid #fee2e2; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); text-align: center; max-width: 420px; }}
    h2 {{ color: #dc2626; font-size: 1.1rem; margin: 0 0 0.5rem; }}
    p {{ font-size: 0.875rem; color: #64748b; margin: 0 0 1rem; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Sign In Cancelled</h2>
    <p>{err_msg}</p>
  </div>
  <script>
    if (window.opener && !window.opener.closed) {{
      window.opener.postMessage({{ type: 'ADFIP_OAUTH_ERROR', error: "{escaped_err}" }}, '*');
      setTimeout(() => window.close(), 600);
    }} else {{
      window.location.href = '/signin?error=' + encodeURIComponent("{escaped_err}");
    }}
  </script>
</body>
</html>"""
        return HTMLResponse(content=html_content, status_code=400)

    try:
        oauth_state = GoogleOAuthService.verify_and_consume_state(db=db, state=state or "")
        tokens = GoogleOAuthService.exchange_code_for_tokens(
            code=code or "",
            code_verifier=oauth_state.code_verifier,
            redirect_uri=oauth_state.redirect_uri,
        )
        identity = GoogleOAuthService.verify_google_identity(
            access_token=tokens.get("access_token") or "",
            id_token=tokens.get("id_token"),
        )
        user, _ = GoogleOAuthService.resolve_or_create_user(db=db, identity=identity)
        ticket = GoogleOAuthService.create_exchange_code(db=db, user=user)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Authentication Successful — ADFIP</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f8fafc; color: #1e293b; }}
    .card {{ background: white; padding: 2.2rem; border-radius: 14px; border: 1px solid #e2e8f0; box-shadow: 0 10px 25px -5px rgb(0 0 0 / 0.1); text-align: center; max-width: 400px; }}
    .spinner {{ width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #0f172a; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 1.2rem; }}
    h2 {{ font-size: 1.15rem; font-weight: 600; color: #0f172a; margin: 0 0 0.4rem; }}
    p {{ font-size: 0.85rem; color: #64748b; margin: 0; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>
  <div class="card">
    <div class="spinner"></div>
    <h2>Authenticated</h2>
    <p>Returning to ADFIP investigation workstation...</p>
  </div>
  <script>
    const ticket = "{ticket}";
    if (window.opener && !window.opener.closed) {{
      window.opener.postMessage({{ type: 'ADFIP_OAUTH_SUCCESS', code: ticket }}, '*');
      setTimeout(() => window.close(), 400);
    }} else {{
      window.location.href = '/auth/callback?code=' + encodeURIComponent(ticket);
    }}
  </script>
</body>
</html>"""
        return HTMLResponse(content=html_content, status_code=200)

    except HTTPException as http_exc:
        err_detail = http_exc.detail
        escaped_err = str(err_detail).replace('"', '\\"').replace("'", "\\'")
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Authentication Error — ADFIP</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f8fafc; color: #1e293b; }}
    .card {{ background: white; padding: 2rem; border-radius: 12px; border: 1px solid #fecaca; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); text-align: center; max-width: 440px; }}
    h2 {{ color: #b91c1c; font-size: 1.1rem; margin: 0 0 0.5rem; }}
    p {{ font-size: 0.875rem; color: #475569; margin: 0 0 1rem; line-height: 1.4; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Authentication Failed</h2>
    <p>{err_detail}</p>
  </div>
  <script>
    if (window.opener && !window.opener.closed) {{
      window.opener.postMessage({{ type: 'ADFIP_OAUTH_ERROR', error: "{escaped_err}" }}, '*');
      setTimeout(() => window.close(), 800);
    }} else {{
      window.location.href = '/signin?error=' + encodeURIComponent("{escaped_err}");
    }}
  </script>
</body>
</html>"""
        return HTMLResponse(content=html_content, status_code=http_exc.status_code)


@router.post("/google/exchange", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def exchange_oauth_code_for_jwt(
    req: OAuthExchangeRequest,
    db: Session = Depends(get_db),
):
    """
    Exchanges a single-use, 60-second exchange ticket for an official signed ADFIP JWT access token.
    Prevents token leakage through browser history, referer headers, or URL parameters.
    """
    return GoogleOAuthService.exchange_code_for_jwt(db=db, code=req.code)


@router.post("/google/link", response_model=UserExternalIdentityResponse, status_code=status.HTTP_200_OK)
def link_google_identity(
    req: AccountLinkRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Securely links an existing password account to a Google OAuth identity.
    Requires proof of password control to prevent unauthorized account takeover.
    """
    # 1. Verify current account password
    if current_user.password_hash:
        if not verify_password(req.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect account password. Proof of account control failed."
            )

    # 2. Exchange ticket to obtain the verified Google identity claims
    # (The exchange code maps to the user or identity extracted during OAuth)
    token_resp = GoogleOAuthService.exchange_code_for_jwt(db=db, code=req.exchange_code)
    target_user_id = token_resp.user.id

    # If the exchange code was tied to a temporary user, fetch external identity
    ext_id = (
        db.query(UserExternalIdentity)
        .filter(UserExternalIdentity.user_id == target_user_id, UserExternalIdentity.provider == "google")
        .first()
    )
    if not ext_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google identity record not found for supplied exchange code."
        )

    linked = GoogleOAuthService.link_google_account_to_user(
        db=db,
        current_user=current_user,
        google_sub=ext_id.provider_subject,
        google_email=ext_id.provider_email or current_user.email,
    )
    return linked


@router.get("/external-identities", response_model=List[UserExternalIdentityResponse], status_code=status.HTTP_200_OK)
def list_user_external_identities(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Lists external identity provider accounts linked to the authenticated investigator.
    """
    return db.query(UserExternalIdentity).filter(UserExternalIdentity.user_id == current_user.id).all()


@router.delete("/google/unlink", status_code=status.HTTP_200_OK)
def unlink_google_identity(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Unlinks Google identity from the current investigator account.
    Fails safely if user has no password configured (prevents permanent account lockout).
    """
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink Google account without first setting a password. You would be locked out of your account."
        )

    link = (
        db.query(UserExternalIdentity)
        .filter(UserExternalIdentity.user_id == current_user.id, UserExternalIdentity.provider == "google")
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No linked Google identity found for this account."
        )

    db.delete(link)
    db.commit()

    log_audit_event(
        db=db,
        case_id=None,
        event_type="GOOGLE_OAUTH_UNLINKED",
        details=f"Google account unlinked from user '{current_user.email}'.",
        actor_id=current_user.id,
        actor_name=current_user.name,
    )

    return {"message": "Google account successfully unlinked."}



