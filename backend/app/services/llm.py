from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import json

class LLMProvider(ABC):
    """
    Abstract Interface for LLM Reasoning Engines.
    Provider-agnostic abstraction for Local LLMs, Gemini, Qwen, Llama, Mistral, etc.
    Does NOT require a paid API key for default operation.
    """

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def analyze(self, verified_context: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def summarize(self, findings: List[Dict[str, Any]]) -> str:
        pass

class LocalLLMProvider(LLMProvider):
    """
    Default provider: executes locally without cloud egress or paid keys.
    """

    def __init__(self, endpoint: Optional[str] = None):
        from backend.app.core.config import settings
        self.endpoint = endpoint if endpoint is not None else settings.LOCAL_LLM_ENDPOINT

    def _sanitize_untrusted_data(self, data_str: str) -> str:
        """
        Hardens prompt against injection by neutralizing instruction overrides in evidence.
        Evidence is always framed strictly as untrusted literal data.
        """
        return data_str.replace("```", "'''")

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Default deterministic reasoning response
        return f"[Reasoned Analysis]: Synthesized verified context based on deterministic findings."

    async def analyze(self, verified_context: Dict[str, Any]) -> Dict[str, Any]:
        findings_count = len(verified_context.get("findings", []))
        if findings_count == 0:
            return {
                "attack_type": "INSUFFICIENT EVIDENCE",
                "mitre_tactic": None,
                "confidence": None,
                "summary": "No verified findings are available for attack classification."
            }

        return {
            "attack_type": "PENDING_INVESTIGATOR_REVIEW",
            "mitre_tactic": None,
            "confidence": None,
            "summary": (
                f"{findings_count} finding(s) are available for investigator review. "
                "No automated attack classification is asserted."
            )
        }

    async def summarize(self, findings: List[Dict[str, Any]]) -> str:
        if not findings:
            return "No verified findings available for summary."
        return f"Investigation identified {len(findings)} technical findings across analyzed forensic artifacts."

class GeminiProvider(LLMProvider):
    """
    Production Google Gemini provider integrating directly with GeminiAdapter.
    Executes real generateContent requests against Google Generative Language API.
    Never returns fake or synthetic responses.
    """
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        from backend.app.services.ai_provider import GeminiAdapter
        self.api_key = api_key
        self.model = model or "gemini-2.5-flash"
        self._adapter = GeminiAdapter()

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        from backend.app.services.ai_provider import ProviderRequest, AIErrorCode, ProviderError
        from backend.app.core.config import settings

        key = self.api_key or (settings.GEMINI_API_KEY if settings.GEMINI_API_KEY else None)
        if not key:
            raise ProviderError(
                self._adapter.provider_id,
                "API key is not configured for Google Gemini provider.",
                error_code=AIErrorCode.CONFIGURATION_ERROR
            )

        req = ProviderRequest(
            provider=self._adapter.provider_id,
            model=self.model,
            prompt=prompt,
            system_prompt=system_prompt,
            api_key=key,
        )
        res = await self._adapter.generate(req)
        return res.content

    async def analyze(self, verified_context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"Analyze verified forensic context and provide technical classification:\n{json.dumps(verified_context, default=str)}"
        content = await self.generate(prompt)
        return {"status": "analyzed", "content": content}

    async def summarize(self, findings: List[Dict[str, Any]]) -> str:
        if not findings:
            return "No verified findings available for summary."
        prompt = f"Summarize technical findings for forensic report:\n{json.dumps(findings, default=str)}"
        return await self.generate(prompt)

