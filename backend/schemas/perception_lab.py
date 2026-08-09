"""
PERCEPTUAL-ORGANS-002 Lane A — the Perception Lab records, in Python.

The canonical vocabulary is `contracts/perception-lab.v1.json`. This module is its FIRST
ENFORCEMENT, not its second definition: every closed set below is checked against that file at
import, and a set edited in one place and not the other fails before any caller runs.

FIVE THINGS THIS FILE EXISTS TO KEEP APART, and each is a nested model rather than a field prefix,
because a prefix convention is broken by one careless field while a nested model is broken only on
purpose, in a diff a reviewer can see:

    identity        which artifact this is, and what it continues
    measurement     the number, and what kind of knowing it is
    projection      how it is drawn — a colour, an opacity, a z-order, and NO geometry
    interpretation  the label, which is a reading and can never be a measurement
    lifecycle       proposed | edited | kept | rejected | promoted — a curation state

A human verdict is the sixth thing and it is NOT here at all. `LabReview` is a separate record
keyed by artifact id, and the artifact does not even carry a list of review ids — because a
`reviews` field on an artifact is exactly how `correct` starts being read as a property of the
measurement. `correct` is a person's judgement of a claim; `measured` is the claim's species;
`kept` is what the lab decided to hold on to. Three axes, three closed sets, no shared member.

WHY `extra="forbid"` EVERYWHERE, when `Region` and `Mark` deliberately allow extras. Those two are
long-lived production documents whose producers keep adding attributes, and a strict model there
would silently delete fields on the next save. These are LABORATORY records whose whole purpose is
to be unambiguous across three runtimes. An undeclared key here is either a typo or a smuggled
claim, and both should stop at the door.

WHAT IS REUSED RATHER THAN REDECIDED:

    EpistemicStatus            imported from `backend.services.epistemics`, not redeclared
    the mask/box ceilings      `epistemics.SUBSTRATE_CEILING`, asserted equal to the contract
    relation kinds             the strings `nestedness_organ`, `adjacency_organ` and
                               `occlusion_organ` already emit
    Region identity            referenced as `region_id` + `geometry_rev`, never copied

PURE. No database, no network, no model, no clock it was not handed. Timestamps are ISO-8601
STRINGS rather than `datetime`, so the same characters cross into JavaScript and back.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Mapping, Optional, Union

from pydantic import (BaseModel, ConfigDict, Field, field_validator, model_validator)

from backend.services.epistemics import EpistemicStatus, SUBSTRATE_CEILING
from backend.services.perception_lab.contracts import (ContractError, closed_set, lab_contract,
                                                       operation_index, organ_index)

SCHEMA_VERSION = "perception-lab.v1"


# ── the closed sets, declared here and checked against the contract ──────────
#
# Declared as real `Enum`s rather than built from the JSON at import, because an enum you can grep
# for, jump to, and read in a traceback is worth more than one saved line of parsing. The price of
# writing them twice is drift, and `_assert_parity` below is what is paid instead: it runs at
# import and raises, so a contract edited without this file fails at the first import rather than
# in whichever validator happened to touch the changed member.


class OrganFamily(str, Enum):
    """The eight perceptual questions. Six are registered and disabled."""
    EXTENT = "extent"
    TOPOLOGY = "topology"
    COLOUR = "colour"
    ILLUMINATION = "illumination"
    SURFACE_PATTERN = "surface_pattern"
    ORIENTATION_FLOW = "orientation_flow"
    DEPTH = "depth"
    SURFACE_FORM = "surface_form"


class SessionMode(str, Enum):
    ISOLATION = "isolation"   # exactly one organ; the lock that makes a judgement about it mean something
    CHAIN = "chain"           # an explicit, inspectable crossing with its own stages


class PlannerIdentity(str, Enum):
    DIRECT = "direct"   # UI controls became one typed command
    RULES = "rules"     # deterministic phrases, offline-testable
    MODEL = "model"     # structured output, behind the identical resolver


class ExecutionIdentity(str, Enum):
    LIVE = "LIVE"        # the only identity permitted to invoke an adapter
    REPLAY = "REPLAY"    # a prior run, re-shown. No callable.
    FIXTURE = "FIXTURE"  # committed data. No callable.


class RunOutcome(str, Enum):
    """Six endings, and the ones that look redundant are the deliverable.

        ready        it ran and produced something
        empty        it ran, looked, and there was nothing of that kind      → look elsewhere
        unavailable  the adapter exists and is not running here             → try elsewhere
        refused      a law said no                                          → satisfy it, or ask differently
        partial      some stages produced, some did not                     → read the stage list
        failed       something raised; no claim is made at all              → fix it
    """
    READY = "ready"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"
    PARTIAL = "partial"
    FAILED = "failed"


class StageState(str, Enum):
    QUEUED = "queued"
    STARTED = "started"
    COMPLETED = "completed"
    EMPTY = "empty"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    FAILED = "failed"


class LifecycleState(str, Enum):
    """What the LAB decided to do with an artifact. Not what it is, and not what a person thought."""
    PROPOSED = "proposed"
    EDITED = "edited"
    KEPT = "kept"
    REJECTED = "rejected"
    PROMOTED = "promoted"   # and ONLY Lane F's explicit human act may set this


class ReviewVerdict(str, Enum):
    """What a PERSON thought. `correct` is not `measured` and never becomes it."""
    CORRECT = "correct"
    PARTIAL = "partial"
    WRONG = "wrong"
    UNCLEAR = "unclear"


class EpistemicBasis(str, Enum):
    """What the claim was computed FROM. Its ceiling is `BASIS_CEILINGS`, below."""
    MASK = "mask"                    # per-pixel on a shared raster
    BOX = "box"                      # bounding boxes; a systematic over-estimate
    DEPTH_ARTIFACT = "depth_artifact"  # an ordering statistic over a SUPPLIED depth field
    MANUAL = "manual"                # a person pointed at it
    DECLARED = "declared"            # an imported region asserting its own geometry


class ArtifactKind(str, Enum):
    EXTENT_SET = "extent_set"
    TOPOLOGY_RELATION_SET = "topology_relation_set"
    NEGATIVE_SPACE_FIELD = "negative_space_field"
    REFUSAL = "refusal"
    DEPTH_FIELD = "depth_field"   # declarable and suppliable; producible by nothing in this phase


class IdentityScope(str, Enum):
    SESSION = "session"      # minted by the lab, meaningful only inside it
    CANONICAL = "canonical"  # a Region that Semant already holds


class ProducerKind(str, Enum):
    ADAPTER = "adapter"
    HUMAN = "human"
    FIXTURE = "fixture"
    REPLAY = "replay"


class CapabilityState(str, Enum):
    AVAILABLE = "available"
    DEFERRED = "deferred"
    UNAVAILABLE = "unavailable"
    UNKNOWN_UNTIL_RUNTIME = "unknown_until_runtime"


class CoordinateSystem(str, Enum):
    NORMALIZED_XY_TOPLEFT = "normalized_xy_topleft"  # what `Region` carries
    PIXEL_XY_TOPLEFT = "pixel_xy_topleft"
    MASK_RLE_HW = "mask_rle_hw"                      # COCO RLE, `{"size": [h, w], ...}`


class LabelSource(str, Enum):
    ADAPTER = "adapter"
    PROMPT = "prompt"
    HUMAN = "human"
    CANONICAL = "canonical"
    NONE = "none"


class RefusalCode(str, Enum):
    """Nine, and not one of them means 'nothing was found'."""
    MISSING_EXTENT_INPUTS = "missing_extent_inputs"
    MISSING_DEPTH_ARTIFACT = "missing_depth_artifact"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    INVALID_PARAMETERS = "invalid_parameters"
    ORGAN_LOCKED = "organ_locked"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    UNKNOWN_REFERENCE = "unknown_reference"
    REPLAY_CANNOT_RECOMPUTE = "replay_cannot_recompute"
    SOURCE_MUTATED = "source_mutated"


class ProjectionKind(str, Enum):
    NONE = "none"
    MASK_FILL = "mask_fill"
    MASK_OUTLINE = "mask_outline"
    BOX_OUTLINE = "box_outline"
    POINT_MARKERS = "point_markers"
    PATH_OVERLAY = "path_overlay"
    CONTACT_BAND = "contact_band"
    INTERSECTION_AREA = "intersection_area"
    ENDPOINT_PAIR = "endpoint_pair"
    RELATION_GRAPH = "relation_graph"
    SCALAR_WASH = "scalar_wash"
    VECTOR_FIELD = "vector_field"
    SWATCH = "swatch"
    CONTACT_SHEET = "contact_sheet"
    BEFORE_AFTER = "before_after"
    AB_OVERLAY = "ab_overlay"
    DIFFERENCE_OVERLAY = "difference_overlay"


class ManualToolKind(str, Enum):
    """The forms a person may use to author or correct. Declared for both enabled organs; a
    deferred organ declares none, because a tool with nothing behind it is a dead control."""
    MASK_BRUSH = "mask_brush"
    POLYGON = "polygon"
    FOREGROUND_BACKGROUND_POINTS = "foreground_background_points"
    REFINEMENT_BOX = "refinement_box"
    REGION_PICKER = "region_picker"
    PAIR_PICKER = "pair_picker"
    REGION_SET_PICKER = "region_set_picker"
    ENDPOINT_CORRECT = "endpoint_correct"
    RELATION_REJECT = "relation_reject"


class RelationKind(str, Enum):
    """The strings the existing organs already emit. Reused verbatim, not renamed."""
    NESTED_WITHIN = "nested_within"   # nestedness_organ.RELATION_NESTED_WITHIN
    CONTAINS = "contains"             # the same relation read from the other endpoint
    MEETS = "meets"                   # adjacency_organ.RELATION_MEETS
    OVERLAPS = "overlaps"
    DISJOINT = "disjoint"
    IN_FRONT_OF = "in_front_of"       # occlusion_organ.RELATION_IN_FRONT_OF
    COPLANAR = "coplanar"             # occlusion_organ.RELATION_COPLANAR


#: What kind of knowing each basis can support. `mask` and `box` are NOT re-decided here — they are
#: `epistemics.SUBSTRATE_CEILING`, and `_assert_parity` fails if this file, the JSON contract and
#: that dict ever stop agreeing. The other three are lab-local and are ruled on in the contract.
BASIS_CEILINGS: Dict[EpistemicBasis, EpistemicStatus] = {
    EpistemicBasis.MASK: EpistemicStatus.MEASURED,
    EpistemicBasis.BOX: EpistemicStatus.INTERPRETIVE,
    EpistemicBasis.DEPTH_ARTIFACT: EpistemicStatus.MEASURED,
    EpistemicBasis.MANUAL: EpistemicStatus.VISIBLE,
    EpistemicBasis.DECLARED: EpistemicStatus.UNCERTAIN,
}

#: A measurement is obtained by looking at THIS image. `sourced` is walled out — see
#: `epistemics.WALLED_STATUSES` — because nothing in this laboratory cites anything outside it.
MEASUREMENT_STATUSES = frozenset({EpistemicStatus.MEASURED, EpistemicStatus.VISIBLE,
                                  EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN})

#: A label is a reading. It may abstain (`uncertain`); it may not become a finding.
INTERPRETATION_STATUSES = frozenset({EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN})

#: The only keys a projection may carry. NO geometry key is in here, and that is the whole point:
#: a projection able to hold a `mask_rle` is a projection able to replace the evidence it depicts.
PROJECTION_HINT_KEYS = frozenset(closed_set("projection_hint_keys"))

#: The organ families this phase enables, read from the contract rather than typed again.
ENABLED_ORGAN_FAMILIES = frozenset(closed_set("enabled_organ_families"))


def _assert_parity() -> None:
    """Every enum above equals its closed set in the contract, at import. Drift stops here."""
    pairs = [
        ("organ_families", OrganFamily), ("session_modes", SessionMode),
        ("planner_identities", PlannerIdentity), ("execution_identities", ExecutionIdentity),
        ("run_outcomes", RunOutcome), ("stage_states", StageState),
        ("lifecycle_states", LifecycleState), ("review_verdicts", ReviewVerdict),
        ("epistemic_bases", EpistemicBasis), ("artifact_kinds", ArtifactKind),
        ("identity_scopes", IdentityScope), ("producer_kinds", ProducerKind),
        ("capability_states", CapabilityState), ("coordinate_systems", CoordinateSystem),
        ("label_sources", LabelSource), ("refusal_codes", RefusalCode),
        ("projection_kinds", ProjectionKind), ("relation_kinds", RelationKind),
        ("manual_tool_kinds", ManualToolKind),
    ]
    for name, enum_cls in pairs:
        declared = closed_set(name)
        here = tuple(m.value for m in enum_cls)
        if declared != here:
            raise ContractError(
                f"closed set {name!r} in contracts/perception-lab.v1.json is {declared} but "
                f"{enum_cls.__name__} in backend/schemas/perception_lab.py is {here}. One law, "
                f"three runtimes — move both or neither.")
    if closed_set("epistemic_statuses") != tuple(m.value for m in EpistemicStatus):
        raise ContractError(
            "the contract's `epistemic_statuses` no longer equals "
            "`backend.services.epistemics.EpistemicStatus`. The lab does not own that vocabulary.")
    for basis, ceiling in SUBSTRATE_CEILING.items():
        declared = lab_contract()["epistemics"]["basis_ceilings"].get(basis)
        if declared != ceiling.value:
            raise ContractError(
                f"the contract gives basis {basis!r} a ceiling of {declared!r}; "
                f"`epistemics.SUBSTRATE_CEILING` gives {ceiling.value!r}. The WAVE2.5 ruling is "
                f"not the lab's to soften.")
        if BASIS_CEILINGS[EpistemicBasis(basis)] is not ceiling:
            raise ContractError(f"BASIS_CEILINGS disagrees with SUBSTRATE_CEILING on {basis!r}")
    enabled_here = {f for f, on in organ_index().items() if on}
    if enabled_here != set(ENABLED_ORGAN_FAMILIES):
        raise ContractError(
            f"`enabled_organ_families` says {sorted(ENABLED_ORGAN_FAMILIES)} but the organ "
            f"definitions say {sorted(enabled_here)}. Enabling an organ takes two edits on "
            f"purpose.")


_assert_parity()


# ── small shared shapes ──────────────────────────────────────────────────────

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def _iso8601(value: str) -> str:
    """ISO-8601 with an explicit offset. A timestamp without a zone is a timestamp in an
    unspecified place, and this record travels between three runtimes."""
    if not _ISO.match(value):
        raise ValueError(f"{value!r} is not an ISO-8601 instant with a timezone offset")
    return value


class _Base(BaseModel):
    """Every lab record. Unknown keys stop at the door — see the module docstring."""
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Box(_Base):
    """`normalized_xy_topleft`, the same convention `Region.box` uses."""
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)


class RegionRef(_Base):
    """A canonical Region, cited by identity AND revision.

    `geometry_rev` is required, not optional. A relation that cites `reg_7` without saying which
    revision of `reg_7` cannot be told to have gone stale, and a stale relation that cannot be
    detected is worse than no relation at all.
    """
    region_id: str = Field(min_length=1)
    geometry_rev: int = Field(ge=0)
    scope: IdentityScope = IdentityScope.CANONICAL


class InputRef(_Base):
    """One thing an operation consumed, in the role it was consumed as.

    Exactly one of `artifact_id` / `region_id`. A ref that named both would let a step claim two
    provenances for one input, and a ref that named neither is the invented identity this contract
    exists to make unsayable.
    """
    role: str = Field(min_length=1)
    scope: IdentityScope
    artifact_id: Optional[str] = None
    region_id: Optional[str] = None
    geometry_rev: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _exactly_one_identity(self) -> "InputRef":
        named = [bool(self.artifact_id), bool(self.region_id)]
        if sum(named) != 1:
            raise ValueError("an input ref names exactly one of artifact_id / region_id")
        if self.region_id and self.geometry_rev is None:
            raise ValueError("a region ref without geometry_rev is not a reference")
        return self


class DataRef(_Base):
    """An immutable pointer to a measurement too large to inline — a distance field, a raster.

    `digest` is mandatory. A pointer without one is a pointer to whatever is there now.
    """
    uri: str = Field(min_length=1)
    digest: str = Field(min_length=8)
    media_type: str = Field(min_length=1)
    bytes: Optional[int] = Field(default=None, ge=0)


class RefusalRecord(_Base):
    """A typed no. Never an empty result, and never an exception message.

    `missing` is what would satisfy it — the difference between "this failed" and "bring me a
    depth field and ask again".
    """
    code: RefusalCode
    organ: OrganFamily
    operation: Optional[str] = None
    message: str = Field(min_length=1)
    missing: List[str] = Field(default_factory=list)
    remedy: Optional[str] = None
    detail: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("operation")
    @classmethod
    def _operation_is_declared(cls, v: Optional[str]) -> Optional[str]:
        # A refusal may name an UNDECLARED operation — that is what `unsupported_operation` is for —
        # so this deliberately does not fail closed. It is the one place an unknown key is data.
        return v


# ── the source, and the session ──────────────────────────────────────────────


class LabSource(_Base):
    """What is being looked at, and the digest that proves it did not move underneath the run."""
    origin: Literal["upload", "post", "fixture"]
    post_id: Optional[str] = None
    image_digest: str = Field(min_length=8)
    natural_width: int = Field(gt=0)
    natural_height: int = Field(gt=0)

    @model_validator(mode="after")
    def _post_origin_names_a_post(self) -> "LabSource":
        if self.origin == "post" and not self.post_id:
            raise ValueError("origin 'post' must name the post")
        return self


class PromptTurn(_Base):
    """What the person said, and which plan it became. Never what the machine 'understood'."""
    turn_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    at: str
    plan_id: Optional[str] = None

    @field_validator("at")
    @classmethod
    def _ts(cls, v: str) -> str:
        return _iso8601(v)


class LabSession(_Base):
    """One sitting at the laboratory.

    THE FOLLOW-UP LAW LIVES HERE. "that mask" is resolvable only through `active_artifact_id`,
    `active_region_ids` and `selected_artifact_ids`. There is deliberately no field in which a
    planner could record what it thinks the person meant, because a remembered intention is
    indistinguishable from an invented identity the moment it is wrong.
    """
    session_id: str = Field(min_length=1)
    source: LabSource
    selected_organ: OrganFamily
    mode: SessionMode
    active_artifact_id: Optional[str] = None
    active_region_ids: List[str] = Field(default_factory=list)
    selected_artifact_ids: List[str] = Field(default_factory=list)
    prompt_turns: List[PromptTurn] = Field(default_factory=list)
    run_ids: List[str] = Field(default_factory=list)
    review_ids: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

    @field_validator("created_at", "updated_at")
    @classmethod
    def _ts(cls, v: str) -> str:
        return _iso8601(v)

    @field_validator("selected_organ")
    @classmethod
    def _organ_is_enabled(cls, v: OrganFamily) -> OrganFamily:
        if v.value not in ENABLED_ORGAN_FAMILIES:
            raise ValueError(
                f"the {v.value} organ is registered and not enabled in this phase. Selecting it "
                f"would give a person a laboratory with nothing behind the glass.")
        return v


# ── the plan: a proposal, and what the resolver made of it ───────────────────


class ProposedStep(_Base):
    """What a planner asked for.

    THERE IS NO AUTHORIZATION FIELD ON THIS MODEL, and its absence is the mechanism. A planner —
    direct, rules or model — constructs these and nothing else, so "planner output is a proposal,
    never execution authority" is not a rule anyone has to remember: there is no field in which
    the proposal could claim to have been authorized.

    `parameters` is permissive `Dict[str, Any]` ON PURPOSE. A model planner WILL emit keys that do
    not exist; the resolver drops them and RECORDS the drop (`DroppedParameter`). Refusing the
    whole plan on a stray key would hide the smuggling attempt instead of showing it.
    """
    step_id: str = Field(min_length=1)
    organ: OrganFamily
    operation: str = Field(min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    input_refs: List[InputRef] = Field(default_factory=list)
    rationale: Optional[str] = None


class ResolvedStep(_Base):
    """What the resolver authorized. The only thing a runner may execute.

    `authorized_by` is a one-member `Literal`. Not an enum with a future second member, not a
    boolean: the single sayable value is `resolver`, so no other component can construct this
    object claiming to have granted the authority.
    """
    step_id: str = Field(min_length=1)
    organ: OrganFamily
    operation: str = Field(min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    input_refs: List[InputRef] = Field(default_factory=list)
    adapter: Optional[str] = None
    authorized_by: Literal["resolver"]
    prerequisites_checked: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _operation_is_declared_and_belongs_to_its_organ(self) -> "ResolvedStep":
        owner = operation_index().get(self.operation)
        if owner is None:
            raise ValueError(
                f"{self.operation!r} is not a declared operation. There is no fallback registry.")
        if owner != self.organ.value:
            raise ValueError(
                f"{self.operation!r} belongs to the {owner} organ, not {self.organ.value}")
        return self

    @model_validator(mode="after")
    def _parameters_are_declared(self) -> "ResolvedStep":
        # Late import: `definitions` is built on top of these records.
        from backend.services.perception_lab.definitions import operation as _operation
        declared = {p.name for p in _operation(self.operation).parameters}
        extra = sorted(set(self.parameters) - declared)
        if extra:
            raise ValueError(
                f"{self.operation!r} does not declare {extra}. A resolved step carries only "
                f"clamped, declared parameters — undeclared keys are dropped and recorded on the "
                f"plan, never carried into execution.")
        return self


class DroppedParameter(_Base):
    """A key the planner asked for that the operation does not declare. Recorded, not silent."""
    step_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ClampedParameter(_Base):
    """A value the operation declares bounds for, and what it became. Clamping is not refusal."""
    step_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    requested: Any = None
    applied: Any = None
    bound: str = Field(min_length=1)


class LabPlan(_Base):
    """The visible proposal a person confirms before anything runs.

    `planner_fell_back_from` is the truthfulness field. When the model planner is unreachable and
    the rules planner answers, `planner` is `rules` and this says `model`. A rules fallback
    wearing the model's name is the specific dishonesty the phase gate looks for.
    """
    plan_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    planner: PlannerIdentity
    planner_fell_back_from: Optional[PlannerIdentity] = None
    selected_organ: OrganFamily
    mode: SessionMode
    proposed_steps: List[ProposedStep] = Field(default_factory=list)
    resolved_steps: List[ResolvedStep] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    refusals: List[RefusalRecord] = Field(default_factory=list)
    dropped_parameters: List[DroppedParameter] = Field(default_factory=list)
    clamped_parameters: List[ClampedParameter] = Field(default_factory=list)
    requires_confirmation: bool
    created_at: str

    @field_validator("created_at")
    @classmethod
    def _ts(cls, v: str) -> str:
        return _iso8601(v)

    @model_validator(mode="after")
    def _isolation_locks_the_organ(self) -> "LabPlan":
        """In isolation mode NOTHING in the plan leaves the selected organ.

        Both lists, because the failure has two halves. A proposal that crosses is the planner
        trying, and it must be visible as a refusal rather than dropped; a RESOLVED step that
        crosses is the lock having failed, and there is no reading of that which is acceptable.
        """
        if self.mode is not SessionMode.ISOLATION:
            return self
        for step in self.resolved_steps:
            if step.organ is not self.selected_organ:
                raise ValueError(
                    f"isolation mode is locked to {self.selected_organ.value}; resolved step "
                    f"{step.step_id!r} is {step.organ.value}. A prompt may not change organs.")
        for step in self.proposed_steps:
            if step.organ is not self.selected_organ and not any(
                    r.code is RefusalCode.ORGAN_LOCKED for r in self.refusals):
                raise ValueError(
                    f"proposed step {step.step_id!r} leaves the locked organ and the plan carries "
                    f"no organ_locked refusal. A crossing that is neither executed nor refused is "
                    f"a crossing that was quietly dropped.")
        return self

    @model_validator(mode="after")
    def _a_crossing_chain_asks_first(self) -> "LabPlan":
        if self.mode is SessionMode.CHAIN:
            organs = {s.organ for s in self.resolved_steps}
            if len(organs) > 1 and not self.requires_confirmation:
                raise ValueError(
                    "a chain crossing the organ boundary requires confirmation. The UI never "
                    "collapses a chain into one organ's finding.")
        return self

    @model_validator(mode="after")
    def _fallback_is_not_the_thing_it_replaced(self) -> "LabPlan":
        if self.planner_fell_back_from is not None \
                and self.planner_fell_back_from is self.planner:
            raise ValueError("a planner cannot have fallen back from itself")
        return self


# ── the artifact, in six separate blocks ─────────────────────────────────────


class ArtifactIdentity(_Base):
    """Which artifact this is, what produced it, and what it continues.

    Shares NO field name with `ArtifactProjection`. That is asserted by the contract tests rather
    than left to care, because "the red one" becoming a way to refer to an artifact is how a
    display attribute quietly becomes an identity.
    """
    artifact_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    organ_family: OrganFamily
    artifact_kind: ArtifactKind
    operation: str = Field(min_length=1)
    identity_scope: IdentityScope
    identity_refs: List[RegionRef] = Field(default_factory=list)
    input_refs: List[InputRef] = Field(default_factory=list)
    derived_from: List[str] = Field(default_factory=list)


class InstanceNaming(_Base):
    """A name for one instance, carried SEPARATELY from its geometry.

    CONCEPT-SEG-001 already established this: a SAM 3 result is a `measured` mask plus an
    `interpretive` label carried as two descriptors, so a wrong name can be rejected without
    discarding a correct measurement. This is that discipline at instance granularity.
    """
    text: str = Field(min_length=1)
    source: LabelSource
    epistemic_status: EpistemicStatus
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("epistemic_status")
    @classmethod
    def _a_name_is_a_reading(cls, v: EpistemicStatus) -> EpistemicStatus:
        if v not in INTERPRETATION_STATUSES:
            raise ValueError(f"a name may be {sorted(s.value for s in INTERPRETATION_STATUSES)}, "
                             f"never {v.value}")
        return v


class ExtentInstance(_Base):
    """One extent. The mask is the identity; the box and polygons are projections of it."""
    instance_id: str = Field(min_length=1)
    mask_rle: Optional[Dict[str, Any]] = None
    box: Optional[Box] = None
    area: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    naming: Optional[InstanceNaming] = None
    region_id: Optional[str] = None
    geometry_rev: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _some_geometry(self) -> "ExtentInstance":
        if self.mask_rle is None and self.box is None:
            raise ValueError("an extent instance with neither a mask nor a box measures nothing")
        if self.region_id and self.geometry_rev is None:
            raise ValueError("an instance claiming a canonical region must name its geometry_rev")
        return self


class ExtentCorrespondence(_Base):
    left_instance_id: str = Field(min_length=1)
    right_instance_id: str = Field(min_length=1)
    iou: float = Field(ge=0.0, le=1.0)


class ExtentDuplicate(_Base):
    """Two instances in ONE set that may be the same thing. A warning, never a deletion."""
    instance_ids: List[str] = Field(min_length=2)
    iou: float = Field(ge=0.0, le=1.0)


class ExtentComparison(_Base):
    """What `extent.compare` measured between two sets — including what only one of them saw."""
    left_artifact_id: str = Field(min_length=1)
    right_artifact_id: str = Field(min_length=1)
    iou_threshold_used: float = Field(ge=0.0, le=1.0)
    correspondences: List[ExtentCorrespondence] = Field(default_factory=list)
    only_in_left: List[str] = Field(default_factory=list)
    only_in_right: List[str] = Field(default_factory=list)


class ExtentSetPayload(_Base):
    """`searched` has no default because `instances: []` means two different things.

    "I looked for faces and there are none" and "nobody looked" arrive at the same empty list, and
    only the first is a measurement.
    """
    variant: Literal["extent_set"]
    searched: str = Field(min_length=1)
    instances: List[ExtentInstance] = Field(default_factory=list)
    dropped_below_min_area: Optional[int] = Field(default=None, ge=0)
    duplicates: List[ExtentDuplicate] = Field(default_factory=list)
    comparison: Optional[ExtentComparison] = None


class RelationEndpoint(_Base):
    """A relation cites identity and revision. It never carries the mask it measured."""
    artifact_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    scope: IdentityScope
    region_id: Optional[str] = None
    geometry_rev: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _canonical_endpoints_carry_a_revision(self) -> "RelationEndpoint":
        if self.scope is IdentityScope.CANONICAL:
            if not self.region_id or self.geometry_rev is None:
                raise ValueError("a canonical endpoint names its region_id and geometry_rev, so "
                                 "that a later revision can make this relation visibly stale")
        return self


class TopologyRelation(_Base):
    """One measured relation, with the basis it rests on and the numbers behind it."""
    relation_id: str = Field(min_length=1)
    kind: RelationKind
    source: RelationEndpoint
    target: RelationEndpoint
    directed: bool
    basis: EpistemicBasis
    epistemic_status: EpistemicStatus
    measurements: Dict[str, float] = Field(default_factory=dict)
    stale: bool = False

    @model_validator(mode="after")
    def _status_within_the_basis_ceiling(self) -> "TopologyRelation":
        ceiling = BASIS_CEILINGS[self.basis]
        if self.epistemic_status is EpistemicStatus.MEASURED and ceiling is not EpistemicStatus.MEASURED:
            raise ValueError(
                f"a {self.basis.value}-basis relation may not be `measured`; its ceiling is "
                f"{ceiling.value}. This is the WAVE2.5 ruling and the lab does not soften it.")
        if self.epistemic_status is EpistemicStatus.SOURCED:
            raise ValueError("no relation in this laboratory comes from outside the image")
        return self


class TopologyRelationSetPayload(_Base):
    """`pairs_examined` has no default, and that single required integer is the guard.

    `relations: []` with `pairs_examined: 4` is a measurement: four pairs were compared and none
    stood in any of the asked-for relations. `relations: []` with nothing counted is not a
    measurement at all, and this model will not let it validate as one.
    """
    variant: Literal["topology_relation_set"]
    pairs_examined: int = Field(ge=0)
    relations: List[TopologyRelation] = Field(default_factory=list)
    bounded_to: Optional[int] = Field(default=None, ge=2)

    @model_validator(mode="after")
    def _empty_only_when_something_looked(self) -> "TopologyRelationSetPayload":
        if not self.relations and self.pairs_examined == 0:
            raise ValueError(
                "no relations and no pairs examined is not an empty measurement — it is an "
                "absence of measurement, and `run.outcome` has other words for that")
        return self


class NegativeSpaceFieldPayload(_Base):
    """A scalar field. Large, so it lives behind a `DataRef` on the measurement block."""
    variant: Literal["negative_space_field"]
    figure_instance_ids: List[str] = Field(min_length=1)
    max_distance_used: float = Field(ge=0.0, le=1.0)
    field_shape: List[int] = Field(min_length=2, max_length=2)
    statistics: Dict[str, float] = Field(default_factory=dict)

    @field_validator("field_shape")
    @classmethod
    def _positive(cls, v: List[int]) -> List[int]:
        if any(n <= 0 for n in v):
            raise ValueError("a field shape is [height, width], both positive")
        return v


class RefusalPayload(_Base):
    """A refusal IS an artifact. It has provenance, a run, a step, and a place in the ledger —
    because "we did not do this, and here is exactly why" is a result worth reopening."""
    variant: Literal["refusal"]
    refusal: RefusalRecord


ArtifactPayload = Annotated[
    Union[ExtentSetPayload, TopologyRelationSetPayload, NegativeSpaceFieldPayload, RefusalPayload],
    Field(discriminator="variant"),
]


class ArtifactMeasurement(_Base):
    """The number, and what kind of knowing it is. Never the colour it is drawn in.

    Exactly one of `payload` / `data_ref`: a measurement is either small enough to carry or big
    enough to point at, and carrying both would create two truths one of which is stale.
    """
    payload_variant: Literal["extent_set", "topology_relation_set", "negative_space_field",
                             "refusal"]
    payload: Optional[ArtifactPayload] = None
    data_ref: Optional[DataRef] = None
    coordinate_system: CoordinateSystem
    epistemic_status: EpistemicStatus
    epistemic_basis: EpistemicBasis
    basis_detail: Optional[str] = None

    @model_validator(mode="after")
    def _one_carrier_and_it_matches_the_variant(self) -> "ArtifactMeasurement":
        if (self.payload is None) == (self.data_ref is None):
            raise ValueError("a measurement carries exactly one of payload / data_ref")
        if self.payload is not None and self.payload.variant != self.payload_variant:
            raise ValueError(
                f"payload_variant is {self.payload_variant!r} and the payload is "
                f"{self.payload.variant!r}")
        return self

    @model_validator(mode="after")
    def _status_is_an_image_status_within_its_ceiling(self) -> "ArtifactMeasurement":
        if self.epistemic_status not in MEASUREMENT_STATUSES:
            raise ValueError(
                f"a measurement may be {sorted(s.value for s in MEASUREMENT_STATUSES)}; "
                f"{self.epistemic_status.value} is not obtainable by looking at this image")
        ceiling = BASIS_CEILINGS[self.epistemic_basis]
        order = {EpistemicStatus.UNCERTAIN: 0, EpistemicStatus.INTERPRETIVE: 1,
                 EpistemicStatus.VISIBLE: 2, EpistemicStatus.MEASURED: 3}
        if order[self.epistemic_status] > order[ceiling]:
            raise ValueError(
                f"a {self.epistemic_basis.value}-basis measurement may claim at most "
                f"{ceiling.value}, not {self.epistemic_status.value}")
        return self


class ArtifactProjection(_Base):
    """How it is DRAWN. A colour, an opacity, a z-order — and no geometry, ever.

    `hints` is clamped to `PROJECTION_HINT_KEYS`. The mutation test for this puts a `mask_rle` in
    here and expects a failure, because an overlay able to carry its own mask is an overlay that
    can disagree with the measurement it claims to depict, and the person looking at the screen
    would have no way to tell which one they were seeing.
    """
    projection_kind: ProjectionKind
    hints: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("hints")
    @classmethod
    def _no_geometry_in_a_hint(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        extra = sorted(set(v) - PROJECTION_HINT_KEYS)
        if extra:
            raise ValueError(
                f"projection hints may not carry {extra}. A projection is how a measurement is "
                f"shown; anything that could stand in for the measurement belongs in the "
                f"measurement block.")
        return v


class ArtifactInterpretation(_Base):
    """The reading. Never a finding, and never a person's verdict.

    Separate from `ArtifactMeasurement` because they can be wrong independently — a perfect mask
    called "hand" when it is a glove is a correct measurement with a wrong reading, and a schema
    that fused them would force a reviewer to reject both.
    """
    label: Optional[str] = None
    label_source: LabelSource
    epistemic_status: EpistemicStatus
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _a_reading_is_not_a_finding(self) -> "ArtifactInterpretation":
        if self.epistemic_status not in INTERPRETATION_STATUSES:
            raise ValueError(
                f"an interpretation may be "
                f"{sorted(s.value for s in INTERPRETATION_STATUSES)}; {self.epistemic_status.value}"
                f" is a claim about the image signal, which a label is not")
        if self.label is None and self.label_source is not LabelSource.NONE:
            raise ValueError("no label means label_source 'none'")
        return self


class ArtifactLifecycle(_Base):
    """What the lab decided to do with it. Not what it is; not what a person thought of it."""
    status: LifecycleState
    changed_at: str
    changed_by: str = Field(min_length=1)

    @field_validator("changed_at")
    @classmethod
    def _ts(cls, v: str) -> str:
        return _iso8601(v)


class ArtifactProvenance(_Base):
    """The receipt. `duration_ms` is null when unmeasured and never 0 — zero is a real duration."""
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    producer_kind: ProducerKind
    producer: str = Field(min_length=1)
    adapter: Optional[str] = None
    model: Optional[str] = None
    revision: Optional[str] = None
    source_image_digest: str = Field(min_length=8)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    device: Optional[str] = None
    peak_memory_mb: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("started_at", "completed_at")
    @classmethod
    def _ts(cls, v: Optional[str]) -> Optional[str]:
        return _iso8601(v) if v is not None else None

    @model_validator(mode="after")
    def _an_adapter_producer_names_its_adapter(self) -> "ArtifactProvenance":
        if self.producer_kind is ProducerKind.ADAPTER and not self.adapter:
            raise ValueError("an adapter-produced artifact names the adapter that produced it")
        if self.producer_kind is ProducerKind.HUMAN and self.adapter:
            raise ValueError("a hand-drawn artifact has no adapter; naming one would make it "
                             "indistinguishable from a segmented mask in every later report")
        return self


class PerceptualArtifact(_Base):
    """One measurement, in six blocks that cannot be mistaken for each other.

    There is no `review` here, and no `review_ids` either. See the module docstring.
    """
    identity: ArtifactIdentity
    measurement: ArtifactMeasurement
    projection: ArtifactProjection
    interpretation: ArtifactInterpretation
    lifecycle: ArtifactLifecycle
    provenance: ArtifactProvenance

    @model_validator(mode="after")
    def _kind_matches_variant(self) -> "PerceptualArtifact":
        kind = self.identity.artifact_kind
        if kind is ArtifactKind.DEPTH_FIELD:
            # Declarable and suppliable, never produced here. A depth field entering the lab does
            # so as an input someone prepared elsewhere; it does not arrive as a lab measurement.
            raise ValueError(
                "no operation in this phase produces a depth_field. `topology.occlusion` declares "
                "it as an input and refuses `missing_depth_artifact` without one.")
        if kind.value != self.measurement.payload_variant:
            raise ValueError(
                f"artifact_kind {kind.value!r} and payload_variant "
                f"{self.measurement.payload_variant!r} are different things")
        return self

    @model_validator(mode="after")
    def _the_organ_that_made_it_can_make_it(self) -> "PerceptualArtifact":
        """A cross-organ payload does not validate.

        An `extent` artifact holding a `topology_relation_set` is either a bug or an organ
        reporting work it did not do, and there is no third case worth admitting.
        """
        contract = lab_contract()
        organ = next((o for o in contract["organs"]
                      if o["family"] == self.identity.organ_family.value), None)
        if organ is None:                                  # pragma: no cover - enum guarantees it
            raise ValueError(f"unknown organ {self.identity.organ_family.value!r}")
        if not organ["enabled"]:
            raise ValueError(
                f"the {organ['family']} organ is registered and disabled; it cannot have produced "
                f"an artifact")
        produced = organ.get("produces_artifact_kinds") or []
        if self.identity.artifact_kind.value not in produced:
            raise ValueError(
                f"the {organ['family']} organ produces {produced}, not "
                f"{self.identity.artifact_kind.value!r}")
        owner = operation_index().get(self.identity.operation)
        if owner is None:
            raise ValueError(f"{self.identity.operation!r} is not a declared operation")
        if owner != self.identity.organ_family.value:
            raise ValueError(
                f"{self.identity.operation!r} belongs to the {owner} organ, not "
                f"{self.identity.organ_family.value}")
        return self

    @model_validator(mode="after")
    def _identity_and_projection_do_not_overlap(self) -> "PerceptualArtifact":
        shared = set(ArtifactIdentity.model_fields) & set(ArtifactProjection.model_fields)
        if shared:                                          # pragma: no cover - structural guard
            raise ValueError(f"identity and projection share {sorted(shared)}")
        return self


# ── the run ──────────────────────────────────────────────────────────────────


class StageAttempt(_Base):
    """What one step of the machinery did.

    `invoked` is the field the replay law turns on. It is not derived from `adapter` being set —
    a replay stage legitimately NAMES the adapter whose recorded output it is showing, and
    conflating "names an adapter" with "called an adapter" would make the honest record unsayable.
    """
    attempt_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    state: StageState
    adapter: Optional[str] = None
    invoked: bool
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    detail: Optional[str] = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def _ts(cls, v: Optional[str]) -> Optional[str]:
        return _iso8601(v) if v is not None else None


class ReplayProvenance(_Base):
    """Where a REPLAY run's content came from, and the fact that it cannot go and get more.

    `adapter_callable` is `Literal[False]`. Not a default, not a boolean anyone can flip: there is
    no way to write `True` into this field, so "replay has no callable adapter" is not a rule the
    replay code has to obey — it is a sentence about a replay that cannot be typed.
    """
    source_run_id: str = Field(min_length=1)
    recorded_at: str
    adapter_callable: Literal[False]
    reason: Optional[str] = None

    @field_validator("recorded_at")
    @classmethod
    def _ts(cls, v: str) -> str:
        return _iso8601(v)


class LabRun(_Base):
    """One execution, with the identity that says whether anything was actually asked of a model."""
    run_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    execution_identity: ExecutionIdentity
    outcome: RunOutcome
    requested_plan_id: str = Field(min_length=1)
    resolved_plan_id: Optional[str] = None
    artifact_ids: List[str] = Field(default_factory=list)
    stage_attempts: List[StageAttempt] = Field(default_factory=list)
    refusals: List[RefusalRecord] = Field(default_factory=list)
    source_digest_before: str = Field(min_length=8)
    source_digest_after: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)
    replay: Optional[ReplayProvenance] = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def _ts(cls, v: Optional[str]) -> Optional[str]:
        return _iso8601(v) if v is not None else None

    @model_validator(mode="after")
    def _only_live_may_invoke(self) -> "LabRun":
        """The mutation test for this flips one `invoked` on a REPLAY run and expects a failure.

        FIXTURE is here too, and deliberately. A fixture run reads committed data; if it were
        permitted to invoke, "FIXTURE" would become a badge a live call could wear.
        """
        if self.execution_identity is ExecutionIdentity.LIVE:
            return self
        called = [a.attempt_id for a in self.stage_attempts if a.invoked]
        if called:
            raise ValueError(
                f"a {self.execution_identity.value} run invoked {called}. Only LIVE may call an "
                f"adapter; this run has nothing to call.")
        return self

    @model_validator(mode="after")
    def _replay_declares_its_source(self) -> "LabRun":
        if self.execution_identity is ExecutionIdentity.REPLAY and self.replay is None:
            raise ValueError("a REPLAY run names the run it replays, or it is not a replay")
        if self.execution_identity is not ExecutionIdentity.REPLAY and self.replay is not None:
            raise ValueError(
                f"a {self.execution_identity.value} run carries no replay provenance")
        return self

    @model_validator(mode="after")
    def _the_outcome_matches_what_is_in_the_record(self) -> "LabRun":
        """An outcome that the rest of the record does not support does not validate.

        This is the guard against the failure the whole absence vocabulary exists to prevent: a
        refusal reported as an empty result, or an empty result reported as a refusal. Both are
        one careless assignment away, and neither is visible on a screen.
        """
        has_refusal = bool(self.refusals)
        if self.outcome is RunOutcome.REFUSED and not has_refusal:
            raise ValueError("outcome 'refused' carries the typed refusal that caused it")
        if self.outcome is RunOutcome.UNAVAILABLE and not any(
                r.code is RefusalCode.CAPABILITY_UNAVAILABLE for r in self.refusals):
            raise ValueError(
                "outcome 'unavailable' carries a capability_unavailable refusal naming what is "
                "not running — otherwise it is indistinguishable from having found nothing")
        if self.outcome in (RunOutcome.READY, RunOutcome.EMPTY) and has_refusal:
            raise ValueError(
                f"outcome {self.outcome.value!r} with a refusal attached is two answers. Use "
                f"'partial' if some stages produced and some refused.")
        if self.outcome is RunOutcome.READY and not self.artifact_ids:
            raise ValueError("outcome 'ready' produced no artifact")
        if self.outcome is RunOutcome.PARTIAL and not (self.artifact_ids and self.stage_attempts):
            raise ValueError("outcome 'partial' means some of it worked; say which")
        return self

    @model_validator(mode="after")
    def _a_mutated_source_says_so(self) -> "LabRun":
        if self.source_digest_after is not None \
                and self.source_digest_after != self.source_digest_before \
                and not any(r.code is RefusalCode.SOURCE_MUTATED for r in self.refusals):
            raise ValueError(
                "the source digest changed during the run and nothing said so. A measurement of "
                "an image that moved is a measurement of neither image.")
        return self


# ── the human verdict, which is none of the above ────────────────────────────


class ReviewCorrection(_Base):
    """What the person changed. A correction is a record of an edit, not a measurement of one."""
    field: str = Field(min_length=1)
    was: Optional[str] = None
    now: Optional[str] = None
    note: Optional[str] = None


class LabReview(_Base):
    """A person's judgement of an artifact.

    Deliberately carries NO epistemic status and NO lifecycle status. Saying `correct` does not
    make a box-basis containment `measured`, and it does not make the artifact `kept`. Those are
    three different decisions by three different deciders, and this record makes only one of them.
    """
    review_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    verdict: ReviewVerdict
    notes: Optional[str] = None
    corrections: List[ReviewCorrection] = Field(default_factory=list)
    reviewed_at: str

    @field_validator("reviewed_at")
    @classmethod
    def _ts(cls, v: str) -> str:
        return _iso8601(v)


#: Every record type in this contract, by the name the JSON contract uses for it. The parity tests
#: walk this rather than a hand-written list, so a new record with no declared fields fails.
RECORD_MODELS: Mapping[str, type] = {
    "LabSession": LabSession,
    "LabPlan": LabPlan,
    "LabRun": LabRun,
    "PerceptualArtifact": PerceptualArtifact,
    "LabReview": LabReview,
}

#: The six blocks of a `PerceptualArtifact`, by the name the contract's `records` block uses.
ARTIFACT_BLOCK_MODELS: Mapping[str, type] = {
    "identity": ArtifactIdentity,
    "measurement": ArtifactMeasurement,
    "projection": ArtifactProjection,
    "interpretation": ArtifactInterpretation,
    "lifecycle": ArtifactLifecycle,
    "provenance": ArtifactProvenance,
}

__all__ = [
    "SCHEMA_VERSION", "OrganFamily", "SessionMode", "PlannerIdentity", "ExecutionIdentity",
    "RunOutcome", "StageState", "LifecycleState", "ReviewVerdict", "EpistemicStatus",
    "EpistemicBasis", "ArtifactKind", "IdentityScope", "ProducerKind", "CapabilityState",
    "CoordinateSystem", "LabelSource", "RefusalCode", "ProjectionKind", "ManualToolKind",
    "RelationKind",
    "BASIS_CEILINGS", "MEASUREMENT_STATUSES", "INTERPRETATION_STATUSES", "PROJECTION_HINT_KEYS",
    "ENABLED_ORGAN_FAMILIES", "Box", "RegionRef", "InputRef", "DataRef", "RefusalRecord",
    "LabSource", "PromptTurn", "LabSession", "ProposedStep", "ResolvedStep", "DroppedParameter",
    "ClampedParameter", "LabPlan", "ArtifactIdentity", "InstanceNaming", "ExtentInstance",
    "ExtentCorrespondence", "ExtentDuplicate", "ExtentComparison", "ExtentSetPayload",
    "RelationEndpoint", "TopologyRelation", "TopologyRelationSetPayload",
    "NegativeSpaceFieldPayload", "RefusalPayload", "ArtifactMeasurement", "ArtifactProjection",
    "ArtifactInterpretation", "ArtifactLifecycle", "ArtifactProvenance", "PerceptualArtifact",
    "StageAttempt", "ReplayProvenance", "LabRun", "ReviewCorrection", "LabReview",
    "RECORD_MODELS", "ARTIFACT_BLOCK_MODELS",
]
