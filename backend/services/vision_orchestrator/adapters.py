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

import time
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
