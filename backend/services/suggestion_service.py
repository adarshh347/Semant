"""
CIRCUIT-001 P4-A — suggestion producers.

Turns real model output into `suggestion descriptors` — the plain-JSON shape the frontend
circuit ingests as quarantined `model_suggested` marks (contract v3 §8.4). Two producers:

  - ``suggestion_from_refine_region`` — a SAM2 mask preview → a ``region_mask`` (raster_mask)
    suggestion referencing the previewed region.
  - ``suggestions_from_semantics`` — a semantic-read result → ``region_mask`` (region_ref) label
    suggestions per assertion, and ``relation_mark`` suggestions per relation.

This module is PURE and geometry-honest: it authors no pixels. A SAM suggestion references the
region SAM already produced (``mask_ref``); a semantic suggestion references an EXISTING region
by id (``region_ref``) or a derived relation — never a mask the VLM drew (the VLM's law).

Every descriptor carries its receipt in ``provenance`` — ``model``, ``adapter``, ``latency_ms``,
``run_id``, ``producer`` — so the mark that results can never claim the model without one. The
route supplies ``run_id`` from a real ``vision_run_service`` run; this module never mints runs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services.mask_geometry import (rle_is_valid, soft_field_from_mask,
                                            strokes_from_field)

PRODUCER_SAM = "sam_refine"
PRODUCER_SEMANTIC = "semantic_read"
# CIRCUIT-001 P5-A — the crossing. A find-similar neighbour lives on ANOTHER post; it enters the
# circuit as an evidence-suggestion, never an assertion (Invariant 4). Its geometry is a
# cross-post `region_ref`: a REFERENCE across the border ({post_id, region_id, geometry_rev}),
# never a copy of the neighbour's mask.
PRODUCER_FIND_SIMILAR = "find_similar"
# CIRCUIT-001 P6-A — the first brush_field producer, and the first that loads NO model. Negative
# space is the complement of a figure that already exists in the packet, so this producer consumes
# a committed region's mask and calls no segmenter: deterministic, CPU-only, ~0 VRAM, unaffected
# by the torch +cpu regression. It occupies the PERCEPTUAL capability conceptually but needs no
# adapter — there is nothing to infer, only geometry to invert.
PRODUCER_NEGATIVE_SPACE = "negative_space"

# The VLM emits a free-text relation ("beside", "echoes", "same-material-as"); the mark contract
# freezes relation_role to a fixed vocabulary. Map by keyword, default to the generic spatial
# address — a valid role so a relation is never silently dropped by the frontend validator.
_RELATION_ROLE_BY_KEYWORD = [
    (("echo", "motif", "repeat", "rhyme"), "motif_echo"),
    (("same-material", "same material", "material", "similar", "same"), "similarity"),
    (("contrast", "oppose", "differ", "unlike"), "contrast"),
    (("tension", "pull", "strain"), "tension"),
    (("contradict",), "contradiction"),
    (("kin", "family", "sibling", "pair"), "kinship"),
    (("support", "hold", "carry", "rest"), "support"),
    (("before", "after", "then", "sequence", "temporal"), "temporal_suggestion"),
    (("address", "face", "look", "gaze", "toward", "beside", "next", "near", "adjacent"), "address_relation"),
]
_RELATION_ROLE_DEFAULT = "address_relation"


def relation_role_for(relation: Optional[str]) -> str:
    """Map a free-text VLM relation to a frozen relation_role key (never None)."""
    text = (relation or "").strip().lower()
    for keywords, role in _RELATION_ROLE_BY_KEYWORD:
        if any(k in text for k in keywords):
            return role
    return _RELATION_ROLE_DEFAULT


def _provenance(*, model: Optional[str], adapter: Optional[str], latency_ms: Optional[float],
                run_id: Optional[str], producer: str) -> Dict[str, Any]:
    return {"model": model, "adapter": adapter, "latency_ms": latency_ms,
            "run_id": run_id, "producer": producer}


def suggestion_from_refine_region(
    region: Dict[str, Any], *, run_id: Optional[str], latency_ms: Optional[float] = None,
    model: str = "sam2.1", adapter: str = "sam2", base_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """A SAM2 preview region → a quarantined ``region_mask`` suggestion descriptor.

    The suggestion references the region SAM produced (``mask_ref`` — the mask lives on the
    region, never inline). Returns None if the region has no id (nothing to reference)."""
    region_id = region.get("id") if isinstance(region, dict) else None
    if not region_id:
        return None
    return {
        "producer": PRODUCER_SAM,
        "type": "region_mask",
        "role": None,                                   # a segmented extent has no reading yet
        "label": region.get("label") or "",
        "source_ref": str(region_id),                   # idempotency key part
        "geometry": {"kind": "raster_mask",
                     "mask_ref": {"region_id": region_id,
                                  "geometry_rev": region.get("geometry_rev", 0)}},
        "linked_ground_ids": [],
        "provenance": _provenance(model=model, adapter=adapter, latency_ms=latency_ms,
                                  run_id=run_id, producer=PRODUCER_SAM),
        # extra context (ignored by the frontend mapper, useful to the review UX / tests)
        "base_id": base_id,
    }


def suggestions_from_semantics(
    semantics: Optional[Dict[str, Any]], *, run_id: Optional[str],
    adapter: str = "semantic_pass", latency_ms: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """A semantic-read result → suggestion descriptors.

    Label proposals (assertions) → ``region_mask`` marks in ``region_ref`` mode: a NAMING
    reference to an existing region, no geometry authored (the VLM's law). Relation proposals →
    ``relation_mark`` marks with ``derived`` geometry, linked to their endpoint region ids.

    A curator-REJECTED assertion is not re-suggested; an OVERRIDDEN/edited label rides through as
    the curator's text. Ids are echoed straight from the semantics — the frontend keys idempotency
    on them, so a semantic rerun updates rather than duplicates."""
    sem = semantics or {}
    meta = sem.get("meta") or {}
    default_model = meta.get("model")
    out: List[Dict[str, Any]] = []

    for a in sem.get("assertions") or []:
        cid = a.get("candidate_id")
        if not cid or a.get("status") == "rejected":
            continue
        label = a.get("curator_label") or a.get("label") or ""
        out.append({
            "producer": PRODUCER_SEMANTIC,
            "type": "region_mask",
            "role": None,
            "label": label,
            "source_ref": str(cid),
            "geometry": {"kind": "region_ref", "region_ref": {"region_id": cid}},
            "linked_ground_ids": [],
            "provenance": _provenance(model=a.get("model") or default_model, adapter=adapter,
                                      latency_ms=latency_ms, run_id=run_id,
                                      producer=PRODUCER_SEMANTIC),
        })

    for r in sem.get("relations") or []:
        frm, to = r.get("from_id"), r.get("to_id")
        if not (frm and to):
            continue
        rel = r.get("relation") or ""
        out.append({
            "producer": PRODUCER_SEMANTIC,
            "type": "relation_mark",
            "role": relation_role_for(rel),
            "label": rel or "relation",
            "source_ref": f"{frm}|{to}|{rel}",
            "geometry": {"kind": "derived"},
            "linked_ground_ids": [frm, to],
            "provenance": _provenance(model=default_model, adapter=adapter, latency_ms=latency_ms,
                                      run_id=run_id, producer=PRODUCER_SEMANTIC),
        })

    return out


# ── producer 3: find-similar as producer (CIRCUIT-001 P5-A, the crossing) ─────────────────────

def suggestions_from_similar(
    result: Optional[Dict[str, Any]], *, run_id: Optional[str], adapter: str = "find_similar",
) -> List[Dict[str, Any]]:
    """A find-similar research packet → cross-post ``region_ref`` suggestion descriptors.

    Each neighbour is a Region on ANOTHER post. It becomes a ``model_suggested`` ``region_mask`` in
    ``region_ref`` mode ON THE CURRENT post, whose geometry is a REFERENCE across the border —
    ``{region_id, post_id, geometry_rev}`` — never a copy of the neighbour's pixels (the border
    rule: a crossing is a reference with receipts, never a copy). ``geometry_rev`` is captured at
    citation so staleness (the source changed since cited) stays detectable downstream.

    A degraded research packet (``status`` error/unavailable) carries no evidence to suggest → []."""
    res = result or {}
    if not isinstance(res, dict):
        return []
    if res.get("status") in ("error", "unavailable"):
        return []
    out: List[Dict[str, Any]] = []
    for h in res.get("results") or []:
        npost = h.get("post_id")
        nregion = h.get("region_id")
        if not npost or nregion is None:
            continue                                    # a neighbour with no source is not citable
        prov = h.get("provenance") or {}
        grev = prov.get("geometry_rev")
        region_ref: Dict[str, Any] = {"region_id": str(nregion), "post_id": str(npost)}
        if grev is not None:
            region_ref["geometry_rev"] = grev           # rev-at-citation → staleness detectable
        out.append({
            "producer": PRODUCER_FIND_SIMILAR,
            "type": "region_mask",
            "role": None,                               # a neighbour is evidence, not a reading
            "label": h.get("label") or "",
            # idempotency key: the border target, so re-searching the same neighbour replaces.
            "source_ref": f"{npost}:{nregion}",
            "geometry": {"kind": "region_ref", "region_ref": region_ref},
            "linked_ground_ids": [],
            "provenance": _provenance(model=prov.get("model"), adapter=adapter, latency_ms=None,
                                      run_id=run_id, producer=PRODUCER_FIND_SIMILAR),
        })
    return out


# ── producer 4: negative_space — the first brush_field producer (CIRCUIT-001 P6-A) ────────────

def suggestion_from_negative_space(
    region: Dict[str, Any], *, run_id: Optional[str], label: Optional[str] = None,
    base_id: Optional[str] = None, grid: int = 8, threshold: float = 0.12, radius: float = 0.05,
) -> Optional[Dict[str, Any]]:
    """A committed region's figure mask → a quarantined ``brush_field`` / ``negative_space``
    soft-field suggestion, carrying editable ``strokes[]``.

    CONSUMES the mask the region ALREADY carries (``mask_rle``). It calls no segmenter and loads no
    model — the negative space is the complement of a figure that is already there — so the receipt
    names a ``run_id`` and a ``producer`` but NO model/adapter/checkpoint: nothing was inferred, only
    geometry inverted. The mark's ``geometry.kind`` is ``soft_mask`` (the mark-layer name for a soft
    field; the action-layer ``geometry_mode`` for the same thing is ``soft_field``).

    Refusal (fail-closed): a region with no id or no valid ``mask_rle`` → None; a mask whose
    complement has nothing to draw (no figure, or all figure → an all-zero field → no strokes) →
    None. A field is NEVER fabricated from absence."""
    if not isinstance(region, dict):
        return None
    region_id = region.get("id")
    rle = region.get("mask_rle")
    if not region_id or not rle_is_valid(rle):
        return None
    field, h, w = soft_field_from_mask(rle)
    strokes = strokes_from_field(field, h, w, grid=grid, threshold=threshold, radius=radius)
    if not strokes:
        return None                                     # no negative space to speak of — refuse
    if label:
        text = label
    elif region.get("label"):
        text = f"negative space around {region['label']}"
    else:
        text = "negative space"
    return {
        "producer": PRODUCER_NEGATIVE_SPACE,
        "type": "brush_field",
        "role": "negative_space",
        "label": text,
        "source_ref": str(region_id),                   # idempotency key part
        "geometry": {"kind": "soft_mask", "strokes": strokes},
        "linked_ground_ids": [],
        # A deterministic producer carries a run receipt but names no model — there was none.
        "provenance": {"run_id": run_id, "producer": PRODUCER_NEGATIVE_SPACE},
        "base_id": base_id,
    }


def suggestions_from_negative_space(
    regions: Optional[List[Dict[str, Any]]], *, run_id: Optional[str],
    grid: int = 8, threshold: float = 0.12, radius: float = 0.05,
) -> List[Dict[str, Any]]:
    """Every mask-bearing region in the packet → its negative-space suggestion. Regions without a
    usable mask are silently skipped (fail-closed); an empty or maskless input yields [] — never a
    fabricated field. Mirrors the crossing producer's degraded-input discipline."""
    out: List[Dict[str, Any]] = []
    for region in (regions or []):
        d = suggestion_from_negative_space(region, run_id=run_id, grid=grid,
                                           threshold=threshold, radius=radius)
        if d:
            out.append(d)
    return out
