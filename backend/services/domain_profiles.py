"""
Domain profiles (VISION-C-DOMAIN-PROFILES-001 · C0) — the persisted, multi-label,
user-overridable routing contract that decides which specialist passes an image gets.

Profiles: auto · general · fashion · architecture · painting. `auto` proposes a
multi-label, confidence-bearing set (an image can be both fashion AND architecture);
the user's explicit choice always wins and persists. Each chosen profile schedules a
set of passes (adapter names from VISION-MODEL-MATRIX-001); `general` is always present
as the cheap fallback, never a compulsory prison for the specialists.

This module is pure/deterministic (no model import) — the actual domain scoring comes
from `fashion_clip_service.classify_domains`; here we turn scores (or a user override)
into the persisted profile + its scheduled passes. Adapters run in C1–C4.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PROFILES = ["auto", "general", "fashion", "architecture", "painting"]
SPECIALISTS = ["fashion", "architecture", "painting"]
ROUTER_VERSION = "route-v1"
DEFAULT_GATE = 0.35

# Which adapter passes each profile schedules (roster names). `general` is the cheap
# proposal pass everyone shares; specialists add their primary + SAM refinement.
PROFILE_PASSES: Dict[str, List[str]] = {
    "general": ["yolo11n_seg", "sam21_hiera_tiny"],
    "fashion": ["fashionpedia_r50fpn", "sam21_hiera_tiny"],
    "architecture": ["segformer_b0_ade", "sam21_hiera_tiny"],
    # painting individuates by prompt (SAM); optional scene proposals; Grounds are
    # first-class when object segmentation is the wrong ontology (handled in the UI/C4).
    "painting": ["sam21_hiera_tiny", "segformer_b0_ade"],
}


def passes_for(chosen: List[str]) -> List[str]:
    """Union of scheduled passes for the chosen profiles, order-stable, deduped.
    `general` always contributes its cheap pass (fallback, not a prison)."""
    seen: List[str] = []
    for prof in ["general", *[p for p in chosen if p != "general"]]:
        for pass_name in PROFILE_PASSES.get(prof, []):
            if pass_name not in seen:
                seen.append(pass_name)
    return seen


def propose_profile(scores: Dict[str, float], *, gate: float = DEFAULT_GATE,
                    router_version: str = ROUTER_VERSION,
                    reason_detail: str = "") -> Dict[str, Any]:
    """Auto proposal: general always, plus every specialist scoring >= gate (multi-label).
    Records why (the scores) and which passes it schedules."""
    proposed = {d: round(float(scores.get(d, 0.0)), 4) for d in SPECIALISTS}
    chosen = ["general"] + [d for d in SPECIALISTS if proposed[d] >= gate]
    ranked = sorted(proposed.items(), key=lambda kv: kv[1], reverse=True)
    reason = reason_detail or (
        "auto: " + ", ".join(f"{d} {s:.2f}" for d, s in ranked)
        + (f" — over gate {gate}: {[d for d in SPECIALISTS if proposed[d] >= gate] or 'none (general only)'}")
    )
    return {
        "mode": "auto",
        "proposed": proposed,
        "chosen": chosen,
        "user_overridden": False,
        "router_version": router_version,
        "reason": reason,
        "scheduled_passes": passes_for(chosen),
    }


def apply_override(profile: Optional[Dict[str, Any]], *, mode: Optional[str] = None,
                   chosen: Optional[List[str]] = None) -> Dict[str, Any]:
    """The user's explicit choice wins and persists. `mode` may be a single profile
    (general/fashion/architecture/painting) or 'auto' (re-enables the proposal's chosen
    set); `chosen` explicitly sets the active multi-label set."""
    base = dict(profile or {"proposed": {}, "router_version": ROUTER_VERSION, "reason": ""})
    if mode is not None and mode not in PROFILES:
        raise ValueError(f"unknown profile mode: {mode}")

    if chosen is not None:
        active = _normalise_chosen(chosen)
        resolved_mode = "auto" if mode is None else mode
    elif mode == "auto":
        # fall back to the auto proposal already computed (general if none)
        active = _normalise_chosen(base.get("chosen") or ["general"])
        resolved_mode = "auto"
    elif mode is not None:
        active = _normalise_chosen(["general", mode] if mode != "general" else ["general"])
        resolved_mode = mode
    else:
        active = _normalise_chosen(base.get("chosen") or ["general"])
        resolved_mode = base.get("mode", "auto")

    base.update({
        "mode": resolved_mode,
        "chosen": active,
        "user_overridden": True,
        "scheduled_passes": passes_for(active),
        "reason": (base.get("reason") or "") + " · user override",
    })
    return base


def _normalise_chosen(chosen: List[str]) -> List[str]:
    """general always first; keep only known specialists; dedupe; stable order."""
    out = ["general"]
    for d in chosen:
        if d in SPECIALISTS and d not in out:
            out.append(d)
    return out


def default_profile() -> Dict[str, Any]:
    """A safe starting profile before any classification (general only)."""
    return {
        "mode": "auto", "proposed": {d: 0.0 for d in SPECIALISTS}, "chosen": ["general"],
        "user_overridden": False, "router_version": ROUTER_VERSION,
        "reason": "not yet classified", "scheduled_passes": passes_for(["general"]),
    }
