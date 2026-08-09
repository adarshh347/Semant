"""
HARNESS-002A §6 — two subjects with nothing in common, one production path.

The lane's claim is that a rich visual question becomes an inspectable graph WITHOUT the code
knowing what the question is about. The proof is two frozen model outputs — a cross-image
comparison of built interiors, and a question about how two plants divide as they grow — run
through the identical parser, schema and contract, plus a scan (with its own negative control)
proving neither subject's vocabulary appears in any production source.

The fixtures also close the seam to Lane A: each carries a REAL `InquiryFrame` produced by the
deterministic framer, and this file re-frames the prompt to prove the frozen one still matches.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (CapabilityClass, ClaimKind, ClaimStatus,
                                                  CompilerRefusalKind, ImageScope, SourceType,
                                                  canonical)
from backend.schemas.inquiry import canonical as canonical_frame
from backend.services.inquiry import frame_prompt
from backend.services.semantic_compilation import contracts
from backend.tests.fixtures import semantic_compilation_fixtures as fixtures

PRODUCTION_SOURCES = [
    Path("backend/services/semantic_compilation"),
    Path("backend/schemas/semantic_compilation.py"),
    Path("contracts/semantic-inquiry-graph.v1.json"),
    Path("scripts/semantic_compile.py"),
]

#: The seven distinctions the directive requires the rehearsal-shaped fixture to keep apart.
REQUIRED_DISTINCTIONS = {
    "a segmentable entity candidate": lambda g: [
        c for c in g.claims_of(ClaimKind.ENTITY)
        if c.epistemic_demand is DemandKind.MEASURABLE
        and any(CapabilityClass.EXTENT in o.capability_classes for o in
                g.observables_for(c.claim_id))],
    "a spatial or hierarchy relation": lambda g: (g.claims_of(ClaimKind.SPATIAL_RELATION)
                                                  + g.claims_of(ClaimKind.HIERARCHY)),
    "an interpretive abstraction": lambda g: g.claims_of(ClaimKind.INTERPRETATION),
    "a sourced historical generalization": lambda g: g.claims_of(ClaimKind.HISTORICAL_OR_SOURCED),
    "a causal hypothesis": lambda g: g.claims_of(ClaimKind.CAUSAL_HYPOTHESIS),
    "a generative rule": lambda g: g.claims_of(ClaimKind.GENERATIVE_RULE),
    "a semantic remainder": lambda g: g.semantic_remainder,
}


def _sources() -> list:
    files = []
    for path in PRODUCTION_SOURCES:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        elif path.exists():
            files.append(path)
    return files


# ── both fixtures traverse the same path ────────────────────────────────────

@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_a_fixture_compiles_cleanly_with_nothing_refused(name):
    _, graph = fixtures.compile_fixture(name)
    assert graph.refusals == [], [r.model_dump() for r in graph.refusals]
    assert graph.claims and graph.observables


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_a_fixture_produces_the_same_typed_shape_whatever_its_subject(name):
    _, graph = fixtures.compile_fixture(name)
    kinds = {c.claim_kind for c in graph.claims}
    for required in (ClaimKind.COMPARISON, ClaimKind.HISTORICAL_OR_SOURCED,
                     ClaimKind.CAUSAL_HYPOTHESIS, ClaimKind.INTERPRETATION,
                     ClaimKind.GENERATIVE_RULE, ClaimKind.UNKNOWN):
        assert required in kinds, f"{name} lost {required.value}"
    assert graph.provenance.producer == "semantic_compilation/compiler-v1"
    assert graph.provenance.compiler_kind == "replay"


def test_the_rehearsal_fixture_keeps_all_seven_distinctions_apart():
    _, graph = fixtures.compile_fixture("cross-image-comparison")
    for label, select in REQUIRED_DISTINCTIONS.items():
        assert select(graph), f"the fixture demonstrates no {label}"


def test_the_two_fixtures_ask_for_different_capabilities():
    """If the same classes came back for both, the compiler would be keying on something other than
    what it was handed — which is what a topic branch looks like from the outside."""
    _, a = fixtures.compile_fixture("cross-image-comparison")
    _, b = fixtures.compile_fixture("unrelated-domain")
    assert set(a.capability_classes()) != set(b.capability_classes())
    assert set(a.capability_classes()) & set(b.capability_classes())     # and they overlap


def test_the_two_fixtures_share_no_claim_id():
    """Ids are keyed on the inquiry as well as the content, so two inquiries never collide even
    where they would say the same words."""
    _, a = fixtures.compile_fixture("cross-image-comparison")
    _, b = fixtures.compile_fixture("unrelated-domain")
    assert not {c.claim_id for c in a.claims} & {c.claim_id for c in b.claims}


# ── no topic branch ──────────────────────────────────────────────────────────

def test_no_production_source_names_either_fixture_s_subject():
    nouns = fixtures.topic_nouns()
    assert len(nouns) >= 8
    offences = []
    for path in _sources():
        text = path.read_text(encoding="utf-8").lower()
        for noun in nouns:
            if noun.lower() in text:
                offences.append(f"{path}: {noun}")
    assert offences == [], offences


def test_that_scan_can_fail(tmp_path):
    """The negative control. A scan that matches nothing is indistinguishable from a scan pointed
    at the wrong directory."""
    decoy = tmp_path / "decoy.py"
    decoy.write_text("SPECIAL_CASE = 'phyllotaxis'\n", encoding="utf-8")
    text = decoy.read_text(encoding="utf-8").lower()
    assert any(noun.lower() in text for noun in fixtures.topic_nouns())


def test_the_production_package_imports_no_database_and_no_model_client():
    """Structural, because the guarantee is 'this compiles nothing into a write'. `groq` is
    imported INSIDE the live adapters' `_get_client`, so a deterministic replay pays for no client
    and a slim deploy can import the package with nothing installed."""
    forbidden = {"pymongo", "motor", "backend.database", "groq", "torch", "requests", "httpx"}
    for path in sorted(Path("backend/services/semantic_compilation").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.col_offset == 0:
                names = ({n.name for n in node.names} if isinstance(node, ast.Import)
                         else {node.module or ""})
                assert not names & forbidden, f"{path} imports {names & forbidden} at module level"


def test_that_scan_can_fail_too(tmp_path):
    decoy = tmp_path / "decoy.py"
    decoy.write_text("import pymongo\n", encoding="utf-8")
    tree = ast.parse(decoy.read_text(encoding="utf-8"))
    top = [n for n in ast.walk(tree) if isinstance(n, ast.Import) and n.col_offset == 0]
    assert any("pymongo" in {a.name for a in n.names} for n in top)


# ── replay ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_two_replays_of_one_fixture_are_byte_identical(name):
    a = canonical(fixtures.compile_fixture(name, now="2026-08-09T10:00:00+00:00")[1])
    b = canonical(fixtures.compile_fixture(name, now="2026-08-09T23:59:59+00:00")[1])
    assert a == b


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_only_thing_a_different_clock_changes_is_the_declared_volatile_fields(name):
    a = fixtures.compile_fixture(name, now="2026-08-09T10:00:00+00:00")[1]
    b = fixtures.compile_fixture(name, now="2026-08-09T23:59:59+00:00")[1]
    assert a.model_dump(mode="json") != b.model_dump(mode="json")
    assert a.provenance.compiled_at != b.provenance.compiled_at
    assert canonical(a) == canonical(b)


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_a_graph_round_trips_through_json_without_losing_a_field(name):
    _, graph = fixtures.compile_fixture(name)
    dumped = graph.model_dump(mode="json", by_alias=True)
    reloaded = type(graph).model_validate(json.loads(json.dumps(dumped)))
    assert reloaded.model_dump(mode="json", by_alias=True) == dumped


# ── the seam to Lane A ───────────────────────────────────────────────────────

@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_frozen_frame_is_still_what_the_deterministic_framer_produces(name):
    """The fixtures carry a REAL `InquiryFrame`, not a hand-written stand-in. If Lane A's lexicon
    moves, this fails here — where it is a reconciliation — rather than downstream as a diff."""
    fixture = fixtures.load(name)
    from backend.schemas.inquiry import InquiryFrame
    frozen = InquiryFrame.model_validate(fixture["inquiry_frame"])
    fresh = frame_prompt(fixture["prompt"], fixture["corpus"])
    assert canonical_frame(frozen) == canonical_frame(fresh)


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_frame_arrives_on_the_graph_byte_for_byte(name):
    fixture, graph = fixtures.compile_fixture(name)
    assert graph.inquiry_frame == fixture["inquiry_frame"]
    assert graph.prompt == fixture["prompt"] == fixture["inquiry_frame"]["prompt"]
    assert graph.provenance.inquiry_frame_schema_version == "inquiry-frame.v1"


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_frame_still_claims_nothing_about_any_image_after_compilation(name):
    """Lane A's guarantee has to survive the seam: the graph embeds the frame and does not enrich
    it. A frame that gained an image fact by being carried would break the one thing it promises."""
    _, graph = fixtures.compile_fixture(name)
    keys = contracts.forbidden_geometry_keys()
    assert contracts.geometry_keys_in(graph.inquiry_frame) == []
    for action in graph.inquiry_frame.get("proposed_actions") or ():
        assert action["status"] == "proposed"
        assert not set(action.get("payload") or {}) & keys


# ── pointers resolve ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_every_source_pointer_resolves_to_something_that_exists(name):
    _, graph = fixtures.compile_fixture(name)
    block_ids = {b.block_id for b in graph.reading.blocks}
    seen = set()
    for claim in graph.claims:
        assert claim.sources, claim.claim_id
        for pointer in claim.sources:
            seen.add(pointer.source_type)
            if pointer.source_type is SourceType.SCENE_READING:
                assert pointer.source_id in block_ids, pointer.source_id
            if pointer.source_type is SourceType.PROMPT and pointer.span:
                start, end = pointer.span
                assert graph.prompt[start:end].lower() == pointer.text.lower()
    assert {SourceType.PROMPT, SourceType.SCENE_READING, SourceType.COMPILER_INFERENCE} <= seen


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_every_inference_names_a_parent_that_is_in_the_graph(name):
    _, graph = fixtures.compile_fixture(name)
    ids = {c.claim_id for c in graph.claims}
    inferences = [c for c in graph.claims
                  if any(s.source_type is SourceType.COMPILER_INFERENCE for s in c.sources)]
    assert inferences
    for claim in inferences:
        assert claim.inferred_from
        assert set(claim.inferred_from) <= ids


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_every_decision_candidate_points_at_a_claim_and_an_observable_that_exist(name):
    _, graph = fixtures.compile_fixture(name)
    known = {c.claim_id for c in graph.claims} | {o.observable_id for o in graph.observables}
    assert graph.decision_candidates
    for decision in graph.decision_candidates:
        assert decision.affected_refs
        assert set(decision.affected_refs) <= known


# ── the honesty guards, on real fixture data ─────────────────────────────────

@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_no_claim_in_either_fixture_starts_visible_or_measured(name):
    _, graph = fixtures.compile_fixture(name)
    assert all(c.status in set(ClaimStatus) for c in graph.claims)
    assert "measured" not in {c.status.value for c in graph.claims}


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_sourced_claim_is_only_ever_asked_of_an_external_source(name):
    _, graph = fixtures.compile_fixture(name)
    sourced = graph.claims_of(ClaimKind.HISTORICAL_OR_SOURCED)
    assert sourced
    for claim in sourced:
        assert claim.epistemic_demand is DemandKind.SOURCED
        assert claim.image_scope is ImageScope.NOT_AN_IMAGE_QUESTION
        for observable in graph.observables_for(claim.claim_id):
            assert observable.capability_classes == [CapabilityClass.EXTERNAL_SOURCE]


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_generative_rule_stays_imagined_and_is_asked_of_nothing(name):
    _, graph = fixtures.compile_fixture(name)
    rules = graph.claims_of(ClaimKind.GENERATIVE_RULE)
    assert rules
    for rule in rules:
        assert rule.epistemic_demand is DemandKind.IMAGINED
        assert graph.observables_for(rule.claim_id) == []


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_interpretation_is_asked_only_for_a_reading_and_keeps_its_remainder(name):
    _, graph = fixtures.compile_fixture(name)
    interpretations = graph.claims_of(ClaimKind.INTERPRETATION)
    assert interpretations
    for claim in interpretations:
        assert claim.epistemic_demand is DemandKind.INTERPRETIVE
        for observable in graph.observables_for(claim.claim_id):
            assert observable.capability_classes == [CapabilityClass.SEMANTIC_READING]
        assert any(claim.claim_id in item.claim_refs for item in graph.semantic_remainder)


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_remainder_names_what_contributes_without_becoming_it(name):
    """The lane's single most important assertion, inherited from HARNESS-001A: naming the
    measurements that bear on a term is what makes refusing to call it measurable a position
    rather than a shrug — and the naming must not perform the promotion."""
    _, graph = fixtures.compile_fixture(name)
    contributing = [i for i in graph.semantic_remainder if i.contributing_capability_classes]
    assert contributing
    measurable_subjects = {c.subject.lower() for c in graph.claims
                           if c.epistemic_demand is DemandKind.MEASURABLE}
    for item in graph.semantic_remainder:
        assert item.term.lower() not in measurable_subjects


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_every_observable_says_what_stays_interpretive_even_if_it_succeeds(name):
    _, graph = fixtures.compile_fixture(name)
    for observable in graph.observables:
        assert observable.remains_interpretive.strip(), observable.observable_id


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_unknown_claim_is_kept_rather_than_dropped_to_look_complete(name):
    _, graph = fixtures.compile_fixture(name)
    unknown = graph.claims_of(ClaimKind.UNKNOWN)
    assert unknown
    for claim in unknown:
        assert claim.epistemic_demand is DemandKind.UNRESOLVED
        assert graph.observables_for(claim.claim_id) == []


# ── mutating a fixture is refused, on the same path ─────────────────────────

@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_a_geometry_key_added_to_a_fixture_claim_is_refused(name):
    fixture = fixtures.load(name)
    payload = copy.deepcopy(fixture["compiler_payload"])
    payload["claims"][0]["mask_rle"] = {"size": [4, 4], "counts": [16]}
    _, graph = fixtures.compile_fixture(name, compiler_payload_override=payload)
    assert any(r.kind is CompilerRefusalKind.GEOMETRY_IN_A_READING for r in graph.refusals)
    assert len(graph.claims) == len(fixture["compiler_payload"]["claims"]) - 1


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_a_geometry_key_added_to_a_fixture_reading_block_is_refused(name):
    fixture = fixtures.load(name)
    payload = copy.deepcopy(fixture["theorist_payload"])
    payload["blocks"][0]["bbox"] = [0, 0, 10, 10]
    _, graph = fixtures.compile_fixture(name, theorist_payload=payload)
    assert any(r.kind is CompilerRefusalKind.GEOMETRY_IN_A_READING for r in graph.refusals)
    # And the claim that anchored to the dropped block is refused for being unanchored, rather
    # than silently reattached to a neighbouring block.
    assert any(r.kind is CompilerRefusalKind.UNANCHORED_CLAIM for r in graph.refusals)


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_an_invented_claim_kind_in_a_fixture_is_retained_as_a_refusal(name):
    fixture = fixtures.load(name)
    payload = copy.deepcopy(fixture["compiler_payload"])
    payload["claims"][0]["kind"] = "vibe_claim"
    _, graph = fixtures.compile_fixture(name, compiler_payload_override=payload)
    refused = [r for r in graph.refusals if r.kind is CompilerRefusalKind.UNKNOWN_CLAIM_KIND]
    assert [r.what for r in refused] == ["vibe_claim"]


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_an_invented_capability_class_in_a_fixture_is_retained_as_a_refusal(name):
    fixture = fixtures.load(name)
    payload = copy.deepcopy(fixture["compiler_payload"])
    payload["observables"][0]["capability_classes"] = ["extent", "clairvoyance"]
    _, graph = fixtures.compile_fixture(name, compiler_payload_override=payload)
    refused = [r for r in graph.refusals
               if r.kind is CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS]
    assert [r.what for r in refused] == ["clairvoyance"]
    assert graph.observables[0].capability_classes == [CapabilityClass.EXTENT]


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_an_unresolvable_block_anchor_arrives_as_a_dangling_reference(name):
    """The loader leaves an unmatched `$BLOCK:` marker ALONE. A loader that dropped it would remove
    exactly the case the compiler is supposed to refuse."""
    fixture = fixtures.load(name)
    payload = copy.deepcopy(fixture["compiler_payload"])
    payload["claims"][0]["sources"][0]["source_id"] = "$BLOCK:a sentence nothing in the reading says"
    _, graph = fixtures.compile_fixture(name, compiler_payload_override=payload)
    assert any(r.kind is CompilerRefusalKind.DANGLING_REFERENCE for r in graph.refusals)
