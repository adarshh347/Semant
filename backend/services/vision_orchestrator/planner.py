"""
VISION-ORCHESTRATOR-001 — progressive multi-label planner.

Turns a domain-profile proposal into a VisionJob DAG (the job graph in the contract):
a fast orientation pass, selective domain passes only for chosen profiles, exact
refinement, then embeddings/semantics/analysis. Region-level routing is represented so
a full fashion parser and a full architecture parser do not both process every pixel.
The deep bundle computes a DINOv2 feature ONCE and fans it out to texture/pattern/
material consumers (the model-reuse rule), expressed as shared dependencies.

B1 wires this to fake adapters; the job kinds and adapter names are the real roster.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .contracts import Capability, DomainProfile, Priority, ResourceKind, VisionJob


def propose_profiles(scores: Dict[str, float], *, gate: float = 0.5,
                     router_version: str = "route-v1") -> DomainProfile:
    """Multi-label image-level route. `general` is always chosen; any domain above the
    gate joins it. The user may override upstream (persist chosen + router version)."""
    chosen = ["general"] + [k for k, v in scores.items() if k != "general" and v >= gate]
    labels = {"general": 1.0, **scores}
    return DomainProfile(labels=labels, chosen=chosen, router_version=router_version)


def build_plan(profile: DomainProfile, *, image_hash: str, geometry_rev: int = 0,
               deep: bool = False, refine: bool = False) -> List[VisionJob]:
    """Build the job DAG for the chosen profiles. Fast pass by default; `deep` adds the
    embeddings/semantic/analysis bundle; `refine` adds a MaskRefine job."""
    def ck(*parts) -> str:
        # cheap deterministic cache key stand-in for tests (real keys via cache.py)
        return "|".join(str(p) for p in ("v1", image_hash, geometry_rev, *parts))

    jobs: List[VisionJob] = []
    jobs.append(VisionJob(id="decode", kind="CanonicalDecode", resource=ResourceKind.CPU_LIGHT,
                          priority=Priority.FOREGROUND, cache_key=ck("decode")))
    jobs.append(VisionJob(id="cheap_signals", kind="CheapSignals", adapter="cpu_perceptual",
                          capability=Capability.PERCEPTUAL, resource=ResourceKind.CPU_LIGHT,
                          priority=Priority.FOREGROUND, deps=["decode"], cache_key=ck("cheap")))
    jobs.append(VisionJob(id="route", kind="DomainRoute", adapter="fashion_clip_router",
                          capability=Capability.DOMAIN_ROUTE, resource=ResourceKind.CPU,
                          priority=Priority.FOREGROUND, deps=["decode"], cache_key=ck("route")))
    jobs.append(VisionJob(id="general", kind="GeneralPropose", adapter="yolo11n_seg",
                          capability=Capability.SEGMENT, resource=ResourceKind.GPU,
                          priority=Priority.FOREGROUND, deps=["decode"], cache_key=ck("general")))

    domain_jobs: List[str] = []
    if "fashion" in profile.chosen:
        jobs.append(VisionJob(id="fashion", kind="FashionParse", adapter="fashionpedia_r50fpn",
                              capability=Capability.FASHION_PARSE, resource=ResourceKind.GPU,
                              priority=Priority.CONTINUATION, deps=["general"],
                              cache_key=ck("fashion")))
        domain_jobs.append("fashion")
    if "architecture" in profile.chosen:
        jobs.append(VisionJob(id="architecture", kind="ArchitectureParse", adapter="segformer_b0_ade",
                              capability=Capability.ARCH_PARSE, resource=ResourceKind.GPU,
                              priority=Priority.CONTINUATION, deps=["general"],
                              cache_key=ck("arch")))
        domain_jobs.append("architecture")
    if "painting" in profile.chosen:
        jobs.append(VisionJob(id="painting", kind="PaintingPropose", adapter="sam21_hiera_tiny",
                              capability=Capability.PAINTING_PROPOSE, resource=ResourceKind.GPU,
                              priority=Priority.CONTINUATION, deps=["general"],
                              cache_key=ck("painting")))
        domain_jobs.append("painting")

    jobs.append(VisionJob(id="merge", kind="CandidateMerge", resource=ResourceKind.CPU_LIGHT,
                          priority=Priority.CONTINUATION, deps=["general", *domain_jobs],
                          adapter=None, cache_key=ck("merge")))

    if refine:
        jobs.append(VisionJob(id="refine", kind="MaskRefine", adapter="sam21_hiera_tiny",
                              capability=Capability.MASK_REFINE, resource=ResourceKind.GPU,
                              priority=Priority.INTERACTIVE, deps=["merge"], cache_key=ck("refine")))

    if deep:
        # DINOv2 feature computed ONCE, fanned out to texture/pattern/material.
        jobs.append(VisionJob(id="dino", kind="DinoFeature", adapter="dinov2_vits14",
                              capability=Capability.FEATURE, resource=ResourceKind.GPU,
                              priority=Priority.BACKGROUND, deps=["decode"],
                              cache_key=ck("dino")))
        for consumer in ("texture", "pattern", "material"):
            jobs.append(VisionJob(id=consumer, kind=f"{consumer.title()}Analyze",
                                  adapter="cpu_perceptual", capability=Capability.PERCEPTUAL,
                                  resource=ResourceKind.CPU_LIGHT, priority=Priority.BACKGROUND,
                                  deps=["dino"], cache_key=ck(consumer)))
        jobs.append(VisionJob(id="embed", kind="Embeddings", adapter="fashion_clip",
                              capability=Capability.EMBED, resource=ResourceKind.CPU,
                              priority=Priority.BACKGROUND, deps=["merge"], cache_key=ck("embed")))
        jobs.append(VisionJob(id="semantic", kind="SemanticAnnotate", adapter="cloud_vlm",
                              capability=Capability.SEMANTIC_ANNOTATE, resource=ResourceKind.REMOTE,
                              priority=Priority.BACKGROUND, deps=["merge"], cache_key=ck("semantic")))
    return jobs
