"""
WAVE3 — cross-modal composition: do two senses' RELATIONS compose, or only coexist?

The last question the `Incommensurable` guard holds open, and it only became answerable now. The
small-society lane asked it of READINGS and got `incommensurable` for every geometry-vs-chroma pair
— by arity, because a relation between two places and a property of one place have no common
subject. That verdict was about percepts. Both senses have since grown RELATIONS (`in_front_of`,
`rhymes_with`), and two relations do share a kind of subject: an ordered pair of regions.

So the question is now real, and this module asks it with the EXISTING mechanism. It invents no
cross-modal statistic, no shared scale and no composition rule.

## What the mechanism says, and why that is not yet an answer

`society.comparable` reads arity off the reading: 2 for a relation, 1 for a field. Under it,
`in_front_of` and `rhymes_with` are both arity 2, so a depth agent and a chroma agent carrying
relations now come back **comparable** where their percept-level selves came back
`incommensurable`. That is a real consequence of chroma becoming relational, and it is worth
stating plainly rather than presenting as a discovery: arity is a coarse test, and it now passes a
pair it used to refuse.

Comparable is not composed. `dialogue.compose` knows **exactly one** composition —
`nested_within` + `meets` over the same region → `nested_at_boundary` — so every other pairing
returns empty and every other pair is `coexistent` BY CONSTRUCTION. A lane that ran the mechanism,
observed `coexistent`, and reported "cross-modal relations do not fuse" would be reporting the
shape of a hardcoded rule as a fact about pictures. This module refuses to do that, and
`KNOWN_COMPOSITIONS` / `attempt` are arranged so the reason is inspectable.

## The structural question underneath, which the corpus CAN answer

Composition worked for nestedness+adjacency because the two organs were **partial views of one
aspect**: both answer "how does this pair's boundary stand?", each blind where the other sees, and
inside-and-at-the-lip is a single topological fact neither can state alone.

Depth-order and chromatic correspondence are not partial views of one aspect. They are complete
answers to **different questions about the same pair**:

    in_front_of    which of these two is nearer the camera
    rhymes_with    whether their warmth is organised the same way

"A is in front of B and A rhymes with B" is a **conjunction**, not a composition. There is no third
fact that neither states — nothing is resolved by putting them together, because neither was
ambiguous in the way the other could fix. That is the difference between two organs disagreeing
about one thing and two organs answering two things.

This module measures the first half of that (do they share a subject at all?) and reports the
second as what it is: an argument about why no composition rule exists, not a measurement.

## The honest default

`COEXISTENT` where the subject is shared and nothing composes; `INCOMMENSURABLE` where no shared
subject is possible. A cross-modal `COMPOSED` would require someone to write a rule saying what
third fact the two jointly establish, and this lane deliberately does not write one — inventing it
here is the fabrication the whole guard exists against.

PURE. No database, no network, no model.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services import chroma_organ
from backend.services.agents import society

#: Reused, never restated. A second vocabulary for the same three outcomes is a second place for
#: them to drift, and the small-society lane is where they are defined.
COMPOSED = society.COMPOSED
COEXISTENT = society.COEXISTENT
INCOMMENSURABLE = society.INCOMMENSURABLE

#: A fourth outcome this layer needs and the pair layer did not: two relations that are both arity
#: 2 — so `comparable` admits them — and are about DIFFERENT PAIRS. Not incommensurable (they could
#: have been about the same pair) and not coexistent (they are not about one thing at all).
DIFFERENT_SUBJECT = "different_subject"

#: The relation kinds this corpus grounds, by the sense that produces them. Data, not a taxonomy
#: with opinions: it exists so `attempt` can say WHICH senses a pair spans without parsing names.
GEOMETRIC = ("nested_within", "meets")
DEPTH = ("in_front_of", "coplanar")
CHROMATIC = ("rhymes_with", "chromatically_unrelated")

_SENSE_OF: Dict[str, str] = {
    **{r: "geometry" for r in GEOMETRIC},
    **{r: "depth" for r in DEPTH},
    **{r: "chroma" for r in CHROMATIC},
}

#: THE ONLY COMPOSITION THIS SYSTEM KNOWS, named here so its scarcity is visible at the place
#: cross-modal composition is being attempted. `dialogue.compose` implements it; this is not a
#: second implementation, it is the fact that there is one.
#:
#: A reader who wants a cross-modal entry has to write down what third fact the two relations
#: jointly establish. That nobody has been able to is the finding, not the absence of a table.
KNOWN_COMPOSITIONS: Tuple[Tuple[str, str, str], ...] = (
    ("nested_within", "meets", "nested_at_boundary"),
)


class CrossModalLeak(Exception):
    """A cross-modal comparison produced a number. Raised, never carried.

    `society.CompatibilityLeak`'s sibling one level up: there the leak would be a magnitude between
    two agents' readings, here between two RELATIONS. Both are the same fabrication — a common
    currency nobody measured — and both are refused at the layer that would otherwise pass it on.
    """


def sense_of(relation: Optional[Mapping[str, Any]]) -> str:
    """Which sense produced this relation reading. `unknown` for anything unregistered."""
    return _SENSE_OF.get(str((relation or {}).get("relation") or ""), "unknown")


def subject_of(relation: Optional[Mapping[str, Any]]) -> Optional[frozenset]:
    """The pair of regions this relation is about, unordered, or None if it names no pair.

    UNORDERED on purpose. `in_front_of` is directed and `rhymes_with` is symmetric; asking whether
    they are about the same SUBJECT is asking whether they concern the same two regions, which is a
    question about what is being talked about rather than about who is in front.
    """
    if not relation:
        return None
    ids = [str(relation.get(k) or "") for k in ("a_region_id", "b_region_id")]
    if not all(ids):
        ids = [str(relation.get(k) or "") for k in ("inner_region_id", "outer_region_id")]
    if not all(ids) or ids[0] == ids[1]:
        return None
    return frozenset(ids)


def shares_a_subject(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """Are these two relations about the same pair of regions?"""
    sa, sb = subject_of(a), subject_of(b)
    return bool(sa and sb and sa == sb)


def _refusal(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    """Ask #158's own function, exactly as `society.refuse_comparison` does, and pass on its words.

    Routed through rather than restated for the reason that lane gives: `compare_across_senses` is
    where this system records that no scale exists, and a second place saying so is a second place
    that can stop saying so.
    """
    try:
        value = chroma_organ.compare_across_senses(dict(a), dict(b))
    except chroma_organ.Incommensurable as exc:
        return str(exc)
    raise CrossModalLeak(
        f"compare_across_senses returned {value!r} for a {sense_of(a)} relation and a "
        f"{sense_of(b)} one instead of refusing. A cross-modal magnitude is the single easiest way "
        f"to make this system confident about something it has never measured.")


def attempt(a: Mapping[str, Any], b: Mapping[str, Any]) -> Dict[str, Any]:
    """Two grounded relation readings → what holds between them. Writes nothing, invents nothing.

    The order of questions mirrors `society.relate`, one level up:

      1. **Same sense?** Then this is not a cross-modal attempt at all and the caller is asking the
         wrong layer — `dialogue.compose` already handles within-sense composition.
      2. **Same subject?** Two relations about different pairs are not about one thing, whatever
         their arity says.
      3. **Does any known composition cover this pairing?** Exactly one exists and it is
         within-sense, so a cross-modal pair reaches `COEXISTENT` — and the verdict says *why*,
         because "no rule covers it" and "no relationship exists" are different sentences.
    """
    sense_a, sense_b = sense_of(a), sense_of(b)
    subject = subject_of(a)

    # ASKED FIRST, and it was not at first — the same-sense exit below used to shadow it, which
    # made COMPOSED unreachable for the only composition that exists and would have turned this
    # lane's null into an artifact of its own control flow. A known composition is reported
    # wherever it applies; the test that catches this is
    # `test_the_mechanism_can_return_composed`.
    covered = [c for c in KNOWN_COMPOSITIONS
               if {c[0], c[1]} == {str(a.get("relation")), str(b.get("relation"))}]
    if covered and shares_a_subject(a, b):
        return {
            "outcome": COMPOSED, "cross_modal": sense_a != sense_b,
            "senses": [sense_a, sense_b], "subject": sorted(subject),
            "claim": covered[0][2],
            "detail": f"a known composition covers this pairing: {covered[0][2]}",
        }

    if sense_a == sense_b:
        return {
            "outcome": COEXISTENT, "cross_modal": False,
            "senses": [sense_a, sense_b], "subject": sorted(subject) if subject else [],
            "detail": (f"both readings are {sense_a} — this is a within-sense pairing, and "
                       f"`dialogue.compose` is the layer that handles those. Asking the cross-modal "
                       f"question of one sense would answer it with the wrong evidence."),
        }

    if not shares_a_subject(a, b):
        return {
            "outcome": DIFFERENT_SUBJECT, "cross_modal": True,
            "senses": [sense_a, sense_b],
            "subject": [],
            "detail": (f"a {sense_a} relation about {sorted(subject_of(a) or [])} and a {sense_b} "
                       f"relation about {sorted(subject_of(b) or [])} are not about the same pair. "
                       f"`society.comparable` admits them because both are arity 2, which is where "
                       f"that test is too coarse now that every sense carries relations."),
        }

    return {
        "outcome": COEXISTENT, "cross_modal": True,
        "senses": [sense_a, sense_b], "subject": sorted(subject),
        # THE HONEST SENTENCE. Not "these do not compose" — "nothing has been written down that
        # says what they would jointly establish", which is a different and weaker claim, and the
        # only one this module is in a position to make.
        "detail": (
            f"a {sense_a} relation and a {sense_b} relation about the same pair "
            f"{sorted(subject)}. They coexist: both are true of it, and no composition is known "
            f"that says what the two jointly establish. That is a fact about what has been "
            f"written down, not a measurement showing no relationship exists — and the reason no "
            f"rule exists is structural: nestedness and adjacency compose because they are partial "
            f"views of ONE aspect (how this pair's boundary stands), each blind where the other "
            f"sees. Depth-order and chromatic correspondence are complete answers to DIFFERENT "
            f"questions about the pair, so putting them together is a conjunction and not a "
            f"composition — neither was ambiguous in the way the other could resolve."),
        "refusal_if_asked_for_a_number": _refusal(a, b),
    }


def survey(relations: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Every cross-modal pairing among these relations, and the distribution of verdicts.

    A report, not a gate. The bound is the caller's and this states what it was handed — a scan
    that said "no cross-modal composition exists" after looking at six pairs would be a claim about
    how far it looked.
    """
    outcomes: Dict[str, int] = {}
    pairings: Dict[str, int] = {}
    shared: List[Dict[str, Any]] = []

    for i in range(len(relations)):
        for j in range(i + 1, len(relations)):
            a, b = relations[i], relations[j]
            if sense_of(a) == sense_of(b) or "unknown" in (sense_of(a), sense_of(b)):
                continue
            verdict = attempt(a, b)
            outcomes[verdict["outcome"]] = outcomes.get(verdict["outcome"], 0) + 1
            key = " x ".join(sorted(verdict["senses"]))
            pairings[key] = pairings.get(key, 0) + 1
            if verdict["outcome"] in (COEXISTENT, COMPOSED) and verdict["cross_modal"]:
                shared.append(verdict)

    return {
        "relations": len(relations),
        "cross_modal_attempts": sum(outcomes.values()),
        "outcomes": outcomes,
        "pairings": pairings,
        "same_subject": len(shared),
        "composed": outcomes.get(COMPOSED, 0),
        "examples": shared[:5],
        "detail": (
            f"{sum(outcomes.values())} cross-modal attempts, {len(shared)} about a shared subject, "
            f"{outcomes.get(COMPOSED, 0)} composed"),
    }
