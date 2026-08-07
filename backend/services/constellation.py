"""WAVE4 — the constellation: the neighbourhood of loci an agent can actually reach.

A scene view shows one picture. An agent lives in a **constellation** — regions across several
images, stitched by the relations it grounded — and this walks that neighbourhood out from a seed
locus to a bounded depth and returns what is there.

## The one thing this module will not do: invent an edge

Every relation here comes from something **persisted**. There are exactly three places a grounded
relation is durable in this system today, and this reads all three and nothing else:

    atlases.edges (kind=movement)   cross-image crossings the kernel grounded    Lane G / Lane M
    curator_proposals               measured claims awaiting a human             #172
    post.visual_marks               relations a curator committed                the ledger

A retina candidate the kernel refused is **not** in any of them, which is why "a refused pair must
not appear as a grounded edge" needs no filter here: refusals were never written down. That is
worth stating rather than relying on, because the day something starts persisting candidates this
module would happily draw them, and the guard would have to be built then.

## What the walk found, and why the number is small

The durable graph is nearly empty, and this module exists partly to make that visible. Every lane
in Wave 3 measured relations and **returned** them — into a transcript, which exited with the
process. Only the occlusion queue files anything. So a constellation drawn today is mostly one
image's worth of occlusions plus a single cross-image movement edge, and a viewer that quietly
padded that out with ungrounded proposals would be showing a world the agent cannot walk.

`reach()` reports its own bound and its own sources for that reason: a neighbourhood of three nodes
is a claim about what has been *filed*, not about what has been *measured*.

## Within-image and between-image are different kinds of edge

    within    occlusion — depth THROUGH one picture; both endpoints share a post
    between   nesting, chromatic rhyme, analogy — a crossing BETWEEN pictures

`#169` made that distinction real for movement, and it is carried on every edge here as `span`
rather than being left for a reader to infer from the endpoints. An agent traversing `in_front_of`
never leaves the image; one traversing `axis_nestedness` does, and those are not the same move.

PURE-ish: reads collections, writes nothing, and has no route, no model and no clock it was not
handed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.services.epistemics import STATUS_KEY

#: How the two endpoints of an edge relate to the pictures they live in. Carried on every edge
#: because it is the distinction an agent's movement actually turns on.
SPAN_WITHIN = "within_image"
SPAN_BETWEEN = "between_images"

#: Where an edge came from. A reader deciding how much to trust a line on a graph needs to know
#: whether it is a curator-committed relation, a filed proposal, or an atlas crossing whose mark
#: nobody has committed — and those are three different amounts of settled.
SOURCE_LEDGER = "ledger"          # committed to a post's visual_marks
SOURCE_PROPOSAL = "proposal"      # filed in the curator's queue, awaiting a human
SOURCE_ATLAS = "atlas"            # a movement edge on an Atlas document
#: WAVE4.5 — the rebuildable store. The many, and never durable.
SOURCE_DERIVED = "derived"

#: Ledger vocabulary, mirrored from `curator` so a reader of this module's output does not have to
#: learn a second set of words for the same two states.
LEDGER_PROPOSED = "proposed"
LEDGER_COMMITTED = "committed"

#: Default and ceiling for the walk. Bounded on purpose: the card's own reasoning is that a
#: full-graph hairball is not legible and the world *reachable from a locus* is. The ceiling exists
#: so a caller cannot ask for the hairball by accident.
DEFAULT_DEPTH = 2
MAX_DEPTH = 4


def node_id_for(post_id: str, region_id: str) -> str:
    """`vm_<post>:<region>` — the same construction `movement_kernel._node_id` and
    `observation.node_id_for` use. Two names for one place would split every traversal that
    touched it, and nothing downstream would report the split."""
    return f"vm_{post_id}:{region_id}"


def parse_node_id(node_id: str) -> Optional[Tuple[str, str]]:
    """The inverse, verified by RECONSTRUCTION rather than by trusting the split — a node id this
    cannot round-trip names a place this walk must not claim to have reached."""
    text = str(node_id or "")
    if not text.startswith("vm_") or ":" not in text:
        return None
    post_id, _, region_id = text[len("vm_"):].partition(":")
    if not post_id or not region_id or node_id_for(post_id, region_id) != text:
        return None
    return post_id, region_id


# ── the three sources ───────────────────────────────────────────────────────

def _edge(*, edge_id: str, source: str, axis: str, relation: str,
          a_node: str, b_node: str, directed: bool, front_node: str = "",
          epistemic: Optional[str], ledger_status: str, basis: str,
          evidence: Mapping[str, Any], detail: str) -> Dict[str, Any]:
    """One relation, as the constellation holds it.

    `span` is DERIVED from the endpoints rather than passed in: a caller that could declare an
    occlusion "between images" would be able to draw a crossing the agent cannot make.
    """
    a, b = parse_node_id(a_node), parse_node_id(b_node)
    same_image = bool(a and b and a[0] == b[0])
    return {
        "edge_id": edge_id,
        "source": source,
        "axis": axis,
        "relation": relation,
        "a_node": a_node,
        "b_node": b_node,
        "span": SPAN_WITHIN if same_image else SPAN_BETWEEN,
        # `in_front_of` has a near end and a far end; `nested_within` and `rhymes_with` as stored
        # here do not orient the traversal. A reader drawing an arrow needs to know which.
        "directed": bool(directed),
        "front_node": front_node,
        # BOTH STATUSES, as everywhere else in this system: `epistemic` is how the producer knows,
        # `ledger_status` is whether a human agreed. Never combined.
        "epistemic": epistemic,
        "ledger_status": ledger_status,
        "basis": basis,
        "evidence": dict(evidence),
        "detail": detail,
    }


def edges_from_proposals(proposals: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The curator's queue → edges. Occlusions today; the shape is kind-agnostic.

    A proposal is a *grounded* relation — the organ measured it — that no human has accepted. So it
    is a real edge with `ledger_status: proposed`, not a candidate: the thing the honesty floor
    excludes is a pair the kernel REFUSED, and a refusal is never filed.
    """
    out: List[Dict[str, Any]] = []
    for proposal in proposals:
        subject = dict(proposal.get("subject") or {})
        evidence = dict(proposal.get("evidence") or {})
        post_id = str(proposal.get("post_id") or "")
        front, back = str(subject.get("front_region_id") or ""), str(subject.get("back_region_id") or "")
        if not (post_id and front and back):
            continue
        mark = dict(proposal.get("mark") or {})
        a_node, b_node = node_id_for(post_id, front), node_id_for(post_id, back)
        out.append(_edge(
            edge_id=str(proposal.get("proposal_id") or ""),
            source=SOURCE_PROPOSAL,
            axis=str(mark.get("axis") or evidence.get("axis") or "axis_occlusion"),
            relation=str(mark.get("role") or "in_front_of"),
            a_node=a_node, b_node=b_node, directed=True, front_node=a_node,
            epistemic=str(mark.get(STATUS_KEY) or "") or None,
            ledger_status=(LEDGER_COMMITTED if proposal.get("committed_at") else LEDGER_PROPOSED),
            basis=str(evidence.get("basis") or ""),
            evidence={k: evidence.get(k) for k in
                      ("ordering_separation", "separation_floor", "ordering_ceiling",
                       "depth_grid", "contradicts") if k in evidence},
            detail=str(subject.get("claim") or "")))
    return out


def edges_from_atlas(atlas_docs: Sequence[Mapping[str, Any]],
                     posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Atlas movement edges → edges. The cross-image crossings the kernel grounded.

    Their status is DERIVED from the cited mark, exactly as `hydrate_movement_edge` does: an edge
    stores none and is not entitled to one. A movement whose mark nobody committed reads
    `proposed`, and — the honest consequence — its `epistemic` is `None`, because the mark is not
    in any post and there is nothing to read it off. `None` here is "this edge cannot tell you",
    which a viewer must render as such rather than filling in.
    """
    out: List[Dict[str, Any]] = []
    for doc in atlas_docs:
        for edge in doc.get("edges") or []:
            if not isinstance(edge, Mapping):
                continue
            if str(edge.get("kind") or "") != "movement":
                continue
            mark = _find_mark(posts, edge.get("spans") or [], str(edge.get("mark_id") or ""))
            out.append(_edge(
                edge_id=str(edge.get("edge_id") or ""),
                source=SOURCE_ATLAS,
                axis=str(edge.get("axis_ref") or ""),
                relation="nested_within",
                a_node=str(edge.get("source_node") or ""),
                b_node=str(edge.get("target_node") or ""),
                directed=False,
                epistemic=(str(mark.get(STATUS_KEY) or "") or None) if mark else None,
                ledger_status=(LEDGER_COMMITTED if mark else LEDGER_PROPOSED),
                basis=str(((mark or {}).get("measurement") or {}).get("basis") or ""),
                evidence={"systematicity": edge.get("systematicity"),
                          "weight": edge.get("weight"),
                          "mark_id": edge.get("mark_id"),
                          "spans": list(edge.get("spans") or [])},
                detail=("the movement kernel grounded this crossing"
                        if mark else
                        "the movement kernel grounded this crossing and the mark it cites is not "
                        "in any post's ledger — so this edge cannot say what kind of knowing it is")))
    return out


def edges_from_ledger(posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Committed relation marks on posts → edges. The only fully-settled relations there are.

    Empty on this corpus today, and that absence is the finding rather than a gap in this function:
    nothing has been committed yet. The path exists so that the first curator commit appears here
    without another lane.
    """
    out: List[Dict[str, Any]] = []
    for post_id, post in (posts or {}).items():
        for mark in post.get("visual_marks") or []:
            if not isinstance(mark, Mapping):
                continue
            if str(mark.get("type") or "") != "relation_mark":
                continue
            measurement = dict(mark.get("measurement") or {})
            a_id = str(measurement.get("front_region_id") or measurement.get("inner_region_id") or "")
            b_id = str(measurement.get("back_region_id") or measurement.get("outer_region_id") or "")
            if not (a_id and b_id):
                continue
            a_node, b_node = node_id_for(post_id, a_id), node_id_for(post_id, b_id)
            directed = "front_region_id" in measurement
            out.append(_edge(
                edge_id=str(mark.get("id") or ""),
                source=SOURCE_LEDGER,
                axis=str(measurement.get("axis") or ""),
                relation=str(mark.get("role") or ""),
                a_node=a_node, b_node=b_node, directed=directed,
                front_node=a_node if directed else "",
                epistemic=str(mark.get(STATUS_KEY) or "") or None,
                ledger_status=LEDGER_COMMITTED,
                basis=str(measurement.get("basis") or ""),
                evidence={"mark_id": mark.get("id"),
                          "committed_by": (mark.get("provenance") or {}).get("committed_by")},
                detail=str(mark.get("label") or "")))
    return out


def _find_mark(posts: Mapping[str, Mapping[str, Any]], spans: Sequence[str],
               mark_id: str) -> Optional[Dict[str, Any]]:
    for post_id in spans:
        for mark in (posts.get(str(post_id)) or {}).get("visual_marks") or []:
            if isinstance(mark, Mapping) and str(mark.get("id")) == str(mark_id):
                return dict(mark)
    return None


# ── the walk ────────────────────────────────────────────────────────────────

def reach(seed: str, edges: Sequence[Mapping[str, Any]], *,
          depth: int = DEFAULT_DEPTH) -> Dict[str, Any]:
    """Breadth-first from one locus, `depth` hops, over the edges given. Nothing is fetched here.

    Undirected traversal even over directed edges, and that is deliberate: `in_front_of` has a near
    end and a far end, but an agent standing at either end can see the relation. Direction is a
    fact about the claim, not about who can reach it, and it is carried on the edge for a renderer
    to draw rather than used to prune the walk.

    Returns the nodes with the hop at which each was first reached — so a viewer can show the seed,
    its immediate neighbourhood, and the ring beyond it as different things, and so the bound is
    visible in the data rather than only in a parameter.
    """
    bound = max(0, min(int(depth), MAX_DEPTH))
    by_node: Dict[str, List[Mapping[str, Any]]] = {}
    for edge in edges:
        by_node.setdefault(str(edge["a_node"]), []).append(edge)
        by_node.setdefault(str(edge["b_node"]), []).append(edge)

    hops: Dict[str, int] = {str(seed): 0}
    frontier = [str(seed)]
    kept: Dict[str, Mapping[str, Any]] = {}

    for hop in range(bound):
        nxt: List[str] = []
        for node in frontier:
            for edge in by_node.get(node, []):
                other = str(edge["b_node"]) if str(edge["a_node"]) == node else str(edge["a_node"])
                kept.setdefault(str(edge["edge_id"]), edge)
                if other not in hops:
                    hops[other] = hop + 1
                    nxt.append(other)
        frontier = nxt
        if not frontier:
            break

    # Edges BETWEEN nodes already reached, that the walk did not travel to get there — the triangles
    # that close. Without these a neighbourhood renders as a tree and reads as more sparse than it
    # is, which is a different lie from the one this module is mostly guarding against but a lie.
    for edge in edges:
        if str(edge["a_node"]) in hops and str(edge["b_node"]) in hops:
            kept.setdefault(str(edge["edge_id"]), edge)

    nodes = []
    for node_id, hop in sorted(hops.items(), key=lambda kv: (kv[1], kv[0])):
        parsed = parse_node_id(node_id)
        nodes.append({
            "node_id": node_id,
            "post_id": parsed[0] if parsed else "",
            "region_id": parsed[1] if parsed else "",
            "hop": hop,
            "is_seed": node_id == str(seed),
        })

    reached = list(kept.values())
    return {
        "seed": str(seed),
        "depth": bound,
        "nodes": nodes,
        "edges": reached,
        "images": sorted({n["post_id"] for n in nodes} - {""}),
        "tally": tally(reached, nodes),
        # THE BOUND, on the record. A neighbourhood that stops at depth N is a claim about how far
        # it walked, and a viewer showing three nodes without it would read as a claim about the
        # world.
        "bound_detail": (
            f"walked {bound} hop(s) from {seed}. Nodes further than that are not absent from the "
            f"world, they are absent from this walk — and an edge appears here only if it was "
            f"persisted, which in this system means committed to a post, filed in the curator's "
            f"queue, or stored on an Atlas. A candidate the kernel refused was never written down "
            f"and cannot appear."),
    }


def tally(edges: Sequence[Mapping[str, Any]], nodes: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The counts a reader needs to know what they are looking at — BY CLASS, never summed.

    `within_image` and `between_images` are the distinction the whole view is for; `proposed` and
    `committed` are how settled it is; and the source says which of the three durable places each
    edge came from. One "edges: 14" would hide every one of them.
    """
    def count(key):
        out: Dict[str, int] = {}
        for edge in edges:
            out[str(edge.get(key) or "")] = out.get(str(edge.get(key) or ""), 0) + 1
        return dict(sorted(out.items()))

    return {
        "nodes": len(nodes),
        "images": len({n["post_id"] for n in nodes} - {""}),
        "edges": len(edges),
        "by_span": count("span"),
        "by_ledger_status": count("ledger_status"),
        "by_axis": count("axis"),
        "by_source": count("source"),
    }


# ── loading ─────────────────────────────────────────────────────────────────

async def load_edges(*, posts_collection=None, atlas=None, proposals=None,
                     derived=None, include_derived: bool = False) -> Dict[str, Any]:
    """The DURABLE relations in the corpus, as constellation edges. Reads, never writes.

    ## The three named sources became one call (WAVE4.5)

    This function used to read the ledger, the curator's queue and the Atlas itself — three sources
    a viewer had to know about, and a fourth it did not: the derived cache the scene view had built
    and nothing else could see. That is why this lane counted **fourteen** edges while **2,755**
    relations had been measured.

    `derived_relations.load` is now the one home. It knows all four origins, re-derives `epistemic`
    from the basis on every read, and labels each row with where it came from — so a reader can
    still tell a committed relation from a rebuildable one, which is the distinction that made
    three sources worth keeping apart in the first place.

    ## `include_derived` DEFAULTS TO FALSE, and that is this view's own ruling

    Delegating to the store made the derived world reachable from here, and switching it on by
    default would take this graph from fourteen edges to 2,769 — silently overturning the finding
    this view exists to show: **a constellation is a world an agent can WALK**, and a relation
    nobody has filed is not somewhere it can go. Padding the graph with measured-but-unfiled
    candidates would draw exactly the world #178 refused to draw.

    So the delegation is about having ONE store with four origins, not about this view showing all
    four. The derived count is reported — by `/api/v1/relations/status`, whose job is the census —
    and the caller who wants it here can ask.
    """
    from backend.services import derived_relations as store

    loaded = await store.load(posts_collection=posts_collection, atlas=atlas,
                              proposals=proposals, derived=derived,
                              include_derived=include_derived)
    edges = [_edge_from(row) for row in loaded["relations"]]
    return {
        "edges": edges,
        "posts": loaded["posts"],
        "census": store.census(loaded["relations"]),
        "cache": loaded["cache"],
        "sources": {
            "ledger_relation_marks": sum(1 for e in edges if e["source"] == SOURCE_LEDGER),
            "curator_proposals": sum(1 for e in edges if e["source"] == SOURCE_PROPOSAL),
            "atlas_movement_edges": sum(1 for e in edges if e["source"] == SOURCE_ATLAS),
            "derived_relations": sum(1 for e in edges if e["source"] == SOURCE_DERIVED),
        },
    }


def _edge_from(row: Mapping[str, Any]) -> Dict[str, Any]:
    """One store relation → the edge shape this view has always drawn.

    A thin adapter, deliberately: the store owns what a relation IS, and this owns what a
    constellation edge needs on top of it — `span`, `directed`, and the ids the walk traverses.
    `span` is still derived from the endpoints here, never carried, so a caller cannot declare an
    occlusion a crossing.
    """
    a_node, b_node = str(row.get("source_node") or ""), str(row.get("target_node") or "")
    a, b = parse_node_id(a_node), parse_node_id(b_node)
    same_image = bool(a and b and a[0] == b[0])
    # `in_front_of` has a near end and a far end; a nesting or a rhyme as stored does not orient a
    # traversal. A renderer drawing an arrow needs to know which, and guessing would invent one.
    directed = str(row.get("relation") or "") == "in_front_of"
    return {
        "edge_id": str(row.get("ref") or f"{row.get('origin')}:{a_node}->{b_node}"),
        "source": str(row.get("origin") or ""),
        "axis": str(row.get("axis") or ""),
        "relation": str(row.get("relation") or ""),
        "a_node": a_node,
        "b_node": b_node,
        "span": SPAN_WITHIN if same_image else SPAN_BETWEEN,
        "directed": directed,
        "front_node": a_node if directed else "",
        "epistemic": row.get("epistemic"),
        "ledger_status": str(row.get("ledger_status") or LEDGER_PROPOSED),
        "basis": str(row.get("basis") or ""),
        "evidence": {**dict(row.get("numbers") or {}),
                     **({"contradicts": row["supersedes"]} if row.get("supersedes") else {}),
                     "queued_for_curation": bool(row.get("queued"))},
        "detail": str(row.get("detail") or ""),
    }


def region_label(posts: Mapping[str, Mapping[str, Any]], node: Mapping[str, Any]) -> str:
    """A region's own label, for the transcript only — `cseg_*` regions carry none by design, so
    most of these come back as their ids. Never a gate: nothing in this module reads a label."""
    for region in (posts.get(str(node.get("post_id"))) or {}).get("region_annotations") or []:
        if isinstance(region, Mapping) and str(region.get("id")) == str(node.get("region_id")):
            return str(region.get("label") or "")
    return ""
