"""
PERCEPTUAL-FORMS-001D — `topology.uncertain_relation_set`: what would be true, if that reading were right.

IF THE FRAGMENTS ARE ONE OBJECT THEN IT OVERLAPS THE PLANE; IF THEY ARE TWO THEN ONE OF THEM STANDS
CLEAR OF IT. Both are worth recording, and neither is a measurement. The masks under them were
measured; the relation between things that may not be those things was not.

EACH HYPOTHESIS IS EVALUATED SEPARATELY AND NOTHING IS EVER MERGED. A pair that comes back
`overlaps` under one reading and `disjoint` under another produces TWO conditional relations, each
naming its condition. There is no arithmetic in this module that could combine them, and that is
deliberate: averaging `overlaps` with `disjoint` yields a number no measurement supports and a kind
neither reading found. Incompatible relation kinds are not near each other on any scale, so there
is no scale on which to average them.

THE STABLE AND THE DEPENDENT ARE REPORTED APART. A relation that holds under every declared
hypothesis is a different kind of fact from one that holds under one of them: the first survives
whichever way the ambiguity resolves, and the second is the ambiguity. `stable` and `dependent` on
the reading say which is which. THEY DO NOT CHANGE THE PAYLOAD — every relation in it keeps its
`conditioned_on`, including the stable ones, because a relation that dropped its condition on the
grounds of being stable would read exactly like a measured one, which is the substitution this form
exists to make impossible.

NOTHING IS CURATED BY CONFIDENCE. An alternative weighted 0.01 is evaluated, recorded and reported
exactly like one weighted 0.99. A producer that dropped the unlikely readings would be resolving
the ambiguity this record exists to preserve, silently, in a module nobody reviews for that — and
the low-weight reading is the one a person most needs to see before they choose.

NOTHING HERE IS `measured` OR `visible`. `ConditionalRelation` refuses both outright, and the form's
declared partitions — `unresolved_alternative` and `interpretive_grouping` — cap it independently
of whatever basis the relations under it were computed from. A mask-basis relation that holds only
under a hypothesis is `interpretive`; a `declared`-basis one is `uncertain`.

PURE. No database, no network, no model, no clock. Readings in, conditionals out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.perception_lab import (BASIS_CEILINGS, PARTITION_CEILINGS, STATUS_ORDER,
                                            ConditionalRelation, EpistemicPartition,
                                            EpistemicStatus, HypothesisCitation, RefusalRecord,
                                            RelationKind, TopologyRelation,
                                            TopologyUncertainRelationsPayload)
from backend.services.perception_lab.topology_forms.adjacency import DIRECTED_KINDS
from backend.services.perception_lab.topology_forms.production import (FormProduction, Omission,
                                                                       ceiling_for,
                                                                       check_inputs_are_read,
                                                                       check_producible, dangling,
                                                                       minted, weaker_basis)
from backend.services.perception_lab.topology_forms.sources import (Carried, HypothesisSet, Reading,
                                                                    Roster, Supplied, endpoint_key)

FORM = "topology.uncertain_relation_set"

#: The partition this form is produced under. `unresolved_alternative`, not `interpretive_grouping`:
#: the relations were not grouped by a reading of what they mean, they were computed under a
#: hypothesis that has not been resolved. Its ceiling is `uncertain`, which the form's own
#: `interpretive` ceiling then sits above — so the weaker of the two governs, as it should.
PARTITION = EpistemicPartition.UNRESOLVED_ALTERNATIVE.value

#: The strongest thing a relation may claim when it holds only under a hypothesis. Restated from
#: `ConditionalRelation`'s own validator rather than imported, so that a producer which stopped
#: capping would be caught by the schema rather than merely agreeing with it.
CONDITIONAL_CEILING = EpistemicStatus.INTERPRETIVE


@dataclass(frozen=True)
class HypothesisReading(FormProduction):
    """The conditional set, plus the split the payload deliberately does not encode.

    `stable` and `dependent` are keys of the form `kind|node_a|node_b`. They are a reading OF the
    payload rather than a part of it, so that a caller who wants the split gets it and a caller who
    reads only the payload cannot mistake a stable relation for a measured one.
    """
    stable: Tuple[str, ...] = ()
    dependent: Tuple[str, ...] = ()
    evaluated: Tuple[str, ...] = ()
    unevaluated: Tuple[str, ...] = ()

    def relations_for(self, hypothesis_id: str) -> Tuple[ConditionalRelation, ...]:
        if self.payload is None:
            return ()
        return tuple(r for r in self.payload.relations if r.conditioned_on == hypothesis_id)


def _pair_key(relation: TopologyRelation) -> str:
    """The identity of a FINDING, independent of which hypothesis produced it.

    Directed kinds keep their order because the arrow is the claim; symmetric ones are sorted so
    that the same finding reached from either end compares equal. The same rule the graph uses, and
    imported from it rather than restated, because two spellings of "which way round is this" is
    how a stable relation starts looking dependent.
    """
    source, target = endpoint_key(relation.source), endpoint_key(relation.target)
    if relation.kind not in DIRECTED_KINDS:
        source, target = sorted((source, target))
    return f"{relation.kind.value}|{source}|{target}"


def _capped(relation: TopologyRelation) -> EpistemicStatus:
    """The status a conditional reading of this relation may carry.

    Two ceilings, applied together: the basis's — a box relation was never better than
    `interpretive` — and the conditional one, which is what makes a perfectly measured mask
    relation stop being `measured` the moment it hangs on a reading that may be wrong.
    """
    ceiling = min(BASIS_CEILINGS[relation.basis], CONDITIONAL_CEILING,
                  PARTITION_CEILINGS[EpistemicPartition.UNRESOLVED_ALTERNATIVE],
                  key=lambda s: STATUS_ORDER[s])
    return min(relation.epistemic_status, ceiling, key=lambda s: STATUS_ORDER[s])


def produce_uncertain_relations(hypotheses: Carried,
                                readings: Mapping[str, Sequence[Supplied]], *,
                                roster: Optional[Roster] = None) -> HypothesisReading:
    """Assemble the conditional relation set over an extent hypothesis set.

    `hypotheses` is an `extent.hypothesis_set` — as an artifact, or as the `(id, payload)` pair that
    form must use while no operation produces one. `readings` maps each alternative's id to the
    relation sets measured UNDER it.

    AN ALTERNATIVE WITH NO READING IS STILL DECLARED. It was considered and nothing was measured
    under it, and dropping it from the citations would shrink the space of readings a later person
    can see was open. It is named in `unevaluated`.
    """
    declared = HypothesisSet.of(hypotheses)
    refusals: List[RefusalRecord] = []
    omitted: List[Omission] = []

    deferred = check_producible(FORM)
    if deferred is not None:                       # today: this form is `deferred`
        refusals.append(deferred)

    known = {a.alternative_id for a in declared.alternatives}
    for hypothesis_id in sorted(readings):
        if hypothesis_id not in known:
            refusals.append(dangling(hypothesis_id, form_key=FORM,
                                     detail={"reason": "undeclared_hypothesis",
                                             "declared": sorted(known)}))
            omitted.append(Omission(hypothesis_id, "endpoint_dangling",
                                    "relations were supplied under a reading this hypothesis set "
                                    "does not declare, and a condition nobody can look up is a "
                                    "condition that has been dropped"))

    citations = [HypothesisCitation(
        hypothesis_id=alternative.alternative_id,
        artifact_id=alternative.artifact_id or declared.artifact_id,
        weight=alternative.weight) for alternative in declared.alternatives]

    relations: List[ConditionalRelation] = []
    seen_by_hypothesis: Dict[str, Set[str]] = {}
    artifact_ids: List[str] = [declared.artifact_id]
    statuses: List[EpistemicStatus] = [declared.epistemic_status]
    bases = [declared.epistemic_basis]
    evaluated: List[str] = []
    unevaluated: List[str] = []
    pairs_examined = 0

    for alternative in declared.alternatives:
        hypothesis_id = alternative.alternative_id
        supplied = readings.get(hypothesis_id)
        if not supplied:
            # NOT a refusal. Nothing went wrong; this reading simply had no relations measured
            # under it, and the citation stays so that the space of readings survives intact.
            unevaluated.append(hypothesis_id)
            continue
        evaluated.append(hypothesis_id)
        reading = Reading.of(supplied)
        wrong_form = check_inputs_are_read(FORM, reading.form_keys)
        if wrong_form is not None:
            refusals.append(wrong_form)
        artifact_ids.extend(reading.artifact_ids)
        statuses.extend(reading.statuses)
        bases.extend(reading.bases)
        pairs_examined += reading.pairs_examined

        held: Set[str] = set()
        for relation in reading.relations:
            source, target = endpoint_key(relation.source), endpoint_key(relation.target)
            if source == target:
                omitted.append(Omission(source, "self_pair",
                                        "a shape stands in no relation to itself"))
                continue
            outside = [k for k in (source, target)
                       if roster is not None and not roster.holds(k)]
            if outside:
                for key in outside:
                    refusals.append(dangling(key, form_key=FORM,
                                             detail={"relation_id": relation.relation_id,
                                                     "hypothesis_id": hypothesis_id}))
                    omitted.append(Omission(key, "endpoint_dangling",
                                            f"cited under {hypothesis_id} and not in the roster"))
                continue
            finding = _pair_key(relation)
            if finding in held:
                omitted.append(Omission(f"{hypothesis_id}/{finding}", "duplicate",
                                        f"{relation.relation_id} repeats a finding already held "
                                        f"under this reading"))
                continue
            held.add(finding)
            relations.append(ConditionalRelation(
                relation_id=minted("crel", hypothesis_id, relation.kind.value, source, target),
                kind=relation.kind, source=relation.source, target=relation.target,
                directed=relation.kind in DIRECTED_KINDS,
                basis=relation.basis, epistemic_status=_capped(relation),
                conditioned_on=hypothesis_id, measurements=dict(relation.measurements)))
        seen_by_hypothesis[hypothesis_id] = held

    stable, dependent = _split(seen_by_hypothesis)

    payload: Optional[TopologyUncertainRelationsPayload] = None
    if citations:
        payload = TopologyUncertainRelationsPayload(
            variant="topology_uncertain_relations",
            # EVERY PAIR EXAMINED UNDER EVERY READING. A pair compared under two hypotheses was
            # compared twice, and the second look is what makes the answer conditional rather than
            # measured — so counting it once would understate what was done.
            pairs_examined=pairs_examined,
            hypotheses=citations, relations=relations)
    else:
        refusals.append(dangling("no declared alternative", form_key=FORM,
                                 detail={"reason": "empty_hypothesis_set"}))

    basis = weaker_basis(bases)
    return HypothesisReading(
        form_key=FORM, payload=payload, producible=deferred is None,
        ceiling=ceiling_for(FORM, basis=basis, input_statuses=statuses, partition=PARTITION),
        basis=basis, refusals=tuple(refusals),
        input_artifact_ids=tuple(dict.fromkeys(artifact_ids)), input_statuses=tuple(statuses),
        omitted=tuple(omitted), stable=stable, dependent=dependent,
        evaluated=tuple(evaluated), unevaluated=tuple(unevaluated))


def _split(seen: Mapping[str, Set[str]]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Which findings survived every evaluated reading, and which did not.

    Computed over the EVALUATED hypotheses only. A reading nothing was measured under cannot
    contradict a finding, and treating its silence as disagreement would report every relation in
    the set as hypothesis-dependent the moment one alternative went unexamined.
    """
    if not seen:
        return (), ()
    every: Set[str] = set()
    for findings in seen.values():
        every |= findings
    stable = {f for f in every if all(f in findings for findings in seen.values())}
    return tuple(sorted(stable)), tuple(sorted(every - stable))


__all__ = ["FORM", "PARTITION", "CONDITIONAL_CEILING", "HypothesisReading",
           "produce_uncertain_relations"]
