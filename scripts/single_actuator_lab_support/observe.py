"""Normalising what came back — from the organ, and from the actuator wrapper around it.

Everything here is DESCRIPTIVE. Nothing in this module decides whether a mask is right; it
measures area, bounds, well-formedness, overlap and survival, which are the things a machine
can settle. The one judgement it refuses to make is the one the lab exists to protect: a mask
is not correct because it is large, confident, or cleanly encoded.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .contract import sha256_bytes

OK, EMPTY, UNAVAILABLE, ERROR = "ok", "empty", "unavailable", "error"


def rle_sha256(rle: Dict[str, Any]) -> str:
    """A stable digest of a mask. Used for repeat stability: identical hashes across repeats
    means the organ is deterministic on this input, which is a fact worth having before any
    IoU is interpreted."""
    return sha256_bytes(json.dumps(rle, sort_keys=True).encode("utf-8"))


def _runs(rle: Dict[str, Any]) -> Iterable[Tuple[int, int, int]]:
    """(start, end, value) segments over the flat column-major index space."""
    pos = 0
    val = 0
    for count in rle.get("counts") or []:
        count = int(count)
        if count:
            yield pos, pos + count, val
        pos += count
        val ^= 1


def rle_iou(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[float]:
    """Intersection over union of two RLEs, by merging runs rather than decoding.

    O(runs), not O(pixels). A 1024×1024 pair decoded twice is a million-element loop in pure
    Python per comparison, and SAM 3 can return sixteen instances — the decode-everything
    version turns a scoring pass into a visible pause, for a number nobody needs at that cost.
    """
    from backend.services.mask_geometry import rle_area, rle_is_valid
    if not (rle_is_valid(a) and rle_is_valid(b)):
        return None
    if list(a.get("size") or []) != list(b.get("size") or []):
        return None

    runs_a = [r for r in _runs(a) if r[2]]
    runs_b = [r for r in _runs(b) if r[2]]
    i = j = 0
    intersection = 0
    while i < len(runs_a) and j < len(runs_b):
        a0, a1, _ = runs_a[i]
        b0, b1, _ = runs_b[j]
        lo, hi = max(a0, b0), min(a1, b1)
        if hi > lo:
            intersection += hi - lo
        if a1 <= b1:
            i += 1
        else:
            j += 1
    union = rle_area(a) + rle_area(b) - intersection
    if union <= 0:
        return None
    return round(intersection / union, 6)


def mask_stats(rle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Everything automatically knowable about one mask. `well_formed` is structural only —
    runs that sum to h*w — and is emphatically not a claim that the extent is the right one."""
    from backend.services.mask_geometry import rle_area, rle_bbox_norm, rle_is_valid

    if not isinstance(rle, dict) or not rle_is_valid(rle):
        return {"mask_rle_sha256": rle_sha256(rle) if isinstance(rle, dict) else "",
                "area_px": 0, "area_fraction": None, "bounds": None,
                "mask_size": None, "well_formed": False}
    h, w = int(rle["size"][0]), int(rle["size"][1])
    area = rle_area(rle)
    return {
        "mask_rle_sha256": rle_sha256(rle),
        "area_px": int(area),
        "area_fraction": round(area / float(h * w), 6) if h and w else None,
        "bounds": rle_bbox_norm(rle),
        "mask_size": [h, w],
        "well_formed": True,
    }


def organ_observation(result: Optional[Dict[str, Any]], *, status: str,
                      concept: Optional[str] = None, error: Optional[str] = None,
                      detail: Optional[str] = None) -> Dict[str, Any]:
    """A `segment_concept` result → the trace's organ observation.

    THE THREE NON-OK STATUSES STAY APART. `empty` is an answer ("that concept is not in this
    picture, as far as I can measure"), `unavailable` is a non-answer (no weights, no runtime),
    and `error` is a fault. Collapsing them would make the negative control — whose PASS is an
    empty result — indistinguishable from a lab with no model installed.
    """
    result = result or {}
    instances = []
    raw: List[Dict[str, Any]] = []
    for inst in result.get("instances") or []:
        stats = mask_stats(inst.get("mask_rle"))
        instances.append({
            "index": int(inst.get("index", len(instances))),
            "confidence": inst.get("confidence"),
            **stats,
        })
        raw.append(inst.get("mask_rle"))
    return {
        # The masks themselves ride under a private key and are POPPED into
        # `observations/masks.json` before the trace is written. The trace carries their
        # digests, areas and bounds; exactly one copy of the geometry exists on disk, which is
        # the same rule the mark contract enforces on a suggestion.
        "_rles": raw,
        "status": status,
        "concept": concept if concept is not None else result.get("concept"),
        "instance_count": len(instances),
        "truncated": result.get("truncated"),
        "latency_ms": result.get("latency_ms"),
        "device": result.get("device"),
        "model": result.get("model"),
        "error": error,
        "detail": detail,
        "instances": instances,
        "repeats": [],
    }


def max_pairwise_iou(rles: List[Dict[str, Any]]) -> Optional[float]:
    """The highest overlap between any two returned instances.

    Worth recording because a high value quietly undermines the instance count: three instances
    that are 0.95 the same mask are one finding reported three times, and a reader who saw only
    `instance_count: 3` would take it for coverage.
    """
    best: Optional[float] = None
    for i in range(len(rles)):
        for j in range(i + 1, len(rles)):
            iou = rle_iou(rles[i], rles[j])
            if iou is not None and (best is None or iou > best):
                best = iou
    return best


# ── the actuator wrapper's own output ─────────────────────────────────────────────────────────

def _descriptor_summary(descriptor: Dict[str, Any]) -> Dict[str, Any]:
    """One quarantined suggestion, reduced to what attribution needs.

    The mask itself is not copied in: it already lives on the proposed region the descriptor
    references, and a trace holding a second copy would be the very thing the mark contract
    forbids — geometry inlined beside the reference to it.
    """
    from backend.services import epistemics
    geometry = descriptor.get("geometry") or {}
    return {
        "producer": descriptor.get("producer"),
        "type": descriptor.get("type"),
        "label": descriptor.get("label"),
        "source_ref": descriptor.get("source_ref"),
        "geometry_kind": geometry.get("kind"),
        "region_id": ((geometry.get("mask_ref") or geometry.get("region_ref") or {})
                      .get("region_id")),
        "status": descriptor.get(epistemics.STATUS_KEY),
        "confidence": descriptor.get("confidence"),
        "naming_withheld": descriptor.get("naming_withheld"),
        "concept_source": descriptor.get("concept_source"),
        "step_id": (descriptor.get("provenance") or {}).get("step_id"),
        "run_id": (descriptor.get("provenance") or {}).get("run_id"),
        "model": (descriptor.get("provenance") or {}).get("model"),
        "adapter": (descriptor.get("provenance") or {}).get("adapter"),
    }


def _region_summary(region: Dict[str, Any]) -> Dict[str, Any]:
    mask = region.get("mask_rle")
    return {
        "id": region.get("id"),
        "label": region.get("label"),
        "detector": region.get("detector"),
        "proposed": region.get("proposed"),
        "confidence": region.get("confidence"),
        "geometry_rev": region.get("geometry_rev"),
        "geometry_provenance": region.get("geometry_provenance"),
        "mask_rle_sha256": rle_sha256(mask) if isinstance(mask, dict) else None,
        "area_px": mask_stats(mask)["area_px"] if isinstance(mask, dict) else 0,
    }


def actuator_observation(result: Any, *, regions: List[Dict[str, Any]],
                         descriptors: List[Dict[str, Any]],
                         instance_count: int) -> Dict[str, Any]:
    """What the production `concept_segment` wrapper made of the same organ result.

    `conversion` is the attribution instrument: instances in, regions and descriptors out. When
    the organ measured three instances and one measured descriptor came out, the failure is in
    the WRAPPER and this is the only place that can say so. SF-004 has the precedent — a
    suggestion that inlines its mask is dropped silently at frontend intake, the producer ships,
    the mark never renders, and nothing fails loudly in between.
    """
    from backend.services import epistemics
    from backend.services.suggestion_service import (PRODUCER_CONCEPT_NAMING,
                                                     PRODUCER_CONCEPT_SEGMENT)

    summaries = [_descriptor_summary(d) for d in descriptors]
    measured = [s for s in summaries if s["producer"] == PRODUCER_CONCEPT_SEGMENT]
    interpretive = [s for s in summaries if s["producer"] == PRODUCER_CONCEPT_NAMING]
    withheld = [s for s in measured if s.get("naming_withheld")]

    status = getattr(result, "status", None)
    return {
        "status": status if status in (OK, EMPTY, UNAVAILABLE, ERROR) else (
            OK if measured else EMPTY),
        "detail": getattr(result, "detail", None),
        "adapter": getattr(result, "adapter", None),
        "model": getattr(result, "model", None),
        "confidence": getattr(result, "confidence", None),
        "proposed_regions": [_region_summary(r) for r in regions],
        "descriptors": summaries,
        "conversion": {
            "instances": instance_count,
            "proposed_regions": len(regions),
            "measured_descriptors": len(measured),
            "interpretive_descriptors": len(interpretive),
            "naming_withheld": len(withheld),
            # A measured extent per instance is the contract. Anything less was dropped between
            # the organ and the quarantine, and naming it `dropped` is what makes it findable.
            "dropped": max(0, instance_count - len(measured)),
            "survived": len(measured) == instance_count,
            # The two-status claim, checked rather than assumed. `measured` and `interpretive`
            # are read off `epistemics` rather than hard-coded, so a change to the status table
            # is caught here instead of silently passing.
            "statuses_seen": sorted({s["status"] for s in summaries if s["status"]}),
        },
    }


def two_status_preserved(observation: Optional[Dict[str, Any]]) -> Optional[bool]:
    """Did the wrapper emit the extent and the naming as SEPARATE claims of different kinds?

    Null when nothing was produced to check — an empty result preserves nothing and violates
    nothing, and reporting False there would turn a correct negative control into a wrapper bug.
    """
    from backend.services.epistemics import EpistemicStatus
    if not observation:
        return None
    conversion = observation.get("conversion") or {}
    if not conversion.get("measured_descriptors"):
        return None
    seen = set(conversion.get("statuses_seen") or [])
    if not conversion.get("interpretive_descriptors"):
        # Every naming was withheld below the floor. The extents still stand, and that IS the
        # contract working — the measurement does not become false because the word attached to
        # it is doubtful.
        return EpistemicStatus.MEASURED.value in seen and bool(conversion.get("naming_withheld"))
    return {EpistemicStatus.MEASURED.value, EpistemicStatus.INTERPRETIVE.value} <= seen
