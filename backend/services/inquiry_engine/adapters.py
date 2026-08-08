"""
HARNESS-001B §6 — the two adapters, and the one thing neither may do.

The directive is explicit that this lane must NOT merge implementations. The Director keeps its
planner, its resolver and its executor; `backend/services/agents/` keeps its organs, its movement
and its meetings. These two classes are the typed handoffs between them, and the honest measure of
whether they are adapters or a second engine is: **is there a decision here that already belongs to
something else?** Every one is delegated —

    what a step may run at all     `director.plan.resolve`
    what happens when it runs      `director.execution.execute`
    what an organ measures         `agents.organs.invoke`, through `agents.situated_agent.perceive`
    whether an agent may walk      `agents.movement.horizon` / `.step`
    whether an aim was met         `agents.goal.satisfying_marks`

## The wall between them

**A Director proposal may never enter an agent's percept field.** The Director's world is global and
its suggestions are quarantined descriptors; an agent's world is what its own organs measured from
where it stands. `assert_organ_authored` is the physical form of that rule: the only marks the
simulator adapter will pass to `movement.horizon` are ones whose provenance names an organ, so a
Director suggestion cannot open a crossing the kernel never grounded, and it cannot arrive in a
percept field wearing the first person.

The reverse is guarded by construction: `AgentMission` carries a locus, a body, a question and a
budget, and has no field an evidence payload could travel in.

## Both are replaceable by fakes

`FakeDirectorAdapter` and `FakeSimulatorAdapter` implement the same two methods and return the same
result types. `test_inquiry_engine_boundaries.py` runs the engine on both and asserts the semantics
do not move — which is what makes the fast tests meaningful rather than a second implementation
being tested.

## Suggestions only

Neither adapter commits anything. `run_agent`'s discipline is kept: posts are fingerprinted before
and after every dispatch, and `posts_unchanged` is a CHECKED field on the result, not a claim in a
docstring.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from backend.services.agents import goal as agent_goal
from backend.services.agents import meeting as meeting_mod
from backend.services.agents import movement as movement_mod
from backend.services.agents import organs as agent_organs
from backend.services.agents import situated_agent as sa
from backend.services.director import execution as director_execution
from backend.services.director.memory import WorkingMemory, build_memory
from backend.services.director.plan import Plan, Step, resolve as resolve_plan
from backend.services.director.planner import Director
from backend.services.inquiry_engine.goals import AgentMission, PreparationTask
from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint

PLANNER_NAME = "inquiry_engine"


class ProposalNotAPerception(Exception):
    """A Director-authored descriptor was offered to a body as if an organ had measured it.

    The single most consequential fabrication available at this seam, and the reason it is an
    exception rather than a filter: a silently dropped proposal would leave the caller believing the
    agent had been given evidence it never saw, and the run would report a smaller horizon with no
    explanation.
    """


def assert_organ_authored(marks: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Every mark here must name an ORGAN as its producer. The wall, checked rather than trusted.

    `organs.resolve` is the live table: a mark whose producer is a pure-python organ or a real organ
    role passes; a mark produced by `concept_segment`, by a planner, or by nothing at all does not.
    """
    out: List[Dict[str, Any]] = []
    for mark in marks or ():
        producer = str((mark.get("provenance") or {}).get("producer") or "")
        binding = agent_organs.resolve(producer)
        if binding.resolution == agent_organs.UNKNOWN:
            raise ProposalNotAPerception(
                f"mark {mark.get('id')!r} names producer {producer!r}, which is not an organ: "
                f"{binding.detail}. A Director proposal handed to a body as its own perception "
                f"would give an agent a first-person claim nothing it owns ever measured — and "
                f"every sentence built on it would parse.")
        out.append(dict(mark))
    return out


# ── Director adapter ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PreparationResult:
    """What a `PreparationTask` came to. Records, suggestions, refusals and availability — four
    fields because collapsing any pair loses a distinction `execution.py` already keeps."""
    task_id: str
    goal_id: str
    ran: bool
    available: bool
    records: Tuple[Dict[str, Any], ...] = ()
    suggestions: Tuple[Dict[str, Any], ...] = ()
    refusals: Tuple[Dict[str, Any], ...] = ()
    provenance: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    posts_unchanged: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "goal_id": self.goal_id, "ran": self.ran,
                "available": self.available, "records": [dict(r) for r in self.records],
                "suggestions": [dict(s) for s in self.suggestions],
                "refusals": [dict(r) for r in self.refusals],
                "provenance": dict(self.provenance), "detail": self.detail,
                "posts_unchanged": self.posts_unchanged}


class PreparesEvidence(Protocol):
    """The Director seam, as one method. A fake implements exactly this."""

    def prepare(self, task: PreparationTask, posts: Mapping[str, Mapping[str, Any]], *,
                run_id: str, inquiry_id: str, evidence_goal_id: str,
                phrase: str = "", now: str = "") -> PreparationResult:
        ...


class DirectorAdapter:
    """`PreparationTask` → the Director's own planner/resolver/executor, and back.

    NO NEW PLANNER. Two entry paths, both ending at the same gate:

      task.actuator   the resolver named an instrument. One `Step` goes through `plan.resolve` —
                      the same function every planner's output passes through, so a task naming a
                      deleted actuator is refused `unknown_actuator` and one whose inputs do not
                      exist is refused `missing_input`, by the existing code.
      task.intention  no instrument was named. `Director.plan` decides, keyword table and all.

    `registry` is the actuator runner map. Handed NONE, `execute` records `no runner registered for
    '<actuator>'` as UNAVAILABLE — an honest empty rather than a fake green, which is exactly what
    the local-proof requirement asks for and why this adapter does not default to stubs.
    """

    def __init__(self, *, director: Optional[Director] = None,
                 registry: Optional[Mapping[str, Any]] = None):
        self.director = director or Director()
        self.registry: Dict[str, Any] = dict(registry or {})

    # -- memory ----------------------------------------------------------
    def _memory(self, task: PreparationTask, posts: Mapping[str, Mapping[str, Any]],
                phrase: str) -> WorkingMemory:
        """The packet the task runs against, hydrated from what the posts ACTUALLY carry.

        Annotation-independent in the same sense `run_surface` means it: a post with no regions
        yields a packet with an image and nothing else, which is a full and legitimate starting
        point because the actuators produce the evidence.
        """
        post_id = (task.post_ids[0] if task.post_ids else
                   (next(iter(posts)) if posts else ""))
        post = dict(posts.get(post_id) or {})
        regions = [str(r.get("id") or "") for r in (post.get("region_annotations") or ())
                   if isinstance(r, Mapping)]
        marks = [str(m.get("id") or "") for m in (post.get("visual_marks") or ())
                 if isinstance(m, Mapping)]
        return build_memory(image_ref=str(post.get("photo_url") or post_id or "image"),
                            post_id=post_id or None,
                            region_ids=[r for r in regions if r],
                            mark_ids=[m for m in marks if m],
                            phrase=phrase or task.params.get("phrase") or None)

    def prepare(self, task: PreparationTask, posts: Mapping[str, Mapping[str, Any]], *,
                run_id: str, inquiry_id: str, evidence_goal_id: str,
                phrase: str = "", now: str = "") -> PreparationResult:
        before = posts_fingerprint(posts)
        memory = self._memory(task, posts, phrase)
        provenance = {"run_id": run_id, "inquiry_id": inquiry_id,
                      "evidence_goal_id": evidence_goal_id, "task_id": task.id,
                      "parent_goal_id": task.parent_goal_id, "at": now}

        if task.actuator:
            step = Step(actuator=task.actuator, params=dict(task.params), id=task.id,
                        note=task.detail)
            plan: Plan = resolve_plan([step], memory, intention=task.title or task.actuator,
                                      planner=PLANNER_NAME)
        else:
            plan = self.director.plan(task.intention, memory)

        chain = director_execution.execute(plan, memory, self.registry,
                                           chain_id=f"{run_id}:{task.id}")
        lineage = [r.to_dict() for r in chain.provenance.lineage]
        refusals = [dict(r) for r in chain.provenance.refused]
        for row in lineage:
            if row.get("status") != director_execution.OK:
                refusals.append({"step_id": row.get("step_id"), "actuator": row.get("actuator"),
                                 "reason": row.get("status"),
                                 "detail": row.get("detail") or row.get("skip_reason") or ""})

        suggestions: List[Dict[str, Any]] = []
        for result in chain.results:
            payload = dict(result.payload or {})
            found = payload.get("suggestions")
            if isinstance(found, (list, tuple)):
                suggestions.extend(dict(s) for s in found if isinstance(s, Mapping))
            elif payload:
                suggestions.append(payload)

        ran = any(r.get("status") in (director_execution.OK, director_execution.EMPTY)
                  for r in lineage)
        available = any(r.get("status") != director_execution.UNAVAILABLE for r in lineage) \
            if lineage else False

        # SUGGESTIONS ONLY, checked. Nothing above writes; this proves it rather than promising it.
        unchanged = True
        try:
            assert_posts_unchanged(before, posts_fingerprint(posts))
        except Exception:                                       # noqa: BLE001
            unchanged = False

        detail = (f"{len([r for r in lineage if r.get('status') == director_execution.OK])} of "
                  f"{len(lineage) + len(plan.refused)} step(s) ran; "
                  f"{len(plan.refused)} refused at plan time")
        return PreparationResult(
            task_id=task.id, goal_id=evidence_goal_id, ran=ran, available=available,
            records=tuple(lineage), suggestions=tuple(suggestions), refusals=tuple(refusals),
            provenance=provenance, detail=detail, posts_unchanged=unchanged)


class FakeDirectorAdapter:
    """Canned preparation. Same shape, no planner, no executor — the fast-test stand-in the
    directive explicitly allows for the control rehearsal's Director half."""

    def __init__(self, *, records: Sequence[Mapping[str, Any]] = (),
                 suggestions: Sequence[Mapping[str, Any]] = (),
                 refusals: Sequence[Mapping[str, Any]] = (),
                 available: bool = True, ran: bool = True):
        self.records = tuple(dict(r) for r in records)
        self.suggestions = tuple(dict(s) for s in suggestions)
        self.refusals = tuple(dict(r) for r in refusals)
        self.available = available
        self.ran = ran
        self.calls: List[PreparationTask] = []

    def prepare(self, task: PreparationTask, posts: Mapping[str, Mapping[str, Any]], *,
                run_id: str, inquiry_id: str, evidence_goal_id: str,
                phrase: str = "", now: str = "") -> PreparationResult:
        self.calls.append(task)
        return PreparationResult(
            task_id=task.id, goal_id=evidence_goal_id, ran=self.ran, available=self.available,
            records=self.records, suggestions=self.suggestions, refusals=self.refusals,
            provenance={"run_id": run_id, "inquiry_id": inquiry_id,
                        "evidence_goal_id": evidence_goal_id, "task_id": task.id,
                        "parent_goal_id": task.parent_goal_id, "at": now, "adapter": "fake"},
            detail="fake director adapter", posts_unchanged=True)


# ── simulator adapter ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MissionResult:
    """What an `AgentMission` came to, with every existing status intact.

    `refusals` carries `OrganRefusal`, `Hearsay` and `MarkMisstated` as rows rather than letting
    them become an empty percept field. "The organ refused" and "the organ measured nothing" are
    different facts about a locus, and a mission that reported the first as the second would make a
    body it could not use look like a quiet place.
    """
    mission_id: str
    goal_id: str
    dispatched: bool
    perceptions: Tuple[Dict[str, Any], ...] = ()
    observations: Tuple[Dict[str, Any], ...] = ()
    marks: Tuple[Dict[str, Any], ...] = ()
    trajectory: Tuple[Dict[str, Any], ...] = ()
    horizon: Tuple[Dict[str, Any], ...] = ()
    memory_summary: Dict[str, Any] = field(default_factory=dict)
    hypotheses: Tuple[Dict[str, Any], ...] = ()
    refusals: Tuple[Dict[str, Any], ...] = ()
    situated_outcome: Optional[Dict[str, Any]] = None
    provenance: Dict[str, Any] = field(default_factory=dict)
    posts_unchanged: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"mission_id": self.mission_id, "goal_id": self.goal_id,
                "dispatched": self.dispatched,
                "perceptions": [dict(p) for p in self.perceptions],
                "observations": [dict(o) for o in self.observations],
                "marks": [dict(m) for m in self.marks],
                "trajectory": [dict(t) for t in self.trajectory],
                "horizon": [dict(h) for h in self.horizon],
                "memory_summary": dict(self.memory_summary),
                "hypotheses": [dict(h) for h in self.hypotheses],
                "refusals": [dict(r) for r in self.refusals],
                "situated_outcome": dict(self.situated_outcome) if self.situated_outcome else None,
                "provenance": dict(self.provenance), "posts_unchanged": self.posts_unchanged}


class InvestigatesLocally(Protocol):
    def dispatch(self, mission: AgentMission, posts: Mapping[str, Mapping[str, Any]], *,
                 run_id: str, inquiry_id: str, evidence_goal_id: str, now: str = "",
                 graph: Optional[Mapping[str, Any]] = None,
                 proposed_marks: Sequence[Mapping[str, Any]] = (),
                 image: Any = None, depth_field: Any = None) -> MissionResult:
        ...


class SimulatorAdapter:
    """`AgentMission` → `inhabit → perceive → remember → report`, and back.

    Uses the CURRENT APIs and adds nothing to `backend/services/agents/`: no LLM import reaches that
    package because nothing here reaches into it except through its declared functions.

    Movement and meeting happen only when a GRAPH is handed in and the mission carries a budget —
    "world actions are available only after a locus and a grounded horizon exist", enforced by
    there being nothing to walk otherwise.

    A private-memory SUMMARY comes back rather than the memory itself, and the distinction is
    deliberate: `remember()` is the agent's first-person episodic record and is private in the sense
    of REACH. The summary says how many entries and of what kinds, which is what a parent inquiry
    needs to know a body was somewhere, without the inquiry acquiring the body's interior.
    """

    def dispatch(self, mission: AgentMission, posts: Mapping[str, Mapping[str, Any]], *,
                 run_id: str, inquiry_id: str, evidence_goal_id: str, now: str = "",
                 graph: Optional[Mapping[str, Any]] = None,
                 proposed_marks: Sequence[Mapping[str, Any]] = (),
                 image: Any = None, depth_field: Any = None) -> MissionResult:
        before = posts_fingerprint(posts)
        provenance = {"run_id": run_id, "inquiry_id": inquiry_id,
                      "evidence_goal_id": evidence_goal_id, "mission_id": mission.id,
                      "parent_goal_id": mission.parent_goal_id, "at": now}
        refusals: List[Dict[str, Any]] = []

        post = posts.get(mission.post_id)
        if post is None:
            return MissionResult(
                mission_id=mission.id, goal_id=evidence_goal_id, dispatched=False,
                refusals=({"reason": "no_post", "detail":
                           f"no post {mission.post_id!r} to perceive — an agent cannot stand where "
                           f"there is nothing to stand on"},),
                provenance=provenance, posts_unchanged=True)

        # THE WALL. A Director proposal may not become an agent's own perception.
        vetted = assert_organ_authored(proposed_marks)

        try:
            agent = sa.inhabit(agent_id=f"{mission.id}", post_id=mission.post_id,
                               region_id=mission.region_id, organ_set=mission.organ_set,
                               temperament=mission.temperament)
        except agent_organs.OrganRefusal as exc:
            return MissionResult(
                mission_id=mission.id, goal_id=evidence_goal_id, dispatched=False,
                refusals=({"reason": "organ_refusal", "detail": str(exc)},),
                provenance=provenance, posts_unchanged=True)

        situated_outcome: Optional[Dict[str, Any]] = None
        try:
            if mission.situated_goal and graph is not None:
                # The aim is pursued by `agents.goal.pursue`, which perceives, checks, chooses and
                # steps. This adapter does not re-implement any of that — it hands over the bound.
                situated_outcome = agent_goal.pursue(
                    agent, graph, posts, goal_name=mission.situated_goal.name,
                    marks=vetted, bound=max(0, int(mission.budget)), now=now)
            else:
                sa.perceive(agent, post, now=now, image=image, depth_field=depth_field)
        except agent_organs.OrganRefusal as exc:
            refusals.append({"reason": "organ_refusal", "detail": str(exc)})
        except sa.Hearsay as exc:
            refusals.append({"reason": "hearsay", "detail": str(exc)})
        except agent_goal.UnknownGoal as exc:
            refusals.append({"reason": "unknown_goal", "detail": str(exc)})

        memory_rows = sa.remember(agent, now=now)
        observations: Tuple[Dict[str, Any], ...] = ()
        marks: Tuple[Dict[str, Any], ...] = ()
        try:
            observations = tuple(sa.report(agent, now=now))
            marks = tuple(sa.proposed_marks(agent))
        except sa.MarkMisstated as exc:
            # Kept as a refusal with its own reason. A mark claiming a kind its basis does not
            # support must not be quietly excluded from the report — that is how the WAVE2.5
            # pathology survived the first time.
            refusals.append({"reason": "mark_misstated", "detail": str(exc)})

        horizon: Tuple[Dict[str, Any], ...] = ()
        if graph is not None:
            horizon = tuple(r.as_dict() for r in movement_mod.horizon(
                agent, graph, posts, proposed_marks=vetted))

        unchanged = True
        try:
            assert_posts_unchanged(before, posts_fingerprint(posts))
        except Exception:                                       # noqa: BLE001
            unchanged = False

        return MissionResult(
            mission_id=mission.id, goal_id=evidence_goal_id, dispatched=True,
            perceptions=tuple(p.as_dict() for p in agent.percept_field),
            observations=observations, marks=marks,
            trajectory=tuple(dict(t) for t in agent.trajectory),
            horizon=horizon,
            # The SUMMARY, not the memory. Private is a claim about reach.
            memory_summary={"entries": len(memory_rows),
                            "organs": sorted({str(r.get("organ") or "") for r in memory_rows}),
                            "statuses": sorted({str(r.get("epistemic_status") or "")
                                                for r in memory_rows}),
                            "node_id": agent.locus.node_id},
            hypotheses=(), refusals=tuple(refusals), situated_outcome=situated_outcome,
            provenance=provenance, posts_unchanged=unchanged)

    # -- meeting, kept separate because it needs two bodies ---------------
    def meet(self, alpha_result: MissionResult, beta_result: MissionResult) -> Dict[str, Any]:
        """Two missions that travelled → what `agents.meeting` makes of them.

        Deliberately NOT part of `dispatch`: a meeting is a fact about two journeys, and staging one
        by dispatching two agents to the same locus is the failure `meeting.assert_travelled`
        already refuses. This lane exposes the seam and performs no meeting it did not earn.
        """
        return {"available": False,
                "detail": ("a meeting requires two agents that each TRAVELLED to a shared "
                           "rendezvous on measured crossings. This lane dispatches missions "
                           "independently and does not stage one; the seam is "
                           f"`{meeting_mod.__name__}.meet(alpha, beta)` and it is the "
                           "society lane's to drive."),
                "alpha": alpha_result.mission_id, "beta": beta_result.mission_id}


class FakeSimulatorAdapter:
    """Canned mission results. Same shape, no organs — used to prove the engine's semantics do not
    depend on which adapter is behind the seam."""

    def __init__(self, *, perceptions: Sequence[Mapping[str, Any]] = (),
                 marks: Sequence[Mapping[str, Any]] = (),
                 observations: Sequence[Mapping[str, Any]] = (),
                 refusals: Sequence[Mapping[str, Any]] = (),
                 dispatched: bool = True):
        self.perceptions = tuple(dict(p) for p in perceptions)
        self.marks = tuple(dict(m) for m in marks)
        self.observations = tuple(dict(o) for o in observations)
        self.refusals = tuple(dict(r) for r in refusals)
        self.dispatched = dispatched
        self.calls: List[AgentMission] = []

    def dispatch(self, mission: AgentMission, posts: Mapping[str, Mapping[str, Any]], *,
                 run_id: str, inquiry_id: str, evidence_goal_id: str, now: str = "",
                 graph: Optional[Mapping[str, Any]] = None,
                 proposed_marks: Sequence[Mapping[str, Any]] = (),
                 image: Any = None, depth_field: Any = None) -> MissionResult:
        self.calls.append(mission)
        assert_organ_authored(proposed_marks)     # the wall holds for fakes too
        return MissionResult(
            mission_id=mission.id, goal_id=evidence_goal_id, dispatched=self.dispatched,
            perceptions=self.perceptions, observations=self.observations, marks=self.marks,
            refusals=self.refusals,
            memory_summary={"entries": len(self.perceptions), "organs": list(mission.organ_set),
                            "statuses": [], "node_id": f"vm_{mission.post_id}:{mission.region_id}"},
            provenance={"run_id": run_id, "inquiry_id": inquiry_id,
                        "evidence_goal_id": evidence_goal_id, "mission_id": mission.id,
                        "parent_goal_id": mission.parent_goal_id, "at": now, "adapter": "fake"},
            posts_unchanged=True)


__all__ = ["PLANNER_NAME", "ProposalNotAPerception", "assert_organ_authored",
           "PreparationResult", "PreparesEvidence", "DirectorAdapter", "FakeDirectorAdapter",
           "MissionResult", "InvestigatesLocally", "SimulatorAdapter", "FakeSimulatorAdapter"]
