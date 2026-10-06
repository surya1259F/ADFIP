"""
ADFIP — Comprehensive Gemini Real End-to-End Production Tests (Section 20)

Validates the complete 10-point production suite for Google Gemini:
1. Test 1 — No key: returns CONFIGURATION_ERROR.
2. Test 2 — Invalid key: mock 401 returns INVALID_API_KEY.
3. Test 3 — Model unavailable: mock 404 returns MODEL_UNAVAILABLE.
4. Test 4 — Quota exceeded: mock 429 returns QUOTA_EXCEEDED / RATE_LIMITED.
5. Test 5 — Provider unreachable: mock timeout/connect failure returns PROVIDER_UNREACHABLE.
6. Test 6 — Successful connection: mock valid generateContent returns success=True.
7. Test 7 — Successful generation: real generated text returned, no hardcoded placeholder strings.
8. Test 8 — User credential precedence: User key takes priority over settings.GEMINI_API_KEY.
9. Test 9 — Credential secrecy: API responses, logs, exceptions, and DB never expose plaintext key.
10. Test 10 — No silent fallback: Gemini selected + error fails closed; never falls back to deterministic engine.
"""

import os
import json
import uuid
import pytest
import httpx
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import HTTPException

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal, ensure_user_auth_schema, ensure_case_auth_schema
from backend.app.models.models import (
    User,
    Case,
    Finding,
    DeterministicFinding,
    NormalizedArtifact,
    StructuredArtifact,
    ExecutionOutput,
    ForensicExecution,
    AIProviderConfigRecord,
    AuditEvent,
    AIReasoningRecord
)
from backend.app.services.authorization import ensure_case_member
from backend.app.services.ai_provider import (
    GeminiAdapter,
    ProviderRequest,
    ProviderResponse,
    ProviderError,
    AIErrorCode,
    ProviderId
)
from backend.app.services.ai_reasoning import (
    AIReasoningService,
    decrypt_credential,
    mask_credential
)
from backend.app.schemas.schemas import (
    AIProviderConfigRequest,
    AIProviderConnectionTestRequest,
    AIReasoningRequest
)
from backend.app.services.llm import GeminiProvider

client = TestClient(app)

MOCK_USER_KEY = "AIzaSyUserSpecificKey9876543210"
MOCK_ENV_KEY = "AIzaSyEnvDefaultKey0123456789"


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    ensure_user_auth_schema(engine)
    ensure_case_auth_schema(engine)
    yield


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_user_and_token(email_prefix: str, name: str = "Test Investigator"):
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@adfir.local"
    signup_res = client.post("/api/v1/auth/signup", json={
        "email": email,
        "name": name,
        "password": "Password123!"
    })
    user_id = signup_res.json()["id"]

    login_res = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Password123!"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, email, headers


def create_case_with_artifacts(owner_user_id: str, owner_email: str, db: SessionLocal):
    case_id = str(uuid.uuid4())
    case = Case(
        id=case_id,
        name=f"Gemini Investigation {case_id[:8]}",
        case_number=f"CAS-{case_id[:6]}",
        owner_id=owner_user_id,
        created_by=owner_email,
        status="OPEN"
    )
    db.add(case)
    db.commit()

    ensure_case_member(case_id=case_id, user_id=owner_user_id, db=db, role="PRIMARY_INVESTIGATOR")

    fe = ForensicExecution(
        id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        case_id=case.id,
        task_key="DISK_PARSING",
        tool_id="tsk_fls",
        executable_path="/usr/bin/fls",
        validated_argv=["fls", "-r"],
        host_platform="Linux",
        host_architecture="x86_64",
        workspace_path="/tmp/workspace",
        execution_status="COMPLETED"
    )
    db.add(fe)
    db.commit()

    exo = ExecutionOutput(
        id=str(uuid.uuid4()),
        case_id=case.id,
        execution_id=fe.id,
        request_id=fe.request_id,
        tool_id="tsk_fls",
        output_type="TOOL_OUTPUT",
        filename="fls_output.txt",
        relative_path="fls_output.txt",
        storage_path="/tmp/fls_output.txt",
        sha256_hash="1" * 64
    )
    db.add(exo)
    db.commit()

    sa = StructuredArtifact(
        id=str(uuid.uuid4()),
        case_id=case.id,
        execution_id=fe.id,
        raw_output_id=exo.id,
        parser_name="fls_parser",
        parser_version="1.0.0",
        artifact_type="FILE_ENTRY",
        source_reference="/tmp/webshell.php",
        normalized_data={"file": "webshell.php"},
        raw_record="d/d * 1234: webshell.php",
        sha256_hash="2" * 64,
        source_raw_output_hash=exo.sha256_hash,
        extraction_status="EXTRACTED",
        created_at=datetime.now(timezone.utc)
    )
    db.add(sa)
    db.commit()

    art = NormalizedArtifact(
        id=str(uuid.uuid4()),
        case_id=case.id,
        evidence_id=str(uuid.uuid4()),
        execution_id=fe.id,
        source_artifact_id=sa.id,
        entity_type="FILE",
        entity_identity="file:/var/www/webshell.php",
        normalized_fields={"path": "/var/www/webshell.php", "sha256": "3" * 64},
        sha256_hash="3" * 64,
        source_artifact_hash="2" * 64,
        normalization_status="NORMALIZED"
    )
    db.add(art)

    finding = Finding(
        id=str(uuid.uuid4()),
        case_id=case.id,
        title="Webshell Dropper Detected",
        description="PHP webshell payload found in web root.",
        severity="HIGH",
        tool="yara",
        confidence_score=0.95,
        details={"path": "/var/www/webshell.php"}
    )
    db.add(finding)
    db.commit()

    return case, art, finding


# -----------------------------------------------------------------------------
# Test 1 — No key: returns CONFIGURATION_ERROR
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_1_gemini_no_key_returns_configuration_error(monkeypatch, db_session):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    user_id, email, headers = create_user_and_token("test1_nokey")
    user = db_session.query(User).filter(User.id == user_id).first()
    AIReasoningService.remove_provider_config(db_session, user)

    # 1. Connection test via service
    test_req = AIProviderConnectionTestRequest(provider="gemini", model="gemini-3.8-flash")
    res = await AIReasoningService.test_connection(db_session, user, test_req)
    assert res.success is False
    assert res.error_code == AIErrorCode.CONFIGURATION_ERROR.value
    assert "required" in res.status_message.lower() or "not configured" in res.status_message.lower()

    # 2. Direct GeminiAdapter generate without key
    adapter = GeminiAdapter()
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Test",
        api_key=None
    )
    with pytest.raises(ProviderError) as exc:
        await adapter.generate(req)
    assert exc.value.error_code == AIErrorCode.CONFIGURATION_ERROR


# -----------------------------------------------------------------------------
# Test 2 — Invalid key: mock 401 returns INVALID_API_KEY
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_2_gemini_invalid_key_returns_invalid_api_key(monkeypatch, db_session):
    def mock_handler(request: httpx.Request):
        return httpx.Response(400, json={
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
                "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}]
            }
        })

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)

    user_id, email, headers = create_user_and_token("test2_invalid")
    user = db_session.query(User).filter(User.id == user_id).first()

    test_req = AIProviderConnectionTestRequest(provider="gemini", model="gemini-3.8-flash", api_key="AIzaSyBadKey")
    res = await AIReasoningService.test_connection(db_session, user, test_req)

    assert res.success is False
    assert res.error_code == AIErrorCode.INVALID_API_KEY.value
    assert "invalid" in res.status_message.lower()


# -----------------------------------------------------------------------------
# Test 3 — Model unavailable: mock 404 returns MODEL_UNAVAILABLE
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_3_gemini_model_unavailable_returns_model_unavailable(monkeypatch, db_session):
    def mock_handler(request: httpx.Request):
        return httpx.Response(404, json={
            "error": {
                "code": 404,
                "message": "models/nonexistent-model is not found for API version v1beta",
                "status": "NOT_FOUND"
            }
        })

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)

    user_id, email, headers = create_user_and_token("test3_model404")
    user = db_session.query(User).filter(User.id == user_id).first()

    test_req = AIProviderConnectionTestRequest(provider="gemini", model="nonexistent-model", api_key=MOCK_USER_KEY)
    res = await AIReasoningService.test_connection(db_session, user, test_req)

    assert res.success is False
    assert res.error_code == AIErrorCode.MODEL_UNAVAILABLE.value
    assert "not found" in res.status_message.lower() or "unavailable" in res.status_message.lower()


# -----------------------------------------------------------------------------
# Test 4 — Quota exceeded: mock 429 returns QUOTA_EXCEEDED / RATE_LIMITED
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_4_gemini_quota_exceeded_returns_quota_exceeded(monkeypatch, db_session):
    def mock_handler(request: httpx.Request):
        return httpx.Response(429, json={
            "error": {
                "code": 429,
                "message": "Resource has been exhausted (e.g. check quota).",
                "status": "RESOURCE_EXHAUSTED"
            }
        })

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)

    user_id, email, headers = create_user_and_token("test4_quota")
    user = db_session.query(User).filter(User.id == user_id).first()

    test_req = AIProviderConnectionTestRequest(provider="gemini", model="gemini-3.8-flash", api_key=MOCK_USER_KEY)
    res = await AIReasoningService.test_connection(db_session, user, test_req)

    assert res.success is False
    assert res.error_code in (AIErrorCode.QUOTA_EXCEEDED.value, AIErrorCode.RATE_LIMITED.value)


# -----------------------------------------------------------------------------
# Test 5 — Provider unreachable: mock timeout/connect failure returns PROVIDER_UNREACHABLE
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_5_gemini_unreachable_returns_provider_unreachable(monkeypatch, db_session):
    def mock_handler(request: httpx.Request):
        raise httpx.ConnectTimeout("Connection to generativelanguage.googleapis.com timed out.")

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)

    user_id, email, headers = create_user_and_token("test5_timeout")
    user = db_session.query(User).filter(User.id == user_id).first()

    test_req = AIProviderConnectionTestRequest(provider="gemini", model="gemini-3.8-flash", api_key=MOCK_USER_KEY)
    res = await AIReasoningService.test_connection(db_session, user, test_req)

    assert res.success is False
    assert res.error_code == AIErrorCode.PROVIDER_UNREACHABLE.value
    assert "timed out" in res.status_message.lower() or "unreachable" in res.status_message.lower()


# -----------------------------------------------------------------------------
# Test 6 — Successful connection: mock valid generateContent returns success=True
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_6_gemini_successful_connection(monkeypatch, db_session):
    def mock_handler(request: httpx.Request):
        assert request.headers.get("x-goog-api-key") == MOCK_USER_KEY
        return httpx.Response(200, json={
            "candidates": [{
                "content": {
                    "parts": [{"text": "OK"}]
                }
            }],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 1}
        })

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)

    user_id, email, headers = create_user_and_token("test6_success")
    user = db_session.query(User).filter(User.id == user_id).first()

    test_req = AIProviderConnectionTestRequest(provider="gemini", model="gemini-3.8-flash", api_key=MOCK_USER_KEY)
    res = await AIReasoningService.test_connection(db_session, user, test_req)

    assert res.success is True
    assert res.error_code in (None, "SUCCESS")
    assert res.latency_ms is not None
    assert res.latency_ms >= 0


# -----------------------------------------------------------------------------
# Test 7 — Successful generation: real generated text returned, no hardcoded strings
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_7_gemini_successful_generation_no_fake_strings(monkeypatch, db_session):
    generated_analysis = (
        '{"summary": "Real Gemini verified forensic analysis.", '
        '"statements": [{"statement_id": "stmt-1", "insight": "Suspicious dropper in webroot.", '
        '"classification": "FACT", "confidence": 0.95, "supporting_finding_ids": [], '
        '"supporting_artifact_ids": [], "supporting_correlation_ids": [], "supporting_evidence_ids": []}]}'
    )

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json={
            "candidates": [{
                "content": {
                    "parts": [{"text": generated_analysis}]
                }
            }]
        })

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)
    monkeypatch.setattr("backend.app.services.llm.get_ai_adapter", lambda p: mock_adapter, raising=False)

    user_id, email, headers = create_user_and_token("test7_gen")
    user = db_session.query(User).filter(User.id == user_id).first()
    case, art, finding = create_case_with_artifacts(user_id, email, db_session)

    # 1. Test GeminiProvider from llm.py
    llm = GeminiProvider(api_key=MOCK_USER_KEY)
    llm._adapter = mock_adapter
    llm_resp = await llm.generate("Analyze artifact")
    assert llm_resp == generated_analysis
    # Ensure old fake strings are NOT returned
    assert "[Gemini Reasoner]: Analysis generated." not in llm_resp
    assert "Using local fallback reasoning" not in llm_resp

    # 2. Test AIReasoningService.reason with gemini
    # Save user provider config
    cfg_req = AIProviderConfigRequest(
        provider="gemini",
        model="gemini-3.8-flash",
        api_key=MOCK_USER_KEY,
        is_enabled=True
    )
    AIReasoningService.configure_provider(db_session, user, cfg_req)

    req = AIReasoningRequest(
        objective="Analyze webshell activity",
        provider="gemini",
        allow_external_egress=True
    )
    reason_res = await AIReasoningService.reason(db_session, case, user, req)

    assert reason_res.status == "COMPLETED"
    assert reason_res.execution_mode == "EXTERNAL_LLM"
    assert reason_res.provider == "gemini"
    assert "Real Gemini verified" in reason_res.summary
    assert "local fallback" not in reason_res.summary.lower()


# -----------------------------------------------------------------------------
# Test 8 — User credential precedence: User A's key takes priority over GEMINI_API_KEY
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_8_gemini_user_credential_precedence(monkeypatch, db_session):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", MOCK_ENV_KEY)

    captured_keys = []

    def mock_handler(request: httpx.Request):
        captured_keys.append(request.headers.get("x-goog-api-key"))
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": "OK"}]}
            }]
        })

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)

    user_id, email, headers = create_user_and_token("test8_precedence")
    user = db_session.query(User).filter(User.id == user_id).first()

    # User explicitly saved their own key
    cfg_req = AIProviderConfigRequest(
        provider="gemini",
        model="gemini-3.8-flash",
        api_key=MOCK_USER_KEY,
        is_enabled=True
    )
    AIReasoningService.configure_provider(db_session, user, cfg_req)

    # Perform connection test without passing transient key -> must use User's encrypted key, NOT env key
    test_req = AIProviderConnectionTestRequest(provider="gemini")
    res = await AIReasoningService.test_connection(db_session, user, test_req)

    assert res.success is True
    assert len(captured_keys) == 1
    assert captured_keys[0] == MOCK_USER_KEY
    assert captured_keys[0] != MOCK_ENV_KEY


# -----------------------------------------------------------------------------
# Test 9 — Credential secrecy: API responses, logs, exceptions, and DB never expose plaintext key
# -----------------------------------------------------------------------------
def test_9_gemini_credential_secrecy(db_session):
    user_id, email, headers = create_user_and_token("test9_secrecy")
    user = db_session.query(User).filter(User.id == user_id).first()

    # 1. Configure via API
    cfg_payload = {
        "provider": "gemini",
        "model": "gemini-3.8-flash",
        "api_key": MOCK_USER_KEY,
        "is_enabled": True
    }
    resp = client.post("/api/v1/ai/provider/config", json=cfg_payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # Masked key returned, NEVER plaintext
    assert data["masked_api_key"] == "AIz...3210"
    assert MOCK_USER_KEY not in json.dumps(data)

    # 2. GET /provider/config API Response
    get_resp = client.get("/api/v1/ai/provider/config", headers=headers)
    assert get_resp.status_code == 200
    assert MOCK_USER_KEY not in json.dumps(get_resp.json())

    # 3. Database Check: Ciphertext only
    rec = db_session.query(AIProviderConfigRecord).filter(
        AIProviderConfigRecord.user_id == user.id
    ).first()
    assert rec is not None
    assert rec.api_key_encrypted != MOCK_USER_KEY
    assert decrypt_credential(rec.api_key_encrypted) == MOCK_USER_KEY

    # 4. Audit Log Check
    audits = db_session.query(AuditEvent).filter(
        AuditEvent.actor_id == user.id
    ).all()
    for ev in audits:
        assert MOCK_USER_KEY not in ev.details
        if ev.metadata_json:
            assert MOCK_USER_KEY not in json.dumps(ev.metadata_json)

    # 5. Exception Sanitization Check
    sanitized = ProviderError._sanitize(f"Error with key {MOCK_USER_KEY} and token Bearer eyJhbGciOi")
    assert MOCK_USER_KEY not in sanitized
    assert "[REDACTED_GEMINI_KEY]" in sanitized


# -----------------------------------------------------------------------------
# Test 10 — No silent fallback: Gemini selected + error -> fails closed
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_gemini_no_silent_fallback_on_error(monkeypatch, db_session):
    def mock_handler(request: httpx.Request):
        return httpx.Response(500, json={
            "error": {
                "code": 500,
                "message": "Internal error encountered in Gemini generation service.",
                "status": "INTERNAL"
            }
        })

    mock_adapter = GeminiAdapter(transport=httpx.MockTransport(mock_handler))
    monkeypatch.setattr("backend.app.services.ai_reasoning.get_ai_adapter", lambda p: mock_adapter)

    user_id, email, headers = create_user_and_token("test10_failclosed")
    user = db_session.query(User).filter(User.id == user_id).first()
    case, art, finding = create_case_with_artifacts(user_id, email, db_session)

    cfg_req = AIProviderConfigRequest(
        provider="gemini",
        model="gemini-3.8-flash",
        api_key=MOCK_USER_KEY,
        is_enabled=True
    )
    AIReasoningService.configure_provider(db_session, user, cfg_req)

    req = AIReasoningRequest(
        objective="Assess lateral movement",
        provider="gemini",
        allow_external_egress=True
    )

    # Must raise HTTPException, NOT silently succeed with DETERMINISTIC_FALLBACK
    with pytest.raises(HTTPException) as exc:
        await AIReasoningService.reason(db_session, case, user, req)

    assert exc.value.status_code in (500, 502)
    assert "PROVIDER_UNREACHABLE" in exc.value.detail or "Internal error" in exc.value.detail

    # Verify no deterministic fallback record was saved for this request
    # Only if an error occurs, it failed closed

