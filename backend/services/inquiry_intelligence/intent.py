"""
INTELLIGENCE-002A — the inquiry reader: a prompt turned into a map, with nothing added to it.

    prompt  →  InquiryMap

The map is a READING OF THE PROMPT. It is not a reading of any picture, and the single law this
module exists to enforce is that it can never become one:

    THE MAP HAS NO PLACE TO PUT AN OBSERVATION.

Not "must not" — cannot. No contract below has a field that could hold a `VisualObservation`, and
every dataclass is frozen, so nothing may be bolted on afterwards either. When a person writes
"the drapery is doing the work here", that sentence enters the map as a UserHypothesis carrying
their words and the offsets they occupy. It does not enter as a fact about drapery. The observer
in `observer.py` is never handed this object at all — see the blinding guards there — and the
alignment pass that IS handed it may only relate the two, never merge them.

## Every element is a span, and the text comes from the prompt

`SourceSpan` carries `(start, end, text)` and `InquiryMap.__post_init__` refuses any span where
`prompt[start:end] != text`. That check is not paranoia about this file's own regexes; it is what
makes the MODEL seam safe (below). Rule 10 of the spine says source posts are preserved
byte-identically. A prompt is the person's own text and gets the same treatment: the map quotes,
it never paraphrases, and the constructor can prove it.

## Why the deterministic reading is the base, and the model only proposes SPANS

A model asked to "extract the hypotheses" hands back sentences it wrote. They read like the
person's sentences. They are not, and by the time one of them is quoted back in an answer nobody
can tell which words were whose.

So `InquiryReaderModel` may return only `SpanProposal(start, end, kind)` — offsets and a kind.
There is no `text` field on a proposal, and the reader slices the prompt itself. Paraphrase is
therefore not something the merge step has to detect; it is unrepresentable. A proposal whose
offsets are out of range, reversed, or empty is DROPPED and named in `dropped_proposals`, because
a reader that silently discarded a fifth of what the model said would look exactly like a reader
the model agreed with.

Proposals are ADDITIVE. They may add elements and add ambiguities; they may not delete an element
the deterministic pass found. Subtraction is how a prompt-reader quietly loses the awkward half of
a question, and there is no legitimate case for it here.

## Where this reading is weak, and why it says so out loud

Sentence splitting is offset arithmetic over `.!?` and newlines. "e.g." splits wrongly. The
observable/interpretive classifier keys on question stems and epistemic verbs — never on subject
matter — so an open-vocabulary predicate it has no marker for falls through. Both weaknesses land
in the same place: `AmbiguityKind.EPISTEMIC_KIND_UNCLEAR`, recorded as ambiguity rather than
resolved by guessing. The asymmetry in `_classify_question` is deliberate: an unclassifiable
question is filed INTERPRETIVE, because filing it observable would tell everything downstream that
looking at the picture can settle it.

## No topic in here

Spine rule 5. The marker tables below are question stems, epistemic and evaluative verbs, hedges,
quantifiers, pronouns and function words. There is no noun from any rehearsal domain in this file,
and `_vocabulary` extracts the person's content words BY EXCLUSION of a closed function-word set —
so the vocabulary is open, and stays whatever they actually said.

PURE MODULE. No database, no network, no image. The model seam is optional and injected.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import (Any, Dict, FrozenSet, List, Mapping, Optional, Protocol, Sequence, Tuple,
                    runtime_checkable)

READER_VERSION = "inquiry-reader.v1"


# ── the vocabulary of the map itself ─────────────────────────────────────────

class ElementKind(str, Enum):
    """What a span of the prompt was read AS. Also the kind a model proposal may claim."""
    HYPOTHESIS = "hypothesis"
    OBSERVABLE_QUESTION = "observable_question"
    INTERPRETIVE_QUESTION = "interpretive_question"
    COMPARISON = "comparison"
    INSTRUCTION = "instruction"
    AMBIGUITY = "ambiguity"


class Stance(str, Enum):
    """How firmly the person held the claim they made. Carried, never corrected.

    A hedged claim and an asserted one are different things to put to a picture, and flattening
    "I think the base is later" into "the base is later" is the first step of the laundering this
    whole section is built to prevent.
    """
    ASSERTED = "asserted"    # stated flat
    HEDGED = "hedged"        # "I think", "probably", "it seems"
    REPORTED = "reported"    # "I was told", "apparently", "according to"


class AmbiguityKind(str, Enum):
    UNRESOLVED_REFERENCE = "unresolved_reference"        # a pronoun with nothing behind it
    INCOMPLETE_COMPARISON = "incomplete_comparison"      # one side of a two-sided ask
    UNSCOPED_QUANTIFIER = "unscoped_quantifier"          # "some", "most", "usually"
    EPISTEMIC_KIND_UNCLEAR = "epistemic_kind_unclear"    # reads both ways, or neither
    UNBOUND_IMAGE_REFERENCE = "unbound_image_reference"  # "the second one" — the reader has no images


@dataclass(frozen=True)
class SourceSpan:
    """A half-open offset pair into the prompt, and the exact characters it covers."""
    start: int
    end: int
    text: str

    def contains(self, offset: int) -> bool:
        return self.start <= offset < self.end


@dataclass(frozen=True)
class UserHypothesis:
    """A claim the person made. Their words, their offsets, their degree of commitment."""
    hypothesis_id: str
    claim: str
    span: SourceSpan
    stance: Stance
    markers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class UserTerm:
    """One content word or quoted phrase the person used, and where in the map it came from.

    `origins` is load-bearing for the audit downstream. A term the person used inside a HYPOTHESIS
    is theory-laden language; the same word inside an OBSERVABLE_QUESTION is a thing they expect
    to be nameable in the picture. Finding the first in a prompt-blind observation is a leak.
    Finding the second is a coincidence worth a second look. Nothing about the WORD tells them
    apart — only where it was said — which is why this field exists rather than a list of
    suspicious adjectives.
    """
    term: str
    surface: str
    spans: Tuple[SourceSpan, ...]
    origins: FrozenSet[ElementKind]


@dataclass(frozen=True)
class RequestedComparison:
    """A comparison the person asked for. `sides` is verbatim; `complete` says whether both arrived."""
    comparison_id: str
    span: SourceSpan
    sides: Tuple[str, ...]
    complete: bool


@dataclass(frozen=True)
class InquiryQuestion:
    """A question, and the markers that decided which kind it is — so the call can be argued with."""
    question_id: str
    question: str
    span: SourceSpan
    kind: ElementKind
    markers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Ambiguity:
    ambiguity_id: str
    kind: AmbiguityKind
    note: str
    span: SourceSpan


@dataclass(frozen=True)
class InquiryMap:
    """Everything the prompt said, filed by kind, and nothing the prompt did not say.

    THERE IS NO OBSERVATION FIELD, and there is no `extra`/`metadata` dict that could grow into
    one. Adding a picture-fact to this contract is a visible edit to this class, reviewed as such.
    """
    prompt: str
    sentences: Tuple[SourceSpan, ...]
    hypotheses: Tuple[UserHypothesis, ...]
    vocabulary: Tuple[UserTerm, ...]
    comparisons: Tuple[RequestedComparison, ...]
    observable_questions: Tuple[InquiryQuestion, ...]
    interpretive_questions: Tuple[InquiryQuestion, ...]
    instructions: Tuple[SourceSpan, ...]
    ambiguities: Tuple[Ambiguity, ...]
    reader: str = READER_VERSION
    model_reader: Optional[str] = None
    dropped_proposals: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for span in self._all_spans():
            if not (0 <= span.start < span.end <= len(self.prompt)):
                raise InquiryReadError(
                    f"span [{span.start}:{span.end}] is not inside a prompt of "
                    f"{len(self.prompt)} characters")
            actual = self.prompt[span.start:span.end]
            if actual != span.text:
                raise InquiryReadError(
                    f"span [{span.start}:{span.end}] claims {span.text!r} but the prompt says "
                    f"{actual!r}. The map quotes the person; it does not restate them.")

    def _all_spans(self) -> Tuple[SourceSpan, ...]:
        out: List[SourceSpan] = list(self.sentences) + list(self.instructions)
        out.extend(h.span for h in self.hypotheses)
        out.extend(c.span for c in self.comparisons)
        out.extend(q.span for q in self.observable_questions)
        out.extend(q.span for q in self.interpretive_questions)
        out.extend(a.span for a in self.ambiguities)
        for term in self.vocabulary:
            out.extend(term.spans)
        return tuple(out)

    @property
    def questions(self) -> Tuple[InquiryQuestion, ...]:
        return self.observable_questions + self.interpretive_questions

    def hypothesis(self, hypothesis_id: str) -> Optional[UserHypothesis]:
        for h in self.hypotheses:
            if h.hypothesis_id == hypothesis_id:
                return h
        return None

    @property
    def hypothesis_ids(self) -> FrozenSet[str]:
        return frozenset(h.hypothesis_id for h in self.hypotheses)

    def terms_from(self, *kinds: ElementKind) -> Tuple[UserTerm, ...]:
        """The person's words that came from these kinds of element. Used by the audit."""
        wanted = frozenset(kinds)
        return tuple(t for t in self.vocabulary if t.origins & wanted)


class InquiryReadError(ValueError):
    """The map does not agree with the prompt it claims to be a map of."""


# ── the optional model seam ──────────────────────────────────────────────────

@dataclass(frozen=True)
class SpanProposal:
    """Offsets and a kind. THERE IS NO `text` FIELD, and that absence is the whole guard.

    A model may say "characters 42 to 96 are a hypothesis". It may not say what those characters
    are, because the reader is going to look. Paraphrase is not caught here; it is unsayable.
    """
    start: int
    end: int
    kind: ElementKind
    note: str = ""


@runtime_checkable
class InquiryReaderModel(Protocol):
    """A model that reads a prompt and points at parts of it.

    Injected, never constructed here. `identity` is a string this module records verbatim into
    `InquiryMap.model_reader`, so a map always says whose reading it is — or says None, which is
    the honest answer for the deterministic pass and is a different claim from "unknown".
    """

    @property
    def identity(self) -> str: ...

    def propose(self, prompt: str) -> Sequence[SpanProposal]: ...


# ── marker tables: stems, epistemics, hedges. No subject matter. ─────────────

#: Question stems. Form, not topic.
_QUESTION_STEM = re.compile(
    r"^(?:can|could|will|would|shall|should|do|does|did|is|are|was|were|has|have|had|am|may|"
    r"might|who|whom|whose|what|when|where|which|why|how)\b", re.I)

#: Task verbs a person opens an instruction with. Generic across every domain.
INSTRUCTION_VERBS: FrozenSet[str] = frozenset("""
look compare contrast describe explain tell show check consider examine analyse analyze
focus ignore list identify find note give assess evaluate review read study inspect
say state discuss point walk take use pay attend
""".split())

#: A wh- or whether-clause turns an instruction into a question in everything but punctuation.
_EMBEDDED_QUESTION = re.compile(
    r"\b(?:whether|why|how many|how much|how|what|where|which|when|who)\b", re.I)

#: Answerable by pointing: existence, count, place, arrangement. Stems and spatial/quantitative
#: relations, all domain-neutral.
OBSERVABLE_MARKERS: Tuple[str, ...] = (
    "is there", "are there", "how many", "how much", "how often", "where",
    "which", "do you see", "can you see", "does the image show", "do the images show",
    "is visible", "are visible", "visible", "present in", "appear in", "located",
    "position", "positioned", "arrangement", "arranged", "count", "number of",
    "on the left", "on the right", "in the foreground", "in the background",
)

#: A reading ABOUT the picture: purpose, effect, cause, value, provenance. Epistemic and
#: evaluative verbs — still no subject matter.
INTERPRETIVE_MARKERS: Tuple[str, ...] = (
    "why", "meaning", "means", "mean", "intend", "intended", "intent", "intention",
    "purpose", "suggest", "suggests", "imply", "implies", "express", "expresses",
    "convey", "conveys", "evoke", "evokes", "symbol", "symbolise", "symbolize",
    "represent", "represents", "feel", "feeling", "mood", "atmosphere", "read as",
    "successful", "succeed", "succeeds", "work well", "effective", "significance",
    "significant", "influence", "influenced", "inspired", "tradition", "history",
    "historical", "historically", "because", "should", "ought", "better", "worse",
    "matter", "matters", "point of",
)

HEDGE_MARKERS: Tuple[str, ...] = (
    "i think", "i believe", "i suspect", "i feel", "i wonder", "it seems", "seems to me",
    "my sense", "my guess", "probably", "perhaps", "maybe", "might", "may be", "possibly",
    "arguably", "presumably", "i'd say", "i would say", "not sure",
)

REPORTED_MARKERS: Tuple[str, ...] = (
    "i was told", "i read", "i've heard", "i have heard", "apparently", "according to",
    "they say", "it is said", "someone said", "the label says", "the caption says",
)

COMPARISON_MARKERS: Tuple[str, ...] = (
    "compare", "compared", "comparing", "comparison", "contrast", "versus", " vs ", " vs.",
    "difference between", "differences between", "same as", "similar to", "unlike",
    "more than", "less than", "than", "both", "either", "against",
)

QUANTIFIERS: Tuple[str, ...] = (
    "some", "many", "most", "several", "a few", "few", "often", "usually", "generally",
    "typically", "much", "various", "certain", "mostly", "sometimes", "rarely", "always",
    "never", "all of", "any of",
)

PRONOUNS: FrozenSet[str] = frozenset("""
it its this that they them their these those one ones he she him her his hers itself
themselves
""".split())

#: The four that double as determiners. "those folds" points at something in the sentence;
#: "those" alone points at whatever the person had in mind, which is the case worth flagging.
DEMONSTRATIVES: FrozenSet[str] = frozenset({"this", "that", "these", "those"})

#: Deictic image talk. The reader has no image set, so it cannot resolve these and says so.
_DEICTIC_IMAGE = re.compile(
    r"\b(?:the\s+)?(?:first|second|third|fourth|fifth|last|next|previous|left|right|middle|"
    r"centre|center|other|top|bottom|upper|lower)\s+(?:one|image|images|photo|photos|picture|"
    r"pictures|shot|shots|frame|frames)\b|\b(?:image|photo|picture|frame)\s*#?\s*\d+\b", re.I)

#: Function words. Everything NOT here (and not an instruction verb) is the person's own
#: vocabulary — which is how the vocabulary stays open.
STOPWORDS: FrozenSet[str] = frozenset("""
a an the and or but if then than that this these those there here of in on at to from by with
without within into onto over under above below between among across through during before after
is are was were be been being am do does did doing done has have had having will would shall
should can could may might must not no nor so as such very too also only just even still yet
about against for it its it's i me my mine we us our ours you your yours he him his she her hers
they them their theirs who whom whose what which when where why how all any both each few more
most other some such own same s t don now d ll m o re ve y ain aren couldn didn doesn hadn hasn
haven isn ma mightn mustn needn shan shouldn wasn weren won wouldn like get got make made seem
seems seemed thing things something anything nothing lot lots bit
""".split())

_WORD = re.compile(r"[A-Za-z][A-Za-z'’‑-]*")
_QUOTED = re.compile(r"[\"“]([^\"“”]{2,80})[\"”]")


# ── sentence segmentation, with offsets kept ─────────────────────────────────

def _sentence_spans(prompt: str) -> Tuple[SourceSpan, ...]:
    """Split on terminal punctuation and newlines, carrying offsets the whole way.

    Offset arithmetic rather than a sentence tokeniser, because the offsets are the product. A
    tokeniser that returned strings would put this module in the business of matching them back
    to the prompt, which is exactly the fuzziness `__post_init__` refuses to accept.
    """
    raw: List[Tuple[int, int]] = []
    start, i, n = 0, 0, len(prompt)
    while i < n:
        ch = prompt[i]
        if ch in ".!?":
            j = i
            while j + 1 < n and prompt[j + 1] in ".!?":
                j += 1
            if j + 1 >= n or prompt[j + 1].isspace():
                raw.append((start, j + 1))
                start = j + 1
            i = j + 1
            continue
        if ch == "\n":
            raw.append((start, i))
            start = i + 1
        i += 1
    if start < n:
        raw.append((start, n))

    out: List[SourceSpan] = []
    for s, e in raw:
        while s < e and prompt[s].isspace():
            s += 1
        while e > s and prompt[e - 1].isspace():
            e -= 1
        if e > s:
            out.append(SourceSpan(s, e, prompt[s:e]))
    return tuple(out)


def _found(text_lower: str, markers: Sequence[str]) -> Tuple[str, ...]:
    """Which markers occur, in table order. Word-bounded for single words, plain for phrases."""
    hits: List[str] = []
    for m in markers:
        if " " in m or "'" in m:
            if m in text_lower:
                hits.append(m.strip())
        elif re.search(r"\b" + re.escape(m) + r"\b", text_lower):
            hits.append(m)
    return tuple(hits)


_HOW_COUNT = re.compile(r"\bhow\s+(?:many|much)\b", re.I)


def _quantifier_hits(text_lower: str) -> Tuple[str, ...]:
    """Quantifiers that are actually vague.

    `how many` and `how much` ASK for a count; they are the opposite of an unscoped quantifier,
    and flagging the `many` inside one was the reader telling a person their clearest question was
    the imprecise part of their prompt.
    """
    masked = _HOW_COUNT.sub(lambda m: " " * len(m.group(0)), text_lower)
    return _found(masked, QUANTIFIERS)


def _is_question(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    body = re.sub(r"^(?:please|so|and|but|also|now)\s+", "", stripped, flags=re.I)
    if _QUESTION_STEM.match(body):
        return True
    if _is_instruction(text) and _EMBEDDED_QUESTION.search(stripped):
        return True
    return False


def _is_instruction(text: str) -> bool:
    body = re.sub(r"^(?:please|so|and|but|also|now|then|first|second|next|finally)\s+", "",
                  text.strip(), flags=re.I)
    head = _WORD.match(body)
    return bool(head) and head.group(0).lower() in INSTRUCTION_VERBS


def _classify_question(text_lower: str) -> Tuple[ElementKind, Tuple[str, ...], bool]:
    """(kind, markers, unclear).

    THE ASYMMETRY IS THE POINT. A question carrying both families, or neither, is filed
    INTERPRETIVE and flagged unclear. Filing it observable would be a claim that looking at the
    picture settles it, made by a module that has never seen a picture.
    """
    obs = _found(text_lower, OBSERVABLE_MARKERS)
    interp = _found(text_lower, INTERPRETIVE_MARKERS)
    if obs and not interp:
        return ElementKind.OBSERVABLE_QUESTION, obs, False
    if interp and not obs:
        return ElementKind.INTERPRETIVE_QUESTION, interp, False
    return ElementKind.INTERPRETIVE_QUESTION, obs + interp, True


def _stance(text_lower: str) -> Tuple[Stance, Tuple[str, ...]]:
    reported = _found(text_lower, REPORTED_MARKERS)
    if reported:
        return Stance.REPORTED, reported
    hedges = _found(text_lower, HEDGE_MARKERS)
    if hedges:
        return Stance.HEDGED, hedges
    return Stance.ASSERTED, ()


_BETWEEN = re.compile(r"\bbetween\s+(.+?)\s+and\s+(.+?)\s*(?:[,.;?!]|$)", re.I | re.S)
_VERSUS = re.compile(r"(.+?)\s+(?:versus|vs\.?)\s+(.+?)\s*(?:[,.;?!]|$)", re.I | re.S)
_COMPARE_TO = re.compile(r"\bcompar\w*\s+(.+?)\s+(?:and|with|to|against)\s+(.+?)\s*(?:[,.;?!]|$)",
                         re.I | re.S)
_THAN_PAIR = re.compile(r"\b(more|less|fewer|\w+er)\s+than\s+(.+?)\s*(?:[,.;?!]|$)", re.I | re.S)
_THAN = re.compile(r"\bthan\b(.*)$", re.I | re.S)


def _comparison_sides(text: str) -> Tuple[Tuple[str, ...], bool]:
    """(sides, complete). Verbatim substrings — the map quotes, so the sides are quoted too."""
    for pattern in (_BETWEEN, _COMPARE_TO, _VERSUS, _THAN_PAIR):
        m = pattern.search(text)
        if m:
            left, right = m.group(1).strip(), m.group(2).strip()
            if left and right:
                return (left, right), True
    m = _THAN.search(text)
    if m and not m.group(1).strip(" \t\n.,;:?!"):
        return (), False
    return (), False


def _vocabulary(prompt: str, owners: Sequence[Tuple[SourceSpan, ElementKind]]) -> Tuple[UserTerm, ...]:
    """The person's content words, by exclusion. Open vocabulary — nothing is looked up.

    Quoted phrases are taken whole: a person who writes "the load-bearing bit" in quotes has named
    something, and chopping it into two stopword-filtered tokens would lose the naming.
    """
    occurrences: Dict[str, List[Tuple[SourceSpan, str]]] = {}

    def record(start: int, end: int) -> None:
        surface = prompt[start:end]
        key = surface.lower().strip("-'’")
        if not key:
            return
        occurrences.setdefault(key, []).append((SourceSpan(start, end, surface), surface))

    claimed: List[Tuple[int, int]] = []
    for m in _QUOTED.finditer(prompt):
        record(m.start(1), m.end(1))
        claimed.append((m.start(1), m.end(1)))

    for m in _WORD.finditer(prompt):
        if any(s <= m.start() and m.end() <= e for s, e in claimed):
            continue
        word = m.group(0).lower()
        if len(word) < 3 or word in STOPWORDS or word in INSTRUCTION_VERBS or word in PRONOUNS:
            continue
        record(m.start(), m.end())

    out: List[UserTerm] = []
    for key, seen in occurrences.items():
        spans = tuple(span for span, _ in seen)
        origins = set()
        for span in spans:
            for owner_span, kind in owners:
                if owner_span.start <= span.start and span.end <= owner_span.end:
                    origins.add(kind)
        out.append(UserTerm(term=key, surface=seen[0][1], spans=spans, origins=frozenset(origins)))
    out.sort(key=lambda t: t.spans[0].start)
    return tuple(out)


def _ambiguities(prompt: str, owners: Sequence[Tuple[SourceSpan, ElementKind]],
                 vocabulary: Sequence[UserTerm],
                 unclear: Sequence[Tuple[SourceSpan, Tuple[str, ...]]],
                 incomplete: Sequence[SourceSpan]) -> Tuple[Ambiguity, ...]:
    found: List[Tuple[AmbiguityKind, str, SourceSpan]] = []

    first_content = min((t.spans[0].start for t in vocabulary), default=len(prompt) + 1)
    for m in _WORD.finditer(prompt):
        word = m.group(0).lower()
        if word not in PRONOUNS:
            continue
        if word in DEMONSTRATIVES and _WORD.match(prompt, m.end() + 1):
            continue  # "these two images" — a determiner, and its head noun is right there
        if m.start() > first_content:
            continue
        found.append((AmbiguityKind.UNRESOLVED_REFERENCE,
                      f"{m.group(0)!r} appears before anything it could refer to",
                      SourceSpan(m.start(), m.end(), m.group(0))))

    for m in _DEICTIC_IMAGE.finditer(prompt):
        found.append((AmbiguityKind.UNBOUND_IMAGE_REFERENCE,
                      f"{m.group(0)!r} points at an image the reader has not been given",
                      SourceSpan(m.start(), m.end(), m.group(0))))

    for span, kind in owners:
        if kind not in (ElementKind.HYPOTHESIS, ElementKind.OBSERVABLE_QUESTION,
                        ElementKind.INTERPRETIVE_QUESTION):
            continue
        for q in _quantifier_hits(span.text.lower()):
            found.append((AmbiguityKind.UNSCOPED_QUANTIFIER,
                          f"{q!r} is not scoped to anything countable", span))

    for span, markers in unclear:
        note = ("carries markers of both kinds: " + ", ".join(markers)) if markers else \
            "carries no marker of either kind"
        found.append((AmbiguityKind.EPISTEMIC_KIND_UNCLEAR,
                      f"filed interpretive; {note}", span))

    for span in incomplete:
        found.append((AmbiguityKind.INCOMPLETE_COMPARISON,
                      "a comparison with only one side given", span))

    found.sort(key=lambda f: (f[2].start, f[0].value))
    return tuple(Ambiguity(f"amb_{i}", kind, note, span)
                 for i, (kind, note, span) in enumerate(found, start=1))


# ── the reader ───────────────────────────────────────────────────────────────

def read_inquiry(prompt: str, reader: Optional[InquiryReaderModel] = None) -> InquiryMap:
    """The prompt, read into a map. Deterministic; a model may only add spans to it.

    `prompt` is carried verbatim onto the map. Not stripped, not normalised: every offset in
    every element is an offset into THIS string, and a reader that quietly trimmed it would
    invalidate all of them by one character.
    """
    if not isinstance(prompt, str):
        raise InquiryReadError(f"a prompt is text; got {type(prompt).__name__}")

    sentences = _sentence_spans(prompt)
    owners: List[Tuple[SourceSpan, ElementKind]] = []
    hypotheses: List[UserHypothesis] = []
    observable: List[InquiryQuestion] = []
    interpretive: List[InquiryQuestion] = []
    comparisons: List[RequestedComparison] = []
    instructions: List[SourceSpan] = []
    unclear: List[Tuple[SourceSpan, Tuple[str, ...]]] = []
    incomplete: List[SourceSpan] = []

    for span in sentences:
        lower = span.text.lower()
        is_question = _is_question(span.text)
        is_instruction = _is_instruction(span.text)
        comparison_markers = _found(lower, COMPARISON_MARKERS)

        if comparison_markers:
            sides, complete = _comparison_sides(span.text)
            comparisons.append(RequestedComparison(
                comparison_id=f"cmp_{len(comparisons) + 1}", span=span, sides=sides,
                complete=complete))
            owners.append((span, ElementKind.COMPARISON))
            if not complete:
                incomplete.append(span)

        if is_question:
            kind, markers, was_unclear = _classify_question(lower)
            if kind is ElementKind.OBSERVABLE_QUESTION:
                observable.append(InquiryQuestion(
                    f"obs_q_{len(observable) + 1}", span.text, span, kind, markers))
            else:
                interpretive.append(InquiryQuestion(
                    f"int_q_{len(interpretive) + 1}", span.text, span, kind, markers))
            owners.append((span, kind))
            if was_unclear:
                unclear.append((span, markers))
            continue

        if is_instruction:
            instructions.append(span)
            owners.append((span, ElementKind.INSTRUCTION))
            continue

        stance, markers = _stance(lower)
        hypotheses.append(UserHypothesis(
            hypothesis_id=f"hyp_{len(hypotheses) + 1}", claim=span.text, span=span,
            stance=stance, markers=markers))
        owners.append((span, ElementKind.HYPOTHESIS))

    dropped: List[str] = []
    model_identity: Optional[str] = None
    if reader is not None:
        model_identity = str(reader.identity)
        proposed, dropped_now = _merge_proposals(prompt, reader, owners, hypotheses, observable,
                                                 interpretive, comparisons, instructions)
        dropped.extend(dropped_now)
        unclear.extend(proposed)

    vocabulary = _vocabulary(prompt, owners)
    ambiguities = _ambiguities(prompt, owners, vocabulary, unclear, incomplete)

    return InquiryMap(
        prompt=prompt, sentences=sentences, hypotheses=tuple(hypotheses),
        vocabulary=vocabulary, comparisons=tuple(comparisons),
        observable_questions=tuple(observable), interpretive_questions=tuple(interpretive),
        instructions=tuple(instructions), ambiguities=ambiguities,
        model_reader=model_identity, dropped_proposals=tuple(dropped))


def _merge_proposals(prompt: str, reader: InquiryReaderModel,
                     owners: List[Tuple[SourceSpan, ElementKind]],
                     hypotheses: List[UserHypothesis], observable: List[InquiryQuestion],
                     interpretive: List[InquiryQuestion],
                     comparisons: List[RequestedComparison],
                     instructions: List[SourceSpan],
                     ) -> Tuple[List[Tuple[SourceSpan, Tuple[str, ...]]], List[str]]:
    """Additive only. The prompt is sliced HERE; the model never supplies a character of text."""
    existing = {(span.start, span.end, kind) for span, kind in owners}
    unclear: List[Tuple[SourceSpan, Tuple[str, ...]]] = []
    dropped: List[str] = []

    try:
        proposals = list(reader.propose(prompt))
    except Exception as exc:                                    # noqa: BLE001 — reported, not raised
        return unclear, [f"the reader raised {type(exc).__name__}: {exc}"]

    for index, p in enumerate(proposals):
        if not isinstance(p, SpanProposal):
            dropped.append(f"proposal {index} is a {type(p).__name__}, not a SpanProposal")
            continue
        if not (0 <= p.start < p.end <= len(prompt)):
            dropped.append(f"proposal {index} spans [{p.start}:{p.end}], outside the prompt")
            continue
        span = SourceSpan(p.start, p.end, prompt[p.start:p.end])
        if not span.text.strip():
            dropped.append(f"proposal {index} spans only whitespace")
            continue
        key = (span.start, span.end, p.kind)
        if key in existing:
            continue
        existing.add(key)

        if p.kind is ElementKind.HYPOTHESIS:
            stance, markers = _stance(span.text.lower())
            hypotheses.append(UserHypothesis(f"hyp_{len(hypotheses) + 1}", span.text, span,
                                             stance, markers))
        elif p.kind is ElementKind.OBSERVABLE_QUESTION:
            observable.append(InquiryQuestion(f"obs_q_{len(observable) + 1}", span.text, span,
                                              p.kind, _found(span.text.lower(),
                                                             OBSERVABLE_MARKERS)))
        elif p.kind is ElementKind.INTERPRETIVE_QUESTION:
            interpretive.append(InquiryQuestion(f"int_q_{len(interpretive) + 1}", span.text, span,
                                               p.kind, _found(span.text.lower(),
                                                              INTERPRETIVE_MARKERS)))
        elif p.kind is ElementKind.COMPARISON:
            sides, complete = _comparison_sides(span.text)
            comparisons.append(RequestedComparison(f"cmp_{len(comparisons) + 1}", span, sides,
                                                   complete))
        elif p.kind is ElementKind.INSTRUCTION:
            instructions.append(span)
        elif p.kind is ElementKind.AMBIGUITY:
            unclear.append((span, (p.note,) if p.note else ()))
        else:
            dropped.append(f"proposal {index} claims kind {p.kind!r}, which is not a kind")
            continue
        owners.append((span, p.kind))

    return unclear, dropped
