"""
CIRCUIT-002 A3 — the answer that resumes the loop, on STUB actuators (deterministic, no models).

A2 taught the loop to stop at `awaiting_answer` with a grounded question. Everything here is about
what may happen next, and the guards are the point rather than the plumbing:

  · an answer supplies a PARAM and never evidence — the curator's words, not their marks;
  · it routes to the exact question it answers, and unblocks through `resolve()`'s own check
    rather than through a re-implementation of it;
  · it RESUMES — the memory, the executed signatures and the closed doors all carry forward, so
    the loop does not redo its own first half, and the arc comes back as ONE receipt;
  · an answer that does not unblock is refused, never rounded up into a fabricated param, and
    never answered with the same question a second time.
"""
from __future__ import annotations

import json

from backend.services.director import loop_controller as lc
from backend.services.director import questions as qs
from backend.services.director.capabilities import Resource
from backend.services.director.execution import stub_registry
from backend.services.director.memory import PHRASE_FROM_ANSWER, build_memory
from backend.services.director.plan import Step
from backend.services.director.planner import Director


def _mem(**kw):
    return build_memory(image_ref="img_1", post_id="p1", **kw)


class _ScriptedPlanner:
    """Steps as a function of MEMORY (so re-planning stays grounded in evidence), recording every
    intention it was asked — the same shape A1's tests use, so 'the intention never changed' stays
    checkable across a resume too."""
    name = "scripted"
    last_notes = ()

    def __init__(self, fn):
        self._fn = fn
        self.calls = []

    def propose(self, intention, memory):
        self.calls.append(intention)
        return self._fn(memory)


def _ask_first(steps=(Step("presence_check", id="pc"),), memory=None, labels=None,
               registry=None, max_rounds=3):
    """Run to A2's stop: a step refused for a missing phrase, and the question that earns."""
    planner = _ScriptedPlanner(lambda m: list(steps))
    reg = registry if registry is not None else stub_registry()
    prior = lc.run_loop("is the cross there", memory or _mem(), reg,
                        director=Director(planner), max_rounds=max_rounds, labels=labels,
                        loop_id="L")
    assert prior.stop_reason == lc.AWAITING_ANSWER, prior.stop_reason
    return prior, planner, reg


# ── 1. the answer lands, the door opens, the loop carries on ──────────────────

def test_the_answer_unblocks_the_step_and_the_loop_carries_on():
    prior, planner, reg = _ask_first()
    assert reg["presence_check"].calls == []            # A2 stopped; nothing ran

    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: [Step("presence_check",
                                                                            id="pc")])),
                         max_rounds=3)

    # the previously-refused step RAN, on the curator's words
    assert len(reg["presence_check"].calls) == 1
    assert res.memory.phrase == "a cross"
    assert res.answer.accepted is True
    # and the loop then terminated honestly rather than spinning: a presence check produces a
    # READING, which is not evidence, so there is nothing to re-plan on.
    assert res.stop_reason == lc.STOP_NO_NEW_EVIDENCE
    assert res.question is None


def test_the_whole_arc_is_one_receipt():
    """A resumed loop that reported only its own rounds would hide where its evidence came from."""
    prior, _, reg = _ask_first()
    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: [Step("presence_check",
                                                                            id="pc")])))
    d = res.to_dict()

    assert [r["round"] for r in d["rounds"]] == list(range(len(res.rounds)))   # contiguous
    assert len(res.rounds) > len(prior.rounds)                                 # it EXTENDS
    assert d["rounds"][0] == prior.to_dict()["rounds"][0]                      # verbatim, not redone
    assert d["resumed_at_round"] == len(prior.rounds)                          # where the human came in
    assert d["answer"]["text"] == "a cross"
    assert d["answer"]["source"] == "curator"
    assert d["answer"]["actuator"] == "presence_check"
    assert d["answer"]["missing_param"] == "phrase"
    assert d["planner_calls"] > prior.planner_calls        # the count spans the arc, not the half


def test_the_intention_is_unchanged_across_the_resume():
    """A3 changes what the loop KNOWS, never what it was asked. Re-plan-on-results survives the
    human's intervention — an answer is a new fact, not a reworded prompt."""
    prior, first, reg = _ask_first()
    resumed_planner = _ScriptedPlanner(lambda m: [Step("presence_check", id="pc")])
    lc.resume_loop(prior, "a cross", reg, director=Director(resumed_planner))
    assert set(first.calls) == {"is the cross there"}
    assert set(resumed_planner.calls) == {"is the cross there"}


# ── 2. guard 1 — a param, never evidence ──────────────────────────────────────

def test_the_answer_changes_only_PHRASE_and_adds_no_evidence():
    """The one thing a param may supply is the curator's words. A region, mark, ground or percept
    arriving this way would be the fabrication the whole layer exists to prevent."""
    prior, _, reg = _ask_first()
    before = prior.memory.available()

    # a planner that proposes nothing on resume, so the ONLY difference to the packet is the answer
    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: [])))
    after = res.memory.available()

    assert after[Resource.PHRASE] == 1 and before[Resource.PHRASE] == 0
    for kind in (Resource.REGION, Resource.MARK, Resource.GROUND, Resource.PERCEPT,
                 Resource.READING, Resource.IMAGE):
        assert after[kind] == before[kind], kind


def test_the_injection_itself_cannot_carry_evidence():
    """Structural, one layer down: `with_phrase` touches two fields and both of them are words."""
    m = _mem()
    after = m.with_phrase("a cross", source=PHRASE_FROM_ANSWER)
    assert after.phrase == "a cross"
    assert (after.region_ids, after.mark_ids, after.ground_ids, after.percept_ids) == \
           (m.region_ids, m.mark_ids, m.ground_ids, m.percept_ids)
    assert m.phrase is None                       # frozen: the original packet is untouched


def test_a_blank_phrase_is_not_stored_on_the_packet():
    """An empty phrase satisfies no requirement, so storing one would put a claim on the packet
    that answers nothing — the emptiness has to stay visible."""
    assert _mem().with_phrase("   ").phrase is None


# ── 3. guard 3 — resume, not restart ──────────────────────────────────────────

def _two_step_arc():
    """rhythm progresses while presence_check is refused for want of a phrase — a refusal ALONGSIDE
    real work, so the first half has something the second half must not redo."""
    steps = [Step("rhythm", id="rh"), Step("presence_check", id="pc")]
    planner = _ScriptedPlanner(lambda m: list(steps))
    reg = stub_registry()
    prior = lc.run_loop("is the cross there", _mem(), reg,
                        director=Director(planner), max_rounds=4, loop_id="L")
    assert prior.stop_reason == lc.AWAITING_ANSWER
    return prior, planner, reg


def test_the_answered_door_re_opens_through_the_existing_reopen_path():
    """A3 adds no reopen machinery. The answer is a key like any other: `_door_still_closed`
    re-runs `resolve()`, the missing param is now on the packet, the door opens and the trace says
    so on the round where it happened."""
    prior, _, reg = _two_step_arc()
    assert not any(r.reopened for r in prior.rounds)          # shut for the whole first half

    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(
                             lambda m: [Step("rhythm", id="rh"), Step("presence_check", id="pc")])),
                         max_rounds=3)
    continuation = res.rounds[len(prior.rounds):]
    assert any(r.reopened for r in continuation), [r.to_dict() for r in continuation]
    assert len(reg["presence_check"].calls) == 1              # it got its chance, exactly once


def test_the_executed_signatures_carry_forward_so_finished_work_is_not_redone():
    """Resuming from memory alone would be a RESTART wearing the old run's evidence: the planner
    would re-propose what has already run and the loop, knowing nothing, would run it again."""
    prior, _, reg = _two_step_arc()
    ran_before = len(reg["rhythm"].calls)

    # the resumed planner proposes ONLY what has already run
    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: [Step("rhythm", id="rh")])),
                         max_rounds=3)

    assert res.stop_reason == lc.STOP_FIXED_POINT             # recognised as already done
    assert len(reg["rhythm"].calls) == ran_before             # and NOT run again
    assert res.rounds[-1].chain is None                       # nothing executed in that round
    assert res.rounds[-1].index == len(prior.rounds)          # numbering continued


def test_the_closed_doors_carry_forward_so_only_the_answered_one_re_opens():
    """The doors A1-FIX shut stay shut across the resume — except the one that was answered. A
    still-shut door is SUPPRESSED in the continuation, never refused a second time, which is only
    true if the closed-door list survived the pause."""
    steps = [Step("presence_check", id="pc"),
             Step("connect_marks", {"relation_role": "x"}, id="cm")]
    planner = _ScriptedPlanner(lambda m: list(steps))
    reg = stub_registry()
    prior = lc.run_loop("is the cross there", _mem(), reg,
                        director=Director(planner), max_rounds=3, loop_id="L")
    assert prior.stop_reason == lc.AWAITING_ANSWER
    shut = {c["actuator"] for c in prior.to_dict()["closed_doors"]}
    assert shut == {"presence_check", "connect_marks"}      # one param door, one evidence door

    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: list(steps))),
                         max_rounds=3)
    continuation = res.rounds[len(prior.rounds):]
    # the ANSWERED door opened and ran …
    assert any("presence_check" in s for r in continuation for s in r.reopened)
    assert len(reg["presence_check"].calls) == 1
    # … while the evidence door stayed shut, and was struck rather than re-refused
    assert any(x["actuator"] == "connect_marks" for r in continuation for x in r.suppressed)
    hits = sum(len([x for x in r.refused if x["actuator"] == "connect_marks"]) for r in res.rounds)
    assert hits == 1                                        # reached the gate once, in round 0
    assert reg["connect_marks"].calls == []


# ── 4. guard 4 — refused, never fabricated ────────────────────────────────────

def test_an_empty_answer_is_refused_and_no_param_is_fabricated():
    prior, _, reg = _ask_first()
    res = lc.resume_loop(prior, "   ", reg, director=Director(_ScriptedPlanner(lambda m: [])))

    assert res.answer.accepted is False
    assert "empty answer" in res.answer.why
    assert res.memory.phrase is None                  # nothing was filled in on the way out
    assert reg["presence_check"].calls == []          # and nothing ran on the strength of it
    # the loop is exactly where it was: still waiting, still holding the same question, because
    # nothing was supplied and pretending otherwise would cost the curator their turn.
    assert res.stop_reason == lc.AWAITING_ANSWER
    assert res.question is prior.question
    assert res.resume_state is prior.resume_state
    assert len(res.rounds) == len(prior.rounds)


def test_a_loop_that_asked_nothing_cannot_be_answered():
    """Attaching the curator's words to a question that was never put to them would be an
    invented exchange."""
    planner = _ScriptedPlanner(lambda m: [Step("rhythm", id="rh")])
    reg = stub_registry()
    finished = lc.run_loop("look", _mem(), reg, director=Director(planner), max_rounds=2)
    assert finished.stop_reason != lc.AWAITING_ANSWER
    assert finished.resume_state is None              # nothing to resume FROM

    res = lc.resume_loop(finished, "a cross", reg, director=Director(planner))
    assert res.answer.accepted is False
    assert "not waiting for an answer" in res.answer.why
    assert res.memory.phrase is None
    assert res.rounds == finished.rounds              # the arc is untouched


# ── 5. guard 5 — no re-ask ping-pong ──────────────────────────────────────────

class _Volunteer:
    """A planner that proposes nothing and volunteers a question about a param no answer can
    route — the pathological case the guard exists for."""
    name = "volunteer"
    last_notes = ()

    def __init__(self, missing_param):
        self.question = qs.Question(step_id="v", actuator="connect_marks",
                                    missing_param=missing_param, text="which relation?")

    def propose(self, intention, memory):
        return qs.Proposal(steps=[], question=self.question)


def test_an_answer_that_cannot_unblock_terminates_instead_of_asking_again():
    """Asking the same question twice would be the loop pretending it had not just heard the
    answer. It terminates with a reason that says exactly what happened."""
    reg = stub_registry()
    planner = _Volunteer("relation_role")
    prior = lc.run_loop("relate them", _mem(), reg, director=Director(planner), max_rounds=2)
    assert prior.stop_reason == lc.AWAITING_ANSWER

    res = lc.resume_loop(prior, "the echo", reg, director=Director(planner), max_rounds=3)
    assert res.stop_reason == lc.ANSWER_DID_NOT_UNBLOCK
    assert res.question is None                       # NOT asked again
    assert res.resume_state is None                   # and not answerable a third time
    assert res.answer.accepted is False
    assert "relation_role" in res.answer.why
    assert res.memory.phrase is None                  # no param was invented to proceed
    assert all(runner.calls == [] for runner in reg.values())


def test_the_same_question_cannot_be_asked_twice_once_the_param_is_on_the_packet():
    """The structural half of the guard: `question_for` returns None the moment the packet can
    answer it, so an answered door has nothing left to ask about."""
    prior, _, reg = _ask_first()
    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: [Step("presence_check",
                                                                            id="pc")])),
                         max_rounds=3)
    assert res.question is None
    assert res.stop_reason != lc.AWAITING_ANSWER
    # even a round that proposes the same blocked step again cannot re-earn the question
    again = lc.resume_loop(res, "a cross", reg, director=Director(_ScriptedPlanner(lambda m: [])))
    assert again.answer.accepted is False


# ── 6. guard 7 — attribution ──────────────────────────────────────────────────

def test_the_injected_phrase_is_marked_curator_supplied():
    """Both are the curator's words and neither is invented, but a phrase on the packet and a
    phrase answered mid-loop are not the same event — anything produced from one should be able to
    say which."""
    prior, _, reg = _ask_first()
    res = lc.resume_loop(prior, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: [Step("presence_check",
                                                                            id="pc")])))
    assert res.memory.phrase_source == PHRASE_FROM_ANSWER
    assert res.memory.summary()["phrase_source"] == PHRASE_FROM_ANSWER    # on every receipt
    # a packet that carried its phrase from the start is distinguishable from an answered one
    assert _mem(phrase="a cross").phrase_source is None


# ── 7. fork 3 — the paused loop survives being written down ───────────────────

def test_the_resume_state_round_trips_through_json_and_still_resumes():
    """In-memory resume is what A3 ships; persisting a paused loop is a store and a load on top of
    it, not a refactor. Pinned by resuming from a state that has been through JSON."""
    prior, _, reg = _ask_first()
    packed = json.dumps(prior.resume_state.to_dict())       # no live handles, no actuators
    restored = lc.ResumeState.from_dict(json.loads(packed))

    assert restored.intention == prior.resume_state.intention
    assert restored.memory.summary() == prior.resume_state.memory.summary()
    assert restored.executed_sigs == prior.resume_state.executed_sigs
    assert [r.index for r in restored.rounds] == [r.index for r in prior.rounds]
    assert restored.question.to_dict() == prior.question.to_dict()

    from dataclasses import replace
    revived = replace(prior, resume_state=restored, question=restored.question)
    res = lc.resume_loop(revived, "a cross", reg,
                         director=Director(_ScriptedPlanner(lambda m: [Step("presence_check",
                                                                            id="pc")])))
    assert res.answer.accepted is True
    assert len(reg["presence_check"].calls) == 1            # it ran, from a state read off disk
    assert res.memory.phrase == "a cross"


def test_a_first_run_carries_no_answer_and_no_resume_marker():
    """The non-resume call is the loop A1 shipped, unchanged."""
    res = lc.run_loop("look", _mem(), stub_registry(),
                      director=Director(_ScriptedPlanner(lambda m: [Step("rhythm", id="rh")])),
                      max_rounds=2)
    assert res.answer is None
    assert res.resumed_at_round is None
    assert res.to_dict()["resumable"] is False
