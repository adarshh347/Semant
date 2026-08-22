"""
PERCEPTUAL-FORMS-001G — what every composite producer returns, and the three caps on what it says.

ONE RESULT TYPE, AND IT IS LANE D'S. `FormProduction` already carries the four things a payload
cannot: the producibility verdict, the derived ceiling, the input artifacts, and the omissions.
Writing a second one here would be a second answer to a settled question, and a reader holding two
would have to learn which lane made the record before they could read it.

THE THREE CAPS, IN THE ORDER THEY BITE. A composite form is a claim about measurements, so it is
capped by:

    the basis     what the claim was computed FROM — `BASIS_CEILINGS`, enforced by the schema
    the partition what was DONE with it — `PARTITION_CEILINGS`, also enforced by the schema
    the inputs    an assembly is never stronger than the weakest artifact under it

The third needs the inputs in hand, which a validator looking at one record does not have. So it
is asked here and recorded on the production — and it is asked THROUGH `definitions.derived_ceiling`
rather than recomputed, because the contract already ranks the four statuses and a second ranking
here would be a second chance to disagree.

AND THE THIRD CAP DOES NOT ALWAYS APPLY, WHICH IS NOT AN OVERSIGHT. `derived_ceiling` extends
caps with the input statuses only for `exact_derivation` and `interpretive_grouping`. An
`inferred_completion` and an `unresolved_alternative` are already capped BELOW every input by their
own partition — `uncertain` is the floor of the ordering — so adding the inputs would change
nothing and would suggest that strong enough inputs could lift them. They cannot, at any
confidence.

A BASIS THE FORM DOES NOT ADMIT IS AN OMISSION, NOT A DOWNGRADE. `extent.fused_hypothesis` admits
`mask`, `manual` and `declared` and not `box`, because a bounding box does not show that two
patches continue into each other. A producer handed a box-basis extent set drops it and SAYS SO,
rather than composing over it at a lower ceiling — the second would produce a hypothesis whose
evidence is a rectangle, at a status a reader would take for a judgement about pixels.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (BASIS_CEILINGS, STATUS_ORDER, EpistemicBasis,
                                            EpistemicStatus, OrganFamily, RefusalRecord)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.extent_composites.sources import ExtentSource
from backend.services.perception_lab.topology_forms.production import (FormProduction, Omission,
                                                                       check_producible, digest)

ORGAN = OrganFamily.EXTENT

#: What every artifact these producers would mint says about who made it. Distinct from
#: `extent.PRODUCER` and from `topology_forms.PRODUCER` on purpose: measuring, assembling
#: structure and claiming a grouping are three acts, and a reader who cannot tell which one wrote
#: a record cannot tell whether anything looked at the image.
PRODUCER = "extent_composites"


def admissible_basis(form_key: str, sources: Sequence[ExtentSource]
                     ) -> Tuple[Optional[EpistemicBasis], Tuple[ExtentSource, ...],
                                Tuple[Omission, ...]]:
    """The weakest basis this form admits, the sources that survived, and the ones that did not.

    THE WEAKEST, because a composition resting on one box-basis input is not a mask-basis
    composition — the rule `topology.all_pairs` already applies to a graph it measures in one go,
    over a wider set. The individual members keep their own basis, so a reader can still see which
    is which.
    """
    definition = D.form(str(form_key))
    kept: List[ExtentSource] = []
    omitted: List[Omission] = []
    for source in sources:
        if source.epistemic_basis.value in definition.admissible_bases:
            kept.append(source)
            continue
        omitted.append(Omission(
            what=source.artifact_id, reason="basis_not_admitted",
            detail=(f"{source.artifact_id} is {source.epistemic_basis.value}-basis and "
                    f"{form_key} is measured from {list(definition.admissible_bases)}. Composing "
                    f"over it would produce a claim whose evidence is a rectangle, at a status a "
                    f"reader would take for a judgement about pixels.")))
    if not kept:
        return None, (), tuple(omitted)
    basis = min((s.epistemic_basis for s in kept),
                key=lambda b: STATUS_ORDER[BASIS_CEILINGS[b]])
    return basis, tuple(kept), tuple(omitted)


def produce(form_key: str, payload: Optional[Any], *, basis: EpistemicBasis, partition: str,
            sources: Sequence[ExtentSource] = (), refusals: Sequence[RefusalRecord] = (),
            omitted: Sequence[Omission] = ()) -> FormProduction:
    """A payload, with the verdict and the ceiling that qualify it.

    `check_producible` RUNS EVERY TIME AND ITS ANSWER TRAVELS WITH THE PAYLOAD. Four of the five
    composite forms are `deferred` in the merged contract. This lane does not soften that and does
    not withhold the payload either: settling the shape a phase before anything writes it is the
    stated reason those forms were registered, and a caller that wants to mint an artifact has to
    step over `producible` to do it.
    """
    statuses = tuple(s.epistemic_status for s in sources)
    ceiling = EpistemicStatus(D.derived_ceiling(
        str(form_key), basis=basis.value, partition=str(partition),
        input_statuses=[s.value for s in statuses]))
    deferral = check_producible(str(form_key))
    return FormProduction(
        form_key=str(form_key), payload=payload,
        producible=deferral is None, ceiling=ceiling, basis=basis,
        refusals=tuple(refusals) + ((deferral,) if deferral is not None else ()),
        input_artifact_ids=tuple(dict.fromkeys(s.artifact_id for s in sources)),
        input_statuses=statuses, omitted=tuple(omitted))


def minted(prefix: str, *parts: Any) -> str:
    """A composed record's id, derived from what it is ABOUT rather than from randomness.

    Composing the same claim twice produces the same id, so a person comparing two repeats is
    comparing claims rather than lining up two sets of uuids.
    """
    return f"{prefix}_{digest(*parts)[:12]}"


__all__ = ["ORGAN", "PRODUCER", "admissible_basis", "minted", "produce"]
