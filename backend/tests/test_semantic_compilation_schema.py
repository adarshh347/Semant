"""
HARNESS-002A — the graph's own honesty guards, enforced rather than documented.

Every test here is a way a compiled graph could start asserting evidence it does not have. The
schema refuses each one at construction, so a parser bug downstream surfaces as a `ValidationError`
naming the rule rather than as a plausible-looking graph.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (CallTopology, CapabilityClass, ClaimEdge,
                                                  ClaimEdgeKind, ClaimKind, ClaimNode, ClaimStatus,
                                                  DecisionCandidate, DecisionKind, GraphProvenance,
                                                  GroundForm, ImageRef, ImageScope, ModelReceipt,
                                                  ObservableSpec, OperationalAlternative,
                                                  ReadingBlock, ReadingBlockKind, SceneReading,
                                                  SemanticInquiryGraph, SemanticRemainderItem,
                                                  SourcePointer, SourceType, canonical)

PROMPT = "How do these two arrangements organise their interiors, and what would a third look like?"
INQUIRY = "inq_000000000001"


def pointer(text: str = "these two arrangements",
            source_type: SourceType = SourceType.PROMPT) -> SourcePointer:
    return SourcePointer(source_type=source_type, source_id="prompt", text=text)


def claim(claim_id: str = "clm_a", *, kind: ClaimKind = ClaimKind.ENTITY,
          text: str = "an interior arrangement is present", **kw) -> ClaimNode:
    kw.setdefault("sources", [pointer()])
    return ClaimNode(claim_id=claim_id, text=text, claim_kind=kind, **kw)


def receipt(**kw) -> ModelReceipt:
    kw.setdefault("role", "scene_theorist")
    kw.setdefault("call_topology", CallTopology.REPLAY)
    return ModelReceipt(**kw)


def graph(**kw) -> SemanticInquiryGraph:
    kw.setdefault("graph_id", "sig_000000000001")
    kw.setdefault("inquiry_id", INQUIRY)
    kw.setdefault("prompt", PROMPT)
    kw.setdefault("provenance", GraphProvenance(producer="test", compiler_kind="replay"))
    return SemanticInquiryGraph(**kw)


# ── round trip ───────────────────────────────────────────────────────────────

def test_a_full_graph_round_trips_without_dropping_or_inventing_a_field():
    original = graph(
        image_refs=[ImageRef(post_id="p1", title="one", image_ref="https://x.invalid/1.jpg")],
        inquiry_frame={"schema_version": "inquiry-frame.v1", "prompt": PROMPT},
        reading=SceneReading(
            text="a long provisional reading",
            blocks=[ReadingBlock(block_id="rb_1", kind=ReadingBlockKind.ORGANIZATION,
                                 text="the parts gather toward a centre", image_refs=["p1"])],
            image_refs=[ImageRef(post_id="p1")],
            provenance=receipt(model="m", provider="groq", call_count=1, parsed=True)),
        claims=[claim("clm_a"),
                claim("clm_b", kind=ClaimKind.SPATIAL_RELATION,
                      text="the parts stand around the centre",
                      inferred_from=["clm_a"],
                      sources=[pointer("gathering", SourceType.SCENE_READING)])],
        claim_edges=[ClaimEdge(edge_id="cle_1", kind=ClaimEdgeKind.SUPPORTS,
                               from_claim="clm_a", to_claim="clm_b", why="the parts are the thing")],
        observables=[ObservableSpec(
            observable_id="obs_1", claim_id="clm_b", observable_kind="dominant extent",
            targets=["the central part"], capability_classes=[CapabilityClass.EXTENT],
            ground_forms=[GroundForm.REGION], success_when="an extent is returned",
            remains_interpretive="whether the arrangement reads as centred",
            alternatives=[OperationalAlternative(alternative_id="alt_1", label="measure the extent",
                                                 recommended=True),
                          OperationalAlternative(alternative_id="alt_2", label="ask for a reading")])],
        decision_candidates=[DecisionCandidate(
            decision_id="dec_1", kind=DecisionKind.CHOOSE_OPERATIONALIZATION,
            question="Measure the extent, or read the arrangement?",
            why_now="the two produce different evidence for the same claim",
            affected_refs=["clm_b", "obs_1"],
            options=[OperationalAlternative(alternative_id="alt_1", label="measure"),
                     OperationalAlternative(alternative_id="alt_2", label="read")])],
        semantic_remainder=[SemanticRemainderItem(
            term="composure", why="no instrument returns it",
            contributing_capability_classes=[CapabilityClass.EXTENT], claim_refs=["clm_b"])],
        notes=["nothing ran"])

    dumped = original.model_dump(mode="json", by_alias=True)
    assert SemanticInquiryGraph.model_validate(dumped).model_dump(mode="json", by_alias=True) == \
        dumped


def test_the_prompt_survives_byte_for_byte_including_its_whitespace():
    odd = "  Explore   the FOLD-level relations,\nand what could follow.  "
    assert graph(prompt=odd).prompt == odd


def test_a_graph_with_no_prompt_is_refused():
    with pytest.raises(ValidationError, match="carries no prompt"):
        graph(prompt="   ")


def test_an_undeclared_field_is_refused_rather_than_ignored():
    with pytest.raises(ValidationError):
        graph(claims=[], evidence=[{"mask_rle": {}}])


def test_canonical_drops_the_caller_handed_timestamps_and_keeps_every_id():
    g = graph(claims=[claim("clm_a")],
              provenance=GraphProvenance(producer="test", compiler_kind="replay",
                                         compiled_at="2026-08-09T00:00:00+00:00",
                                         theorist=receipt(requested_at="2026-08-09T00:00:00+00:00"),
                                         compiler=receipt(role="semantic_compiler",
                                                          requested_at="2026-08-09T00:00:01+00:00")))
    data = canonical(g)
    assert "compiled_at" not in data["provenance"]
    assert "requested_at" not in data["provenance"]["theorist"]
    assert "requested_at" not in data["provenance"]["compiler"]
    assert data["claims"][0]["claim_id"] == "clm_a"
    assert data["graph_id"] == "sig_000000000001"


# ── nothing starts measured ──────────────────────────────────────────────────

def test_a_claim_cannot_be_constructed_with_a_measured_status():
    with pytest.raises(ValidationError):
        claim(status="measured")
    with pytest.raises(ValidationError):
        claim(status="visible")


def test_the_only_statuses_a_compiled_claim_may_hold_are_the_three_a_thinker_can_reach():
    assert {s.value for s in ClaimStatus} == {"interpretive", "sourced", "uncertain"}


# ── every claim is anchored ──────────────────────────────────────────────────

def test_a_claim_with_no_source_pointer_is_refused():
    with pytest.raises(ValidationError, match="carries no source pointer"):
        ClaimNode(claim_id="clm_x", text="something is true", claim_kind=ClaimKind.ENTITY,
                  sources=[])


def test_a_compiler_inference_that_names_no_parent_is_refused():
    with pytest.raises(ValidationError, match="wearing an inference"):
        claim(sources=[pointer("derived", SourceType.COMPILER_INFERENCE)], inferred_from=[])


def test_a_compiler_inference_with_a_parent_is_accepted():
    node = claim(sources=[pointer("derived", SourceType.COMPILER_INFERENCE)],
                 inferred_from=["clm_parent"])
    assert node.inferred_from == ["clm_parent"]


def test_a_claim_with_no_text_is_refused():
    with pytest.raises(ValidationError, match="not a claim"):
        claim(text="   ")


# ── demand constraints ───────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", [ClaimKind.HISTORICAL_OR_SOURCED, ClaimKind.INTERPRETATION,
                                  ClaimKind.CAUSAL_HYPOTHESIS])
def test_the_three_kinds_that_may_never_ask_for_a_measurement(kind):
    with pytest.raises(ValidationError, match="demands 'measurable'"):
        claim(kind=kind, text="a claim of that kind", epistemic_demand=DemandKind.MEASURABLE)


def test_an_interpretation_may_still_ask_for_a_reading():
    node = claim(kind=ClaimKind.INTERPRETATION, text="the interior reads as composed",
                 epistemic_demand=DemandKind.INTERPRETIVE)
    assert node.epistemic_demand is DemandKind.INTERPRETIVE


def test_a_generative_rule_must_be_imagined_or_unresolved():
    for demand in (DemandKind.IMAGINED, DemandKind.UNRESOLVED):
        assert claim(kind=ClaimKind.GENERATIVE_RULE, text="a rule for a third arrangement",
                     epistemic_demand=demand).epistemic_demand is demand
    for demand in (DemandKind.MEASURABLE, DemandKind.INTERPRETIVE, DemandKind.SOURCED):
        with pytest.raises(ValidationError, match="must demand one of"):
            claim(kind=ClaimKind.GENERATIVE_RULE, text="a rule for a third arrangement",
                  epistemic_demand=demand)


def test_an_entity_may_ask_for_a_measurement_because_that_is_what_entities_are_for():
    assert claim(kind=ClaimKind.ENTITY, epistemic_demand=DemandKind.MEASURABLE).epistemic_demand \
        is DemandKind.MEASURABLE


def test_a_comparison_scoped_to_one_image_is_refused():
    with pytest.raises(ValidationError, match="single observation"):
        claim(kind=ClaimKind.COMPARISON, text="the two differ in their centring",
              image_scope=ImageScope.ONE_IMAGE)


def test_a_comparison_over_a_pair_or_the_corpus_is_accepted():
    for scope in (ImageScope.IMAGE_PAIR, ImageScope.CORPUS):
        assert claim(kind=ClaimKind.COMPARISON, text="the two differ", image_scope=scope)


# ── references resolve ───────────────────────────────────────────────────────

def test_an_edge_pointing_at_a_claim_that_is_not_here_is_refused():
    with pytest.raises(ValidationError, match="dangling reference|not a claim in this graph"):
        graph(claims=[claim("clm_a")],
              claim_edges=[ClaimEdge(edge_id="cle_1", kind=ClaimEdgeKind.SUPPORTS,
                                     from_claim="clm_a", to_claim="clm_ghost")])


def test_an_observable_serving_a_claim_that_is_not_here_is_refused():
    with pytest.raises(ValidationError, match="not a claim in this graph"):
        graph(claims=[claim("clm_a")],
              observables=[ObservableSpec(observable_id="obs_1", claim_id="clm_ghost",
                                          observable_kind="extent",
                                          capability_classes=[CapabilityClass.EXTENT])])


def test_an_inferred_from_pointing_nowhere_is_refused():
    with pytest.raises(ValidationError, match="not a claim in this graph"):
        graph(claims=[claim("clm_a", sources=[pointer("x", SourceType.COMPILER_INFERENCE)],
                            inferred_from=["clm_ghost"])])


def test_two_claims_sharing_an_id_are_refused():
    with pytest.raises(ValidationError, match="share an id"):
        graph(claims=[claim("clm_a"), claim("clm_a", text="a different sentence")])


def test_an_edge_from_a_claim_to_itself_is_refused():
    with pytest.raises(ValidationError, match="never bottoms out"):
        ClaimEdge(edge_id="cle_1", kind=ClaimEdgeKind.SUPPORTS,
                  from_claim="clm_a", to_claim="clm_a")


# ── a source is not asked of an organ ────────────────────────────────────────

def test_an_observable_on_a_sourced_claim_must_request_an_external_source():
    sourced = claim("clm_h", kind=ClaimKind.HISTORICAL_OR_SOURCED,
                    text="this arrangement descends from an earlier one",
                    epistemic_demand=DemandKind.SOURCED, status=ClaimStatus.SOURCED)
    with pytest.raises(ValidationError, match="cannot settle"):
        graph(claims=[sourced],
              observables=[ObservableSpec(observable_id="obs_1", claim_id="clm_h",
                                          observable_kind="dominant extent",
                                          capability_classes=[CapabilityClass.EXTENT])])
    ok = graph(claims=[sourced],
               observables=[ObservableSpec(observable_id="obs_1", claim_id="clm_h",
                                           observable_kind="a citation",
                                           capability_classes=[CapabilityClass.EXTERNAL_SOURCE])])
    assert ok.observables[0].capability_classes == [CapabilityClass.EXTERNAL_SOURCE]


# ── the remainder is not measurable ──────────────────────────────────────────

def test_a_remainder_term_that_a_claim_declares_measurable_is_refused():
    with pytest.raises(ValidationError, match="cannot both be true"):
        graph(claims=[claim("clm_a", subject="composure",
                            epistemic_demand=DemandKind.MEASURABLE)],
              semantic_remainder=[SemanticRemainderItem(term="Composure",
                                                        why="no instrument returns it")])


def test_a_remainder_term_that_an_observable_targets_for_measurement_is_refused():
    """The same contradiction one level down. A term nothing measures, with a measurement
    requested against it by name, is the promotion the remainder exists to refuse."""
    with pytest.raises(ValidationError, match="cannot both be true"):
        graph(claims=[claim("clm_a")],
              observables=[ObservableSpec(observable_id="obs_1", claim_id="clm_a",
                                          observable_kind="dominant extent",
                                          targets=["composure"],
                                          capability_classes=[CapabilityClass.EXTENT])],
              semantic_remainder=[SemanticRemainderItem(term="composure", why="unreachable")])


def test_a_remainder_term_a_reading_is_asked_about_is_allowed():
    """The negative control. `semantic_reading` and `external_source` settle no measurement, so
    asking a thinker about a remainder term is not the contradiction — it is the honest route."""
    g = graph(claims=[claim("clm_a")],
              observables=[ObservableSpec(observable_id="obs_1", claim_id="clm_a",
                                          observable_kind="a reading of the arrangement",
                                          targets=["composure"],
                                          capability_classes=[CapabilityClass.SEMANTIC_READING])],
              semantic_remainder=[SemanticRemainderItem(term="composure", why="unreachable")])
    assert g.semantic_remainder[0].term == "composure"


def test_a_remainder_may_name_the_measurements_that_contribute_to_it():
    g = graph(claims=[claim("clm_a")],
              semantic_remainder=[SemanticRemainderItem(
                  term="composure", why="the measurements bear on it and do not exhaust it",
                  contributing_capability_classes=[CapabilityClass.EXTENT, CapabilityClass.DEPTH])])
    assert g.semantic_remainder[0].contributing_capability_classes == \
        [CapabilityClass.EXTENT, CapabilityClass.DEPTH]


# ── the reading ──────────────────────────────────────────────────────────────

def test_a_scene_reading_cannot_claim_a_status_stronger_than_interpretive():
    with pytest.raises(ValidationError):
        SceneReading(text="x", status="measured", provenance=receipt())
    with pytest.raises(ValidationError):
        SceneReading(text="x", source="an_organ", provenance=receipt())


def test_a_reading_records_how_it_was_actually_obtained():
    reading = SceneReading(text="x", provenance=receipt(
        call_count=3, call_topology=CallTopology.PER_IMAGE_THEN_SYNTHESIS))
    assert reading.provenance.call_topology is CallTopology.PER_IMAGE_THEN_SYNTHESIS
    assert reading.provenance.call_count == 3


def test_an_unavailable_reading_says_so_rather_than_holding_a_default_topology():
    assert ModelReceipt(role="scene_theorist").call_topology is CallTopology.UNAVAILABLE


# ── observables and decisions ────────────────────────────────────────────────

def test_an_observable_that_names_no_capability_class_is_refused():
    with pytest.raises(ValidationError, match="requests no capability class"):
        ObservableSpec(observable_id="obs_1", claim_id="clm_a", observable_kind="something")


def test_an_observable_that_names_no_kind_is_refused():
    with pytest.raises(ValidationError, match="names no observable kind"):
        ObservableSpec(observable_id="obs_1", claim_id="clm_a", observable_kind="  ",
                       capability_classes=[CapabilityClass.EXTENT])


def test_a_decision_candidate_with_one_branch_is_refused():
    with pytest.raises(ValidationError, match="click through"):
        DecisionCandidate(decision_id="dec_1", kind=DecisionKind.CHOOSE_OPERATIONALIZATION,
                          question="which?", why_now="it changes the observable",
                          options=[OperationalAlternative(alternative_id="alt_1", label="one")])


def test_an_author_exclusive_confirmation_may_have_a_single_branch():
    """Confirming an act only a person may author is a yes/no, not a fork with two operationalizations."""
    d = DecisionCandidate(decision_id="dec_1", kind=DecisionKind.CONFIRM_AUTHOR_EXCLUSIVE_ACT,
                          question="Author this challenge yourself?",
                          why_now="a model may not author a challenge",
                          options=[OperationalAlternative(alternative_id="alt_1", label="author it")])
    assert d.options[0].label == "author it"


def test_a_decision_candidate_that_does_not_say_what_changes_is_refused():
    with pytest.raises(ValidationError, match="not a reason to interrupt"):
        DecisionCandidate(decision_id="dec_1", kind=DecisionKind.RESOLVE_AMBIGUOUS_TERM,
                          question="which?", why_now="  ",
                          options=[OperationalAlternative(alternative_id="alt_1", label="a"),
                                   OperationalAlternative(alternative_id="alt_2", label="b")])


# ── reading a graph ──────────────────────────────────────────────────────────

def test_the_helpers_read_what_is_there_and_claim_nothing_more():
    g = graph(claims=[claim("clm_a"),
                      claim("clm_b", kind=ClaimKind.INTERPRETATION, text="it reads as composed")],
              observables=[ObservableSpec(observable_id="obs_1", claim_id="clm_a",
                                          observable_kind="dominant extent",
                                          capability_classes=[CapabilityClass.EXTENT,
                                                              CapabilityClass.DEPTH])])
    assert g.claim("clm_b").claim_kind is ClaimKind.INTERPRETATION
    assert [c.claim_id for c in g.claims_of(ClaimKind.ENTITY)] == ["clm_a"]
    assert g.capability_classes() == ["depth", "extent"]
    assert [c.claim_id for c in g.investigable_claims()] == ["clm_a"]
    assert "none run" in g.summary()


def test_an_empty_graph_summarises_as_empty_rather_than_as_a_finding():
    assert graph().summary().startswith("0 claims")
