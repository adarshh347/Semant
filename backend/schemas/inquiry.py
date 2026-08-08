"""
HARNESS-001A — the `InquiryFrame`: what a prompt turns into before anything is looked at.

WHAT THIS OBJECT IS. A structured, inspectable reading OF A QUESTION. It says what the person
asked for, what kind of knowing each part of it wants, which grammar-valid acts could serve it,
what nothing can operationalise, and what the available measurements will not exhaust even if
they all succeed.

WHAT IT IS NOT, and every field below is shaped by this. It is not a result, not a finding, not a
percept, not evidence, and not a report about any image. The mind that produces it sees THE
USER'S WORDS AND CORPUS METADATA — ids, titles, counts — and no pixels at all. So:

  · no field may carry a region, a mask, a box, a coordinate, a confidence or a measurement;
  · every attention is attributed to the prompt ("the user said 'fold'"), never to a picture;
  · every proposed action is `status: proposed` and nothing dispatches it;
  · `corpus_context` holds ids/titles/counts, and refuses anything that would be an image fact.

THE TWO THAT ARE EASIEST TO GET WRONG, spelled out because getting them wrong is the whole
failure mode this frame exists to prevent:

  `epistemic_demands` — what KIND of knowing a clause asks for. `sensuality` is `interpretive`
  and must not become `measurable` merely because fold geometry contributes to a reading of it.
  `hybrid style` is `imagined`. Historical influence is `sourced`. A fold mask may be measurable
  ONCE AN ORGAN ACTUALLY RUNS, and at this stage it is only a REQUESTED measurement — which is
  why the kind is `measurable` (a capacity) rather than `measured` (a claim).

  `semantic_remainder` — meaning left over after every available measurement has been named.
  It is first-class, not a footnote: a tool decomposition that pretends to exhaust a concept is
  how "we measured the folds" becomes "we measured the sensuality".

STRICT. Every model forbids unknown fields. A framer that invents a key is refused rather than
tidied, because a key nobody declared is exactly how geometry would arrive.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "inquiry-frame.v1"


class InquiryMode(str, Enum):
    """What the person is doing with the corpus. Deliberately four, and not the run surface's
    two: `explore`/`argue` are the Director's modes, and framing also has to describe a request
    to MAKE something and a request to CHECK something."""
    EXPLORE = "explore"
    ARGUE = "argue"
    CREATE = "create"
    INSPECT = "inspect"


class DemandKind(str, Enum):
    """What KIND of knowing a clause asks for.

    Four of these are the epistemic statuses a produced item may carry (`epistemics.py`), read
    one step earlier — as a REQUEST rather than a claim. `measurable` is deliberately not spelled
    `measured`: nothing has run, and a frame that said `measured` would be asserting a result it
    has no way to possess.

    `unresolved` is the fifth and has no counterpart downstream, because it names the case where
    no producer exists at all. It is not a weak measurement; it is the absence of an instrument.
    """
    MEASURABLE = "measurable"
    INTERPRETIVE = "interpretive"
    SOURCED = "sourced"
    IMAGINED = "imagined"
    UNRESOLVED = "unresolved"


class RefusalKind(str, Enum):
    """Why something a framer produced did not become part of the frame.

    Refusals are KEPT. An unknown action silently dropped while parsing would hide how often a
    model invents capabilities, and the refusal rate is the only observable that says whether to
    trust the framer at all — the same argument `groq_planner` makes for passing hallucinated
    actuator names through to be refused by name.
    """
    UNKNOWN_ACTION = "unknown_action"          # not in the Perceptual Action Grammar
    INVALID_ACTION = "invalid_action"          # a known type that failed validation
    DISALLOWED_PARAMS = "disallowed_params"    # payload keys the action does not declare
    HUMAN_ACTION_REQUIRED = "human_action_required"   # only a person may author this act
    UNKNOWN_MODE = "unknown_mode"
    UNKNOWN_DEMAND_KIND = "unknown_demand_kind"


class _Strict(BaseModel):
    """Unknown fields are refused, not ignored. A key nobody declared is how geometry arrives."""
    model_config = ConfigDict(extra="forbid", frozen=False)


class Attention(_Strict):
    """A place in the prompt that the framer keyed on, and what it was read as.

    `said` is the phrasing rule made into a field. It always reads "the user said …", so a
    consumer rendering this object cannot accidentally write "Semant found …" — the sentence is
    already written, and it is the honest one.
    """
    term: str = Field(..., description="the cue as matched, lowercased")
    said: str = Field(..., description="the attribution sentence — always 'the user said …'")
    span: Optional[Tuple[int, int]] = Field(
        default=None, description="character offsets into the prompt, or None if not located")
    category: str = Field(..., description="lexicon cue key, inquiry-cue key, or model category")
    action_roles: List[str] = Field(
        default_factory=list,
        description="grammar roles this attention would reach, e.g. 'field:fold'")
    attributed_to: str = Field(default="prompt", frozen=True)

    @field_validator("attributed_to")
    @classmethod
    def _only_the_prompt(cls, value: str) -> str:
        # There is no other legal value, and the field exists so that the absence of an
        # alternative is visible in the data rather than implied by a docstring.
        if value != "prompt":
            raise ValueError("an attention is attributed to the prompt and to nothing else — "
                             "this mind sees words, not pixels")
        return value

    @model_validator(mode="after")
    def _said_is_an_attribution(self) -> "Attention":
        if not self.said.lower().startswith("the user said"):
            raise ValueError("`said` must begin 'the user said' — a cue hit is an attribution, "
                             "never a detection")
        return self


class EpistemicDemand(_Strict):
    """One clause, the kind of knowing it asks for, and why it was read that way."""
    clause: str = Field(..., description="the clause from the prompt, verbatim")
    term: Optional[str] = Field(default=None, description="the word inside the clause that fired")
    kind: DemandKind
    why: str = Field(..., description="why this clause asks for this kind of knowing")


class UnresolvedTerm(_Strict):
    """A term no lexicon or grammar binding can safely operationalise."""
    term: str
    why: str


class SemanticRemainder(_Strict):
    """Meaning not exhausted by the measurements that bear on it.

    `contributing_measurements` is the honest half of the pair: naming what DOES bear on a term
    is what makes the refusal to call it measured a considered position rather than a shrug.
    """
    term: str
    why: str
    contributing_measurements: List[str] = Field(default_factory=list)


class Refusal(_Strict):
    """Something a framer produced that did not become part of the frame, and why."""
    kind: RefusalKind
    what: str = Field(..., description="the offending name or value, verbatim")
    why: str
    detail: List[str] = Field(default_factory=list)


class CorpusContext(_Strict):
    """Ids, titles and counts. NOTHING that would be a fact about a picture.

    The validator is not decoration: this is the one place image data could plausibly be argued
    into the frame ("just the dimensions", "just the region count on each"), and once one such
    field is accepted the mind is reporting on images it never opened.
    """
    post_ids: List[str] = Field(default_factory=list)
    titles: List[str] = Field(default_factory=list)
    count: int = 0
    tags: List[str] = Field(default_factory=list)
    note: Optional[str] = None

    @model_validator(mode="after")
    def _count_is_not_a_second_source(self) -> "CorpusContext":
        if self.post_ids and self.count and self.count != len(self.post_ids):
            raise ValueError(f"corpus count {self.count} disagrees with {len(self.post_ids)} ids; "
                             "one of them is wrong and neither may be quietly preferred")
        return self


class FrameProvenance(_Strict):
    """Who framed this, with what, from which contracts, and when."""
    producer: str = Field(..., description="the framer that produced this frame")
    framer_kind: str = Field(..., description="deterministic | model | model_fallback_deterministic")
    model: Optional[str] = None
    role: Optional[str] = None
    prompt_sha256: str
    schema_version: str = SCHEMA_VERSION
    grammar_version: str
    lexicon_version: str
    framed_at: Optional[str] = None
    model_calls: int = 0

    model_config = ConfigDict(extra="forbid", protected_namespaces=())


#: Payload keys that would be a claim about a picture. Checked on every proposed action's payload
#: as a belt-and-braces guard: `grammar.clamp_payload` already drops anything the action does not
#: declare, and no declared key is in this set — so this firing at all means the grammar contract
#: itself grew a field it should not have.
FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "mask", "mask_rle", "masks", "bbox", "box", "boxes", "polygon", "points", "coordinates",
    "coords", "region_id", "region_ids", "ground_id_measured", "confidence", "score", "scores",
    "measurement", "measurements", "epistemic_status", "pixels", "geometry", "area_px",
})


class InquiryFrame(_Strict):
    """A prompt, read. Nothing here was seen; everything here was said, asked for, or refused."""

    schema_version: str = SCHEMA_VERSION
    inquiry_id: str
    prompt: str = Field(..., description="the user's words, byte for byte")
    mode: InquiryMode = InquiryMode.EXPLORE

    attentions: List[Attention] = Field(default_factory=list)
    epistemic_demands: List[EpistemicDemand] = Field(default_factory=list)
    proposed_actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Perceptual Action Grammar objects, already validated, status=proposed")
    unresolved_terms: List[UnresolvedTerm] = Field(default_factory=list)
    semantic_remainder: List[SemanticRemainder] = Field(default_factory=list)

    requested_output: Optional[str] = None
    corpus_context: CorpusContext = Field(default_factory=CorpusContext)
    provenance: FrameProvenance
    refusals: List[Refusal] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def _pinned(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}, got {value!r}")
        return value

    @model_validator(mode="after")
    def _claims_nothing_about_any_image(self) -> "InquiryFrame":
        """The honesty guard, enforced rather than documented.

        Three separate ways a frame could start asserting evidence, all refused here:
        a proposed act that is not `proposed`, a payload carrying geometry or a confidence, and
        an interpretive/imagined demand that also claims to be measurable.
        """
        for action in self.proposed_actions:
            status = action.get("status")
            if status != "proposed":
                raise ValueError(
                    f"proposed_actions carries an action with status {status!r}. A frame proposes; "
                    f"it never records that anything ran.")
            payload = action.get("payload") or {}
            forbidden = sorted(set(payload) & FORBIDDEN_PAYLOAD_KEYS)
            if forbidden:
                raise ValueError(
                    f"action {action.get('type')!r} carries {forbidden} in its payload. This mind "
                    f"has not seen the image and may not author geometry, a region or a "
                    f"confidence.")

        # A SET of kinds per term, not the last one seen. Keyed by a dict, a frame recording
        # `sensuality` as both measurable and interpretive would pass whenever the interpretive
        # demand happened to come second — the guard would be decided by list order.
        demanded: Dict[str, set] = {}
        for demand in self.epistemic_demands:
            demanded.setdefault((demand.term or demand.clause).lower(), set()).add(demand.kind)
        for remainder in self.semantic_remainder:
            if DemandKind.MEASURABLE in demanded.get(remainder.term.lower(), set()):
                raise ValueError(
                    f"'{remainder.term}' is recorded as a semantic remainder AND as a measurable "
                    f"demand. A remainder is what measurement does not reach; the two cannot both "
                    f"be true of one term.")
        return self

    # ── reading a frame ──

    def demands_of(self, kind: DemandKind) -> List[EpistemicDemand]:
        return [d for d in self.epistemic_demands if d.kind is kind]

    def action_types(self) -> List[str]:
        return [str(a.get("type")) for a in self.proposed_actions]

    def summary(self) -> str:
        """One honest line. Says what was asked and what was refused; claims nothing found."""
        bits = [f"{len(self.attentions)} attention{'' if len(self.attentions) == 1 else 's'}"]
        by_kind: Dict[str, int] = {}
        for demand in self.epistemic_demands:
            by_kind[demand.kind.value] = by_kind.get(demand.kind.value, 0) + 1
        if by_kind:
            bits.append("demands " + " · ".join(f"{n} {k}" for k, n in sorted(by_kind.items())))
        bits.append(f"{len(self.proposed_actions)} proposed act"
                    f"{'' if len(self.proposed_actions) == 1 else 's'}, none run")
        if self.unresolved_terms:
            bits.append(f"{len(self.unresolved_terms)} term"
                        f"{'' if len(self.unresolved_terms) == 1 else 's'} nothing can serve")
        if self.semantic_remainder:
            bits.append(f"{len(self.semantic_remainder)} meaning"
                        f"{'' if len(self.semantic_remainder) == 1 else 's'} measurement will not "
                        f"exhaust")
        if self.refusals:
            bits.append(f"{len(self.refusals)} refused")
        return " · ".join(bits)


#: Fields that change on every framing of the same prompt. A byte-stability check must exclude
#: exactly these and nothing else — excluding more would let a real drift hide inside the
#: exclusion list.
VOLATILE_FIELDS = ("inquiry_id", "framed_at")


def canonical(frame: InquiryFrame) -> Dict[str, Any]:
    """The frame with its minted id and timestamp removed, for comparing two framings.

    Two deterministic framings of one prompt must be identical under this helper. The helper
    exists rather than the test hand-rolling a dict copy so that a field added later is either
    stable or deliberately named volatile — and never quietly excluded by whoever wrote the test.
    """
    data = frame.model_dump(mode="json")
    data.pop("inquiry_id", None)
    provenance = dict(data.get("provenance") or {})
    provenance.pop("framed_at", None)
    data["provenance"] = provenance
    return data


def prompt_hash(prompt: str) -> str:
    """A stable handle for the prompt, so provenance can point at it without repeating it."""
    return hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()


_ID_SAFE = re.compile(r"[^a-z0-9]+")


def mint_inquiry_id(prompt: str, *, now: Optional[datetime] = None) -> str:
    """`inq_<12 hex>` — derived from the prompt and the moment, minted once.

    Not a run id and not persisted. Nothing in this lane writes to Mongo, and an id that looked
    like a stored record's would invite somebody to go looking for one.
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    digest = hashlib.sha256(f"{prompt}\x00{stamp}".encode("utf-8")).hexdigest()
    return f"inq_{digest[:12]}"


def utc_now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()
