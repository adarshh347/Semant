"""
HARNESS-002B §6 — the read projections, and the two things they must never become.

They must not become a second store: everything here is derived from the event log, so a UI reading
a projection is reading what actually happened rather than a copy that can drift from it.

And they must not become a second evidence log: nothing here holds a mark, a percept, a receipt or
a measurement. A projection that inlined a result would be a place where a result could be
described differently from where it is defined, and the difference would be unfalsifiable because
nobody would know which was the copy.
"""
from __future__ import annotations

import json

import pytest

from backend.schemas.inquiry_interaction import (STATUS_KEYS, InteractionMode, SessionState)
from backend.services.inquiry_interaction import fixtures as fx
from backend.services.inquiry_interaction import machine as m
from backend.services.inquiry_interaction import projections as pj
from backend.services.inquiry_interaction import steward as stw
from backend.services.inquiry_interaction.policy import DeliberationPolicy

STAMP = fx.STAMP
LATER = "2026-01-01T00:05:00+00:00"


def steward(mode=InteractionMode.CONSULT):
    return stw.DeliberationSteward(policy=DeliberationPolicy(mode=mode))


def opened(mode=InteractionMode.CONSULT, graph=None, candidates=None):
    st = steward(mode)
    state = m.open_session(session_id="inqs_1", mode=mode, at=STAMP,
                           graph=graph if graph is not None else fx.survey_graph())
    state = m.advance(state, SessionState.COMPILING, at=STAMP)
    return m.offer(state, candidates or fx.survey_batch(), steward=st, at=STAMP), st


def answer(state, **over):
    base = {"response_id": "rsp_1", "session_id": state.session_id,
            "decision_id": state.open_decision_id, "expected_revision": state.revision,
            "kind": "select_option", "option_id": "opt_eastern", "at": LATER}
    base.update(over)
    return m.read_response(base)


# ── status: what a client polls ──────────────────────────────────────────────

def test_status_says_answerable_only_when_it_is_both_waiting_and_naming_something():
    """Both conditions, not one. `run_store.is_answerable` holds the same rule for the Director's
    runs, because either alone is a session that would answer into a void."""
    state, st = opened()
    assert pj.status(state)["answerable"] is True
    assert pj.status(state)["open_decision_id"] == state.open_decision_id
    assert pj.status(state)["paused_from"] == "compiling"

    auto, _ = opened(InteractionMode.AUTO)
    assert pj.status(auto)["answerable"] is False
    assert pj.status(auto)["open_decision_id"] == ""


def test_status_carries_the_revision_a_client_must_send_back():
    state, st = opened()
    revision = pj.status(state)["revision"]
    resumed = m.respond(state, answer(state, expected_revision=revision), steward=st, at=LATER)
    assert pj.status(resumed)["revision"] == revision + 1


# ── why_paused: the projection that does real work ───────────────────────────

def test_why_paused_gives_the_fork_the_consequences_and_the_policys_own_reason():
    """'awaiting_user' is not an explanation. A person returning to a session needs the fork, what
    each way out of it changes, and why this system could not settle it alone."""
    state, _ = opened()
    why = pj.why_paused(state)
    assert why["kind"] == "choose_scope"
    assert why["question"].startswith("Compare the eastern wells")
    assert "eleven times" in why["why_now"]
    assert why["pause_class"] == "material"
    assert "consult mode pauses at a material fork" in why["policy_reason"]
    assert [o["option_id"] for o in why["options"]] == ["opt_eastern", "opt_district"]
    assert all(o["consequence"] for o in why["options"])


def test_why_paused_quotes_the_recorded_reason_rather_than_re_deriving_it():
    """Re-deriving would create a second explanation that could disagree with the one in the
    record — and the one people read is the projection."""
    state, _ = opened()
    event = next(e for e in reversed(state.events)
                 if e.decision_id == state.open_decision_id and e.reason)
    assert pj.why_paused(state)["policy_reason"] == event.reason


def test_why_paused_is_empty_rather_than_a_sentence_when_nothing_is_open():
    """A caller branches on presence instead of parsing prose."""
    auto, _ = opened(InteractionMode.AUTO)
    assert pj.why_paused(auto) == {}


# ── decisions: auto ones are here too ────────────────────────────────────────

def test_the_decision_log_shows_the_forks_nobody_was_asked_about():
    """The whole content of 'auto mode means no interruption, not invisible agency': if this list
    showed only what a person answered, an uninterrupted session would look like a session with no
    decisions in it."""
    auto, _ = opened(InteractionMode.AUTO)
    log = pj.decisions(auto)
    assert len(log) == 3
    assert all(d["settled"] for d in log)
    assert {d["by"] for d in log} == {"policy"}
    taken = next(d for d in log if d["chosen_option_id"] == "opt_eastern")
    assert taken["alternatives"] == ["opt_district"]
    assert taken["reason"]


def test_an_unresolved_fork_is_visible_as_unresolved_and_not_as_missing():
    """A tie auto mode declined to break is a recorded outcome, not the absence of one."""
    auto, _ = opened(InteractionMode.AUTO)
    tie = next(d for d in pj.decisions(auto) if d["outcome"] == "unresolved")
    assert tie["chosen_option_id"] == ""
    assert "list order" in tie["reason"]
    assert sorted(tie["alternatives"]) == ["opt_peak", "opt_seasonal"]


def test_the_decision_log_keeps_the_order_the_forks_arrived_in():
    """Nothing reorders by confidence, cost or recommendation strength — a queue sorted by any of
    those would make which fork a person sees first a judgement nobody declared."""
    auto, _ = opened(InteractionMode.AUTO)
    assert [d["kind"] for d in pj.decisions(auto)] == ["choose_scope", "authorize_cost",
                                                       "choose_operationalization"]


def test_an_open_fork_shows_as_unsettled_with_no_outcome_invented_for_it():
    state, _ = opened()
    first = pj.decisions(state)[0]
    assert first["settled"] is False
    assert first["outcome"] == "" and first["by"] == ""


# ── amendments and the causal arrow ──────────────────────────────────────────

def test_the_amendment_projection_has_no_field_a_kind_of_knowing_could_be_printed_from():
    """A UI rendering a person's opinion has nothing to read that would let it print a status
    beside it."""
    state, st = opened()
    state = m.respond(state, answer(state, kind="amend", option_id="",
                                    free_text="the rise is in the southern wells",
                                    amendment_target="clm_nitrate"), steward=st, at=LATER)
    row = pj.amendments(state)[0]
    assert row["actor"] == "user"
    assert row["target_ref"] == "clm_nitrate"
    assert not (set(row) & STATUS_KEYS), f"a status could be printed from {sorted(set(row) & STATUS_KEYS)}"


def test_a_users_answer_shows_which_graph_objects_it_changed():
    """The phase gate: 'the person's answer changes the remaining graph and that causal change is
    visible'. This is the projection that makes it drawable rather than asserted."""
    state, st = opened()
    state = m.respond(state, answer(state), steward=st, at=LATER)
    changed = pj.changed_refs(state)
    by_user = [c for c in changed if c["by"] == "user"]
    assert by_user, "the answer changed nothing visible"
    # `opt_eastern` declares it affects the series, so that is the ref the arrow points at
    assert {c["ref"] for c in by_user} == {"obs_series"}
    assert by_user[0]["option_id"] == "opt_eastern"


def test_no_settled_fork_that_took_no_road_out_of_itself_draws_a_causal_arrow():
    """Three outcomes settle a fork without choosing anything, and `rejected` is the one easiest to
    miss because unlike the other two it IS an answer: the person replied, and what they said was
    "none of these". An arrow would assert a downstream consequence for a decision whose whole
    content is that none was chosen."""
    auto, _ = opened(InteractionMode.AUTO)
    unresolved = next(d for d in pj.decisions(auto) if d["outcome"] == "unresolved")
    assert not [c for c in pj.changed_refs(auto)
                if c["decision_id"] == unresolved["decision_id"]]

    deferred, st = opened()
    deferred = m.respond(deferred, answer(deferred, kind="skip", option_id=""), steward=st,
                         at=LATER)
    assert deferred.deferred
    assert not [c for c in pj.changed_refs(deferred) if c["decision_id"] in deferred.deferred]

    rejected, st2 = opened()
    decision = rejected.open_decision_id
    rejected = m.respond(rejected, answer(rejected, kind="reject_all", option_id=""), steward=st2,
                         at=LATER)
    assert rejected.record_for(decision).outcome == m.OUTCOME_REJECTED
    assert not [c for c in pj.changed_refs(rejected) if c["decision_id"] == decision]


def test_a_chosen_option_still_draws_its_arrow():
    """The negative control for the three above. If `changed_refs` returned nothing at all, the
    absence of an arrow would say nothing about rejections in particular."""
    state, st = opened()
    state = m.respond(state, answer(state), steward=st, at=LATER)
    assert [c["ref"] for c in pj.changed_refs(state) if c["by"] == "user"] == ["obs_series"]


# ── the trace and the whole view ─────────────────────────────────────────────

def test_the_trace_is_thin_and_does_not_repeat_the_session_inside_itself():
    """A trace that inlined every payload would be the whole session twice, and the second copy is
    the one a reader would skim."""
    state, _ = opened()
    rows = pj.trace(state)
    assert [r["seq"] for r in rows] == list(range(len(rows)))
    assert all("payload" not in r for r in rows)
    assert {"kind", "actor", "reason", "refs", "revision"} <= set(rows[0])


def test_the_view_is_composed_of_the_projections_and_introduces_no_new_work():
    state, _ = opened()
    view = pj.view(state)
    assert view["status"] == pj.status(state)
    assert view["why_paused"] == pj.why_paused(state)
    assert view["decisions"] == pj.decisions(state)
    assert view["trace"] == pj.trace(state)


def test_the_whole_view_is_json_serialisable_as_it_stands():
    """Lane C consumes this shape. A view that needed an encoder would be a contract with a
    footnote."""
    state, st = opened()
    state = m.respond(state, answer(state, kind="redirect", option_id="",
                                    free_text="compare against the western wells"),
                      steward=st, at=LATER)
    blob = json.dumps(pj.view(state))
    assert json.loads(blob)["amendments"][0]["text"] == "compare against the western wells"


def test_a_formatter_refusal_reaches_the_view_where_a_reader_will_find_it():
    class _Oversteps:
        name = "a_model_formatter"

        def format(self, draft, *, candidate):
            return {"affected_refs": []}

    st = stw.DeliberationSteward(policy=DeliberationPolicy(mode=InteractionMode.CONSULT),
                                 formatter=_Oversteps())
    state = m.offer(m.advance(m.open_session(session_id="inqs_1", mode=InteractionMode.CONSULT,
                                             at=STAMP), SessionState.COMPILING, at=STAMP),
                    [fx.survey_scope_candidate()], steward=st, at=STAMP)
    codes = [r["code"] for r in pj.view(state)["refusals"]]
    assert codes == [stw.REFUSAL_LOST_REF]


def test_no_projection_holds_a_result_a_mark_or_a_measurement():
    """Structural. Interaction events sit BESIDE the goal engine's evidence log and reference its
    objects by id; a projection carrying one would be a second place a result is described."""
    state, st = opened()
    state = m.respond(state, answer(state), steward=st, at=LATER)
    blob = json.dumps(pj.view(state)).lower()
    for token in ("mask_rle", "mask_ref", "grounding_mark", "epistemic_status", "usable_as_evidence",
                  "measurement", "percept", "receipt_id"):
        assert token not in blob, f"a projection carries {token!r}"


def test_that_result_scan_can_actually_fail():
    """The negative control. A goal-engine evidence dict really does carry these tokens, so the
    scan above is looking for something that exists rather than for a spelling nothing uses."""
    from backend.services.inquiry_engine.events import Evidence
    blob = json.dumps(Evidence(id="ev", goal_id="g", kind="organ_mark",
                               epistemic_status="measured").to_dict()).lower()
    assert "epistemic_status" in blob


# ── projections are derived, never stored ────────────────────────────────────

def test_every_projection_is_a_function_of_the_replayed_event_log():
    """The claim that makes 'derived, not stored' checkable: a state rebuilt from nothing but its
    events produces the same view, so no projection depends on anything held beside the log."""
    state, st = opened()
    state = m.respond(state, answer(state), steward=st, at=LATER)
    assert pj.view(m.replay(state.events)) == pj.view(state)
