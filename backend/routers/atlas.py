"""
ATLAS C1 — the Atlas routes: create, read, hydrate, arrange.

Five endpoints over one thin document (`atlas_service`). The canvas, drivable by a person with a
set of images.

    POST /api/v1/atlas                    post_ids or a run_id  → the new Atlas document
    GET  /api/v1/atlas                    the recent Atlases (so a curator can find one again)
    GET  /api/v1/atlas/{id}               the STORED document — arrangement only
    GET  /api/v1/atlas/{id}/view          the same, hydrated from the ledger for rendering
    POST /api/v1/atlas/{id}/arrangement   node positions; refusals travel with the save

WHY `GET {id}` AND `GET {id}/view` ARE TWO ENDPOINTS. They could have been one with a query
parameter, and separating them is the point: the first returns exactly what is stored, so what the
Atlas document does and does not contain is inspectable rather than asserted in a comment. Anyone
can `curl` it and see there is no percept data in there. The second assembles the drawable view
from the ledger at read time, which is where percept truth is allowed to appear.

READ-ONLY WITH RESPECT TO EVIDENCE. Nothing here writes to a post, creates a percept, accepts a
suggestion, or touches the ledger. The only thing these routes write is where a picture sits on a
canvas. C2 adds percept creation — through the EXISTING quarantine and Accept path, not through
here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from bson.errors import InvalidId
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.database import post_collection
from backend.services import atlas_service as A

router = APIRouter()

# How many images one Atlas may span. Not a storage limit — a canvas with two hundred nodes on it
# is a folder, and the surface would stop being a place anyone could think.
MAX_IMAGES = 60


class NodePatch(BaseModel):
    node_id: str
    x: Optional[float] = None
    y: Optional[float] = None
    w: Optional[float] = None
    h: Optional[float] = None


class CreateAtlasRequest(BaseModel):
    title: str = ""
    post_ids: List[str] = Field(default_factory=list)
    run_id: Optional[str] = None


class ArrangementRequest(BaseModel):
    nodes: List[NodePatch] = Field(default_factory=list)


async def _posts_for(post_ids: List[str], collection=None) -> Dict[str, Dict[str, Any]]:
    """post id → post document, for the ids this Atlas holds.

    An id that resolves to nothing is simply absent from the map; `hydrate_node` turns that into a
    node that says it could not be read. Same discipline as the run route's corpus resolution —
    the image stays on the canvas and stays honest about why it is empty.
    """
    posts = collection if collection is not None else post_collection
    out: Dict[str, Dict[str, Any]] = {}
    for raw in post_ids:
        doc = None
        try:
            doc = await posts.find_one({"_id": ObjectId(raw)})
        except (InvalidId, TypeError):
            doc = None
        if doc is None:
            doc = await posts.find_one({"_id": raw})
        if doc:
            out[str(raw)] = doc
    return out


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_atlas(body: CreateAtlasRequest):
    """Open a canvas over a corpus.

    The corpus is named either by an explicit list of post ids or by a run that already spans them.
    There is no third option and no default: an Atlas over "whatever images exist" would be a
    gallery, and the corpus's ORDER is the thing that makes it an argument.
    """
    post_ids = list(dict.fromkeys(p for p in body.post_ids if p))
    corpus_ref: Any = {"kind": A.CORPUS_POSTS, "post_ids": post_ids}

    if body.run_id:
        from backend.services import run_store
        run_doc = await run_store.get_run(str(body.run_id))
        if run_doc is None:
            raise HTTPException(status_code=404, detail=f"no run '{body.run_id}'")
        from_run = A.post_ids_from_run(run_doc)
        if not from_run:
            raise HTTPException(
                status_code=409,
                detail=(f"run '{body.run_id}' has not resolved a corpus yet — "
                        "it names no images this Atlas could open"))
        post_ids = from_run
        corpus_ref = {"kind": A.CORPUS_RUN, "run_id": str(body.run_id), "post_ids": post_ids}

    if not post_ids:
        raise HTTPException(status_code=400,
                            detail="an Atlas needs a corpus: pass post_ids or a run_id")
    if len(post_ids) > MAX_IMAGES:
        raise HTTPException(status_code=400,
                            detail=f"an Atlas spans at most {MAX_IMAGES} images "
                                   f"(asked for {len(post_ids)})")

    doc = await A.create_atlas(corpus_ref=corpus_ref, post_ids=post_ids, title=body.title)
    return A._out(doc)


@router.get("")
@router.get("/")
async def list_atlases(limit: int = 20):
    return {"atlases": [A._out(d) for d in await A.list_atlases(limit=max(1, min(limit, 100)))]}


@router.get("/{atlas_id}")
async def get_atlas(atlas_id: str):
    """The STORED document, verbatim. Arrangement and references — no percept data."""
    doc = await A.get_atlas(atlas_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return A._out(doc)


@router.get("/{atlas_id}/view")
async def get_atlas_view(atlas_id: str):
    """The document hydrated from the ledger — what the canvas actually draws.

    Assembled fresh on every request. A percept accepted in the Differential a second ago is in the
    next response, because this reads the post document rather than anything the Atlas cached.
    """
    doc = await A.get_atlas(atlas_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    ids = [str(n.get("post_id")) for n in doc.get("nodes") or []]
    return A.atlas_view(doc, await _posts_for(ids))


@router.post("/{atlas_id}/arrangement")
async def save_arrangement(atlas_id: str, body: ArrangementRequest):
    """Move nodes. Position only — a save cannot repoint a node at a different image.

    Returns the refusals alongside the saved nodes. A stale node id does not fail the request: the
    real nodes move, and the client is told which one it asked about that no longer exists.
    """
    result = await A.save_arrangement(
        atlas_id, [n.model_dump(exclude_none=True) for n in body.nodes])
    if result is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return {"atlas": A._out(result["doc"]), "refused": result["refused"]}
