"""
CIRCUIT-002 SURFACE-002 — where a run lives between requests.

A run is the first thing in this system that OUTLIVES the request that started it. A2 taught the
loop to stop and ask; A3 taught it to continue from the answer — but only inside one process, with
the `ResumeState` held in a local variable. The curator answers minutes later, over a new HTTP
request, quite possibly to a different worker. This module is the store that makes that the same
run rather than a new one.

WHAT IS STORED, AND WHY EACH PIECE. Three things, and none of them is a convenience:

  view        the `RunView` the API serves. Stored whole rather than re-derived, because a run's
              receipt must not change when the code that renders it does.
  resume      A3's `ResumeState`, serialized. This is what an answer resumes FROM — the memory,
              the executed signatures, the closed doors, the trace so far. Present exactly when
              the run is `awaiting_answer`, which is the same invariant A3 already holds.
  image_of    the corpus resolver's step → image map. Without it a resumed run would re-attribute
              the first half's evidence to the focus image, and a second-round step would be
              judged against the wrong picture's packet.

NOT WRITE-BEHIND. `vision_runs` is observability: a failed write there must never change what the
instrumented route does. This is the opposite — the document IS the run's continuity, so a failed
write is reported to the caller instead of swallowed. A run that looks live but cannot be answered
would be the dishonest outcome.

NOTHING AUTHORITATIVE. Every suggestion in a stored view is quarantined. Persisting a run commits
nothing, accepts nothing, and touches no post.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

CONTRACT_VERSION = 1

# The lifecycle, restated here so the store can validate without importing the driver (and so a
# rename cannot half-happen across the two modules).
STATUSES = ("pending", "running", "awaiting_answer", "complete", "stopped")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collection(collection=None):
    """The runs collection, injectable. Tests hand a `FakeCollection`; production gets the real
    one. Imported lazily so this module can be exercised with no database configured at all."""
    if collection is not None:
        return collection
    from backend.database import run_collection
    return run_collection


def new_run_doc(*, run_id: str, spec: Mapping[str, Any], status: str = "pending",
                now: Optional[str] = None) -> Dict[str, Any]:
    """The document a run starts as. Pure — no clock it is not handed, no database."""
    stamp = now or utc_now()
    return {
        "_id": run_id,
        "contract_version": CONTRACT_VERSION,
        "spec": dict(spec),
        "status": status if status in STATUSES else "pending",
        "view": None,
        "resume": None,
        "image_of": {},
        "created_at": stamp,
        "updated_at": stamp,
    }


async def create_run(*, run_id: str, spec: Mapping[str, Any], status: str = "pending",
                     now: Optional[str] = None, collection=None) -> Dict[str, Any]:
    doc = new_run_doc(run_id=run_id, spec=spec, status=status, now=now)
    await _collection(collection).insert_one(doc)
    return doc


async def get_run(run_id: str, *, collection=None) -> Optional[Dict[str, Any]]:
    return await _collection(collection).find_one({"_id": run_id})


async def save_view(run_id: str, view: Mapping[str, Any], *,
                    resume: Optional[Mapping[str, Any]] = None,
                    image_of: Optional[Mapping[str, str]] = None,
                    now: Optional[str] = None, collection=None) -> bool:
    """Store what the run currently is.

    `resume` is written on EVERY save, including as None — a run that has moved past
    `awaiting_answer` must stop being answerable, and leaving a stale state behind would let a late
    answer resume a run that has already continued without it.
    """
    stamp = now or utc_now()
    update = {
        "status": str(view.get("status") or "running"),
        "view": dict(view),
        "resume": dict(resume) if resume else None,
        "updated_at": stamp,
    }
    if image_of is not None:
        update["image_of"] = {str(k): str(v) for k, v in image_of.items()}
    result = await _collection(collection).update_one({"_id": run_id}, {"$set": update})
    return bool(getattr(result, "matched_count", 0))


async def set_status(run_id: str, status: str, *, now: Optional[str] = None,
                     collection=None) -> bool:
    result = await _collection(collection).update_one(
        {"_id": run_id}, {"$set": {"status": status, "updated_at": now or utc_now()}})
    return bool(getattr(result, "matched_count", 0))


async def list_runs(*, limit: int = 20, collection=None) -> List[Dict[str, Any]]:
    """Newest first. A thin listing — the demo needs to find a run it started a moment ago."""
    cursor = _collection(collection).find({}).sort("created_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        out.append(doc)
    return out


def is_answerable(doc: Mapping[str, Any]) -> bool:
    """A run may be answered exactly when it is waiting for one AND has the state to continue
    from. Both, because either alone is a run that would answer into a void."""
    return bool(doc.get("status") == "awaiting_answer" and doc.get("resume"))
