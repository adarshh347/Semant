"""
HARNESS-003E §2 — the relation architect, batched locally, with every atom primary exactly once.

WHAT THIS FILE DOES NOT TEST. That relations crossing a batch boundary are found — nothing here can,
because local batching is precisely the arrangement in which they are invisible. That is §3's
reconciliation and `test_semantic_compilation_reconciliation.py`, and the separation is deliberate:
if these tests passed and those did not, the pass would be sending green requests and reporting a
relation search it never performed.

The atoms are synthetic and say nothing about anything. `test_semantic_compilation_generality.py`
forbids a production module from naming a fixture's subject, and a test that leaned on a subject
would be proving the batching over the one shape somebody had in mind.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pytest

from backend.schemas.semantic_compilation import (AtomKind, ClaimEdgeKind, ImageScope,
                                                  ItemDispositionKind, PassOutcome, SemanticAtom,
                                                  SourceUnit, SourceUnitKind)
from backend.services.semantic_compilation import architect, ids, sizing
from backend.services.semantic_compilation.passes import PassResult

INQUIRY = "inq_batch0001"


def unit(n: int, *, words: str = "") -> SourceUnit:
    text = words or f"source unit number {n} carries some words of its own"
    return SourceUnit(source_unit_id=ids.source_unit_id(INQUIRY, SourceUnitKind.READING_BLOCK,
                                                        f"rb_{n}", text),
                      kind=SourceUnitKind.READING_BLOCK, source_ref=f"rb_{n}", exact_quote=text,
                      ordinal=n)


def atom(n: int, *, unit_id: str, kind: AtomKind = AtomKind.VISUAL_QUALITY,
         text: str = "", pad: int = 0) -> SemanticAtom:
    body = text or f"atom number {n} states one thing" + (" and more words" * pad)
    return SemanticAtom(atom_id=ids.atom_id(INQUIRY, kind, body, [unit_id]), text=body,
                        unit_kind=kind, source_unit_ids=[unit_id], quotes=[],
                        subject=f"subject {n}", predicate="is", object=f"object {n}",
                        image_scope=ImageScope.CORPUS)


def corpus(atoms_per_unit: int, units_count: int, *, pad: int = 0):
    units = [unit(u) for u in range(units_count)]
    atoms = [atom(u * 100 + a, unit_id=units[u].source_unit_id, pad=pad)
             for u in range(units_count) for a in range(atoms_per_unit)]
    return atoms, units


def claim_row(ref: str, atom_ids: Sequence[str], *, text: str = "", kind: str = "attribute"):
    return {"ref": ref, "text": text or f"claim {ref} over {len(atom_ids)} atom(s)", "kind": kind,
            "atom_ids": list(atom_ids), "subject": "s", "predicate": "p", "object": "o",
            "image_scope": "corpus", "demand": "interpretive", "status": "interpretive",
            "inferred_from": [], "note": ""}


class _Scripted(architect.RelationArchitect):
    """The architect with a scripted answer per request, and a record of what each request held.

    Not `FrozenRelationArchitect`: these tests need to see the ATOMS each request carried, which is
    the thing a batch boundary decides and the thing nothing else can observe from outside.
    """

    def __init__(self, answers: Sequence[Any], *, truncate: Sequence[int] = (),
                 fail: Sequence[int] = ()):
        super().__init__(client=None)
        self.answers = list(answers)
        self.truncate = set(truncate)
        self.fail = set(fail)
        self.prompts: List[str] = []
        self.completion_budgets: List[int] = []
        self.estimates: List[int] = []

    def is_available(self) -> bool:
        return True

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1, inputs: int = 0,
               system_prompt: Optional[str] = None, estimated_prompt_tokens: int = 0,
               completion_tokens: Optional[int] = None) -> PassResult:
        from backend.schemas.semantic_compilation import DissolutionPass, PassReceipt
        index = len(self.prompts)
        self.prompts.append(user_prompt)
        self.completion_budgets.append(completion_tokens or 0)
        self.estimates.append(estimated_prompt_tokens)
        self.calls += 1
        payload = self.answers[index] if index < len(self.answers) else {"claims": [], "edges": []}
        outcome = (PassOutcome.TRUNCATED if index in self.truncate
                   else PassOutcome.ERROR if index in self.fail else PassOutcome.COMPLETED)
        receipt = PassReceipt(
            pass_id=ids.pass_id(inquiry_id, DissolutionPass.RELATION_ARCHITECT, attempt),
            pass_name=DissolutionPass.RELATION_ARCHITECT, outcome=outcome, call_count=1,
            finish_reasons=["length"] if index in self.truncate else ["stop"],
            inputs=inputs, detail="scripted")
        return PassResult(None if index in self.fail else payload, receipt)


# ── the partition ────────────────────────────────────────────────────────────

def test_a_dissection_too_large_for_one_request_becomes_several():
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    assert len(plan.batches) > 1, "72 atoms planned as one request is the 413 all over again"
    assert plan.record.every_item_is_primary_once
    assert plan.record.total_items == len(atoms)


def test_no_planned_architect_request_exceeds_the_allowance():
    atoms, _ = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    for batch in plan.batches:
        assert batch.assignment.estimated_total_tokens <= sizing.Allowance().usable_tokens
        assert batch.assignment.requested_completion_tokens <= architect.DEFAULT_BUDGET \
            .max_completion_tokens


def test_atoms_from_one_source_unit_are_kept_together_where_they_fit():
    """The seam goes where a relation is least likely to cross. Atoms dissolved out of one block
    are the ones most likely to relate to each other."""
    atoms, units = corpus(4, 10)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    by_atom = {a.atom_id: a.source_unit_ids[0] for a in atoms}
    split = 0
    for source in {u.source_unit_id for u in units}:
        holders = {b.batch_id for b in plan.batches
                   if any(by_atom[r] == source for r in b.assignment.primary_refs)}
        if len(holders) > 1:
            split += 1
    assert split == 0, f"{split} source unit(s) were split across batches when they need not be"


def test_each_request_carries_only_its_own_atoms():
    """A batch's prompt shows the model its own atoms and nothing else, so a claim naming an atom
    from another batch is an id the model invented and is refused as one."""
    atoms, units = corpus(6, 12)
    pas = _Scripted([])
    pas.assemble(atoms, units, inquiry_id=INQUIRY)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    assert len(pas.prompts) == len(plan.batches)
    for prompt, batch in zip(pas.prompts, plan.batches):
        mine = set(batch.assignment.primary_refs)
        for atom_id in (a.atom_id for a in atoms):
            assert (atom_id in prompt) is (atom_id in mine)


def test_the_completion_reservation_follows_the_batch():
    atoms, units = corpus(6, 12)
    pas = _Scripted([])
    pas.assemble(atoms, units, inquiry_id=INQUIRY)
    assert pas.completion_budgets
    assert all(0 < b <= architect.DEFAULT_BUDGET.max_completion_tokens
               for b in pas.completion_budgets)
    assert all(e > 0 for e in pas.estimates), "the sizing estimate never reached the call"


# ── merging ──────────────────────────────────────────────────────────────────

def test_a_claim_two_batches_both_built_is_one_claim_carrying_both_sets_of_atoms():
    """A duplicate is one object seen twice, not two claims kept — and dropping the second sighting
    without taking its atoms would report those atoms as orphans nothing used."""
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    first, second = plan.batches[0], plan.batches[1]
    shared = "one sentence two batches both arrived at"
    answers = [{"claims": [claim_row("c1", first.assignment.primary_refs[:2], text=shared)],
                "edges": []},
               {"claims": [claim_row("c1", second.assignment.primary_refs[:2], text=shared)],
                "edges": []}]
    claims, _edges, _r, notes, receipt = _Scripted(answers).assemble(
        atoms, units, inquiry_id=INQUIRY)

    same = [c for c in claims if c.text == shared]
    assert len(same) == 1
    assert set(same[0].atom_refs) == set(first.assignment.primary_refs[:2]
                                         + second.assignment.primary_refs[:2])
    assert any("merged into one" in n for n in notes)
    assert receipt.batch_plan is not None


def test_a_claim_naming_an_atom_from_another_batch_is_refused_by_name():
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    stranger = plan.batches[1].assignment.primary_refs[0]
    answers = [{"claims": [claim_row("c1", [stranger])], "edges": []}]
    _claims, _edges, refusals, _n, _receipt = _Scripted(answers).assemble(
        atoms, units, inquiry_id=INQUIRY)
    assert any(r.what == stranger and r.kind.value == "dangling_reference" for r in refusals)


def test_two_batches_naming_the_same_edge_produce_one_edge():
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    rows = [claim_row("c1", plan.batches[0].assignment.primary_refs[:1], text="first claim"),
            claim_row("c2", plan.batches[0].assignment.primary_refs[1:2], text="second claim")]
    edge = {"kind": ClaimEdgeKind.SUPPORTS.value, "from": "c1", "to": "c2", "why": "because"}
    answers = [{"claims": rows, "edges": [edge]}, {"claims": rows, "edges": [edge]}]
    _claims, edges, _r, _n, _receipt = _Scripted(answers).assemble(atoms, units,
                                                                   inquiry_id=INQUIRY)
    assert len(edges) == 1


# ── the dispositions the plan carries ────────────────────────────────────────

def test_every_atom_gets_a_disposition_on_the_plan():
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    answers = [{"claims": [claim_row(f"c{i}", b.assignment.primary_refs[:1])], "edges": []}
               for i, b in enumerate(plan.batches)]
    _claims, _edges, _r, _n, receipt = _Scripted(answers).assemble(atoms, units,
                                                                   inquiry_id=INQUIRY)
    record = receipt.batch_plan
    assert {d.ref for d in record.dispositions} == {a.atom_id for a in atoms}
    kinds = {d.disposition for d in record.dispositions}
    assert ItemDispositionKind.USED in kinds
    assert ItemDispositionKind.ORPHAN in kinds
    assert all(d.batch_id for d in record.dispositions)


def test_an_orphan_is_reported_rather_than_left_to_be_noticed():
    atoms, units = corpus(3, 4)
    answers = [{"claims": [claim_row("c1", [atoms[0].atom_id])], "edges": []}]
    _claims, _edges, _r, notes, receipt = _Scripted(answers).assemble(atoms, units,
                                                                      inquiry_id=INQUIRY)
    orphans = [d for d in receipt.batch_plan.dispositions
               if d.disposition is ItemDispositionKind.ORPHAN]
    assert len(orphans) == len(atoms) - 1
    assert any("not built into any claim" in n for n in notes)


# ── honesty about what went wrong ────────────────────────────────────────────

def test_one_truncated_batch_makes_the_whole_pass_truncated():
    """Averaging would round it away. What a truncated batch produced is a PREFIX, and a pass
    holding one prefix has not completed."""
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    answers = [{"claims": [claim_row(f"c{i}", b.assignment.primary_refs[:1])], "edges": []}
               for i, b in enumerate(plan.batches)]
    _c, _e, _r, _n, receipt = _Scripted(answers, truncate=[1]).assemble(atoms, units,
                                                                        inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.TRUNCATED
    assert receipt.truncated
    assert "1 of" in receipt.detail


def test_one_failed_batch_makes_the_whole_pass_an_error():
    atoms, units = corpus(6, 12)
    plan = architect.RelationArchitect().plan_batches(atoms, inquiry_id=INQUIRY)
    answers = [{"claims": [claim_row(f"c{i}", b.assignment.primary_refs[:1])], "edges": []}
               for i, b in enumerate(plan.batches)]
    _c, _e, _r, _n, receipt = _Scripted(answers, fail=[0]).assemble(atoms, units,
                                                                    inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.ERROR


def test_an_atom_too_large_for_any_request_is_refused_before_transport():
    """The 413, caught by arithmetic. The pass does not `complete` over an atom nothing looked at,
    and no request was spent discovering that."""
    units = [unit(0)]
    small = atom(1, unit_id=units[0].source_unit_id)
    huge = atom(2, unit_id=units[0].source_unit_id, text="w " * 40_000)
    pas = _Scripted([{"claims": [claim_row("c1", [small.atom_id])], "edges": []}])
    _c, _e, refusals, _n, receipt = pas.assemble([small, huge], units, inquiry_id=INQUIRY)

    assert receipt.outcome is PassOutcome.COVERAGE_FAILED
    assert any(r.what == huge.atom_id for r in refusals)
    assert [d.disposition for d in receipt.batch_plan.dispositions
            if d.ref == huge.atom_id] == [ItemDispositionKind.REFUSED]
    assert len(pas.prompts) == 1, "the oversized atom cost the allowance a request"


def test_no_atom_means_no_request_and_says_so():
    _c, _e, _r, notes, receipt = _Scripted([]).assemble([], [], inquiry_id=INQUIRY)
    assert receipt.outcome is PassOutcome.EMPTY
    assert notes == ["the architect was given no atom, so it built nothing"]


# ── narration ────────────────────────────────────────────────────────────────

def test_each_batch_narrates_itself_as_it_happens():
    """003D's whole visibility argument, one pass along: a stage reported only at the end is a stage
    that sat silent and then finished, which is indistinguishable from one that hung."""
    atoms, units = corpus(6, 12)
    seen: List[Dict[str, Any]] = []
    pas = _Scripted([])
    pas.observer = lambda label, **fields: seen.append({"label": label, **fields})
    pas.assemble(atoms, units, inquiry_id=INQUIRY)

    started = [s for s in seen if s.get("outcome") == "started"]
    assert len(started) > 1
    assert all(s["label"].startswith("relating batch ") for s in seen)
    assert all(s["refs"] for s in started)
    assert {s["total"] for s in seen} == {started[0]["total"]}
