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
import hashlib
import importlib.util
import time

CHECKPOINT = "depth-anything/Depth-Anything-V2-Small-hf"
# WEIGHTS-001 — pinned HF commit. Passed to every from_pretrained below so the pin is
# ENFORCED at load, not merely recorded. Mirrors weights.manifest.json.
REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"
MODEL_TAG = "depth_anything_v2_small"
PREPROCESSING_VERSION = "depth-anything-v2-s-v1"
GRID = 16                      # same coarse grid as DINOv2 patches / cpu_perceptual
DENSE_VERSION = "depth-anything-v2-s-native-v1"
CHECKPOINT_SHA256 = "3152477ce0d8d6978d76b995120de97cb5b928701fd0f817769f59e249a16b70"

_model = None
_processor = None
_load_failed = False
_dense_cache = None


def dense_readiness() -> tuple[bool, str]:
    """Cheap, local-only admission probe: never import torch or retrieve weights."""
    for package in ("torch", "transformers", "numpy", "PIL", "huggingface_hub"):
        if importlib.util.find_spec(package) is None:
            return False, f"Depth requires the installed {package} package."
    from huggingface_hub import try_to_load_from_cache
    for filename in ("config.json", "preprocessor_config.json", "model.safetensors"):
        if not isinstance(try_to_load_from_cache(CHECKPOINT, filename, revision=REVISION), str):
            return False, f"Pinned Depth checkpoint file is not cached: {filename}. No download was attempted."
    if _load_failed:
        return False, "Pinned Depth model previously failed to load in this process. Restart after repairing runtime."
    return True, "Pinned Depth Anything V2 Small is cached locally; inference is still an estimate."


def is_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def _device() -> str:
    """cuda → mps → cpu, resolved centrally (`torch_device`) so this box's answer is one answer."""
    from backend.services.torch_device import resolve
    return resolve()


def _load(*, local_files_only: bool = False) -> None:
    global _model, _processor, _load_failed
    if _model is not None or _load_failed:
        return
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation
        proc = AutoImageProcessor.from_pretrained(CHECKPOINT, revision=REVISION,
                                                  local_files_only=local_files_only)
        model = AutoModelForDepthEstimation.from_pretrained(CHECKPOINT, revision=REVISION,
                                                           local_files_only=local_files_only)
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
        elif hasattr(torch, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()
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


def clear_dense_cache() -> None:
    """Drop the one-result CPU numeric cache, independently of GPU model residency."""
    global _dense_cache
    _dense_cache = None


def estimate_dense(image, *, resolution: str = "standard", use_cache: bool = True) -> Dict[str, Any]:
    """Retain native predicted_depth, without min/max or metric conversion.

    The pinned processor resizes the complete image, with no crop/pad. A pixel-centre
    affine maps the prepared source to this native grid. This API never downloads;
    the caller owns scheduling/lease and unloading. The legacy API is unchanged.
    """
    global _dense_cache
    if resolution not in {"standard", "compact"}:
        raise ValueError("resolution must be standard (518) or compact (392)")
    im = image.convert("RGB")
    if min(im.size) < 1 or max(im.size) / min(im.size) > 8:
        raise ValueError("Depth requires a nonempty image with aspect ratio at most 8:1")
    digest = hashlib.sha256(im.tobytes()).hexdigest()
    key = (REVISION, DENSE_VERSION, im.size, digest, resolution)
    if use_cache and _dense_cache and _dense_cache[0] == key:
        return {**_dense_cache[1], "depth": _dense_cache[1]["depth"].copy(),
                "valid": _dense_cache[1]["valid"].copy(), "cache_hit": True,
                "load_ms": 0.0, "inference_ms": 0.0, "invocation_count": 0}
    ready, reason = dense_readiness()
    if not ready:
        raise RuntimeError(reason)
    import numpy as np
    import torch
    cached = _model is not None
    started = time.perf_counter()
    _load(local_files_only=True)
    load_ms = (time.perf_counter() - started) * 1000
    if _model is None or _processor is None:
        raise RuntimeError("Pinned Depth model failed to load; no substitute field was produced")
    if getattr(_processor, "do_pad", False) or getattr(_processor, "do_center_crop", False):
        raise RuntimeError("Depth processor crop/pad geometry is unsupported")
    device = _device()
    started = time.perf_counter()
    kwargs = {} if resolution == "standard" else {"size": {"height": 392, "width": 392}}
    inputs = _processor(images=im, return_tensors="pt", **kwargs).to(device)
    input_shape = list(inputs["pixel_values"].shape[-2:])
    if input_shape[0] * input_shape[1] > 2_500_000:
        raise ValueError("Depth preprocessed raster exceeds the bounded inference size")
    with torch.no_grad():
        predicted = _model(**inputs).predicted_depth
    arr = predicted[0].float().cpu().numpy().copy()
    inference_ms = (time.perf_counter() - started) * 1000
    if arr.ndim != 2 or not arr.size or arr.size > 2_500_000:
        raise RuntimeError("Depth model returned an invalid native raster")
    valid = np.isfinite(arr)
    arr[~valid] = 0.0
    height, width = arr.shape
    sx, sy = width / im.width, height / im.height
    result = {"depth": arr, "valid": valid, "native_shape": [height, width],
              "input_shape": input_shape, "working_size": list(im.size),
              "working_to_field": [sx, 0, (sx-1)/2, 0, sy, (sy-1)/2, 0, 0, 1],
              "preprocessing": ("pinned DPT RGB processor; bicubic aspect-preserving resize; "
                                "multiple-of-14; 1/255 and ImageNet mean/std; no crop/pad; "
                                f"{resolution}; native output retained, no post-resampling or normalization"),
              "device": device, "load_ms": load_ms, "inference_ms": inference_ms,
              "model_cached": cached, "cache_hit": False, "invocation_count": 1}
    if use_cache:
        _dense_cache = (key, {**result, "depth": arr.copy(), "valid": valid.copy()})
    return result
