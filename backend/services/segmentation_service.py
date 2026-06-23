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
    Segment an image (raw bytes) into labeled regions with polygon masks.
    Returns a list of region dicts, or None if segmentation is unavailable / errored.
    Each region: {id, label, category, box{x,y,w,h}, polygon[[x,y]...], confidence, description}
    (all coordinates normalized 0..1, top-left origin).
    """
    try:
        from PIL import Image
        model = _load_model()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        # CPU is plenty fast for the nano model and avoids occasional MPS instabilities.
        results = model.predict(img, conf=conf, verbose=False, device="cpu", retina_masks=True)
        if not results:
            return []
        r = results[0]
        names = r.names if isinstance(r.names, dict) else {i: n for i, n in enumerate(r.names)}
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            return []
        polys = r.masks.xyn if r.masks is not None else []

        regions = []
        for i in range(len(boxes)):
            cls = int(boxes.cls[i].item())
            conf_i = float(boxes.conf[i].item())
            label = str(names.get(cls, cls))
            x1, y1, x2, y2 = (float(v) for v in boxes.xyxyn[i].tolist())
            box = {
                "x": round(max(0.0, x1), 4), "y": round(max(0.0, y1), 4),
                "w": round(max(0.0, min(1.0, x2) - max(0.0, x1)), 4),
                "h": round(max(0.0, min(1.0, y2) - max(0.0, y1)), 4),
            }
            polygon = []
            if i < len(polys) and polys[i] is not None and len(polys[i]):
                pts = [[round(float(px), 4), round(float(py), 4)] for px, py in polys[i]]
                polygon = _simplify(pts)
            regions.append({
                "id": f"seg_{i}",
                "label": label,
                "category": _category(label),
                "box": box,
                "polygon": polygon,
                "confidence": round(conf_i, 3),
                "description": f"{label} · {int(conf_i * 100)}% match",
            })

        # Largest / most prominent first, capped.
        regions.sort(key=lambda rg: rg["box"]["w"] * rg["box"]["h"], reverse=True)
        return regions[:max_regions]
    except Exception as e:
        print(f"❌ Segmentation error: {e}")
        return None
