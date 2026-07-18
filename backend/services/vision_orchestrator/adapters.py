"""
VISION-ORCHESTRATOR-001 / VISION-BUILD-001 B2 — real adapter wrappers.

B2 wraps the existing `yolo11n-seg.pt` path as the general `Segmenter` adapter. The rule
that matters: each native instance mask is preserved as **authoritative `mask_rle`** and
is NEVER reduced to a bbox before persistence — rings/bbox/crops are derived only through
`mask_geometry` (Increment A). Mask, class, confidence and model/preprocessing provenance
stay bound to the same candidate id.

`masks_to_regions` is a pure helper (no torch) so the conversion is unit-testable with
synthetic masks; `YoloSegmenterAdapter` lazy-imports ultralytics and runs on the GPU
through the orchestrator. This module import stays torch-free.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from backend.services import mask_geometry
from .contracts import (AdapterSpec, Capability, CancelToken, JobResult, JobStatus,
                        Provenance, ResourceKind, VisionArtifact)

# COCO class → Semant's coarse category vocabulary (mirrors segmentation_service).
_GARMENTS = {"tie", "handbag", "backpack", "umbrella", "suitcase"}


def coco_category(name: str) -> str:
    name = (name or "").lower()
    if name == "person":
        return "figure"
    if name in _GARMENTS:
        return "garment"
    return "object"


def masks_to_regions(masks: Sequence, classes: Sequence, confs: Sequence, names,
                     *, id_prefix: str = "seg", detector: str = "yolo",
                     model_id: str = "yolo11n-seg.pt", checkpoint: Optional[str] = None,
                     device: str = "cpu", preprocessing_version: str = "ultralytics-retina",
                     max_regions: Optional[int] = None) -> List[Dict[str, Any]]:
    """Native instance masks → region dicts whose AUTHORITATIVE geometry is `mask_rle`.

    `masks` is a sequence of 2-D 0/1 arrays (one per instance). Each region gets its
    mask encoded to RLE, then `mask_geometry.canonicalize_geometry` derives
    polygons/legacy-polygon/box + geometry_rev + provenance (model/device/confidence
    bound to the candidate). Legacy fields (box/polygon/label/category) remain present so
    existing consumers keep working; the box is DERIVED, never the stored identity.
    """
    def name_of(cls: int) -> str:
        if isinstance(names, dict):
            return str(names.get(cls, cls))
        try:
            return str(names[cls])
        except Exception:
            return str(cls)

    regions: List[Dict[str, Any]] = []
    for i, m in enumerate(masks):
        rle = mask_geometry.rle_encode_mask(m)
        if mask_geometry.rle_area(rle) <= 0:
            continue                                   # empty instance mask — skip honestly
        cls = int(classes[i]) if i < len(classes) else 0
        conf = float(confs[i]) if i < len(confs) else 0.0
        label = name_of(cls)
        region = {
            "id": f"{id_prefix}_{i}",
            "actor": "auto",
            "detector": detector,
            "label": label,
            "category": coco_category(label),
            "confidence": round(conf, 3),
            "description": f"{label} · {int(conf * 100)}% match",
            "mask_rle": rle,                           # authoritative — set BEFORE canonicalize
        }
        mask_geometry.canonicalize_geometry(region, provenance={
            "adapter": "yolo11n_seg", "model": model_id, "checkpoint": checkpoint,
            "device": device, "preprocessing_version": preprocessing_version,
            "confidence": round(conf, 3),
        })
        regions.append(region)

    regions.sort(key=lambda r: mask_geometry.rle_area(r["mask_rle"]), reverse=True)
    return regions[:max_regions] if max_regions else regions


class YoloSegmenterAdapter:
    """The general `Segmenter` — YOLO11n-seg through the orchestrator, on the GPU pool.
    Returns regions with authoritative masks; never fabricates a mask (an instance with
    no mask is dropped, not coerced to a box)."""

    def __init__(self, *, weights: str = "yolo11n-seg.pt", device: int = 0,
                 conf: float = 0.30, max_regions: int = 12, imgsz: int = 640) -> None:
        self.spec = AdapterSpec(
            name="yolo11n_seg", capability=Capability.SEGMENT, resource=ResourceKind.GPU,
            model_id=weights, license="AGPL-3.0",
            available=self._deps_ok(), deferred=not self._deps_ok(),
            preprocessing_version="ultralytics-retina")
        self.weights = weights
        self.device = device
        self.conf = conf
        self.max_regions = max_regions
        self.imgsz = imgsz
        self._model = None

    @staticmethod
    def _deps_ok() -> bool:
        try:
            import ultralytics  # noqa: F401
            import torch  # noqa: F401
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        return self.spec.available

    async def load(self) -> float:
        if self._model is not None:
            return 0.0
        t0 = time.perf_counter()
        from ultralytics import YOLO
        import torch
        self._model = YOLO(self.weights)
        dev = self.device if torch.cuda.is_available() else "cpu"
        try:
            self._model.to(dev)
        except Exception:
            pass
        return (time.perf_counter() - t0) * 1000.0

    async def unload(self) -> None:
        self._model = None
        try:
            import torch, gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    async def infer(self, payload: dict, cancel: CancelToken) -> JobResult:
        if cancel.cancelled:
            return JobResult(JobStatus.CANCELLED)
        import torch
        if self._model is None:
            await self.load()
        src = payload.get("image") or payload.get("path") or payload.get("image_bytes")
        dev = self.device if torch.cuda.is_available() else "cpu"
        t0 = time.perf_counter()
        results = self._model.predict(src, device=dev, imgsz=self.imgsz, conf=self.conf,
                                      retina_masks=True, verbose=False)
        latency = (time.perf_counter() - t0) * 1000.0
        if not results:
            return JobResult(JobStatus.SUCCEEDED,
                             artifact=VisionArtifact("segment", [], Provenance(adapter=self.spec.name)))
        r = results[0]
        if r.masks is None or r.boxes is None or len(r.boxes) == 0:
            regions: List[dict] = []
        else:
            md = (r.masks.data.detach().to("cpu").numpy() > 0.5).astype("uint8")
            cls = r.boxes.cls.detach().to("cpu").tolist()
            conf = r.boxes.conf.detach().to("cpu").tolist()
            names = r.names if isinstance(r.names, dict) else {i: n for i, n in enumerate(r.names)}
            regions = masks_to_regions([md[i] for i in range(md.shape[0])], cls, conf, names,
                                       model_id=self.weights, device=str(dev),
                                       preprocessing_version=self.spec.preprocessing_version,
                                       max_regions=self.max_regions)
        prov = Provenance(adapter=self.spec.name, model=self.weights, device=str(dev),
                          preprocessing_version=self.spec.preprocessing_version,
                          latency_ms=latency)
        return JobResult(JobStatus.SUCCEEDED,
                         artifact=VisionArtifact("segment", regions, prov), provenance=prov)


# ── B3: exact-mask refiner (SAM 2.1 Hiera Tiny) ──────────────────────────────
_SAM2_CFG = "configs/sam2.1/sam2.1_hiera_t.yaml"
_SAM2_CKPT = os.path.join(os.getcwd(), "models", "sam2.1_hiera_tiny.pt")


def refined_mask_to_region(mask2d, *, base_id: Optional[str] = None,
                           base_geometry_rev: int = 0, score: Optional[float] = None,
                           prompt: str = "point", device: str = "cuda",
                           model_id: str = "sam2.1_hiera_tiny",
                           checkpoint: Optional[str] = None) -> Dict[str, Any]:
    """A refiner's 0/1 mask → a PROPOSED region revision. Non-destructive: it carries the
    NEXT geometry_rev and `proposed=True`; the base evidence is not overwritten until the
    curator confirms (B4). When `base_id` is given the same Region identity is upgraded."""
    region: Dict[str, Any] = {
        "id": base_id or f"refine_{uuid.uuid4().hex[:10]}",
        "actor": "creator",                       # a refinement is user-directed
        "detector": "sam2",
        "mask_rle": mask_geometry.rle_encode_mask(mask2d),
        "confidence": round(float(score), 3) if score is not None else None,
        "refined_from": base_id,
        "proposed": True,
        "geometry_rev": int(base_geometry_rev),   # canonicalize bumps to +1
    }
    mask_geometry.canonicalize_geometry(region, provenance={
        "adapter": "sam21_hiera_tiny", "model": model_id, "checkpoint": checkpoint,
        "device": device, "method": "sam2-refine", "prompt": prompt,
    })
    return region


class Sam2RefinerAdapter:
    """The `MaskRefiner` — SAM 2.1 Hiera Tiny, point/box/existing-mask prompts, on the GPU
    pool. Benchmarked local-viable on this box (peak ~597 MiB VRAM, warm prompts 11–166 ms,
    clean unload). Returns a PROPOSED region revision; never overwrites saved evidence."""

    def __init__(self, *, config: str = _SAM2_CFG, checkpoint: str = _SAM2_CKPT,
                 device: int = 0) -> None:
        self.config = config
        self.checkpoint = checkpoint
        self.device = device
        self._predictor = None
        self.spec = AdapterSpec(
            name="sam21_hiera_tiny", capability=Capability.MASK_REFINE,
            resource=ResourceKind.GPU, model_id="sam2.1_hiera_tiny", checkpoint=checkpoint,
            preprocessing_version="sam2.1", available=self._deps_ok(),
            deferred=not self._deps_ok())

    def _deps_ok(self) -> bool:
        try:
            import sam2  # noqa: F401
            import torch  # noqa: F401
            return os.path.exists(self.checkpoint)
        except Exception:
            return False

    def is_available(self) -> bool:
        return self.spec.available

    async def load(self) -> float:
        if self._predictor is not None:
            return 0.0
        t0 = time.perf_counter()
        import torch
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        dev = f"cuda:{self.device}" if torch.cuda.is_available() else "cpu"
        model = build_sam2(self.config, self.checkpoint, device=dev)
        self._predictor = SAM2ImagePredictor(model)
        return (time.perf_counter() - t0) * 1000.0

    async def unload(self) -> None:
        self._predictor = None
        try:
            import torch, gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    async def infer(self, payload: dict, cancel: CancelToken) -> JobResult:
        if cancel.cancelled:
            return JobResult(JobStatus.CANCELLED)
        import numpy as np
        if self._predictor is None:
            await self.load()
        image = payload.get("image")               # HxWx3 RGB ndarray (or PIL)
        if image is None:
            path = payload.get("path")
            from PIL import Image
            image = np.array(Image.open(path).convert("RGB"))
        image = np.asarray(image)
        prompt = payload.get("prompt") or {}
        base_id = payload.get("base_id")
        base_rev = int(payload.get("base_geometry_rev", 0))

        t0 = time.perf_counter()
        self._predictor.set_image(image)
        kwargs: Dict[str, Any] = {"multimask_output": bool(prompt.get("multimask", True))}
        kind = "point"
        if prompt.get("points"):
            kwargs["point_coords"] = np.asarray(prompt["points"], dtype=float)
            kwargs["point_labels"] = np.asarray(prompt.get("labels", [1] * len(prompt["points"])))
        if prompt.get("box") is not None:
            kwargs["box"] = np.asarray(prompt["box"], dtype=float); kind = "box"
        if prompt.get("mask_input") is not None:
            kwargs["mask_input"] = np.asarray(prompt["mask_input"]); kind = "existing-mask"
        masks, scores, _ = self._predictor.predict(**kwargs)
        latency = (time.perf_counter() - t0) * 1000.0
        best = int(np.argmax(scores))
        region = refined_mask_to_region(
            (masks[best] > 0).astype("uint8"), base_id=base_id, base_geometry_rev=base_rev,
            score=float(scores[best]), prompt=kind, checkpoint=self.checkpoint)
        prov = Provenance(adapter=self.spec.name, model="sam2.1_hiera_tiny",
                          checkpoint=self.checkpoint, device=str(self.device),
                          preprocessing_version="sam2.1", latency_ms=latency,
                          confidence=round(float(scores[best]), 3),
                          geometry_rev=region["geometry_rev"])
        return JobResult(JobStatus.SUCCEEDED,
                         artifact=VisionArtifact("mask_refine", region, prov), provenance=prov)
