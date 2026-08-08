"""
HARNESS-001A — the model-backed framer, driven by a fake client.

No network. Every test here passes a fake whose reply is written by the test, which is the only
way to pin what happens when the model does the WRONG thing — and what happens then is the whole
value of the seam.

The five guards, one test each and then some:

  1. hallucinations are refused BY NAME, never filtered away while parsing;
  2. payload keys are clamped to the declared vocabulary, and the drop is recorded;
  3. exactly one call per `frame()` — no re-prompt loop;
  4. unavailable falls back to the deterministic framer AND SAYS SO in the provenance;
  5. an empty-but-valid model answer is kept, not overruled by a keyword plan.
"""
from __future__ import annotations

import json

import pytest

from backend.schemas.inquiry import DemandKind, InquiryMode, RefusalKind
from backend.services import role_registry
from backend.services.inquiry.model import ModelInquiryFramer

PROMPT = "Explore the fold relations between two sculptures and their sensuality."
CORPUS = {"post_ids": ["p1", "p2"], "titles": ["one", "two"]}


class FakeClient:
    """The smallest thing shaped like a Groq client. Records what it was called with."""

    def __init__(self, payload, *, raise_with=None):
        self._payload = payload
        self._raise = raise_with
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        body = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return type("R", (), {"choices": [type("C", (), {
            "message": type("M", (), {"content": body})()})()]})()


GOOD = {
    "mode": "explore",
    "requested_output": "comparison",
    "attentions": [{"term": "fold", "category": "drapery"},
                   {"term": "sensuality", "category": "reading"}],
    "epistemic_demands": [
        {"clause": "the fold relations between two sculptures", "term": "fold",
         "kind": "measurable", "why": "an extent an organ could put a mask on"},
        {"clause": "their sensuality", "term": "sensuality", "kind": "interpretive",
         "why": "a reading about the pictures"}],
    "proposed_actions": [
        {"type": "brush_field", "payload": {"field_role": "fold", "label": "fold"},
         "reason": "the user said fold"}],
    "unresolved_terms": [],
    "semantic_remainder": [{"term": "sensuality", "why": "not exhausted by fold geometry",
                            "contributing_measurements": ["fold"]}],
    "human_action_requested": [],
}


def _framer(payload, **kw):
    return ModelInquiryFramer(client=FakeClient(payload), **kw)


# ── the role ─────────────────────────────────────────────────────────────────

def test_the_role_is_declared_and_rebindable_like_every_other_thinker():
    role = role_registry.get("inquiry_framer")
    assert role is not None
    assert role.kind is role_registry.RoleKind.THINKER
    assert role.epistemic_ceiling.value == "interpretive"
    assert role.env_var == "SEMANT_ROLE_INQUIRY_FRAMER_MODEL"


def test_the_framer_asks_the_registry_rather_than_holding_a_literal():
    role_registry.bind("inquiry_framer", "some/other-model")
    try:
        assert ModelInquiryFramer().model == "some/other-model"
    finally:
        role_registry.unbind("inquiry_framer")


# ── the happy path ───────────────────────────────────────────────────────────

def test_a_well_formed_model_answer_becomes_a_valid_frame():
    frame = _framer(GOOD).frame(PROMPT, CORPUS)
    assert frame.provenance.framer_kind == "model"
    assert frame.provenance.role == "inquiry_framer"
    assert frame.action_types() == ["brush_field"]
    assert frame.proposed_actions[0]["source"] == "model_suggested"
    assert frame.requested_output == "comparison"


def test_the_attribution_sentence_is_built_here_and_never_taken_from_the_model():
    """A model asked to phrase its own attribution is one prompt-edit away from writing 'Semant
    detected', and the schema would accept the sentence."""
    payload = {**GOOD, "attentions": [{"term": "fold", "category": "drapery",
                                       "said": "Semant found folds in both images"}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert frame.attentions[0].said == "the user said “fold”"


def test_exactly_one_call_per_frame():
    framer = _framer(GOOD)
    framer.frame(PROMPT, CORPUS)
    assert framer.calls == 1
    assert len(framer._client.calls) == 1


def test_the_catalogue_sent_to_the_model_omits_the_act_it_may_not_author():
    framer = _framer(GOOD)
    framer.frame(PROMPT, CORPUS)
    sent = framer._client.calls[0]["messages"][1]["content"]
    # Listing an action and then forbidding it invites exactly one attempt.
    assert '"action": "challenge_percept"' not in sent
    assert '"action": "brush_field"' in sent


def test_the_prompt_sent_to_the_model_says_it_cannot_see_the_images():
    framer = _framer(GOOD)
    framer.frame(PROMPT, CORPUS)
    system = framer._client.calls[0]["messages"][0]["content"]
    assert "CANNOT SEE THE IMAGES" in system


# ── guard 1: hallucinations ──────────────────────────────────────────────────

def test_an_invented_action_is_refused_by_name_and_not_filtered_away():
    payload = {**GOOD, "proposed_actions": [
        {"type": "segment_folds", "payload": {"prompt": "folds"}},
        {"type": "brush_field", "payload": {"field_role": "fold", "label": "fold"}}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert frame.action_types() == ["brush_field"]
    refused = [r for r in frame.refusals if r.kind is RefusalKind.UNKNOWN_ACTION]
    assert refused and refused[0].what == "segment_folds"


def test_a_known_action_that_does_not_validate_is_refused_with_its_reasons():
    payload = {**GOOD, "proposed_actions": [{"type": "brush_field", "payload": {}}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert frame.proposed_actions == []
    refused = [r for r in frame.refusals if r.kind is RefusalKind.INVALID_ACTION]
    assert refused
    assert any("field_role" in d for d in refused[0].detail)


# ── guard 2: the clamp ───────────────────────────────────────────────────────

def test_a_model_trying_to_author_geometry_has_it_dropped_and_recorded():
    payload = {**GOOD, "proposed_actions": [{
        "type": "brush_field",
        "payload": {"field_role": "fold", "label": "fold", "mask_rle": "0" * 30,
                    "bbox": [1, 2, 3, 4], "confidence": 0.98, "region_id": "r_9"}}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert set(frame.proposed_actions[0]["payload"]) <= {"field_role", "label", "reason"}
    dropped = [r for r in frame.refusals if r.kind is RefusalKind.DISALLOWED_PARAMS]
    assert dropped
    assert dropped[0].detail == ["bbox", "confidence", "mask_rle", "region_id"]


# ── the human's veto ─────────────────────────────────────────────────────────

def test_a_model_authored_challenge_is_refused_and_the_request_is_kept():
    payload = {**GOOD, "proposed_actions": [{
        "type": "challenge_percept",
        "payload": {"percept_ref": "draft", "challenge_type": "overreach"},
        "reason": "the user asked for a counter-reading"}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert "challenge_percept" not in frame.action_types()
    refused = [r for r in frame.refusals if r.kind is RefusalKind.HUMAN_ACTION_REQUIRED]
    assert refused and refused[0].what == "challenge_percept"
    # The asking is not erased along with the act.
    assert refused[0].detail == ["the user asked for a counter-reading"]


def test_the_model_can_report_a_request_for_human_action_directly():
    payload = {**GOOD, "human_action_requested": [
        {"action": "challenge_percept", "why": "the user asked me to challenge the percept"}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert any(r.what == "challenge_percept" for r in frame.refusals)


# ── the epistemic wall ───────────────────────────────────────────────────────

def test_an_unknown_demand_kind_is_refused_rather_than_coerced_upward():
    """Guessing `interpretive` would silently downgrade a real measurement request; guessing
    `measurable` would do the far worse thing. So it is dropped and named."""
    payload = {**GOOD, "epistemic_demands": [
        {"clause": "their sensuality", "term": "sensuality", "kind": "felt", "why": "…"}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert frame.epistemic_demands == []
    assert any(r.kind is RefusalKind.UNKNOWN_DEMAND_KIND for r in frame.refusals)


def test_a_model_cannot_call_one_term_both_measurable_and_left_over():
    payload = {**GOOD,
               "epistemic_demands": [{"clause": "their sensuality", "term": "sensuality",
                                      "kind": "measurable", "why": "fold geometry gives it"}],
               "semantic_remainder": [{"term": "sensuality", "why": "…",
                                       "contributing_measurements": []}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    # The demand stands and the contradictory remainder is refused by name — rather than the
    # whole framing dying as a ValidationError somebody reads as a bug in the schema.
    assert frame.semantic_remainder == []
    assert any(r.what == "sensuality" for r in frame.refusals)


def test_the_frame_notes_an_interpretive_demand_with_no_remainder_rather_than_inventing_one():
    payload = {**GOOD, "semantic_remainder": []}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert frame.semantic_remainder == []
    assert any("no semantic remainder" in note for note in frame.notes)


def test_an_unknown_mode_is_refused_and_the_callers_mode_stands():
    payload = {**GOOD, "mode": "vibe"}
    frame = _framer(payload).frame(PROMPT, CORPUS, mode=InquiryMode.INSPECT)
    assert frame.mode is InquiryMode.INSPECT
    assert any(r.kind is RefusalKind.UNKNOWN_MODE for r in frame.refusals)


# ── guard 5: an empty answer is an answer ────────────────────────────────────

def test_a_model_that_safely_proposes_nothing_is_not_overruled_by_a_keyword_plan():
    """Falling back here would overrule the model's honest silence with a lexicon guess. The
    same rule `GroqPlanner` applies to an empty plan."""
    payload = {**GOOD, "proposed_actions": []}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert frame.proposed_actions == []
    assert frame.provenance.framer_kind == "model"
    assert any("NOT replaced by a keyword plan" in note for note in frame.notes)


# ── guard 4: unavailable, out loud ───────────────────────────────────────────

def test_no_client_falls_back_to_the_deterministic_framer_and_says_so():
    framer = ModelInquiryFramer(client=None)
    framer._client_resolved = True          # no key, no client, no network
    frame = framer.frame(PROMPT, CORPUS)
    assert frame.provenance.framer_kind == "model_fallback_deterministic"
    assert frame.provenance.model is None
    assert "unavailable" in frame.notes[0]
    assert frame.proposed_actions           # the deterministic framer did the work


def test_an_api_error_falls_back_and_names_the_failure_kind():
    framer = ModelInquiryFramer(client=FakeClient(GOOD, raise_with=TimeoutError("slow")))
    frame = framer.frame(PROMPT, CORPUS)
    assert frame.provenance.framer_kind == "model_fallback_deterministic"
    assert "TimeoutError" in frame.notes[0]


def test_unparseable_json_falls_back_rather_than_guessing():
    frame = _framer("not json at all").frame(PROMPT, CORPUS)
    assert frame.provenance.framer_kind == "model_fallback_deterministic"


def test_a_non_object_payload_yields_an_honest_empty_frame():
    frame = _framer([1, 2, 3]).frame(PROMPT, CORPUS)
    assert frame.proposed_actions == []
    assert any("non-object payload" in note for note in frame.notes)


# ── overflow ─────────────────────────────────────────────────────────────────

def test_an_overlong_attention_list_is_capped_and_the_cap_is_reported():
    payload = {**GOOD, "attentions": [{"term": f"w{i}", "category": "c"} for i in range(40)]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert len(frame.attentions) == 16
    assert any("kept the first 16" in note for note in frame.notes)


def test_the_frame_still_carries_no_geometry_after_a_hostile_answer():
    payload = {
        "mode": "explore",
        "attentions": [{"term": "fold", "category": "drapery",
                        "said": "I can see the mask clearly"}],
        "epistemic_demands": [{"clause": "the folds", "term": "fold", "kind": "measurable",
                               "why": "I measured them"}],
        "proposed_actions": [{"type": "brush_field",
                              "payload": {"field_role": "fold", "label": "fold",
                                          "mask_rle": "x" * 50, "confidence": 1.0}}],
        "semantic_remainder": [], "unresolved_terms": [], "human_action_requested": [],
    }
    frame = _framer(payload).frame(PROMPT, CORPUS)
    # No proposed act carries geometry…
    for action in frame.proposed_actions:
        assert not ({"mask_rle", "confidence"} & set(action["payload"]))
    # …and the VALUES never entered the frame at all. The key NAMES do survive, in the refusal,
    # and that is the point: dropping a key silently is how you fail to notice that a framer is
    # repeatedly trying to author geometry.
    serialised = frame.model_dump_json()
    assert "x" * 50 not in serialised
    assert any(r.kind is RefusalKind.DISALLOWED_PARAMS and "mask_rle" in r.detail
               for r in frame.refusals)
    assert frame.attentions[0].said == "the user said “fold”"


@pytest.mark.parametrize("kind", [DemandKind.MEASURABLE, DemandKind.INTERPRETIVE,
                                  DemandKind.SOURCED, DemandKind.IMAGINED,
                                  DemandKind.UNRESOLVED])
def test_every_declared_kind_round_trips(kind):
    payload = {**GOOD, "epistemic_demands": [
        {"clause": "a clause", "term": "t", "kind": kind.value, "why": "…"}]}
    frame = _framer(payload).frame(PROMPT, CORPUS)
    assert frame.epistemic_demands[0].kind is kind
