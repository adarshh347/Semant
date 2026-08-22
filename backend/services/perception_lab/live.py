"""
PERCEPTUAL-ORGANS-002 Lane F1 — the live laboratory: a conductor wired to real organs, and the
projections a route serves.

    a post → a snapshot → a runtime → a live registry → a conductor → the durable store

ONE CONDUCTOR PER REQUEST, and Lane D says that is fine. It is more than fine here: a conductor
holds the RUNTIME — this picture's bytes, this post's regions, this deployment's capability
opinions — and a process-wide one would either have to be handed a different runtime per call
(which is the same object with a mutable field, i.e. a race) or would serve one person's image to
another person's run. The store is the durable part and is the same five collections every time.

WHAT THIS MODULE ADDS TO LANE D, AND IT IS DELIBERATELY LITTLE:

    · the runtime and registry, from a source snapshot
    · the source probe, so `source_digest_after` is a re-reading rather than a copied value
    · the projections — records to JSON, with an `execution_identity` on every envelope
    · a process-local cancel table, and an honest account of what it cannot reach

WHAT IT DOES NOT ADD. Any decision about a measurement, any state a session did not already carry,
and any path from `kept` to a post. `LifecycleState` is a lab curation state and setting it is one
`put_artifact`; there is no code here that reads it, and none that could act on it.

EVERY ENVELOPE SAYS WHICH WIRE IT IS ON. `execution_identity` is on every response body, including
the ones that report no run at all — because a person looking at a session has to know whether the
laboratory around it can call anything, and the answer is a property of the registry rather than of
the URL. It comes from the registry itself, so a test that hands in fakes gets `FIXTURE` without
anybody having to remember to say so.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (CapabilityState, ExecutionIdentity, LabPlan, LabReview,
                                            LabRun, LabSession, LifecycleState, OrganFamily,
                                            PerceptualArtifact, SessionMode)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.adapters import CallBudget, CancelToken
from backend.services.perception_lab.bridges import LabRuntime, live_registry
from backend.services.perception_lab.contracts import LAB_SCHEMA_VERSION
from backend.services.perception_lab.mongo_store import MongoLabStore
from backend.services.perception_lab import producers
from backend.services.perception_lab.orchestrator import Execution, PerceptionConductor
from backend.services.perception_lab.planners import ModelPlanner
from backend.services.perception_lab.response import LabResponse
from backend.services.perception_lab.session import SessionMachine
from backend.services.perception_lab.source import SourceSnapshot, mutation_probe

#: What one lab run may spend. Lower than Lane D's default wall clock because this one is behind an
#: HTTP request a person is watching: eight adapter calls is an all-pairs sweep over four extents,
#: and three minutes is longer than anybody waits before reloading.
LAB_BUDGET = CallBudget(max_adapter_calls=8, max_wall_ms=180_000)


# ── cancellation ─────────────────────────────────────────────────────────────


class CancelTable:
    """Tickets a person can pull, for runs happening in THIS process.

    THE HONEST LIMIT, stated rather than hidden. A run is a synchronous call inside one request;
    cancelling it means another request setting a flag the first one polls between stages. That
    works when both land on the same worker and does not when they do not, and there is no shared
    flag store here to make it work — so `cancel()` reports whether it actually reached a run, and
    the route returns that instead of a cheerful 200.

    A ticket is the CLIENT'S id for a run it is about to start, because the run's own id is minted
    inside `execute` and does not exist yet at the moment somebody might want to stop it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open: Dict[str, CancelToken] = {}

    def open(self, ticket: Optional[str]) -> CancelToken:
        token = CancelToken()
        if ticket:
            with self._lock:
                self._open[str(ticket)] = token
        return token

    def close(self, ticket: Optional[str]) -> None:
        if ticket:
            with self._lock:
                self._open.pop(str(ticket), None)

    def cancel(self, ticket: str, reason: str = "cancelled by the person") -> bool:
        with self._lock:
            token = self._open.get(str(ticket))
        if token is None:
            return False
        token.cancel(reason)
        return True

    @property
    def open_tickets(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._open))


CANCELS = CancelTable()


# ── building the laboratory ──────────────────────────────────────────────────


def runtime_for(snapshot: SourceSnapshot, *,
                capability_states: Optional[Mapping[str, CapabilityState]] = None,
                extent_adapters: Optional[Mapping[str, Any]] = None) -> LabRuntime:
    return LabRuntime(source=snapshot.source, image_bytes=snapshot.image_bytes,
                      regions=snapshot.regions,
                      capability_states=dict(capability_states or {}),
                      extent_adapters=extent_adapters)


def conductor_for(snapshot: SourceSnapshot, *, store: Any = None, registry: Any = None,
                  capability_states: Optional[Mapping[str, CapabilityState]] = None,
                  extent_adapters: Optional[Mapping[str, Any]] = None,
                  probe_collection: Any = None,
                  model: Any = None) -> PerceptionConductor:
    """The conductor a request runs on: real organs, the durable store, and a live source probe.

    `model` defaults to a configured `ModelPlanner`, which handles its own absence — no key means
    it falls back to the rules arm AND records `planner_fell_back_from`, so a person is told the
    sentence was not read by a model rather than being quietly served a keyword match.
    """
    runtime = runtime_for(snapshot, capability_states=capability_states,
                          extent_adapters=extent_adapters)
    return PerceptionConductor(
        store=store if store is not None else MongoLabStore(),
        registry=registry if registry is not None else live_registry(runtime),
        model=model if model is not None else ModelPlanner(),
        budget=LAB_BUDGET,
        source_probe=mutation_probe(snapshot, collection=probe_collection))


def identity_of(registry: Any) -> ExecutionIdentity:
    """What kind of wire this laboratory is on. Read off the registry, never off the route."""
    found = getattr(registry, "identity", None)
    return found if isinstance(found, ExecutionIdentity) else ExecutionIdentity.FIXTURE


# ── the catalogue ────────────────────────────────────────────────────────────


def capability_catalogue(registry: Any) -> Dict[str, Any]:
    """Every organ, every operation, and what this deployment can honestly say about each adapter.

    THE THREE ANSWERS ARE KEPT APART. `available` is an adapter this registry holds and that said
    yes; `unavailable` is one it holds that said no; and an adapter absent from `states` is
    `unknown_until_runtime` — nobody looked. The six disabled organs are reported with
    `enabled: false` and no adapter states at all, because a capability answer about an organ this
    phase does not have would be a capability invented at the wiring layer.
    """
    states = dict(registry.capabilities()) if registry is not None else {}
    organs: List[Dict[str, Any]] = []
    for organ in D.organs().values():
        operations = []
        for op in D.operations_for(organ.family):
            operations.append({
                "key": op.key,
                "manual": op.manual,
                "requires_confirmation": op.requires_confirmation,
                "adapters": [_adapter_json(name, states) for name in op.adapters],
                "inputs": [{"role": i.role, "required": i.required,
                            "required_for_execution": i.required_for_execution}
                           for i in op.inputs],
                "parameters": [p.name for p in op.parameters],
            })
        organs.append({"family": organ.family, "label": organ.label, "question": organ.question,
                       "enabled": organ.enabled, "availability": organ.availability,
                       "epistemic_ceiling": organ.epistemic_ceiling,
                       "deferred_note": organ.deferred_note,
                       "operations": operations if organ.enabled else []})
    return {"schema_version": LAB_SCHEMA_VERSION, "organs": organs,
            "states": {name: state.value for name, state in states.items()},
            # PERCEPTUAL-FORMS-001H. The form catalogue rides beside the organ catalogue rather
            # than on a second route, because a person deciding what to open needs both answers at
            # once and two round trips is two chances for them to disagree.
            "forms": producers.catalogue(states=states)}


def _adapter_json(name: str, states: Mapping[str, CapabilityState]) -> Dict[str, Any]:
    """One adapter's state, and — when it is not running — WHICH absence and what to do about it.

    THE REASON IS NEW AND IT IS THE POINT. `unavailable` on its own once sent a rehearsal looking
    for a 3.2 GB download that was already on the disk; the checkpoint was there and the
    environment variable naming it was not, and the table could not tell those apart. The state
    still comes from the registry — this only adds the sentence the registry has no field for.
    """
    state = states.get(name, CapabilityState.UNKNOWN_UNTIL_RUNTIME)
    entry = producers.adapter_identity(name)
    out: Dict[str, Any] = {"key": name, "state": state.value, "kind": entry.kind,
                           "label": entry.label, "model": entry.model,
                           "revision": entry.revision}
    if state is not CapabilityState.AVAILABLE:
        out["reason"] = entry.reason
        out["remedy"] = entry.remedy
    return out


# ── projections ──────────────────────────────────────────────────────────────


def _json(record: Any) -> Any:
    return record.model_dump(mode="json") if record is not None else None


def session_json(session: LabSession) -> Dict[str, Any]:
    return _json(session)


def record_json(record: Any) -> Any:
    """Any contract record, as the contract holds it. No renaming, no flattening, no dropped nulls.

    The same rule Lane E's export states and for the same reason: a projection that tidied the
    records would be a second vocabulary, and the field it dropped would be the one a reader needed
    six months later.
    """
    return _json(record)


def response_json(response: Optional[LabResponse]) -> Dict[str, Any]:
    """The templated lines, as ids AND text. Both, so a client can render its own and a reader can
    check the second against the first."""
    if response is None:
        return {"lines": [], "text": ""}
    return {"lines": [{"template_id": line.template_id, "fields": dict(line.fields),
                       "text": line.text} for line in response.lines],
            "text": response.text}


def execution_json(execution: Execution) -> Dict[str, Any]:
    return {"run": _json(execution.run), "plan": _json(execution.plan),
            "artifacts": [_json(a) for a in execution.artifacts],
            "response": response_json(execution.response),
            "execution_identity": execution.run.execution_identity.value,
            "outcome": execution.run.outcome.value}


def history_json(store: Any, session: LabSession) -> Dict[str, Any]:
    """One sitting's whole ledger, in the contract's five record types and no others."""
    artifacts = _artifacts_for(store, session)
    return {
        "session": session_json(session),
        "plans": [_json(p) for p in store.plans_for_session(session.session_id)],
        "runs": [_json(r) for r in store.runs_for_session(session.session_id)],
        "artifacts": [_json(a) for a in artifacts],
        "reviews": [_json(r) for r in _reviews_for(store, session, artifacts)],
    }


def _artifacts_for(store: Any, session: LabSession) -> List[PerceptualArtifact]:
    """Every artifact of the sitting, by run, in run order.

    Walks the runs rather than querying by session because `LabStore`'s fifteen methods are what
    every implementation is guaranteed to have — the durable store offers a session-wide query and
    the in-memory one does not, and a projection that only worked against one of them would fail in
    exactly the tests that matter.
    """
    seen: Dict[str, PerceptualArtifact] = {}
    for run in store.runs_for_session(session.session_id):
        for artifact in store.artifacts_for_run(run.run_id):
            seen.setdefault(artifact.identity.artifact_id, artifact)
    return list(seen.values())


def _reviews_for(store: Any, session: LabSession,
                 artifacts: Sequence[PerceptualArtifact]) -> List[LabReview]:
    out: List[LabReview] = []
    for review_id in session.review_ids:
        found = store.get_review(review_id)
        if found is not None:
            out.append(found)
    if out:
        return out
    for artifact in artifacts:
        out.extend(store.reviews_for_artifact(artifact.identity.artifact_id))
    return out


def export_json(store: Any, session: LabSession, *, identity: ExecutionIdentity) -> Dict[str, Any]:
    """The canonical session export: the five record types, unrenamed and unflattened.

    THE SAME FIVE KEYS Lane E's `buildExport` takes, so the browser's export and this one are two
    renderings of one bundle rather than two bundles. Nothing here is promoted, nothing is merged,
    and no canonical id is minted — an export is a copy, and this envelope says so in a field
    rather than in a comment nobody ships.
    """
    bundle = history_json(store, session)
    return {
        "export_kind": "perception-lab.session-export",
        "export_version": 1,
        "exported_by": "perception_lab_backend",
        "execution_identity": identity.value,
        "what_this_is":
            "One Perception Lab session in the records of `perception-lab.v1`. Every artifact is "
            "SESSION-LOCAL: none of it is in Semant's ledger, and reading this file does not put "
            "it there. Lifecycle states are carried as they stand; `kept` means kept in the lab.",
        "not_this": [
            "Not a promotion. No canonical id is minted here and this lane has no path that could.",
            "Not a judgement. Reviews are separate records keyed by artifact_id, because a verdict "
            "folded into an artifact becomes a property of the measurement.",
        ],
        **bundle,
        "counts": {key: len(bundle[key]) for key in ("plans", "runs", "artifacts", "reviews")},
    }


# ── the one write that is a curation state and not a promotion ───────────────


def set_lifecycle(store: Any, artifact_id: str, status: LifecycleState, *,
                  changed_by: str, at: str) -> PerceptualArtifact:
    """`proposed` → `kept` / `rejected`, inside the laboratory.

    NOT PROMOTION, and the difference is structural rather than a matter of intent: this writes one
    field of one document in `perception_lab_artifacts`, and nothing in Semant reads that
    collection. `promoted` is refused here — the contract has the state because promotion will one
    day set it, and the act that sets it is a separate, explicit, confirmed one that this lane does
    not implement. A lifecycle endpoint that could reach it would be that act, wearing a smaller
    name.
    """
    if status is LifecycleState.PROMOTED:
        raise ValueError(
            "`promoted` is not a lifecycle a person sets from the laboratory. Promotion is a "
            "separate confirmed act with revision checks, and this endpoint is a curation state "
            "inside the lab's own ledger.")
    artifact = store.get_artifact(artifact_id)
    if artifact is None:
        raise KeyError(artifact_id)
    updated = artifact.model_copy(update={
        "lifecycle": artifact.lifecycle.model_copy(update={
            "status": status, "changed_at": at, "changed_by": changed_by})})
    store.put_artifact(updated)
    return updated


# ── selection, applied through the machine that owns the invariants ──────────


def apply_selection(machine: SessionMachine, *, organ: Optional[str] = None,
                    mode: Optional[str] = None,
                    selected_artifact_ids: Optional[Sequence[str]] = None,
                    active_artifact_id: Optional[str] = None,
                    selected_instance_refs: Optional[Sequence[Mapping[str, Any]]] = None,
                    active_region_ids: Optional[Sequence[str]] = None,
                    clear_active: bool = False) -> LabSession:
    """Every selection change, through `SessionMachine` and never by assignment.

    THE ORDER IS THE INVARIANT. Artifacts are replaced first, then instances, then the active one —
    because `LabSession` refuses an instance ref whose artifact is not selected, and `deselect`
    drops the instances of an artifact that left. Assigning the fields directly would let a route
    write a session the schema then refuses, and the person's deselection would look like a 422.
    """
    if organ is not None:
        machine.select_organ(OrganFamily(organ))
    if mode is not None:
        machine.set_mode(SessionMode(mode))
    if selected_artifact_ids is not None:
        machine.clear_selection()
        machine.select(*[str(a) for a in selected_artifact_ids])
    if selected_instance_refs is not None:
        machine.clear_instance_selection()
        for ref in selected_instance_refs:
            artifact_id = str(ref.get("artifact_id") or "")
            instance_id = str(ref.get("instance_id") or "")
            if artifact_id and instance_id:
                machine.select_instance(artifact_id, instance_id)
    if clear_active:
        machine.clear_active()
    if active_artifact_id:
        machine.activate(str(active_artifact_id))
    if active_region_ids is not None:
        machine.activate_regions([str(r) for r in active_region_ids])
    return machine.session


__all__ = ["LAB_BUDGET", "CancelTable", "CANCELS", "runtime_for", "conductor_for", "identity_of",
           "capability_catalogue", "session_json", "response_json", "execution_json",
           "history_json", "export_json", "set_lifecycle", "apply_selection"]
