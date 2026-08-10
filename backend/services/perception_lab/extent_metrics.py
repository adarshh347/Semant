"""
PERCEPTUAL-ORGANS-002 Lane B — exact mask arithmetic for the Extent organ.

Every number the Extent façade reports about two extents is computed here, on the RLE, per pixel.
Nothing in this module loads a model, opens an image, or knows what an artifact is — it takes
masks and boxes and returns numbers, so a synthetic 4×4 mask can test the same code that measures
a 1600×1200 photograph.

WHY IT IS NOT IN `mask_geometry`. That module owns the RLE ↔ mask ↔ polygon chain and is imported
by half the backend; these are comparisons BETWEEN two masks, which nothing outside the lab has
needed yet. When a second lane needs `iou`, the right move is to promote it there — not to grow a
second copy here.

THE ONE RULE. Two masks may only be compared on a SHARED RASTER. `rle_decode` gives the size back,
and every function here refuses a size mismatch rather than resampling, because a resampled
comparison is a number about neither mask. The caller gets `None`, which the façade reports as a
box-basis comparison — a coarser measurement, honestly labelled.

PURE. No database, no network, no model, no clock.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.mask_geometry import rle_decode, rle_encode, rle_is_valid

__all__ = [
    "mask_size", "same_raster", "intersection_area", "union_area", "iou",
    "mask_union", "mask_subtract", "mask_intersect",
    "box_iou", "box_of", "normalized_area",
    "pair_iou", "greedy_correspondence", "duplicate_pairs",
]


# ── raster agreement ─────────────────────────────────────────────────────────


def mask_size(rle: Optional[Mapping[str, Any]]) -> Optional[Tuple[int, int]]:
    """`(h, w)` for a valid RLE, else None. The one place `size` is read."""
    if not rle_is_valid(rle):
        return None
    size = rle.get("size") or []
    if len(size) != 2:
        return None
    return int(size[0]), int(size[1])


def same_raster(a: Optional[Mapping[str, Any]], b: Optional[Mapping[str, Any]]) -> bool:
    sa, sb = mask_size(a), mask_size(b)
    return sa is not None and sa == sb


# ── the three set operations, exact ──────────────────────────────────────────


def _bits(rle: Mapping[str, Any]) -> Tuple[bytearray, int, int]:
    return rle_decode(dict(rle))


def _combine(a: Mapping[str, Any], b: Mapping[str, Any], op: str) -> Optional[Dict[str, Any]]:
    if not same_raster(a, b):
        return None
    abits, h, w = _bits(a)
    bbits, _, _ = _bits(b)
    out = bytearray(len(abits))
    if op == "union":
        for i in range(len(abits)):
            out[i] = 1 if (abits[i] or bbits[i]) else 0
    elif op == "subtract":
        for i in range(len(abits)):
            out[i] = 1 if (abits[i] and not bbits[i]) else 0
    else:                                            # intersect
        for i in range(len(abits)):
            out[i] = 1 if (abits[i] and bbits[i]) else 0
    return rle_encode(out, h, w)


def mask_union(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """`a ∪ b`. What `extent.refine` in `add` mode means: the base, plus what the prompt found."""
    return _combine(a, b, "union")


def mask_subtract(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """`a − b`. What `extent.refine` in `subtract` mode means: the base, minus what it found."""
    return _combine(a, b, "subtract")


def mask_intersect(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    return _combine(a, b, "intersect")


# ── overlap ──────────────────────────────────────────────────────────────────


def intersection_area(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[int]:
    """Pixels in both. None when the two masks do not share a raster."""
    if not same_raster(a, b):
        return None
    abits, _, _ = _bits(a)
    bbits, _, _ = _bits(b)
    return sum(1 for i in range(len(abits)) if abits[i] and bbits[i])


def union_area(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[int]:
    if not same_raster(a, b):
        return None
    abits, _, _ = _bits(a)
    bbits, _, _ = _bits(b)
    return sum(1 for i in range(len(abits)) if abits[i] or bbits[i])


def iou(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[float]:
    """Intersection over union, per pixel. `None` on a raster mismatch, never a resample.

    Two empty masks score 1.0 — they agree completely about there being nothing there, and the
    alternative (0.0) would report two identical answers as maximally different.
    """
    inter = intersection_area(a, b)
    if inter is None:
        return None
    uni = union_area(a, b)
    if not uni:
        return 1.0
    return inter / uni


def normalized_area(rle: Optional[Mapping[str, Any]]) -> Optional[float]:
    """Mask area as a fraction of the frame. None when there is no valid mask."""
    size = mask_size(rle)
    if size is None:
        return None
    h, w = size
    frame = float(h * w)
    if frame <= 0:
        return None
    bits, _, _ = _bits(rle)
    return sum(bits) / frame


# ── the coarser fallback, kept visibly coarser ───────────────────────────────


def box_of(instance: Mapping[str, Any]) -> Optional[Dict[str, float]]:
    box = instance.get("box")
    if not isinstance(box, Mapping):
        return None
    try:
        return {k: float(box[k]) for k in ("x", "y", "w", "h")}
    except (KeyError, TypeError, ValueError):
        return None


def box_iou(a: Optional[Mapping[str, float]], b: Optional[Mapping[str, float]]) -> Optional[float]:
    """Box IoU. A SYSTEMATIC OVER-ESTIMATE of the shapes inside the boxes, and the caller is
    expected to carry `basis: box` alongside it — `epistemics.SUBSTRATE_CEILING` rules that
    interpretive, and this module does not get a say in that."""
    if not a or not b:
        return None
    ax0, ay0, ax1, ay1 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
    bx0, by0, bx1, by1 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    union = max(0.0, (ax1 - ax0) * (ay1 - ay0)) + max(0.0, (bx1 - bx0) * (by1 - by0)) - inter
    if union <= 0:
        return None
    return inter / union


# ── comparing two extents, and saying on what ────────────────────────────────


def pair_iou(a: Mapping[str, Any], b: Mapping[str, Any]) -> Tuple[Optional[float], str]:
    """`(value, basis)` for two extent-instance mappings.

    Prefers the mask, falls back to the box, and RETURNS WHICH. A comparison that did not say
    which substrate it used would let a box agreement of 0.9 read exactly like a per-pixel one,
    and the whole reason the lab reports a basis is that those two numbers mean different things.
    """
    ma, mb = a.get("mask_rle"), b.get("mask_rle")
    if rle_is_valid(ma) and rle_is_valid(mb):
        value = iou(ma, mb)
        if value is not None:
            return value, "mask"
    value = box_iou(box_of(a), box_of(b))
    return (value, "box") if value is not None else (None, "none")


def greedy_correspondence(left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]],
                          threshold: float) -> Dict[str, Any]:
    """Match each left extent to at most one right extent, best agreement first.

    GREEDY, NOT OPTIMAL, and deliberately so. A Hungarian assignment would sometimes pair a
    slightly-worse match to raise the total, which is the right answer for a scheduler and the
    wrong one for a person asking "did that instance come back". Greedy gives every extent its own
    best partner or none, which is the question being asked.

    Returns `{"correspondences", "only_in_left", "only_in_right", "bases"}` where each
    correspondence is `{"left_instance_id", "right_instance_id", "iou"}`.
    """
    scored: List[Tuple[float, int, int, str]] = []
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            value, basis = pair_iou(a, b)
            if value is not None and value >= threshold:
                scored.append((value, i, j, basis))
    # Sorted by agreement, then by index, so the result does not depend on dict ordering — a
    # comparison that shuffled between identical runs would make repeat-stability unmeasurable.
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))

    taken_left: set = set()
    taken_right: set = set()
    pairs: List[Dict[str, Any]] = []
    bases: List[str] = []
    for value, i, j, basis in scored:
        if i in taken_left or j in taken_right:
            continue
        taken_left.add(i)
        taken_right.add(j)
        bases.append(basis)
        pairs.append({
            "left_instance_id": str(left[i].get("instance_id")),
            "right_instance_id": str(right[j].get("instance_id")),
            "iou": round(float(value), 6),
        })
    return {
        "correspondences": pairs,
        "only_in_left": [str(a.get("instance_id")) for i, a in enumerate(left)
                         if i not in taken_left],
        "only_in_right": [str(b.get("instance_id")) for j, b in enumerate(right)
                          if j not in taken_right],
        "bases": bases,
    }


def duplicate_pairs(instances: Sequence[Mapping[str, Any]], threshold: float
                    ) -> List[Dict[str, Any]]:
    """Pairs WITHIN one set that may be the same thing.

    A warning, never a deletion. The plan's rule is explicit — "a duplicate instance warning does
    not silently delete either instance" — and this returns evidence for a person to act on rather
    than acting on it.
    """
    out: List[Dict[str, Any]] = []
    for i in range(len(instances)):
        for j in range(i + 1, len(instances)):
            value, _basis = pair_iou(instances[i], instances[j])
            if value is not None and value >= threshold:
                out.append({
                    "instance_ids": [str(instances[i].get("instance_id")),
                                     str(instances[j].get("instance_id"))],
                    "iou": round(float(value), 6),
                })
    out.sort(key=lambda row: (-row["iou"], row["instance_ids"]))
    return out
