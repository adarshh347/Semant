"""
FashionCLIP inference (Darshan Track B · Phase 1) — the taste-vectorizer + zero-shot
labeler + domain router.

FashionCLIP (`patrickjohncyh/fashion-clip`, a CLIP ViT-B/32 fine-tuned on fashion)
does NOT locate anything — geometry stays YOLO/vision's job (Track A/B). This service
only:
  1. VECTORIZES a region crop (or whole image) → a normalized embedding (the taste
     vector) stored out-of-row in the region_embeddings sidecar.
  2. LABELS a fashion region zero-shot → a first-cut `part` + `attributes[]`.
  3. ROUTES an image's domain (fashion vs not) — a cheap first cut that feeds Track C.

Heavy deps (torch / transformers) are imported LAZILY and the model is loaded once and
cached — exactly like `segmentation_service.py`. If the deps/model aren't available
(e.g. a slim deploy), every entry point degrades gracefully (returns None / [] / a
low-confidence "unknown" domain) so the backend never hard-depends on FashionCLIP.
CPU is fine — no GPU required in Phase 1.
"""

import io
from typing import List, Optional, Tuple

_MODEL_NAME = "patrickjohncyh/fashion-clip"
_model = None
_processor = None
_load_failed = False

# --- Zero-shot vocabularies (first cut; Fashionpedia's full 294 lands in Phase 2) ---
# Coarse apparel parts — the single best match becomes Region.part.
FASHION_PARTS = [
    "neckline", "collar", "lapel", "sleeve", "cuff", "hem", "waistband",
    "pocket", "button placket", "bodice", "skirt", "trousers", "shoulder",
    "drape or fold", "yoke", "hood", "belt", "shoe", "bag", "jewellery",
]
# Fine attributes — every match above the gate joins Region.attributes[].
FASHION_ATTRIBUTES = [
    "fitted silhouette", "loose silhouette", "flowing", "structured",
    "sheer", "matte", "glossy", "textured", "pleated", "ruffled",
    "solid colour", "striped", "floral print", "patterned",
    "embroidered", "asymmetric", "draped",
]
# Domain router prompts — the winner's family is the domain tag.
_DOMAIN_PROMPTS = {
    "fashion": "a fashion or clothing outfit photo",
    "architecture": "an interior design or architecture photo",
    "photography": "a landscape, nature, or portrait photograph",
    "food": "a food or drink photo",
    "product": "a product or object photo",
}


def is_available() -> bool:
    """True if torch + transformers import cleanly (model may still lazy-load later)."""
    if _load_failed:
        return False
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def _load():
    """Load + cache the FashionCLIP model & processor once. Returns (model, processor)
    or (None, None) if unavailable."""
    global _model, _processor, _load_failed
    if _model is not None and _processor is not None:
        return _model, _processor
    if _load_failed:
        return None, None
    try:
        from transformers import CLIPModel, CLIPProcessor
        _model = CLIPModel.from_pretrained(_MODEL_NAME)
        _model.eval()
        _processor = CLIPProcessor.from_pretrained(_MODEL_NAME)
        return _model, _processor
    except Exception as e:
        print(f"⚠️ FashionCLIP unavailable ({e}); embeddings/labels skipped.")
        _load_failed = True
        return None, None


def _open_image(data: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(data)).convert("RGB")


def _crop_norm(img, box: Optional[dict]):
    """Crop a PIL image to a normalized {x,y,w,h} box (top-left origin). Returns the
    whole image if the box is missing/degenerate."""
    if not box:
        return img
    W, H = img.size
    try:
        x, y = float(box.get("x", 0)), float(box.get("y", 0))
        w, h = float(box.get("w", 1)), float(box.get("h", 1))
    except (TypeError, ValueError):
        return img
    left, top = max(0, int(x * W)), max(0, int(y * H))
    right, bottom = min(W, int((x + w) * W)), min(H, int((y + h) * H))
    if right - left < 4 or bottom - top < 4:      # too small to be meaningful
        return img
    return img.crop((left, top, right, bottom))


# ---------------------------------------------------------------------------
# Core inference
# ---------------------------------------------------------------------------
def embed_image(img) -> Optional[List[float]]:
    """L2-normalized FashionCLIP image embedding (projected into the shared image/text
    space) as a plain float list, or None. Uses the canonical vision_model →
    visual_projection path so it is robust across transformers versions (5.x returns an
    output object from get_image_features rather than a bare tensor)."""
    model, processor = _load()
    if model is None:
        return None
    try:
        import torch
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            pooled = model.vision_model(pixel_values=inputs["pixel_values"]).pooler_output
            embeds = model.visual_projection(pooled)          # → shared CLIP space
            embeds = embeds / embeds.norm(dim=-1, keepdim=True)  # L2 normalize
        return embeds[0].cpu().tolist()
    except Exception as e:
        print(f"❌ FashionCLIP embed error: {e}")
        return None


def zero_shot(img, labels: List[str]) -> List[Tuple[str, float]]:
    """Softmax image↔text match over `labels`. Returns (label, prob) sorted desc, or []."""
    model, processor = _load()
    if model is None or not labels:
        return []
    try:
        import torch
        inputs = processor(text=labels, images=img, return_tensors="pt", padding=True)
        with torch.no_grad():
            out = model(**inputs)
        probs = out.logits_per_image.softmax(dim=1)[0].cpu().tolist()
        return sorted(zip(labels, probs), key=lambda t: t[1], reverse=True)
    except Exception as e:
        print(f"❌ FashionCLIP zero-shot error: {e}")
        return []


# ---------------------------------------------------------------------------
# Higher-level helpers used by the enrichment endpoint
# ---------------------------------------------------------------------------
def label_region(img, box: Optional[dict], *, part_gate: float = 0.18,
                 attr_gate: float = 0.10) -> dict:
    """Zero-shot a first-cut {part, attributes[]} for a fashion region crop.
    Confidence-gated: a weak best-part is left None; only attributes above the gate
    are kept. Returns {} when FashionCLIP is unavailable."""
    if not is_available():
        return {}
    crop = _crop_norm(img, box)
    out = {}
    parts = zero_shot(crop, FASHION_PARTS)
    if parts and parts[0][1] >= part_gate:
        out["part"] = parts[0][0]
    attrs = zero_shot(crop, FASHION_ATTRIBUTES)
    kept = [lab for lab, p in attrs if p >= attr_gate]
    if kept:
        out["attributes"] = kept[:5]
    return out


def classify_domain(img, *, gate: float = 0.35) -> dict:
    """Route the image's domain (first cut, feeds Track C). Returns
    {label, score, is_fashion}. 'unknown' if FashionCLIP is unavailable or below gate."""
    if not is_available():
        return {"label": "unknown", "score": 0.0, "is_fashion": False}
    ranked = zero_shot(img, list(_DOMAIN_PROMPTS.values()))
    if not ranked:
        return {"label": "unknown", "score": 0.0, "is_fashion": False}
    prompt_to_key = {v: k for k, v in _DOMAIN_PROMPTS.items()}
    top_prompt, top_score = ranked[0]
    key = prompt_to_key.get(top_prompt, "unknown")
    label = key if top_score >= gate else "unknown"
    return {"label": label, "score": round(float(top_score), 4),
            "is_fashion": label == "fashion"}


def cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity of two already-L2-normalized vectors (dot product)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))
