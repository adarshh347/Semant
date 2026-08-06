"""
Semant Writer W7 — the readings store: flags the author dismisses or acts on.

A reading is DIAGNOSTICS. Nothing in this module is prose, nothing here can become prose,
and there is no accept path: acting on a flag means going back through the render loop
under adjusted orchestration, which is the author's action in the editor, not a write here.

WHY FLAGS ARE PERSISTED AT ALL. Two reasons, and neither is "so we can apply them":

  A FLAG NEEDS AN IDENTITY TO DISMISS. Propose-not-commit applies to diagnostics as much as
  to prose — the author decides what to do with each one, and a dismissal has to stick.

  THE READING IS ITSELF AUDITED. The editor is held to the standard it holds the prose to:
  every reading records which declared elements it measured against and which model made
  it, so "why was this flagged?" has an answer that resolves, exactly as "what wrote this?"
  does for a passage.

The author's response is the calibration signal (§5): `dismissed` is a false alarm, `acted`
is a real divergence, and an operator that accumulates real divergences from its own intent
is miscalibrated. Recorded from the first reading; nothing reads it that way yet.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.database import writer_reading_collection
from backend.services.writer import alignment, instrument

OPEN = "open"
DISMISSED = "dismissed"
ACTED = "acted"


class ReadingError(ValueError):
    """A decision that cannot be applied, with the reason."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _out(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


async def store(
    project_id: str,
    result: "alignment.AlignmentResult",
    *,
    passage_id: str = "",
    block_id: str = "",
    scene_id: str = "",
    manuscript_id: str = "",
) -> Dict[str, Any]:
    """Persist one reading and its flags. Writes no prose and touches no canon."""
    now = _now()
    doc = {
        "_id": f"rdg_{uuid4().hex[:12]}",
        "project_id": project_id,
        "passage_id": passage_id,
        "block_id": block_id,
        "scene_id": scene_id,
        "manuscript_id": manuscript_id,
        "status": result.status,
        "detail": result.detail,
        # The reading's own provenance: what it measured against, and who made it.
        "measured_against": [dict(e) for e in result.measured_against],
        "model": result.model,
        "diagnostics": list(result.diagnostics),
        "flags": [
            {**flag, "id": f"flg_{uuid4().hex[:10]}", "state": OPEN, "decided_at": None}
            for flag in result.flags
        ],
        "read_at": now,
    }
    await writer_reading_collection.insert_one(doc)
    return _out(doc)


async def get(reading_id: str) -> Optional[Dict[str, Any]]:
    return _out(await writer_reading_collection.find_one({"_id": reading_id}))


async def list_for(project_id: str, *, scene_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"project_id": project_id}
    if scene_id:
        query["scene_id"] = scene_id
    out: List[Dict[str, Any]] = []
    async for doc in writer_reading_collection.find(query).sort("read_at", -1):
        out.append(_out(doc))
        if len(out) >= limit:
            break
    return out


async def decide(reading_id: str, flag_id: str, state: str, note: str = "") -> Dict[str, Any]:
    """The author's response to one flag: `dismissed` (false alarm) or `acted` (real).

    Neither writes prose. `acted` records that the author took it seriously — what they
    actually DO about it is a re-render through the loop, an operator edit, or a change to
    the staging, all of which are their own author-driven paths. This is the record of the
    judgement, not the application of a fix.
    """
    if state not in (DISMISSED, ACTED):
        raise ReadingError(f"a flag is either {DISMISSED} or {ACTED}, not {state!r}")

    doc = await writer_reading_collection.find_one({"_id": reading_id})
    if not doc:
        raise ReadingError(f"no such reading: {reading_id}")

    target = next((f for f in doc.get("flags", []) if f.get("id") == flag_id), None)
    if target is None:
        raise ReadingError(f"no such flag on this reading: {flag_id}")

    # DECIDED ONCE, AND ATOMICALLY. The read above is for the error message; the write is
    # what enforces it. Matching `state: OPEN` inside the query makes this a compare-and-set,
    # so of two concurrent decisions on the same flag exactly one lands — a check-then-write
    # would let both through and instrument both, and the calibration signal would record a
    # dismissal and an action for one judgement.
    #
    # It also updates the ONE flag by position rather than replacing the array. Rewriting the
    # whole list would let a decision on flag A silently revert a concurrent decision on
    # flag B, which is the quieter half of the same bug.
    result = await writer_reading_collection.update_one(
        {"_id": reading_id, "flags": {"$elemMatch": {"id": flag_id, "state": OPEN}}},
        {"$set": {
            "flags.$[f].state": state,
            "flags.$[f].note": note or "",
            "flags.$[f].decided_at": _now(),
        }},
        array_filters=[{"f.id": flag_id}],
    )
    if not result.matched_count:
        current = next((f for f in (await writer_reading_collection.find_one(
            {"_id": reading_id}) or {}).get("flags", []) if f.get("id") == flag_id), {})
        raise ReadingError(
            f"flag {flag_id} is already {current.get('state', 'decided')} — "
            f"a decision is made once"
        )

    # THE CALIBRATION SIGNAL. Which operator the flag cited, and what the author made of it.
    await instrument.record(
        alignment.FLAG_DISMISSED if state == DISMISSED else alignment.FLAG_ACTED,
        doc.get("project_id", ""),
        operators=[target["operator"]] if target.get("operator") else [],
        extra={
            "reading_id": reading_id,
            "flag_id": flag_id,
            "element": target.get("element"),
            "element_kind": target.get("element_kind"),
            "operator_version": target.get("operator_version"),
        },
    )
    return _out(await writer_reading_collection.find_one({"_id": reading_id}))
