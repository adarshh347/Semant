"""
CIRCUIT-001 P6-F — Depth-Anything-V2-Small: relative depth as a perceptual field.

The roster has carried `depth_anything_v2_small` as a deferred spec since VISION-MODEL-MATRIX-001;
this is the class behind it. Depth-Anything-V2-Small (24.8M params, ~100 MB, Apache-2.0) is small
enough to share the 4 GB card with everything else, and `transformers` supports it natively
(`DepthAnythingForDepthEstimation`) — no extra package, no system deps.

What it gives the circuit: a RELATIVE depth map, which is what `atmosphere_field` and
`background_recession` are actually about — not "how far in metres" but "what falls away behind".
The map is inverse-depth (larger = nearer), so recession is its complement; both bands are read by
the producers in `suggestion_service`.

Mirrors `dinov2_service`: a lazy GPU singleton with an explicit `unload()`, so `ModelManager` can
enforce single-GPU residency (loading depth evicts DINOv2/SAM, and vice versa). The map is reduced
to a coarse grid of block means before it leaves this module, which is the shape the pure
converters consume — so the field logic stays testable with synthetic maps and no GPU.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

CHECKPOINT = "depth-anything/Depth-Anything-V2-Small-hf"
# WEIGHTS-001 — pinned HF commit. Passed to every from_pretrained below so the pin is
# ENFORCED at load, not merely recorded. Mirrors weights.manifest.json.
REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"
MODEL_TAG = "depth_anything_v2_small"
PREPROCESSING_VERSION = "depth-anything-v2-s-v1"
GRID = 16                      # same coarse grid as DINOv2 patches / cpu_perceptual

_model = None
_processor = None
_load_failed = False


def is_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load() -> None:
    global _model, _processor, _load_failed
    if _model is not None or _load_failed:
        return
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        proc = AutoImageProcessor.from_pretrained(CHECKPOINT, revision=REVISION)
        model = AutoModelForDepthEstimation.from_pretrained(CHECKPOINT, revision=REVISION)
        _processor = proc
        _model = model.to(_device()).to(torch.float32).eval()
    except Exception as e:  # pragma: no cover - depends on weights/hardware
        _load_failed = True
        print(f"⚠️ Depth-Anything load failed (non-fatal): {e}")


def unload() -> None:
    """Free the model + GPU memory — called when the GPU slot goes to another adapter."""
    global _model, _processor
    _model = None
    _processor = None
    try:
        import torch, gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _to_grid(arr, grid: int) -> List[float]:
    """A dense depth map → `grid × grid` block means, row-major."""
    h, w = arr.shape
    out: List[float] = []
    for gy in range(grid):
        y0, y1 = gy * h // grid, max(gy * h // grid + 1, (gy + 1) * h // grid)
        for gx in range(grid):
            x0, x1 = gx * w // grid, max(gx * w // grid + 1, (gx + 1) * w // grid)
            cell = arr[y0:y1, x0:x1]
            out.append(float(cell.mean()) if cell.size else 0.0)
    return out


def estimate(image, *, grid: int = GRID) -> Optional[Dict[str, Any]]:
    """A PIL image → ``{"depth": [...], "grid": n}``, a coarse relative-depth grid.

    Values are the model's inverse-depth output (LARGER = NEARER), left in their raw scale — the
    pure converters normalize and band them. Returns None when the model is unavailable or failed
    to load, which the producer surfaces as an honest refusal rather than a flat field."""
    if not is_available():
        return None
    import torch
    _load()
    if _model is None:
        return None
    im = image.convert("RGB")
    inputs = _processor(images=im, return_tensors="pt").to(_device())
    with torch.no_grad():
        predicted = _model(**inputs).predicted_depth      # (1, H, W) inverse depth
    arr = predicted[0].float().cpu().numpy()
    return {"depth": _to_grid(arr, grid), "grid": grid}
