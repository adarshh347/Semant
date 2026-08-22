"""
PERCEPTUAL-FORMS-001G — `extent.visible_inferred_partition`: what we saw, what we inferred, and
what we do not know.

THE PERSON BEHIND THE TABLE. The head and torso were seen; the legs were not; the part that runs
off the frame is settled by nothing. One mask covering all three is a claim the picture does not
support, and a mask covering only the torso throws away a reading worth keeping. Three parts,
three statuses, and the schema refuses `visible` or `measured` on the inferred one at any
confidence — Lane C's rule for every amodal output, enforced by a record shape rather than by a
reviewer.

NO MODEL PRODUCES THIS FORM TODAY AND THIS LANE DOES NOT PRETEND OTHERWISE. Both candidates Lane C
looked at are deferred: pix2gestalt needs 22-28 GB against a 10 GB budget, and Amodal SAM had no
published checkpoint on 2026-08-22. So the parts arrive from a person's brush or from a fixture,
`admission.producer_for` refuses with both verdicts named, and nothing is substituted. Manual and
fixture production is the route until a checkpoint exists and its hallucinated-structure rate has
been measured.

THE PARTS MAY NOT OVERLAP, AND AN OVERLAP REFUSES THE WHOLE PARTITION. This is the one rule the
form is for. If a pixel is in both the visible part and the inferred part, then the record cannot
say which it is — and the failure mode is precise: a reader drawing the tricolour would paint it
in whichever colour their loop reached last, so a hallucinated leg would appear in the same key as
a photographed one. There is no partial answer worth returning here, because every part of it is
contaminated by the ambiguity.

THE VISIBLE PART IS REQUIRED. `of` names an extent somebody measured, and a partition of it with
no visible region contradicts the thing it partitions. The absence semantics say the same from the
other side: an empty answer means "the extent was partitioned and nothing fell outside the visible
part", which presupposes there is one.

COVERAGE IS COMPUTED, NEVER TRUSTED. A supplied coverage beside a supplied mask is two numbers
that can disagree, and the schema checks their SUM without being able to check either. So mask
parts get their coverage measured off the mask, and only a field part — which has no pixels to
count — may declare one.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (STATUS_ORDER, EpistemicBasis, EpistemicStatus,
                                            ExtentPartitionPayload, PartitionPart,
                                            PartitionRegion, RefusalCode, RefusalRecord,
                                            ScalarFieldSpec)
from backend.services.perception_lab import extent_metrics as M
from backend.services.perception_lab.extent_composites import sources as SRC
from backend.services.perception_lab.extent_composites.compose import (ORGAN, admissible_basis,
                                                                       produce)
from backend.services.perception_lab.topology_forms.production import FormProduction, Omission

FORM = "extent.visible_inferred_partition"

#: The two partitions this form admits. A record holding an inferred part asserts pixels nobody
#: saw, and that is an `inferred_completion` whatever else is in it.
COMPLETION = "inferred_completion"
MEASURED = "visible_measured"

#: What each part may claim, restated from the schema so this producer picks a status rather than
#: guessing one and being corrected by a validator. A second copy that disagreed would be caught
#: by `test_the_statuses_this_producer_picks_are_the_ones_the_schema_allows`.
ALLOWED = {
    PartitionPart.VISIBLE: (EpistemicStatus.MEASURED, EpistemicStatus.VISIBLE),
    PartitionPart.INFERRED: (EpistemicStatus.UNCERTAIN,),
    PartitionPart.UNKNOWN: (EpistemicStatus.UNCERTAIN,),
}


@dataclass(frozen=True)
class SuppliedPart:
    """One of the three parts, as a person's brush or a fixture hands it over."""
    part: PartitionPart
    mask_rle: Optional[Mapping[str, Any]] = None
    field: Optional[ScalarFieldSpec] = None
    coverage: Optional[float] = None


def _refuse(message: str, *, code: RefusalCode, missing: Sequence[str] = (),
            remedy: str = "", detail: Optional[Mapping[str, Any]] = None) -> RefusalRecord:
    return RefusalRecord(code=code, organ=ORGAN, message=message, missing=list(missing),
                         remedy=remedy or None, detail=dict(detail or {"form": FORM}))


def produce_visible_inferred_partition(of_key: str, parts: Sequence[SuppliedPart], *,
                                       sources: Sequence[SRC.ExtentSource],
                                       conditioned_on: Optional[str] = None) -> FormProduction:
    """Assemble the three parts of one extent, or refuse the whole thing and say why.

    `cells_partitioned` IS THE RASTER, not the number of parts. It is what proves something looked
    at every cell before deciding which of the three it belonged to, and a count of the parts
    supplied would be `3` for a partition of a 4-megapixel photograph and a partition of a
    thumbnail alike.
    """
    basis, kept, omitted = admissible_basis(FORM, sources)
    omissions: List[Omission] = list(omitted)
    refusals: List[RefusalRecord] = []
    held = SRC.index(kept) if kept else {}

    if of_key not in held:
        refusals.append(_refuse(
            f"{of_key} is the extent to be partitioned and no supplied source holds it.",
            code=RefusalCode.UNKNOWN_REFERENCE, missing=[of_key],
            remedy="supply the extent set that holds it"))
        return produce(FORM, None, basis=basis or EpistemicBasis.MASK, partition=MEASURED,
                       sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))

    source, member = held[of_key]
    weakest = min((s.epistemic_status for s in kept), key=lambda s: STATUS_ORDER[s])
    if STATUS_ORDER[weakest] < STATUS_ORDER[EpistemicStatus.VISIBLE]:
        refusals.append(_refuse(
            f"the extent to be partitioned is {weakest.value}, and the visible part of a "
            f"partition may only be `measured` or `visible`. Partitioning something nobody saw "
            f"into what was seen and what was not is a question with no answer.",
            code=RefusalCode.INVALID_PARAMETERS, missing=[],
            remedy="partition an extent somebody measured",
            detail={"form": FORM, "input_status": weakest.value}))
        return produce(FORM, None, basis=basis or EpistemicBasis.MASK, partition=MEASURED,
                       sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))

    by_part: Dict[PartitionPart, SuppliedPart] = {}
    for supplied in parts:
        if supplied.part in by_part:
            omissions.append(Omission(
                what=supplied.part.value, reason="duplicate",
                detail="a partition names each of visible / inferred / unknown at most once"))
            continue
        by_part[supplied.part] = supplied
    for part in PartitionPart:
        if part not in by_part:
            omissions.append(Omission(
                what=part.value, reason="part_not_supplied",
                detail=(f"no {part.value} region was supplied. `unknown` is a real third part: "
                        f"not-seen-and-not-inferred is not the same as absent."
                        if part is PartitionPart.UNKNOWN else
                        f"no {part.value} region was supplied.")))

    if PartitionPart.VISIBLE not in by_part:
        refusals.append(_refuse(
            "a partition with no visible part contradicts the extent it partitions. `of` names "
            "something somebody measured, and an answer holding only inferred and unknown pixels "
            "is a statement about an extent nobody saw.",
            code=RefusalCode.MISSING_EXTENT_INPUTS, missing=["visible"],
            remedy="supply the part that was seen"))
        return produce(FORM, None, basis=basis or EpistemicBasis.MASK, partition=MEASURED,
                       sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))

    stray = _off_raster(member, by_part)
    if stray is not None:
        part, shape, expected = stray
        refusals.append(_refuse(
            f"the {part.value} part is {shape[0]}x{shape[1]} and the extent it partitions is "
            f"{expected[0]}x{expected[1]}. Two rasters is two pictures: the parts could not be "
            f"checked against each other for overlap, and their coverages would be fractions of "
            f"different frames.",
            code=RefusalCode.INVALID_PARAMETERS, missing=[],
            remedy="supply the parts on the raster the extent was measured on",
            detail={"form": FORM, "part": part.value, "part_raster": list(shape),
                    "extent_raster": list(expected)}))
        return produce(FORM, None, basis=basis or EpistemicBasis.MASK, partition=MEASURED,
                       sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))

    overlap = _overlaps(by_part)
    if overlap is not None:
        left, right, shared = overlap
        refusals.append(_refuse(
            f"the {left.value} and {right.value} parts share {shared} pixels. A pixel in two "
            f"parts is a pixel this record cannot place, and a reader drawing the tricolour would "
            f"paint it in whichever key their loop reached last - so a hallucinated leg would "
            f"appear in the same colour as a photographed one.",
            code=RefusalCode.INVALID_PARAMETERS, missing=[],
            remedy="separate the parts; inferred geometry is not visible geometry",
            detail={"form": FORM, "parts": [left.value, right.value], "shared_pixels": shared}))
        return produce(FORM, None, basis=basis or EpistemicBasis.MASK, partition=COMPLETION,
                       sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))

    regions: List[PartitionRegion] = []
    for part in PartitionPart:
        supplied = by_part.get(part)
        if supplied is None:
            continue
        coverage = _coverage(supplied)
        if coverage is None:
            omissions.append(Omission(
                what=part.value, reason="part_not_supplied",
                detail=("a field part has no pixels to count, so its coverage has to be declared. "
                        "Without one there is no honest number to record.")))
            continue
        status = (EpistemicStatus.MEASURED if weakest is EpistemicStatus.MEASURED
                  else EpistemicStatus.VISIBLE) if part is PartitionPart.VISIBLE \
            else EpistemicStatus.UNCERTAIN
        regions.append(PartitionRegion(
            part=part, epistemic_status=status, coverage=coverage,
            mask_rle=None if supplied.mask_rle is None else dict(supplied.mask_rle),
            field=supplied.field))

    payload = ExtentPartitionPayload(
        variant="extent_partition", of=source.ref(of_key.split("#", 1)[1]),
        cells_partitioned=_cells(member, by_part), regions=regions,
        conditioned_on=conditioned_on)
    partition = COMPLETION if PartitionPart.INFERRED in by_part else MEASURED
    return produce(FORM, payload, basis=basis or EpistemicBasis.MASK, partition=partition,
                   sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))


def _coverage(supplied: SuppliedPart) -> Optional[float]:
    """Measured off the mask where there is one; declared only where there are no pixels."""
    if supplied.mask_rle is not None:
        area = M.normalized_area(dict(supplied.mask_rle))
        # Rounded at the precision the rest of the tree rounds normalized geometry to. A
        # coverage recorded to seventeen places is a number whose last ten digits are an artifact
        # of binary division, and three of them summed would trip the schema's own tolerance.
        return None if area is None else round(area, 6)
    return None if supplied.coverage is None else round(float(supplied.coverage), 6)


def _overlaps(by_part: Mapping[PartitionPart, SuppliedPart]
              ) -> Optional[Tuple[PartitionPart, PartitionPart, int]]:
    """The first pair of parts that share a pixel, per pixel, on a shared raster."""
    masked = [(p, s.mask_rle) for p, s in by_part.items() if s.mask_rle is not None]
    for i in range(len(masked)):
        for j in range(i + 1, len(masked)):
            shared = M.intersection_area(dict(masked[i][1]), dict(masked[j][1]))
            if shared:
                return masked[i][0], masked[j][0], shared
    return None


def _off_raster(member: Any, by_part: Mapping[PartitionPart, SuppliedPart]
                ) -> Optional[Tuple[PartitionPart, Tuple[int, int], Tuple[int, int]]]:
    """The first mask part measured on a raster the extent was not.

    CHECKED BEFORE OVERLAP, because `intersection_area` returns None on a raster mismatch rather
    than resampling — so two parts on two rasters would pass the overlap check by being
    incomparable, and a partition whose parts could not be compared would validate.
    """
    expected = M.mask_size(SRC.geometry_of(member)[0])
    if expected is None:
        return None
    for part, supplied in by_part.items():
        if supplied.mask_rle is None:
            continue
        shape = M.mask_size(dict(supplied.mask_rle))
        if shape is not None and shape != expected:
            return part, shape, expected
    return None


def _cells(member: Any, by_part: Mapping[PartitionPart, SuppliedPart]) -> int:
    """Every cell of the raster the parts were decided on.

    THE EXTENT'S RASTER FIRST, because that is the frame the question was asked in. A field-only
    partition falls back to the field's own shape, which is the only raster in the record.
    """
    size = M.mask_size(SRC.geometry_of(member)[0])
    if size is None:
        for supplied in by_part.values():
            size = M.mask_size(supplied.mask_rle) if supplied.mask_rle is not None else None
            if size is not None:
                break
    if size is None:
        for supplied in by_part.values():
            if supplied.field is not None:
                return supplied.field.field_shape[0] * supplied.field.field_shape[1]
        return 0
    return size[0] * size[1]


__all__ = ["ALLOWED", "COMPLETION", "FORM", "MEASURED", "SuppliedPart",
           "produce_visible_inferred_partition"]
