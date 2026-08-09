"""
HARNESS-002D — session ids, derived from content wherever a replay has to compare them.

TWO KINDS OF ID, and the split is deliberate.

  THE SESSION ID IS MINTED FROM A CLOCK. It has to be: two people may ask the same question of the
  same images, and those are two sessions. It is the one place in this lane a clock is read, the
  caller may hand one in, and every replay comparison excludes it by name.

  EVERYTHING ELSE IS CONTENT-DERIVED. A stage event, a receipt, a verdict, a section: each is a
  hash of the session id plus what it is about. So replaying a session with frozen model output
  produces the same ids, and the diff between two runs contains only what actually differed —
  rather than being uniformly red because a counter started again.

Lane A learned this the expensive way and Lane B did not have to: `ids.py` there mints from content
for the same reason, and Lane B's package needs no exclusion list at all because it reads no clock.
This module is the middle case — one clock, named, excluded once.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

PREFIXES = {
    "session": "inqs_",
    "stage": "stg_",
    "receipt": "capr_",
    "verdict": "vrd_",
    "section": "sec_",
    "synthesis": "syn_",
    "evidence": "evd_",
}

WIDTH = 12

_WHITESPACE = re.compile(r"\s+")


def normalise(text: Any) -> str:
    return _WHITESPACE.sub(" ", str(text or "")).strip().lower()


def _digest(parts: Sequence[Any]) -> str:
    # NUL-joined, so ("ab","c") and ("a","bc") cannot hash alike.
    return hashlib.sha256("\x00".join(normalise(p) for p in parts).encode("utf-8")).hexdigest()[
        :WIDTH]


def _mint(kind: str, parts: Iterable[Any]) -> str:
    return f"{PREFIXES[kind]}{_digest([kind, *parts])}"


def session_id(prompt: str, post_ids: Sequence[str], *, now: Optional[datetime] = None) -> str:
    """`inqs_<12 hex>` — the one id in this lane derived from a moment.

    Content alone would make two people asking the same question of the same images ONE session,
    and the second would resume the first's decisions. The clock is what keeps them apart.
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    return _mint("session", [prompt, "|".join(sorted(str(p) for p in post_ids)), stamp])


def stage_id(session: str, stage: Any, outcome: Any, seq: int) -> str:
    """Keyed on the SEQUENCE as well as the stage, because a stage legitimately records more than
    one event — `started` then `completed` — and a budget may invoke one twice across branches."""
    return _mint("stage", [session, getattr(stage, "value", stage),
                           getattr(outcome, "value", outcome), seq])


def receipt_id(session: str, observable_ref: str, capability: str) -> str:
    return _mint("receipt", [session, observable_ref, capability])


def verdict_id(session: str, claim_ref: str) -> str:
    return _mint("verdict", [session, claim_ref])


def section_id(session: str, heading: str, text: str) -> str:
    return _mint("section", [session, heading, text])


def synthesis_id(session: str, revision: int) -> str:
    """Keyed on the revision: a session composed again after a further decision is a DIFFERENT
    answer, and giving both the same id would make the second look like an edit of the first."""
    return _mint("synthesis", [session, revision])


def evidence_id(session: str, claim_ref: str, source_ref: str) -> str:
    return _mint("evidence", [session, claim_ref, source_ref])


__all__ = ["PREFIXES", "WIDTH", "normalise", "session_id", "stage_id", "receipt_id", "verdict_id",
           "section_id", "synthesis_id", "evidence_id"]
