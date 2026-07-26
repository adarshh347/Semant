"""
CIRCUIT-001 WIRE-001 — real ActuatorRunners: the Director executes plans for real.

ORCH-001 built the executor (`execution.execute`) against a STUB registry. WIRE swaps the stubs
for runners that dispatch each step to the ACTUAL produce-field pipeline IN-PROCESS — the same
`_FIELD_PRODUCERS` handlers the `POST /{post_id}/produce-field` route calls, and the same
segmentation services `find_parts` runs — so a plan actually runs a model and leaves real
evidence behind. No HTTP round-trip to self.

TWO THINGS THE EXECUTOR ALREADY DOES, and this module relies on:
  - memory evolution: after an OK step, `execute` calls `memory.evolve(result.produced)` so a
    REGION produced by `find_parts` satisfies `material_field`'s REGION requirement at the GATE.
  - refusal propagation: a runner returning `status='unavailable'` (model down) flows through the
    existing skip logic untouched — WIRE adds no new refusal path.

THE BRIDGE THIS MODULE ADDS. The executor's memory advances resource COUNTS with projected ids;
the real region DATA (mask geometry) a downstream step must compute on travels in a shared
`ExecutionContext` the runners close over. `find_parts` appends its real regions to the context;
`material_field` reads one back and encodes it. That is what makes the two-step chain do work
rather than merely type-check.

DATA SAFETY (load-bearing). Executing a plan produces SUGGESTIONS into an in-memory quarantine
(`context.suggestions`) — `model_suggested` descriptors, exactly like the produce-field route
returns. Nothing here writes to `post_collection`; no region is committed, no mark is accepted,
`updated_at` is never touched. Surfacing and Accept are a later, supervised gate (SURFACE).

RESIDENCY. Every GPU producer already runs through `ModelManager` (single-GPU residency,
load→infer→unload per call). The runners drive them on ONE persistent event loop so the manager's
semaphores stay valid across steps and models load one at a time — the GPU returns to baseline
after each step, and after the whole plan.
"""
from __future__ import annotations

import asyncio
import importlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .capabilities import Actuator, Resource, get as get_actuator, known
from .execution import (ActuatorResult, EMPTY, ERROR, OK, UNAVAILABLE)
from .memory import WorkingMemory
from .plan import Step


# ── availability probes (capability string → is the runtime dependency up?) ────────────────────

def _svc(name: str):
    return importlib.import_module(f"backend.services.{name}")


def _capability_available(capability: Optional[str]) -> bool:
    """Is the runtime dependency this actuator names actually up?

    A capability of None is pure-python — always available. Everything else probes the real
    service's `is_available()`. A probe that raises is treated as DOWN (fail-closed), never as up.
    """
    if not capability:
        return True
    probes: Dict[str, Callable[[], bool]] = {
        "segmenter": lambda: _svc("segmentation_service").is_available()
                             or _svc("sam2_auto_service").is_available(),
        "dinov2": lambda: _svc("dinov2_service").is_available(),
        "depth": lambda: _svc("depth_service").is_available(),
        "intrinsic": lambda: _svc("intrinsic_service").is_available(),
        "grounding_detector": lambda: _svc("grounding_detector_service").is_available(),
        "semantic_provider": lambda: _semantic_available(),
    }
    probe = probes.get(capability)
    if probe is None:
        return False                                   # unknown capability → fail closed
    try:
        return bool(probe())
    except Exception:
        return False


def _semantic_available() -> bool:
    try:
        from backend.services.semantic_provider import SemanticProvider
        return bool(SemanticProvider().available())
    except Exception:
        return False


# ── residency: return the GPU to baseline after each GPU step ───────────────────────────────────
# A curator re-tapping ONE producer wants it resident (the produce-field route keeps it so). A PLAN
# moves to a DIFFERENT producer each step, so the opposite is right here: unload after each GPU step
# so only one model is ever resident and the card returns to baseline after the plan. Mirrors the
# canonical list in POST /{post_id}/produce-field/unload.
_GPU_CAPABILITIES = {"segmenter", "dinov2", "depth", "intrinsic", "grounding_detector"}
_GPU_UNLOAD_MODULES = (
    ("dinov2_vits14", "dinov2_service"), ("depth_anything_v2_small", "depth_service"),
    ("intrinsic_ordinal_shading", "intrinsic_service"), ("florence2_base", "florence2_service"),
    ("grounding_dino_tiny", "grounding_detector_service"), ("clip_vit_b32", "clip_presence_service"),
)


async def unload_models() -> List[str]:
    """Release every GPU field-producer model + the SAM2 refine session, then empty the cache.
    Idempotent — a model that was never loaded has nothing to release. Returns what it freed."""
    released: List[str] = []
    for name, mod in _GPU_UNLOAD_MODULES:
        try:
            _svc(mod).unload()
            released.append(name)
        except Exception:
            pass
    try:
        from backend.services.vision_orchestrator.refine_session import refine_session
        await refine_session.unload()
        released.append("sam21_hiera_tiny")
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    return released


# ── the execution context — the real-data bridge across steps ──────────────────────────────────

@dataclass
class ExecutionContext:
    """What the runners share across one plan run.

    `regions` is the real region DATA available to downstream steps — seeded with whatever the
    memory already knew about (committed regions) and extended by every `find_parts` step. This
    is the bridge the executor's count-only memory abstracts over: `material_field` reads a real
    region here, not the projected id memory carries.

    `suggestions` is the plan's OUTPUT — quarantined `model_suggested` descriptors, never marks.
    Nothing in this dataclass is ever written back to the database.
    """
    post_id: str
    post: Dict[str, Any]
    run_id: str = ""
    regions: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    log: List[Dict[str, Any]] = field(default_factory=list)
    loop: Any = None                                   # ONE persistent loop → residency stays sane
    _owns_loop: bool = False

    def __post_init__(self):
        if not self.run_id:
            self.run_id = f"wire::{uuid.uuid4().hex[:12]}"
        if self.loop is None:
            self.loop = asyncio.new_event_loop()
            self._owns_loop = True

    def close(self) -> None:
        if self._owns_loop and self.loop is not None:
            try:
                self.loop.close()
            except Exception:
                pass


# ── input resolution ───────────────────────────────────────────────────────────────────────────

def _requires_region(actuator: Actuator) -> bool:
    return any(r.kind is Resource.REGION for r in actuator.requires)


def _resolve_region(step: Step, ctx: ExecutionContext, actuator: Actuator) -> Optional[Dict[str, Any]]:
    """The region a step should work on.

    Prefers an explicit `region_id` param; otherwise the most recent real region in the context
    (the one a preceding `find_parts` just produced — the whole point of the chain). Returns None
    for image-only actuators, which read the whole frame."""
    rid = step.params.get("region_id")
    if rid:
        for r in ctx.regions:
            if str(r.get("id")) == str(rid):
                return r
    if not ctx.regions:
        return None
    if _requires_region(actuator):
        # the largest by area is the most likely "the part" a curator means; fall back to last.
        def _area(r):
            b = r.get("box") or {}
            try:
                return float(b.get("w", 0)) * float(b.get("h", 0))
            except (TypeError, ValueError):
                return 0.0
        return max(ctx.regions, key=_area)
    return None                                        # image-only actuator → whole frame


def _seed_point(step: Step, region: Optional[Dict[str, Any]]) -> Optional[List[float]]:
    """A normalized [x, y] tap for `material_field`. Explicit param wins; else the region's box
    centre (the honest default — where the curator most likely meant, the middle of the part)."""
    seed = step.params.get("seed_point")
    if isinstance(seed, (list, tuple)) and len(seed) == 2:
        return [float(seed[0]), float(seed[1])]
    box = (region or {}).get("box") or {}
    try:
        x, y, w, h = (float(box["x"]), float(box["y"]), float(box["w"]), float(box["h"]))
        return [x + w / 2.0, y + h / 2.0]
    except (KeyError, TypeError, ValueError):
        return None


# ── the runners ──────────────────────────────────────────────────────────────────────────────

async def _run_find_parts(step: Step, memory: WorkingMemory, ctx: ExecutionContext,
                          actuator: Actuator) -> ActuatorResult:
    """The default part proposer — YOLO general segmentation, quality-gated onto SAM2-auto (the
    same services the detect-regions route uses). Its regions feed downstream steps and are ALSO
    surfaced as quarantined region suggestions. Never written to `region_annotations`."""
    posts = importlib.import_module("backend.routers.posts")
    seg = _svc("segmentation_service")
    sam = _svc("sam2_auto_service")
    img_bytes = await posts._fetch_post_image_cached(ctx.post_id, ctx.post)

    regions = await asyncio.to_thread(seg.segment_image_bytes, img_bytes) or []
    if not sam.decomposition_adequate(regions) and sam.is_available():
        auto = await asyncio.to_thread(sam.generate_masks, img_bytes)
        if auto:
            regions = auto
    if not regions:
        return ActuatorResult(status=EMPTY, produced=(), model="yolo11n_seg+sam2_auto",
                              adapter="find_parts", detail="no parts found")

    ctx.regions.extend(regions)
    from backend.services import suggestion_service as ss
    for r in regions:
        sug = ss.suggestion_from_refine_region(r, run_id=ctx.run_id, model="segmenter",
                                               adapter="find_parts")
        if sug:
            ctx.suggestions.append(sug)
    return ActuatorResult(
        status=OK, produced=tuple([Resource.REGION] * len(regions)),
        model="yolo11n_seg+sam2_auto", adapter="find_parts", confidence=None,
        detail=f"proposed {len(regions)} region(s)", payload={"regions": len(regions)})


async def _run_field_producer(step: Step, memory: WorkingMemory, ctx: ExecutionContext,
                              actuator: Actuator) -> ActuatorResult:
    """Dispatch to the real `_FIELD_PRODUCERS` handler — the SAME function the produce-field route
    calls — and map its `(suggestions, status, ok)` onto an ActuatorResult. Suggestions land in the
    context's quarantine; nothing is committed."""
    posts = importlib.import_module("backend.routers.posts")
    handler = posts._FIELD_PRODUCERS.get(actuator.name)
    if handler is None:
        return ActuatorResult(status=UNAVAILABLE, produced=(), adapter=actuator.name,
                              detail=f"'{actuator.name}' is not a field producer")

    region = _resolve_region(step, ctx, actuator)
    req = posts.ProduceFieldRequest(
        producer=actuator.name,
        region_id=(region or {}).get("id"),
        seed_point=_seed_point(step, region),
        phrase=step.params.get("phrase"),
        params=dict(step.params or {}))

    suggestions, status, _ok = await handler(ctx.post_id, ctx.post, region, req, ctx.run_id)
    suggestions = list(suggestions or [])
    ctx.suggestions.extend(suggestions)
    return _result_from_producer(actuator, suggestions, status)


def _result_from_producer(actuator: Actuator, suggestions: List[Dict[str, Any]],
                          status: str) -> ActuatorResult:
    """Map a producer's `(suggestions, status)` to an ActuatorResult.

    'ready' → OK and the actuator's declared `produces` advances memory. 'empty' → EMPTY (ran,
    found nothing — leaves memory untouched, so a dependent step skips). 'unavailable' →
    UNAVAILABLE. The receipt (model/adapter/confidence) is lifted from the first suggestion's
    provenance so the chain record names what actually ran."""
    prov = (suggestions[0].get("provenance") if suggestions else {}) or {}
    model = prov.get("model")
    adapter = prov.get("adapter")
    confidence = suggestions[0].get("confidence") if suggestions else None
    if status == "ready" and suggestions:
        return ActuatorResult(status=OK, produced=tuple(actuator.produces), confidence=confidence,
                              model=model, adapter=adapter,
                              detail=f"produced {len(suggestions)} suggestion(s)")
    if status == "unavailable":
        return ActuatorResult(status=UNAVAILABLE, produced=(), model=model, adapter=adapter,
                              detail=f"'{actuator.name}' unavailable")
    return ActuatorResult(status=EMPTY, produced=(), model=model, adapter=adapter,
                          detail=f"'{actuator.name}' found nothing")


# actuator name → the async handler that runs it. Field producers share one handler; find_parts
# has its own (it calls segmentation, not a produce-field row). Actuators absent here have no
# in-process runner yet and report UNAVAILABLE — honest, and it flows through the skip logic.
_FIELD_PRODUCER_NAMES = (
    "negative_space", "material_field", "rhythm", "pressure_zone",
    "background_recession", "atmosphere_field", "light_field", "shadow_field",
    "grounded_sam_find_parts", "presence_check", "enumerate",
)
_DISPATCH: Dict[str, Callable] = {"find_parts": _run_find_parts}
for _n in _FIELD_PRODUCER_NAMES:
    _DISPATCH[_n] = _run_field_producer


class RealActuatorRunner:
    """One actuator, wired to its real in-process producer. Shares the `ActuatorRunner` shape
    (`(Step, WorkingMemory) → ActuatorResult`) with `StubActuator`, so `execute` cannot tell them
    apart. Synchronous like the protocol demands; it drives the async producer on the context's
    persistent loop."""

    def __init__(self, name: str, ctx: ExecutionContext):
        self.name = name
        self.ctx = ctx
        self.actuator = get_actuator(name)

    def __call__(self, step: Step, memory: WorkingMemory) -> ActuatorResult:
        act = self.actuator
        if act is None:
            return ActuatorResult(status=UNAVAILABLE, produced=(), adapter=self.name,
                                  detail=f"unknown actuator '{self.name}'")
        if not _capability_available(act.capability):
            return ActuatorResult(status=UNAVAILABLE, produced=(), model=act.capability,
                                  adapter=self.name, detail=f"{act.capability} unavailable")
        handler = _DISPATCH.get(self.name)
        if handler is None:
            return ActuatorResult(status=UNAVAILABLE, produced=(), adapter=self.name,
                                  detail=f"no in-process runner wired for '{self.name}'")

        async def _dispatch_then_unload() -> ActuatorResult:
            res = await handler(step, memory, self.ctx, act)
            # Single-GPU residency: a GPU step hands the card back before the next model loads,
            # so the chain never needs two resident at once and the card ends at baseline.
            if act.capability in _GPU_CAPABILITIES:
                await unload_models()
            return res

        try:
            return self.ctx.loop.run_until_complete(_dispatch_then_unload())
        except Exception as e:                          # a producer that throws is a failed step,
            return ActuatorResult(status=ERROR, produced=(), adapter=self.name,  # never a crash
                                  detail=f"{type(e).__name__}: {e}")


def real_registry(ctx: ExecutionContext) -> Dict[str, RealActuatorRunner]:
    """A real runner for every known actuator, all sharing one execution context. The drop-in
    replacement for `stub_registry()` — same keys, same `ActuatorRunner` shape."""
    return {name: RealActuatorRunner(name, ctx) for name in known()}


def run_plan(plan, memory: WorkingMemory, ctx: ExecutionContext):
    """Convenience: execute a resolved plan with real runners. Returns the ChainResult; the
    produced suggestions are in `ctx.suggestions`."""
    from .execution import execute
    return execute(plan, memory, real_registry(ctx), chain_id=ctx.run_id)
