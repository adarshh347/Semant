"""
INTELLIGENCE-001A — the seven things an inquiry must never let blur into one another.

    what the person PROPOSED          -> UserHypothesis, and it can only ever come from the prompt
    what a model SAID about a picture -> VisualObservation, interpretive until something measures
    how the two STAND to each other   -> HypothesisAlignment
    what Semant CHOSE to compare      -> ContrastPlan
    what it INFERRED from that        -> CandidateRelation
    what a critic ACCEPTED or REFUSED -> RelationCritique
    whether any of it was USEFUL      -> IntelligenceOutcomeRecord, which is not "did it finish"

## Why a separate module

`semantic_compilation` already models a reading becoming claims. This models something else: the
difference between the four WARRANTS a sentence can hold. A claim in that graph knows which source
type it came from; it does not know whether a person would stand behind it, whether a VLM merely
recognised something, or whether an instrument produced it. Those are not degrees of one scale —
they are different kinds of thing to be wrong about, and a schema that ranks them on one axis makes
the most common failure in this whole system unspellable: a hypothesis the person typed coming back
to them as if the pictures had said it.

Nothing here is wired into the live inquiry pipeline. These are contracts and their invariants; the
lane that binds them is a later one. That is deliberate — a contract that arrives already load
bearing is one nobody can argue with.

## The three rules the file is shaped by

**PROMPT MATERIAL CANNOT ACQUIRE AN IMAGE.** `UserHypothesis` has no field for an image, a ground, a
region, an evidence id or an epistemic status. Not "has them and forbids them" — HAS THEM NOT, and
`extra="forbid"` means one cannot be added by a parser, a model or a later dict update. The only
way to say something about a picture is to construct a `VisualObservation`, which requires an image
reference to exist at all.

**LOOKING IS NOT MEASURING.** A VLM that reads an image produces `interpretive` — always, and the
enum's `measured` member is reachable only through `measurement`, a required object naming a
capability class, an instrument and the evidence it produced. Model agreement is not a path:
two observations that say the same thing are two interpretations, and `IntelligenceOutcomeRecord`
counts them as such.

**A DESCRIPTION, AN EFFECT AND AN INTERPRETATION ARE THREE FIELDS.** `visible_description` is what
is there; `appearance_effect` is what it does to a viewer; `interpretive_possibility` is what it
might mean. One prose field holding all three is how "it looks translucent" becomes "it is
translucent" two passes later, with nothing to point at as the moment it happened.

## Open vocabulary, closed grammar

Every SUBJECT is an open string: a feature, a comparison dimension, a user's own word. Every
RELATION between subjects is a closed enum. Every member of every enum here describes a shape one
could want to say about anything at all, and none of them names a subject any rehearsal happens to
be about — `test_inquiry_intelligence_contracts.py` scans this module against the vocabulary of all
four fixtures, which is the same guard `semantic_compilation` lives under.

## Ids

Content-derived, no clock and no counter, so a re-run is a comparison rather than an act of faith —
the reasoning is `semantic_compilation.ids`, and the prefixes are deliberately NOT added to that
module's table: `test_semantic_compilation_contract.py` pins it to the graph contract by exact
equality, and a spine prefix appearing there would fail a contract this lane is not editing.
"""
from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.schemas.semantic_compilation import CapabilityClass

#: The version this code WRITES.
SCHEMA_VERSION_V1 = "inquiry-intelligence.v1"
SCHEMA_VERSION = SCHEMA_VERSION_V1

#: Every version this code can VALIDATE. One today, and a tuple rather than a constant so the next
#: version is a bump rather than a migration — the policy `semantic_compilation` already follows.
READABLE_SCHEMA_VERSIONS: Tuple[str, ...] = (SCHEMA_VERSION_V1,)


# ── ids ──────────────────────────────────────────────────────────────────────

PREFIXES: Dict[str, str] = {
    "inquiry_map": "imap_",
    "user_hypothesis": "hyp_",
    "requested_comparison": "rqc_",
    "inquiry_question": "qst_",
    "ambiguity": "amb_",
    "visual_observation": "vob_",
    "hypothesis_alignment": "hal_",
    "contrast_plan": "con_",
    "candidate_relation": "crl_",
    "relation_critique": "crt_",
    "intelligence_outcome": "out_",
}

#: Twelve hex characters, the width the rest of the system uses.
WIDTH = 12

_WHITESPACE = re.compile(r"\s+")


def normalise(text: Any) -> str:
    """The form a hash is taken over: lowercased, whitespace collapsed, trimmed."""
    return _WHITESPACE.sub(" ", str(text or "")).strip().lower()


def mint(kind: str, parts: Iterable[Any]) -> str:
    """A content-derived id. NUL-joined so ('ab','c') and ('a','bc') cannot collide."""
    if kind not in PREFIXES:
        raise KeyError(f"no id prefix declared for {kind!r}")
    payload = "\x00".join(normalise(p) for p in [kind, *parts])
    return f"{PREFIXES[kind]}{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:WIDTH]}"


# ── the closed sets ──────────────────────────────────────────────────────────

class MaterialOrigin(str, Enum):
    """Where a piece of material came from. The four warrants, and they do not convert.

    A reader who knows only that something is "in the inquiry" knows nothing about who is
    answerable for it. This enum is that answer, and it is on every object that carries content.
    """
    PROMPT = "prompt"
    IMAGE_OBSERVATION = "image_observation"
    SEMANT_INFERENCE = "semant_inference"
    EXTERNAL_SOURCE = "external_source"


class EpistemicStatus(str, Enum):
    """What warrant a statement currently holds.

    `MEASURED` EXISTS HERE AND DOES NOT EXIST IN `ClaimStatus`, and the difference is deliberate. A
    compiled claim is authored before anything has run, so an enum that could spell `measured` was
    a hole; a spine object may be revised AFTER a capability has produced evidence, so an enum that
    could not spell it would force the measured case to be represented as something it is not. The
    wall is moved rather than removed: `MEASURED` requires `measurement`, checked on every model
    that carries a status.
    """
    INTERPRETIVE = "interpretive"
    SOURCED = "sourced"
    UNCERTAIN = "uncertain"
    MEASURED = "measured"


#: The status a model-authored statement may not hold on its own say-so, named so a refusal can
#: quote it rather than describe it.
MEASURED_STATUS = EpistemicStatus.MEASURED


class ObservationState(str, Enum):
    """Whether there IS an observation. An absence that reads as a quiet negative is the failure
    this enum exists to prevent: `refused` and `unavailable` are facts about the instrument, and
    neither is evidence that the picture lacks the feature."""
    OBSERVED = "observed"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"


class ProvenanceKind(str, Enum):
    """WHICH RUN THIS IS, and it is never inferable. A frozen payload replayed through the real
    parser and a live provider call produce the same shapes; only this field tells them apart, and
    a surface that cannot tell them apart will eventually screenshot one as the other."""
    LIVE = "live"
    REPLAY = "replay"
    FIXTURE = "fixture"
    LOCAL = "local"
    DETERMINISTIC = "deterministic"


#: The kinds that reached a provider, and therefore must name which one.
PROVIDER_BACKED: Tuple[ProvenanceKind, ...] = (ProvenanceKind.LIVE,)

#: The kinds that did NOT reach a provider, and therefore may not claim one.
UNREACHED: Tuple[ProvenanceKind, ...] = (ProvenanceKind.REPLAY, ProvenanceKind.FIXTURE,
                                         ProvenanceKind.DETERMINISTIC)


class AnswerForm(str, Enum):
    """The SHAPE of answer the question asks for. Topic-free by construction: every member is a
    thing one can want about anything at all."""
    COMPARISON = "comparison"
    EXPLANATION = "explanation"
    DESCRIPTION = "description"
    ENUMERATION = "enumeration"
    JUDGEMENT = "judgement"
    UNSPECIFIED = "unspecified"


# ── the strict base ──────────────────────────────────────────────────────────

class _Strict(BaseModel):
    """Unknown fields are refused, not ignored.

    THIS IS THE COMPATIBILITY POLICY, not an omission from it. A future field arrives as a schema
    version this tuple lists, reviewed; a field nobody declared arriving silently is precisely how
    an image reference lands on a user hypothesis.
    """
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class Provenance(_Strict):
    """Who produced a thing, and under which identity.

    `model` and `provider` are gated on `kind` in both directions. A `live` record that names no
    provider cannot be audited; a `fixture` record that names one is a replay wearing a live face,
    which is the confusion this whole field exists to prevent.
    """
    producer: str = Field(..., min_length=1, description="the module or role that authored this")
    kind: ProvenanceKind
    model: str = ""
    provider: str = ""
    prompt_sha256: str = ""
    note: str = ""

    @model_validator(mode="after")
    def _identity_is_explicit(self) -> "Provenance":
        if self.kind in PROVIDER_BACKED and not (self.provider and self.model):
            raise ValueError(
                f"provenance.kind={self.kind.value!r} must name both a provider and a model. A "
                f"live call nobody can attribute is not a live call anybody can check.")
        if self.kind in UNREACHED and (self.provider or self.model):
            raise ValueError(
                f"provenance.kind={self.kind.value!r} reached no provider, so it may not name "
                f"{self.provider or self.model!r}. A replay that names a provider is a replay that "
                f"will be read as a live reading.")
        return self


class MeasurementProvenance(_Strict):
    """The only thing that licenses `measured`.

    Deliberately demanding. It names the capability CLASS that ran, the instrument that implemented
    it, and at least one evidence reference — three facts a model cannot supply by being confident,
    and which together let a reader go and look at what was actually produced.
    """
    capability_class: CapabilityClass
    instrument: str = Field(..., min_length=1, description="what implemented the class, by name")
    evidence_refs: List[str] = Field(..., min_length=1)
    run_ref: str = ""
    note: str = ""

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_is_named(cls, refs: List[str]) -> List[str]:
        if any(not str(r).strip() for r in refs):
            raise ValueError("an empty evidence reference is not evidence")
        return [str(r).strip() for r in refs]


class PromptSpan(_Strict):
    """Where in the person's own words something was found.

    `text` is load bearing and `span` is not: a model asked for character offsets will invent them,
    so the quote is what gets checked against the prompt and the offsets are a convenience.
    """
    text: str = Field(..., min_length=1)
    span: Optional[Tuple[int, int]] = None
    sentence_index: Optional[int] = None

    @model_validator(mode="after")
    def _span_is_ordered(self) -> "PromptSpan":
        if self.span is not None:
            start, end = self.span
            if start < 0 or end < start:
                raise ValueError(f"span {self.span!r} does not describe a range")
        return self


# ── 1. what the person proposed ──────────────────────────────────────────────

class UserHypothesis(_Strict):
    """SOMETHING THE PERSON SAID, and nothing else.

    Read the field list for what is not here: no image, no post id, no region, no ground, no
    evidence, no epistemic status, no measurement. A hypothesis cannot be given one, because
    `extra="forbid"` refuses the key rather than absorbing it — so the sentence "the person's guess
    became an image finding" has no representation in this system, which is stronger than having a
    rule against it.

    `origin` is a `Literal` rather than an enum field with a default. A default is a value somebody
    can overwrite; a literal is a value the type system will not accept anything else for.
    """
    hypothesis_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    origin: Literal[MaterialOrigin.PROMPT] = MaterialOrigin.PROMPT
    spans: List[PromptSpan] = Field(default_factory=list)
    user_terms: List[str] = Field(default_factory=list,
                                  description="the person's own words, open vocabulary")
    note: str = ""

    @field_validator("hypothesis_id")
    @classmethod
    def _prefixed(cls, value: str) -> str:
        return _require_prefix(value, "user_hypothesis")

    @field_validator("text")
    @classmethod
    def _said_something(cls, value: str) -> str:
        return _require_nonblank(value, "text")


class RequestedComparison(_Strict):
    """A comparison the person ASKED FOR. Still prompt material — it proposes work, it reports
    nothing. `image_ids` are the pictures they pointed at, which is a fact about the request and
    not about what any of those pictures contain."""
    comparison_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    image_ids: List[str] = Field(default_factory=list)
    dimension: str = Field(default="", description="open vocabulary; the person's own axis")
    spans: List[PromptSpan] = Field(default_factory=list)

    @field_validator("comparison_id")
    @classmethod
    def _prefixed(cls, value: str) -> str:
        return _require_prefix(value, "requested_comparison")

    @field_validator("image_ids")
    @classmethod
    def _distinct(cls, ids: List[str]) -> List[str]:
        # REFUSED rather than dropped, which is what this did first. Silently discarding a blank
        # entry means a request for three pictures is served as a request for two, and the person
        # is shown a comparison of a set they did not ask about with nothing saying so.
        cleaned = [_require_nonblank(i, "image_ids") for i in ids]
        _require_unique(cleaned, "image_ids")
        return cleaned


class InquiryQuestion(_Strict):
    """One question the map found in the prompt.

    `capability_classes` is what separates the two lists on `InquiryMap`: a question is
    POTENTIALLY OBSERVABLE because one can name the kind of instrument that would bear on it, and
    interpretive because one cannot. Naming a class is not commissioning it and not having it.
    """
    question_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    capability_classes: List[CapabilityClass] = Field(default_factory=list)
    spans: List[PromptSpan] = Field(default_factory=list)

    @field_validator("question_id")
    @classmethod
    def _prefixed(cls, value: str) -> str:
        return _require_prefix(value, "inquiry_question")


class Ambiguity(_Strict):
    """Something the prompt could mean more than one of, kept rather than resolved.

    A map that silently picked one reading would make every downstream result a fact about the
    guess. `readings` holds them all; nothing here chooses.
    """
    ambiguity_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    readings: List[str] = Field(default_factory=list)
    why_it_matters: str = ""
    spans: List[PromptSpan] = Field(default_factory=list)

    @field_validator("ambiguity_id")
    @classmethod
    def _prefixed(cls, value: str) -> str:
        return _require_prefix(value, "ambiguity")


class InquiryMap(_Strict):
    """WHAT THE PERSON ASKED, typed. Every field on it is prompt material or a reading of prompt
    material, and the object as a whole carries `MaterialOrigin.PROMPT` for the same reason each
    hypothesis does: so a later pass cannot mistake the map for a finding.

    It holds no observation, no relation and no verdict. Those live in objects that require an
    image reference to exist, which is what makes "the map said the picture shows X" unsayable.
    """
    schema_version: str = SCHEMA_VERSION
    inquiry_map_id: str = Field(..., min_length=1)
    inquiry_id: str = Field(..., min_length=1)
    principal_question: str = Field(..., min_length=1)
    origin: Literal[MaterialOrigin.PROMPT] = MaterialOrigin.PROMPT
    user_hypotheses: List[UserHypothesis] = Field(default_factory=list)
    user_vocabulary: List[str] = Field(default_factory=list,
                                       description="open; the person's words, unmapped")
    requested_comparisons: List[RequestedComparison] = Field(default_factory=list)
    interpretive_questions: List[InquiryQuestion] = Field(default_factory=list)
    potentially_observable_questions: List[InquiryQuestion] = Field(default_factory=list)
    desired_answer_form: AnswerForm = AnswerForm.UNSPECIFIED
    ambiguities: List[Ambiguity] = Field(default_factory=list)
    prompt_source_spans: List[PromptSpan] = Field(default_factory=list)
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def _readable(cls, value: str) -> str:
        return _require_readable(value)

    @field_validator("inquiry_map_id")
    @classmethod
    def _prefixed(cls, value: str) -> str:
        return _require_prefix(value, "inquiry_map")

    @field_validator("inquiry_id", "principal_question")
    @classmethod
    def _asked_something(cls, value: str) -> str:
        return _require_nonblank(value, "the inquiry id and the principal question")

    @model_validator(mode="after")
    def _ids_are_unique_and_questions_are_typed(self) -> "InquiryMap":
        _require_unique([h.hypothesis_id for h in self.user_hypotheses], "user_hypotheses")
        _require_unique([c.comparison_id for c in self.requested_comparisons],
                        "requested_comparisons")
        _require_unique([a.ambiguity_id for a in self.ambiguities], "ambiguities")
        _require_unique([q.question_id for q in
                         (*self.interpretive_questions, *self.potentially_observable_questions)],
                        "questions")
        for question in self.potentially_observable_questions:
            if not question.capability_classes:
                raise ValueError(
                    f"{question.question_id} sits in potentially_observable_questions and names no "
                    f"capability class. What makes a question observable is that one can say what "
                    f"KIND of instrument would bear on it; a question that cannot say is an "
                    f"interpretive one, and belongs in the other list.")
        for question in self.interpretive_questions:
            if question.capability_classes:
                raise ValueError(
                    f"{question.question_id} is interpretive and names "
                    f"{[c.value for c in question.capability_classes]}. A question with a named "
                    f"instrument class is potentially observable — move it rather than annotate it.")
        return self

    def hypothesis_ids(self) -> List[str]:
        return [h.hypothesis_id for h in self.user_hypotheses]

    def images_requested(self) -> List[str]:
        seen: List[str] = []
        for comparison in self.requested_comparisons:
            for image_id in comparison.image_ids:
                if image_id not in seen:
                    seen.append(image_id)
        return seen


# ── 2. what a model said about an image ──────────────────────────────────────

class VisualObservation(_Strict):
    """ONE THING A MODEL REPORTED ABOUT ONE PICTURE, in three separated layers.

    THE IMAGE REFERENCE IS REQUIRED. Not defaulted, not optional — an observation with no picture
    is a sentence somebody wrote, and this system already has a place for those. This single
    requirement is what makes prompt material structurally unable to enter as an observation.

    THE THREE LAYERS.

      `visible_description`   what is there. The claim a viewer could check by looking.
      `appearance_effect`     what it does — reads as heavy, reads as continuous. Still not meaning.
      `interpretive_possibility`  what it might mean. Never promoted by agreement or repetition.

    `region_ref` and `ground_ref` are optional and stay optional. An interpretive observation with
    no ground is the NORMAL case — a VLM saw something and nothing has segmented it — and a schema
    that required a ground would either block the ordinary path or invite a fabricated id. Note
    that this file does not add `epistemic_status` to `GroundBase` and must not: a ground is a
    measured region, and giving it a status field would invite an unmeasured one.
    """
    schema_version: str = SCHEMA_VERSION
    observation_id: str = Field(..., min_length=1)
    image_id: str = Field(..., min_length=1, description="the post or image this is ABOUT")
    origin: Literal[MaterialOrigin.IMAGE_OBSERVATION] = MaterialOrigin.IMAGE_OBSERVATION
    locus: str = Field(default="", description="prose, not coordinates; where in the picture")
    region_ref: str = Field(default="", description="a future region id, when one exists")
    ground_ref: str = Field(default="", description="a future ground id, when one exists")
    feature: str = Field(..., min_length=1, description="open vocabulary; what is being reported")
    visible_description: str = ""
    organization: str = Field(default="", description="the spatial or visual arrangement")
    appearance_effect: str = Field(default="", description="what it does to a viewer")
    interpretive_possibility: str = Field(default="", description="what it might mean")
    reading_block_refs: List[str] = Field(default_factory=list)
    epistemic_status: EpistemicStatus = EpistemicStatus.INTERPRETIVE
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    requested_capability_classes: List[CapabilityClass] = Field(default_factory=list)
    state: ObservationState = ObservationState.OBSERVED
    absence_reason: str = Field(default="", description="why there is no observation, if there is")
    measurement: Optional[MeasurementProvenance] = None
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def _readable(cls, value: str) -> str:
        return _require_readable(value)

    @field_validator("observation_id")
    @classmethod
    def _prefixed(cls, value: str) -> str:
        return _require_prefix(value, "visual_observation")

    @field_validator("image_id")
    @classmethod
    def _image_resolves(cls, value: str) -> str:
        return _require_nonblank(value, "image_id")

    @field_validator("feature")
    @classmethod
    def _feature_is_named(cls, value: str) -> str:
        return _require_nonblank(value, "feature")

    @model_validator(mode="after")
    def _looking_is_not_measuring(self) -> "VisualObservation":
        _require_measurement(self.epistemic_status, self.measurement, self.observation_id)
        if self.state is ObservationState.OBSERVED and not self.visible_description.strip():
            raise ValueError(
                f"{self.observation_id} claims state=observed with no visible_description. The "
                f"layer a viewer could check is the one that may not be empty; an observation that "
                f"is only an effect and a possibility is an interpretation with an image id.")
        if self.state is not ObservationState.OBSERVED:
            if not self.absence_reason.strip():
                raise ValueError(
                    f"{self.observation_id} is {self.state.value} and says why not. An absent "
                    f"observation with no reason reads as evidence the feature is not there.")
            if self.epistemic_status is EpistemicStatus.MEASURED:
                raise ValueError(
                    f"{self.observation_id} is {self.state.value} and measured. Nothing was "
                    f"produced, so nothing was measured.")
        return self

    def is_measured(self) -> bool:
        return self.epistemic_status is EpistemicStatus.MEASURED and self.measurement is not None


# ── 3. how an observation stands to what the person proposed ────────────────

class AlignmentKind(str, Enum):
    """The five ways an observation can bear on a hypothesis, and the last two are not failures.

    `DOES_NOT_BEAR_ON` and `CANNOT_DETERMINE` are the members that keep the other three honest. A
    vocabulary with only supports/complicates/challenges forces every observation to take a side,
    and the pressure to take a side is exactly what turns a picture into a witness for whatever the
    person already said. Most observations bear on most hypotheses not at all.
    """
    SUPPORTS = "supports"
    COMPLICATES = "complicates"
    CHALLENGES = "challenges"
    DOES_NOT_BEAR_ON = "does_not_bear_on"
    CANNOT_DETERMINE = "cannot_determine"


class HypothesisAlignment(_Strict):
    """One observation, one hypothesis, and the relation between them — never a merge of the two.

    THE ALIGNMENT IS A THIRD OBJECT rather than a field on either side. A `supported: true` on the
    hypothesis would make the person's sentence carry an image finding, which is the thing this
    whole module exists to make unsayable; a field on the observation would make a picture carry
    the person's proposal. The relation belongs to neither, so it lives on its own.

    An alignment is never `measured`. It is a judgement ABOUT two things, and if one of them was
    measured that fact stays on the observation where the evidence is.
    """
    schema_version: str = SCHEMA_VERSION
    alignment_id: str = Field(..., min_length=1)
    hypothesis_id: str = Field(..., min_length=1)
    observation_id: str = Field(..., min_length=1)
    alignment: AlignmentKind
    explanation: str = Field(..., min_length=1)
    missing_capability_classes: List[CapabilityClass] = Field(default_factory=list)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def _readable(cls, value: str) -> str:
        return _require_readable(value)

    @field_validator("alignment_id")
    @classmethod
    def _own_prefix(cls, value: str) -> str:
        return _require_prefix(value, "hypothesis_alignment")

    @field_validator("hypothesis_id")
    @classmethod
    def _points_at_a_hypothesis(cls, value: str) -> str:
        return _require_prefix(value, "user_hypothesis")

    @field_validator("observation_id")
    @classmethod
    def _points_at_an_observation(cls, value: str) -> str:
        return _require_prefix(value, "visual_observation")

    @field_validator("explanation")
    @classmethod
    def _says_why(cls, value: str) -> str:
        return _require_nonblank(value, "explanation")


# ── 4. what Semant chose to compare ─────────────────────────────────────────

class ContrastScope(str, Enum):
    """Whether a contrast crosses pictures. Declared rather than inferred, so the declaration can
    be CHECKED against what the observations actually resolve to."""
    SINGLE_IMAGE = "single_image"
    CROSS_IMAGE = "cross_image"


class ContrastPlan(_Strict):
    """A comparison SEMANT decided was worth making. Nothing has been compared yet.

    `possible_countercondition` is required, and that is the load-bearing decision in this model. A
    contrast that cannot say what would show the opposite is not an investigation — it is a
    description of an expected result, and it will find that result. One sentence naming what would
    embarrass the comparison is the cheapest falsifiability this system can buy.

    `comparison_dimension` is an open string and must stay one. The moment it becomes an enum, the
    set of comparisons Semant can make is fixed at the size of whatever list somebody wrote, and
    every subject outside it gets compared along an axis that does not fit it.
    """
    schema_version: str = SCHEMA_VERSION
    contrast_id: str = Field(..., min_length=1)
    question_ref: str = Field(default="", description="the inquiry question served, if one")
    question_text: str = Field(default="", description="the question in words")
    observation_ids: List[str] = Field(..., min_length=2)
    image_ids: List[str] = Field(..., min_length=1)
    comparison_dimension: str = Field(..., min_length=1, description="open vocabulary")
    why_it_matters: str = Field(..., min_length=1)
    difference_investigated: str = Field(..., min_length=1)
    possible_countercondition: str = Field(..., min_length=1)
    required_capability_classes: List[CapabilityClass] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    scope: ContrastScope = ContrastScope.CROSS_IMAGE
    origin: Literal[MaterialOrigin.SEMANT_INFERENCE] = MaterialOrigin.SEMANT_INFERENCE
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def _readable(cls, value: str) -> str:
        return _require_readable(value)

    @field_validator("contrast_id")
    @classmethod
    def _own_prefix(cls, value: str) -> str:
        return _require_prefix(value, "contrast_plan")

    @field_validator("observation_ids")
    @classmethod
    def _point_at_observations(cls, refs: List[str]) -> List[str]:
        cleaned = [_require_prefix(r, "visual_observation") for r in refs]
        _require_unique(cleaned, "observation_ids")
        return cleaned

    @field_validator("comparison_dimension", "why_it_matters", "difference_investigated",
                     "possible_countercondition")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _require_nonblank(value, "a contrast's own sentences")

    @field_validator("image_ids")
    @classmethod
    def _distinct_images(cls, ids: List[str]) -> List[str]:
        cleaned = [_require_nonblank(i, "image_ids") for i in ids]
        _require_unique(cleaned, "image_ids")
        return cleaned

    @model_validator(mode="after")
    def _scope_matches_the_pictures(self) -> "ContrastPlan":
        if self.scope is ContrastScope.CROSS_IMAGE and len(self.image_ids) < 2:
            raise ValueError(
                f"{self.contrast_id} declares itself cross-image and names "
                f"{self.image_ids!r}. A cross-image contrast must resolve to at least two distinct "
                f"images; one picture compared with itself is a single-image contrast, which is a "
                f"legitimate thing to plan and a different claim to make.")
        if self.scope is ContrastScope.SINGLE_IMAGE and len(self.image_ids) != 1:
            raise ValueError(
                f"{self.contrast_id} declares itself single-image over {self.image_ids!r}.")
        return self


# ── 5. what it inferred ─────────────────────────────────────────────────────

class RelationKind(str, Enum):
    """The closed grammar of how two observations can stand to one another.

    Closed, and topic-free: every member describes a SHAPE of relation that could hold between
    observations of anything at all. `UNKNOWN` is a legal outcome and a visible one — a relation
    the model could not type is better kept and marked than dropped or forced into the nearest
    member, which is how a vocabulary quietly stops meaning anything.
    """
    CONTRAST = "contrast"
    SHARED_ORGANIZATION = "shared_organization"
    DIVERGENT_TREATMENT = "divergent_treatment"
    ANALOGY = "analogy"
    SCALE_VARIATION = "scale_variation"
    COMPOSITIONAL = "compositional"
    CAUSAL_HYPOTHESIS = "causal_hypothesis"
    UNKNOWN = "unknown"


class CandidateRelation(_Strict):
    """A relation Semant proposes between two observations. CANDIDATE is the whole word.

    Nothing here has been accepted. `RelationCritique` is a separate object by a separate producer,
    for the same reason the alignment is a third object: a relation carrying its own verdict is a
    thing that grades itself, and the grade it gives itself is the one it was built to earn.

    `counterevidence` is a list on the relation rather than a field on the critique, because the
    proposer is the one who knows what it had to set aside. A relation that names none is not
    thereby unopposed; it is a relation whose proposer did not look, and the critic reads the empty
    list as exactly that.
    """
    schema_version: str = SCHEMA_VERSION
    relation_id: str = Field(..., min_length=1)
    left_observation_id: str = Field(..., min_length=1)
    right_observation_id: str = Field(..., min_length=1)
    relation_kind: RelationKind
    explanation: str = Field(..., min_length=1)
    image_ids: List[str] = Field(..., min_length=1)
    inquiry_relevance: str = Field(..., min_length=1, description="why this bears on the question")
    epistemic_status: EpistemicStatus = EpistemicStatus.INTERPRETIVE
    hypothesis_refs: List[str] = Field(default_factory=list)
    uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    counterevidence: List[str] = Field(default_factory=list)
    contrast_ref: str = Field(default="", description="the plan this answers, if one")
    scope: ContrastScope = ContrastScope.CROSS_IMAGE
    measurement: Optional[MeasurementProvenance] = None
    origin: Literal[MaterialOrigin.SEMANT_INFERENCE] = MaterialOrigin.SEMANT_INFERENCE
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def _readable(cls, value: str) -> str:
        return _require_readable(value)

    @field_validator("relation_id")
    @classmethod
    def _own_prefix(cls, value: str) -> str:
        return _require_prefix(value, "candidate_relation")

    @field_validator("left_observation_id", "right_observation_id")
    @classmethod
    def _point_at_observations(cls, value: str) -> str:
        return _require_prefix(value, "visual_observation")

    @field_validator("hypothesis_refs")
    @classmethod
    def _point_at_hypotheses(cls, refs: List[str]) -> List[str]:
        return [_require_prefix(r, "user_hypothesis") for r in refs]

    @field_validator("contrast_ref")
    @classmethod
    def _points_at_a_contrast(cls, value: str) -> str:
        return _require_prefix(value, "contrast_plan") if value else value

    @field_validator("explanation", "inquiry_relevance")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _require_nonblank(value, "a relation's own sentences")

    @field_validator("image_ids")
    @classmethod
    def _distinct_images(cls, ids: List[str]) -> List[str]:
        cleaned = [_require_nonblank(i, "image_ids") for i in ids]
        _require_unique(cleaned, "image_ids")
        return cleaned

    @model_validator(mode="after")
    def _stands_between_two_things(self) -> "CandidateRelation":
        if self.left_observation_id == self.right_observation_id:
            raise ValueError(
                f"{self.relation_id} relates {self.left_observation_id} to itself. A relation with "
                f"one side is a description, and describing an observation twice does not make a "
                f"comparison.")
        if self.scope is ContrastScope.CROSS_IMAGE and len(self.image_ids) < 2:
            raise ValueError(
                f"{self.relation_id} claims to be cross-image over {self.image_ids!r}. A relation "
                f"cannot claim to cross pictures unless its observations resolve to at least two.")
        _require_measurement(self.epistemic_status, self.measurement, self.relation_id)
        return self

    def observation_refs(self) -> Tuple[str, str]:
        return (self.left_observation_id, self.right_observation_id)

    def is_cross_image(self) -> bool:
        """What the relation DECLARES. Whether it is true of the observations is `check_resolves`,
        and the two are kept apart on purpose: a declaration is checkable only against something,
        and the something is a set of observations this object does not hold."""
        return self.scope is ContrastScope.CROSS_IMAGE and len(self.image_ids) >= 2


# ── 6. what a critic accepted or refused ────────────────────────────────────

class CritiqueVerdict(str, Enum):
    """Four verdicts, and `UNRESOLVED` is not a polite `ACCEPTED`.

    A critic that had to choose between accept and reject would accept whatever it could not
    disprove, which converts every ambiguity into a finding. `REVISE` and `UNRESOLVED` are where
    that pressure goes instead.
    """
    ACCEPTED = "accepted"
    REVISE = "revise"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class ParrotAssessment(str, Enum):
    """Whether the relation says anything the prompt did not already say.

    THE FAILURE MODE THIS SYSTEM IS MOST EXPOSED TO. A model handed a question and some pictures
    will restate the question about the pictures, and the restatement will be fluent, on-topic and
    empty. `ECHOES_PROMPT` — uses the person's words, adds something — is legal. `PARROTS_PROMPT`
    is not acceptable, ever.
    """
    NOT_PARROTING = "not_parroting"
    ECHOES_PROMPT = "echoes_prompt"
    PARROTS_PROMPT = "parrots_prompt"
    UNASSESSED = "unassessed"


class SourceCompleteness(str, Enum):
    """Whether everything the relation rests on is present and resolvable."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    UNASSESSED = "unassessed"


class ImageDiversity(str, Enum):
    """What the relation actually spans, as the critic found it — not as it declared itself."""
    CROSS_IMAGE = "cross_image"
    SINGLE_IMAGE = "single_image"
    UNASSESSED = "unassessed"


class Relevance(str, Enum):
    """Whether it bears on the question that was asked, rather than on a question it answers well."""
    RELEVANT = "relevant"
    TANGENTIAL = "tangential"
    IRRELEVANT = "irrelevant"
    UNASSESSED = "unassessed"


class InferenceSupport(str, Enum):
    """Whether the explanation follows from the observations, or arrives from somewhere else."""
    SUPPORTED = "supported"
    UNSUPPORTED_LEAP = "unsupported_leap"
    UNASSESSED = "unassessed"


#: The assessments that must all be made before anything may be accepted, with the value each must
#: NOT hold. Declared as a table rather than as a chain of `if`s so the gate can be read, quoted in
#: the refusal, and tested member by member.
ACCEPTANCE_GATE: Tuple[Tuple[str, Tuple[Any, ...]], ...] = (
    ("source_completeness", (SourceCompleteness.PARTIAL, SourceCompleteness.MISSING,
                             SourceCompleteness.UNASSESSED)),
    ("unsupported_inference", (InferenceSupport.UNSUPPORTED_LEAP, InferenceSupport.UNASSESSED)),
    ("prompt_parroting", (ParrotAssessment.PARROTS_PROMPT, ParrotAssessment.UNASSESSED)),
    ("inquiry_relevance", (Relevance.IRRELEVANT, Relevance.UNASSESSED)),
)


class RelationCritique(_Strict):
    """A verdict on ONE relation, by a producer that did not propose it.

    THE ACCEPT GATE IS THE POINT OF THIS OBJECT. `ACCEPTED` is not a field a critic sets; it is a
    conclusion that four separate assessments have to permit, and `UNASSESSED` blocks it as firmly
    as a negative does. A critic that accepted what it had not examined would be a rubber stamp
    with extra fields, and the shape of that failure — everything accepted, nothing assessed — is
    exactly what an automated critic drifts toward under load.

    `missing_capability` does NOT block acceptance, deliberately. Most relations worth keeping are
    interpretive and always will be; refusing to accept anything until an instrument exists would
    make the critic a capability tracker rather than a critic. It is recorded, and it is what
    `IntelligenceOutcome.CAPABILITY_GAP` is counted from.
    """
    schema_version: str = SCHEMA_VERSION
    critique_id: str = Field(..., min_length=1)
    relation_id: str = Field(..., min_length=1)
    verdict: CritiqueVerdict
    prompt_parroting: ParrotAssessment = ParrotAssessment.UNASSESSED
    source_completeness: SourceCompleteness = SourceCompleteness.UNASSESSED
    image_diversity: ImageDiversity = ImageDiversity.UNASSESSED
    inquiry_relevance: Relevance = Relevance.UNASSESSED
    unsupported_inference: InferenceSupport = InferenceSupport.UNASSESSED
    speculative_or_historical_warning: str = Field(
        default="", description="a reading that goes beyond the picture, named rather than removed")
    missing_capability_classes: List[CapabilityClass] = Field(default_factory=list)
    explanation: str = Field(..., min_length=1)
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def _readable(cls, value: str) -> str:
        return _require_readable(value)

    @field_validator("critique_id")
    @classmethod
    def _own_prefix(cls, value: str) -> str:
        return _require_prefix(value, "relation_critique")

    @field_validator("relation_id")
    @classmethod
    def _points_at_a_relation(cls, value: str) -> str:
        return _require_prefix(value, "candidate_relation")

    @field_validator("explanation")
    @classmethod
    def _says_why(cls, value: str) -> str:
        return _require_nonblank(value, "explanation")

    @model_validator(mode="after")
    def _nothing_is_accepted_unexamined(self) -> "RelationCritique":
        if self.verdict is not CritiqueVerdict.ACCEPTED:
            return self
        blocking = [(name, getattr(self, name)) for name, refused in ACCEPTANCE_GATE
                    if getattr(self, name) in refused]
        if blocking:
            raise ValueError(
                f"{self.critique_id} accepts {self.relation_id} while "
                + "; ".join(f"{name}={value.value!r}" for name, value in blocking)
                + ". Acceptance is a conclusion four assessments have to permit, and `unassessed` "
                  "blocks it as firmly as a negative does: a critic that accepts what it has not "
                  "examined is a rubber stamp with extra fields.")
        return self

    def accepted(self) -> bool:
        return self.verdict is CritiqueVerdict.ACCEPTED


# ── 7. whether any of it was any good ───────────────────────────────────────

class WorkflowCompletion(str, Enum):
    """Did the machinery finish. Nothing more."""
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class IntelligenceOutcome(str, Enum):
    """Was it worth doing. A different question, on a different axis, and it is the one that gets
    quietly answered by the first if the two share a field.

    `UNDERPERFORMED` is the member that has to exist and has to be reachable from a clean run: the
    pipeline did everything it was asked, and what came out was not worth the person's attention.
    A vocabulary in which a finished run is a successful one cannot express the most likely result
    this system produces.
    """
    USEFUL_RELATIONS = "useful_relations"
    UNDERPERFORMED = "underperformed"
    INSUFFICIENT_OBSERVATIONS = "insufficient_observations"
    PROMPT_DOMINATED = "prompt_dominated"
    TRUNCATED = "truncated"
    CAPABILITY_GAP = "capability_gap"
    REFUSED = "refused"
    ERROR = "error"


#: Outcomes a run that did not finish may not claim. A failed workflow can still have produced
#: something interesting, but "useful relations" is a report about the whole, and there was no whole.
OUTCOMES_NEEDING_A_FINISH: Tuple[IntelligenceOutcome, ...] = (IntelligenceOutcome.USEFUL_RELATIONS,)


class IntelligenceCounts(_Strict):
    """What was produced, counted. The counts are what make the outcome checkable rather than
    asserted — an outcome with no arithmetic behind it is a mood."""
    hypotheses: int = Field(default=0, ge=0)
    observations: int = Field(default=0, ge=0)
    refused_observations: int = Field(default=0, ge=0)
    measured_observations: int = Field(default=0, ge=0)
    alignments: int = Field(default=0, ge=0)
    contrasts: int = Field(default=0, ge=0)
    relations: int = Field(default=0, ge=0)
    accepted_relations: int = Field(default=0, ge=0)
    accepted_cross_image_relations: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _subsets_are_subsets(self) -> "IntelligenceCounts":
        for smaller, larger in (("accepted_relations", "relations"),
                                ("accepted_cross_image_relations", "accepted_relations"),
                                ("measured_observations", "observations"),
                                ("refused_observations", "observations")):
            if getattr(self, smaller) > getattr(self, larger):
                raise ValueError(
                    f"{smaller}={getattr(self, smaller)} exceeds {larger}={getattr(self, larger)}")
        return self


class IntelligenceOutcomeRecord(_Strict):
    """TWO FIELDS, TWO AXES, and the whole object exists to keep them apart.

    `workflow` says whether the machinery finished. `outcome` says whether the result was worth
    having. A single `status` field collapses them, and it always collapses in the same direction:
    the run finished, so it is reported as a success, and the person is handed a fluent restatement
    of their own question as though it were a finding.

    THE ONE ARITHMETIC RULE. A comparative inquiry that produced claims and zero ACCEPTED
    CROSS-IMAGE relations may not call itself `useful_relations`. That is the specific shape this
    system fails in — plenty of observations, plenty of sentences, nothing that ever crossed from
    one picture to another — and it is a shape a reader cannot see from a status word.
    """
    schema_version: str = SCHEMA_VERSION
    outcome_id: str = Field(..., min_length=1)
    inquiry_id: str = Field(..., min_length=1)
    comparative: bool = Field(..., description="did the question ask for a comparison at all")
    workflow: WorkflowCompletion
    outcome: IntelligenceOutcome
    counts: IntelligenceCounts = Field(default_factory=IntelligenceCounts)
    explanation: str = Field(..., min_length=1)
    limitations: List[str] = Field(default_factory=list)
    provenance: Provenance

    @field_validator("schema_version")
    @classmethod
    def _readable(cls, value: str) -> str:
        return _require_readable(value)

    @field_validator("outcome_id")
    @classmethod
    def _own_prefix(cls, value: str) -> str:
        return _require_prefix(value, "intelligence_outcome")

    @field_validator("explanation")
    @classmethod
    def _says_why(cls, value: str) -> str:
        return _require_nonblank(value, "explanation")

    @model_validator(mode="after")
    def _success_is_earned_rather_than_declared(self) -> "IntelligenceOutcomeRecord":
        if self.outcome is IntelligenceOutcome.USEFUL_RELATIONS:
            if self.counts.accepted_relations < 1:
                raise ValueError(
                    f"{self.outcome_id} reports useful_relations with "
                    f"{self.counts.accepted_relations} accepted relation(s). Useful is a claim "
                    f"about what a critic let through, not about what was produced.")
            if self.comparative and self.counts.accepted_cross_image_relations < 1:
                raise ValueError(
                    f"{self.outcome_id} is a comparative inquiry reporting useful_relations with "
                    f"{self.counts.accepted_relations} accepted relation(s), none of which crosses "
                    f"images. Plenty of observations and nothing that ever crossed from one "
                    f"picture to another is the specific way this system fails, and it is not a "
                    f"success — `underperformed` is the honest word for it.")
        if self.outcome in OUTCOMES_NEEDING_A_FINISH and self.workflow is WorkflowCompletion.FAILED:
            raise ValueError(
                f"{self.outcome_id} reports {self.outcome.value!r} on a workflow that FAILED. The "
                f"outcome is a report about the whole run, and there was no whole run.")
        if (self.outcome is IntelligenceOutcome.INSUFFICIENT_OBSERVATIONS
                and self.counts.accepted_relations > 0):
            raise ValueError(
                f"{self.outcome_id} blames insufficient observations while {self.counts.accepted_relations} "
                f"relation(s) were accepted from them.")
        return self

    def finished(self) -> bool:
        """Did the machinery complete. NOT whether the result was worth anything."""
        return self.workflow is WorkflowCompletion.COMPLETED

    def was_useful(self) -> bool:
        """Was the result worth the person's attention. NOT whether the machinery completed."""
        return self.outcome is IntelligenceOutcome.USEFUL_RELATIONS


# ── resolution: a reference is a promise, and this is how it is kept ─────────

class UnresolvedReference(ValueError):
    """A reference that names nothing. Its own type so a caller can tell a dangling pointer from a
    malformed object — the two want different repairs, and `driver_failed:ValueError` tells a
    reader neither."""


def index_observations(observations: Sequence["VisualObservation"]) -> Dict[str, "VisualObservation"]:
    index: Dict[str, VisualObservation] = {}
    for observation in observations:
        if observation.observation_id in index:
            raise ValueError(f"{observation.observation_id} appears twice in the same set")
        index[observation.observation_id] = observation
    return index


def resolve_observations(refs: Sequence[str],
                         observations: Sequence["VisualObservation"]) -> List["VisualObservation"]:
    """Every ref, or an exception naming the first that missed. No partial resolution.

    Returning what it could find would let a caller compute over a subset and report the whole —
    which is the shape of every "it said it compared four and compared two" failure.
    """
    index = index_observations(observations)
    out = []
    for ref in refs:
        if ref not in index:
            raise UnresolvedReference(
                f"{ref!r} names no observation in this set ({len(index)} known). A relation whose "
                f"sides do not resolve is a sentence about nothing.")
        out.append(index[ref])
    return out


def images_of(refs: Sequence[str], observations: Sequence["VisualObservation"]) -> List[str]:
    """The distinct images the referenced observations are ABOUT, in first-seen order."""
    seen: List[str] = []
    for observation in resolve_observations(refs, observations):
        if observation.image_id not in seen:
            seen.append(observation.image_id)
    return seen


def check_resolves(item: Any, observations: Sequence["VisualObservation"]) -> List[str]:
    """A contrast or a relation against the observations it names. Returns the resolved images.

    THE DECLARED IMAGES MUST EQUAL THE RESOLVED ONES. Checking only the count would accept a
    cross-image claim whose two observations are both about one picture and whose `image_ids`
    happen to list two — which is precisely the lie the invariant is written against.
    """
    refs = (list(item.observation_refs()) if hasattr(item, "observation_refs")
            else list(item.observation_ids))
    resolved = images_of(refs, observations)
    declared = list(item.image_ids)
    if sorted(resolved) != sorted(declared):
        raise UnresolvedReference(
            f"declares images {declared!r} and its observations resolve to {resolved!r}. A "
            f"declaration that does not match what the observations are about is the form a "
            f"cross-image claim takes when nothing crossed.")
    if getattr(item, "scope", None) is ContrastScope.CROSS_IMAGE and len(resolved) < 2:
        raise UnresolvedReference(
            f"claims to cross pictures and resolves to {resolved!r}.")
    return resolved


# ── the shared checks ────────────────────────────────────────────────────────

def _require_prefix(value: str, kind: str) -> str:
    prefix = PREFIXES[kind]
    if not str(value).startswith(prefix):
        raise ValueError(f"a {kind} id must start with {prefix!r}; got {value!r}")
    return str(value)


def _require_nonblank(value: str, what: str) -> str:
    """Non-empty AFTER stripping, and the stripped form is what gets stored.

    `min_length=1` is not this check. A single space satisfies it, and a whitespace image id is an
    observation that will resolve to nothing at exactly the moment somebody tries to go and look at
    the picture — which is the one thing an observation is for.
    """
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{what} is blank; whitespace is not a value anything can resolve")
    return text


def _require_readable(value: str) -> str:
    if value not in READABLE_SCHEMA_VERSIONS:
        raise ValueError(
            f"schema_version {value!r} is not one this code reads "
            f"({list(READABLE_SCHEMA_VERSIONS)}). A version bump is a reviewed change, not "
            f"something a payload declares for itself.")
    return value


def _require_unique(values: Sequence[str], what: str) -> None:
    seen = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{what} names {value!r} twice; a reference to it would be ambiguous")
        seen.add(value)


def _require_measurement(status: EpistemicStatus, measurement: Optional[MeasurementProvenance],
                         ref: str) -> None:
    """The one rule every status-carrying model shares, in one place so it cannot drift.

    Both directions are errors. `measured` with nothing that measured is the obvious one; a
    measurement attached to something still calling itself interpretive is the quieter one, and it
    matters because a reader filtering on status would miss evidence that exists.
    """
    if status is EpistemicStatus.MEASURED and measurement is None:
        raise ValueError(
            f"{ref} claims {MEASURED_STATUS.value!r} with no measurement provenance. Measured is "
            f"not a confidence level and not a thing a model may assert about its own output: it "
            f"requires a capability class, the instrument that ran it, and evidence to go and look "
            f"at. Model agreement is not a path to it.")
    if status is not EpistemicStatus.MEASURED and measurement is not None:
        raise ValueError(
            f"{ref} carries measurement provenance while calling itself {status.value!r}. If an "
            f"instrument produced evidence for it, say so in the status; if it did not, the "
            f"provenance is describing something else.")
