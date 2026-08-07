"""
WAVE4 — the constellation routes: the neighbourhood reachable from one locus.

    GET /api/v1/constellation/seeds          loci that have any persisted relation at all
    GET /api/v1/constellation?node=…&depth=N the reachable sub-graph from one of them

READ-ONLY, and structurally so: there is no write path in this router to misuse. It reads the three
places a grounded relation is durable — a post's committed marks, the curator's queue, an Atlas's
movement edges — walks outward, and returns nodes and edges. It grounds nothing, mints nothing and
commits nothing; the commit surface is `/api/v1/curator`.

## `/seeds` exists because the graph is small and mostly empty

Every Wave 3 lane measured relations and *returned* them; only the occlusion queue files anything.
So most loci in this corpus have no persisted relation at all, and a viewer left to guess a seed
would mostly draw a single unconnected dot. `/seeds` answers "where is there anything to see",
which is a fact about what has been filed rather than about what has been measured — and it says so.

## Both statuses, and the span, on every edge

    epistemic      how the producer knows it        `measured` | `interpretive` | null
    ledger_status  whether a human agreed           `proposed` | `committed`
    span           within_image | between_images    occlusion moves THROUGH a picture;
                                                    the rest move BETWEEN pictures

None of the three is defaulted on the response models. A `ledger_status: str = "committed"` would
render every un-hydrated edge as settled and nobody would have written the word — the trap #172
closed on the curator surface, which does not stop this router from reopening it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services import constellation

router = APIRouter()


class NodeView(BaseModel):
    node_id: str
    post_id: str
    region_id: str
    label: str = ""
    hop: int
    is_seed: bool


class EdgeView(BaseModel):
    """One grounded relation. Nothing about its status is defaulted — see the module note."""
    edge_id: str
    source: str
    axis: str
    relation: str
    a_node: str
    b_node: str
    #: `within_image` or `between_images`. Derived from the endpoints in the service, never passed
    #: in — a caller able to declare an occlusion "between images" could draw a crossing no agent
    #: can make.
    span: str
    directed: bool
    front_node: str = ""
    epistemic: Optional[str]
    ledger_status: str
    basis: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)
    detail: str = ""


class ConstellationResponse(BaseModel):
    seed: str
    depth: int
    nodes: List[NodeView]
    edges: List[EdgeView]
    images: List[str]
    tally: Dict[str, Any]
    bound_detail: str
    sources: Dict[str, int]


class SeedView(BaseModel):
    node_id: str
    post_id: str
    region_id: str
    label: str = ""
    degree: int


class SeedsResponse(BaseModel):
    seeds: List[SeedView]
    total: int
    detail: str


@router.get("/seeds", response_model=SeedsResponse)
async def read_seeds(limit: int = Query(default=60, ge=1, le=500)):
    """Every locus with at least one persisted relation, busiest first.

    Sorted by degree, and that ordering is about NAVIGATION rather than importance: a locus with six
    relations is a better place to look at a neighbourhood than one with a single edge, and no claim
    is being made that it matters more.
    """
    loaded = await constellation.load_edges()
    degree: Dict[str, int] = {}
    for edge in loaded["edges"]:
        for key in ("a_node", "b_node"):
            degree[str(edge[key])] = degree.get(str(edge[key]), 0) + 1

    seeds: List[SeedView] = []
    for node_id, count in sorted(degree.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]:
        parsed = constellation.parse_node_id(node_id)
        node = {"post_id": parsed[0] if parsed else "", "region_id": parsed[1] if parsed else ""}
        seeds.append(SeedView(
            node_id=node_id, post_id=node["post_id"], region_id=node["region_id"],
            label=constellation.region_label(loaded["posts"], node), degree=count))

    return SeedsResponse(
        seeds=seeds, total=len(degree),
        detail=(f"{len(degree)} loci carry at least one persisted relation, out of every region in "
                f"the corpus. That is a fact about what producers have FILED, not about what the "
                f"engine has measured: every Wave 3 lane returned its marks into a transcript and "
                f"only the occlusion queue writes any of them down."))


@router.get("", response_model=ConstellationResponse)
async def read_constellation(
    node: str = Query(..., description="the seed locus, as vm_<post_id>:<region_id>"),
    depth: int = Query(default=constellation.DEFAULT_DEPTH, ge=0,
                       le=constellation.MAX_DEPTH),
):
    """The neighbourhood reachable from one locus, bounded and saying so."""
    if constellation.parse_node_id(node) is None:
        raise HTTPException(
            status_code=400,
            detail=(f"{node!r} is not a locus id. They read vm_<post_id>:<region_id> — the same "
                    f"construction the movement kernel and the agents' observations use, so a "
                    f"traversal cannot land somewhere they would call by another name."))

    loaded = await constellation.load_edges()
    walk = constellation.reach(node, loaded["edges"], depth=depth)

    nodes = [NodeView(**{**n, "label": constellation.region_label(loaded["posts"], n)})
             for n in walk["nodes"]]
    return ConstellationResponse(
        seed=walk["seed"], depth=walk["depth"], nodes=nodes,
        edges=[EdgeView(**e) for e in walk["edges"]],
        images=walk["images"], tally=walk["tally"], bound_detail=walk["bound_detail"],
        sources=loaded["sources"])
