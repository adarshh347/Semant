"""
HARNESS-001A — the model-backed framer: one call, closed vocabulary, refusals kept.

The same seam `GroqPlanner` sits in, one level earlier. `GroqPlanner` asks a model for a chain of
ACTUATORS; this asks it to read a QUESTION — which clauses want a measurement, which want a
reading, which rest on a source, which are about something that does not exist, and which nothing
can operationalise at all.

THE GUARDS, carried over from PLANNER-001 verbatim where they apply, because they are the reason
that seam holds:

  1. HALLUCINATIONS ARE NOT FILTERED AWAY. An action type outside the Perceptual Action Grammar
     is not dropped while parsing. It becomes a `Refusal` on the frame, by name. Dropping it
     would hide how often the model invents capabilities, and the refusal rate is the only
     observable that says whether to trust the framer at all.

  2. PAYLOAD KEYS ARE CLAMPED TO THE DECLARED VOCABULARY. Every key an action does not declare is
     dropped and RECORDED as a `disallowed_params` refusal. This is what stops a model that has
     never seen the image from smuggling in a mask, a box, a region id or a confidence.

  3. NO RE-PROMPT LOOP. Exactly one call per `frame()`. A model whose actions are all refused
     produces a frame with no actions and a full refusal list. Looping until something passes
     would search for a frame that validates rather than one that is true.

  4. UNAVAILABLE IS SAID OUT LOUD. No key, no client, an API error, unparseable JSON — all fall
     back to the deterministic framer and record WHY in `notes` and in `provenance.framer_kind`
     (`model_fallback_deterministic`). A silent fallback would mean the model could be down for a
     week and every frame would still look like it came from one.

  5. AN EMPTY MODEL RESULT IS NOT A FAILURE. A model that safely proposes no actions has given a
     valid answer, and it does NOT trigger the deterministic fallback. Falling back there would
     overrule the model's honest silence with a keyword guess — the same rule `GroqPlanner`
     applies to an empty plan.

WHAT THE MODEL MAY NOT DO, enforced here rather than requested in the prompt:

  · claim it saw the images — no field of the frame can carry a mask, region, box or confidence,
    and `InquiryFrame`'s own validator refuses one that does;
  · author `challenge_percept` — the human's veto (P1 addendum §3.1). A proposal is refused as
    `human_action_required` and the REQUEST is kept, so asking for a counter-reading is recorded
    rather than erased;
  · set an action to `applied`, or bypass `requiresConfirmation` — both are spec-authored in
    `grammar.normalize_action` and the caller's value is discarded;
  · turn an `imagined` or `interpretive` demand into a measurement — the frame refuses a term
    that is both a measurable demand and a semantic remainder, and unknown demand kinds are
    refused rather than coerced upward.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from backend.schemas.inquiry import (Attention, DemandKind, EpistemicDemand, FrameProvenance,
                                     InquiryFrame, InquiryMode, Refusal, RefusalKind,
                                     SemanticRemainder, UnresolvedTerm, mint_inquiry_id,
                                     prompt_hash, utc_now_iso)
from backend.services import role_registry

from . import grammar, lexicon
from .base import to_corpus_context
from .deterministic import UNCREATED, DeterministicFramer

ROLE = "inquiry_framer"
PRODUCER = "inquiry/model-v1"

#: More attentions than this is the model listing the prompt back rather than reading it. Applied
#: after parsing and the overflow is REPORTED, never trimmed silently.
MAX_ATTENTIONS = 16
MAX_ACTIONS = 12

SYSTEM_PROMPT = (
    "You are a framing component inside a visual close-reading tool. You are given a person's "
    "PROMPT and metadata about a corpus of images — ids, titles, counts. YOU CANNOT SEE THE "
    "IMAGES and you never will. You output JSON and nothing else.\n\n"
    "Your job is to read the QUESTION, not to answer it.\n\n"
    "Hard rules:\n"
    "- Never state or imply that you saw anything. Every attention you report is attributed to "
    "the person's words: 'the user said X'.\n"
    "- Never output a mask, a bounding box, coordinates, a region id, a mark id, an area, or a "
    "confidence value. You do not possess that information.\n"
    "- Use ONLY action types from the provided grammar, and set only the parameter keys listed "
    "for that action. Never invent an action.\n"
    "- You may NOT propose 'challenge_percept'. Only a person may author a challenge. If the "
    "prompt asks for one, say so in `human_action_requested` instead.\n"
    "- Classify each clause by what KIND of knowing it asks for:\n"
    "    measurable   — an organ could put a number or an extent on it, once one runs\n"
    "    interpretive — a reading ABOUT a picture; not a weak measurement, a different claim\n"
    "    sourced      — a claim from outside the picture, needing a citation\n"
    "    imagined     — something that does not exist and cannot be measured or cited\n"
    "    unresolved   — nothing available can operationalise it at all\n"
    "- A word like 'sensuality' is INTERPRETIVE. It does not become measurable because fold "
    "geometry contributes to a reading of it. A hybrid style that does not exist yet is "
    "IMAGINED. A period or a school is SOURCED.\n"
    "- `semantic_remainder` is what the available measurements will NOT exhaust even if every "
    "one of them succeeds. It is first-class. Do not leave it empty for an interpretive prompt.\n"
    "- If nothing in the grammar serves the prompt, return an empty `proposed_actions`. An empty "
    "list is a valid and useful answer; a plausible-looking wrong act is not."
)


def _grammar_catalog() -> List[Dict[str, Any]]:
    """The action vocabulary, as data the model must choose from.

    Sent as a structured list rather than described in prose, for the reason `groq_planner` gives:
    an action name is a closed set and should be typed as one, because prose invites paraphrase
    and a paraphrased name is a hallucination that merely looks like a typo.

    `challenge_percept` is DELIBERATELY ABSENT from the catalogue as well as forbidden in the
    system prompt. Listing an action and then forbidding it invites exactly one attempt.
    """
    rows: List[Dict[str, Any]] = []
    for name in grammar.ACTION_TYPES:
        if not grammar.model_may_author(name):
            continue
        spec = grammar.SPEC[name]
        rows.append({
            "action": name,
            "target": spec.target,
            "required_params": list(spec.required),
            "params_you_may_set": list(spec.payload_keys),
            "vocabularies": {k: list(v) for k, v in spec.enums.items()},
            "needs_a_mark_from_the_person": spec.needs_geometry,
        })
    return rows


def build_prompt(prompt: str, corpus: Mapping[str, Any]) -> str:
    return (
        f"THE PERSON'S PROMPT, verbatim:\n{prompt}\n\n"
        f"THE CORPUS — metadata only. You have not seen these images:\n"
        f"{json.dumps(dict(corpus), indent=2)}\n\n"
        f"AVAILABLE ACTIONS — choose only from these:\n"
        f"{json.dumps(_grammar_catalog(), indent=2)}\n\n"
        f"KINDS OF KNOWING: {json.dumps([k.value for k in DemandKind])}\n"
        f"MODES: {json.dumps([m.value for m in InquiryMode])}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"mode": "<one of the modes>", '
        f'"requested_output": "<comparison|article|map|list|reading, or null>", '
        f'"attentions": [{{"term": "<the words the person used>", '
        f'"category": "<what you read it as>"}}], '
        f'"epistemic_demands": [{{"clause": "<the clause, verbatim from the prompt>", '
        f'"term": "<the word in it that decides the kind>", '
        f'"kind": "<one of the kinds>", "why": "<one clause>"}}], '
        f'"proposed_actions": [{{"type": "<action from the list>", "payload": {{}}, '
        f'"reason": "<why this act, one clause>"}}], '
        f'"unresolved_terms": [{{"term": "…", "why": "…"}}], '
        f'"semantic_remainder": [{{"term": "…", "why": "…", '
        f'"contributing_measurements": []}}], '
        f'"human_action_requested": [{{"action": "…", "why": "…"}}]}}\n'
        f'Return empty lists rather than inventing content for any field.'
    )


class ModelInquiryFramer:
    """A model proposes the framing. The grammar still refuses what it may not author.

    `client` is injectable so the whole class is testable with no network — the tests pass a fake
    and never touch the API. Shaped like `GroqPlanner` on purpose: one method, `last_notes`, and
    an observable `calls` counter that pins the no-loop guard.
    """

    name = "model"

    def __init__(self, client: Any = None, *, model: Optional[str] = None,
                 fallback: Optional[Any] = None):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        self.fallback = fallback if fallback is not None else DeterministicFramer()
        self.last_notes: Tuple[str, ...] = ()
        self.calls: int = 0            # guard 3 is observable: tests assert this is 1

    @property
    def model(self) -> Optional[str]:
        return self._model if self._model is not None else role_registry.model_for(ROLE)

    # ── client ──
    def _get_client(self) -> Any:
        """Lazy real client. An absent key is UNAVAILABLE, not a crash."""
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        try:
            from groq import Groq

            from backend.config import settings
            self._client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        except Exception:
            self._client = None
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    # ── the seam ──
    def frame(self, prompt: str, corpus_context: Optional[Mapping[str, Any]] = None, *,
              mode: InquiryMode = InquiryMode.EXPLORE,
              now: Optional[datetime] = None) -> InquiryFrame:
        corpus = to_corpus_context(corpus_context)
        client = self._get_client()
        if client is None:
            return self._fall_back(prompt, corpus_context, mode, now,
                                   "the inquiry framer is unavailable (no client or API key)")
        try:
            self.calls += 1
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": build_prompt(prompt, corpus.model_dump())}],
                model=self.model,
                response_format={"type": "json_object"},
            )
            payload = json.loads(completion.choices[0].message.content)
        except Exception as exc:
            return self._fall_back(prompt, corpus_context, mode, now,
                                   f"the inquiry framer failed: {type(exc).__name__}")

        # Cleared on the success path too. `last_notes` is documented as an observable of the
        # LAST framing, and one fallback followed by one success would otherwise keep reporting
        # the stale fallback reason forever.
        self.last_notes = (f"framer: {self.name}",)
        return _assemble(prompt, corpus, payload, mode=mode, now=now, model=self.model)

    def _fall_back(self, prompt: str, corpus_context: Optional[Mapping[str, Any]],
                   mode: InquiryMode, now: Optional[datetime], why: str) -> InquiryFrame:
        """Deterministic framing, and the frame SAYS it was deterministic.

        The explicit fallback is allowed only here — when the model itself never answered. A
        model that answered with no safe actions gets its empty answer kept.
        """
        frame = self.fallback.frame(prompt, corpus_context, mode=mode, now=now)
        notes = [why, "fell back to the deterministic framer, which reads the shared lexicon "
                      "and no model at all"] + list(frame.notes)
        provenance = frame.provenance.model_copy(update={
            "producer": PRODUCER,
            "framer_kind": "model_fallback_deterministic",
            "model": None,
            "role": ROLE,
            "model_calls": self.calls,
        })
        self.last_notes = tuple(notes[:2])
        return frame.model_copy(update={"notes": notes, "provenance": provenance})


# ── parsing ──────────────────────────────────────────────────────────────────

def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _rows(payload: Mapping[str, Any], key: str) -> List[Mapping[str, Any]]:
    raw = payload.get(key)
    return [r for r in raw if isinstance(r, Mapping)] if isinstance(raw, list) else []


def _assemble(prompt: str, corpus: Any, payload: Any, *, mode: InquiryMode,
              now: Optional[datetime], model: Optional[str]) -> InquiryFrame:
    """Model JSON → a validated frame, plus every refusal along the way.

    Deliberately tolerant of SHAPE and strict about CONTENT — the split `parse_steps` makes. A
    missing `why`, an integer where a string belongs, a payload as a list: all survivable,
    because none of them can cause a wrong claim. An invented action type, a disallowed payload
    key, an unknown demand kind: none is corrected, all are refused by name.
    """
    notes: List[str] = []
    refusals: List[Refusal] = []

    if not isinstance(payload, Mapping):
        payload = {}
        notes.append("the framer returned a non-object payload; nothing in it was used")

    # ── mode ──
    raw_mode = _text(payload.get("mode"))
    if raw_mode and raw_mode in {m.value for m in InquiryMode}:
        mode = InquiryMode(raw_mode)
    elif raw_mode:
        refusals.append(Refusal(kind=RefusalKind.UNKNOWN_MODE, what=raw_mode,
                                why=f"not one of {[m.value for m in InquiryMode]}; the caller's "
                                    f"mode {mode.value!r} stands"))

    # ── attentions ──
    attentions: List[Attention] = []
    for row in _rows(payload, "attentions"):
        term = _text(row.get("term"))
        if not term:
            continue
        at = prompt.lower().find(term.lower())
        attentions.append(Attention(
            term=term,
            # The attribution sentence is BUILT HERE, never taken from the model. A model asked to
            # phrase its own attribution is a model one prompt-edit away from writing "Semant
            # detected", and the schema would accept it.
            said=f"the user said “{term}”",
            span=(at, at + len(term)) if at >= 0 else None,
            category=_text(row.get("category"), "unnamed"),
            action_roles=[str(r) for r in row.get("action_roles", []) if isinstance(r, str)]))
    if len(attentions) > MAX_ATTENTIONS:
        notes.append(f"the framer reported {len(attentions)} attentions; kept the first "
                     f"{MAX_ATTENTIONS}")
        attentions = attentions[:MAX_ATTENTIONS]

    # ── demands ──
    kinds = {k.value for k in DemandKind}
    demands: List[EpistemicDemand] = []
    for row in _rows(payload, "epistemic_demands"):
        clause = _text(row.get("clause"))
        kind = _text(row.get("kind")).lower()
        if not clause:
            continue
        if kind not in kinds:
            # NOT coerced. An unknown kind has no safe direction to be pushed in: guessing
            # `interpretive` would silently downgrade a real measurement request, and guessing
            # `measurable` would do the far worse thing.
            refusals.append(Refusal(kind=RefusalKind.UNKNOWN_DEMAND_KIND, what=kind or "(empty)",
                                    why=f"not one of {sorted(kinds)}; the demand was dropped",
                                    detail=[clause]))
            continue
        demands.append(EpistemicDemand(clause=clause, term=_text(row.get("term")) or None,
                                       kind=DemandKind(kind),
                                       why=_text(row.get("why"), "the framer gave no reason")))

    # ── actions ──
    actions: List[Dict[str, Any]] = []
    for index, row in enumerate(_rows(payload, "proposed_actions"), start=1):
        type_ = _text(row.get("type")) or _text(row.get("action"))
        if not type_:
            continue
        if grammar.spec_for(type_) is None:
            # GUARD 1. Refused BY NAME rather than dropped while parsing.
            refusals.append(Refusal(
                kind=RefusalKind.UNKNOWN_ACTION, what=type_,
                why="not in the Perceptual Action Grammar. It is recorded rather than dropped: "
                    "how often a framer invents a capability is the observable that says whether "
                    "to trust it.",
                detail=sorted(str(k) for k in (row.get("payload") or {}))
                if isinstance(row.get("payload"), Mapping) else []))
            continue
        if not grammar.model_may_author(type_):
            refusals.append(Refusal(
                kind=RefusalKind.HUMAN_ACTION_REQUIRED, what=type_,
                why="only a person may author this act — it is the human's veto over the circuit. "
                    "The request is kept so that asking for it is not erased.",
                detail=[_text(row.get("reason"))] if _text(row.get("reason")) else []))
            continue

        kept, dropped = grammar.clamp_payload(type_, row.get("payload"))
        if dropped:
            # GUARD 2. Recorded, never silent: this is how you find out a framer is trying to
            # author geometry, which is the failure that matters most and shows up nowhere else.
            refusals.append(Refusal(
                kind=RefusalKind.DISALLOWED_PARAMS, what=type_,
                why=f"{type_} does not declare these keys, so they were dropped before the act "
                    f"was built. A framer that has not seen the image may not author them.",
                detail=dropped))
        reason = _text(row.get("reason"))
        if reason and "reason" in grammar.SPEC[type_].payload_keys:
            kept.setdefault("reason", reason)

        action = grammar.normalize_action(
            {"type": type_, "source": "model_suggested", "payload": kept,
             "intent": _text(row.get("intent")),
             "provenance": {"planner": PRODUCER, "promptExcerpt": _excerpt(prompt),
                            "matched": [], "model": model}},
            now=UNCREATED, action_id=f"act_{index}")
        if action is None:
            verdict = grammar.validate_action(
                {"type": type_, "source": "model_suggested", "payload": kept,
                 "id": f"act_{index}", "label": grammar.default_label(type_, kept),
                 "status": "proposed", "target": grammar.SPEC[type_].target, "createdAt": UNCREATED})
            refusals.append(Refusal(kind=RefusalKind.INVALID_ACTION, what=type_,
                                    why="a known action that did not validate against the grammar",
                                    detail=verdict.errors))
            continue
        actions.append(action)

    if len(actions) > MAX_ACTIONS:
        notes.append(f"the framer proposed {len(actions)} actions; kept the first {MAX_ACTIONS}")
        actions = actions[:MAX_ACTIONS]

    # ── what only a person may do ──
    for row in _rows(payload, "human_action_requested"):
        what = _text(row.get("action"))
        if what:
            refusals.append(Refusal(kind=RefusalKind.HUMAN_ACTION_REQUIRED, what=what,
                                    why=_text(row.get("why"),
                                              "the framer recorded this as a request for a person")))

    # ── unresolved and remainder ──
    unresolved = [UnresolvedTerm(term=_text(r.get("term")),
                                 why=_text(r.get("why"), "the framer gave no reason"))
                  for r in _rows(payload, "unresolved_terms") if _text(r.get("term"))]

    # Keyed EXACTLY as `InquiryFrame`'s own validator keys it — `term or clause`. Keying only on
    # `term` here let a measurable demand with an empty term slip past this refusal and then die
    # inside the `InquiryFrame(...)` construction below, where a model's contradiction would
    # surface as a ValidationError somebody reads as a bug in the schema.
    measurable_terms = {(d.term or d.clause).lower() for d in demands
                        if d.kind is DemandKind.MEASURABLE}
    remainder: List[SemanticRemainder] = []
    for row in _rows(payload, "semantic_remainder"):
        term = _text(row.get("term"))
        if not term:
            continue
        if term.lower() in measurable_terms:
            # The frame's own validator would refuse this outright. Refusing it HERE, by name,
            # keeps the model's contradiction visible instead of turning the whole framing into a
            # ValidationError somebody reads as a bug in the schema.
            refusals.append(Refusal(
                kind=RefusalKind.INVALID_ACTION, what=term,
                why="the framer called this both a measurable demand and a semantic remainder. "
                    "A remainder is what measurement does not reach; both cannot be true of one "
                    "term, so the remainder entry was dropped and the demand stands."))
            continue
        remainder.append(SemanticRemainder(
            term=term, why=_text(row.get("why"), "the framer gave no reason"),
            contributing_measurements=[str(m) for m in row.get("contributing_measurements", [])
                                       if isinstance(m, str)]))

    if not actions:
        notes.append("the framer proposed no grammar-valid act. That is a valid answer and it "
                     "was NOT replaced by a keyword plan.")
    if demands and not remainder and any(d.kind in (DemandKind.INTERPRETIVE, DemandKind.IMAGINED)
                                         for d in demands):
        notes.append("the framer reported an interpretive or imagined demand and no semantic "
                     "remainder. The gap is stated rather than filled in on its behalf.")

    requested = _text(payload.get("requested_output")) or None
    if requested and requested.lower() in {"null", "none"}:
        requested = None

    return InquiryFrame(
        inquiry_id=mint_inquiry_id(prompt, now=now),
        prompt=prompt,
        mode=mode,
        attentions=attentions,
        epistemic_demands=demands,
        proposed_actions=actions,
        unresolved_terms=unresolved,
        semantic_remainder=remainder,
        requested_output=requested,
        corpus_context=corpus,
        provenance=FrameProvenance(
            producer=PRODUCER, framer_kind="model", model=model, role=ROLE,
            prompt_sha256=prompt_hash(prompt), grammar_version=grammar.SCHEMA_VERSION,
            lexicon_version=lexicon.SCHEMA_VERSION, framed_at=utc_now_iso(now), model_calls=1),
        refusals=refusals,
        notes=notes)


def _excerpt(prompt: str, max_len: int = 120) -> str:
    text = " ".join(str(prompt or "").split())
    return text if len(text) <= max_len else f"{text[:max_len - 1]}…"
