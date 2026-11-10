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
    a, _, c, _, e, f, *_ = result.metadata["source_to_field"]
    assert a == .256 and e == .255
    assert a*499.5+c == 127.5 and e*199.5+f == 50.5
    meta = json.loads(result.metadata["value_convention"])
    assert meta["source_working_size"] == [1000, 400]
    assert "inverse" in meta["source_direction"]


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
