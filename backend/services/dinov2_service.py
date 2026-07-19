"""
VISION-E · E2 — DINOv2 ViT-S/14 shared visual representation.

DINOv2 (`facebook/dinov2-small`, Apache-2.0; ViT-S/14, hidden 384) is the reusable visual
backbone. The rule that matters: the whole image is encoded ONCE per (source, preprocessing)
into a patch-token grid, and Region vectors are produced by POOLING that shared grid under each
mask — the full image is never re-encoded per Region. When a specific framing is needed (the
E1 identity/context crops), a crop is encoded on its own and the route is recorded, so every
vector says how it was made.

Measured on the box's GTX 1650 (Turing, sm_75): FP32 warm ≈14 ms/image, peak ≈99 MiB VRAM;
FP16 is slower (~57 ms) with no VRAM headroom benefit worth taking and CLS agreement 1.00000,
so this runs FP32. Preprocessing is fixed as `dino-v1`: RGB → resize 224×224 (no center-crop,
so the 16×16 patch grid maps linearly to normalized image coords) → model normalization.

Vectors are L2-normalized. The encoder is a lazy GPU singleton with an explicit `unload()`.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from backend.services import mask_geometry as mg

CHECKPOINT = "facebook/dinov2-small"     # DINOv2 ViT-S/14, Apache-2.0
MODEL_TAG = "dinov2_vits14"
PREPROCESSING_VERSION = "dino-v1"        # resize-224-square, no center-crop
DIM = 384
_INPUT = 224

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
        from transformers import AutoImageProcessor, AutoModel
        proc = AutoImageProcessor.from_pretrained(CHECKPOINT)
        model = AutoModel.from_pretrained(CHECKPOINT).to(_device()).to(torch.float32).eval()
        _processor, _model = proc, model
    except Exception as e:  # pragma: no cover - depends on weights/hardware
        _load_failed = True
        print(f"⚠️ DINOv2 load failed (non-fatal): {e}")


def unload() -> None:
    """Free the model + GPU memory — called when the GPU slot is handed to another adapter."""
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


def _l2(vec: List[float]) -> List[float]:
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


class Dinov2Encoder:
    """Injectable encoder facade (real DINOv2). Tests pass a fake with the same three methods:
    `encode_image`, `pool_region`, `encode_crop` (+ `available`)."""

    model_tag = MODEL_TAG
    checkpoint = CHECKPOINT
    preprocessing_version = PREPROCESSING_VERSION
    dim = DIM

    def available(self) -> bool:
        return is_available()

    def encode_image(self, image) -> Dict[str, Any]:
        """Encode the WHOLE image once → {cls (normalized), patches (grid×grid×384 raw), grid}.
        This is the shared artifact reused for every Region's mask pooling."""
        import torch
        _load()
        if _model is None:
            raise RuntimeError("DINOv2 unavailable")
        im = image.convert("RGB").resize((_INPUT, _INPUT))
        inp = _processor(images=im, return_tensors="pt", do_resize=False,
                         do_center_crop=False).to(_device())
        with torch.no_grad():
            lhs = _model(**inp).last_hidden_state[0]     # (1 + P, 384)
        cls = lhs[0].float().cpu().tolist()
        patches = lhs[1:].float().cpu()                  # (P, 384)
        grid = int(round(math.sqrt(patches.shape[0])))
        return {"cls": _l2(cls), "patches": patches.reshape(grid, grid, DIM), "grid": grid}

    def pool_region(self, features: Dict[str, Any], mask_rle: dict) -> Optional[List[float]]:
        """Mask-pool the SHARED patch grid: coverage-weighted mean of the patch tokens under the
        mask, L2-normalized. Returns None when the mask covers less than one patch cell (then the
        caller crop-encodes instead) — so a sub-patch sliver never gets a meaningless pooled vector."""
        import numpy as np
        grid = features["grid"]
        patches = features["patches"].numpy().reshape(grid * grid, DIM)
        bits, h, w = mg.rle_decode(mask_rle)
        m = np.frombuffer(bytes(bits), dtype=np.uint8).reshape(h, w)
        # coverage of each grid cell = fraction of mask pixels in that normalized cell
        cov = np.zeros(grid * grid, dtype=np.float64)
        for gy in range(grid):
            y0, y1 = gy * h // grid, max(gy * h // grid + 1, (gy + 1) * h // grid)
            for gx in range(grid):
                x0, x1 = gx * w // grid, max(gx * w // grid + 1, (gx + 1) * w // grid)
                cell = m[y0:y1, x0:x1]
                cov[gy * grid + gx] = cell.mean() if cell.size else 0.0
        total = cov.sum()
        if total <= 1e-9:
            return None
        pooled = (patches * cov[:, None]).sum(axis=0) / total
        return _l2(pooled.tolist())

    def encode_crop(self, image) -> List[float]:
        """Encode a specific crop (E1 identity/context) → its normalized CLS vector."""
        return self.encode_image(image)["cls"]


_encoder: Optional[Dinov2Encoder] = None


def get_encoder() -> Dinov2Encoder:
    global _encoder
    if _encoder is None:
        _encoder = Dinov2Encoder()
    return _encoder
