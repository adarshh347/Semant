"""
CIRCUIT-001 P6-G — Intrinsic (Careaga/Aksoy Ordinal Shading): light and shadow as fields.

The Monet answer. Every other field producer reads WHAT is where — a mask, a material, a
texture, a distance. This one reads the LIGHT: intrinsic decomposition separates an image into
albedo (the surface's own colour) and shading (the light falling on it), so `light_field` is the
shading map and `shadow_field` is its inverse. That is the difference between "there is a
haystack here" and "this is what the light is doing to the haystack".

STATUS: SCAFFOLD — DEFERRED (P6-G novel-integration guard).
=========================================================
The wiring ships; the weights do not. Intrinsic is NOT a clean install:

  · it is not on PyPI — `pip install intrinsic` resolves to an unrelated 0.0.1 stub, NOT the
    Careaga/Aksoy package (installing it would be actively wrong);
  · the real package is a GitHub repo (`compphoto/Intrinsic`), and it pulls two further
    GitHub-only dependencies, `chrislib` (compphoto/chrislib) and `altered_midas`
    (compphoto's MiDaS fork);
  · its checkpoints are not on the HF hub — `load_models(...)` fetches them from the project's
    own hosting on first call.

So `is_available()` returns False on this box and the adapter registers as DEFERRED. The
converters and producers downstream are fully built and tested against synthetic shading maps,
so activating this is "install the deps and confirm the call shape" — not "write the feature".

The call surface below follows the project's documented pipeline API (`load_models` +
`run_pipeline`, whose result carries an inverse-shading map). Because the package cannot be
imported here, that shape is UNVERIFIED — `_extract_shading` is deliberately tolerant of several
plausible key names and must be confirmed against the real output at activation.

Shape mirrors `depth_service` / `dinov2_service`: a lazy GPU singleton with an explicit
`unload()`, reducing to a coarse grid before the map leaves this module, so the field logic stays
testable with synthetic input and no GPU.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

MODEL_TAG = "intrinsic_ordinal_shading"
CHECKPOINT = "compphoto/Intrinsic:paper_weights"     # custom hosting, not an HF repo id
PREPROCESSING_VERSION = "intrinsic-ordinal-v1"
GRID = 16                       # same coarse grid as depth / dinov2 / cpu_perceptual

# The keys the pipeline result might carry its shading under, best-guess first. Confirmed at
# activation; until then the tolerance is what keeps a rename from silently yielding a blank field.
_SHADING_KEYS = ("inv_shading", "shading", "gry_shd", "ord_shading")

_model = None
_load_failed = False


def is_available() -> bool:
    """True only when the REAL Intrinsic package is importable.

    Deliberately probes `intrinsic.pipeline` rather than the bare `intrinsic` name: the PyPI
    stub of that name would import fine and then produce nothing, which is exactly the kind of
    silent wrongness this codebase refuses. `chrislib` is required too — it is the project's own
    image utility package, so its presence is a good signal the GitHub install really happened."""
    try:
        import importlib
        importlib.import_module("intrinsic.pipeline")
        importlib.import_module("chrislib")
        return True
    except Exception:
        return False


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load() -> None:
    global _model, _load_failed
    if _model is not None or _load_failed:
        return
    try:
        from intrinsic.model_util import load_models
        _model = load_models("paper_weights", device=_device())
    except Exception as e:  # pragma: no cover — deferred until the deps are installed
        _load_failed = True
        print(f"⚠️ Intrinsic load failed (non-fatal, adapter stays deferred): {e}")


def unload() -> None:
    """Free the models + GPU memory — called when the GPU slot goes to another adapter."""
    global _model
    _model = None
    try:
        import torch, gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _extract_shading(result: Any):
    """Pull the shading map out of a pipeline result, tolerating the key names it may use.

    Returns a 2-D array-like, or None when nothing recognisable is present — which the producer
    surfaces as an honest refusal rather than a flat field."""
    if result is None:
        return None
    if not isinstance(result, dict):
        return result
    for key in _SHADING_KEYS:
        if key in result and result[key] is not None:
            return result[key]
    return None


def _to_grid(arr, grid: int) -> List[float]:
    """A dense shading map → `grid × grid` block means, row-major."""
    import numpy as np
    a = np.asarray(arr, dtype="float32")
    if a.ndim == 3:                       # collapse a colour shading map to luminance-ish mean
        a = a.mean(axis=2)
    h, w = a.shape[:2]
    out: List[float] = []
    for gy in range(grid):
        y0, y1 = gy * h // grid, max(gy * h // grid + 1, (gy + 1) * h // grid)
        for gx in range(grid):
            x0, x1 = gx * w // grid, max(gx * w // grid + 1, (gx + 1) * w // grid)
            cell = a[y0:y1, x0:x1]
            out.append(float(cell.mean()) if cell.size else 0.0)
    return out


def estimate(image, *, grid: int = GRID) -> Optional[Dict[str, Any]]:
    """A PIL image → ``{"shading": [...], "grid": n}``, a coarse shading grid.

    Values are the pipeline's shading magnitudes in their raw scale — LARGER = MORE LIT. The pure
    converters normalize and invert; nothing here decides what counts as light or shadow. Returns
    None when the package is unavailable or the result carries no recognisable shading map."""
    if not is_available():
        return None
    _load()
    if _model is None:
        return None
    try:
        import numpy as np
        from intrinsic.pipeline import run_pipeline
        arr = np.asarray(image.convert("RGB"), dtype="float32") / 255.0
        result = run_pipeline(_model, arr)
        shading = _extract_shading(result)
        if shading is None:
            return None
        return {"shading": _to_grid(shading, grid), "grid": grid}
    except Exception as e:  # pragma: no cover — deferred
        print(f"⚠️ Intrinsic inference failed (non-fatal): {e}")
        return None
