import pytest
import httpx
import re
import json

from backend.app.services.ai_provider import (
    ProviderId,
    ProviderRequest,
    ProviderResponse,
    ProviderError,
    AIErrorCode,
    OpenAIAdapter,
    AnthropicAdapter,
    GeminiAdapter,
    LocalOpenAIAdapter,
    get_ai_adapter,
    DEFAULT_TIMEOUT
)

MOCK_SECRET_KEY = "sk-proj-test1234567890secretkey12345"

# -----------------------------------------------------------------------------
# 1-4: OpenAI Adapter Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_1_openai_success():
    def handler(request: httpx.Request):
        assert request.headers["authorization"] == f"Bearer {MOCK_SECRET_KEY}"
        return httpx.Response(200, json={
            "id": "chatcmpl-123",
            "choices": [{"message": {"role": "assistant", "content": "OpenAI generated analysis"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        })

    adapter = OpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.OPENAI,
        model="gpt-4o-mini",
        prompt="Analyze memory dump",
        api_key=MOCK_SECRET_KEY
    )
    res = await adapter.generate(req)
    assert res.provider == ProviderId.OPENAI
    assert res.content == "OpenAI generated analysis"
    assert res.request_id == "chatcmpl-123"
    assert res.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

@pytest.mark.asyncio
async def test_2_openai_http_error():
    def handler(request: httpx.Request):
        return httpx.Response(401, json={"error": {"message": "Invalid API key provided"}})

    adapter = OpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.OPENAI,
        model="gpt-4o-mini",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.status_code == 401
    assert MOCK_SECRET_KEY not in str(exc_info.value)

@pytest.mark.asyncio
async def test_3_openai_timeout():
    def handler(request: httpx.Request):
        raise httpx.TimeoutException("Connection timed out")

    adapter = OpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.OPENAI,
        model="gpt-4o-mini",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "timed out" in str(exc_info.value).lower()
    assert MOCK_SECRET_KEY not in str(exc_info.value)

@pytest.mark.asyncio
async def test_4_openai_malformed_response():
    def handler(request: httpx.Request):
        return httpx.Response(200, text="NOT_VALID_JSON")

    adapter = OpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.OPENAI,
        model="gpt-4o-mini",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "malformed" in str(exc_info.value).lower()

# -----------------------------------------------------------------------------
# 5-8: Anthropic Adapter Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_5_anthropic_success():
    def handler(request: httpx.Request):
        assert request.headers["x-api-key"] == MOCK_SECRET_KEY
        return httpx.Response(200, json={
            "id": "msg_013Z95v5",
            "content": [{"type": "text", "text": "Claude generated analysis"}],
            "usage": {"input_tokens": 12, "output_tokens": 8}
        })

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        prompt="Analyze malware sample",
        api_key=MOCK_SECRET_KEY
    )
    res = await adapter.generate(req)
    assert res.provider == ProviderId.ANTHROPIC
    assert res.content == "Claude generated analysis"
    assert res.request_id == "msg_013Z95v5"

@pytest.mark.asyncio
async def test_6_anthropic_http_error():
    def handler(request: httpx.Request):
        return httpx.Response(403, json={"error": {"type": "authentication_error", "message": "invalid x-api-key"}})

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.status_code == 403
    assert MOCK_SECRET_KEY not in str(exc_info.value)

@pytest.mark.asyncio
async def test_7_anthropic_timeout():
    def handler(request: httpx.Request):
        raise httpx.TimeoutException("Read timeout")

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "timed out" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_8_anthropic_malformed_response():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"content": []}) # missing text block

    adapter = AnthropicAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.ANTHROPIC,
        model="claude-3-5-sonnet-20241022",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "malformed" in str(exc_info.value).lower()

# -----------------------------------------------------------------------------
# 9-12: Gemini Adapter Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_9_gemini_success():
    def handler(request: httpx.Request):
        assert request.headers["x-goog-api-key"] == MOCK_SECRET_KEY
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": "Gemini generated analysis"}]}
            }],
            "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 4}
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Analyze EVTX logs",
        api_key=MOCK_SECRET_KEY
    )
    res = await adapter.generate(req)
    assert res.provider == ProviderId.GEMINI
    assert res.content == "Gemini generated analysis"

@pytest.mark.asyncio
async def test_10_gemini_http_error():
    def handler(request: httpx.Request):
        return httpx.Response(400, json={"error": {"code": 400, "message": "API key not valid."}})

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.status_code == 400
    assert MOCK_SECRET_KEY not in str(exc_info.value)

@pytest.mark.asyncio
async def test_11_gemini_timeout():
    def handler(request: httpx.Request):
        raise httpx.TimeoutException("Gemini server timeout")

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "timed out" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_12_gemini_malformed_response():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"candidates": []}) # missing candidates

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "malformed" in str(exc_info.value).lower()

# -----------------------------------------------------------------------------
# 13-15: Local OpenAI-Compatible Tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_13_local_openai_success():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={
            "id": "ollama-123",
            "choices": [{"message": {"role": "assistant", "content": "Ollama local analysis"}}]
        })

    adapter = LocalOpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.LOCAL_OPENAI,
        model="llama3",
        prompt="Local analysis prompt",
        base_url="http://localhost:11434/v1"
    )
    res = await adapter.generate(req)
    assert res.provider == ProviderId.LOCAL_OPENAI
    assert res.content == "Ollama local analysis"

@pytest.mark.asyncio
async def test_14_local_http_error():
    def handler(request: httpx.Request):
        return httpx.Response(500, text="Internal Server Error")

    adapter = LocalOpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.LOCAL_OPENAI,
        model="llama3",
        prompt="Analyze",
        base_url="http://localhost:11434/v1"
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.status_code == 500

@pytest.mark.asyncio
async def test_15_local_malformed_response():
    def handler(request: httpx.Request):
        return httpx.Response(200, text="INVALID_JSON")

    adapter = LocalOpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.LOCAL_OPENAI,
        model="llama3",
        prompt="Analyze",
        base_url="http://localhost:11434/v1"
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "malformed" in str(exc_info.value).lower()

# -----------------------------------------------------------------------------
# 16-22: General Security & Architecture Tests
# -----------------------------------------------------------------------------

def test_16_invalid_provider_configuration():
    with pytest.raises(ProviderError) as exc_info:
        get_ai_adapter("invalid_provider_name")
    assert "not a supported" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_17_api_key_never_appears_in_normalized_response():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={
            "id": "chatcmpl-1",
            "choices": [{"message": {"role": "assistant", "content": "Analysis content"}}]
        })

    adapter = OpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.OPENAI,
        model="gpt-4o-mini",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY
    )
    res = await adapter.generate(req)
    res_json = res.model_dump_json()
    assert MOCK_SECRET_KEY not in res_json

@pytest.mark.asyncio
async def test_18_api_key_never_appears_in_normalized_exception():
    err = ProviderError(ProviderId.OPENAI, f"Failed request with Authorization: Bearer {MOCK_SECRET_KEY}")
    assert MOCK_SECRET_KEY not in str(err)
    assert MOCK_SECRET_KEY not in err.message
    assert "[REDACTED]" in str(err)

@pytest.mark.asyncio
async def test_19_api_key_never_appears_in_logging_or_str(capsys):
    err = ProviderError(ProviderId.OPENAI, f"Header x-api-key: {MOCK_SECRET_KEY} failed")
    print(f"Logged Exception: {err}")
    captured = capsys.readouterr()
    assert MOCK_SECRET_KEY not in captured.out
    assert "[REDACTED]" in captured.out

@pytest.mark.asyncio
async def test_20_https_enforcement_for_external_providers():
    adapter = OpenAIAdapter()
    req = ProviderRequest(
        provider=ProviderId.OPENAI,
        model="gpt-4o-mini",
        prompt="Analyze",
        api_key=MOCK_SECRET_KEY,
        base_url="http://insecure-cloud-endpoint.com/v1" # Insecure HTTP
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert "requires https" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_21_explicitly_permitted_local_http_behavior():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    adapter = LocalOpenAIAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.LOCAL_OPENAI,
        model="llama3",
        prompt="Analyze",
        base_url="http://localhost:11434/v1" # Local HTTP is explicitly permitted
    )
    res = await adapter.generate(req)
    assert res.content == "OK"

def test_22_timeout_values_are_bounded():
    assert DEFAULT_TIMEOUT.connect == 5.0
    assert DEFAULT_TIMEOUT.read == 15.0
    assert DEFAULT_TIMEOUT.write == 5.0


@pytest.mark.asyncio
async def test_23_gemini_model_mapping_and_test_connection():
    called_urls = []
    def handler(request: httpx.Request):
        called_urls.append(str(request.url))
        assert request.headers["x-goog-api-key"] == MOCK_SECRET_KEY
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "pong"}]}}]
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    # Test connection preserves selected model name without artificial downgrade
    res = await adapter.test_connection(api_key=MOCK_SECRET_KEY, model="gemini-3.5-flash-lite")
    assert res.success is True
    assert "gemini-3.5-flash-lite" in res.status_message
    assert any("models/gemini-3.5-flash-lite:generateContent" in u for u in called_urls)
    assert res.error_code == AIErrorCode.SUCCESS


@pytest.mark.asyncio
async def test_24_gemini_error_categorization():
    # 404 Model Unavailable
    def handler_404(request: httpx.Request):
        return httpx.Response(404, json={"error": {"code": 404, "message": "models/gemini-not-found is not found for generateContent"}})

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler_404))
    res = await adapter.test_connection(api_key=MOCK_SECRET_KEY, model="gemini-not-found")
    assert res.success is False
    assert res.error_code == AIErrorCode.MODEL_UNAVAILABLE
    assert "[MODEL_UNAVAILABLE]" in res.status_message

    # 429 Quota Exceeded
    def handler_429(request: httpx.Request):
        return httpx.Response(429, json={"error": {"code": 429, "message": "Resource exhausted: quota exceeded"}})

    adapter_quota = GeminiAdapter(transport=httpx.MockTransport(handler_429))
    res_quota = await adapter_quota.test_connection(api_key=MOCK_SECRET_KEY, model="gemini-3.8-flash")
    assert res_quota.success is False
    assert res_quota.error_code == AIErrorCode.QUOTA_EXCEEDED
    assert "[QUOTA_EXCEEDED]" in res_quota.status_message

    # Missing Key -> Configuration Error
    res_nokey = await adapter.test_connection(api_key=None)
    assert res_nokey.success is False
    assert res_nokey.error_code == AIErrorCode.CONFIGURATION_ERROR
    assert "[CONFIGURATION_ERROR]" in res_nokey.status_message


@pytest.mark.asyncio
async def test_25_gemini_list_models_success():
    def handler(request: httpx.Request):
        assert request.headers["x-goog-api-key"] == MOCK_SECRET_KEY
        return httpx.Response(200, json={
            "models": [
                {
                    "name": "models/gemini-3.8-flash",
                    "supportedGenerationMethods": ["generateContent"]
                },
                {
                    "name": "models/gemini-3.5-flash-lite",
                    "supportedGenerationMethods": ["generateContent"]
                },
                {
                    "name": "models/text-embedding-004",
                    "supportedGenerationMethods": ["embedContent"]
                }
            ]
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    models = await adapter.list_models(api_key=MOCK_SECRET_KEY)
    assert "gemini-3.8-flash" in models
    assert "gemini-3.5-flash-lite" in models
    assert "text-embedding-004" not in models


@pytest.mark.asyncio
async def test_26_gemini_list_models_auth_failure():
    def handler(request: httpx.Request):
        return httpx.Response(400, json={"error": {"message": "API_KEY_INVALID"}})

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as exc_info:
        await adapter.list_models(api_key="bad-key")
    assert exc_info.value.error_code == AIErrorCode.INVALID_API_KEY
    assert "[INVALID_API_KEY]" in exc_info.value.message


@pytest.mark.asyncio
async def test_27_gemini_generate_success():
    def handler(request: httpx.Request):
        assert request.headers["x-goog-api-key"] == MOCK_SECRET_KEY
        return httpx.Response(200, json={
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Ground truth forensic analysis of disk artifact."}],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 25,
                "candidatesTokenCount": 15,
                "totalTokenCount": 40
            }
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Explain finding evidence.",
        api_key=MOCK_SECRET_KEY
    )
    res = await adapter.generate(req)
    assert res.provider == ProviderId.GEMINI
    assert res.model == "gemini-3.8-flash"
    assert "Ground truth forensic analysis" in res.content
    assert res.usage["prompt_tokens"] == 25
    assert res.usage["completion_tokens"] == 15
    assert res.usage["total_tokens"] == 40


@pytest.mark.asyncio
async def test_28_gemini_generate_missing_key():
    adapter = GeminiAdapter()
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Explain finding evidence.",
        api_key=None
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.error_code == AIErrorCode.CONFIGURATION_ERROR
    assert "[CONFIGURATION_ERROR]" in exc_info.value.message


@pytest.mark.asyncio
async def test_29_gemini_rate_limit_handling():
    def handler(request: httpx.Request):
        return httpx.Response(429, json={"error": {"message": "Too Many Requests, please back off"}})

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    res = await adapter.test_connection(api_key=MOCK_SECRET_KEY, model="gemini-3.8-flash")
    assert res.success is False
    assert res.error_code == AIErrorCode.RATE_LIMITED
    assert "[RATE_LIMITED]" in res.status_message


@pytest.mark.asyncio
async def test_30_gemini_no_fake_ai_fallback():
    def handler(request: httpx.Request):
        return httpx.Response(500, json={"error": {"message": "Internal error"}})

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Investigate memory image.",
        api_key=MOCK_SECRET_KEY
    )
    with pytest.raises(ProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.error_code == AIErrorCode.PROVIDER_UNREACHABLE
    assert "Internal error" in exc_info.value.message


def test_31_no_hardcoded_secrets_in_repo():
    from backend.app.core.config import Settings
    s = Settings()
    # Ensure default is empty string or None, not a real key
    assert not s.GEMINI_API_KEY or s.GEMINI_API_KEY == "" or not s.GEMINI_API_KEY.startswith("AIzaSy")


def test_32_gemini_normalization_helpers():
    assert GeminiAdapter._normalize_model("models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiAdapter._normalize_model("/models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiAdapter._normalize_model("models//models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiAdapter._normalize_model("default") == "gemini-3.8-flash"
    assert GeminiAdapter._normalize_model("") == "gemini-3.8-flash"
    assert GeminiAdapter._normalize_model(None) == "gemini-3.8-flash"
    assert GeminiAdapter._normalize_model("gemini-3.5-flash-lite") == "gemini-3.5-flash-lite"
    assert GeminiAdapter._normalize_model("custom-model-id") == "custom-model-id"

    assert GeminiAdapter._normalize_base_url("https://generativelanguage.googleapis.com") == "https://generativelanguage.googleapis.com/v1beta"
    assert GeminiAdapter._normalize_base_url("https://generativelanguage.googleapis.com/") == "https://generativelanguage.googleapis.com/v1beta"
    assert GeminiAdapter._normalize_base_url("https://generativelanguage.googleapis.com/v1beta") == "https://generativelanguage.googleapis.com/v1beta"
    assert GeminiAdapter._normalize_base_url("https://generativelanguage.googleapis.com/v1beta/") == "https://generativelanguage.googleapis.com/v1beta"
    assert GeminiAdapter._normalize_base_url("https://generativelanguage.googleapis.com/v1beta/models") == "https://generativelanguage.googleapis.com/v1beta"


def test_33_gemini_error_categorization_nuances():
    # Model unavailable 404 (Google model not found format)
    res_404_model = GeminiAdapter._categorize_http_status(
        404,
        json.dumps({"error": {"code": 404, "message": "models/gemini-not-found is not found for API version v1beta"}})
    )
    assert res_404_model == AIErrorCode.MODEL_UNAVAILABLE

    # Generic route 404 must NOT be classified as MODEL_UNAVAILABLE
    res_404_generic = GeminiAdapter._categorize_http_status(
        404,
        "<!DOCTYPE html><html><body>404 Not Found</body></html>"
    )
    assert res_404_generic == AIErrorCode.CONFIGURATION_ERROR

    # 400 with API key invalid
    res_400_key = GeminiAdapter._categorize_http_status(
        400,
        json.dumps({"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}})
    )
    assert res_400_key == AIErrorCode.INVALID_API_KEY

    # 403 unregistered callers
    res_403_unreg = GeminiAdapter._categorize_http_status(
        403,
        json.dumps({"error": {"code": 403, "message": "Method doesn't allow unregistered callers. Please use API Key.", "status": "PERMISSION_DENIED"}})
    )
    assert res_403_unreg == AIErrorCode.INVALID_API_KEY


@pytest.mark.asyncio
async def test_34_gemini_list_models_no_key_returns_supported_models():
    adapter = GeminiAdapter()
    models = await adapter.list_models(api_key=None)
    assert isinstance(models, list)
    assert "gemini-3.8-flash" in models
    assert "gemini-3.5-flash-lite" in models
    assert "gemini-3.7-flash" in models
    assert "gemini-3.6-flash" in models
    assert "gemini-3.5-flash" in models
    assert len(models) == 5


# -----------------------------------------------------------------------------
# Section 26: Required Gemini Production Tests (Tests A through N)
# -----------------------------------------------------------------------------

def test_a_gemini_default_model():
    assert GeminiAdapter.DEFAULT_MODEL == "gemini-3.8-flash"


def test_b_gemini_config_default():
    from backend.app.core.config import settings
    assert settings.GEMINI_MODEL == "gemini-3.8-flash"


def test_c_model_normalization():
    assert GeminiAdapter._normalize_model("models/gemini-3.8-flash") == "gemini-3.8-flash"
    assert GeminiAdapter._normalize_model("gemini-3.8-flash") == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_d_and_e_model_discovery_and_filtering():
    def handler(request: httpx.Request):
        assert request.headers["x-goog-api-key"] == MOCK_SECRET_KEY
        return httpx.Response(200, json={
            "models": [
                {
                    "name": "models/gemini-3.8-flash",
                    "supportedGenerationMethods": ["generateContent"]
                },
                {
                    "name": "models/some-embedding-model",
                    "supportedGenerationMethods": ["embedContent"]
                }
            ]
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    models = await adapter.list_models(api_key=MOCK_SECRET_KEY)
    assert models == ["gemini-3.8-flash"]
    assert "some-embedding-model" not in models


@pytest.mark.asyncio
async def test_f_discovery_failure():
    for status_code in (401, 403, 404, 500):
        def handler(request: httpx.Request):
            return httpx.Response(status_code, json={"error": {"code": status_code, "message": "Discovery failed"}})

        adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
        with pytest.raises(ProviderError) as exc_info:
            await adapter.list_models(api_key=MOCK_SECRET_KEY)
        assert exc_info.value.status_code == status_code
        # Critical invariant: must NOT return stale models
        assert "gemini-2.5-flash" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_g_real_generation_request_shape():
    captured_requests = []
    def handler(request: httpx.Request):
        captured_requests.append(request)
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": "OK"}]}
            }]
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Test shape",
        api_key=MOCK_SECRET_KEY
    )
    res = await adapter.generate(req)
    assert res.content == "OK"
    assert len(captured_requests) == 1
    req_url = str(captured_requests[0].url)
    assert "/models/gemini-3.8-flash:generateContent" in req_url


@pytest.mark.asyncio
async def test_h_unavailable_model():
    def handler(request: httpx.Request):
        return httpx.Response(404, json={
            "error": {
                "code": 404,
                "message": "models/nonexistent is not found for generateContent"
            }
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    res = await adapter.test_connection(api_key=MOCK_SECRET_KEY, model="nonexistent")
    assert res.success is False
    assert res.error_code == AIErrorCode.MODEL_UNAVAILABLE
    assert "[MODEL_UNAVAILABLE]" in res.status_message


def test_i_api_key_security():
    secret_key = "AIzaSySecretProductionKey1234567890"
    sanitized = ProviderError._sanitize(f"Error occurred with key {secret_key}")
    assert secret_key not in sanitized
    assert "[REDACTED_GEMINI_KEY]" in sanitized


@pytest.mark.asyncio
async def test_j_malformed_gemini_response():
    # 1. 200 OK with missing candidates in test_connection
    def handler_missing(request: httpx.Request):
        return httpx.Response(200, json={"candidates": []})

    adapter_missing = GeminiAdapter(transport=httpx.MockTransport(handler_missing))
    res_missing = await adapter_missing.test_connection(api_key=MOCK_SECRET_KEY, model="gemini-3.8-flash")
    assert res_missing.success is False
    assert res_missing.error_code == AIErrorCode.GENERATION_FAILED

    # 2. 200 OK with non-JSON in test_connection
    def handler_non_json(request: httpx.Request):
        return httpx.Response(200, text="<HTML>Bad Gateway</HTML>")

    adapter_non_json = GeminiAdapter(transport=httpx.MockTransport(handler_non_json))
    res_non_json = await adapter_non_json.test_connection(api_key=MOCK_SECRET_KEY, model="gemini-3.8-flash")
    assert res_non_json.success is False
    assert res_non_json.error_code == AIErrorCode.GENERATION_FAILED


@pytest.mark.asyncio
async def test_k_gemini_system_instruction():
    captured_payloads = []
    def handler(request: httpx.Request):
        captured_payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={
            "candidates": [{
                "content": {"parts": [{"text": "Forensic findings verified."}]}
            }]
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    req = ProviderRequest(
        provider=ProviderId.GEMINI,
        model="gemini-3.8-flash",
        prompt="Examine memory dump artifact.",
        system_prompt="You are a certified DFIR investigator adhering to ISO/IEC 27037.",
        api_key=MOCK_SECRET_KEY
    )
    res = await adapter.generate(req)
    assert res.content == "Forensic findings verified."
    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert "systemInstruction" in payload
    assert payload["systemInstruction"]["parts"][0]["text"] == "You are a certified DFIR investigator adhering to ISO/IEC 27037."


@pytest.mark.asyncio
async def test_l_gemini_pagination():
    pages_requested = []
    def handler(request: httpx.Request):
        url = str(request.url)
        pages_requested.append(url)
        if "pageToken=page2_token" in url:
            return httpx.Response(200, json={
                "models": [
                    {
                        "name": "models/gemini-3.5-flash-lite",
                        "supportedGenerationMethods": ["generateContent"]
                    }
                ]
            })
        else:
            return httpx.Response(200, json={
                "models": [
                    {
                        "name": "models/gemini-3.8-flash",
                        "supportedGenerationMethods": ["generateContent"]
                    }
                ],
                "nextPageToken": "page2_token"
            })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    models = await adapter.list_models(api_key=MOCK_SECRET_KEY)
    assert "gemini-3.8-flash" in models
    assert "gemini-3.5-flash-lite" in models
    assert len(pages_requested) == 2


@pytest.mark.asyncio
async def test_m_gemini_non_text_modality_filtering():
    def handler(request: httpx.Request):
        return httpx.Response(200, json={
            "models": [
                {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-live-2.5", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-tts-1.0", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/imagen-3-image-generation", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/chirp-transcribe-v2", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-custom-tuning", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-005", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/aqa-model", "supportedGenerationMethods": ["generateContent"]},
            ]
        })

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    models = await adapter.list_models(api_key=MOCK_SECRET_KEY)
    assert models == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    assert "gemini-live-2.5" not in models
    assert "gemini-tts-1.0" not in models
    assert "imagen-3-image-generation" not in models
    assert "chirp-transcribe-v2" not in models
    assert "gemini-custom-tuning" not in models
    assert "text-embedding-005" not in models
    assert "aqa-model" not in models



