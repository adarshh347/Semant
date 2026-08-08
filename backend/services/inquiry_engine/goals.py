"""
HARNESS-001B — the goal hierarchy: five nested kinds, and why none of them is the others.

The Director plans globally and the situated agents perceive locally, and until this lane there was
no object that could hold both. The obvious move — one `Goal` with a `scope` field — is the one this
module refuses, because the five things below have genuinely different truth conditions:

    InquiryGoal        the human-scale purpose. May contain clauses nothing can measure.
    EvidenceGoal       one answerable need: what evidence would support/challenge/complicate a claim.
    PreparationTask    global work delegated to the Director (find/segment/retrieve/compare/compose).
    AgentMission       a bounded local investigation: locus, body, question, budget, return contract.
    SituatedGoal       an ADAPTER around the existing measured, modality-bound `agents.goal` aim.

Flattening them would mean one `satisfied` for all five, and `satisfied` means five different things:
a Director task is satisfied when an actuator ran, a mission when an agent perceived, an evidence
goal when a declared criterion was met by returned evidence, and an inquiry goal — possibly never,
because "what hybrid styles could they give birth to" has no satisfaction condition at all.

## `satisfied` is the word this module is arranged around

    §2 of the directive: *"`satisfied` requires evidence satisfying an explicit criterion. Agreement,
    eloquent dialogue and a completed actuator call are not themselves satisfaction."*

So a criterion is a DECLARED, CHECKABLE predicate over returned evidence — a relation, a basis, a
required kind of knowing — and `evaluator.py` is the only thing that reads one. Nothing here decides
that a goal was met; this module only makes it possible to say precisely what would.

## The four clause modes, and the one that is not an EpistemicStatus

`measured`, `interpretive` and `sourced` are `EpistemicStatus` values and are spelled from that enum
rather than retyped, so a clause cannot demand a kind of knowing the rest of the system does not
have. `imagined` is deliberately NOT one: speculation is not a way of knowing the image, and giving
it an `EpistemicStatus` would create a supported way to publish a fabrication as evidence. It exists
here as a clause mode so that "what hybrids could they give birth to" can be CARRIED — named,
inspectable, and permanently unsatisfiable — rather than silently dropped or quietly answered.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from backend.services.epistemics import EpistemicStatus

# ── goal kinds ───────────────────────────────────────────────────────────────
KIND_INQUIRY = "inquiry"
KIND_EVIDENCE = "evidence"
KIND_PREPARATION = "preparation"
KIND_MISSION = "mission"
KIND_SITUATED = "situated"

GOAL_KINDS: Tuple[str, ...] = (KIND_INQUIRY, KIND_EVIDENCE, KIND_PREPARATION,
                               KIND_MISSION, KIND_SITUATED)

# ── status ───────────────────────────────────────────────────────────────────
#: The nine states a goal may be in. Nine rather than three, because collapsing any pair loses a
#: distinction somebody downstream has to make:
#:
#:   capability_gap vs unresolved   "there is no instrument" vs "the instrument found nothing"
#:   unresolved vs exhausted        "not answered" vs "not answered and nothing further will be tried"
#:   refused vs capability_gap      "a law forbids this" vs "no law, no instrument"
#:   partially_satisfied vs satisfied   the whole reason this lane exists
STATUS_PROPOSED = "proposed"
STATUS_READY = "ready"
STATUS_ACTIVE = "active"
STATUS_SATISFIED = "satisfied"
STATUS_PARTIALLY_SATISFIED = "partially_satisfied"
STATUS_UNRESOLVED = "unresolved"
STATUS_CAPABILITY_GAP = "capability_gap"
STATUS_EXHAUSTED = "exhausted"
STATUS_REFUSED = "refused"

STATUSES: Tuple[str, ...] = (
    STATUS_PROPOSED, STATUS_READY, STATUS_ACTIVE, STATUS_SATISFIED,
    STATUS_PARTIALLY_SATISFIED, STATUS_UNRESOLVED, STATUS_CAPABILITY_GAP,
    STATUS_EXHAUSTED, STATUS_REFUSED,
)

#: The statuses that mean "nothing further will happen to this goal in this run". A run that stops
#: with a non-terminal goal still open is a run that stopped early, and the loop says so.
TERMINAL_STATUSES: Tuple[str, ...] = (
    STATUS_SATISFIED, STATUS_PARTIALLY_SATISFIED, STATUS_UNRESOLVED,
    STATUS_CAPABILITY_GAP, STATUS_EXHAUSTED, STATUS_REFUSED,
)

# ── clause modes ─────────────────────────────────────────────────────────────
CLAUSE_MEASURED = EpistemicStatus.MEASURED.value
CLAUSE_INTERPRETIVE = EpistemicStatus.INTERPRETIVE.value
CLAUSE_SOURCED = EpistemicStatus.SOURCED.value
#: NOT an `EpistemicStatus`, and the absence is the design — see the module note.
CLAUSE_IMAGINED = "imagined"

CLAUSE_MODES: Tuple[str, ...] = (CLAUSE_MEASURED, CLAUSE_INTERPRETIVE,
                                 CLAUSE_SOURCED, CLAUSE_IMAGINED)


class UnknownClauseMode(Exception):
    """A clause demanding a kind of knowing nobody declared. Raised rather than defaulted: a
    criterion whose demand is a typo would silently become unsatisfiable-for-the-wrong-reason,
    which is indistinguishable from a real capability gap."""


class GoalMalformed(Exception):
    """A goal that could not be read back from its own serialization, or that names a kind or
    status outside the declared sets."""


@dataclass(frozen=True)
class Criterion:
    """One checkable clause of an evidence goal. The only thing `satisfied` may rest on.

    `demands` is what KIND of knowing would settle it, and it is the field that makes an honest
    partial result possible: a measured clause and an interpretive clause sitting on one goal is the
    normal case (a fold's extent is measurable; whether it reads as sensual is not), and a goal that
    could not tell them apart would either over-claim on the first or under-claim on the second.

    `relation` and `basis` narrow it to a specific organ measurement where one exists. Empty means
    "any evidence of the demanded kind", which is correct for a sourced clause and wrong for a
    measured one — so the derivation fills them, and `evaluator` never invents them.
    """
    id: str
    clause: str
    demands: str = CLAUSE_MEASURED
    relation: str = ""
    basis: str = ""
    #: The instruments whose output settles this clause, by producer name.
    #:
    #: Without it a clause demanding `measured` is settled by ANY measured evidence in the run — so
    #: a nestedness mark returned for one goal would quietly satisfy a different goal's clause about
    #: a fold's extent. Both are honest measurements; neither is a measurement of the other's
    #: subject. Empty means "any producer", which is correct only for a clause that named no
    #: instrument.
    produced_by: Tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if self.demands not in CLAUSE_MODES:
            raise UnknownClauseMode(
                f"criterion {self.id!r} demands {self.demands!r}; the declared modes are "
                f"{list(CLAUSE_MODES)}. Three of them are `EpistemicStatus` values and the fourth "
                f"({CLAUSE_IMAGINED!r}) deliberately is not — speculation is not a way of knowing "
                f"the image, and a criterion that could demand one that does not exist would be "
                f"unsatisfiable for a reason a reader would mistake for a capability gap.")

    @property
    def measurable(self) -> bool:
        """Could an organ or an actuator ever settle this? False for interpretive and imagined
        clauses, and that is a fact about the clause rather than about this system's maturity."""
        return self.demands in (CLAUSE_MEASURED, CLAUSE_SOURCED)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "clause": self.clause, "demands": self.demands,
                "relation": self.relation, "basis": self.basis,
                "produced_by": list(self.produced_by), "detail": self.detail}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Criterion":
        return cls(id=str(d.get("id") or ""), clause=str(d.get("clause") or ""),
                   demands=str(d.get("demands") or CLAUSE_MEASURED),
                   relation=str(d.get("relation") or ""), basis=str(d.get("basis") or ""),
                   produced_by=tuple(str(p) for p in d.get("produced_by") or ()),
                   detail=str(d.get("detail") or ""))


# ── the hierarchy ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Goal:
    """What every goal carries. `parent_goal_id` on all of them, per the directive, so the causal
    tree is reconstructible from the flat list without consulting the event log."""
    id: str
    kind: str
    title: str = ""
    parent_goal_id: str = ""
    status: str = STATUS_PROPOSED
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind not in GOAL_KINDS:
            raise GoalMalformed(f"goal {self.id!r} has kind {self.kind!r}, not one of "
                                f"{list(GOAL_KINDS)}")
        if self.status not in STATUSES:
            raise GoalMalformed(f"goal {self.id!r} has status {self.status!r}, not one of "
                                f"{list(STATUSES)}")

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def with_status(self, status: str) -> "Goal":
        """A NEW goal at the new status. Goals are frozen and the run holds them by value, so a
        transition is a replacement recorded as an event — never an in-place edit that would leave
        the event log describing a state no object is in."""
        return replace(self, status=status)

    def _base_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "title": self.title,
                "parent_goal_id": self.parent_goal_id, "status": self.status,
                "detail": self.detail}

    def to_dict(self) -> Dict[str, Any]:
        return self._base_dict()


@dataclass(frozen=True)
class InquiryGoal(Goal):
    """The human-scale purpose, in the curator's own words, with its clauses named.

    `prompt` is verbatim and is never rewritten — an inquiry whose prompt drifted would make every
    downstream refusal unfalsifiable, because nobody could check what was actually asked.
    """
    kind: str = KIND_INQUIRY
    prompt: str = ""
    mode: str = "explore"
    criteria: Tuple[Criterion, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {**self._base_dict(), "prompt": self.prompt, "mode": self.mode,
                "criteria": [c.to_dict() for c in self.criteria]}


@dataclass(frozen=True)
class EvidenceGoal(Goal):
    """One answerable need. The unit the capability resolver is asked about.

    `need` is a key in `capability.NEEDS` — a declared entry rather than free text, for the reason
    `agents.goal.GOALS` and `director.INTENTS` are tables: a need a run acted on has to be a thing a
    reader can look up afterwards.
    """
    kind: str = KIND_EVIDENCE
    need: str = ""
    question: str = ""
    phrase: str = ""
    post_id: str = ""
    region_id: str = ""
    criteria: Tuple[Criterion, ...] = ()
    #: Where the need came from in the frame — an attention, a proposed action, an unresolved term.
    #: Kept because a gap reported against a term the curator typed reads differently from one
    #: reported against an act a planner proposed.
    origin: str = ""
    #: The proposed public act this goal came from, normalised, when it came from one.
    #:
    #: Carried rather than reduced to a `need`, because three public acts are NOT a lookup —
    #: `brush_field(fold)`, `challenge_percept` and `compose_percept` each have a rule of their own
    #: in `capability.resolve_action`, and a goal that had already been flattened to a need would
    #: silently lose all three. An empty dict means the goal came from a term or an attention.
    action: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {**self._base_dict(), "need": self.need, "question": self.question,
                "phrase": self.phrase, "post_id": self.post_id, "region_id": self.region_id,
                "origin": self.origin, "action": dict(self.action),
                "criteria": [c.to_dict() for c in self.criteria]}


@dataclass(frozen=True)
class PreparationTask(Goal):
    """Global work delegated to the Director.

    Either an `actuator` (the resolver named a specific instrument) or an `intention` (the Director's
    own keyword table decides). Both paths end at `plan.resolve` and `execution.execute`, which is
    what makes this an adapter rather than a second planner — see `adapters.DirectorAdapter`.
    """
    kind: str = KIND_PREPARATION
    actuator: str = ""
    intention: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    post_ids: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {**self._base_dict(), "actuator": self.actuator, "intention": self.intention,
                "params": dict(self.params), "post_ids": list(self.post_ids)}


@dataclass(frozen=True)
class SituatedGoal(Goal):
    """An ADAPTER around `agents.goal.GOALS`, and nothing more.

    It holds exactly what that module declares — a relation, an axis, its own detail — and adds no
    field of its own. That is the "never overloaded" rule in the directive made structural: the
    moment this carried a criterion or a budget of its own, there would be two places deciding when
    a situated aim is met, and the one that is not `agents.goal.satisfying_marks` would be wrong.
    """
    kind: str = KIND_SITUATED
    name: str = ""
    relation: str = ""
    axis: str = ""

    @classmethod
    def of(cls, name: str, *, goal_id: str = "", parent_goal_id: str = "") -> "SituatedGoal":
        """Resolve through `agents.goal.resolve`, so an undeclared aim is refused THERE rather than
        approximated here. This lane states no aims of its own."""
        from backend.services.agents import goal as agent_goal
        declared = agent_goal.resolve(name)
        return cls(id=goal_id or f"sg_{name}", parent_goal_id=parent_goal_id,
                   title=str(declared["name"]), name=str(declared["name"]),
                   relation=str(declared["relation"]), axis=str(declared["axis"]),
                   detail=str(declared["detail"]), status=STATUS_PROPOSED)

    def to_dict(self) -> Dict[str, Any]:
        return {**self._base_dict(), "name": self.name, "relation": self.relation,
                "axis": self.axis}


@dataclass(frozen=True)
class AgentMission(Goal):
    """A bounded local investigation: locus, body, question, budget, return contract.

    `budget` is a step bound, not a token or time budget — an agent's expensive act is MOVING, and a
    mission that could not bound it would be the open-ended autonomous loop the directive refuses.
    `bound=0` is legitimate and means "perceive from here and report"; it is the control rehearsal's
    mission and the honest minimum.

    `return_contract` names what the mission must hand back. It is not decoration: `evaluator` reads
    only declared criteria, and a mission that returned trajectory where the goal wanted marks would
    otherwise look like a mission that returned nothing.
    """
    kind: str = KIND_MISSION
    post_id: str = ""
    region_id: str = ""
    organ_set: Tuple[str, ...] = ()
    question: str = ""
    budget: int = 0
    temperament: str = ""
    situated_goal: Optional[SituatedGoal] = None
    return_contract: Tuple[str, ...] = ("perceptions", "observations", "marks", "trajectory")

    def to_dict(self) -> Dict[str, Any]:
        return {**self._base_dict(), "post_id": self.post_id, "region_id": self.region_id,
                "organ_set": list(self.organ_set), "question": self.question,
                "budget": self.budget, "temperament": self.temperament,
                "situated_goal": self.situated_goal.to_dict() if self.situated_goal else None,
                "return_contract": list(self.return_contract)}


# ── serialization ────────────────────────────────────────────────────────────

_BY_KIND = {
    KIND_INQUIRY: InquiryGoal,
    KIND_EVIDENCE: EvidenceGoal,
    KIND_PREPARATION: PreparationTask,
    KIND_MISSION: AgentMission,
    KIND_SITUATED: SituatedGoal,
}


def goal_from_dict(d: Mapping[str, Any]) -> Goal:
    """Read a goal back by its own `kind`. Round-trip fidelity is a required proof of this lane, so
    an unknown kind RAISES rather than degrading to the base class — a goal that came back as a
    weaker type than it went in would lose fields silently, which is exactly the loss the proof is
    supposed to detect."""
    kind = str(d.get("kind") or "")
    cls = _BY_KIND.get(kind)
    if cls is None:
        raise GoalMalformed(
            f"cannot read back a goal of kind {kind!r} — the declared kinds are {list(GOAL_KINDS)}. "
            f"Degrading to the base class here would drop every field the subclass added and the "
            f"round trip would still 'succeed'.")
    common = dict(id=str(d.get("id") or ""), kind=kind, title=str(d.get("title") or ""),
                  parent_goal_id=str(d.get("parent_goal_id") or ""),
                  status=str(d.get("status") or STATUS_PROPOSED),
                  detail=str(d.get("detail") or ""))
    if cls is InquiryGoal:
        return InquiryGoal(**common, prompt=str(d.get("prompt") or ""),
                           mode=str(d.get("mode") or "explore"),
                           criteria=tuple(Criterion.from_dict(c) for c in d.get("criteria") or ()))
    if cls is EvidenceGoal:
        return EvidenceGoal(**common, need=str(d.get("need") or ""),
                            question=str(d.get("question") or ""),
                            phrase=str(d.get("phrase") or ""),
                            post_id=str(d.get("post_id") or ""),
                            region_id=str(d.get("region_id") or ""),
                            origin=str(d.get("origin") or ""),
                            action=dict(d.get("action") or {}),
                            criteria=tuple(Criterion.from_dict(c) for c in d.get("criteria") or ()))
    if cls is PreparationTask:
        return PreparationTask(**common, actuator=str(d.get("actuator") or ""),
                               intention=str(d.get("intention") or ""),
                               params=dict(d.get("params") or {}),
                               post_ids=tuple(str(p) for p in d.get("post_ids") or ()))
    if cls is SituatedGoal:
        return SituatedGoal(**common, name=str(d.get("name") or ""),
                            relation=str(d.get("relation") or ""),
                            axis=str(d.get("axis") or ""))
    situated = d.get("situated_goal")
    return AgentMission(**common, post_id=str(d.get("post_id") or ""),
                        region_id=str(d.get("region_id") or ""),
                        organ_set=tuple(str(o) for o in d.get("organ_set") or ()),
                        question=str(d.get("question") or ""),
                        budget=int(d.get("budget") or 0),
                        temperament=str(d.get("temperament") or ""),
                        situated_goal=(goal_from_dict(situated)  # type: ignore[arg-type]
                                       if isinstance(situated, Mapping) else None),
                        return_contract=tuple(str(r) for r in d.get("return_contract") or ()))


def children_of(goals: Sequence[Goal], parent_id: str) -> Tuple[Goal, ...]:
    return tuple(g for g in goals if g.parent_goal_id == parent_id)


__all__ = [
    "KIND_INQUIRY", "KIND_EVIDENCE", "KIND_PREPARATION", "KIND_MISSION", "KIND_SITUATED",
    "GOAL_KINDS", "STATUSES", "TERMINAL_STATUSES",
    "STATUS_PROPOSED", "STATUS_READY", "STATUS_ACTIVE", "STATUS_SATISFIED",
    "STATUS_PARTIALLY_SATISFIED", "STATUS_UNRESOLVED", "STATUS_CAPABILITY_GAP",
    "STATUS_EXHAUSTED", "STATUS_REFUSED",
    "CLAUSE_MEASURED", "CLAUSE_INTERPRETIVE", "CLAUSE_SOURCED", "CLAUSE_IMAGINED", "CLAUSE_MODES",
    "Criterion", "Goal", "InquiryGoal", "EvidenceGoal", "PreparationTask", "AgentMission",
    "SituatedGoal", "goal_from_dict", "children_of",
    "UnknownClauseMode", "GoalMalformed",
]
