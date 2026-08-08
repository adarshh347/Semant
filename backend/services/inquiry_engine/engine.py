"""
HARNESS-001B §5 — the bounded, deterministic inquiry loop.

    frame
      → derive evidence goals
      → resolve capabilities
      → run ready Director preparation tasks
      → dispatch ready agent missions
      → collect evidence / refusals / trajectory summaries
      → evaluate goals
      → replan ONLY from new evidence or a named gap
      → answerable | partially_answerable | awaiting_human | exhausted

## Bounded, and deterministic

There is no open-ended autonomous loop here and there is no place to put one. Every round must
either produce new evidence or open a goal that a named gap made reachable; a round that does
neither ends the run with `no_new_evidence`. The round count is a hard ceiling on top of that, not
the mechanism — a loop whose only bound is a round limit is an open-ended loop with a timer.

Determinism: nothing here reads a clock, a random number or a database. `now` is handed in, goal ids
are derived from the frame's own content, and the adapters are injected. The same frame over the
same posts produces the same run, byte for byte — which is what makes `scripts/inquiry_goal_run.py`
a replay rather than a demo.

## The replan rule, concretely

The only replan this lane performs is the COMPOSITE one, and it is the honest minimum: a need whose
organ reads a field a model produces (today, depth) has its preparation run in one round and its
mission dispatched in the next, GATED on the preparation actually having returned something. That is
"replan from new evidence" with nothing invented — the second round exists because the first
produced a field, and does not exist when it did not.

## What a goal may and may not do

A goal SELECTS work. It never alters a measurement. Nothing in this module touches a mark: evidence
is constructed by `Evidence.of_mark`, which copies the organ's own word, and the boundary test runs
the same locus with and without a goal and compares the marks byte for byte.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.inquiry_engine import capability as cap
from backend.services.inquiry_engine import evaluator as ev
from backend.services.inquiry_engine.adapters import (FakeDirectorAdapter, MissionResult,
                                                      PreparationResult, SimulatorAdapter)
from backend.services.inquiry_engine.events import (ACTOR_AGENT, ACTOR_DIRECTOR, ACTOR_ENGINE,
                                                    EV_AGENT_PERCEIVED, EV_AGENT_REFUSED,
                                                    EV_CAPABILITY_GAP, EV_CAPABILITY_RESOLVED,
                                                    EV_DIRECTOR_TASK_COMPLETED,
                                                    EV_DIRECTOR_TASK_REFUSED,
                                                    EV_DIRECTOR_TASK_STARTED,
                                                    EV_EVIDENCE_RETURNED, EV_GOAL_CREATED,
                                                    EV_GOAL_PARTIAL, EV_GOAL_SATISFIED,
                                                    EV_GOAL_UNRESOLVED, EV_INQUIRY_FRAMED,
                                                    EV_MISSION_DISPATCHED, EV_RUN_STOPPED,
                                                    OUTCOME_ANSWERABLE, OUTCOME_AWAITING_HUMAN,
                                                    OUTCOME_EXHAUSTED,
                                                    OUTCOME_PARTIALLY_ANSWERABLE,
                                                    STOP_BUDGET_EXHAUSTED, STOP_AWAITING_HUMAN,
                                                    STOP_CAPABILITY_GAP,
                                                    STOP_EXECUTION_UNAVAILABLE,
                                                    STOP_NO_NEW_EVIDENCE, STOP_SATISFIED,
                                                    CapabilityGap, Evidence, InquiryRun, new_run)
from backend.services.inquiry_engine.frame import AcceptedFrame, ProposedAction, accept
from backend.services.inquiry_engine.goals import (CLAUSE_INTERPRETIVE,
                                                   CLAUSE_MEASURED, CLAUSE_MODES, CLAUSE_SOURCED,
                                                   AgentMission, Criterion, EvidenceGoal, Goal,
                                                   InquiryGoal, PreparationTask,
                                                   STATUS_ACTIVE, STATUS_CAPABILITY_GAP,
                                                   STATUS_EXHAUSTED, STATUS_PARTIALLY_SATISFIED,
                                                   STATUS_PROPOSED, STATUS_READY, STATUS_REFUSED,
                                                   STATUS_SATISFIED, STATUS_UNRESOLVED)

DEFAULT_MAX_ROUNDS = 3

ORIGIN_ACTION = "proposed_action"
ORIGIN_TERM = "unresolved_term"
ORIGIN_ATTENTION = "attention"
ORIGIN_DEMAND = "epistemic_demand"


@dataclass
class _Ids:
    """Content-derived ids, so a replayed run is identical to the first one. A uuid here would make
    every proof in this lane compare two runs that differ in every id."""
    run_id: str
    n: int = 0

    def next(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}_{self.n:03d}"


# ── deriving the hierarchy from a frame ──────────────────────────────────────

def _demand_mode(demand: Demand) -> Tuple[str, str, bool]:
    """(mode, clause, confident) for one `epistemic_demands` entry.

    Four ways a mode is decided, in order of how much the frame actually said:

      0. LANE A DECLARED IT. `DemandKind` is read, never re-derived. This is the branch that
         matters, and it is a correctness fix rather than an optimisation: against Lane A's real
         output, re-deriving found `fold` inside `unfolding` and turned "way of unfolding" — which
         Lane A marks `unresolved`, "no organ in the sensorium is scoped to a manner" — into a
         MEASURED criterion this engine could report having produced.
      1. an explicit `"<mode>: <clause>"` prefix, which the committed fixtures use;
      2. the clause routes to a declared need, whose `demands` says what kind of knowing it is;
      3. nothing matched — and the fallback is `interpretive`, NOT `measured`.

    The fallback direction is the whole point. An unrecognised demand treated as measurable would
    become a clause this engine could report satisfied; treated as interpretive it can only ever
    await a human. When the engine cannot tell what kind of knowing something asks for, it must not
    be able to claim it produced it. `confident=False` is carried so the run can say which clauses
    fell through rather than presenting the guess as a reading.
    """
    raw = demand.text.strip()
    if demand.mode:
        return demand.mode, demand.clause or raw, True
    for mode in CLAUSE_MODES:
        if raw.lower().startswith(f"{mode}:"):
            return mode, raw.split(":", 1)[1].strip() or raw, True
    need_key = cap.need_for_term(raw)
    if need_key:
        return cap.NEEDS[need_key].demands, raw, True
    return CLAUSE_INTERPRETIVE, raw, False


def _criterion_for(need_key: str, *, cid: str, clause: str) -> Criterion:
    need = cap.NEEDS[need_key]
    return Criterion(id=cid, clause=clause, demands=need.demands,
                     relation=need.relation, basis=need.basis,
                     # The clause names the instruments that settle it, so one goal's measurement
                     # cannot quietly satisfy another goal's clause about a different subject.
                     produced_by=(*need.actuators, *need.organs, *need.prepares_first),
                     detail=need.summary)


def derive(frame: AcceptedFrame, *, ids: _Ids, post_id: str = "", region_id: str = "",
           ) -> Tuple[InquiryGoal, Tuple[EvidenceGoal, ...], Tuple[str, ...]]:
    """A frame → the inquiry goal and its evidence goals. Returns any notes the derivation owes.

    Four sources, deduplicated by (need, phrase) so an attention and a proposed action naming the
    same concept produce ONE goal rather than two that would each report the same gap:

        proposed_actions    the grammar-valid acts Lane A proposed — the principal source
        unresolved_terms    what the frame could not settle; the fold gap arrives here
        attentions          what caught the curator, where it routes to a declared need
        epistemic_demands   the clauses, which become criteria on the inquiry goal

    A source that routes to no declared need is NOT dropped. It becomes an evidence goal with an
    empty need, which `resolve_need` refuses BY NAME — a dropped term is invisible in the run and an
    unmatched one is a fact about the frame.
    """
    notes: List[str] = []
    criteria: List[Criterion] = []
    #: Demands Lane A marked `unresolved` — its own finding that no producer exists. Transported to
    #: the evidence-goal pass below as a declared gap rather than becoming a clause: a criterion
    #: would imply something could settle it, and re-deriving the reason would present Lane A's
    #: finding as this engine's conclusion.
    declared_gaps: List[Demand] = [d for d in frame.epistemic_demands if d.declares_gap]

    #: Each criterion beside the TERM it came from. Lane A's `clause` is the whole sentence the
    #: demand was read out of and its `term` is the word — the sentence is what a reader should see
    #: on the criterion, and the word is what routes to a need. Keeping only one of them made the
    #: goal pass below try to route "their common way of unfolding sensuality" as a term.
    criteria_terms: List[Tuple[Criterion, str]] = []

    for demand in frame.epistemic_demands:
        if demand.declares_gap:
            continue
        mode, clause, confident = _demand_mode(demand)
        criterion = Criterion(id=ids.next("cr"), clause=clause, demands=mode,
                              detail=("" if confident else
                                      "the frame did not say what kind of knowing this asks "
                                      "for and no declared need matched it"))
        criteria.append(criterion)
        criteria_terms.append((criterion, demand.text))
        if not confident:
            notes.append(
                f"epistemic demand {demand.text!r} matched no declared need and carried no "
                f"explicit mode; it is carried as {CLAUSE_INTERPRETIVE!r} so this engine cannot "
                f"report having produced it")

    inquiry = InquiryGoal(
        id=ids.next("iq"), title=frame.prompt[:80], prompt=frame.prompt, mode=frame.mode,
        criteria=tuple(criteria), status=STATUS_ACTIVE,
        detail="the human-scale purpose, in the curator's own words, unrewritten")

    seen: set = set()
    goals: List[EvidenceGoal] = []

    def _add(*, need_key: str, phrase: str, question: str, origin: str,
             clause: str, action: Optional[ProposedAction] = None,
             declared_gap: str = "") -> None:
        # ONE GOAL PER DECLARED NEED. An attention, a proposed act and an epistemic demand that all
        # point at containment are one question asked three ways, and three goals would report the
        # same gap three times — which reads as three findings.
        #
        # A framer-declared gap keys on the PHRASE rather than the origin, because Lane A names the
        # same term in both `epistemic_demands` (kind `unresolved`) and `unresolved_terms`, and two
        # goals carrying one finding would double it in the report.
        key = f"gap:{phrase.lower()}" if declared_gap else (need_key or
                                                            f"{origin}:{phrase.lower()}")
        if key in seen:
            return
        seen.add(key)
        gid = ids.next("eg")
        crit = ((_criterion_for(need_key, cid=ids.next("cr"), clause=clause),)
                if need_key in cap.NEEDS and not declared_gap else ())
        goals.append(EvidenceGoal(
            id=gid, parent_goal_id=inquiry.id, title=question[:80], need=need_key,
            question=question, phrase=phrase, post_id=post_id, region_id=region_id,
            origin=origin, criteria=crit, status=STATUS_PROPOSED,
            action=action.to_dict() if action is not None else {},
            declared_gap=declared_gap,
            detail=(declared_gap or cap.NEEDS[need_key].summary if need_key in cap.NEEDS
                    else declared_gap or f"nothing declared serves {phrase!r}")))

    for action in frame.proposed_actions:
        words = action.phrase or action.role or ""
        # The act is CARRIED, not flattened to the need. Three public acts have rules of their own
        # in `capability.resolve_action` and a goal reduced to a need would lose all three.
        need_key = cap.need_for_term(words) or cap.need_for_action(action.type) or ""
        _add(need_key=need_key, phrase=words,
             question=f"{action.type}({words})" if words else action.type,
             origin=ORIGIN_ACTION, action=action,
             clause=f"the act {action.type!r} is served")

    # LANE A'S OWN GAPS, transported first so a term it already adjudicated is not re-derived below.
    for demand in declared_gaps:
        _add(need_key="", phrase=demand.text,
             question=f"what evidence would settle {demand.text!r}?",
             origin=ORIGIN_DEMAND, clause=demand.clause or demand.text,
             declared_gap=demand.why or
             "the framer found no producer for this at all — not a weak measurement, the absence "
             "of an instrument")

    for term in frame.unresolved_terms:
        # THE FRAMER'S DECLARATION WINS over a near-miss in this engine's term table. Lane A saw the
        # whole clause and refused it; our table matching a neighbouring instrument is precisely the
        # "confident gap against the wrong organ" `need_for_term` warns about — and it reads as a
        # considered finding. A term carrying no reason (the committed fixtures) still routes.
        if term.why:
            _add(need_key="", phrase=term.text,
                 question=f"what evidence would settle {term.text!r}?",
                 origin=ORIGIN_TERM, clause=term.text, declared_gap=term.why)
            continue
        _add(need_key=cap.need_for_term(term.text) or "", phrase=term.text,
             question=f"what evidence would settle {term.text!r}?",
             origin=ORIGIN_TERM, clause=term.text)

    for attention in frame.attentions:
        need_key = cap.need_for_term(attention) or ""
        if not need_key:  # noqa: SIM102 — the note below is the point
            # An attention that matches no need is NOT a gap — the curator looked at something and
            # this engine has no question for it yet. Recorded as a note; inventing an evidence goal
            # would manufacture a refusal against a word nobody asked a question about.
            notes.append(f"attention {attention!r} routes to no declared need; no evidence goal "
                         f"was derived from it")
            continue
        _add(need_key=need_key, phrase=attention,
             question=f"what can be measured about {attention!r}?",
             origin=ORIGIN_ATTENTION, clause=attention)

    # EVERY demand that routes to a declared need becomes a goal, not only the measurable ones. An
    # interpretive or imagined clause with no goal behind it would sit on the inquiry unexamined and
    # unreported, which is the quietest possible way to drop the hardest half of a prompt.
    for crit, term in criteria_terms:
        need_key = cap.need_for_term(term) or cap.need_for_term(crit.clause) or ""
        if need_key:
            _add(need_key=need_key, phrase=term or crit.clause,
                 question=f"what settles {(term or crit.clause)!r}?",
                 origin=ORIGIN_DEMAND, clause=crit.clause)

    return inquiry, tuple(goals), tuple(notes)


# ── the loop ─────────────────────────────────────────────────────────────────

@dataclass
class _Pending:
    """One evidence goal's work, waiting. Held outside the run because it is machinery, not
    history — what survives is the goals, the events and the evidence."""
    goal: EvidenceGoal
    resolution: cap.Resolution
    task: Optional[PreparationTask] = None
    mission: Optional[AgentMission] = None
    task_done: bool = False
    mission_done: bool = False
    prep_produced: int = 0


def run_inquiry(frame_mapping: Mapping[str, Any], *,
                posts: Optional[Mapping[str, Mapping[str, Any]]] = None,
                director=None, simulator=None,
                run_id: str = "", now: str = "",
                post_id: str = "", region_id: str = "",
                organ_set: Sequence[str] = (),
                graph: Optional[Mapping[str, Any]] = None,
                proposed_marks: Sequence[Mapping[str, Any]] = (),
                image: Any = None, depth_field: Any = None,
                situated_goal_name: str = "",
                mission_budget: int = 0,
                capabilities_up: Optional[frozenset] = None,
                max_rounds: int = DEFAULT_MAX_ROUNDS) -> InquiryRun:
    """One frame → one bounded run → one serialisable `InquiryRun`.

    `director` and `simulator` are injected. With no simulator the real `SimulatorAdapter` is used —
    it needs nothing but pure-python organs. With no director, a `FakeDirectorAdapter` that has
    NOTHING to give is used, so a run with no Director wiring reports `unavailable` explicitly
    rather than silently skipping the global half.
    """
    posts = dict(posts or {})
    stamp = str(now or "").strip()
    if not stamp:
        raise ValueError(
            "run_inquiry needs a timestamp handed in. This module reads no clock: a run whose "
            "events were stamped from the wall clock could not be replayed and compared, and every "
            "proof in this lane is a comparison of two runs.")

    frame = accept(frame_mapping)
    run_id = run_id or f"inq_{frame.inquiry_id or 'run'}"
    ids = _Ids(run_id=run_id)
    director = director if director is not None else FakeDirectorAdapter(
        records=(), suggestions=(), available=False, ran=False)
    simulator = simulator if simulator is not None else SimulatorAdapter()

    run = new_run(run_id=run_id, frame=frame, at=stamp)
    run = run.with_event(kind=EV_INQUIRY_FRAMED, step_id=ids.next("st"), actor=ACTOR_ENGINE,
                         source="frame", at=stamp,
                         reason="a validated inquiry-frame.v1 mapping was accepted by shape",
                         payload={"inquiry_id": frame.inquiry_id, "mode": frame.mode,
                                  "prompt": frame.prompt,
                                  "adjustments": list(frame.adjustments)})

    inquiry, evidence_goals, notes = derive(frame, ids=ids, post_id=post_id, region_id=region_id)
    run = run.with_goal(inquiry)
    run = run.with_event(kind=EV_GOAL_CREATED, step_id=ids.next("st"), actor=ACTOR_ENGINE,
                         source="derivation", at=stamp, goal_id=inquiry.id,
                         reason="the human-scale purpose, carried verbatim",
                         payload={"kind": inquiry.kind, "criteria": len(inquiry.criteria)})
    for note in notes:
        run = run.with_note(note)

    pendings: List[_Pending] = []
    for goal in evidence_goals:
        run = run.with_goal(goal)
        run = run.with_event(kind=EV_GOAL_CREATED, step_id=ids.next("st"), actor=ACTOR_ENGINE,
                             source=goal.origin, at=stamp, goal_id=goal.id,
                             parent_goal_id=goal.parent_goal_id,
                             reason=goal.question,
                             payload={"kind": goal.kind, "need": goal.need,
                                      "phrase": goal.phrase})

        # THE FRAMER'S OWN GAP, transported. Lane A already found that no producer exists for this;
        # asking the capability table again would replace a considered refusal with an unknown-
        # instrument error, and the run would report our table's silence as the sensorium's.
        if goal.declared_gap:
            resolution = cap.Resolution(
                kind=cap.CAPABILITY_GAP, need=goal.need or goal.phrase,
                unmet=(goal.declared_gap,),
                why=f"the framer found no producer for {goal.phrase!r}: {goal.declared_gap}")
        # An act goes through `resolve_action` — which owns the three rules a need lookup would
        # erase; a term or an attention goes straight to `resolve_need`.
        elif goal.action:
            resolution = cap.resolve_action(
                ProposedAction.from_dict(goal.action), phrase=goal.phrase,
                locus=bool(goal.post_id and goal.region_id), evidence_returned=0,
                horizon_grounded=graph is not None, capabilities_up=capabilities_up)
        else:
            resolution = cap.resolve_need(
                goal.need, phrase=goal.phrase,
                locus=bool(goal.post_id and goal.region_id),
                evidence_returned=0, horizon_grounded=graph is not None,
                capabilities_up=capabilities_up)
        run = run.with_event(kind=EV_CAPABILITY_RESOLVED, step_id=ids.next("st"),
                             actor=ACTOR_ENGINE, source="capability_resolver", at=stamp,
                             goal_id=goal.id, parent_goal_id=goal.parent_goal_id,
                             reason=resolution.why, payload=resolution.to_dict())

        pending = _Pending(goal=goal, resolution=resolution)

        if resolution.kind == cap.CAPABILITY_GAP:
            gap = CapabilityGap(goal_id=goal.id, need=goal.need or goal.phrase,
                                unmet=resolution.unmet, why=resolution.why, at=stamp)
            run = run.with_gap(gap)
            run = run.with_event(kind=EV_CAPABILITY_GAP, step_id=ids.next("st"),
                                 actor=ACTOR_ENGINE, source="capability_resolver", at=stamp,
                                 goal_id=goal.id, parent_goal_id=goal.parent_goal_id,
                                 reason=resolution.why, payload=gap.to_dict())
            run = run.with_goal_status(goal.id, STATUS_CAPABILITY_GAP)
            pendings.append(pending)
            continue

        if resolution.kind == cap.REFUSED:
            run = run.with_goal_status(goal.id, STATUS_REFUSED)
            run = run.with_event(kind=EV_GOAL_UNRESOLVED, step_id=ids.next("st"),
                                 actor=ACTOR_ENGINE, source="capability_resolver", at=stamp,
                                 goal_id=goal.id, parent_goal_id=goal.parent_goal_id,
                                 reason=resolution.why,
                                 payload={"law": resolution.law,
                                          "unmet": list(resolution.unmet)})
            pendings.append(pending)
            continue

        if resolution.kind == cap.HUMAN_ACTION:
            run = run.with_goal_status(goal.id, STATUS_UNRESOLVED)
            run = run.with_event(kind=EV_GOAL_UNRESOLVED, step_id=ids.next("st"),
                                 actor=ACTOR_ENGINE, source="capability_resolver", at=stamp,
                                 goal_id=goal.id, parent_goal_id=goal.parent_goal_id,
                                 reason=resolution.why,
                                 payload={"awaiting": "curator",
                                          "unmet": list(resolution.unmet)})
            pendings.append(pending)
            continue

        if resolution.kind in (cap.DIRECTOR_PREPARATION, cap.COMPOSITE):
            actuator = resolution.actuators[0] if resolution.actuators else ""
            params: Dict[str, Any] = {}
            if goal.phrase:
                params["phrase"] = goal.phrase
            task = PreparationTask(
                id=ids.next("pt"), parent_goal_id=goal.id, title=actuator or goal.question,
                actuator=actuator, intention=goal.question, params=params,
                post_ids=tuple(p for p in (goal.post_id,) if p) or tuple(posts),
                status=STATUS_READY,
                detail=" | ".join(resolution.caveats) or resolution.why)
            run = run.with_goal(task)
            run = run.with_event(kind=EV_GOAL_CREATED, step_id=ids.next("st"),
                                 actor=ACTOR_ENGINE, source="capability_resolver", at=stamp,
                                 goal_id=task.id, parent_goal_id=goal.id,
                                 reason=task.detail,
                                 payload={"kind": task.kind, "actuator": task.actuator,
                                          "interpretive_naming": resolution.interpretive_naming})
            pending.task = task

        if resolution.kind in (cap.AGENT_MISSION, cap.COMPOSITE):
            # THE NEED DECIDES THE BODY. `organ_set` is a fallback for a resolution that named no
            # organ, never an override: dispatching a mission for an adjacency need with a
            # nestedness organ would return real marks of the wrong relation, and the goal would
            # read as unresolved for a reason that is an artefact of the caller's arguments.
            body = tuple(resolution.organs) or tuple(organ_set)
            situated = None
            if situated_goal_name:
                from backend.services.inquiry_engine.goals import SituatedGoal
                situated = SituatedGoal.of(situated_goal_name, goal_id=ids.next("sg"))
            mission = AgentMission(
                id=ids.next("am"), parent_goal_id=goal.id,
                title=f"{goal.phrase or goal.need} @ {region_id or goal.region_id}",
                post_id=goal.post_id or post_id, region_id=goal.region_id or region_id,
                organ_set=body, question=goal.question, budget=int(mission_budget),
                situated_goal=situated,
                # A composite mission is NOT ready: its organ reads a field the preparation has to
                # produce first, and the organ refuses without it.
                status=STATUS_PROPOSED if resolution.kind == cap.COMPOSITE else STATUS_READY,
                detail=" | ".join(resolution.caveats) or resolution.why)
            run = run.with_goal(mission)
            run = run.with_event(kind=EV_GOAL_CREATED, step_id=ids.next("st"),
                                 actor=ACTOR_ENGINE, source="capability_resolver", at=stamp,
                                 goal_id=mission.id, parent_goal_id=goal.id,
                                 reason=mission.detail,
                                 payload={"kind": mission.kind, "organ_set": list(body),
                                          "budget": mission.budget,
                                          "gated_on_preparation":
                                              resolution.kind == cap.COMPOSITE})
            pending.mission = mission

        run = run.with_goal_status(goal.id, STATUS_READY)
        pendings.append(pending)

    # ── rounds ───────────────────────────────────────────────────────────
    rounds = 0
    unavailable_only = True
    any_dispatch = False
    for round_index in range(max(1, int(max_rounds))):
        rounds = round_index + 1
        produced_this_round = 0

        for pending in pendings:
            task = pending.task
            if task is None or pending.task_done or task.status != STATUS_READY:
                continue
            pending.task_done = True
            any_dispatch = True
            run = run.with_goal_status(task.id, STATUS_ACTIVE)
            run = run.with_event(kind=EV_DIRECTOR_TASK_STARTED, step_id=ids.next("st"),
                                 actor=ACTOR_DIRECTOR, source="director_adapter", at=stamp,
                                 goal_id=task.id, parent_goal_id=pending.goal.id,
                                 reason=f"preparing {task.actuator or task.intention!r}",
                                 payload={"actuator": task.actuator,
                                          "params": dict(task.params)})
            result: PreparationResult = director.prepare(
                task, posts, run_id=run_id, inquiry_id=frame.inquiry_id,
                evidence_goal_id=pending.goal.id, phrase=pending.goal.phrase, now=stamp)
            items = _evidence_from_preparation(result, goal_id=pending.goal.id, ids=ids)
            pending.prep_produced = len(items)
            produced_this_round += len(items)
            if items:
                run = run.with_evidence(*items)
                run = run.with_event(kind=EV_EVIDENCE_RETURNED, step_id=ids.next("st"),
                                     actor=ACTOR_DIRECTOR, source="director_adapter", at=stamp,
                                     goal_id=pending.goal.id, parent_goal_id=pending.goal.id,
                                     reason=f"{len(items)} item(s) returned from "
                                            f"{task.actuator or task.intention!r}",
                                     payload={"evidence_ids": [i.id for i in items]})
            if result.ran:
                unavailable_only = False
                run = run.with_goal_status(task.id, STATUS_SATISFIED)
                run = run.with_event(kind=EV_DIRECTOR_TASK_COMPLETED, step_id=ids.next("st"),
                                     actor=ACTOR_DIRECTOR, source="director_adapter", at=stamp,
                                     goal_id=task.id, parent_goal_id=pending.goal.id,
                                     reason=result.detail,
                                     payload={"records": list(result.records),
                                              "suggestions": len(result.suggestions),
                                              "posts_unchanged": result.posts_unchanged})
            else:
                run = run.with_goal_status(task.id, STATUS_UNRESOLVED)
                run = run.with_event(kind=EV_DIRECTOR_TASK_REFUSED, step_id=ids.next("st"),
                                     actor=ACTOR_DIRECTOR, source="director_adapter", at=stamp,
                                     goal_id=task.id, parent_goal_id=pending.goal.id,
                                     reason=(result.detail or
                                             "no runner was registered for this actuator — the "
                                             "instrument exists and is not running, which is "
                                             "UNAVAILABLE and not a measured absence"),
                                     payload={"available": result.available,
                                              "refusals": list(result.refusals)})
            # THE REPLAN, and the only one: a composite mission becomes ready exactly when its
            # preparation actually returned something.
            if pending.mission is not None and pending.mission.status == STATUS_PROPOSED:
                if result.ran:
                    pending.mission = pending.mission.with_status(STATUS_READY)  # type: ignore
                    run = run.with_goal_status(pending.mission.id, STATUS_READY)
                else:
                    pending.mission = pending.mission.with_status(STATUS_UNRESOLVED)  # type: ignore
                    run = run.with_goal_status(pending.mission.id, STATUS_UNRESOLVED)
                    run = run.with_event(
                        kind=EV_GOAL_UNRESOLVED, step_id=ids.next("st"), actor=ACTOR_ENGINE,
                        source="replan", at=stamp, goal_id=pending.mission.id,
                        parent_goal_id=pending.goal.id,
                        reason=("the preparation this mission reads produced no field, and the "
                                "organ refuses without one. Dispatching anyway would surface as a "
                                "refusal mid-mission and look like a quiet locus."),
                        payload={"gated_on": task.id})

        for pending in pendings:
            mission = pending.mission
            if mission is None or pending.mission_done or mission.status != STATUS_READY:
                continue
            pending.mission_done = True
            any_dispatch = True
            run = run.with_goal_status(mission.id, STATUS_ACTIVE)
            run = run.with_event(kind=EV_MISSION_DISPATCHED, step_id=ids.next("st"),
                                 actor=ACTOR_ENGINE, source="simulator_adapter", at=stamp,
                                 goal_id=mission.id, parent_goal_id=pending.goal.id,
                                 reason=mission.question,
                                 payload={"post_id": mission.post_id,
                                          "region_id": mission.region_id,
                                          "organ_set": list(mission.organ_set),
                                          "budget": mission.budget})
            outcome: MissionResult = simulator.dispatch(
                mission, posts, run_id=run_id, inquiry_id=frame.inquiry_id,
                evidence_goal_id=pending.goal.id, now=stamp, graph=graph,
                proposed_marks=proposed_marks, image=image, depth_field=depth_field)
            if outcome.dispatched:
                unavailable_only = False
                run = run.with_event(kind=EV_AGENT_PERCEIVED, step_id=ids.next("st"),
                                     actor=ACTOR_AGENT, source=mission.id, at=stamp,
                                     goal_id=mission.id, parent_goal_id=pending.goal.id,
                                     reason=(f"{len(outcome.perceptions)} reading(s) from "
                                             f"{outcome.memory_summary.get('node_id')}"),
                                     payload={"perceptions": len(outcome.perceptions),
                                              "trajectory": list(outcome.trajectory),
                                              "memory_summary": dict(outcome.memory_summary),
                                              "horizon": len(outcome.horizon),
                                              "posts_unchanged": outcome.posts_unchanged})
            for refusal in outcome.refusals:
                run = run.with_event(kind=EV_AGENT_REFUSED, step_id=ids.next("st"),
                                     actor=ACTOR_AGENT, source=mission.id, at=stamp,
                                     goal_id=mission.id, parent_goal_id=pending.goal.id,
                                     reason=str(refusal.get("detail") or refusal.get("reason")),
                                     payload=dict(refusal))
            items = _evidence_from_mission(outcome, goal_id=pending.goal.id, ids=ids)
            produced_this_round += len([i for i in items if i.kind != "refusal"])
            if items:
                run = run.with_evidence(*items)
                run = run.with_event(kind=EV_EVIDENCE_RETURNED, step_id=ids.next("st"),
                                     actor=ACTOR_AGENT, source=mission.id, at=stamp,
                                     goal_id=pending.goal.id, parent_goal_id=pending.goal.id,
                                     reason=f"{len(items)} item(s) returned from a body at "
                                            f"{outcome.memory_summary.get('node_id')}",
                                     payload={"evidence_ids": [i.id for i in items]})
            run = run.with_goal_status(
                mission.id, STATUS_SATISFIED if outcome.dispatched else STATUS_UNRESOLVED)
            if outcome.situated_outcome:
                run = run.with_event(
                    kind=EV_GOAL_PARTIAL if outcome.situated_outcome.get("outcome") != "satisfied"
                    else EV_GOAL_SATISFIED,
                    step_id=ids.next("st"), actor=ACTOR_AGENT, source=mission.id, at=stamp,
                    goal_id=mission.situated_goal.id if mission.situated_goal else mission.id,
                    parent_goal_id=mission.id,
                    reason=str(outcome.situated_outcome.get("detail") or ""),
                    payload=dict(outcome.situated_outcome))

        # A round that opened nothing new ends the run. The ceiling below is a backstop, not the
        # mechanism — see the module note.
        if produced_this_round == 0:
            break
        if not any(p.mission is not None and not p.mission_done
                   and p.mission.status == STATUS_READY for p in pendings):
            break

    # ── evaluate ─────────────────────────────────────────────────────────
    verdicts: List[ev.GoalVerdict] = []
    for pending in pendings:
        goal = pending.goal
        gap = (pending.resolution.unmet[0]
               if pending.resolution.kind == cap.CAPABILITY_GAP and pending.resolution.unmet
               else "")
        verdict = ev.evaluate(goal, run.evidence_for(goal.id), gap=gap)
        ev.assert_not_satisfied_without_evidence(verdict)
        verdicts.append(verdict)

        # A goal the resolver already refused or handed to a curator keeps that status: the verdict
        # describes its clauses, and overwriting `refused` with `unresolved` would lose the reason.
        current = run.goal(goal.id)
        if current is not None and current.status in (STATUS_REFUSED, STATUS_CAPABILITY_GAP,
                                                      STATUS_UNRESOLVED):
            status = current.status
        else:
            status = verdict.status
            run = run.with_goal_status(goal.id, status)

        kind = (EV_GOAL_SATISFIED if status == STATUS_SATISFIED else
                EV_GOAL_PARTIAL if status == STATUS_PARTIALLY_SATISFIED else
                EV_GOAL_UNRESOLVED)
        run = run.with_event(kind=kind, step_id=ids.next("st"), actor=ACTOR_ENGINE,
                             source="evaluator", at=stamp, goal_id=goal.id,
                             parent_goal_id=goal.parent_goal_id, reason=verdict.why,
                             payload=verdict.to_dict())

    outcome_name, stop_reason = _conclude(run, verdicts, pendings,
                                          any_dispatch=any_dispatch,
                                          unavailable_only=unavailable_only,
                                          rounds=rounds, max_rounds=max_rounds)
    run = run.stopped(outcome=outcome_name, stop_reason=stop_reason, at=stamp, rounds=rounds)
    run = run.with_event(kind=EV_RUN_STOPPED, step_id=ids.next("st"), actor=ACTOR_ENGINE,
                         source="engine", at=stamp, goal_id=inquiry.id,
                         reason=stop_reason,
                         payload={"outcome": outcome_name, "rounds": rounds,
                                  "gaps": [g.to_dict() for g in run.gaps],
                                  "verdicts": [v.to_dict() for v in verdicts]})
    run = run.with_goal_status(
        inquiry.id,
        STATUS_SATISFIED if outcome_name == OUTCOME_ANSWERABLE else
        STATUS_PARTIALLY_SATISFIED if outcome_name == OUTCOME_PARTIALLY_ANSWERABLE else
        STATUS_UNRESOLVED if outcome_name == OUTCOME_AWAITING_HUMAN else STATUS_EXHAUSTED)
    return run


# ── evidence construction ────────────────────────────────────────────────────

def _evidence_from_mission(result: MissionResult, *, goal_id: str, ids: _Ids) -> List[Evidence]:
    """Marks and refusals, as evidence. The status is COPIED off each mark by `Evidence.of_mark`.

    Observations are deliberately NOT emitted as separate evidence: an observation is the LEDGER
    view of the same organ mark, and counting both would double every measurement. They ride on the
    mission event instead, where a reader can put the private and public readings side by side.
    """
    out: List[Evidence] = []
    for mark in result.marks:
        out.append(Evidence.of_mark(
            mark, evidence_id=ids.next("evd"), goal_id=goal_id,
            provenance={**dict(result.provenance), "returned_by": "simulator_adapter"}))
    for refusal in result.refusals:
        out.append(Evidence.of_refusal(
            refusal, evidence_id=ids.next("evd"), goal_id=goal_id,
            provenance={**dict(result.provenance), "returned_by": "simulator_adapter"}))
    return out


def _evidence_from_preparation(result: PreparationResult, *, goal_id: str,
                               ids: _Ids) -> List[Evidence]:
    """Suggestions, as evidence, each carrying the status the descriptor states about ITSELF.

    A suggestion with no `epistemic_status` is skipped rather than given one. The Director's own
    `epistemics.guard` is what stamps a descriptor, and an engine that supplied a missing status
    would be doing the stamping from the wrong side of the wall.
    """
    out: List[Evidence] = []
    for suggestion in result.suggestions:
        status = str(suggestion.get("epistemic_status") or "")
        if not status:
            continue
        out.append(Evidence.of_production(
            suggestion, evidence_id=ids.next("evd"), goal_id=goal_id,
            epistemic_status=status,
            provenance={**dict(result.provenance), "returned_by": "director_adapter"}))
    return out


# ── stopping ─────────────────────────────────────────────────────────────────

def _conclude(run: InquiryRun, verdicts: Sequence[ev.GoalVerdict],
              pendings: Sequence[_Pending], *, any_dispatch: bool,
              unavailable_only: bool, rounds: int, max_rounds: int) -> Tuple[str, str]:
    """The run's outcome and its explicit stop reason. Six reasons, none of them 'it finished'."""
    settled = [v for v in verdicts if v.status in (STATUS_SATISFIED, STATUS_PARTIALLY_SATISFIED)]
    gaps = bool(run.gaps)
    awaiting = any(v.awaiting_human for v in verdicts) or any(
        p.resolution.kind == cap.HUMAN_ACTION for p in pendings)
    open_measurable = any(
        v.status in (STATUS_UNRESOLVED, STATUS_PARTIALLY_SATISFIED)
        and any(c.demands in (CLAUSE_MEASURED, CLAUSE_SOURCED) and not c.met for c in v.clauses)
        for v in verdicts)

    if any_dispatch and unavailable_only and not settled:
        return OUTCOME_EXHAUSTED, STOP_EXECUTION_UNAVAILABLE

    if settled and not (open_measurable or gaps or awaiting):
        return OUTCOME_ANSWERABLE, STOP_SATISFIED
    if settled:
        reason = (STOP_CAPABILITY_GAP if gaps else
                  STOP_AWAITING_HUMAN if awaiting and not open_measurable else
                  STOP_BUDGET_EXHAUSTED if rounds >= max_rounds and open_measurable else
                  STOP_NO_NEW_EVIDENCE)
        return OUTCOME_PARTIALLY_ANSWERABLE, reason
    if gaps:
        return OUTCOME_EXHAUSTED, STOP_CAPABILITY_GAP
    if awaiting:
        return OUTCOME_AWAITING_HUMAN, STOP_AWAITING_HUMAN
    return OUTCOME_EXHAUSTED, STOP_NO_NEW_EVIDENCE


__all__ = ["DEFAULT_MAX_ROUNDS", "ORIGIN_ACTION", "ORIGIN_TERM", "ORIGIN_ATTENTION",
           "ORIGIN_DEMAND", "derive", "run_inquiry"]
