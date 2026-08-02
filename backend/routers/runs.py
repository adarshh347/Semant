"""
CIRCUIT-002 SURFACE-002 — the run routes: start, poll, stream, answer.

Four endpoints over one shape (`RunView`, `run-contract.md`). The whole engine, drivable by a
person with a set of images and a sentence.

    POST /api/v1/runs                 image_ids and/or tags + a prompt  → {run_id}
    GET  /api/v1/runs/{id}            the current RunView (poll)
    GET  /api/v1/runs/{id}/events     the same RunView, streamed as it changes (SSE)
    POST /api/v1/runs/{id}/answer     A3 — the curator answers; the SAME run continues

ANNOTATION-INDEPENDENT. The only thing a post must have to join a run is a picture. Nothing here
reads `region_annotations` as a precondition; the corpus is assembled from `photo_url` and the
actuators produce the evidence. A curator's committed marks, where they exist, are folded in by
`hydrate_corpus` as a head start.

WHERE THE WORK HAPPENS. The loop is synchronous and its runners drive async producers with
`run_until_complete`, which cannot nest inside the server's loop. So a run executes on the SAME
single orchestration worker thread SURFACE-001 introduced — one persistent event loop, plans
serialised, the server loop never blocked. Reusing that worker rather than starting a second one is
deliberate: two workers would race for one GPU.

SUGGESTIONS-ONLY, and it is the reason this can be exposed at all. A run accumulates quarantined
descriptors and returns them for the existing supervised review. It accepts nothing, commits
nothing, and writes to no post — pinned by a test that hashes every post document before and after.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from bson.errors import InvalidId
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.database import post_collection
from backend.services import run_store
from backend.services.director import run_surface as rs

router = APIRouter()

# How often the SSE stream looks for a change, and how long it will wait before giving the client
# something to hold. A stream that never speaks is indistinguishable from a broken one.
_STREAM_TICK_SECONDS = 0.5
_STREAM_KEEPALIVE_TICKS = 30

# In-process progress, published per round while a run is still working. The STORE remains the
# source of truth — this only exists because a run's rounds happen inside one synchronous call, and
# a curator watching a two-minute run deserves to see it move.
_progress: Dict[str, Dict[str, Any]] = {}


class RunRequest(BaseModel):
    prompt: str = Field(..., description="the curator's intention; fixed for the life of the run")
    image_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    mode: str = Field(default=rs.MODE_EXPLORE)
    max_rounds: int = Field(default=4, ge=1, le=12)


class AnswerRequest(BaseModel):
    answer: str


# ── corpus resolution ────────────────────────────────────────────────────────

async def _posts_for(spec: rs.RunSpec, collection=None) -> Dict[str, Dict[str, Any]]:
    """The posts a run spans: the ids the curator listed, then whatever the tags resolved to.

    A missing or malformed id is SKIPPED and the run says so through `hydrate_corpus`'s
    `unreadable` — dropping it silently would let a run report on four images while the curator
    believes it read five.
    """
    posts = collection if collection is not None else post_collection
    out: Dict[str, Dict[str, Any]] = {}
    for raw in spec.image_ids:
        try:
            doc = await posts.find_one({"_id": ObjectId(raw)})
        except (InvalidId, TypeError):
            doc = await posts.find_one({"_id": raw})
        if doc:
            out[str(doc.get("_id"))] = doc
    if spec.tags:
        cursor = posts.find({"general_tags": {"$in": list(spec.tags)}})
        async for doc in cursor:
            out.setdefault(str(doc.get("_id")), doc)
    return out


# ── driving, on the orchestration worker ─────────────────────────────────────

def _worker_loop():
    """The single persistent event loop the producers' `run_until_complete` binds to.

    Held on `routers.posts` rather than here so SURFACE-001's orchestrate route and a run share
    one loop and one worker. ModelManager's semaphores bind to that loop once and are reused; a
    fresh loop per request would rebind them and fail.
    """
    from backend.routers import posts as P
    if P._orchestration_loop is None:
        P._orchestration_loop = asyncio.new_event_loop()
    return P._orchestration_loop


def _pool():
    from backend.routers import posts as P
    return P._orchestration_pool


def _drive_in_worker(spec: rs.RunSpec, posts: Dict[str, Dict[str, Any]], run_id: str,
                     max_rounds: int, publish) -> Dict[str, Any]:
    """Runs on the orchestration worker. Returns everything the store needs to persist."""
    engine = None
    try:
        engine = rs.build_engine(spec, posts, run_id=run_id, loop=_worker_loop())
        result = rs.lc.run_loop(
            spec.prompt, engine.memory, engine.registry, director=engine.director,
            max_rounds=max_rounds, loop_id=run_id, resolve_fn=engine.resolver,
            on_round=lambda record: publish(run_id, record, engine, spec))
        view = rs.assemble_view(spec, result, engine, run_id=run_id, now=run_store.utc_now())
        return _persistable(view, result, engine)
    finally:
        if engine is not None:
            engine.close()


def _resume_in_worker(spec: rs.RunSpec, posts: Dict[str, Dict[str, Any]], run_id: str,
                      state_doc: Dict[str, Any], image_of: Dict[str, str], answer: str,
                      max_rounds: int, publish) -> Dict[str, Any]:
    """A3 across a request boundary: rebuild the run from what was stored, then continue it."""
    engine = None
    try:
        state = rs.lc.ResumeState.from_dict(state_doc)
        engine = rs.build_engine(spec, posts, run_id=run_id, loop=_worker_loop(),
                                 image_of=image_of)
        # The stored packet is A3's plain `WorkingMemory` — it carries the run's evolved ids and
        # the curator's words, but not the corpus. Re-hydrating from the posts and keeping the
        # stored ids restores the corpus view WITHOUT inventing evidence: the ids are the run's
        # own, and the resolver re-attributes them to their images through `image_of`.
        packet = state.memory
        from dataclasses import replace as _replace
        memory = _replace(engine.memory,
                          region_ids=packet.region_ids, mark_ids=packet.mark_ids,
                          ground_ids=packet.ground_ids, percept_ids=packet.percept_ids,
                          phrase=packet.phrase, first_attention=packet.first_attention,
                          phrase_source=packet.phrase_source)
        state = _replace(state, memory=memory)
        prior = rs.lc.LoopResult(
            loop_id=state.loop_id, intention=state.intention, rounds=state.rounds,
            stop_reason=rs.lc.AWAITING_ANSWER, memory=memory,
            planner_calls=state.planner_calls, question=state.question, resume_state=state)
        result = rs.lc.resume_loop(
            prior, answer, engine.registry, director=engine.director, max_rounds=max_rounds,
            resolve_fn=engine.resolver,
            on_round=lambda record: publish(run_id, record, engine, spec))
        view = rs.assemble_view(spec, result, engine, run_id=run_id, now=run_store.utc_now())
        return _persistable(view, result, engine)
    finally:
        if engine is not None:
            engine.close()


def _persistable(view: rs.RunView, result, engine) -> Dict[str, Any]:
    return {"view": view.to_dict(),
            "resume": result.resume_state.to_dict() if result.resume_state else None,
            "image_of": dict(engine.resolver.image_of)}


def _publish_round(run_id: str, record, engine, spec: rs.RunSpec) -> None:
    """A partial view, after each round. Called from the worker thread; a plain dict assignment is
    the whole synchronisation, because the only reader is a poll loop that wants the latest."""
    _progress[run_id] = {
        "run_id": run_id, "status": rs.STATUS_RUNNING, "intention": spec.prompt,
        "mode": spec.mode,
        "corpus": [{"post_id": i.post_id, "image_url": i.image_ref, "title": i.title}
                   for i in engine.corpus.images],
        "rounds": [record.to_dict()],
        "round": record.index, "verdict": record.verdict,
        "new_evidence": dict(record.new_evidence),
        "suggestions_so_far": len(engine.ctx.all_suggestions()),
    }


# ── the four routes ──────────────────────────────────────────────────────────

@router.post("")
@router.post("/")
async def start_run(req: RunRequest):
    """Start a run. Returns `{run_id}` immediately; the work happens on the orchestration worker.

    A prompt is required and at least one of `image_ids`/`tags` — a run over nothing is not an
    empty run, it is a request that names no images, and answering it with a manufactured empty
    result would be the dishonest reading of the two.
    """
    spec = rs.RunSpec.of(prompt=req.prompt, image_ids=req.image_ids, tags=req.tags, mode=req.mode)
    if not spec.prompt:
        raise HTTPException(status_code=422, detail="A prompt is required")
    if not spec.image_ids and not spec.tags:
        raise HTTPException(status_code=422, detail="At least one of image_ids or tags is required")

    posts = await _posts_for(spec)
    if not posts:
        raise HTTPException(status_code=404, detail="No posts matched image_ids/tags")

    run_id = rs.new_run_id()
    await run_store.create_run(run_id=run_id, spec=spec.to_dict(), status=rs.STATUS_PENDING)
    asyncio.get_running_loop().create_task(
        _run_and_store(spec, posts, run_id, req.max_rounds))
    return {"run_id": run_id, "status": rs.STATUS_PENDING}


async def _run_and_store(spec: rs.RunSpec, posts: Dict[str, Dict[str, Any]], run_id: str,
                         max_rounds: int) -> None:
    await run_store.set_status(run_id, rs.STATUS_RUNNING)
    loop = asyncio.get_running_loop()
    try:
        stored = await loop.run_in_executor(
            _pool(), _drive_in_worker, spec, posts, run_id, max_rounds, _publish_round)
        await run_store.save_view(run_id, stored["view"], resume=stored["resume"],
                                  image_of=stored["image_of"])
    except Exception as exc:                       # noqa: BLE001
        # A run that fell over says so, with the exception type and nothing invented. `stopped`
        # is the honest state: it is not complete, and it is not waiting for a human either.
        await run_store.save_view(run_id, {
            "run_id": run_id, "status": rs.STATUS_STOPPED, "intention": spec.prompt,
            "mode": spec.mode, "stop_reason": f"run_failed:{type(exc).__name__}",
            "notes": [str(exc)[:400]]})
    finally:
        _progress.pop(run_id, None)


@router.get("/{run_id}")
async def get_run(run_id: str):
    """The current RunView. While a run is still working this returns its stored state plus the
    latest round the worker has published — poll and stream agree on the same shape."""
    doc = await run_store.get_run(run_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")
    return _view_of(doc)


def _view_of(doc: Dict[str, Any]) -> Dict[str, Any]:
    view = doc.get("view")
    if view:
        return view
    # Still pending/running and nothing stored yet: report the truthful in-flight shape rather
    # than an empty RunView that would read as a run which found nothing.
    partial = _progress.get(str(doc.get("_id")), {})
    return {"run_id": str(doc.get("_id")), "status": doc.get("status"),
            "intention": (doc.get("spec") or {}).get("prompt", ""),
            "mode": (doc.get("spec") or {}).get("mode", rs.MODE_EXPLORE),
            "corpus": partial.get("corpus", []), "rounds": partial.get("rounds", []),
            "question": None, "stop_reason": None, "weakest_link": None,
            "suggestions": [], "production_records": [], "article": None,
            "answer": None, "notes": [], "progress": partial or None,
            "created_at": doc.get("created_at"), "updated_at": doc.get("updated_at")}


@router.get("/{run_id}/events")
async def stream_run(run_id: str):
    """Server-sent events: the same RunView, pushed when it changes, until the run is terminal.

    Poll is the fallback and returns the identical shape — a client that cannot hold a stream open
    must not get a different, thinner truth.
    """
    doc = await run_store.get_run(run_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")

    async def _events():
        last = ""
        idle = 0
        while True:
            current = await run_store.get_run(run_id)
            if current is None:
                yield f"event: gone\ndata: {json.dumps({'run_id': run_id})}\n\n"
                return
            payload = _view_of(current)
            encoded = json.dumps(payload, default=str)
            if encoded != last:
                last, idle = encoded, 0
                yield f"event: run\ndata: {encoded}\n\n"
            else:
                idle += 1
                if idle >= _STREAM_KEEPALIVE_TICKS:
                    idle = 0
                    yield ": keepalive\n\n"
            if payload.get("status") in (rs.STATUS_COMPLETE, rs.STATUS_STOPPED,
                                         rs.STATUS_AWAITING_ANSWER):
                return
            await asyncio.sleep(_STREAM_TICK_SECONDS)

    return StreamingResponse(_events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/answer")
async def answer_run(run_id: str, req: AnswerRequest):
    """A3 at the surface: the curator's answer resumes the SAME run.

    Synchronous, unlike the start: an answer is a turn in a conversation and the person is waiting.
    The returned view's rounds EXTEND the prior trace — one receipt for the whole arc, ask through
    answer through continuation.
    """
    doc = await run_store.get_run(run_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")
    if not run_store.is_answerable(doc):
        raise HTTPException(status_code=409,
                            detail=f"Run '{run_id}' is not waiting for an answer "
                                   f"(status: {doc.get('status')})")

    spec = rs.RunSpec.of(**{**(doc.get("spec") or {}), "prompt": (doc.get("spec") or {}).get("prompt", "")})
    posts = await _posts_for(spec)
    if not posts:
        raise HTTPException(status_code=409,
                            detail="The images this run was about can no longer be read")

    loop = asyncio.get_running_loop()
    stored = await loop.run_in_executor(
        _pool(), _resume_in_worker, spec, posts, run_id, dict(doc.get("resume") or {}),
        dict(doc.get("image_of") or {}), req.answer, 4, _publish_round)
    await run_store.save_view(run_id, stored["view"], resume=stored["resume"],
                              image_of=stored["image_of"])
    _progress.pop(run_id, None)
    return stored["view"]


@router.get("")
@router.get("/")
async def list_runs(limit: int = 20):
    """Newest first — the demo needs to find the run it started a moment ago."""
    docs = await run_store.list_runs(limit=limit)
    return {"runs": [{"run_id": str(d.get("_id")), "status": d.get("status"),
                      "prompt": (d.get("spec") or {}).get("prompt", ""),
                      "mode": (d.get("spec") or {}).get("mode", rs.MODE_EXPLORE),
                      "created_at": d.get("created_at"),
                      "updated_at": d.get("updated_at")} for d in docs]}
