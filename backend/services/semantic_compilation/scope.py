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

No prompt, no model call, no threshold. `select_units` is a pure function of the units, their
metadata and one declared number — which is what makes a scoped run replayable, and what makes "the
same input selects the same ids" a test rather than an assurance.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (SCOPE_DEFERRED_REASON, ExecutionScope,
                                                  ScopeExclusion, SourceUnit, SourceUnitKind)

from . import sizing

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


# ── the selector ─────────────────────────────────────────────────────────────

#: A reading block that named no image. Its own group rather than folded into the first picture's,
#: because a block nobody attributed is not evidence about that picture and giving it that picture's
#: turn in the rotation would spend one image's share on material from none.
UNATTRIBUTED_GROUP = ""


def group_of(unit: SourceUnit) -> str:
    """Which rotation this unit takes its turn in. STRUCTURE ONLY — authorship and image ref.

    A prompt clause belongs to the QUESTION rather than to any one picture, so it gets its own key.
    Folding the person's own words into the first image's group would let the round-robin spend
    their share as if it were that picture's, and the person's clauses are the one thing §3 says to
    retain first.
    """
    if unit.kind is SourceUnitKind.PROMPT_CLAUSE:
        return PROMPT_GROUP
    return str(unit.image_refs[0]) if unit.image_refs else UNATTRIBUTED_GROUP


def projected_tokens(unit: SourceUnit, expansion: float = ATOM_EXPANSION) -> int:
    """What this unit's ATOMS are expected to cost in one relation request.

    Not what the unit costs. The architect batches atoms, the atoms do not exist yet, and sizing the
    prose instead of the atoms would plan a request a third the size of the one that gets sent. See
    `ATOM_EXPANSION`: declared, conservative in the direction that costs a unit rather than a 413,
    and checked against the real atoms afterwards.
    """
    return max(1, int(sizing.estimate_tokens(unit.exact_quote) * max(1.0, float(expansion))))


@dataclass(frozen=True)
class UnitSelection:
    """What the scope chose, what it left, and the arithmetic that decided.

    `deferred` holds the SourceUnits themselves rather than their ids, because the caller has to
    dispose of each one in the coverage ledger and a list of ids would make it look them back up in
    the object it just handed in.
    """
    selected: Tuple[SourceUnit, ...] = ()
    deferred: Tuple[SourceUnit, ...] = ()
    exclusions: Tuple[ScopeExclusion, ...] = ()
    room_tokens: int = 0
    projected_tokens: int = 0
    notes: Tuple[str, ...] = ()

    @property
    def group_count(self) -> int:
        return len({group_of(u) for u in self.selected})


def select_units(units: Sequence[SourceUnit], *, room_tokens: int,
                 expansion: float = ATOM_EXPANSION) -> UnitSelection:
    """The declared subset, chosen deterministically and without reading a single word for meaning.

    The priority order is §3's, and each step is here for a reason the live runs paid for:

      1. **Every prompt clause that fits, first.** The person's own words are the one thing in the
         ledger nothing else can supply. 003D and 003E both report four user units surviving into
         the ledger and attributed to the person; a scope that spent its room on the reading and
         deferred the question would be a rehearsal of the model talking to itself.

      2. **Then a ROUND-ROBIN over images, one unit at a time.** Not the ledger in order: the ledger
         is the prompt followed by image 1's blocks, then image 2's, and a budget filled in that
         order is a budget spent entirely on the first picture. Every relation this council exists
         to find is a comparison, and a comparison needs two pictures in the same request.

      3. **Whole units or nothing.** A unit that does not fit is DEFERRED, never cut down. Half a
         source unit is a sentence the person did not write and the model did not produce, and the
         coverage ledger has no word for it.

    Deterministic: no clock, no randomness, no counter. The result is a function of the units' ids,
    texts, kinds and image refs and of one declared number — so the same input selects the same ids,
    which is what makes a scoped run replayable rather than merely repeatable.
    """
    room = max(0, int(room_tokens))
    costs: Dict[str, int] = {u.source_unit_id: projected_tokens(u, expansion) for u in units}

    groups: List[str] = []
    queues: Dict[str, List[SourceUnit]] = {}
    for unit in units:
        key = group_of(unit)
        if key not in queues:
            queues[key] = []
            groups.append(key)
        queues[key].append(unit)

    taken: List[SourceUnit] = []
    spent = 0

    def fits(unit: SourceUnit) -> bool:
        return spent + costs[unit.source_unit_id] <= room

    # ── 1. the person's own words ──
    for unit in queues.get(PROMPT_GROUP, []):
        if fits(unit):
            taken.append(unit)
            spent += costs[unit.source_unit_id]

    # ── 2. the rotation, over everything else ──
    rotation = [g for g in groups if g != PROMPT_GROUP]
    remaining = {g: list(queues[g]) for g in rotation}
    chosen = {u.source_unit_id for u in taken}
    moved = True
    while moved:
        moved = False
        for key in rotation:
            queue = remaining[key]
            # THE FIRST ONE THAT FITS, scanning forward rather than stopping at the head. A long
            # opening block would otherwise close its whole image out of the rotation, and losing a
            # picture entirely is the failure this step exists to prevent.
            for index, unit in enumerate(queue):
                if fits(unit):
                    taken.append(unit)
                    chosen.add(unit.source_unit_id)
                    spent += costs[unit.source_unit_id]
                    queue.pop(index)
                    moved = True
                    break

    # ── 3. what was left, named individually ──
    order = {u.source_unit_id: i for i, u in enumerate(units)}
    selected = tuple(sorted(taken, key=lambda u: order[u.source_unit_id]))
    deferred = tuple(u for u in units if u.source_unit_id not in chosen)
    exclusions = tuple(ScopeExclusion(
        ref=u.source_unit_id, kind="source_unit",
        reason=f"{SCOPE_DEFERRED_REASON}. Its atoms are projected at "
               f"{costs[u.source_unit_id]} token(s) and {max(0, room - spent)} of the "
               f"{room}-token relation request remained when it was reached.") for u in deferred)

    notes = [
        f"the vertical-slice scope selected {len(selected)} of {len(units)} source unit(s) — "
        f"{sum(1 for u in selected if u.kind is SourceUnitKind.PROMPT_CLAUSE)} of "
        f"{sum(1 for u in units if u.kind is SourceUnitKind.PROMPT_CLAUSE)} from the person — "
        f"across {len({group_of(u) for u in selected if group_of(u) != PROMPT_GROUP})} of "
        f"{len([g for g in groups if g != PROMPT_GROUP])} image group(s), projecting {spent} of "
        f"{room} token(s) of room in one relation request at a declared {expansion}x expansion from "
        f"prose to atoms.",
        "every deferred unit is still in the ledger with its own id and is disposed `refused` with "
        "the scope's reason. It is not `semantic_remainder`: remainder is content nothing measures, "
        "and this is content nothing was asked about.",
    ]
    if not selected:
        notes.append(
            f"nothing fitted. The smallest source unit projects at "
            f"{min(costs.values()) if costs else 0} token(s) against {room} of room, so the scope "
            f"selected no material and the run stops here rather than sending an empty request.")
    return UnitSelection(selected=selected, deferred=deferred, exclusions=exclusions,
                         room_tokens=room, projected_tokens=spent, notes=tuple(notes))


__all__ = ["PRODUCER", "ENABLED_ENV", "MAX_RELATION_BATCHES_ENV",
           "MAX_OPERATIONALIZER_BATCHES_ENV", "MAX_RECONCILIATION_ROUNDS_ENV",
           "DEFAULT_MAX_RELATION_BATCHES", "DEFAULT_MAX_OPERATIONALIZER_BATCHES",
           "DEFAULT_MAX_RECONCILIATION_ROUNDS", "ATOM_EXPANSION", "PROMPT_GROUP",
           "UNATTRIBUTED_GROUP", "ExecutionScope", "ScopeRefused", "feature_enabled", "parse",
           "ScopeLimits", "UNBOUNDED", "configured_limits", "group_of", "projected_tokens",
           "UnitSelection", "select_units"]
