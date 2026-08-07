"""WAVE3 — the first small society: three agents, and one of them cannot compare notes.

Two agents give you agreement, disagreement, and refusal. Three give you something none of those
are: **a structure over the pairs**. In this society one pair can compose a claim neither made
alone, and two pairs cannot even be about the same thing — and the difference between "we looked
and found nothing in common" and "there is nothing we could have in common" is the first fact here
that is not about any single agent.

    α  nestedness_organ   the locus is INSIDE R
    β  adjacency_organ    the locus MEETS R's boundary       → compose: it is at R's RIM
    γ  chroma_organ       the locus reads +0.31 on warm/cool  → and this composes with NEITHER

## What is genuinely new at three, and what is not

**New: heterogeneous comparability.** The society partitions into classes that can be about the
same thing at all. That partition is a property of the group, invisible from inside any pair, and
it is the first structure this project has that is richer than one agreement.

**New: the wholly-received belief.** With two agents, every joint hypothesis has both of them as
contributors — an agent holding a claim it contributed nothing to is a state that CANNOT ARISE.
Add a third and it arises immediately: γ stands there and hears α and β compose. `dialogue.hold`
would record it happily as `contributed=0 received=2`, which is testimony with no measurement of
its own — hearsay wearing the vocabulary of a held belief. `hold_all` refuses it. See §`hold_all`.

**NOT new: measured contradiction.** Two agents measuring the same subject to incompatible answers
is not producible in this corpus and this lane does not stage one. The organs are deterministic
geometry, and a `nested_within` reading and a `meets` reading about the same pair are compatible by
construction — that is why they compose. What a third agent actually adds is **refusal**: γ can be
asked to state what α and β agreed and cannot. Reporting that as "disagreement" would be dressing a
missing capability as a finding.

## Commensurability is read off the readings, not off a list of organ names

The tempting implementation is `if organ == "chroma_organ": incommensurable`. That hard-codes
today's sensorium into the society layer, and it would be wrong the moment a chromatic *relation*
exists (a later lane's subject). The structural fact is in the readings themselves:

    a geometry reading   relates the locus to ANOTHER region     two terms
    a chroma reading     reports a property of the locus itself  one term

A one-term reading and a two-term reading have no subject in common, so there is nothing for them
to agree or disagree about. `arity` reads that off `other_region_id`, which is exactly what the
chroma finding measured ("a chroma reading has `other_region_id == ''` and rests on ONE ground").
Nestedness and adjacency are commensurable under the same rule, and they are — they compose.

## The refusal is REUSED, not re-implemented

When two agents share no arity, this module calls `chroma_organ.compare_across_senses` and records
the `Incommensurable` it raises. It does not decide incommensurability for itself and it does not
paraphrase the reason. That function exists so the absence is reachable (#158); a society layer with
its own private copy of the judgement is two judgements that will drift, and the one that drifts
quietly is the one deciding whether two senses may be compared.

And if it ever returns instead of raising, this module raises `CompatibilityLeak` — loudly, at the
call site, rather than quietly producing the cross-sense number nobody has earned.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services import chroma_organ
from backend.services.agents import dialogue
from backend.services.agents import meeting
from backend.services.agents import movement as mv
from backend.services.agents import observation as obs_mod
from backend.services.agents.situated_agent import Hearsay, SituatedAgent

#: Three. Two is the dialogue lane, and the whole question here is what appears at three — so a
#: "society" of two would answer it by not asking.
MIN_MEMBERS = 3

#: How a pair of co-located agents stands to each other. Four outcomes, kept apart because they are
#: four different facts about a pair and collapsing any two would hide the heterogeneity this lane
#: exists to represent.
COMPOSED = "composed"                  # they made a claim neither made alone
COEXISTENT = "coexistent"              # comparable, co-located, nothing in common to compose
INCOMMENSURABLE = "incommensurable"    # no shared subject is possible — not "none was found"
SAME_BODY = "same_body"                # two copies of one world; their agreement is bookkeeping
#: One of them measured NOTHING here, so comparability is not a question this locus can answer.
#: Caught by this lane's own tests: `comparable` reads arities off the readings, and an agent with
#: an empty field has none — which made a silent agent read as `incommensurable` with everyone.
#: That is the exact confusion the lane exists to prevent, arriving from the inside: "we could
#: never be about the same thing" is a strong claim, and "it said nothing" is no evidence for it.
UNDETERMINED = "undetermined"

#: Why an agent may not hold a hypothesis. One entry, and it only becomes reachable at three.
WHOLLY_RECEIVED = "wholly_received"


class NotASociety(Exception):
    """Fewer than three members, or fewer than two bodies between them.

    Three agents carrying one organ set are one world enacted three times. The count is not the
    point; the heterogeneity is, and a society that is uniform answers the lane's question by
    changing it.
    """


class CompatibilityLeak(Exception):
    """`compare_across_senses` returned a number instead of refusing.

    The single most dangerous thing that could happen to this layer, so it is an exception rather
    than a log line: a cross-sense magnitude would make the system confident about a comparison
    nobody has ever measured, and every downstream reader would inherit it.
    """


# ── comparability, read off the readings ────────────────────────────────────

def arity(reading: Any) -> int:
    """How many terms this reading is about: 2 for a relation, 1 for a field.

    The structural difference between the senses in this corpus, and it is a fact about the
    reading rather than a fact about the organ's name — so it keeps working when an organ grows a
    second kind of output, and it never has to be updated when a fourth sense arrives.
    """
    return 2 if str(getattr(reading, "other_region_id", "") or "") else 1


def arities(agent: SituatedAgent) -> set:
    """The kinds of subject this agent's field is about at all. Empty if it measured nothing."""
    return {arity(p.reading) for p in agent.percept_field}


def comparable(alpha: SituatedAgent, beta: SituatedAgent) -> bool:
    """Could these two ever be about the same thing? A question about bodies, not about luck.

    Two geometry agents that happen to share no region are still comparable — they simply found
    nothing in common here, and at the next locus they might. A geometry agent and a chroma agent
    are not, at any locus, because a property of a place and a relation between two places have no
    common subject to be about.
    """
    return bool(arities(alpha) & arities(beta))


def _first_reading(agent: SituatedAgent) -> Optional[Mapping[str, Any]]:
    return dict(agent.percept_field[0].reading.measurement) if agent.percept_field else None


def refuse_comparison(alpha: SituatedAgent, beta: SituatedAgent) -> str:
    """Ask #158's own function for the comparison, and return the refusal it raises.

    The point of routing through it rather than writing the sentence here: `compare_across_senses`
    is where this system records that no scale exists, and a second place saying so is a second
    place that can stop saying so. If it ever answers, that is a defect in the sensorium and this
    raises rather than passing the number on.
    """
    readings = [r for r in (_first_reading(alpha), _first_reading(beta)) if r is not None]
    try:
        value = chroma_organ.compare_across_senses(*readings)
    except chroma_organ.Incommensurable as exc:
        return str(exc)
    raise CompatibilityLeak(
        f"compare_across_senses returned {value!r} for {alpha.id} and {beta.id} instead of "
        f"refusing. A cross-sense magnitude is the single easiest way to make this system "
        f"confident about something it has never measured, and this layer will not carry one.")


# ── where three of them can meet ────────────────────────────────────────────

#: How a GROUP meeting is arranged. `meeting.RENDEZVOUS_RULES` says the same two things about a
#: pair; these are stated separately rather than reused because "the weaker of the two" and "the
#: weakest of the N" are different sentences, and a rule that goes on the record has to be the one
#: that was actually applied.
#:
#: Still the OBSERVER's rules. No agent sees another's horizon, and nothing here gives any of them
#: an interest in where the others are — the meeting is arranged and the travel is earned, exactly
#: as the move-and-meet lane found and named.
GROUP_WEAKEST = "strongest_weakest_leg"
GROUP_SUM = "strongest_combined"
GROUP_RULES: Dict[str, str] = {
    GROUP_WEAKEST: ("meet where the WEAKEST of the group's crossings is strongest — a meeting is "
                    "only as earned as its worst leg; ties broken by the meeting node id"),
    GROUP_SUM: ("meet where the group's crossings sum highest; ties broken by the meeting node id"),
}


@dataclass(frozen=True)
class GroupRendezvous:
    """One node EVERY member can reach on a measured crossing, with each member's leg."""
    node_id: str
    post_id: str
    region_id: str
    legs: Dict[str, Any]

    @property
    def weakest_leg(self) -> float:
        return min(float(r.systematicity) for r in self.legs.values())

    @property
    def combined(self) -> float:
        return round(sum(float(r.systematicity) for r in self.legs.values()), 6)

    def as_dict(self) -> Dict[str, Any]:
        return {"node_id": self.node_id, "post_id": self.post_id, "region_id": self.region_id,
                "weakest_leg": self.weakest_leg, "combined": self.combined,
                "legs": {aid: r.as_dict() for aid, r in self.legs.items()}}


def rendezvous_all(agents: Sequence[SituatedAgent],
                   horizons: Mapping[str, Sequence[Any]]) -> List[GroupRendezvous]:
    """Every node ALL of them can reach on a measured crossing. Computed, never chosen.

    The pairwise version generalises by intersection, and the move-and-meet lane predicted what
    that costs: it "gets emptier fast". It does — three horizons agree on far less than two — and
    the run reports the count so the reader can see how thin the group's common world is rather
    than being told it.

    Nodes any member already stands on are excluded, for the reason `meeting.rendezvous` gives:
    meeting where someone already is makes their journey zero steps, which is the staged meeting.
    """
    standing = {a.locus.node_id for a in agents}
    reachable = [{r.other_node: r for r in (horizons.get(a.id) or []) if r.reachable}
                 for a in agents]
    if not reachable:
        return []

    shared = set(reachable[0])
    for rows in reachable[1:]:
        shared &= set(rows)
    out: List[GroupRendezvous] = []
    for node_id in sorted(shared - standing):
        parsed = mv.parse_node_id(node_id)
        if parsed is None:
            continue
        out.append(GroupRendezvous(
            node_id=node_id, post_id=parsed[0], region_id=parsed[1],
            legs={a.id: rows[node_id] for a, rows in zip(agents, reachable)}))
    return out


def choose_group(options: Sequence[GroupRendezvous], *,
                 rule: str = GROUP_WEAKEST) -> Optional[GroupRendezvous]:
    """Pick one group meeting by a NAMED rule. `None` when the horizons do not all overlap."""
    if rule not in GROUP_RULES:
        raise ValueError(
            f"unknown group rendezvous rule {rule!r} — a meeting has to be arranged by something "
            f"a reader can look up, and {sorted(GROUP_RULES)} are the ones this lane states")
    if not options:
        return None
    if rule == GROUP_SUM:
        return max(options, key=lambda r: (r.combined, r.node_id))
    return max(options, key=lambda r: (r.weakest_leg, r.combined, r.node_id))


# ── the pairwise verdict ────────────────────────────────────────────────────

@dataclass(frozen=True)
class PairVerdict:
    """How two members of the society stand to each other, and what came of it."""
    left_id: str
    right_id: str
    outcome: str
    detail: str
    hypotheses: Tuple[Dict[str, Any], ...] = ()
    shared_subjects: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "left": self.left_id, "right": self.right_id, "outcome": self.outcome,
            "detail": self.detail, "shared_subjects": list(self.shared_subjects),
            "hypotheses": [h.get("hypothesis_id") for h in self.hypotheses],
        }


def relate(alpha: SituatedAgent, beta: SituatedAgent, *,
           atlas_id: str = "", now: str = "") -> PairVerdict:
    """One pair of co-located agents → what holds between them. Writes nothing.

    Order of questions matters and is not arbitrary:

      1. **Same body?** Asked first, because two copies of one world would otherwise pass the
         comparability test trivially and compose with themselves. `dialogue.exchange` is the one
         that knows this rule; it is called and its refusal is caught rather than pre-empted.
      2. **Comparable at all?** If not, the refusal comes from `compare_across_senses` and the pair
         is `incommensurable` — which is not a failure to find something, it is the absence of
         anything to find.
      3. **Did anything compose?** `dialogue.compose` decides; an empty result is `coexistent`,
         which is a real and common state and not an error.
    """
    stamp = now or obs_mod.utc_now()
    try:
        exchange_ = dialogue.exchange(alpha, beta)
    except ValueError as exc:
        if "SAME world twice" not in str(exc):
            raise
        return PairVerdict(alpha.id, beta.id, SAME_BODY, str(exc))

    silent = [a.id for a in (alpha, beta) if not a.percept_field]
    if silent:
        return PairVerdict(
            alpha.id, beta.id, UNDETERMINED,
            f"{silent} measured nothing at {alpha.locus.node_id}, so whether these two could be "
            f"about the same thing is not a question this locus can answer. An empty field is 'I "
            f"looked and found nothing here'; it is no evidence that there is nothing to find.")

    if not comparable(alpha, beta):
        return PairVerdict(alpha.id, beta.id, INCOMMENSURABLE, refuse_comparison(alpha, beta))

    shared = tuple(sorted(exchange_.both))
    # EARNED, not merely joint: each hypothesis carries how both contributors got here
    # (`meeting.earned_hypothesis`), so a society's artefacts say the same thing a pair's did and
    # a reader does not have to know which lane produced the row.
    journeys = [meeting.journey(alpha), meeting.journey(beta)]
    hypotheses = tuple(meeting.earned_hypothesis(h, journeys)
                       for h in dialogue.compose(exchange_, atlas_id=atlas_id, now=stamp))
    if not hypotheses:
        return PairVerdict(
            alpha.id, beta.id, COEXISTENT,
            f"{alpha.id} and {beta.id} can be about the same things and are not: "
            f"{len(shared)} shared subject(s), no pairing their organs compose over. Comparable "
            f"and with nothing in common is a fact about this locus, not about these bodies.",
            shared_subjects=shared)
    return PairVerdict(
        alpha.id, beta.id, COMPOSED,
        f"{len(hypotheses)} claim(s) neither made alone, over {len(shared)} shared subject(s)",
        hypotheses=hypotheses, shared_subjects=shared)


# ── the society ─────────────────────────────────────────────────────────────

@dataclass
class Society:
    """Three or more co-located, differently-bodied agents, and the structure between them."""
    members: List[SituatedAgent] = field(default_factory=list)
    verdicts: List[PairVerdict] = field(default_factory=list)

    @property
    def node_id(self) -> str:
        return self.members[0].locus.node_id if self.members else ""

    def by_outcome(self, outcome: str) -> List[PairVerdict]:
        return [v for v in self.verdicts if v.outcome == outcome]

    def hypotheses(self) -> List[Dict[str, Any]]:
        return [h for v in self.verdicts for h in v.hypotheses]

    def silent(self) -> List[str]:
        """Members that measured nothing here. They are in no comparability class, and putting
        them in one of their own would say they are incommensurable with everyone — which is a
        claim, and silence is not evidence for it."""
        return sorted(a.id for a in self.members if not a.percept_field)

    def classes(self) -> List[List[str]]:
        """The comparability partition: who could be about the same thing as whom.

        Transitive closure over `comparable`, so it is a property of the GROUP. With two agents
        there is one pair and no partition to speak of; the partition is the thing that only
        exists at three, and it is what "some compose, some only coexist" means precisely.

        Silent members are EXCLUDED rather than given singleton classes — see `silent`.
        """
        groups: List[List[SituatedAgent]] = []
        for agent in self.members:
            if not agent.percept_field:
                continue
            for group in groups:
                if any(comparable(agent, other) for other in group):
                    group.append(agent)
                    break
            else:
                groups.append([agent])
        return [sorted(a.id for a in group) for group in groups]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "members": [{"id": a.id, "organ_set": list(a.organ_set),
                         "measured": len(a.percept_field),
                         "arities": sorted(arities(a))} for a in self.members],
            "verdicts": [v.as_dict() for v in self.verdicts],
            "classes": self.classes(),
            "silent": self.silent(),
        }


def assert_a_society(agents: Sequence[SituatedAgent]) -> None:
    """Raise unless this is three or more agents with at least two bodies between them."""
    if len(agents) < MIN_MEMBERS:
        raise NotASociety(
            f"{len(agents)} agent(s) — this lane asks what appears at {MIN_MEMBERS}, and two is "
            f"the dialogue lane. A society of two would answer the question by changing it.")
    if len({tuple(sorted(a.organ_set)) for a in agents}) < 2:
        raise NotASociety(
            f"all {len(agents)} agents carry {sorted(agents[0].organ_set)}. Three copies of one "
            f"world is not a society, it is one world enacted three times — and every pair of them "
            f"would compose with itself.")
    if len({a.id for a in agents}) != len(agents):
        raise NotASociety("two members share an id — a society needs distinguishable members")


def convene(agents: Sequence[SituatedAgent], *, atlas_id: str = "", now: str = "",
            minimum_steps: int = meeting.MIN_STEPS) -> Society:
    """Every pair of a travelled, co-located, differently-bodied group → the structure between them.

    Each member must have WALKED here and PERCEIVED here — `meeting`'s two guards, applied to a
    group instead of a pair. They are not weakened by there being three: an agent that was placed
    at the meeting is in a staged one, and a third agent makes that easier to miss rather than
    less important.
    """
    stamp = now or obs_mod.utc_now()
    assert_a_society(agents)
    for agent in agents:
        meeting.assert_travelled(agent, minimum=minimum_steps)
        meeting.assert_perceived_here(agent)

    society = Society(members=list(agents))
    for i, left in enumerate(agents):
        for right in agents[i + 1:]:
            society.verdicts.append(relate(left, right, atlas_id=atlas_id, now=stamp))
    return society


# ── holding: the state that only exists at three ────────────────────────────

def hold_all(society: Society, *, now: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """Each member holds the hypotheses it CONTRIBUTED to, and is refused the rest.

    THE RULE THIS LANE ADDS. `DECISION-testimony-is-interpretive` says a belief composed partly
    from another agent's testimony is `interpretive`, with `contributed` vs `received` per mark.
    It is written for a belief the holder contributed *something* to, because with two agents that
    is the only kind there is: both members of a pair are contributors by construction.

    At three, γ stands in the room while α and β compose. `dialogue.hold` would record γ's copy
    without complaint as `contributed=0 received=2` — and a belief with no contribution at all is
    not testimony-weakened evidence, it is a claim no organ of the holder measured, which the
    situated-agent lane REFUSES as hearsay. The two rules meet here for the first time and the
    stricter one wins.

    Refused, never weakened to `uncertain` or held with a flag: a supported way to hold a wholly
    received claim is a supported way to launder one.
    """
    stamp = now or obs_mod.utc_now()
    held: Dict[str, List[Dict[str, Any]]] = {}
    for agent in society.members:
        rows: List[Dict[str, Any]] = []
        for hypothesis in society.hypotheses():
            if agent.id in [str(a) for a in (hypothesis.get("agent_ids") or [])]:
                rows.append(dialogue.hold(agent, hypothesis, now=stamp))
                continue
            rows.append({
                "at": stamp, "agent_id": agent.id, "kind": "refused_to_hold",
                "hypothesis_id": hypothesis.get("hypothesis_id"),
                "claim": hypothesis.get("claim"),
                "reason": WHOLLY_RECEIVED,
                "detail": (
                    f"{agent.id} contributed no mark to this claim — it was in the room when it "
                    f"was made. A belief that is entirely received is not weakened evidence, it "
                    f"is a claim no organ of this agent measured, and that is hearsay however "
                    f"many other agents stand behind it."),
            })
        held[agent.id] = rows
    return held


def held_beliefs(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows if str(r.get("kind") or "") != "refused_to_hold"]


def refusals_to_hold(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows if str(r.get("kind") or "") == "refused_to_hold"]


# ── the three-way outcome two agents cannot produce ─────────────────────────

def put_to(agent: SituatedAgent, hypothesis: Mapping[str, Any]) -> Dict[str, Any]:
    """Ask a member to state, in its own voice, a claim the society composed. Records the answer.

    The three-way outcome: two composed it, and the third is asked. There are exactly two honest
    answers and neither is agreement —

      · **refused (hearsay)** — no organ of this agent measured it. The usual case for γ, and the
        important one, because γ is standing in the same place and has just heard it said.
      · **restated** — this agent measured the same subject itself, so it can say it in its own
        voice. Not a vote and not corroboration: `movement_graph.strengthen` refuses to move a
        weight on agreement for the same reason.

    A measured CONTRADICTION is not among them and this lane does not manufacture one — see the
    module note. The guard is `situated_agent.attest`, through `dialogue.say`, reused rather than
    re-implemented.
    """
    contribution = next((c for c in (hypothesis.get("rests_on") or [])
                         if str(c.get("agent_id")) != agent.id), None)
    claim = {"relation": (contribution or {}).get("relation"),
             "other_region_id": hypothesis.get("about_region_id")}
    try:
        utterance = dialogue.say(agent, claim)
    except Hearsay as exc:
        return {"agent_id": agent.id, "hypothesis_id": hypothesis.get("hypothesis_id"),
                "claim": claim, "answer": "refused", "reason": "hearsay", "detail": str(exc)}
    return {"agent_id": agent.id, "hypothesis_id": hypothesis.get("hypothesis_id"),
            "claim": claim, "answer": "restated", "reason": "measured it too",
            "detail": utterance.detail,
            # SAID AGAIN, NOT CONFIRMED. Two agents measuring the same thing is two readings, and
            # a society that counted them as evidence would be learning what it already believed.
            "corroborates": False}
