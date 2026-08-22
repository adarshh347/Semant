"""
PERCEPTUAL-FORMS-001G — `extent.fused_hypothesis`: are these pieces one thing, and on what.

THE FRAGMENTS ARE MEASURED AND THE GROUPING IS NOT. Every member of a fusion is a mask somebody
measured per pixel. The claim that four green patches behind a fence are one tree is a different
kind of statement about the same pixels, and `PARTITION_CEILINGS` caps it at `interpretive` —
`uncertain` the moment it also asserts extent nobody saw. No number of members and no strength on
any ground lifts it, because the cap is on the ACT rather than on the evidence.

WHAT THIS PRODUCER WILL NOT DO, and each absence is the whole point of the form:

  · IT DOES NOT GROUP. Nothing here computes a similarity, thresholds it, and emits the groups.
    A caller proposes a grouping and this assembles it with its evidence and its cost. Lane C's
    `false-twins` control is the committed proof of the alternative: three identical discs, two of
    which belong together, and any appearance threshold gives one confident group of three.
  · IT DOES NOT CHOOSE. Two proposals over the same members both survive, in the order they were
    given, and `alternatives_retained` says so. Dropping the rejected grouping is how a guess
    becomes a fact between one panel and the next.
  · IT DOES NOT WEIGH. `weight` is carried if a caller supplies one and is never computed here,
    never sorted on, and never used to keep one hypothesis over another.

`fragments_considered` IS CARRIED THROUGH FROM THE SOURCES AND NEVER RECOUNTED. It is the field
that separates "the fragments were considered and no grouping was supportable" from "nobody
looked", and a producer that counted the members it happened to be handed would report the second
number while meaning the first.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (EpistemicBasis, EpistemicPartition,
                                            ExtentFusionHypothesisPayload, FusionHypothesis,
                                            InstanceRef)
from backend.services.perception_lab.extent_composites import grounds as G
from backend.services.perception_lab.extent_composites import sources as SRC
from backend.services.perception_lab.extent_composites.compose import (admissible_basis, minted,
                                                                       produce)
from backend.services.perception_lab.topology_forms.production import FormProduction, Omission

FORM = "extent.fused_hypothesis"

#: The two partitions this form admits. Which one a hypothesis carries is not a flag on one
#: claim; it is WHICH CLAIM is being made, and the schema refuses hidden extent under the first.
GROUPING = EpistemicPartition.INTERPRETIVE_GROUPING
COMPLETION = EpistemicPartition.INFERRED_COMPLETION


@dataclass(frozen=True)
class ProposedFusion:
    """One grouping somebody wants to claim, with what they say it rests on.

    `asserts_hidden_extent` IS THE CALLER'S DECLARATION AND IT CHANGES THE PARTITION. Grouping
    what is visible and inventing what is not are two different claims — the schema refuses the
    second under `interpretive_grouping` — so this is not a flag on a claim, it is which claim is
    being made.
    """
    proposal_id: str
    member_keys: Tuple[str, ...]
    evidence: Tuple[G.GroundEvidence, ...] = ()
    asserts_hidden_extent: bool = False
    weight: Optional[float] = None


def produce_fused_hypothesis(proposals: Sequence[ProposedFusion], *,
                             sources: Sequence[SRC.ExtentSource]) -> FormProduction:
    """Assemble the proposed groupings that survive their evidence, and name the ones that do not.

    FOUR WAYS A PROPOSAL IS LEFT OUT, and every one of them is recorded rather than dropped:

        endpoint_dangling       a member no supplied source holds
        self_pair               the members collapse to fewer than two identities
        no_ground_supplied      a grouping arrived with no evidence at all
        sole_ground_forbidden   its only ground is one Lane C said may never be the only one

    A hypothesis that survives is not thereby true. It is a claim with its evidence attached and
    its ceiling recorded, which is the most this form is for.
    """
    basis, kept, omitted = admissible_basis(FORM, sources)
    omissions: List[Omission] = list(omitted)
    if basis is None:
        return produce(FORM, None, basis=EpistemicBasis.MASK, partition=GROUPING.value,
                       sources=(), omitted=tuple(omissions))

    # The two ceilings are asked ONCE, before the loop. `derived_ceiling` is a pure function of
    # the form, the basis, the partition and the input statuses, and all four are settled here;
    # asking it per hypothesis would invite a future edit that made one of them per-hypothesis
    # without anyone noticing that the answers had started to differ.
    ceilings = {p: produce(FORM, None, basis=basis, partition=p.value, sources=kept).ceiling
                for p in (GROUPING, COMPLETION)}
    held = SRC.index(kept)
    hypotheses: List[FusionHypothesis] = []
    for proposal in proposals:
        missing = [k for k in proposal.member_keys if k not in held]
        if missing:
            omissions.append(Omission(
                what=proposal.proposal_id, reason="endpoint_dangling",
                detail=(f"{missing} are cited as members and no supplied source holds them. A "
                        f"grouping over an extent nobody supplied is a picture of something this "
                        f"record cannot show.")))
            continue
        unique = tuple(dict.fromkeys(proposal.member_keys))
        if len(unique) < 2:
            omissions.append(Omission(
                what=proposal.proposal_id, reason="self_pair",
                detail=(f"the members collapse to {len(unique)} identity. A fusion of one thing "
                        f"with itself is a hard mask wearing a hypothesis's clothes.")))
            continue
        vetting = G.vet(proposal.evidence, form_key=FORM, subject=proposal.proposal_id)
        omissions.extend(vetting.omitted)
        if not vetting.grounds:
            omissions.append(Omission(
                what=proposal.proposal_id, reason="no_ground_supplied",
                detail=("a grouping with no ground is a confidence with nothing behind it. "
                        "Enumerated evidence is what lets a reviewer disagree with a specific "
                        "part of it rather than with a number.")))
            continue
        if vetting.sole_forbidden_ground:
            omissions.append(Omission(
                what=proposal.proposal_id, reason="sole_ground_forbidden",
                detail=(f"the only ground is {list(vetting.may_not_stand_alone)}, which Lane C "
                        f"admitted as one ground among several and never as the sole one. It "
                        f"measures resemblance or ordering; neither is unity.")))
            continue
        partition = COMPLETION if proposal.asserts_hidden_extent else GROUPING
        hypotheses.append(FusionHypothesis(
            hypothesis_id=minted("fus", FORM, proposal.proposal_id, *unique),
            members=[held[k][0].ref(k.split("#", 1)[1]) for k in unique],
            grounds=list(vetting.grounds), partition=partition,
            epistemic_status=ceilings[partition], weight=proposal.weight,
            asserts_hidden_extent=proposal.asserts_hidden_extent))

    payload = ExtentFusionHypothesisPayload(
        variant="extent_fusion_hypothesis",
        fragments_considered=sum(s.examined for s in kept),
        hypotheses=hypotheses, alternatives_retained=True)
    # THE RECORDED PARTITION IS THE WEAKER OF THE ONES PRESENT. A set holding one completion is a
    # set that asserts hidden extent, and reporting it under the grouping ceiling would let the
    # strongest hypothesis in it read as the whole record's claim.
    partition = COMPLETION if any(h.asserts_hidden_extent for h in hypotheses) else GROUPING
    return produce(FORM, payload, basis=basis, partition=partition.value, sources=kept,
                   omitted=tuple(omissions))


__all__ = ["FORM", "ProposedFusion", "produce_fused_hypothesis"]
