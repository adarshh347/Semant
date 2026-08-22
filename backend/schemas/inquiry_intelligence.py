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
RELATION between subjects is a closed enum. No enum in this file names a fold, a sculpture, a
building, a plant or any other rehearsal subject, and `test_inquiry_intelligence_contracts.py`
scans this module for exactly that — the same guard `semantic_compilation` lives under.

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
        cleaned = [str(i).strip() for i in ids if str(i).strip()]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError(f"the same image is named twice in {ids!r}")
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
