"""
Semant Writer W7 — the alignment reading: the honest editor.

Rendering answers "produce prose from my declared operators and orchestration." This
answers its mirror: **where does this prose diverge from what I declared?** It takes a
passage that carries provenance and reports, span by span, where the prose fails to honour
the standard the author set — citing the specific declared element each flag rests on.

IT NEVER PRODUCES OR EDITS PROSE. There is no rewrite path in this module, no suggested
replacement, no scene and no block. It diagnoses; the author acts, and the only forward
action is going back through the render loop under adjusted orchestration.

THE TASTE WALL — the load-bearing decision, and the reason this is not a generic editor.

Every AI writing assistant critiques against a generic notion of good prose. That is priors
deciding what the author's writing should be, which is the fabrication this project spent
five gates refusing. The hard question is whether a taste-free critique is even possible: to
judge "this reads melodramatic despite `//avoid melodrama`", the model uses its own notion
of melodrama, and that notion is priors.

The answer is yes, on one precise line:

    The model may use its linguistic competence to MEASURE CONFORMANCE TO A TERM THE
    AUTHOR DECLARED. It may not introduce a term of its own.

Recognising melodrama is the detector; deciding melodrama is unwanted is the author's
`//avoid`. That is exactly the vision side's split — a detector recognises a cat with its
trained competence, and the decision that cats matter here is the curator's marking. The
competence detects; the author sets the standard.

ENFORCED STRUCTURALLY, NOT REQUESTED POLITELY. `GROUNDING.md` records what happened the
last time a wall lived only in the prompt: the model was told plainly not to render style
by reference, and it did anyway. So every flag must name a declared element by id, and
`_ground_flags` DROPS any flag that does not — before the author ever sees it. The prompt
states the rule too, but the prompt is the net behind the guard, never the guard.

WHAT THE STANDARD IS. Exactly the passage's own provenance: its `//` intents, and its
operators' `rendering_intent` and `negative_examples`. Note what is absent — an operator's
`definition` is what the thing IS, which is the basis for RENDERING it; it is not a
standard the prose can be measured against. A passage is measured against what the author
said it should DO, and against nothing else, including operators it was not made from.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.services import role_registry
from backend.services.director.execution import ERROR, OK, UNAVAILABLE
from backend.services.llm_service import llm_service
from backend.services.writer import instrument

#: The reading's outcomes. Silence is a RESULT here, not a failure — see `_SYSTEM`.
ALIGNED = "aligned"          # measured against the standard, nothing diverges
FLAGGED = "flagged"          # at least one grounded divergence
THIN = "thin"                # the passage declared almost nothing to be checked against
NO_PROVENANCE = "no_provenance"   # not made by the loop; not ours to critique

#: ROLES-001 — the job this actuator does. Its own role, so rebinding the renderer cannot
#: silently change how the author's prose is judged, and vice versa.
ROLE = "alignment_reader"

#: The instrumentation events. The calibration signal (§5) is built from these.
READ = "alignment_read"
FLAG_DISMISSED = "alignment_flag_dismissed"
FLAG_ACTED = "alignment_flag_acted"

_RESPONSE_CONTRACT = (
    '{"flags": [{"element": "<one of the element ids listed above>", '
    '"span": "<the exact words from the passage>", '
    '"divergence": "<how those words fail that element>"}]}'
)


@dataclass(frozen=True)
class AlignmentResult:
    """What one reading hands back. Diagnostics only — there is no `text` field, ever."""
    status: str = ALIGNED
    flags: Tuple[Dict[str, Any], ...] = ()
    measured_against: Tuple[Dict[str, Any], ...] = ()
    detail: str = ""
    diagnostics: Tuple[str, ...] = ()
    model: Optional[str] = None

    @property
    def has_flags(self) -> bool:
        return bool(self.flags)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── the declared standard ────────────────────────────────────────────────────

def declared_elements(
    provenance: Dict[str, Any],
    operators_by_name: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """The passage's provenance → the elements it may be measured against.

    Exactly three kinds, and the omission is deliberate:

      `intent:<key>`          a `//` note the author set for this passage
      `operator:<name>:intent`      what the author said the operator should DO
      `operator:<name>:not`         the operator's own authored "this is NOT it"

    An operator's DEFINITION is not here. A definition says what the thing is, which is the
    basis for rendering it; it is not a standard the prose can diverge from. Measuring prose
    against a definition would slide straight back into "does this read like the idea?",
    which is taste wearing a citation.
    """
    elements: List[Dict[str, Any]] = []

    for intent in (provenance or {}).get("intents", []) or []:
        key, value = intent.get("key"), (intent.get("value") or "").strip()
        if key and value:
            elements.append({
                "id": f"intent:{key}",
                "kind": "intent",
                "key": key,
                "declared": value,
                # `avoid` is the sharpest case: the author named something they do not want,
                # so a flag against it is the least ambiguous kind this reading can make.
                "polarity": "avoid" if key == "avoid" else "toward",
            })

    for stamp in (provenance or {}).get("operators", []) or []:
        name = stamp.get("name")
        operator = operators_by_name.get(name) or {}
        version = stamp.get("version")

        intent = (operator.get("rendering_intent") or "").strip()
        if intent:
            elements.append({
                "id": f"operator:{name}:intent",
                "kind": "operator_intent",
                "operator": name,
                "operator_version": version,
                "operator_id": operator.get("id"),
                "declared": intent,
                "polarity": "toward",
            })

        for i, negative in enumerate(operator.get("negative_examples") or []):
            text = str(negative).strip()
            if text:
                elements.append({
                    "id": f"operator:{name}:not:{i}",
                    "kind": "operator_negative_example",
                    "operator": name,
                    "operator_version": version,
                    "operator_id": operator.get("id"),
                    "declared": text,
                    "polarity": "avoid",
                })

    return elements


# ── the prompt contract (PURE — this is what the taste-wall test reads) ──────

_SYSTEM = (
    "You are reading one passage against ONE author's own declared standard, and you have "
    "no other standard available to you.\n"
    "\n"
    "You will be given a numbered list of DECLARED ELEMENTS. Each is something this author "
    "said about this passage — a staging note they wrote, or something they said one of "
    "their operators should do or should never be. Your entire job is to report where the "
    "prose diverges from THOSE elements.\n"
    "\n"
    "THE ONE RULE: every flag must name one of the listed element ids, and must assert only "
    "that the prose conforms to or diverges from THAT element's declared meaning. You are "
    "measuring conformance to the author's terms. You are not bringing terms of your own.\n"
    "\n"
    "So you MUST NOT raise:\n"
    "  - anything about sentence rhythm, length, variety or repetition unless an element "
    "declares it;\n"
    "  - word choice, stronger verbs, cutting adverbs, 'show don't tell', or any other "
    "craft advice — none of these are the author's declared standard;\n"
    "  - a quality score, a grade, or an overall impression of how good the writing is;\n"
    "  - anything you noticed that is genuinely worth saying but that no element covers. "
    "That last one is the hard case and the rule still holds: if no listed element covers "
    "it, it is not yours to say.\n"
    "\n"
    "SILENCE IS A CORRECT AND VALUED ANSWER. If the prose honours every element, return an "
    "empty list of flags. Do not manufacture a small nitpick to look useful — an invented "
    "flag is worse than saying nothing, because the author cannot tell it from a real one. "
    "Returning zero flags is the expected outcome for a passage that is doing what its "
    "author asked.\n"
    "\n"
    "Quote the exact words from the passage in `span` so the author can find what you mean. "
    "Do not suggest a replacement, a rewrite, or a fix — you diagnose only; what to do about "
    "it is the author's.\n"
    "\n"
    f"Answer with JSON only, in exactly this shape: {_RESPONSE_CONTRACT}"
)


def build_reading_prompt(passage: str, elements: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    """The reading contract as `{system, user}`. PURE — testable without a network.

    Every standard-bearing line is the author's: element bodies are their `//` notes and
    their operators' own words, verbatim. This function contributes no evaluative vocabulary
    of its own, and a test asserts that — which is why it is pure and separate from the call.
    """
    parts: List[str] = ["THE AUTHOR'S DECLARED ELEMENTS — your entire standard.\n"]

    for element in elements:
        if element["polarity"] == "avoid":
            frame = "the author said the prose should NOT be this"
        else:
            frame = "the author said the prose should do this"
        parts.append(f"[{element['id']}] ({frame})")
        parts.append(f"    {element['declared']}")
        parts.append("")

    parts.append("THE PASSAGE:")
    parts.append(passage.strip())
    parts.append("")
    parts.append(
        "Report only divergences from the elements above, each naming its element id. "
        "If the passage honours all of them, return an empty list."
    )
    return {"system": _SYSTEM, "user": "\n".join(parts)}


# ── the structural guard (the taste wall, enforced) ─────────────────────────

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def ground_flags(
    raw_flags: Sequence[Dict[str, Any]],
    elements: Sequence[Dict[str, Any]],
    passage: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Keep only the flags that rest on a declared element. Returns `(kept, diagnostics)`.

    TWO STRUCTURAL CHECKS, and both drop rather than repair:

      1. THE ELEMENT MUST BE ONE OF THE AUTHOR'S. A flag naming no element id, or an id
         that was not offered, is the model bringing a standard of its own. That is the
         exact thing §2 forbids, and it cannot be fixed by rewording — it is dropped.

      2. THE SPAN MUST BE IN THE PASSAGE. A quoted span that does not appear in the prose
         is a flag about text that does not exist. Whitespace is normalised before
         comparing, because a model reflowing a line is not the same as inventing one.

    Dropping is silent to the author and LOUD in the diagnostics: they should see a clean
    reading, and the operator of the system should be able to see how often the model tried
    to step outside the standard.
    """
    by_id = {e["id"]: e for e in elements}
    haystack = _normalise(passage)
    kept: List[Dict[str, Any]] = []
    diagnostics: List[str] = []

    for raw in raw_flags or []:
        if not isinstance(raw, dict):
            diagnostics.append("dropped a flag that was not an object")
            continue

        element_id = str(raw.get("element") or "").strip()
        element = by_id.get(element_id)
        if element is None:
            # The taste wall doing its work. Recorded with the text so the discipline is
            # observable rather than merely asserted.
            diagnostics.append(
                f"dropped an ungrounded flag: it named "
                f"{element_id or '(no element)'!r}, which is not one of the author's "
                f"declared elements"
            )
            continue

        span = str(raw.get("span") or "").strip()
        if span and _normalise(span) not in haystack:
            diagnostics.append(
                f"dropped a flag quoting text that is not in the passage: {span[:60]!r}"
            )
            continue

        kept.append({
            "element": element_id,
            "element_kind": element["kind"],
            "operator": element.get("operator"),
            "operator_version": element.get("operator_version"),
            "declared": element["declared"],
            "span": span,
            "divergence": str(raw.get("divergence") or "").strip(),
        })

    return kept, diagnostics


# ── the model call ───────────────────────────────────────────────────────────

async def _call_model(system: str, user: str) -> Tuple[str, Optional[str]]:
    """Groq, via the existing client, on this actuator's OWN role binding."""
    client = getattr(llm_service, "client", None)
    if client is None:
        raise RuntimeError("GROQ_API_KEY is not configured, so no reading can be made")
    model = role_registry.model_for(ROLE)

    def _blocking() -> str:
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            model=model,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content

    return await asyncio.to_thread(_blocking), model


def _parse(raw: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    try:
        data = json.loads((raw or "").strip())
    except (ValueError, TypeError):
        return [], ["the reading did not come back as JSON; no flags were taken from it"]
    if not isinstance(data, dict):
        return [], ["the reading came back as JSON that was not an object"]
    flags = data.get("flags")
    if not isinstance(flags, list):
        return [], []
    return flags, []


# ── the actuator ─────────────────────────────────────────────────────────────

async def read_alignment(
    project_id: str,
    passage: str,
    provenance: Dict[str, Any],
    operators_by_name: Dict[str, Dict[str, Any]],
) -> AlignmentResult:
    """Measure one passage against its own declared standard. Diagnoses; changes nothing.

    Returns `THIN` or `NO_PROVENANCE` rather than inventing something to say when there is
    no standard to measure against — see the module docstring on silence as a result.
    """
    elements = declared_elements(provenance, operators_by_name)

    if not (provenance or {}).get("operators") and not (provenance or {}).get("intents"):
        return AlignmentResult(
            status=NO_PROVENANCE,
            detail=(
                "You wrote this yourself — it carries no operators or staging notes, so "
                "there is no declared standard to read it against. Measuring it against "
                "operators it was not made from would be this system inventing a yardstick."
            ),
        )

    if not elements:
        return AlignmentResult(
            status=THIN,
            detail=(
                "Little declared intent to check against: this passage's operators say what "
                "they are but not what they should do, and no `//` notes were active. Give "
                "an operator a rendering intent, or stage the block, and there will be "
                "something to measure."
            ),
        )

    prompt = build_reading_prompt(passage, elements)

    try:
        raw, model = await _call_model(prompt["system"], prompt["user"])
    except RuntimeError as exc:
        return AlignmentResult(status=UNAVAILABLE, detail=str(exc),
                               measured_against=tuple(elements))
    except Exception as exc:
        return AlignmentResult(status=ERROR, detail=f"the reading failed: {exc}",
                               measured_against=tuple(elements))

    raw_flags, diagnostics = _parse(raw)
    flags, dropped = ground_flags(raw_flags, elements, passage)
    diagnostics.extend(dropped)

    await instrument.record(
        READ, project_id,
        operators=[e["operator"] for e in elements if e.get("operator")],
        extra={
            "flags": len(flags),
            "dropped": len(dropped),
            "elements": [e["id"] for e in elements],
            # The calibration signal (§5): which operator each flag cited. An operator whose
            # renders are repeatedly flagged against its own intent is miscalibrated, and
            # this is the record that will eventually be able to say so. Logged now, read
            # later — the corpus is not there yet.
            "flagged_operators": [f["operator"] for f in flags if f.get("operator")],
        },
    )

    return AlignmentResult(
        status=FLAGGED if flags else ALIGNED,
        flags=tuple(flags),
        measured_against=tuple(elements),
        detail="" if flags else (
            "Aligned — nothing here diverges from what you declared."
        ),
        diagnostics=tuple(diagnostics),
        model=model,
    )
