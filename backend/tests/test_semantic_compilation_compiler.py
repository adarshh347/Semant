"""
HARNESS-002A §4/§5 — the compiler turns prose into a graph, or refuses by name.

The two behaviours under test, and the difference between them is the design:

  AN INVENTION IS REFUSED. A kind, class, ground form or edge kind outside the closed sets is
  dropped and quoted verbatim, and whatever depended on it goes with it.
  A CONSTRAINT VIOLATION IS CORRECTED DOWNWARD AND RECORDED. A demand or a status is an aspiration
  rather than an instruction, and correcting one down can only weaken a claim.

No test here touches a network.
"""
from __future__ import annotations

import json

import pytest

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (CallTopology, CapabilityClass, ClaimKind,
                                                  ClaimStatus, CompilerRefusalKind, DecisionKind,
                                                  GroundForm, ImageRef, ImageScope, SourceType,
                                                  canonical)
from backend.services import role_registry
from backend.services.semantic_compilation import contracts
from backend.services.semantic_compilation.base import CompilationRequest, ReadingResult
from backend.services.semantic_compilation.compiler import (ROLE, FrozenSemanticCompiler,
                                                            MAX_CLAIMS, ModelSemanticCompiler,
                                                            build_prompt)
from backend.services.semantic_compilation.theorist import FrozenSceneTheorist

PROMPT = "How do these two interiors organise themselves, where do they part, and what could follow?"
INQUIRY = "inq_000000000001"
IMAGES = [ImageRef(post_id="p1", title="one"), ImageRef(post_id="p2", title="two")]

READING_PAYLOAD = {
    "reading": "Both gather their parts toward a centre, by different means.",
    "blocks": [{"kind": "part", "text": "a tall central void", "images": ["p1"]},
               {"kind": "comparison", "text": "one centres by height, the other by enclosure",
                "images": ["p1", "p2"]}],
}

FRAME = {
    "schema_version": "inquiry-frame.v1",
    "prompt": PROMPT,
    "mode": "explore",
    "requested_output": "comparison",
    "attentions": [{"term": "organise", "category": "organization"}],
    "epistemic_demands": [{"clause": "how do these two interiors organise themselves",
                           "term": "organise", "kind": "measurable", "why": "an arrangement"}],
    "unresolved_terms": [{"term": "part", "why": "a manner, not a thing"}],
    "semantic_remainder": [{"term": "composure", "why": "no instrument returns it"}],
    "proposed_actions": [], "provenance": {}, "inquiry_id": INQUIRY,
}


def reading():
    return FrozenSceneTheorist(READING_PAYLOAD).read(PROMPT, IMAGES, inquiry_id=INQUIRY)


def request(**kw) -> CompilationRequest:
    result: ReadingResult = kw.pop("reading_result", None) or reading()
    kw.setdefault("prompt", PROMPT)
    kw.setdefault("inquiry_id", INQUIRY)
    kw.setdefault("inquiry_frame", dict(FRAME))
    kw.setdefault("reading", result.reading)
    kw.setdefault("images", tuple(IMAGES))
    kw.setdefault("inherited_refusals", result.refusals)
    kw.setdefault("inherited_notes", result.notes)
    return CompilationRequest(**kw)


def claim_row(ref="c1", **kw):
    row = {"ref": ref, "text": "a tall central void is present", "kind": "entity",
           "sources": [{"type": "prompt", "source_id": "prompt", "text": "these two interiors"}]}
    row.update(kw)
    return row


def compile_payload(payload):
    return FrozenSemanticCompiler(payload).compile(request())


def kinds_of(graph):
    return [r.kind for r in graph.refusals]


class FakeClient:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests = []
        self.chat = self

    @property
    def completions(self):
        return self

    finish_reason = "stop"

    def create(self, **kwargs):
        self.requests.append(kwargs)
        payload = self._responses.pop(0) if self._responses else {}
        if isinstance(payload, BaseException):
            raise payload
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return type("C", (), {"choices": [type("M", (), {
            "message": type("X", (), {"content": text})(),
            "finish_reason": self.finish_reason})()]})()


class TruncatingClient(FakeClient):
    finish_reason = "length"


# ── what the compiler is shown ───────────────────────────────────────────────

def test_the_prompt_the_frame_and_the_reading_arrive_as_three_labelled_things():
    """Not one undifferentiated context. 'The user said this' and 'a VLM thought it saw this' are
    different warrants, and only the first is something the person can be held to."""
    built = build_prompt(request())
    assert PROMPT in built
    assert "PROMPT-ONLY FRAME — produced without seeing any image" in built
    assert "THE VISUAL READING" in built and "INTERPRETIVE, not evidence" in built
    assert built.index("PROMPT-ONLY FRAME") < built.index("THE VISUAL READING")


def test_the_compiler_is_not_handed_any_image_url():
    built = build_prompt(request(images=(ImageRef(post_id="p1", image_ref="https://x.invalid/1.jpg"),)))
    assert "https://x.invalid/1.jpg" not in built
    assert '"post_id": "p1"' in built


def test_every_closed_set_reaches_the_model_as_data():
    built = build_prompt(request())
    for name in ("claim_kinds", "claim_edge_kinds", "capability_classes", "ground_forms",
                 "image_scopes", "decision_kinds"):
        for value in contracts.closed_set(name):
            assert f'"{value}"' in built, f"{name}:{value} was not sent"


def test_the_frame_reaches_the_compiler_with_its_own_unresolved_terms_and_remainder():
    built = build_prompt(request())
    assert "a manner, not a thing" in built
    assert "composure" in built


# ── atomizing and anchoring ──────────────────────────────────────────────────

def test_a_claim_keeps_a_span_into_the_prompt_when_its_quote_is_really_there():
    graph = compile_payload({"claims": [claim_row()]})
    pointer = graph.claims[0].sources[0]
    assert pointer.source_type is SourceType.PROMPT
    assert pointer.span is not None
    assert PROMPT[pointer.span[0]:pointer.span[1]] == "these two interiors"


def test_a_span_the_compiler_invented_is_never_used_and_the_quote_is_flagged():
    """A model asked for character offsets invents them, and an invented span renders in a UI as a
    highlight over words the person did not write. The span is computed here or left unset."""
    graph = compile_payload({"claims": [claim_row(
        sources=[{"type": "prompt", "source_id": "prompt", "text": "a phrase nobody typed",
                  "span": [0, 9]}])]})
    assert graph.claims[0].sources[0].span is None
    assert "not there verbatim" in " ".join(graph.notes)


def test_a_claim_may_anchor_to_a_reading_block_by_id():
    block_id = reading().reading.blocks[0].block_id
    graph = compile_payload({"claims": [claim_row(
        sources=[{"type": "scene_reading", "source_id": block_id, "text": "a tall central void"}])]})
    assert graph.claims[0].sources[0].source_id == block_id
    assert graph.claims[0].sources[0].source_type is SourceType.SCENE_READING


def test_an_anchor_to_a_reading_block_that_is_not_in_the_reading_is_refused():
    graph = compile_payload({"claims": [claim_row(
        sources=[{"type": "scene_reading", "source_id": "rb_ghost", "text": "x"}])]})
    assert graph.claims == []
    assert CompilerRefusalKind.DANGLING_REFERENCE in kinds_of(graph)
    assert CompilerRefusalKind.UNANCHORED_CLAIM in kinds_of(graph)


def test_a_claim_with_no_pointer_and_no_parent_is_refused_as_unanchored():
    graph = compile_payload({"claims": [claim_row(sources=[])]})
    assert graph.claims == []
    refused = next(r for r in graph.refusals if r.kind is CompilerRefusalKind.UNANCHORED_CLAIM)
    assert "nobody said and nothing produced" in refused.why


def test_a_derived_claim_with_no_sources_becomes_a_compiler_inference_naming_its_parents():
    graph = compile_payload({"claims": [
        claim_row("c1"),
        claim_row("c2", text="the arrangement is centred", kind="spatial_relation",
                  sources=[], inferred_from=["c1"])]})
    derived = graph.claim(graph.claims[1].claim_id)
    assert derived.sources[0].source_type is SourceType.COMPILER_INFERENCE
    assert derived.inferred_from == [graph.claims[0].claim_id]


def test_an_inference_may_name_a_parent_the_model_listed_after_it():
    """Parents cannot be resolved on the first pass; a forward reference is legitimate."""
    graph = compile_payload({"claims": [
        claim_row("c1", text="the arrangement is centred", kind="spatial_relation", sources=[],
                  inferred_from=["c2"]),
        claim_row("c2")]})
    assert len(graph.claims) == 2
    assert graph.claims[0].inferred_from == [graph.claims[1].claim_id]


def test_an_inference_whose_only_parent_was_itself_refused_goes_with_it():
    """The fixpoint. A single pass would leave an inference standing on a claim that had been
    dropped, which is the assertion-wearing-inference's-clothes shape one remove away."""
    graph = compile_payload({"claims": [
        claim_row("c1", kind="vibe"),                       # refused: invented kind
        claim_row("c2", text="therefore it is centred", kind="spatial_relation", sources=[],
                  inferred_from=["c1"])]})
    assert graph.claims == []
    assert CompilerRefusalKind.UNKNOWN_CLAIM_KIND in kinds_of(graph)
    assert CompilerRefusalKind.INFERENCE_WITHOUT_PARENT in kinds_of(graph)


def test_two_identical_claims_collapse_into_one():
    graph = compile_payload({"claims": [claim_row("c1"), claim_row("c2")]})
    assert len(graph.claims) == 1


def test_a_claim_the_compiler_could_not_type_is_kept_as_unknown_and_not_dropped():
    graph = compile_payload({"claims": [claim_row(kind="unknown",
                                                  text="something about the light, unclear")]})
    assert graph.claims[0].claim_kind is ClaimKind.UNKNOWN


# ── inventions are refused by name ───────────────────────────────────────────

def test_an_invented_claim_kind_is_refused_verbatim_and_not_filed_under_unknown():
    """`unknown` means the compiler could not type it. Using it for an invented kind would hide a
    made-up vocabulary inside a legitimate one."""
    graph = compile_payload({"claims": [claim_row(kind="vibe_claim")]})
    assert graph.claims == []
    refused = next(r for r in graph.refusals if r.kind is CompilerRefusalKind.UNKNOWN_CLAIM_KIND)
    assert refused.what == "vibe_claim"


def test_an_invented_capability_class_is_dropped_and_named():
    graph = compile_payload({"claims": [claim_row()], "observables": [
        {"claim": "c1", "kind": "dominant extent",
         "capability_classes": ["extent", "bounding_box"]}]})
    assert graph.observables[0].capability_classes == [CapabilityClass.EXTENT]
    refused = next(r for r in graph.refusals
                   if r.kind is CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS)
    assert refused.what == "bounding_box"


def test_an_observable_left_with_no_declared_class_is_dropped():
    graph = compile_payload({"claims": [claim_row()], "observables": [
        {"claim": "c1", "kind": "vibe check", "capability_classes": ["vibes"]}]})
    assert graph.observables == []
    assert len([r for r in graph.refusals
                if r.kind is CompilerRefusalKind.UNKNOWN_CAPABILITY_CLASS]) == 2


def test_an_invented_ground_form_is_dropped_and_named():
    graph = compile_payload({"claims": [claim_row()], "observables": [
        {"claim": "c1", "kind": "extent", "capability_classes": ["extent"],
         "ground_forms": ["region", "voxel"]}]})
    assert graph.observables[0].ground_forms == [GroundForm.REGION]
    assert any(r.what == "voxel" for r in graph.refusals)


def test_an_invented_edge_kind_is_dropped_rather_than_read_as_support():
    """An unreadable rhetorical job silently turned into support is how an argument gains evidence
    nobody offered."""
    graph = compile_payload({"claims": [claim_row("c1"), claim_row("c2", text="a second claim")],
                             "edges": [{"kind": "vibes_with", "from": "c1", "to": "c2"}]})
    assert graph.claim_edges == []
    refused = next(r for r in graph.refusals if r.kind is CompilerRefusalKind.UNKNOWN_EDGE_KIND)
    assert refused.what == "vibes_with"


def test_an_edge_pointing_at_a_refused_claim_is_dropped():
    graph = compile_payload({"claims": [claim_row("c1"), claim_row("c2", kind="vibe")],
                             "edges": [{"kind": "supports", "from": "c1", "to": "c2"}]})
    assert graph.claim_edges == []
    assert CompilerRefusalKind.DANGLING_REFERENCE in kinds_of(graph)


# ── constraint violations are corrected downward and recorded ────────────────

def test_a_claim_the_compiler_called_measured_is_read_as_uncertain_and_recorded():
    graph = compile_payload({"claims": [claim_row(status="measured")]})
    assert graph.claims[0].status is ClaimStatus.UNCERTAIN
    refused = next(r for r in graph.refusals
                   if r.kind is CompilerRefusalKind.MEASURED_STATUS_CLAIMED)
    assert refused.what == "measured"


def test_an_interpretation_asking_for_a_measurement_is_corrected_to_interpretive():
    graph = compile_payload({"claims": [claim_row(kind="interpretation",
                                                  text="the interior reads as composed",
                                                  demand="measurable")]})
    assert graph.claims[0].epistemic_demand is DemandKind.INTERPRETIVE
    assert CompilerRefusalKind.MEASURED_STATUS_CLAIMED in kinds_of(graph)


def test_a_historical_claim_asking_for_a_measurement_is_corrected_to_sourced():
    graph = compile_payload({"claims": [claim_row(kind="historical_or_sourced",
                                                  text="it descends from an earlier convention",
                                                  demand="measurable")]})
    assert graph.claims[0].epistemic_demand is DemandKind.SOURCED


def test_a_generative_rule_is_corrected_to_imagined():
    graph = compile_payload({"claims": [claim_row(kind="generative_rule",
                                                  text="a third could centre by light alone",
                                                  demand="interpretive")]})
    assert graph.claims[0].epistemic_demand is DemandKind.IMAGINED


def test_a_comparison_scoped_to_one_image_is_widened_and_the_correction_recorded():
    graph = compile_payload({"claims": [claim_row(kind="comparison", text="the two differ",
                                                  image_scope="one_image")]})
    assert graph.claims[0].image_scope is ImageScope.CORPUS
    assert any("cheapest way to manufacture a finding" in r.why for r in graph.refusals)


def test_an_unknown_demand_is_read_as_interpretive_which_is_the_direction_with_no_overstatement():
    graph = compile_payload({"claims": [claim_row(demand="super_measurable")]})
    assert graph.claims[0].epistemic_demand is DemandKind.INTERPRETIVE
    refused = next(r for r in graph.refusals
                   if r.kind is CompilerRefusalKind.UNKNOWN_DEMAND_KIND)
    assert refused.what == "super_measurable"


def test_a_local_observation_and_a_corpus_tendency_stay_distinguishable():
    graph = compile_payload({"claims": [
        claim_row("c1", image_scope="one_image"),
        claim_row("c2", text="interiors of this kind tend to centre", kind="pattern_or_sequence",
                  image_scope="corpus")]})
    assert [c.image_scope for c in graph.claims] == [ImageScope.ONE_IMAGE, ImageScope.CORPUS]


# ── geometry ─────────────────────────────────────────────────────────────────

def test_a_claim_carrying_geometry_is_dropped_and_named():
    graph = compile_payload({"claims": [claim_row(bbox=[0, 0, 4, 4]), claim_row("c2",
                                                                                text="a second")]})
    assert [c.text for c in graph.claims] == ["a second"]
    assert CompilerRefusalKind.GEOMETRY_IN_A_READING in kinds_of(graph)


def test_an_observable_carrying_a_measurement_rather_than_requesting_one_is_dropped():
    graph = compile_payload({"claims": [claim_row()], "observables": [
        {"claim": "c1", "kind": "extent", "capability_classes": ["extent"], "confidence": 0.9}]})
    assert graph.observables == []
    assert any(r.what == "confidence" for r in graph.refusals)


# ── a source is not asked of an organ ────────────────────────────────────────

def test_an_observable_asking_an_image_capability_of_a_historical_claim_is_dropped():
    """Dropped rather than rewritten to `external_source`, which would be the compiler inventing a
    request nobody made."""
    graph = compile_payload({"claims": [claim_row(kind="historical_or_sourced",
                                                  text="it descends from an earlier convention",
                                                  demand="sourced")],
                             "observables": [{"claim": "c1", "kind": "dominant extent",
                                              "capability_classes": ["extent"]}]})
    assert graph.observables == []
    refused = next(r for r in graph.refusals
                   if r.kind is CompilerRefusalKind.SOURCED_CLAIM_ASKED_OF_AN_ORGAN)
    assert "outside the picture" in refused.why


def test_the_same_claim_asking_for_a_citation_is_kept():
    graph = compile_payload({"claims": [claim_row(kind="historical_or_sourced",
                                                  text="it descends from an earlier convention",
                                                  demand="sourced")],
                             "observables": [{"claim": "c1", "kind": "a documented attribution",
                                              "capability_classes": ["external_source"]}]})
    assert graph.observables[0].capability_classes == [CapabilityClass.EXTERNAL_SOURCE]


# ── the remainder ────────────────────────────────────────────────────────────

def test_a_remainder_the_compiler_also_asked_to_measure_is_dropped_and_the_request_stands():
    graph = compile_payload({
        "claims": [claim_row(subject="composure", demand="measurable")],
        "semantic_remainder": [{"term": "composure", "why": "unreachable"}]})
    assert graph.semantic_remainder == []
    assert graph.claims[0].epistemic_demand is DemandKind.MEASURABLE
    refused = next(r for r in graph.refusals
                   if r.kind is CompilerRefusalKind.REMAINDER_CLAIMED_MEASURABLE)
    assert refused.what == "composure"


def test_a_remainder_may_name_what_contributes_to_it_without_becoming_measurable():
    graph = compile_payload({
        "claims": [claim_row()],
        "semantic_remainder": [{"term": "composure", "why": "the measurements bear on it",
                                "contributing_capability_classes": ["extent", "depth"],
                                "claims": ["c1"]}]})
    item = graph.semantic_remainder[0]
    assert item.contributing_capability_classes == [CapabilityClass.EXTENT, CapabilityClass.DEPTH]
    assert item.claim_refs == [graph.claims[0].claim_id]


def test_interpretive_claims_with_no_remainder_produce_a_stated_gap_rather_than_a_filled_one():
    graph = compile_payload({"claims": [claim_row(kind="interpretation",
                                                  text="it reads as composed",
                                                  demand="interpretive")]})
    assert graph.semantic_remainder == []
    assert any("stated rather than filled in on its behalf" in n for n in graph.notes)


# ── alternatives and decisions ───────────────────────────────────────────────

def test_an_observable_may_offer_alternatives_without_raising_a_decision():
    graph = compile_payload({"claims": [claim_row()], "observables": [
        {"ref": "o1", "claim": "c1", "kind": "dominant extent",
         "capability_classes": ["extent"],
         "alternatives": [{"label": "measure the extent", "recommended": True},
                          {"label": "ask for a reading"}]}]})
    assert len(graph.observables[0].alternatives) == 2
    assert graph.decision_candidates == []
    assert any("not material" in n for n in graph.notes)


def test_a_decision_candidate_links_to_the_claim_and_observable_it_would_change():
    graph = compile_payload({"claims": [claim_row()], "observables": [
        {"ref": "o1", "claim": "c1", "kind": "dominant extent",
         "capability_classes": ["extent"]}], "decisions": [
        {"kind": "choose_operationalization", "question": "Measure it, or read it?",
         "why_now": "the two produce different evidence for the same claim",
         "affects": ["c1", "o1"],
         "options": [{"label": "measure", "recommended": True}, {"label": "read"}]}]})
    decision = graph.decision_candidates[0]
    assert decision.kind is DecisionKind.CHOOSE_OPERATIONALIZATION
    assert decision.affected_refs == [graph.claims[0].claim_id,
                                      graph.observables[0].observable_id]


def test_a_fork_with_one_branch_is_dropped_and_says_why():
    graph = compile_payload({"claims": [claim_row()], "decisions": [
        {"kind": "choose_operationalization", "question": "Measure it?",
         "why_now": "it changes the evidence", "options": [{"label": "measure"}]}]})
    assert graph.decision_candidates == []
    assert any("trains a person to click through" in n for n in graph.notes)


def test_a_decision_that_does_not_say_what_changes_is_dropped():
    graph = compile_payload({"claims": [claim_row()], "decisions": [
        {"kind": "resolve_ambiguous_term", "question": "Which sense of 'part'?", "why_now": "",
         "options": [{"label": "a"}, {"label": "b"}]}]})
    assert graph.decision_candidates == []
    assert any("not a reason to interrupt somebody" in n for n in graph.notes)


def test_a_repeated_option_does_not_become_a_fork_with_the_same_branch_twice():
    graph = compile_payload({"claims": [claim_row()], "decisions": [
        {"kind": "choose_operationalization", "question": "Measure it?",
         "why_now": "it changes the evidence",
         "options": [{"label": "measure"}, {"label": "measure"}]}]})
    assert graph.decision_candidates == []


# ── caps are stated ──────────────────────────────────────────────────────────

def test_more_claims_than_the_cap_are_trimmed_out_loud():
    rows = [claim_row(f"c{i}", text=f"claim number {i}") for i in range(MAX_CLAIMS + 5)]
    graph = compile_payload({"claims": rows})
    assert len(graph.claims) == MAX_CLAIMS
    assert any(f"kept the first {MAX_CLAIMS}" in n for n in graph.notes)


def test_more_observables_than_one_claim_may_carry_are_trimmed_out_loud():
    rows = [{"claim": "c1", "kind": f"observation {i}", "capability_classes": ["extent"]}
            for i in range(8)]
    graph = compile_payload({"claims": [claim_row()], "observables": rows})
    assert len(graph.observables) == 4
    assert any("the extras were not kept" in n for n in graph.notes)


# ── silence ──────────────────────────────────────────────────────────────────

def test_an_unparseable_payload_produces_an_empty_graph_that_says_so():
    graph = compile_payload("I could not do that")
    assert graph.claims == []
    assert graph.provenance.compiler_kind == "unavailable"
    assert graph.refusals[0].kind is CompilerRefusalKind.UNPARSEABLE_MODEL_OUTPUT
    assert graph.prompt == PROMPT


def test_an_unavailable_compiler_produces_an_empty_graph_and_invents_no_decomposition():
    """No rule-based fallback. Nothing rule-based can atomize prose into claims, so a fallback
    would have to invent a decomposition — the worst failure this module has."""
    compiler = ModelSemanticCompiler(client=None)
    compiler._client_resolved = True
    graph = compiler.compile(request())
    assert graph.claims == []
    assert graph.refusals[0].kind is CompilerRefusalKind.COMPILER_UNAVAILABLE
    assert graph.provenance.compiler.call_topology is CallTopology.UNAVAILABLE
    assert "nothing was invented in its place" in " ".join(graph.notes)


def test_a_live_call_that_fails_is_a_refusal_and_not_a_retry():
    compiler = ModelSemanticCompiler(client=FakeClient(RuntimeError("boom")))
    graph = compiler.compile(request())
    assert compiler.calls == 1
    assert graph.refusals[0].kind is CompilerRefusalKind.COMPILER_UNAVAILABLE
    assert "RuntimeError" in graph.refusals[0].why


def test_a_live_call_is_one_call_and_records_its_receipt():
    payload = {"claims": [claim_row()]}
    client = FakeClient(payload)
    compiler = ModelSemanticCompiler(client=client)
    graph = compiler.compile(request())
    assert compiler.calls == 1
    assert client.requests[0]["response_format"] == {"type": "json_object"}
    assert graph.provenance.compiler.role == ROLE
    assert graph.provenance.compiler.call_count == 1
    assert graph.provenance.compiler.parsed is True
    assert graph.provenance.compiler_kind == "model"


# ── provenance and replay ────────────────────────────────────────────────────

def test_a_graph_truncated_by_the_output_budget_says_it_is_a_prefix():
    """The failure worth naming: a compiler that ran out of budget and happened to close its JSON
    returns a thin decomposition that looks exactly like an honest one. `finish_reason` is the only
    thing that separates them, so it travels on the receipt whatever it says."""
    graph = ModelSemanticCompiler(client=TruncatingClient({"claims": [claim_row()]})).compile(
        request())
    notes = " ".join(graph.provenance.compiler.notes)
    assert "finish_reason: length" in notes
    assert "is a PREFIX of what it was writing" in notes
    assert graph.claims                      # what did arrive is kept


def test_a_graph_that_finished_normally_records_that_too():
    graph = ModelSemanticCompiler(client=FakeClient({"claims": [claim_row()]})).compile(request())
    notes = " ".join(graph.provenance.compiler.notes)
    assert "finish_reason: stop" in notes
    assert "PREFIX" not in notes


def test_the_reading_s_receipt_travels_onto_the_graph_beside_the_compiler_s():
    graph = compile_payload({"claims": [claim_row()]})
    assert graph.provenance.theorist is not None
    assert graph.provenance.theorist.role == "scene_theorist"
    assert graph.provenance.compiler.role == ROLE


def test_the_theorist_s_refusals_are_carried_onto_the_graph_rather_than_lost_at_the_seam():
    result = FrozenSceneTheorist(
        {"blocks": [{"kind": "part", "text": "a void", "bbox": [0, 0, 1, 1]}]}
    ).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    graph = FrozenSemanticCompiler({"claims": [claim_row()]}).compile(
        request(reading_result=result))
    assert CompilerRefusalKind.GEOMETRY_IN_A_READING in kinds_of(graph)


def test_the_whole_frame_is_embedded_verbatim():
    graph = compile_payload({"claims": [claim_row()]})
    assert graph.inquiry_frame == FRAME
    assert graph.provenance.inquiry_frame_schema_version == "inquiry-frame.v1"


def test_two_replays_of_one_frozen_output_are_byte_identical():
    payload = {"claims": [claim_row("c1"), claim_row("c2", text="a second claim",
                                                     kind="interpretation")],
               "edges": [{"kind": "supports", "from": "c1", "to": "c2"}],
               "observables": [{"claim": "c1", "kind": "extent",
                                "capability_classes": ["extent"]}]}
    a = canonical(FrozenSemanticCompiler(payload).compile(request(now="2026-08-09T00:00:00Z")))
    b = canonical(FrozenSemanticCompiler(payload).compile(request(now="2026-08-09T09:99:99Z")))
    assert a == b


def test_reordering_the_model_s_own_claims_does_not_renumber_the_graph():
    """The whole reason ids are content-derived. A model that reordered two claims it weighs
    equally would otherwise renumber both and every reference to them."""
    one = claim_row("c1")
    two = claim_row("c2", text="a second claim", kind="interpretation")
    forward = compile_payload({"claims": [one, two]})
    reversed_ = compile_payload({"claims": [two, one]})
    assert {c.claim_id for c in forward.claims} == {c.claim_id for c in reversed_.claims}


def test_the_compiler_role_is_a_thinker_and_is_not_the_theorist_s_binding():
    assert role_registry.get(ROLE).kind is role_registry.RoleKind.THINKER
    assert role_registry.model_for(ROLE) != role_registry.model_for("scene_theorist")


@pytest.mark.parametrize("payload", [{}, {"claims": []}, "junk"])
def test_no_compilation_ever_loses_the_prompt(payload):
    assert compile_payload(payload).prompt == PROMPT
