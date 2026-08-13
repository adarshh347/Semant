"""
HARNESS-003E — sizing a request against the provider's allowance, before it is sent.

    the fixed part of a prompt + the items it would carry + the completion reservation
      -> a conservative token estimate
      -> a deterministic partition into requests that FIT
      -> a plan that says which items each request answers for, and why each boundary is there

THE FAILURE THIS EXISTS FOR, in the provider's own words:

    413 Request too large for model `…` … service tier `on_demand`
    on tokens per minute (TPM): Limit 8000, Requested 9827

182 atoms in one request. Not congestion — a request the account cannot send at any moment, however
long anything waits, which is why `pacing.is_capacity_refusal` refuses to re-send it. The repair is
not to wait differently. It is to know the size BEFORE the bytes go out.

## Why the completion budget is part of the request size

Lane A raised `max_completion_tokens` from 4096 to 8192 and every call began failing outright. A
provider counts the RESERVATION against the per-minute allowance whether or not the model spends it,
so `estimated_total_tokens` is the prompt plus the reservation and the sizing is done against that
sum. Sizing the prompt alone would produce batches that fit and requests that do not.

## Why a conservative character bound rather than a tokenizer

The honest options were three. A model tokenizer for the served model is not in this tree and is not
downloadable at request time without making a compilation depend on a network fetch. `transformers`
is present but only in `requirements-ml.txt`, which the API does not install, and a sizing rule that
silently changed behaviour depending on which requirements file a box had installed would be worse
than a coarse rule everywhere. So: a declared floor on characters per token.

`CHARS_PER_TOKEN_FLOOR = 3.0` means "assume no fewer than one token per three characters". Byte-pair
encodings of English prose and of the JSON these prompts carry run 3.5–4.2 characters per token, so
this over-estimates by roughly 15–40% and the margin absorbs the rest. Over-estimating costs extra
batches; under-estimating costs a 413, and those are not symmetric.

AND THE BOUND IS CHECKED RATHER THAN ASSERTED. `passes.ModelPass.invoke` compares this estimate
against the provider's own reported `prompt_tokens` on every live call and records an under-estimate
on the receipt by name. A conservative bound nobody verifies is a guess with a confident docstring.

## Determinism

No clock, no randomness, no counter. The partition is a function of the item texts, their affinity
keys and the declared allowance, and the ids are content-derived — so the same input plans the same
way on a re-run, which is what makes a replay a comparison rather than an act of faith.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (BATCH_PLAN_VERSION, BatchAssignment,
                                                  BatchBoundaryReason, BatchPlanRecord,
                                                  ComparisonPair, DissolutionPass)

from . import ids

PRODUCER = "semantic_compilation/sizing-v1"

#: The account's per-minute token allowance. 8000 is what the live runs met; it is configurable
#: because it is a fact about a deployment's provider tier and not about this code.
DEFAULT_ALLOWANCE_TOKENS = 8000

#: Held back from the allowance for everything this module cannot see: the provider's own message
#: framing, a system prompt edited between planning and sending, and the gap between a character
#: bound and a real tokenizer on input we have not met. A tenth of the allowance, declared rather
#: than tuned — the number that matters is that it exists and is reported on every batch.
DEFAULT_SAFETY_MARGIN_TOKENS = 800

#: Characters per token, as a FLOOR. See the module note: the direction of the error is chosen.
CHARS_PER_TOKEN_FLOOR = 3.0

#: Per chat message, for the role/name framing every provider adds around content it did not send.
PER_MESSAGE_OVERHEAD_TOKENS = 8

#: The request envelope outside the messages — model name, response format, the budget field.
REQUEST_ENVELOPE_TOKENS = 24

ALLOWANCE_ENV = "SEMANT_INQUIRY_PROVIDER_ALLOWANCE_TOKENS"
MARGIN_ENV = "SEMANT_INQUIRY_SIZING_MARGIN_TOKENS"


def estimate_tokens(text: Any) -> int:
    """A conservative upper bound on what one string costs. Deterministic, and never zero for
    non-empty text — a rule that returned 0 for a short item would pack an unbounded number of
    them."""
    length = len(str(text or ""))
    if not length:
        return 0
    return max(1, math.ceil(length / CHARS_PER_TOKEN_FLOOR))


def estimate_request_tokens(system_prompt: str, user_prompt: str, *,
                            completion_tokens: int) -> int:
    """What the provider will count against the allowance for this exact request.

    The prompt AND the reservation, because the reservation is charged whether it is spent or not —
    the single most expensive thing Lane A learned, and the reason a sizing rule that looked only at
    the prompt would plan batches that fit and send requests that do not.
    """
    return (estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
            + 2 * PER_MESSAGE_OVERHEAD_TOKENS + REQUEST_ENVELOPE_TOKENS
            + max(0, int(completion_tokens)))


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


@dataclass(frozen=True)
class Allowance:
    """What one request may cost, and what is held back from it.

    A value rather than module state so a test, a rehearsal script and a deployment can each declare
    their own without any of them reaching into a global.
    """
    tokens: int = DEFAULT_ALLOWANCE_TOKENS
    margin_tokens: int = DEFAULT_SAFETY_MARGIN_TOKENS

    @property
    def usable_tokens(self) -> int:
        return max(0, self.tokens - self.margin_tokens)

    def fixed_cost(self, fixed_text: str) -> int:
        """What every request pays before it carries a single item.

        The system prompt, the vocabulary and the JSON scaffolding are charged on EVERY request,
        which is why a plan of many small requests is not free — the fixed part is paid once per
        batch rather than once per compilation, and it is the reason the sizing packs batches full
        rather than splitting evenly.
        """
        return (estimate_tokens(fixed_text) + 2 * PER_MESSAGE_OVERHEAD_TOKENS
                + REQUEST_ENVELOPE_TOKENS)


def configured_allowance() -> Allowance:
    return Allowance(tokens=_env_int(ALLOWANCE_ENV, DEFAULT_ALLOWANCE_TOKENS),
                     margin_tokens=_env_int(MARGIN_ENV, DEFAULT_SAFETY_MARGIN_TOKENS))


@dataclass(frozen=True)
class CompletionPolicy:
    """What to reserve for the ANSWER, as a function of how much was asked. HARNESS-003E.

    ## Why this is not "lowering the token limit"

    003D's second-order finding, in its own words: `openai/gpt-oss-120b` emits reasoning tokens into
    the same completion budget as the JSON, "so the ceiling is not the ceiling the sizing assumed —
    and no code in the lane counts it". This is the code that counts it. `reserved_tokens` is the
    reasoning-and-framing headroom charged once per request whatever the batch holds, and
    `per_item_tokens` is what one item's share of the answer is expected to cost on top.

    Sizing the answer to the question is what makes the batches BIGGER, not smaller. A flat 4096
    reservation against an 8000 allowance spends more than half of every request on an answer a
    twelve-atom batch cannot produce, so the items get 1,495 tokens of room and the pass needs
    sixteen requests. Reserving what the batch can plausibly emit gives the items three times the
    room and the pass a third of the requests — and the same total number of atoms crosses the wire
    either way.

    `maximum_tokens` is the pass's own declared budget and is a CEILING that is never raised. The
    003D finding is explicit that raising it is what turned every request into a 413.

    A batch that truncates anyway is still `truncated`, still fails `completed`, and still says so.
    The reservation being derived rather than flat changes what is asked for; it changes nothing
    about what a length stop means.
    """
    reserved_tokens: int
    per_item_tokens: int = 0
    minimum_tokens: int = 0
    maximum_tokens: int = 4096

    @classmethod
    def flat(cls, tokens: int) -> "CompletionPolicy":
        """A fixed reservation, for a pass whose answer does not scale with its input."""
        return cls(reserved_tokens=tokens, per_item_tokens=0, minimum_tokens=tokens,
                   maximum_tokens=tokens)

    def for_batch(self, count: int) -> int:
        floor = max(self.minimum_tokens, self.reserved_tokens)
        return max(1, min(self.maximum_tokens,
                          max(floor, self.reserved_tokens + self.per_item_tokens * max(0, count))))

    def room(self, allowance: Allowance, fixed_text: str) -> int:
        """Tokens available for items AND their share of the answer, in one number.

        The packing below spends `item.tokens + per_item_tokens` per item against this, which is
        what makes "the request fits" a property of the arithmetic rather than a second check:
        `fixed + Σitem + reserved + per_item·k ≤ usable` follows directly from
        `Σ(item + per_item) ≤ usable − fixed − reserved`.
        """
        return allowance.usable_tokens - allowance.fixed_cost(fixed_text) - max(
            self.reserved_tokens, self.minimum_tokens)


@dataclass(frozen=True)
class SizedItem:
    """One thing a request may carry: what it is called, what it costs, and what it belongs with.

    `affinity` is a preference and never a constraint. Atoms from one source unit or one image are
    kept together where they fit, because a relation between two readings of the same picture is the
    one most likely to be found locally — but an affinity group larger than a request is SPLIT, with
    the split reported, rather than sent as a request that cannot go.
    """
    ref: str
    text: str
    affinity: str = ""

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


@dataclass(frozen=True)
class SizedBatch:
    """A planned request, with the items themselves rather than only their refs.

    The plan RECORD carries refs, because it is stored on the graph and a graph that repeated every
    atom's text inside its own plan would double the object for no reader. This is the working
    object the pass iterates.
    """
    assignment: BatchAssignment
    items: Tuple[SizedItem, ...] = ()

    @property
    def batch_id(self) -> str:
        return self.assignment.batch_id

    @property
    def sendable(self) -> bool:
        return self.assignment.sendable


@dataclass(frozen=True)
class BatchPlan:
    """The partition, as the pass consumes it and as the graph records it."""
    record: BatchPlanRecord
    batches: Tuple[SizedBatch, ...] = ()
    room_tokens: int = 0

    @property
    def sendable(self) -> Tuple[SizedBatch, ...]:
        return tuple(b for b in self.batches if b.sendable)

    @property
    def unsendable(self) -> Tuple[SizedBatch, ...]:
        return tuple(b for b in self.batches if not b.sendable)


def _grouped(items: Sequence[SizedItem]) -> List[List[SizedItem]]:
    """Items gathered by affinity, in first-appearance order of both the keys and the items.

    First-appearance rather than sorted: the caller's order is already content-derived (the ledger's
    order, the dissection's order), and re-sorting here would introduce a second ordering opinion
    that the caller's tests would then have to know about.
    """
    order: List[str] = []
    groups: Dict[str, List[SizedItem]] = {}
    for item in items:
        key = item.affinity or item.ref
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    return [groups[k] for k in order]


def plan(items: Sequence[SizedItem], *, inquiry_id: str, pass_name: DissolutionPass, unit: str,
         fixed_text: str, completion: CompletionPolicy, allowance: Optional[Allowance] = None,
         context_refs_for: Optional[Any] = None, note: str = "") -> BatchPlan:
    """Partition `items` into requests that fit, deterministically, with every boundary explained.

    EVERY ITEM IS PRIMARY IN EXACTLY ONE BATCH. That is the property the whole repair rests on: it
    is what makes "every atom was locally considered" a number the plan can be asked for, rather
    than a claim the pass makes about itself. `BatchPlanRecord` refuses a plan that breaks it.

    A single item larger than one whole request is not dropped and not trimmed. It gets a batch of
    its own marked `sendable=False`, and the caller reports it as refused — which is the 413 caught
    by arithmetic instead of by the provider, at no cost to the allowance.
    """
    allowance = allowance or configured_allowance()
    room = completion.room(allowance, fixed_text)
    fixed_tokens = allowance.fixed_cost(fixed_text)
    share = max(0, completion.per_item_tokens)

    planned: List[Tuple[List[SizedItem], BatchBoundaryReason]] = []
    current: List[SizedItem] = []
    spent = 0

    def close(reason: BatchBoundaryReason) -> None:
        nonlocal current, spent
        if current:
            planned.append((current, reason))
        current, spent = [], 0

    for group in _grouped(items):
        group_cost = sum(i.tokens + share for i in group)
        # A WHOLE GROUP THAT FITS STAYS WHOLE. The seam is placed where a relation is least likely
        # to cross rather than wherever the arithmetic happened to run out.
        if current and group_cost <= room and spent + group_cost > room:
            close(BatchBoundaryReason.AFFINITY_BOUNDARY)
        for item in group:
            if item.tokens + share > room:
                close(BatchBoundaryReason.ALLOWANCE_REACHED)
                planned.append(([item], BatchBoundaryReason.OVERSIZED_ITEM))
                continue
            if current and spent + item.tokens + share > room:
                close(BatchBoundaryReason.ALLOWANCE_REACHED)
            current.append(item)
            spent += item.tokens + share
    close(BatchBoundaryReason.LAST_ITEMS)

    total = max(1, len(planned))
    by_ref = {item.ref: item.tokens for item in items}
    assignments: List[BatchAssignment] = []
    batches: List[SizedBatch] = []
    trimmed = 0
    for index, (batch_items, reason) in enumerate(planned, 1):
        refs = [i.ref for i in batch_items]
        oversized = reason is BatchBoundaryReason.OVERSIZED_ITEM
        primary_tokens = fixed_tokens + sum(i.tokens for i in batch_items)
        reservation = completion.for_batch(len(batch_items))

        # CONTEXT IS PART OF THE REQUEST AND IS SIZED AS SUCH. It was not, at first, and the
        # under-count was the shape of the very failure this module exists to prevent: a hub item
        # with many neighbours would plan as if its neighbours cost nothing and send a request
        # larger than the allowance. Context is trimmed rather than the primaries, because it is
        # enrichment — the batch still answers for everything it is primary for, and what a trim
        # costs is cross-batch visibility, which the reconciliation covers and REPORTS.
        context: List[str] = []
        spare = allowance.usable_tokens - primary_tokens - reservation
        dropped = 0
        for ref in (list(context_refs_for(refs)) if context_refs_for is not None else []):
            if ref in set(refs):
                continue
            cost = by_ref.get(ref, 0)
            if cost > spare:
                dropped += 1
                continue
            context.append(ref)
            spare -= cost
        trimmed += dropped

        assignment = BatchAssignment(
            batch_id=ids.batch_id(inquiry_id, pass_name, refs), index=index, total=total,
            primary_refs=refs, context_refs=context,
            estimated_prompt_tokens=primary_tokens + sum(by_ref.get(c, 0) for c in context),
            requested_completion_tokens=reservation,
            allowance_tokens=allowance.tokens, boundary_reason=reason, sendable=not oversized,
            note=("one item alone estimates at more tokens than a whole request may carry "
                  f"({batch_items[0].tokens} + {share} of answer > {room} of room). It was NOT "
                  f"sent: a provider would refuse it as too large at any moment, and discovering "
                  f"that costs the allowance a round trip to learn what this arithmetic already "
                  f"knew." if oversized else
                  f"{dropped} neighbour(s) did not fit as context and were left out of this "
                  f"request. They are answered for in their own batch; what is lost here is one "
                  f"batch's view of them." if dropped else ""))
        assignments.append(assignment)
        batches.append(SizedBatch(assignment=assignment, items=tuple(batch_items)))

    notes = [f"sized against a {allowance.tokens}-token allowance, holding back "
             f"{allowance.margin_tokens} as margin and reserving {completion.reserved_tokens} plus "
             f"{share} per item for the answer (ceiling {completion.maximum_tokens}); "
             f"{room} token(s) of room per request for {len(items)} item(s)"]
    if note:
        notes.append(note)
    if trimmed:
        notes.append(f"{trimmed} neighbour reference(s) did not fit as context in the batch that "
                     f"would have shown them. Every one is still primary in its own batch; the "
                     f"cross-batch pass is where what was lost between them is looked for.")
    if room <= 0:
        notes.append("the fixed part of this prompt and its completion reservation already exceed "
                     "the allowance, so no item fits in any request. Nothing was sent.")

    record = BatchPlanRecord(
        plan_version=BATCH_PLAN_VERSION,
        plan_id=ids.plan_id(inquiry_id, pass_name, [a.batch_id for a in assignments]),
        pass_name=pass_name, unit=unit, total_items=len(items), batches=assignments, notes=notes)
    return BatchPlan(record=record, batches=tuple(batches), room_tokens=room)


def unexamined_matrix(batch_ids: Sequence[str], reason: str) -> List[ComparisonPair]:
    """Every pair of batches, all of them unexamined. The matrix before any round has run.

    Built up front rather than accumulated, so a pair that was never scheduled and a pair that was
    scheduled and skipped are both PRESENT and differ only in their reason — the alternative, adding
    rows as rounds complete, makes an unexamined pair indistinguishable from one nobody thought of.
    """
    out: List[ComparisonPair] = []
    for left in range(len(batch_ids)):
        for right in range(left + 1, len(batch_ids)):
            out.append(ComparisonPair(left_batch_id=batch_ids[left], right_batch_id=batch_ids[right],
                                      examined=False, reason=reason))
    return out


def schedule_rounds(groups: Sequence[str], *, capacity: int) -> List[List[str]]:
    """Which groups to put in front of the model together, so every PAIR co-occurs at least once.

    A covering schedule rather than one request per pair. `capacity` is how many groups fit in one
    reconciliation request; with a capacity of four and six groups, `C(6,2) = 15` pairs are covered
    by far fewer than fifteen rounds because each round of four covers six of them at once.

    Deterministic and greedy: take the first uncovered pair, seed a round with it, then admit
    whichever remaining group would cover the MOST still-uncovered pairs, ties broken by index. Each
    round therefore carries as much new comparison as its capacity allows, which matters because
    every round is a whole request against a per-minute allowance — a schedule that filled rounds in
    index order covers the same pairs and pays for roughly twice as many of them.

    It terminates because each round covers at least the pair that seeded it.

    NOT CAPPED HERE. A schedule that quietly stopped at N rounds would report `completed` over a
    comparison nobody made, which is the exact shape §3 forbids. Bounding the work is the caller's
    job and it is done by REPORTING the unexamined pairs, not by shortening this list.
    """
    unique = list(dict.fromkeys(groups))
    if len(unique) < 2:
        return []
    room = max(2, int(capacity))
    if len(unique) <= room:
        return [list(unique)]

    rank = {name: i for i, name in enumerate(unique)}

    def key(a: str, b: str) -> Tuple[str, str]:
        return (a, b) if rank[a] < rank[b] else (b, a)

    covered: set = set()
    rounds: List[List[str]] = []
    for left in range(len(unique)):
        for right in range(left + 1, len(unique)):
            if key(unique[left], unique[right]) in covered:
                continue
            members = [unique[left], unique[right]]
            while len(members) < room:
                best, best_gain = None, 0
                for other in unique:
                    if other in members:
                        continue
                    gain = sum(1 for m in members if key(other, m) not in covered)
                    if gain > best_gain:
                        best, best_gain = other, gain
                if best is None:
                    break
                members.append(best)
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    covered.add(key(members[i], members[j]))
            rounds.append(members)
    return rounds


__all__ = ["PRODUCER", "DEFAULT_ALLOWANCE_TOKENS", "DEFAULT_SAFETY_MARGIN_TOKENS",
           "CHARS_PER_TOKEN_FLOOR", "PER_MESSAGE_OVERHEAD_TOKENS", "REQUEST_ENVELOPE_TOKENS",
           "ALLOWANCE_ENV", "MARGIN_ENV", "estimate_tokens", "estimate_request_tokens",
           "Allowance", "CompletionPolicy", "configured_allowance", "SizedItem", "SizedBatch",
           "BatchPlan", "plan", "unexamined_matrix", "schedule_rounds"]
