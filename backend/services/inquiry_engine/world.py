"""
HARNESS-001B2 §1 — `PreparedWorldDelta`: what preparation ADDED, without implying it was kept.

## The object that was missing, and the failure that named it

HARNESS-001B's `DirectorAdapter` reads `ActuatorResult.payload` and calls what it finds
"suggestions". That is not where production puts its evidence. A real `concept_segment` step does
three things, in this order:

    svc.instances_to_regions(result)     the masks become PROPOSED Regions, which OWN the mask_rle
    ctx.regions.extend(regions)          → ExecutionContext.regions
    ctx.suggestions.extend(descriptors)  → ExecutionContext.suggestions, TWO per instance:
                                             a `measured` extent whose geometry is
                                                 {"kind": "raster_mask",
                                                  "mask_ref": {"region_id": …}}
                                             an `interpretive` naming whose geometry is
                                                 {"kind": "region_ref",
                                                  "region_ref": {"region_id": …}}

and returns a payload of COUNTS (`{"concept": …, "instances": 2, "latency_ms": …}`).

The mark contract forbids a suggestion from inlining its own mask — `validateMark` requires
`mask_ref.region_id` — so the mask exists in exactly one place, the Region. A capture that reads
only the payload therefore gets a count; a capture that reads only `ctx.suggestions` gets a
POINTER WITH NO TARGET. Either way the measurement is gone, and nothing raises: the descriptor is
well-formed, it names a region id, and the region it names does not exist anywhere the consumer
can see. Downstream that is not an error, it is an agent standing in an empty room.

So the delta carries both halves, and refuses to be handed to a mission unless every pointer
resolves.

## Identity is POST-QUALIFIED, and this is not a detail

A Region resolves under `(post_id, region_id, geometry_rev)` and never under `region_id` alone.
SAM 3's instance ids are POSITIONAL — `instances_to_regions` mints `cseg_<concept>_<index>` — so
the same concept run on two images produces `cseg_fold_0` on both. Under a global key the second
would shadow the first, an agent on image B would perceive image A's mask, and every reading it
returned would be well-formed and about the wrong picture.

`geometry_rev` rides along for the same reason it exists on a committed Region: a mask that was
re-cut is a different extent under the same name.

## It is a receipt, not a ledger

Every Region keeps `proposed: True`. Every descriptor keeps its producer's epistemic status and
its run/step provenance. Nothing here mints a committed mark id, and nothing here writes.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

# ── refusal reasons ──────────────────────────────────────────────────────────
#: Six named reasons, and the reason there are six rather than one `no_new_evidence`: each names a
#: DIFFERENT thing that went wrong, and a caller that collapsed them would report "nothing found"
#: for a missing instrument, a missing target and a measured absence alike. §4 of the directive
#: forbids the flattening until the top-level stop event, and even there the detail survives.
MEASURED_ABSENCE = "measured_absence"            # it ran, it looked, there is nothing there
PLANNER_EMPTY = "planner_empty"                  # nothing was planned to run at all
EXECUTION_UNAVAILABLE = "execution_unavailable"  # the instrument exists and did not run
POINTER_TARGET_MISSING = "pointer_target_missing"  # a descriptor names a Region nobody captured
NO_LOCUS = "no_locus"                            # nowhere in the projected post to stand
ORGAN_REFUSED = "organ_refused"                  # the body refused this locus

DELTA_REFUSALS: Tuple[str, ...] = (MEASURED_ABSENCE, PLANNER_EMPTY, EXECUTION_UNAVAILABLE,
                                   POINTER_TARGET_MISSING, NO_LOCUS, ORGAN_REFUSED)

#: A descriptor's geometry kinds, and which of them points at a Region.
KIND_RASTER_MASK = "raster_mask"
KIND_REGION_REF = "region_ref"


class DeltaRefused(Exception):
    """A delta that may not be handed to a mission. Raised rather than filtered.

    A silently dropped descriptor would leave the caller believing an agent had been given
    evidence it never saw, and the run would report a smaller world with no explanation — the same
    argument `ProposalNotAPerception` makes one seam over.
    """


# ── identity ─────────────────────────────────────────────────────────────────

def region_key(post_id: Any, region_id: Any, geometry_rev: Any = 0) -> Tuple[str, str, int]:
    """The only key a Region may be resolved under.

    Three parts, and dropping any one of them is a real failure that has a name:
      · without `post_id`, `cseg_fold_0` on two images is one Region and an agent perceives the
        wrong picture;
      · without `region_id` there is nothing to point at;
      · without `geometry_rev` a re-cut mask silently substitutes for the extent that was measured.
    """
    try:
        rev = int(geometry_rev or 0)
    except (TypeError, ValueError):
        rev = 0
    return (str(post_id or ""), str(region_id or ""), rev)


def pointer_of(descriptor: Mapping[str, Any]) -> Optional[Tuple[str, int]]:
    """`(region_id, geometry_rev)` this descriptor points at, or None if it points at nothing.

    Reads BOTH shapes, because the two halves of a concept segmentation use different ones on
    purpose: the measured extent carries `mask_ref` and the interpretive naming carries
    `region_ref`, so review can accept one and reject the other and still know which mask was
    meant. A reader that knew only `mask_ref` would silently treat every naming as pointing at
    nothing.
    """
    geometry = descriptor.get("geometry")
    if not isinstance(geometry, Mapping):
        return None
    for key in ("mask_ref", "region_ref"):
        ref = geometry.get(key)
        if isinstance(ref, Mapping) and ref.get("region_id"):
            try:
                rev = int(ref.get("geometry_rev") or 0)
            except (TypeError, ValueError):
                rev = 0
            return (str(ref["region_id"]), rev)
    return None


def authors_geometry(descriptor: Mapping[str, Any]) -> bool:
    """Does this descriptor CARRY a mask rather than point at one?

    A naming authors no geometry — that is its whole discipline — and a naming that arrived with a
    mask inline would have smuggled the interpretive half into the measured object. Inline
    geometry is also silently dropped at frontend intake, so it fails invisibly in production and
    must fail loudly here.
    """
    geometry = descriptor.get("geometry")
    if not isinstance(geometry, Mapping):
        return False
    if geometry.get("mask_rle") or geometry.get("rle") or geometry.get("polygon"):
        return True
    ref = geometry.get("region_ref")
    return bool(isinstance(ref, Mapping) and (ref.get("mask_rle") or ref.get("polygons")))


def region_has_mask(region: Mapping[str, Any]) -> bool:
    """Does this Region actually own an extent?

    A Region with no mask and no polygons is a name with nothing under it. Admitting a `measured`
    descriptor that points at one would be a measurement resting on an absence.
    """
    if region.get("mask_rle"):
        return True
    polygons = region.get("polygons")
    return bool(isinstance(polygons, (list, tuple)) and polygons)


# ── the per-post half ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PostDelta:
    """What preparation added TO ONE POST. Regions first, because the descriptors point into them.

    `committed_region_ids` is what the source post already carried. It is held so a pointer into a
    committed Region resolves without the delta having to copy the Region — copying it would
    create a second geometry for one extent, which is PROV-001's two-copy drift arriving through
    the back door.
    """
    post_id: str
    proposed_regions: Tuple[Dict[str, Any], ...] = ()
    suggestions: Tuple[Dict[str, Any], ...] = ()
    committed_region_ids: Tuple[str, ...] = ()

    def region_ids(self) -> Tuple[str, ...]:
        return tuple(str(r.get("id") or "") for r in self.proposed_regions)

    def region(self, region_id: str) -> Optional[Dict[str, Any]]:
        for candidate in self.proposed_regions:
            if str(candidate.get("id") or "") == str(region_id):
                return dict(candidate)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"post_id": self.post_id,
                "proposed_regions": [dict(r) for r in self.proposed_regions],
                "suggestions": [dict(s) for s in self.suggestions],
                "committed_region_ids": list(self.committed_region_ids)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PostDelta":
        return cls(post_id=str(d.get("post_id") or ""),
                   proposed_regions=tuple(dict(r) for r in d.get("proposed_regions") or ()),
                   suggestions=tuple(dict(s) for s in d.get("suggestions") or ()),
                   committed_region_ids=tuple(str(r) for r in
                                              d.get("committed_region_ids") or ()))


# ── the delta ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PreparedWorldDelta:
    """An execution receipt: what a preparation task added, per post, and nothing about keeping it.

    `posts_unchanged` is a CHECKED field, not a claim in a docstring — the capture fingerprints the
    source posts before and after and writes the answer here.
    """
    task_id: str = ""
    evidence_goal_id: str = ""
    run_id: str = ""
    inquiry_id: str = ""
    step_ids: Tuple[str, ...] = ()
    per_post: Tuple[PostDelta, ...] = ()
    production_records: Tuple[Dict[str, Any], ...] = ()
    refusals: Tuple[Dict[str, Any], ...] = ()
    availability: str = ""
    posts_unchanged: bool = True
    detail: str = ""

    # ── reading ──

    def post_ids(self) -> Tuple[str, ...]:
        return tuple(d.post_id for d in self.per_post)

    def for_post(self, post_id: str) -> Optional[PostDelta]:
        for delta in self.per_post:
            if delta.post_id == str(post_id):
                return delta
        return None

    def proposed_region_count(self) -> int:
        return sum(len(d.proposed_regions) for d in self.per_post)

    def suggestion_count(self) -> int:
        return sum(len(d.suggestions) for d in self.per_post)

    def keys(self) -> Tuple[Tuple[str, str, int], ...]:
        """Every proposed Region, post-qualified. Two posts carrying `cseg_fold_0` yield two."""
        return tuple(region_key(d.post_id, r.get("id"), r.get("geometry_rev"))
                     for d in self.per_post for r in d.proposed_regions)

    def has_usable_region(self) -> bool:
        return any(region_has_mask(r) for d in self.per_post for r in d.proposed_regions)

    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "evidence_goal_id": self.evidence_goal_id,
                "run_id": self.run_id, "inquiry_id": self.inquiry_id,
                "step_ids": list(self.step_ids),
                "per_post": [d.to_dict() for d in self.per_post],
                "production_records": [dict(r) for r in self.production_records],
                "refusals": [dict(r) for r in self.refusals],
                "availability": self.availability, "posts_unchanged": self.posts_unchanged,
                "detail": self.detail}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "PreparedWorldDelta":
        return cls(task_id=str(d.get("task_id") or ""),
                   evidence_goal_id=str(d.get("evidence_goal_id") or ""),
                   run_id=str(d.get("run_id") or ""),
                   inquiry_id=str(d.get("inquiry_id") or ""),
                   step_ids=tuple(str(s) for s in d.get("step_ids") or ()),
                   per_post=tuple(PostDelta.from_dict(p) for p in d.get("per_post") or ()),
                   production_records=tuple(dict(r) for r in d.get("production_records") or ()),
                   refusals=tuple(dict(r) for r in d.get("refusals") or ()),
                   availability=str(d.get("availability") or ""),
                   posts_unchanged=bool(d.get("posts_unchanged", True)),
                   detail=str(d.get("detail") or ""))


# ── validation ───────────────────────────────────────────────────────────────

def _refusal(reason: str, detail: str, **extra: Any) -> Dict[str, Any]:
    return {"reason": reason, "detail": detail, **extra}


def validate_delta(delta: PreparedWorldDelta) -> List[Dict[str, Any]]:
    """Every reason this delta may not be projected. Empty means it may.

    Returns rather than raises, because the caller records these as run events: a refusal that
    only existed as an exception message would not survive into the receipt, and "which pointer
    failed to resolve" is exactly the thing somebody will want three weeks later.

    Four checks, each with a failure that has actually happened somewhere in this codebase:

      1. a pointer whose target is in NEITHER the delta nor the post's committed regions;
      2. a `measured` descriptor pointing at a Region that owns no extent;
      3. a naming that carries geometry instead of referencing it;
      4. two proposals for one `(post_id, region_id)` whose geometry differs.
    """
    problems: List[Dict[str, Any]] = []

    for post_delta in delta.per_post:
        by_id: Dict[str, Dict[str, Any]] = {}
        for region in post_delta.proposed_regions:
            rid = str(region.get("id") or "")
            if not rid:
                problems.append(_refusal(
                    POINTER_TARGET_MISSING,
                    "a proposed Region carries no id, so nothing can point at it and nothing can "
                    "say which extent it is", post_id=post_delta.post_id))
                continue
            previous = by_id.get(rid)
            if previous is not None and _geometry_of(previous) != _geometry_of(region):
                # A same-id/different-geometry pair is refused rather than resolved. Picking one
                # would substitute an extent nobody chose for the one that was measured.
                problems.append(_refusal(
                    POINTER_TARGET_MISSING,
                    f"two proposed Regions on post {post_delta.post_id!r} both claim id {rid!r} "
                    f"with different geometry; a pointer to it would resolve to whichever was "
                    f"captured last", post_id=post_delta.post_id, region_id=rid))
            by_id[rid] = dict(region)

        resolvable = set(by_id) | {str(r) for r in post_delta.committed_region_ids}

        for descriptor in post_delta.suggestions:
            producer = str(descriptor.get("producer") or "")
            pointer = pointer_of(descriptor)
            if pointer is None:
                # Not every descriptor points at a Region — a relation or a reading need not — so
                # this is not a refusal. It is simply outside this check.
                continue
            rid, _rev = pointer
            if rid not in resolvable:
                problems.append(_refusal(
                    POINTER_TARGET_MISSING,
                    f"descriptor from {producer or 'an unnamed producer'} points at region "
                    f"{rid!r} on post {post_delta.post_id!r}, and no proposed or committed Region "
                    f"there has that id. The mask lives on the Region and the descriptor only "
                    f"names it, so this is a mark with nothing under it.",
                    post_id=post_delta.post_id, region_id=rid, producer=producer))
                continue
            target = by_id.get(rid)
            status = str(descriptor.get("epistemic_status") or "")
            if status == "measured" and target is not None and not region_has_mask(target):
                problems.append(_refusal(
                    POINTER_TARGET_MISSING,
                    f"a measured descriptor points at region {rid!r} on post "
                    f"{post_delta.post_id!r}, which owns no mask and no polygons. A measurement "
                    f"resting on an absent extent is the fabrication the two-status split exists "
                    f"to prevent.",
                    post_id=post_delta.post_id, region_id=rid, producer=producer))
            if authors_geometry(descriptor) and status != "measured":
                problems.append(_refusal(
                    POINTER_TARGET_MISSING,
                    f"a {status or 'non-measured'} descriptor from {producer!r} carries geometry "
                    f"inline instead of referencing a Region. A naming authors no geometry, and "
                    f"an inlined mask is dropped silently at intake rather than refused.",
                    post_id=post_delta.post_id, region_id=rid, producer=producer))

    return problems


def _geometry_of(region: Mapping[str, Any]) -> Tuple[Any, Any, Any]:
    return (region.get("mask_rle"), region.get("polygons"), region.get("geometry_rev"))


def assert_projectable(delta: PreparedWorldDelta) -> None:
    """Raise unless every pointer in this delta resolves. The gate in front of a mission."""
    problems = validate_delta(delta)
    if problems:
        raise DeltaRefused("; ".join(str(p.get("detail")) for p in problems))


__all__ = [
    "MEASURED_ABSENCE", "PLANNER_EMPTY", "EXECUTION_UNAVAILABLE", "POINTER_TARGET_MISSING",
    "NO_LOCUS", "ORGAN_REFUSED", "DELTA_REFUSALS", "KIND_RASTER_MASK", "KIND_REGION_REF",
    "DeltaRefused", "region_key", "pointer_of", "authors_geometry", "region_has_mask",
    "PostDelta", "PreparedWorldDelta", "validate_delta", "assert_projectable",
]
