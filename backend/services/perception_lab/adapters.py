"""
PERCEPTUAL-ORGANS-002 Lane D — the adapter seam, and the exact shape Lane F must fill.

THIS FILE IS THE HANDOFF. Lane B has an Extent façade and Lane C has a Topology façade; neither
knows about sessions, plans, runs or artifacts, and neither should. This is the one interface
between them and the conductor, and Lane D develops against fakes that implement it so that the
shape is settled before the real ones arrive rather than negotiated afterwards.

    invoke(AdapterCall) -> AdapterOutcome

WHAT THE ADAPTER IS GIVEN. A resolved operation, clamped parameters, and the artifacts its inputs
RESOLVED TO — not the ids. An adapter that received ids would need a store to look them up in, and
an adapter with a store is an adapter that can read something nobody authorized.

WHAT THE ADAPTER RETURNS, AND WHAT IT DOES NOT.

  RETURNS   the measurement, the projection, the reading, and the facts only it knows: which model
            ran, at what revision, on what device, how much memory it took.

  DOES NOT   mint an artifact id, a run id or a step id;
             time itself;
             decide the run's outcome;
             write anything anywhere.

  The conductor owns identity and the clock. An adapter that stamped its own `duration_ms` would
  be reporting the number it wished were true, and the one number a laboratory cannot afford to
  take on trust is the one that says how long the measurement took. The observer holds the
  stopwatch, on the outside of the call.

THE ORGAN FIREWALL LIVES IN THE REGISTRY. An adapter declares the organ it serves, and
`AdapterRegistry.register` refuses to bind it to an operation of any other. That is the structural
half of "never silently cross from Topology to Extent": even a registry misconfiguration cannot
make a topology operation reach an extent adapter, so the crossing cannot happen below the level
where the resolver and the session lock can see it.

CANCELLATION IS COOPERATIVE, and honestly so. `AdapterCall.cancel` is a token the adapter MAY
poll; nothing here can interrupt a model mid-forward-pass. What the conductor guarantees is that
no FURTHER call is made once the token is set, and the run says which stages were skipped. A
harder promise would be one this process cannot keep.

PURE. No database, no network, no model. The fakes in `fakes.py` are the reference implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from backend.schemas.perception_lab import (ArtifactInterpretation, ArtifactMeasurement,
                                            ArtifactProjection, CapabilityState, InputRef,
                                            LabSource, OrganFamily, PerceptualArtifact,
                                            RefusalRecord, StageState)
from backend.services.perception_lab.contracts import operation_index
from backend.services.perception_lab.definitions import operation

#: The states an adapter may report. `queued`, `started` and `skipped` belong to the observer —
#: they are facts about the machinery around the call, not about what the call found.
ADAPTER_STATES: Tuple[StageState, ...] = (
    StageState.COMPLETED, StageState.EMPTY, StageState.REFUSED, StageState.UNAVAILABLE,
    StageState.FAILED)


class AdapterError(RuntimeError):
    """Raised by the registry, never by an adapter. An adapter reports failure in its outcome."""


class NotRegistered(AdapterError):
    """No adapter is bound to this operation here. Distinct from `capability_unavailable`, which
    is a declared adapter that is not loadable; this is a lane that has not been wired yet."""


class OrganCrossing(AdapterError):
    """An adapter was offered an operation of an organ it does not serve. Never a refusal — a
    person cannot fix this and there is no message worth showing them."""


class Cancelled(RuntimeError):
    """The person stopped the run. Not a refusal: nothing said no, someone changed their mind."""


class CancelToken:
    """A flag one side sets and the other polls. Deliberately not a threading primitive.

    A `threading.Event` would suggest this can interrupt something, and it cannot. What the
    conductor promises is that it checks before every stage and before every call, and that a
    stage it did not run is recorded as `skipped` with the reason. An adapter that wants to be a
    better citizen polls `cancelled` inside its own loop.
    """

    def __init__(self) -> None:
        self._cancelled = False
        self.reason: Optional[str] = None

    def cancel(self, reason: str = "cancelled by the person") -> None:
        self._cancelled = True
        self.reason = reason

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise Cancelled(self.reason or "cancelled")


@dataclass(frozen=True)
class CallBudget:
    """What one run is allowed to spend before it stops asking.

    TWO BOUNDS, because they catch two different failures. `max_adapter_calls` catches a plan that
    fans out — an all-pairs sweep over a set somebody did not bound. `max_wall_ms` catches one
    call that never comes back. Either alone leaves the other open.

    EXHAUSTION IS NOT A REFUSAL, and there is no refusal code for it in the contract's closed set
    of nine. It is recorded as `skipped` stages with the reason, and the run ends `partial` if
    something was produced and `failed` if nothing was — `failed` being the outcome that means
    "no claim is made about the image at all", which is exactly true of a run that stopped early.
    """
    max_adapter_calls: int = 8
    max_wall_ms: int = 120_000

    def exceeded_calls(self, made: int) -> bool:
        return made >= self.max_adapter_calls

    def exceeded_wall(self, elapsed_ms: int) -> bool:
        return elapsed_ms >= self.max_wall_ms


@dataclass(frozen=True)
class AdapterCall:
    """Everything an adapter is given, and nothing it could use to reach further.

    `inputs` are RESOLVED ARTIFACTS keyed by the role the operation declares, not ids. An adapter
    handed ids would need a store to resolve them in, and a store is a door.
    """
    session_id: str
    run_id: str
    step_id: str
    organ: OrganFamily
    operation: str
    adapter: str
    parameters: Mapping[str, Any]
    input_refs: Tuple[InputRef, ...]
    inputs: Mapping[str, Tuple[PerceptualArtifact, ...]]
    source: LabSource
    cancel: CancelToken
    deadline_ms: Optional[int] = None

    def one(self, role: str) -> Optional[PerceptualArtifact]:
        got = self.inputs.get(role, ())
        return got[0] if got else None

    def all(self, role: str) -> Tuple[PerceptualArtifact, ...]:
        return tuple(self.inputs.get(role, ()))


@dataclass(frozen=True)
class AdapterOutcome:
    """What one call found, in the blocks Lane A keeps apart.

    The adapter fills measurement, projection and interpretation — the three things that are true
    of what it saw. It does not fill identity, lifecycle or provenance-envelope: those are facts
    about the RUN, and the conductor owns them.
    """
    state: StageState
    measurement: Optional[ArtifactMeasurement] = None
    projection: Optional[ArtifactProjection] = None
    interpretation: Optional[ArtifactInterpretation] = None
    refusal: Optional[RefusalRecord] = None
    model: Optional[str] = None
    revision: Optional[str] = None
    device: Optional[str] = None
    peak_memory_mb: Optional[float] = None
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if self.state not in ADAPTER_STATES:
            raise AdapterError(
                f"an adapter may report {[s.value for s in ADAPTER_STATES]}; "
                f"{self.state.value!r} is a fact about the machinery around the call, which the "
                f"observer records and the adapter does not know.")
        if self.state in (StageState.COMPLETED, StageState.EMPTY) and self.measurement is None:
            raise AdapterError(
                f"a {self.state.value} stage carries the measurement it made. An empty result is "
                f"still a measurement — it says what was looked for and did not find it — and a "
                f"stage that reported emptiness with no payload would be indistinguishable from "
                f"one that never looked.")
        if self.state in (StageState.REFUSED, StageState.UNAVAILABLE) and self.refusal is None:
            raise AdapterError(
                f"a {self.state.value} stage carries the typed refusal that caused it. An "
                f"untyped no is the empty result this contract exists to keep apart from one.")
        if self.state is StageState.FAILED and not self.detail:
            raise AdapterError("a failed stage says what raised. `failed` means no claim is made "
                               "about the image, and a reader needs to know why to fix it.")


@runtime_checkable
class LabAdapter(Protocol):
    """One organ's runtime, as the conductor sees it. THE INTERFACE LANE F IMPLEMENTS.

        name        the adapter id declared in `contracts/perception-lab.v1.json`
        organ       the family this serves. The registry refuses to bind it outside that family.
        operations  the operation keys it can run. Every one must belong to `organ`.
        invoke      one call, one outcome. Never raises for a refusal; raising is `failed`.
    """

    name: str
    organ: str
    operations: Tuple[str, ...]

    def invoke(self, call: AdapterCall) -> AdapterOutcome:
        ...


class AdapterRegistry:
    """Which adapter runs which operation here, and the organ firewall around that question.

    `capabilities()` is the table the resolver's fifth gate reads. It reports `available` for what
    is registered and says nothing about the rest — `unknown_until_runtime`, Lane A's rule that a
    caller who has not looked is not a caller who found nothing. Marking an unregistered adapter
    `unavailable` would be this registry claiming to know what is loadable on a machine, which is
    exactly the fabricated capability the deferred organs exist to avoid.
    """

    def __init__(self) -> None:
        self._by_operation: Dict[Tuple[str, str], LabAdapter] = {}
        self._names: Dict[str, LabAdapter] = {}

    def register(self, adapter: LabAdapter) -> "AdapterRegistry":
        for op_key in adapter.operations:
            owner = operation_index().get(op_key)
            if owner is None:
                raise NotRegistered(
                    f"adapter {adapter.name!r} claims {op_key!r}, which is not a declared "
                    f"operation. There is no fallback registry.")
            if owner != adapter.organ:
                raise OrganCrossing(
                    f"adapter {adapter.name!r} serves the {adapter.organ} organ and claims "
                    f"{op_key!r}, which belongs to {owner}. A crossing below this level is a "
                    f"crossing neither the session lock nor the resolver can see.")
            if adapter.name not in operation(op_key).adapters:
                raise NotRegistered(
                    f"{op_key!r} declares adapters {list(operation(op_key).adapters)} and "
                    f"{adapter.name!r} is not among them. An adapter the contract does not name "
                    f"cannot be chosen by the resolver, so binding it here would create a runtime "
                    f"nobody can reach on purpose.")
            self._by_operation[(op_key, adapter.name)] = adapter
        self._names[adapter.name] = adapter
        return self

    def resolve(self, op_key: str, adapter_name: Optional[str]) -> LabAdapter:
        if adapter_name is None:
            raise NotRegistered(f"{op_key!r} was resolved without an adapter to run it")
        found = self._by_operation.get((op_key, adapter_name))
        if found is None:
            raise NotRegistered(
                f"no adapter {adapter_name!r} is registered for {op_key!r} in this deployment")
        return found

    def capabilities(self) -> Mapping[str, CapabilityState]:
        return {name: CapabilityState.AVAILABLE for name in self._names}

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._names))


__all__ = ["AdapterCall", "AdapterOutcome", "LabAdapter", "AdapterRegistry", "CancelToken",
           "CallBudget", "AdapterError", "NotRegistered", "OrganCrossing", "Cancelled",
           "ADAPTER_STATES"]
