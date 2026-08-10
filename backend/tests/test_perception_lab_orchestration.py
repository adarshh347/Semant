"""
PERCEPTUAL-ORGANS-002 Lane D — the conductor end to end, and the guards it is not allowed to lose.

WHAT THIS FILE IS FOR, and how it differs from the four beside it. Those test one component
against hand-built inputs. This one runs the whole path — prompt or control, planner, resolver,
store, adapter, observer, response — and asserts the properties the phase gate asks about, which
are properties of the PATH and not of any one piece.

IT IS WRITTEN TO BE MUTATION-SENSITIVE, and the list below was CHECKED rather than asserted: each
guard was deleted in turn, the lab suite was run, and the tests named as the tell are the ones that
went red. A suite that only claims to be mutation-sensitive is a suite nobody ran backwards.

    delete the isolation check in `resolve`      -> 10 tests, six of them in other files
    delete `may_invoke` from `RunObserver`       -> 3, including the FIXTURE run's call counter
    weaken the execution-time `check_inputs`     -> 1: occlusion produces an artifact from no depth
    delete `AdapterRegistry`'s organ firewall    -> 1: a topology operation binds to extent
    give `replay()` a registry parameter         -> 2, on the signature and on the source
    return the before-digest when no probe ran   -> 1: "nobody looked" becomes a claim
    let one template name `label`                -> 6, the response tests and the unsayable set
    stop clearing `active` on deselect           -> 2: a removed id stays reachable
    add a `backend.database` import anywhere     -> the import-closure test

So the assertions are on counters, ids and closures rather than on flags in records: a broken lane
writes the same flags, immediately after doing the thing the flag denies.
"""
from __future__ import annotations

import ast
import inspect
import os
from collections import deque

import pytest

from backend.schemas.perception_lab import (EpistemicStatus, ExecutionIdentity, IdentityScope,
                                            InputRef, LabSource, LifecycleState, OrganFamily,
                                            ProducerKind, RefusalCode, ReviewVerdict, RunOutcome,
                                            SessionMode, StageState)
from backend.services.perception_lab import fakes, replay as RP
from backend.services.perception_lab.adapters import (AdapterError, AdapterOutcome,
                                                      AdapterRegistry, CallBudget, CancelToken,
                                                      NotRegistered, OrganCrossing)
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.observer import ReplayCannotInvoke
from backend.services.perception_lab.orchestrator import (ConfirmationRequired, NothingToRun,
                                                          PerceptionConductor)
from backend.services.perception_lab.planners import DirectCommand, ModelPlanner, RulesPlanner
from backend.services.perception_lab.response import TEMPLATE_FIELDS, TEMPLATES, UNSAYABLE
from backend.services.perception_lab.store import InMemoryLabStore

from .test_perception_lab_model_planner import FakeClient

SOURCE = LabSource(origin="post", post_id="post_finial", image_digest="sha256:9f1c0a5b7d2e4438",
                   natural_width=1600, natural_height=1200)


class TickingClock(FrozenClock):
    """Advances on every reading, so durations are non-zero and still deterministic."""

    def monotonic_ms(self) -> int:
        self.elapsed_ms += 7
        return self.elapsed_ms


def conductor(registry=None, **kw) -> PerceptionConductor:
    return PerceptionConductor(store=InMemoryLabStore(),
                               registry=registry if registry is not None else fakes.full_registry(),
                               clock=TickingClock(), ids=SequentialIds(), **kw)


def two_extents(c: PerceptionConductor):
    """The supported way into a topology question: measure extents, choose them, switch organ."""
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    first = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    second = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    machine.select(first.run.artifact_ids[0], second.run.artifact_ids[0])
    machine.select_organ(OrganFamily.TOPOLOGY)
    return machine


def codes(obj) -> list:
    return [r.code for r in obj.refusals]


def states(execution) -> list:
    return [a.state for a in execution.run.stage_attempts]


# ── the two arms reach one adapter ───────────────────────────────────────────

def test_direct_and_prompt_reach_the_same_adapter_object_with_the_same_call():
    """The phase gate's question, asked of the adapter rather than of the plan.

    One adapter INSTANCE, one call list. Both arms land in it, and the two records agree on every
    field that describes the work — operation, adapter, clamped parameters, refs, source. They
    differ only in the ids of the run and step that produced them, which is what they are for.
    """
    adapter = fakes.FakeExtentAdapter(name="sam3_concept", operations=("extent.find_named",))
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)

    c.execute(machine, c.plan_direct(machine,
                                     DirectCommand("extent.find_named", {"concept": "chair"})).plan)
    c.execute(machine, c.plan_prompt(machine, "mask the chair").plan)

    assert len(adapter.calls) == 2
    pressed, said = adapter.calls
    for field in ("organ", "operation", "adapter", "parameters", "input_refs", "source",
                  "session_id"):
        assert getattr(pressed, field) == getattr(said, field), field
    assert pressed.run_id != said.run_id and pressed.step_id != said.step_id


def test_the_two_arms_are_distinguishable_only_where_they_should_be():
    """Same adapter, same measurement — and a plan that still says which arm asked.

    "Reaching the same callable" must not mean "leaving the same trace". A run whose planner
    identity was lost would make the Direct arm useless for its actual purpose: establishing that
    the organ works without also testing whether language reached it.
    """
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    pressed = c.plan_direct(machine, DirectCommand("extent.find_named", {"concept": "chair"})).plan
    said = c.plan_prompt(machine, "mask the chair").plan

    assert pressed.planner.value == "direct" and said.planner.value == "rules"
    assert [s.operation for s in pressed.resolved_steps] == \
           [s.operation for s in said.resolved_steps]
    assert [s.parameters for s in pressed.resolved_steps] == \
           [s.parameters for s in said.resolved_steps]
    assert [s.adapter for s in pressed.resolved_steps] == [s.adapter for s in said.resolved_steps]


# ── the isolation firewall, from the prompt to the call list ─────────────────

def test_a_prompt_cannot_switch_organs_in_isolation_and_nothing_is_called():
    topology = fakes.FakeTopologyAdapter(name="adjacency_organ",
                                         operations=("topology.adjacency",))
    c = conductor(fakes.extent_registry().register(topology))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT, mode=SessionMode.ISOLATION)
    machine.select("art_a", "art_b")

    plan = c.plan_prompt(machine, "do those two touch").plan
    assert RefusalCode.ORGAN_LOCKED in codes(plan)
    assert plan.resolved_steps == []

    execution = c.execute(machine, plan)
    assert execution.run.outcome is RunOutcome.REFUSED
    assert topology.calls == [], "a locked organ was reached anyway"
    assert not execution.run.artifact_ids


def test_the_lock_follows_the_organ_the_person_selected_rather_than_the_one_they_started_in():
    """Switching organs moves the lock; it does not lift it. The mirror of the test above."""
    extent = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(fakes.full_registry().register(extent))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.TOPOLOGY, mode=SessionMode.ISOLATION)

    plan = c.plan_prompt(machine, "how many things are in this").plan
    assert RefusalCode.ORGAN_LOCKED in codes(plan)
    c.execute(machine, plan)
    assert extent.calls == []


def test_an_extent_call_is_never_made_from_inside_a_topology_step():
    """The master plan's own non-goal, asserted on the call lists of both organs at once."""
    c = conductor()
    machine = two_extents(c)
    extent_adapters = [a for a in _registered(c) if a.organ == "extent"]
    before = sum(len(a.calls) for a in extent_adapters)

    c.execute(machine, c.plan_prompt(machine, "do those two touch").plan)

    assert sum(len(a.calls) for a in extent_adapters) == before


def _registered(c: PerceptionConductor):
    return list({id(a): a for a in c.registry._by_operation.values()}.values())


# ── the chain, which is visible and confirmed ────────────────────────────────

def test_a_chain_that_crosses_organs_will_not_run_until_it_is_confirmed():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.TOPOLOGY, mode=SessionMode.CHAIN)
    plan = c.plan_prompt(machine, "do those two touch").plan

    assert plan.requires_confirmation
    assert [s.operation for s in plan.proposed_steps] == ["extent.find_all", "topology.adjacency"]
    with pytest.raises(ConfirmationRequired):
        c.execute(machine, plan)


def test_a_confirmed_chain_runs_its_preparation_and_still_refuses_to_feed_it_forward():
    """The three-term chain: extents, THEN A PERSON, then the measurement.

    The preparation stage runs and the topology stage refuses, because the extents it needs are
    ones nobody has chosen yet. A conductor that piped stage one into stage two would produce a
    tidier run and would have decided, on the person's behalf, which of the extents it just found
    the question was about.
    """
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.TOPOLOGY, mode=SessionMode.CHAIN)
    plan = c.plan_prompt(machine, "do those two touch").plan
    execution = c.execute(machine, plan, confirmed=True)

    assert execution.run.outcome is RunOutcome.PARTIAL
    assert RefusalCode.MISSING_EXTENT_INPUTS in codes(execution.run)
    assert len(execution.artifacts) == 1
    assert execution.artifacts[0].identity.organ_family is OrganFamily.EXTENT
    assert any("selects the extents" in p for p in plan.prerequisites)
    assert "required confirmation" in execution.response.text


def test_the_chain_the_person_confirmed_is_the_chain_they_were_shown():
    """Both stages are on the plan before it runs, and the response repeats the prerequisites."""
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.TOPOLOGY, mode=SessionMode.CHAIN)
    plan = c.plan_prompt(machine, "do those two touch").plan
    shown = {s.operation for s in plan.proposed_steps}
    execution = c.execute(machine, plan, confirmed=True)
    ran_or_refused = {a.operation for a in execution.run.stage_attempts}
    assert ran_or_refused == shown
    assert execution.response.of("prerequisite")


# ── references: only what the session declared ───────────────────────────────

def test_an_artifact_the_store_holds_but_the_session_did_not_declare_is_unknown():
    """The strongest form of the reference law: the id is REAL and still refused.

    A conductor that resolved references by looking in the store would pass every test that used
    an invented id and fail exactly here — which is the case that matters, because a plausible id
    is the one a model produces.
    """
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    made = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    real_id = made.run.artifact_ids[0]
    machine.clear_selection()
    assert c.store.get_artifact(real_id) is not None

    ref = InputRef(role="source", scope=IdentityScope.SESSION, artifact_id=real_id)
    plan = c.plan_direct(machine, DirectCommand("extent.refine", {}, (ref,))).plan
    assert RefusalCode.UNKNOWN_REFERENCE in codes(plan)
    assert plan.resolved_steps == []


def test_an_invented_artifact_id_is_refused_and_never_reaches_an_adapter():
    refine = fakes.FakeExtentAdapter(name="sam2_refine", operations=("extent.refine",))
    c = conductor(AdapterRegistry().register(refine))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    ref = InputRef(role="source", scope=IdentityScope.SESSION, artifact_id="art_the_model_made_up")

    plan = c.plan_direct(machine, DirectCommand("extent.refine", {}, (ref,))).plan
    c.execute(machine, plan)
    assert RefusalCode.UNKNOWN_REFERENCE in codes(plan)
    assert refine.calls == []


def test_a_follow_up_measures_the_active_artifact_and_a_deselected_one_is_not_reused():
    """"that mask" is the active id, and deselecting it makes the follow-up refuse rather than
    quietly fall back to the other field that happened to hold it."""
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    first = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    art = first.run.artifact_ids[0]
    machine.activate(art)

    plan = c.plan_prompt(machine, "tighten that mask").plan
    assert [r.artifact_id for s in plan.resolved_steps for r in s.input_refs] == [art]

    machine.deselect(art)
    after = c.plan_prompt(machine, "tighten that mask").plan
    assert RefusalCode.MISSING_EXTENT_INPUTS in codes(after)
    assert after.resolved_steps == []


# ── failing closed ───────────────────────────────────────────────────────────

def test_an_unknown_operation_is_named_in_the_refusal_and_reaches_nothing():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.imagine")).plan
    execution = c.execute(machine, plan)

    assert codes(plan) == [RefusalCode.UNSUPPORTED_OPERATION]
    assert "extent.imagine" in plan.refusals[0].message
    assert execution.run.outcome is RunOutcome.REFUSED
    assert sum(len(a.calls) for a in _registered(c)) == 0


def test_the_adapter_is_handed_the_clamped_parameters_and_not_the_asked_for_ones():
    """The clamp is not advice. What the plan records is what the adapter received."""
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",),
                                      instances=5)
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand(
        "extent.find_all", {"max_instances": 900, "colour": "red"})).plan
    c.execute(machine, plan)

    assert adapter.calls[0].parameters == {"max_instances": 64}
    assert [d.name for d in plan.dropped_parameters] == ["colour"]
    assert [(c_.name, c_.requested, c_.applied) for c_ in plan.clamped_parameters] == \
           [("max_instances", 900, 64)]


def test_a_plan_that_authorized_nothing_and_refused_nothing_is_a_caller_bug():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine).plan
    with pytest.raises(NothingToRun):
        c.execute(machine, plan)
    assert not c.store.runs_for_session(machine.session.session_id)


def test_asking_for_the_model_arm_when_none_is_configured_does_not_silently_give_the_rules_arm():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    with pytest.raises(KeyError):
        c.plan_prompt(machine, "mask the chair", planner="model")


# ── depth: optional to plan, required to run ─────────────────────────────────

def test_occlusion_plans_cleanly_and_refuses_the_missing_depth_at_execution_time():
    """The one operation whose input check differs between the two moments.

    Nothing here computes depth. The Depth organ is registered and disabled, so
    `missing_depth_artifact` is the end of the path rather than a placeholder for a call the
    laboratory could make if it tried — and the assertion that proves it is the occlusion
    adapter's empty call list.
    """
    occlusion = fakes.FakeTopologyAdapter(name="occlusion_organ",
                                          operations=("topology.occlusion",))
    c = conductor(fakes.full_registry().register(occlusion))
    machine = two_extents(c)

    plan = c.plan_prompt(machine, "is that in front of the other one").plan
    assert codes(plan) == [], "the depth input is optional to PLAN"
    assert [s.operation for s in plan.resolved_steps] == ["topology.occlusion"]

    execution = c.execute(machine, plan, confirmed=True)
    assert codes(execution.run) == [RefusalCode.MISSING_DEPTH_ARTIFACT]
    assert execution.run.outcome is RunOutcome.REFUSED
    assert occlusion.calls == [], "the organ was asked to measure depth it was not given"


# ── budgets and cancellation ─────────────────────────────────────────────────

def test_a_run_cancelled_before_it_starts_calls_nothing_and_makes_no_claim():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_all"),
                         DirectCommand("extent.find_all")).plan
    token = CancelToken()
    token.cancel("the person pressed stop")

    execution = c.execute(machine, plan, cancel=token)
    assert states(execution) == [StageState.SKIPPED, StageState.SKIPPED]
    assert execution.run.outcome is RunOutcome.FAILED
    assert sum(len(a.calls) for a in _registered(c)) == 0
    assert all("stop" in a.detail for a in execution.run.stage_attempts)


def test_cancelling_during_a_call_stops_the_next_one():
    """Cooperative, and honest about it: the call in flight finishes, the next is not made.

    The token is set AFTER the measurement exists, which is the real shape of the thing — a person
    presses stop while an organ is running, and an organ that already has an answer returns it.
    An adapter that polls and gives up mid-way is the other case, and it is the test below.
    """

    class StopsAfterAnswering(fakes.FakeExtentAdapter):
        def invoke(self, call):
            outcome = super().invoke(call)
            call.cancel.cancel("the person pressed stop mid-run")
            return outcome

    adapter = StopsAfterAnswering(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_all"),
                         DirectCommand("extent.find_all")).plan

    execution = c.execute(machine, plan, cancel=CancelToken())
    assert len(adapter.calls) == 1
    assert states(execution) == [StageState.COMPLETED, StageState.SKIPPED]
    assert execution.run.outcome is RunOutcome.PARTIAL


def test_an_adapter_that_polls_the_token_and_gives_up_is_skipped_rather_than_failed():
    """`Cancelled` is not an error. Nothing said no and nothing broke: someone changed their mind,
    and a stage that recorded it as `failed` would put a defect in the ledger instead."""
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_all")).plan

    token = CancelToken()
    original = adapter.invoke

    def cancel_then_invoke(call):
        token.cancel("stopped while the organ was working")
        return original(call)

    adapter.invoke = cancel_then_invoke                    # the token trips inside the fake
    execution = c.execute(machine, plan, cancel=token)

    assert states(execution) == [StageState.SKIPPED]
    assert execution.run.stage_attempts[0].invoked is True, "the call was made and must say so"
    assert execution.run.refusals == []
    assert execution.run.outcome is RunOutcome.FAILED


def test_the_call_budget_stops_the_run_and_names_the_stages_it_did_not_run():
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter), budget=CallBudget(max_adapter_calls=1))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_all"),
                         DirectCommand("extent.find_all"),
                         DirectCommand("extent.find_all")).plan

    execution = c.execute(machine, plan)
    assert len(adapter.calls) == 1
    assert states(execution) == [StageState.COMPLETED, StageState.SKIPPED, StageState.SKIPPED]
    assert execution.run.outcome is RunOutcome.PARTIAL
    assert "budget of 1 adapter calls" in execution.run.stage_attempts[1].detail


def test_a_wall_clock_budget_stops_a_run_that_has_already_spent_it():
    c = conductor(budget=CallBudget(max_wall_ms=1))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    execution = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    assert states(execution) == [StageState.SKIPPED]
    assert sum(len(a.calls) for a in _registered(c)) == 0


def test_exhaustion_is_not_a_refusal_because_the_contract_has_no_code_for_one():
    """Nine refusal codes, and none of them means "we stopped asking". Inventing a tenth here
    would put a word on a run that no reader of the contract could look up."""
    c = conductor(budget=CallBudget(max_adapter_calls=1))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_all"),
                         DirectCommand("extent.find_all")).plan
    execution = c.execute(machine, plan)
    assert execution.run.refusals == []
    assert StageState.SKIPPED in states(execution)


# ── the six endings ──────────────────────────────────────────────────────────

def _outcome_cases():
    """One conductor per ending, each reached the way the ending actually happens."""
    def ready():
        c = conductor()
        m = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
        return c.execute(m, c.plan_direct(m, DirectCommand("extent.find_all")).plan)

    def empty():
        c = conductor(fakes.extent_registry(instances=0))
        m = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
        return c.execute(m, c.plan_direct(m, DirectCommand("extent.find_all")).plan)

    def unavailable():
        c = conductor(AdapterRegistry())
        m = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
        return c.execute(m, c.plan_direct(m, DirectCommand("extent.find_all")).plan)

    def refused():
        c = conductor()
        m = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
        return c.execute(m, c.plan_direct(m, DirectCommand("extent.imagine")).plan)

    def partial():
        c = conductor()
        m = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
        return c.execute(m, c.plan_direct(m, DirectCommand("extent.find_all"),
                                          DirectCommand("extent.imagine")).plan)

    def failed():
        c = conductor(fakes.extent_registry(fail_with="the organ died mid-forward-pass"))
        m = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
        return c.execute(m, c.plan_direct(m, DirectCommand("extent.find_all")).plan)

    return {RunOutcome.READY: ready, RunOutcome.EMPTY: empty, RunOutcome.UNAVAILABLE: unavailable,
            RunOutcome.REFUSED: refused, RunOutcome.PARTIAL: partial, RunOutcome.FAILED: failed}


@pytest.mark.parametrize("expected", list(_outcome_cases()))
def test_every_run_outcome_is_reachable_and_is_the_one_the_record_earns(expected):
    assert _outcome_cases()[expected]().run.outcome is expected


def test_the_six_endings_read_differently_to_a_person():
    """`empty` is a MEASURED nothing and `unavailable` is nobody having looked. A response that
    said "no instances" to both would be the absence vocabulary discarded at the last step."""
    said = {outcome: build().response.text for outcome, build in _outcome_cases().items()}
    assert len(set(said.values())) == 6
    assert "found none" in said[RunOutcome.EMPTY]
    assert "capability_unavailable" in said[RunOutcome.UNAVAILABLE]
    assert "unsupported_operation" in said[RunOutcome.REFUSED]


def test_an_empty_result_still_carries_the_measurement_that_found_nothing():
    c = conductor(fakes.extent_registry(instances=0))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    execution = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    payload = execution.artifacts[0].measurement.payload
    assert payload.instances == [] and payload.searched


# ── the three execution identities ───────────────────────────────────────────

def test_live_replay_and_fixture_are_distinguishable_in_the_record_and_in_the_response():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    live = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    shown = c.replay(machine, live.run.run_id)
    fixture = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.imagine")).plan,
                        identity=ExecutionIdentity.FIXTURE)

    assert [e.run.execution_identity for e in (live, shown, fixture)] == [
        ExecutionIdentity.LIVE, ExecutionIdentity.REPLAY, ExecutionIdentity.FIXTURE]
    for execution in (live, shown, fixture):
        assert execution.response.text.startswith(execution.run.execution_identity.value)


def test_a_fixture_run_cannot_invoke_an_adapter_either():
    """`may_invoke` is read off the identity, so FIXTURE gets the replay's guard for free — and
    the raise happens before the caller has a handle, which is where it has to be."""
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_all")).plan

    with pytest.raises(ReplayCannotInvoke):
        c.execute(machine, plan, identity=ExecutionIdentity.FIXTURE)
    assert adapter.calls == []


# ── replay ───────────────────────────────────────────────────────────────────

def test_the_conductor_does_not_hand_its_registry_to_replay():
    """Guard 1, asserted twice: on the signature, and on the source of the method that calls it."""
    assert "registry" not in inspect.signature(RP.replay).parameters

    # The docstring of the method says `self.registry` in order to say it is not passed, so the
    # prose is stripped before the code is read. Comparing against source is the point: this is
    # the assertion that fails if a later hand adds the argument the signature has no room for.
    body = inspect.getsource(PerceptionConductor.replay)
    code = body.split('"""')[2]
    assert "self.registry" not in code
    assert "registry" not in inspect.getsource(RP.replay).split('"""')[2]


def test_a_replay_cannot_reach_a_registry_that_would_notice():
    """An exploding registry proves the negative the other tests can only imply."""

    class Explodes(AdapterRegistry):
        def resolve(self, op_key, adapter_name):
            raise AssertionError(f"a replay resolved {op_key!r}")

    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    live = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    c.registry = Explodes()
    shown = c.replay(machine, live.run.run_id)
    assert shown.run.execution_identity is ExecutionIdentity.REPLAY
    assert shown.run.artifact_ids == live.run.artifact_ids


def test_a_sealed_registry_refuses_before_it_returns_anything():
    sealed = RP.SealedAdapterRegistry()
    with pytest.raises(RP.ReplayCannotRecompute):
        sealed.resolve("extent.find_all", "yolo_sam2_auto")
    with pytest.raises(RP.ReplayCannotRecompute):
        sealed.register(fakes.FakeExtentAdapter())
    assert sealed.capabilities() == {}
    assert isinstance(sealed.capabilities(), dict)


def test_a_replay_whose_source_is_gone_refuses_rather_than_rebuilding_it_from_the_plan():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    shown = c.replay(machine, "run_that_never_was")
    assert codes(shown.run) == [RefusalCode.REPLAY_CANNOT_RECOMPUTE]
    assert shown.run.outcome is RunOutcome.REFUSED
    assert sum(len(a.calls) for a in _registered(c)) == 0


# ── the source under the run ─────────────────────────────────────────────────

def test_a_source_that_moved_under_the_run_makes_no_claim_about_either_image():
    c = conductor(source_probe=lambda: "sha256:0000000000000000")
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    execution = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)

    assert codes(execution.run) == [RefusalCode.SOURCE_MUTATED]
    assert execution.run.outcome is RunOutcome.FAILED
    assert execution.run.source_digest_after == "sha256:0000000000000000"


def test_with_no_probe_the_run_says_nobody_looked_rather_than_asserting_the_image_held_still():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    execution = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    assert execution.run.source_digest_before == SOURCE.image_digest
    assert execution.run.source_digest_after is None


# ── the import firewall ──────────────────────────────────────────────────────

#: Everything the conductor is allowed to reach, transitively. `role_registry` and the two
#: `vision_orchestrator` modules under it are READ-ONLY capability lookups the model arm consults;
#: `backend.config` arrives with them. Nothing here opens a collection, and this list is short
#: enough to read, which is the point of asserting it by hand.
ALLOWED_CLOSURE = {
    "backend.config",
    "backend.schemas.perception_lab",
    "backend.services",
    "backend.services.epistemics",
    "backend.services.role_registry",
    "backend.services.vision_orchestrator.contracts",
    "backend.services.vision_orchestrator.registry",
}


def _closure(root_module: str) -> set:
    """Every `backend.*` module reachable from one, read out of the source rather than imported.

    Static, so a late import inside a method — the conductor has one — is counted, and so an
    import that only fires on a code path no test walks is counted too.
    """
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def path_of(module: str):
        base = os.path.join(here, *module.split("."))
        if os.path.isfile(base + ".py"):
            return base + ".py"
        package = os.path.join(base, "__init__.py")
        return package if os.path.isfile(package) else None

    def imported_by(module: str) -> set:
        path = path_of(module)
        if path is None:
            return set()
        tree = ast.parse(open(path, encoding="utf-8").read())
        package = module if path.endswith("__init__.py") else module.rsplit(".", 1)[0]
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parts = package.split(".")
                    base = ".".join(parts[:len(parts) - node.level + 1] +
                                    ([base] if base else []))
                found.add(base)
                found |= {f"{base}.{alias.name}" for alias in node.names}
        return {m for m in found if m.startswith("backend")}

    seen, queue = set(), deque([root_module])
    while queue:
        module = queue.popleft()
        if module in seen:
            continue
        seen.add(module)
        queue.extend(m for m in imported_by(module) if m not in seen)
    return {m for m in seen if path_of(m)}


def test_the_conductor_cannot_reach_a_post_a_ground_or_the_perceptual_ledger():
    """No write outside the lab store is REACHABLE, not merely not performed.

    Walked statically over the whole transitive closure, so a path no test exercises is still
    counted. `backend.database` never appears, which is the short version of the whole claim.
    """
    closure = _closure("backend.services.perception_lab.orchestrator")
    outside = {m for m in closure if not m.startswith("backend.services.perception_lab")}
    assert outside <= ALLOWED_CLOSURE, f"the conductor grew a new dependency: {outside - ALLOWED_CLOSURE}"
    assert "backend.database" not in closure
    assert not any(word in m for m in closure
                   for word in ("router", "percept_lineage", "ground", "mongo", "post_"))


def test_the_lab_writes_only_through_the_store_it_was_given():
    """Counted rather than asserted: every record the run produced is in the injected store, and
    the number of stores in play is one."""
    c = conductor()
    machine = two_extents(c)
    c.execute(machine, c.plan_prompt(machine, "do those two touch").plan)
    counts = c.store.counts()
    assert counts["sessions"] == 1 and counts["runs"] == 3 and counts["artifacts"] == 3
    assert counts["plans"] == 3


def test_the_store_protocol_names_nothing_outside_the_laboratory():
    from backend.services.perception_lab.store import LabStore
    methods = {m for m in dir(LabStore) if not m.startswith("_")}
    assert not any(word in m for m in methods
                   for word in ("post", "region", "mark", "ground", "percept", "promote"))


# ── the registry's organ firewall ────────────────────────────────────────────

def test_an_adapter_cannot_be_bound_to_an_operation_of_another_organ():
    crossing = fakes.FakeExtentAdapter(name="adjacency_organ", organ="extent",
                                       operations=("topology.adjacency",))
    with pytest.raises(OrganCrossing):
        AdapterRegistry().register(crossing)


def test_an_adapter_the_contract_does_not_name_cannot_be_registered():
    with pytest.raises(NotRegistered):
        AdapterRegistry().register(
            fakes.FakeExtentAdapter(name="my_own_segmenter", operations=("extent.find_all",)))


def test_an_operation_that_does_not_exist_cannot_be_claimed_by_an_adapter():
    with pytest.raises(NotRegistered):
        AdapterRegistry().register(
            fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.imagine",)))


def test_an_unregistered_adapter_is_unknown_here_rather_than_reported_unavailable():
    """A caller who has not looked is not a caller who found nothing. The registry says what it
    has and stays silent about the rest."""
    registry = AdapterRegistry().register(
        fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",)))
    assert set(registry.capabilities()) == {"yolo_sam2_auto"}


# ── what an adapter may report ───────────────────────────────────────────────

def test_an_adapter_may_not_report_a_state_that_belongs_to_the_machinery():
    with pytest.raises(AdapterError):
        AdapterOutcome(state=StageState.SKIPPED, detail="I decided to stop")


def test_an_adapter_reporting_emptiness_without_a_measurement_is_refused_at_the_seam():
    with pytest.raises(AdapterError):
        AdapterOutcome(state=StageState.EMPTY)


def test_an_adapter_reporting_a_refusal_without_a_typed_one_is_refused_at_the_seam():
    with pytest.raises(AdapterError):
        AdapterOutcome(state=StageState.REFUSED, detail="no")


def test_an_adapter_that_raises_is_a_failed_stage_and_not_a_refusal():
    c = conductor(fakes.extent_registry(fail_with=None))

    class Raises(fakes.FakeExtentAdapter):
        def invoke(self, call):
            raise RuntimeError("CUDA is on fire")

    c = conductor(AdapterRegistry().register(
        Raises(name="yolo_sam2_auto", operations=("extent.find_all",))))
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    execution = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)

    assert states(execution) == [StageState.FAILED]
    assert execution.run.refusals == []
    assert "CUDA is on fire" in execution.run.stage_attempts[0].detail
    assert execution.run.stage_attempts[0].invoked is True


# ── the response ─────────────────────────────────────────────────────────────

def test_no_template_names_a_field_that_carries_a_reading_of_the_picture():
    named = set().union(*TEMPLATE_FIELDS.values())
    assert named & UNSAYABLE == set()


def test_no_template_can_be_filled_with_a_planners_account_of_itself():
    """The rationale, the notes and the model's prose reach no sentence the laboratory says."""
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_named", {"concept": "chair"})).plan
    execution = c.execute(machine, plan)

    assert plan.proposed_steps[0].rationale
    assert plan.proposed_steps[0].rationale not in execution.response.text
    for line in execution.response.lines:
        assert set(line.fields) <= TEMPLATE_FIELDS[line.template_id]


def test_the_response_says_what_the_artifact_is_entitled_to_claim():
    c = conductor()
    machine = two_extents(c)
    execution = c.execute(machine, c.plan_prompt(machine, "do those two touch").plan)
    basis = execution.response.of("basis")
    assert basis and basis[0].fields["epistemic_status"] == "measured"


def test_a_box_basis_relation_cannot_call_itself_measured_in_the_response():
    """The WAVE2.5 ruling arriving through the whole path rather than asserted about one file."""
    c = conductor()
    machine = two_extents(c)
    refs = tuple(machine.view().artifact_ref(role, a) for role, a in
                 zip(("source", "target"), machine.view().artifact_ids))
    plan = c.plan_direct(machine,
                         DirectCommand("topology.adjacency", {"basis": "box"}, refs)).plan
    execution = c.execute(machine, plan)
    assert execution.artifacts[0].measurement.epistemic_status is EpistemicStatus.INTERPRETIVE
    assert execution.response.of("basis")[0].fields["epistemic_status"] == "interpretive"


# ── the model arm's honesty, end to end ──────────────────────────────────────

def test_a_model_fallback_stays_visible_from_the_planner_to_the_response():
    """The five guards' fourth: unavailability said out loud. A run planned by the rules arm after
    the model failed must not be readable as a run the model planned."""
    ids = SequentialIds()
    planner = ModelPlanner(FakeClient(RuntimeError("the model host is down")),
                           model="test/planner-1", fallback=RulesPlanner(ids), ids=ids)
    c = conductor(model=planner)
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)

    plan = c.plan_prompt(machine, "mask the chair", planner="model").plan
    execution = c.execute(machine, plan)

    assert plan.planner.value == "rules"
    assert plan.planner_fell_back_from.value == "model"
    assert "did not answer" in execution.response.text
    assert execution.response.of("planner") == ()


def test_a_model_plan_that_worked_does_not_claim_a_fallback():
    ids = SequentialIds()
    planner = ModelPlanner(
        FakeClient({"steps": [{"operation": "extent.find_all", "parameters": {}}]}),
        model="test/planner-1", fallback=RulesPlanner(ids), ids=ids)
    c = conductor(model=planner)
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_prompt(machine, "what is in this", planner="model").plan
    assert plan.planner.value == "model" and plan.planner_fell_back_from is None


def test_the_model_is_asked_once_and_the_count_is_readable():
    """No re-prompt loop. `inquiry/model.py` guard 3, and the counter is the proof."""
    ids = SequentialIds()
    client = FakeClient("not json at all")
    planner = ModelPlanner(client, model="test/planner-1", fallback=RulesPlanner(ids), ids=ids)
    c = conductor(model=planner)
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    c.plan_prompt(machine, "mask the chair", planner="model")
    assert client.calls == 1


# ── the ledger of a sitting ──────────────────────────────────────────────────

def test_every_prompt_is_recorded_including_the_ones_that_refused():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT, mode=SessionMode.ISOLATION)
    c.plan_prompt(machine, "mask the chair")
    c.plan_prompt(machine, "do those two touch")
    turns = c.store.get_session(machine.session.session_id).prompt_turns
    assert [t.text for t in turns] == ["mask the chair", "do those two touch"]
    assert all(t.plan_id for t in turns)


def test_a_review_records_a_verdict_and_changes_nothing_else():
    """Three decisions, three deciders. Saying `correct` does not promote the artifact and does
    not raise what it is entitled to claim."""
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    execution = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    artifact_id = execution.run.artifact_ids[0]
    before = c.store.get_artifact(artifact_id)

    c.review(machine, artifact_id, reviewer="a person", verdict=ReviewVerdict.CORRECT)
    after = c.store.get_artifact(artifact_id)

    assert after.lifecycle.status is LifecycleState.PROPOSED == before.lifecycle.status
    assert after.measurement.epistemic_status == before.measurement.epistemic_status
    assert len(c.store.reviews_for_artifact(artifact_id)) == 1


def test_a_review_of_an_artifact_this_store_does_not_hold_is_a_caller_bug():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    with pytest.raises(KeyError):
        c.review(machine, "art_invented", reviewer="a person", verdict=ReviewVerdict.CORRECT)


def test_a_manual_artifact_is_a_persons_hand_and_names_no_adapter():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand(
        "extent.draw", {"tool": "mask_brush",
                        "mask_rle": {"size": [16, 16], "counts": [0, 256]}})).plan
    execution = c.execute(machine, plan)

    provenance = execution.artifacts[0].provenance
    assert provenance.producer_kind is ProducerKind.HUMAN
    assert provenance.adapter is None and provenance.model is None


def test_a_drawn_mask_that_does_not_say_which_hand_drew_it_is_refused():
    """`tool` is required, and it is required so that a drawn mask never reads as a segmented one
    in any later report. A missing one is `invalid_parameters` before any step exists."""
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand(
        "extent.draw", {"mask_rle": {"size": [16, 16], "counts": [0, 256]}})).plan
    assert codes(plan) == [RefusalCode.INVALID_PARAMETERS]
    assert plan.resolved_steps == []
