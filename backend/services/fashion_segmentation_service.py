"""
Fashion garment segmentation (Darshan Track B · Phase 2a) — the domain spine, on CPU.

YOLO gives us COCO: one "person" box and, if we're lucky, a "handbag". That is not an
anatomy of a garment. This service replaces it, for fashion images, with real per-pixel
clothing regions — upper-clothes, skirt, pants, dress, belt, shoes, bag, scarf — each
with a true polygon outline rather than a rectangle around a whole human.

**The model:** `mattmdjaga/segformer_b2_clothes` — SegFormer-B2 (27.4M params) fine-tuned
on the ATR human-parsing dataset, 18 classes, mIoU ≈ 0.69. It is *semantic* segmentation
(a class per pixel), so we recover instances by connected components. Chosen because it
runs in ~2s on CPU with no GPU at all, which is the whole constraint of Phase 2a.

**What this is NOT.** This is not Fashionpedia. ATR has no 294-attribute vocabulary and
no fine apparel parts (necklines, cuffs, plackets). `detector="segformer_clothes"` says
so honestly, leaving `detector="fashionpedia"` for Phase 2b's Attribute-Mask-RCNN /
Fashionformer on the M4 or a serverless GPU. `attributes[]` stays empty here — the model
does not produce them, and inventing them would be worse than leaving them absent.

Heavy deps (torch / transformers / opencv) are imported LAZILY and the model is loaded
once and cached — exactly like `segmentation_service.py`. If the deps or the weights
aren't available (a slim deploy), `segment_image_bytes` returns None and the caller
falls back to YOLO, then to the vision-LLM. The backend never hard-depends on this.
"""

import io

from backend.services import mask_geometry
from typing import List, Optional

_MODEL_NAME = "mattmdjaga/segformer_b2_clothes"
_model = None
_processor = None
_load_failed = False

# Provenance. Deliberately NOT "fashionpedia": that value is reserved for the model that
# actually is Fashionpedia (Phase 2b), so precedence and dedup can tell the two apart
# without a migration.
DETECTOR = "segformer_clothes"

_MAX_POLY_POINTS = 48        # match segmentation_service — keeps post payloads small
_MAX_REGIONS = 14

# Minimum blob area, as a fraction of the frame, for a region to be kept. Garments and
# accessories get a tighter floor than body parts: a belt or a shoe is a small, genuinely
# interesting region (a belt is ~0.3% of a full-length portrait), whereas a sliver of arm
# that size is a segmentation artefact. One global floor loses the belt or keeps the noise.
_MIN_AREA_FRAC_GARMENT = 0.0015
_MIN_AREA_FRAC_BODY = 0.004

# Semantic segmentation labels pixels, not objects, so one garment occluded by an arm
# comes back as several connected components. A sliver of dress peeking past an elbow is
# not a second dress — emitting it would double-count the garment in the frequency
# catalog and put two identical rows in the parts panel. So per class we keep the
# dominant component, plus any component that is a real rival to it: at least this
# fraction of its area, and not sitting mostly inside its box (which would make it a
# fragment rather than a separate piece).
_FRAGMENT_KEEP_RATIO = 0.35
_FRAGMENT_CONTAINMENT = 0.5

# ATR's 18 classes → the Track A taxonomy. `category` is the coarse, catalog-critical
# vocabulary (aggregate_categories buckets on it, so these values must already exist in
# it); `part` is the finer slot. Background is dropped.
#
# Body parts are kept, not discarded: they are real anatomy with real masks, and the
# vision-LLM currently only *approximates* them. Their category is "skin"/"hair", so the
# catalog and the FashionCLIP garment gate treat them exactly as before.
_CLASS_MAP = {
    1:  ("hat",         "accessory",      "hat"),
    2:  ("hair",        "hair",           None),
    3:  ("sunglasses",  "accessory",      "sunglasses"),
    4:  ("top",         "garment",        "top"),
    5:  ("skirt",       "garment",        "skirt"),
    6:  ("trousers",    "garment",        "trousers"),
    7:  ("dress",       "garment",        "dress"),
    8:  ("belt",        "accessory",      "belt"),
    9:  ("left shoe",   "accessory",      "shoe"),
    10: ("right shoe",  "accessory",      "shoe"),
    11: ("face",        "skin",           "face"),
    12: ("left leg",    "skin",           None),
    13: ("right leg",   "skin",           None),
    14: ("left arm",    "skin",           None),
    15: ("right arm",   "skin",           None),
    16: ("bag",         "accessory",      "bag"),
    17: ("scarf",       "accessory",      "scarf"),
}

# The classes that make this model worth running at all. Used by the caller's precedence
# rule: a YOLO "person"/"handbag" that overlaps one of these is superseded.
GARMENT_CATEGORIES = {"garment", "accessory"}


def is_available() -> bool:
    """True if the heavy deps import cleanly. The weights may still fail to load later,
    which `_load` handles by degrading rather than raising."""
    if _load_failed:
        return False
    try:
        import torch        # noqa: F401
        import transformers # noqa: F401
        import cv2          # noqa: F401
        import numpy        # noqa: F401
        return True
    except Exception:
        return False


def _load():
    """Load + cache the segmenter once. Returns (model, processor) or (None, None)."""
    global _model, _processor, _load_failed
    if _model is not None and _processor is not None:
        return _model, _processor
    if _load_failed:
        return None, None
    try:
        from transformers import AutoModelForSemanticSegmentation, SegformerImageProcessor
        _processor = SegformerImageProcessor.from_pretrained(_MODEL_NAME)
        _model = AutoModelForSemanticSegmentation.from_pretrained(_MODEL_NAME)
        _model.eval()
        return _model, _processor
    except Exception as e:
        print(f"⚠️ Fashion segmenter unavailable ({e}); falling back to YOLO.")
        _load_failed = True
        return None, None


def _simplify(points: list, max_pts: int = _MAX_POLY_POINTS) -> list:
    n = len(points)
    if n <= max_pts:
        return points
    step = n / max_pts
    return [points[int(i * step)] for i in range(max_pts)]


def _predict(img):
    """Per-pixel class map at full image resolution, plus the softmax confidence map."""
    import torch
    model, processor = _load()
    if model is None:
        return None, None
    inputs = processor(images=img, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits          # (1, C, h/4, w/4)
    # SegFormer predicts at a quarter scale; upsample to the image so the polygons we
    # trace are in true pixel space and normalize exactly.
    upsampled = torch.nn.functional.interpolate(
        logits, size=img.size[::-1], mode="bilinear", align_corners=False
    )
    probs = upsampled.softmax(dim=1)[0]           # (C, H, W)
    pred = probs.argmax(dim=0).numpy()
    return pred, probs.numpy()


def _regions_from_mask(pred, probs, width: int, height: int) -> List[dict]:
    """Semantic mask → instance regions.

    The model labels pixels, not objects, so a class can appear as several disjoint
    blobs (two sleeves of a jacket, a skirt split by an arm). Connected components
    recovers the instances; contours give the polygon the UI actually draws.
    """
    import cv2
    import numpy as np

    frame_area = float(width * height)
    regions: List[dict] = []

    for class_id, (label, category, part) in _CLASS_MAP.items():
        mask = (pred == class_id).astype("uint8")
        if not mask.any():
            continue

        floor = (_MIN_AREA_FRAC_GARMENT if category in GARMENT_CATEGORIES
                 else _MIN_AREA_FRAC_BODY)
        min_area = floor * frame_area

        count, comps = cv2.connectedComponents(mask)
        candidates = []
        for comp_id in range(1, count):
            blob = (comps == comp_id).astype("uint8")
            area = int(blob.sum())
            if area < min_area:
                continue

            contours, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            contour = max(contours, key=cv2.contourArea)
            # Douglas-Peucker before downsampling: keeps the silhouette's corners rather
            # than dropping every k-th point of a dense contour.
            eps = 0.002 * cv2.arcLength(contour, True)
            contour = cv2.approxPolyDP(contour, eps, True)
            if len(contour) < 3:
                continue

            pts = [[round(float(p[0][0]) / width, 4), round(float(p[0][1]) / height, 4)]
                   for p in contour]
            x, y, w, h = cv2.boundingRect(blob)
            # Mean probability of the winning class over the blob — a real confidence,
            # not a constant. Low-confidence blobs are still returned; the caller and the
            # curator decide, and Track B's plan explicitly budgets for LLM fallback.
            confidence = float(probs[class_id][blob.astype(bool)].mean())

            candidates.append({
                "area": area,
                "box": {
                    "x": round(x / width, 4), "y": round(y / height, 4),
                    "w": round(w / width, 4), "h": round(h / height, 4),
                },
                "polygon": _simplify(pts),
                "blob": blob,                          # the exact instance mask (VISION-C · C3)
                "confidence": confidence,
            })

        for cand in _keep_instances(candidates):
            region = {
                "id": f"fseg_{len(regions)}",
                "actor": "auto",
                "detector": DETECTOR,
                "label": label,
                "category": category,
                "part": part,                          # garment part, kept SEPARATE from category
                # attributes[] intentionally empty: ATR has no attribute vocabulary.
                # Phase 2b's Fashionpedia fills this; FashionCLIP's zero-shot pass
                # (Track B Phase 1) still supplies a first cut in the meantime.
                "attributes": [],
                "confidence": round(cand["confidence"], 3),
                "description": f"{label} · {int(cand['confidence'] * 100)}% match",
                # authoritative garment mask (C3) — derived polygons/box come from it.
                "mask_rle": mask_geometry.rle_encode_mask(cand["blob"]),
                "area_frac": round(cand["area"] / frame_area, 5),  # transient; caller drops it
            }
            mask_geometry.canonicalize_geometry(region, provenance={
                "adapter": "segformer_clothes", "model": _MODEL_NAME, "device": "cpu",
                "preprocessing_version": "segformer-clothes", "method": "segformer-clothes",
                "part": part, "confidence": round(cand["confidence"], 3),
            })
            regions.append(region)

    regions.sort(key=lambda r: r["area_frac"], reverse=True)
    return regions[:_MAX_REGIONS]


def _keep_instances(candidates: List[dict]) -> List[dict]:
    """Collapse a class's connected components down to real instances.

    The dominant component always survives. A smaller one survives only if it is a
    genuine rival — a substantial share of the dominant's area, and not mostly inside
    its box. That keeps a skirt truly split in two, and discards the sliver of dress
    visible past an elbow.
    """
    if len(candidates) <= 1:
        return candidates
    candidates.sort(key=lambda c: c["area"], reverse=True)
    dominant = candidates[0]
    kept = [dominant]
    for cand in candidates[1:]:
        big_enough = cand["area"] >= _FRAGMENT_KEEP_RATIO * dominant["area"]
        detached = _containment(cand["box"], dominant["box"]) < _FRAGMENT_CONTAINMENT
        if big_enough and detached:
            kept.append(cand)
    return kept


def segment_image_bytes(data: bytes) -> Optional[List[dict]]:
    """
    Segment a fashion image into garment/body regions with true polygon masks.

    Returns a list of region dicts (coordinates normalized 0..1, top-left origin), `[]`
    when the model found nothing worth keeping, or **None** when the segmenter is
    unavailable or errored — which is the caller's signal to fall back to YOLO.
    That three-way return is load-bearing: `[]` means "looked, found nothing", `None`
    means "could not look".
    """
    if not is_available():
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("RGB")
        pred, probs = _predict(img)
        if pred is None:
            return None
        width, height = img.size
        regions = _regions_from_mask(pred, probs, width, height)
        for r in regions:
            r.pop("area_frac", None)
        return regions
    except Exception as e:
        print(f"❌ Fashion segmentation error: {e}")
        return None


# ---------------------------------------------------------------------------
# Precedence / dedup (Track B lock: the garment segmenter outranks YOLO)
# ---------------------------------------------------------------------------
def _box_iou(a: dict, b: dict) -> float:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def _containment(inner: dict, outer: dict) -> float:
    """How much of `inner` lies inside `outer` (0..1)."""
    ix2, iy2 = inner["x"] + inner["w"], inner["y"] + inner["h"]
    ox2, oy2 = outer["x"] + outer["w"], outer["y"] + outer["h"]
    ix = max(0.0, min(ix2, ox2) - max(inner["x"], outer["x"]))
    iy = max(0.0, min(iy2, oy2) - max(inner["y"], outer["y"]))
    inter = ix * iy
    area = inner["w"] * inner["h"]
    return inter / area if area > 0 else 0.0


# A YOLO region in one of these categories is the kind of thing the garment segmenter
# is strictly better at. A "couch" or a "potted plant" is not, and survives.
_SUPERSEDABLE = {"figure", "garment"}


def merge_with_precedence(primary: List[dict], secondary: List[dict],
                          iou_threshold: float = 0.5,
                          containment_threshold: float = 0.6) -> List[dict]:
    """
    Keep every garment-segmenter region; drop the YOLO regions it supersedes.

    Two ways a YOLO region is superseded, because IoU alone is not enough here:
      · it overlaps a garment region substantially (IoU ≥ threshold) — the duplicate
        "handbag" vs "bag" case;
      · a garment region sits mostly *inside* it (containment ≥ threshold) — the
        "person" box that contains the dress it can't name. IoU(person, dress) is low,
        so an IoU-only rule would keep both and leave the curator two overlapping,
        differently-named anchors for the same thing.

    Everything YOLO saw that the garment model cannot see (furniture, objects,
    background) survives untouched. `detector` records who produced what.
    """
    kept: List[dict] = list(primary)
    if not primary:
        return list(secondary)

    for region in secondary:
        if region.get("category") not in _SUPERSEDABLE:
            kept.append(region)
            continue
        box = region.get("box") or {}
        superseded = any(
            _box_iou(box, p["box"]) >= iou_threshold
            or _containment(p["box"], box) >= containment_threshold
            for p in primary
        )
        if not superseded:
            kept.append(region)

    kept.sort(key=lambda r: r["box"]["w"] * r["box"]["h"], reverse=True)
    return kept
