"""
HARNESS-002D — the semantic inquiry routes: ask, read, answer.

    POST /api/v1/inquiries                       prompt + post ids + mode  → a session
    GET  /api/v1/inquiries/{session_id}          the same session, current
    POST /api/v1/inquiries/{session_id}/decisions   an answer; the SAME session resumes
    GET  /api/v1/inquiries/{session_id}/events   the same session, streamed (SSE)
    GET  /api/v1/inquiries                       the newest sessions, thin

ONE BODY SHAPE. Every route returns `view.session_view(...)` and nothing else, including the 409s.
A client that had to parse a different shape out of a rejection would have two readers for one
object, and the one exercised least often would be the one that drifted.

WHAT THIS ROUTE DOES NOT CONTAIN. No prompt, no claim taxonomy, no pause policy, no capability
algorithm, no field renaming. Those are the coordinator's stages and the view's projection. What is
here is HTTP: read a body, resolve some posts, call one of two coordinator entry points, persist,
and map the nine typed conflicts onto status codes.

THE NINE CONFLICTS, AND WHY FOUR OF THEM ARE 409. Lane B refuses a response with a typed exception
that carries what it expected and what it got. Four of those are the ordinary weather of a
resumable session — the client was right and merely late, or right and duplicated — and they are
409 with the person's own text echoed back untouched. The other five say the request should never
have been sent in that form, and they are 422. A single "conflict" code across all nine would tell
somebody to retry a thing that will never work.

NOTHING IS ACCEPTED. Creating or answering an inquiry writes exactly one document: the session's own
history. Every post is fingerprinted at creation and re-checked before each write, so "no post,
mark, percept or Atlas edge was touched" is a comparison this route performs rather than a promise
it makes.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.schemas.inquiry_interaction import InteractionMode
from backend.services.inquiry_session import (coordinator, corpus, driver, runtime, steps, store,
                                              view)
from backend.services.inquiry_interaction import InteractionConflict, WrongSession
from backend.services.movement_kernel import PostsMutated

router = APIRouter()

#: How often the stream re-reads the store, and how many quiet ticks before it says something
#: anyway. Same shape and the same reason as the run stream: a stream that never speaks is
#: indistinguishable from a broken one.
_STREAM_TICK_SECONDS = 0.75
_STREAM_KEEPALIVE_TICKS = 20

#: States a session may sit in while work is still happening. The stream stays OPEN through all of
#: them: a stage stream that closed on the first state it did not recognise would end the moment the
#: theorist started, which is precisely the window it exists to show.
_WORKING_STATES = ("framing", "reading", "compiling", "ready", "executing", "judging", "composing")

#: Where the stream stops. `awaiting_user` is not terminal — it is a session working correctly and
#: waiting for a person — but it is a boundary the client must act on, so the stream hands control
#: back rather than holding a socket open across a human's coffee break.
_STREAM_STOPS_AT = ("complete", "exhausted", "refused", "error", "awaiting_user")

#: The four conflicts a client can recover from by re-reading and, in three cases, resubmitting.
#: Everything else Lane B raises is a request that should not have been formed that way.
_CONFLICT_409 = ("stale_revision", "duplicate_response", "wrong_session", "no_decision_open")


class StartInquiry(BaseModel):
    prompt: str = Field(..., description="the person's question, kept byte for byte")
    #: `image_ids` is what the workbench sends; `post_ids` is what everything else in this
    #: repository calls them. Both are read, because renaming one of them would be an edit in
    #: somebody else's lane to save one line here.
    image_ids: List[str] = Field(default_factory=list)
    post_ids: List[str] = Field(default_factory=list)
    mode: str = Field(default="consult")

    def selected(self) -> List[str]:
        seen: List[str] = []
        for raw in [*self.image_ids, *self.post_ids]:
            key = str(raw).strip()
            if key and key not in seen:
                seen.append(key)
        return seen


#: The workbench's verbs → Lane B's `ResponseKind`. Both spellings are accepted and only one is
#: stored: a wire vocabulary is a client's convenience and the session records the canonical one.
_ACTION_KINDS = {
    "select": "select_option", "select_option": "select_option",
    "reject": "reject_all", "reject_all": "reject_all",
    "skip": "skip", "redirect": "redirect", "amend": "amend",
}


class DecisionBody(BaseModel):
    decision_id: str = Field(..., description="the open decision this answers")
    response_id: str = Field(default="", description="the client's idempotency key")
    #: Optional, and the reason it exists is Lane B's `wrong_session`. The path already names the
    #: session, so a mismatch is otherwise UNREACHABLE through HTTP — the route would rewrite a
    #: client's belief about what it was answering into agreement with the URL, which is exactly
    #: the confusion that conflict was typed to name. Sent, it is checked; absent, the path stands.
    session_id: str = ""
    action: str = Field(default="select")
    selected_option_id: str = ""
    free_text: str = ""
    #: Optional only in the schema. A response with no expected revision is accepted and recorded,
    #: but it cannot be protected from the race it exists to prevent, so the session says so.
    expected_revision: Optional[int] = None
    amendment_target: str = ""
    amendment_relation: str = "supplements"

    def as_response(self, session_id: str, revision: int, at: str) -> Dict[str, Any]:
        kind = _ACTION_KINDS.get(str(self.action).strip().lower(), str(self.action).strip())
        return {
            "response_id": self.response_id or f"resp_{session_id}_{self.decision_id}",
            "session_id": session_id,
            "decision_id": self.decision_id,
            "expected_revision": (self.expected_revision
                                  if self.expected_revision is not None else revision),
            "kind": kind,
            "option_id": self.selected_option_id,
            "free_text": self.free_text,
            "amendment_target": self.amendment_target,
            "amendment_relation": self.amendment_relation,
            "at": at,
        }


def _busy(session_id: str, session) -> bool:
    """Whether a stage is in flight for this session right now.

    NARROW ON PURPOSE. "Stages remain to be run" is not busy — most of a paused session's chain is
    pending by definition, and refusing an answer for that reason would report every duplicate,
    stale and unknown-option response as `session_busy` and collapse four of the nine typed
    conflicts into one.

    Busy is the LEASE (held, and readable by another worker) or an attempt that entered external
    work and has not recorded leaving it. Both are persisted facts; `driver.running` is a local
    optimisation that cannot see another process and is checked last.
    """
    if steps.dangling_stages(session):
        return True
    if str((session.driver or {}).get("lease_id") or ""):
        return True
    return driver.running(session_id)


def _stages():
    """The bound stage order. A function rather than a module constant so a test can monkeypatch
    one seam without the import order deciding what a route uses."""
    return runtime.build_stages()


def _view(session) -> Dict[str, Any]:
    return view.session_view(session, servable_classes=coordinator.servable_classes(_stages()))


def _conflict_body(exc: InteractionConflict, session, submitted: Dict[str, Any]) -> Dict[str, Any]:
    """A rejection that keeps the person's words and the session they were written against.

    `submitted` is echoed verbatim — not summarised, not normalised. The workbench holds its own
    selection while it refreshes, and the echo is what lets a person see that what they sent is
    still what they meant.
    """
    return {"error": exc.code, "detail": exc.detail, "recoverable": exc.recoverable,
            "expected": exc.expected, "actual": exc.actual, "refs": list(exc.refs),
            "submitted": submitted, "session": _view(session)}


def _raise_conflict(exc: InteractionConflict, session, submitted: Dict[str, Any]) -> None:
    status = 409 if exc.code in _CONFLICT_409 else 422
    raise HTTPException(status_code=status, detail=_conflict_body(exc, session, submitted))


# ── create ───────────────────────────────────────────────────────────────────

@router.post("")
@router.post("/")
async def start_inquiry(request: StartInquiry) -> Dict[str, Any]:
    """A question and some pictures → a persisted session, advanced to its first honest boundary.

    The session is written BEFORE any model runs and again after. A reading that fails therefore
    leaves a real session saying so, rather than leaving nothing at all and a 500 the person cannot
    reopen.
    """
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="an inquiry needs a question")
    selected = request.selected()
    if not selected:
        raise HTTPException(status_code=422, detail="an inquiry needs at least one post id")
    try:
        mode = InteractionMode(str(request.mode).strip().lower()).value
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"mode must be one of {[m.value for m in InteractionMode]}, "
                   f"got {request.mode!r}") from None

    refs, _ = await corpus.resolve(selected)
    if not any(r.readable for r in refs):
        raise HTTPException(
            status_code=422,
            detail={"error": "no_readable_post",
                    "detail": "none of the selected posts resolved to an image, so there is no "
                              "scene for anything to read",
                    "posts": [r.model_dump(mode="json") for r in refs]})

    session = coordinator.new_session(prompt=prompt, refs=refs, mode=mode)
    await corpus.assert_unchanged(session.posts)
    await store.create(session)

    # SCHEDULED, NOT AWAITED. The whole architecture of this route is this line and the one after
    # it: the session is durable before any model runs, a driver is started, and the response goes
    # back. 002R watched `Starting…` for the length of a four-image reading because the frontend
    # could not subscribe to the stream until this handler returned — which made its progress state
    # structurally incapable of showing progress, however it was written.
    driver.schedule(session.session_id, _stages())
    return JSONResponse(status_code=202, content=_view(session))


# ── read ─────────────────────────────────────────────────────────────────────

@router.get("/{session_id}")
async def read_inquiry(session_id: str) -> Dict[str, Any]:
    return _view(await _load(session_id))


@router.get("")
@router.get("/")
async def list_inquiries(limit: int = 20) -> Dict[str, Any]:
    """The newest sessions, thin. Discriminated on `kind`, so no Director run can appear here."""
    docs = await store.list_sessions(limit=max(1, min(int(limit or 20), 100)))
    return {"sessions": [{
        "session_id": str(d.get("_id") or ""),
        "state": str((d.get("session") or {}).get("interaction", {}).get("state") or "framing"),
        "prompt": str((d.get("session") or {}).get("prompt") or ""),
        "revision": (d.get("session") or {}).get("revision"),
        "created_at": d.get("created_at"), "updated_at": d.get("updated_at"),
    } for d in docs]}


# ── answer ───────────────────────────────────────────────────────────────────

@router.post("/{session_id}/decisions")
async def answer_inquiry(session_id: str, body: DecisionBody) -> Dict[str, Any]:
    """Apply a person's answer to the open decision and carry the SAME session on from there.

    Never a new session and never a rerun: `coordinator.resume` continues from the state the store
    holds, and every stage that already recorded an outcome keeps it.
    """
    session = await _load(session_id)
    stages = _stages()
    submitted = body.model_dump(mode="json")
    payload = body.as_response(session_id, session.revision, stages.clock())

    if body.session_id and body.session_id != session_id:
        _raise_conflict(WrongSession(
            f"this response was written for session {body.session_id!r} and was posted to "
            f"{session_id!r}. It is not applied to either: answering a question the person was not "
            f"looking at is the one outcome worse than refusing them.",
            expected=session_id, actual=body.session_id), session, submitted)

    if _busy(session_id, session):
        # A RESPONSE CANNOT RACE A RUNNING STAGE. The answer is not lost and not applied: the
        # client is told the session is still working, with the same 409 shape it already handles
        # for a stale revision. Applying it would write an interaction state on top of a session a
        # driver is about to checkpoint, and one of the two writes would silently win.
        raise HTTPException(status_code=409, detail={
            "error": "session_busy", "recoverable": True,
            "detail": "this inquiry is still working through a stage. Your answer was not applied "
                      "and nothing was lost — re-read the session and send it again once a "
                      "decision is open.",
            "submitted": submitted, "session": _view(session)})

    try:
        advanced = coordinator.resume(session, payload, stages)
    except InteractionConflict as exc:
        _raise_conflict(exc, session, submitted)
        raise  # unreachable; `_raise_conflict` always raises. Kept so the type is honest.

    await _persist(advanced, expected_revision=session.revision)
    # The remaining stages run off the request for the same reason the first ones do.
    driver.schedule(session_id, stages)
    return _view(advanced)


# ── stream ───────────────────────────────────────────────────────────────────

@router.get("/{session_id}/events")
async def stream_inquiry(session_id: str) -> StreamingResponse:
    """The same view, pushed when it changes. The client falls back to polling on its own.

    Reused in IDIOM from the run stream and not in code: that loop is written against `RunView` and
    the run lifecycle, and its one blocking state is `awaiting_answer`. This lifecycle has twelve
    states and four terminal ones.
    """
    async def events():
        last = ""
        quiet = 0
        while True:
            try:
                payload = json.dumps(_view(await _load(session_id)), default=str)
            except HTTPException:
                yield f"data: {json.dumps({'error': 'gone', 'session_id': session_id})}\n\n"
                return
            if payload != last:
                last, quiet = payload, 0
                yield f"data: {payload}\n\n"
                state = json.loads(payload).get("state")
                if state in _STREAM_STOPS_AT:
                    return
            else:
                quiet += 1
                if quiet >= _STREAM_KEEPALIVE_TICKS:
                    quiet = 0
                    yield ": keepalive\n\n"
            await asyncio.sleep(_STREAM_TICK_SECONDS)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── the two things every route does ──────────────────────────────────────────

async def _load(session_id: str):
    try:
        return await store.load(session_id)
    except store.SessionNotFound:
        raise HTTPException(status_code=404, detail=f"no inquiry session {session_id!r}") from None


async def _persist(session, *, expected_revision: Optional[int]) -> None:
    """Re-check the corpus, then write. In that order, and never the reverse.

    A session that mutated a post and put it back would pass an end-to-end comparison and fail this
    one, which is why the check sits before every write rather than once at the end.
    """
    try:
        await corpus.assert_unchanged(session.posts)
    except PostsMutated as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "posts_mutated",
                    "detail": f"a source post changed while this inquiry ran: {exc}. Nothing was "
                              f"written; an inquiry that altered its own corpus is not a reading "
                              f"of it."}) from None
    try:
        await store.save(session, expected_revision=expected_revision)
    except store.SessionWriteFailed as exc:
        raise HTTPException(status_code=409, detail={
            "error": "stale_session_write", "recoverable": True, "detail": str(exc)}) from None
