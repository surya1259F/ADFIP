"""
ADFIR — AI Reasoning Layer & Copilot API Endpoints (Phase 2 / Step 18)

Governed AI reasoning downstream of verified forensic structure.
Endpoints for:
- AI provider configuration, removal, and health status
- Provider connection testing without secret leakage
- Governed reasoning creation with FACT / INFERENCE / UNVERIFIED classification
- Retrieval of reasoning records and classified insights
- Cryptographic SHA-256 integrity verification and tamper detection
- Lineage, governance, and citation provenance inspection
- Backward-compatible Copilot endpoints
"""

import logging
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import get_current_active_user
from backend.app.models.models import User, AIReasoningRecord
from backend.app.schemas.schemas import (
    CopilotQueryRequest,
    ExplainFindingRequest,
    ProviderTestRequest,
    ProviderTestResponse,
    EgressPolicy,
    AIProviderConfigRequest,
    AIProviderConfigResponse,
    AIProviderConnectionTestRequest,
    AIProviderConnectionTestResponse,
    AIReasoningRequest,
    AIReasoningResponse,
    AIStatementItem,
    AIReasoningIntegrityResponse,
    AIReasoningProvenanceResponse
)
from backend.app.services.authorization import get_authorized_case
from backend.app.services.ai_copilot import (
    AICopilotResponse,
    AIExplanationResponse,
    run_copilot_query,
    explain_case_finding
)
from backend.app.services.ai_provider import (
    ProviderRequest,
    ProviderError,
    get_ai_adapter
)
from backend.app.services.ai_reasoning import (
    AIReasoningService,
    mask_credential,
    decrypt_credential
)
from backend.app.services.audit import log_audit_event

logger = logging.getLogger("ADFIR_AI_API")

router = APIRouter()

EXTERNAL_PROVIDERS = {"openai", "anthropic", "google", "gemini"}


def _resolve_effective_provider(requested_provider: Optional[str], egress_policy: EgressPolicy) -> str:
    p_clean = (requested_provider or "local_stub").lower().strip()
    if egress_policy in (EgressPolicy.LOCAL_ONLY, EgressPolicy.EXTERNAL_PROVIDER_BLOCKED):
        if p_clean in EXTERNAL_PROVIDERS:
            logger.info(f"Egress policy {egress_policy.value} blocked external provider '{p_clean}'. Redirecting to local_stub.")
            return "local_stub"
    return p_clean


# =============================================================================
# 1. AI PROVIDER CONFIGURATION & STATUS ENDPOINTS
# =============================================================================

@router.post("/provider/config", response_model=AIProviderConfigResponse, status_code=status.HTTP_200_OK)
@router.post("/ai/provider/config", response_model=AIProviderConfigResponse, status_code=status.HTTP_200_OK)
def configure_provider(
    payload: AIProviderConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Configures or updates the LLM provider and securely encrypts credentials.
    API keys are never logged or returned in plaintext.
    """
    rec = AIReasoningService.configure_provider(db, current_user, payload)
    return AIProviderConfigResponse(
        id=rec.id,
        provider=rec.provider,
        model=rec.model,
        endpoint=rec.endpoint,
        has_api_key=bool(rec.api_key_encrypted),
        masked_api_key=mask_credential(decrypt_credential(rec.api_key_encrypted)),
        is_enabled=rec.is_enabled,
        status=rec.status,
        last_tested_at=rec.last_tested_at,
        last_test_status=rec.last_test_status,
        configured=bool(rec.is_enabled and (rec.api_key_encrypted or rec.provider == "local_stub")),
        key_configured=bool(rec.api_key_encrypted),
        created_at=rec.created_at,
        updated_at=rec.updated_at
    )


@router.get("/provider/config", response_model=AIProviderConfigResponse)
@router.get("/ai/provider/config", response_model=AIProviderConfigResponse)
async def get_provider_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves current user's provider configuration with masked API key.
    Automatically resolves stale saved Gemini models without altering the DB record.
    """
    rec = AIReasoningService.get_provider_config(db, current_user)
    if not rec:
        if settings.IS_GEMINI_CONFIGURED:
            return AIProviderConfigResponse(
                id="env-configured",
                provider=settings.DEFAULT_LLM_PROVIDER,
                model=getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash"),
                endpoint=None,
                has_api_key=True,
                masked_api_key="[Configured via .env]",
                is_enabled=True,
                status="CONFIGURED",
                last_tested_at=None,
                last_test_status=None,
                configured=True,
                key_configured=True,
                created_at=None,
                updated_at=None
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No AI provider configured.")

    effective_model = rec.model
    if rec.provider in ("gemini", "google"):
        stale_models = {"gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"}
        if rec.model in stale_models:
            plain_key = decrypt_credential(rec.api_key_encrypted) or (settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else None)
            if plain_key:
                try:
                    adapter = get_ai_adapter("gemini")
                    discovered = await adapter.list_models(api_key=plain_key, base_url=rec.endpoint)
                    if discovered:
                        effective_model = rec.model if rec.model in discovered else discovered[0]
                    else:
                        effective_model = getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
                except Exception:
                    effective_model = getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
            else:
                effective_model = getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")

    return AIProviderConfigResponse(
        id=rec.id,
        provider=rec.provider,
        model=effective_model,
        endpoint=rec.endpoint,
        has_api_key=bool(rec.api_key_encrypted),
        masked_api_key=mask_credential(decrypt_credential(rec.api_key_encrypted)),
        is_enabled=rec.is_enabled,
        status=rec.status,
        last_tested_at=rec.last_tested_at,
        last_test_status=rec.last_test_status,
        configured=bool(rec.is_enabled and (rec.api_key_encrypted or rec.provider == "local_stub")),
        key_configured=bool(rec.api_key_encrypted),
        created_at=rec.created_at,
        updated_at=rec.updated_at
    )


@router.delete("/provider/config", status_code=status.HTTP_200_OK)
@router.delete("/ai/provider/config", status_code=status.HTTP_200_OK)
def remove_provider_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Removes stored provider configuration and encrypted credentials.
    """
    removed = AIReasoningService.remove_provider_config(db, current_user)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No AI provider configuration found to remove.")
    return {"status": "SUCCESS", "message": "AI provider configuration and credentials removed successfully."}


@router.get("/provider/status")
@router.get("/ai/provider/status")
def get_provider_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns current provider health and operational status.
    """
    rec = AIReasoningService.get_provider_config(db, current_user)
    if not rec:
        if settings.IS_GEMINI_CONFIGURED:
            return {
                "status": "CONFIGURED",
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "model": getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash"),
                "is_enabled": True,
                "has_api_key": True,
                "last_tested_at": None,
                "last_test_status": None,
                "fallback_available": True
            }
        return {
            "status": "UNCONFIGURED",
            "provider": "local_stub",
            "model": "adfir-deterministic-engine",
            "is_enabled": False,
            "has_api_key": False,
            "fallback_available": True
        }
    return {
        "status": rec.status,
        "provider": rec.provider,
        "model": rec.model,
        "is_enabled": rec.is_enabled,
        "has_api_key": bool(rec.api_key_encrypted),
        "last_tested_at": rec.last_tested_at.isoformat() if rec.last_tested_at else None,
        "last_test_status": rec.last_test_status,
        "fallback_available": True
    }


@router.get("/provider/models", response_model=List[str])
@router.get("/ai/provider/models", response_model=List[str])
async def get_provider_models(
    provider: Optional[str] = Query(default=None),
    endpoint: Optional[str] = Query(default=None),
    x_provider_api_key: Optional[str] = Header(default=None, alias="x-provider-api-key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Discovers and lists supported models for the AI provider dynamically.
    """
    return await AIReasoningService.list_models(
        db,
        current_user,
        provider=provider,
        api_key=x_provider_api_key,
        base_url=endpoint
    )


class _TransientModelDiscoveryRequest(BaseModel):
    """Request body for POST model discovery with a transient API key.
    The API key is used only for the discovery request, never persisted, never logged, never returned."""
    provider: str = "gemini"
    api_key: Optional[str] = None
    endpoint: Optional[str] = None


@router.post("/provider/models", response_model=List[str])
@router.post("/ai/provider/models", response_model=List[str])
async def discover_provider_models(
    payload: _TransientModelDiscoveryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Discovers models using a transient API key provided in the request body.
    The key is NOT persisted, NOT logged, and NOT returned.
    This allows model discovery before saving the key to the backend.
    """
    return await AIReasoningService.list_models(
        db,
        current_user,
        provider=payload.provider,
        api_key=payload.api_key.strip() if payload.api_key else None,
        base_url=payload.endpoint.strip() if payload.endpoint else None
    )


@router.post("/provider/test-connection", response_model=AIProviderConnectionTestResponse)
@router.post("/ai/provider/test-connection", response_model=AIProviderConnectionTestResponse)
async def test_provider_connection_endpoint(
    request: Optional[AIProviderConnectionTestRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Tests provider connectivity and authentication without leaking credentials.
    """
    return await AIReasoningService.test_connection(db, current_user, request)


# Legacy provider test endpoint compatibility
@router.post("/provider/test", response_model=ProviderTestResponse)
@router.post("/ai/provider/test", response_model=ProviderTestResponse)
async def provider_test_endpoint(
    request: ProviderTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    p_clean = request.provider.lower().strip()
    if p_clean == "google":
        p_clean = "gemini"
    if not p_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider name is required.")

    status_str = "SUCCESS"
    details_str = "Local stub provider is available."
    model_str = request.model or "adfir-deterministic-engine"

    if p_clean not in ("local_stub", "none"):
        try:
            adapter = get_ai_adapter(p_clean)
            target_model = request.model or adapter.default_model
            effective_key = request.api_key
            effective_base_url = request.base_url
            if not effective_key:
                cfg = AIReasoningService.get_provider_config(db, current_user)
                cfg_p = (cfg.provider.lower().strip() if cfg else "")
                if cfg_p == "google":
                    cfg_p = "gemini"
                if cfg and cfg_p == p_clean and cfg.api_key_encrypted:
                    effective_key = decrypt_credential(cfg.api_key_encrypted)
                    effective_base_url = effective_base_url or cfg.endpoint
                elif p_clean == "gemini" and settings.GEMINI_API_KEY:
                    effective_key = settings.GEMINI_API_KEY

            test_req = ProviderRequest(
                provider=adapter.provider_id,
                model=target_model,
                prompt="ADFIP connectivity test check. Respond with OK.",
                api_key=effective_key,
                base_url=effective_base_url
            )
            resp = await adapter.generate(test_req)
            status_str = "SUCCESS"
            details_str = f"Provider connection verified. Response generated successfully using {target_model}."
            model_str = target_model
        except Exception as e:
            status_str = "FAILED"
            details_str = f"Provider test failed: {ProviderError._sanitize(str(e))}"
            model_str = request.model or "unknown"

    log_audit_event(
        db=db,
        event_type="AI_PROVIDER_TEST",
        details=f"AI provider connectivity test for '{p_clean}' (status: {status_str})",
        actor_id=current_user.id,
        actor_name=current_user.email,
        metadata_json={
            "provider": p_clean,
            "model": model_str,
            "status": status_str
        }
    )

    return ProviderTestResponse(
        provider=p_clean,
        model=model_str,
        status=status_str,
        details=details_str
    )


# =============================================================================
# 2. GOVERNED AI REASONING ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/reason", response_model=AIReasoningResponse, status_code=status.HTTP_201_CREATED)
@router.post("/cases/{case_id}/ai/reason", response_model=AIReasoningResponse, status_code=status.HTTP_201_CREATED)
async def create_reasoning_request(
    case_id: str,
    payload: AIReasoningRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Initiates governed AI reasoning over verified structured forensic data.
    Enforces Governance Gate, prompt injection checks, and citation verification.
    """
    case = get_authorized_case(case_id, db, current_user)
    return await AIReasoningService.reason(db, case, current_user, payload)


@router.get("/cases/{case_id}/reasoning", response_model=List[AIReasoningResponse])
@router.get("/cases/{case_id}/ai/reasoning", response_model=List[AIReasoningResponse])
def list_reasoning_records(
    case_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Lists historical reasoning records for an authorized case.
    """
    case = get_authorized_case(case_id, db, current_user)
    records = db.query(AIReasoningRecord).filter(
        AIReasoningRecord.case_id == case.id
    ).order_by(AIReasoningRecord.created_at.desc()).offset(offset).limit(limit).all()

    return [
        AIReasoningResponse(
            id=r.id,
            case_id=r.case_id,
            objective=r.objective,
            status=r.status,
            execution_mode=r.execution_mode,
            provider=r.provider,
            model=r.model,
            governance_decision_id=r.governance_decision_id,
            input_references=r.input_references or {},
            raw_evidence_egress_blocked=r.raw_evidence_egress_blocked,
            egress_approved=r.egress_approved,
            statements=[AIStatementItem(**s) for s in (r.statements or [])],
            citations_verified=r.citations_verified,
            summary=r.summary,
            provenance=r.provenance or {},
            reasoning_metadata=r.reasoning_metadata or {},
            sha256_hash=r.sha256_hash,
            created_at=r.created_at,
            completed_at=r.completed_at
        ) for r in records
    ]


@router.get("/cases/{case_id}/reasoning/{reasoning_id}", response_model=AIReasoningResponse)
@router.get("/cases/{case_id}/ai/reasoning/{reasoning_id}", response_model=AIReasoningResponse)
def get_reasoning_record(
    case_id: str,
    reasoning_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves full details of a specific AI reasoning record including classified statements.
    """
    case = get_authorized_case(case_id, db, current_user)
    rec = db.query(AIReasoningRecord).filter(
        AIReasoningRecord.id == reasoning_id,
        AIReasoningRecord.case_id == case.id
    ).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI reasoning record not found.")

    return AIReasoningResponse(
        id=rec.id,
        case_id=rec.case_id,
        objective=rec.objective,
        status=rec.status,
        execution_mode=rec.execution_mode,
        provider=rec.provider,
        model=rec.model,
        governance_decision_id=rec.governance_decision_id,
        input_references=rec.input_references or {},
        raw_evidence_egress_blocked=rec.raw_evidence_egress_blocked,
        egress_approved=rec.egress_approved,
        statements=[AIStatementItem(**s) for s in (rec.statements or [])],
        citations_verified=rec.citations_verified,
        summary=rec.summary,
        provenance=rec.provenance or {},
        reasoning_metadata=rec.reasoning_metadata or {},
        sha256_hash=rec.sha256_hash,
        created_at=rec.created_at,
        completed_at=rec.completed_at
    )


@router.get("/cases/{case_id}/reasoning/{reasoning_id}/integrity", response_model=AIReasoningIntegrityResponse)
@router.get("/cases/{case_id}/ai/reasoning/{reasoning_id}/integrity", response_model=AIReasoningIntegrityResponse)
def get_reasoning_integrity(
    case_id: str,
    reasoning_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Verifies SHA-256 integrity hash of generated reasoning statements.
    Detects tampering or unauthorized modification.
    """
    get_authorized_case(case_id, db, current_user)
    return AIReasoningService.verify_integrity(db, case_id, reasoning_id)


@router.get("/cases/{case_id}/reasoning/{reasoning_id}/provenance", response_model=AIReasoningProvenanceResponse)
@router.get("/cases/{case_id}/ai/reasoning/{reasoning_id}/provenance", response_model=AIReasoningProvenanceResponse)
def get_reasoning_provenance(
    case_id: str,
    reasoning_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Inspects complete provenance, Governance Gate linkage, and input references.
    """
    case = get_authorized_case(case_id, db, current_user)
    rec = db.query(AIReasoningRecord).filter(
        AIReasoningRecord.id == reasoning_id,
        AIReasoningRecord.case_id == case.id
    ).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI reasoning record not found.")

    return AIReasoningProvenanceResponse(
        reasoning_id=rec.id,
        case_id=rec.case_id,
        governance_decision_id=rec.governance_decision_id,
        provider=rec.provider,
        model=rec.model,
        execution_mode=rec.execution_mode,
        input_references=rec.input_references or {},
        statements_count=len(rec.statements or []),
        raw_evidence_egress_blocked=rec.raw_evidence_egress_blocked,
        sha256_hash=rec.sha256_hash,
        created_at=rec.created_at
    )


# =============================================================================
# 3. LEGACY COPILOT ENDPOINTS (BACKWARD COMPATIBILITY)
# =============================================================================

@router.post("/copilot", response_model=AICopilotResponse)
@router.post("/ai/copilot", response_model=AICopilotResponse)
async def copilot_query_endpoint(
    request: CopilotQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(request.case_id, db, current_user)
    effective_provider = _resolve_effective_provider(request.provider, request.egress_policy)

    res = await run_copilot_query(
        case_id=case.id,
        query=request.query,
        db=db,
        provider=effective_provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url
    )

    log_audit_event(
        db=db,
        event_type="AI_COPILOT_QUERY",
        details=f"AI Copilot query executed for case {case.id} using provider {res.provider}",
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email,
        metadata_json={
            "provider": res.provider,
            "model": res.model,
            "execution_mode": res.execution_mode,
            "fallback_used": res.fallback_used,
            "claims_count": len(res.claims)
        }
    )
    return res


@router.post("/explain-finding", response_model=AIExplanationResponse)
@router.post("/ai/explain-finding", response_model=AIExplanationResponse)
async def explain_finding_endpoint(
    request: ExplainFindingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    case = get_authorized_case(request.case_id, db, current_user)
    effective_provider = _resolve_effective_provider(request.provider, request.egress_policy)

    res = await explain_case_finding(
        case_id=case.id,
        finding_id=request.finding_id,
        db=db,
        provider=effective_provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url
    )

    log_audit_event(
        db=db,
        event_type="AI_EXPLAIN_FINDING",
        details=f"AI finding explanation for finding {request.finding_id} in case {case.id}",
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email,
        metadata_json={
            "finding_id": request.finding_id,
            "provider": res.provider,
            "model": res.model
        }
    )
    return res
