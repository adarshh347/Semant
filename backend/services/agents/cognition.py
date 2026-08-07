"""
WAVE4 — the lived-cognition view: an agent's walk, made legible without being narrated.

Agents inhabit, perceive, move by disposition and report, and until now there was no way to WATCH
one. This module turns a walk into a stream a person can read: the loci it stood in, what it
measured at each, **what it could not** and why, and what it proposed.

## Refusals are the content, not the gaps between it

The temptation on a viewing surface is to render what was found and leave the rest blank. That is
the opposite of what this system is for. An agent that measured three nestings and refused eleven
crossings has told you far more with the eleven — a blank says "nothing here", and a refusal says
"something here I could not stand on, and here is the word for why".

So every refusal carries its own reason, and the reasons stay DECOMPOSED — the discipline
`movement` keeps for the same reason Lane M keeps `box_only` and `surface_only` apart:

    closed / no_mark / mark_misstated      the EDGE cannot be walked
    interpretive_basis                     it is grounded on an estimate
    mark_measures_elsewhere                its mark is about another pair
    unperceived / box_footing              the TRAVELLER is not standing well enough to leave

A single "refused: 11" would hide which world the refusals are about, and this view would become a
progress bar.

## No narrated arrival

`movement.step` empties the percept field on arrival, because everything the agent knew was
knowledge from where it was standing. A view that filled the destination in — from the post, from
the graph, from anywhere — would be showing the agent a world it had not looked at yet. So a step's
`arrived_with` is explicitly `0 perceptions`, said rather than omitted, and the next locus's
readings appear only after it perceives there.

## Temperament biases the route and never the reading

The bright line the temperament lane drew, made visible here. `signature()` reduces an agent's
percept field to what it MEASURED, with no trace of who measured it — so two characters at one
locus produce byte-identical signatures and visibly different paths. The view renders both, and
`compare()` is the thing a test can hold to it.

PURE. No database, no network, no model. An agent and its trajectory in, a view out.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.agents import movement as mv
from backend.services.agents import temperament as tp
from backend.services.agents.situated_agent import SituatedAgent
from backend.services.epistemics import STATUS_KEY

#: What a refusal is ABOUT. The two families `movement` already keeps apart, named here so the
#: surface can group them without re-deriving the distinction from the reason strings.
ABOUT_THE_EDGE = "edge"
ABOUT_THE_TRAVELLER = "traveller"

_EDGE_REASONS = {
    mv.UNREACHABLE_CLOSED: "the crossing is closed",
    mv.UNREACHABLE_NO_MARK: "no mark stands behind it",
    mv.UNREACHABLE_MISSTATED: "its mark claims more than its basis supports",
    mv.UNREACHABLE_INTERPRETIVE: "it is grounded on an estimate, not a measurement",
    mv.UNREACHABLE_ELSEWHERE: "its mark measures a different pair",
}
_TRAVELLER_REASONS = {
    mv.UNFOOTED_UNPERCEIVED: "the agent has not perceived the locus this edge leaves from",
    mv.UNFOOTED_BOX: "the agent's own footing is a box — an estimate cannot carry a crossing",
}

#: Plain-language glosses, kept beside the constants rather than in the frontend. A surface that
#: wrote its own sentences for these would be a second vocabulary, and the one that drifted would
#: be the one a human actually reads.
REFUSAL_GLOSS: Dict[str, str] = {**_EDGE_REASONS, **_TRAVELLER_REASONS}


def refusal_about(reason: str) -> str:
    """Whether this refusal is a fact about the edge or about the traveller."""
    return ABOUT_THE_TRAVELLER if str(reason) in _TRAVELLER_REASONS else ABOUT_THE_EDGE


def signature(agent: SituatedAgent) -> List[Tuple[str, ...]]:
    """What this agent MEASURED, with nothing about who measured it.

    The bright line, as a value. Two temperaments at one locus must produce identical signatures —
    temperament biases which edge is taken and which readings are attended to first, and touches no
    organ. Sorted so ordering cannot smuggle in a difference; `attend` reorders a field and this
    must not see it.
    """
    return sorted(
        (str(p.organ), str(p.reading.relation), str(p.reading.direction),
         str(p.reading.other_region_id), str(p.reading.basis), str(p.epistemic_status))
        for p in agent.percept_field)


def perceptions_at(agent: SituatedAgent) -> List[Dict[str, Any]]:
    """The agent's current field, as rows a surface can render. Status is copied, never chosen."""
    return [{
        "organ": p.organ,
        "relation": p.reading.relation,
        "direction": p.reading.direction,
        "other_region_id": p.reading.other_region_id or None,
        "basis": p.reading.basis,
        "admissible": p.reading.admissible,
        # OFF THE MARK. The organ is the only thing entitled to say what kind of knowing this is,
        # and a view that restated it would be a second place for it to be wrong.
        "epistemic": p.epistemic_status,
        "detail": p.reading.detail,
        "expression": p.reading.expression,
        "mark_id": str(p.mark.get("id") or ""),
    } for p in agent.percept_field]


def horizon_at(entries: Sequence[mv.Reach]) -> Dict[str, Any]:
    """The horizon at one locus, split into what could be walked and what could not — with reasons.

    Both halves are returned. A view that showed only the reachable would make an agent hemmed in
    by eleven refusals look identical to one standing in an empty world.
    """
    reachable, refused = [], []
    for entry in entries:
        row = {
            "to_node": entry.other_node,
            "axis_ref": entry.axis_ref,
            "edge_id": entry.edge_id,
            "relation": entry.relation or None,
            "basis": entry.basis or None,
            "systematicity": entry.edge.get("systematicity"),
            "detail": entry.detail,
        }
        if entry.reachable:
            reachable.append({**row, "mark_id": entry.mark_id,
                              "epistemic": (entry.mark or {}).get(STATUS_KEY),
                              "ledger_status": entry.ledger_status})
        else:
            reason = str(entry.reason or "")
            refused.append({**row, "reason": reason,
                            "about": refusal_about(reason),
                            "gloss": REFUSAL_GLOSS.get(reason, "refused")})
    return {
        "reachable": reachable,
        "refused": refused,
        # COUNTED SEPARATELY per family, so "hemmed in by its own footing" and "hemmed in by the
        # graph" never collapse into one number.
        "tally": {
            "reachable": len(reachable),
            "refused_edge": sum(1 for r in refused if r["about"] == ABOUT_THE_EDGE),
            "refused_traveller": sum(1 for r in refused if r["about"] == ABOUT_THE_TRAVELLER),
        },
    }


def step_view(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """One trajectory entry, as a crossing a reader can check.

    `arrived_with` is stated rather than omitted. `movement.step` empties the percept field on
    arrival — everything the agent knew was knowledge from where it stood — and a view that left
    that implicit invites the reader to assume a destination was seen.
    """
    return {
        "from_node": entry.get("from_node"),
        "to_node": entry.get("to_node"),
        # THE HONEST TOUCH the depth lane earned: a step within one picture is a real move, and
        # rendering it as a cross-image analogy would misdescribe what the agent did.
        "crossed_image": bool(entry.get("crossed_image")),
        "kind": ("between pictures" if entry.get("crossed_image") else "within one picture"),
        "axis_ref": entry.get("axis_ref"),
        "relation": entry.get("relation"),
        "mark_id": entry.get("mark_id"),
        "basis": entry.get("basis"),
        "epistemic": entry.get(STATUS_KEY),
        "ledger_status": entry.get("ledger_status"),
        "systematicity": entry.get("systematicity"),
        "ordering": entry.get("ordering"),
        "policy": entry.get("policy"),
        "rule": entry.get("rule"),
        "arrived_with": 0,
        "arrival_detail": ("arrived with an empty field — everything it knew was knowledge from "
                           "where it stood, and it is not standing there any more"),
        "detail": entry.get("detail"),
    }


def compare(views: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Two or more walks from one locus → did they measure the same world, and did they diverge?

    The two questions are deliberately separate. Identical measurements with different routes is
    the temperament lane's whole finding; the same answer to both would mean either that character
    does nothing or that it reaches into the organs.
    """
    signatures = [tuple(tuple(row) for row in (v.get("first_signature") or [])) for v in views]
    firsts = [(v.get("steps") or [{}])[0].get("to_node") for v in views]
    return {
        "measurements_identical": len(set(signatures)) <= 1,
        "readings_each": {str(v.get("temperament") or "none"): len(v.get("first_signature") or [])
                          for v in views},
        "first_destinations": {str(v.get("temperament") or "none"): d
                               for v, d in zip(views, firsts)},
        "diverged": len({d for d in firsts if d}) > 1,
        "detail": ("temperament biases the route and never the reading: identical signatures, "
                   "different destinations" if len(set(signatures)) <= 1 and
                   len({d for d in firsts if d}) > 1 else
                   "the two walks did not diverge here"),
    }


def walk_view(agent: SituatedAgent, *, stations: Sequence[Mapping[str, Any]],
              proposals: Sequence[Mapping[str, Any]] = ()) -> Dict[str, Any]:
    """The whole walk, as the stream the surface renders.

    A STATION is one stop: where the agent stood, what it perceived there, and what its horizon
    offered and refused. The steps between them come from the trajectory, so there is exactly one
    record of where the agent has been.
    """
    steps = [step_view(e) for e in agent.trajectory if e.get("kind") == mv.TRAJECTORY_STEP]
    character = tp.resolve(agent.temperament) if agent.temperament else None
    first = list(stations)[0] if stations else {}

    return {
        "agent_id": agent.id,
        "temperament": agent.temperament or None,
        "character": character.as_dict() if character else None,
        "organ_set": list(agent.organ_set),
        "stations": list(stations),
        "steps": steps,
        "proposals": list(proposals),
        "first_signature": first.get("signature") or [],
        "tally": {
            "stations": len(stations),
            "steps": len(steps),
            "within_one_picture": sum(1 for s in steps if not s["crossed_image"]),
            "between_pictures": sum(1 for s in steps if s["crossed_image"]),
            "perceived": sum(len(s.get("perceptions") or []) for s in stations),
            "refused": sum(len(((s.get("horizon") or {}).get("refused")) or [])
                           for s in stations),
            "proposed": len(proposals),
        },
    }


def station(agent: SituatedAgent, entries: Sequence[mv.Reach], *,
            index: int = 0) -> Dict[str, Any]:
    """One stop on the walk: where it stood, what it measured, what its horizon offered."""
    return {
        "index": index,
        "node_id": agent.locus.node_id,
        "post_id": agent.locus.post_id,
        "region_id": agent.locus.region_id,
        "perceptions": perceptions_at(agent),
        "horizon": horizon_at(entries),
        "signature": [list(row) for row in signature(agent)],
    }


# ── the walk itself ─────────────────────────────────────────────────────────

def walk(agent: SituatedAgent, graph: Mapping[str, Any], posts: Mapping[str, Any], *,
         marks: Sequence[Mapping[str, Any]] = (), steps: int = 3,
         policy: str = mv.POLICY_SYSTEMATICITY, now: str = "") -> Dict[str, Any]:
    """Perceive, look, step, repeat — recording the stream at every stop. Writes nothing.

    The loop is deliberately the same one `scripts/temperament_run.py` walks, and it records the
    horizon at EVERY station rather than only where a step was taken. A stop where nothing was
    reachable is the most informative kind: it is an agent that looked and found every road
    refused, and a view that only recorded successful steps would render it as a walk that simply
    ended.

    A station's perceptions are read AFTER perceiving there and BEFORE stepping away, because
    `mv.step` empties the field and there is no second chance to ask.
    """
    from backend.services.agents import situated_agent as sa

    stations: List[Dict[str, Any]] = []
    for index in range(max(1, int(steps) + 1)):
        post = posts.get(agent.locus.post_id)
        if post is None:
            break
        sa.perceive(agent, post, now=now)
        entries = mv.horizon(agent, graph, posts, proposed_marks=list(marks))
        stations.append(station(agent, entries, index=index))

        if index >= int(steps):
            break
        chosen = tp.choose(entries, temperament=agent.temperament or tp.NO_TEMPERAMENT,
                           policy=policy)
        reach = chosen.get("reach")
        if reach is None:
            # THE WALK ENDED, and it says why rather than simply stopping. "Nothing was reachable"
            # and "the caller asked for three steps and got three" are different endings.
            stations[-1]["ended"] = {
                "reason": chosen.get("reason") or "no reachable crossing from here",
                "available": chosen.get("available"),
            }
            break
        mv.step(agent, reach, policy=chosen.get("policy") or policy, now=now)

    return walk_view(agent, stations=stations,
                     proposals=sa.report(agent) if agent.percept_field else ())
