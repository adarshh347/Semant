"""
HARNESS-001A — the deterministic framer: a prompt read by the shared lexicon, and nothing else.

This is the existing attunement planner's intelligence made available to the backend, NOT a newly
invented keyword system. It reads `contracts/attunement-lexicon.v1.json` — the same file the
Differential panel reads — and proposes acts from `contracts/perceptual-action-grammar.v1.json` —
the same file the Differential validator reads.

WHY DETERMINISTIC FIRST, AGAIN. P2B's ordering argument holds one level up: the frame, the
grammar and the refusals have to exist and be trustworthy BEFORE anything generative is allowed
near them. A model that invents an action type is caught here and recorded as a refusal; a model
that returned free prose would have nothing to be caught by.

FOUR PLACES THIS DELIBERATELY DIFFERS FROM THE FRONTEND PLANNER, each because the backend is
reading a QUESTION about a corpus rather than a NOTICING about one picture:

  1. NO `compose_percept`. The panel seeds a percept draft with the curator's own sentence,
     because they were describing what they saw. A question is not a noticing, and seeding a
     percept from one would put a claim in the curator's mouth that they did not make.

  2. NO `challenge_percept`. The act requires a `percept_ref` and there is no percept here. The
     panel can pass 'draft' because a draft exists on screen; minting one in the backend would
     be inventing the thing the challenge is about. When the prompt ASKS for a counter-reading it
     is recorded as a refusal of kind `human_action_required`, never erased.

  3. `find_parts` ONLY WHEN A CORPUS WAS NAMED. There is nothing to open into parts if no image
     was named, and proposing it anyway is the panel's `hasParts` suppression read from the other
     side.

  4. THE INQUIRY CUES FIRE. Comparison, distinction, speculation and sequence are about the shape
     of a question over several images; the panel has no use for them and does not read them.

WHAT THE FRAMER MAY NOT DO, and does not: look at an image, author geometry, assert that any
evidence exists, dispatch anything, or write to any store. It reads words.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from backend.schemas.inquiry import (Attention, CorpusContext, DemandKind, EpistemicDemand,
                                     FrameProvenance, InquiryFrame, InquiryMode, Refusal,
                                     RefusalKind, SemanticRemainder, UnresolvedTerm,
                                     mint_inquiry_id, prompt_hash, utc_now_iso)

from . import grammar, lexicon
from .base import to_corpus_context

PRODUCER = "inquiry/deterministic-v1"

#: A proposal has not been created; it has been proposed. `createdAt: 0` is the absence of a
#: moment rather than a moment, and keeping it constant is what makes two framings of one prompt
#: byte-identical — the property the stability test pins.
UNCREATED = 0.0


class DeterministicFramer:
    """The lexicon, the grammar, and no model at all."""

    name = "deterministic"

    def frame(self, prompt: str, corpus_context: Optional[Mapping[str, Any]] = None, *,
              mode: InquiryMode = InquiryMode.EXPLORE,
              now: Optional[datetime] = None) -> InquiryFrame:
        corpus = to_corpus_context(corpus_context)
        notes: List[str] = []
        refusals: List[Refusal] = []

        image_hits = lexicon.detect_cues(prompt)
        inquiry_hits = lexicon.detect_inquiry_cues(prompt)
        corpus_terms = lexicon.detect_corpus_terms(prompt)
        demands_raw = lexicon.detect_demands(prompt)
        known_unresolved = lexicon.detect_known_unresolved(prompt)
        human_only = lexicon.detect_human_only_requests(prompt)

        attentions = _attentions(prompt, image_hits, inquiry_hits, corpus_terms)
        demands = _demands(prompt, demands_raw, known_unresolved)
        actions, action_notes = _actions(prompt, image_hits, inquiry_hits, corpus)
        notes.extend(action_notes)

        for request in human_only:
            refusals.append(Refusal(
                kind=RefusalKind.HUMAN_ACTION_REQUIRED,
                what=request["action"],
                why=request["why"],
                detail=[f"the user said “{cue}”" for cue in request["matched"]]))
            notes.append(f"the prompt asks for '{request['action']}'. It is recorded and not "
                         f"proposed: only a person may author it.")

        unresolved = _unresolved(prompt, known_unresolved)
        remainder = _remainder(demands)

        if not actions:
            notes.append("no grammar-valid act was proposed. Nothing here serves this prompt, "
                         "and an empty proposal list is the honest answer rather than a keyword "
                         "guess dressed as a plan.")
        if not corpus.post_ids:
            notes.append("no corpus was named. The frame reads the words only; ids, titles and "
                         "counts would be the whole of what it could hold about images anyway.")

        return InquiryFrame(
            inquiry_id=mint_inquiry_id(prompt, now=now),
            prompt=prompt,
            mode=mode,
            attentions=attentions,
            epistemic_demands=demands,
            proposed_actions=actions,
            unresolved_terms=unresolved,
            semantic_remainder=remainder,
            requested_output=lexicon.detect_requested_output(prompt),
            corpus_context=corpus,
            provenance=FrameProvenance(
                producer=PRODUCER,
                framer_kind="deterministic",
                model=None,
                role=None,
                prompt_sha256=prompt_hash(prompt),
                grammar_version=grammar.SCHEMA_VERSION,
                lexicon_version=lexicon.SCHEMA_VERSION,
                framed_at=utc_now_iso(now),
                model_calls=0),
            refusals=refusals,
            notes=notes)


# ── attentions ───────────────────────────────────────────────────────────────

def _span(prompt: str, term: str) -> Optional[tuple]:
    at = str(prompt).lower().find(str(term).lower())
    return (at, at + len(term)) if at >= 0 else None


def _attention(prompt: str, term: str, category: str, roles: List[str]) -> Attention:
    return Attention(term=term, said=f"the user said “{term}”", span=_span(prompt, term),
                     category=category, action_roles=list(roles))


def _attentions(prompt: str, image_hits, inquiry_hits, corpus_terms) -> List[Attention]:
    """Everything the prompt was keyed on, in one list, each attributed to the prompt.

    Order is lexicon order, then inquiry order, then corpus terms — fixed, so two framings of one
    prompt produce the same list rather than the same set.
    """
    out: List[Attention] = []
    for hit in image_hits:
        out.append(_attention(prompt, hit["matched"][0], hit["key"], hit["proposes"]))
    for hit in inquiry_hits:
        out.append(_attention(prompt, hit["matched"][0], hit["category"], hit["proposes"]))
    for term in corpus_terms:
        out.append(_attention(prompt, term, "corpus_selector", []))
    return out


# ── demands ──────────────────────────────────────────────────────────────────

def _demands(prompt: str, raw: List[Dict[str, Any]],
             known_unresolved: List[Dict[str, str]]) -> List[EpistemicDemand]:
    """One demand per cue that fired, plus one per declared-unoperationalisable phrase.

    THE RULE THAT MATTERS: a term's kind comes from the cue block it fired, and the blocks are
    disjoint. `sensuality` is in the interpretive block and cannot arrive at `measurable` by any
    route, including the route that would be easiest to take — noticing that fold geometry bears
    on it and treating 'bears on' as 'is'.
    """
    out: List[EpistemicDemand] = []
    seen = set()
    for row in raw:
        key = (row["kind"], row["term"])
        if key in seen:
            continue
        seen.add(key)
        out.append(EpistemicDemand(clause=row["clause"], term=row["term"],
                                   kind=DemandKind(row["kind"]), why=row["why"]))
    for row in known_unresolved:
        key = ("unresolved", row["term"])
        if key in seen:
            continue
        seen.add(key)
        out.append(EpistemicDemand(clause=lexicon.clause_containing(prompt, row["term"]),
                                   term=row["term"], kind=DemandKind.UNRESOLVED, why=row["why"]))
    return out


# ── proposed acts ────────────────────────────────────────────────────────────

def _actions(prompt: str, image_hits, inquiry_hits,
             corpus: CorpusContext) -> tuple:
    """Grammar-valid acts, in a fixed order, every one of them `proposed`.

    Ids are `act_1…act_n` per frame rather than from a process-wide counter: the frame must be
    byte-identical across two framings of one prompt, and a global sequence would make the second
    framing differ in a way that has nothing to do with what was asked.
    """
    raw: List[Dict[str, Any]] = []
    notes: List[str] = []

    if corpus.post_ids:
        raw.append({
            "type": "find_parts",
            "source": "system",
            "intent": "open the named images into material you can cite",
            "payload": {"reason": f"{len(corpus.post_ids)} image"
                                  f"{'' if len(corpus.post_ids) == 1 else 's'} were named and "
                                  f"nothing has been opened into parts"},
            "provenance": _provenance(prompt, "bootstrap", []),
        })

    for hit in image_hits:
        for proposal in hit["proposes"]:
            act = _act_from_proposal(prompt, proposal, hit["key"], hit["matched"])
            if act is not None:
                raw.append(act)

    for hit in inquiry_hits:
        if not hit["proposes"]:
            # A cue that proposes nothing is not a gap — `speculation` fires on "hybrid" and
            # there is no act that measures what does not exist. The note says so, because an
            # attention with no act beside it otherwise reads as something that was forgotten.
            notes.append(f"'{hit['matched'][0]}' was read as {hit['category']} and proposes no "
                         f"act: {hit['why']}")
            continue
        for proposal in hit["proposes"]:
            act = _act_from_proposal(prompt, proposal, hit["category"], hit["matched"])
            if act is not None:
                raw.append(act)

    writing_mode = lexicon.detect_writing_mode(prompt)
    if writing_mode:
        raw.append({
            "type": "start_manuscript",
            "source": "system",
            "intent": "begin writing from what has been marked",
            "payload": {"mode": writing_mode, "draft": "", "cited_percept_refs": [],
                        "insertion_mode": "unsaved", "reason": "you named a kind of writing"},
            "provenance": _provenance(prompt, "writing", [writing_mode]),
        })

    actions: List[Dict[str, Any]] = []
    for index, proposal in enumerate(raw, start=1):
        action = grammar.normalize_action(proposal, now=UNCREATED, action_id=f"act_{index}")
        if action is None:
            # A proposal this framer built itself and cannot validate is a lexicon bug, and it is
            # REPORTED. A planner that silently drops its own output is how such a bug stays
            # invisible for a month.
            notes.append(f"a proposed '{proposal.get('type')}' failed its own grammar and was "
                         f"dropped — this is a lexicon defect, not a refusal of the prompt")
            continue
        actions.append(action)
    return actions, notes


def _act_from_proposal(prompt: str, proposal: str, cue_key: str,
                       matched: List[str]) -> Optional[Dict[str, Any]]:
    """`field:fold` / `trace:gaze_address` / `connect:contrast` → a raw action."""
    family, _, role = proposal.partition(":")
    first = matched[0] if matched else cue_key
    hint = lexicon.side_hint_for(prompt, first)
    provenance = _provenance(prompt, cue_key, matched)
    reason = f"you said “{first}”"

    if family == "field":
        return {
            "type": "brush_field", "source": "system",
            "intent": "mark where this lives, in your own hand",
            "payload": {"field_role": role, "label": lexicon.label_from_cue(first, role, hint),
                        "target_hint": hint, "geometry_mode": "soft_field",
                        "color": lexicon.FIELD_COLOURS.get(role), "softness": 0.8,
                        "requires_refinement": True, "reason": reason},
            "provenance": provenance,
        }
    if family == "trace":
        return {
            "type": "trace_direction", "source": "system",
            "intent": "draw the direction, from and to",
            "payload": {"trace_role": role, "label": lexicon.label_from_cue(first, role, hint),
                        "from_hint": hint or "", "to_hint": "",
                        "geometry_mode": "vector" if role == "architectural_axis" else "curve",
                        "requires_user_anchor": True, "reason": reason},
            "provenance": provenance,
        }
    if family == "connect":
        return {
            "type": "connect_marks", "source": "system",
            "intent": "tie two marks together and say how they bear on each other",
            "payload": {"relation_role": role, "label": "", "source_refs": [], "target_refs": [],
                        "reason": reason},
            "provenance": provenance,
        }
    return None


def _provenance(prompt: str, cue_key: str, matched: List[str]) -> Dict[str, Any]:
    return {"planner": "inquiry/lexicon-v1", "promptExcerpt": _excerpt(prompt),
            "matched": list(matched), "cue": cue_key}


def _excerpt(prompt: str, max_len: int = 120) -> str:
    text = " ".join(str(prompt or "").split())
    return text if len(text) <= max_len else f"{text[:max_len - 1]}…"


# ── unresolved and remainder ─────────────────────────────────────────────────

def _unresolved(prompt: str, known: List[Dict[str, str]]) -> List[UnresolvedTerm]:
    """The declared-unoperationalisable phrases, then the salient words nothing covered.

    Two sources on purpose. The declared ones carry a considered reason somebody wrote down; the
    leftovers are the blunt general mechanism that catches vocabulary nobody anticipated. A frame
    with only the first would look complete on a prompt full of words it had never seen.
    """
    out: List[UnresolvedTerm] = [UnresolvedTerm(term=row["term"], why=row["why"]) for row in known]
    seen = {row["term"].lower() for row in known}
    for term in lexicon.leftover_terms(prompt):
        if term in seen:
            continue
        seen.add(term)
        out.append(UnresolvedTerm(
            term=term,
            why="no cue in the shared lexicon and no act in the Perceptual Action Grammar "
                "operationalises this word. It is carried unread rather than dropped."))
    return out


def _remainder(demands: List[EpistemicDemand]) -> List[SemanticRemainder]:
    """What the available measurements will not exhaust, even if all of them succeed.

    Every interpretive and imagined demand produces one. That is a rule and not a judgement call:
    a reading about a picture is never exhausted by measurements on it, and a thing that does not
    exist cannot be measured at all. Where the lexicon names contributing measurements they are
    listed — saying what DOES bear on `sensuality` is what makes refusing to call it measured a
    position rather than a shrug.
    """
    kinds = set(lexicon.always_remainder_kinds())
    out: List[SemanticRemainder] = []
    seen = set()
    for demand in demands:
        if demand.kind.value not in kinds or not demand.term:
            continue
        if demand.term.lower() in seen:
            continue
        seen.add(demand.term.lower())
        rule = lexicon.remainder_for(demand.term)
        if rule is not None:
            out.append(SemanticRemainder(
                term=demand.term, why=str(rule["why"]),
                contributing_measurements=list(rule.get("contributing_measurements", ()))))
        else:
            out.append(SemanticRemainder(
                term=demand.term,
                why=lexicon.remainder_why_for_kind(demand.kind.value),
                contributing_measurements=[]))
    return out
