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
