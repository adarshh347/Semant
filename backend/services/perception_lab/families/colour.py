"""Deterministic colour fields from A's EXIF/ICC-prepared sRGB image.

OpenCV documents float RGB [0,1], D65 and unoffset float Lab at
https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html.
These are image signals, not calibrated reflectance or pigment observations.
"""
from __future__ import annotations

import json
import math
import numpy as np

from .base import FamilyForm, FamilyModule, FamilyOperation, ProducedField

MAX_SIDE = 512
MAX_SAMPLES = 128
MAX_CLUSTERS = 8
REVISION = "colour-srgb-lab-v1"


def _spec(kind, description, lo, hi):
    return {"type": kind, "required": True, "description": description,
            "minimum": lo, "maximum": hi}


def _convention(image, step, **details):
    return json.dumps({"schema": "colour.v1", "working_profile": image.profile,
        "working_rgb_digest": image.working_rgb_digest, "orientation": image.orientation,
        "working_size": image.working_size, "sampling_step": step,
        "white": "D65 XYZ (0.950456,1,1.088754)",
        "transfer": "IEC 61966-2-1 sRGB", **details},
        sort_keys=True, separators=(",", ":"))


def _samples(image):
    width, height = image.working_size
    step = max(1, math.ceil(max(width, height) / MAX_SIDE))
    rgb = np.frombuffer(image.rgb_bytes, dtype=np.uint8).reshape(height, width, 3)
    alpha = np.frombuffer(image.alpha_bytes, dtype=np.uint8).reshape(height, width)
    return rgb[::step, ::step].astype(np.float64) / 255, alpha[::step, ::step] > 0, step


def _lab(rgb):
    linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
    xyz = linear @ np.array([[.4124564, .2126729, .0193339],
                             [.3575761, .7151522, .1191920],
                             [.1804375, .0721750, .9503041]])
    xyz /= [.950456, 1, 1.088754]
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz / (3*(6/29)**2) + 4/29)
    return np.stack((116*f[..., 1]-16, 500*(f[..., 0]-f[..., 1]),
                     200*(f[..., 1]-f[..., 2])), axis=-1)


def _field(image, values, valid, step, channels, convention, kind="multichannel"):
    values = np.asarray(values, dtype=np.float32).copy()
    values[~valid] = 0
    a, b, c, d, e, f, _, _, _ = image.source_to_working
    meta = {"version": 1, "shape": list(values.shape), "dtype": "float32-le",
            "kind": kind, "channels": [{"name": n, "quantity": q, "unit": u}
                                     for n, q, u in channels],
            "frame": "image_pixel_xy_topleft", "units": "declared per channel",
            "source_digest": image.source_digest,
            "source_to_field": [a/step, b/step, c/step, d/step, e/step, f/step, 0, 0, 1],
            "value_convention": convention}
    return ProducedField(meta, values.reshape(-1).tolist(), valid.reshape(-1).tolist(), REVISION)


CHANNELS = (("sRGB_R", "nonlinear working red", "0..1"),
            ("sRGB_G", "nonlinear working green", "0..1"),
            ("sRGB_B", "nonlinear working blue", "0..1"),
            ("Lab_L", "CIELAB lightness", "0..100"),
            ("Lab_a", "CIELAB green-red opponent", "approximately -127..127"),
            ("Lab_b", "CIELAB blue-yellow opponent", "approximately -127..127"))


def channels(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    rgb, valid, step = _samples(image)
    return _field(image, np.concatenate((rgb, _lab(rgb)), axis=-1), valid, step,
                  CHANNELS, _convention(image, step, form="channels",
                  achromatic="near-neutral when sqrt(a²+b²)<2"))


def palette(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    rgb, valid, step = _samples(image)
    lab = _lab(rgb)
    ys, xs = np.where(valid)
    if not len(xs):
        raise ValueError("palette needs at least one valid source pixel")
    count = min(int(parameters["samples"]), len(xs))
    k = min(int(parameters["clusters"]), count)
    rng = np.random.default_rng(int(parameters["seed"]))
    chosen = np.sort(rng.choice(len(xs), size=count, replace=False))
    sampled = lab[ys[chosen], xs[chosen]]
    k = min(k, len(np.unique(np.round(sampled, 6), axis=0)))
    centres = [sampled[0]]
    for _ in range(1, k):
        distances = np.min(np.stack([np.sum((sampled-c)**2, axis=1)
                                     for c in centres]), axis=0)
        centres.append(sampled[int(np.argmax(distances))])
    centres = np.asarray(centres)
    for _ in range(8):
        assignment = np.argmin(np.sum((sampled[:, None]-centres[None])**2, axis=2), axis=1)
        centres = np.asarray([sampled[assignment == i].mean(axis=0)
                              if np.any(assignment == i) else centres[i] for i in range(k)])
    population = lab[valid]
    membership = np.argmin(np.sum((population[:, None]-centres[None])**2, axis=2), axis=1)
    ids = np.zeros((*valid.shape, 1), dtype=np.float32)
    ids[..., 0][valid] = membership
    sample_membership = np.argmin(np.sum((sampled[:, None]-centres[None])**2, axis=2), axis=1)
    details = {"form": "palette-membership", "seed": int(parameters["seed"]),
        "requested_clusters": int(parameters["clusters"]), "actual_clusters": k,
        "requested_samples": int(parameters["samples"]), "actual_samples": count,
        "population_count": len(xs), "population_counts": np.bincount(membership, minlength=k).tolist(),
        "sample_counts": np.bincount(sample_membership, minlength=k).tolist(),
        "sample_locations": [[int(xs[i]), int(ys[i]), int(sample_membership[j])]
                             for j, i in enumerate(chosen)],
        "centres_lab": np.round(centres, 5).tolist(),
        "meaning": "groups of sampled image colour, not objects or pigments"}
    return _field(image, ids, valid, step,
                  (("cluster_id", "zero-based nearest CIELAB centre", "index"),),
                  _convention(image, step, **details), "scalar")


def _distance(image, reference_lab, reference):
    rgb, valid, step = _samples(image)
    delta = np.linalg.norm(_lab(rgb)-reference_lab, axis=-1)[..., None]
    return _field(image, delta, valid, step,
                  (("delta_E_76", "CIELAB Euclidean distance", "ΔE76"),),
                  _convention(image, step, form="distance", metric="CIELAB Euclidean ΔE76",
                  reference_location="resolved operation parameters in exported LabPlan",
                  threshold="none; display threshold is a separate choice"), "scalar")


def distance_sample(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    rgb, valid, _ = _samples(image)
    x, y = int(parameters["x"]), int(parameters["y"])
    if not (0 <= x < rgb.shape[1] and 0 <= y < rgb.shape[0]) or not valid[y, x]:
        raise ValueError("reference sample is outside the valid colour field")
    return _distance(image, _lab(rgb[y, x]), {"mode": "selected field pixel", "x": x, "y": y})


def distance_rgb(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    colour = [int(parameters[key]) for key in ("r", "g", "b")]
    return _distance(image, _lab(np.asarray(colour, dtype=np.float64)/255),
                     {"mode": "supplied sRGB8", "rgb": colour})


MODULE = FamilyModule("colour", "Colour", True,
    "Deterministic image-colour fields; sRGB working copy, not physical pigment data.",
    forms=(
        FamilyForm("colour.channels", "Colour channels", "sRGB and CIELAB image signal",
                   "Source-aligned six-channel field.", ("channel",)),
        FamilyForm("colour.palette", "Sampled palette", "sampled colour groups",
                   "Sampled CIELAB palette with full field membership.", ("palette",)),
        FamilyForm("colour.distance", "Reference colour distance", "CIELAB ΔE76",
                   "Distance from a selected pixel or supplied sRGB8 colour.", ("distance",))),
    operations=(
        FamilyOperation("colour.channels", "Make colour field", "colour.channels",
                        "colour.channels", {}, ("show the colour field",)),
        FamilyOperation("colour.palette", "Make sampled palette", "colour.palette",
                        "colour.palette", {
                            "clusters": _spec("integer", "Requested groups", 1, MAX_CLUSTERS),
                            "samples": _spec("integer", "Requested samples", 1, MAX_SAMPLES),
                            "seed": _spec("integer", "Deterministic seed", 0, 2147483647)}),
        FamilyOperation("colour.distance", "Distance from selected pixel", "colour.distance",
                        "colour.distance", {
                            "x": _spec("integer", "Selected field-pixel x", 0, MAX_SIDE-1),
                            "y": _spec("integer", "Selected field-pixel y", 0, MAX_SIDE-1)},
                        ("compare colour to the selected sample",)),
        FamilyOperation("colour.distance_rgb", "Distance from supplied sRGB colour",
                        "colour.distance", "colour.distance_rgb", {
                            key: _spec("integer", f"sRGB8 {key}", 0, 255)
                            for key in ("r", "g", "b")})),
    producers={"colour.channels": channels, "colour.palette": palette,
               "colour.distance": distance_sample, "colour.distance_rgb": distance_rgb},
    dependencies=({"package": "numpy", "version": ">=1.24,<3", "license": "BSD-3-Clause",
                   "admitted": True},))
