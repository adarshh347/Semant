"""
HARNESS-003A §8 — two frozen fixtures from unrelated subjects, one production path.

The rehearsal fixture is the prompt 002R actually failed on, frozen as MODEL OUTPUT. The control
shares no noun, no cue and no capability pattern with it. Neither asserts that any reading is true:
what is under test is that the SHAPE survives the pipeline, and that it survives it identically for
a subject nobody wrote the code for.

The six distinctions the directive names are checked on BOTH fixtures, not only the rehearsal one —
a control exercising fewer of them would prove the pipeline generalises over the easy half.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from backend.schemas.semantic_compilation import (SCHEMA_VERSION_V2, AtomAuthor, AtomKind,
                                                  CapabilityClass, ClaimKind, DispositionKind,
                                                  DissolutionPass, PassOutcome, SourceUnitKind,
                                                  canonical)
from backend.services.semantic_compilation import dissolution, ids
from backend.tests.fixtures import semantic_dissolution_fixtures as F

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def graphs():
    return {name: F.dissolve_fixture(name) for name in F.FIXTURES}


# ── both fixtures traverse the identical path ────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_whole_pipeline_completes_on_both_fixtures(name, graphs):
    graph = graphs[name]
    assert graph.schema_version == SCHEMA_VERSION_V2
    assert [p.outcome for p in graph.passes] == [PassOutcome.COMPLETED] * len(graph.passes)
    assert graph.refusals == []
    assert graph.notes[-1].startswith("dissolution: completed")


@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_source_unit_has_exactly_one_disposition(name, graphs):
    graph = graphs[name]
    seen = [c.source_unit_id for c in graph.coverage]
    assert sorted(seen) == sorted({u.source_unit_id for u in graph.source_units})
    assert len(seen) == len(set(seen))
    assert all(c.disposition is DispositionKind.REPRESENTED_BY for c in graph.coverage)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_prompt_and_every_quote_survive_byte_for_byte(name, graphs):
    graph = graphs[name]
    assert graph.prompt == F.prompt_for(name)
    for unit in graph.source_units:
        if unit.kind is SourceUnitKind.PROMPT_CLAUSE:
            assert graph.prompt[unit.span[0]:unit.span[1]] == unit.exact_quote


@pytest.mark.parametrize("name", F.FIXTURES)
def test_both_fixtures_run_the_same_pass_sequence(name, graphs):
    assert [p.pass_name for p in graphs[name].passes] == [
        DissolutionPass.SOURCE_LEDGER, DissolutionPass.SEMANTIC_DISSECTOR,
        DissolutionPass.RELATION_ARCHITECT, DissolutionPass.EPISTEMIC_OPERATIONALIZER,
        DissolutionPass.COVERAGE_AUDIT]


def test_the_two_fixtures_are_genuinely_different_inquiries(graphs):
    """The negative control for the test above: an identical pass sequence is also what you get
    from a pipeline that ignores its input."""
    fold, weave = graphs["fold-rehearsal"], graphs["unrelated-weave"]
    assert fold.prompt != weave.prompt
    assert not {a.atom_id for a in fold.semantic_atoms} & {a.atom_id for a in weave.semantic_atoms}
    assert not {c.claim_id for c in fold.claims} & {c.claim_id for c in weave.claims}
    fold_classes = {c for o in fold.observables for c in o.capability_classes}
    weave_classes = {c for o in weave.observables for c in o.capability_classes}
    assert fold_classes != weave_classes
    assert fold_classes & weave_classes, "and they overlap, or they share no production path"


# ── the six distinctions, on both ────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_persons_own_hypothesis_stays_attributed_to_them(name, graphs):
    graph = graphs[name]
    theirs = [a for a in graph.semantic_atoms if a.author is AtomAuthor.USER]
    assert theirs, "the prompt's clauses produced no atom attributed to the person"
    causal = [a for a in theirs if a.unit_kind is AtomKind.CAUSAL_HYPOTHESIS]
    assert causal, "the person's causal claim did not survive as one"
    by_unit = {u.source_unit_id: u for u in graph.source_units}
    for atom in theirs:
        assert all(by_unit[u].is_user_authored for u in atom.source_unit_ids)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_visual_quality_and_the_effect_it_produces_are_different_objects(name, graphs):
    """The distinction the rehearsal turned on. Fusing them would make it impossible to ask whether
    only one of the two could ever be observed."""
    graph = graphs[name]
    qualities = [a for a in graph.semantic_atoms if a.unit_kind is AtomKind.VISUAL_QUALITY]
    effects = [a for a in graph.semantic_atoms if a.unit_kind is AtomKind.CAUSAL_HYPOTHESIS]
    assert qualities and effects
    assert not {a.atom_id for a in qualities} & {a.atom_id for a in effects}


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_cross_image_comparison_is_never_scoped_to_one_image(name, graphs):
    graph = graphs[name]
    comparisons = [c for c in graph.claims if c.claim_kind is ClaimKind.COMPARISON]
    assert comparisons
    assert all(c.image_scope.value != "one_image" for c in comparisons)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_relation_or_effect_reaches_a_claim_of_its_own(name, graphs):
    graph = graphs[name]
    kinds = {c.claim_kind for c in graph.claims}
    assert ClaimKind.CAUSAL_HYPOTHESIS in kinds
    assert kinds & {ClaimKind.SPATIAL_RELATION, ClaimKind.PATTERN_OR_SEQUENCE, ClaimKind.ATTRIBUTE}


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_possible_observation_requests_a_class_and_never_a_tool(name, graphs):
    graph = graphs[name]
    assert graph.observables
    declared = set(CapabilityClass)
    for observable in graph.observables:
        assert observable.capability_classes
        assert set(observable.capability_classes) <= declared


@pytest.mark.parametrize("name", F.FIXTURES)
def test_semantic_remainder_is_present_and_says_why(name, graphs):
    graph = graphs[name]
    assert len(graph.semantic_remainder) >= 3
    for item in graph.semantic_remainder:
        assert item.why.strip()
        assert item.claim_refs


@pytest.mark.parametrize("name", F.FIXTURES)
def test_an_interpretation_keeps_its_residue_when_something_could_contribute(name, graphs):
    """A measurement contributing to an interpretation never exhausts it."""
    graph = graphs[name]
    interpretive = [c for c in graph.claims if c.claim_kind is ClaimKind.INTERPRETATION]
    assert interpretive
    remainder_claims = {r for item in graph.semantic_remainder for r in item.claim_refs}
    assert {c.claim_id for c in interpretive} & remainder_claims


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_sourced_claim_only_ever_asks_for_a_source(name, graphs):
    graph = graphs[name]
    sourced = [c for c in graph.claims if c.claim_kind is ClaimKind.HISTORICAL_OR_SOURCED]
    assert sourced
    for claim in sourced:
        for observable in [o for o in graph.observables if o.claim_id == claim.claim_id]:
            assert CapabilityClass.EXTERNAL_SOURCE in observable.capability_classes


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_fork_is_raised_only_with_two_branches_and_a_consequence(name, graphs):
    graph = graphs[name]
    assert graph.decision_candidates
    for fork in graph.decision_candidates:
        assert len(fork.options) >= 2
        assert fork.why_now.strip()
        assert fork.affected_refs


# ── the markers ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_no_id_is_hardcoded_in_any_fixture(name):
    """Every id is content-derived. A fixture that wrote one down would rot the moment a word
    changed, and would be testing a graph the parser could not produce."""
    raw = (F.FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")
    for prefix in ("su_", "atm_", "clm_", "obs_", "cle_", "dec_", "cov_", "rb_"):
        assert prefix not in raw, f"{name} hardcodes a {prefix!r} id"


@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_marker_in_both_fixtures_resolved(name, graphs):
    graph = graphs[name]
    body = json.dumps(graph.model_dump(mode="json", by_alias=True))
    for marker in (F.UNIT_MARKER, F.ATOM_MARKER, F.CLAIM_MARKER):
        assert marker not in body, f"{marker} survived into the graph unresolved"


def test_an_unresolvable_unit_marker_is_left_alone_and_refused_downstream():
    """A loader that removed it would hide the failure; leaving it makes the dissector refuse an
    anchor that is not in the ledger, by name."""
    units = F.ledger_for("fold-rehearsal")
    payload = F.resolve_units({"source_unit_ids": ["$UNIT:999"]}, units)
    assert payload["source_unit_ids"] == ["$UNIT:999"]


def test_an_unresolvable_atom_marker_is_left_alone():
    assert F.resolve_refs({"atom_ids": ["$ATOM:nope"]}, F.ATOM_MARKER, {})["atom_ids"] == \
        ["$ATOM:nope"]


# ── replay ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_dissolving_a_fixture_twice_is_byte_identical(name):
    assert canonical(F.dissolve_fixture(name)) == canonical(F.dissolve_fixture(name))


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_replay_makes_no_live_call(name, graphs):
    assert all(p.provider is None for p in graphs[name].passes)
    assert all(not p.prompt_tokens for p in graphs[name].passes)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_graph_round_trips_through_json_without_loss(name, graphs):
    from backend.schemas.semantic_compilation import SemanticInquiryGraph
    dumped = graphs[name].model_dump(mode="json", by_alias=True)
    assert SemanticInquiryGraph.model_validate(json.loads(json.dumps(dumped))).model_dump(
        mode="json", by_alias=True) == dumped


# ── the coverage table, which is the deliverable ─────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_coverage_table_answers_what_happened_to_every_paragraph(name, graphs):
    """The question 002R could not answer."""
    rows = dissolution.coverage_table(graphs[name])
    assert len(rows) == len(graphs[name].source_units)
    assert {r["author"] for r in rows} == {"user", "scene_theorist"}
    for row in rows:
        assert row["disposition"] == "represented_by"
        assert row["atoms"], row
        assert row["quote"]


# ── generality ───────────────────────────────────────────────────────────────

def _production_sources():
    roots = [ROOT / "backend" / "services" / "semantic_compilation",
             ROOT / "backend" / "schemas" / "semantic_compilation.py",
             ROOT / "contracts" / "semantic-inquiry-graph.v1.json",
             ROOT / "contracts" / "semantic-inquiry-graph.v2.json",
             ROOT / "scripts" / "semantic_compile.py",
             ROOT / "scripts" / "semantic_dissolve.py"]
    out = []
    for root in roots:
        out.extend(sorted(root.rglob("*.py")) if root.is_dir() else [root])
    return [p for p in out if p.exists()]


def _scannable(path) -> str:
    """The prose that exists to NAME forbidden topics is excluded — see the same exclusion in
    `test_semantic_compilation_generality.py`. A rule cannot be its own violation."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".json":
        return text.lower()
    data = json.loads(text)
    data.pop("no_topic_branch", None)
    return json.dumps(data).lower()


def test_no_production_source_names_either_dissolution_fixtures_subject():
    nouns = F.topic_nouns()
    assert len(nouns) >= 10
    sources = _production_sources()
    assert len(sources) >= 10, "the scan is pointed at nothing"
    offences = [f"{p.relative_to(ROOT)}: {noun}"
                for p in sources for noun in nouns if noun.lower() in _scannable(p)]
    assert offences == [], offences


def test_that_scan_can_fail(tmp_path):
    decoy = tmp_path / "decoy.py"
    decoy.write_text(f"SPECIAL_CASE = {F.topic_nouns()[0]!r}\n", encoding="utf-8")
    assert any(n.lower() in decoy.read_text(encoding="utf-8").lower() for n in F.topic_nouns())


def test_the_two_fixtures_share_no_topic_noun():
    fold = set(F.load("fold-rehearsal")["topic_nouns"])
    weave = set(F.load("unrelated-weave")["topic_nouns"])
    assert not fold & weave


def test_the_loader_itself_names_no_topic():
    source = pathlib.Path(F.__file__).read_text(encoding="utf-8").lower()
    for noun in F.topic_nouns():
        assert noun.lower() not in source
