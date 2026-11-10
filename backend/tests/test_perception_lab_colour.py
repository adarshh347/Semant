"""Synthetic colour controls and portable reuse of the real Colour slot."""
from __future__ import annotations

import io
import json

import pytest
from PIL import Image, ImageCms

from backend.schemas.perception_lab import (
    ArtifactIdentity, ArtifactInterpretation, ArtifactLifecycle, ArtifactMeasurement,
    ArtifactProjection, ArtifactProvenance, ExecutionIdentity, LabPlan, LabRun,
    LabSession, LabSource, PerceptualArtifact, ProposedStep, ResolvedStep, SampleGridPayload)
from backend.services.perception_lab import live
from backend.services.perception_lab.definitions import resolve_parameters
from backend.services.perception_lab.bridges import LabRuntime, live_registry
from backend.services.perception_lab.derivation_store import InMemoryDerivationStore
from backend.services.perception_lab.families.colour import (
    MAX_CLUSTERS, MAX_SAMPLES, channels, distance_rgb, distance_sample, palette)
from backend.services.perception_lab.field_assets import InMemoryFieldAssets
from backend.services.perception_lab.field_data import (
    compare_fields, decode_grid, encode_grid, path_sample, point_sample, roi_sample)
from backend.services.perception_lab.field_transfer import attach_field_assets, import_session_bundle
from backend.services.perception_lab.image_preparation import prepare_image
from backend.services.perception_lab.store import InMemoryLabStore
from backend.services.perception_lab.orchestrator import PerceptionConductor
from backend.services.perception_lab.planners.base import DirectCommand
from backend.schemas.perception_lab import OrganFamily

NOW = "2026-09-23T00:00:00Z"


class NoCancel:
    def raise_if_cancelled(self):
        return None


def prepared(size, pixels, mode="RGBA"):
    image = Image.new(mode, size)
    image.putdata(pixels)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return prepare_image(stream.getvalue())


def grid(produced, assets=None):
    manifest, ref = encode_grid(produced.metadata, produced.values, produced.valid,
                                put_asset=assets.put if assets else None)
    return decode_grid(manifest, ref, get_asset=assets.get if assets else None)


def test_known_srgb_lab_patches_and_achromatic_invalid_non_square():
    image = prepared((3, 2), [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255),
                              (128, 128, 128, 255), (255, 255, 255, 0), (0, 0, 0, 255)])
    result = grid(channels(image, {}, (), NoCancel()))
    assert result.shape == (2, 3, 6)
    red, green, blue = [point_sample(result, x, 0)["values"] for x in range(3)]
    assert red[:3] == [1, 0, 0]
    assert red[3:] == pytest.approx([53.24, 80.09, 67.20], abs=.04)
    assert green[3:] == pytest.approx([87.73, -86.18, 83.18], abs=.06)
    assert blue[3:] == pytest.approx([32.30, 79.19, -107.86], abs=.06)
    grey = point_sample(result, 0, 1)["values"]
    assert grey[4:] == pytest.approx([0, 0], abs=.005)
    assert point_sample(result, 1, 1)["values"] is None
    assert "sRGB assumed" in json.loads(result.metadata["value_convention"])["working_profile"]
    assert result.metadata["source_digest"] == image.source_digest


def test_colour_ramps_keep_lightness_and_chroma_distinct():
    image = prepared((4, 1), [(30, 30, 30, 255), (220, 220, 220, 255),
                              (160, 90, 90, 255), (90, 160, 90, 255)])
    result = grid(channels(image, {}, (), NoCancel()))
    dark, light, warm, green = [point_sample(result, x, 0)["values"] for x in range(4)]
    assert light[3] > dark[3] + 60
    assert abs(light[4]) < .01 and abs(dark[5]) < .01
    assert warm[4] > 0 and green[4] < 0
    assert abs(warm[3] - green[3]) < 15
    assert path_sample(result, [(0, 0), (1, 0)])[-1]["values"] == light
    roi = roi_sample(result, [(0, 0), (1, 0), (2, 0)])
    assert roi["sample_count"] == 3 and roi["valid_count"] == 3


def test_constant_grey_and_smooth_ramp_are_not_false_palette_objects():
    grey = prepared((7, 3), [(128, 128, 128, 255)] * 21)
    colour = grid(channels(grey, {}, (), NoCancel()))
    assert all(point_sample(colour, x, y)["values"][3] == colour.values[3]
               for y in range(3) for x in range(7))
    grouped = grid(palette(grey, {"clusters": 8, "samples": 128, "seed": 0}, (), NoCancel()))
    summary = json.loads(grouped.metadata["value_convention"])
    assert summary["actual_clusters"] == 1 and summary["population_counts"] == [21]
    ramp = prepared((16, 1), [(v, 0, 255 - v, 255) for v in range(0, 256, 17)])
    signal = grid(channels(ramp, {}, (), NoCancel()))
    red = [point_sample(signal, x, 0)["values"][0] for x in range(16)]
    assert red == sorted(red) and red[0] == 0 and red[-1] == 1


def test_palette_determinism_caps_counts_and_locations():
    image = prepared((3, 2), [(255, 0, 0, 255)] * 3 + [(0, 0, 255, 255)] * 3)
    params = {"clusters": MAX_CLUSTERS, "samples": MAX_SAMPLES, "seed": 9}
    first = grid(palette(image, params, (), NoCancel()))
    second = grid(palette(image, params, (), NoCancel()))
    assert first.measurement_hash == second.measurement_hash
    summary = json.loads(first.metadata["value_convention"])
    assert summary["actual_samples"] == 6
    assert summary["actual_clusters"] == 2
    assert sum(summary["population_counts"]) == 6
    assert sum(summary["sample_counts"]) == 6
    for x, y, group in summary["sample_locations"]:
        assert point_sample(first, x, y)["values"] == [group]


def test_distance_sample_and_supplied_rgb_are_full_saved_fields():
    image = prepared((2, 1), [(255, 0, 0, 255), (0, 0, 255, 255)])
    sampled = grid(distance_sample(image, {"x": 0, "y": 0}, (), NoCancel()))
    supplied = grid(distance_rgb(image, {"r": 255, "g": 0, "b": 0}, (), NoCancel()))
    assert point_sample(sampled, 0, 0)["values"] == [0]
    assert point_sample(sampled, 1, 0)["values"][0] > 170
    assert compare_fields(sampled, supplied)["max_absolute_difference"] == 0
    different = grid(distance_rgb(image, {"r": 0, "g": 0, "b": 255}, (), NoCancel()))
    assert compare_fields(sampled, different)["max_absolute_difference"] > 170
    with pytest.raises(ValueError, match="valid colour field"):
        distance_sample(image, {"x": 2, "y": 0}, (), NoCancel())
    refused = resolve_parameters("colour.distance_rgb", {"r": 256, "g": 0, "b": 0})
    assert refused.refusal is not None


def test_profile_and_exif_orientation_are_declared_derivatives():
    image = Image.new("RGB", (2, 1))
    image.putdata([(255, 0, 0), (0, 0, 255)])
    exif = Image.Exif(); exif[274] = 6
    stream = io.BytesIO(); image.save(stream, format="JPEG", exif=exif)
    prepared_image = prepare_image(stream.getvalue())
    result = grid(channels(prepared_image, {}, (), NoCancel()))
    assert result.shape[:2] == (2, 1)
    assert result.metadata["source_to_field"] == [0, -1, 0, 1, 0, 0, 0, 0, 1]
    assert json.loads(result.metadata["value_convention"])["orientation"] == 6
    assert prepared_image.source_bytes == stream.getvalue()
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    stream = io.BytesIO(); image.save(stream, format="PNG", icc_profile=profile)
    profiled = grid(channels(prepare_image(stream.getvalue()), {}, (), NoCancel()))
    assert "embedded ICC converted" in json.loads(
        profiled.metadata["value_convention"])["working_profile"]


def test_real_colour_field_export_import_and_read_without_producer(monkeypatch):
    image = prepared((2, 1), [(255, 0, 0, 255), (0, 0, 255, 255)])
    produced = channels(image, {}, (), NoCancel())
    assets = InMemoryFieldAssets()
    manifest, ref = encode_grid(produced.metadata, produced.values, produced.valid, put_asset=assets.put)
    artifact = PerceptualArtifact(
        identity=ArtifactIdentity(artifact_id="art_colour", session_id="labs_colour",
            run_id="run_colour", step_id="step_1", organ_family="colour",
            artifact_kind="sample_grid", operation="colour.channels", identity_scope="session"),
        measurement=ArtifactMeasurement(payload_variant="sample_grid",
            payload=SampleGridPayload(form_key="colour.channels", manifest=manifest, field_ref=ref),
            coordinate_system="pixel_xy_topleft", epistemic_status="measured",
            epistemic_basis="image_signal"),
        projection=ArtifactProjection(projection_kind="scalar_wash"),
        interpretation=ArtifactInterpretation(label=None, label_source="none",
                                              epistemic_status="uncertain"),
        lifecycle=ArtifactLifecycle(status="proposed", changed_at=NOW, changed_by="colour-test"),
        provenance=ArtifactProvenance(producer_kind="adapter", producer="colour.channels",
                                      adapter="colour.channels",
                                      source_image_digest=image.source_digest))
    source = LabSource(origin="post", post_id="post_colour", image_digest=image.source_digest,
                       natural_width=2, natural_height=1)
    session = LabSession(session_id="labs_colour", source=source, selected_organ="colour",
                         mode="isolation", run_ids=["run_colour"],
                         selected_artifact_ids=["art_colour"], active_artifact_id="art_colour",
                         created_at=NOW, updated_at=NOW)
    plan = LabPlan(plan_id="plan_colour", session_id="labs_colour", planner="direct",
                   selected_organ="colour", mode="isolation",
                   proposed_steps=[ProposedStep(step_id="step_1", organ="colour",
                                                operation="colour.channels")],
                   resolved_steps=[ResolvedStep(step_id="step_1", organ="colour",
                                                operation="colour.channels", adapter="colour.channels",
                                                authorized_by="resolver")],
                   requires_confirmation=True, created_at=NOW)
    run = LabRun(run_id="run_colour", session_id="labs_colour", execution_identity="LIVE",
                 outcome="ready", requested_plan_id="plan_colour", resolved_plan_id="plan_colour",
                 artifact_ids=["art_colour"], source_digest_before=image.source_digest,
                 source_digest_after=image.source_digest)
    store = InMemoryLabStore()
    for writer, record in ((store.put_session, session), (store.put_plan, plan),
                           (store.put_run, run), (store.put_artifact, artifact)):
        writer(record)
    bundle = attach_field_assets(live.export_json(store, session, identity=ExecutionIdentity.LIVE), assets)
    monkeypatch.setattr("backend.services.perception_lab.families.colour.channels",
                        lambda *_: pytest.fail("import attempted to run colour producer"))
    fresh = InMemoryLabStore()
    receipt = import_session_bundle(bundle, store=fresh,
        derivation_store=InMemoryDerivationStore(), asset_store=InMemoryFieldAssets(),
        target_source=source)
    imported = fresh.get_artifact(receipt["identity_map"]["art_colour"])
    read = decode_grid(imported.measurement.payload.manifest,
                       imported.measurement.payload.field_ref)
    assert read.measurement_hash == manifest["measurement_hash"]
    assert point_sample(read, 0, 0)["values"][3] == pytest.approx(53.24, abs=.04)
    assert roi_sample(read, [(0, 0), (1, 0)])["valid_count"] == 2
    assert image.source_bytes == image.source_bytes


def test_live_conductor_runs_colour_and_rules_prompt_through_resolver():
    image = prepared((3, 1), [(255, 0, 0, 255), (128, 128, 128, 255),
                              (0, 0, 255, 255)])
    source = LabSource(origin="post", post_id="post_colour", image_digest=image.source_digest,
                       natural_width=3, natural_height=1)
    store = InMemoryLabStore()
    conductor = PerceptionConductor(store=store,
        registry=live_registry(LabRuntime(source=source, image_bytes=image.source_bytes)),
        source_probe=lambda: source.image_digest)
    machine = conductor.open_session(source=source, organ=OrganFamily.COLOUR)
    direct = conductor.plan_direct(machine, DirectCommand("colour.channels"))
    prompt = conductor.plan_prompt(machine, "show the colour field", planner="rules")
    assert direct.plan.resolved_steps[0].operation == prompt.plan.resolved_steps[0].operation
    result = conductor.execute(machine, direct.plan, confirmed=True)
    assert result.run.outcome.value == "ready"
    artifact = result.artifacts[0]
    read = decode_grid(artifact.measurement.payload.manifest,
                       artifact.measurement.payload.field_ref)
    assert point_sample(read, 0, 0)["values"][3] == pytest.approx(53.24, abs=.04)
    missing = conductor.plan_prompt(machine, "compare colour to the selected sample",
                                    planner="rules")
    assert missing.plan.refusals
    assert "required" in missing.plan.refusals[0].message
