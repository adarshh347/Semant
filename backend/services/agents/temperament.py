"""
WAVE3 — temperament: an agent chooses by disposition, because the alternatives cannot be ranked.

## The problem depth-movement created

An agent now has two ways to move and **they cannot be compared**:

    axis_nestedness   a cross-image analogy    ranked by systematicity   [0,1], a structure-map score
    axis_occlusion    an intra-image depth step ranked by separation     [0,1], an ordering statistic

Both are numbers in `[0,1]` and that is the whole trap. A systematicity of 0.62 and a depth
separation of 0.99 are not 0.62 and 0.99 of the same thing; putting them in one `max()` would
invent a common currency, and the agent would then "prefer" depth steps for a reason that is an
artefact of two unrelated statistics happening to share a range. This is the same wall
`depth_organ.compare_across_senses` raises and `retina.store` builds between vector spaces: *every
pair of measures is incommensurable until someone earns the comparison.*

Nobody has earned it. So the agent does not rank them — **it has a disposition**, and the
disposition picks the KIND of move. The kind's own rule then picks within it, where the numbers are
finally of one thing.

    temperament   picks the MODE       — a declared bias over kinds of move
    the mode      picks the MOVE       — systematicity within geometry, separation within depth

The incommensurable numbers never meet. `test_the_two_scores_are_never_put_on_one_scale` asserts it
by watching what `movement.select` is handed: always entries sharing one axis, never a mixture.

## The bright line

**Temperament biases SELECTION and ATTENTION — never MEASUREMENT.**

An organ measures the same thing whoever is looking. A depth-seeker and an analogy-seeker standing
at one locus, measuring one pair, produce the **identical mark**; their worlds differ in where they
GO, not in what is TRUE there. A temperament that changed a measurement would be a character
authoring its own evidence, which is the confabulation this module exists to make impossible —
nothing here imports an organ, and `attend` re-orders a percept field without touching a reading.

## Not a goal

A temperament is a bias over *kinds*, never an aim toward a *target*. "Prefer depth steps" is a way
of being; "reach the minaret" is a want, and a want is something to confabulate a justification for.
There is no destination anywhere in this module and `assert_no_destination` refuses one that tries.

## Declared, not learned

Every temperament is a value in `TEMPERAMENTS` with its preference order written out, and the order
it used is recorded on the choice it produced. An agent's character is inspectable from the outside,
which is the only version of interiority this system can currently be honest about.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.agents import movement as mv

#: The axis names, MIRRORED from the organs rather than imported.
#:
#: Importing `occlusion_organ` here would put a relation-grounding capability inside the layer that
#: decides where an agent goes, and `movement.py` is guarded against exactly that. What this module
#: needs is three strings. `test_the_axis_names_have_not_drifted_from_the_organs` imports the organs
#: and asserts these still match — the guard that makes the duplication safe rather than a
#: liability, as with the retina's `_alignment`.
AXIS_NESTEDNESS = "axis_nestedness"
AXIS_ADJACENCY = "axis_adjacency"
AXIS_OCCLUSION = "axis_occlusion"

#: Which rule decides WITHIN a kind, once a temperament has chosen the kind.
#:
#: This is where the numbers are finally of one thing. Two systematicity scores are comparable
#: because they measure the same quantity over the same kind of crossing; two separations likewise.
#: A kind with no entry falls to the geometric rule and says so, rather than being dropped.
RULE_FOR_AXIS: Dict[str, str] = {
    AXIS_NESTEDNESS: mv.POLICY_SYSTEMATICITY,
    AXIS_ADJACENCY: mv.POLICY_SYSTEMATICITY,
    AXIS_OCCLUSION: mv.POLICY_ORDERING,
}

#: The kind used when an axis is not one this module knows. Named rather than defaulted inline, so
#: an unfamiliar axis produces a stated fallback instead of a silent one.
DEFAULT_RULE = mv.POLICY_SYSTEMATICITY


@dataclass(frozen=True)
class Temperament:
    """A declared bias over KINDS of move. Not a goal, not a target, not a learned policy.

    `prefers` is an order, not a score: the agent takes the first kind it can actually move along.
    That is what keeps this a disposition — there is no quantity being maximised across kinds, so
    there is nothing for an incommensurable comparison to hide inside.
    """
    name: str
    prefers: Tuple[str, ...]
    detail: str

    def as_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "prefers": list(self.prefers), "detail": self.detail}


#: The characters this lane states. A dict of values rather than branches, for the reason
#: `movement.POLICIES` is: the disposition an agent acted on has to be a thing a reader can look up.
TEMPERAMENTS: Dict[str, Temperament] = {
    "depth_seeker": Temperament(
        name="depth_seeker",
        prefers=(AXIS_OCCLUSION, AXIS_NESTEDNESS, AXIS_ADJACENCY),
        detail=("moves through a scene before moving between pictures: takes an occlusion step "
                "wherever one is reachable, and only then an analogy")),
    "analogy_seeker": Temperament(
        name="analogy_seeker",
        prefers=(AXIS_NESTEDNESS, AXIS_ADJACENCY, AXIS_OCCLUSION),
        detail=("moves between pictures before moving through one: takes a grounded cross-image "
                "crossing wherever one is reachable, and only then a depth step")),
    "contact_seeker": Temperament(
        name="contact_seeker",
        prefers=(AXIS_ADJACENCY, AXIS_OCCLUSION, AXIS_NESTEDNESS),
        detail=("follows what touches what: takes an adjacency crossing wherever one is "
                "reachable, then a depth step, then an analogy")),
}

#: The character an agent has when nobody gave it one: no bias at all.
#:
#: NOT a hidden default temperament. An agent with no declared disposition falls straight through
#: to the caller's stated policy, which is what every agent did before this module existed. A
#: default character would be this lane deciding who agents are by omission.
NO_TEMPERAMENT = ""


class UnknownTemperament(Exception):
    """A character nobody declared. Raised rather than defaulted: an agent acting on a disposition
    that is not written down anywhere is the opposite of what this module is for."""


def resolve(name: str) -> Optional[Temperament]:
    """The declared temperament, or None for an agent that was given none."""
    key = str(name or "")
    if not key:
        return None
    if key not in TEMPERAMENTS:
        raise UnknownTemperament(
            f"no temperament named {key!r} — the ones this lane states are {sorted(TEMPERAMENTS)}. "
            f"A character has to be declared to be inspectable, and an undeclared one is a policy "
            f"nobody can read off the agent")
    return TEMPERAMENTS[key]


def assert_no_destination(temperament: Mapping[str, Any]) -> None:
    """Refuse a temperament that names somewhere to get to.

    A bias over kinds is a way of being; a target is a want, and a want is the thing an agent would
    start confabulating justifications for. The line is not a matter of degree — either the
    disposition mentions a place or it does not.
    """
    forbidden = ("destination", "target", "goal", "toward", "node_id", "post_id", "region_id")
    named = sorted(k for k in temperament if any(f in str(k).lower() for f in forbidden))
    if named:
        raise ValueError(
            f"temperament {temperament.get('name')!r} names {named} — that is a goal, not a "
            f"character. This lane builds dispositions over KINDS of move; an aim toward a place "
            f"is the deferred fork, and it does not arrive by the back door")


def by_axis(entries: Sequence[Any]) -> Dict[str, List[Any]]:
    """Reachable moves, partitioned by kind. THE STRUCTURAL GUARANTEE.

    Partitioning first is what makes the incommensurability impossible to violate rather than
    merely discouraged: every group handed onward shares one axis, so the only comparisons any rule
    ever makes are between two measurements of the same quantity.
    """
    groups: Dict[str, List[Any]] = {}
    for entry in mv.reachable(entries):
        groups.setdefault(str(entry.axis_ref or ""), []).append(entry)
    return groups


def choose(entries: Sequence[Any], *, temperament: str = NO_TEMPERAMENT,
           policy: str = mv.POLICY_SYSTEMATICITY) -> Dict[str, Any]:
    """Pick one reachable move by DISPOSITION, and say how the choice was made.

    Returns a record rather than a bare `Reach`, because "which kind did you take and was it the
    one you prefer" is the whole content of this lane and a caller that got only the move could not
    ask it. `reach` is None when nothing is reachable at all.

    THE FALLBACK IS LEGIBLE. A depth-seeker at a locus with no reachable occlusion takes an analogy
    step and the record says it fell back, from what, to what. What it never does is manufacture a
    preferred move: the disposition ranks kinds that exist, and a kind with nothing in it is
    skipped, not invented.
    """
    character = resolve(temperament)
    groups = by_axis(entries)
    available = {axis: len(rows) for axis, rows in sorted(groups.items())}

    base = {
        "temperament": character.name if character else NO_TEMPERAMENT,
        "prefers": list(character.prefers) if character else [],
        "available": available,
        "reach": None, "chose_kind": "", "policy": "", "fell_back": False,
    }

    if not groups:
        return {**base, "reason": "nothing reachable from here — no kind to prefer"}

    if character is None:
        # NO CHARACTER, NO CHANGE. An agent given no disposition behaves exactly as it did before
        # this module existed: the caller's stated policy over everything reachable.
        chosen = mv.select(entries, policy=policy)
        return {**base, "reach": chosen, "chose_kind": chosen.axis_ref if chosen else "",
                "policy": policy, "rule": mv.POLICIES.get(policy, ""),
                "reason": ("this agent has no declared temperament, so the caller's policy decides "
                           "over every reachable move — which is what every agent did before "
                           "characters existed")}

    order = [axis for axis in character.prefers if groups.get(axis)]
    unmet = [axis for axis in character.prefers if not groups.get(axis)]
    # A kind the character never named, but which is reachable. Taken only after every named one,
    # and never silently: an agent that walked an axis its disposition does not mention should say
    # that is what happened.
    unnamed = [axis for axis in sorted(groups) if axis not in character.prefers]

    kind = (order + unnamed)[0]
    rule = RULE_FOR_AXIS.get(kind, DEFAULT_RULE)
    # ONE AXIS ONLY. `groups[kind]` shares an axis by construction, so the rule below compares two
    # measurements of one quantity and never two of different ones.
    chosen = mv.select(groups[kind], policy=rule)

    preferred = character.prefers[0] if character.prefers else ""
    fell_back = bool(preferred and kind != preferred)
    if fell_back:
        reason = (f"{character.name} prefers {preferred} and nothing along it is reachable from "
                  f"here ({', '.join(unmet) or 'none'} empty), so it took {kind} — the next kind "
                  f"in its order that affords a move")
    else:
        reason = (f"{character.name} prefers {kind} and {available.get(kind, 0)} move(s) along it "
                  f"are reachable, so the choice was made within that kind by {rule!r}")

    return {**base, "reach": chosen, "chose_kind": kind, "policy": rule,
            "rule": mv.POLICIES.get(rule, ""), "fell_back": fell_back,
            "preferred": preferred, "unmet": unmet, "unnamed_kinds_taken": bool(kind in unnamed),
            "reason": reason}


def attend(percepts: Sequence[Any], *, temperament: str = NO_TEMPERAMENT) -> List[Any]:
    """Re-ORDER a percept field by disposition. Never filters, and never touches a reading.

    Attention is what an agent looks at first, not what it is able to see. A temperament that
    dropped readings would be a character deciding what is true of a place, and two agents at one
    locus would then disagree about the world rather than about where to go next — the exact
    confusion the bright line exists to prevent.

    So this returns the same readings, every one of them, in a different order. `test_attention_is
    _a_permutation_and_never_a_filter` pins it by multiset comparison.
    """
    character = resolve(temperament)
    rows = list(percepts)
    if character is None:
        return rows

    # A stable sort on a key that reads only the RELATION a reading is of, so the order is a
    # function of the disposition and the reading's own kind — never of its numbers.
    rank = {axis: i for i, axis in enumerate(character.prefers)}

    def key(percept: Any) -> Tuple[int, str]:
        relation = str(getattr(getattr(percept, "reading", None), "direction", "") or "")
        return (rank.get(_axis_for_relation(relation), len(rank)), relation)

    return sorted(rows, key=key)


#: Which kind of move a reading's relation belongs to. Mirrored, like the axis names above, and
#: pinned against the organs by the same drift test.
_RELATION_AXIS: Dict[str, str] = {
    "nested_within": AXIS_NESTEDNESS,
    "contains": AXIS_NESTEDNESS,
    "meets": AXIS_ADJACENCY,
    "in_front_of": AXIS_OCCLUSION,
    "coplanar": AXIS_OCCLUSION,
}


def _axis_for_relation(relation: str) -> str:
    return _RELATION_AXIS.get(str(relation or ""), "")


__all__ = ["Temperament", "TEMPERAMENTS", "NO_TEMPERAMENT", "UnknownTemperament",
           "AXIS_NESTEDNESS", "AXIS_ADJACENCY", "AXIS_OCCLUSION", "RULE_FOR_AXIS", "DEFAULT_RULE",
           "resolve", "assert_no_destination", "by_axis", "choose", "attend"]
