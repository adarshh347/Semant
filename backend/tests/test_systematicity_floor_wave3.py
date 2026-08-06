"""
WAVE3 — the systematicity score: agreement is agreement about things that exist.

Two lanes' worth of claims live here. The floor lane audited `MIN_SYSTEMATICITY` and found the
score partly measuring absence; this lane changed the aggregation so it does not, and re-derived
the floor — which turned out to have no derivation left. The corpus numbers live in
`scripts/systematicity_floor_audit.py` and cannot live here (Mongo, 129,564 scored pairs). What
belongs in the suite is everything both lanes CONCLUDED, in a form that breaks if it is undone:

  1. **absence abstains.** A component neither side has no longer counts toward agreement. The
     old rule stays runnable so the comparison remains a measurement rather than a memory.
  2. **the decomposition is honest.** `live`, `earned` and `absence_share` describe the same three
     components the score is built from, and shared absence is reported rather than banked.
  3. **the floor has no derivation left**, and the arithmetic showing why is a test rather than a
     paragraph. So is the fact that the two principled-sounding replacements were measured and
     refuted.
  4. **the floor is nesting's.** `relational_structure` is nesting-shaped, and a test shows what
     it does to a symmetric relation rather than leaving that to a docstring.

Two claims are deliberately NOT tested here. The separation figures (+20.3 → +25.7) are facts about
this corpus, not this code — pinning them would make the suite fail when the corpus grows, which is
the wrong thing to be told. And the residual inversion is likewise a corpus statistic; what IS
pinned is the mechanism behind it, since that is a property of the rule.
"""
import inspect

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

def test_the_shape_derivation_still_holds_for_the_aggregation_it_was_about():
    """The floor lane's derivation was not wrong; it was scoped. Under `shape` there are always
    three components, one of them is always exactly a third, and 2,178 corpus pairs sit on that
    value. This keeps the arithmetic checkable now that the default has moved off it."""
    assert sm.ONE_COMPONENT_SHARE == pytest.approx(1 / 3)
    assert round(sm.ONE_COMPONENT_SHARE + sm.SYSTEMATICITY_EPSILON, 5) == sm.MIN_SYSTEMATICITY

    one_only = sm.systematicity(skeleton(depth=2, siblings=3, descendants=4),
                                skeleton(depth=2, siblings=0, descendants=0),
                                aggregation=sm.AGGREGATION_SHAPE)
    # depth agrees 1.0; siblings 3-vs-0 and descendants 4-vs-0 both align to 0.
    assert one_only["score"] == pytest.approx(1 / 3, abs=1e-6)
    assert one_only["score"] < sm.MIN_SYSTEMATICITY


def test_the_floor_did_not_move_so_the_before_after_measures_one_thing():
    """DELIBERATE, and the reason is methodological rather than conservative. Separation is flat
    across 0.15–0.60 (+25.7 to +29.6, non-monotonic), so no value is measurably better and picking
    the argmax of a flat noisy curve is fitting. Holding it constant isolates the aggregation
    change: move both and the before/after measures two things and attributes neither."""
    assert sm.MIN_SYSTEMATICITY == 0.34


def test_one_components_worth_is_not_a_single_number_under_present():
    """WHY THE DERIVATION DIED, as arithmetic rather than as a claim.

    The floor lane derived `MIN_SYSTEMATICITY` from `ONE_COMPONENT_SHARE + eps`, and that was
    correct — for `shape`, where the mean was always over three components, so one of them was
    always exactly a third. `present` averages over the LIVE components, so the score of a pair
    that agrees on exactly one is 1/3, 1/2 or 1/1 depending on how many were live. No scalar
    floor expresses "more than one predicate" across all three cases, which is why the number
    above is now an operating point and not a derivation.
    """
    live_three = sm.systematicity(skeleton(depth=2, siblings=3, descendants=4),
                                  skeleton(depth=2, siblings=0, descendants=0))
    assert live_three["live"] == ["depth", "descendants", "siblings"]
    assert live_three["score"] == pytest.approx(1 / 3)

    live_two = sm.systematicity(skeleton(depth=2, siblings=3, descendants=0),
                                skeleton(depth=2, siblings=0, descendants=0))
    assert live_two["live"] == ["depth", "siblings"]
    assert live_two["score"] == pytest.approx(1 / 2)

    live_one = sm.systematicity(skeleton(depth=2, siblings=0, descendants=0),
                                skeleton(depth=2, siblings=0, descendants=0))
    assert live_one["live"] == ["depth"]
    assert live_one["score"] == pytest.approx(1.0)


def test_the_adaptive_floor_that_would_have_been_principled_was_measured_and_rejected():
    """`score > 1/live` generalises the WAVE2 intent exactly, and it is worse: +18.5 points
    against the held-out criterion versus +25.7 for the flat floor, because it refuses all 894
    single-live pairs and those pairs' containers map 54.1% of the time against a 30.8% base.

    Kept as a test because the rule is attractive enough that someone will propose it again. The
    arithmetic it turns on is here; the corpus numbers are in the audit script.
    """
    live_one = sm.systematicity(skeleton(depth=2, siblings=0, descendants=0),
                                skeleton(depth=2, siblings=0, descendants=0))
    # A mean over one component cannot exceed 1/1, so the adaptive rule refuses every such pair
    # however perfectly it agrees.
    assert live_one["score"] == 1.0
    assert not live_one["score"] > 1 / len(live_one["live"])


# ── 2. the decomposition is honest about shared absence ──────────────────────────────────────

def test_a_component_neither_side_has_no_longer_counts_toward_agreement():
    """THE CHANGE. `_alignment` still scores 0-vs-0 as 1.0 — it is a pairwise primitive and that
    is a defensible thing for it to say — but the score no longer AVERAGES that in. Under `shape`
    two shared absences banked two thirds of a perfect score; under `present` they abstain."""
    poor = skeleton(depth=2, siblings=0, descendants=0)
    rich_ish = skeleton(depth=4, siblings=0, descendants=0)
    verdict = sm.systematicity(poor, rich_ish)
    assert verdict["live"] == ["depth"]
    assert verdict["absence_share"] == pytest.approx(2 / 3)
    assert verdict["score"] == verdict["components"]["depth"] == pytest.approx(0.5)
    assert verdict["shape_score"] == pytest.approx((0.5 + 1.0 + 1.0) / 3)


def test_withdrawing_the_credit_does_not_make_a_one_component_mean_stable():
    """THE RESIDUAL, PINNED AS A MECHANISM. `present` fixes the free credit and not the variance:
    where siblings and descendants are absent on both sides the score is depth alone, so a pair
    with no structure at all whose depths happen to match still scores 1.0.

    On the corpus the zero-structure bucket falls 0.842 → 0.525 and remains the highest of any
    bucket. The inversion is 79% removed, not eliminated, and this is why — it is a property of
    averaging one number, not of what the rule credits.
    """
    verdict = sm.systematicity(skeleton(depth=2, siblings=0, descendants=0),
                               skeleton(depth=2, siblings=0, descendants=0))
    assert verdict["live"] == ["depth"]
    assert verdict["score"] == 1.0          # still the maximum, on no structure whatsoever
    assert verdict["shape_score"] == 1.0


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


# ── 3. the default moved, deliberately and with the old one kept runnable ────────────────────

def test_present_is_the_default_aggregation():
    """The floor lane measured `present` better and refused to adopt it under cover of an audit.
    This lane is that adoption, with its own before/after: separation +20.3 → +25.7 against the
    held-out criterion, and the poverty inversion 79% removed."""
    assert sm.DEFAULT_AGGREGATION == sm.AGGREGATION_PRESENT
    assert sm.systematicity(skeleton(), skeleton())["aggregation"] == sm.AGGREGATION_PRESENT
    assert sm.structure_map(skeleton("a", parent="pa"),
                            skeleton("b", parent="pb"))["systematicity"]["aggregation"] \
        == sm.AGGREGATION_PRESENT


def test_the_rule_that_was_replaced_is_still_runnable():
    """A claim of improvement that cannot be re-measured against what it improved on is not a
    measurement. `shape` stays, the way #150 kept `ranking="identity"`."""
    source = skeleton(depth=2, siblings=0, descendants=4)
    target = skeleton(depth=4, siblings=0, descendants=1)
    present = sm.structure_map(source, target)
    shape = sm.structure_map(source, target, aggregation=sm.AGGREGATION_SHAPE)
    # siblings are 0-vs-0: `shape` banks a free 1/3 for it, `present` abstains.
    assert shape["systematicity"]["score"] > present["systematicity"]["score"]
    assert shape["systematicity"]["aggregation"] == sm.AGGREGATION_SHAPE


def test_an_unknown_aggregation_raises_rather_than_falling_back():
    """Silently defaulting would let a typo produce a number that looks like the other rule's."""
    with pytest.raises(ValueError):
        sm.systematicity(skeleton(), skeleton(), aggregation="whatever")


def test_the_score_key_still_means_what_the_gate_reads():
    """`score` is what `structure_map` compares to the floor. It must follow the aggregation, or
    both readings would be reported honestly and the gate would still read the old one."""
    source = skeleton(depth=2, siblings=0, descendants=4)
    target = skeleton(depth=4, siblings=0, descendants=1)
    default = sm.systematicity(source, target)
    assert default["score"] == default["present_score"] != default["shape_score"]
    alt = sm.systematicity(source, target, aggregation=sm.AGGREGATION_SHAPE)
    assert alt["score"] == alt["shape_score"]


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
