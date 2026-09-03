"""
PERCEPTUAL-FORMS-001H — where a derivation is remembered, and why it is not the lab store.

A SIXTH COLLECTION, AND A SEPARATE DOOR. `LabStore` has fifteen methods and the conductor calls
those fifteen and no others; adding `put_derivation` to it would hand the conductor a door it must
not walk through. A derivation is not produced by a run, is not authorized by a plan, and cannot
become an artifact — so it gets its own store, and "the conductor cannot write a derivation" stays
a description of what it was handed rather than a rule it follows.

THE SAME DOCUMENT SHAPE AS THE LAB STORE, deliberately. `{_id, kind, contract_version, session_id,
record, written_at}` — because a person reading two collections in a shell should not have to learn
two layouts, and `session_id` lifted out is what makes the by-session read an indexed query rather
than a scan.

WHAT IS NOT ON THIS CLASS. `promote`, `put_artifact`, `put_region`, `put_post`. There is no method
here that could turn a derivation into canon, and the suite asserts the public surface against the
Protocol so that a method added would fail the test that says the door is not there.

FAILED WRITES ARE RAISED, not swallowed. A derivation that looks recorded and cannot be re-opened
is worse than one that failed to record.

PURE OF ORGANS. No model, no image, no adapter. The collection is injected; the default is
resolved lazily, so this module imports with no database configured at all.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple

from backend.services.perception_lab.derivations import RECORD_KIND, LabDerivation

CONTRACT_VERSION = 1
COLLECTION_KEY = "derivations"


class DerivationStoreUnavailable(RuntimeError):
    """The derivation collection could not be reached. Raised rather than returning None: a
    caller that carried on would tell somebody their derivation was saved when it was not."""


class DerivationStore(Protocol):
    """Everything a derivation runtime may remember. Three methods, and none of them is canon."""

    def put(self, record: LabDerivation) -> LabDerivation: ...
    def get(self, derivation_id: str) -> Optional[LabDerivation]: ...
    def for_session(self, session_id: str) -> Tuple[LabDerivation, ...]: ...


class InMemoryDerivationStore:
    """The reference implementation. Values in, values out, insertion order preserved.

    ORDER IS PART OF THE CONTRACT for the same reason it is on the lab store: a person comparing
    two derivations of one form is comparing a first attempt with a second, and a list that
    reordered them would make the second look like the first.
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, LabDerivation] = {}

    def put(self, record: LabDerivation) -> LabDerivation:
        self._by_id[record.derivation_id] = record.model_copy(deep=True)
        return record

    def get(self, derivation_id: str) -> Optional[LabDerivation]:
        found = self._by_id.get(derivation_id)
        return found.model_copy(deep=True) if found is not None else None

    def for_session(self, session_id: str) -> Tuple[LabDerivation, ...]:
        return tuple(r.model_copy(deep=True) for r in self._by_id.values()
                     if r.session_id == session_id)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MongoDerivationStore:
    """The durable one. The same three methods against one collection."""

    def __init__(self, collection: Any = None, *, now=None) -> None:
        self._collection = collection
        self._now = now or _now

    def _c(self):
        if self._collection is None:
            try:
                from backend.database import perception_lab_collections
                self._collection = perception_lab_collections()[COLLECTION_KEY]
            except Exception as exc:
                raise DerivationStoreUnavailable(
                    f"the derivation collection could not be resolved: {exc}") from exc
        return self._collection

    def put(self, record: LabDerivation) -> LabDerivation:
        document = {
            "_id": record.derivation_id, "kind": RECORD_KIND,
            "contract_version": CONTRACT_VERSION, "session_id": record.session_id,
            "form": record.form, "record": record.model_dump(mode="json"),
            "written_at": self._now(),
        }
        try:
            self._c().replace_one({"_id": record.derivation_id}, document, upsert=True)
        except Exception as exc:
            raise DerivationStoreUnavailable(
                f"could not write derivation {record.derivation_id}: {exc}") from exc
        return record

    def get(self, derivation_id: str) -> Optional[LabDerivation]:
        try:
            document = self._c().find_one({"_id": derivation_id})
        except Exception as exc:
            raise DerivationStoreUnavailable(
                f"could not read derivation {derivation_id}: {exc}") from exc
        return self._hydrate(document)

    def for_session(self, session_id: str) -> Tuple[LabDerivation, ...]:
        try:
            found = list(self._c().find({"session_id": session_id})
                         .sort([("written_at", 1), ("_id", 1)]))
        except Exception as exc:
            raise DerivationStoreUnavailable(
                f"could not read derivations for {session_id}: {exc}") from exc
        return tuple(r for r in (self._hydrate(d) for d in found) if r is not None)

    @staticmethod
    def _hydrate(document: Optional[Mapping[str, Any]]) -> Optional[LabDerivation]:
        if not document:
            return None
        return LabDerivation.model_validate(document["record"])


__all__ = ["COLLECTION_KEY", "CONTRACT_VERSION", "DerivationStore",
           "DerivationStoreUnavailable", "InMemoryDerivationStore", "MongoDerivationStore"]
