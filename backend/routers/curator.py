"""
WAVE3 — the curator routes: review what was proposed, and commit what you accept.

    GET  /api/v1/curator/queue                 the proposals, with their evidence and both statuses
    GET  /api/v1/curator/queue/{proposal_id}   one proposal
    POST /api/v1/curator/queue/{id}/commit     a human accepts it — the only status change here

THE COMMIT IS THE ONLY WRITE, and it is the only route in this system that appends to a post's
ledger. Both GETs are pure reads; there is no bulk-commit, no accept-all, and no threshold above
which anything is taken automatically. That absence is the design: the curator's taste is the value
function, and a route that accepted things on a score would be substituting its own.

## The serializer trap, and why the read models look the way they do

A response model with a defaulted status field is how `proposed` becomes `measured` without anybody
writing the word. FastAPI builds the response from the model, so a field the handler never set is
filled in from its default and rendered as though it were data — the same failure the writer lane
hit with `response_model` ignoring `exclude_unset`, and the `TextBlock.origin` failure one wave
before that.

So the two fields that carry status here are **required and un-defaulted**:

    epistemic      Optional[str]   what the producer measured. `None` is a real answer.
    ledger_status  str             `proposed` until a human commits. No default.

`hydrate_proposal` computes both from the mark and the ledger on every read, and
`test_the_read_path_never_renders_proposed_as_measured` pins both directions through the real
route.

## Statuses

    404  no such proposal
    409  already committed, or the post it names is gone — the commit did not happen and says so
    400  a commit with no curator named
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services import curator

router = APIRouter()


class ProposalView(BaseModel):
    """One proposal as a curator sees it.

    NOTHING HERE HAS A STATUS DEFAULT. `ledger_status` is required, so a handler that forgot to
    hydrate fails loudly instead of rendering the model's idea of the answer; `epistemic` is
    `Optional` with no default for the same reason, and `None` means "this row cannot currently
    tell you" rather than `uncertain`.
    """
    proposal_id: str
    kind: str
    producer: str
    post_id: str
    mark_id: str
    subject: Dict[str, Any] = Field(default_factory=dict)
    # THE PRODUCER'S OWN NUMBERS, passed through untouched. A curator judging an occlusion needs
    # the ordering statistic and the grid it was read at; this route summarises neither.
    evidence: Dict[str, Any] = Field(default_factory=dict)
    filed_by: str = ""
    filed_at: str
    committed_at: Optional[str]
    committed_by: Optional[str]
    # ── the two statuses, kept apart ──
    epistemic: Optional[str]
    ledger_status: str
    live: bool
    detail_ledger: str


class QueueResponse(BaseModel):
    proposals: List[ProposalView]
    total: int
    #: What the queue is filtered to, echoed back — a caller looking at four rows should be able to
    #: tell "four proposals exist" from "four match this filter".
    filter: Dict[str, Any]


class CommitRequest(BaseModel):
    """`curator` is required by the service, not merely by this model — an anonymous commit is a
    claim in the ledger that nobody stands behind."""
    curator: str
    note: str = ""


class CommitResponse(BaseModel):
    proposal_id: str
    committed_by: str
    committed_at: str
    mark_id: str
    post_id: str
    written_to: List[str]
    ledger_status: str
    epistemic: Optional[str]
    detail: str


async def _posts_for(proposals) -> Dict[str, Dict[str, Any]]:
    """The posts the queue's proposals name, for hydration. Read-only."""
    from bson.errors import InvalidId
    from bson.objectid import ObjectId

    from backend.database import post_collection

    out: Dict[str, Dict[str, Any]] = {}
    for post_id in {str(p.get("post_id") or "") for p in proposals} - {""}:
        try:
            doc = await post_collection.find_one({"_id": ObjectId(post_id)})
        except (InvalidId, TypeError):
            doc = None
        if doc is None:
            doc = await post_collection.find_one({"_id": post_id})
        if doc is not None:
            out[post_id] = doc
    return out


@router.get("/queue", response_model=QueueResponse)
async def read_queue(kind: str = "", post_id: str = "", producer: str = "",
                     committed: Optional[bool] = None,
                     limit: int = Query(default=200, ge=1, le=1000)):
    """The proposals awaiting a human, in FILED ORDER.

    Not sorted by the producer's confidence, and that is deliberate: a queue ranked by the
    evidence's own strength is the surface telling the curator what matters, which is the judgement
    it exists to present rather than to make.
    """
    proposals = await curator.list_proposals(kind=kind, post_id=post_id, producer=producer,
                                             committed=committed, limit=limit)
    posts = await _posts_for(proposals)
    return QueueResponse(
        proposals=[ProposalView(**row) for row in curator.queue_view(proposals, posts)],
        total=len(proposals),
        filter={"kind": kind or None, "post_id": post_id or None,
                "producer": producer or None, "committed": committed, "limit": limit})


@router.get("/queue/{proposal_id}", response_model=ProposalView)
async def read_proposal(proposal_id: str):
    proposal = await curator.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"no proposal {proposal_id!r}")
    posts = await _posts_for([proposal])
    return ProposalView(**curator.hydrate_proposal(proposal, posts))


@router.post("/queue/{proposal_id}/commit", response_model=CommitResponse)
async def commit_proposal(proposal_id: str, body: CommitRequest):
    """A human accepts one proposal, and the ledger changes. The only write in this router.

    After this the mark is in the post's `visual_marks` and every reader in the system finds it —
    the movement edges, the agent observations, the joint hypotheses all already derive their
    status from the ledger and have been reading `proposed` only because the mark was absent.
    Nothing downstream needed changing; they were waiting for this.
    """
    try:
        committed = await curator.commit(proposal_id, curator=body.curator)
    except curator.CommitRefused as exc:
        message = str(exc)
        if message.startswith("no proposal"):
            raise HTTPException(status_code=404, detail=message) from exc
        if "needs a curator" in message:
            raise HTTPException(status_code=400, detail=message) from exc
        raise HTTPException(status_code=409, detail=message) from exc

    posts = await _posts_for([committed])
    view = curator.hydrate_proposal(committed, posts)
    return CommitResponse(
        proposal_id=committed["proposal_id"],
        committed_by=committed["committed_by"], committed_at=committed["committed_at"],
        mark_id=committed["mark_id"], post_id=committed["post_id"],
        written_to=list(committed.get("written_to") or []),
        ledger_status=view["ledger_status"], epistemic=view["epistemic"],
        detail=(f"{committed['committed_by']} committed {committed['mark_id']} to post "
                f"{committed['post_id']}. It reads {view['epistemic']!r} on the ledger now — the "
                f"kind of knowing is the producer's and did not change; what changed is that a "
                f"person accepted it."))
