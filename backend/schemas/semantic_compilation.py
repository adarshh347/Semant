"""
HARNESS-002A — the Semantic Inquiry Graph: what a question and a reading turn into.

WHAT THIS OBJECT IS. A rich visual question, an abundant provisional reading of the pictures, and
the transformation between them made inspectable: atomic typed claims, the relations between them,
and — for each claim that could be investigated at all — a statement of what would have to become
OBSERVABLE for it to gain support.

WHAT IT IS NOT. It is not evidence, not a measurement, not a result, and not a plan. Nothing here
has run. `ObservableSpec` names a capability CLASS ("extent", "depth", "external_source") and
deliberately never an actuator, an organ or a model: choosing an implementation is the broker's job
downstream, and a compiler that chose one would make a capability gap look like a planning error.

THE TWO SEPARATIONS THE WHOLE FILE IS SHAPED BY.

  1. WORDS AND PIXELS STAY APART. `InquiryFrame` (HARNESS-001A) reads the prompt and corpus
     metadata and never sees an image. `SceneReading` sees the images. Both arrive here, and both
     keep their own provenance — the graph never merges them into one undifferentiated "context",
     because "the user said this" and "a VLM thought it saw this" are different warrants and only
     the first is something the person can be held to.

  2. A THINKER THAT LOOKS IS STILL A THINKER. The scene theorist reads pixels and its ceiling is
     `interpretive` regardless. It may say a thing is present; it may not say WHERE, in numbers.
     `forbidden_geometry_keys` is checked on KEYS rather than values and refuses rather than
     strips, because a stripped key is a model authoring geometry, silently.

STRICT. Every model forbids unknown fields, for the reason HARNESS-001A gives: a key nobody
declared is exactly how geometry arrives.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.schemas.inquiry import DemandKind

#: The version this code WRITES. v1 is still read — see `READABLE_SCHEMA_VERSIONS`.
SCHEMA_VERSION_V1 = "semantic-inquiry-graph.v1"
SCHEMA_VERSION_V2 = "semantic-inquiry-graph.v2"
SCHEMA_VERSION = SCHEMA_VERSION_V2

#: Every version this code can VALIDATE. v1 graphs are stored in the runs collection and frozen in
#: fixtures; a validator that refused them would make the migration a data loss rather than a
#: version bump. A v1 graph simply carries no source units, no atoms and no coverage — which is what
#: it never had, rather than an absence somebody has to interpret.
READABLE_SCHEMA_VERSIONS: Tuple[str, ...] = (SCHEMA_VERSION_V1, SCHEMA_VERSION_V2)


# ── the closed sets ──────────────────────────────────────────────────────────
# Every one of these is pinned against `contracts/semantic-inquiry-graph.v1.json` by
# `test_semantic_compilation_contract.py`. The contract is canonical; these enums are how Python
# reads it, and a divergence fails by name rather than forking the vocabulary in half.

class ClaimKind(str, Enum):
    """The stable open grammar. Thirteen shapes; the subjects stay open strings.

    `UNKNOWN` is a legal outcome and a visible one. A compiler that dropped what it could not type
    would produce a graph that looks more complete than the reading it came from.
    """
    ENTITY = "entity"
    ATTRIBUTE = "attribute"
    SPATIAL_RELATION = "spatial_relation"
    TOPOLOGY = "topology"
    PATTERN_OR_SEQUENCE = "pattern_or_sequence"
    FIELD = "field"
    HIERARCHY = "hierarchy"
    COMPARISON = "comparison"
    HISTORICAL_OR_SOURCED = "historical_or_sourced"
    CAUSAL_HYPOTHESIS = "causal_hypothesis"
    INTERPRETATION = "interpretation"
    GENERATIVE_RULE = "generative_rule"
    UNKNOWN = "unknown"


class ClaimEdgeKind(str, Enum):
    """How two claims stand to each other.

    The first three are `director.argument`'s rhetorical functions, reused deliberately rather than
    respelled: a percept that SUPPORTS a claim and a claim that SUPPORTS another claim are the same
    relation at two scales, and two vocabularies for it would drift the moment either moved.
    """
    SUPPORTS = "supports"
    COMPLICATES = "complicates"
    CHALLENGES = "challenges"
    COMPOSES_FROM = "composes_from"
    GENERALIZES = "generalizes"


class ClaimStatus(str, Enum):
    """What a claim is, before anything has been produced for it.

    `visible` and `measured` are DELIBERATELY ABSENT rather than present-and-forbidden. An enum
    that can express a measured claim is one a parser can be talked into constructing; an enum that
    cannot is a wall. A model that says "measured" gets a named refusal, in `_status_of`.
    """
    INTERPRETIVE = "interpretive"
    SOURCED = "sourced"
    UNCERTAIN = "uncertain"


#: The two statuses no compiled claim may start at, named so the refusal can quote them.
FORBIDDEN_INITIAL_STATUSES: Tuple[str, ...] = ("visible", "measured")


class ImageScope(str, Enum):
    """How much of the corpus a claim is about. `not_an_image_question` is a real answer — a
    historical or generative claim is not scoped to a picture at all, and typing it as if it were
    is how a source becomes something somebody looks for in the frame."""
    ONE_IMAGE = "one_image"
    IMAGE_PAIR = "image_pair"
    CORPUS = "corpus"
    NOT_AN_IMAGE_QUESTION = "not_an_image_question"


class SourceType(str, Enum):
    """Where a claim's words came from. Four warrants, and they are not interchangeable."""
    PROMPT = "prompt"
    INQUIRY_FRAME = "inquiry_frame"
    SCENE_READING = "scene_reading"
    COMPILER_INFERENCE = "compiler_inference"


class CapabilityClass(str, Enum):
    """What KIND of instrument a claim would need. Never which one.

    This is the fourth vocabulary in the system and it is kept unflattened from the other three for
    the same reason `inquiry_engine.capability` keeps those three apart: a class with no instrument
    today has to be expressible, and it stops being expressible the moment classes are spelled as
    tool names.
    """
    EXTENT = "extent"
    GEOMETRY = "geometry"
    TOPOLOGY = "topology"
    PATTERN = "pattern"
    SCALAR_FIELD = "scalar_field"
    VECTOR_FIELD = "vector_field"
    DEPTH = "depth"
    COLOUR = "colour"
    SEMANTIC_READING = "semantic_reading"
    EXTERNAL_SOURCE = "external_source"


#: Classes whose product is not something the picture shows. Neither can ever settle a `measurable`
#: demand — `semantic_read` produces `Resource.READING`, which no actuator consumes, and `sourced`
#: is walled in `epistemics.py`. Named here so the graph can say so before anything is chosen.
NON_MEASURING_CLASSES = frozenset({CapabilityClass.SEMANTIC_READING, CapabilityClass.EXTERNAL_SOURCE})


class GroundForm(str, Enum):
    """The representation an observable's answer would land in. Candidate, never manufactured."""
    REGION = "region"
    FRAME = "frame"
    FIELD = "field"
    PATH = "path"
    RELATION = "relation"


class ReadingBlockKind(str, Enum):
    """The structure inside an abundant reading, so it can be pointed AT rather than re-parsed."""
    PART = "part"
    ORGANIZATION = "organization"
    COMPARISON = "comparison"
    HISTORICAL_ASSOCIATION = "historical_association"
    TENSION = "tension"
    HYPOTHESIS = "hypothesis"


class DecisionKind(str, Enum):
    """The forks this lane can detect. Lane B owns the interaction contract; these are CANDIDATES —
    a compiler saying "a person's answer here would change the rest", not a session pausing."""
    CHOOSE_OPERATIONALIZATION = "choose_operationalization"
    CHOOSE_IMAGE_SCOPE = "choose_image_scope"
    RESOLVE_AMBIGUOUS_TERM = "resolve_ambiguous_term"
    CONFIRM_AUTHOR_EXCLUSIVE_ACT = "confirm_author_exclusive_act"


class CompilerRefusalKind(str, Enum):
    """Why something a model produced did not become part of the graph.

    Refusals are KEPT, for HARNESS-001A's reason: how often a model invents a capability is the
    only observable that says whether to trust it, and a silently dropped invention is unobservable.
    """
    UNKNOWN_CLAIM_KIND = "unknown_claim_kind"
    UNKNOWN_CAPABILITY_CLASS = "unknown_capability_class"
    UNKNOWN_GROUND_FORM = "unknown_ground_form"
    UNKNOWN_EDGE_KIND = "unknown_edge_kind"
    UNKNOWN_DEMAND_KIND = "unknown_demand_kind"
    UNKNOWN_READING_BLOCK_KIND = "unknown_reading_block_kind"
    UNKNOWN_SOURCE_TYPE = "unknown_source_type"
    UNKNOWN_DECISION_KIND = "unknown_decision_kind"
    UNKNOWN_CLAIM_STATUS = "unknown_claim_status"
    GEOMETRY_IN_A_READING = "geometry_in_a_reading"
    MEASURED_STATUS_CLAIMED = "measured_status_claimed"
    IMAGE_SCOPE_CORRECTED = "image_scope_corrected"
    DANGLING_REFERENCE = "dangling_reference"
    INFERENCE_WITHOUT_PARENT = "inference_without_parent"
    UNANCHORED_CLAIM = "unanchored_claim"
    REMAINDER_CLAIMED_MEASURABLE = "remainder_claimed_measurable"
    SOURCED_CLAIM_ASKED_OF_AN_ORGAN = "sourced_claim_asked_of_an_organ"
    UNPARSEABLE_MODEL_OUTPUT = "unparseable_model_output"
    COMPILER_UNAVAILABLE = "compiler_unavailable"
    READING_UNAVAILABLE = "reading_unavailable"

    # ── v2: the dissolution refusals ──
    UNKNOWN_ATOM_KIND = "unknown_atom_kind"
    UNKNOWN_DISPOSITION = "unknown_disposition"
    UNANCHORED_ATOM = "unanchored_atom"
    ATOM_SOURCE_NOT_IN_LEDGER = "atom_source_not_in_ledger"
    SOURCE_UNIT_UNCOVERED = "source_unit_uncovered"
    SOURCE_UNIT_DOUBLE_COVERED = "source_unit_double_covered"
    USER_STATEMENT_REATTRIBUTED = "user_statement_reattributed"
    ATOM_INVENTED_VISUAL_CONTENT = "atom_invented_visual_content"
    DUPLICATE_POINTS_AT_ITSELF = "duplicate_points_at_itself"
    PASS_UNAVAILABLE = "pass_unavailable"
    REPAIR_BUDGET_SPENT = "repair_budget_spent"

    # ── HARNESS-003E: the cross-batch reconciliation ──
    #: A claim the reconciliation added whose parents all come from one batch. That batch had the
    #: material in front of it and did not build the claim, so admitting it here is the pass making
    #: an ordinary claim with no atoms behind it rather than finding one that crosses a boundary.
    RECONCILIATION_ADDED_LOCAL_CONTENT = "reconciliation_added_local_content"


class SourceUnitKind(str, Enum):
    """Where a piece of source prose came from. Two, and the difference is a WARRANT.

    A prompt clause is something the person is answerable for. A reading block is something a vision
    model proposed. Merging them would let the dissector attribute the person's own hypothesis to a
    machine — the one error nothing downstream can detect, because a model observation is exactly
    what the rest of the graph is made of.
    """
    PROMPT_CLAUSE = "prompt_clause"
    READING_BLOCK = "reading_block"


class AtomKind(str, Enum):
    """What a source unit SAYS. Nine, and deliberately not `ClaimKind`.

    A claim kind types what the graph asserts and carries the demand table with it. An atom kind
    types what somebody said, before anything has decided whether it is investigable. They meet in
    exactly one place — the contract's `atom_kind_to_claim_kind` default — so a change to either
    vocabulary is a change a reader can see rather than a coincidence of two enums drifting.

    `VISUAL_QUALITY` is the distinction the rehearsal turned on and `ClaimKind` has no word for: how
    a thing APPEARS is not a property of the thing, and flattening the two loses the whole question
    of whether appearance can be measured.
    """
    ENTITY = "entity"
    VISUAL_QUALITY = "visual_quality"
    RELATION = "relation"
    COMPARISON = "comparison"
    INTERPRETATION = "interpretation"
    HISTORICAL_OR_SOURCED = "historical_or_sourced"
    CAUSAL_HYPOTHESIS = "causal_hypothesis"
    GENERATIVE_PROPOSAL = "generative_proposal"
    UNKNOWN = "unknown"


class AtomAuthor(str, Enum):
    """Who said it. `USER` is frozen onto any atom anchored to a prompt clause."""
    USER = "user"
    SCENE_THEORIST = "scene_theorist"
    SEMANTIC_DISSECTOR = "semantic_dissector"


class DispositionKind(str, Enum):
    """What happened to one source unit. Exactly one per unit, and the four are not degrees.

    `SEMANTIC_REMAINDER` is content nothing MEASURES; `REFUSED` is content nothing PROCESSED. A
    ledger that used one word for both would report a dissector failure as an epistemic limit, which
    is the most flattering possible mistake and therefore the one to make impossible.
    """
    REPRESENTED_BY = "represented_by"
    DUPLICATE_OF = "duplicate_of"
    SEMANTIC_REMAINDER = "semantic_remainder"
    REFUSED = "refused"


class DissolutionPass(str, Enum):
    """The six steps a v2 compilation runs, named so a receipt can be attributed to one."""
    SOURCE_LEDGER = "source_ledger"
    SEMANTIC_DISSECTOR = "semantic_dissector"
    RELATION_ARCHITECT = "relation_architect"
    EPISTEMIC_OPERATIONALIZER = "epistemic_operationalizer"
    COVERAGE_AUDIT = "coverage_audit"
    TARGETED_REPAIR = "targeted_repair"


class PassOutcome(str, Enum):
    """How a pass ended. Eight, and `COMPLETED` is the only one that means what it looks like.

    HARNESS-002R's central failure in one enum: a parsed response is not a successful one. A
    truncated prefix that happens to close its JSON, a graph whose references dangle, and a ledger
    with an uncovered paragraph all parse. Each gets its own word.
    """
    COMPLETED = "completed"
    THIN = "thin"
    TRUNCATED = "truncated"
    COVERAGE_FAILED = "coverage_failed"
    EMPTY = "empty"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


#: Outcomes that mean the pass did not deliver what it was for. `THIN` is in here: coverage without
#: relations is the exact shape the rehearsal produced, and calling it a success is what made the
#: rehearsal's result unreadable.
UNDERPERFORMING_OUTCOMES: Tuple[PassOutcome, ...] = (
    PassOutcome.THIN, PassOutcome.TRUNCATED, PassOutcome.COVERAGE_FAILED, PassOutcome.EMPTY,
    PassOutcome.REFUSED, PassOutcome.UNAVAILABLE, PassOutcome.ERROR,
)


class BatchBoundaryReason(str, Enum):
    """Why one batch stopped where it did. HARNESS-003E.

    A batch boundary is where a relation becomes hard to see, so every boundary owes a reason. The
    four are not degrees: `ALLOWANCE_REACHED` is the sizing working, `AFFINITY_BOUNDARY` is a
    deliberate seam kept at a source or image edge where a relation is least likely to cross,
    `LAST_ITEMS` is the tail, and `OVERSIZED_ITEM` is a single item no request could carry — the one
    case where the plan has to report a limit rather than a partition.
    """
    ALLOWANCE_REACHED = "allowance_reached"
    AFFINITY_BOUNDARY = "affinity_boundary"
    LAST_ITEMS = "last_items"
    OVERSIZED_ITEM = "oversized_item"


class ItemDispositionKind(str, Enum):
    """What became of one atom or one claim inside a batched pass. HARNESS-003E.

    The coverage ledger's argument, one layer along. `DispositionKind` answers it for a source unit;
    this answers it for the objects the batched passes consume, because a pass that quietly used
    half its input and called itself complete is the shape the whole lane exists to prevent.

    Silence is not one of these. A claim nobody operationalized is `NOT_INVESTIGATED` with a reason,
    which is a decision; a claim missing from this list is a claim the pass lost.
    """
    USED = "used"
    ORPHAN = "orphan"
    REFUSED = "refused"
    OPERATIONALIZED = "operationalized"
    SEMANTIC_REMAINDER = "semantic_remainder"
    NOT_INVESTIGATED = "not_investigated"


#: HARNESS-003F. The version stamped on every `ExecutionScopeRecord`. Its own version rather than
#: the graph's, and for the reason `BATCH_PLAN_VERSION` gives one object along: the scope is a
#: TEMPORARY contract, it is the thing most likely to be withdrawn or widened, and a reader has to
#: be able to tell a run scoped under one rule from a run scoped under another without inferring it
#: from the graph around it.
EXECUTION_SCOPE_VERSION = "inquiry-execution-scope.v1"

#: The one purpose this scope may be declared for. A string rather than a free field because a
#: bounded run whose stated purpose could be anything is a bounded run nobody can audit — and this
#: one exists to test that the vertical FLOWS, never to produce a better-looking answer.
SCOPE_PURPOSE_VERTICAL_FLOW = "live_vertical_flow_rehearsal"


class ExecutionScope(str, Enum):
    """How much of the inquiry this run was allowed to investigate. HARNESS-003F.

    `FULL` is the existing behaviour and the default, and nothing about it changes: no limit, no
    selection, no record beyond the one that says so.

    `VERTICAL_SLICE` is TEMPORARY. It exists because the account's per-minute allowance is an order
    of magnitude under what one pass of this council needs at four-image scale (003E), so the whole
    chain — prompt to answer — has never once run end to end on live models. A slice makes that
    testable. It does not make the result a reading: `full_coverage` is False by law, every deferred
    unit is on the record with a reason, and the badge follows the session into every terminal
    state.
    """
    FULL = "full"
    VERTICAL_SLICE = "vertical_slice"


#: What a deferred source unit's `CoverageDisposition.reason` says, verbatim. One string, because a
#: reason that varied by call site would let one of them drift into sounding like a finding about
#: the images.
SCOPE_DEFERRED_REASON = ("temporary vertical-slice rehearsal scope; not investigated and not "
                         "evidence of absence")


class CallTopology(str, Enum):
    """How the reading was actually obtained. Recorded because it changes what the reading IS:
    three separate per-image calls plus a synthesis is not a joint view of three pictures, and a
    receipt that said `single_joint_call` for it would be describing a comparison nobody made."""
    SINGLE_JOINT_CALL = "single_joint_call"
    PER_IMAGE_THEN_SYNTHESIS = "per_image_then_synthesis"
    TEXT_ONLY = "text_only"
    REPLAY = "replay"
    UNAVAILABLE = "unavailable"


class _Strict(BaseModel):
    """Unknown fields are refused, not ignored."""
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


# ── the parts ────────────────────────────────────────────────────────────────

class ImageRef(_Strict):
    """One selected image, named the way the corpus names it. No pixels travel in this object."""
    post_id: str
    title: str = ""
    image_ref: str = Field(default="", description="url or storage ref the transport accepts")
    note: str = ""


class SourcePointer(_Strict):
    """Where a claim's words came from, exactly enough to go back and check.

    `span` is character offsets into whatever `source_id` names — the prompt, a reading block. It is
    optional because a model asked for offsets will confidently invent them; `text` is the load
    bearing half and is verified against the source by the parser where the source is available.
    """
    source_type: SourceType
    source_id: str = Field(..., description="'prompt', a frame field name, or a reading block id")
    text: str = Field(default="", description="the words, verbatim from the source")
    span: Optional[Tuple[int, int]] = None
    sentence_index: Optional[int] = None
    image_refs: List[str] = Field(default_factory=list)


class ReadingBlock(_Strict):
    """One structured piece of the provisional reading, addressable so a claim can point at it."""
    block_id: str
    kind: ReadingBlockKind
    text: str
    image_refs: List[str] = Field(default_factory=list)


class ModelReceipt(_Strict):
    """Everything needed to say what actually answered, and whether it answered at all.

    `raw_response_sha256` is here rather than the raw text: the text is quarantined until strict
    parsing succeeds and is not carried into the graph, but a hash lets a replay prove it received
    the same bytes. `call_count` and `call_topology` together are the honesty of the reading.
    """
    role: str
    model: Optional[str] = None
    provider: Optional[str] = None
    prompt_sha256: str = ""
    image_refs: List[str] = Field(default_factory=list)
    image_sha256: Dict[str, str] = Field(default_factory=dict)
    requested_at: Optional[str] = Field(
        default=None, description="handed in by the caller; this layer owns no clock")
    raw_response_sha256: List[str] = Field(default_factory=list)
    parsed: bool = False
    refusal: Optional[str] = None
    call_count: int = 0
    call_topology: CallTopology = CallTopology.UNAVAILABLE
    #: Why the provider stopped generating — `stop`, `length`, or whatever it said. TYPED, because
    #: HARNESS-003B asked for it by name: its `outcomes.py` consults `receipt.finish_reason` FIRST
    #: and falls back to reading a `finish_reason: ` note only because no such field existed.
    #:
    #: A note is prose that happens to be machine-written; a field cannot be reworded by somebody
    #: improving a sentence. The difference decides whether a truncated reading is reported as a
    #: short one, which is the exact failure 002R's rehearsal produced — so the better route should
    #: not depend on nobody touching a string.
    #:
    #: `None` means nothing was asked, and it is NOT `""`: an unavailable call reports no finish
    #: reason because there was no call, and a route that read the empty string as "stopped
    #: normally" would report an unchecked stage as a verified one.
    #:
    #: A LIST would be wrong here. A `ModelReceipt` covers one logical call — the theorist's sweep
    #: counts its own truncated calls in `truncated_calls`, which is the producer-attribute route
    #: 003B reads for exactly that case. The per-pass, many-call receipt is `PassReceipt`, and it
    #: carries `finish_reasons` plural.
    finish_reason: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class SceneReading(_Strict):
    """The abundant provisional reading. Interpretive at strongest, and it says so in a field.

    `status` and `source` are frozen rather than defaulted. A reading whose status could be set by
    its producer is one a producer will eventually set to something stronger.
    """
    text: str = ""
    status: str = Field(default="interpretive", frozen=True)
    source: str = Field(default="scene_theorist", frozen=True)
    blocks: List[ReadingBlock] = Field(default_factory=list)
    image_refs: List[ImageRef] = Field(default_factory=list)
    provenance: ModelReceipt

    @field_validator("status")
    @classmethod
    def _interpretive_at_strongest(cls, value: str) -> str:
        if value != "interpretive":
            raise ValueError(
                f"a scene reading is {value!r}? It is `interpretive` and nothing else. The theorist "
                f"looks at pixels and is still a thinker: it authors no geometry and measures "
                f"nothing, so no stronger status is available to it.")
        return value

    @field_validator("source")
    @classmethod
    def _one_source(cls, value: str) -> str:
        if value != "scene_theorist":
            raise ValueError("a scene reading is produced by the scene theorist role and no other")
        return value

    def block(self, block_id: str) -> Optional[ReadingBlock]:
        return next((b for b in self.blocks if b.block_id == block_id), None)


class ClaimNode(_Strict):
    """One atomic claim, typed, anchored, and asking for a kind of knowing.

    `subject` / `predicate` / `object_` are OPEN STRINGS and optional. They are a convenience for a
    consumer that wants to group claims, never a schema the model must satisfy — a compiler forced
    to triple-ise every sentence will triple-ise the ones that are not triples.
    """
    claim_id: str
    text: str
    claim_kind: ClaimKind
    subject: str = ""
    predicate: str = ""
    object_: str = Field(default="", alias="object")
    vocabulary: str = Field(default="", description="open: whose words these are, if named")
    sources: List[SourcePointer] = Field(default_factory=list)
    image_scope: ImageScope = ImageScope.CORPUS
    epistemic_demand: DemandKind = DemandKind.INTERPRETIVE
    status: ClaimStatus = ClaimStatus.INTERPRETIVE
    inferred_from: List[str] = Field(default_factory=list)
    #: v2. The atoms this claim was built from. Empty on a v1 graph and on a claim the architect
    #: declared as its own inference — `inferred_from` carries the parents in that case, and the two
    #: fields answer different questions: which ATOMS say this, and which CLAIMS it follows from.
    atom_refs: List[str] = Field(default_factory=list)
    note: str = ""

    model_config = ConfigDict(extra="forbid", populate_by_name=True,
                              protected_namespaces=())

    @model_validator(mode="after")
    def _anchored_and_honest(self) -> "ClaimNode":
        if not self.text.strip():
            raise ValueError("a claim with no text is not a claim")
        if not self.sources:
            raise ValueError(
                f"claim {self.claim_id} carries no source pointer. An unanchored claim is one "
                f"nobody said and nothing produced, and it reads exactly like the others. A claim "
                f"the compiler derived declares `compiler_inference` and names its parents.")
        if all(s.source_type is SourceType.COMPILER_INFERENCE for s in self.sources) \
                and not self.inferred_from:
            raise ValueError(
                f"claim {self.claim_id} is a compiler inference that names no parent claim. An "
                f"inference with no parents is an assertion wearing an inference's clothes.")

        forbidden = _FORBIDDEN_DEMANDS.get(self.claim_kind)
        if forbidden and self.epistemic_demand in forbidden:
            raise ValueError(
                f"claim {self.claim_id} is {self.claim_kind.value!r} and demands "
                f"{self.epistemic_demand.value!r}: {_FORBIDDEN_DEMANDS_WHY[self.claim_kind]}")
        required = _REQUIRED_DEMANDS.get(self.claim_kind)
        if required and self.epistemic_demand not in required:
            raise ValueError(
                f"claim {self.claim_id} is {self.claim_kind.value!r} and must demand one of "
                f"{sorted(d.value for d in required)}, not {self.epistemic_demand.value!r}: "
                f"{_REQUIRED_DEMANDS_WHY[self.claim_kind]}")
        if self.claim_kind is ClaimKind.COMPARISON and self.image_scope is ImageScope.ONE_IMAGE:
            raise ValueError(
                f"claim {self.claim_id} is a comparison scoped to one image. A comparison across "
                f"images is not available from one of them; typed from one, it is a corpus "
                f"tendency asserted from a single observation.")
        return self


#: Demand constraints, keyed by claim kind. Data rather than a chain of `if`s because each row is a
#: rule somebody will want to relax, and a table makes relaxing one a visible edit.
_FORBIDDEN_DEMANDS: Dict[ClaimKind, frozenset] = {
    ClaimKind.HISTORICAL_OR_SOURCED: frozenset({DemandKind.MEASURABLE}),
    ClaimKind.INTERPRETATION: frozenset({DemandKind.MEASURABLE}),
    ClaimKind.CAUSAL_HYPOTHESIS: frozenset({DemandKind.MEASURABLE}),
}

_FORBIDDEN_DEMANDS_WHY: Dict[ClaimKind, str] = {
    ClaimKind.HISTORICAL_OR_SOURCED:
        "its warrant lies outside the picture. `epistemics.py` walls `sourced` for this reason, and "
        "the wall is applied here one level up — on the claim, before any instrument is chosen.",
    ClaimKind.INTERPRETATION:
        "an interpretation does not become measurable because measurements contribute to it. That "
        "promotion is the exact failure HARNESS-001A's semantic remainder exists to prevent.",
    ClaimKind.CAUSAL_HYPOTHESIS:
        "the CONSEQUENCES of a because may be observable and belong on their own claims. The link "
        "itself is not something an instrument returns.",
}

_REQUIRED_DEMANDS: Dict[ClaimKind, frozenset] = {
    ClaimKind.GENERATIVE_RULE: frozenset({DemandKind.IMAGINED, DemandKind.UNRESOLVED}),
}

_REQUIRED_DEMANDS_WHY: Dict[ClaimKind, str] = {
    ClaimKind.GENERATIVE_RULE:
        "a rule for making what does not exist has nothing to measure and nothing to cite. "
        "HARNESS-001B declined to give `imagined` an EpistemicStatus for exactly this reason.",
}


class ClaimEdge(_Strict):
    """One typed relation between two claims. Both ends are checked against the graph."""
    edge_id: str
    kind: ClaimEdgeKind
    from_claim: str
    to_claim: str
    why: str = ""

    @model_validator(mode="after")
    def _not_a_self_loop(self) -> "ClaimEdge":
        if self.from_claim == self.to_claim:
            raise ValueError(f"edge {self.edge_id} relates {self.from_claim} to itself. A claim "
                             f"that supports itself is the shape of a graph that never bottoms out.")
        return self


class OperationalAlternative(_Strict):
    """One way of making a claim observable, where more than one honest way exists.

    Doubles as a decision OPTION — Lane B's `DecisionRequest.options` is `{option_id, label,
    consequence, recommended}`, which this is a superset of. One object rather than two nearly
    identical ones, because the alternative a compiler emitted and the option a person is shown must
    not be able to disagree about what the choice was.
    """
    alternative_id: str
    label: str
    consequence: str = ""
    capability_classes: List[CapabilityClass] = Field(default_factory=list)
    ground_forms: List[GroundForm] = Field(default_factory=list)
    description: str = ""
    recommended: bool = False


class ObservableSpec(_Strict):
    """What would have to become observable for one claim to gain support.

    It names a capability CLASS and never an implementation. `remains_interpretive` is the field
    that stops this object from being a promise: it says, in advance, what is still a reading even
    if every requested measurement comes back exactly as hoped.
    """
    observable_id: str
    claim_id: str
    observable_kind: str = Field(..., description="open: 'dominant extent', 'radial distribution'")
    targets: List[str] = Field(default_factory=list, description="open target descriptions")
    image_scope: ImageScope = ImageScope.CORPUS
    capability_classes: List[CapabilityClass] = Field(default_factory=list)
    ground_forms: List[GroundForm] = Field(default_factory=list)
    success_when: str = ""
    ambiguous_when: str = ""
    refused_when: str = ""
    remains_interpretive: str = ""
    alternatives: List[OperationalAlternative] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="after")
    def _asks_for_something(self) -> "ObservableSpec":
        if not self.observable_kind.strip():
            raise ValueError(f"observable {self.observable_id} names no observable kind")
        if not self.capability_classes:
            raise ValueError(
                f"observable {self.observable_id} requests no capability class. An observable that "
                f"names no class cannot be brokered, cannot be reported as a gap, and would sit in "
                f"the graph looking like work somebody had scoped.")
        return self


class DecisionCandidate(_Strict):
    """A fork where a person's answer would change the rest of the inquiry.

    A CANDIDATE. Lane B decides whether the session actually pauses; this lane only detects that the
    choice is material. Uncertainty alone is not a fork — `why_now` has to say what changes.
    """
    decision_id: str
    kind: DecisionKind
    question: str
    why_now: str
    affected_refs: List[str] = Field(default_factory=list)
    options: List[OperationalAlternative] = Field(default_factory=list)
    allow_free_text: bool = True
    blocking: bool = False

    @model_validator(mode="after")
    def _a_fork_has_branches(self) -> "DecisionCandidate":
        if len(self.options) < 2 and self.kind is not DecisionKind.CONFIRM_AUTHOR_EXCLUSIVE_ACT:
            raise ValueError(
                f"decision {self.decision_id} offers {len(self.options)} option(s). A fork with one "
                f"branch is a notification; asking about it trains a person to click through.")
        if not self.why_now.strip():
            raise ValueError(
                f"decision {self.decision_id} does not say what changes downstream. 'The system is "
                f"uncertain' is not a reason to interrupt somebody.")
        return self


class SemanticRemainderItem(_Strict):
    """Meaning the requested measurements will not exhaust, even if every one of them succeeds.

    `contributing_capability_classes` is the honest half: naming what DOES bear on a term is what
    makes refusing to call it measurable a considered position rather than a shrug.
    """
    term: str
    why: str
    contributing_capability_classes: List[CapabilityClass] = Field(default_factory=list)
    claim_refs: List[str] = Field(default_factory=list)


class CompilerRefusal(_Strict):
    """Something a model produced that did not become part of the graph, and why."""
    refusal_id: str
    kind: CompilerRefusalKind
    what: str
    why: str
    detail: List[str] = Field(default_factory=list)


# ── v2: the source ledger ────────────────────────────────────────────────────

class SourceUnit(_Strict):
    """One addressable piece of source prose, and the exact words it consists of.

    THE SPAN IS COMPUTED, NEVER TAKEN. A prompt clause carries the character offsets it occupies in
    the verbatim prompt, found by the splitter in the prompt itself. No model is asked for an offset
    — an invented one renders in a UI as a highlight over words the person did not write. A quote
    that does not resolve keeps `span=None` and says so in `note`.
    """
    source_unit_id: str
    kind: SourceUnitKind
    #: `prompt` for a clause; the reading block's own id for a block. Never an index: a theorist that
    #: emits its blocks in a different order emits the same blocks.
    source_ref: str
    exact_quote: str = Field(..., description="the words, byte for byte from the source")
    span: Optional[Tuple[int, int]] = None
    image_refs: List[str] = Field(default_factory=list)
    block_kind: str = Field(default="", description="for a reading block: the theorist's own kind")
    ordinal: int = Field(default=0, description="reading order, for display only — never an id")
    note: str = ""

    @field_validator("exact_quote")
    @classmethod
    def _a_unit_has_words(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a source unit with no text is a pointer at nothing")
        return value

    @property
    def is_user_authored(self) -> bool:
        return self.kind is SourceUnitKind.PROMPT_CLAUSE


class SemanticAtom(_Strict):
    """One semantic unit, anchored to the source that says it.

    An atom is smaller than a claim and larger than a word. `this edge is abrupt` and `that makes
    the material read as hard` are two atoms: one is how something looks, the other is what that
    does to a reader, and a pipeline that fused them could never ask whether only the first is
    observable.

    `author` is FROZEN to the user for anything anchored to a prompt clause. The validator does it
    rather than the dissector, because an adapter can be edited and a validator has to be argued
    with — and this is the one attribution error nothing downstream could detect.
    """
    atom_id: str
    text: str
    unit_kind: AtomKind
    source_unit_ids: List[str] = Field(default_factory=list)
    quotes: List[str] = Field(default_factory=list, description="verbatim from those units")
    #: Open strings, always. The closed sets are shapes; the subjects are the world.
    subject: str = ""
    predicate: str = ""
    object_: str = Field(default="", alias="object")
    image_scope: ImageScope = ImageScope.CORPUS
    image_refs: List[str] = Field(default_factory=list)
    author: AtomAuthor = AtomAuthor.SEMANTIC_DISSECTOR
    #: The strongest thing this atom could ever be. Never above `interpretive` — a dissector reads
    #: prose about pixels and is two removes from the pixels.
    epistemic_ceiling: str = "interpretive"
    note: str = ""
    provenance: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("text")
    @classmethod
    def _an_atom_says_something(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("an atom with no text is not a unit of anything")
        return value

    @field_validator("epistemic_ceiling")
    @classmethod
    def _nothing_above_interpretive(cls, value: str) -> str:
        if value in FORBIDDEN_INITIAL_STATUSES:
            raise ValueError(
                f"an atom may not declare a {value!r} ceiling. Nothing has run, and a dissector "
                f"reads prose about pixels — it is two removes from the pixels.")
        return value

    @model_validator(mode="after")
    def _an_atom_is_anchored(self) -> "SemanticAtom":
        if not self.source_unit_ids:
            raise ValueError(
                f"atom {self.atom_id} names no source unit. An unanchored atom is prose the "
                f"dissector wrote, and it reads exactly like one it found.")
        return self


class CoverageDisposition(_Strict):
    """What happened to exactly one source unit.

    The whole point of the ledger. Zero dispositions for a unit means a paragraph vanished and
    nothing says so; two means the graph tells two stories about the same words and a reader cannot
    tell which one is the record.
    """
    coverage_id: str
    source_unit_id: str
    disposition: DispositionKind
    refs: List[str] = Field(default_factory=list,
                            description="atom ids for represented_by; a source unit id for duplicate_of")
    reason: str = ""

    @model_validator(mode="after")
    def _a_disposition_carries_what_it_claims(self) -> "CoverageDisposition":
        if self.disposition is DispositionKind.REPRESENTED_BY and not self.refs:
            raise ValueError(
                f"coverage {self.coverage_id} says the unit is represented and names no atom. "
                f"'Represented by nothing' is the uncovered case wearing the covered case's name.")
        if self.disposition is DispositionKind.DUPLICATE_OF:
            if len(self.refs) != 1:
                raise ValueError(
                    f"coverage {self.coverage_id} is a duplicate of {len(self.refs)} units. A "
                    f"duplicate names exactly one original.")
            if self.refs[0] == self.source_unit_id:
                raise ValueError(
                    f"coverage {self.coverage_id} says a source unit duplicates itself, which "
                    f"removes it from the ledger while looking like an entry in it.")
        if self.disposition in (DispositionKind.SEMANTIC_REMAINDER, DispositionKind.REFUSED) \
                and not self.reason.strip():
            raise ValueError(
                f"coverage {self.coverage_id} is {self.disposition.value!r} with no reason. The "
                f"reason is the only thing separating an epistemic limit from a pass that failed.")
        return self


class CapacityWaitRecord(_Strict):
    """One provider capacity refusal, and the pause that followed it — or the pause that did not.

    HARNESS-003D. Lane A's fifth live run was rate-limited out of the relation architect and the
    record could say only that a pass had `error`ed with a `429`. A wait is a fact about the ACCOUNT
    rather than about the prompt, and a run whose elapsed time is mostly waiting is not a slow run —
    it is a run inside a smaller allowance than the work needs. Those two read alike in a latency
    column and their repairs are opposite, so the waiting is recorded apart from the thinking.

    `taken=False` is a refusal the pacer did NOT wait on, because the declared wall-clock budget or
    the attempt bound stopped it. Kept rather than dropped: giving up because you ran out of time
    and giving up because the provider kept refusing are different reports.
    """
    attempt: int = Field(..., ge=1, description="which transport attempt was refused")
    seconds: float = Field(..., ge=0.0, description="how long was waited, or would have been")
    #: `provider_retry_after` | `provider_reset_header` | `provider_message` | `declared_interval`
    #: for a wait, and `budget_exhausted` | `attempts_exhausted` for a refusal nothing waited on.
    source: str
    detail: str = ""
    taken: bool = True


#: The version stamped on every `BatchPlanRecord`. Its own version rather than the graph's: the plan
#: is the object a later lane is most likely to extend (a real tokenizer, a different provider), and
#: a reader has to be able to tell a plan written under one sizing rule from one written under
#: another without inferring it from the graph around it.
BATCH_PLAN_VERSION = "semantic-batch-plan.v1"


class BatchAssignment(_Strict):
    """One request's worth of work, sized before anything was sent. HARNESS-003E.

    `primary_refs` and `context_refs` are the whole design in two fields. An item is PRIMARY in
    exactly one batch — that is what makes "every atom was locally considered" a countable fact
    rather than a hope — and may appear as CONTEXT in others, where the model may read it and may
    not produce output for it. Collapsing the two would let one claim be operationalized three times
    from three neighbourhoods and report three observables as three findings.
    """
    batch_id: str
    index: int = Field(..., ge=1)
    total: int = Field(..., ge=1)
    primary_refs: List[str] = Field(default_factory=list)
    context_refs: List[str] = Field(default_factory=list)
    #: What this module's conservative bound said the whole request would cost, and what was
    #: reserved for the answer. Both recorded because the sum is what the provider counts.
    estimated_prompt_tokens: int = Field(default=0, ge=0)
    requested_completion_tokens: int = Field(default=0, ge=0)
    allowance_tokens: int = Field(default=0, ge=0)
    boundary_reason: BatchBoundaryReason = BatchBoundaryReason.LAST_ITEMS
    #: True where a single item exceeds everything one request can carry. The batch is NOT sent —
    #: 413 is a request that cannot be sent at any moment, and discovering that from the provider
    #: costs the allowance a round trip to learn what arithmetic already knew.
    sendable: bool = True
    note: str = ""

    @property
    def estimated_total_tokens(self) -> int:
        """What the provider counts against the per-minute allowance: the prompt AND the reservation.

        Lane A learned this the expensive way — raising `max_completion_tokens` from 4096 to 8192
        made every request fail with `413`, because a completion budget is charged whether or not
        the model spends it.
        """
        return self.estimated_prompt_tokens + self.requested_completion_tokens

    @model_validator(mode="after")
    def _an_item_is_primary_or_context_and_never_both(self) -> "BatchAssignment":
        overlap = sorted(set(self.primary_refs) & set(self.context_refs))
        if overlap:
            raise ValueError(
                f"batch {self.batch_id} lists {len(overlap)} ref(s) as both primary and context: "
                f"{overlap[:5]}. An item the model may answer for and may not answer for is one the "
                f"parser cannot decide about.")
        if self.index > self.total:
            raise ValueError(f"batch {self.batch_id} is {self.index} of {self.total}")
        return self


class ComparisonPair(_Strict):
    """Two batches, and whether anything ever looked at them together. HARNESS-003E.

    THE COVERAGE MATRIX IS THIS LIST. Local batching alone makes a cross-batch relation structurally
    invisible — the model is never shown both sides — so the claim "this pass looked for relations"
    is only true of pairs that co-occurred in some reconciliation request. An unexamined pair is a
    relation nobody looked for, and it is named rather than rounded off.
    """
    left_batch_id: str
    right_batch_id: str
    #: The reconciliation round both groups appeared in, or empty where none did.
    round_id: str = ""
    examined: bool = False
    #: Why it was not examined, when it was not. Empty on an examined pair.
    reason: str = ""

    @model_validator(mode="after")
    def _examined_means_a_round_can_be_named(self) -> "ComparisonPair":
        if self.left_batch_id == self.right_batch_id:
            raise ValueError("a batch pair compares a batch with itself, which examines nothing")
        if self.examined and not self.round_id.strip():
            raise ValueError(
                f"the pair {self.left_batch_id}/{self.right_batch_id} says it was examined and "
                f"names no round. A comparison nobody can point at did not happen.")
        if not self.examined and not self.reason.strip():
            raise ValueError(
                f"the pair {self.left_batch_id}/{self.right_batch_id} was not examined and gives no "
                f"reason. An unexamined pair with no reason reads as an oversight rather than a "
                f"reported limit.")
        return self


class ReconciliationRound(_Strict):
    """One cross-batch request, and which groups of claim cards it actually held. HARNESS-003E."""
    round_id: str
    index: int = Field(..., ge=1)
    total: int = Field(..., ge=1)
    #: The batch ids whose claim cards co-occurred in this request. Two or more, always: a round
    #: over one group compares nothing.
    group_ids: List[str] = Field(default_factory=list)
    estimated_prompt_tokens: int = Field(default=0, ge=0)
    outcome: PassOutcome = PassOutcome.COMPLETED
    added_edges: int = Field(default=0, ge=0)
    added_claims: int = Field(default=0, ge=0)
    duplicate_claims: int = Field(default=0, ge=0)
    detail: str = ""

    @model_validator(mode="after")
    def _a_round_compares_something(self) -> "ReconciliationRound":
        if len(set(self.group_ids)) < 2:
            raise ValueError(
                f"reconciliation round {self.round_id} carries {len(set(self.group_ids))} group(s). "
                f"A round over one group is a second look at material that was already together.")
        return self


class DuplicateClaim(_Strict):
    """One claim the reconciliation identified as another's duplicate. HARNESS-003E.

    THE MAPPING IS AUDITABLE OR THE MERGE IS A DELETION. Merging two claims removes one id from the
    graph, and every edge, observable and remainder item that named it has to be rewritten — so the
    record has to say which id went, which one it went into, and which round decided.
    """
    claim_id: str = Field(..., description="the id that was merged away")
    canonical_id: str = Field(..., description="the id it was merged into")
    round_id: str = ""
    why: str = ""

    @model_validator(mode="after")
    def _a_claim_does_not_duplicate_itself(self) -> "DuplicateClaim":
        if self.claim_id == self.canonical_id:
            raise ValueError(
                f"claim {self.claim_id} is said to duplicate itself, which removes it from the "
                f"graph while looking like an entry in it.")
        return self


class ItemDisposition(_Strict):
    """What became of one atom or one claim. HARNESS-003E.

    `reason` is required exactly where the disposition is a JUDGEMENT rather than a fact:
    `used` and `orphan` are read off the output, and `refused` / `not_investigated` are decisions
    somebody made — the same rule `CoverageDisposition` applies one layer up.
    """
    ref: str
    disposition: ItemDispositionKind
    batch_id: str = ""
    reason: str = ""

    @model_validator(mode="after")
    def _a_judgement_carries_its_reason(self) -> "ItemDisposition":
        if self.disposition in (ItemDispositionKind.REFUSED,
                                ItemDispositionKind.NOT_INVESTIGATED) and not self.reason.strip():
            raise ValueError(
                f"{self.ref} is {self.disposition.value!r} with no reason. The reason is the only "
                f"thing separating a decision from a pass that lost track of it.")
        return self


class BatchPlanRecord(_Strict):
    """How a pass was cut into sendable requests, and what that cost in coverage. HARNESS-003E.

    A VERSIONED OBJECT rather than a note, because the fact it carries — "every atom was considered,
    and these four batch pairs were never compared" — is the fact a reader most needs and the one
    prose is worst at holding. It is content-derived and replay-stable for the same reason every id
    in this package is: a plan that renumbered itself between two runs of the same input would make
    a replay a comparison of two different partitions.
    """
    plan_version: str = BATCH_PLAN_VERSION
    plan_id: str
    pass_name: DissolutionPass
    #: What was partitioned: `semantic_atom` or `claim`. Not an enum — a later pass may batch
    #: something else, and inventing a closed set for two members would make that a schema change.
    unit: str = ""
    total_items: int = Field(default=0, ge=0)
    batches: List[BatchAssignment] = Field(default_factory=list)
    #: HARNESS-003F. How many of those batches were actually put in front of the model.
    #:
    #: `None` on a pass that did not track it, and it is NOT `len(batches)`: a declared scope may
    #: permit fewer requests than the partition contains, and a plan whose only number was the
    #: partition size would report a bounded pass as a complete one. The batches nobody sent are
    #: still here, still primary for their items, and their items are `not_investigated` below.
    batches_sent: Optional[int] = None
    pairs: List[ComparisonPair] = Field(default_factory=list)
    rounds: List[ReconciliationRound] = Field(default_factory=list)
    dispositions: List[ItemDisposition] = Field(default_factory=list)
    duplicate_map: List[DuplicateClaim] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    @property
    def unexamined_pairs(self) -> List[ComparisonPair]:
        return [p for p in self.pairs if not p.examined]

    @property
    def pairs_examined(self) -> int:
        return sum(1 for p in self.pairs if p.examined)

    @property
    def unsendable_batches(self) -> List[BatchAssignment]:
        return [b for b in self.batches if not b.sendable]

    @property
    def every_item_is_primary_once(self) -> bool:
        primary = [r for b in self.batches for r in b.primary_refs]
        return len(primary) == len(set(primary)) == self.total_items

    @model_validator(mode="after")
    def _the_partition_is_a_partition(self) -> "BatchPlanRecord":
        primary = [r for b in self.batches for r in b.primary_refs]
        doubled = sorted({r for r in primary if primary.count(r) > 1})
        if doubled:
            raise ValueError(
                f"{len(doubled)} item(s) are primary in more than one batch: {doubled[:5]}. An item "
                f"answered for twice produces the same object twice and reports it as two findings.")
        known = {b.batch_id for b in self.batches}
        for pair in self.pairs:
            for side in (pair.left_batch_id, pair.right_batch_id):
                if side not in known:
                    raise ValueError(
                        f"the coverage matrix names batch {side!r}, which this plan does not "
                        f"contain. A matrix over batches that do not exist proves nothing.")
        rounds = {r.round_id for r in self.rounds}
        for pair in self.pairs:
            if pair.examined and pair.round_id not in rounds:
                raise ValueError(
                    f"the pair {pair.left_batch_id}/{pair.right_batch_id} names round "
                    f"{pair.round_id!r}, which this plan does not contain.")
        for entry in self.rounds:
            for group in entry.group_ids:
                if group not in known:
                    raise ValueError(
                        f"reconciliation round {entry.round_id} names group {group!r}, which is not "
                        f"a batch in this plan.")
        return self


class ScopeExclusion(_Strict):
    """One thing the scope did not investigate, and why. HARNESS-003F.

    A COUNT IS NOT A RECORD. 003E's whole argument about unexamined batch pairs applies here one
    layer up: an excluded source unit reported as "17 deferred" is a gap whose size a reader knows
    and whose location they do not. Every exclusion is named individually.
    """
    ref: str
    #: `source_unit` | `semantic_atom` | `claim`. Not an enum: the scope may one day defer something
    #: else, and inventing a closed set for three members would make that a schema change.
    kind: str = ""
    reason: str

    @field_validator("reason")
    @classmethod
    def _an_exclusion_carries_its_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "an exclusion with no reason reads as an oversight rather than a declared bound, "
                "which is the whole difference between a scoped run and a short one")
        return value


class ExecutionScopeRecord(_Strict):
    """What this run was allowed to look at, what it therefore did not, and that it knows. 003F.

    THE FIELD THIS OBJECT EXISTS FOR IS `full_coverage`, and the validator below is why it is an
    object rather than a note. A slice that could report complete coverage would be a smaller
    question wearing the larger question's answer — and every other honesty guard in this tree
    (`_a_fixture_is_never_evidence`, `_a_length_stop_is_truncated`, `_a_disposition_carries_what_it_claims`)
    is built the same way: the lie is made unrepresentable rather than merely discouraged.

    The batch counts are `allowed` and `sent` as a PAIR, and `allowed=None` means unlimited. A
    single "batches" number could not tell a run that was capped at one and sent one from a run that
    was uncapped and had one to send.
    """
    scope_version: str = EXECUTION_SCOPE_VERSION
    mode: ExecutionScope = ExecutionScope.FULL
    purpose: str = ""
    #: Which code chose. Named because the selection is the load-bearing act of a scoped run, and a
    #: later lane that changes how the choosing works must be visible in the record it wrote.
    selection_producer: str = ""
    #: The allowance the selection was sized against, in the provider's own unit. A scoped run whose
    #: record did not carry this could not be compared with the run that follows a tier change.
    allowance_tokens: int = Field(default=0, ge=0)

    selected_source_unit_ids: List[str] = Field(default_factory=list)
    deferred_source_unit_ids: List[str] = Field(default_factory=list)
    selected_atom_ids: List[str] = Field(default_factory=list)
    atoms_not_investigated: List[str] = Field(default_factory=list)
    selected_claim_ids: List[str] = Field(default_factory=list)
    claims_not_investigated: List[str] = Field(default_factory=list)

    #: `None` is unlimited, and it is not `0`. Zero permitted rounds is a real and deliberate
    #: configuration in this lane, so the two had to stop being the same value.
    relation_batches_allowed: Optional[int] = None
    relation_batches_sent: int = Field(default=0, ge=0)
    operationalizer_batches_allowed: Optional[int] = None
    operationalizer_batches_sent: int = Field(default=0, ge=0)
    reconciliation_rounds_allowed: Optional[int] = None
    reconciliation_rounds_sent: int = Field(default=0, ge=0)

    exclusions: List[ScopeExclusion] = Field(default_factory=list)
    full_coverage: bool = True
    notes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _a_slice_never_reports_full_coverage(self) -> "ExecutionScopeRecord":
        if self.mode is ExecutionScope.VERTICAL_SLICE:
            if self.full_coverage:
                raise ValueError(
                    "a vertical-slice run declares full coverage. It investigated a declared "
                    "subset; reporting that as a complete reading is the one thing this record "
                    "exists to make impossible.")
            if self.purpose != SCOPE_PURPOSE_VERTICAL_FLOW:
                raise ValueError(
                    f"a vertical-slice run declares purpose {self.purpose!r}. The only purpose "
                    f"this scope may be used for is {SCOPE_PURPOSE_VERTICAL_FLOW!r} — a bounded "
                    f"run whose stated purpose could be anything is one nobody can audit.")
        named = {e.ref for e in self.exclusions}
        missing = sorted(({*self.deferred_source_unit_ids, *self.atoms_not_investigated,
                           *self.claims_not_investigated}) - named)
        if missing:
            raise ValueError(
                f"{len(missing)} excluded item(s) carry no reason: {missing[:5]}. A count of what "
                f"was left out tells a reader the size of the gap and not where it is.")
        return self


class PassReceipt(_Strict):
    """What one pass of the council did, whether or not it produced anything.

    Separate from `ModelReceipt` because a pass is not always a model call: the source ledger and
    the coverage audit are deterministic, and giving them a model receipt with an empty model field
    would make two very different kinds of step look alike in the one list a reader scans.
    """
    pass_id: str
    pass_name: DissolutionPass
    outcome: PassOutcome
    model: Optional[str] = None
    provider: Optional[str] = None
    call_count: int = 0
    #: `stop`, `length`, or whatever the provider said. Empty when nothing was called.
    finish_reasons: List[str] = Field(default_factory=list)
    prompt_sha256: List[str] = Field(default_factory=list)
    raw_response_sha256: List[str] = Field(default_factory=list)
    #: Present when the provider reports it. `None` rather than 0 — a call whose usage was not
    #: reported did not use zero tokens.
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    duration_ms: Optional[float] = None
    inputs: int = Field(default=0, description="how many objects went in")
    outputs: int = Field(default=0, description="how many came out")
    detail: str = ""
    notes: List[str] = Field(default_factory=list)

    #: HARNESS-003D. How many times BYTES went on the wire, including identical re-sends after a
    #: capacity refusal. Deliberately not folded into `call_count`, which counts how many times the
    #: pass ASKED: a pass that asked once and was refused twice for capacity is `call_count=1,
    #: transport_attempts=3`, and one number for both would make a rate-limited run look like a pass
    #: that could not make up its mind.
    transport_attempts: int = 0
    capacity_waits: List[CapacityWaitRecord] = Field(default_factory=list)
    #: Time spent waiting for the allowance, not for the model. `None` where nothing waited — zero
    #: would say a pacer was consulted and reported no wait, which is not the same as no pacer.
    waited_ms: Optional[float] = None

    #: HARNESS-003E. How this pass was cut into sendable requests, and what that cost in coverage.
    #: `None` on a pass that was never partitioned — the ledger and the audit make no request at all,
    #: and an empty plan on them would say a partition happened and found one batch.
    batch_plan: Optional[BatchPlanRecord] = None

    @property
    def truncated(self) -> bool:
        return "length" in self.finish_reasons

    @property
    def waited(self) -> bool:
        return any(w.taken for w in self.capacity_waits)

    @property
    def underperformed(self) -> bool:
        return self.outcome in UNDERPERFORMING_OUTCOMES

    @model_validator(mode="after")
    def _a_length_stop_is_truncated(self) -> "PassReceipt":
        """A pass that reported a length stop may not call itself completed.

        The rehearsal's exact failure, made unrepresentable: the compiler ran out of budget, closed
        its JSON, parsed cleanly and reported success. `finish_reason` was already on the receipt;
        nothing stopped the outcome from disagreeing with it.
        """
        if "length" in self.finish_reasons and self.outcome is PassOutcome.COMPLETED:
            raise ValueError(
                f"pass {self.pass_name.value!r} reported a length stop and calls itself "
                f"`completed`. Whatever it produced is a PREFIX; the outcome is `truncated`.")
        return self


class GraphProvenance(_Strict):
    """Who compiled this, from which contracts, with which receipts."""
    producer: str
    compiler_kind: str = Field(..., description="replay | model | unavailable")
    contract_version: str = SCHEMA_VERSION
    inquiry_frame_schema_version: str = ""
    theorist: Optional[ModelReceipt] = None
    compiler: Optional[ModelReceipt] = None
    prompt_sha256: str = ""
    compiled_at: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class SemanticInquiryGraph(_Strict):
    """The whole transformation, in one object. Nothing here has run."""

    schema_version: str = SCHEMA_VERSION
    graph_id: str
    inquiry_id: str
    prompt: str = Field(..., description="the user's words, byte for byte")
    image_refs: List[ImageRef] = Field(default_factory=list)
    #: The WHOLE `InquiryFrame`, as the mapping Lane A handed over. Embedded rather than referenced
    #: because a graph that pointed at a frame stored elsewhere would be checkable only where that
    #: elsewhere is reachable, and the frame is the other half of the provenance.
    inquiry_frame: Dict[str, Any] = Field(default_factory=dict)
    reading: Optional[SceneReading] = None

    #: v2. Empty on every v1 graph, and empty is the truth there rather than a missing field.
    source_units: List[SourceUnit] = Field(default_factory=list)
    semantic_atoms: List[SemanticAtom] = Field(default_factory=list)
    coverage: List[CoverageDisposition] = Field(default_factory=list)
    passes: List[PassReceipt] = Field(default_factory=list)

    #: HARNESS-003F. What this run was ALLOWED to investigate, and what it therefore did not.
    #: `None` on every graph compiled before this lane and on every full-coverage run that predates
    #: the record — and absent is not the same claim as `full`, which is why the projection mints a
    #: full-coverage record rather than reading the absence as one.
    execution_scope: Optional[ExecutionScopeRecord] = None

    claims: List[ClaimNode] = Field(default_factory=list)
    claim_edges: List[ClaimEdge] = Field(default_factory=list)
    observables: List[ObservableSpec] = Field(default_factory=list)
    decision_candidates: List[DecisionCandidate] = Field(default_factory=list)
    semantic_remainder: List[SemanticRemainderItem] = Field(default_factory=list)
    refusals: List[CompilerRefusal] = Field(default_factory=list)
    provenance: GraphProvenance
    notes: List[str] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _pinned(cls, value: str) -> str:
        """One of the versions this code reads — not only the one it writes.

        A stored v1 session and a frozen v1 fixture must both still validate. Pinning to the current
        version alone would turn a version bump into a data loss, and the graph is the object the
        whole run ledger is built around.
        """
        if value not in READABLE_SCHEMA_VERSIONS:
            raise ValueError(f"schema_version must be one of {list(READABLE_SCHEMA_VERSIONS)}, "
                             f"got {value!r}")
        return value

    @property
    def is_dissolved(self) -> bool:
        """Whether this graph carries a source ledger at all.

        `False` for every v1 graph, and that is a fact about the graph rather than a defect: v1 had
        no ledger to carry. A reader branches on this instead of on the version string, so a v3 that
        keeps the ledger does not break it.
        """
        return bool(self.source_units)

    @field_validator("prompt")
    @classmethod
    def _the_prompt_is_there(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("the graph carries no prompt. Every refusal downstream is only "
                             "checkable against what was actually asked.")
        return value

    @model_validator(mode="after")
    def _the_ledger_accounts_for_everything(self) -> "SemanticInquiryGraph":
        """The v2 laws. Skipped entirely on a v1 graph, which has no ledger to check.

        Not "skipped for compatibility" — a v1 graph genuinely made no coverage claim, and inventing
        one to validate against would be the migration asserting something the data never said.
        """
        if not self.source_units:
            if self.semantic_atoms or self.coverage:
                raise ValueError(
                    "this graph carries atoms or coverage and no source units. Every atom is "
                    "anchored to a unit, so a ledger-less graph with atoms in it is one whose "
                    "anchors point outside itself.")
            return self

        unit_ids = {u.source_unit_id for u in self.source_units}
        if len(unit_ids) != len(self.source_units):
            raise ValueError("two source units share an id. Unit ids are derived from source "
                             "identity plus text, so a collision means one unit was listed twice.")

        atom_ids = {a.atom_id for a in self.semantic_atoms}
        if len(atom_ids) != len(self.semantic_atoms):
            raise ValueError("two atoms share an id.")

        for atom in self.semantic_atoms:
            for ref in atom.source_unit_ids:
                if ref not in unit_ids:
                    raise ValueError(
                        f"atom {atom.atom_id} is anchored to {ref!r}, which is not a source unit in "
                        f"this graph. The anchor is the only thing separating what the dissector "
                        f"found from what it wrote.")

        # EXACTLY ONE DISPOSITION PER UNIT — the law the whole ledger exists for.
        seen: Dict[str, int] = {}
        for entry in self.coverage:
            if entry.source_unit_id not in unit_ids:
                raise ValueError(
                    f"coverage {entry.coverage_id} disposes of {entry.source_unit_id!r}, which is "
                    f"not a source unit in this graph.")
            seen[entry.source_unit_id] = seen.get(entry.source_unit_id, 0) + 1
        uncovered = sorted(unit_ids - set(seen))
        doubled = sorted(k for k, n in seen.items() if n > 1)
        if uncovered:
            raise ValueError(
                f"{len(uncovered)} source unit(s) have no coverage disposition: {uncovered[:5]}. A "
                f"unit with no disposition is a paragraph that vanished with nothing saying so.")
        if doubled:
            raise ValueError(
                f"{len(doubled)} source unit(s) have more than one disposition: {doubled[:5]}. Two "
                f"dispositions tell two stories about the same words and a reader cannot tell which "
                f"one is the record.")

        for entry in self.coverage:
            if entry.disposition is DispositionKind.REPRESENTED_BY:
                for ref in entry.refs:
                    if ref not in atom_ids:
                        raise ValueError(
                            f"coverage {entry.coverage_id} says its unit is represented by "
                            f"{ref!r}, which is not an atom in this graph.")
            elif entry.disposition is DispositionKind.DUPLICATE_OF:
                if entry.refs[0] not in unit_ids:
                    raise ValueError(
                        f"coverage {entry.coverage_id} says its unit duplicates {entry.refs[0]!r}, "
                        f"which is not a source unit in this graph.")

        for claim in self.claims:
            for ref in claim.atom_refs:
                if ref not in atom_ids:
                    raise ValueError(
                        f"claim {claim.claim_id} is built from atom {ref!r}, which is not in this "
                        f"graph. A claim standing on an atom that was refused is one whose warrant "
                        f"was removed while the claim stayed.")

        # A USER STATEMENT STAYS THE USER'S. Enforced on the graph as well as on the atom, because
        # the atom cannot see which KIND of unit it was anchored to.
        by_unit = {u.source_unit_id: u for u in self.source_units}
        for atom in self.semantic_atoms:
            anchors = [by_unit[r] for r in atom.source_unit_ids if r in by_unit]
            if anchors and all(a.is_user_authored for a in anchors) \
                    and atom.author is not AtomAuthor.USER:
                raise ValueError(
                    f"atom {atom.atom_id} is anchored only to the person's own words and is "
                    f"attributed to {atom.author.value!r}. A user's hypothesis rewritten as a model "
                    f"observation is the one attribution error nothing downstream can detect.")
        return self

    @model_validator(mode="after")
    def _references_resolve_and_nothing_is_promoted(self) -> "SemanticInquiryGraph":
        ids = {c.claim_id for c in self.claims}
        if len(ids) != len(self.claims):
            raise ValueError("two claims share an id. Ids are content-derived, so a collision means "
                             "two claims with identical content were both kept.")

        def _check(ref: str, where: str) -> None:
            if ref not in ids:
                raise ValueError(
                    f"{where} points at {ref!r}, which is not a claim in this graph. A dangling "
                    f"reference renders as a supported claim in any UI that follows edges.")

        for edge in self.claim_edges:
            _check(edge.from_claim, f"edge {edge.edge_id}")
            _check(edge.to_claim, f"edge {edge.edge_id}")
        for observable in self.observables:
            _check(observable.claim_id, f"observable {observable.observable_id}")
        for claim in self.claims:
            for parent in claim.inferred_from:
                _check(parent, f"claim {claim.claim_id} (inferred_from)")
        for item in self.semantic_remainder:
            for ref in item.claim_refs:
                _check(ref, f"semantic remainder {item.term!r}")

        by_id = {c.claim_id: c for c in self.claims}
        for observable in self.observables:
            claim = by_id[observable.claim_id]
            if claim.claim_kind is ClaimKind.HISTORICAL_OR_SOURCED and \
                    CapabilityClass.EXTERNAL_SOURCE not in observable.capability_classes:
                raise ValueError(
                    f"observable {observable.observable_id} serves the sourced claim "
                    f"{claim.claim_id} and requests "
                    f"{[c.value for c in observable.capability_classes]}. A historical "
                    f"generalization routed to an image capability becomes an image measurement of "
                    f"a claim the image cannot settle.")

        # HARNESS-001A's rule, applied to the graph rather than to the frame. Two places a term can
        # be declared measurable — a claim's own demand, and an observable that targets it by name —
        # and a remainder contradicts both.
        measurable_subjects = {c.subject.strip().lower() for c in self.claims
                               if c.epistemic_demand is DemandKind.MEASURABLE and c.subject.strip()}
        measurable_targets = {t.strip().lower() for o in self.observables
                              for t in o.targets
                              if t.strip() and not set(o.capability_classes) <= NON_MEASURING_CLASSES}
        for item in self.semantic_remainder:
            term = item.term.strip().lower()
            if term and (term in measurable_subjects or term in measurable_targets):
                raise ValueError(
                    f"{item.term!r} is a semantic remainder AND is declared measurable elsewhere in "
                    f"this graph. A remainder is what measurement does not reach; the two cannot "
                    f"both be true of one term.")
        return self

    # ── reading a graph ──

    def claim(self, claim_id: str) -> Optional[ClaimNode]:
        return next((c for c in self.claims if c.claim_id == claim_id), None)

    def claims_of(self, kind: ClaimKind) -> List[ClaimNode]:
        return [c for c in self.claims if c.claim_kind is kind]

    def observables_for(self, claim_id: str) -> List[ObservableSpec]:
        return [o for o in self.observables if o.claim_id == claim_id]

    def capability_classes(self) -> List[str]:
        seen: List[str] = []
        for observable in self.observables:
            for klass in observable.capability_classes:
                if klass.value not in seen:
                    seen.append(klass.value)
        return sorted(seen)

    def investigable_claims(self) -> List[ClaimNode]:
        """Claims something was actually asked for. Not the same as claims worth keeping."""
        served = {o.claim_id for o in self.observables}
        return [c for c in self.claims if c.claim_id in served]

    def summary(self) -> str:
        """One honest line. Says what was compiled and what was refused; claims nothing found."""
        bits = [f"{len(self.claims)} claim{'' if len(self.claims) == 1 else 's'}"]
        by_kind: Dict[str, int] = {}
        for claim in self.claims:
            by_kind[claim.claim_kind.value] = by_kind.get(claim.claim_kind.value, 0) + 1
        if by_kind:
            bits.append(" · ".join(f"{n} {k}" for k, n in sorted(by_kind.items())))
        bits.append(f"{len(self.observables)} observable"
                    f"{'' if len(self.observables) == 1 else 's'} requested, none run")
        if self.decision_candidates:
            bits.append(f"{len(self.decision_candidates)} decision candidate"
                        f"{'' if len(self.decision_candidates) == 1 else 's'}")
        if self.semantic_remainder:
            bits.append(f"{len(self.semantic_remainder)} meaning"
                        f"{'' if len(self.semantic_remainder) == 1 else 's'} measurement will not "
                        f"exhaust")
        if self.refusals:
            bits.append(f"{len(self.refusals)} refused")
        return " · ".join(bits)


#: Fields that change between two compilations of identical inputs. A replay check must exclude
#: exactly these and nothing else — every id in this graph is content-derived on purpose, so a
#: broader exclusion list would let a real drift hide inside it.
VOLATILE_FIELDS: Tuple[str, ...] = ("compiled_at", "requested_at")


def canonical(graph: SemanticInquiryGraph) -> Dict[str, Any]:
    """The graph with its caller-handed timestamps removed, for comparing two compilations.

    Note what is NOT removed: every id. `ids.py` derives them from content, so two replays of one
    frozen output must agree on them — and a canonicaliser that dropped ids would let two runs
    disagree about which claim an observable served and still call the replay reproducible.
    """
    data = graph.model_dump(mode="json", by_alias=True)
    provenance = dict(data.get("provenance") or {})
    provenance.pop("compiled_at", None)
    for key in ("theorist", "compiler"):
        provenance[key] = _without_timestamp(provenance.get(key))
    data["provenance"] = provenance
    # THE READING CARRIES A RECEIPT OF ITS OWN, and it is the SAME receipt object the graph's
    # provenance points at — so stripping only `provenance.theorist` left a second `requested_at`
    # embedded one level down and two replays of one fixture differed. Found by the cross-domain
    # fixtures rather than by reading this function, which is the argument for having them.
    reading = data.get("reading")
    if isinstance(reading, dict):
        reading = dict(reading)
        reading["provenance"] = _without_timestamp(reading.get("provenance"))
        data["reading"] = reading
    return data


def _without_timestamp(receipt: Any) -> Any:
    if not isinstance(receipt, dict):
        return receipt
    stripped = dict(receipt)
    stripped.pop("requested_at", None)
    return stripped


__all__ = [
    "SCHEMA_VERSION", "SCHEMA_VERSION_V1", "SCHEMA_VERSION_V2", "READABLE_SCHEMA_VERSIONS",
    "VOLATILE_FIELDS", "FORBIDDEN_INITIAL_STATUSES", "NON_MEASURING_CLASSES",
    "UNDERPERFORMING_OUTCOMES",
    "ClaimKind", "ClaimEdgeKind", "ClaimStatus", "ImageScope", "SourceType", "CapabilityClass",
    "GroundForm", "ReadingBlockKind", "DecisionKind", "CompilerRefusalKind", "CallTopology",
    "SourceUnitKind", "AtomKind", "AtomAuthor", "DispositionKind", "DissolutionPass", "PassOutcome",
    "ImageRef", "SourcePointer", "ReadingBlock", "ModelReceipt", "SceneReading", "ClaimNode",
    "ClaimEdge", "OperationalAlternative", "ObservableSpec", "DecisionCandidate",
    "SemanticRemainderItem", "CompilerRefusal", "GraphProvenance", "SemanticInquiryGraph",
    "SourceUnit", "SemanticAtom", "CoverageDisposition", "PassReceipt", "CapacityWaitRecord",
    "BATCH_PLAN_VERSION", "BatchBoundaryReason", "ItemDispositionKind", "BatchAssignment",
    "ComparisonPair", "ReconciliationRound", "DuplicateClaim", "ItemDisposition", "BatchPlanRecord",
    "EXECUTION_SCOPE_VERSION", "SCOPE_PURPOSE_VERTICAL_FLOW", "SCOPE_DEFERRED_REASON",
    "ExecutionScope", "ScopeExclusion", "ExecutionScopeRecord",
    "canonical",
]
