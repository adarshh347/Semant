"""
PERCEPTUAL-FORMS-001D — `topology.containment_tree`: the nesting, and what the relations disagree about.

WHAT THIS ADDS TO A LIST OF `contains` RELATIONS. Ordering and transitivity, and nothing else. The
containment of a fountain in a courtyard was measured by `nestedness_organ` and recorded by the
Topology façade; a flat list of those measurements cannot answer "what is the fountain in, at the
nearest level", because the list also contains courtyard-in-palace and fountain-in-palace and says
nothing about which of the two holds the fountain more closely. The tree answers it by TRANSITIVE
REDUCTION, which is arithmetic over records already made — hence `exact_derivation`, hence a
ceiling no higher than the weakest artifact underneath.

DIRECTION IS THE CLAIM, AND IT SURVIVES BOTH SPELLINGS. The façade records one measurement from
two ends: `nested_within` reads source→target as "the source lies inside the target", `contains`
reads the same arrow as "the source holds the target". Both normalise to the same child→parent
edge here, so a tree assembled from a set of `contains` relations and a tree assembled from their
inverses are the same tree. A producer that read only one spelling would silently build half a
forest out of a set that measured all of it.

THE THREE THINGS THAT CAN GO WRONG, AND NOT ONE OF THEM IS SILENTLY RESOLVED:

  A REDUNDANT ANCESTOR IS ABSORBED, NOT DROPPED. basin ⊂ fountain ⊂ court, plus a measured
  basin ⊂ court. The last is implied by the first two, so the tree holds the nearest parent and
  `implied` names the relation the reduction absorbed. Nothing is lost: the reader still reads
  basin inside court, by walking.

  INCOMPARABLE PARENTS ARE A CONFLICT, AND THE NODE LEAVES THE TREE. A shape inside two
  overlapping shapes that do not contain one another is in two places, and there is no arrangement
  of `ContainmentNode` that can say so — it holds ONE `parent_node_id`. The tempting move is to
  list it as a root, and that is the move this module refuses: `root_node_ids` means "nothing
  holds it", so a disputed node parked there would read as a finding of top-level-ness that no
  measurement supports. It is excluded, both candidates are named in `conflicts`, and the
  ambiguity is a record rather than an absence.

  A CYCLE IS REPORTED, NEVER BROKEN. A ⊂ B ⊂ A means two measurements disagree — different bases,
  different revisions, or a genuine contradiction — and dropping whichever edge makes the tree
  validate would hide exactly the thing worth reading. Lane A's `_acyclic` refuses to validate
  one, so a cycle must be caught here or the payload cannot be built at all.

EXCLUSION CASCADES, and this is the part that is easy to get wrong. Excluding a node excludes the
nodes whose parentage ran THROUGH it: `_acyclic` requires that every `parent_node_id` names a node
the record holds, so a child left behind pointing at a removed parent would not validate — and
re-rooting it would assert a top-level-ness measured containment contradicts. They leave together,
with `orphaned_by_exclusion` on the ones that leave for that reason, so the two kinds of departure
never get counted as one.

GEOMETRIC CONTAINMENT IS NOT PART-WHOLE, AND THIS MODULE NEVER SAYS IT IS. A hat on a table is
inside the table's bounding shape and is not part of the table; a face inside a portrait is inside
a painting and is not a component of it. Nothing here reads a label, and `ContainmentNode` has no
field in which a semantic relationship could be recorded, so the absence is structural rather than
disciplined.

PURE. No database, no network, no model, no clock. Relations in, a forest out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.perception_lab import (BASIS_CEILINGS, STATUS_ORDER, ContainmentNode,
                                            EpistemicBasis, EpistemicStatus, RefusalRecord,
                                            RelationEndpoint, RelationKind,
                                            TopologyContainmentTreePayload, TopologyRelation)
from backend.services.perception_lab.topology_forms.production import (FormProduction, Omission,
                                                                       ceiling_for,
                                                                       check_inputs_are_read,
                                                                       check_producible, dangling,
                                                                       weaker_basis, weakest)
from backend.services.perception_lab.topology_forms.sources import (Reading, Roster, Supplied,
                                                                    endpoint_key)

FORM = "topology.containment_tree"

#: The two spellings of one measurement. Both are directed, and `directed` on the relation says so;
#: what differs is which end the arrow's word describes.
CONTAINMENT_KINDS = (RelationKind.NESTED_WITHIN, RelationKind.CONTAINS)

#: Where the occupancy of a child in its parent comes from. `nestedness_organ` computes
#: `scale_ratio = area(inner) / area(outer)` and the façade carries it through under that name, so
#: reading it here is quoting a measurement rather than making one. It is child-over-parent in
#: BOTH spellings: `contains` was measured with the endpoints swapped, so its `scale_ratio` is
#: already the target's share of the source.
OCCUPANCY_KEY = "scale_ratio"


@dataclass(frozen=True)
class ContainmentConflict:
    """A disagreement the relations contain, named so that it can be looked up.

    `kind` is `ambiguous_parents` or `cycle`. Both mean the same thing to a reader — the
    measurements do not compose into a tree here — and they mean different things to whoever fixes
    it, which is why they are not one word.
    """
    kind: str
    node_key: str
    candidates: Tuple[str, ...]
    relation_ids: Tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class ContainmentReading(FormProduction):
    """The forest, plus the two things the payload has nowhere to hold.

    `conflicts` is where the ambiguity went. `implied` is the relations the transitive reduction
    absorbed — kept because "this edge is redundant" and "this edge was dropped" look identical
    from outside and only one of them is true.
    """
    conflicts: Tuple[ContainmentConflict, ...] = ()
    implied: Tuple[str, ...] = ()


def _child_parent(relation: TopologyRelation) -> Tuple[str, str]:
    """One relation, normalised to (child, parent). The inverse law, in one place.

    `nested_within(A→B)`: A lies inside B, so B is A's candidate parent.
    `contains(A→B)`:      A holds B, so A is B's candidate parent.
    """
    source, target = endpoint_key(relation.source), endpoint_key(relation.target)
    if relation.kind is RelationKind.NESTED_WITHIN:
        return source, target
    return target, source


def produce_containment_tree(relation_sets: Sequence[Supplied], *,
                             roster: Optional[Roster] = None) -> ContainmentReading:
    """Assemble the containment forest over the supplied relation sets.

    `roster`, when given, is the set of endpoints this tree may hold — read off the extent
    artifacts the caller supplied. A relation citing anything outside it is refused as a dangling
    reference and contributes no edge, because a nesting assembled over an endpoint nobody supplied
    would be a structure about something this record cannot show.
    """
    reading = Reading.of(relation_sets)
    refusals: List[RefusalRecord] = []
    omitted: List[Omission] = []
    conflicts: List[ContainmentConflict] = []

    deferred = check_producible(FORM)
    if deferred is not None:                       # not today: this form is `experimental`
        refusals.append(deferred)
    wrong_form = check_inputs_are_read(FORM, reading.form_keys)
    if wrong_form is not None:
        refusals.append(wrong_form)

    # ── the edges, normalised and bounded ──
    candidates: Dict[str, Dict[str, TopologyRelation]] = {}
    mentioned: Dict[str, List[TopologyRelation]] = {}
    endpoints: Dict[str, RelationEndpoint] = dict(reading.endpoints)
    if roster is not None:
        endpoints.update(roster.endpoints)

    for relation in reading.relations:
        if relation.kind not in CONTAINMENT_KINDS:
            omitted.append(Omission(relation.relation_id, "not_a_structural_kind",
                                    f"{relation.kind.value} is not a nesting"))
            continue
        child, parent = _child_parent(relation)
        if child == parent:
            omitted.append(Omission(child, "self_pair",
                                    "a shape inside itself is not a level of a nesting"))
            continue
        outside = [k for k in (child, parent) if roster is not None and not roster.holds(k)]
        if outside:
            for key in outside:
                refusals.append(dangling(key, form_key=FORM,
                                         detail={"relation_id": relation.relation_id}))
                omitted.append(Omission(key, "endpoint_dangling",
                                        f"cited by {relation.relation_id} and not in the roster"))
            continue
        if parent in candidates.get(child, {}):
            omitted.append(Omission(f"{child}<{parent}", "duplicate",
                                    f"{relation.relation_id} repeats a nesting already held"))
            continue
        candidates.setdefault(child, {})[parent] = relation
        mentioned.setdefault(child, []).append(relation)
        mentioned.setdefault(parent, []).append(relation)

    # ── cycles, before anything is reduced ──
    #
    # Found on the candidate graph rather than on the finished tree, because the reduction below
    # walks ancestors and a cycle would make that walk unbounded. A cycle detected afterwards would
    # be a cycle detected by hanging.
    cyclic = _cyclic_nodes(candidates)
    for key in sorted(cyclic):
        involved = tuple(sorted(candidates.get(key, {})))
        conflicts.append(ContainmentConflict(
            kind="cycle", node_key=key, candidates=involved,
            relation_ids=tuple(sorted(r.relation_id for r in candidates.get(key, {}).values())),
            detail=("this nesting closes a loop, so two measurements disagree. Breaking it here "
                    "would hide the disagreement instead of reporting it")))
        omitted.append(Omission(key, "containment_cycle",
                                f"in a containment loop with {list(involved)}"))
    held = {k for k in _all_keys(candidates) if k not in cyclic}

    # ── the reduction: the NEAREST candidate parent, or a conflict ──
    #
    # ITERATED TO A FIXED POINT, because an exclusion propagates. A node leaves when its holders
    # are incomparable; the node it was holding then has no held holder left, and re-rooting THAT
    # one would claim a top-level-ness the relations contradict just as loudly. So the pass runs
    # again over what remains until a pass changes nothing.
    parent_of: Dict[str, str] = {}
    parent_via: Dict[str, TopologyRelation] = {}
    implied: List[str] = []
    while True:
        parent_of, parent_via, implied = {}, {}, []
        ambiguous: List[Tuple[str, Dict[str, TopologyRelation]]] = []
        orphans: List[Tuple[str, Tuple[str, ...]]] = []
        for child in sorted(candidates):
            if child not in held:
                continue
            offered = {p: r for p, r in candidates[child].items() if p in held}
            if not offered:
                if candidates[child]:          # it had holders, and every one of them left
                    orphans.append((child, tuple(sorted(candidates[child]))))
                continue
            nearest = _nearest(offered, candidates, held)
            if nearest is None:
                ambiguous.append((child, offered))
                continue
            parent_of[child] = nearest
            parent_via[child] = offered[nearest]
            implied.extend(sorted(r.relation_id for p, r in offered.items() if p != nearest))
        if not ambiguous and not orphans:
            break
        for child, offered in ambiguous:
            conflicts.append(ContainmentConflict(
                kind="ambiguous_parents", node_key=child, candidates=tuple(sorted(offered)),
                relation_ids=tuple(sorted(r.relation_id for r in offered.values())),
                detail=("two candidate holders that do not contain one another. The nesting is "
                        "real in both readings and this record holds one parent, so it names "
                        "neither. See topology.uncertain_relation_set for the form that can hold "
                        "both")))
            omitted.append(Omission(child, "containment_conflict",
                                    f"held by {sorted(offered)}, which are incomparable"))
            held.discard(child)
        for child, had in orphans:
            omitted.append(Omission(child, "orphaned_by_exclusion",
                                    f"every holder it was measured inside — {list(had)} — left "
                                    f"the tree, and re-rooting it would claim a top-level-ness "
                                    f"the relations contradict"))
            held.discard(child)

    nodes = [_node(key, parent_of.get(key), parent_via.get(key), mentioned.get(key, ()), endpoints)
             for key in sorted(held)]
    basis = weaker_basis([n.basis for n in nodes] or list(reading.bases))
    payload = TopologyContainmentTreePayload(
        variant="topology_containment_tree", pairs_examined=reading.pairs_examined, nodes=nodes,
        root_node_ids=sorted(n.node_id for n in nodes if n.parent_node_id is None))

    return ContainmentReading(
        form_key=FORM, payload=payload, producible=deferred is None,
        ceiling=ceiling_for(FORM, basis=basis, input_statuses=reading.statuses), basis=basis,
        refusals=tuple(refusals), input_artifact_ids=reading.artifact_ids,
        input_statuses=reading.statuses, omitted=tuple(omitted),
        conflicts=tuple(conflicts), implied=tuple(sorted(set(implied))))


# ── the graph arithmetic, kept out of the producer so it can be read ─────────


def _all_keys(candidates: Mapping[str, Mapping[str, TopologyRelation]]) -> Set[str]:
    keys: Set[str] = set(candidates)
    for parents in candidates.values():
        keys.update(parents)
    return keys


def _reaches(start: str, candidates: Mapping[str, Mapping[str, TopologyRelation]]) -> Set[str]:
    """Every node reachable from `start` by following child→parent edges, in one or more steps."""
    seen: Set[str] = set()
    stack: List[str] = list(candidates.get(start, {}))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(candidates.get(node, {}))
    return seen


def _cyclic_nodes(candidates: Mapping[str, Mapping[str, TopologyRelation]]) -> Set[str]:
    """Every node that lies on a child→parent cycle — which is every node that holds itself.

    THE WHOLE CYCLE, not an entry point. "A and B disagree" is the finding, and naming only the
    node the search happened to start from would suggest the other one is fine.
    """
    return {key for key in _all_keys(candidates) if key in _reaches(key, candidates)}


def _ancestors(key: str, candidates: Mapping[str, Mapping[str, TopologyRelation]],
               held: Set[str]) -> Set[str]:
    """Every holder of `key`, transitively. Safe because the cyclic nodes are gone by now."""
    out: Set[str] = set()
    stack = [key]
    while stack:
        node = stack.pop()
        for parent in candidates.get(node, {}):
            if parent in held and parent not in out:
                out.add(parent)
                stack.append(parent)
    return out


def _nearest(offered: Mapping[str, TopologyRelation],
             candidates: Mapping[str, Mapping[str, TopologyRelation]],
             held: Set[str]) -> Optional[str]:
    """The one candidate parent contained in all the others, or None when they are incomparable.

    "Nearest" is not "smallest by area", and the difference matters: area is a measurement this
    module is not entitled to re-judge, and two shapes of similar size can nest. Nearest is the
    candidate every other candidate transitively holds — a fact about the recorded relations.
    """
    if len(offered) == 1:
        return next(iter(offered))
    for candidate in offered:
        others = set(offered) - {candidate}
        if others <= _ancestors(candidate, candidates, held):
            return candidate
    return None


def _node(key: str, parent: Optional[str], via: Optional[TopologyRelation],
          mentions: Sequence[TopologyRelation],
          endpoints: Mapping[str, RelationEndpoint]) -> ContainmentNode:
    """One level of the forest, carrying the basis of the measurement that put it there.

    A CHILD'S BASIS IS ITS PARENTAGE'S. That relation is the reason this node sits where it sits,
    so a box-basis nesting yields a box-basis node and the ceiling keeps it `interpretive` however
    confident the number is.

    A ROOT HAS NO PARENTAGE, so its basis is the WEAKEST of the relations that mention it. A root
    is in this tree because things were measured to be inside it, and the weakest of those
    measurements is what its presence rests on.
    """
    if via is not None:
        basis, status = via.basis, via.epistemic_status
        occupancy = via.measurements.get(OCCUPANCY_KEY)
    else:
        basis = weaker_basis([r.basis for r in mentions])
        status = weakest([r.epistemic_status for r in mentions] or [BASIS_CEILINGS[basis]])
        occupancy = None
    if STATUS_ORDER[status] > STATUS_ORDER[BASIS_CEILINGS[basis]]:
        status = BASIS_CEILINGS[basis]
    return ContainmentNode(
        node_id=key, endpoint=endpoints[key], parent_node_id=parent,
        occupancy_of_parent=(None if occupancy is None
                             else min(1.0, max(0.0, float(occupancy)))),
        basis=basis, epistemic_status=status)


__all__ = ["FORM", "CONTAINMENT_KINDS", "OCCUPANCY_KEY", "ContainmentConflict",
           "ContainmentReading", "produce_containment_tree"]
