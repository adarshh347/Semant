"""
PERCEPTUAL-FORMS-001G — what a composite Extent producer is handed, and what it may read off it.

COMPOSITES CONSUME SUPPLIED EXTENTS AND NEVER GO AND GET THEIR OWN. Lane C's rule, inherited
through Lane D without softening: nothing in this package segments anything, opens an image, or
asks an adapter a question. It takes measurements that exist — a hard mask set, a fragment set, a
containment reading — and assembles claims ON TOP OF them, which is a different act with a
different ceiling.

TWO SHAPES OF INPUT, AND THE SECOND ONE IS NOT A CONVENIENCE. `extent.hard_mask` is `enabled` and
six operations produce it, so it arrives as a `PerceptualArtifact`. `extent.fragment_set` and
`extent.boundary_rings` are `experimental` with no operation declaring them, so no artifact of
either can exist — `PerceptualArtifact` refuses a form no operation produces. A producer that
accepted only artifacts could therefore never be handed the very input its contract entry names.
So the carried `(artifact_id, payload)` pair Lane D built for the same reason is reused here
rather than reinvented, and the deferral it steps around is checked separately and reported on the
production.

WHY THE ARTIFACT FORM MATTERS WHERE IT EXISTS. Three laws have nowhere else to live: the input
form gate (`check_input_forms` refuses a soft field where a hard mask was wanted), the derived
ceiling (an assembly may claim no more than the weakest artifact under it, which is a fact about
artifacts and not about instances), and provenance (`input_artifact_ids` is what lets a reader
walk back from a hypothesis to the pixels).

IDENTITY IS `artifact_id#instance_id`, THE SAME STRING LANE D AND LANE E ALREADY KEY ON. An
instance id is unique inside its artifact and nowhere else. A label is never part of an identity:
two masks a person called "the tree" are two instances, and merging them by name would assert the
very grouping `extent.fused_hypothesis` exists to make visible.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from backend.schemas.perception_lab import (EpistemicBasis, EpistemicStatus, ExtentFragment,
                                            ExtentInstance, InstanceRef, PerceptualArtifact)
from backend.services.perception_lab.topology_forms.sources import (Carried, Supplied, as_artifact,
                                                                    carried)

#: The form each source claims to be, so `check_input_forms` has something true to check.
HARD_MASK = "extent.hard_mask"
FRAGMENT_SET = "extent.fragment_set"
BOUNDARY_RINGS = "extent.boundary_rings"
FUSED_HYPOTHESIS = "extent.fused_hypothesis"


class NotAnExtentSet(TypeError):
    """The supplied artifact is not an `extent_set`. Raised rather than refused, for the reason
    Lane D's `NotARelationSet` gives: this is a caller handing the wrong TYPE, and the typed
    refusal for a person supplying the wrong ARTIFACT is `check_input_forms`."""


@dataclass(frozen=True)
class ExtentSource:
    """One artifact or carried payload of extents, as these producers read it.

    `examined` IS CARRIED THROUGH AND NEVER RECOUNTED. It is the field that separates a measured
    emptiness from an absence of measurement — `searched` on a hard mask set, `regions_examined`
    on a fragment set — and a composition that recomputed it from the members it received would
    report `0` for a set that looked at six things and found nothing, turning the one honest empty
    record into the dishonest one.
    """
    artifact_id: str
    form_key: str
    members: Tuple[Any, ...]
    examined: int
    epistemic_status: EpistemicStatus
    epistemic_basis: EpistemicBasis
    searched: Optional[str] = None

    def keys(self) -> Tuple[str, ...]:
        return tuple(f"{self.artifact_id}#{self._id(m)}" for m in self.members)

    @staticmethod
    def _id(member: Any) -> str:
        return getattr(member, "instance_id", None) or getattr(member, "fragment_id")

    def ref(self, member_id: str) -> InstanceRef:
        return InstanceRef(artifact_id=self.artifact_id, instance_id=str(member_id))


def extent_set(supplied: Supplied) -> ExtentSource:
    """An `extent.hard_mask` artifact, read.

    The artifact-level status and basis are taken from the MEASUREMENT block the façade wrote
    after weighing every instance, never re-derived from the instances here. A set holding one
    box-basis instance was already ruled interpretive by the thing that measured it, and a second
    opinion computed downstream would be a second answer to a settled question.
    """
    artifact = as_artifact(supplied)
    payload = artifact.measurement.payload
    if getattr(payload, "variant", None) != "extent_set":
        raise NotAnExtentSet(
            f"{artifact.identity.artifact_id} carries {getattr(payload, 'variant', None)!r}; "
            f"a composite Extent form reads an extent_set")
    return ExtentSource(
        artifact_id=artifact.identity.artifact_id, form_key=HARD_MASK,
        members=tuple(payload.instances), examined=len(payload.instances),
        epistemic_status=artifact.measurement.epistemic_status,
        epistemic_basis=artifact.measurement.epistemic_basis,
        searched=payload.searched)


def fragment_set(supplied: Carried, *,
                 epistemic_status: EpistemicStatus = EpistemicStatus.MEASURED,
                 epistemic_basis: EpistemicBasis = EpistemicBasis.MASK) -> ExtentSource:
    """An `extent.fragment_set` payload, carried with the id its artifact WOULD have.

    THE STATUS IS THE CALLER'S TO DECLARE AND IT DEFAULTS TO THE STRONGEST, which is safe only
    because it is then CAPPED by everything downstream: a fusion over these fragments is an
    `interpretive_grouping` and cannot exceed `interpretive` whatever the members claim. Defaulting
    to `measured` here rather than to `uncertain` keeps the cap where the contract puts it — on
    the act, not on the evidence — so a reader who sees `interpretive` knows it was the GROUPING
    that capped it and not a pessimistic default nobody chose.
    """
    artifact_id, payload = carried(supplied)
    if getattr(payload, "variant", None) != "extent_fragment_set":
        raise NotAnExtentSet(
            f"{artifact_id} carries {getattr(payload, 'variant', None)!r}; a fragment source "
            f"reads an extent_fragment_set")
    return ExtentSource(
        artifact_id=artifact_id, form_key=FRAGMENT_SET, members=tuple(payload.fragments),
        examined=payload.regions_examined, epistemic_status=epistemic_status,
        epistemic_basis=epistemic_basis)


def index(sources: Sequence[ExtentSource]) -> Dict[str, Tuple[ExtentSource, Any]]:
    """`art#inst` → the source that holds it and the member itself.

    A DUPLICATE KEY IS A CALLER ERROR AND NOT A MERGE. Two sources carrying the same artifact id
    would make one key mean two members, and quietly keeping the last one would silently choose
    which measurement a hypothesis cites.
    """
    out: Dict[str, Tuple[ExtentSource, Any]] = {}
    for source in sources:
        for member in source.members:
            key = f"{source.artifact_id}#{ExtentSource._id(member)}"
            if key in out:
                raise NotAnExtentSet(
                    f"{key} is held by two supplied sources. One key naming two measurements "
                    f"would let a composition cite either of them and record neither.")
            out[key] = (source, member)
    return out


def geometry_of(member: Any) -> Tuple[Optional[Mapping[str, Any]], Optional[Any]]:
    """`(mask_rle, box)` off either member type. The mask is the identity; the box is a fallback."""
    return getattr(member, "mask_rle", None), getattr(member, "box", None)


def area_of(member: Any) -> Optional[float]:
    return getattr(member, "area", None)


__all__ = ["BOUNDARY_RINGS", "EpistemicBasis", "EpistemicStatus", "ExtentSource", "FRAGMENT_SET", "FUSED_HYPOTHESIS", "HARD_MASK",
           "NotAnExtentSet", "area_of", "extent_set", "fragment_set", "geometry_of", "index"]
