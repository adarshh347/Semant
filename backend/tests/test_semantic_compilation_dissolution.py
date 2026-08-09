"""
HARNESS-003A §7 — the audit, the one repair, and the pipeline that runs the council in order.

The audit is the check ON the council, so the tests that matter are the ones proving it is not
performed BY it: it makes no call, it compares sets, and it decides the compilation's one quality
state by ordering explanations so the FIRST cause is reported rather than the last symptom.
"""
from __future__ import annotations

import ast
import copy
import pathlib

import pytest

from backend.schemas.semantic_compilation import (SCHEMA_VERSION_V2, DispositionKind,
                                                  DissolutionPass, ModelReceipt, PassOutcome,
                                                  PassReceipt, ReadingBlock, ReadingBlockKind,
                                                  SceneReading, SemanticInquiryGraph, canonical)
from backend.services.semantic_compilation import audit as AU
from backend.services.semantic_compilation import dissolution as P
from backend.services.semantic_compilation import ids, ledger
from backend.services.semantic_compilation.architect import FrozenRelationArchitect
from backend.services.semantic_compilation.base import CompilationRequest
from backend.services.semantic_compilation.dissector import (FrozenSemanticDissector,
                                                             SemanticDissector)
from backend.services.semantic_compilation.operationalizer import FrozenEpistemicOperationalizer

INQUIRY = "inq_000000000001"
PROMPT = "the first thing has one quality and that makes it read a certain way. the second differs"
AT = "2026-08-10T00:00:00+00:00"


def a_reading(*texts):
    return SceneReading(
        text="the theorist's summary",
        blocks=[ReadingBlock(block_id=f"rb_{i}", kind=ReadingBlockKind.PART, text=t,
                             image_refs=["img_1"]) for i, t in enumerate(texts)],
        provenance=ModelReceipt(role="scene_theorist"))


def a_request(reading=None):
    return CompilationRequest(prompt=PROMPT, inquiry_id=INQUIRY, reading=reading, now=AT)


def a_ledger(reading=None):
    units, _ = ledger.build(PROMPT, reading, inquiry_id=INQUIRY)
    return units


def dissection_payload(units, kinds=("visual_quality", "comparison", "entity")):
    return {"atoms": [{"ref": f"a{i}", "text": f"atom {i}", "unit_kind": kinds[i % len(kinds)],
                       "source_unit_ids": [u.source_unit_id]} for i, u in enumerate(units)],
            "coverage": [{"source_unit_id": u.source_unit_id, "disposition": "represented_by",
                          "refs": [f"a{i}"]} for i, u in enumerate(units)]}


def run(dissection=None, *, reading=None, architect=None, operationalizer=None, repairer=None):
    units = a_ledger(reading)
    payloads = dissection if dissection is not None else [dissection_payload(units)]
    council = P.Council(
        dissector=FrozenSemanticDissector(payloads),
        architect=FrozenRelationArchitect(architect if architect is not None else {"claims": []}),
        operationalizer=FrozenEpistemicOperationalizer(
            operationalizer if operationalizer is not None else {"observables": []}),
        repairer=repairer)
    return units, P.dissolve(a_request(reading), council)


# ── the audit is a comparison, not a mind ────────────────────────────────────

def test_the_audit_module_reaches_no_model():
    """A check the council performed on itself is not a check."""
    source = pathlib.Path(AU.__file__).read_text(encoding="utf-8")
    for token in ("groq", "llm_service", "openai", "invoke", "ModelPass"):
        assert token not in source, f"the audit reaches {token!r}"


def test_a_whole_ledger_audits_clean():
    units = a_ledger()
    atoms_payload = dissection_payload(units)
    atoms, coverage, _, _ = FrozenSemanticDissector([atoms_payload]).dissolve(
        units, prompt=PROMPT, inquiry_id=INQUIRY)
    report = AU.audit(units, atoms, coverage, [], inquiry_id=INQUIRY)
    assert report.clean and not report.coverage_failed
    assert report.repairable == ()


def test_an_uncovered_unit_is_named_and_is_repairable():
    units = a_ledger()
    payload = {"atoms": [{"ref": "a0", "text": "x", "unit_kind": "entity",
                          "source_unit_ids": [units[0].source_unit_id]}],
               "coverage": [{"source_unit_id": units[0].source_unit_id,
                             "disposition": "represented_by", "refs": ["a0"]}]}
    atoms, coverage, _, _ = FrozenSemanticDissector([payload]).dissolve(
        units, prompt=PROMPT, inquiry_id=INQUIRY)
    report = AU.audit(units, atoms, coverage, [], inquiry_id=INQUIRY)
    assert report.uncovered == (units[1].source_unit_id,)
    assert report.repairable == (units[1].source_unit_id,)
    assert report.coverage_failed
    assert any(r.kind.value == "source_unit_uncovered" for r in report.refusals)


def test_nothing_is_repairable_when_the_dissector_never_ran():
    """Asking again would be the retry this lane refuses to perform."""
    units = a_ledger()
    report = AU.audit(units, [], [], [], inquiry_id=INQUIRY, dissector_ran=False)
    assert report.uncovered and report.repairable == ()


def test_the_repair_brief_carries_only_what_failed():
    units = a_ledger()
    report = AU.audit(units, [], [], [], inquiry_id=INQUIRY)
    brief = AU.repair_brief(report, units)
    assert len(brief["source_units"]) == len(units)
    assert brief["why"]
    assert "reading" not in brief and "prompt" not in brief, \
        "a repair that resent the original request would be a second attempt at the failed call"


# ── the ordering of explanations ─────────────────────────────────────────────

def a_pass(name, outcome, **kw):
    return PassReceipt(pass_id=ids.pass_id(INQUIRY, name), pass_name=name, outcome=outcome, **kw)


def test_a_truncation_is_reported_ahead_of_the_coverage_failure_it_caused():
    """Reporting the downstream symptom would send somebody to fix the wrong thing."""
    units = a_ledger()
    report = AU.audit(units, [], [], [], inquiry_id=INQUIRY)
    outcome, detail = AU.overall(
        [a_pass(DissolutionPass.SEMANTIC_DISSECTOR, PassOutcome.TRUNCATED,
                finish_reasons=["length"], model="m")], report)
    assert outcome is PassOutcome.TRUNCATED
    assert "saw a prefix" in detail


def test_a_coverage_failure_is_reported_ahead_of_thinness():
    units = a_ledger()
    report = AU.audit(units, [], [], [], inquiry_id=INQUIRY)
    outcome, _ = AU.overall(
        [a_pass(DissolutionPass.SEMANTIC_DISSECTOR, PassOutcome.COMPLETED, model="m"),
         a_pass(DissolutionPass.RELATION_ARCHITECT, PassOutcome.THIN, model="m")], report)
    assert outcome is PassOutcome.COVERAGE_FAILED


def test_thinness_survives_a_clean_ledger():
    units = a_ledger()
    atoms, coverage, _, _ = FrozenSemanticDissector([dissection_payload(units)]).dissolve(
        units, prompt=PROMPT, inquiry_id=INQUIRY)
    report = AU.audit(units, atoms, coverage, [], inquiry_id=INQUIRY)
    outcome, detail = AU.overall(
        [a_pass(DissolutionPass.SEMANTIC_DISSECTOR, PassOutcome.COMPLETED, model="m"),
         a_pass(DissolutionPass.RELATION_ARCHITECT, PassOutcome.THIN, model="m",
                detail="drew no edge")], report)
    assert outcome is PassOutcome.THIN
    assert "drew no edge" in detail


def test_an_unavailable_pass_explains_everything_after_it():
    units = a_ledger()
    report = AU.audit(units, [], [], [], inquiry_id=INQUIRY, dissector_ran=False)
    outcome, detail = AU.overall(
        [a_pass(DissolutionPass.SEMANTIC_DISSECTOR, PassOutcome.UNAVAILABLE, model="m")], report)
    assert outcome is PassOutcome.UNAVAILABLE
    assert "semantic_dissector" in detail


# ── the one repair ───────────────────────────────────────────────────────────

def test_a_repair_runs_once_over_the_uncovered_units_and_both_attempts_are_recorded():
    units = a_ledger()
    partial = {"atoms": [{"ref": "a0", "text": "x", "unit_kind": "entity",
                          "source_unit_ids": [units[0].source_unit_id]}],
               "coverage": [{"source_unit_id": units[0].source_unit_id,
                             "disposition": "represented_by", "refs": ["a0"]}]}
    fixed = {"atoms": [{"ref": "b0", "text": "y", "unit_kind": "comparison",
                        "source_unit_ids": [units[1].source_unit_id]}],
             "coverage": [{"source_unit_id": units[1].source_unit_id,
                           "disposition": "represented_by", "refs": ["b0"]}]}
    _, graph = run([partial], repairer=FrozenSemanticDissector([fixed]))

    dissections = [p for p in graph.passes
                   if p.pass_name is DissolutionPass.SEMANTIC_DISSECTOR]
    assert len(dissections) == 2, "both attempts keep their own receipt"
    assert dissections[0].pass_id != dissections[1].pass_id
    assert len(graph.coverage) == len(units)
    assert any("one targeted repair was run over 1 uncovered source unit" in n
               for n in graph.notes)
    assert any("would be a second attempt at the failed call" in n for n in graph.notes)


def test_a_repair_cannot_overwrite_the_part_that_already_worked():
    units = a_ledger()
    partial = {"atoms": [{"ref": "a0", "text": "the original atom", "unit_kind": "entity",
                          "source_unit_ids": [units[0].source_unit_id]}],
               "coverage": [{"source_unit_id": units[0].source_unit_id,
                             "disposition": "represented_by", "refs": ["a0"]}]}
    # The repair tries to re-dispose of a unit that already had one.
    greedy = {"atoms": [{"ref": "b0", "text": "y", "unit_kind": "comparison",
                         "source_unit_ids": [units[1].source_unit_id]}],
              "coverage": [{"source_unit_id": units[1].source_unit_id,
                            "disposition": "represented_by", "refs": ["b0"]},
                           {"source_unit_id": units[0].source_unit_id,
                            "disposition": "refused", "reason": "changed my mind"}]}
    _, graph = run([partial], repairer=FrozenSemanticDissector([greedy]))
    first = next(c for c in graph.coverage if c.source_unit_id == units[0].source_unit_id)
    assert first.disposition is DispositionKind.REPRESENTED_BY
    assert any("the original atom" == a.text for a in graph.semantic_atoms)


def test_there_is_no_second_repair():
    """One targeted repair, and the pipeline has no loop that could ask for another."""
    tree = ast.parse(pathlib.Path(P.__file__).read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.While)]
    source = pathlib.Path(P.__file__).read_text(encoding="utf-8")
    assert source.count("_repair(") == 2, "declared once and called once"


def test_without_a_repair_adapter_the_gap_is_reported_and_nothing_is_retried():
    units = a_ledger()
    partial = {"atoms": [{"ref": "a0", "text": "x", "unit_kind": "entity",
                          "source_unit_ids": [units[0].source_unit_id]}],
               "coverage": [{"source_unit_id": units[0].source_unit_id,
                             "disposition": "represented_by", "refs": ["a0"]}]}
    _, graph = run([partial])
    assert any("no repair adapter is bound. Nothing was retried" in n for n in graph.notes)
    assert len([p for p in graph.passes
                if p.pass_name is DissolutionPass.SEMANTIC_DISSECTOR]) == 1


# ── the pipeline ─────────────────────────────────────────────────────────────

def test_the_pipeline_writes_v2_and_carries_the_whole_ledger():
    units, graph = run(reading=a_reading("a part is present"))
    assert graph.schema_version == SCHEMA_VERSION_V2
    assert graph.provenance.contract_version == SCHEMA_VERSION_V2
    assert graph.is_dissolved
    assert len(graph.source_units) == len(units)
    assert {c.source_unit_id for c in graph.coverage} == {u.source_unit_id for u in units}


def test_the_prompt_survives_the_whole_pipeline_byte_for_byte():
    _, graph = run()
    assert graph.prompt == PROMPT
    for unit in graph.source_units:
        if unit.span:
            assert PROMPT[unit.span[0]:unit.span[1]] == unit.exact_quote


def test_every_pass_leaves_a_receipt_even_the_deterministic_ones():
    _, graph = run(reading=a_reading("a part is present"))
    names = [p.pass_name for p in graph.passes]
    assert DissolutionPass.SOURCE_LEDGER in names
    assert DissolutionPass.SEMANTIC_DISSECTOR in names
    assert DissolutionPass.RELATION_ARCHITECT in names
    assert DissolutionPass.EPISTEMIC_OPERATIONALIZER in names
    assert DissolutionPass.COVERAGE_AUDIT in names


def test_no_single_compiler_receipt_is_claimed_for_three_minds():
    """Putting one pass's receipt in `provenance.compiler` would name one of three minds as the
    author of all of it. The passes list is the receipt."""
    _, graph = run()
    assert graph.provenance.compiler is None
    assert graph.provenance.compiler_kind == "council"


def test_a_missing_mind_is_unavailable_and_the_ones_after_it_report_what_they_were_given():
    """A dissector that did not run leaves the architect AVAILABLE with nothing to work with, and
    collapsing those two would hide which mind was missing."""
    council = P.Council(dissector=None, architect=FrozenRelationArchitect({"claims": []}),
                        operationalizer=FrozenEpistemicOperationalizer({"observables": []}))
    graph = P.dissolve(a_request(), council)
    dissector = next(p for p in graph.passes
                     if p.pass_name is DissolutionPass.SEMANTIC_DISSECTOR)
    architect = next(p for p in graph.passes
                     if p.pass_name is DissolutionPass.RELATION_ARCHITECT)
    assert dissector.outcome is PassOutcome.UNAVAILABLE
    assert architect.outcome is PassOutcome.EMPTY
    assert graph.notes[-1].startswith("dissolution: unavailable")


def test_a_claim_standing_on_a_removed_atom_is_dropped_with_what_depended_on_it():
    """The graph validator refuses one outright, and raising there would lose the whole run over
    one bad reference."""
    units = a_ledger()
    payload = dissection_payload(units)
    architect = {"claims": [{"ref": "c1", "text": "built on a ghost", "kind": "entity",
                             "atom_ids": ["atm_nothing"]}]}
    _, graph = run([payload], architect=architect)
    assert graph.claims == []
    assert isinstance(graph, SemanticInquiryGraph)


def test_the_coverage_table_says_what_became_of_every_unit():
    _, graph = run(reading=a_reading("a part is present"))
    rows = P.coverage_table(graph)
    assert len(rows) == len(graph.source_units)
    assert {r["author"] for r in rows} == {"user", "scene_theorist"}
    for row in rows:
        assert row["disposition"] != "(none)"
        assert row["quote"]


def test_the_whole_pipeline_replays_byte_for_byte():
    """Two runs of the same frozen payloads are one graph. Nothing in the pipeline reads a clock
    it was not handed."""
    units = a_ledger()
    payload = dissection_payload(units)
    first = P.dissolve(a_request(), P.Council(
        dissector=FrozenSemanticDissector([copy.deepcopy(payload)]),
        architect=FrozenRelationArchitect({"claims": []}),
        operationalizer=FrozenEpistemicOperationalizer({"observables": []})))
    second = P.dissolve(a_request(), P.Council(
        dissector=FrozenSemanticDissector([copy.deepcopy(payload)]),
        architect=FrozenRelationArchitect({"claims": []}),
        operationalizer=FrozenEpistemicOperationalizer({"observables": []})))
    assert canonical(first) == canonical(second)


def test_the_pipeline_holds_no_prompt_and_no_taxonomy():
    """It owns the ORDER, the budget and the assembly. A stage order with judgement in it is one
    that disagrees with its stages."""
    source = pathlib.Path(P.__file__).read_text(encoding="utf-8")
    assert "SYSTEM_PROMPT" not in source
    assert "You are a" not in source


# ── the audit as disposer of last resort ─────────────────────────────────────

def test_an_unavailable_dissector_still_produces_a_readable_graph():
    """Two laws disagreed about one object: "every unit has exactly one disposition" made a
    compilation whose dissector never ran unrepresentable, and "silence is an empty graph carrying
    a refusal" required exactly that graph. The audit closes the ledger and signs its work."""
    council = P.Council(dissector=None, architect=None, operationalizer=None)
    graph = P.dissolve(a_request(), council)

    assert isinstance(graph, SemanticInquiryGraph)
    assert graph.semantic_atoms == []
    assert {c.source_unit_id for c in graph.coverage} == \
           {u.source_unit_id for u in graph.source_units}
    assert all(c.disposition is DispositionKind.REFUSED for c in graph.coverage)
    assert all("closed by the coverage audit, not by the dissector" in c.reason
               for c in graph.coverage)
    assert any("it was not the council that balanced it" in n for n in graph.notes)


def test_the_last_resort_disposition_is_refused_and_never_remainder():
    """Remainder is content nothing MEASURES; this is content nothing PROCESSED. Using the softer
    word would report a failed pass as an epistemic limit."""
    council = P.Council(dissector=None)
    graph = P.dissolve(a_request(), council)
    assert DispositionKind.SEMANTIC_REMAINDER not in {c.disposition for c in graph.coverage}


def test_the_uncovered_units_are_still_counted_as_refusals_and_as_a_failed_state():
    """The ledger balancing must not make the failure disappear."""
    council = P.Council(dissector=None)
    graph = P.dissolve(a_request(), council)
    assert [r for r in graph.refusals if r.kind.value == "source_unit_uncovered"]
    audit_pass = next(p for p in graph.passes
                      if p.pass_name is DissolutionPass.COVERAGE_AUDIT)
    assert audit_pass.outcome is PassOutcome.COVERAGE_FAILED
    assert graph.notes[-1].startswith("dissolution: unavailable")
