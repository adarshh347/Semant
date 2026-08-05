"""WAVE3 — the shared ledger's half: an agent's report, and the status it deliberately does not carry.

`DECISION-measured-private-vs-shared-ledger` draws one line and this module is the far side of it.
An agent's episodic memory may read an organ result as `measured` — it lives on what its organs
measured and does not wait for a human to believe its own eyes. The durable, shared record may not.
It stays **proposed until a curator commits**, and the observation on it is a suggestion.

## How that is made structural rather than promised

An observation row stores `mark_id` and **no epistemic status at all**. `hydrate_observation`
derives what kind of knowing it is from the mark, on every read, exactly the way
`movement_graph.hydrate_movement_edge` derives a movement edge's. So "proposed publicly" is not a
field anyone must remember to set correctly — it is the only thing the row can say until the mark
it cites is in the ledger.

That matters because the flattering failure here is so cheap. Writing `epistemic_status:
"measured"` onto the observation would be one line, would look right in every dump, and would be
indistinguishable from a curator-committed grounding to everything downstream. Lane G refused the
same field on a movement edge for the same reason, and `assert_valid_observation` refuses it here
with the same guard shape — so an agent lane that drifts toward self-certification fails a test
rather than shipping a claim.

## What a reader gets instead

Both readings, never the flattering one alone:

    ledger_status  proposed   — the mark is not in the ledger; this is a suggestion
    ledger_status  measured   — a curator committed the mark, and the observation now rests on it

The gap between them is the human act this wave does not perform.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence
from uuid import uuid4

from backend.services.epistemics import STATUS_KEY

OBSERVATION_CONTRACT_VERSION = 1

#: What the shared ledger reads while the cited mark is uncommitted. NOT an `EpistemicStatus` —
#: deliberately. `measured`/`interpretive`/`visible` answer "how is this known"; `proposed` answers
#: "has anyone accepted it", which is a different question, and minting a sixth status would have
#: put a commitment state into a vocabulary about kinds of knowing.
LEDGER_PROPOSED = "proposed"

#: The `source` every agent observation carries. It sits in `atlas_service.QUARANTINED_SOURCE`'s
#: family — a thing the system proposed, not a thing a person committed — and is a separate string
#: so a reader can tell an agent's report from a model suggestion on a mark.
AGENT_PROPOSED_SOURCE = "agent_proposed"

#: Refused on the way in, for the reason in the module note. `epistemic_status` is the one that
#: matters; the others are here because each would be a second copy of something the ledger already
#: answers, and a copy that can disagree is the drift PROV-001 exists to fight.
_FORBIDDEN_OBSERVATION_KEYS = frozenset({
    STATUS_KEY, "epistemic", "measured", "committed_at", "accepted_by", "provenance",
})


class ObservationRefused(Exception):
    """A malformed observation, caught before it reaches the ledger."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_observation_id() -> str:
    return f"aobs_{uuid4().hex[:12]}"


def node_id_for(post_id: str, region_id: str) -> str:
    """The Atlas node an observation is about.

    The SAME construction `movement_kernel._node_id` uses, and a test asserts the two agree rather
    than trusting this comment: census §4 — `seg_0`/`arch_n` ids are positional and unique only
    within a post, so an endpoint carrying one alone would be silently repointed by the next
    re-dissect. The pair is the identity. An agent's observations and a movement's endpoints have
    to land on the same node or the atlas holds two names for one place.
    """
    return f"vm_{post_id}:{region_id}"


def observation_entry(*, agent_id: str, post_id: str, region_id: str, organ: str,
                      relation: str, direction: str, mark_id: str, detail: str,
                      atlas_id: str = "", now: str = "") -> Dict[str, Any]:
    """One perception → the row the shared ledger stores. A suggestion, and nothing stronger.

    Every field is set explicitly, including the ones whose honest value is empty. That is Lane G's
    declare-and-set rule and it applies for the same reason: a hydrator rebuilds a view from a
    fixed key list, and a field that was never set is dropped on the way out just as surely as one
    that was never stored.
    """
    stamp = now or utc_now()
    entry = {
        "observation_id": new_observation_id(),
        "contract_version": OBSERVATION_CONTRACT_VERSION,
        "agent_id": str(agent_id),
        "atlas_id": str(atlas_id) or None,
        "node_id": node_id_for(str(post_id), str(region_id)),
        "post_id": str(post_id),
        "region_id": str(region_id),
        # WHERE THE AGENT STOOD, carried on the row itself. An observation whose locus can only be
        # recovered by re-running the agent is not a first-person report, it is an anonymous one.
        "locus": {"post_id": str(post_id), "region_id": str(region_id)},
        "organ": str(organ),
        "relation": str(relation),
        "direction": str(direction),
        # THE GROUNDING. Everything about what kind of claim this is comes from here, at read time.
        "mark_id": str(mark_id),
        "detail": str(detail),
        "source": AGENT_PROPOSED_SOURCE,
        "created_at": stamp,
    }
    assert_valid_observation(entry)
    return entry


def assert_valid_observation(obs: Mapping[str, Any]) -> None:
    """Raise unless this row is a well-formed agent observation that claims nothing on its own."""
    missing = [k for k in ("observation_id", "agent_id", "node_id", "post_id", "region_id",
                           "organ", "relation", "mark_id", "source", "created_at")
               if k not in obs]
    if missing:
        raise ObservationRefused(
            f"observation {obs.get('observation_id')!r} is missing {missing} — every field is set "
            "at mint time, because an unset one is dropped by the hydrator and gone")

    forbidden = sorted(k for k in _FORBIDDEN_OBSERVATION_KEYS if k in obs)
    if forbidden:
        raise ObservationRefused(
            f"an agent observation may not carry {forbidden}. What kind of knowing this is comes "
            f"from the mark it cites, read fresh every time — a status stored here would let a "
            f"suggestion present itself as a curator-committed grounding, which is exactly the "
            f"private-certainty-becoming-the-world's-certainty the decision forbids.")

    if not str(obs.get("mark_id") or ""):
        raise ObservationRefused(
            "an observation with no mark cites no measurement — that is hearsay with a timestamp")


# ── hydration: the row says nothing; the mark says everything ────────────────

def find_mark(post: Optional[Mapping[str, Any]], mark_id: str) -> Optional[Dict[str, Any]]:
    """The cited mark, if a curator has committed it to the post. `None` is the common case here."""
    for mark in (post or {}).get("visual_marks") or []:
        if isinstance(mark, Mapping) and str(mark.get("id")) == str(mark_id):
            return dict(mark)
    return None


def hydrate_observation(obs: Mapping[str, Any],
                        posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """One stored observation + the posts → what a reader actually gets.

    `live` is whether the cited mark is in the ledger. `epistemic` is what that mark says it is, or
    `None` — and `None` is not "uncertain", it is "this row cannot currently tell you", which a
    caller must handle rather than fill in. `ledger_status` collapses the pair into the one word a
    human reads, and it is `proposed` for every observation this wave produces.
    """
    mark = find_mark(posts.get(str(obs.get("post_id"))), str(obs.get("mark_id") or ""))
    epistemic = str((mark or {}).get(STATUS_KEY) or "") or None
    live = mark is not None
    return {
        **dict(obs),
        "live": live,
        "epistemic": epistemic,
        "ledger_status": epistemic if (live and epistemic) else LEDGER_PROPOSED,
        "detail_ledger": (
            "the curator committed the mark this observation cites; it now rests on it"
            if live else
            "the mark this observation cites is not in the ledger — the agent measured it, "
            "nobody has accepted it, and the ledger says so"),
    }


# ── persistence ──────────────────────────────────────────────────────────────

def _collection(collection=None):
    if collection is not None:
        return collection
    from backend.database import agent_observation_collection
    return agent_observation_collection


async def write_observation(obs: Mapping[str, Any], *, collection=None) -> Dict[str, Any]:
    """Store one observation. Writes to `agent_observations` and to nothing else — never a post.

    Its own collection rather than an array on the Atlas document, and the reason is the Atlas's
    own discipline: `atlas_collection` "stores ARRANGEMENT ONLY … it holds no percept data
    whatsoever", and `assert_no_percept_data` enforces it on every save path. An agent's report IS
    percept data. Putting it on the canvas would mean weakening that guard from this lane to make
    room for the thing the guard exists to keep out. So the observation lives beside the Atlas and
    points at it by `atlas_id` and `node_id`, the way a movement axis does.
    """
    assert_valid_observation(obs)
    doc = dict(obs)
    await _collection(collection).insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_observations(*, agent_id: str = "", atlas_id: str = "", post_id: str = "",
                            limit: int = 100, collection=None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if agent_id:
        query["agent_id"] = str(agent_id)
    if atlas_id:
        query["atlas_id"] = str(atlas_id)
    if post_id:
        query["post_id"] = str(post_id)
    out: List[Dict[str, Any]] = []
    cursor = _collection(collection).find(query).limit(int(limit))
    async for doc in cursor:
        doc.pop("_id", None)
        out.append(doc)
    return out


def report_view(observations: Sequence[Mapping[str, Any]],
                posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """A whole report, hydrated. What a reader of the blackboard sees."""
    return [hydrate_observation(o, posts) for o in observations]
