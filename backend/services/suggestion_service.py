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

PRODUCER_SAM = "sam_refine"
PRODUCER_SEMANTIC = "semantic_read"

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
