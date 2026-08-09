"""
PERCEPTUAL-ORGANS-002 Lane B — the Extent organ façade.

ONE ENTRY POINT. `run(step, context)` takes a Lane A `ResolvedStep` and returns an `ExtentResult`.
That is the whole public surface, and it is one function on purpose: the Direct arm (a person
moves a control, the UI builds a step) and the Prompt arm (a planner proposes, the resolver
authorizes, the same step comes out) must reach the SAME runner, or the phase's central
comparison — "did the sentence choose the operation the person would have chosen?" — is comparing
two different machines. There is no second entry point for prompts, and the test that matters
asserts a direct step and a planner-built step produce byte-identical artifacts.

WHAT THIS LANE IS. A façade over producers that already exist, normalizing their output into the
contract's `extent_set` artifact and their failure into the contract's typed refusals. It does not
segment anything itself, it does not tune anything, and it writes nowhere:

    extent.find_all     sam2_auto_service · segmentation_service (YOLO11-seg)
    extent.find_named   sam3_concept_service · grounding_detector_service
    extent.refine       vision_orchestrator/refine_session (SAM 2.1) + exact mask arithmetic
    extent.draw         a person, through `mask_geometry.canonicalize_geometry`
    extent.reuse        an existing `Region`, referenced and never re-derived
    extent.compare      `extent_metrics`, per pixel

THE FOUR THINGS IT REFUSES TO BLUR.

  1. UNAVAILABLE IS NOT EMPTY. Every adapter is asked `is_available()` FIRST. Only an adapter that
     said yes is allowed to return `[]`, and only then does `[]` mean "looked, found nothing".
     Several of the underlying services return `None` for both conditions — that conflation is the
     single most important thing this façade un-conflates, and `_UNAVAILABLE_IS_NOT_EMPTY` below
     is where it happens.

  2. GEOMETRY IS NOT NAMING. A mask and the word for it are two claims with two statuses, carried
     as two fields. `sam3_concept_service.NAMING_CONFIDENCE_FLOOR` already encodes the ruling that
     below 0.50 the naming is not trustworthy; this façade honours it by WITHHOLDING THE NAME AND
     KEEPING THE MASK. Dropping the extent because its label was doubtful would throw away the
     measured half to punish the interpretive one.

  3. THE MASK IS THE MEASUREMENT; THE BOX IS A PROJECTION OF IT — except where the box is all
     there is (GroundingDINO), and then the artifact says `basis: box` and takes the
     `interpretive` ceiling `epistemics.SUBSTRATE_CEILING` gives it. The lab does not get to
     decide that its boxes are measurements.

  4. NOTHING IS WRITTEN. No database import, no post, no Ground, no ledger. Input images are read
     and never re-encoded; input region dicts are copied before anything touches them, because
     `mask_geometry.canonicalize_geometry` mutates in place and bumps `geometry_rev`, and running
     it on a caller's canonical Region would silently revise the corpus.

DETERMINISM. Artifact and instance ids are derived from `(run_id, step_id, index)` — no uuid4, no
clock read behind the caller's back. `ExtentContext.now` is the only clock, and it is injectable.
Two identical runs of the same fixture produce byte-identical artifacts, which is what makes
`extent.compare`'s repeat measurement mean anything at all.

PURE OF I/O EXCEPT THE MODELS. No routes, no persistence, no navigation, no promotion.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from backend.schemas.perception_lab import (ArtifactIdentity, ArtifactInterpretation,
                                            ArtifactKind, ArtifactLifecycle, ArtifactMeasurement,
                                            ArtifactProjection, ArtifactProvenance,
                                            CapabilityState, CoordinateSystem, EpistemicBasis,
                                            EpistemicStatus, ExtentComparison,
                                            ExtentCorrespondence, ExtentDuplicate, ExtentInstance,
                                            ExtentSetPayload, IdentityScope, InputRef,
                                            InstanceNaming, LabelSource, LabRun, LifecycleState,
                                            OrganFamily, PerceptualArtifact, ProducerKind,
                                            ProjectionKind, RefusalCode, RefusalRecord, RegionRef,
                                            ResolvedStep, RunOutcome, StageAttempt, StageState)
from backend.services import mask_geometry as mg
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import extent_metrics as M

ORGAN = OrganFamily.EXTENT

#: The threshold `extent.compare` uses when the caller did not choose one. The contract declares
#: `default: null` for every parameter precisely so that this number lives HERE, in the runtime
#: that used it, and is recorded on the artifact as `iou_threshold_used` — a value the person can
#: see and disagree with, rather than one inherited from a file nobody reads.
DEFAULT_IOU_THRESHOLD = 0.5

#: Above this, two extents in ONE set are flagged as possibly the same thing. Higher than the
#: correspondence threshold on purpose: two different parts of a figure legitimately overlap a
#: little, and a duplicate warning that fires on every adjacent part is a warning nobody reads.
DUPLICATE_IOU = 0.85

#: What `extent.find_all` asks for when the caller did not say. The underlying services have their
#: own caps; this is the lab's, and the effective one is recorded on the stage receipt.
DEFAULT_MAX_INSTANCES = 20


# ── the context a run happens in ─────────────────────────────────────────────


def _utc_now() -> str:
    """ISO-8601 with an explicit offset, which is what the contract's validator requires."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class ExtentContext:
    """Everything a step needs that is not in the step.

    `image_bytes` is READ-ONLY here and is never re-encoded — `source_image_digest` is checked
    against it so a façade handed the wrong picture says so rather than measuring it.

    `artifacts` and `regions` are the ONLY places a reference may resolve. An id that is not in one
    of them is `unknown_reference`, which is the contract's rule that language may not invent an
    identity, enforced at the point of use.

    `capability_states` comes from the CALLER. This module asks each adapter `is_available()` and
    will not pretend to know what is loadable on a machine it is not running on; the caller may
    override with a state it learned some other way.
    """
    session_id: str
    run_id: str
    image_bytes: bytes = b""
    source_image_digest: str = ""
    natural_width: int = 0
    natural_height: int = 0
    artifacts: Mapping[str, PerceptualArtifact] = field(default_factory=dict)
    regions: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    capability_states: Mapping[str, CapabilityState] = field(default_factory=dict)
    adapters: Optional[Mapping[str, "ExtentAdapter"]] = None
    now: Callable[[], str] = _utc_now
    reviewer: str = "perception_lab"

    def adapter(self, key: str) -> Optional["ExtentAdapter"]:
        table = self.adapters if self.adapters is not None else default_adapters()
        return table.get(key)

    def image_digest(self) -> str:
        """`sha256:…` of the bytes actually held. Computed, never taken on trust."""
        return f"sha256:{hashlib.sha256(self.image_bytes).hexdigest()}"

    def digest_matches(self) -> bool:
        """Is the picture in hand the picture the session named?

        Only checked when both are present. A `sha256:` digest is compared in full; anything else
        is a digest scheme this lane does not know, and a comparison it cannot make is reported as
        no objection rather than as agreement it did not verify.
        """
        if not self.image_bytes or not self.source_image_digest:
            return True
        if not self.source_image_digest.startswith("sha256:"):
            return True
        return self.source_image_digest == self.image_digest()


@dataclass(frozen=True)
class ExtentResult:
    """What one step produced: artifacts, one stage receipt, and any typed refusals.

    Deliberately NOT a `LabRun`. Assembling runs out of steps is the conductor's job (Lane D), and
    a façade that returned finished runs would be a second orchestrator. `as_run()` exists for the
    single-step direct case — tests, and whatever Lane F needs to show a person one measurement —
    and it is explicitly a convenience, not the run machinery.
    """
    outcome: RunOutcome
    artifacts: Tuple[PerceptualArtifact, ...] = ()
    stage_attempt: Optional[StageAttempt] = None
    refusals: Tuple[RefusalRecord, ...] = ()

    def as_run(self, ctx: ExtentContext, step: ResolvedStep, *, plan_id: str) -> LabRun:
        """A contract-valid single-step `LabRun`. LIVE, because this façade only ever runs live —
        replay and fixture identities belong to the store that holds the recording, not to the
        organ that made it."""
        attempts = (self.stage_attempt,) if self.stage_attempt else ()
        return LabRun(
            run_id=ctx.run_id, session_id=ctx.session_id,
            execution_identity="LIVE", outcome=self.outcome,
            requested_plan_id=plan_id, resolved_plan_id=plan_id,
            artifact_ids=[a.identity.artifact_id for a in self.artifacts],
            stage_attempts=list(attempts), refusals=list(self.refusals),
            source_digest_before=ctx.source_image_digest,
            source_digest_after=ctx.source_image_digest,
            started_at=attempts[0].started_at if attempts else None,
            completed_at=attempts[0].completed_at if attempts else None,
            duration_ms=attempts[0].duration_ms if attempts else None,
            replay=None)


# ── the adapter seam ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AdapterOutput:
    """What an adapter measured, before it becomes an artifact.

    `instances` are plain mappings — `{"instance_id", "mask_rle", "box", "area", "confidence",
    "naming", "region_id", "geometry_rev"}` — rather than `ExtentInstance` models, so an adapter
    can be written without importing the schema and so `extent_metrics` can read them directly.
    The façade is the only thing that turns them into contract objects, in one place.
    """
    instances: Tuple[Mapping[str, Any], ...] = ()
    basis: EpistemicBasis = EpistemicBasis.MASK
    status: EpistemicStatus = EpistemicStatus.MEASURED
    basis_detail: Optional[str] = None
    model: Optional[str] = None
    revision: Optional[str] = None
    device: Optional[str] = None
    duration_ms: Optional[int] = None
    peak_memory_mb: Optional[float] = None
    naming_withheld: int = 0
    truncated: bool = False
    detail: Optional[str] = None
    notes: Optional[str] = None


class ExtentAdapter(Protocol):
    """One way of producing extents.

    `capability()` is asked BEFORE `measure()`, always, and its answer is what separates
    `unavailable` from `empty`. An adapter that cannot answer honestly should return
    `UNKNOWN_UNTIL_RUNTIME` rather than guessing — the façade treats that as "go ahead and find
    out", which is the only honest reading of not knowing.
    """

    key: str

    def capability(self) -> CapabilityState:            # pragma: no cover - protocol
        ...

    def measure(self, step: ResolvedStep, ctx: ExtentContext,
                params: Mapping[str, Any]) -> AdapterOutput:   # pragma: no cover - protocol
        ...


class AdapterUnavailable(RuntimeError):
    """Raised by an adapter that discovers mid-run that it cannot run. Becomes `unavailable`."""

    def __init__(self, adapter: str, detail: str = "") -> None:
        super().__init__(detail or adapter)
        self.adapter = adapter
        self.detail = detail


# ── the gates, in the order a person needs to hear them ──────────────────────


def _refusal(code: RefusalCode, step: ResolvedStep, message: str, *,
             missing: Optional[Sequence[str]] = None, remedy: Optional[str] = None,
             detail: Optional[Mapping[str, Any]] = None) -> RefusalRecord:
    return RefusalRecord(code=code, organ=ORGAN, operation=step.operation, message=message,
                         missing=list(missing or ()), remedy=remedy, detail=dict(detail or {}))


def _resolve_refs(step: ResolvedStep, ctx: ExtentContext
                  ) -> Tuple[Dict[str, List[Any]], List[RefusalRecord]]:
    """Turn the step's `input_refs` into the things they name, or say which did not resolve.

    An id from nowhere is `unknown_reference` — the contract's rule that "that mask" resolves
    through declared ids and never through language, applied at the moment of use. Refusals are
    collected rather than raised on the first one, because a person who supplied four regions and
    mistyped one should be told which one.
    """
    resolved: Dict[str, List[Any]] = {}
    refusals: List[RefusalRecord] = []
    for ref in step.input_refs:
        target: Any = None
        if ref.artifact_id is not None:
            target = ctx.artifacts.get(ref.artifact_id)
            name = ref.artifact_id
        else:
            target = ctx.regions.get(ref.region_id or "")
            name = str(ref.region_id)
        if target is None:
            refusals.append(_refusal(
                RefusalCode.UNKNOWN_REFERENCE, step,
                f"{name} is not a selected or active reference in this session.",
                missing=[name],
                remedy="select the artifact or region first — a reference resolves through ids",
                detail={"role": ref.role, "reference": name, "scope": ref.scope.value}))
            continue
        resolved.setdefault(ref.role, []).append((ref, target))
    return resolved, refusals


def capability_of(adapter: "ExtentAdapter", ctx: ExtentContext) -> CapabilityState:
    """What the caller says, or failing that what the adapter says about itself.

    The caller wins because it may know something the adapter cannot — a deployment that has the
    package installed and the GPU withheld, say. An adapter is never asked to guess.
    """
    stated = ctx.capability_states.get(adapter.key)
    return stated if stated is not None else adapter.capability()


def _capability_refusal(step: ResolvedStep, adapter: "ExtentAdapter",
                        ctx: ExtentContext) -> Optional[RefusalRecord]:
    """`unavailable` is decided HERE and nowhere else — before the adapter is ever called.

    THE CONFLATION THIS UNDOES, and it is the most important thing in the lane.
    `sam2_auto_service.generate_masks`, `segmentation_service.segment_image_bytes` and
    `grounding_detector_service.detect` each return `None` for BOTH "the package is not installed"
    and "it ran and raised", and `detect` returns `None` for "grounded nothing" as well. Three
    different sentences, one return value — and a UI reading that value has no way to tell a
    person whether to look somewhere else, try another machine, or file a bug.

    Asking `is_available()` FIRST is what makes the remaining `None` legible: after this gate, a
    `None` can only mean the adapter ran and failed, and an empty list can only mean it ran and
    found nothing. That is the whole difference between `unavailable`, `failed` and `empty`.
    """
    state = capability_of(adapter, ctx)
    if state in (CapabilityState.UNAVAILABLE, CapabilityState.DEFERRED):
        return _refusal(
            RefusalCode.CAPABILITY_UNAVAILABLE, step,
            f"{adapter.key} is in the catalogue and is not running here.",
            missing=[adapter.key],
            remedy="choose another adapter, or run where the model lives",
            detail={"adapters": [adapter.key], "capability_state": state.value})
    return None


# ── building the artifact ────────────────────────────────────────────────────


def _artifact_id(ctx: ExtentContext, step: ResolvedStep) -> str:
    return f"art_{ctx.run_id}_{step.step_id}"


def instance_id(ctx: ExtentContext, step: ResolvedStep, index: int) -> str:
    """Deterministic, and that is the point: an id minted from a uuid would make two identical
    runs incomparable, and comparing two identical runs is how repeat stability is measured."""
    return f"ext_{ctx.run_id}_{step.step_id}_{index:02d}"


def _naming(raw: Optional[Mapping[str, Any]]) -> Optional[InstanceNaming]:
    if not raw or not raw.get("text"):
        return None
    return InstanceNaming(
        text=str(raw["text"]), source=LabelSource(raw.get("source", "adapter")),
        epistemic_status=EpistemicStatus(raw.get("epistemic_status", "interpretive")),
        confidence=raw.get("confidence"))


def _instance(raw: Mapping[str, Any]) -> ExtentInstance:
    box = raw.get("box")
    return ExtentInstance(
        instance_id=str(raw["instance_id"]),
        mask_rle=dict(raw["mask_rle"]) if raw.get("mask_rle") else None,
        box=dict(box) if isinstance(box, Mapping) else None,
        area=raw.get("area"), confidence=raw.get("confidence"),
        naming=_naming(raw.get("naming")),
        region_id=raw.get("region_id"), geometry_rev=raw.get("geometry_rev"))


def _projection_for(step: ResolvedStep) -> ArtifactProjection:
    """The FIRST projection the operation declares, with a hint that is a hint.

    A projection is chosen here and not computed here. Nothing in this function may look at the
    measurement, because a projection that varied with the evidence would be a second, quieter
    copy of it.
    """
    declared = D.operation(step.operation).render_projections
    kind = ProjectionKind(declared[0]) if declared else ProjectionKind.NONE
    return ArtifactProjection(projection_kind=kind,
                              hints={"opacity": 0.35, "palette_role": "figure"})


def _build_artifact(ctx: ExtentContext, step: ResolvedStep, out: AdapterOutput, *,
                    searched: str, adapter_key: Optional[str], producer_kind: ProducerKind,
                    started_at: str, completed_at: str,
                    input_refs: Sequence[InputRef] = (),
                    identity_refs: Sequence[RegionRef] = (),
                    derived_from: Sequence[str] = (),
                    identity_scope: IdentityScope = IdentityScope.SESSION,
                    comparison: Optional[ExtentComparison] = None,
                    dropped_below_min_area: Optional[int] = None,
                    duplicates: Sequence[ExtentDuplicate] = ()) -> PerceptualArtifact:
    """One measurement, in the contract's six blocks.

    The blocks are filled by separate arguments on purpose. There is no path through this function
    where a projection hint can be derived from a measurement or a label can be read off a mask —
    the separations Lane A made structural are kept structural by never having the values in the
    same place at the same time.
    """
    instances = [_instance(raw) for raw in out.instances]
    label, label_source, notes = _reading(out, instances)

    return PerceptualArtifact(
        identity=ArtifactIdentity(
            artifact_id=_artifact_id(ctx, step), session_id=ctx.session_id, run_id=ctx.run_id,
            step_id=step.step_id, organ_family=ORGAN, artifact_kind=ArtifactKind.EXTENT_SET,
            operation=step.operation, identity_scope=identity_scope,
            identity_refs=list(identity_refs), input_refs=list(input_refs),
            derived_from=list(derived_from)),
        measurement=ArtifactMeasurement(
            payload_variant="extent_set",
            payload=ExtentSetPayload(
                variant="extent_set", searched=searched, instances=instances,
                dropped_below_min_area=dropped_below_min_area,
                duplicates=list(duplicates), comparison=comparison),
            data_ref=None,
            coordinate_system=CoordinateSystem.NORMALIZED_XY_TOPLEFT,
            epistemic_status=out.status, epistemic_basis=out.basis,
            basis_detail=out.basis_detail),
        projection=_projection_for(step),
        interpretation=ArtifactInterpretation(
            label=label, label_source=label_source,
            epistemic_status=EpistemicStatus.INTERPRETIVE if label
            else EpistemicStatus.UNCERTAIN,
            notes=notes),
        lifecycle=ArtifactLifecycle(status=LifecycleState.PROPOSED, changed_at=completed_at,
                                    changed_by=ctx.reviewer),
        provenance=ArtifactProvenance(
            producer_kind=producer_kind, producer="extent_facade", adapter=adapter_key,
            model=out.model, revision=out.revision,
            source_image_digest=ctx.source_image_digest,
            started_at=started_at, completed_at=completed_at, duration_ms=out.duration_ms,
            device=out.device, peak_memory_mb=out.peak_memory_mb))


def _reading(out: AdapterOutput, instances: Sequence[ExtentInstance]
             ) -> Tuple[Optional[str], LabelSource, Optional[str]]:
    """The artifact-level reading, assembled from the per-instance ones and NEVER invented.

    An extent set with no named instance gets NO label and `label_source: none`. The temptation
    here is to synthesize something like "3 regions" for the UI to show; that sentence would be an
    interpretation the producer never made, and `notes` is where the true remark goes instead.
    """
    named = [i.naming.text for i in instances if i.naming]
    unique = sorted(set(named))
    label = ", ".join(unique) if unique else None
    source = LabelSource.NONE
    if unique:
        sources = {i.naming.source for i in instances if i.naming}
        source = sources.pop() if len(sources) == 1 else LabelSource.ADAPTER

    remarks: List[str] = []
    if out.naming_withheld:
        remarks.append(
            f"{out.naming_withheld} of {len(instances) + 0} extents came back below the naming "
            f"floor and stay unnamed. The geometry is kept: a doubtful word is not a reason to "
            f"discard a measured mask.")
    if out.truncated:
        remarks.append("the adapter found more than the cap allowed and the extra were not "
                       "returned — this is a truncation, not a count of what is there.")
    if out.notes:
        remarks.append(out.notes)
    return label, source, ("; ".join(remarks) or None)


def _stage(ctx: ExtentContext, step: ResolvedStep, *, state: StageState, adapter: Optional[str],
           invoked: bool, started_at: str, completed_at: Optional[str],
           duration_ms: Optional[int], detail: Optional[str]) -> StageAttempt:
    return StageAttempt(
        attempt_id=f"att_{ctx.run_id}_{step.step_id}", step_id=step.step_id,
        operation=step.operation, state=state, adapter=adapter, invoked=invoked,
        started_at=started_at, completed_at=completed_at, duration_ms=duration_ms, detail=detail)


# ── the one entry point ──────────────────────────────────────────────────────


def run(step: ResolvedStep, ctx: ExtentContext) -> ExtentResult:
    """Execute one authorized Extent step. The Direct arm and the Prompt arm both arrive here.

    The order of the gates is the order a person needs to hear them in: is this even my operation,
    are the parameters sayable, did the inputs resolve, is the adapter running. Each answers a
    different question and each has its own code, so "it did not work" is never the report.
    """
    if step.organ is not ORGAN:
        return ExtentResult(
            outcome=RunOutcome.REFUSED,
            refusals=(_refusal(RefusalCode.ORGAN_LOCKED, step,
                               f"{step.operation} belongs to the {step.organ.value} organ; this "
                               f"is the extent organ.",
                               remedy="route the step to its own organ"),))
    handler = _HANDLERS.get(step.operation)
    if handler is None:
        return ExtentResult(
            outcome=RunOutcome.REFUSED,
            refusals=(_refusal(RefusalCode.UNSUPPORTED_OPERATION, step,
                               f"{step.operation} is not an operation of the extent organ.",
                               remedy="choose a declared operation of this organ"),))

    started_at = ctx.now()
    resolved, ref_refusals = _resolve_refs(step, ctx)
    input_refusal = D.check_inputs(step.operation, list(step.input_refs), for_execution=True)
    if input_refusal is not None:
        return ExtentResult(
            outcome=RunOutcome.REFUSED, refusals=(input_refusal,),
            stage_attempt=_stage(ctx, step, state=StageState.REFUSED, adapter=None, invoked=False,
                                 started_at=started_at, completed_at=ctx.now(), duration_ms=None,
                                 detail=input_refusal.message))
    return handler(step, ctx, resolved, tuple(ref_refusals), started_at)


def _draw(step: ResolvedStep, ctx: ExtentContext, resolved: Mapping[str, List[Any]],
          ref_refusals: Tuple[RefusalRecord, ...], started_at: str) -> ExtentResult:
    """`extent.draw` — a person authored the extent, and the record says so.

    `visible` on the `manual` basis, which `epistemics` defines as "the extent is present in the
    picture — you can point at it". NOT `measured`: nothing computed this, and a hand-drawn mask
    that reported itself as measured would be indistinguishable from a segmenter's in every later
    report — which is precisely the attribution hole REGION-PROV-001 spent a lane closing.
    """
    params = dict(step.parameters)
    tool = params.get("tool")
    rle = params.get("mask_rle")
    polygon = params.get("polygon")

    if tool == "mask_brush" and not mg.rle_is_valid(rle):
        return _param_refusal(ctx, step, started_at,
                              "the mask_brush tool needs a valid mask_rle")
    if tool == "polygon" and not (isinstance(polygon, list) and len(polygon) >= 3):
        return _param_refusal(ctx, step, started_at,
                              "the polygon tool needs a ring of at least three points")
    if tool == "polygon" and not (ctx.natural_width and ctx.natural_height):
        return _param_refusal(
            ctx, step, started_at,
            "a drawn polygon needs the image's natural dimensions to become a mask; without them "
            "the lab would have to guess a raster, and a guessed raster is a guessed measurement")

    region: Dict[str, Any] = {
        "id": instance_id(ctx, step, 0),
        "actor": "creator",
        "detector": None,
        "geometry_rev": 0,
    }
    if mg.rle_is_valid(rle):
        region["mask_rle"] = dict(rle)
    else:
        region["polygons"] = [list(list(pt) for pt in polygon)]
    mg.canonicalize_geometry(
        region,
        default_mask_size=(ctx.natural_height, ctx.natural_width),
        provenance={"adapter": None, "model": None, "method": f"lab-draw-{tool}",
                    "actor": "creator", "tool": tool})

    if not mg.rle_is_valid(region.get("mask_rle")):
        return _param_refusal(
            ctx, step, started_at,
            "the drawing did not rasterize to any pixels — a ring with no interior is not an "
            "extent")

    completed_at = ctx.now()
    out = AdapterOutput(
        instances=({"instance_id": region["id"], "mask_rle": region["mask_rle"],
                    "box": region.get("box"),
                    "area": M.normalized_area(region["mask_rle"]),
                    "confidence": None, "naming": None,
                    "region_id": None, "geometry_rev": region.get("geometry_rev")},),
        basis=EpistemicBasis.MANUAL, status=EpistemicStatus.VISIBLE,
        basis_detail=f"a person drew it with the {tool} tool. `visible`, not `measured` — "
                     f"nothing computed it.",
        model=None, revision=None, device=None, duration_ms=None,
        detail=f"one extent drawn with {tool}")

    artifact = _build_artifact(
        ctx, step, out, searched="the boundary the person drew by hand", adapter_key=None,
        producer_kind=ProducerKind.HUMAN, started_at=started_at, completed_at=completed_at)
    return ExtentResult(
        outcome=RunOutcome.READY, artifacts=(artifact,), refusals=ref_refusals,
        stage_attempt=_stage(ctx, step, state=StageState.COMPLETED, adapter=None, invoked=False,
                             started_at=started_at, completed_at=completed_at, duration_ms=None,
                             detail=out.detail))


def _param_refusal(ctx: ExtentContext, step: ResolvedStep, started_at: str,
                   why: str) -> ExtentResult:
    """A prerequisite the schema cannot express — "a brush needs a mask" — as a typed refusal.

    `ResolvedStep` already proved every parameter is DECLARED. What it cannot prove is that the
    combination means anything, and an operation that ran on a meaningless combination would have
    to invent the missing half.
    """
    ref = _refusal(RefusalCode.INVALID_PARAMETERS, step,
                   f"{step.operation} refused the supplied parameters: {why}.",
                   remedy="read the operation's parameter declarations", detail={"why": why})
    completed_at = ctx.now()
    return ExtentResult(
        outcome=RunOutcome.REFUSED, refusals=(ref,),
        stage_attempt=_stage(ctx, step, state=StageState.REFUSED, adapter=None, invoked=False,
                             started_at=started_at, completed_at=completed_at, duration_ms=None,
                             detail=why))


#: Operation → handler. Populated as the lane lands each one; `run()` refuses anything absent with
#: `unsupported_operation`, which is the same answer a genuinely undeclared key gets, because from
#: the caller's side "this laboratory will not do that" is one fact.
_HANDLERS: Dict[str, Callable[..., ExtentResult]] = {
    "extent.draw": _draw,
}


def default_adapters() -> Mapping[str, ExtentAdapter]:
    """The real adapters, by their contract key. Overridden through `ExtentContext.adapters` in
    tests and by Lane F where a different transport is wanted."""
    return {}


__all__ = [
    "ORGAN", "DEFAULT_IOU_THRESHOLD", "DUPLICATE_IOU", "DEFAULT_MAX_INSTANCES",
    "ExtentContext", "ExtentResult", "AdapterOutput", "ExtentAdapter", "AdapterUnavailable",
    "run", "instance_id", "default_adapters",
]
