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

  1. UNAVAILABLE IS NOT EMPTY. Every adapter is asked `is_available()` FIRST, in
     `_capability_refusal` / `_choose_adapter`, before it is called. Only an adapter that said yes
     is allowed to return `[]`, and only then does `[]` mean "looked, found nothing". Several of
     the underlying services return `None` for both conditions, and un-conflating that is the
     single most load-bearing thing in this file.

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
from dataclasses import dataclass, field, replace
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
from backend.services.sam3_concept_service import NAMING_CONFIDENCE_FLOOR as NAMING_FLOOR

ORGAN = OrganFamily.EXTENT

#: THE LAB HAS ONE NAMING FLOOR AND IT IS NOT A NEW NUMBER. `sam3_concept_service` carries the one
#: SF-004-R2 measured — 0.50, below which naming stopped tracking correctness — and every named
#: adapter here is held to it. Retyping the value would have created a second operating point that
#: drifts from the measured one silently, which is the whole reason it is imported rather than
#: declared. The import is safe at module load: that service's own heavy dependencies are lazy.

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

    return _finish(step, ctx, out, searched="the boundary the person drew by hand",
                   adapter_key=None, producer_kind=ProducerKind.HUMAN, started_at=started_at,
                   invoked=False, ref_refusals=ref_refusals)


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


# ── choosing an adapter, and saying so when there is none ────────────────────


def _choose_adapter(step: ResolvedStep, ctx: ExtentContext
                    ) -> Tuple[Optional[ExtentAdapter], Optional[RefusalRecord]]:
    """The adapter the caller asked for, or the first declared one that is actually running.

    The contract gives `adapter` no default, and this is why: absence means "you choose, and write
    down what you chose". The choice is recorded on the artifact's provenance, so a person reading
    a result never has to infer which model produced it from how the numbers look.

    An adapter that is UNAVAILABLE is skipped rather than refused, until none is left — a
    deployment with SAM 3 missing and Grounded-SAM present should get Grounded-SAM and a receipt
    saying so, not a refusal it could have avoided.
    """
    op = D.operation(step.operation)
    requested = step.parameters.get("adapter")
    keys: Sequence[str] = (str(requested),) if requested else op.adapters
    tried: List[Dict[str, str]] = []
    for key in keys:
        adapter = ctx.adapter(key)
        if adapter is None:
            tried.append({"adapter": key, "state": "not registered in this runtime"})
            continue
        state = capability_of(adapter, ctx)
        if state in (CapabilityState.UNAVAILABLE, CapabilityState.DEFERRED):
            tried.append({"adapter": key, "state": state.value})
            continue
        return adapter, None
    return None, _refusal(
        RefusalCode.CAPABILITY_UNAVAILABLE, step,
        f"{', '.join(str(k) for k in keys)} is in the catalogue and is not running here.",
        missing=[str(k) for k in keys],
        remedy="choose another adapter, or run where the model lives",
        detail={"adapters": [str(k) for k in keys], "tried": tried})


@dataclass(frozen=True)
class _Invocation:
    """Either an adapter and what it measured, or a finished result that ended before that.

    Split out of the measure path so `extent.refine` can invoke SAM 2.1 and then do its own exact
    mask arithmetic before an artifact exists. Without the split, refine would either duplicate the
    capability/failure handling or push the arithmetic into the adapter — and the arithmetic is the
    lab's, not the model's.
    """
    adapter: Optional[ExtentAdapter] = None
    out: Optional[AdapterOutput] = None
    terminal: Optional[ExtentResult] = None


def _invoke(step: ResolvedStep, ctx: ExtentContext, params: Mapping[str, Any], started_at: str,
            ref_refusals: Tuple[RefusalRecord, ...]) -> _Invocation:
    """Capability gate, then the call. Ends the step itself on `unavailable` or `failed`.

    THE TWO ENDINGS THAT STOP HERE:

        unavailable  the gate said no. The adapter was NEVER CALLED and `invoked` is false, which
                     is the field a reader uses to tell a refusal from a failure.
        failed       it was called and raised. No claim is made about the image, and `duration_ms`
                     stays null because nothing completed to be measured — 0 would report a fast
                     failure where there was an unmeasured one.
    """
    adapter, refusal = _choose_adapter(step, ctx)
    if adapter is None or refusal is not None:
        completed_at = ctx.now()
        return _Invocation(terminal=ExtentResult(
            outcome=RunOutcome.UNAVAILABLE, refusals=(refusal,) + ref_refusals,
            stage_attempt=_stage(ctx, step, state=StageState.UNAVAILABLE,
                                 adapter=(refusal.missing or [None])[0], invoked=False,
                                 started_at=started_at, completed_at=completed_at,
                                 duration_ms=None, detail=refusal.message)))
    try:
        out = adapter.measure(step, ctx, params)
    except AdapterUnavailable as exc:
        completed_at = ctx.now()
        ref = _refusal(
            RefusalCode.CAPABILITY_UNAVAILABLE, step,
            f"{exc.adapter} is in the catalogue and is not running here.",
            missing=[exc.adapter],
            remedy="choose another adapter, or run where the model lives",
            detail={"adapters": [exc.adapter], "why": exc.detail})
        return _Invocation(adapter=adapter, terminal=ExtentResult(
            outcome=RunOutcome.UNAVAILABLE, refusals=(ref,) + ref_refusals,
            stage_attempt=_stage(ctx, step, state=StageState.UNAVAILABLE, adapter=adapter.key,
                                 invoked=False, started_at=started_at, completed_at=completed_at,
                                 duration_ms=None, detail=exc.detail or ref.message)))
    except Exception as exc:                          # the adapter ran and broke
        return _Invocation(adapter=adapter, terminal=ExtentResult(
            outcome=RunOutcome.FAILED, refusals=ref_refusals,
            stage_attempt=_stage(
                ctx, step, state=StageState.FAILED, adapter=adapter.key, invoked=True,
                started_at=started_at, completed_at=None, duration_ms=None,
                detail=f"{type(exc).__name__}: {exc}. No claim is made about the image.")))
    return _Invocation(adapter=adapter, out=out)


def _finish(step: ResolvedStep, ctx: ExtentContext, out: AdapterOutput, *, searched: str,
            adapter_key: Optional[str], producer_kind: ProducerKind, started_at: str,
            invoked: bool, ref_refusals: Tuple[RefusalRecord, ...] = (),
            input_refs: Sequence[InputRef] = (), identity_refs: Sequence[RegionRef] = (),
            derived_from: Sequence[str] = (),
            identity_scope: IdentityScope = IdentityScope.SESSION,
            comparison: Optional[ExtentComparison] = None,
            duplicates_override: Optional[Sequence[ExtentDuplicate]] = None,
            dropped: Optional[int] = None, capped: int = 0) -> ExtentResult:
    """Measured output → artifact, duplicates, receipt, outcome.

    `empty` still produces an ARTIFACT, carrying `searched`, because "I looked for drapery and
    there is none" is a measurement and "nobody looked" is not — and the two arrive at the same
    empty panel unless the artifact says which.

    `partial` is what comes back when some references resolved and some did not: real extents plus
    a typed refusal naming the ones that were not found. Reporting that as `ready` would hide a
    missing input behind a result that looks complete.
    """
    completed_at = ctx.now()
    # `extent.compare` computes duplicates per SIDE and prefixes their ids, so it supplies its own
    # list; every other operation has one set and finds them here. Running the default over a
    # comparison's union would report every correspondence as a duplicate, which is the opposite
    # of what it means.
    duplicates = (list(duplicates_override) if duplicates_override is not None else
                  [ExtentDuplicate(**row) for row in M.duplicate_pairs(out.instances,
                                                                       DUPLICATE_IOU)])
    artifact = _build_artifact(
        ctx, step, out, searched=searched, adapter_key=adapter_key,
        producer_kind=producer_kind, started_at=started_at, completed_at=completed_at,
        input_refs=input_refs, identity_refs=identity_refs, derived_from=derived_from,
        identity_scope=identity_scope, comparison=comparison,
        dropped_below_min_area=dropped, duplicates=duplicates)

    detail = out.detail or f"{len(out.instances)} extents"
    if capped:
        detail += f"; {capped} beyond the cap were not returned"
    if duplicates:
        detail += (f"; {len(duplicates)} possible duplicate pair(s) flagged and NOT removed — "
                   f"a duplicate warning is evidence for a person, not a deletion")

    empty = not out.instances
    if ref_refusals and not empty:
        outcome, state = RunOutcome.PARTIAL, StageState.COMPLETED
    elif ref_refusals:
        outcome, state = RunOutcome.REFUSED, StageState.REFUSED
    else:
        outcome = RunOutcome.EMPTY if empty else RunOutcome.READY
        state = StageState.EMPTY if empty else StageState.COMPLETED

    return ExtentResult(
        outcome=outcome, artifacts=(artifact,), refusals=ref_refusals,
        stage_attempt=_stage(ctx, step, state=state, adapter=adapter_key, invoked=invoked,
                             started_at=started_at, completed_at=completed_at,
                             duration_ms=out.duration_ms, detail=detail))


def _measure_with_adapter(step: ResolvedStep, ctx: ExtentContext, *, searched: str,
                          started_at: str, ref_refusals: Tuple[RefusalRecord, ...] = (),
                          input_refs: Sequence[InputRef] = (),
                          derived_from: Sequence[str] = ()) -> ExtentResult:
    """Capability gate → measure → post-filter → artifact. The path every model-backed op takes."""
    params = dict(step.parameters)
    call = _invoke(step, ctx, params, started_at, ref_refusals)
    if call.terminal is not None:
        return call.terminal
    out, dropped, capped = _post_filter(call.out, params, ctx, step)
    return _finish(step, ctx, out, searched=searched, adapter_key=call.adapter.key,
                   producer_kind=ProducerKind.ADAPTER, started_at=started_at, invoked=True,
                   ref_refusals=ref_refusals, input_refs=input_refs, derived_from=derived_from,
                   dropped=dropped, capped=capped)


def _post_filter(out: AdapterOutput, params: Mapping[str, Any], ctx: ExtentContext,
                 step: ResolvedStep) -> Tuple[AdapterOutput, Optional[int], int]:
    """The lab's own `min_area` and `max_instances`, applied HERE so they can be counted.

    The contract says instances below `min_area` are "dropped and counted, never hidden", and the
    only way to honour the second half is to do the dropping where the counting happens. The
    underlying services have their own internal floors — those are the model's hygiene and are
    reported as its defaults; this is the lab's filter, and its count is a number the person asked
    for and is owed.

    `dropped_below_min_area` stays None when no floor was supplied, because 0 would claim a filter
    ran and found nothing to drop.
    """
    instances = list(out.instances)
    dropped: Optional[int] = None

    min_area = params.get("min_area")
    if isinstance(min_area, (int, float)):
        kept = [i for i in instances if (i.get("area") is None or i["area"] >= float(min_area))]
        dropped = len(instances) - len(kept)
        instances = kept

    capped = 0
    max_instances = params.get("max_instances")
    if isinstance(max_instances, int) and len(instances) > max_instances:
        instances.sort(key=lambda i: (-(i.get("area") or 0.0), str(i.get("instance_id"))))
        capped = len(instances) - max_instances
        instances = instances[:max_instances]

    # Ids are assigned AFTER filtering so they are dense and stable for the set that survives —
    # a gap in the numbering would read as an instance somebody removed later.
    renumbered = tuple({**raw, "instance_id": instance_id(ctx, step, n)}
                       for n, raw in enumerate(instances))
    truncated = out.truncated or bool(capped)
    return replace(out, instances=renumbered, truncated=truncated), dropped, capped


def _find_all(step: ResolvedStep, ctx: ExtentContext, resolved: Mapping[str, List[Any]],
              ref_refusals: Tuple[RefusalRecord, ...], started_at: str) -> ExtentResult:
    """`extent.find_all` — what separable instances are in this picture?"""
    return _measure_with_adapter(step, ctx, searched="every separable instance",
                                 started_at=started_at, ref_refusals=ref_refusals)


def _find_named(step: ResolvedStep, ctx: ExtentContext, resolved: Mapping[str, List[Any]],
                ref_refusals: Tuple[RefusalRecord, ...], started_at: str) -> ExtentResult:
    """`extent.find_named` — where is the thing I named, and how many of it are there?

    `searched` carries the concept verbatim. That single string is the difference between an empty
    result that says "there is no drapery in this picture" and one that says nothing at all.
    """
    concept = str(step.parameters.get("concept") or "").strip()
    if not concept:
        return _param_refusal(ctx, step, started_at,
                              "a named search needs something to look for")
    return _measure_with_adapter(step, ctx, searched=concept, started_at=started_at,
                                 ref_refusals=ref_refusals)


def _single_instance(step: ResolvedStep, ctx: ExtentContext, resolved: Mapping[str, List[Any]],
                     role: str) -> Tuple[Optional[Any], Optional[ExtentInstance], Optional[str]]:
    """The one extent an operation is about, or why there isn't one.

    A CONTRACT LIMIT, MADE VISIBLE RATHER THAN GUESSED AROUND. Lane A's `InputRef` addresses an
    ARTIFACT, not an instance inside it, so a refine request against a set of five extents cannot
    say which one it means. Picking the largest, or the first, would be the lab choosing a subject
    on the person's behalf and then attributing the choice to them.

    So this refuses, and says how to proceed: select one extent first. Lane F should read this as
    the argument for an optional `instance_id` on `InputRef`.
    """
    entries = resolved.get(role) or []
    if not entries:
        return None, None, f"{step.operation} needs a {role} extent and none resolved"
    _ref, artifact = entries[0]
    payload = getattr(artifact.measurement, "payload", None)
    instances = list(getattr(payload, "instances", ()) or ())
    if len(instances) != 1:
        return artifact, None, (
            f"the {role} artifact holds {len(instances)} extents and this operation works on one. "
            f"Select a single extent first — the lab will not choose which one you meant")
    return artifact, instances[0], None


def _carry_naming(instance: ExtentInstance) -> Optional[Dict[str, Any]]:
    """A refinement inherits the base's name and does not re-earn it.

    The geometry changed; the reading did not. Re-deriving a name from a refined mask would be the
    lab inventing an interpretation nobody made, and dropping the name would lose one a person may
    have typed.
    """
    if instance.naming is None:
        return None
    return {"text": instance.naming.text, "source": instance.naming.source.value,
            "epistemic_status": instance.naming.epistemic_status.value,
            "confidence": instance.naming.confidence}


def _refine(step: ResolvedStep, ctx: ExtentContext, resolved: Mapping[str, List[Any]],
            ref_refusals: Tuple[RefusalRecord, ...], started_at: str) -> ExtentResult:
    """`extent.refine` — is this the boundary I meant?

    IDENTITY IS PRESERVED AND THE REVISION MOVES. A refinement continuing the same subject keeps
    the base's `region_id` and increments `geometry_rev`; it does not mint a new identity, because
    a relation citing that region must be able to notice that its endpoint moved. Split and merge
    mint new identities, and this lane implements neither — the plan defers them until the lineage
    rules exist, and a split that quietly reused an id would be the exact defect those rules are
    for.

    THE THREE MODES ARE EXACT SET ARITHMETIC, not three prompts to a model. SAM 2.1 predicts a
    mask from the points or box it was given; what happens to the BASE is the lab's arithmetic,
    per pixel, in `extent_metrics`:

        replace   the prediction stands alone
        add       base ∪ prediction
        subtract  base − prediction

    Doing it this way makes `add` and `subtract` checkable claims about two masks rather than
    hints whose effect depends on how the model felt about the points.
    """
    base_artifact, base_instance, why = _single_instance(step, ctx, resolved, "base")
    if why is not None:
        return _param_refusal(ctx, step, started_at, why)

    params = dict(step.parameters)
    mode = str(params.get("mode") or "")
    if not params.get("points") and not params.get("box"):
        return _param_refusal(ctx, step, started_at,
                              "a refinement needs points or a box to refine with")
    if mode in ("add", "subtract") and not mg.rle_is_valid(base_instance.mask_rle):
        return _param_refusal(
            ctx, step, started_at,
            f"{mode!r} is arithmetic on the base mask and the base extent has no mask. "
            f"Use 'replace', or refine something that carries one")

    call = _invoke(step, ctx, params, started_at, ref_refusals)
    if call.terminal is not None:
        return call.terminal
    out = call.out
    predicted = out.instances[0]["mask_rle"] if out.instances else None
    if not mg.rle_is_valid(predicted):
        return _param_refusal(ctx, step, started_at,
                              "the refiner returned no mask for that prompt")

    base_rle = base_instance.mask_rle
    if mode == "replace" or not mg.rle_is_valid(base_rle):
        combined = dict(predicted)
        arithmetic = "the prediction, standing alone"
    elif mode == "add":
        combined = M.mask_union(base_rle, predicted)
        arithmetic = "base ∪ prediction, per pixel"
    else:
        combined = M.mask_subtract(base_rle, predicted)
        arithmetic = "base − prediction, per pixel"

    if combined is None:
        return _param_refusal(
            ctx, step, started_at,
            "the base mask and the refiner's mask are on different rasters, and the lab does not "
            "resample one to meet the other — a resampled refinement is a mask of neither")
    if not mg.rle_is_valid(combined):
        return _param_refusal(ctx, step, started_at,
                              f"{mode!r} left no pixels — a refinement that erases the extent is "
                              f"a rejection, not a revision")

    # ONE canonicalization, on a dict the lab owns. `canonicalize_geometry` bumps `geometry_rev`
    # exactly once per identity derivation, so the base's revision goes in and the bump takes it to
    # the next one. Doing the arithmetic first and canonicalizing once is what keeps the revision
    # honest — running it twice would report two revisions for one refinement.
    base_rev = int(base_instance.geometry_rev or 0)
    region: Dict[str, Any] = {
        "id": base_instance.region_id or instance_id(ctx, step, 0),
        "actor": "creator",
        "mask_rle": combined,
        "geometry_rev": base_rev,
        "refined_from": base_instance.instance_id,
    }
    mg.canonicalize_geometry(region, provenance={
        "adapter": call.adapter.key, "model": out.model, "device": out.device,
        "method": f"lab-refine-{mode}", "arithmetic": arithmetic})

    refined = {
        "instance_id": instance_id(ctx, step, 0),
        "mask_rle": region["mask_rle"], "box": region.get("box"),
        "area": M.normalized_area(region["mask_rle"]),
        "confidence": out.instances[0].get("confidence"),
        "naming": _carry_naming(base_instance),
        "region_id": base_instance.region_id,
        "geometry_rev": region.get("geometry_rev"),
    }
    identity_refs = ([RegionRef(region_id=base_instance.region_id,
                                geometry_rev=int(region.get("geometry_rev") or base_rev + 1))]
                     if base_instance.region_id else [])

    out = replace(out, instances=(refined,), basis=EpistemicBasis.MASK,
                  status=EpistemicStatus.MEASURED,
                  basis_detail=f"per-pixel refinement: {arithmetic}",
                  detail=f"{mode} refinement of {base_instance.instance_id} "
                         f"(geometry_rev {base_rev} → {region.get('geometry_rev')})")
    return _finish(
        step, ctx, out,
        searched=f"the boundary of {base_instance.instance_id}, refined",
        adapter_key=call.adapter.key, producer_kind=ProducerKind.ADAPTER,
        started_at=started_at, invoked=True, ref_refusals=ref_refusals,
        input_refs=list(step.input_refs), identity_refs=identity_refs,
        derived_from=[base_artifact.identity.artifact_id],
        identity_scope=(IdentityScope.CANONICAL if base_instance.region_id
                        else IdentityScope.SESSION))


#: How much the lab will vouch for geometry it did not measure, ordered weakest first. `declared`
#: is the abstention: a mask whose maker nobody recorded is not weak evidence, it is evidence the
#: lab will not stand behind — the hole REGION-PROV-001 counted, with
#: `region_provenance.is_attributed` as its reader.
_REUSE_BASIS_ORDER = {EpistemicBasis.DECLARED: 0, EpistemicBasis.BOX: 1, EpistemicBasis.MASK: 2}


def _region_epistemics(region: Mapping[str, Any]) -> Tuple[EpistemicBasis, EpistemicStatus, str]:
    from backend.services import region_provenance as rp
    if not mg.rle_is_valid(region.get("mask_rle")):
        return (EpistemicBasis.BOX, EpistemicStatus.INTERPRETIVE,
                "a box-only region: an estimate of an extent, and interpretive by "
                "`epistemics.SUBSTRATE_CEILING`")
    if rp.is_attributed(region):
        maker = rp.maker_of(region)
        return (EpistemicBasis.MASK, EpistemicStatus.MEASURED,
                f"an attributed mask — {maker.get('detail')} — carried, not re-derived")
    return (EpistemicBasis.DECLARED, EpistemicStatus.UNCERTAIN,
            "a mask with no recorded maker. The lab carries the claim and will not vouch for it: "
            "`uncertain` is an abstention, not a low score")


def _reuse(step: ResolvedStep, ctx: ExtentContext, resolved: Mapping[str, List[Any]],
           ref_refusals: Tuple[RefusalRecord, ...], started_at: str) -> ExtentResult:
    """`extent.reuse` — work on extents Semant already holds, without copying or re-deriving them.

    NOTHING IS CANONICALIZED HERE, and that is the whole care of this function.
    `mask_geometry.canonicalize_geometry` mutates in place and bumps `geometry_rev`; running it on
    a caller's Region would silently revise the corpus from inside a laboratory whose first promise
    is that it does not write. So the geometry is READ and deep-copied, and the artifact references
    `region_id` + `geometry_rev` rather than owning them.

    THE SET TAKES ITS WEAKEST MEMBER'S STATUS. One unattributed mask among four attributed ones
    drags the artifact to `declared` / `uncertain`, because a set reported as `measured` invites a
    reader to trust a part of it nobody can trace.
    """
    entries = resolved.get("regions") or []
    if not entries:
        completed_at = ctx.now()
        return ExtentResult(
            outcome=RunOutcome.REFUSED, refusals=ref_refusals,
            stage_attempt=_stage(ctx, step, state=StageState.REFUSED, adapter="canonical_region",
                                 invoked=False, started_at=started_at, completed_at=completed_at,
                                 duration_ms=None,
                                 detail="no reference resolved to a region held in this session"))

    instances: List[Dict[str, Any]] = []
    bases: List[Tuple[EpistemicBasis, EpistemicStatus, str]] = []
    for n, (ref, region) in enumerate(entries):
        basis, status, why = _region_epistemics(region)
        bases.append((basis, status, why))
        rle = region.get("mask_rle")
        box = region.get("box")
        naming, _hidden = _naming_from(str(region.get("label") or ""),
                                       region.get("confidence"), "canonical", 0.0)
        instances.append({
            "instance_id": instance_id(ctx, step, n),
            # Deep copies. The dicts handed in belong to the caller and go back untouched.
            "mask_rle": dict(rle) if mg.rle_is_valid(rle) else None,
            "box": dict(box) if isinstance(box, Mapping) else None,
            "area": M.normalized_area(rle) if mg.rle_is_valid(rle) else None,
            "confidence": region.get("confidence"), "naming": naming,
            "region_id": str(region.get("id") or ref.region_id),
            "geometry_rev": int(region.get("geometry_rev") or ref.geometry_rev or 0)})

    weakest = min(bases, key=lambda row: _REUSE_BASIS_ORDER[row[0]])
    mixed = len({row[0] for row in bases}) > 1
    out = AdapterOutput(
        instances=tuple(instances), basis=weakest[0], status=weakest[1],
        basis_detail=(weakest[2] + ("; the set is mixed and takes its weakest member's status"
                                    if mixed else "")),
        model=None, revision=None, device=None, duration_ms=None,
        detail=f"{len(instances)} region(s) referenced, none re-derived")

    identity_refs = [RegionRef(region_id=str(i["region_id"]),
                               geometry_rev=int(i["geometry_rev"] or 0))
                     for i in instances if i.get("region_id")]
    return _finish(
        step, ctx, out,
        searched=("extents Semant already holds: "
                  + ", ".join(str(i["region_id"]) for i in instances)),
        adapter_key="canonical_region", producer_kind=ProducerKind.ADAPTER,
        started_at=started_at, invoked=False, ref_refusals=ref_refusals,
        input_refs=list(step.input_refs), identity_refs=identity_refs,
        identity_scope=IdentityScope.CANONICAL)


def _as_mapping(instance: ExtentInstance) -> Dict[str, Any]:
    """An `ExtentInstance` as the plain mapping `extent_metrics` reads. One conversion, one place."""
    return {"instance_id": instance.instance_id, "mask_rle": instance.mask_rle,
            "box": instance.box.model_dump() if instance.box is not None else None,
            "area": instance.area, "confidence": instance.confidence,
            "region_id": instance.region_id, "geometry_rev": instance.geometry_rev,
            "naming": _carry_naming(instance)}


def _compare(step: ResolvedStep, ctx: ExtentContext, resolved: Mapping[str, List[Any]],
             ref_refusals: Tuple[RefusalRecord, ...], started_at: str) -> ExtentResult:
    """`extent.compare` — did those two runs see the same thing?

    WHAT THE ARTIFACT CARRIES, and why it is shaped this way. The measurement is the
    CORRESPONDENCE — which extent on the left is which extent on the right, and how much they
    agree — plus what only one side saw. The artifact's own `instances` are the union of both
    sets, prefixed `L:` and `R:`, so a renderer has the geometry for an A/B overlay without
    re-fetching the inputs; the correspondence rows name the INPUTS' own instance ids, because
    those are the identities the left and right artifacts actually hold.

    MASKS ONLY, and this is a real limit rather than a shortcut. The contract declares
    `allowed_bases: ["mask"]` for this operation, and it is right to: an IoU between a box and a
    mask is a number about neither, and a box-versus-box agreement of 0.9 next to a per-pixel one
    of 0.9 would invite exactly the reading `epistemics.SUBSTRATE_CEILING` exists to prevent. A set
    carrying a box-only extent is refused, by name, with what to do instead. That means the
    box-basis Grounded-SAM detector cannot currently be A/B'd against SAM 3 — see the lane report.

    NO SUMMARY NUMBER IS STORED. Mean agreement, "identical", "stable across a repeat" — all of
    them are derivable from the correspondence rows, and all of them are READINGS. They are
    offered as functions below, computed by whoever displays them, rather than frozen into the
    measurement where a later change of definition would silently rewrite history.
    """
    left_entry = (resolved.get("left") or [None])[0]
    right_entry = (resolved.get("right") or [None])[0]
    if left_entry is None or right_entry is None:
        return _param_refusal(ctx, step, started_at,
                              "a comparison needs both a left and a right extent set")
    left_artifact = left_entry[1]
    right_artifact = right_entry[1]

    left = [_as_mapping(i) for i in left_artifact.measurement.payload.instances]
    right = [_as_mapping(i) for i in right_artifact.measurement.payload.instances]

    unmasked = [i["instance_id"] for i in (left + right) if not mg.rle_is_valid(i["mask_rle"])]
    if unmasked:
        return _param_refusal(
            ctx, step, started_at,
            f"comparison is exact mask arithmetic and {len(unmasked)} extent(s) carry no mask "
            f"({', '.join(unmasked[:4])}). An agreement between a box and a mask is a number "
            f"about neither — compare sets from mask-producing adapters")

    threshold = step.parameters.get("iou_threshold")
    threshold = float(threshold) if isinstance(threshold, (int, float)) else DEFAULT_IOU_THRESHOLD
    matched = M.greedy_correspondence(left, right, threshold)

    comparison = ExtentComparison(
        left_artifact_id=left_artifact.identity.artifact_id,
        right_artifact_id=right_artifact.identity.artifact_id,
        iou_threshold_used=threshold,
        correspondences=[ExtentCorrespondence(**row) for row in matched["correspondences"]],
        only_in_left=matched["only_in_left"], only_in_right=matched["only_in_right"])

    union: List[Dict[str, Any]] = []
    for side, rows in (("L", left), ("R", right)):
        for raw in rows:
            union.append({**raw, "instance_id": f"{side}:{raw['instance_id']}"})
    duplicates = [ExtentDuplicate(instance_ids=[f"{side}:{a}" for a in row["instance_ids"]],
                                  iou=row["iou"])
                  for side, rows in (("L", left), ("R", right))
                  for row in M.duplicate_pairs(rows, DUPLICATE_IOU)]

    ious = [row["iou"] for row in matched["correspondences"]]
    identical = (not matched["only_in_left"] and not matched["only_in_right"]
                 and bool(ious) and all(v >= 1.0 for v in ious))
    changed = [row for row in matched["correspondences"] if row["iou"] < 1.0]
    detail = (f"{len(matched['correspondences'])} matched at IoU ≥ {threshold}; "
              f"{len(matched['only_in_left'])} only on the left, "
              f"{len(matched['only_in_right'])} only on the right; "
              f"{len(changed)} matched pair(s) differ in geometry"
              + ("; the two sets are identical" if identical else ""))

    out = AdapterOutput(
        instances=tuple(union), basis=EpistemicBasis.MASK, status=EpistemicStatus.MEASURED,
        basis_detail="per-pixel intersection over union on a shared raster",
        model=None, revision=None, device=None, duration_ms=None, detail=detail)

    return _finish(
        step, ctx, out,
        searched=(f"the union of {left_artifact.identity.artifact_id} and "
                  f"{right_artifact.identity.artifact_id}"),
        adapter_key="lab_compare", producer_kind=ProducerKind.ADAPTER, started_at=started_at,
        invoked=False, ref_refusals=ref_refusals, input_refs=list(step.input_refs),
        derived_from=[left_artifact.identity.artifact_id, right_artifact.identity.artifact_id],
        comparison=comparison, duplicates_override=duplicates)


# ── readings over a comparison, computed rather than stored ──────────────────


def mean_agreement(comparison: ExtentComparison) -> Optional[float]:
    """Mean IoU across matched pairs, or None when nothing matched.

    None rather than 0.0. Two sets with no correspondence at all did not agree badly — they did not
    agree about anything, and a 0.0 in a column of averages reads as a measurement of disagreement.
    """
    values = [c.iou for c in comparison.correspondences]
    return sum(values) / len(values) if values else None


def is_identical(comparison: ExtentComparison) -> bool:
    """Did the two sets see exactly the same extents, pixel for pixel?

    This is the repeat-stability question. Run the same operation twice on the same image with the
    same adapter and compare the results: `True` means the producer is deterministic on this
    input, and `False` with a high `mean_agreement` means it is stable but not deterministic —
    two different findings that a single "stability score" would blur.
    """
    return (not comparison.only_in_left and not comparison.only_in_right
            and bool(comparison.correspondences)
            and all(c.iou >= 1.0 for c in comparison.correspondences))


def changed_geometry(comparison: ExtentComparison) -> List[ExtentCorrespondence]:
    """Matched pairs whose masks are not identical — the same extent, drawn differently."""
    return [c for c in comparison.correspondences if c.iou < 1.0]


# ── the real adapters ────────────────────────────────────────────────────────


def _pil_image(ctx: ExtentContext):
    """The image, as PIL, for adapters that take an image rather than bytes.

    Opened read-only and never saved. `ExtentContext.image_bytes` is the source of truth and stays
    byte-identical — the non-mutation test hashes it before and after every operation.
    """
    import io
    from PIL import Image
    return Image.open(io.BytesIO(ctx.image_bytes)).convert("RGB")


def _naming_from(text: str, confidence: Optional[float], source: str, floor: float
                 ) -> Tuple[Optional[Dict[str, Any]], bool]:
    """`(naming, withheld)` — the rule that keeps a doubtful word from costing a good mask.

    SF-004-R2 measured that confidence tracked correctness for SAM 3's naming: `snake hood` at
    0.92 was right eleven times over, `shoulder fabric` at 0.27–0.43 masked the background. Below
    the floor the NAME is not proposed. The extent is emitted regardless, because the mask and the
    word are two claims and only one of them is in doubt.
    """
    if not text:
        return None, False
    if confidence is not None and confidence < floor:
        return None, True
    return ({"text": text, "source": source, "epistemic_status": "interpretive",
             "confidence": confidence}, False)


class Sam2AutoAdapter:
    """`yolo_sam2_auto` — automatic instance proposal over the whole image.

    TWO SUBSTRATES BEHIND ONE CONTRACT KEY, and the receipt always says which ran. SAM 2.1's
    automatic generator produces class-agnostic extents with no label; YOLO11-seg produces labelled
    ones. The adapter prefers SAM 2.1 and falls back to YOLO ONLY when SAM 2.1 is unavailable —
    never when it FAILED. Unavailability may route; a failure is reported, because a silent
    substitution after an error is a model change hidden inside a receipt that says nothing
    happened.
    """

    key = "yolo_sam2_auto"

    def _sam2(self):
        from backend.services import sam2_auto_service
        return sam2_auto_service

    def _yolo(self):
        from backend.services import segmentation_service
        return segmentation_service

    def capability(self) -> CapabilityState:
        try:
            if self._sam2().is_available() or self._yolo().is_available():
                return CapabilityState.AVAILABLE
        except Exception:
            return CapabilityState.UNAVAILABLE
        return CapabilityState.UNAVAILABLE

    def measure(self, step: ResolvedStep, ctx: ExtentContext,
                params: Mapping[str, Any]) -> AdapterOutput:
        cap = params.get("max_instances")
        cap = int(cap) if isinstance(cap, int) else DEFAULT_MAX_INSTANCES
        sam2, yolo = self._sam2(), self._yolo()

        if sam2.is_available():
            regions = sam2.generate_masks(ctx.image_bytes, max_regions=cap)
            substrate, model, revision = "sam2-auto", sam2.MODEL_TAG, sam2.PREPROCESSING_VERSION
        elif yolo.is_available():
            regions = yolo.segment_image_bytes(ctx.image_bytes, max_regions=cap)
            substrate, model, revision = "yolo11n-seg", yolo.MODEL_TAG, None
        else:                                          # pragma: no cover - gate already refused
            raise AdapterUnavailable(self.key, "neither substrate is installed")

        if regions is None:
            raise RuntimeError(f"{substrate} was available and returned nothing readable")

        instances: List[Dict[str, Any]] = []
        withheld = 0
        for n, region in enumerate(regions):
            rle = region.get("mask_rle")
            naming, hidden = _naming_from(str(region.get("label") or ""),
                                          region.get("confidence"), "adapter", NAMING_FLOOR)
            withheld += int(hidden)
            instances.append({
                "instance_id": instance_id(ctx, step, n),
                "mask_rle": dict(rle) if mg.rle_is_valid(rle) else None,
                "box": dict(region["box"]) if isinstance(region.get("box"), Mapping) else None,
                "area": M.normalized_area(rle) if mg.rle_is_valid(rle) else None,
                "confidence": region.get("confidence"), "naming": naming,
                "region_id": None, "geometry_rev": None})

        masked = all(i["mask_rle"] for i in instances) if instances else True
        prov = (regions[0].get("geometry_provenance") or {}) if regions else {}
        return AdapterOutput(
            instances=tuple(instances),
            basis=EpistemicBasis.MASK if masked else EpistemicBasis.BOX,
            status=EpistemicStatus.MEASURED if masked else EpistemicStatus.INTERPRETIVE,
            basis_detail=("per-pixel masks from the automatic generator" if masked else
                          "at least one proposal came back without a mask, so the set is read on "
                          "boxes and takes the interpretive ceiling"),
            model=model, revision=revision, device=prov.get("device"),
            duration_ms=int(prov["latency_ms"]) if isinstance(prov.get("latency_ms"),
                                                              (int, float)) else None,
            naming_withheld=withheld,
            detail=f"{len(instances)} extents from {substrate}")


class Sam3ConceptAdapter:
    """`sam3_concept` — every instance of a named concept, as canonical RLE.

    UNAVAILABLE IS NEVER EMPTY HERE, and this adapter is the reason the rule is written down. SAM 3
    needs a 3.2 GiB checkpoint that most deployments do not have; a missing checkpoint reported as
    "no drapery in this picture" would be a measurement nobody made, about a picture nobody looked
    at. `capability()` answers from `weights_path()` and `is_available()` before anything runs.
    """

    key = "sam3_concept"

    def _svc(self):
        from backend.services import sam3_concept_service
        return sam3_concept_service

    def capability(self) -> CapabilityState:
        try:
            return (CapabilityState.AVAILABLE if self._svc().is_available()
                    else CapabilityState.UNAVAILABLE)
        except Exception:
            return CapabilityState.UNAVAILABLE

    def measure(self, step: ResolvedStep, ctx: ExtentContext,
                params: Mapping[str, Any]) -> AdapterOutput:
        svc = self._svc()
        concept = str(params.get("concept") or "")
        cap = params.get("max_instances")
        cap = int(cap) if isinstance(cap, int) else DEFAULT_MAX_INSTANCES
        result = svc.segment_concept(_pil_image(ctx), concept, max_instances=cap)

        instances: List[Dict[str, Any]] = []
        withheld = 0
        for n, inst in enumerate(result.get("instances") or []):
            rle = inst.get("mask_rle")
            if not mg.rle_is_valid(rle):
                continue
            naming, hidden = _naming_from(concept, inst.get("confidence"), "prompt",
                                          svc.NAMING_CONFIDENCE_FLOOR)
            withheld += int(hidden)
            instances.append({
                "instance_id": instance_id(ctx, step, n),
                "mask_rle": dict(rle), "box": mg.rle_bbox_norm(rle),
                "area": M.normalized_area(rle), "confidence": inst.get("confidence"),
                "naming": naming, "region_id": None, "geometry_rev": None})

        return AdapterOutput(
            instances=tuple(instances), basis=EpistemicBasis.MASK,
            status=EpistemicStatus.MEASURED,
            basis_detail="per-pixel concept masks on the source raster",
            model=result.get("model"), revision=svc.PREPROCESSING_VERSION,
            device=result.get("device"),
            duration_ms=int(result["latency_ms"]) if isinstance(result.get("latency_ms"),
                                                                (int, float)) else None,
            naming_withheld=withheld, truncated=bool(result.get("truncated")),
            detail=f"{len(instances)} instances of {concept!r}")


class GroundedSamAdapter:
    """`grounded_sam` — a phrase grounded to BOXES, and the artifact says so.

    WHAT THIS SEAM IS AND IS NOT. `grounding_detector_service.detect` is GroundingDINO alone: it
    returns pixel boxes, not masks. The repository's full Grounded-SAM path — detector, then a CLIP
    presence gate, then SAM for the mask — lives in `backend/routers/posts.py::_produce_grounded_sam`
    and is a router-level async pipeline this lane may not touch. So this adapter is the DETECTOR,
    honestly named: `basis: box`, `interpretive`, per `epistemics.SUBSTRATE_CEILING`.

    A box-basis extent is a real and useful proposal. It is not a mask, and the ceiling is what
    stops it being read as one.
    """

    key = "grounded_sam"

    def _svc(self):
        from backend.services import grounding_detector_service
        return grounding_detector_service

    def capability(self) -> CapabilityState:
        try:
            return (CapabilityState.AVAILABLE if self._svc().is_available()
                    else CapabilityState.UNAVAILABLE)
        except Exception:
            return CapabilityState.UNAVAILABLE

    def measure(self, step: ResolvedStep, ctx: ExtentContext,
                params: Mapping[str, Any]) -> AdapterOutput:
        svc = self._svc()
        concept = str(params.get("concept") or "")
        detection = svc.detect(_pil_image(ctx), concept)

        instances: List[Dict[str, Any]] = []
        withheld = 0
        if detection:
            size = detection.get("image_size") or [0, 0]
            width, height = int(size[0] or 0), int(size[1] or 0)
            scores = detection.get("scores") or []
            labels = detection.get("labels") or []
            for n, box in enumerate(detection.get("boxes") or []):
                nb = mg.normalize_box_xyxy(box, width, height)
                if not nb:
                    continue
                score = float(scores[n]) if n < len(scores) else None
                text = str(labels[n]) if n < len(labels) and labels[n] else concept
                naming, hidden = _naming_from(text, score, "prompt", NAMING_FLOOR)
                withheld += int(hidden)
                instances.append({
                    "instance_id": instance_id(ctx, step, n), "mask_rle": None, "box": nb,
                    "area": float(nb["w"]) * float(nb["h"]), "confidence": score,
                    "naming": naming, "region_id": None, "geometry_rev": None})

        return AdapterOutput(
            instances=tuple(instances), basis=EpistemicBasis.BOX,
            status=EpistemicStatus.INTERPRETIVE,
            basis_detail="grounded boxes, not masks. A box is an estimate of an extent and takes "
                         "the interpretive ceiling `epistemics.SUBSTRATE_CEILING` gives it; the "
                         "CLIP presence gate and the SAM mask upgrade live in the router pipeline "
                         "this lane does not reach.",
            model=svc.MODEL_TAG, revision=svc.REVISION, device=None,
            naming_withheld=withheld,
            detail=f"{len(instances)} grounded boxes for {concept!r}")


def _call_refine_session(image_bytes: bytes, prompt: Mapping[str, Any], base_id: Optional[str],
                         base_rev: int) -> Mapping[str, Any]:
    """The sync seam over `refine_session.preview`, which is async.

    WHY A SEAM AND NOT AN ASYNC FAÇADE. Everything else this organ wraps is blocking, and an async
    `run()` would make five synchronous adapters pay for one asynchronous one — and would make the
    test that matters (a direct step and a planner step reaching the same runner) harder to write
    than the thing it proves. So the façade stays synchronous and the one async producer is
    adapted here, in six lines a reader can check.

    When there is no running loop this is `asyncio.run`. When there IS one — a FastAPI request
    thread, which is where Lane F will call from — the coroutine goes to its own loop on a worker
    thread rather than blocking the caller's. Lane F may inject a plain `await` seam instead.
    """
    import asyncio
    from backend.services.vision_orchestrator.refine_session import refine_session

    def _go():
        return asyncio.run(refine_session.preview(image_bytes, dict(prompt), base_id, base_rev))

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _go()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_go).result()


class Sam2RefineAdapter:
    """`sam2_refine` — SAM 2.1 point/box refinement, through `vision_orchestrator/refine_session`.

    THE ADAPTER PREDICTS; THE FAÇADE DOES THE ARITHMETIC. What comes back here is one mask for the
    prompt that was given, and nothing else. `add` and `subtract` are then exact set operations on
    the base, done in `extent_metrics` where they can be tested on a 4×4 mask. Pushing them into
    the adapter would make the modes depend on a model's response to point labels, which is not a
    thing anyone can check.

    Point labels still travel: `add` sends foreground points, `subtract` sends background ones, so
    the prediction is the best one available for what the person meant. The arithmetic is what
    makes the mode's EFFECT definite.
    """

    key = "sam2_refine"

    def __init__(self, refine_call: Callable[..., Mapping[str, Any]] = _call_refine_session
                 ) -> None:
        self._refine_call = refine_call

    def _session(self):
        from backend.services.vision_orchestrator.refine_session import refine_session
        return refine_session

    def capability(self) -> CapabilityState:
        try:
            return (CapabilityState.AVAILABLE if self._session().available()
                    else CapabilityState.UNAVAILABLE)
        except Exception:
            return CapabilityState.UNAVAILABLE

    def measure(self, step: ResolvedStep, ctx: ExtentContext,
                params: Mapping[str, Any]) -> AdapterOutput:
        points = params.get("points") or []
        box = params.get("box")
        mode = str(params.get("mode") or "replace")
        prompt: Dict[str, Any] = {}
        if points:
            prompt["points"] = [[float(p[0]), float(p[1])] for p in points]
            # `subtract` means "not this part of it", which is SAM 2.1's background label.
            prompt["labels"] = [0 if mode == "subtract" else 1] * len(prompt["points"])
        if isinstance(box, Mapping):
            prompt["box"] = [float(box["x"]), float(box["y"]),
                             float(box["x"]) + float(box["w"]),
                             float(box["y"]) + float(box["h"])]

        region = self._refine_call(ctx.image_bytes, prompt, None, 0) or {}
        rle = region.get("mask_rle")
        prov = region.get("geometry_provenance") or {}
        return AdapterOutput(
            instances=({"instance_id": instance_id(ctx, step, 0),
                        "mask_rle": dict(rle) if mg.rle_is_valid(rle) else None,
                        "box": region.get("box"),
                        "area": M.normalized_area(rle) if mg.rle_is_valid(rle) else None,
                        "confidence": region.get("confidence"), "naming": None,
                        "region_id": None, "geometry_rev": None},),
            basis=EpistemicBasis.MASK, status=EpistemicStatus.MEASURED,
            basis_detail="a per-pixel prediction from the point/box prompt",
            model=prov.get("model"), revision=prov.get("checkpoint"), device=prov.get("device"),
            detail=f"{mode} prompt refined")


#: Operation → handler. `run()` refuses anything absent with `unsupported_operation`, which is the
#: same answer a genuinely undeclared key gets, because from the caller's side "this laboratory
#: will not do that" is one fact.
_HANDLERS: Dict[str, Callable[..., ExtentResult]] = {
    "extent.find_all": _find_all,
    "extent.find_named": _find_named,
    "extent.refine": _refine,
    "extent.draw": _draw,
    "extent.reuse": _reuse,
    "extent.compare": _compare,
}


def default_adapters() -> Mapping[str, ExtentAdapter]:
    """The real adapters, by their contract key.

    ONLY THE THINGS THAT CAN BE ABSENT ARE IN HERE. `extent.draw`, `extent.reuse` and
    `extent.compare` name their contract adapter on the provenance (`null` for a person,
    `canonical_region`, `lab_compare`) and never consult this registry, because an operation with
    no model behind it cannot be unavailable — and a registry entry that is always available would
    be a capability declaration that means nothing.

    Constructed fresh each call and holding no model: every adapter imports its service lazily, so
    importing this module costs nothing and a deployment without torch can still read the registry
    and be told, honestly, that nothing is running.
    """
    return {
        Sam2AutoAdapter.key: Sam2AutoAdapter(),
        Sam3ConceptAdapter.key: Sam3ConceptAdapter(),
        GroundedSamAdapter.key: GroundedSamAdapter(),
        Sam2RefineAdapter.key: Sam2RefineAdapter(),
    }


__all__ = [
    "ORGAN", "DEFAULT_IOU_THRESHOLD", "DUPLICATE_IOU", "DEFAULT_MAX_INSTANCES", "NAMING_FLOOR",
    "ExtentContext", "ExtentResult", "AdapterOutput", "ExtentAdapter", "AdapterUnavailable",
    "Sam2AutoAdapter", "Sam3ConceptAdapter", "GroundedSamAdapter",
    "Sam2RefineAdapter", "run", "instance_id", "capability_of", "default_adapters",
    "mean_agreement", "is_identical", "changed_geometry",
]
