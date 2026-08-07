"""
WAVE4 — the cognition routes: watch an agent walk.

    GET /api/v1/cognition/temperaments        the characters, and what each prefers
    GET /api/v1/cognition/walk                one agent's walk, as a legible stream
    GET /api/v1/cognition/compare             two characters from one locus, side by side

READ-ONLY, ALL THREE. Nothing here writes a post, a mark, an axis or an edge. The walk is
recomputed from the stored graph on every request rather than persisted, because a stored walk is
a second record of where an agent went that can disagree with the trajectory — and the whole point
of the surface is that what you are watching is what actually happened.

## The serializer trap, and why the response models look the way they do

Same one the curator lane hit. A response model with a defaulted status field is how `proposed`
becomes `measured` without anybody writing the word: FastAPI builds the response from the model, so
a field the handler never set is filled from its default and rendered as though it were data.

So every field that carries a status here is **required and un-defaulted**, and the two that can
honestly be absent are `Optional` with no default value to fall back on:

    epistemic       Optional[str]   what the organ measured. `None` is a real answer.
    ledger_status   Optional[str]   `proposed` until a curator commits.

And the refusal rows are not modelled with an optional `reason` — a refusal without its reason is
the blank this whole lane exists to prevent, so `reason`, `about` and `gloss` are all required.

## Statuses

    404  no such post, or no such region in it
    400  a temperament nobody declared — raised rather than defaulted, per `temperament`
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services import nestedness_organ
from backend.services.agents import cognition
from backend.services.agents import movement as mv
from backend.services.agents import situated_agent as sa
from backend.services.agents import temperament as tp

router = APIRouter()


class RefusalRow(BaseModel):
    """A crossing the agent could see and could not take. Every field required — a refusal whose
    reason is optional is a blank with extra steps."""
    to_node: str
    reason: str
    about: str
    gloss: str
    axis_ref: Optional[str]
    relation: Optional[str]
    basis: Optional[str]
    detail: str


class CharacterView(BaseModel):
    name: str
    prefers: List[str]
    detail: str


class WalkView(BaseModel):
    agent_id: str
    temperament: Optional[str]
    character: Optional[CharacterView]
    organ_set: List[str]
    stations: List[Dict[str, Any]]
    steps: List[Dict[str, Any]]
    proposals: List[Dict[str, Any]]
    first_signature: List[List[str]]
    tally: Dict[str, Any]


class CompareView(BaseModel):
    walks: List[WalkView]
    comparison: Dict[str, Any]


async def _world(post_id: str, region_id: str, atlas_id: str):
    """The post, the graph and the marks a walk needs. Reads; writes nothing."""
    from bson import ObjectId

    from backend.database import atlas_collection, post_collection

    query = {"_id": ObjectId(post_id)} if ObjectId.is_valid(post_id) else {"_id": post_id}
    post = await post_collection.find_one(query)
    if not post:
        raise HTTPException(status_code=404, detail=f"no post {post_id}")
    if region_id and not any(str(r.get("id")) == region_id
                             for r in (post.get("region_annotations") or [])):
        raise HTTPException(
            status_code=404,
            detail=(f"no region {region_id!r} in post {post_id} — an agent cannot stand where "
                    f"there is nothing to stand on"))

    graph = await atlas_collection.find_one({"_id": atlas_id}) if atlas_id else None
    if graph is None:
        graph = await atlas_collection.find_one({"edges.0": {"$exists": True}}) or {"edges": []}

    # Every post the graph's edges can reach, so a cross-image step has somewhere to arrive.
    post_ids = {str(post["_id"])}
    for edge in graph.get("edges") or []:
        for span in edge.get("spans") or []:
            post_ids.add(str(span))
    posts: Dict[str, Any] = {}
    for pid in post_ids:
        q = {"_id": ObjectId(pid)} if ObjectId.is_valid(pid) else {"_id": pid}
        doc = await post_collection.find_one(q)
        if doc:
            posts[str(doc["_id"])] = doc
    return post, graph, posts


def _marks_for(posts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The organ marks the graph's edges cite, recomputed from geometry.

    PROPOSED, never committed — the same posture every agent script keeps. A walk needs marks to
    judge an edge's footing, and minting them here rather than reading a ledger is what keeps this
    route from depending on a curator having accepted anything.
    """
    marks: List[Dict[str, Any]] = []
    for pid, post in posts.items():
        regions = post.get("region_annotations") or []
        for measurement in nestedness_organ.find_nested_pairs(regions):
            marks.append(nestedness_organ.grounding_mark(measurement, post_id=pid))
    return marks


async def _walk_one(post_id: str, region_id: str, atlas_id: str, temperament: str,
                    steps: int, organ: str) -> Dict[str, Any]:
    if temperament:
        # `temperament.resolve` RAISES on an undeclared name rather than returning None — the
        # module refuses to default, which is exactly right and means this must catch rather than
        # test. Turned into a 400 so the surface gets the refusal instead of a 500.
        try:
            tp.resolve(temperament)
        except tp.UnknownTemperament as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    post, graph, posts = await _world(post_id, region_id, atlas_id)
    region = region_id or str((post.get("region_annotations") or [{}])[0].get("id") or "")
    agent = sa.inhabit(agent_id=f"agent_{temperament or 'plain'}",
                       post_id=str(post["_id"]), region_id=region,
                       organ_set=(organ or nestedness_organ.ORGAN,),
                       temperament=temperament or tp.NO_TEMPERAMENT)
    return cognition.walk(agent, graph, posts, marks=_marks_for(posts), steps=steps)


@router.get("/temperaments", response_model=List[CharacterView])
async def read_temperaments():
    """The declared characters. A surface that hardcoded these would be a second place they live."""
    return [t.as_dict() for t in tp.TEMPERAMENTS.values()]


@router.get("/walk", response_model=WalkView)
async def read_walk(post_id: str = Query(...), region_id: str = "", atlas_id: str = "",
                    temperament: str = "", organ: str = "",
                    steps: int = Query(default=3, ge=0, le=12)):
    """One agent's walk from one locus, as the stream the cognition page renders."""
    return await _walk_one(post_id, region_id, atlas_id, temperament, steps, organ)


@router.get("/compare", response_model=CompareView)
async def read_comparison(post_id: str = Query(...), region_id: str = "", atlas_id: str = "",
                          left: str = "depth_seeker", right: str = "analogy_seeker",
                          organ: str = "", steps: int = Query(default=3, ge=0, le=12)):
    """Two characters from ONE locus — the bright line, as something you can look at.

    Returns both walks whole rather than a diff, because the claim is about two things at once:
    the signatures must be identical and the routes must not be. A diff would show the second and
    hide the first, and the first is the one that is easy to lose.
    """
    walks = [await _walk_one(post_id, region_id, atlas_id, name, steps, organ)
             for name in (left, right)]
    return {"walks": walks, "comparison": cognition.compare(walks)}
