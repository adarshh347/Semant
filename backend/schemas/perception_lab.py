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
from typing import Annotated, Any, Dict, List, Literal, Mapping, Optional, Tuple, Union

from pydantic import (BaseModel, ConfigDict, Field, field_validator, model_validator)

from backend.services.epistemics import EpistemicStatus, SUBSTRATE_CEILING
from backend.services.perception_lab.contracts import (ContractError, closed_set, form_index,
                                                       lab_contract, legacy_form_index,
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


class PerceptualForm(str, Enum):
    """The nineteen canonical answers — PERCEPTUAL-FORMS-001A.

    NOT the operation list. A form is what was PERCEIVED; an operation is what was ASKED FOR, and
    the two registries have different arities in both directions. Nine of these are `deferred`:
    designed, validated, and unwritable until the phase that means to produce them.
    """
    EXTENT_HARD_MASK = "extent.hard_mask"
    EXTENT_BOUNDARY_RINGS = "extent.boundary_rings"
    EXTENT_HOLE_SET = "extent.hole_set"
    EXTENT_SOFT_FIELD = "extent.soft_field"
    EXTENT_FRAGMENT_SET = "extent.fragment_set"
    EXTENT_FUSED_HYPOTHESIS = "extent.fused_hypothesis"
    EXTENT_VISIBLE_INFERRED_PARTITION = "extent.visible_inferred_partition"
    EXTENT_HIERARCHY = "extent.hierarchy"
    EXTENT_DENSITY_FIELD = "extent.density_field"
    EXTENT_HYPOTHESIS_SET = "extent.hypothesis_set"
    TOPOLOGY_PAIR_RELATION = "topology.pair_relation"
    TOPOLOGY_CONTACT_LOCUS = "topology.contact_locus"
    TOPOLOGY_INTERSECTION_AREA = "topology.intersection_area"
    TOPOLOGY_CLEARANCE_PATH = "topology.clearance_path"
    TOPOLOGY_CONTAINMENT_TREE = "topology.containment_tree"
    TOPOLOGY_ADJACENCY_GRAPH = "topology.adjacency_graph"
    TOPOLOGY_NEGATIVE_SPACE_FIELD = "topology.negative_space_field"
    TOPOLOGY_TRANSITION = "topology.transition"
    TOPOLOGY_UNCERTAIN_RELATION_SET = "topology.uncertain_relation_set"


class FormState(str, Enum):
    ENABLED = "enabled"            # a producer writes it today
    EXPERIMENTAL = "experimental"  # writable, and never `promoted` out of the laboratory
    DEFERRED = "deferred"          # registered, designed, and unwritable


class ProducerClass(str, Enum):
    """What kind of machinery may write a form, in the order this phase moves through them."""
    DIRECT_MEASUREMENT = "direct_measurement"
    EXACT_DERIVATION = "exact_derivation"
    DETERMINISTIC_COMPOSITION = "deterministic_composition"
    MANUAL_AUTHORING = "manual_authoring"
    BOUNDED_STRATEGY = "bounded_strategy"   # declared, and used by nothing in this phase
    IMPORT_DECLARED = "import_declared"


class EpistemicPartition(str, Enum):
    """What KIND OF ACT produced a claim — orthogonal to the basis it was computed from.

    A basis says what a number came FROM. A partition says what was DONE with it. Both cap the
    status, and that is the whole answer to "a hypothesis may cite measurements and may not
    inherit `measured` merely because its inputs were measured".
    """
    VISIBLE_MEASURED = "visible_measured"
    EXACT_DERIVATION = "exact_derivation"
    INTERPRETIVE_GROUPING = "interpretive_grouping"
    INFERRED_COMPLETION = "inferred_completion"
    UNRESOLVED_ALTERNATIVE = "unresolved_alternative"


class RendererMode(str, Enum):
    DIRECT = "direct"     # drawn from the payload as recorded
    DERIVED = "derived"   # computed by the reader, and stamped as such


class ComparisonMethod(str, Enum):
    IOU = "iou"
    BOUNDARY_F1 = "boundary_f1"
    CHAMFER = "chamfer"
    HAUSDORFF = "hausdorff"
    SET_OVERLAP = "set_overlap"
    TREE_EDIT = "tree_edit"
    GRAPH_EDIT = "graph_edit"
    FIELD_L1 = "field_l1"
    FIELD_CORRELATION = "field_correlation"
    RANK_AGREEMENT = "rank_agreement"


class FieldDerivation(str, Enum):
    """How a scalar field's numbers came to exist. `blur_of_binary_mask` is the one that cannot
    be calibrated: it is a picture of an edge's uncertainty, not a probability."""
    DIRECT_PROBABILITY = "direct_probability"
    MODEL_LOGIT = "model_logit"
    DISTANCE_TRANSFORM = "distance_transform"
    BLUR_OF_BINARY_MASK = "blur_of_binary_mask"
    KERNEL_DENSITY = "kernel_density"
    SAMPLE_HISTOGRAM = "sample_histogram"
    MANUAL_PAINT = "manual_paint"


class CalibrationState(str, Enum):
    CALIBRATED = "calibrated"      # names a method AND the reference it was calibrated against
    NOMINAL = "nominal"            # ordered and comparable; not a probability
    UNCALIBRATED = "uncalibrated"  # numbers with no declared meaning beyond their order


class GroundKind(str, Enum):
    """What a hypothesis rests on. Enumerated rather than collapsed into one confidence, because
    `0.94` with no ground is a number about nothing."""
    APPEARANCE_CONTINUITY = "appearance_continuity"
    SHAPE_CONTINUITY = "shape_continuity"
    DEPTH_CONTINUITY = "depth_continuity"
    RELATIVE_POSITION = "relative_position"
    OCCLUSION_HYPOTHESIS = "occlusion_hypothesis"
    FLOW_CONTINUITY = "flow_continuity"
    SCALE_CONSISTENCY = "scale_consistency"
    HUMAN_ASSERTION = "human_assertion"


class RingWinding(str, Enum):
    OUTER = "outer"
    INNER = "inner"


class PartitionPart(str, Enum):
    VISIBLE = "visible"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class TransitionChange(str, Enum):
    APPEARED = "appeared"
    DISAPPEARED = "disappeared"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


class ArtifactKind(str, Enum):
    """One kind per registered form, plus `refusal` and `depth_field`.

    `depth_field` is still declarable and produced by nothing — the same discipline the nine
    `deferred` forms are held to, and for the same reason.
    """
    EXTENT_SET = "extent_set"
    EXTENT_BOUNDARY = "extent_boundary"
    EXTENT_HOLE_SET = "extent_hole_set"
    EXTENT_SOFT_FIELD = "extent_soft_field"
    EXTENT_FRAGMENT_SET = "extent_fragment_set"
    EXTENT_FUSION_HYPOTHESIS = "extent_fusion_hypothesis"
    EXTENT_PARTITION = "extent_partition"
    EXTENT_HIERARCHY = "extent_hierarchy"
    EXTENT_DENSITY_FIELD = "extent_density_field"
    EXTENT_HYPOTHESIS_SET = "extent_hypothesis_set"
    TOPOLOGY_RELATION_SET = "topology_relation_set"
    TOPOLOGY_CONTACT_LOCUS = "topology_contact_locus"
    TOPOLOGY_INTERSECTION = "topology_intersection"
    TOPOLOGY_CLEARANCE_PATH = "topology_clearance_path"
    TOPOLOGY_CONTAINMENT_TREE = "topology_containment_tree"
    TOPOLOGY_ADJACENCY_GRAPH = "topology_adjacency_graph"
    NEGATIVE_SPACE_FIELD = "negative_space_field"
    TOPOLOGY_TRANSITION = "topology_transition"
    TOPOLOGY_UNCERTAIN_RELATIONS = "topology_uncertain_relations"
    REFUSAL = "refusal"
    DEPTH_FIELD = "depth_field"   # declarable and suppliable; producible by nothing in this phase


class PayloadVariant(str, Enum):
    """The same nineteen, plus `refusal`. `depth_field` is deliberately absent: a kind that can be
    referenced is not a kind that can be built."""
    EXTENT_SET = "extent_set"
    EXTENT_BOUNDARY = "extent_boundary"
    EXTENT_HOLE_SET = "extent_hole_set"
    EXTENT_SOFT_FIELD = "extent_soft_field"
    EXTENT_FRAGMENT_SET = "extent_fragment_set"
    EXTENT_FUSION_HYPOTHESIS = "extent_fusion_hypothesis"
    EXTENT_PARTITION = "extent_partition"
    EXTENT_HIERARCHY = "extent_hierarchy"
    EXTENT_DENSITY_FIELD = "extent_density_field"
    EXTENT_HYPOTHESIS_SET = "extent_hypothesis_set"
    TOPOLOGY_RELATION_SET = "topology_relation_set"
    TOPOLOGY_CONTACT_LOCUS = "topology_contact_locus"
    TOPOLOGY_INTERSECTION = "topology_intersection"
    TOPOLOGY_CLEARANCE_PATH = "topology_clearance_path"
    TOPOLOGY_CONTAINMENT_TREE = "topology_containment_tree"
    TOPOLOGY_ADJACENCY_GRAPH = "topology_adjacency_graph"
    NEGATIVE_SPACE_FIELD = "negative_space_field"
    TOPOLOGY_TRANSITION = "topology_transition"
    TOPOLOGY_UNCERTAIN_RELATIONS = "topology_uncertain_relations"
    REFUSAL = "refusal"


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
    """Eleven, and not one of them means 'nothing was found'."""
    MISSING_EXTENT_INPUTS = "missing_extent_inputs"
    MISSING_DEPTH_ARTIFACT = "missing_depth_artifact"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    INVALID_PARAMETERS = "invalid_parameters"
    ORGAN_LOCKED = "organ_locked"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    UNKNOWN_REFERENCE = "unknown_reference"
    REPLAY_CANNOT_RECOMPUTE = "replay_cannot_recompute"
    SOURCE_MUTATED = "source_mutated"
    UNSUPPORTED_FORM = "unsupported_form"          # the artifact resolved; it is the wrong ANSWER
    FORM_NOT_PRODUCIBLE = "form_not_producible"    # the form is real, declared, and deferred


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
    RING_OUTLINE = "ring_outline"
    HOLE_FILL = "hole_fill"
    FRAGMENT_CLUSTER = "fragment_cluster"
    PARTITION_TRICOLOR = "partition_tricolor"
    HIERARCHY_TREE = "hierarchy_tree"
    DENSITY_CONTOURS = "density_contours"
    HYPOTHESIS_STACK = "hypothesis_stack"
    TRANSITION_DIFF = "transition_diff"


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
    RING_EDIT = "ring_edit"
    HOLE_MARK = "hole_mark"
    FRAGMENT_GROUP = "fragment_group"
    FRAGMENT_SPLIT = "fragment_split"
    PARTITION_PAINT = "partition_paint"
    HIERARCHY_LINK = "hierarchy_link"
    HYPOTHESIS_CHOOSE = "hypothesis_choose"


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

#: What kind of ACT each partition is, and therefore how strong a claim it can support.
#: Independent of `BASIS_CEILINGS` above, and applied on top of it: a mask-basis claim that was
#: nevertheless an inference about pixels nobody saw is capped at `uncertain`, not at `measured`.
#: This is the structural form of "a hypothesis may cite measurements and may not inherit their
#: status".
PARTITION_CEILINGS: Dict[EpistemicPartition, EpistemicStatus] = {
    EpistemicPartition.VISIBLE_MEASURED: EpistemicStatus.MEASURED,
    EpistemicPartition.EXACT_DERIVATION: EpistemicStatus.MEASURED,
    EpistemicPartition.INTERPRETIVE_GROUPING: EpistemicStatus.INTERPRETIVE,
    EpistemicPartition.INFERRED_COMPLETION: EpistemicStatus.UNCERTAIN,
    EpistemicPartition.UNRESOLVED_ALTERNATIVE: EpistemicStatus.UNCERTAIN,
}

#: How the four obtainable statuses order. Declared once, because three validators compare them
#: and three private orderings would be three chances to disagree.
STATUS_ORDER: Dict[EpistemicStatus, int] = {
    EpistemicStatus.UNCERTAIN: 0,
    EpistemicStatus.INTERPRETIVE: 1,
    EpistemicStatus.VISIBLE: 2,
    EpistemicStatus.MEASURED: 3,
}

#: The partitions that describe an act of INFERENCE rather than of measurement or derivation.
#: Neither can reach `visible` or `measured`, at any confidence, on any basis.
INFERRING_PARTITIONS = frozenset({EpistemicPartition.INFERRED_COMPLETION,
                                  EpistemicPartition.UNRESOLVED_ALTERNATIVE})

#: The partitions that rest on records already made, and therefore must name what they rest on.
DERIVING_PARTITIONS = frozenset({EpistemicPartition.EXACT_DERIVATION,
                                 EpistemicPartition.INTERPRETIVE_GROUPING})


def _cap(status: EpistemicStatus, ceiling: EpistemicStatus, because: str) -> None:
    """Raise unless `status` is at or below `ceiling`. The one comparison, used everywhere."""
    if status is EpistemicStatus.SOURCED:
        raise ValueError("nothing in this laboratory comes from outside the image it is looking at")
    if STATUS_ORDER[status] > STATUS_ORDER[ceiling]:
        raise ValueError(f"{because}: at most {ceiling.value}, not {status.value}")


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
        ("payload_variants", PayloadVariant),
        ("identity_scopes", IdentityScope), ("producer_kinds", ProducerKind),
        ("capability_states", CapabilityState), ("coordinate_systems", CoordinateSystem),
        ("label_sources", LabelSource), ("refusal_codes", RefusalCode),
        ("projection_kinds", ProjectionKind), ("relation_kinds", RelationKind),
        ("manual_tool_kinds", ManualToolKind),
        # PERCEPTUAL-FORMS-001A
        ("perceptual_forms", PerceptualForm), ("form_states", FormState),
        ("producer_classes", ProducerClass), ("epistemic_partitions", EpistemicPartition),
        ("renderer_modes", RendererMode), ("comparison_methods", ComparisonMethod),
        ("field_derivations", FieldDerivation), ("calibration_states", CalibrationState),
        ("ground_kinds", GroundKind), ("ring_windings", RingWinding),
        ("partition_parts", PartitionPart), ("transition_changes", TransitionChange),
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
    declared_partitions = lab_contract()["form_grammar"]["epistemic_partitions"]["ceilings"]
    for partition, ceiling in PARTITION_CEILINGS.items():
        if declared_partitions.get(partition.value) != ceiling.value:
            raise ContractError(
                f"the contract gives partition {partition.value!r} a ceiling of "
                f"{declared_partitions.get(partition.value)!r}; this file gives {ceiling.value!r}. "
                f"A partition that caps at two different statuses caps at neither.")
    for key, form in form_index().items():
        best_basis = max((BASIS_CEILINGS[EpistemicBasis(b)] for b in form["admissible_bases"]),
                         key=lambda s: STATUS_ORDER[s])
        best_part = max((PARTITION_CEILINGS[EpistemicPartition(p)]
                         for p in form["admissible_partitions"]), key=lambda s: STATUS_ORDER[s])
        weaker = min((best_basis, best_part), key=lambda s: STATUS_ORDER[s])
        if form["epistemic_ceiling"] != weaker.value:
            raise ContractError(
                f"form {key!r} declares a ceiling of {form['epistemic_ceiling']!r}; its strongest "
                f"admissible basis reaches {best_basis.value!r} and its strongest admissible "
                f"partition reaches {best_part.value!r}, so it reaches {weaker.value!r}. A "
                f"declared ceiling above what the form can support is the lie this registry "
                f"exists to make unwritable.")
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


class InstanceRef(_Base):
    """One instance inside one artifact, as a session records having selected it.

    BOTH FIELDS ARE REQUIRED, and that is the whole design. "Never store a bare instance_id" is a
    rule nobody has to remember when there is no arrangement of this record that could hold one:
    an instance id is unique inside its artifact and nowhere else, so `inst_1` on its own names
    every extent set's first mask at once. A flat list of instance ids would be ambiguous in the
    NORMAL case rather than an exotic one, because every set numbers its own from 1.
    """
    artifact_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)

    @property
    def key(self) -> Tuple[str, str]:
        return self.artifact_id, self.instance_id

    def __str__(self) -> str:                      # what a refusal message prints
        return f"{self.artifact_id}#{self.instance_id}"


class RevisionRef(_Base):
    """One instance, pinned to the revision of its geometry — PERCEPTUAL-FORMS-001A.

    THE THIRD DEPTH OF THE ONE REFERENCE TYPE, not a fourth reference record: artifact →
    instance → revision, the same identity all the way down. All three fields are required, for
    the same reason both of `InstanceRef`'s are: a revision number without the instance it
    revises names nothing at all.

    IT EXISTS BECAUSE A TRANSITION IS A STATEMENT ABOUT TWO REVISIONS. `TopologyRelation.stale`
    can say a relation is out of date. Only a pair of pinned references can say what it changed
    FROM — and a change nobody can see the start of is not a finding, it is a rumour.

    IT IS NOT USED WHERE AN `InstanceRef` WOULD DO. Pinning a revision onto a reference that
    merely SELECTS something would freeze the selection to a geometry the person did not choose,
    so a session's selections stay `InstanceRef` and only the records that are about revisions
    reach this far.
    """
    artifact_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    geometry_rev: int = Field(ge=0)

    @property
    def instance(self) -> "InstanceRef":
        """The same reference, one depth shallower."""
        return InstanceRef(artifact_id=self.artifact_id, instance_id=self.instance_id)

    @property
    def key(self) -> Tuple[str, str, int]:
        return self.artifact_id, self.instance_id, self.geometry_rev

    def __str__(self) -> str:
        return f"{self.artifact_id}#{self.instance_id}@{self.geometry_rev}"


class InputRef(_Base):
    """One thing an operation consumed, in the role it was consumed as.

    Exactly one of `artifact_id` / `region_id`. A ref that named both would let a step claim two
    provenances for one input, and a ref that named neither is the invented identity this contract
    exists to make unsayable.

    ONE REFERENCE TYPE, TWO DEPTHS (PERCEPTUAL-ORGANS-002A2). An `extent_set` holds many instances,
    and a person who clicked one mask said something more precise than "that artifact". Before
    `instance_id` existed here, four lanes each reached past the contract in their own way — Extent
    refused every multi-instance refinement, Topology froze a local `instance_id` on its own input
    type, the conductor could not bind "that mask", and the frontend emitted a field this schema
    rejected. Four private answers to one question is exactly how a second identity system starts,
    so the repair is one optional field here rather than a second reference record anywhere.

    THE THREE RULES, and each is a shape rather than a convention:

        `instance_id` beside `artifact_id`   one instance inside that artifact
        `artifact_id` alone                  the WHOLE artifact, meaning what it always meant
        `instance_id` beside `region_id`     REFUSED — a canonical Region is already one shape,
                                             and an instance inside it would be a second geometry
                                             wearing one id

    A bare `instance_id` cannot validate: it fails the exactly-one-identity rule first, because an
    instance id without its container is not a reference to anything.

    BACKWARD COMPATIBLE BY CONSTRUCTION. The field is optional and defaults to None, so every
    record written before it existed reads back unchanged and means what it meant.
    """
    role: str = Field(min_length=1)
    scope: IdentityScope
    artifact_id: Optional[str] = None
    instance_id: Optional[str] = None
    region_id: Optional[str] = None
    geometry_rev: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _exactly_one_identity(self) -> "InputRef":
        named = [bool(self.artifact_id), bool(self.region_id)]
        if sum(named) != 1:
            raise ValueError("an input ref names exactly one of artifact_id / region_id")
        if self.region_id and self.geometry_rev is None:
            raise ValueError("a region ref without geometry_rev is not a reference")
        if self.instance_id and not self.artifact_id:
            raise ValueError(
                "an instance ref names the artifact that holds it. An instance id is unique "
                "inside one artifact and nowhere else, so one recorded alone names nothing")
        return self

    @property
    def names_one_instance(self) -> bool:
        return self.instance_id is not None

    @property
    def reference(self) -> str:
        """What this ref is called in a refusal — the composite when it reaches an instance.

        `art_3#inst_2` and `art_3` are different references and a message that printed the same
        string for both would tell a person to select something they already had selected.
        """
        if self.artifact_id is None:
            return str(self.region_id)
        if self.instance_id is None:
            return self.artifact_id
        return f"{self.artifact_id}#{self.instance_id}"


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
    `active_region_ids`, `selected_artifact_ids` and `selected_instance_refs`. There is
    deliberately no field in which a planner could record what it thinks the person meant, because
    a remembered intention is indistinguishable from an invented identity the moment it is wrong.

    `selected_instance_refs` IS PAIRS, NOT IDS, and that is the whole reason it is a record type.
    A list of bare instance ids would be ambiguous the moment two selected artifacts each held an
    `inst_1` — which is every time, since each extent set numbers its own from 1. It is also why
    an instance ref may not name an artifact this session has not selected: a reference reachable
    from one field and invisible in the other is how a deselection gets disobeyed.
    """
    session_id: str = Field(min_length=1)
    source: LabSource
    selected_organ: OrganFamily
    mode: SessionMode
    active_artifact_id: Optional[str] = None
    active_region_ids: List[str] = Field(default_factory=list)
    selected_artifact_ids: List[str] = Field(default_factory=list)
    selected_instance_refs: List[InstanceRef] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def _an_instance_is_selected_with_its_artifact(self) -> "LabSession":
        """An instance ref whose artifact is not declared here is not a reference.

        Without this, "select A and B, select instance A#2, deselect A, now measure that mask"
        would still resolve A#2 — the person's deselection recorded and disobeyed, through the
        other field that happened to still hold it. `SessionMachine.deselect` maintains the
        invariant; this is where the record refuses to be written any other way.
        """
        declared = set(self.selected_artifact_ids)
        if self.active_artifact_id:
            declared.add(self.active_artifact_id)
        stray = sorted({r.artifact_id for r in self.selected_instance_refs} - declared)
        if stray:
            raise ValueError(
                f"selected instances name {stray}, which this session has neither selected nor "
                f"made active. Selecting an instance selects its artifact; an instance reachable "
                f"from one field and absent from the other is a deselection that did not take")
        return self

    @property
    def instance_keys(self) -> Tuple[Tuple[str, str], ...]:
        """The declared artifact/instance pairs, for a membership test that cannot be fooled by
        two artifacts whose instances happen to share a local id."""
        return tuple(r.key for r in self.selected_instance_refs)


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
    form: Optional[PerceptualForm] = None
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
    """A scalar field: what the figure is NOT, with distance attached.

    The raster is large, so `field_ref` points at it while the payload keeps the metadata a reader
    needs to know what it is looking at. The pointer is inside the payload rather than replacing
    it, because `data_ref` at the measurement level means "the whole measurement is elsewhere" and
    a scalar field's shape, truncation distance and statistics are not elsewhere — they are what
    makes the pointer interpretable.
    """
    variant: Literal["negative_space_field"]
    figure_instance_ids: List[str] = Field(min_length=1)
    max_distance_used: float = Field(ge=0.0, le=1.0)
    field_shape: List[int] = Field(min_length=2, max_length=2)
    field_ref: Optional[DataRef] = None
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


# ── PERCEPTUAL-FORMS-001A: the shapes the sixteen new forms share ────────────
#
# Three small records the new payloads reuse rather than each inventing their own version of.
# `ScalarFieldSpec` in particular is why `extent.soft_field`, `extent.density_field` and any
# later field form cannot disagree about what a raster of numbers is: there is one declaration
# of shape, coordinates, range, derivation and calibration, and every field form embeds it.


def _normalized_points(points: List[List[float]], what: str) -> List[List[float]]:
    """Every point is an `[x, y]` pair inside the unit square. One check, four payloads."""
    for point in points:
        if len(point) != 2:
            raise ValueError(f"{what} carries {point!r}; a point is exactly [x, y]")
        if not all(0.0 <= c <= 1.0 for c in point):
            raise ValueError(f"{what} carries {point!r}, which is outside the normalized frame")
    return points


class CalibrationDeclaration(_Base):
    """What a field's numbers MEAN, said out loud rather than assumed by whoever reads them.

    THE ONE RULE THIS RECORD EXISTS FOR. A field produced by blurring a binary mask is a picture
    of an edge's uncertainty. It is NOT a probability, and calling it one lets a Gaussian radius
    read downstream as a confidence. So `calibrated` requires both a method and the reference it
    was calibrated against, and `ScalarFieldSpec` refuses the combination outright for a blurred
    mask. `nominal` is the honest word for "ordered and comparable"; `uncalibrated` is the honest
    word for "these numbers only have an order".
    """
    state: CalibrationState
    method: Optional[str] = None
    reference: Optional[str] = None
    units: Optional[str] = None

    @model_validator(mode="after")
    def _calibrated_names_its_method_and_its_reference(self) -> "CalibrationDeclaration":
        if self.state is CalibrationState.CALIBRATED and not (self.method and self.reference):
            raise ValueError(
                "a `calibrated` field names the method it was calibrated BY and the reference it "
                "was calibrated AGAINST. Calibration without either is a word, and a word that "
                "makes a number look like a probability")
        return self


class ScalarFieldSpec(_Base):
    """A raster of numbers, and everything a reader needs in order to know what they are.

    EXACTLY ONE CARRIER. A small field may be inlined; a large one points at itself through a
    `DataRef` whose digest is mandatory, because a pointer without a digest points at whatever is
    there now. Carrying both would create two truths, one of which is stale.

    THE POINTER DOES NOT REPLACE THE METADATA. Shape, coordinate system, value range, derivation
    and calibration stay here even when the raster is elsewhere — they are what makes the pointer
    interpretable, and a reader who cannot say what the numbers mean cannot draw them honestly.
    """
    field_shape: List[int] = Field(min_length=2, max_length=2)
    coordinate_system: CoordinateSystem
    value_range: List[float] = Field(min_length=2, max_length=2)
    derivation: FieldDerivation
    calibration: CalibrationDeclaration
    data_ref: Optional[DataRef] = None
    inline_values: Optional[List[float]] = None
    statistics: Dict[str, float] = Field(default_factory=dict)

    @field_validator("field_shape")
    @classmethod
    def _positive(cls, v: List[int]) -> List[int]:
        if any(n <= 0 for n in v):
            raise ValueError("a field shape is [height, width], both positive")
        return v

    @field_validator("value_range")
    @classmethod
    def _ordered(cls, v: List[float]) -> List[float]:
        if v[0] >= v[1]:
            raise ValueError("a value range is [low, high] with high strictly above low")
        return v

    @model_validator(mode="after")
    def _one_carrier(self) -> "ScalarFieldSpec":
        if (self.inline_values is None) == (self.data_ref is None):
            raise ValueError(
                "a field carries exactly one of inline_values / data_ref. A raster that does not "
                "fit inside a record points at itself, with a digest")
        if self.inline_values is not None:
            expected = self.field_shape[0] * self.field_shape[1]
            if len(self.inline_values) != expected:
                raise ValueError(
                    f"field_shape {self.field_shape} needs {expected} values and "
                    f"{len(self.inline_values)} were supplied")
        return self

    @model_validator(mode="after")
    def _a_blurred_mask_is_not_a_probability(self) -> "ScalarFieldSpec":
        if (self.derivation is FieldDerivation.BLUR_OF_BINARY_MASK
                and self.calibration.state is CalibrationState.CALIBRATED):
            raise ValueError(
                "a field blurred out of a binary mask may not declare itself `calibrated`. The "
                "numbers are a picture of where an edge is uncertain; nothing measured their "
                "correspondence to anything, and `calibrated` would let a Gaussian radius read "
                "downstream as a probability")
        return self


class Ground(_Base):
    """One piece of evidence a hypothesis rests on.

    ENUMERATED, NOT COLLAPSED INTO ONE NUMBER. `confidence: 0.94` with no ground is a number
    about nothing; a reviewer needs to know it was shape continuity rather than colour before
    they can disagree with it. `strength` is optional and per-ground, so a strong colour match
    and a weak shape match do not average into one uninspectable score.
    """
    kind: GroundKind
    detail: str = Field(min_length=1)
    cites: List[InputRef] = Field(default_factory=list)
    strength: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ── PERCEPTUAL-FORMS-001A: the extent forms ──────────────────────────────────


class BoundaryRing(_Base):
    """One closed curve of an extent's edge, declaring which side of it is inside.

    `winding` IS DECLARED, NEVER INFERRED FROM POINT ORDER. Half the renderers in the world read
    clockwise as outer and half read it as inner, and a boundary whose meaning depends on which
    one is looking is not a measurement.
    """
    ring_id: str = Field(min_length=1)
    winding: RingWinding
    points: List[List[float]] = Field(min_length=3)
    closed: bool = True
    length: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("points")
    @classmethod
    def _in_the_frame(cls, v: List[List[float]]) -> List[List[float]]:
        return _normalized_points(v, "a boundary ring")


class InstanceBoundary(_Base):
    """Every ring of one instance's edge, on the raster they were traced from."""
    of: InstanceRef
    rings: List[BoundaryRing] = Field(min_length=1)
    raster_shape: List[int] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _something_encloses_something(self) -> "InstanceBoundary":
        if not any(r.winding is RingWinding.OUTER for r in self.rings):
            raise ValueError(
                "a boundary with no outer ring encloses nothing. Inner rings are holes IN "
                "something, and a set of holes with no shape around them is not a boundary")
        ids = [r.ring_id for r in self.rings]
        if len(set(ids)) != len(ids):
            raise ValueError("two rings of one boundary share a ring_id")
        return self


class ExtentBoundaryPayload(_Base):
    """`extent.boundary_rings` — the edge as curves, derived from the mask that stays the
    authority.

    MULTI-RING BY CONSTRUCTION. A grille, an arch and a leaf each produce several outer rings and
    several inner ones, and a single-polygon field would have forced a producer to choose one and
    throw the rest away.
    """
    variant: Literal["extent_boundary"]
    rings_traced: int = Field(ge=0)
    boundaries: List[InstanceBoundary] = Field(default_factory=list)

    @model_validator(mode="after")
    def _the_count_is_the_count(self) -> "ExtentBoundaryPayload":
        traced = sum(len(b.rings) for b in self.boundaries)
        if self.boundaries and traced != self.rings_traced:
            raise ValueError(
                f"rings_traced is {self.rings_traced} and {traced} rings are recorded. The count "
                f"is what proves something looked; it is not a summary that may drift")
        return self


class ExtentHole(_Base):
    """One void, and the extent it is a void OF."""
    hole_id: str = Field(min_length=1)
    outer: InstanceRef
    enclosed: bool
    mask_rle: Optional[Dict[str, Any]] = None
    rings: List[BoundaryRing] = Field(default_factory=list)
    area: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _a_hole_has_a_shape(self) -> "ExtentHole":
        if self.mask_rle is None and not self.rings:
            raise ValueError("a hole with neither a mask nor a ring is a claim without a shape")
        return self


class ExtentHoleSetPayload(_Base):
    """`extent.hole_set` — the voids inside an extent, each tied to the extent it is inside.

    A VOID IS NOT A FREE-STANDING SHAPE. The arch's opening is only a hole OF the arch, and a
    hole record that did not name its outer extent would be a second extent set wearing a
    different word.

    `enclosed` SEPARATES A HOLE FROM A CONCAVITY. A bay open at one side is not a window, and a
    schema that called both `hole` would let a courtyard validate as a doorway.
    """
    variant: Literal["extent_hole_set"]
    candidates_examined: int = Field(ge=0)
    holes: List[ExtentHole] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "ExtentHoleSetPayload":
        ids = [h.hole_id for h in self.holes]
        if len(set(ids)) != len(ids):
            raise ValueError("two holes share a hole_id")
        return self


class ExtentSoftFieldPayload(_Base):
    """`extent.soft_field` — how much of it is here, where the edge is not a line.

    FOG IS THE CASE. A binary mask answers "where does it end" with a line the picture does not
    contain. This form answers with a value per cell and a declared statement of what that value
    means, and it has NO `mask_rle` anywhere in it — a soft field cannot be handed to something
    expecting a hard mask, because there is nothing in this record shaped like one.

    `threshold_would_be` is a courtesy, and it is not a mask. It records the cut a producer would
    use IF someone asked for one, so that a later binarization is a recorded decision rather than
    a number invented at render time.
    """
    variant: Literal["extent_soft_field"]
    cells_evaluated: int = Field(ge=0)
    searched: str = Field(min_length=1)
    field: ScalarFieldSpec
    of_instance: Optional[InstanceRef] = None
    threshold_would_be: Optional[float] = None


class ExtentFragment(_Base):
    """One visible piece. It does not know whether it belongs to anything."""
    fragment_id: str = Field(min_length=1)
    mask_rle: Optional[Dict[str, Any]] = None
    box: Optional[Box] = None
    area: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    naming: Optional[InstanceNaming] = None

    @model_validator(mode="after")
    def _some_geometry(self) -> "ExtentFragment":
        if self.mask_rle is None and self.box is None:
            raise ValueError("a fragment with neither a mask nor a box measures nothing")
        return self


class ExtentFragmentSetPayload(_Base):
    """`extent.fragment_set` — the pieces, with no claim about whether they are one thing.

    THE POINT IS WHAT IT CANNOT SAY. `unity_asserted` is the literal `false` and `extra="forbid"`
    means there is nowhere else to put the claim, so a producer that believes three green patches
    are one tree behind a fence has to say so in `extent.fused_hypothesis` — where the grounds
    are enumerated and the status is capped below `measured`.

    That is what makes this form SAFE TO COMPUTE EAGERLY. Nothing downstream can read unity out
    of it, so producing one commits to nothing at all.
    """
    variant: Literal["extent_fragment_set"]
    regions_examined: int = Field(ge=0)
    unity_asserted: Literal[False] = False
    fragments: List[ExtentFragment] = Field(default_factory=list)


class FusionHypothesis(_Base):
    """The claim that these pieces are one thing, with what it rests on and what it costs."""
    hypothesis_id: str = Field(min_length=1)
    members: List[InstanceRef] = Field(min_length=2)
    grounds: List[Ground] = Field(min_length=1)
    partition: EpistemicPartition
    epistemic_status: EpistemicStatus
    weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    asserts_hidden_extent: bool = False

    @model_validator(mode="after")
    def _a_grouping_is_not_a_measurement(self) -> "FusionHypothesis":
        if self.partition not in (EpistemicPartition.INTERPRETIVE_GROUPING,
                                  EpistemicPartition.INFERRED_COMPLETION):
            raise ValueError(
                f"a fusion is a grouping or a completion; {self.partition.value} is neither, and "
                f"the members being measured does not make the grouping measured")
        if (self.asserts_hidden_extent
                and self.partition is not EpistemicPartition.INFERRED_COMPLETION):
            raise ValueError(
                "a hypothesis asserting extent behind an occluder is an `inferred_completion`. "
                "Grouping what is visible and inventing what is not are two different claims")
        _cap(self.epistemic_status, PARTITION_CEILINGS[self.partition],
             f"a {self.partition.value} hypothesis")
        return self


class ExtentFusionHypothesisPayload(_Base):
    """`extent.fused_hypothesis` — are these pieces one thing, and on what evidence?

    A HYPOTHESIS CITES MEASUREMENTS AND DOES NOT INHERIT THEIR STATUS. Every member is a measured
    mask. The claim that they are one tree is not, and the partition caps it — at `interpretive`
    when it only groups what is visible, at `uncertain` when it also asserts extent behind the
    fence.

    `alternatives_retained` is a real field because dropping the rejected groupings is how a
    guess becomes a fact between one panel and the next.
    """
    variant: Literal["extent_fusion_hypothesis"]
    fragments_considered: int = Field(ge=0)
    hypotheses: List[FusionHypothesis] = Field(default_factory=list)
    alternatives_retained: bool

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "ExtentFusionHypothesisPayload":
        ids = [h.hypothesis_id for h in self.hypotheses]
        if len(set(ids)) != len(ids):
            raise ValueError("two hypotheses share a hypothesis_id")
        return self


class PartitionRegion(_Base):
    """One of the three parts, carrying its own status because they can never be the same one."""
    part: PartitionPart
    epistemic_status: EpistemicStatus
    coverage: float = Field(ge=0.0, le=1.0)
    mask_rle: Optional[Dict[str, Any]] = None
    field: Optional[ScalarFieldSpec] = None

    @model_validator(mode="after")
    def _a_part_claims_only_what_its_kind_can(self) -> "PartitionRegion":
        if (self.mask_rle is None) == (self.field is None):
            raise ValueError("a partition region carries exactly one of mask_rle / field")
        allowed = {
            PartitionPart.VISIBLE: {EpistemicStatus.MEASURED, EpistemicStatus.VISIBLE},
            PartitionPart.INFERRED: {EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN},
            PartitionPart.UNKNOWN: {EpistemicStatus.UNCERTAIN},
        }[self.part]
        if self.epistemic_status not in allowed:
            raise ValueError(
                f"the {self.part.value} part may be {sorted(s.value for s in allowed)}, not "
                f"{self.epistemic_status.value}. Pixels nobody saw do not become visible by being "
                f"drawn in the same colour as the ones who were")
        return self


class ExtentPartitionPayload(_Base):
    """`extent.visible_inferred_partition` — which of this we saw, which we inferred, which we do
    not know.

    THE PERSON BEHIND THE TABLE. The head and torso were seen; the legs were not. One mask
    covering both is a claim the picture does not support, and one covering only the torso throws
    away a reading worth keeping. Three parts, three statuses, enforced.

    `unknown` IS A REAL THIRD PART. Not-seen-and-not-inferred is not the same as absent, and a
    two-part schema would have forced every unresolved pixel into one of the other two.
    """
    variant: Literal["extent_partition"]
    cells_partitioned: int = Field(ge=0)
    of: InstanceRef
    regions: List[PartitionRegion] = Field(min_length=1)
    conditioned_on: Optional[str] = None

    @model_validator(mode="after")
    def _each_part_once_and_no_more_than_all_of_it(self) -> "ExtentPartitionPayload":
        parts = [r.part for r in self.regions]
        if len(set(parts)) != len(parts):
            raise ValueError("a partition names each of visible / inferred / unknown at most once")
        total = sum(r.coverage for r in self.regions)
        if total > 1.0 + 1e-6:
            raise ValueError(
                f"the three parts cover {total:.4f} of one extent, which is more than all of it")
        return self


class HierarchyNode(_Base):
    """One level of a nesting, cited by identity AND revision.

    Exactly one of `instance` / `region`. A node naming both would claim two provenances for one
    level, and a node naming neither is a level of nothing.
    """
    node_id: str = Field(min_length=1)
    instance: Optional[RevisionRef] = None
    region: Optional[RegionRef] = None
    parent_node_id: Optional[str] = None
    occupancy_of_parent: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    basis: EpistemicBasis

    @model_validator(mode="after")
    def _exactly_one_identity(self) -> "HierarchyNode":
        if (self.instance is None) == (self.region is None):
            raise ValueError("a hierarchy node names exactly one of instance / region")
        if self.parent_node_id is None and self.occupancy_of_parent is not None:
            raise ValueError("a root node occupies no parent")
        return self


def _acyclic(nodes: List[Any], *, what: str) -> List[str]:
    """Ids are unique, parents exist, and no parent chain reaches itself. Returns the roots."""
    ids = [n.node_id for n in nodes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"two {what} nodes share a node_id")
    by_id = {n.node_id: n for n in nodes}
    for node in nodes:
        if node.parent_node_id is not None and node.parent_node_id not in by_id:
            raise ValueError(
                f"{what} node {node.node_id!r} names parent {node.parent_node_id!r}, which this "
                f"record does not hold. A level of a hierarchy that is not in the hierarchy is a "
                f"reference to somewhere else")
        seen = {node.node_id}
        walk = node.parent_node_id
        while walk is not None:
            if walk in seen:
                raise ValueError(
                    f"the {what} contains a cycle through {node.node_id!r}. A containment cycle "
                    f"means the relations disagree, and dropping an edge to break it would hide "
                    f"the disagreement rather than report it")
            seen.add(walk)
            walk = by_id[walk].parent_node_id
    return [n.node_id for n in nodes if n.parent_node_id is None]


class ExtentHierarchyPayload(_Base):
    """`extent.hierarchy` — palace → courtyard → garden → fountain, with the fractions.

    EVERY LEVEL IS A REAL EXTENT WITH A REAL IDENTITY, and flattening them loses the only
    interesting question: how much of the courtyard IS garden.

    EVERY NODE CITES A REVISION. A tree built over `reg_7` without saying which revision of
    `reg_7` cannot be told it has gone stale, and a stale hierarchy is worse than none.
    """
    variant: Literal["extent_hierarchy"]
    pairs_examined: int = Field(ge=0)
    nodes: List[HierarchyNode] = Field(default_factory=list)
    root_node_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _a_tree_and_its_roots(self) -> "ExtentHierarchyPayload":
        roots = _acyclic(self.nodes, what="hierarchy")
        if self.nodes and sorted(self.root_node_ids) != sorted(roots):
            raise ValueError(
                f"root_node_ids is {sorted(self.root_node_ids)} and the parentless nodes are "
                f"{sorted(roots)}")
        return self


class SmoothingDeclaration(_Base):
    """What was done to the samples after they were placed. Declared, so that a bandwidth cannot
    be mistaken for a population."""
    applied: bool
    method: Optional[str] = None
    bandwidth: Optional[float] = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _smoothing_names_itself(self) -> "SmoothingDeclaration":
        if self.applied and not (self.method and self.bandwidth is not None):
            raise ValueError("smoothing that was applied names its method and its bandwidth")
        if not self.applied and (self.method or self.bandwidth is not None):
            raise ValueError("smoothing that was not applied has no method and no bandwidth")
        return self


class ExtentDensityFieldPayload(_Base):
    """`extent.density_field` — where the collection is, when there is no single object.

    FIVE HUNDRED PEOPLE IN A PLAZA. There is no object called `crowd`, and "the crowd occupies
    the eastern half" is still a true and useful sentence. This form is how it is said without
    inventing an entity to hang it on.

    COUNTS, SAMPLES AND SMOOTHING ARE THREE SEPARATE DECLARATIONS, because they answer three
    different questions and a single `density` number answers none of them: `members_counted` is
    how many entities entered, `samples_taken` is how many points were placed, and `smoothing` is
    what was applied afterwards. A smoothed field reporting itself as counts would let a kernel
    bandwidth read as a population.
    """
    variant: Literal["extent_density_field"]
    members_counted: int = Field(ge=0)
    samples_taken: int = Field(ge=0)
    counts_are_exact: bool
    members: List[InstanceRef] = Field(default_factory=list)
    field: ScalarFieldSpec
    smoothing: SmoothingDeclaration

    @model_validator(mode="after")
    def _the_count_is_the_count_and_smoothing_says_so(self) -> "ExtentDensityFieldPayload":
        if self.members and len(self.members) != self.members_counted:
            raise ValueError(
                f"members_counted is {self.members_counted} and {len(self.members)} members are "
                f"listed")
        if self.smoothing.applied and self.field.derivation not in (
                FieldDerivation.KERNEL_DENSITY, FieldDerivation.SAMPLE_HISTOGRAM):
            raise ValueError(
                f"a smoothed density field is derived by kernel density or by histogram, not by "
                f"{self.field.derivation.value}. Naming a derivation that does no smoothing while "
                f"declaring that smoothing was applied describes two different rasters")
        return self


class ExtentAlternative(_Base):
    """One competing reading of where the thing is."""
    alternative_id: str = Field(min_length=1)
    weight: float = Field(ge=0.0, le=1.0)
    artifact_id: Optional[str] = None
    instances: List[InstanceRef] = Field(default_factory=list)
    grounds: List[Ground] = Field(default_factory=list)

    @model_validator(mode="after")
    def _an_alternative_names_something(self) -> "ExtentAlternative":
        if not self.artifact_id and not self.instances:
            raise ValueError(
                "an alternative names the artifact that embodies it, or the instances it is made "
                "of. A weight attached to nothing is a number about nothing")
        return self


class ExtentHypothesisSetPayload(_Base):
    """`extent.hypothesis_set` — the competing readings, held open.

    THE CUBIST CASE. One continuous object, two overlapping objects, or an object and an
    architectural plane. The honest answer is that the picture supports three readings, and
    forcing one is a fabrication dressed as a measurement.

    IT CANNOT RESOLVE ITSELF. There is no `chosen` field anywhere in this record. Resolution is a
    separate act producing a separate artifact, so the alternatives survive the choice and a
    later reader can see what was set aside — which is the whole reason for writing them down.

    ONE ALTERNATIVE IS NOT AN ALTERNATIVE SET. If only one reading survived, the answer is a hard
    mask, and recording it here would dress a single reading as a preserved ambiguity.
    """
    variant: Literal["extent_hypothesis_set"]
    alternatives_considered: int = Field(ge=0)
    question: str = Field(min_length=1)
    weights_are_probabilities: bool = False
    alternatives: List[ExtentAlternative] = Field(default_factory=list)

    @model_validator(mode="after")
    def _two_or_none(self) -> "ExtentHypothesisSetPayload":
        if len(self.alternatives) == 1:
            raise ValueError(
                "one alternative is not an alternative set. A single surviving reading is a hard "
                "mask; recording it here would dress it as a preserved ambiguity")
        ids = [a.alternative_id for a in self.alternatives]
        if len(set(ids)) != len(ids):
            raise ValueError("two alternatives share an alternative_id")
        if self.weights_are_probabilities and self.alternatives:
            total = sum(a.weight for a in self.alternatives)
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"weights declared as probabilities sum to {total:.4f}. Either they are "
                    f"probabilities and they sum to one, or they are weights and they say so")
        return self


# ── PERCEPTUAL-FORMS-001A: the topology forms ────────────────────────────────


class ContactLocus(_Base):
    """WHERE two extents touch, not merely THAT they do."""
    locus_id: str = Field(min_length=1)
    source: RelationEndpoint
    target: RelationEndpoint
    raster_shape: List[int] = Field(min_length=2, max_length=2)
    contact_pixels: int = Field(ge=0)
    basis: EpistemicBasis
    epistemic_status: EpistemicStatus
    mask_rle: Optional[Dict[str, Any]] = None
    points: List[List[float]] = Field(default_factory=list)

    @field_validator("points")
    @classmethod
    def _in_the_frame(cls, v: List[List[float]]) -> List[List[float]]:
        return _normalized_points(v, "a contact locus")

    @model_validator(mode="after")
    def _a_locus_has_a_place_and_a_ceiling(self) -> "ContactLocus":
        if self.mask_rle is None and not self.points:
            raise ValueError("a contact locus with neither a mask nor points records no place")
        _cap(self.epistemic_status, BASIS_CEILINGS[self.basis],
             f"a {self.basis.value}-basis locus")
        return self


class TopologyContactLocusPayload(_Base):
    """`topology.contact_locus` — the band itself, recorded rather than re-derived.

    THE FORM THAT MOVES A DRAWING BACK INTO THE EVIDENCE. Today the band a person sees is
    computed in their browser and honestly stamped `derived: true, computed_by: lab_browser`,
    because `TopologyRelation` carries `contact_pixels` and no shape. The stamp is truthful and it
    is also a gap: nobody can review a band that was never recorded, and two readers on two
    rasters can disagree with nothing to appeal to.

    When a producer writes this form the same projection becomes `direct`, and the browser's
    derived band becomes a CHECK against it rather than a substitute for it.
    """
    variant: Literal["topology_contact_locus"]
    pairs_examined: int = Field(ge=0)
    loci: List[ContactLocus] = Field(default_factory=list)


class IntersectionRegion(_Base):
    """The shared region, with BOTH denominators."""
    intersection_id: str = Field(min_length=1)
    source: RelationEndpoint
    target: RelationEndpoint
    raster_shape: List[int] = Field(min_length=2, max_length=2)
    intersection_area: float = Field(ge=0.0, le=1.0)
    fraction_of_source: float = Field(ge=0.0, le=1.0)
    fraction_of_target: float = Field(ge=0.0, le=1.0)
    basis: EpistemicBasis
    epistemic_status: EpistemicStatus
    mask_rle: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _within_the_ceiling(self) -> "IntersectionRegion":
        _cap(self.epistemic_status, BASIS_CEILINGS[self.basis],
             f"a {self.basis.value}-basis intersection")
        return self


class TopologyIntersectionPayload(_Base):
    """`topology.intersection_area` — what they share, and how much of each it is.

    THE TREE ACROSS THE FAÇADE. `overlaps` is true and uninteresting. "The tree crosses seventy
    per cent of the façade's width" is the sentence a person wanted, and it needs the shared
    region and both denominators rather than one ratio — because a small thing entirely inside a
    large one covers all of itself and almost none of the other, and one number cannot say both.
    """
    variant: Literal["topology_intersection"]
    pairs_examined: int = Field(ge=0)
    intersections: List[IntersectionRegion] = Field(default_factory=list)


class ClearancePath(_Base):
    """The gap, and the line it was measured along."""
    path_id: str = Field(min_length=1)
    source: RelationEndpoint
    target: RelationEndpoint
    raster_shape: List[int] = Field(min_length=2, max_length=2)
    separation: float = Field(ge=0.0)
    from_point: List[float] = Field(min_length=2, max_length=2)
    to_point: List[float] = Field(min_length=2, max_length=2)
    path: List[List[float]] = Field(default_factory=list)
    basis: EpistemicBasis
    epistemic_status: EpistemicStatus

    @model_validator(mode="after")
    def _the_line_is_in_the_frame(self) -> "ClearancePath":
        _normalized_points([self.from_point, self.to_point] + list(self.path),
                           "a clearance path")
        _cap(self.epistemic_status, BASIS_CEILINGS[self.basis],
             f"a {self.basis.value}-basis clearance")
        return self


class TopologyClearancePathPayload(_Base):
    """`topology.clearance_path` — how far apart, and along which line.

    A DISTANCE WITHOUT A PATH CANNOT BE CHECKED. `separation: 0.11` is unfalsifiable on the
    screen. Two endpoints and the segment between them can be looked at and disagreed with, which
    is the entire difference between a measurement and an assertion.
    """
    variant: Literal["topology_clearance_path"]
    pairs_examined: int = Field(ge=0)
    paths: List[ClearancePath] = Field(default_factory=list)


class ContainmentNode(_Base):
    """One level of a containment, as a reference rather than a shape."""
    node_id: str = Field(min_length=1)
    endpoint: RelationEndpoint
    parent_node_id: Optional[str] = None
    occupancy_of_parent: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    basis: EpistemicBasis
    epistemic_status: EpistemicStatus

    @model_validator(mode="after")
    def _within_the_ceiling(self) -> "ContainmentNode":
        _cap(self.epistemic_status, BASIS_CEILINGS[self.basis],
             f"a {self.basis.value}-basis node")
        if self.parent_node_id is None and self.occupancy_of_parent is not None:
            raise ValueError("a root node occupies no parent")
        return self


class TopologyContainmentTreePayload(_Base):
    """`topology.containment_tree` — the nesting, assembled from relations already measured.

    A COMPOSITION, NOT A NEW MEASUREMENT. Every edge here is a relation that was measured
    already; the tree adds ordering and transitivity and no evidence at all, which is why its
    partition is `exact_derivation` and why it may claim no more than the weakest edge in it.

    CYCLES ARE REFUSED RATHER THAN BROKEN. A containment cycle means the relations disagree, and
    silently dropping an edge to make a tree would hide the disagreement instead of reporting it.
    """
    variant: Literal["topology_containment_tree"]
    pairs_examined: int = Field(ge=0)
    nodes: List[ContainmentNode] = Field(default_factory=list)
    root_node_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _a_tree_and_its_roots(self) -> "TopologyContainmentTreePayload":
        roots = _acyclic(self.nodes, what="containment")
        if self.nodes and sorted(self.root_node_ids) != sorted(roots):
            raise ValueError(
                f"root_node_ids is {sorted(self.root_node_ids)} and the parentless nodes are "
                f"{sorted(roots)}")
        return self


class GraphNode(_Base):
    node_id: str = Field(min_length=1)
    endpoint: RelationEndpoint


class GraphEdge(_Base):
    """One relation between two nodes THE GRAPH HOLDS."""
    edge_id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    kind: RelationKind
    directed: bool
    basis: EpistemicBasis
    epistemic_status: EpistemicStatus
    measurements: Dict[str, float] = Field(default_factory=dict)
    locus_artifact_id: Optional[str] = None

    @model_validator(mode="after")
    def _an_edge_joins_two_things(self) -> "GraphEdge":
        if self.source_node_id == self.target_node_id:
            raise ValueError("an edge from a node to itself is not a relation between two extents")
        _cap(self.epistemic_status, BASIS_CEILINGS[self.basis],
             f"a {self.basis.value}-basis edge")
        return self


class TopologyAdjacencyGraphPayload(_Base):
    """`topology.adjacency_graph` — what touches what, across the whole scene.

    THE NAVE AT WELLS. Pier, arch, pier, arch, receding. The interesting object is the repeated
    structure, and it exists only once the pairwise relations are assembled into one graph whose
    nodes are identities rather than positions.

    EVERY EDGE NAMES TWO NODES THE RECORD HOLDS. An edge to an unlisted node is a relation about
    something this graph does not contain, and a graph that admitted one could not be read
    without going somewhere else to find out what it meant.
    """
    variant: Literal["topology_adjacency_graph"]
    pairs_examined: int = Field(ge=0)
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _the_edges_stay_inside_the_graph(self) -> "TopologyAdjacencyGraphPayload":
        ids = [n.node_id for n in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("two graph nodes share a node_id")
        held = set(ids)
        for edge in self.edges:
            missing = {edge.source_node_id, edge.target_node_id} - held
            if missing:
                raise ValueError(
                    f"edge {edge.edge_id!r} names {sorted(missing)}, which this graph does not "
                    f"hold. An edge to a node that is not here is a relation about something else")
        edge_ids = [e.edge_id for e in self.edges]
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("two edges share an edge_id")
        return self


class RelationState(_Base):
    """How one pair stood, at one pair of revisions. `kind: null` is 'no relation then'."""
    source: RevisionRef
    target: RevisionRef
    kind: Optional[RelationKind] = None
    measurements: Dict[str, float] = Field(default_factory=dict)


class TopologyTransition(_Base):
    """What changed, cited at both ends and on both sides."""
    transition_id: str = Field(min_length=1)
    before: RelationState
    after: RelationState
    change: TransitionChange

    @model_validator(mode="after")
    def _the_same_pair_at_two_revisions(self) -> "TopologyTransition":
        for role, was, now in (("source", self.before.source, self.after.source),
                               ("target", self.before.target, self.after.target)):
            if was.instance.key != now.instance.key:
                raise ValueError(
                    f"the {role} before this transition is {was.instance} and after it is "
                    f"{now.instance}. A transition is one pair at two revisions, not two pairs")
        if (self.before.source.geometry_rev == self.after.source.geometry_rev
                and self.before.target.geometry_rev == self.after.target.geometry_rev):
            raise ValueError(
                "before and after cite the same two revisions, so nothing was revised. That is a "
                "relation measured twice, not a transition")
        was, now = self.before.kind, self.after.kind
        if was is None and now is None:
            raise ValueError("no relation before and none after is not a transition")
        expected = (TransitionChange.APPEARED if was is None else
                    TransitionChange.DISAPPEARED if now is None else
                    TransitionChange.UNCHANGED if was is now else TransitionChange.CHANGED)
        if self.change is not expected:
            raise ValueError(
                f"the kinds go from {was.value if was else 'none'} to "
                f"{now.value if now else 'none'}, which is {expected.value}, and the record says "
                f"{self.change.value}")
        return self


class TopologyTransitionPayload(_Base):
    """`topology.transition` — what changed between two revisions of the same pair.

    A REFINEMENT CHANGES A MASK, AND EVERY RELATION THAT RESTED ON IT IS NOW ABOUT SOMETHING
    ELSE. `TopologyRelation.stale` can say a relation is out of date. Only this form says what
    the change WAS — that `meets` became `overlaps`, or that `disjoint` became `meets` — and only
    a record citing four revision-pinned references can be checked by someone who was not there.
    """
    variant: Literal["topology_transition"]
    revisions_compared: int = Field(ge=0)
    transitions: List[TopologyTransition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "TopologyTransitionPayload":
        ids = [t.transition_id for t in self.transitions]
        if len(set(ids)) != len(ids):
            raise ValueError("two transitions share a transition_id")
        return self


class HypothesisCitation(_Base):
    """The extent hypothesis a set of relations hangs on, named where it lives."""
    hypothesis_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ConditionalRelation(_Base):
    """A relation that is only true IF a reading of the extents is right."""
    relation_id: str = Field(min_length=1)
    kind: RelationKind
    source: RelationEndpoint
    target: RelationEndpoint
    directed: bool
    basis: EpistemicBasis
    epistemic_status: EpistemicStatus
    conditioned_on: str = Field(min_length=1)
    measurements: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _a_conditional_relation_is_never_measured(self) -> "ConditionalRelation":
        if self.epistemic_status in (EpistemicStatus.MEASURED, EpistemicStatus.VISIBLE):
            raise ValueError(
                f"a relation that holds only under a hypothesis may not be "
                f"{self.epistemic_status.value}. The masks under it were measured; the relation "
                f"between things that may not be those things was not")
        _cap(self.epistemic_status, BASIS_CEILINGS[self.basis],
             f"a {self.basis.value}-basis conditional relation")
        return self


class TopologyUncertainRelationsPayload(_Base):
    """`topology.uncertain_relation_set` — what would be true, if that reading were right.

    IF THE FRAGMENTS ARE ONE OBJECT THEN IT OVERLAPS THE PLANE; IF THEY ARE TWO THEN ONE OF THEM
    IS BEHIND IT. Both are worth recording, and neither is a measurement.

    EVERY RELATION NAMES THE HYPOTHESIS IT HANGS ON, and that hypothesis must be one this payload
    declared. A conditional relation whose condition was dropped reads exactly like a measured
    one — same kind, same endpoints, same numbers — which is precisely the substitution this form
    exists to make impossible.
    """
    variant: Literal["topology_uncertain_relations"]
    pairs_examined: int = Field(ge=0)
    hypotheses: List[HypothesisCitation] = Field(min_length=1)
    relations: List[ConditionalRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _every_condition_is_one_we_declared(self) -> "TopologyUncertainRelationsPayload":
        ids = [h.hypothesis_id for h in self.hypotheses]
        if len(set(ids)) != len(ids):
            raise ValueError("two citations share a hypothesis_id")
        declared = set(ids)
        for relation in self.relations:
            if relation.conditioned_on not in declared:
                raise ValueError(
                    f"relation {relation.relation_id!r} is conditioned on "
                    f"{relation.conditioned_on!r}, which this record does not declare. A "
                    f"condition nobody can look up is a condition that has been dropped, and a "
                    f"dropped condition reads as a measurement")
        return self


ArtifactPayload = Annotated[
    Union[
        # the four the laboratory already writes, unchanged
        ExtentSetPayload, TopologyRelationSetPayload, NegativeSpaceFieldPayload, RefusalPayload,
        # PERCEPTUAL-FORMS-001A — the extent forms
        ExtentBoundaryPayload, ExtentHoleSetPayload, ExtentSoftFieldPayload,
        ExtentFragmentSetPayload, ExtentFusionHypothesisPayload, ExtentPartitionPayload,
        ExtentHierarchyPayload, ExtentDensityFieldPayload, ExtentHypothesisSetPayload,
        # PERCEPTUAL-FORMS-001A — the topology forms
        TopologyContactLocusPayload, TopologyIntersectionPayload, TopologyClearancePathPayload,
        TopologyContainmentTreePayload, TopologyAdjacencyGraphPayload, TopologyTransitionPayload,
        TopologyUncertainRelationsPayload,
    ],
    Field(discriminator="variant"),
]

#: `{payload_variant: model}`, so a test can reach a form's payload by the name the contract uses
#: without a chain of isinstance checks. The parity suite asserts it covers every declared
#: variant, which is how a payload model added without a variant — or the other way round — fails.
FORM_PAYLOAD_MODELS: Mapping[str, type] = {
    "extent_set": ExtentSetPayload,
    "extent_boundary": ExtentBoundaryPayload,
    "extent_hole_set": ExtentHoleSetPayload,
    "extent_soft_field": ExtentSoftFieldPayload,
    "extent_fragment_set": ExtentFragmentSetPayload,
    "extent_fusion_hypothesis": ExtentFusionHypothesisPayload,
    "extent_partition": ExtentPartitionPayload,
    "extent_hierarchy": ExtentHierarchyPayload,
    "extent_density_field": ExtentDensityFieldPayload,
    "extent_hypothesis_set": ExtentHypothesisSetPayload,
    "topology_relation_set": TopologyRelationSetPayload,
    "topology_contact_locus": TopologyContactLocusPayload,
    "topology_intersection": TopologyIntersectionPayload,
    "topology_clearance_path": TopologyClearancePathPayload,
    "topology_containment_tree": TopologyContainmentTreePayload,
    "topology_adjacency_graph": TopologyAdjacencyGraphPayload,
    "negative_space_field": NegativeSpaceFieldPayload,
    "topology_transition": TopologyTransitionPayload,
    "topology_uncertain_relations": TopologyUncertainRelationsPayload,
    "refusal": RefusalPayload,
}


class ArtifactMeasurement(_Base):
    """The number, and what kind of knowing it is. Never the colour it is drawn in.

    Exactly one of `payload` / `data_ref`: a measurement is either small enough to carry or big
    enough to point at, and carrying both would create two truths one of which is stale.
    """
    payload_variant: PayloadVariant
    payload: Optional[ArtifactPayload] = None
    data_ref: Optional[DataRef] = None
    coordinate_system: CoordinateSystem
    epistemic_status: EpistemicStatus
    epistemic_basis: EpistemicBasis
    partition: Optional[EpistemicPartition] = None
    basis_detail: Optional[str] = None

    @model_validator(mode="after")
    def _one_carrier_and_it_matches_the_variant(self) -> "ArtifactMeasurement":
        if (self.payload is None) == (self.data_ref is None):
            raise ValueError("a measurement carries exactly one of payload / data_ref")
        if self.payload is not None and self.payload.variant != self.payload_variant.value:
            raise ValueError(
                f"payload_variant is {self.payload_variant.value!r} and the payload is "
                f"{self.payload.variant!r}")
        return self

    @model_validator(mode="after")
    def _status_is_an_image_status_within_its_ceiling(self) -> "ArtifactMeasurement":
        if self.epistemic_status not in MEASUREMENT_STATUSES:
            raise ValueError(
                f"a measurement may be {sorted(s.value for s in MEASUREMENT_STATUSES)}; "
                f"{self.epistemic_status.value} is not obtainable by looking at this image")
        ceiling = BASIS_CEILINGS[self.epistemic_basis]
        if STATUS_ORDER[self.epistemic_status] > STATUS_ORDER[ceiling]:
            raise ValueError(
                f"a {self.epistemic_basis.value}-basis measurement may claim at most "
                f"{ceiling.value}, not {self.epistemic_status.value}")
        return self

    @model_validator(mode="after")
    def _the_partition_caps_it_too(self) -> "ArtifactMeasurement":
        """PERCEPTUAL-FORMS-001A. The basis says what this was computed FROM; the partition says
        what was DONE, and both cap the claim.

        This is the whole structural answer to "a hypothesis may cite measurements and may not
        inherit `measured` merely because its inputs were measured". A completion behind an
        occluder is computed from a mask — perfect `mask` basis, ceiling `measured` — and it is
        still an assertion about pixels nobody saw, so `inferred_completion` caps it at
        `uncertain` and no confidence lifts it.
        """
        if self.partition is None:
            return self
        _cap(self.epistemic_status, PARTITION_CEILINGS[self.partition],
             f"a {self.partition.value} measurement")
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

    # ── PERCEPTUAL-FORMS-001A ────────────────────────────────────────────────
    #
    # Seven gates that run only once a form is in play. A `refusal` has no perceptual form — it is
    # the record of a question NOT answered — so `effective_form` returns None for it and every
    # gate below returns early. That is deliberate: a refusal is not a nineteenth kind of seeing.

    @property
    def effective_form(self) -> Optional[PerceptualForm]:
        """The form this artifact is in, whether or not it says so.

        A record written before this grammar existed carries no `form`, and it still means exactly
        what it meant: `legacy_form_for_kind` in the contract is the table that says which. This
        property is the only place that lookup happens, so "old records remain readable" is one
        line rather than a convention repeated in six validators.
        """
        if self.identity.form is not None:
            return self.identity.form
        legacy = legacy_form_index().get(self.identity.artifact_kind.value)
        return PerceptualForm(legacy) if legacy else None

    @property
    def form_declaration(self) -> Optional[Dict[str, Any]]:
        form = self.effective_form
        return form_index()[form.value] if form is not None else None

    @model_validator(mode="after")
    def _the_form_and_the_kind_are_the_same_answer(self) -> "PerceptualArtifact":
        if self.identity.form is not None:
            declared = form_index()[self.identity.form.value]
            if declared["artifact_kind"] != self.identity.artifact_kind.value:
                raise ValueError(
                    f"form {self.identity.form.value!r} is carried by artifact kind "
                    f"{declared['artifact_kind']!r} and this artifact declares "
                    f"{self.identity.artifact_kind.value!r}. A form and a kind that disagree are "
                    f"two answers to one question")
            if declared["organ"] != self.identity.organ_family.value:
                raise ValueError(
                    f"form {self.identity.form.value!r} belongs to the {declared['organ']} organ, "
                    f"not {self.identity.organ_family.value}")
        elif self.identity.artifact_kind is not ArtifactKind.REFUSAL:
            if self.identity.artifact_kind.value not in legacy_form_index():
                raise ValueError(
                    f"an artifact of kind {self.identity.artifact_kind.value!r} must declare its "
                    f"`identity.form`. Only the three kinds that existed before the form grammar "
                    f"did may leave it null, and only because `legacy_form_for_kind` says what "
                    f"they are")
        return self

    @model_validator(mode="after")
    def _a_registered_form_is_not_a_producer(self) -> "PerceptualArtifact":
        """`deferred` cannot be written; `experimental` cannot leave the laboratory.

        The same discipline `depth_field` is held to, for the same reason: a payload shape agreed
        in advance is what stops the lane that finally implements fog from inventing its own field
        record, and a state that let it be written today would make this file claim the laboratory
        can already see something it cannot.
        """
        declaration = self.form_declaration
        if declaration is None:
            return self
        state = FormState(declaration["state"])
        if state is FormState.DEFERRED:
            raise ValueError(
                f"{declaration['key']} is registered and deferred. Its payload is designed and "
                f"validated and nothing in this phase produces one — the refusal for trying is "
                f"`form_not_producible`")
        if state is FormState.EXPERIMENTAL and self.lifecycle.status is LifecycleState.PROMOTED:
            raise ValueError(
                f"{declaration['key']} is experimental. It may be kept inside the laboratory and "
                f"it may not be promoted into Semant, because promotion is the point at which a "
                f"shape nobody has reviewed becomes something the rest of the system reads")
        return self

    @model_validator(mode="after")
    def _a_hypothesis_is_not_curated_by_confidence(self) -> "PerceptualArtifact":
        """A hypothesis-carrying form may not reach `kept` or `promoted`, at any confidence.

        Resolving an alternative produces a NEW artifact of a resolved form, citing this one. It
        does not re-badge the guess — because a `kept` hypothesis is indistinguishable, on every
        later screen and in every later export, from a finding.
        """
        declaration = self.form_declaration
        if declaration and declaration.get("carries_hypothesis") and self.lifecycle.status in (
                LifecycleState.KEPT, LifecycleState.PROMOTED):
            raise ValueError(
                f"{declaration['key']} carries a hypothesis and may not be "
                f"{self.lifecycle.status.value}. Resolving it produces a new artifact of a "
                f"resolved form; it does not promote the guess")
        return self

    @model_validator(mode="after")
    def _the_form_admits_this_basis_partition_and_claim(self) -> "PerceptualArtifact":
        declaration = self.form_declaration
        if declaration is None:
            return self
        basis = self.measurement.epistemic_basis.value
        if basis not in declaration["admissible_bases"]:
            raise ValueError(
                f"{declaration['key']} is measured from {declaration['admissible_bases']}, not "
                f"from {basis!r}")
        if self.measurement.partition is not None:
            if self.measurement.partition.value not in declaration["admissible_partitions"]:
                raise ValueError(
                    f"{declaration['key']} admits the partitions "
                    f"{declaration['admissible_partitions']}, not "
                    f"{self.measurement.partition.value!r}")
        _cap(self.measurement.epistemic_status,
             EpistemicStatus(declaration["epistemic_ceiling"]), f"the {declaration['key']} form")
        return self

    @model_validator(mode="after")
    def _a_derivation_declares_what_it_derived_from(self) -> "PerceptualArtifact":
        """A derivation from nothing derived nothing.

        `exact_derivation` and `interpretive_grouping` both mean "this rests on records already
        made". An artifact claiming either while citing no input is either a direct measurement
        wearing the wrong partition, or a claim whose evidence has gone missing, and there is no
        third case worth admitting.
        """
        if (self.measurement.partition in DERIVING_PARTITIONS
                and not self.identity.input_refs):
            raise ValueError(
                f"a {self.measurement.partition.value} cites no input. It rests on records "
                f"already made, and a record it cannot name is a record nobody can check it "
                f"against")
        return self

    @model_validator(mode="after")
    def _the_form_gets_the_receipt_it_asks_for(self) -> "PerceptualArtifact":
        declaration = self.form_declaration
        if declaration is None:
            return self
        missing = [f for f in declaration["required_provenance"]
                   if getattr(self.provenance, f, None) in (None, "")]
        if missing:
            raise ValueError(
                f"{declaration['key']} requires {declaration['required_provenance']} in its "
                f"provenance and {missing} are absent. A derived record that cannot say which "
                f"revision of the code composed it cannot be reproduced")
        return self

    @model_validator(mode="after")
    def _the_projection_is_one_the_form_declares(self) -> "PerceptualArtifact":
        """A renderer is never the measurement, and it is never a renderer the form does not have.

        `none` is always allowed: an artifact that is not drawn is not a lie about how it looks.
        Everything else must be in the form's declared list, so a projection kind that reached the
        screen without a declaration fails here rather than in a component.
        """
        declaration = self.form_declaration
        if declaration is None or self.projection.projection_kind is ProjectionKind.NONE:
            return self
        declared = {p["kind"] for p in declaration["renderer_projections"]}
        if self.projection.projection_kind.value not in declared:
            raise ValueError(
                f"{declaration['key']} declares the projections {sorted(declared)}; "
                f"{self.projection.projection_kind.value!r} is not one of them, and a drawing "
                f"nobody declared is a drawing nobody can say is faithful")
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

#: The three reference shapes, by the name the contract's `references` block uses. One identity
#: reaching three depths — artifact, instance, revision — and not three identity systems.
REFERENCE_MODELS: Mapping[str, type] = {
    "InputRef": InputRef,
    "InstanceRef": InstanceRef,
    "RevisionRef": RevisionRef,
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

def _assert_field_parity() -> None:
    """Every field list the contract declares equals the model's, at import.

    The closed-set check above catches a renamed MEMBER; this catches a renamed or dropped FIELD,
    which is the failure A2 was written to repair — `instance_id` existed on the frontend and not
    in this file, and nothing failed until a request reached a validator. Now adding a field to a
    declared record without saying so in the contract stops the first import.
    """
    contract = lab_contract()
    declared: Dict[str, Any] = {}
    declared.update({k: v for k, v in contract["references"].items() if k in REFERENCE_MODELS})
    declared.update({k: v for k, v in contract["records"].items() if k in RECORD_MODELS})
    for name, block in declared.items():
        fields = block.get("fields")
        if fields is None:
            continue
        model = {**REFERENCE_MODELS, **RECORD_MODELS}[name]
        here = tuple(model.model_fields)
        if tuple(fields) != here:
            raise ContractError(
                f"the contract declares {name} as {tuple(fields)} and "
                f"backend/schemas/perception_lab.py declares {here}. A field that exists in one "
                f"runtime and not the other is the A2 defect verbatim — move both or neither.")


_assert_field_parity()


def _assert_form_parity() -> None:
    """PERCEPTUAL-FORMS-001A. Every registered form has a payload here, and can say it looked.

    Two failures this catches at import rather than in a fixture:

        a form registered with no payload model — a word in a registry, nothing behind it;
        a form whose `examined_field` does not exist, or has a DEFAULT — which would let an empty
        payload validate as a measurement of nothing, and that is the one absence law this whole
        contract is built around.
    """
    variants = set(closed_set("payload_variants"))
    if set(FORM_PAYLOAD_MODELS) != variants:
        raise ContractError(
            f"the contract declares payload variants {sorted(variants)} and FORM_PAYLOAD_MODELS "
            f"holds {sorted(FORM_PAYLOAD_MODELS)}. A variant with no model is a form nothing can "
            f"carry; a model with no variant is a shape nothing can name.")
    for key, form in form_index().items():
        variant = form["payload_variant"]
        if variant != form["artifact_kind"]:
            raise ContractError(
                f"form {key!r} declares artifact kind {form['artifact_kind']!r} and payload "
                f"variant {variant!r}. `PerceptualArtifact` requires them equal.")
        model = FORM_PAYLOAD_MODELS[variant]
        examined = form["absence"]["examined_field"]
        field = model.model_fields.get(examined)
        if field is None:
            raise ContractError(
                f"form {key!r} names {examined!r} as the field that proves something looked, and "
                f"{model.__name__} has no such field.")
        if not field.is_required():
            raise ContractError(
                f"{model.__name__}.{examined} has a default. It is the field that tells an empty "
                f"measurement apart from an absent one, and a default answers that question for "
                f"a producer who never did.")
        for projection in form["renderer_projections"]:
            if projection["kind"] not in {p.value for p in ProjectionKind}:
                raise ContractError(
                    f"form {key!r} declares the projection {projection['kind']!r}, which is not "
                    f"a projection kind.")
        forbidden = set(model.model_fields) & (PROJECTION_HINT_KEYS | {"projection_kind"})
        if forbidden:
            raise ContractError(
                f"{model.__name__} carries {sorted(forbidden)}. A renderer is never the "
                f"measurement, and a payload able to hold its own opacity is a payload able to "
                f"disagree with the block that draws it.")


_assert_form_parity()


__all__ = [
    "SCHEMA_VERSION", "OrganFamily", "SessionMode", "PlannerIdentity", "ExecutionIdentity",
    "RunOutcome", "StageState", "LifecycleState", "ReviewVerdict", "EpistemicStatus",
    "EpistemicBasis", "ArtifactKind", "IdentityScope", "ProducerKind", "CapabilityState",
    "CoordinateSystem", "LabelSource", "RefusalCode", "ProjectionKind", "ManualToolKind",
    "RelationKind",
    # PERCEPTUAL-FORMS-001A
    "PerceptualForm", "FormState", "ProducerClass", "EpistemicPartition", "RendererMode",
    "ComparisonMethod", "FieldDerivation", "CalibrationState", "GroundKind", "RingWinding",
    "PartitionPart", "TransitionChange", "PayloadVariant",
    "PARTITION_CEILINGS", "STATUS_ORDER", "INFERRING_PARTITIONS", "DERIVING_PARTITIONS",
    "RevisionRef", "CalibrationDeclaration", "ScalarFieldSpec", "Ground",
    "BoundaryRing", "InstanceBoundary", "ExtentBoundaryPayload", "ExtentHole",
    "ExtentHoleSetPayload", "ExtentSoftFieldPayload", "ExtentFragment",
    "ExtentFragmentSetPayload", "FusionHypothesis", "ExtentFusionHypothesisPayload",
    "PartitionRegion", "ExtentPartitionPayload", "HierarchyNode", "ExtentHierarchyPayload",
    "SmoothingDeclaration", "ExtentDensityFieldPayload", "ExtentAlternative",
    "ExtentHypothesisSetPayload", "ContactLocus", "TopologyContactLocusPayload",
    "IntersectionRegion", "TopologyIntersectionPayload", "ClearancePath",
    "TopologyClearancePathPayload", "ContainmentNode", "TopologyContainmentTreePayload",
    "GraphNode", "GraphEdge", "TopologyAdjacencyGraphPayload", "RelationState",
    "TopologyTransition", "TopologyTransitionPayload", "HypothesisCitation",
    "ConditionalRelation", "TopologyUncertainRelationsPayload", "FORM_PAYLOAD_MODELS",
    "BASIS_CEILINGS", "MEASUREMENT_STATUSES", "INTERPRETATION_STATUSES", "PROJECTION_HINT_KEYS",
    "ENABLED_ORGAN_FAMILIES", "Box", "RegionRef", "InstanceRef", "InputRef", "DataRef",
    "RefusalRecord",
    "LabSource", "PromptTurn", "LabSession", "ProposedStep", "ResolvedStep", "DroppedParameter",
    "ClampedParameter", "LabPlan", "ArtifactIdentity", "InstanceNaming", "ExtentInstance",
    "ExtentCorrespondence", "ExtentDuplicate", "ExtentComparison", "ExtentSetPayload",
    "RelationEndpoint", "TopologyRelation", "TopologyRelationSetPayload",
    "NegativeSpaceFieldPayload", "RefusalPayload", "ArtifactMeasurement", "ArtifactProjection",
    "ArtifactInterpretation", "ArtifactLifecycle", "ArtifactProvenance", "PerceptualArtifact",
    "StageAttempt", "ReplayProvenance", "LabRun", "ReviewCorrection", "LabReview",
    "RECORD_MODELS", "REFERENCE_MODELS", "ARTIFACT_BLOCK_MODELS",
]
