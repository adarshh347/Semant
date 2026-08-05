"""
Semant Writer W1 — usage instrumentation. RECORD ONLY; reason about it later.

Tier 2 (assemblages: which operators habitually travel together) and Tier 3 (the
semantic ecology) are DATA-GATED. They cannot be designed from first principles — they
have to emerge from a real corpus of one author actually working. That corpus only
exists if we start writing it on day one, so this module ships in W1 and nothing reads
it in W1. That is the point.

Four events, which is the smallest set the later tiers need:
  `render`   — an operator stack fired, under these intents (co-occurrence lives here:
               one event per render carries the WHOLE stack, so pairs are recoverable).
  `refusal`  — it could not render, and why. Refusals are signal, not noise: they map
               where the author's ontology is thin.
  `accept`   — the author took it into canon.
  `dismiss`  — the author threw it away.

WRITE-BEHIND, ALWAYS. Every function here swallows its own errors. Instrumentation that
can break a render is worse than no instrumentation, and an author must never lose a
passage because a stats collection was unreachable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from backend.database import writer_usage_collection

RENDER = "render"
REFUSAL = "refusal"
ACCEPT = "accept"
DISMISS = "dismiss"


async def record(
    event: str,
    project_id: str,
    *,
    operators: Sequence[str] = (),
    intents: Optional[Dict[str, str]] = None,
    passage_id: str = "",
    detail: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Append one usage event. Returns its id, or None if the write failed (never raises).

    `operators` is stored as the ordered stack AND as a sorted `pair` list, because
    co-occurrence is the one query Tier 2 will certainly run and deriving it later from
    the raw stack across a large corpus is needlessly expensive.
    """
    names = [str(n) for n in operators if n]
    pairs: List[str] = []
    for i, a in enumerate(sorted(set(names))):
        for b in sorted(set(names))[i + 1:]:
            pairs.append(f"{a}|{b}")

    doc = {
        "_id": f"wu_{uuid4().hex[:12]}",
        "event": event,
        "project_id": project_id,
        "operators": names,
        "operator_pairs": pairs,
        "intent_keys": sorted((intents or {}).keys()),
        "intents": dict(intents or {}),
        "passage_id": passage_id,
        "detail": detail,
        "extra": dict(extra or {}),
        "at": datetime.now(timezone.utc),
    }
    try:
        await writer_usage_collection.insert_one(doc)
        return doc["_id"]
    except Exception:
        # Deliberately silent. See the module docstring: a stats failure must never be
        # visible in the render path's behaviour.
        return None


async def usage_for_project(project_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Raw events, newest first. A read-out for inspection — nothing reasons on it yet."""
    out: List[Dict[str, Any]] = []
    try:
        cursor = writer_usage_collection.find({"project_id": project_id}).sort("at", -1)
        async for doc in cursor:
            doc = dict(doc)
            doc["id"] = doc.pop("_id")
            out.append(doc)
            if len(out) >= limit:
                break
    except Exception:
        return out
    return out
