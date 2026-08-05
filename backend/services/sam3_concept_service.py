"""
CONCEPT-SEG-001 (SF-004) — SAM 3 Promptable Concept Segmentation.

WHAT IT ANSWERS. Given an image and a CONCEPT (`"collar"`, `"snake hood"`, `"raised hand"`),
return a real pixel mask for EVERY instance of it. Not the box a language model guessed — the
extent, measured off the signal.

WHY THIS EXISTS. The SŪKṢMA fine-parts stage currently asks a VLM to dissect an image and hand
back sub-part boxes. Those boxes are ESTIMATED from a reading; the stage emits no `mask_rle` at
all. The SF-004-R2 spike measured that directly: 0 masks on 72/72 baseline parts from the VLM,
against 27/35 concepts really masked by this model on the same three fixtures.

THE TWO STATUSES, WHICH ARE THE WHOLE POINT (SF-004-R §5.3). One SAM-3 result carries two
claims of different kinds:

    the MASK  is `measured` — computed off the image signal
    the LABEL is `interpretive` — it was handed to the model in the prompt

SAM 3 never named anything. It was told a name and measured where that name lands. The spike
found the failure this predicts, on a painting: `shoulder fabric` at confidence 0.27–0.43
returned a real, well-formed mask of the BACKGROUND. The extent was measured correctly; the
binding of the words to it was simply wrong. Collapsing the two into one status would make that
result either wholly trustworthy or wholly discardable, and it is neither — the measurement is
good and the naming is not. `suggestion_service.suggestions_from_concept_segments` emits them as
two descriptors, and the confidence floor below is aimed at the naming, never at the geometry.

SHAPE. Mirrors the other GPU services exactly — lazy singleton, module-level `unload()`, so
`model_residency` DISCOVERS it with no registration step (that module exists because a
hand-maintained release list was wrong four times running). `MODEL_TAG` names it on the receipt.

AVAILABILITY IS GATED ON WEIGHTS, DELIBERATELY. ~3.2 GiB, and the spike measured 5.3 s per
concept warm on an M4 — a GO on quality, not on cost. Nothing here downloads anything: if the
checkpoint is not on disk the service reports unavailable and the caller falls back to the VLM
and SAYS SO. A deploy with no weights (Render) degrades honestly rather than failing.
"""
from __future__ import annotations

import os
import threading
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence

CHECKPOINT = "facebook/sam3"
MODEL_TAG = "sam3"
PREPROCESSING_VERSION = "sam3-pcs-v1"

#: Where the weights live. An explicit path, never a hub download at request time: fetching 3.2
#: GiB inside a live route is not a fallback, it is an outage. `scripts/spike_sam3` records the
#: acquisition (1036 s over plain HTTP, and it did NOT resume when the first attempt died).
WEIGHTS_ENV = "SAM3_WEIGHTS"

#: The operating point, measured. At 0.05 the spike's recall rose to 33/35 but the instance
#: counts exploded into nonsense — `snake tongue` 17 → 162, `serpent scale` 1 → 93. At 0.25 the
#: counts stay believable. This is a floor on the NAMING, which is what confidence tracks; the
#: mask it comes with is measured either way (see the two-status note above).
DEFAULT_CONF = 0.25

#: SF-004-R2 §4.3: confidence tracked correctness. `snake hood` at 0.92 was right eleven times
#: over; `shoulder fabric` at 0.27–0.43 masked the background. Below this line the naming is not
#: trusted enough to propose as a reading — the extent may still be emitted, tagged for what it
#: is. Not calibrated: three fixtures and thirty-five concepts is an observation, not a curve.
NAMING_CONFIDENCE_FLOOR = 0.50

DEFAULT_IMGSZ = 1024

_predictor = None
_lock = threading.Lock()


def weights_path() -> Optional[str]:
    """The checkpoint path if it is actually on disk, else None. Existence, not configuration —
    an env var pointing at a file that was never fetched is not availability."""
    path = (os.environ.get(WEIGHTS_ENV) or "").strip()
    if not path:
        return None
    return path if os.path.exists(path) else None


def is_available() -> bool:
    """Weights present AND the runtime imports. Both halves, and a raise counts as DOWN —
    fail-closed, matching every other capability probe in the system."""
    if weights_path() is None:
        return False
    try:
        import torch  # noqa: F401
        from ultralytics.models.sam import SAM3SemanticPredictor  # noqa: F401
        return True
    except Exception:
        return False


def device() -> str:
    """CUDA where it exists, MPS on Apple Silicon, CPU as the honest last resort.

    MPS is here because it is what the spike actually ran on: Ultralytics'
    `SAM3SemanticPredictor` on `device="mps"` worked first try, and neither the reference repo
    nor the `sam3-apple-silicon` fork was needed. This module was for a long time the ONLY one
    that knew that; the resolution now lives in `torch_device` so every adapter knows it.

    `indexed=True` because Ultralytics wants the ordinal — `cuda:0`, not `cuda`. The docstring
    used to lead with "MPS first" while the code checked CUDA first; the code was right (see
    `torch_device` on why the order is nearly unobservable anyway) and the sentence is now fixed
    rather than the behaviour.
    """
    from backend.services.torch_device import resolve
    return resolve(indexed=True)


def load(*, conf: float = DEFAULT_CONF, imgsz: int = DEFAULT_IMGSZ) -> float:
    """Build the predictor. Returns load_ms. Idempotent — a second call is free.

    NB the spike measured a 14.3 s cold start (13.9 s of it the first inference, because the
    encoder builds lazily). Nothing here can hide that; the caller's telemetry should see it.
    """
    global _predictor
    with _lock:
        if _predictor is not None:
            return 0.0
        path = weights_path()
        if path is None:
            raise RuntimeError(
                f"SAM 3 weights not found — set {WEIGHTS_ENV} to the checkpoint path")
        t0 = time.perf_counter()
        from ultralytics.models.sam import SAM3SemanticPredictor
        # Instantiated DIRECTLY, not through `SAM("sam3.pt")`: that wires the plain
        # `SAM3Predictor`, which has no text path at all. The semantic predictor is the only one
        # whose `inference()` takes `text=`. Losing an afternoon to this is why it is written down.
        _predictor = SAM3SemanticPredictor(overrides={
            "model": path, "device": device(), "imgsz": imgsz, "conf": conf,
            "save": False, "verbose": False, "mode": "predict", "task": "segment"})
        return (time.perf_counter() - t0) * 1000.0


def unload() -> None:
    """Release the weights. Module-level and named exactly this, so `model_residency` finds it
    by discovery rather than by anyone remembering to register it."""
    global _predictor
    with _lock:
        _predictor = None
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def _to_source(image: Any) -> Any:
    """Whatever the caller has → something Ultralytics accepts.

    THIS IS WHERE THE SPIKE AND PRODUCTION DIVERGE, and it is worth naming because the spike
    could not have found it. The spike fed `str(path)` — it had files on disk. Every production
    caller has BYTES: `posts._fetch_post_image_cached` returns the fetched image, and no file is
    ever written. Ultralytics' `check_source` accepts str/Path/PIL/ndarray/Tensor and raises
    `TypeError: Unsupported image type` on bytes or a `BytesIO`, so handing it what the route
    actually holds would have failed on the first real call.

    Decoded to PIL rather than to a numpy array on purpose: Ultralytics treats a bare ndarray as
    BGR and a PIL image as RGB, and getting that backwards is a colour-channel swap that
    degrades results without raising anything.
    """
    if isinstance(image, (bytes, bytearray, memoryview)):
        from PIL import Image
        return Image.open(BytesIO(bytes(image))).convert("RGB")
    if isinstance(image, BytesIO):
        from PIL import Image
        image.seek(0)
        return Image.open(image).convert("RGB")
    return image


def segment_concept(image: Any, concept: str, *, conf: float = DEFAULT_CONF,
                    max_instances: int = 16) -> Dict[str, Any]:
    """One concept → every instance of it, as canonical RLE.

    Returns `{"concept", "instances": [...], "latency_ms", "device", "model", "truncated"}`.
    Each instance is `{"mask_rle", "confidence", "index"}`.

    AN EMPTY LIST IS A REAL ANSWER and is returned as one. The spike logged silent-empty-returns
    as an open question precisely because a concept that is not in the picture and a concept the
    model failed on look identical from the outside; conflating either with an error would let a
    caller invent a fallback box, which is the fabrication this whole organ exists to remove.
    """
    from backend.services.mask_geometry import rle_encode_mask

    if _predictor is None:
        load(conf=conf)
    t0 = time.perf_counter()
    res = _predictor(source=_to_source(image), text=[concept])
    latency = (time.perf_counter() - t0) * 1000.0

    r = res[0] if isinstance(res, (list, tuple)) else res
    masks = getattr(r, "masks", None)
    data = getattr(masks, "data", None) if masks is not None else None
    instances: List[Dict[str, Any]] = []
    if data is not None and getattr(data, "shape", (0,))[0]:
        arr = (data.detach().to("cpu").numpy() > 0.5).astype("uint8")
        boxes = getattr(r, "boxes", None)
        confs: Sequence[float] = []
        if boxes is not None and getattr(boxes, "conf", None) is not None and len(boxes.conf):
            confs = [float(c) for c in boxes.conf.detach().to("cpu").numpy()]
        for i in range(min(arr.shape[0], max_instances)):
            instances.append({
                "index": i,
                "mask_rle": rle_encode_mask(arr[i]),
                "confidence": round(confs[i], 4) if i < len(confs) else None,
            })
    return {
        "concept": concept,
        "instances": instances,
        # Reported, never trimmed silently — the headline claim is that it segments EXHAUSTIVELY,
        # so a cap that hid how many it actually found would hide the thing worth checking.
        "truncated": bool(data is not None and getattr(data, "shape", (0,))[0] > max_instances),
        "latency_ms": round(latency, 1),
        "device": device(),
        "model": CHECKPOINT,
    }


def instances_to_regions(result: Dict[str, Any], *, prefix: str = "cseg") -> List[Dict[str, Any]]:
    """A concept result's instances → PROPOSED Regions that own the masks.

    The mark contract requires a suggestion to REFERENCE a region's mask by id, never to inline
    it (`validateMark`: `raster_mask` needs `mask_ref.region_id`). So the masks have to become
    regions first — the same move `refined_mask_to_region` makes for SAM 2 — and the two-status
    descriptors then both point here.

    Mutates each instance with its `region_id`, so `suggestions_from_concept_segments` can find
    it, and returns the regions for the caller to put in front of the curator.

    `proposed=True`: nothing is committed. These are candidate extents awaiting review, and the
    curator fields carry Region's own defaults so the shape stays schema-valid.
    """
    from backend.services import mask_geometry

    concept = result.get("concept") or ""
    slug = "".join(ch if ch.isalnum() else "_" for ch in concept)[:24] or "concept"
    regions: List[Dict[str, Any]] = []
    for inst in result.get("instances") or []:
        if not inst.get("mask_rle"):
            continue
        region: Dict[str, Any] = {
            "id": f"{prefix}_{slug}_{inst.get('index')}",
            "actor": "auto",
            "detector": MODEL_TAG,
            # The label lives on the NAMING descriptor, not here. A region minted with the
            # concept already written on it would smuggle the interpretive half into the
            # measured object and make the two statuses inseparable again.
            "label": "",
            "confidence": inst.get("confidence"),
            "mask_rle": inst["mask_rle"],
            "proposed": True,
            "geometry_rev": 0,
            "prioritised": False,
            "weight": 0,
            "user_note": "",
        }
        mask_geometry.canonicalize_geometry(region, provenance={
            "adapter": MODEL_TAG, "model": CHECKPOINT, "device": device(),
            "method": "sam3-concept-segment", "prompt": concept,
        })
        inst["region_id"] = region["id"]
        inst["geometry_rev"] = region.get("geometry_rev", 0)
        regions.append(region)
    return regions


def segment_concepts(image: Any, concepts: Sequence[str], *, conf: float = DEFAULT_CONF,
                     max_instances: int = 16) -> List[Dict[str, Any]]:
    """Several concepts on one image, in order.

    ONE CALL PER CONCEPT, which is the cost. The spike measured 5.3 s warm per concept, so a
    twelve-concept image is a minute of wall clock — the reason this organ is opt-in rather than
    the default SŪKṢMA path. `encode-once-prompt-many` is the obvious fix and is NOT implemented
    here: the Ultralytics semantic predictor exposes no such seam, and inventing one against its
    internals inside a production route is not a thing to do on a measurement this thin.
    """
    return [segment_concept(image, c, conf=conf, max_instances=max_instances) for c in concepts]
