"""
HARNESS-001B2 §2 — the production-context Director adapter: transport, not a second engine.

HARNESS-001B's `DirectorAdapter` takes an INJECTED registry of runners and reads
`ActuatorResult.payload`. That is exactly right for unit tests and exactly wrong for the real
runners, because the real runners do not return their evidence — they WRITE IT INTO THE CONTEXT:

    ctx.regions      proposed Regions, which own `mask_rle`
    ctx.suggestions  quarantined descriptors, whose geometry is a `mask_ref` POINTER into the above
    result.payload   counts

So this module runs a `PreparationTask` through the SAME `plan.resolve` and the SAME
`execution.execute`, against a real `ExecutionContext` (or a `CorpusExecutionContext`), and then
captures the context — by DIFF, so what it reports is what this task added rather than everything
the context happened to hold.

## What is deliberately not here

`_run_concept_segment`, `instances_to_regions`, `suggestions_from_concept_segments`, corpus routing.
None of it is duplicated. This module builds a context, hands it to production, and carries away
what production made. A transporter that re-implemented any of that would eventually transport
something the runtime never produced.

## Both adapters, kept apart on purpose

`DirectorAdapter` (injected registry) stays exactly as it was — the fast tests depend on it and it
is the right seam for them. `ProductionDirectorAdapter` is a clearly named SIBLING implementing the
same `prepare(...)` protocol. Silently turning the first into the second is the change this
docstring exists to prevent: a test that thought it was running stubs and was firing SAM 3 would be
slow, non-deterministic, and would look like a passing test the whole time.

## Borrowed contexts

`ExecutionContext.__post_init__` opens an event loop when it is handed none, and `close()` closes it
only if it opened it. This module owns the contexts it builds and closes them; a caller that passes
its own context keeps it. `owns_context=False` is what a corpus caller uses, and it is why `capture`
is a function over a context rather than a method that assumes it made one.

PURE OF PERSISTENCE. No database, no commit, no post write. Source posts are fingerprinted before
and after every preparation, and `posts_unchanged` on the delta is that check's result rather than a
claim.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.director import execution as director_execution
from backend.services.director.memory import WorkingMemory, build_memory
from backend.services.director.plan import Plan, Step, resolve as resolve_plan
from backend.services.director.planner import Director
from backend.services.inquiry_engine.adapters import PLANNER_NAME, PreparationResult
from backend.services.inquiry_engine.goals import PreparationTask
from backend.services.inquiry_engine.world import (EXECUTION_UNAVAILABLE, MEASURED_ABSENCE,
                                                   PLANNER_EMPTY, PostDelta, PreparedWorldDelta,
                                                   ProposedRegion, validate_delta)
from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint


def _region_signature(region: Mapping[str, Any]) -> Tuple[str, int]:
    """`(id, geometry_rev)` — how a captured Region is told from one that was already there.

    Not identity by `id` alone: a re-canonicalisation bumps `geometry_rev` on the same id, and a
    diff keyed only on the id would report a repointed region as unchanged.
    """
    return (str(region.get("id") or ""), int(region.get("geometry_rev") or 0))


def capture(ctx: Any, *, post_id: str, before_regions: Sequence[Mapping[str, Any]],
            before_suggestions: int) -> PostDelta:
    """What this execution ADDED to one context, as a `PostDelta`.

    BY DIFF, and the diff is the point. `build_context` seeds `ctx.regions` with the post's
    committed regions so a step needing a region can use one the curator already made — exactly as
    the production orchestrate route does. Reporting `ctx.regions` wholesale would therefore return
    the curator's own geometry as something this preparation proposed, and a reader could not tell
    which regions were new.

    Suggestions are taken by COUNT rather than by signature: a descriptor has no stable identity
    until it is accepted (its `id` is None by contract), and the context only ever appends.
    """
    seen = {_region_signature(r) for r in before_regions}
    added = [r for r in (ctx.regions or ()) if _region_signature(r) not in seen]
    fresh = list(ctx.suggestions or ())[before_suggestions:]
    committed = tuple(str(r.get("id") or "") for r in before_regions)
    return PostDelta(post_id=str(post_id),
                     proposed_regions=tuple(ProposedRegion.of(r, post_id=str(post_id))
                                            for r in added),
                     suggestions=tuple(copy.deepcopy(dict(s)) for s in fresh),
                     committed_region_ids=committed)


def build_context(post_id: str, post: Mapping[str, Any], *, run_id: str, loop: Any = None):
    """One real `ExecutionContext`, seeded exactly as production seeds one.

    Imported lazily because `real_actuators` pulls in the vision stack, and a caller that only wants
    the injected-registry adapter should not pay for it.
    """
    from backend.services.director.real_actuators import ExecutionContext

    ctx = ExecutionContext(post_id=str(post_id), post=dict(post), run_id=run_id, loop=loop)
    # The committed regions the curator already has. `_resolve_region` reads these, so a step that
    # needs a region can use one that exists — and `capture`'s diff excludes them from the delta.
    ctx.regions.extend(dict(r) for r in (post.get("region_annotations") or ())
                       if isinstance(r, Mapping))
    return ctx


class ProductionDirectorAdapter:
    """`PreparationTask` → real runners → `PreparedWorldDelta`. The live half of the seam.

    Implements the same `prepare(...)` protocol as `DirectorAdapter`, and returns the same
    `PreparationResult` — with the delta attached, because a caller that only wants records and
    refusals should not have to know this one carries a world.

    `registry_factory` exists so the production PATH can be exercised without the production MODELS:
    a test hands `real_registry`-shaped runners built over a monkeypatched SAM service, and the
    runner still performs `instances_to_regions`, the suggestion conversion and the context writes.
    That is the difference the directive asks for between this and a fake Director result — the
    fake returns an answer, this one runs the machinery that produces one.
    """

    def __init__(self, *, director: Optional[Director] = None,
                 registry_factory=None, loop: Any = None):
        self.director = director or Director()
        self._registry_factory = registry_factory
        self.loop = loop
        self.last_delta: Optional[PreparedWorldDelta] = None

    def _registry(self, ctx: Any) -> Dict[str, Any]:
        if self._registry_factory is not None:
            return self._registry_factory(ctx)
        from backend.services.director.real_actuators import real_registry
        return real_registry(ctx)

    def _memory(self, task: PreparationTask, post_id: str, post: Mapping[str, Any],
                phrase: str) -> WorkingMemory:
        regions = [str(r.get("id") or "") for r in (post.get("region_annotations") or ())
                   if isinstance(r, Mapping)]
        marks = [str(m.get("id") or "") for m in (post.get("visual_marks") or ())
                 if isinstance(m, Mapping)]
        return build_memory(image_ref=str(post.get("photo_url") or post_id or "image"),
                            post_id=post_id or None,
                            region_ids=[r for r in regions if r],
                            mark_ids=[m for m in marks if m],
                            phrase=phrase or task.params.get("phrase") or None)

    def _plan(self, task: PreparationTask, memory: WorkingMemory) -> Plan:
        """The same gate every planner's output passes through. Not a new planner."""
        if task.actuator:
            step = Step(actuator=task.actuator, params=dict(task.params), id=task.id,
                        note=task.detail)
            return resolve_plan([step], memory, intention=task.title or task.actuator,
                                planner=PLANNER_NAME)
        return self.director.plan(task.intention, memory)

    def prepare(self, task: PreparationTask, posts: Mapping[str, Mapping[str, Any]], *,
                run_id: str, inquiry_id: str, evidence_goal_id: str,
                phrase: str = "", now: str = "") -> PreparationResult:
        before = posts_fingerprint(posts)
        provenance = {"run_id": run_id, "inquiry_id": inquiry_id,
                      "evidence_goal_id": evidence_goal_id, "task_id": task.id,
                      "parent_goal_id": task.parent_goal_id, "at": now,
                      "adapter": "production"}

        targets = [p for p in (task.post_ids or tuple(posts)) if p in posts]
        per_post: List[PostDelta] = []
        lineage: List[Dict[str, Any]] = []
        refusals: List[Dict[str, Any]] = []
        contexts: List[Any] = []

        try:
            for post_id in targets:
                post = posts[post_id]
                ctx = build_context(post_id, post, run_id=run_id, loop=self.loop)
                contexts.append(ctx)
                memory = self._memory(task, post_id, post, phrase)
                plan = self._plan(task, memory)
                if not plan.steps:
                    refusals.append({"post_id": post_id, "reason": PLANNER_EMPTY,
                                     "detail": " | ".join(plan.notes) or
                                     "nothing was planned for this task"})
                before_regions = [dict(r) for r in ctx.regions]
                before_suggestions = len(ctx.suggestions)

                chain = director_execution.execute(
                    plan, memory, self._registry(ctx), chain_id=f"{run_id}:{task.id}:{post_id}")
                for record in chain.provenance.lineage:
                    row = record.to_dict()
                    row["post_id"] = post_id
                    lineage.append(row)
                    if row.get("status") != director_execution.OK:
                        refusals.append({
                            "post_id": post_id, "step_id": row.get("step_id"),
                            "actuator": row.get("actuator"),
                            # EMPTY is a real answer — "that concept is not in this picture" — and
                            # UNAVAILABLE is a model being down. Reported as different reasons here
                            # so the mission's decomposed result can stay decomposed.
                            "reason": (MEASURED_ABSENCE
                                       if row.get("status") == director_execution.EMPTY
                                       else EXECUTION_UNAVAILABLE
                                       if row.get("status") == director_execution.UNAVAILABLE
                                       else str(row.get("status") or "")),
                            "detail": row.get("detail") or row.get("skip_reason") or ""})
                for refused in chain.provenance.refused:
                    refusals.append({"post_id": post_id, **dict(refused)})

                per_post.append(capture(ctx, post_id=post_id, before_regions=before_regions,
                                        before_suggestions=before_suggestions))
        finally:
            for ctx in contexts:
                ctx.close()

        unchanged = True
        try:
            assert_posts_unchanged(before, posts_fingerprint(posts))
        except Exception:                                       # noqa: BLE001
            unchanged = False

        ran = any(r.get("status") in (director_execution.OK, director_execution.EMPTY)
                  for r in lineage)
        available = any(r.get("status") != director_execution.UNAVAILABLE for r in lineage) \
            if lineage else False

        delta = PreparedWorldDelta(
            task_id=task.id, evidence_goal_id=evidence_goal_id, run_id=run_id,
            step_id=task.id, per_post=tuple(per_post),
            production_records=tuple(lineage), refusals=tuple(refusals),
            availability={"ran": ran, "available": available,
                          "posts": list(targets)},
            posts_unchanged=unchanged,
            detail=(f"{sum(len(p.proposed_regions) for p in per_post)} proposed region(s), "
                    f"{sum(len(p.suggestions) for p in per_post)} descriptor(s) across "
                    f"{len(per_post)} post(s)"))
        # VALIDATED BEFORE IT CAN BE HANDED ANYWHERE. A delta whose pointers do not resolve must not
        # reach a projection, and the refusal has to name the descriptor rather than surface later
        # as an organ measuring nothing.
        validate_delta(delta)
        self.last_delta = delta

        suggestions = [s for p in per_post for s in p.suggestions]
        return PreparationResult(
            task_id=task.id, goal_id=evidence_goal_id, ran=ran, available=available,
            records=tuple(lineage), suggestions=tuple(suggestions), refusals=tuple(refusals),
            provenance={**provenance, "world_delta": delta.to_dict()},
            detail=delta.detail, posts_unchanged=unchanged)


def delta_of(result: PreparationResult) -> Optional[PreparedWorldDelta]:
    """The world delta a production preparation carried back, or None for an injected-registry one.

    The delta rides on `provenance` rather than on a new field of `PreparationResult`, so the two
    adapters keep one return type and a caller that does not care about the world does not have to
    branch on which adapter ran. `None` here is a fact — that preparation added no world — and not
    a missing lookup.
    """
    payload = (result.provenance or {}).get("world_delta")
    if not isinstance(payload, Mapping):
        return None
    return PreparedWorldDelta.from_dict(payload)


__all__ = ["ProductionDirectorAdapter", "build_context", "capture", "delta_of"]
