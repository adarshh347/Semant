"""
HARNESS-003E §1 — the request sizing, and the 413 it exists to catch by arithmetic.

The load-bearing test in this file is `test_the_live_413_request_is_refused_before_transport`. Every
other one guards a property that test depends on: that the bound sits above the provider's real
count, that a plan never emits a request larger than the allowance, and that every item is primary
in exactly one batch.
"""
from __future__ import annotations

import pytest

from backend.schemas.semantic_compilation import (BATCH_PLAN_VERSION, BatchBoundaryReason,
                                                  DissolutionPass)
from backend.services.semantic_compilation import architect, sizing
from backend.tests.fixtures import semantic_dissolution_fixtures as F

PASS = DissolutionPass.RELATION_ARCHITECT
INQUIRY = "inq_sizing0001"


def _items(count: int, *, chars: int = 300, affinity: str = "") -> list:
    return [sizing.SizedItem(ref=f"r{i}", text="x" * chars,
                             affinity=affinity or f"g{i // 3}") for i in range(count)]


def _plan(items, *, fixed_text: str = "", completion=None, allowance=None, **kw):
    return sizing.plan(items, inquiry_id=INQUIRY, pass_name=PASS, unit="semantic_atom",
                       fixed_text=fixed_text,
                       completion=completion or sizing.CompletionPolicy.flat(1000),
                       allowance=allowance or sizing.Allowance(), **kw)


# ── the estimate ─────────────────────────────────────────────────────────────

def test_an_empty_string_costs_nothing_and_a_short_one_costs_something():
    """Never zero for non-empty text: a rule that rounded a short item to nothing would pack an
    unbounded number of them into one request."""
    assert sizing.estimate_tokens("") == 0
    assert sizing.estimate_tokens(None) == 0
    assert sizing.estimate_tokens("a") == 1
    assert sizing.estimate_tokens("ab") == 1


def test_the_estimate_is_deterministic_and_monotone():
    short, long = "word " * 10, "word " * 100
    assert sizing.estimate_tokens(long) == sizing.estimate_tokens(long)
    assert sizing.estimate_tokens(long) > sizing.estimate_tokens(short)


def test_the_completion_reservation_is_part_of_the_request_size():
    """Lane A raised the reservation from 4096 to 8192 and every call began failing with a 413. A
    provider charges what you reserve whether or not the model spends it, so a sizing rule that
    looked at the prompt alone would plan batches that fit and send requests that do not."""
    prompt = "the request body"
    lean = sizing.estimate_request_tokens("sys", prompt, completion_tokens=1000)
    fat = sizing.estimate_request_tokens("sys", prompt, completion_tokens=4096)
    assert fat - lean == 3096


# ── the live refusal, caught by arithmetic ───────────────────────────────────

#: How many atoms the refused request actually carried. The architect used to cap one call at forty
#: — `MAX_ATOMS_PER_CALL`, removed by this lane — so the live fold rehearsal sent FORTY, not the 182
#: the 003D finding attributes those 9,827 tokens to. The cap was never a sizing rule; its own
#: comment called forty "what fits under an 8000-token allowance", and the provider disagreed.
LIVE_ATOMS_IN_THE_REFUSED_REQUEST = 40


def _live_shaped_request():
    """The request shape HARNESS-003D's fold rehearsal was refused for.

    The atoms come from the frozen fixture at the density the live dissection produced, repeated to
    reach the count the live run actually sent.
    """
    graph = F.dissolve_fixture("fold-rehearsal")
    units = {u.source_unit_id: u for u in graph.source_units}
    atoms = list(graph.semantic_atoms)
    while len(atoms) < LIVE_ATOMS_IN_THE_REFUSED_REQUEST:
        atoms = atoms + atoms
    atoms = atoms[:LIVE_ATOMS_IN_THE_REFUSED_REQUEST]
    return architect.build_prompt(atoms, units), atoms, units


#: What the provider counted for that request, from its own refusal:
#:     413 … tokens per minute (TPM): Limit 8000, Requested 9827
LIVE_REQUESTED_TOKENS = 9827
LIVE_ALLOWANCE_TOKENS = 8000


def test_the_live_413_request_is_refused_before_transport():
    """The whole lane in one assertion.

    Two separate things are proved. The bound sits ABOVE what the provider actually counted, which
    is the direction the sizing must err in — an estimate under 9,827 would have called that request
    sendable. And the estimate is over the allowance, so no plan may emit it as one batch.

    Measured against THIS lane's prompt, which is compact JSON and about a fifth smaller than the
    one the live run sent. Forty atoms is still unsendable with the fifth taken off, which is the
    fact worth having: the compaction buys room inside a batch, not a way back to one call.
    """
    prompt, _, _ = _live_shaped_request()
    estimate = sizing.estimate_request_tokens(architect.SYSTEM_PROMPT, prompt,
                                              completion_tokens=4096)
    assert estimate >= LIVE_REQUESTED_TOKENS, (
        f"the bound under-estimated the one request this lane exists to refuse: {estimate} < "
        f"{LIVE_REQUESTED_TOKENS} the provider counted")
    assert estimate > LIVE_ALLOWANCE_TOKENS


def test_the_same_atoms_do_fit_once_they_are_planned():
    """The negative control for the test above: refusing everything would also pass it.

    Driven through the architect's own planner rather than a hand-built one, so what is proved is
    that the production partition sends these atoms rather than that some partition could.
    """
    graph = F.dissolve_fixture("fold-rehearsal")
    atoms = list(graph.semantic_atoms)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    assert plan.batches
    assert all(b.sendable for b in plan.batches)
    assert plan.record.every_item_is_primary_once
    for batch in plan.batches:
        assert batch.assignment.estimated_total_tokens <= sizing.Allowance().usable_tokens


# ── the plan ─────────────────────────────────────────────────────────────────

def test_no_planned_request_exceeds_the_allowance():
    """The invariant every other guarantee rests on. `estimated_total_tokens` is the prompt plus the
    reservation, which is what the provider counts."""
    plan = _plan(_items(60), fixed_text="s" * 3000,
                 completion=sizing.CompletionPolicy(reserved_tokens=1200, per_item_tokens=50,
                                                    maximum_tokens=4096))
    assert len(plan.batches) > 1
    for batch in plan.batches:
        assert batch.assignment.estimated_total_tokens <= sizing.Allowance().usable_tokens


def test_every_item_is_primary_in_exactly_one_batch():
    plan = _plan(_items(47), fixed_text="s" * 2000)
    primary = [r for b in plan.record.batches for r in b.primary_refs]
    assert sorted(primary) == sorted(i.ref for i in _items(47))
    assert len(primary) == len(set(primary)) == plan.record.total_items == 47
    assert plan.record.every_item_is_primary_once


def test_planning_the_same_input_twice_produces_the_same_plan():
    """Replay stability. A plan that renumbered itself between two runs of one input would make a
    replay a comparison of two different partitions."""
    first, second = _plan(_items(30), fixed_text="s" * 500), _plan(_items(30), fixed_text="s" * 500)
    assert first.record.model_dump() == second.record.model_dump()
    assert first.record.plan_id.startswith("plan_")
    assert all(b.batch_id.startswith("bat_") for b in first.record.batches)


def test_a_batch_id_follows_its_items_rather_than_its_position():
    """Content-derived, so inserting an item earlier renames the batches it moved between rather
    than renumbering every batch after it."""
    plan = _plan(_items(30), fixed_text="s" * 500)
    by_refs = {tuple(sorted(b.primary_refs)): b.batch_id for b in plan.record.batches}
    again = _plan(list(reversed(_items(30))), fixed_text="s" * 500)
    for batch in again.record.batches:
        key = tuple(sorted(batch.primary_refs))
        if key in by_refs:
            assert batch.batch_id == by_refs[key]


def test_an_affinity_group_that_fits_is_not_split_across_a_boundary():
    """The seam is placed where a relation is least likely to cross."""
    items = ([sizing.SizedItem(ref=f"a{i}", text="x" * 3600, affinity="A") for i in range(3)]
             + [sizing.SizedItem(ref=f"b{i}", text="x" * 3600, affinity="B") for i in range(3)])
    plan = _plan(items, fixed_text="s" * 3000,
                 completion=sizing.CompletionPolicy.flat(2000))
    assert len(plan.batches) == 2
    assert {b.assignment.primary_refs[0][0] for b in plan.batches} == {"a", "b"}
    assert plan.record.batches[0].boundary_reason is BatchBoundaryReason.AFFINITY_BOUNDARY


def test_an_item_no_request_could_carry_is_reported_rather_than_sent():
    """The 413, caught by arithmetic. The item is not trimmed and not dropped — it gets a batch of
    its own that is never sent, and the caller refuses it by name."""
    items = [sizing.SizedItem(ref="small", text="x" * 100, affinity="g"),
             sizing.SizedItem(ref="huge", text="x" * 200_000, affinity="g")]
    plan = _plan(items, fixed_text="s" * 500)
    oversized = [b for b in plan.record.batches if not b.sendable]
    assert [b.primary_refs for b in oversized] == [["huge"]]
    assert oversized[0].boundary_reason is BatchBoundaryReason.OVERSIZED_ITEM
    assert "was NOT sent" in oversized[0].note
    assert [b.assignment.primary_refs for b in plan.sendable] == [["small"]]


def test_a_prompt_whose_fixed_part_already_fills_the_allowance_sends_nothing():
    plan = _plan(_items(4), fixed_text="s" * 60_000)
    assert plan.room_tokens <= 0
    assert plan.sendable == ()
    assert any("no item fits" in n for n in plan.record.notes)


def test_the_plan_says_what_it_was_sized_against():
    plan = _plan(_items(5), fixed_text="s" * 500,
                 allowance=sizing.Allowance(tokens=5000, margin_tokens=250))
    assert plan.record.plan_version == BATCH_PLAN_VERSION
    assert all(b.allowance_tokens == 5000 for b in plan.record.batches)
    assert "5000-token allowance" in plan.record.notes[0]
    assert "holding back 250" in plan.record.notes[0]


# ── the completion policy ────────────────────────────────────────────────────

def test_the_reservation_scales_with_the_batch_and_never_passes_the_declared_ceiling():
    """003D's second-order finding, counted: a reasoning model spends the completion budget before
    it answers, so the reservation carries fixed headroom PLUS a per-item share. The pass's own
    declared budget stays the ceiling — raising it is what produced the 413."""
    policy = sizing.CompletionPolicy(reserved_tokens=1536, per_item_tokens=64, minimum_tokens=1024,
                                     maximum_tokens=4096)
    assert policy.for_batch(0) == 1536
    assert policy.for_batch(10) == 1536 + 640
    assert policy.for_batch(1000) == 4096


def test_a_flat_policy_reserves_the_same_whatever_the_batch_holds():
    policy = sizing.CompletionPolicy.flat(2048)
    assert policy.for_batch(1) == policy.for_batch(50) == 2048


# ── the comparison schedule ──────────────────────────────────────────────────

@pytest.mark.parametrize("count,capacity", [(2, 2), (3, 2), (5, 2), (6, 3), (7, 4), (9, 3),
                                            (12, 5)])
def test_every_pair_of_groups_co_occurs_in_at_least_one_round(count, capacity):
    """The matrix's whole claim. A pair that never shared a request is a relation nobody looked
    for, and a schedule that missed one would let the pass report `completed` over it."""
    groups = [f"g{i}" for i in range(count)]
    rounds = sizing.schedule_rounds(groups, capacity=capacity)
    # Keyed on INDEX rather than on the group name: `"g10" < "g2"` is true of strings and false of
    # what the pair means, and a matrix compared that way would report coverage it does not have.
    rank = {name: i for i, name in enumerate(groups)}
    covered = {(a, b) for members in rounds for a in members for b in members if rank[a] < rank[b]}
    wanted = {(groups[i], groups[j]) for i in range(count) for j in range(i + 1, count)}
    assert wanted <= covered
    assert all(len(set(m)) >= 2 for m in rounds)
    assert all(len(m) <= max(2, capacity) for m in rounds)


def test_one_group_needs_no_round_at_all():
    """Everything already co-occurred: there was one request and it held all of it."""
    assert sizing.schedule_rounds(["only"], capacity=4) == []
    assert sizing.schedule_rounds([], capacity=4) == []


def test_groups_that_all_fit_at_once_are_compared_in_one_round():
    assert sizing.schedule_rounds(["a", "b", "c"], capacity=4) == [["a", "b", "c"]]


def test_the_schedule_is_deterministic():
    groups = [f"g{i}" for i in range(8)]
    assert sizing.schedule_rounds(groups, capacity=3) == sizing.schedule_rounds(groups, capacity=3)


def test_the_matrix_starts_with_every_pair_unexamined_and_says_why():
    pairs = sizing.unexamined_matrix(["a", "b", "c"], "no reconciliation round ran")
    assert len(pairs) == 3
    assert all(not p.examined and p.reason for p in pairs)
    assert {(p.left_batch_id, p.right_batch_id) for p in pairs} == {("a", "b"), ("a", "c"),
                                                                   ("b", "c")}


def test_a_pair_cannot_claim_it_was_examined_without_naming_a_round():
    from pydantic import ValidationError

    from backend.schemas.semantic_compilation import ComparisonPair
    with pytest.raises(ValidationError, match="names no round"):
        ComparisonPair(left_batch_id="a", right_batch_id="b", examined=True)
    with pytest.raises(ValidationError, match="gives no reason"):
        ComparisonPair(left_batch_id="a", right_batch_id="b", examined=False)
    with pytest.raises(ValidationError, match="compares a batch with itself"):
        ComparisonPair(left_batch_id="a", right_batch_id="a", examined=False, reason="x")
