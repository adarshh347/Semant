"""WAVE3 — the depth organ: the sense that can measure what a bounding box fakes.

Every fabrication the WAVE2.5 ruling routed around exists because this system could not measure
occlusion order. `cseg_golden_finial_7` scored containment 1.000 and nesting index 0.999 against
'Sky' — and the finial is in FRONT of the sky. A bounding box in a 2D projection cannot tell
`inside` from `in front of`, and the ruling's answer was to refuse the box basis rather than to
resolve the question, because nothing in the system could answer it.

This organ is the sense that could. **It does not resolve the finial case** — that needs an
`in_front_of` RELATION, which needs the systematicity gate the floor lane is reworking, and which
deserves its own design. This lane adds the measurement such a relation would stand on.

## What it measures, over one region

    depth_mean     mean inverse depth over the region — LARGER IS NEARER
    relief         how much depth varies within it: a flat facade vs a receding one
    gradient       which way depth runs across it, and how hard
    frame_rank     what fraction of the frame's depth cells lie BEHIND this region

`frame_rank` is the number a future occlusion relation would use, and it is worth being exact about
what it is not. It is a property of ONE region read against the frame it is in — like asking how
tall someone is, not who is taller. It relates the region to no other region, grounds nothing, and
this module mints no relation of any kind. See `direction="field"` on the reading.

## PURE, and the model is somebody else's job

This module imports no torch, no transformers and no image library. It takes a DEPTH FIELD — the
coarse grid `depth_service.estimate` already returns — exactly as `chroma_organ` takes pixels, and
for the reason `depth_service`'s own docstring gives: "the map is reduced to a coarse grid of block
means before it leaves this module, which is the shape the pure converters consume — so the field
logic stays testable with synthetic maps and no GPU."

So there are TWO organs here and conflating them is the mistake this module avoids:

    depth_anything_v2_small   the MODEL. On the roster since VISION-MODEL-MATRIX-001, a
                              `Capability.DEPTH` GPU adapter, residency-managed by `ModelManager`,
                              ceiling `measured`. It runs ONCE PER IMAGE.
    depth_organ               the SENSE. Reads a region's depth out of that field, declares its
                              substrates, and mints the mark an agent reports.

The same split `concept_segment` / `concept_naming` makes one level down.

## Why the field must be estimated on the WHOLE frame, never a crop

Monocular depth is a global inference. Run it on a crop and you get depth relative to the crop,
which is meaningless for occlusion order — the whole point is where this region sits against
everything else in the same projection. `assert_whole_frame` refuses a field that says it was
cropped, because a cropped field and a frame field are the same shape and produce the same numbers,
and only one of them means anything.

## The two substrates (TWO-STATUS-001), and here the argument is not an analogy

    mask   depth sampled over the region's own shape        → `measured`
    box    depth sampled over the bounding rectangle        → `interpretive`

For chroma the box argument was "a box around a spire includes the sky, and sky is cold". Here it is
the SAME PIXELS and the SAME failure that forced WAVE2.5: a box around the finial includes the sky
behind it, so a box-basis depth reading averages the finial's depth with the sky's and lands
somewhere between. That number is not a noisier estimate of the finial's depth. It is the arithmetic
mean of a thing and the thing it is in front of — which is precisely the confusion the mask ruling
exists to prevent, arriving in the one modality that could otherwise have detected it.

## Provenance is required, not optional

A synthetic depth grid and a real one are the same list of floats. `measure` refuses a field that
does not name the model and revision that produced it, because a mark whose provenance says nothing
is a mark that cannot be told apart from a fixture.

No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services import epistemics
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nestedness
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

ORGAN = "depth_organ"
ORGAN_VERSION = 1

#: The roster adapter this sense expects its field to come from. Named so a mark says which model
#: stood behind it, and so `assert_field_valid` can refuse a field from somewhere else — a depth
#: grid from an unpinned checkpoint is not the same measurement and must not read as one.
SOURCE_ADAPTER = "depth_anything_v2_small"

#: What this organ reports. A FIELD on one region, never a relation between two. `in_front_of` is
#: the relation this measurement would ground and it is deliberately not in this lane: it needs the
#: systematicity gate the floor lane is reworking, and a relation minted here would arrive before
#: the gate that judges it.
FIELD_DEPTH = "depth_field"

#: A region must land on at least this many grid cells before its depth means anything. The field
#: is coarse by construction (`depth_service.GRID` is 16 over the whole frame), so a small region
#: can cover a single cell — and one cell's block mean is the depth of that cell, not of the region.
MIN_CELLS = 4

#: A cell counts as inside the region when at least this much of it is. Below that the cell's mean
#: is mostly whatever is behind or beside the region, which is the error the mask basis exists to
#: avoid — and here that error is the finial-and-sky average itself.
MIN_CELL_COVERAGE = 0.25

#: Below this spread there is no direction to report, only floating-point noise between equal cell
#: means. The chroma lane shipped a `dx=-0.19` on a uniform region before this gate existed; the
#: same arithmetic is here, so the same gate is.
MIN_DEPTH_SPREAD = 1e-9

#: Reused, never restated — TWO-STATUS-001 put the ruling in one place so a fourth organ could not
#: arrive with a fifth copy of it.
BASIS_EPISTEMIC = nestedness.BASIS_EPISTEMIC
ADMISSIBLE_BASIS = nestedness.ADMISSIBLE_BASIS


class DepthRefusal(Exception):
    """The organ cannot read this region. Raised, never returned as a flat field.

    A depth spread of 0.0 means "measured, and this region is flat to the camera". This means "not
    measured" — and an unread region reported as flat is a claim about what is in front of what,
    made from an absence of evidence, in the one organ built to stop exactly that.
    """


class Incommensurable(Exception):
    """Two readings from different senses, asked to be compared on one scale.

    Raised rather than answered, and re-raised here rather than imported from `chroma_organ` so the
    refusal is a fact about EVERY pair of senses rather than a quirk of the first one that had two.
    """


def epistemic_for(basis: str) -> str:
    """What kind of knowing a reading on this basis is. Delegated, not re-decided."""
    return epistemics.substrate_ceiling(basis).value


def is_admissible(measurement: Optional[Mapping[str, Any]]) -> bool:
    return nestedness.is_admissible(measurement)


# ── the field this organ reads ──────────────────────────────────────────────

def depth_field(estimate: Mapping[str, Any], *, adapter: str, model: str, revision: str,
                preprocessing_version: str = "", whole_frame: bool = True) -> Dict[str, Any]:
    """A `depth_service.estimate` result + who produced it → the field this organ accepts.

    A separate constructor rather than a convention, because the provenance is the whole difference
    between a measurement and a fixture: the grid alone is a list of floats and a synthetic one is
    indistinguishable from a real one. Whoever ran the model is the only thing that knows which
    model it was, and this is where they say so.
    """
    grid = int(estimate.get("grid") or 0)
    return {
        "depth": [float(v) for v in (estimate.get("depth") or [])],
        "grid": grid,
        "adapter": str(adapter),
        "model": str(model),
        "revision": str(revision),
        "preprocessing_version": str(preprocessing_version),
        # Declared rather than inferred: a cropped field and a frame field are the same shape.
        "whole_frame": bool(whole_frame),
    }


def assert_field_valid(field: Optional[Mapping[str, Any]]) -> None:
    """Raise unless this is a depth field that says where it came from and what it covers."""
    if not field:
        raise DepthRefusal(
            "no depth field was handed to the organ. A depth reading with no field behind it is "
            "not a shallow reading, it is not a reading — and an agent bound to this organ with no "
            "field perceives NOTHING, which `organs.invoke` must report as such")

    depth, grid = field.get("depth"), int(field.get("grid") or 0)
    if not depth or grid <= 0 or len(depth) != grid * grid:
        raise DepthRefusal(
            f"malformed depth field: grid={grid}, {len(depth or [])} values. A field whose shape "
            f"does not match its own declared grid cannot be indexed, and indexing it anyway would "
            f"read one region's depth at another region's coordinates")

    if not field.get("whole_frame"):
        raise DepthRefusal(
            "this field declares it was not estimated on the whole frame. Monocular depth is a "
            "GLOBAL inference: run on a crop it gives depth relative to the crop, which is "
            "meaningless for occlusion order — and it looks exactly like a frame field")

    if str(field.get("adapter") or "") != SOURCE_ADAPTER:
        raise DepthRefusal(
            f"this field names adapter {field.get('adapter')!r}, not {SOURCE_ADAPTER!r}. A depth "
            f"grid from another model is another measurement and must not read as this one")

    if not (field.get("model") and field.get("revision")):
        raise DepthRefusal(
            "this field names no model/revision. A mark whose provenance says nothing is a mark "
            "that cannot be told apart from a fixture, and this organ mints `measured` claims")


# ── which cells the region covers ───────────────────────────────────────────

def _mask_cells(region: Mapping[str, Any], grid: int) -> Optional[List[float]]:
    """Per-cell coverage of the region's MASK on the depth grid, or None.

    Coverage rather than membership: the depth grid is coarse and a region's mask is not, so the
    honest question per cell is how much of it the region occupies. `MIN_CELL_COVERAGE` then does
    the work that a nearest-neighbour membership test would fake.
    """
    rle = region.get("mask_rle")
    if not mg.rle_is_valid(rle):
        return None
    bits, h, w = mg.rle_decode(rle)
    if h <= 0 or w <= 0:
        return None
    counts = [0] * (grid * grid)
    totals = [0] * (grid * grid)
    for y in range(h):
        gy = min(grid - 1, y * grid // h)
        row = y * w
        for x in range(w):
            i = gy * grid + min(grid - 1, x * grid // w)
            totals[i] += 1
            if bits[row + x]:
                counts[i] += 1
    return [(counts[i] / totals[i]) if totals[i] else 0.0 for i in range(grid * grid)]


def _box_cells(region: Mapping[str, Any], grid: int) -> Optional[List[float]]:
    """The same, for the region's BOUNDING BOX — every cell the rectangle touches, weighted."""
    box = nestedness._box_of(region)
    if box is None:
        return None
    x0, x1 = box["x"], box["x"] + box["w"]
    y0, y1 = box["y"], box["y"] + box["h"]
    out = [0.0] * (grid * grid)
    for gy in range(grid):
        cy0, cy1 = gy / grid, (gy + 1) / grid
        oy = max(0.0, min(cy1, y1) - max(cy0, y0)) * grid
        if oy <= 0:
            continue
        for gx in range(grid):
            cx0, cx1 = gx / grid, (gx + 1) / grid
            ox = max(0.0, min(cx1, x1) - max(cx0, x0)) * grid
            if ox > 0:
                out[gy * grid + gx] = ox * oy
    return out


def _gradient(depth: Sequence[float], coverage: Sequence[float], grid: int) -> Dict[str, Any]:
    """Which way depth runs across the region — the near centroid minus the far one.

    The same centroid-difference shape `chroma_organ._gradient` uses, and gated on the spread for
    the same reason: on a region that is flat to the camera every cell mean is equal to within float
    error, `v > mean` still partitions them, and the centroids of two arbitrary halves sit apart. A
    measurement of nothing must not acquire a direction.
    """
    cells = [(i, depth[i]) for i in range(grid * grid) if coverage[i] >= MIN_CELL_COVERAGE]
    flat = {"dx": 0.0, "dy": 0.0, "magnitude": 0.0, "cells_covered": len(cells),
            "detail": "flat to the camera across every covered cell"}
    if len(cells) < 2:
        return {**flat, "detail": "too few covered cells to say which way depth runs"}

    mean = sum(v for _, v in cells) / len(cells)
    near = [(i, v) for i, v in cells if v > mean]     # inverse depth: larger is NEARER
    far = [(i, v) for i, v in cells if v <= mean]
    if not near or not far:
        return flat
    spread = (sum(v for _, v in near) / len(near)) - (sum(v for _, v in far) / len(far))
    if abs(spread) < MIN_DEPTH_SPREAD:
        return flat

    def centroid(group):
        xs = sum((i % grid) + 0.5 for i, _ in group) / len(group)
        ys = sum((i // grid) + 0.5 for i, _ in group) / len(group)
        return xs / grid, ys / grid

    nx, ny = centroid(near)
    fx, fy = centroid(far)
    return {
        "dx": round(nx - fx, 6), "dy": round(ny - fy, 6),
        "magnitude": round(abs(spread), 6),
        "cells_covered": len(cells),
        "detail": (f"depth runs ({nx - fx:+.2f}, {ny - fy:+.2f}) toward the near side across "
                   f"{len(cells)} covered cells, spread {spread:.4f}"),
    }


# ── the measurement ─────────────────────────────────────────────────────────

def measure(region: Mapping[str, Any], field: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Read the depth field over one region. The organ's whole job.

    Reads no label, no category and no embedding — it cannot tell you what the region depicts, which
    is exactly why what it says is checkable.
    """
    if region is None:
        raise DepthRefusal("a region is required")
    assert_field_valid(field)

    grid = int(field["grid"])
    depth = list(field["depth"])

    coverage = _mask_cells(region, grid)
    basis = "mask"
    if coverage is None:
        coverage = _box_cells(region, grid)
        basis = "box"
    if coverage is None:
        raise DepthRefusal(
            f"region {region.get('id')!r} carries neither a valid mask nor a valid box — there is "
            f"nowhere to read")

    inside = [i for i in range(grid * grid) if coverage[i] >= MIN_CELL_COVERAGE]
    if len(inside) < MIN_CELLS:
        raise DepthRefusal(
            f"the region covers {len(inside)} depth cells, below {MIN_CELLS}. The field is coarse "
            f"by construction, and one cell's block mean is the depth of that CELL rather than of "
            f"this region — reporting it would be measuring the grid")

    values = [depth[i] for i in inside]
    depth_mean = sum(values) / len(values)
    relief = max(values) - min(values)

    # What fraction of the WHOLE FRAME lies behind this region. A property of one region read
    # against its frame — not a relation, and it grounds none. See the module docstring.
    behind = sum(1 for v in depth if v < depth_mean)
    frame_rank = behind / float(len(depth))

    gradient = _gradient(depth, coverage, grid)

    return {
        "field": FIELD_DEPTH,
        "organ": ORGAN,
        "organ_version": ORGAN_VERSION,
        "region_id": str(region.get("id") or ""),
        # INVERSE depth throughout, in the model's own raw scale: larger is nearer. Not converted
        # to metres, because it is not metres — Depth-Anything gives relative depth and calling it
        # a distance would be the units arriving from nowhere.
        "depth_mean": round(depth_mean, 6),
        "relief": round(relief, 6),
        "frame_rank": round(frame_rank, 6),
        "gradient": gradient,
        "cells": len(inside),
        "grid": grid,
        "basis": basis,
        "basis_detail": (
            "sampled over the region's own mask" if basis == "mask" else
            "sampled over the BOUNDING BOX — an ESTIMATE, and the WAVE2.5 case exactly: a box "
            "around a part contains what the part is IN FRONT OF, so this averages the two"),
        "thresholds": {"min_cells": MIN_CELLS, "min_cell_coverage": MIN_CELL_COVERAGE},
        "source": {"adapter": field.get("adapter"), "model": field.get("model"),
                   "revision": field.get("revision"),
                   "preprocessing_version": field.get("preprocessing_version")},
        "detail": (f"{basis} depth {depth_mean:.4f} (inverse; larger is nearer), relief "
                   f"{relief:.4f} over {len(inside)} cells, {frame_rank:.0%} of the frame behind "
                   f"it — {gradient['detail']}"),
    }


def compare_across_senses(*_readings: Mapping[str, Any]) -> float:
    """Refuses. There is no scale on which a depth field and a nesting index are comparable.

    The chroma lane established the discipline and this repeats it deliberately rather than
    importing it: the point is that EVERY pair of senses is incommensurable until somebody earns
    the comparison, not that the first organ to have a neighbour was a special case. Inverse depth
    in a model's raw scale, a nesting index in [0, 1] and a warmth mean in [-1, 1] are three
    different quantities that happen to be floats.
    """
    raise Incommensurable(
        "a depth mean is in the model's own inverse-depth scale, a nesting index is a ratio of "
        "areas, and a warmth mean is an opponent-channel average. There is no common scale, this "
        "lane does not invent one, and the senses coexist at a locus WITHOUT a forced comparison. "
        "Relating them is cross-modal grounding and it is a later lane's whole subject.")


def new_mark_id() -> str:
    return f"vm_dep_{uuid4().hex[:12]}"


def grounding_mark(measurement: Mapping[str, Any], *, post_id: str,
                   run_id: str = "", step_id: str = "", mark_id: str = "",
                   now: str = "") -> Dict[str, Any]:
    """The measurement, as the mark a claim cites. RETURNED, not written.

    `field_mark` rather than `relation_mark`, because it relates nothing. The provenance names the
    MODEL that produced the depth as well as this organ that read it — two producers stand behind
    this number and a mark naming only one of them would leave the weighted half anonymous.

    `producer` is the organ, and it is the name `epistemics.guard` classifies. The model's identity
    rides in `provenance.model`/`revision`, where `weights.manifest.json` and WEIGHTS-001 already
    expect to find such a thing.
    """
    basis = str(measurement.get("basis") or "")
    source = dict(measurement.get("source") or {})
    return {
        "id": mark_id or new_mark_id(),
        "type": "field_mark",
        "role": FIELD_DEPTH,
        "label": f"depth field over {measurement.get('region_id')}",
        STATUS_KEY: epistemic_for(basis),
        epistemics.SUBSTRATE_KEY: basis,
        "post_id": str(post_id),
        "measurement": dict(measurement),
        "provenance": {
            "run_id": str(run_id) or None,
            "step_id": str(step_id) or None,
            "producer": ORGAN,
            "adapter": source.get("adapter") or SOURCE_ADAPTER,
            "model": source.get("model"),
            "revision": source.get("revision"),
            "preprocessing_version": source.get("preprocessing_version"),
            "organ_version": ORGAN_VERSION,
        },
        "created_at": now,
    }


def read_regions(regions: Sequence[Mapping[str, Any]],
                 field: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Every region this organ can read, nearest first. The god's-eye sweep.

    Present for the same reason `nestedness_organ.find_nested_pairs` is — so a situated field can be
    COMPARED against the unsituated reading and partiality can be counted rather than asserted. No
    agent may call it about its own world.
    """
    out: List[Dict[str, Any]] = []
    for region in regions or []:
        try:
            out.append(measure(region, field))
        except DepthRefusal:
            continue
    out.sort(key=lambda m: -m["depth_mean"])
    return out
