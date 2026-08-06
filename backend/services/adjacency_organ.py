"""WAVE3 dialogue — the adjacency organ: does this region MEET that one, and along how much of itself?

The second real organ, and it exists because the dialogue lane cannot be honest without one. Two
agents at one locus are supposed to enact two worlds; with one organ between them they would enact
the same world twice and their "disagreement" would be a difference in bookkeeping. Every other
organ in the registry loads weights and is residency-managed, so the only way to a genuine second
body was to build one that measures something else from pure geometry.

## What it measures, and why it is not nestedness in another coat

`nestedness_organ` asks **is A inside B**. This asks **does A's edge lie against B's edge**, which
is independent of the first in both directions:

    A deep inside B          nested, NOT adjacent      (its boundary is nowhere near B's)
    A at the lip of B        nested AND adjacent       (inside, but meeting the rim)
    A beside B               adjacent, NOT nested      (touching along a shared border)
    A far from B             neither

That third column is the one this lane is for. "Inside AND meeting the rim" is a claim neither
organ can make alone, and it is not a conjunction of two facts about different things — it is a
single topological fact about one pair that requires two measurements to state.

## The two bases, and the WAVE2.5 discipline

Same ruling as `nestedness_organ`, for the same reason, and it bites harder here:

    mask   ∂A against ∂B, counted per pixel on a shared raster        → `measured`
    box    an ESTIMATE from the boxes' margin                         → `interpretive`

Boundary contact off bounding boxes is a *worse* estimate than containment off bounding boxes, not
a better one: a box's edge is not the shape's edge, so two boxes can share an edge while the
shapes inside them are far apart, and two shapes can touch while their boxes' margins are wide.
The box path is kept because refusing it would leave an agent on unmasked geometry with no
adjacency world at all — but it is a falloff, it is coarse, and it says `interpretive`.

PURE. No database, no network, no model, no clock it was not handed. Geometry in, measurement out.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nestedness
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

ORGAN = "adjacency_organ"
ORGAN_VERSION = 1

#: The relation this organ grounds, and the axis it instantiates. One string each, so the organ,
#: the axis and anything reading them cannot drift into three spellings of one idea.
RELATION_MEETS = "meets"
AXIS_ADJACENCY = "axis_adjacency"

#: How much of a region's own boundary must lie against the other's before this counts as meeting
#: it. Not a hair's breadth: two shapes that graze at a corner share a boundary in the same sense
#: that two countries meeting at a point share a border, which is to say not usefully.
MIN_CONTACT = 0.02

#: On the box basis, how far apart two edges may sit and still be called touching, in normalized
#: image units. UNCALIBRATED — say so, in the voice `epistemics.MARGINAL_FACTOR` uses for such
#: numbers. 0.01 is one percent of the frame, chosen because it is roughly the width of a
#: segmenter's disagreement with itself, not because it was measured on anything. It only ever
#: affects readings that are already `interpretive`, which is why an uncalibrated constant is
#: tolerable here and would not be on the mask path.
BOX_TOLERANCE = 0.01

#: Below this a boundary is too short to trust: a region a few pixels across is mostly quantisation
#: error, and the fraction of it touching anything is noise wearing a number.
MIN_BOUNDARY_PIXELS = 8

#: Reused rather than restated. The whole point of WAVE2.5 is that ONE table says what each basis
#: supports; a second organ with its own copy would be the drift the ruling exists to end.
BASIS_EPISTEMIC = nestedness.BASIS_EPISTEMIC
ADMISSIBLE_BASIS = nestedness.ADMISSIBLE_BASIS


class AdjacencyRefusal(Exception):
    """The organ cannot measure this pair. Raised, never returned as a zero.

    A zero contact fraction means "measured, and these do not meet". This means "not measured" —
    and the two must never collapse, because an unmeasurable pair reported as `not adjacent` is a
    claim about the picture made from an absence of evidence.
    """


def epistemic_for(basis: str) -> str:
    """What kind of knowing a reading on this basis is. Delegated, not re-decided."""
    return nestedness.epistemic_for(basis)


def is_admissible(measurement: Optional[Mapping[str, Any]]) -> bool:
    return nestedness.is_admissible(measurement)


# ── the mask path: ∂A against ∂B, per pixel ─────────────────────────────────

def _boundary(bits: bytearray, h: int, w: int) -> bytearray:
    """The pixels of a mask that have a 4-neighbour outside it — its own edge.

    The frame counts as outside, so a region running off the edge of the image has a boundary
    there. That is the honest reading: the shape ends at the frame, and whether it continues
    beyond is not something this image can say.
    """
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


def _contact(edge_a: bytearray, edge_b: bytearray, h: int, w: int) -> Tuple[int, int]:
    """(pixels of ∂A lying against ∂B, |∂A|).

    "Against" is 8-connected — a diagonal touch is a touch. 4-connectivity would miss the very
    common case of two masks meeting along a staircase edge, which is what a rasterised diagonal
    boundary always is, and would report two shapes that visibly share a border as disjoint.
    """
    area_a = touching = 0
    for y in range(h):
        row = y * w
        for x in range(w):
            i = row + x
            if not edge_a[i]:
                continue
            area_a += 1
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= h:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if xx < 0 or xx >= w or (dx == 0 and dy == 0):
                        continue
                    if edge_b[yy * w + xx]:
                        touching += 1
                        break
                else:
                    continue
                break
    return touching, area_a


def _mask_pair(a: Mapping[str, Any], b: Mapping[str, Any]):
    """Both masks decoded onto ONE raster, or None.

    Same-size only, exactly as `nestedness_organ._mask_pair` requires and for the same reason:
    resampling one mask onto the other's grid would invent boundary pixels and then measure them,
    which for a BOUNDARY organ would not be a coarser measurement but a measurement of the
    resampler.
    """
    ra, rb = a.get("mask_rle"), b.get("mask_rle")
    if not (mg.rle_is_valid(ra) and mg.rle_is_valid(rb)):
        return None
    if list(ra.get("size") or []) != list(rb.get("size") or []):
        return None
    bits_a, h, w = mg.rle_decode(ra)
    bits_b, _, _ = mg.rle_decode(rb)
    return bits_a, bits_b, h, w


# ── the box path: an estimate, and it says so ───────────────────────────────

def _box_of(region: Mapping[str, Any]) -> Optional[Dict[str, float]]:
    return nestedness._box_of(region)


def _edge_gap(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    """How far A's box sits from B's nearest edge, in normalized units. 0 means it lands on it.

    This is `nestedness_organ._margin` read for a different purpose. There, a positive margin means
    the part is comfortably inside and the number is reported and set aside. Here the SAME number
    answers the question directly: a margin near zero is a part at the rim, which is what meeting
    an edge means, and a large margin — inside or outside — is a part that does not meet it.
    """
    return abs(min(a["x"] - b["x"],
                   b["x"] + b["w"] - (a["x"] + a["w"]),
                   a["y"] - b["y"],
                   b["y"] + b["h"] - (a["y"] + a["h"])))


# ── the measurement ─────────────────────────────────────────────────────────

def measure(a: Mapping[str, Any], b: Mapping[str, Any]) -> Dict[str, Any]:
    """Measure how much of `a`'s boundary lies against `b`'s. The organ's whole job.

    Reads no label, no category and no embedding — it cannot tell you what either region depicts,
    which is exactly why what it says is checkable.
    """
    if a is None or b is None:
        raise AdjacencyRefusal("two regions are required")
    if str(a.get("id") or "") and str(a.get("id")) == str(b.get("id")):
        raise AdjacencyRefusal(
            f"region {a.get('id')!r} against itself — a thing does not meet its own edge")

    pair = _mask_pair(a, b)
    if pair is not None:
        bits_a, bits_b, h, w = pair
        edge_a, edge_b = _boundary(bits_a, h, w), _boundary(bits_b, h, w)
        touching, boundary_len = _contact(edge_a, edge_b, h, w)
        if boundary_len < MIN_BOUNDARY_PIXELS:
            raise AdjacencyRefusal(
                f"boundary of {boundary_len} px is below {MIN_BOUNDARY_PIXELS} — too short to "
                f"carry a contact fraction that means anything")
        contact = touching / float(boundary_len)
        basis, gap = "mask", None
        detail_basis = "per-pixel boundary contact on a shared raster"
    else:
        box_a, box_b = _box_of(a), _box_of(b)
        if box_a is None or box_b is None:
            raise AdjacencyRefusal(
                "a region carries neither a valid mask nor a valid box — there is no geometry")
        gap = _edge_gap(box_a, box_b)
        # A falloff rather than a threshold, so a reader can see how near "near" was. Still an
        # estimate: these are the boxes' edges, not the shapes'.
        contact = max(0.0, 1.0 - (gap / BOX_TOLERANCE)) if BOX_TOLERANCE > 0 else 0.0
        basis = "box"
        detail_basis = (f"box edge margin {gap:.4f} against a {BOX_TOLERANCE} tolerance — an "
                        f"ESTIMATE of contact: a box's edge is not the shape's edge")
        boundary_len = 0

    contact = min(1.0, max(0.0, contact))
    adjacent = bool(contact >= MIN_CONTACT)
    return {
        "relation": RELATION_MEETS,
        "organ": ORGAN,
        "organ_version": ORGAN_VERSION,
        "contact_fraction": round(contact, 6),
        "boundary_pixels": boundary_len,
        "edge_gap": (round(gap, 6) if gap is not None else None),
        "basis": basis,
        "basis_detail": detail_basis,
        "adjacent": adjacent,
        "thresholds": {"min_contact": MIN_CONTACT, "box_tolerance": BOX_TOLERANCE},
        "inner_region_id": str(a.get("id") or ""),
        "outer_region_id": str(b.get("id") or ""),
        # Names the two region ids and the basis, nothing about what either depicts.
        "detail": (f"{basis} boundary contact {contact:.3f}"
                   + (f" over {boundary_len} px" if basis == "mask"
                      else f" (edge margin {gap:.4f})")),
    }


def find_adjacent_pairs(regions: Sequence[Mapping[str, Any]], *,
                        min_contact: float = MIN_CONTACT) -> list:
    """Every measurable meeting among a post's regions, strongest first. The god's-eye sweep.

    Present for the same reason `nestedness_organ.find_nested_pairs` is — so a situated field can
    be COMPARED against the unsituated reading and partiality can be counted rather than asserted.
    No agent may call it about its own world.
    """
    out = []
    for a in regions or []:
        for b in regions or []:
            if a is b:
                continue
            try:
                m = measure(a, b)
            except AdjacencyRefusal:
                continue
            if m["adjacent"] and m["contact_fraction"] >= min_contact:
                out.append(m)
    out.sort(key=lambda m: -m["contact_fraction"])
    return out


def new_mark_id() -> str:
    return f"vm_adj_{uuid4().hex[:12]}"


def grounding_mark(measurement: Mapping[str, Any], *, post_id: str,
                   run_id: str = "", step_id: str = "", mark_id: str = "",
                   now: str = "") -> Dict[str, Any]:
    """The measurement, as the mark a claim cites.

    Named and shaped exactly like `nestedness_organ.grounding_mark`, deliberately: two organs whose
    marks a reader has to tell apart by shape would make the dialogue layer's job a parsing problem
    instead of an epistemic one. The status is DERIVED from the basis and never assumed — this
    organ has no `measured_mark` to be renamed later, because it was born after the ruling.

    RETURNED, not written. Committing it to a post is a curator's act.
    """
    return {
        "id": mark_id or new_mark_id(),
        "type": "relation_mark",
        "role": RELATION_MEETS,
        "label": f"{measurement.get('inner_region_id')} meets "
                 f"{measurement.get('outer_region_id')}",
        STATUS_KEY: epistemic_for(measurement.get("basis")),
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
