"""
Semant Writer W1 — the render actuator. The core of the executable document.

This is an ACTUATOR RUN, not a chat completion with a nice wrapper. It keeps the same
shape as every runner in `director/execution.py`:

  propose, never commit   — it returns a passage; it writes nothing to canon.
  refusal is a return     — `RenderResult(status=REFUSED, refusal=...)`. It never fills
                            the gap with plausible prose, and there is no path in this
                            module that produces text when it should have refused.
  provenance travels      — every result names the operators (with versions) and the `//`
                            intents that produced it.

THE AUTHOR'S-ONTOLOGY WALL (invariant 5), which is the load-bearing part.

`epistemics.py` builds a wall around image evidence: nothing may cross from `sourced`
into the image statuses, because a citation cannot be checked by looking harder at the
picture. The Writer's wall is the same wall transposed: the AUTHOR'S OWN LANGUAGE is the
only evidence base, and a generic prior cannot be checked against the author's book.

Enforced in the prompt CONTRACT, in three places that must stay in agreement:

  1. `build_render_prompt` is a pure function whose every style-bearing line comes from
     `operator_registry.as_evidence()` — i.e. from text the author typed. This module
     contains NO exemplar prose, no genre vocabulary, no style adjectives. A test reads
     the built prompt and asserts that, which is why the builder is pure and separate
     from the network call.
  2. An operator the author has not defined is a REFUSAL before any model is contacted
     (`_preflight`). Rendering an undefined operator from priors is the exact failure the
     wall exists to prevent, so it cannot even reach the model.
  3. The system prompt states the constraint as a prohibition with a required escape
     hatch: when the author's ontology does not cover what the directive asks for, the
     model must refuse and say what is missing rather than reach for what it knows.

THE `/` ÷ `//` WALL (invariant 6) is enforced on the way OUT: the model's text is passed
through `dsl.scrub_notation` and `dsl.find_orchestration_leak`, and a passage that is
nothing but leak becomes a refusal. `passages.accept` re-checks before committing, so the
guarantee holds even if a passage reaches canon by some path this module did not write.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.services.director.execution import ERROR, OK, UNAVAILABLE
from backend.services.llm_service import llm_service
from backend.services.writer import dsl, instrument
from backend.services.writer.dsl import Directive, OrchestrationNote
from backend.services.writer.operators import operator_registry

#: A refusal is not an error and not an empty result — it is the actuator's ANSWER.
#: The kernel's four statuses have no member for "it could have run and declined", and
#: collapsing this into `empty` would lose the reason, which is the only useful part.
REFUSED = "refused"

#: The one JSON contract the model may answer with. Exactly one field is non-empty.
_RESPONSE_CONTRACT = (
    '{"passage": "<the rendered prose, or empty string>", '
    '"refusal": "<why you cannot render it, or empty string>"}'
)


@dataclass(frozen=True)
class RenderResult:
    """What one render hands back. Mirrors `director.execution.ActuatorResult`."""
    status: str = OK
    text: str = ""
    refusal: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Tuple[str, ...] = ()
    model: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.status == OK and bool(self.text.strip())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── the prompt contract (PURE — no network, no db; this is what the wall test reads) ──

_SYSTEM = (
    "You render prose for one author, inside that author's own writing system.\n"
    "\n"
    "THE ONE RULE: the author's operator definitions below are the ONLY basis you may "
    "write from. They are not hints or seeds — they are the whole permitted evidence "
    "base, the way a citation is the whole permitted basis for a sourced claim.\n"
    "\n"
    "Therefore you MUST NOT:\n"
    "  - write in a voice, register or style the author has not declared here;\n"
    "  - import conventions from fiction you have read that the author did not ask for;\n"
    "  - fill a gap in the author's definitions with something that merely sounds right;\n"
    "  - invent a proper name, a place or a fact the author has not given you;\n"
    "\n"
    "STYLE BY REFERENCE IS AN IMPORT, AND YOU MUST REFUSE IT. There is a difference "
    "between an orchestration note that DESCRIBES a quality — 'close third, past tense', "
    "'short declaratives', 'no interiority until the last line' — and one that NAMES AN "
    "OUTSIDE BODY OF WORK: an author, a book, a school, a period, a genre ('like "
    "Hemingway', 'a 19th-century Russian novel', 'noir', 'lyrical MFA realism'). The "
    "first is the author's own language and you should follow it. The second asks you to "
    "reach for a corpus that is not this author's, which cannot be checked against this "
    "author's book — so REFUSE it, say which reference you cannot honour, and ask them to "
    "describe the qualities they want in their own words instead. This holds even though "
    "the author wrote the note themselves: they can instruct you with their language, not "
    "borrow someone else's.\n"
    "\n"
    "You must also not:\n"
    "  - restate, quote or narrate the orchestration notes — they stage the writing, they "
    "are not part of it, and no line of them may appear in your prose;\n"
    "  - emit any '/' or '//' notation.\n"
    "\n"
    "If the operators do not tell you enough to render what the directive asks for, or if "
    "the orchestration notes contradict each other or contradict the operators, REFUSE. "
    "Say plainly what is missing or what conflicts. A refusal with a reason is a correct "
    "and valued answer here; prose written past a gap is not, and hollow filler that "
    "gestures at the shape of a passage is the single worst thing you can return.\n"
    "\n"
    f"Answer with JSON only, in exactly this shape: {_RESPONSE_CONTRACT}\n"
    "Exactly one of the two fields is non-empty."
)


def build_render_prompt(
    operators: Sequence[Dict[str, Any]],
    orchestration: Optional[Dict[str, str]] = None,
    *,
    arguments: Optional[Dict[str, str]] = None,
    preceding_prose: str = "",
) -> Dict[str, str]:
    """The render contract as `{system, user}`. PURE — testable without a network.

    Every style-bearing line in the user prompt is the author's: operator bodies come
    from `as_evidence()`, orchestration values are the author's `//` notes verbatim, and
    `preceding_prose` is the author's committed manuscript. The scaffolding sentences
    this function adds are instructions ABOUT the author's material and never describe
    how prose should sound.
    """
    orchestration = orchestration or {}
    arguments = arguments or {}
    parts: List[str] = []

    parts.append("THE AUTHOR'S OPERATORS — this is your entire evidence base.\n")
    for op in operators:
        parts.append(operator_registry.as_evidence(op))
        parts.append("")

    if orchestration:
        parts.append(
            "ORCHESTRATION (the author's staging). It conditions HOW you render and never "
            "appears in the prose. Do not quote it, summarise it, or answer it directly:"
        )
        for key in dsl.ORCHESTRATION_KEYS:
            if orchestration.get(key):
                parts.append(f"  {key}: {orchestration[key]}")
        parts.append("")

    if preceding_prose.strip():
        parts.append(
            "THE MANUSCRIPT SO FAR (the author's committed prose — continue from it; it is "
            "also the author's language, so let it constrain you as the operators do):"
        )
        parts.append(preceding_prose.strip())
        parts.append("")

    invocation = []
    for op in operators:
        name = op.get("name", "")
        arg = arguments.get(name, "")
        invocation.append(f"{name}({arg})" if arg else name)
    parts.append(
        "THE DIRECTIVE: render one passage by applying "
        + " then ".join(f"`{i}`" for i in invocation)
        + "."
    )
    if len(operators) > 1:
        parts.append(
            "They are a stack: the passage is a single continuous piece of prose in which "
            "each operator does its work, not one paragraph per operator."
        )
    parts.append(
        "Render only the passage itself — no title, no preamble, no commentary, no "
        "explanation of what you did."
    )

    return {"system": _SYSTEM, "user": "\n".join(parts)}


# ── pre-flight: the refusals that need no model ──────────────────────────────────

#: Phrases that mark an orchestration note as STYLE BY REFERENCE — a request to render
#: from a corpus that is not this author's. Kept deliberately small and literal.
#:
#: WHY THIS EXISTS AS CODE AND NOT ONLY AS AN INSTRUCTION. The system prompt states the
#: rule plainly, and the model was measured ignoring it: asked for "the ornate omniscience
#: of a 19th-century Russian novel", it complied, invented a Russian name, and addressed
#: the reader — importing a whole tradition the author never wrote a word of. A wall that
#: the model can talk past is not a wall, so the refusal is made structural here, exactly
#: as an undefined operator is. The prompt keeps the rule (it catches phrasings this list
#: does not); this catches the ones the prompt does not.
#:
#: IT IS A HEURISTIC AND IT IS NOT COMPLETE. It will miss a bare author's name ("write it
#: Woolf") and it can fire on an author who genuinely uses one of these words about their
#: own writing. Both failures are survivable in the right direction: a miss falls back to
#: the prompt rule, and a false positive is a REFUSAL that names the offending phrase and
#: asks for a rephrase — recoverable, and never a silent change to the prose.
_STYLE_BY_REFERENCE = (
    "in the style of", "in the manner of", "written like", "write like", "sounds like",
    "reminiscent of", "channelling", "channeling", "pastiche", "homage to", "a la ",
    "à la ", "-esque", "esque,", "th-century", "th century", "st-century", "st century",
    "victorian", "edwardian", "modernist", "postmodern", "beat generation", "gothic",
    "noir", "hardboiled", "hard-boiled", "pulp", "penny dreadful", "mfa",
)

#: `avoid` is exempt: telling the model NOT to sound like something imports nothing.
_REFERENCE_CHECKED_KEYS = tuple(k for k in dsl.ORCHESTRATION_KEYS if k != "avoid")


def _style_by_reference(orchestration: Dict[str, str]) -> Optional[str]:
    """The refusal reason if a note asks for a style by reference, else None."""
    for key in _REFERENCE_CHECKED_KEYS:
        value = orchestration.get(key) or ""
        lowered = value.lower()
        for marker in _STYLE_BY_REFERENCE:
            if marker in lowered:
                return (
                    f"style by reference in `// {key}`: \"{value}\" points at a body of "
                    f"work outside your own (\"{marker.strip()}\"). That is an import of "
                    f"priors this system cannot check against your book, so it will not "
                    f"render from it. Describe the qualities you want in your own words — "
                    f"or make them an operator, which is what operators are for."
                )
    return None


def _preflight(
    resolved: Dict[str, Any],
    names: Sequence[str],
    orchestration: Dict[str, str],
) -> Optional[str]:
    """The refusal reason, or None to proceed. Cheap, certain, and before any spend."""
    if not names:
        return "this directive names no operator, so there is nothing to render with"

    missing = resolved.get("missing") or []
    if missing:
        plural = "operators" if len(missing) > 1 else "operator"
        return (
            f"undefined {plural}: {', '.join('`' + m + '`' for m in missing)}. "
            f"Define with `#create {missing[0]}: …` first — rendering it now would mean "
            f"inventing a voice you have not declared."
        )

    # The author's-ontology wall, made structural — see `_STYLE_BY_REFERENCE`.
    by_reference = _style_by_reference(orchestration)
    if by_reference:
        return by_reference

    # A structural contradiction the parser can see without a model: the directive
    # invokes what the staging forbids. The model would have to choose which of the
    # author's two instructions to disobey, and silently picking one is worse than saying so.
    avoid = (orchestration.get("avoid") or "").lower()
    if avoid:
        for name in names:
            if name.lower() in avoid:
                return (
                    f"contradictory orchestration: the directive invokes `{name}` while "
                    f"`// avoid` says \"{orchestration['avoid']}\". Resolve which one you "
                    f"mean — this cannot be rendered honestly as written."
                )
    return None


# ── the model call ───────────────────────────────────────────────────────────────

def _parse_model_reply(raw: str) -> Tuple[str, str, List[str]]:
    """Model text → `(passage, refusal, diagnostics)`. Tolerates a bare-prose reply."""
    diagnostics: List[str] = []
    text = (raw or "").strip()
    if not text:
        return "", "", ["the model returned nothing"]
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        diagnostics.append("model did not answer with JSON; its reply was read as the passage")
        return text, "", diagnostics
    if not isinstance(data, dict):
        return text, "", ["model returned JSON that was not an object"]
    return (
        str(data.get("passage") or "").strip(),
        str(data.get("refusal") or "").strip(),
        diagnostics,
    )


async def _call_model(system: str, user: str) -> Tuple[str, Optional[str]]:
    """Groq, via the EXISTING `llm_service` client. Returns `(reply, model_name)`.

    The kernel's client is reused rather than a second one built here — same key, same
    model choice, one place to change it. The Groq SDK call is synchronous, so it goes to
    a worker thread: a render must not block the event loop the rest of the app runs on.
    """
    client = getattr(llm_service, "client", None)
    if client is None:
        raise RuntimeError("GROQ_API_KEY is not configured, so no passage can be rendered")
    model = getattr(llm_service, "model", None)

    def _blocking() -> str:
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            model=model,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content

    return await asyncio.to_thread(_blocking), model


# ── the actuator ─────────────────────────────────────────────────────────────────

async def render_directive(
    project_id: str,
    directive: Directive,
    *,
    preceding_prose: str = "",
    manuscript_id: str = "",
    scene_id: str = "",
) -> RenderResult:
    """Fire one `/` directive under its active `//` orchestration.

    Returns a QUARANTINED passage or a refusal. Writes nothing anywhere (the usage
    record in `instrument` is write-behind and holds no prose).
    """
    names = list(directive.operator_names)
    orchestration = dsl.active_orchestration(directive)
    arguments = {o.name: o.argument for o in directive.operators if o.argument}
    notes: Tuple[OrchestrationNote, ...] = directive.orchestration

    resolved = await operator_registry.resolve(project_id, names)
    found = resolved["found"]

    provenance: Dict[str, Any] = {
        "operators": [
            {"name": n, "version": found[n].get("version"), "id": found[n].get("id")}
            for n in names if n in found
        ],
        "requested_operators": names,
        "intents": [{"key": n.key, "value": n.value} for n in notes if n.known and n.key],
        "directive": directive.raw,
        "directive_line": directive.line,
        "manuscript_id": manuscript_id,
        "scene_id": scene_id,
        "rendered_at": _now_iso(),
    }

    refusal = _preflight(resolved, names, orchestration)
    if refusal:
        await instrument.record(
            instrument.REFUSAL, project_id, operators=names,
            intents=orchestration, detail=refusal, extra={"stage": "preflight"},
        )
        return RenderResult(status=REFUSED, refusal=refusal, provenance=provenance)

    prompt = build_render_prompt(
        [found[n] for n in names],
        orchestration,
        arguments=arguments,
        preceding_prose=preceding_prose,
    )

    try:
        raw, model = await _call_model(prompt["system"], prompt["user"])
    except RuntimeError as exc:
        # The model is not configured — the writer's `unavailable`, not a refusal. The
        # distinction matters exactly as it does in the kernel: this is transient and
        # retryable, a refusal is a statement about the work.
        return RenderResult(status=UNAVAILABLE, refusal=str(exc), provenance=provenance)
    except Exception as exc:
        return RenderResult(
            status=ERROR, refusal=f"the render call failed: {exc}", provenance=provenance
        )

    provenance["model"] = model
    passage, model_refusal, diagnostics = _parse_model_reply(raw)

    if model_refusal and not passage:
        await instrument.record(
            instrument.REFUSAL, project_id, operators=names,
            intents=orchestration, detail=model_refusal, extra={"stage": "model"},
        )
        return RenderResult(
            status=REFUSED, refusal=model_refusal, provenance=provenance,
            diagnostics=tuple(diagnostics), model=model,
        )

    # Invariant 6, outbound: every leaking line is removed before the passage exists.
    passage, leaks = dsl.strip_orchestration(passage, notes)
    diagnostics.extend(leaks)

    if not passage.strip():
        reason = model_refusal or (
            "the model produced nothing that was not orchestration restated as prose"
        )
        await instrument.record(
            instrument.REFUSAL, project_id, operators=names,
            intents=orchestration, detail=reason, extra={"stage": "postflight"},
        )
        return RenderResult(
            status=REFUSED, refusal=reason, provenance=provenance,
            diagnostics=tuple(diagnostics), model=model,
        )

    await instrument.record(
        instrument.RENDER, project_id, operators=names,
        intents=orchestration, extra={"chars": len(passage)},
    )
    return RenderResult(
        status=OK, text=passage, provenance=provenance,
        diagnostics=tuple(diagnostics), model=model,
    )
