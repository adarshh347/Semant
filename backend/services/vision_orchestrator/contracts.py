"""
VISION-ORCHESTRATOR-001 — typed contracts.

Narrow, dependency-free dataclasses/enums shared by the registry, model manager,
scheduler, planner and cache. No model or torch import here — the orchestrator layer
stays importable in a slim deploy and unit-testable with fake adapters.

Geometry note: adapters that produce masks emit them as canonical RLE (Increment A's
`mask_geometry`); this layer never defines a second geometry representation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Sequence


class Capability(str, Enum):
    """What an adapter answers — one row-family of VISION-MODEL-MATRIX-001."""
    SEGMENT = "segment"                 # general instance masks (YOLO)
    MASK_REFINE = "mask_refine"         # exact refinement from prompts (SAM2)
    FASHION_PARSE = "fashion_parse"     # garments/parts/attributes (Fashionpedia)
    ARCH_PARSE = "arch_parse"           # architecture/interior surfaces (SegFormer-ADE)
    PAINTING_PROPOSE = "painting_propose"
    DOMAIN_ROUTE = "domain_route"       # multi-label profile proposal (FashionCLIP)
    EMBED = "embed"                     # region/image embeddings (FashionCLIP/DINO/CLIP)
    FEATURE = "feature"                 # reusable patch features (DINOv2) — fanned out
    SEMANTIC_ANNOTATE = "semantic_annotate"   # cloud VLM — never authors geometry
    PERCEPTUAL = "perceptual"           # CPU colour/edge/texture/pattern analyzers
    DEPTH = "depth"                     # relative depth (Depth-Anything)


class ResourceKind(str, Enum):
    GPU = "gpu"            # one heavy job at a time
    CPU = "cpu"            # heavy CPU inference — begins at concurrency 1
    CPU_LIGHT = "cpu_light"  # colour/geometry operators — bounded pool of 2
    REMOTE = "remote"     # cloud VLM — 1 per image, deduplicated


class Priority(IntEnum):
    """Lower runs first. Interactive can preempt queued Background at job boundaries."""
    INTERACTIVE = 0     # click-to-refine, selected label, recall
    FOREGROUND = 1      # user asked Dissect/Analyze
    CONTINUATION = 2    # remaining jobs for the open image
    BACKGROUND = 3      # embeddings, backfills, indexing


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"   # adapter deferred / not installed
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_terminal_ok(self) -> bool:
        return self in (JobStatus.SUCCEEDED, JobStatus.PARTIAL)


@dataclass
class Provenance:
    """The observability record VISION-BUILD-001 requires on every inference result."""
    adapter: str
    model: Optional[str] = None
    checkpoint: Optional[str] = None
    preprocessing_version: Optional[str] = None
    input_size: Optional[Sequence[int]] = None
    device: Optional[str] = None
    dtype: Optional[str] = None
    latency_ms: Optional[float] = None
    load_ms: Optional[float] = None
    peak_vram_mib: Optional[float] = None
    confidence: Optional[float] = None
    geometry_rev: Optional[int] = None
    from_cache: bool = False
    fallbacks: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], False)} \
            or {"adapter": self.adapter}


@dataclass
class VisionArtifact:
    """An immutable adapter output. `kind` names the artifact class; `data` is opaque
    to the orchestrator (masks travel as RLE, features as vectors, etc.)."""
    kind: str
    data: Any
    provenance: Provenance


@dataclass
class JobResult:
    status: JobStatus
    artifact: Optional[VisionArtifact] = None
    provenance: Optional[Provenance] = None
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return self.status.is_terminal_ok


@dataclass
class AdapterSpec:
    """Static description of a roster entry (VISION-MODEL-MATRIX-001)."""
    name: str
    capability: Capability
    resource: ResourceKind
    model_id: str
    checkpoint: Optional[str] = None
    preprocessing_version: str = "v1"
    license: Optional[str] = None
    available: bool = False          # False → deferred/not installed (fake in B1)
    deferred: bool = True            # architectural placeholder for the roster
    shares_feature: Optional[str] = None  # e.g. a DINO consumer names the feature adapter


@dataclass
class DomainProfile:
    """Multi-label image-level route (VISION-ORCHESTRATOR-001). `chosen` may be user
    overridden; both the proposal and the router version are persisted upstream."""
    labels: Dict[str, float]
    chosen: List[str]
    router_version: str = "route-v1"
    user_overridden: bool = False


@dataclass
class VisionJob:
    id: str
    kind: str
    capability: Optional[Capability] = None
    adapter: Optional[str] = None
    resource: ResourceKind = ResourceKind.CPU_LIGHT
    priority: Priority = Priority.CONTINUATION
    deps: List[str] = field(default_factory=list)
    cache_key: Optional[str] = None
    timeout_s: Optional[float] = None
    estimated_cost: float = 1.0
    payload: Dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING


class CancelToken:
    """Cooperative cancellation. Jobs check `.cancelled` at boundaries; a running GPU
    kernel is never interrupted mid-flight (cancel takes effect at the next boundary)."""
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled
