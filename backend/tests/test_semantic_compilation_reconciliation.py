"""
HARNESS-003E §3 — the cross-batch pass, and the relation that only exists between two batches.

THE LOAD-BEARING TEST IS `test_the_only_important_relation_crosses_a_batch_boundary`. It is built so
that every local batch succeeds and produces claims, and the one relation that matters connects two
claims that were never in the same request. Delete the reconciliation and the local batches still
go green — which is exactly the failure mode this lane exists to prevent, and why that test asserts
on the edge rather than on the pass's outcome alone.

`test_removing_the_reconciliation_loses_the_relation` is its negative control: it drives the same
material with the rounds suppressed and shows the edge is gone and the pass refuses to call itself
completed.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

import pytest

from backend.schemas.semantic_compilation import (AtomKind, CapacityWaitRecord, ClaimEdgeKind,
                                                  ClaimKind, DissolutionPass, ImageScope,
                                                  PassOutcome, PassReceipt)
from backend.services.semantic_compilation import architect, ids, reconciliation, sizing
from backend.services.semantic_compilation.passes import PassResult
from backend.tests.test_semantic_compilation_architect_batches import (INQUIRY, atom, claim_row,
                                                                       corpus, unit)


def edge_row(source: str, target: str, kind: str = "supports", why: str = "because"):
    return {"kind": kind, "from": source, "to": target, "why": why}


def cross_claim(text: str, parents: Sequence[str], *, kind: str = "comparison"):
    return {"text": text, "kind": kind, "inferred_from": list(parents), "subject": "s",
            "predicate": "p", "object": "o", "image_scope": "corpus", "demand": "interpretive",
            "status": "interpretive", "note": ""}


class _Council(architect.RelationArchitect):
    """The architect with a scripted answer per LOCAL batch and per RECONCILIATION round.

    The two are told apart by the system prompt the pass hands `invoke`, which is exactly how the
    production code distinguishes them — a test that counted calls instead would pass against an
    architect that sent the local prompt to every request.
    """

    def __init__(self, local: Sequence[Any], rounds: Sequence[Any] = (), *,
                 skip_rounds: bool = False, stop_after_round: Optional[int] = None):
        super().__init__(client=None)
        self.local = list(local)
        self.rounds = list(rounds)
        self.skip_rounds = skip_rounds
        self.stop_after_round = stop_after_round
        self.local_prompts: List[str] = []
        self.round_prompts: List[str] = []

    def is_available(self) -> bool:
        return True

    def _reconcile(self, merged, *, plan, **kwargs):
        """`skip_rounds` sends no round at all, leaving every pair unexamined.

        Deliberately NOT a round that errors: an error makes the whole pass an error, which is a
        different report and would let the negative control pass for the wrong reason. What is under
        test is a batched pass in which no two batches were ever put in front of the model —
        precisely the state a batched architect without this half is permanently in.
        """
        if not self.skip_rounds:
            return super()._reconcile(merged, plan=plan, **kwargs)
        groups = [b.batch_id for b in plan.batches
                  if any(merged.batch_of.get(c) == b.batch_id for c in merged.claims)]
        return [], reconciliation.matrix_for(groups, [], {}), []

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1, inputs: int = 0,
               system_prompt: Optional[str] = None, estimated_prompt_tokens: int = 0,
               completion_tokens: Optional[int] = None) -> PassResult:
        is_round = system_prompt == reconciliation.SYSTEM_PROMPT
        self.calls += 1
        waits: List[CapacityWaitRecord] = []
        if is_round:
            index = len(self.round_prompts)
            self.round_prompts.append(user_prompt)
            payload = self.rounds[index] if index < len(self.rounds) else {}
            if self.stop_after_round is not None and index + 1 >= self.stop_after_round:
                waits = [CapacityWaitRecord(attempt=1, seconds=2400.0, source="budget_exhausted",
                                            detail="retry-after: 2400", taken=False)]
        else:
            index = len(self.local_prompts)
            self.local_prompts.append(user_prompt)
            payload = self.local[index] if index < len(self.local) else {"claims": [], "edges": []}
        receipt = PassReceipt(
            pass_id=ids.pass_id(inquiry_id, DissolutionPass.RELATION_ARCHITECT, attempt),
            pass_name=DissolutionPass.RELATION_ARCHITECT,
            outcome=PassOutcome.COMPLETED if payload is not None else PassOutcome.ERROR,
            call_count=1, finish_reasons=["stop"], inputs=inputs,
            transport_attempts=1 + len(waits), capacity_waits=waits, detail="scripted")
        return PassResult(payload, receipt)


def _two_batch_material():
    """Enough atoms for two batches, and a claim in each — one of them relational."""
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    assert len(plan.batches) >= 2, "the fixture must actually cross a boundary"
    return atoms, units, plan


def _one_claim_per_batch(plan):
    return [{"claims": [claim_row(f"c{i}", b.assignment.primary_refs[:2],
                                  text=f"a local claim from batch {i}")],
             "edges": []}
            for i, b in enumerate(plan.batches)]


def _many_groups():
    """Enough batches, each holding enough claim cards, that one round cannot hold them all.

    Both halves matter. Many batches gives many pairs; fat claim cards makes the ROUND capacity
    smaller than the group count, which is what forces the schedule to take several rounds — and a
    schedule of one round is not one a budget can stop halfway through.
    """
    atoms, units = corpus(6, 30)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    local = [{"claims": [claim_row(f"c{i}{j}", b.assignment.primary_refs[j:j + 1],
                                   text=f"claim {i}-{j} " + "carrying a good many more words " * 18)
                         for j in range(4)], "edges": []}
             for i, b in enumerate(plan.batches)]
    assert len(plan.batches) >= 4, "the schedule needs more than one round to be stoppable"
    return atoms, units, plan, local


def _claim_ids(plan, local):
    """The ids the parser will mint for each batch's single claim, in batch order."""
    return [ids.claim_id(INQUIRY, ClaimKind.ATTRIBUTE, answer["claims"][0]["text"])
            for answer in local]


# ── the relation that only exists across a boundary ──────────────────────────

def test_the_only_important_relation_crosses_a_batch_boundary():
    """Every local batch succeeds. The edge that matters connects two claims that were never in one
    request, so nothing local could draw it and only the reconciliation can."""
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    first, second = _claim_ids(plan, local)[:2]
    rounds = [{"edges": [edge_row(first, second, "complicates", "one qualifies the other")],
               "duplicates": [], "claims": []}]

    pas = _Council(local, rounds)
    claims, edges, _refusals, _notes, receipt = pas.assemble(atoms, units, inquiry_id=INQUIRY)

    assert pas.round_prompts, "no reconciliation round ran"
    crossing = [e for e in edges if {e.from_claim, e.to_claim} == {first, second}]
    assert len(crossing) == 1
    assert crossing[0].kind is ClaimEdgeKind.COMPLICATES
    # And the two ends really did come from different local batches.
    by_claim = {c.claim_id for c in claims}
    assert {first, second} <= by_claim
    assert receipt.batch_plan.pairs_examined == len(receipt.batch_plan.pairs)


def test_removing_the_reconciliation_loses_the_relation():
    """The negative control. Same material, rounds suppressed: the local batches still go green and
    the relation is simply not there — which is what a batched pass without this half reports as a
    successful relation search."""
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    first, second = _claim_ids(plan, local)[:2]

    claims, edges, _r, _n, receipt = _Council(local, [], skip_rounds=True).assemble(
        atoms, units, inquiry_id=INQUIRY)

    assert len(claims) >= 2, "the local batches did produce claims"
    assert not [e for e in edges if {e.from_claim, e.to_claim} == {first, second}]
    assert receipt.outcome is not PassOutcome.COMPLETED
    assert receipt.batch_plan.unexamined_pairs
    assert "never compared" in receipt.detail


def test_a_cross_batch_comparison_names_parents_from_more_than_one_batch():
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    first, second = _claim_ids(plan, local)[:2]
    rounds = [{"edges": [], "duplicates": [],
               "claims": [cross_claim("the two batches differ in the same respect",
                                      [first, second])]}]

    claims, _edges, _r, _n, receipt = _Council(local, rounds).assemble(atoms, units,
                                                                       inquiry_id=INQUIRY)
    added = [c for c in claims if c.claim_kind is ClaimKind.COMPARISON]
    assert len(added) == 1
    assert set(added[0].inferred_from) == {first, second}
    assert added[0].atom_refs == [], "a cross-batch inference is built from claims, not from atoms"
    assert added[0].image_scope is not ImageScope.ONE_IMAGE
    assert receipt.batch_plan.rounds[0].added_claims == 1


def test_a_claim_whose_parents_are_all_in_one_batch_is_refused():
    """Not a cross-batch inference: that batch had the material in front of it and did not build
    this claim, so admitting it here is the reconciliation making an ordinary claim with no atoms
    behind it."""
    atoms, units, plan = _two_batch_material()
    local = [{"claims": [claim_row("c0", plan.batches[0].assignment.primary_refs[:1],
                                   text="first claim of the first batch"),
                         claim_row("c1", plan.batches[0].assignment.primary_refs[1:2],
                                   text="second claim of the first batch")], "edges": []},
             # The second batch must produce a claim too, or there is only one group and no round
             # is scheduled at all — which would pass this test without exercising it.
             {"claims": [claim_row("c2", plan.batches[1].assignment.primary_refs[:1],
                                   text="a claim from the other batch")], "edges": []}]
    a = ids.claim_id(INQUIRY, ClaimKind.ATTRIBUTE, "first claim of the first batch")
    b = ids.claim_id(INQUIRY, ClaimKind.ATTRIBUTE, "second claim of the first batch")
    rounds = [{"edges": [], "duplicates": [],
               "claims": [cross_claim("something only this batch could see", [a, b])]}]

    claims, _edges, refusals, _n, _receipt = _Council(local, rounds).assemble(
        atoms, units, inquiry_id=INQUIRY)
    assert not [c for c in claims if c.claim_kind is ClaimKind.COMPARISON]
    assert any(r.kind.value == "reconciliation_added_local_content" for r in refusals)


def test_an_inference_with_unresolved_parents_is_refused():
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    rounds = [{"edges": [], "duplicates": [],
               "claims": [cross_claim("stands on nothing", ["clm_notaclaim01",
                                                            "clm_notaclaim02"])]}]
    claims, _edges, refusals, _n, _receipt = _Council(local, rounds).assemble(
        atoms, units, inquiry_id=INQUIRY)
    assert not [c for c in claims if c.claim_kind is ClaimKind.COMPARISON]
    assert any(r.kind.value == "inference_without_parent" for r in refusals)
    assert any(r.kind.value == "dangling_reference" for r in refusals)


def test_an_edge_naming_a_claim_that_is_not_in_the_graph_is_refused():
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    first = _claim_ids(plan, local)[0]
    rounds = [{"edges": [edge_row(first, "clm_nothinghere")], "duplicates": [], "claims": []}]
    _c, edges, refusals, _n, _receipt = _Council(local, rounds).assemble(atoms, units,
                                                                         inquiry_id=INQUIRY)
    assert not edges
    assert any(r.kind.value == "dangling_reference" for r in refusals)


# ── duplicates ───────────────────────────────────────────────────────────────

def test_a_duplicate_across_batches_is_merged_and_the_mapping_is_on_the_plan():
    """A merge is a deletion. The removed id's atoms go to the survivor — otherwise they become
    orphans the architect never used — and the mapping says which id went where."""
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    first, second = _claim_ids(plan, local)[:2]
    rounds = [{"edges": [], "claims": [],
               "duplicates": [{"claim": second, "duplicate_of": first,
                               "why": "the same claim in different words"}]}]

    claims, _edges, _r, notes, receipt = _Council(local, rounds).assemble(atoms, units,
                                                                          inquiry_id=INQUIRY)
    kept = {c.claim_id for c in claims}
    assert first in kept and second not in kept
    survivor = next(c for c in claims if c.claim_id == first)
    assert set(plan.batches[1].assignment.primary_refs[:2]) <= set(survivor.atom_refs)
    mapping = receipt.batch_plan.duplicate_map
    assert [(m.claim_id, m.canonical_id) for m in mapping] == [(second, first)]
    assert mapping[0].round_id
    assert any("merged into" in n for n in notes)


def test_two_claims_of_different_kinds_are_never_duplicates():
    """The merge that destroys the distinction this council exists to keep: a quality, the effect it
    produces and a comparison between two such effects are three claims with three warrants."""
    atoms, units, plan = _two_batch_material()
    local = [{"claims": [claim_row("c0", plan.batches[0].assignment.primary_refs[:1],
                                   text="how it looks", kind="attribute")], "edges": []},
             {"claims": [claim_row("c1", plan.batches[1].assignment.primary_refs[:1],
                                   text="what that does", kind="interpretation")], "edges": []}]
    a = ids.claim_id(INQUIRY, ClaimKind.ATTRIBUTE, "how it looks")
    b = ids.claim_id(INQUIRY, ClaimKind.INTERPRETATION, "what that does")
    rounds = [{"edges": [], "claims": [],
               "duplicates": [{"claim": b, "duplicate_of": a, "why": "same thing"}]}]

    claims, _edges, refusals, _n, receipt = _Council(local, rounds).assemble(
        atoms, units, inquiry_id=INQUIRY)
    assert {a, b} <= {c.claim_id for c in claims}
    assert receipt.batch_plan.duplicate_map == []
    assert any("different kinds" in r.why for r in refusals)


def test_a_ring_of_duplicate_mappings_keeps_every_claim():
    """No fact of the matter about which survives, so none of them is removed."""
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    first, second = _claim_ids(plan, local)[:2]
    rounds = [{"edges": [], "claims": [],
               "duplicates": [{"claim": first, "duplicate_of": second, "why": "a"},
                              {"claim": second, "duplicate_of": first, "why": "b"}]}]
    claims, _edges, _r, notes, receipt = _Council(local, rounds).assemble(atoms, units,
                                                                          inquiry_id=INQUIRY)
    assert {first, second} <= {c.claim_id for c in claims}
    assert receipt.batch_plan.duplicate_map == []
    assert any("cycle" in n for n in notes)


def test_a_claim_cannot_be_said_to_duplicate_itself():
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    first = _claim_ids(plan, local)[0]
    rounds = [{"edges": [], "claims": [],
               "duplicates": [{"claim": first, "duplicate_of": first, "why": "x"}]}]
    claims, _edges, refusals, _n, _receipt = _Council(local, rounds).assemble(
        atoms, units, inquiry_id=INQUIRY)
    assert first in {c.claim_id for c in claims}
    assert any(r.kind.value == "duplicate_points_at_itself" for r in refusals)


# ── the coverage matrix ──────────────────────────────────────────────────────

def test_every_pair_of_batches_appears_in_the_matrix():
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    _c, _e, _r, _n, receipt = _Council(local, [{"edges": [], "duplicates": [], "claims": []}]
                                       * 20).assemble(atoms, units, inquiry_id=INQUIRY)
    record = receipt.batch_plan
    groups = {b.batch_id for b in record.batches}
    expected = len(groups) * (len(groups) - 1) // 2
    assert len(record.pairs) == expected
    assert record.pairs_examined == expected
    assert all(p.round_id for p in record.pairs)


def test_a_pair_nothing_compared_prevents_completed_and_is_named():
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    _c, _e, _r, _n, receipt = _Council(local, [], skip_rounds=True).assemble(
        atoms, units, inquiry_id=INQUIRY)
    record = receipt.batch_plan
    assert receipt.outcome is PassOutcome.THIN
    assert record.unexamined_pairs
    assert all(p.reason for p in record.unexamined_pairs)
    for pair in record.unexamined_pairs[:3]:
        assert f"{pair.left_batch_id}/{pair.right_batch_id}" in receipt.detail \
            or len(record.unexamined_pairs) > 3


def test_a_budget_that_stops_the_waiting_names_the_pairs_it_never_reached():
    """The decision's honest ending, one pass along. `the budget ran out` and `nothing was found
    between these two` are opposite reports and may not render alike."""
    atoms, units, plan, local = _many_groups()
    pas = _Council(local, [{"edges": [], "duplicates": [], "claims": []}] * 40,
                   stop_after_round=1)
    _c, _e, _r, notes, receipt = pas.assemble(atoms, units, inquiry_id=INQUIRY)

    record = receipt.batch_plan
    assert len(pas.round_prompts) == 1, "the schedule kept going after the budget stopped it"
    assert record.unexamined_pairs
    assert all(p.reason == reconciliation.NOT_REACHED for p in record.unexamined_pairs)
    assert any("declared budget" in n for n in notes)
    assert receipt.outcome is PassOutcome.THIN


def test_one_batch_needs_no_reconciliation_and_says_why():
    """An empty matrix because there is nothing across is not an empty matrix because nothing was
    compared, and a reader has to be able to tell them apart."""
    atoms, units = corpus(2, 2)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    assert len(plan.batches) == 1
    local = [{"claims": [claim_row("c0", [atoms[0].atom_id], text="only claim"),
                         claim_row("c1", [atoms[1].atom_id], text="another claim",
                                   kind="comparison")],
              "edges": [edge_row("c0", "c1")]}]
    pas = _Council(local, [])
    _c, edges, _r, notes, receipt = pas.assemble(atoms, units, inquiry_id=INQUIRY)
    assert pas.round_prompts == []
    assert receipt.batch_plan.pairs == []
    assert edges
    assert any("nothing across" in n for n in notes)
    assert any("1 of 1 batch(es) produced a claim" in n for n in notes)
    assert receipt.outcome is PassOutcome.COMPLETED


def test_batches_that_returned_nothing_are_named_rather_than_counted_as_one_batch():
    """The live control planned THREE batches, two were refused for capacity, and the note said
    "one batch" three lines under a plan saying three — which reads as the plan contradicting
    itself rather than as two requests having failed."""
    atoms, units, plan = _two_batch_material()
    # Only the first batch answers; the rest come back with nothing.
    local = [{"claims": [claim_row("c0", plan.batches[0].assignment.primary_refs[:1],
                                   text="the only claim anybody built")], "edges": []}]
    _c, _e, _r, notes, receipt = _Council(local, []).assemble(atoms, units, inquiry_id=INQUIRY)

    total = len(plan.batches)
    assert receipt.batch_plan.pairs == []
    assert any(f"1 of {total} batch(es) produced a claim" in n for n in notes), notes
    assert any(f"the other {total - 1} returned none" in n for n in notes), notes


# ── what a card carries ──────────────────────────────────────────────────────

def test_a_claim_card_carries_its_identity_and_not_its_prose():
    """A card that repeated its source paragraph would put this pass back over the allowance the
    batching exists to fit under."""
    atoms, units, plan = _two_batch_material()
    local = _one_claim_per_batch(plan)
    pas = _Council(local, [{"edges": [], "duplicates": [], "claims": []}] * 20)
    pas.assemble(atoms, units, inquiry_id=INQUIRY)
    prompt = pas.round_prompts[0]
    for unit_obj in units:
        assert unit_obj.exact_quote not in prompt
    assert "claim_id" in prompt and "group" in prompt


def test_no_reconciliation_request_exceeds_the_allowance():
    atoms, units = corpus(6, 20)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    local = [{"claims": [claim_row(f"c{i}{j}", b.assignment.primary_refs[j:j + 1],
                                   text=f"claim {i}-{j} " + "with some words " * 6)
                         for j in range(4)], "edges": []}
             for i, b in enumerate(plan.batches)]
    pas = _Council(local, [{"edges": [], "duplicates": [], "claims": []}] * 200)
    pas.assemble(atoms, units, inquiry_id=INQUIRY)
    usable = sizing.Allowance().usable_tokens
    for prompt in pas.round_prompts:
        estimate = sizing.estimate_request_tokens(
            reconciliation.SYSTEM_PROMPT, prompt,
            completion_tokens=architect.RECONCILE_COMPLETION.maximum_tokens)
        assert estimate <= usable + architect.RECONCILE_COMPLETION.maximum_tokens, prompt[:200]


# ── the pacing this lane may not have changed ───────────────────────────────

class _Refusing:
    """A provider client that refuses for capacity, then answers. Records the exact bytes sent."""

    def __init__(self, status_codes, answer):
        self.status_codes = list(status_codes)
        self.answer = answer
        self.sent = []

        class _Completions:
            def create(inner, **request):                          # noqa: N805
                self.sent.append(json.dumps(request, sort_keys=True))
                if self.status_codes:
                    raise _ProviderRefusal(self.status_codes.pop(0))
                return self.answer

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class _ProviderRefusal(Exception):
    def __init__(self, status_code):
        super().__init__(f"Error code: {status_code}")
        self.status_code = status_code
        self.headers = {"retry-after": "0.01"}


def _completion(payload):
    class _Message:
        content = json.dumps(payload)

    class _Choice:
        message = _Message()
        finish_reason = "stop"

    class _Completion:
        choices = [_Choice()]
        usage = None

    return _Completion()


def _paced(client):
    from backend.services.semantic_compilation import pacing
    pacer = pacing.ProviderPacer(interval_seconds=0.001, max_attempts=4, budget_seconds=60,
                                 sleep=lambda _s: None, monotonic=_Clock())
    pacer.open_budget(60)
    pas = architect.RelationArchitect(client=client, pacer=pacer)
    return pas


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += 0.001
        return self.t


def test_a_capacity_refusal_re_sends_the_identical_bytes_through_the_batched_pass():
    """003D's rule, unchanged by the batching: a 429 is congestion and the SAME request goes
    again. Identical is a property of the signature — the request dict is built once, above the
    pacer — and this asserts it end to end through a batched architect."""
    atoms, units = corpus(2, 2)
    client = _Refusing([429], _completion({"claims": [], "edges": []}))
    pas = _paced(client)
    _c, _e, _r, _n, receipt = pas.assemble(atoms, units, inquiry_id=INQUIRY)

    assert len(client.sent) == 2
    assert client.sent[0] == client.sent[1], "the retry did not re-send identical bytes"
    assert receipt.call_count == 1, "a transport retry was counted as a second semantic attempt"
    assert receipt.transport_attempts == 2
    assert receipt.waited


def test_a_request_the_provider_calls_too_large_is_never_re_sent():
    """A 413 says the request itself cannot go. Re-sending it unchanged would fail identically
    forever and spend the gate's budget proving what the first response already said."""
    atoms, units = corpus(2, 2)
    client = _Refusing([413], _completion({"claims": [], "edges": []}))
    pas = _paced(client)
    _c, _e, refusals, _n, receipt = pas.assemble(atoms, units, inquiry_id=INQUIRY)

    assert len(client.sent) == 1
    assert receipt.outcome is PassOutcome.ERROR
    assert receipt.transport_attempts == 1
    assert receipt.capacity_waits == []
    assert any("413" in r.why for r in refusals)
