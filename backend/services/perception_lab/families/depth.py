"""Depth Anything's saved, source-aligned relative inverse depth — never metres."""
from __future__ import annotations

from backend.services.perception_lab.field_data import FieldError, path_sample, roi_sample
from .base import FamilyForm, FamilyModule, FamilyOperation, ProducedField
from . import depth_spec

FORM = "depth.relative_inverse_depth"
PRODUCER = "depth.anything_v2_small"
QUANTITY = "estimated_relative_inverse_depth"


def _check_saved(grid, parameters):
    if parameters:
        raise FieldError("Depth readers take explicit field cells and no measurement parameters")
    if (grid.metadata["kind"] != "scalar" or grid.metadata["units"] != "model_relative"
            or grid.metadata["channels"] != [{"name": "relative_inverse_depth",
                                             "quantity": QUANTITY, "unit": "model_relative"}]
            or not grid.metadata["value_convention"].startswith(depth_spec.DENSE_VERSION + ";")
            or "larger=nearer" not in grid.metadata["value_convention"]):
        raise FieldError("Expected a compatible saved larger-nearer relative inverse-depth field")


def profile(grid, points, parameters):
    """Exact, ordered saved-cell samples; no interpolation and no producer imports."""
    _check_saved(grid, parameters)
    return {"quantity": QUANTITY, "unit": "model_relative", "larger_means": "nearer",
            "samples": path_sample(grid, points), "interpolation": "none; explicit field cells",
            "field_hash": grid.measurement_hash, "model_invocations": 0}


def regional_summary(grid, points, parameters):
    """Unique explicit cells, not independently inferred crops or bounding rectangles."""
    _check_saved(grid, parameters)
    samples = path_sample(grid, points)  # validates bounds before deduplication
    unique = list(dict.fromkeys((sample["x"], sample["y"]) for sample in samples))
    result = roi_sample(grid, unique)
    values = sorted(sample["values"][0] for sample in path_sample(grid, unique) if sample["valid"])
    return {**result, "requested_count": len(points), "minimum": min(values) if values else None,
            "maximum": max(values) if values else None, "larger_means": "nearer",
            "quantity": QUANTITY, "unit": "model_relative", "field_hash": grid.measurement_hash,
            "model_invocations": 0, "support": "unique explicit native-field cells"}


def produce(prepared, parameters, inputs, cancel) -> ProducedField:
    """Infer the whole prepared image; ROI consumers only read the saved result."""
    if inputs:
        raise ValueError("Depth estimates the whole image; sample an ROI on the saved field instead")
    if set(parameters) - {"resolution", "alpha_min"}:
        raise ValueError("Unknown Depth measurement parameter")
    resolution = parameters.get("resolution", "standard")
    alpha_min = parameters.get("alpha_min", 1)
    if resolution not in {"standard", "compact"}:
        raise ValueError("resolution must be standard or compact")
    if type(alpha_min) is not int or not 1 <= alpha_min <= 255:
        raise ValueError("alpha_min must be an integer from 1 to 255")
    cancel.raise_if_cancelled()
    from backend.services import depth_service
    from PIL import Image
    import numpy as np
    image = Image.frombytes("RGB", prepared.working_size, prepared.rgb_bytes)
    try:
        result = depth_service.estimate_dense(image, resolution=resolution)
    finally:
        # No GPU residency may outlive a Lab call's exclusive lease. CPU values stay cached.
        depth_service.unload()
    cancel.raise_if_cancelled()
    values = result["depth"].copy()
    h, w = result["native_shape"]
    if values.shape != (h, w) or result["valid"].shape != (h, w):
        raise ValueError("Depth output shape differs from its declared native raster")
    alpha = Image.frombytes("L", prepared.working_size, prepared.alpha_bytes)
    valid = (np.asarray(alpha.resize((w, h), Image.Resampling.NEAREST)) >= alpha_min)
    valid &= result["valid"] & np.isfinite(values)
    values[~valid] = 0
    transform = (np.asarray(result["working_to_field"]).reshape(3, 3)
                 @ np.asarray(prepared.source_to_working).reshape(3, 3)).ravel().tolist()
    convention = (f"{depth_service.DENSE_VERSION}; {depth_service.REVISION}; larger=nearer; "
                  "raw model relative inverse-depth; whole-image inference; no metric units, "
                  "camera calibration or cross-image scale; " + result["preprocessing"])
    metadata = {"version": 1, "shape": [h, w, 1], "dtype": "float32-le",
                "kind": "scalar", "channels": [{"name": "relative_inverse_depth",
                "quantity": QUANTITY, "unit": "model_relative"}],
                "frame": "image_pixel_xy_topleft", "units": "model_relative",
                "source_digest": prepared.source_digest, "source_to_field": transform,
                "value_convention": convention}
    receipt = {key: result[key] for key in ("load_ms", "inference_ms", "model_cached",
               "cache_hit", "invocation_count", "native_shape", "input_shape", "working_size")}
    receipt.update(source_size=list(prepared.source_size), alpha_min=alpha_min,
                   checkpoint_digest="sha256:" + depth_service.CHECKPOINT_SHA256,
                   validity="finite native prediction AND nearest source alpha >= alpha_min")
    return ProducedField(metadata, values.ravel().tolist(), valid.ravel().tolist(),
                         depth_service.REVISION, depth_service.CHECKPOINT,
                         result["device"], receipt)


def runtime_probe(_):
    from backend.services import depth_service
    return depth_service.dense_readiness()


MODULE = FamilyModule(
    "depth", "Depth", True,
    "Pinned Depth Anything V2 Small; runtime checks local checkpoint availability without loading it.",
    forms=(FamilyForm(FORM, "Relative depth", QUANTITY,
                      "Whole-image model estimate; larger values nearer, not metric distance.",
                      ("near_far", "grayscale", "profile")),),
    operations=(FamilyOperation("depth.estimate", "Estimate relative depth", FORM, PRODUCER,
        {"resolution": {"type": "enum", "required": False, "enum": ["standard", "compact"],
                        "description": "Whole-image processor target: standard 518 or compact 392. Changes measurement resolution, not display."},
         "alpha_min": {"type": "integer", "required": False, "minimum": 1, "maximum": 255,
                       "description": "Source alpha below this threshold is unknown. Default 1."}},
        ("estimate relative depth",), True),),
    producers={PRODUCER: produce},
    models=({"key": depth_spec.CHECKPOINT, "revision": depth_spec.REVISION,
             "license": "Apache-2.0", "checkpoint_digest": "sha256:" + depth_spec.CHECKPOINT_SHA256,
             "admitted": True},),
    dependencies=({"package": "torch", "version": "2.13.0", "license": "BSD-3-Clause", "admitted": True},
                  {"package": "transformers", "version": "5.14.1", "license": "Apache-2.0", "admitted": True},
                  {"package": "numpy", "version": "2.5.1", "license": "BSD-3-Clause", "admitted": True},
                  {"package": "Pillow", "version": "12.3.0", "license": "MIT-CMU", "admitted": True}),
    runtime_probe=runtime_probe,
    consumers={"depth.profile": profile, "depth.regional_summary": regional_summary},
)
