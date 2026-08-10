"""
HARNESS-003A — the dissolution pipeline: the council in order, with one repair and one audit.

    source ledger (deterministic)
      -> semantic dissector, batched
      -> deterministic coverage audit
      -> at most ONE targeted repair, carrying only what failed
      -> relation architect
      -> epistemic operationalizer
      -> final audit
      -> a v2 SemanticInquiryGraph

THIS MODULE CONTAINS NO INTELLIGENCE and no prompt. It owns the ORDER, the budget and the assembly,
exactly as `inquiry_session.coordinator` does one layer up — and for the same reason: a stage order
with judgement in it is a stage order that disagrees with its stages.

## Why the audit runs twice

Once after dissection, to decide whether a repair is warranted and what it should carry. Once at
the end, over everything, because the architect and the operationalizer can introduce dangling
references of their own and an audit that ran before they did would report a graph that no longer
exists.

## What happens when a pass is unavailable

The pipeline continues and each later pass reports what it was given. A dissector that did not run
produces no atoms, so the architect reports `empty` rather than `unavailable` — it WAS available and
had nothing to work with, and collapsing those two would hide which mind was missing. The overall
state is decided by `audit.overall`, which orders the explanations so the first cause is the one
reported.

## Narration (HARNESS-003D)

`on_substage` is an optional sink the caller supplies. The council reports which pass it is entering,
which batch it is on, and what each pass came back with — and `passes.ModelPass` reports each
capacity refusal and planned wait through the same sink, as it happens.

It is a SINK rather than a return value because a compilation that only narrates at the end narrates
nothing: the whole reason 002R's rehearsal read as `visibility_failure` is that a person watched a
two-minute wait with no account of it. What arrives here is a callable and a label; nothing about the
inquiry's subject reaches it, and a sink that raises is ignored rather than allowed to fail the pass.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (SCHEMA_VERSION_V2, ClaimEdge, ClaimNode,
                                                  CompilerRefusal, CoverageDisposition,
                                                  DecisionCandidate, DispositionKind,
                                                  DissolutionPass, GraphProvenance, ModelReceipt,
                                                  ObservableSpec, PassOutcome, PassReceipt,
                                                  SemanticAtom, SemanticInquiryGraph,
                                                  SemanticRemainderItem, SourceUnit)

from . import audit as audit_mod
from . import contracts, ids, ledger as ledger_mod
from .architect import RelationArchitect
from .base import CompilationRequest, sha256_of
from .dissector import SemanticDissector
from .operationalizer import EpistemicOperationalizer

PRODUCER = "semantic_compilation/dissolution-v2"


@dataclass(frozen=True)
class Council:
    """The three minds, injected. None of them is constructed here.

    A pass left `None` is not substituted: the pipeline runs without it and every later pass
    reports what it was actually given, which is how a missing mind stays visible.
    """
    dissector: Optional[SemanticDissector] = None
    architect: Optional[RelationArchitect] = None
    operationalizer: Optional[EpistemicOperationalizer] = None
    #: The one repair the audit may ask for. A SEPARATE instance, so its receipt is its own and the
    #: first attempt's accounting is not overwritten by the second's.
    repairer: Optional[SemanticDissector] = None


def live_council() -> Council:
    """The production binding. Three roles, three adapters, one repair adapter."""
    return Council(dissector=SemanticDissector(), architect=RelationArchitect(),
                   operationalizer=EpistemicOperationalizer(), repairer=SemanticDissector())


#: The order a person watches the council in, and the denominator of `pass N of M`. Declared as
#: data rather than counted from the code, so the progress a surface renders is the sequence this
#: module actually runs rather than a number somebody kept in step by hand.
PASS_ORDER: Tuple[DissolutionPass, ...] = (
    DissolutionPass.SOURCE_LEDGER, DissolutionPass.SEMANTIC_DISSECTOR,
    DissolutionPass.TARGETED_REPAIR, DissolutionPass.RELATION_ARCHITECT,
    DissolutionPass.EPISTEMIC_OPERATIONALIZER, DissolutionPass.COVERAGE_AUDIT,
)

#: What each pass is called where a person reads it. The council's names are accurate and the
#: surface has to render something a reader who has not read this file can follow.
PASS_LABEL = {
    DissolutionPass.SOURCE_LEDGER: "splitting the question and the reading into source units",
    DissolutionPass.SEMANTIC_DISSECTOR: "dissolving source units into semantic atoms",
    DissolutionPass.TARGETED_REPAIR: "one targeted repair over the units nothing accounted for",
    DissolutionPass.RELATION_ARCHITECT: "building claims and the relations between them",
    DissolutionPass.EPISTEMIC_OPERATIONALIZER: "deciding what could be observed, and what cannot",
    DissolutionPass.COVERAGE_AUDIT: "auditing what became of every source unit",
}


class _Narrator:
    """The council's account of itself, for whoever is watching. Nobody, usually.

    Every method is a no-op with no sink, so the pipeline below reads the same whether or not
    anything is listening — the alternative, an `if observer is not None` at each of six sites, is
    six places for the narration to fall out of step with the thing it narrates.
    """

    def __init__(self, sink: Optional[Callable[..., None]] = None):
        self._sink = sink
        self.index = 0

    def say(self, label: str, **fields: Any) -> None:
        if self._sink is None:
            return
        try:
            self._sink(label, **fields)
        except Exception:                                        # noqa: BLE001
            pass

    def entering(self, name: DissolutionPass, *, inputs: int, detail: str = "") -> None:
        self.index += 1
        self.say(PASS_LABEL.get(name, name.value), index=self.index, total=len(PASS_ORDER),
                 outcome="started",
                 detail=detail or f"{name.value} · {inputs} input(s)")

    def left(self, receipt: PassReceipt) -> None:
        """What the pass came back with — its own outcome and its own sentence, never a rewrite.

        `outcome` travels as the pass's word for it. A narrator that mapped `coverage_failed` onto
        `completed` because the pipeline carried on would be the exact laundering the coverage
        ledger exists to prevent, one layer out.
        """
        self.say(PASS_LABEL.get(receipt.pass_name, receipt.pass_name.value),
                 index=self.index, total=len(PASS_ORDER), outcome=receipt.outcome.value,
                 detail=f"{receipt.pass_name.value} · {receipt.outcome.value}"
                        + (f" · {receipt.detail}" if receipt.detail else "")
                        + (f" · {receipt.call_count} call(s)" if receipt.call_count else "")
                        + (f" · {receipt.transport_attempts} transport attempt(s)"
                           if receipt.transport_attempts > receipt.call_count else ""))


@contextlib.contextmanager
def _narrating(council: Council, sink: Optional[Callable[..., None]]) -> Iterator[None]:
    """Bind the sink onto every bound adapter for one run, and unbind it after.

    Unbinding matters: `live_council()` builds fresh adapters per compilation today, but a
    deployment that cached one would otherwise keep narrating into the session that finished.
    """
    adapters = [a for a in (council.dissector, council.architect, council.operationalizer,
                            council.repairer) if a is not None]
    for adapter in adapters:
        setattr(adapter, "observer", sink)
    try:
        yield
    finally:
        for adapter in adapters:
            setattr(adapter, "observer", None)


def dissolve(request: CompilationRequest, council: Council, *,
             on_substage: Optional[Callable[..., None]] = None) -> SemanticInquiryGraph:
    """The whole pipeline. Returns a v2 graph whatever happened, including when nothing ran."""
    with _narrating(council, on_substage):
        return _dissolve(request, council, _Narrator(on_substage))


def _dissolve(request: CompilationRequest, council: Council,
              say: _Narrator) -> SemanticInquiryGraph:
    inquiry_id = request.inquiry_id
    refusals: List[CompilerRefusal] = list(request.inherited_refusals)
    notes: List[str] = list(request.inherited_notes)
    passes: List[PassReceipt] = []

    # ── the ledger ──
    say.entering(DissolutionPass.SOURCE_LEDGER,
                 inputs=1 + len(request.reading.blocks if request.reading else ()))
    units, ledger_notes = ledger_mod.build(request.prompt, request.reading, inquiry_id=inquiry_id)
    notes.extend(ledger_notes)
    passes.append(PassReceipt(
        pass_id=ids.pass_id(inquiry_id, DissolutionPass.SOURCE_LEDGER),
        pass_name=DissolutionPass.SOURCE_LEDGER,
        outcome=PassOutcome.COMPLETED if units else PassOutcome.EMPTY,
        call_count=0, inputs=1 + len(request.reading.blocks if request.reading else ()),
        outputs=len(units),
        detail=f"{len(units)} source unit(s): "
               f"{sum(1 for u in units if u.is_user_authored)} from the person, "
               f"{sum(1 for u in units if not u.is_user_authored)} from the reading"))
    say.left(passes[-1])

    # ── dissection ──
    atoms: List[SemanticAtom] = []
    coverage: List[CoverageDisposition] = []
    dissector_ran = False
    say.entering(DissolutionPass.SEMANTIC_DISSECTOR, inputs=len(units))
    if council.dissector is not None and units:
        atoms, coverage, pass_refusals, receipt = council.dissector.dissolve(
            units, prompt=request.prompt, inquiry_id=inquiry_id)
        refusals.extend(pass_refusals)
        passes.append(receipt)
        dissector_ran = receipt.outcome is not PassOutcome.UNAVAILABLE
    else:
        passes.append(PassReceipt(
            pass_id=ids.pass_id(inquiry_id, DissolutionPass.SEMANTIC_DISSECTOR),
            pass_name=DissolutionPass.SEMANTIC_DISSECTOR, outcome=PassOutcome.UNAVAILABLE,
            inputs=len(units),
            detail="no dissector was bound" if council.dissector is None
                   else "the ledger was empty, so there was nothing to dissolve"))
    say.left(passes[-1])

    # ── the audit, and the one repair it may ask for ──
    report = audit_mod.audit(units, atoms, coverage, [], inquiry_id=inquiry_id,
                             dissector_ran=dissector_ran)
    if report.repairable and council.repairer is not None:
        say.entering(DissolutionPass.TARGETED_REPAIR, inputs=len(report.repairable))
        atoms, coverage, refusals, notes, repair_receipt = _repair(
            council.repairer, report, units, atoms, coverage, refusals, notes,
            prompt=request.prompt, inquiry_id=inquiry_id)
        passes.append(repair_receipt)
        say.left(repair_receipt)
        report = audit_mod.audit(units, atoms, coverage, [], inquiry_id=inquiry_id,
                                 dissector_ran=dissector_ran)
    elif report.repairable:
        notes.append(f"{len(report.repairable)} source unit(s) could have been repaired and no "
                     f"repair adapter is bound. Nothing was retried.")

    # ── relations ──
    claims: List[ClaimNode] = []
    edges: List[ClaimEdge] = []
    say.entering(DissolutionPass.RELATION_ARCHITECT, inputs=len(atoms))
    if council.architect is not None:
        claims, edges, pass_refusals, pass_notes, receipt = council.architect.assemble(
            atoms, units, inquiry_id=inquiry_id)
        refusals.extend(pass_refusals)
        notes.extend(pass_notes)
        passes.append(receipt)
    else:
        passes.append(PassReceipt(
            pass_id=ids.pass_id(inquiry_id, DissolutionPass.RELATION_ARCHITECT),
            pass_name=DissolutionPass.RELATION_ARCHITECT, outcome=PassOutcome.UNAVAILABLE,
            inputs=len(atoms), detail="no relation architect was bound"))
    say.left(passes[-1])

    # ── operationalization ──
    observables: List[ObservableSpec] = []
    decisions: List[DecisionCandidate] = []
    remainder: List[SemanticRemainderItem] = []
    say.entering(DissolutionPass.EPISTEMIC_OPERATIONALIZER, inputs=len(claims))
    if council.operationalizer is not None:
        observables, decisions, remainder, pass_refusals, pass_notes, receipt = \
            council.operationalizer.operationalize(claims, edges, inquiry_id=inquiry_id)
        refusals.extend(pass_refusals)
        notes.extend(pass_notes)
        passes.append(receipt)
    else:
        passes.append(PassReceipt(
            pass_id=ids.pass_id(inquiry_id, DissolutionPass.EPISTEMIC_OPERATIONALIZER),
            pass_name=DissolutionPass.EPISTEMIC_OPERATIONALIZER, outcome=PassOutcome.UNAVAILABLE,
            inputs=len(claims), detail="no operationalizer was bound"))
    say.left(passes[-1])

    # ── the final audit, over everything ──
    say.entering(DissolutionPass.COVERAGE_AUDIT, inputs=len(units))
    final = audit_mod.audit(units, atoms, coverage, claims, inquiry_id=inquiry_id,
                            dissector_ran=dissector_ran)
    refusals.extend(final.refusals)
    passes.append(audit_mod.receipt_for(final, inquiry_id=inquiry_id, units=len(units)))
    say.left(passes[-1])

    # A CLAIM STANDING ON A REMOVED ATOM IS DROPPED, not carried. The graph validator refuses one
    # outright, and a compilation that raised there would lose the whole run over one bad reference.
    if final.dangling_claim_atoms:
        gone = set(final.dangling_claim_atoms)
        before = len(claims)
        claims = [c for c in claims if not (set(c.atom_refs) & gone)]
        kept = {c.claim_id for c in claims}
        edges = [e for e in edges if e.from_claim in kept and e.to_claim in kept]
        observables = [o for o in observables if o.claim_id in kept]
        decisions = [d for d in decisions if not d.affected_refs
                     or any(r in kept for r in d.affected_refs)]
        remainder = [r.model_copy(update={"claim_refs": [x for x in r.claim_refs if x in kept]})
                     for r in remainder]
        notes.append(f"{before - len(claims)} claim(s) stood on an atom that is not in the graph "
                     f"and were dropped with what depended on them.")

    coverage = _close_the_ledger(units, coverage, final, notes, inquiry_id=inquiry_id)

    outcome, detail = audit_mod.overall(passes, final)
    notes.append(f"dissolution: {outcome.value} — {detail}")

    return _assemble(request, units=units, atoms=atoms, coverage=coverage, claims=claims,
                     edges=edges, observables=observables, decisions=decisions,
                     remainder=remainder, refusals=refusals, notes=notes, passes=passes)


def _close_the_ledger(units: Sequence[SourceUnit], coverage: List[CoverageDisposition],
                      report: audit_mod.AuditReport, notes: List[str], *,
                      inquiry_id: str) -> List[CoverageDisposition]:
    """The audit is the disposer of LAST RESORT, and it signs its work.

    THE TENSION THIS RESOLVES. "Every source unit has exactly one disposition" is a graph law, so a
    compilation whose dissector never ran could not be represented at all — the pipeline would raise
    rather than produce the empty-graph-carrying-a-refusal the contract also requires. Two laws,
    both right, disagreeing about the same object.

    So the audit closes the ledger itself, and the way it does so is what keeps this from being a
    failure laundered into a tidy table:

      · the disposition is `refused`, never `represented_by` and never `semantic_remainder` —
        remainder is content nothing MEASURES, and this is content nothing PROCESSED;
      · the reason names the audit as the author and says the dissector never accounted for it;
      · a `source_unit_uncovered` refusal is already on the graph, counted;
      · the pass outcome is `coverage_failed` and so is the overall state.

    A reader gets a ledger that still balances and a record saying who balanced it. The alternative
    — refusing to build the graph — would lose the run and every receipt in it over the fact that
    something had already gone wrong.
    """
    if not report.uncovered and not report.double_covered:
        return coverage

    seen: Dict[str, CoverageDisposition] = {}
    dropped = 0
    for entry in coverage:
        if entry.source_unit_id in seen:
            dropped += 1
            continue
        seen[entry.source_unit_id] = entry
    if dropped:
        notes.append(f"{dropped} duplicate coverage entr(ies) were dropped, keeping the first. Two "
                     f"dispositions tell two stories about the same words.")

    for unit_id in report.uncovered:
        seen[unit_id] = CoverageDisposition(
            coverage_id=ids.coverage_id(inquiry_id, unit_id),
            source_unit_id=unit_id, disposition=DispositionKind.REFUSED, refs=[],
            reason="closed by the coverage audit, not by the dissector: no pass accounted for this "
                   "source unit. This is `refused` rather than `semantic_remainder` because "
                   "remainder is content nothing measures and this is content nothing processed.")
    if report.uncovered:
        notes.append(f"the coverage audit closed {len(report.uncovered)} source unit(s) the "
                     f"dissector never accounted for. The ledger balances; it was not the council "
                     f"that balanced it.")
    return [seen[u.source_unit_id] for u in units if u.source_unit_id in seen]


def _repair(repairer: SemanticDissector, report: audit_mod.AuditReport,
            units: Sequence[SourceUnit], atoms: List[SemanticAtom],
            coverage: List[CoverageDisposition], refusals: List[CompilerRefusal],
            notes: List[str], *, prompt: str, inquiry_id: str
            ) -> Tuple[List[SemanticAtom], List[CoverageDisposition], List[CompilerRefusal],
                       List[str], PassReceipt]:
    """One targeted call, over the uncovered units only. Attempt 2, and there is no attempt 3.

    The repaired units are dissolved as their own small ledger. Merging is additive: an atom or a
    disposition the first attempt already produced is kept, so a repair cannot overwrite the part
    that worked.
    """
    by_id = {u.source_unit_id: u for u in units}
    targets = [by_id[u] for u in report.repairable if u in by_id]
    brief = audit_mod.repair_brief(report, units)
    notes.append(
        f"one targeted repair was run over {len(targets)} uncovered source unit(s), carrying only "
        f"those units and the audit's errors ({'; '.join(brief['why'])}). The whole reading was not "
        f"resent: that would be a second attempt at the failed call rather than a repair.")

    new_atoms, new_coverage, repair_refusals, receipt = repairer.dissolve(
        targets, prompt=prompt, inquiry_id=inquiry_id, attempt=2)
    refusals.extend(repair_refusals)

    known_atoms = {a.atom_id for a in atoms}
    atoms = [*atoms, *[a for a in new_atoms if a.atom_id not in known_atoms]]
    known_units = {c.source_unit_id for c in coverage}
    coverage = [*coverage, *[c for c in new_coverage if c.source_unit_id not in known_units]]
    return atoms, coverage, refusals, notes, receipt


def _assemble(request: CompilationRequest, *, units, atoms, coverage, claims, edges, observables,
              decisions, remainder, refusals, notes, passes) -> SemanticInquiryGraph:
    frame = dict(request.inquiry_frame or {})
    dissector_receipt = next((p for p in passes
                              if p.pass_name is DissolutionPass.SEMANTIC_DISSECTOR), None)
    return SemanticInquiryGraph(
        schema_version=SCHEMA_VERSION_V2,
        graph_id=ids.graph_id(request.inquiry_id, request.prompt),
        inquiry_id=request.inquiry_id,
        prompt=request.prompt,                    # VERBATIM. Never rewritten or clarified.
        image_refs=list(request.images),
        inquiry_frame=frame,
        reading=request.reading,
        source_units=list(units),
        semantic_atoms=list(atoms),
        coverage=list(coverage),
        passes=list(passes),
        claims=list(claims),
        claim_edges=list(edges),
        observables=list(observables),
        decision_candidates=list(decisions),
        semantic_remainder=list(remainder),
        refusals=list(refusals),
        provenance=GraphProvenance(
            producer=PRODUCER, compiler_kind="council",
            contract_version=SCHEMA_VERSION_V2,
            inquiry_frame_schema_version=str(frame.get("schema_version") or ""),
            theorist=request.reading.provenance if request.reading else None,
            # `compiler` stays None: v2 has no single compiler receipt, and putting one pass's
            # receipt there would name one of three minds as the author of all of it. The passes
            # list is the receipt.
            compiler=None,
            prompt_sha256=sha256_of(request.prompt), compiled_at=request.now),
        notes=list(notes))


def coverage_table(graph: SemanticInquiryGraph) -> List[Dict[str, Any]]:
    """One row per source unit: what it said, and what became of it. The deliverable's table."""
    by_unit = {c.source_unit_id: c for c in graph.coverage}
    by_atom = {a.atom_id: a for a in graph.semantic_atoms}
    rows: List[Dict[str, Any]] = []
    for unit in graph.source_units:
        entry = by_unit.get(unit.source_unit_id)
        atoms = [by_atom[r] for r in (entry.refs if entry else ()) if r in by_atom]
        rows.append({
            "source_unit_id": unit.source_unit_id,
            "kind": unit.kind.value,
            "author": "user" if unit.is_user_authored else "scene_theorist",
            "quote": unit.exact_quote,
            "disposition": entry.disposition.value if entry else "(none)",
            "atoms": [{"atom_id": a.atom_id, "unit_kind": a.unit_kind.value, "text": a.text}
                      for a in atoms],
            "reason": entry.reason if entry else "the audit found no disposition for this unit",
        })
    return rows


__all__ = ["PRODUCER", "PASS_ORDER", "PASS_LABEL", "Council", "live_council", "dissolve",
           "coverage_table"]
