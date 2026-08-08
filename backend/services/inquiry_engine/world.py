"""
HARNESS-001B2 §1 & §3 — `PreparedWorldDelta`, and the ephemeral world it projects.

## The object HARNESS-001B did not have

That lane's Director adapter collected `ActuatorResult.payload`, which for the actuator this whole
bridge exists for is a dict of COUNTS:

    {"concept": "fold", "instances": 2, "truncated": False, "latency_ms": 4210.0}

Everything that matters went somewhere else. `_run_concept_segment` puts the proposed Regions —
the objects that OWN `mask_rle` — into `ctx.regions`, and the quarantined descriptors into
`ctx.suggestions`. Each descriptor's geometry is `mask_ref: {region_id, geometry_rev}`: **a
pointer.** Capture the descriptors without the Regions and you have handed the next stage a
well-formed mark citing a region that does not exist. Every reader downstream sees a mark. Nothing
sees a mask.

So this module names the missing object. A `PreparedWorldDelta` is **an execution receipt, not a
ledger**: what preparation ADDED, carried whole, with no implication that any of it is committed.

## Identity is post-qualified, always

SAM 3 instance ids are POSITIONAL — `cseg_fold_0` is the first instance of *this* concept in *this*
run — and `sam3_concept_service` says so outright. Two posts segmented for one concept therefore
produce the SAME local id. A world that resolved `region_id` globally would let the second image's
mask answer for the first, silently, with correct-looking geometry. So a Region is keyed
`(post_id, region_id, geometry_rev)` and a `mask_ref` resolves only inside its own post's delta or
against a Region already committed on that post.

## Pointer without target is a NAMED refusal

Not a silent drop (a run reporting fewer marks, with no reason) and not a pass-through (a mark
citing nothing, inside an agent's world). `validate_delta` refuses, naming the descriptor and the
id it could not resolve, and `POINTER_TARGET_MISSING` is one of the decomposed reasons the mission
result carries.

## The projection

`project_post` is the explicit bridge from global preparation to local situatedness: a committed
post copy plus a valid delta becomes a mission-world post copy that an organ can measure from.

It never mutates the source. Proposed Regions become live/private geometry — which is exactly the
existing private-measured / ledger-proposed ruling: an agent's organ may measure a proposed mask and
record `measured` in its own memory, while the shared ledger still reads `proposed` because no
curator has committed anything. What a projection may never do is make a naming into a fact: an
`interpretive` `region_ref` authors no extent, so it is carried as a suggestion and never as a
region an organ could stand on.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: The two geometry kinds a concept descriptor carries, spelled from `suggestion_service`'s own
#: output rather than restated: a measured extent is a `raster_mask` pointing at a region's mask,
#: an interpretive naming is a `region_ref` pointing at the same region and authoring nothing.
GEOMETRY_RASTER = "raster_mask"
GEOMETRY_NAMING = "region_ref"

# ── the decomposed reasons a preparation produced no usable locus ────────────
#: Six, and none of them is `no_new_evidence`. They are flattened to that only at the top-level stop
#: event, which keeps the detailed reason — because "the model was down", "the concept is not in
#: this picture" and "the mark cited a region nobody captured" ask for three different next moves.
MEASURED_ABSENCE = "measured_absence"
PLANNER_EMPTY = "planner_empty"
EXECUTION_UNAVAILABLE = "execution_unavailable"
POINTER_TARGET_MISSING = "pointer_target_missing"
NO_LOCUS = "no_locus"
ORGAN_REFUSED = "organ_refused"

HANDOFF_REASONS: Tuple[str, ...] = (MEASURED_ABSENCE, PLANNER_EMPTY, EXECUTION_UNAVAILABLE,
                                    POINTER_TARGET_MISSING, NO_LOCUS, ORGAN_REFUSED)


class WorldDeltaInvalid(Exception):
    """A delta that may not be handed to a mission. Raised rather than filtered: a silently
    repaired delta would let a run report a smaller world with no explanation of why."""


class ProjectionRefused(Exception):
    """A proposed Region cannot enter the projected world without contradicting a committed one."""


def region_key(post_id: str, region: Mapping[str, Any]) -> Tuple[str, str, int]:
    """`(post_id, region_id, geometry_rev)` — the only identity this lane resolves on.

    `region_id` alone is not one. Positional SAM ids repeat across posts and across runs, and a
    global resolution would substitute one image's mask for another's while every id still looked
    right.
    """
    return (str(post_id), str(region.get("id") or ""), int(region.get("geometry_rev") or 0))


@dataclass(frozen=True)
class ProposedRegion:
    """One Region preparation added, carried WHOLE — mask and all.

    A copy, not a reference: the delta is a receipt of what an execution produced, and a receipt
    that aliased live context state would change after the fact.
    """
    post_id: str
    region: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def of(cls, region: Mapping[str, Any], *, post_id: str = "") -> "ProposedRegion":
        return cls(post_id=str(post_id), region=copy.deepcopy(dict(region)))

    @property
    def id(self) -> str:
        return str(self.region.get("id") or "")

    @property
    def geometry_rev(self) -> int:
        return int(self.region.get("geometry_rev") or 0)

    @property
    def proposed(self) -> bool:
        return bool(self.region.get("proposed"))

    @property
    def has_mask(self) -> bool:
        """A Region without geometry is not one an organ can stand on. `mask_rle` is authoritative;
        `polygons` is accepted because `canonicalize_geometry` derives one from the other and a
        polygon-only region is legitimate geometry, merely not raster."""
        return bool(self.region.get("mask_rle") or self.region.get("polygons"))

    @property
    def key(self) -> Tuple[str, str, int]:
        return region_key(self.post_id, self.region)

    def as_region(self) -> Dict[str, Any]:
        return copy.deepcopy(self.region)

    def to_dict(self) -> Dict[str, Any]:
        return {"post_id": self.post_id, "region": copy.deepcopy(self.region)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ProposedRegion":
        return cls(post_id=str(d.get("post_id") or ""), region=dict(d.get("region") or {}))


def _ref_of(descriptor: Mapping[str, Any]) -> Tuple[str, str, int]:
    """`(kind, region_id, geometry_rev)` for one descriptor's geometry, or `("", "", 0)`.

    Reads the two shapes `suggestion_service` actually emits. A descriptor with neither is not a
    pointer at all — a relation mark, a reading — and is carried without a resolution requirement.
    """
    geometry = descriptor.get("geometry") if isinstance(descriptor, Mapping) else None
    if not isinstance(geometry, Mapping):
        return ("", "", 0)
    kind = str(geometry.get("kind") or "")
    if kind == GEOMETRY_RASTER:
        ref = geometry.get("mask_ref") or {}
        return (kind, str(ref.get("region_id") or ""), int(ref.get("geometry_rev") or 0))
    if kind == GEOMETRY_NAMING:
        ref = geometry.get("region_ref") or {}
        return (kind, str(ref.get("region_id") or ""), int(ref.get("geometry_rev") or 0))
    return ("", "", 0)


@dataclass(frozen=True)
class PostDelta:
    """What preparation added TO ONE POST. The per-post grouping is the identity rule made
    structural: there is no place to put a Region that is not already qualified by its image."""
    post_id: str
    proposed_regions: Tuple[ProposedRegion, ...] = ()
    suggestions: Tuple[Dict[str, Any], ...] = ()
    # (declared after the two above so `__post_init__` can stamp them)
    #: Region ids already committed on this post when preparation began. A `mask_ref` may resolve
    #: against one of these — a step that measured over a curator's existing region is not a
    #: dangling pointer.
    committed_region_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Stamp every Region with THIS post's id.

        A `ProposedRegion` built straight from a context has no post on it — the context knows which
        image it is and the region dict does not. Leaving it blank would make `region_key` return
        `("", "cseg_fold_0", 0)` for two different images, and the positional-id collision this
        whole identity rule exists to prevent would come back through the object that was supposed
        to prevent it. There is no legitimate way for a region inside a post delta to belong to
        another post, so it is stamped rather than validated.
        """
        stamped = tuple(r if r.post_id == self.post_id
                        else ProposedRegion(post_id=self.post_id, region=r.region)
                        for r in self.proposed_regions)
        object.__setattr__(self, "proposed_regions", stamped)

    def measured_refs(self) -> Tuple[Tuple[str, int], ...]:
        return tuple((rid, rev) for kind, rid, rev in map(_ref_of, self.suggestions)
                     if kind == GEOMETRY_RASTER and rid)

    def naming_refs(self) -> Tuple[Tuple[str, int], ...]:
        return tuple((rid, rev) for kind, rid, rev in map(_ref_of, self.suggestions)
                     if kind == GEOMETRY_NAMING and rid)

    def region_ids(self) -> Tuple[str, ...]:
        return tuple(r.id for r in self.proposed_regions)

    def region(self, region_id: str) -> Optional[ProposedRegion]:
        for candidate in self.proposed_regions:
            if candidate.id == str(region_id):
                return candidate
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"post_id": self.post_id,
                "proposed_regions": [r.to_dict() for r in self.proposed_regions],
                "suggestions": [copy.deepcopy(dict(s)) for s in self.suggestions],
                "committed_region_ids": list(self.committed_region_ids)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PostDelta":
        return cls(post_id=str(d.get("post_id") or ""),
                   proposed_regions=tuple(ProposedRegion.from_dict(r)
                                          for r in d.get("proposed_regions") or ()),
                   suggestions=tuple(dict(s) for s in d.get("suggestions") or ()),
                   committed_region_ids=tuple(str(r) for r in
                                              d.get("committed_region_ids") or ()))


@dataclass(frozen=True)
class PreparedWorldDelta:
    """What a preparation task added to the world. A receipt, never a ledger.

    Nothing here is persisted, nothing is committed, and no mark id is minted. Every Region keeps
    `proposed: True` and every descriptor keeps the status its producer stamped.
    """
    task_id: str
    evidence_goal_id: str
    run_id: str
    step_id: str
    per_post: Tuple[PostDelta, ...] = ()
    production_records: Tuple[Dict[str, Any], ...] = ()
    refusals: Tuple[Dict[str, Any], ...] = ()
    availability: Dict[str, Any] = field(default_factory=dict)
    posts_unchanged: bool = True
    detail: str = ""

    @property
    def region_count(self) -> int:
        return sum(len(p.proposed_regions) for p in self.per_post)

    @property
    def suggestion_count(self) -> int:
        return sum(len(p.suggestions) for p in self.per_post)

    def post(self, post_id: str) -> Optional[PostDelta]:
        for delta in self.per_post:
            if delta.post_id == str(post_id):
                return delta
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "evidence_goal_id": self.evidence_goal_id,
                "run_id": self.run_id, "step_id": self.step_id,
                "per_post": [p.to_dict() for p in self.per_post],
                "production_records": [copy.deepcopy(dict(r)) for r in self.production_records],
                "refusals": [copy.deepcopy(dict(r)) for r in self.refusals],
                "availability": copy.deepcopy(dict(self.availability)),
                "posts_unchanged": self.posts_unchanged, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PreparedWorldDelta":
        return cls(task_id=str(d.get("task_id") or ""),
                   evidence_goal_id=str(d.get("evidence_goal_id") or ""),
                   run_id=str(d.get("run_id") or ""), step_id=str(d.get("step_id") or ""),
                   per_post=tuple(PostDelta.from_dict(p) for p in d.get("per_post") or ()),
                   production_records=tuple(dict(r) for r in d.get("production_records") or ()),
                   refusals=tuple(dict(r) for r in d.get("refusals") or ()),
                   availability=dict(d.get("availability") or {}),
                   posts_unchanged=bool(d.get("posts_unchanged", True)),
                   detail=str(d.get("detail") or ""))


def validate_delta(delta: PreparedWorldDelta) -> PreparedWorldDelta:
    """Refuse a delta that may not be handed to a mission. Returns it when it may.

    Four rules, each of which is a way the world would arrive damaged and still look intact:

      1. every proposed Region carries geometry — a Region with no mask is not somewhere to stand;
      2. every proposed Region is still `proposed` — a receipt that contained a committed Region
         would be a ledger, and this lane commits nothing;
      3. every `mask_ref` resolves inside its own post, or to a Region already committed there;
      4. a naming `region_ref` resolves too, and authors no geometry — it may point at a Region and
         may never BE one.
    """
    for post in delta.per_post:
        available = {r.id for r in post.proposed_regions} | set(post.committed_region_ids)
        by_id = {r.id: r for r in post.proposed_regions}

        for region in post.proposed_regions:
            if not region.has_mask:
                raise WorldDeltaInvalid(
                    f"proposed region {region.id!r} on post {post.post_id!r} carries no mask and no "
                    f"polygons. A region with no geometry is not somewhere an agent can stand, and "
                    f"projecting one would put an empty extent into a world an organ measures from.")
            if not region.proposed:
                raise WorldDeltaInvalid(
                    f"region {region.id!r} on post {post.post_id!r} is not marked proposed. A "
                    f"world delta is an execution receipt; a committed region inside one would "
                    f"make preparation look like an accept path nobody authorised.")

        for descriptor in post.suggestions:
            kind, region_id, rev = _ref_of(descriptor)
            if not kind or not region_id:
                continue                       # not a pointer — a relation mark, a reading
            if region_id not in available:
                raise WorldDeltaInvalid(
                    f"{POINTER_TARGET_MISSING}: descriptor {descriptor.get('producer')!r} on post "
                    f"{post.post_id!r} points at region {region_id!r}, which is neither in this "
                    f"post's delta ({sorted(by_id) or 'none'}) nor already committed on it. A "
                    f"pointer without its target is a well-formed mark citing nothing — every "
                    f"reader downstream would see a mark and no reader would see a mask.")
            target = by_id.get(region_id)
            if target is not None and rev and target.geometry_rev != rev:
                raise WorldDeltaInvalid(
                    f"{POINTER_TARGET_MISSING}: descriptor {descriptor.get('producer')!r} cites "
                    f"{region_id!r} at geometry_rev {rev} and the captured region is at "
                    f"{target.geometry_rev}. A revision is part of the identity because a "
                    f"re-dissect repoints the id at different pixels.")
            if kind == GEOMETRY_NAMING and (descriptor.get("geometry") or {}).get("mask_ref"):
                raise WorldDeltaInvalid(
                    f"naming descriptor {descriptor.get('producer')!r} on post {post.post_id!r} "
                    f"carries a mask reference. A naming authors no geometry — that separation is "
                    f"what lets a reviewer accept the measurement and reject the word.")
    return delta


# ── the ephemeral projection ─────────────────────────────────────────────────

def project_post(post: Mapping[str, Any], delta: PreparedWorldDelta, *,
                 post_id: str = "") -> Dict[str, Any]:
    """A committed post copy + a valid delta → the post an agent's mission perceives from.

    NEVER MUTATES THE SOURCE. The returned document is a deep copy with the proposed Regions
    appended to `region_annotations`, so an organ can measure over them exactly as it measures over
    a curator's own — which is the private-measured half of the existing ruling, and is legitimate:
    the agent's memory records what its organ said, and the shared ledger still reads `proposed`
    because nobody has committed anything.

    A conflicting proposal is REFUSED rather than allowed to replace a committed Region. Same id,
    different geometry, and the committed one wins by not being overwritten — a preparation that
    could silently repoint a curator's region at new pixels would be an accept path wearing a
    receipt's clothes.

    Interpretive namings do NOT enter as regions. They ride along under `proposed_suggestions`,
    where a reader can see them and no organ can stand on them.
    """
    pid = str(post_id or post.get("_id") or post.get("id") or "")
    projected = copy.deepcopy(dict(post))
    post_delta = delta.post(pid)
    if post_delta is None:
        # NOT AN ERROR. A delta that added nothing to this post projects the post unchanged, which
        # is a real and reportable state — and different from a delta that could not be validated.
        projected["projection"] = {"post_id": pid, "added_regions": 0, "from_task": delta.task_id,
                                   "detail": "the preparation added nothing to this post"}
        return projected

    existing = {str(r.get("id")): dict(r) for r in (projected.get("region_annotations") or ())
                if isinstance(r, Mapping)}
    added: List[Dict[str, Any]] = []
    for proposed in post_delta.proposed_regions:
        committed = existing.get(proposed.id)
        if committed is not None:
            same = (committed.get("mask_rle") == proposed.region.get("mask_rle")
                    and int(committed.get("geometry_rev") or 0) == proposed.geometry_rev)
            if not same:
                raise ProjectionRefused(
                    f"proposed region {proposed.id!r} on post {pid!r} collides with a committed "
                    f"region of the same id and different geometry. The committed one stands: a "
                    f"preparation that repointed a curator's region at new pixels would be an "
                    f"accept path nobody authorised, and every id downstream would still look "
                    f"right.")
            continue                            # already there, identically — nothing to add
        region = proposed.as_region()
        # THE LEDGER STATUS DOES NOT MOVE. The geometry is live for this mission and uncommitted
        # for everybody else, and the region says so in the projected world too.
        region["proposed"] = True
        region["ledger_status"] = "proposed"
        added.append(region)

    projected["region_annotations"] = [*(projected.get("region_annotations") or ()), *added]
    # Carried where a reader can see them and no organ can reach them. A naming is a word about an
    # extent; putting one in `region_annotations` would make it a shape.
    projected["proposed_suggestions"] = [copy.deepcopy(dict(s)) for s in post_delta.suggestions]
    projected["projection"] = {
        "post_id": pid,
        "from_task": delta.task_id,
        "from_step": delta.step_id,
        "added_regions": len(added),
        "added_region_ids": [r["id"] for r in added],
        "suggestions": len(post_delta.suggestions),
        "ephemeral": True,
        "detail": ("proposed geometry, live for this mission and uncommitted everywhere else; "
                   "discardable after the run"),
    }
    return projected


def project_world(posts: Mapping[str, Mapping[str, Any]],
                  delta: PreparedWorldDelta) -> Dict[str, Dict[str, Any]]:
    """Every post, projected. The source mapping is untouched — checked by the caller's fingerprint
    and by `test_inquiry_handoff_vertical`."""
    return {str(pid): project_post(post, delta, post_id=str(pid)) for pid, post in posts.items()}


def locus_available(projected_post: Mapping[str, Any], region_id: str) -> bool:
    """Does the mission's locus resolve to a region in the projected post — committed or proposed?

    Asked before dispatch so `no_locus` is a decomposed reason rather than an organ refusal that a
    reader would have to interpret.
    """
    for region in projected_post.get("region_annotations") or ():
        if isinstance(region, Mapping) and str(region.get("id")) == str(region_id):
            return True
    return False


__all__ = [
    "GEOMETRY_RASTER", "GEOMETRY_NAMING", "HANDOFF_REASONS",
    "MEASURED_ABSENCE", "PLANNER_EMPTY", "EXECUTION_UNAVAILABLE", "POINTER_TARGET_MISSING",
    "NO_LOCUS", "ORGAN_REFUSED",
    "WorldDeltaInvalid", "ProjectionRefused", "region_key",
    "ProposedRegion", "PostDelta", "PreparedWorldDelta", "validate_delta",
    "project_post", "project_world", "locus_available",
]
