"""
PERCEPTUAL-ORGANS-002 Lane F1 — the bridges: the conductor meets the real organs.

Lane D developed against `fakes.py`. This is the same interface filled by the two façades that
actually measure things:

    ExtentBridge    → `extent.run(step, ExtentContext)`      → `ExtentResult`
    TopologyBridge  → `topology.run(TopologyRequest)`        → `TopologyResult`

THE AUTHORITY SPLIT, WHICH IS THE WHOLE DESIGN OF THIS FILE. Both façades return a finished
`PerceptualArtifact` — they have to, because both are usable on their own. The conductor also
builds one. Two artifacts for one measurement is exactly the duplicate envelope this lane must not
persist, so a bridge does not return the façade's artifact. It returns the three blocks the façade
is the authority for and lets the conductor mint the rest:

    THE ORGAN IS AUTHORITATIVE FOR    measurement · projection · interpretation ·
                                      epistemic basis and status · which model, revision, device
    THE CONDUCTOR IS AUTHORITATIVE    artifact / run / step / session identity · lifecycle ·
                                      the outer clock · the run's outcome · what is stored

The façade's artifact id is never minted into the ledger; its inner timings never become the
run's. Nothing here writes anything anywhere — the store is the conductor's and this file has no
reference to one.

ONE CLOCK ON THE RECORD, THE INNER ONE IN WORDS. `StageAttempt.duration_ms` is the observer's
stopwatch, outside the call, and it is the only duration that reaches a field. The organ's own
number — SAM's forward pass, the distance transform's milliseconds — is real and worth keeping, so
it goes into the stage's `detail` prose, where a reader can see both and can never mistake the
second for a second authoritative clock.

WHAT A BRIDGE MAY NOT DO. Mint an id, read the time onto a record, write to a store, choose an
adapter the resolver did not, or turn a refusal into a failure. A refusal comes back typed; an
exception is `failed` and the conductor says so.

PURE OF PERSISTENCE. Models, yes — that is the point. No database, no post, no ledger, no route.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (ArtifactInterpretation, ArtifactMeasurement,
                                            ArtifactProjection, CapabilityState, ExecutionIdentity,
                                            LabSource, OrganFamily, PerceptualArtifact,
                                            RefusalCode, RefusalRecord, ResolvedStep, RunOutcome,
                                            StageState)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import extent as extent_facade
from backend.services.perception_lab import topology as topology_facade
from backend.services.perception_lab.adapters import (AdapterCall, AdapterError, AdapterOutcome,
                                                      AdapterRegistry)

#: The organs this deployment actually runs. The other six are declared and disabled in the
#: contract, and a bridge for one of them would be a capability invented at the wiring layer.
LIVE_ORGANS: Tuple[str, ...] = (OrganFamily.EXTENT.value, OrganFamily.TOPOLOGY.value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _monotonic_ms() -> float:
    return time.monotonic() * 1000.0


@dataclass(frozen=True)
class LabRuntime:
    """The picture, the regions and the capability opinions one sitting runs against.

    Built ONCE per request, from a post that has already been read, and handed to the bridges. It
    is what makes a bridge pure of I/O: the image is bytes in hand rather than a URL to fetch, and
    the regions are dicts already copied out of the post document, so nothing below this line can
    reach a database even by accident.

    `capability_states` is the CALLER'S opinion and wins over an adapter's own — a deployment with
    the weights on disk and the GPU withheld knows something the adapter cannot. Empty is the
    honest default: no opinion, ask the adapter.

    `region_revs` is what the corpus currently holds, per region. Topology compares it against the
    revision an extent cited and marks a stale endpoint; without it a lab measurement could quietly
    describe a region that has since been redrawn.
    """
    source: LabSource
    image_bytes: bytes = b""
    regions: Tuple[Mapping[str, Any], ...] = ()
    capability_states: Mapping[str, CapabilityState] = field(default_factory=dict)
    #: Injectable for tests. `None` means the real adapters, imported lazily by the façade.
    extent_adapters: Optional[Mapping[str, Any]] = None
    now: Callable[[], str] = _utc_now
    monotonic_ms: Callable[[], float] = _monotonic_ms
    device: Optional[str] = None

    @property
    def regions_by_id(self) -> Dict[str, Mapping[str, Any]]:
        return {str(r.get("id")): r for r in self.regions if r.get("id")}

    @property
    def region_revs(self) -> Dict[str, int]:
        return {str(r.get("id")): int(r.get("geometry_rev") or 0)
                for r in self.regions if r.get("id")}


def _step_of(call: AdapterCall) -> ResolvedStep:
    """The authorization the conductor was given, not one this file wrote.

    Raises rather than rebuilding. A bridge that constructed a `ResolvedStep` would be typing
    `authorized_by="resolver"` on an object the resolver never saw, which is the one sentence Lane
    A arranged its `Literal` so that nobody could type.
    """
    if call.step is None:
        raise AdapterError(
            f"the call for {call.operation!r} carries no resolved step. A real organ runs an "
            f"authorization; it does not reconstruct one from the fields around it.")
    if call.step.step_id != call.step_id or call.step.operation != call.operation:
        raise AdapterError(
            f"the call names step {call.step_id!r}/{call.operation!r} and carries "
            f"{call.step.step_id!r}/{call.step.operation!r}. Two steps in one call is not a state "
            f"this bridge will guess its way out of.")
    return call.step


def _merge_refusals(refusals: Sequence[RefusalRecord]) -> Optional[RefusalRecord]:
    """Several refusals of one code into one, keeping every name.

    `AdapterOutcome` carries one refusal and a façade may return several — five cited refs, two
    that did not resolve. They are merged rather than truncated because the whole reason
    `_resolve_refs` collects instead of raising is that a person who mistyped one of four ids
    should be told WHICH, and a bridge that kept only the first would undo that on the way out.
    Different codes cannot be merged, and then the first is returned and the rest are named in its
    detail — the honest report of a shape the seam cannot carry.
    """
    if not refusals:
        return None
    if len(refusals) == 1:
        return refusals[0]
    codes = {r.code for r in refusals}
    first = refusals[0]
    if len(codes) == 1:
        missing: List[str] = []
        for refusal in refusals:
            missing.extend(m for m in refusal.missing if m not in missing)
        return first.model_copy(update={
            "message": " ".join(r.message for r in refusals),
            "missing": missing,
            "detail": {**dict(first.detail or {}),
                       "also": [dict(r.detail or {}) for r in refusals[1:]]}})
    return first.model_copy(update={
        "detail": {**dict(first.detail or {}),
                   "further_refusals": [{"code": r.code.value, "message": r.message}
                                        for r in refusals[1:]]}})


def _blocks(artifact: PerceptualArtifact) -> Tuple[ArtifactMeasurement,
                                                   Optional[ArtifactProjection],
                                                   Optional[ArtifactInterpretation]]:
    """The three blocks the organ owns, lifted off the artifact it also built.

    Deep copies, because the façade's artifact is discarded immediately after and a shared payload
    would leave the ledger holding a reference into an object nothing else keeps alive.
    """
    return (artifact.measurement.model_copy(deep=True),
            artifact.projection.model_copy(deep=True) if artifact.projection else None,
            artifact.interpretation.model_copy(deep=True) if artifact.interpretation else None)


def _inner(detail: Optional[str], **facts: Any) -> str:
    """The stage's prose: what the organ said, plus its own numbers, labelled as its own.

    `inner_ms` rather than `duration_ms`, and in a string rather than a field, so there is exactly
    one number on this run that a reader could take for the run's duration.
    """
    parts = [detail] if detail else []
    parts.extend(f"{k}={v}" for k, v in facts.items() if v is not None)
    return "; ".join(parts) or "no detail"


# ── Extent ───────────────────────────────────────────────────────────────────


@dataclass
class ExtentBridge:
    """One declared Extent adapter, as the conductor sees it.

    ONE BRIDGE PER ADAPTER NAME, not one per organ, because the registry's organ firewall binds
    adapters to operations by name and the resolver's fifth gate picks a name. `sam3_concept` and
    `grounded_sam` both serve `extent.find_named`, and a deployment that has the second and not the
    first must be able to say so — which it can only do if they are two objects with two
    capability answers.

    THE RESOLVER'S CHOICE IS FORCED, not suggested. `extent._choose_adapter` walks the operation's
    declared adapters and takes the first one running; handing it a table containing ONLY the
    adapter the resolver named makes those two decisions the same decision. Otherwise the plan
    could say `grounded_sam` and the receipt say `sam3_concept`, and no reader could tell which of
    the two the numbers came from.
    """
    name: str
    operations: Tuple[str, ...]
    runtime: LabRuntime
    organ: str = OrganFamily.EXTENT.value

    def capability(self) -> CapabilityState:
        """What this deployment can say about this adapter, without pretending to know more.

        The caller's opinion first. Then the adapter's own, for the four that load a model. The
        rest — `human`, `canonical_region`, `lab_compare` — have nothing that could be absent, and
        `extent.default_adapters()` deliberately does not list them; an operation with no model
        behind it cannot be unavailable.
        """
        stated = self.runtime.capability_states.get(self.name)
        if stated is not None:
            return stated
        adapter = self._adapters().get(self.name)
        if adapter is None:
            return CapabilityState.AVAILABLE
        return adapter.capability()

    def _adapters(self) -> Mapping[str, Any]:
        if self.runtime.extent_adapters is not None:
            return self.runtime.extent_adapters
        return extent_facade.default_adapters()

    def _context(self, call: AdapterCall) -> extent_facade.ExtentContext:
        table = self._adapters()
        return extent_facade.ExtentContext(
            session_id=call.session_id, run_id=call.run_id,
            image_bytes=self.runtime.image_bytes,
            source_image_digest=call.source.image_digest,
            natural_width=call.source.natural_width,
            natural_height=call.source.natural_height,
            artifacts={a.identity.artifact_id: a
                       for found in call.inputs.values() for a in found},
            regions=self.runtime.regions_by_id,
            capability_states=dict(self.runtime.capability_states),
            # Only the adapter the resolver named. See the class docstring.
            adapters={self.name: table[self.name]} if self.name in table else {},
            now=self.runtime.now)

    def invoke(self, call: AdapterCall) -> AdapterOutcome:
        step = _step_of(call)
        call.cancel.raise_if_cancelled()
        context = self._context(call)

        # THE PICTURE IN HAND IS THE PICTURE THE SESSION NAMED, checked before anything measures
        # it. `ExtentContext.digest_matches` was written by Lane B and called by nothing; this is
        # the caller it was waiting for. The image behind a `photo_url` can be replaced while a
        # sitting is open, and a session that then measured the new one would attribute a
        # measurement of picture B to the digest of picture A — a wrong artifact that validates.
        if not context.digest_matches():
            return AdapterOutcome(
                state=StageState.REFUSED,
                refusal=RefusalRecord(
                    code=RefusalCode.SOURCE_MUTATED, organ=OrganFamily.EXTENT,
                    operation=call.operation,
                    message=D._message("source_mutated"),
                    missing=[call.source.image_digest],
                    remedy="re-open the session against the current source",
                    detail={"session_digest": call.source.image_digest,
                            "in_hand": context.image_digest()}),
                detail=_inner("the image behind this post is not the one this session opened on",
                              adapter=self.name))

        started = self.runtime.monotonic_ms()
        result = extent_facade.run(step, context)
        inner_ms = int(round(self.runtime.monotonic_ms() - started))
        return _extent_outcome(result, adapter=self.name, inner_ms=inner_ms)


def _extent_outcome(result: extent_facade.ExtentResult, *, adapter: str,
                    inner_ms: int) -> AdapterOutcome:
    """An `ExtentResult` in the conductor's vocabulary. Six endings, none of them collapsed.

    The stage state comes from the façade's own receipt where it made one, because the façade
    already decided the thing that is hard to decide: whether an empty list was a measured
    emptiness or an adapter that never ran. Re-deriving it here from the outcome would be a second
    opinion about the one distinction the whole lane exists to keep.
    """
    attempt = result.stage_attempt
    refusal = _merge_refusals(result.refusals)
    detail = _inner(attempt.detail if attempt else None, inner_ms=inner_ms, adapter=adapter,
                    organ_duration_ms=attempt.duration_ms if attempt else None)

    if not result.artifacts:
        if result.outcome is RunOutcome.FAILED:
            return AdapterOutcome(state=StageState.FAILED, detail=detail)
        if refusal is None:
            # A façade that produced nothing and refused nothing has no claim to report, and an
            # untyped nothing is what the contract's nine codes exist to prevent. `failed` is the
            # only honest reading: no claim is made about the image.
            return AdapterOutcome(
                state=StageState.FAILED,
                detail=_inner(f"{adapter} returned neither an artifact nor a refusal", inner_ms=inner_ms))
        state = (StageState.UNAVAILABLE
                 if refusal.code is RefusalCode.CAPABILITY_UNAVAILABLE else StageState.REFUSED)
        return AdapterOutcome(state=state, refusal=refusal, detail=detail)

    artifact = result.artifacts[0]
    measurement, projection, interpretation = _blocks(artifact)
    state = attempt.state if attempt is not None else (
        StageState.EMPTY if result.outcome is RunOutcome.EMPTY else StageState.COMPLETED)
    if state not in (StageState.COMPLETED, StageState.EMPTY):
        # `partial` — extents came back AND a reference did not resolve. The façade marks the
        # stage `refused` in that case; the conductor needs a producing state so the measurement
        # is kept, and the refusal travels beside it so the run ends `partial` rather than `ready`.
        state = StageState.COMPLETED
    provenance = artifact.provenance
    return AdapterOutcome(
        state=state, measurement=measurement, projection=projection,
        interpretation=interpretation, refusal=refusal,
        model=provenance.model, revision=provenance.revision, device=provenance.device,
        peak_memory_mb=provenance.peak_memory_mb, detail=detail)


# ── Topology ─────────────────────────────────────────────────────────────────


@dataclass
class TopologyBridge:
    """One declared Topology adapter. Geometry in, relations out, and nothing loadable.

    ALWAYS AVAILABLE, and honestly so: `nestedness_organ`, `adjacency_organ`, `mask_arithmetic`
    and `distance_transform` are arithmetic over masks this repository already ships. There is no
    weight file, no device and no import that can fail at runtime, so a capability state other than
    `available` would be a fabricated absence.

    IT NEVER RUNS EXTENT. Nothing in the module it calls can produce one — `topology.py` asserts
    its own forbidden-import list — and this bridge adds no seam. A topology step whose extents did
    not resolve refuses `missing_extent_inputs`, which is the visible half of isolation mode.

    IT NEVER RUNS DEPTH. `TopologyRequest.depth` is left `None` here, always. This deployment has
    no organ that produces a depth field, so `topology.occlusion` refuses `missing_depth_artifact`
    — and the conductor's execution-time input check usually refuses it one layer earlier, which is
    two gates for the seam that would be easiest to satisfy quietly.
    """
    name: str
    operations: Tuple[str, ...]
    runtime: LabRuntime
    organ: str = OrganFamily.TOPOLOGY.value

    def capability(self) -> CapabilityState:
        stated = self.runtime.capability_states.get(self.name)
        return stated if stated is not None else CapabilityState.AVAILABLE

    def _request(self, call: AdapterCall,
                 step: ResolvedStep) -> topology_facade.TopologyRequest:
        return topology_facade.TopologyRequest(
            operation=call.operation,
            context=topology_facade.LabContext(
                session_id=call.session_id, run_id=call.run_id, step_id=call.step_id,
                source_image_digest=call.source.image_digest, now=self.runtime.now(),
                device=self.runtime.device, clock=self.runtime.monotonic_ms),
            inputs=tuple(step.input_refs),
            parameters=dict(step.parameters),
            extents=tuple(a for found in call.inputs.values() for a in found),
            regions=tuple(self.runtime.regions),
            depth=None,
            current_region_revs=self.runtime.region_revs)

    def invoke(self, call: AdapterCall) -> AdapterOutcome:
        step = _step_of(call)
        call.cancel.raise_if_cancelled()
        started = self.runtime.monotonic_ms()
        result = topology_facade.run(self._request(call, step))
        inner_ms = int(round(self.runtime.monotonic_ms() - started))
        return _topology_outcome(result, adapter=self.name, operation=call.operation,
                                 inner_ms=inner_ms)


def _topology_outcome(result: topology_facade.TopologyResult, *, adapter: str, operation: str,
                      inner_ms: int) -> AdapterOutcome:
    """A `TopologyResult` in the conductor's vocabulary.

    THE ADAPTER NAME IS REPORTED TWICE ON PURPOSE, and the reason is a contradiction between two
    merged lanes rather than a choice made here. The contract declares `topology.all_pairs`'
    adapters as `[nestedness_organ, adjacency_organ, mask_arithmetic]` — three organs that
    COLLABORATE on one measurement — while the resolver reads every declared adapter list as
    alternatives and names the first. So the plan says `nestedness_organ` and the façade's own
    `PRIMARY_ADAPTER` says `mask_arithmetic`, and both are true of different halves of the same
    run. The conductor records the resolver's choice, which is what a person picked; this line puts
    the façade's beside it in the stage detail, so the receipt carries both rather than silently
    preferring one. See the Lane F1 report.

    `field_values` is dropped. A negative-space raster is tens of thousands of floats, the payload
    already carries its shape, truncation and statistics, and this lane has no blob store to put
    the field in. Saying so in the detail is better than a payload that is quietly a summary.
    """
    produced_by = topology_facade.PRIMARY_ADAPTER.get(operation)
    detail = _inner(
        (result.artifact.interpretation.notes
         if result.artifact is not None and result.artifact.interpretation else None),
        inner_ms=inner_ms, adapter=adapter,
        produced_by=produced_by if produced_by != adapter else None,
        field_values="withheld — the payload carries the shape and statistics"
        if result.field_values is not None else None)

    if result.refusal is not None:
        state = (StageState.UNAVAILABLE
                 if result.refusal.code is RefusalCode.CAPABILITY_UNAVAILABLE
                 else StageState.REFUSED)
        return AdapterOutcome(state=state, refusal=result.refusal, detail=detail)
    if result.artifact is None:
        return AdapterOutcome(
            state=StageState.FAILED,
            detail=_inner(f"{adapter} produced neither an artifact nor a refusal",
                          inner_ms=inner_ms))

    measurement, projection, interpretation = _blocks(result.artifact)
    return AdapterOutcome(
        state=StageState.EMPTY if result.outcome is RunOutcome.EMPTY else StageState.COMPLETED,
        measurement=measurement, projection=projection, interpretation=interpretation,
        model=None, revision=result.artifact.provenance.revision,
        device=result.artifact.provenance.device, detail=detail)


# ── the registry ─────────────────────────────────────────────────────────────


class LiveAdapterRegistry(AdapterRegistry):
    """The registry the live conductor holds, with capability states that are asked rather than
    assumed.

    `AdapterRegistry.capabilities()` reports `available` for everything registered, which is right
    for a table of fakes and wrong for a machine where SAM 3 may not be installed. This subclass
    asks each registered adapter, and the resolver's fifth gate then does what it was written to
    do: walk `extent.find_named`'s declared adapters, skip `sam3_concept` because it said
    `unavailable`, and choose `grounded_sam` — with the receipt naming the one that ran.

    UNREGISTERED ADAPTERS STAY UNSPOKEN. They are absent from the map, which reads as
    `unknown_until_runtime`, exactly as the base class insists: a registry that has not been asked
    about an adapter is not a registry that found it missing.
    """

    identity: ExecutionIdentity = ExecutionIdentity.LIVE

    def capabilities(self) -> Mapping[str, CapabilityState]:
        out: Dict[str, CapabilityState] = {}
        for name, adapter in self._names.items():
            asked = getattr(adapter, "capability", None)
            out[name] = asked() if callable(asked) else CapabilityState.AVAILABLE
        return out


def _adapters_by_name(family: str) -> Dict[str, Tuple[str, ...]]:
    """`{adapter_name: (operation, …)}` for one organ, read off the contract.

    Built from the declared registry rather than hand-listed, so an adapter added to an operation
    is wired here by the file that declared it. A hand list would drift on exactly the day somebody
    added the second segmenter, and would drift silently.
    """
    out: Dict[str, List[str]] = {}
    for op in D.operations_for(family):
        for name in op.adapters:
            out.setdefault(name, []).append(op.key)
    return {name: tuple(keys) for name, keys in out.items()}


def live_registry(runtime: LabRuntime) -> LiveAdapterRegistry:
    """Every declared adapter of the two live organs, bridged to the façade that runs it.

    The six disabled organs get nothing, because `D.operations_for` returns their operations and
    `AdapterRegistry.register` would bind them — a control a person could press that reaches an
    organ this phase does not have. They are excluded by name here and the exclusion is asserted in
    the suite.
    """
    registry = LiveAdapterRegistry()
    for name, ops in sorted(_adapters_by_name(OrganFamily.EXTENT.value).items()):
        registry.register(ExtentBridge(name=name, operations=ops, runtime=runtime))
    for name, ops in sorted(_adapters_by_name(OrganFamily.TOPOLOGY.value).items()):
        registry.register(TopologyBridge(name=name, operations=ops, runtime=runtime))
    return registry


__all__ = ["LIVE_ORGANS", "LabRuntime", "ExtentBridge", "TopologyBridge", "LiveAdapterRegistry",
           "live_registry"]
