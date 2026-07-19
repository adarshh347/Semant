"""
VISION-F · F2 — capability readiness + the unavailable→skip guard.

F3 chooses a recovery action per post; each action needs certain capabilities (a domain rerun
needs its segmenter; SAM refine needs SAM; a semantic refresh needs the VLM provider). This
module names those dependencies and provides the guard that turns an action whose capability is
DOWN into a **planned skip** — never a partial, corrupt write. The live probe that fills the
matrix lives in `scripts/vision_f2_capabilities.py`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

# a recovery action → the capabilities it needs (all must be available to run it)
ACTION_CAPABILITIES: Dict[str, List[str]] = {
    "retain_box": [],                               # honest legacy retention — needs nothing
    "derive_from_polygon": ["geometry"],            # pure-python geometry service
    "rerun_profile_general": ["yolo", "sam"],
    "rerun_profile_architecture": ["segformer"],
    "rerun_profile_fashion": ["fashion_segmenter"],
    "sam_refine": ["sam"],
    "semantic_refresh": ["semantic_provider"],
    "embed_dinov2": ["dinov2"],
    "embed_fashion": ["fashionclip"],
}


def missing_for(action: str, matrix: Dict[str, bool]) -> List[str]:
    """Capabilities an action needs that are not available in the live matrix."""
    return [c for c in ACTION_CAPABILITIES.get(action, []) if not matrix.get(c, False)]


def resolve_action(action: str, matrix: Dict[str, bool]) -> Dict[str, Any]:
    """Decide whether an action can run. Unavailable capability → the action becomes a SKIP with
    a reason; it is never allowed to run and write partial geometry."""
    missing = missing_for(action, matrix)
    if missing:
        return {"action": "skip", "requested": action, "runnable": False,
                "reason": f"unavailable: {', '.join(missing)}"}
    return {"action": action, "requested": action, "runnable": True, "reason": ""}


def plan_skips(planned: Sequence[Dict[str, Any]], matrix: Dict[str, bool]) -> List[Dict[str, Any]]:
    """Apply the guard across a plan: `planned` is [{post_id, action}, …]; returns each item with
    its resolved action (possibly downgraded to skip). No item is ever a partial write."""
    out = []
    for item in planned:
        res = resolve_action(item["action"], matrix)
        out.append({"post_id": item.get("post_id"), **res})
    return out
