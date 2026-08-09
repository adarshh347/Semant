"""
HARNESS-003A §1 — the ledger objects, and the laws they make unrepresentable.

Every test here is a way the coverage ledger could go back to being decoration: a paragraph with no
disposition, two dispositions telling two stories, an atom anchored to nothing, the person's own
hypothesis attributed to a model, or a truncated pass calling itself complete.

The migration tests are the other half: v2 may add whatever it likes and may not make a stored v1
graph unreadable.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from backend.schemas.semantic_compilation import (READABLE_SCHEMA_VERSIONS, SCHEMA_VERSION,
                                                  SCHEMA_VERSION_V1, SCHEMA_VERSION_V2,
                                                  UNDERPERFORMING_OUTCOMES, AtomAuthor, AtomKind,
                                                  CoverageDisposition, DispositionKind,
                                                  DissolutionPass, GraphProvenance, PassOutcome,
                                                  PassReceipt, SemanticAtom, SemanticInquiryGraph,
                                                  SourceUnit, SourceUnitKind, canonical)
from backend.services.semantic_compilation import ids

INQUIRY = "inq_000000000001"
PROMPT = "the first thing has one quality; the second thing has another, and one causes the other"


def a_unit(text="the first thing has one quality", *, kind=SourceUnitKind.READING_BLOCK,
           ref="rb_1", **kw) -> SourceUnit:
    return SourceUnit(source_unit_id=ids.source_unit_id(INQUIRY, kind, ref, text), kind=kind,
                      source_ref=ref, exact_quote=text, **kw)


def an_atom(unit: SourceUnit, text="one quality is present", *, kind=AtomKind.VISUAL_QUALITY,
            **kw) -> SemanticAtom:
    return SemanticAtom(atom_id=ids.atom_id(INQUIRY, kind, text, [unit.source_unit_id]),
                        text=text, unit_kind=kind, source_unit_ids=[unit.source_unit_id],
                        quotes=[unit.exact_quote], **kw)


def covered(unit: SourceUnit, *atoms: SemanticAtom, **kw) -> CoverageDisposition:
    kw.setdefault("disposition", DispositionKind.REPRESENTED_BY)
    kw.setdefault("refs", [a.atom_id for a in atoms])
    return CoverageDisposition(coverage_id=ids.coverage_id(INQUIRY, unit.source_unit_id),
                               source_unit_id=unit.source_unit_id, **kw)


def a_graph(**kw) -> SemanticInquiryGraph:
    kw.setdefault("graph_id", ids.graph_id(INQUIRY, PROMPT))
    kw.setdefault("inquiry_id", INQUIRY)
    kw.setdefault("prompt", PROMPT)
    kw.setdefault("provenance", GraphProvenance(producer="test", compiler_kind="replay"))
    return SemanticInquiryGraph(**kw)


# ── the version, in both directions ──────────────────────────────────────────

def test_this_code_writes_v2_and_reads_both():
    assert SCHEMA_VERSION == SCHEMA_VERSION_V2
    assert READABLE_SCHEMA_VERSIONS == (SCHEMA_VERSION_V1, SCHEMA_VERSION_V2)


def test_a_stored_v1_graph_still_validates_and_carries_no_ledger():
    """The migration's one hard requirement. A v1 graph made no coverage claim; it must not be
    forced to make one retroactively, and it must not be refused for not having."""
    graph = a_graph(schema_version=SCHEMA_VERSION_V1)
    assert graph.schema_version == SCHEMA_VERSION_V1
    assert graph.source_units == [] and graph.semantic_atoms == [] and graph.coverage == []
    assert graph.is_dissolved is False


def test_a_version_this_code_does_not_read_is_refused_by_name():
    with pytest.raises(ValidationError, match="schema_version must be one of"):
        a_graph(schema_version="semantic-inquiry-graph.v3")


@pytest.mark.parametrize("name", ["cross-image-comparison", "unrelated-domain"])
def test_every_frozen_v1_fixture_still_loads_through_the_v2_schema(name):
    """The fixtures are the stored-data proxy. If the v1 payloads stopped round-tripping, so would
    every session in the runs collection written before this lane."""
    from backend.tests.fixtures import semantic_compilation_fixtures as fixtures
    _, graph = fixtures.compile_fixture(name)
    assert graph.claims
    assert canonical(graph) == canonical(
        SemanticInquiryGraph.model_validate(graph.model_dump(mode="json", by_alias=True)))


# ── a source unit ────────────────────────────────────────────────────────────

def test_a_source_unit_with_no_words_is_a_pointer_at_nothing():
    with pytest.raises(ValidationError, match="pointer at nothing"):
        SourceUnit(source_unit_id="su_1", kind=SourceUnitKind.PROMPT_CLAUSE, source_ref="prompt",
                   exact_quote="   ")


def test_a_prompt_clause_is_user_authored_and_a_reading_block_is_not():
    assert a_unit(kind=SourceUnitKind.PROMPT_CLAUSE, ref="prompt").is_user_authored
    assert not a_unit().is_user_authored


def test_a_unit_id_ignores_reading_order_and_follows_content():
    """A theorist that emits its blocks in a different order emits the same blocks. An ordinal in
    the key would renumber a whole ledger — and every atom anchor with it — over a reordering that
    changed nothing."""
    first = a_unit(ordinal=0)
    again = a_unit(ordinal=7)
    assert first.source_unit_id == again.source_unit_id
    assert a_unit("different words").source_unit_id != first.source_unit_id


# ── an atom ──────────────────────────────────────────────────────────────────

def test_an_atom_anchored_to_nothing_cannot_be_constructed():
    with pytest.raises(ValidationError, match="names no source unit"):
        SemanticAtom(atom_id="atm_1", text="something", unit_kind=AtomKind.ENTITY)


def test_an_atom_may_not_declare_a_measured_ceiling():
    unit = a_unit()
    with pytest.raises(ValidationError, match="two removes from the pixels"):
        an_atom(unit, epistemic_ceiling="measured")


def test_the_same_sentence_read_two_ways_is_two_atoms():
    """`a fold has a sharp edge` as a visual quality and as an interpretation are two readings of
    one sentence, and collapsing them would discard whichever arrived second."""
    unit = a_unit()
    quality = an_atom(unit, "it reads one way", kind=AtomKind.VISUAL_QUALITY)
    reading = an_atom(unit, "it reads one way", kind=AtomKind.INTERPRETATION)
    assert quality.atom_id != reading.atom_id


def test_an_atom_id_ignores_the_order_its_anchors_were_listed_in():
    a, b = a_unit("first"), a_unit("second")
    one = ids.atom_id(INQUIRY, AtomKind.RELATION, "x", [a.source_unit_id, b.source_unit_id])
    other = ids.atom_id(INQUIRY, AtomKind.RELATION, "x", [b.source_unit_id, a.source_unit_id])
    assert one == other


# ── a disposition ────────────────────────────────────────────────────────────

def test_represented_by_nothing_is_the_uncovered_case_in_disguise():
    unit = a_unit()
    with pytest.raises(ValidationError, match="Represented by nothing"):
        covered(unit)


def test_a_duplicate_names_exactly_one_original_and_never_itself():
    unit = a_unit()
    with pytest.raises(ValidationError, match="duplicates itself"):
        covered(unit, disposition=DispositionKind.DUPLICATE_OF, refs=[unit.source_unit_id])
    with pytest.raises(ValidationError, match="exactly one original"):
        covered(unit, disposition=DispositionKind.DUPLICATE_OF, refs=["su_a", "su_b"])


@pytest.mark.parametrize("disposition", [DispositionKind.SEMANTIC_REMAINDER,
                                         DispositionKind.REFUSED])
def test_remainder_and_refused_both_need_a_reason(disposition):
    """The reason is the only thing separating an epistemic limit from a pass that failed."""
    with pytest.raises(ValidationError, match="no reason"):
        covered(a_unit(), disposition=disposition, refs=[], reason="")


# ── the ledger's central law ─────────────────────────────────────────────────

def test_a_graph_with_a_ledger_accounts_for_every_unit():
    unit = a_unit()
    atom = an_atom(unit)
    graph = a_graph(source_units=[unit], semantic_atoms=[atom], coverage=[covered(unit, atom)])
    assert graph.is_dissolved is True


def test_a_source_unit_with_no_disposition_fails_the_graph():
    seen, unseen = a_unit("one"), a_unit("two")
    atom = an_atom(seen)
    with pytest.raises(ValidationError, match="no coverage disposition"):
        a_graph(source_units=[seen, unseen], semantic_atoms=[atom], coverage=[covered(seen, atom)])


def test_a_source_unit_with_two_dispositions_fails_the_graph():
    unit = a_unit()
    atom = an_atom(unit)
    twice = CoverageDisposition(coverage_id="cov_other", source_unit_id=unit.source_unit_id,
                                disposition=DispositionKind.SEMANTIC_REMAINDER,
                                reason="also called remainder")
    with pytest.raises(ValidationError, match="more than one disposition"):
        a_graph(source_units=[unit], semantic_atoms=[atom], coverage=[covered(unit, atom), twice])


def test_atoms_without_a_ledger_are_anchors_pointing_outside_the_graph():
    unit = a_unit()
    with pytest.raises(ValidationError, match="anchors point outside itself"):
        a_graph(semantic_atoms=[an_atom(unit)])


def test_an_atom_anchored_to_a_unit_that_is_not_here_fails_the_graph():
    here, elsewhere = a_unit("one"), a_unit("two")
    stray = an_atom(elsewhere)
    mine = an_atom(here)
    with pytest.raises(ValidationError, match="not a source unit in this graph"):
        a_graph(source_units=[here], semantic_atoms=[mine, stray],
                coverage=[covered(here, mine)])


def test_coverage_pointing_at_an_atom_that_is_not_here_fails_the_graph():
    unit = a_unit()
    atom = an_atom(unit)
    lying = CoverageDisposition(coverage_id=ids.coverage_id(INQUIRY, unit.source_unit_id),
                                source_unit_id=unit.source_unit_id,
                                disposition=DispositionKind.REPRESENTED_BY, refs=["atm_invented"])
    with pytest.raises(ValidationError, match="not an atom in this graph"):
        a_graph(source_units=[unit], semantic_atoms=[atom], coverage=[lying])


# ── the attribution law ──────────────────────────────────────────────────────

def test_the_persons_own_words_cannot_be_attributed_to_a_model():
    """The one attribution error nothing downstream can detect: a model observation is exactly what
    the rest of the graph is made of."""
    clause = a_unit("one causes the other", kind=SourceUnitKind.PROMPT_CLAUSE, ref="prompt")
    stolen = an_atom(clause, kind=AtomKind.CAUSAL_HYPOTHESIS,
                     author=AtomAuthor.SEMANTIC_DISSECTOR)
    with pytest.raises(ValidationError, match="attribution error nothing downstream can detect"):
        a_graph(source_units=[clause], semantic_atoms=[stolen], coverage=[covered(clause, stolen)])


def test_the_same_atom_attributed_to_the_user_is_accepted():
    clause = a_unit("one causes the other", kind=SourceUnitKind.PROMPT_CLAUSE, ref="prompt")
    kept = an_atom(clause, kind=AtomKind.CAUSAL_HYPOTHESIS, author=AtomAuthor.USER)
    graph = a_graph(source_units=[clause], semantic_atoms=[kept], coverage=[covered(clause, kept)])
    assert graph.semantic_atoms[0].author is AtomAuthor.USER


def test_an_atom_drawing_on_the_person_AND_the_reading_may_be_the_dissectors():
    """The rule is about atoms anchored ONLY to the person's words. One that genuinely synthesises
    a clause with a reading block is the dissector's work and says so."""
    clause = a_unit("one causes the other", kind=SourceUnitKind.PROMPT_CLAUSE, ref="prompt")
    block = a_unit("the second thing has another")
    both = SemanticAtom(
        atom_id=ids.atom_id(INQUIRY, AtomKind.COMPARISON, "they differ",
                            [clause.source_unit_id, block.source_unit_id]),
        text="they differ", unit_kind=AtomKind.COMPARISON,
        source_unit_ids=[clause.source_unit_id, block.source_unit_id],
        author=AtomAuthor.SEMANTIC_DISSECTOR)
    graph = a_graph(source_units=[clause, block], semantic_atoms=[both],
                    coverage=[covered(clause, both), covered(block, both)])
    assert len(graph.coverage) == 2


# ── a pass receipt ───────────────────────────────────────────────────────────

def test_a_truncated_pass_cannot_call_itself_completed():
    """HARNESS-002R's central failure, made unrepresentable rather than merely recorded."""
    with pytest.raises(ValidationError, match="is a PREFIX"):
        PassReceipt(pass_id="pas_1", pass_name=DissolutionPass.SEMANTIC_DISSECTOR,
                    outcome=PassOutcome.COMPLETED, finish_reasons=["length"])


def test_the_same_pass_reporting_truncated_is_accepted_and_says_so():
    receipt = PassReceipt(pass_id="pas_1", pass_name=DissolutionPass.SEMANTIC_DISSECTOR,
                          outcome=PassOutcome.TRUNCATED, finish_reasons=["stop", "length"])
    assert receipt.truncated is True
    assert receipt.underperformed is True


def test_only_completed_is_not_an_underperformance():
    for outcome in PassOutcome:
        receipt = PassReceipt(pass_id="p", pass_name=DissolutionPass.COVERAGE_AUDIT,
                              outcome=outcome)
        assert receipt.underperformed is (outcome is not PassOutcome.COMPLETED)
    assert PassOutcome.COMPLETED not in UNDERPERFORMING_OUTCOMES


def test_an_unreported_token_count_is_null_rather_than_zero():
    """A call whose usage the provider did not report did not use zero tokens."""
    receipt = PassReceipt(pass_id="p", pass_name=DissolutionPass.SOURCE_LEDGER,
                          outcome=PassOutcome.COMPLETED)
    assert receipt.prompt_tokens is None and receipt.completion_tokens is None


def test_the_repair_pass_and_the_pass_it_repairs_are_two_receipts():
    first = ids.pass_id(INQUIRY, DissolutionPass.SEMANTIC_DISSECTOR, 1)
    second = ids.pass_id(INQUIRY, DissolutionPass.SEMANTIC_DISSECTOR, 2)
    assert first != second


# ── round trip ───────────────────────────────────────────────────────────────

def test_a_v2_graph_round_trips_through_json_without_loss_or_invention():
    unit = a_unit()
    atom = an_atom(unit)
    graph = a_graph(source_units=[unit], semantic_atoms=[atom], coverage=[covered(unit, atom)],
                    passes=[PassReceipt(pass_id="pas_1", pass_name=DissolutionPass.SOURCE_LEDGER,
                                        outcome=PassOutcome.COMPLETED, inputs=1, outputs=1)])
    dumped = graph.model_dump(mode="json", by_alias=True)
    restored = SemanticInquiryGraph.model_validate(json.loads(json.dumps(dumped)))
    assert restored.model_dump(mode="json", by_alias=True) == dumped
    # `object` survives its alias — the field is `object_` in Python and `object` on the wire, and a
    # round trip that quietly renamed it would break every consumer reading the JSON.
    assert "object" in dumped["semantic_atoms"][0]
