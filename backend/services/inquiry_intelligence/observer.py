"""
INTELLIGENCE-002A — two passes over the images, and the wall between them.

    images                  →  prompt-blind observation   →  VisualObservation
    InquiryMap + those      →  prompt-aware alignment     →  HypothesisAlignment

TWO PASSES, NOT ONE, AND THE ORDER IS THE ARCHITECTURE. A model shown "I think the drapery is
doing the work" and a picture will find drapery doing work. It is not lying; it is answering the
question it was asked, and the resulting sentence is indistinguishable from one produced by
looking. The only way to know whether the picture supports the person is to look at the picture
BEFORE knowing what they hoped.

## Guard 1 — structural: there is no parameter for the prompt

`observe_images(images, client, *, ids)` takes images and a client. There is no `prompt`, no
`inquiry`, no `context`, no `**kwargs`. Adding one is a visible edit to a signature, reviewed as
such, which is a different kind of event from someone passing an extra dict through.

## Guard 2 — sealed: the request has nowhere to put prompt text

`BlindObservationRequest` is frozen and carries an image reference and an instruction. The
instruction is not the caller's to choose: `__post_init__` refuses anything other than the module
constant `BLIND_INSTRUCTION`, so the obvious smuggling channel raises `PromptLeak` at construction
rather than arriving at a provider. `ImageRef` is likewise bounded — short, newline-free
identifiers — because a free-text field on the one object that DOES reach the model is the second
channel, and "the source path" is exactly where a paragraph would be parked.

## Guard 3 — typed: alignment will only accept a set the blind pass built

`align_hypotheses` requires a `BlindObservationSet`, which only `observe_images` constructs. A
prompt-aware pass cannot hand its own output back in as "the observations", because it cannot
produce that type without going through the blind path.

## Guard 4 — the alignment pass cannot mint an observation

`align_hypotheses` never constructs a `VisualObservation`. Not "must not": the call does not appear
anywhere in its path, and a test asserts that over the source. Every observation id an alignment
cites is checked against the frozen set the blind pass produced; an id that is not in it produces
a `RefusedAlignment`, never a new observation with that id. And `SUPPORTS`, `COMPLICATES` and
`CHALLENGES` each require at least one real observation id — you cannot support a hypothesis out
of nothing, so the empty-cited relations are exactly the two that admit to having nothing:
`DOES_NOT_BEAR_ON` and `CANNOT_DETERMINE`.

## Guard 5 — nothing here is measured

Spine rules 8 and 9. A VLM's reading is INTERPRETIVE, whatever it calls itself, until an actual
measuring capability supports it — and agreement between models is not a measuring capability, so
`AGREEMENT_PSEUDO_CAPABILITIES` is refused by name. The model's own claim is not discarded: it is
recorded verbatim on `claimed_status` so `observation_audit.py` can see that it was made. A parser
that quietly rewrote "measured" to "interpretive" would keep the audit green forever while the
model went on claiming measurement into every reply.

## The model boundary

The role is a shape, not a provider. `BlindObservationClient` and `AlignmentClient` are Protocols;
`FrozenClient` replays committed records and can call nothing, `TransportClient` wraps an injected
callable. Both carry a `ModelIdentity` naming an `ExecutionIdentity` AND a `ProviderKind`, because
"a local Qwen ran this" and "a hosted endpoint ran this" are two facts a run must not blur, and
neither is the same as "this was replayed". A frozen client may not wear LIVE and a transport
client may not wear REPLAY; both are refused at construction.

PURE MODULE. No database, no network, no provider SDK, no image decoding. The transport is
injected; the tests drive frozen records.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import (Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Protocol, Sequence,
                    Tuple, runtime_checkable)

from backend.services.epistemics import EpistemicStatus
from backend.services.inquiry_intelligence.intent import InquiryMap

OBSERVER_VERSION = "visual-observer.v1"


# ── identity: who ran this, and in what sense it ran ─────────────────────────

class ExecutionIdentity(str, Enum):
    """Mirrors `backend/schemas/perception_lab.py`'s enum by value, deliberately.

    NOT IMPORTED. The intelligence section names its own provenance; it should not have to import
    the laboratory's record schema — and pydantic — to say the word REPLAY. The three values are a
    house vocabulary rather than the lab's property, and `test_inquiry_observer.py` asserts the two
    enums still agree, so the mirror is checked rather than trusted.
    """
    LIVE = "LIVE"        # something was actually called
    REPLAY = "REPLAY"    # a prior call, re-shown. Nothing callable is in reach.
    FIXTURE = "FIXTURE"  # committed data that was never a call at all


class ProviderKind(str, Enum):
    """WHERE the answer came from. Orthogonal to `ExecutionIdentity`, and needed alongside it.

    LIVE alone does not say whether a person's images left the machine. HOSTED and LOCAL are the
    same identity and a different fact, and rule 11 asks for both to stay explicit — so a future
    local Qwen is a `ProviderKind.LOCAL`, not a hosted provider with a different model string.
    """
    HOSTED = "hosted"      # an endpoint over the network
    LOCAL = "local"        # a model resident on this machine
    RECORDED = "recorded"  # a frozen reply; no provider ran


@dataclass(frozen=True)
class ModelIdentity:
    identity: ExecutionIdentity
    provider_kind: ProviderKind
    provider: str
    model: str
    revision: str = ""

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip():
            raise ProvenanceError(
                "a model identity names its provider and its model. An unnamed provider reads as "
                "'somewhere' in a run record, which is the one thing a provenance field must "
                "never be allowed to mean.")


class ProvenanceError(ValueError):
    """An identity that would record something untrue about how an answer was obtained."""


class PromptLeak(RuntimeError):
    """Something tried to reach the prompt-blind pass with the person's words."""


class NothingRecorded(LookupError):
    """A frozen client was asked for a reply it does not hold. It will not compute one."""


class ObservationParseError(ValueError):
    """A reply is not shaped like a reply. Distinct from a reply that is shaped right and wrong —
    that one becomes observations, and the audit is what judges them."""


# ── what reaches the model, and what may not ─────────────────────────────────

#: Bounds on the one object that crosses to the provider. Prompt text is a paragraph; an id is
#: not. These caps are the difference.
MAX_REF_LENGTH = 512


@dataclass(frozen=True)
class ImageRef:
    """A picture, named. Short, newline-free identifiers — see Guard 2 in the module docstring."""
    image_id: str
    source: str
    media_type: str = ""
    checksum: str = ""

    def __post_init__(self) -> None:
        for name in ("image_id", "source", "media_type", "checksum"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise PromptLeak(f"{name} is a {type(value).__name__}; an image reference is text")
            if "\n" in value or "\r" in value:
                raise PromptLeak(
                    f"{name} contains a newline. An image reference is an identifier, and a "
                    f"multi-line one is a paragraph riding into the prompt-blind pass.")
            if len(value) > MAX_REF_LENGTH:
                raise PromptLeak(
                    f"{name} is {len(value)} characters, over the {MAX_REF_LENGTH} allowed for an "
                    f"identifier.")
        if not self.image_id.strip():
            raise PromptLeak("an image reference needs an id")


#: The ONLY instruction the prompt-blind pass may send. A constant rather than an argument, so the
#: seam that would carry the person's words has no give in it. It names the fields it wants and
#: says nothing about what the picture is of.
BLIND_INSTRUCTION = (
    "Describe what is present in this image and how it is organised. For each thing you notice, "
    "give: the feature; where in the image it is; how it is organised; the effect of its "
    "appearance; one interpretive possibility it leaves open; and what you are unsure of. "
    "Describe only this image. Do not guess what question is being asked of it."
)


@dataclass(frozen=True)
class BlindObservationRequest:
    """One image, one fixed instruction. Nothing else may travel."""
    image: ImageRef
    instruction: str = BLIND_INSTRUCTION

    def __post_init__(self) -> None:
        if self.instruction != BLIND_INSTRUCTION:
            raise PromptLeak(
                "the prompt-blind instruction is not the caller's to choose. This field is the "
                "obvious place to park the person's question, which is why it is sealed rather "
                "than defaulted.")

    def payload(self) -> Dict[str, Any]:
        return {"instruction": self.instruction,
                "image": {"image_id": self.image.image_id, "source": self.image.source,
                          "media_type": self.image.media_type,
                          "checksum": self.image.checksum}}


@dataclass(frozen=True)
class AlignmentRequest:
    """The prompt-aware pass, and it is allowed to be: it gets the map AND the frozen observations.

    What it does not get is any way to add to the second. The observations here are the ones the
    blind pass produced, carried by id, and `align_hypotheses` checks every id that comes back.
    """
    inquiry: InquiryMap
    observations: Tuple["VisualObservation", ...]

    def payload(self) -> Dict[str, Any]:
        return {
            "prompt": self.inquiry.prompt,
            "hypotheses": [{"hypothesis_id": h.hypothesis_id, "claim": h.claim,
                            "stance": h.stance.value} for h in self.inquiry.hypotheses],
            "observations": [{"observation_id": o.observation_id, "image_ref": o.image_ref,
                              "feature": o.feature, "locus": o.locus,
                              "visible_organization": o.visible_organization,
                              "appearance_effect": o.appearance_effect,
                              "uncertainty": o.uncertainty} for o in self.observations],
            "relations": [r.value for r in AlignmentRelation],
        }


# ── the observation ──────────────────────────────────────────────────────────

#: Words that have been offered as grounds for calling a reading `measured`, and are not.
#: Rule 9: nothing becomes measured merely through model agreement. Named rather than implied,
#: because "three models agreed" is a persuasive sentence and someone will write it.
AGREEMENT_PSEUDO_CAPABILITIES: FrozenSet[str] = frozenset({
    "agreement", "consensus", "majority", "vote", "voting", "ensemble", "self_consistency",
    "self-consistency", "model_agreement", "models_agreed", "cross_model", "concordance",
})


@dataclass(frozen=True)
class MeasurementEvidence:
    """A number from a capability that actually measures, and the artifact it came off.

    The only thing that lifts an observation out of `interpretive`. Refuses the pseudo-capabilities
    at construction, so the lift cannot be performed by naming agreement as the instrument.
    """
    capability: str
    quantity: str
    value: float
    units: str
    artifact_ref: str

    def __post_init__(self) -> None:
        key = self.capability.strip().lower().replace(" ", "_")
        if not key:
            raise ProvenanceError("measurement evidence names the capability that produced it")
        if key in AGREEMENT_PSEUDO_CAPABILITIES:
            raise ProvenanceError(
                f"{self.capability!r} is agreement, not measurement. Models concurring is a fact "
                f"about the models; it says nothing about the image, and a reading does not "
                f"become measured by being popular.")
        if not self.artifact_ref.strip():
            raise ProvenanceError(
                "measurement evidence cites the artifact it was computed off. A number with no "
                "artifact behind it is a claim about a measurement, not a measurement.")


@dataclass(frozen=True)
class ObservationProvenance:
    model: ModelIdentity
    request_id: str
    measurement: Optional[MeasurementEvidence] = None


@dataclass(frozen=True)
class VisualObservation:
    """One thing noticed in one image, and everything needed to doubt it.

    THE SIX CONTENT FIELDS ARE NOT SYNONYMS. `visible_organization` is what is there and how it is
    arranged. `appearance_effect` is what that arrangement does to the look of the thing.
    `interpretive_possibility` is what it might mean — and it is a separate field precisely so
    that meaning is never smuggled into the description of what is present. `observation_audit.py`
    enforces the difference, which it can only do because the three are apart.

    `image_ref` is stamped by the observer from the request. `claimed_image_ref` is what the model
    said, when it said anything, and the two differing is a finding rather than a correction.
    """
    observation_id: str
    image_ref: str
    feature: str
    locus: str
    visible_organization: str
    appearance_effect: str
    interpretive_possibility: str
    uncertainty: str
    provenance: Optional[ObservationProvenance] = None
    epistemic_status: EpistemicStatus = EpistemicStatus.INTERPRETIVE
    claimed_status: str = ""
    claimed_image_ref: str = ""

    @property
    def described_fields(self) -> Tuple[Tuple[str, str], ...]:
        """(field_name, text) for everything the model wrote. What the audit reads."""
        return (("feature", self.feature), ("locus", self.locus),
                ("visible_organization", self.visible_organization),
                ("appearance_effect", self.appearance_effect),
                ("interpretive_possibility", self.interpretive_possibility),
                ("uncertainty", self.uncertainty))


@dataclass(frozen=True)
class BlindObservationSet:
    """The output of the prompt-blind pass, and the ONLY thing alignment accepts.

    Only `observe_images` constructs this. That is Guard 3: a prompt-aware pass cannot present its
    own findings as the blind record, because it has no way to produce this type.
    """
    observations: Tuple[VisualObservation, ...]
    images: Tuple[ImageRef, ...]
    per_image: bool = True
    observer: str = OBSERVER_VERSION
    failures: Tuple[str, ...] = ()

    @property
    def ids(self) -> FrozenSet[str]:
        return frozenset(o.observation_id for o in self.observations)

    def for_image(self, image_id: str) -> Tuple[VisualObservation, ...]:
        return tuple(o for o in self.observations if o.image_ref == image_id)


# ── alignment ────────────────────────────────────────────────────────────────

class AlignmentRelation(str, Enum):
    """The five things an observation can do to a hypothesis, and nothing else.

    The last two are the deliverable. Without `DOES_NOT_BEAR_ON` a model asked "does this support
    the claim?" has only degrees of yes, and without `CANNOT_DETERMINE` it has no way to say the
    picture is silent — so both failures come back wearing weak support, which is the failure this
    whole section exists to prevent.
    """
    SUPPORTS = "supports"
    COMPLICATES = "complicates"
    CHALLENGES = "challenges"
    DOES_NOT_BEAR_ON = "does_not_bear_on"
    CANNOT_DETERMINE = "cannot_determine"


#: The three that are claims about the picture. Each needs at least one observation behind it.
GROUNDED_RELATIONS: FrozenSet[AlignmentRelation] = frozenset({
    AlignmentRelation.SUPPORTS, AlignmentRelation.COMPLICATES, AlignmentRelation.CHALLENGES})


class AlignmentRefusalCode(str, Enum):
    UNKNOWN_HYPOTHESIS = "unknown_hypothesis"
    UNKNOWN_OBSERVATION = "unknown_observation"
    UNKNOWN_RELATION = "unknown_relation"
    UNGROUNDED_RELATION = "ungrounded_relation"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class HypothesisAlignment:
    """One relation between one hypothesis and the observations that bear on it.

    NO FIELD HERE CAN HOLD AN OBSERVATION — only ids, and every id was checked. `reasoning` is
    prose about the relation; it is not carried forward as anything the picture showed, and
    nothing in this module turns it into a `VisualObservation`.
    """
    alignment_id: str
    hypothesis_id: str
    relation: AlignmentRelation
    observation_ids: Tuple[str, ...]
    reasoning: str = ""
    uncertainty: str = ""
    provenance: Optional[ObservationProvenance] = None


@dataclass(frozen=True)
class RefusedAlignment:
    """A relation the aligner would not record, and exactly why.

    Kept rather than dropped. A pass that silently discarded the four alignments citing invented
    observation ids would report six clean alignments out of ten and look better than a pass that
    had not hallucinated at all.
    """
    code: AlignmentRefusalCode
    detail: str
    offered: Mapping[str, Any]


@dataclass(frozen=True)
class AlignmentSet:
    alignments: Tuple[HypothesisAlignment, ...]
    refusals: Tuple[RefusedAlignment, ...] = ()
    observer: str = OBSERVER_VERSION

    @property
    def by_hypothesis(self) -> Dict[str, Tuple[HypothesisAlignment, ...]]:
        out: Dict[str, List[HypothesisAlignment]] = {}
        for a in self.alignments:
            out.setdefault(a.hypothesis_id, []).append(a)
        return {k: tuple(v) for k, v in out.items()}


# ── the model seam ───────────────────────────────────────────────────────────

@runtime_checkable
class BlindObservationClient(Protocol):
    """A client for the blind pass. One method, and it takes a sealed request."""

    @property
    def identity(self) -> ModelIdentity: ...

    def observe(self, request: BlindObservationRequest) -> Mapping[str, Any]: ...


@runtime_checkable
class AlignmentClient(Protocol):
    @property
    def identity(self) -> ModelIdentity: ...

    def align(self, request: AlignmentRequest) -> Mapping[str, Any]: ...


class FrozenClient:
    """Committed replies, handed back. It cannot compute one, and has nothing to compute with.

    No transport, no endpoint, no callable of any kind — the way `perception_lab.replay` is sealed.
    An image it holds no record for is `NothingRecorded`, never a fabricated reply and never a
    quiet empty list, because "nothing was recorded" and "the model saw nothing" are two different
    facts and only one of them is about the picture.

    REPLAY versus FIXTURE. A replay re-shows a call that happened; a fixture is data that was never
    a call. The class is the same and the badge is not, so a run record cannot say a hand-authored
    adversarial sample was once a live reading.
    """

    def __init__(self, identity: ModelIdentity,
                 observations: Optional[Mapping[str, Mapping[str, Any]]] = None,
                 alignments: Optional[Mapping[str, Any]] = None) -> None:
        if identity.identity is ExecutionIdentity.LIVE:
            raise ProvenanceError(
                "a frozen client may not wear LIVE. Nothing here calls anything, and a record "
                "saying otherwise would make LIVE mean 'some code ran', which is every run.")
        if identity.provider_kind is not ProviderKind.RECORDED:
            raise ProvenanceError(
                f"a frozen client's provider kind is RECORDED, not {identity.provider_kind.value}. "
                f"Naming the original provider here would report a hosted call that did not "
                f"happen in this run.")
        self._identity = identity
        self._observations = dict(observations or {})
        self._alignments = dict(alignments or {})

    @property
    def identity(self) -> ModelIdentity:
        return self._identity

    def observe(self, request: BlindObservationRequest) -> Mapping[str, Any]:
        key = request.image.image_id
        if key not in self._observations:
            raise NothingRecorded(
                f"no reply is recorded for image {key!r}. A frozen client will not produce one: "
                f"its content is the record of a reading that already happened.")
        return self._observations[key]

    def align(self, request: AlignmentRequest) -> Mapping[str, Any]:
        key = request.inquiry.prompt
        if key in self._alignments:
            return self._alignments[key]
        if "*" in self._alignments:
            return self._alignments["*"]
        raise NothingRecorded("no alignment reply is recorded for this prompt")


class TransportClient:
    """A live client over an injected callable. The provider lives on the other side of it.

    THE TRANSPORT IS THE WHOLE POINT. This module imports no SDK and opens no socket; it is handed
    `Callable[[Mapping], Mapping]` and calls it. A hosted endpoint and a resident Qwen are the same
    shape and different `ProviderKind`s, so adding the second is a construction site, not an edit
    to this class. Tests drive it with a plain function.
    """

    def __init__(self, transport: Callable[[Mapping[str, Any]], Mapping[str, Any]],
                 identity: ModelIdentity) -> None:
        if identity.identity is not ExecutionIdentity.LIVE:
            raise ProvenanceError(
                f"a transport client is LIVE by construction; it may not wear "
                f"{identity.identity.value}. Something calls out when this runs, and a REPLAY "
                f"badge over a live call is the one lie the identity vocabulary exists to catch.")
        if identity.provider_kind is ProviderKind.RECORDED:
            raise ProvenanceError("RECORDED belongs to a frozen client; this one calls something")
        if not callable(transport):
            raise ProvenanceError("a transport is callable")
        self._transport = transport
        self._identity = identity

    @property
    def identity(self) -> ModelIdentity:
        return self._identity

    def observe(self, request: BlindObservationRequest) -> Mapping[str, Any]:
        return self._transport({"role": "blind_observer", **request.payload()})

    def align(self, request: AlignmentRequest) -> Mapping[str, Any]:
        return self._transport({"role": "hypothesis_alignment", **request.payload()})


def hosted_client(transport: Callable[[Mapping[str, Any]], Mapping[str, Any]], *, provider: str,
                  model: str, revision: str = "") -> TransportClient:
    """An endpoint over the network. The person's images leave the machine; the record says so."""
    return TransportClient(transport, ModelIdentity(
        ExecutionIdentity.LIVE, ProviderKind.HOSTED, provider, model, revision))


def local_client(transport: Callable[[Mapping[str, Any]], Mapping[str, Any]], *, provider: str,
                 model: str, revision: str = "") -> TransportClient:
    """A model resident here. Same identity, different provider kind, and the difference matters
    to a person deciding what to put in front of it — which is why it is a field and not a note."""
    return TransportClient(transport, ModelIdentity(
        ExecutionIdentity.LIVE, ProviderKind.LOCAL, provider, model, revision))


def replay_client(observations: Optional[Mapping[str, Mapping[str, Any]]] = None,
                  alignments: Optional[Mapping[str, Any]] = None, *,
                  provider: str = "recorded", model: str = "recorded",
                  revision: str = "") -> FrozenClient:
    """A prior run, re-shown."""
    return FrozenClient(ModelIdentity(ExecutionIdentity.REPLAY, ProviderKind.RECORDED, provider,
                                      model, revision), observations, alignments)


def fixture_client(observations: Optional[Mapping[str, Mapping[str, Any]]] = None,
                   alignments: Optional[Mapping[str, Any]] = None, *,
                   provider: str = "committed", model: str = "committed",
                   revision: str = "") -> FrozenClient:
    """Committed data that was never a call. Not a replay, and the badge says which."""
    return FrozenClient(ModelIdentity(ExecutionIdentity.FIXTURE, ProviderKind.RECORDED, provider,
                                      model, revision), observations, alignments)


# ── ids ──────────────────────────────────────────────────────────────────────

@runtime_checkable
class IdFactory(Protocol):
    def next(self, kind: str) -> str: ...


class SequenceIds:
    """Deterministic ids, injected. No clock and no randomness, so a replay of the same records
    produces the same ids and two runs can be diffed rather than eyeballed."""

    def __init__(self, prefix: str = "") -> None:
        self._prefix = prefix
        self._counts: Dict[str, int] = {}

    def next(self, kind: str) -> str:
        self._counts[kind] = self._counts.get(kind, 0) + 1
        head = f"{self._prefix}_" if self._prefix else ""
        return f"{head}{kind}_{self._counts[kind]}"


# ── pass one: prompt-blind ───────────────────────────────────────────────────

def observe_images(images: Sequence[ImageRef], client: BlindObservationClient, *,
                   ids: Optional[IdFactory] = None) -> BlindObservationSet:
    """Each image, on its own, with no knowledge of what is being asked.

    ONE CALL PER IMAGE, and that is a claim about what the observations mean, not a batching
    choice. An image described alongside three others is described in their company: the second
    reading borrows the first's vocabulary, and the resemblance the run later reports was partly
    manufactured by the request. Cross-image work belongs after this, over these, and is not in
    this lane.

    A failing image does not fail the set — its failure is recorded and the rest proceed, because
    the useful answer to "one of five images was unreadable" is the other four plus that sentence.
    """
    factory = ids or SequenceIds()
    seen: Dict[str, ImageRef] = {}
    for image in images:
        if not isinstance(image, ImageRef):
            raise PromptLeak(f"images are ImageRefs; got {type(image).__name__}")
        if image.image_id in seen:
            raise PromptLeak(
                f"image id {image.image_id!r} appears twice. Two pictures under one id would make "
                f"every observation on them unattributable.")
        seen[image.image_id] = image

    observations: List[VisualObservation] = []
    failures: List[str] = []
    for image in images:
        request = BlindObservationRequest(image=image)
        try:
            reply = client.observe(request)
        except NothingRecorded as exc:
            failures.append(f"{image.image_id}: {exc}")
            continue
        except Exception as exc:                                # noqa: BLE001 — recorded, not raised
            failures.append(f"{image.image_id}: {type(exc).__name__}: {exc}")
            continue
        try:
            observations.extend(_parse_observations(reply, image, client.identity, factory))
        except ObservationParseError as exc:
            failures.append(f"{image.image_id}: {exc}")

    return BlindObservationSet(observations=tuple(observations), images=tuple(images),
                               per_image=True, failures=tuple(failures))


def _text(raw: Mapping[str, Any], *names: str) -> str:
    """A field, as text. Missing becomes empty — the audit is what calls that a problem.

    DELIBERATELY PERMISSIVE. A parser that raised on a missing `locus` would mean the audit's
    `MISSING_*` findings could never fire on a real reply, and the one thing this section needs is
    to be able to see a bad reading rather than never receive one.
    """
    for name in names:
        if name in raw and raw[name] is not None:
            value = raw[name]
            return value if isinstance(value, str) else str(value)
    return ""


def _parse_observations(reply: Mapping[str, Any], image: ImageRef, model: ModelIdentity,
                        ids: IdFactory) -> List[VisualObservation]:
    if not isinstance(reply, Mapping):
        raise ObservationParseError(f"a reply is a mapping; got {type(reply).__name__}")
    raw_list = reply.get("observations")
    if raw_list is None:
        raise ObservationParseError("the reply carries no 'observations' key")
    if not isinstance(raw_list, Sequence) or isinstance(raw_list, (str, bytes)):
        raise ObservationParseError(
            f"'observations' is a {type(raw_list).__name__}; a list was expected")

    request_id = ids.next("req")
    out: List[VisualObservation] = []
    for item in raw_list:
        if not isinstance(item, Mapping):
            raise ObservationParseError(
                f"an observation is a mapping; got {type(item).__name__}")
        measurement = _parse_measurement(item.get("measurement"))
        claimed_status = _text(item, "epistemic_status", "status")
        out.append(VisualObservation(
            observation_id=_text(item, "observation_id") or ids.next("obs"),
            image_ref=image.image_id,
            feature=_text(item, "feature"),
            locus=_text(item, "locus", "where"),
            visible_organization=_text(item, "visible_organization", "organization"),
            appearance_effect=_text(item, "appearance_effect", "effect"),
            interpretive_possibility=_text(item, "interpretive_possibility", "possibility"),
            uncertainty=_text(item, "uncertainty"),
            provenance=ObservationProvenance(model=model, request_id=request_id,
                                             measurement=measurement),
            epistemic_status=_settled_status(measurement),
            claimed_status=claimed_status,
            claimed_image_ref=_text(item, "image_ref", "image_id"),
        ))
    return out


def _parse_measurement(raw: Any) -> Optional[MeasurementEvidence]:
    """A measurement the model claims. Refused here if it names agreement as the instrument.

    Refused rather than downgraded, because a `MeasurementEvidence` in hand is what lets an
    observation out of `interpretive`, and one built on 'three models concurred' would let it out
    on rule 9's exact forbidden grounds.
    """
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return None
    try:
        return MeasurementEvidence(
            capability=str(raw.get("capability", "")),
            quantity=str(raw.get("quantity", "")),
            value=float(raw.get("value", 0.0)),
            units=str(raw.get("units", "")),
            artifact_ref=str(raw.get("artifact_ref", "")))
    except (ProvenanceError, TypeError, ValueError):
        return None


def _settled_status(measurement: Optional[MeasurementEvidence]) -> EpistemicStatus:
    """Rule 8, in one line. A reading is interpretive until a measuring capability supports it.

    The model's own word is not consulted. It is kept on `claimed_status` for the audit, because
    the model claiming measurement is a fact worth surfacing and a fact worth refusing, and those
    are two different jobs done in two different files.
    """
    return EpistemicStatus.MEASURED if measurement is not None else EpistemicStatus.INTERPRETIVE


# ── pass two: prompt-aware alignment ─────────────────────────────────────────

def align_hypotheses(inquiry: InquiryMap, observations: BlindObservationSet,
                     client: AlignmentClient, *,
                     ids: Optional[IdFactory] = None) -> AlignmentSet:
    """Relate what was seen to what was claimed. Add nothing to either.

    This function does not construct a `VisualObservation` and does not import a way to. Every
    observation id that comes back is checked against `observations.ids` — the set the blind pass
    froze — and an id outside it is a `RefusedAlignment`, which is the difference between "the
    model referred to something that does not exist" and "the model found a new thing".
    """
    if not isinstance(observations, BlindObservationSet):
        raise PromptLeak(
            f"alignment runs over a BlindObservationSet; got {type(observations).__name__}. Only "
            f"the prompt-blind pass builds one, which is what makes the ordering enforceable.")

    factory = ids or SequenceIds()
    request = AlignmentRequest(inquiry=inquiry, observations=observations.observations)
    known_observations = observations.ids
    known_hypotheses = inquiry.hypothesis_ids

    try:
        reply = client.align(request)
    except NothingRecorded as exc:
        return AlignmentSet(alignments=(), refusals=(RefusedAlignment(
            AlignmentRefusalCode.MALFORMED, str(exc), {}),))

    raw_list = reply.get("alignments") if isinstance(reply, Mapping) else None
    if not isinstance(raw_list, Sequence) or isinstance(raw_list, (str, bytes)):
        return AlignmentSet(alignments=(), refusals=(RefusedAlignment(
            AlignmentRefusalCode.MALFORMED,
            "the reply carries no 'alignments' list", {"reply_type": type(reply).__name__}),))

    accepted: List[HypothesisAlignment] = []
    refused: List[RefusedAlignment] = []
    provenance = ObservationProvenance(model=client.identity, request_id=factory.next("req"))

    for item in raw_list:
        if not isinstance(item, Mapping):
            refused.append(RefusedAlignment(AlignmentRefusalCode.MALFORMED,
                                            f"an alignment is a mapping; got "
                                            f"{type(item).__name__}", {}))
            continue
        hypothesis_id = str(item.get("hypothesis_id", ""))
        if hypothesis_id not in known_hypotheses:
            refused.append(RefusedAlignment(
                AlignmentRefusalCode.UNKNOWN_HYPOTHESIS,
                f"{hypothesis_id!r} is not a hypothesis in this map", dict(item)))
            continue

        try:
            relation = AlignmentRelation(str(item.get("relation", "")))
        except ValueError:
            refused.append(RefusedAlignment(
                AlignmentRefusalCode.UNKNOWN_RELATION,
                f"{item.get('relation')!r} is not one of the five relations", dict(item)))
            continue

        raw_ids = item.get("observation_ids") or ()
        if isinstance(raw_ids, (str, bytes)):
            raw_ids = [raw_ids]
        cited = tuple(str(x) for x in raw_ids)
        unknown = tuple(x for x in cited if x not in known_observations)
        if unknown:
            refused.append(RefusedAlignment(
                AlignmentRefusalCode.UNKNOWN_OBSERVATION,
                f"cites {', '.join(repr(u) for u in unknown)}, which the prompt-blind pass did "
                f"not produce. An alignment may relate observations; it may not add one.",
                dict(item)))
            continue

        if relation in GROUNDED_RELATIONS and not cited:
            refused.append(RefusedAlignment(
                AlignmentRefusalCode.UNGROUNDED_RELATION,
                f"{relation.value!r} cites no observation. A hypothesis cannot be supported, "
                f"complicated or challenged out of nothing; the relations for having nothing are "
                f"{AlignmentRelation.DOES_NOT_BEAR_ON.value!r} and "
                f"{AlignmentRelation.CANNOT_DETERMINE.value!r}.", dict(item)))
            continue

        accepted.append(HypothesisAlignment(
            alignment_id=str(item.get("alignment_id") or factory.next("align")),
            hypothesis_id=hypothesis_id, relation=relation, observation_ids=cited,
            reasoning=_text(item, "reasoning"), uncertainty=_text(item, "uncertainty"),
            provenance=provenance))

    return AlignmentSet(alignments=tuple(accepted), refusals=tuple(refused))
