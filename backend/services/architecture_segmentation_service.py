"""
Architecture surface segmentation (VISION-C · C2) — SegFormer-B0 fine-tuned on ADE20K.

Turns an architectural image's semantic map into SEPARATE canonical mask candidates —
wall, floor, ceiling, window, door, building, column, stairs and other scene surfaces —
each an authoritative `mask_rle` (via `mask_geometry`) with class/confidence/provenance.
The semantic label is metadata only: it NEVER clips or moves geometry; the mask is the
evidence. SAM can refine any selected architectural mask afterwards (the profile's second
pass).

Modeled on `fashion_segmentation_service` (semantic map → connected components → instance
masks), but it emits `mask_rle` directly and keeps the ADE scene-surface vocabulary. Heavy
deps are lazy-imported and the model is cached; if unavailable, `segment_image_bytes`
returns None and the caller degrades. `nvidia/segformer-b0-finetuned-ade-512-512` runs in
~0.5s on CPU (measured), so no GPU is required for C2.
"""
import io
from typing import List, Optional

from backend.services import mask_geometry

_MODEL_NAME = "nvidia/segformer-b0-finetuned-ade-512-512"
DETECTOR = "segformer_ade"
_model = None
_processor = None
_load_failed = False

_MAX_REGIONS = 16
_MIN_AREA_FRAC = 0.01          # a scene surface below 1% of the frame is noise

# ADE20K label NAMES that are architectural, → Semant's coarse category. Matching by name
# (not index) keeps it robust to id ordering. `part` is the finer ADE label.
_SURFACE = {"wall", "floor", "flooring", "ceiling", "road", "route", "sidewalk", "pavement",
            "field", "path", "runway", "grass"}
_OPENING = {"windowpane", "window", "door", "double door", "screen door", "screen"}
_STRUCTURE = {"building", "edifice", "house", "skyscraper", "column", "pillar", "stairs",
              "steps", "stairway", "staircase", "step", "railing", "rail", "bannister",
              "balustrade", "fence", "fencing", "bridge", "span", "tower", "awning",
              "sunshade", "hovel", "hut", "hutch", "shack", "shanty", "arcade machine"}
_ARCH_LABELS = _SURFACE | _OPENING | _STRUCTURE


def _category_for(label: str) -> Optional[str]:
    """First ADE synonym of the label that we recognise → coarse category, else None."""
    parts = [p.strip().lower() for p in label.split(",")]
    for p in parts:
        if p in _OPENING:
            return "opening"
        if p in _SURFACE:
            return "surface"
        if p in _STRUCTURE:
            return "structure"
    return None


# friendlier canonical names for a few ADE primaries (the UI/catalog label).
_CANONICAL = {"windowpane": "window", "flooring": "floor", "edifice": "building",
              "pillar": "column", "stairway": "stairs", "staircase": "stairs"}


def _primary_name(label: str) -> str:
    primary = label.split(",")[0].strip().lower()
    return _CANONICAL.get(primary, primary)


def is_available() -> bool:
    if _load_failed:
        return False
    try:
        import torch        # noqa: F401
        import transformers  # noqa: F401
        import cv2           # noqa: F401
        import numpy         # noqa: F401
        return True
    except Exception:
        return False


def _load():
    global _model, _processor, _load_failed
    if _model is not None and _processor is not None:
        return _model, _processor
    if _load_failed:
        return None, None
    try:
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
        _processor = SegformerImageProcessor.from_pretrained(_MODEL_NAME)
        _model = SegformerForSemanticSegmentation.from_pretrained(_MODEL_NAME)
        _model.eval()
        return _model, _processor
    except Exception as e:
        print(f"⚠️ SegFormer-ADE unavailable ({e}); architecture pass skipped.")
        _load_failed = True
        return None, None


def _predict(img):
    """Per-pixel ADE class map at full resolution + softmax confidence."""
    import torch
    model, processor = _load()
    if model is None:
        return None, None, None
    inputs = processor(images=img, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits            # (1, C, h/4, w/4)
    up = torch.nn.functional.interpolate(logits, size=img.size[::-1], mode="bilinear",
                                         align_corners=False)
    probs = up.softmax(dim=1)[0]                    # (C, H, W)
    pred = probs.argmax(dim=0).numpy()
    return pred, probs.numpy(), model.config.id2label


def _regions_from_semantic(pred, probs, id2label, width: int, height: int) -> List[dict]:
    """Semantic ADE map → separate architectural instance masks (connected components).
    Each surface/opening/structure blob is its own candidate; labels never touch geometry."""
    import cv2
    import numpy as np

    frame_area = float(width * height)
    min_area = _MIN_AREA_FRAC * frame_area
    regions: List[dict] = []

    present = [int(c) for c in np.unique(pred)]
    for class_id in present:
        label = id2label.get(class_id, str(class_id))
        category = _category_for(label)
        if category is None:                       # not an architectural class
            continue
        mask = (pred == class_id).astype("uint8")
        count, comps = cv2.connectedComponents(mask)
        for comp_id in range(1, count):
            blob = (comps == comp_id).astype("uint8")
            if int(blob.sum()) < min_area:
                continue
            confidence = float(probs[class_id][blob.astype(bool)].mean())
            region = {
                "id": f"arch_{len(regions)}",
                "actor": "auto",
                "detector": DETECTOR,
                "label": _primary_name(label),
                "category": category,
                "part": _primary_name(label),
                "attributes": [],
                "confidence": round(confidence, 3),
                "description": f"{_primary_name(label)} · {int(confidence * 100)}% (ADE)",
                "mask_rle": mask_geometry.rle_encode_mask(blob),   # authoritative
            }
            mask_geometry.canonicalize_geometry(region, provenance={
                "adapter": "segformer_b0_ade", "model": _MODEL_NAME, "device": "cpu",
                "preprocessing_version": "segformer-ade", "method": "segformer-ade",
                "ade_class": label, "confidence": round(confidence, 3),
            })
            regions.append(region)

    regions.sort(key=lambda r: mask_geometry.rle_area(r["mask_rle"]), reverse=True)
    return regions[:_MAX_REGIONS]


def segment_image_bytes(data: bytes) -> Optional[List[dict]]:
    """Architectural surfaces of an image as authoritative-mask regions. `[]` = looked,
    found none; `None` = could not look (deps/model unavailable) → caller degrades."""
    if not is_available():
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("RGB")
        pred, probs, id2label = _predict(img)
        if pred is None:
            return None
        width, height = img.size
        return _regions_from_semantic(pred, probs, id2label, width, height)
    except Exception as e:
        print(f"❌ Architecture segmentation error: {e}")
        return None
