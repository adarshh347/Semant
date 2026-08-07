"""
WAVE4 — the society routes: watch agents meet.

    GET /api/v1/society/meeting    several agents at one locus, and the partition between them

READ-ONLY. Nothing here writes a post, a mark, an edge or a hypothesis. The joint hypotheses this
returns are `proposed` and stay that way: composing one is not committing it, and there is no route
in this file that could.

## The meeting is EARNED, and that is why this route walks

`society.convene` refuses a group that did not travel (`meeting.assert_travelled`) and one that did
not perceive on arrival. Those guards are the difference between a meeting and a tableau, so this
route cannot shortcut them by placing agents at the locus — it walks each one there with the
cognition lane's own `walk`, and a group that could not get there returns the reason rather than a
staged encounter.

That also means this surface renders the two lanes joined: every member arrives carrying the walk
the cognition view would have shown, and the encounter is what happens next.

## The serializer trap, and the one field it would ruin here

The curator lane's lesson, and this is the worst place in the system for it. A `MEASURED` default
on a hypothesis's status field would render a `proposed` joint claim as a measurement — the exact
fabrication `dialogue.hydrate_hypothesis` has no code path to produce. So `ledger_status` is
**required and un-defaulted**, and `HypothesisView` has no status field that could be filled in
from anywhere but the hydrator.

`refused_to_hold` rows are modelled the same way: `reason` is required, because a refusal whose
reason can default is a blank, and this one — `wholly_received` — is the finding of the whole
society lane.

## Statuses

    404  no such post, or no such region in it
    409  the group could not be convened — not travelled, not perceived, or not a society
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services import adjacency_organ, chroma_organ, nestedness_organ
from backend.services.agents import cognition, dialogue, meeting, society as soc
from backend.services.agents import movement as mv
from backend.services.agents import situated_agent as sa
from backend.services.agents import temperament as tp
from backend.routers.cognition import _marks_for, _world

router = APIRouter()

#: The bodies this surface convenes, and why these three. Two geometry organs that CAN compose
#: (containment and boundary contact are partial views of one aspect) and one sensory organ that
#: cannot be about the same thing as either — so a single meeting shows `composed`, `coexistent`
#: and `incommensurable` at once rather than needing three requests to demonstrate a partition.
DEFAULT_BODIES: List[Dict[str, str]] = [
    {"organ": nestedness_organ.ORGAN, "temperament": "analogy_seeker"},
    {"organ": adjacency_organ.ORGAN, "temperament": "contact_seeker"},
    {"organ": chroma_organ.ORGAN, "temperament": "depth_seeker"},
]


class HypothesisView(BaseModel):
    """A joint claim two agents composed. NO status field with a default — see the module note."""
    hypothesis_id: str
    claim: str
    agent_ids: List[str]
    about_region_id: Optional[str]
    rests_on: List[Dict[str, Any]]
    ledger_status: str
    marks_live: str
    detail_ledger: str


class RefusalToHoldView(BaseModel):
    agent_id: str
    hypothesis_id: Optional[str]
    claim: Optional[str]
    reason: str
    detail: str


class MeetingView(BaseModel):
    node_id: str
    members: List[Dict[str, Any]]
    verdicts: List[Dict[str, Any]]
    classes: List[List[str]]
    silent: List[str]
    hypotheses: List[HypothesisView]
    held: Dict[str, List[Dict[str, Any]]]
    refusals_to_hold: List[RefusalToHoldView]
    journeys: Dict[str, Any]
    outcomes: Dict[str, int]
    convened: bool
    detail: str


def _hypothesis_view(hypothesis: Dict[str, Any], posts: Dict[str, Any]) -> Dict[str, Any]:
    """Hydrated through `dialogue`'s own hydrator, which has NO path to `measured`.

    Not recomputed here and not defaulted: the hydrator is where this system records that a
    composition stays `proposed` however many of its marks are committed, and a second place
    deciding that is a second place that can stop deciding it.
    """
    hydrated = dialogue.hydrate_hypothesis(hypothesis, posts)
    return {
        "hypothesis_id": hydrated.get("hypothesis_id"),
        "claim": hydrated.get("claim"),
        "agent_ids": list(hydrated.get("agent_ids") or []),
        "about_region_id": hydrated.get("about_region_id"),
        # CONTRIBUTED vs RECEIVED per mark, carried through so the surface can show which half
        # each agent is entitled to rather than presenting a joint claim as one voice.
        "rests_on": list(hydrated.get("rests_on") or []),
        "ledger_status": hydrated["ledger_status"],
        "marks_live": hydrated.get("marks_live") or "0/0",
        "detail_ledger": hydrated.get("detail_ledger") or "",
    }


@router.get("/meeting", response_model=MeetingView)
async def read_meeting(post_id: str = Query(...), region_id: str = "", atlas_id: str = "",
                       steps: int = Query(default=2, ge=1, le=8)):
    """Walk a differently-bodied group to one locus and return what holds between them."""
    post, graph, posts = await _world(post_id, region_id, atlas_id)
    marks = _marks_for(posts)
    region = region_id or str((post.get("region_annotations") or [{}])[0].get("id") or "")

    agents: List[sa.SituatedAgent] = []
    journeys: Dict[str, Any] = {}
    for body in DEFAULT_BODIES:
        agent = sa.inhabit(agent_id=f"agent_{body['organ'].split('_')[0]}",
                           post_id=str(post["_id"]), region_id=region,
                           organ_set=(body["organ"],), temperament=body["temperament"])
        # WALKED, not placed. `convene` refuses a group that did not travel, and shortcutting that
        # here would be staging the meeting this surface exists to show honestly.
        cognition.walk(agent, graph, posts, marks=marks, steps=steps)
        agents.append(agent)
        journeys[agent.id] = meeting.journey(agent)

    try:
        society = soc.convene(agents, atlas_id=atlas_id)
    except (soc.NotASociety, meeting.NotTravelled, meeting.NotHere) as exc:
        # A GROUP THAT COULD NOT MEET, reported as that rather than as an empty meeting. "Nobody
        # travelled far enough" and "they met and nothing composed" are different findings, and a
        # surface that rendered them alike would lose the one that is about the graph.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    body = society.as_dict()
    held = soc.hold_all(society)
    refusals = [r for rows in held.values() for r in soc.refusals_to_hold(rows)]
    outcomes: Dict[str, int] = {}
    for verdict in society.verdicts:
        outcomes[verdict.outcome] = outcomes.get(verdict.outcome, 0) + 1

    return {
        **body,
        "hypotheses": [_hypothesis_view(h, posts) for h in society.hypotheses()],
        "held": {aid: soc.held_beliefs(rows) for aid, rows in held.items()},
        "refusals_to_hold": refusals,
        "journeys": journeys,
        "outcomes": outcomes,
        "convened": True,
        "detail": (
            f"{len(society.members)} agents at {society.node_id}: "
            + ", ".join(f"{n} {k}" for k, n in sorted(outcomes.items()))),
    }


@router.get("/bodies", response_model=List[Dict[str, Any]])
async def read_bodies():
    """The bodies this surface convenes, and the characters they carry. Data, not a hardcoded UI
    list — a page that wrote its own would be a second place they live."""
    return [{**b, "character": (tp.resolve(b["temperament"]).as_dict()
                                if b.get("temperament") else None)}
            for b in DEFAULT_BODIES]
