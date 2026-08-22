"""
INTELLIGENCE-002C — the provenance-bearing interpretive composer.

    an InquiryMap, what each image was said to suggest, what Semant chose to compare,
    the relations that were proposed and the critiques of them, the observables, the
    capability gaps and whatever evidence exists
      -> six sections that keep apart WHO SAID IT and HOW IT IS KNOWN

Nothing here routes, persists, renders or measures. It takes plain data in and returns a
`Composition`: a statement of what was proposed, what was seen, what was chosen, what survived,
what is still only a reading, and what would have to exist before any of it could be more.

WHY A COMPOSER AT ALL, AND WHY THIS ONE REFUSES TO BE A SUMMARISER.

The useful thing a vision-language model produces is a sentence about a picture. The dangerous
thing about that sentence is that it reads exactly like a measurement. Put six of them in a list
under a heading and the list becomes a finding; put a seventh underneath saying "all six agree"
and the finding becomes a fact. No step in that sequence is a lie, and the end of it is a
fabrication. This module exists to make that sequence unsayable rather than discouraged.

So it does three things and declines to do a fourth:

  1. It PRESERVES the upstream sentence byte-identically. Every `Line.text` is a string that
     arrived, not a paraphrase of one. A composer that rewrote its inputs would be a seventh
     producer with no provenance of its own, and the rewrite is exactly where a hedge goes
     missing.
  2. It CARRIES the provenance on every line — who produced it, which upstream ids it rests on,
     which evidence it cited, and, separately, which capabilities actually backed it. The last
     field is the load-bearing one: `measured_by` is empty for almost everything, and an empty
     `measured_by` beside a confident sentence is the whole point of the exercise.
  3. It SETTLES the epistemic status downward and never upward, recording each demotion with its
     reason, so a reader can see not just what the line is but what it was claimed to be.
  4. It does not compose prose. There is no narrative voice here, because a narrative voice is
     where the six sentences quietly become a finding.

THE VOCABULARY IS NOT NEW. `EpistemicStatus` comes from `backend/services/epistemics.py`, which
has carried the five kinds and the sourced wall since CIRCUIT-003 M6. Minting a second status
enum for this lane would be the precise failure that module was written to prevent: two
vocabularies that look alike until they disagree.

WHAT IS NOT REUSED, AND WHY. `epistemics.guard()` and `epistemics.retag()` key their rules on the
PRODUCER's classification — a table of names in `role_registry` and `_DEFAULTS`. This lane's
producers are not in that table, and adding them from here would be a producer classifying
itself, which `assert_substrate_tables_agree` exists to refuse. So the composer enforces the same
asymmetry on a different hinge: not "who produced it" but "did a capability that actually
measures anything back it". That hinge is the one INTELLIGENCE requires (a VLM observation is
interpretive until a measuring capability supports it), and it needs no name to be registered
anywhere. The sourced wall itself is imported rather than restated, so the two cannot drift.

THREE RULES WORTH STATING SEPARATELY, BECAUSE EACH IS A WAY THIS MODULE COULD HAVE BEEN WRONG.

  A USER HYPOTHESIS IS NOT AN IMAGE OBSERVATION. It arrives in section 1 as `sourced` — from
  outside the picture, cited to the inquirer's own prompt — and the imported wall then makes it
  incapable of becoming `visible` later. A hypothesis that arrives already claiming an image
  status is not accepted and quietly used; it is demoted, and the demotion is on the line. An
  alignment saying an image supports a hypothesis is a claim about the image and lives in section
  2; it does not travel back and improve the hypothesis.

  AGREEMENT IS NOT MEASUREMENT. Evidence whose kind is a consensus — a vote, a second opinion, a
  panel — grants nothing. It is named in `NON_PROMOTING_EVIDENCE_KINDS` rather than merely
  omitted, and citing it under a `measured` claim is a refusal, because silence would make the
  rule indistinguishable from an oversight.

  A CAPABILITY THAT DOES NOT EXIST CANNOT HAVE MEASURED ANYTHING. Evidence naming a capability
  that the gap list declares missing, or that the live matrix says is down, is discounted and
  refused. This is the case that looks most like a bug and is most like a lie: the evidence is
  well-formed, it names a real-sounding capability, and nothing ever ran.

SECTION 4 SHOWS THE WHOLE FIELD, NOT THE WINNERS. "Which relations survived critique" is a
question whose honest answer includes the ones that did not, and the ones nobody critiqued at
all — which is a third thing, not a soft version of the second. A section listing only survivors
reads as "these are the relations", and the discarded ones become invisible. So every relation
that entered appears, each carrying its `standing`, and `Composition.survivors()` is what a caller
uses when it genuinely wants only the sustained ones.

EVERY SECTION IS ALWAYS PRESENT, including the empty ones. An absent section and an empty section
say different things — "nothing to report" versus "this was never looked at" — and a composer that
dropped the empties would make them the same string.

FIXTURE-COMPATIBLE INPUTS. Nothing here imports a contract model. Each input is read through
`_field`, which accepts a mapping or an object with attributes, so the same code consumes frozen
JSON samples today and INTELLIGENCE-001A's typed models when they land, with no edit. That is a
deliberate seam and not a shortcut: the composer's job is to be right about provenance, and
binding it to a schema version would make every schema bump a change to the honesty rules.

PURE. No database, no network, no model client, no clock, no randomness. `now` is injected by the
caller; a composition built without one carries an empty `composed_at` rather than inventing a
time. Ids are hashes of content, so two replays of one input are the same composition rather than
two that a reader has to compare by hand.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.epistemics import (IMAGE_STATUSES, IMAGE_STRENGTH, WALLED_STATUSES,
                                         EpistemicStatus)

#: The producer name this module stamps on everything it builds. One string, so a reader grepping
#: for what made a line finds this file and not a guess.
COMPOSER_PRODUCER = "inquiry_intelligence/composer-v1"

SCHEMA_VERSION = "inquiry-intelligence-composition.v1"


# ── the vocabulary ───────────────────────────────────────────────────────────

class Origin(str, Enum):
    """WHO a line came from — a different question from `EpistemicStatus`, which is HOW it is known.

    The two are routinely confused and the confusion is the bug. "The inquirer proposed it" and
    "it is a reading rather than a measurement" are both true of the same sentence and neither
    implies the other; keeping them in one field would mean picking which half to lose.
    """
    USER = "user"          # the inquirer said it, in their own prompt
    IMAGE = "image"        # obtained by looking at a picture
    SYSTEM = "system"      # Semant's own act — a choice, a plan, an accounting of its own limits
    EXTERNAL = "external"  # from outside the picture, carrying a citation


class SectionId(str, Enum):
    """The six sections, in the order the directive names them."""
    PROPOSED = "proposed"          # 1. what the user proposed
    SUGGESTED = "suggested"        # 2. what each image suggested
    COMPARED = "compared"          # 3. what Semant chose to compare
    SURVIVED = "survived"          # 4. which relations survived critique
    INTERPRETIVE = "interpretive"  # 5. what remained interpretive
    MEASURABLE = "measurable"      # 6. what could be measured, and what is missing


#: Fixed order and fixed titles. A caller that wants a different order sorts the tuple itself;
#: the composition's own order is not a rendering choice.
SECTION_ORDER: Tuple[SectionId, ...] = (
    SectionId.PROPOSED, SectionId.SUGGESTED, SectionId.COMPARED,
    SectionId.SURVIVED, SectionId.INTERPRETIVE, SectionId.MEASURABLE,
)

SECTION_TITLES: Dict[SectionId, str] = {
    SectionId.PROPOSED: "what the inquirer proposed",
    SectionId.SUGGESTED: "what each image was said to suggest",
    SectionId.COMPARED: "what Semant chose to compare",
    SectionId.SURVIVED: "which relations survived critique",
    SectionId.INTERPRETIVE: "what remained interpretive",
    SectionId.MEASURABLE: "what could be measured, and what would have to exist first",
}

#: What a section says when it holds nothing. Present so that "nothing was proposed" and "the
#: proposals were never read" are different strings in the output rather than one absent key.
SECTION_EMPTINESS: Dict[SectionId, str] = {
    SectionId.PROPOSED: "the inquirer proposed nothing beyond the prompt itself",
    SectionId.SUGGESTED: "no image was read, or every reading was refused",
    SectionId.COMPARED: "Semant chose nothing to compare",
    SectionId.SURVIVED: "no relation was proposed, so none survived and none failed",
    SectionId.INTERPRETIVE: "nothing was left interpretive — every line above is backed",
    SectionId.MEASURABLE: "nothing named a capability that would settle anything",
}


class LineKind(str, Enum):
    PROPOSAL = "proposal"        # a hypothesis, or the prompt itself
    OBSERVATION = "observation"  # what an image was said to suggest
    ALIGNMENT = "alignment"      # an image read against a hypothesis
    CHOICE = "choice"            # a contrast Semant elected to draw
    RELATION = "relation"        # a candidate relation and its standing after critique
    RESIDUE = "residue"          # a restatement, in section 5, of a line nothing backed
    GAP = "gap"                  # a capability that would settle a residue, and whether it exists


#: The strongest status each kind of line may EVER carry, before evidence is even consulted.
#:
#: A ceiling, not a default. `OBSERVATION` and `RELATION` are the only kinds that can reach an
#: image status at all, and reaching it still requires a measuring capability. Everything else is
#: capped here because of what it IS, not because of how well it went:
#:
#:   PROPOSAL   is not from the picture. `sourced` is the walled status and the wall is the rule.
#:   RELATION   caps one rung below `OBSERVATION`, and the rung is the point. `visible` means an
#:              extent someone can point at; a relation is not an extent. "A is wider than B" can
#:              be computed and so can reach `measured`, but there is nothing in the picture to
#:              put a finger on, and a relation arriving as `visible` has confused the claim with
#:              the two regions it is about.
#:   ALIGNMENT  is a reading of an image against a sentence the inquirer wrote. Even where the
#:              image genuinely does contain what the hypothesis claims, the ALIGNMENT is the
#:              judgement that it does, and that judgement is interpretive. The measurement, if
#:              one exists, is on the observation the alignment cites.
#:   CHOICE     is an act, not a finding. Semant putting two things side by side is a fact about
#:              Semant; the only thing a reader could mistake it for is a result, and
#:              `interpretive` is the honest ceiling for "these seemed worth comparing".
#:   RESIDUE    restates something already established to be unbacked.
#:   GAP        is an account of what is NOT known. `uncertain` is not modesty here; it is the
#:              literal content of the line.
CEILING_BY_KIND: Dict[LineKind, EpistemicStatus] = {
    LineKind.PROPOSAL: EpistemicStatus.SOURCED,
    LineKind.OBSERVATION: EpistemicStatus.VISIBLE,
    LineKind.ALIGNMENT: EpistemicStatus.INTERPRETIVE,
    LineKind.CHOICE: EpistemicStatus.INTERPRETIVE,
    LineKind.RELATION: EpistemicStatus.MEASURED,
    LineKind.RESIDUE: EpistemicStatus.INTERPRETIVE,
    LineKind.GAP: EpistemicStatus.UNCERTAIN,
}

ORIGIN_BY_KIND: Dict[LineKind, Origin] = {
    LineKind.PROPOSAL: Origin.USER,
    LineKind.OBSERVATION: Origin.IMAGE,
    LineKind.ALIGNMENT: Origin.IMAGE,
    LineKind.CHOICE: Origin.SYSTEM,
    LineKind.RELATION: Origin.IMAGE,
    LineKind.RESIDUE: Origin.SYSTEM,
    LineKind.GAP: Origin.SYSTEM,
}

#: Evidence kinds that actually raise a claim off `interpretive`, and how far.
#:
#: TWO ENTRIES, and the shortness is the content. `extent` is a region someone can point at in the
#: picture; `measurement` is a number computed from the signal. Nothing else in this system
#: produces either, so nothing else appears here — and an evidence kind absent from this table
#: grants nothing rather than defaulting to something. Default-deny, because the failure of a
#: default-allow table is a new evidence kind silently promoting everything that cites it.
MEASURING_EVIDENCE_KINDS: Dict[str, EpistemicStatus] = {
    "extent": EpistemicStatus.VISIBLE,
    "measurement": EpistemicStatus.MEASURED,
}

#: Evidence kinds that grant nothing, NAMED rather than merely absent.
#:
#: They would grant nothing anyway — the table above is default-deny. Naming them buys the
#: refusal: citing one of these under a claim of measurement is not an unrecognised kind, it is a
#: specific known error, and it is reported as one. `agreement`, `consensus` and `vote` are here
#: because model-to-model concurrence is the most persuasive thing in the pipeline that is not
#: evidence at all; `reading` and `description` because a second sentence about a sentence is
#: still a sentence; `citation` because a source is outside the picture by definition.
NON_PROMOTING_EVIDENCE_KINDS: Tuple[str, ...] = (
    "agreement", "consensus", "vote", "corroboration", "second_opinion",
    "reading", "description", "citation",
)

#: The subset of the above that is specifically an appeal to concurrence. Refused louder, because
#: "three models said so" is the sentence this whole module exists to stop.
AGREEMENT_EVIDENCE_KINDS: Tuple[str, ...] = (
    "agreement", "consensus", "vote", "corroboration", "second_opinion",
)


class DemotionReason(str, Enum):
    NOT_FROM_THE_IMAGE = "not_from_the_image"
    NO_MEASURING_CAPABILITY = "no_measuring_capability"
    CAPABILITY_IS_A_GAP = "capability_is_a_gap"
    CAPABILITY_IS_DOWN = "capability_is_down"
    AGREEMENT_IS_NOT_MEASUREMENT = "agreement_is_not_measurement"
    A_CHOICE_IS_NOT_A_FINDING = "a_choice_is_not_a_finding"
    A_READING_IS_NOT_A_MEASUREMENT = "a_reading_is_not_a_measurement"
    CRITIQUE_WITHHELD_SUPPORT = "critique_withheld_support"
    NOTHING_CRITIQUED_IT = "nothing_critiqued_it"
    NO_STATUS_WAS_DECLARED = "no_status_was_declared"
    CEILING_FOR_THIS_KIND = "ceiling_for_this_kind"
    IT_WAS_NOT_ACCEPTED = "it_was_not_accepted"


class RefusalKind(str, Enum):
    UNANCHORED_OBSERVATION = "unanchored_observation"
    EMPTY_STATEMENT = "empty_statement"
    UNDECLARED_STATUS = "undeclared_status"
    UNKNOWN_STATUS = "unknown_status"
    SOURCED_CLAIM_ABOUT_THE_IMAGE = "sourced_claim_about_the_image"
    DANGLING_HYPOTHESIS = "dangling_hypothesis"
    DANGLING_OBSERVATION = "dangling_observation"
    DANGLING_RELATION = "dangling_relation"
    DANGLING_PLAN = "dangling_plan"
    DANGLING_EVIDENCE = "dangling_evidence"
    CONTRADICTED_ACCEPTANCE = "contradicted_acceptance"
    EVIDENCE_FROM_ABSENT_CAPABILITY = "evidence_from_absent_capability"
    AGREEMENT_OFFERED_AS_MEASUREMENT = "agreement_offered_as_measurement"
    DUPLICATE_ID = "duplicate_id"
    UNIDENTIFIED_ITEM = "unidentified_item"


class Standing(str, Enum):
    """What became of a candidate relation. Four outcomes, and the third is not a soft second."""
    SUSTAINED = "sustained"      # accepted, and a critique upheld it
    WITHHELD = "withheld"        # accepted, but its critique would not vouch for it
    REFUTED = "refuted"          # accepted, and its critique took it apart
    UNCRITIQUED = "uncritiqued"  # accepted, and nothing examined it — not the same as upheld
    REJECTED = "rejected"        # never accepted in the first place


#: Critique verdicts that let an accepted relation stand. Everything else, including a verdict
#: nobody recognises, withholds — an unreadable critique is not an endorsement.
SUSTAINING_VERDICTS: Tuple[str, ...] = ("sustained", "upheld", "supported", "accept", "accepted")
REFUTING_VERDICTS: Tuple[str, ...] = ("refuted", "rejected", "overturned")


# ── ids ──────────────────────────────────────────────────────────────────────
#
# Content-derived, following `semantic_compilation/ids.py`, for the same reason: a replay must be
# a comparison rather than an act of faith. A line id keyed on list position would renumber the
# whole composition the moment a model emitted two observations in the other order, and the diff
# would show a change where nothing had changed.

PREFIXES: Dict[str, str] = {
    "composition": "icm_",
    "section": "isc_",
    "line": "iln_",
    "refusal": "irf_",
}

#: Twelve hex characters, the width the rest of the system uses.
WIDTH = 12

_WHITESPACE = re.compile(r"\s+")


def normalise(text: Any) -> str:
    """The form a hash is taken over: lowercased, whitespace collapsed, trimmed.

    Shallow on purpose. It absorbs a model rewrapping a sentence and absorbs nothing that is
    meaning — stripping punctuation here would merge two lines that differ by a `not`.
    """
    return _WHITESPACE.sub(" ", str(text or "")).strip().lower()


def _digest(parts: Sequence[Any]) -> str:
    # NUL-joined: a separator that cannot occur in any part, so ("ab","c") and ("a","bc") cannot
    # hash alike.
    payload = "\x00".join(normalise(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:WIDTH]


def _mint(kind: str, parts: Sequence[Any]) -> str:
    return "{}{}".format(PREFIXES[kind], _digest([kind, *parts]))


def composition_id(inquiry_id: str, prompt: str) -> str:
    return _mint("composition", [inquiry_id, prompt])


def section_id(inquiry_id: str, section: SectionId) -> str:
    return _mint("section", [inquiry_id, section.value])


def line_id(inquiry_id: str, section: SectionId, kind: LineKind, text: str,
            source_ids: Sequence[str] = ()) -> str:
    # The source ids are mixed in because two different upstream items may legitimately say the
    # same words about the same picture, and collapsing them would silently drop one producer's
    # contribution while leaving the other's provenance attached to both.
    return _mint("line", [inquiry_id, section.value, kind.value, text, *source_ids])


def refusal_id(inquiry_id: str, kind: RefusalKind, subject: str, detail: str) -> str:
    return _mint("refusal", [inquiry_id, kind.value, subject, detail])


# ── reading fixture-compatible inputs ────────────────────────────────────────

def _field(item: Any, name: str, default: Any = None) -> Any:
    """One accessor for a mapping or an object.

    This is the seam that makes the module fixture-compatible. A frozen JSON sample and a typed
    model from INTELLIGENCE-001A are both read through here, so the honesty rules below never
    mention a schema and never move when one is versioned.
    """
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _first_field(item: Any, names: Sequence[str], default: Any = None) -> Any:
    """The first of several field names that is actually present and non-empty."""
    for name in names:
        value = _field(item, name)
        if value not in (None, "", (), []):
            return value
    return default


def _text(value: Any) -> str:
    return str(value or "")


def _ids(value: Any) -> Tuple[str, ...]:
    if value in (None, "", ()):
        return ()
    if isinstance(value, (str, bytes)):
        return (str(value),)
    return tuple(str(v) for v in value)


def _status(value: Any) -> Tuple[Optional[EpistemicStatus], bool]:
    """`(status, was_readable)`.

    `(None, True)` means nothing was declared; `(None, False)` means something was declared and it
    is not a status this system has. The two are different failures and get different refusals: a
    producer that forgot to say is a wiring bug, and a producer that said `probable` has invented
    a sixth kind of knowing.
    """
    if value in (None, ""):
        return None, True
    if isinstance(value, EpistemicStatus):
        return value, True
    try:
        return EpistemicStatus(str(value)), True
    except ValueError:
        return None, False


#: Strength ranking for the image statuses, strongest first, taken from `epistemics` rather than
#: restated. `sourced` is deliberately absent there and absent here: it is not on this scale, which
#: is what the wall means.
_STRENGTH: Dict[EpistemicStatus, int] = {s: i for i, s in enumerate(IMAGE_STRENGTH)}


def _weaker_of(a: EpistemicStatus, b: EpistemicStatus) -> EpistemicStatus:
    """The weaker of two image statuses. Off-scale (`sourced`) never enters this function."""
    return a if _STRENGTH[a] >= _STRENGTH[b] else b


def _is_stronger(a: EpistemicStatus, b: EpistemicStatus) -> bool:
    """Is `a` a stronger image status than `b`? False whenever either is off the scale."""
    if a not in _STRENGTH or b not in _STRENGTH:
        return False
    return _STRENGTH[a] < _STRENGTH[b]


# ── the composed objects ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Demotion:
    """One downward step, with the reason it was taken.

    Recorded rather than applied silently, because the interesting fact about a demoted line is
    usually not its settled status but the distance between that and what its producer claimed.
    """
    from_status: EpistemicStatus
    to_status: EpistemicStatus
    reason: DemotionReason
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"from_status": self.from_status.value, "to_status": self.to_status.value,
                "reason": self.reason.value, "detail": self.detail}


@dataclass(frozen=True)
class Attribution:
    """Everything a reader needs to go back to what a line rests on.

    `measured_by` is separate from `evidence_ids` and that separation is the module's whole
    argument: a line may cite five pieces of evidence and be backed by none of them. Empty
    `measured_by` beside a confident sentence is what the reader is meant to notice.
    """
    producer: str = ""
    source_ids: Tuple[str, ...] = ()
    evidence_ids: Tuple[str, ...] = ()
    measured_by: Tuple[str, ...] = ()
    discounted_evidence: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {"producer": self.producer, "source_ids": list(self.source_ids),
                "evidence_ids": list(self.evidence_ids), "measured_by": list(self.measured_by),
                "discounted_evidence": list(self.discounted_evidence)}


@dataclass(frozen=True)
class Line:
    """One statement, with who said it, how it is known, and what it was claimed to be."""
    line_id: str
    kind: LineKind
    text: str
    status: EpistemicStatus
    origin: Origin
    attribution: Attribution
    declared_status: Optional[EpistemicStatus] = None
    demotions: Tuple[Demotion, ...] = ()
    subjects: Tuple[str, ...] = ()
    because: str = ""
    restates: str = ""
    standing: str = ""
    stance: str = ""
    blocks: Tuple[str, ...] = ()

    @property
    def is_backed(self) -> bool:
        """Did a capability that actually measures something support this line?"""
        return bool(self.attribution.measured_by) and self.status in (
            EpistemicStatus.VISIBLE, EpistemicStatus.MEASURED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_id": self.line_id, "kind": self.kind.value, "text": self.text,
            "status": self.status.value, "origin": self.origin.value,
            "declared_status": self.declared_status.value if self.declared_status else None,
            "attribution": self.attribution.to_dict(),
            "demotions": [d.to_dict() for d in self.demotions],
            "subjects": list(self.subjects), "because": self.because,
            "restates": self.restates, "standing": self.standing, "stance": self.stance,
            "blocks": list(self.blocks),
        }


@dataclass(frozen=True)
class Section:
    section: SectionId
    section_uid: str
    title: str
    lines: Tuple[Line, ...] = ()
    emptiness: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"section": self.section.value, "section_uid": self.section_uid,
                "title": self.title, "lines": [l.to_dict() for l in self.lines],
                "emptiness": self.emptiness if not self.lines else ""}


@dataclass(frozen=True)
class Refusal:
    """Something the composer would not do, kept rather than dropped.

    Filtering silently is how a laundered claim becomes a bug nobody investigates. Every refusal
    names the id it is about, so the input can be repaired without re-deriving which item it was.
    """
    refusal_uid: str
    kind: RefusalKind
    subject_id: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"refusal_uid": self.refusal_uid, "kind": self.kind.value,
                "subject_id": self.subject_id, "detail": self.detail}


@dataclass(frozen=True)
class ComposerProvenance:
    producer: str = COMPOSER_PRODUCER
    schema_version: str = SCHEMA_VERSION
    composed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"producer": self.producer, "schema_version": self.schema_version,
                "composed_at": self.composed_at}


@dataclass(frozen=True)
class Composition:
    composition_uid: str
    inquiry_id: str
    prompt: str
    sections: Tuple[Section, ...]
    refusals: Tuple[Refusal, ...] = ()
    provenance: ComposerProvenance = field(default_factory=ComposerProvenance)

    def section(self, which: SectionId) -> Section:
        for s in self.sections:
            if s.section is which:
                return s
        raise KeyError(which)

    def lines(self) -> Tuple[Line, ...]:
        return tuple(l for s in self.sections for l in s.lines)

    def line(self, uid: str) -> Optional[Line]:
        for l in self.lines():
            if l.line_id == uid:
                return l
        return None

    def survivors(self) -> Tuple[Line, ...]:
        """The relations a critique actually upheld — for a caller that wants only those.

        It is a method rather than a section because the section shows the field. A caller asking
        for the survivors is making a choice, and the choice is visible at the call site.
        """
        return tuple(l for l in self.section(SectionId.SURVIVED).lines
                     if l.standing == Standing.SUSTAINED.value)

    def backed(self) -> Tuple[Line, ...]:
        return tuple(l for l in self.lines() if l.is_backed)

    def unbacked(self) -> Tuple[Line, ...]:
        return tuple(l for l in self.lines() if not l.is_backed)

    def to_dict(self) -> Dict[str, Any]:
        return {"composition_uid": self.composition_uid, "inquiry_id": self.inquiry_id,
                "prompt": self.prompt, "sections": [s.to_dict() for s in self.sections],
                "refusals": [r.to_dict() for r in self.refusals],
                "provenance": self.provenance.to_dict()}


def canonical(composition: Composition) -> Dict[str, Any]:
    """The composition with the declared-volatile fields removed.

    One field is volatile — `composed_at`, which the caller supplies. Everything else is derived
    from the input, so two runs over one input are byte-identical here even when the clocks differ.
    """
    data = composition.to_dict()
    data["provenance"] = {k: v for k, v in data["provenance"].items() if k != "composed_at"}
    return data


@dataclass(frozen=True)
class CompositionRequest:
    """Everything the composer consumes. Every field optional but `inquiry_id` and `prompt`.

    A missing input is a real state — a composition run before the critics have said anything is
    a legitimate thing to want — and it produces an empty section with its emptiness line rather
    than an exception.
    """
    inquiry_id: str
    prompt: str
    inquiry_map: Any = None
    observations: Sequence[Any] = ()
    alignments: Sequence[Any] = ()
    contrast_plans: Sequence[Any] = ()
    accepted_relations: Sequence[Any] = ()
    rejected_relations: Sequence[Any] = ()
    critiques: Sequence[Any] = ()
    observables: Sequence[Any] = ()
    capability_gaps: Sequence[Any] = ()
    evidence: Sequence[Any] = ()
    capabilities: Mapping[str, bool] = field(default_factory=dict)
    now: Optional[str] = None


# ── reading the inputs, by field name rather than by type ────────────────────
#
# Each tuple is the field names one kind of input may carry its id or its sentence under. They are
# lists rather than single strings because the composer is fixture-compatible by design: a frozen
# sample written before 001A settles on `observation_id` versus `id` must not become unreadable
# when it does.

_ID_FIELDS: Dict[str, Tuple[str, ...]] = {
    "hypothesis": ("hypothesis_id", "id"),
    "image": ("image_id", "post_id", "id"),
    "observation": ("observation_id", "id"),
    "alignment": ("alignment_id", "id"),
    "plan": ("plan_id", "contrast_id", "id"),
    "relation": ("relation_id", "candidate_id", "id"),
    "critique": ("critique_id", "id"),
    "observable": ("observable_id", "id"),
    "gap": ("gap_id", "id"),
    "evidence": ("evidence_id", "id"),
}

_TEXT_FIELDS: Tuple[str, ...] = ("statement", "text", "claim", "reading", "sentence", "why")
_STATUS_FIELDS: Tuple[str, ...] = ("declared_status", "epistemic_status", "status")
_BECAUSE_FIELDS: Tuple[str, ...] = ("because", "rationale", "reason", "motivation")
_EVIDENCE_REF_FIELDS: Tuple[str, ...] = ("evidence_ids", "evidence", "supported_by")
_TARGET_FIELDS: Tuple[str, ...] = ("of", "for", "target", "subject_id", "about")


def _item_id(item: Any, kind: str) -> str:
    return _text(_first_field(item, _ID_FIELDS[kind], ""))


def _item_text(item: Any) -> str:
    return _text(_first_field(item, _TEXT_FIELDS, ""))


class _Composer:
    """One composition, built once. Instance state is the indexes and the refusal ledger.

    A class rather than a chain of functions because eleven inputs cross-reference each other and
    threading eight indexes through six builders as arguments is how one of them ends up reading a
    stale copy.
    """

    def __init__(self, request: CompositionRequest) -> None:
        self.request = request
        self.inquiry_id = _text(request.inquiry_id)
        self.prompt = _text(request.prompt)
        self._refusals: Dict[str, Refusal] = {}

        # the capability picture ------------------------------------------------
        self.gaps: Tuple[Any, ...] = tuple(request.capability_gaps or ())
        self.gap_capabilities: Tuple[str, ...] = tuple(
            dict.fromkeys(_text(_field(g, "capability", "")) for g in self.gaps
                          if _text(_field(g, "capability", ""))))
        # An EMPTY matrix means the caller did not report one, not that every capability is down.
        # The distinction matters: with no matrix the gap list alone governs, and a composer that
        # read an unreported matrix as all-false would discount every real measurement in the
        # system the first time a caller forgot to pass it.
        self.matrix: Dict[str, bool] = dict(request.capabilities or {})

        # evidence --------------------------------------------------------------
        self.evidence_by_id: Dict[str, Any] = {}
        for e in request.evidence or ():
            eid = _item_id(e, "evidence")
            if eid and eid not in self.evidence_by_id:
                self.evidence_by_id[eid] = e
        self.evidence_order: Tuple[str, ...] = tuple(self.evidence_by_id)
        self.evidence_by_target: Dict[str, List[str]] = {}
        for eid, e in self.evidence_by_id.items():
            for target in _ids(_first_field(e, _TARGET_FIELDS, ())):
                self.evidence_by_target.setdefault(target, []).append(eid)

        # the map ---------------------------------------------------------------
        imap = request.inquiry_map
        self.hypotheses: Dict[str, Any] = {}
        self.hypothesis_order: List[str] = []
        for h in (_field(imap, "hypotheses", ()) or ()):
            hid = _item_id(h, "hypothesis")
            if not hid:
                continue
            if hid in self.hypotheses:
                self._refuse(RefusalKind.DUPLICATE_ID, hid, "two hypotheses share one id")
                continue
            self.hypotheses[hid] = h
            self.hypothesis_order.append(hid)
        self.map_image_order: Tuple[str, ...] = tuple(
            dict.fromkeys(_item_id(i, "image") for i in (_field(imap, "images", ()) or ())
                          if _item_id(i, "image")))
        self.image_titles: Dict[str, str] = {
            _item_id(i, "image"): _text(_first_field(i, ("title", "name", "label"), ""))
            for i in (_field(imap, "images", ()) or ()) if _item_id(i, "image")}

        # observations ----------------------------------------------------------
        self.observation_ids: Tuple[str, ...] = tuple(
            dict.fromkeys(_item_id(o, "observation") for o in (request.observations or ())
                          if _item_id(o, "observation")))

        # relations and their critiques ------------------------------------------
        self.critique_by_relation: Dict[str, Any] = {}
        for c in (request.critiques or ()):
            rid = _text(_first_field(c, ("relation_id", "candidate_id", "of", "target"), ""))
            if not rid:
                self._refuse(RefusalKind.DANGLING_RELATION, _item_id(c, "critique"),
                             "a critique that names no relation")
                continue
            self.critique_by_relation.setdefault(rid, c)

        # the lines, filled in as the sections are built -------------------------
        self._sections: Dict[SectionId, List[Line]] = {s: [] for s in SECTION_ORDER}

    # ── the ledger ───────────────────────────────────────────────────────────

    def _refuse(self, kind: RefusalKind, subject: str, detail: str = "") -> None:
        """Record a refusal, once. Deduplicated by content so one malformed item cited from three
        places produces one entry rather than three identical ones."""
        uid = refusal_id(self.inquiry_id, kind, subject, detail)
        if uid not in self._refusals:
            self._refusals[uid] = Refusal(refusal_uid=uid, kind=kind, subject_id=subject,
                                          detail=detail)

    # ── evidence ─────────────────────────────────────────────────────────────

    def _evidence_for(self, item: Any, item_id: str) -> Tuple[str, ...]:
        """Evidence ids this item rests on: the ones it cites, plus the ones that name it.

        Both directions, because the two conventions coexist upstream — a producer either hangs
        evidence off its claim or files evidence pointing back at it — and a composer that read
        only one would silently find nothing for half the pipeline.
        """
        cited = _ids(_first_field(item, _EVIDENCE_REF_FIELDS, ()))
        found: List[str] = []
        for eid in cited:
            if eid not in self.evidence_by_id:
                self._refuse(RefusalKind.DANGLING_EVIDENCE, item_id,
                             "cites evidence '{}', which does not exist".format(eid))
                continue
            if eid not in found:
                found.append(eid)
        for eid in self.evidence_by_target.get(item_id, ()):
            if eid not in found:
                found.append(eid)
        return tuple(found)

    def _weigh(self, evidence_ids: Sequence[str], subject_id: str,
               declared: Optional[EpistemicStatus]) -> Tuple[EpistemicStatus, Tuple[str, ...],
                                                             Tuple[str, ...], DemotionReason]:
        """What the evidence actually supports: `(best, measured_by, discounted, why_not_more)`.

        `best` starts at `interpretive` and only a capability that measures something moves it.
        Nothing in this function counts, and that omission is the rule about agreement: there is
        no path by which two pieces of evidence support more than one of them does.
        """
        best = EpistemicStatus.INTERPRETIVE
        measured_by: List[str] = []
        discounted: List[str] = []
        reason = DemotionReason.NO_MEASURING_CAPABILITY

        for eid in evidence_ids:
            entry = self.evidence_by_id.get(eid)
            if entry is None:
                continue
            kind = normalise(_first_field(entry, ("kind", "evidence_kind", "type"), ""))
            capability = _text(_first_field(entry, ("capability", "capability_class", "producer"),
                                            ""))

            if kind in AGREEMENT_EVIDENCE_KINDS:
                discounted.append(eid)
                reason = DemotionReason.AGREEMENT_IS_NOT_MEASUREMENT
                if declared in (EpistemicStatus.VISIBLE, EpistemicStatus.MEASURED):
                    self._refuse(
                        RefusalKind.AGREEMENT_OFFERED_AS_MEASUREMENT, subject_id,
                        "claims '{}' on evidence of kind '{}'; concurrence is not a measurement"
                        .format(declared.value, kind))
                continue

            grant = MEASURING_EVIDENCE_KINDS.get(kind)
            if grant is None:
                discounted.append(eid)
                if kind in NON_PROMOTING_EVIDENCE_KINDS:
                    reason = DemotionReason.A_READING_IS_NOT_A_MEASUREMENT
                continue

            if not capability:
                discounted.append(eid)
                self._refuse(RefusalKind.EVIDENCE_FROM_ABSENT_CAPABILITY, subject_id,
                             "evidence '{}' claims a measurement and names no capability"
                             .format(eid))
                continue
            if capability in self.gap_capabilities:
                discounted.append(eid)
                reason = DemotionReason.CAPABILITY_IS_A_GAP
                self._refuse(RefusalKind.EVIDENCE_FROM_ABSENT_CAPABILITY, subject_id,
                             "evidence '{}' rests on '{}', which is declared a capability gap"
                             .format(eid, capability))
                continue
            if self.matrix and not self.matrix.get(capability, False):
                discounted.append(eid)
                reason = DemotionReason.CAPABILITY_IS_DOWN
                self._refuse(RefusalKind.EVIDENCE_FROM_ABSENT_CAPABILITY, subject_id,
                             "evidence '{}' rests on '{}', which the capability matrix reports "
                             "unavailable".format(eid, capability))
                continue

            if capability not in measured_by:
                measured_by.append(capability)
            if _is_stronger(grant, best):
                best = grant

        return best, tuple(measured_by), tuple(discounted), reason

    # ── settling a status ────────────────────────────────────────────────────

    def _settle(self, kind: LineKind, item: Any, subject_id: str,
                evidence_ids: Sequence[str] = ()) -> Tuple[EpistemicStatus,
                                                           Optional[EpistemicStatus],
                                                           Tuple[Demotion, ...],
                                                           Tuple[str, ...], Tuple[str, ...]]:
        """`(settled, declared, demotions, measured_by, discounted)`.

        FOUR GATES, EACH ONLY DOWNWARD. The declaration, the wall, the kind's ceiling, the
        evidence. A line leaves this function no stronger than it entered at every one of them,
        which is what `_assert_never_promoted` checks at the end and what the tests check from the
        outside.
        """
        ceiling = CEILING_BY_KIND[kind]
        demotions: List[Demotion] = []
        declared, readable = _status(_first_field(item, _STATUS_FIELDS)) if item is not None \
            else (None, True)

        # 1. the declaration ---------------------------------------------------
        if not readable:
            self._refuse(RefusalKind.UNKNOWN_STATUS, subject_id,
                         "declares '{}', which is not one of the five kinds of knowing"
                         .format(_first_field(item, _STATUS_FIELDS)))
            declared = None
        must_declare = kind in (LineKind.OBSERVATION, LineKind.ALIGNMENT, LineKind.RELATION)
        if declared is None and must_declare:
            # Only when nothing was said at all. A producer that said something unreadable has
            # already been refused above, and reporting it twice would make one wiring fault look
            # like two — the sort of noise that trains a reader to skim the refusal list.
            if readable:
                self._refuse(
                    RefusalKind.UNDECLARED_STATUS, subject_id,
                    "carries no epistemic status; an untagged claim reads as a confident one")
            current = EpistemicStatus.UNCERTAIN
            demotions.append(Demotion(EpistemicStatus.UNCERTAIN, EpistemicStatus.UNCERTAIN,
                                      DemotionReason.NO_STATUS_WAS_DECLARED))
        else:
            current = declared if declared is not None else ceiling

        # 2. the wall, in both directions ---------------------------------------
        if ceiling in WALLED_STATUSES:
            # A proposal. It came from outside the picture and no evidence inside one can move it.
            if declared is not None and declared in IMAGE_STATUSES:
                demotions.append(Demotion(declared, ceiling, DemotionReason.NOT_FROM_THE_IMAGE,
                                          "the inquirer's own sentence is not something the "
                                          "picture shows"))
            return ceiling, declared, tuple(demotions), (), ()
        if current in WALLED_STATUSES:
            # An image-facing line arriving already walled. It is not moved — that is what walled
            # means — but its being here at all is the error, and it is reported as one.
            self._refuse(RefusalKind.SOURCED_CLAIM_ABOUT_THE_IMAGE, subject_id,
                         "a claim from outside the image was filed as one about it; it keeps its "
                         "'{}' status and gains nothing from the picture"
                         .format(EpistemicStatus.SOURCED.value))
            return current, declared, tuple(demotions), (), ()

        # 3. the ceiling for this kind ------------------------------------------
        if _is_stronger(current, ceiling):
            reason = (DemotionReason.A_CHOICE_IS_NOT_A_FINDING if kind is LineKind.CHOICE
                      else DemotionReason.CEILING_FOR_THIS_KIND)
            demotions.append(Demotion(current, ceiling, reason,
                                      "a '{}' line can be no stronger than '{}'"
                                      .format(kind.value, ceiling.value)))
            current = ceiling

        # 4. the evidence --------------------------------------------------------
        best, measured_by, discounted, why = self._weigh(evidence_ids, subject_id, declared)
        if _is_stronger(current, best):
            demotions.append(Demotion(current, best, why))
            current = best

        return current, declared, tuple(demotions), measured_by, discounted

    # ── building a line ──────────────────────────────────────────────────────

    def _line(self, section: SectionId, kind: LineKind, text: str, item: Any, item_id: str,
              *, producer: str = "", source_ids: Sequence[str] = (), subjects: Sequence[str] = (),
              because: str = "", stance: str = "", standing: str = "",
              extra_demotions: Sequence[Demotion] = ()) -> Line:
        evidence_ids = self._evidence_for(item, item_id) if item is not None else ()
        settled, declared, demotions, measured_by, discounted = self._settle(
            kind, item, item_id, evidence_ids)
        for demotion in extra_demotions:
            # A standing-driven cap (a critique that would not vouch, a relation nobody examined)
            # applies AFTER the evidence gate and, like every other gate here, only downward.
            #
            # RECORDED EVEN WHEN IT DOES NOT BITE, which is the one place this module keeps a
            # same-status step. The other gates are silent when they change nothing, because
            # `declared_status` already tells that story. This one is not: "it stayed interpretive
            # because nothing critiqued it" and "it stayed interpretive because nothing measured
            # it" are different facts about the same line, and section 5 reports whichever this
            # list ends with. Dropping the no-op step would make the second the answer to both.
            if not _is_stronger(demotion.to_status, settled):
                demotions = demotions + (Demotion(settled, demotion.to_status, demotion.reason,
                                                  demotion.detail),)
                settled = demotion.to_status
        attribution = Attribution(
            producer=producer or _text(_field(item, "producer", "")) or COMPOSER_PRODUCER,
            source_ids=tuple(source_ids) or ((item_id,) if item_id else ()),
            evidence_ids=evidence_ids, measured_by=measured_by, discounted_evidence=discounted)
        return Line(
            line_id=line_id(self.inquiry_id, section, kind, text, attribution.source_ids),
            kind=kind, text=text, status=settled, origin=ORIGIN_BY_KIND[kind],
            attribution=attribution, declared_status=declared, demotions=demotions,
            subjects=tuple(subjects), because=because, stance=stance, standing=standing)

    def _add(self, section: SectionId, line: Line) -> Line:
        self._sections[section].append(line)
        return line

    def _plain(self, section: SectionId, kind: LineKind, text: str, *, status: EpistemicStatus,
               origin: Origin, attribution: Attribution, id_parts: Sequence[str] = (),
               declared: Optional[EpistemicStatus] = None,
               demotions: Sequence[Demotion] = (), subjects: Sequence[str] = (),
               because: str = "", restates: str = "", standing: str = "",
               blocks: Sequence[str] = ()) -> Line:
        """A line the composer authors itself, with no status to settle.

        Sections 5 and 6 do not settle anything: a residue carries the status its original already
        arrived at, and a gap is a statement about what is missing. Running them through `_settle`
        would give the residue a second, differently-derived status for the same sentence — two
        answers to one question, which is the drift this module is otherwise built to avoid.
        """
        return Line(
            line_id=line_id(self.inquiry_id, section, kind, text,
                            tuple(id_parts) or attribution.source_ids),
            kind=kind, text=text, status=status, origin=origin, attribution=attribution,
            declared_status=declared, demotions=tuple(demotions), subjects=tuple(subjects),
            because=because, restates=restates, standing=standing, blocks=tuple(blocks))

    # ── 1. what the inquirer proposed ────────────────────────────────────────

    def _build_proposed(self) -> None:
        """The prompt verbatim, then each hypothesis, all of it `sourced`.

        THE PROMPT IS ALWAYS HERE, even when no hypothesis was extracted from it. A section 1 that
        went empty because the extractor found nothing would say "the inquirer proposed nothing",
        which is never true of an inquiry that exists.
        """
        self._add(SectionId.PROPOSED, self._line(
            SectionId.PROPOSED, LineKind.PROPOSAL, self.prompt, None, self.inquiry_id,
            producer="inquirer", source_ids=(self.inquiry_id,),
            subjects=self.map_image_order))

        for hid in self.hypothesis_order:
            h = self.hypotheses[hid]
            text = _item_text(h)
            if not text.strip():
                self._refuse(RefusalKind.EMPTY_STATEMENT, hid, "a hypothesis with no sentence")
                continue
            self._add(SectionId.PROPOSED, self._line(
                SectionId.PROPOSED, LineKind.PROPOSAL, text, h, hid, producer="inquirer",
                subjects=_ids(_first_field(h, ("images", "image_ids", "subjects"), ())),
                because=_text(_first_field(h, _BECAUSE_FIELDS, ""))))

    # ── 2. what each image was said to suggest ───────────────────────────────

    def _build_suggested(self) -> Tuple[str, ...]:
        """Observations grouped by image, then the alignments against the inquirer's hypotheses.

        GROUPING ORDER is the map's image order first, then any image an observation names that
        the map did not — appended rather than dropped, because an observation about a picture
        nobody listed is a wiring fault worth seeing, not a reason to lose the sentence.

        AN ALIGNMENT LIVES HERE, not in section 1. "This picture supports what you proposed" is a
        claim about the picture; filing it beside the proposal would let a reader take the
        proposal as having been checked, which is exactly the laundering the wall prevents in the
        other direction.
        """
        placed: Dict[str, List[Any]] = {}
        order: List[str] = [i for i in self.map_image_order]
        seen_ids: List[str] = []

        for obs in (self.request.observations or ()):
            oid = _item_id(obs, "observation")
            text = _item_text(obs)
            if not oid:
                self._refuse(RefusalKind.UNIDENTIFIED_ITEM, text[:60],
                             "an observation with no id cannot be cited by anything downstream")
                continue
            if oid in seen_ids:
                self._refuse(RefusalKind.DUPLICATE_ID, oid, "two observations share one id")
                continue
            if not text.strip():
                self._refuse(RefusalKind.EMPTY_STATEMENT, oid, "an observation with no sentence")
                continue
            image = _text(_first_field(obs, ("image_id", "post_id", "image", "of"), ""))
            if not image:
                self._refuse(RefusalKind.UNANCHORED_OBSERVATION, oid,
                             "names no image; a reading of nothing in particular cannot be "
                             "attributed to a picture")
                continue
            seen_ids.append(oid)
            if image not in order:
                order.append(image)
            placed.setdefault(image, []).append(obs)

        for image in order:
            for obs in placed.get(image, ()):
                oid = _item_id(obs, "observation")
                self._add(SectionId.SUGGESTED, self._line(
                    SectionId.SUGGESTED, LineKind.OBSERVATION, _item_text(obs), obs, oid,
                    subjects=(image,),
                    because=_text(_first_field(obs, _BECAUSE_FIELDS, ""))))

        for al in (self.request.alignments or ()):
            aid = _item_id(al, "alignment")
            text = _item_text(al)
            hid = _text(_first_field(al, ("hypothesis_id", "hypothesis", "of"), ""))
            oid = _text(_first_field(al, ("observation_id", "observation"), ""))
            if not aid:
                self._refuse(RefusalKind.UNIDENTIFIED_ITEM, text[:60], "an alignment with no id")
                continue
            if hid not in self.hypotheses:
                self._refuse(RefusalKind.DANGLING_HYPOTHESIS, aid,
                             "aligns against hypothesis '{}', which the map does not contain"
                             .format(hid))
                continue
            if oid and oid not in seen_ids:
                self._refuse(RefusalKind.DANGLING_OBSERVATION, aid,
                             "cites observation '{}', which was not placed".format(oid))
                continue
            if not text.strip():
                self._refuse(RefusalKind.EMPTY_STATEMENT, aid, "an alignment with no sentence")
                continue
            sources = tuple(x for x in (aid, hid, oid) if x)
            self._add(SectionId.SUGGESTED, self._line(
                SectionId.SUGGESTED, LineKind.ALIGNMENT, text, al, aid, source_ids=sources,
                subjects=tuple(x for x in (hid, oid) if x),
                stance=_text(_first_field(al, ("stance", "direction", "verdict"), "")),
                because=_text(_first_field(al, _BECAUSE_FIELDS, ""))))

        return tuple(seen_ids)

    # ── 3. what Semant chose to compare ──────────────────────────────────────

    def _build_compared(self, placed_observations: Sequence[str]) -> None:
        """The contrast plans, kept even where one of their citations is broken.

        THE RULE FOR WHAT IS DROPPED AND WHAT IS KEPT, and it is the same everywhere in this
        module: an item is dropped when it cannot be stated without inventing something, and kept
        with a refusal beside it when it can. An alignment whose hypothesis does not exist cannot
        be stated — "this image supports —" is not a sentence. A plan that cites one observation
        that does not exist can still be stated: the choice was made, and only the citation is
        broken. So the plan survives with the bad reference stripped and the refusal on record.
        """
        for plan in (self.request.contrast_plans or ()):
            pid = _item_id(plan, "plan")
            text = _item_text(plan)
            if not pid:
                self._refuse(RefusalKind.UNIDENTIFIED_ITEM, text[:60], "a contrast plan with no id")
                continue
            if not text.strip():
                self._refuse(RefusalKind.EMPTY_STATEMENT, pid, "a contrast plan with no sentence")
                continue
            cited = _ids(_first_field(plan, ("observation_ids", "observations", "of"), ()))
            good = []
            for oid in cited:
                if oid in placed_observations:
                    good.append(oid)
                else:
                    self._refuse(RefusalKind.DANGLING_OBSERVATION, pid,
                                 "cites observation '{}', which was not placed".format(oid))
            self._add(SectionId.COMPARED, self._line(
                SectionId.COMPARED, LineKind.CHOICE, text, plan, pid,
                source_ids=(pid,) + tuple(good),
                subjects=_ids(_first_field(plan, ("images", "image_ids", "subjects"), ())),
                because=_text(_first_field(plan, _BECAUSE_FIELDS, ""))))

    # ── 4. which relations survived critique ─────────────────────────────────

    def _build_survived(self) -> Tuple[str, ...]:
        """Every candidate relation that entered, each carrying what became of it.

        FOUR OUTCOMES AND NOT TWO. `uncritiqued` is the one that keeps getting collapsed into
        `sustained` by anything that filters on "was it rejected?", and it is the opposite: a
        relation nobody examined has not passed anything. It is capped at `interpretive` here for
        that reason — the measurement, where there is one, backs the relation's PARTS, and nothing
        has yet checked that the parts add up to the claim.
        """
        entries: Dict[str, Tuple[Any, Standing]] = {}
        order: List[str] = []

        for rel in (self.request.accepted_relations or ()):
            rid = _item_id(rel, "relation")
            if not rid:
                self._refuse(RefusalKind.UNIDENTIFIED_ITEM, _item_text(rel)[:60],
                             "an accepted relation with no id")
                continue
            if rid in entries:
                self._refuse(RefusalKind.DUPLICATE_ID, rid, "two accepted relations share one id")
                continue
            entries[rid] = (rel, Standing.SUSTAINED)
            order.append(rid)

        for rel in (self.request.rejected_relations or ()):
            rid = _item_id(rel, "relation")
            if not rid:
                self._refuse(RefusalKind.UNIDENTIFIED_ITEM, _item_text(rel)[:60],
                             "a rejected relation with no id")
                continue
            if rid in entries:
                # Accepted and rejected at once. The weaker reading governs — a relation that
                # anything rejected is not one that survived — and the contradiction is reported
                # rather than resolved quietly.
                self._refuse(RefusalKind.DUPLICATE_ID, rid,
                             "appears in both the accepted and the rejected set; it is treated as "
                             "rejected")
                entries[rid] = (entries[rid][0], Standing.REJECTED)
                continue
            entries[rid] = (rel, Standing.REJECTED)
            order.append(rid)

        for rid in order:
            rel, base = entries[rid]
            text = _item_text(rel)
            if not text.strip():
                self._refuse(RefusalKind.EMPTY_STATEMENT, rid, "a relation with no sentence")
                continue
            critique = self.critique_by_relation.get(rid)
            verdict = normalise(_first_field(critique, ("verdict", "outcome", "stance"), "")) \
                if critique is not None else ""
            because = _text(_first_field(critique, _BECAUSE_FIELDS + _TEXT_FIELDS, "")) \
                if critique is not None else ""
            extra: List[Demotion] = []

            if base is Standing.REJECTED:
                standing = Standing.REJECTED
                extra.append(Demotion(EpistemicStatus.UNCERTAIN, EpistemicStatus.UNCERTAIN,
                                      DemotionReason.IT_WAS_NOT_ACCEPTED,
                                      "it is here so that what was discarded stays visible"))
                if verdict in SUSTAINING_VERDICTS:
                    self._refuse(RefusalKind.CONTRADICTED_ACCEPTANCE, rid,
                                 "was rejected, yet its critique upheld it")
            elif critique is None:
                standing = Standing.UNCRITIQUED
                extra.append(Demotion(EpistemicStatus.INTERPRETIVE, EpistemicStatus.INTERPRETIVE,
                                      DemotionReason.NOTHING_CRITIQUED_IT,
                                      "accepted, and nothing examined it"))
            elif verdict in SUSTAINING_VERDICTS:
                standing = Standing.SUSTAINED
            elif verdict in REFUTING_VERDICTS:
                standing = Standing.REFUTED
                extra.append(Demotion(EpistemicStatus.UNCERTAIN, EpistemicStatus.UNCERTAIN,
                                      DemotionReason.CRITIQUE_WITHHELD_SUPPORT, verdict))
                self._refuse(RefusalKind.CONTRADICTED_ACCEPTANCE, rid,
                             "was accepted, and its critique refuted it")
            else:
                # An unrecognised verdict withholds. An unreadable critique is not an endorsement.
                standing = Standing.WITHHELD
                extra.append(Demotion(EpistemicStatus.UNCERTAIN, EpistemicStatus.UNCERTAIN,
                                      DemotionReason.CRITIQUE_WITHHELD_SUPPORT,
                                      verdict or "the critique returned no verdict"))
                self._refuse(RefusalKind.CONTRADICTED_ACCEPTANCE, rid,
                             "was accepted, and its critique would not vouch for it")

            self._add(SectionId.SURVIVED, self._line(
                SectionId.SURVIVED, LineKind.RELATION, text, rel, rid,
                subjects=_ids(_first_field(rel, ("subjects", "images", "image_ids", "of"), ())),
                because=because, standing=standing.value, extra_demotions=extra))

        return tuple(order)

    # ── 5. what remained interpretive ────────────────────────────────────────

    #: The sections section 5 accounts for. Section 1 is absent deliberately: a proposal is
    #: `sourced`, and `sourced` never was interpretive and never will be. Calling it a residue
    #: would put the inquirer's own sentence on the image scale by the back door.
    RESIDUE_SOURCES: Tuple[SectionId, ...] = (SectionId.SUGGESTED, SectionId.COMPARED,
                                              SectionId.SURVIVED)

    def _build_interpretive(self) -> Tuple[Line, ...]:
        """Every line above that no measuring capability backed, restated by reference.

        DERIVED, NOT AUTHORED. The section is a projection of what sections 2 to 4 already settled,
        so it cannot disagree with them and cannot be forgotten: adding a line up there adds one
        here unless something measured it. `text` is copied verbatim from the original rather than
        summarised, and `because` is one of the closed `DemotionReason` values rather than a
        sentence, because a composer writing its own prose about why a claim is weak would be the
        one unattributed voice in the output.
        """
        residues: List[Line] = []
        for section in self.RESIDUE_SOURCES:
            for original in self._sections[section]:
                if original.is_backed:
                    continue
                reason = (original.demotions[-1].reason.value if original.demotions
                          else DemotionReason.NO_MEASURING_CAPABILITY.value)
                residue = self._plain(
                    SectionId.INTERPRETIVE, LineKind.RESIDUE, original.text,
                    status=original.status,
                    # The residue reports on someone else's sentence, so it carries THEIR origin.
                    # Stamping it `system` would make the composer the speaker of every weak claim
                    # in the inquiry.
                    origin=original.origin, attribution=original.attribution,
                    id_parts=(original.line_id,) + original.attribution.source_ids,
                    declared=original.declared_status, demotions=original.demotions,
                    subjects=original.subjects, because=reason, restates=original.line_id,
                    standing=original.standing)
                residues.append(self._add(SectionId.INTERPRETIVE, residue))
        return tuple(residues)

    # ── 6. what could be measured ────────────────────────────────────────────

    def _build_measurable(self, residues: Sequence[Line]) -> None:
        """For each residue, the capability that would settle it — and whether it exists.

        THREE STANDINGS, and the first is the one worth building this section for:

          present     something in the system could measure this and nothing did. Actionable now.
          absent      the gap list or the capability matrix says nothing can. Actionable later.
          undeclared  no matrix was supplied and no gap names it, so its existence is unknown.

        AND A FOURTH LINE that names no capability at all. When nothing in the observables or the
        gap list says what would settle a residue, the composer does NOT invent a plausible
        capability name — that is the failure this whole lane exists to prevent, arriving one
        level up. It says so instead, and lists what is stranded.
        """
        by_source: Dict[str, str] = {}          # source id → the residue line it belongs to
        for residue in residues:
            for sid in residue.attribution.source_ids:
                by_source.setdefault(sid, residue.line_id)

        # key → (capability, text, standing, source_ids, blocks)
        entries: Dict[str, Dict[str, Any]] = {}
        stranded: List[str] = []

        def _standing_of(capability: str) -> str:
            if not capability:
                # An observable that says what would settle a residue without saying what would
                # produce it. Not `absent` — nothing has been asserted about a capability, because
                # none was named — and the composer does not supply the missing name.
                return "unnamed"
            if capability in self.gap_capabilities:
                return "absent"
            if not self.matrix:
                return "undeclared"
            return "present" if self.matrix.get(capability, False) else "absent"

        def _record(key: str, capability: str, text: str, sources: Sequence[str],
                    block: str) -> None:
            entry = entries.get(key)
            if entry is None:
                entry = entries[key] = {"capability": capability, "text": text,
                                        "standing": _standing_of(capability),
                                        "sources": list(dict.fromkeys(sources)), "blocks": []}
            # An empty block is a gap nothing in this inquiry happened to need. It is recorded
            # with no blocks rather than with a blank one, so `blocks` never carries a line id
            # that is not a line.
            if block and block not in entry["blocks"]:
                entry["blocks"].append(block)

        matched: List[str] = []
        for obs in (self.request.observables or ()):
            oid = _item_id(obs, "observable")
            target_ids = _ids(_first_field(obs, _TARGET_FIELDS, ()))
            blocks = [by_source[t] for t in target_ids if t in by_source]
            if not blocks:
                continue
            caps = _ids(_first_field(obs, ("capability_classes", "capabilities", "capability"), ()))
            text = _item_text(obs)
            for capability in (caps or ("",)):
                for block in blocks:
                    _record("obs::{}::{}".format(oid, capability), capability, text,
                            (oid,) + target_ids, block)
            matched.extend(blocks)

        for gap in self.gaps:
            gid = _item_id(gap, "gap")
            capability = _text(_field(gap, "capability", ""))
            needed = _ids(_first_field(gap, ("needed_for", "blocks", "of", "for"), ()))
            blocks = [by_source[n] for n in needed if n in by_source]
            text = (_item_text(gap)
                    or "no capability in this system computes '{}'".format(capability))
            if blocks:
                for block in blocks:
                    _record("gap::{}".format(gid), capability, text, (gid,) + needed, block)
                matched.extend(blocks)
            else:
                # A gap nobody's residue points at is still a gap. It is named with no blocks
                # rather than dropped, because "we know this is missing" is worth as much when
                # nothing in this inquiry happened to need it.
                _record("gap::{}".format(gid), capability, text, (gid,), "")

        for residue in residues:
            if residue.line_id not in matched:
                stranded.append(residue.line_id)

        for entry in entries.values():
            self._add(SectionId.MEASURABLE, self._plain(
                SectionId.MEASURABLE, LineKind.GAP, entry["text"],
                status=EpistemicStatus.UNCERTAIN, origin=ORIGIN_BY_KIND[LineKind.GAP],
                attribution=Attribution(producer=COMPOSER_PRODUCER,
                                        source_ids=tuple(entry["sources"])),
                subjects=(entry["capability"],) if entry["capability"] else (),
                standing=entry["standing"], blocks=tuple(entry["blocks"])))

        if stranded:
            self._add(SectionId.MEASURABLE, self._plain(
                SectionId.MEASURABLE, LineKind.GAP, NOTHING_NAMED,
                status=EpistemicStatus.UNCERTAIN, origin=ORIGIN_BY_KIND[LineKind.GAP],
                attribution=Attribution(producer=COMPOSER_PRODUCER),
                id_parts=(NOTHING_NAMED,), standing="unnamed", blocks=tuple(stranded)))

    # ── the whole thing ──────────────────────────────────────────────────────

    def run(self) -> Composition:
        self._build_proposed()
        placed = self._build_suggested()
        self._build_compared(placed)
        relations = self._build_survived()

        for critique in (self.request.critiques or ()):
            rid = _text(_first_field(critique, ("relation_id", "candidate_id", "of", "target"), ""))
            if rid and rid not in relations:
                self._refuse(RefusalKind.DANGLING_RELATION, _item_id(critique, "critique"),
                             "critiques relation '{}', which was neither accepted nor rejected"
                             .format(rid))

        residues = self._build_interpretive()
        self._build_measurable(residues)

        sections = tuple(
            Section(section=s, section_uid=section_id(self.inquiry_id, s), title=SECTION_TITLES[s],
                    lines=tuple(self._sections[s]), emptiness=SECTION_EMPTINESS[s])
            for s in SECTION_ORDER)
        composition = Composition(
            composition_uid=composition_id(self.inquiry_id, self.prompt),
            inquiry_id=self.inquiry_id, prompt=self.prompt, sections=sections,
            refusals=tuple(self._refusals.values()),
            provenance=ComposerProvenance(composed_at=_text(self.request.now)))
        assert_never_promoted(composition)
        return composition


#: What section 6 says when nothing in the inputs names a capability that would settle a residue.
#: A constant rather than an f-string, so the one sentence the composer authors about a missing
#: capability is the same sentence every time and can be grepped for.
NOTHING_NAMED = "nothing names a capability that would settle this"


class ComposerViolation(Exception):
    """A composition that promoted something. Raised rather than returned: a caller holding one of
    these is about to publish a claim as better-founded than its inputs allow, and there is no
    sensible way to continue."""


def assert_never_promoted(composition: Composition) -> None:
    """The invariant, checked on the way out of every composition.

    Two things, both of them the same thing. No recorded demotion may move a line UP the image
    scale, and no line may end stronger than its producer declared it. The second is what makes
    the first more than bookkeeping: a gate that forgot to record its demotion would still be
    caught here.

    A line that ends `sourced` having declared an image status is not a promotion — it is the wall,
    which moves a claim off the scale rather than up it — and is exempt by construction, since
    `_is_stronger` is false whenever either side is off-scale.
    """
    for line in composition.lines():
        for demotion in line.demotions:
            if _is_stronger(demotion.to_status, demotion.from_status):
                raise ComposerViolation(
                    "line {} records a move from '{}' to '{}', which is a promotion"
                    .format(line.line_id, demotion.from_status.value, demotion.to_status.value))
        if line.declared_status is not None and _is_stronger(line.status, line.declared_status):
            raise ComposerViolation(
                "line {} was declared '{}' and settled at '{}'; a composer may weaken a producer's "
                "claim and never strengthen it"
                .format(line.line_id, line.declared_status.value, line.status.value))


def compose(request: CompositionRequest) -> Composition:
    """The whole lane. Plain data in, a `Composition` out; nothing else happens."""
    return _Composer(request).run()


__all__ = [
    "COMPOSER_PRODUCER", "SCHEMA_VERSION", "NOTHING_NAMED",
    "Origin", "SectionId", "LineKind", "Standing", "DemotionReason", "RefusalKind",
    "SECTION_ORDER", "SECTION_TITLES", "SECTION_EMPTINESS", "CEILING_BY_KIND", "ORIGIN_BY_KIND",
    "MEASURING_EVIDENCE_KINDS", "NON_PROMOTING_EVIDENCE_KINDS", "AGREEMENT_EVIDENCE_KINDS",
    "SUSTAINING_VERDICTS", "REFUTING_VERDICTS",
    "PREFIXES", "WIDTH", "normalise", "composition_id", "section_id", "line_id", "refusal_id",
    "Demotion", "Attribution", "Line", "Section", "Refusal", "ComposerProvenance", "Composition",
    "CompositionRequest", "ComposerViolation",
    "canonical", "assert_never_promoted", "compose",
]
