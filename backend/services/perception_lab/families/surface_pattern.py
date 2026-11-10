"""CPU multiscale image pattern, distinct from inferred physical material."""
from __future__ import annotations

import math
from typing import Sequence

from backend.services import cpu_perceptual_service as cpu
from backend.services.perception_lab.field_data import FieldError, SampleGrid
from .base import FamilyForm, FamilyModule, FamilyOperation, ProducedField

FORM = "surface_pattern.response_bank"
OPERATION = "surface_pattern.inspect_scales"
PRODUCER = "surface_pattern.cpu_gabor"


def _transform(source_to_working: Sequence[int], working_size: tuple[int, int],
               shape: Sequence[int]) -> list[float]:
    width, height = working_size
    field_height, field_width = shape[:2]
    sx = (field_width - 1) / (width - 1) if width > 1 else 1.0
    sy = (field_height - 1) / (height - 1) if height > 1 else 1.0
    a, b, c, d, e, f, _, _, _ = source_to_working
    return [sx*a, sx*b, sx*c, sy*d, sy*e, sy*f, 0, 0, 1]


def produce(prepared, parameters, inputs, cancel) -> ProducedField:
    if inputs:
        raise ValueError("pattern measurement takes the whole prepared image, not implicit inputs")
    cancel.raise_if_cancelled()
    scale = parameters.get("scale_set", "fine_and_coarse")
    if scale not in {"fine_and_coarse", "fine", "coarse"}:
        raise ValueError("unknown scale set")
    wavelengths = {"fine_and_coarse": (6.0, 12.0), "fine": (6.0,),
                   "coarse": (12.0,)}[scale]
    result = cpu.response_bank(prepared.rgb_bytes, prepared.working_size,
                               wavelengths=wavelengths)
    cancel.raise_if_cancelled()
    h, w, count = result["shape"]
    alpha = prepared.alpha_bytes
    # Resize validity with nearest-neighbour so transparent pixels stay unknown.
    import cv2
    import numpy as np
    original = np.frombuffer(alpha, dtype=np.uint8).reshape(
        prepared.working_size[1], prepared.working_size[0])
    valid = cv2.resize(original, (w, h), interpolation=cv2.INTER_NEAREST) > 0
    data = result["values"].copy()
    data[~valid] = 0
    channels = [{"name": item["name"], "quantity": "local_gabor_response_rms",
                 "unit": "relative_encoded_luma_response"} for item in result["channels"]]
    metadata = {"version": 1, "shape": [h, w, count], "dtype": "float32-le",
                "kind": "multichannel", "channels": channels,
                "frame": "image_pixel_xy_topleft", "units": "relative_encoded_luma_response",
                "source_digest": prepared.source_digest,
                "source_to_field": _transform(prepared.source_to_working,
                                               prepared.working_size, result["shape"]),
                "value_convention": (f"{cpu.RESPONSE_VERSION}; {result['preprocessing']}; "
                                     f"{result['kernel']}; {result['border']}; "
                                     f"working-grid {w}x{h}; channels name wavelength in "
                                     "working pixels and filter orientation in degrees; "
                                     "nonnegative uncalibrated filter RMS")}
    return ProducedField(metadata, data.ravel().tolist(), valid.ravel().tolist(),
                         cpu.RESPONSE_VERSION, device="cpu")


def _check_grid(grid: SampleGrid) -> tuple[int, int, int]:
    meta = grid.metadata
    if (meta.get("kind") != "multichannel" or not meta.get("value_convention", "").startswith(
            cpu.RESPONSE_VERSION) or any(c["quantity"] != "local_gabor_response_rms"
                                      for c in meta["channels"])):
        raise FieldError("expected a compatible saved Gabor response bank")
    return grid.shape


def patch_descriptor(grid: SampleGrid, cells: Sequence[Sequence[int]]) -> dict:
    """Mean response per *named* channel over explicit valid field cells."""
    h, w, count = _check_grid(grid)
    if not cells or len(cells) > 4096:
        raise FieldError("patch needs 1–4096 explicit field cells")
    indices = set()
    for point in cells:
        if (len(point) != 2 or any(type(v) is not int for v in point)
                or not 0 <= point[0] < w or not 0 <= point[1] < h):
            raise FieldError("patch cell lies outside the saved field")
        indices.add(point[1]*w + point[0])
    good = sorted(i for i in indices if grid.valid[i])
    if not good:
        raise FieldError("patch contains no valid field cells")
    means = [sum(grid.values[i*count+j] for i in good)/len(good) for j in range(count)]
    return {"field_hash": grid.measurement_hash,
            "support": [[i % w, i // w] for i in sorted(indices)],
            "valid_support": [[i % w, i // w] for i in good],
            "channels": grid.metadata["channels"], "mean_response": means}


def compare_patches(grid: SampleGrid, reference: dict, *, patch_width: int,
                    patch_height: int) -> dict:
    """Cosine similarity of aligned local response descriptors on the same saved grid."""
    h, w, count = _check_grid(grid)
    if (reference.get("field_hash") != grid.measurement_hash
            or reference.get("channels") != grid.metadata["channels"]):
        raise FieldError("reference descriptor belongs to another field or channel space")
    if (type(patch_width) is not int or type(patch_height) is not int
            or not 1 <= patch_width <= w or not 1 <= patch_height <= h):
        raise FieldError("invalid comparison patch dimensions")
    ref = reference["mean_response"]
    if len(ref) != count or any(not math.isfinite(v) for v in ref):
        raise FieldError("invalid reference descriptor")
    norm_ref = math.sqrt(sum(v*v for v in ref))
    if norm_ref < 1e-12:
        raise FieldError("reference has no measured pattern response")
    values, valid = [], []
    for y in range(h):
        for x in range(w):
            x0 = max(0, x - patch_width//2)
            y0 = max(0, y - patch_height//2)
            x1, y1 = min(w, x0 + patch_width), min(h, y0 + patch_height)
            ids = [yy*w + xx for yy in range(y0, y1) for xx in range(x0, x1)]
            if not ids or not all(grid.valid[i] for i in ids):
                values.append(0.0); valid.append(False); continue
            local = [sum(grid.values[i*count+j] for i in ids)/len(ids) for j in range(count)]
            norm = math.sqrt(sum(v*v for v in local))
            values.append(sum(a*b for a, b in zip(ref, local))/(norm_ref*norm)
                          if norm > 1e-12 else 0.0)
            valid.append(norm > 1e-12)
    return {"shape": [h, w], "values": values, "valid": valid,
            "reference": reference, "patch_size": [patch_width, patch_height],
            "quantity": "cosine_similarity_of_named_gabor_response_descriptors"}


MODULE = FamilyModule(
    "surface_pattern", "Surface pattern", cpu.is_available(),
    "CPU Gabor bank available" if cpu.is_available() else "OpenCV or NumPy is unavailable",
    forms=(FamilyForm(FORM, "Multiscale pattern response", "local_gabor_response_rms",
                      "Named scale and orientation filter responses; not material identity.",
                      ("selected_scale", "paired_scales", "profile")),),
    operations=(FamilyOperation(OPERATION, "Inspect pattern at different scales", FORM, PRODUCER,
                                {"scale_set": {"type": "enum", "required": False,
                                               "enum": ["fine_and_coarse", "fine", "coarse"],
                                               "description": "Filter wavelengths are 6 and 12 resized-grid pixels; default uses both."}},
                                ("show texture at the selected scale",)),),
    producers={PRODUCER: produce},
    dependencies=({"package": "opencv-python", "version": "5.0.0.93", "license": "Apache-2.0",
                   "admitted": True},
                  {"package": "numpy", "version": "2.5.1", "license": "BSD-3-Clause",
                   "admitted": True}),
)
