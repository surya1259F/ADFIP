import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.core.database import get_db
from backend.app.core.security import get_current_active_user
from backend.app.models.models import User
from backend.app.schemas.schemas import (
    CopilotQueryRequest,
    ExplainFindingRequest,
    ProviderTestRequest,
    ProviderTestResponse,
    EgressPolicy
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


@router.post("/copilot", response_model=AICopilotResponse)
async def copilot_query_endpoint(
    request: CopilotQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Authenticated AI Copilot Endpoint.
    Enforces Task 8 case authorization BEFORE building context or invoking LLM.
    """
    # 1. Task 8 Centralized Authorization Check
    case = get_authorized_case(request.case_id, db, current_user)

    # 2. Resolve Egress Policy
    effective_provider = _resolve_effective_provider(request.provider, request.egress_policy)

    # 3. Execute AI Copilot Query
    res = await run_copilot_query(
        case_id=case.id,
        query=request.query,
        db=db,
        provider=effective_provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url
    )

    # 4. Log Sanitized Audit Event
    log_audit_event(
        db=db,
        event_type="AI_COPILOT_QUERY",
        details=f"AI Copilot query executed for case {case.id} using provider {res.provider} (mode: {res.execution_mode}, fallback: {res.fallback_used})",
        case_id=case.id,
        actor_id=current_user.id,
        actor_name=current_user.email,
        metadata_json={
            "provider": res.provider,
            "model": res.model,
            "execution_mode": res.execution_mode,
            "fallback_used": res.fallback_used,
            "provider_status": res.provider_status,
            "context_truncated": res.context_truncated,
            "claims_count": len(res.claims)
        }
    )

    return res


@router.post("/explain-finding", response_model=AIExplanationResponse)
async def explain_finding_endpoint(
    request: ExplainFindingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Authenticated AI Finding Explanation Endpoint.
    Enforces Task 8 case authorization and server-side finding resolution inside case boundaries.
    """
    # 1. Task 8 Centralized Authorization Check
    case = get_authorized_case(request.case_id, db, current_user)

    # 2. Resolve Egress Policy
    effective_provider = _resolve_effective_provider(request.provider, request.egress_policy)

    # 3. Execute Finding Explanation
    res = await explain_case_finding(
        case_id=case.id,
        finding_id=request.finding_id,
        db=db,
        provider=effective_provider,
        model=request.model,
        api_key=request.api_key,
        base_url=request.base_url
    )

    # 4. Log Sanitized Audit Event
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
            "model": res.model,
            "execution_mode": res.execution_mode,
            "fallback_used": res.fallback_used,
            "provider_status": res.provider_status
        }
    )

    return res


@router.post("/provider/test", response_model=ProviderTestResponse)
async def provider_test_endpoint(
    request: ProviderTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Authenticated AI Provider Connectivity Test Endpoint.
    Credentials are runtime-only and strictly omitted from logs, audit events, and responses.
    """
    p_clean = request.provider.lower().strip()
    if not p_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provider name is required.")

    status_str = "SUCCESS"
    details_str = "Local stub provider is available."
    model_str = request.model or "adfir-deterministic-engine"

    if p_clean not in ("local_stub", "none"):
        try:
            adapter = get_ai_adapter(p_clean)
            target_model = request.model or adapter.default_model
            test_req = ProviderRequest(
                provider=adapter.provider_id,
                model=target_model,
                prompt="ADFIR connectivity test check.",
                api_key=request.api_key,
                base_url=request.base_url
            )
            resp = await adapter.generate(test_req)
            status_str = "SUCCESS"
            details_str = f"Provider connection verified. Response generated successfully."
            model_str = target_model
        except Exception as e:
            status_str = "FAILED"
            details_str = f"Provider test failed: {ProviderError._sanitize(str(e))}"
            model_str = request.model or "unknown"

    # Log Sanitized Audit Event (No Credentials Exposed)
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
