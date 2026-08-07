"""WAVE3 — the occlusion sweep: the four ways a corpus-scale partition would quietly lie.

This lane's whole content is a comparison between two instruments, and a comparison is the easiest
thing in the world to rig. Each of these guards a claim that would still produce a publishable
table if it failed:

  1. IT USES THE ORDERING STATISTIC, NOT THE MEAN. #164 measured that the mean's sign carries no
     information; a sweep that quietly ranked on the mean again would reproduce #164's result and
     present it as an improvement on itself. §1.
  2. IT APPLIES THE RELATION AND DOES NOT RE-GROUND ONE. The verdicts must come from
     `occlusion_organ`, not from a threshold this script keeps privately. §1.
  3. A REFUSAL IS NOT A CONTAINMENT THAT STOOD. `stands`, `superseded` and `refused` are three
     different facts, and folding the third into the first would turn every geometry the grid is
     too coarse for into evidence that nestings are genuine. §2.
  4. THE PARTITION REPORTS BOTH STATISTICS FROM THE SAME PAIRS. A comparison quoted rather than
     computed is one the reader has to take on trust. §3.

§4 pins both verdict branches and the arithmetic ceiling that governs which one a pair can reach.
#165 predicted this corpus would yield NO superseded containments, on the grounds that segmentation
masks are exclusive; the sweep found 13, and that premise is false — a mask-basis containment
REQUIRES the container's mask to cover the part. What actually limits the ordering is 1 - k/(2n).
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

from backend.services import depth_organ
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services import occlusion_organ as occlusion

_SPEC = importlib.util.spec_from_file_location(
    "occlusion_sweep",
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "occlusion_sweep.py"))
sweep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sweep)

RASTER = 32
GRID = 16


# ── fixtures: two nestings, one genuine and one an occlusion ────────────────

def _rle(x0, x1, y0, y1, w=RASTER, h=RASTER):
    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: A container filling the left half, and a part genuinely inside it.
#:
#: THE PART HAD TO BE MADE SMALL, and the reason is this lane's sharpest finding. A mask-basis
#: containment means the container's mask covers the part (nestedness needs containment ≥ 0.95), so
#: the container's CELLS include the part's — and every part-cell compared against itself inside the
#: container's distribution is a tie, worth half. That puts an arithmetic ceiling on the ordering:
#:
#:     dominance ≤ 1 − k / (2n)      k = the part's cells, n = the container's
#:
#: At k=32 of n=160 the ceiling is 0.9000 and the 0.95 floor is unreachable no matter how much
#: nearer the part is. `test_the_ordering_statistic_has_an_arithmetic_ceiling` pins the formula; the
#: fixture uses k=6 (ceiling 0.9812) so the superseded branch is reachable at all.
OUTER = {"id": "r_outer", "label": "wall", "mask_rle": _rle(0, 20, 0, 32)}
INNER = {"id": "r_inner", "label": "panel", "mask_rle": _rle(4, 8, 8, 14)}


def _post(post_id="p1", regions=None):
    return {"_id": post_id, "region_annotations": [dict(r) for r in (regions or (INNER, OUTER))]}


def _depth(values):
    return depth_organ.depth_field(
        {"grid": GRID, "depth": values}, adapter="depth_anything_v2_small",
        model="depth_anything_v2_small", revision="test", preprocessing_version="v1",
        whole_frame=True)


def _field(*, inner_near: bool, part=None):
    """A depth field over the fixture. `inner_near` decides whether the part's cells read nearer
    than its container's — the whole question, and the only thing that differs between branches.

    Inverse depth: larger is nearer. `inner_near=False` puts the part at THE SAME depth as its
    container rather than merely closer to it: a part that is slightly nearer is still ordered, and
    a fixture that used "slightly" for "coplanar" would be testing the floor rather than the
    relation.
    """
    part = part or INNER
    inner_cells, _ = depth_organ.region_cells(part, GRID)
    outer_cells, _ = depth_organ.region_cells(OUTER, GRID)
    inner_only, outer_all = set(inner_cells), set(outer_cells)
    values = []
    for i in range(GRID * GRID):
        if i in inner_only:
            values.append(0.90 if inner_near else 0.10)
        elif i in outer_all:
            values.append(0.10)
        else:
            values.append(0.05)
    return _depth(values)


def test_the_fixture_is_a_containment_that_depth_can_judge_either_way():
    """The premise. If `r_inner` stopped being mask-nested in `r_outer`, or the two fields stopped
    ordering differently, every partition assertion below would pass over an empty list."""
    m = nest.measure(INNER, OUTER)
    assert m["nested"] and m["basis"] == nest.ADMISSIBLE_BASIS

    near = occlusion.measure(INNER, OUTER, _field(inner_near=True))
    same = occlusion.measure(INNER, OUTER, _field(inner_near=False))
    assert near["separated"] and near["front_region_id"] == "r_inner"
    assert not same["separated"]


# ── 1. the statistic, and whose judgement it is ────────────────────────────

_SCRIPT = Path(sweep.__file__)


def test_the_verdicts_come_from_the_organ_and_not_from_a_private_threshold():
    """A sweep that kept its own floor would be re-grounding the relation under a measurement
    lane's name, and its partition would move whenever it felt like it."""
    body = re.sub(r'"""[\s\S]*?"""', "", _SCRIPT.read_text())
    assert "reconcile_containment" in body, "the organ must be the thing that judges"
    assert "occlusion.measure" in body
    # no threshold of its own: MIN_SEPARATION is read from the organ, never restated
    assert re.search(r"MIN_SEPARATION\s*=", body) is None
    assert "occlusion.MIN_SEPARATION" in body


def test_the_sweep_mints_no_relation_and_touches_no_gate_or_agent():
    """Scanned over the BODY, not the prose — the docstring names what the lane does not touch, and
    a scan that could not tell a mention from a call would force the module to stop explaining
    itself."""
    source = _SCRIPT.read_text()
    body = re.sub(r'"""[\s\S]*?"""', "", source)
    assert "grounding_mark" not in body and "EpistemicStatus" not in body
    for forbidden in ("structure_map", "agents.", "run_kernel",
                      "write_hypothesis", "write_observation"):
        assert forbidden not in body, forbidden
    # `movement_kernel` IS imported, for its two post-hashing helpers — which is how this lane
    # proves it wrote nothing. Nothing else from it is reachable.
    assert set(re.findall(r"mk\.\w+", body)) == {"mk.posts_fingerprint",
                                                  "mk.assert_posts_unchanged"}


def test_both_statistics_are_computed_from_the_same_pairs():
    """The comparison is the lane. Quoting #164's number instead of recomputing it would leave the
    reader to trust that the two sweeps saw the same corpus."""
    rows = sweep.judge_post(_post(), _field(inner_near=False))
    assert rows and all("separation" in r and "mean_separation" in r for r in rows)

    part = sweep.partition(rows)
    assert part["ordering"]["n"] == part["mean_separation"]["n"] == len(rows)
    assert "positive_share" in part["mean_separation"]


# ── 2. a refusal is not a containment that stood ───────────────────────────

def test_a_pair_the_grid_is_too_coarse_for_is_refused_and_not_counted_as_standing():
    """The failure that would inflate the null: a geometry finer than the grid returns a refusal,
    and counting it as `stands` would turn "we could not look" into "we looked and it was fine"."""
    speck = {"id": "r_speck", "label": "speck", "mask_rle": _rle(6, 8, 10, 12)}
    post = _post("p2", regions=(speck, OUTER))
    field = _field(inner_near=True)

    with pytest.raises(occlusion.OcclusionRefusal):
        occlusion.measure(speck, OUTER, field)

    rows = sweep.judge_post(post, field)
    assert rows and all(r["verdict"] == "refused" for r in rows)
    assert {r["reason"] for r in rows} == {"too_few_cells"}

    part = sweep.partition(rows)
    assert part["judged"] == 0 and part["pairs_seen"] == len(rows)
    assert part["verdicts"] == {} and part["refusals"] == {"too_few_cells": len(rows)}


def test_refusals_are_counted_by_reason_and_not_summed():
    """`too_few_cells` says the geometry is finer than the grid; `unreadable` says the region
    carries nothing to read. One is about resolution, the other about data."""
    assert sweep._refusal_reason("one side covers 2 depth cells, below 4") == "too_few_cells"
    assert sweep._refusal_reason(
        "region 'x' carries neither a valid mask nor a valid box") == "unreadable"
    assert sweep._refusal_reason("something else entirely") == "other"


def test_only_mask_basis_nestings_enter_the_sweep():
    """A box-basis containment is the pathology being offered as evidence about itself, and
    `reconcile_containment` refuses to supersede on one. Excluded at the door, so it cannot land in
    the denominator as a containment that stood."""
    boxed = {"id": "b_inner", "box": {"x": 0.2, "y": 0.3, "w": 0.2, "h": 0.3}}
    post = _post("p3", regions=(INNER, OUTER, boxed))
    ids = {r["inner_region_id"] for r in sweep.judge_post(post, _field(inner_near=False))}
    assert "b_inner" not in ids
    assert [str(r["id"]) for r in sweep.masked_regions(post)] == ["r_inner", "r_outer"]


# ── 3. the partition ───────────────────────────────────────────────────────

def test_a_containment_depth_does_not_order_stands():
    rows = sweep.judge_post(_post(), _field(inner_near=False))
    assert [r["verdict"] for r in rows] == [occlusion.CONTAINMENT_STANDS]
    assert rows[0]["separated"] is False

    part = sweep.partition(rows)
    assert part["verdicts"] == {occlusion.CONTAINMENT_STANDS: 1}
    assert part["occlusions"] == []
    assert part["ordering"]["superseded_max"] is None
    assert part["ordering"]["stands_max"] == rows[0]["separation"]


def test_a_containment_whose_inner_region_is_in_front_is_superseded():
    """The finial case, as geometry — and #165 reported this branch as never having fired. At
    corpus scale it fires 13 times, so what this pins is not a hypothetical: it is the verdict the
    sweep's headline rests on."""
    rows = sweep.judge_post(_post(), _field(inner_near=True))
    assert [r["verdict"] for r in rows] == [occlusion.CONTAINMENT_SUPERSEDED]
    assert rows[0]["front_region_id"] == "r_inner"
    assert rows[0]["relation"] == occlusion.RELATION_IN_FRONT_OF

    part = sweep.partition(rows)
    assert len(part["occlusions"]) == 1
    assert part["ordering"]["at_or_above_floor"] == 1
    assert part["ordering"]["superseded_max"] >= occlusion.MIN_SEPARATION


def test_the_two_statistics_can_disagree_and_the_ordering_one_is_the_verdict():
    """THE LANE, in one assertion. A part strictly nearer than every other cell of its container
    reads strongly positive on #164's mean statistic — it IS nearer than the container's mean — and
    the ordering statistic still refuses it, because the container's cells include the part's and
    the ties cap the ordering at 1 − k/(2n) = 0.90. That gap is why the seed set needed re-running.
    """
    big = {"id": "r_inner", "label": "panel", "mask_rle": _rle(4, 12, 8, 24)}
    rows = sweep.judge_post(_post("p8", regions=(big, OUTER)),
                            _field(inner_near=True, part=big))
    row = rows[0]
    assert row["mean_separation"] > 0.2, "the mean statistic calls this a strong candidate"
    assert row["separation"] < occlusion.MIN_SEPARATION, "the ordering statistic does not"
    assert row["verdict"] == occlusion.CONTAINMENT_STANDS


def test_the_ordering_statistic_has_an_arithmetic_ceiling_on_a_containment():
    """THE LANE'S SHARPEST FINDING, pinned as arithmetic rather than observed as a pattern.

    A mask-basis containment means the container's mask covers the part, so the container's cells
    include the part's. Every part-cell then meets itself inside the container's distribution as a
    TIE, worth half — and the ordering is capped:

        dominance = [k(n−k) + k²/2] / (kn) = 1 − k/(2n)

    So a part covering more than 10% of its container's cells CANNOT reach the 0.95 floor however
    much nearer it is. The finial reached 0.9987 because its mask and the sky's do not overlap at
    all — mask-basis containment 0.000 — which is a different geometry entirely.
    """
    big = {"id": "r_big", "label": "panel", "mask_rle": _rle(4, 12, 8, 24)}
    post = _post("p4", regions=(big, OUTER))
    part_cells, _ = depth_organ.region_cells(big, GRID)
    outer_cells, _ = depth_organ.region_cells(OUTER, GRID)
    k, n = len(part_cells), len(outer_cells)
    assert set(part_cells) <= set(outer_cells), "a containment's cells are inside its container's"
    ceiling = 1.0 - k / (2.0 * n)
    assert ceiling < occlusion.MIN_SEPARATION, "the fixture must be over the 10% line"

    # every part-cell strictly nearer than every non-part cell of the container: the BEST case
    inner_only = set(part_cells)
    field = _depth([(0.90 if i in inner_only else 0.10) for i in range(GRID * GRID)])

    reading = occlusion.measure(big, OUTER, field)
    assert reading["dominance"] == pytest.approx(ceiling, abs=1e-6)
    assert reading["separated"] is False, "unreachable floor, not a coplanar measurement"
    assert sweep.judge_post(post, field)[0]["verdict"] == occlusion.CONTAINMENT_STANDS


# ── 4. the shape of the null ───────────────────────────────────────────────

def test_an_empty_partition_is_reported_as_a_bounded_claim_and_not_as_an_absence():
    """The corpus turned out to hold 13 occlusions, so this is not the branch the lane reports —
    but it is the branch a smaller bound or a coarser grid reaches, and a sweep that printed
    nothing would be indistinguishable from one that found nothing."""
    body = _SCRIPT.read_text()
    assert "NONE, within the bound above" in body
    assert "1 - k/(2n)" in body, "the null must carry the reason a pair may be unable to qualify"
    part = sweep.partition(sweep.judge_post(_post(), _field(inner_near=False)))
    assert part["occlusions"] == [] and part["judged"] == 1
    assert part["verdicts"] == {occlusion.CONTAINMENT_STANDS: 1}


def test_the_bound_is_carried_on_the_record():
    """Every claim in the report is bounded by these, so they travel with it rather than living in
    the invocation somebody has since forgotten."""
    part = sweep.partition(sweep.judge_post(_post(), _field(inner_near=True)))
    assert set(part) >= {"pairs_seen", "judged", "verdicts", "refusals",
                         "ordering", "mean_separation", "occlusions"}
    body = _SCRIPT.read_text()
    for carried in ('"grid"', '"min_separation"', '"min_cells_per_side"', '"posts_scanned"'):
        assert carried in body, carried
