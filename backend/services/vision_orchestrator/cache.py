"""
VISION-ORCHESTRATOR-001 — content-addressed result/feature cache.

Caching follows *evidence identity*, not URLs. Keys are content-addressed and versioned
so the right things invalidate: a new geometry revision invalidates masks/semantics that
referenced the old one; a label change does NOT invalidate a visual embedding. This
module is the key builders + an in-memory store with hit/miss/bypass telemetry; a
disk-backed artifact store is a later increment (interface kept small so it can swap in).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


def _digest(*parts: Any) -> str:
    """Stable sha256 over the parts (order-significant, JSON-normalised)."""
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def image_key(canonical_bytes: bytes) -> str:
    """1. Canonical image cache — sha256 of the EXIF-transposed RGB pixels/bytes.
    Two URLs with identical pixels share downstream computation."""
    return hashlib.sha256(canonical_bytes).hexdigest()


def feature_key(image_hash: str, model_id: str, checkpoint: str,
                preprocessing_version: str, input_size) -> str:
    """2. Model feature cache — reusable encoders (SAM/DINO/CLIP)."""
    return _digest("feature", image_hash, model_id, checkpoint, preprocessing_version, input_size)


def analysis_key(image_hash: str, job_kind: str, profile: str,
                 operator_version: str, params: Optional[dict] = None) -> str:
    """3. Analysis-result cache — proposals, masks, depth/luminous maps."""
    return _digest("analysis", image_hash, job_kind, profile, operator_version, params or {})


def embedding_key(image_hash: str, mask_hash: str, crop_mode: str,
                  embedding_model: str, preprocessing_version: str) -> str:
    """4. Region embedding cache — a LABEL change does not invalidate; a MASK change does."""
    return _digest("embedding", image_hash, mask_hash, crop_mode, embedding_model, preprocessing_version)


def semantic_key(image_hash: str, candidate_set_digest: str, prompt_version: str,
                 schema_version: str, vlm_model: str) -> str:
    """5. Semantic/VLM cache — a new geometry revision (new candidate set) invalidates."""
    return _digest("semantic", image_hash, candidate_set_digest, prompt_version, schema_version, vlm_model)


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    bypasses: int = 0
    stores: int = 0
    invalidations: int = 0
    avoided_calls: int = 0   # adapter invocations skipped thanks to a hit

    def as_dict(self) -> Dict[str, int]:
        return dict(self.__dict__)


@dataclass
class ResultCache:
    """In-memory, content-addressed. `never_evict` guards authoritative artifacts from
    LRU (only recomputable artifacts are evictable) — the orchestrator never stores
    authoritative Regions/Grounds/Percepts here."""
    _store: Dict[str, Any] = field(default_factory=dict)
    stats: CacheStats = field(default_factory=CacheStats)

    def get(self, key: str):
        if key in self._store:
            self.stats.hits += 1
            self.stats.avoided_calls += 1
            return self._store[key]
        self.stats.misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        self._store[key] = value
        self.stats.stores += 1

    def has(self, key: str) -> bool:
        return key in self._store

    def bypass(self) -> None:
        """Record a manual `re-run with current model` (cache intentionally skipped)."""
        self.stats.bypasses += 1

    def invalidate(self, predicate: Callable[[str], bool]) -> int:
        gone = [k for k in self._store if predicate(k)]
        for k in gone:
            del self._store[k]
        self.stats.invalidations += len(gone)
        return len(gone)

    def clear(self) -> None:
        self._store.clear()
