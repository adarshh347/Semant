"""
HARNESS-001B §5 — one causal history, append-only, and the evidence rule that keeps it honest.

The point of this lane is not that the Director and the situated agents can both be commissioned.
It is that AFTERWARDS THEY ARE IN THE SAME STORY: a reader can follow one causal chain from the
prompt through a global segmentation, into a body standing on a region, out through what that body
measured, and back to the clause it did or did not settle.

## The rule that makes the log worth reading

**No event may inline fabricated evidence.** An `evidence_returned` event does not carry a sentence
about what was found — it carries, or references, the EXISTING typed shape (an organ's grounding
mark, an observation row, a production record) together with the provenance that shape already has.

`Evidence.of_mark` enforces the half of that a comment cannot: the epistemic status is READ OFF the
referenced object and refused if a caller states a different one. That is the same discipline
`situated_agent.remember` keeps — copy the organ's word, never choose one — moved up a level, and it
exists because this is the layer where a plausible summary would be easiest to write and hardest to
catch.

## Testimony stays testimony

An agent's dialogue hypothesis is `TESTIMONY`. It is carried, it is legible, and the engine never
promotes it: two agents concurring is two readings, not a measurement. `Evidence.of_testimony`
therefore cannot produce a `measured` item at all — the constructor has no path to that word.

## Append-only, by value

`InquiryRun` is frozen and every mutation returns a new run. An event log that could be edited after
the fact is a log that cannot be used to check anything, and this one is a required proof: the run
must round-trip through `to_dict`/`from_dict` with no field loss.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Mapping, Optional, Tuple

from backend.services.epistemics import STATUS_KEY
from backend.services.inquiry_engine.frame import AcceptedFrame
from backend.services.inquiry_engine.goals import Goal, goal_from_dict

RUN_CONTRACT_VERSION = 1

# ── the event vocabulary ─────────────────────────────────────────────────────
EV_INQUIRY_FRAMED = "inquiry_framed"
EV_GOAL_CREATED = "goal_created"
EV_CAPABILITY_RESOLVED = "capability_resolved"
EV_DIRECTOR_TASK_STARTED = "director_task_started"
EV_DIRECTOR_TASK_COMPLETED = "director_task_completed"
EV_DIRECTOR_TASK_REFUSED = "director_task_refused"
EV_MISSION_DISPATCHED = "mission_dispatched"
EV_AGENT_PERCEIVED = "agent_perceived"
EV_AGENT_MOVED = "agent_moved"
EV_AGENT_MET = "agent_met"
EV_AGENT_REFUSED = "agent_refused"
EV_EVIDENCE_RETURNED = "evidence_returned"
EV_GOAL_SATISFIED = "goal_satisfied"
EV_GOAL_PARTIAL = "goal_partial"
EV_GOAL_UNRESOLVED = "goal_unresolved"
EV_CAPABILITY_GAP = "capability_gap"
EV_RUN_STOPPED = "run_stopped"

EVENT_KINDS: Tuple[str, ...] = (
    EV_INQUIRY_FRAMED, EV_GOAL_CREATED, EV_CAPABILITY_RESOLVED,
    EV_DIRECTOR_TASK_STARTED, EV_DIRECTOR_TASK_COMPLETED, EV_DIRECTOR_TASK_REFUSED,
    EV_MISSION_DISPATCHED, EV_AGENT_PERCEIVED, EV_AGENT_MOVED, EV_AGENT_MET, EV_AGENT_REFUSED,
    EV_EVIDENCE_RETURNED, EV_GOAL_SATISFIED, EV_GOAL_PARTIAL, EV_GOAL_UNRESOLVED,
    EV_CAPABILITY_GAP, EV_RUN_STOPPED,
)

# ── actors ───────────────────────────────────────────────────────────────────
#: WHO did it. Four, and the separation is the point of the whole log: a reader must be able to see
#: that the thing which measured is not the thing which planned.
ACTOR_ENGINE = "engine"
ACTOR_DIRECTOR = "director"
ACTOR_AGENT = "agent"
ACTOR_CURATOR = "curator"

# ── evidence kinds ───────────────────────────────────────────────────────────
EVIDENCE_ORGAN_MARK = "organ_mark"
EVIDENCE_OBSERVATION = "observation"
EVIDENCE_PRODUCTION = "production_record"
EVIDENCE_TESTIMONY = "testimony"
EVIDENCE_REFUSAL = "refusal"

# ── the run's outcome ────────────────────────────────────────────────────────
OUTCOME_ANSWERABLE = "answerable"
OUTCOME_PARTIALLY_ANSWERABLE = "partially_answerable"
OUTCOME_AWAITING_HUMAN = "awaiting_human"
OUTCOME_EXHAUSTED = "exhausted"

OUTCOMES: Tuple[str, ...] = (OUTCOME_ANSWERABLE, OUTCOME_PARTIALLY_ANSWERABLE,
                             OUTCOME_AWAITING_HUMAN, OUTCOME_EXHAUSTED)

# ── stop reasons ─────────────────────────────────────────────────────────────
#: Explicit, closed, and none of them is "the loop finished". An open-ended autonomous loop is what
#: this vocabulary exists to make impossible to write.
STOP_SATISFIED = "satisfied"
STOP_NO_NEW_EVIDENCE = "no_new_evidence"
STOP_BUDGET_EXHAUSTED = "budget_exhausted"
STOP_AWAITING_HUMAN = "awaiting_human"
STOP_CAPABILITY_GAP = "capability_gap"
STOP_EXECUTION_UNAVAILABLE = "execution_unavailable"

STOP_REASONS: Tuple[str, ...] = (STOP_SATISFIED, STOP_NO_NEW_EVIDENCE, STOP_BUDGET_EXHAUSTED,
                                 STOP_AWAITING_HUMAN, STOP_CAPABILITY_GAP,
                                 STOP_EXECUTION_UNAVAILABLE)


class EventMalformed(Exception):
    """An event outside the declared vocabulary, or one missing the fields that make it causal."""


class EvidenceFabricated(Exception):
    """Something tried to state an epistemic status the referenced object does not carry.

    Raised rather than corrected. A silently-corrected status would leave the caller believing it
    stated one thing while the log said another, which is worse than either.
    """


@dataclass(frozen=True)
class Event:
    """One transition. Carries `run_id`, `step_id`, actor, source, timestamp and reason — the six
    the directive requires — because an event missing any of them cannot be placed in a causal
    chain, and a log of unplaceable events is a list, not a history."""
    seq: int
    kind: str
    run_id: str
    step_id: str
    actor: str
    source: str
    at: str
    reason: str = ""
    goal_id: str = ""
    parent_goal_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise EventMalformed(
                f"event kind {self.kind!r} is not one of {list(EVENT_KINDS)}. The vocabulary is "
                f"closed so a reader can branch on it; a free-text kind is not something anyone "
                f"can check a run against.")
        for name in ("run_id", "step_id", "actor", "source", "at"):
            if not str(getattr(self, name) or "").strip():
                raise EventMalformed(
                    f"event {self.kind!r} carries no {name!r}. Every transition carries run_id, "
                    f"step_id, actor, source, timestamp and reason — an event missing one cannot "
                    f"be placed in the causal chain it claims to be part of.")

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "kind": self.kind, "run_id": self.run_id,
                "step_id": self.step_id, "actor": self.actor, "source": self.source,
                "at": self.at, "reason": self.reason, "goal_id": self.goal_id,
                "parent_goal_id": self.parent_goal_id, "payload": dict(self.payload)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Event":
        return cls(seq=int(d.get("seq") or 0), kind=str(d.get("kind") or ""),
                   run_id=str(d.get("run_id") or ""), step_id=str(d.get("step_id") or ""),
                   actor=str(d.get("actor") or ""), source=str(d.get("source") or ""),
                   at=str(d.get("at") or ""), reason=str(d.get("reason") or ""),
                   goal_id=str(d.get("goal_id") or ""),
                   parent_goal_id=str(d.get("parent_goal_id") or ""),
                   payload=dict(d.get("payload") or {}))


@dataclass(frozen=True)
class Evidence:
    """One returned piece of evidence, carrying the typed shape it came from.

    `ref` IS the existing object — an organ's grounding mark, an observation row, a production
    record — not a summary of it. That is what makes "no fabricated evidence" checkable rather than
    promised: a reader can take `ref` out of the log and hand it to the same code that produced it.
    """
    id: str
    goal_id: str
    kind: str
    epistemic_status: str
    ledger_status: str = "proposed"
    basis: str = ""
    relation: str = ""
    organ: str = ""
    producer: str = ""
    mark_id: str = ""
    detail: str = ""
    ref: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def of_mark(cls, mark: Mapping[str, Any], *, evidence_id: str, goal_id: str,
                organ: str = "", relation: str = "", detail: str = "",
                provenance: Optional[Mapping[str, Any]] = None) -> "Evidence":
        """An organ's grounding mark, as evidence. THE STATUS IS COPIED, NEVER CHOSEN.

        The organ that did the work is the only thing entitled to say what kind of knowing its
        output is — `situated_agent.remember`'s rule, and the reason a box-basis nesting arrives
        here reading `interpretive` rather than being promoted on the way up.
        """
        status = str(mark.get(STATUS_KEY) or "")
        if not status:
            raise EvidenceFabricated(
                f"mark {mark.get('id')!r} carries no {STATUS_KEY}. Evidence reads its kind of "
                f"knowing off the object; a mark that states none cannot be given one here.")
        measurement = dict(mark.get("measurement") or {})
        prov = dict(mark.get("provenance") or {})
        return cls(
            id=evidence_id, goal_id=goal_id, kind=EVIDENCE_ORGAN_MARK,
            epistemic_status=status,
            basis=str(measurement.get("basis") or ""),
            relation=relation or str(mark.get("relation")
                                     or measurement.get("relation")
                                     or mark.get("role") or ""),
            organ=organ or str(prov.get("producer") or ""),
            producer=str(prov.get("producer") or ""),
            mark_id=str(mark.get("id") or ""),
            detail=detail or str(measurement.get("detail") or mark.get("label") or ""),
            ref=dict(mark),
            provenance={**prov, **dict(provenance or {})})

    @classmethod
    def of_production(cls, record: Mapping[str, Any], *, evidence_id: str, goal_id: str,
                      epistemic_status: str,
                      provenance: Optional[Mapping[str, Any]] = None) -> "Evidence":
        """A Director step's own record. `epistemic_status` must be stated by the CALLER from what
        the produced descriptor says, and is refused if the record itself disagrees."""
        stated = str(record.get(STATUS_KEY) or "")
        if stated and stated != epistemic_status:
            raise EvidenceFabricated(
                f"production record {record.get('step_id')!r} carries {stated!r} and the caller "
                f"stated {epistemic_status!r}. A status restated differently from the object it "
                f"describes is the exact drift this constructor exists to catch.")
        return cls(id=evidence_id, goal_id=goal_id, kind=EVIDENCE_PRODUCTION,
                   epistemic_status=epistemic_status,
                   producer=str(record.get("actuator") or record.get("producer") or ""),
                   detail=str(record.get("detail") or ""),
                   ref=dict(record), provenance=dict(provenance or {}))

    @classmethod
    def of_testimony(cls, hypothesis: Mapping[str, Any], *, evidence_id: str, goal_id: str,
                     provenance: Optional[Mapping[str, Any]] = None) -> "Evidence":
        """An agent's spoken claim, or two agents' joint hypothesis. Testimony, and it stays that.

        There is NO PATH from this constructor to `measured`. Agreement is not grounding: two
        differently-embodied agents concurring is two readings, and a composition becomes measured
        knowledge only by being re-grounded on new loci. The engine never upgrades what this returns.
        """
        return cls(id=evidence_id, goal_id=goal_id, kind=EVIDENCE_TESTIMONY,
                   epistemic_status="",          # deliberately none — see the docstring
                   detail=str(hypothesis.get("claim") or hypothesis.get("detail") or ""),
                   ref=dict(hypothesis), provenance=dict(provenance or {}))

    @classmethod
    def of_refusal(cls, refusal: Mapping[str, Any], *, evidence_id: str, goal_id: str,
                   provenance: Optional[Mapping[str, Any]] = None) -> "Evidence":
        """A refusal, carried as evidence rather than as an absence. "The organ refused" is a fact
        about this locus and this body, and a run that dropped it would report a quieter world."""
        return cls(id=evidence_id, goal_id=goal_id, kind=EVIDENCE_REFUSAL,
                   epistemic_status="",
                   detail=str(refusal.get("detail") or refusal.get("reason") or ""),
                   ref=dict(refusal), provenance=dict(provenance or {}))

    @property
    def measured(self) -> bool:
        return self.epistemic_status == "measured"

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "goal_id": self.goal_id, "kind": self.kind,
                "epistemic_status": self.epistemic_status, "ledger_status": self.ledger_status,
                "basis": self.basis, "relation": self.relation, "organ": self.organ,
                "producer": self.producer, "mark_id": self.mark_id, "detail": self.detail,
                "ref": dict(self.ref), "provenance": dict(self.provenance)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Evidence":
        return cls(id=str(d.get("id") or ""), goal_id=str(d.get("goal_id") or ""),
                   kind=str(d.get("kind") or ""),
                   epistemic_status=str(d.get("epistemic_status") or ""),
                   ledger_status=str(d.get("ledger_status") or "proposed"),
                   basis=str(d.get("basis") or ""), relation=str(d.get("relation") or ""),
                   organ=str(d.get("organ") or ""), producer=str(d.get("producer") or ""),
                   mark_id=str(d.get("mark_id") or ""), detail=str(d.get("detail") or ""),
                   ref=dict(d.get("ref") or {}), provenance=dict(d.get("provenance") or {}))


@dataclass(frozen=True)
class CapabilityGap:
    """A gap, as DATA with its unmet requirement — never an error and never an empty result."""
    goal_id: str
    need: str
    unmet: Tuple[str, ...]
    why: str
    at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"goal_id": self.goal_id, "need": self.need, "unmet": list(self.unmet),
                "why": self.why, "at": self.at}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "CapabilityGap":
        return cls(goal_id=str(d.get("goal_id") or ""), need=str(d.get("need") or ""),
                   unmet=tuple(str(u) for u in d.get("unmet") or ()),
                   why=str(d.get("why") or ""), at=str(d.get("at") or ""))


@dataclass(frozen=True)
class InquiryRun:
    """One inquiry's whole causal history, as plain serialisable data.

    NO MONGO COLLECTION. This lane opens none — the reconciliation in `__init__.py` says which
    existing store should eventually carry this, and until that is reviewed a fourth run collection
    would reproduce exactly the drift this wave exists to remove. So the run is a value: a caller
    that wants it persisted calls `to_dict()` and puts it where the reconciliation says.

    Frozen, and every mutator returns a new run. The log is append-only in the strongest available
    sense — there is no method that removes or rewrites an event.
    """
    run_id: str
    frame: AcceptedFrame
    goals: Tuple[Goal, ...] = ()
    events: Tuple[Event, ...] = ()
    evidence: Tuple[Evidence, ...] = ()
    gaps: Tuple[CapabilityGap, ...] = ()
    outcome: str = ""
    stop_reason: str = ""
    rounds: int = 0
    notes: Tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    contract_version: int = RUN_CONTRACT_VERSION

    # ── append-only mutators, each returning a new run ────────────────────
    def next_seq(self) -> int:
        return len(self.events)

    def with_event(self, **kwargs: Any) -> "InquiryRun":
        event = Event(seq=self.next_seq(), run_id=self.run_id, **kwargs)
        return replace(self, events=(*self.events, event), updated_at=event.at)

    def with_goal(self, goal: Goal) -> "InquiryRun":
        return replace(self, goals=(*self.goals, goal))

    def with_goal_status(self, goal_id: str, status: str) -> "InquiryRun":
        """Replace one goal with itself at a new status. The goals tuple holds current state; the
        event log holds how it got there. Neither is derivable from the other, which is why both
        exist."""
        return replace(self, goals=tuple(g.with_status(status) if g.id == goal_id else g
                                         for g in self.goals))

    def with_evidence(self, *items: Evidence) -> "InquiryRun":
        return replace(self, evidence=(*self.evidence, *items))

    def with_gap(self, gap: CapabilityGap) -> "InquiryRun":
        return replace(self, gaps=(*self.gaps, gap))

    def with_note(self, note: str) -> "InquiryRun":
        return replace(self, notes=(*self.notes, note))

    def stopped(self, *, outcome: str, stop_reason: str, at: str, rounds: int) -> "InquiryRun":
        if outcome not in OUTCOMES:
            raise EventMalformed(f"outcome {outcome!r} is not one of {list(OUTCOMES)}")
        if stop_reason not in STOP_REASONS:
            raise EventMalformed(f"stop reason {stop_reason!r} is not one of {list(STOP_REASONS)}")
        return replace(self, outcome=outcome, stop_reason=stop_reason, rounds=rounds,
                       updated_at=at)

    # ── reading ──────────────────────────────────────────────────────────
    def goal(self, goal_id: str) -> Optional[Goal]:
        for g in self.goals:
            if g.id == goal_id:
                return g
        return None

    def evidence_for(self, goal_id: str) -> Tuple[Evidence, ...]:
        return tuple(e for e in self.evidence if e.goal_id == goal_id)

    def events_of(self, kind: str) -> Tuple[Event, ...]:
        return tuple(e for e in self.events if e.kind == kind)

    # ── serialization: the round trip is a required proof ────────────────
    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "run_id": self.run_id,
            "frame": self.frame.to_dict(),
            "goals": [g.to_dict() for g in self.goals],
            "events": [e.to_dict() for e in self.events],
            "evidence": [e.to_dict() for e in self.evidence],
            "gaps": [g.to_dict() for g in self.gaps],
            "outcome": self.outcome,
            "stop_reason": self.stop_reason,
            "rounds": self.rounds,
            "notes": list(self.notes),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "InquiryRun":
        return cls(
            run_id=str(d.get("run_id") or ""),
            frame=AcceptedFrame.from_dict(d.get("frame") or {}),
            goals=tuple(goal_from_dict(g) for g in d.get("goals") or ()),
            events=tuple(Event.from_dict(e) for e in d.get("events") or ()),
            evidence=tuple(Evidence.from_dict(e) for e in d.get("evidence") or ()),
            gaps=tuple(CapabilityGap.from_dict(g) for g in d.get("gaps") or ()),
            outcome=str(d.get("outcome") or ""),
            stop_reason=str(d.get("stop_reason") or ""),
            rounds=int(d.get("rounds") or 0),
            notes=tuple(str(n) for n in d.get("notes") or ()),
            created_at=str(d.get("created_at") or ""),
            updated_at=str(d.get("updated_at") or ""),
            contract_version=int(d.get("contract_version") or RUN_CONTRACT_VERSION))


def new_run(*, run_id: str, frame: AcceptedFrame, at: str) -> InquiryRun:
    return InquiryRun(run_id=run_id, frame=frame, created_at=at, updated_at=at)


__all__ = [
    "RUN_CONTRACT_VERSION", "EVENT_KINDS", "EVENT_KINDS",
    "EV_INQUIRY_FRAMED", "EV_GOAL_CREATED", "EV_CAPABILITY_RESOLVED",
    "EV_DIRECTOR_TASK_STARTED", "EV_DIRECTOR_TASK_COMPLETED", "EV_DIRECTOR_TASK_REFUSED",
    "EV_MISSION_DISPATCHED", "EV_AGENT_PERCEIVED", "EV_AGENT_MOVED", "EV_AGENT_MET",
    "EV_AGENT_REFUSED", "EV_EVIDENCE_RETURNED", "EV_GOAL_SATISFIED", "EV_GOAL_PARTIAL",
    "EV_GOAL_UNRESOLVED", "EV_CAPABILITY_GAP", "EV_RUN_STOPPED",
    "ACTOR_ENGINE", "ACTOR_DIRECTOR", "ACTOR_AGENT", "ACTOR_CURATOR",
    "EVIDENCE_ORGAN_MARK", "EVIDENCE_OBSERVATION", "EVIDENCE_PRODUCTION", "EVIDENCE_TESTIMONY",
    "EVIDENCE_REFUSAL",
    "OUTCOMES", "OUTCOME_ANSWERABLE", "OUTCOME_PARTIALLY_ANSWERABLE", "OUTCOME_AWAITING_HUMAN",
    "OUTCOME_EXHAUSTED",
    "STOP_REASONS", "STOP_SATISFIED", "STOP_NO_NEW_EVIDENCE", "STOP_BUDGET_EXHAUSTED",
    "STOP_AWAITING_HUMAN", "STOP_CAPABILITY_GAP", "STOP_EXECUTION_UNAVAILABLE",
    "Event", "Evidence", "CapabilityGap", "InquiryRun", "new_run",
    "EventMalformed", "EvidenceFabricated",
]
