"""
HARNESS-003D — the adapter that makes the merged dissolution council reachable from `/inquiry`.

003A built the council and 003B built the checkpointed driver, and neither could reach the other:
`runtime.build_stages` still bound `ModelSemanticCompiler`, the one-call compiler 002R's rehearsal
failed on. This is the seam between them, and it is an ADAPTER rather than a change to either lane.

## Why an adapter rather than a new stage

The coordinator drives a `SemanticCompiler`: one object, one `compile(request) -> graph`. The
council is a pipeline of three roles behind a function. Teaching the coordinator about passes would
put the council's shape into the stage order, and the stage order is Lane B's; teaching the council
to be a stage would put the driver's shape into the compiler, which is Lane A's. So the shapes meet
here, in the lane whose job is exactly that.

## What it has to carry across

The coordinator reads three things off a compilation that a v2 graph does not present the same way:

  · `graph.provenance.compiler` — a single `ModelReceipt`. v2 leaves it `None` on purpose, because
    naming one of three minds as the author of all of it would be a lie. The adapter exposes the
    council's own per-pass receipts instead, and the stage projection reads those.
  · truncation — 003B's `detect_truncation` consults a receipt field, then a PRODUCER ATTRIBUTE,
    then a note. With no single receipt the producer route is the one that can answer, so this
    object declares `last_finish_reason` and `truncated_calls` computed from the pass receipts.
    Those are the exact attribute names 003B reads; nothing in that lane changes.
  · adequacy — the coverage ledger is already on the graph and `declared_adequacy` already reads it.

## What it must not do

It must not improve the council, re-run a pass, or repair a graph. If the dissolution reports
`coverage_failed`, this returns a graph that says `coverage_failed`. Integration is where an
underperformance becomes VISIBLE, not where it gets tidied.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from backend.schemas.semantic_compilation import PassOutcome, PassReceipt, SemanticInquiryGraph
from backend.services.semantic_compilation.base import CompilationRequest
from backend.services.semantic_compilation.dissolution import Council, dissolve, live_council

PRODUCER = "inquiry_session/dissolution-binding-v1"

#: The finish reason that means a pass stopped on its budget. Spelled here as well as in 003B
#: because this module computes the producer-attribute signals that lane reads, and importing its
#: private constant would couple the adapter to the reader it is feeding.
TRUNCATED_FINISH_REASON = "length"


class DissolutionCompiler:
    """The v2 council, wearing the one-call compiler seam the coordinator drives.

    `name` is `council` rather than `model`: the stage ledger records it, and a reader who sees
    `model` for a five-pass pipeline would be told the wrong thing about what produced the graph.
    """

    name = "council"

    def __init__(self, council: Optional[Council] = None):
        self._council = council
        #: 003B's producer-attribute route reads these two by name. They are properties of the last
        #: compilation rather than of the object, and they are reset per call so a second inquiry
        #: on a reused adapter cannot inherit the first one's truncation.
        self.last_finish_reason: str = ""
        self.truncated_calls: int = 0
        self.last_passes: tuple = ()
        self.calls: int = 0

    # ── the seam ──

    def compile(self, request: CompilationRequest) -> SemanticInquiryGraph:
        self.last_finish_reason = ""
        self.truncated_calls = 0
        self.last_passes = ()
        self.calls += 1

        graph = dissolve(request, self._council if self._council is not None else live_council())

        self.last_passes = tuple(graph.passes)
        self.truncated_calls = sum(
            sum(1 for f in p.finish_reasons if f == TRUNCATED_FINISH_REASON) for p in graph.passes)
        # THE LAST REASON ANY PASS REPORTED, and `length` wins over a later `stop`. A sweep whose
        # third batch was cut off and whose fourth finished cleanly is a truncated sweep, and a
        # strictly-last reading of it would report the clean one and lose the fact.
        reasons = [f for p in graph.passes for f in p.finish_reasons if f]
        if TRUNCATED_FINISH_REASON in reasons:
            self.last_finish_reason = TRUNCATED_FINISH_REASON
        elif reasons:
            self.last_finish_reason = reasons[-1]
        return graph

    # ── what the stage projection reads ──

    @property
    def model(self) -> Optional[str]:
        """The model behind the passes that actually called one, when they agree.

        `None` when they disagree, because a single model field over a council that used two of them
        would name one and hide the other. The per-pass receipts carry the full answer.
        """
        models = {p.model for p in self.last_passes if p.model}
        return next(iter(models)) if len(models) == 1 else None

    @property
    def provider(self) -> Optional[str]:
        providers = {p.provider for p in self.last_passes if p.provider}
        return next(iter(providers)) if len(providers) == 1 else None

    @property
    def actual_calls(self) -> int:
        """Requests this council made. The deterministic passes contribute zero, which is correct:
        the ledger and the audit are transforms, and counting them as calls would inflate the number
        a reader uses to judge cost."""
        return sum(p.call_count for p in self.last_passes)

    @property
    def worst_outcome(self) -> Optional[PassOutcome]:
        """The first cause among the passes, in the order `audit.overall` established.

        Reused rather than re-derived — a second opinion about which failure explains the others is
        exactly the drift this lane exists to avoid.
        """
        for outcome in (PassOutcome.UNAVAILABLE, PassOutcome.ERROR, PassOutcome.TRUNCATED,
                        PassOutcome.COVERAGE_FAILED, PassOutcome.THIN, PassOutcome.EMPTY):
            if any(p.outcome is outcome for p in self.last_passes):
                return outcome
        return PassOutcome.COMPLETED if self.last_passes else None

    def is_available(self) -> bool:
        """Whether any mind in the council can be reached. A council with no provider still runs —
        the ledger and the audit are deterministic — and produces a graph that says so."""
        council = self._council if self._council is not None else live_council()
        return any(getattr(p, "is_available", lambda: False)()
                   for p in (council.dissector, council.architect, council.operationalizer)
                   if p is not None)


__all__ = ["PRODUCER", "TRUNCATED_FINISH_REASON", "DissolutionCompiler"]
