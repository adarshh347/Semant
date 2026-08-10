"""
HARNESS-003D — visible, bounded, rate-aware pacing at the remote-call transport boundary.

`DECISION-harness-003D-visible-rate-pacing` is the ruling this implements. Lane A's fifth live run
dissected the whole corpus — 105 atoms, every call `stop` — and then the account's 8000 TPM
allowance rate-limited the relation architect out before a single claim existed. The two obvious
answers were both refused: shrinking the reading changes the problem, and buying a provider tier
makes an architecture gate contingent on a purchase.

So the wait happens here, where it is honest, and it happens WHERE A PERSON CAN SEE IT.

## The distinction the whole module rests on

    a SEMANTIC retry re-asks a model that answered badly.       Forbidden. `passes.py` says why.
    a TRANSPORT retry re-sends bytes the provider never read.   This module, and only this module.

The difference is not a matter of degree. A semantic retry hides a marginal prompt behind a good
average, because the pass that needed three attempts and the pass that worked first time produce
identical output. A transport retry cannot hide anything about the prompt, because the prompt never
reached a model — the request was refused for capacity at the door.

`send` takes a THUNK. It cannot see the request, cannot rebuild it and cannot vary it; re-sending is
literally calling the same closure again. "Identical request bytes on a capacity retry" is therefore
a property of this function's signature rather than a promise in its docstring — the alternative,
handing it a payload to re-serialise, is the shape in which a retry quietly becomes a different
question.

## Why the counts stay apart

`call_count` on a `PassReceipt` counts SEMANTIC attempts — how many times a pass asked. This module
reports `transport_attempts`, which counts how many times bytes went on the wire. A pass that asked
once and was refused twice for capacity is `call_count=1, transport_attempts=3`, and merging those
into one number would make a rate-limited run look like a pass that could not make up its mind.

## Why the provider's own numbers come first

A fixed interval is a guess about somebody else's accounting. Groq reports `retry-after`,
`x-ratelimit-reset-tokens` and — in the refusal's own prose — `Please try again in 7.66s`. Those are
the allowance answering a question about itself, so they are consulted in that order and the
declared interval is what happens when NONE of them can be asked. The interval is a configured
constant and never a topic-specific delay: nothing here knows what the inquiry is about.

## Why it is bounded, and what happens at the boundary

A run that waits forever is not more honest than one that shrinks the corpus — it is the same
refusal to report a limit, spent differently. The gate declares a wall-clock budget (30 minutes per
prompt by default). A wait that would cross the deadline is not taken: the refusal propagates, the
pass ends as it honestly ended, and the record says the budget was exhausted rather than that the
provider said no one last time.

PURE-ISH. No model, no prompt, no schema. It sleeps and it reads headers. The clock and the sleep
are both injectable, which is what makes every rule below testable without waiting for any of it.
"""
from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Sequence, Tuple

#: The declared conservative interval, in seconds, for a capacity refusal that carries no reset
#: information at all. Not tuned to a topic and not derived from one: this is what "wait a bit"
#: means when the provider will not say how long.
DEFAULT_INTERVAL_SECONDS = 20.0

#: How many times identical bytes may be re-sent after a capacity refusal. Bounded so a provider
#: that refuses permanently produces a finished, reportable pass rather than a run that never ends.
DEFAULT_MAX_TRANSPORT_ATTEMPTS = 6

#: The gate's wall-clock budget for WAITING, per prompt. Thirty minutes is the decision's declared
#: default; `DECISION-harness-003D` is explicit that it settles this gate and not production latency.
DEFAULT_BUDGET_SECONDS = 30 * 60.0

#: Env names, so a deployment can declare its own without an edit here.
INTERVAL_ENV = "SEMANT_INQUIRY_PACING_INTERVAL_SECONDS"
ATTEMPTS_ENV = "SEMANT_INQUIRY_PACING_MAX_ATTEMPTS"
BUDGET_ENV = "SEMANT_INQUIRY_PACING_BUDGET_SECONDS"

#: Where a wait's length came from. Recorded on every wait, because "the provider told us 7.66s" and
#: "nobody would say, so we guessed 20s" are different facts about the same pause and a reader
#: deciding whether the pacing is working needs to know which one they are looking at.
FROM_RETRY_AFTER = "provider_retry_after"
FROM_RESET_HEADER = "provider_reset_header"
FROM_MESSAGE = "provider_message"
FROM_DECLARED_INTERVAL = "declared_interval"

#: Why waiting stopped. Not a source — these are the two ways a refusal survives the pacer.
STOPPED_BUDGET = "budget_exhausted"
STOPPED_ATTEMPTS = "attempts_exhausted"

#: Headers consulted, in order. `retry-after` is the HTTP-standard one; the two `x-ratelimit-reset-*`
#: are Groq's, and the token one is the allowance this account actually runs out of.
_RETRY_AFTER_HEADERS = ("retry-after", "retry-after-ms")
_RESET_HEADERS = ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests")

#: `7.66s`, `2m59.56s`, `500ms`, `1h2m3s`. `ms` is matched before `m` so a millisecond value is not
#: read as two and a half minutes — which is the kind of unit slip that turns a working pacer into
#: a run that hammers the allowance.
#:
#: NO TRAILING `\b`. It was there in the first draft and it silently dropped every leading part of a
#: compound duration: in `2m59.56s` there is no word boundary between `m` and `5`, so `2m` never
#: matched and a two-minute-fifty-nine wait was read as fifty-nine seconds. Which is worse than a
#: parse failure — a wait too short by two minutes sends bytes back into a limit that is still
#: spent, so the pacer would burn its attempts discovering the same refusal. `_ONLY_DURATION` does
#: the work `\b` was there for.
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)")
_UNIT_SECONDS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}

#: What is allowed to remain after the duration parts are removed. `Retry-After` may legitimately be
#: an HTTP-date (`Wed, 21 Oct 2015 07:28:00 GMT`), which is full of digits and the letters this
#: parser reads — so a string with anything else left in it is refused rather than half-read.
_ONLY_DURATION = re.compile(r"^[\s,]*$")

#: The refusal's own prose, as a last resort before the declared interval.
_TRY_AGAIN = re.compile(r"try again in\s+([0-9hms.\s]+)", re.IGNORECASE)


def parse_duration(raw: Any) -> Optional[float]:
    """Seconds, from a provider's duration string, or None.

    Accepts a bare number (the `Retry-After` standard) and the unit-suffixed form Groq uses. None
    rather than 0 on anything unreadable: a wait of zero is a decision to send immediately, and a
    header nobody could parse is not that decision.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if float(raw) >= 0 else None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        pass
    else:
        return value if value >= 0 else None
    if not _ONLY_DURATION.match(_DURATION_PART.sub("", text)):
        return None
    total = 0.0
    found = False
    for amount, unit in _DURATION_PART.findall(text):
        total += float(amount) * _UNIT_SECONDS[unit]
        found = True
    return total if found else None


def _headers_of(exc: BaseException) -> Any:
    """The refused response's headers, wherever the SDK put them. `{}` when there are none.

    Defensive on purpose. This reads an exception raised by somebody else's client, and a pacer that
    raised while inspecting a rate limit would convert a wait into a crash.
    """
    for owner in (exc, getattr(exc, "response", None)):
        headers = getattr(owner, "headers", None)
        if headers is not None:
            return headers
    return {}


def _header(headers: Any, name: str) -> Any:
    try:
        return headers.get(name)
    except Exception:                                            # noqa: BLE001
        return None


def is_capacity_refusal(exc: BaseException) -> bool:
    """Did the provider refuse these bytes for CAPACITY, without reading them?

    NARROW, and the narrowness is the point. `429` is the one status that means "the allowance is
    spent, ask again later" — the same bytes will be accepted once the window rolls. Everything else
    propagates untouched: a `413` says the request itself is too large and re-sending it unchanged
    would fail identically forever, and a `400` says the request was wrong. Waiting on either would
    spend the gate's whole budget proving something the first response already said.
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    return status == 429


@dataclass(frozen=True)
class CapacityWait:
    """One refusal, and the pause that followed it — or the pause that did not.

    `taken` is false where the budget or the attempt bound stopped the wait. Recorded rather than
    dropped: a run that gave up because it was out of time and a run that gave up because the
    provider kept refusing are different reports, and both are different from a run that never hit
    the limit at all.
    """
    attempt: int
    seconds: float
    source: str
    detail: str = ""
    taken: bool = True

    def line(self) -> str:
        if not self.taken:
            return f"transport attempt {self.attempt} refused for capacity; no wait ({self.source})"
        return (f"transport attempt {self.attempt} refused for capacity; waiting "
                f"{self.seconds:.2f}s ({self.source})")


@dataclass(frozen=True)
class TransportResult:
    """What one logical request cost at the transport boundary.

    `attempts` counts bytes on the wire and is deliberately not `call_count`: the pass asked once.
    """
    value: Any = None
    error: Optional[BaseException] = None
    attempts: int = 0
    waits: Tuple[CapacityWait, ...] = ()
    waited_ms: float = 0.0
    stopped_by: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def waited(self) -> bool:
        return any(w.taken for w in self.waits)


class ProviderPacer:
    """One provider allowance, serialised, with visible bounded waiting on a capacity refusal.

    SERIALISED because the allowance is per-account rather than per-pass. Three council roles firing
    concurrently into one 8000 TPM ceiling is the arrangement that produced Lane A's `429`, and no
    amount of per-pass backoff fixes contention the passes cannot see. One lock, held across the
    request, so the council's requests queue against the allowance instead of racing for it.

    THE HOLD IS SHARED TOO. A refusal establishes when the window rolls, and that fact is about the
    ACCOUNT, not about the request that discovered it. Every later request through this pacer waits
    out the same reset rather than each one learning it by being refused in turn — which is the
    difference between one wait and one wait per pass.
    """

    def __init__(self, *, interval_seconds: Optional[float] = None,
                 max_attempts: Optional[int] = None, budget_seconds: Optional[float] = None,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        self.interval_seconds = (DEFAULT_INTERVAL_SECONDS if interval_seconds is None
                                 else float(interval_seconds))
        self.max_attempts = (DEFAULT_MAX_TRANSPORT_ATTEMPTS if max_attempts is None
                             else max(1, int(max_attempts)))
        self.budget_seconds = (DEFAULT_BUDGET_SECONDS if budget_seconds is None
                               else float(budget_seconds))
        self._sleep = sleep
        self._monotonic = monotonic
        self._lock = threading.RLock()
        self._deadline: Optional[float] = None
        #: When the allowance is next expected to admit a request, learned from a refusal.
        self._hold_until: float = 0.0

    # ── the budget ──

    def open_budget(self, seconds: Optional[float] = None) -> None:
        """Start this prompt's wall-clock budget. Called once per compilation.

        Per PROMPT rather than per pass, because the decision bounds the rehearsal rather than any
        one call: five passes each granted thirty minutes is a two-and-a-half-hour gate wearing a
        thirty-minute label.
        """
        with self._lock:
            self.budget_seconds = (self.budget_seconds if seconds is None else float(seconds))
            self._deadline = self._monotonic() + self.budget_seconds
            self._hold_until = 0.0

    def budget_remaining(self) -> Optional[float]:
        """Seconds left, or None where no budget was opened. None is not infinity — it says nobody
        started the clock, and `send` refuses to wait in that state rather than waiting forever."""
        if self._deadline is None:
            return None
        return max(0.0, self._deadline - self._monotonic())

    # ── the one call ──

    def send(self, call: Callable[[], Any], *,
             on_event: Optional[Callable[[CapacityWait], None]] = None) -> TransportResult:
        """Put these bytes on the wire, and put the SAME bytes back on it if capacity refuses them.

        `call` is a thunk the caller built with its final request. This function never inspects it,
        never rebuilds it and has no way to vary it, so a capacity retry is identical by
        construction. `on_event` is called BEFORE each wait rather than after, because a wait
        reported once it is over is a wait nobody could watch — which is the whole complaint the
        decision's `may not look frozen` clause is about.
        """
        waits: List[CapacityWait] = []
        waited = 0.0
        with self._lock:
            for attempt in range(1, self.max_attempts + 1):
                held = self._hold_for_the_window(attempt, waits, on_event)
                waited += held
                try:
                    return TransportResult(value=call(), attempts=attempt, waits=tuple(waits),
                                           waited_ms=round(waited * 1000, 3))
                except BaseException as exc:                      # noqa: BLE001
                    if not is_capacity_refusal(exc):
                        return TransportResult(error=exc, attempts=attempt, waits=tuple(waits),
                                               waited_ms=round(waited * 1000, 3))
                    seconds, source, detail = self._wait_for(exc)
                    # THE WINDOW IS RECORDED WHETHER OR NOT THIS REQUEST WAITS ON IT. When it does,
                    # the hold is already in the past by the time the next request asks, so nothing
                    # waits twice. When this request GIVES UP — out of attempts, out of budget — the
                    # next one still knows when the allowance rolls, instead of paying its own
                    # refusal to learn a fact this one already established.
                    self._hold_until = self._monotonic() + seconds
                    if attempt >= self.max_attempts:
                        waits.append(CapacityWait(attempt, 0.0, STOPPED_ATTEMPTS, detail,
                                                  taken=False))
                        _announce(on_event, waits[-1])
                        return TransportResult(error=exc, attempts=attempt, waits=tuple(waits),
                                               waited_ms=round(waited * 1000, 3),
                                               stopped_by=STOPPED_ATTEMPTS)
                    remaining = self.budget_remaining()
                    if remaining is None or seconds > remaining:
                        waits.append(CapacityWait(attempt, seconds, STOPPED_BUDGET, detail,
                                                  taken=False))
                        _announce(on_event, waits[-1])
                        return TransportResult(error=exc, attempts=attempt, waits=tuple(waits),
                                               waited_ms=round(waited * 1000, 3),
                                               stopped_by=STOPPED_BUDGET)
                    entry = CapacityWait(attempt, seconds, source, detail)
                    waits.append(entry)
                    _announce(on_event, entry)
                    self._sleep(seconds)
                    waited += seconds
        # Unreachable: every branch of the loop returns. Kept so the type is honest.
        return TransportResult(attempts=0, waits=tuple(waits), waited_ms=round(waited * 1000, 3))

    def _hold_for_the_window(self, attempt: int, waits: List[CapacityWait],
                             on_event: Optional[Callable[[CapacityWait], None]]) -> float:
        """Wait out a reset ANOTHER request already discovered, before sending at all.

        This is the half that makes a five-pass council finish. Without it every pass learns the
        window by being refused, so the run pays one refusal per pass for a fact the first refusal
        established — and each of those refusals is a request that consumed part of the allowance it
        was waiting for.
        """
        now = self._monotonic()
        if self._hold_until <= now:
            return 0.0
        seconds = self._hold_until - now
        remaining = self.budget_remaining()
        if remaining is None or seconds > remaining:
            self._hold_until = 0.0
            return 0.0
        entry = CapacityWait(attempt, seconds, FROM_RESET_HEADER,
                             "holding for a reset an earlier request established; the allowance is "
                             "the account's, not this request's")
        waits.append(entry)
        _announce(on_event, entry)
        self._sleep(seconds)
        return seconds

    def _wait_for(self, exc: BaseException) -> Tuple[float, str, str]:
        """How long to wait, and on whose authority. The provider first, always."""
        headers = _headers_of(exc)
        for name in _RETRY_AFTER_HEADERS:
            raw = _header(headers, name)
            seconds = parse_duration(raw)
            if seconds is not None:
                # `retry-after-ms` is milliseconds by name; `parse_duration` reads a bare number as
                # seconds, so the unit is applied here rather than guessed there.
                if name.endswith("-ms") and not _DURATION_PART.search(str(raw)):
                    seconds = seconds / 1000.0
                return seconds, FROM_RETRY_AFTER, f"{name}: {raw}"

        resets = [(name, parse_duration(_header(headers, name))) for name in _RESET_HEADERS]
        known = [(name, s) for name, s in resets if s is not None]
        if known:
            # The LONGEST reset, not the first. Two allowances with different windows means the
            # request is admitted when the slower one rolls, and taking the shorter would send bytes
            # into a limit that is still spent.
            name, seconds = max(known, key=lambda pair: pair[1])
            return seconds, FROM_RESET_HEADER, f"{name}: {_header(headers, name)}"

        match = _TRY_AGAIN.search(" ".join(str(exc).split()))
        if match:
            # The sentence ends in a full stop and the duration does not. Stripped here rather than
            # widened in `_ONLY_DURATION`, which exists precisely to refuse a string with stray
            # characters in it — loosening it to admit this one would also admit an HTTP-date.
            said = match.group(1).strip().strip(".")
            seconds = parse_duration(said)
            if seconds is not None:
                return seconds, FROM_MESSAGE, f"the refusal said: try again in {said}"

        return (self.interval_seconds, FROM_DECLARED_INTERVAL,
                f"the refusal carried no reset information; waiting the declared "
                f"{self.interval_seconds:g}s interval")


def _announce(on_event: Optional[Callable[[CapacityWait], None]], wait: CapacityWait) -> None:
    """Report a wait, and never let the reporting break the waiting.

    An observer is a UI concern reaching into a transport loop. One that raised would turn a
    recoverable rate limit into a failed pass, which is a strictly worse outcome than a wait nobody
    watched.
    """
    if on_event is None:
        return
    try:
        on_event(wait)
    except Exception:                                            # noqa: BLE001
        pass


def _env_float(name: str, default: Optional[float]) -> Optional[float]:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: Optional[int]) -> Optional[int]:
    value = _env_float(name, None)
    return default if value is None else int(value)


_PACER: Optional[ProviderPacer] = None
_PACER_LOCK = threading.Lock()


def provider_pacer() -> ProviderPacer:
    """The process's one pacer, because the account has one allowance.

    A pacer per pass would serialise nothing: three roles each politely backing off against a limit
    they cannot see each other spending is the arrangement that produced the run this exists to
    repair.
    """
    global _PACER
    with _PACER_LOCK:
        if _PACER is None:
            _PACER = ProviderPacer(
                interval_seconds=_env_float(INTERVAL_ENV, DEFAULT_INTERVAL_SECONDS),
                max_attempts=_env_int(ATTEMPTS_ENV, DEFAULT_MAX_TRANSPORT_ATTEMPTS),
                budget_seconds=_env_float(BUDGET_ENV, DEFAULT_BUDGET_SECONDS))
        return _PACER


def set_provider_pacer(pacer: Optional[ProviderPacer]) -> None:
    """Bind a pacer, or reset to the configured one. For tests and for a rehearsal that declares its
    own budget on the command line."""
    global _PACER
    with _PACER_LOCK:
        _PACER = pacer


def waiting_line(waits: Sequence[CapacityWait]) -> str:
    """One sentence about the waiting, or nothing at all.

    Empty where nothing waited, deliberately: a run that never hit the allowance should not carry a
    reassuring `0 waits` note, because a reader would then have to tell the difference between that
    and a pacer nobody wired in.
    """
    taken = [w for w in waits if w.taken]
    if not taken:
        stopped = [w for w in waits if not w.taken]
        if stopped:
            return (f"{len(stopped)} capacity refusal(s), and no wait was taken "
                    f"({stopped[-1].source})")
        return ""
    total = sum(w.seconds for w in taken)
    return (f"{len(taken)} capacity wait(s) totalling {total:.1f}s, longest "
            f"{max(w.seconds for w in taken):.1f}s")


__all__ = [
    "DEFAULT_INTERVAL_SECONDS", "DEFAULT_MAX_TRANSPORT_ATTEMPTS", "DEFAULT_BUDGET_SECONDS",
    "INTERVAL_ENV", "ATTEMPTS_ENV", "BUDGET_ENV",
    "FROM_RETRY_AFTER", "FROM_RESET_HEADER", "FROM_MESSAGE", "FROM_DECLARED_INTERVAL",
    "STOPPED_BUDGET", "STOPPED_ATTEMPTS",
    "parse_duration", "is_capacity_refusal", "CapacityWait", "TransportResult", "ProviderPacer",
    "provider_pacer", "set_provider_pacer", "waiting_line",
]
