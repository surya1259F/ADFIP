import base64
import hashlib
import html
import json
import logging
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List

import httpx
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import create_access_token, verify_password
from backend.app.models.models import (
    User,
    UserExternalIdentity,
    OAuthState,
    OAuthExchangeCode,
)
from backend.app.schemas.schemas import (
    GoogleAuthUrlResponse,
    TokenResponse,
    UserResponse,
)
from backend.app.services.audit import log_audit_event

logger = logging.getLogger("ADFIR_OAUTH")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ALLOWED_FRONTEND_REDIRECT_PATHS = {
    "/dashboard",
    "/signin",
    "/auth/callback",
    "/settings",
    "/cases",
}

ALLOWED_FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]


def safe_json_for_script(data: Any) -> str:
    """
    Safely encodes data as JSON for inclusion in an inline <script> block.
    Escapes <, >, and & as Unicode escape sequences to prevent </script> breakouts or XSS.
    """
    return (
        json.dumps(data)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def validate_redirect_url(redirect_url: Optional[str]) -> Optional[str]:
    """
    Strict allowlist validation for frontend redirect URLs.
    Prevents open redirect attacks (e.g., //evil, https://evil, javascript:, data:).
    """
    if not redirect_url:
        return None
    url = redirect_url.strip()
    if url.startswith(("//", "http://", "https://", "javascript:", "data:", "vbscript:")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URL: Absolute URLs, protocol schemes, and protocol-relative URLs are not permitted."
        )
    if ":" in url or "\\" in url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URL: Contains invalid characters or schemes."
        )
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme or parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect URL: External destinations are prohibited."
        )
    clean_path = parsed.path.rstrip("/")
    if clean_path not in ALLOWED_FRONTEND_REDIRECT_PATHS and parsed.path not in ALLOWED_FRONTEND_REDIRECT_PATHS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid redirect URL path '{parsed.path}'. Allowed redirect paths are: {sorted(list(ALLOWED_FRONTEND_REDIRECT_PATHS))}."
        )
    return url


def validate_frontend_origin(origin: Optional[str]) -> str:
    """
    Validates origin against configured allowed origins.
    Defaults to http://localhost:5173 if not provided or unrecognized.
    """
    if origin and origin.strip():
        clean_origin = origin.strip().rstrip("/")
        if clean_origin in ALLOWED_FRONTEND_ORIGINS:
            return clean_origin
    return "http://localhost:5173"


class OAuthRateLimiter:
    """Lightweight in-memory rate limiter per IP address for OAuth sensitive endpoints."""
    _requests: Dict[str, List[float]] = {}

    @classmethod
    def check_rate_limit(cls, client_ip: str, max_requests: int = 30, window_seconds: int = 60) -> None:
        now = time.time()
        timestamps = cls._requests.setdefault(client_ip, [])
        cutoff = now - window_seconds
        cls._requests[client_ip] = [ts for ts in timestamps if ts > cutoff]
        if len(cls._requests[client_ip]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication requests. Please try again later."
            )
        cls._requests[client_ip].append(now)


class GoogleOAuthService:
    """
    Production-grade Google OAuth 2.0 / OpenID Connect service for ADFIP.
    Implements Authorization Code flow with PKCE S256, single-use state verification,
    OIDC nonce verification, SHA-256 ticket hashing, atomic replay protection,
    strict redirect URL validation, and hardened account linking.
    """

    GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
    GOOGLE_TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"

    @classmethod
    def is_configured(cls) -> bool:
        """Returns True if Google OAuth credentials are fully configured."""
        return settings.IS_GOOGLE_OAUTH_CONFIGURED

    @classmethod
    def get_login_url(
        cls,
        db: Session,
        frontend_redirect_url: Optional[str] = None,
        purpose: str = "LOGIN",
        target_user: Optional[User] = None,
        frontend_origin: Optional[str] = None,
    ) -> GoogleAuthUrlResponse:
        """
        Initiates Google OAuth 2.0 flow:
        1. Verifies configuration exists.
        2. Validates redirect path and origin against strict allowlists.
        3. Generates cryptographically secure, random state (32 bytes urlsafe).
        4. Generates PKCE code_verifier and code_challenge (S256).
        5. Generates cryptographically random OIDC nonce (32 bytes urlsafe).
        6. Persists OAuthState with purpose (LOGIN vs LINK) and target_user_id.
        7. Constructs and returns the Google authorization URL.
        """
        if not cls.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth is not configured for this deployment. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in deployment configuration."
            )

        clean_purpose = purpose.upper()
        if clean_purpose not in ("LOGIN", "LINK"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OAuth purpose '{purpose}'. Must be 'LOGIN' or 'LINK'."
            )

        if clean_purpose == "LINK" and not target_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target user required for account linking OAuth flow."
            )

        validated_redirect = validate_redirect_url(frontend_redirect_url)
        validated_origin = validate_frontend_origin(frontend_origin)

        # Generate cryptographically secure state, PKCE verifier, and OIDC nonce
        state_token = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        nonce = secrets.token_urlsafe(32)

        # S256 code challenge
        challenge_bytes = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")

        redirect_uri = settings.EFFECTIVE_GOOGLE_REDIRECT_URI

        # Persist single-use state
        oauth_state = OAuthState(
            state=state_token,
            provider="google",
            purpose=clean_purpose,
            target_user_id=target_user.id if target_user else None,
            nonce=nonce,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            frontend_redirect_url=validated_redirect,
            frontend_origin=validated_origin,
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(minutes=10),
            is_consumed=False,
        )
        db.add(oauth_state)
        db.commit()

        # Build authorization URL
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state_token,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "select_account",
        }
        auth_url = f"{cls.GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

        audit_event = "OAUTH_LOGIN_INITIATED" if clean_purpose == "LOGIN" else "OAUTH_LINK_ATTEMPT"
        log_audit_event(
            db=db,
            case_id=None,
            event_type=audit_event,
            details=f"Google OAuth 2.0 {clean_purpose} flow initiated.",
            actor_id=target_user.id if target_user else None,
            actor_name=target_user.name if target_user else None,
        )

        return GoogleAuthUrlResponse(
            authorization_url=auth_url,
            state=state_token,
            is_configured=True,
        )

    @classmethod
    def verify_and_consume_state(cls, db: Session, state: str) -> OAuthState:
        """
        Validates OAuth state atomically:
        - Must exist in DB
        - Must not be already consumed (atomic UPDATE where is_consumed=False)
        - Must not be expired (10 min TTL)
        Immediately marks state as consumed in the database.
        """
        if not state or not state.strip():
            log_audit_event(
                db=db,
                case_id=None,
                event_type="OAUTH_STATE_INVALID",
                details="Missing OAuth state token in callback.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing OAuth state parameter."
            )

        clean_state = state.strip()
        now = utc_now()

        # Atomic check-and-consume: prevents race condition double-consumption
        updated_rows = (
            db.query(OAuthState)
            .filter(
                OAuthState.state == clean_state,
                OAuthState.is_consumed.is_(False),
                OAuthState.expires_at > now,
            )
            .update(
                {OAuthState.is_consumed: True, OAuthState.consumed_at: now},
                synchronize_session=False,
            )
        )
        db.commit()

        if updated_rows == 1:
            record = db.query(OAuthState).filter(OAuthState.state == clean_state).first()
            return record

        # Atomic update failed: diagnose reason for accurate response and audit event
        record = db.query(OAuthState).filter(OAuthState.state == clean_state).first()
        if not record:
            log_audit_event(
                db=db,
                case_id=None,
                event_type="OAUTH_STATE_INVALID",
                details="OAuth state not found in database. Possible CSRF attempt.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or unrecognized OAuth state token."
            )

        if record.is_consumed:
            log_audit_event(
                db=db,
                case_id=None,
                event_type="OAUTH_STATE_REPLAYED",
                details="OAuth state has already been consumed. Replay attack blocked.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth state token has already been consumed."
            )

        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            log_audit_event(
                db=db,
                case_id=None,
                event_type="OAUTH_STATE_EXPIRED",
                details="OAuth state token expired prior to callback completion.",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth state token has expired. Please initiate sign in again."
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state validation failed."
        )

    @classmethod
    def exchange_code_for_tokens(
        cls,
        code: str,
        code_verifier: Optional[str],
        redirect_uri: str,
        http_client: Optional[httpx.Client] = None
    ) -> Dict[str, Any]:
        """
        Exchanges Google authorization code for access and ID tokens via Google's token endpoint.
        """
        if not code or not code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code missing from Google callback."
            )

        token_payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code.strip(),
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            token_payload["code_verifier"] = code_verifier

        client = http_client or httpx.Client(timeout=15.0)
        try:
            resp = client.post(cls.GOOGLE_TOKEN_ENDPOINT, data=token_payload)
            if resp.status_code != 200:
                logger.warning("Google token exchange error (%d): %s", resp.status_code, resp.text)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange authorization code with Google identity service."
                )
            return resp.json()
        except httpx.RequestError as exc:
            logger.error("Network error during Google token exchange: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to reach Google OAuth services. Verify network connectivity."
            )
        finally:
            if http_client is None:
                client.close()

    @classmethod
    def verify_google_identity(
        cls,
        access_token: str,
        id_token: Optional[str] = None,
        expected_nonce: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Validates Google identity tokens and claims (MANDATORY ID TOKEN & NONCE, FAIL CLOSED):
        1. Mandates presence of both id_token and expected_nonce (fails closed if omitted).
        2. Cryptographically validates id_token via Google tokeninfo endpoint:
           - Status MUST be 200 (fails closed if non-200)
           - Issuer MUST be accounts.google.com or https://accounts.google.com
           - Audience MUST match settings.GOOGLE_CLIENT_ID
           - Expiration MUST be in the future
           - Subject MUST be present and non-empty (authoritative identity)
           - Email MUST be present, non-empty, and valid
           - Email verified MUST be True
           - Nonce MUST match expected_nonce from OAuthState
        3. Treats userinfo as supplementary enrichment only:
           - Fetches userinfo via access_token if available
           - Validates that userinfo claims do NOT conflict with verified ID token
           - Fails closed if userinfo subject or email conflicts with ID token
        4. Uses verified ID token claims as authoritative identity.
        """
        # 1. Mandatory ID token check (FAIL CLOSED)
        if not id_token or not str(id_token).strip():
            logger.error("Missing mandatory Google OIDC ID token")
            if db:
                log_audit_event(
                    db=db,
                    case_id=None,
                    event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                    details="Missing mandatory Google OIDC ID token in verification request.",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OIDC ID token is mandatory. Authentication failed closed."
            )

        # 2. Mandatory Nonce check (FAIL CLOSED)
        if not expected_nonce or not str(expected_nonce).strip():
            logger.error("Missing mandatory transaction nonce for Google OIDC verification")
            if db:
                log_audit_event(
                    db=db,
                    case_id=None,
                    event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                    details="Missing mandatory transaction nonce in stored OAuth state.",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OIDC transaction nonce is mandatory. Authentication failed closed."
            )

        client = http_client or httpx.Client(timeout=15.0)
        try:
            # 3. Validate ID token via Google tokeninfo endpoint (FAIL CLOSED)
            tokeninfo_resp = client.get(
                f"{cls.GOOGLE_TOKENINFO_ENDPOINT}?id_token={urllib.parse.quote(str(id_token).strip())}"
            )
            if tokeninfo_resp.status_code != 200:
                logger.error("Google tokeninfo validation failed (%d): %s", tokeninfo_resp.status_code, tokeninfo_resp.text)
                if db:
                    log_audit_event(
                        db=db,
                        case_id=None,
                        event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                        details=f"Google tokeninfo endpoint returned status {tokeninfo_resp.status_code}.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google ID token validation failed."
                )

            tokeninfo = tokeninfo_resp.json()
            aud = tokeninfo.get("aud")
            iss = tokeninfo.get("iss")
            expected_iss = ["accounts.google.com", "https://accounts.google.com"]

            if settings.GOOGLE_CLIENT_ID and aud != settings.GOOGLE_CLIENT_ID:
                logger.error("Google ID token audience mismatch: %s != %s", aud, settings.GOOGLE_CLIENT_ID)
                if db:
                    log_audit_event(
                        db=db,
                        case_id=None,
                        event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                        details="Google ID token audience mismatch.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google ID token audience mismatch."
                )

            if iss not in expected_iss:
                logger.error("Google ID token issuer mismatch: %s", iss)
                if db:
                    log_audit_event(
                        db=db,
                        case_id=None,
                        event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                        details=f"Google ID token issuer mismatch: {iss}.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google ID token issuer mismatch."
                )

            # Expiration check
            try:
                exp_val = int(tokeninfo.get("exp", 0))
                if exp_val <= int(time.time()):
                    logger.error("Google ID token has expired (exp=%s)", exp_val)
                    if db:
                        log_audit_event(
                            db=db,
                            case_id=None,
                            event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                            details="Google ID token has expired.",
                        )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Google ID token has expired."
                    )
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid expiration claim in Google ID token."
                )

            # Subject check (authoritative identity from verified ID token)
            id_token_sub = str(tokeninfo.get("sub") or "").strip()
            if not id_token_sub:
                logger.error("Google ID token missing permanent subject identifier")
                if db:
                    log_audit_event(
                        db=db,
                        case_id=None,
                        event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                        details="Google ID token missing sub claim.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google ID token missing permanent subject identifier."
                )

            # Email check in ID token
            id_token_email = str(tokeninfo.get("email") or "").lower().strip()
            if not id_token_email or "@" not in id_token_email:
                logger.error("Invalid or missing email claim in Google ID token: %s", id_token_email)
                if db:
                    log_audit_event(
                        db=db,
                        case_id=None,
                        event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                        details="Invalid or missing email claim in Google ID token.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid email address returned from Google identity service."
                )

            # Email verified check in tokeninfo
            tokeninfo_email_verified = tokeninfo.get("email_verified")
            if tokeninfo_email_verified not in [True, "true", "True", 1]:
                logger.error("Google ID token email is not verified")
                if db:
                    log_audit_event(
                        db=db,
                        case_id=None,
                        event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                        details="Google ID token email is not verified.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google account email is not verified. A verified email address is required for ADFIP access."
                )

            # Mandatory Nonce match check
            token_nonce = tokeninfo.get("nonce")
            if not token_nonce or str(token_nonce).strip() != str(expected_nonce).strip():
                logger.error("OIDC nonce mismatch: expected %s, got %s", expected_nonce, token_nonce)
                if db:
                    log_audit_event(
                        db=db,
                        case_id=None,
                        event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                        details=f"OIDC nonce mismatch: expected {expected_nonce}, got {token_nonce}.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OIDC nonce mismatch. Possible replay or authentication injection attack."
                )

            # 4. Supplementary userinfo profile enrichment (cannot override verified ID token identity)
            name = str(tokeninfo.get("name") or id_token_email.split("@")[0]).strip()
            picture = tokeninfo.get("picture")

            if access_token and str(access_token).strip():
                try:
                    userinfo_resp = client.get(
                        cls.GOOGLE_USERINFO_ENDPOINT,
                        headers={"Authorization": f"Bearer {str(access_token).strip()}"}
                    )
                    if userinfo_resp.status_code == 200:
                        userinfo = userinfo_resp.json()
                        # Strict consistency check 1: subject mismatch (FAIL CLOSED)
                        userinfo_sub = str(userinfo.get("sub") or "").strip()
                        if userinfo_sub and userinfo_sub != id_token_sub:
                            logger.error("Subject mismatch between ID token and userinfo: %s != %s", id_token_sub, userinfo_sub)
                            if db:
                                log_audit_event(
                                    db=db,
                                    case_id=None,
                                    event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                                    details=f"Subject mismatch between ID token ({id_token_sub}) and userinfo ({userinfo_sub}).",
                                )
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Google identity subject mismatch between ID token and userinfo."
                            )

                        # Strict consistency check 2: email mismatch (FAIL CLOSED)
                        userinfo_email = str(userinfo.get("email") or "").lower().strip()
                        if userinfo_email and userinfo_email != id_token_email:
                            logger.error("Email mismatch between ID token and userinfo: %s != %s", id_token_email, userinfo_email)
                            if db:
                                log_audit_event(
                                    db=db,
                                    case_id=None,
                                    event_type="OAUTH_IDENTITY_VERIFICATION_FAILED",
                                    details=f"Email mismatch between ID token ({id_token_email}) and userinfo ({userinfo_email}).",
                                )
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Google identity email mismatch between ID token and userinfo."
                            )

                        # Profile enrichment only
                        if userinfo.get("name"):
                            name = str(userinfo.get("name")).strip()
                        if userinfo.get("picture"):
                            picture = userinfo.get("picture")
                except HTTPException:
                    raise
                except Exception as exc:
                    logger.warning("Supplementary userinfo fetch failed: %s", exc)

            return {
                "sub": id_token_sub,
                "email": id_token_email,
                "name": name,
                "picture": picture,
            }
        except HTTPException:
            raise
        except httpx.RequestError as exc:
            logger.error("Network error during Google identity verification: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to verify identity with Google services."
            )
        finally:
            if http_client is None:
                client.close()

    @classmethod
    def resolve_or_create_user(
        cls,
        db: Session,
        identity: Dict[str, Any]
    ) -> Tuple[User, bool]:
        """
        Resolves or creates the ADFIP user based on Google identity:
        Scenario A: New Google user -> creates investigator account (INVESTIGATOR role) + links identity.
        Scenario B: Existing linked Google user -> authenticates account.
        Scenario C: Email matches existing password user with NO Google link -> REJECTS silent takeover.
        Handles concurrent user creation race conditions safely with database transactions.
        """
        google_sub = identity["sub"]
        google_email = identity["email"]
        google_name = identity["name"]

        # Check existing external identity link
        ext_identity = (
            db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.provider == "google",
                UserExternalIdentity.provider_subject == google_sub
            )
            .first()
        )

        if ext_identity:
            # Scenario B: Existing linked user
            user = ext_identity.user
            if not user or not user.is_active:
                log_audit_event(
                    db=db,
                    case_id=None,
                    event_type="OAUTH_DISABLED_USER_ATTEMPT",
                    details=f"Deactivated user '{google_email}' attempted Google OAuth login.",
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is deactivated. Contact your system administrator."
                )

            user.last_login_at = utc_now()
            db.commit()
            db.refresh(user)

            log_audit_event(
                db=db,
                case_id=None,
                event_type="USER_LOGIN_SUCCESSFUL",
                details=f"User '{user.email}' authenticated via Google OAuth.",
                actor_id=user.id,
                actor_name=user.name,
            )
            return user, False

        # Check if an account already exists with this email address
        existing_user = db.query(User).filter(User.email == google_email).first()
        if existing_user:
            # Scenario C: Existing account with same email, but NO Google link.
            # DO NOT silently link! Require proof of account control.
            log_audit_event(
                db=db,
                case_id=None,
                event_type="OAUTH_LINK_DENIED",
                details=f"Google identity '{google_sub}' matches existing password account '{google_email}'. Silent linking blocked.",
                actor_id=existing_user.id,
                actor_name=existing_user.name,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"An account with email '{google_email}' already exists. "
                    "For security, please sign in with your investigator password, "
                    "then link your Google account in Settings."
                )
            )

        # Scenario A: New user registration via Google OAuth with race-condition safety
        try:
            new_user = User(
                email=google_email,
                name=google_name,
                organization="Digital Forensics Unit",
                role="INVESTIGATOR",  # Least-privileged investigator default; NEVER admin
                is_active=True,
                password_hash=None,  # External OAuth-authenticated user
                last_login_at=utc_now(),
            )
            db.add(new_user)
            db.flush()

            new_ext = UserExternalIdentity(
                user_id=new_user.id,
                provider="google",
                provider_subject=google_sub,
                provider_email=google_email,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(new_ext)
            db.commit()
            db.refresh(new_user)

            log_audit_event(
                db=db,
                case_id=None,
                event_type="USER_ACCOUNT_CREATED",
                details=f"User account '{new_user.email}' created via verified Google OAuth.",
                actor_id=new_user.id,
                actor_name=new_user.name,
            )
            log_audit_event(
                db=db,
                case_id=None,
                event_type="GOOGLE_OAUTH_LINKED",
                details=f"Google subject '{google_sub}' linked to user '{new_user.email}'.",
                actor_id=new_user.id,
                actor_name=new_user.name,
            )

            return new_user, True
        except IntegrityError:
            db.rollback()
            # Concurrent registration happened: retry resolving existing identity
            existing_ext = (
                db.query(UserExternalIdentity)
                .filter(
                    UserExternalIdentity.provider == "google",
                    UserExternalIdentity.provider_subject == google_sub
                )
                .first()
            )
            if existing_ext and existing_ext.user and existing_ext.user.is_active:
                return existing_ext.user, False
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent user registration conflict. Please try signing in again."
            )

    @classmethod
    def create_exchange_code(
        cls,
        db: Session,
        user: Optional[User] = None,
        purpose: str = "LOGIN",
        target_user_id: Optional[str] = None,
        google_sub: Optional[str] = None,
        google_email: Optional[str] = None,
    ) -> str:
        """
        Generates a single-use, high-entropy exchange ticket valid for 60 seconds.
        Stores SHA-256 digest in database instead of plaintext ticket.
        Returns the raw ticket once to the client for immediate single exchange.
        """
        raw_ticket = secrets.token_urlsafe(32)
        code_hash = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()

        record = OAuthExchangeCode(
            code=code_hash,  # Store one-way hash in code column to satisfy NOT NULL constraints
            code_hash=code_hash,
            purpose=purpose.upper(),
            user_id=user.id if user else target_user_id,
            target_user_id=target_user_id,
            google_sub=google_sub,
            google_email=google_email,
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(seconds=60),
            is_consumed=False,
        )

        db.add(record)
        db.commit()
        return raw_ticket

    @classmethod
    def exchange_code_for_jwt(cls, db: Session, code: str) -> TokenResponse:
        """
        Validates single-use exchange ticket and returns the official ADFIP Bearer JWT.
        Performs atomic single-use consumption to prevent replay race conditions.
        Enforces purpose == 'LOGIN'.
        """
        if not code or not code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing exchange code."
            )

        clean_code = code.strip()
        code_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()
        now = utc_now()

        # Atomic check-and-consume: prevents race condition double-consumption
        updated_rows = (
            db.query(OAuthExchangeCode)
            .filter(
                (OAuthExchangeCode.code_hash == code_hash) | (OAuthExchangeCode.code == clean_code),
                OAuthExchangeCode.is_consumed.is_(False),
                OAuthExchangeCode.expires_at > now,
            )
            .update(
                {OAuthExchangeCode.is_consumed: True, OAuthExchangeCode.consumed_at: now},
                synchronize_session=False,
            )
        )
        db.commit()

        if updated_rows != 1:
            record = (
                db.query(OAuthExchangeCode)
                .filter((OAuthExchangeCode.code_hash == code_hash) | (OAuthExchangeCode.code == clean_code))
                .first()
            )
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired OAuth exchange code."
                )
            if record.is_consumed:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="OAuth exchange code has already been consumed."
                )
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="OAuth exchange code has expired. Please initiate login again."
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth exchange code validation failed."
            )

        record = (
            db.query(OAuthExchangeCode)
            .filter((OAuthExchangeCode.code_hash == code_hash) | (OAuthExchangeCode.code == clean_code))
            .first()
        )

        if record.purpose != "LOGIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid ticket purpose. This exchange ticket was not issued for login."
            )

        user = record.user
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Investigator account is deactivated."
            )

        token = create_access_token(user_id=user.id, email=user.email, role=user.role)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    @classmethod
    def verify_and_consume_link_ticket(cls, db: Session, code: str, current_user: User) -> OAuthExchangeCode:
        """
        Validates and atomically consumes a link-specific OAuth ticket.
        Enforces:
        - Must exist and not be expired
        - Must not be replayed
        - ticket.purpose == 'LINK'
        - ticket.target_user_id == current_user.id (prevents cross-account ticket abuse)
        """
        if not code or not code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing exchange code."
            )

        clean_code = code.strip()
        code_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()
        now = utc_now()

        updated_rows = (
            db.query(OAuthExchangeCode)
            .filter(
                (OAuthExchangeCode.code_hash == code_hash) | (OAuthExchangeCode.code == clean_code),
                OAuthExchangeCode.purpose == "LINK",
                OAuthExchangeCode.target_user_id == current_user.id,
                OAuthExchangeCode.is_consumed.is_(False),
                OAuthExchangeCode.expires_at > now,
            )
            .update(
                {OAuthExchangeCode.is_consumed: True, OAuthExchangeCode.consumed_at: now},
                synchronize_session=False,
            )
        )
        db.commit()

        if updated_rows != 1:
            record = (
                db.query(OAuthExchangeCode)
                .filter((OAuthExchangeCode.code_hash == code_hash) | (OAuthExchangeCode.code == clean_code))
                .first()
            )
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired OAuth exchange code."
                )
            if record.purpose != "LINK":
                log_audit_event(
                    db=db,
                    case_id=None,
                    event_type="OAUTH_LINK_DENIED",
                    details="Attempted to use non-link ticket for account linking.",
                    actor_id=current_user.id,
                    actor_name=current_user.name,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid ticket purpose. Link flow requires a dedicated link transaction."
                )
            if record.target_user_id != current_user.id:
                log_audit_event(
                    db=db,
                    case_id=None,
                    event_type="OAUTH_LINK_CROSS_ACCOUNT_BLOCKED",
                    details=f"User '{current_user.id}' attempted to use link ticket issued to '{record.target_user_id}'.",
                    actor_id=current_user.id,
                    actor_name=current_user.name,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-account linking prohibited. The OAuth link transaction does not belong to this user."
                )
            if record.is_consumed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth exchange code has already been consumed."
                )
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth exchange code has expired. Please initiate linking again."
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth exchange code validation failed."
            )

        record = (
            db.query(OAuthExchangeCode)
            .filter((OAuthExchangeCode.code_hash == code_hash) | (OAuthExchangeCode.code == clean_code))
            .first()
        )
        return record

    @classmethod
    def link_google_account_to_user(
        cls,
        db: Session,
        current_user: User,
        google_sub: str,
        google_email: str,
    ) -> UserExternalIdentity:
        """
        Explicitly links an authenticated investigator account to a verified Google identity.
        Invariants enforced:
        - google_sub must NOT be linked to another investigator account (409 Conflict)
        - user's role, permissions, and profile remain completely unaltered
        """
        # Ensure provider_subject not already linked elsewhere
        existing_link = (
            db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.provider == "google",
                UserExternalIdentity.provider_subject == google_sub
            )
            .first()
        )
        if existing_link:
            if existing_link.user_id == current_user.id:
                return existing_link
            log_audit_event(
                db=db,
                case_id=None,
                event_type="OAUTH_LINK_DENIED",
                details=f"Google subject '{google_sub}' is already linked to user '{existing_link.user_id}'.",
                actor_id=current_user.id,
                actor_name=current_user.name,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked to another investigator profile."
            )

        # Case A check: Check if current user already has a Google account linked
        user_link = (
            db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.provider == "google",
                UserExternalIdentity.user_id == current_user.id
            )
            .first()
        )
        if user_link:
            # If already linked to the exact same Google identity, return idempotently
            if user_link.provider_subject == google_sub:
                return user_link

            # Current user already has a different Google identity linked: REJECT silent replacement
            log_audit_event(
                db=db,
                case_id=None,
                event_type="OAUTH_LINK_DENIED",
                details=f"User '{current_user.id}' already has Google identity '{user_link.provider_subject}' linked. Replacement with '{google_sub}' rejected.",
                actor_id=current_user.id,
                actor_name=current_user.name,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A Google account is already linked to this investigator profile. It must be explicitly unlinked before another Google account can be linked."
            )

        link_record = UserExternalIdentity(
            user_id=current_user.id,
            provider="google",
            provider_subject=google_sub,
            provider_email=google_email,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(link_record)
        db.commit()
        db.refresh(link_record)

        log_audit_event(
            db=db,
            case_id=None,
            event_type="GOOGLE_OAUTH_LINKED",
            details=f"Google account '{google_email}' ({google_sub}) successfully linked to user '{current_user.email}'.",
            actor_id=current_user.id,
            actor_name=current_user.name,
        )

        return link_record
