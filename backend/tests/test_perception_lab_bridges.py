"""
PERCEPTUAL-ORGANS-002 Lane F1 — the conductor against the REAL organs.

Lane D proved the conductor against fakes. This file proves the seam: that `extent.run` and
`topology.run` reach the conductor without either of them acquiring the other's authority. The
Topology arithmetic here is the real one — real RLE masks, real `nestedness_organ`, real
containment numbers — and only the segmenter is faked, because a test that downloaded SAM is a
test nobody runs.

WHAT IS ASSERTED, and each of these was checked by breaking the thing it names:

    give the façade's artifact id to the store   -> the duplicate-envelope test
    carry the organ's duration onto the stage    -> the one-clock test
    let the bridge build its own ResolvedStep    -> the authorization test
    register a bridge for a disabled organ       -> the six-deferred-organs test
    let the topology bridge supply a depth field -> the occlusion test
    let a topology step reach an extent adapter  -> the isolation tests
    drop the refusal when an artifact came back  -> the partial test
"""
from __future__ import annotations

import pytest

from backend.schemas.perception_lab import (ArtifactKind, CapabilityState, EpistemicStatus,
                                            ExecutionIdentity, IdentityScope, InputRef,
                                            OrganFamily, PerceptualArtifact, ProducerKind,
                                            RefusalCode, RunOutcome, SessionMode, StageState)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.adapters import AdapterError
from backend.services.perception_lab.bridges import (ExtentBridge, LabRuntime, TopologyBridge,
                                                     live_registry)
from backend.services.perception_lab.live import conductor_for
from backend.services.perception_lab.planners import DirectCommand
from backend.services.perception_lab.store import InMemoryLabStore
from backend.tests.fixtures import perception_lab_live as F


def _lab(**over):
    """A conductor on the real organs, a fake segmenter and an in-memory ledger."""
    snapshot = over.pop("snapshot", None) or F.snapshot()
    store = over.pop("store", None) or InMemoryLabStore()
    adapters = over.pop("extent_adapters", None)
    conductor = conductor_for(
        snapshot, store=store,
        extent_adapters=adapters if adapters is not None else F.extent_adapters(),
        probe_collection=F.FakeCollection([F.post_document()]), **over)
    return conductor, store, snapshot


def _extents(conductor, machine, **params):
    plan = conductor.plan_direct(machine, DirectCommand("extent.find_all", params)).plan
    return conductor.execute(machine, plan)


def _open(conductor, snapshot, organ=OrganFamily.EXTENT, mode=SessionMode.ISOLATION):
    return conductor.open_session(source=snapshot.source, organ=organ, mode=mode)


# ── the seam ─────────────────────────────────────────────────────────────────


def test_the_real_extent_facade_produces_a_contract_valid_artifact_through_the_conductor():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    execution = _extents(conductor, machine)

    assert execution.run.outcome is RunOutcome.READY
    artifact = execution.artifacts[0]
    # Re-validated from JSON rather than trusted as an object: what is stored and what a route
    # serves is the dump, and a record that only validates in memory is a record that fails at the
    # wire.
    PerceptualArtifact.model_validate(artifact.model_dump(mode="json"))
    assert artifact.identity.artifact_kind is ArtifactKind.EXTENT_SET
    assert artifact.measurement.epistemic_status is EpistemicStatus.MEASURED
    assert len(artifact.measurement.payload.instances) == 2


def test_the_real_topology_organ_measures_a_real_containment_through_the_conductor():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    extents = _extents(conductor, machine)
    artifact_id = extents.artifacts[0].identity.artifact_id
    ids = [i.instance_id for i in extents.artifacts[0].measurement.payload.instances]
    machine.select_instance(artifact_id, *ids)
    machine.select_organ(OrganFamily.TOPOLOGY)

    plan = conductor.plan_direct(machine, DirectCommand("topology.containment", {}, (
        InputRef(role="source", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[1]),
        InputRef(role="target", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[0])))).plan
    execution = conductor.execute(machine, plan)

    assert execution.run.outcome is RunOutcome.READY
    payload = execution.artifacts[0].measurement.payload
    assert payload.pairs_examined == 1
    relation = payload.relations[0]
    # The INNER rectangle inside the OUTER one, computed per pixel by `nestedness_organ`. A fake
    # would have returned a number; this is the number.
    assert relation.measurements["containment"] == pytest.approx(1.0)
    assert relation.source.instance_id == ids[1]
    assert relation.target.instance_id == ids[0]


def test_the_instance_ref_a_person_selected_is_the_instance_the_organ_measured():
    """A2's reference, end to end through a real organ rather than a fake that ignored it."""
    conductor, store, snapshot = _lab(extent_adapters=F.extent_adapters(
        yolo_sam2_auto=F.FakeSegmenter("yolo_sam2_auto", instances=3)))
    machine = _open(conductor, snapshot)
    extents = _extents(conductor, machine)
    artifact_id = extents.artifacts[0].identity.artifact_id
    ids = [i.instance_id for i in extents.artifacts[0].measurement.payload.instances]
    assert len(ids) == 3
    machine.select_instance(artifact_id, ids[0], ids[2])
    machine.select_organ(OrganFamily.TOPOLOGY)

    plan = conductor.plan_direct(machine, DirectCommand("topology.adjacency", {}, (
        InputRef(role="source", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[0]),
        InputRef(role="target", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[2])))).plan
    execution = conductor.execute(machine, plan)

    cited = {e.instance_id for r in execution.artifacts[0].measurement.payload.relations
             for e in (r.source, r.target)}
    assert cited == {ids[0], ids[2]}
    assert ids[1] not in cited


def test_an_instance_the_artifact_does_not_hold_refuses_instead_of_widening():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    extents = _extents(conductor, machine)
    artifact_id = extents.artifacts[0].identity.artifact_id
    ids = [i.instance_id for i in extents.artifacts[0].measurement.payload.instances]
    machine.select_instance(artifact_id, *ids)
    machine.select_organ(OrganFamily.TOPOLOGY)
    ghost = InputRef(role="source", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                     instance_id="inst_nobody_selected")

    plan = conductor.plan_direct(machine, DirectCommand("topology.containment", {}, (
        ghost,
        InputRef(role="target", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[0])))).plan

    # Refused at the RESOLVER, before an organ was reached — the session never declared the pair.
    assert not plan.resolved_steps
    assert plan.refusals[0].code is RefusalCode.UNKNOWN_REFERENCE
    assert f"{artifact_id}#inst_nobody_selected" in plan.refusals[0].missing


# ── one authority for identity, one clock ────────────────────────────────────


def test_only_the_conductors_artifact_is_persisted_and_the_facades_id_is_nowhere():
    """The duplicate-envelope guard. Both façades mint an artifact id; one of them is discarded."""
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    execution = _extents(conductor, machine)

    assert store.counts()["artifacts"] == 1
    artifact = execution.artifacts[0]
    # `extent._artifact_id` is `art_<run>_<step>`; the conductor's is `art_<uuid>`. Not one of the
    # façade's ids may be in the ledger, under any key.
    facade_id = f"art_{execution.run.run_id}_{artifact.identity.step_id}"
    assert artifact.identity.artifact_id != facade_id
    assert store.get_artifact(facade_id) is None
    assert execution.run.artifact_ids == [artifact.identity.artifact_id]


def test_the_run_has_one_duration_and_the_organs_own_number_is_prose():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    execution = _extents(conductor, machine)

    attempt = execution.run.stage_attempts[-1]
    assert attempt.duration_ms is not None
    # The organ measured 11ms of itself (the fixture says so). That number may APPEAR, and only in
    # the prose, where nothing reads it as the run's.
    assert "inner_ms=" in (attempt.detail or "")
    assert attempt.duration_ms == execution.artifacts[0].provenance.duration_ms
    assert execution.run.duration_ms >= attempt.duration_ms


def test_the_artifact_takes_its_identity_from_the_conductor_and_its_facts_from_the_organ():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    execution = _extents(conductor, machine)
    artifact = execution.artifacts[0]

    # The conductor's:
    assert artifact.identity.session_id == machine.session.session_id
    assert artifact.identity.run_id == execution.run.run_id
    assert artifact.provenance.producer_kind is ProducerKind.ADAPTER
    # The organ's:
    assert artifact.provenance.model == "fixture/yolo_sam2_auto"
    assert artifact.provenance.revision == "fixture-1"
    assert artifact.provenance.device == "cpu"
    assert artifact.provenance.adapter == "yolo_sam2_auto"
    assert artifact.provenance.source_image_digest == snapshot.source.image_digest


def test_a_bridge_will_not_run_a_step_it_was_not_handed():
    """The authorization guard: a bridge that could build a `ResolvedStep` could grant itself one."""
    from backend.services.perception_lab.adapters import AdapterCall, CancelToken
    runtime = LabRuntime(source=F.snapshot().source)
    bridge = ExtentBridge(name="yolo_sam2_auto", operations=("extent.find_all",), runtime=runtime)
    call = AdapterCall(session_id="labs_1", run_id="run_1", step_id="step_1",
                       organ=OrganFamily.EXTENT, operation="extent.find_all", adapter="yolo_sam2_auto",
                       parameters={}, input_refs=(), inputs={}, source=runtime.source,
                       cancel=CancelToken(), step=None)
    with pytest.raises(AdapterError, match="does not reconstruct one"):
        bridge.invoke(call)


# ── the two arms reach one runner ────────────────────────────────────────────


def test_a_control_and_a_sentence_reach_the_same_facade_and_measure_the_same_thing():
    """The phase's central comparison, against the REAL Extent façade rather than a fake."""
    conductor, store, snapshot = _lab()
    direct = _extents(conductor, _open(conductor, snapshot))

    machine = _open(conductor, snapshot)
    resolution = conductor.plan_prompt(machine, "what is in this picture?", planner="rules")
    prompted = conductor.execute(machine, resolution.plan)

    assert [s.operation for s in resolution.plan.resolved_steps] == ["extent.find_all"]
    assert direct.run.outcome is prompted.run.outcome is RunOutcome.READY

    def _shape(execution):
        payload = execution.artifacts[0].measurement.payload
        return (execution.artifacts[0].identity.artifact_kind,
                execution.artifacts[0].measurement.epistemic_basis,
                execution.artifacts[0].provenance.adapter,
                [(i.mask_rle, i.area) for i in payload.instances])

    # The MEASUREMENT is identical; the ids are not, because two runs are two runs.
    assert _shape(direct) == _shape(prompted)


# ── the three states the underlying services conflate ────────────────────────


def test_an_unavailable_adapter_refuses_before_the_call_and_an_empty_one_measures_nothing():
    unavailable = F.extent_adapters(
        yolo_sam2_auto=F.FakeSegmenter("yolo_sam2_auto", state=CapabilityState.UNAVAILABLE))
    conductor, store, snapshot = _lab(extent_adapters=unavailable)
    machine = _open(conductor, snapshot)
    refused = _extents(conductor, machine)

    assert refused.run.outcome is RunOutcome.UNAVAILABLE
    assert refused.run.refusals[0].code is RefusalCode.CAPABILITY_UNAVAILABLE
    assert refused.run.stage_attempts[-1].invoked is False
    assert unavailable["yolo_sam2_auto"].calls == []

    empty = F.extent_adapters(yolo_sam2_auto=F.FakeSegmenter("yolo_sam2_auto", instances=0))
    conductor2, store2, snapshot2 = _lab(extent_adapters=empty)
    measured = _extents(conductor2, _open(conductor2, snapshot2))

    assert measured.run.outcome is RunOutcome.EMPTY
    assert measured.run.stage_attempts[-1].invoked is True
    assert measured.artifacts[0].measurement.payload.searched          # it says what it looked for
    assert not measured.run.refusals


def test_an_adapter_that_raises_is_failed_and_makes_no_claim():
    broken = F.extent_adapters(
        yolo_sam2_auto=F.FakeSegmenter("yolo_sam2_auto", raises=RuntimeError("cuda is gone")))
    conductor, store, snapshot = _lab(extent_adapters=broken)
    execution = _extents(conductor, _open(conductor, snapshot))

    assert execution.run.outcome is RunOutcome.FAILED
    assert not execution.artifacts
    assert execution.run.stage_attempts[-1].state is StageState.FAILED
    assert "cuda is gone" in (execution.run.stage_attempts[-1].detail or "")


def test_the_resolver_walks_past_an_unavailable_adapter_to_one_that_is_running():
    """`sam3_concept` missing and `grounded_sam` present is the ordinary deployment, and the
    receipt must name the one that ran rather than the one that was asked for first."""
    table = F.extent_adapters(
        sam3_concept=F.FakeSegmenter("sam3_concept", state=CapabilityState.UNAVAILABLE))
    conductor, store, snapshot = _lab(extent_adapters=table)
    machine = _open(conductor, snapshot)
    plan = conductor.plan_direct(
        machine, DirectCommand("extent.find_named", {"concept": "disc"})).plan

    assert plan.resolved_steps[0].adapter == "grounded_sam"
    execution = conductor.execute(machine, plan)
    assert execution.artifacts[0].provenance.adapter == "grounded_sam"
    assert table["sam3_concept"].calls == []


def test_every_adapter_missing_is_capability_unavailable_and_never_an_empty_result():
    table = F.extent_adapters(
        sam3_concept=F.FakeSegmenter("sam3_concept", state=CapabilityState.UNAVAILABLE),
        grounded_sam=F.FakeSegmenter("grounded_sam", state=CapabilityState.UNAVAILABLE))
    conductor, store, snapshot = _lab(extent_adapters=table)
    machine = _open(conductor, snapshot)
    plan = conductor.plan_direct(
        machine, DirectCommand("extent.find_named", {"concept": "disc"})).plan

    assert not plan.resolved_steps
    assert plan.refusals[0].code is RefusalCode.CAPABILITY_UNAVAILABLE
    assert sorted(plan.refusals[0].missing) == ["grounded_sam", "sam3_concept"]


# ── what the bridges may not reach ───────────────────────────────────────────


def test_occlusion_refuses_a_missing_depth_field_and_no_bridge_can_supply_one():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    extents = _extents(conductor, machine)
    artifact_id = extents.artifacts[0].identity.artifact_id
    ids = [i.instance_id for i in extents.artifacts[0].measurement.payload.instances]
    machine.select_instance(artifact_id, *ids)
    machine.select_organ(OrganFamily.TOPOLOGY)

    plan = conductor.plan_direct(machine, DirectCommand("topology.occlusion", {}, (
        InputRef(role="source", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[0]),
        InputRef(role="target", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[1])))).plan
    # `topology.occlusion` declares a confirmation, and this is the person giving it. The refusal
    # that follows is about the DEPTH FIELD, not about the confirmation — two different noes, and
    # a test that stopped at the first would never reach the one it is named for.
    assert plan.requires_confirmation
    execution = conductor.execute(machine, plan, confirmed=True)

    assert execution.run.outcome is RunOutcome.REFUSED
    assert execution.run.refusals[0].code is RefusalCode.MISSING_DEPTH_ARTIFACT
    assert not execution.artifacts

    # And the seam is closed structurally, not only by this run: the bridge has no code that
    # constructs a `DepthArtifact`.
    import inspect
    from backend.services.perception_lab import bridges
    assert "DepthArtifact" not in inspect.getsource(bridges)


def test_a_topology_run_never_reaches_an_extent_adapter():
    """Isolation, at the level below the resolver: the registry's organ firewall."""
    table = F.extent_adapters()
    conductor, store, snapshot = _lab(extent_adapters=table)
    machine = _open(conductor, snapshot)
    extents = _extents(conductor, machine)
    before = sum(len(a.calls) for a in table.values())
    artifact_id = extents.artifacts[0].identity.artifact_id
    ids = [i.instance_id for i in extents.artifacts[0].measurement.payload.instances]
    machine.select_instance(artifact_id, *ids)
    machine.select_organ(OrganFamily.TOPOLOGY)

    plan = conductor.plan_direct(machine, DirectCommand("topology.containment", {}, (
        InputRef(role="source", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[1]),
        InputRef(role="target", scope=IdentityScope.SESSION, artifact_id=artifact_id,
                 instance_id=ids[0])))).plan
    conductor.execute(machine, plan)

    assert sum(len(a.calls) for a in table.values()) == before


def test_a_topology_question_with_no_extents_refuses_rather_than_finding_its_own():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot, organ=OrganFamily.TOPOLOGY)
    plan = conductor.plan_direct(machine, DirectCommand("topology.containment")).plan

    assert not plan.resolved_steps
    assert plan.refusals[0].code is RefusalCode.MISSING_EXTENT_INPUTS


# ── the registry ─────────────────────────────────────────────────────────────


def test_the_live_registry_holds_exactly_the_declared_adapters_of_the_two_live_organs():
    registry = live_registry(LabRuntime(source=F.snapshot().source))
    declared = {name for family in ("extent", "topology")
                for op in D.operations_for(family) for name in op.adapters}
    assert set(registry.names) == declared

    deferred = {name for organ in D.organs().values() if not organ.enabled
                for op in organ.operations for name in op.adapters}
    assert not (set(registry.names) & deferred)


def test_the_live_registry_reports_what_an_adapter_says_rather_than_that_it_is_registered():
    runtime = LabRuntime(source=F.snapshot().source,
                         capability_states={"sam3_concept": CapabilityState.UNAVAILABLE})
    states = live_registry(runtime).capabilities()

    assert states["sam3_concept"] is CapabilityState.UNAVAILABLE
    assert states["nestedness_organ"] is CapabilityState.AVAILABLE
    # An adapter nobody registered is ABSENT, not `unavailable`: a registry that has not been asked
    # is not a registry that found something missing.
    assert "depth_anything" not in states


def test_the_live_registry_is_the_thing_that_says_the_wire_is_live():
    from backend.services.perception_lab.live import identity_of
    from backend.services.perception_lab import fakes
    assert identity_of(live_registry(LabRuntime(source=F.snapshot().source))) \
        is ExecutionIdentity.LIVE
    # A suite that wired fakes gets `FIXTURE` without anybody remembering to say so.
    assert identity_of(fakes.full_registry()) is ExecutionIdentity.FIXTURE


# ── a measurement and a refusal, both true of one stage ──────────────────────


def test_extents_that_came_back_and_a_reference_that_did_not_are_one_partial_run():
    """`extent.reuse` over two regions where one is gone. BOTH facts reach the record.

    This is the seam repair Lane F1 made in the conductor: `AdapterOutcome` can carry a
    measurement and a refusal at once, and dropping the refusal because an artifact arrived would
    report a missing input as `ready`. The façade already calls this `partial`; the run says so too.
    """
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    machine.activate_regions(["seg_0", "seg_vanished"])

    plan = conductor.plan_direct(machine, DirectCommand("extent.reuse", {}, (
        InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="seg_0",
                 geometry_rev=3),
        InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="seg_vanished",
                 geometry_rev=0)))).plan
    execution = conductor.execute(machine, plan)

    assert execution.run.outcome is RunOutcome.PARTIAL
    assert len(execution.artifacts) == 1
    assert len(execution.artifacts[0].measurement.payload.instances) == 1
    assert execution.run.refusals[0].code is RefusalCode.UNKNOWN_REFERENCE
    assert "seg_vanished" in execution.run.refusals[0].missing
    assert store.counts()["artifacts"] == 1


def test_several_unresolved_references_are_named_rather_than_truncated_to_the_first():
    conductor, store, snapshot = _lab()
    machine = _open(conductor, snapshot)
    machine.activate_regions(["seg_0", "seg_gone_a", "seg_gone_b"])

    plan = conductor.plan_direct(machine, DirectCommand("extent.reuse", {}, (
        InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="seg_0",
                 geometry_rev=3),
        InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="seg_gone_a",
                 geometry_rev=0),
        InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="seg_gone_b",
                 geometry_rev=0)))).plan
    execution = conductor.execute(machine, plan)

    # A person who mistyped two of three ids is told about both. The whole reason the façade
    # collects refusals instead of raising on the first is undone by a seam that keeps one.
    assert sorted(execution.run.refusals[0].missing) == ["seg_gone_a", "seg_gone_b"]
