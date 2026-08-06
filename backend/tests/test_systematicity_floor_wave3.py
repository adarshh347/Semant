"""
WAVE3 — the systematicity floor, audited: what the number is made of and what it does not cover.

The corpus numbers live in `scripts/systematicity_floor_audit.py` and cannot live here — they need
Mongo and 129,564 scored pairs. What belongs in the suite is everything the audit CONCLUDED, in a
form that breaks if someone quietly undoes it:

  1. **the floor is derived, not typed.** `MIN_SYSTEMATICITY` is `ONE_COMPONENT_SHARE + eps`, so
     the number and its reason cannot drift apart the way they did between WAVE2 and WAVE3. Its
     one defensible job — standing above the exact-1/3 atom — is asserted directly.
  2. **the decomposition is honest.** `live`, `earned` and `absence_share` describe the same three
     components the score is built from, and a shared absence is reported as one rather than
     silently banked.
  3. **the default did not move.** An audit that reshaped what grounds while claiming to
     characterise a threshold would be the taste-fitting the lane forbade. `shape` stays the
     default; `present` is runnable and off.
  4. **the floor is nesting's.** `relational_structure` is nesting-shaped, and a test shows what
     it does to a symmetric relation rather than leaving that to a docstring.

The one claim NOT tested here is the interesting one — that the floor separates by +20.3 points
against the held-out criterion. That is a fact about this corpus, not about this code, and pinning
a corpus statistic in a unit test would make the suite fail when the corpus grows, which is the
wrong thing to be told.
"""
import inspect
import re

import pytest

from backend.services import structure_map as sm


def skeleton(region_id="r", *, depth=1, siblings=0, descendants=0, parent="p"):
    """A relational skeleton, built directly. `relational_structure` derives these from an organ's
    measurements; the gate only ever reads the counts, so the counts are what these tests vary."""
    return {"region_id": region_id, "relation": sm.RELATION_NESTED_WITHIN, "parent_id": parent,
            "depth": depth, "sibling_count": siblings, "descendant_count": descendants,
            "has_relation": bool(parent), "sibling_ids": [], "descendant_ids": [],
            "region_count": 8}


# ── 1. the floor is derived, and its one job is provable ─────────────────────────────────────

def test_the_floor_is_derived_from_one_components_worth_of_agreement():
    """Not a typed-in 0.34. The number now follows from the reason, so editing one without the
    other is impossible rather than merely discouraged."""
    assert sm.ONE_COMPONENT_SHARE == pytest.approx(1 / 3)
    assert sm.MIN_SYSTEMATICITY == pytest.approx(
        round(sm.ONE_COMPONENT_SHARE + sm.SYSTEMATICITY_EPSILON, 5))


def test_the_floor_still_sits_where_it_did():
    """The audit characterised the floor; it did not move it. If this changes, something reshaped
    what grounds — which is a different lane with a different burden of proof."""
    assert sm.MIN_SYSTEMATICITY == 0.34


def test_the_floor_excludes_exactly_one_components_worth_and_nothing_more():
    """THE FLOOR'S ONE DEFENSIBLE JOB. A pair agreeing perfectly on one component and not at all
    on the other two scores exactly 1/3 — 2,178 real pairs sit on that value — and is refused.
    A hair more than one component's worth passes. Everything between is a free parameter."""
    one_only = sm.systematicity(skeleton(depth=2, siblings=3, descendants=4),
                                skeleton(depth=2, siblings=0, descendants=0))
    # depth agrees 1.0; siblings 3-vs-0 and descendants 4-vs-0 both align to 0.
    assert one_only["shape_score"] == pytest.approx(1 / 3, abs=1e-6)
    assert one_only["shape_score"] < sm.MIN_SYSTEMATICITY

    a_hair_more = sm.systematicity(skeleton(depth=2, siblings=3, descendants=4),
                                   skeleton(depth=2, siblings=1, descendants=0))
    assert a_hair_more["shape_score"] > sm.MIN_SYSTEMATICITY


def test_the_floor_is_not_a_bare_literal_any_more():
    """The audit found NO valley near the floor — a smooth unimodal continuum — so the magnitude
    beyond 1/3 is arbitrary. The lane's deliverable was to stop that being a silent setting, and
    the structural form of "not silent" is that the free part has its own name: you cannot edit
    the threshold without editing something called `EPSILON`.

    Asserted against the source rather than the value, because `MIN_SYSTEMATICITY == 0.34` would
    still pass if someone typed the literal back in.
    """
    assert 0 < sm.SYSTEMATICITY_EPSILON < 0.05
    source = inspect.getsource(sm)
    assert re.search(r"^MIN_SYSTEMATICITY\s*=\s*[0-9.]+\s*$", source, re.M) is None
    assert re.search(r"^MIN_SYSTEMATICITY\s*=.*ONE_COMPONENT_SHARE", source, re.M) is not None


# ── 2. the decomposition is honest about shared absence ──────────────────────────────────────

def test_a_component_neither_side_has_is_reported_as_absence_not_banked_as_agreement():
    """`_alignment` scores 0-vs-0 as 1.0, and the audit measured what that costs: pairs with no
    siblings and no descendants on either side average 0.842, the highest bucket in the corpus,
    while the score FALLS as real structure rises. The credit is still paid — changing that is not
    this lane's to do — but it can no longer be paid invisibly."""
    verdict = sm.systematicity(skeleton(depth=2, siblings=0, descendants=0),
                               skeleton(depth=2, siblings=0, descendants=0))
    assert verdict["shape_score"] == 1.0
    assert verdict["absence_share"] == pytest.approx(2 / 3)
    assert verdict["live"] == ["depth"]
    assert verdict["earned"] == ["depth"]


def test_a_component_only_one_side_has_is_live_and_earns_nothing():
    """Present-but-mismatched is disagreement; absent-on-both is no evidence. Collapsing the two
    is exactly what makes structural poverty outscore structure."""
    verdict = sm.systematicity(skeleton(depth=1, siblings=4, descendants=0),
                               skeleton(depth=1, siblings=0, descendants=0))
    assert "siblings" in verdict["live"]
    assert "siblings" not in verdict["earned"]
    assert verdict["components"]["siblings"] == 0.0
    assert verdict["absence_share"] == pytest.approx(1 / 3)   # descendants only


def test_absence_share_accounts_for_the_gap_between_the_two_aggregations():
    """The two numbers are two readings of one pair and must stay reconcilable — otherwise a
    reader cannot check the claim that abstention removes the absence credit."""
    verdict = sm.systematicity(skeleton(depth=2, siblings=0, descendants=0),
                               skeleton(depth=4, siblings=0, descendants=0))
    live = verdict["components"]["depth"]
    assert verdict["present_score"] == pytest.approx(live)
    assert verdict["shape_score"] == pytest.approx((live + 1.0 + 1.0) / 3)
    assert verdict["absence_share"] == pytest.approx(2 / 3)


def test_the_insystematic_refusal_says_what_it_is_made_of():
    """A bare '0.31 < 0.34' cannot tell a reader whether the relation is thin or the floor is
    arbitrary. The refusal now names what agreed and how much came from shared absence."""
    verdict = sm.structure_map(skeleton("a", depth=1, siblings=8, descendants=0, parent="pa"),
                               skeleton("b", depth=4, siblings=0, descendants=3, parent="pb"))
    assert verdict["status"] == "refused" and verdict["reason"] == "insystematic"
    assert "shared absence" in verdict["detail"]
    assert verdict["systematicity"]["live"] and "earned" in verdict["systematicity"]


def test_every_verdict_carries_both_readings_even_when_it_maps():
    mapped = sm.structure_map(skeleton("a", depth=2, siblings=2, descendants=1, parent="pa"),
                              skeleton("b", depth=2, siblings=2, descendants=1, parent="pb"))
    assert sm.mapped(mapped)
    for key in ("shape_score", "present_score", "live", "earned", "absence_share"):
        assert key in mapped["systematicity"]


# ── 3. the default did not move ──────────────────────────────────────────────────────────────

def test_shape_is_the_default_aggregation():
    """THE CLAIM THAT KEEPS THIS AN AUDIT. `present` measures better on both criteria the audit
    used, and adopting it here would have been a silent reshaping of what grounds under cover of
    characterising a threshold. It is runnable and off, the way #150 kept identity ranking."""
    assert sm.systematicity(skeleton(), skeleton())["aggregation"] == sm.AGGREGATION_SHAPE
    assert sm.AGGREGATIONS == (sm.AGGREGATION_SHAPE, sm.AGGREGATION_PRESENT)


def test_the_alternative_aggregation_is_runnable():
    """A better rule that cannot be run is a claim, not a finding."""
    source = skeleton(depth=2, siblings=0, descendants=0)
    target = skeleton(depth=4, siblings=0, descendants=0)
    shape = sm.structure_map(source, target)
    present = sm.structure_map(source, target, aggregation=sm.AGGREGATION_PRESENT)
    assert shape["systematicity"]["score"] > present["systematicity"]["score"]
    assert present["systematicity"]["aggregation"] == sm.AGGREGATION_PRESENT


def test_an_unknown_aggregation_raises_rather_than_falling_back():
    """Silently defaulting would let a typo produce a number that looks like the other rule's."""
    with pytest.raises(ValueError):
        sm.systematicity(skeleton(), skeleton(), aggregation="whatever")


def test_the_score_key_still_means_what_the_gate_reads():
    """`score` is what `structure_map` compares to the floor. It must follow the aggregation, or
    the two readings would be reported honestly and the gate would still read the old one."""
    source = skeleton(depth=2, siblings=0, descendants=0)
    target = skeleton(depth=4, siblings=0, descendants=0)
    assert sm.systematicity(source, target)["score"] == \
        sm.systematicity(source, target)["shape_score"]
    alt = sm.systematicity(source, target, aggregation=sm.AGGREGATION_PRESENT)
    assert alt["score"] == alt["present_score"]


def test_systematicity_still_cannot_see_a_similarity_score():
    """The WAVE2 guarantee, re-checked from this lane: the audit added a keyword-only knob and
    nothing that carries appearance."""
    sig = inspect.signature(sm.systematicity)
    positional = [n for n, p in sig.parameters.items()
                  if p.kind is not inspect.Parameter.KEYWORD_ONLY]
    assert positional == ["source", "target"]
    assert not any(word in name.lower() for name in sig.parameters
                   for word in ("score", "similarity", "embedding", "distance"))


# ── 4. the floor is nesting's, and the skeleton is nesting-shaped ────────────────────────────

def test_the_skeleton_reads_inner_and_outer_as_a_hierarchy():
    """`relational_structure` hard-codes the nesting relation and picks the immediate parent by
    `scale_ratio` — the tightest container. Both are nesting facts."""
    regions = [{"id": r} for r in ("part", "small", "big")]
    pairs = [{"inner_region_id": "part", "outer_region_id": "big", "scale_ratio": 0.1},
             {"inner_region_id": "part", "outer_region_id": "small", "scale_ratio": 0.6}]
    skel = sm.relational_structure(regions, "part", measurements=pairs)
    assert skel["relation"] == sm.RELATION_NESTED_WITHIN
    assert skel["parent_id"] == "small"          # tightest, not first and not largest
    assert skel["depth"] == 2


def test_a_symmetric_relation_gets_a_parent_by_accident_not_by_design():
    """THE VERDICT ON ONE FLOOR FOR TWO ORGANS, as a test rather than a docstring.

    `adjacency_organ` reuses the `inner_region_id`/`outer_region_id` keys and sets no
    `scale_ratio`. Fed to this skeleton the sort key is 0.0 for every candidate parent, so the
    'immediate container' of a region that merely MEETS three others is whichever row the organ
    happened to emit first. The number the floor is compared against is calibrated on nesting and
    means something else here.
    """
    regions = [{"id": r} for r in ("a", "b", "c")]
    meets = [{"inner_region_id": "a", "outer_region_id": "b"},      # no scale_ratio anywhere
             {"inner_region_id": "a", "outer_region_id": "c"}]
    skel = sm.relational_structure(regions, "a", measurements=meets)
    assert skel["parent_id"] == "b"                       # first emitted, not tightest
    assert skel["parent_measurement"].get("scale_ratio") is None
    assert skel["relation"] == sm.RELATION_NESTED_WITHIN   # says 'nested' about a meeting


def test_a_symmetric_sweep_makes_depth_and_descendants_measure_the_same_thing():
    """When both orderings of a pair are emitted — which a symmetric relation's sweep does
    wherever the measure is symmetric — 'how many contain me' and 'how many do I contain' become
    the same count. Two of the three components then stop being independent, and a mean over
    three of them double-weights one quantity."""
    regions = [{"id": r} for r in ("a", "b", "c")]
    both_ways = []
    for x, y in (("a", "b"), ("b", "c")):
        both_ways += [{"inner_region_id": x, "outer_region_id": y},
                      {"inner_region_id": y, "outer_region_id": x}]
    for rid in ("a", "b", "c"):
        skel = sm.relational_structure(regions, rid, measurements=both_ways)
        assert skel["depth"] == skel["descendant_count"]
