"""
PERCEPTUAL-FORMS-001H — producing a form directly, and the sixth record kind that has to exist.

A DERIVATION IS NOT A RUN AND IT CANNOT BE AN ARTIFACT. Sixteen of the nineteen forms are declared
by no operation, and `ArtifactIdentity.operation` is required — so a `PerceptualArtifact` of
`extent.hole_set` would have to name an operation that never ran, and `PerceptualArtifact` refuses
exactly that. Nothing here softens it. What a derivation produces is a payload, a verdict, a
ceiling and a list of omissions, and this module gives that its own record, its own id prefix and
its own collection, so that nothing downstream can mistake one for a measurement.

    THE CONTRACT HAS FIVE RECORD KINDS AND THIS IS A SIXTH. It is deliberately NOT added to
    `contracts/perception-lab.v1.json`: freezing a record shape the phase has not reviewed is what
    the form grammar was built to prevent, and Lane A owns that file. It reuses the contract's own
    types throughout — payload variants, refusal records, statuses, bases — so it is one
    vocabulary written down twice rather than two vocabularies. Reported as a gap in the finding.

WHAT A DERIVATION READS AND WHAT IT NEVER TOUCHES. It reads `PerceptualArtifact` records that are
already in the ledger, and the person's own decisions out of `parameters`. It calls no adapter,
loads no model, opens no image, and writes nothing outside the derivation collection. There is no
code path here that could promote anything to canon — see `no_promotion` in the test suite, which
reads this module's import graph rather than trusting the sentence.

THE PERSON'S DECISIONS ARRIVE AS PARAMETERS, WHICH IS THE WHOLE OF "HYPOTHESES ARE NOT ACCEPTED
AUTOMATICALLY". Nothing here computes a grouping, paints an inferred region, proposes a parent or
picks a reading. A fusion with no proposed members produces an empty hypothesis set with its
`fragments_considered` intact, which is the honest answer to "nobody grouped anything" and is not
the same as "no grouping was supportable".

AN UNDECLARED PARAMETER IS DROPPED AND RECORDED, never carried and never fatal — the discipline
`resolver.resolve` already applies to a planner's proposal, applied here to a person's form. A
model that will one day propose a derivation gets the same treatment, and the attempt stays
visible.

PURE. No database, no network, no model, no adapter, no image. The clock and the id factory are
injected.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.perception_lab import (EpistemicBasis, EpistemicStatus, GroundKind,
                                            OrganFamily, PartitionPart, PerceptualArtifact,
                                            RefusalCode, RefusalRecord)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import extent_composites as EC
from backend.services.perception_lab import extent_forms as EF
from backend.services.perception_lab import producers as PR
from backend.services.perception_lab import topology_forms as TF
from backend.services.perception_lab.extent_composites import (alternatives as ALT,
                                                               density as DEN, fusion as FUS,
                                                               grounds as GR, hierarchy as HIER,
                                                               partition as PART, sources as SRC)

ORGAN_OF = {"extent": OrganFamily.EXTENT, "topology": OrganFamily.TOPOLOGY}

#: What a derivation record is called in the store. A different word from `artifact` on purpose:
#: a reader scanning a collection list should not have to remember which of two names means the
#: thing that cannot be promoted.
RECORD_KIND = "perception_lab_derivation"


class DroppedParameter(BaseModel):
    """A key the person's form carried that the form does not declare. Recorded, not silent."""
    model_config = ConfigDict(extra="forbid")
    name: str
    reason: str


class LabDerivation(BaseModel):
    """One form, computed from recorded artifacts, with everything that qualifies it.

    NO LIFECYCLE FIELD, AND THAT IS THE DESIGN. `PerceptualArtifact` carries one because an
    artifact can be kept, promoted or discarded. A derivation has no such ladder to climb: it is
    not a measurement, nothing may promote it, and a `lifecycle` field would be the first rung.
    """
    model_config = ConfigDict(extra="forbid")

    derivation_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    form: str = Field(min_length=1)
    organ: OrganFamily
    payload_variant: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    producible: bool
    writable_as_artifact: bool
    ceiling: EpistemicStatus
    basis: EpistemicBasis
    partition: Optional[str] = None
    producer: str = Field(min_length=1)
    producer_kind: str = Field(min_length=1)
    producer_revision: Optional[str] = None
    source_image_digest: str = Field(min_length=8)
    input_artifact_ids: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dropped_parameters: List[DroppedParameter] = Field(default_factory=list)
    refusals: List[RefusalRecord] = Field(default_factory=list)
    omitted: List[Dict[str, str]] = Field(default_factory=list)
    measurements: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(min_length=1)


class DerivationRefused(Exception):
    """A typed no, in flight. `.refusal` is the record; the message is only for a traceback."""

    def __init__(self, refusal: RefusalRecord) -> None:
        super().__init__(refusal.message)
        self.refusal = refusal


def _refuse(code: RefusalCode, organ: OrganFamily, message: str, *,
            missing: Sequence[str] = (), remedy: str = "",
            detail: Optional[Mapping[str, Any]] = None) -> None:
    raise DerivationRefused(RefusalRecord(
        code=code, organ=organ, message=message, missing=list(missing),
        remedy=remedy or None, detail=dict(detail or {})))


@dataclass(frozen=True)
class Context:
    """Everything one derivation is handed: the ledger it reads, and the person's decisions."""
    form_key: str
    artifacts: Tuple[PerceptualArtifact, ...]
    parameters: Mapping[str, Any]
    source_image_digest: str
    dropped: List[DroppedParameter] = field(default_factory=list)

    def extents(self) -> Tuple[SRC.ExtentSource, ...]:
        """Every supplied `extent_set`, read. Refuses when none was supplied.

        THE REFUSAL NAMES THE INPUT FORM RATHER THAN THE ARTIFACT KIND, because that is the
        question a person can act on: `extent.hole_set` reads a hard mask, and being told "no
        extent_set" sends somebody looking for a kind they never chose.
        """
        found = tuple(SRC.extent_set(a) for a in self.artifacts
                      if a.measurement.payload_variant.value == "extent_set")
        if not found:
            _refuse(RefusalCode.MISSING_EXTENT_INPUTS, OrganFamily.EXTENT,
                    f"{self.form_key} reads {list(D.form(self.form_key).accepted_input_forms)} "
                    f"and no extent set was supplied.",
                    missing=list(D.form(self.form_key).accepted_input_forms),
                    remedy="select an extent set in this session and derive again")
        return found

    def relations(self) -> Tuple[PerceptualArtifact, ...]:
        found = tuple(a for a in self.artifacts
                      if a.measurement.payload_variant.value == "topology_relation_set")
        if not found:
            _refuse(RefusalCode.MISSING_EXTENT_INPUTS, OrganFamily.TOPOLOGY,
                    f"{self.form_key} reads a topology.pair_relation set and none was supplied.",
                    missing=["topology.pair_relation"],
                    remedy="measure a relation set in this session and derive again")
        return found

    def take(self, name: str, default: Any = None) -> Any:
        return self.parameters.get(name, default)

    def source_extents(self) -> Tuple[SRC.ExtentSource, ...]:
        """The supplied extents as Lane B's derivable form, skipping the box-only ones out loud.

        TWO REFUSALS, NOT ONE. "no extent set was supplied" and "every supplied instance carries
        only a box" send a person to two different places — the first to their selection, the
        second to the adapter that measured it — so `extents()` answers the first before this
        answers the second.
        """
        supplied = self.extents()
        usable: List[EF.SourceExtent] = []
        for artifact in self.artifacts:
            if artifact.measurement.payload_variant.value != "extent_set":
                continue
            found, skipped = EF.source_extents(artifact.identity.artifact_id,
                                               artifact.measurement.payload)
            usable.extend(found)
            for ref in skipped:
                self.dropped.append(DroppedParameter(
                    name=str(ref), reason=("a box-only instance has no mask to derive from, and "
                                           "was not traced")))
        if not usable:
            _refuse(RefusalCode.MISSING_EXTENT_INPUTS, OrganFamily.EXTENT,
                    f"{self.form_key} needs a mask and every one of the "
                    f"{sum(len(s.members) for s in supplied)} supplied instances carries only a "
                    f"box. A boundary of a rectangle is a rectangle.",
                    missing=["mask_rle"],
                    remedy="supply an extent set measured on a mask basis")
        return tuple(usable)


#: Which parameters each form declares. An undeclared key is dropped and recorded — the discipline
#: `resolver.resolve` applies to a planner's proposal, applied here to a person's form.
DECLARED: Mapping[str, Tuple[str, ...]] = {
    "extent.boundary_rings": (),
    "extent.hole_set": (),
    "extent.fragment_set": ("measure_separation",),
    "extent.fused_hypothesis": ("groupings",),
    "extent.visible_inferred_partition": ("of", "parts", "conditioned_on"),
    "extent.hierarchy": ("links",),
    "extent.density_field": ("members", "field_shape", "bandwidth", "kernel"),
    "extent.hypothesis_set": ("question", "readings", "weights_are_probabilities"),
    "topology.containment_tree": (),
    "topology.adjacency_graph": ("max_nodes",),
    "topology.transition": (),
    "topology.uncertain_relation_set": ("hypothesis",),
}


def _ground(raw: Mapping[str, Any]) -> GR.GroundEvidence:
    kind = GroundKind(str(raw.get("kind") or GroundKind.HUMAN_ASSERTION.value))
    strength = raw.get("strength")
    return GR.GroundEvidence(
        kind=kind, detail=str(raw.get("detail") or "supplied by a person"),
        attributed_to=str(raw.get("attributed_to") or GR.HUMAN),
        strength=None if strength is None else float(strength))


def _boundary_rings(ctx: Context):
    return EF.boundary_rings(ctx.source_extents(), source_image_digest=ctx.source_image_digest)


def _hole_set(ctx: Context):
    return EF.hole_set(ctx.source_extents(), source_image_digest=ctx.source_image_digest)


def _fragment_set(ctx: Context):
    return EF.fragment_set(ctx.source_extents(), source_image_digest=ctx.source_image_digest,
                           measure_separation=bool(ctx.take("measure_separation", True)))


def _fused_hypothesis(ctx: Context):
    proposals = [
        FUS.ProposedFusion(
            proposal_id=str(raw.get("id") or f"proposal_{i + 1}"),
            member_keys=tuple(str(k) for k in raw.get("members") or ()),
            evidence=tuple(_ground(g) for g in raw.get("grounds") or ()),
            asserts_hidden_extent=bool(raw.get("asserts_hidden_extent")),
            weight=raw.get("weight"))
        for i, raw in enumerate(ctx.take("groupings") or ())]
    return FUS.produce_fused_hypothesis(proposals, sources=ctx.extents())


def _partition(ctx: Context):
    parts = [PART.SuppliedPart(part=PartitionPart(str(raw.get("part"))),
                               mask_rle=raw.get("mask_rle"), coverage=raw.get("coverage"))
             for raw in ctx.take("parts") or ()]
    of_key = str(ctx.take("of") or "")
    if not of_key:
        _refuse(RefusalCode.MISSING_EXTENT_INPUTS, OrganFamily.EXTENT,
                "a partition names the extent it partitions, and none was named.",
                missing=["of"], remedy="choose the instance this partition is of")
    return PART.produce_visible_inferred_partition(
        of_key, parts, sources=ctx.extents(), conditioned_on=ctx.take("conditioned_on"))


def _hierarchy(ctx: Context):
    links = [HIER.ProposedLink(
        child_key=str(raw.get("child")),
        parent_key=(str(raw["parent"]) if raw.get("parent") else None),
        kind=HIER.LinkKind(str(raw.get("kind") or HIER.LinkKind.GEOMETRIC.value)),
        asserted_by=(_ground(raw["asserted_by"]) if raw.get("asserted_by") else None))
        for raw in ctx.take("links") or ()]
    return HIER.produce_extent_hierarchy(links, sources=ctx.extents())


def _density_field(ctx: Context):
    sources = ctx.extents()
    members = [str(k) for k in ctx.take("members") or ()]
    if not members:
        members = [key for source in sources for key in source.keys()]
    shape = ctx.take("field_shape") or [16, 16]
    bandwidth = ctx.take("bandwidth")
    kernel = (DEN.Kernel(str(ctx.take("kernel") or DEN.GAUSSIAN), float(bandwidth))
              if bandwidth is not None else DEN.NO_SMOOTHING)
    return DEN.produce_density_field(members, sources=sources,
                                    field_shape=[int(shape[0]), int(shape[1])], kernel=kernel)


def _hypothesis_set(ctx: Context):
    readings = [ALT.Reading(
        reading_id=str(raw.get("id") or f"reading_{i + 1}"),
        weight=float(raw.get("weight") or 0.0),
        member_keys=tuple(str(k) for k in raw.get("members") or ()),
        artifact_id=raw.get("artifact_id"),
        evidence=tuple(_ground(g) for g in raw.get("grounds") or ()),
        label=str(raw.get("label") or ""))
        for i, raw in enumerate(ctx.take("readings") or ())]
    return ALT.produce_hypothesis_set(
        str(ctx.take("question") or "which reading does this picture support?"), readings,
        sources=ctx.extents(),
        weights_are_probabilities=bool(ctx.take("weights_are_probabilities")))


def _containment_tree(ctx: Context):
    return TF.produce_containment_tree(list(ctx.relations()))


def _adjacency_graph(ctx: Context):
    return TF.produce_adjacency_graph(list(ctx.relations()))


def _transition(ctx: Context):
    found = ctx.relations()
    if len(found) < 2:
        _refuse(RefusalCode.MISSING_EXTENT_INPUTS, OrganFamily.TOPOLOGY,
                "a transition is a statement about two revisions and one relation set was "
                "supplied. A change nobody can see the start of is not a finding.",
                missing=["a second topology.pair_relation set"],
                remedy="measure the same pair again after the geometry changed")
    return TF.produce_transition(found[0], found[1])


def _uncertain_relations(ctx: Context):
    hypothesis = ctx.take("hypothesis")
    if hypothesis is None:
        _refuse(RefusalCode.MISSING_EXTENT_INPUTS, OrganFamily.TOPOLOGY,
                "a conditional relation set is conditioned on a reading of the extents, and no "
                "hypothesis set was supplied.",
                missing=["extent.hypothesis_set"],
                remedy="derive an extent.hypothesis_set first and supply it here")
    return TF.produce_uncertain_relations(list(ctx.relations()),
                                          ("art_hypotheses", hypothesis))


PRODUCERS: Mapping[str, Callable[[Context], Any]] = {
    "extent.boundary_rings": _boundary_rings,
    "extent.hole_set": _hole_set,
    "extent.fragment_set": _fragment_set,
    "extent.fused_hypothesis": _fused_hypothesis,
    "extent.visible_inferred_partition": _partition,
    "extent.hierarchy": _hierarchy,
    "extent.density_field": _density_field,
    "extent.hypothesis_set": _hypothesis_set,
    "topology.containment_tree": _containment_tree,
    "topology.adjacency_graph": _adjacency_graph,
    "topology.transition": _transition,
    "topology.uncertain_relation_set": _uncertain_relations,
}


def derivable_forms() -> Tuple[str, ...]:
    """Every form this deployment can compute directly, whether or not it may be written."""
    return tuple(sorted(PRODUCERS))


def derive(form_key: str, *, session_id: str, artifacts: Sequence[PerceptualArtifact],
           parameters: Optional[Mapping[str, Any]] = None, source_image_digest: str,
           derivation_id: str, now: str) -> LabDerivation:
    """Compute one form from recorded artifacts and a person's decisions.

    RAISES `DerivationRefused` FOR AN INPUT THAT DOES NOT RESOLVE and returns a record for
    everything else — including a form that is deferred, and including a form whose producer left
    every proposal out. The distinction is the same one the laboratory makes everywhere: a refusal
    is what it says to a person about their request, and an empty answer is a measurement.
    """
    if form_key not in PRODUCERS:
        _refuse(RefusalCode.UNSUPPORTED_FORM, OrganFamily.EXTENT,
                f"{form_key!r} is not a form this deployment computes. The twelve are "
                f"{list(derivable_forms())}.",
                missing=[form_key],
                remedy="choose a form with a code producer, or measure it with an operation")
    definition = D.form(form_key)
    declared = set(DECLARED.get(form_key, ()))
    supplied = dict(parameters or {})
    dropped = [DroppedParameter(name=name,
                                reason=f"{form_key} does not declare it; declared: "
                                       f"{sorted(declared) or 'none'}")
               for name in sorted(set(supplied) - declared)]
    kept = {k: v for k, v in supplied.items() if k in declared}

    ctx = Context(form_key=form_key, artifacts=tuple(artifacts), parameters=kept,
                  source_image_digest=source_image_digest, dropped=list(dropped))
    normalized = _normalize(PRODUCERS[form_key](ctx), form_key)
    availability = PR.availability(form_key)
    code = [p for p in availability.producers if p.kind is PR.CODE]
    payload = normalized["payload"]
    return LabDerivation(
        derivation_id=derivation_id, session_id=session_id, form=form_key,
        organ=ORGAN_OF[definition.organ],
        payload_variant=(getattr(payload, "variant", None) if payload is not None else None),
        payload=(payload.model_dump(mode="json") if payload is not None else None),
        producible=normalized["producible"],
        writable_as_artifact=availability.writable_as_artifact,
        ceiling=normalized["ceiling"], basis=normalized["basis"],
        partition=normalized["partition"],
        producer=(code[0].key if code else PR.CODE),
        producer_kind=PR.CODE,
        producer_revision=(code[0].revision if code else None),
        source_image_digest=source_image_digest,
        input_artifact_ids=[a.identity.artifact_id for a in artifacts],
        parameters=kept, dropped_parameters=ctx.dropped,
        refusals=normalized["refusals"],
        omitted=normalized["omitted"],
        measurements=normalized["measurements"],
        created_at=now)


def _normalize(production: Any, form_key: str) -> Dict[str, Any]:
    """One view over the two producer result shapes this laboratory now has.

    Lane B's exact substrates return `Derived` — a payload, a receipt and the measurements the
    payload has no field for. Lanes D and G return `FormProduction` — a payload, a producibility
    verdict, a ceiling and a list of omissions. Neither is wrong and neither is a superset, so
    this reads whichever it was handed rather than making one lane rewrite its return type to
    suit a runtime that arrived afterwards.

    WHAT LANE B DOES NOT CARRY AND IS SUPPLIED HERE. `Derived` has no producibility verdict,
    because at the time nothing asked it that; the answer is Lane A's `check_form_producible`,
    which is the same gate Lane D and Lane G call. And it tracks no INPUT statuses, so its
    ceiling is computed from the record-local caps only — an exact derivation of a mask is capped
    at `measured` by the basis and the partition alike, which is the answer either way here, and
    the difference is recorded rather than hidden.
    """
    if hasattr(production, "producible"):
        return {
            "payload": production.payload,
            "producible": production.producible,
            "ceiling": production.ceiling,
            "basis": production.basis,
            "partition": None,
            "refusals": list(production.refusals),
            "omitted": [{"what": o.what, "reason": o.reason, "detail": o.detail}
                        for o in production.omitted],
            "measurements": {},
        }
    provenance = production.provenance
    deferral = D.check_form_producible(form_key)
    omitted = [{"what": str(ref), "reason": "part_not_supplied",
                "detail": "a box-only instance has no mask to derive from, and was not traced"}
               for ref in production.skipped_without_mask]
    ceiling = EpistemicStatus(D.derived_ceiling(
        form_key, basis=provenance.epistemic_basis.value,
        partition=provenance.partition.value, input_statuses=[]))
    return {
        "payload": production.payload,
        "producible": deferral is None,
        "ceiling": ceiling,
        "basis": provenance.epistemic_basis,
        "partition": provenance.partition.value,
        "refusals": [deferral] if deferral is not None else [],
        "omitted": omitted,
        "measurements": dict(production.measurements),
    }


__all__ = ["Context", "DECLARED", "DerivationRefused", "DroppedParameter", "LabDerivation",
           "PRODUCERS", "RECORD_KIND", "derivable_forms", "derive"]
