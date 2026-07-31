"""
CIRCUIT-001 P6-G — Intrinsic (Careaga/Aksoy Ordinal Shading): light and shadow as fields.

The Monet answer. Every other field producer reads WHAT is where — a mask, a material, a
texture, a distance. This one reads the LIGHT: intrinsic decomposition separates an image into
albedo (the surface's own colour) and shading (the light falling on it), so `light_field` is the
shading map and `shadow_field` is its inverse. That is the difference between "there is a
haystack here" and "this is what the light is doing to the haystack".

STATUS: ACTIVE (P6-I) — real weights, verified end to end.
=========================================================
Installing it is still not a `pip install` (which is why P6-G shipped this deferred):

  · it is not on PyPI — `pip install intrinsic` resolves to an unrelated stub that is ALSO
    version 0.0.1, so the version string cannot tell them apart. `is_available()` therefore
    probes `intrinsic.pipeline` + `chrislib`, never the bare name or a version;
  · the real package is a GitHub repo (`compphoto/Intrinsic`) and pulls `chrislib` and
    `altered_midas` (a MiDaS fork) transitively — ONE requirement line, not three;
  · `altered_midas` additionally does `torch.hub.load("rwightman/gen-efficientnet-pytorch")`
    WITHOUT `trust_repo`, so first load needs that repo in torch's trusted_list (a human
    consent step — an undocumented fourth dependency);
  · checkpoints are not on the HF hub. First load pulls ~850 MB into ~/.cache/torch/hub:
    `final_weights.pt` (485 MB) + the ResNeXt-101 WSL backbone (340 MB) + the
    gen-efficientnet repo. (P6-G's scaffold guessed "~100 MB" — wrong by ~8×.)

Measured on the GTX 1650: load ≈5.5 s / 492 MiB resident, inference ≈945 ms warm, peak
≈984 MiB. That makes this the HEAVIEST producer in the roster (Depth peaks 234 MiB, DINOv2 99),
so single-GPU residency matters more here than anywhere else — `unload()` is not optional.

GRAYSCALE ONLY, deliberately. `paper_weights` is the V1 release from the ordinal-shading paper;
`load_models` forces `stage = 1` for it, so the multi-stage `run_pipeline` dies with
`KeyError: 'col_model'`. The correct entry point is **`run_gray_pipeline`**, whose `gry_shd` is a
single-channel shading map — exactly what a light field wants, and it avoids the heavier v2
five-stage download. (The v2/v2.1 weights would enable colour shading if ever needed.)

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

# CONFIRMED against a real run (P6-I): `run_gray_pipeline` returns
#   gry_shd (704,544) float32  ← the shading map, single channel. THIS one.
#   gry_alb (…,3)              — albedo, the surface's own colour, NOT the light
#   ord_base / ord_full (…,1)  — intermediate ordinal estimates, NOT the final shading
#   image / lin_img            — the inputs echoed back
# Pinned rather than tolerant: a silently-wrong key would yield a plausible-looking field
# derived from albedo, which is precisely the kind of confident nonsense the receipts exist to
# prevent. If a future weights release renames it, this must FAIL loudly, not guess.
SHADING_KEY = "gry_shd"

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
        # `load_models` lives in intrinsic.pipeline — NOT intrinsic.model_util, which P6-G's
        # scaffold guessed and which does not exist in the real package.
        from intrinsic.pipeline import load_models
        _model = load_models("paper_weights", device=_device())
    except Exception as e:  # pragma: no cover — depends on the GitHub install + checkpoints
        _load_failed = True
        print(f"⚠️ Intrinsic load failed (non-fatal, light/shadow report unavailable): {e}")


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
    """Pull the shading map out of a gray-pipeline result — by its CONFIRMED key, `gry_shd`.

    No fallback chain. The result also carries `gry_alb` (albedo) and `ord_base`/`ord_full`
    (intermediate ordinal estimates), each of which is a same-shaped float map that would produce
    a perfectly plausible-looking field while meaning something else entirely. Guessing among them
    is worse than failing: a field derived from albedo would claim to be light and be wrong, with a
    full model receipt attached. So an absent key returns None and the producer refuses."""
    if not isinstance(result, dict):
        return None
    return result.get(SHADING_KEY)


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
    None when the package is unavailable, the model failed to load, or the result carries no
    `gry_shd` — each an honest refusal rather than a flat or mis-derived field."""
    if not is_available():
        return None
    _load()
    if _model is None:
        return None
    try:
        import numpy as np
        # run_GRAY_pipeline: `paper_weights` is the V1 grayscale-only release (load_models forces
        # stage=1 for it), so the multi-stage run_pipeline raises KeyError: 'col_model'.
        from intrinsic.pipeline import run_gray_pipeline
        arr = np.asarray(image.convert("RGB"), dtype="float32") / 255.0
        result = run_gray_pipeline(_model, arr)
        shading = _extract_shading(result)
        if shading is None:
            return None
        return {"shading": _to_grid(shading, grid), "grid": grid}
    except Exception as e:  # pragma: no cover — depends on GPU + checkpoints
        print(f"⚠️ Intrinsic inference failed (non-fatal): {e}")
        return None
