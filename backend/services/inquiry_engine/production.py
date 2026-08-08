"""
HARNESS-001B2 §2 — running a preparation task through the REAL production context seams.

`DirectorAdapter` (HARNESS-001B) takes an injected registry, which is right for unit tests and
wrong for the live bridge: with a fake registry there is no `ExecutionContext`, so there are no
Regions, so the masks never exist. This is its sibling, behind the same `PreparesEvidence`
protocol, and it differs in exactly one respect — it builds the production context and reads the
world back out of it.

WHAT IT DOES NOT DO, and the list is the point. It does not duplicate `_run_concept_segment`, or
`instances_to_regions`, or suggestion conversion, or corpus routing. Every one of those is
production's, called by production, through `real_registry` / `routed_registry`. This module
TRANSPORTS what production already made:

    seed a context per post   → ExecutionContext(post_id, post) with committed regions in place
    run the existing plan     → execution.execute(plan, memory, real_registry(ctx))
    diff the regions          → what this run ADDED, by identity, not by count
    take ctx.suggestions      → the descriptors, not the payload
    fingerprint the posts     → before and after, so `posts_unchanged` is checked, not claimed
    close the context         → the loop it owns, and only the loop it owns

## Why a DIFF rather than "everything in ctx.regions"

The context is SEEDED with the post's committed Regions, because a downstream step has to be able
to read one. Returning the whole list would report a committed Region as something this
preparation proposed, and a curator would be shown a mask they accepted last week as new work
awaiting review. So the capture takes the difference under
`(post_id, region_id, geometry_rev)` — identity, not position: a re-cut mask under an old id is a
different extent and must show up as added.

## Why availability is a word rather than a bool

`ran`/`available` as two booleans cannot say the four things `execution.py` already distinguishes:
OK, EMPTY, UNAVAILABLE and refused-at-plan-time. A preparation that measured nothing and one whose
instrument never started are not the same fact, and the mission that follows behaves differently
for each. So the delta carries `availability` from `world.py`'s named vocabulary.

SUGGESTIONS ONLY. Nothing here writes. The proof is a fingerprint, not a sentence.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.director import execution as director_execution
from backend.services.director.memory import WorkingMemory, build_memory
from backend.services.director.plan import Plan, Step, resolve as resolve_plan
from backend.services.director.planner import Director
from backend.services.inquiry_engine.adapters import PLANNER_NAME, PreparationResult
from backend.services.inquiry_engine.goals import PreparationTask
from backend.services.inquiry_engine.world import (EXECUTION_UNAVAILABLE, MEASURED_ABSENCE,
                                                   PLANNER_EMPTY, PostDelta, PreparedWorldDelta,
                                                   region_key)
from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

#: What the delta reports when a step ran and produced usable geometry.
AVAILABILITY_OK = "ok"


def _committed_regions(post: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [dict(r) for r in (post.get("region_annotations") or ()) if isinstance(r, Mapping)]


def _keys_of(post_id: str, regions: Sequence[Mapping[str, Any]]) -> set:
    return {region_key(post_id, r.get("id"), r.get("geometry_rev")) for r in regions}


class ProductionDirectorAdapter:
    """`PreparationTask` → the real Director, run in a real `ExecutionContext`, back as a delta.

    Implements `PreparesEvidence` so it drops into `run_inquiry` wherever `DirectorAdapter` does.
    `prepare()` returns the same `PreparationResult` the engine already reads; `prepare_world()`
    returns that PLUS the `PreparedWorldDelta`, which is the object a mission needs.

    `sam3_service` and friends are NOT injected here. The seam a test monkeypatches is the SERVICE
    module, one layer below, so the production runner above it is genuinely exercised — injecting
    a service into this class would let a proof pass while `_run_concept_segment` drifted.
    """

    name = "production"

    def __init__(self, *, director: Optional[Director] = None,
                 registry_for: Optional[Any] = None):
        self.director = director or Director()
        #: Injectable ONLY so the corpus path can be run on stubs, exactly as `routed_registry`
        #: allows. Default None means real runners.
        self.registry_for = registry_for
        self.last_delta: Optional[PreparedWorldDelta] = None

    # ── memory ──
    def _memory(self, post_id: str, post: Mapping[str, Any], phrase: str,
                task: PreparationTask) -> WorkingMemory:
        regions = [str(r.get("id") or "") for r in _committed_regions(post)]
        marks = [str(m.get("id") or "") for m in (post.get("visual_marks") or ())
                 if isinstance(m, Mapping)]
        return build_memory(image_ref=str(post.get("photo_url") or post_id or "image"),
                            post_id=post_id or None,
                            region_ids=[r for r in regions if r],
                            mark_ids=[m for m in marks if m],
                            phrase=phrase or task.params.get("phrase") or None)

    # ── the seam ──
    def prepare(self, task: PreparationTask, posts: Mapping[str, Mapping[str, Any]], *,
                run_id: str, inquiry_id: str, evidence_goal_id: str,
                phrase: str = "", now: str = "") -> PreparationResult:
        result, delta = self.prepare_world(
            task, posts, run_id=run_id, inquiry_id=inquiry_id,
            evidence_goal_id=evidence_goal_id, phrase=phrase, now=now)
        self.last_delta = delta
        return result

    def prepare_world(self, task: PreparationTask, posts: Mapping[str, Mapping[str, Any]], *,
                      run_id: str, inquiry_id: str, evidence_goal_id: str,
                      phrase: str = "", now: str = ""
                      ) -> Tuple[PreparationResult, PreparedWorldDelta]:
        """Run the task and return both the engine's result and the world it added."""
        from backend.services.director.real_actuators import ExecutionContext, real_registry

        before = posts_fingerprint(posts)
        provenance = {"run_id": run_id, "inquiry_id": inquiry_id,
                      "evidence_goal_id": evidence_goal_id, "task_id": task.id,
                      "parent_goal_id": task.parent_goal_id, "at": now,
                      "adapter": self.name}

        target_ids = [str(p) for p in (task.post_ids or ()) if str(p) in posts]
        if not target_ids:
            target_ids = [str(next(iter(posts)))] if posts else []
        if not target_ids:
            return self._nothing(task, evidence_goal_id, provenance, run_id, inquiry_id,
                                 detail="no post was named and none was available",
                                 availability=PLANNER_EMPTY)

        per_post: List[PostDelta] = []
        records: List[Dict[str, Any]] = []
        refusals: List[Dict[str, Any]] = []
        step_ids: List[str] = []
        statuses: List[str] = []

        for post_id in target_ids:
            post = dict(posts.get(post_id) or {})
            memory = self._memory(post_id, post, phrase, task)
            plan = self._plan(task, memory)
            if not plan.steps:
                refusals.append({"post_id": post_id, "reason": PLANNER_EMPTY,
                                 "detail": "the planner proposed no step for this task"})
            for row in plan.refused:
                refusals.append({"post_id": post_id, "reason": "plan_refused",
                                 "detail": str(row)})

            committed = _committed_regions(post)
            ctx = ExecutionContext(post_id=post_id, post=post, run_id=f"{run_id}:{task.id}")
            try:
                # SEEDED with the committed Regions, because a downstream step must be able to
                # read one — and diffed afterwards, so a committed mask is never reported as
                # something this preparation proposed.
                ctx.regions.extend(dict(r) for r in committed)
                seeded = _keys_of(post_id, ctx.regions)

                chain = director_execution.execute(plan, memory, real_registry(ctx),
                                                   chain_id=f"{run_id}:{task.id}:{post_id}")

                added = [dict(r) for r in ctx.regions
                         if region_key(post_id, r.get("id"), r.get("geometry_rev")) not in seeded]
                # `ctx.suggestions`, NOT `result.payload`. This one line is the lane.
                captured = [dict(s) for s in ctx.suggestions]
            finally:
                ctx.close()

            for row in chain.provenance.lineage:
                record = row.to_dict()
                record["post_id"] = post_id
                records.append(record)
                statuses.append(str(record.get("status") or ""))
                if record.get("step_id"):
                    step_ids.append(str(record["step_id"]))
                if record.get("status") != director_execution.OK:
                    refusals.append({"post_id": post_id, "step_id": record.get("step_id"),
                                     "actuator": record.get("actuator"),
                                     "reason": record.get("status"),
                                     "detail": record.get("detail")
                                     or record.get("skip_reason") or ""})
            for row in chain.provenance.refused:
                refusals.append({"post_id": post_id, **dict(row)})

            per_post.append(PostDelta(
                post_id=post_id, proposed_regions=tuple(added), suggestions=tuple(captured),
                committed_region_ids=tuple(str(r.get("id") or "") for r in committed)))

        availability = self._availability(statuses, per_post)
        unchanged = True
        try:
            assert_posts_unchanged(before, posts_fingerprint(posts))
        except Exception:                                       # noqa: BLE001
            unchanged = False

        added_total = sum(len(d.proposed_regions) for d in per_post)
        captured_total = sum(len(d.suggestions) for d in per_post)
        detail = (f"{len([s for s in statuses if s == director_execution.OK])} of {len(statuses)} "
                  f"step(s) ran; {added_total} proposed region(s) and {captured_total} "
                  f"descriptor(s) captured from the execution context")

        delta = PreparedWorldDelta(
            task_id=task.id, evidence_goal_id=evidence_goal_id, run_id=run_id,
            inquiry_id=inquiry_id, step_ids=tuple(step_ids), per_post=tuple(per_post),
            production_records=tuple(records), refusals=tuple(refusals),
            availability=availability, posts_unchanged=unchanged, detail=detail)

        ran = any(s in (director_execution.OK, director_execution.EMPTY) for s in statuses)
        result = PreparationResult(
            task_id=task.id, goal_id=evidence_goal_id, ran=ran,
            available=availability != EXECUTION_UNAVAILABLE,
            records=tuple(records),
            # The engine's own view stays the descriptors, so nothing downstream of it changes
            # shape. The Regions travel in the delta, where a mission can find them.
            suggestions=tuple(s for d in per_post for s in d.suggestions),
            refusals=tuple(refusals), provenance=provenance, detail=detail,
            posts_unchanged=unchanged)
        self.last_delta = delta
        return result, delta

    # ── plan ──
    def _plan(self, task: PreparationTask, memory: WorkingMemory) -> Plan:
        """The task's own plan, through the SAME resolver every planner's output passes through.

        No new planner. A task naming a deleted actuator is refused `unknown_actuator` and one
        whose inputs do not exist is refused `missing_input`, by the existing code.
        """
        if task.actuator:
            step = Step(actuator=task.actuator, params=dict(task.params), id=task.id,
                        note=task.detail)
            return resolve_plan([step], memory, intention=task.title or task.actuator,
                                planner=PLANNER_NAME)
        return self.director.plan(task.intention, memory)

    # ── availability ──
    @staticmethod
    def _availability(statuses: Sequence[str], per_post: Sequence[PostDelta]) -> str:
        """One word from the named vocabulary, never a bool.

        The order matters: a run that produced usable geometry is `ok` even if some other step was
        unavailable, and a run that produced none reports WHY it produced none — because "the
        instrument never started" and "the instrument looked and found nothing" lead to different
        missions and a caller that saw one bool would treat them alike.
        """
        if not statuses:
            return PLANNER_EMPTY
        if any(len(d.proposed_regions) > 0 for d in per_post):
            return AVAILABILITY_OK
        if any(s == director_execution.OK for s in statuses):
            return AVAILABILITY_OK
        if any(s == director_execution.EMPTY for s in statuses):
            return MEASURED_ABSENCE
        return EXECUTION_UNAVAILABLE

    @staticmethod
    def _nothing(task: PreparationTask, evidence_goal_id: str, provenance: Dict[str, Any],
                 run_id: str, inquiry_id: str, *, detail: str, availability: str
                 ) -> Tuple[PreparationResult, PreparedWorldDelta]:
        delta = PreparedWorldDelta(task_id=task.id, evidence_goal_id=evidence_goal_id,
                                   run_id=run_id, inquiry_id=inquiry_id,
                                   availability=availability, detail=detail)
        result = PreparationResult(task_id=task.id, goal_id=evidence_goal_id, ran=False,
                                   available=False, provenance=provenance, detail=detail)
        return result, delta


__all__ = ["AVAILABILITY_OK", "ProductionDirectorAdapter"]
