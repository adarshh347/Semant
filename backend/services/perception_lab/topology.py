"""
PERCEPTUAL-ORGANS-002 Lane C — the Topology organ façade.

One question: **how are extents spatially related?** Seven operations answer it, and not one of
them may go and find its own extents. That is the whole shape of this module.

WHAT IS NEW HERE, AND WHAT IS NOT. The measurements are not new. `nestedness_organ` has computed
containment since WAVE2, `adjacency_organ` boundary contact since WAVE3, `occlusion_organ` depth
ordering since WAVE3, and `mask_geometry` owns the RLE chain all three ride on. This module calls
them. What it adds is the four things a LABORATORY needs and a movement graph never did:

    an identity      a relation cites endpoint ids and revisions, and a stale one can be seen
    a locus          not `contact_fraction 0.21` but the contact band's own bounding box
    a refusal        typed, with the thing that would satisfy it named
    a ceiling        carried on the artifact, so a box-basis 0.999 cannot be read as a finding

WHAT IT WILL NOT DO, and the reasons are not stylistic:

    it never invokes Extent          isolation mode exists so a judgement about one organ means
                                     something; an organ that quietly ran another would make every
                                     verdict a verdict about two
    it never invokes Depth           `topology.occlusion` consumes a PREPARED depth field or
                                     refuses `missing_depth_artifact`. Live Depth is the next
                                     phase, and a capability that half-exists is worse than one
                                     that does not
    it never infers a relation       no VLM, no label, no name. The organs read pixels. A relation
                                     this module cannot compute is one it refuses
    it writes nothing                no post, no database, no Ground, no perceptual ledger. It
                                     returns artifacts; Lane F decides what becomes canonical

WHERE THE INPUTS COME FROM. Every declared input on every topology operation is an `extent_set`
ARTIFACT — the merged contract says so, and it is why there is no code path here that could produce
an extent. Callers holding bare canonical Regions reach Topology through Lane B's `extent.reuse`,
which is the visible step that turns a Region into an artifact. The one seam this module offers for
explicit region geometry is `TopologyRequest.regions`: a reuse-style instance may cite a canonical
region and carry a coarser projection of it, and a caller that has the Region itself may supply the
geometry — WITH its `geometry_rev`, checked against the instance's, so the seam cannot be used to
attach a newer mask to an older reference.

PURE. No database, no network, no model, no clock it was not handed (`LabContext.now` and an
optional injected `clock`). Geometry in, artifacts out.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (BASIS_CEILINGS, ArtifactIdentity,
                                            ArtifactInterpretation, ArtifactKind,
                                            ArtifactLifecycle, ArtifactMeasurement,
                                            ArtifactProjection, ArtifactProvenance,
                                            CoordinateSystem, EpistemicBasis, EpistemicStatus,
                                            IdentityScope, InputRef, LabelSource, LifecycleState,
                                            NegativeSpaceFieldPayload, OrganFamily, PerceptualArtifact,
                                            ProducerKind, ProjectionKind, RefusalCode,
                                            RefusalPayload, RefusalRecord, RegionRef, RelationEndpoint,
                                            RelationKind, RunOutcome, SessionMode,
                                            TopologyRelation, TopologyRelationSetPayload)
from backend.services import adjacency_organ as adjacency
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nestedness
from backend.services import occlusion_organ as occlusion
from backend.services import region_geometry as rg
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import topology_evidence as ev

ORGAN = OrganFamily.TOPOLOGY

#: What the provenance of every artifact this module mints says. The same name Lane A's committed
#: fixtures already use, so a reader comparing a live artifact against the example is comparing two
#: records of the same producer rather than two producers.
PRODUCER = "topology_facade"

#: Which declared adapter each operation actually ran. Read from the contract's own adapter lists
#: rather than restated, except where an operation declares several and this façade picks one — and
#: those picks are here, visible, rather than inside the branch that made them.
PRIMARY_ADAPTER: Mapping[str, str] = {
    "topology.containment": "nestedness_organ",
    "topology.adjacency": "adjacency_organ",
    "topology.overlap": "mask_arithmetic",
    "topology.disjoint": "distance_transform",
    "topology.negative_space": "distance_transform",
    "topology.all_pairs": "mask_arithmetic",
    "topology.occlusion": "occlusion_organ",
}

#: The projection each operation's artifact proposes. Every value is in that operation's declared
#: `render_projections`, asserted at import — a projection the contract did not declare is a
#: renderer this lane invented, and Lane E would have nothing registered to draw it with.
PROJECTION: Mapping[str, ProjectionKind] = {
    "topology.containment": ProjectionKind.ENDPOINT_PAIR,
    "topology.adjacency": ProjectionKind.CONTACT_BAND,
    "topology.overlap": ProjectionKind.INTERSECTION_AREA,
    "topology.disjoint": ProjectionKind.ENDPOINT_PAIR,
    "topology.negative_space": ProjectionKind.SCALAR_WASH,
    "topology.all_pairs": ProjectionKind.RELATION_GRAPH,
    "topology.occlusion": ProjectionKind.ENDPOINT_PAIR,
}

#: Modules this lane may not reach for, ever. Checked by the suite against the import graph rather
#: than trusted: `depth_service` loads Depth-Anything, `sam*_service` loads a segmenter, and either
#: one arriving in this module's transitive imports would mean the laboratory's isolation mode has
#: a hole in it that no reviewer would see. `depth_organ` is deliberately NOT here — it is a pure
#: reader of a field somebody else produced, which is exactly the seam occlusion is allowed.
FORBIDDEN_MODULES: Tuple[str, ...] = (
    "backend.services.depth_service",
    "backend.services.segmentation_service",
    "backend.services.sam2_auto_service",
    "backend.services.sam3_concept_service",
    "backend.services.grounding_detector_service",
    "backend.database",
)

#: The relation vocabulary, reconciled rather than renamed. Asserted at import against the strings
#: the three organs emit, because a lab that calls it `containment` while the organ calls it
#: `nested_within` is two vocabularies pretending to be one — and the pretence survives right up
#: until something tries to join them.
_RECONCILED = {
    RelationKind.NESTED_WITHIN.value: nestedness.RELATION_NESTED_WITHIN,
    RelationKind.MEETS.value: adjacency.RELATION_MEETS,
    RelationKind.IN_FRONT_OF.value: occlusion.RELATION_IN_FRONT_OF,
    RelationKind.COPLANAR.value: occlusion.RELATION_COPLANAR,
}


def _assert_reconciled() -> None:
    for lab_value, organ_value in _RECONCILED.items():
        if lab_value != organ_value:
            raise RuntimeError(
                f"the lab's relation kind {lab_value!r} and the organ's {organ_value!r} have "
                f"drifted apart. One of them is now a relation nothing else in the repository "
                f"knows the name of.")
    for op_key, projection in PROJECTION.items():
        declared = D.operation(op_key).render_projections
        if projection.value not in declared:
            raise RuntimeError(
                f"{op_key} proposes projection {projection.value!r}, which its contract does not "
                f"declare ({list(declared)}).")
    for op_key, adapter in PRIMARY_ADAPTER.items():
        if adapter not in D.operation(op_key).adapters:
            raise RuntimeError(
                f"{op_key} names adapter {adapter!r}, which its contract does not declare.")


_assert_reconciled()


# ── what a caller hands in ───────────────────────────────────────────────────


@dataclass(frozen=True)
class LabContext:
    """Everything about the run that this module is not entitled to decide for itself.

    `now` is a string rather than a clock because the organs in this repository take the same
    discipline: a module that reads the time is a module whose output cannot be reproduced. `clock`
    is optional and monotonic-in-milliseconds; without it `duration_ms` stays null, which the
    contract says is the honest value for an unmeasured duration and 0 is not.
    """
    session_id: str
    run_id: str
    step_id: str
    source_image_digest: str
    now: str
    artifact_id: Optional[str] = None
    device: Optional[str] = None
    clock: Optional[Callable[[], float]] = None
    changed_by: str = "perception_lab"


@dataclass(frozen=True)
class TopologyInput:
    """One extent artifact, in the role the operation consumes it as, and which instance of it.

    `instance_id` is Lane C's, not Lane A's: the contract's `InputRef` names an ARTIFACT, and an
    `extent_set` holds many instances. A pair operation needs one endpoint per role, so the
    reference has to reach one instance deeper. Absent, it resolves when the artifact holds exactly
    one instance and refuses `unknown_reference` when it holds several — a laboratory that picked
    the first would answer a question about a mask nobody selected.
    """
    role: str
    artifact_id: str
    instance_id: Optional[str] = None
    scope: IdentityScope = IdentityScope.SESSION

    def as_ref(self) -> InputRef:
        return InputRef(role=self.role, scope=self.scope, artifact_id=self.artifact_id)


@dataclass(frozen=True)
class DepthArtifact:
    """A PREPARED depth field, supplied from outside this organ. The whole occlusion seam.

    Carries an `artifact_id` so the relation can cite where the ordering came from, and a `field`
    in the shape `depth_organ` accepts — grid, values, adapter, model, revision, whole_frame.
    Nothing in this module can construct one: there is no code path here that produces a depth
    field, which is the difference between declaring a dependency and quietly satisfying it.
    """
    artifact_id: str
    field: Mapping[str, Any]
    scope: IdentityScope = IdentityScope.SESSION


@dataclass(frozen=True)
class TopologyRequest:
    """One resolved step, as this façade needs it.

    `extents` are contract-shaped `PerceptualArtifact` records (models or plain dicts, validated
    either way — an input that does not satisfy the merged contract is not an input this lane will
    measure). `regions` is the explicit-geometry seam described in the module docstring.
    """
    operation: str
    context: LabContext
    inputs: Tuple[TopologyInput, ...] = ()
    parameters: Mapping[str, Any] = dc_field(default_factory=dict)
    extents: Tuple[Any, ...] = ()
    regions: Tuple[Mapping[str, Any], ...] = ()
    depth: Optional[DepthArtifact] = None
    current_region_revs: Mapping[str, int] = dc_field(default_factory=dict)


@dataclass(frozen=True)
class TopologyResult:
    """What one operation produced, and how the run ended.

    `outcome` is here rather than left to the caller because only this module knows which of the
    contract's five nothings happened: a measured emptiness and a refusal are the same shape on a
    screen and the difference is the entire deliverable.

    `field_values` carries a negative-space raster out of band. The payload keeps its shape,
    truncation and statistics; the field itself is large and this lane has no store to put it in.
    """
    artifact: Optional[PerceptualArtifact]
    outcome: RunOutcome
    refusal: Optional[RefusalRecord] = None
    parameters_used: Mapping[str, Any] = dc_field(default_factory=dict)
    dropped_parameters: Tuple[Tuple[str, str], ...] = ()
    clamped_parameters: Tuple[Tuple[str, Any, Any, str], ...] = ()
    field_values: Optional[List[float]] = None
    field_shape: Optional[Tuple[int, int]] = None

    @property
    def refused(self) -> bool:
        return self.refusal is not None


# ── endpoints: an id, a revision, and the geometry behind them ───────────────


@dataclass(frozen=True)
class _Endpoint:
    """One resolved instance: who it is, and what there is to measure."""
    role: str
    artifact_id: str
    instance_id: str
    scope: IdentityScope
    region_id: Optional[str]
    geometry_rev: Optional[int]
    mask_rle: Optional[Mapping[str, Any]]
    box: Optional[Mapping[str, float]]
    stale: bool

    @property
    def key(self) -> str:
        return f"{self.artifact_id}/{self.instance_id}"

    def as_relation_endpoint(self) -> RelationEndpoint:
        return RelationEndpoint(artifact_id=self.artifact_id, instance_id=self.instance_id,
                                scope=self.scope, region_id=self.region_id,
                                geometry_rev=self.geometry_rev)

    def as_region(self) -> Dict[str, Any]:
        """The shape `nestedness_organ`, `adjacency_organ` and `occlusion_organ` already read.

        A fresh dict every time, and never the caller's: those organs take mappings and this lane
        promises not to mutate what it was handed. Building the adapter shape here rather than
        asking callers for it is what "reconcile, do not reimplement" means in practice.
        """
        out: Dict[str, Any] = {"id": self.key}
        if self.mask_rle is not None:
            out["mask_rle"] = dict(self.mask_rle)
        if self.box is not None:
            out["box"] = dict(self.box)
        return out


class _Refused(Exception):
    """An operation stopped with a typed refusal. Carried, never raised past the façade edge."""

    def __init__(self, refusal: RefusalRecord) -> None:
        super().__init__(refusal.message)
        self.refusal = refusal


def _refusal(code: RefusalCode, operation: str, message: str, *, missing: Sequence[str] = (),
             remedy: str = "", detail: Optional[Mapping[str, Any]] = None) -> RefusalRecord:
    return RefusalRecord(code=code, organ=ORGAN, operation=operation, message=message,
                         missing=list(missing), remedy=remedy or None, detail=dict(detail or {}))


def _artifacts_by_id(request: TopologyRequest) -> Dict[str, PerceptualArtifact]:
    """The supplied extent artifacts, validated through the merged contract and keyed by id."""
    out: Dict[str, PerceptualArtifact] = {}
    for raw in request.extents:
        art = raw if isinstance(raw, PerceptualArtifact) else PerceptualArtifact.model_validate(raw)
        out[art.identity.artifact_id] = art
    return out


def _instances_of(art: PerceptualArtifact, operation: str) -> List[Any]:
    if art.identity.artifact_kind is not ArtifactKind.EXTENT_SET:
        raise _Refused(_refusal(
            RefusalCode.MISSING_EXTENT_INPUTS, operation,
            f"{art.identity.artifact_id} is a {art.identity.artifact_kind.value}, and topology "
            f"measures relations between extents",
            missing=[art.identity.artifact_id], remedy="supply an extent_set artifact",
            detail={"reason": "wrong_artifact_kind",
                    "artifact_kind": art.identity.artifact_kind.value}))
    payload = art.measurement.payload
    if payload is None:
        raise _Refused(_refusal(
            RefusalCode.MISSING_EXTENT_INPUTS, operation,
            f"{art.identity.artifact_id} carries its measurement by reference and this lane has no "
            f"store to dereference it with",
            missing=[art.identity.artifact_id],
            remedy="supply the extent set with an inline payload",
            detail={"reason": "payload_elsewhere"}))
    return list(payload.instances)


def _resolve_endpoints(request: TopologyRequest, role: str, *,
                       artifacts: Mapping[str, PerceptualArtifact],
                       allow_many: bool) -> List[_Endpoint]:
    """Every endpoint a role resolved to, or a typed refusal saying which id did not.

    THREE WAYS THIS REFUSES, and they are three different sentences to a person:

        no input in this role at all        `missing_extent_inputs` — nothing was measured
        an artifact id nobody supplied      `unknown_reference`     — that id is not in the session
        an artifact holding several masks   `unknown_reference`     — which one did you mean
    """
    operation = request.operation
    refs = [i for i in request.inputs if i.role == role]
    if not refs:
        spec = D.operation(operation).input_for(role)
        raise _Refused(_refusal(
            spec.refusal_when_missing if spec else RefusalCode.MISSING_EXTENT_INPUTS,
            operation,
            D._message(spec.refusal_when_missing.value if spec else "missing_extent_inputs",
                       operation=operation),
            missing=[role], remedy=spec.description if spec else "",
            detail={"reason": "role_absent", "role": role}))

    out: List[_Endpoint] = []
    for ref in refs:
        art = artifacts.get(ref.artifact_id)
        if art is None:
            raise _Refused(_refusal(
                RefusalCode.UNKNOWN_REFERENCE, operation,
                D._message("unknown_reference", reference=ref.artifact_id),
                missing=[ref.artifact_id],
                remedy="select the artifact first — 'that mask' resolves through ids, never "
                       "through language",
                detail={"reason": "dangling_artifact", "role": role,
                        "artifact_id": ref.artifact_id}))
        instances = _instances_of(art, operation)
        chosen = _choose_instances(instances, ref, operation, allow_many=allow_many)
        for inst in chosen:
            out.append(_endpoint_from(request, ref, art, inst))
    return out


def _choose_instances(instances: Sequence[Any], ref: TopologyInput, operation: str, *,
                      allow_many: bool) -> List[Any]:
    if ref.instance_id is not None:
        found = [i for i in instances if i.instance_id == ref.instance_id]
        if not found:
            raise _Refused(_refusal(
                RefusalCode.UNKNOWN_REFERENCE, operation,
                D._message("unknown_reference", reference=ref.instance_id),
                missing=[ref.instance_id],
                remedy="select an instance the artifact actually holds",
                detail={"reason": "dangling_instance", "role": ref.role,
                        "artifact_id": ref.artifact_id, "instance_id": ref.instance_id,
                        "available": [i.instance_id for i in instances]}))
        return found
    if not instances:
        raise _Refused(_refusal(
            RefusalCode.MISSING_EXTENT_INPUTS, operation,
            f"{ref.artifact_id} holds no instances, so the {ref.role} endpoint has nothing to be",
            missing=[ref.role], remedy="measure or draw an extent first",
            detail={"reason": "empty_extent_set", "role": ref.role,
                    "artifact_id": ref.artifact_id}))
    if allow_many or len(instances) == 1:
        return list(instances)
    raise _Refused(_refusal(
        RefusalCode.UNKNOWN_REFERENCE, operation,
        f"{ref.artifact_id} holds {len(instances)} instances and the step named none of them",
        missing=[ref.role],
        remedy="name the instance — an endpoint is an identity, and a laboratory that picked the "
               "first one would answer about a mask nobody selected",
        detail={"reason": "ambiguous_instance", "role": ref.role,
                "artifact_id": ref.artifact_id,
                "available": [i.instance_id for i in instances]}))


def _endpoint_from(request: TopologyRequest, ref: TopologyInput, art: PerceptualArtifact,
                   inst: Any) -> _Endpoint:
    """One instance → an endpoint, with the explicit-region seam applied and revisions checked."""
    mask = inst.mask_rle
    box = inst.box.model_dump() if inst.box is not None else None
    region_id = inst.region_id
    rev = inst.geometry_rev

    if region_id:
        supplied = next((r for r in request.regions if str(r.get("id")) == str(region_id)), None)
        if supplied is not None:
            supplied_rev = supplied.get("geometry_rev")
            if supplied_rev is not None and rev is not None and int(supplied_rev) != int(rev):
                raise _Refused(_refusal(
                    RefusalCode.UNKNOWN_REFERENCE, request.operation,
                    f"{region_id} was supplied at geometry_rev {int(supplied_rev)} and the extent "
                    f"cites rev {int(rev)}. Two revisions of one region are two shapes.",
                    missing=[str(region_id)],
                    remedy="supply the revision the extent cites, or re-run the extent",
                    detail={"reason": "revision_mismatch", "region_id": str(region_id),
                            "cited": int(rev), "supplied": int(supplied_rev)}))
            if supplied.get("mask_rle") is not None:
                mask = supplied.get("mask_rle")
            if supplied.get("box") is not None and mask is None:
                box = dict(supplied["box"])

    current = request.current_region_revs.get(str(region_id)) if region_id else None
    stale = bool(region_id and rev is not None and current is not None and int(current) != int(rev))

    return _Endpoint(role=ref.role, artifact_id=art.identity.artifact_id,
                     instance_id=inst.instance_id,
                     scope=IdentityScope.CANONICAL if region_id else ref.scope,
                     region_id=region_id, geometry_rev=rev, mask_rle=mask, box=box, stale=stale)


# ── the basis, and the ceiling it carries ────────────────────────────────────


def _rasters(endpoints: Sequence[_Endpoint], operation: str) -> Optional[List[ev.Raster]]:
    """Decode every endpoint's mask onto one raster, or None when the pair is not maskable.

    Returns None rather than raising for a MISSING mask — a box-basis reading is a real, coarser
    measurement and the operations that permit it take that path. An EMPTY mask raises instead:
    zero set pixels is not a coarser extent, it is no extent, and a relation with an endpoint that
    is nowhere is not a relation.
    """
    rasters: List[ev.Raster] = []
    for end in endpoints:
        if end.mask_rle is None:
            return None
        try:
            rasters.append(ev.decode(end.mask_rle))
        except ev.GeometryUnavailable as exc:
            if "empty" in str(exc):
                raise _Refused(_refusal(
                    RefusalCode.MISSING_EXTENT_INPUTS, operation,
                    f"{end.key} carries an empty mask — zero set pixels",
                    missing=[end.role],
                    remedy="re-run or redraw the extent; an empty mask has no endpoint in the "
                           "picture for a relation to attach to",
                    detail={"reason": "empty_mask", "role": end.role, "endpoint": end.key})) from exc
            return None
    try:
        for other in rasters[1:]:
            ev.same_raster(rasters[0], other)
    except ev.GeometryUnavailable:
        return None
    return rasters


def _require_mask(endpoints: Sequence[_Endpoint], operation: str,
                  why: str) -> List[ev.Raster]:
    """The mask path, or a refusal. For the operations whose contract allows no box basis."""
    rasters = _rasters(endpoints, operation)
    if rasters is None:
        raise _Refused(_refusal(
            RefusalCode.MISSING_EXTENT_INPUTS, operation,
            f"{operation} measures on masks and the endpoints did not supply a shared one",
            missing=[e.role for e in endpoints],
            remedy="supply mask-bearing extents on the same raster",
            detail={"reason": "box_basis_not_admissible", "why": why,
                    "endpoints": [e.key for e in endpoints]}))
    return rasters


def _status_for(basis: EpistemicBasis) -> EpistemicStatus:
    """The ceiling, never a choice. `BASIS_CEILINGS` is `epistemics.SUBSTRATE_CEILING` for the two
    bases that ruling covers, and the merged contract asserts the equality at import."""
    return BASIS_CEILINGS[basis]


# ── identity ─────────────────────────────────────────────────────────────────


def _digest(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def relation_id(context: LabContext, kind: str, source: str, target: str, *,
                ordinal: int = 0) -> str:
    """A stable run-local relation id.

    Derived from the step and the endpoints rather than minted from randomness, so that running the
    same step twice produces the same ids and a person comparing two repeats is comparing
    relations rather than trying to line up two sets of uuids. Run-local because it names a step: a
    relation that survives into Semant gets a canonical identity from Lane F's promotion, and it is
    not this one.
    """
    return f"rel_{_digest(context.run_id, context.step_id, kind, source, target, ordinal)[:12]}"


def artifact_id_for(context: LabContext, operation: str) -> str:
    if context.artifact_id:
        return context.artifact_id
    return f"art_{_digest(context.session_id, context.run_id, context.step_id, operation)[:12]}"


# ── artifact construction ────────────────────────────────────────────────────


def _identity(request: TopologyRequest, kind: ArtifactKind,
              endpoints: Sequence[_Endpoint]) -> ArtifactIdentity:
    seen: Dict[str, RegionRef] = {}
    for end in endpoints:
        if end.region_id and end.geometry_rev is not None:
            seen.setdefault(end.region_id, RegionRef(region_id=end.region_id,
                                                     geometry_rev=end.geometry_rev,
                                                     scope=IdentityScope.CANONICAL))
    derived: List[str] = []
    for ref in request.inputs:
        if ref.artifact_id not in derived:
            derived.append(ref.artifact_id)
    return ArtifactIdentity(
        artifact_id=artifact_id_for(request.context, request.operation),
        session_id=request.context.session_id, run_id=request.context.run_id,
        step_id=request.context.step_id, organ_family=ORGAN, artifact_kind=kind,
        operation=request.operation,
        # The ARTIFACT is always session-scoped: the lab minted it. Its ENDPOINTS may be canonical,
        # and that is a different field on purpose — an artifact that inherited canonical scope from
        # what it cites would be a lab measurement wearing Semant's identity.
        identity_scope=IdentityScope.SESSION,
        identity_refs=list(seen.values()),
        input_refs=[i.as_ref() for i in request.inputs],
        derived_from=derived)


def _provenance(request: TopologyRequest, *, adapter: str, revision: Optional[str],
                started: Optional[float], ended: Optional[float]) -> ArtifactProvenance:
    duration = None
    if started is not None and ended is not None:
        duration = max(0, int(round(ended - started)))
    return ArtifactProvenance(
        producer_kind=ProducerKind.ADAPTER, producer=PRODUCER, adapter=adapter,
        model=None, revision=revision,
        source_image_digest=request.context.source_image_digest,
        started_at=None, completed_at=None, duration_ms=duration,
        device=request.context.device, peak_memory_mb=None)


def _lifecycle(context: LabContext) -> ArtifactLifecycle:
    """Always `proposed`. A façade does not curate.

    `kept`, `rejected` and `promoted` are decisions a person makes about a measurement, and an
    organ that arrived at `kept` would be reviewing its own work.
    """
    return ArtifactLifecycle(status=LifecycleState.PROPOSED, changed_at=context.now,
                             changed_by=context.changed_by)


def _interpretation(notes: Optional[str]) -> ArtifactInterpretation:
    """No label. Every one of them.

    This organ reads pixels; it never reads a name, so it has nothing to call what it measured. The
    sentence in `notes` names ids and numbers and nothing about what either endpoint depicts —
    the discipline `nestedness_organ.measure`'s own `detail` string already keeps.
    """
    return ArtifactInterpretation(label=None, label_source=LabelSource.NONE,
                                  epistemic_status=EpistemicStatus.UNCERTAIN, notes=notes)


def _relation_artifact(request: TopologyRequest, *, relations: Sequence[TopologyRelation],
                       pairs_examined: int, endpoints: Sequence[_Endpoint],
                       basis: EpistemicBasis, basis_detail: str, adapter: str,
                       revision: Optional[str], notes: Optional[str],
                       bounded_to: Optional[int] = None,
                       started: Optional[float] = None,
                       ended: Optional[float] = None) -> PerceptualArtifact:
    payload = TopologyRelationSetPayload(variant="topology_relation_set",
                                         pairs_examined=pairs_examined,
                                         relations=list(relations), bounded_to=bounded_to)
    status = _status_for(basis)
    return PerceptualArtifact(
        identity=_identity(request, ArtifactKind.TOPOLOGY_RELATION_SET, endpoints),
        measurement=ArtifactMeasurement(
            payload_variant="topology_relation_set", payload=payload, data_ref=None,
            # NORMALIZED, not the raster. Everything a relation carries is a fraction or a locus in
            # the image's own frame; the raster the pixels were counted on is named in
            # `basis_detail`, and pixel counts say `_pixels` where they appear. Lane A's example
            # artifact declares `mask_rle_hw` for a payload that carries no coordinates at all —
            # this lane's payloads carry loci, and they are normalized.
            coordinate_system=CoordinateSystem.NORMALIZED_XY_TOPLEFT,
            epistemic_status=status, epistemic_basis=basis, basis_detail=basis_detail),
        projection=ArtifactProjection(
            projection_kind=PROJECTION[request.operation],
            hints=_hints(status)),
        interpretation=_interpretation(notes),
        lifecycle=_lifecycle(request.context),
        provenance=_provenance(request, adapter=adapter, revision=revision, started=started,
                               ended=ended))


def _hints(status: EpistemicStatus) -> Dict[str, Any]:
    """Presentation, and nothing that could stand in for the measurement.

    `emphasis: muted` on anything below `measured` is the WAVE2.5 ruling arriving at the eye: a
    box-basis containment of 0.999 should not be drawn as confidently as a mask-basis one of 0.96,
    and a reader who has to open the receipt to find out has already believed the picture.
    """
    return {"palette_role": "relation",
            "emphasis": "primary" if status is EpistemicStatus.MEASURED else "muted",
            "legend": f"{status.value} — read the basis before the number"}


def refusal_artifact(request: TopologyRequest, refusal: RefusalRecord, *,
                     adapter: Optional[str] = None) -> PerceptualArtifact:
    """A refusal IS an artifact: it has a run, a step, a provenance and a place in the ledger.

    Its measurement is `uncertain` on the `declared` basis, which is the honest floor — a refusal
    looked at nothing, and any other status would imply it had.
    """
    return PerceptualArtifact(
        identity=_identity(request, ArtifactKind.REFUSAL, ()),
        measurement=ArtifactMeasurement(
            payload_variant="refusal",
            payload=RefusalPayload(variant="refusal", refusal=refusal), data_ref=None,
            coordinate_system=CoordinateSystem.NORMALIZED_XY_TOPLEFT,
            epistemic_status=EpistemicStatus.UNCERTAIN, epistemic_basis=EpistemicBasis.DECLARED,
            basis_detail="a refusal makes no claim about the image"),
        projection=ArtifactProjection(projection_kind=ProjectionKind.NONE, hints={}),
        interpretation=_interpretation(
            "This is a result, not an error: what was asked, and what was missing."),
        lifecycle=_lifecycle(request.context),
        provenance=_provenance(request,
                               adapter=adapter or PRIMARY_ADAPTER.get(request.operation, ""),
                               revision=None, started=None, ended=None))


# ── the gates every operation passes first ───────────────────────────────────


def _gate(request: TopologyRequest) -> Tuple[Dict[str, Any], List[Tuple[str, str]],
                                             List[Tuple[str, Any, Any, str]]]:
    """The contract's own four gates, run before any geometry is touched.

    Not duplicated from `definitions.py` — CALLED from it. The conductor (Lane D) runs the same
    functions before it dispatches, and that redundancy is deliberate: a façade that trusted its
    caller to have checked would be a façade whose guarantees hold only when it is called the way
    one lane happens to call it today.
    """
    lock = D.check_organ_lock(request.operation, selected_organ=ORGAN.value,
                              mode=SessionMode.ISOLATION)
    if lock is not None:
        raise _Refused(lock)

    resolution = D.resolve_parameters(request.operation, request.parameters)
    if resolution.refusal is not None:
        raise _Refused(resolution.refusal)

    refs = [i.as_ref() for i in request.inputs]
    if request.depth is not None:
        refs.append(InputRef(role="depth", scope=request.depth.scope,
                             artifact_id=request.depth.artifact_id))
    inputs = D.check_inputs(request.operation, refs, for_execution=True)
    if inputs is not None:
        raise _Refused(inputs)
    return resolution.clean, resolution.dropped, resolution.clamped


def _tick(context: LabContext) -> Optional[float]:
    return context.clock() if context.clock is not None else None


# ── containment ──────────────────────────────────────────────────────────────


def containment(request: TopologyRequest) -> TopologyResult:
    """Is the source inside the target? A DIRECTED reading, both ways round.

    `nestedness_organ` measures one direction at a time — inner against outer — so this asks it
    twice and reports whichever holds: `nested_within` when the source lies in the target,
    `contains` when the target lies in the source. Both, never: the organ's own `MAX_SCALE_RATIO`
    makes mutual nesting unreachable, and if that ever changed this would report a contradiction
    rather than silently pick one.

    NO RELATION IS A RESULT. Two shapes measured and found not nested come back as an artifact with
    `pairs_examined: 1` and `relations: []`, and the run's outcome is `empty` — the contract's
    "measured emptiness", which is a different thing from `refused` and says so.
    """
    return _run_pair(request, _containment_relations)


def _containment_relations(request: TopologyRequest, params: Mapping[str, Any],
                           source: _Endpoint, target: _Endpoint
                           ) -> Tuple[List[TopologyRelation], EpistemicBasis, str, str]:
    basis_param = params.get("basis")
    rasters = _basis_choice([source, target], request.operation, basis_param)
    forward = nestedness.measure(source.as_region(), target.as_region())
    reverse = nestedness.measure(target.as_region(), source.as_region())
    if basis_param == "box":
        forward, reverse = _forced_box(source, target), _forced_box(target, source)

    basis = EpistemicBasis(forward["basis"])
    status = _status_for(basis)
    relations: List[TopologyRelation] = []

    for measurement, kind, src, tgt in (
            (forward, RelationKind.NESTED_WITHIN, source, target),
            (reverse, RelationKind.CONTAINS, source, target)):
        if not measurement["nested"]:
            continue
        numbers = _containment_numbers(measurement)
        if rasters is not None and basis is EpistemicBasis.MASK:
            inner, outer = (rasters[0], rasters[1]) if kind is RelationKind.NESTED_WITHIN \
                else (rasters[1], rasters[0])
            clear = ev.containment_clearance(inner, outer)
            numbers.update({"boundary_clearance_px": clear["pixels"],
                            "boundary_clearance_normalized": clear["normalized"],
                            "boundary_nearest_x": clear["nearest_x"],
                            "boundary_nearest_y": clear["nearest_y"]})
        relations.append(TopologyRelation(
            relation_id=relation_id(request.context, kind.value, src.key, tgt.key),
            kind=kind, source=src.as_relation_endpoint(), target=tgt.as_relation_endpoint(),
            # DIRECTED, and the direction is the claim. `nested_within` reads source→target as
            # "the source lies inside the target"; `contains` reads the same arrow the other way.
            # A person correcting an endpoint is correcting which shape is inside which.
            directed=True, basis=basis, epistemic_status=status,
            measurements=numbers, stale=src.stale or tgt.stale))

    detail = forward["detail"] if not relations or relations[0].kind is RelationKind.NESTED_WITHIN \
        else reverse["detail"]
    return relations, basis, forward["basis_detail"], detail


def _containment_numbers(m: Mapping[str, Any]) -> Dict[str, float]:
    """The organ's numbers, plus the thresholds they were judged against.

    The thresholds travel WITH the measurement rather than living only in the organ, because
    `nested: true` is a verdict against a floor and a reader who cannot see the floor cannot
    disagree with the verdict.
    """
    return {
        "containment": float(m["containment"]),
        "scale_ratio": float(m["scale_ratio"]),
        "nesting_index": float(m["nesting_index"]),
        "margin": float(m["margin"]),
        "area_inner": float(m["area_inner"]),
        "area_outer": float(m["area_outer"]),
        "threshold_min_containment": float(nestedness.MIN_CONTAINMENT),
        "threshold_max_scale_ratio": float(nestedness.MAX_SCALE_RATIO),
    }


def _forced_box(inner: _Endpoint, outer: _Endpoint) -> Dict[str, Any]:
    """The box reading when a person asked for the box basis on maskable geometry.

    Asking for it is legitimate — comparing what the coarse substrate would have said is half of
    why the lab exists — and the reading that comes back is `interpretive` exactly as it would be
    if no mask had been there. The masks are dropped rather than "not used": handing the organ a
    region without its mask is the only way to make it take its own box path, and doing it here
    where it is visible beats a flag threaded through the organ.
    """
    return nestedness.measure(_boxes_only(inner), _boxes_only(outer))


def _basis_choice(endpoints: Sequence[_Endpoint], operation: str,
                  requested: Optional[str]) -> Optional[List[ev.Raster]]:
    """Which substrate this reading will rest on, and never a silent upgrade.

    Absent, the runtime takes the best substrate BOTH endpoints carry, exactly as the contract's
    `basis` parameter says. Asked for `mask` on geometry that has none, it refuses rather than
    quietly falling back — a box reading returned to someone who asked for a mask is the coarse
    substrate wearing the fine one's name.
    """
    rasters = _rasters(endpoints, operation)
    if requested == "mask" and rasters is None:
        raise _Refused(_refusal(
            RefusalCode.MISSING_EXTENT_INPUTS, operation,
            f"{operation} was asked for the mask basis and the endpoints do not share one",
            missing=[e.role for e in endpoints],
            remedy="supply mask-bearing extents on the same raster, or drop the basis parameter",
            detail={"reason": "mask_basis_requested_but_unavailable",
                    "endpoints": [e.key for e in endpoints]}))
    if requested == "box":
        return None
    return rasters


# ── adjacency ────────────────────────────────────────────────────────────────


def adjacency_relation(request: TopologyRequest) -> TopologyResult:
    """Do the two extents meet, and along how much of the source's own edge?

    Symmetric in kind and asymmetric in number, and both halves are deliberate. `meets` reads the
    same either way round, so the relation is `directed: false`. The CONTACT FRACTION does not:
    a small shape against a large one meets along most of its own perimeter and a sliver of the
    other's, so the number is named `contact_fraction_of_source_perimeter` rather than left to be
    read as a property of the pair.

    A pair that does not meet AND does not intersect comes back as a `disjoint` relation with the
    measured separation on it — the contract's "positive no-relation", a finding rather than an
    absence. A pair that does not meet and DOES intersect comes back with NO relation and an
    outcome of `empty`, because one shape lying inside another neither meets its edge nor is apart
    from it, and this operation has no third word. Calling that pair `disjoint` because their
    boundaries never touch would be the most confident wrong answer available here.
    """
    return _run_pair(request, _adjacency_relations)


def _adjacency_relations(request: TopologyRequest, params: Mapping[str, Any],
                         source: _Endpoint, target: _Endpoint
                         ) -> Tuple[List[TopologyRelation], EpistemicBasis, str, str]:
    tolerance = int(params.get("contact_tolerance_px") or 0)
    rasters = _basis_choice([source, target], request.operation, params.get("basis"))

    if rasters is not None:
        band = ev.contact_band(rasters[0], rasters[1], tolerance_px=tolerance)
        gap = ev.clearance(rasters[0], rasters[1])
        inter = ev.intersection(rasters[0], rasters[1])
        intersects = bool(inter["pixels"])
        contact = band["fraction_of_source_perimeter"]
        basis = EpistemicBasis.MASK
        basis_detail = (f"per-pixel boundary contact on a shared {rasters[0].h}x{rasters[0].w} "
                        f"raster, tolerance {tolerance}px")
        numbers: Dict[str, float] = {
            "contact_fraction_of_source_perimeter": round(float(contact), 6),
            "contact_pixels": float(band["pixels"]),
            "source_perimeter_pixels": float(band["perimeter_pixels"]),
            "contact_tolerance_px": float(tolerance),
            "clearance_px": float(gap["pixels"]),
            "clearance_normalized": float(gap["normalized"]),
            "nearest_x": float(gap["nearest_x"]),
            "nearest_y": float(gap["nearest_y"]),
            "intersection_pixels": float(inter["pixels"]),
            "threshold_min_contact": float(adjacency.MIN_CONTACT),
        }
        numbers.update(ev.locus_keys("contact_locus", band["locus"]))
        detail = (f"mask boundary contact {contact:.3f} over {band['pixels']} px "
                  f"of {band['perimeter_pixels']}")
    else:
        measurement = adjacency.measure(_boxes_only(source), _boxes_only(target))
        contact = measurement["contact_fraction"]
        # On boxes the best available reading of "do these occupy any common ground" is the boxes'
        # own overlap — `region_geometry.overlap_fraction`, which `nestedness_organ` already takes
        # its box path from. Coarse, like everything else on this substrate, and it only decides
        # whether a NON-meeting pair is reported apart or reported as nothing.
        box_source, box_target = _box_of(source), _box_of(target)
        intersects = bool(box_source and box_target
                          and rg.overlap_fraction(box_source, box_target) > 0.0)
        basis = EpistemicBasis.BOX
        basis_detail = measurement["basis_detail"]
        numbers = {
            "contact_fraction_of_source_perimeter": float(contact),
            "edge_gap": float(measurement["edge_gap"] or 0.0),
            "contact_tolerance_px": float(tolerance),
            "threshold_min_contact": float(adjacency.MIN_CONTACT),
            "threshold_box_tolerance": float(adjacency.BOX_TOLERANCE),
        }
        detail = measurement["detail"]

    status = _status_for(basis)
    meets = contact >= adjacency.MIN_CONTACT
    if not meets and intersects:
        # Measured, and neither word applies. `pairs_examined: 1` with no relation is the contract's
        # measured emptiness, and it is the truthful answer for a pair that overlaps without
        # touching — the finding belongs to `topology.overlap`, and inventing it here would put one
        # fact in two vocabularies.
        return [], basis, basis_detail, (
            f"{detail} — and the two intersect, so they neither meet nor stand apart. "
            f"topology.overlap measures what they do instead.")
    kind = RelationKind.MEETS if meets else RelationKind.DISJOINT
    relation = TopologyRelation(
        relation_id=relation_id(request.context, kind.value, source.key, target.key),
        kind=kind, source=source.as_relation_endpoint(), target=target.as_relation_endpoint(),
        # `meets` and `disjoint` read the same in both directions. The source/target arrow still
        # says which perimeter the fraction is OF, which is why the endpoints are not a set.
        directed=False, basis=basis, epistemic_status=status, measurements=numbers,
        stale=source.stale or target.stale)
    return [relation], basis, basis_detail, detail


def _box_of(endpoint: _Endpoint) -> Optional[Dict[str, float]]:
    """The endpoint's normalized box: its own when it has one, the mask's tight bbox otherwise.

    The same preference `nestedness_organ._box_of` states, for the same reason: where a stored box
    and a mask disagree, `canonicalize_geometry` treats the mask as the authoritative identity.
    """
    if endpoint.mask_rle is not None and mg.rle_is_valid(endpoint.mask_rle):
        derived = mg.rle_bbox_norm(dict(endpoint.mask_rle))
        if derived["w"] > 0 and derived["h"] > 0:
            return derived
    return dict(endpoint.box) if endpoint.box else None


def _boxes_only(endpoint: _Endpoint) -> Dict[str, Any]:
    """The endpoint as the organs' box path sees it: an id and a box, and no mask to distract them.

    Handing an organ a region WITHOUT its mask is the only way to make it take its own box path,
    and doing it here — where a reader can see the mask being dropped — beats threading a flag
    through an organ that has no business knowing this laboratory exists.
    """
    box = _box_of(endpoint)
    return {"id": endpoint.key, "box": dict(box)} if box else {"id": endpoint.key}


# ── overlap and disjointness ─────────────────────────────────────────────────


def overlap(request: TopologyRequest) -> TopologyResult:
    """Exactly how many pixels the two extents share, and where.

    MASK ONLY, and the contract is explicit about why: the intersection of two bounding boxes is
    the intersection of two bounding boxes, and calling it the overlap of the shapes inside them is
    the founding pathology in miniature. Box-only endpoints refuse rather than degrade.
    """
    return _run_pair(request, _overlap_relations)


def _overlap_relations(request: TopologyRequest, params: Mapping[str, Any],
                       source: _Endpoint, target: _Endpoint
                       ) -> Tuple[List[TopologyRelation], EpistemicBasis, str, str]:
    rasters = _require_mask([source, target], request.operation,
                            "an intersection of two boxes is not an overlap of the shapes in them")
    inter = ev.intersection(rasters[0], rasters[1])
    numbers: Dict[str, float] = {
        "intersection_pixels": float(inter["pixels"]),
        "intersection_fraction_of_source": round(float(inter["fraction_of_source"]), 6),
        "intersection_fraction_of_target": round(float(inter["fraction_of_target"]), 6),
        "iou": round(float(inter["iou"]), 6),
        "area_source_pixels": float(inter["area_source"]),
        "area_target_pixels": float(inter["area_target"]),
    }
    numbers.update(ev.locus_keys("intersection_locus", inter["locus"]))

    if inter["pixels"]:
        kind = RelationKind.OVERLAPS
        detail = (f"mask intersection {inter['pixels']} px — "
                  f"{inter['fraction_of_source']:.3f} of the source, "
                  f"{inter['fraction_of_target']:.3f} of the target, IoU {inter['iou']:.3f}")
    else:
        # ONE MEANING OF `disjoint` ACROSS THE WHOLE ORGAN: no shared pixels AND no contact. Two
        # shapes that abut share no pixels, and calling them disjoint here while
        # `topology.adjacency` calls the same pair `meets` would put one picture in two
        # vocabularies — the reader would have to know which operation ran to know what the word
        # meant. A pair that touches without overlapping is measured and reported as neither.
        band = ev.contact_band(rasters[0], rasters[1], tolerance_px=0)
        numbers["contact_pixels"] = float(band["pixels"])
        if band["pixels"]:
            return [], EpistemicBasis.MASK, \
                f"exact per-pixel intersection on a shared {rasters[0].h}x{rasters[0].w} raster", \
                (f"no shared pixels, and {band['pixels']} px of boundary contact — these touch "
                 f"without overlapping, which topology.adjacency measures")
        kind = RelationKind.DISJOINT
        gap = ev.clearance(rasters[0], rasters[1])
        numbers.update({"clearance_px": float(gap["pixels"]),
                        "clearance_normalized": float(gap["normalized"]),
                        "nearest_x": float(gap["nearest_x"]),
                        "nearest_y": float(gap["nearest_y"])})
        detail = (f"no shared pixels — measured apart, nearest approach {gap['pixels']:.1f} px "
                  f"({gap['normalized']:.4f} of the frame diagonal)")

    relation = TopologyRelation(
        relation_id=relation_id(request.context, kind.value, source.key, target.key),
        kind=kind, source=source.as_relation_endpoint(), target=target.as_relation_endpoint(),
        directed=False, basis=EpistemicBasis.MASK, epistemic_status=EpistemicStatus.MEASURED,
        measurements=numbers, stale=source.stale or target.stale)
    return [relation], EpistemicBasis.MASK, \
        f"exact per-pixel intersection on a shared {rasters[0].h}x{rasters[0].w} raster", detail


def disjoint(request: TopologyRequest) -> TopologyResult:
    """Are they genuinely apart, and by how much?

    The operation that exists so that "no" can be a measurement. It reports the nearest approach in
    pixels, as a fraction of the frame diagonal, and WHERE on the source that approach happens — a
    separation with no locus is a number a person cannot check against the picture.

    A pair that turns out to be in contact comes back as `meets` with a zero clearance. The
    operation declares both kinds precisely so the contradictory finding has somewhere to go: an
    operation that could only report its own name would be a question that cannot be answered no.

    A pair that intersects without their boundaries touching — one shape inside another — is
    neither, and comes back measured and empty. See `adjacency_relation` for why that is not
    `disjoint`.
    """
    return _run_pair(request, _disjoint_relations)


def _disjoint_relations(request: TopologyRequest, params: Mapping[str, Any],
                        source: _Endpoint, target: _Endpoint
                        ) -> Tuple[List[TopologyRelation], EpistemicBasis, str, str]:
    rasters = _require_mask([source, target], request.operation,
                            "a separation measured between two boxes is a separation between two "
                            "boxes")
    inter = ev.intersection(rasters[0], rasters[1])
    gap = ev.clearance(rasters[0], rasters[1])
    band = ev.contact_band(rasters[0], rasters[1], tolerance_px=0)
    apart = inter["pixels"] == 0 and band["pixels"] == 0

    numbers: Dict[str, float] = {
        "clearance_px": float(gap["pixels"]),
        "clearance_normalized": float(gap["normalized"]),
        "nearest_x": float(gap["nearest_x"]),
        "nearest_y": float(gap["nearest_y"]),
        "intersection_pixels": float(inter["pixels"]),
        "contact_pixels": float(band["pixels"]),
    }
    if apart:
        kind = RelationKind.DISJOINT
        detail = (f"measured apart: nearest approach {gap['pixels']:.1f} px "
                  f"({gap['normalized']:.4f} of the frame diagonal), no shared pixels and no "
                  f"boundary contact")
    elif band["pixels"]:
        kind = RelationKind.MEETS
        numbers.update(ev.locus_keys("contact_locus", band["locus"]))
        detail = (f"not apart: {inter['pixels']} shared px and {band['pixels']} px of boundary "
                  f"contact")
    else:
        return [], EpistemicBasis.MASK, \
            f"chamfer distance transform on a shared {rasters[0].h}x{rasters[0].w} raster", \
            (f"neither apart nor meeting: {inter['pixels']} shared px and no boundary contact, "
             f"which is one shape lying within the other. topology.containment reads that.")

    relation = TopologyRelation(
        relation_id=relation_id(request.context, kind.value, source.key, target.key),
        kind=kind, source=source.as_relation_endpoint(), target=target.as_relation_endpoint(),
        directed=False, basis=EpistemicBasis.MASK, epistemic_status=EpistemicStatus.MEASURED,
        measurements=numbers, stale=source.stale or target.stale)
    return [relation], EpistemicBasis.MASK, \
        f"chamfer distance transform on a shared {rasters[0].h}x{rasters[0].w} raster", detail


# ── negative space ───────────────────────────────────────────────────────────


def negative_space(request: TopologyRequest) -> TopologyResult:
    """The shape of what the figures are NOT, as a scalar field.

    The mask complement plus a distance transform — `mask_geometry.soft_field_from_mask`'s geometry,
    taken with one change that matters for a laboratory: the field is TRUNCATED at
    `max_distance` rather than normalized to its own deepest point. A field rescaled to its own
    maximum looks identical in an image whose ground is a corridor and one whose ground is a plain,
    and the lab exists to compare runs.

    The raster leaves through `TopologyResult.field_values`, not through the artifact. The payload
    keeps the shape, the truncation and the statistics — which is what makes a pointer readable —
    and Lane F attaches the `field_ref` when there is a store to point at.
    """
    started = _tick(request.context)
    try:
        params, dropped, clamped = _gate(request)
        artifacts = _artifacts_by_id(request)
        figures = _resolve_endpoints(request, "figure", artifacts=artifacts, allow_many=True)
        rasters = _require_mask(figures, request.operation,
                                "a distance transform needs pixels, and a box has none")
        max_distance = float(params.get("max_distance") or 1.0)
        try:
            measured = ev.negative_space(rasters, max_distance=max_distance)
        except ev.GeometryUnavailable as exc:
            raise _Refused(_refusal(
                RefusalCode.MISSING_EXTENT_INPUTS, request.operation, str(exc),
                missing=["figure"], remedy="supply figures that leave some ground to measure",
                detail={"reason": "no_negative_space"})) from exc
    except _Refused as refused:
        return _refused_result(request, refused)

    payload = NegativeSpaceFieldPayload(
        variant="negative_space_field",
        figure_instance_ids=[e.instance_id for e in figures],
        max_distance_used=round(min(1.0, max(0.0, max_distance)), 6),
        field_shape=list(measured["shape"]), field_ref=None,
        statistics=dict(measured["statistics"]))

    artifact = PerceptualArtifact(
        identity=_identity(request, ArtifactKind.NEGATIVE_SPACE_FIELD, figures),
        measurement=ArtifactMeasurement(
            payload_variant="negative_space_field", payload=payload, data_ref=None,
            # The one payload in this lane that IS in raster coordinates: `field_shape` is [h, w]
            # and the field is indexed on it.
            coordinate_system=CoordinateSystem.MASK_RLE_HW,
            epistemic_status=EpistemicStatus.MEASURED, epistemic_basis=EpistemicBasis.MASK,
            basis_detail=("mask complement, then a chamfer distance transform truncated at "
                          "max_distance_used")),
        projection=ArtifactProjection(projection_kind=PROJECTION[request.operation],
                                      hints={"palette_role": "ground", "emphasis": "primary",
                                             "legend": "distance from the figure, not the figure"}),
        interpretation=_interpretation(
            f"ground covers {measured['statistics']['ground_fraction']:.3f} of the frame; the "
            f"deepest point of it lies {measured['statistics']['max_clearance_normalized']:.4f} "
            f"of a diagonal from the nearest figure"),
        lifecycle=_lifecycle(request.context),
        provenance=_provenance(request, adapter=PRIMARY_ADAPTER[request.operation],
                               revision=None, started=started, ended=_tick(request.context)))

    return TopologyResult(artifact=artifact, outcome=RunOutcome.READY, parameters_used=params,
                          dropped_parameters=tuple(dropped), clamped_parameters=tuple(clamped),
                          field_values=measured["field"],
                          field_shape=(measured["shape"][0], measured["shape"][1]))


# ── all pairs ────────────────────────────────────────────────────────────────

#: Which measurement answers which requested relation kind. `nested_within` and `contains` are one
#: measurement read from two ends, so asking for either runs containment once.
_FAMILY_OF: Mapping[str, str] = {
    RelationKind.NESTED_WITHIN.value: "containment",
    RelationKind.CONTAINS.value: "containment",
    RelationKind.MEETS.value: "adjacency",
    RelationKind.OVERLAPS.value: "overlap",
    RelationKind.DISJOINT.value: "separation",
}


def all_pairs(request: TopologyRequest) -> TopologyResult:
    """The relation graph over an explicitly bounded set. Bounded by the person, never widened.

    Pairs grow quadratically, which is why `max_regions` is a hard clamp and why the operation
    declares `requires_confirmation`. The set is whatever the person selected; this walks each
    unordered pair once and asks the requested families of it.

    A pair that refuses — an empty mask, two different rasters — does not sink the graph. It is
    counted in `pairs_examined` and contributes no relation, because in a sweep a refusal per pair
    is noise rather than a coverage claim; `find_nested_pairs` made the same call for the same
    reason. What a caller sees is a shorter relation list against a pair count it can check.
    """
    started = _tick(request.context)
    try:
        params, dropped, clamped = _gate(request)
        artifacts = _artifacts_by_id(request)
        members = _resolve_endpoints(request, "members", artifacts=artifacts, allow_many=True)
        if len(members) < 2:
            raise _Refused(_refusal(
                RefusalCode.MISSING_EXTENT_INPUTS, request.operation,
                f"all_pairs needs at least two extents; {len(members)} resolved",
                missing=["members"], remedy="select a bounded set of two or more extents",
                detail={"reason": "too_few_members", "resolved": len(members)}))

        bound = int(params.get("max_regions") or len(members))
        bound = max(2, min(bound, len(members)))
        dropped_members = [e.key for e in members[bound:]]
        members = members[:bound]

        families, dropped_kinds = _requested_families(params)
        if dropped_kinds:
            clamped = list(clamped) + [("relations", dropped_kinds, sorted(families),
                                        "clamped to this operation's declared relation_kinds")]
    except _Refused as refused:
        return _refused_result(request, refused)

    relations: List[TopologyRelation] = []
    examined = 0
    bases: set = set()
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            examined += 1
            a, b = members[i], members[j]
            for measured, basis in _pair_relations(request, params, a, b, families):
                relations.append(measured)
                bases.add(basis)

    # THE WEAKER BASIS GOVERNS the graph as a whole, exactly as `occlusion_organ` rules for a pair:
    # a graph containing one box-basis edge is not a measured graph. The individual relations keep
    # their own basis, so a reader can see which edges are which.
    basis = EpistemicBasis.BOX if EpistemicBasis.BOX in bases else EpistemicBasis.MASK
    artifact = _relation_artifact(
        request, relations=relations, pairs_examined=examined, endpoints=members, basis=basis,
        basis_detail=(f"{len(members)} extents, {examined} unordered pairs, families "
                      f"{sorted(families)}"
                      + (f"; {len(dropped_members)} member(s) beyond the bound were not examined"
                         if dropped_members else "")),
        adapter=PRIMARY_ADAPTER[request.operation], revision=None,
        notes=(f"{len(relations)} relation(s) over {examined} pair(s) of {len(members)} extents"),
        bounded_to=len(members), started=started, ended=_tick(request.context))

    return TopologyResult(
        artifact=artifact,
        outcome=RunOutcome.READY if relations else RunOutcome.EMPTY,
        parameters_used=params, dropped_parameters=tuple(dropped),
        clamped_parameters=tuple(clamped))


def _requested_families(params: Mapping[str, Any]) -> Tuple[set, List[str]]:
    """Which measurement families this graph runs, and which requested kinds were not declared."""
    declared = set(D.operation("topology.all_pairs").relation_kinds)
    asked = params.get("relations")
    if not asked:
        return {"containment", "adjacency", "overlap", "separation"}, []
    kept = [k for k in asked if k in declared]
    dropped = [k for k in asked if k not in declared]
    return ({_FAMILY_OF[k] for k in kept} or {"containment", "adjacency", "overlap",
                                              "separation"}), dropped


def _pair_relations(request: TopologyRequest, params: Mapping[str, Any], a: _Endpoint,
                    b: _Endpoint, families: set
                    ) -> List[Tuple[TopologyRelation, EpistemicBasis]]:
    """Every requested family, measured over one unordered pair. Refusals skip the pair."""
    out: List[Tuple[TopologyRelation, EpistemicBasis]] = []
    if "containment" in families:
        try:
            rels, basis, _, _ = _containment_relations(request, params, a, b)
            out.extend((r, basis) for r in rels)
        except (_Refused, nestedness.NestednessRefusal):
            pass
    if "adjacency" in families:
        try:
            rels, basis, _, _ = _adjacency_relations(request, params, a, b)
            out.extend((r, basis) for r in rels
                       if r.kind is RelationKind.MEETS or "separation" in families)
        except (_Refused, adjacency.AdjacencyRefusal):
            pass
    if "overlap" in families:
        try:
            rels, basis, _, _ = _overlap_relations(request, params, a, b)
            out.extend((r, basis) for r in rels
                       if r.kind is RelationKind.OVERLAPS or "separation" in families)
        except _Refused:
            pass
    if "separation" in families and not any(
            r.kind in (RelationKind.DISJOINT, RelationKind.MEETS) for r, _ in out):
        try:
            rels, basis, _, _ = _disjoint_relations(request, params, a, b)
            out.extend((r, basis) for r in rels)
        except _Refused:
            pass
    return _dedupe(out)


def _dedupe(pairs: Sequence[Tuple[TopologyRelation, EpistemicBasis]]
            ) -> List[Tuple[TopologyRelation, EpistemicBasis]]:
    """One relation per (kind, source, target). Two families can reach the same finding — overlap
    and separation both report `disjoint` — and reporting it twice would make a graph look denser
    than the picture is."""
    seen: set = set()
    out = []
    for relation, basis in pairs:
        key = (relation.kind.value,
               f"{relation.source.artifact_id}/{relation.source.instance_id}",
               f"{relation.target.artifact_id}/{relation.target.instance_id}")
        if key in seen:
            continue
        seen.add(key)
        out.append((relation, basis))
    return out


# ── occlusion: the prepared-depth seam ───────────────────────────────────────


def occlusion_relation(request: TopologyRequest) -> TopologyResult:
    """Is the source in front of the target, or are they at one depth?

    THE ONLY OPERATION HERE WITH A DEPENDENCY, and the dependency is satisfied by SUPPLY. A
    prepared depth field arrives on the request; `occlusion_organ` reads it; nothing in this module
    can make one. Without it the answer is `missing_depth_artifact` — a typed refusal naming what
    would satisfy it — rather than a silent call to a model this phase has not gated.

    Mask endpoints only, and that is the organ's own ruling rather than this lane's caution: a
    box's depth is the arithmetic mean of a thing and the thing behind it, so an occlusion read off
    two boxes offers the pathology as the evidence for itself. The contract's single allowed basis
    for this operation is `depth_artifact`, which names the field the ordering came from — the
    masks say WHERE to read it, and the field says what is nearer.
    """
    started = _tick(request.context)
    try:
        params, dropped, clamped = _gate(request)
        artifacts = _artifacts_by_id(request)
        source = _one(_resolve_endpoints(request, "source", artifacts=artifacts, allow_many=False))
        target = _one(_resolve_endpoints(request, "target", artifacts=artifacts, allow_many=False))
        if request.depth is None:
            # `_gate` has usually refused already: `check_inputs(for_execution=True)` reads the
            # contract's `required_for_execution` on the depth role and returns exactly this code.
            # This is the second lock, and it is reachable — a caller that put a `depth` role in
            # `inputs` rather than on `request.depth` satisfies the gate's arithmetic while leaving
            # this façade with no field to read, and answering anyway would be answering from
            # nothing.
            raise _Refused(_refusal(
                RefusalCode.MISSING_DEPTH_ARTIFACT, request.operation,
                D._message("missing_depth_artifact", operation=request.operation),
                missing=["depth"],
                remedy="supply a prepared depth artifact, or wait for the Depth phase",
                detail={"role": "depth", "artifact_kinds": ["depth_field"], "min": 1, "max": 1,
                        "may_invoke": False}))
        _require_mask([source, target], request.operation,
                      "a box's depth averages a thing with whatever it occludes")
        try:
            measurement = occlusion.measure(source.as_region(), target.as_region(),
                                            dict(request.depth.field))
        except occlusion.OcclusionRefusal as exc:
            # RELAYED, not re-classified. The organ refuses for several different reasons — a
            # malformed field, a field from another checkpoint, too few covered cells — and this
            # lane deciding which of them a caller meant would be a guess wearing a typed code.
            raise _Refused(_refusal(
                RefusalCode.INVALID_PARAMETERS, request.operation,
                f"the occlusion organ refused this pair: {exc}",
                remedy="check the supplied depth field and the endpoints' coverage of it",
                detail={"reason": "occlusion_refusal", "organ": occlusion.ORGAN,
                        "detail": str(exc)})) from exc
    except _Refused as refused:
        return _refused_result(request, refused, adapter=PRIMARY_ADAPTER["topology.occlusion"])

    front = str(measurement.get("front_region_id") or "")
    if measurement["separated"]:
        kind = RelationKind.IN_FRONT_OF
        # DIRECTED, and the direction is measured rather than inherited from the argument order:
        # source→target reads "the source is in front of the target", so when the organ finds the
        # target nearer the endpoints are swapped rather than the sign flipped.
        src, tgt = (source, target) if front == source.key else (target, source)
        directed = True
    else:
        kind = RelationKind.COPLANAR
        src, tgt = source, target
        directed = False

    numbers = {
        "dominance": float(measurement["dominance"]),
        "separation": float(measurement["separation"]),
        "depth_gap": float(measurement["depth_gap"]),
        "rank_gap": float(measurement["rank_gap"]),
        "source_depth_mean": float(measurement["a_depth"]),
        "target_depth_mean": float(measurement["b_depth"]),
        "source_cells": float(measurement["a_cells"]),
        "target_cells": float(measurement["b_cells"]),
        "threshold_min_separation": float(occlusion.MIN_SEPARATION),
        "threshold_min_cells_per_side": float(occlusion.MIN_CELLS_PER_SIDE),
    }

    relation = TopologyRelation(
        relation_id=relation_id(request.context, kind.value, src.key, tgt.key),
        kind=kind, source=src.as_relation_endpoint(), target=tgt.as_relation_endpoint(),
        directed=directed, basis=EpistemicBasis.DEPTH_ARTIFACT,
        epistemic_status=_status_for(EpistemicBasis.DEPTH_ARTIFACT),
        measurements=numbers, stale=src.stale or tgt.stale)

    artifact = _relation_artifact(
        request, relations=[relation], pairs_examined=1, endpoints=[source, target],
        basis=EpistemicBasis.DEPTH_ARTIFACT,
        basis_detail=(f"an ordering statistic over the SUPPLIED depth field "
                      f"{request.depth.artifact_id}, read at the endpoints' mask cells. This "
                      f"laboratory did not compute the field and cannot."),
        adapter=PRIMARY_ADAPTER["topology.occlusion"],
        revision=str(request.depth.field.get("revision") or "") or None,
        notes=measurement["detail"], started=started, ended=_tick(request.context))

    return TopologyResult(artifact=artifact, outcome=RunOutcome.READY, parameters_used=params,
                          dropped_parameters=tuple(dropped), clamped_parameters=tuple(clamped))


# ── the shared pair runner ───────────────────────────────────────────────────


def _one(endpoints: Sequence[_Endpoint]) -> _Endpoint:
    return endpoints[0]


def _run_pair(request: TopologyRequest, measure: Callable[..., Any]) -> TopologyResult:
    """Gate, resolve two endpoints, measure, build the artifact. The shape of four operations.

    One runner rather than four, so that the gates cannot be applied unevenly: an operation that
    forgot to check its inputs would be a hole in exactly the law the contract's `check_inputs`
    exists to close, and it would be invisible in review because the other three do it correctly.
    """
    started = _tick(request.context)
    try:
        params, dropped, clamped = _gate(request)
        artifacts = _artifacts_by_id(request)
        source = _one(_resolve_endpoints(request, "source", artifacts=artifacts, allow_many=False))
        target = _one(_resolve_endpoints(request, "target", artifacts=artifacts, allow_many=False))
        relations, basis, basis_detail, detail = measure(request, params, source, target)
    except _Refused as refused:
        return _refused_result(request, refused)
    except (nestedness.NestednessRefusal, adjacency.AdjacencyRefusal) as exc:
        # The organs refuse degenerate geometry — a region against itself, an area below their own
        # floor. Relayed as `missing_extent_inputs` because what is missing is a measurable extent,
        # and with the organ's own sentence so a reader is told which floor it fell below.
        return _refused_result(request, _Refused(_refusal(
            RefusalCode.MISSING_EXTENT_INPUTS, request.operation,
            f"the organ refused this pair: {exc}",
            remedy="supply two distinct extents with measurable geometry",
            detail={"reason": "organ_refusal", "detail": str(exc)})))

    artifact = _relation_artifact(
        request, relations=relations, pairs_examined=1, endpoints=[source, target], basis=basis,
        basis_detail=basis_detail, adapter=PRIMARY_ADAPTER[request.operation], revision=None,
        notes=detail, started=started, ended=_tick(request.context))
    return TopologyResult(
        artifact=artifact,
        # READY when something stood in a relation; EMPTY when the pair was measured and nothing
        # did. `pairs_examined: 1` on that empty artifact is what makes it a measurement rather
        # than an absence of one — see `TopologyRelationSetPayload`.
        outcome=RunOutcome.READY if relations else RunOutcome.EMPTY,
        parameters_used=params, dropped_parameters=tuple(dropped),
        clamped_parameters=tuple(clamped))


def _refused_result(request: TopologyRequest, refused: _Refused, *,
                    adapter: Optional[str] = None) -> TopologyResult:
    """A typed refusal, and an artifact for it WHEN THE CONTRACT ALLOWS ONE.

    TWO REFUSALS CANNOT BE ARTIFACTS, and finding that out is worth stating plainly.
    `PerceptualArtifact` requires `identity.operation` to be a declared operation OF the organ that
    produced it, so `unsupported_operation` (nobody declares that key) and `organ_locked` (another
    organ declares it) have no artifact they could legally inhabit. That is Lane A being right
    rather than Lane A being incomplete: those two are PLAN-time refusals about a request that was
    never a topology operation, and `LabPlan.refusals` and `LabRun.refusals` are the lists they
    belong in. `TopologyResult.refusal` is always set; `.artifact` is None for exactly these two.
    """
    refusal = refused.refusal
    outcome = (RunOutcome.UNAVAILABLE
               if refusal.code is RefusalCode.CAPABILITY_UNAVAILABLE else RunOutcome.REFUSED)
    artifact = None
    if request.operation in RUNNERS:
        artifact = refusal_artifact(request, refusal, adapter=adapter)
    return TopologyResult(artifact=artifact, outcome=outcome, refusal=refusal)


# ── the dispatcher ───────────────────────────────────────────────────────────

#: Every declared topology operation, and the callable that runs it. Built from the contract's own
#: registry rather than hand-listed, so an operation added to the organ and not implemented here
#: fails at import instead of at the moment a person asks for it.
RUNNERS: Mapping[str, Callable[[TopologyRequest], TopologyResult]] = {
    "topology.containment": containment,
    "topology.adjacency": adjacency_relation,
    "topology.overlap": overlap,
    "topology.disjoint": disjoint,
    "topology.negative_space": negative_space,
    "topology.all_pairs": all_pairs,
    "topology.occlusion": occlusion_relation,
}


def _assert_every_operation_runs() -> None:
    declared = {op.key for op in D.operations_for(ORGAN.value)}
    if declared != set(RUNNERS):
        raise RuntimeError(
            f"the topology organ declares {sorted(declared)} and this façade runs "
            f"{sorted(RUNNERS)}. A declared operation with no runner is a control a person can "
            f"press that does nothing.")


_assert_every_operation_runs()


def run(request: TopologyRequest) -> TopologyResult:
    """Run one topology operation. The single entry point a conductor calls.

    An unknown key does not reach a runner: `check_organ_lock` returns `unsupported_operation` for
    a key no organ declares and `organ_locked` for one another organ owns, and both come back as
    refusal ARTIFACTS rather than exceptions — a laboratory records what it would not do.
    """
    runner = RUNNERS.get(request.operation)
    if runner is None:
        lock = D.check_organ_lock(request.operation, selected_organ=ORGAN.value,
                                  mode=SessionMode.ISOLATION)
        return _refused_result(request, _Refused(lock))
    return runner(request)


__all__ = ["ORGAN", "PRODUCER", "PRIMARY_ADAPTER", "PROJECTION", "FORBIDDEN_MODULES", "RUNNERS",
           "LabContext", "TopologyInput", "DepthArtifact", "TopologyRequest", "TopologyResult",
           "relation_id", "artifact_id_for", "refusal_artifact", "containment",
           "adjacency_relation", "overlap", "disjoint", "negative_space", "all_pairs",
           "occlusion_relation", "run"]
