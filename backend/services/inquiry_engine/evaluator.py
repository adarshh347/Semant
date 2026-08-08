"""
HARNESS-001B §6 — the goal evaluator: declared criteria against returned evidence, and nothing else.

Three rules, and each is a way a goal engine lies if it is not written down:

  1. **It evaluates only DECLARED criteria.** Not "did the mission complete", not "did the actuator
     return 200", not "did the agents agree". A completed actuator call is a completed actuator
     call; a fluent dialogue is a fluent dialogue. `satisfied` is a claim about EVIDENCE meeting a
     predicate somebody wrote down before the run.

  2. **`partially_satisfied` names exactly which clauses remain.** A partial result whose remainder
     is a number ("3 of 5") is a partial result nobody can act on. The verdict carries the clause
     ids and their text, so the honest report writes itself.

  3. **`capability_gap` is not `no_new_evidence` and is not success.** Three separate verdicts,
     because they tell a curator to do three different things: build an instrument, look somewhere
     else, or stop looking.

## Why an interpretive clause is never satisfied here

`demands=interpretive` is settled by a curator, and this module has no curator. It could be made to
"pass" by accepting a model's reading, and that reading would be indistinguishable in the log from a
measured one — so the evaluator has no path to it at all. The verdict is `awaiting_human` at run
level and the clause stays in `remaining`, named.

`demands=imagined` is stronger still: there is no evidence, present or future, that settles "what
hybrid styles could they give birth to". It remains unresolved and is explicitly NOT reported as a
capability gap, because no instrument is missing — the question was never a measurement.

## Measurements are byte-identical whether or not a goal wanted them

Nothing in this module touches a mark. It reads `epistemic_status`, `basis` and `relation` off
evidence that already exists, exactly as `agents.goal.satisfying_marks` reads the percept field.
`test_inquiry_engine_boundaries.py` pins it by running the same locus with and without a goal and
comparing the marks byte for byte.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Sequence, Tuple

from backend.services.inquiry_engine.events import (EVIDENCE_ORGAN_MARK, EVIDENCE_PRODUCTION,
                                                    EVIDENCE_TESTIMONY, Evidence)
from backend.services.inquiry_engine.goals import (CLAUSE_IMAGINED, CLAUSE_INTERPRETIVE,
                                                   CLAUSE_MEASURED, CLAUSE_SOURCED, Criterion,
                                                   EvidenceGoal, STATUS_CAPABILITY_GAP,
                                                   STATUS_PARTIALLY_SATISFIED, STATUS_SATISFIED,
                                                   STATUS_UNRESOLVED)


@dataclass(frozen=True)
class ClauseVerdict:
    """One criterion, settled or not, with the evidence that settled it cited by id."""
    criterion_id: str
    clause: str
    demands: str
    met: bool
    why: str
    evidence_ids: Tuple[str, ...] = ()
    #: True when nothing this system can ever produce would meet it — an interpretive or imagined
    #: clause. Distinct from `met=False`, which means "not yet, by evidence that could exist".
    unmeetable_by_evidence: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"criterion_id": self.criterion_id, "clause": self.clause, "demands": self.demands,
                "met": self.met, "why": self.why, "evidence_ids": list(self.evidence_ids),
                "unmeetable_by_evidence": self.unmeetable_by_evidence}


@dataclass(frozen=True)
class GoalVerdict:
    """What became of one evidence goal, with the remainder named rather than counted."""
    goal_id: str
    status: str
    clauses: Tuple[ClauseVerdict, ...] = ()
    why: str = ""

    @property
    def met(self) -> Tuple[ClauseVerdict, ...]:
        return tuple(c for c in self.clauses if c.met)

    @property
    def remaining(self) -> Tuple[ClauseVerdict, ...]:
        return tuple(c for c in self.clauses if not c.met)

    @property
    def awaiting_human(self) -> bool:
        """At least one clause that only a curator can settle. Kept separate from `remaining`
        because "nobody has looked yet" and "no amount of looking would do it" ask for different
        next moves."""
        return any(c.unmeetable_by_evidence and c.demands == CLAUSE_INTERPRETIVE
                   for c in self.clauses)

    def to_dict(self) -> Dict[str, Any]:
        return {"goal_id": self.goal_id, "status": self.status, "why": self.why,
                "clauses": [c.to_dict() for c in self.clauses],
                "remaining": [c.clause for c in self.remaining],
                "remaining_ids": [c.criterion_id for c in self.remaining]}


def _matches(criterion: Criterion, item: Evidence) -> bool:
    """Does this evidence item settle this clause?

    Every check is a comparison against something the evidence ALREADY SAYS about itself. Nothing
    is inferred from the item's existence — an organ mark that exists is not thereby a mark of the
    relation the clause asked about, and a run that assumed so would satisfy a nestedness clause
    with an adjacency measurement.
    """
    if criterion.demands not in (CLAUSE_MEASURED, CLAUSE_SOURCED):
        return False        # interpretive / imagined never match — see the module note
    # THE STATUS IS THE PRODUCER'S WORD, whoever the producer was. An organ's mask nesting and a
    # segmenter's measured extent are both measurements, and this is not the place to rank them.
    #
    # "A completed actuator call is not satisfaction" is enforced upstream instead, and more
    # precisely: `engine._evidence_from_preparation` turns only stamped DESCRIPTORS into evidence,
    # never lineage records — so a step that ran and produced nothing contributes nothing here.
    if item.epistemic_status != criterion.demands:
        return False
    if item.kind not in (EVIDENCE_ORGAN_MARK, EVIDENCE_PRODUCTION):
        return False
    if criterion.produced_by and str(item.producer) not in criterion.produced_by:
        return False
    if criterion.relation and str(item.relation) != criterion.relation:
        return False
    if criterion.basis and str(item.basis) != criterion.basis:
        return False
    return True


def evaluate_clause(criterion: Criterion, evidence: Sequence[Evidence]) -> ClauseVerdict:
    if criterion.demands == CLAUSE_INTERPRETIVE:
        return ClauseVerdict(
            criterion_id=criterion.id, clause=criterion.clause, demands=criterion.demands,
            met=False, unmeetable_by_evidence=True,
            why=("an interpretive clause is the curator's to make. No organ measures it, and a "
                 "model's sentence would sit in this log looking exactly like one that was "
                 "measured — so this clause waits for a hand rather than being settled here."))
    if criterion.demands == CLAUSE_IMAGINED:
        return ClauseVerdict(
            criterion_id=criterion.id, clause=criterion.clause, demands=criterion.demands,
            met=False, unmeetable_by_evidence=True,
            why=("speculation is not evidence. No instrument is missing — this was never a "
                 "measurement question — so it is carried unresolved and is deliberately NOT "
                 "reported as a capability gap."))

    hits = [e for e in evidence if _matches(criterion, e)]
    if hits:
        return ClauseVerdict(
            criterion_id=criterion.id, clause=criterion.clause, demands=criterion.demands,
            met=True, evidence_ids=tuple(e.id for e in hits),
            why=(f"{len(hits)} piece(s) of {criterion.demands} evidence match"
                 + (f" relation {criterion.relation!r}" if criterion.relation else "")
                 + (f" on the {criterion.basis!r} basis" if criterion.basis else "")))

    testimony = [e for e in evidence if e.kind == EVIDENCE_TESTIMONY]
    why = (f"no {criterion.demands} evidence"
           + (f" of relation {criterion.relation!r}" if criterion.relation else "")
           + (f" on the {criterion.basis!r} basis" if criterion.basis else "")
           + f" returned; {len(evidence)} item(s) came back and none matched")
    if testimony:
        why += (f". {len(testimony)} of them are testimony — agents said things about this locus. "
                f"Testimony is not a measurement and the engine does not upgrade it")
    return ClauseVerdict(criterion_id=criterion.id, clause=criterion.clause,
                         demands=criterion.demands, met=False, why=why)


def evaluate(goal: EvidenceGoal, evidence: Sequence[Evidence], *,
             gap: str = "") -> GoalVerdict:
    """One evidence goal → its verdict.

    `gap` is the unmet requirement when capability resolution already reported one. It arrives from
    the resolver rather than being inferred here, because "no instrument" is a fact about the system
    and "no evidence" is a fact about this picture, and only the resolver knows the first.
    """
    clauses = tuple(evaluate_clause(c, evidence) for c in goal.criteria)

    if gap:
        return GoalVerdict(
            goal_id=goal.id, status=STATUS_CAPABILITY_GAP, clauses=clauses,
            why=(f"no current instrument measures this: {gap}. That is not 'nothing was found' and "
                 f"it is not success — it is a named absence in the sensorium."))

    if not clauses:
        return GoalVerdict(
            goal_id=goal.id, status=STATUS_UNRESOLVED, clauses=(),
            why=("the goal declared no criterion, so there is nothing that could be satisfied. A "
                 "goal with no predicate cannot be met — reporting it as satisfied because work "
                 "happened is the failure this evaluator exists to prevent."))

    met = [c for c in clauses if c.met]
    if len(met) == len(clauses):
        return GoalVerdict(goal_id=goal.id, status=STATUS_SATISFIED, clauses=clauses,
                           why=f"every declared criterion ({len(clauses)}) is met by returned "
                               f"evidence")
    if met:
        remaining = [c.clause for c in clauses if not c.met]
        return GoalVerdict(
            goal_id=goal.id, status=STATUS_PARTIALLY_SATISFIED, clauses=clauses,
            why=(f"{len(met)} of {len(clauses)} criteria met; still open: "
                 f"{'; '.join(remaining)}"))
    return GoalVerdict(
        goal_id=goal.id, status=STATUS_UNRESOLVED, clauses=clauses,
        why=(f"none of the {len(clauses)} declared criteria is met by the "
             f"{len(evidence)} piece(s) of evidence returned"))


def assert_not_satisfied_without_evidence(verdict: GoalVerdict) -> None:
    """The write-side twin, in the shape `agents.goal.assert_satisfied_is_measured` established.

    `satisfied` with no cited evidence is the whole confabulation of a goal engine, and it is the
    one thing that must fail loudly rather than be reported.
    """
    if verdict.status != STATUS_SATISFIED:
        return
    if not any(c.evidence_ids for c in verdict.clauses):
        raise AssertionError(
            f"goal {verdict.goal_id!r} is reported satisfied and no clause cites a single piece of "
            f"evidence. A goal is satisfied by evidence meeting a declared criterion or it is not "
            f"satisfied — 'the work completed' is not a third way.")


__all__ = ["ClauseVerdict", "GoalVerdict", "evaluate", "evaluate_clause",
           "assert_not_satisfied_without_evidence"]
