"""
Local image segmentation (Ultralytics YOLO11-seg) — runs on-device (Apple M-series
CPU/MPS), no API key, no cost. Produces labeled instance masks: each region has a
class label, a normalized bounding box, and a normalized polygon outline (the actual
segment), so the UI can draw true clickable shapes rather than rough rectangles.

Heavy deps (torch/ultralytics) are imported lazily and the model is loaded once and
cached, so backend startup stays light. If the deps/model aren't available (e.g. the
Render deploy), `segment_image_bytes` returns None and the caller falls back to the
vision-LLM detector.
"""

import io
from typing import List, Optional

_model = None
_MODEL_NAME = "yolo11n-seg.pt"   # small, fast; auto-downloads (~6MB) on first use
_MAX_POLY_POINTS = 48            # downsample polygons to keep payloads small


def is_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False


def _load_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(_MODEL_NAME)
    return _model


def _category(name: str) -> str:
    """Map a COCO class to our coarse category vocabulary."""
    name = (name or "").lower()
    if name == "person":
        return "figure"
    if name in {"tie", "handbag", "backpack", "umbrella", "suitcase"}:
        return "garment"
    return "object"


def _simplify(points: list, max_pts: int = _MAX_POLY_POINTS) -> list:
    n = len(points)
    if n <= max_pts:
        return points
    step = n / max_pts
    return [points[int(i * step)] for i in range(max_pts)]


def segment_image_bytes(data: bytes, conf: float = 0.30, max_regions: int = 12) -> Optional[List[dict]]:
    """
    Segment an image (raw bytes) into labeled regions whose AUTHORITATIVE geometry is the
    native instance mask (VISION-BUILD-001 B2): each region carries `mask_rle` (COCO RLE)
    plus the derived `polygons`/legacy `polygon`/`box` from `mask_geometry`. Returns a
    list of region dicts, `[]` when nothing is found, or None if unavailable/errored.
    """
    try:
        from PIL import Image
        from backend.services.vision_orchestrator.adapters import masks_to_regions
        model = _load_model()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        # CPU is plenty fast for the nano model and avoids occasional MPS instabilities.
        results = model.predict(img, conf=conf, verbose=False, device="cpu", retina_masks=True)
        if not results:
            return []
        r = results[0]
        boxes = r.boxes
        if boxes is None or len(boxes) == 0 or r.masks is None:
            return []
        names = r.names if isinstance(r.names, dict) else {i: n for i, n in enumerate(r.names)}
        # Native per-instance masks (retina = full image resolution) are the identity;
        # we never reduce them to a bbox before persistence.
        md = (r.masks.data.detach().to("cpu").numpy() > 0.5).astype("uint8")
        cls = boxes.cls.detach().to("cpu").tolist()
        confs = boxes.conf.detach().to("cpu").tolist()
        return masks_to_regions([md[i] for i in range(md.shape[0])], cls, confs, names,
                                detector="yolo", model_id=_MODEL_NAME, device="cpu",
                                preprocessing_version="ultralytics-retina",
                                max_regions=max_regions)
    except Exception as e:
        print(f"❌ Segmentation error: {e}")
        return None
