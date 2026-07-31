"""
CIRCUIT-002 A1 — the loop controller, on STUB actuators (deterministic, no models).

What's pinned: a loop CONTINUES while it adds new evidence and CONVERGES at a fixed point; a
REFUSAL stops it immediately and the planner is never re-prompted to force the refused step
through; an empty round and a run-but-no-evidence round both terminate; the max_rounds backstop;
and every round is traced with its own lineage. The boundary — re-plan-on-results, never
re-prompt-around-a-refusal — is asserted directly (same intention every round; propose called once
per round; no extra call to route around a refusal).
"""
from __future__ import annotations

from backend.services.director import loop_controller as lc
from backend.services.director.capabilities import Resource
from backend.services.director.execution import stub_registry
from backend.services.director.memory import build_memory
from backend.services.director.planner import Director
from backend.services.director.plan import Step


def _mem(**kw):
    return build_memory(image_ref="img_1", post_id="p1", **kw)


class _RecordingPlanner:
    """A planner whose steps are a function of MEMORY (so re-planning is grounded in evidence),
    and which records every (intention) it was asked — so a test can prove it was called with the
    SAME intention each round and never re-prompted around a refusal."""
    name = "recording"
    last_notes = ()

    def __init__(self, fn):
        self._fn = fn
        self.calls = []          # the intention passed to each propose()

    def propose(self, intention, memory):
        self.calls.append(intention)
        return self._fn(memory)


def _director(fn):
    return Director(_RecordingPlanner(fn)), None


# ── 1. continue on new evidence, converge at a fixed point ─────────────────────

def test_continues_on_new_evidence_then_converges_at_fixed_point():
    def stages(memory):
        av = memory.available()
        if av[Resource.REGION] == 0:
            return [Step("find_parts", id="fp")]          # → region (+ mark)
        if av[Resource.PERCEPT] == 0:
            return [Step("compose_percept", id="cp")]     # needs a mark → percept
        return [Step("find_parts", id="fp")]              # already run → fixed point

    planner = _RecordingPlanner(stages)
    res = lc.run_loop("read the material", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=6, loop_id="L")

    verdicts = [(r.index, r.verdict) for r in res.rounds]
    assert verdicts == [(0, lc.CONTINUE), (1, lc.CONTINUE), (2, lc.STOP_FIXED_POINT)]
    assert res.stop_reason == lc.STOP_FIXED_POINT
    # each executing round left NEW evidence in memory
    assert res.rounds[0].new_evidence.get("region") == 1
    assert res.rounds[1].new_evidence.get("percept") == 1
    # the fixed-point round did NOT execute (no chain, nothing wasted)
    assert res.rounds[2].chain is None
    assert len(res.executed_rounds) == 2


# ── 2. a refusal stops immediately; the planner is NOT re-prompted around it ────

def test_refusal_stops_immediately_and_planner_is_not_re_prompted():
    # material_field needs a REGION; on a bare image nothing provides one, so resolve REFUSES it —
    # and the loop must NOT loop again to try to satisfy it.
    planner = _RecordingPlanner(lambda m: [Step("material_field", id="mf")])
    res = lc.run_loop("show the material", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=5)

    assert res.stop_reason == lc.STOP_ONLY_REFUSALS
    assert len(res.rounds) == 1                          # stopped on the first round
    # the refusal is reported, with its reason — never hidden
    refused = res.rounds[0].plan["refused"]
    assert any(r["actuator"] == "material_field" and r["reason"] == "missing_input" for r in refused)
    # THE BOUNDARY: the planner was asked exactly once — not re-prompted to force the refused step.
    assert planner.calls == ["show the material"]


def test_a_refusal_that_new_evidence_unblocks_is_re_planned_not_re_prompted():
    """The other side of the boundary: a step refused because its input was missing DOES come to
    run — but only because a real producer supplied that input (re-plan-on-results), never because
    the loop nagged the planner."""
    def stages(memory):
        # Always ask for BOTH; on round 0 material_field is refused (no region), on round 1 the
        # region find_parts produced makes it runnable. Same ask, evolved memory.
        return [Step("find_parts", id="fp"), Step("material_field", id="mf")]

    planner = _RecordingPlanner(stages)
    res = lc.run_loop("read the material", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=5)

    # round 0: find_parts runs, material_field is placed after it (resolve projects the region), so
    # both run in ONE round and the mark is produced. round 1: same steps, all already run → fixed.
    assert res.rounds[0].verdict == lc.CONTINUE
    ran0 = [(s["actuator"]) for s in res.rounds[0].plan["steps"]]
    assert ran0 == ["find_parts", "material_field"]
    assert res.stop_reason == lc.STOP_FIXED_POINT
    # every propose saw the SAME intention — memory changed, the prompt never did.
    assert set(planner.calls) == {"read the material"}


# ── 3. termination without new evidence ────────────────────────────────────────

def test_an_empty_round_terminates():
    # find_parts runs but honestly finds nothing → no evidence → stop (a real answer, not a retry).
    #
    # A1-FIX repointed the expected reason. It used to be STOP_ONLY_REFUSALS, whose value is
    # "only_refusals_or_empties" — a single constant covering two unrelated situations, back when
    # _decide() judged refusals. Refusals no longer reach _decide (closed-door suppression handles
    # them), so nothing was refused here and saying so would be false. STOP_ONLY_REFUSALS still
    # exists and is still reached, but now only where something actually WAS refused.
    planner = _RecordingPlanner(lambda m: [Step("find_parts", id="fp")])
    res = lc.run_loop("find parts", _mem(), stub_registry(empty=["find_parts"]),
                      director=Director(planner), max_rounds=5)
    assert res.stop_reason == lc.STOP_NO_NEW_EVIDENCE
    assert res.rounds[0].verdict == lc.STOP_NO_NEW_EVIDENCE
    assert res.rounds[0].new_evidence == {}
    assert res.rounds[0].refused == ()            # nothing was refused — that is the point


def test_a_round_that_runs_but_adds_no_evidence_terminates():
    # presence_check runs OK but produces a READING, not evidence — nothing to re-plan on.
    planner = _RecordingPlanner(lambda m: [Step("presence_check", id="pc")])
    res = lc.run_loop("is there an arch", _mem(phrase="arch"), stub_registry(),
                      director=Director(planner), max_rounds=5)
    assert res.stop_reason == lc.STOP_NO_NEW_EVIDENCE
    assert res.rounds[0].verdict == lc.STOP_NO_NEW_EVIDENCE
    assert res.rounds[0].new_evidence == {}


def test_nothing_planned_terminates():
    planner = _RecordingPlanner(lambda m: [])            # the planner proposes nothing
    res = lc.run_loop("mumble", _mem(), stub_registry(), director=Director(planner), max_rounds=5)
    assert res.stop_reason == lc.STOP_NOTHING_PLANNED
    assert len(res.rounds) == 1


# ── 4. the max_rounds backstop ─────────────────────────────────────────────────

def test_max_rounds_backstop():
    # a planner that always proposes a NEW distinct step producing evidence would never converge —
    # the backstop stops it.
    n = {"i": 0}

    def endless(memory):
        n["i"] += 1
        return [Step("find_parts", params={"round": n["i"]}, id=f"fp{n['i']}")]

    planner = _RecordingPlanner(endless)
    res = lc.run_loop("keep going", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=3)
    assert res.stop_reason == lc.STOP_MAX_ROUNDS
    assert len(res.executed_rounds) == 3
    assert all(r.verdict == lc.CONTINUE for r in res.rounds)


# ── 5. round-level provenance ──────────────────────────────────────────────────

def test_round_provenance_traces_every_round():
    planner = _RecordingPlanner(
        lambda m: [Step("find_parts", id="fp")] if m.available()[Resource.REGION] == 0
        else [Step("find_parts", id="fp")])
    res = lc.run_loop("read", _mem(), stub_registry(), director=Director(planner), max_rounds=4)
    d = res.to_dict()

    assert d["rounds_total"] == len(res.rounds)
    assert [r["round"] for r in d["rounds"]] == list(range(len(res.rounds)))
    # the executing round carries a full per-step chain lineage; the fixed-point round records the
    # plan and the verdict but no chain (it never ran).
    assert d["rounds"][0]["chain"] is not None
    assert d["rounds"][0]["chain"]["lineage"]
    assert d["rounds"][-1]["verdict"] == lc.STOP_FIXED_POINT
    assert d["rounds"][-1]["chain"] is None
    # weakest_link is the minimum across rounds, never a synthesized score.
    assert d["weakest_link"] == res.weakest_link


def test_weakest_link_is_the_minimum_across_rounds_or_none():
    # stub confidence is 0.9 by default → weakest_link 0.9; a confidence-less registry → None.
    planner = _RecordingPlanner(lambda m: [Step("find_parts", id="fp")]
                                if m.available()[Resource.REGION] == 0 else [Step("find_parts", id="fp")])
    res = lc.run_loop("read", _mem(), stub_registry(confidence=0.9),
                      director=Director(planner), max_rounds=3)
    assert res.weakest_link == 0.9

    planner2 = _RecordingPlanner(lambda m: [Step("find_parts", id="fp")]
                                 if m.available()[Resource.REGION] == 0 else [Step("find_parts", id="fp")])
    res2 = lc.run_loop("read", _mem(), stub_registry(confidence=None),
                       director=Director(planner2), max_rounds=3)
    assert res2.weakest_link is None


# ── 6. A1-FIX: closed-door refusal semantics ───────────────────────────────────
#
# The bug: _decide() returned CONTINUE on new evidence BEFORE looking at refusals, so a round that
# progressed AND had a step refused kept going and the planner was asked again about a world where
# that step had just been refused. Measured before the fix: connect_marks refused in round 0,
# planner called 3 times.
#
# The ruling: a refused step ends THAT BRANCH — struck from later rounds while its reason holds —
# while the loop itself continues on whatever else is legitimately moving. Shut the door, do not
# evacuate the building.

def _seeded(marks=0, regions=0):
    return build_memory(image_ref="img", post_id="p",
                        mark_ids=tuple(f"m{i}" for i in range(marks)),
                        region_ids=tuple(f"r{i}" for i in range(regions)))


def test_a_refused_step_is_suppressed_and_never_re_proposed():
    """The core of the fix. `rhythm` progresses while `connect_marks` is refused for want of a
    second mark; the planner keeps asking for it and it is struck every time.

    (`find_parts` would NOT serve here — it is `plural=True`, so the planner projects two marks
    from it and connect_marks is legitimately planned rather than refused.)"""
    planner = _RecordingPlanner(lambda m: [Step("rhythm", id="rh"),
                                           Step("connect_marks", {"relation_role": "x"}, id="cm")])
    res = lc.run_loop("look and relate", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=4)
    assert [r.index for r in res.rounds if r.refused] == [0]      # refused once, ever
    assert res.rounds[0].refused[0]["actuator"] == "connect_marks"
    for r in res.rounds[1:]:
        assert r.refused == ()
        assert "connect_marks" in [x["actuator"] for x in r.suppressed]


def test_one_impossible_step_does_not_kill_legitimate_continuations():
    """The other half of the ruling — the loop must NOT stop dead on a refusal."""
    planner = _RecordingPlanner(lambda m: [Step("rhythm", id="rh"),
                                           Step("connect_marks", {"relation_role": "x"}, id="cm")])
    res = lc.run_loop("look and relate", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=4)
    assert len(res.rounds) > 1                      # it kept going
    assert res.rounds[0].new_evidence               # because rhythm was still working


def test_a_door_re_opens_when_a_later_round_produces_the_prerequisite():
    """Found the key → the door opens. The case suppression must NOT block."""
    seen = {"n": 0}

    def script(m):
        seen["n"] += 1
        if seen["n"] == 1:
            # refused (only 1 mark projected) AND carries real work, so the loop survives the
            # round — a refusal alongside progress is the exact case the fix is about.
            return [Step("rhythm", id="rh"), Step("connect_marks", {"relation_role": "x"}, id="cm")]
        if seen["n"] == 2:
            return [Step("pressure_zone", id="pz")]                            # the second mark
        return [Step("connect_marks", {"relation_role": "x"}, id="cm2")]       # now legal

    res = lc.run_loop("relate", _mem(), stub_registry(),
                      director=Director(_RecordingPlanner(script)), max_rounds=6)
    assert any(r.reopened for r in res.rounds), [r.to_dict() for r in res.rounds]
    ran = [s["actuator"] for r in res.rounds if r.chain for s in r.chain["lineage"]]
    assert "connect_marks" in ran                   # it got its chance once two marks existed


def test_a_round_that_only_re_knocks_a_closed_door_stops():
    """No progress is possible, so the loop ends rather than spinning."""
    seen = {"n": 0}

    def script(m):
        seen["n"] += 1
        if seen["n"] == 1:
            return [Step("rhythm", id="rh"), Step("connect_marks", {"relation_role": "x"}, id="cm")]
        return [Step("connect_marks", {"relation_role": "x"}, id="cm")]   # only the shut door

    res = lc.run_loop("relate", _mem(), stub_registry(),
                      director=Director(_RecordingPlanner(script)), max_rounds=6)
    assert res.stop_reason == lc.STOP_ONLY_CLOSED_DOORS
    assert res.rounds[-1].suppressed
    assert res.rounds[-1].chain is None             # nothing executed — there was nothing to run


def test_the_bare_image_case_converges_without_re_asking_connect_marks():
    """The exact scenario that exposed the bug, now terminating cleanly."""
    planner = _RecordingPlanner(lambda m: [Step("rhythm", id="rh"),
                                           Step("connect_marks", {"relation_role": "x"}, id="cm")])
    res = lc.run_loop("look and relate", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=6)
    assert res.stop_reason in (lc.STOP_FIXED_POINT, lc.STOP_ONLY_CLOSED_DOORS)
    gate_hits = sum(len([x for x in r.refused if x["actuator"] == "connect_marks"])
                    for r in res.rounds)
    assert gate_hits == 1                           # reached the gate once, however often proposed


def test_the_receipt_reports_planner_calls_and_matches_the_rounds():
    """'The planner was not re-prompted around a refusal' must be readable from the receipt."""
    planner = _RecordingPlanner(lambda m: [Step("rhythm", id="rh"),
                                           Step("connect_marks", {"relation_role": "x"}, id="cm")])
    res = lc.run_loop("look and relate", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=4)
    d = res.to_dict()
    assert d["planner_calls"] == len(planner.calls)          # the receipt matches reality
    assert d["planner_calls"] == len(res.rounds)             # exactly one call per round
    assert d["suppressed_total"] >= 1
    assert any(c["actuator"] == "connect_marks" for c in d["closed_doors"])


def test_the_trace_names_which_doors_were_shut_and_why():
    planner = _RecordingPlanner(lambda m: [Step("connect_marks", {"relation_role": "x"}, id="cm")])
    res = lc.run_loop("relate", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=3)
    door = res.to_dict()["closed_doors"][0]
    assert door["actuator"] == "connect_marks"
    assert "2× mark" in door["detail"]
    assert door["round"] == 0


def test_a_permanently_closed_door_never_re_opens():
    """A missing PARAM is not a missing prerequisite — no amount of looking supplies a phrase."""
    seen = {"n": 0}

    def script(m):
        seen["n"] += 1
        if seen["n"] == 1:
            return [Step("rhythm", id="rh"), Step("presence_check", id="pc")]
        return [Step("pressure_zone", id="pz"), Step("presence_check", id="pc2")]

    res = lc.run_loop("is it there", _mem(), stub_registry(),
                      director=Director(_RecordingPlanner(script)), max_rounds=4)
    assert any(x["actuator"] == "presence_check" for r in res.rounds for x in r.refused)
    assert not any(r.reopened for r in res.rounds)          # evidence cannot supply a phrase


def test_suppression_happens_before_the_gate_not_after():
    """Structural: a suppressed step must never reach a plan's refusals a second time, which is
    only true if it was filtered BEFORE resolve() ever saw it."""
    planner = _RecordingPlanner(lambda m: [Step("rhythm", id="rh"),
                                           Step("connect_marks", {"relation_role": "x"}, id="cm")])
    res = lc.run_loop("look and relate", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=5)
    assert sum(len(r.refused) for r in res.rounds) == 1


# ── 7. A2: questions as an honest planner output ───────────────────────────────
#
# A1-FIX leaves a MISSING-PARAM door permanently shut: no amount of looking supplies a phrase the
# curator never gave. The loop knows exactly what it needs and that no further work will produce
# it — and used to say nothing. A2 makes it ask.
#
# The guard that matters is NOT that questions are well-formed. It is that an unanswered question
# yields a refusal and never a fabricated param: a planner that needs a phrase can always invent
# a plausible one, and every downstream receipt would look immaculate while answering a question
# nobody asked.

from backend.services.director import questions as qs


def _asks(steps, memory=None, labels=None, max_rounds=4):
    planner = _RecordingPlanner(lambda m: list(steps))
    return lc.run_loop("look", memory or _mem(), stub_registry(),
                       director=Director(planner), max_rounds=max_rounds, labels=labels)


def test_a_missing_param_door_emits_a_grounded_question():
    res = _asks([Step("rhythm", id="rh"), Step("presence_check", id="pc")],
                labels=["the wall", "the figure"])
    assert res.stop_reason == lc.AWAITING_ANSWER
    q = res.question
    assert q is not None and q.is_grounded
    assert q.actuator == "presence_check"
    assert q.missing_param == "phrase"
    assert q.options == ("the wall", "the figure")       # REAL options, from what was found
    assert "the wall" in q.text and "the figure" in q.text


def test_a_question_is_grounded_never_open_ended_fishing():
    """It names the act it is blocking and points at things that exist. 'What would you like me
    to look for?' moves the whole burden back to the curator while appearing helpful."""
    res = _asks([Step("presence_check", id="pc")], labels=["the drapery"])
    q = res.question
    assert "Is the named thing actually there?" in q.text   # names the blocked act
    assert "the drapery" in q.text                          # points at something real
    assert q.grounded_in["options_from"] == "labels"


def test_memory_that_supplies_the_param_asks_NOTHING():
    """A question about something already known teaches the curator to ignore questions."""
    res = _asks([Step("rhythm", id="rh"), Step("presence_check", id="pc")],
                memory=build_memory(image_ref="img", post_id="p", phrase="a cross"))
    assert res.question is None
    assert res.stop_reason != lc.AWAITING_ANSWER


def test_an_unanswered_question_refuses_and_NEVER_fabricates_the_param():
    """The load-bearing guard. A2 stops; it does not invent a phrase to proceed."""
    reg = stub_registry()
    res = lc.run_loop("look", _mem(), reg, director=Director(
        _RecordingPlanner(lambda m: [Step("presence_check", id="pc")])), max_rounds=4)
    assert res.stop_reason == lc.AWAITING_ANSWER
    assert reg["presence_check"].calls == []              # never ran
    # and the step still carries no phrase — nothing was filled in on the way out
    for r in res.rounds:
        for ref in r.refused:
            assert ref["reason"] == "missing_param"
    assert res.question.missing_param == "phrase"


def test_a_missing_EVIDENCE_door_is_not_question_able():
    """The loop has the models to produce marks. Asking would hand the curator a job the machine
    is standing next to."""
    res = _asks([Step("rhythm", id="rh"),
                 Step("connect_marks", {"relation_role": "x"}, id="cm")])
    assert res.question is None
    assert res.stop_reason != lc.AWAITING_ANSWER
    assert any(c["reason"] == "missing_input" for c in res.to_dict()["closed_doors"])


def test_is_question_able_admits_only_missing_param():
    assert qs.is_question_able("missing_param") is True
    assert qs.is_question_able("missing_input") is False
    assert qs.is_question_able("unknown_actuator") is False


def test_the_question_is_on_the_receipt_with_its_trigger():
    res = _asks([Step("presence_check", id="pc")], labels=["the wall"])
    d = res.to_dict()
    assert d["stop_reason"] == lc.AWAITING_ANSWER
    q = d["question"]
    assert q["actuator"] == "presence_check"            # which step
    assert q["missing_param"] == "phrase"               # which param
    assert q["options"] == ["the wall"]
    assert q["round"] == 0
    assert q["text"]


def test_a_productive_loop_is_never_interrupted_to_ask():
    """While work is still going, there is nothing to ask about."""
    seen = {"n": 0}

    def script(m):
        seen["n"] += 1
        return [Step("rhythm", id="rh")] if seen["n"] == 1 else [Step("pressure_zone", id="pz")]

    res = lc.run_loop("look", _mem(), stub_registry(),
                      director=Director(_RecordingPlanner(script)), max_rounds=2)
    assert res.question is None                          # it was busy, not stuck


def test_the_backstop_reports_running_out_of_rounds_not_a_question():
    """At max_rounds progress was still being made, so the closed door is not the blocker and
    saying 'I need you' would be false."""
    planner = _RecordingPlanner(lambda m: [Step("find_parts", id=f"fp{id(m)}"),
                                           Step("presence_check", id="pc")])
    res = lc.run_loop("look", _mem(), stub_registry(),
                      director=Director(planner), max_rounds=1)
    assert res.stop_reason == lc.STOP_MAX_ROUNDS
    assert res.question is None


def test_a_planner_may_volunteer_its_own_question():
    """A planner that already knows it is stuck can say so instead of proposing what it cannot
    run — and the loop honours that without deriving one."""
    q = qs.Question(step_id="s", actuator="presence_check", missing_param="phrase",
                    text="which one?", options=("a",))

    class Volunteer:
        name = "volunteer"

        def propose(self, intention, memory):
            return qs.Proposal(steps=[], question=q)

    res = lc.run_loop("look", _mem(), stub_registry(),
                      director=Director(Volunteer()), max_rounds=3)
    assert res.stop_reason == lc.AWAITING_ANSWER
    assert res.question is q


def test_a_bare_list_from_propose_still_works():
    """The pre-A2 contract is untouched — no existing planner has to change."""
    assert qs.Proposal.of([Step("rhythm", id="r")]).steps
    assert qs.Proposal.of([]).question is None
    assert qs.Proposal.of(None).steps == []


def test_options_are_never_invented_when_nothing_has_been_found():
    """An invented option is a suggestion with no basis that the curator cannot tell apart from
    a found one."""
    res = _asks([Step("presence_check", id="pc")])        # bare image, no labels
    q = res.question
    assert q.options == ()
    assert "nothing to point at" in q.text.lower()
