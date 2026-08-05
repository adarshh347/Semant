"""
CIRCUIT-001 QUALITY-001 (Q-A) — SAM2 automatic ("everything") mask generation.

The class-agnostic part proposer for the art/painting domain. YOLO11n-seg can only speak the
80 COCO nouns, so on a sculpture it trips one `person`-shaped blob and calls it done; SAM2's
automatic generator proposes regions by STRUCTURE, not by a fixed noun list, which is exactly
what drapery / torso / pedestal / veil need. The masks it returns carry no labels — honest,
since it segments extent, not meaning — and the always-on SŪKṢMA stage (or the curator) names
them afterward.

It rides the SAME SAM2 build path as the refiner adapter (`_SAM2_CFG` / `_SAM2_CKPT`), so there
is one SAM2 model identity on the box, and it loads-then-unloads for single-GPU residency on the
4 GB GTX 1650. Throttled for that card: `points_per_side=16` → 256 point prompts (not 4096 at
64), single crop layer, higher quality thresholds so fewer, cleaner masks come back.

`decomposition_adequate` is the pure QUALITY gate that replaces the old zero-gated fallback: a
lone whole-figure blob now counts as FAILURE (→ try SAM2-auto), not success. It is torch-free so
the gate is unit-testable without a GPU.
"""
from __future__ import annotations

import io
import time
from typing import Any, Dict, List, Optional

from backend.services import mask_geometry
# Ride the existing SAM2 adapter's build path — same config + checkpoint, one model identity.
from backend.services.vision_orchestrator.adapters import _SAM2_CFG, _SAM2_CKPT

MODEL_TAG = "sam2.1_hiera_tiny"
PREPROCESSING_VERSION = "sam2.1-auto"

# 4 GB throttle. points_per_side=16 → 16² = 256 point prompts (points_per_side=64 = 4096, which
# takes 16–25 s even on an RTX 3080). Single crop layer keeps VRAM and time down further.
DEFAULT_POINTS_PER_SIDE = 16
DEFAULT_POINTS_PER_BATCH = 32          # smaller batch → lower VRAM peak on the 4 GB card

# Area filters (fraction of frame): drop specks and the near-full-frame "whole image is one
# segment" mask SAM2-auto habitually emits.
_MIN_AREA_FRAC = 0.004
_MAX_AREA_FRAC = 0.92

# The QUALITY gate. A real decomposition has at least this many parts; and no single part may
# dominate the frame (a "whole-image mask + a speck" is not a sane size distribution).
MIN_PARTS = 2
MAX_DOMINANT_FRAC = 0.9

_generator = None
_load_failed = False


def is_available() -> bool:
    try:
        import torch  # noqa: F401
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator  # noqa: F401
        import os
        return os.path.exists(_SAM2_CKPT)
    except Exception:
        return False


def _device() -> str:
    """cuda → mps → cpu, resolved centrally (`torch_device`) so this box's answer is one answer."""
    from backend.services.torch_device import resolve
    return resolve()


def _load(points_per_side: int, points_per_batch: int) -> None:
    global _generator, _load_failed
    if _generator is not None or _load_failed:
        return
    try:
        from sam2.build_sam import build_sam2
        from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
        dev = _device()
        model = build_sam2(_SAM2_CFG, _SAM2_CKPT, device=dev, apply_postprocessing=False)
        _generator = SAM2AutomaticMaskGenerator(
            model,
            points_per_side=points_per_side,
            points_per_batch=points_per_batch,
            pred_iou_thresh=0.70,
            stability_score_thresh=0.90,
            crop_n_layers=0,                  # single crop — cheapest on 4 GB
            box_nms_thresh=0.70,
            min_mask_region_area=0,           # our own area filter runs post-hoc (no cv2 dep)
        )
    except Exception as e:  # pragma: no cover - depends on weights/hardware
        _load_failed = True
        print(f"⚠️ SAM2-auto load failed (non-fatal): {e}")


def unload() -> None:
    """Free the generator + GPU memory — called after a proposal so the 4 GB card is clear for
    the next adapter (single-GPU residency)."""
    global _generator
    _generator = None
    try:
        import torch
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _norm_area(region: Dict[str, Any]) -> float:
    """A region's coverage as a fraction of the frame.

    Prefers the derived normalized bbox (always present after `canonicalize_geometry`, and robust
    to whichever RLE encoding a region carries); falls back to the authoritative uncompressed RLE
    for box-less regions. Never raises — a region whose area can't be read counts as 0."""
    box = region.get("box") or {}
    try:
        w, h = float(box.get("w", 0.0)), float(box.get("h", 0.0))
        if w > 0.0 and h > 0.0:
            return max(0.0, min(1.0, w * h))
    except (TypeError, ValueError):
        pass
    rle = region.get("mask_rle")
    # rle_area only reads the uncompressed (int-list) counts form; skip compressed-string RLE.
    if isinstance(rle, dict) and isinstance(rle.get("counts"), list):
        size = rle.get("size") or [0, 0]
        total = float((size[0] or 0) * (size[1] or 0))
        if total > 0:
            try:
                return mask_geometry.rle_area(rle) / total
            except Exception:
                pass
    return 0.0


def decomposition_adequate(anchors: Optional[List[Dict[str, Any]]], *,
                           min_parts: int = MIN_PARTS,
                           max_dominant_frac: float = MAX_DOMINANT_FRAC) -> bool:
    """Is this a real part-decomposition, or one coarse blob / nothing?

    This is the QUALITY gate that replaces the old ``if not anchors`` (zero) gate. The old gate
    only failed on ZERO anchors, so the common art case — YOLO returns a single `person`-shaped
    blob for a whole sculpture (or a 5-figure collage) — sailed through as "success" and a coarse
    mislabeled anchor went to the VLM. A decomposition is adequate only when:

      - there are at least ``min_parts`` parts (a lone anchor is never a decomposition — this is
        the case the old gate missed), AND
      - no single part dominates the frame (``max_dominant_frac``) — guarding the degenerate
        "whole-image mask + a speck", which is two parts but not a sane size distribution.
    """
    if not anchors or len(anchors) < min_parts:
        return False
    largest = max(_norm_area(a) for a in anchors)
    return largest < max_dominant_frac


def generate_masks(data: bytes, *, points_per_side: int = DEFAULT_POINTS_PER_SIDE,
                   points_per_batch: int = DEFAULT_POINTS_PER_BATCH, max_regions: int = 20,
                   min_area_frac: float = _MIN_AREA_FRAC, max_area_frac: float = _MAX_AREA_FRAC
                   ) -> Optional[List[Dict[str, Any]]]:
    """Raw image bytes → class-agnostic part regions whose AUTHORITATIVE geometry is `mask_rle`.

    Mirrors `segmentation_service.segment_image_bytes`' region shape (RLE + derived
    polygons/box via `mask_geometry.canonicalize_geometry`) so these regions flow through the
    exact same merge/persist/render path as YOLO's — but labelled `detector="sam2_auto"`,
    `label=""` (extent, not meaning), and scored by SAM2's own predicted-IoU/stability.

    Returns a list (possibly `[]`) on success, or None if unavailable/errored. Loads then
    UNLOADS the model so the GPU slot is returned (single-GPU residency on 4 GB)."""
    try:
        import numpy as np
        from PIL import Image
        _load(points_per_side, points_per_batch)
        if _generator is None:
            return None
        image = np.array(Image.open(io.BytesIO(data)).convert("RGB"))
        h, w = image.shape[0], image.shape[1]
        frame = float(h * w) or 1.0

        import torch
        t0 = time.perf_counter()
        with torch.inference_mode():
            anns = _generator.generate(image)
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)

        regions: List[Dict[str, Any]] = []
        for i, ann in enumerate(anns):
            seg = ann.get("segmentation")
            if seg is None:
                continue
            mask = np.asarray(seg).astype("uint8")
            rle = mask_geometry.rle_encode_mask(mask)
            area = mask_geometry.rle_area(rle)
            if area <= 0:
                continue
            frac = area / frame
            if frac < min_area_frac or frac > max_area_frac:
                continue                                   # speck, or the whole-frame segment
            score = float(ann.get("predicted_iou") or ann.get("stability_score") or 0.0)
            region: Dict[str, Any] = {
                "id": f"auto_{i}",
                "actor": "auto",
                "detector": "sam2_auto",
                "label": "",                               # extent, not meaning — named later
                "category": "object",
                "confidence": round(score, 3),
                "description": f"segment · {int(score * 100)}% quality",
                "mask_rle": rle,                           # authoritative — before canonicalize
            }
            mask_geometry.canonicalize_geometry(region, provenance={
                "adapter": "sam21_hiera_tiny", "model": MODEL_TAG, "checkpoint": _SAM2_CKPT,
                "device": _device(), "method": "sam2-auto",
                "preprocessing_version": PREPROCESSING_VERSION,
                "points_per_side": points_per_side, "latency_ms": latency_ms,
                "confidence": round(score, 3),
            })
            regions.append(region)

        regions.sort(key=lambda r: mask_geometry.rle_area(r["mask_rle"]), reverse=True)
        return regions[:max_regions]
    except Exception as e:  # pragma: no cover - depends on weights/hardware
        print(f"❌ SAM2-auto error: {e}")
        return None
    finally:
        unload()                                            # always return the GPU slot
