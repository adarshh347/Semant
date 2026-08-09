"""
HARNESS-003B — the stage attempt: what the machinery did, when, for how long, and how it ended.

WHY THIS REPLACES `StageEvent`. The v1 event answered "did the theorist run, and if not, was it
unavailable, empty, refused or skipped?" That was the right question for a request that returned
only when everything had finished. It cannot answer the question a person watching a live inquiry
actually has, which is "what is happening NOW and how long has it been happening" — and it cannot
answer the one 002R's rehearsal exposed, which is "the compiler parsed, so why is the graph barren?"

Three additions carry that:

  TIME. `queued_at`, `started_at`, `completed_at` and a `duration_ms` that is NULL when unknown.
  Zero is a real measurement — a stage that begins and ends within one tick of a controlled clock
  genuinely took 0ms — so zero may never stand in for "we did not measure". A UI rendering an
  unknown duration as 0ms reports a fast stage where there was an unmeasured one.

  FOUR MORE ENDINGS. `thin`, `truncated` and `interrupted` join the seven. Each names a case v1
  reported as `completed` or `empty`:

      truncated    the producer stopped on its output budget. What came back is a PREFIX, and a
                   short graph is not evidence that the prompt decomposes into few claims.
      thin         it parsed and its OWN declared coverage check failed. A parse is not an
                   adequacy, and this is the most flattering failure in the chain because a
                   truncated response that happens to close its JSON looks exactly like an honest
                   short answer.
      interrupted  a `started` attempt whose process never returned. The call MAY have happened.

  TOPOLOGY AND COUNTS. What entered, what emerged, how many calls were planned and made. This is
  what lets `exhausted` say "31 reading blocks entered; 4 claims, 0 observables emerged" instead of
  "nothing was compiled" — the sentence 002R named as the difference between a report and a shrug.

COMPATIBILITY IS A READER, NOT A MIGRATION. Sessions written before this contract are in the store
and must keep opening. `StageAttempt` accepts a v1 `StageEvent` mapping and upgrades it in a
before-validator, and every field v1 never had comes back absent rather than zero — which is the
whole point of the null-duration law, applied to history.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "inquiry-stage-attempt.v1"


class StageName(str, Enum):
    """The declared stage interfaces the coordinator may call, and nothing else.

    Declared HERE rather than on the session envelope, which is where it lived until HARNESS-003B.
    The ledger is the thing that names stages, and a vocabulary living in the envelope while the
    ledger held bare strings is how `stage` came to be untyped in the first place —
    `inquiry_session` re-exports it, so no caller had to move.
    """
    FRAMER = "framer"
    THEORIST = "theorist"
    COMPILER = "compiler"
    STEWARD = "steward"
    CAPABILITY = "capability"
    JUDGE = "judge"
    COMPOSER = "composer"


class StageAttemptOutcome(str, Enum):
    """How an attempt stands. Eleven, and the ones that look redundant are the deliverable.

    From outside, `thin`, `truncated`, `empty`, `unavailable`, `refused`, `skipped` and `error` are
    all "that stage produced nothing useful". They tell a reader seven different things to do, and
    HARNESS-001B's table is the ancestor of this one:

        thin         it answered and its own coverage check failed   the prompt is not the problem
        truncated    it ran out of budget mid-answer                 give it room, or split the call
        empty        it ran and found nothing                        look somewhere else
        unavailable  it exists and is not running                    try again
        refused      a law said no                                   stop asking this of the machine
        skipped      the branch or budget excluded it                nothing is wrong
        error        it raised                                       fix it
        interrupted  it may have run; nobody knows                   decide, then re-enter by hand
    """
    QUEUED = "queued"
    STARTED = "started"
    COMPLETED = "completed"
    THIN = "thin"
    TRUNCATED = "truncated"
    EMPTY = "empty"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    ERROR = "error"
    INTERRUPTED = "interrupted"


#: An attempt in one of these will not change again. `queued` and `started` are deliberately absent:
#: a `started` attempt with no terminal successor is the crash signature this contract exists to
#: make visible, and a set that swallowed it would hide exactly that.
TERMINAL_OUTCOMES: Tuple[StageAttemptOutcome, ...] = (
    StageAttemptOutcome.COMPLETED, StageAttemptOutcome.THIN, StageAttemptOutcome.TRUNCATED,
    StageAttemptOutcome.EMPTY, StageAttemptOutcome.REFUSED, StageAttemptOutcome.UNAVAILABLE,
    StageAttemptOutcome.SKIPPED, StageAttemptOutcome.ERROR, StageAttemptOutcome.INTERRUPTED,
)

#: The stage ran, returned something, and it was not good enough — as distinct from not running and
#: from running and finding nothing. These are the three a product must never render as success.
UNDERPERFORMANCE_OUTCOMES: Tuple[StageAttemptOutcome, ...] = (
    StageAttemptOutcome.THIN, StageAttemptOutcome.TRUNCATED, StageAttemptOutcome.EMPTY,
)

#: Outcomes that produced no usable output at all. `truncated` and `thin` are NOT here: both
#: produced something partial that downstream stages may legitimately use, while saying so.
BARREN_ATTEMPT_OUTCOMES: Tuple[StageAttemptOutcome, ...] = (
    StageAttemptOutcome.EMPTY, StageAttemptOutcome.UNAVAILABLE, StageAttemptOutcome.REFUSED,
    StageAttemptOutcome.SKIPPED, StageAttemptOutcome.ERROR, StageAttemptOutcome.INTERRUPTED,
)


class TruncationSource(str, Enum):
    """Which route established whether a producer stopped on its output budget.

    `UNKNOWN` is not `NONE`, and the distance between them is the honesty of the whole field.
    `NONE` says a route was consulted and reported no truncation. `UNKNOWN` says nothing could be
    consulted. A product that rendered them alike would show an unchecked stage as a verified one —
    which is the shape this repository has now paid for repeatedly: a check whose evidence is the
    availability of a signal rather than the content of one.
    """
    FIELD = "field"
    PRODUCER_ATTRIBUTE = "producer_attribute"
    RECEIPT_NOTE = "receipt_note"
    NONE = "none"
    UNKNOWN = "unknown"


class AttemptExecutionMode(str, Enum):
    """`fixture` is not a weaker `live`; it is a different claim about what happened. `none` is for
    stages that call nothing external — a deterministic framer is neither."""
    FIXTURE = "fixture"
    LIVE = "live"
    NONE = "none"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


def _refuse_invented_duration(obj: Any, kind: str, name: str) -> Any:
    """THE NULL-DURATION LAW, in one place so three models cannot drift apart.

    A duration exists only where both ends were observed. Zero is a legitimate value — a controlled
    clock that does not advance across a stage genuinely yields 0.0 — which is precisely why zero
    may not double as "unmeasured": the two would be indistinguishable in the one field a reader
    consults to find the slow stage.
    """
    if obj.duration_ms is None:
        return obj
    if obj.started_at is None or obj.completed_at is None:
        raise ValueError(
            f"{kind} {name!r} states duration_ms={obj.duration_ms} with "
            f"started_at={obj.started_at!r} and completed_at={obj.completed_at!r}. A duration "
            f"without both ends was not measured; reporting one anyway is how an unmeasured stage "
            f"comes to look like a fast one.")
    if obj.duration_ms < 0:
        raise ValueError(f"{kind} {name!r} states a negative duration_ms={obj.duration_ms}")
    return obj


class StageCall(_Strict):
    """One external call a stage made, when the stage supplies them.

    Optional by design: no stage is required to itemise its calls, and one that does not is
    reported by its planned/actual counts alone rather than by an invented per-call record.
    """
    call_id: str = ""
    label: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    outcome: str = ""
    input_refs: List[str] = Field(default_factory=list)
    output_refs: List[str] = Field(default_factory=list)
    detail: str = ""

    @model_validator(mode="after")
    def _unknown_duration_stays_unknown(self) -> "StageCall":
        return _refuse_invented_duration(self, "call", self.call_id)


class SubstageEvent(_Strict):
    """Progress reported from INSIDE a stage — image 2 of 4, then a cross-image synthesis.

    Supplied by the stage through an injected observer. The coordinator never reaches into a
    stage's internals to discover these: it would have to import the semantic compiler to do so,
    and a stage runner that knew what a compiler was made of could not be reused for the next one.

    A stage that reports nothing still has its declared FLOOR recorded — how many inputs were
    selected and what topology it declared — because those are facts the coordinator holds itself.
    """
    substage_id: str = ""
    label: str = Field(..., description="what is happening, in words a person reads")
    index: Optional[int] = None
    total: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    at: Optional[str] = None
    duration_ms: Optional[float] = None
    outcome: str = ""
    refs: List[str] = Field(default_factory=list)
    detail: str = ""

    @model_validator(mode="after")
    def _index_fits_its_total(self) -> "SubstageEvent":
        if self.index is not None and self.total is not None and self.index > self.total:
            raise ValueError(
                f"substage reports {self.index} of {self.total}. A progress counter past its own "
                f"total is the shape a bar takes when it is counting the wrong thing.")
        return _refuse_invented_duration(self, "substage", self.substage_id or self.label)


#: v1 `StageEvent` field → v2 `StageAttempt` field. Read by the compatibility validator, and
#: declared as data so the upgrade is inspectable rather than buried in an if-chain.
_V1_FIELD_MAP = {"event_id": "attempt_id", "at": "queued_at", "detail": "summary"}

#: v1 outcomes, all seven of which are still v2 outcomes. Listed rather than assumed, because a
#: v1 value that quietly failed to be a v2 value would make an old session unopenable.
_V1_OUTCOMES = ("started", "completed", "empty", "unavailable", "refused", "skipped", "error")


class StageAttempt(_Strict):
    """One entry in the ledger of what the machinery did.

    `sequence` orders attempts within a session and is what keeps two attempts on one stage apart —
    a stage legitimately records `started` and then a terminal outcome, and a resumed session may
    enter a stage on a later branch.
    """
    schema_version: str = SCHEMA_VERSION
    attempt_id: str
    stage: StageName
    outcome: StageAttemptOutcome
    sequence: int = 0
    revision: int = 0

    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    #: Null when unknown. See `_refuse_invented_duration` — this is the field the law is about.
    duration_ms: Optional[float] = None

    role: str = ""
    model: Optional[str] = None
    provider: Optional[str] = None
    execution_mode: AttemptExecutionMode = AttemptExecutionMode.NONE

    input_refs: List[str] = Field(default_factory=list)
    #: What the stage said entered it. Carried, never inferred: an absent count is absent, and a
    #: zero written in its place would be a measurement nobody made.
    input_counts: Dict[str, int] = Field(default_factory=dict)
    output_refs: List[str] = Field(default_factory=list)
    output_counts: Dict[str, int] = Field(default_factory=dict)

    call_topology: str = ""
    planned_calls: Optional[int] = None
    actual_calls: Optional[int] = None
    calls: List[StageCall] = Field(default_factory=list)
    substages: List[SubstageEvent] = Field(default_factory=list)

    truncation_source: TruncationSource = TruncationSource.UNKNOWN
    #: One UI-safe sentence about the ATTEMPT. Never model output — see the `no-model-prose` law.
    summary: str = ""
    refusal_refs: List[str] = Field(default_factory=list)
    gap_refs: List[str] = Field(default_factory=list)
    receipt_refs: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _read_a_v1_event_too(cls, data: Any) -> Any:
        """THE COMPATIBILITY READER. A v1 `StageEvent` mapping becomes a v2 attempt.

        Sessions written before this contract are in the store and must keep opening. Every field
        v1 never had arrives ABSENT rather than zero: an old attempt's duration is unknown, not
        instant, and its call count is unrecorded, not none. That is the null-duration law applied
        to history, and it is why this is a reader rather than a migration — a migration would have
        had to invent the missing values in order to write them down.
        """
        if isinstance(data, BaseModel) and not isinstance(data, StageAttempt):
            # A v1 `StageEvent` OBJECT, not just its mapping. Callers hold these — the fixtures do —
            # and a reader that only understood the serialised form would work against the store
            # and fail against every caller that had the typed thing in hand.
            data = data.model_dump(mode="json")
        if not isinstance(data, Mapping):
            return data
        if "attempt_id" in data or "schema_version" in data:
            return data
        if "event_id" not in data:
            return data
        outcome = str(data.get("outcome") or "")
        if outcome and outcome not in _V1_OUTCOMES:
            # Not an upgrade path we know. Left alone so the field validator names it by value,
            # rather than coerced into the nearest neighbour.
            return data
        upgraded: Dict[str, Any] = {}
        for key, value in data.items():
            upgraded[_V1_FIELD_MAP.get(key, key)] = value
        upgraded["provenance"] = {**dict(upgraded.get("provenance") or {}),
                                  "upgraded_from": "semantic-inquiry-session.v1 StageEvent"}
        return upgraded

    @model_validator(mode="after")
    def _time_and_endings_agree(self) -> "StageAttempt":
        _refuse_invented_duration(self, "attempt", self.attempt_id)
        if self.outcome is StageAttemptOutcome.STARTED and self.completed_at is not None:
            raise ValueError(
                f"attempt {self.attempt_id!r} is `started` and carries a completed_at. A stage that "
                f"finished has a terminal outcome; leaving it `started` is how a crash signature "
                f"gets written over a successful run.")
        for name, count in (*self.input_counts.items(), *self.output_counts.items()):
            if count < 0:
                raise ValueError(f"attempt {self.attempt_id!r} reports {name}={count}")
        return self

    @property
    def detail(self) -> str:
        """The v1 name for `summary`, retained for readers.

        Kept as a property rather than a second field: one string, two spellings, and no way for
        them to disagree. Lane C is being written in parallel against the old name and Lane D
        retires it.
        """
        return self.summary

    @property
    def terminal(self) -> bool:
        return self.outcome in TERMINAL_OUTCOMES

    @property
    def underperformed(self) -> bool:
        return self.outcome in UNDERPERFORMANCE_OUTCOMES

    @property
    def produced_nothing(self) -> bool:
        return self.outcome in BARREN_ATTEMPT_OUTCOMES

    def counts_line(self) -> str:
        """`31 reading blocks in → 4 claims · 0 observables out`, or as much as was reported.

        Only what the stage itself declared. An unreported count contributes NOTHING to this string
        rather than a zero — 002R's whole complaint was a report that said "nothing was compiled",
        and replacing it with an invented "0 blocks in" would be the same failure with more digits.
        """
        left = " · ".join(f"{n} {k}" for k, n in sorted(self.input_counts.items()))
        right = " · ".join(f"{n} {k}" for k, n in sorted(self.output_counts.items()))
        if left and right:
            return f"{left} in → {right} out"
        return f"{left} in" if left else (f"{right} out" if right else "")


def duration_ms_between(started_at: Optional[str], completed_at: Optional[str]) -> Optional[float]:
    """Milliseconds between two handed-in stamps, or None.

    None on anything unparseable, deliberately: a clock this layer cannot read is a duration it did
    not measure, and the alternative — falling back to a wall clock to fill the gap — would time
    the parse failure instead of the stage.
    """
    from datetime import datetime

    if not started_at or not completed_at:
        return None
    try:
        start = datetime.fromisoformat(str(started_at))
        end = datetime.fromisoformat(str(completed_at))
    except (TypeError, ValueError):
        return None
    return max(0.0, (end - start).total_seconds() * 1000.0)


__all__ = [
    "SCHEMA_VERSION", "StageName", "TERMINAL_OUTCOMES", "UNDERPERFORMANCE_OUTCOMES",
    "BARREN_ATTEMPT_OUTCOMES",
    "StageAttemptOutcome", "TruncationSource", "AttemptExecutionMode",
    "StageCall", "SubstageEvent", "StageAttempt", "duration_ms_between",
]
