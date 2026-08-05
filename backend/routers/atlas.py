"""
ATLAS C1 — the Atlas routes: create, read, hydrate, arrange.

Five endpoints over one thin document (`atlas_service`). The canvas, drivable by a person with a
set of images.

    POST /api/v1/atlas                    post_ids or a run_id  → the new Atlas document
    GET  /api/v1/atlas                    the recent Atlases (so a curator can find one again)
    GET  /api/v1/atlas/{id}               the STORED document — arrangement only
    GET  /api/v1/atlas/{id}/view          the same, hydrated from the ledger for rendering
    POST /api/v1/atlas/{id}/arrangement   node positions; refusals travel with the save
    POST /api/v1/atlas/{id}/notes         T1 — the author's freehand notes; NOT percepts

WHY `GET {id}` AND `GET {id}/view` ARE TWO ENDPOINTS. They could have been one with a query
parameter, and separating them is the point: the first returns exactly what is stored, so what the
Atlas document does and does not contain is inspectable rather than asserted in a comment. Anyone
can `curl` it and see there is no percept data in there. The second assembles the drawable view
from the ledger at read time, which is where percept truth is allowed to appear.

ATLAS C5 adds the writer — four more, over M3's composition and M4's resolver:

    POST   /api/v1/atlas/{id}/draft          the accepted plan → EXECUTED, composed, quarantined
    POST   /api/v1/atlas/{id}/draft/accept   the drafted passages → the manuscript
    DELETE /api/v1/atlas/{id}/draft          dismiss the draft; the plan and the images stay
    GET    /api/v1/atlas/{id}/draft/export   the M4 perceptual-article artifact

WHY DRAFTING RUNS PRODUCERS AND PLANNING DOES NOT. M3 refuses to compose from a plan. A plan says
what WOULD be produced; only a run says what was, and an article written from the former is
indistinguishable from one that was earned. So `POST /draft` executes the accepted plan's percept
chain first and composes against that chain's provenance. It is the most expensive route in this
file and the only one that runs a producer, which is why nothing calls it implicitly — no draft is
composed on page load, on accept, or on arrangement.

WHAT DRAFTING STILL DOES NOT DO. The percepts a draft rests on are SUGGESTIONS: quarantined, held
inside the draft, committed to no post. `POST /draft` writes exactly one thing — the draft on the
Atlas document — and `POST /draft/accept` writes exactly one more, a manuscript. Neither accepts a
mark, edits a region, or touches the ledger.

ATLAS C4 adds plan mode, and C3 adds relation edges:

    POST   /api/v1/atlas/{id}/plan                a thesis → the proposed ArgumentPlan, NOT persisted
    POST   /api/v1/atlas/{id}/plan/accept         the writer's edited plan → RE-BOUND, then persisted
    DELETE /api/v1/atlas/{id}/plan                drop the accepted plan
    POST   /api/v1/atlas/{id}/relations           a drawn line → a committed relation, or a refusal
    DELETE /api/v1/atlas/{id}/relations/{edge_id} take the edge off the canvas; the ledger keeps the mark

WHY PROPOSING DOES NOT PERSIST. A proposal is a question the writer has not answered yet, and an
Atlas that stored every thesis anyone tried would accumulate arguments nobody chose. Accepting is
the gesture that means something, and it is the one that writes.

WHY ACCEPTING RE-BINDS RATHER THAN RECORDING. The accept payload is a browser's, so every status
in it is discarded and `plan_argument` judges the edited claims again against the corpus as it is
at accept time — the same asymmetry the Director keeps with the model, applied to the client.

READ-ONLY WITH RESPECT TO EVIDENCE, WITH EXACTLY ONE EXCEPTION — `POST /relations`. Drawing a line
from one image to another IS the curator's decision, so that route appends the one relation mark
`compare_views` produced to the two posts the writer named. It can do nothing else: it cannot edit
a mark, delete one, or touch a region, and every other route in this file is as read-only as it
was. A refusal writes nothing at all.

OTHERWISE, READ-ONLY WITH RESPECT TO EVIDENCE. Nothing here writes to a post, creates a percept, accepts a
suggestion, or touches the ledger. The only thing these routes write is where a picture sits on a
canvas. C2 adds percept creation — through the EXISTING quarantine and Accept path, not through
here.
"""
from __future__ import annotations

import asyncio

from typing import Any, Dict, List, Mapping, Optional

from bson.errors import InvalidId
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.database import post_collection
from backend.services import atlas_draft as D
from backend.services import atlas_plan as P
from backend.services import atlas_relation as R
from backend.services import atlas_scout as S
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


class NotePatch(BaseModel):
    """One author note. Two fields, and the model is closed: FastAPI drops anything else the
    client sent, so percept data cannot arrive inside a note even before the service whitelists it."""
    note_id: Optional[str] = None
    text: str = ""


class NotesPatch(BaseModel):
    node_id: str
    notes: List[NotePatch] = Field(default_factory=list)


class NotesRequest(BaseModel):
    nodes: List[NotesPatch] = Field(default_factory=list)


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
    # `atlas_service` because the relation hydrator lives beside `compare_views`' vocabulary, and
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


@router.post("/{atlas_id}/notes")
async def save_notes(atlas_id: str, body: NotesRequest):
    """Save the author's notes on one or more images. Notes only — this cannot move a node.

    T1's second tiny write, and the only one that stores something a person typed. An author note
    is the writer's freehand aside: NOT a percept, NOT evidence, NOT citable, and never entering
    the ledger. It lives here beside the arrangement because it is the same kind of thing — the
    writer's own thinking, about the corpus rather than in it.

    Nothing on this route can produce a percept, and nothing anywhere can promote a note into one.
    The other lane — the machine read — runs the existing Director and can only ever mint a
    QUARANTINED proposal on the post, which is reviewed in the Differential. Two lanes, no bridge.
    """
    result = await A.save_notes(
        atlas_id, [n.model_dump() for n in body.nodes])
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


# ── T2: the Scout ────────────────────────────────────────────────────────────

class ScoutRequest(BaseModel):
    limit: int = 0              # 0 → the module's own ceiling


@router.post("/{atlas_id}/scout")
async def scout_relations(atlas_id: str, body: ScoutRequest):
    """Ask which pairs might repay comparison. Proposes only; grounds nothing; persists nothing.

    THE ROUTE HAS NO WRITE, and that is the guard rather than a description of one. A candidate
    returned here is session material: it is not an edge, not a percept, not in the Atlas document
    and not in the ledger. The only way one becomes a relation is `POST /{atlas_id}/relations` —
    C3's gate — which runs `compare_views` and can refuse. There is deliberately no route that
    turns a candidate into an edge directly, because such a route would be a way to draw a line
    between two photographs without ever looking at them.

    REFUSAL IS 200, like C3's. "The scout could not be reached" and "nothing here is worth
    comparing" are answers about the corpus and the tooling, not malfunctions of the request.
    """
    doc = await _atlas_or_404(atlas_id)
    ids = [str(n.get("post_id")) for n in doc.get("nodes") or []]
    posts = await _posts_for(ids)
    return await asyncio.to_thread(
        S.propose_relations, doc, posts,
        limit=body.limit or S.MAX_CANDIDATES)


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


# ── C5: the writer ───────────────────────────────────────────────────────────

class DraftRequest(BaseModel):
    why: str = ""


class AcceptDraftRequest(BaseModel):
    manuscript_id: str = ""     # append to this manuscript; blank opens a new one
    chapter_id: str = ""        # append to this chapter; blank opens one for the reading
    title: str = ""


def _draft_or_404(doc: Mapping[str, Any]) -> Dict[str, Any]:
    draft = doc.get("draft")
    if not isinstance(draft, Mapping) or not draft:
        raise HTTPException(status_code=409,
                            detail="this Atlas holds no draft; draft the article first")
    return dict(draft)


@router.post("/{atlas_id}/draft")
async def draft_article(atlas_id: str, body: DraftRequest):
    """The accepted plan → an executed chain → M3's prose → M4's live percepts. QUARANTINED.

    THE ORDER IS M3's AND IS NOT NEGOTIABLE. The stored plan is re-bound against the corpus as it
    is now (a percept that has stopped resolving is refused here, before a word is written), its
    percept chain is EXECUTED, and only then is the article composed against that chain's
    provenance. Composing straight from the accepted plan would describe evidence that may never
    have been produced.

    THE PRODUCERS RUN FOR REAL, and their output stays quarantined. `run_corpus_plan` routes each
    step to its image's context; what comes back are suggestions, held in the draft, accepted into
    no post. The composition is synchronous and GPU-bound, so it runs off the event loop.
    """
    doc = await _atlas_or_404(atlas_id)

    blocker = D.draft_blocker(doc)
    if blocker is not None:
        # 409, not 422: the request is well formed and the Atlas is simply not in a state that can
        # be drafted from. The reason travels as the writer's own sentence.
        raise HTTPException(status_code=409,
                            detail={"reason": blocker, "message": D.blocker_text(blocker)})

    corpus, memory = await _corpus_memory(doc, why=body.why)
    argument, notes = D.argument_from_stored_plan(doc, memory)
    if argument is None:
        raise HTTPException(status_code=409, detail={
            "reason": D.BLOCK_NO_CLAIMS, "message": D.blocker_text(D.BLOCK_NO_CLAIMS),
            "notes": notes})

    plan = getattr(argument, "plan", None)
    if plan is None or not getattr(plan, "steps", ()):
        # An argument that binds but plans no chain has nothing to execute, and M3 would compose
        # nothing from it. Said plainly rather than returned as an empty article.
        raise HTTPException(status_code=409, detail={
            "reason": D.BLOCK_ALL_REFUSED,
            "message": ("No percept chain could be planned for this argument, so there is nothing "
                        "to run and nothing to write from."),
            "notes": notes})

    from backend.services.director.corpus_execution import build_corpus_context, run_corpus_plan

    run_id = f"atlas:{atlas_id}:draft"
    posts = await _posts_for(P.node_post_ids(doc))
    cctx = build_corpus_context(corpus, posts, run_id=run_id)
    try:
        chain = await asyncio.to_thread(run_corpus_plan, plan, memory, cctx, chain_id=run_id)
        article = await asyncio.to_thread(
            D.compose_from_chain, argument, memory,
            provenance=chain.provenance, suggestions=cctx.all_suggestions(), run_id=run_id)
    finally:
        cctx.close()

    notes = list(notes) + [f"composed against a run of {len(chain.provenance.lineage)} step(s)"]
    stored = D.stored_draft(article, thesis=str((doc.get("plan") or {}).get("thesis") or ""),
                            run_id=run_id, notes=notes, now=A.utc_now())
    D.assert_draft_is_quarantined(stored)

    updated = await A.save_draft(atlas_id, stored)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return {"atlas": A._out(updated), "draft": stored}


@router.get("/{atlas_id}/draft/export")
async def export_draft(atlas_id: str):
    """The M4 perceptual-article artifact: the resolved article, exactly as the renderer eats it.

    A read, and only a read. Exporting does not accept, commit or publish anything — the payload
    carries `committed: false` all the way out, and the passages are included so what Accept WOULD
    write can be inspected before anyone accepts it.
    """
    doc = await _atlas_or_404(atlas_id)
    draft = _draft_or_404(doc)
    article = draft.get("article") or {}
    return {
        "atlas_id": atlas_id,
        "title": str(doc.get("title") or ""),
        "state": draft.get("state"),
        "committed": bool(draft.get("committed")),
        "thesis": draft.get("thesis"),
        "run_id": draft.get("run_id"),
        "drafted_at": draft.get("drafted_at"),
        "article": article,
        "passages": D.passages(article),
        "limits": D.limit_lines(article),
        "notes": draft.get("notes") or [],
    }


@router.post("/{atlas_id}/draft/accept")
async def accept_draft(atlas_id: str, body: AcceptDraftRequest):
    """The drafted passages → the manuscript. The one place prose leaves quarantine.

    THE CURATOR'S GESTURE, and nothing more automatic than that. What crosses is what M3 composed;
    what M3 refused crosses as a marked limits passage rather than as body text, because a limit
    pasted in as prose becomes a finding on the next read. Every passage keeps the step_ids it
    rests on, so an accepted paragraph is still checkable after it has left the canvas.

    The draft is marked accepted rather than deleted. A writer who accepted an article and then
    wants to see what it rested on should find it still there, saying it has been accepted.
    """
    doc = await _atlas_or_404(atlas_id)
    draft = _draft_or_404(doc)
    if str(draft.get("state")) == D.DRAFT_ACCEPTED:
        raise HTTPException(status_code=409,
                            detail="this draft has already been accepted into a manuscript")

    article = draft.get("article") or {}
    items = D.passages(article)
    if not items:
        raise HTTPException(status_code=409, detail=(
            "this draft composed no prose; there is nothing to accept. Read the refusals on it."))

    blocks = D.passages_to_text_blocks(items)
    from backend.services.manuscript_service import ManuscriptService
    svc = ManuscriptService()

    title = (body.title or str(draft.get("thesis") or "") or str(doc.get("title") or "")).strip()
    manuscript_id = (body.manuscript_id or "").strip()
    chapter_id = (body.chapter_id or "").strip()
    if not manuscript_id:
        created = await svc.create_manuscript(title)
        manuscript_id = str(created.get("id"))
        chapter_id = ""
    if not chapter_id:
        # A reading lands as its own chapter. Appending scenes into whatever chapter happened to
        # be first would interleave one argument's prose with another's.
        holder = await svc.add_chapter(manuscript_id, title)
        if holder is None:
            raise HTTPException(status_code=404, detail=f"no manuscript '{manuscript_id}'")
        chapter_id = str((holder.get("chapters") or [])[-1].get("id"))

    scene = await svc.add_scene(manuscript_id, chapter_id, title, blocks)
    if scene is None:
        raise HTTPException(
            status_code=404,
            detail=f"no manuscript '{manuscript_id}' or chapter '{chapter_id}'")

    stored = dict(draft)
    stored["state"] = D.DRAFT_ACCEPTED
    stored["accepted_at"] = A.utc_now()
    stored["manuscript_id"] = manuscript_id
    stored["chapter_id"] = chapter_id
    stored["scene_id"] = str((scene or {}).get("id") or "")
    updated = await A.save_draft(atlas_id, stored)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return {"atlas": A._out(updated), "draft": stored,
            "manuscript_id": manuscript_id, "scene": scene, "passages": len(items)}


@router.delete("/{atlas_id}/draft")
async def dismiss_draft(atlas_id: str):
    """Drop the draft. The accepted plan, the images and the arrangement all stay.

    Dismissing is cheap and repeatable BECAUSE the plan survives it: the writer can draft again
    from the same argument and get prose composed against a fresh run.
    """
    updated = await A.save_draft(atlas_id, None)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no atlas '{atlas_id}'")
    return {"atlas": A._out(updated), "draft": None}
