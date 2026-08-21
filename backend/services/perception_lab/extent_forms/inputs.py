"""
PERCEPTUAL-FORMS-001B — what a derivation is handed, and the receipt it carries out.

THE PROVENANCE IS NOT DECORATION. `extent.boundary_rings` and `extent.hole_set` both declare
`required_provenance: [producer_kind, producer, source_image_digest, revision]`, and a derivation
that dropped any of those would produce a ring nobody could tie back to the picture it came from.
So every entry point here takes the digest of the source image and refuses without it, and hands
back a `DerivationProvenance` holding the digest, the algorithm revision, the artifact and
instance each output came from, and the geometry revision each of those was pinned at.

WHY IT IS NOT AN `ArtifactProvenance`. That record requires `producer_kind`, whose four values are
`adapter`, `human`, `fixture` and `replay` — and an exact derivation is none of them. Choosing one
here would stamp a per-pixel derivation as something it is not, in the field a later report reads
to decide whether a person or a model made a shape. So this package carries the four facts it
knows and leaves the fifth to the lane that registers the operation, which will have to answer it.

A BOX IS NOT A MASK, AND THAT IS WHY `skipped_without_mask` EXISTS. GroundingDINO returns boxes;
`extent.py` keeps them and stamps `basis: box`. There is no boundary of a box worth tracing and no
void inside one, so an instance with no mask is not traced — and it is NOT silently absent from
the answer either. `source_extents` returns the skipped references beside the usable ones, the
form payloads have nowhere to record them, and the caller therefore has to hold them. That is the
whole design: the omission is in the return type, so it cannot be forgotten by not being noticed.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (CoordinateSystem, EpistemicBasis, EpistemicPartition,
                                            IdentityScope, InputRef, InstanceRef, PerceptualForm,
                                            RefusalCode)
from backend.services.perception_lab.extent_forms.raster import Raster, raster_of, refuse

#: What this package IS, in a producer field. One string, so a run record naming it can be
#: grepped, and versioned separately from the tree so a change in the tracer is visible in every
#: artifact derived after it.
PRODUCER = "perception_lab.extent_forms"
DERIVATION_REVISION = "extent-exact-forms.v1"

#: The role every extent input is consumed as. `extent.boundary_rings` and `extent.hole_set` both
#: declare `accepted_input_forms: [extent.hard_mask]`, and this is the word for that consumption.
INPUT_ROLE = "extent"

#: The shortest digest `ArtifactProvenance.source_image_digest` accepts. Repeated rather than
#: imported because the constraint lives inside a pydantic `Field`; the test holds the two equal.
MIN_DIGEST = 8


@dataclass(frozen=True)
class SourceExtent:
    """One masked extent, decoded, and everything needed to point back at where it came from."""
    artifact_id: str
    instance_id: str
    raster: Raster
    geometry_rev: Optional[int] = None
    region_id: Optional[str] = None

    @property
    def ref(self) -> InstanceRef:
        return InstanceRef(artifact_id=self.artifact_id, instance_id=self.instance_id)

    @property
    def key(self) -> str:
        return f"{self.artifact_id}#{self.instance_id}"

    @property
    def scope(self) -> IdentityScope:
        return IdentityScope.CANONICAL if self.region_id else IdentityScope.SESSION

    @property
    def input_ref(self) -> InputRef:
        """The instance-deep reference — never the whole artifact.

        A boundary derived from `inst_2` was derived from `inst_2`, and an input ref naming only
        the artifact would let a reader think the other seven masks in it were consulted.
        """
        return InputRef(role=INPUT_ROLE, scope=self.scope, artifact_id=self.artifact_id,
                        instance_id=self.instance_id, geometry_rev=self.geometry_rev)


def source_extent(artifact_id: str, instance: Any, *,
                  raster_shape: Optional[Sequence[int]] = None) -> SourceExtent:
    """One `ExtentInstance` — model or mapping — decoded into a derivable extent.

    `raster_shape` IS A CHECK, NOT A RESIZE. A caller that already knows what raster this instance
    was measured on passes it, and a mask that disagrees is REFUSED rather than resampled onto the
    declared one. Resampling would produce a shape that is a plausible-looking answer to a
    question nobody asked: the derivation would succeed, the rings would be smooth, and every
    number in them would belong to a raster the measurement was never taken on.
    """
    data = instance if isinstance(instance, Mapping) else instance.model_dump()
    instance_id = str(data.get("instance_id") or "")
    if not instance_id:
        refuse(RefusalCode.MISSING_EXTENT_INPUTS,
               f"an instance of {artifact_id!r} carries no instance_id. An instance id is unique "
               f"inside its artifact and nowhere else, so one that is missing names nothing.",
               missing=["instance_id"])
    what = f"{artifact_id}#{instance_id}"
    raster = raster_of(data.get("mask_rle"), what=what)
    if raster_shape is not None:
        declared = tuple(int(v) for v in raster_shape)
        if declared != raster.shape:
            refuse(RefusalCode.INVALID_PARAMETERS,
                   f"{what} was declared on a {declared[0]}x{declared[1]} raster and its mask is "
                   f"{raster.h}x{raster.w}. Two rasters is two pictures, and resampling one onto "
                   f"the other would report a measurement that was never taken.",
                   detail={"declared_raster": list(declared), "mask_raster": list(raster.shape)},
                   remedy="supply the mask that was measured on the declared raster")
    rev = data.get("geometry_rev")
    return SourceExtent(artifact_id=str(artifact_id), instance_id=instance_id, raster=raster,
                        geometry_rev=None if rev is None else int(rev),
                        region_id=data.get("region_id") or None)


def source_extents(artifact_id: str, payload: Any
                   ) -> Tuple[Tuple[SourceExtent, ...], Tuple[InstanceRef, ...]]:
    """Every derivable instance of an `extent_set`, and every one that had no mask.

    TWO RETURN VALUES, ALWAYS. See the module docstring: a box-only instance is not traceable and
    is not absent either, and the only way to make that impossible to forget is to make the caller
    unpack it.
    """
    data = payload if isinstance(payload, Mapping) else payload.model_dump()
    usable: List[SourceExtent] = []
    skipped: List[InstanceRef] = []
    for raw in data.get("instances") or []:
        item = raw if isinstance(raw, Mapping) else raw.model_dump()
        if item.get("mask_rle") is None:
            skipped.append(InstanceRef(artifact_id=str(artifact_id),
                                       instance_id=str(item.get("instance_id") or "?")))
            continue
        usable.append(source_extent(artifact_id, item))
    return tuple(usable), tuple(skipped)


# ── the receipt ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DerivationProvenance:
    """What a derived payload came from. Four of the five fields a form's receipt requires."""
    producer: str
    revision: str
    source_image_digest: str
    derived_from: Tuple[str, ...]
    input_refs: Tuple[InputRef, ...]
    coordinate_system: CoordinateSystem
    epistemic_basis: EpistemicBasis
    partition: EpistemicPartition
    rasters: Mapping[str, Tuple[int, int]]
    geometry_revs: Mapping[str, Optional[int]]


@dataclass(frozen=True)
class Derived:
    """A payload, its receipt, the exact numbers the payload has no field for, and the omissions.

    `measurements` IS NOT A SECOND PAYLOAD. Centroids, separations and perimeters are facts ABOUT
    the pieces a form names, and every form payload in this contract is `extra="forbid"`. They are
    returned here as plain data, keyed by the id they describe, so nothing has to grow a field and
    nothing has to be thrown away.
    """
    form: PerceptualForm
    payload: Any
    provenance: DerivationProvenance
    measurements: Mapping[str, Any] = field(default_factory=dict)
    skipped_without_mask: Tuple[InstanceRef, ...] = ()


def provenance_for(extents: Sequence[SourceExtent], *, source_image_digest: str
                   ) -> DerivationProvenance:
    """The receipt for a derivation over these extents. Refuses without a real digest.

    THE DIGEST IS WHAT MAKES THE DERIVATION FALSIFIABLE. A ring traced today from a mask measured
    yesterday is only trustworthy while the picture underneath both is the same picture, and a
    receipt with no digest cannot be shown to have gone stale.
    """
    digest = str(source_image_digest or "")
    if len(digest) < MIN_DIGEST:
        refuse(RefusalCode.INVALID_PARAMETERS,
               f"source_image_digest is {len(digest)} characters and a receipt needs at least "
               f"{MIN_DIGEST}. A derivation whose source cannot be identified cannot be shown to "
               f"have gone stale, which is worse than one that is known to be.",
               missing=["source_image_digest"])
    seen: List[str] = []
    for extent in extents:
        if extent.artifact_id not in seen:
            seen.append(extent.artifact_id)
    return DerivationProvenance(
        producer=PRODUCER, revision=DERIVATION_REVISION, source_image_digest=digest,
        derived_from=tuple(seen),
        input_refs=tuple(e.input_ref for e in extents),
        coordinate_system=CoordinateSystem.NORMALIZED_XY_TOPLEFT,
        epistemic_basis=EpistemicBasis.MASK,
        partition=EpistemicPartition.EXACT_DERIVATION,
        rasters={e.key: e.raster.shape for e in extents},
        geometry_revs={e.key: e.geometry_rev for e in extents})


def one_raster(extents: Sequence[SourceExtent], *, what: str) -> Tuple[int, int]:
    """The shared raster of these extents, or a refusal naming the ones that disagree.

    USED WHERE THE PAYLOAD HAS NOWHERE TO PUT A SECOND RASTER, and nowhere else.
    `ExtentFragmentSetPayload` counts `regions_examined` over one image and holds a flat list of
    pieces; two rasters in one of those is two answers in one record, and a reader comparing the
    normalized areas of a piece from an 800x600 mask and a piece from a 200x150 one would be
    comparing fractions of two different frames. `InstanceBoundary` carries its own `raster_shape`
    and `ExtentHole` carries its own mask, so neither is asked this question.
    """
    shapes = {e.key: e.raster.shape for e in extents}
    distinct = sorted(set(shapes.values()))
    if len(distinct) > 1:
        refuse(RefusalCode.INVALID_PARAMETERS,
               f"{what} was given extents on {len(distinct)} different rasters "
               f"{[list(s) for s in distinct]}. This form holds one flat list of pieces of ONE "
               f"image and has no field in which a second raster could be named, so the areas in "
               f"it would be fractions of two different frames.",
               detail={"rasters": {k: list(v) for k, v in sorted(shapes.items())}},
               remedy="derive one fragment set per raster")
    return distinct[0] if distinct else (0, 0)


__all__ = ["DERIVATION_REVISION", "Derived", "DerivationProvenance", "INPUT_ROLE", "MIN_DIGEST",
           "PRODUCER", "SourceExtent", "one_raster", "provenance_for", "source_extent",
           "source_extents"]
