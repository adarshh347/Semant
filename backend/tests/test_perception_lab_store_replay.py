"""
PERCEPTUAL-ORGANS-002 Lane D — the ledger, the observer, and the run that cannot recompute.

The replay tests are the ones this file exists for. Every one of them holds a fake adapter with a
public call counter, and asserts on that counter rather than on a flag in a record — because a
record saying `invoked: false` is exactly what a broken replay would also produce, right after
calling the adapter.
"""
from __future__ import annotations

import pytest

from backend.schemas.perception_lab import (ExecutionIdentity, LabSource, OrganFamily,
                                            RefusalCode, ReviewVerdict, RunOutcome, SessionMode,
                                            StageState)
from backend.services.perception_lab import fakes, replay as RP
from backend.services.perception_lab.adapters import AdapterRegistry
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.observer import ReplayCannotInvoke, RunObserver
from backend.services.perception_lab.orchestrator import PerceptionConductor
from backend.services.perception_lab.planners import DirectCommand
from backend.services.perception_lab.store import InMemoryLabStore, resolve_inputs

SOURCE = LabSource(origin="post", post_id="post_finial", image_digest="sha256:9f1c0a5b7d2e4438",
                   natural_width=1600, natural_height=1200)


class TickingClock(FrozenClock):
    """Advances a little on every reading, so durations are non-zero and still deterministic."""

    def monotonic_ms(self) -> int:
        self.elapsed_ms += 7
        return self.elapsed_ms


def conductor(registry=None, **kw) -> PerceptionConductor:
    return PerceptionConductor(store=InMemoryLabStore(),
                              registry=registry if registry is not None else fakes.full_registry(),
                              clock=TickingClock(), ids=SequentialIds(), **kw)


def extent_run(c: PerceptionConductor):
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    plan = c.plan_direct(machine, DirectCommand("extent.find_all")).plan
    return machine, c.execute(machine, plan)


# ── the store ────────────────────────────────────────────────────────────────

def test_the_store_interface_has_no_method_that_writes_anything_outside_the_lab():
    from backend.services.perception_lab.store import LabStore
    methods = {m for m in dir(LabStore) if not m.startswith("_")}
    assert methods == {
        "put_session", "get_session", "sessions", "put_plan", "get_plan", "plans_for_session",
        "put_run", "get_run", "runs_for_session", "put_artifact", "get_artifact",
        "artifacts_for_run", "put_review", "get_review", "reviews_for_artifact"}
    assert not any(word in m for m in methods
                   for word in ("post", "region", "mark", "ground", "percept", "promote"))


def test_a_record_read_out_of_the_store_is_a_value_and_not_a_window_onto_it():
    c = conductor()
    machine, execution = extent_run(c)
    artifact = c.store.get_artifact(execution.run.artifact_ids[0])
    artifact.lifecycle.status = artifact.lifecycle.status          # touch it
    artifact.identity.derived_from.append("art_smuggled")
    again = c.store.get_artifact(execution.run.artifact_ids[0])
    assert again.identity.derived_from == []


def test_a_record_mutated_after_being_put_does_not_change_what_was_stored():
    store = InMemoryLabStore()
    c = conductor()
    machine, execution = extent_run(c)
    store.put_run(execution.run)
    execution.run.artifact_ids.append("art_smuggled")
    assert store.get_run(execution.run.run_id).artifact_ids == ["art_1"]


def test_runs_come_back_in_the_order_they_happened():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    first = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    second = c.execute(machine, c.plan_direct(machine, DirectCommand("extent.find_all")).plan)
    ids = [r.run_id for r in c.store.runs_for_session(machine.session.session_id)]
    assert ids == [first.run.run_id, second.run.run_id]


def test_an_input_ref_whose_artifact_is_absent_resolves_to_nothing_rather_than_raising():
    from backend.schemas.perception_lab import IdentityScope, InputRef
    ref = InputRef(role="source", scope=IdentityScope.SESSION, artifact_id="art_gone")
    assert resolve_inputs(InMemoryLabStore(), [ref]) == {}


# ── the observer ─────────────────────────────────────────────────────────────

def test_the_observer_grew_no_new_way_to_produce_a_stage():
    """The test below exercises every method that can mint a `StageAttempt`. If a new one appears,
    this fails first and says so, rather than the coverage silently going stale."""
    minting = {m for m in dir(RunObserver)
               if not m.startswith("_") and callable(getattr(RunObserver, m))}
    assert minting == {"refused", "unavailable", "skipped", "failed", "begin", "end", "reshown"}


def test_only_begin_can_make_a_stage_invoked():
    """`invoked` is the field the whole replay law turns on. Every other road to a stage leaves it
    false — not by convention but because no other method takes the argument that sets it."""
    import inspect

    observer = RunObserver("run_x", clock=TickingClock(), ids=SequentialIds(), may_invoke=True)

    for method in ("refused", "unavailable", "skipped", "failed"):
        attempt = getattr(observer, method)("step_1", "extent.find_all", "because")
        assert attempt.invoked is False, f"{method} minted an invoked stage"
        assert "invoking" not in inspect.signature(getattr(observer, method)).parameters

    honest = observer.end(observer.begin("s", "extent.find_all", "yolo_sam2_auto", invoking=False),
                          StageState.COMPLETED)
    assert honest.invoked is False
    assert observer.reshown(honest, "re-shown").invoked is False

    called = observer.end(observer.begin("s", "extent.find_all", "yolo_sam2_auto", invoking=True),
                          StageState.COMPLETED)
    assert called.invoked is True, "the one road that may set it stopped setting it"


def test_no_road_to_an_invoked_stage_is_open_on_an_observer_that_may_not_invoke():
    """The same sweep, on the observer a replay actually gets. `begin` raises rather than lying,
    and nothing else can reach the field at all."""
    observer = RunObserver("run_x", clock=TickingClock(), ids=SequentialIds(), may_invoke=False)
    for method in ("refused", "unavailable", "skipped", "failed"):
        assert getattr(observer, method)("step_1", "extent.find_all", "because").invoked is False
    with pytest.raises(ReplayCannotInvoke):
        observer.begin("step_1", "extent.find_all", "yolo_sam2_auto", invoking=True)
    assert not observer.invoked_any


def test_an_observer_that_may_not_invoke_raises_before_the_caller_gets_a_handle():
    observer = RunObserver("run_x", clock=TickingClock(), ids=SequentialIds(), may_invoke=False)
    with pytest.raises(ReplayCannotInvoke):
        observer.begin("step_1", "extent.find_all", "yolo_sam2_auto", invoking=True)
    assert observer.attempts == []


def test_a_replay_stage_may_name_the_adapter_whose_output_it_shows_without_having_called_it():
    observer = RunObserver("run_x", clock=TickingClock(), ids=SequentialIds(), may_invoke=False)
    stage = observer.begin("step_1", "extent.find_all", "yolo_sam2_auto", invoking=False)
    attempt = observer.end(stage, StageState.COMPLETED, "re-shown")
    assert attempt.adapter == "yolo_sam2_auto"
    assert attempt.invoked is False


def test_the_observer_holds_the_stopwatch_and_the_adapter_does_not():
    c = conductor()
    _, execution = extent_run(c)
    attempt = execution.run.stage_attempts[0]
    assert attempt.duration_ms and attempt.duration_ms > 0
    # `FakeExtentAdapter` reports no duration at all; there is no field for one on AdapterOutcome.
    from backend.services.perception_lab.adapters import AdapterOutcome
    assert "duration_ms" not in AdapterOutcome.__dataclass_fields__


# ── replay ───────────────────────────────────────────────────────────────────

def test_a_replay_re_shows_the_run_and_calls_nothing():
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine, live = extent_run(c)
    assert len(adapter.calls) == 1

    shown = c.replay(machine, live.run.run_id)
    assert shown.run.execution_identity is ExecutionIdentity.REPLAY
    assert shown.run.replay.source_run_id == live.run.run_id
    assert shown.run.replay.adapter_callable is False
    assert shown.run.artifact_ids == live.run.artifact_ids
    assert len(adapter.calls) == 1, "the replay called the adapter"


def test_no_stage_of_a_replay_is_invoked():
    c = conductor()
    machine, live = extent_run(c)
    shown = c.replay(machine, live.run.run_id)
    assert any(a.invoked for a in live.run.stage_attempts)
    assert not any(a.invoked for a in shown.run.stage_attempts)


def test_a_replay_re_times_itself_rather_than_wearing_the_originals_duration():
    """The one column that distinguishes a replay from the run it replays."""
    c = conductor()
    machine, live = extent_run(c)
    shown = c.replay(machine, live.run.run_id)
    assert shown.run.stage_attempts[0].adapter == live.run.stage_attempts[0].adapter
    assert shown.run.stage_attempts[0].started_at != live.run.stage_attempts[0].started_at
    assert "measured the organ" in shown.run.stage_attempts[0].detail


def test_a_replay_reuses_the_original_artifact_ids_rather_than_minting_new_ones():
    """Two ids carrying one measurement is how a lab reviews a mask twice and calls it agreement."""
    c = conductor()
    machine, live = extent_run(c)
    before = c.store.counts()["artifacts"]
    shown = c.replay(machine, live.run.run_id)
    assert c.store.counts()["artifacts"] == before
    assert shown.artifacts[0].identity.artifact_id == live.artifacts[0].identity.artifact_id


def test_replaying_a_run_the_ledger_never_held_refuses_rather_than_rebuilding_it():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    shown = c.replay(machine, "run_that_never_was")
    assert shown.run.execution_identity is ExecutionIdentity.REPLAY
    assert shown.run.outcome is RunOutcome.REFUSED
    assert [r.code for r in shown.run.refusals] == [RefusalCode.REPLAY_CANNOT_RECOMPUTE]


def test_a_replay_whose_artifacts_are_gone_refuses_rather_than_running_the_plan_again():
    """The plan is right there. Rebuilding from it is the one thing a replay must never do."""
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    c = conductor(AdapterRegistry().register(adapter))
    machine, live = extent_run(c)
    c.store._artifacts.clear()

    shown = c.replay(machine, live.run.run_id)
    assert shown.run.outcome is RunOutcome.REFUSED
    assert [r.code for r in shown.run.refusals] == [RefusalCode.REPLAY_CANNOT_RECOMPUTE]
    assert len(adapter.calls) == 1, "the replay re-ran the plan"


def test_the_replay_function_is_handed_no_registry_and_imports_no_adapter():
    """GUARD 1, read off the signature and the module namespace."""
    import inspect

    assert "registry" not in inspect.signature(RP.replay).parameters
    assert not any(name.lower().endswith("registry") and name != "SealedAdapterRegistry"
                   for name in vars(RP))


def test_the_sealed_registry_raises_before_it_returns_an_adapter():
    """GUARD 2, for the Lane F code that will be handed 'a registry' and not ask which kind."""
    adapter = fakes.FakeExtentAdapter(name="yolo_sam2_auto", operations=("extent.find_all",))
    sealed = RP.SealedAdapterRegistry()
    with pytest.raises(RP.ReplayCannotRecompute):
        sealed.resolve("extent.find_all", "yolo_sam2_auto")
    with pytest.raises(RP.ReplayCannotRecompute):
        sealed.register(adapter)
    assert adapter.calls == []
    assert sealed.capabilities() == {}


def test_a_non_live_run_carrying_an_invoked_stage_does_not_validate():
    """GUARD 4, and it is the LAST one: by the time a schema refuses, a call would have happened."""
    from pydantic import ValidationError

    from backend.schemas.perception_lab import LabRun, ReplayProvenance, StageAttempt
    with pytest.raises(ValidationError):
        LabRun(run_id="r", session_id="s", execution_identity=ExecutionIdentity.REPLAY,
               outcome=RunOutcome.READY, requested_plan_id="p", artifact_ids=["a"],
               stage_attempts=[StageAttempt(attempt_id="att", step_id="s1",
                                            operation="extent.find_all",
                                            state=StageState.COMPLETED, invoked=True)],
               source_digest_before="sha256:9f1c0a5b",
               replay=ReplayProvenance(source_run_id="r0", recorded_at="2026-08-10T09:00:00Z",
                                       adapter_callable=False))


def test_a_replay_cannot_declare_itself_callable():
    from pydantic import ValidationError

    from backend.schemas.perception_lab import ReplayProvenance
    with pytest.raises(ValidationError):
        ReplayProvenance(source_run_id="r0", recorded_at="2026-08-10T09:00:00Z",
                         adapter_callable=True)


def test_a_replay_is_recorded_on_the_session_beside_the_run_it_replays():
    c = conductor()
    machine, live = extent_run(c)
    shown = c.replay(machine, live.run.run_id)
    assert machine.session.run_ids == [live.run.run_id, shown.run.run_id]


def test_a_replay_of_a_replay_names_the_replay_it_re_showed():
    c = conductor()
    machine, live = extent_run(c)
    once = c.replay(machine, live.run.run_id)
    twice = c.replay(machine, once.run.run_id)
    assert twice.run.replay.source_run_id == once.run.run_id
    assert not any(a.invoked for a in twice.run.stage_attempts)


# ── reviews ──────────────────────────────────────────────────────────────────

def test_a_review_changes_no_lifecycle_and_no_epistemic_status():
    """Three axes, three deciders. `correct` is not `measured` and is not `kept`."""
    c = conductor()
    machine, execution = extent_run(c)
    artifact_id = execution.run.artifact_ids[0]
    before = c.store.get_artifact(artifact_id)
    c.review(machine, artifact_id, reviewer="a person", verdict=ReviewVerdict.CORRECT,
             notes="the masks are right")
    after = c.store.get_artifact(artifact_id)
    assert after.lifecycle.status is before.lifecycle.status
    assert after.measurement.epistemic_status is before.measurement.epistemic_status
    assert set(c.store.reviews_for_artifact(artifact_id)[0].model_dump()) == {
        "review_id", "session_id", "artifact_id", "reviewer", "verdict", "notes", "corrections",
        "reviewed_at"}


def test_a_review_of_an_artifact_this_laboratory_does_not_hold_is_refused():
    c = conductor()
    machine = c.open_session(source=SOURCE, organ=OrganFamily.EXTENT)
    with pytest.raises(KeyError):
        c.review(machine, "art_invented", reviewer="a person", verdict=ReviewVerdict.CORRECT)
