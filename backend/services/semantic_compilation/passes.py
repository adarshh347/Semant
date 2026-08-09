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
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (CompilerRefusal, CompilerRefusalKind,
                                                  DissolutionPass, PassOutcome, PassReceipt)
from backend.services import role_registry

from . import contracts, ids
from .base import refusal, sha256_of


#: How much of a provider's error message travels onto the receipt. Enough to tell a rate limit
#: from a context overflow — which is the whole difference between "wait" and "send less" — and
#: bounded because a provider is free to return a page of HTML.
PROVIDER_DETAIL_CHARS = 300


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
                 budget: Optional[PassBudget] = None):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        if budget is not None:
            self.budget = budget
        self.calls = 0

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
            self._client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        except Exception:
            self._client = None
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    # ── the one call ──

    def invoke(self, user_prompt: str, *, inquiry_id: str, attempt: int = 1,
               inputs: int = 0) -> PassResult:
        """Exactly one request. Returns a receipt in every branch, including the ones that failed.

        The geometry scan runs on the RAW parsed payload, before anything is constructed. By the
        time a typed object exists `extra="forbid"` has already dropped the key and nobody can say
        it was ever there — and a pass emitting a box is the fact most worth recording.
        """
        pass_id = ids.pass_id(inquiry_id, self.pass_name, attempt)
        prompt_hash = sha256_of(user_prompt)

        if not self.is_available():
            return PassResult(None, self._receipt(
                pass_id, PassOutcome.UNAVAILABLE, prompt_hash=[prompt_hash], inputs=inputs,
                calls=0, detail=f"{self.role} is unavailable (no client or API key)"),
                (refusal(inquiry_id, CompilerRefusalKind.PASS_UNAVAILABLE, self.role,
                         f"{self.role} could not be reached, so nothing was attempted. Nothing "
                         f"rule-based was substituted: a fallback here would have to invent the "
                         f"decomposition this pass exists to produce."),))

        started = time.perf_counter()
        try:
            self.calls += 1
            completion = self._get_client().chat.completions.create(
                messages=[{"role": "system", "content": self.system_prompt},
                          {"role": "user", "content": user_prompt}],
                model=self.model,
                response_format={"type": "json_object"},
                max_completion_tokens=self.budget.max_completion_tokens)
            raw = completion.choices[0].message.content or ""
            finish = str(getattr(completion.choices[0], "finish_reason", "") or "")
            usage = getattr(completion, "usage", None)
            payload = json.loads(raw)
        except Exception as exc:                                   # noqa: BLE001
            duration = (time.perf_counter() - started) * 1000
            return PassResult(None, self._receipt(
                pass_id, PassOutcome.ERROR, prompt_hash=[prompt_hash], inputs=inputs,
                duration_ms=round(duration, 3),
                detail=f"{self.role} failed: {type(exc).__name__}: {_provider_detail(exc)}"),
                (refusal(inquiry_id, CompilerRefusalKind.PASS_UNAVAILABLE, self.role,
                         f"{self.role} raised {type(exc).__name__}: {_provider_detail(exc)}. One "
                         f"call was made and no retry was attempted; a retry loop would hide a "
                         f"marginal prompt behind a good average."),))

        duration = (time.perf_counter() - started) * 1000
        notes: List[str] = []
        outcome = PassOutcome.COMPLETED
        if finish == "length":
            outcome = PassOutcome.TRUNCATED
            notes.append(
                f"{self.role} ran out of its {self.budget.max_completion_tokens}-token completion "
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
                detail=f"{self.role} returned {type(payload).__name__}, not a JSON object"),
                (*refusals, refusal(inquiry_id, CompilerRefusalKind.UNPARSEABLE_MODEL_OUTPUT,
                                    type(payload).__name__,
                                    "the response was not a JSON object. Nothing was invented in "
                                    "its place.")))

        return PassResult(payload, self._receipt(
            pass_id, outcome, prompt_hash=[prompt_hash], raw=[raw], finish=[finish], usage=usage,
            duration_ms=round(duration, 3), inputs=inputs, notes=notes), tuple(refusals))

    # ── the receipt ──

    def _receipt(self, pass_id: str, outcome: PassOutcome, *, prompt_hash: Sequence[str] = (),
                 raw: Sequence[str] = (), finish: Sequence[str] = (), usage: Any = None,
                 duration_ms: Optional[float] = None, inputs: int = 0, outputs: int = 0,
                 detail: str = "", notes: Sequence[str] = (), calls: int = 1) -> PassReceipt:
        return PassReceipt(
            pass_id=pass_id, pass_name=self.pass_name, outcome=outcome,
            model=self.model, provider=self.provider, call_count=self.calls,
            finish_reasons=[f for f in finish if f],
            prompt_sha256=list(prompt_hash),
            raw_response_sha256=[sha256_of(r) for r in raw],
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            duration_ms=duration_ms, inputs=inputs, outputs=outputs, detail=detail,
            notes=list(notes))


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
               inputs: int = 0) -> PassResult:
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
                   outputs: int = 0, detail: str = "",
                   notes: Sequence[str] = ()) -> PassReceipt:
    """Several batch calls, as one receipt for the pass.

    The parts are summed rather than averaged, and every `finish_reason` is kept: one truncated
    batch out of six is a truncated pass, and an average would round it away.
    """
    durations = [r.duration_ms for r in receipts if r.duration_ms is not None]
    prompt_tokens = [r.prompt_tokens for r in receipts if r.prompt_tokens is not None]
    completion_tokens = [r.completion_tokens for r in receipts if r.completion_tokens is not None]
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
        notes=[*(n for r in receipts for n in r.notes), *notes])


def batched(items: Sequence[Any], size: int) -> List[List[Any]]:
    """Fixed-size batches. A request that cannot overflow is one that cannot be truncated into a
    plausible prefix, which is the whole reason this exists rather than one big call."""
    step = max(1, int(size))
    return [list(items[i:i + step]) for i in range(0, len(items), step)]


__all__ = ["PassBudget", "PassResult", "ModelPass", "FrozenPass", "merge_receipts", "batched"]
