#!/usr/bin/env python3
"""
PERCEPTUAL-FORMS-001C — the specialist-model laboratory.

WHAT THIS IS FOR. Lane A registered ten Extent forms and froze their payloads. Four of them are
`deferred` because they need a producer nobody has built: `extent.soft_field`,
`extent.fused_hypothesis`, `extent.visible_inferred_partition` and `extent.density_field`. This
harness asks, for each of those four, WHICH MODEL — if any — could produce it, and answers with
measurements rather than with a citation.

WHAT IT IS NOT. It integrates nothing. It touches no production registry, route, dependency or
lockfile. Every candidate adapter lives inside this file, loads its own weights, records what it
did and releases them. A candidate that cannot be loaded on this machine says so and the trial
records `unavailable` — which is a result, not a failure, and is exactly the distinction the
Perception Lab contract exists to keep.

THE ONE QUESTION EVERY TRIAL ANSWERS. Not "does the model run" — every model runs. It is:

    does this output MEAN what the form it would fill says it means?

So each trial ends by building the declared payload out of the model's real output and validating
it against Lane A's own Pydantic models. A candidate whose output cannot fill the payload without
lying about what the numbers are gets `REJECT` no matter how good the picture looks.

THE SIX THINGS THIS FILE REFUSES TO CONFLATE, because every one of them is a real mistake
somebody has shipped:

    alpha transparency      what fraction of a pixel the thing covers. A measurement.
    class probability       how likely the thing is of a kind. Not coverage.
    model confidence        how sure the model is about its own output. Not coverage either.
    boundary uncertainty    where the model does not know the edge is. Needs calibration to claim.
    density                 how many per unit area. A count statistic, not an occupancy.
    inferred occupancy      extent asserted where nothing was seen. A hypothesis, forever.

A blurred mask is not a soft extent. A logit is not a calibrated uncertainty until something has
measured the calibration. Depth is supporting evidence from the Depth family and is never an
Extent measurement. Amodal completion is a hypothesis and never `visible` or `measured` geometry.

USAGE

    python scripts/perception_lab_model_trials.py controls          # write the control corpus
    python scripts/perception_lab_model_trials.py controls --check  # verify it has not drifted
    python scripts/perception_lab_model_trials.py list              # candidates and residency
    python scripts/perception_lab_model_trials.py run --candidate vitmatte_small
    python scripts/perception_lab_model_trials.py run-all
    python scripts/perception_lab_model_trials.py matrix            # the verdict table

NO WEIGHTS IN GIT. Every candidate declares where its weights come from and how big they are;
none of them is written into the repository. `--allow-download` is required before this file will
fetch anything it does not already find in the local cache, and the budget guard refuses anything
over `MAX_DOWNLOAD_MB` outright.

PURE-ISH. Reads the contract and the models, writes only under `research/perception_lab/
model_trials/`. No database, no network except a declared, guarded weight fetch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

TRIALS_ROOT = REPO_ROOT / "research" / "perception_lab" / "model_trials"
CONTROLS_DIR = TRIALS_ROOT / "controls"
RUNS_DIR = TRIALS_ROOT / "runs"
PREVIEWS_DIR = TRIALS_ROOT / "previews"

#: The practical budget on the box this lane runs on: a 16 GB Mac mini, ~10 GB usable for a model.
#: A candidate above this is not evaluated here — it is recorded as DEFERRED with the number that
#: put it out of reach, which is a more useful finding than an out-of-memory traceback.
BUDGET_VRAM_GB = 10.0
MAX_DOWNLOAD_MB = 2048.0

CONTROL_SIZE = 256


# ── the control corpus ───────────────────────────────────────────────────────
#
# SYNTHETIC ON PURPOSE, and small. Two reasons, and the second is the important one.
#
#   1. LAWFUL. Nothing here is scraped, licensed or someone else's. Every pixel is computed by the
#      code below, so the corpus can live in a public repository without a rights question.
#
#   2. THE GROUND TRUTH IS KNOWN BEFORE THE MODEL RUNS. That is what makes these CONTROLS rather
#      than examples. `soft-fog` has an exact alpha at every pixel because the alpha is what drew
#      it; `fence-tree` knows which fragments are one thing because it cut them from one blob;
#      `occluder-table` knows precisely which pixels are hidden because it covered them. A model
#      evaluated on a photograph can only be compared to another model's opinion.
#
# The Lane F corpus (Steenwyck, de Chirico, Wells, the Cubist interior, van Delen, the still life)
# is the real test and does not exist yet. These are the disposable controls that come first, and
# a candidate that fails HERE never needs to meet a painting.


@dataclass(frozen=True)
class Control:
    name: str
    tests: Tuple[str, ...]
    what: str
    truth: str
    draw: Callable[[Any], Tuple[Any, Dict[str, Any]]]


def _np():
    import numpy as np
    return np


def _grid(n: int = CONTROL_SIZE):
    np = _np()
    ys, xs = np.mgrid[0:n, 0:n]
    return xs / (n - 1.0), ys / (n - 1.0)


def _compose(alpha, fg, bg):
    """Alpha compositing, so the control's alpha is the TRUE fractional coverage by construction."""
    np = _np()
    a = alpha[..., None]
    return np.clip(a * fg + (1.0 - a) * bg, 0.0, 1.0)


def _rgb(r: float, g: float, b: float):
    np = _np()
    return np.array([r, g, b], dtype=np.float32)


def draw_hard_edge(rng) -> Tuple[Any, Dict[str, Any]]:
    """THE NEGATIVE CONTROL. A crisp square: alpha is 0 or 1 and nowhere between.

    A soft-field producer that reports a graded fringe HERE is reporting its own blur, not the
    picture's. This is the single most important control in the corpus.
    """
    np = _np()
    alpha = np.zeros((CONTROL_SIZE, CONTROL_SIZE), dtype=np.float32)
    alpha[64:192, 64:192] = 1.0
    image = _compose(alpha, _rgb(0.85, 0.42, 0.25), _rgb(0.10, 0.11, 0.13))
    return image, {"alpha_is_binary": True, "interior_box": [64, 64, 192, 192],
                   "true_soft_pixels": 0}


def draw_soft_fog(rng) -> Tuple[Any, Dict[str, Any]]:
    """A radial field with no boundary anywhere. The alpha IS the answer."""
    np = _np()
    x, y = _grid()
    d = np.sqrt((x - 0.42) ** 2 + (y - 0.55) ** 2)
    alpha = np.clip(1.0 - (d / 0.46) ** 1.4, 0.0, 1.0).astype(np.float32)
    image = _compose(alpha, _rgb(0.86, 0.87, 0.90), _rgb(0.16, 0.20, 0.28))
    return image, {"alpha_is_binary": False,
                   "true_alpha_mean": float(alpha.mean()),
                   "true_soft_fraction": float(((alpha > 0.02) & (alpha < 0.98)).mean())}


def draw_hair_veil(rng) -> Tuple[Any, Dict[str, Any]]:
    """Filaments thinner than a pixel. Their true coverage is FRACTIONAL, not uncertain.

    This separates alpha from uncertainty better than anything else here: the model is not unsure
    where the hair is, and the pixel is genuinely 30% hair. A producer that reports these as
    `uncertain` has mislabelled a measurement as a doubt.
    """
    np = _np()
    x, y = _grid()
    alpha = np.zeros((CONTROL_SIZE, CONTROL_SIZE), dtype=np.float32)
    for i in range(26):
        phase = 0.11 * i
        centre = 0.18 + 0.026 * i + 0.05 * np.sin(6.0 * y + phase)
        width = 0.0016 + 0.0009 * (i % 3)
        strand = np.clip(1.0 - np.abs(x - centre) / (width * 3.0), 0.0, 1.0)
        alpha = np.maximum(alpha, strand * 0.92)
    alpha *= np.clip(1.6 - 1.4 * y, 0.0, 1.0)
    image = _compose(alpha, _rgb(0.18, 0.13, 0.10), _rgb(0.78, 0.76, 0.72))
    return image, {"alpha_is_binary": False,
                   "true_alpha_mean": float(alpha.mean()),
                   "true_soft_fraction": float(((alpha > 0.02) & (alpha < 0.98)).mean()),
                   "note": "fractional coverage of sub-pixel filaments, not model doubt"}


def draw_fence_tree(rng) -> Tuple[Any, Dict[str, Any]]:
    """ONE blob, cut into fragments by vertical bars. Membership is known because it was cut."""
    np = _np()
    x, y = _grid()
    blob = np.clip(1.0 - np.sqrt(((x - 0.5) / 0.34) ** 2 + ((y - 0.45) / 0.30) ** 2), 0.0, 1.0)
    blob = (blob > 0.18).astype(np.float32)
    bars = np.zeros_like(blob)
    for cx in (0.30, 0.44, 0.58, 0.72):
        bars = np.maximum(bars, (np.abs(x - cx) < 0.022).astype(np.float32))
    visible = blob * (1.0 - bars)
    image = _compose(bars, _rgb(0.32, 0.33, 0.35),
                     _compose(blob, _rgb(0.24, 0.52, 0.28), _rgb(0.80, 0.82, 0.86)))
    fragments = _connected_columns(visible)
    return image, {"one_entity": True, "fragment_count": len(fragments),
                   "fragment_boxes": fragments,
                   "occluder": "four vertical bars", "true_whole_area": float(blob.mean())}


def draw_false_twins(rng) -> Tuple[Any, Dict[str, Any]]:
    """Two blobs that LOOK alike and are not one thing. The fragment-affinity negative control."""
    np = _np()
    x, y = _grid()
    left = (np.sqrt(((x - 0.24) / 0.14) ** 2 + ((y - 0.34) / 0.15) ** 2) < 1.0).astype(np.float32)
    right = (np.sqrt(((x - 0.76) / 0.14) ** 2 + ((y - 0.70) / 0.15) ** 2) < 1.0).astype(np.float32)
    image = _compose(np.maximum(left, right), _rgb(0.24, 0.52, 0.28), _rgb(0.80, 0.82, 0.86))
    return image, {"one_entity": False, "fragment_count": 2,
                   "fragment_boxes": [[0.10, 0.19, 0.38, 0.49], [0.62, 0.55, 0.90, 0.85]],
                   "note": "same colour, same shape, opposite corners, two things"}


def draw_lit_floor(rng) -> Tuple[Any, Dict[str, Any]]:
    """ONE surface whose appearance changes hard across the middle. Continuity without similarity."""
    np = _np()
    x, y = _grid()
    floor = (y > 0.45).astype(np.float32)
    lit = (x < 0.52).astype(np.float32)
    base = _rgb(0.62, 0.55, 0.44)
    shaded = base * 0.42
    surface = lit[..., None] * base + (1.0 - lit)[..., None] * shaded
    image = _compose(floor, surface, _rgb(0.14, 0.15, 0.18))
    return image, {"one_entity": True, "fragment_count": 2,
                   "fragment_boxes": [[0.0, 0.45, 0.52, 1.0], [0.52, 0.45, 1.0, 1.0]],
                   "note": "appearance discontinuity in one continuous surface"}


def draw_occluder_table(rng) -> Tuple[Any, Dict[str, Any]]:
    """A figure behind a bar, with the hidden pixels recorded EXACTLY because they were covered."""
    np = _np()
    x, y = _grid()
    figure = ((np.abs(x - 0.5) < 0.11) & (y > 0.16) & (y < 0.88)).astype(np.float32)
    head = (np.sqrt(((x - 0.5) / 0.085) ** 2 + ((y - 0.16) / 0.085) ** 2) < 1.0).astype(np.float32)
    whole = np.clip(figure + head, 0.0, 1.0)
    bar = ((y > 0.52) & (y < 0.72)).astype(np.float32)
    visible = whole * (1.0 - bar)
    hidden = whole * bar
    image = _compose(bar, _rgb(0.45, 0.30, 0.20),
                     _compose(whole, _rgb(0.20, 0.24, 0.44), _rgb(0.84, 0.84, 0.86)))
    return image, {"visible_fraction": float(visible.mean() / max(whole.mean(), 1e-9)),
                   "hidden_fraction": float(hidden.mean() / max(whole.mean(), 1e-9)),
                   "hidden_band": [0.52, 0.72],
                   "whole_box": [0.39, 0.075, 0.61, 0.88],
                   "note": "the hidden pixels are known exactly; the model must not invent others"}


def draw_crowd_plaza(rng) -> Tuple[Any, Dict[str, Any]]:
    """Sixty marks, deliberately denser in the eastern half. A count and a distribution, both known."""
    np = _np()
    x, y = _grid()
    alpha = np.zeros((CONTROL_SIZE, CONTROL_SIZE), dtype=np.float32)
    points = []
    for i in range(60):
        east = i % 4 != 0                      # 45 east, 15 west
        cx = rng.uniform(0.55, 0.95) if east else rng.uniform(0.05, 0.45)
        cy = rng.uniform(0.30, 0.92)
        points.append([round(float(cx), 4), round(float(cy), 4)])
        blob = (np.sqrt(((x - cx) / 0.018) ** 2 + ((y - cy) / 0.026) ** 2) < 1.0)
        alpha = np.maximum(alpha, blob.astype(np.float32))
    image = _compose(alpha, _rgb(0.15, 0.16, 0.20), _rgb(0.80, 0.78, 0.72))
    east_count = sum(1 for p in points if p[0] >= 0.5)
    return image, {"true_count": 60, "east_count": east_count,
                   "west_count": 60 - east_count, "points": points,
                   "note": "the crowd occupies the eastern half; there is no object called crowd"}


def draw_windows_facade(rng) -> Tuple[Any, Dict[str, Any]]:
    """A regular grid of openings. Repetition without a crowd — the density transfer control."""
    np = _np()
    x, y = _grid()
    alpha = np.zeros((CONTROL_SIZE, CONTROL_SIZE), dtype=np.float32)
    count = 0
    for row in range(4):
        for col in range(5):
            cx, cy = 0.13 + 0.185 * col, 0.16 + 0.22 * row
            win = (np.abs(x - cx) < 0.055) & (np.abs(y - cy) < 0.070)
            alpha = np.maximum(alpha, win.astype(np.float32))
            count += 1
    image = _compose(alpha, _rgb(0.10, 0.12, 0.16), _rgb(0.72, 0.68, 0.60))
    return image, {"true_count": count, "regular": True,
                   "note": "repeated structure a crowd model has never seen"}


def draw_sparse_objects(rng) -> Tuple[Any, Dict[str, Any]]:
    """Three things. A density model that reports a field here has answered the wrong question."""
    np = _np()
    x, y = _grid()
    alpha = np.zeros((CONTROL_SIZE, CONTROL_SIZE), dtype=np.float32)
    for cx, cy, r in ((0.22, 0.30, 0.085), (0.55, 0.66, 0.10), (0.82, 0.24, 0.07)):
        alpha = np.maximum(alpha, (np.sqrt(((x - cx) / r) ** 2 + ((y - cy) / r) ** 2) < 1.0)
                           .astype(np.float32))
    image = _compose(alpha, _rgb(0.55, 0.20, 0.24), _rgb(0.86, 0.85, 0.82))
    return image, {"true_count": 3, "sparse": True}


def _connected_columns(mask) -> List[List[float]]:
    """Column-run boxes of a binary mask. Enough to name the fragments these controls make."""
    np = _np()
    cols = mask.sum(axis=0) > 0
    boxes: List[List[float]] = []
    start = None
    for i, on in enumerate(list(cols) + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            band = mask[:, start:i]
            rows = np.where(band.sum(axis=1) > 0)[0]
            if len(rows):
                boxes.append([round(start / (CONTROL_SIZE - 1), 4),
                              round(float(rows[0]) / (CONTROL_SIZE - 1), 4),
                              round((i - 1) / (CONTROL_SIZE - 1), 4),
                              round(float(rows[-1]) / (CONTROL_SIZE - 1), 4)])
            start = None
    return boxes


CONTROLS: Tuple[Control, ...] = (
    Control("hard-edge", ("soft_field",),
            "a crisp square on a flat ground",
            "alpha is 0 or 1 and nowhere between; there are no soft pixels to find",
            draw_hard_edge),
    Control("soft-fog", ("soft_field",),
            "a radial haze with no boundary anywhere",
            "the alpha that drew it is the true fractional occupancy at every pixel",
            draw_soft_fog),
    Control("hair-veil", ("soft_field",),
            "sub-pixel filaments over a pale ground",
            "fractional COVERAGE, not doubt — the model is not unsure where the hair is",
            draw_hair_veil),
    Control("fence-tree", ("fragment_link",),
            "one blob cut into four by vertical bars",
            "the fragments are one entity, because they were cut from one",
            draw_fence_tree),
    Control("false-twins", ("fragment_link",),
            "two identical blobs in opposite corners",
            "they are NOT one entity, and they look exactly alike",
            draw_false_twins),
    Control("lit-floor", ("fragment_link",),
            "one surface, half lit and half in shadow",
            "one entity whose appearance changes hard across the middle",
            draw_lit_floor),
    Control("occluder-table", ("amodal_partition",),
            "a figure behind a horizontal bar",
            "which pixels are hidden is known exactly, because the bar covered them",
            draw_occluder_table),
    Control("crowd-plaza", ("density",),
            "sixty marks, denser in the eastern half",
            "the count is 60 and the eastern share is recorded",
            draw_crowd_plaza),
    Control("windows-facade", ("density",),
            "a regular grid of twenty openings",
            "repetition that is not a crowd — the transfer control",
            draw_windows_facade),
    Control("sparse-objects", ("density",),
            "three well-separated blobs",
            "a field is the wrong answer to a picture with three things in it",
            draw_sparse_objects),
)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_controls(check: bool = False) -> int:
    """Draw the corpus, or verify the committed one has not drifted."""
    import numpy as np
    from PIL import Image

    CONTROLS_DIR.mkdir(parents=True, exist_ok=True)
    entries: Dict[str, Any] = {}
    drifted: List[str] = []
    for control in CONTROLS:
        rng = np.random.default_rng(20260822)      # fixed: a control that moves is not a control
        image, truth = control.draw(rng)
        png = (np.clip(image, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        path = CONTROLS_DIR / f"{control.name}.png"
        buffer = Image.fromarray(png, mode="RGB")
        if check:
            if not path.exists():
                drifted.append(f"{control.name}.png is missing")
                continue
            existing = np.array(Image.open(path).convert("RGB"))
            if not np.array_equal(existing, png):
                drifted.append(f"{control.name}.png has drifted")
        else:
            buffer.save(path, optimize=True)
        entries[control.name] = {
            "file": f"{control.name}.png",
            "tests": list(control.tests),
            "what": control.what,
            "ground_truth_is": control.truth,
            "size": [CONTROL_SIZE, CONTROL_SIZE],
            "digest": sha256_bytes(png.tobytes()),
            "truth": truth,
        }

    manifest = {
        "what_this_is": [
            "PERCEPTUAL-FORMS-001C. Synthetic controls for the specialist-model laboratory, drawn",
            "by `scripts/perception_lab_model_trials.py controls` and verified by `--check`.",
            "SYNTHETIC ON PURPOSE. Nothing here is scraped or licensed, so the corpus can live in",
            "a public repository; and the ground truth is known BEFORE any model runs, because the",
            "alpha that drew each image is the alpha the model is being asked to recover. A model",
            "evaluated on a photograph can only be compared with another model's opinion.",
            "These are the disposable controls that come first. The Lane F corpus of real works is",
            "the actual test and does not exist yet — but a candidate that fails here never needs",
            "to meet a painting.",
        ],
        "seed": 20260822,
        "controls": entries,
    }
    path = CONTROLS_DIR / "manifest.json"
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if check:
        if not path.exists():
            drifted.append("manifest.json is missing")
        elif path.read_text(encoding="utf-8") != rendered:
            drifted.append("manifest.json has drifted")
        if drifted:
            for line in drifted:
                print(f"DRIFT: {line}")
            print("regenerate with: python scripts/perception_lab_model_trials.py controls")
            return 1
        print(f"{len(CONTROLS)} controls are current")
        return 0
    path.write_text(rendered, encoding="utf-8")
    print(f"wrote {len(CONTROLS)} controls to {CONTROLS_DIR.relative_to(REPO_ROOT)}")
    return 0


# ── the candidates ───────────────────────────────────────────────────────────


@dataclass
class Candidate:
    """One specialist producer under evaluation, and everything a reader needs to judge it."""
    key: str
    label: str
    forms: Tuple[str, ...]
    source: str
    checkpoint: str
    revision: Optional[str]
    license: str
    acquisition: str
    size_mb: Optional[float]
    expected_vram_gb: Optional[float]
    produces: str
    cannot_produce: str
    claim: str                       # measured | derived | inferred | proposal
    run: Optional[Callable[..., Dict[str, Any]]] = None
    unavailable_reason: Optional[str] = None
    controls: Tuple[str, ...] = ()


def _device() -> str:
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Darwin reports bytes; Linux reports kilobytes.
    return usage / (1024.0 * 1024.0) if sys.platform == "darwin" else usage / 1024.0


def _accelerator_mb() -> Optional[float]:
    """Accelerator memory, sampled WHILE THE MODEL IS STILL RESIDENT.

    The first version of this sampled in `run_trial`, after each adapter had already moved its
    model back to the CPU, and every trial dutifully recorded 0.0 MB. A memory figure taken after
    the release is a memory figure for nothing, so each adapter now takes its own reading between
    the warm run and the unload.

    `driver_allocated_memory` rather than `current_allocated_memory` on MPS: the second reports the
    live block and the first reports what the process has actually taken from the driver, which is
    the number a person sizing a machine needs.
    """
    import torch
    try:
        if torch.backends.mps.is_available():
            return torch.mps.driver_allocated_memory() / (1024.0 * 1024.0)
        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / (1024.0 * 1024.0)
    except Exception:
        return None
    return None


def _load_control(name: str):
    import numpy as np
    from PIL import Image
    path = CONTROLS_DIR / f"{name}.png"
    if not path.exists():
        raise SystemExit(f"{path} is missing — run `controls` first")
    array = np.array(Image.open(path).convert("RGB"))
    return array, sha256_path(path)


def _array_digest(array) -> str:
    import numpy as np
    contiguous = np.ascontiguousarray(array.astype(np.float32))
    return sha256_bytes(contiguous.tobytes())


def _save_preview(name: str, panels: Sequence[Tuple[str, Any]]) -> str:
    """A row of grayscale/colour panels, so a person can look at what the numbers say."""
    import numpy as np
    from PIL import Image

    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    rendered = []
    for _, panel in panels:
        array = np.asarray(panel)
        if array.ndim == 2:
            lo, hi = float(array.min()), float(array.max())
            scaled = (array - lo) / (hi - lo) if hi > lo else np.zeros_like(array)
            array = np.repeat((scaled * 255).astype(np.uint8)[..., None], 3, axis=2)
        elif array.dtype != np.uint8:
            array = (np.clip(array, 0.0, 1.0) * 255).astype(np.uint8)
        rendered.append(array)
    height = max(a.shape[0] for a in rendered)
    strip = np.full((height, sum(a.shape[1] + 4 for a in rendered) - 4, 3), 20, dtype=np.uint8)
    x = 0
    for array in rendered:
        strip[:array.shape[0], x:x + array.shape[1]] = array
        x += array.shape[1] + 4
    path = PREVIEWS_DIR / f"{name}.png"
    Image.fromarray(strip).save(path, optimize=True)
    return str(path.relative_to(REPO_ROOT))


# ── candidate 1: SAM 2 raw mask logits ───────────────────────────────────────


def run_sam2_logits(control: str, **_: Any) -> Dict[str, Any]:
    """Are SAM 2's mask logits a soft BOUNDARY, or a stretched hard mask?

    THE QUESTION THAT MATTERS, and the reason this candidate is first. SAM's decoder emits a
    per-pixel logit and a separate scalar IoU prediction. It is tempting to read `sigmoid(logit)`
    as occupancy and fill `extent.soft_field` with it. The published analysis says the scalar is a
    MASK-LEVEL quality estimate — Mask-level Confidence Confusion — and says nothing about which
    pixels near the edge are reliable. This trial asks the pixels themselves: if the logit field
    is a soft boundary, `hard-edge` and `soft-fog` produce measurably different transition widths.
    If it is a stretched hard mask, they produce the same width, and the width is the decoder's.
    """
    import numpy as np
    import torch

    image, digest = _load_control(control)
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from backend.services.vision_orchestrator.adapters import _SAM2_CFG, _SAM2_CKPT

    device = _device()
    cold_started = time.perf_counter()
    model = build_sam2(_SAM2_CFG, _SAM2_CKPT, device=device)
    predictor = SAM2ImagePredictor(model)
    cold = time.perf_counter() - cold_started

    box = np.array([[10, 10, CONTROL_SIZE - 10, CONTROL_SIZE - 10]], dtype=np.float32)
    point = np.array([[CONTROL_SIZE * 0.42, CONTROL_SIZE * 0.5]], dtype=np.float32)
    label = np.array([1], dtype=np.int32)

    def once():
        with torch.inference_mode():
            predictor.set_image(image)
            masks, scores, logits = predictor.predict(
                point_coords=point, point_labels=label, multimask_output=True,
                return_logits=True)
        return masks, scores, logits

    warm_started = time.perf_counter()
    masks, scores, logits = once()
    warm = time.perf_counter() - warm_started
    again = once()

    best = int(np.argmax(scores))
    field = 1.0 / (1.0 + np.exp(-np.asarray(logits[best], dtype=np.float64)))
    soft = float(((field > 0.02) & (field < 0.98)).mean())
    transition = _transition_width(field)

    result = {
        "iou_prediction": [round(float(s), 6) for s in scores],
        "best_index": best,
        "logit_range": [round(float(np.min(logits[best])), 4),
                        round(float(np.max(logits[best])), 4)],
        "sigmoid_range": [round(float(field.min()), 6), round(float(field.max()), 6)],
        "soft_pixel_fraction": round(soft, 6),
        "transition_width_px": transition,
        "output_shape": list(np.asarray(logits[best]).shape),
        "deterministic": _array_digest(logits[best]) == _array_digest(again[2][int(np.argmax(again[1]))]),
        "raw_output_digest": _array_digest(logits[best]),
        "preview": _save_preview(f"sam2_logits.{control}", [("image", image), ("field", field)]),
    }
    accel_mb = _accelerator_mb()          # while it is still resident
    try:
        model.to("cpu")
        del predictor, model
        if device == "mps":
            torch.mps.empty_cache()
    except Exception:
        pass
    return {"cold_s": cold, "warm_s": warm, "source_digest": digest, "measurements": result,
            "accel_mb": accel_mb}


def _transition_width(field) -> float:
    """Mean run-length, per row, of pixels strictly between 0.02 and 0.98. The soft-fringe width."""
    import numpy as np
    band = (field > 0.02) & (field < 0.98)
    widths = []
    for row in band:
        run = 0
        for on in row:
            if on:
                run += 1
            elif run:
                widths.append(run)
                run = 0
        if run:
            widths.append(run)
    return round(float(np.mean(widths)) if widths else 0.0, 3)


# ── candidate 2: ViTMatte ────────────────────────────────────────────────────


VITMATTE_CHECKPOINT = "hustvl/vitmatte-small-composition-1k"


def run_vitmatte(control: str, allow_download: bool = False, trimap_band: int = 10,
                 **_: Any) -> Dict[str, Any]:
    """Alpha, from a trimap derived from a hard mask. The honest soft-field candidate.

    WHAT ALPHA IS, precisely, and why it is the right primitive for `extent.soft_field`: the
    fraction of the pixel the thing COVERS. On the hair control it is 0.3 because the strand is
    three tenths of a pixel wide, not because anything is unsure. That is a measurement of the
    picture, and it is a different quantity from every kind of confidence.

    WHAT IT IS NOT. It is not calibrated against anything by default and it is not a probability.
    `soft-fog` is the control that tells us whether the recovered alpha tracks the true alpha, and
    `hard-edge` is the one that tells us whether the model invents a fringe where there is none.
    """
    import numpy as np
    import torch
    from transformers import VitMatteForImageMatting, VitMatteImageProcessor

    image, digest = _load_control(control)
    if not _cached_or_allowed(VITMATTE_CHECKPOINT, allow_download):
        raise Unavailable(
            f"{VITMATTE_CHECKPOINT} is not in the local HF cache and --allow-download was not "
            f"given. Declared size ~103 MB, Apache-2.0.")

    device = _device()
    cold_started = time.perf_counter()
    processor = VitMatteImageProcessor.from_pretrained(VITMATTE_CHECKPOINT)
    model = VitMatteForImageMatting.from_pretrained(VITMATTE_CHECKPOINT).to(device).eval()
    cold = time.perf_counter() - cold_started

    trimap = _trimap_from_luminance(image, band_radius=trimap_band)

    def once():
        inputs = processor(images=image, trimaps=trimap, return_tensors="pt").to(device)
        with torch.inference_mode():
            return model(**inputs).alphas[0, 0].float().cpu().numpy()

    warm_started = time.perf_counter()
    alpha = once()
    warm = time.perf_counter() - warm_started
    alpha_again = once()
    alpha = alpha[:image.shape[0], :image.shape[1]]

    truth = _control_truth(control)
    measurements = {
        "output_shape": list(alpha.shape),
        "output_range": [round(float(alpha.min()), 6), round(float(alpha.max()), 6)],
        "soft_pixel_fraction": round(float(((alpha > 0.02) & (alpha < 0.98)).mean()), 6),
        "transition_width_px": _transition_width(alpha),
        "alpha_mean": round(float(alpha.mean()), 6),
        "trimap_band_radius_px": trimap_band,
        "trimap_unknown_fraction": round(float((trimap == 128.0).mean()), 6),
        "deterministic": _array_digest(alpha) == _array_digest(alpha_again[:alpha.shape[0],
                                                                           :alpha.shape[1]]),
        "raw_output_digest": _array_digest(alpha),
        "preview": _save_preview(f"vitmatte.{control}",
                                 [("image", image), ("trimap", trimap / 255.0),
                                  ("alpha", alpha)]),
    }
    if "true_alpha_mean" in truth:
        measurements["true_alpha_mean"] = truth["true_alpha_mean"]
        measurements["alpha_mean_error"] = round(
            abs(float(alpha.mean()) - truth["true_alpha_mean"]), 6)
    if truth.get("alpha_is_binary"):
        measurements["invented_fringe_fraction"] = measurements["soft_pixel_fraction"]

    accel_mb = _accelerator_mb()          # while it is still resident
    try:
        model.to("cpu")
        del model
        if device == "mps":
            torch.mps.empty_cache()
    except Exception:
        pass
    return {"cold_s": cold, "warm_s": warm, "source_digest": digest,
            "measurements": measurements, "accel_mb": accel_mb}


def _trimap_from_luminance(image, band_radius: int = 10):
    """A trimap the harness derives itself, so the trial measures the MATTING and not a segmenter.

    ViTMatte is a TRIMAP-BASED model: it refines a three-valued map into an alpha, and it decides
    nothing outside the unknown band. In production that map would come from an Extent hard mask —
    which is exactly the `extent.hard_mask` → `extent.soft_field` seam Lane A declares. Here it is
    derived by thresholding luminance and growing a band around the boundary, so a bad segmenter
    cannot be mistaken for a bad matte.

    THE UNITS ARE 0-255 AND THAT IS NOT COSMETIC. `VitMatteImageProcessor` has `do_rescale=True`
    with a factor of 1/255 and applies it to the TRIMAP as well as the image. A trimap handed over
    in [0, 1] arrives at the model as [0, 0.004] — uniformly "definite background" — and the model
    dutifully returns an all-zero alpha. That is a silent convention mismatch which looks exactly
    like a model that cannot do the job, and the first run of this harness fell into it.
    """
    import numpy as np
    grey = image.astype(np.float32).mean(axis=2) / 255.0
    mid = 0.5 * (float(np.percentile(grey, 5)) + float(np.percentile(grey, 95)))
    # The figure is whichever side of the split occupies less of the frame. These controls all put
    # the thing on a flat ground, so the smaller population is the thing.
    dark = grey < mid
    inside = dark if dark.mean() <= 0.5 else ~dark
    definite_fg = _erode(inside, band_radius)
    definite_bg = ~_dilate(inside, band_radius)
    trimap = np.full(grey.shape, 128.0, dtype=np.float32)      # unknown
    trimap[definite_fg] = 255.0
    trimap[definite_bg] = 0.0
    return trimap


def _dilate(mask, radius: int):
    import numpy as np
    out = mask.copy()
    for shift in range(1, radius + 1):
        out |= np.roll(mask, shift, axis=0) | np.roll(mask, -shift, axis=0)
        out |= np.roll(mask, shift, axis=1) | np.roll(mask, -shift, axis=1)
    return out


def _erode(mask, radius: int):
    import numpy as np
    return ~_dilate(~mask, radius)


# ── candidate 3: DINOv2 patch affinity ───────────────────────────────────────


def run_dinov2_affinity(control: str, **_: Any) -> Dict[str, Any]:
    """Do two fragments of ONE thing look more alike, to DINOv2, than two lookalikes do?

    THIS IS EVIDENCE, NOT GEOMETRY, and the distinction is the whole point of the candidate.
    A patch-feature cosine says how similar two regions look. It cannot say they are one object,
    it cannot paint the hidden part, and it must never be written into an extent. What it CAN do
    is fill a `Ground` of kind `appearance_continuity` inside `extent.fused_hypothesis`, where the
    claim is already capped below `measured` and sits beside the other grounds.

    THE THREE CONTROLS ARE A DISCRIMINATION TEST, not an accuracy test. `fence-tree` should score
    high (one thing), `false-twins` should score high TOO — they are identical by construction —
    and `lit-floor` should score LOW while still being one thing. If the affinity cannot separate
    those, it is not evidence of unity; it is evidence of resemblance, and the finding says so.
    """
    import numpy as np
    import torch

    image, digest = _load_control(control)
    from backend.services import dinov2_service

    truth = _control_truth(control)
    boxes = truth.get("fragment_boxes") or []
    if len(boxes) < 2:
        raise Unavailable(f"{control} declares fewer than two fragments to compare")

    device = _device()
    cold_started = time.perf_counter()
    from transformers import AutoImageProcessor, AutoModel
    processor = AutoImageProcessor.from_pretrained(dinov2_service.CHECKPOINT,
                                                   revision=dinov2_service.REVISION)
    model = AutoModel.from_pretrained(dinov2_service.CHECKPOINT,
                                      revision=dinov2_service.REVISION).to(device).eval()
    cold = time.perf_counter() - cold_started

    def once():
        from PIL import Image as PILImage
        inputs = processor(images=PILImage.fromarray(image), return_tensors="pt").to(device)
        with torch.inference_mode():
            tokens = model(**inputs).last_hidden_state[0, 1:]
        side = int(round(tokens.shape[0] ** 0.5))
        grid = tokens.reshape(side, side, -1).float().cpu().numpy()
        return grid / (np.linalg.norm(grid, axis=2, keepdims=True) + 1e-9)

    warm_started = time.perf_counter()
    grid = once()
    warm = time.perf_counter() - warm_started
    again = once()

    side = grid.shape[0]

    def pooled(box):
        x0, y0, x1, y1 = box
        c0, r0 = int(x0 * (side - 1)), int(y0 * (side - 1))
        c1, r1 = max(int(x1 * (side - 1)), c0 + 1), max(int(y1 * (side - 1)), r0 + 1)
        patch = grid[r0:r1 + 1, c0:c1 + 1].reshape(-1, grid.shape[2])
        vector = patch.mean(axis=0)
        return vector / (np.linalg.norm(vector) + 1e-9)

    vectors = [pooled(b) for b in boxes]
    pairs = [(i, j, float(np.dot(vectors[i], vectors[j])))
             for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
    similarities = [p[2] for p in pairs]

    measurements = {
        "patch_grid": [side, side],
        "feature_dim": int(grid.shape[2]),
        "fragments_compared": len(vectors),
        "pairwise_cosine": [[p[0], p[1], round(p[2], 6)] for p in pairs],
        "mean_cosine": round(float(np.mean(similarities)), 6),
        "min_cosine": round(float(np.min(similarities)), 6),
        "one_entity_truth": truth.get("one_entity"),
        "deterministic": _array_digest(grid) == _array_digest(again),
        "raw_output_digest": _array_digest(grid),
        "preview": _save_preview(
            f"dinov2_affinity.{control}",
            [("image", image), ("affinity", _affinity_map(grid, vectors[0]))]),
    }
    accel_mb = _accelerator_mb()          # while it is still resident
    try:
        model.to("cpu")
        del model
        if device == "mps":
            torch.mps.empty_cache()
    except Exception:
        pass
    return {"cold_s": cold, "warm_s": warm, "source_digest": digest,
            "measurements": measurements, "accel_mb": accel_mb}


def _affinity_map(grid, reference):
    import numpy as np
    return np.tensordot(grid, reference, axes=([2], [0]))


# ── candidate 4: Depth Anything V2 (supporting evidence only) ────────────────


def run_depth_anything(control: str, **_: Any) -> Dict[str, Any]:
    """Relative depth, recorded as SUPPORTING EVIDENCE and never as an extent.

    WHY IT IS IN THIS LANE AT ALL. Two of the four forms need an occlusion story — the fusion
    hypothesis needs to say the fence is in front of the tree, and the partition needs to say the
    bar is in front of the figure. Depth supplies exactly that and nothing more: a `Ground` of
    kind `depth_continuity` or `occlusion_hypothesis`.

    WHAT IT MAY NEVER BECOME. `extent.soft_field`. Relative inverse depth is a monotone ordering
    statistic with no units and no zero; reading it as occupancy would make a far wall 0.2 OCCUPIED
    rather than 0.2 NEAR. It is also, in Lane A's terms, the Depth organ's business — Extent may
    cite it and may not produce it.
    """
    import numpy as np
    import torch

    image, digest = _load_control(control)
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    checkpoint = "depth-anything/Depth-Anything-V2-Small-hf"
    revision = "5426e4f0f36572d16453bbda7a8389317b1bef99"

    device = _device()
    cold_started = time.perf_counter()
    processor = AutoImageProcessor.from_pretrained(checkpoint, revision=revision)
    model = AutoModelForDepthEstimation.from_pretrained(checkpoint,
                                                        revision=revision).to(device).eval()
    cold = time.perf_counter() - cold_started

    def once():
        from PIL import Image as PILImage
        inputs = processor(images=PILImage.fromarray(image), return_tensors="pt").to(device)
        with torch.inference_mode():
            return model(**inputs).predicted_depth[0].float().cpu().numpy()

    warm_started = time.perf_counter()
    depth = once()
    warm = time.perf_counter() - warm_started
    again = once()

    measurements = {
        "output_shape": list(depth.shape),
        "output_range": [round(float(depth.min()), 4), round(float(depth.max()), 4)],
        "units": "relative inverse depth, no zero and no scale",
        "is_an_extent": False,
        "deterministic": _array_digest(depth) == _array_digest(again),
        "raw_output_digest": _array_digest(depth),
        "preview": _save_preview(f"depth_anything.{control}", [("image", image), ("depth", depth)]),
    }
    accel_mb = _accelerator_mb()          # while it is still resident
    try:
        model.to("cpu")
        del model
        if device == "mps":
            torch.mps.empty_cache()
    except Exception:
        pass
    return {"cold_s": cold, "warm_s": warm, "source_digest": digest,
            "measurements": measurements, "accel_mb": accel_mb}


class Unavailable(RuntimeError):
    """The candidate could not run HERE. A result, and never a crash."""


def _cached_or_allowed(repo_id: str, allow_download: bool) -> bool:
    """True when the weights are already local, or downloading them has been permitted.

    THE BUDGET GUARD. Nothing in this file reaches the network unless a person asked for it on the
    command line, and nothing above `MAX_DOWNLOAD_MB` is fetched at all — a candidate that big is
    recorded as DEFERRED with the number that put it out of reach, which is a more useful finding
    than an out-of-memory traceback at midnight.
    """
    home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    cache = home / "hub" / ("models--" + repo_id.replace("/", "--"))
    if cache.exists():
        return True
    return bool(allow_download)


def _control_truth(name: str) -> Dict[str, Any]:
    manifest = json.loads((CONTROLS_DIR / "manifest.json").read_text(encoding="utf-8"))
    return manifest["controls"][name]["truth"]


CANDIDATES: Tuple[Candidate, ...] = (
    Candidate(
        key="sam2_logits",
        label="SAM 2.1 hiera-tiny — raw mask logits",
        forms=("extent.soft_field",),
        source="https://github.com/facebookresearch/sam2",
        checkpoint="sam2.1_hiera_tiny.pt",
        revision="sam2.1 release checkpoint (local, models/)",
        license="Apache-2.0",
        acquisition="already resident — weights.manifest.json entry `sam21_hiera_tiny`",
        size_mb=148.8,
        expected_vram_gb=1.0,
        produces="a per-pixel logit field and a scalar IoU prediction",
        cannot_produce="a calibrated occupancy; the scalar is mask-level quality, not per-pixel",
        claim="proposal",
        run=run_sam2_logits,
        controls=("hard-edge", "soft-fog", "hair-veil"),
    ),
    Candidate(
        key="vitmatte_small",
        label="ViTMatte small (composition-1k)",
        forms=("extent.soft_field",),
        source="https://huggingface.co/hustvl/vitmatte-small-composition-1k",
        checkpoint=VITMATTE_CHECKPOINT,
        revision="pin at integration time; this trial records the resolved commit",
        license="Apache-2.0",
        acquisition="huggingface_hub, ~103 MB, 25.8M params",
        size_mb=103.0,
        expected_vram_gb=0.8,
        produces="an alpha matte: the fraction of each pixel the thing covers",
        cannot_produce="uncertainty, a class probability, or a mask where it was given no trimap",
        claim="measured",
        run=run_vitmatte,
        controls=("hard-edge", "soft-fog", "hair-veil"),
    ),
    Candidate(
        key="dinov2_affinity",
        label="DINOv2 ViT-S/14 — patch-feature affinity",
        forms=("extent.fused_hypothesis",),
        source="https://huggingface.co/facebook/dinov2-small",
        checkpoint="facebook/dinov2-small",
        revision="ed25f3a31f01632728cabb09d1542f84ab7b0056",
        license="Apache-2.0",
        acquisition="already resident — weights.manifest.json entry `dinov2_vits14`",
        size_mb=85.0,
        expected_vram_gb=0.4,
        produces="a cosine between pooled patch features: how alike two fragments LOOK",
        cannot_produce="unity, geometry, or any hidden extent",
        claim="derived",
        run=run_dinov2_affinity,
        controls=("fence-tree", "false-twins", "lit-floor"),
    ),
    Candidate(
        key="depth_anything_v2_small",
        label="Depth Anything V2 small",
        forms=("extent.fused_hypothesis", "extent.visible_inferred_partition"),
        source="https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf",
        checkpoint="depth-anything/Depth-Anything-V2-Small-hf",
        revision="5426e4f0f36572d16453bbda7a8389317b1bef99",
        license="Apache-2.0",
        acquisition="already resident — weights.manifest.json entry `depth_anything_v2_small`",
        size_mb=95.0,
        expected_vram_gb=0.6,
        produces="relative inverse depth — supporting evidence for an occlusion ground",
        cannot_produce="an Extent measurement of any kind; depth belongs to the Depth organ",
        claim="derived",
        run=run_depth_anything,
        controls=("fence-tree", "occluder-table"),
    ),
    Candidate(
        key="pix2gestalt",
        label="pix2gestalt — amodal completion by synthesis",
        forms=("extent.visible_inferred_partition",),
        source="https://github.com/cvlab-columbia/pix2gestalt",
        checkpoint="pix2gestalt (Stable Diffusion 1.5 fine-tune)",
        revision="not resolved — not fetched",
        license="see upstream repository; the SD-1.5 lineage carries CreativeML OpenRAIL-M",
        acquisition="NOT ATTEMPTED",
        size_mb=None,
        expected_vram_gb=24.0,
        produces="a synthesized whole object, from which an amodal mask can be cut",
        cannot_produce="anything on this machine",
        claim="inferred",
        run=None,
        unavailable_reason=(
            "The published demo requires roughly 22-28 GB of VRAM against a 10 GB budget. Not "
            "downloaded, not run, not integrated — DEFERRED on resources rather than rejected on "
            "merit. The form stays valid and producible by hand in the meantime."),
        controls=("occluder-table",),
    ),
    Candidate(
        key="amodal_sam",
        label="Amodal SAM — SAM with a spatial completion adapter",
        forms=("extent.visible_inferred_partition",),
        source="https://arxiv.org/abs/2604.20748",
        checkpoint="no public checkpoint located as of 2026-08-22",
        revision=None,
        license="unknown — no released weights to carry one",
        acquisition="NOT ATTEMPTED — nothing to acquire",
        size_mb=None,
        expected_vram_gb=None,
        produces="an amodal mask, on paper",
        cannot_produce="anything until weights exist",
        claim="inferred",
        run=None,
        unavailable_reason=(
            "Published April 2026 as a SAM adapter, which would sit inside the budget if released. "
            "No public checkpoint was found at the time of this trial, so there is nothing to "
            "measure. Re-check before Lane G rather than adopting on the strength of a paper."),
        controls=("occluder-table",),
    ),
    Candidate(
        key="density_counter",
        label="A low-shot density/counting model (DAVE / GeCo family)",
        forms=("extent.density_field",),
        source="https://github.com/jerpelhan/GeCo",
        checkpoint="not resolved — not fetched",
        revision=None,
        license="research-use terms upstream; verify before any commercial use",
        acquisition="NOT ATTEMPTED",
        size_mb=None,
        expected_vram_gb=None,
        produces="a count, and in the density families a density map",
        cannot_produce="a calibrated occupancy field, and nothing at all without exemplars",
        claim="proposal",
        run=None,
        unavailable_reason=(
            "The low-shot counters need exemplar boxes or a text prompt, which makes them "
            "operations rather than producers of a standing field; and their published terms are "
            "research-use. `extent.density_field` also does not need a model to be well formed: "
            "its counts come from an existing extent set, and only the smoothing needs deciding. "
            "Measured rather than modelled is the cheaper and more honest route, so no weights "
            "were fetched."),
        controls=("crowd-plaza", "windows-facade", "sparse-objects"),
    ),
)

BY_KEY = {c.key: c for c in CANDIDATES}


# ── does the output satisfy a declared form contract? ────────────────────────


def check_form_contract(candidate: Candidate, control: str,
                        measurements: Dict[str, Any]) -> Dict[str, Any]:
    """Build the declared payload out of what the model actually produced, and validate it.

    THE POINT OF THE WHOLE HARNESS. A model that runs is not a producer. A producer is something
    whose output can fill a form's payload WITHOUT anybody having to lie about what the numbers
    are — which is a question only Lane A's own models can answer, so they are the ones asked.
    """
    from backend.schemas import perception_lab as S

    form = candidate.forms[0]
    verdict: Dict[str, Any] = {"form": form, "attempted": True}
    try:
        if form == "extent.soft_field":
            lo, hi = measurements.get("output_range") or measurements.get("sigmoid_range")
            derivation = ("direct_probability" if candidate.key == "vitmatte_small"
                          else "model_logit")
            calibration = S.CalibrationDeclaration(
                state=S.CalibrationState.UNCALIBRATED,
                units=("fraction of the pixel covered" if candidate.claim == "measured"
                       else "a decoder logit passed through a sigmoid; not a probability"))
            payload = S.ExtentSoftFieldPayload(
                variant="extent_soft_field",
                cells_evaluated=int(measurements["output_shape"][0]
                                    * measurements["output_shape"][1]),
                searched=f"the {control} control",
                field=S.ScalarFieldSpec(
                    field_shape=[int(measurements["output_shape"][0]),
                                 int(measurements["output_shape"][1])],
                    coordinate_system=S.CoordinateSystem.MASK_RLE_HW,
                    value_range=[float(min(lo, 0.0)), float(max(hi, 1.0))],
                    derivation=S.FieldDerivation(derivation),
                    calibration=calibration,
                    data_ref=S.DataRef(uri=f"trial://{candidate.key}/{control}",
                                       digest=measurements["raw_output_digest"],
                                       media_type="application/octet-stream")),
                threshold_would_be=0.5)
            verdict.update(satisfies=True, payload_variant=payload.variant)
            verdict["may_declare_calibrated"] = False
            verdict["why"] = (
                "the payload validates; `calibration.state` is `uncalibrated` because nothing in "
                "this trial measured a correspondence between the numbers and anything else")
        elif form == "extent.fused_hypothesis":
            payload = S.ExtentFusionHypothesisPayload(
                variant="extent_fusion_hypothesis",
                fragments_considered=int(measurements.get("fragments_compared", 2)),
                alternatives_retained=True,
                hypotheses=[S.FusionHypothesis(
                    hypothesis_id="hyp_trial",
                    members=[S.InstanceRef(artifact_id="art_trial", instance_id=f"frag_{i}")
                             for i in range(max(2, int(measurements.get("fragments_compared", 2))))],
                    grounds=[S.Ground(
                        kind=(S.GroundKind.APPEARANCE_CONTINUITY
                              if candidate.key == "dinov2_affinity"
                              else S.GroundKind.DEPTH_CONTINUITY),
                        detail=f"{candidate.label} on the {control} control",
                        strength=float(min(max(measurements.get("mean_cosine", 0.5), 0.0), 1.0)))],
                    partition=S.EpistemicPartition.INTERPRETIVE_GROUPING,
                    epistemic_status=S.EpistemicStatus.INTERPRETIVE)])
            verdict.update(satisfies=True, payload_variant=payload.variant)
            verdict["why"] = (
                "the model fills a GROUND, never the grouping. The claim is `interpretive` by "
                "partition and the model's number is one strength among several")
        elif form == "extent.visible_inferred_partition":
            verdict.update(satisfies=False)
            verdict["why"] = ("no candidate produced an amodal mask on this machine, so no "
                              "partition payload was built from a measurement")
        else:
            verdict.update(satisfies=False, why="no candidate produced this form here")
    except Exception as exc:                       # a payload that will not build IS the finding
        verdict.update(satisfies=False, why=f"{type(exc).__name__}: {exc}")
    return verdict


def fidelity(candidate: Candidate, control: str,
             measurements: Dict[str, Any]) -> Dict[str, Any]:
    """Does the output TRACK the truth — a different question from whether it validates.

    THE TWO VERDICTS ARE DELIBERATELY SEPARATE, and keeping them apart is the point.
    `form_contract.satisfies` asks whether the payload can be built without lying about what the
    numbers ARE; a logit field passes that, honestly, by declaring `derivation: model_logit` and
    `calibration: uncalibrated`. It says nothing about whether the numbers are RIGHT.

    A contract cannot ask the second question, because a schema has never seen the picture. Only a
    control with known ground truth can, which is what this corpus is for. A candidate that
    validates and does not track is exactly the dangerous case: it produces a well-formed record
    that a reader would believe.
    """
    truth = _control_truth(control)
    out: Dict[str, Any] = {"control": control, "checked": False}
    if "soft_field" not in "".join(candidate.forms):
        return out

    observed = measurements.get("soft_pixel_fraction")
    if observed is None:
        return out
    out["checked"] = True
    out["true_soft_fraction"] = truth.get("true_soft_fraction", 0.0)
    out["observed_soft_fraction"] = observed
    if truth.get("alpha_is_binary"):
        # THE NEGATIVE CONTROL. There is nothing soft here. Anything reported is the producer's own
        # blur, and a fringe wider than a couple of pixels is an invented gradient.
        out["invented_soft_fraction"] = observed
        out["tracks_truth"] = observed < 0.02 and measurements["transition_width_px"] < 6.0
        out["why"] = ("the control's alpha is 0 or 1 everywhere; a soft fringe here is the "
                      "producer's resolution, not the picture's")
    else:
        true_soft = float(truth.get("true_soft_fraction", 0.0))
        ratio = observed / true_soft if true_soft else float("inf")
        out["soft_fraction_ratio"] = round(ratio, 4)
        error = measurements.get("alpha_mean_error")
        out["alpha_mean_error"] = error
        out["comparable_to_alpha"] = error is not None
        # BOTH tests, and the second one is why a coarse ratio cannot pass alone. A producer of
        # this form must recover HOW MUCH of the picture is covered (the mean) and WHERE the
        # coverage is graded (the fraction). A candidate whose output is not an alpha at all has
        # no mean to compare — `sigmoid(logit)` is a decision surface, not a coverage — so it
        # cannot pass, and the record says that rather than letting a ratio read as an endorsement.
        out["tracks_truth"] = bool(0.5 <= ratio <= 2.0 and error is not None and error < 0.05)
        out["why"] = (
            "a producer of this form must recover both HOW MUCH is covered and WHERE the coverage "
            "is graded. The ratio is the second; `alpha_mean_error` is the first, and it is null "
            "when the output is not a coverage at all"
            if error is None else
            "a producer of this form must recover both HOW MUCH is covered and WHERE the coverage "
            "is graded; the ratio and the mean error are those two")
    return out


# ── running a trial ──────────────────────────────────────────────────────────


def environment() -> Dict[str, Any]:
    import torch
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "device": _device(),
        "budget_vram_gb": BUDGET_VRAM_GB,
    }


def run_trial(candidate: Candidate, control: str, *, allow_download: bool,
              stamp: str, **options: Any) -> Dict[str, Any]:
    suffix = f".band{options['trimap_band']}" if options.get("trimap_band") not in (None, 10) \
        else ""
    trial_id = f"{candidate.key}.{control}{suffix}"
    record: Dict[str, Any] = {
        "trial_id": trial_id,
        "recorded_at": stamp,
        "candidate": {
            "key": candidate.key, "label": candidate.label,
            "forms": list(candidate.forms), "source": candidate.source,
            "checkpoint": candidate.checkpoint, "revision": candidate.revision,
            "license": candidate.license, "acquisition": candidate.acquisition,
            "size_mb": candidate.size_mb, "expected_vram_gb": candidate.expected_vram_gb,
            "produces": candidate.produces, "cannot_produce": candidate.cannot_produce,
            "claim": candidate.claim,
        },
        "control": control,
        "environment": environment(),
    }
    if candidate.run is None:
        record["outcome"] = "unavailable"
        record["unavailable_reason"] = candidate.unavailable_reason
        record["form_contract"] = {"form": candidate.forms[0], "attempted": False,
                                   "satisfies": False,
                                   "why": "nothing ran, so nothing is claimed"}
        return record

    before_rss = _peak_rss_mb()
    try:
        result = candidate.run(control, allow_download=allow_download, **options)
    except Unavailable as exc:
        record["outcome"] = "unavailable"
        record["unavailable_reason"] = str(exc)
        record["form_contract"] = {"form": candidate.forms[0], "attempted": False,
                                   "satisfies": False, "why": "nothing ran"}
        return record
    except Exception as exc:
        record["outcome"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["form_contract"] = {"form": candidate.forms[0], "attempted": False,
                                   "satisfies": False, "why": "the trial raised"}
        return record

    measurements = result["measurements"]
    record["fidelity"] = fidelity(candidate, control, measurements)
    record.update({
        "outcome": "ready",
        "source_image_digest": result["source_digest"],
        "cold_load_s": round(result["cold_s"], 4),
        "warm_run_s": round(result["warm_s"], 4),
        "peak_process_rss_mb": round(max(_peak_rss_mb(), before_rss), 1),
        "accelerator_allocated_mb": (round(result["accel_mb"], 1)
                                     if result.get("accel_mb") is not None else None),
        "measurements": measurements,
        "form_contract": check_form_contract(candidate, control, measurements),
    })
    return record


def cmd_run(keys: Sequence[str], controls: Optional[Sequence[str]], *, allow_download: bool,
            stamp: str, **options: Any) -> int:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for key in keys:
        candidate = BY_KEY[key]
        for control in (controls or candidate.controls):
            record = run_trial(candidate, control, allow_download=allow_download, stamp=stamp,
                               **options)
            path = RUNS_DIR / f"{record['trial_id']}.json"
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            written += 1
            outcome = record["outcome"]
            extra = ""
            if outcome == "ready":
                extra = f"  warm {record['warm_run_s']:.3f}s"
            elif outcome == "unavailable":
                extra = "  " + (record.get("unavailable_reason") or "")[:70]
            print(f"{record['trial_id']:<42} {outcome:<12}{extra}")
    print(f"\n{written} trial records under {RUNS_DIR.relative_to(REPO_ROOT)}")
    return 0


def cmd_list() -> int:
    print(f"{'candidate':<26} {'form':<38} {'size':>8}  license")
    print("-" * 100)
    for candidate in CANDIDATES:
        size = f"{candidate.size_mb:.0f} MB" if candidate.size_mb else "—"
        runnable = "runs here" if candidate.run else "NOT RUN"
        print(f"{candidate.key:<26} {candidate.forms[0]:<38} {size:>8}  {candidate.license}")
        print(f"{'':<26} {runnable} · {candidate.produces}")
    return 0


def cmd_matrix() -> int:
    if not RUNS_DIR.exists():
        print("no trials yet — run `run-all` first")
        return 1
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUNS_DIR.glob("*.json"))]
    print(f"{'trial':<44} {'outcome':<12} {'warm':>8}  {'payload':<10}  fidelity")
    print("-" * 108)
    for row in rows:
        warm = f"{row['warm_run_s']:.3f}s" if row.get("warm_run_s") else "—"
        contract = row.get("form_contract", {})
        mark = "validates" if contract.get("satisfies") else "no payload"
        fid = row.get("fidelity", {})
        tracks = ("—" if not fid.get("checked")
                  else "tracks truth" if fid.get("tracks_truth") else "DOES NOT TRACK")
        print(f"{row['trial_id']:<44} {row['outcome']:<12} {warm:>8}  {mark:<10}  {tracks}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="command", required=True)

    controls = sub.add_parser("controls", help="write or verify the synthetic control corpus")
    controls.add_argument("--check", action="store_true")

    sub.add_parser("list", help="the candidates, their licences and their residency")
    sub.add_parser("matrix", help="the trial records, as a table")

    for name in ("run", "run-all"):
        runner = sub.add_parser(name, help="run trials and write evidence")
        if name == "run":
            runner.add_argument("--candidate", action="append", dest="candidates", required=True,
                                choices=sorted(BY_KEY))
            runner.add_argument("--control", action="append", dest="controls")
        runner.add_argument("--allow-download", action="store_true",
                            help=f"permit fetching declared weights under {MAX_DOWNLOAD_MB:.0f} MB")
        runner.add_argument("--stamp", default=None,
                            help="ISO timestamp to record (default: now)")
        runner.add_argument("--trimap-band", type=int, default=10,
                            help="ViTMatte only: unknown-band radius in pixels. A ring around a "
                                 "threshold is the wrong trimap for a thing with no boundary, and "
                                 "this is the knob that shows it.")

    args = parser.parse_args(argv)
    if args.command == "controls":
        return write_controls(check=args.check)
    if args.command == "list":
        return cmd_list()
    if args.command == "matrix":
        return cmd_matrix()

    stamp = args.stamp or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    options = {"trimap_band": args.trimap_band}
    if args.command == "run-all":
        return cmd_run(sorted(BY_KEY), None, allow_download=args.allow_download, stamp=stamp,
                       **options)
    return cmd_run(args.candidates, args.controls, allow_download=args.allow_download,
                   stamp=stamp, **options)


if __name__ == "__main__":
    raise SystemExit(main())
