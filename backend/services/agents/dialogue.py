"""WAVE3 — two agents at one locus: the exchange, and the first thing neither knew alone.

Two situated agents inhabit the SAME locus with DIFFERENT organ-sets. They do not see two views of
one world; they enact two worlds, because a world is what a body can measure from where it stands.
The exchange is where those two worlds meet, and the joint hypothesis is the one claim that needs
both of them.

## The composition this lane actually builds

    α (nestedness_organ)   the locus is INSIDE R
    β (adjacency_organ)    the locus MEETS R's boundary
    ────────────────────────────────────────────────────────
    joint                  the locus lies at R's RIM, not in its interior

That last line is not a conjunction of two facts about different things. It is a single
topological fact about one pair that **neither organ can state alone** — nestedness cannot tell a
part deep inside from a part at the lip, and adjacency cannot tell a neighbour outside from a part
at the lip. Put them together and the ambiguity in each is resolved by the other. That is the
smallest genuine emergence available, and it is checkable: `adjacency_organ`'s own tests pin the
2×2 (deep / rim / beside / far) that makes the four cases distinguishable.

## Two channels, kept apart because they answer to different rules

    EXCHANGE (ephemeral)   agent ↔ agent. Nothing is stored. Every utterance must trace to the
                           SPEAKING agent's own organ at this locus; anything else is `Hearsay`.
    BLACKBOARD (durable)   the joint hypothesis, `proposed`. It stores no status and cites both
                           agents' marks.

## A joint hypothesis is `proposed`, and it stays `proposed`

Not "until the marks are committed" — **full stop**. This is where it differs from an observation,
and the difference is the whole honesty floor of dialogue:

    an observation    cites ONE mark. Commit the mark and it reads what that mark says.
    a hypothesis      cites TWO marks and adds a claim NEITHER of them makes. Committing both
                      makes its inputs durable; it does not make the composition a measurement.

**Agreement is not grounding.** Two agents concurring is two readings, and a graph that treats
concurrence as evidence is a graph that learns what it already believes — the same reasoning
`movement_graph.strengthen` uses to refuse everything but a measured re-observation. A joint
hypothesis becomes measured knowledge by being re-grounded on NEW loci, which is a later lane.
`hydrate_hypothesis` therefore has no path to `measured`, and a test asserts there is none even
when every cited mark is committed.

## Where this lane departs from its card, and why

The card (and the situatedness finding §5) says agents may *hold* a joint hypothesis as `measured`
privately, on the private-vs-ledger decision. **It is held as `interpretive` here**, and the
reasoning is the honesty floor this same lane is asked to enforce: α did not measure β's half. The
decision entitles an agent to believe *what its own organs measured* without waiting for a curator
— it does not entitle it to promote what another agent told it. An agent privately holding as
`measured` a claim half of which arrived by testimony is hearsay with one extra step, and the extra
step is exactly what would make it invisible.

So each agent holds the composition, marked as resting on one mark of its own and one received —
`contributed` vs `received` on every held belief, so a reader can always see which half the agent
is entitled to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services import adjacency_organ, nestedness_organ
from backend.services.agents import observation as obs_mod
from backend.services.agents.situated_agent import (Hearsay, Perception, SituatedAgent, attest,
                                                    inhabit, overlay_posts, perceive,
                                                    proposed_marks, remember)
from backend.services.epistemics import STATUS_KEY, EpistemicStatus
from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

HYPOTHESIS_CONTRACT_VERSION = 1

DIALOGUE_STEP_ID = "wave3_dialogue:exchange"

#: The composition this lane knows how to make. One entry, named, because the next one is a
#: decision somebody makes rather than a pattern that accretes.
CLAIM_AT_THE_RIM = "nested_at_boundary"

#: What a held belief rests on. `contributed` is the half this agent's own organ measured;
#: `received` is the half it was told. Kept per-mark rather than per-belief because that is the
#: granularity at which the entitlement differs.
CONTRIBUTED = "contributed"
RECEIVED = "received"


class NotJoint(Exception):
    """A 'joint' hypothesis that only one agent stands behind."""


@dataclass(frozen=True)
class Utterance:
    """One agent saying what IT measured from the shared locus. Ephemeral — never stored.

    Carries `basis` and `admissible` because the listener needs them: under WAVE2.5 an estimate and
    a measurement are different kinds of thing, and a dialogue that flattened them would let one
    agent's box guess compose with another's mask measurement into something presented as firmer
    than either.
    """
    agent_id: str
    post_id: str
    region_id: str
    organ: str
    relation: str
    direction: str
    other_region_id: str
    epistemic_status: str
    basis: str
    admissible: bool
    mark_id: str
    detail: str

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    def __str__(self) -> str:
        return (f"{self.agent_id}, from {self.region_id}: {self.relation}/{self.direction} "
                f"{self.other_region_id} — {self.detail} [{self.epistemic_status}]")


def _utterance(agent: SituatedAgent, perception: Perception) -> Utterance:
    return Utterance(
        agent_id=agent.id,
        post_id=agent.locus.post_id,
        region_id=agent.locus.region_id,
        organ=perception.organ,
        relation=perception.reading.relation,
        direction=perception.reading.direction,
        other_region_id=perception.reading.other_region_id,
        epistemic_status=perception.epistemic_status,
        basis=perception.reading.basis,
        admissible=perception.reading.admissible,
        mark_id=str(perception.mark.get("id") or ""),
        detail=perception.reading.detail)


def speak(agent: SituatedAgent) -> List[Utterance]:
    """Everything this agent measured from here, as things it can say.

    Cannot produce hearsay by construction — it walks the percept field, and the field is built
    only from this agent's own organs at this locus. `say` is the door for a claim arriving from
    outside, and that is where the refusal lives.
    """
    return [_utterance(agent, p) for p in agent.percept_field]


def say(agent: SituatedAgent, claim: Mapping[str, Any]) -> Utterance:
    """One claim, checked against what this agent actually measured. Raises `Hearsay` if unbacked.

    The guard is `situated_agent.attest`, reused rather than reimplemented — a dialogue lane with
    its own copy of the hearsay rule is two rules that will disagree, and the one that disagrees
    quietly is the one in the room where claims are being exchanged.
    """
    return _utterance(agent, attest(agent, claim))


# ── the exchange ────────────────────────────────────────────────────────────

@dataclass
class Exchange:
    """What two agents at one locus said to each other. Ephemeral: this is never persisted."""
    locus: Dict[str, str]
    alpha_id: str
    beta_id: str
    alpha_said: List[Utterance] = field(default_factory=list)
    beta_said: List[Utterance] = field(default_factory=list)

    @property
    def alpha_regions(self) -> set:
        return {u.other_region_id for u in self.alpha_said}

    @property
    def beta_regions(self) -> set:
        return {u.other_region_id for u in self.beta_said}

    @property
    def only_alpha(self) -> set:
        """Regions α related the locus to and β did not. NOT an error on β's part — β's organ
        cannot see containment at all, so this is the shape of its blindness, and α's is the
        mirror image. The two sets differing IS the disagreement the lane is for."""
        return self.alpha_regions - self.beta_regions

    @property
    def only_beta(self) -> set:
        return self.beta_regions - self.alpha_regions

    @property
    def both(self) -> set:
        """The regions where a composition is even possible."""
        return self.alpha_regions & self.beta_regions

    def as_dict(self) -> Dict[str, Any]:
        return {
            "locus": dict(self.locus),
            "alpha": {"id": self.alpha_id, "said": [u.as_dict() for u in self.alpha_said]},
            "beta": {"id": self.beta_id, "said": [u.as_dict() for u in self.beta_said]},
            "only_alpha": sorted(self.only_alpha),
            "only_beta": sorted(self.only_beta),
            "both": sorted(self.both),
        }


def exchange(alpha: SituatedAgent, beta: SituatedAgent) -> Exchange:
    """Two agents state what each measured. Refuses a pair that is not actually co-located.

    Co-location is checked rather than assumed because the whole claim of this lane is that the
    DIFFERENCE between the two fields comes from the bodies, not from the positions. Two agents
    standing in different places would produce different fields for an entirely uninteresting
    reason, and the run would look exactly the same.
    """
    if alpha.locus != beta.locus:
        raise ValueError(
            f"{alpha.id} stands at {alpha.locus.node_id} and {beta.id} at {beta.locus.node_id}. "
            f"This lane is about two BODIES at one place; two places would explain the difference "
            f"in their fields without saying anything about their organs.")
    if alpha.id == beta.id:
        raise ValueError("an agent does not converse with itself")
    if set(alpha.organ_set) == set(beta.organ_set):
        raise ValueError(
            f"both agents carry {sorted(alpha.organ_set)}. Two identical bodies at one locus enact "
            f"the SAME world twice; any difference between their fields would be a difference in "
            f"bookkeeping, and a 'disagreement' between them would be staged.")

    return Exchange(locus=alpha.locus.as_dict(), alpha_id=alpha.id, beta_id=beta.id,
                    alpha_said=speak(alpha), beta_said=speak(beta))


# ── the joint hypothesis ────────────────────────────────────────────────────

def new_hypothesis_id() -> str:
    return f"ahyp_{uuid4().hex[:12]}"


#: Refused on the way in. `epistemic_status` for the reason the whole module exists; the others
#: because each would be a second copy of something the cited marks already answer.
_FORBIDDEN_HYPOTHESIS_KEYS = frozenset({
    STATUS_KEY, "epistemic", "measured", "grounded", "confirmed", "committed_at", "accepted_by",
})


def hypothesis_entry(*, claim: str, alpha: Utterance, beta: Utterance,
                     atlas_id: str = "", now: str = "") -> Dict[str, Any]:
    """Two grounded utterances → the row the blackboard stores. A proposal, and nothing stronger.

    Cites both marks and both agents. Stores no status: what kind of knowing the INPUTS are comes
    off their marks at read time, and what kind of knowing the COMPOSITION is has one answer
    (`proposed`) that `hydrate_hypothesis` supplies and no field can override.
    """
    stamp = now or obs_mod.utc_now()
    entry = {
        "hypothesis_id": new_hypothesis_id(),
        "contract_version": HYPOTHESIS_CONTRACT_VERSION,
        "claim": str(claim),
        "atlas_id": str(atlas_id) or None,
        "post_id": alpha.post_id,
        "region_id": alpha.region_id,
        "node_id": obs_mod.node_id_for(alpha.post_id, alpha.region_id),
        "about_region_id": alpha.other_region_id,
        "agent_ids": [alpha.agent_id, beta.agent_id],
        # WHAT IT RESTS ON, per contributor. Not a flat list of mark ids: a reader must be able to
        # see which agent and which organ stands behind each half, because that is what makes the
        # composition auditable rather than merely attributed.
        "rests_on": [
            {"agent_id": alpha.agent_id, "organ": alpha.organ, "mark_id": alpha.mark_id,
             "relation": alpha.relation, "basis": alpha.basis, "detail": alpha.detail},
            {"agent_id": beta.agent_id, "organ": beta.organ, "mark_id": beta.mark_id,
             "relation": beta.relation, "basis": beta.basis, "detail": beta.detail},
        ],
        "source": obs_mod.AGENT_PROPOSED_SOURCE,
        "created_at": stamp,
    }
    assert_valid_hypothesis(entry)
    return entry


def assert_valid_hypothesis(h: Mapping[str, Any]) -> None:
    """Raise unless this is a well-formed joint hypothesis that claims nothing on its own."""
    missing = [k for k in ("hypothesis_id", "claim", "post_id", "region_id", "node_id",
                           "agent_ids", "rests_on", "source", "created_at") if k not in h]
    if missing:
        raise NotJoint(f"hypothesis {h.get('hypothesis_id')!r} is missing {missing}")

    forbidden = sorted(k for k in _FORBIDDEN_HYPOTHESIS_KEYS if k in h)
    if forbidden:
        raise NotJoint(
            f"a joint hypothesis may not carry {forbidden}. It is a composition over two "
            f"measurements, not a measurement — and agreement is not grounding. What kind of "
            f"knowing its inputs are comes from their marks; the composition itself is `proposed` "
            f"and there is no field that can say otherwise.")

    agents = {str(a) for a in (h.get("agent_ids") or [])}
    rests = list(h.get("rests_on") or [])
    if len(agents) < 2 or len(rests) < 2:
        raise NotJoint(
            f"a JOINT hypothesis needs two agents behind it — this one has {len(agents)} agent(s) "
            f"and {len(rests)} contribution(s). One agent composing with itself is not a dialogue, "
            f"it is a single view with two names on it.")
    if any(not str(r.get("mark_id") or "") for r in rests):
        raise NotJoint("a contribution with no mark cites no measurement — that is hearsay")
    if {str(r.get("agent_id")) for r in rests} != agents:
        raise NotJoint("the agents named on the hypothesis and the agents behind its marks differ")


def compose(exchange_: Exchange, *, atlas_id: str = "", now: str = "") -> List[Dict[str, Any]]:
    """Where the two views compose into a claim neither made alone.

    Only where BOTH agents related the locus to the same region R, one saying `nested_within` and
    the other `meets`. That pairing is the whole content: inside-and-touching-the-rim is a position
    neither organ can report by itself.

    Returns proposals. Nothing is written here.
    """
    stamp = now or obs_mod.utc_now()
    by_region_nested: Dict[str, Utterance] = {}
    by_region_meets: Dict[str, Utterance] = {}

    for utterance in (*exchange_.alpha_said, *exchange_.beta_said):
        if utterance.relation == nestedness_organ.RELATION_NESTED_WITHIN \
                and utterance.direction == "within":
            by_region_nested.setdefault(utterance.other_region_id, utterance)
        elif utterance.relation == adjacency_organ.RELATION_MEETS:
            by_region_meets.setdefault(utterance.other_region_id, utterance)

    out: List[Dict[str, Any]] = []
    for region_id in sorted(set(by_region_nested) & set(by_region_meets)):
        nested, meets = by_region_nested[region_id], by_region_meets[region_id]
        # Two utterances from ONE agent are not a dialogue. This can happen the moment an agent
        # carries both organs, which is a perfectly legal configuration — so it is checked here
        # rather than assumed away by how the run happens to be set up.
        if nested.agent_id == meets.agent_id:
            continue
        out.append(hypothesis_entry(
            claim=CLAIM_AT_THE_RIM, alpha=nested, beta=meets, atlas_id=atlas_id, now=stamp))
    return out


# ── hydration: the composition has one status, and it is not `measured` ─────

def hydrate_hypothesis(h: Mapping[str, Any],
                       posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """One stored hypothesis + the posts → what a reader gets.

    `rests_on` is hydrated per contribution, so a reader can see which halves a curator has
    committed. `ledger_status` is `proposed` and there is no branch that makes it anything else —
    not when one mark is committed, not when both are. That is the point, and it is why this
    function has no `if` on the mark count.
    """
    hydrated = []
    live = 0
    for contribution in h.get("rests_on") or []:
        mark = obs_mod.find_mark(posts.get(str(h.get("post_id"))),
                                 str(contribution.get("mark_id") or ""))
        if mark is not None:
            live += 1
        hydrated.append({
            **dict(contribution),
            "live": mark is not None,
            "epistemic": (str(mark.get(STATUS_KEY) or "") or None) if mark else None,
        })

    total = len(hydrated)
    return {
        **dict(h),
        "rests_on": hydrated,
        "marks_live": f"{live}/{total}",
        # NO BRANCH. Committing every cited mark makes the INPUTS durable; the composition is still
        # a reading over them, and two agents concurring is two readings.
        "ledger_status": obs_mod.LEDGER_PROPOSED,
        "detail_ledger": (
            "a joint hypothesis is a composition over two measurements, not a measurement. "
            "Committing its marks makes what it rests on durable; it does not make the "
            "composition grounded. That takes re-grounding on new loci — a later lane."),
    }


# ── what each agent privately holds ─────────────────────────────────────────

def hold(agent: SituatedAgent, hypothesis: Mapping[str, Any], *,
         now: str = "") -> Dict[str, Any]:
    """Record a joint hypothesis in one agent's episodic memory, as a READING it holds.

    `interpretive`, not `measured`, and this is where this lane departs from its card. The
    private-vs-ledger decision entitles an agent to believe what ITS OWN ORGANS measured without
    waiting for a curator. It does not entitle it to promote what another agent told it. Half of
    this claim arrived by testimony, and an agent privately holding it as `measured` would be
    laundering hearsay through one extra step — which is precisely the step that would make it
    invisible to the guard this same lane is asked to keep.

    So the belief carries `contributed` vs `received` per mark, and a reader can always see which
    half the agent is entitled to.
    """
    stamp = now or obs_mod.utc_now()
    mine = {str(m.get("id") or "") for m in proposed_marks(agent)}
    rests = [{**dict(c),
              "standing": CONTRIBUTED if str(c.get("mark_id")) in mine else RECEIVED}
             for c in (hypothesis.get("rests_on") or [])]

    entry = {
        "at": stamp,
        "agent_id": agent.id,
        "locus": agent.locus.as_dict(),
        "node_id": agent.locus.node_id,
        "kind": "joint_hypothesis",
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "claim": hypothesis.get("claim"),
        "about_region_id": hypothesis.get("about_region_id"),
        # A READING over two measurements — the strongest thing a composition can be.
        STATUS_KEY: EpistemicStatus.INTERPRETIVE.value,
        "rests_on": rests,
        "contributed": sum(1 for r in rests if r["standing"] == CONTRIBUTED),
        "received": sum(1 for r in rests if r["standing"] == RECEIVED),
    }
    agent.memory.append(entry)
    return entry


# ── persistence ─────────────────────────────────────────────────────────────

def _collection(collection=None):
    if collection is not None:
        return collection
    from backend.database import agent_hypothesis_collection
    return agent_hypothesis_collection


async def write_hypothesis(h: Mapping[str, Any], *, collection=None) -> Dict[str, Any]:
    """Store one joint hypothesis. Writes to `agent_hypotheses` and nothing else — never a post."""
    assert_valid_hypothesis(h)
    doc = dict(h)
    await _collection(collection).insert_one(doc)
    doc.pop("_id", None)
    return doc


# ── the run ─────────────────────────────────────────────────────────────────

async def run_dialogue(*, post: Mapping[str, Any], region_id: str,
                       alpha_organs: Sequence[str] = (), beta_organs: Sequence[str] = (),
                       alpha_id: str = "alpha", beta_id: str = "beta",
                       atlas_id: str = "", persist: bool = False, collection=None,
                       now: str = "") -> Dict[str, Any]:
    """Two agents inhabit → perceive → exchange → compose, with the transcript a human reads.

    `persist=False` runs everything and writes nothing; every hypothesis is still minted and
    VALIDATED through `assert_valid_hypothesis`, so a dry run proves the same contract a stored one
    would. `persist=True` writes to `agent_hypotheses` and to nothing else — never a post, and
    never a mark: the organ marks the two agents produced are RETURNED in the transcript so a
    curator can see what a commit would mean, and this function is not entitled to perform it.

    The post is hashed before and after regardless, the same way `run_agent` does. Suggestions-only
    is a claim this function checks rather than makes.
    """
    stamp = now or obs_mod.utc_now()
    post_id = str(post.get("_id") or post.get("id") or "")
    posts = {post_id: post}
    before = posts_fingerprint(posts)

    alpha = inhabit(agent_id=alpha_id, post_id=post_id, region_id=region_id,
                    organ_set=tuple(alpha_organs) or (nestedness_organ.ORGAN,))
    beta = inhabit(agent_id=beta_id, post_id=post_id, region_id=region_id,
                   organ_set=tuple(beta_organs) or (adjacency_organ.ORGAN,))

    transcript: Dict[str, Any] = {
        "step_id": DIALOGUE_STEP_ID, "at": stamp,
        "locus": alpha.locus.as_dict(),
        "agents": [{"id": a.id, "organ_set": list(a.organ_set)} for a in (alpha, beta)],
    }

    for agent in (alpha, beta):
        perceive(agent, post, now=stamp)
        remember(agent, now=stamp)

    # The two fields side by side, BEFORE any composition. The disagreement is the finding, and it
    # has to be readable without trusting the composition step that follows it.
    transcript["fields"] = {
        a.id: [p.as_dict() for p in a.percept_field] for a in (alpha, beta)
    }

    exchange_ = exchange(alpha, beta)
    transcript["exchange"] = exchange_.as_dict()

    hypotheses = compose(exchange_, atlas_id=atlas_id, now=stamp)
    for h in hypotheses:
        assert_valid_hypothesis(h)
    transcript["hypotheses"] = hypotheses

    # Each agent's private holding, with `contributed` vs `received` visible per mark.
    transcript["held"] = {
        a.id: [hold(a, h, now=stamp) for h in hypotheses] for a in (alpha, beta)
    }

    marks = [*proposed_marks(alpha), *proposed_marks(beta)]
    transcript["proposed_marks"] = marks

    # BOTH READINGS, and for a hypothesis they are DELIBERATELY IDENTICAL on `ledger_status`. That
    # is not a redundant pair — printing them side by side is how the run demonstrates that
    # committing every cited mark changes `marks_live` and changes nothing else.
    overlaid = overlay_posts(posts, marks)
    transcript["hydrated"] = [{
        "as_stored": hydrate_hypothesis(h, posts),
        "with_proposed_marks": hydrate_hypothesis(h, overlaid),
    } for h in hypotheses]

    transcript["persisted"] = {"hypotheses": []}
    if persist:
        for h in hypotheses:
            stored = await write_hypothesis(h, collection=collection)
            transcript["persisted"]["hypotheses"].append(stored["hypothesis_id"])

    assert_posts_unchanged(before, posts_fingerprint(posts))
    transcript["posts_unchanged"] = True
    return transcript


async def list_hypotheses(*, post_id: str = "", atlas_id: str = "", limit: int = 100,
                          collection=None) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if post_id:
        query["post_id"] = str(post_id)
    if atlas_id:
        query["atlas_id"] = str(atlas_id)
    out: List[Dict[str, Any]] = []
    async for doc in _collection(collection).find(query).limit(int(limit)):
        doc.pop("_id", None)
        out.append(doc)
    return out
