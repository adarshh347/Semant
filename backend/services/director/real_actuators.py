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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
        # M6 — the library, not a model. Available means "a provider is configured and its
        # client library imports", never a live reachability probe: a network round trip in
        # front of every plan would make availability the slowest question the planner asks.
        "external_source": lambda: _svc("external_source_service").default_provider().is_available(),
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
# WIRE-002: the hand-maintained list is GONE. It was wrong four times running — DINOv2-only,
# then SAM2's refine_session, then CLIP, and most recently sam2_auto_service (which `find_parts`
# calls on every plan) plus perspective_service. `model_residency` discovers every service holding
# a model instead of remembering them, so a newly-wired GPU producer is released with no edit here.
async def unload_models() -> List[str]:
    """Release every model this process could be holding, via the discovery registry.
    Idempotent — a service that never loaded has nothing to free. Returns what it freed."""
    from backend.services import model_residency
    return await model_residency.release_all()


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
    # Each region is ALSO a quarantined region_mask suggestion, so the packet advances on both
    # axes — this is what lets compose_percept/connect_marks follow find_parts in one chain.
    return ActuatorResult(
        status=OK,
        produced=tuple([Resource.REGION] * len(regions) + [Resource.MARK] * len(regions)),
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



# ── WIRE-002: the four remaining actuators ─────────────────────────────────────────────────────
# WIRE-001 wired the pixel producers — the ones that read the image. These four read the EVIDENCE
# instead: what has been gathered, and what it means together. That is why they come last and why
# they are the ones that make a rich plan possible: a chain is only interesting when a later step
# consumes what an earlier one produced.


def _llm_available() -> bool:
    """Groq, for the two actuators that need language. Declared capability is None for these
    (they author no pixels), so availability is probed here rather than by `_capability_available`."""
    try:
        from backend.config import settings
        return bool(getattr(settings, "GROQ_API_KEY", None))
    except Exception:
        return False


def _quarantined_marks(ctx: "ExecutionContext") -> List[Dict[str, Any]]:
    """Suggestions produced SO FAR in this plan that are real marks (not readings).

    This is the real-data bridge for evidence, exactly as `ctx.regions` is for geometry: working
    memory carries counts, and a step that must actually cite two marks needs the marks.

    M6 makes this allowlist load-bearing rather than merely tidy. It names the four MARK types,
    so a `sourced_statement` sitting in the same quarantine is invisible to `connect_marks` and
    `compose_percept`: a plan cannot relate a citation to a mask, and a percept cannot come to
    rest on a quotation. An allowlist and not a denylist, so a type added later is excluded
    until someone decides otherwise — the safe direction to fail."""
    return [s for s in ctx.suggestions
            if isinstance(s, dict) and s.get("type") in ("region_mask", "brush_field",
                                                         "trace_mark", "relation_mark")]


# ── CIRCUIT-003 M1 — the cross-image bridge ────────────────────────────────────────────────────
# The corpus counterpart of `_quarantined_marks`. A corpus execution context (see
# `corpus_execution.py`) holds one per-image context per image and answers `marks_by_image()`.
#
# DUCK-TYPED, not imported. `corpus_execution` imports THIS module for `ExecutionContext`, so a
# type import in the other direction would be a cycle. More to the point, the runners below have
# no business knowing what a corpus is: they need "marks, grouped by which picture they are on",
# and a single-post context can answer that too — with one group, which is exactly why they refuse
# honestly instead of degrading into a same-image relation.

def _marks_by_image(ctx: "ExecutionContext") -> Dict[str, List[Dict[str, Any]]]:
    """Quarantined marks grouped by the image they were produced on, in corpus order.

    A plain single-post context yields ONE group. That is not a special case to work around; it is
    the fact that makes `compare_views` on a single post return EMPTY with a reason a curator can
    act on, rather than relating a picture to itself and calling it a comparison."""
    grouped = getattr(ctx, "marks_by_image", None)
    if callable(grouped):
        return grouped()
    return {ctx.post_id: _quarantined_marks(ctx)}


def _mark_ref(mark: Dict[str, Any]) -> str:
    return str(mark.get("source_ref") or mark.get("id") or "")


def _image_ref_for(ctx: "ExecutionContext", post_id: str) -> str:
    """The image_ref a corpus context knows for a post, or the post id. Provenance names both, so
    a source stays identifiable after the post document has moved on."""
    lookup = getattr(ctx, "image_ref_for", None)
    if callable(lookup):
        return str(lookup(post_id) or post_id)
    return str((ctx.post or {}).get("photo_url") or post_id)


def _source(ctx: "ExecutionContext", post_id: str, mark: Dict[str, Any],
            position: Optional[int]) -> Dict[str, Any]:
    """One side of a cross-image claim, fully identified.

    Everything needed to go BACK to the evidence: which post, which image, which mark, and where
    the image stood in the sequence. A comparative percept whose provenance named only the marks
    would be uncheckable the moment two images carried marks with the same local id — which, since
    ids are minted per post, is the normal case rather than the edge one."""
    return {"post_id": post_id, "image_ref": _image_ref_for(ctx, post_id),
            "mark_ref": _mark_ref(mark), "label": mark.get("label") or mark.get("role"),
            "position": position}


def _corpus_positions(ctx: "ExecutionContext") -> Dict[str, int]:
    corpus = getattr(ctx, "corpus", None)
    images = getattr(corpus, "images", ()) or ()
    return {str(i.post_id): int(i.position) for i in images}


def _pick_across_images(step: Step, by_image: Dict[str, List[Dict[str, Any]]]
                        ) -> Optional[Tuple[Tuple[str, Dict[str, Any]], Tuple[str, Dict[str, Any]]]]:
    """Two marks on two DIFFERENT images: explicit `left_ref`/`right_ref` if given, else one from
    each of the first two images that actually carry marks, in corpus order.

    Returns None when fewer than two images have marks — never a same-image pair as a consolation.
    """
    populated = [(pid, marks) for pid, marks in by_image.items() if marks]
    explicit = {}
    for side in ("left_ref", "right_ref"):
        ref = str((step.params or {}).get(side) or "").strip()
        if not ref:
            continue
        for pid, marks in populated:
            found = next((m for m in marks if _mark_ref(m) == ref), None)
            if found is not None:
                explicit[side] = (pid, found)
                break
    left = explicit.get("left_ref")
    right = explicit.get("right_ref")
    if left and right and left[0] != right[0]:
        return left, right
    if len(populated) < 2:
        return None
    if left:
        other = next(((pid, marks[-1]) for pid, marks in populated if pid != left[0]), None)
        return (left, other) if other else None
    if right:
        other = next(((pid, marks[-1]) for pid, marks in populated if pid != right[0]), None)
        return (other, right) if other else None
    (pid_a, marks_a), (pid_b, marks_b) = populated[0], populated[1]
    return (pid_a, marks_a[-1]), (pid_b, marks_b[-1])


async def _name_relation(a_label: Any, b_label: Any, a_image: str, b_image: str
                         ) -> Tuple[str, Optional[str]]:
    """Ask the language model to name a CROSS-IMAGE relation. Returns (text, model) and never
    raises — a failed naming is not a failed relation, exactly as in `_run_connect_marks`."""
    if not _llm_available():
        return "", None
    try:
        llm = _svc("llm_service").LLMService()
        prompt = (f'Two visual marks, each on a DIFFERENT photograph of the same sequence: '
                  f'"{a_label}" (on {a_image}) and "{b_label}" (on {b_image}). In ONE short '
                  f'phrase, name the relation BETWEEN THE TWO VIEWS. Do not describe either '
                  f'alone. JSON: {{"relation": "..."}}')
        out = await asyncio.to_thread(
            lambda: llm.client.chat.completions.create(
                messages=[{"role": "system", "content": "You output JSON."},
                          {"role": "user", "content": prompt}],
                model=llm.model, response_format={"type": "json_object"}))
        import json as _json
        return (_json.loads(out.choices[0].message.content) or {}).get("relation", ""), llm.model
    except Exception:
        return "", None


async def _run_compare_views(step: Step, memory: WorkingMemory, ctx: "ExecutionContext",
                             actuator: Actuator) -> ActuatorResult:
    """Name the relation between two marks on two DIFFERENT images (CIRCUIT-003 M1).

    `connect_marks`' cross-image sibling. Two things make it a different act rather than a wider
    one, and both are load-bearing:

      IT REFUSES ON ONE IMAGE. `resolve()` already proved two images would be present; this proves
      two images DO carry marks at the moment of dispatch, and those differ exactly when one
      image's finder came back empty. Falling back to a same-image pair there would produce a
      well-formed relation that answers a question nobody asked — the precise failure the chain
      honesty rules exist to prevent.

      IT TRACES BOTH SOURCES. `provenance.sources` carries post id, image ref, mark ref and
      sequence position for EACH side. A cross-image claim that cannot say which pictures it
      spans is not checkable, and an uncheckable comparison is the article's whole risk.
    """
    by_image = _marks_by_image(ctx)
    populated = {pid: ms for pid, ms in by_image.items() if ms}
    if len(populated) < 2:
        return ActuatorResult(status=EMPTY, produced=(), adapter="compare_views",
                              detail=(f"needs marks on 2 images; {len(populated)} image(s) "
                                      f"carry any"))
    pair = _pick_across_images(step, by_image)
    if pair is None:
        return ActuatorResult(status=EMPTY, produced=(), adapter="compare_views",
                              detail="no two marks on two different images")
    (pid_a, mark_a), (pid_b, mark_b) = pair

    positions = _corpus_positions(ctx)
    src_a = _source(ctx, pid_a, mark_a, positions.get(pid_a))
    src_b = _source(ctx, pid_b, mark_b, positions.get(pid_b))

    role_hint = (step.params or {}).get("relation_role")
    relation_text = role_hint or ""
    model_name = None
    if not relation_text:
        relation_text, model_name = await _name_relation(
            mark_a.get("label") or mark_a.get("role"), mark_b.get("label") or mark_b.get("role"),
            src_a["image_ref"], src_b["image_ref"])

    from backend.services import suggestion_service as ss
    role = ss.relation_role_for(relation_text)
    left = f"{pid_a}:{src_a['mark_ref']}"
    right = f"{pid_b}:{src_b['mark_ref']}"
    sug = {
        "producer": "semantic_read",           # the frozen producer vocabulary's relation minter
        "type": "relation_mark",
        "role": role,
        "label": relation_text or role.replace("_", " "),
        "source_ref": f"{left}→{right}",
        # Endpoints stay STRINGS, like `connect_marks`' — post-qualified so nothing that already
        # reads endpoints has to learn a new shape to keep working.
        "geometry": {"kind": "derived", "endpoints": [left, right], "cross_image": True},
        "linked_ground_ids": [],
        "corpus": {"corpus_id": getattr(getattr(ctx, "corpus", None), "corpus_id", None),
                   "spans": [pid_a, pid_b]},
        "provenance": {"run_id": ctx.run_id, "producer": "compare_views",
                       "adapter": "compare_views", "sources": [src_a, src_b],
                       **({"model": model_name} if model_name else {})},
    }
    _record_comparative(ctx, sug)
    return ActuatorResult(status=OK, produced=tuple(actuator.produces), model=model_name,
                          adapter="compare_views",
                          detail=f"related '{role}' across {pid_a} and {pid_b}")


async def _run_compose_comparative_percept(step: Step, memory: WorkingMemory,
                                           ctx: "ExecutionContext",
                                           actuator: Actuator) -> ActuatorResult:
    """Draft a percept that rests on a NAMED comparison across two images.

    The single-image `compose_percept` rests on marks; this rests on a cross-image relation, and
    refuses without one. That refusal is the point: a sentence about two photographs that was not
    grounded in a relation somebody actually named would be a comparison in grammar only, and it
    would look identical to one that was earned.
    """
    relations = [s for s in _comparative_relations(ctx)
                 if len(((s.get("corpus") or {}).get("spans") or [])) >= 2]
    if not relations:
        return ActuatorResult(status=EMPTY, produced=(), adapter="compose_comparative_percept",
                              detail="no cross-image relation to rest on")
    relation = relations[-1]
    sources = list((relation.get("provenance") or {}).get("sources") or [])
    spans = list((relation.get("corpus") or {}).get("spans") or [])

    draft = (step.params or {}).get("draft_text") or ""
    model_name = None
    if not draft and _llm_available():
        try:
            llm = _svc("llm_service").LLMService()
            model_name = llm.model
            left = sources[0] if sources else {}
            right = sources[1] if len(sources) > 1 else {}
            prompt = (f'A curator relating two photographs of one sequence named this relation: '
                      f'"{relation.get("label")}". It joins "{left.get("label")}" on the view '
                      f'"{left.get("image_ref")}" to "{right.get("label")}" on the view '
                      f'"{right.get("image_ref")}". Write ONE sentence of close reading about '
                      f'what the two views do TOGETHER. Claim nothing you cannot see in either. '
                      f'JSON: {{"percept": "..."}}')
            out = await asyncio.to_thread(
                lambda: llm.client.chat.completions.create(
                    messages=[{"role": "system", "content": "You output JSON."},
                              {"role": "user", "content": prompt}],
                    model=llm.model, response_format={"type": "json_object"}))
            import json as _json
            draft = (_json.loads(out.choices[0].message.content) or {}).get("percept", "")
        except Exception:
            draft = ""
    if not draft:
        return ActuatorResult(status=UNAVAILABLE, produced=(),
                              adapter="compose_comparative_percept",
                              detail="no draft available (language model unavailable)")

    sug = {
        "producer": "planner",
        "type": "percept_draft",
        "role": None,
        "label": draft[:120],
        "draft_text": draft,
        "source_ref": f"{ctx.run_id}:comparative_percept:{len(spans)}",
        # What it rests on: the named relation, and each side's mark. Post-qualified, so a reader
        # of the percept can reach every piece of evidence without guessing which image it is on.
        "ground_refs": [relation.get("source_ref")] + [
            f"{s.get('post_id')}:{s.get('mark_ref')}" for s in sources if s.get("mark_ref")],
        "geometry": None,                      # a percept has no extent — it rests on ones that do
        "linked_ground_ids": [],
        "corpus": {"corpus_id": (relation.get("corpus") or {}).get("corpus_id"),
                   "spans": spans},
        "provenance": {"run_id": ctx.run_id, "producer": "compose_comparative_percept",
                       "adapter": "compose_comparative_percept",
                       "rests_on": relation.get("source_ref"),
                       "sources": sources,
                       **({"model": model_name} if model_name else {})},
    }
    _record_comparative(ctx, sug)
    return ActuatorResult(status=OK, produced=tuple(actuator.produces), model=model_name,
                          adapter="compose_comparative_percept",
                          detail=f"drafted across {len(spans)} image(s)")


def _record_comparative(ctx: "ExecutionContext", suggestion: Dict[str, Any]) -> None:
    """Where a cross-image suggestion lands.

    A corpus context keeps comparative suggestions in their OWN quarantine rather than on any one
    image's pile — a relation that spans the façade and the rotunda belongs to neither post, and
    filing it under one of them would make it look, to every later reader, like evidence found
    there. A plain context has nowhere else to put it, so it goes on the pile with everything
    else and stays honest by carrying its `spans` list."""
    sink = getattr(ctx, "record_comparative", None)
    if callable(sink):
        sink(suggestion)
        return
    ctx.suggestions.append(suggestion)


def _comparative_relations(ctx: "ExecutionContext") -> List[Dict[str, Any]]:
    """Cross-image relations produced SO FAR in this run — the evidence a comparative percept
    must rest on."""
    pool = getattr(ctx, "comparative", None)
    items = list(pool) if isinstance(pool, list) else list(ctx.suggestions)
    return [s for s in items
            if isinstance(s, dict) and s.get("type") == "relation_mark"
            and bool((s.get("geometry") or {}).get("cross_image"))]


async def _run_semantic_read(step: Step, memory: WorkingMemory, ctx: "ExecutionContext",
                             actuator: Actuator) -> ActuatorResult:
    """The cloud VLM reads what has been gathered. Never authors geometry (schema-forbidden);
    every assertion is bound to a region id that already exists, and one about an unknown id is
    dropped rather than honoured."""
    import base64
    posts = importlib.import_module("backend.routers.posts")
    sp = _svc("semantic_provider")
    provider = sp.SemanticProvider()
    if not provider.available():
        return ActuatorResult(status=UNAVAILABLE, produced=(), adapter="semantic_read",
                              detail=f"semantic provider unavailable: {provider.state().get('reason')}")

    regions = list(ctx.regions or [])
    if not regions:
        return ActuatorResult(status=EMPTY, produced=(), adapter="semantic_read",
                              detail="no regions to read")
    allowed = [str(r.get("id")) for r in regions if r.get("id")]
    img_bytes = await posts._fetch_post_image_cached(ctx.post_id, ctx.post)
    b64 = base64.b64encode(img_bytes).decode("ascii")
    question = (step.params or {}).get("question") or "What is here, and how do these parts relate?"

    result = await asyncio.to_thread(
        provider.interpret, image_b64=b64, allowed_ids=allowed, prompt=question)
    payload = result.as_dict() if hasattr(result, "as_dict") else {}
    if payload.get("status") not in ("ok", "succeeded", "success"):
        # A degraded provider is UNAVAILABLE, never a silent empty reading.
        return ActuatorResult(status=UNAVAILABLE, produced=(), adapter="semantic_read",
                              model=getattr(provider, "model", None),
                              detail=f"semantic read {payload.get('status')}")

    from backend.services import suggestion_service as ss
    sugs = ss.suggestions_from_semantics(payload.get("response") or payload,
                                         run_id=ctx.run_id) or []
    ctx.suggestions.extend(sugs)
    if not sugs:
        return ActuatorResult(status=EMPTY, produced=(), adapter="semantic_read",
                              model=getattr(provider, "model", None),
                              detail="read returned nothing citable")
    return ActuatorResult(status=OK, produced=tuple(actuator.produces),
                          model=getattr(provider, "model", None), adapter="semantic_read",
                          detail=f"read {len(sugs)} assertion(s)")


async def _run_find_similar(step: Step, memory: WorkingMemory, ctx: "ExecutionContext",
                            actuator: Actuator) -> ActuatorResult:
    """DINOv2 neighbours for a seed region, as CROSS-POST references.

    Each neighbour becomes a `region_ref` pointing across the border — a reference with receipts,
    never a copy of the neighbour's pixels. Produces MARKs, which is what lets `connect_marks`
    become satisfiable in a chain that started with nothing but an image."""
    posts = importlib.import_module("backend.routers.posts")
    fss = _svc("find_similar_service")
    res_svc = _svc("region_embedding_service")
    retrieval = _svc("retrieval_service")

    seed_id = (step.params or {}).get("seed_mark_id")
    region = None
    if seed_id:
        region = next((r for r in ctx.regions if str(r.get("id")) == str(seed_id)), None)
    if region is None:
        region = ctx.regions[0] if ctx.regions else None
    if region is None or not region.get("id"):
        return ActuatorResult(status=EMPTY, produced=(), adapter="find_similar",
                              detail="no seed region to match against")

    img_bytes = await posts._fetch_post_image_cached(ctx.post_id, ctx.post)
    # `find_similar_for_region` resolves its seed out of the POST's region_annotations, but the
    # regions `find_parts` proposed live only in ctx.regions — WIRE never writes them to the post,
    # by design. Without this the chain could only ever match against parts a curator had already
    # committed, which defeats "find the motif and its echoes" on a fresh image.
    #
    # So it gets a SHALLOW COPY of the post carrying the proposed regions. ctx.post is not
    # mutated, nothing is persisted, and the copy dies with the step.
    seed_post = dict(ctx.post)
    seed_post["region_annotations"] = list(ctx.post.get("region_annotations") or []) + list(ctx.regions)
    try:
        domain = fss._domain_of(seed_post)
        routed = retrieval.route(query_kind="evidence", domain=domain, context_sensitive=False)
        model = retrieval._SPACES[routed["space"]]["model"]
        scope = list(await res_svc.region_embeddings_collection.distinct("post_id", {"model": model}))
        if ctx.post_id not in scope:
            scope.append(ctx.post_id)
    except Exception as e:
        return ActuatorResult(status=UNAVAILABLE, produced=(), adapter="find_similar",
                              detail=f"retrieval scope unavailable: {type(e).__name__}")

    result = await fss.find_similar_for_region(
        seed_post, str(region["id"]), img_bytes, mode="identity", top_k=int(
            (step.params or {}).get("top_k") or 6),
        exclude_self_post=False, reindex=False, scope_post_ids=scope)

    from backend.services import suggestion_service as ss
    sugs = ss.suggestions_from_similar(result, run_id=ctx.run_id) or []
    ctx.suggestions.extend(sugs)
    status = (result or {}).get("status")
    if status in ("error", "unavailable"):
        return ActuatorResult(status=UNAVAILABLE, produced=(), adapter="find_similar",
                              model="dinov2_vits14", detail=f"find_similar {status}")
    if not sugs:
        return ActuatorResult(status=EMPTY, produced=(), adapter="find_similar",
                              model="dinov2_vits14", detail="no neighbours found")
    return ActuatorResult(status=OK, produced=tuple(Resource.MARK for _ in sugs),
                          model="dinov2_vits14", adapter="find_similar",
                          detail=f"found {len(sugs)} neighbour(s)")


async def _run_connect_marks(step: Step, memory: WorkingMemory, ctx: "ExecutionContext",
                             actuator: Actuator) -> ActuatorResult:
    """Name the relation between two gathered marks. DINOv2 gathered them; Groq names the kind.

    Refuses on fewer than two marks even though `resolve()` already checked the COUNT — the plan
    proved two marks would exist, this proves two marks DO exist, and those differ exactly when an
    upstream step returned empty. The relation_role is mapped through the frozen vocabulary, so a
    model that invents a relation name cannot put an unknown role on a mark."""
    marks = _quarantined_marks(ctx)
    if len(marks) < 2:
        return ActuatorResult(status=EMPTY, produced=(), adapter="connect_marks",
                              detail=f"needs 2 marks, {len(marks)} available")

    a, b = marks[-2], marks[-1]
    role_hint = (step.params or {}).get("relation_role")
    model_name = None
    relation_text = role_hint or ""
    if not relation_text and _llm_available():
        try:
            llm = _svc("llm_service").LLMService()
            model_name = llm.model
            prompt = (f'Two visual marks on one image: "{a.get("label") or a.get("role")}" and '
                      f'"{b.get("label") or b.get("role")}". In ONE short phrase, name the '
                      f'relation between them. JSON: {{"relation": "..."}}')
            out = await asyncio.to_thread(
                lambda: llm.client.chat.completions.create(
                    messages=[{"role": "system", "content": "You output JSON."},
                              {"role": "user", "content": prompt}],
                    model=llm.model, response_format={"type": "json_object"}))
            import json as _json
            relation_text = (_json.loads(out.choices[0].message.content) or {}).get("relation", "")
        except Exception:
            relation_text = ""                 # a failed naming is not a failed relation

    from backend.services import suggestion_service as ss
    role = ss.relation_role_for(relation_text)
    sug = {
        "producer": "semantic_read",           # the frozen producer vocabulary's relation minter
        "type": "relation_mark",
        "role": role,
        "label": relation_text or role.replace("_", " "),
        "source_ref": f"{a.get('source_ref') or a.get('id')}→{b.get('source_ref') or b.get('id')}",
        "geometry": {"kind": "derived", "endpoints": [a.get("source_ref"), b.get("source_ref")]},
        "linked_ground_ids": [],
        "provenance": {"run_id": ctx.run_id, "producer": "connect_marks",
                       "adapter": "connect_marks", **({"model": model_name} if model_name else {})},
    }
    from backend.services import epistemics
    epistemics.stamp(sug)                      # interpretive: a named relation is a reading
    ctx.suggestions.append(sug)
    return ActuatorResult(status=OK, produced=tuple(actuator.produces), model=model_name,
                          adapter="connect_marks", detail=f"related as '{role}'")


async def _run_compose_percept(step: Step, memory: WorkingMemory, ctx: "ExecutionContext",
                               actuator: Actuator) -> ActuatorResult:
    """Draft a percept that RESTS ON the marks gathered so far.

    The draft is a proposal, never a commitment: it enters the same quarantine as every other
    suggestion and a curator writes the real sentence. `ground_refs` names what it rests on, so a
    percept resting on two marks cannot later be mistaken for one resting on five."""
    marks = _quarantined_marks(ctx)
    if not marks:
        return ActuatorResult(status=EMPTY, produced=(), adapter="compose_percept",
                              detail="nothing gathered to compose from")

    draft = (step.params or {}).get("draft_text") or ""
    model_name = None
    if not draft and _llm_available():
        try:
            llm = _svc("llm_service").LLMService()
            model_name = llm.model
            names = ", ".join(str(m.get("label") or m.get("role")) for m in marks[:6])
            prompt = (f"A curator gathered these marks on one image: {names}. Write ONE sentence "
                      f"of close reading that rests only on them. Claim nothing you cannot see. "
                      f'JSON: {{"percept": "..."}}')
            out = await asyncio.to_thread(
                lambda: llm.client.chat.completions.create(
                    messages=[{"role": "system", "content": "You output JSON."},
                              {"role": "user", "content": prompt}],
                    model=llm.model, response_format={"type": "json_object"}))
            import json as _json
            draft = (_json.loads(out.choices[0].message.content) or {}).get("percept", "")
        except Exception:
            draft = ""
    if not draft:
        return ActuatorResult(status=UNAVAILABLE, produced=(), adapter="compose_percept",
                              detail="no draft available (language model unavailable)")

    sug = {
        "producer": "planner",
        "type": "percept_draft",
        "role": None,
        "label": draft[:120],
        "draft_text": draft,
        "source_ref": f"{ctx.run_id}:percept:{len(ctx.suggestions)}",
        "ground_refs": [m.get("source_ref") for m in marks if m.get("source_ref")],
        "geometry": None,                      # a percept has no extent — it rests on ones that do
        "linked_ground_ids": [],
        "provenance": {"run_id": ctx.run_id, "producer": "compose_percept",
                       "adapter": "compose_percept",
                       **({"model": model_name} if model_name else {})},
    }
    from backend.services import epistemics
    epistemics.stamp(sug)                      # interpretive: a draft percept is a reading
    ctx.suggestions.append(sug)
    return ActuatorResult(status=OK, produced=tuple(actuator.produces), model=model_name,
                          adapter="compose_percept", detail=f"drafted from {len(marks)} mark(s)")


async def _run_historical_source(step: Step, memory: WorkingMemory, ctx: "ExecutionContext",
                                 actuator: Actuator) -> ActuatorResult:
    """CIRCUIT-003 M6 — retrieve what is DOCUMENTED about a topic, and quarantine it as sourced.

    The one runner in this module that never touches `ctx.post` or the image bytes. It cannot:
    the whole point of the actuator is that its answer comes from somewhere the picture is not,
    and a runner holding the image would eventually be tempted to check its claims against it —
    which is precisely the laundering the `sourced` status exists to prevent.

    Three outcomes, mapped to the executor's existing vocabulary rather than a new one:
      UNAVAILABLE — no provider, or the lookup failed. Retry is sensible.
      EMPTY       — searched, found nothing citable. An honest answer; retry is not sensible.
      OK          — statements, each carrying a citation that was checked before it got here.

    `epistemics.guard()` runs on the descriptors before they enter the quarantine. It is
    redundant here by construction — `to_descriptor()` is the only thing that built them and it
    always writes `sourced` — and it is called anyway, because the day someone adds a second
    path into this list is the day redundant becomes load-bearing.
    """
    from backend.services import epistemics
    ess = _svc("external_source_service")

    topic = str((step.params or {}).get("phrase")
                or (step.params or {}).get("topic")
                or memory.phrase or "").strip()
    if not topic:
        # `resolve()` already refused a topic-less step at plan time; this is the execution-time
        # twin, for the same reason `connect_marks` re-counts its marks — the plan proved a topic
        # WOULD exist, this proves one DOES.
        return ActuatorResult(status=EMPTY, produced=(), adapter="historical_source",
                              detail="no topic to research")

    result = await asyncio.to_thread(ess.retrieve, topic)
    if result.status == ess.RETRIEVAL_UNAVAILABLE:
        return ActuatorResult(status=UNAVAILABLE, produced=(), adapter=result.provider,
                              detail=result.detail)
    if not result.ok:
        return ActuatorResult(status=EMPTY, produced=(), adapter=result.provider,
                              detail=result.detail)

    descriptors = epistemics.guard([s.to_descriptor(run_id=ctx.run_id, provider=result.provider)
                                    for s in result.statements])
    ctx.suggestions.extend(descriptors)
    # `confidence` here is retrieval relevance, not a claim about whether the source is right.
    # The weakest-link summary treats it like any other, which is correct: a chain resting on a
    # barely-relevant quotation IS the weaker for it.
    weakest = min((s.confidence for s in result.statements), default=None)
    return ActuatorResult(
        status=OK, produced=tuple(actuator.produces) * len(result.statements),
        confidence=weakest, model=None, adapter=result.provider,
        detail=f"{len(result.statements)} sourced statement(s) from {result.documents_seen} source(s)",
        payload={"topic": topic, "documents_seen": result.documents_seen})


# actuator name → the async handler that runs it. Field producers share one handler; find_parts
# has its own (it calls segmentation, not a produce-field row). Actuators absent here have no
# in-process runner yet and report UNAVAILABLE — honest, and it flows through the skip logic.
_FIELD_PRODUCER_NAMES = (
    "negative_space", "material_field", "rhythm", "pressure_zone",
    "background_recession", "atmosphere_field", "light_field", "shadow_field",
    "grounded_sam_find_parts", "presence_check", "enumerate",
)
_DISPATCH: Dict[str, Callable] = {
    "find_parts": _run_find_parts,
    # WIRE-002 — the evidence-reading four.
    "semantic_read": _run_semantic_read,
    "find_similar": _run_find_similar,
    "connect_marks": _run_connect_marks,
    "compose_percept": _run_compose_percept,
    # CIRCUIT-003 M1 — the comparative two. They live in the SAME dispatch table as everything
    # else (the suite pins that every declared actuator has a runner), and they are handed the
    # same `ExecutionContext` shape. On a single-post context they find one image's marks and
    # refuse; on a corpus context they find all of them and compare.
    "compare_views": _run_compare_views,
    "compose_comparative_percept": _run_compose_comparative_percept,
    # CIRCUIT-003 M6 — the library.
    "historical_source": _run_historical_source,
}
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
            before = len(self.ctx.suggestions)
            res = await handler(step, memory, self.ctx, act)
            # M5 — the Director's quarantine boundary. Every runner appends to `ctx.suggestions`;
            # only what THIS step added is checked, so the cost stays flat across a long chain
            # rather than re-walking the whole list per step. In M6 this ran for one actuator and
            # was redundant by construction; across every actuator it is the single place where a
            # claim's stated kind is checked against the kind its producer is classified as.
            from backend.services import epistemics
            epistemics.guard(self.ctx.suggestions[before:])
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
