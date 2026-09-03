"""
PERCEPTUAL-FORMS-001D — `topology.transition`: what changed between two revisions of one pair.

A REFINEMENT CHANGES A MASK, AND EVERY RELATION THAT RESTED ON IT IS NOW ABOUT SOMETHING ELSE.
`TopologyRelation.stale` can say a relation is out of date. Only this form says what the change WAS
— that `disjoint` became `meets`, that a containment was lost, that the band moved — and only a
record citing FOUR revision-pinned references can be checked by someone who was not there.

A TRANSITION IS PER PAIR AND PER FAMILY, and the second half of that is the part worth explaining.
The façade does not record one relation per pair: the one-pixel control comes back `nested_within`
AND `meets` AND `overlaps`, because all three are true of a shape that pokes one nub out of another.
So "what changed" is not a single question. It is asked once per FAMILY of mutually alternative
kinds:

    nesting     nested_within / contains     a pair is one of these, or neither
    planarity   disjoint / meets / overlaps  how the two stand in the plane
    depth       in_front_of / coplanar       how they stand in the ordering

Within a family a state normally holds at most one kind, and then the comparison is exact:
`disjoint` → `meets` is `changed`, a nesting present before and absent after is `disappeared`.

WHEN A STATE HOLDS TWO KINDS OF ONE FAMILY, NOTHING IS EMITTED FOR IT. The one-pixel control is
`meets` and `overlaps` at both revisions, and there is no arrangement of `RelationState` — which
carries one `kind` — that can say so. Picking the "main" one would be this module deciding which
measurement counted, so the family is named in `omitted` and the OTHER families still report. That
control's nesting family reports the finding that matters: `nested_within` disappeared.

DIRECTION SURVIVES CANONICALISATION. Pairs are keyed in a canonical order so that a relation
measured A→B before and B→A after is one pair rather than two. Kinds with an inverse are flipped
when they are turned round — the same law `containment.py` applies — and `in_front_of`, which has
no inverse in this vocabulary, keys on the ORDER IT WAS MEASURED IN, because "A is in front of B"
and "B is in front of A" are two claims and not one claim twice.

A THRESHOLD CROSSING IS A CHANGE IN THE RELATION, NEVER IN THE OBJECT. `MIN_CONTAINMENT` is 0.95;
the one-pixel control crosses it because one pixel moved. What disappears is the nesting. The
instance is the same instance at both revisions — Lane A's validator enforces exactly that, and
this producer never mints an identity, so there is no mechanism here by which a moved pixel could
become a new object.

PURE. No database, no network, no model, no clock. Two readings in, a comparison out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.perception_lab import (RefusalRecord, RelationEndpoint, RelationKind,
                                            RelationState, RevisionRef, TopologyRelation,
                                            TopologyTransition, TopologyTransitionPayload,
                                            TransitionChange)
from backend.services.perception_lab.topology_forms.production import (FormProduction, Omission,
                                                                       ceiling_for,
                                                                       check_inputs_are_read,
                                                                       check_producible, minted,
                                                                       not_a_revision,
                                                                       weaker_basis)
from backend.services.perception_lab.topology_forms.sources import (Reading, Roster, Supplied,
                                                                    endpoint_key)

FORM = "topology.transition"

#: The families of mutually alternative kinds. Closed, and declared here rather than inferred,
#: because "which of these two findings replaced which" is the entire question this form answers
#: and a producer that grouped them by guesswork would answer a different one each time.
FAMILIES: Mapping[str, frozenset] = {
    "nesting": frozenset({RelationKind.NESTED_WITHIN, RelationKind.CONTAINS}),
    "planarity": frozenset({RelationKind.DISJOINT, RelationKind.MEETS, RelationKind.OVERLAPS}),
    "depth": frozenset({RelationKind.IN_FRONT_OF, RelationKind.COPLANAR}),
}

#: The kinds that mean something else when the arrow is turned round. `contains` ↔ `nested_within`
#: is one measurement read from two ends — the same law `containment.py` normalises on.
INVERSE: Mapping[RelationKind, RelationKind] = {
    RelationKind.NESTED_WITHIN: RelationKind.CONTAINS,
    RelationKind.CONTAINS: RelationKind.NESTED_WITHIN,
}

#: The kinds that read the same from either end, so turning the pair round changes nothing.
SYMMETRIC = frozenset({RelationKind.MEETS, RelationKind.OVERLAPS, RelationKind.DISJOINT,
                       RelationKind.COPLANAR})

#: The family whose pairs are keyed in the order they were MEASURED. `in_front_of` has no inverse
#: in this vocabulary, so a canonical reordering would have to either invent one or silently assert
#: the claim backwards.
ORDERED_FAMILIES = frozenset({"depth"})


@dataclass(frozen=True)
class MeasurementDelta:
    """One number that moved between the revisions, with both values.

    THE CLEARANCE AND THE CONTACT LOCUS LIVE HERE. `TransitionChange` has four words and none of
    them is "the band moved" — a pair that still `meets` after a refinement is `unchanged` in kind
    however far the contact travelled. So the movement is recorded as the numbers it actually
    consists of, beside the transition rather than inside it.
    """
    transition_id: str
    measurement: str
    before: Optional[float]
    after: Optional[float]

    @property
    def moved(self) -> bool:
        return self.before != self.after


@dataclass(frozen=True)
class TransitionReading(FormProduction):
    """The comparison, plus the numbers the four-word vocabulary cannot carry."""
    deltas: Tuple[MeasurementDelta, ...] = ()
    unchanged_pairs: Tuple[str, ...] = ()

    def deltas_for(self, transition_id: str) -> Tuple[MeasurementDelta, ...]:
        return tuple(d for d in self.deltas if d.transition_id == transition_id)


def _family(kind: RelationKind) -> Optional[str]:
    return next((name for name, kinds in FAMILIES.items() if kind in kinds), None)


def _canonical(relation: TopologyRelation
               ) -> Optional[Tuple[str, str, str, RelationKind, RelationEndpoint,
                                   RelationEndpoint]]:
    """One relation, keyed the way both sides of a comparison will key it.

    Returns `(family, node_a, node_b, kind, endpoint_a, endpoint_b)` or None for a kind this form
    does not group. The endpoints come back in the canonical order, so a `RelationState` built from
    the before side and one built from the after side name the same instance in the same slot —
    which is precisely what Lane A's validator checks and refuses.
    """
    family = _family(relation.kind)
    if family is None:
        return None
    source, target = endpoint_key(relation.source), endpoint_key(relation.target)
    if family in ORDERED_FAMILIES or source <= target:
        return family, source, target, relation.kind, relation.source, relation.target
    if relation.kind in INVERSE:
        return family, target, source, INVERSE[relation.kind], relation.target, relation.source
    if relation.kind in SYMMETRIC:
        return family, target, source, relation.kind, relation.target, relation.source
    return None


def _state_index(reading: Reading, *, refusals: List[RefusalRecord], omitted: List[Omission],
                 side: str, roster: Optional[Roster]
                 ) -> Tuple[Dict[Tuple[str, str, str], List[TopologyRelation]],
                            Dict[str, RevisionRef]]:
    """Every relation this side holds, grouped by `(family, node_a, node_b)`, and its revisions.

    A LIST PER KEY, not a single relation, so that a family holding two kinds at once is VISIBLE at
    the point of comparison instead of being resolved by whichever one arrived last.

    THE REVISION MAP IS THE SECOND RETURN AND IT IS NOT AN OPTIMISATION. A nesting that exists in
    the before state and not in the after one still needs the AFTER revisions to be citable —
    otherwise the disappearance would be recorded against two identical revisions, which Lane A
    reads as a re-measurement and refuses. Those revisions are in that side's other relations about
    the same instances, so they are collected once per side rather than hunted for per pair.
    """
    index: Dict[Tuple[str, str, str], List[TopologyRelation]] = {}
    revisions: Dict[str, RevisionRef] = {}
    for relation in reading.relations:
        keyed = _canonical(relation)
        if keyed is None:
            omitted.append(Omission(relation.relation_id, "not_a_structural_kind",
                                    f"{relation.kind.value} belongs to no comparable family"))
            continue
        family, a, b, _, end_a, end_b = keyed
        if a == b:
            omitted.append(Omission(a, "self_pair", "a pair of one shape has no transition"))
            continue
        if roster is not None and not (roster.holds(a) and roster.holds(b)):
            continue
        missing = [e for e in (end_a, end_b) if e.geometry_rev is None]
        if missing:
            for endpoint in missing:
                refusals.append(not_a_revision(f"{side}: {endpoint_key(endpoint)}", form_key=FORM))
                omitted.append(Omission(endpoint_key(endpoint), "revision_missing",
                                        f"the {side} state carries no geometry_rev"))
            continue
        revisions.setdefault(a, _revision(end_a))
        revisions.setdefault(b, _revision(end_b))
        index.setdefault((family, a, b), []).append(relation)
    return index, revisions


def _revision(endpoint: RelationEndpoint) -> RevisionRef:
    return RevisionRef(artifact_id=endpoint.artifact_id, instance_id=endpoint.instance_id,
                       geometry_rev=int(endpoint.geometry_rev))


def _ends(relations: Sequence[TopologyRelation]) -> Tuple[RelationEndpoint, RelationEndpoint]:
    keyed = _canonical(relations[0])
    assert keyed is not None
    return keyed[4], keyed[5]


def produce_transition(before: Sequence[Supplied], after: Sequence[Supplied], *,
                       roster: Optional[Roster] = None) -> TransitionReading:
    """Compare two readings of the same scene, taken at two revisions of its extents.

    `before` and `after` are `topology.pair_relation` artifacts. Which is which is the caller's
    statement, and this producer does not try to work it out from revision numbers: a revision is
    monotonic within one region and says nothing about the order two different scenes were measured
    in, so inferring it would be guessing at exactly the fact the record is supposed to fix.
    """
    was, now = Reading.of(before), Reading.of(after)
    refusals: List[RefusalRecord] = []
    omitted: List[Omission] = []

    deferred = check_producible(FORM)
    if deferred is not None:                       # today: this form is `deferred`
        refusals.append(deferred)
    for reading in (was, now):
        wrong_form = check_inputs_are_read(FORM, reading.form_keys)
        if wrong_form is not None:
            refusals.append(wrong_form)

    left, left_rev = _state_index(was, refusals=refusals, omitted=omitted, side="before",
                                  roster=roster)
    right, right_rev = _state_index(now, refusals=refusals, omitted=omitted, side="after",
                                    roster=roster)

    transitions: List[TopologyTransition] = []
    deltas: List[MeasurementDelta] = []
    unchanged: List[str] = []
    for key in sorted(set(left) | set(right)):
        family, a, b = key
        was_here, now_here = left.get(key, []), right.get(key, [])
        crowded = [(side, group) for side, group in (("before", was_here), ("after", now_here))
                   if len(group) > 1]
        if crowded:
            for side, group in crowded:
                omitted.append(Omission(
                    f"{a}~{b}/{family}", "ambiguous_state",
                    f"the {side} state holds {sorted(r.kind.value for r in group)} at once, and a "
                    f"relation state carries one kind. Naming a main one would decide which "
                    f"measurement counted"))
            continue
        if not was_here and not now_here:
            continue

        # EACH SIDE BRINGS ITS OWN REVISIONS, which is the entire point of citing four of them.
        # A pair whose family is absent on one side takes that side's revisions from the other
        # relations it measured about the same two instances; a pair one side never saw at all
        # cannot be compared, and says so.
        unseen = [k for k in (a, b) if k not in left_rev or k not in right_rev]
        if unseen:
            for node in unseen:
                omitted.append(Omission(node, "revision_missing",
                                        "only one of the two states measured this instance, so "
                                        "there is no revision to cite on the other side"))
            continue
        before_state = RelationState(
            source=left_rev[a], target=left_rev[b],
            kind=(_canonical(was_here[0])[3] if was_here else None),
            measurements=dict(was_here[0].measurements) if was_here else {})
        after_state = RelationState(
            source=right_rev[a], target=right_rev[b],
            kind=(_canonical(now_here[0])[3] if now_here else None),
            measurements=dict(now_here[0].measurements) if now_here else {})

        if (before_state.source.geometry_rev == after_state.source.geometry_rev
                and before_state.target.geometry_rev == after_state.target.geometry_rev):
            omitted.append(Omission(f"{a}~{b}/{family}", "revision_unchanged",
                                    "both sides cite the same two revisions, so this pair was "
                                    "measured twice rather than revised"))
            unchanged.append(f"{a}~{b}/{family}")
            continue

        change = _change(before_state.kind, after_state.kind)
        transition_id = minted("trans", family, a, b)
        transitions.append(TopologyTransition(
            transition_id=transition_id, before=before_state, after=after_state, change=change))
        deltas.extend(_deltas(transition_id, before_state.measurements, after_state.measurements))

    basis = weaker_basis(list(was.bases) + list(now.bases))
    payload = TopologyTransitionPayload(
        variant="topology_transition",
        # WHAT WAS COMPARED IS TWO REVISION-STATES OF THE SCENE, and the count says so. The field
        # exists to prove something looked; counting the distinct revision numbers instead would
        # add revisions of different instances together, which is arithmetic on incomparable things.
        revisions_compared=2 if (before and after) else len([s for s in (before, after) if s]),
        transitions=transitions)

    return TransitionReading(
        form_key=FORM, payload=payload, producible=deferred is None,
        ceiling=ceiling_for(FORM, basis=basis,
                            input_statuses=list(was.statuses) + list(now.statuses)),
        basis=basis, refusals=tuple(refusals),
        input_artifact_ids=was.artifact_ids + now.artifact_ids,
        input_statuses=was.statuses + now.statuses, omitted=tuple(omitted),
        deltas=tuple(deltas), unchanged_pairs=tuple(unchanged))


def _change(was: Optional[RelationKind], now: Optional[RelationKind]) -> TransitionChange:
    """The word for what happened. The same arithmetic Lane A's validator re-derives and checks,
    written here rather than imported because a producer that could not state it independently
    would be asserting whatever the validator was willing to accept."""
    if was is None:
        return TransitionChange.APPEARED
    if now is None:
        return TransitionChange.DISAPPEARED
    return TransitionChange.UNCHANGED if was is now else TransitionChange.CHANGED


def _deltas(transition_id: str, before: Mapping[str, float],
            after: Mapping[str, float]) -> List[MeasurementDelta]:
    """Every number that differs, both values kept.

    A key present on one side and absent on the other is a delta with a None on that side, because
    "the clearance stopped being measurable" is a change and reporting it as zero would be a
    measurement nobody made.
    """
    out: List[MeasurementDelta] = []
    for name in sorted(set(before) | set(after)):
        a, b = before.get(name), after.get(name)
        if a != b:
            out.append(MeasurementDelta(transition_id=transition_id, measurement=name,
                                        before=a, after=b))
    return out


__all__ = ["FORM", "FAMILIES", "INVERSE", "SYMMETRIC", "ORDERED_FAMILIES", "MeasurementDelta",
           "TransitionReading", "produce_transition"]
