"""Model-free readers for an explicit directed camera-normal convention.

These functions do not admit a model, produce normals, or register a live form.
The affine transform places samples in the image; it never rotates camera vectors.
Source/working sizes, intrinsics (calibrated or assumed), preprocessing and actual
producer must additionally be retained in a future producer's record provenance.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from backend.services.perception_lab.field_data import (
    FieldError, SampleGrid, decode_grid, path_sample,
)

NORMAL_CONVENTION = (
    "directed-unit-camera-normal.v1; right-handed; +x=image-right; +y=image-down; "
    "+z=away-from-camera; locations=field-pixel-xy-topleft; "
    "source_to_field-transforms-locations-not-vectors; no-calibration-implied"
)
NORMAL_CHANNELS = [
    {"name": "nx", "quantity": "camera_normal_x", "unit": "1"},
    {"name": "ny", "quantity": "camera_normal_y", "unit": "1"},
    {"name": "nz", "quantity": "camera_normal_z", "unit": "1"},
]
UNIT_TOLERANCE = 1e-4


def validate_normal_grid(grid: SampleGrid) -> SampleGrid:
    """Refuse unknown conventions instead of guessing axis order/sign or flipping z.

    Storage integrity/affine/dimensions are checked by the shared decoder. Repeat
    sample invariants here because callers can construct SampleGrid directly.
    """
    if not isinstance(grid, SampleGrid):
        raise FieldError("a decoded saved normal SampleGrid is required")
    meta = grid.metadata
    if (meta.get("kind") != "normal_camera_3d" or meta.get("frame") != "camera_xyz"
            or meta.get("channels") != NORMAL_CHANNELS or meta.get("units") != "1"
            or meta.get("value_convention") != NORMAL_CONVENTION):
        raise FieldError("unsupported directed camera-normal convention, channels or units")
    shape = meta.get("shape")
    if (not isinstance(shape, list) or len(shape) != 3 or shape[2] != 3
            or any(type(n) is not int or n < 1 for n in shape)
            or len(grid.values) != math.prod(shape)
            or len(grid.valid) != shape[0] * shape[1]):
        raise FieldError("normal values and validity must match [height,width,3]")
    for index, valid in enumerate(grid.valid):
        vector = grid.values[index * 3:index * 3 + 3]
        if (type(valid) is not bool
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in vector)):
            raise FieldError("normal samples require finite numbers and boolean validity")
        if not valid and any(value != 0 for value in vector):
            raise FieldError("invalid normals require zero storage; unknown is not a zero vector")
        if valid and abs(math.hypot(*vector) - 1) > UNIT_TOLERANCE:
            raise FieldError("valid directed camera normals must be unit length")
    return grid


def read_normal_field(manifest, reference, *, get_asset=None) -> SampleGrid:
    """Verify the existing bounded lossless carrier, then the family semantics."""
    return validate_normal_grid(decode_grid(manifest, reference, get_asset=get_asset))


def normal_path(grid: SampleGrid, points: Sequence[Sequence[int]]) -> list[dict]:
    """Read exact saved vectors at explicit field cells, never interpolated normals."""
    validate_normal_grid(grid)
    if (not isinstance(points, (list, tuple)) or not 1 <= len(points) <= 4096
            or any(not isinstance(point, (list, tuple)) or len(point) != 2 for point in points)):
        raise FieldError("normal path needs 1–4096 explicit [x,y] field cells")
    return [{**sample, "channels": [dict(channel) for channel in sample["channels"]]}
            for sample in path_sample(grid, points)]


def angular_change_profile(grid: SampleGrid, points, parameters=None) -> dict:
    """Pure saved-field consumer: directed angle to a declared pixel neighbour.

    Compatible with the shared (grid, points, parameters) consumer seam, but not
    registered while Surface Form has no admitted producer/form. Boundaries and
    invalid neighbours stay unknown; there is no interpolation, wrap or bridging.
    """
    samples = normal_path(grid, points)
    parameters = {} if parameters is None else parameters
    if not isinstance(parameters, Mapping) or set(parameters) - {"offset_x", "offset_y"}:
        raise FieldError("angular change accepts only offset_x and offset_y")
    dx, dy = parameters.get("offset_x", 1), parameters.get("offset_y", 0)
    if (type(dx) is not int or type(dy) is not int or abs(dx) > 64 or abs(dy) > 64
            or (dx == 0 and dy == 0)):
        raise FieldError("neighbour offset must be nonzero integer pixels within [-64,64]")
    height, width, _ = grid.shape
    readings, angles = [], []
    for sample in samples:
        x, y = sample["x"], sample["y"]
        nx, ny = x + dx, y + dy
        reading = {"x": x, "y": y, "neighbour": [nx, ny], "valid": False,
                   "normal": sample["values"], "neighbour_normal": None,
                   "angle_degrees": None, "status": "invalid_source"}
        if sample["valid"]:
            if not (0 <= nx < width and 0 <= ny < height):
                reading["status"] = "outside_field"
            elif not grid.valid[ny * width + nx]:
                reading["status"] = "invalid_neighbour"
            else:
                a = sample["values"]
                b = list(grid.values[(ny * width + nx) * 3:(ny * width + nx) * 3 + 3])
                cross = (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2],
                         a[0]*b[1] - a[1]*b[0])
                # atan2 avoids acos domain errors from roundoff near 0/180°.
                angle = math.degrees(math.atan2(math.hypot(*cross), sum(u*v for u, v in zip(a, b))))
                reading.update(valid=True, neighbour_normal=b, angle_degrees=angle, status="valid")
                angles.append(angle)
        readings.append(reading)
    return {
        "schema_version": "surface-normal-angular-profile.v1",
        "quantity": "angular_change_of_directed_camera_normals", "unit": "degree",
        "algorithm": "atan2(cross_product_length,dot_product)",
        "value_convention": "0–180 degrees; not physical curvature or inverse metres",
        "input_measurement_hash": grid.measurement_hash,
        "source_digest": grid.metadata["source_digest"],
        "source_to_field": list(grid.metadata["source_to_field"]),
        "location_frame": "image_pixel_xy_topleft", "vector_frame": "camera_xyz",
        "normal_convention": NORMAL_CONVENTION, "neighbour_offset_pixels": [dx, dy],
        "sample_count": len(readings), "valid_count": len(angles), "samples": readings,
        "mean_degrees": sum(angles) / len(angles) if angles else None,
        "max_degrees": max(angles) if angles else None,
    }
