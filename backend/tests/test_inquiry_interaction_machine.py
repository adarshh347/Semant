"""
HARNESS-002B §3/§4 — the transitions, the steward's wall, and the session that resumes itself.

The claim this file checks is not "the machine works". It is that a session which paused and was
answered is THE SAME SESSION — same id, one revision on, its earlier events untouched, resuming the
phase it stopped in rather than a default — and that everything the machine did on its own is
visible in the record afterwards.
"""
from __future__ import annotations

import pytest

from backend.schemas.inquiry_interaction import (Actor, AmendmentRelation, DecisionKind, EventKind,
                                                 InteractionMode, ResponseKind, SessionState)
from backend.services.inquiry_interaction import fixtures as fx
from backend.services.inquiry_interaction import machine as m
from backend.services.inquiry_interaction import steward as stw
from backend.services.inquiry_interaction.candidates import read as read_candidate
from backend.services.inquiry_interaction.policy import DeliberationPolicy

STAMP = fx.STAMP
LATER = "2026-01-01T00:05:00+00:00"


def steward(mode=InteractionMode.CONSULT, formatter=None):
    return stw.DeliberationSteward(policy=DeliberationPolicy(mode=mode), formatter=formatter)


def session(mode=InteractionMode.CONSULT, graph=None):
    return m.open_session(session_id="inqs_1", mode=mode, at=STAMP,
                          graph=graph if graph is not None else fx.survey_graph())


def compiled(mode=InteractionMode.CONSULT, graph=None):
    return m.advance(session(mode, graph), SessionState.COMPILING, at=STAMP)


def answer(state, **over):
    base = {"response_id": "rsp_1", "session_id": state.session_id,
            "decision_id": state.open_decision_id, "expected_revision": state.revision,
            "kind": "select_option", "option_id": "opt_eastern", "at": LATER}
    base.update(over)
    return m.read_response(base)


# ── opening and phases ───────────────────────────────────────────────────────

def test_a_new_session_starts_at_framing_with_its_graph_hashed_and_untouched():
    graph = fx.survey_graph()
    state = m.open_session(session_id="inqs_1", mode=InteractionMode.STEP, at=STAMP, graph=graph)
    assert state.state is SessionState.FRAMING
    assert state.revision == 0
    assert state.graph.snapshot == graph
    assert state.graph.graph_hash.startswith("sig_")
    assert state.events[0].kind is EventKind.SESSION_OPENED


def test_a_session_reads_no_clock_and_refuses_to_be_opened_without_one():
    with pytest.raises(m.SessionMisuse, match="reads no clock"):
        m.open_session(session_id="inqs_1", mode=InteractionMode.AUTO, at="")


def test_a_phase_advance_appends_and_moves_one_revision():
    state = m.advance(session(), SessionState.COMPILING, at=STAMP)
    assert state.state is SessionState.COMPILING
    assert state.revision == 1
    assert state.events[-1].kind is EventKind.PHASE_ADVANCED


def test_a_session_cannot_advance_past_an_open_decision():
    """A phase advance that stepped over an open decision would answer it by walking away, and the
    trace would show a question asked and never answered while the run carried on regardless."""
    paused = m.offer(compiled(), [fx.survey_scope_candidate()], steward=steward(), at=STAMP)
    with pytest.raises(m.SessionMisuse, match="answer it by walking away"):
        m.advance(paused, SessionState.EXECUTING, at=LATER)
    with pytest.raises(m.SessionMisuse, match="not the same as one answered"):
        m.close(paused, SessionState.COMPLETE, at=LATER)
    with pytest.raises(m.SessionMisuse, match="looking at a question"):
        m.offer(paused, [fx.survey_cost_candidate()], steward=steward(), at=LATER)


# ── auto mode: settles a batch, records everything, waits for nobody ─────────

def test_auto_mode_settles_a_whole_batch_without_ever_opening_a_user_wait():
    state = m.offer(compiled(InteractionMode.AUTO), fx.survey_batch(),
                    steward=steward(InteractionMode.AUTO), at=STAMP)
    assert state.state is SessionState.COMPILING          # never entered awaiting_user
    assert state.pending == []
    assert [r.outcome for r in state.records] == [m.OUTCOME_AUTO_RESOLVED, m.OUTCOME_AUTO_RESOLVED,
                                                  m.OUTCOME_UNRESOLVED]
    assert all(r.actor is Actor.POLICY for r in state.records)


def test_an_auto_decision_carries_the_alternatives_it_did_not_take():
    """Auto mode means no interruption, not invisible agency. Without the alternatives and the
    reason, an automatic choice is indistinguishable from a fork that never existed."""
    state = m.offer(compiled(InteractionMode.AUTO), [fx.survey_scope_candidate()],
                    steward=steward(InteractionMode.AUTO), at=STAMP)
    record = state.records[0]
    assert record.chosen_option_id == "opt_eastern"
    assert record.alternatives == ["opt_district"]
    assert record.reason and "auto mode took it without asking" in record.reason
    # And the question it answered on the person's behalf is on the session, readable.
    assert state.requests[0].question.startswith("Compare the eastern wells")


def test_a_batch_costs_one_revision_however_many_candidates_it_settles():
    """`revision` counts turns. One that counted events would change under a client's feet for
    reasons the client has no way to observe."""
    before = compiled(InteractionMode.AUTO)
    after = m.offer(before, fx.survey_batch(), steward=steward(InteractionMode.AUTO), at=STAMP)
    assert after.revision == before.revision + 1
    assert len(after.events) > len(before.events) + 1


# ── step mode: every candidate, one at a time ────────────────────────────────

def test_step_mode_stops_at_every_candidate_in_the_batch_in_order():
    """The pending queue is what makes this a property of the session rather than of how the
    caller batched its offers: with one open slot, candidates two and three would be dropped at
    the first pause."""
    st = steward(InteractionMode.STEP)
    state = m.offer(compiled(InteractionMode.STEP), fx.survey_batch(), steward=st, at=STAMP)
    seen = []
    for i in range(3):
        assert state.state is SessionState.AWAITING_USER
        seen.append(state.open_decision.candidate["candidate_id"])
        state = m.respond(state, answer(state, response_id=f"rsp_{i}",
                                        kind="reject_all", option_id=""), steward=st, at=LATER)
    assert seen == ["cnd_survey_scope", "cnd_survey_cost", "cnd_survey_tie"]
    assert state.state is SessionState.COMPILING and state.pending == []


# ── consult mode and the resumed session ─────────────────────────────────────

def test_consult_pauses_at_a_material_fork_and_passes_the_deferrable_one_behind_it():
    state = m.offer(compiled(), fx.survey_batch(), steward=steward(), at=STAMP)
    assert state.state is SessionState.AWAITING_USER
    assert state.open_decision.kind is DecisionKind.CHOOSE_SCOPE
    assert state.paused_from is SessionState.COMPILING
    assert len(state.pending) == 3


def test_an_answer_resumes_the_same_session_and_increments_the_revision_once():
    """The whole point. Same id, one revision on, the earlier events untouched, and back in the
    phase it paused from rather than in a default."""
    st = steward()
    paused = m.offer(compiled(), [fx.survey_scope_candidate()], steward=st, at=STAMP)
    before_events = [e.model_dump(mode="json") for e in paused.events]

    resumed = m.respond(paused, answer(paused), steward=st, at=LATER)

    assert resumed.session_id == paused.session_id
    assert resumed.revision == paused.revision + 1
    assert resumed.state is SessionState.COMPILING       # the phase it paused from
    assert resumed.open_decision_id == "" and resumed.paused_from is None
    # append-only: every earlier event is byte-identical and still first
    assert [e.model_dump(mode="json") for e in resumed.events[:len(before_events)]] == before_events


def test_an_answer_records_who_chose_and_what_the_choice_changes():
    st = steward()
    paused = m.offer(compiled(), [fx.survey_scope_candidate()], steward=st, at=STAMP)
    resumed = m.respond(paused, answer(paused), steward=st, at=LATER)
    record = resumed.records[-1]
    assert record.actor is Actor.USER
    assert record.outcome == m.OUTCOME_ANSWERED
    assert record.chosen_option_id == "opt_eastern"
    assert record.response_id == "rsp_1"
    # the consequence the person was shown is what the record cites
    assert "speaks about the wells the claim names" in record.reason


def test_answering_the_first_fork_lets_the_queue_drain_to_the_next_pause():
    st = steward()
    state = m.offer(compiled(), fx.survey_batch(), steward=st, at=STAMP)
    state = m.respond(state, answer(state), steward=st, at=LATER)
    # the cost fork was passed with a record; the tie fork is the next pause
    assert state.state is SessionState.AWAITING_USER
    assert state.open_decision.candidate["candidate_id"] == "cnd_survey_tie"
    outcomes = [(r.outcome, r.actor.value) for r in state.records]
    assert outcomes == [("answered", "user"), ("auto_resolved", "policy")]


def test_a_deferred_fork_is_recorded_as_outstanding_rather_than_resolved():
    """`skip` and `reject_all` are different, and a composer that could not tell them apart would
    report a considered no as a postponement."""
    st = steward()
    state = m.offer(compiled(), [fx.survey_scope_candidate()], steward=st, at=STAMP)
    state = m.respond(state, answer(state, kind="skip", option_id=""), steward=st, at=LATER)
    assert state.records[-1].outcome == m.OUTCOME_DEFERRED
    assert state.deferred == [state.records[-1].decision_id]

    st2 = steward()
    other = m.offer(compiled(), [fx.survey_scope_candidate()], steward=st2, at=STAMP)
    other = m.respond(other, answer(other, kind="reject_all", option_id=""), steward=st2, at=LATER)
    assert other.records[-1].outcome == m.OUTCOME_REJECTED
    assert other.deferred == []


# ── amendments ───────────────────────────────────────────────────────────────

def test_a_free_text_amendment_creates_a_user_authored_successor_and_edits_nothing():
    """It never rewrites a model claim and never upgrades what anything is known by. Both halves:
    the graph is byte-identical afterwards, and the amendment carries no status."""
    graph = fx.survey_graph()
    st = steward()
    state = m.offer(m.advance(session(graph=graph), SessionState.COMPILING, at=STAMP),
                    [fx.survey_scope_candidate()], steward=st, at=STAMP)
    state = m.respond(state, answer(state, kind="amend", option_id="",
                                    free_text="the rise is in the two southern wells only",
                                    amendment_target="clm_nitrate",
                                    amendment_relation="disputes"), steward=st, at=LATER)

    amendment = state.amendments[-1]
    assert amendment.actor is Actor.USER
    assert amendment.target_ref == "clm_nitrate"
    assert amendment.text == "the rise is in the two southern wells only"
    assert amendment.relation is AmendmentRelation.DISPUTES
    # the graph it stands beside is unchanged, byte for byte
    assert state.graph.snapshot == graph == fx.survey_graph()
    assert state.graph.graph_hash == m.open_session(
        session_id="x", mode=InteractionMode.AUTO, at=STAMP, graph=fx.survey_graph()
    ).graph.graph_hash


def test_a_redirect_keeps_the_persons_words_verbatim_as_a_user_authored_object():
    """Otherwise the direction would live only inside a record's summary field."""
    st = steward()
    state = m.offer(compiled(), [fx.survey_scope_candidate()], steward=st, at=STAMP)
    state = m.respond(state, answer(state, kind="redirect", option_id="",
                                    free_text="neither — compare against the western wells"),
                      steward=st, at=LATER)
    amendment = state.amendments[-1]
    assert amendment.text == "neither — compare against the western wells"
    assert amendment.target_ref == state.records[-1].decision_id
    assert state.records[-1].amendment_ids == [amendment.amendment_id]


def test_a_users_direction_changes_goals_and_never_becomes_evidence():
    """THE LAW, checked on the object the person actually produces. There is no field on an
    amendment or a record where a kind of knowing could be written down."""
    st = steward()
    state = m.offer(compiled(), [fx.survey_scope_candidate()], steward=st, at=STAMP)
    state = m.respond(state, answer(state, kind="amend", option_id="",
                                    free_text="I am certain the nitrate rose",
                                    amendment_target="clm_nitrate"), steward=st, at=LATER)
    dumped = state.model_dump(mode="json")
    for word in ("measured", "visible", "epistemic_status", "usable_as_evidence"):
        assert word not in str(dumped["amendments"]), f"an amendment carries {word!r}"
    # and the changed ref is a GOAL-side change: the decision points at the graph object by id
    assert state.amendments[-1].target_ref == "clm_nitrate"
    assert state.graph.snapshot["claims"][0]["text"] == "nitrate concentration rose in the eastern wells"


# ── the steward and the formatter wall ───────────────────────────────────────

def test_the_deterministic_steward_keeps_the_producers_own_question():
    """This role words a fork; it does not restate it. Rewriting a supplied question would
    paraphrase the only sentence in the chain whose wording somebody deliberately chose."""
    candidate = read_candidate(fx.survey_scope_candidate())
    request = steward().draft(candidate, session_id="inqs_1", revision=1, at=STAMP)
    assert request.question == candidate.question
    assert request.why_now == candidate.why_now
    assert request.formatter == stw.DETERMINISTIC


def test_a_candidate_with_no_stated_consequence_still_gets_a_checkable_why_now():
    """The floor, not a hedge. `WHY_NOW` says what changes for that KIND of fork rather than
    'to be sure', which is what a system says when it has not looked."""
    raw = fx.survey_scope_candidate()
    raw.pop("why_now")
    request = steward().draft(read_candidate(raw), session_id="inqs_1", revision=1, at=STAMP)
    assert request.why_now == stw.WHY_NOW[DecisionKind.CHOOSE_SCOPE]
    assert "sure" not in request.why_now and "confirm" not in request.why_now


def test_the_affected_refs_are_the_union_of_the_candidates_and_its_options():
    """An option that changes an object the candidate did not list is exactly the case where a
    downstream reader would miss a consequence."""
    request = steward().draft(read_candidate(fx.survey_scope_candidate()),
                              session_id="inqs_1", revision=1, at=STAMP)
    assert set(request.affected_refs) == {"clm_nitrate", "obs_series"}


class _Formatter:
    """A model formatter stand-in. Whatever it is handed, it returns."""

    def __init__(self, returns, name="deliberation_steward"):
        self.returns = returns
        self.name = name

    def format(self, draft, *, candidate):
        return self.returns(draft) if callable(self.returns) else self.returns


def test_a_formatter_may_reword_a_question_and_its_options():
    """The negative control for every refusal below: prove the wall admits what it should, or
    'it refused' says nothing about what it refuses on."""
    st = steward(formatter=_Formatter(lambda d: {
        "question": "Which wells?",
        "options": [{"option_id": o.option_id, "label": o.label.upper()} for o in d.options]}))
    formed = st.form(read_candidate(fx.survey_scope_candidate()), session_id="inqs_1",
                     revision=1, at=STAMP)
    assert formed.refusals == ()
    assert formed.request.question == "Which wells?"
    assert formed.request.options[0].label == "EASTERN WELLS ONLY"
    assert formed.request.formatter == "deliberation_steward"
    # and the fields the policy reads came from the draft, untouched
    assert formed.request.options[0].recommended is True
    assert formed.request.options[0].reversible is True


def test_a_formatter_cannot_add_an_option():
    """An invented option is a capability nobody declared, offered to a person who cannot tell it
    from a real one."""
    st = steward(formatter=_Formatter(lambda d: {"options": [
        *[{"option_id": o.option_id} for o in d.options],
        {"option_id": "opt_invented", "label": "Model both", "consequence": "runs both"}]}))
    formed = st.form(read_candidate(fx.survey_scope_candidate()), session_id="inqs_1",
                     revision=1, at=STAMP)
    assert [r.code for r in formed.refusals] == [stw.REFUSAL_ADDED_OPTION]
    assert "opt_invented" in formed.refusals[0].what
    # and the deterministic request is what stands
    assert [o.option_id for o in formed.request.options] == ["opt_eastern", "opt_district"]
    assert formed.request.formatter == stw.DETERMINISTIC


def test_a_formatter_cannot_drop_an_option():
    st = steward(formatter=_Formatter(lambda d: {"options": [{"option_id": d.options[0].option_id}]}))
    formed = st.form(read_candidate(fx.survey_scope_candidate()), session_id="inqs_1",
                     revision=1, at=STAMP)
    assert [r.code for r in formed.refusals] == [stw.REFUSAL_DROPPED_OPTION]
    assert len(formed.request.options) == 2


def test_a_formatter_cannot_lose_an_affected_ref():
    st = steward(formatter=_Formatter({"affected_refs": ["clm_nitrate"]}))
    formed = st.form(read_candidate(fx.survey_scope_candidate()), session_id="inqs_1",
                     revision=1, at=STAMP)
    assert [r.code for r in formed.refusals] == [stw.REFUSAL_LOST_REF]
    assert set(formed.request.affected_refs) == {"clm_nitrate", "obs_series"}


def test_a_formatter_cannot_set_a_field_that_decides_whether_a_person_is_asked():
    """The one that would matter most: a formatter that could set `recommended` or `reversible`
    could talk the system out of asking."""
    st = steward(formatter=_Formatter(lambda d: {"options": [
        {"option_id": o.option_id, "recommended": True, "reversible": True} for o in d.options]}))
    formed = st.form(read_candidate(fx.survey_tie_candidate()), session_id="inqs_1",
                     revision=1, at=STAMP)
    assert [r.code for r in formed.refusals] == [stw.REFUSAL_ADDED_FIELD]
    assert "recommended" in formed.refusals[0].what


def test_a_formatter_cannot_assert_a_claim_a_capability_or_a_status():
    """Structural, not textual. There is no key it could put one in — a prose scan for forbidden
    words would be the weaker check that looks stronger."""
    for payload in ({"epistemic_status": "measured"}, {"capability": "locate_phrase"},
                    {"claims": ["clm_new"]}, {"evidence": {"mark_id": "m1"}},
                    {"blocking": False}, {"kind": "authorize_cost"}):
        formed = steward(formatter=_Formatter(payload)).form(
            read_candidate(fx.survey_scope_candidate()), session_id="inqs_1", revision=1, at=STAMP)
        assert [r.code for r in formed.refusals] == [stw.REFUSAL_ADDED_FIELD], payload
        assert formed.request.kind is DecisionKind.CHOOSE_SCOPE
        assert formed.request.blocking is True


def test_a_formatter_that_raises_does_not_take_the_session_down():
    def boom(_draft):
        raise RuntimeError("the model timed out")

    formed = steward(formatter=_Formatter(boom)).form(
        read_candidate(fx.survey_scope_candidate()), session_id="inqs_1", revision=1, at=STAMP)
    assert formed.refusals and "RuntimeError" in formed.refusals[0].why
    assert formed.request.question.startswith("Compare the eastern wells")


def test_a_formatter_refusal_lands_on_the_session_where_a_reader_will_find_it():
    st = steward(formatter=_Formatter({"options": [{"option_id": "opt_invented",
                                                    "label": "x", "consequence": "y"}]}))
    state = m.offer(compiled(), [fx.survey_scope_candidate()], steward=st, at=STAMP)
    assert [r.code for r in state.refusals] == [stw.REFUSAL_ADDED_OPTION]
    assert any(e.kind is EventKind.FORMATTER_REFUSED for e in state.events)
    assert state.state is SessionState.AWAITING_USER      # and the fork is still asked


def test_an_unreadable_candidate_is_refused_onto_the_session_and_the_rest_still_run():
    st = steward(InteractionMode.AUTO)
    state = m.offer(compiled(InteractionMode.AUTO),
                    [{"id": "cnd_bad", "kind": "not_a_kind"}, fx.survey_scope_candidate()],
                    steward=st, at=STAMP)
    assert [r.code for r in state.refusals] == ["candidate_kind_unknown"]
    assert any(e.kind is EventKind.CANDIDATE_REFUSED for e in state.events)
    assert [r.outcome for r in state.records] == [m.OUTCOME_AUTO_RESOLVED]
    assert state.pending == []
