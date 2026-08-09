"""
HARNESS-002D — where a semantic inquiry session lives between requests.

THE SAME COLLECTION, A DIFFERENT DOCUMENT SHAPE. The directive's instruction is to reuse the runs
collection and, if `run_store` cannot carry the payload, to build an additive adapter over that
collection with a clear discriminator. `run_store` cannot, and the reason is exactly one field.

    run_store.save_view:  "status": str(view.get("status") or "running")
    run_store.STATUSES:   pending · running · awaiting_answer · complete · stopped

A session's state vocabulary is Lane B's twelve — `framing … awaiting_user … composing · complete ·
exhausted · refused · error`. Writing a session through `save_view` would stamp `awaiting_user`, or
`composing`, into the field that `list_runs`, the runs router and `run_store.is_answerable` all read
as the DIRECTOR run lifecycle. `is_answerable` would then be deciding whether a semantic inquiry can
take a Director answer. `new_run_doc` validates against `STATUSES`; `save_view` does not validate at
all, so the corruption would be silent and would surface only as a run listing full of words nothing
recognises.

So: same collection, discriminated documents, and the run lifecycle field keeps a value FROM the run
vocabulary. The twelve-state session state lives under `session.interaction.state`, where it means
what it says.

    {"_id": "inqs_…", "kind": "semantic_inquiry", "contract_version": 1,
     "status": <run vocabulary>, "session": {…the envelope…},
     "created_at": …, "updated_at": …, "encoding_repairs": [...]}

WHAT IS REUSED RATHER THAN REBUILT. `run_store.acyclic` — the guard that stopped argue mode's
self-referential article from taking a whole run down at BSON encode time. A session embeds three
lanes' snapshots and a model's free-form provenance, so it is exactly the shape that acquires a
cycle by accident, and writing a second projection would be a second place to get it wrong.

NOT WRITE-BEHIND. Like `run_store` and unlike `vision_runs`: this document IS the session's
continuity, so a failed write is reported to the caller rather than swallowed. A session that looks
live but cannot be answered would be the dishonest outcome.

NOTHING AUTHORITATIVE. Persisting a session commits nothing, accepts nothing and touches no post.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from backend.schemas.inquiry_session import SemanticInquirySession
from backend.services.run_store import acyclic

CONTRACT_VERSION = 1

#: The discriminator. Every document this adapter writes carries it, and every read filters on it —
#: so a Director run and a semantic inquiry can share a collection without either being able to
#: load the other and misread its fields as its own.
KIND = "semantic_inquiry"

#: The run-lifecycle value a session document reports, per session state. The mapping is
#: deliberately LOSSY and one-directional: it exists so the shared `status` field stays inside the
#: run vocabulary, and nothing reads it back to recover a session state. `interaction.state` is the
#: session's state and this is a courtesy to anything listing the collection.
_RUN_STATUS: Dict[str, str] = {
    "framing": "running", "reading": "running", "compiling": "running", "ready": "running",
    "executing": "running", "judging": "running", "composing": "running",
    "awaiting_user": "awaiting_answer",
    "complete": "complete", "exhausted": "stopped", "refused": "stopped", "error": "stopped",
}


class SessionNotFound(LookupError):
    """No session with that id. A distinct type so a route maps it to 404 without string matching."""


class SessionWriteFailed(RuntimeError):
    """The write did not land. Raised rather than returned: a caller that carried on would tell
    somebody their answer was recorded when it was not."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collection(collection=None):
    """The runs collection, injectable. Tests hand a fake; production gets the real one. Imported
    lazily so this module can be exercised with no database configured at all."""
    if collection is not None:
        return collection
    from backend.database import run_collection
    return run_collection


def run_status_for(state: str) -> str:
    """A session state → a value from the RUN lifecycle. Unknown maps to `running`, which is the
    only safe direction: `complete` would tell a lister the session had finished."""
    return _RUN_STATUS.get(str(state or ""), "running")


#: The envelope's free-form mappings — the ones holding another lane's snapshot or a model's own
#: provenance. Every cycle a session can acquire is inside one of these, because nothing typed in
#: `inquiry_session.py` can hold a back-reference.
_OPAQUE_FIELDS = ("frame", "graph", "interaction", "evidence", "refusals")


def payload_of(session: SemanticInquirySession, breaks: List[str]) -> Dict[str, Any]:
    """The session as plain, acyclic, BSON-safe data.

    `acyclic` RUNS BEFORE `model_dump`, and the order is forced rather than tidy: pydantic's
    serializer detects the cycle itself and raises `ValueError: Circular reference detected` from
    inside `model_dump`, so a projection applied to its output never gets to run. Sanitising the
    typed model first and re-walking the result afterwards costs one extra pass and means a cycle
    is a marker in one field instead of a 500 on the write.
    """
    receipts = [r.model_copy(update={"payload": acyclic(r.payload, _breaks=breaks),
                                     "provenance": acyclic(r.provenance, _breaks=breaks)})
                for r in session.capability_receipts]
    synthesis = (session.synthesis.model_copy(
        update={"provenance": acyclic(session.synthesis.provenance, _breaks=breaks)})
        if session.synthesis else None)
    safe = session.model_copy(update={
        **{name: acyclic(getattr(session, name), _breaks=breaks) for name in _OPAQUE_FIELDS},
        "capability_receipts": receipts,
        "synthesis": synthesis,
    })
    return acyclic(safe.model_dump(mode="json"), _breaks=breaks)


def new_session_doc(session: SemanticInquirySession, *, now: Optional[str] = None
                    ) -> Dict[str, Any]:
    """The document a session starts as. Pure — no clock it is not handed, no database."""
    stamp = now or utc_now()
    breaks: List[str] = []
    return {
        "_id": session.session_id,
        "kind": KIND,
        "contract_version": CONTRACT_VERSION,
        "status": run_status_for(session.state),
        "session": payload_of(session, breaks),
        "created_at": stamp,
        "updated_at": stamp,
        "encoding_repairs": breaks,
    }


async def create(session: SemanticInquirySession, *, now: Optional[str] = None,
                 collection=None) -> Dict[str, Any]:
    doc = new_session_doc(session, now=now)
    await _collection(collection).insert_one(doc)
    return doc


async def load(session_id: str, *, collection=None) -> SemanticInquirySession:
    """The session, typed. Raises rather than returning None.

    THE READ FILTERS ON THE DISCRIMINATOR. Without it, a Director run id passed to this route would
    load a run document, find no `session` key, and produce a validation error about a missing
    prompt — which reads as a corrupt session rather than as the wrong kind of thing.
    """
    doc = await _collection(collection).find_one({"_id": session_id, "kind": KIND})
    if not doc:
        raise SessionNotFound(session_id)
    payload = doc.get("session")
    if not isinstance(payload, Mapping):
        raise SessionNotFound(session_id)
    return SemanticInquirySession.model_validate(dict(payload))


async def save(session: SemanticInquirySession, *, expected_revision: Optional[int] = None,
               expected_checkpoint: Optional[int] = None,
               now: Optional[str] = None, collection=None) -> Dict[str, Any]:
    """Write the session back.

    `expected_revision` makes the write a COMPARE-AND-SET. Two clients answering one decision at
    the same moment would otherwise both read revision 3, both append, and both write revision 4 —
    and the second would silently erase the first person's answer from an append-only history. The
    filter is the only place that race can be caught, because by the time either write is built,
    both look perfectly well formed.

    `expected_checkpoint` is the SAME mechanism for the stage driver, on a different counter, and
    the two are separate because they count different things. `revision` is the deliberation's turn
    counter and moves only when a fork is settled; a driver checkpoints many times between two
    turns. Sharing one counter would mean either corrupting the optimistic lock a client is holding
    across a pause, or making every stage checkpoint look like a turn nobody took — and a client
    that re-read after each would keep finding its answer stale for reasons it could not see.
    """
    stamp = now or utc_now()
    breaks: List[str] = []
    query: Dict[str, Any] = {"_id": session.session_id, "kind": KIND}
    if expected_revision is not None:
        query["session.revision"] = expected_revision
    if expected_checkpoint is not None:
        query["session.checkpoint"] = expected_checkpoint
    result = await _collection(collection).update_one(query, {"$set": {
        "status": run_status_for(session.state),
        "session": payload_of(session, breaks),
        "updated_at": stamp,
        # Empty on every healthy save. Non-empty names the exact paths that had to be broken —
        # a repaired payload is a defect upstream, and a store that quietly patched one would hide
        # the next as effectively as the first was hidden.
        "encoding_repairs": breaks,
    }})
    if not getattr(result, "matched_count", 0):
        raise SessionWriteFailed(
            f"session {session.session_id} did not accept a write at revision "
            f"{expected_revision!r} / checkpoint {expected_checkpoint!r}. Either it does not exist "
            f"or something else advanced it first; nothing was written and no answer was recorded.")
    return {"matched": True, "encoding_repairs": breaks}


async def list_sessions(*, limit: int = 20, collection=None) -> List[Dict[str, Any]]:
    """Newest first, discriminated. Director runs are not in this listing and cannot be."""
    cursor = _collection(collection).find({"kind": KIND}).sort("created_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        out.append(doc)
    return out


__all__ = ["CONTRACT_VERSION", "KIND", "SessionNotFound", "SessionWriteFailed", "utc_now",
           "run_status_for", "payload_of", "new_session_doc", "create", "load", "save", "list_sessions"]
