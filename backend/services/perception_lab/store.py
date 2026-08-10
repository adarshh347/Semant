"""
PERCEPTUAL-ORGANS-002 Lane D — the lab's own memory, and the door it deliberately does not have.

THE STORE IS AN INTERFACE WITH FIVE RECORD TYPES ON IT. Sessions, plans, runs, artifacts, reviews.
There is no method here that writes a Post, a Region, a Mark, a Ground or a Percept, and that is
the enforcement: "lab execution is non-mutating" is not a rule the conductor obeys, it is a
sentence about a conductor that has been handed nothing it could mutate with. The orchestration
suite's import firewall proves the other half — that nothing reachable from the conductor imports
a module which could.

WHY AN INTERFACE AND NOT A DATABASE. Lane F owns persistence wiring; Lane D owns the shape. An
in-memory implementation ships here so the conductor is testable, and because a lab that can be
run entirely in a process is a lab whose mutation tests are fast enough that people run them.

WHY EVERY GET AND PUT COPIES. `InMemoryLabStore` deep-copies on the way in AND on the way out. It
would be cheaper to hand back the object. It would also mean a caller that mutated an artifact it
had read — to try a correction, to build a response — would have silently rewritten the ledger,
and the ledger's whole job is to be the thing that did not change. Copying makes a value a value,
which is what a real database would give you anyway; discovering that difference at the moment the
Mongo wiring lands is discovering it in the worst place.

PURE. No database, no network, no model, no clock.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Protocol, Tuple, TypeVar, runtime_checkable

from backend.schemas.perception_lab import (LabPlan, LabReview, LabRun, LabSession,
                                            PerceptualArtifact)

R = TypeVar("R")


class StoreError(RuntimeError):
    """A record that was asked for and is not there, where absence is a defect rather than an
    answer. Reading a missing artifact during a replay is a REFUSAL, not this."""


@runtime_checkable
class LabStore(Protocol):
    """Everything the conductor may remember. Note what is not on it.

    Lane F implements this against real collections. The method list is the contract: an
    implementation that added `put_region` would be adding a door to this interface, and the
    conductor would still not be able to walk through it, because the conductor calls these
    fifteen methods and no others.
    """

    # -- sessions --
    def put_session(self, session: LabSession) -> LabSession: ...
    def get_session(self, session_id: str) -> Optional[LabSession]: ...
    def sessions(self) -> Tuple[LabSession, ...]: ...

    # -- plans --
    def put_plan(self, plan: LabPlan) -> LabPlan: ...
    def get_plan(self, plan_id: str) -> Optional[LabPlan]: ...
    def plans_for_session(self, session_id: str) -> Tuple[LabPlan, ...]: ...

    # -- runs --
    def put_run(self, run: LabRun) -> LabRun: ...
    def get_run(self, run_id: str) -> Optional[LabRun]: ...
    def runs_for_session(self, session_id: str) -> Tuple[LabRun, ...]: ...

    # -- artifacts --
    def put_artifact(self, artifact: PerceptualArtifact) -> PerceptualArtifact: ...
    def get_artifact(self, artifact_id: str) -> Optional[PerceptualArtifact]: ...
    def artifacts_for_run(self, run_id: str) -> Tuple[PerceptualArtifact, ...]: ...

    # -- reviews --
    def put_review(self, review: LabReview) -> LabReview: ...
    def get_review(self, review_id: str) -> Optional[LabReview]: ...
    def reviews_for_artifact(self, artifact_id: str) -> Tuple[LabReview, ...]: ...


def _copy(record: R) -> R:
    return record.model_copy(deep=True)                       # type: ignore[attr-defined]


class InMemoryLabStore:
    """The reference implementation. Values in, values out, insertion order preserved.

    ORDER IS PART OF THE CONTRACT. `runs_for_session` returns runs in the order they were put,
    because a lab history read out of order is a history in which a replay can appear to precede
    the run it replays. A dict preserving insertion order is doing real work here, not an
    incidental property being relied on.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, LabSession] = {}
        self._plans: Dict[str, LabPlan] = {}
        self._runs: Dict[str, LabRun] = {}
        self._artifacts: Dict[str, PerceptualArtifact] = {}
        self._reviews: Dict[str, LabReview] = {}

    # -- sessions --

    def put_session(self, session: LabSession) -> LabSession:
        self._sessions[session.session_id] = _copy(session)
        return session

    def get_session(self, session_id: str) -> Optional[LabSession]:
        found = self._sessions.get(session_id)
        return _copy(found) if found is not None else None

    def sessions(self) -> Tuple[LabSession, ...]:
        return tuple(_copy(s) for s in self._sessions.values())

    # -- plans --

    def put_plan(self, plan: LabPlan) -> LabPlan:
        self._plans[plan.plan_id] = _copy(plan)
        return plan

    def get_plan(self, plan_id: str) -> Optional[LabPlan]:
        found = self._plans.get(plan_id)
        return _copy(found) if found is not None else None

    def plans_for_session(self, session_id: str) -> Tuple[LabPlan, ...]:
        return tuple(_copy(p) for p in self._plans.values() if p.session_id == session_id)

    # -- runs --

    def put_run(self, run: LabRun) -> LabRun:
        self._runs[run.run_id] = _copy(run)
        return run

    def get_run(self, run_id: str) -> Optional[LabRun]:
        found = self._runs.get(run_id)
        return _copy(found) if found is not None else None

    def runs_for_session(self, session_id: str) -> Tuple[LabRun, ...]:
        return tuple(_copy(r) for r in self._runs.values() if r.session_id == session_id)

    # -- artifacts --

    def put_artifact(self, artifact: PerceptualArtifact) -> PerceptualArtifact:
        self._artifacts[artifact.identity.artifact_id] = _copy(artifact)
        return artifact

    def get_artifact(self, artifact_id: str) -> Optional[PerceptualArtifact]:
        found = self._artifacts.get(artifact_id)
        return _copy(found) if found is not None else None

    def artifacts_for_run(self, run_id: str) -> Tuple[PerceptualArtifact, ...]:
        return tuple(_copy(a) for a in self._artifacts.values() if a.identity.run_id == run_id)

    # -- reviews --

    def put_review(self, review: LabReview) -> LabReview:
        self._reviews[review.review_id] = _copy(review)
        return review

    def get_review(self, review_id: str) -> Optional[LabReview]:
        found = self._reviews.get(review_id)
        return _copy(found) if found is not None else None

    def reviews_for_artifact(self, artifact_id: str) -> Tuple[LabReview, ...]:
        return tuple(_copy(r) for r in self._reviews.values() if r.artifact_id == artifact_id)

    # -- for tests and for a lab receipt --

    def counts(self) -> Dict[str, int]:
        return {"sessions": len(self._sessions), "plans": len(self._plans),
                "runs": len(self._runs), "artifacts": len(self._artifacts),
                "reviews": len(self._reviews)}


def resolve_inputs(store: LabStore, refs) -> Dict[str, List[PerceptualArtifact]]:
    """Input refs into the artifacts they name, keyed by role.

    A ref whose artifact is not in the store is SKIPPED rather than raising, and the caller then
    finds the role short and refuses `missing_extent_inputs`. The resolver has already proved the
    id was declared by the session, so an id that is declared and absent is a lab whose ledger
    disagrees with its session — and the honest report of that is "the input did not resolve",
    which is what the refusal says.
    """
    out: Dict[str, List[PerceptualArtifact]] = {}
    for ref in refs:
        if ref.artifact_id is None:
            continue
        found = store.get_artifact(ref.artifact_id)
        if found is not None:
            out.setdefault(ref.role, []).append(found)
    return out


__all__ = ["LabStore", "InMemoryLabStore", "StoreError", "resolve_inputs"]
