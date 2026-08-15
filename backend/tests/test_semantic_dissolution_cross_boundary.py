"""
HARNESS-003E §7 — a frozen fixture whose one important relation lies BETWEEN two batches.

Everything else in this lane tests a pass in isolation. This drives the whole production pipeline —
ledger, dissector, batched architect, cross-batch reconciliation, batched operationalizer, audit —
over frozen model output, and it is built so that every LOCAL request succeeds while the relation
that matters connects two claims no local request ever saw together.

`test_deleting_the_reconciliation_loses_the_relation_and_the_local_batches_stay_green` is the
negative control and the reason the file exists. A batched architect without the cross-batch half
does not fail loudly; it reports a successful relation search over relations it was structurally
unable to see. That is worse than the 413 it replaces, and it is what this asserts against.

THE SPLIT IS DECLARED, NOT CONTRIVED. `sizing` reads the provider allowance from the environment,
so this suite declares a smaller one — which is a real deployment on a smaller tier, and which also
proves the allowance is genuinely configurable rather than a constant with a settable name.
`test_the_same_fixture_needs_no_batching_at_the_default_allowance` is that claim's control.
"""
from __future__ import annotations

from typing import List

import pytest

from backend.schemas.semantic_compilation import (SCHEMA_VERSION_V2, AtomAuthor, AtomKind,
                                                  ClaimEdgeKind, ClaimKind, DispositionKind,
                                                  DissolutionPass, ImageScope, ItemDispositionKind,
                                                  PassOutcome, canonical)
from backend.services.semantic_compilation import architect, reconciliation, sizing
from backend.services.semantic_compilation.dissolution import dissolve
from backend.tests.fixtures import semantic_dissolution_fixtures as F

NAME = F.CROSS_BOUNDARY

#: The allowance this fixture is sized against. Chosen so the first run's atoms and the second
#: run's fall either side of one boundary — which is what makes the relation between them the one
#: no local request could draw.
DECLARED_ALLOWANCE = "5200"


@pytest.fixture()
def small_allowance(monkeypatch):
    monkeypatch.setenv(sizing.ALLOWANCE_ENV, DECLARED_ALLOWANCE)
    return int(DECLARED_ALLOWANCE)


@pytest.fixture()
def graph(small_allowance):
    return F.dissolve_fixture(NAME)


def _pass(graph, name: DissolutionPass):
    return next(p for p in graph.passes if p.pass_name is name)


def _by_text(graph, fragment: str):
    return next(c for c in graph.claims if fragment in c.text)


# ── the partition is real ────────────────────────────────────────────────────

def test_the_sizing_puts_each_run_in_its_own_request(graph):
    plan = _pass(graph, DissolutionPass.RELATION_ARCHITECT).batch_plan
    assert plan is not None
    assert len(plan.batches) == 2, "the fixture no longer crosses a boundary"
    assert plan.every_item_is_primary_once
    assert plan.total_items == len(graph.semantic_atoms)
    for batch in plan.batches:
        assert batch.sendable
        assert batch.estimated_total_tokens <= sizing.Allowance(
            tokens=int(DECLARED_ALLOWANCE)).usable_tokens


def test_the_same_fixture_needs_no_batching_at_the_default_allowance():
    """The control for the test above. The split is the declared allowance doing its job, not
    something this fixture is shaped to force whatever the account permits."""
    whole = F.dissolve_fixture(NAME)
    plan = _pass(whole, DissolutionPass.RELATION_ARCHITECT).batch_plan
    assert len(plan.batches) == 1
    assert plan.pairs == []


def test_no_local_batch_ever_held_both_ends_of_the_relation(graph):
    plan = _pass(graph, DissolutionPass.RELATION_ARCHITECT).batch_plan
    flat = _by_text(graph, "sits flat across the uprights")
    follows = _by_text(graph, "follows the swell")
    by_atom = {ref: b.batch_id for b in plan.batches for ref in b.primary_refs}
    left = {by_atom[a] for a in flat.atom_refs}
    right = {by_atom[a] for a in follows.atom_refs}
    assert left and right and not (left & right), (
        "the two claims were built from atoms in the same batch, so a local call could have "
        "related them and this fixture proves nothing")


# ── the relation only the cross-batch pass could find ────────────────────────

def test_the_relation_that_matters_is_drawn_across_the_boundary(graph):
    flat = _by_text(graph, "sits flat across the uprights")
    follows = _by_text(graph, "follows the swell")
    crossing = [e for e in graph.claim_edges
                if {e.from_claim, e.to_claim} == {flat.claim_id, follows.claim_id}]
    assert len(crossing) == 1
    assert crossing[0].kind is ClaimEdgeKind.COMPLICATES
    assert crossing[0].why.strip()


def test_the_cross_image_comparison_names_a_parent_in_each_batch(graph):
    plan = _pass(graph, DissolutionPass.RELATION_ARCHITECT).batch_plan
    comparisons = [c for c in graph.claims if c.claim_kind is ClaimKind.COMPARISON]
    assert len(comparisons) == 1
    added = comparisons[0]
    assert len(added.inferred_from) == 2
    assert added.atom_refs == [], "a cross-batch inference follows from claims, not from atoms"
    # A comparison across images may never be scoped to one of them.
    assert added.image_scope is not ImageScope.ONE_IMAGE

    by_atom = {ref: b.batch_id for b in plan.batches for ref in b.primary_refs}
    by_claim = {c.claim_id: c for c in graph.claims}
    homes = {next(iter({by_atom[a] for a in by_claim[p].atom_refs}))
             for p in added.inferred_from}
    assert len(homes) == 2, "both parents came from the same batch"


def test_every_pair_of_batches_was_actually_compared(graph):
    plan = _pass(graph, DissolutionPass.RELATION_ARCHITECT).batch_plan
    assert plan.pairs
    assert plan.unexamined_pairs == []
    assert plan.pairs_examined == len(plan.pairs)
    assert plan.rounds and all(r.outcome is PassOutcome.COMPLETED for r in plan.rounds)
    assert sum(r.added_edges for r in plan.rounds) == 1
    assert sum(r.added_claims for r in plan.rounds) == 1


def test_deleting_the_reconciliation_loses_the_relation_and_the_local_batches_stay_green(
        small_allowance):
    """THE NEGATIVE CONTROL, and the reason this file exists.

    With the cross-batch half removed the local batches still succeed and still produce claims. The
    relation between them is simply absent — and the pass refuses to call itself completed, which is
    the only thing standing between a batched architect and a green report over a search it never
    performed.
    """
    council = F.council_for(NAME)

    def no_rounds(merged, *, plan, **kwargs):
        groups = [b.batch_id for b in plan.batches
                  if any(merged.batch_of.get(c) == b.batch_id for c in merged.claims)]
        return [], reconciliation.matrix_for(groups, [], {}), []

    council.architect._reconcile = no_rounds
    graph = dissolve(F.request_for(NAME), council)

    assert len(graph.claims) >= 6, "the local batches produced nothing, so nothing is being tested"
    assert not [c for c in graph.claims if c.claim_kind is ClaimKind.COMPARISON]
    flat = _by_text(graph, "sits flat across the uprights")
    follows = _by_text(graph, "follows the swell")
    assert not [e for e in graph.claim_edges
                if {e.from_claim, e.to_claim} == {flat.claim_id, follows.claim_id}]

    receipt = _pass(graph, DissolutionPass.RELATION_ARCHITECT)
    assert receipt.outcome is PassOutcome.THIN
    assert "never compared" in receipt.detail
    assert receipt.batch_plan.unexamined_pairs


# ── one pass along: the fork that spans the batches ──────────────────────────

def test_a_fork_spanning_two_batches_is_found_by_the_final_round(graph):
    plan = _pass(graph, DissolutionPass.EPISTEMIC_OPERATIONALIZER).batch_plan
    assert len(plan.batches) >= 2
    assert graph.decision_candidates, "the fork spanning the batches was lost"
    fork = graph.decision_candidates[0]
    assert len(fork.affected_refs) == 2
    assert len(fork.options) >= 2
    assert fork.why_now.strip()

    by_claim = {c.claim_id: c for c in graph.claims}
    homes = {b.batch_id for b in plan.batches
             for r in fork.affected_refs if r in b.primary_refs}
    assert len(homes) == 2, "the fork's two claims were primary in the same batch"
    assert all(r in by_claim for r in fork.affected_refs)


def test_a_remainder_item_may_name_claims_from_more_than_one_batch(graph):
    spanning = [r for r in graph.semantic_remainder if len(r.claim_refs) > 1]
    assert spanning
    assert all(item.why.strip() for item in graph.semantic_remainder)


def test_every_claim_carries_a_disposition_and_every_atom_does_too(graph):
    ops = _pass(graph, DissolutionPass.EPISTEMIC_OPERATIONALIZER).batch_plan
    arch = _pass(graph, DissolutionPass.RELATION_ARCHITECT).batch_plan
    assert {d.ref for d in ops.dispositions} == {c.claim_id for c in graph.claims}
    assert {d.ref for d in arch.dispositions} == {a.atom_id for a in graph.semantic_atoms}
    for entry in [*ops.dispositions, *arch.dispositions]:
        if entry.disposition in (ItemDispositionKind.REFUSED,
                                 ItemDispositionKind.NOT_INVESTIGATED):
            assert entry.reason.strip()


# ── the laws that must survive the batching ──────────────────────────────────

def test_the_whole_pipeline_completes(graph):
    assert graph.schema_version == SCHEMA_VERSION_V2
    assert [p.outcome for p in graph.passes] == [PassOutcome.COMPLETED] * len(graph.passes)
    assert graph.refusals == []
    assert graph.notes[-1].startswith("dissolution: completed")


def test_every_source_unit_still_has_exactly_one_disposition(graph):
    seen = [c.source_unit_id for c in graph.coverage]
    assert sorted(seen) == sorted({u.source_unit_id for u in graph.source_units})
    assert len(seen) == len(set(seen))
    assert all(c.disposition is DispositionKind.REPRESENTED_BY for c in graph.coverage)


def test_the_persons_own_clauses_stay_attributed_to_them(graph):
    theirs = [a for a in graph.semantic_atoms if a.author is AtomAuthor.USER]
    assert theirs
    by_unit = {u.source_unit_id: u for u in graph.source_units}
    for atom in theirs:
        assert all(by_unit[u].is_user_authored for u in atom.source_unit_ids)
    assert any(a.unit_kind is AtomKind.CAUSAL_HYPOTHESIS for a in theirs)
    assert any(a.unit_kind is AtomKind.GENERATIVE_PROPOSAL for a in theirs)


def test_the_prompt_survives_byte_for_byte(graph):
    assert graph.prompt == F.prompt_for(NAME)
    for unit in graph.source_units:
        if unit.span:
            assert graph.prompt[unit.span[0]:unit.span[1]] == unit.exact_quote


# ── replay ───────────────────────────────────────────────────────────────────

def test_dissolving_the_fixture_twice_is_byte_identical(small_allowance):
    assert canonical(F.dissolve_fixture(NAME)) == canonical(F.dissolve_fixture(NAME))


def test_a_replay_makes_no_live_call(graph):
    assert all(p.provider is None for p in graph.passes)
    assert all(not p.prompt_tokens for p in graph.passes)


def test_no_id_is_hardcoded_in_the_fixture():
    raw = (F.FIXTURE_DIR / f"{NAME}.json").read_text(encoding="utf-8")
    for prefix in ("su_", "atm_", "clm_", "obs_", "cle_", "dec_", "cov_", "rb_", "bat_", "rnd_",
                   "plan_"):
        assert prefix not in raw, f"{NAME} hardcodes a {prefix!r} id"


def test_every_marker_resolved(graph):
    import json
    body = json.dumps(graph.model_dump(mode="json", by_alias=True))
    for marker in (F.UNIT_MARKER, F.ATOM_MARKER, F.CLAIM_MARKER):
        assert marker not in body, f"{marker} survived into the graph unresolved"


def test_this_fixture_shares_no_topic_noun_with_either_of_the_other_two():
    mine = set(F.load(NAME)["topic_nouns"])
    for other in F.FIXTURES:
        assert not mine & set(F.load(other)["topic_nouns"])
    assert mine <= set(F.topic_nouns()), "the generality scan does not read this fixture's subject"
