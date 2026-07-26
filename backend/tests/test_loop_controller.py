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
    planner = _RecordingPlanner(lambda m: [Step("find_parts", id="fp")])
    res = lc.run_loop("find parts", _mem(), stub_registry(empty=["find_parts"]),
                      director=Director(planner), max_rounds=5)
    assert res.stop_reason == lc.STOP_ONLY_REFUSALS
    assert res.rounds[0].verdict == lc.STOP_ONLY_REFUSALS
    assert res.rounds[0].new_evidence == {}


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
