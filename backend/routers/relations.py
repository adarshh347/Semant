"""
WAVE4.5 — the derived-relation store's one route.

    GET /api/v1/relations/status    what is derived, what is durable, what is committed,
                                    and which of them the triage rule sends to a curator

ONE route, and read-only. The views that need relations already have their own endpoints — the
scene view, the constellation, the curator queue — and each of them now reads
`backend.services.derived_relations` underneath. What none of them could answer is the question this
lane exists for: **how many relations are there, and how many of them has anybody accepted?**

That question has two numbers and they differ by two orders of magnitude. Reporting one total would
erase the finding, so this route reports them apart:

    derived     rebuildable from the regions, the organs and the depth grid
    durable     written down somewhere — filed proposals, Atlas edges, committed marks
    committed   a person said yes

It also returns the **decision** and the **triage rule** as prose, not only as counts. A number
without the rule that produced it is a number a reader has to trust; with the rule, they can check
it. The rule here is mechanical — queued IFF the relation carries `supersedes` — so "13 of 2,755" is
verifiable by reading the rows rather than by believing this endpoint.

There is no write path in this router. The commit surface is `/api/v1/curator`, where a human is.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.services import derived_relations

router = APIRouter()


class QueuedView(BaseModel):
    """A relation the triage rule selected. Its `supersedes` is included because the rule IS the
    contradiction — a selected row that could not show what it contradicts would be asking to be
    taken on faith."""
    origin: str
    kind: str
    relation: str
    source_node: str
    target_node: str
    basis: str
    organ: str
    epistemic: str | None
    ledger_status: str
    numbers: Dict[str, Any] = Field(default_factory=dict)
    supersedes: Dict[str, Any] | None = None
    ref: str = ""
    detail: str = ""


class StatusResponse(BaseModel):
    #: Counted by origin, by kind, by basis and by ledger status — never as one total.
    census: Dict[str, Any]
    #: The stated rule, what it selected, and what it skipped.
    rule: str
    selected_count: int
    skipped_count: int
    triage_detail: str
    queued: List[QueuedView]
    #: Where the derived side came from — build stamp, kinds, depth grid. A count of 2,755 means
    #: nothing without the parameters that produced it, since a different grid produces a different
    #: count (5 occlusions at 32, 13 at 192).
    cache: Dict[str, Any]
    decision: str


@router.get("/status", response_model=StatusResponse)
async def read_status(
    include_derived: bool = Query(
        default=True,
        description=("false gives the durable world alone — the fourteen the constellation lane "
                     "counted. The gap between the two answers is the finding.")),
    limit: int = Query(default=200, ge=1, le=2000,
                       description="cap on returned queued rows; the counts are never capped"),
):
    """The census, the triage and the decision — in one read, with the rule attached."""
    loaded = await derived_relations.load(include_derived=include_derived)
    rows = loaded["relations"]
    census = derived_relations.census(rows)
    triage = derived_relations.triage(rows)

    return StatusResponse(
        census=census,
        rule=triage["rule"],
        selected_count=triage["selected_count"],
        skipped_count=triage["skipped_count"],
        triage_detail=triage["detail"],
        # Truncated for transport, and the counts above are NOT — a reader can always see that more
        # were selected than are shown, which is the mistake #164 made and had to correct.
        queued=[QueuedView(**{k: v for k, v in row.items() if k in QueuedView.model_fields})
                for row in triage["selected"][:limit]],
        cache=loaded["cache"],
        decision=derived_relations.DECISION,
    )
