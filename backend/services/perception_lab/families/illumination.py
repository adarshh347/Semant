"""Image-relative luminance and independently estimated grayscale shading."""
from __future__ import annotations

from PIL import Image

from .base import FamilyForm, FamilyModule, FamilyOperation, ProducedField

MODEL_REVISION = "Intrinsic@1a93aafaaf7dbe11be7ec86323d9a06e5950966d:paper_weights"
CHECKPOINT_SHA256 = "daeeb1e9aa9bcd65a3357e22c54344099fb9adb852541b89d06926db3a518001"


def _metadata(prepared, *, quantity: str, convention: str) -> dict:
    w, h = prepared.working_size
    return {"version": 1, "shape": [h, w, 1], "dtype": "float32-le",
            "kind": "scalar", "channels": [{"name": quantity, "quantity": quantity,
                                         "unit": "relative"}],
            "frame": "image_pixel_xy_topleft", "units": "relative",
            "source_digest": prepared.source_digest,
            "source_to_field": list(prepared.source_to_working),
            "value_convention": convention}


def _alpha_valid(prepared, alpha_min: int) -> list[bool]:
    if type(alpha_min) is not int or not 1 <= alpha_min <= 255:
        raise ValueError("alpha_min must be an integer from 1 to 255")
    return [value >= alpha_min for value in prepared.alpha_bytes]


def image_luminance(prepared, parameters, inputs, cancel) -> ProducedField:
    """Rec.709 linear-light Y from the shared ICC-normalized sRGB raster."""
    alpha_min = parameters.get("alpha_min", 1)
    valid = _alpha_valid(prepared, alpha_min)
    values = []
    for index in range(0, len(prepared.rgb_bytes), 3):
        if index % 12288 == 0:
            cancel.raise_if_cancelled()
        channels = (prepared.rgb_bytes[index + j] / 255 for j in range(3))
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                  for c in channels]
        y = .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
        values.append(y if valid[index // 3] else 0.0)
    return ProducedField(
        metadata=_metadata(prepared, quantity="image_linear_luminance",
                           convention=("sRGB IEC 61966-2-1 decoded to linear light; "
                                       "Rec.709 Y coefficients; image-relative 0..1; "
                                       f"alpha >= {alpha_min}; no intrinsic decomposition")),
        values=values, valid=valid, producer_revision="srgb-eotf-rec709-y-v1",
        model=None, device="cpu")


def estimated_shading(prepared, parameters, inputs, cancel) -> ProducedField:
    """Source-sized model estimate; never substitute luminance if inference fails."""
    from backend.services import intrinsic_service

    alpha_min = parameters.get("alpha_min", 1)
    valid_alpha = _alpha_valid(prepared, alpha_min)
    cancel.raise_if_cancelled()
    image = Image.frombytes("RGB", prepared.working_size, prepared.rgb_bytes)
    result = intrinsic_service.estimate_dense(image)
    cancel.raise_if_cancelled()
    values = result["shading"].ravel().tolist()
    model_valid = result["valid"].ravel().tolist()
    valid = [a and b for a, b in zip(valid_alpha, model_valid)]
    if len(values) != len(valid):
        raise ValueError("Intrinsic shading shape differs from prepared image")
    values = [value if good else 0.0 for value, good in zip(values, valid)]
    native_h, native_w = result["native_shape"]
    return ProducedField(
        metadata=_metadata(prepared, quantity="estimated_grayscale_shading",
                           convention=("Intrinsic paper_weights gray pipeline; single channel; "
                                       "gry_shd stores inverse shading in installed revision; "
                                       "converted by 1/clip(x,0.001,1)-1; relative, uncalibrated; "
                                       f"native pipeline raster {native_w}x{native_h}; "
                                       "maintain_size=True antialiased resize to working source; "
                                       f"alpha >= {alpha_min}; invalid model cells unknown")),
        values=values, valid=valid,
        producer_revision=MODEL_REVISION,
        model="Intrinsic ordinal grayscale shading / paper_weights",
        device=result["device"])


ALPHA_PARAMETER = {"alpha_min": {"type": "integer", "required": False,
                                  "minimum": 1, "maximum": 255,
                                  "description": "Pixels below this source alpha are unknown. Default 1."}}

MODULE = FamilyModule(
    "illumination", "Illumination", True,
    "Image luminance is deterministic; estimated shading requires the installed Intrinsic model.",
    forms=(
        FamilyForm("illumination.image_luminance", "Image luminance",
                   "image-relative linear-light Y", "Brightness in the prepared image, not lighting decomposition.",
                   ("grayscale", "false_colour", "contours")),
        FamilyForm("illumination.estimated_shading", "Estimated shading",
                   "model-estimated relative grayscale shading", "An intrinsic-model estimate with an independent scale.",
                   ("grayscale", "false_colour", "contours")),
    ),
    operations=(
        FamilyOperation("illumination.image_luminance", "Show image luminance",
                        "illumination.image_luminance", "illumination.luminance_producer",
                        ALPHA_PARAMETER, ("show image brightness",), False),
        FamilyOperation("illumination.estimated_shading", "Estimate shading",
                        "illumination.estimated_shading", "illumination.shading_producer",
                        ALPHA_PARAMETER, ("estimate shading",), True),
    ),
    producers={"illumination.luminance_producer": image_luminance,
               "illumination.shading_producer": estimated_shading},
    models=({"key": "intrinsic-paper-weights", "revision": MODEL_REVISION,
             "license": "academic use only; patent pending",
             "checkpoint_digest": "sha256:" + CHECKPOINT_SHA256, "admitted": True},),
    dependencies=({"package": "compphoto/Intrinsic", "version": "git@1a93aafaaf7dbe11be7ec86323d9a06e5950966d",
                   "license": "academic use only", "admitted": True},),
)
