"""
HARNESS-003A §7 — the deterministic audit, and the one repair it is allowed to ask for.

    the ledger + the atoms + the coverage + the graph
      -> errors, by name
      -> the source units a repair could still cover
      -> an overall quality state

NO MODEL RUNS HERE, for the same reason none runs in the ledger: the audit is the check on the
council, and a check the council performed on itself is not a check. Everything below is a set
comparison.

## Why a repair is bounded to one call, and to the units that failed

A retry loop hides a marginal prompt behind a good average. A repair that resent the whole reading
would be a second attempt at the failed call rather than a repair, and would cost the same
truncation again. So the repair receives ONLY the uncovered units and the audit's own error list,
which is both smaller than the original request and different in kind from it — and both attempts
keep their receipts, so "this needed a second pass" is visible rather than smoothed away.

`repairable` deliberately excludes units nothing could fix: if the dissector was unavailable there
is nothing to repair, and asking again is the retry this module refuses to perform.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.schemas.semantic_compilation import (ClaimNode, CompilerRefusal, CompilerRefusalKind,
                                                  CoverageDisposition, DispositionKind,
                                                  DissolutionPass, ObservableSpec, PassOutcome,
                                                  PassReceipt, SemanticAtom, SemanticRemainderItem,
                                                  SourceUnit)

from . import ids
from .base import refusal

PRODUCER = "semantic_compilation/audit-v1"


@dataclass(frozen=True)
class AuditReport:
    """What the audit found. A value, so a caller can act on it and a test can assert on it."""
    errors: Tuple[str, ...] = ()
    uncovered: Tuple[str, ...] = ()
    double_covered: Tuple[str, ...] = ()
    dangling_atom_anchors: Tuple[str, ...] = ()
    dangling_coverage_refs: Tuple[str, ...] = ()
    dangling_claim_atoms: Tuple[str, ...] = ()
    orphaned_atoms: Tuple[str, ...] = ()
    repairable: Tuple[str, ...] = ()
    refusals: Tuple[CompilerRefusal, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.errors

    @property
    def coverage_failed(self) -> bool:
        return bool(self.uncovered or self.double_covered)


def audit(units: Sequence[SourceUnit], atoms: Sequence[SemanticAtom],
          coverage: Sequence[CoverageDisposition], claims: Sequence[ClaimNode], *,
          inquiry_id: str, dissector_ran: bool = True) -> AuditReport:
    """Every reference checked against what actually exists. Pure set comparison."""
    unit_ids = {u.source_unit_id for u in units}
    atom_ids = {a.atom_id for a in atoms}

    seen: Dict[str, int] = {}
    dangling_coverage: List[str] = []
    for entry in coverage:
        seen[entry.source_unit_id] = seen.get(entry.source_unit_id, 0) + 1
        if entry.disposition is DispositionKind.REPRESENTED_BY:
            dangling_coverage += [r for r in entry.refs if r not in atom_ids]
        elif entry.disposition is DispositionKind.DUPLICATE_OF:
            dangling_coverage += [r for r in entry.refs if r not in unit_ids]

    uncovered = sorted(unit_ids - set(seen))
    doubled = sorted(k for k, n in seen.items() if n > 1)
    dangling_anchors = sorted({r for a in atoms for r in a.source_unit_ids if r not in unit_ids})
    dangling_claim_atoms = sorted({r for c in claims for r in c.atom_refs if r not in atom_ids})
    used = {r for c in claims for r in c.atom_refs}
    orphans = sorted(a.atom_id for a in atoms if a.atom_id not in used)

    errors: List[str] = []
    refusals: List[CompilerRefusal] = []
    if uncovered:
        errors.append(f"{len(uncovered)} source unit(s) have no coverage disposition")
        for unit_id in uncovered:
            refusals.append(refusal(
                inquiry_id, CompilerRefusalKind.SOURCE_UNIT_UNCOVERED, unit_id,
                "the audit found a source unit nothing accounted for. A paragraph that vanished "
                "with nothing saying so is the failure this whole ledger exists to make visible."))
    if doubled:
        errors.append(f"{len(doubled)} source unit(s) have more than one disposition")
        for unit_id in doubled:
            refusals.append(refusal(
                inquiry_id, CompilerRefusalKind.SOURCE_UNIT_DOUBLE_COVERED, unit_id,
                "two dispositions tell two stories about the same words and a reader cannot tell "
                "which one is the record."))
    if dangling_anchors:
        errors.append(f"{len(dangling_anchors)} atom anchor(s) point outside the ledger")
    if dangling_coverage:
        errors.append(f"{len(dangling_coverage)} coverage reference(s) resolve to nothing")
    if dangling_claim_atoms:
        errors.append(f"{len(dangling_claim_atoms)} claim(s) are built from atoms that are gone")

    # REPAIRABLE IS NARROWER THAN UNCOVERED. If the dissector never ran there is nothing to repair,
    # and asking again would be the retry this lane refuses.
    repairable = tuple(uncovered) if dissector_ran else ()

    return AuditReport(
        errors=tuple(errors), uncovered=tuple(uncovered), double_covered=tuple(doubled),
        dangling_atom_anchors=tuple(dangling_anchors),
        dangling_coverage_refs=tuple(sorted(set(dangling_coverage))),
        dangling_claim_atoms=tuple(dangling_claim_atoms), orphaned_atoms=tuple(orphans),
        repairable=repairable, refusals=tuple(refusals))


def receipt_for(report: AuditReport, *, inquiry_id: str, units: int,
                attempt: int = 1) -> PassReceipt:
    outcome = (PassOutcome.COMPLETED if report.clean
               else PassOutcome.COVERAGE_FAILED if report.coverage_failed
               else PassOutcome.THIN)
    detail = ("every source unit has exactly one disposition and every reference resolves"
              if report.clean else "; ".join(report.errors))
    return PassReceipt(
        pass_id=ids.pass_id(inquiry_id, DissolutionPass.COVERAGE_AUDIT, attempt),
        pass_name=DissolutionPass.COVERAGE_AUDIT, outcome=outcome, call_count=0,
        inputs=units, outputs=len(report.errors), detail=detail,
        notes=[f"{len(report.orphaned_atoms)} atom(s) reached no claim"]
        if report.orphaned_atoms else [])


def overall(passes: Sequence[PassReceipt], report: AuditReport) -> Tuple[PassOutcome, str]:
    """The compilation's one quality state, from the passes and the audit.

    ORDER IS THE WHOLE CONTENT of this function, and it is the order a reader needs rather than the
    order of severity: an `unavailable` pass explains everything after it, a truncation explains a
    coverage failure, and a coverage failure explains thinness. Reporting the downstream symptom
    would send somebody to fix the wrong thing.
    """
    if not passes:
        return PassOutcome.UNAVAILABLE, "no pass ran"
    truncated = [p for p in passes if p.truncated]
    if truncated:
        return (PassOutcome.TRUNCATED,
                f"{', '.join(sorted({p.pass_name.value for p in truncated}))} hit a completion "
                f"budget; everything downstream of it saw a prefix")
    errored = [p for p in passes if p.outcome is PassOutcome.ERROR]
    if errored:
        return (PassOutcome.ERROR,
                f"{', '.join(sorted({p.pass_name.value for p in errored}))} failed")
    unavailable = [p for p in passes if p.outcome is PassOutcome.UNAVAILABLE]
    if unavailable:
        return (PassOutcome.UNAVAILABLE,
                f"{', '.join(sorted({p.pass_name.value for p in unavailable}))} was unavailable")
    if report.coverage_failed:
        return (PassOutcome.COVERAGE_FAILED,
                f"{len(report.uncovered)} uncovered and {len(report.double_covered)} "
                f"double-covered source unit(s)")
    if not report.clean:
        return PassOutcome.THIN, "; ".join(report.errors)
    thin = [p for p in passes if p.outcome is PassOutcome.THIN]
    if thin:
        return (PassOutcome.THIN,
                "; ".join(f"{p.pass_name.value}: {p.detail}" for p in thin))
    empty = [p for p in passes if p.outcome is PassOutcome.EMPTY]
    if empty:
        return (PassOutcome.EMPTY,
                f"{', '.join(sorted({p.pass_name.value for p in empty}))} produced nothing")
    return PassOutcome.COMPLETED, "every pass completed and the ledger is whole"


def repair_brief(report: AuditReport, units: Sequence[SourceUnit]) -> Dict[str, Any]:
    """What a repair call is given: the units that failed, and why the audit said so.

    NOT the prompt, NOT the reading, NOT the atoms that already worked. A repair that resent the
    original request would be a second attempt at the failed call and would cost the same
    truncation again.
    """
    by_id = {u.source_unit_id: u for u in units}
    return {
        "why": list(report.errors),
        "source_units": [{"source_unit_id": u, "text": by_id[u].exact_quote,
                          "kind": by_id[u].kind.value,
                          "author": "user" if by_id[u].is_user_authored else "scene_theorist"}
                         for u in report.repairable if u in by_id],
    }


__all__ = ["PRODUCER", "AuditReport", "audit", "receipt_for", "overall", "repair_brief"]
