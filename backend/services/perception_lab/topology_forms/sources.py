"""
PERCEPTUAL-FORMS-001D — what a structural producer is handed, and the identity it reads off it.

TOPOLOGY CONSUMES SUPPLIED ARTIFACTS AND NEVER GOES AND GETS ITS OWN. That rule is Lane C's, and
it is inherited here without softening: these producers take `PerceptualArtifact` records — a
`topology.pair_relation` set, an `extent.hypothesis_set` — and there is no code path in this
package that could produce one. The isolation test that matters is not a promise in a docstring;
it is that nothing in this package imports Extent, Depth, a database or a router, and the suite
walks the import closure to prove it.

WHY THE INPUT IS AN ARTIFACT RATHER THAN A LIST OF RELATIONS. Three reasons, and each one is a
law that would otherwise have nowhere to live:

    THE FORM GATE BECOMES REAL. `check_input_forms` refuses a supplied artifact whose FORM the
    consuming form does not read. Handed a bare list of `TopologyRelation` objects there would be
    nothing to check, and the gate would be a function nobody calls.

    THE CEILING BECOMES COMPUTABLE. An `exact_derivation` may claim no more than the weakest
    artifact it derived from, and "the weakest artifact" is a fact about artifacts. A list of
    relations carries per-relation statuses and not the artifact-level one the façade wrote after
    weighing every basis in the set.

    THE PROVENANCE SURVIVES. `input_artifact_ids` on the production is what lets a later reader
    walk back from a graph to the measurements under it.

NODE IDENTITY IS `artifact_id#instance_id`, AND THAT IS THE SAME STRING THE BROWSER USES. Lane E's
`relationGraph` already keys its nodes that way. Matching it is not a coincidence to be tidied
later: it is what makes the browser's derived graph a CHECK against a recorded one rather than a
second graph that happens to be beside it.

A LABEL IS NEVER PART OF AN IDENTITY. Two instances a person called "pier" are two nodes. Merging
them by name would assert a relation nobody measured, and the assertion would be invisible because
the merged node would look exactly like a measured one.

PURE. No database, no network, no model, no clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from backend.schemas.perception_lab import (EpistemicBasis, EpistemicStatus, PerceptualArtifact,
                                            RelationEndpoint, RelationKind, RevisionRef,
                                            TopologyRelation)

#: The artifact this package accepts, in either shape a caller may hold it: the typed record, or
#: the JSON it crossed the wire as. Both are validated through `PerceptualArtifact` before a single
#: relation is read, so a producer never sees a half-shaped input.
Supplied = Union[PerceptualArtifact, Mapping[str, Any]]


class NotARelationSet(TypeError):
    """The supplied artifact is not a `topology.pair_relation`. Raised rather than refused: this
    is a caller handing the wrong TYPE, not a person supplying the wrong artifact, and the typed
    refusal for the latter is `check_input_forms`."""


def as_artifact(supplied: Supplied) -> PerceptualArtifact:
    if isinstance(supplied, PerceptualArtifact):
        return supplied
    return PerceptualArtifact.model_validate(dict(supplied))


def endpoint_key(endpoint: Union[RelationEndpoint, RevisionRef]) -> str:
    """`art_x#inst_y` — the composite Lane E's browser graph already keys on.

    An instance id is unique inside its artifact and nowhere else, which is the reason
    `InstanceRef` requires both fields and the reason this key carries both. `inst_1` alone names
    every extent set's first mask at once.
    """
    return f"{endpoint.artifact_id}#{endpoint.instance_id}"


def revision_key(ref: RevisionRef) -> str:
    return f"{ref.artifact_id}#{ref.instance_id}@{ref.geometry_rev}"


@dataclass(frozen=True)
class RelationSet:
    """One `topology.pair_relation` artifact, as these producers read it.

    `pairs_examined` is carried through rather than recomputed. It is the field that distinguishes
    a measured emptiness from an absence of measurement, and a composition that recounted it from
    the relations it received would report `0` for a set that examined six pairs and found nothing
    — turning the one honest empty record into the dishonest one.
    """
    artifact_id: str
    relations: Tuple[TopologyRelation, ...]
    pairs_examined: int
    epistemic_status: EpistemicStatus
    epistemic_basis: EpistemicBasis
    form_key: str = "topology.pair_relation"

    @classmethod
    def of(cls, supplied: Supplied) -> "RelationSet":
        artifact = as_artifact(supplied)
        payload = artifact.measurement.payload
        if payload is None or payload.variant != "topology_relation_set":
            raise NotARelationSet(
                f"artifact {artifact.identity.artifact_id!r} carries "
                f"{artifact.measurement.payload_variant.value!r}, and these producers assemble "
                f"relations. Supply a topology.pair_relation artifact.")
        return cls(artifact_id=artifact.identity.artifact_id,
                   relations=tuple(payload.relations),
                   pairs_examined=int(payload.pairs_examined),
                   epistemic_status=artifact.measurement.epistemic_status,
                   epistemic_basis=artifact.measurement.epistemic_basis)


@dataclass(frozen=True)
class HypothesisSet:
    """One `extent.hypothesis_set` artifact — the competing readings a conditional relation hangs on.

    NOTHING HERE CURATES. The alternatives are carried in the order and at the weights they were
    written; a producer that dropped the low-weight ones would be resolving the ambiguity this
    record exists to preserve, and doing it silently in a module nobody reviews for that.
    """
    artifact_id: str
    alternatives: Tuple[Any, ...]
    alternatives_considered: int
    question: str
    weights_are_probabilities: bool
    epistemic_status: EpistemicStatus
    epistemic_basis: EpistemicBasis
    form_key: str = "extent.hypothesis_set"

    @classmethod
    def of(cls, supplied: Supplied) -> "HypothesisSet":
        artifact = as_artifact(supplied)
        payload = artifact.measurement.payload
        if payload is None or payload.variant != "extent_hypothesis_set":
            raise NotARelationSet(
                f"artifact {artifact.identity.artifact_id!r} carries "
                f"{artifact.measurement.payload_variant.value!r}, and a conditional relation set "
                f"hangs on extent hypotheses. Supply an extent.hypothesis_set artifact.")
        return cls(artifact_id=artifact.identity.artifact_id,
                   alternatives=tuple(payload.alternatives),
                   alternatives_considered=int(payload.alternatives_considered),
                   question=payload.question,
                   weights_are_probabilities=bool(payload.weights_are_probabilities),
                   epistemic_status=artifact.measurement.epistemic_status,
                   epistemic_basis=artifact.measurement.epistemic_basis)

    @property
    def ids(self) -> Tuple[str, ...]:
        return tuple(a.alternative_id for a in self.alternatives)


@dataclass(frozen=True)
class Reading:
    """Every relation supplied to one producer, with the artifacts they came from.

    `held` is the set of endpoint keys the supplied artifacts actually contain — which is what
    makes a dangling endpoint detectable. Note carefully what it is built from: THE ENDPOINTS THE
    RELATIONS THEMSELVES CITE. A relation set is a record about pairs, not a roster of instances,
    so "the endpoints this reading holds" can only mean the ones some supplied relation names.
    Widening it to whatever an extent set happens to contain would let a structure quote an
    endpoint no relation in evidence ever mentioned.
    """
    sets: Tuple[RelationSet, ...]
    relations: Tuple[TopologyRelation, ...]
    endpoints: Mapping[str, RelationEndpoint]
    pairs_examined: int

    @classmethod
    def of(cls, supplied: Sequence[Supplied]) -> "Reading":
        sets = tuple(RelationSet.of(s) for s in supplied)
        relations: List[TopologyRelation] = []
        endpoints: Dict[str, RelationEndpoint] = {}
        for source in sets:
            for relation in source.relations:
                relations.append(relation)
                for end in (relation.source, relation.target):
                    endpoints.setdefault(endpoint_key(end), end)
        return cls(sets=sets, relations=tuple(relations), endpoints=endpoints,
                   pairs_examined=sum(s.pairs_examined for s in sets))

    @property
    def artifact_ids(self) -> Tuple[str, ...]:
        return tuple(s.artifact_id for s in self.sets)

    @property
    def statuses(self) -> Tuple[EpistemicStatus, ...]:
        return tuple(s.epistemic_status for s in self.sets)

    @property
    def bases(self) -> Tuple[EpistemicBasis, ...]:
        return tuple(s.epistemic_basis for s in self.sets)

    @property
    def form_keys(self) -> Tuple[str, ...]:
        return tuple(s.form_key for s in self.sets)

    def holds(self, key: str) -> bool:
        return key in self.endpoints

    def of_kinds(self, *kinds: RelationKind) -> Tuple[TopologyRelation, ...]:
        wanted = set(kinds)
        return tuple(r for r in self.relations if r.kind in wanted)


__all__ = ["Supplied", "NotARelationSet", "as_artifact", "endpoint_key", "revision_key",
           "RelationSet", "HypothesisSet", "Reading"]
