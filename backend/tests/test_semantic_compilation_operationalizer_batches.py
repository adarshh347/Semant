"""
HARNESS-003E §5 — the operationalizer, batched, with each claim answered for exactly once.

The rule this file exists to hold is the PRIMARY/CONTEXT split. The old pass made one call over the
whole graph and its comment gave the reason: what is observable about a claim depends on the other
claims, so a batched operationalizer would propose the same observable twice from two halves. That
reason is right, and the arrangement it justified is unsendable. The split answers both — the
neighbours are in view, and only primary ids may receive an observable.

`test_a_contextual_claim_is_not_operationalized_from_its_neighbours_batch` is the one that would
fail if that split were dropped.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

import pytest

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (CapacityWaitRecord, ClaimEdge, ClaimEdgeKind,
                                                  ClaimKind, ClaimStatus, DissolutionPass,
                                                  ImageScope, ItemDispositionKind, PassOutcome,
                                                  PassReceipt, SourcePointer, SourceType)
from backend.services.semantic_compilation import ids, operationalizer, reconciliation, sizing
from backend.services.semantic_compilation.architect import _Merged  # noqa: F401  (shape check)
from backend.services.semantic_compilation.passes import PassResult
from backend.schemas.semantic_compilation import ClaimNode

INQUIRY = "inq_ops0001"


def claim(n: int, *, kind: ClaimKind = ClaimKind.ATTRIBUTE, text: str = "",
          demand: DemandKind = DemandKind.MEASURABLE, pad: int = 0) -> ClaimNode:
    body = text or f"claim number {n} says one thing" + (" with more words" * pad)
    return ClaimNode(
        claim_id=ids.claim_id(INQUIRY, kind, body), text=body, claim_kind=kind,
        subject=f"subject {n}", predicate="is", object=f"object {n}",
        sources=[SourcePointer(source_type=SourceType.SCENE_READING, source_id=f"rb_{n}",
                               text=body)],
        image_scope=ImageScope.CORPUS, epistemic_demand=demand,
        status=ClaimStatus.INTERPRETIVE, atom_refs=[f"atm_{n:04d}"])


def edge(a: ClaimNode, b: ClaimNode, kind: ClaimEdgeKind = ClaimEdgeKind.SUPPORTS) -> ClaimEdge:
    return ClaimEdge(edge_id=ids.edge_id(INQUIRY, kind, a.claim_id, b.claim_id), kind=kind,
                     from_claim=a.claim_id, to_claim=b.claim_id, why="because")


def observable_row(claim_id: str, *, ref: str = "o1", kind: str = "extent of the thing",
                   classes: Sequence[str] = ("extent",), targets: Sequence[str] = ("a target",)):
    return {"ref": ref, "claim": claim_id, "kind": kind, "targets": list(targets),
            "image_scope": "corpus", "capability_classes": list(classes),
            "ground_forms": ["scalar"], "success_when": "it resolves",
            "ambiguous_when": "it does not", "refused_when": "nothing is there",
            "remains_interpretive": "what it means stays a reading", "alternatives": []}


def remainder_row(term: str, claims: Sequence[str]):
    return {"term": term, "why": "no instrument reaches it",
            "contributing_capability_classes": ["semantic_reading"], "claims": list(claims)}


def decision_row(question: str, affects: Sequence[str]):
    return {"kind": "choose_operationalization", "question": question,
            "why_now": "it changes which instrument runs", "affects": list(affects),
            "blocking": False,
            "options": [{"label": "one", "consequence": "a", "recommended": True},
                        {"label": "two", "consequence": "b", "recommended": False}]}


class _Scripted(operationalizer.EpistemicOperationalizer):
    """A scripted answer per batch request and per cross-batch round, told apart by system prompt."""

    def __init__(self, batches: Sequence[Any], forks: Sequence[Any] = (), *,
                 truncate: Sequence[int] = (), stop_after_round: Optional[int] = None):
        super().__init__(client=None)
        self.batches = list(batches)
        self.forks = list(forks)
        self.truncate = set(truncate)
        self.stop_after_round = stop_after_round
        self.batch_prompts: List[str] = []
        self.fork_prompts: List[str] = []
        self.completion_budgets: List[int] = []

    def is_available(self) -> bool:
        return True

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1, inputs: int = 0,
               system_prompt: Optional[str] = None, estimated_prompt_tokens: int = 0,
               completion_tokens: Optional[int] = None) -> PassResult:
        is_fork = system_prompt == operationalizer.FORK_SYSTEM_PROMPT
        self.calls += 1
        waits: List[CapacityWaitRecord] = []
        if is_fork:
            index = len(self.fork_prompts)
            self.fork_prompts.append(user_prompt)
            payload = self.forks[index] if index < len(self.forks) else {}
            if self.stop_after_round is not None and index + 1 >= self.stop_after_round:
                waits = [CapacityWaitRecord(attempt=1, seconds=2400.0, source="budget_exhausted",
                                            detail="retry-after: 2400", taken=False)]
        else:
            index = len(self.batch_prompts)
            self.batch_prompts.append(user_prompt)
            self.completion_budgets.append(completion_tokens or 0)
            payload = self.batches[index] if index < len(self.batches) else {}
        receipt = PassReceipt(
            pass_id=ids.pass_id(inquiry_id, DissolutionPass.EPISTEMIC_OPERATIONALIZER, attempt),
            pass_name=DissolutionPass.EPISTEMIC_OPERATIONALIZER,
            outcome=PassOutcome.TRUNCATED if index in self.truncate and not is_fork
            else PassOutcome.COMPLETED,
            call_count=1,
            finish_reasons=["length"] if index in self.truncate and not is_fork else ["stop"],
            inputs=inputs, transport_attempts=1 + len(waits), capacity_waits=waits,
            detail="scripted")
        return PassResult(payload, receipt)


def _two_batch_graph(count: int = 60, pad: int = 6):
    """Enough claims for more than one batch, joined in one chain.

    A CHAIN rather than one edge, because the affinity keeps a whole connected component together
    where it fits: two claims joined by a single edge simply land in the same batch, and nothing
    about context would be exercised. A component larger than one request is the case that matters
    and the one a real graph produces — it is split, and the seams are where context appears.
    """
    claims = [claim(i, pad=pad) for i in range(count)]
    edges = [edge(claims[i], claims[i + 1]) for i in range(count - 1)]
    plan = operationalizer.EpistemicOperationalizer().plan_batches(claims, edges,
                                                                   inquiry_id=INQUIRY)
    assert len(plan.batches) >= 2, "the fixture must actually cross a boundary"
    return claims, edges, plan


# ── the partition ────────────────────────────────────────────────────────────

def test_a_graph_too_large_for_one_request_becomes_several():
    claims, edges, plan = _two_batch_graph()
    assert plan.record.every_item_is_primary_once
    assert plan.record.total_items == len(claims)
    for batch in plan.batches:
        assert batch.assignment.estimated_total_tokens <= sizing.Allowance().usable_tokens


def test_claims_joined_by_an_edge_travel_together_or_as_each_others_context():
    """Claims that relate are the ones whose forks are only visible together, so an edge is either
    inside a batch or spans one as context — never invisible."""
    claims, edges, plan = _two_batch_graph()
    seen = 0
    for e in edges:
        for batch in plan.batches:
            if e.from_claim not in batch.assignment.primary_refs \
                    and e.to_claim not in batch.assignment.primary_refs:
                continue
            both = set(batch.assignment.primary_refs) | set(batch.assignment.context_refs)
            assert {e.from_claim, e.to_claim} <= both, \
                "an edge's two ends were invisible to each other"
            seen += 1
    assert seen >= len(edges), "the check reached no edge"


def test_the_completion_reservation_follows_the_batch():
    claims, edges, _plan = _two_batch_graph()
    pas = _Scripted([])
    pas.operationalize(claims, edges, inquiry_id=INQUIRY)
    assert pas.completion_budgets
    assert all(0 < b <= operationalizer.DEFAULT_BUDGET.max_completion_tokens
               for b in pas.completion_budgets)


# ── primary and context ──────────────────────────────────────────────────────

def test_a_contextual_claim_is_not_operationalized_from_its_neighbours_batch():
    """THE RULE THE SPLIT EXISTS FOR. Without it, a claim that is contextual in two batches collects
    an observable from each and the graph reports one claim as investigated three ways."""
    claims, edges, plan = _two_batch_graph()
    # A claim that is primary in one batch and CONTEXTUAL in another — the seam of the chain, which
    # is the only place the rule can be exercised.
    first = next(r for b in plan.batches for r in b.assignment.context_refs)
    holder = next(b for b in plan.batches if first in b.assignment.primary_refs)
    stranger = next(b for b in plan.batches if first in b.assignment.context_refs)
    answers = [{} for _ in plan.batches]
    answers[holder.assignment.index - 1] = {"observables": [observable_row(first)]}
    answers[stranger.assignment.index - 1] = {
        "observables": [observable_row(first, ref="o2", kind="a second look at the same claim")]}

    observables, _d, _r, refusals, _n, receipt = _Scripted(answers).operationalize(
        claims, edges, inquiry_id=INQUIRY)

    assert [o.claim_id for o in observables] == [first]
    assert any("only as CONTEXT" in r.why for r in refusals)
    assert receipt.batch_plan is not None


def test_the_prompt_marks_which_claims_may_be_answered_for():
    claims, edges, plan = _two_batch_graph()
    pas = _Scripted([])
    pas.operationalize(claims, edges, inquiry_id=INQUIRY)
    holder = next(b for b in plan.batches if b.assignment.context_refs)
    prompt = pas.batch_prompts[holder.assignment.index - 1]
    assert "CONTEXT ONLY" in prompt
    assert "context_claims" in prompt
    for ref in holder.assignment.context_refs:
        assert ref in prompt


def test_the_per_claim_observable_bound_is_global_rather_than_per_batch():
    """A claim primary in one batch and contextual in two others would otherwise collect three
    times `MAX_OBSERVABLES_PER_CLAIM`."""
    claims, edges, plan = _two_batch_graph()
    first = claims[0].claim_id
    holder = next(b for b in plan.batches if first in b.assignment.primary_refs)
    answers = [{} for _ in plan.batches]
    answers[holder.assignment.index - 1] = {"observables": [
        observable_row(first, ref=f"o{i}", kind=f"way number {i} of looking at it")
        for i in range(operationalizer.MAX_OBSERVABLES_PER_CLAIM + 3)]}

    observables, _d, _r, _refusals, notes, _receipt = _Scripted(answers).operationalize(
        claims, edges, inquiry_id=INQUIRY)
    assert len([o for o in observables if o.claim_id == first]) \
        == operationalizer.MAX_OBSERVABLES_PER_CLAIM
    assert any("more than" in n for n in notes)


def test_the_same_observable_from_two_batches_is_kept_once():
    claims, edges, plan = _two_batch_graph()
    first, second = claims[0].claim_id, claims[1].claim_id
    answers = [{"observables": [observable_row(first)]} for _ in plan.batches]
    observables, _d, _r, _ref, _n, _receipt = _Scripted(answers).operationalize(
        claims, edges, inquiry_id=INQUIRY)
    assert len({o.observable_id for o in observables}) == len(observables)


# ── every claim gets a disposition ───────────────────────────────────────────

def test_every_claim_carries_an_explicit_disposition():
    """An empty observable list may be right for a wholly interpretive graph. Silence about a claim
    never is."""
    claims, edges, plan = _two_batch_graph()
    answers = [{"observables": [observable_row(b.assignment.primary_refs[0])],
                "semantic_remainder": [remainder_row(f"residue {i}",
                                                     [b.assignment.primary_refs[1]])]}
               for i, b in enumerate(plan.batches)]
    _o, _d, _r, _ref, _n, receipt = _Scripted(answers, forks=[{}] * 40).operationalize(
        claims, edges, inquiry_id=INQUIRY)

    record = receipt.batch_plan
    assert {d.ref for d in record.dispositions} == {c.claim_id for c in claims}
    kinds = {d.disposition for d in record.dispositions}
    assert ItemDispositionKind.OPERATIONALIZED in kinds
    assert ItemDispositionKind.SEMANTIC_REMAINDER in kinds
    assert ItemDispositionKind.NOT_INVESTIGATED in kinds
    for entry in record.dispositions:
        if entry.disposition is ItemDispositionKind.NOT_INVESTIGATED:
            assert entry.reason.strip()


def test_a_claim_no_request_could_carry_is_refused_before_transport():
    small = claim(1)
    huge = claim(2, text="w " * 40_000)
    pas = _Scripted([{"observables": [observable_row(small.claim_id)]}])
    _o, _d, _r, refusals, _n, receipt = pas.operationalize([small, huge], [], inquiry_id=INQUIRY)

    assert receipt.outcome is PassOutcome.COVERAGE_FAILED
    assert any(r.what == huge.claim_id for r in refusals)
    assert [d.disposition for d in receipt.batch_plan.dispositions
            if d.ref == huge.claim_id] == [ItemDispositionKind.REFUSED]


def test_one_truncated_batch_makes_the_whole_pass_truncated():
    claims, edges, plan = _two_batch_graph()
    answers = [{"observables": [observable_row(b.assignment.primary_refs[0])]}
               for b in plan.batches]
    _o, _d, _r, _ref, _n, receipt = _Scripted(answers, truncate=[1]).operationalize(
        claims, edges, inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.TRUNCATED
    assert "1 of" in receipt.detail


def test_no_claim_means_no_request_and_says_so():
    _o, _d, _r, _ref, notes, receipt = _Scripted([]).operationalize([], [], inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.EMPTY
    assert notes == ["there was no claim to operationalize"]


# ── the cross-batch fork pass ────────────────────────────────────────────────

def test_a_fork_that_spans_two_batches_is_found_by_the_final_round():
    claims, edges, plan = _two_batch_graph()
    a = plan.batches[0].assignment.primary_refs[0]
    b = plan.batches[1].assignment.primary_refs[0]
    answers = [{"observables": [observable_row(bb.assignment.primary_refs[0])]}
               for bb in plan.batches]
    forks = [{"decisions": [decision_row("which of these two to follow", [a, b])],
              "semantic_remainder": [remainder_row("what spans both", [a, b])]}] * 40

    _o, decisions, remainder, _ref, _n, receipt = _Scripted(answers, forks).operationalize(
        claims, edges, inquiry_id=INQUIRY)

    assert [d.question for d in decisions] == ["which of these two to follow"]
    assert set(decisions[0].affected_refs) == {a, b}
    assert any(item.term == "what spans both" for item in remainder)
    assert receipt.batch_plan.rounds
    assert receipt.batch_plan.pairs_examined == len(receipt.batch_plan.pairs)


def test_the_final_round_may_not_propose_an_observable():
    """Every claim was already answered for by the batch it was primary in. A second observable
    here is one claim operationalized twice."""
    claims, edges, plan = _two_batch_graph()
    a = plan.batches[0].assignment.primary_refs[0]
    answers = [{"observables": [observable_row(bb.assignment.primary_refs[0])]}
               for bb in plan.batches]
    forks = [{"observables": [observable_row(a, ref="ox", kind="a third look")],
              "decisions": [], "semantic_remainder": []}] * 40

    observables, _d, _r, refusals, _n, _receipt = _Scripted(answers, forks).operationalize(
        claims, edges, inquiry_id=INQUIRY)
    assert all(o.observable_kind != "a third look" for o in observables)
    assert any(r.what == "observables" for r in refusals)


def test_one_batch_needs_no_final_round_and_says_why():
    claims = [claim(i) for i in range(3)]
    plan = operationalizer.EpistemicOperationalizer().plan_batches(claims, [], inquiry_id=INQUIRY)
    assert len(plan.batches) == 1
    pas = _Scripted([{"observables": [observable_row(c.claim_id, ref=f"o{i}")
                                      for i, c in enumerate(claims)]}])
    _o, _d, _r, _ref, notes, receipt = pas.operationalize(claims, [], inquiry_id=INQUIRY)
    assert pas.fork_prompts == []
    assert receipt.batch_plan.pairs == []
    assert any("nothing across" in n for n in notes)


def test_a_budget_that_stops_the_final_pass_names_the_pairs_it_never_reached():
    """The decision's honest ending. `the budget ran out` and `no fork spans these two` are opposite
    reports and may not render alike."""
    claims, edges, plan = _two_batch_graph(count=60, pad=6)
    assert len(plan.batches) >= 4
    answers = [{"observables": [observable_row(b.assignment.primary_refs[0], ref=f"o{i}")]}
               for i, b in enumerate(plan.batches)]
    pas = _Scripted(answers, [{}] * 60, stop_after_round=1)
    _o, _d, _r, _ref, notes, receipt = pas.operationalize(claims, edges, inquiry_id=INQUIRY)

    record = receipt.batch_plan
    assert len(record.rounds) >= 1, "no cross-batch round ran, so nothing could be stopped"
    assert len(pas.fork_prompts) == 1, "the schedule kept going after the budget stopped it"
    assert record.unexamined_pairs
    assert all(p.reason == reconciliation.NOT_REACHED for p in record.unexamined_pairs)
    assert any("declared budget" in n for n in notes)
    assert receipt.outcome is PassOutcome.THIN


def test_a_remainder_term_two_batches_both_name_is_one_remainder():
    claims, edges, plan = _two_batch_graph()
    answers = [{"observables": [observable_row(b.assignment.primary_refs[0])],
                "semantic_remainder": [remainder_row("the same residue",
                                                     [b.assignment.primary_refs[1]])]}
               for b in plan.batches]
    _o, _d, remainder, _ref, _n, _receipt = _Scripted(answers, [{}] * 40).operationalize(
        claims, edges, inquiry_id=INQUIRY)
    assert [r.term for r in remainder].count("the same residue") == 1
