"""
CIRCUIT-001 P6-D — cpu_perceptual: signal processing, no learned model.

The third producer archetype. `negative_space` derives a field from a mask that already
exists; `material_field` derives one from a learned embedding; this one derives it from the
image signal itself — Gabor energy (repetition/texture → `rhythm`) and structure-tensor
coherence (directional organisation → `pressure_zone`). No weights, no download, no GPU: it
runs on the CPU_LIGHT pool ALONGSIDE a resident GPU model rather than evicting it.

Implemented on **OpenCV + numpy only** (no scikit-image — it is not installed, and every
operator here is a few lines of cv2). Both maps are reduced to a coarse `grid × grid` of
block means, which is the shape the pure converters in `mask_geometry` consume: the field
logic stays testable with synthetic maps and never needs cv2 in CI.

Deterministic: same pixels in, same numbers out. There is nothing to load and nothing to
unload, so `load()` is free and residency never applies.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

MODEL_TAG = "cpu_perceptual"
PREPROCESSING_VERSION = "cpu-perceptual-v1"     # grayscale → 256² → gabor bank + structure tensor
_INPUT = 256
GRID = 16                                        # matches DINOv2's 16×16 patch grid, deliberately


def is_available() -> bool:
    """True whenever cv2 + numpy import. No weights, no GPU, nothing to fetch — so this
    adapter is available on any box that can run the backend at all."""
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def _to_grid(arr, grid: int) -> List[float]:
    """A dense response map → `grid × grid` block means, row-major. Coarse on purpose: a
    field is a felt region, not a per-pixel segmentation."""
    h, w = arr.shape
    out: List[float] = []
    for gy in range(grid):
        y0, y1 = gy * h // grid, max(gy * h // grid + 1, (gy + 1) * h // grid)
        for gx in range(grid):
            x0, x1 = gx * w // grid, max(gx * w // grid + 1, (gx + 1) * w // grid)
            cell = arr[y0:y1, x0:x1]
            out.append(float(cell.mean()) if cell.size else 0.0)
    return out


def analyze(image, *, grid: int = GRID) -> Optional[Dict[str, Any]]:
    """A PIL image (already cropped to whatever is being read) → the two perceptual maps.

    Returns ``{"energy": [...], "coherence": [...], "grid": n}`` — both flat row-major lists of
    ``grid*grid`` floats — or None when cv2/numpy are absent. Raw magnitudes: normalization and
    the degeneracy verdict belong to the pure converters, not here."""
    if not is_available():
        return None
    import cv2
    import numpy as np

    im = np.asarray(image.convert("L").resize((_INPUT, _INPUT)), dtype=np.float32) / 255.0

    # ── Gabor energy: repetition at several orientations and scales. The max response over
    # the bank is the "how strongly does something repeat here" signal that reads as rhythm.
    energy = np.zeros_like(im)
    for theta in (0.0, math.pi / 4, math.pi / 2, 3 * math.pi / 4):
        for lambd in (6.0, 12.0):
            kern = cv2.getGaborKernel((15, 15), 4.0, theta, lambd, 0.5, 0.0, ktype=cv2.CV_32F)
            resp = cv2.filter2D(im, cv2.CV_32F, kern)
            np.maximum(energy, np.abs(resp), out=energy)

    # ── structure-tensor coherence: how DIRECTIONAL the local gradient is. High where the
    # image organises along an axis (drapery, architecture, a pull); low where it is isotropic.
    gx = cv2.Sobel(im, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(im, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 3.0)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), 3.0)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), 3.0)
    num = np.sqrt((jxx - jyy) ** 2 + 4.0 * (jxy ** 2))
    coherence = num / (jxx + jyy + 1e-9)          # already in [0,1] by construction

    return {"energy": _to_grid(energy, grid),
            "coherence": _to_grid(coherence, grid),
            "grid": grid}
