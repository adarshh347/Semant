"""WAVE3 — the curator surface: the door the architecture has been holding open since Lane M.

Every lane in this system ends the same way. The organ measures, the agent reports, the kernel
grounds — and then the mark is **returned, never committed**, because
`DECISION-measured-private-vs-shared-ledger` says the durable record stays `proposed` until a
curator commits it. Ten lanes have written that sentence. **Nobody built the curator.**

So the system now holds a body of proposed knowledge with no way to accept any of it: 13 measured
occlusions from the sweep, grounded movement edges, joint hypotheses, agent observations. The
decision says *"an agent's certainty is its own; the world's certainty requires a human"* — and the
human has had no door. This is the door.

    propose      a producer files a mark it measured           `file_proposal`
    review       a curator reads the queue with its evidence   `queue`
    commit       a human accepts one                           `commit`  ← the only status change

## Why there had to be a queue at all

A proposal in this system is an **uncommitted mark**. Nothing durable held one: every lane produced
marks into a transcript and dropped them when the process exited. So "review the proposals" was not
a missing view over existing data — the data did not exist. `curator_proposals` is that store, and
it is the smallest thing that makes the seam operable: it holds the mark a producer measured, what
it is about, and who filed it. It does not hold a status.

## The one rule this module has: no status is stored, and commit is the only thing that moves one

A proposal row carries **no `epistemic_status` and no `committed` flag** — `assert_valid_proposal`
refuses both, the same guard `movement_graph` puts on an edge and `observation` on an agent's
report, for the same reason. What kind of knowing the item is comes off its MARK; whether the world
has accepted it comes off whether that mark is in the post's ledger. Both are derived on every read
by `hydrate_proposal`.

That is what makes "nothing auto-commits" structural rather than promised. There is no field to set
and no code path that sets one: the only way an item becomes committed is `commit()`, which appends
the mark to the post — and a reader looking at the ledger afterwards sees it because it is *there*,
not because a boolean says so.

## The commit writes to a post, and that is not a violation of suggestions-only

Worth stating plainly, because "posts byte-identical" is the invariant every prior lane checked and
this is the lane that breaks it — deliberately, and in exactly one way.

**In this codebase the ledger IS `post.visual_marks`.** Every `hydrate_*` in the system reads marks
from there; there is no separate ledger collection to write to instead. So committing a mark means
appending it to a post, and a curator surface that did not do that would be a surface that cannot
commit anything.

What is preserved is the discipline underneath the invariant:

  · **`$push`, never `$set`.** A replace on `visual_marks` has already destroyed committed regions
    in this codebase — twenty-four became twenty-two, from a producer writing back a list assembled
    from stale state. An append cannot do that, and there is no read here to go stale.
  · **No other field of the post is touched**, and `test_a_commit_appends_one_mark_and_changes_
    nothing_else` hashes every other field before and after.
  · **One mark per commit**, by id, from the queue.

## What this module does NOT do

It does not judge. There is no scoring, no ranking by confidence, no auto-accept above a threshold,
and no filter that hides a weak proposal — the curator's taste is the value function, and a surface
that pre-sorted by its own opinion of quality would be substituting for it. The queue is filed
order; the evidence is the producer's own numbers; the decision is a person's.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence
from uuid import uuid4

from backend.services.epistemics import STATUS_KEY

PROPOSAL_CONTRACT_VERSION = 1

#: What the ledger reads while the proposed mark is not in it. NOT an `EpistemicStatus` — the five
#: statuses answer "how is this known" and this answers "has anyone accepted it", which is a
#: different question. The same string `observation.LEDGER_PROPOSED` uses, because a reader
#: scanning both surfaces must not have to learn two words for one state.
LEDGER_PROPOSED = "proposed"

#: And what it reads once a curator has committed it: whatever the MARK says. There is no third
#: word — `committed` is a fact about the ledger, not a kind of knowing, and rendering it as a
#: status would put a commitment state into the epistemic vocabulary.
LEDGER_COMMITTED = "committed"

#: Refused on the way in. `epistemic_status` for the reason in the module note; the rest because
#: each would be a second copy of something the ledger already answers, and a copy that can
#: disagree is the drift PROV-001 exists to fight.
_FORBIDDEN_PROPOSAL_KEYS = frozenset({
    STATUS_KEY, "epistemic", "committed", "accepted", "status", "ledger_status",
})


class ProposalRefused(Exception):
    """A malformed proposal, caught before it reaches the queue."""


class CommitRefused(Exception):
    """A commit that cannot be performed. Raised, never silently skipped — a commit that did
    nothing and said nothing is the worst outcome available here, because the curator would
    believe they had accepted something."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_proposal_id() -> str:
    return f"prop_{uuid4().hex[:12]}"


# ── filing ──────────────────────────────────────────────────────────────────

def proposal_entry(*, mark: Mapping[str, Any], post_id: str, producer: str, kind: str,
                   subject: Mapping[str, Any], evidence: Mapping[str, Any],
                   filed_by: str = "", now: str = "") -> Dict[str, Any]:
    """One measured-but-uncommitted mark → the row the queue stores.

    `evidence` is the producer's OWN numbers, carried verbatim and never recomputed here. A curator
    deciding whether to accept an occlusion needs the ordering statistic, the depth grid it was
    read at, and the containment it contradicts — and a surface that summarised those into a score
    would be making the judgement it exists to present.

    Every field is set explicitly, including the ones whose honest value is empty: a hydrator
    rebuilds a view from a fixed key list, and a field never set is dropped on the way out just as
    surely as one never stored.
    """
    stamp = now or utc_now()
    mark_id = str((mark or {}).get("id") or "")
    if not mark_id:
        raise ProposalRefused(
            "a proposal with no mark cites no measurement — that is a suggestion with a timestamp, "
            "and committing it would put an unmeasured claim in the ledger")

    entry = {
        "proposal_id": new_proposal_id(),
        "contract_version": PROPOSAL_CONTRACT_VERSION,
        "kind": str(kind),
        "producer": str(producer),
        "post_id": str(post_id),
        "mark_id": mark_id,
        # THE MARK ITSELF, carried whole. The queue is the only place it exists until a curator
        # commits it: the producing run has exited and its transcript is gone. A queue holding only
        # an id would be a queue of pointers to nothing.
        "mark": dict(mark),
        "subject": dict(subject),
        "evidence": dict(evidence),
        "filed_by": str(filed_by),
        "filed_at": stamp,
        # Set at commit time and nowhere else. `None` here is not a status — it is the absence of a
        # human act, which is exactly what a proposal is.
        "committed_at": None,
        "committed_by": None,
    }
    assert_valid_proposal(entry)
    return entry


def assert_valid_proposal(proposal: Mapping[str, Any]) -> None:
    """Raise unless this row is a well-formed proposal that claims nothing on its own."""
    missing = [k for k in ("proposal_id", "kind", "producer", "post_id", "mark_id", "mark",
                           "filed_at") if k not in proposal]
    if missing:
        raise ProposalRefused(
            f"proposal {proposal.get('proposal_id')!r} is missing {missing} — every field is set "
            "at file time, because an unset one is dropped by the hydrator and gone")

    forbidden = sorted(k for k in _FORBIDDEN_PROPOSAL_KEYS if k in proposal)
    if forbidden:
        raise ProposalRefused(
            f"a proposal may not carry {forbidden}. What kind of knowing it is comes from the mark "
            f"it holds; whether the world has accepted it comes from whether that mark is in the "
            f"ledger. A status stored here would let a proposal present itself as committed "
            f"knowledge, which is the one thing this surface exists to make impossible.")

    if not str((proposal.get("mark") or {}).get("id") or ""):
        raise ProposalRefused("the carried mark has no id — nothing could ever be committed")


# ── hydration: the row says nothing; the mark and the ledger say everything ──

def find_mark(post: Optional[Mapping[str, Any]], mark_id: str) -> Optional[Dict[str, Any]]:
    for mark in (post or {}).get("visual_marks") or []:
        if isinstance(mark, Mapping) and str(mark.get("id")) == str(mark_id):
            return dict(mark)
    return None


def hydrate_proposal(proposal: Mapping[str, Any],
                     posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """One stored proposal + the posts → what a curator actually sees.

    THE THREE THINGS THAT MUST STAY DISTINCT, and the reason this function has no shortcut:

        epistemic      what the PRODUCER measured — `measured`, `interpretive`. Off the mark.
        ledger_status  whether a HUMAN has accepted it — `proposed` or `committed`. Off the post.
        live           whether the mark is findable in the ledger at all.

    A measured mark that nobody has committed reads `measured` **and** `proposed`, and those are
    not in tension: the organ is sure and the world has not agreed yet. Collapsing them — rendering
    a measured proposal as though it were accepted — is the failure this whole surface exists to
    prevent, and it is one line away in any serializer that fills a default in.
    """
    mark = find_mark(posts.get(str(proposal.get("post_id"))), str(proposal.get("mark_id") or ""))
    carried = dict(proposal.get("mark") or {})
    live = mark is not None
    # From the mark in the LEDGER when there is one, else from the mark the queue carries. They are
    # the same object either way; reading the committed copy first means a curator who edited a
    # mark on the way in cannot have the queue's version reported back as what the world holds.
    epistemic = str((mark or carried).get(STATUS_KEY) or "") or None

    return {
        **dict(proposal),
        "live": live,
        "epistemic": epistemic,
        "ledger_status": LEDGER_COMMITTED if live else LEDGER_PROPOSED,
        "detail_ledger": (
            "a curator committed this mark; the ledger holds it and every reader of the ledger "
            "now sees it" if live else
            "this mark is not in the ledger. The producer measured it, nobody has accepted it, "
            "and until somebody does it is a proposal — however strong the evidence under it"),
    }


def queue_view(proposals: Sequence[Mapping[str, Any]],
               posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The whole queue, hydrated. FILED ORDER, and deliberately not sorted by anything.

    A queue ranked by the producer's own confidence would be the surface telling the curator what
    to look at first, which is the beginning of the surface deciding. The evidence is on every row;
    the ordering is the order things arrived.
    """
    return [hydrate_proposal(p, posts) for p in proposals]


# ── persistence ─────────────────────────────────────────────────────────────

def _collection(collection=None):
    if collection is not None:
        return collection
    from backend.database import curator_proposal_collection
    return curator_proposal_collection


async def file_proposal(proposal: Mapping[str, Any], *, collection=None) -> Dict[str, Any]:
    """Store one proposal. Writes to `curator_proposals` and nothing else — never a post.

    Filing is NOT committing and this function cannot become one: it does not take a post
    collection and has no way to reach one.
    """
    assert_valid_proposal(proposal)
    doc = dict(proposal)
    await _collection(collection).insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_proposals(*, kind: str = "", post_id: str = "", producer: str = "",
                         committed: Optional[bool] = None, limit: int = 200,
                         collection=None) -> List[Dict[str, Any]]:
    """The queue, filtered by the facts a curator filters on. `committed` reads the timestamp,
    which is the only durable trace a commit leaves on this row."""
    query: Dict[str, Any] = {}
    if kind:
        query["kind"] = str(kind)
    if post_id:
        query["post_id"] = str(post_id)
    if producer:
        query["producer"] = str(producer)
    if committed is True:
        query["committed_at"] = {"$ne": None}
    elif committed is False:
        query["committed_at"] = None

    out: List[Dict[str, Any]] = []
    async for doc in _collection(collection).find(query).limit(int(limit)):
        doc.pop("_id", None)
        out.append(doc)
    return out


async def get_proposal(proposal_id: str, *, collection=None) -> Optional[Dict[str, Any]]:
    doc = await _collection(collection).find_one({"proposal_id": str(proposal_id)})
    if doc is not None:
        doc.pop("_id", None)
    return doc


# ── the commit: the only thing in this system that changes durable status ───

async def commit(proposal_id: str, *, curator: str, now: str = "",
                 collection=None, posts=None) -> Dict[str, Any]:
    """A human accepts one proposal. THE SEAM.

    Appends the proposal's mark to its post's `visual_marks` with `$push`, and stamps the proposal
    with who committed it and when. After this, every `hydrate_*` in the system finds the mark and
    reports what it says — no downstream code changes, because they all already derive their status
    from the ledger and have been reading `proposed` only because the mark was absent.

    `curator` is REQUIRED and must be a name. An anonymous commit is a claim in the ledger that
    nobody stands behind, and the whole justification for this surface is that a person did.

    Refuses rather than repeating itself: committing twice would put the same mark in the ledger
    twice, and a later reader counting relations would find two where a curator accepted one.
    """
    stamp = now or utc_now()
    who = str(curator or "").strip()
    if not who:
        raise CommitRefused(
            "a commit needs a curator. The private-vs-ledger decision turns on a person having "
            "accepted this, and an unattributed commit is the ledger asserting something on "
            "nobody's authority")

    proposal = await get_proposal(proposal_id, collection=collection)
    if proposal is None:
        raise CommitRefused(f"no proposal {proposal_id!r}")
    if proposal.get("committed_at"):
        raise CommitRefused(
            f"proposal {proposal_id!r} was committed at {proposal['committed_at']} by "
            f"{proposal.get('committed_by')!r}. Committing again would put the same mark in the "
            f"ledger twice and a later reader would count two where one was accepted.")

    from backend.services.atlas_relation import commit_relation_to_posts

    mark = dict(proposal.get("mark") or {})
    # The mark is written EXACTLY as the producer measured it, with two additions that are facts
    # about the acceptance rather than about the measurement. Nothing here touches
    # `epistemic_status`: a curator's act makes a claim durable and cannot make an estimate into a
    # measurement (the WAVE2.5 ruling, applied to the human).
    provenance = dict(mark.get("provenance") or {})
    provenance["committed_by"] = who
    provenance["committed_at"] = stamp
    mark["provenance"] = provenance

    written = await commit_relation_to_posts(mark, [str(proposal["post_id"])], collection=posts)
    if not written:
        raise CommitRefused(
            f"post {proposal['post_id']!r} was not found, so the mark went nowhere. Nothing was "
            f"changed and this proposal is still open — a commit that silently wrote nothing "
            f"would leave a curator believing they had accepted something")

    await _collection(collection).update_one(
        {"proposal_id": str(proposal_id)},
        {"$set": {"committed_at": stamp, "committed_by": who}})

    return {**proposal, "committed_at": stamp, "committed_by": who,
            "written_to": written, "mark": mark}
