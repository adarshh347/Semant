"""
VISION-ORCHESTRATOR-001 — adapter protocol, fake adapters, and the full roster.

The registry models the COMPLETE target roster of VISION-MODEL-MATRIX-001 as deferred
specs, even though B1 installs/executes none of them ("current models only" limits
execution, not architectural preparedness). B1 registers deterministic fake adapters for
tests; B2+ swaps in real wrappers over the existing YOLO/SegFormer/FashionCLIP loaders.
"""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Dict, List, Optional, Protocol

from .contracts import (AdapterSpec, Capability, CancelToken, JobResult, JobStatus,
                        Provenance, ResourceKind, VisionArtifact)


class Adapter(Protocol):
    """Every model wrapper implements this. Inference is async so the scheduler can hold
    resource semaphores across awaits without blocking the loop."""
    spec: AdapterSpec

    def is_available(self) -> bool: ...
    async def load(self) -> float: ...        # returns load_ms
    async def unload(self) -> None: ...
    async def infer(self, payload: dict, cancel: CancelToken) -> JobResult: ...


# ── the complete target roster (deferred specs) ─────────────────────────────
def default_roster() -> List[AdapterSpec]:
    return [
        AdapterSpec("yolo11n_seg", Capability.SEGMENT, ResourceKind.GPU,
                    "yolo11n-seg.pt", license="AGPL-3.0", available=False, deferred=True),
        AdapterSpec("sam21_hiera_tiny", Capability.MASK_REFINE, ResourceKind.GPU,
                    "sam2.1_hiera_tiny", available=False, deferred=True),
        AdapterSpec("fashionpedia_r50fpn", Capability.FASHION_PARSE, ResourceKind.GPU,
                    "fashionpedia-attribute-mask-rcnn-r50-fpn", available=False, deferred=True),
        AdapterSpec("segformer_b0_ade", Capability.ARCH_PARSE, ResourceKind.GPU,
                    "nvidia/segformer-b0-finetuned-ade-512-512", available=False, deferred=True),
        AdapterSpec("dinov2_vits14", Capability.FEATURE, ResourceKind.GPU,
                    "dinov2_vits14", available=False, deferred=True),
        AdapterSpec("depth_anything_v2_small", Capability.DEPTH, ResourceKind.GPU,
                    "Depth-Anything-V2-Small", available=False, deferred=True),
        AdapterSpec("fashion_clip", Capability.EMBED, ResourceKind.CPU,
                    "patrickjohncyh/fashion-clip", available=False, deferred=True),
        AdapterSpec("fashion_clip_router", Capability.DOMAIN_ROUTE, ResourceKind.CPU,
                    "patrickjohncyh/fashion-clip", available=False, deferred=True),
        AdapterSpec("cpu_perceptual", Capability.PERCEPTUAL, ResourceKind.CPU_LIGHT,
                    "opencv+numpy+skimage", available=False, deferred=True),
        AdapterSpec("cloud_vlm", Capability.SEMANTIC_ANNOTATE, ResourceKind.REMOTE,
                    "cloud-vision-language-model", available=False, deferred=True),
    ]


class FakeAdapter:
    """Deterministic adapter for orchestration tests. Records load/unload/infer calls,
    simulates latency, and can be configured unavailable or to fail — so the scheduler's
    concurrency, cancellation, cache, deferral and failure-isolation are all testable
    without a single real model."""

    def __init__(self, spec: AdapterSpec, *, latency: float = 0.02,
                 output=None, fail: bool = False, available: bool = True):
        self.spec = spec
        self.latency = latency
        self._output = output if output is not None else {"name": spec.name}
        self._fail = fail
        self._available = available
        self.loaded = False
        self.unloaded = False
        self.load_calls = 0
        self.infer_calls = 0

    def is_available(self) -> bool:
        return self._available and self.spec.available

    async def load(self) -> float:
        self.load_calls += 1
        await asyncio.sleep(self.latency / 2)
        self.loaded = True
        self.unloaded = False
        return self.latency / 2 * 1000.0

    async def unload(self) -> None:
        self.loaded = False
        self.unloaded = True

    async def infer(self, payload: dict, cancel: CancelToken) -> JobResult:
        self.infer_calls += 1
        if cancel.cancelled:
            return JobResult(JobStatus.CANCELLED)
        t0 = time.perf_counter()
        await asyncio.sleep(self.latency)          # simulate work; lets peers overlap if allowed
        if cancel.cancelled:                        # boundary re-check after the await
            return JobResult(JobStatus.CANCELLED)
        if self._fail:
            prov = Provenance(adapter=self.spec.name, error="fake failure")
            return JobResult(JobStatus.FAILED, provenance=prov)
        prov = Provenance(adapter=self.spec.name, model=self.spec.model_id,
                          checkpoint=self.spec.checkpoint,
                          preprocessing_version=self.spec.preprocessing_version,
                          latency_ms=(time.perf_counter() - t0) * 1000.0,
                          device="cuda:0" if self.spec.resource is ResourceKind.GPU else "cpu")
        art = VisionArtifact(kind=self.spec.capability.value, data=self._output, provenance=prov)
        return JobResult(JobStatus.SUCCEEDED, artifact=art, provenance=prov)


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, Adapter] = {}
        self._specs: Dict[str, AdapterSpec] = {}

    def register_spec(self, spec: AdapterSpec) -> None:
        self._specs[spec.name] = spec

    def register(self, adapter: Adapter) -> None:
        self._adapters[adapter.spec.name] = adapter
        self._specs[adapter.spec.name] = adapter.spec

    def get(self, name: str) -> Optional[Adapter]:
        return self._adapters.get(name)

    def spec(self, name: str) -> Optional[AdapterSpec]:
        return self._specs.get(name)

    def names(self) -> List[str]:
        return list(self._specs)

    def by_capability(self, cap: Capability) -> List[str]:
        return [n for n, s in self._specs.items() if s.capability is cap]

    @classmethod
    def with_full_roster(cls) -> "AdapterRegistry":
        """A registry pre-loaded with every roster spec as deferred (no executables)."""
        reg = cls()
        for spec in default_roster():
            reg.register_spec(spec)
        return reg
