"""Synthetic controls for portable numeric fields; no image or model service is called."""
from __future__ import annotations

import base64
import gzip
import io

import pytest
from PIL import Image

from backend.services.perception_lab.field_assets import InMemoryFieldAssets
from backend.services.perception_lab.field_data import (
    FieldError, compare_fields, decode_grid, encode_grid, path_sample, point_sample,
    roi_sample, validate_source_transform)
from backend.services.perception_lab.image_preparation import prepare_image


SOURCE = "sha256:" + "a" * 64


def metadata(kind, shape, channels, *, frame="image_pixel_xy_topleft"):
    return {"version": 1, "shape": shape, "dtype": "float32-le", "kind": kind,
            "channels": [{"name": name, "quantity": quantity, "unit": unit}
                         for name, quantity, unit in channels],
            "frame": frame, "units": "relative", "source_digest": SOURCE,
            "source_to_field": [1, 0, 0, 0, 1, 0, 0, 0, 1],
            "value_convention": "relative to producer output"}


@pytest.mark.parametrize("kind,shape,channels,values", [
    ("scalar", [2, 3, 1], [("v", "luminance", "relative")], [0, .25, .5, .75, 1, 0]),
    ("scalar", [1, 4, 1], [("v", "constant", "relative")], [.5] * 4),
    ("directed_vector_2d", [1, 2, 2], [("x", "image_x", "pixel"), ("y", "image_y", "pixel")],
     [1, 0, 0, -1]),
    ("axial_orientation_2d", [1, 2, 2], [("cos2", "cos_double_angle", "relative"),
                                         ("sin2", "sin_double_angle", "relative")],
     [1, 0, .999, -.0447]),
    ("normal_camera_3d", [1, 2, 3], [("nx", "camera_x", "relative"),
                                     ("ny", "camera_y", "relative"),
                                     ("nz", "camera_z", "relative")],
     [0, 0, 1, 0, 1, 0]),
    ("multichannel", [1, 2, 4], [(f"c{i}", f"quantity_{i}", "relative") for i in range(4)],
     [.1, .2, .3, .4, .5, .6, .7, .8]),
])
def test_exact_roundtrip(kind, shape, channels, values):
    frame = "camera_xyz" if kind == "normal_camera_3d" else "image_pixel_xy_topleft"
    meta = metadata(kind, shape, channels, frame=frame)
    manifest, ref = encode_grid(meta, values, [True] * (shape[0]*shape[1]))
    read = decode_grid(manifest, ref)
    assert read.shape == tuple(shape)
    assert read.measurement_hash == manifest["measurement_hash"]
    assert len(read.values) == len(values)
    assert read.values == decode_grid(manifest, ref).values
    assert point_sample(read, shape[1]-1, shape[0]-1)["values"] == list(read.values[-shape[2]:])


def test_invalid_cells_and_consumers():
    meta = metadata("scalar", [2, 3, 1], [("v", "luminance", "relative")])
    manifest, ref = encode_grid(meta, [1, 0, 3, 4, 5, 6],
                                [True, False, True, True, True, True])
    grid = decode_grid(manifest, ref)
    assert point_sample(grid, 1, 0)["values"] is None
    assert path_sample(grid, [(0, 0), (1, 0)])[-1]["valid"] is False
    assert roi_sample(grid, [(0, 0), (1, 0), (2, 0)])["mean"] == [2]
    assert compare_fields(grid, grid)["max_absolute_difference"] == 0


def test_large_assets_and_remote_rejection():
    asset = InMemoryFieldAssets()
    meta = metadata("scalar", [256, 256, 1], [("v", "random", "relative")])
    values = [((i * 2003) % 65521) / 65521 for i in range(256*256)]
    manifest, ref = encode_grid(meta, values, [True] * len(values), put_asset=asset.put)
    assert ref.uri.startswith("lab-asset:")
    assert decode_grid(manifest, ref, get_asset=asset.get).measurement_hash == manifest["measurement_hash"]
    with pytest.raises(FieldError, match="remote or arbitrary"):
        decode_grid(manifest, ref.model_copy(update={"uri": "https://example.com/field"}),
                    get_asset=asset.get)


def test_corruption_and_bomb_refused():
    meta = metadata("scalar", [1, 1, 1], [("v", "luminance", "relative")])
    manifest, ref = encode_grid(meta, [1], [True])
    with pytest.raises(FieldError, match="digest"):
        decode_grid(manifest, ref.model_copy(update={"digest": SOURCE}))
    with pytest.raises(FieldError, match="manifest"):
        decode_grid({**manifest, "metadata": {**meta, "shape": [1, 2, 1]}}, ref)
    bomb = gzip.compress(b"0" * (64 * 1024 * 1024 + 1), mtime=0)
    from hashlib import sha256
    encoded = "data:application/gzip;base64," + base64.b64encode(bomb).decode()
    with pytest.raises(FieldError, match="decompressed"):
        decode_grid(manifest, ref.model_copy(update={"uri": encoded,
                          "digest": "sha256:" + sha256(bomb).hexdigest(), "bytes": len(bomb)}))


def test_source_preparation_keeps_original_bytes_and_alpha():
    image = Image.new("RGBA", (3, 2), (120, 80, 20, 0))
    output = io.BytesIO()
    image.save(output, format="PNG")
    original = output.getvalue()
    prepared = prepare_image(original)
    assert prepared.source_bytes == original
    assert prepared.source_digest != prepared.working_rgb_digest
    assert prepared.alpha_bytes == bytes([0] * 6)
    assert prepared.source_to_working == (1, 0, 0, 0, 1, 0, 0, 0, 1)


def test_cross_source_compare_needs_decoded_image_proof():
    image = Image.new("RGB", (2, 1), (80, 40, 20))
    png, bmp = io.BytesIO(), io.BytesIO()
    image.save(png, format="PNG")
    image.save(bmp, format="BMP")
    left_source, right_source = prepare_image(png.getvalue()), prepare_image(bmp.getvalue())
    left_meta = metadata("scalar", [1, 2, 1], [("v", "signal", "relative")])
    left_meta["source_digest"] = left_source.source_digest
    right_meta = {**left_meta, "source_digest": right_source.source_digest}
    lm, lr = encode_grid(left_meta, [.2, .4], [True, True])
    rm, rr = encode_grid(right_meta, [.2, .4], [True, True])
    left, right = decode_grid(lm, lr), decode_grid(rm, rr)
    with pytest.raises(FieldError, match="source mismatch"):
        compare_fields(left, right)
    proof = validate_source_transform(png.getvalue(), bmp.getvalue())
    assert compare_fields(left, right, source_transform=proof)["max_absolute_difference"] == 0
