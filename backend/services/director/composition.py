"""
CIRCUIT-003 M3 — argument composition: evidence-bound prose from a CONFIRMED ArgumentPlan.

M2 produces an ArgumentPlan: claims bound to percepts, each percept carrying an argumentative
function, with refusals and epistemic downgrades recorded. It is a structure, not an article. M3
composes it into the PROSE of the perceptual article — a thesis, per-claim sections that realize
their function, a real counter-reading, and honest qualification of what the corpus could not
carry.

The rule the whole module exists to enforce, one level above where M2 enforces it: EVERY SENTENCE
RESTS ON A BOUND PERCEPT. `compose_percept` already writes one sentence from the marks in front of
it. This writes an argument from the evidence in front of it, and the difference that matters is
that an argument has somewhere to hide — a paragraph can slip in a claim about an image it never
looked at, and the paragraph will still read beautifully.

    Citation      — one confirmed percept a sentence may rest on
    Section       — one claim, composed, with its citations and epistemic tag
    CounterReading— the challenge, composed from surviving challenge percepts, or honestly absent
    Qualification — a claim the corpus could NOT carry, stated as a limit and never as a finding
    ArticleDraft  — the whole thing, QUARANTINED: proposed, never committed

FIVE RULES, AND WHY EACH IS CODE RATHER THAN PROMPT.

  1. CONFIRM BEFORE COMPOSING. `resolve()` proves evidence CAN be produced; only a run proves it
     WAS. M3 takes a chain provenance and re-judges the argument through M2's
     `confirm_against_chain` before writing a word, then composes ONLY from claims whose binding
     is `confirmed`. Composing from a plan would put prose behind a producer that came back empty,
     and the prose would be indistinguishable from prose behind one that did not.

  2. CITATIONS ARE INTERSECTED, NOT TRUSTED. The model returns which percepts it grounded each
     sentence in. Those ids are intersected with the section's ACTUAL bound percepts; anything
     else is dropped and recorded. A section left citing nothing is REFUSED rather than published
     — prose resting on nothing is exactly what this layer exists to prevent, and asking the model
     nicely not to do it is not a control.

  3. FREE ASSOCIATION IS DETECTED, NOT DISCOURAGED. A section that names an image it does not cite
     is flagged. This is the failure that reads best and checks worst: "the colonnade prepares the
     rotunda" in a section whose only evidence is a field on the Lustgarten.

  4. RELEVANCE IS SURFACED, NOT ASSUMED. M2's binding proves a percept RESOLVES, not that it bears
     on the claim — a limit M2 flagged rather than hid. The composer is asked, per percept,
     whether it actually bears on the claim; a percept it says does not is forced into the
     section's caveats and the section is qualified. A mis-bound `pressure_zone` then READS as the
     mismatch it is, instead of being narrated into a fluent non-sequitur. This is partial and is
     documented as partial: full relevance checking remains a frontier.

  5. NOTHING IS INVENTED WHEN THE MODEL IS ABSENT. No language model, no prose — the section is
     reported unavailable. A template-composed sentence would be a claim nobody made, wearing the
     same shape as one somebody did.

QUARANTINE. `ArticleDraft.to_suggestion()` mirrors the visual quarantine's descriptor: a
`model_suggested` item with a producer, a source_ref and a provenance receipt. It is proposed,
never committed — nothing here writes a post, a manuscript, or a mark. (The manuscript quarantine
this would otherwise mirror does not exist on this branch; the visual one does, and it is the
convention followed.)

NON-SCOPE: the article ARTIFACT — the interleaved, live-percept, reopen-on-source document — is
M4. This produces the draft M4 renders. Epistemic UI chips are M5.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .argument import (ARGUMENT_NO_CHALLENGE, BINDING_CONFIRMED, CHALLENGE, COMPLICATE,
                       INTERPRETIVE, QUALIFIED, REFUSED, SOURCED, SUPPORT, SUPPORTED, UNCERTAIN,
                       ArgumentPlan, BoundClaim, PerceptStep, confirm_against_chain,
                       weakest_status)
from .capabilities import ACTUATORS, get as get_actuator
from .corpus import CorpusWorkingMemory
from .memory import WorkingMemory

COMPOSITION_VERSION = 1

# The quarantine descriptor vocabulary, mirroring the visual circuit's.
PRODUCER_COMPOSE_ARTICLE = "compose_article"
ARTICLE_DRAFT_TYPE = "article_draft"
STATUS_MODEL_SUGGESTED = "model_suggested"

# Why a section could not be composed. Closed set — M4 and M5 branch on these.
SECTION_NO_MODEL = "no_language_model"
SECTION_NO_PROSE = "model_returned_no_prose"
SECTION_CITES_NOTHING = "prose_cited_no_bound_percept"
SECTION_NOT_CONFIRMED = "claim_was_not_confirmed_by_a_run"

# Why a counter-reading is absent. M2 distinguishes these and so must the prose — a curator
# reading "no counter-reading" needs to know whether nobody proposed one or whether one was
# proposed and the evidence for it never arrived.
COUNTER_NONE_PROPOSED = "no_challenge_percept_was_proposed"
COUNTER_NOT_PRODUCED = "the_challenge_percept_could_not_be_produced"


# ── what a sentence may rest on ──────────────────────────────────────────────

@dataclass(frozen=True)
class Citation:
    """One confirmed percept. The unit of "resting on" — a section's citations ARE its evidence.

    `attribution` is populated only for `sourced` percepts, and is the reason a sourced claim can
    be composed at all: it must be attributed to whoever said it, never narrated as something the
    picture shows.
    """
    step_id: str
    actuator: str
    function: str
    epistemic: str
    image: Optional[str] = None
    image_title: str = ""
    shows: str = ""                       # what this actuator actually reports, from the catalogue
    attribution: Optional[str] = None     # for `sourced` only: who said it

    @property
    def is_sourced(self) -> bool:
        return self.epistemic == SOURCED

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "actuator": self.actuator, "function": self.function,
                "epistemic": self.epistemic, "image": self.image,
                "image_title": self.image_title, "shows": self.shows,
                "attribution": self.attribution}


def _citation_for(percept: PerceptStep, claim: BoundClaim,
                  memory: WorkingMemory) -> Citation:
    actuator = get_actuator(percept.actuator)
    title = ""
    if isinstance(memory, CorpusWorkingMemory) and memory.corpus is not None and percept.image:
        image = memory.corpus.by_post_id(percept.image)
        title = image.title if image is not None else ""
    attribution = None
    if percept.ceiling == SOURCED:
        # A sourced percept MUST name its source. Absent attribution is not a missing nicety —
        # it is a quotation with no quoter, and the section is qualified for it below.
        attribution = (percept.step.params or {}).get("source") or \
                      (percept.step.params or {}).get("citation") or None
    return Citation(step_id=percept.step.id, actuator=percept.actuator,
                    function=percept.function, epistemic=percept.ceiling,
                    image=percept.image, image_title=title,
                    shows=actuator.summary if actuator else "",
                    attribution=str(attribution) if attribution else None)


# ── the composed pieces ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Section:
    """One claim, composed. Prose plus exactly what it rests on."""
    claim_id: str
    claim: str
    function: str
    prose: str
    citations: Tuple[Citation, ...] = ()
    epistemic: str = UNCERTAIN
    qualified: bool = False
    caveats: Tuple[str, ...] = ()
    # Percepts the composer said do NOT bear on the claim. Rule 4 — surfaced, never smoothed over.
    relevance_flags: Tuple[Dict[str, str], ...] = ()
    # Citations the model claimed and did not have. Rule 2 — recorded, never silent.
    dropped_citations: Tuple[str, ...] = ()
    # Images named in the prose that the section does not cite. Rule 3.
    uncited_mentions: Tuple[str, ...] = ()

    @property
    def grounded(self) -> bool:
        return bool(self.prose.strip()) and bool(self.citations)

    def to_dict(self) -> Dict[str, Any]:
        return {"claim_id": self.claim_id, "claim": self.claim, "function": self.function,
                "prose": self.prose, "epistemic": self.epistemic, "qualified": self.qualified,
                "caveats": list(self.caveats),
                "citations": [c.to_dict() for c in self.citations],
                "relevance_flags": [dict(f) for f in self.relevance_flags],
                "dropped_citations": list(self.dropped_citations),
                "uncited_mentions": list(self.uncited_mentions)}


@dataclass(frozen=True)
class UncomposedSection:
    """A claim that was confirmed but could not be written. Kept, not dropped — a draft missing a
    section silently is a draft that has quietly narrowed the argument."""
    claim_id: str
    claim: str
    reason: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"claim_id": self.claim_id, "claim": self.claim, "reason": self.reason,
                "detail": self.detail}


@dataclass(frozen=True)
class CounterReading:
    """The counter-reading, composed from the surviving `challenge` percepts — or honestly absent.

    `grounded=False` is a first-class outcome carrying M2's distinction between a challenge that
    was never proposed and one that was proposed and could not be produced. It is NEVER filled in
    with a plausible objection: an invented counter-reading is the most convincing possible way to
    look rigorous while having tested nothing.
    """
    grounded: bool
    prose: str = ""
    citations: Tuple[Citation, ...] = ()
    absence_reason: str = ""
    absence_detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"grounded": self.grounded, "prose": self.prose,
                "citations": [c.to_dict() for c in self.citations],
                "absence_reason": self.absence_reason,
                "absence_detail": self.absence_detail}


@dataclass(frozen=True)
class Qualification:
    """A claim the corpus could not carry, stated as a LIMIT.

    Composed from M2's `gaps()`. The prose here says what could not be established and what would
    be needed — never what the claim would have shown had it worked, which is the shape a
    qualification takes when it is quietly doing the asserting anyway.
    """
    claim_id: str
    claim: str
    status: str
    prose: str
    why: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"claim_id": self.claim_id, "claim": self.claim, "status": self.status,
                "prose": self.prose, "why": self.why}


@dataclass(frozen=True)
class ArticleDraft:
    """The composed article, QUARANTINED. Proposed, never committed."""
    thesis: str
    thesis_prose: str = ""
    sections: Tuple[Section, ...] = ()
    uncomposed: Tuple[UncomposedSection, ...] = ()
    counter_reading: Optional[CounterReading] = None
    qualifications: Tuple[Qualification, ...] = ()
    epistemic: str = UNCERTAIN
    notes: Tuple[str, ...] = ()
    run_id: str = ""
    model: Optional[str] = None
    version: int = COMPOSITION_VERSION

    # ── quarantine ──
    #: Always false. A draft is a proposal; committing one is a curator's act, through review,
    #: and there is deliberately no method here that performs it.
    committed: bool = False

    @property
    def citations(self) -> Tuple[Citation, ...]:
        out: List[Citation] = []
        for section in self.sections:
            out.extend(section.citations)
        if self.counter_reading is not None:
            out.extend(self.counter_reading.citations)
        return tuple(out)

    @property
    def grounded(self) -> bool:
        """Is there any composed, evidence-bound prose at all?"""
        return any(s.grounded for s in self.sections)

    @property
    def complete(self) -> bool:
        """Every confirmed claim composed, a grounded counter-reading, nothing qualified away."""
        return (bool(self.sections) and not self.uncomposed and not self.qualifications
                and self.counter_reading is not None and self.counter_reading.grounded)

    def to_suggestion(self) -> Dict[str, Any]:
        """The quarantined descriptor, mirroring the visual circuit's `model_suggested` items.

        Same shape a produced mark travels in — producer, type, status, source_ref, provenance —
        so the existing supervised-review vocabulary applies to a draft without inventing a second
        one. It is a DESCRIPTOR: nothing about returning it writes anything.
        """
        return {
            "producer": PRODUCER_COMPOSE_ARTICLE,
            "type": ARTICLE_DRAFT_TYPE,
            "status": STATUS_MODEL_SUGGESTED,
            "source_ref": f"{self.run_id}:article",
            "label": (self.thesis_prose or self.thesis)[:120],
            "geometry": None,               # an article has no extent; it rests on things that do
            "linked_ground_ids": [],
            "draft": self.to_dict(),
            "cites": [c.step_id for c in self.citations],
            "provenance": {"run_id": self.run_id, "producer": PRODUCER_COMPOSE_ARTICLE,
                           "adapter": PRODUCER_COMPOSE_ARTICLE,
                           **({"model": self.model} if self.model else {})},
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "thesis": self.thesis,
            "thesis_prose": self.thesis_prose,
            "epistemic": self.epistemic,
            "grounded": self.grounded,
            "complete": self.complete,
            "committed": self.committed,
            "sections": [s.to_dict() for s in self.sections],
            "uncomposed": [u.to_dict() for u in self.uncomposed],
            "counter_reading": (self.counter_reading.to_dict()
                                if self.counter_reading is not None else None),
            "qualifications": [q.to_dict() for q in self.qualifications],
            "notes": list(self.notes),
            "run_id": self.run_id,
            "model": self.model,
        }


# ── the language model seam ──────────────────────────────────────────────────

class LLM:
    """The narrow surface M3 needs. Injectable, so composition is testable with no network.

    Deliberately not the whole `LLMService`: one method, JSON in, JSON out. A composer that could
    reach more of the client could reach the image, and this one has no business seeing it.
    """

    def __init__(self, client: Any = None, model: str = ""):
        self._client = client
        self.model = model

    @classmethod
    def from_service(cls) -> Optional["LLM"]:
        try:
            from backend.config import settings
            if not getattr(settings, "GROQ_API_KEY", None):
                return None
            import importlib
            svc = importlib.import_module("backend.services.llm_service").LLMService()
            return cls(client=svc.client, model=svc.model)
        except Exception:
            return None

    def complete(self, system: str, user: str) -> str:
        out = self._client.chat.completions.create(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            model=self.model, response_format={"type": "json_object"})
        return out.choices[0].message.content


SYSTEM_PROMPT = (
    "You write the prose of a perceptual close-reading article. You are given ONE claim and the "
    "EXACT pieces of visual evidence that were produced for it. You output JSON and nothing "
    "else.\n\n"
    "Hard rules:\n"
    "- Write ONLY about the evidence listed. Do not mention any image, part, material, or "
    "feature that is not in that list. You have not seen the pictures; the list is everything "
    "you know.\n"
    "- Do not assert anything the listed evidence does not report. If the evidence is thinner "
    "than the claim, write the thinner sentence.\n"
    "- Carry the KIND of knowing into the words. Evidence marked 'measured' is something an "
    "instrument reported — write it as measured. 'interpretive' is a reading — write it as a "
    "reading, not a fact. 'sourced' came from outside the picture and MUST be attributed to its "
    "source, never written as something the image shows. 'uncertain' must be qualified.\n"
    "- If a piece of evidence does not actually bear on the claim, say so in 'relevance' and do "
    "NOT use it to assert the claim. A field that measures something unrelated is not support.\n"
    "- Realize the stated FUNCTION exactly. 'support': assert the claim on its evidence. "
    "'complicate': make the PRIOR claim harder to state simply, without abandoning it. "
    "'challenge': read the evidence AGAINST the main argument.\n"
    "- Two to four sentences. No headings, no lists, no flourish."
)


def _evidence_rows(citations: Sequence[Citation]) -> List[Dict[str, Any]]:
    return [{"id": c.step_id, "evidence": c.shows or c.actuator,
             "produced_by": c.actuator,
             "on_image": c.image_title or c.image,
             "kind_of_knowing": c.epistemic,
             **({"attributed_to": c.attribution} if c.is_sourced else {})}
            for c in citations]


def build_section_prompt(claim: BoundClaim, citations: Sequence[Citation], *,
                         function: str, prior_claim: str = "",
                         thesis: str = "") -> str:
    rows = _evidence_rows(citations)
    caveats = list(claim.caveats)
    if claim.downgraded:
        caveats.append(f"this claim aimed to be '{claim.claim.target_status}' but the evidence "
                       f"produced for it is only '{claim.achieved_status}'")
    return (
        f"THE ARTICLE'S THESIS (context only — do not argue it here):\n{thesis}\n\n"
        f"THE CLAIM THIS SECTION MAKES:\n{claim.claim.text}\n\n"
        f"THIS SECTION'S FUNCTION: {function}\n"
        + (f"THE PRIOR CLAIM YOU ARE COMPLICATING:\n{prior_claim}\n\n"
           if function == COMPLICATE and prior_claim else "\n")
        + f"THE EVIDENCE ACTUALLY PRODUCED — this is everything you know:\n"
        f"{json.dumps(rows, indent=2)}\n\n"
        f"QUALIFICATIONS you must carry into the prose:\n{json.dumps(caveats, indent=2)}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"prose": "<2-4 sentences>", '
        f'"grounded_in": ["<id of each evidence item the prose rests on>"], '
        f'"relevance": [{{"id": "<evidence id>", "bears_on_claim": true, '
        f'"why": "<one clause>"}}], '
        f'"qualified": <true if the prose had to hedge>}}'
    )


# ── composing one section, with the guards ───────────────────────────────────

def _parse_section_payload(raw: Any) -> Tuple[str, List[str], List[Dict[str, Any]], bool, List[str]]:
    """Model JSON → (prose, grounded_in, relevance, qualified, notes). Tolerant of shape."""
    notes: List[str] = []
    if not isinstance(raw, dict):
        return "", [], [], False, ["composer returned a non-object payload"]
    prose = raw.get("prose") or raw.get("text") or ""
    prose = prose.strip() if isinstance(prose, str) else ""
    grounded = raw.get("grounded_in")
    grounded = [str(g) for g in grounded] if isinstance(grounded, list) else []
    relevance = raw.get("relevance")
    relevance = [r for r in relevance if isinstance(r, dict)] if isinstance(relevance, list) else []
    qualified = bool(raw.get("qualified"))
    return prose, grounded, relevance, qualified, notes


def _uncited_image_mentions(prose: str, citations: Sequence[Citation],
                            memory: WorkingMemory,
                            permitted: Sequence[str] = ()) -> Tuple[str, ...]:
    """Images named in the prose that this section does not cite (rule 3).

    The failure this catches reads better than the prose that passes: "the colonnade prepares the
    rotunda" in a section whose only evidence is a field on the Lustgarten is fluent, plausible,
    and rests on nothing. Matching is on the corpus's own titles and ids, so it can only ever fire
    on an image the curator actually named.

    `permitted` is the images the PRIOR section cited, and exempting them is not a loophole — it
    is the difference between a guard and a nuisance. A `complicate` section is handed the prior
    claim and told to make it harder to state simply; it will name that claim's image, correctly,
    every time. Flagging it there would fire on every complication in every article, and a warning
    that fires on everything is one a reader learns to skip — which would cost exactly the real
    leaps this is built to catch. Found by the guarded run, which flagged its own §2.
    """
    if not isinstance(memory, CorpusWorkingMemory) or memory.corpus is None:
        return ()
    cited = {c.image for c in citations if c.image} | {p for p in permitted if p}
    lowered = prose.lower()
    hits: List[str] = []
    for image in memory.corpus.images:
        if image.post_id in cited:
            continue
        for token in (image.title, image.post_id):
            if token and len(token) > 3 and token.lower() in lowered:
                hits.append(image.post_id)
                break
    return tuple(dict.fromkeys(hits))


def compose_section(claim: BoundClaim, memory: WorkingMemory, llm: Optional[LLM], *,
                    function: str = SUPPORT, prior_claim: str = "", thesis: str = "",
                    percepts: Optional[Sequence[PerceptStep]] = None,
                    prior_images: Sequence[str] = ()):
    """Compose ONE claim into prose, then enforce the guards in code.

    Returns a `Section` or an `UncomposedSection`. Never returns prose that cites nothing, and
    never invents prose when the model is absent.
    """
    chosen = list(percepts if percepts is not None else claim.bound)
    citations = tuple(_citation_for(p, claim, memory) for p in chosen)
    if not citations:
        return UncomposedSection(claim_id=claim.claim_id, claim=claim.claim.text,
                                 reason=SECTION_CITES_NOTHING,
                                 detail="the claim carries no confirmed percept")
    if llm is None:
        # Rule 5. A template sentence here would be a claim nobody made, wearing the shape of one
        # somebody did.
        return UncomposedSection(claim_id=claim.claim_id, claim=claim.claim.text,
                                 reason=SECTION_NO_MODEL,
                                 detail="no language model available; no prose was invented")

    prompt = build_section_prompt(claim, citations, function=function,
                                  prior_claim=prior_claim, thesis=thesis)
    try:
        payload = json.loads(llm.complete(SYSTEM_PROMPT, prompt))
    except Exception as e:
        return UncomposedSection(claim_id=claim.claim_id, claim=claim.claim.text,
                                 reason=SECTION_NO_PROSE,
                                 detail=f"{type(e).__name__}: {e}")

    prose, grounded_in, relevance, model_qualified, _notes = _parse_section_payload(payload)
    if not prose:
        return UncomposedSection(claim_id=claim.claim_id, claim=claim.claim.text,
                                 reason=SECTION_NO_PROSE,
                                 detail="the composer returned no prose")

    # RULE 2 — intersect, never trust. Ids the model claimed and did not have are dropped and
    # recorded; a section citing nothing after the intersection is refused, not published.
    available = {c.step_id: c for c in citations}
    kept = [available[g] for g in grounded_in if g in available]
    dropped = tuple(g for g in grounded_in if g not in available)
    if not kept:
        return UncomposedSection(
            claim_id=claim.claim_id, claim=claim.claim.text, reason=SECTION_CITES_NOTHING,
            detail=("the composer grounded its prose in "
                    + (f"evidence this claim does not have ({', '.join(dropped)})"
                       if dropped else "nothing")))

    # RULE 4 — relevance, surfaced. A percept the composer says does not bear on the claim cannot
    # silently remain a support: it becomes a caveat and the section is qualified.
    flags: List[Dict[str, str]] = []
    for row in relevance:
        rid = str(row.get("id") or "")
        if rid in available and row.get("bears_on_claim") is False:
            flags.append({"step_id": rid, "actuator": available[rid].actuator,
                          "why": str(row.get("why") or "does not bear on this claim")})

    caveats = list(claim.caveats)
    if claim.downgraded:
        caveats.append(f"aimed to be '{claim.claim.target_status}', reached "
                       f"'{claim.achieved_status}'")
    for flag in flags:
        caveats.append(f"{flag['actuator']} does not bear on this claim: {flag['why']}")

    # A `sourced` citation with no attribution is a quotation with no quoter.
    for citation in kept:
        if citation.is_sourced and not citation.attribution:
            caveats.append(f"{citation.actuator} is sourced from outside the image but names no "
                           f"source; it is reported as unattributed")

    epistemic = weakest_status([c.epistemic for c in kept])
    qualified = bool(model_qualified or flags or caveats or claim.status == QUALIFIED
                     or epistemic == UNCERTAIN)

    return Section(
        claim_id=claim.claim_id, claim=claim.claim.text, function=function, prose=prose,
        citations=tuple(kept), epistemic=epistemic, qualified=qualified,
        caveats=tuple(dict.fromkeys(caveats)), relevance_flags=tuple(flags),
        dropped_citations=dropped,
        uncited_mentions=_uncited_image_mentions(prose, kept, memory,
                                                 permitted=prior_images))


# ── the counter-reading ──────────────────────────────────────────────────────

COUNTER_SYSTEM_PROMPT = (
    "You write the counter-reading of a perceptual close-reading article: the part that reads "
    "the evidence AGAINST the article's own argument. You output JSON and nothing else.\n\n"
    "Hard rules:\n"
    "- Write ONLY about the evidence listed. You have not seen the pictures.\n"
    "- Your job is to state what this evidence would mean if the main argument were wrong. Do "
    "not defend the argument, and do not conclude that the argument survives.\n"
    "- Do not overstate: if the challenge evidence is weak, say that it is weak. A counter-"
    "reading that is easy to dismiss must be written as easy to dismiss.\n"
    "- Carry the kind of knowing into the words, as in the body sections.\n"
    "- Two to four sentences."
)


def compose_counter_reading(argument: ArgumentPlan, memory: WorkingMemory,
                            llm: Optional[LLM], *, thesis: str = "") -> CounterReading:
    """Compose the counter-reading from surviving `challenge` percepts, or report its absence.

    NEVER fabricates. An ungrounded counter-reading is the most convincing possible way to look
    rigorous while having tested nothing, and it is the one piece of an article a reader is least
    equipped to check.
    """
    challenges: List[Tuple[BoundClaim, PerceptStep]] = [
        (claim, percept) for claim in argument.claims for percept in claim.bound
        if percept.function == CHALLENGE]

    if not challenges:
        proposed = any(p.function == CHALLENGE
                       for c in argument.claims for p in c.claim.percepts)
        # M2's distinction, carried into the prose layer verbatim.
        return CounterReading(
            grounded=False,
            absence_reason=(COUNTER_NOT_PRODUCED if proposed else COUNTER_NONE_PROPOSED),
            absence_detail=("A counter-reading was planned, but the evidence for it could not be "
                            "produced; none is offered here rather than one being supplied."
                            if proposed else
                            "No evidence was gathered that could tell against this argument. "
                            "The argument is therefore untested, not confirmed."))

    citations = tuple(_citation_for(p, c, memory) for c, p in challenges)
    if llm is None:
        return CounterReading(grounded=False, citations=citations,
                              absence_reason=SECTION_NO_MODEL,
                              absence_detail="challenge evidence exists but no language model "
                                             "was available to read it against the argument")
    prompt = (
        f"THE ARTICLE'S ARGUMENT:\n{thesis}\n\n"
        f"THE CHALLENGE EVIDENCE — everything you know:\n"
        f"{json.dumps(_evidence_rows(citations), indent=2)}\n\n"
        f"Return JSON: {{\"prose\": \"<2-4 sentences>\", "
        f"\"grounded_in\": [\"<evidence id>\"]}}")
    try:
        payload = json.loads(llm.complete(COUNTER_SYSTEM_PROMPT, prompt))
    except Exception as e:
        return CounterReading(grounded=False, citations=citations,
                              absence_reason=SECTION_NO_PROSE,
                              absence_detail=f"{type(e).__name__}: {e}")
    prose, grounded_in, _rel, _q, _n = _parse_section_payload(payload)
    available = {c.step_id: c for c in citations}
    kept = tuple(available[g] for g in grounded_in if g in available) or citations
    if not prose:
        return CounterReading(grounded=False, citations=citations,
                              absence_reason=SECTION_NO_PROSE,
                              absence_detail="the composer returned no counter-reading")
    return CounterReading(grounded=True, prose=prose, citations=kept)


# ── qualifications: what the corpus could not carry ──────────────────────────

def compose_qualifications(argument: ArgumentPlan) -> Tuple[Qualification, ...]:
    """M2's `gaps()` → honest limits. Never assertions.

    The prose is TEMPLATED rather than model-written, and that is deliberate: a qualification is
    the one part of an article where fluency is a hazard. A language model asked to write "we
    could not establish X" will, given the chance, explain what X would have shown — and the
    explanation asserts the claim the qualification exists to withhold.
    """
    out: List[Qualification] = []
    for claim in argument.claims:
        if claim.status == SUPPORTED and not claim.downgraded and not claim.caveats:
            continue
        if claim.status == REFUSED:
            prose = (f"This reading could not establish that {_lower_first(claim.claim.text)} "
                     f"No evidence for it could be produced from this corpus, so the point is "
                     f"left open rather than argued.")
        elif claim.status == QUALIFIED:
            missing = ", ".join(sorted({p.actuator for p, _ in claim.unbound}))
            prose = (f"The claim that {_lower_first(claim.claim.text)} rests on less than was "
                     f"asked of it: {missing} could not be produced. What is said above stands "
                     f"only on what did.")
        else:                      # supported but downgraded, or carrying a caveat
            prose = (f"The claim that {_lower_first(claim.claim.text)} is carried, but not in "
                     f"the way it was aimed at: it sought "
                     f"'{claim.claim.target_status}' evidence and rests on "
                     f"'{claim.achieved_status}'.")
        out.append(Qualification(
            claim_id=claim.claim_id, claim=claim.claim.text, status=claim.status, prose=prose,
            why=claim.reason))
    for refusal in argument.refusals:
        out.append(Qualification(
            claim_id="", claim="", status="argument_refused",
            prose=f"This argument is incomplete: {refusal.detail}",
            why=refusal.reason))
    return tuple(out)


def _lower_first(text: str) -> str:
    text = (text or "").strip()
    return (text[0].lower() + text[1:]) if text else text


# ── the whole draft ──────────────────────────────────────────────────────────

def compose_article(argument: ArgumentPlan, memory: WorkingMemory, *,
                    provenance: Any = None, llm: Optional[LLM] = None,
                    run_id: str = "", require_confirmation: bool = True) -> ArticleDraft:
    """A confirmed ArgumentPlan → a quarantined ArticleDraft.

    CONFIRM FIRST (rule 1). When a chain `provenance` is given, the argument is re-judged through
    M2's `confirm_against_chain` — downgrade-only — and composition proceeds from the CONFIRMED
    claims. With `require_confirmation` on and no provenance supplied, NOTHING is composed: an
    article written from a plan is an article about producers that may never have run, and it
    would be indistinguishable from one written from a run.
    """
    notes: List[str] = []
    if provenance is not None:
        argument = confirm_against_chain(argument, provenance)
        notes.append("confirmed against a run before composing")
    elif require_confirmation:
        return ArticleDraft(
            thesis=argument.thesis, run_id=run_id,
            qualifications=compose_qualifications(argument),
            notes=("no run was supplied; nothing was composed. An article written from a plan "
                   "would describe evidence that may never have been produced.",))
    else:
        notes.append("composed WITHOUT run confirmation (explicitly permitted by the caller)")

    sections: List[Section] = []
    uncomposed: List[UncomposedSection] = []
    prior_claim = ""
    prior_images: Tuple[str, ...] = ()

    for claim in argument.claims:
        if require_confirmation and claim.binding != BINDING_CONFIRMED:
            uncomposed.append(UncomposedSection(
                claim_id=claim.claim_id, claim=claim.claim.text,
                reason=SECTION_NOT_CONFIRMED,
                detail="the run did not confirm this claim's evidence"))
            continue
        if not claim.carried:
            # A refused claim is NOT a section. It reaches the reader as a qualification, which
            # is the argument-level cites-nothing rule: what could not be carried is stated as a
            # limit and never narrated as a finding.
            continue
        # The section's function is the function of the percepts CARRYING it. A claim whose only
        # surviving evidence is a challenge reads as a challenge, whatever it was planned as.
        body = [p for p in claim.bound if p.function != CHALLENGE]
        if not body:
            continue                      # challenge-only claims belong to the counter-reading
        function = _dominant_function(body)
        composed = compose_section(claim, memory, llm, function=function,
                                   prior_claim=prior_claim, thesis=argument.thesis,
                                   percepts=body, prior_images=prior_images)
        if isinstance(composed, Section):
            sections.append(composed)
            prior_claim = claim.claim.text
            # What the NEXT section may name without being flagged: this section cited it, so the
            # article has established it by the time the next paragraph refers back to it.
            prior_images = tuple(c.image for c in composed.citations if c.image)
        else:
            uncomposed.append(composed)

    counter = compose_counter_reading(argument, memory, llm, thesis=argument.thesis)
    qualifications = compose_qualifications(argument)
    epistemic = weakest_status([s.epistemic for s in sections]) if sections else UNCERTAIN

    thesis_prose = _compose_thesis(argument, sections, llm, notes)

    if any(s.uncited_mentions for s in sections):
        notes.append("a section named an image it does not cite; see `uncited_mentions`")
    if any(s.relevance_flags for s in sections):
        notes.append("a percept was reported as not bearing on its claim; those sections are "
                     "qualified")

    return ArticleDraft(
        thesis=argument.thesis, thesis_prose=thesis_prose, sections=tuple(sections),
        uncomposed=tuple(uncomposed), counter_reading=counter,
        qualifications=qualifications, epistemic=epistemic, notes=tuple(notes),
        run_id=run_id or _run_id_from(provenance), model=(llm.model if llm else None))


def _dominant_function(percepts: Sequence[PerceptStep]) -> str:
    """What this section is DOING. `complicate` wins over `support` when both are present — a
    section carrying a complication is a complication, and flattening it to support would erase
    the §4-complicates-§3 move the argument was built to make."""
    functions = {p.function for p in percepts}
    if COMPLICATE in functions:
        return COMPLICATE
    if SUPPORT in functions:
        return SUPPORT
    return next(iter(functions), SUPPORT)


THESIS_SYSTEM_PROMPT = (
    "You write the opening paragraph of a perceptual close-reading article. You output JSON and "
    "nothing else.\n\n"
    "Hard rules:\n"
    "- You are given the article's thesis and the claims that the body ACTUALLY establishes. "
    "State the thesis and say what the article will show — using only those claims.\n"
    "- Do not promise anything not in the list. If a claim is marked qualified, do not present "
    "it as settled.\n"
    "- Do not describe any image. You have not seen them.\n"
    "- Two to four sentences."
)


def _compose_thesis(argument: ArgumentPlan, sections: Sequence[Section],
                    llm: Optional[LLM], notes: List[str]) -> str:
    """The opening paragraph, resting on the claims the body actually establishes.

    Composed from the SECTIONS rather than from the thesis alone, so an article whose body
    qualified two of its three claims cannot open by promising all three.
    """
    if llm is None or not sections:
        return ""
    rows = [{"claim": s.claim, "function": s.function, "kind_of_knowing": s.epistemic,
             "qualified": s.qualified} for s in sections]
    prompt = (f"THE THESIS:\n{argument.thesis}\n\n"
              f"WHAT THE BODY ACTUALLY ESTABLISHES:\n{json.dumps(rows, indent=2)}\n\n"
              f'Return JSON: {{"prose": "<2-4 sentences>"}}')
    try:
        payload = json.loads(llm.complete(THESIS_SYSTEM_PROMPT, prompt))
        prose, _g, _r, _q, _n = _parse_section_payload(payload)
        return prose
    except Exception as e:
        notes.append(f"the opening paragraph could not be composed: {type(e).__name__}")
        return ""


def _run_id_from(provenance: Any) -> str:
    return str(getattr(provenance, "chain_id", "") or "")
