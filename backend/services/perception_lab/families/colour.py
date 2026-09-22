"""Deterministic colour fields from A's EXIF/ICC-prepared sRGB image.

OpenCV documents float RGB [0,1], D65 and unoffset float Lab at
https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html.
These are image signals, not calibrated reflectance or pigment observations.
"""
from __future__ import annotations

import json
import math
import random

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
    columns = range(0, width, step)
    rows = range(0, height, step)
    rgb = image.rgb_bytes
    alpha = image.alpha_bytes
    colours, valid = [], []
    for y in rows:
        for x in columns:
            i = y * width + x
            colours.append(tuple(v / 255 for v in rgb[3*i:3*i+3]))
            valid.append(alpha[i] > 0)
    return colours, valid, len(columns), len(rows), step


def _lab(rgb):
    def linear(v):
        return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
    r, g, b = map(linear, rgb)
    x = (.4124564*r + .3575761*g + .1804375*b) / .950456
    y = .2126729*r + .7151522*g + .0721750*b
    z = (.0193339*r + .1191920*g + .9503041*b) / 1.088754
    def f(t):
        return t ** (1/3) if t > (6/29)**3 else t / (3*(6/29)**2) + 4/29
    fx, fy, fz = f(x), f(y), f(z)
    return (116*fy-16, 500*(fx-fy), 200*(fy-fz))


def _field(image, values, valid, width, height, step, channels, convention, kind="multichannel"):
    count = len(channels)
    if len(values) != width * height * count:
        raise ValueError("colour field shape does not match values")
    numbers = [0.0 if not valid[i//count] else float(value)
               for i, value in enumerate(values)]
    a, b, c, d, e, f, _, _, _ = image.source_to_working
    meta = {"version": 1, "shape": [height, width, count], "dtype": "float32-le",
            "kind": kind, "channels": [{"name": n, "quantity": q, "unit": u}
                                     for n, q, u in channels],
            "frame": "image_pixel_xy_topleft", "units": "declared per channel",
            "source_digest": image.source_digest,
            "source_to_field": [a/step, b/step, c/step, d/step, e/step, f/step, 0, 0, 1],
            "value_convention": convention}
    return ProducedField(meta, numbers, valid, REVISION)


CHANNELS = (("sRGB_R", "nonlinear working red", "0..1"),
            ("sRGB_G", "nonlinear working green", "0..1"),
            ("sRGB_B", "nonlinear working blue", "0..1"),
            ("Lab_L", "CIELAB lightness", "0..100"),
            ("Lab_a", "CIELAB green-red opponent", "approximately -127..127"),
            ("Lab_b", "CIELAB blue-yellow opponent", "approximately -127..127"))


def channels(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    colours, valid, width, height, step = _samples(image)
    values = [v for rgb in colours for v in (*rgb, *_lab(rgb))]
    return _field(image, values, valid, width, height, step, CHANNELS,
                  _convention(image, step, form="channels",
                  achromatic="near-neutral when sqrt(a²+b²)<2"))


def palette(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    colours, valid, width, height, step = _samples(image)
    positions = [i for i, is_valid in enumerate(valid) if is_valid]
    if not positions:
        raise ValueError("palette needs at least one valid source pixel")
    count = min(int(parameters["samples"]), len(positions))
    chosen = sorted(random.Random(int(parameters["seed"])).sample(positions, count))
    sampled = [_lab(colours[i]) for i in chosen]
    k = min(int(parameters["clusters"]), count,
            len({tuple(round(v, 6) for v in colour) for colour in sampled}))
    centres = [sampled[0]]
    for _ in range(1, k):
        centres.append(max(sampled, key=lambda colour:
                           min(math.dist(colour, centre) for centre in centres)))
    def nearest(colour):
        return min(range(k), key=lambda i: math.dist(colour, centres[i]))
    for _ in range(8):
        assignment = [nearest(colour) for colour in sampled]
        next_centres = []
        for i in range(k):
            group = [colour for colour, label in zip(sampled, assignment) if label == i]
            next_centres.append(tuple(sum(colour[j] for colour in group)/len(group)
                                      for j in range(3)) if group else centres[i])
        centres = next_centres
    sample_membership = [nearest(colour) for colour in sampled]
    all_lab = [_lab(colours[i]) for i in positions]
    membership = [nearest(colour) for colour in all_lab]
    ids = [0.0] * (width * height)
    for position, label in zip(positions, membership):
        ids[position] = float(label)
    details = {"form": "palette-membership", "seed": int(parameters["seed"]),
        "requested_clusters": int(parameters["clusters"]), "actual_clusters": k,
        "requested_samples": int(parameters["samples"]), "actual_samples": count,
        "population_count": len(positions),
        "population_counts": [membership.count(i) for i in range(k)],
        "sample_counts": [sample_membership.count(i) for i in range(k)],
        "sample_locations": [[position % width, position // width, label]
                             for position, label in zip(chosen, sample_membership)],
        "centres_lab": [[round(v, 5) for v in centre] for centre in centres],
        "meaning": "groups of sampled image colour, not objects or pigments"}
    return _field(image, ids, valid, width, height, step,
                  (("cluster_id", "zero-based nearest CIELAB centre", "index"),),
                  _convention(image, step, **details), "scalar")


def _distance(image, reference_lab):
    colours, valid, width, height, step = _samples(image)
    delta = [math.dist(_lab(colour), reference_lab) for colour in colours]
    return _field(image, delta, valid, width, height, step,
                  (("delta_E_76", "CIELAB Euclidean distance", "ΔE76"),),
                  _convention(image, step, form="distance", metric="CIELAB Euclidean ΔE76",
                  reference_location="resolved operation parameters in exported LabPlan",
                  threshold="none; display threshold is a separate choice"), "scalar")


def distance_sample(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    colours, valid, width, height, _ = _samples(image)
    x, y = int(parameters["x"]), int(parameters["y"])
    if not (0 <= x < width and 0 <= y < height) or not valid[y*width+x]:
        raise ValueError("reference sample is outside the valid colour field")
    return _distance(image, _lab(colours[y*width+x]))


def distance_rgb(image, parameters, inputs, cancel):
    cancel.raise_if_cancelled()
    colour = tuple(int(parameters[key])/255 for key in ("r", "g", "b"))
    return _distance(image, _lab(colour))


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
               "colour.distance": distance_sample, "colour.distance_rgb": distance_rgb})
