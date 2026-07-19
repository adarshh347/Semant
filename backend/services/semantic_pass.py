"""
VISION-D · D2 — the semantic pass + safe persistence.

Runs the geometry-forbidding VLM interpretation through the orchestrator's REMOTE slot
(concurrency 1, dedup, timeout, cancellation, telemetry, content-addressed cache) and
returns semantic assertions to be stored SEPARATELY from geometry (post.semantics), never
touching region_annotations. A rerun with the same evidence hits the cache; a new candidate
set (a geometry change) is a new cache key. Curator state (accepted/rejected/overridden +
edited label) is preserved across reruns.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.services import evidence_packet
from backend.services.semantic_provider import MODEL, PROVIDER
from backend.services.vision_orchestrator import (AdapterRegistry, CancelToken, ModelManager,
                                                  Priority)
from backend.services.vision_orchestrator.adapters import SemanticAnnotatorAdapter
from backend.services.vision_orchestrator.cache import semantic_key
from backend.schemas.vision_semantic import SCHEMA_VERSION

PROMPT_VERSION = "prompt-v1"

_registry = AdapterRegistry()
_default_adapter = SemanticAnnotatorAdapter()
_registry.register(_default_adapter)
_manager = ModelManager(_registry)

# curator states that must survive a semantic rerun untouched.
_STICKY_STATES = {"accepted", "rejected", "overridden"}


def _candidate_digest(candidates: List[dict]) -> str:
    payload = [[c.get("candidate_id"), c.get("auto_label")] for c in candidates]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def run_semantic(post: dict, image_bytes: bytes, *, intent: str = "name",
                       force: bool = False, cancel: Optional[CancelToken] = None,
                       adapter=None) -> Dict[str, Any]:
    """Build the packet, run (or cache-hit) the semantic call through the remote slot,
    and return the semantics structure. Does NOT persist — the caller does that."""
    adapter = adapter or _default_adapter
    packet = evidence_packet.build_packet(post, image_bytes, intent=intent)
    cand_digest = _candidate_digest(packet["candidates"])
    ckey = semantic_key(packet["image_hash"], cand_digest, PROMPT_VERSION, SCHEMA_VERSION,
                        adapter.spec.model_id)
    if force:
        _manager.cache.invalidate(lambda k: k == ckey)   # bypass but keep prior revisions
        _manager.cache.bypass()

    result = await _manager.run_adapter(
        adapter, {"packet": packet, "allowed_ids": packet["allowed_ids"]},
        priority=int(Priority.FOREGROUND), cancel=cancel or CancelToken(),
        cache_key=ckey, timeout_s=45.0)

    return _to_semantics(result, cand_digest, adapter)


def _to_semantics(job_result, cand_digest: str, adapter) -> Dict[str, Any]:
    sr = job_result.artifact.data if job_result.artifact else None
    now = datetime.now(timezone.utc)
    meta = {
        "provider": adapter.spec.name, "model": adapter.spec.model_id,
        "schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION,
        "candidate_digest": cand_digest, "status": job_result.status.value,
        "from_cache": bool(getattr(job_result, "from_cache", False)),
        "created_at": now, "dropped_ids": getattr(sr, "dropped_ids", []),
        "error": getattr(sr, "error", "") or "",
    }
    if not (sr and getattr(sr, "response", None)):
        return {"assertions": [], "relations": [], "global": None, "meta": meta}

    resp = sr.response
    assertions = []
    for c in resp.candidates:
        assertions.append({
            "candidate_id": c.candidate_id,
            "label": c.label, "ranked_alternatives": c.ranked_alternatives,
            "part": c.part, "material": c.material, "attributes": c.attributes,
            "style": c.style, "confidence": c.confidence, "uncertainty": c.uncertainty,
            "provider": adapter.spec.name, "model": adapter.spec.model_id,
            "prompt_schema_version": SCHEMA_VERSION, "created_at": now,
            "status": "proposed", "curator_label": None,
        })
    relations = [r.model_dump() for r in resp.relations]
    global_reading = resp.global_reading.model_dump() if resp.global_reading else None
    return {"assertions": assertions, "relations": relations, "global": global_reading, "meta": meta}


def merge_curator_state(new_sem: Dict[str, Any], prior_sem: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Preserve curator decisions across a rerun: any prior assertion whose status is
    accepted/rejected/overridden — or that carries an edited curator_label — is kept as the
    curator left it; only untouched (proposed) assertions are refreshed by the new run."""
    if not prior_sem:
        return new_sem
    prior_by_id = {a.get("candidate_id"): a for a in (prior_sem.get("assertions") or [])}
    merged = []
    for a in new_sem.get("assertions", []):
        prev = prior_by_id.get(a["candidate_id"])
        if prev and (prev.get("status") in _STICKY_STATES or prev.get("curator_label")):
            merged.append(prev)                            # curator's decision wins
        else:
            merged.append(a)
    new_sem = dict(new_sem)
    new_sem["assertions"] = merged
    return new_sem
