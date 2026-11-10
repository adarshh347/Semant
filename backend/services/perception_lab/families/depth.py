"""Depth Anything's saved, source-aligned relative inverse depth — never metres."""
from __future__ import annotations

from backend.services import depth_service
from .base import FamilyForm, FamilyModule, FamilyOperation, ProducedField

FORM = "depth.relative_inverse_depth"
PRODUCER = "depth.anything_v2_small"
QUANTITY = "estimated_relative_inverse_depth"


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
    models=({"key": depth_service.CHECKPOINT, "revision": depth_service.REVISION,
             "license": "Apache-2.0", "checkpoint_digest": "sha256:" + depth_service.CHECKPOINT_SHA256,
             "admitted": True},),
    dependencies=({"package": "torch", "version": "2.13.0", "license": "BSD-3-Clause", "admitted": True},
                  {"package": "transformers", "version": "5.14.1", "license": "Apache-2.0", "admitted": True},
                  {"package": "numpy", "version": "2.5.1", "license": "BSD-3-Clause", "admitted": True},
                  {"package": "Pillow", "version": "12.3.0", "license": "MIT-CMU", "admitted": True}),
    runtime_probe=lambda _: depth_service.dense_readiness(),
)
