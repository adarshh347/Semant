"""
HARNESS-003D — the pacer, and the six rules `DECISION-harness-003D-visible-rate-pacing` declares.

Every test here runs with an injected sleep and an injected clock, so the suite proves the WAITING
without doing any. That is not only speed: a test that actually slept would have to use a wait short
enough to be tolerable, and the rules that matter — a thirty-minute budget, a provider asking for
three minutes — are exactly the ones a tolerable wait cannot exercise.

The rules, in the decision's own order:

  1. serialise council requests against ONE provider allowance;
  2. prefer provider rate-limit/reset/`Retry-After` information;
  3. otherwise a declared configurable interval, never a topic-specific delay;
  4. a capacity retry sends IDENTICAL bytes under the same semantic attempt identity;
  5. persist and stream each refusal, wait, resumed request and outcome;
  6. bound it by a declared wall-clock budget and stop honestly at the boundary.
"""
from __future__ import annotations

import threading
from typing import Any, List

import pytest

from backend.schemas.semantic_compilation import (CapacityWaitRecord, DissolutionPass, PassOutcome,
                                                  PassReceipt)
from backend.services.semantic_compilation import pacing
from backend.services.semantic_compilation.passes import ModelPass, PassBudget, merge_receipts


# ── a provider that refuses, in the shapes a real one does ──────────────────

class FakeRefusal(Exception):
    """A 429 carrying whichever reset channel the case under test is about."""

    def __init__(self, message: str = "Rate limit reached", *, headers: Any = None,
                 status_code: int = 429):
        super().__init__(message)
        self.status_code = status_code
        self.headers = dict(headers or {})


class OtherFailure(Exception):
    """Anything that is not a capacity refusal. A 413 is the important one: the same bytes will be
    refused identically forever, so waiting on it would spend the budget proving that."""

    def __init__(self, message: str = "Request too large", status_code: int = 413):
        super().__init__(message)
        self.status_code = status_code


class Clock:
    """A monotonic clock that only moves when something sleeps on it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: List[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


def pacer_for(clock: Clock, **kwargs: Any) -> pacing.ProviderPacer:
    return pacing.ProviderPacer(sleep=clock.sleep, monotonic=clock.monotonic, **kwargs)


# ── 2 and 3: whose number is the wait ───────────────────────────────────────

@pytest.mark.parametrize("headers,message,expected,source", [
    ({"retry-after": "12"}, "Rate limit reached", 12.0, pacing.FROM_RETRY_AFTER),
    ({"retry-after-ms": "1500"}, "Rate limit reached", 1.5, pacing.FROM_RETRY_AFTER),
    ({"x-ratelimit-reset-tokens": "7.66s"}, "Rate limit reached", 7.66, pacing.FROM_RESET_HEADER),
    ({"x-ratelimit-reset-tokens": "2m59.56s"}, "Rate limit", 179.56, pacing.FROM_RESET_HEADER),
    ({}, "Rate limit reached. Please try again in 8.5s.", 8.5, pacing.FROM_MESSAGE),
    ({}, "Rate limit reached", pacing.DEFAULT_INTERVAL_SECONDS, pacing.FROM_DECLARED_INTERVAL),
])
def test_the_provider_is_asked_before_the_interval_is_guessed(headers, message, expected, source):
    """The declared interval is the LAST resort, not the policy."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    attempts = {"n": 0}

    def call():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise FakeRefusal(message, headers=headers)
        return "answered"

    result = pacer.send(call)

    assert result.ok and result.value == "answered"
    assert result.attempts == 2
    assert [w.source for w in result.waits] == [source]
    assert result.waits[0].seconds == pytest.approx(expected)
    assert clock.slept == pytest.approx([expected])


def test_the_longest_reset_wins_when_two_allowances_disagree():
    """Two windows means the request is admitted when the SLOWER one rolls. Taking the shorter
    sends bytes into a limit that is still spent, which costs an attempt to learn nothing."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeRefusal(headers={"x-ratelimit-reset-requests": "2s",
                                       "x-ratelimit-reset-tokens": "45s"})
        return "answered"

    result = pacer.send(call)
    assert result.waits[0].seconds == pytest.approx(45.0)


def test_a_declared_interval_is_configuration_and_not_a_topic():
    """The one number this module invents is a constant a deployment declares. Nothing about the
    inquiry reaches it — there is nowhere for a subject to enter."""
    clock = Clock()
    pacer = pacer_for(clock, interval_seconds=3.5)
    pacer.open_budget(600)
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeRefusal()
        return "answered"

    result = pacer.send(call)
    assert result.waits[0].seconds == 3.5
    assert result.waits[0].source == pacing.FROM_DECLARED_INTERVAL


# ── 4: identical bytes, one semantic attempt ────────────────────────────────

def test_a_capacity_retry_sends_the_same_bytes():
    """The pacer takes a THUNK, so it has nothing to vary. Proven by capturing what arrived."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    seen: List[Any] = []
    request = {"messages": [{"role": "user", "content": "the same words"}],
               "max_completion_tokens": 4096}

    def call():
        seen.append(dict(request))
        if len(seen) < 3:
            raise FakeRefusal(headers={"retry-after": "1"})
        return "answered"

    result = pacer.send(call)

    assert result.attempts == 3
    assert seen[0] == seen[1] == seen[2] == request
    assert len({repr(sorted(s.items(), key=str)) for s in seen}) == 1


def test_a_pass_that_waited_still_asked_once():
    """`call_count` is semantic attempts; `transport_attempts` is bytes on the wire. A run that
    merged them would report a rate-limited pass as one that could not make up its mind."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)

    pass_ = _TestPass(pacer=pacer, responses=[FakeRefusal(headers={"retry-after": "2"}),
                                              FakeRefusal(headers={"retry-after": "2"}),
                                              _completion('{"atoms": []}')])
    result = pass_.invoke("a prompt", inquiry_id="inq_1")

    assert result.receipt.call_count == 1
    assert result.receipt.transport_attempts == 3
    assert pass_.calls == 1
    assert result.parsed


# ── 1: one allowance, serialised, and the hold is shared ────────────────────

def test_requests_serialise_against_one_allowance():
    """Two threads through one pacer do not overlap. Three council roles firing concurrently into
    one 8000 TPM ceiling is the arrangement that produced Lane A's 429."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    inside = []
    peak = {"n": 0}
    lock = threading.Lock()

    def call():
        with lock:
            inside.append(1)
            peak["n"] = max(peak["n"], len(inside))
        # long enough that an unserialised pair would overlap on any machine
        threading.Event().wait(0.02)
        with lock:
            inside.pop()
        return "answered"

    threads = [threading.Thread(target=lambda: pacer.send(call)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak["n"] == 1


def test_a_reset_one_request_learns_is_waited_out_by_the_next():
    """The allowance belongs to the ACCOUNT. A request that gave up still leaves behind WHEN the
    window rolls, so the next pass holds instead of paying its own refusal to learn the same fact —
    and a refusal is itself a round trip against the allowance it is waiting for."""
    clock = Clock()
    pacer = pacer_for(clock, max_attempts=1)
    pacer.open_budget(600)

    first = pacer.send(lambda: (_ for _ in ()).throw(FakeRefusal(headers={"retry-after": "30"})))
    assert first.stopped_by == pacing.STOPPED_ATTEMPTS
    assert clock.slept == []               # it did not wait; it recorded the window and stopped

    clock.now += 1.0                       # a second passes; 29 of the window remain
    second = pacer.send(lambda: "answered")

    assert second.attempts == 1            # it was not refused
    assert [w.source for w in second.waits] == [pacing.FROM_RESET_HEADER]
    assert second.waits[0].seconds == pytest.approx(29.0, abs=0.01)
    assert second.waits[0].taken is True
    assert clock.slept == pytest.approx([29.0])


def test_a_hold_is_paid_once_rather_than_by_every_later_request():
    """A pass that WAITED out the window leaves nothing for the next one to wait on. Otherwise the
    fix for one wait per pass would be one wait per pass plus one."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeRefusal(headers={"retry-after": "30"})
        return "answered"

    pacer.send(call)
    assert clock.slept == [30.0]

    assert pacer.send(lambda: "answered").waits == ()
    assert clock.slept == [30.0]


# ── 6: the declared wall-clock budget ───────────────────────────────────────

def test_a_wait_that_would_cross_the_budget_is_not_taken():
    """`capacity_limited` at the boundary, not a partial graph called ratified."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(10)

    def call():
        raise FakeRefusal(headers={"retry-after": "60"})

    result = pacer.send(call)

    assert not result.ok
    assert result.stopped_by == pacing.STOPPED_BUDGET
    assert clock.slept == []
    assert [(w.source, w.taken) for w in result.waits] == [(pacing.STOPPED_BUDGET, False)]


def test_the_budget_is_spent_across_waits_rather_than_per_wait():
    """Per-wait budgeting is how a thirty-minute label ends up on a two-hour gate."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(25)
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        raise FakeRefusal(headers={"retry-after": "10"})

    result = pacer.send(call)

    assert clock.slept == [10.0, 10.0]          # 20 spent; the third would cross 25
    assert result.stopped_by == pacing.STOPPED_BUDGET
    assert calls["n"] == 3


def test_no_budget_opened_means_no_waiting_at_all():
    """None is not infinity. A pacer nobody started the clock on refuses to wait rather than
    waiting forever — an unbounded wait is the same refusal to report a limit as a shrunken corpus,
    spent differently."""
    clock = Clock()
    pacer = pacer_for(clock)

    result = pacer.send(lambda: (_ for _ in ()).throw(FakeRefusal(headers={"retry-after": "1"})))

    assert result.stopped_by == pacing.STOPPED_BUDGET
    assert clock.slept == []


def test_the_budget_default_is_thirty_minutes():
    assert pacing.DEFAULT_BUDGET_SECONDS == 30 * 60


def test_the_budget_is_configurable(monkeypatch):
    monkeypatch.setenv(pacing.BUDGET_ENV, "90")
    monkeypatch.setenv(pacing.INTERVAL_ENV, "4")
    monkeypatch.setenv(pacing.ATTEMPTS_ENV, "9")
    pacing.set_provider_pacer(None)
    try:
        pacer = pacing.provider_pacer()
        assert (pacer.budget_seconds, pacer.interval_seconds, pacer.max_attempts) == (90.0, 4.0, 9)
    finally:
        pacing.set_provider_pacer(None)


def test_attempts_are_bounded_so_a_permanent_refusal_still_finishes():
    clock = Clock()
    pacer = pacer_for(clock, max_attempts=3)
    pacer.open_budget(10_000)
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        raise FakeRefusal(headers={"retry-after": "1"})

    result = pacer.send(call)

    assert calls["n"] == 3
    assert result.stopped_by == pacing.STOPPED_ATTEMPTS
    assert not result.ok


# ── what is NOT a capacity refusal ──────────────────────────────────────────

def test_only_a_429_is_waited_on():
    """A 413 says the bytes are too large: re-sending them unchanged fails identically forever, and
    a pacer that waited on it would spend the whole gate budget re-learning the first answer."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        raise OtherFailure()

    result = pacer.send(call)

    assert calls["n"] == 1
    assert clock.slept == []
    assert result.waits == ()
    assert isinstance(result.error, OtherFailure)


def test_is_capacity_refusal_reads_a_nested_response_status():
    class Nested(Exception):
        response = type("R", (), {"status_code": 429})()

    assert pacing.is_capacity_refusal(Nested())
    assert not pacing.is_capacity_refusal(ValueError("nothing to do with a provider"))


# ── 5: it is announced BEFORE the wait, not after ───────────────────────────

def test_a_wait_is_announced_before_it_is_taken():
    """A wait reported once it is over is a wait nobody could watch, which is 002R's
    `visibility_failure` with a different cause underneath it."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    order: List[str] = []

    def sleeping(seconds):
        order.append(f"slept {seconds}")
        clock.now += seconds

    pacer._sleep = sleeping                                  # noqa: SLF001 — the seam under test
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeRefusal(headers={"retry-after": "5"})
        return "answered"

    pacer.send(call, on_event=lambda w: order.append(f"announced {w.seconds}"))

    assert order == ["announced 5.0", "slept 5.0"]


def test_an_observer_that_raises_does_not_break_the_call():
    """An observer is a UI concern reaching into a transport loop. One that turned a recoverable
    rate limit into a failed pass would be strictly worse than no observer."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    calls = {"n": 0}

    def call():
        calls["n"] += 1
        if calls["n"] == 1:
            raise FakeRefusal(headers={"retry-after": "1"})
        return "answered"

    def hostile(_wait):
        raise RuntimeError("the surface fell over")

    assert pacer.send(call, on_event=hostile).value == "answered"


def test_the_waiting_line_is_empty_where_nothing_waited():
    """No reassuring `0 waits`: a reader would have to tell that apart from a pacer nobody wired
    in, and those are different facts."""
    assert pacing.waiting_line([]) == ""
    assert "1 capacity wait" in pacing.waiting_line(
        [pacing.CapacityWait(1, 4.0, pacing.FROM_RETRY_AFTER)])
    assert "no wait was taken" in pacing.waiting_line(
        [pacing.CapacityWait(1, 60.0, pacing.STOPPED_BUDGET, taken=False)])


# ── the receipt carries all of it ───────────────────────────────────────────

def test_the_receipt_separates_waiting_from_thinking():
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    pass_ = _TestPass(pacer=pacer, responses=[FakeRefusal(headers={"retry-after": "3"}),
                                              _completion('{"atoms": []}')])

    receipt = pass_.invoke("a prompt", inquiry_id="inq_1").receipt

    assert receipt.transport_attempts == 2
    assert receipt.waited is True
    assert receipt.waited_ms == pytest.approx(3000.0)
    assert [w.source for w in receipt.capacity_waits] == [pacing.FROM_RETRY_AFTER]
    assert any("capacity wait" in n for n in receipt.notes)


def test_a_pass_that_never_waited_reports_no_waiting_rather_than_zero():
    """`waited_ms=None`, not 0.0. Zero says a pacer answered and reported no wait; None says
    nothing waited — and `duration_ms` already carries the same law one field over."""
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(600)
    pass_ = _TestPass(pacer=pacer, responses=[_completion('{"atoms": []}')])

    receipt = pass_.invoke("a prompt", inquiry_id="inq_1").receipt

    assert receipt.waited_ms is None
    assert receipt.capacity_waits == []
    assert receipt.transport_attempts == 1
    assert receipt.waited is False


def test_a_pass_the_budget_gave_up_on_errors_and_says_which_boundary():
    clock = Clock()
    pacer = pacer_for(clock)
    pacer.open_budget(2)
    pass_ = _TestPass(pacer=pacer, responses=[FakeRefusal(headers={"retry-after": "600"})])

    result = pass_.invoke("a prompt", inquiry_id="inq_1")

    assert result.receipt.outcome is PassOutcome.ERROR
    assert result.receipt.capacity_waits[0].source == pacing.STOPPED_BUDGET
    assert result.receipt.capacity_waits[0].taken is False
    assert any(pacing.STOPPED_BUDGET in r.why for r in result.refusals)


def test_merged_receipts_sum_the_waiting_and_keep_every_entry():
    """Six batches that each waited eleven seconds waited sixty-six. A merge reporting only the
    last would make a pass that spent a minute queueing look like one that spent eleven seconds."""
    parts = [
        PassReceipt(pass_id=f"p{i}", pass_name=DissolutionPass.SEMANTIC_DISSECTOR,
                    outcome=PassOutcome.COMPLETED, call_count=1, transport_attempts=2,
                    waited_ms=11_000.0,
                    capacity_waits=[CapacityWaitRecord(attempt=1, seconds=11.0,
                                                       source=pacing.FROM_RETRY_AFTER)])
        for i in range(6)]

    merged = merge_receipts(DissolutionPass.SEMANTIC_DISSECTOR, parts, inquiry_id="inq_1",
                            outcome=PassOutcome.COMPLETED)

    assert merged.call_count == 6
    assert merged.transport_attempts == 12
    assert merged.waited_ms == pytest.approx(66_000.0)
    assert len(merged.capacity_waits) == 6


# ── the pass double under test ──────────────────────────────────────────────

def _completion(content: str, finish_reason: str = "stop"):
    choice = type("Choice", (), {"message": type("M", (), {"content": content})(),
                                 "finish_reason": finish_reason})()
    return type("Completion", (), {"choices": [choice], "usage": None})()


class _TestPass(ModelPass):
    """A real `ModelPass` with a scripted provider. Everything the module does to a response —
    the geometry scan, the finish-reason rule, the receipt — runs unchanged."""

    role = "semantic_dissector"
    pass_name = DissolutionPass.SEMANTIC_DISSECTOR
    system_prompt = "a system prompt"
    budget = PassBudget(max_completion_tokens=4096, batch_size=3)

    def __init__(self, *, pacer, responses):
        super().__init__(client=self, pacer=pacer)
        self._responses = list(responses)
        self._served = 0
        self.requests: List[Any] = []

    # the SDK surface `invoke` reaches for
    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **request):
        self.requests.append(request)
        response = self._responses[min(self._served, len(self._responses) - 1)]
        self._served += 1
        if isinstance(response, BaseException):
            raise response
        return response

    @property
    def model(self):
        return "a-test-model"

    @property
    def provider(self):
        return "a-test-provider"

    def is_available(self) -> bool:
        return True

    def _get_client(self):
        return self
