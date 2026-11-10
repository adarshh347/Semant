"""Hosted text transports. Provider changes are explicit, never a silent fallback."""
import os
from types import SimpleNamespace

SARVAM_ROLES = frozenset({"semantic_dissector", "relation_architect",
                         "epistemic_operationalizer", "synthesis_composer"})


def uses_sarvam(role):
    return role in SARVAM_ROLES and os.getenv("SEMANT_TEXT_PROVIDER", "groq").lower() == "sarvam"


class SarvamClient:
    def __init__(self, api_key, transport=None):
        import httpx
        self._http = httpx.Client(base_url="https://api.sarvam.ai/v1/", timeout=120,
                                 headers={"api-subscription-key": api_key}, transport=transport)
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        if not str(request.get("model", "")).startswith("sarvam-"):
            raise ValueError("Sarvam transport requires a Sarvam model binding")
        if any(not isinstance(m.get("content"), str) for m in request.get("messages", [])):
            raise ValueError("Sarvam text transport does not accept image messages")
        payload = dict(request)
        payload["max_tokens"] = payload.pop("max_completion_tokens", payload.get("max_tokens", 4096))
        payload.setdefault("reasoning_effort", None)
        payload.setdefault("temperature", 0.2)
        response = self._http.post("chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=c["message"].get("content")),
                                     finish_reason=c.get("finish_reason")) for c in data["choices"]],
            usage=SimpleNamespace(**(data.get("usage") or {})))


def client_for(role, *, max_retries=0):
    if uses_sarvam(role):
        key = os.getenv("SARVAM_API_KEY")
        return SarvamClient(key) if key else None
    from backend.config import settings
    from groq import Groq
    return Groq(api_key=settings.GROQ_API_KEY, max_retries=max_retries) if settings.GROQ_API_KEY else None
