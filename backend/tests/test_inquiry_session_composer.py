"""
HARNESS-002D §6 — the answer, and the two things that must be true of every sentence in it.

It must name what it rests on, and it must not rest on anything that does not exist.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry_session import Synthesis, SynthesisSection
from backend.services.inquiry_session import coordinator, judge as J
from backend.services.inquiry_session.capability import LockedFixtureCapability
from backend.services.inquiry_session.composer import (CompositionRefused, DeterministicComposer,
                                                       ModelSynthesisComposer, PHASE_NOTE,
                                                       RENDERINGS, ROLE, SYSTEM_PROMPT,
                                                       build_prompt, request_for, validate)
from backend.tests.fixtures import inquiry_session_fixtures as F

AT = "2026-08-09T00:00:00+00:00"


def run(name, mode="consult", **bound):
    stages = F.stages_for(name, capability=LockedFixtureCapability(), judge=J.judge,
                          composer=bound.pop("composer", DeterministicComposer()), **bound)
    session = coordinator.new_session(prompt=F.prompt_for(name), refs=F.post_refs(name),
                                      mode=mode, now=AT)
    session = coordinator.begin(session, stages)
    if session.awaiting_user:
        request = coordinator.machine.from_dict(session.interaction).open_decision
        session = coordinator.resume(session, {
            "response_id": "r1", "session_id": session.session_id,
            "decision_id": request.decision_id, "expected_revision": session.revision,
            "kind": "select_option", "option_id": request.options[0].option_id, "at": AT}, stages)
    return session


# ── what the composer may see ────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_composer_never_receives_an_image_or_the_readings_prose(name):
    """The omission is the guarantee. A composer handed the pictures would perform a second,
    unrecorded visual reading; one handed the reading's prose would paraphrase it back, and a
    paraphrase reads exactly like a synthesis while resting on nothing that was decomposed."""
    session = run(name)
    request = request_for(session)

    assert not hasattr(request, "posts") and not hasattr(request, "images")
    body = build_prompt(request)
    for post in session.posts:
        assert post.image_ref not in body
        assert post.post_id not in body
    # The reading's own paragraph — the thing a composer would paraphrase back — is absent.
    # A CLAIM's text may legitimately echo the block it was atomized from; that text reached the
    # composer as a claim, with an id, a kind and a verdict, which is the whole difference.
    reading = (session.graph.get("reading") or {}).get("text") or ""
    assert reading, "the fixture has no reading, so this test would prove nothing"
    assert reading not in body
    # Nor the reading's receipt: which model read the pictures is not the composer's business.
    assert "scene_theorist" not in body


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_composer_sees_the_claims_verdicts_decisions_and_remainder(name):
    session = run(name)
    request = request_for(session)
    assert request.claims and request.verdicts and request.decisions
    assert len(request.verdicts) == len(session.graph["claims"])
    assert request.receipts and request.evidence == ()


# ── every section names what it rests on ─────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_section_declares_a_rendering_and_carries_its_references(name):
    session = run(name)
    assert session.synthesis is not None
    for section in session.synthesis.sections:
        assert section.status in RENDERINGS, section.status
        assert section.text.strip()
        assert (section.claim_refs or section.decision_refs or section.refusal_refs), \
            f"section {section.heading!r} rests on nothing it names"


@pytest.mark.parametrize("name", F.FIXTURES)
def test_no_section_renders_as_measured_and_none_cites_evidence(name):
    session = run(name)
    for section in session.synthesis.sections:
        assert section.status not in ("measured", "visible")
        assert section.evidence_refs == []


def test_a_measured_section_with_no_evidence_cannot_be_constructed():
    """The sentence this whole layer exists to make impossible."""
    with pytest.raises(ValidationError, match="cites no evidence"):
        SynthesisSection(section_id="sec_1", text="The bays are 3.2 m apart.", status="measured")


@pytest.mark.parametrize("name", F.FIXTURES)
def test_every_reference_in_the_answer_resolves_to_something_on_the_session(name):
    session = run(name)
    claims = {c["claim_id"] for c in session.graph["claims"]}
    decisions = {d.decision_id for d in coordinator.machine.from_dict(session.interaction).requests}
    remainder = set(session.synthesis.remainder_refs)
    refusals = {str(r.get("refusal_id")) for r in session.refusals}

    for section in session.synthesis.sections:
        assert set(section.claim_refs) <= claims
        assert set(section.decision_refs) <= decisions
        assert set(section.refusal_refs) <= (remainder | refusals)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_answer_says_on_its_face_that_phase_one_measured_nothing(name):
    session = run(name)
    assert session.synthesis.note == PHASE_NOTE
    assert "SIMULATION" in session.synthesis.note
    assert session.synthesis.provenance["measured_anything"] is False
    assert session.synthesis.provenance["simulated_capability"] is True


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_persons_decision_is_reported_as_a_decision_and_not_as_a_finding(name):
    session = run(name)
    section = next(s for s in session.synthesis.sections if s.decision_refs)
    assert section.status == "unresolved"
    assert section.claim_refs == []
    assert "not itself a finding" in section.text


@pytest.mark.parametrize("name", F.FIXTURES)
def test_interpretive_statements_are_still_allowed_to_be_intelligent(name):
    """Not flattened into apology. The rehearsal gate asks this directly."""
    session = run(name)
    reading = next(s for s in session.synthesis.sections if s.status == "interpretive")
    assert "not the weaker for it" in reading.text
    assert "sorry" not in reading.text.lower()


# ── an unknown reference refuses the whole composition ───────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_one_invented_reference_refuses_the_entire_composition(name):
    """Not the section — the composition. A synthesis in which one sentence points at nothing is a
    synthesis whose bindings cannot be trusted anywhere, and dropping the bad section would leave a
    plausible answer built by a producer just shown to invent references."""
    session = run(name)
    request = request_for(session)
    good = session.synthesis.sections[0]
    bad = SynthesisSection(section_id="sec_bad", text="A confident sentence.",
                           status="interpretive", claim_refs=["clm_never_existed"])
    with pytest.raises(CompositionRefused) as exc:
        validate([good, bad], request)
    assert "clm_never_existed" in exc.value.unknown[0]
    assert "the whole composition is refused" in str(exc.value).lower()


def test_the_refusal_names_every_bad_reference_at_once():
    """A producer is told all of what it invented rather than one thing per round trip."""
    session = run(F.FIXTURES[0])
    request = request_for(session)
    bad = SynthesisSection(section_id="sec_bad", text="x", status="interpretive",
                           claim_refs=["clm_a", "clm_b"], decision_refs=["dec_c"])
    with pytest.raises(CompositionRefused) as exc:
        validate([bad], request)
    assert len(exc.value.unknown) == 3


# ── the model composer, held to the same standard ────────────────────────────

class _Choice:
    def __init__(self, content, finish="stop"):
        self.message = type("M", (), {"content": content})()
        self.finish_reason = finish


class _Client:
    """A groq-shaped double. Returns whatever body it was given, once."""

    def __init__(self, body, finish="stop"):
        self._body = body
        self._finish = finish
        self.calls = 0
        self.chat = type("C", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return type("R", (), {"choices": [_Choice(self._body, self._finish)]})()


def test_an_unavailable_composer_writes_nothing_rather_than_handing_over_quietly():
    """Substituting the deterministic composer here and calling the result a model composition is
    structurally the same lie as calling a simulated receipt evidence, one layer up."""
    session = run(F.FIXTURES[0], composer=None) if False else run(F.FIXTURES[0])
    composer = ModelSynthesisComposer(client=None)
    composer._client_resolved = True
    assert composer.compose(session, at=AT) is None
    assert "unavailable" in composer.last_error


def test_the_model_composer_is_refused_for_a_reference_it_invented():
    import json
    session = run(F.FIXTURES[0])
    body = json.dumps({"sections": [{"heading": "What can be said", "text": "Something.",
                                     "status": "interpretive",
                                     "claim_refs": ["clm_the_model_made_this_up"]}]})
    composer = ModelSynthesisComposer(client=_Client(body))
    with pytest.raises(CompositionRefused):
        composer.compose(session, at=AT)


def test_the_model_composer_binds_real_refs_and_records_its_receipt():
    import json
    session = run(F.FIXTURES[0])
    claim = session.graph["claims"][0]["claim_id"]
    body = json.dumps({"sections": [{"heading": "What can be said", "text": "A reading.",
                                     "status": "interpretive", "claim_refs": [claim]}]})
    client = _Client(body)
    synthesis = ModelSynthesisComposer(client=client).compose(session, at=AT)

    assert client.calls == 1
    assert synthesis.sections[0].claim_refs == [claim]
    assert synthesis.provenance["composer"] == "model"
    assert synthesis.provenance["model"], "the receipt does not say what wrote it"
    assert synthesis.provenance["truncated"] is False
    assert synthesis.note == PHASE_NOTE


def test_a_truncated_model_answer_says_so_on_its_receipt():
    import json
    session = run(F.FIXTURES[0])
    claim = session.graph["claims"][0]["claim_id"]
    body = json.dumps({"sections": [{"heading": "h", "text": "t", "status": "interpretive",
                                     "claim_refs": [claim]}]})
    synthesis = ModelSynthesisComposer(client=_Client(body, finish="length")).compose(session, at=AT)
    assert synthesis.provenance["truncated"] is True
    assert synthesis.provenance["finish_reason"] == "length"


def test_an_unrecognised_rendering_is_corrected_downward_and_never_up():
    import json
    session = run(F.FIXTURES[0])
    claim = session.graph["claims"][0]["claim_id"]
    body = json.dumps({"sections": [{"heading": "h", "text": "t", "status": "definitive",
                                     "claim_refs": [claim]}]})
    synthesis = ModelSynthesisComposer(client=_Client(body)).compose(session, at=AT)
    assert synthesis.sections[0].status == "unresolved"


def test_the_model_composer_cannot_mint_a_measured_section_out_of_a_receipt():
    """It has no evidence ref to cite, and the schema refuses `measured` without one — so the
    strongest thing a model can say about a simulated receipt is still not a finding."""
    import json
    session = run(F.FIXTURES[0])
    claim = session.graph["claims"][0]["claim_id"]
    body = json.dumps({"sections": [{"heading": "h", "text": "The extent was measured.",
                                     "status": "measured", "claim_refs": [claim],
                                     "evidence_refs": []}]})
    with pytest.raises(ValidationError, match="cites no evidence"):
        ModelSynthesisComposer(client=_Client(body)).compose(session, at=AT)


def test_the_role_is_the_merged_one_and_its_ceiling_is_interpretive():
    from backend.services import role_registry
    assert role_registry.model_for(ROLE)
    assert "capability receipt is not evidence" in SYSTEM_PROMPT
    assert "never any image" in SYSTEM_PROMPT


# ── the whole chain ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_session_closes_complete_with_an_answer_rather_than_exhausted(name):
    session = run(name)
    assert session.state == "complete"
    assert session.synthesis is not None
    assert session.stop_reason


def test_a_deployment_with_no_composer_stops_at_exhausted_and_says_why(name="cross-image-comparison"):
    stages = F.stages_for(name, capability=LockedFixtureCapability(), judge=J.judge)
    session = coordinator.new_session(prompt=F.prompt_for(name), refs=F.post_refs(name),
                                      mode="auto", now=AT)
    session = coordinator.begin(session, stages)
    assert session.state == "exhausted"
    assert session.synthesis is None
    assert "Nothing was invented in its place" in session.stop_reason
