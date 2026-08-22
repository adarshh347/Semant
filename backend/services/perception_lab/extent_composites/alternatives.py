"""
PERCEPTUAL-FORMS-001G — `extent.hypothesis_set`: the competing readings, held open.

THE CUBIST CASE, AND THE SHADOW. A figure and the dark shape it throws are one extent under one
reading and two under another, and Lane F's `competing-extents` control records both as legitimate
with an IoU of 0.77 between them. The honest answer is that the picture supports both. Forcing one
is a fabrication dressed as a measurement, and the fabrication is invisible afterwards because a
single mask is exactly what a confident answer looks like.

THE THREE THINGS THIS PRODUCER CANNOT DO, and the first is structural rather than disciplined:

  · IT CANNOT RESOLVE. `ExtentHypothesisSetPayload` has no `chosen` field and no `winner` field,
    so there is nowhere for a selection to be written. Resolution is a separate act that produces
    a separate artifact of a resolved form, and the alternatives survive it.
  · IT DOES NOT ORDER BY WEIGHT. Alternatives come back sorted by their derived id, which carries
    no ranking at all. Sorting by weight would put a winner first in every reader that took the
    first element, and "first" is a selection whatever the field is called.
  · IT DOES NOT PROMOTE A WEIGHT TO A PROBABILITY. `weights_are_probabilities` is False unless a
    caller declares otherwise, and weights that happen to sum to one do not flip it. Three
    alternatives at 0.5, 0.3 and 0.2 sum to one by arithmetic and are still not a distribution
    anybody calibrated.

ONE ALTERNATIVE IS NOT AN ALTERNATIVE SET. The schema refuses it, and this producer refuses before
the schema does so the refusal names what happened: a single surviving reading IS a hard mask, and
recording it here would dress one answer as a preserved ambiguity — the exact inverse of what the
form is for.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (EpistemicBasis, ExtentAlternative,
                                            ExtentHypothesisSetPayload, OrganFamily, RefusalCode,
                                            RefusalRecord)
from backend.services.perception_lab.extent_composites import grounds as G
from backend.services.perception_lab.extent_composites import sources as SRC
from backend.services.perception_lab.extent_composites.compose import (ORGAN, admissible_basis,
                                                                       minted, produce)
from backend.services.perception_lab.topology_forms.production import FormProduction, Omission

FORM = "extent.hypothesis_set"

#: The only partition this form admits, and it is the floor of the ordering. An unresolved
#: alternative is `uncertain` however strong the extents under it are, which is why no input
#: status lifts it and no weight does either.
PARTITION = "unresolved_alternative"


@dataclass(frozen=True)
class Reading:
    """One competing reading of where the thing is, as a caller proposes it."""
    reading_id: str
    weight: float
    member_keys: Tuple[str, ...] = ()
    artifact_id: Optional[str] = None
    evidence: Tuple[G.GroundEvidence, ...] = ()
    label: str = ""


def produce_hypothesis_set(question: str, readings: Sequence[Reading], *,
                           sources: Sequence[SRC.ExtentSource],
                           weights_are_probabilities: bool = False) -> FormProduction:
    """Hold the readings open, or say why there is no ambiguity worth preserving.

    `alternatives_considered` COUNTS EVERY READING THAT WAS PUT FORWARD, including the ones that
    did not survive. It is the field that distinguishes "alternatives were considered and only one
    reading survived" from "nobody considered any", and those are opposite findings.
    """
    basis, kept, omitted = admissible_basis(FORM, sources)
    omissions: List[Omission] = list(omitted)
    refusals: List[RefusalRecord] = []
    held = SRC.index(kept) if kept else {}
    alternatives: List[ExtentAlternative] = []
    for reading in readings:
        missing = [k for k in reading.member_keys if k not in held]
        if missing:
            omissions.append(Omission(
                what=reading.reading_id, reason="endpoint_dangling",
                detail=f"{missing} are cited by this reading and no supplied source holds them"))
            continue
        if not reading.member_keys and not reading.artifact_id:
            omissions.append(Omission(
                what=reading.reading_id, reason="endpoint_dangling",
                detail=("a reading names the artifact that embodies it or the instances it is "
                        "made of. A weight attached to nothing is a number about nothing.")))
            continue
        vetting = G.vet(reading.evidence, form_key=FORM, subject=reading.reading_id)
        omissions.extend(vetting.omitted)
        alternatives.append(ExtentAlternative(
            alternative_id=minted("alt", FORM, reading.reading_id, *reading.member_keys),
            weight=float(reading.weight),
            artifact_id=reading.artifact_id if not reading.member_keys else None,
            instances=[held[k][0].ref(k.split("#", 1)[1]) for k in reading.member_keys],
            grounds=list(vetting.grounds)))

    # BY ID, NEVER BY WEIGHT. A reader that takes the first element takes a winner, whatever the
    # field it was sorted on is called, so the order carries no ranking to take.
    alternatives.sort(key=lambda a: a.alternative_id)

    if len(alternatives) == 1:
        survivor = alternatives[0]
        omissions.append(Omission(
            what=survivor.alternative_id, reason="single_reading",
            detail=("one reading survived. That is a hard mask, and recording it here would dress "
                    "a single answer as a preserved ambiguity.")))
        refusals.append(RefusalRecord(
            code=RefusalCode.UNSUPPORTED_FORM, organ=ORGAN,
            message=("one alternative is not an alternative set. A single surviving reading is a "
                     "hard mask; this form preserves an ambiguity and there is none to preserve."),
            missing=["a second reading"],
            remedy="record the surviving reading as an extent set, or supply the reading it "
                   "competes with",
            detail={"form": FORM, "considered": len(readings), "survived": 1}))
        alternatives = []

    if weights_are_probabilities and alternatives:
        total = sum(a.weight for a in alternatives)
        if abs(total - 1.0) > 1e-6:
            refusals.append(RefusalRecord(
                code=RefusalCode.INVALID_PARAMETERS, organ=ORGAN,
                message=(f"weights declared as probabilities sum to {total:.4f}. Either they are "
                         f"probabilities and they sum to one, or they are weights and they say "
                         f"so."),
                missing=[], remedy="declare them as weights, or supply a calibrated distribution",
                detail={"form": FORM, "sum": round(total, 6)}))
            weights_are_probabilities = False

    payload = ExtentHypothesisSetPayload(
        variant="extent_hypothesis_set", question=str(question),
        alternatives_considered=len(readings),
        weights_are_probabilities=bool(weights_are_probabilities),
        alternatives=alternatives)
    return produce(FORM, payload, basis=basis or EpistemicBasis.MASK, partition=PARTITION,
                   sources=kept, refusals=tuple(refusals), omitted=tuple(omissions))


__all__ = ["FORM", "PARTITION", "Reading", "produce_hypothesis_set"]
