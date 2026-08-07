"""WAVE3 — the society characterization sweep: the invariants a census could quietly break.

A measurement lane's failure mode is not a crash, it is a **table that looks right**. Four things
would each produce a plausible distribution while being false, and each is pinned here:

  1. THE SWEEP MUST NOT REINTRODUCE NAME-BASED COMPARISON. The society decides comparability from
     reading arity; a census that shortcut it with `if organ == "chroma_organ"` would produce the
     same numbers today and the wrong ones the day a chromatic relation exists. §1.
  2. THE `CompatibilityLeak` GUARD MUST SURVIVE THE SWEEP. If `compare_across_senses` ever answers,
     every `incommensurable` row in the table silently becomes a comparison. §1.
  3. AN ORGAN THAT COULD NOT LOOK IS NOT AN ORGAN THAT LOOKED AND FOUND NOTHING. The sweep drops
     refusing bodies from a locus; counting them as present-and-silent would inflate `undetermined`
     with agents that were never there. §2.
  4. THE SEED SET RANKS AND DOES NOT DECIDE. It carries both organs' own numbers and mints no
     relation — there is no occlusion relation in this system and this script must not become one.
     §3.

§4 pins the two sub-kinds of `coexistent` the sweep found, because the distinction between them is
the lane's own result and a later refactor could collapse it without any test noticing.
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

from backend.services import adjacency_organ as adjacency
from backend.services import chroma_organ as chroma
from backend.services import depth_organ as depth
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services.agents import society as soc

_SPEC = importlib.util.spec_from_file_location(
    "society_characterization",
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts",
                 "society_characterization.py"))
sweep = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sweep)

RASTER = 16


# ── fixtures ────────────────────────────────────────────────────────────────

def _rle(x0, x1, y0, y1, w=RASTER, h=RASTER):
    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: The dialogue lane's 2×2, sized so the cells are genuinely separated. `DEEP` had to be moved
#: twice: at a 12-raster it sat one pixel from the container's edge and adjacency read contact
#: 0.444 through 8-connectivity, so the "deep inside" fixture was quietly at the rim. Verified
#: numerically by `test_the_fixture_geometry_is_the_two_by_two_it_claims_to_be`.
WHOLE = {"id": "r_whole", "label": "whole", "mask_rle": _rle(0, 12, 0, 16)}
#: Inside the whole AND meeting its edge — the one position that needs two organs to state.
RIM = {"id": "r_rim", "label": "part", "mask_rle": _rle(9, 12, 5, 11)}
#: Inside the whole and touching NOTHING it is inside — so with a neighbour present the two
#: relation organs relate the locus to different regions entirely, which is the `coexistent`
#: case the lane went looking for.
DEEP = {"id": "r_deep", "label": "core", "mask_rle": _rle(3, 6, 4, 12)}
NEIGH = {"id": "r_neigh", "label": "next", "mask_rle": _rle(6, 9, 4, 12)}


def _post(post_id="p1", regions=None):
    return {"_id": post_id,
            "region_annotations": [dict(r) for r in (regions or (RIM, WHOLE))]}


class FakeImage:
    """A warm-left raster, duck-typed on the three methods `chroma.sample_rgb` calls — so this file
    imports no image library, the same choice the chroma organ's own tests make."""

    def __init__(self, size=64):
        self.size = size

    def convert(self, _mode):
        return self

    def resize(self, wh):
        return FakeImage(int(wh[0]))

    def getdata(self):
        return [((220, 90, 40) if (i % self.size) < self.size // 2 else (40, 90, 220))
                for i in range(self.size * self.size)]


def _field(grid=8, *, near_left=True):
    """A synthetic whole-frame depth field, with provenance — the organ refuses one without it.

    Inverse depth, so a larger value is NEARER. The left half is near and the right half far, which
    gives `separations` a real gap to measure rather than a rounding difference.
    """
    depths = [(0.9 if (i % grid) < grid // 2 else 0.1) for i in range(grid * grid)]
    if not near_left:
        depths = [(0.1 if (i % grid) < grid // 2 else 0.9) for i in range(grid * grid)]
    return depth.depth_field(
        {"grid": grid, "depth": depths}, adapter="depth_anything_v2_small",
        model="depth_anything_v2_small", revision="test", preprocessing_version="v1",
        whole_frame=True)


# ── 1. the sweep must not decide comparability for itself ──────────────────

_SCRIPT = Path(sweep.__file__)


def test_the_sweep_never_compares_by_organ_name():
    """The society reads comparability off arity. A census that shortcut that would produce the
    same table today and the wrong one the day a chromatic relation exists — and nothing in the
    numbers would show it."""
    body = re.sub(r'""".*?"""', "", _SCRIPT.read_text(), flags=re.S)
    for shortcut in ('== "chroma_organ"', "== 'chroma_organ'",
                     '== "depth_organ"', "== 'depth_organ'"):
        assert shortcut not in body, f"{shortcut} — comparability decided by name, not by arity"
    assert "soc.relate" in body, "the sweep must ask the society, not re-derive its verdicts"


def test_the_sweep_mints_no_relation_and_writes_no_status():
    """A measurement lane that grounded something would become the thing it was measuring."""
    source = _SCRIPT.read_text()
    assert "grounding_mark" not in source and "EpistemicStatus" not in source
    assert not re.search(r"STATUS_KEY\s*[:=]", source)
    for writer in ("write_hypothesis", "write_observation", "write_edge"):
        assert writer not in source
    # `insert_one` DOES appear — inside `freeze`, which replaces it with a raiser. That is the
    # opposite of a write, and a scan that could not tell the two apart would have to be either
    # wrong here or blind somewhere else.
    assert re.findall(r"insert_one", source) == ["insert_one"]

    class Collection:
        def insert_one(self, *_a, **_k):
            raise AssertionError("the real method was called")

    frozen = Collection()
    sweep.freeze(frozen)
    with pytest.raises(sweep.WriteAttempted, match="writes nothing"):
        frozen.insert_one({})


def test_the_compatibility_leak_guard_still_fires_under_the_sweeps_own_agents(monkeypatch):
    """If `compare_across_senses` ever answers, every `incommensurable` row in the table is
    silently a comparison. Checked with the agents the sweep itself builds."""
    post = _post()
    geo = sweep.stand(post, "r_rim", (nest.ORGAN,), agent_id="alpha")
    chr_ = sweep.stand(post, "r_rim", (chroma.ORGAN,), agent_id="gamma", image=FakeImage())
    assert geo is not None and chr_ is not None
    assert soc.relate(geo, chr_).outcome == soc.INCOMMENSURABLE

    monkeypatch.setattr(chroma, "compare_across_senses", lambda *a, **k: 0.5)
    with pytest.raises(soc.CompatibilityLeak):
        soc.relate(geo, chr_)


# ── 2. could-not-look is not looked-and-found-nothing ──────────────────────

def test_an_organ_that_refuses_is_absent_from_the_locus_not_silent_at_it():
    """`undetermined` means an agent looked and measured nothing. A body that could not look at
    all — no pixels, no depth field — must not be counted as one, or the commonest outcome in the
    table becomes an artefact of what the sweep failed to hand its agents."""
    post = _post()
    assert sweep.stand(post, "r_rim", (chroma.ORGAN,), agent_id="gamma", image=None) is None
    assert sweep.stand(post, "r_rim", (depth.ORGAN,), agent_id="delta", depth_field=None) is None

    census = sweep.census_at(post, "r_rim")
    assert sorted(census["bodies"]) == ["alpha", "beta"]
    assert census["absent"] == ["delta", "gamma"]
    assert all(row["outcome"] != soc.UNDETERMINED for row in census["pairs"])


def test_a_body_that_looked_and_found_nothing_stays_in_the_table_as_undetermined():
    """The other half: an agent that DID look and measured nothing is present, and its pairs read
    `undetermined` rather than being dropped. Silence is a fact about the locus.

    `r_deep` with no neighbour: nestedness relates it to the container, adjacency touches nothing.
    """
    lone = _post("p2", regions=(DEEP, WHOLE))
    census = sweep.census_at(lone, "r_deep")
    assert "beta" in census["bodies"]
    assert census["measured"]["alpha"] == 1 and census["measured"]["beta"] == 0
    assert {row["outcome"] for row in census["pairs"]} == {soc.UNDETERMINED}
    assert census["silent"] == ["beta"]


def test_the_census_counts_only_masked_loci():
    """A society over two box-basis estimates would characterise the WAVE2.5 fallback rather than
    the sense. The census excludes them by construction."""
    mixed = {"_id": "p3", "region_annotations": [
        dict(RIM), dict(WHOLE), {"id": "b_est", "box": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3}}]}
    assert [str(r["id"]) for r in sweep.masked_regions(mixed)] == ["r_rim", "r_whole"]


# ── 3. the seed set ranks, and does not decide ─────────────────────────────

def test_the_seed_set_carries_both_organs_numbers_and_ranks_by_a_stated_rule():
    post = _post()
    rows = sweep.separations(post, _field(), limit=10)
    assert rows, "the fixture must produce a mask-basis nested pair to rank"
    row = rows[0]
    assert row["nesting_basis"] == nest.ADMISSIBLE_BASIS
    for key in ("nesting_index", "containment", "inner_depth", "outer_depth",
                "inner_frame_rank", "outer_frame_rank", "separation", "frame_spread"):
        assert key in row, key
    assert row["separation"] == pytest.approx(
        (row["inner_depth"] - row["outer_depth"]) / row["frame_spread"], abs=1e-3)


def test_the_ranking_flips_sign_when_the_depth_field_does():
    """It measures the field, not the geometry. Same regions, same nesting, mirrored depth — and a
    part reported as nearer than its container becomes one reported as further."""
    post = _post()
    near = sweep.separations(post, _field(near_left=True), limit=10)[0]
    far = sweep.separations(post, _field(near_left=False), limit=10)[0]
    assert near["inner_region_id"] == far["inner_region_id"]
    assert near["nesting_index"] == far["nesting_index"]
    assert near["separation"] == pytest.approx(-far["separation"], abs=1e-3)


def test_the_seed_set_is_ordered_most_suspicious_first():
    post = _post("p4", regions=(RIM, DEEP, NEIGH, WHOLE))
    rows = sweep.separations(post, _field(), limit=20)
    assert rows == sorted(rows, key=lambda r: -r["separation"])


def test_a_pair_the_depth_organ_cannot_read_is_dropped_rather_than_guessed():
    """`DepthRefusal` on either end means no comparable number exists for that pair. Falling back
    to a box-basis reading would put the WAVE2.5 estimate into the one table meant to expose it."""
    tiny = {"id": "r_tiny", "label": "speck", "mask_rle": _rle(5, 6, 5, 6)}
    post = _post("p5", regions=(tiny, WHOLE))
    with pytest.raises(depth.DepthRefusal):
        depth.measure(tiny, _field())
    assert sweep.separations(post, _field(), limit=10) == []


# ── 4. the two sub-kinds of coexistent ─────────────────────────────────────

def test_two_relation_organs_that_share_no_subject_are_coexistent_disjoint():
    """The case the card asked for: `r_deep` is inside `r_whole` and touches `r_neigh`, so the two
    geometry organs relate the locus to different regions entirely."""
    post = _post("p6", regions=(DEEP, WHOLE, NEIGH))
    census = sweep.census_at(post, "r_deep")
    row = next(r for r in census["pairs"] if {r["left"], r["right"]} == {"alpha", "beta"})
    assert row["outcome"] == soc.COEXISTENT and row["shared_subjects"] == []

    cases = sweep.coexistent_cases([census])
    assert cases["relational_total"] == 1 and cases["relational_why"] == {"disjoint": 1}


def test_two_relation_organs_can_share_every_subject_and_still_compose_nothing():
    """THE SUB-KIND THE SWEEP FOUND rather than expected, and the reason a shared-subject count
    alone is misleading: standing on the CONTAINER, nestedness faces `contains` where adjacency
    faces `meets`, and `contains + meets` is not being at that region's rim — it is being the thing
    that region is at the rim of. `dialogue.compose` pairs `within` with `meets`, and this is what
    that decision looks like from the outside."""
    post = _post("p7", regions=(RIM, WHOLE))
    census = sweep.census_at(post, "r_whole")
    row = next(r for r in census["pairs"] if {r["left"], r["right"]} == {"alpha", "beta"})
    assert row["outcome"] == soc.COEXISTENT
    assert row["shared_subjects"] == ["r_rim"]
    assert row["shared_directions"] == ["contains+meets"]

    cases = sweep.coexistent_cases([census])
    assert cases["relational_why"] == {"direction": 1}


def test_a_field_pair_is_coexistent_too_and_is_counted_separately():
    """Chroma and depth share an arity, so the society calls them comparable and they come out
    `coexistent` — but they have no composition rule at all, which is a different animal from two
    relation organs that could have composed and did not. Counted apart so the table cannot imply
    otherwise."""
    post = _post()
    census = sweep.census_at(post, "r_rim", image=FakeImage(), depth_field=_field())
    row = next(r for r in census["pairs"] if {r["left"], r["right"]} == {"gamma", "delta"})
    assert row["outcome"] == soc.COEXISTENT
    assert row["left_arity"] == [1] and row["right_arity"] == [1]

    cases = sweep.coexistent_cases([census])
    assert cases["fieldwise_total"] == 1 and cases["relational_total"] == 0


def test_the_distribution_is_reported_by_body_pair_and_not_only_overall():
    """A single column would hide that one outcome belongs almost entirely to one kind of pairing —
    which is the sweep's main result."""
    post = _post()
    tally = sweep.tally([sweep.census_at(post, "r_rim", image=FakeImage(), depth_field=_field())])
    assert tally["pair_verdicts"] == 6 and tally["loci"] == 1
    assert set(tally["by_body_pair"]) == {
        "adjacency_organ × chroma_organ", "adjacency_organ × depth_organ",
        "adjacency_organ × nestedness_organ", "chroma_organ × depth_organ",
        "chroma_organ × nestedness_organ", "depth_organ × nestedness_organ"}
    assert sum(sum(v.values()) for v in tally["by_body_pair"].values()) == tally["pair_verdicts"]


def test_the_fixture_geometry_is_the_two_by_two_it_claims_to_be():
    """THE PREMISE, checked numerically rather than eyeballed off the coordinates — because it was
    wrong the first time. At a 12-raster `r_deep` sat one pixel inside the container's edge and
    adjacency read contact 0.444 through 8-connectivity, so the "deep inside, touching nothing"
    fixture was silently at the rim and the `disjoint` case it was built for could not occur."""
    assert nest.measure(RIM, WHOLE)["nested"] and adjacency.measure(RIM, WHOLE)["adjacent"]
    assert nest.measure(DEEP, WHOLE)["nested"]
    assert not adjacency.measure(DEEP, WHOLE)["adjacent"], "deep must not touch its container"
    assert adjacency.measure(DEEP, NEIGH)["adjacent"]
    assert not nest.measure(DEEP, NEIGH)["nested"]
