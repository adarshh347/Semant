"""Synthetic controls for the real CPU axial field and its saved-data consumers."""
import io
import json
import math

import pytest
from PIL import Image

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from backend.services.perception_lab.families import orientation_flow as family
from backend.services.perception_lab.field_assets import InMemoryFieldAssets
from backend.services.perception_lab.field_data import decode_grid, encode_grid, point_sample
from backend.services.perception_lab.image_preparation import prepare_image
from backend.services.perception_lab.families.orientation_consumers import axial_summary, trace
from backend.services.perception_lab.field_data import FieldError, SampleGrid


class NoCancel:
    def raise_if_cancelled(self):
        pass


def prepared(values, alpha=None):
    image = Image.fromarray(np.asarray(values, dtype=np.uint8)).convert("RGBA")
    if alpha is not None:
        image.putalpha(Image.fromarray(np.asarray(alpha, dtype=np.uint8)))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return prepare_image(stream.getvalue())


def stripes(angle, width=96, height=72):
    y, x = np.mgrid[:height, :width]
    theta = math.radians(angle)
    return prepared(127+110*np.sin((-math.sin(theta)*x+math.cos(theta)*y)*2*math.pi/12))


def saved(produced):
    assets = InMemoryFieldAssets()
    manifest, ref = encode_grid(produced.metadata, produced.values, produced.valid, put_asset=assets.put)
    return decode_grid(manifest, ref, get_asset=assets.get)


@pytest.mark.parametrize("angle", [0, 1, 30, 45, 90, 135, 179])
def test_known_stripe_tangents_not_gradient_normals(angle):
    image = stripes(angle)
    grid = saved(family.tangent(image, {}, (), NoCancel()))
    values = point_sample(grid, 48, 36)["values"]
    norm = math.hypot(*values)
    assert norm > .98
    assert [v/norm for v in values] == pytest.approx(
        [math.cos(math.radians(2*angle)), math.sin(math.radians(2*angle))], abs=.025)
    assert grid.shape == (72, 96, 2)
    assert grid.metadata["source_to_field"] == [1, 0, 0, 0, 1, 0, 0, 0, 1]
    assert grid.metadata["source_digest"] == image.source_digest


def test_flat_unoriented_but_energy_is_valid_zero_and_coherence_not_confidence():
    image = prepared(np.full((20, 30), 128))
    axis = saved(family.tangent(image, {}, (), NoCancel()))
    coherence = saved(family.coherence(image, {}, (), NoCancel()))
    energy = saved(family.energy(image, {}, (), NoCancel()))
    assert not any(axis.valid) and not any(coherence.valid)
    assert all(energy.valid) and max(energy.values) < 1e-12
    assert all(value == 0 for value in axis.values)
    assert "not confidence" in json.loads(axis.metadata["value_convention"])["axial_encoding"]


def test_noise_less_coherent_than_stripes_and_scale_changes_new_numbers():
    image = prepared(np.random.default_rng(17).integers(0, 256, (96, 96)))
    small = saved(family.coherence(image, {"integration_sigma": 1}, (), NoCancel()))
    large = saved(family.coherence(image, {"integration_sigma": 8}, (), NoCancel()))
    assert np.mean(large.values) < np.mean(small.values) < .8
    assert large.measurement_hash != small.measurement_hash


def test_explicit_numeric_defaults_and_prompt_defaults_have_identical_saved_semantics():
    image = stripes(30)
    explicit = saved(family.tangent(image, {"derivative_sigma": 1, "integration_sigma": 3,
                                           "min_coherence": .15}, (), NoCancel()))
    default = saved(family.tangent(image, {}, (), NoCancel()))
    assert explicit.measurement_hash == default.measurement_hash


def test_curve_tangent_and_alpha_support_are_not_invented_axes():
    y, x = np.mgrid[:100, :100]
    image = prepared(127+110*np.sin(np.hypot(x-50, y-50)*2*math.pi/12))
    grid = saved(family.tangent(image, {}, (), NoCancel()))
    assert point_sample(grid, 75, 50)["values"][0] < -.8  # right edge of circle: vertical tangent
    alpha = np.full((100, 100), 255, dtype=np.uint8); alpha[:, 45:55] = 0
    masked = prepared(127+110*np.sin(y*2*math.pi/12), alpha)
    mask_grid = saved(family.tangent(masked, {}, (), NoCancel()))
    assert not point_sample(mask_grid, 40, 50)["valid"]
    assert point_sample(mask_grid, 15, 50)["valid"]


def test_bounded_non_square_resize_and_source_pixel_centre_mapping():
    image = stripes(45, 1000, 400)
    result = saved(family.tangent(image, {}, (), NoCancel()))
    assert result.shape == (102, 256, 2)
    assert sum(result.valid) > len(result.valid)*.9
    a, _, c, _, e, f, *_ = result.metadata["source_to_field"]
    assert a == .256 and e == .255
    assert a*499.5+c == 127.5 and e*199.5+f == 50.5
    meta = json.loads(result.metadata["value_convention"])
    assert meta["source_working_size"] == [1000, 400]
    assert "inverse" in meta["source_direction"]


def test_downsampling_never_rounds_partial_opacity_to_fully_valid_support():
    y, _ = np.mgrid[:512, :512]
    alpha = np.full((512, 512), 255, dtype=np.uint8)
    alpha[256, 256] = 254  # uint8 INTER_AREA would round this hole back to 255
    image = prepared(127+110*np.sin(y*2*math.pi/24), alpha)
    result = saved(family.tangent(image, {}, (), NoCancel()))
    assert not point_sample(result, 128, 128)["valid"]
    assert point_sample(result, 100, 100)["valid"]


@pytest.mark.parametrize("shape", [(1, 1), (1, 32), (32, 1)])
def test_degenerate_rasters_remain_bounded_and_unoriented(shape):
    image = prepared(np.full(shape, 128))
    result = saved(family.tangent(image, {}, (), NoCancel()))
    assert result.shape[:2] == shape
    assert not any(result.valid)


def test_rotated_source_preserves_exif_mapping_and_tangent_basis():
    image = Image.open(io.BytesIO(stripes(0).source_bytes)).convert("RGB")
    exif = Image.Exif(); exif[274] = 6
    stream = io.BytesIO(); image.save(stream, format="PNG", exif=exif)
    rotated = prepare_image(stream.getvalue())
    result = saved(family.tangent(rotated, {}, (), NoCancel()))
    assert result.shape[:2] == (96, 72)
    assert result.metadata["source_to_field"] == [0, -1, 71, 1, 0, 0, 0, 0, 1]
    assert point_sample(result, 36, 48)["values"] == pytest.approx([-1, 0], abs=.001)


def test_axial_sign_reversal_traces_the_same_route():
    first, reversed_axis = analytical_grid([0]), analytical_grid([180])
    a, b = trace(first, [[10, 5]], {"max_length": 3}), trace(reversed_axis, [[10, 5]], {"max_length": 3})
    for left, right in zip(a["paths"], b["paths"]):
        assert left["stop_reason"] == right["stop_reason"]
        assert np.asarray(left["points"]) == pytest.approx(np.asarray(right["points"]))


@pytest.mark.parametrize("parameters", [{"integration_sigma": 0}, {"derivative_sigma": float("nan")},
    {"min_coherence": True}, {"min_coherence": 1.1}, {"unknown": 1}])
def test_invalid_parameters_refused(parameters):
    with pytest.raises(ValueError):
        family.tangent(stripes(0), parameters, (), NoCancel())


def test_explicit_cancellation_missing_dependency_and_unsupported_roi(monkeypatch):
    class Cancel:
        def raise_if_cancelled(self):
            raise RuntimeError("cancelled")
    with pytest.raises(RuntimeError, match="cancelled"):
        family.tangent(stripes(0), {}, (), Cancel())
    with pytest.raises(ValueError, match="ROI"):
        family.tangent(stripes(0), {}, ("ambiguous",), NoCancel())
    monkeypatch.setattr(family, "available", lambda: (False, "missing"))
    with pytest.raises(ValueError, match="unavailable"):
        family.tangent(stripes(0), {}, (), NoCancel())


def analytical_grid(angles, width=20, height=10, invalid=()):
    base = family.tangent(stripes(0, width, height), {}, (), NoCancel())
    values = []
    for i in range(width*height):
        angle = angles[i % len(angles)]
        values.extend([math.cos(math.radians(2*angle)), math.sin(math.radians(2*angle))]
                      if i not in invalid else [0, 0])
    return saved(family.ProducedField(base.metadata, values,
        [i not in invalid for i in range(width*height)], family.VERSION))


def test_wraparound_axial_summary_sign_reversal_and_invalid_support():
    grid = analytical_grid([1, 179])
    result = axial_summary(grid, [[1, 2], [2, 2], [1, 2]], {})
    assert result["sample_count"] == 2
    assert min(result["mean_axis_degrees"], 180-result["mean_axis_degrees"]) < .001
    assert result["axial_resultant_length"] > .99
    reversed_grid = analytical_grid([181, 359])
    assert reversed_grid.values == pytest.approx(grid.values)
    empty = analytical_grid([0], invalid=range(200))
    summary = axial_summary(empty, [[1, 2]], {})
    assert summary["valid_count"] == 0 and summary["mean_axis_degrees"] is None


def test_trace_deterministic_both_directions_boundary_and_length_stop():
    grid = analytical_grid([0])
    before = grid.values
    params = {"max_length": 3, "step_size": .5}
    first = trace(grid, [[10, 5]], params)
    assert first == trace(grid, [[10, 5]], params)
    assert [p["stop_point"] for p in first["paths"]] == [[13., 5.], [7., 5.]]
    assert all(p["stop_reason"] == "max_length" for p in first["paths"])
    boundary = trace(grid, [[10, 5]], {"max_length": 100})
    assert all(p["stop_reason"] == "field_boundary" for p in boundary["paths"])
    assert grid.values == before and first["field_hash"] == grid.measurement_hash


def test_trace_does_not_cross_invalid_stripe_or_fabricate_seed_support():
    grid = analytical_grid([0], invalid=[y*20+12 for y in range(10)])
    result = trace(grid, [[10, 5]], {"directions": "positive"})
    assert result["paths"][0]["stop_reason"] == "invalid_support"
    assert max(point[0] for point in result["paths"][0]["points"]) <= 11
    invalid = trace(grid, [[12, 5]], {})
    assert all(p["steps"] == 0 and p["stop_reason"] == "invalid_support" for p in invalid["paths"])


def test_trace_step_bound_turn_limit_and_non_square_vertical_axis():
    vertical = analytical_grid([90])
    result = trace(vertical, [[10, 5]], {"max_steps": 2})
    assert all(p["steps"] == 2 and p["stop_reason"] == "max_steps" for p in result["paths"])
    assert result["paths"][0]["stop_point"] == pytest.approx([10, 6])
    bend = analytical_grid([0]*11+[60]*9)
    result = trace(bend, [[10, 5]], {"directions": "positive", "max_turn_degrees": 10})
    assert result["paths"][0]["stop_reason"] == "max_turn"


@pytest.mark.parametrize("parameters", [{"max_steps": 2049}, {"max_length": float("inf")},
    {"step_size": 2}, {"directions": "clockwise"}, {"min_coherence": False}, {"oops": 1}])
def test_trace_rejects_unbounded_and_unknown_settings(parameters):
    with pytest.raises(FieldError):
        trace(analytical_grid([0]), [[10, 5]], parameters)


def test_consumers_reject_missing_points_wrong_quantity_and_scale_convention():
    grid = analytical_grid([0])
    for points in ([], [[20, 0]], [[1.5, 0]], [[True, 1]]):
        with pytest.raises(FieldError):
            trace(grid, points, {})
    for changes in ({"units": "unit_vector"}, {"kind": "directed_vector_2d"}):
        wrong = SampleGrid({**grid.metadata, **changes}, grid.values, grid.valid, grid.measurement_hash)
        with pytest.raises(FieldError, match="compatible"):
            axial_summary(wrong, [[1, 1]], {})


def test_normal_planner_saved_trace_export_import_and_reconsume_without_source(monkeypatch):
    from dataclasses import replace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routers import perception_lab as route
    from backend.schemas.perception_lab import LabSource, OrganFamily
    from backend.services.perception_lab.bridges import LabRuntime, live_registry
    from backend.services.perception_lab.derivation_store import InMemoryDerivationStore
    from backend.services.perception_lab.families import registry
    from backend.services.perception_lab.orchestrator import PerceptionConductor
    from backend.services.perception_lab.planners.base import DirectCommand
    from backend.services.perception_lab.store import InMemoryLabStore
    from backend.services.perception_lab.field_transfer import import_session_bundle

    image = stripes(0, 64, 48)
    source = LabSource(origin="post", post_id="post_synthetic_orientation", image_digest=image.source_digest,
                       natural_width=64, natural_height=48)
    store, assets, readings = InMemoryLabStore(), InMemoryFieldAssets(), InMemoryDerivationStore()
    conductor = PerceptionConductor(store=store, registry=live_registry(
        LabRuntime(source=source, image_bytes=image.source_bytes, field_assets=assets)),
        source_probe=lambda: source.image_digest)
    machine = conductor.open_session(source=source, organ=OrganFamily.ORIENTATION_FLOW)
    direct = conductor.plan_direct(machine, DirectCommand("orientation_flow.tangent"))
    prompt = conductor.plan_prompt(machine, "show local orientation", planner="rules")
    assert direct.plan.resolved_steps[0].operation == prompt.plan.resolved_steps[0].operation
    first = conductor.execute(machine, direct.plan, confirmed=True)
    second = conductor.execute(machine, prompt.plan, confirmed=True)
    assert first.run.outcome.value == second.run.outcome.value == "ready"
    artifact = first.artifacts[0]
    assert artifact.measurement.payload.manifest["measurement_hash"] == second.artifacts[0].measurement.payload.manifest["measurement_hash"]
    assert first.run.source_digest_before == first.run.source_digest_after == image.source_digest
    monkeypatch.setattr(route, "_store", lambda: store)
    monkeypatch.setattr(route, "_field_assets", lambda: assets)
    monkeypatch.setattr(route, "_derivation_store", lambda: readings)
    app = FastAPI(); app.include_router(route.router)
    session_id = machine.session.session_id
    path = f"/sessions/{session_id}/fields/{artifact.identity.artifact_id}/consume"
    with TestClient(app) as client:
        response = client.post(path, json={"operation": "orientation_flow.trace", "points": [[32, 24]],
                                           "parameters": {"max_length": 4}})
        assert response.status_code == 201, response.text
        record = response.json()["derivation"]
        assert record["input_artifact_ids"] == [artifact.identity.artifact_id]
        assert record["measurements"]["result"]["paths"][0]["stop_reason"] == "max_length"
        bundle = client.get(f"/sessions/{session_id}/export").json()
    fresh, fresh_assets, fresh_readings = InMemoryLabStore(), InMemoryFieldAssets(), InMemoryDerivationStore()
    monkeypatch.setitem(registry.REGISTRY, "orientation_flow", replace(family.MODULE,
        producers={key: lambda *_: pytest.fail("saved reuse invoked producer") for key in family.MODULE.producers}))
    receipt = import_session_bundle(bundle, store=fresh, derivation_store=fresh_readings,
                                    asset_store=fresh_assets, target_source=source)
    imported_id = receipt["identity_map"][artifact.identity.artifact_id]
    imported = fresh.get_artifact(imported_id)
    assert imported.measurement.payload.manifest["measurement_hash"] == artifact.measurement.payload.manifest["measurement_hash"]
    imported_trace = fresh_readings.get(receipt["identity_map"][record["derivation_id"]])
    assert imported_trace.input_artifact_ids == [imported_id]
    monkeypatch.setattr(route, "_store", lambda: fresh)
    monkeypatch.setattr(route, "_field_assets", lambda: fresh_assets)
    monkeypatch.setattr(route, "_derivation_store", lambda: fresh_readings)
    with TestClient(app) as client:
        response = client.post(f"/sessions/{imported.identity.session_id}/fields/{imported_id}/consume",
            json={"operation": "orientation_flow.trace", "points": [[32, 24]], "parameters": {"max_length": 4}})
        assert response.status_code == 201, response.text
        assert response.json()["derivation"]["measurements"]["result"] == record["measurements"]["result"]
