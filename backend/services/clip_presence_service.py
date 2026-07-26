"""
CIRCUIT-001 P8-C — the CLIP presence gate: a second, independent opinion.

P8-B measured the problem precisely. GroundingDINO has no presence head: asked for something
absent it returns its best guess, confidently, and its score does not separate present from
absent ("a purple bicycle" scored 0.444 on a Pietà, outscoring a real "the drapery" at 0.397).
The only safe response was a high detector threshold (0.5), which bought zero fabrications at
the cost of roughly a third of legitimate queries.

This module buys that recall back. The detector answers *where might it be*; CLIP answers
*is that crop actually the thing you asked for*. Two models disagreeing is the point — a
fabrication survives only if BOTH are wrong in the same direction, which is a far stronger bar
than either alone.

WHY A GENERAL CLIP, not the fashion one already in the roster: the gate judges arbitrary curator
phrases on arbitrary images. `patrickjohncyh/fashion-clip` is tuned on a fashion manifold and
would score "the drapery" on a Pietà against the wrong notion of drapery. `openai/clip-vit-base-
patch32` is MIT, transformers-native, and general.

THE SCORING DECISION. Raw CLIP cosine similarity is not comparable across phrases — "a face"
and "the pedestal" sit at different absolute similarities regardless of presence, so a fixed
cosine cutoff cannot work. Instead the crop is scored CONTRASTIVELY: the phrase competes against
a fixed set of neutral distractor captions, and the gate keeps the softmax probability assigned
to the phrase. That converts "how similar" (uncalibrated) into "did this beat the alternatives"
(comparable), which is the question a presence check is actually asking.

Shape mirrors the other GPU services: lazy singleton, explicit `unload()`, so ModelManager keeps
one heavy model resident at a time. This is the third model in the grounded find_parts chain
(detector → CLIP → SAM2), and they are sequenced, never co-resident.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

CHECKPOINT = "openai/clip-vit-base-patch32"
# WEIGHTS-001 — pinned HF commit, passed to every from_pretrained so the pin is ENFORCED at load.
REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
MODEL_TAG = "clip_vit_b32"
PREPROCESSING_VERSION = "clip-vit-b32-v1"

# The phrase competes against these. They are deliberately bland and mutually unlike: the point
# is to give CLIP somewhere plausible to put its probability mass when the phrase is NOT in the
# crop. Too specific and they would compete with real answers; too few and everything wins.
DISTRACTORS: Sequence[str] = (
    "a photograph of something else",
    "an empty background",
    "a plain surface",
    "an unrelated object",
)

# CALIBRATED on the P8-B phrase set — the same 12 phrases, same photograph, so the two gates are
# directly comparable. CLIP presence probability of the detector's best box:
#
#     present: 0.979 marble figure · 0.961 cross · 0.913 seated woman · 0.892 THE DRAPERY
#              · 0.875 face · 0.613 pedestal · 0.356 stone
#     absent : 0.0048 laptop · 0.0040 traffic light · 0.0005 pizza · 0.0003 helicopter
#              · 0.0001 purple bicycle
#
# Where the DETECTOR's distributions overlapped (absent 0.471 beat present 0.397), CLIP's are
# separated by ~75×: the highest absent score is 0.0048, the lowest present 0.356. That is the
# whole justification for this gate — the detector cannot tell presence, and this can.
#
# 0.25 sits in the gap with margin on both sides: ~50× above the worst false positive, ~1.4×
# below the weakest true positive. Note "stone" (0.356) is the near miss — a vague mass noun with
# no crisp extent is genuinely hard, and it is the phrase to watch if this is ever recalibrated.
DEFAULT_PRESENCE_THRESHOLD = 0.25

_model = None
_processor = None
_load_failed = False


def is_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers
        return hasattr(transformers, "CLIPModel")
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
        from transformers import CLIPModel, CLIPProcessor
        # This repo ships only pytorch_model.bin (no safetensors), so the loader must be told not
        # to insist on safetensors — the manifest records the same asymmetry.
        proc = CLIPProcessor.from_pretrained(CHECKPOINT, revision=REVISION)
        model = CLIPModel.from_pretrained(CHECKPOINT, revision=REVISION, use_safetensors=False)
        _processor = proc
        _model = model.to(_device()).to(torch.float32).eval()
    except Exception as e:  # pragma: no cover — depends on weights/hardware
        _load_failed = True
        print(f"⚠️ CLIP presence gate load failed (non-fatal, gate reports unavailable): {e}")


def unload() -> None:
    """Free the model + GPU memory — the gate sits between two other GPU models."""
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


def crop_box(image, box_xyxy: Sequence[float], *, pad: float = 0.06):
    """Crop a NORMALIZED [x0,y0,x1,y1] box out of a PIL image, with a little context.

    The padding matters: a mask-tight crop of "the drapery" is a texture swatch, and CLIP judges
    textures poorly out of context. A small margin gives it the surrounding evidence a person
    would use, without letting the rest of the picture answer for the box."""
    w, h = image.size
    x0, y0, x1, y1 = (float(v) for v in box_xyxy[:4])
    dx, dy = (x1 - x0) * pad, (y1 - y0) * pad
    px0 = max(0, int((x0 - dx) * w))
    py0 = max(0, int((y0 - dy) * h))
    px1 = min(w, int((x1 + dx) * w))
    py1 = min(h, int((y1 + dy) * h))
    if px1 <= px0 or py1 <= py0:
        return None
    return image.crop((px0, py0, px1, py1))


def presence_score(image, box_xyxy: Sequence[float], phrase: str,
                   *, distractors: Sequence[str] = DISTRACTORS) -> Optional[float]:
    """Does this crop actually show `phrase`? → probability in [0,1], or None.

    Contrastive by construction: the phrase competes with neutral distractors and the returned
    number is the softmax mass it wins. Absolute cosine similarity is NOT used, because it is not
    comparable between phrases.

    None means "could not judge" (model unavailable, degenerate crop) — which the caller must
    treat as a refusal, never as a pass."""
    text = (phrase or "").strip()
    if not text or not is_available():
        return None
    _load()
    if _model is None:
        return None
    crop = crop_box(image, box_xyxy)
    if crop is None:
        return None
    try:
        import torch
        candidates = [f"a photo of {text}"] + [str(d) for d in distractors]
        inputs = _processor(text=candidates, images=crop.convert("RGB"),
                            return_tensors="pt", padding=True, truncation=True).to(_device())
        with torch.no_grad():
            out = _model(**inputs)
        probs = out.logits_per_image.softmax(dim=1)[0]
        return float(probs[0].item())                # mass on the curator's phrase
    except Exception as e:  # pragma: no cover — depends on GPU
        print(f"⚠️ CLIP presence scoring failed (non-fatal): {e}")
        return None


def verify_boxes(image, detection: Optional[Dict[str, Any]], phrase: str, *,
                 threshold: float = DEFAULT_PRESENCE_THRESHOLD, max_check: int = 5
                 ) -> List[Dict[str, Any]]:
    """Score a detector's boxes and keep only those CLIP agrees actually show the phrase.

    Returns survivors as ``[{"box_xyxy", "detector_score", "presence"}]``, best presence first.
    Empty means the detector fired but nothing verified — the honest "it guessed, and it is not
    really there", which is exactly the case a bare detector cannot report.

    Only the top `max_check` detector boxes are scored: CLIP is the expensive stage, and a box
    ranked twentieth by the detector is not the curator's answer."""
    if not isinstance(detection, dict):
        return []
    boxes = detection.get("boxes") or []
    scores = detection.get("scores") or []
    size = detection.get("image_size") or [0, 0]
    w, h = int(size[0] or 0), int(size[1] or 0)
    if not boxes or w <= 0 or h <= 0:
        return []

    survivors: List[Dict[str, Any]] = []
    for i, b in enumerate(boxes[:max_check]):
        x0, y0, x1, y1 = (float(v) for v in b[:4])
        norm = [max(0.0, min(1.0, x0 / w)), max(0.0, min(1.0, y0 / h)),
                max(0.0, min(1.0, x1 / w)), max(0.0, min(1.0, y1 / h))]
        if (norm[2] - norm[0]) <= 0.005 or (norm[3] - norm[1]) <= 0.005:
            continue                                  # a sliver is not a part
        p = presence_score(image, norm, phrase)
        if p is None or p < threshold:
            continue
        survivors.append({"box_xyxy": [round(v, 5) for v in norm],
                          "detector_score": round(float(scores[i]), 4) if i < len(scores) else None,
                          "presence": round(p, 4)})
    survivors.sort(key=lambda s: s["presence"], reverse=True)
    return survivors
