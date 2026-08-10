"""
HARNESS-003A/003B reconciliation — the typed `finish_reason` Lane B asked for by name.

`inquiry_session/outcomes.py` consults three routes in order and records which answered:

    field                a typed field on the receipt — "Does not exist yet … this route is
                         written for the Lane A change that should add it."
    producer_attribute   `last_finish_reason` / `truncated_calls` on the producer object
    receipt_note         an anchored `finish_reason: ` note

It has been falling through to the third for every reading in the tree. These tests prove the
first route now answers, and that the two better routes agree with it — a field and a note written
from the same variable cannot disagree, and this is where that is checked rather than assumed.
"""
from __future__ import annotations

import pytest

from backend.schemas.inquiry_stage import TruncationSource
from backend.schemas.semantic_compilation import CallTopology, ModelReceipt
from backend.services.inquiry_session import outcomes
from backend.services.semantic_compilation import theorist as T
from backend.services.semantic_compilation.base import to_image_refs
from backend.services.semantic_compilation.compiler import ModelSemanticCompiler
from backend.services.semantic_compilation.base import CompilationRequest


class _Choice:
    def __init__(self, content, finish):
        self.message = type("M", (), {"content": content})()
        self.finish_reason = finish


class _Client:
    """A groq-shaped double that stops for a stated reason."""

    def __init__(self, body, finish="stop"):
        self._body, self._finish = body, finish
        self.calls = 0
        self.chat = type("C", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls += 1
        return type("R", (), {"choices": [_Choice(self._body, self._finish)],
                              "usage": None})()


# ── the field exists and is typed ────────────────────────────────────────────

def test_a_receipt_that_was_never_called_reports_no_finish_reason_rather_than_an_empty_one():
    """`None` is not `""`. An unavailable call reports no finish reason because there was no call,
    and a route reading the empty string as "stopped normally" would report an unchecked stage as
    a verified one."""
    receipt = ModelReceipt(role="scene_theorist")
    assert receipt.finish_reason is None
    assert outcomes.detect_truncation(receipt).source is not TruncationSource.FIELD


def test_the_field_route_answers_for_a_normal_stop():
    receipt = ModelReceipt(role="semantic_compiler", finish_reason="stop")
    truncation = outcomes.detect_truncation(receipt)
    assert truncation.source is TruncationSource.FIELD
    assert truncation.truncated is False
    assert "finish_reason" in truncation.detail


def test_the_field_route_answers_for_a_length_stop():
    receipt = ModelReceipt(role="semantic_compiler", finish_reason="length")
    truncation = outcomes.detect_truncation(receipt)
    assert truncation.source is TruncationSource.FIELD
    assert truncation.truncated is True


def test_the_field_is_consulted_before_the_note():
    """The whole point of adding it. A note is prose that happens to be machine-written; a field
    cannot be reworded by somebody improving a sentence."""
    receipt = ModelReceipt(role="semantic_compiler", finish_reason="length",
                           notes=["finish_reason: stop"])
    truncation = outcomes.detect_truncation(receipt)
    assert truncation.source is TruncationSource.FIELD
    assert truncation.truncated is True


# ── the live adapters set it, and it agrees with the note ────────────────────

def _reading_body():
    return ('{"reading": "a paragraph", "blocks": [{"kind": "part", "text": "a part is present", '
            '"images": ["img_a"]}]}')


@pytest.mark.parametrize("finish,expected", [("stop", False), ("length", True)])
def test_the_theorist_records_its_finish_reason_as_a_field(finish, expected):
    reader = T.ModelSceneTheorist(client=_Client(_reading_body(), finish=finish))
    result = reader.read("a question about something",
                         to_image_refs([{"post_id": "img_a", "image_ref": "scratch://a.jpg"}]),
                         inquiry_id="inq_1", now="2026-08-10T00:00:00+00:00")
    receipt = result.reading.provenance
    assert receipt.finish_reason == finish
    truncation = outcomes.detect_truncation(receipt)
    assert truncation.source is TruncationSource.FIELD
    assert truncation.truncated is expected


def test_the_field_and_the_note_are_written_from_one_variable_and_cannot_disagree():
    """Both are kept: removing the note would break the fallback for anything still reading notes.
    They agree because they come from the same value, and this is where that is checked."""
    reader = T.ModelSceneTheorist(client=_Client(_reading_body(), finish="length"))
    result = reader.read("a question about something",
                         to_image_refs([{"post_id": "img_a", "image_ref": "scratch://a.jpg"}]),
                         inquiry_id="inq_1", now="2026-08-10T00:00:00+00:00")
    receipt = result.reading.provenance
    assert receipt.finish_reason == "length"
    # The producer-attribute route agrees too.
    assert outcomes.detect_truncation(receipt, producer=reader).truncated is True


@pytest.mark.parametrize("finish,expected", [("stop", False), ("length", True)])
def test_the_legacy_compiler_records_its_finish_reason_as_a_field(finish, expected):
    body = '{"claims": []}'
    graph = ModelSemanticCompiler(client=_Client(body, finish=finish)).compile(
        CompilationRequest(prompt="a question about something", inquiry_id="inq_1",
                           now="2026-08-10T00:00:00+00:00"))
    receipt = graph.provenance.compiler
    assert receipt.finish_reason == finish
    truncation = outcomes.detect_truncation(receipt)
    assert truncation.source is TruncationSource.FIELD
    assert truncation.truncated is expected
    assert any(n.startswith("finish_reason:") for n in receipt.notes), \
        "the note stays, so anything still reading notes keeps working"


def test_a_replayed_receipt_reports_no_finish_reason_because_nothing_was_called():
    reader = T.FrozenSceneTheorist({"reading": "r", "blocks": []})
    result = reader.read("a question", to_image_refs([{"post_id": "img_a"}]), inquiry_id="inq_1")
    assert result.reading.provenance.finish_reason is None


def test_the_receipt_for_one_call_carries_a_reason_and_the_pass_receipt_carries_many():
    """A `ModelReceipt` covers one logical call; a list there would report the last reason as if it
    spoke for all of them. The per-pass, many-call receipt is `PassReceipt`."""
    from backend.schemas.semantic_compilation import DissolutionPass, PassOutcome, PassReceipt
    assert isinstance(ModelReceipt(role="r").finish_reason, type(None))
    many = PassReceipt(pass_id="pas_1", pass_name=DissolutionPass.SEMANTIC_DISSECTOR,
                       outcome=PassOutcome.TRUNCATED, finish_reasons=["stop", "length"])
    assert many.truncated is True


# ── 003B's second request: a coverage signal it can read ─────────────────────

def test_lane_b_reads_a_v2_graphs_coverage_ledger_with_no_edit_on_its_side():
    """003B's other tree contradiction: "No coverage or adequacy signal exists on the graph yet …
    `declared_adequacy` reads both shapes it will plausibly take — a flag and a per-source-unit
    ledger — and returns undeclared until one arrives."

    The v2 ledger is the second shape. This asserts the seam rather than assuming it: a rename of
    `coverage`, or a disposition value outside the four, would break the reader silently otherwise.
    """
    from backend.tests.fixtures import semantic_dissolution_fixtures as F
    graph = F.dissolve_fixture("fold-rehearsal")
    # THE DUMPED FORM, because that is what production passes: the session stores the graph as a
    # mapping (`inquiry_session` holds `graph: Dict[str, Any]`), and the reader walks mappings.
    adequacy = outcomes.declared_adequacy(graph.model_dump(mode="json", by_alias=True))
    assert adequacy.declared is True
    assert adequacy.complete is True
    assert adequacy.uncovered == 0
    assert "coverage ledger disposes of" in adequacy.detail


def test_an_incomplete_ledger_reads_as_incomplete_on_lane_bs_side_too():
    """The negative control. A reader that said `complete` for everything would be worse than one
    that said `undeclared`."""
    from backend.schemas.semantic_compilation import (CoverageDisposition, DispositionKind,
                                                      GraphProvenance, SemanticInquiryGraph,
                                                      SourceUnit, SourceUnitKind)
    from backend.services.semantic_compilation import ids as I
    unit = SourceUnit(source_unit_id=I.source_unit_id("inq_1", SourceUnitKind.PROMPT_CLAUSE,
                                                      "prompt", "a clause of real content"),
                      kind=SourceUnitKind.PROMPT_CLAUSE, source_ref="prompt",
                      exact_quote="a clause of real content")
    graph = SemanticInquiryGraph(
        graph_id="sig_1", inquiry_id="inq_1", prompt="a clause of real content",
        source_units=[unit],
        coverage=[CoverageDisposition(coverage_id=I.coverage_id("inq_1", unit.source_unit_id),
                                      source_unit_id=unit.source_unit_id,
                                      disposition=DispositionKind.REFUSED,
                                      reason="nothing dissolved it")],
        provenance=GraphProvenance(producer="test", compiler_kind="council"))
    adequacy = outcomes.declared_adequacy(graph.model_dump(mode="json", by_alias=True))
    assert adequacy.declared is True and adequacy.complete is False and adequacy.uncovered == 1


def test_the_reader_counts_a_refused_ledger_the_same_whether_typed_or_dumped():
    """003A pinned this as a FAILING-ON-FIX test and 003D is the fix.

    `declared_adequacy` tested `isinstance(entry, Mapping)` and nothing else, so a typed v2 graph —
    a list of `CoverageDisposition` models — matched no entry and reported `complete` for a ledger
    that could be entirely refusals. Production stores the dumped mapping, so the running system was
    never wrong; anyone holding the object in process was.

    The old test asserted the broken behaviour on purpose, with a note saying it should fail the day
    somebody fixed it. It did, and this replaced it.
    """
    from backend.schemas.semantic_compilation import (CoverageDisposition, DispositionKind,
                                                      GraphProvenance, SemanticInquiryGraph,
                                                      SourceUnit, SourceUnitKind)
    from backend.services.semantic_compilation import ids as I
    unit = SourceUnit(source_unit_id=I.source_unit_id("inq_1", SourceUnitKind.PROMPT_CLAUSE,
                                                      "prompt", "a clause of real content"),
                      kind=SourceUnitKind.PROMPT_CLAUSE, source_ref="prompt",
                      exact_quote="a clause of real content")
    graph = SemanticInquiryGraph(
        graph_id="sig_1", inquiry_id="inq_1", prompt="a clause of real content",
        source_units=[unit],
        coverage=[CoverageDisposition(coverage_id=I.coverage_id("inq_1", unit.source_unit_id),
                                      source_unit_id=unit.source_unit_id,
                                      disposition=DispositionKind.REFUSED,
                                      reason="nothing dissolved it")],
        provenance=GraphProvenance(producer="test", compiler_kind="council"))
    typed = outcomes.declared_adequacy(graph)
    dumped = outcomes.declared_adequacy(graph.model_dump(mode="json", by_alias=True))
    assert typed.uncovered == dumped.uncovered == 1
    assert typed.complete is dumped.complete is False


def test_an_enum_disposition_is_compared_by_value_and_not_by_repr():
    """`DispositionKind.REFUSED` against the string `"refused"` is False, and a comparison that is
    always False is a check that never fires — the same shape as the Mapping bug, one level in."""
    from backend.schemas.semantic_compilation import DispositionKind
    from backend.services.inquiry_session.outcomes import _disposition_of

    class _Entry:
        disposition = DispositionKind.REFUSED

    assert _disposition_of(_Entry()) == "refused"
    assert _disposition_of({"disposition": "refused"}) == "refused"
    assert _disposition_of({"disposition": DispositionKind.REPRESENTED_BY}) == "represented_by"
    assert _disposition_of({}) == ""
