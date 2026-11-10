"""Analytical controls only: no model-quality or live-family claims."""
from __future__ import annotations

import copy
import json
import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from backend.services.perception_lab.field_data import FieldError, decode_grid, encode_grid
from backend.services.perception_lab.families.surface_form import MODULE
from backend.services.perception_lab.families.surface_form_normals import (
    NORMAL_CHANNELS, NORMAL_CONVENTION, angular_change_profile, normal_path,
    read_normal_field, validate_normal_grid,
)

FIXTURE = json.loads((Path(__file__).parents[2] / "contracts/perception-lab-families/"
                     "surface_form-normal-fixture.v1.json").read_text())


def field(vectors=None, valid=None, *, shape=None, transform=None):
    vectors = [[1, 0, 0], [0, 1, 0], [0, 0, 1]] if vectors is None else vectors
    metadata = copy.deepcopy(FIXTURE["metadata"])
    metadata["shape"] = shape or [1, len(vectors), 3]
    metadata["source_to_field"] = transform or metadata["source_to_field"]
    manifest, ref = encode_grid(metadata, [n for vector in vectors for n in vector],
                                [True] * len(vectors) if valid is None else valid)
    return read_normal_field(manifest, ref), manifest, ref


def test_family_stays_unavailable_without_live_producers_or_heavy_imports():
    assert MODULE.available is False
    assert MODULE.forms == MODULE.operations == MODULE.models == MODULE.dependencies == ()
    assert not MODULE.producers
    assert "checkpoint permission" in MODULE.reason and "DSINE" in MODULE.reason
    probe = subprocess.run([sys.executable, "-c", (
        "import sys; "
        "from backend.services.perception_lab.families import surface_form, surface_form_normals; "
        "assert not any(name.split('.')[0] in {'torch', 'torchvision', 'cv2', 'timm'} "
        "for name in sys.modules)"
    )], cwd=Path(__file__).parents[2], capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr


def test_public_fixture_uses_exact_shared_camera_convention():
    assert FIXTURE["execution_identity"] == "FIXTURE"
    assert FIXTURE["metadata"]["value_convention"] == NORMAL_CONVENTION
    assert FIXTURE["metadata"]["channels"] == NORMAL_CHANNELS
    manifest, ref = encode_grid(FIXTURE["metadata"], FIXTURE["preview"]["values"],
                               FIXTURE["preview"]["valid"])
    grid = read_normal_field(manifest, ref)
    assert grid.values == tuple(FIXTURE["preview"]["values"])
    assert normal_path(grid, [[6, 0]])[0]["values"] is None


@pytest.mark.parametrize("other,expected", [
    ([1, 0, 0], 0), ([0, 1, 0], 90), ([-1, 0, 0], 180),
    ([math.sqrt(.5), math.sqrt(.5), 0], 45),
])
def test_directed_angles_are_not_axial(other, expected):
    grid, _, _ = field([[1, 0, 0], other])
    result = angular_change_profile(grid, [[0, 0]], {})
    assert result["samples"][0]["angle_degrees"] == pytest.approx(expected)
    assert result["max_degrees"] == pytest.approx(expected)
    assert result["neighbour_offset_pixels"] == [1, 0]
    assert "not physical curvature" in result["value_convention"]
    json.dumps(result, allow_nan=False)


def test_plane_and_analytic_sphere_profile():
    plane, _, _ = field([[0, 0, -1]] * 4)
    assert angular_change_profile(plane, [[0, 0], [1, 0], [2, 0]])["max_degrees"] == 0
    # Equatorial points on a unit sphere, not a normal estimate from any image.
    vectors = [[math.sin(math.radians(a)), 0, -math.cos(math.radians(a))]
               for a in [-60, -30, 0, 30, 60]]
    sphere, _, _ = field(vectors)
    result = angular_change_profile(sphere, [[x, 0] for x in range(4)])
    assert [s["angle_degrees"] for s in result["samples"]] == pytest.approx([30] * 4, abs=1e-5)


def test_offset_neighbourhood_boundaries_invalid_and_no_wrapping():
    grid, _, _ = field([[1, 0, 0], [0, 0, 0], [-1, 0, 0], [0, 1, 0]],
                       [True, False, True, True], shape=[2, 2, 3])
    horizontal = angular_change_profile(grid, [[0, 0], [1, 0], [1, 1]])
    assert [s["status"] for s in horizontal["samples"]] == [
        "invalid_neighbour", "invalid_source", "outside_field"]
    assert all(s["angle_degrees"] is None for s in horizontal["samples"])
    assert horizontal["valid_count"] == 0
    assert horizontal["mean_degrees"] is horizontal["max_degrees"] is None
    vertical = angular_change_profile(grid, [[0, 0]], {"offset_x": 0, "offset_y": 1})
    assert vertical["samples"][0]["angle_degrees"] == 180
    negative = angular_change_profile(grid, [[0, 1]], {"offset_x": 0, "offset_y": -1})
    assert negative["samples"][0]["angle_degrees"] == 180


@pytest.mark.parametrize("params", [[], "x", {"offset_x": True}, {"offset_x": 1.0},
    {"offset_y": None}, {"offset_x": 0}, {"offset_y": 65}, {"offset_x": -65},
    {"radius": 1}, {"curvature": True}])
def test_invalid_or_unknown_parameters_are_refused(params):
    with pytest.raises(FieldError):
        angular_change_profile(field()[0], [[0, 0]], params)


@pytest.mark.parametrize("points", [None, [], [[0]], [[0, 0, 0]], ["0,0"],
    [[-1, 0]], [[3, 0]], [[0, 1]], [[.5, 0]], [[True, 0]], [[0, 0]] * 4097])
def test_invalid_points_are_refused(points):
    with pytest.raises(FieldError):
        angular_change_profile(field()[0], points)


@pytest.mark.parametrize("change", [
    {"kind": "scalar"}, {"frame": "image_pixel_xy_topleft"}, {"units": "metre"},
    {"channels": list(reversed(NORMAL_CHANNELS))}, {"value_convention": "unknown camera"},
    {"shape": [1, 4, 3]},
])
def test_incompatible_field_semantics_refused(change):
    grid, _, _ = field()
    with pytest.raises(FieldError):
        validate_normal_grid(replace(grid, metadata={**grid.metadata, **change}))


@pytest.mark.parametrize("values,valid", [
    ((0, 0, 0), (True,)), ((1.01, 0, 0), (True,)), ((float("nan"), 0, 0), (True,)),
    ((float("inf"), 0, 0), (True,)), ((1, 0, 0), (False,)), ((True, 0, 0), (True,)),
    ((1, 0, 0), (1,)),
])
def test_semantically_bad_samples_refused_even_when_grid_is_constructed_directly(values, valid):
    grid, _, _ = field([[1, 0, 0]])
    with pytest.raises(FieldError):
        validate_normal_grid(replace(grid, values=values, valid=valid))


def test_roundtrip_reuse_keeps_hash_values_provenance_without_producer():
    original, manifest, ref = field()
    before = copy.deepcopy(original)
    transferred = read_normal_field(json.loads(json.dumps(manifest)),
                                    json.loads(ref.model_dump_json()))
    assert transferred == original
    points = [[0, 0], [1, 0], [2, 0]]
    first = angular_change_profile(original, points)
    assert angular_change_profile(transferred, points) == first
    assert original == before
    assert first["input_measurement_hash"] == original.measurement_hash
    first["source_to_field"][0] = 999
    first["samples"][0]["normal"][0] = 999
    normal_path(original, [[0, 0]])[0]["channels"][0]["quantity"] = "changed"
    assert original == before


@pytest.mark.parametrize("transform", [
    [-1, 0, 2, 0, 1, 0, 0, 0, 1],  # source reflection changes locations only
    [0, -1, 1, 1, 0, 0, 0, 0, 1],  # source quarter-turn changes locations only
    [.5, 0, 1, 0, .5, 2, 0, 0, 1],
])
def test_source_image_transform_does_not_silently_rotate_camera_normals(transform):
    grid, _, _ = field(transform=transform)
    result = angular_change_profile(grid, [[0, 0]])
    assert result["source_to_field"] == transform
    assert result["samples"][0]["normal"] == [1, 0, 0]
    assert result["samples"][0]["angle_degrees"] == 90


def test_explicit_vector_rotation_and_reflection_preserve_pair_angle():
    vectors = [[1, 0, 0], [math.sqrt(.5), math.sqrt(.5), 0]]
    original = angular_change_profile(field(vectors)[0], [[0, 0]])["max_degrees"]
    for mapped in ([[-y, x, z] for x, y, z in vectors],
                   [[x, -y, z] for x, y, z in vectors]):
        assert angular_change_profile(field(mapped)[0], [[0, 0]])["max_degrees"] == original


def test_corrupted_lossless_carrier_refused_before_normal_reader():
    _, manifest, ref = field()
    with pytest.raises(FieldError, match="digest"):
        read_normal_field(manifest, ref.model_copy(update={"digest": "sha256:" + "b" * 64}))
    with pytest.raises(FieldError, match="hash"):
        read_normal_field({**manifest, "measurement_hash": "sha256:" + "b" * 64}, ref)
    bad = copy.deepcopy(manifest)
    bad["metadata"]["source_to_field"] = [0] * 9
    with pytest.raises(FieldError):
        decode_grid(bad, ref)
