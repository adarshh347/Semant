"""
PERCEPTUAL-ORGANS-002 Lane F1 — the lab's memory, made durable.

`InMemoryLabStore` is Lane D's reference implementation and this is the same fifteen methods
against five Mongo collections. What it inherits from that reference is not code but a rule:

    EVERY GET AND EVERY PUT RETURNS A VALUE, NEVER A WINDOW ONTO STATE.

A document read out of Mongo is validated back into a pydantic record, so a caller that mutates
what it read has mutated a copy. Lane D's docstring says discovering that difference at the moment
the Mongo wiring lands is discovering it in the worst place; this is that moment, and there was
nothing to discover, which is the point.

WHAT IS NOT ON THIS CLASS. `put_region`, `put_mark`, `put_percept`, `put_post`, `promote`. The
`LabStore` Protocol has fifteen methods and none of them is canon, so "a lab run cannot mutate
Semant" stays a description of what the conductor was handed rather than a rule it follows. The
suite asserts this class's public surface against the Protocol's, so a method added here would fail
the test that says the door is not there.

WHAT A DOCUMENT LOOKS LIKE, and why it is not just the record:

    {"_id": <the record's own id>, "kind": "perception_lab_run", "contract_version": 1,
     "session_id": …, "record": {…the contract record, mode="json"…},
     "written_at": "2026-08-13T09:00:00.123456+00:00"}

`session_id` is lifted out so the three `*_for_session` reads are indexed queries rather than
scans. `kind` is a discriminator on collections that do not currently need one — a habit borrowed
from `inquiry_session/store.py`, where sharing a collection with Director runs made it load-bearing.

ORDER. Lane D's in-memory store preserves insertion order and calls it part of the contract, for
the reason that a history read out of order can show a replay before the run it replays. Mongo has
no insertion order to preserve, so `written_at` is written and sorted on, with `_id` as a stable
tie-break. Two runs written inside the same microsecond by two processes get an arbitrary but
stable order; a replay is always written after the run it re-shows, so the ordering that mattered
is the one that holds.

FAILED WRITES ARE RAISED, not swallowed. This is not write-behind observability: a session that
looks live and cannot be re-opened is worse than a session that failed to open.

PURE OF ORGANS. No model, no image, no adapter. A collection is injected; the default is the real
one, resolved lazily so this module imports with no database configured at all.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Type, TypeVar

from backend.schemas.perception_lab import (LabPlan, LabReview, LabRun, LabSession,
                                            PerceptualArtifact)

CONTRACT_VERSION = 1

R = TypeVar("R")

#: `{record kind: (collection key, model, id attribute path)}`. One table rather than five pairs of
#: near-identical methods, so a change to how a record is stored is one edit and cannot be applied
#: to four of the five.
KINDS: Mapping[str, str] = {
    "sessions": "perception_lab_session",
    "plans": "perception_lab_plan",
    "runs": "perception_lab_run",
    "artifacts": "perception_lab_artifact",
    "reviews": "perception_lab_review",
}


class LabStoreUnavailable(RuntimeError):
    """The lab's store could not be reached. Raised rather than returning None: a caller that
    carried on would tell somebody their session was saved when it was not."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_collections() -> Mapping[str, Any]:
    from backend.database import perception_lab_collections
    return perception_lab_collections()


class MongoLabStore:
    """`LabStore`, durable. Fifteen methods, five collections, and no door onto canon.

    `collections` is `{"sessions": …, "plans": …, "runs": …, "artifacts": …, "reviews": …}` of
    synchronous pymongo-shaped collections. Injected so the suite can hand in fakes and so this
    module never imports the database at module scope; `None` resolves the real five on first use.
    """

    def __init__(self, collections: Optional[Mapping[str, Any]] = None,
                 *, now: Callable[[], str] = _now):
        self._given = collections
        self._resolved: Optional[Mapping[str, Any]] = None
        self._now = now

    def _c(self, key: str):
        if self._given is not None:
            return self._given[key]
        if self._resolved is None:
            try:
                self._resolved = _default_collections()
            except Exception as exc:                       # noqa: BLE001 - config or driver
                raise LabStoreUnavailable(
                    f"the Perception Lab store could not reach its collections: {exc}") from exc
        return self._resolved[key]

    # -- the two operations everything else is made of --

    def _put(self, key: str, record: Any, record_id: str, session_id: Optional[str]) -> Any:
        doc = {
            "_id": record_id,
            "kind": KINDS[key],
            "contract_version": CONTRACT_VERSION,
            "session_id": session_id,
            "record": record.model_dump(mode="json"),
            "written_at": self._now(),
        }
        try:
            self._c(key).replace_one({"_id": record_id}, doc, upsert=True)
        except LabStoreUnavailable:
            raise
        except Exception as exc:                           # noqa: BLE001 - driver
            raise LabStoreUnavailable(
                f"{KINDS[key]} {record_id!r} was not written: {exc}. Nothing in this laboratory "
                f"reports a record it did not manage to keep.") from exc
        # The record itself, unchanged — the caller's object, not a re-read. Lane D's contract is
        # that a put RETURNS what it was given; only reads are copies.
        return record

    def _get(self, key: str, model: Type[R], record_id: str) -> Optional[R]:
        doc = self._c(key).find_one({"_id": record_id, "kind": KINDS[key]})
        return self._hydrate(model, doc)

    def _find(self, key: str, model: Type[R], query: Mapping[str, Any]) -> Tuple[R, ...]:
        cursor = self._c(key).find({**query, "kind": KINDS[key]})
        sort = getattr(cursor, "sort", None)
        if callable(sort):
            cursor = sort([("written_at", 1), ("_id", 1)])
        out: List[R] = []
        for doc in cursor:
            found = self._hydrate(model, doc)
            if found is not None:
                out.append(found)
        return tuple(out)

    @staticmethod
    def _hydrate(model: Type[R], doc: Optional[Mapping[str, Any]]) -> Optional[R]:
        """A document back into a contract record — a VALUE, validated on the way out.

        A record that no longer validates is a defect, and it is raised rather than skipped: a
        history that silently omitted the one run whose shape drifted would be a history that
        looked complete. `contract_version` is carried so a future migration has something to read;
        nothing branches on it yet, and a fallback that guessed at an older shape would be the
        invented vocabulary this contract is arranged against.
        """
        if not doc:
            return None
        payload = doc.get("record")
        if not isinstance(payload, Mapping):
            return None
        return model.model_validate(dict(payload))         # type: ignore[attr-defined]

    # -- sessions --

    def put_session(self, session: LabSession) -> LabSession:
        return self._put("sessions", session, session.session_id, session.session_id)

    def get_session(self, session_id: str) -> Optional[LabSession]:
        return self._get("sessions", LabSession, session_id)

    def sessions(self) -> Tuple[LabSession, ...]:
        return self._find("sessions", LabSession, {})

    # -- plans --

    def put_plan(self, plan: LabPlan) -> LabPlan:
        return self._put("plans", plan, plan.plan_id, plan.session_id)

    def get_plan(self, plan_id: str) -> Optional[LabPlan]:
        return self._get("plans", LabPlan, plan_id)

    def plans_for_session(self, session_id: str) -> Tuple[LabPlan, ...]:
        return self._find("plans", LabPlan, {"session_id": session_id})

    # -- runs --

    def put_run(self, run: LabRun) -> LabRun:
        return self._put("runs", run, run.run_id, run.session_id)

    def get_run(self, run_id: str) -> Optional[LabRun]:
        return self._get("runs", LabRun, run_id)

    def runs_for_session(self, session_id: str) -> Tuple[LabRun, ...]:
        return self._find("runs", LabRun, {"session_id": session_id})

    # -- artifacts --

    def put_artifact(self, artifact: PerceptualArtifact) -> PerceptualArtifact:
        return self._put("artifacts", artifact, artifact.identity.artifact_id,
                         artifact.identity.session_id)

    def get_artifact(self, artifact_id: str) -> Optional[PerceptualArtifact]:
        return self._get("artifacts", PerceptualArtifact, artifact_id)

    def artifacts_for_run(self, run_id: str) -> Tuple[PerceptualArtifact, ...]:
        return self._find("artifacts", PerceptualArtifact, {"record.identity.run_id": run_id})

    # -- reviews --

    def put_review(self, review: LabReview) -> LabReview:
        return self._put("reviews", review, review.review_id, review.session_id)

    def get_review(self, review_id: str) -> Optional[LabReview]:
        return self._get("reviews", LabReview, review_id)

    def reviews_for_artifact(self, artifact_id: str) -> Tuple[LabReview, ...]:
        return self._find("reviews", LabReview, {"record.artifact_id": artifact_id})

    # -- for a lab receipt, and for the suite --

    def artifacts_for_session(self, session_id: str) -> Tuple[PerceptualArtifact, ...]:
        """Not on the Protocol, and additive rather than a widening of it.

        The conductor never calls this — it reads artifacts by RUN, because a run is what produced
        them. An export and a session history need the sitting's whole ledger, and deriving it by
        walking every run's id list would be the same query with more round trips.
        """
        return self._find("artifacts", PerceptualArtifact, {"session_id": session_id})

    def reviews_for_session(self, session_id: str) -> Tuple[LabReview, ...]:
        return self._find("reviews", LabReview, {"session_id": session_id})

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for key in KINDS:
            collection = self._c(key)
            counter = getattr(collection, "count_documents", None)
            out[key] = counter({}) if callable(counter) else 0
        return out


__all__ = ["MongoLabStore", "LabStoreUnavailable", "KINDS", "CONTRACT_VERSION"]
