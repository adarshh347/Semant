"""
HARNESS-001B2 §3–4 — the bridge from global preparation to local situatedness.

    committed post copy + valid PreparedWorldDelta  →  mission-world post copy

An organ reads exactly one thing: `post["region_annotations"]` (`organs._region`). So the whole
projection is the act of putting the proposed Regions where an organ will look, on a COPY, and
being precise about what that does and does not mean.

## What projection means, and what it does not

A proposed Region becomes live geometry for the agent standing on it. That is the existing
private-vs-ledger ruling applied rather than extended: an organ's measurement is the agent's own
first-person reading, private in the sense of REACH, and it can rest on geometry that is not yet
part of the shared record. The mask is real — SAM 3 computed it off the signal — and what is
un-agreed is whether the curator wants it in the ledger.

So the projection carries the mask and keeps `proposed: True` on every Region it adds. Nothing
here accepts, commits, or writes; a projected post is discarded when the mission ends.

## The three things it refuses

  · A proposed Region whose id collides with a COMMITTED one on the same post, with different
    geometry. The committed Region wins and the proposal is refused by name. Replacing it would
    substitute an unaccepted extent for an accepted one, and every later reading would be about a
    different shape under a familiar id.
  · A pointer with no target — inherited from `world.validate_delta`, checked again here because
    this is the last place before an agent stands on it.
  · An interpretive naming as geometry. A naming authors none, so it contributes NOTHING to
    `region_annotations`. An organ that could read a naming would be measuring a word.

## Mission return

The mission runs through the existing `SimulatorAdapter` against the projected posts. The body,
the organ set and the locus come from the mission; the readings come from the organ; the wall
(`assert_organ_authored`) still refuses a Director descriptor offered as a perception. What this
module adds is the projection underneath and a DECOMPOSED reason when nothing came back — because
`no_new_evidence` covering six different failures is how a missing instrument and a measured
absence stop being distinguishable.

PURE apart from the adapters it is handed. No database, no network, no clock it was not given.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.inquiry_engine.world import (EXECUTION_UNAVAILABLE, MEASURED_ABSENCE,
                                                   NO_LOCUS, ORGAN_REFUSED, PLANNER_EMPTY,
                                                   POINTER_TARGET_MISSING, PostDelta,
                                                   PreparedWorldDelta, region_has_mask,
                                                   validate_delta)

#: The key an organ reads. Named once so a rename cannot half-happen.
REGIONS_KEY = "region_annotations"


@dataclass(frozen=True)
class ProjectedWorld:
    """Post copies an agent may inhabit, plus everything refused on the way in.

    `refusals` is not an error channel — it is the receipt. A projection that silently dropped a
    conflicting Region would produce a mission whose world was smaller than the delta for reasons
    nobody could reconstruct.
    """
    posts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    projected_region_ids: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    refusals: Tuple[Dict[str, Any], ...] = ()

    def loci(self, post_id: str) -> Tuple[str, ...]:
        """Region ids an agent could stand on in this post — committed and projected alike."""
        post = self.posts.get(str(post_id)) or {}
        return tuple(str(r.get("id") or "") for r in post.get(REGIONS_KEY) or ()
                     if isinstance(r, Mapping))

    def measurable_loci(self, post_id: str) -> Tuple[str, ...]:
        """Only the ones that own an extent. A locus with no mask affords no measurement."""
        post = self.posts.get(str(post_id)) or {}
        return tuple(str(r.get("id") or "") for r in post.get(REGIONS_KEY) or ()
                     if isinstance(r, Mapping) and region_has_mask(r))

    def to_dict(self) -> Dict[str, Any]:
        return {"post_ids": sorted(self.posts),
                "projected_region_ids": {k: list(v) for k, v in self.projected_region_ids.items()},
                "refusals": [dict(r) for r in self.refusals]}


def project(posts: Mapping[str, Mapping[str, Any]], delta: PreparedWorldDelta) -> ProjectedWorld:
    """A valid delta over committed posts → posts an agent can inhabit. NEVER mutates the source.

    The copy is deep at every level the projection touches: the post mapping, its
    `region_annotations` list, and each Region dict. A shallow copy would let an organ's
    canonicalisation write through into the committed post, which is precisely the thing this
    lane's whole `posts_unchanged` discipline is built to prevent.
    """
    refusals: List[Dict[str, Any]] = [dict(r) for r in validate_delta(delta)]
    projected: Dict[str, Dict[str, Any]] = {}
    ids_by_post: Dict[str, Tuple[str, ...]] = {}

    for post_id, source in posts.items():
        post_copy = dict(source)
        committed = [dict(r) for r in (source.get(REGIONS_KEY) or ()) if isinstance(r, Mapping)]
        post_copy[REGIONS_KEY] = committed
        post_copy["visual_marks"] = [dict(m) for m in (source.get("visual_marks") or ())
                                     if isinstance(m, Mapping)]
        projected[str(post_id)] = post_copy
        ids_by_post[str(post_id)] = ()

    for post_delta in delta.per_post:
        post_id = post_delta.post_id
        post_copy = projected.get(post_id)
        if post_copy is None:
            refusals.append({"reason": NO_LOCUS, "post_id": post_id,
                             "detail": f"the delta carries work for post {post_id!r}, which is "
                                       f"not among the posts handed to the projection — there is "
                                       f"nothing to project it onto"})
            continue
        added, post_refusals = _merge(post_copy, post_delta)
        ids_by_post[post_id] = added
        refusals.extend(post_refusals)

    return ProjectedWorld(posts=projected, projected_region_ids=ids_by_post,
                          refusals=tuple(refusals))


def _merge(post_copy: Dict[str, Any], post_delta: PostDelta) -> Tuple[Tuple[str, ...],
                                                                      List[Dict[str, Any]]]:
    """Put this post's proposed Regions where an organ will look, and say what was refused."""
    refusals: List[Dict[str, Any]] = []
    committed = {str(r.get("id") or ""): r for r in post_copy[REGIONS_KEY]}
    added: List[str] = []

    for region in post_delta.proposed_regions:
        rid = str(region.get("id") or "")
        if not rid:
            refusals.append({"reason": POINTER_TARGET_MISSING, "post_id": post_delta.post_id,
                             "detail": "a proposed Region with no id cannot be a locus"})
            continue
        existing = committed.get(rid)
        if existing is not None:
            if _geometry(existing) != _geometry(region):
                # THE COMMITTED REGION WINS. Replacing it would substitute an unaccepted extent
                # for an accepted one, and every later reading would be about a different shape
                # under a familiar id.
                refusals.append({
                    "reason": POINTER_TARGET_MISSING, "post_id": post_delta.post_id,
                    "region_id": rid,
                    "detail": f"a proposed Region claims id {rid!r}, which a COMMITTED Region on "
                              f"post {post_delta.post_id!r} already holds with different "
                              f"geometry. The committed one stands; the proposal is refused "
                              f"rather than allowed to replace it."})
            continue
        # `proposed: True` is asserted rather than assumed. A Region that arrived here without it
        # would enter the agent's world indistinguishable from something a curator accepted.
        projected_region = dict(region)
        projected_region["proposed"] = True
        projected_region["ledger_status"] = "proposed"
        post_copy[REGIONS_KEY].append(projected_region)
        committed[rid] = projected_region
        added.append(rid)

    return tuple(added), refusals


def _geometry(region: Mapping[str, Any]) -> Tuple[Any, Any, Any]:
    return (region.get("mask_rle"), region.get("polygons"), region.get("geometry_rev"))


# ── mission dispatch over a projected world ──────────────────────────────────

@dataclass(frozen=True)
class HandoffOutcome:
    """One preparation → one mission, and a reason precise enough to act on.

    `reason` comes from `world.DELTA_REFUSALS` and is NOT flattened to `no_new_evidence` here.
    §4 of the directive says the flattening may happen at the top-level stop event and that the
    detail must survive there — so the decomposition has to exist somewhere, and this is it.
    """
    dispatched: bool
    reason: str = ""
    detail: str = ""
    mission_result: Optional[Any] = None
    world: Optional[ProjectedWorld] = None
    locus: Tuple[str, str] = ("", "")
    organ_marks: Tuple[Dict[str, Any], ...] = ()
    posts_unchanged: bool = True

    def measured_marks(self) -> Tuple[Dict[str, Any], ...]:
        """Only the organ-authored marks whose own status is `measured`.

        The parent `EvidenceGoal` is evaluated from THESE, not from the preparation completing.
        A preparation that ran is not evidence; it is the condition under which evidence became
        possible.
        """
        return tuple(m for m in self.organ_marks
                     if str(m.get("epistemic_status") or "") == "measured")

    def to_dict(self) -> Dict[str, Any]:
        return {"dispatched": self.dispatched, "reason": self.reason, "detail": self.detail,
                "locus": {"post_id": self.locus[0], "region_id": self.locus[1]},
                "world": self.world.to_dict() if self.world is not None else None,
                "organ_marks": [dict(m) for m in self.organ_marks],
                "measured_marks": len(self.measured_marks()),
                "mission_result": (self.mission_result.to_dict()
                                   if self.mission_result is not None else None),
                "posts_unchanged": self.posts_unchanged}


def choose_locus(world: ProjectedWorld, delta: PreparedWorldDelta, *,
                 post_id: str = "", region_id: str = "") -> Tuple[str, str]:
    """Where the agent stands: an explicit locus if one was named, else a projected Region.

    Prefers a Region THIS PREPARATION added, because that is what the mission is for. Falls back
    to any measurable locus in the post, so a mission is not refused merely because the useful
    Region was already committed.
    """
    if post_id and region_id:
        return (post_id, region_id)
    candidates = [post_id] if post_id else list(delta.post_ids())
    for candidate in candidates:
        projected = world.projected_region_ids.get(candidate) or ()
        measurable = set(world.measurable_loci(candidate))
        for rid in projected:
            if rid in measurable:
                return (candidate, rid)
    for candidate in candidates:
        measurable = world.measurable_loci(candidate)
        if measurable:
            return (candidate, measurable[0])
    return ("", "")


def _at_locus(mission: Any, post_id: str, region_id: str) -> Any:
    """The mission, standing where the projection put it.

    `AgentMission` is frozen, so this returns a NEW mission rather than moving the old one — an
    agent whose locus could be reassigned in place would make the run's own record of where it
    stood unreliable.
    """
    if getattr(mission, "post_id", "") == post_id and getattr(mission, "region_id", "") == region_id:
        return mission
    import dataclasses
    if dataclasses.is_dataclass(mission):
        return dataclasses.replace(mission, post_id=post_id, region_id=region_id)
    return mission


def run_handoff(delta: PreparedWorldDelta, posts: Mapping[str, Mapping[str, Any]], *,
                simulator: Any, mission: Any, run_id: str, inquiry_id: str,
                evidence_goal_id: str, now: str = "",
                graph: Optional[Mapping[str, Any]] = None) -> HandoffOutcome:
    """Project the delta, stand an agent on it, and return what its organs measured.

    The mission is dispatched with `proposed_marks=()` — DELIBERATELY. The Director's descriptors
    travel in the delta as Regions the organ can measure FOR ITSELF; handing them to the agent as
    marks would offer a proposal as a perception, which `assert_organ_authored` refuses by name.
    The distinction is the whole point of the lane: prepared GEOMETRY is available to be measured,
    prepared CLAIMS are not available to be believed.
    """
    from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

    before = posts_fingerprint(posts)

    if delta.availability == EXECUTION_UNAVAILABLE:
        return HandoffOutcome(False, EXECUTION_UNAVAILABLE,
                              delta.detail or "the instrument exists and did not run")
    if delta.availability == PLANNER_EMPTY:
        return HandoffOutcome(False, PLANNER_EMPTY, delta.detail or "nothing was planned")

    problems = validate_delta(delta)
    if problems:
        return HandoffOutcome(False, POINTER_TARGET_MISSING,
                              "; ".join(str(p.get("detail")) for p in problems))

    world = project(posts, delta)

    if not delta.has_usable_region():
        # It ran and it looked. That is an ANSWER, and reporting it as an unavailable instrument
        # would make a real absence look like a broken tool.
        return HandoffOutcome(False, MEASURED_ABSENCE,
                              delta.detail or "the preparation created no Region with an extent",
                              world=world)

    post_id, region_id = choose_locus(world, delta, post_id=getattr(mission, "post_id", ""),
                                      region_id=getattr(mission, "region_id", ""))
    if not post_id or not region_id:
        return HandoffOutcome(False, NO_LOCUS,
                              "the projected world has no Region with an extent to stand on",
                              world=world)

    situated = _at_locus(mission, post_id, region_id)
    result = simulator.dispatch(situated, world.posts, run_id=run_id, inquiry_id=inquiry_id,
                                evidence_goal_id=evidence_goal_id, now=now, graph=graph,
                                proposed_marks=())

    unchanged = True
    try:
        assert_posts_unchanged(before, posts_fingerprint(posts))
    except Exception:                                          # noqa: BLE001
        unchanged = False

    if not result.dispatched:
        detail = "; ".join(str(r.get("detail")) for r in result.refusals) or "the body refused"
        return HandoffOutcome(False, ORGAN_REFUSED, detail, mission_result=result, world=world,
                              locus=(post_id, region_id), posts_unchanged=unchanged)

    marks = tuple(dict(m) for m in result.marks)
    if not marks and result.refusals:
        return HandoffOutcome(False, ORGAN_REFUSED,
                              "; ".join(str(r.get("detail")) for r in result.refusals),
                              mission_result=result, world=world, locus=(post_id, region_id),
                              posts_unchanged=unchanged)

    return HandoffOutcome(True, "", result.provenance.get("detail", "") or "",
                          mission_result=result, world=world, locus=(post_id, region_id),
                          organ_marks=marks, posts_unchanged=unchanged)


__all__ = ["REGIONS_KEY", "ProjectedWorld", "project", "HandoffOutcome", "choose_locus",
           "run_handoff"]
