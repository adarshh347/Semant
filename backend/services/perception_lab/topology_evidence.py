"""
PERCEPTUAL-ORGANS-002 Lane C — the geometry the Topology façade shows a person.

`nestedness_organ` and `adjacency_organ` already answer the two questions this laboratory asks
about a pair — is A inside B, does A's edge lie against B's — and this module does not answer them
again. What it adds is the thing an organ built for a movement graph never needed: **where**.

    nestedness_organ   containment 0.97                       a number
    this module        …and the inner shape's boundary runs    a locus a person can look at
                       0.004 from the outer's at its nearest

A relation graph made of numbers alone is a laboratory that asks a person to trust it. The lab's
whole gate is that a person can INSPECT the measurement, so every relation this lane emits carries
the locus the number came from: the contact band's own bounding box, the intersection's own
bounding box, the nearest approach and where it happens. All of it in the same
`normalized_xy_topleft` convention `Region.box` uses, so the frontend draws it with the stage
geometry it already has.

WHY FLAT FLOAT KEYS. `TopologyRelation.measurements` is `Dict[str, float]` in the merged contract —
deliberately, so a relation cannot smuggle a mask into the place a reader looks for a number. A
locus therefore travels as four floats (`contact_locus_x/_y/_w/_h`) rather than as a nested box.
That is the contract's clamp working as intended, and the price is a naming convention rather than
a nested object.

PURE. No database, no network, no model, no clock. Bits in, floats out.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services import mask_geometry as mg

#: A mask whose set-pixel count is below this is treated as no extent at all. It is 1 rather than a
#: fraction on purpose: an EMPTY mask is a different thing from a small one, and the façade refuses
#: the first while measuring the second. `nestedness_organ.MIN_AREA` already rules on smallness.
MIN_MASK_PIXELS = 1

#: The 8-neighbourhood, as offsets. `adjacency_organ._contact` counts contact 8-connected because a
#: rasterised diagonal boundary is a staircase and 4-connectivity reports two shapes that visibly
#: share a border as disjoint. The contact LOCUS has to agree with the contact FRACTION, so it uses
#: the same neighbourhood rather than a second opinion about what touching means.
_NEIGHBOURS_8: Tuple[Tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))

_DIAG = math.sqrt(2.0)


class GeometryUnavailable(Exception):
    """There is nothing here to measure — no valid mask, an empty one, or two different rasters.

    Raised rather than returned as a zero, for the reason every organ in this repository gives:
    a zero overlap means "measured, and they do not overlap", and an unmeasurable pair reported as
    zero is a claim about the picture made from an absence of evidence.
    """


# ── decoding, once, onto one raster ──────────────────────────────────────────


class Raster:
    """One decoded mask, and the frame it was decoded on.

    Holds the bit buffer rather than the RLE because everything below walks pixels, and decoding
    the same mask twice in an all-pairs sweep is the cost `nestedness_organ._decode` already
    learned to cache away.
    """

    __slots__ = ("bits", "h", "w", "area")

    def __init__(self, bits: bytearray, h: int, w: int) -> None:
        self.bits = bits
        self.h = h
        self.w = w
        self.area = sum(1 for b in bits if b)

    @property
    def size(self) -> Tuple[int, int]:
        return (self.h, self.w)


def decode(rle: Optional[Mapping[str, Any]]) -> Raster:
    """A COCO RLE → a `Raster`. Raises when there is no usable mask, including an empty one."""
    if not mg.rle_is_valid(rle):
        raise GeometryUnavailable("no valid mask_rle")
    bits, h, w = mg.rle_decode(dict(rle))
    raster = Raster(bits, h, w)
    if raster.area < MIN_MASK_PIXELS:
        raise GeometryUnavailable(
            "the mask is empty — zero set pixels. An empty extent is not a small extent: there is "
            "nothing in the frame for a relation to have an endpoint at")
    return raster


def same_raster(a: Raster, b: Raster) -> None:
    """Raise unless two masks were decoded on one grid.

    Same-size only, exactly as `nestedness_organ._mask_pair` and `adjacency_organ._mask_pair`
    require and for the same reason: resampling one mask onto the other's grid invents boundary
    pixels and then measures them, and the measurement is of the resampler.
    """
    if a.size != b.size:
        raise GeometryUnavailable(
            f"masks on different rasters ({a.size} and {b.size}) — resampling one onto the other "
            f"would invent the pixels the measurement is made of")


# ── loci: where the number came from ─────────────────────────────────────────


def bbox_of(bits: Sequence[int], h: int, w: int) -> Optional[Dict[str, float]]:
    """The tight normalized bbox of a bit buffer, or None when nothing is set.

    Same convention and rounding as `mask_geometry.rle_bbox_norm`, over a buffer rather than an
    RLE, because these buffers are intermediate (an intersection, a contact band) and encoding them
    back into an RLE purely to take a bbox would cost a full column-major walk for four numbers.
    """
    minr = minc = 1 << 30
    maxr = maxc = -1
    for r in range(h):
        base = r * w
        for c in range(w):
            if bits[base + c]:
                if r < minr:
                    minr = r
                if r > maxr:
                    maxr = r
                if c < minc:
                    minc = c
                if c > maxc:
                    maxc = c
    if maxr < 0:
        return None
    return {"x": round(minc / w, 6), "y": round(minr / h, 6),
            "w": round((maxc - minc + 1) / w, 6), "h": round((maxr - minr + 1) / h, 6)}


def locus_keys(prefix: str, box: Optional[Mapping[str, float]]) -> Dict[str, float]:
    """A normalized box → four flat float keys, or nothing when there is no locus.

    Absent rather than zeroed when there is no locus. `{"contact_locus_x": 0.0, ...}` is a box at
    the top-left corner of the image, which is a place; the honest record of "these do not touch
    anywhere" is that the keys are not there.
    """
    if not box:
        return {}
    return {f"{prefix}_x": float(box["x"]), f"{prefix}_y": float(box["y"]),
            f"{prefix}_w": float(box["w"]), f"{prefix}_h": float(box["h"])}


# ── mask arithmetic: the intersection, exactly ───────────────────────────────


def intersection(a: Raster, b: Raster) -> Dict[str, Any]:
    """Exact per-pixel intersection of two masks on one raster.

    Returns the intersecting bits, the counts, and the two fractions — of A and of B — because
    "half of the small one and a twentieth of the large one" is one intersection described two
    ways, and a single `iou` would hide the asymmetry that tells a person which is which.
    """
    same_raster(a, b)
    inter = bytearray(len(a.bits))
    count = 0
    for i, bit in enumerate(a.bits):
        if bit and b.bits[i]:
            inter[i] = 1
            count += 1
    union = a.area + b.area - count
    return {
        "bits": inter,
        "pixels": count,
        "area_source": a.area,
        "area_target": b.area,
        "fraction_of_source": (count / a.area) if a.area else 0.0,
        "fraction_of_target": (count / b.area) if b.area else 0.0,
        "iou": (count / union) if union else 0.0,
        "locus": bbox_of(inter, a.h, a.w),
    }


# ── the contact band, and where it runs ──────────────────────────────────────


def boundary(raster: Raster) -> bytearray:
    """The mask's own edge: set pixels with a 4-neighbour outside the mask.

    `adjacency_organ._boundary` in this module's own terms — same rule, including the frame
    counting as outside, so a shape running off the edge of the image has a boundary there. Not
    imported, because that function is private to an organ whose signature is `(bits, h, w)` and
    this module carries the raster; the RULE is the shared thing and it is stated identically.
    """
    bits, h, w = raster.bits, raster.h, raster.w
    out = bytearray(len(bits))
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            if not bits[i]:
                continue
            if (x == 0 or not bits[i - 1]) or (x == w - 1 or not bits[i + 1]) or \
               (y == 0 or not bits[i - w]) or (y == h - 1 or not bits[i + w]):
                out[i] = 1
    return out


def contact_band(a: Raster, b: Raster, *, tolerance_px: int = 0) -> Dict[str, Any]:
    """Where ∂A lies against ∂B, as a locus and a count.

    `tolerance_px` dilates the second boundary before contact is counted — the contract's
    `contact_tolerance_px`, which exists because two masks segmented separately from the same
    picture routinely miss each other by a pixel of quantisation. Zero means literal 8-connected
    adjacency, and the value used is reported so a reader can see what "touching" meant here.

    The band returned is the part of ∂A that touches, NOT a line between centroids. The contract
    asks for the actual contact band because a centroid line is a picture of two ids, not of a
    measurement — it looks identical whether the shapes meet along their whole length or at a
    corner.
    """
    same_raster(a, b)
    h, w = a.h, a.w
    edge_a, edge_b = boundary(a), boundary(b)
    near_b = _dilate(edge_b, h, w, tolerance_px) if tolerance_px > 0 else edge_b

    band = bytearray(len(edge_a))
    touching = 0
    perimeter = 0
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            if not edge_a[i]:
                continue
            perimeter += 1
            if _touches(near_b, h, w, x, y):
                band[i] = 1
                touching += 1
    return {
        "bits": band,
        "pixels": touching,
        "perimeter_pixels": perimeter,
        "fraction_of_source_perimeter": (touching / perimeter) if perimeter else 0.0,
        "tolerance_px": int(tolerance_px),
        "locus": bbox_of(band, h, w),
    }


def _touches(mask: Sequence[int], h: int, w: int, x: int, y: int) -> bool:
    """Is any 8-neighbour of (x, y) set? The neighbourhood `adjacency_organ` counts contact in."""
    for dy, dx in _NEIGHBOURS_8:
        yy, xx = y + dy, x + dx
        if 0 <= yy < h and 0 <= xx < w and mask[yy * w + xx]:
            return True
    return False


def _dilate(bits: Sequence[int], h: int, w: int, radius: int) -> bytearray:
    """Chebyshev dilation by `radius`. Square rather than circular on purpose.

    The tolerance is a pixel budget for segmenter disagreement, not a physical distance, and a
    circular structuring element would imply a precision the budget does not have.
    """
    out = bytearray(bits)
    for _ in range(max(0, radius)):
        step = bytearray(out)
        for y in range(h):
            row = y * w
            for x in range(w):
                if out[row + x]:
                    continue
                if _touches(out, h, w, x, y):
                    step[row + x] = 1
        out = step
    return out


# ── clearance: how far apart, and where they come nearest ────────────────────


def clearance(a: Raster, b: Raster) -> Dict[str, Any]:
    """The nearest approach between two masks, in pixels and normalized units, and where.

    A two-pass chamfer distance transform from B, read at A's boundary — the same transform
    `mask_geometry.soft_field_from_mask` runs, taken to a different question. Chamfer rather than
    exact Euclidean because the answer is a separation a person reads next to a picture, and the
    chamfer's few-percent error over that is smaller than the boundary's own uncertainty.

    Zero means they touch. `nearest_x` / `nearest_y` is the point ON A that comes closest, so a
    person can be shown WHERE the gap is rather than only how wide.
    """
    same_raster(a, b)
    h, w = a.h, a.w
    dist = _chamfer(b.bits, h, w)
    edge_a = boundary(a)
    best = None
    at = (0, 0)
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            if not edge_a[i]:
                continue
            d = dist[i]
            if best is None or d < best:
                best, at = d, (x, y)
    if best is None:                                # pragma: no cover - a non-empty mask has an edge
        raise GeometryUnavailable("the source mask has no boundary to measure from")
    diagonal = math.hypot(h, w) or 1.0
    return {
        "pixels": round(float(best), 4),
        "normalized": round(float(best) / diagonal, 6),
        "nearest_x": round((at[0] + 0.5) / w, 6),
        "nearest_y": round((at[1] + 0.5) / h, 6),
    }


def _chamfer(bits: Sequence[int], h: int, w: int) -> List[float]:
    """Distance from every pixel to the nearest set pixel of `bits`. Two passes, 3-4 chamfer."""
    n = h * w
    inf = float(h + w) * 2.0 + 1.0
    dist = [0.0 if bits[i] else inf for i in range(n)]
    for r in range(h):
        base = r * w
        for c in range(w):
            i = base + c
            if bits[i]:
                continue
            d = dist[i]
            if c > 0:
                d = min(d, dist[i - 1] + 1.0)
            if r > 0:
                d = min(d, dist[i - w] + 1.0)
                if c > 0:
                    d = min(d, dist[i - w - 1] + _DIAG)
                if c < w - 1:
                    d = min(d, dist[i - w + 1] + _DIAG)
            dist[i] = d
    for r in range(h - 1, -1, -1):
        base = r * w
        for c in range(w - 1, -1, -1):
            i = base + c
            if bits[i]:
                continue
            d = dist[i]
            if c < w - 1:
                d = min(d, dist[i + 1] + 1.0)
            if r < h - 1:
                d = min(d, dist[i + w] + 1.0)
                if c < w - 1:
                    d = min(d, dist[i + w + 1] + _DIAG)
                if c > 0:
                    d = min(d, dist[i + w - 1] + _DIAG)
            dist[i] = d
    return dist


def containment_clearance(inner: Raster, outer: Raster) -> Dict[str, Any]:
    """How much room the inner shape has inside the outer one — the containment boundary.

    The distance from ∂inner to the OUTSIDE of `outer`, so a part sitting comfortably within its
    whole reads a large clearance and one pressed against the rim reads ~0. Negative is not
    representable and is not wanted: a part that pokes out is reported by `containment` being below
    1.0, and a second signed number would double-count the same evidence — the reason
    `nestedness_organ` reports `margin` and refuses to fold it into the index.
    """
    same_raster(inner, outer)
    h, w = inner.h, inner.w
    outside = bytearray(1 if not b else 0 for b in outer.bits)
    dist = _chamfer(outside, h, w)
    edge = boundary(inner)
    best = None
    at = (0, 0)
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            if not edge[i]:
                continue
            if best is None or dist[i] < best:
                best, at = dist[i], (x, y)
    if best is None:                                # pragma: no cover - a non-empty mask has an edge
        raise GeometryUnavailable("the inner mask has no boundary to measure from")
    diagonal = math.hypot(h, w) or 1.0
    return {
        "pixels": round(float(best), 4),
        "normalized": round(float(best) / diagonal, 6),
        "nearest_x": round((at[0] + 0.5) / w, 6),
        "nearest_y": round((at[1] + 0.5) / h, 6),
    }


# ── negative space: the shape of what this is not ────────────────────────────


def negative_space(figures: Sequence[Raster], *, max_distance: float) -> Dict[str, Any]:
    """The union of the figures → the complement → a distance field over it.

    `max_distance` is normalized against the frame diagonal and TRUNCATES the field: everything
    beyond it reads 1.0. Truncation rather than rescaling, because a field normalized to its own
    deepest point — which is what `mask_geometry.soft_field_from_mask` returns — is not comparable
    between two images, and the laboratory's whole point is comparing runs.

    Returns the raw field alongside its statistics. The field is large and the merged contract
    keeps it out of the payload behind an optional `field_ref`; this lane has no store to put it
    in, so it hands it to its caller and Lane F decides where it lives.
    """
    if not figures:
        raise GeometryUnavailable("negative space is measured against a figure, and none resolved")
    first = figures[0]
    for other in figures[1:]:
        same_raster(first, other)
    h, w = first.h, first.w
    union = bytearray(len(first.bits))
    for raster in figures:
        for i, bit in enumerate(raster.bits):
            if bit:
                union[i] = 1
    figure_pixels = sum(1 for b in union if b)
    if figure_pixels >= h * w:
        raise GeometryUnavailable(
            "the figures cover the whole frame — there is no negative space to measure, which is a "
            "fact about the geometry and not a field of zeros")

    diagonal = math.hypot(h, w) or 1.0
    ceiling = max(1e-9, float(max_distance) * diagonal)
    dist = _chamfer(union, h, w)
    field = [0.0 if union[i] else min(1.0, dist[i] / ceiling) for i in range(h * w)]

    ground = [dist[i] / diagonal for i in range(h * w) if not union[i]]
    deepest = max(ground) if ground else 0.0
    return {
        "field": field,
        "shape": [h, w],
        "figure_pixels": figure_pixels,
        "ground_pixels": len(ground),
        "statistics": {
            "ground_fraction": round(len(ground) / float(h * w), 6),
            "max_clearance_normalized": round(deepest, 6),
            "mean_clearance_normalized": round(sum(ground) / len(ground), 6) if ground else 0.0,
            "truncated_at_normalized": round(float(max_distance), 6),
            "saturated_fraction": round(
                sum(1 for v in field if v >= 1.0) / float(h * w), 6),
        },
    }


__all__ = ["MIN_MASK_PIXELS", "GeometryUnavailable", "Raster", "decode", "same_raster", "bbox_of",
           "locus_keys", "intersection", "boundary", "contact_band", "clearance",
           "containment_clearance", "negative_space"]
