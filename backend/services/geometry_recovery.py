"""
VISION-F · F3 — geometry recovery planner + executor.

Per Region, choose an HONEST recovery action and preserve the curator's identity:

  · `retain_mask`     — the Region already has an authoritative mask; leave geometry untouched.
  · `derive_polygon`  — a GENUINE traced polygon exists (many points); rasterize it to a canonical
                        mask (defensible fidelity). Never derive a mask from a 4-point box.
  · `sam_refine_box`  — box-only evidence; run SAM with the box as a PROMPT to segment the real
                        pixels (genuine, not fabricated), keeping the Region id + label + curator
                        fields. Skipped to `retain_box` if SAM is unavailable (F2 guard).
  · `retain_box`      — honest box-only retention (SAM down, or by choice).

Rules honoured: stable Region ids preserved; `geometry_rev` bumped + provenance recorded on
change; curator notes / priority / weight / label / accepted-rejected decisions preserved; old
geometry kept for rollback; masks never fabricated from boxes; geometry never label-parented or
clipped. Detached Grounds are marked visibly, never cascade-deleted.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from backend.services import mask_geometry as mg
from backend.services import vision_capabilities as cap

GENUINE_POLYGON_MIN_PTS = 8     # below this a "polygon" is a box rectangle, not a traced shape


def classify(region: dict) -> str:
    if mg.rle_is_valid(region.get("mask_rle")):
        return "mask"
    polys = region.get("polygons") or ([region["polygon"]] if region.get("polygon") else [])
    pts = sum(len(r) for r in polys if isinstance(r, list))
    if pts >= GENUINE_POLYGON_MIN_PTS:
        return "polygon"
    if region.get("box"):
        return "box"
    return "none"


def plan_region(region: dict, matrix: Dict[str, bool]) -> Dict[str, Any]:
    """Decide the action for one Region, applying the F2 capability skip-guard."""
    cls = classify(region)
    if cls == "mask":
        action = "retain_mask"
    elif cls == "polygon":
        action = "derive_polygon"
    elif cls == "box":
        action = "sam_refine_box"
    else:
        action = "skip"
    # capability guard: an action whose model is down becomes an honest fallback / skip
    if action == "sam_refine_box" and not matrix.get("sam", False):
        action = "retain_box"                    # honest — never fabricate a mask
    if action == "derive_polygon" and not matrix.get("geometry", True):
        action = "skip"
    return {"region_id": str(region.get("id")), "label": region.get("label"),
            "class": cls, "action": action}


def plan_post(post: dict, matrix: Dict[str, bool]) -> Dict[str, Any]:
    regions = post.get("region_annotations") or []
    region_plans = [plan_region(r, matrix) for r in regions]
    rids = {str(r.get("id")) for r in regions}
    grounds = post.get("grounds") or []
    detached = [g.get("id") for g in grounds
                if g.get("ground_type") == "region" and str(g.get("region_id")) not in rids]
    counts: Dict[str, int] = {}
    for rp in region_plans:
        counts[rp["action"]] = counts.get(rp["action"], 0) + 1
    return {"post_id": str(post.get("_id") or post.get("id")), "n_regions": len(regions),
            "actions": counts, "regions": region_plans, "detached_grounds": detached,
            "mutates": any(rp["action"] in ("derive_polygon", "sam_refine_box") for rp in region_plans)
                       or bool(detached)}


# ── geometry-only merge: change pixels, keep the curator's identity ──────────
_GEOMETRY_KEYS = ("mask_rle", "polygons", "polygon", "box", "geometry_rev", "geometry_provenance")


def apply_mask_to_region(region: dict, mask_rle: dict, *, method: str, image_hw=None) -> dict:
    """Set a Region's authoritative mask and re-canonicalize IN PLACE, preserving every non-
    geometry field (id, label, user_note, prioritised, weight, actor, category…). Records the old
    geometry under `_prev_geometry` for the ledger/rollback and bumps geometry_rev via canonicalize."""
    prev = {k: region.get(k) for k in _GEOMETRY_KEYS}
    region["mask_rle"] = mask_rle
    region.pop("polygon", None)                  # stale legacy singular — re-derived below
    region["polygons"] = None
    mg.canonicalize_geometry(region, default_mask_size=image_hw,
                             provenance={"recovery": "vision-f", "method": method})
    region["_prev_geometry"] = prev
    return region


def derive_mask_from_polygon(region: dict, image_hw) -> Optional[dict]:
    """Rasterize a genuine traced polygon into an authoritative mask, preserving identity."""
    polys = region.get("polygons") or ([region["polygon"]] if region.get("polygon") else [])
    polys = [r for r in polys if isinstance(r, list) and len(r) >= 3]
    if not polys or not image_hw:
        return None
    h, w = int(image_hw[0]), int(image_hw[1])
    bits = mg.polygons_to_bits(polys, h, w)
    if mg.rle_area(mg.rle_encode(bits, h, w)) <= 0:
        return None
    rle = mg.rle_encode(bits, h, w)
    return apply_mask_to_region(region, rle, method="derive-polygon", image_hw=(h, w))


async def recover_post(post: dict, image_bytes: bytes, plan: Dict[str, Any], *,
                       refine_session, image_hw) -> Dict[str, Any]:
    """Execute a post's geometry plan IN PLACE on `post`, preserving curator identity. Runs SAM
    (box prompt) for box regions, rasterizes genuine polygons, retains masks. Returns a per-region
    trace of what changed. The caller persists `post` and updates the ledger."""
    regions = {str(r.get("id")): r for r in (post.get("region_annotations") or [])}
    trace = []
    for rp in plan["regions"]:
        rid = rp["region_id"]
        region = regions.get(rid)
        if region is None:
            continue
        action = rp["action"]
        before = {"class": rp["class"], "geometry_rev": region.get("geometry_rev")}
        if action == "derive_polygon":
            res = derive_mask_from_polygon(region, image_hw)
            ok = res is not None
            trace.append({"region_id": rid, "label": rp["label"], "action": action,
                          "ok": ok, "before": before, "geometry_rev": region.get("geometry_rev")})
        elif action == "sam_refine_box":
            box = region.get("box") or {}
            x, y, w, h = box.get("x", 0), box.get("y", 0), box.get("w", 0), box.get("h", 0)
            prompt = {"box": [x, y, x + w, y + h]}          # normalized corners (refine_session scales)
            try:
                proposal = await refine_session.preview(image_bytes, prompt, base_id=rid,
                                                        base_rev=int(region.get("geometry_rev") or 0))
                apply_mask_to_region(region, proposal["mask_rle"], method="sam-refine-box",
                                     image_hw=image_hw)
                ok = mg.rle_is_valid(region.get("mask_rle"))
            except Exception as e:
                ok = False
                trace.append({"region_id": rid, "label": rp["label"], "action": action,
                              "ok": False, "error": str(e)})
                continue
            trace.append({"region_id": rid, "label": rp["label"], "action": action, "ok": ok,
                          "before": before, "geometry_rev": region.get("geometry_rev")})
        else:  # retain_mask / retain_box / skip — no geometry change
            trace.append({"region_id": rid, "label": rp["label"], "action": action, "ok": True,
                          "before": before, "geometry_rev": region.get("geometry_rev")})
    marked = mark_detached_grounds(post)
    return {"post_id": plan["post_id"], "trace": trace, "detached_marked": marked}


def stale_semantic_assertions(post: dict, prior_mask_hashes: Dict[str, str]) -> List[str]:
    """Candidate ids whose semantic assertion must be marked stale because the EVIDENCE it reads
    changed — the region's mask now differs from `prior_mask_hashes` (pre-recovery). Curator
    decisions are never dropped here; the caller flags stale but preserves status/curator_label.
    An assertion about unchanged evidence stays valid (a geometry recovery that did not touch a
    region does not invalidate its reading)."""
    from backend.services.region_embedding_service import mask_hash
    cur = {str(r.get("id")): (mask_hash(r.get("mask_rle")) if mg.rle_is_valid(r.get("mask_rle")) else "")
           for r in (post.get("region_annotations") or [])}
    sem = post.get("semantics") or {}
    stale = []
    for a in (sem.get("assertions") or []):
        cid = str(a.get("candidate_id"))
        if cur.get(cid, "") != prior_mask_hashes.get(cid, ""):
            stale.append(cid)
    return stale


def mark_stale_semantic_assertions(post: dict, prior_mask_hashes: Dict[str, str]) -> List[str]:
    """Flag stale assertions in place (`evidence_stale=True`) WITHOUT dropping curator decisions —
    status / curator_label are preserved; only a marker is added so the UX can offer a re-read."""
    stale = set(stale_semantic_assertions(post, prior_mask_hashes))
    for a in ((post.get("semantics") or {}).get("assertions") or []):
        a["evidence_stale"] = str(a.get("candidate_id")) in stale
    return sorted(stale)


def mark_detached_grounds(post: dict) -> List[str]:
    """Flag Grounds whose Region no longer exists as detached/stale — visibly, never deleted."""
    regions = post.get("region_annotations") or []
    rids = {str(r.get("id")) for r in regions}
    marked = []
    for g in (post.get("grounds") or []):
        if g.get("ground_type") == "region" and str(g.get("region_id")) not in rids:
            g["detached"] = True
            g["detached_reason"] = "region evidence absent after recovery"
            marked.append(g.get("id"))
    return marked
