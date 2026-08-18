"""
HARNESS-003F — the declared, temporary execution scope: what a run was ALLOWED to investigate.

    a requested mode          -> refused visibly, or a scope with its own version and purpose
    the whole source ledger   -> a deterministic, topic-independent selection that FITS
    the passes that cost most -> a declared batch bound, and every item it skipped named

## Why this exists at all, and why it is temporary

003D could not send the relation architect's request. 003E made every request sendable and the fold
rehearsal produced the first live claims this chain has ever made — and then spent 91.5% of its
running time waiting, and the operationalizer's eight requests were all refused for capacity. So the
vertical has never once run end to end on live models: no observable, no fork, no answer.

That is an ALLOWANCE problem and the honest repair is a tier change, which 003E says in its own
words. This module is the other road: run the whole chain over a declared subset, so the chain
itself can be tested while the allowance is what it is. It buys a different thing from a tier change
and it must never be mistaken for one — which is what `full_coverage: false`, the named exclusions
and the badge on every terminal state are all for.

## The three rules this module is written against

**A scope is DECLARED or it does not exist.** Two gates, and both must open: the request asks for
`vertical_slice`, and the deployment sets `SEMANT_INQUIRY_SCOPED_REHEARSAL_ENABLED=1`. A request
that asks while the feature is off is REFUSED, visibly, with the reason. It is never quietly served
as `full` — a person who asked for a bounded run and got a full one would draw conclusions about
the wrong thing — and it is never quietly accepted either.

**The selection may not know what the inquiry is about.** No word, no topic, no vocabulary. The
selector reads structure — who authored a unit, which image it came from, and what it costs in
tokens — and nothing else. A selector that behaved differently on one subject from on another would
make every scoped result a fact about the selector's opinions rather than about the images, and the
tree already has a test that scans this file for the rehearsal's own nouns.

**Nothing is deleted and nothing is trimmed.** A deferred source unit stays in the ledger, keeps its
id, and is disposed `refused` with the scope's own sentence. It is not `semantic_remainder`:
remainder is content nothing MEASURES, and this is content nothing was ASKED about.

## What is NOT here

No prompt, no model call, no threshold. The selector that lands next to this gate is a pure
function of the units, their metadata and a declared allowance — which is what makes a scoped run
replayable, and what makes "the same input selects the same ids" a test rather than an assurance.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from backend.schemas.semantic_compilation import ExecutionScope

PRODUCER = "semantic_compilation/scope-v1"

#: The deployment gate. Off unless a deployment says otherwise, and the string comparison is
#: deliberately narrow: this is a temporary contract and a box that half-set an environment variable
#: should get the safe answer.
ENABLED_ENV = "SEMANT_INQUIRY_SCOPED_REHEARSAL_ENABLED"

#: The three bounds, applied ONLY in `vertical_slice`. Outside it every one of them is `None`, which
#: is unlimited and is the behaviour every merged lane already has.
MAX_RELATION_BATCHES_ENV = "SEMANT_INQUIRY_SLICE_MAX_RELATION_BATCHES"
MAX_OPERATIONALIZER_BATCHES_ENV = "SEMANT_INQUIRY_SLICE_MAX_OPERATIONALIZER_BATCHES"
MAX_RECONCILIATION_ROUNDS_ENV = "SEMANT_INQUIRY_SLICE_MAX_RECONCILIATION_ROUNDS"

DEFAULT_MAX_RELATION_BATCHES = 1
DEFAULT_MAX_OPERATIONALIZER_BATCHES = 2
DEFAULT_MAX_RECONCILIATION_ROUNDS = 0

#: What a source unit's atoms are expected to cost, as a multiple of the unit's own prose.
#:
#: THE SELECTOR HAS TO SIZE SOMETHING IT CANNOT SEE. It chooses source units; the relation architect
#: batches ATOMS, which do not exist until the dissector has run. So the bound is declared, in the
#: same direction and for the same reason `sizing.CHARS_PER_TOKEN_FLOOR` is: over-estimating costs a
#: unit that would have fitted, under-estimating costs the very thing this module exists to avoid.
#:
#: Two-to-one is measured rather than guessed. An atom carries its own text (a fragment of the unit),
#: its ids, its subject/predicate/object and its JSON scaffolding, and the dissector emits several
#: per unit — 003E's fold run dissolved 35 units into 188 atoms. The JSON digest the architect sends
#: is what is being sized, not the atom object.
#:
#: AND IT IS CHECKED RATHER THAN ASSERTED: `dissolution` compares the projection against the real
#: atom cost after dissection and records an under-estimate on the record by name.
ATOM_EXPANSION = 2.0

#: The sentinel affinity for the person's own clauses. Not an image and not a block — a prompt
#: clause belongs to the question rather than to any one picture, and grouping it under the first
#: image would let the round-robin spend the person's own words as if they were one image's share.
PROMPT_GROUP = "prompt"


class ScopeRefused(Exception):
    """A scope was asked for that this deployment will not serve.

    An exception rather than a fallback, because the two quiet answers are both wrong: serving
    `full` silently tells a person their bounded run was bounded when it was not, and accepting
    `vertical_slice` silently on a deployment that never declared it turns a temporary contract into
    an ambient one.
    """

    def __init__(self, code: str, detail: str, *, requested: str = ""):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.requested = requested


def _flag(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return max(0, int(float(raw)))
    except ValueError:
        return default


def feature_enabled() -> bool:
    """Whether this deployment will serve a scoped run at all. Off by default, always."""
    return _flag(ENABLED_ENV)


def parse(requested: object, *, enabled: Optional[bool] = None) -> ExecutionScope:
    """A requested scope → the scope this run will use, or `ScopeRefused`.

    THE ONLY TWO OUTCOMES ARE THE ONE THAT WAS ASKED FOR AND A REFUSAL. There is no third branch
    where a request is honoured approximately.
    """
    raw = str(requested or ExecutionScope.FULL.value).strip().lower()
    if not raw:
        return ExecutionScope.FULL
    try:
        mode = ExecutionScope(raw)
    except ValueError:
        raise ScopeRefused(
            "unknown_execution_scope",
            f"execution_scope must be one of {[s.value for s in ExecutionScope]}, got {raw!r}. It "
            f"was not run as `full` instead: a scope nobody recognises is not a scope anybody can "
            f"read the result against.", requested=raw) from None
    if mode is ExecutionScope.VERTICAL_SLICE:
        allowed = feature_enabled() if enabled is None else bool(enabled)
        if not allowed:
            raise ScopeRefused(
                "scoped_rehearsal_disabled",
                f"this deployment does not serve the temporary vertical-slice rehearsal scope. Set "
                f"{ENABLED_ENV}=1 to enable it. Nothing was run: falling back to a full-coverage "
                f"reading would answer a different question from the one that was asked, and "
                f"accepting the scope without the deployment declaring it would make a temporary "
                f"contract permanent by accident.", requested=raw)
    return mode


@dataclass(frozen=True)
class ScopeLimits:
    """What a scoped run may spend on the two passes that cost most. `None` is unlimited.

    `None` rather than a large number, and `0` is a real value distinct from it: this lane's
    declared configuration sets the reconciliation to ZERO permitted rounds, and a representation
    where unlimited and none were both falsy would collapse them.
    """
    relation_batches: Optional[int] = None
    operationalizer_batches: Optional[int] = None
    reconciliation_rounds: Optional[int] = None

    @property
    def bounded(self) -> bool:
        return any(v is not None for v in
                   (self.relation_batches, self.operationalizer_batches,
                    self.reconciliation_rounds))


#: Full coverage, and it is the ABSENCE of every bound rather than a large one. A reader of
#: `relation_batches_allowed: null` on a record knows nothing was capped; a reader of `999` has to
#: guess whether that was a bound nobody reached.
UNBOUNDED = ScopeLimits()


def configured_limits(mode: ExecutionScope) -> ScopeLimits:
    """The bounds for this mode. Outside `vertical_slice` there are none, ever.

    Read from the environment per call rather than cached, for the same reason
    `sizing.configured_allowance` is: a rehearsal declares its own numbers on the command line and a
    module-level constant would make that a restart.
    """
    if mode is not ExecutionScope.VERTICAL_SLICE:
        return UNBOUNDED
    return ScopeLimits(
        relation_batches=_env_int(MAX_RELATION_BATCHES_ENV, DEFAULT_MAX_RELATION_BATCHES),
        operationalizer_batches=_env_int(MAX_OPERATIONALIZER_BATCHES_ENV,
                                         DEFAULT_MAX_OPERATIONALIZER_BATCHES),
        reconciliation_rounds=_env_int(MAX_RECONCILIATION_ROUNDS_ENV,
                                       DEFAULT_MAX_RECONCILIATION_ROUNDS),
    )


__all__ = ["PRODUCER", "ENABLED_ENV", "MAX_RELATION_BATCHES_ENV",
           "MAX_OPERATIONALIZER_BATCHES_ENV", "MAX_RECONCILIATION_ROUNDS_ENV",
           "DEFAULT_MAX_RELATION_BATCHES", "DEFAULT_MAX_OPERATIONALIZER_BATCHES",
           "DEFAULT_MAX_RECONCILIATION_ROUNDS", "ATOM_EXPANSION", "PROMPT_GROUP",
           "ExecutionScope", "ScopeRefused", "feature_enabled", "parse", "ScopeLimits",
           "UNBOUNDED", "configured_limits"]
