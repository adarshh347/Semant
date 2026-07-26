"""
CIRCUIT-001 P8-B — GroundingDINO: the detector half of Grounded-SAM.

Open-vocab find_parts, delivered the modular way. P8-A tried to do it with one model
(Florence-2) and could not: that checkpoint loads under neither the native transformers path nor
`trust_remote_code` on 5.13. So the verb is split across two models that DO run here:

    phrase → GroundingDINO → box → SAM2 (already live) → mask → find_parts suggestion

This is the canonical "detector + segmenter" arrangement. It is also better separation than the
monolith: the detector answers *where roughly*, the segmenter answers *exactly what extent*, and
each can be swapped without touching the other.

Why GroundingDINO-tiny:
  · it loads NATIVELY on transformers 5.13 (`GroundingDinoForObjectDetection`) — the repo ships
    NO remote code at all, so unlike Florence-2 there is no trust decision to make;
  · Apache-2.0, so unlike YOLO's AGPL it carries no distribution constraint;
  · natural-phrase grounding is what it is for ("the folded cloth at her knee"), where OWLv2 is
    happier with short object nouns. OWLv2 stays the documented fallback.

Text prompt convention: GroundingDINO expects lowercase phrases terminated by a period, and
treats `.` as the separator between candidate phrases. Getting this wrong silently degrades
grounding quality rather than erroring, which is why it is normalized here in one place.

Shape mirrors the other GPU services: a lazy singleton with an explicit `unload()`, so
`ModelManager` can keep exactly one heavy model resident on the 4 GB card. That matters more
here than anywhere: this producer runs TWO models, and they must never be co-resident.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

CHECKPOINT = "IDEA-Research/grounding-dino-tiny"
# WEIGHTS-001 — pinned HF commit, passed to every from_pretrained so the pin is ENFORCED at load.
REVISION = "a2bb814dd30d776dcf7e30523b00659f4f141c71"
MODEL_TAG = "grounding_dino_tiny"
PREPROCESSING_VERSION = "grounding-dino-tiny-v1"

# CALIBRATED, and the calibration is the interesting part.
#
# GroundingDINO's score does NOT encode presence. It is an open-vocab detector, not a presence
# head: asked for something absent it still returns its best guess, confidently. Measured on one
# real photograph (a Pietà), 11 phrases, box_threshold=0.05 so nothing was filtered:
#
#     present: 0.792 marble figure · 0.582 seated woman · 0.575 cross · 0.555 face
#              · 0.453 pedestal · 0.384 stone
#     absent : 0.471 traffic light · 0.444 purple bicycle · 0.440 helicopter
#              · 0.339 pizza slice · 0.286 laptop
#
# The distributions OVERLAP — "a purple bicycle" (0.444) outscored "the drapery" (0.397). So no
# threshold is clean, and the default of 0.35 that seemed reasonable would have cut a confident
# mask around a bicycle that is not in the picture.
#
# 0.5 rejects all five absent phrases and keeps four of six present ones. That is a deliberate
# trade: ~2/3 recall in exchange for no fabricated regions on this sample. For a tool whose whole
# claim is that it never invents evidence, a missed part ("nothing here") costs far less than an
# invented one — the curator can rephrase, but they cannot un-see a mask that was never real.
#
# P8-C SUPERSEDES the 0.5 above. That number existed because the detector was the ONLY guard, so
# it had to be set where absent phrases could not pass — costing ~1/3 of real queries. The CLIP
# presence gate is now the guard, and it separates present from absent by ~75× where the detector
# could not separate them at all. So the detector returns to being what it is good at — proposing
# candidate locations — and 0.30 lets the weak-but-real ones through ("the drapery" 0.397,
# "stone" 0.384) for CLIP to judge.
#
# The safety property is unchanged and now stronger: a fabrication must fool BOTH models.
DEFAULT_BOX_THRESHOLD = 0.30
DEFAULT_TEXT_THRESHOLD = 0.25

_model = None
_processor = None
_load_failed = False


def is_available() -> bool:
    """True when transformers implements GroundingDINO natively and torch is present.

    No remote-code escape hatch: if the native class is absent the answer is False, rather than
    silently falling back to executing model code from the hub (the P8-A lesson)."""
    try:
        import torch  # noqa: F401
        import transformers
        return hasattr(transformers, "GroundingDinoForObjectDetection")
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
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        proc = AutoProcessor.from_pretrained(CHECKPOINT, revision=REVISION)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(CHECKPOINT, revision=REVISION)
        _processor = proc
        _model = model.to(_device()).to(torch.float32).eval()
    except Exception as e:  # pragma: no cover — depends on weights/hardware
        _load_failed = True
        print(f"⚠️ GroundingDINO load failed (non-fatal, find_parts reports unavailable): {e}")


def unload() -> None:
    """Free the model + GPU memory. Called before SAM2 runs — the two must not share the card."""
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


def normalize_prompt(phrase: str) -> str:
    """GroundingDINO's text convention: lowercase, period-terminated.

    A malformed prompt does not raise — it just grounds worse — so normalizing in one place is
    the difference between a reliable verb and an occasionally-mystifying one."""
    text = (phrase or "").strip().lower()
    if not text:
        return ""
    return text if text.endswith(".") else text + "."


def detect(image, phrase: str, *, box_threshold: float = DEFAULT_BOX_THRESHOLD,
           text_threshold: float = DEFAULT_TEXT_THRESHOLD) -> Optional[Dict[str, Any]]:
    """A phrase → grounded boxes, or None.

    Returns ``{"boxes": [[x0,y0,x1,y1], …] (PIXEL), "scores": [...], "labels": [...],
    "image_size": [w, h], "phrase": …}`` sorted by score, highest first. Normalization into the
    repo's [0,1] contract is the pure converter's job, exactly once, in `mask_geometry`.

    None when the package is unavailable, the phrase is empty, or nothing clears the threshold —
    the last being the honest presence-check: a phrase that grounds nothing must ground nothing."""
    prompt = normalize_prompt(phrase)
    if not prompt or not is_available():
        return None
    _load()
    if _model is None:
        return None
    try:
        import torch
        im = image.convert("RGB")
        inputs = _processor(images=im, text=prompt, return_tensors="pt").to(_device())
        with torch.no_grad():
            outputs = _model(**inputs)
        res = _processor.post_process_grounded_object_detection(
            outputs, inputs["input_ids"], threshold=box_threshold,
            text_threshold=text_threshold, target_sizes=[(im.height, im.width)])[0]
        boxes = [[float(v) for v in b] for b in res["boxes"].tolist()]
        scores = [float(s) for s in res["scores"].tolist()]
        labels = list(res.get("text_labels") or res.get("labels") or [])
        if not boxes:
            return None                              # grounded nothing — an honest answer
        order = sorted(range(len(boxes)), key=lambda i: scores[i], reverse=True)
        return {
            "boxes": [boxes[i] for i in order],
            "scores": [scores[i] for i in order],
            "labels": [str(labels[i]) if i < len(labels) else "" for i in order],
            "image_size": [im.width, im.height],
            "phrase": phrase.strip(),
        }
    except Exception as e:  # pragma: no cover — depends on GPU
        print(f"⚠️ GroundingDINO inference failed (non-fatal): {e}")
        return None
