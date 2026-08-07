"""WAVE3 — the chroma organ: the first sense in this system that is not geometry.

`nestedness_organ` asks whether A is inside B. `adjacency_organ` asks whether A's edge lies against
B's. Both answer questions about SHAPE, so two agents carrying one each enact two geometric worlds —
different, genuinely, but the same KIND of world. This one reads the signal itself: how warm the
light is across a region, and which way that warmth runs.

That is the point of the lane. An agent bound to this organ and an agent bound to a geometric one,
standing on the same region at the same instant, do not disagree about a shared world — they enact
worlds that have almost nothing to say to each other. Which is the first honest instance of the
problem named at the bottom of this docstring.

## What it measures

Over the pixels the region actually occupies:

    warmth        a red-versus-blue opponent value per pixel, averaged     ∈ [-1, 1]
    chroma        how far from grey the colour sits, averaged              ∈ [0, 1]
    gradient      which way warmth RUNS across the region, and how hard    (dx, dy, magnitude)

The gradient is the part that makes this a FIELD rather than a swatch. A uniformly warm wall and a
wall lit warm on one side are the same `warmth_mean` and completely different things to stand in;
an organ that reported only the average would erase the difference and never say it had.

## The two substrates (TWO-STATUS-001, and this is the first organ built on it)

    mask   the region's own pixels, per pixel                   → `measured`
    box    the bounding rectangle's pixels                      → `interpretive`

The box path is an ESTIMATE and it is a worse one here than it is for containment. A bounding box
around a spire includes the sky behind it, and sky is the coldest thing in most of this corpus — so
a box-basis warmth reading of a warm object against a cold ground is not a slightly noisier number,
it is a number about a different subject. It is kept because refusing it would leave an agent on
unmasked geometry with no chromatic world at all, and it says `interpretive` every time.

## The naming is a SECOND producer, not a second status

"warm" / "cool" / "neutral" is a word with an uncalibrated threshold behind it. Per
`DECISION-two-status-producer-declares-its-substrates` §8 — *if a curator could accept the field and
reject the name, they are two descriptors* — and a curator plainly could: the field is a number
computed from the pixels, the name is a convention about where warm begins. So `chroma_organ` emits
the field and `chroma_naming` emits the word, exactly as `concept_segment` and `concept_naming` do
for a SAM 3 result, and rejecting the word costs you nothing you measured.

## COMMENSURABILITY IS NAMED HERE, NOT SOLVED

A nesting index and a warmth mean are both floats in [-1, 1] or [0, 1], and that is a coincidence of
encoding, not a common scale. There is no defensible answer to "is this nesting stronger than that
warmth", and this module deliberately does not invent one: no shared magnitude, no normalisation
against geometry, no combined score. `compare_across_senses` exists and refuses, so that the absence
is a thing a caller runs into rather than a thing nobody wrote down.

Two senses coexisting at one locus without a forced comparison is the honest state of the art here.
Making them relatable is a cross-modal grounding problem and it is a later lane's whole subject.

PURE. No database, no network, no model, no image library, no clock it was not handed. Pixels in —
through a tiny duck-typed protocol so the tests can hand it a synthetic raster and never import
PIL — measurement out.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services import epistemics
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nestedness
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

ORGAN = "chroma_organ"
ORGAN_VERSION = 1

#: The second producer: the WORD, never the number. It declares no substrate, because a naming is
#: interpretive whatever it was computed from — there is no version of "warm" that is a measurement.
NAMING_PRODUCER = "chroma_naming"

#: What this organ reports. Not a relation between two regions — a FIELD on one — and the vocabulary
#: says so, because calling it a relation would put it in the movement kernel's path, where a
#: chromatic relation belongs only after the systematicity floor is settled. That is a later lane.
FIELD_WARMTH = "warmth_field"

#: The sampling raster. Coarse on purpose and for the same reason `cpu_perceptual_service` reduces
#: to a 16×16 grid: a field is a felt region, not a per-pixel segmentation, and reading every pixel
#: of a 4000px photograph in Python to average it would cost a hundred times more for a number that
#: moves in the third decimal.
SAMPLE = 64

#: The gradient grid — how many cells the region is divided into to ask which way warmth runs.
GRADIENT_GRID = 6

#: A cell needs this share of its area inside the mask before it counts toward the gradient. Below
#: it the cell's mean is mostly whatever is outside the region, which is exactly the error the mask
#: basis exists to avoid.
MIN_CELL_COVERAGE = 0.25

#: Fewer sampled pixels than this and there is no field to speak of. UNCALIBRATED — said plainly, in
#: the voice `epistemics.MARGINAL_FACTOR` and `adjacency_organ.BOX_TOLERANCE` use for such numbers.
#: 64 is one thousandth of the sample raster, chosen because a region thinner than that is mostly
#: edge, not because it was measured on anything.
MIN_SAMPLED_PIXELS = 64

#: Below this warmth spread between the warm and cool halves there is no direction to report, only
#: floating-point noise. It is not a quality threshold — the magnitude would already be ~0 — it is
#: about `dx`/`dy`, which are a CENTROID DIFFERENCE and stay finite however small the spread gets.
#: A uniform region was reporting `dx=-0.19` off last-bit differences between identical cell means,
#: which reads as a direction and is not one. UNCALIBRATED in the sense that any number a few orders
#: above float error would do; 1e-6 is that.
MIN_WARMTH_SPREAD = 1e-6

#: Where "warm" begins. UNCALIBRATED, and the reason the naming is a separate producer rather than a
#: second status on the field: this number is a convention, the warmth mean is not.
WARM_THRESHOLD = 0.05

#: Reused, never restated. TWO-STATUS-001 put the ruling in one place precisely so a third organ
#: could not arrive with a fourth copy of it.
BASIS_EPISTEMIC = nestedness.BASIS_EPISTEMIC
ADMISSIBLE_BASIS = nestedness.ADMISSIBLE_BASIS


class ChromaRefusal(Exception):
    """The organ cannot read this region. Raised, never returned as a neutral field.

    A warmth of 0.0 means "measured, and this region is neither warm nor cool". This means "not
    measured" — and the two must never collapse, because an unread region reported as neutral grey
    is a claim about the picture made from an absence of light.
    """


class Incommensurable(Exception):
    """Two readings from different senses, asked to be compared on one scale.

    Raised rather than answered. See the module docstring: a nesting index and a warmth mean are
    both small floats and that is an accident of encoding. This exception is the honest form of the
    open problem — a caller that wants the comparison finds out that nobody has earned it yet.
    """


def epistemic_for(basis: str) -> str:
    """What kind of knowing a reading on this basis is. Delegated, not re-decided."""
    return epistemics.substrate_ceiling(basis).value


def is_admissible(measurement: Optional[Mapping[str, Any]]) -> bool:
    return nestedness.is_admissible(measurement)


# ── sampling: the only thing here that touches an image ──────────────────────

def image_frame(image: Any, *, source: str, whole_frame: bool = True) -> Dict[str, Any]:
    """An image + WHERE IT CAME FROM → the frame this organ accepts. Mirrors `depth_organ`.

    ORGAN-PROVENANCE-001 added this, and the audit that found it is worth repeating because the
    number is unpleasant. `measure` used to take a bare image and index the region's mask against
    whatever it was handed. Hand it the frame and hand it a crop of the same frame, and the SAME
    region gives:

        on the frame   warmth +0.6923
        on a crop      warmth -0.6923

    Same call, same region, same mark shape, `measured` both times — and the sign flipped, because
    the mask's coordinates are the frame's coordinates and mean nothing against a crop. There was no
    way to tell the two marks apart afterwards: the mark named the organ, the basis and the region,
    and nothing at all about the pixels it read.

    `depth_organ` closed exactly this for itself (`assert_field_valid`), for exactly this reason —
    "a cropped field and a frame field are the same shape". This is the same contract one modality
    over, and the asymmetry it corrects is a real one: the geometry organs read the POST'S OWN
    `region_annotations`, so there is no second artifact that could be the wrong one. Chroma and
    depth read an artifact handed in from outside, and only an external artifact can silently be a
    different picture.

    `source` is free-form on purpose — a `photo_url`, a fixture name, a run id. What matters is that
    something identifies the pixels; this module cannot check a URL and does not pretend to.
    """
    return {"image": image, "source": str(source), "whole_frame": bool(whole_frame)}


def assert_frame_valid(frame: Optional[Mapping[str, Any]]) -> None:
    """Raise unless this is an image frame that says what it is and where it came from."""
    if frame is None:
        raise ChromaRefusal(
            "no pixels were handed to the organ. A chromatic reading with no image behind it is "
            "not a dim reading, it is not a reading — and an agent bound to this organ with no "
            "image perceives NOTHING, which `organs.invoke` must report as such")

    if not isinstance(frame, Mapping) or "image" not in frame:
        raise ChromaRefusal(
            "a bare image is no longer enough: wrap it with `chroma_organ.image_frame(image, "
            "source=...)`. The mask's coordinates are the FRAME's coordinates, so an image that is "
            "not that frame produces a confident number about a different subject — and the mark "
            "is identical either way. See `image_frame` for the reading that made this a rule.")

    if frame.get("image") is None:
        raise ChromaRefusal("the frame carries no image")

    if not frame.get("whole_frame"):
        raise ChromaRefusal(
            "this frame declares it is not the whole picture. The region's mask is indexed in the "
            "FRAME's coordinate space; against a crop those coordinates address different pixels, "
            "and the reading would be a measurement of somewhere else")

    if not str(frame.get("source") or ""):
        raise ChromaRefusal(
            "this frame names no source. A mark whose provenance says nothing about the pixels it "
            "read cannot be told apart from one read off a fixture, and this organ mints "
            "`measured` claims")


def sample_rgb(image: Any, size: int = SAMPLE) -> Tuple[List[Tuple[int, int, int]], int, int]:
    """An image → a flat row-major list of (r, g, b) at `size × size`.

    DUCK-TYPED on purpose. Everything used here — `convert("RGB")`, `resize((w, h))`, `getdata()` —
    is the intersection of PIL's API and about fifteen lines of a stub, so the tests hand this a
    synthetic raster and the organ's own test file imports no image library at all. An organ whose
    tests need PIL installed is an organ whose behaviour is partly PIL's.

    The caller supplies the pixels. This module never opens a file or a URL, exactly as
    `cpu_perceptual_service.analyze` takes an already-cropped image and asks no questions about
    where it came from.
    """
    if image is None:
        raise ChromaRefusal("no pixels were handed to the organ")
    rgb = image.convert("RGB").resize((int(size), int(size)))
    return [tuple(px[:3]) for px in rgb.getdata()], int(size), int(size)


def _warmth(px: Tuple[int, int, int]) -> float:
    """One pixel → where it sits on the warm/cool axis, in [-1, 1].

    Red minus blue over their sum: the crudest honest opponent channel, and deliberately crude.
    A perceptually uniform space (CIELAB b*, say) would be better and would need a white point this
    corpus does not record — an organ that assumed one would be reporting its assumption. What this
    computes is exactly what it says: how much more red than blue this pixel is.
    """
    r, b = float(px[0]), float(px[2])
    total = r + b
    return 0.0 if total <= 0 else (r - b) / total


def _chroma(px: Tuple[int, int, int]) -> float:
    """How far from grey, in [0, 1]. The HSV saturation, which needs no white point to be true."""
    hi, lo = max(px[0], px[1], px[2]), min(px[0], px[1], px[2])
    return 0.0 if hi <= 0 else (hi - lo) / float(hi)


def _mask_bits(region: Mapping[str, Any], h: int, w: int) -> Optional[List[int]]:
    """The region's mask resampled to the sample raster as a membership test, or None.

    NEAREST-NEIGHBOUR, and unlike `adjacency_organ` — which refuses to resample because inventing
    boundary pixels for a BOUNDARY organ would be measuring the resampler — that is sound here.
    This organ averages over an interior; a pixel misassigned at the edge shifts a mean over
    thousands of pixels by a hair, and the alternative (sampling the image at mask resolution) would
    mean decoding a full-resolution raster in Python for a number that moves in the third decimal.
    """
    rle = region.get("mask_rle")
    if not mg.rle_is_valid(rle):
        return None
    bits, mh, mw = mg.rle_decode(rle)
    if mh <= 0 or mw <= 0:
        return None
    out = [0] * (h * w)
    for y in range(h):
        my = min(mh - 1, y * mh // h)
        for x in range(w):
            mx = min(mw - 1, x * mw // w)
            out[y * w + x] = 1 if bits[my * mw + mx] else 0
    return out


def _box_bits(region: Mapping[str, Any], h: int, w: int) -> Optional[List[int]]:
    """The region's bounding box as a membership test on the sample raster, or None."""
    box = nestedness._box_of(region)
    if box is None:
        return None
    x0, x1 = int(box["x"] * w), int(round((box["x"] + box["w"]) * w))
    y0, y1 = int(box["y"] * h), int(round((box["y"] + box["h"]) * h))
    out = [0] * (h * w)
    for y in range(max(0, y0), min(h, max(y0 + 1, y1))):
        for x in range(max(0, x0), min(w, max(x0 + 1, x1))):
            out[y * w + x] = 1
    return out


def _gradient(warmth: Sequence[float], member: Sequence[int], h: int, w: int,
              grid: int = GRADIENT_GRID) -> Dict[str, Any]:
    """Which way warmth runs across the region, from cell means on a coarse grid.

    A centroid difference rather than a fitted plane: the warm cells' centre of mass minus the cool
    cells', in normalized region coordinates. It is robust to the ragged cell coverage a real mask
    produces, and it degrades to a zero vector when the region is uniform — which is the correct
    answer for a uniform region, and distinguishable from a refusal.
    """
    sums = [0.0] * (grid * grid)
    counts = [0] * (grid * grid)
    cell_area = (h / grid) * (w / grid)

    for y in range(h):
        gy = min(grid - 1, y * grid // h)
        for x in range(w):
            if not member[y * w + x]:
                continue
            i = gy * grid + min(grid - 1, x * grid // w)
            sums[i] += warmth[y * w + x]
            counts[i] += 1

    cells = [(i, sums[i] / counts[i]) for i in range(grid * grid)
             if counts[i] and counts[i] >= MIN_CELL_COVERAGE * cell_area]
    covered = len(cells)
    if covered < 2:
        return {"dx": 0.0, "dy": 0.0, "magnitude": 0.0, "cells_covered": covered,
                "cells": grid * grid,
                "detail": "too few covered cells to say which way warmth runs"}

    mean = sum(v for _, v in cells) / covered
    warm = [(i, v) for i, v in cells if v > mean]
    cool = [(i, v) for i, v in cells if v <= mean]
    uniform = {"dx": 0.0, "dy": 0.0, "magnitude": 0.0, "cells_covered": covered,
               "cells": grid * grid, "detail": "uniform across every covered cell"}
    if not warm or not cool:
        return uniform

    def centroid(group):
        xs = sum((i % grid) + 0.5 for i, _ in group) / len(group)
        ys = sum((i // grid) + 0.5 for i, _ in group) / len(group)
        return xs / grid, ys / grid

    spread = (sum(v for _, v in warm) / len(warm)) - (sum(v for _, v in cool) / len(cool))
    # THE DIRECTION IS GATED ON THE SPREAD, not the other way round. On a uniform region every cell
    # mean is equal to within float error, so `v > mean` still splits them — into two arbitrary
    # groups whose centroids sit apart. The magnitude correctly reads 0.0 and the vector reads like
    # a finding. Reporting the vector anyway is how a measurement of nothing acquires a direction.
    if abs(spread) < MIN_WARMTH_SPREAD:
        return uniform

    wx, wy = centroid(warm)
    cx, cy = centroid(cool)
    dx, dy = wx - cx, wy - cy
    return {
        "dx": round(dx, 6), "dy": round(dy, 6),
        # The magnitude is the WARMTH SPREAD, not the geometric distance: how much warmer the warm
        # half is. A region split hard into hot and cold and one that shades gently across have the
        # same centroid separation and are not the same field.
        "magnitude": round(abs(spread), 6),
        "cells_covered": covered, "cells": grid * grid,
        "detail": (f"warmth runs ({dx:+.2f}, {dy:+.2f}) across {covered}/{grid * grid} covered "
                   f"cells, spread {spread:.3f}"),
    }


# ── the measurement ─────────────────────────────────────────────────────────

def measure(region: Mapping[str, Any], frame: Optional[Mapping[str, Any]], *,
            size: int = SAMPLE) -> Dict[str, Any]:
    """Read the warmth field over one region. The organ's whole job.

    `frame` is a declared image frame (`image_frame`), not a bare image — see `assert_frame_valid`
    for why, and for the +0.6923 / -0.6923 reading that made it a requirement.

    Reads no label, no category and no embedding — it cannot tell you what the region depicts, which
    is exactly why what it says is checkable.
    """
    if region is None:
        raise ChromaRefusal("a region is required")
    assert_frame_valid(frame)
    pixels, h, w = sample_rgb(frame["image"], size)

    member = _mask_bits(region, h, w)
    basis = "mask"
    if member is None:
        member = _box_bits(region, h, w)
        basis = "box"
    if member is None:
        raise ChromaRefusal(
            f"region {region.get('id')!r} carries neither a valid mask nor a valid box — there is "
            f"nowhere to read")

    warmth = [_warmth(px) for px in pixels]
    idx = [i for i in range(h * w) if member[i]]
    if len(idx) < MIN_SAMPLED_PIXELS:
        raise ChromaRefusal(
            f"{len(idx)} sampled pixels is below {MIN_SAMPLED_PIXELS} — too little of the region "
            f"landed on the sample raster to carry a field that means anything")

    warmth_mean = sum(warmth[i] for i in idx) / len(idx)
    chroma_mean = sum(_chroma(pixels[i]) for i in idx) / len(idx)
    gradient = _gradient(warmth, member, h, w)

    return {
        "field": FIELD_WARMTH,
        "organ": ORGAN,
        "organ_version": ORGAN_VERSION,
        "region_id": str(region.get("id") or ""),
        "warmth_mean": round(warmth_mean, 6),
        "chroma_mean": round(chroma_mean, 6),
        "gradient": gradient,
        "sampled_pixels": len(idx),
        "sample_size": h,
        "coverage": round(len(idx) / float(h * w), 6),
        "basis": basis,
        "source": {"image": str(frame.get("source") or ""),
                   "whole_frame": bool(frame.get("whole_frame"))},
        "basis_detail": (
            "per-pixel over the region's own mask" if basis == "mask" else
            "per-pixel over the BOUNDING BOX — an ESTIMATE, and a poor one here: a box around a "
            "spire includes the sky behind it, so this may be a number about a different subject"),
        "thresholds": {"min_sampled_pixels": MIN_SAMPLED_PIXELS,
                       "min_cell_coverage": MIN_CELL_COVERAGE},
        "detail": (f"{basis} warmth {warmth_mean:+.3f}, chroma {chroma_mean:.3f} over "
                   f"{len(idx)} px — {gradient['detail']}"),
    }


def name_of(measurement: Mapping[str, Any]) -> Dict[str, Any]:
    """The WORD for a warmth field. A second producer, and interpretive whatever the substrate was.

    `WARM_THRESHOLD` is a convention and nothing in the picture votes on it. Separating this from
    the field is what lets a curator keep a warmth of +0.043 and throw away the claim that +0.043
    is "warm" — the CONCEPT-SEG-001 shape, which the two-status decision names as the right answer
    whenever the two halves are separably acceptable.
    """
    warmth = float(measurement.get("warmth_mean") or 0.0)
    mood = "warm" if warmth > WARM_THRESHOLD else ("cool" if warmth < -WARM_THRESHOLD else "neutral")
    return {
        "producer": NAMING_PRODUCER,
        "field": FIELD_WARMTH,
        "region_id": str(measurement.get("region_id") or ""),
        "mood": mood,
        "threshold": WARM_THRESHOLD,
        # NO `basis`, and its absence is the claim: this word would be interpretive on any
        # substrate, so naming one would suggest a substrate could make it something else.
        STATUS_KEY: EpistemicStatus.INTERPRETIVE.value,
        "detail": (f"called {mood!r} because warmth {warmth:+.3f} falls "
                   f"{'above' if mood == 'warm' else 'below' if mood == 'cool' else 'within'} "
                   f"±{WARM_THRESHOLD} — an UNCALIBRATED convention, not a measurement"),
    }


def compare_across_senses(*_readings: Mapping[str, Any]) -> float:
    """Refuses. There is no scale on which a warmth field and a nesting index are comparable.

    This function exists so the absence is REACHABLE. A missing function is indistinguishable from
    a function nobody has needed yet; this one says, at the point somebody wants the number, that
    nobody has earned it — and that inventing a shared magnitude here would be the single easiest
    way to make this system confident about something it has never measured.
    """
    raise Incommensurable(
        "a warmth mean and a nesting index are both small floats, and that is a fact about "
        "floating point rather than about the picture. There is no common scale, this lane does "
        "not invent one, and the two senses coexist at a locus WITHOUT a forced comparison. "
        "Relating them is cross-modal grounding and it is a later lane's whole subject.")


def new_mark_id() -> str:
    return f"vm_chr_{uuid4().hex[:12]}"


def grounding_mark(measurement: Mapping[str, Any], *, post_id: str,
                   run_id: str = "", step_id: str = "", mark_id: str = "",
                   now: str = "") -> Dict[str, Any]:
    """The measurement, as the mark a claim cites. RETURNED, not written.

    Shaped like `nestedness_organ.grounding_mark` and `adjacency_organ.grounding_mark`, and typed
    `field_mark` rather than `relation_mark` because it relates nothing: it is a reading over ONE
    region. A chromatic RELATION between two regions is deliberately not in this lane — grounding
    one needs the systematicity treatment the floor lane is auditing, and a relation minted here
    would arrive before the gate that judges it.

    `epistemic_basis` is written FLAT as well, which the geometry organs do not do. They predate
    TWO-STATUS-001 and carry `measurement.basis`, which `epistemics.substrate_of` reads; a mark
    born after the contract should name its substrate in the contract's own key.
    """
    basis = str(measurement.get("basis") or "")
    return {
        "id": mark_id or new_mark_id(),
        "type": "field_mark",
        "role": FIELD_WARMTH,
        "label": f"warmth field over {measurement.get('region_id')}",
        STATUS_KEY: epistemic_for(basis),
        epistemics.SUBSTRATE_KEY: basis,
        "post_id": str(post_id),
        "measurement": dict(measurement),
        "provenance": {
            "run_id": str(run_id) or None,
            "step_id": str(step_id) or None,
            "producer": ORGAN,
            "adapter": f"chroma:{basis}",
            # WHICH PIXELS. Without this the mark is the same shape whatever image it read, which
            # is how a crop reading and a frame reading became indistinguishable.
            "image_source": (measurement.get("source") or {}).get("image"),
            "organ_version": ORGAN_VERSION,
        },
        "created_at": now,
    }


def read_regions(regions: Sequence[Mapping[str, Any]],
                 frame: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Every region this organ can read, warmest first. The god's-eye sweep.

    Present for the same reason `nestedness_organ.find_nested_pairs` is — so a situated field can be
    COMPARED against the unsituated reading and partiality can be counted rather than asserted. No
    agent may call it about its own world.
    """
    out: List[Dict[str, Any]] = []
    for region in regions or []:
        try:
            out.append(measure(region, frame))
        except ChromaRefusal:
            continue
    out.sort(key=lambda m: -m["warmth_mean"])
    return out
