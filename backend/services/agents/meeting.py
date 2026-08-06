"""WAVE3 — two agents move, then meet: the first emergence earned by travel.

#148 put two agents at one locus and had them compose a claim neither organ could state alone.
#151 gave an agent a horizon and a step. This is the fusion, and the fusion is not a convenience:

    a STAGED meeting   two agents are placed at one locus                      → #148
    an EARNED meeting  two agents each WALK to a locus, and each knows only
                       what its own organs measure at the place it walked to   → here

The difference is what each speaker is entitled to. In a staged meeting an agent's knowledge and
its position were arranged together by the same hand. Here the position was reached along a
crossing the agent verified, and the knowledge was measured after arrival — because `movement.step`
empties the percept field and the horizon, so an agent arrives holding nothing and has to look.

## What is earned, and what is arranged — said plainly, because the difference is the finding

**Earned:** the travel, the arrival, and everything each agent knows at the meeting locus. Neither
agent imports a view across its step; both fields are measured after arrival; every step cites a
measured mask-basis mark the agent checked for itself.

**Arranged:** the meeting point. `rendezvous` computes the destinations BOTH horizons can reach —
that is a fact about the graph, not a choice — and then the harness picks one by a stated rule.
Neither agent can see the other's horizon, neither has a goal, and nothing here gives either one an
interest in being where the other is. Two agents each walking their own rule would meet by
coincidence and essentially never; a lane that pretended otherwise would be staging the arrival and
calling it emergence. So the rendezvous is the observer's act, and it is named as one.

## An agent may walk a road it did not survey

α carries `nestedness_organ` and β carries `adjacency_organ` — they must differ, or the exchange is
two copies of one world (`dialogue.exchange` refuses identical organ sets). But every movement edge
in this corpus is grounded on nestedness, because that is the only relation the kernel grounds. So
β walks a crossing measured by an organ it does not have.

That is the stigmergic claim, and it is legitimate exactly as far as it is stated: the graph is a
trace left in the environment, and a reader of a trace does not have to be able to have made it.
What β does verify for itself is the *ground*, not the road — `movement.footing` asks β's own organ
whether the geometry where it stands is measured, and β's adjacency masks answer that as well as
α's nestedness masks do. A road it did not survey, on ground it checked.

## The joint hypothesis, with the journeys on it

`dialogue.compose` already produces a proposal citing both marks; `dialogue.hold` already records
each agent's private copy as `interpretive` with `contributed` vs `received` per mark
(`DECISION-testimony-is-interpretive`). Neither needed changing. What this lane adds is
`arrived_by`: how each contributor got there, so the stored row reads

    agent alpha (via L0 →1 step→ L1) and agent beta (via L2 →1 step→ L1)
    jointly propose nested_at_boundary at L1

— travel and authorship both visible on the artefact rather than only in a transcript. The
composition is still `proposed`, full stop, and this module contains no path to anything stronger.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.services.agents import dialogue
from backend.services.agents import movement as mv
from backend.services.agents import observation as obs_mod
from backend.services.agents.situated_agent import SituatedAgent, TRAJECTORY_PERCEIVE

#: How many measured crossings an agent must have walked before it may call a meeting *earned*.
#: One, not zero, and the difference is the whole lane: an agent that was already standing there is
#: in a staged meeting, which #148 already built and which this module must not be able to produce
#: by accident.
MIN_STEPS = 1

#: The rendezvous rules. Same shape as `movement.POLICIES` and for the same reason — the rule a
#: meeting was arranged by is a value that goes on the record, not a branch nobody can cite.
#:
#: THESE ARE THE OBSERVER'S RULES, NOT AN AGENT'S. Neither agent sees the other's horizon and
#: neither has an interest in where the other is; naming them here rather than inside `step` is how
#: that stays true. The moment a policy like this lives on the agent, the agent has acquired a goal.
RENDEZVOUS_SUM = "strongest_combined"
RENDEZVOUS_MIN = "strongest_weakest_leg"
RENDEZVOUS_RULES: Dict[str, str] = {
    RENDEZVOUS_SUM: ("meet where the two crossings' systematicity sums highest; ties broken by "
                     "the meeting node id"),
    RENDEZVOUS_MIN: ("meet where the WEAKER of the two crossings is strongest — a meeting is only "
                     "as earned as its worse leg; ties broken by the meeting node id"),
}


class NotTravelled(Exception):
    """A meeting one of the agents did not walk to. Refused, because it is #148 wearing this
    lane's vocabulary — and it would look identical in every transcript."""


class NotHere(Exception):
    """An agent asked to speak from a locus it has not perceived since arriving.

    `movement.step` empties the percept field precisely so that this state exists and is empty
    rather than stale. An agent that spoke from a field it built somewhere else would be reporting
    the image it left under the name of the image it reached, and every sentence would parse.
    """


# ── the rendezvous: a fact about two horizons, chosen by a stated rule ───────

@dataclass(frozen=True)
class Rendezvous:
    """One node both agents can reach, with the crossing each would walk to get there."""
    node_id: str
    post_id: str
    region_id: str
    alpha: mv.Reach
    beta: mv.Reach

    @property
    def combined_systematicity(self) -> float:
        return round(self.alpha.systematicity + self.beta.systematicity, 6)

    @property
    def weakest_leg(self) -> float:
        return min(self.alpha.systematicity, self.beta.systematicity)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "post_id": self.post_id,
            "region_id": self.region_id,
            "combined_systematicity": self.combined_systematicity,
            "weakest_leg": self.weakest_leg,
            "alpha_leg": self.alpha.as_dict(),
            "beta_leg": self.beta.as_dict(),
        }


def rendezvous(alpha: SituatedAgent, beta: SituatedAgent,
               alpha_horizon: Sequence[mv.Reach],
               beta_horizon: Sequence[mv.Reach]) -> List[Rendezvous]:
    """Every node BOTH agents can reach on a measured crossing. Computed, never chosen.

    Only `reachable` rows on either side, so this inherits the whole WAVE2.5 gate rather than
    restating it: a destination one agent can merely *see* is not a place they can meet, and it
    drops out here for the reason `movement.horizon` already recorded on the row.

    A node either agent is ALREADY standing on is excluded. Meeting where one of them already is
    would make that agent's journey zero steps, which is the staged meeting again — and it is
    excluded here as well as refused in `assert_travelled`, because a rendezvous list that offered
    it would be inviting the failure.
    """
    standing = {alpha.locus.node_id, beta.locus.node_id}
    mine = {r.other_node: r for r in alpha_horizon if r.reachable}
    theirs = {r.other_node: r for r in beta_horizon if r.reachable}

    out: List[Rendezvous] = []
    for node_id in sorted((set(mine) & set(theirs)) - standing):
        parsed = mv.parse_node_id(node_id)
        if parsed is None:
            continue
        out.append(Rendezvous(node_id=node_id, post_id=parsed[0], region_id=parsed[1],
                              alpha=mine[node_id], beta=theirs[node_id]))
    return out


def choose(options: Sequence[Rendezvous], *, rule: str = RENDEZVOUS_MIN) -> Optional[Rendezvous]:
    """Pick one meeting by a NAMED rule. `None` when the two horizons do not overlap.

    `RENDEZVOUS_MIN` is the default and it is the more honest of the two: a meeting is only as
    earned as its weaker leg, and summing lets one excellent crossing carry a marginal one into the
    record. Deterministic to the tie-break (`node_id`, a content identity — #151 learned the hard
    way that a freshly minted `edge_id` makes a "stated rule" unrepeatable).
    """
    if rule not in RENDEZVOUS_RULES:
        raise ValueError(
            f"unknown rendezvous rule {rule!r} — a meeting has to be arranged by something a "
            f"reader can look up, and {sorted(RENDEZVOUS_RULES)} are the ones this lane states")
    if not options:
        return None
    if rule == RENDEZVOUS_SUM:
        return max(options, key=lambda r: (r.combined_systematicity, r.node_id))
    return max(options, key=lambda r: (r.weakest_leg, r.combined_systematicity, r.node_id))


# ── what a meeting must prove about each of its participants ────────────────

def steps_of(agent: SituatedAgent) -> List[Dict[str, Any]]:
    return [e for e in agent.trajectory if str(e.get("kind") or "") == mv.TRAJECTORY_STEP]


def assert_travelled(agent: SituatedAgent, *, minimum: int = MIN_STEPS) -> List[Dict[str, Any]]:
    """Raise unless this agent walked here. The one thing that makes the meeting earned."""
    walked = steps_of(agent)
    if len(walked) < int(minimum):
        raise NotTravelled(
            f"agent {agent.id} has walked {len(walked)} measured crossing(s) and this meeting "
            f"requires {minimum}. An agent that was already standing here is in a staged meeting — "
            f"a real thing, built in the dialogue lane, and not this one. The transcripts are "
            f"identical, which is why this is checked rather than arranged for.")
    return walked


def assert_perceived_here(agent: SituatedAgent) -> None:
    """Raise unless this agent's field was measured at the locus it is currently standing in.

    Two failures, one check. A field left EMPTY by a step is an agent that arrived and did not
    look; a field built at the previous locus would be worse, and cannot occur while `step` empties
    it — so this is the guard on that invariant rather than a duplicate of it.
    """
    if not agent.percept_field:
        raise NotHere(
            f"agent {agent.id} stands at {agent.locus.node_id} and has measured nothing here. "
            f"A step empties the field on purpose: arrival is empty, and an agent speaks only "
            f"after it has looked at where it arrived.")
    # AGAINST THE MARK'S POST, not only the region id, and that is not belt-and-braces. Region ids
    # are positional (census §4): `r_rim`, `fine_0`, `cseg_*` recur across images, so a field
    # carried from the previous locus can match on region id alone and read as local. The mark
    # carries the image it was measured in, which is the only part of a reading that cannot recur.
    stale = [p for p in agent.percept_field
             if p.reading.locus_region_id != agent.locus.region_id
             or str(p.mark.get("post_id") or "") != agent.locus.post_id]
    if stale:
        elsewhere = sorted({obs_mod.node_id_for(str(p.mark.get("post_id") or ""),
                                                p.reading.locus_region_id) for p in stale})
        raise NotHere(
            f"agent {agent.id} holds {len(stale)} reading(s) measured at {elsewhere} while "
            f"standing at {agent.locus.node_id} — that is the image it left, wearing the name of "
            f"the image it reached")
    last_look = [e for e in agent.trajectory if str(e.get("kind") or "") == TRAJECTORY_PERCEIVE]
    if not last_look or str(last_look[-1].get("node_id") or "") != agent.locus.node_id:
        raise NotHere(
            f"agent {agent.id}'s most recent perception was not taken at {agent.locus.node_id}")


# ── the journey, as the artefact carries it ─────────────────────────────────

def journey(agent: SituatedAgent) -> Dict[str, Any]:
    """How this agent got to where it is, in the form the hypothesis will carry.

    Built from the trajectory — the one record of where the agent has been — rather than kept
    alongside it, so there is no second copy to disagree. Every leg cites the mark it rested on,
    which is what makes a journey checkable rather than a story about one.
    """
    walked = steps_of(agent)
    legs = [{
        "from_node": e.get("from_node"), "to_node": e.get("to_node"),
        "axis_ref": e.get("axis_ref"), "mark_id": e.get("mark_id"), "basis": e.get("basis"),
        "systematicity": e.get("systematicity"), "policy": e.get("policy"),
        # COPIED off the step, which copied it off the mark. Nothing in this module names a status.
        "epistemic_status": e.get("epistemic_status"),
        "ledger_status": e.get("ledger_status"),
    } for e in walked]
    return {
        "agent_id": agent.id,
        "organ_set": list(agent.organ_set),
        "origin_node": (legs[0]["from_node"] if legs else agent.locus.node_id),
        "arrived_node": agent.locus.node_id,
        "steps": len(legs),
        "legs": legs,
        "crossed_images": len({str(leg["from_node"]).split(":")[0] for leg in legs}
                              | {agent.locus.node_id.split(":")[0]}) if legs else 1,
    }


def earned_hypothesis(hypothesis: Mapping[str, Any],
                      journeys: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """A joint hypothesis + how each contributor arrived → the row this lane stores.

    ADDITIVE ONLY. The dialogue contract is untouched: same required keys, same forbidden keys,
    same `rests_on`, and the result is re-validated through `dialogue.assert_valid_hypothesis` so
    a field added here cannot smuggle past the guard that lane wrote. `arrived_by` is keyed by
    agent id and carries no claim — it is provenance of POSITION, beside the provenance of
    evidence that `rests_on` already carries.

    Nothing about the composition's status changes, and nothing here could change it: a hypothesis
    is `proposed` because `hydrate_hypothesis` has no branch to anything else, and travel is not an
    argument for promoting it. An agent that walked further has not measured more.
    """
    by_agent = {str(j.get("agent_id")): dict(j) for j in journeys}
    contributors = [str(a) for a in (hypothesis.get("agent_ids") or [])]
    missing = [a for a in contributors if a not in by_agent]
    if missing:
        raise NotTravelled(
            f"no journey for {missing} — every agent behind an earned hypothesis has to be able to "
            f"say how it got there, or 'earned' is a word in a docstring")

    out = {**dict(hypothesis), "arrived_by": {a: by_agent[a] for a in contributors}}
    dialogue.assert_valid_hypothesis(out)
    return out


def legible(hypothesis: Mapping[str, Any]) -> str:
    """One sentence with the travel, the authorship and the subject all in it.

    `about_region_id` is in it because without it two hypotheses composed at one meeting read as
    the same sentence twice — which is what the first real run printed, three identical lines for
    three different claims about three different regions.
    """
    arrived = hypothesis.get("arrived_by") or {}
    parts = []
    for agent_id in (hypothesis.get("agent_ids") or []):
        j = arrived.get(str(agent_id)) or {}
        if j.get("steps"):
            parts.append(f"agent {agent_id} (via {j.get('origin_node')} "
                         f"—{j['steps']} step(s)→ {j.get('arrived_node')})")
        else:
            parts.append(f"agent {agent_id} (did not travel)")
    return (f"{' and '.join(parts)} jointly propose {hypothesis.get('claim')} "
            f"about {hypothesis.get('about_region_id')!r} at {hypothesis.get('node_id')} "
            f"— {obs_mod.LEDGER_PROPOSED}")


# ── the meeting ─────────────────────────────────────────────────────────────

def meet(alpha: SituatedAgent, beta: SituatedAgent, *, atlas_id: str = "",
         now: str = "", minimum_steps: int = MIN_STEPS) -> Dict[str, Any]:
    """Two travelled agents at one locus → the exchange, and the hypotheses they earned.

    Every gate here is somebody else's, reused rather than restated:

      · **travelled** — this lane's own, and the only new one.
      · **perceived here** — this lane's, guarding #151's invariant from the outside.
      · **co-located, and differently bodied** — `dialogue.exchange`, which refuses two agents in
        different places (their fields would differ for an uninteresting reason) and two agents
        with the same organ set (they would enact one world twice).
      · **hearsay** — `situated_agent.attest`, through `dialogue.say`.
      · **`proposed`, full stop** — `dialogue.hydrate_hypothesis`, which has no branch to anything
        stronger and does not acquire one because the agents walked.

    Writes nothing.
    """
    stamp = now or obs_mod.utc_now()
    journeys = []
    for agent in (alpha, beta):
        assert_travelled(agent, minimum=minimum_steps)
        assert_perceived_here(agent)
        journeys.append(journey(agent))

    exchange_ = dialogue.exchange(alpha, beta)
    hypotheses = [earned_hypothesis(h, journeys)
                  for h in dialogue.compose(exchange_, atlas_id=atlas_id, now=stamp)]

    held = {a.id: [dialogue.hold(a, h, now=stamp) for h in hypotheses] for a in (alpha, beta)}

    return {
        "at": stamp,
        "locus": alpha.locus.as_dict(),
        "node_id": alpha.locus.node_id,
        "journeys": journeys,
        "exchange": exchange_.as_dict(),
        "hypotheses": hypotheses,
        "held": held,
        "legible": [legible(h) for h in hypotheses],
    }
