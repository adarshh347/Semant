"""
WAVE5 — the first pursued goal: assigned, grounded, measured-or-failed.

Temperament gave an agent a character — a bias in HOW it moves. A goal gives an aim — a WHAT it
moves toward. This is the lane where intent-confabulation lives, because "the agent wanted to get
there" is a sentence that writes itself and that no measurement supports.

So the first goal is the most bounded one available:

    ASSIGNED    external and inspectable. The agent does not invent it, does not acquire one by
                walking, and cannot change the one it was given. Emergent goals are a later lane
                and a much riskier one.
    GROUNDED    a PREDICATE THE ORGANS CAN MEASURE — "stand where an occlusion is measurable",
                "stand where something rhymes with region R". Not a description of a destination
                and not a felt want; a claim that is true or false of a locus and that an organ,
                not this module, decides.
    MEASURED    satisfied ONLY when an organ has measured the predicate satisfied. Not-yet is
                not-yet. At the bound it is `not_reached`, which is a FINDING carrying how far it
                got — never a fabricated arrival.

## The bright line, which is the whole lane

**A goal biases which move is chosen and defines a measured success criterion. It changes nothing
an organ measures.**

The same pair of regions yields the same mark whether or not that mark advances a goal — pinned by
a test that runs one agent with a goal and one without and compares their percept fields byte for
byte. If a goal could touch a measurement, every number downstream would inherit the agent's aim,
and "the system found what it was looking for" would become literally true in the worst sense.

## Where a goal is allowed to act, and where it is not

`temperament.choose` picks the AXIS — the kind of move — and then selects within it. A goal ranks
**within the axis temperament already chose**, and nowhere else:

    temperament   which kind of move (occlusion / analogy / contact)
    goal          which move of that kind
    organ         what any of them measures        ← untouched by both

That ordering is not a convenience. A goal that could override the axis would be a goal reaching
across modalities — and the incommensurability wall says a depth reading and a chroma reading have
no common scale, so "closer to my aim" across them would be a number nobody measured. **A goal is
modality-bound** because the alternative is a fabricated comparison.

## What "advances the goal" is allowed to mean

Only a property of a REACHABLE, ALREADY-MEASURED move. `advantage()` reads the edge's own numbers —
the ones the organ put there — and never invents a distance-to-target. There is no gradient over
unvisited loci, because a gradient over places nobody has measured is exactly the fabricated
closeness this lane exists to refuse. An agent pursuing a goal is an agent preferring, among moves
it could already take, the ones whose measured properties point the right way.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.agents import movement as mv
from backend.services.agents import temperament as tp
from backend.services.agents.situated_agent import SituatedAgent
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

#: What a pursuit came to. Three outcomes, and the middle one is the honest one nobody wants to
#: build: an agent that pursued, did not arrive, and says so with how far it got.
SATISFIED = "satisfied"
NOT_REACHED = "not_reached"
UNPURSUABLE = "unpursuable"

#: The aims this lane states. A dict of declared goals rather than a free-form predicate, for the
#: reason `movement.POLICIES` and `temperament.TEMPERAMENTS` are tables: an aim an agent acted on
#: has to be a thing a reader can look up, and a lambda passed in from a caller is not inspectable
#: after the fact.
#:
#: Each names the ORGAN RELATION that satisfies it. `satisfied_by` then reads the agent's marks for
#: that relation and nothing else — which is what makes success a measurement rather than a claim.
GOALS: Dict[str, Dict[str, Any]] = {
    "reach_measurable_occlusion": {
        "relation": "in_front_of",
        "axis": "axis_occlusion",
        "detail": ("stand where the depth organ measures one region in front of another. Satisfied "
                   "by an `in_front_of` mark at the agent's own locus, on the mask basis"),
    },
    "reach_measurable_nesting": {
        "relation": "nested_within",
        "axis": "axis_nestedness",
        "detail": ("stand where the nestedness organ measures containment. Satisfied by a "
                   "`nested_within` mark at the agent's own locus, on the mask basis"),
    },
    "reach_measurable_contact": {
        "relation": "meets",
        "axis": "axis_adjacency",
        "detail": ("stand where the adjacency organ measures two regions meeting. Satisfied by a "
                   "`meets` mark at the agent's own locus, on the mask basis"),
    },
}

#: The basis a goal may be satisfied on. A box reading is an estimate (WAVE2.5), and an aim
#: satisfied by an estimate would be an arrival nobody measured — the exact shape of the
#: fabrication this lane is arranged against.
SATISFYING_BASIS = "mask"


class UnknownGoal(Exception):
    """An aim nobody declared. Raised rather than defaulted, exactly as `temperament` does: an
    agent pursuing something that is not written down anywhere is the opposite of assigned."""


class GoalNotMeasured(Exception):
    """Something claimed a goal satisfied without an organ measurement behind it.

    Raised rather than returned, and never caught into a softer outcome. `satisfied_by` reads
    marks; this fires when a caller tries to assert satisfaction some other way, which is the one
    thing a goal must never be able to do.
    """


def resolve(name: str) -> Dict[str, Any]:
    """An aim by name. Never guesses — an undeclared goal is refused, not approximated."""
    goal = GOALS.get(str(name or ""))
    if goal is None:
        raise UnknownGoal(
            f"no goal named {str(name)!r}. The ones this lane states are {sorted(GOALS)}. An aim "
            f"has to be declared to be inspectable, and an undeclared one is an intention nobody "
            f"can read off the agent.")
    return {"name": str(name), **goal}


# ── success: an organ measured it, or it did not happen ─────────────────────

def satisfying_marks(agent: SituatedAgent, goal_name: str) -> List[Dict[str, Any]]:
    """The agent's OWN marks that satisfy this aim. The only evidence of success there is.

    Reads the percept field — what this agent measured from where it stands — and nothing else. Not
    the graph, not another agent's report, not a horizon entry: a goal satisfied by something the
    agent did not itself measure is hearsay with an aim attached.

    TWO CHECKS THAT OVERLAP, KEPT ON PURPOSE. A box-basis mark already reads `interpretive`, so
    the status check alone would reject it — mutation-testing this function found that removing the
    basis check broke no test, which means the box case was passing for the status reason rather
    than the one it was written for.

    Both stay, because they say different things and the day they disagree is the day it matters:
    the basis check is about the GEOMETRY an aim may rest on, the status check is about what the
    ORGAN said. `situated_agent.MarkMisstated` exists precisely because a mark can claim a kind its
    basis does not support, and an aim is the last place that should be discovered.
    `test_the_status_check_stands_on_its_own` pins the second independently of the first.
    """
    goal = resolve(goal_name)
    out: List[Dict[str, Any]] = []
    for perception in agent.percept_field:
        reading = perception.reading
        if str(reading.relation) != goal["relation"]:
            continue
        if str(reading.basis) != SATISFYING_BASIS:
            continue
        mark = dict(perception.mark or {})
        # THE MARK ITSELF must say it is a measurement. The organ is the only thing entitled to say
        # so, and this reads its word rather than inferring one from the basis a second time.
        if str(mark.get(STATUS_KEY) or "") != EpistemicStatus.MEASURED.value:
            continue
        out.append(mark)
    return out


def is_satisfied(agent: SituatedAgent, goal_name: str) -> bool:
    """True only when an organ measured this aim's predicate at the agent's own locus."""
    return bool(satisfying_marks(agent, goal_name))


def assert_satisfied_is_measured(agent: SituatedAgent, goal_name: str,
                                 claimed: bool) -> None:
    """Refuse a claim of satisfaction that no mark supports.

    The write-side twin of `is_satisfied`, and it exists for the same reason `epistemics.declare`
    exists beside `guard`: the check that matters is the one on the path something takes when it is
    trying to assert rather than to ask.
    """
    if claimed and not is_satisfied(agent, goal_name):
        raise GoalNotMeasured(
            f"agent {agent.id} was reported to have satisfied {goal_name!r} and no organ of its "
            f"own measured the predicate at {agent.locus.node_id}. A goal is satisfied by a "
            f"measurement or it is not satisfied — there is no third state, and 'close enough' is "
            f"the fabrication this lane exists to refuse.")


# ── pursuit: preferring among moves that already exist ──────────────────────

def advantage(reach: mv.Reach, goal_name: str) -> Tuple[int, float]:
    """How much this ALREADY-MEASURED move points toward the aim. Never a distance to a target.

    Two components, both read off the edge the organ produced:

      1. does this crossing's own relation match the aim's? A move along the aim's relation lands
         somewhere that relation was measured, which is the only honest sense in which a reachable
         move "advances" a predicate about relations.
      2. among those, the organ's own strength number, so ties break on a measurement rather than
         on iteration order.

    WHAT IS ABSENT is the design: no estimate of the destination's contents, no gradient over loci
    nobody has measured, no learned value. An agent cannot know what it will find where it has not
    stood — `movement.step` empties the percept field for exactly that reason — so a goal that
    scored unvisited destinations would be scoring an imagination.
    """
    goal = resolve(goal_name)
    matches = 1 if str(reach.relation or "") == goal["relation"] else 0
    strength = float(reach.edge.get("systematicity") or reach.edge.get("weight") or 0.0)
    return (matches, strength)


def choose(entries: Sequence[mv.Reach], *, goal_name: str = "",
           temperament: str = tp.NO_TEMPERAMENT,
           policy: str = mv.POLICY_SYSTEMATICITY) -> Dict[str, Any]:
    """Pick one reachable move, with an aim, and say exactly how the aim mattered.

    THE ORDER IS THE HONESTY. `temperament.choose` runs FIRST and picks the axis; the goal then
    re-ranks inside that axis and nowhere else. A goal that could pull the agent onto a different
    axis would be comparing a depth move to an analogy move on a scale nobody measured, which is
    the incommensurability wall — so it cannot, and the record says when the aim's own axis was not
    the one taken.
    """
    record = tp.choose(entries, temperament=temperament, policy=policy)
    if not goal_name:
        return {**record, "goal": None, "goal_biased": False}

    goal = resolve(goal_name)
    chosen_axis = str(record.get("chose_kind") or "")
    within = [r for r in entries if str(r.axis_ref or "") == chosen_axis] if chosen_axis else []

    base = {**record, "goal": goal["name"], "goal_detail": goal["detail"],
            "goal_axis": goal["axis"], "goal_biased": False}

    if record.get("reach") is None or not within:
        return {**base, "goal_reason": "nothing reachable, so the aim had nothing to choose among"}

    if chosen_axis != goal["axis"]:
        # SAID, not silently absorbed. The agent is moving along an axis its aim is not about, and
        # a pursuit record that hid that would make every step look purposeful.
        return {**base, "goal_reason": (
            f"temperament chose {chosen_axis} and this aim is about {goal['axis']} — the goal did "
            f"not bias this step. An aim may rank moves WITHIN a kind; ranking across kinds would "
            f"compare two measurements that share no scale.")}

    ranked = sorted(within, key=lambda r: advantage(r, goal["name"]), reverse=True)
    best = ranked[0]
    biased = best is not record.get("reach")
    return {**base, "reach": best, "goal_biased": biased,
            "goal_advantage": list(advantage(best, goal["name"])),
            "goal_reason": (
                f"among {len(within)} reachable {chosen_axis} move(s), the aim preferred the one "
                f"whose own measured relation is {goal['relation']!r}"
                + ("" if biased else " — which is the one the policy would have taken anyway"))}


# ── the pursuit, and its honest ending ──────────────────────────────────────

def outcome(agent: SituatedAgent, goal_name: str, *, steps_taken: int,
            bound: int, reason: str = "") -> Dict[str, Any]:
    """What became of the pursuit. Satisfied, not reached, or never pursuable — each with evidence.

    `not_reached` is a FINDING and is shaped like one: it carries how far the agent got and what it
    did measure, because "pursued and did not arrive" is a real result about this graph and this
    body, and rendering it as an error would throw that away. What it never carries is a distance
    to the target, because there is no measured one.
    """
    marks = satisfying_marks(agent, goal_name)
    goal = resolve(goal_name)
    common = {
        "goal": goal["name"], "goal_detail": goal["detail"],
        "agent_id": agent.id, "node_id": agent.locus.node_id,
        "steps_taken": steps_taken, "bound": bound,
        "measured_here": len(agent.percept_field),
    }
    if marks:
        return {**common, "outcome": SATISFIED,
                # THE EVIDENCE, cited. A satisfaction that named no mark would be a claim.
                "satisfying_marks": [str(m.get("id") or "") for m in marks],
                "detail": (f"an organ of {agent.id} measured {goal['relation']!r} at "
                           f"{agent.locus.node_id} on the {SATISFYING_BASIS} basis")}
    if steps_taken == 0 and reason:
        return {**common, "outcome": UNPURSUABLE, "satisfying_marks": [],
                "detail": f"the pursuit could not begin: {reason}"}
    return {**common, "outcome": NOT_REACHED, "satisfying_marks": [],
            "detail": (
                f"{agent.id} took {steps_taken} of {bound} step(s) and no organ of its own measured "
                f"{goal['relation']!r} at {agent.locus.node_id}. That is a finding about this graph "
                f"and this body — not an error, and not a near miss: there is no measured distance "
                f"to an aim, so 'how close' is not a question this system can answer.")}


def pursue(agent: SituatedAgent, graph: Mapping[str, Any], posts: Mapping[str, Any], *,
           goal_name: str, marks: Sequence[Mapping[str, Any]] = (), bound: int = 3,
           policy: str = mv.POLICY_SYSTEMATICITY, now: str = "") -> Dict[str, Any]:
    """Perceive, check, choose toward the aim, step — until satisfied or out of bound.

    Stops the moment the aim is measured. Not because stopping is efficient, but because continuing
    would make the record ambiguous about WHERE it was satisfied, and the locus is half the claim.
    """
    from backend.services.agents import situated_agent as sa

    resolve(goal_name)                      # refuse an undeclared aim before anything moves
    steps: List[Dict[str, Any]] = []
    taken = 0
    reason = ""

    for _ in range(max(0, int(bound)) + 1):
        post = posts.get(agent.locus.post_id)
        if post is None:
            reason = f"no post {agent.locus.post_id} to perceive"
            break
        sa.perceive(agent, post, now=now)
        if is_satisfied(agent, goal_name):
            break
        if taken >= int(bound):
            break
        entries = mv.horizon(agent, graph, posts, proposed_marks=list(marks))
        decision = choose(entries, goal_name=goal_name,
                          temperament=agent.temperament or tp.NO_TEMPERAMENT, policy=policy)
        reach = decision.get("reach")
        if reach is None:
            reason = decision.get("reason") or "nothing reachable from here"
            break
        entry = mv.step(agent, reach, policy=decision.get("policy") or policy, now=now)
        steps.append({"to_node": entry["to_node"], "axis_ref": entry["axis_ref"],
                      "goal_biased": bool(decision.get("goal_biased")),
                      "goal_reason": decision.get("goal_reason") or "",
                      "crossed_image": bool(entry.get("crossed_image"))})
        taken += 1

    return {**outcome(agent, goal_name, steps_taken=taken, bound=bound, reason=reason),
            "steps": steps,
            "biased_steps": sum(1 for s in steps if s["goal_biased"])}
