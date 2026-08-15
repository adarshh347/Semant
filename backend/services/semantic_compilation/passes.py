"""
HARNESS-003A §7 — what every model pass in the council shares: a budget, a receipt, and one call.

Three roles run through this class. It is not a base class for the sake of one: the thing being
shared is the accounting, and the accounting is the lane's whole argument.

## One call per invocation, and no silent retry anywhere

`invoke` makes exactly one request and returns a receipt whether or not it worked. There is no loop
in this module, no `for attempt in range(...)`, and no `except: try again`. A retry loop hides a bad
prompt behind a good average: the pass that needed three attempts and the pass that worked first
time produce identical output, so nothing in the record says the prompt is marginal. When a repair
IS warranted the caller runs a second, DIFFERENT invocation with a different payload, and both
receipts survive.

## An explicit completion budget per pass

The rehearsal's compiler asked for everything in one response with no declared budget and was cut
off by the provider's default. Each pass here declares what it needs, so running out is a fact about
a known limit rather than a surprise — and `finish_reason` travels onto the receipt in every case,
including the ones that parsed cleanly.

## The outcome is decided by the caller, not by the parse

`invoke` returns `PassOutcome.COMPLETED` only in the sense of "a response arrived and parsed". Every
caller then narrows it — to `truncated`, `thin`, `coverage_failed` — because whether a pass did its
job is a question about the pass's own output, and only the caller knows what that job was. The
receipt's validator refuses `completed` alongside a length stop, so the narrowing cannot be skipped.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (CapacityWaitRecord, CompilerRefusal,
                                                  CompilerRefusalKind, DissolutionPass,
                                                  PassOutcome, PassReceipt)
from backend.services import role_registry

from . import contracts, ids, pacing
from .base import refusal, sha256_of


#: How much of a provider's error message travels onto the receipt. Enough to tell a rate limit
#: from a context overflow — which is the whole difference between "wait" and "send less" — and
#: bounded because a provider is free to return a page of HTML.
PROVIDER_DETAIL_CHARS = 300

#: How many times the SDK may re-send an identical request the provider refused for capacity.
#:
#: ZERO SINCE HARNESS-003D, and this is the second time this constant has moved — so the reasoning
#: matters more than the value. Lane A set it to 0 on the theory that a guarantee stopping at the
#: module boundary is not a guarantee; nine batches then fired in two seconds, every one was
#: refused, and the dissection came back empty. The rule had been applied to the wrong thing, and
#: the SDK's default was restored.
#:
#: It is 0 again now, and for the opposite reason: `pacing.ProviderPacer` re-sends the identical
#: bytes ITSELF, serialised against one provider allowance, on the provider's own reset information,
#: bounded by a declared wall-clock budget — and it RECORDS each refusal and each wait. The SDK's
#: retry does none of that. Two backoff loops stacked would double the waiting and hide half of it
#: inside somebody else's client, which is exactly the invisible waiting the decision forbids.
TRANSPORT_RETRIES = 0

TRANSPORT_RETRY_NOTE = (
    "`call_count` counts requests this module made — semantic attempts. Identical bytes re-sent "
    "after a capacity refusal are TRANSPORT attempts, counted separately in "
    "`transport_attempts` with each refusal and planned wait on `capacity_waits`. A transport "
    "retry re-sends a request the provider never read; it is not a second attempt at the prompt.")


#: How a sizing under-estimate announces itself on a receipt. HARNESS-003E sizes every request
#: against a conservative character bound because no tokenizer for the served model is in this tree;
#: this is the sentence that appears the day that bound is wrong, which is the only way anyone finds
#: out before a 413 does.
SIZING_UNDERESTIMATE = "sizing under-estimated this request"


def _sizing_shortfall(estimated: int, usage: Any) -> str:
    """The provider's own prompt-token count against what `sizing` predicted, when both exist.

    Silent when the estimate agrees or sits above, which is the intended direction — a note on
    every well-sized call would be noise a reader learns to skip, and this one has to be read.
    """
    actual = getattr(usage, "prompt_tokens", None)
    if not estimated or not isinstance(actual, int) or actual <= estimated:
        return ""
    return (f"{SIZING_UNDERESTIMATE}: {estimated} token(s) predicted, the provider counted "
            f"{actual}. The bound is meant to sit ABOVE the real count; a request sized this way "
            f"is one the allowance may refuse as too large.")


def _provider_detail(exc: BaseException) -> str:
    """The provider's own words, trimmed.

    `type(exc).__name__` alone was what the first live run recorded, and `APIStatusError` does not
    say whether the request was too large or the account was rate limited. Those need opposite
    fixes, so the message is kept.
    """
    text = " ".join(str(exc).split())
    return text[:PROVIDER_DETAIL_CHARS] or "(no message)"


@dataclass(frozen=True)
class PassBudget:
    """What one pass is allowed. Declared per pass rather than shared, because the three jobs are
    genuinely different sizes: dissection scales with the ledger, relation with the atom count, and
    operationalization with the claims that survived."""
    max_completion_tokens: int = 4096
    #: How many source objects go into one request. Batching is the direct answer to the failure:
    #: a request that cannot overflow is one that cannot be truncated into a plausible prefix.
    batch_size: int = 8


@dataclass(frozen=True)
class PassResult:
    """One call's outcome, in one object, whether or not anything came back."""
    payload: Optional[Mapping[str, Any]]
    receipt: PassReceipt
    refusals: Tuple[CompilerRefusal, ...] = ()

    @property
    def parsed(self) -> bool:
        return self.payload is not None


class ModelPass:
    """One thinker role, called once per invocation, with its accounting kept.

    Subclasses supply the role name, the pass name, the system prompt and the budget. Everything
    that could drift between three near-identical adapters — client resolution, timing, token
    accounting, the geometry scan, the finish-reason rule — lives here once.
    """

    role: str = ""
    pass_name: DissolutionPass = DissolutionPass.SEMANTIC_DISSECTOR
    system_prompt: str = ""
    budget: PassBudget = PassBudget()

    def __init__(self, client: Any = None, *, model: Optional[str] = None,
                 budget: Optional[PassBudget] = None, pacer: Any = None):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        if budget is not None:
            self.budget = budget
        self.calls = 0
        #: HARNESS-003D. The transport boundary's pacer. Injected for tests; the process's one
        #: pacer otherwise, because the allowance being paced is the account's and not the pass's.
        self._pacer = pacer
        #: An injected progress sink, set by the council for the duration of one compilation. A
        #: plain attribute rather than a constructor argument: the adapters are built once by
        #: `live_council()` and the observer belongs to a single run through them.
        self.observer: Optional[Callable[..., None]] = None

    # ── the provider ──

    @property
    def model(self) -> Optional[str]:
        return self._model if self._model is not None else role_registry.model_for(self.role)

    @property
    def provider(self) -> Optional[str]:
        return getattr(role_registry.get(self.role), "provider", None)

    def _get_client(self) -> Any:
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        try:
            from groq import Groq

            from backend.config import settings
            # TWO KINDS OF RETRY, and this lane forbids only one of them.
            #
            # A SEMANTIC retry re-asks a model that answered badly, and it is what `no silent
            # retry` is about: it hides a marginal prompt behind a good average, because the pass
            # that needed three attempts and the pass that worked first time produce identical
            # output. Nothing in this module does that.
            #
            # A TRANSPORT retry re-sends an IDENTICAL request the provider refused for capacity.
            # It hides nothing about the prompt — the request never reached a model — and the SDK
            # does it with backoff, which is the correct response to a 429.
            #
            # This was set to 0 for one run on the theory that a guarantee stopping at the module
            # boundary is not a guarantee. The live run said otherwise: nine batches fired in two
            # seconds, every one was rate limited, and the whole dissection came back empty with
            # eighteen `pass_unavailable` refusals. The rule had been applied to the wrong thing.
            #
            # It is 0 again since HARNESS-003D, and the difference is that the transport retry now
            # HAPPENS HERE, in `pacing.ProviderPacer`, where it is serialised against one account
            # allowance, timed from the provider's own reset information, bounded by a declared
            # wall-clock budget, and RECORDED on the receipt as it happens. Leaving the SDK's loop
            # on underneath it would stack two backoffs and hide one of them — see
            # `TRANSPORT_RETRIES`.
            self._client = (Groq(api_key=settings.GROQ_API_KEY, max_retries=TRANSPORT_RETRIES)
                            if settings.GROQ_API_KEY else None)
        except Exception:
            self._client = None
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    @property
    def pacer(self) -> Any:
        return self._pacer if self._pacer is not None else pacing.provider_pacer()

    def observe(self, label: str, **fields: Any) -> None:
        """Report progress from inside this pass, if anybody is listening.

        Swallows whatever the sink raises. An observer is a UI concern reaching into a model call,
        and one that broke the call it was watching would be strictly worse than no observer.
        """
        sink = self.observer
        if sink is None:
            return
        try:
            sink(label, **fields)
        except Exception:                                          # noqa: BLE001
            pass

    # ── the one call ──

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1,
               inputs: int = 0, system_prompt: Optional[str] = None,
               estimated_prompt_tokens: int = 0,
               completion_tokens: Optional[int] = None) -> PassResult:
        """Exactly one SEMANTIC request. Returns a receipt in every branch, including the failures.

        The geometry scan runs on the RAW parsed payload, before anything is constructed. By the
        time a typed object exists `extra="forbid"` has already dropped the key and nobody can say
        it was ever there — and a pass emitting a box is the fact most worth recording.

        ONE ASK, POSSIBLY SEVERAL SENDS. The request is built ONCE and handed to the pacer as a
        thunk; a capacity refusal re-sends that same closure. There is no branch here in which the
        prompt is rebuilt, so `no silent semantic retry` and `identical bytes on a capacity retry`
        are the same line of code rather than two rules that have to agree.

        `system_prompt` overrides this pass's own for one call. HARNESS-003E's cross-batch
        reconciliation is a different question asked by the same role, of the same model, inside the
        same receipt — a second `ModelPass` subclass for it would give it its own `call_count` and
        split one pass's accounting in half.

        `estimated_prompt_tokens` is what `sizing` said this request would cost. It is carried here
        for one purpose: comparing it against the provider's own `prompt_tokens` afterwards, so the
        claim that the bound is conservative is CHECKED on every live call rather than asserted in a
        docstring. An under-estimate is recorded by name; it is the one way this lane's arithmetic
        can be wrong in the direction that costs a 413.
        """
        pass_id = ids.pass_id(inquiry_id, self.pass_name, attempt)
        system = self.system_prompt if system_prompt is None else system_prompt
        # NEVER ABOVE THE PASS'S OWN DECLARED BUDGET. `sizing` may reserve less for a small batch;
        # it may not reserve more, because raising this is precisely what turned every one of Lane
        # A's requests into a 413.
        budget = (self.budget.max_completion_tokens if completion_tokens is None
                  else min(self.budget.max_completion_tokens, max(1, int(completion_tokens))))
        prompt_hash = sha256_of(user_prompt)

        if not self.is_available():
            return PassResult(None, self._receipt(
                pass_id, PassOutcome.UNAVAILABLE, prompt_hash=[prompt_hash], inputs=inputs,
                calls=0, detail=f"{self.role} is unavailable (no client or API key)"),
                (refusal(inquiry_id, CompilerRefusalKind.PASS_UNAVAILABLE, self.role,
                         f"{self.role} could not be reached, so nothing was attempted. Nothing "
                         f"rule-based was substituted: a fallback here would have to invent the "
                         f"decomposition this pass exists to produce."),))

        client = self._get_client()
        model = self.model
        # BUILT ONCE, ABOVE THE PACER. The dict is the request; the thunk closes over it. Nothing
        # below can vary it, which is what makes the capacity retry identical rather than merely
        # intended to be.
        request = dict(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user_prompt}],
            model=model,
            response_format={"type": "json_object"},
            max_completion_tokens=budget)

        started = time.perf_counter()
        self.calls += 1
        sent = self.pacer.send(lambda: client.chat.completions.create(**request),
                               on_event=self._announce_wait)
        waits = [CapacityWaitRecord(attempt=w.attempt, seconds=round(w.seconds, 3),
                                    source=w.source, detail=w.detail, taken=w.taken)
                 for w in sent.waits]
        transport = dict(transport_attempts=sent.attempts, capacity_waits=waits,
                         waited_ms=sent.waited_ms if sent.waits else None)

        try:
            if not sent.ok:
                raise sent.error
            completion = sent.value
            raw = completion.choices[0].message.content or ""
            finish = str(getattr(completion.choices[0], "finish_reason", "") or "")
            usage = getattr(completion, "usage", None)
            payload = json.loads(raw)
        except Exception as exc:                                   # noqa: BLE001
            duration = (time.perf_counter() - started) * 1000
            waiting = pacing.waiting_line(sent.waits)
            stopped = (f" The pacer stopped waiting: {sent.stopped_by}." if sent.stopped_by else "")
            return PassResult(None, self._receipt(
                pass_id, PassOutcome.ERROR, prompt_hash=[prompt_hash], inputs=inputs,
                duration_ms=round(duration, 3),
                detail=f"{self.role} failed: {type(exc).__name__}: {_provider_detail(exc)}"
                       + (f" · {waiting}" if waiting else ""),
                notes=[waiting] if waiting else (),
                **transport),
                (refusal(inquiry_id, CompilerRefusalKind.PASS_UNAVAILABLE, self.role,
                         f"{self.role} raised {type(exc).__name__}: {_provider_detail(exc)}. One "
                         f"semantic attempt was made and no second question was asked; a retry loop "
                         f"would hide a marginal prompt behind a good average."
                         + (f" {sent.attempts} transport attempt(s) sent identical bytes against a "
                            f"capacity refusal.{stopped}" if sent.waits else "")),))

        duration = (time.perf_counter() - started) * 1000
        notes: List[str] = []
        under = _sizing_shortfall(estimated_prompt_tokens, usage)
        if under:
            notes.append(under)
        outcome = PassOutcome.COMPLETED
        if finish == "length":
            outcome = PassOutcome.TRUNCATED
            notes.append(
                f"{self.role} ran out of its {budget}-token completion "
                f"budget. Whatever it produced is a PREFIX, and a short result here is not evidence "
                f"that there was little to produce.")

        refusals: List[CompilerRefusal] = []
        found = contracts.geometry_keys_in(payload)
        if found:
            refusals.append(refusal(
                inquiry_id, CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                f"{self.role} emitted a geometry, region or confidence key. Nothing has been "
                f"measured and this pass has not seen an image. Refused on the raw payload, before "
                f"anything was constructed: a key dropped by validation is one nobody can prove was "
                f"ever there."))

        if not isinstance(payload, Mapping):
            return PassResult(None, self._receipt(
                pass_id, PassOutcome.ERROR, prompt_hash=[prompt_hash], raw=[raw], finish=[finish],
                usage=usage, duration_ms=round(duration, 3), inputs=inputs,
                detail=f"{self.role} returned {type(payload).__name__}, not a JSON object",
                **transport),
                (*refusals, refusal(inquiry_id, CompilerRefusalKind.UNPARSEABLE_MODEL_OUTPUT,
                                    type(payload).__name__,
                                    "the response was not a JSON object. Nothing was invented in "
                                    "its place.")))

        waiting = pacing.waiting_line(sent.waits)
        return PassResult(payload, self._receipt(
            pass_id, outcome, prompt_hash=[prompt_hash], raw=[raw], finish=[finish], usage=usage,
            duration_ms=round(duration, 3), inputs=inputs,
            notes=[*notes, *( [waiting] if waiting else []), TRANSPORT_RETRY_NOTE],
            **transport), tuple(refusals))

    def _announce_wait(self, wait: Any) -> None:
        """A capacity refusal, reported the moment it happens rather than when the pass finishes.

        BEFORE the sleep, which is the whole reason the pacer calls this rather than returning a
        list. A wait reported afterwards is a wait nobody could watch, and the surface would show a
        stage frozen for four minutes with no account of why — which is 002R's `visibility_failure`
        with a different cause underneath it.
        """
        self.observe(
            "waiting for provider capacity" if wait.taken else "provider capacity refused",
            outcome="waiting" if wait.taken else "capacity_limited",
            detail=f"{wait.line()} — {wait.detail}".strip(" —"))

    # ── the receipt ──

    def _receipt(self, pass_id: str, outcome: PassOutcome, *, prompt_hash: Sequence[str] = (),
                 raw: Sequence[str] = (), finish: Sequence[str] = (), usage: Any = None,
                 duration_ms: Optional[float] = None, inputs: int = 0, outputs: int = 0,
                 detail: str = "", notes: Sequence[str] = (), calls: int = 1,
                 transport_attempts: int = 0,
                 capacity_waits: Sequence[CapacityWaitRecord] = (),
                 waited_ms: Optional[float] = None) -> PassReceipt:
        return PassReceipt(
            pass_id=pass_id, pass_name=self.pass_name, outcome=outcome,
            model=self.model, provider=self.provider,
            # ONE, not `self.calls`. The counter is cumulative across a batched pass, so putting it
            # on every batch receipt made `merge_receipts` sum 1+2+…+n — six calls reported as
            # twenty-one. The triangular number was the giveaway in the live run.
            call_count=calls,
            finish_reasons=[f for f in finish if f],
            prompt_sha256=list(prompt_hash),
            raw_response_sha256=[sha256_of(r) for r in raw],
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            duration_ms=duration_ms, inputs=inputs, outputs=outputs, detail=detail,
            notes=list(notes),
            transport_attempts=transport_attempts, capacity_waits=list(capacity_waits),
            waited_ms=waited_ms)


class FrozenPass(ModelPass):
    """Replays a frozen payload through the production parser, one batch at a time.

    The generality proof rests on this class holding no domain knowledge: two fixtures from
    unrelated subjects are two lists of JSON handed to one code path. It takes a SEQUENCE because a
    batched pass is called several times and a single payload would replay the first batch's answer
    to every batch.
    """

    def __init__(self, payloads: Sequence[Any], *, model: Optional[str] = None):
        super().__init__(client=None, model=model)
        self._payloads = list(payloads)
        self._served = 0

    def is_available(self) -> bool:
        return True

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1,
               inputs: int = 0, system_prompt: Optional[str] = None,
               estimated_prompt_tokens: int = 0) -> PassResult:
        pass_id = ids.pass_id(inquiry_id, self.pass_name, attempt)
        prompt_hash = sha256_of(user_prompt)
        if self._served >= len(self._payloads):
            # A FIXTURE THAT RAN OUT IS EMPTY, NOT REPEATED. Serving the last payload again would
            # make a batch look answered by a response written for different inputs.
            return PassResult(None, self._receipt(
                pass_id, PassOutcome.EMPTY, prompt_hash=[prompt_hash], inputs=inputs,
                detail="the frozen payload list is exhausted; this batch was not replayed"))
        payload = self._payloads[self._served]
        self._served += 1
        self.calls += 1
        refusals: List[CompilerRefusal] = []
        found = contracts.geometry_keys_in(payload)
        if found:
            refusals.append(refusal(
                inquiry_id, CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                f"the frozen {self.role} payload carries a geometry key. Replay runs the same scan "
                f"as a live call — a fixture is not exempt from a law."))
        return PassResult(payload if isinstance(payload, Mapping) else None, self._receipt(
            pass_id, PassOutcome.COMPLETED if isinstance(payload, Mapping) else PassOutcome.ERROR,
            prompt_hash=[prompt_hash],
            raw=[json.dumps(payload, sort_keys=True, ensure_ascii=False)], inputs=inputs,
            notes=["replayed from a frozen payload; no network call was made"]), tuple(refusals))

    @property
    def provider(self) -> Optional[str]:
        return None


def merge_receipts(pass_name: DissolutionPass, receipts: Sequence[PassReceipt], *,
                   inquiry_id: str, outcome: PassOutcome, attempt: int = 1,
                   outputs: int = 0, detail: str = "", notes: Sequence[str] = (),
                   batch_plan: Optional[Any] = None) -> PassReceipt:
    """Several batch calls, as one receipt for the pass.

    The parts are summed rather than averaged, and every `finish_reason` is kept: one truncated
    batch out of six is a truncated pass, and an average would round it away.

    `batch_plan` rides on the MERGED receipt and never on the parts. A plan is a fact about the
    partition, and one copy per batch would say the pass was partitioned once per batch — which is
    the same triangular-counting mistake `call_count` made in the first live run, in a field a
    reader trusts more.
    """
    durations = [r.duration_ms for r in receipts if r.duration_ms is not None]
    prompt_tokens = [r.prompt_tokens for r in receipts if r.prompt_tokens is not None]
    completion_tokens = [r.completion_tokens for r in receipts if r.completion_tokens is not None]
    # WAITING IS SUMMED AND ITS ENTRIES ARE KEPT. A pass whose six batches each waited eleven
    # seconds waited sixty-six, and a merged receipt reporting only the last one would make a pass
    # that spent most of a minute queueing look like one that spent eleven seconds.
    waited = [r.waited_ms for r in receipts if r.waited_ms is not None]
    return PassReceipt(
        pass_id=ids.pass_id(inquiry_id, pass_name, attempt),
        pass_name=pass_name, outcome=outcome,
        model=next((r.model for r in receipts if r.model), None),
        provider=next((r.provider for r in receipts if r.provider), None),
        call_count=sum(r.call_count for r in receipts) if receipts else 0,
        finish_reasons=[f for r in receipts for f in r.finish_reasons],
        prompt_sha256=[h for r in receipts for h in r.prompt_sha256],
        raw_response_sha256=[h for r in receipts for h in r.raw_response_sha256],
        prompt_tokens=sum(prompt_tokens) if prompt_tokens else None,
        completion_tokens=sum(completion_tokens) if completion_tokens else None,
        duration_ms=round(sum(durations), 3) if durations else None,
        inputs=sum(r.inputs for r in receipts), outputs=outputs, detail=detail,
        notes=[*(n for r in receipts for n in r.notes), *notes],
        transport_attempts=sum(r.transport_attempts for r in receipts),
        capacity_waits=[w for r in receipts for w in r.capacity_waits],
        waited_ms=round(sum(waited), 3) if waited else None,
        batch_plan=batch_plan)


def batched(items: Sequence[Any], size: int) -> List[List[Any]]:
    """Fixed-size batches. A request that cannot overflow is one that cannot be truncated into a
    plausible prefix, which is the whole reason this exists rather than one big call."""
    step = max(1, int(size))
    return [list(items[i:i + step]) for i in range(0, len(items), step)]


__all__ = ["PassBudget", "PassResult", "ModelPass", "FrozenPass", "merge_receipts", "batched"]
