"""
VISION-ORCHESTRATOR-001 — progressive multi-model orchestration (skeleton, B1).

Current-model-only execution; the registry/planner nonetheless model the complete
VISION-MODEL-MATRIX-001 roster as deferred adapters. Adapter masks always enter through
Increment A's canonical `mask_geometry` — this layer defines no second geometry contract.
"""
from .contracts import (AdapterSpec, Capability, CancelToken, DomainProfile, JobResult,
                        JobStatus, Priority, Provenance, ResourceKind, VisionArtifact,
                        VisionJob)
from .cache import (ResultCache, CacheStats, image_key, feature_key, analysis_key,
                    embedding_key, semantic_key)
from .registry import Adapter, AdapterRegistry, AdapterSpec as _Spec, FakeAdapter, default_roster
from .manager import ModelManager, Scheduler, PriorityResource, Telemetry
from .planner import propose_profiles, build_plan

__all__ = [
    "Capability", "ResourceKind", "Priority", "JobStatus", "Provenance", "VisionArtifact",
    "JobResult", "AdapterSpec", "DomainProfile", "VisionJob", "CancelToken",
    "ResultCache", "CacheStats", "image_key", "feature_key", "analysis_key",
    "embedding_key", "semantic_key",
    "Adapter", "AdapterRegistry", "FakeAdapter", "default_roster",
    "ModelManager", "Scheduler", "PriorityResource", "Telemetry",
    "propose_profiles", "build_plan",
]
