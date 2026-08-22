"""
INTELLIGENCE-002A — the observation audit: what the two passes did wrong, said out loud.

The observer is built so that the worst failures are unrepresentable. This file is for the rest —
the failures that arrive looking exactly like good work, in a reply that parsed cleanly.

    audit(observations, alignments=…, inquiry=…, declared_images=…)  →  AuditReport

## The auditor is prompt-aware ON PURPOSE, and runs last

Everything else in this section keeps the person's words away from the images. The auditor is the
one place that holds both, because its job is to notice when they have already met: a word the
person used inside a hypothesis, turning up in a reading that was supposed to have been taken
before anyone knew the hypothesis existed.

That is only safe under one condition, and it is structural rather than stated: NOTHING HERE
RETURNS AN OBSERVATION. `audit` returns findings. It cannot amend, re-tag or re-word a
`VisualObservation`, so there is no path by which the prompt reaches an observation through the
auditor. It runs after, it reads, it reports.

## Leakage is judged by WHERE the person said the word, not by what the word is

The hard case: the person writes "are the columns evenly spaced?", and the prompt-blind observer
says "columns, evenly spaced". Nothing leaked. They are both looking at columns.

Now the person writes "I think the columns are doing the emotional work", and the blind observer
says "the columns do the emotional work". That is the failure, and no property of the WORD
separates the two cases — only where in the prompt it was said.

So `UserTerm.origins` decides severity. A term drawn from a HYPOTHESIS or an INTERPRETIVE_QUESTION
is theory-laden language and finding it in a blind reading is a VIOLATION. The same term drawn
from an OBSERVABLE_QUESTION is a thing the person expected to be nameable, and finding it is a
SUSPICION worth a person's eye and not an assertion of misconduct. Terms that occur only inside an
INSTRUCTION ("look at these two images") are not checked at all: "images" is not anybody's theory.

## Speculation and history are caught by FORM, not by subject

Spine rule 5 forbids baking a topic into production logic, so there is no list of periods, styles,
movements or materials in this file. What it matches is grammatical:

    intent      an agent given a purpose — `the \\w+ intended`, "meant to", "in order to"
    history     dated and provenanced language — "17th century", "originally", "attributed to"
    hedge       "probably", "perhaps", "may have been"

And it matches them PER FIELD, which is the whole reason `VisualObservation` splits description
from possibility. "It may have been added later" is not a forbidden sentence — it is a perfectly
good `interpretive_possibility`. It is a violation in `visible_organization`, because that field
is the one downstream code reads as what the picture shows. The policy table below is the
enforcement, and it is a table so that arguing with it is a diff.

## A clean report does not mean everything was checked

`AuditReport.clean` says no violations were found. `AuditReport.complete` says every check ran.
They are separate because most calls will lack something — no `InquiryMap`, so no leakage check —
and one boolean covering both would let an audit that skipped its most important check report the
same word as an audit that passed it. `checks_skipped` carries the reason for each.

PURE MODULE. No database, no network, no model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import (Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple,
                    Union)

from backend.services.epistemics import EpistemicStatus
from backend.services.inquiry_intelligence.intent import (HEDGE_MARKERS, ElementKind, InquiryMap,
                                                          UserTerm)
from backend.services.inquiry_intelligence.observer import (AGREEMENT_PSEUDO_CAPABILITIES,
                                                            AlignmentSet, BlindObservationSet,
                                                            HypothesisAlignment, ImageRef,
                                                            VisualObservation)

AUDIT_VERSION = "observation-audit.v1"


class AuditCode(str, Enum):
    MISSING_IMAGE_REF = "missing_image_ref"
    MISSING_SOURCE_REF = "missing_source_ref"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    DUPLICATE_OBSERVATION_ID = "duplicate_observation_id"
    HALLUCINATED_IMAGE_REF = "hallucinated_image_ref"
    HALLUCINATED_OBSERVATION_ID = "hallucinated_observation_id"
    HALLUCINATED_HYPOTHESIS_ID = "hallucinated_hypothesis_id"
    PROMPT_VOCABULARY_IN_BLIND_OBSERVATION = "prompt_vocabulary_in_blind_observation"
    MEASURED_WITHOUT_EVIDENCE = "measured_without_evidence"
    SPECULATION_AS_DESCRIPTION = "speculation_as_description"
    HISTORICAL_CLAIM_AS_DESCRIPTION = "historical_claim_as_description"


class Severity(str, Enum):
    """VIOLATION: a law was broken. SUSPICION: this may be innocent and a person should look.

    Two levels rather than three. A scale of five would invite tuning the number instead of
    fixing the thing, and the only decision anyone makes from a finding is whether to act on it
    now or read it later.
    """
    VIOLATION = "violation"
    SUSPICION = "suspicion"


class AuditCheck(str, Enum):
    IMAGE_REFS = "image_refs"
    SOURCE_REFS = "source_refs"
    DUPLICATION = "duplication"
    ID_INTEGRITY = "id_integrity"
    PROMPT_LEAKAGE = "prompt_leakage"
    MEASUREMENT_EVIDENCE = "measurement_evidence"
    DESCRIPTION_PURITY = "description_purity"


@dataclass(frozen=True)
class AuditFinding:
    code: AuditCode
    severity: Severity
    subject_id: str
    detail: str
    evidence: Tuple[str, ...] = ()
    field_name: str = ""


@dataclass(frozen=True)
class AuditReport:
    findings: Tuple[AuditFinding, ...]
    checks_run: Tuple[AuditCheck, ...]
    checks_skipped: Tuple[Tuple[AuditCheck, str], ...] = ()
    observation_count: int = 0
    alignment_count: int = 0
    auditor: str = AUDIT_VERSION

    @property
    def violations(self) -> Tuple[AuditFinding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.VIOLATION)

    @property
    def suspicions(self) -> Tuple[AuditFinding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.SUSPICION)

    @property
    def clean(self) -> bool:
        """No violations. Says nothing about what was checked — see `complete`."""
        return not self.violations

    @property
    def complete(self) -> bool:
        """Every check ran. A `clean` report that is not `complete` is a narrower claim."""
        return not self.checks_skipped

    def by_code(self, code: AuditCode) -> Tuple[AuditFinding, ...]:
        return tuple(f for f in self.findings if f.code is code)


# ── marker tables: grammar, not subject matter ───────────────────────────────

#: Purpose attributed to a maker. The second pattern is the general case: an article, a noun, and
#: a verb of intention. It catches "the artist intended", "the designer wanted", "its maker chose"
#: without this file ever naming an artist, a designer or a maker.
INTENT_MARKERS: Tuple[str, ...] = (
    "intended to", "intended as", "was intended", "meant to", "meant as", "in order to",
    "so as to", "so that it would", "deliberately", "purposefully", "on purpose",
    "designed to", "built to", "made to", "aims to", "aimed to", "seeks to", "sought to",
    "trying to", "tries to", "attempts to", "wants to", "wanted to", "chose to",
)

_AGENCY_INTENT = re.compile(
    r"\b(?:the|its|his|her|their|a|an)\s+\w+\s+"
    r"(?:intended|intends|meant|means|wanted|wants|chose|chooses|decided|decides|sought|seeks|"
    r"aimed|aims|tried|tries|intended)\b", re.I)

#: Dated, provenanced, restored, attributed. Period arithmetic and provenance verbs — no style,
#: movement or material names, which would be topic.
HISTORICAL_MARKERS: Tuple[str, ...] = (
    "originally", "historically", "at the time", "in its day", "dates from", "dating from",
    "dates to", "was built", "were built", "was made", "were made", "was carved", "were carved",
    "was created", "were created", "was painted", "were painted", "was commissioned",
    "commissioned by", "attributed to", "influenced by", "in the tradition of", "derives from",
    "derived from", "later added", "added later", "was restored", "was rebuilt", "was replaced",
    "predates", "postdates", "survives from", "in antiquity",
)

#: A bare number is not a date. "roughly 1200 pixels across" and "about 240 units wide" are
#: descriptions, and flagging either would raise a VIOLATION against an honest reading — so a year
#: has to arrive with a temporal cue AND look like a year, or arrive as a plural decade.
_HISTORICAL_DATING = re.compile(
    r"\b\d{1,2}(?:st|nd|rd|th)[\s-]centur(?:y|ies)\b"
    r"|\bcentur(?:y|ies)\b"
    r"|\b(?:in|from|of|since|around|about|by|before|after|dated|circa)\s+(?:1\d{3}|20\d{2})s?\b"
    r"|\b1\d{2}0s\b|\b20\d0s\b"
    r"|\bc(?:irca)?\.\s*\d{3,4}\b", re.I)

#: CASE-SENSITIVE, unlike everything else here, because "ad" is an ordinary English word and
#: `re.I` would turn every mention of an ad into a dated claim.
_HISTORICAL_ERA = re.compile(r"\b(?:B\.?C\.?E?\.?|A\.?D\.?)\b")


class MarkerFamily(str, Enum):
    INTENT = "intent"
    HISTORY = "history"
    HEDGE = "hedge"


#: Which families each field may carry, and how badly it reads when it does.
#:
#: `interpretive_possibility` and `uncertainty` are absent from this table on purpose: they are the
#: fields where a hedge and a historical guess are the CORRECT content, and a policy that flagged
#: them would push every honest "this may be later" out of the field built to hold it and into
#: nowhere.
_FIELD_POLICY: Mapping[str, Mapping[MarkerFamily, Severity]] = {
    "feature": {MarkerFamily.INTENT: Severity.VIOLATION, MarkerFamily.HISTORY: Severity.VIOLATION},
    "locus": {MarkerFamily.INTENT: Severity.VIOLATION, MarkerFamily.HISTORY: Severity.VIOLATION},
    "visible_organization": {MarkerFamily.INTENT: Severity.VIOLATION,
                             MarkerFamily.HISTORY: Severity.VIOLATION,
                             MarkerFamily.HEDGE: Severity.SUSPICION},
    "appearance_effect": {MarkerFamily.HISTORY: Severity.VIOLATION,
                          MarkerFamily.INTENT: Severity.SUSPICION},
}

_CODE_FOR_FAMILY = {
    MarkerFamily.INTENT: AuditCode.SPECULATION_AS_DESCRIPTION,
    MarkerFamily.HEDGE: AuditCode.SPECULATION_AS_DESCRIPTION,
    MarkerFamily.HISTORY: AuditCode.HISTORICAL_CLAIM_AS_DESCRIPTION,
}

#: Below this, a shared word between a prompt and a reading is noise.
MIN_LEAK_TERM_LENGTH = 4

#: Origins that make a shared term a violation rather than a coincidence.
THEORY_LADEN_ORIGINS: FrozenSet[ElementKind] = frozenset({
    ElementKind.HYPOTHESIS, ElementKind.INTERPRETIVE_QUESTION})

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]+")


def _phrases(text_lower: str, markers: Sequence[str]) -> Tuple[str, ...]:
    return tuple(m for m in markers if m in text_lower)


def _stem(word: str) -> str:
    """Enough morphology to see "folds" and "folding" as the same word. No more than that."""
    w = word.lower().strip("-'’")
    for suffix, keep, add in (("ies", 3, "y"), ("ing", 3, ""), ("ed", 2, ""), ("es", 2, ""),
                              ("s", 1, "")):
        if w.endswith(suffix) and len(w) - keep >= 3:
            if suffix == "s" and w.endswith("ss"):
                continue
            return w[:-keep] + add
    return w


def _normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


def _families(text: str) -> Dict[MarkerFamily, Tuple[str, ...]]:
    lower = text.lower()
    intent = list(_phrases(lower, INTENT_MARKERS))
    intent.extend(m.group(0) for m in _AGENCY_INTENT.finditer(text))
    history = list(_phrases(lower, HISTORICAL_MARKERS))
    history.extend(m.group(0) for m in _HISTORICAL_DATING.finditer(text))
    history.extend(m.group(0) for m in _HISTORICAL_ERA.finditer(text))
    hedge = list(_phrases(lower, HEDGE_MARKERS))
    return {MarkerFamily.INTENT: tuple(dict.fromkeys(intent)),
            MarkerFamily.HISTORY: tuple(dict.fromkeys(history)),
            MarkerFamily.HEDGE: tuple(dict.fromkeys(hedge))}


# ── the checks ───────────────────────────────────────────────────────────────

def _check_refs(observations: Sequence[VisualObservation],
                declared: Optional[FrozenSet[str]]) -> List[AuditFinding]:
    out: List[AuditFinding] = []
    for o in observations:
        if not o.image_ref.strip():
            out.append(AuditFinding(
                AuditCode.MISSING_IMAGE_REF, Severity.VIOLATION, o.observation_id,
                "an observation with no image behind it. It cannot be checked against anything, "
                "and it reads downstream as a fact about whichever image is nearby."))
        elif declared is not None and o.image_ref not in declared:
            out.append(AuditFinding(
                AuditCode.HALLUCINATED_IMAGE_REF, Severity.VIOLATION, o.observation_id,
                f"names image {o.image_ref!r}, which was not among the images observed.",
                (o.image_ref,)))
        if o.claimed_image_ref and o.claimed_image_ref != o.image_ref:
            out.append(AuditFinding(
                AuditCode.HALLUCINATED_IMAGE_REF, Severity.VIOLATION, o.observation_id,
                f"the model attributed this to {o.claimed_image_ref!r} while it was reading "
                f"{o.image_ref!r}. The observer's stamp stands; the attempt is the finding.",
                (o.claimed_image_ref, o.image_ref)))
    return out


def _check_sources(observations: Sequence[VisualObservation]) -> List[AuditFinding]:
    out: List[AuditFinding] = []
    for o in observations:
        if o.provenance is None:
            out.append(AuditFinding(
                AuditCode.MISSING_SOURCE_REF, Severity.VIOLATION, o.observation_id,
                "no provenance. Nothing records which model produced this, in what sense it ran, "
                "or whether it ran at all — so the reading cannot be replayed, attributed or "
                "retired when the model behind it is."))
            continue
        if not o.provenance.request_id.strip():
            out.append(AuditFinding(
                AuditCode.MISSING_SOURCE_REF, Severity.SUSPICION, o.observation_id,
                "provenance carries no request id, so this reading cannot be tied back to the "
                "call that produced it."))
    return out


def _check_duplication(observations: Sequence[VisualObservation]) -> List[AuditFinding]:
    out: List[AuditFinding] = []
    seen_ids: Dict[str, int] = {}
    seen_content: Dict[Tuple[str, str, str, str], str] = {}
    for o in observations:
        seen_ids[o.observation_id] = seen_ids.get(o.observation_id, 0) + 1
        key = (o.image_ref, _normalise(o.feature), _normalise(o.locus),
               _normalise(o.visible_organization))
        if not any(key[1:]):
            continue
        first = seen_content.get(key)
        if first is None:
            seen_content[key] = o.observation_id
        else:
            out.append(AuditFinding(
                AuditCode.DUPLICATE_OBSERVATION, Severity.VIOLATION, o.observation_id,
                f"the same feature, locus and organisation as {first!r} on the same image. Two "
                f"records of one noticing read downstream as two independent noticings, which is "
                f"how a single reading becomes its own corroboration.",
                (first,)))
    for observation_id, count in seen_ids.items():
        if count > 1:
            out.append(AuditFinding(
                AuditCode.DUPLICATE_OBSERVATION_ID, Severity.VIOLATION, observation_id,
                f"{count} observations share this id. Every citation of it is ambiguous."))
    return out


def _check_ids(observations: Sequence[VisualObservation],
               alignments: Sequence[HypothesisAlignment],
               inquiry: Optional[InquiryMap]) -> List[AuditFinding]:
    """The same law `align_hypotheses` enforces, checked again over whatever arrived.

    Deliberately redundant. The aligner refuses an invented id at the moment it is offered; this
    catches an `AlignmentSet` assembled some other way — by hand, by a future route, by a lane
    that has not read the aligner. A guard that exists in only one place is a guard somebody
    eventually routes around.
    """
    out: List[AuditFinding] = []
    known = frozenset(o.observation_id for o in observations)
    hypotheses = inquiry.hypothesis_ids if inquiry is not None else None
    for a in alignments:
        for cited in a.observation_ids:
            if cited not in known:
                out.append(AuditFinding(
                    AuditCode.HALLUCINATED_OBSERVATION_ID, Severity.VIOLATION, a.alignment_id,
                    f"cites observation {cited!r}, which no pass produced.", (cited,)))
        if hypotheses is not None and a.hypothesis_id not in hypotheses:
            out.append(AuditFinding(
                AuditCode.HALLUCINATED_HYPOTHESIS_ID, Severity.VIOLATION, a.alignment_id,
                f"relates to hypothesis {a.hypothesis_id!r}, which is not in the map — so it "
                f"answers a claim the person did not make.", (a.hypothesis_id,)))
    return out


def _check_leakage(observations: Sequence[VisualObservation],
                   inquiry: InquiryMap) -> List[AuditFinding]:
    """The person's words, found in a reading taken before their words existed."""
    out: List[AuditFinding] = []
    watched: List[Tuple[str, UserTerm, Severity]] = []
    for term in inquiry.vocabulary:
        if len(term.term) < MIN_LEAK_TERM_LENGTH:
            continue
        if not term.origins or term.origins == {ElementKind.INSTRUCTION}:
            continue
        severity = (Severity.VIOLATION if term.origins & THEORY_LADEN_ORIGINS
                    else Severity.SUSPICION)
        for word in _WORD.findall(term.term) or [term.term]:
            if len(word) >= MIN_LEAK_TERM_LENGTH:
                watched.append((_stem(word), term, severity))
    if not watched:
        return out

    for o in observations:
        for field_name, text in o.described_fields:
            if not text:
                continue
            stems = {_stem(w) for w in _WORD.findall(text)}
            for stem, term, severity in watched:
                if stem not in stems:
                    continue
                origins = ", ".join(sorted(k.value for k in term.origins))
                out.append(AuditFinding(
                    code=AuditCode.PROMPT_VOCABULARY_IN_BLIND_OBSERVATION, severity=severity,
                    subject_id=o.observation_id, field_name=field_name,
                    detail=(f"{term.surface!r} is the person's word, used in their {origins}, and "
                            f"it appears in a reading that was taken without it."
                            if severity is Severity.VIOLATION else
                            f"{term.surface!r} appears in both the prompt (in their {origins}) "
                            f"and this reading. It may simply be the name of the thing."),
                    evidence=(term.surface, text)))
    return out


def _check_measurement(observations: Sequence[VisualObservation]) -> List[AuditFinding]:
    out: List[AuditFinding] = []
    grounded = {EpistemicStatus.MEASURED, EpistemicStatus.VISIBLE}
    for o in observations:
        measurement = o.provenance.measurement if o.provenance is not None else None
        if o.epistemic_status in grounded and measurement is None:
            out.append(AuditFinding(
                AuditCode.MEASURED_WITHOUT_EVIDENCE, Severity.VIOLATION, o.observation_id,
                f"carries status {o.epistemic_status.value!r} with no measuring capability behind "
                f"it. A reading is interpretive until something actually measured it.")) 
        if measurement is not None:
            key = measurement.capability.strip().lower().replace(" ", "_")
            if key in AGREEMENT_PSEUDO_CAPABILITIES:
                out.append(AuditFinding(
                    AuditCode.MEASURED_WITHOUT_EVIDENCE, Severity.VIOLATION, o.observation_id,
                    f"names {measurement.capability!r} as the capability that measured this. "
                    f"Agreement is a fact about models, not about the image.",
                    (measurement.capability,)))
            elif not measurement.artifact_ref.strip():
                out.append(AuditFinding(
                    AuditCode.MEASURED_WITHOUT_EVIDENCE, Severity.VIOLATION, o.observation_id,
                    "a measurement with no artifact behind it."))
        claimed = o.claimed_status.strip().lower()
        if claimed in {"measured", "visible"} and measurement is None:
            out.append(AuditFinding(
                AuditCode.MEASURED_WITHOUT_EVIDENCE, Severity.SUSPICION, o.observation_id,
                f"the model called this reading {claimed!r}. The observer recorded it as "
                f"{o.epistemic_status.value!r}, which stands — but the claim was made, and a model "
                f"that keeps making it is worth knowing about.", (o.claimed_status,)))
        if o.epistemic_status is EpistemicStatus.SOURCED:
            out.append(AuditFinding(
                AuditCode.MEASURED_WITHOUT_EVIDENCE, Severity.VIOLATION, o.observation_id,
                "carries 'sourced', which is knowledge from outside the image. Nothing outside "
                "the image reached the prompt-blind pass, so either the status is wrong or the "
                "blinding was."))
    return out


def _check_description(observations: Sequence[VisualObservation]) -> List[AuditFinding]:
    out: List[AuditFinding] = []
    for o in observations:
        for field_name, text in o.described_fields:
            policy = _FIELD_POLICY.get(field_name)
            if not policy or not text:
                continue
            families = _families(text)
            for family, severity in policy.items():
                hits = families[family]
                if not hits:
                    continue
                out.append(AuditFinding(
                    code=_CODE_FOR_FAMILY[family], severity=severity,
                    subject_id=o.observation_id, field_name=field_name,
                    detail=(f"{field_name} carries {family.value} language "
                            f"({', '.join(repr(h) for h in hits)}). That belongs in "
                            f"interpretive_possibility; this field is read downstream as what the "
                            f"picture shows."),
                    evidence=hits + (text,)))
    return out


# ── the audit ────────────────────────────────────────────────────────────────

ObservationsIn = Union[BlindObservationSet, Sequence[VisualObservation]]
AlignmentsIn = Union[AlignmentSet, Sequence[HypothesisAlignment], None]


def audit(observations: ObservationsIn, *, alignments: AlignmentsIn = None,
          inquiry: Optional[InquiryMap] = None,
          declared_images: Optional[Sequence[Union[ImageRef, str]]] = None) -> AuditReport:
    """Everything checkable from what was handed in, and a list of what was not checkable.

    Takes a `BlindObservationSet` or a bare sequence. The set is the normal case and brings its
    own image list with it; the bare sequence is for auditing records that came back from
    somewhere else, where the declared images have to be supplied or the hallucinated-ref check
    honestly cannot run.
    """
    if isinstance(observations, BlindObservationSet):
        items: Tuple[VisualObservation, ...] = observations.observations
        if declared_images is None:
            declared_images = observations.images
    else:
        items = tuple(observations)

    if isinstance(alignments, AlignmentSet):
        alignment_items: Tuple[HypothesisAlignment, ...] = alignments.alignments
    elif alignments is None:
        alignment_items = ()
    else:
        alignment_items = tuple(alignments)

    declared: Optional[FrozenSet[str]] = None
    if declared_images is not None:
        declared = frozenset(i.image_id if isinstance(i, ImageRef) else str(i)
                             for i in declared_images)

    findings: List[AuditFinding] = []
    run: List[AuditCheck] = []
    skipped: List[Tuple[AuditCheck, str]] = []

    findings.extend(_check_refs(items, declared))
    run.append(AuditCheck.IMAGE_REFS)
    if declared is None:
        skipped.append((AuditCheck.IMAGE_REFS,
                        "no declared image set, so a reference to an image that was never "
                        "observed cannot be distinguished from a valid one"))

    findings.extend(_check_sources(items))
    run.append(AuditCheck.SOURCE_REFS)

    findings.extend(_check_duplication(items))
    run.append(AuditCheck.DUPLICATION)

    if alignment_items:
        findings.extend(_check_ids(items, alignment_items, inquiry))
        run.append(AuditCheck.ID_INTEGRITY)
        if inquiry is None:
            skipped.append((AuditCheck.ID_INTEGRITY,
                            "no InquiryMap, so an alignment answering a hypothesis nobody made "
                            "cannot be detected"))
    else:
        skipped.append((AuditCheck.ID_INTEGRITY, "no alignments were given"))

    if inquiry is not None:
        findings.extend(_check_leakage(items, inquiry))
        run.append(AuditCheck.PROMPT_LEAKAGE)
    else:
        skipped.append((AuditCheck.PROMPT_LEAKAGE,
                        "no InquiryMap, so the person's vocabulary is unknown and leakage into "
                        "the prompt-blind readings cannot be checked at all"))

    findings.extend(_check_measurement(items))
    run.append(AuditCheck.MEASUREMENT_EVIDENCE)

    findings.extend(_check_description(items))
    run.append(AuditCheck.DESCRIPTION_PURITY)

    findings.sort(key=lambda f: (f.severity is not Severity.VIOLATION, f.code.value,
                                 f.subject_id, f.field_name))
    return AuditReport(findings=tuple(findings), checks_run=tuple(run),
                       checks_skipped=tuple(skipped), observation_count=len(items),
                       alignment_count=len(alignment_items))
