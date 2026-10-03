import base64
import hashlib
import json
import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple

import httpx
from fastapi import HTTPException, status
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


class GoogleOAuthService:
    """
    Production-grade Google OAuth 2.0 / OpenID Connect service for ADFIP.
    Implements Authorization Code flow with PKCE, single-use state verification,
    cryptographic identity validation, safe account linking, and exchange tickets.
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
        frontend_redirect_url: Optional[str] = None
    ) -> GoogleAuthUrlResponse:
        """
        Initiates Google OAuth 2.0 flow:
        1. Verifies configuration exists.
        2. Generates cryptographically secure, random state (32 bytes).
        3. Generates PKCE code_verifier and code_challenge (S256).
        4. Persists OAuthState with strict 10-minute expiration.
        5. Constructs and returns the Google authorization URL.
        """
        if not cls.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google OAuth is not configured for this deployment. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in deployment configuration."
            )

        # Generate cryptographically secure state and PKCE verifier
        state_token = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)

        # S256 code challenge
        challenge_bytes = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode("ascii").rstrip("=")

        redirect_uri = settings.EFFECTIVE_GOOGLE_REDIRECT_URI

        # Persist single-use state
        oauth_state = OAuthState(
            state=state_token,
            provider="google",
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            frontend_redirect_url=frontend_redirect_url,
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
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "select_account",
        }
        auth_url = f"{cls.GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

        log_audit_event(
            db=db,
            case_id=None,
            event_type="OAUTH_LOGIN_INITIATED",
            details="Google OAuth 2.0 login initiated by investigator.",
        )

        return GoogleAuthUrlResponse(
            authorization_url=auth_url,
            state=state_token,
            is_configured=True,
        )

    @classmethod
    def verify_and_consume_state(cls, db: Session, state: str) -> OAuthState:
        """
        Validates OAuth state:
        - Must exist in DB
        - Must not be already consumed (replay prevention)
        - Must not be expired (10 min TTL)
        Immediately marks state as consumed.
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

        oauth_state = db.query(OAuthState).filter(OAuthState.state == state.strip()).first()
        if not oauth_state:
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

        if oauth_state.is_consumed:
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

        # Check expiration
        now = utc_now()
        # Handle naive datetime from SQLite gracefully
        expires_at = oauth_state.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
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

        # Consume immediately
        oauth_state.is_consumed = True
        oauth_state.consumed_at = now
        db.commit()

        return oauth_state

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
        http_client: Optional[httpx.Client] = None
    ) -> Dict[str, Any]:
        """
        Validates Google identity tokens and claims:
        1. Fetches verified OpenID Connect userinfo.
        2. Validates id_token issuer and audience if present.
        3. Enforces email_verified requirement.
        4. Uses stable Google sub claim as primary provider identity.
        """
        client = http_client or httpx.Client(timeout=15.0)
        try:
            # 1. Fetch userinfo from OpenID Connect endpoint
            userinfo_resp = client.get(
                cls.GOOGLE_USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_resp.status_code != 200:
                logger.warning("Google userinfo fetch failed (%d): %s", userinfo_resp.status_code, userinfo_resp.text)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to retrieve verified user information from Google."
                )
            userinfo = userinfo_resp.json()

            # 2. If ID token present, verify claims via tokeninfo
            if id_token:
                tokeninfo_resp = client.get(
                    f"{cls.GOOGLE_TOKENINFO_ENDPOINT}?id_token={urllib.parse.quote(id_token)}"
                )
                if tokeninfo_resp.status_code == 200:
                    tokeninfo = tokeninfo_resp.json()
                    aud = tokeninfo.get("aud")
                    iss = tokeninfo.get("iss")
                    expected_iss = ["accounts.google.com", "https://accounts.google.com"]

                    if settings.GOOGLE_CLIENT_ID and aud != settings.GOOGLE_CLIENT_ID:
                        logger.error("Google ID token audience mismatch: %s != %s", aud, settings.GOOGLE_CLIENT_ID)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Google ID token audience mismatch."
                        )
                    if iss not in expected_iss:
                        logger.error("Google ID token issuer mismatch: %s", iss)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Google ID token issuer mismatch."
                        )
                    if tokeninfo.get("sub") and tokeninfo.get("sub") != userinfo.get("sub"):
                        logger.error("Subject mismatch between userinfo and tokeninfo")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Google identity subject mismatch."
                        )

            # 3. Ensure sub exists
            google_sub = str(userinfo.get("sub") or "").strip()
            if not google_sub:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google identity missing permanent subject identifier."
                )

            # 4. Enforce email_verified
            email_verified = userinfo.get("email_verified")
            if email_verified not in [True, "true", "True", 1]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google account email is not verified. A verified email address is required for ADFIP access."
                )

            email = str(userinfo.get("email") or "").lower().strip()
            if not email or "@" not in email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid email address returned from Google identity service."
                )

            return {
                "sub": google_sub,
                "email": email,
                "name": str(userinfo.get("name") or email.split("@")[0]).strip(),
                "picture": userinfo.get("picture"),
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
                event_type="OAUTH_ACCOUNT_LINK_REQUIRED",
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

        # Scenario A: New user registration via Google OAuth
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
        db.commit()
        db.refresh(new_user)

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

    @classmethod
    def create_exchange_code(cls, db: Session, user: User) -> str:
        """
        Generates a single-use, high-entropy exchange ticket valid for 60 seconds.
        Prevents JWT tokens from being transmitted in URL parameters or browser history.
        """
        ticket = secrets.token_urlsafe(32)
        record = OAuthExchangeCode(
            code=ticket,
            user_id=user.id,
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(seconds=60),
            is_consumed=False,
        )
        db.add(record)
        db.commit()
        return ticket

    @classmethod
    def exchange_code_for_jwt(cls, db: Session, code: str) -> TokenResponse:
        """
        Validates single-use exchange ticket and returns the official ADFIP Bearer JWT.
        """
        if not code or not code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing exchange code."
            )

        record = db.query(OAuthExchangeCode).filter(OAuthExchangeCode.code == code.strip()).first()
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

        now = utc_now()
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OAuth exchange code has expired. Please initiate login again."
            )

        # Mark consumed immediately
        record.is_consumed = True
        record.consumed_at = now
        db.commit()

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
    def link_google_account_to_user(
        cls,
        db: Session,
        current_user: User,
        google_sub: str,
        google_email: str,
    ) -> UserExternalIdentity:
        """
        Explicitly links an authenticated investigator account to a verified Google identity.
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
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked to another investigator profile."
            )

        # Check if current user already has a Google account linked
        user_link = (
            db.query(UserExternalIdentity)
            .filter(
                UserExternalIdentity.provider == "google",
                UserExternalIdentity.user_id == current_user.id
            )
            .first()
        )
        if user_link:
            user_link.provider_subject = google_sub
            user_link.provider_email = google_email
            user_link.updated_at = utc_now()
            db.commit()
            db.refresh(user_link)
            link_record = user_link
        else:
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
