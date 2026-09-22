"""A fixture field survives existing Lab stores and #238 export into a fresh session."""
from __future__ import annotations

import pytest

from backend.schemas.perception_lab import (
    ArtifactIdentity, ArtifactInterpretation, ArtifactLifecycle, ArtifactMeasurement,
    ArtifactProjection, ArtifactProvenance, LabPlan, LabRun, LabSession, LabSource,
    PerceptualArtifact, ProposedStep, ResolvedStep, SampleGridPayload, ExecutionIdentity)
from backend.services.perception_lab import contracts, definitions, live
from backend.services.perception_lab.derivation_store import InMemoryDerivationStore
from backend.services.perception_lab.families import registry
from backend.services.perception_lab.families.base import FamilyForm, FamilyModule, FamilyOperation
from backend.services.perception_lab.field_assets import InMemoryFieldAssets
from backend.services.perception_lab.field_data import FieldError, decode_grid, encode_grid, point_sample
from backend.services.perception_lab.field_transfer import attach_field_assets, import_session_bundle
from backend.services.perception_lab.store import InMemoryLabStore

NOW = "2026-09-23T00:00:00Z"
SOURCE = "sha256:" + "a" * 64


def test_family_registry_rejects_duplicate_and_unadmitted_declarations():
    from dataclasses import replace
    slot = FamilyModule("colour", "Fixture", True, "FIXTURE only",
        forms=(FamilyForm("colour.synthetic", "Synthetic", "relative signal", "Fixture", ("colour",)),),
        operations=(FamilyOperation("colour.synthetic", "Synthetic", "colour.synthetic",
                                    "colour.fixture", {}, ("show synthetic field",), True),),
        producers={"colour.fixture": lambda *_: None},
        models=({"key": "fixture", "revision": "1", "license": "test",
                 "checkpoint_digest": SOURCE, "admitted": False},))
    with pytest.raises(ValueError, match="unadmitted"):
        registry.checked_slots((slot, *registry.SLOTS[1:]))
    with pytest.raises(ValueError, match="duplicate"):
        registry.checked_slots((replace(slot, models=({**slot.models[0], "admitted": True},),
                                        forms=(slot.forms[0], slot.forms[0])), *registry.SLOTS[1:]))


@pytest.fixture
def fixture_slot(monkeypatch):
    def fixture_producer(*args):
        raise AssertionError("fixture import must never run a producer")
    slot = FamilyModule(
        family="colour", label="Colour fixture", available=True, reason="fixture test only",
        forms=(FamilyForm("colour.synthetic", "Synthetic", "synthetic scalar",
                          "Fixture-only control", ("colour", "grayscale")),),
        operations=(FamilyOperation("colour.synthetic", "Synthetic", "colour.synthetic",
                                    "colour.fixture", {}, ("show synthetic field",)),),
        producers={"colour.fixture": fixture_producer})
    patched = registry.checked_slots((slot, *registry.SLOTS[1:]))
    monkeypatch.setattr(registry, "REGISTRY", patched)
    contracts.operation_index.cache_clear()
    definitions._registry.cache_clear()
    yield slot
    contracts.operation_index.cache_clear()
    definitions._registry.cache_clear()


def field_record(assets):
    metadata = {"version": 1, "shape": [2, 3, 1], "dtype": "float32-le",
                "kind": "scalar", "channels": [{"name": "v", "quantity": "synthetic ramp",
                                                "unit": "relative"}],
                "frame": "image_pixel_xy_topleft", "units": "relative",
                "source_digest": SOURCE, "source_to_field": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                "value_convention": "synthetic fixture"}
    manifest, ref = encode_grid(metadata, [0, .25, .5, .75, 0, 1],
                                [True, True, True, True, False, True], put_asset=assets.put)
    return PerceptualArtifact(
        identity=ArtifactIdentity(artifact_id="art_fixture", session_id="labs_fixture",
            run_id="run_fixture", step_id="step_1", organ_family="colour",
            artifact_kind="sample_grid", operation="colour.synthetic", identity_scope="session"),
        measurement=ArtifactMeasurement(payload_variant="sample_grid",
            payload=SampleGridPayload(form_key="colour.synthetic", manifest=manifest, field_ref=ref),
            coordinate_system="pixel_xy_topleft", epistemic_status="measured",
            epistemic_basis="image_signal"),
        projection=ArtifactProjection(projection_kind="scalar_wash"),
        interpretation=ArtifactInterpretation(label=None, label_source="none",
                                              epistemic_status="uncertain"),
        lifecycle=ArtifactLifecycle(status="proposed", changed_at=NOW, changed_by="fixture"),
        provenance=ArtifactProvenance(producer_kind="fixture", producer="fixture-only",
                                      source_image_digest=SOURCE))


def test_export_import_and_consume_without_model(fixture_slot):
    assets = InMemoryFieldAssets()
    artifact = field_record(assets)
    source = LabSource(origin="post", post_id="post_fixture", image_digest=SOURCE,
                       natural_width=3, natural_height=2)
    session = LabSession(session_id="labs_fixture", source=source, selected_organ="colour",
                         mode="isolation", run_ids=["run_fixture"],
                         selected_artifact_ids=["art_fixture"], active_artifact_id="art_fixture",
                         created_at=NOW, updated_at=NOW)
    plan = LabPlan(plan_id="plan_fixture", session_id="labs_fixture", planner="direct",
                   selected_organ="colour", mode="isolation",
                   proposed_steps=[ProposedStep(step_id="step_1", organ="colour",
                                                operation="colour.synthetic")],
                   resolved_steps=[ResolvedStep(step_id="step_1", organ="colour",
                                                operation="colour.synthetic", adapter="colour.fixture",
                                                authorized_by="resolver")],
                   requires_confirmation=True, created_at=NOW)
    run = LabRun(run_id="run_fixture", session_id="labs_fixture", execution_identity="FIXTURE",
                 outcome="ready", requested_plan_id="plan_fixture", resolved_plan_id="plan_fixture",
                 artifact_ids=["art_fixture"], source_digest_before=SOURCE,
                 source_digest_after=SOURCE)
    first = InMemoryLabStore()
    for method, record in ((first.put_session, session), (first.put_plan, plan),
                           (first.put_run, run), (first.put_artifact, artifact)):
        method(record)
    bundle = live.export_json(first, session, identity=ExecutionIdentity.FIXTURE)
    bundle["derivations"] = []
    portable = attach_field_assets(bundle, assets)
    assert portable["field_asset_status"] == "complete"
    fresh = InMemoryLabStore()
    receipt = import_session_bundle(portable, store=fresh,
        derivation_store=InMemoryDerivationStore(), asset_store=InMemoryFieldAssets(),
        target_source=source)
    assert receipt["session_id"] != session.session_id
    imported = fresh.get_artifact(receipt["identity_map"][artifact.identity.artifact_id])
    grid = decode_grid(imported.measurement.payload.manifest,
                       imported.measurement.payload.field_ref)
    assert point_sample(grid, 2, 1)["values"] == [1]
    assert point_sample(grid, 1, 1)["values"] is None
    assert grid.measurement_hash == artifact.measurement.payload.manifest["measurement_hash"]
    assert fresh.get_session(receipt["session_id"]).active_artifact_id == imported.identity.artifact_id


def test_import_refuses_bad_field_digest_before_any_record_write(fixture_slot):
    assets = InMemoryFieldAssets()
    artifact = field_record(assets)
    source = LabSource(origin="post", post_id="post_fixture", image_digest=SOURCE,
                       natural_width=3, natural_height=2)
    session = LabSession(session_id="labs_fixture", source=source, selected_organ="colour",
                         mode="isolation", created_at=NOW, updated_at=NOW)
    bundle = {"export_kind": "perception-lab.session-export", "export_version": 1,
              "session": session.model_dump(mode="json"), "plans": [], "runs": [],
              "artifacts": [], "reviews": [], "derivations": [], "field_assets": []}
    bad = {**bundle, "field_assets": [{"uri": "lab-asset:sha256:" + "0"*64,
            "digest": "sha256:" + "0"*64, "bytes": 3, "base64": "YWJj"}]}
    fresh = InMemoryLabStore()
    with pytest.raises(FieldError, match="digest"):
        import_session_bundle(bad, store=fresh, derivation_store=InMemoryDerivationStore(),
                              asset_store=assets, target_source=source)
    assert fresh.sessions() == ()


def test_large_asset_is_embedded_in_export_and_restored_to_fresh_store(fixture_slot):
    assets = InMemoryFieldAssets()
    artifact = field_record(assets)
    payload = artifact.measurement.payload
    metadata = {**payload.manifest["metadata"], "shape": [256, 256, 1]}
    values = [((i * 2003) % 65521) / 65521 for i in range(256 * 256)]
    manifest, ref = encode_grid(metadata, values, [True] * len(values), put_asset=assets.put)
    assert ref.uri.startswith("lab-asset:")
    artifact = artifact.model_copy(update={"measurement": artifact.measurement.model_copy(
        update={"payload": SampleGridPayload(form_key="colour.synthetic", manifest=manifest,
                                               field_ref=ref)})})
    source = LabSource(origin="post", post_id="post_fixture", image_digest=SOURCE,
                       natural_width=256, natural_height=256)
    session = LabSession(session_id="labs_fixture", source=source, selected_organ="colour",
                         mode="isolation", run_ids=["run_fixture"],
                         selected_artifact_ids=["art_fixture"], active_artifact_id="art_fixture",
                         created_at=NOW, updated_at=NOW)
    plan = LabPlan(plan_id="plan_fixture", session_id="labs_fixture", planner="direct",
                   selected_organ="colour", mode="isolation",
                   proposed_steps=[ProposedStep(step_id="step_1", organ="colour",
                                                operation="colour.synthetic")],
                   resolved_steps=[ResolvedStep(step_id="step_1", organ="colour",
                                                operation="colour.synthetic", adapter="colour.fixture",
                                                authorized_by="resolver")],
                   requires_confirmation=True, created_at=NOW)
    run = LabRun(run_id="run_fixture", session_id="labs_fixture", execution_identity="FIXTURE",
                 outcome="ready", requested_plan_id="plan_fixture", resolved_plan_id="plan_fixture",
                 artifact_ids=["art_fixture"], source_digest_before=SOURCE,
                 source_digest_after=SOURCE)
    first = InMemoryLabStore()
    for method, record in ((first.put_session, session), (first.put_plan, plan),
                           (first.put_run, run), (first.put_artifact, artifact)):
        method(record)
    bundle = attach_field_assets(live.export_json(first, session, identity=ExecutionIdentity.FIXTURE), assets)
    assert len(bundle["field_assets"]) == 1
    fresh, fresh_assets = InMemoryLabStore(), InMemoryFieldAssets()
    receipt = import_session_bundle(bundle, store=fresh,
        derivation_store=InMemoryDerivationStore(), asset_store=fresh_assets, target_source=source)
    imported = fresh.get_artifact(receipt["identity_map"]["art_fixture"])
    read = decode_grid(imported.measurement.payload.manifest,
                       imported.measurement.payload.field_ref, get_asset=fresh_assets.get)
    assert read.measurement_hash == manifest["measurement_hash"]
    assert point_sample(read, 255, 255)["values"] == [read.values[-1]]


def test_direct_and_bounded_prompt_reach_same_saved_field(fixture_slot):
    from dataclasses import replace
    from io import BytesIO
    from PIL import Image
    from backend.schemas.perception_lab import OrganFamily
    from backend.services.perception_lab.adapters import CancelToken
    from backend.services.perception_lab.bridges import LabRuntime, live_registry
    from backend.services.perception_lab.families.base import ProducedField
    from backend.services.perception_lab.orchestrator import PerceptionConductor
    from backend.services.perception_lab.planners.base import DirectCommand
    from backend.services.perception_lab.source import image_digest

    image = Image.new("RGB", (3, 2), (120, 80, 40))
    output = BytesIO(); image.save(output, format="PNG")
    image_bytes = output.getvalue()
    source = LabSource(origin="post", post_id="post_fixture",
                       image_digest=image_digest(image_bytes), natural_width=3, natural_height=2)
    calls = []
    def producer(prepared, parameters, inputs, cancel):
        calls.append(prepared.source_digest)
        return ProducedField(metadata={"version": 1, "shape": [2, 3, 1],
            "dtype": "float32-le", "kind": "scalar",
            "channels": [{"name": "v", "quantity": "synthetic ramp", "unit": "relative"}],
            "frame": "image_pixel_xy_topleft", "units": "relative",
            "source_digest": prepared.source_digest,
            "source_to_field": list(prepared.source_to_working),
            "value_convention": "synthetic fixture"},
            values=[0, .25, .5, .75, 0, 1], valid=[True, True, True, True, False, True],
            producer_revision="fixture-v1")
    registry.REGISTRY["colour"] = replace(fixture_slot,
                                           producers={"colour.fixture": producer})
    store = InMemoryLabStore()
    conductor = PerceptionConductor(store=store,
        registry=live_registry(LabRuntime(source=source, image_bytes=image_bytes)),
        source_probe=lambda: source.image_digest)
    machine = conductor.open_session(source=source, organ=OrganFamily.COLOUR)
    direct = conductor.plan_direct(machine, DirectCommand("colour.synthetic"))
    prompt = conductor.plan_prompt(machine, "show synthetic field", planner="rules")
    assert direct.plan.resolved_steps[0].operation == prompt.plan.resolved_steps[0].operation
    first = conductor.execute(machine, direct.plan, confirmed=True)
    second = conductor.execute(machine, prompt.plan, confirmed=True)
    assert first.run.outcome.value == second.run.outcome.value == "ready"
    assert first.artifacts[0].measurement.payload.manifest["measurement_hash"] == \
        second.artifacts[0].measurement.payload.manifest["measurement_hash"]
    assert len(calls) == 2
