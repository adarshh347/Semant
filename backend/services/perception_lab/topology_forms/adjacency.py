"""
PERCEPTUAL-FORMS-001D — `topology.adjacency_graph`: what touches what, across the whole scene.

THE NAVE AT WELLS. Pier, arch, pier, arch, receding. The interesting object is the repeated
structure, and it does not exist in any pair: `pier_1 meets pier_2` is a fact about two shapes, and
"a row of four" is a fact about the assembly. That is the whole of what this producer adds — the
assembly — and it adds no evidence, which is why it is `exact_derivation` and why it may claim no
more than the weakest relation set under it.

A NODE IS AN IDENTITY. `artifact_id#instance_id`, the same key Lane E's browser graph builds, and
never a label. Two piers a person called "pier" are two nodes, because a graph that merged them by
name would assert one edge where two were measured and the assertion would be invisible: the merged
node would look exactly like a measured one. Nothing in this package reads `naming`.

AN UNDIRECTED RELATION IS ONE EDGE, NOT TWO. `meets` reads the same both ways, so `A meets B` and
`B meets A` are one finding recorded once, keyed on the pair in a canonical order. A graph that
kept both would report a scene twice as densely connected as it was measured to be. The DIRECTED
kinds keep their direction, because there the arrow is the claim: `nested_within` says which of the
two is inside the other, and dropping the order would lose the only thing that measurement found.

THE GRAPH IS NOT ONLY ITS CONTACTS. `GraphEdge.kind` is the whole relation vocabulary and Lane A's
own committed example holds a `disjoint` edge, because "these two were compared and they are apart"
is a finding. So connectivity is asked separately — `contact_components` and `isolated` are computed
over `meets` alone — and a reader is never left to infer from a dense graph that everything touches.

BOUNDS AND OMISSIONS STAY VISIBLE, and they had to go somewhere. `TopologyAdjacencyGraphPayload`
holds `pairs_examined` and has no field for the members a bound excluded, so they live on the
production: `bounded_to`, and an `Omission` per member with the reason. A truncated graph that said
nothing about the truncation would read as coverage, which is the one thing a scene-wide record
must never do.

PURE. No database, no network, no model, no clock. Relations in, a graph out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.perception_lab import (EpistemicBasis, GraphEdge, GraphNode, RefusalRecord,
                                            RelationEndpoint, RelationKind,
                                            TopologyAdjacencyGraphPayload, TopologyRelation)
from backend.services.perception_lab.topology_forms.production import (FormProduction, Omission,
                                                                       ceiling_for,
                                                                       check_inputs_are_read,
                                                                       check_producible, dangling,
                                                                       minted, weaker_basis)
from backend.services.perception_lab.topology_forms.sources import (Carried, Reading, Roster,
                                                                    Supplied, carried,
                                                                    endpoint_key)

FORM = "topology.adjacency_graph"

#: The kinds whose arrow is a claim. Everything else reads the same from both ends and is recorded
#: once. Taken from `topologyView.DIRECTED_KINDS` in Lane E — one vocabulary, two runtimes.
DIRECTED_KINDS = frozenset({RelationKind.NESTED_WITHIN, RelationKind.CONTAINS,
                            RelationKind.IN_FRONT_OF})

#: What "connected" means in a graph that also records apartness. Contact, and nothing else.
CONTACT_KINDS = frozenset({RelationKind.MEETS})


@dataclass(frozen=True)
class AdjacencyReading(FormProduction):
    """The graph, plus the three questions the payload has nowhere to answer.

    `bounded_to` is the size of the declared member set, or None when the caller declared none —
    which is a different statement from a bound of zero. `contact_components` and `isolated` are
    connectivity under `meets` alone, so a reader never has to infer touching from density.
    """
    bounded_to: Optional[int] = None
    contact_components: Tuple[Tuple[str, ...], ...] = ()
    isolated: Tuple[str, ...] = ()


def _pair(relation: TopologyRelation) -> Tuple[str, str]:
    """The edge's two ends, in the order this graph records them.

    Directed kinds keep the order they were measured in. Undirected kinds are sorted, which is what
    makes `A meets B` and `B meets A` land on one edge with one id instead of two records of one
    finding.
    """
    source, target = endpoint_key(relation.source), endpoint_key(relation.target)
    if relation.kind in DIRECTED_KINDS:
        return source, target
    return tuple(sorted((source, target)))            # type: ignore[return-value]


def produce_adjacency_graph(relation_sets: Sequence[Supplied], *,
                            roster: Optional[Roster] = None,
                            loci: Sequence[Carried] = (),
                            max_nodes: Optional[int] = None) -> AdjacencyReading:
    """Assemble the scene graph over the supplied relation sets.

    `roster` declares which members the graph is over. Its presence changes two things: an endpoint
    outside it is refused rather than admitted, and a declared member that no relation mentions
    stays in the graph as an isolated node — which is how a disconnected scene tells "nothing
    touches it" apart from "it was never in the set".

    `loci` are `topology.contact_locus` records — as artifacts, or as the `(id, payload)` pair
    that form must use while it has no operation to produce it. Where one was recorded for a pair,
    the edge
    names it, so a reader can go and look at the band rather than at a pixel count. The edge does
    not CARRY the band: a graph able to hold geometry is a graph able to disagree with the
    measurement it depicts.

    `max_nodes` bounds the graph explicitly. Members beyond the bound are named in `omitted`, never
    dropped in silence.
    """
    reading = Reading.of(relation_sets)
    refusals: List[RefusalRecord] = []
    omitted: List[Omission] = []

    deferred = check_producible(FORM)
    if deferred is not None:                       # not today: this form is `experimental`
        refusals.append(deferred)
    wrong_form = check_inputs_are_read(FORM, reading.form_keys)
    if wrong_form is not None:
        refusals.append(wrong_form)

    # ── the members, and the bound on them ──
    endpoints: Dict[str, RelationEndpoint] = {}
    if roster is not None:
        endpoints.update(roster.endpoints)
        order = list(roster.keys)
    else:
        order = []
    for key, endpoint in reading.endpoints.items():
        if roster is not None and not roster.holds(key):
            continue
        if key not in endpoints:
            endpoints[key] = endpoint
            order.append(key)

    held = list(order)
    if max_nodes is not None and len(held) > max_nodes:
        for key in held[max_nodes:]:
            omitted.append(Omission(key, "bound_exceeded",
                                    f"the graph was bounded to {max_nodes} members and this one "
                                    f"is beyond it"))
        held = held[:max_nodes]
    inside = set(held)

    locus_for = _loci_by_pair(loci)

    # ── the edges ──
    edges: List[GraphEdge] = []
    seen: Set[Tuple[str, str, str]] = set()
    for relation in reading.relations:
        source, target = endpoint_key(relation.source), endpoint_key(relation.target)
        if source == target:
            omitted.append(Omission(source, "self_pair",
                                    "an edge from a node to itself is not a relation between two "
                                    "extents"))
            continue
        missing = [k for k in (source, target) if k not in inside]
        if missing:
            for key in missing:
                if roster is not None and not roster.holds(key):
                    refusals.append(dangling(key, form_key=FORM,
                                             detail={"relation_id": relation.relation_id}))
                    omitted.append(Omission(key, "endpoint_dangling",
                                            f"cited by {relation.relation_id} and not in the "
                                            f"roster"))
                else:
                    omitted.append(Omission(key, "bound_exceeded",
                                            f"{relation.relation_id} cites a member beyond the "
                                            f"bound"))
            continue
        a, b = _pair(relation)
        signature = (relation.kind.value, a, b)
        if signature in seen:
            omitted.append(Omission(f"{a}~{b}", "duplicate",
                                    f"{relation.relation_id} repeats a {relation.kind.value} "
                                    f"already held; an undirected relation is one edge"))
            continue
        seen.add(signature)
        edges.append(GraphEdge(
            edge_id=minted("edge", relation.kind.value, a, b),
            source_node_id=a, target_node_id=b, kind=relation.kind,
            directed=relation.kind in DIRECTED_KINDS,
            basis=relation.basis, epistemic_status=relation.epistemic_status,
            measurements=dict(relation.measurements),
            locus_artifact_id=locus_for.get(tuple(sorted((source, target))))))

    nodes = [GraphNode(node_id=key, endpoint=endpoints[key]) for key in held]
    basis = weaker_basis([e.basis for e in edges] or list(reading.bases))
    payload = TopologyAdjacencyGraphPayload(
        variant="topology_adjacency_graph", pairs_examined=reading.pairs_examined,
        nodes=nodes, edges=edges)

    components = _components(held, edges)
    return AdjacencyReading(
        form_key=FORM, payload=payload, producible=deferred is None,
        ceiling=ceiling_for(FORM, basis=basis, input_statuses=reading.statuses), basis=basis,
        refusals=tuple(refusals), input_artifact_ids=reading.artifact_ids,
        input_statuses=reading.statuses, omitted=tuple(omitted),
        bounded_to=(len(roster) if roster is not None else None),
        contact_components=components,
        isolated=tuple(c[0] for c in components if len(c) == 1))


def _loci_by_pair(loci: Sequence[Carried]) -> Dict[Tuple[str, str], str]:
    """Which recorded contact band belongs to which pair.

    Joined on the ENDPOINT PAIR rather than on a relation id, because a locus is a measurement of
    two shapes and a relation id names one run's reading of them. A band measured in an earlier run
    is still that pair's band.
    """
    out: Dict[Tuple[str, str], str] = {}
    for supplied in loci:
        artifact_id, payload = carried(supplied)
        if payload is None or payload.variant != "topology_contact_locus":
            continue
        for locus in payload.loci:
            pair = tuple(sorted((endpoint_key(locus.source), endpoint_key(locus.target))))
            out.setdefault(pair, artifact_id)
    return out


def _components(nodes: Sequence[str], edges: Sequence[GraphEdge]) -> Tuple[Tuple[str, ...], ...]:
    """The connected components under CONTACT alone.

    Not under every edge. A graph that also records `disjoint` findings is connected under "was
    compared to", and reporting that as connectivity would tell a reader that everything in the
    scene touches everything else.
    """
    parent: Dict[str, str] = {n: n for n in nodes}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for edge in edges:
        if edge.kind not in CONTACT_KINDS:
            continue
        a, b = find(edge.source_node_id), find(edge.target_node_id)
        if a != b:
            parent[a] = b
    grouped: Dict[str, List[str]] = {}
    for node in nodes:
        grouped.setdefault(find(node), []).append(node)
    return tuple(tuple(sorted(members)) for members in
                 sorted(grouped.values(), key=lambda m: (-len(m), sorted(m)[0])))


__all__ = ["FORM", "DIRECTED_KINDS", "CONTACT_KINDS", "AdjacencyReading",
           "produce_adjacency_graph"]
