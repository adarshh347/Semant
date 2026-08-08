"""
HARNESS-001B §7 — the CONTROL VERTICAL REHEARSAL, step by step, plus the run's serialisation.

The directive names seven steps and this file walks them in order:

    1. intake a fixture `InquiryFrame` asking a bounded structural question
    2. resolve at least one Director preparation and one situated mission
    3. inhabit and perceive
    4. return evidence to the parent EvidenceGoal
    5. mark ONLY the supported criterion satisfied
    6. serialise and reload the `InquiryRun` with no field loss
    7. assert source posts byte-identical

The mission uses REAL pure-python organ code — `nestedness_organ` on mask geometry, through
`situated_agent.inhabit → perceive` — because a rehearsal driven by a fake simulator would prove
that the fake works. The Director half uses a fake, which the directive explicitly allows for the
fast test, and the real `DirectorAdapter` is exercised in its own section below.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from backend.services.epistemics import STATUS_KEY
from backend.services.inquiry_engine import capability as cap
from backend.services.inquiry_engine import engine as eng
from backend.services.inquiry_engine import fixtures
from backend.services.inquiry_engine.adapters import (DirectorAdapter, FakeDirectorAdapter,
                                                      SimulatorAdapter)
from backend.services.inquiry_engine.events import (EV_AGENT_PERCEIVED, EV_CAPABILITY_RESOLVED,
                                                    EV_EVIDENCE_RETURNED, EV_GOAL_CREATED,
                                                    EV_INQUIRY_FRAMED, EV_MISSION_DISPATCHED,
                                                    EV_RUN_STOPPED, EVENT_KINDS, InquiryRun)
from backend.services.inquiry_engine.goals import (KIND_EVIDENCE, KIND_INQUIRY, KIND_MISSION,
                                                   KIND_PREPARATION, STATUS_SATISFIED,
                                                   STATUS_UNRESOLVED)
from backend.services.movement_kernel import posts_fingerprint

STAMP = fixtures.STAMP

#: A Director suggestion of the shape `find_parts` yields, carrying its OWN stamped status. Used so
#: the Director half of the rehearsal returns something real to evaluate rather than a hole.
PARTS_SUGGESTION = {
    "id": None, "type": "region_mask", "producer": "find_parts",
    "epistemic_status": "measured", "label": "a part",
    "provenance": {"producer": "find_parts", "adapter": "fixture:find_parts"},
}


@pytest.fixture()
def world():
    return fixtures.control_world()


def _run(world, **kwargs):
    posts, graph, marks = world
    defaults = dict(posts=posts, now=STAMP, post_id="post_renaissance", region_id="finial",
                    graph=graph, proposed_marks=marks, simulator=SimulatorAdapter(),
                    director=FakeDirectorAdapter(suggestions=[PARTS_SUGGESTION], ran=True))
    defaults.update(kwargs)
    return eng.run_inquiry(fixtures.control_frame(), **defaults)


# ── 1. intake ────────────────────────────────────────────────────────────────

def test_step_1_the_fixture_frame_is_taken_in_and_the_prompt_is_carried_verbatim(world):
    run = _run(world)
    framed = run.events_of(EV_INQUIRY_FRAMED)
    assert len(framed) == 1
    assert framed[0].payload["prompt"] == fixtures.control_frame()["prompt"]
    inquiry = [g for g in run.goals if g.kind == KIND_INQUIRY][0]
    assert inquiry.prompt == fixtures.control_frame()["prompt"]


# ── 2. resolution: both scales ───────────────────────────────────────────────

def test_step_2_both_a_director_preparation_and_a_situated_mission_are_resolved(world):
    """The whole claim of the lane: one inquiry commissions global preparation AND local
    investigation. A run that only ever produced one of the two would not be evidence of a seam."""
    posts, graph, marks = world
    frame = dict(fixtures.control_frame())
    # The control frame is deliberately local; adding one global act makes the run cross both
    # scales without changing what the local half does.
    frame["proposed_actions"] = [*frame["proposed_actions"],
                                 {"type": "find_parts", "source": "user", "target": "image"}]
    run = eng.run_inquiry(frame, posts=posts, now=STAMP, post_id="post_renaissance",
                          region_id="finial", graph=graph, proposed_marks=marks,
                          simulator=SimulatorAdapter(),
                          director=FakeDirectorAdapter(suggestions=[PARTS_SUGGESTION], ran=True))

    kinds = {g.kind for g in run.goals}
    assert KIND_PREPARATION in kinds, "no Director preparation was commissioned"
    assert KIND_MISSION in kinds, "no situated mission was commissioned"

    resolved = run.events_of(EV_CAPABILITY_RESOLVED)
    outcomes = {e.payload["kind"] for e in resolved}
    assert cap.AGENT_MISSION in outcomes
    assert cap.DIRECTOR_PREPARATION in outcomes


def test_the_causal_chain_from_the_prompt_to_a_mark_is_walkable_in_one_history(world):
    """The point of the lane, stated as a walk: prompt → goal → resolution → dispatch → perception
    → evidence → verdict, with every hop carrying the parent it came from."""
    run = _run(world)
    inquiry = [g for g in run.goals if g.kind == KIND_INQUIRY][0]
    evidence_goal = next(g for g in run.goals
                         if g.kind == KIND_EVIDENCE and g.status == STATUS_SATISFIED)
    mission = next(g for g in run.goals if g.kind == KIND_MISSION)

    assert evidence_goal.parent_goal_id == inquiry.id
    assert mission.parent_goal_id == evidence_goal.id
    assert any(e.goal_id == mission.id and e.parent_goal_id == evidence_goal.id
               for e in run.events_of(EV_MISSION_DISPATCHED))
    assert any(e.goal_id == evidence_goal.id for e in run.events_of(EV_EVIDENCE_RETURNED))
    assert run.evidence_for(evidence_goal.id)


def test_every_event_carries_the_six_fields_that_make_it_causal(world):
    run = _run(world)
    assert run.events
    for event in run.events:
        assert event.run_id and event.step_id and event.actor and event.source and event.at
        assert event.kind in EVENT_KINDS
    # Sequence numbers are dense and ordered — an append-only log with holes is not one.
    assert [e.seq for e in run.events] == list(range(len(run.events)))


# ── 3. inhabit and perceive, with the real organ ─────────────────────────────

def test_step_3_a_real_pure_python_organ_measured_from_a_real_locus(world):
    run = _run(world)
    perceived = run.events_of(EV_AGENT_PERCEIVED)
    assert perceived, "no agent ever perceived"
    assert perceived[0].payload["memory_summary"]["node_id"] == "vm_post_renaissance:finial"
    assert perceived[0].payload["perceptions"] >= 1
    assert perceived[0].payload["posts_unchanged"] is True


# ── 4. evidence returns to the parent goal ───────────────────────────────────

def test_step_4_the_evidence_carries_the_organs_own_mark_and_the_organs_own_word(world):
    """No fabricated evidence: the item carries the typed mark and copies the status off it."""
    run = _run(world)
    marks = [e for e in run.evidence if e.kind == "organ_mark"]
    assert marks
    for item in marks:
        assert item.ref, "the evidence carries no typed object"
        assert item.epistemic_status == item.ref[STATUS_KEY]
        assert item.producer == item.ref["provenance"]["producer"]
        assert item.provenance["run_id"] == run.run_id


# ── 5. only the supported criterion is satisfied ─────────────────────────────

def test_step_5_the_supported_criterion_is_satisfied_and_the_unsupported_one_is_not(world):
    """The whole discipline in one assertion. The finial is INSIDE the sky, so nestedness measures
    and adjacency does not — and the run must say exactly that rather than rounding either way."""
    run = _run(world)
    by_need = {g.need: g for g in run.goals if g.kind == KIND_EVIDENCE}
    assert by_need["nestedness_here"].status == STATUS_SATISFIED
    assert by_need["adjacency_here"].status == STATUS_UNRESOLVED

    stopped = run.events_of(EV_RUN_STOPPED)[0]
    verdicts = {v["goal_id"]: v for v in stopped.payload["verdicts"]}
    unresolved = verdicts[by_need["adjacency_here"].id]
    assert unresolved["remaining"], "an unresolved goal must name what remains"
    assert "meets" in unresolved["clauses"][0]["why"]


def test_the_run_is_partially_answerable_and_never_falsely_answerable(world):
    run = _run(world)
    assert run.outcome == "partially_answerable"
    assert run.stop_reason in ("no_new_evidence", "capability_gap", "budget_exhausted")


# ── 6. serialise and reload with no field loss ───────────────────────────────

def test_step_6_the_full_event_history_round_trips_without_loss(world):
    run = _run(world)
    payload = run.to_dict()
    reloaded = InquiryRun.from_dict(payload)

    assert reloaded.to_dict() == payload
    assert reloaded.events == run.events
    assert reloaded.goals == run.goals
    assert reloaded.evidence == run.evidence
    assert reloaded.gaps == run.gaps
    assert (reloaded.outcome, reloaded.stop_reason, reloaded.rounds) == \
           (run.outcome, run.stop_reason, run.rounds)


def test_the_run_is_plain_json_and_acyclic(world):
    """`run_store.acyclic` exists because argue mode shipped a self-referential article. An
    `InquiryRun` is acyclic by construction, and this is the check that keeps it that way."""
    from backend.services.run_store import acyclic

    run = _run(world)
    payload = run.to_dict()
    assert json.loads(json.dumps(payload)) == payload

    breaks = []
    acyclic(payload, _breaks=breaks)
    assert breaks == [], f"the run had to be repaired to encode: {breaks}"


def test_a_replayed_run_is_identical_to_the_first_one(world):
    """Determinism. Nothing reads a clock, a uuid or a database, so the same frame over the same
    posts produces the same run — which is what makes every comparison in this lane a proof."""
    first = _run(world)
    second = _run(fixtures.control_world())

    def _stable(payload):
        # Organ mark ids are uuid-backed by `nestedness_organ.new_mark_id` and correctly so; the
        # rest of the run is content-derived and must not move.
        return json.dumps(payload, sort_keys=True, default=str)

    a, b = first.to_dict(), second.to_dict()
    for run_dict in (a, b):
        for item in run_dict["evidence"]:
            item["ref"].pop("id", None)
            item.pop("mark_id", None)
        for event in run_dict["events"]:
            event["payload"].pop("evidence_ids", None)
    assert _stable(a) == _stable(b)


# ── 7. the posts are byte-identical ──────────────────────────────────────────

def test_step_7_no_post_is_touched_by_a_run(world):
    posts, graph, marks = world
    before = posts_fingerprint(posts)
    eng.run_inquiry(fixtures.control_frame(), posts=posts, now=STAMP,
                    post_id="post_renaissance", region_id="finial", graph=graph,
                    proposed_marks=marks, simulator=SimulatorAdapter(),
                    director=FakeDirectorAdapter(suggestions=[PARTS_SUGGESTION], ran=True))
    assert posts_fingerprint(posts) == before


# ── the real Director adapter, on the real seams ─────────────────────────────

def test_the_real_director_adapter_goes_through_plan_resolve_and_execution_execute(world):
    """It is an adapter, not a second planner: a task naming an actuator becomes ONE `Step` that
    passes through the same `plan.resolve` every planner's output passes through."""
    from backend.services.director import execution as director_execution
    from backend.services.inquiry_engine.goals import PreparationTask

    posts, _graph, _marks = world
    adapter = DirectorAdapter(registry={
        "find_parts": director_execution.StubActuator("find_parts")})
    task = PreparationTask(id="pt_1", kind=KIND_PREPARATION, actuator="find_parts",
                           post_ids=("post_renaissance",))
    result = adapter.prepare(task, posts, run_id="r", inquiry_id="i", evidence_goal_id="eg",
                             now=STAMP)
    assert result.ran is True
    assert result.records and result.records[0]["actuator"] == "find_parts"
    assert result.posts_unchanged is True
    assert result.provenance["evidence_goal_id"] == "eg"
    assert result.provenance["inquiry_id"] == "i"


def test_a_task_naming_an_actuator_that_does_not_exist_is_refused_by_the_existing_gate(world):
    from backend.services.inquiry_engine.goals import PreparationTask

    posts, _graph, _marks = world
    result = DirectorAdapter().prepare(
        PreparationTask(id="pt_1", kind=KIND_PREPARATION, actuator="find_the_sublime",
                        post_ids=("post_renaissance",)),
        posts, run_id="r", inquiry_id="i", evidence_goal_id="eg", now=STAMP)
    assert result.ran is False
    assert any(r.get("reason") == "unknown_actuator" for r in result.refusals)


def test_the_local_proof_script_emits_one_json_run_for_each_committed_frame(tmp_path):
    """§8: `scripts/inquiry_goal_run.py` runs in fixture/replay mode by default and emits one JSON
    `InquiryRun`. Driven here so a broken script is a red test rather than a surprise in review."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "inquiry_goal_run",
        pathlib.Path(__file__).resolve().parents[2] / "scripts" / "inquiry_goal_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                        # type: ignore[union-attr]

    for name, expected in (("control", "partially_answerable"), ("fold", "partially_answerable")):
        out = tmp_path / f"{name}.json"
        assert module.main(["--frame", name, "--summary", "--out", str(out)]) == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["outcome"] == expected
        assert InquiryRun.from_dict(payload).to_dict() == payload


def test_the_local_proof_scripts_live_mode_reports_unavailable_rather_than_a_fake_green(tmp_path):
    """'unavailable infrastructure must produce an explicit event rather than a fake green run.'"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "inquiry_goal_run_live",
        pathlib.Path(__file__).resolve().parents[2] / "scripts" / "inquiry_goal_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                        # type: ignore[union-attr]

    out = tmp_path / "live.json"
    assert module.main(["--frame", "fold", "--live", "--summary", "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["outcome"] == "exhausted"
    assert payload["stop_reason"] == "execution_unavailable"
    # The gap is reported either way: a missing instrument is not contingent on the wiring.
    assert [g["need"] for g in payload["gaps"]] == ["fold_morphology"]


def test_with_no_registry_the_director_reports_unavailable_rather_than_a_fake_green(world):
    """The local-proof rule: unavailable infrastructure produces an explicit event, never a run
    that looks like it worked."""
    from backend.services.inquiry_engine.goals import PreparationTask

    posts, _graph, _marks = world
    result = DirectorAdapter().prepare(
        PreparationTask(id="pt_1", kind=KIND_PREPARATION, actuator="find_parts",
                        post_ids=("post_renaissance",)),
        posts, run_id="r", inquiry_id="i", evidence_goal_id="eg", now=STAMP)
    assert result.ran is False
    assert result.available is False
    assert any("no runner registered" in str(r.get("detail")) for r in result.refusals)
