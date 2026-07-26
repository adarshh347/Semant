"""
CIRCUIT-001 P8-A — Florence-2: the Director's local eyes.

Until now the Director reasons on Groq (cloud) with no local vision. Every local model in the
roster answers ONE narrow question — YOLO segments, DINOv2 embeds, Depth-Anything measures
distance. Florence-2 is the first that answers *what you ask it*: one small model covering
captioning, detection, phrase-grounding and referring-expression segmentation.

The verb this unlocks first is **open-vocab find_parts** — "name it and get it". Today a curator
can only work with the parts a segmenter happened to find; with grounding they can ask for
"the folded cloth at her knee" and get a mask. The same adapter later answers `enumerate`
("how many arches?") and `presence_check` ("is X here?"), which is why the adapter exposes the
whole task surface even though one producer uses it now.

DEPS — the honest finding, corrected by running it:
  · transformers 5.13 DOES implement Florence2 natively (`Florence2ForConditionalGeneration`,
    `Florence2Processor`), and `AutoConfig.from_pretrained` resolves to the built-in
    `Florence2Config` with no remote code. That much is true and was verified first.
  · BUT the model still does not load. `microsoft/Florence-2-base` is the ORIGINAL remote-code
    checkpoint, and its tokenizer predates the `image_token` the native processor expects:
        RobertaTokenizer has no attribute image_token
    The native classes target a converted checkpoint format that this repo is not. No official
    or community native conversion exists (the alternatives on the hub are Microsoft's original
    or ONNX ports, and nothing here uses ONNX).
  · So running this checkpoint requires **trust_remote_code=True** — executing
    processing_florence2.py from the hub. That is a consent decision, not a config detail, so it
    is OFF by default and gated behind SEMANT_FLORENCE_TRUST_REMOTE_CODE=1.
    `is_available()` reports False while it is off: a producer that cannot actually run must not
    claim it can, or the endpoint spends seven seconds failing to load before saying "nothing".
  · `timm` is present (arrived with Intrinsic). No new package, no system deps.
  · Weights are provisioned through WEIGHTS-001 (`weights.manifest.json` +
    scripts/fetch_weights.py), pinned by commit, with `pytorch_model.bin` excluded — the repo
    ships both formats and demanding the redundant one makes the snapshot permanently
    "incomplete" (the fashion-clip lesson).

Shape mirrors `depth_service` / `dinov2_service`: a lazy GPU singleton with an explicit
`unload()`, so `ModelManager` enforces single-GPU residency on the 4 GB card. Geometry leaves
this module as normalized boxes/polygons — never as a rendered overlay, and never as an
assertion about what the image means.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

CHECKPOINT = "microsoft/Florence-2-base"
# Executing model code from the hub is a consent decision (same class as Intrinsic's
# gen-efficientnet trust_repo step), so it is opt-in and never implicit.
TRUST_REMOTE_CODE = os.environ.get("SEMANT_FLORENCE_TRUST_REMOTE_CODE", "") == "1"
# WEIGHTS-001 — pinned HF commit, passed to every from_pretrained so the pin is ENFORCED at load.
# Mirrors weights.manifest.json.
REVISION = "5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac"
MODEL_TAG = "florence2_base"
PREPROCESSING_VERSION = "florence2-base-v1"

# Florence-2 is driven by task tokens, not free prose. These are the four that matter to the
# circuit; the model supports more. `<CAPTION_TO_PHRASE_GROUNDING>` and
# `<REFERRING_EXPRESSION_SEGMENTATION>` both take a phrase — the others take none.
TASK_CAPTION = "<CAPTION>"
TASK_DETECT = "<OD>"                                   # open detection: every object it knows
TASK_GROUNDING = "<CAPTION_TO_PHRASE_GROUNDING>"       # phrase → boxes
TASK_REFERRING_SEG = "<REFERRING_EXPRESSION_SEGMENTATION>"   # phrase → polygon(s)
PHRASE_TASKS = {TASK_GROUNDING, TASK_REFERRING_SEG}
TASKS = (TASK_CAPTION, TASK_DETECT, TASK_GROUNDING, TASK_REFERRING_SEG)

_model = None
_processor = None
_load_failed = False


def is_available() -> bool:
    """True only when this checkpoint can ACTUALLY load — not merely when the package imports.

    Availability that outruns capability is a lie the rest of the system acts on: the endpoint
    would accept the request, spend seven seconds failing to load, and then report "nothing here"
    as though the phrase had grounded nothing. So this requires the remote-code opt-in, without
    which `microsoft/Florence-2-base` cannot be loaded by transformers 5.13 at all."""
    try:
        import torch  # noqa: F401
        import transformers
        if not hasattr(transformers, "Florence2ForConditionalGeneration"):
            return False
        return TRUST_REMOTE_CODE and not _load_failed
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
        from transformers import AutoModelForCausalLM, AutoProcessor
        # trust_remote_code is gated by is_available(), so reaching here means it was granted.
        proc = AutoProcessor.from_pretrained(CHECKPOINT, revision=REVISION,
                                             trust_remote_code=TRUST_REMOTE_CODE)
        model = AutoModelForCausalLM.from_pretrained(CHECKPOINT, revision=REVISION,
                                                     trust_remote_code=TRUST_REMOTE_CODE)
        _processor = proc
        _model = model.to(_device()).to(torch.float32).eval()
    except Exception as e:  # pragma: no cover — depends on weights/hardware
        _load_failed = True
        print(f"⚠️ Florence-2 load failed (non-fatal, find_parts reports unavailable): {e}")


def unload() -> None:
    """Free the model + GPU memory — called when the GPU slot goes to another adapter."""
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


def run_task(image, task: str, *, phrase: Optional[str] = None,
             max_new_tokens: int = 512) -> Optional[Dict[str, Any]]:
    """Run ONE Florence task and return its parsed result, or None.

    `task` is a task token (see TASKS). Phrase tasks require `phrase`; asking for one without it
    is a refusal, not a silent whole-image answer — "find the thing I didn't name" has no honest
    result. The return is Florence's own parsed structure (`{task: {...}}` with `bboxes`/`labels`
    or `polygons`), normalized to the image size by the processor."""
    if task not in TASKS:
        return None
    if task in PHRASE_TASKS and not (phrase or "").strip():
        return None
    if not is_available():
        return None
    _load()
    if _model is None:
        return None
    try:
        import torch
        im = image.convert("RGB")
        prompt = task + (phrase.strip() if task in PHRASE_TASKS and phrase else "")
        inputs = _processor(text=prompt, images=im, return_tensors="pt").to(_device())
        with torch.no_grad():
            ids = _model.generate(input_ids=inputs["input_ids"],
                                  pixel_values=inputs["pixel_values"],
                                  max_new_tokens=max_new_tokens, num_beams=3, do_sample=False)
        text = _processor.batch_decode(ids, skip_special_tokens=False)[0]
        parsed = _processor.post_process_generation(text, task=task,
                                                    image_size=(im.width, im.height))
        return {"task": task, "phrase": phrase, "result": parsed,
                "image_size": [im.width, im.height]}
    except Exception as e:  # pragma: no cover — depends on GPU
        print(f"⚠️ Florence-2 inference failed (non-fatal): {e}")
        return None


def ground_phrase(image, phrase: str) -> Optional[Dict[str, Any]]:
    """A phrase → regions: the open-vocab find_parts reading.

    Tries referring-expression segmentation first (polygons — a real extent), falling back to
    phrase grounding (boxes) when the model returns no polygon. Returns
    ``{"polygons": [...], "boxes": [...], "labels": [...], "image_size": [w, h]}`` in PIXEL
    coordinates as Florence emits them; the pure converter normalizes. None when the phrase
    grounds nothing — which is the honest answer, not an empty mask."""
    seg = run_task(image, TASK_REFERRING_SEG, phrase=phrase)
    grd = None
    polys: List[Any] = []
    if seg:
        block = (seg["result"] or {}).get(TASK_REFERRING_SEG) or {}
        polys = block.get("polygons") or []

    boxes: List[Any] = []
    labels: List[str] = []
    if not polys:
        grd = run_task(image, TASK_GROUNDING, phrase=phrase)
        if grd:
            block = (grd["result"] or {}).get(TASK_GROUNDING) or {}
            boxes = block.get("bboxes") or []
            labels = block.get("labels") or []

    if not polys and not boxes:
        return None                                  # the phrase grounds nothing here
    size = (seg or grd or {}).get("image_size") or [0, 0]
    return {"polygons": polys, "boxes": boxes, "labels": labels,
            "phrase": phrase, "image_size": size}
