"""WAVE3 — the first situated agent: inhabit a locus, perceive through bound organs, report.

A conventional vision system *processes* an image: the whole frame goes in, a result comes out,
from nowhere in particular. This inhabits a locus inside one, and everything it knows is knowledge
**from where it stands**. That is not decoration — it is the constraint the whole module is built
around, and `_perceptions_for` is where it bites: an agent may only hold measurements that have
its own locus as one of their terms.

## The loop this wave builds, and the two it does not

    inhabit   →   perceive   →   record (private)   →   report (shared)          ← this lane
                                                    →   move → converse         ← the next lanes

No movement (that lane is gated on the retina/density rebuild) and no dialogue (that needs a
second agent). One agent, one locus, single image.

## The one line running through all of it

`DECISION-measured-private-vs-shared-ledger`, applied twice in the same function call:

    remember()   the agent's episodic, first-person record reads `measured`. It lives on what its
                 organs measured and does not wait for a human to believe its own eyes.
    report()     the shared ledger gets a suggestion that stores NO status and derives one from
                 the mark. Proposed until a curator commits.

Both come from the SAME organ reading. That is what makes the distinction legible rather than
decorative: a reader can put the private record and the public row side by side, see one say
`measured` and the other say `proposed`, and know that the difference is not a difference in
evidence — it is the human act nobody has performed yet.

## Where confabulation would hide, and what stands in its way

"I, standing here, experienced X" is a very persuasive sentence, and an agent is the richest place
in this system for one to hide. Four things stand in the way, none of them a promise:

  1. **No thinker is reachable.** `backend/services/agents/` imports no LLM client, and the test
     suite asserts it structurally over the whole package rather than trusting this paragraph.
     A claim without an organ behind it cannot be generated here, let alone published.
  2. **`attest` refuses hearsay.** A claim handed to the agent from outside is checked against its
     percept field and refused if no organ of its own measured it — and refused separately if it
     is about somewhere the agent is not standing.
  3. **The locus constraint.** A nesting between two regions the agent is not on is not knowledge
     it could have from here, and it never enters the field. `perceive` cannot produce a god's-eye
     reading even when the post is full of them.
  4. **Posts are hashed before and after.** Suggestions-only is checked, not claimed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.schemas.soft_fields import Percept, RegionGround
from backend.services import epistemics
from backend.services.agents import observation as obs_mod
from backend.services.agents import organs
from backend.services.agents.organs import OrganReading
from backend.services.epistemics import STATUS_KEY, EpistemicStatus
from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

AGENT_STEP_ID = "wave3_situated_agent:perceive"

#: The `kind` an agent's percept carries, and it is deliberately NEITHER of the two lineages
#: `percept_lineage` names. An expression percept is the curator's durable act of noticing; a draft
#: is a director proposal on its way to becoming a mark. This is a third thing — what an agent
#: measured from where it stands — and giving it `kind: "expression"` would have made an agent's
#: reading indistinguishable from a curator's in the one field SF-001B's census proved clean.
#:
#: `test_situated_agent_wave3.py` asserts the classifier reads these as neither.
AGENT_PERCEPT_KIND = "agent_percept"


class Hearsay(Exception):
    """A claim no organ of this agent measured from this locus. Refused, never weakened.

    Named for what it is in the situatedness finding: *"a claim must trace to an organ … otherwise
    it is `hearsay`, not admissible."* Deliberately NOT an `EpistemicStatus` — the five statuses
    answer "how is this known", and hearsay is the answer "it is not known by this agent at all",
    which is a thing to refuse rather than a kind to record. A sixth status would have created a
    supported way to publish one.
    """


@dataclass(frozen=True)
class Locus:
    """Where an agent stands. Single image, single region — this wave's whole extent.

    A locus that binds regions across several images is what makes an agent's world a constellation
    rather than a frame, and it is the movement lane's, not this one's.
    """
    post_id: str
    region_id: str

    @property
    def node_id(self) -> str:
        return obs_mod.node_id_for(self.post_id, self.region_id)

    def as_dict(self) -> Dict[str, str]:
        return {"post_id": self.post_id, "region_id": self.region_id}


@dataclass(frozen=True)
class Perception:
    """One organ reading, as the agent's world contains it: typed percept, typed grounds, evidence.

    The SF-002 types are used for the field's CONTENT and nothing here ever reaches `post.percepts`
    or `post.grounds`. That is the point of typing it: an agent's field and a curator's ledger are
    now the same shape, so the day an agent's reading is offered for commit, the offer is a
    conversion nobody has to write.

    `epistemic_status` is read off the organ's mark rather than stored, for the reason
    `nestedness_organ.measured_mark` gives: the organ that did the measuring is the only thing
    entitled to say what kind of knowing its output is.
    """
    organ: str
    reading: OrganReading
    percept: Percept
    grounds: Tuple[RegionGround, ...]

    @property
    def epistemic_status(self) -> str:
        return self.reading.epistemic_status

    @property
    def mark(self) -> Dict[str, Any]:
        return self.reading.mark

    def as_dict(self) -> Dict[str, Any]:
        return {
            "organ": self.organ,
            "relation": self.reading.relation,
            "direction": self.reading.direction,
            "locus_region_id": self.reading.locus_region_id,
            "other_region_id": self.reading.other_region_id,
            "epistemic_status": self.epistemic_status,
            "detail": self.reading.detail,
            "percept": self.percept.model_dump(mode="json"),
            "grounds": [g.model_dump(mode="json") for g in self.grounds],
            "mark_id": str(self.mark.get("id") or ""),
        }


@dataclass
class SituatedAgent:
    """A light stateful process, not a resident model.

    The expensive thing is the organ, which is residency-managed and shared; this is a handful of
    dicts and a position. That asymmetry is what makes a population of agents affordable on a 16 GB
    machine, and it is why nothing here holds a model, opens a socket, or caches a tensor.

    `horizon` from the situatedness finding's data shape is deliberately absent: it is the set of
    grounded axes this agent could move along, and this wave has no movement. An empty field
    claiming a reachable world would be worse than no field.
    """
    id: str
    locus: Locus
    organ_set: Tuple[str, ...]
    temperament: str = ""
    percept_field: List[Perception] = field(default_factory=list)
    trajectory: List[Dict[str, Any]] = field(default_factory=list)
    memory: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "locus": self.locus.as_dict(),
            "node_id": self.locus.node_id,
            "organ_set": list(self.organ_set),
            "temperament": self.temperament,
            "percept_field": [p.as_dict() for p in self.percept_field],
            "trajectory": list(self.trajectory),
            "memory": list(self.memory),
        }


# ── 1. inhabit ───────────────────────────────────────────────────────────────

def inhabit(*, agent_id: str = "", post_id: str, region_id: str,
            organ_set: Sequence[str], temperament: str = "") -> SituatedAgent:
    """Place an agent at a locus with a body. Refuses a body it cannot perceive through.

    Every organ is resolved HERE rather than at first use, because an agent whose organ set is half
    imaginary has a world that is half imaginary, and the failure would otherwise surface as a
    thin percept field — which is indistinguishable from a locus that affords little.
    """
    if not organ_set:
        raise organs.OrganRefusal(
            "an agent with no organs has no world — situatedness is the pairing (locus × organ "
            "set), and half of it missing is not a degraded agent, it is not an agent")
    for name in organ_set:
        organs.assert_invocable(name)
    return SituatedAgent(
        id=str(agent_id) or f"agent_{uuid4().hex[:8]}",
        locus=Locus(post_id=str(post_id), region_id=str(region_id)),
        organ_set=tuple(str(o) for o in organ_set),
        temperament=str(temperament))


# ── 2. perceive ──────────────────────────────────────────────────────────────

def _grounds_for(reading: OrganReading, *, organ: str, now: str) -> Tuple[RegionGround, ...]:
    """The two regions the measurement rests on, as SF-002 region grounds.

    A region ground is "a reference, never a duplication" (`soft_fields.RegionGround`) — it carries
    `region_id` and no geometry, so a re-dissect degrades it gracefully instead of leaving it
    holding stale coordinates. Exactly the right shape for an agent, whose whole claim is about
    where it stands rather than about pixel values it copied.

    `actor="auto"` with `detector` naming the organ is the vocabulary the schema already has for
    "a machine found this", and it means an agent's ground is legible to the same reader as a
    detector's without a new field.

    `ground_type` IS PASSED EXPLICITLY even though the class declares it as a `Literal` default,
    and that is not redundancy — it is Lane G's declare-and-set rule arriving in SF-002's clothing.
    `SoftFieldModel` emits only `__pydantic_fields_set__`, and SF-002 says so on purpose ("the
    schema will not quietly speak on its behalf"), so a `RegionGround` built without this argument
    dumps with NO `ground_type` at all — and the discriminated union then re-validates it as
    `UndeclaredGround`. The ground would survive every round trip while quietly ceasing to be a
    region ground. `test_situated_agent_wave3.py` pins both halves.
    """
    return tuple(
        RegionGround(id=f"agnd_{uuid4().hex[:12]}", ground_type="region", actor="auto",
                     detector=organ, region_id=region_id, created_at=now)
        for region_id in (reading.locus_region_id, reading.other_region_id))


def _percept_for(reading: OrganReading, grounds: Sequence[RegionGround]) -> Percept:
    """What the agent noticed, in the organ's own vocabulary.

    The expression names TWO REGION IDS and a relation. No label, no category, nothing about what
    either region depicts — the same discipline `nestedness_organ` keeps for its mark detail, and
    for the same reason: a sentence a second reader can check against the numbers is the only kind
    an organ is entitled to author.

    `actor` is deliberately left UNSET rather than filled in. The field's own comment says
    `creator | audience — never a producer name`, and an agent is neither; `SoftFieldModel` emits
    only what was set, so the percept simply declines to claim a human authorship it does not have.
    Who produced it is on the grounds' `detector` and on the mark's provenance, where it belongs.
    """
    within = reading.direction == "within"
    subject, held = ((reading.locus_region_id, reading.other_region_id) if within
                     else (reading.other_region_id, reading.locus_region_id))
    fields: Dict[str, Any] = {
        "id": f"apc_{uuid4().hex[:12]}",
        "kind": AGENT_PERCEPT_KIND,
        "expression": f"{subject} nested within {held}",
        "ground_ids": [g.id for g in grounds],
    }
    # PASSED ONLY WHEN THERE IS ONE, never as an explicit None. `SoftFieldModel` emits what was
    # SET, so `created_at=None` would put a null on the wire — the precise thing SF-002's serializer
    # exists to prevent, and the habit is worth keeping even here, where nothing reaches a post.
    if reading.mark.get("created_at"):
        fields["created_at"] = str(reading.mark["created_at"])
    return Percept(**fields)


def _perceptions_for(readings: Sequence[OrganReading], *, organ: str, locus: Locus,
                     now: str) -> List[Perception]:
    out: List[Perception] = []
    for reading in readings:
        # THE LOCUS CONSTRAINT, checked rather than assumed. `organs.invoke` builds only readings
        # that have the locus as a term, so this can only fire if that changes — which is exactly
        # when it must. A percept field that quietly widened to the whole image would still look
        # like a situated agent from the outside, and every claim it made would be a claim from
        # nowhere wearing a first-person pronoun.
        if reading.locus_region_id != locus.region_id:
            raise Hearsay(
                f"a reading about region {reading.locus_region_id!r} reached an agent standing on "
                f"{locus.region_id!r} — that is not knowledge this agent could have from here")
        grounds = _grounds_for(reading, organ=organ, now=now)
        out.append(Perception(organ=organ, reading=reading,
                              percept=_percept_for(reading, grounds), grounds=grounds))
    return out


def perceive(agent: SituatedAgent, post: Mapping[str, Any], *,
             step_id: str = AGENT_STEP_ID, now: str = "") -> List[Perception]:
    """Bind the agent's organs to its locus, invoke them, and populate its percept field.

    The world is brought forth by the coupling of this body to this place: change either and the
    agent is somewhere else. Nothing global is consulted, nothing is narrated, and the field that
    comes back is exactly what these organs could measure from this position — which is frequently
    less than the image contains, and that partiality is the engine rather than the flaw.

    An EMPTY field is a real answer. It means the organs looked from here and measured nothing,
    which is a fact about the locus. `organs.invoke` raises instead when no organ looked at all.
    """
    stamp = now or obs_mod.utc_now()
    if str(post.get("_id") or post.get("id") or "") != agent.locus.post_id:
        raise organs.OrganRefusal(
            f"agent {agent.id} stands in post {agent.locus.post_id} and was handed "
            f"{post.get('_id') or post.get('id')!r} — an agent perceiving a picture it is not in "
            f"is the god's-eye read this whole module is arranged against")

    field_: List[Perception] = []
    per_organ: List[Dict[str, Any]] = []
    for organ_name in agent.organ_set:
        readings = organs.invoke(organ_name, post=post, region_id=agent.locus.region_id,
                                 step_id=step_id, now=stamp)
        perceptions = _perceptions_for(readings, organ=organ_name, locus=agent.locus, now=stamp)
        field_.extend(perceptions)
        per_organ.append({"organ": organ_name, "measured": len(perceptions)})

    agent.percept_field = field_
    agent.trajectory.append({
        "at": stamp,
        "locus": agent.locus.as_dict(),
        "node_id": agent.locus.node_id,
        "organ_set": list(agent.organ_set),
        "organs": per_organ,
        "measured": len(field_),
        # The denominator, so "measured 2" is a coverage claim rather than a number. A field of 2
        # out of 3 candidate regions and one of 2 out of 40 are different reports about a locus.
        "regions_in_reach": len(post.get("region_annotations") or []),
        "step_id": step_id,
    })
    return field_


# ── 3. record — episodic, private, measured ──────────────────────────────────

def remember(agent: SituatedAgent, *, now: str = "") -> List[Dict[str, Any]]:
    """Write the perception into the agent's first-person memory, as MEASURED evidence.

    This is the yes-half of the decision, and the word `measured` appears here for one reason: the
    organ computed it from the image signal, and `EpistemicStatus.MEASURED` means exactly that. It
    is not a confidence, not a vote, and not the agent's opinion of its own reliability — which is
    why it is copied off the mark rather than chosen here.

    Private, and that is a claim about REACH rather than about secrecy: nothing in this list is
    visible to another agent or to the ledger. `report` is the only door out, and it opens onto
    `proposed`.
    """
    stamp = now or obs_mod.utc_now()
    written: List[Dict[str, Any]] = []
    for perception in agent.percept_field:
        entry = {
            "at": stamp,
            "agent_id": agent.id,
            "locus": agent.locus.as_dict(),
            "node_id": agent.locus.node_id,
            "organ": perception.organ,
            "relation": perception.reading.relation,
            "direction": perception.reading.direction,
            "other_region_id": perception.reading.other_region_id,
            # THE PRIVATE VIEW, and the only place in this lane that stores the word.
            STATUS_KEY: perception.epistemic_status,
            "basis": perception.reading.measurement.get("basis"),
            "nesting_index": perception.reading.measurement.get("nesting_index"),
            "detail": perception.reading.detail,
            "mark_id": str(perception.mark.get("id") or ""),
            "percept_id": perception.percept.id,
        }
        written.append(entry)
    agent.memory.extend(written)
    return written


# ── 4. report — shared, proposed ─────────────────────────────────────────────

def _matches(perception: Perception, claim: Mapping[str, Any]) -> bool:
    reading = perception.reading
    for key, value in (("relation", reading.relation),
                       ("direction", reading.direction),
                       ("other_region_id", reading.other_region_id),
                       ("organ", perception.organ)):
        wanted = claim.get(key)
        if wanted is not None and str(wanted) != str(value):
            return False
    return True


def attest(agent: SituatedAgent, claim: Mapping[str, Any]) -> Perception:
    """Check a claim against what this agent actually measured. The honesty gate.

    Two refusals, kept apart because they are different mistakes:

      · **not where I stand** — the claim is about another locus. Even a true statement about
        another region is not this agent's to make; situatedness means knowledge is indexed to a
        position, and a first-person report about somewhere else is a report from nowhere.
      · **no organ of mine measured that** — the claim is about the right place and nothing in the
        percept field backs it.

    `report()` cannot produce hearsay by construction, because it walks the percept field. This
    exists for the path where a sentence arrives from OUTSIDE the agent — a planner, a dialogue
    partner in the next lane, a prompt — which is the path where a fluent claim about a locus is
    most likely to be right-sounding and unmeasured.
    """
    region_id = claim.get("region_id") or claim.get("locus_region_id")
    if region_id is not None and str(region_id) != agent.locus.region_id:
        raise Hearsay(
            f"agent {agent.id} stands on {agent.locus.region_id!r} and was asked to attest to a "
            f"claim about {str(region_id)!r} — a first-person report about somewhere the agent is "
            f"not is a report from nowhere, however true it happens to be")

    for perception in agent.percept_field:
        if _matches(perception, claim):
            return perception

    raise Hearsay(
        f"agent {agent.id} has no organ reading behind {dict(claim)!r}. Its {len(agent.organ_set)} "
        f"organ(s) measured {len(agent.percept_field)} thing(s) from "
        f"{agent.locus.node_id} and this is not one of them — a claim without an organ behind it "
        f"is hearsay, not admissible.")


def _guard_marks(perceptions: Sequence[Perception]) -> None:
    """Run every mark this report rests on through the epistemic guard before publishing.

    Not ceremony. `epistemics.guard` is the single place where a claim's stated kind is checked
    against the kind its producer is classified as, and until this lane classified
    `nestedness_organ` the guard REFUSED the organ's own `measured` marks — the organ was unknown
    to both classification tables, so it was entitled to claim nothing but `uncertain`. Lane M
    never called the guard, so nothing surfaced it. Calling it here is what makes the honesty floor
    a check rather than a sentence in a docstring.
    """
    epistemics.guard([{
        "producer": (p.mark.get("provenance") or {}).get("producer"),
        "type": p.mark.get("type"),
        STATUS_KEY: p.mark.get(STATUS_KEY),
    } for p in perceptions])


def observe(agent: SituatedAgent, claim: Mapping[str, Any], *,
            atlas_id: str = "", now: str = "") -> Dict[str, Any]:
    """One attested claim → one proposed observation. Raises `Hearsay` if no organ backs it."""
    perception = attest(agent, claim)
    _guard_marks([perception])
    return obs_mod.observation_entry(
        agent_id=agent.id, post_id=agent.locus.post_id, region_id=agent.locus.region_id,
        organ=perception.organ, relation=perception.reading.relation,
        direction=perception.reading.direction, mark_id=str(perception.mark.get("id") or ""),
        detail=perception.reading.detail, atlas_id=atlas_id, now=now)


def report(agent: SituatedAgent, *, atlas_id: str = "", now: str = "") -> List[Dict[str, Any]]:
    """The agent's partial situated view, as suggestions on the shared ledger.

    Legible as "agent α, from locus L, measured X": the row carries the agent, the locus, the organ
    and the mark, and it carries no status — `hydrate_observation` reads that off the mark every
    time, so the report says `proposed` until a curator commits, and says so structurally.

    PARTIAL is the operative word. This is what one body measured from one place, and there is no
    field on the row that would let it be mistaken for a statement about the image.
    """
    _guard_marks(agent.percept_field)
    return [
        obs_mod.observation_entry(
            agent_id=agent.id, post_id=agent.locus.post_id, region_id=agent.locus.region_id,
            organ=p.organ, relation=p.reading.relation, direction=p.reading.direction,
            mark_id=str(p.mark.get("id") or ""), detail=p.reading.detail,
            atlas_id=atlas_id, now=now)
        for p in agent.percept_field
    ]


def proposed_marks(agent: SituatedAgent) -> List[Dict[str, Any]]:
    """The organ marks this agent's report rests on. RETURNED, never committed."""
    return [dict(p.mark) for p in agent.percept_field]


def overlay_posts(posts: Mapping[str, Mapping[str, Any]],
                  marks: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Posts as they WOULD be if these marks were committed — in memory, never saved.

    The same device `movement_kernel.overlay_posts` uses, and it is how a run shows what its
    observations would mean without performing the commit it is not entitled to perform.
    """
    out = {str(pid): dict(post) for pid, post in (posts or {}).items()}
    for mark in marks or []:
        pid = str(mark.get("post_id") or "")
        if pid not in out:
            continue
        out[pid] = {**out[pid], "visual_marks": [*(out[pid].get("visual_marks") or []), dict(mark)]}
    return out


# ── the run ──────────────────────────────────────────────────────────────────

async def run_agent(*, post: Mapping[str, Any], region_id: str,
                    organ_set: Sequence[str] = (), agent_id: str = "", temperament: str = "",
                    atlas_id: str = "", persist: bool = False, collection=None,
                    now: str = "") -> Dict[str, Any]:
    """Inhabit → perceive → remember → report, with the transcript a human reads.

    `persist=False` runs everything and writes nothing; the observations are minted and VALIDATED
    through `assert_valid_observation`, so a dry run proves the same contract a stored one would.
    `persist=True` writes to `agent_observations` and to nothing else — never a post.

    The post is hashed before and after regardless. Suggestions-only is a claim this function
    checks rather than makes.
    """
    from backend.services import nestedness_organ

    stamp = now or obs_mod.utc_now()
    post_id = str(post.get("_id") or post.get("id") or "")
    posts = {post_id: post}
    before = posts_fingerprint(posts)

    agent = inhabit(agent_id=agent_id, post_id=post_id, region_id=region_id,
                    organ_set=tuple(organ_set) or (nestedness_organ.ORGAN,),
                    temperament=temperament)

    transcript: Dict[str, Any] = {
        "step_id": AGENT_STEP_ID, "at": stamp,
        "agent": {"id": agent.id, "locus": agent.locus.as_dict(), "node_id": agent.locus.node_id,
                  "organ_set": list(agent.organ_set), "temperament": agent.temperament},
        # How each organ name resolved, in the transcript rather than only in a raised exception.
        # A run that perceived little should say whether that is a quiet locus or a body it could
        # not use.
        "bindings": [{"name": b.name, "resolution": b.resolution, "invocable": b.invocable,
                      "role": (b.role.name if b.role else None), "detail": b.detail}
                     for b in (organs.resolve(o) for o in agent.organ_set)],
    }

    perceptions = perceive(agent, post, now=stamp)
    transcript["percept_field"] = [p.as_dict() for p in perceptions]
    transcript["trajectory"] = list(agent.trajectory)

    transcript["memory"] = remember(agent, now=stamp)
    observations = report(agent, atlas_id=atlas_id, now=stamp)
    transcript["observations"] = observations
    marks = proposed_marks(agent)
    transcript["proposed_marks"] = marks

    # BOTH READINGS, never the flattering one alone — the same discipline `run_kernel` keeps.
    transcript["hydrated"] = [{
        "as_stored": obs_mod.hydrate_observation(o, posts),
        "with_proposed_marks": obs_mod.hydrate_observation(o, overlay_posts(posts, marks)),
    } for o in observations]

    transcript["persisted"] = {"observations": []}
    if persist:
        for o in observations:
            stored = await obs_mod.write_observation(o, collection=collection)
            transcript["persisted"]["observations"].append(stored["observation_id"])

    assert_posts_unchanged(before, posts_fingerprint(posts))
    transcript["posts_unchanged"] = True
    return transcript
