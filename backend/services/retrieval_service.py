"""
VISION-E · E3 — retrieval spaces + query routing.

Evidence lives in several vector spaces that must never be mixed:

  · **visual_identity / visual_context / visual_whole** — DINOv2 ViT-S/14 (384-d). Visual
    similarity of the evidence itself (identity) or of the evidence in its surroundings (context).
  · **fashion** — FashionCLIP ViT-B/32 (512-d). Fashion similarity of garment evidence; reuses
    the existing `fashion_clip_service` (Fashionpedia *segments/names* garments — FashionCLIP
    *represents* them; the two are never confused).
  · **text_image** — a general OpenCLIP text↔image space. DEFERRED/UNAVAILABLE: nothing is
    installed, and per the E-contract it is added ONLY if E4 evaluation shows it beats DINOv2 on
    text↔evidence retrieval. Until then queries for it return an explicit unavailable state.

The router picks the right space for a query; `find_similar` resolves that space and searches it
through the ONE sidecar. A comparison is only ever expressed via `cosine_same_space` (which
RAISES across spaces), so no cross-space cosine is possible in code — a FashionCLIP score can
never be compared with a DINOv2 or OpenCLIP one.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from backend.services import region_embedding_service as res

# ── space registry (availability resolved lazily so it reflects installed models) ──
# each: model tag, role, version, dim, and a human name. `available()` reads the live service.
_SPACES: Dict[str, Dict[str, Any]] = {
    "visual_identity": {"model": "dinov2_vits14", "role": "identity", "version": "dino-v1", "dim": 384},
    "visual_context":  {"model": "dinov2_vits14", "role": "context",  "version": "dino-v1", "dim": 384},
    "visual_whole":    {"model": "dinov2_vits14", "role": "whole_image", "version": "dino-v1", "dim": 384},
    "fashion":         {"model": "fashion-clip",  "role": "fashion",  "version": "vitb32",  "dim": 512},
    "text_image":      {"model": "openclip",      "role": "identity", "version": "unset",   "dim": 0},
}


def _dino_available() -> bool:
    try:
        from backend.services import dinov2_service
        return dinov2_service.is_available()
    except Exception:
        return False


def _fashion_available() -> bool:
    try:
        from backend.services import fashion_clip_service
        return fashion_clip_service.is_available()
    except Exception:
        return False


def _openclip_available() -> bool:
    # nothing installed/planned; the install is gated on E4 evidence (add only if it beats DINOv2).
    return False


def space_id(name: str) -> Optional[str]:
    """The `region_embedding_service.space_key` string for a named space (or None if unknown)."""
    s = _SPACES.get(name)
    if not s:
        return None
    return res.space_key(s["model"], s["role"], s["version"], s["dim"])


def space_available(name: str) -> bool:
    s = _SPACES.get(name)
    if not s:
        return False
    m = s["model"]
    if m == "dinov2_vits14":
        return _dino_available()
    if m == "fashion-clip":
        return _fashion_available()
    if m == "openclip":
        return _openclip_available()
    return False


def _unavailable_reason(name: str) -> str:
    s = _SPACES.get(name)
    if not s:
        return f"unknown space {name!r}"
    if s["model"] == "openclip":
        return "OpenCLIP not installed — deferred; add only if E4 shows it beats DINOv2 on text↔evidence"
    return f"{s['model']} unavailable (model not installed)"


def list_spaces() -> List[Dict[str, Any]]:
    """The retrieval spaces + live availability — for the curator UX / capabilities."""
    out = []
    for name, s in _SPACES.items():
        out.append({"name": name, "model": s["model"], "role": s["role"], "dim": s["dim"],
                    "space_id": space_id(name), "available": space_available(name),
                    "reason": "" if space_available(name) else _unavailable_reason(name)})
    return out


def route(*, query_kind: str, domain: Optional[str] = None,
          context_sensitive: bool = False) -> Dict[str, Any]:
    """Choose the space for a query. `query_kind` ∈ {'evidence','text'}; `domain` is the curator's
    domain profile (e.g. 'fashion'). Returns {space, available, reason}. Text queries need a
    text-capable space (fashion CLIP for fashion, else OpenCLIP)."""
    if query_kind == "text":
        # fashion text → FashionCLIP's text encoder; general text → OpenCLIP (deferred)
        name = "fashion" if domain == "fashion" else "text_image"
    else:  # evidence → evidence visual similarity
        if domain == "fashion":
            name = "fashion"
        else:
            name = "visual_context" if context_sensitive else "visual_identity"
    return {"space": name, "space_id": space_id(name), "available": space_available(name),
            "reason": "" if space_available(name) else _unavailable_reason(name)}


async def find_similar(query_vector: List[float], *, space: str, post_ids: Sequence[str],
                       exclude_post_id: Optional[str] = None, top_k: int = 8,
                       min_score: float = 0.0) -> Dict[str, Any]:
    """Search ONE named space. Returns {status, space, results, reason}. An unavailable space
    yields an explicit unavailable status (never a silent empty or a cross-space search); the
    search itself compares only within the resolved space (`search_similar(space=…)` →
    `cosine_same_space`), so a cross-space score can never be produced."""
    sid = space_id(space)
    if sid is None:
        return {"status": "error", "space": space, "results": [], "reason": f"unknown space {space!r}"}
    if not space_available(space):
        return {"status": "unavailable", "space": space, "results": [], "reason": _unavailable_reason(space)}
    if not query_vector:
        return {"status": "empty", "space": space, "results": [], "reason": "no query vector"}
    hits = await res.search_similar(query_vector, post_ids=post_ids, exclude_post_id=exclude_post_id,
                                    top_k=top_k, space=sid, min_score=min_score)
    return {"status": "ready", "space": space, "space_id": sid, "results": hits, "reason": ""}
