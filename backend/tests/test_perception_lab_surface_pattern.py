import io
import math

import numpy as np
import pytest
from PIL import Image

from backend.services import cpu_perceptual_service as cpu
from backend.services.perception_lab.field_data import FieldError, SampleGrid, decode_grid, encode_grid
from backend.services.perception_lab.image_preparation import prepare_image
from backend.services.perception_lab.families.surface_pattern import (
    MODULE, compare_patches, patch_descriptor, produce)


class Cancel:
    def raise_if_cancelled(self):
        pass


def prepared(array, mode="RGB"):
    image = Image.fromarray(array, mode)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return prepare_image(out.getvalue())


def field(array):
    output = produce(prepared(array), {}, (), Cancel())
    manifest, ref = encode_grid(output.metadata, output.values, output.valid)
    return decode_grid(manifest, ref)


def test_constant_is_unstructured_and_legacy_contract_survives():
    image = np.full((40, 80, 3), 120, dtype=np.uint8)
    response = field(image)
    assert response.shape == (40, 80, 8)
    assert max(abs(v) for v in response.values) < 1e-6
    legacy = cpu.analyze(Image.fromarray(image))
    assert set(legacy) == {"energy", "coherence", "grid"}
    assert len(legacy["energy"]) == 256


def test_named_scale_response_and_deterministic_roundtrip():
    x = np.arange(128)
    stripes = (127 + 100 * np.cos(2 * np.pi * x / 6)).astype(np.uint8)
    image = np.repeat(stripes[None, :, None], 64, axis=0)
    image = np.repeat(image, 3, axis=2)
    one, two = field(image), field(image)
    assert one.measurement_hash == two.measurement_hash
    assert one.values == two.values
    assert one.metadata["channels"][0]["name"] == "lambda6_theta0"
    assert one.metadata["source_to_field"] == [1, 0, 0, 0, 1, 0, 0, 0, 1]
    assert max(one.values) > .001
    patch = patch_descriptor(one, [[x, y] for y in range(8, 16) for x in range(8, 16)])
    assert patch["field_hash"] == one.measurement_hash
    comparison = compare_patches(one, patch, patch_width=8, patch_height=8)
    assert comparison["shape"] == [64, 128]
    assert comparison["valid"][10*128+10]
    assert 0 <= comparison["values"][10*128+10] <= 1.00001


def test_alpha_support_and_incompatible_reference():
    rgba = np.full((32, 64, 4), 255, dtype=np.uint8)
    rgba[:, :8, 3] = 0
    output = produce(prepared(rgba, "RGBA"), {}, (), Cancel())
    grid = SampleGrid(output.metadata, tuple(output.values), tuple(output.valid), "hash")
    assert not grid.valid[0]
    assert all(v == 0 for v in grid.values[:8])
    with pytest.raises(FieldError, match="valid"):
        patch_descriptor(grid, [[0, 0]])
    patch = patch_descriptor(grid, [[16, 8]])
    patch["field_hash"] = "another"
    with pytest.raises(FieldError, match="another field"):
        compare_patches(grid, patch, patch_width=2, patch_height=2)


def test_parameter_and_shape_rejection():
    rgb = bytes(40 * 30 * 3)
    with pytest.raises(ValueError):
        cpu.response_bank(rgb, (40, 30), wavelengths=(3,))
    with pytest.raises(ValueError):
        cpu.response_bank(rgb, (40, 31))
    result = cpu.response_bank(rgb, (40, 30), wavelengths=(12,))
    assert result["shape"] == [30, 40, 4]
    assert MODULE.available


def test_checkerboard_noise_and_scale_sensitivity():
    yy, xx = np.indices((96, 128))
    checker = (((xx // 4 + yy // 4) % 2) * 255).astype(np.uint8)
    noise = np.random.default_rng(7).integers(0, 256, (96, 128), dtype=np.uint8)
    for pattern in (checker, noise):
        rgb = np.repeat(pattern[:, :, None], 3, axis=2)
        fine = cpu.response_bank(rgb.tobytes(), (128, 96), wavelengths=(6,))
        coarse = cpu.response_bank(rgb.tobytes(), (128, 96), wavelengths=(12,))
        assert fine["shape"] == coarse["shape"] == [96, 128, 4]
        assert float(np.max(fine["values"])) > 0
        assert not np.array_equal(fine["values"], coarse["values"])
        assert np.isfinite(fine["values"]).all()
        assert np.isfinite(coarse["values"]).all()
    # Reflected borders produce finite responses without a dark zero-padded frame.
    assert np.isfinite(fine["values"][:4]).all()
