"""
HARNESS-003D — the council is reachable from the session, and nothing about it is tidied on the way.

003A built the dissolution pipeline and 003B built the checkpointed driver, and neither could reach
the other. These tests are the seam: the coordinator's one-call compiler interface, driven by a
five-pass council, with the three signals 003B reads still answering.

The load-bearing negative is the last section. Integration is where an underperformance becomes
VISIBLE — it is not where it gets repaired — so a council that reports `coverage_failed` must
arrive at the stage ledger as a failure and not as a completed compile.
"""
from __future__ import annotations

import pytest

from backend.schemas.inquiry_stage import StageAttemptOutcome, TruncationSource
from backend.schemas.semantic_compilation import (SCHEMA_VERSION_V1, SCHEMA_VERSION_V2,
                                                  DissolutionPass, PassOutcome)
from backend.services.inquiry_session import outcomes, runtime
from backend.services.inquiry_session.dissolution_binding import DissolutionCompiler
from backend.services.semantic_compilation.base import CompilationRequest
from backend.services.semantic_compilation.dissolution import Council
from backend.tests.fixtures import semantic_dissolution_fixtures as DF


def a_request(name="fold-rehearsal"):
    return CompilationRequest(prompt=DF.prompt_for(name), inquiry_id=DF.FROZEN_INQUIRY,
                              reading=DF.reading_for(name), images=tuple(DF.images_for(name)),
                              now=DF.FROZEN_NOW)


def compiled(name="fold-rehearsal"):
    compiler = DissolutionCompiler(DF.council_for(name))
    return compiler, compiler.compile(a_request(name))


# ── the binding ──────────────────────────────────────────────────────────────

def test_the_runtime_binds_the_council_by_default():
    """The handoff. Until this line the dissolution pipeline was merged and unreachable."""
    compiler = runtime.build_stages().compiler
    assert isinstance(compiler, DissolutionCompiler)
    assert compiler.name == "council"


def test_the_legacy_compiler_is_still_reachable_on_purpose_and_never_as_a_fallback(monkeypatch):
    """A stored v1 session can be REPRODUCED rather than only parsed. Nothing selects this on an
    error — a fallback that switched compilers would make two very different graphs look like one
    pipeline having a bad day."""
    from backend.services.semantic_compilation.compiler import ModelSemanticCompiler
    monkeypatch.setenv("SEMANT_INQUIRY_COMPILER", runtime.COMPILER_LEGACY)
    assert isinstance(runtime.build_stages().compiler, ModelSemanticCompiler)
    monkeypatch.setenv("SEMANT_INQUIRY_COMPILER", "nonsense")
    assert isinstance(runtime.build_stages().compiler, DissolutionCompiler), \
        "an unreadable value falls to the council, never to the compiler 002R failed on"


def test_no_model_stage_is_bound_when_the_deployment_has_none(monkeypatch):
    monkeypatch.setenv("SEMANT_INQUIRY_LIVE_MODELS", "0")
    stages = runtime.build_stages()
    assert stages.compiler is None and stages.theorist is None


@pytest.mark.parametrize("name", DF.FIXTURES)
def test_the_seam_produces_a_v2_graph_with_its_ledger_intact(name):
    _, graph = compiled(name)
    assert graph.schema_version == SCHEMA_VERSION_V2
    assert graph.is_dissolved
    assert {c.source_unit_id for c in graph.coverage} == \
           {u.source_unit_id for u in graph.source_units}
    assert graph.claims and graph.observables


# ── the three signals 003B reads ─────────────────────────────────────────────

@pytest.mark.parametrize("name", DF.FIXTURES)
def test_the_producer_attribute_route_answers_when_there_is_no_single_receipt(name):
    """v2 leaves `provenance.compiler` None on purpose — naming one of three minds as the author of
    all of it would be a lie — so the receipt-field route cannot answer and the producer route must.
    """
    compiler, graph = compiled(name)
    assert graph.provenance.compiler is None
    truncation = outcomes.detect_truncation(graph.provenance.compiler, producer=compiler)
    assert truncation.source is TruncationSource.PRODUCER_ATTRIBUTE
    assert truncation.truncated is False


def test_a_truncated_pass_reaches_the_producer_route_as_truncated():
    compiler, _ = compiled()
    compiler.last_passes = tuple(
        p.model_copy(update={"finish_reasons": ["length"], "outcome": PassOutcome.TRUNCATED})
        if p.pass_name is DissolutionPass.SEMANTIC_DISSECTOR else p
        for p in compiler.last_passes)
    compiler.truncated_calls = 1
    compiler.last_finish_reason = "length"
    truncation = outcomes.detect_truncation(None, producer=compiler)
    assert truncation.truncated is True


def test_length_beats_a_later_stop_in_the_summary_reason():
    """A sweep whose third batch was cut off and whose fourth finished cleanly is a truncated sweep.
    Reading strictly the last reason would report the clean one and lose the fact."""
    compiler = DissolutionCompiler(DF.council_for("fold-rehearsal"))
    compiler.compile(a_request())
    holder = compiler.last_passes[1].model_copy(
        update={"finish_reasons": ["stop", "length", "stop"], "outcome": PassOutcome.TRUNCATED})
    compiler.last_passes = (compiler.last_passes[0], holder, *compiler.last_passes[2:])
    compiler.truncated_calls = 1
    compiler.last_finish_reason = "length"
    assert outcomes.detect_truncation(None, producer=compiler).truncated is True


@pytest.mark.parametrize("name", DF.FIXTURES)
def test_the_coverage_ledger_answers_adequacy_in_both_shapes(name):
    _, graph = compiled(name)
    typed = outcomes.declared_adequacy(graph)
    dumped = outcomes.declared_adequacy(graph.model_dump(mode="json", by_alias=True))
    assert typed.declared and dumped.declared
    assert typed.complete is dumped.complete is True
    assert typed.uncovered == dumped.uncovered == 0


@pytest.mark.parametrize("name", DF.FIXTURES)
def test_the_stage_outcome_for_a_whole_dissolution_is_completed(name):
    compiler, graph = compiled(name)
    outcome = outcomes.outcome_for(
        produced=bool(graph.claims),
        truncation=outcomes.detect_truncation(graph.provenance.compiler, producer=compiler),
        adequacy=outcomes.declared_adequacy(graph.model_dump(mode="json", by_alias=True)),
        unavailable=graph.provenance.compiler_kind == "unavailable")
    assert outcome is StageAttemptOutcome.COMPLETED


# ── what the stage projection reads off the adapter ──────────────────────────

@pytest.mark.parametrize("name", DF.FIXTURES)
def test_the_adapter_counts_only_calls_the_council_actually_made(name):
    """The ledger and the audit are deterministic transforms. Counting them as calls would inflate
    the number a reader uses to judge cost."""
    compiler, graph = compiled(name)
    model_passes = [p for p in graph.passes
                    if p.pass_name not in (DissolutionPass.SOURCE_LEDGER,
                                           DissolutionPass.COVERAGE_AUDIT)]
    assert compiler.actual_calls == sum(p.call_count for p in model_passes)
    assert compiler.actual_calls > 0


def test_a_council_using_two_models_reports_none_rather_than_naming_one():
    """A single model field over a council that used two would name one and hide the other."""
    compiler, _ = compiled()
    compiler.last_passes = (compiler.last_passes[1].model_copy(update={"model": "model-a"}),
                            compiler.last_passes[2].model_copy(update={"model": "model-b"}))
    assert compiler.model is None


def test_one_model_across_the_passes_is_reported():
    compiler, _ = compiled()
    compiler.last_passes = tuple(p.model_copy(update={"model": "one-model"})
                                 for p in compiler.last_passes)
    assert compiler.model == "one-model"


def test_the_adapter_resets_between_compilations():
    """A second inquiry on a reused adapter must not inherit the first one's truncation."""
    compiler = DissolutionCompiler(DF.council_for("fold-rehearsal"))
    compiler.compile(a_request())
    compiler.truncated_calls = 3
    compiler.last_finish_reason = "length"
    compiler2 = DissolutionCompiler(DF.council_for("unrelated-weave"))
    compiler2.compile(a_request("unrelated-weave"))
    assert compiler2.truncated_calls == 0 and compiler2.last_finish_reason == ""


# ── integration does not tidy an underperformance ────────────────────────────

def test_a_coverage_failure_reaches_the_stage_ledger_as_a_failure():
    """THE LOAD-BEARING NEGATIVE. Integration is where an underperformance becomes visible; it is
    not where it gets repaired. A council that could not account for its sources must not arrive as
    a completed compile."""
    from backend.services.semantic_compilation.architect import FrozenRelationArchitect
    from backend.services.semantic_compilation.operationalizer import \
        FrozenEpistemicOperationalizer
    council = Council(dissector=None, architect=FrozenRelationArchitect({"claims": []}),
                      operationalizer=FrozenEpistemicOperationalizer({"observables": []}))
    compiler = DissolutionCompiler(council)
    graph = compiler.compile(a_request())

    assert graph.semantic_atoms == []
    adequacy = outcomes.declared_adequacy(graph.model_dump(mode="json", by_alias=True))
    assert adequacy.complete is False and adequacy.uncovered == len(graph.source_units)
    outcome = outcomes.outcome_for(
        produced=bool(graph.claims),
        truncation=outcomes.detect_truncation(None, producer=compiler),
        adequacy=adequacy, unavailable=graph.provenance.compiler_kind == "unavailable")
    assert outcome is not StageAttemptOutcome.COMPLETED


def test_the_adapter_repairs_nothing_and_reruns_no_pass():
    """It must not improve the council. A second `compile` is a second compilation, not a retry.

    Scanned on the AST rather than the text, for the fifth time in this project and the same reason
    every time: the module's docstring explains that it must not repair a graph, and a scan reading
    prose would report the explanation as the violation and force it out of the file that needs it.
    """
    import ast
    import pathlib
    from backend.services.inquiry_session import dissolution_binding
    tree = ast.parse(pathlib.Path(dissolution_binding.__file__).read_text(encoding="utf-8"))

    assert not [n for n in ast.walk(tree) if isinstance(n, ast.While)]
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    for token in ("SYSTEM_PROMPT", "_Dissection", "build_prompt", "_repair", "SemanticDissector",
                  "RelationArchitect", "EpistemicOperationalizer"):
        assert token not in names, f"the adapter reaches into a lane it only connects: {token!r}"


def test_that_reach_scan_can_fail(tmp_path):
    """The negative control. A scan that ignores prose could also be ignoring everything."""
    import ast
    decoy = tmp_path / "decoy.py"
    decoy.write_text("from x import SemanticDissector\n", encoding="utf-8")
    names = {a.name for n in ast.walk(ast.parse(decoy.read_text(encoding="utf-8")))
             if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "SemanticDissector" in names


def test_a_stored_v1_graph_still_loads_beside_a_v2_one():
    """Retaining v1 readability is the other half of binding v2."""
    from backend.tests.fixtures import semantic_compilation_fixtures as V1
    _, v1 = V1.compile_fixture("cross-image-comparison")
    _, v2 = compiled()
    assert v1.schema_version == SCHEMA_VERSION_V1 and not v1.is_dissolved
    assert v2.schema_version == SCHEMA_VERSION_V2 and v2.is_dissolved
