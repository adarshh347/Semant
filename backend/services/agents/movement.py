"""WAVE3 — agent movement: read a grounded horizon, traverse one measured edge, perceive again.

The situated agent inhabits a locus and perceives from it. This is the step that makes its world
*grow*: it reads the movement edges reaching its node, refuses the ones it cannot prove, walks one
of the rest into another image, and perceives there through the same organs. Two loci stitched by
a relation it can trace to a measurement — the first being in this system whose world is larger
because it moved.

## What this module is allowed to do, and the line it does not cross

    the kernel   grounds a crossing and mints the edge          → `movement_kernel`
    the agent    READS that edge, verifies it, and walks it     → here

Nothing in this file measures a cross-image relation, and nothing in it may. `movement_kernel` is
deliberately not imported — `test_agent_movement_wave3.py` asserts the absence structurally, the
same way the package's no-language-model guard is asserted. An agent that could ground its own
crossings would be authoring the world it then reports having found in.

## Reachability — what a step must prove before it is a step

The WAVE2.5 ruling (`DECISION-movement-grounds-only-on-masks`) says a measured movement grounds on
masks at BOTH ends or it does not ground. So an edge the retina proposed and the kernel refused is
a place this agent can SEE and cannot STEP TO, and that difference is carried on every horizon row
rather than expressed by absence: an unreachable edge stays in the horizon wearing its reason.

Five reasons, kept apart because they are five different facts:

    closed                  a contradiction ended this movement, or it evaporated below the floor
    no_mark                 the measurement it cites is not readable from here
    mark_misstated          the mark claims a kind of knowing its own basis does not support
    interpretive_basis      box geometry — an estimate of an extent, so it may propose, never carry
    mark_measures_elsewhere the mark this edge cites does not measure either of its endpoints

and one about the agent rather than the edge:

    box_footing             the agent's own locus rests on an estimate

That last one is the near half of the ruling, and the agent checks it ITSELF rather than taking
the edge's word for it. A movement edge stores ONE `mark_id` — the far measurement — while a
crossing rests on two, so from the edge alone the near side is unverifiable. What the agent can
verify is where it is standing: if its own organ measured no mask-basis relation from this locus,
it has no measured footing, and a measured crossing cannot start from an estimate. See §5 of the
findings note for why this is a limit rather than a fix.

## Two readings of every edge, never the flattering one alone

`DECISION-measured-private-vs-shared-ledger`: the live/private view may act on an organ-backed
result; the shared ledger stays proposed until a curator commits. Both are computed for every
horizon row — `epistemic` (private: the posts plus the marks the running session actually holds)
and `ledger_status` (the durable record as it stands) — and the gap between them is the human act
nobody has performed. **Reachability is decided on the private reading**, which is the yes-half of
the decision applied to movement: an agent does not wait for a curator to believe its own eyes.

A mark handed in as `proposed_marks` is not taken on trust. It must be an organ's mark, its stated
status must match what its own basis supports, and it must measure one of the crossing's endpoints
— otherwise a fabricated row would be a passport.

## No goal, and no narrated arrival

Selection is a stated rule (`POLICIES`), recorded on the step it produced, and nothing here reads
a label, a similarity or a preference. An agent that "wanted" to go somewhere would be confabulating
intent it has no organ for; emergent goals are a later lane.

And arrival is empty. `step` clears the percept field and the horizon, so between a step and the
next `perceive` the agent knows *nothing* about where it is — it did not import the seed's world
and it cannot describe a destination it has not measured. `test_the_agent_arrives_knowing_nothing`
pins it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services import nestedness_organ
from backend.services.agents import observation as obs_mod
from backend.services.agents.situated_agent import (Locus, SituatedAgent, TRAJECTORY_STEP,
                                                    overlay_posts)
from backend.services.epistemics import STATUS_KEY
from backend.services.movement_store import read_neighbours

#: Why an edge in the horizon cannot be walked. Named constants, because each one is reported to a
#: human, read by a test, and counted in a run's tally — a bare string in three places is three
#: spellings waiting to happen. Kept apart rather than summed for the reason Lane M keeps
#: `box_only` and `surface_only` apart: a single "refused" count would hide which world the
#: refusals are about.
UNREACHABLE_CLOSED = "closed"
UNREACHABLE_NO_MARK = "no_mark"
UNREACHABLE_MISSTATED = "mark_misstated"
UNREACHABLE_INTERPRETIVE = "interpretive_basis"
UNREACHABLE_ELSEWHERE = "mark_measures_elsewhere"

#: About the traveller rather than the edge — the near half of the WAVE2.5 ruling.
UNFOOTED_UNPERCEIVED = "unperceived"
UNFOOTED_BOX = "box_footing"

#: The selection rules this lane offers. A dict rather than an `if`, so the rule an agent used is a
#: value that can be recorded on the step and read back, rather than a branch nobody can cite.
#:
#: All of them are deliberately dull. "Most shared structure", "most re-measured" and "most cleanly
#: ordered" are properties of the GRAPH, not preferences of the agent, and none consults a label, an
#: embedding or a history of where this agent has been. The moment a policy reads any of those, the
#: agent has acquired an interest — which is a real and interesting lane, and it is not this one.
POLICY_SYSTEMATICITY = "strongest_systematicity"
POLICY_WEIGHT = "heaviest"

#: WAVE3 — the rule for the DEPTH axis, and it exists because neither of the others can serve it.
#:
#: An `in_front_of` edge carries **no systematicity**: structure-mapping is how an analogy between
#: two images is judged, and an occlusion is not an analogy — it is a fact about one scene. So it
#: scores 0.0 under `strongest_systematicity`, and an agent on that policy would never take a depth
#: step while any geometric edge was reachable. That is not a default to paper over; it is the two
#: axes being incommensurable, the same wall `depth_organ` puts between its own readings and every
#: other sense's.
#:
#: This rule reads the one number an occlusion mark does carry — how cleanly the two cell
#: distributions are ordered — and is a property of the measurement, like the others.
POLICY_ORDERING = "clearest_ordering"

POLICIES: Dict[str, str] = {
    POLICY_SYSTEMATICITY: ("take the reachable edge whose structure-map score is highest; ties "
                           "broken by weight, then by the destination node id"),
    POLICY_WEIGHT: ("take the reachable edge with the most concentration — the movement this "
                    "corpus has re-measured most; ties broken by systematicity, then by the "
                    "destination node id"),
    POLICY_ORDERING: ("take the reachable edge whose cited measurement orders its two ends most "
                      "cleanly — the depth axis, where nothing carries a structure-map score; "
                      "ties broken by weight, then by the destination node id"),
}

#: TRAJECTORY DECAY — a hook, deliberately not implemented.
#:
#: An unbounded trajectory eventually makes every agent omniscient: walk long enough and the union
#: of its loci is the corpus, at which point "what this agent knows from where it stands" has
#: quietly become "what the corpus contains", and the partiality that makes a second agent worth
#: talking to is gone. `movement_graph.DECAY_HALF_LIFE_SECONDS` is the precedent for what the fix
#: looks like.
#:
#: The hook is that every trajectory entry carries `at`, so a decay pass is a filter over stamps
#: and needs no change to the record shape. Left as `None` — and pinned as `None` by a test — so
#: that implementing it is a deliberate act rather than a default nobody chose.
TRAJECTORY_DECAY_HALF_LIFE_SECONDS: Optional[float] = None


class Unreachable(Exception):
    """A step the agent may see but may not take. Raised, never downgraded to a weaker step.

    Deliberately not a returned refusal, unlike `organs.resolve`: a horizon row already carries its
    refusal as data, so by the time anything calls `step` the question has been asked and answered.
    Reaching here with an unreachable edge means a caller ignored the answer, and the honest
    response is to stop before the agent is somewhere it did not earn.
    """


# ── node ids: the inverse of the one construction everything uses ────────────

def parse_node_id(node_id: str) -> Optional[Tuple[str, str]]:
    """`vm_<post_id>:<region_id>` → the pair, or None if it is not one of ours.

    Verified by RECONSTRUCTION rather than by trusting the split: whatever comes back must rebuild
    the exact string through `observation.node_id_for`, which is the same construction the movement
    kernel uses (`_node_id`) and the one a test already pins the two to agree on. A node id this
    cannot round-trip is one this lane must not walk to, because the endpoint it would land on is
    not the endpoint the edge names.
    """
    text = str(node_id or "")
    if not text.startswith("vm_") or ":" not in text:
        return None
    post_id, _, region_id = text[len("vm_"):].partition(":")
    if not post_id or not region_id:
        return None
    if obs_mod.node_id_for(post_id, region_id) != text:
        return None
    return post_id, region_id


# ── footing: the near half of the ruling, checked by the traveller ───────────

def footing(agent: SituatedAgent) -> Dict[str, Any]:
    """What kind of ground this agent is standing on, from its OWN organ's readings.

    Not a geometry inspection and not a promise — it is the agent's percept field, asked one
    question: did anything I measured from here rest on a mask? A mask-basis measurement requires
    both regions masked on a shared raster (`nestedness_organ._mask_pair`), so holding one is proof
    that the locus itself carries measured geometry.

    An EMPTY field is not `box`. It is `unperceived`, and the distinction matters: "I looked from
    here and everything I found was an estimate" and "I have not looked" are different states, and
    an agent that stepped from the second would be crossing on geometry nobody consulted.
    """
    if not agent.percept_field:
        return {
            "basis": None, "admissible": False, "reason": UNFOOTED_UNPERCEIVED,
            "admissible_readings": 0, "readings": 0,
            "detail": ("this agent has not perceived from its current locus, so it has not "
                       "measured its own footing — a crossing that starts from geometry nobody "
                       "consulted is not a measured crossing"),
        }
    admissible = [p for p in agent.percept_field if p.reading.admissible]
    if not admissible:
        return {
            "basis": "box", "admissible": False, "reason": UNFOOTED_BOX,
            "admissible_readings": 0, "readings": len(agent.percept_field),
            "detail": (f"every one of this agent's {len(agent.percept_field)} reading(s) from here "
                       f"rests on box geometry. A box is an estimate of an extent (WAVE2.5); a "
                       f"measured cross-image relation grounds on masks at BOTH ends, and this is "
                       f"the end the agent is standing on"),
        }
    return {
        "basis": nestedness_organ.ADMISSIBLE_BASIS, "admissible": True, "reason": "",
        "admissible_readings": len(admissible), "readings": len(agent.percept_field),
        "detail": (f"{len(admissible)} of {len(agent.percept_field)} reading(s) from this locus "
                   f"rest on a per-pixel mask intersection — the near end is measured geometry"),
    }


# ── the horizon ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Reach:
    """One movement edge as the agent's horizon holds it: where it goes, and whether it may go.

    An unreachable row is kept rather than filtered. "The kernel refused this crossing" is a fact
    about the agent's world — it is a place it can see and cannot get to — and a horizon that
    silently dropped them would report a smaller, tidier world in which every visible relation was
    also a road.
    """
    edge: Dict[str, Any]                 # hydrated against the agent's private/live world
    ledger: Dict[str, Any]               # the same edge as the durable record currently reads it
    other_node: str
    direction: str
    reachable: bool
    reason: str
    detail: str
    mark: Optional[Dict[str, Any]] = None

    @property
    def edge_id(self) -> str:
        return str(self.edge.get("edge_id") or "")

    @property
    def mark_id(self) -> str:
        return str(self.edge.get("mark_id") or "")

    @property
    def axis_ref(self) -> str:
        return str(self.edge.get("axis_ref") or "")

    @property
    def systematicity(self) -> float:
        return float(self.edge.get("systematicity") or 0.0)

    @property
    def weight(self) -> float:
        return float(self.edge.get("weight") or 0.0)

    @property
    def epistemic(self) -> Optional[str]:
        """What the PRIVATE view says this crossing is. `None` — never `uncertain` — when the mark
        cannot be read at all, because that is "this edge cannot currently tell you"."""
        return str(self.edge.get("epistemic") or "") or None

    @property
    def basis(self) -> str:
        return str(((self.mark or {}).get("measurement") or {}).get("basis") or "")

    @property
    def ordering(self) -> float:
        """How cleanly the cited measurement orders its two ends — the depth axis's only score.

        0.0 when the mark carries none, which is every geometric crossing: containment says nothing
        about which end is nearer, and reading a default as an ordering would invent one.
        """
        return float(((self.mark or {}).get("measurement") or {}).get("separation") or 0.0)

    @property
    def relation(self) -> str:
        """What the cited mark says this crossing IS. Read off the mark, never named here.

        Both places, because the two organs put it in different ones: `nestedness_organ` nests it
        inside `measurement`, `occlusion_organ` carries it on the mark. Neither is wrong and this
        lane does not get to legislate mark shape — it gets to read what is there.
        """
        mark = self.mark or {}
        return str(mark.get("relation")
                   or (mark.get("measurement") or {}).get("relation") or "")

    @property
    def ledger_status(self) -> str:
        """What the SHARED record says, which is `proposed` until a curator commits the mark."""
        if self.ledger.get("live") and self.ledger.get("epistemic"):
            return str(self.ledger["epistemic"])
        return obs_mod.LEDGER_PROPOSED

    def destination(self) -> Optional[Locus]:
        parsed = parse_node_id(self.other_node)
        return Locus(post_id=parsed[0], region_id=parsed[1]) if parsed else None

    def as_dict(self) -> Dict[str, Any]:
        destination = self.destination()
        return {
            "edge_id": self.edge_id,
            "axis_ref": self.axis_ref,
            "direction": self.direction,
            "other_node": self.other_node,
            "destination": destination.as_dict() if destination else None,
            "reachable": self.reachable,
            "reason": self.reason,
            "detail": self.detail,
            "systematicity": self.edge.get("systematicity"),
            "weight": self.edge.get("weight"),
            # The depth axis's own score, and the relation the mark names. Both `None`/empty on a
            # geometric crossing rather than defaulted, because a containment does not order its
            # ends and a zero here would read as one that orders them badly.
            "ordering": self.ordering or None,
            "relation": self.relation or None,
            "mark_id": self.mark_id,
            "basis": self.basis,
            # BOTH READINGS on every row. The private one decides whether the agent may walk; the
            # ledger one says what the world has accepted, and they are not the same thing today.
            "epistemic": self.epistemic,
            "ledger_status": self.ledger_status,
        }


#: The keys an organ's mark may use to name the regions it measured.
#:
#: More than one vocabulary, because more than one relation now grounds a crossing and they do not
#: describe their ends alike: containment has an `inner`/`outer`, occlusion has a `front`/`back`,
#: and neither name would be honest for the other — a thing in front of another is not inside it,
#: which is the entire subject of the occlusion lane.
#:
#: Read as a SET rather than as a schema. This lane does not get to say what an organ must call its
#: ends; it gets to ask which regions a mark is about, and refuse the crossing if the answer does
#: not include one of the edge's own endpoints.
MARK_REGION_KEYS: Tuple[str, ...] = (
    "inner_region_id", "outer_region_id",       # nestedness, adjacency
    "front_region_id", "back_region_id",        # occlusion
    "a_region_id", "b_region_id", "region_id",
)


def measured_nodes(mark: Optional[Mapping[str, Any]]) -> set:
    """Which loci this mark is actually about, as node ids.

    The check `_admits` makes with it is the one that is easy to leave out, because every other
    property of a misapplied mark is impeccable: well-formed, mask-basis, honestly stamped, and
    about a different pair. Generalising the vocabulary widens what can be READ here; it does not
    weaken the test, which still demands that the mark name an end of this very crossing.
    """
    if not mark:
        return set()
    post_id = str(mark.get("post_id") or "")
    region_ids = set()
    for source in (mark, mark.get("measurement") or {}):
        if not isinstance(source, Mapping):
            continue
        for key in MARK_REGION_KEYS:
            value = source.get(key)
            if value:
                region_ids.add(str(value))
        for value in (source.get("region_ids") or []):
            if value:
                region_ids.add(str(value))
    return {obs_mod.node_id_for(post_id, region_id) for region_id in region_ids}


def _cited_mark(edge: Mapping[str, Any],
                posts: Mapping[str, Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The measurement this edge cites, from either image it spans, or None."""
    mark_id = str(edge.get("mark_id") or "")
    for post_id in edge.get("spans") or []:
        mark = obs_mod.find_mark(posts.get(str(post_id)), mark_id)
        if mark is not None:
            return mark
    return None


def _admits(edge: Mapping[str, Any], mark: Optional[Mapping[str, Any]]) -> Tuple[bool, str, str]:
    """May this edge carry a measured crossing? The far half of the ruling, verified not assumed.

    Every check is on the MARK rather than on the edge, because the edge stores no status and is not
    entitled to one — Lane G refuses `epistemic_status` on an edge precisely so that this question
    has exactly one answer and it lives with the organ that did the work.

    The last check is the one that is easy to leave out. A mark grants passage across the crossing
    it MEASURED; a valid, mask-basis, honestly-stamped mark that measures some other pair is still
    not evidence about this one, and an edge citing it is an assertion nobody grounded.
    """
    if mark is None:
        return False, UNREACHABLE_NO_MARK, (
            f"the measurement this movement cites ({edge.get('mark_id')}) is not readable from "
            f"here — it is in neither image's ledger nor among the marks this run holds. The edge "
            f"names a crossing; the evidence for it is somewhere this agent cannot see")

    measurement = dict(mark.get("measurement") or {})
    basis = str(measurement.get("basis") or "")
    stated = str(mark.get(STATUS_KEY) or "")
    supported = nestedness_organ.epistemic_for(basis)

    # PER MEASUREMENT, not per producer. The same check `situated_agent._verify_marks` makes before
    # a report, for the same reason: a box mark stamped `measured` is the 2D-projection artefact
    # wearing the strongest word the vocabulary has, and a per-producer table would wave it through.
    if stated != supported:
        return False, UNREACHABLE_MISSTATED, (
            f"mark {mark.get('id')} claims {stated!r} on the {basis!r} basis, which supports "
            f"{supported!r}. A mark that misstates its own geometry is not a passport, and this "
            f"agent will not walk on one")

    if not nestedness_organ.is_admissible(measurement):
        return False, UNREACHABLE_INTERPRETIVE, (
            f"this crossing rests on {basis!r} geometry — an estimate of an extent, not a "
            f"measurement of one. It is a real peripheral signal and it may propose; it may not "
            f"carry an agent to another image. VISIBLE, and not reachable")

    endpoints = {str(edge.get("source_node")), str(edge.get("target_node"))}
    measured = measured_nodes(mark)
    if not measured & endpoints:
        return False, UNREACHABLE_ELSEWHERE, (
            f"mark {mark.get('id')} measures {sorted(measured) or 'nothing this lane can name'} "
            f"and this movement runs between {sorted(endpoints)}. A measurement of some other pair "
            f"is not evidence about this crossing, however well-formed it is")

    return True, "", (
        f"{basis} basis at the measured end, {stated} — the crossing this movement names was "
        f"measured, and the agent may walk it")


def horizon(agent: SituatedAgent, doc: Mapping[str, Any],
            posts: Mapping[str, Mapping[str, Any]], *,
            proposed_marks: Sequence[Mapping[str, Any]] = (),
            axis: str = "") -> List[Reach]:
    """The agent's REACHABLE WORLD: every movement touching where it stands, each with its verdict.

    Distinct from what the retina proposes, and the distinction is the whole point of the field. The
    retina answers "what looks like this"; an axis answers "what stands in this relation to it"; and
    a horizon answers the third question neither asks — "which of those can I actually get to from
    here, and on what evidence". A row that fails the last question stays, carrying its reason.

    `proposed_marks` are the organ marks the running session holds in hand — the private/live world
    the decision permits an agent to act on. Given none, the horizon is computed against the durable
    ledger alone, which today means nothing is reachable at all: no curator has committed a movement
    mark in this corpus. That is not a bug to route around. It is the measured state of the world,
    and a run should report it rather than quietly overlaying its own evidence and calling the
    result "the graph".
    """
    private = overlay_posts(posts, list(proposed_marks))
    node_id = agent.locus.node_id

    ledger_rows = {str(e.get("edge_id") or ""): e for e in
                   read_neighbours(doc, node_id, axis=axis, posts=posts, include_dead=True)}

    out: List[Reach] = []
    for hydrated in read_neighbours(doc, node_id, axis=axis, posts=private, include_dead=True):
        edge_id = str(hydrated.get("edge_id") or "")
        raw = _raw_edge(doc, edge_id)
        mark = _cited_mark(hydrated, private)

        if not hydrated.get("live_now"):
            reachable, reason, detail = False, UNREACHABLE_CLOSED, (
                "this movement is closed — a contradiction ended it, or it decayed below the "
                "prune floor. Its record stands; its claim does not")
        else:
            reachable, reason, detail = _admits(raw or hydrated, mark)

        out.append(Reach(
            edge=hydrated, ledger=ledger_rows.get(edge_id, {}),
            other_node=str(hydrated.get("other_node") or ""),
            direction=str(hydrated.get("direction") or ""),
            reachable=reachable, reason=reason, detail=detail, mark=mark))

    agent.horizon = out
    return out


def _raw_edge(doc: Mapping[str, Any], edge_id: str) -> Optional[Dict[str, Any]]:
    """The stored row behind a hydrated one. Used for `spans`/endpoints, which hydration keeps."""
    for edge in doc.get("edges") or []:
        if isinstance(edge, Mapping) and str(edge.get("edge_id") or "") == str(edge_id):
            return dict(edge)
    return None


def reachable(entries: Sequence[Reach]) -> List[Reach]:
    return [r for r in entries if r.reachable]


def horizon_tally(entries: Sequence[Reach]) -> Dict[str, Any]:
    """Visible, reachable, and the refusals BY CLASS — never as one number.

    Lane M's rule, carried here: `box_only` and `surface_only` say different things about the
    corpus, and a single count would hide which. `interpretive_basis` says the geometry cannot
    carry the claim; `no_mark` says the evidence is somewhere this agent cannot read; `closed` says
    the movement is over. Summing them would make a starved agent and a fenced-in one look alike.
    """
    tally: Dict[str, Any] = {"visible": len(entries), "reachable": 0, "refused": {}}
    for row in entries:
        if row.reachable:
            tally["reachable"] += 1
            continue
        tally["refused"][row.reason] = tally["refused"].get(row.reason, 0) + 1
    return tally


# ── selection: a stated rule, and nothing that could want anything ───────────

def select(entries: Sequence[Reach], *, policy: str = POLICY_SYSTEMATICITY) -> Optional[Reach]:
    """Choose one reachable edge by a NAMED, inspectable rule. `None` when there is nothing to walk.

    The rule is a value (`POLICIES[policy]`) and it is recorded on the step it produces, so a reader
    of a trajectory can see why the agent went where it went without reading this function. That is
    the entire honesty claim of this stage: the agent has no preference, no memory of where it has
    been, and no goal — it has a rule, and the rule is written down.

    THE TIE-BREAK IS THE DESTINATION NODE, not the edge id, and that is the difference between a
    walk that can be re-run and one that only looks like it can. `edge_id` is minted per edge
    (`new_movement_edge_id`, uuid-backed, and correctly so — census §4: a positional id would be
    repointed by the next re-dissect). A kernel run that grounds the same crossings twice therefore
    produces different edge ids both times, so a tie broken on them resolves differently on every
    run. It was, and the two walks went to different images — which is exactly the kind of quiet
    irreproducibility a stated rule is supposed to rule out.

    `other_node` is `vm_<post>:<region>`: a content identity, stable across runs, and the thing the
    step actually means. Two runs over the same corpus now choose the same way.
    """
    if policy not in POLICIES:
        raise ValueError(
            f"unknown selection policy {policy!r} — the rule an agent moves by has to be one a "
            f"reader can look up, and {sorted(POLICIES)} are the ones this lane states")
    candidates = reachable(entries)
    if not candidates:
        return None
    if policy == POLICY_WEIGHT:
        key = lambda r: (r.weight, r.systematicity, r.other_node)       # noqa: E731
    elif policy == POLICY_ORDERING:
        key = lambda r: (r.ordering, r.weight, r.other_node)            # noqa: E731
    else:
        key = lambda r: (r.systematicity, r.weight, r.other_node)       # noqa: E731
    return max(candidates, key=key)


# ── the step ─────────────────────────────────────────────────────────────────

def step(agent: SituatedAgent, reach: Reach, *, policy: str = POLICY_SYSTEMATICITY,
         now: str = "") -> Dict[str, Any]:
    """Traverse one measured edge. The agent is somewhere else afterwards, and knows nothing there.

    Three refusals before anything moves, and none of them is a downgrade — there is no weaker step
    this could become:

      · the edge is not reachable (the horizon already said so, with its reason);
      · the agent has no measured footing where it stands (the near half of the ruling);
      · the far endpoint is not a node this lane can resolve to a locus in an image the edge spans.

    On success the locus changes and the percept field and horizon are EMPTIED. That is the
    no-narrated-arrival rule as code rather than as discipline: an agent that kept its old field
    would arrive already holding sentences about a place it has not looked at, and those sentences
    would be about the image it just left while wearing the new locus's name.
    """
    stamp = now or obs_mod.utc_now()

    if not reach.reachable:
        raise Unreachable(
            f"agent {agent.id} may see {reach.other_node} along {reach.axis_ref} and may not step "
            f"to it [{reach.reason}]: {reach.detail}")

    stood = footing(agent)
    if not stood["admissible"]:
        raise Unreachable(
            f"agent {agent.id} cannot step from {agent.locus.node_id} [{stood['reason']}]: "
            f"{stood['detail']}")

    destination = reach.destination()
    if destination is None:
        raise Unreachable(
            f"the far endpoint {reach.other_node!r} is not a node id this lane can resolve to an "
            f"image and a region — an agent cannot arrive somewhere that cannot be named")

    spans = {str(p) for p in (reach.edge.get("spans") or [])}
    if spans and destination.post_id not in spans:
        raise Unreachable(
            f"the far endpoint names post {destination.post_id} and this movement spans "
            f"{sorted(spans)} — an edge whose endpoint is outside its own span is malformed, and "
            f"walking it would put the agent in an image the crossing never measured")

    origin = agent.locus
    agent.locus = destination
    # ARRIVAL IS EMPTY. Everything the agent knew was knowledge from where it was standing, and it
    # is not standing there any more.
    agent.percept_field = []
    agent.horizon = []

    entry = {
        "at": stamp,
        "kind": TRAJECTORY_STEP,
        "from": origin.as_dict(),
        "from_node": origin.node_id,
        "to": destination.as_dict(),
        "to_node": destination.node_id,
        "crossed_image": destination.post_id != origin.post_id,
        "axis_ref": reach.axis_ref,
        "edge_id": reach.edge_id,
        # THE CITATION. A step whose mark cannot be named is a step nobody can check, and
        # `_admits` has already refused every edge that could produce one.
        "mark_id": reach.mark_id,
        "basis": reach.basis,
        # COPIED off the mark, never named here. The episodic record of a step says what the
        # organ said about the crossing — which, because only an admissible crossing is walkable,
        # is `measured`; but it is `measured` because the mark says so, not because this line does.
        STATUS_KEY: (reach.mark or {}).get(STATUS_KEY),
        # And the other reading, on the same row: the durable record has accepted nothing.
        "ledger_status": reach.ledger_status,
        "systematicity": reach.edge.get("systematicity"),
        "weight": reach.edge.get("weight"),
        # WAVE3 — what kind of crossing this was. A depth step and an analogy step are both steps
        # and they are not the same event: one moved the agent within a scene, the other between
        # two pictures that share a shape.
        "relation": reach.relation or None,
        "ordering": reach.ordering or None,
        # WHY THIS EDGE — the rule, spelled out, not the preference the agent does not have.
        "policy": policy,
        "rule": POLICIES.get(policy, ""),
        "footing": stood,
        "detail": reach.detail,
    }
    agent.trajectory.append(entry)
    return entry


# ── the map the agent drew ───────────────────────────────────────────────────

def constellation(agent: SituatedAgent) -> Dict[str, Any]:
    """The walk as a world: the loci this agent has stood in, and the crossings between them.

    Built from the trajectory rather than kept alongside it, so there is exactly one record of
    where the agent has been and no second copy to disagree with it. Every crossing carries the
    mark it rests on, which is what makes the constellation checkable rather than a picture: a
    reader can take any leg of the walk and go and look at the measurement under it.
    """
    loci: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []
    for entry in agent.trajectory:
        if str(entry.get("kind") or "") == TRAJECTORY_STEP:
            steps.append(dict(entry))
            continue
        loci.append({
            "at": entry.get("at"),
            "node_id": entry.get("node_id"),
            "locus": entry.get("locus"),
            # How many readings the agent held HERE, against how many regions were in reach — the
            # coverage claim, carried per locus so a two-image constellation says what each of its
            # ends actually afforded rather than only that it was reached.
            "readings": entry.get("measured"),
            "regions_in_reach": entry.get("regions_in_reach"),
        })

    legible = ""
    if loci:
        legible = f"agent {agent.id}: {loci[0]['node_id']}"
        for i, walked in enumerate(steps):
            arrived = loci[i + 1]["node_id"] if i + 1 < len(loci) else walked["to_node"]
            legible += (f" —[{walked['axis_ref']}, {walked.get(STATUS_KEY)}, "
                        f"{walked['basis']}]→ {arrived}")

    return {
        "agent_id": agent.id,
        "loci": loci,
        "steps": steps,
        "posts": sorted({str((row.get("locus") or {}).get("post_id") or "")
                         for row in loci} - {""}),
        "legible": legible,
    }


