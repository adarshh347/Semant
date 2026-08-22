"""
PERCEPTUAL-FORMS-001G — `extent.density_field`: where the collection is, when there is no object.

FIVE HUNDRED PEOPLE IN A PLAZA. There is no object called `crowd`, and "the crowd occupies the
eastern half" is still a true and useful sentence. This form is how it is said without inventing
an entity to hang it on — and the whole difficulty is saying it without letting a smoothing
bandwidth read as a population.

LANE C REJECTED THE MODEL AND KEPT THE FORM, and this is the route they named: counts from an
existing extent set, a declared kernel, `counts_are_exact: true`. DAVE and GeCo need exemplars and
carry research-use terms, and the form does not need a model at all — every member was already
measured, so the count is not estimated, it is *known*. `admission.producer_for` refuses the
counters with that verdict, and nothing is substituted.

THREE DECLARATIONS THAT ANSWER THREE QUESTIONS, and a single `density` number answers none:

    members_counted   how many entities entered. Exact, because each one is a measured extent
    samples_taken     how many points were placed. One per member, at its centroid
    smoothing         what was applied afterwards, with its method and its bandwidth

SMOOTHING MOVES MASS AND DOES NOT MAKE IT. Every kernel is normalized so that one member
contributes exactly one unit of weight across the whole field, whatever the bandwidth. So the
field sums to `members_counted` before and after smoothing, and a test holds it there — which is
the arithmetic version of "a bandwidth choice may not read as a population".

AND SMOOTHING COSTS THE CALIBRATION, which is the honest price. An unsmoothed field's numbers ARE
members per cell: `calibrated`, with the method and the extent set it was counted from named. A
smoothed field's numbers are weighted neighbours; they keep their order and lose their unit, which
is exactly what `nominal` means. Nothing here ever writes `calibrated` on a smoothed field, and
Lane A's schema would refuse the pair `blur_of_binary_mask` + `calibrated` anyway.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (CalibrationDeclaration, CalibrationState,
                                            CoordinateSystem, EpistemicBasis,
                                            ExtentDensityFieldPayload, FieldDerivation,
                                            InstanceRef, RefusalCode, RefusalRecord,
                                            ScalarFieldSpec, SmoothingDeclaration)
from backend.services.mask_geometry import rle_decode, rle_is_valid
from backend.services.perception_lab.extent_composites import sources as SRC
from backend.services.perception_lab.extent_composites.compose import (ORGAN, admissible_basis,
                                                                       produce)
from backend.services.perception_lab.extent_forms import measure as LB
from backend.services.perception_lab.extent_forms.raster import PixelSet
from backend.services.perception_lab.topology_forms.production import FormProduction, Omission

FORM = "extent.density_field"

#: The only partition this form is produced under here. Counting measured extents and placing one
#: point per extent adds no evidence; it is an ordering of things that were already measured.
PARTITION = "exact_derivation"

#: What an unsmoothed field's numbers are. Named so a reader does not have to infer it from the
#: derivation, and so `statistics["sum"]` has a unit.
UNITS = "members per cell"

#: The one smoothing method this producer knows. A second would be a second set of numbers with
#: the same name, so adding one is a visible edit rather than a parameter.
GAUSSIAN = "gaussian"


@dataclass(frozen=True)
class Kernel:
    """What to do to the samples after they are placed. `None` bandwidth means: nothing.

    THE BANDWIDTH IS A DECISION AND IT IS RECORDED AS ONE. Lane C's finding on the ViTMatte band
    radius applies here unchanged — it is the single biggest determinant of what the field looks
    like, and a field whose record does not say which bandwidth produced it cannot be compared
    with another field.
    """
    method: Optional[str] = None
    bandwidth: Optional[float] = None

    @property
    def applied(self) -> bool:
        return self.method is not None and self.bandwidth is not None


NO_SMOOTHING = Kernel()


def _centroid(member: Any) -> Optional[Tuple[float, float]]:
    """Where one member is, as a single normalized point.

    THE MASK'S CENTRE OF AREA WHERE THERE IS A MASK, and the box's centre where there is not. The
    two are different points for any shape that is not a rectangle, and the difference is why a
    box-basis source drops the whole field's ceiling to `interpretive` rather than being quietly
    treated as equivalent.
    """
    mask, box = SRC.geometry_of(member)
    if rle_is_valid(mask):
        bits, h, w = rle_decode(dict(mask))
        pixels = tuple(i for i, b in enumerate(bits) if b)
        if pixels:
            return LB.centroid(PixelSet(h=h, w=w, pixels=pixels, connectivity=4))
    if box is not None:
        return (round(box.x + box.w / 2, 6), round(box.y + box.h / 2, 6))
    return None


def _cell(point: Tuple[float, float], shape: Tuple[int, int]) -> Tuple[int, int]:
    h, w = shape
    x, y = point
    return (min(h - 1, max(0, int(y * h))), min(w - 1, max(0, int(x * w))))


def _spread(row: int, col: int, shape: Tuple[int, int], bandwidth: float) -> List[float]:
    """One sample's unit of weight, spread over the field and RENORMALIZED to sum to one.

    THE RENORMALIZATION IS THE POINT. A truncated Gaussian loses whatever mass falls outside the
    frame, so a member near the edge would contribute less than a member in the middle and the
    field would no longer sum to the count. Renormalizing over the cells the kernel actually
    reaches keeps one member worth exactly one member wherever it stands.
    """
    h, w = shape
    weights = [0.0] * (h * w)
    two_sigma_squared = 2.0 * bandwidth * bandwidth
    total = 0.0
    for r in range(h):
        for c in range(w):
            distance = (r - row) ** 2 + (c - col) ** 2
            weight = math.exp(-distance / two_sigma_squared)
            weights[r * w + c] = weight
            total += weight
    return [weight / total for weight in weights]


def produce_density_field(member_keys: Sequence[str], *, sources: Sequence[SRC.ExtentSource],
                          field_shape: Sequence[int],
                          kernel: Kernel = NO_SMOOTHING) -> FormProduction:
    """Count the members, place one point each, and declare what was done afterwards.

    `counts_are_exact` IS TRUE AND IT MEANS SOMETHING NARROW. Every member is an extent somebody
    measured, so the number of them is known rather than estimated — which is precisely the claim
    a low-shot counter cannot make. It does NOT mean the field is exact: the placement is one
    point per member and the smoothing is a choice, and both are declared separately for that
    reason.
    """
    basis, kept, omitted = admissible_basis(FORM, sources)
    omissions: List[Omission] = list(omitted)
    refusals: List[RefusalRecord] = []
    held = SRC.index(kept) if kept else {}
    shape = (int(field_shape[0]), int(field_shape[1]))
    if shape[0] <= 0 or shape[1] <= 0:
        refusals.append(RefusalRecord(
            code=RefusalCode.INVALID_PARAMETERS, organ=ORGAN,
            message=f"a density field of {shape[0]}x{shape[1]} has no cells to count into.",
            missing=[], remedy="declare a field shape with both dimensions above zero",
            detail={"form": FORM, "field_shape": list(shape)}))
        return produce(FORM, None, basis=basis or EpistemicBasis.MASK, partition=PARTITION,
                       sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))

    members: List[InstanceRef] = []
    placements: List[Tuple[int, int]] = []
    for key in member_keys:
        if key not in held:
            omissions.append(Omission(
                what=key, reason="endpoint_dangling",
                detail="no supplied source holds this member, so it cannot be counted"))
            continue
        source, member = held[key]
        point = _centroid(member)
        if point is None:
            omissions.append(Omission(
                what=key, reason="part_not_supplied",
                detail=("this member carries neither a mask nor a box, so there is nowhere to "
                        "place its sample. Counting it and not placing it would make the field "
                        "disagree with its own count.")))
            continue
        members.append(source.ref(key.split("#", 1)[1]))
        placements.append(_cell(point, shape))

    values = [0.0] * (shape[0] * shape[1])
    if kernel.applied and placements:
        for row, col in placements:
            for i, weight in enumerate(_spread(row, col, shape, float(kernel.bandwidth))):
                values[i] += weight
    else:
        for row, col in placements:
            values[row * shape[1] + col] += 1.0
    values = [round(v, 9) for v in values]

    smoothed = kernel.applied
    payload = ExtentDensityFieldPayload(
        variant="extent_density_field", members_counted=len(members),
        samples_taken=len(placements), counts_are_exact=True, members=members,
        smoothing=SmoothingDeclaration(
            applied=smoothed,
            method=str(kernel.method) if smoothed else None,
            bandwidth=float(kernel.bandwidth) if smoothed else None),
        field=ScalarFieldSpec(
            field_shape=[shape[0], shape[1]],
            coordinate_system=CoordinateSystem.NORMALIZED_XY_TOPLEFT,
            value_range=[0.0, max(values) if max(values) > 0 else 1.0],
            derivation=(FieldDerivation.KERNEL_DENSITY if smoothed
                        else FieldDerivation.SAMPLE_HISTOGRAM),
            calibration=_calibration(smoothed),
            inline_values=values,
            statistics={"members": float(len(members)), "samples": float(len(placements)),
                        "sum": round(sum(values), 6), "peak": max(values) if values else 0.0}))
    return produce(FORM, payload, basis=basis or EpistemicBasis.MASK, partition=PARTITION,
                   sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))


def _calibration(smoothed: bool) -> CalibrationDeclaration:
    """What the numbers mean, and what smoothing costs.

    An unsmoothed cell holds a count of members, which is a unit, measured against the set they
    were counted from — `calibrated`, with both named, which is what the schema requires. A
    smoothed cell holds weighted neighbours: still ordered, still comparable, and no longer a
    count of anything, which is exactly what `nominal` is the honest word for.
    """
    if smoothed:
        return CalibrationDeclaration(
            state=CalibrationState.NOMINAL, method=None, reference=None, units=None)
    return CalibrationDeclaration(
        state=CalibrationState.CALIBRATED,
        method="one sample per measured member, counted into its cell",
        reference="the supplied extent set", units=UNITS)


__all__ = ["FORM", "GAUSSIAN", "Kernel", "NO_SMOOTHING", "PARTITION", "UNITS",
           "produce_density_field"]
