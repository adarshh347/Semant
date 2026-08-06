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

WHAT "PERMITTED `//` ORCHESTRATION" MEANS — stated explicitly, because it read as an
ambiguity once and must not again. Invariant 5 permits generation to be constrained by
the author's operator definitions AND their `//` orchestration. That permission covers
orchestration WHOSE MEANING THE AUTHOR SUPPLIES. A `//` value that refers out to the
model's priors for its content is NOT permitted orchestration and never was: it is an
import wearing the author's syntax. `// voice: close third, past tense` is theirs;
`// voice: like Tolstoy` is the priors', and the author's own hand typing it does not
make its meaning theirs. See `_STYLE_BY_REFERENCE`.

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
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.services import role_registry
from backend.services.director.execution import ERROR, OK, UNAVAILABLE
from backend.services.llm_service import llm_service
from backend.services.writer import dsl, instrument, library, relations
from backend.services.writer import recall as recall_mod
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


async def _manuscript_author(manuscript_id: str) -> str:
    """The manuscript's declared author, or "" if it has not declared one.

    Empty is the normal case for everything written before W5, and `library.author_guard`
    treats absence as "nobody has said yet" rather than as a violation — see the note there.
    """
    try:
        from backend.services.manuscript_service import manuscript_collection
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        return (doc or {}).get("author") or ""
    except Exception:
        return ""


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
    required: Sequence[Dict[str, Any]] = (),
    cited: Sequence[Dict[str, str]] = (),
) -> Dict[str, str]:
    """The render contract as `{system, user}`. PURE — testable without a network.

    Every style-bearing line in the user prompt is the author's: operator bodies come
    from `as_evidence()`, orchestration values are the author's `//` notes verbatim, and
    `preceding_prose` is the author's committed manuscript. The scaffolding sentences
    this function adds are instructions ABOUT the author's material and never describe
    how prose should sound.

    `required` (W3) is the operators pulled in through `requires` edges. They are in the
    prompt as GROUNDING for this one span, and the prompt says so explicitly: they shape
    how the invoked operators read, they are not additional things to render. That
    distinction is what keeps composition sequential — one operator, one span — instead of
    quietly becoming the blended field that Tier 3 reserves.
    """
    orchestration = orchestration or {}
    arguments = arguments or {}
    parts: List[str] = []

    parts.append("THE AUTHOR'S OPERATORS — this is your entire evidence base.\n")
    for op in operators:
        parts.append(operator_registry.as_evidence(op))
        parts.append("")

    if required:
        parts.append(
            "GROUNDING THE AUTHOR HAS DECLARED THESE OPERATORS TO REQUIRE. Their meaning "
            "must be present in the passage for the invoked operators to read correctly. "
            "Do NOT render them as separate moments or give them their own span — this is "
            "one passage, and they condition it:"
        )
        parts.append("")
        for op in required:
            parts.append(operator_registry.as_evidence(op))
            parts.append("")

    if cited:
        # W9 — the author's OWN COMMITTED PROSE, verbatim, as grounding. This is the purest
        # material in the prompt: not a declaration about how to write, but writing they
        # already accepted into the book.
        #
        # It says STAY CONSISTENT WITH, not CONTINUE FROM or MATCH THE STYLE OF. The author
        # cited these passages to keep the new one from contradicting them; reading that as
        # "write more like this" would let committed prose act as a style reference, which
        # is the author's own voice arriving through a door that was not built for it — and
        # it would make the cited text an instruction the author never gave.
        parts.append(
            "PASSAGES THE AUTHOR HAS ALREADY COMMITTED AND ASKED YOU TO STAY CONSISTENT "
            "WITH. This is their own accepted prose, quoted exactly. Treat what it "
            "establishes as true, and do not contradict it. Do NOT continue it, retell it, "
            "quote it back, or take it as a style to imitate — render the directive below:"
        )
        parts.append("")
        for citation in cited:
            parts.append(f"[{citation['label']}]")
            parts.append(citation["text"])
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

#: Markers of an orchestration value whose meaning lives in the MODEL'S PRIORS rather than
#: in anything the author has declared.
#:
#: THE PRINCIPLE, stated exactly, because the surface symptom is easy to mistake for it.
#: The test is NOT "describes qualities vs names a corpus", and it is not "common noun vs
#: proper noun". It is GROUNDED-IN-THE-AUTHOR'S-ONTOLOGY vs IMPORTED-FROM-PRIORS. When the
#: author writes `// voice: close third, past tense`, every word is theirs and the model is
#: being instructed. When they write `// voice: like Tolstoy`, the word "Tolstoy" carries
#: no meaning the author has supplied — its entire content lives in the training priors, so
#: the model reaches in and renders a voice the author never defined. That is not a risky-
#: looking `//` constraint; it is precisely what invariant 5 forbids, and it is the writer's
#: analogue of a VLM narrating a region with no detector evidence under it.
#:
#: WHY THIS EXISTS AS CODE AND NOT ONLY AS AN INSTRUCTION. The system prompt states the rule
#: plainly, and the model was measured ignoring it: asked for "the ornate omniscience of a
#: 19th-century Russian novel", it complied, invented a Russian name, and addressed the
#: reader. Strengthening the prompt did not fix it. A wall the model can talk past is not a
#: wall, so the refusal is structural here, exactly as an undefined operator is. The prompt
#: keeps the rule too — it catches phrasings this list cannot.
#:
#: IT IS A HEURISTIC, AND IT IS TUNED TO OVER-REFUSE ON PURPOSE. The two failure directions
#: are not symmetric:
#:   · a FALSE POSITIVE is a loud, named refusal the author rephrases around — a shrug;
#:   · a FALSE NEGATIVE silently smuggles priors into the sacred canon — the cardinal sin,
#:     because nothing downstream can tell borrowed prose from the author's own.
#: So the list is deliberately broad, bare surnames included, and any UNDER-refusal found
#: later is a priority bug rather than a papercut. Over-refusal is the safe direction and
#: this list should be tuned aggressively toward it.
#: Phrase markers: emulation formulas, periods, movements, genres. A genre label is a
#: corpus reference wearing a common noun, which is why "noir" sits beside "like Tolstoy".
_PRIOR_PHRASES = (
    # explicit emulation
    "in the style of", "in the manner of", "in the vein of", "written like", "write like",
    "sounds like", "read like", "reminiscent of", "evoking", "channelling", "channeling",
    "pastiche", "homage", "à la ", "a la ", "-esque", "-ian prose", "riff on",
    # periods and movements
    "th-century", "th century", "st-century", "st century", "victorian", "edwardian",
    "modernist", "postmodern", "romantic era", "beat generation", "new journalism",
    # genres and schools
    "gothic", "noir", "hardboiled", "hard-boiled", "pulp", "penny dreadful", "mfa",
    "magical realism", "hard sci-fi", "space opera", "cozy mystery", "bodice ripper",
    "airport thriller", "literary fiction", "autofiction",
)

#: Bare surnames the model has a dense prior for. Held SEPARATELY from the phrases because
#: only these make a usable operator name: `tolstoy` → `#create tolstoy_voice` reads as an
#: invitation, whereas a fragment like "th-century" would produce `th_century_voice`, which
#: is noise. Not a canon and not meant as one — a sample of what actually gets typed into a
#: `//voice`. A name that is missing falls through to the prompt rule; see the over-refusal
#: note above, and treat any under-refusal as a bug worth fixing here.
_PRIOR_SURNAMES = (
    "tolstoy", "dostoev", "chekhov", "nabokov", "woolf", "joyce", "hemingway",
    "faulkner", "mccarthy", "morrison", "austen", "dickens", "kafka", "borges",
    "sebald", "didion", "carver", "munro", "ishiguro", "ferrante", "knausgaard",
    "proust", "beckett", "pynchon", "delillo", "atwood", "le guin", "tolkien",
)

_STYLE_BY_REFERENCE = _PRIOR_PHRASES + _PRIOR_SURNAMES

#: `avoid` is exempt: telling the model NOT to sound like something imports nothing.
_REFERENCE_CHECKED_KEYS = tuple(k for k in dsl.ORCHESTRATION_KEYS if k != "avoid")


def _suggested_operator_name(marker: str) -> str:
    """A name for the operator this reference WANTS to become.

    Only a SURNAME marker yields a stem — a phrase marker is a fragment ("th-century")
    and would make a worse suggestion than the neutral fallback.

    Deliberately not clever even then: `tolstoy` → `tolstoy_voice`, not an attempt at
    `tolstoyan`. English adjective formation off a surname has no correct general answer
    ("kafkaesque", "woolfian", "le guinian"?) and this only has to be a valid, obvious
    starting point the author will rename anyway. It must satisfy `operators.NAME_RE`.
    """
    if marker not in _PRIOR_SURNAMES:
        return "my_voice"
    stem = re.sub(r"[^a-z0-9]+", "_", marker.strip().lower()).strip("_")
    return f"{stem}_voice" if stem and stem[0].isalpha() else "my_voice"


def _style_by_reference(orchestration: Dict[str, str]) -> Optional[str]:
    """The refusal reason if a note's meaning lives in the priors, else None.

    THE REFUSAL IS GENERATIVE, and that is the point of it. It does not merely wall off
    `// voice: like Tolstoy` — it routes the author to `#create`, where the qualities they
    were reaching for become a declared, versioned operator they own and can re-render.
    They get the destination they wanted, by the path that keeps the canon theirs. The wall
    is an on-ramp to the ontology growing, not a dead end, and this is the mechanism behind
    "the language becomes more the author's own with every chapter".
    """
    for key in _REFERENCE_CHECKED_KEYS:
        value = orchestration.get(key) or ""
        lowered = value.lower()
        for marker in _STYLE_BY_REFERENCE:
            if marker in lowered:
                name = _suggested_operator_name(marker)
                return (
                    f"`// {key}: {value}` names something whose meaning lives in my priors, "
                    f"not in your ontology (\"{marker.strip()}\"). I cannot check it against "
                    f"your book, so I will not render from it — that would put prose in your "
                    f"manuscript that is not yours.\n\n"
                    f"Tell me what it means TO YOU instead — the remove, the sentence length, "
                    f"what the narrator is allowed to know — and it becomes an operator you "
                    f"own:\n"
                    f"    #create {name}: <the qualities, in your words>\n"
                    f"Then `/ {name}` renders it, versioned and auditable, and it is yours "
                    f"from that point on."
                )
    return None


def _thin_operator_warnings(operators: Sequence[Dict[str, Any]]) -> List[str]:
    """Operators whose `definition` and `rendering_intent` say the same thing.

    A WARNING, not a refusal — it is the author's ontology and they may have meant it. But
    it is worth saying, because it reliably produces the failure W4's gate hit live: an
    operator carrying one sentence twice gives the render nothing to work from but an
    instruction, and the likeliest thing to come back is that instruction. This is the
    calibration axis (plan §9) showing up where the author can act on it — the same reason
    an assemblage refuses outright, softened for operators that predate the rule.
    """
    out: List[str] = []
    for op in operators:
        definition = (op.get("definition") or "").strip()
        intent = (op.get("rendering_intent") or "").strip()
        if definition and intent and definition == intent:
            out.append(
                f"`{op.get('name')}` says the same thing for what it IS and for what should "
                f"happen when it fires. Operators that thin tend to get their own sentence "
                f"handed back — worth sharpening one of the two."
            )
    return out


def _author_refusal(found: Dict[str, Any], manuscript_author: str) -> Optional[str]:
    """I5 ACROSS AUTHORS (W5). An operator another person declared may not render here.

    W5 widens the evidence base from one project's ontology to the AUTHOR'S — across their
    books. That is still their own declared language, so it stays grounded. What it must not
    become is someone else's: an operator from another hand carries meaning this author never
    declared and cannot check against their own book, which is the priors violation with a
    human source rather than a statistical one.

    Checked here, before the model, for the same reason every other wall is: a refusal is
    cheaper and more certain than hoping the prompt holds.
    """
    for name, operator in found.items():
        reason = library.author_guard(operator.get("author", ""), manuscript_author)
        if reason:
            return f"`{name}` is not yours to render from. {reason}"
    return None


def _preflight(
    resolved: Dict[str, Any],
    names: Sequence[str],
    orchestration: Dict[str, str],
    manuscript_author: str = "",
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

    # I5 across authors — the W5 guardrail. Before the style wall, because an operator
    # from another hand is not a question about how the prose sounds.
    foreign = _author_refusal(resolved.get("found") or {}, manuscript_author)
    if foreign:
        return foreign

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


#: ROLES-001 — the JOB this actuator does. The model bound to it lives in `role_registry`
#: and is resolved LIVE on every render, so `SEMANT_ROLE_MANUSCRIPT_RENDERER_MODEL` is a
#: config change rather than a code edit.
ROLE = "manuscript_renderer"


async def _call_model(system: str, user: str) -> Tuple[str, Optional[str]]:
    """Groq, via the EXISTING `llm_service` client. Returns `(reply, model_name)`.

    TWO DIFFERENT THINGS ARE BORROWED HERE, and only one of them should be.

    The CLIENT is reused: it is a connection built from one API key, and a second one would
    be a second thing to configure for no gain.

    The MODEL is NOT taken from `llm_service` — it is resolved from this actuator's own
    role. Reading `llm_service.model` would bind manuscript prose to the `archivist` role
    (corpus summarisation), so rebinding the archivist would silently change how the
    author's book reads. Same default model today, different jobs, separately rebindable:
    that is the whole point of ROLES-001.

    The Groq SDK call is synchronous, so it goes to a worker thread: a render must not
    block the event loop the rest of the app runs on.
    """
    client = getattr(llm_service, "client", None)
    if client is None:
        raise RuntimeError("GROQ_API_KEY is not configured, so no passage can be rendered")
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


# ── the actuator ─────────────────────────────────────────────────────────────────

async def render_directive(
    project_id: str,
    directive: Directive,
    *,
    preceding_prose: str = "",
    manuscript_id: str = "",
    scene_id: str = "",
    run_id: str = "",
    manuscript_author: str = "",
    cited: Sequence[Dict[str, Any]] = (),
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

    # W3 — `requires` resolution. Follows ONLY `requires` edges, transitively, and only
    # from operators that actually resolved. Every name it returns is an operator the
    # author defined, so nothing ungrounded can enter this way (I5 holds by construction:
    # an edge target is an operator reference, never free text).
    ontology = await operator_registry.by_name(project_id)
    pulled_names, requires_diagnostics = relations.resolve_requires(
        [n for n in names if n in found], ontology
    )
    pulled = [ontology[n] for n in pulled_names if n in ontology]

    def _stamp(op: Dict[str, Any], source: str) -> Dict[str, Any]:
        return {
            "name": op.get("name"),
            "version": op.get("version"),
            "id": op.get("id"),
            # I4, the load-bearing half of W3. The author typed only the direct operators;
            # if the passage reads as it does partly because of what `requires` pulled in,
            # provenance has to say so. Naming only what was typed would be an audit trail
            # that lies by omission.
            "source": source,
            # W5 — where this operator came from, if it was imported. Lineage, recorded so a
            # passage made with a carried-over operator can say which library version it was
            # taken from; nothing reads it to fetch anything.
            "library_ref": op.get("library_ref"),
            "author": op.get("author") or None,
        }

    provenance: Dict[str, Any] = {
        "operators": (
            [_stamp(found[n], "direct") for n in names if n in found]
            + [_stamp(op, "pulled_via_requires") for op in pulled]
        ),
        "requested_operators": names,
        "pulled_operators": pulled_names,
        "intents": [{"key": n.key, "value": n.value} for n in notes if n.known and n.key],
        "directive": directive.raw,
        "directive_line": directive.line,
        "manuscript_id": manuscript_id,
        "scene_id": scene_id,
        "run_id": run_id,
        # W9, I4 — which committed passages this one was asked to stay consistent with.
        # Recorded whether or not the render succeeds, for the same reason the operators
        # are: what the author asked for is part of the record, not just what came back.
        "cited": recall_mod.citation_stamps(cited),
        "rendered_at": _now_iso(),
    }

    # Whose manuscript is this? Resolved here rather than trusted from the caller, so the
    # guard cannot be bypassed by a caller that simply omits it.
    if manuscript_id and not manuscript_author:
        manuscript_author = await _manuscript_author(manuscript_id)

    refusal = _preflight(resolved, names, orchestration, manuscript_author)
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
        required=pulled,
        cited=recall_mod.as_grounding(cited),
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
    # A dangling or cyclic `requires` edge does not fail the span — the author's DIRECT
    # request is still renderable — but it is never silent either. Same for an operator
    # thin enough that it is likely to echo.
    diagnostics = (
        list(requires_diagnostics)
        + _thin_operator_warnings([found[n] for n in names if n in found] + pulled)
        + diagnostics
    )

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
        intents=orchestration,
        extra={"chars": len(passage), "pulled_operators": pulled_names, "run_id": run_id,
               "directive": directive.raw},
    )
    return RenderResult(
        status=OK, text=passage, provenance=provenance,
        diagnostics=tuple(diagnostics), model=model,
    )
