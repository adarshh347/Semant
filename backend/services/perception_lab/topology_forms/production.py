"""
PERCEPTUAL-FORMS-001D — what a structural producer returns, and what it is allowed to claim.

FOUR FORMS, ONE RESULT TYPE. `topology.containment_tree`, `topology.adjacency_graph`,
`topology.transition` and `topology.uncertain_relation_set` are assembled from relations that were
measured already. None of them looks at a pixel. What they add is ORDERING, and the honest name
for that is `exact_derivation`: the tree adds transitivity, the graph adds assembly, the transition
adds a comparison, and not one of them adds evidence.

WHY A RESULT TYPE RATHER THAN A PAYLOAD. Because three of the things a reader most needs cannot be
said inside the Lane A payloads, and a producer that returned only a payload would have to throw
them away:

    the producibility verdict   two of these four forms are DEFERRED in the merged contract, and a
                                payload handed back with no verdict attached is a payload somebody
                                writes
    the derived ceiling         `derived_ceiling` needs the INPUT statuses, which a validator
                                looking at one record does not have. The composing runtime asks,
                                and the answer belongs beside the payload it caps
    the omissions               `TopologyAdjacencyGraphPayload` has nowhere to record the members a
                                bound excluded, and `TopologyContainmentTreePayload` has nowhere to
                                record the node whose parentage two relations disagreed about.
                                Silence there would read as coverage

SO EVERY PRODUCER RETURNS `FormProduction`, and a caller that wants to mint an artifact has to step
over `producible` to do it.

THE DEFERRAL IS NOT DECORATIVE, AND IT IS ALSO NOT A LIE ABOUT WHAT THIS LANE DID. Lane A's
`check_form_producible` refuses an attempt to WRITE a deferred form, and `PerceptualArtifact`
refuses to validate one — that is where the gate bites, and this lane does not touch it. What this
lane does is compute the structure so that the payload shape can be reviewed a phase before
anything writes it, which is the stated reason the deferred forms were registered at all. The
verdict travels with the payload precisely so the distinction cannot be lost in transit.

PURE. No database, no network, no model, no clock, no adapter. Records in, records out.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from backend.schemas.perception_lab import (BASIS_CEILINGS, STATUS_ORDER, EpistemicBasis,
                                            EpistemicStatus, OrganFamily, PerceptualArtifact,
                                            RefusalCode, RefusalRecord, TopologyRelation)
from backend.services.perception_lab import definitions as D

ORGAN = OrganFamily.TOPOLOGY

#: What every artifact these producers would mint says about who made it. Distinct from
#: `topology.PRODUCER` on purpose: a composition and a measurement are different acts, and a
#: reader who cannot tell which one wrote a record cannot tell whether it looked at the image.
PRODUCER = "topology_forms"

#: The partition every structural form here is produced under. Declared once because all four
#: agree, and because a producer that picked its own would be picking its own ceiling.
PARTITION = "exact_derivation"

#: The reasons a producer leaves something out. Closed, because "omitted for other reasons" is the
#: category that swallows the ones worth reading.
OMISSION_REASONS: Tuple[str, ...] = (
    "bound_exceeded",          # the caller bounded the set and this member fell outside it
    "endpoint_dangling",       # the relation cites an endpoint no supplied input holds
    "containment_conflict",    # two incomparable candidate parents; see `containment.py`
    "containment_cycle",       # the relations disagree in a loop
    "orphaned_by_exclusion",   # its parent was excluded, so its parentage is no longer holdable
    "revision_missing",        # a transition needs a pinned revision and this endpoint has none
    "revision_unchanged",      # the pair was re-measured, not revised
    "not_a_structural_kind",   # the relation kind is not one this form assembles
    "ambiguous_state",         # one pair held two kinds of one family at once; see `transition.py`
    "self_pair",               # source and target are the same identity
    "duplicate",               # the same finding arrived twice
    # PERCEPTUAL-FORMS-001G adds the composite-Extent reasons HERE rather than opening a second
    # closed set beside this one. A reader counting what a laboratory left out should have ONE
    # vocabulary to count in; two lists that each call themselves closed are two lists that drift
    # on the first edit, and the omission a reader most wants is the one that fell between them.
    "producer_unavailable",    # the form's only candidate producer is deferred or rejected
    "ground_not_admitted",     # the evidence cites a model Lane C did not admit for this form
    "sole_ground_forbidden",   # the only ground offered is one that may not stand alone
    "no_ground_supplied",      # a grouping arrived with no evidence at all
    "part_not_supplied",       # a partition part the caller did not provide
    "not_geometrically_contained",  # a proposed parent does not contain the child, per pixel
    "semantic_link_undeclared",     # a part/whole link with no human assertion behind it
    "single_reading",          # one alternative is not an alternative set
)


@dataclass(frozen=True)
class Omission:
    """One thing a producer left out, named, with the reason from the closed set above.

    `what` is a reference — a node key, a member key, a relation id — never a description. An
    omission a reader cannot look up is an apology rather than a record.
    """
    what: str
    reason: str
    detail: str

    def __post_init__(self) -> None:
        if self.reason not in OMISSION_REASONS:
            raise ValueError(
                f"{self.reason!r} is not one of the declared omission reasons "
                f"{list(OMISSION_REASONS)}. A producer that invents a reason has invented a "
                f"category nobody counts.")


@dataclass(frozen=True)
class FormProduction:
    """One structural form, assembled — with the verdict and the ceiling that qualify it.

    `payload` is None only when the producer refused outright. A DEFERRED form still carries its
    payload, with `producible: False` and the typed refusal beside it: the shape is the thing this
    phase exists to settle, and withholding it would settle nothing while pretending to.
    """
    form_key: str
    payload: Optional[Any]
    producible: bool
    ceiling: EpistemicStatus
    basis: EpistemicBasis
    refusals: Tuple[RefusalRecord, ...] = ()
    input_artifact_ids: Tuple[str, ...] = ()
    input_statuses: Tuple[EpistemicStatus, ...] = ()
    omitted: Tuple[Omission, ...] = ()

    @property
    def refused(self) -> bool:
        """Whether anything at all was refused — INCLUDING the deferral.

        Deliberately not the same question as `payload is None`. A caller asking "may I write
        this" wants `producible`; a caller asking "did everything resolve" wants this.
        """
        return bool(self.refusals)

    @property
    def writable_payload(self) -> Optional[Any]:
        """The payload IF this deployment may write it, and None otherwise.

        The accessor a minting caller should reach for, so that forgetting to check `producible`
        is not the same shape of mistake as checking it.
        """
        return self.payload if self.producible else None

    def omissions_for(self, reason: str) -> Tuple[Omission, ...]:
        return tuple(o for o in self.omitted if o.reason == reason)


# ── the gates every producer runs, in the order they refuse ──────────────────


def check_producible(form_key: str) -> Optional[RefusalRecord]:
    """Lane A's gate 6, unchanged and uncached. Two of these four forms answer with a refusal."""
    return D.check_form_producible(form_key)


def check_inputs_are_read(form_key: str, supplied_forms: Sequence[str]) -> Optional[RefusalRecord]:
    """Lane A's gate 5. A relation set handed to a form that reads hypothesis sets is the wrong
    ANSWER, not a missing one, and the two send a person to different places."""
    return D.check_input_forms(form_key, list(supplied_forms))


def ceiling_for(form_key: str, *, basis: EpistemicBasis,
                input_statuses: Sequence[EpistemicStatus],
                partition: str = PARTITION) -> EpistemicStatus:
    """The strongest status the assembled form may carry.

    THREE CAPS, and the third is the one this lane exists to apply. The basis ceiling and the
    partition ceiling are properties of the record and Lane A's validators enforce them. The third
    — that an `exact_derivation` is never stronger than the weakest artifact it derived FROM —
    needs the inputs in hand, so it is asked here and recorded on the production.
    """
    answer = D.derived_ceiling(form_key, basis=basis.value, partition=partition,
                               input_statuses=[s.value for s in input_statuses])
    return EpistemicStatus(answer)


def weakest(statuses: Sequence[EpistemicStatus],
            default: EpistemicStatus = EpistemicStatus.MEASURED) -> EpistemicStatus:
    return min(statuses, key=lambda s: STATUS_ORDER[s]) if statuses else default


def weaker_basis(bases: Sequence[EpistemicBasis]) -> EpistemicBasis:
    """The substrate a composed form rests on: the weakest of the ones under it.

    `all_pairs` already rules this way for a graph it measures in one go — "a graph containing one
    box-basis edge is not a measured graph" — and a composition assembled from several artifacts
    is the same claim over a wider set. The individual edges keep their own basis, so a reader can
    still see which is which.
    """
    if not bases:
        return EpistemicBasis.MASK
    return min(bases, key=lambda b: STATUS_ORDER[BASIS_CEILINGS[b]])


# ── refusals this lane raises, in the vocabulary the contract already has ────


def dangling(reference: str, *, form_key: str, detail: Mapping[str, Any]) -> RefusalRecord:
    """A record cites an endpoint the supplied inputs do not hold.

    `unknown_reference` is the nearest of the eleven codes and it is not an exact fit: its message
    template says "in this session", and this is a statement about the artifacts handed to one
    producer. The alternative was to say `missing_extent_inputs`, which would send a person to
    select more extents when what is wrong is that a relation names one they never supplied. The
    detail block carries the precise version; see the lane report.
    """
    return RefusalRecord(
        code=RefusalCode.UNKNOWN_REFERENCE, organ=ORGAN, operation=None,
        message=(f"{reference} is cited by a relation and is not held by any artifact supplied to "
                 f"{form_key}. A structure assembled over an endpoint nobody supplied would be a "
                 f"picture of something this record cannot show."),
        missing=[reference],
        remedy="supply the artifact that holds this endpoint, or drop the relation that cites it",
        detail={"form": form_key, "reference": reference, **dict(detail)})


def not_a_revision(reference: str, *, form_key: str) -> RefusalRecord:
    """A transition needs `geometry_rev` at both ends and this endpoint has none.

    `RelationEndpoint.geometry_rev` is optional — a session-scope relation may legitimately carry
    none — so this is a refusal rather than a validation error: the relation is perfectly good and
    it cannot be the subject of a statement about revisions.
    """
    return RefusalRecord(
        code=RefusalCode.UNKNOWN_REFERENCE, organ=ORGAN, operation=None,
        message=(f"{reference} carries no geometry_rev, so it cannot be one end of a transition. "
                 f"A change nobody can see the start of is not a finding."),
        missing=["geometry_rev"],
        remedy="supply relations whose endpoints are pinned to a revision",
        detail={"form": form_key, "reference": reference, "reason": "revision_missing"})


# ── stable, derived identity ─────────────────────────────────────────────────


def digest(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def minted(prefix: str, *parts: Any) -> str:
    """A composed record's id, derived from what it is ABOUT rather than minted from randomness.

    Assembling the same relations twice produces the same ids, so a person comparing two repeats
    is comparing structures rather than lining up two sets of uuids. `topology.relation_id` takes
    the same discipline for the same reason, and this deliberately does not reuse it: that one
    keys on run and step, and a composition is not a step's property.
    """
    return f"{prefix}_{digest(*parts)[:12]}"


__all__ = ["ORGAN", "PRODUCER", "PARTITION", "OMISSION_REASONS", "Omission", "FormProduction",
           "check_producible", "check_inputs_are_read", "ceiling_for", "weakest", "weaker_basis",
           "dangling", "not_a_revision", "digest", "minted"]
