"""
ATLAS C1 — the Atlas routes: create, read, hydrate, arrange.

Five endpoints over one thin document (`atlas_service`). The canvas, drivable by a person with a
set of images.

    POST /api/v1/atlas                    post_ids or a run_id  → the new Atlas document
    GET  /api/v1/atlas                    the recent Atlases (so a curator can find one again)
    GET  /api/v1/atlas/{id}               the STORED document — arrangement only
    GET  /api/v1/atlas/{id}/view          the same, hydrated from the ledger for rendering
    POST /api/v1/atlas/{id}/arrangement   node positions; refusals travel with the save

ATLAS C4 adds plan mode — three more, over M2's rhetorical planner:

    POST   /api/v1/atlas/{id}/plan          a thesis → the proposed ArgumentPlan, NOT persisted
    POST   /api/v1/atlas/{id}/plan/accept   the writer's edited plan → RE-BOUND, then persisted
    DELETE /api/v1/atlas/{id}/plan          drop the accepted plan

WHY PROPOSING DOES NOT PERSIST. A proposal is a question the writer has not answered yet, and an
Atlas that stored every thesis anyone tried would accumulate arguments nobody chose. Accepting is
the gesture that means something, and it is the one that writes.

WHY ACCEPTING RE-BINDS RATHER THAN RECORDING. The accept payload is a browser's, so every status
in it is discarded and `plan_argument` judges the edited claims again against the corpus as it is
at accept time. It is the same asymmetry the Director keeps with the model, applied to the client:
propose freely, and let the gate decide what is carried.

WHY `GET {id}` AND `GET {id}/view` ARE TWO ENDPOINTS. They could have been one with a query
parameter, and separating them is the point: the first returns exactly what is stored, so what the
Atlas document does and does not contain is inspectable rather than asserted in a comment. Anyone
can `curl` it and see there is no percept data in there. The second assembles the drawable view
from the ledger at read time, which is where percept truth is allowed to appear.

ATLAS C3 adds relation edges — two more, over M1's `compare_views`:

    POST   /api/v1/atlas/{id}/relations            a drawn line → a committed relation, or a refusal
    DELETE /api/v1/atlas/{id}/relations/{edge_id}  take the edge off the canvas; the ledger keeps the mark

READ-ONLY WITH RESPECT TO EVIDENCE, WITH EXACTLY ONE EXCEPTION — and it is written here rather than
discovered later. Through C2 this was absolute: nothing in this file wrote to a post, created a
percept or accepted a suggestion. `POST /relations` is the exception. Drawing a line from one image
to another IS the curator's decision, so that route appends the one relation mark `compare_views`
produced to the two posts the writer named. It can do nothing else: it cannot edit a mark, cannot
delete one, cannot touch a region, and every other route in this file remains as read-only as it
was. A refusal writes nothing at all.

Everything else these routes write is still only where a picture sits on a canvas and which
relations have been drawn between them.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Mapping, Optional

from bson.errors import InvalidId
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.database import post_collection
from backend.services import atlas_plan as P
from backend.services import atlas_relation as R
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
    posts = await _posts_for(ids)
    view = A.atlas_view(doc, posts)
    # C3: the edges carry ids; what each relation SAYS is read from the ledger here, on every
    # request, exactly as the nodes' overlays are. Hydrated in the route rather than in
    # `atlas_service` because the relation hydrator lives beside `compare_views`' vocabulary and
    # `atlas_service` must stay importable with none of the Director on the path.
    view["edges"] = R.hydrate_edges(doc, posts)
    return view


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


# ── C4: plan mode ────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    thesis: str = ""
    why: str = ""            # what this sequence of images is FOR, in the writer's words


class AcceptPlanRequest(BaseModel):
    thesis: str = ""
    claims: List[Dict[str, Any]] = Field(default_factory=list)


async def _atlas_or_404(atlas_id: str) -> Dict[str, Any]:
    doc = await A.get_atlas(atlas_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return doc


async def _corpus_memory(doc: Mapping[str, Any], *, why: str = ""):
    """The Atlas's images → M1's corpus, hydrated from the ledger.

    THE CORPUS IS THE NODES, IN NODE ORDER. Not `corpus_ref.post_ids` — those record how the Atlas
    was opened, while the nodes are what the writer is looking at now, and order is evidence. An
    image whose post cannot be read stays in the corpus and `hydrate_corpus` records it as
    unreadable, so a claim planned on it binds with a caveat rather than vanishing.
    """
    from backend.services.director.corpus import build_corpus, hydrate_corpus

    post_ids = P.node_post_ids(doc)
    posts = await _posts_for(post_ids)
    corpus = build_corpus(
        corpus_id=str(doc.get("_id") or ""),
        title=str(doc.get("title") or ""),
        why=why or str(doc.get("title") or ""),
        images=[{
            "post_id": pid,
            "photo_url": str((posts.get(pid) or {}).get("photo_url") or ""),
            "title": str((posts.get(pid) or {}).get("instagram_handle")
                         or (posts.get(pid) or {}).get("domain") or ""),
        } for pid in post_ids])
    return corpus, hydrate_corpus(corpus, posts)


@router.post("/{atlas_id}/plan")
async def propose_plan(atlas_id: str, body: PlanRequest):
    """A thesis → the argument this corpus could carry, as M2 judges it. NOT persisted.

    The model gets to propose a decomposition; it does not get to decide what is carried. Every
    percept goes through the unmodified `resolve_corpus()` gate, and a claim whose evidence cannot
    be produced comes back refused with the gate's own reason — which is the answer the writer
    most needs and the one a planner left to itself would never give.

    The Groq call is synchronous, so it runs off the event loop in a worker thread. It needs no
    GPU and drives no producers, so it deliberately does NOT queue behind the orchestration worker
    that runs; planning a thesis should not wait on somebody else's segmentation.
    """
    thesis = (body.thesis or "").strip()
    if not thesis:
        raise HTTPException(status_code=422, detail="a thesis is required to plan an argument")

    doc = await _atlas_or_404(atlas_id)
    corpus, memory = await _corpus_memory(doc, why=body.why)
    if not corpus.images:
        raise HTTPException(status_code=409,
                            detail="this Atlas spans no images; there is nothing to argue over")

    from backend.services.director.argument_planner import RhetoricalDirector
    director = RhetoricalDirector()
    available = bool(getattr(director.planner, "is_available", lambda: True)())
    argument = await asyncio.to_thread(director.plan, thesis, memory)
    return P.plan_view(argument, doc, planner_available=available)


@router.post("/{atlas_id}/plan/accept")
async def accept_plan(atlas_id: str, body: AcceptPlanRequest):
    """The writer's edited plan, RE-BOUND against the corpus, then stored as C5's seed.

    Nothing the payload says about a claim's status survives this route. The claims and their
    percepts are rebuilt, params are clamped to each actuator's declared vocabulary, and
    `plan_argument` judges the lot again — so an accepted `supported` was earned against the
    ledger a second time, and a writer who removed the last challenge percept gets the
    argument-level refusal rather than a document that looks finished.
    """
    thesis = (body.thesis or "").strip()
    if not thesis:
        raise HTTPException(status_code=422, detail="a thesis is required to accept a plan")

    doc = await _atlas_or_404(atlas_id)
    claims, notes, proposed = P.claims_from_payload(body.claims)
    if not claims:
        # An empty accept is a clear wearing the wrong verb. Refused rather than silently
        # honoured, because "I accepted this plan" and "I threw it away" must not be the same call.
        raise HTTPException(
            status_code=422,
            detail="an accepted plan needs at least one claim; DELETE the plan to clear it")

    _, memory = await _corpus_memory(doc)

    from backend.services.director.argument import plan_argument
    argument = plan_argument(thesis, claims, memory, planner=P.PLANNER_ACCEPTED, notes=notes)
    stored = P.stored_plan(argument, doc, proposed_text=proposed, now=A.utc_now())
    P.assert_plan_authors_no_evidence(stored)

    updated = await A.save_plan(atlas_id, stored)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return {"atlas": A._out(updated), "plan": stored}


@router.delete("/{atlas_id}/plan")
async def clear_plan(atlas_id: str):
    """Drop the accepted plan. The Atlas keeps its images and its arrangement."""
    updated = await A.save_plan(atlas_id, None)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return {"atlas": A._out(updated), "plan": None}


# ── C3: relation edges ───────────────────────────────────────────────────────

class RelateRequest(BaseModel):
    source_node: str
    target_node: str
    relation_role: str = ""     # the writer's own word for the relation, when they have one
    left_ref: str = ""          # which mark on the source image
    right_ref: str = ""         # which mark on the target image


def _node_post(doc: Mapping[str, Any], node_id: str) -> Optional[str]:
    for node in doc.get("nodes") or []:
        if isinstance(node, Mapping) and str(node.get("node_id")) == str(node_id):
            return str(node.get("post_id"))
    return None


@router.post("/{atlas_id}/relations")
async def draw_relation(atlas_id: str, body: RelateRequest):
    """A drawn line → M1's `compare_views` → a committed relation, or a refusal.

    THE ONE ROUTE IN THIS FILE THAT WRITES TO A POST, and the gesture is the reason: a writer
    dragging one image onto another has made the decision a review step would otherwise ask for.
    C1's header said this router touches no post; C3 is the deliberate exception, and it is narrow
    — it appends the one relation mark the actuator produced to the two posts the writer named,
    and it can do nothing else.

    REFUSAL IS 200, NOT 4xx. "These two images carry no marks to compare" is an answer about the
    evidence, not a complaint about the request. An error status would make the surface render it
    as a malfunction, and the writer would learn nothing about their corpus.
    """
    doc = await _atlas_or_404(atlas_id)

    if body.source_node == body.target_node:
        return {"refused": R.refusal(
            R.REFUSED_SAME_NODE,
            "a relation needs two different images; this line starts and ends on one",
            source_node=body.source_node, target_node=body.target_node)}

    source_post = _node_post(doc, body.source_node)
    target_post = _node_post(doc, body.target_node)
    missing = [n for n, p in ((body.source_node, source_post), (body.target_node, target_post))
               if p is None]
    if missing:
        return {"refused": R.refusal(
            R.REFUSED_UNKNOWN_NODE, f"this Atlas holds no node {', '.join(missing)}",
            source_node=body.source_node, target_node=body.target_node)}

    posts = await _posts_for([source_post, target_post])
    unreadable = [p for p in (source_post, target_post) if p not in posts]
    if unreadable:
        # An unreadable endpoint is not an empty one. Saying which, rather than letting
        # `compare_views` report "no marks", keeps the two facts apart.
        return {"refused": R.refusal(
            R.REFUSED_UNREADABLE, f"could not read post(s): {', '.join(unreadable)}",
            source_node=body.source_node, target_node=body.target_node)}

    outcome = await asyncio.to_thread(
        R.relate,
        [(source_post, posts[source_post]), (target_post, posts[target_post])],
        source_node=body.source_node, target_node=body.target_node,
        relation_role=body.relation_role, left_ref=body.left_ref, right_ref=body.right_ref)

    if outcome.get("refused"):
        # NOTHING IS PERSISTED on this path — not the edge, not a mark, not a placeholder.
        return {"refused": outcome["refused"]}

    mark = R.committed_relation(outcome["relation"], mark_id=R.new_mark_id())
    # The collection is passed EXPLICITLY, never left to the service's default import. This is the
    # only line in the Atlas that writes to a post, and a route that resolved its own collection
    # would be one a test could not redirect — which is how a suite ends up writing to the real
    # ledger while appearing to run against fakes.
    written = await R.commit_relation_to_posts(mark, [source_post, target_post],
                                               collection=post_collection)
    if not written:
        return {"refused": R.refusal(
            R.REFUSED_UNREADABLE, "the relation was named but no post accepted the write",
            source_node=body.source_node, target_node=body.target_node)}

    entry = R.edge_entry(mark_id=mark["id"], source_node=body.source_node,
                         target_node=body.target_node, spans=[source_post, target_post])
    updated = await A.add_edge(atlas_id, entry)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")

    # Re-read so the edge is hydrated from the ledger exactly as a later page load will do it —
    # if the write did not land, this is where the surface finds out rather than at reload.
    return {"atlas": A._out(updated),
            "edge": R.hydrate_edge(entry, await _posts_for([source_post, target_post]))}


@router.delete("/{atlas_id}/relations/{edge_id}")
async def remove_relation(atlas_id: str, edge_id: str):
    """Take the edge off this canvas. The committed relation stays in the ledger.

    The Atlas never owned the percept and does not get to destroy one. Removing the reference is
    reversible — the relation can be drawn again, and it will find the mark still there.
    """
    updated = await A.remove_edge(atlas_id, edge_id)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return {"atlas": A._out(updated), "removed": edge_id}
