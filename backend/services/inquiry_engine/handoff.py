"""
HARNESS-001B2 §3 & §4 — the handoff: prepared world → projected world → situated mission.

    real InquiryFrame
      → EvidenceGoal
      → real Director ExecutionContext          (production.py)
      → PreparedWorldDelta                      (world.py)
      → ephemeral projected post                (world.project_world)
      → real situated-agent mission             (adapters.SimulatorAdapter, unchanged)
      → organ-authored evidence, back to the same InquiryRun

This module is the join, and it is deliberately thin: the projection is in `world.py` because it is
pure, the mission dispatch is `SimulatorAdapter` because that already exists and works, and what is
here is the ORDER, the locus check, and the decomposition of what went wrong.

## The one rule this file is really about

**The Region owning `mask_rle` travels with every `mask_ref`.** A mission is never handed a pointer
without its target — `validate_delta` refuses that before a projection can be built, and
`project_post` puts the Regions themselves into `region_annotations`, which is what an organ
actually reads. A descriptor is carried too, under `proposed_suggestions`, where a reader can see
it and no organ can stand on it.

## Six reasons, not one

When a preparation produces no usable locus, `no_new_evidence` is the answer that destroys the
information. These stay apart until the top-level stop event:

    measured_absence        the instrument ran; the concept is not in this picture
    planner_empty           nothing was planned for this task
    execution_unavailable   the instrument exists and is not running
    pointer_target_missing  a mark cited a region nobody captured
    no_locus                nothing to stand on in the projected post
    organ_refused           the body could not be used here

The first three come from the Director's own vocabulary, the fourth from `validate_delta`, and the
last two from the mission. They tell a curator to do six different things.

PURE OF PERSISTENCE. The projection is a deep copy, the source posts are fingerprinted before and
after, and everything the mission returns is a proposal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.inquiry_engine.adapters import MissionResult, SimulatorAdapter
from backend.services.inquiry_engine.goals import AgentMission, PreparationTask
from backend.services.inquiry_engine.production import ProductionDirectorAdapter, delta_of
from backend.services.inquiry_engine.world import (EXECUTION_UNAVAILABLE, NO_LOCUS, ORGAN_REFUSED,
                                                   PLANNER_EMPTY, POINTER_TARGET_MISSING,
                                                   PreparedWorldDelta, ProjectionRefused,
                                                   WorldDeltaInvalid, locus_available,
                                                   project_world)
from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint


@dataclass(frozen=True)
class HandoffResult:
    """One preparation → one mission, with everything either side produced, and why.

    `reasons` is a LIST because a handoff can fail in more than one way at once — a task that ran on
    two posts may have measured an absence on one and been unavailable on the other, and reporting
    the first one found would make the second invisible.
    """
    task_id: str
    evidence_goal_id: str
    delta: Optional[PreparedWorldDelta] = None
    mission: Optional[MissionResult] = None
    reasons: Tuple[str, ...] = ()
    detail: str = ""
    projected_post_ids: Tuple[str, ...] = ()
    locus: Tuple[str, str] = ("", "")
    posts_unchanged: bool = True

    @property
    def usable(self) -> bool:
        """Did a body actually perceive from prepared geometry? The whole question of the lane."""
        return bool(self.mission and self.mission.dispatched and self.mission.marks)

    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "evidence_goal_id": self.evidence_goal_id,
                "delta": self.delta.to_dict() if self.delta else None,
                "mission": self.mission.to_dict() if self.mission else None,
                "reasons": list(self.reasons), "detail": self.detail,
                "projected_post_ids": list(self.projected_post_ids),
                "locus": {"post_id": self.locus[0], "region_id": self.locus[1]},
                "posts_unchanged": self.posts_unchanged, "usable": self.usable}


def choose_locus(delta: PreparedWorldDelta, *, post_id: str = "",
                 region_id: str = "") -> Tuple[str, str]:
    """Where the mission should stand, given what preparation actually produced.

    An EXPLICIT locus wins and is not second-guessed — a mission that names a region is a mission
    about that region. Otherwise the first proposed Region on the first post that got one, in
    capture order, which is SAM's own instance order.

    Deliberately not "the largest" or "the most confident": those are selections dressed as
    defaults, and a run whose locus moved with a confidence score would not be replayable.
    """
    if post_id and region_id:
        return (post_id, region_id)
    for post in delta.per_post:
        if post_id and post.post_id != post_id:
            continue
        for region in post.proposed_regions:
            return (post.post_id, region.id)
    return (post_id, region_id)


def _reasons_from(delta: PreparedWorldDelta) -> List[str]:
    """The Director's own refusal vocabulary, kept as it was rather than collapsed.

    `production.py` already translated EMPTY → `measured_absence` and UNAVAILABLE →
    `execution_unavailable` at the point where it could still see which was which.
    """
    out: List[str] = []
    for refusal in delta.refusals:
        reason = str(refusal.get("reason") or "")
        if reason in (PLANNER_EMPTY, EXECUTION_UNAVAILABLE) or reason.endswith("_absence"):
            out.append(reason)
        elif reason:
            out.append(reason)
    return out


def run_handoff(task: PreparationTask, mission: AgentMission,
                posts: Mapping[str, Mapping[str, Any]], *,
                run_id: str, inquiry_id: str, evidence_goal_id: str,
                director: Optional[ProductionDirectorAdapter] = None,
                simulator: Optional[SimulatorAdapter] = None,
                phrase: str = "", now: str = "",
                graph: Optional[Mapping[str, Any]] = None) -> HandoffResult:
    """Prepare globally, project, and investigate locally — in that order, once.

    Bounded by construction: one preparation, one projection, one mission. There is no loop here;
    the engine's own bounded loop is what decides whether a second round happens.
    """
    director = director or ProductionDirectorAdapter()
    simulator = simulator or SimulatorAdapter()
    before = posts_fingerprint(posts)
    reasons: List[str] = []

    # ── 1. prepare, through the real context ─────────────────────────────
    try:
        result = director.prepare(task, posts, run_id=run_id, inquiry_id=inquiry_id,
                                  evidence_goal_id=evidence_goal_id, phrase=phrase, now=now)
    except WorldDeltaInvalid as exc:
        # The delta could not be validated — a pointer with no target, a region with no mask. The
        # mission is NOT dispatched: an agent perceiving from a half-built world would return real
        # readings of a world nobody made.
        return HandoffResult(task_id=task.id, evidence_goal_id=evidence_goal_id,
                             reasons=(POINTER_TARGET_MISSING,), detail=str(exc),
                             posts_unchanged=True)

    delta = delta_of(result)
    reasons.extend(_reasons_from(delta) if delta else [])

    if delta is None or delta.region_count == 0:
        return HandoffResult(
            task_id=task.id, evidence_goal_id=evidence_goal_id, delta=delta,
            reasons=tuple(reasons) or (EXECUTION_UNAVAILABLE,),
            detail=(result.detail or "the preparation created no usable region"),
            posts_unchanged=result.posts_unchanged)

    # ── 2. project — ephemeral, never mutating the source ────────────────
    try:
        projected = project_world(posts, delta)
    except ProjectionRefused as exc:
        return HandoffResult(task_id=task.id, evidence_goal_id=evidence_goal_id, delta=delta,
                             reasons=(*reasons, POINTER_TARGET_MISSING), detail=str(exc),
                             posts_unchanged=True)

    post_id, region_id = choose_locus(delta, post_id=mission.post_id,
                                      region_id=mission.region_id)
    projected_post = projected.get(post_id)
    if projected_post is None or not locus_available(projected_post, region_id):
        return HandoffResult(
            task_id=task.id, evidence_goal_id=evidence_goal_id, delta=delta,
            reasons=(*reasons, NO_LOCUS),
            detail=(f"the mission's locus {post_id!r}/{region_id!r} resolves to no region in the "
                    f"projected post — neither committed nor proposed"),
            projected_post_ids=tuple(projected), locus=(post_id, region_id),
            posts_unchanged=result.posts_unchanged)

    # ── 3. investigate locally, against the projected world ──────────────
    standing = AgentMission(**{**{f.name: getattr(mission, f.name)
                                  for f in mission.__dataclass_fields__.values()},
                               "post_id": post_id, "region_id": region_id})
    outcome = simulator.dispatch(standing, projected, run_id=run_id, inquiry_id=inquiry_id,
                                 evidence_goal_id=evidence_goal_id, now=now, graph=graph)
    if outcome.refusals:
        reasons.append(ORGAN_REFUSED)

    # THE SOURCE POSTS, not the projected copies. The projection is expected to differ; the posts
    # this run was handed must not.
    unchanged = True
    try:
        assert_posts_unchanged(before, posts_fingerprint(posts))
    except Exception:                                           # noqa: BLE001
        unchanged = False

    return HandoffResult(
        task_id=task.id, evidence_goal_id=evidence_goal_id, delta=delta, mission=outcome,
        reasons=tuple(reasons),
        detail=(f"{delta.region_count} proposed region(s) projected onto "
                f"{len(delta.per_post)} post(s); a body at {post_id}/{region_id} measured "
                f"{len(outcome.perceptions)} thing(s)"),
        projected_post_ids=tuple(projected), locus=(post_id, region_id),
        posts_unchanged=unchanged and result.posts_unchanged)


def evidence_provenance(handoff: HandoffResult) -> Dict[str, Any]:
    """What an evidence event must cite: the mission AND the preparation that made its locus exist.

    §4's rule, and it is not bookkeeping. A measurement taken on a proposed mask is only checkable
    if a reader can get from the measurement back to the segmentation that produced the extent —
    otherwise the mark is a measurement of geometry with no recorded origin, which is the same
    detachment as a pointer with no target, one step later.
    """
    return {"mission_id": (handoff.mission.mission_id if handoff.mission else ""),
            "preparation_task_id": handoff.task_id,
            "evidence_goal_id": handoff.evidence_goal_id,
            "locus": {"post_id": handoff.locus[0], "region_id": handoff.locus[1]},
            "world_delta": {"regions": handoff.delta.region_count if handoff.delta else 0,
                            "run_id": handoff.delta.run_id if handoff.delta else "",
                            "step_id": handoff.delta.step_id if handoff.delta else ""},
            "geometry_origin": "proposed_by_preparation"}


__all__ = ["HandoffResult", "run_handoff", "choose_locus", "evidence_provenance"]
