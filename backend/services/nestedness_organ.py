"""
WAVE2 Lane M — the nestedness organ: a real instrument, not a narration.

The whole kernel turns on this distinction. A VLM can look at a temple and say "the finial sits
within the spire", and that sentence is `interpretive` — fluent, probably right, and grounded in
nothing a second reader could check. This module computes containment from the geometry the
segmenter actually produced, which is `measured` in the exact sense `epistemics.EpistemicStatus`
means it: **computed from the image signal**.

So this is what the epistemic wall is FOR. It is the only thing in Lane M entitled to mint a
`measured` mark, and it earns that by never reading a label. It does not know that `golden finial`
is a finial. It knows one set of pixels lies inside another.

## What it measures

    containment   area(inner ∩ outer) / area(inner) — how much of the part lies within the whole
    scale_ratio   area(inner) / area(outer)         — a part is much smaller than what holds it
    nesting_index containment × (1 − scale_ratio)

The index is that product and not something cleverer, because both factors are necessary and
neither is sufficient. Containment alone calls a region nested in itself (a thing is entirely
within itself, and `scale_ratio` 1.0 correctly drives the index to 0). Scale alone calls a small
region in the corner of the frame nested in a large one across the image. Multiplying them says
"inside, AND substantially smaller", which is what nesting is.

`margin` is measured and reported but deliberately NOT folded in: containment already punishes a
part that poked out, and a second overlapping penalty would double-count the same evidence while
making the number harder to explain. A measurement nobody can explain is one nobody can challenge.

## Mask, or box, and the record always says which

Where both regions carry a `mask_rle` the intersection is counted per pixel. Where they do not it
falls back to bounding boxes — and a box containment is a systematic OVER-estimate, because boxes
overlap where the shapes inside them do not. That is still a measurement; it is a coarser one, and
`basis` carries which was used into the mark, so a reader can discount a `box` measurement without
having to guess whether one happened. Most of this corpus is box-only, so this is the common path,
not the exotic one.

PURE. No database, no network, no model, no clock it was not handed. Geometry in, measurement out.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services import mask_geometry as mg
from backend.services import region_geometry as rg
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

ORGAN = "nestedness_organ"
ORGAN_VERSION = 1

#: The relation this organ is entitled to ground, and the axis it instantiates. One string, so the
#: organ, the axis and the structure-mapper cannot drift into three spellings of one idea.
RELATION_NESTED_WITHIN = "nested_within"

#: The axis id is FIXED rather than minted per run. `write_axis` upserts on it, so every run that
#: rediscovers nestedness lands on the one axis — two rows named `nestedness` would split every
#: retrieval along it in half and nothing downstream would report the split (Lane G's own warning).
AXIS_NESTEDNESS = "axis_nestedness"

#: A part must lie essentially wholly inside the whole. Not 1.0: segmenter boundaries are a pixel
#: or two loose, and demanding perfection would refuse real nesting for quantisation noise.
MIN_CONTAINMENT = 0.95

#: A part must be substantially smaller than what holds it. At 0.9 two near-coincident regions —
#: the same thing dissected twice, which this corpus genuinely contains — would read as nested.
MAX_SCALE_RATIO = 0.75

#: Below this the geometry is too small to trust: a region a few pixels across has a boundary that
#: is mostly quantisation error, and its containment is noise wearing a number.
MIN_AREA = 1e-6


class NestednessRefusal(Exception):
    """The organ cannot measure this pair. Raised, never returned as a zero.

    A zero index means "measured, and these are not nested". This means "not measured" — and an
    unmeasured pair must never reach `write_edge`, because the edge would then cite a mark that
    asserts a measurement nobody made.
    """


def _box_of(region: Mapping[str, Any]) -> Optional[Dict[str, float]]:
    """A region's normalized box, from its own `box` or tightened from its mask.

    Preferring the mask's tight bbox over a stored `box` is deliberate: `canonicalize_geometry`
    treats `mask_rle` as the authoritative identity and the box as a derived convenience, so where
    they disagree the mask is right.
    """
    rle = region.get("mask_rle")
    if mg.rle_is_valid(rle):
        box = mg.rle_bbox_norm(rle)
        if box["w"] > 0 and box["h"] > 0:
            return box
    raw = region.get("box")
    if not isinstance(raw, Mapping):
        return None
    try:
        box = {k: float(raw.get(k, 0.0)) for k in ("x", "y", "w", "h")}
    except (TypeError, ValueError):
        return None
    return box if box["w"] > 0 and box["h"] > 0 else None


def _mask_pair(inner: Mapping[str, Any], outer: Mapping[str, Any]
               ) -> Optional[Tuple[bytearray, bytearray, int, int]]:
    """Both masks decoded onto ONE raster, or None if that is not possible.

    Same-size only. Resampling one mask onto the other's grid to force a pixel comparison would
    invent boundary pixels and then measure them — the measurement would be of the resampler, not
    of the image. Different rasters fall back to boxes and say so.
    """
    ri, ro = inner.get("mask_rle"), outer.get("mask_rle")
    if not (mg.rle_is_valid(ri) and mg.rle_is_valid(ro)):
        return None
    if list(ri.get("size") or []) != list(ro.get("size") or []):
        return None
    bi, h, w = mg.rle_decode(ri)
    bo, _, _ = mg.rle_decode(ro)
    return bi, bo, h, w


def _measure_masks(bits_inner: bytearray, bits_outer: bytearray) -> Tuple[float, float, float]:
    """(containment, area_inner, area_outer) as pixel fractions of the raster."""
    inter = 0
    ai = ao = 0
    for a, b in zip(bits_inner, bits_outer):
        if a:
            ai += 1
            if b:
                inter += 1
        if b:
            ao += 1
    total = float(len(bits_inner)) or 1.0
    if ai == 0:
        return 0.0, 0.0, ao / total
    return inter / ai, ai / total, ao / total


def _margin(inner: Mapping[str, float], outer: Mapping[str, float]) -> float:
    """Smallest normalized gap between the part's edge and the whole's, on any side.

    Negative when the part pokes out. Reported, never folded into the index — see the module note.
    """
    return round(min(inner["x"] - outer["x"],
                     outer["x"] + outer["w"] - (inner["x"] + inner["w"]),
                     inner["y"] - outer["y"],
                     outer["y"] + outer["h"] - (inner["y"] + inner["h"])), 6)


def measure(inner: Mapping[str, Any], outer: Mapping[str, Any]) -> Dict[str, Any]:
    """Measure how far `inner` is nested within `outer`. The organ's whole job.

    Returns the measurement record — `nesting_index`, its two factors, the `basis` they were
    computed from, and `nested` against this module's stated thresholds. Raises
    `NestednessRefusal` when the geometry cannot support a measurement at all.

    Reads no label, no category and no embedding. It cannot tell you what either region depicts,
    which is exactly why what it says is checkable.
    """
    if inner is None or outer is None:
        raise NestednessRefusal("two regions are required")
    if str(inner.get("id") or "") and str(inner.get("id")) == str(outer.get("id")):
        raise NestednessRefusal(
            f"region {inner.get('id')!r} against itself — a thing is not nested within itself")

    box_inner, box_outer = _box_of(inner), _box_of(outer)
    if box_inner is None or box_outer is None:
        raise NestednessRefusal(
            "a region carries neither a valid mask nor a valid box — there is no geometry to measure")

    pair = _mask_pair(inner, outer)
    if pair is not None:
        bits_i, bits_o, _, _ = pair
        containment, area_inner, area_outer = _measure_masks(bits_i, bits_o)
        basis, basis_detail = "mask", "per-pixel intersection on a shared raster"
    else:
        containment = rg.overlap_fraction(box_inner, box_outer)
        area_inner, area_outer = rg.box_area(box_inner), rg.box_area(box_outer)
        basis = "box"
        basis_detail = ("bounding boxes — no shared mask raster. Box containment over-estimates: "
                        "boxes overlap where the shapes inside them do not.")

    if area_inner < MIN_AREA or area_outer < MIN_AREA:
        raise NestednessRefusal(
            f"degenerate geometry (areas {area_inner:.2e} / {area_outer:.2e}) — a region this small "
            "has a boundary that is mostly quantisation error")

    scale_ratio = area_inner / area_outer if area_outer > 0 else 1.0
    # Clamped: a part measured larger than its container is not 'negatively nested', it is not
    # nested, and letting the ratio exceed 1 would drive the index negative and imply a direction.
    scale_ratio = min(1.0, max(0.0, scale_ratio))
    containment = min(1.0, max(0.0, containment))
    index = round(containment * (1.0 - scale_ratio), 6)

    nested = bool(containment >= MIN_CONTAINMENT and scale_ratio <= MAX_SCALE_RATIO)
    return {
        "relation": RELATION_NESTED_WITHIN,
        "organ": ORGAN,
        "organ_version": ORGAN_VERSION,
        "nesting_index": index,
        "containment": round(containment, 6),
        "scale_ratio": round(scale_ratio, 6),
        "margin": _margin(box_inner, box_outer),
        "area_inner": round(area_inner, 8),
        "area_outer": round(area_outer, 8),
        "basis": basis,
        "basis_detail": basis_detail,
        "nested": nested,
        "thresholds": {"min_containment": MIN_CONTAINMENT, "max_scale_ratio": MAX_SCALE_RATIO},
        "inner_region_id": str(inner.get("id") or ""),
        "outer_region_id": str(outer.get("id") or ""),
        # What the organ measured, said in words a reader can check against the numbers. NOT a
        # label and not an interpretation: it names the two region ids and the basis, nothing about
        # what either region depicts.
        "detail": (f"{basis} containment {containment:.3f}, scale ratio {scale_ratio:.3f} "
                   f"→ nesting index {index:.3f}"),
    }


def find_nested_pairs(regions: Sequence[Mapping[str, Any]], *,
                      min_index: float = 0.0) -> list:
    """Every measurable nested pair among a post's regions, strongest first.

    The seed step's instrument: hand it `region_annotations` and it reports where this image
    actually holds a part within a whole. Pairs it cannot measure are skipped silently HERE — the
    caller sees a shorter list and can compare it against the region count — because a refusal per
    unmeasurable pair in an n² sweep is noise, not a coverage claim. Single measurements, where the
    caller has asserted a specific pair matters, raise instead.
    """
    out = []
    for inner in regions or []:
        for outer in regions or []:
            if inner is outer:
                continue
            try:
                m = measure(inner, outer)
            except NestednessRefusal:
                continue
            if m["nested"] and m["nesting_index"] >= min_index:
                out.append(m)
    out.sort(key=lambda m: -m["nesting_index"])
    return out


def new_mark_id() -> str:
    return f"vm_nest_{uuid4().hex[:12]}"


def measured_mark(measurement: Mapping[str, Any], *, post_id: str,
                  run_id: str = "", step_id: str = "", mark_id: str = "",
                  now: str = "") -> Dict[str, Any]:
    """The measurement, as the mark a movement edge cites.

    THIS IS THE GROUNDING. Lane G stores no `epistemic_status` on an edge and derives it from the
    mark at read time, so this mark is the only place the word `measured` is written — and it is
    written here, by the organ that did the measuring, and nowhere else in Lane M.

    `epistemic_status` is `measured` because `EpistemicStatus.MEASURED` means "computed from the
    image signal" and that is literally what happened. An organ that had asked a model whether two
    things look related would have to write `interpretive` here, and the edge would inherit it.

    The mark is RETURNED, not written. Committing it to a post is a curator's act, and this lane
    writes nothing to any post.
    """
    return {
        "id": mark_id or new_mark_id(),
        "type": "relation_mark",
        "role": RELATION_NESTED_WITHIN,
        "label": f"{measurement.get('inner_region_id')} nested within "
                 f"{measurement.get('outer_region_id')}",
        STATUS_KEY: EpistemicStatus.MEASURED.value,
        "post_id": str(post_id),
        "measurement": dict(measurement),
        "provenance": {
            "run_id": str(run_id) or None,
            "step_id": str(step_id) or None,
            "producer": ORGAN,
            "adapter": f"geometry:{measurement.get('basis')}",
            "organ_version": ORGAN_VERSION,
        },
        "created_at": now,
    }
