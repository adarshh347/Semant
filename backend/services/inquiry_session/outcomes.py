"""
HARNESS-003B — telling a short answer from a cut-off one, and a parse from an adequacy.

## The failure this module exists for

002R's rehearsal produced a barren graph from an abundant reading, and the session reported it as
an honest empty result. Provenance was correct about every fact it held. It was still the wrong
report, because two very different things had happened and only one of them was the person's
problem:

    the compiler decomposed the prompt into few claims       → the prompt is what it is
    the compiler ran out of output budget mid-sentence       → give it room, or split the call

A model that stops on `length` and happens to close its JSON returns a graph that is
indistinguishable from an honest short one. `finish_reason` is the only thing that tells them
apart, and a chain that does not read it will report the second as the first every time — with a
receipt, a hash and a provenance block that are all accurate.

## Read the producer's own signal; never its prose

Three routes are consulted, in order, and WHICH ONE ANSWERED IS RECORDED. They are not equally
trustworthy and a reader is entitled to know which was used:

    field                a typed field on the receipt. Cannot be mistaken. Does not exist yet —
                         see the tree contradiction in the finding — so this route is written for
                         the Lane A change that should add it.
    producer_attribute   the producer object declares it (`last_finish_reason`, `truncated_calls`).
                         A declared attribute, read directly. Not prose.
    receipt_note         an exact, ANCHORED `finish_reason: <value>` note the producer emits
                         itself. Machine-written, and matched with `startswith` on the whole note
                         rather than `in` on the blob.

`unknown` is returned when none of the three could be consulted, and `unknown` is NOT `none`.
`none` says a route answered and reported no truncation; `unknown` says nothing could be asked. A
product rendering them alike would show an unchecked stage as a verified one — the shape this
repository has paid for repeatedly: *a check whose evidence is the availability of a signal rather
than the content of one.*

## Why prose is not scanned

The theorist writes `"N call(s) stopped on the output budget rather than finishing…"`. Matching that
sentence would work today and would break the first time somebody improves the wording, silently,
in the direction of reporting every truncated reading as complete. That is HARNESS-001B2's defect
exactly — a kind re-derived from wording instead of read — and it is refused here by construction:
the note route matches only the machine-emitted `finish_reason: ` prefix, which is a field that
happens to be spelled as a string.

## Thin is the compiler's own verdict, not ours

`thin` means the producer's DECLARED coverage or adequacy check failed. This lane does not invent
an adequacy rule — "few claims for a long reading" is exactly the inference 002R shows to be
ambiguous. Until a producer declares coverage, `thin` is simply never returned, and the absence is
visible rather than papered over with a heuristic that would be right often enough to be trusted.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from backend.schemas.inquiry_stage import StageAttemptOutcome, TruncationSource

#: The exact prefix a producer uses when it writes its finish reason into a note. Anchored: matched
#: against the START of a whole note, never searched for inside a blob of concatenated ones.
FINISH_REASON_PREFIX = "finish_reason:"

#: The value that means "stopped on the output budget". One string, from the OpenAI-shaped API both
#: producers speak.
TRUNCATED_FINISH_REASON = "length"

#: Attributes a producer may declare to report its own truncation. Read directly off the object.
_PRODUCER_LAST_REASON = "last_finish_reason"
_PRODUCER_TRUNCATED_CALLS = "truncated_calls"

#: Keys a receipt may one day carry as a typed field. Checked first, so the day Lane A adds one the
#: better route is used with no edit here.
_RECEIPT_FIELDS = ("finish_reason", "last_finish_reason")


@dataclass(frozen=True)
class Truncation:
    """Whether a producer stopped on its budget, and which route said so."""
    truncated: Optional[bool]
    source: TruncationSource
    detail: str = ""

    @property
    def known(self) -> bool:
        return self.truncated is not None


UNKNOWN = Truncation(truncated=None, source=TruncationSource.UNKNOWN,
                     detail="no declared truncation signal was available on this producer or its "
                            "receipt, so nothing is claimed either way")


def _notes_of(receipt: Any) -> Sequence[str]:
    notes = getattr(receipt, "notes", None)
    if notes is None and isinstance(receipt, Mapping):
        notes = receipt.get("notes")
    return [str(n) for n in (notes or ())]


def _disposition_of(entry: Any) -> str:
    """One coverage entry's disposition, whether it arrived as a mapping or as a typed object.

    An enum member is unwrapped to its value: `DispositionKind.REFUSED` compared against the string
    `"refused"` is False, and a comparison that is always False is a check that never fires.
    """
    raw = entry.get("disposition") if isinstance(entry, Mapping) \
        else getattr(entry, "disposition", None)
    return str(getattr(raw, "value", raw) or "")


def _field_of(receipt: Any, name: str) -> Optional[str]:
    if receipt is None:
        return None
    if isinstance(receipt, Mapping):
        value = receipt.get(name)
    else:
        value = getattr(receipt, name, None)
    return None if value is None else str(value)


def detect_truncation(receipt: Any = None, *, producer: Any = None) -> Truncation:
    """Was this producer cut off? Three declared routes, in order, and the route is recorded."""
    for name in _RECEIPT_FIELDS:
        value = _field_of(receipt, name)
        if value is not None and str(value).strip():
            hit = str(value).strip().lower() == TRUNCATED_FINISH_REASON
            return Truncation(truncated=hit, source=TruncationSource.FIELD,
                              detail=f"receipt.{name} = {value!r}")

    if producer is not None:
        reason = getattr(producer, _PRODUCER_LAST_REASON, None)
        calls = getattr(producer, _PRODUCER_TRUNCATED_CALLS, None)
        if isinstance(calls, int) and calls > 0:
            return Truncation(truncated=True, source=TruncationSource.PRODUCER_ATTRIBUTE,
                              detail=f"{calls} call(s) stopped on the output budget")
        if reason is not None and str(reason).strip():
            hit = str(reason).strip().lower() == TRUNCATED_FINISH_REASON
            return Truncation(truncated=hit, source=TruncationSource.PRODUCER_ATTRIBUTE,
                              detail=f"producer.{_PRODUCER_LAST_REASON} = {reason!r}")
        if isinstance(calls, int):
            # The producer declares the counter and it is zero: a route ANSWERED, and it said no.
            return Truncation(truncated=False, source=TruncationSource.PRODUCER_ATTRIBUTE,
                              detail="the producer reports no call stopped on its output budget")

    for note in _notes_of(receipt):
        text = note.strip()
        if not text.lower().startswith(FINISH_REASON_PREFIX):
            continue
        value = text[len(FINISH_REASON_PREFIX):].strip().strip(".").lower()
        if not value or value == "not reported":
            return Truncation(truncated=None, source=TruncationSource.UNKNOWN,
                              detail="the producer emitted a finish_reason note and did not report "
                                     "a value")
        return Truncation(truncated=value == TRUNCATED_FINISH_REASON,
                          source=TruncationSource.RECEIPT_NOTE,
                          detail=f"{FINISH_REASON_PREFIX} {value}")

    return UNKNOWN


# ── declared adequacy ────────────────────────────────────────────────────────

#: Where a producer may declare that its own coverage check failed. Read as DATA off the artifact;
#: nothing here computes an adequacy rule of its own.
_COVERAGE_KEYS = ("coverage", "coverage_report")
_COMPLETE_KEYS = ("complete", "coverage_complete", "is_complete")


@dataclass(frozen=True)
class Adequacy:
    """A producer's own verdict on whether it covered what it was given."""
    complete: Optional[bool]
    detail: str = ""
    uncovered: int = 0

    @property
    def declared(self) -> bool:
        return self.complete is not None


UNDECLARED = Adequacy(complete=None,
                      detail="this producer declares no coverage check, so a short result is not "
                             "distinguishable from an inadequate one and nothing is claimed")


def declared_adequacy(artifact: Any) -> Adequacy:
    """Read a producer's DECLARED coverage verdict, or return undeclared.

    No inference. "Few claims for a long reading" is precisely the ambiguity 002R demonstrated, and
    a heuristic here would be right often enough that nobody would check it on the run where it was
    wrong. When Lane A's dissolution contract lands, its coverage ledger is what this reads.
    """
    if artifact is None:
        return UNDECLARED
    for key in _COVERAGE_KEYS:
        block = artifact.get(key) if isinstance(artifact, Mapping) else getattr(artifact, key, None)
        if block is None:
            continue
        if isinstance(block, Mapping):
            for flag in _COMPLETE_KEYS:
                if flag in block:
                    complete = bool(block.get(flag))
                    uncovered = int(block.get("uncovered") or block.get("uncovered_count") or 0)
                    return Adequacy(
                        complete=complete, uncovered=uncovered,
                        detail=(f"the producer's own coverage check reports {'complete' if complete else 'INCOMPLETE'}"
                                + (f"; {uncovered} source unit(s) uncovered" if uncovered else "")))
        if isinstance(block, Sequence) and not isinstance(block, (str, bytes)):
            # A coverage LEDGER: one disposition per source unit. Incomplete when any entry says so.
            #
            # BOTH SHAPES, and the reconciliation is the point. This read `isinstance(entry,
            # Mapping)` and nothing else, so a TYPED v2 graph — a list of `CoverageDisposition`
            # models — matched no entry and reported `complete` for a ledger that might be entirely
            # refusals. Production stores the dumped mapping, so it was never wrong in the running
            # system; it was wrong for anyone who passed the object, which is what an in-process
            # caller naturally holds. Lane A pinned it with a failing-on-fix test rather than
            # editing this file, and this is that fix.
            uncovered = sum(1 for entry in block
                            if _disposition_of(entry) in ("", "semantic_remainder", "refused"))
            return Adequacy(
                complete=uncovered == 0, uncovered=uncovered,
                detail=(f"the producer's coverage ledger disposes of {len(block)} source unit(s); "
                        f"{uncovered} left uncovered"))
    return UNDECLARED


def outcome_for(*, produced: bool, truncation: Truncation, adequacy: Adequacy,
                unavailable: bool = False, refused: bool = False,
                errored: bool = False) -> StageAttemptOutcome:
    """The one place a stage's ending is decided, so seven callers cannot decide it seven ways.

    ORDER IS THE ARGUMENT. Availability first — an instrument that never ran cannot be truncated.
    Then truncation, which OUTRANKS emptiness: a call cut off before it wrote anything is
    `truncated`, not `empty`, because "it found nothing" and "it never finished looking" send a
    reader to opposite places. Then the producer's own adequacy verdict. Only what survives all
    four is `completed`.
    """
    if errored:
        return StageAttemptOutcome.ERROR
    if refused:
        return StageAttemptOutcome.REFUSED
    if unavailable:
        return StageAttemptOutcome.UNAVAILABLE
    if truncation.truncated:
        return StageAttemptOutcome.TRUNCATED
    if adequacy.complete is False:
        return StageAttemptOutcome.THIN
    if not produced:
        return StageAttemptOutcome.EMPTY
    return StageAttemptOutcome.COMPLETED


__all__ = ["FINISH_REASON_PREFIX", "TRUNCATED_FINISH_REASON", "Truncation", "Adequacy",
           "UNKNOWN", "UNDECLARED", "detect_truncation", "declared_adequacy", "outcome_for"]
