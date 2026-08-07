"""
WAVE3 — chromatic rhyme: the relation that asks whether two warmth fields ECHO, not whether they match.

Depth became relational with `in_front_of`. Chroma was still perceive-only. This is its relation.

## The statistic question, which the occlusion lane made compulsory

That lane built difference-of-means first and it failed on the one case it existed for: `in_front_of`
is an ORDERING relation and orderings are answered by an ordering statistic (dominance), not a
magnitude one. The lesson generalised: **pick the statistic that matches the relation type.**

So what is a chromatic rhyme? Not two regions with the same average warmth — a terracotta wall and a
sunset sky can share a mean and have nothing to say to each other. A rhyme is a correspondence of
INTERNAL STRUCTURE: warmth running the same way across both, gathering and falling off together.

    the relation           the statistic it needs
    ────────────────────   ─────────────────────────────────────────────
    in_front_of / order    dominance — P(a cell of A reads nearer than B)
    rhyme / correspondence SHAPE CORRELATION — do the two fields co-vary, cell by cell,
                           after each is centred on its own mean

**Centring is the whole design.** Each field has its own mean subtracted before comparison, so a
shared average cannot contribute to the score — it is not merely down-weighted, it is arithmetically
removed. "Not a mean-warmth match" is a property of the statistic rather than a threshold on top of
it, which is why it is checkable rather than promised.

The fields are resampled onto a canonical grid over each region's OWN bounding box, so a small
region and a large one on the other side of the corpus can rhyme. Position and size drop out;
only the shape of the variation is left.

## What the corpus said

10 images, 307 usable region fields, 65,642 cross-image pairs at the floors below.

**The tail is real, and this was checked rather than assumed.** A permutation null — the same two
fields with one shuffled, which destroys the correspondence while keeping every value, variance and
count exactly — gives:

    r > 0.7      1154 real        1 null      (65,642 pairs)
    r > 0.8       237 real        0 null
    r > 0.9        20 real        0 null

Whatever is in that tail is spatial correspondence, because the null has the same numbers in a
different arrangement and produces none of it.

**Coincidence does not score.** Of 8,510 pairs whose mean warmth matches within 0.02, 0.27% clear
0.8 — *below* the 0.36% base rate. Sharing an average confers no advantage at all. The clearest
single case: `fine_6 ~ cseg_secondary_domes_6`, mean gap **0.0008**, rhyme **+0.049**. Nearly
identical average warmth, no correspondence, correctly not a rhyme.

**There is no valley.** The distribution over all pairs is smooth and unimodal about zero
(p25 −0.25, p50 +0.00, p75 +0.26). `MIN_RHYME` is a free parameter, declared as one per
[[DECISION-systematicity-floor-is-a-free-parameter]] — but unlike a bare choice it is placed where
the null tail has vanished entirely, which is a weaker claim than a derivation and a stronger one
than taste.

## The absence-credit trap, excluded by construction

The `present`-aggregation lesson: two absences must not aggregate into an agreement. A flat field has
zero variance, and the correlation of anything with a constant is 0/0 — a naive implementation
returns 1.0 or a NaN that compares as agreement. Both sides must clear `MIN_FIELD_SPREAD`, and a
zero-variance side is refused rather than scored. On this corpus 15 of 307 fields are that flat.

## What a rhyme does NOT claim

Correlation is scale-free. A field varying by 0.11 can rhyme with one varying by 0.02 if the SHAPE
corresponds — `cseg_Temple_Spire_3 ~ cseg_lattice_window_1` rhymes at 0.963 with spreads of 0.066
and 0.013. That is the honest content of the word: the warmth is organised the same way, not that
the two are equally chromatic. Both spreads are reported on every reading so a caller who wants
amplitude agreement can add it; this module does not smuggle it in.

PURE. No database, no network, no model. Two regions and two image frames in, a relation out.
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services import chroma_organ as chroma
from backend.services import epistemics
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nestedness
from backend.services.epistemics import STATUS_KEY

ORGAN = "chromatic_relation"
ORGAN_VERSION = 1

#: The relation this module grounds, and the axis it instantiates.
RELATION_RHYMES_WITH = "rhymes_with"
AXIS_CHROMATIC_RHYME = "axis_chromatic_rhyme"

#: The null result, named so it cannot be mistaken for a refusal. Two fields that were both read
#: and do not correspond is a MEASUREMENT; two that could not be read is not.
RELATION_UNRELATED = "chromatically_unrelated"

#: The canonical grid each region's warmth is resampled onto, over its OWN bounding box.
#: 8×8 = 64 cells, which is what makes size and position drop out of the comparison.
RHYME_GRID = 8

#: How many canonical cells both regions must occupy before a correlation between them means
#: anything. CORPUS-DERIVED: below 16 the permutation null itself clears |r| > 0.7 on 1.1% of pairs,
#: and at 8–15 cells the same region turned up at both ends of the ranking — the signature of an
#: artifact. At 24 the null tail is gone (1 pair in 65,642 above 0.7, none above 0.8).
MIN_SHARED_CELLS = 24

#: Below this a field has no structure to rhyme with, only a level. THE ABSENCE-CREDIT GUARD, and
#: the reason it is a floor rather than a special case: a correlation against a near-constant is
#: dominated by whatever noise the constant has. 15 of 307 corpus fields sit below it.
MIN_FIELD_SPREAD = 0.01

#: A FREE PARAMETER, declared as one. The distribution over all cross-image pairs is smooth and
#: unimodal about zero — there is no valley, and 0.8 is not derived from one.
#:
#: What it IS placed on: the permutation null. At 24+ shared cells, r > 0.8 occurs 237 times in the
#: real data and 0 times in the null over the same 65,642 pairs. The floor sits where chance stops
#: producing the answer at all, which is the strongest thing available here and is still not a
#: derivation. 0.36% of cross-image pairs clear it.
#:
#: `measure()` reports `rhyme` on every reading, so a caller who disagrees can re-threshold without
#: re-measuring, and `scripts/chromatic_rhyme_proof.py` sweeps it rather than assuming it.
MIN_RHYME = 0.8

#: Mask → measured, box → interpretive. Taken from the nestedness organ rather than restated, so the
#: relations cannot drift apart about what a basis is worth.
BASIS_EPISTEMIC = nestedness.BASIS_EPISTEMIC
ADMISSIBLE_BASIS = nestedness.ADMISSIBLE_BASIS


class RhymeRefusal(Exception):
    """The geometry or the frames cannot support a rhyme reading at all.

    Raised, never returned as `chromatically_unrelated`. Two fields that were read and do not
    correspond is a measurement; two that could not be read is not, and collapsing them would let
    an unreadable pair count as evidence of no relation.
    """


def epistemic_for(basis: str) -> str:
    return epistemics.substrate_ceiling(basis).value


def is_admissible(measurement: Optional[Mapping[str, Any]]) -> bool:
    return nestedness.is_admissible(measurement)


# ── the field, on a canonical region-relative grid ──────────────────────────

def _warmth(px: Sequence[int]) -> float:
    """One pixel on the warm/cool axis.

    The same red-minus-blue opponent value `chroma_organ` uses. Recomputed here rather than reaching
    into the organ's private helper — and `test_chromatic_relation` pins the two against each other
    over the same region, so the copy cannot drift into a second definition of warmth without a
    test failing.
    """
    r, b = float(px[0]), float(px[2])
    total = r + b
    return 0.0 if total <= 0 else (r - b) / total


def warmth_shape(region: Mapping[str, Any], frame: Optional[Mapping[str, Any]], *,
                 grid: int = RHYME_GRID) -> Tuple[Dict[int, float], str]:
    """A region's warmth on a canonical `grid × grid` over its own bounding box.

    Returns `(cells, basis)`. The mask path uses the region's actual shape; a box-only region falls
    back to its rectangle and reports `box`, which makes the whole reading `interpretive` — a box's
    warmth is the region's averaged with whatever is behind it, which the chroma lane measured.
    """
    chroma.assert_frame_valid(frame)
    pixels, sh, sw = chroma.sample_rgb(frame["image"], chroma.SAMPLE)

    rle = region.get("mask_rle")
    if mg.rle_is_valid(rle):
        bits, mh, mw = mg.rle_decode(rle)
        basis = "mask"
    else:
        box = nestedness._box_of(region)
        if box is None:
            raise RhymeRefusal(
                f"region {region.get('id')!r} carries neither a valid mask nor a valid box")
        mh = mw = max(grid, 32)
        bits = bytearray(mh * mw)
        for y in range(int(box["y"] * mh), min(mh, int(round((box["y"] + box["h"]) * mh)))):
            for x in range(int(box["x"] * mw), min(mw, int(round((box["x"] + box["w"]) * mw)))):
                bits[y * mw + x] = 1
        basis = "box"

    xs = [x for y in range(mh) for x in range(mw) if bits[y * mw + x]]
    if not xs:
        raise RhymeRefusal(f"region {region.get('id')!r} has an empty mask — nothing to read")
    ys = [y for y in range(mh) for x in range(mw) if bits[y * mw + x]]
    x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    bw, bh = x1 - x0, y1 - y0
    if bw < grid or bh < grid:
        raise RhymeRefusal(
            f"region {region.get('id')!r} is {bw}×{bh} on its own raster, thinner than the {grid}×"
            f"{grid} rhyme grid — resampling it would invent the structure being compared")

    sums = [0.0] * (grid * grid)
    counts = [0] * (grid * grid)
    for y in range(y0, y1):
        gy = min(grid - 1, (y - y0) * grid // bh)
        sy = min(sh - 1, y * sh // mh)
        for x in range(x0, x1):
            if not bits[y * mw + x]:
                continue
            gx = min(grid - 1, (x - x0) * grid // bw)
            sx = min(sw - 1, x * sw // mw)
            sums[gy * grid + gx] += _warmth(pixels[sy * sw + sx])
            counts[gy * grid + gx] += 1

    return ({i: sums[i] / counts[i] for i in range(grid * grid) if counts[i]}, basis)


def _correlation(va: Sequence[float], vb: Sequence[float]) -> Optional[float]:
    """Pearson correlation, each side centred on its OWN mean. None when either has no variation.

    `None` rather than 0.0 or 1.0 is the absence-credit guard at its sharpest: a constant field
    correlates with nothing, and the two conventional answers are both wrong in the flattering
    direction.
    """
    ma, mb = statistics.fmean(va), statistics.fmean(vb)
    da = [v - ma for v in va]
    db = [v - mb for v in vb]
    na = math.sqrt(sum(v * v for v in da))
    nb = math.sqrt(sum(v * v for v in db))
    if na == 0.0 or nb == 0.0:
        return None
    return sum(x * y for x, y in zip(da, db)) / (na * nb)


# ── the measurement ─────────────────────────────────────────────────────────

def measure(a: Mapping[str, Any], a_frame: Optional[Mapping[str, Any]],
            b: Mapping[str, Any], b_frame: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Do these two regions' warmth fields rhyme? Reads no label and no embedding."""
    if a is None or b is None:
        raise RhymeRefusal("two regions are required")
    a_id, b_id = str(a.get("id") or ""), str(b.get("id") or "")
    if a_id and a_id == b_id and a_frame is b_frame:
        raise RhymeRefusal(f"region {a_id!r} against itself — nothing rhymes with itself")

    a_cells, a_basis = warmth_shape(a, a_frame)
    b_cells, b_basis = warmth_shape(b, b_frame)

    shared = sorted(set(a_cells) & set(b_cells))
    if len(shared) < MIN_SHARED_CELLS:
        raise RhymeRefusal(
            f"the two regions co-occupy {len(shared)} canonical cells, below {MIN_SHARED_CELLS}. "
            f"A correlation over that few is where the permutation null itself clears 0.7 — the "
            f"answer would be about the sample size, not about the pictures")

    va = [a_cells[i] for i in shared]
    vb = [b_cells[i] for i in shared]
    a_spread = statistics.pstdev(va)
    b_spread = statistics.pstdev(vb)

    if min(a_spread, b_spread) < MIN_FIELD_SPREAD:
        raise RhymeRefusal(
            f"one field varies by {min(a_spread, b_spread):.4f}, below {MIN_FIELD_SPREAD} — it has "
            f"a level and no structure. A flat field cannot rhyme; scoring it would let two "
            f"absences agree, which is the trap the `present` aggregation lesson names")

    rhyme = _correlation(va, vb)
    if rhyme is None:
        raise RhymeRefusal(
            "a field with no variation correlates with nothing. Returning 1.0 or 0.0 here would be "
            "the absence-credit trap taking whichever answer flatters the pair")

    basis = "mask" if a_basis == "mask" == b_basis else "box"
    rhymes = rhyme >= MIN_RHYME
    relation = RELATION_RHYMES_WITH if rhymes else RELATION_UNRELATED

    return {
        "relation": relation,
        "organ": ORGAN,
        "organ_version": ORGAN_VERSION,
        "a_region_id": a_id,
        "b_region_id": b_id,
        # THE STATISTIC, on every reading — a caller who disagrees with the floor re-thresholds
        # without re-measuring, the discipline `occlusion_organ` established for `dominance`.
        "rhyme": round(rhyme, 6),
        "rhymes": rhymes,
        "shared_cells": len(shared),
        "a_cells": len(a_cells),
        "b_cells": len(b_cells),
        # Reported, never folded in: correlation is scale-free, so a rhyme says the warmth is
        # ORGANISED the same way and not that the two are equally chromatic.
        "a_spread": round(a_spread, 6),
        "b_spread": round(b_spread, 6),
        "a_mean": round(statistics.fmean(va), 6),
        "b_mean": round(statistics.fmean(vb), 6),
        # The gap the statistic deliberately ignores, kept so a reader can SEE it was ignored.
        "mean_gap": round(abs(statistics.fmean(va) - statistics.fmean(vb)), 6),
        "basis": basis,
        "basis_detail": ("per-pixel over both regions' own masks" if basis == "mask" else
                         "at least one side is a BOUNDING BOX — an estimate whose warmth is the "
                         "region's averaged with whatever is behind it"),
        "thresholds": {"min_rhyme": MIN_RHYME, "min_shared_cells": MIN_SHARED_CELLS,
                       "min_field_spread": MIN_FIELD_SPREAD, "grid": RHYME_GRID},
        "source": {"a_image": (a_frame or {}).get("source"),
                   "b_image": (b_frame or {}).get("source")},
        "detail": (
            f"{basis} shape correlation {rhyme:+.3f} over {len(shared)} canonical cells "
            f"(spreads {a_spread:.3f}/{b_spread:.3f}, mean gap {abs(statistics.fmean(va) - statistics.fmean(vb)):.3f} "
            f"— removed by centring, not scored): "
            + ("the warmth is organised the same way in both" if rhymes
               else "no correspondence of structure")),
    }


def new_mark_id() -> str:
    return f"vm_rhy_{uuid4().hex[:12]}"


def grounding_mark(measurement: Mapping[str, Any], *, post_id: str = "",
                   step_id: str = "", now: str = "") -> Dict[str, Any]:
    """The reading as a proposable mark. The ONE place a status is written.

    Derived from the basis, so a box-basis rhyme cannot be committed as `measured` however high its
    correlation — the discipline `nestedness_organ.grounding_mark` established and every organ since
    has kept.

    Names the IMAGES both fields were read from, per ORGAN-PROVENANCE-001: chroma reads an external
    artifact, and a cross-image relation reads two of them.
    """
    basis = str(measurement.get("basis") or "")
    return {
        "id": new_mark_id(),
        "type": "relation_mark",
        "relation": measurement.get("relation"),
        "axis": AXIS_CHROMATIC_RHYME,
        "post_id": str(post_id),
        "region_ids": [measurement.get("a_region_id"), measurement.get("b_region_id")],
        STATUS_KEY: epistemic_for(basis),
        epistemics.SUBSTRATE_KEY: basis,
        "detail": measurement.get("detail"),
        "measurement": {k: measurement.get(k) for k in
                        ("rhyme", "rhymes", "shared_cells", "a_spread", "b_spread", "a_mean",
                         "b_mean", "mean_gap", "basis", "thresholds")},
        "provenance": {
            "producer": ORGAN,
            "producer_version": ORGAN_VERSION,
            "step_id": str(step_id),
            **{k: v for k, v in (measurement.get("source") or {}).items()},
        },
        "at": str(now),
    }


def find_rhymes(pairs: Sequence[Tuple[Mapping[str, Any], Mapping[str, Any],
                                      Mapping[str, Any], Mapping[str, Any]]], *,
                min_rhyme: float = MIN_RHYME) -> List[Dict[str, Any]]:
    """Every rhyme among `(region_a, frame_a, region_b, frame_b)` tuples, strongest first.

    A sweep, not an agent's world: no agent may call this about its own locus. Present for the same
    reason `find_nested_pairs` is — so a situated reading can be compared against the unsituated one.
    """
    out: List[Dict[str, Any]] = []
    for a, a_frame, b, b_frame in pairs or []:
        try:
            m = measure(a, a_frame, b, b_frame)
        except RhymeRefusal:
            continue
        if m["rhyme"] >= min_rhyme:
            out.append(m)
    out.sort(key=lambda m: -m["rhyme"])
    return out
