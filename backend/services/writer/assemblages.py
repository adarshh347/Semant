"""
Semant Writer W4 — assemblage suggestion: the Tier-2 capstone.

Since W1 the system has logged operator usage and co-occurrence; since W3, which operators
were pulled through `requires`. This module finally READS that corpus, and it is the first
time the system proposes something derived from the author's own working. That makes it
the most honesty-delicate part of the Writer, and the discipline is one sentence:

    **The system may propose the cluster because it has evidence.
      The system may not decide what the cluster means.**

BOTH HONESTY MODES APPEAR HERE, AND KEEPING THEM APART IS THE DESIGN.

  THE SUGGESTION IS EVIDENTIAL. "These operators recurred together across 7 blocks" is a
  claim that rests on real logged records, exactly as a mark on the vision side rests on
  detector output. So a suggestion CITES the blocks it rests on — `cite()` builds the
  citation from the actual events, and `suggest()` drops any candidate whose evidence it
  cannot produce. A pattern that cannot point at its records is a fabricated pattern, and
  the correct number of those to show the author is zero.

  THE AUTHORING IS AUTHORIAL. The name and the meaning come from the author. The strawman
  this module drafts is assembled DETERMINISTICALLY from the members' own definitions —
  the author's sentences, rearranged — and there is no model call anywhere in this file.
  That is deliberate and it mirrors `operator_registry.propose()`: asking an LLM what a
  recurring cluster "means" would let priors decide the meaning of the author's own
  recurring images, which is precisely the fabrication the project exists to refuse.

DETECTION IS ANALYSIS, NOT INFERENCE. Frequency and co-occurrence over the log. No model,
no clustering heuristic that cannot be explained to the author in one sentence. If the
count is not there, the suggestion is not there.

WHAT IS NOT COUNTED, AND WHY. Co-occurrence is counted over the operators the author TYPED
together in a block (`direct`), never over operators that arrived by a `requires` edge. An
edge the author already drew makes its two ends co-occur on every single render — counting
that would let the system "discover" a pattern the author declared by hand in W3 and hand
it back as an insight. Pulled operators are still REPORTED in the evidence, because they
are part of what actually happened; they just cannot manufacture a cluster.

THIS MODULE HAS NO ROUTE TO THE CANON. It reads the usage log and the operator registry.
There is no scene, no passage, no block-commit path in it — the same discipline as the W3
graph, and there is a test asserting it.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from backend.database import writer_usage_collection
from backend.services.writer import instrument

#: How many distinct BLOCKS a cluster must recur in before it is worth the author's
#: attention. A tunable, documented number rather than a magic one: two operators landing
#: in one block together is a coincidence, and the whole value of the suggestion is that
#: it only fires on a habit. Raise it if the author finds the feed noisy.
MIN_BLOCKS = 3

#: Cluster sizes considered. Two is the smallest thing that can be a pair-habit; beyond
#: four the combinatorics grow and the suggestion stops being legible to a human anyway.
MIN_MEMBERS = 2
MAX_MEMBERS = 4

#: A dismissed cluster may return only when the evidence has grown substantially — this
#: multiple of the support it had when dismissed. "Do not nag" means the next render must
#: not re-raise it; it does not mean never again if the habit really deepens.
RESURFACE_FACTOR = 2

#: Instrumentation event names. Suggested is NOT recorded (a suggestion the author never
#: saw is not an event), but the author's decisions are.
DISMISSED = "assemblage_dismissed"
AUTHORED = "assemblage_authored"

#: The operator `kind` an assemblage carries. A plain operator is `operator`.
ASSEMBLAGE_KIND = "assemblage"


def cluster_key(members: Iterable[str]) -> str:
    """A stable id for a set of member names, order-independent.

    Dismissals key on this, so `{a,b,c}` dismissed stays dismissed however the detector
    happens to order it next time.
    """
    joined = "|".join(sorted({str(m) for m in members if m}))
    return "asm_" + hashlib.sha1(joined.encode()).hexdigest()[:12]


# ── reading the log ──────────────────────────────────────────────────────────

async def _render_events(project_id: str, limit: int = 5000) -> List[Dict[str, Any]]:
    """Every `render` event for the project, newest first. The raw evidence."""
    out: List[Dict[str, Any]] = []
    try:
        cursor = writer_usage_collection.find(
            {"project_id": project_id, "event": instrument.RENDER}
        ).sort("at", -1)
        async for doc in cursor:
            out.append(doc)
            if len(out) >= limit:
                break
    except Exception:
        return out
    return out


async def _dismissals(project_id: str) -> Dict[str, int]:
    """`cluster_key → the support it had when the author dismissed it`."""
    out: Dict[str, int] = {}
    try:
        cursor = writer_usage_collection.find(
            {"project_id": project_id, "event": DISMISSED}
        ).sort("at", -1)
        async for doc in cursor:
            key = (doc.get("extra") or {}).get("cluster_key")
            if key and key not in out:
                out[key] = int((doc.get("extra") or {}).get("support") or 0)
    except Exception:
        return out
    return out


def blocks_from_events(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Render events → one entry per BLOCK, with what the author typed in it.

    A block is one `run_block` invocation (`run_id`). Events with no `run_id` — anything
    logged before W4 added it — fall back to being their own block, which is honest: they
    record a render that happened, we simply cannot say what else was in the block with it.
    """
    by_run: Dict[str, Dict[str, Any]] = {}
    for e in events:
        extra = e.get("extra") or {}
        run_id = extra.get("run_id") or f"_event:{e.get('_id')}"
        block = by_run.setdefault(run_id, {
            "run_id": run_id,
            "at": e.get("at"),
            "direct": [],
            "pulled": [],
            "directives": [],
            "event_ids": [],
        })
        for name in e.get("operators") or []:
            if name not in block["direct"]:
                block["direct"].append(name)
        for name in extra.get("pulled_operators") or []:
            if name not in block["pulled"]:
                block["pulled"].append(name)
        if extra.get("directive"):
            block["directives"].append(extra["directive"])
        block["event_ids"].append(e.get("_id"))
        # keep the earliest timestamp for the block
        if e.get("at") and block["at"] and e["at"] < block["at"]:
            block["at"] = e["at"]
    return list(by_run.values())


# ── detection ────────────────────────────────────────────────────────────────

def _candidates(blocks: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, ...], List[Dict[str, Any]]]:
    """Every operator subset that appeared together in a block → the blocks it appeared in.

    Counted over `direct` only — see the module docstring on why a `requires` edge must not
    be able to manufacture a cluster.
    """
    support: Dict[Tuple[str, ...], List[Dict[str, Any]]] = {}
    for block in blocks:
        names = sorted(set(block["direct"]))
        if len(names) < MIN_MEMBERS:
            continue
        for size in range(MIN_MEMBERS, min(MAX_MEMBERS, len(names)) + 1):
            for combo in combinations(names, size):
                support.setdefault(combo, []).append(block)
    return support


def _maximal(surviving: Dict[Tuple[str, ...], List[Dict[str, Any]]]) -> List[Tuple[str, ...]]:
    """Drop a cluster that is wholly contained in a larger one with the same support.

    `{a,b}` recurring 4 times is not a separate finding from `{a,b,c}` recurring 4 times —
    it is the same habit seen through a smaller window, and showing both would make one
    pattern look like two.
    """
    keys = sorted(surviving, key=len, reverse=True)
    kept: List[Tuple[str, ...]] = []
    for combo in keys:
        s = set(combo)
        if any(s < set(bigger) and len(surviving[bigger]) == len(surviving[combo])
               for bigger in kept):
            continue
        kept.append(combo)
    return kept


def cite(members: Sequence[str], blocks: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The evidence for a cluster, or None if there is none to show.

    Returning None is the load-bearing case: `suggest()` drops any candidate whose citation
    comes back empty rather than showing an uncited claim. A pattern the system cannot point
    at is one it should not mention.
    """
    cited = [
        {
            "run_id": b["run_id"],
            "at": b["at"].isoformat() if isinstance(b["at"], datetime) else b["at"],
            "directives": list(b["directives"]),
            "event_ids": list(b["event_ids"]),
        }
        for b in blocks
    ]
    if not cited:
        return None
    pulled_in = sum(1 for b in blocks if b["pulled"])
    return {
        "block_count": len(cited),
        "blocks": cited,
        # Reported, never counted — see the module docstring.
        "blocks_with_pulled_operators": pulled_in,
        "threshold": MIN_BLOCKS,
    }


def strawman(members: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """A first draft of the assemblage, built ONLY from the members' own definitions.

    NO MODEL CALL, deliberately — the same decision as `operator_registry.propose()`. The
    author's sentences are rearranged and handed back; nothing is added about what the
    cluster "should" mean, because the moment a prior supplies that, the meaning of the
    author's recurring images stops being theirs.

    It is meant to be edited. The name is a mechanical join, and the intent is the members'
    own intents in sequence — a starting point that is obviously a starting point.
    """
    names = [str(m.get("name", "")) for m in members if m.get("name")]
    parts: List[str] = []
    for m in members:
        own = (m.get("rendering_intent") or "").strip() or (m.get("definition") or "").strip()
        if own:
            parts.append(f"{m.get('name')}: {own}")
    return {
        "name": "_".join(names),
        "rendering_intent": "; ".join(parts),
        # Said plainly so the surface can say it plainly: this is the author's own words
        # put next to each other, not a reading of them.
        "source": "composed from the members' own definitions — rewrite it in your words",
    }


async def suggest(
    project_id: str,
    operators_by_name: Dict[str, Dict[str, Any]],
    *,
    min_blocks: int = MIN_BLOCKS,
) -> List[Dict[str, Any]]:
    """Clusters worth naming, strongest first. Proposes; changes nothing.

    Every returned suggestion carries a citation to the blocks it rests on. A candidate
    that clears the threshold but cannot be cited is dropped, not shown uncited.
    """
    events = await _render_events(project_id)
    blocks = blocks_from_events(events)
    dismissed = await _dismissals(project_id)

    # A cluster already authored as an assemblage is not a finding any more.
    authored: Set[str] = {
        cluster_key([m.get("name") for m in (op.get("members") or [])])
        for op in operators_by_name.values()
        if op.get("kind") == ASSEMBLAGE_KIND and op.get("members")
    }

    support = {k: v for k, v in _candidates(blocks).items() if len(v) >= min_blocks}
    out: List[Dict[str, Any]] = []

    for combo in _maximal(support):
        # Only operators that still exist can be members — a cluster naming a deleted
        # operator is a fact about the past, not something the author can author now.
        if any(name not in operators_by_name for name in combo):
            continue

        key = cluster_key(combo)
        if key in authored:
            continue

        seen_blocks = support[combo]
        if key in dismissed:
            # Respect the dismissal until the evidence has grown substantially.
            if len(seen_blocks) < max(1, dismissed[key]) * RESURFACE_FACTOR:
                continue

        evidence = cite(combo, seen_blocks)
        if not evidence:
            continue          # uncitable → not shown at all

        members = [
            {"name": n,
             "version": operators_by_name[n].get("version"),
             "definition": operators_by_name[n].get("definition", ""),
             "rendering_intent": operators_by_name[n].get("rendering_intent", "")}
            for n in combo
        ]
        out.append({
            "id": key,
            "members": members,
            "support": len(seen_blocks),
            "evidence": evidence,
            "strawman": strawman(members),
        })

    out.sort(key=lambda s: (-s["support"], -len(s["members"]), s["id"]))
    return out


# ── the author's decisions ───────────────────────────────────────────────────

async def dismiss(project_id: str, member_names: Sequence[str], support: int = 0) -> str:
    """Record that the author does not want this cluster. Changes no ontology."""
    key = cluster_key(member_names)
    await instrument.record(
        DISMISSED, project_id, operators=list(member_names),
        extra={"cluster_key": key, "support": int(support or 0)},
    )
    return key


async def record_authored(project_id: str, name: str, member_names: Sequence[str]) -> None:
    """Log the authoring. The seed corpus for anything Tier 3 ever reads."""
    await instrument.record(
        AUTHORED, project_id, operators=[name] + list(member_names),
        extra={"cluster_key": cluster_key(member_names), "members": list(member_names)},
    )
