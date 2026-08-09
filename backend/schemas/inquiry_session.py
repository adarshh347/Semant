"""
HARNESS-002D — the transport envelope: one semantic inquiry, whole, as durable session history.

WHAT THIS OBJECT IS. Everything one inquiry produced, from the words somebody typed to the answer
they were given, with every stage's outcome and every reference between them. It is the thing the
route serves, the thing the store writes, and the thing a replay reproduces.

WHAT IT COMPOSES RATHER THAN REIMPLEMENTS. Three merged lanes already own most of this:

    InquiryFrame                 HARNESS-001A — the prompt, read, with no pixels seen
    SemanticInquiryGraph         HARNESS-002A — reading, claims, observables, remainder
    InquiryInteractionState      HARNESS-002B — modes, decisions, conflicts, the event log

None of the three is re-declared here. The envelope holds each as its own snapshot and adds only
what no lane owned: the request that started it, the post fingerprints that prove nothing moved,
the stage ledger, the capability receipts, the claim verdicts and the composed answer.

SESSION HISTORY IS NOT THE PERCEPTUAL LEDGER. Everything in here is durable and none of it is
accepted. No post, mark, percept, Atlas edge or agent memory is touched by anything that writes
this object, and `source_fingerprints` is the checked form of that promise rather than the
promised form.

WHY THE STAGE VOCABULARY IS ITS OWN. Lane B's `EventKind` is the twelve transitions of a
DELIBERATION — offered, requested, auto-resolved, refused. A stage ledger answers a different
question: did the theorist run, and if it did not, was it unavailable, empty, refused or skipped?
Collapsing the two would put "the compiler returned nothing" in the same list as "the person chose
option two", and the four ways a stage produces no output would lose the distinction that
HARNESS-001B built its whole finding around.
"""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.schemas.inquiry_stage import (StageAttempt, StageAttemptOutcome, StageName,
                                           UNDERPERFORMANCE_OUTCOMES)

SCHEMA_VERSION = "semantic-inquiry-session.v2"

#: Versions this envelope will OPEN. v1 documents are in the store and a bump that refused them
#: would make every session written before HARNESS-003B unreadable — the stage ledger grew, and a
#: richer ledger is not a reason to lose the sessions that recorded a thinner one. `StageAttempt`'s
#: own before-validator does the per-entry upgrade; this is the envelope half of the same reader.
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = ("semantic-inquiry-session.v1", SCHEMA_VERSION)


class StageOutcome(str, Enum):
    """How a stage ended. Seven, and the middle four are the point.

    From outside, `empty`, `unavailable`, `refused` and `skipped` all look like "that stage
    produced nothing". They are four different facts and they tell a reader four different things
    to do — HARNESS-001B's table, held at stage scale:

        empty        it ran and produced nothing        look somewhere else
        unavailable  it exists and is not running       try again
        refused      a law said no                      stop asking this of the machine
        skipped      the budget or the branch excluded it   nothing is wrong
    """
    STARTED = "started"
    COMPLETED = "completed"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"
    SKIPPED = "skipped"
    ERROR = "error"


#: Outcomes that mean the stage produced no usable output. `completed` is deliberately absent, and
#: so is `started` — a stage that started and never recorded an ending is a coordinator bug, and a
#: set that swallowed it would hide one.
BARREN_OUTCOMES: Tuple[StageOutcome, ...] = (
    StageOutcome.EMPTY, StageOutcome.UNAVAILABLE, StageOutcome.REFUSED, StageOutcome.SKIPPED,
    StageOutcome.ERROR,
)


class ExecutionMode(str, Enum):
    """`fixture` is not a weaker `live`. It is a different claim about what happened."""
    FIXTURE = "fixture"
    LIVE = "live"


class ReceiptStatus(str, Enum):
    """The six outcomes a capability request can have, spelled as the workbench reads them."""
    LIVE = "live"
    SIMULATED = "simulated"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"
    CAPABILITY_GAP = "capability_gap"


class ClaimVerdictOutcome(str, Enum):
    """What the judge concluded about one claim.

    `interpretive_only` and `not_investigated` are the two that carry Phase 1, and they are not the
    same: the first says the claim was looked at and nothing measured bears on it, the second says
    nobody asked. A reader deciding whether to trust an answer needs both.
    """
    SUPPORTED_BY_EVIDENCE = "supported_by_evidence"
    PARTIALLY_SUPPORTED = "partially_supported"
    INTERPRETIVE_ONLY = "interpretive_only"
    UNRESOLVED = "unresolved"
    CONTRADICTED = "contradicted"
    NOT_INVESTIGATED = "not_investigated"


#: The two verdicts that assert evidence carried a claim. A fixture receipt may never produce one,
#: and the judge has a test for each direction.
SUPPORTED_VERDICTS: Tuple[ClaimVerdictOutcome, ...] = (
    ClaimVerdictOutcome.SUPPORTED_BY_EVIDENCE, ClaimVerdictOutcome.PARTIALLY_SUPPORTED,
)


class _Strict(BaseModel):
    """Unknown fields are refused, not ignored."""
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


def sha256_of(text: Any) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


class PostRef(_Strict):
    """One selected post, and the fingerprint that proves it did not move.

    `fingerprint` is `movement_kernel.posts_fingerprint`'s value for the document as it was read.
    It is captured at creation and re-checked at every write, so "no post was mutated" is a
    comparison rather than an assurance.
    """
    post_id: str
    title: str = ""
    image_ref: str = ""
    fingerprint: str = ""
    readable: bool = True
    note: str = ""


class StageEvent(_Strict):
    """The v1 stage record. RETAINED, not deleted, and not written any more.

    `SemanticInquirySession.stages` now holds `StageAttempt`, which reads one of these and upgrades
    it. This class stays declared because the upgrade has to be testable against the real shape
    rather than against a dict somebody typed out from memory in a test — a compatibility reader
    checked only against a hand-written approximation of the old format is a reader for a format
    that never existed.
    """
    event_id: str
    stage: StageName
    outcome: StageOutcome
    at: Optional[str] = None
    revision: int = 0
    detail: str = ""
    input_refs: List[str] = Field(default_factory=list)
    output_refs: List[str] = Field(default_factory=list)


class CapabilityReceipt(_Strict):
    """What a capability request produced, and — the load-bearing half — what produced it.

    Phase 1's firewall lives in the validator rather than in the adapter that builds these: a
    receipt whose `execution_mode` is `fixture` may not claim to be usable as evidence, whatever
    the adapter passed. An adapter can be edited; a validator has to be argued with.
    """
    receipt_id: str
    request_ref: str = Field(..., description="the observable this answers")
    capability: str
    execution_mode: ExecutionMode
    status: ReceiptStatus
    usable_as_evidence: bool = False
    #: Spent on ATTEMPT, never on success — the field that separates `empty` from `unavailable`.
    attempted: bool = False
    payload: Dict[str, Any] = Field(default_factory=dict)
    detail: str = ""
    latency_ms: Optional[float] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _a_fixture_is_never_evidence(self) -> "CapabilityReceipt":
        if self.execution_mode is ExecutionMode.FIXTURE:
            if self.usable_as_evidence:
                raise ValueError(
                    f"receipt {self.receipt_id} was produced by a fixture and claims to be usable "
                    f"as evidence. A stand-in that can be promoted is not a stand-in; it is an "
                    f"unlabelled measurement.")
            if self.status is ReceiptStatus.LIVE:
                raise ValueError(
                    f"receipt {self.receipt_id} has execution_mode `fixture` and status `live`. "
                    f"The mode is what happened; the status may not contradict it.")
        if self.status in (ReceiptStatus.UNAVAILABLE, ReceiptStatus.CAPABILITY_GAP) \
                and self.attempted:
            raise ValueError(
                f"receipt {self.receipt_id} is {self.status.value!r} and says it was attempted. "
                f"Nothing was attempted against an instrument that was not there — and `attempted` "
                f"is the only field separating that from an instrument that ran and found nothing.")
        return self


class ClaimVerdict(_Strict):
    """What the judge concluded about one claim, and on what."""
    verdict_id: str
    claim_ref: str
    outcome: ClaimVerdictOutcome
    why: str
    evidence_refs: List[str] = Field(default_factory=list)
    receipt_refs: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _support_needs_evidence(self) -> "ClaimVerdict":
        if self.outcome in SUPPORTED_VERDICTS and not self.evidence_refs:
            raise ValueError(
                f"verdict {self.verdict_id} says {self.outcome.value!r} and cites no evidence. A "
                f"receipt is not evidence: it records that a route was invoked, not that anything "
                f"was found.")
        return self


class SynthesisSection(_Strict):
    """One paragraph of the answer, with everything it rests on named.

    `status` is the epistemic rendering the workbench reads. A section with no evidence refs is
    perfectly legitimate — most of Phase 1 is — but it must SAY so, which is what stops fluent
    prose from reading as a finding.
    """
    section_id: str
    heading: str = ""
    text: str
    status: str = "interpretive"
    claim_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    refusal_refs: List[str] = Field(default_factory=list)
    decision_refs: List[str] = Field(default_factory=list)
    user_authored: bool = False

    @model_validator(mode="after")
    def _a_section_says_what_it_rests_on(self) -> "SynthesisSection":
        if not self.text.strip():
            raise ValueError(f"section {self.section_id} carries no text")
        if self.status in ("measured", "visible") and not self.evidence_refs:
            raise ValueError(
                f"section {self.section_id} renders as {self.status!r} and cites no evidence. That "
                f"is the sentence this whole layer exists to make impossible.")
        return self


class Synthesis(_Strict):
    """The composed answer. Provisional by construction in Phase 1, and it says so."""
    synthesis_id: str
    note: str = ""
    sections: List[SynthesisSection] = Field(default_factory=list)
    remainder_refs: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class SessionProvenance(_Strict):
    """Who ran this, with what, and the hashes a replay compares."""
    producer: str = "inquiry_session/coordinator-v1"
    mode: str = ""
    frame_producer: str = ""
    theorist_model: Optional[str] = None
    compiler_model: Optional[str] = None
    composer_model: Optional[str] = None
    prompt_sha256: str = ""
    graph_hash: str = ""
    frame_hash: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class SemanticInquirySession(_Strict):
    """One inquiry, whole. The route serves it, the store writes it, a replay reproduces it."""

    schema_version: str = SCHEMA_VERSION
    session_id: str
    inquiry_id: str = ""
    revision: int = 0

    #: Byte for byte. Every source span in the graph indexes into THIS string.
    prompt: str
    mode: str = "consult"
    posts: List[PostRef] = Field(default_factory=list)

    frame: Dict[str, Any] = Field(default_factory=dict)
    #: The scene theorist's own output, persisted the moment it returns.
    #:
    #: WHY IT IS HERE AND NOT ONLY INSIDE THE GRAPH. The compiled graph carries a copy of the
    #: reading, so before HARNESS-003B this field would have been redundant — the reading existed
    #: as a Python object between the theorist call and the compiler call, and both happened inside
    #: one request. Checkpointing splits that: the theorist's outcome is persisted, the process may
    #: end, and the compiler runs later from the store alone. A reading held only in memory would
    #: force a re-read after every pause, which is a second charged model call for a result the
    #: session already had.
    #:
    #: It is also the artifact 002R asked to SEE. `{"reading": {...}, "refusals": [...],
    #: "notes": [...]}` — the theorist's paragraphs, visible the instant they exist rather than
    #: only once something downstream succeeded in using them.
    reading: Dict[str, Any] = Field(default_factory=dict)
    graph: Dict[str, Any] = Field(default_factory=dict)
    interaction: Dict[str, Any] = Field(default_factory=dict)

    selected_observable_ref: str = ""
    capability_receipts: List[CapabilityReceipt] = Field(default_factory=list)
    #: Real evidence. Empty in Phase 1, and empty ON PURPOSE — the list exists so that "nothing was
    #: measured" is a visible empty rather than a missing field somebody reads as not-yet-supported.
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    verdicts: List[ClaimVerdict] = Field(default_factory=list)
    synthesis: Optional[Synthesis] = None

    #: The stage ledger. `StageAttempt` upgrades a v1 `StageEvent` mapping on read, so a session
    #: written before HARNESS-003B opens with its history intact and its unrecorded fields absent.
    stages: List[StageAttempt] = Field(default_factory=list)
    #: Monotonic, and NOT `revision`. `revision` is the deliberation's turn counter and moves only
    #: when a person or a policy settles a fork; a driver checkpoints many times between two turns.
    #: Compare-and-set on stage writes needs a counter that moves on every one of them, and reusing
    #: `revision` would either corrupt the optimistic lock a client holds or make every checkpoint
    #: look like a turn nobody took.
    checkpoint: int = 0
    #: Which driver, if any, holds this session, and what it was last seen doing. See
    #: `inquiry_session.driver` — one active driver per session is enforced by a CAS on this block.
    driver: Dict[str, Any] = Field(default_factory=dict)
    gaps: List[str] = Field(default_factory=list)
    refusals: List[Dict[str, Any]] = Field(default_factory=list)
    stop_reason: str = ""
    error: str = ""
    provenance: SessionProvenance = Field(default_factory=SessionProvenance)

    @field_validator("schema_version")
    @classmethod
    def _pinned(cls, value: str) -> str:
        """Accepts every version this envelope can READ, and normalises none of them away.

        The stored string is kept as it was written. A reader that silently restamped a v1 document
        as v2 would make "which contract wrote this" unanswerable from the document itself, which
        is the one question a compatibility reader exists so somebody can ask.
        """
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"schema_version must be one of {list(SUPPORTED_SCHEMA_VERSIONS)}, "
                             f"got {value!r}")
        return value

    @field_validator("prompt")
    @classmethod
    def _the_prompt_is_there(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a session with no prompt is an inquiry into nothing")
        return value

    @model_validator(mode="after")
    def _nothing_simulated_became_evidence(self) -> "SemanticInquirySession":
        """The Phase 1 firewall, at envelope scale.

        Each receipt already refuses to call itself evidence. This checks the other direction: that
        no evidence object was minted FROM one. The two guards are not redundant — a receipt cannot
        see the evidence list, and the evidence list is a plain mapping precisely because Phase 1
        produces none and a typed empty would invite somebody to fill it.
        """
        fixture_receipts = {r.receipt_id for r in self.capability_receipts
                            if r.execution_mode is ExecutionMode.FIXTURE}
        for item in self.evidence:
            ref = str(item.get("receipt_ref") or "")
            if ref and ref in fixture_receipts:
                raise ValueError(
                    f"evidence {item.get('evidence_id')!r} was minted from fixture receipt {ref!r}. "
                    f"A simulated receipt proves a route was invoked. It cannot become the thing "
                    f"the route was supposed to find.")
            if str(item.get("execution_mode") or "") == ExecutionMode.FIXTURE.value:
                raise ValueError(
                    f"evidence {item.get('evidence_id')!r} declares execution_mode `fixture`.")

        known = {v.claim_ref for v in self.verdicts}
        if len(known) != len(self.verdicts):
            raise ValueError("two verdicts for one claim; a claim has one verdict or none")
        return self

    # ── reading ──

    def stage_events(self, stage: StageName) -> List[StageAttempt]:
        return [e for e in self.stages if e.stage is stage]

    def latest_attempt(self, stage: StageName) -> Optional[StageAttempt]:
        events = self.stage_events(stage)
        return events[-1] if events else None

    def unterminated(self) -> List[StageAttempt]:
        """Attempts that entered external work and never recorded leaving it.

        THE CRASH SIGNATURE. A `started` attempt is written before the call, so one still standing
        after a reload means the process died while the call may have been in flight. Returned as
        data rather than repaired here: the repair is a decision (record `interrupted` and stop),
        and a schema that made it silently would be re-running non-idempotent calls on a reload.
        """
        latest: Dict[StageName, StageAttempt] = {}
        for attempt in self.stages:
            latest[attempt.stage] = attempt
        return [a for a in latest.values() if a.outcome is StageAttemptOutcome.STARTED]

    @property
    def underperforming_stages(self) -> List[StageAttempt]:
        """Stages that ran, returned something, and whose own signal says it was not enough."""
        return [a for a in self.stages if a.outcome in UNDERPERFORMANCE_OUTCOMES]

    def receipt(self, receipt_id: str) -> Optional[CapabilityReceipt]:
        return next((r for r in self.capability_receipts if r.receipt_id == receipt_id), None)

    def verdict_for(self, claim_ref: str) -> Optional[ClaimVerdict]:
        return next((v for v in self.verdicts if v.claim_ref == claim_ref), None)

    @property
    def state(self) -> str:
        return str(self.interaction.get("state") or "framing")

    @property
    def awaiting_user(self) -> bool:
        return self.state == "awaiting_user"

    def summary(self) -> str:
        bits = [f"{self.state}", f"rev {self.revision}"]
        claims = (self.graph.get("claims") or []) if isinstance(self.graph, dict) else []
        bits.append(f"{len(claims)} claim{'' if len(claims) == 1 else 's'}")
        if self.capability_receipts:
            simulated = sum(1 for r in self.capability_receipts
                            if r.execution_mode is ExecutionMode.FIXTURE)
            bits.append(f"{len(self.capability_receipts)} receipt(s), {simulated} simulated")
        bits.append(f"{len(self.evidence)} evidence object(s)")
        if self.synthesis:
            bits.append(f"{len(self.synthesis.sections)} answer section(s)")
        if self.gaps:
            bits.append(f"{len(self.gaps)} gap(s)")
        return " · ".join(bits)


#: Fields that change between two runs of identical inputs. A replay comparison excludes exactly
#: these and nothing else.
VOLATILE_FIELDS: Tuple[str, ...] = ("at", "created_at", "updated_at", "latency_ms", "requested_at",
                                    "compiled_at", "framed_at",
                                    # HARNESS-003B's three. The stage ledger now carries its own
                                    # clocks and the elapsed time between them, and a replay
                                    # comparison that missed one would be uniformly red for the
                                    # only reason two runs are ALLOWED to differ. The existing
                                    # `canonical` test caught all three the moment they existed,
                                    # which is the argument for that test walking the whole tree
                                    # rather than the level somebody remembered.
                                    "queued_at", "started_at", "completed_at", "duration_ms")


def canonical(session: SemanticInquirySession) -> Dict[str, Any]:
    """The session with its clocks and latencies removed, for comparing two runs.

    Recursive, because the timestamps are not all at the top: a stage event carries `at`, a receipt
    carries `latency_ms`, the frame carries `framed_at`, the graph's receipts carry `requested_at`
    and `compiled_at`, and Lane B's events carry their own `at`. The HARNESS-002A lane shipped a
    `canonical()` that missed one of these by looking only at the level it remembered, and the
    fixtures caught it — so this one walks.
    """
    return _strip(session.model_dump(mode="json"))


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in VOLATILE_FIELDS}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


__all__ = [
    "SCHEMA_VERSION", "VOLATILE_FIELDS", "BARREN_OUTCOMES", "SUPPORTED_VERDICTS",
    "StageName", "StageOutcome", "ExecutionMode", "ReceiptStatus", "ClaimVerdictOutcome",
    "PostRef", "StageEvent", "CapabilityReceipt", "ClaimVerdict", "SynthesisSection", "Synthesis",
    "SessionProvenance", "SemanticInquirySession", "canonical", "sha256_of",
]
