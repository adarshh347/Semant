"""CPU structure-tensor tangents, not optical motion or semantic brushstrokes."""
from __future__ import annotations

import importlib.util
import json
import math
from time import perf_counter

from .base import FamilyForm, FamilyModule, FamilyOperation, ProducedField
from .orientation_consumers import CONSUMERS

VERSION = "structure-tensor-tangent-v1"
MAX_EDGE = 256
ENERGY_FLOOR = 1e-6
PARAMETERS = {
    "derivative_sigma": {"type": "number", "required": False, "minimum": .5,
                         "maximum": 3, "description": "Gaussian presmoothing, field pixels; default 1."},
    "integration_sigma": {"type": "number", "required": False, "minimum": 1,
                          "maximum": 8, "description": "Tensor neighbourhood, field pixels; default 3."},
    "min_coherence": {"type": "number", "required": False, "minimum": .01,
                      "maximum": 1, "description": "Minimum anisotropy for a valid axis; default 0.15. Not confidence."},
}


def _parameters(parameters):
    if set(parameters) - set(PARAMETERS):
        raise ValueError("unsupported orientation parameter")
    result = dict(derivative_sigma=1.0, integration_sigma=3.0, min_coherence=.15)
    result.update(parameters)
    for name, value in result.items():
        spec = PARAMETERS[name]
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not spec["minimum"] <= value <= spec["maximum"]):
            raise ValueError(f"invalid {name}")
    return result


def available(_=None):
    ready = all(importlib.util.find_spec(name) is not None for name in ("cv2", "numpy"))
    return ready, "CPU structure tensor requires the installed OpenCV and NumPy adapters."


def _produce(prepared, parameters, inputs, cancel, form):
    if inputs:
        raise ValueError("orientation takes a whole source image; implicit ROI inputs are unsupported")
    settings = _parameters(parameters)
    cancel.raise_if_cancelled()
    if not available()[0]:
        raise ValueError("CPU orientation unavailable: OpenCV and NumPy are required")
    import cv2
    import numpy as np

    started = perf_counter()
    width, height = prepared.working_size
    scale = min(1., MAX_EDGE / max(width, height))
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    rgb = np.frombuffer(prepared.rgb_bytes, dtype=np.uint8).reshape(height, width, 3)
    alpha = np.frombuffer(prepared.alpha_bytes, dtype=np.uint8).reshape(height, width)
    rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_AREA)
    luma = rgb @ np.array([.2126, .7152, .0722], dtype=np.float32)
    sigma, rho = settings["derivative_sigma"], settings["integration_sigma"]
    blur_radius, tensor_radius = math.ceil(3*sigma), math.ceil(3*rho)
    smooth = cv2.GaussianBlur(luma, (2*blur_radius+1,)*2, sigma,
                              borderType=cv2.BORDER_REFLECT_101)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3, scale=1/8,
                   borderType=cv2.BORDER_REFLECT_101)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3, scale=1/8,
                   borderType=cv2.BORDER_REFLECT_101)
    cancel.raise_if_cancelled()
    def integrate(array):
        return cv2.GaussianBlur(array, (2*tensor_radius+1,)*2, rho,
                                borderType=cv2.BORDER_REFLECT_101)
    jxx, jyy, jxy = integrate(gx*gx), integrate(gy*gy), integrate(gx*gy)
    energy = jxx+jyy
    difference = np.hypot(jxx-jyy, 2*jxy)
    coherence = np.clip(np.divide(difference, energy, out=np.zeros_like(energy),
                                  where=energy > ENERGY_FLOOR), 0, 1)
    # Full finite Gaussian/Sobel support must be opaque; hidden RGB cannot create axes.
    radius = blur_radius + 1 + tensor_radius
    support = cv2.erode((alpha == 255).astype(np.uint8), np.ones((2*radius+1,)*2, np.uint8),
                        borderType=cv2.BORDER_REFLECT_101).astype(bool)
    supported_energy = support & (energy > ENERGY_FLOOR)
    if form == "tangent":
        # Tangent is perpendicular to the principal-gradient eigenvector.
        # Adding pi/2 negates BOTH doubled-angle components.
        denominator = np.where(energy > ENERGY_FLOOR, energy, 1)
        values = np.stack(((jyy-jxx)/denominator, -2*jxy/denominator), axis=-1)
        valid = supported_energy & (coherence >= settings["min_coherence"])
        kind, units = "axial_orientation_2d", "dimensionless_coherence_weighted_double_angle"
        channels = [{"name": name, "quantity": "coherence_weighted_axial_tangent", "unit": "1"}
                    for name in ("coherence_cos_2theta", "coherence_sin_2theta")]
    elif form == "coherence":
        values, valid = coherence[..., None], supported_energy
        kind, units = "scalar", "dimensionless_anisotropy"
        channels = [{"name": "tensor_coherence", "quantity": "structure_tensor_anisotropy", "unit": "1"}]
    else:
        values, valid = energy[..., None], support
        kind, units = "scalar", "squared_encoded_luma_per_field_pixel"
        channels = [{"name": "gradient_energy", "quantity": "structure_tensor_trace",
                     "unit": "encoded_luma_squared_per_field_pixel_squared"}]
    values[~valid] = 0
    sx, sy = w/width, h/height
    a, b, c, d, e, f, _, _, _ = prepared.source_to_working
    convention = dict(algorithm=VERSION, form=form, parameters=settings,
        signal="encoded sRGB weighted luma 0.2126 R + 0.7152 G + 0.0722 B; not physical luminance",
        working_profile=prepared.profile, working_rgb_digest=prepared.working_rgb_digest,
        source_working_size=[width, height], field_size=[w, h],
        sampling="INTER_AREA, no upsampling, longest edge <=256; pixel-centre affine",
        derivative="Gaussian truncated at ceil(3 sigma), Sobel 3x3 /8",
        integration="Gaussian truncated at ceil(3 rho) of gx², gy², gx*gy",
        border="REFLECT_101", energy_floor=ENERGY_FLOOR,
        validity="entire derivative/tensor support opaque; axis additionally needs energy and min_coherence",
        direction="tangent in field pixel x-right y-down axes; theta modulo 180 degrees",
        axial_encoding="coherence * (cos(2 theta), sin(2 theta)); magnitude is anisotropy, not confidence",
        source_direction="apply inverse source_to_field linear 2x2 to a field tangent, then normalize",
        limitation="one local axis only; crossings can be unoriented; not optical flow, stroke identity or hand trajectory")
    metadata = dict(version=1, shape=[h, w, len(channels)], dtype="float32-le", kind=kind,
        channels=channels, frame="image_pixel_xy_topleft", units=units,
        source_digest=prepared.source_digest,
        source_to_field=[sx*a, sx*b, sx*c+(sx-1)/2, sy*d, sy*e, sy*f+(sy-1)/2, 0, 0, 1],
        value_convention=json.dumps(convention, sort_keys=True, separators=(",", ":")))
    cancel.raise_if_cancelled()
    return ProducedField(metadata, values.ravel().tolist(), valid.ravel().tolist(), VERSION,
        device="cpu", receipt={"algorithm_ms": (perf_counter()-started)*1000,
                               "model_invocations": 0, "cache_hit": False, "device": "cpu"})


def tangent(prepared, parameters, inputs, cancel):
    return _produce(prepared, parameters, inputs, cancel, "tangent")


def coherence(prepared, parameters, inputs, cancel):
    return _produce(prepared, parameters, inputs, cancel, "coherence")


def energy(prepared, parameters, inputs, cancel):
    return _produce(prepared, parameters, inputs, cancel, "energy")


MODULE = FamilyModule("orientation_flow", "Orientation / flow", True,
    "CPU tensor tangent, coherence and energy; not optical motion.",
    forms=tuple(FamilyForm(f"orientation_flow.{key}", label, quantity, description, views)
        for key, label, quantity, description, views in (
            ("tangent", "Local axial tangent", "coherence_weighted_axial_tangent",
             "Headless tangent; 0 and 180 degrees are equivalent.", ("headless_marks", "coherence_wash", "trace")),
            ("coherence", "Tensor coherence", "structure_tensor_anisotropy",
             "Local directional concentration, not calibrated confidence.", ("coherence_wash",)),
            ("energy", "Gradient energy", "structure_tensor_trace",
             "Smoothed squared encoded-luma gradient; not motion energy.", ("energy_wash",)))),
    operations=tuple(FamilyOperation(f"orientation_flow.{key}", label,
        f"orientation_flow.{key}", f"orientation_flow.{key}", PARAMETERS,
        ("show local orientation",) if key == "tangent" else ())
        for key, label in (("tangent", "Show local orientation"),
                           ("coherence", "Measure tensor coherence"), ("energy", "Measure gradient energy"))),
    producers={"orientation_flow.tangent": tangent, "orientation_flow.coherence": coherence,
               "orientation_flow.energy": energy}, runtime_probe=available, consumers=CONSUMERS,
    dependencies=({"package": "opencv-python", "version": "5.0.0.93", "license": "Apache-2.0", "admitted": True},
                  {"package": "numpy", "version": "2.5.1", "license": "BSD-3-Clause", "admitted": True}))
