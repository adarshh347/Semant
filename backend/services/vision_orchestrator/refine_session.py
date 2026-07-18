"""
VISION-BUILD-001 B4 — interactive refine session.

A single, lazily-loaded SAM 2.1 predictor that CACHES the current image's embedding, so
the first prompt on an image pays the ~0.5 s encode and every subsequent click/box is the
interactive 10–170 ms path (the whole point of a usable refine loop). One refine at a
time (an asyncio.Lock = the single heavy-GPU-job rule); blocking inference runs in a
worker thread so the event loop stays responsive. Prompts arrive in NORMALIZED [0,1]
image coords (the stage-geometry contract) and are converted to pixels here.

Preview never persists; confirmation is the caller's job (the endpoint), keeping this
purely a proposal engine. Masks are returned as canonical RLE via `mask_geometry`.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
from typing import Any, Dict, List, Optional

from .adapters import _SAM2_CFG, _SAM2_CKPT, refined_mask_to_region


class RefineSession:
    def __init__(self) -> None:
        self._predictor = None
        self._dev = "cpu"
        self._cur_key: Optional[str] = None
        self._lock = asyncio.Lock()

    def available(self) -> bool:
        try:
            import sam2  # noqa: F401
            import torch  # noqa: F401
            import os
            return os.path.exists(_SAM2_CKPT)
        except Exception:
            return False

    # ── blocking worker (runs in a thread) ───────────────────────────────────
    def _ensure_loaded(self) -> None:
        if self._predictor is not None:
            return
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        self._dev = "cuda" if torch.cuda.is_available() else "cpu"
        self._predictor = SAM2ImagePredictor(build_sam2(_SAM2_CFG, _SAM2_CKPT, device=self._dev))

    def _run(self, image_bytes: bytes, prompt: Dict[str, Any],
             base_id: Optional[str], base_rev: int) -> Dict[str, Any]:
        import numpy as np
        from PIL import Image
        self._ensure_loaded()
        key = hashlib.sha256(image_bytes).hexdigest()
        img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        H, W = img.shape[:2]
        if key != self._cur_key:                       # encode once per image (cached)
            self._predictor.set_image(img)
            self._cur_key = key

        kwargs: Dict[str, Any] = {"multimask_output": True}
        kind = "point"
        pts = prompt.get("points")
        box = prompt.get("box")
        if pts:
            kwargs["point_coords"] = np.array([[x * W, y * H] for x, y in pts], dtype=float)
            kwargs["point_labels"] = np.array(prompt.get("labels") or [1] * len(pts))
        if box is not None:
            kwargs["box"] = np.array([box[0] * W, box[1] * H, box[2] * W, box[3] * H], dtype=float)
            kwargs["multimask_output"] = False
            kind = "box"
        masks, scores, _ = self._predictor.predict(**kwargs)
        best = int(np.argmax(scores))
        return refined_mask_to_region((masks[best] > 0).astype("uint8"),
                                      base_id=base_id, base_geometry_rev=base_rev,
                                      score=float(scores[best]), prompt=kind, device=self._dev)

    # ── async API ─────────────────────────────────────────────────────────────
    async def preview(self, image_bytes: bytes, prompt: Dict[str, Any],
                      base_id: Optional[str] = None, base_rev: int = 0) -> Dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(self._run, image_bytes, prompt, base_id, base_rev)

    async def unload(self) -> None:
        async with self._lock:
            self._predictor = None
            self._cur_key = None
            try:
                import torch
                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass


# module singleton — lazily loads SAM2 only on the first refine request.
refine_session = RefineSession()
