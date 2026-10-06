from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional
import json
import logging
import re
import time
from pydantic import BaseModel, Field, ConfigDict
import httpx

from backend.app.core.config import settings

logger = logging.getLogger("ADFIR_AI_PROVIDER")

DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0, read=15.0, write=5.0)


class ProviderId(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    LOCAL_OPENAI = "local_openai"
    LOCAL_STUB = "local_stub"


class AIErrorCode(str, Enum):
    SUCCESS = "SUCCESS"
    INVALID_API_KEY = "INVALID_API_KEY"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    PROVIDER_UNREACHABLE = "PROVIDER_UNREACHABLE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    GENERATION_FAILED = "GENERATION_FAILED"


class ConnectionTestResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: ProviderId
    success: bool
    status_message: str
    error_code: Optional[AIErrorCode] = None
    latency_ms: Optional[float] = None
    has_key: bool = False


class ProviderRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: ProviderId
    model: str
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 1000
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: ProviderId
    model: str
    content: str
    request_id: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


class ProviderError(Exception):
    """
    Sanitized provider exception.
    Guarantees API keys and Authorization headers are NEVER exposed in error message or str representation.
    """
    def __init__(
        self,
        provider: ProviderId,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[AIErrorCode] = None
    ):
        sanitized_msg = self._sanitize(message)
        super().__init__(sanitized_msg)
        self.provider = provider
        self.message = sanitized_msg
        self.status_code = status_code
        self.error_code = error_code or AIErrorCode.GENERATION_FAILED

    @staticmethod
    def _sanitize(text: str) -> str:
        if not text:
            return "Unknown provider error"
        sanitized = text
        sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'x-api-key["\']?\s*[:=]\s*["\']?[A-Za-z0-9_\-\.]+', 'x-api-key: [REDACTED]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'x-goog-api-key["\']?\s*[:=]\s*["\']?[A-Za-z0-9_\-\.]+', 'x-goog-api-key: [REDACTED]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'key=[A-Za-z0-9_\-\.]{10,}', 'key=[REDACTED]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'AIza[A-Za-z0-9_\-]{20,}', '[REDACTED_GEMINI_KEY]', sanitized)
        sanitized = re.sub(r'sk-[A-Za-z0-9_-]{8,}', 'sk-[REDACTED]', sanitized)
        return sanitized


class BaseAIAdapter(ABC):
    def __init__(
        self,
        provider_id: ProviderId,
        default_model: str,
        transport: Optional[httpx.AsyncBaseTransport] = None
    ):
        self.provider_id = provider_id
        self.default_model = default_model
        self.transport = transport

    def _get_client(self, timeout: Optional[httpx.Timeout] = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=self.transport,
            timeout=timeout or DEFAULT_TIMEOUT
        )

    def _validate_https_url(self, url: str, is_local: bool = False):
        url_clean = url.lower().strip()
        if not is_local and url_clean.startswith("http://"):
            raise ProviderError(
                self.provider_id,
                f"Security Policy Error: External provider '{self.provider_id.value}' requires HTTPS. HTTP is prohibited for cloud endpoints."
            )

    @abstractmethod
    async def test_connection(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> ConnectionTestResult:
        pass

    @abstractmethod
    async def generate(self, req: ProviderRequest) -> ProviderResponse:
        pass

    async def list_models(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> List[str]:
        return [self.default_model]


class OpenAIAdapter(BaseAIAdapter):
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        super().__init__(ProviderId.OPENAI, self.DEFAULT_MODEL, transport)

    async def test_connection(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> ConnectionTestResult:
        if not api_key:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message="API key is required for OpenAI provider connection test.",
                has_key=False
            )
        target_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._validate_https_url(target_url, is_local=False)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        start_time = time.time()
        try:
            async with self._get_client() as client:
                res = await client.get(f"{target_url}/models", headers=headers)
                latency = round((time.time() - start_time) * 1000, 2)

                if res.status_code == 200:
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=True,
                        status_message="OpenAI API connection verified successfully.",
                        latency_ms=latency,
                        has_key=True
                    )
                else:
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=False,
                        status_message=f"OpenAI API returned HTTP {res.status_code}",
                        latency_ms=latency,
                        has_key=True
                    )
        except httpx.TimeoutException:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message="Connection timed out connecting to OpenAI API.",
                has_key=True
            )
        except Exception as e:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message=ProviderError._sanitize(str(e)),
                has_key=True
            )

    async def generate(self, req: ProviderRequest) -> ProviderResponse:
        if not req.api_key:
            raise ProviderError(self.provider_id, "API key is required for OpenAI provider generation.")

        target_url = (req.base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._validate_https_url(target_url, is_local=False)

        headers = {
            "Authorization": f"Bearer {req.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})

        payload = {
            "model": req.model or self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens
        }

        try:
            async with self._get_client() as client:
                res = await client.post(f"{target_url}/chat/completions", headers=headers, json=payload)
                if res.status_code != 200:
                    raise ProviderError(
                        self.provider_id,
                        f"OpenAI API error HTTP {res.status_code}: {res.text}",
                        status_code=res.status_code
                    )

                data = res.json()
                if "choices" not in data or not data["choices"]:
                    raise ProviderError(self.provider_id, "OpenAI API returned malformed response: missing choices.")

                choice = data["choices"][0]
                content = choice.get("message", {}).get("content", "")
                if content is None:
                    content = ""

                usage = data.get("usage", {})
                req_id = data.get("id")

                return ProviderResponse(
                    provider=self.provider_id,
                    model=req.model or self.DEFAULT_MODEL,
                    content=content,
                    request_id=req_id,
                    usage=usage if isinstance(usage, dict) else None
                )

        except httpx.TimeoutException:
            raise ProviderError(self.provider_id, "OpenAI API request timed out.")
        except json.JSONDecodeError:
            raise ProviderError(self.provider_id, "OpenAI API returned malformed non-JSON response.")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(self.provider_id, f"OpenAI API execution error: {str(e)}")


class AnthropicAdapter(BaseAIAdapter):
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        super().__init__(ProviderId.ANTHROPIC, self.DEFAULT_MODEL, transport)

    async def test_connection(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> ConnectionTestResult:
        if not api_key:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message="API key is required for Anthropic provider connection test.",
                has_key=False
            )
        target_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._validate_https_url(target_url, is_local=False)

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        start_time = time.time()
        try:
            async with self._get_client() as client:
                res = await client.post(
                    f"{target_url}/messages",
                    headers=headers,
                    json={
                        "model": self.DEFAULT_MODEL,
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "ping"}]
                    }
                )
                latency = round((time.time() - start_time) * 1000, 2)

                if res.status_code in (200, 400): # 200 OK or 400 with valid key structure
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=res.status_code == 200,
                        status_message="Anthropic API connection verified successfully." if res.status_code == 200 else f"Anthropic API returned HTTP {res.status_code}",
                        latency_ms=latency,
                        has_key=True
                    )
                else:
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=False,
                        status_message=f"Anthropic API returned HTTP {res.status_code}",
                        latency_ms=latency,
                        has_key=True
                    )
        except httpx.TimeoutException:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message="Connection timed out connecting to Anthropic API.",
                has_key=True
            )
        except Exception as e:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message=ProviderError._sanitize(str(e)),
                has_key=True
            )

    async def generate(self, req: ProviderRequest) -> ProviderResponse:
        if not req.api_key:
            raise ProviderError(self.provider_id, "API key is required for Anthropic provider generation.")

        target_url = (req.base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._validate_https_url(target_url, is_local=False)

        headers = {
            "x-api-key": req.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": req.model or self.DEFAULT_MODEL,
            "max_tokens": req.max_tokens,
            "messages": [{"role": "user", "content": req.prompt}]
        }
        if req.system_prompt:
            payload["system"] = req.system_prompt

        try:
            async with self._get_client() as client:
                res = await client.post(f"{target_url}/messages", headers=headers, json=payload)
                if res.status_code != 200:
                    raise ProviderError(
                        self.provider_id,
                        f"Anthropic API error HTTP {res.status_code}: {res.text}",
                        status_code=res.status_code
                    )

                data = res.json()
                if "content" not in data or not isinstance(data["content"], list) or not data["content"]:
                    raise ProviderError(self.provider_id, "Anthropic API returned malformed response: missing content block.")

                text_content = ""
                for block in data["content"]:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_content += block.get("text", "")

                req_id = data.get("id")
                usage = data.get("usage", {})

                return ProviderResponse(
                    provider=self.provider_id,
                    model=req.model or self.DEFAULT_MODEL,
                    content=text_content,
                    request_id=req_id,
                    usage=usage if isinstance(usage, dict) else None
                )

        except httpx.TimeoutException:
            raise ProviderError(self.provider_id, "Anthropic API request timed out.")
        except json.JSONDecodeError:
            raise ProviderError(self.provider_id, "Anthropic API returned malformed non-JSON response.")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(self.provider_id, f"Anthropic API execution error: {str(e)}")


class GeminiAdapter(BaseAIAdapter):
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-2.5-flash"
    SUPPORTED_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        default_model = getattr(settings, "GEMINI_MODEL", self.DEFAULT_MODEL) or self.DEFAULT_MODEL
        super().__init__(ProviderId.GEMINI, default_model, transport)

    @classmethod
    def _normalize_base_url(cls, base_url: Optional[str]) -> str:
        url = (base_url or cls.DEFAULT_BASE_URL).strip().rstrip("/")
        if url.endswith("/models"):
            url = url[:-7].rstrip("/")
        if url in (
            "https://generativelanguage.googleapis.com",
            "http://generativelanguage.googleapis.com",
        ):
            url = f"{url}/v1beta"
        return url

    @classmethod
    def _normalize_model(cls, model_name: Optional[str]) -> str:
        fallback = getattr(settings, "GEMINI_MODEL", cls.DEFAULT_MODEL) or cls.DEFAULT_MODEL
        name = (model_name or "").strip()
        if not name or name.lower() == "default":
            name = fallback.strip()
        name = name.lstrip("/")
        while name.startswith("models/"):
            name = name[7:].lstrip("/")
        return name or fallback

    @classmethod
    def _categorize_http_status(cls, status_code: int, response_text: str = "") -> AIErrorCode:
        text_lower = response_text.lower()
        error_msg = ""
        error_status = ""
        error_reason = ""
        try:
            parsed = json.loads(response_text)
            err = parsed.get("error", {})
            if isinstance(err, dict):
                error_msg = str(err.get("message", "")).lower()
                error_status = str(err.get("status", "")).lower()
                details = err.get("details", [])
                if isinstance(details, list):
                    for d in details:
                        if isinstance(d, dict) and "reason" in d:
                            error_reason = str(d.get("reason", "")).lower()
        except Exception:
            pass

        combined_text = f"{text_lower} {error_msg} {error_status} {error_reason}"

        # 1. Quota & Rate Limit
        if (
            status_code == 429
            or error_reason in ("resource_exhausted", "quota_exceeded", "rate_limit_exceeded")
            or "resource_exhausted" in combined_text
            or "resourceexhausted" in combined_text
            or "quota" in combined_text
            or "billing" in combined_text
        ):
            if "quota" in combined_text or "billing" in combined_text or "resource_exhausted" in combined_text:
                return AIErrorCode.QUOTA_EXCEEDED
            return AIErrorCode.RATE_LIMITED

        # 2. Authentication & API Key
        if (
            status_code in (401, 403)
            or error_reason in ("api_key_invalid", "api_key_not_found", "key_invalid")
            or "api_key_invalid" in combined_text
            or "api key not valid" in combined_text
            or "unregistered callers" in combined_text
            or "api key not found" in combined_text
            or "unauthenticated" in combined_text
            or "permission_denied" in combined_text
            or "permissiondenied" in combined_text
        ):
            return AIErrorCode.INVALID_API_KEY

        if status_code == 400 and (
            "api_key" in combined_text
            or "api key" in combined_text
            or "credential" in combined_text
            or "invalid api key" in combined_text
            or "key not valid" in combined_text
        ):
            return AIErrorCode.INVALID_API_KEY

        # 3. Model Availability
        # A 404 indicates model unavailable ONLY if Google specifically states that the model was not found
        # or not supported for generateContent.
        is_model_specific_404 = (
            status_code == 404
            and (
                "models/" in error_msg
                or "model" in error_msg
                or "is not supported for generatecontent" in combined_text
                or "not found for api version" in combined_text
            )
        )
        is_model_specific_error = (
            "is not supported for generatecontent" in combined_text
            or ("model" in error_msg and ("not found" in error_msg or "not supported" in error_msg or "unknown model" in error_msg))
        )
        if is_model_specific_404 or is_model_specific_error:
            return AIErrorCode.MODEL_UNAVAILABLE

        # 4. Provider / Server Unreachable
        if status_code in (500, 502, 503, 504):
            return AIErrorCode.PROVIDER_UNREACHABLE

        # 5. Configuration Error (e.g. general 400, or route 404 that was not a model error)
        return AIErrorCode.CONFIGURATION_ERROR

    @staticmethod
    def _extract_error_detail(response_text: str) -> str:
        if not response_text:
            return "No response received from Google Gemini API."
        try:
            data = json.loads(response_text)
            err = data.get("error", {})
            if isinstance(err, dict):
                msg = err.get("message")
                status_str = err.get("status")
                details = err.get("details", [])
                reasons = []
                if isinstance(details, list):
                    for d in details:
                        if isinstance(d, dict) and "reason" in d:
                            reasons.append(str(d["reason"]))
                parts = []
                if msg and isinstance(msg, str):
                    parts.append(msg.strip())
                if status_str and isinstance(status_str, str) and status_str != msg:
                    parts.append(f"[{status_str}]")
                if reasons:
                    parts.append(f"Reason: {', '.join(reasons)}")
                if parts:
                    return " ".join(parts)
        except Exception:
            pass
        clean = ProviderError._sanitize(response_text).strip()
        return clean[:300] if len(clean) > 300 else clean

    async def list_models(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> List[str]:
        effective_key = api_key or (settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else None)

        if not effective_key:
            # Without a configured API key, return the documented supported models.
            return list(self.SUPPORTED_MODELS)

        target_url = self._normalize_base_url(base_url)
        self._validate_https_url(target_url, is_local=False)
        headers = {"x-goog-api-key": effective_key.strip()}

        try:
            async with self._get_client() as client:
                res = await client.get(f"{target_url}/models", headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    models_raw = data.get("models", [])
                    discovered = []
                    for m in models_raw:
                        methods = m.get("supportedGenerationMethods", [])
                        if "generateContent" in methods:
                            clean_name = m.get("name", "")
                            while clean_name.startswith("models/"):
                                clean_name = clean_name[7:].lstrip("/")
                            if (
                                clean_name
                                and not clean_name.endswith("-tuning")
                                and not clean_name.startswith("text-embedding")
                                and not clean_name.startswith("embedding-")
                                and not clean_name.startswith("aqa")
                            ):
                                discovered.append(clean_name)
                    return discovered if discovered else list(self.SUPPORTED_MODELS)
                else:
                    category = self._categorize_http_status(res.status_code, res.text)
                    detail = self._extract_error_detail(res.text)
                    sanitized_detail = ProviderError._sanitize(detail)
                    logger.warning(
                        f"Google Gemini model discovery failed (HTTP {res.status_code}, {category.value}): {sanitized_detail}"
                    )
                    raise ProviderError(
                        self.provider_id,
                        f"[{category.value}] Google Gemini model discovery failed (HTTP {res.status_code}): {sanitized_detail}",
                        status_code=res.status_code,
                        error_code=category
                    )
        except httpx.TimeoutException:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.PROVIDER_UNREACHABLE.value}] Timeout connecting to Google Gemini model discovery.",
                error_code=AIErrorCode.PROVIDER_UNREACHABLE
            )
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.PROVIDER_UNREACHABLE.value}] Network connection failed during model discovery: {ProviderError._sanitize(str(e))}",
                error_code=AIErrorCode.PROVIDER_UNREACHABLE
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.CONFIGURATION_ERROR.value}] Model discovery failed: {ProviderError._sanitize(str(e))}",
                error_code=AIErrorCode.CONFIGURATION_ERROR
            )

    async def test_connection(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> ConnectionTestResult:
        effective_key = api_key or (settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else None)
        if not effective_key:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message=f"[{AIErrorCode.CONFIGURATION_ERROR.value}] API key is required for Google Gemini provider connection test.",
                error_code=AIErrorCode.CONFIGURATION_ERROR,
                has_key=False
            )
        target_url = self._normalize_base_url(base_url)
        self._validate_https_url(target_url, is_local=False)

        model_name = self._normalize_model(model)
        headers = {
            "x-goog-api-key": effective_key.strip(),
            "Content-Type": "application/json"
        }
        start_time = time.time()
        try:
            async with self._get_client() as client:
                res = await client.post(
                    f"{target_url}/models/{model_name}:generateContent",
                    headers=headers,
                    json={"contents": [{"parts": [{"text": "ADFIP connectivity test check. Respond with OK."}]}]}
                )
                latency = round((time.time() - start_time) * 1000, 2)

                if res.status_code == 200:
                    logger.info(f"Google Gemini connection verified successfully using model '{model_name}' ({latency}ms).")
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=True,
                        status_message=f"Google Gemini connection verified successfully using {model_name}.",
                        error_code=AIErrorCode.SUCCESS,
                        latency_ms=latency,
                        has_key=True
                    )
                else:
                    category = self._categorize_http_status(res.status_code, res.text)
                    detail = self._extract_error_detail(res.text)
                    sanitized_detail = ProviderError._sanitize(detail)
                    logger.warning(
                        f"Google Gemini connection test failed for '{model_name}' (HTTP {res.status_code}, {category.value}): {sanitized_detail}"
                    )
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=False,
                        status_message=f"[{category.value}] Google Gemini API error (HTTP {res.status_code}): {sanitized_detail}",
                        error_code=category,
                        latency_ms=latency,
                        has_key=True
                    )
        except httpx.TimeoutException:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"Google Gemini connection timed out for model '{model_name}'.")
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message=f"[{AIErrorCode.PROVIDER_UNREACHABLE.value}] Connection timed out connecting to Google Gemini API.",
                error_code=AIErrorCode.PROVIDER_UNREACHABLE,
                latency_ms=latency,
                has_key=True
            )
        except (httpx.ConnectError, httpx.NetworkError) as e:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"Google Gemini network connection failed for model '{model_name}': {ProviderError._sanitize(str(e))}")
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message=f"[{AIErrorCode.PROVIDER_UNREACHABLE.value}] Network connection failed: {ProviderError._sanitize(str(e))}",
                error_code=AIErrorCode.PROVIDER_UNREACHABLE,
                latency_ms=latency,
                has_key=True
            )
        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Unexpected error during Google Gemini connection test for model '{model_name}': {ProviderError._sanitize(str(e))}")
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message=f"[{AIErrorCode.CONFIGURATION_ERROR.value}] {ProviderError._sanitize(str(e))}",
                error_code=AIErrorCode.CONFIGURATION_ERROR,
                latency_ms=latency,
                has_key=True
            )

    async def generate(self, req: ProviderRequest) -> ProviderResponse:
        effective_key = req.api_key or (settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else None)
        if not effective_key:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.CONFIGURATION_ERROR.value}] API key is required for Google Gemini provider generation.",
                error_code=AIErrorCode.CONFIGURATION_ERROR
            )

        target_url = self._normalize_base_url(req.base_url)
        self._validate_https_url(target_url, is_local=False)

        headers = {
            "x-goog-api-key": effective_key.strip(),
            "Content-Type": "application/json"
        }

        model_name = self._normalize_model(req.model)
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": req.prompt}]}]
        }
        if req.system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": req.system_prompt}]}

        generation_config: Dict[str, Any] = {}
        if req.temperature is not None:
            generation_config["temperature"] = req.temperature
        if req.max_tokens:
            generation_config["maxOutputTokens"] = req.max_tokens
        if generation_config:
            payload["generationConfig"] = generation_config

        try:
            async with self._get_client() as client:
                res = await client.post(
                    f"{target_url}/models/{model_name}:generateContent",
                    headers=headers,
                    json=payload
                )
                if res.status_code != 200:
                    category = self._categorize_http_status(res.status_code, res.text)
                    detail = self._extract_error_detail(res.text)
                    sanitized_detail = ProviderError._sanitize(detail)
                    logger.warning(
                        f"Google Gemini generation failed for '{model_name}' (HTTP {res.status_code}, {category.value}): {sanitized_detail}"
                    )
                    raise ProviderError(
                        self.provider_id,
                        f"[{category.value}] Google Gemini API error HTTP {res.status_code}: {sanitized_detail}",
                        status_code=res.status_code,
                        error_code=category
                    )

                data = res.json()
                if "candidates" not in data or not data["candidates"]:
                    raise ProviderError(
                        self.provider_id,
                        f"[{AIErrorCode.GENERATION_FAILED.value}] Google Gemini API returned malformed response: missing candidates.",
                        error_code=AIErrorCode.GENERATION_FAILED
                    )

                candidate = data["candidates"][0]
                parts = candidate.get("content", {}).get("parts", [])
                text_content = "".join([p.get("text", "") for p in parts if isinstance(p, dict)])

                usage_raw = data.get("usageMetadata", {})
                usage = None
                if isinstance(usage_raw, dict) and usage_raw:
                    usage = {
                        "prompt_tokens": usage_raw.get("promptTokenCount", 0),
                        "completion_tokens": usage_raw.get("candidatesTokenCount", 0),
                        "total_tokens": usage_raw.get("totalTokenCount", 0),
                        **usage_raw
                    }

                return ProviderResponse(
                    provider=self.provider_id,
                    model=model_name,
                    content=text_content,
                    usage=usage
                )

        except httpx.TimeoutException:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.PROVIDER_UNREACHABLE.value}] Google Gemini API request timed out.",
                error_code=AIErrorCode.PROVIDER_UNREACHABLE
            )
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.PROVIDER_UNREACHABLE.value}] Network connection to Google Gemini API failed: {ProviderError._sanitize(str(e))}",
                error_code=AIErrorCode.PROVIDER_UNREACHABLE
            )
        except json.JSONDecodeError:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.GENERATION_FAILED.value}] Google Gemini API returned malformed non-JSON response.",
                error_code=AIErrorCode.GENERATION_FAILED
            )
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                self.provider_id,
                f"[{AIErrorCode.GENERATION_FAILED.value}] Google Gemini API execution error: {ProviderError._sanitize(str(e))}",
                error_code=AIErrorCode.GENERATION_FAILED
            )


class LocalOpenAIAdapter(BaseAIAdapter):
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "llama3"

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        super().__init__(ProviderId.LOCAL_OPENAI, self.DEFAULT_MODEL, transport)

    async def test_connection(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> ConnectionTestResult:
        target_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._validate_https_url(target_url, is_local=True)

        start_time = time.time()
        try:
            async with self._get_client() as client:
                res = await client.get(f"{target_url}/models")
                latency = round((time.time() - start_time) * 1000, 2)

                if res.status_code == 200:
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=True,
                        status_message="Local OpenAI-compatible API connection verified successfully.",
                        latency_ms=latency,
                        has_key=False
                    )
                else:
                    return ConnectionTestResult(
                        provider=self.provider_id,
                        success=False,
                        status_message=f"Local OpenAI API returned HTTP {res.status_code}",
                        latency_ms=latency,
                        has_key=False
                    )
        except httpx.TimeoutException:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message="Connection timed out connecting to local endpoint.",
                has_key=False
            )
        except Exception as e:
            return ConnectionTestResult(
                provider=self.provider_id,
                success=False,
                status_message=ProviderError._sanitize(str(e)),
                has_key=False
            )

    async def generate(self, req: ProviderRequest) -> ProviderResponse:
        target_url = (req.base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._validate_https_url(target_url, is_local=True)

        headers = {"Content-Type": "application/json"}
        if req.api_key:
            headers["Authorization"] = f"Bearer {req.api_key}"

        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})

        payload = {
            "model": req.model or self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens
        }

        try:
            async with self._get_client() as client:
                res = await client.post(f"{target_url}/chat/completions", headers=headers, json=payload)
                if res.status_code != 200:
                    raise ProviderError(
                        self.provider_id,
                        f"Local OpenAI API error HTTP {res.status_code}: {res.text}",
                        status_code=res.status_code
                    )

                data = res.json()
                if "choices" not in data or not data["choices"]:
                    raise ProviderError(self.provider_id, "Local OpenAI API returned malformed response: missing choices.")

                choice = data["choices"][0]
                content = choice.get("message", {}).get("content", "")
                if content is None:
                    content = ""

                return ProviderResponse(
                    provider=self.provider_id,
                    model=req.model or self.DEFAULT_MODEL,
                    content=content,
                    request_id=data.get("id"),
                    usage=data.get("usage") if isinstance(data.get("usage"), dict) else None
                )

        except httpx.TimeoutException:
            raise ProviderError(self.provider_id, "Local OpenAI API request timed out.")
        except json.JSONDecodeError:
            raise ProviderError(self.provider_id, "Local OpenAI API returned malformed non-JSON response.")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(self.provider_id, f"Local OpenAI API execution error: {str(e)}")


def get_ai_adapter(
    provider_id: str | ProviderId,
    transport: Optional[httpx.AsyncBaseTransport] = None
) -> BaseAIAdapter:
    raw = str(provider_id.value if isinstance(provider_id, ProviderId) else provider_id).lower().strip()
    if raw == "google":
        raw = "gemini"
    try:
        p_enum = ProviderId(raw)
    except ValueError:
        raise ProviderError(
            ProviderId.LOCAL_STUB,
            f"Invalid provider configuration: '{provider_id}' is not a supported AI provider."
        )

    if p_enum == ProviderId.OPENAI:
        return OpenAIAdapter(transport=transport)
    elif p_enum == ProviderId.ANTHROPIC:
        return AnthropicAdapter(transport=transport)
    elif p_enum == ProviderId.GEMINI:
        return GeminiAdapter(transport=transport)
    elif p_enum == ProviderId.LOCAL_OPENAI:
        return LocalOpenAIAdapter(transport=transport)
    else:
        raise ProviderError(
            ProviderId.LOCAL_STUB,
            f"Invalid provider configuration: '{provider_id}' is not a supported AI provider."
        )
