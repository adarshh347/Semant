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

SCHEMA_VERSION = "semantic-inquiry-graph.v1"


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
        if value != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}, got {value!r}")
        return value

    @field_validator("prompt")
    @classmethod
    def _the_prompt_is_there(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("the graph carries no prompt. Every refusal downstream is only "
                             "checkable against what was actually asked.")
        return value

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
    "SCHEMA_VERSION", "VOLATILE_FIELDS", "FORBIDDEN_INITIAL_STATUSES", "NON_MEASURING_CLASSES",
    "ClaimKind", "ClaimEdgeKind", "ClaimStatus", "ImageScope", "SourceType", "CapabilityClass",
    "GroundForm", "ReadingBlockKind", "DecisionKind", "CompilerRefusalKind", "CallTopology",
    "ImageRef", "SourcePointer", "ReadingBlock", "ModelReceipt", "SceneReading", "ClaimNode",
    "ClaimEdge", "OperationalAlternative", "ObservableSpec", "DecisionCandidate",
    "SemanticRemainderItem", "CompilerRefusal", "GraphProvenance", "SemanticInquiryGraph",
    "canonical",
]
