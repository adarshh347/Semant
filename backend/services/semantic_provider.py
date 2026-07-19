"""
VISION-D · D0 — the semantic (VLM) provider.

Provider decision (evidence-backed, 2026-07-19):
  · **Groq (the configured provider) no longer serves ANY vision model** — its catalog is
    now text-only (llama-3.x, gpt-oss, qwen, whisper). The old `llama-4-scout` /
    `llama-4-maverick` vision models are gone; the 404 was real. Not viable.
  · **OpenRouter** serves 179 vision models. Chosen model: **`openai/gpt-4o-mini`** —
    native strict `json_schema` structured output (load-bearing for the geometry-forbidding
    contract), vision, low cost (~$0.15/M prompt, $0.60/M completion), broadly reliable.
    Cheaper capable alternatives kept on file: `google/gemini-2.5-flash-lite`,
    `qwen/qwen3-vl-8b-instruct`.
  · **Current state: UNAVAILABLE** — `OPENROUTER_API_KEY` is the literal placeholder, so no
    live call authenticates. The contract, packet and safety gates are provable without it;
    live interpretation needs a real key. No silent repoint to a deprecated model.

This module returns an explicit `state()` (ready | unavailable) and never fabricates a
reading when unavailable. `FakeSemanticProvider` drives deterministic tests.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.schemas.vision_semantic import (SemanticResponse, SCHEMA_VERSION,
                                             enforce_candidate_ids)

PROVIDER = "openrouter"
MODEL = "openai/gpt-4o-mini"
FALLBACK_MODELS = ["google/gemini-2.5-flash-lite", "qwen/qwen3-vl-8b-instruct"]
_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def _key() -> Optional[str]:
    k = (settings.OPENROUTER_API_KEY or "").strip()
    # a real OpenRouter key looks like sk-or-… ; the repo ships a placeholder.
    if not k or len(k) < 20 or k.lower() == "placeholder":
        return None
    return k


def _response_schema() -> Dict[str, Any]:
    """The json_schema the model is constrained to — geometry is unrepresentable
    (`additionalProperties: false` everywhere). OpenAI strict mode requires ALL properties
    in `required`, so optionals are nullable (type: [T, "null"])."""
    S = {"type": ["string", "null"]}
    NUM = {"type": ["number", "null"]}
    STRARR = {"type": "array", "items": {"type": "string"}}
    cand = {"type": "object", "additionalProperties": False,
            "properties": {"candidate_id": {"type": "string"}, "label": S,
                           "ranked_alternatives": STRARR, "part": S, "material": S,
                           "attributes": STRARR, "style": S, "confidence": NUM,
                           "uncertainty": S},
            "required": ["candidate_id", "label", "ranked_alternatives", "part", "material",
                         "attributes", "style", "confidence", "uncertainty"]}
    rel = {"type": "object", "additionalProperties": False,
           "properties": {"from_id": {"type": "string"}, "to_id": {"type": "string"},
                          "relation": {"type": "string"}, "confidence": NUM, "note": S},
           "required": ["from_id", "to_id", "relation", "confidence", "note"]}
    glob = {"type": "object", "additionalProperties": False,
            "properties": {"composition": S, "atmosphere": S, "colour": S, "scene": S,
                           "notes": STRARR},
            "required": ["composition", "atmosphere", "colour", "scene", "notes"]}
    return {
        "name": "semantic", "strict": True,
        "schema": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "candidates": {"type": "array", "items": cand},
                "relations": {"type": "array", "items": rel},
                "global_reading": glob,
                "needs_better_evidence": STRARR,
            }, "required": ["candidates", "relations", "global_reading", "needs_better_evidence"]},
    }


class SemanticResult:
    def __init__(self, status: str, response: Optional[SemanticResponse] = None,
                 *, error: str = "", dropped_ids: Optional[List[str]] = None,
                 latency_ms: Optional[float] = None, model: str = MODEL,
                 provider: str = PROVIDER, tokens: Optional[str] = None):
        self.status = status            # ready | unavailable | error | timed_out
        self.response = response
        self.error = error
        self.dropped_ids = dropped_ids or []
        self.latency_ms = latency_ms
        self.model = model
        self.provider = provider
        self.tokens = tokens

    def as_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "provider": self.provider, "model": self.model,
                "schema_version": SCHEMA_VERSION, "error": self.error,
                "dropped_ids": self.dropped_ids, "latency_ms": self.latency_ms,
                "tokens": self.tokens}


class SemanticProvider:
    def __init__(self, model: str = MODEL):
        self.model = model
        self.provider = PROVIDER

    def available(self) -> bool:
        return _key() is not None

    def state(self) -> Dict[str, str]:
        if self.available():
            return {"state": "ready", "provider": self.provider, "model": self.model, "reason": ""}
        return {"state": "unavailable", "provider": self.provider, "model": self.model,
                "reason": "OPENROUTER_API_KEY is a placeholder — set a real key to enable semantic reading"}

    def interpret(self, *, image_b64: str, allowed_ids: List[str], prompt: str,
                  timeout_s: float = 40.0) -> SemanticResult:
        """One structured semantic call. Never emits geometry (schema-forbidden); any
        assertion about an id not in `allowed_ids` is dropped, not honoured."""
        key = _key()
        if key is None:
            return SemanticResult("unavailable", error=self.state()["reason"])
        import httpx
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ]}],
            "response_format": {"type": "json_schema", "json_schema": _response_schema()},
            "max_tokens": 1200, "temperature": 0.2,
        }
        try:
            t0 = time.time()
            r = httpx.post(_ENDPOINT, headers={"Authorization": f"Bearer {key}"},
                           json=body, timeout=timeout_s)
            latency = (time.time() - t0) * 1000
        except httpx.TimeoutException:
            return SemanticResult("timed_out", error="provider timeout")
        except Exception as e:
            return SemanticResult("error", error=f"{type(e).__name__}: {e}")
        if r.status_code != 200:
            return SemanticResult("error", error=f"http {r.status_code}: {r.text[:200]}",
                                  latency_ms=round(latency))
        return self._parse(r.json(), allowed_ids, latency)

    def _parse(self, data: dict, allowed_ids: List[str], latency: float) -> SemanticResult:
        try:
            content = data["choices"][0]["message"]["content"]
            raw = json.loads(content)
            resp = SemanticResponse(**raw)                 # extra="forbid" rejects geometry
        except Exception as e:
            return SemanticResult("error", error=f"malformed structured output: {e}",
                                  latency_ms=round(latency))
        bad = enforce_candidate_ids(resp, allowed_ids)     # drop unknown-id assertions
        if bad:
            resp.candidates = [c for c in resp.candidates if c.candidate_id in allowed_ids]
            resp.relations = [x for x in resp.relations
                              if x.from_id in allowed_ids and x.to_id in allowed_ids]
            resp.needs_better_evidence = [i for i in resp.needs_better_evidence if i in allowed_ids]
        usage = data.get("usage") or {}
        tokens = f"{usage.get('prompt_tokens', '?')}+{usage.get('completion_tokens', '?')}"
        return SemanticResult("ready", resp, dropped_ids=bad, latency_ms=round(latency),
                              model=self.model, tokens=tokens)


class FakeSemanticProvider(SemanticProvider):
    """Deterministic provider for tests — returns a canned response bound to allowed_ids."""
    def __init__(self, response: Optional[SemanticResponse] = None, *, available: bool = True):
        super().__init__(model="fake-semantic")
        self._response = response
        self._available = available

    def available(self) -> bool:
        return self._available

    def state(self) -> Dict[str, str]:
        return {"state": "ready" if self._available else "unavailable",
                "provider": "fake", "model": self.model, "reason": ""}

    def interpret(self, *, image_b64: str, allowed_ids: List[str], prompt: str,
                  timeout_s: float = 40.0) -> SemanticResult:
        if not self._available:
            return SemanticResult("unavailable", error="fake unavailable")
        resp = self._response or SemanticResponse(
            candidates=[{"candidate_id": allowed_ids[0], "label": "fake", "confidence": 0.9}]
            if allowed_ids else [])
        bad = enforce_candidate_ids(resp, allowed_ids)
        if bad:
            resp.candidates = [c for c in resp.candidates if c.candidate_id in allowed_ids]
        return SemanticResult("ready", resp, dropped_ids=bad, model="fake-semantic", provider="fake")
