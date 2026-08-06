"""
Semant Writer W1 — the manuscript DSL, and the `/` ÷ `//` wall.

THREE GESTURES, THREE LAYERS. They are deliberately kept apart:

  `#create <name>`  DEFINES an operator from the author's own description. It authors
                    the ontology; it renders nothing.
  `/ <operator>`    RENDERING DIRECTIVE. Invokes one operator, or a stack of them
                    (`/ threshold + interiority`), to render a span of prose.
  `// key: value`   ORCHESTRATION NOTE. Conditions generation and is INVISIBLE to the
                    output. Keys: goal / arc / priority / avoid / voice.

WHY TWO LAYERS AND NOT ONE SYNTAX. A single bleeding syntax would let the author's
staging notes drift into the prose — the model would eventually render "bring the reader
to the threshold" as a sentence instead of *doing* it. So `//` is a separate enforced
layer with its own parser, its own scope rule, and a leak check at the commit boundary
(`find_orchestration_leak`). Invariant 6 is the reason this module exists as a parser
rather than as a prompt convention.

SCOPE RULE. A `//` note is ACTIVE for every directive that follows it, until a later note
with the same key supersedes it. That is what "under active orchestration" means: the
author sets the staging once, then writes directives beneath it. Each parsed directive
carries a snapshot of the orchestration that was active where it sits, so a render call
never has to re-derive scope (and a re-render of directive 3 cannot silently pick up
staging the author wrote for directive 5).

UNKNOWN `//` KEYS ARE NOT SILENTLY HONOURED. A misspelt key is retained (the author's
words are never dropped on the floor) but marked `known=False` and excluded from the
render prompt, with a diagnostic. Silently feeding an unvalidated key into generation
would make the orchestration vocabulary a fiction.

This module is PURE: no database, no LLM, no I/O. It is a parser.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: The orchestration vocabulary. A `//` note outside this set is retained but inert.
#: W10 added `register`: which of the AUTHOR'S declared layers to foreground. It is a
#: `//` note like the rest, so it is stripped from the page (I6) and recorded to
#: provenance (I4) with no extra machinery — the wall already covers it.
ORCHESTRATION_KEYS: Tuple[str, ...] = (
    "goal", "arc", "priority", "avoid", "voice", "register",
)
_KNOWN = frozenset(ORCHESTRATION_KEYS)

# ── notation ─────────────────────────────────────────────────────────────────────
# Anchored at the START of a stripped line, always. A `//` inside a sentence (a URL, a
# dialogue tic) is prose and must stay prose — only a line that OPENS with the notation
# is notation. This is why every regex below begins with `^`.

_CREATE_RE = re.compile(r"^#create\s+(?P<name>[A-Za-z][\w-]*)\s*(?::\s*(?P<description>.*))?$")
_ORCH_RE = re.compile(r"^//\s*(?P<key>[A-Za-z_][\w-]*)\s*:\s*(?P<value>.*)$")
#: `/` but NOT `//` — the negative lookahead is the whole wall, expressed once.
_DIRECTIVE_RE = re.compile(r"^/(?!/)\s*(?P<body>.+)$")
_OPERATOR_RE = re.compile(r"^(?P<name>[A-Za-z][\w-]*)\s*(?:\((?P<argument>[^)]*)\))?$")

#: A `//` line that carries no `key: value` at all (`// just a thought`). Still
#: orchestration — it must never reach the page — but it conditions nothing.
_BARE_ORCH_RE = re.compile(r"^//\s*(?P<text>.*)$")


# ── parsed elements ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OperatorCall:
    """One operator named inside a directive, with the author's optional argument."""
    name: str
    argument: str = ""

    def describe(self) -> str:
        return f"{self.name}({self.argument})" if self.argument else self.name


@dataclass(frozen=True)
class Directive:
    """A `/` rendering directive: render a span by invoking these operators.

    `orchestration` is the snapshot of `//` notes active AT THIS LINE — not the block's
    final state. Rendering one directive therefore needs nothing but the directive.
    """
    line: int
    operators: Tuple[OperatorCall, ...]
    orchestration: Tuple["OrchestrationNote", ...] = ()
    raw: str = ""

    @property
    def operator_names(self) -> Tuple[str, ...]:
        return tuple(o.name for o in self.operators)


@dataclass(frozen=True)
class OrchestrationNote:
    """A `//` staging note. NEVER rendered — it conditions, it does not appear."""
    line: int
    key: str
    value: str
    known: bool = True
    raw: str = ""


@dataclass(frozen=True)
class CreateGesture:
    """`#create <name>: <description>` — authors an operator, renders nothing."""
    line: int
    name: str
    description: str = ""
    raw: str = ""


@dataclass(frozen=True)
class Prose:
    """A line of the author's own manuscript text. Not notation, never touched."""
    line: int
    text: str


@dataclass(frozen=True)
class ParsedBlock:
    """A manuscript block parsed into its ordered layers."""
    elements: Tuple[Any, ...] = ()
    diagnostics: Tuple[str, ...] = ()

    @property
    def directives(self) -> Tuple[Directive, ...]:
        return tuple(e for e in self.elements if isinstance(e, Directive))

    @property
    def notes(self) -> Tuple[OrchestrationNote, ...]:
        return tuple(e for e in self.elements if isinstance(e, OrchestrationNote))

    @property
    def creates(self) -> Tuple[CreateGesture, ...]:
        return tuple(e for e in self.elements if isinstance(e, CreateGesture))

    @property
    def prose(self) -> Tuple[Prose, ...]:
        return tuple(e for e in self.elements if isinstance(e, Prose))


# ── the parser ───────────────────────────────────────────────────────────────────

def _parse_directive_body(body: str, line: int) -> Tuple[Tuple[OperatorCall, ...], List[str]]:
    """`threshold(the door) + interiority` → two OperatorCalls. Malformed parts diagnose."""
    calls: List[OperatorCall] = []
    problems: List[str] = []
    for part in body.split("+"):
        part = part.strip()
        if not part:
            continue
        m = _OPERATOR_RE.match(part)
        if not m:
            problems.append(f"line {line}: cannot read '{part}' as an operator invocation")
            continue
        calls.append(OperatorCall(name=m.group("name"), argument=(m.group("argument") or "").strip()))
    if not calls and not problems:
        problems.append(f"line {line}: a `/` directive names no operator")
    return tuple(calls), problems


def parse_block(text: str) -> ParsedBlock:
    """A manuscript block → an ordered sequence of gestures, directives, notes and prose.

    Order is preserved exactly, so the block round-trips and provenance can point at a
    line. Orchestration scope is folded in as we go (see the module docstring).
    """
    elements: List[Any] = []
    diagnostics: List[str] = []
    active: Dict[str, OrchestrationNote] = {}

    for i, raw_line in enumerate((text or "").splitlines(), start=1):
        stripped = raw_line.strip()

        if not stripped:
            elements.append(Prose(line=i, text=""))
            continue

        # `//` FIRST — before `/` — so orchestration can never be read as a directive.
        if stripped.startswith("//"):
            m = _ORCH_RE.match(stripped)
            if m:
                key = m.group("key").strip().lower()
                known = key in _KNOWN
                note = OrchestrationNote(
                    line=i, key=key, value=m.group("value").strip(), known=known, raw=stripped
                )
                if known:
                    active[key] = note
                else:
                    diagnostics.append(
                        f"line {i}: '{key}' is not an orchestration key "
                        f"({', '.join(ORCHESTRATION_KEYS)}) — retained but it conditions nothing"
                    )
            else:
                bare = _BARE_ORCH_RE.match(stripped)
                note = OrchestrationNote(
                    line=i, key="", value=(bare.group("text").strip() if bare else ""),
                    known=False, raw=stripped,
                )
                diagnostics.append(
                    f"line {i}: `//` note without a `key: value` — kept out of the prose, "
                    f"but it conditions nothing"
                )
            elements.append(note)
            continue

        if stripped.startswith("#create"):
            m = _CREATE_RE.match(stripped)
            if m:
                elements.append(CreateGesture(
                    line=i, name=m.group("name"),
                    description=(m.group("description") or "").strip(), raw=stripped,
                ))
            else:
                diagnostics.append(f"line {i}: `#create` needs a name — `#create <name>: <description>`")
                elements.append(Prose(line=i, text=raw_line))
            continue

        m = _DIRECTIVE_RE.match(stripped)
        if m:
            calls, problems = _parse_directive_body(m.group("body"), i)
            diagnostics.extend(problems)
            if calls:
                elements.append(Directive(
                    line=i, operators=calls,
                    orchestration=tuple(active[k] for k in ORCHESTRATION_KEYS if k in active),
                    raw=stripped,
                ))
            else:
                # Unreadable notation is NOT quietly demoted to prose: that would put a
                # `/` line on the page. It is dropped, loudly, into diagnostics.
                elements.append(OrchestrationNote(line=i, key="", value="", known=False, raw=stripped))
            continue

        elements.append(Prose(line=i, text=raw_line))

    return ParsedBlock(elements=tuple(elements), diagnostics=tuple(diagnostics))


def active_orchestration(directive: Directive) -> Dict[str, str]:
    """The KNOWN staging for a directive, as the flat map the render prompt consumes."""
    return {n.key: n.value for n in directive.orchestration if n.known and n.key}


# ── the wall, enforced at the boundary ───────────────────────────────────────────

def is_notation(line: str) -> bool:
    """Is this line DSL notation rather than prose? The single definition of the wall."""
    s = (line or "").strip()
    return bool(s.startswith("//") or _DIRECTIVE_RE.match(s) or s.startswith("#create"))


def scrub_notation(text: str) -> str:
    """Remove every notation line from a rendered passage.

    Belt to `find_orchestration_leak`'s braces: the leak check REFUSES a passage, this
    makes sure that nothing which slipped past a check can reach the page regardless.
    """
    kept = [ln for ln in (text or "").splitlines() if not is_notation(ln)]
    return "\n".join(kept).strip()


def _normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", (s or "").lower()).strip()


def _leak_reason(line: str, values: Dict[str, "OrchestrationNote"]) -> Optional[str]:
    """Why this ONE line is a leak, or None if it is honest prose.

    THREE failure modes, and only three — the check is deliberately about NOTATION and
    RESTATEMENT, never about semantics:

      1. notation survived — a `//` or `/` line is sitting in the passage;
      2. the model RESTATED a staging note verbatim as a line of prose;
      3. the model NARRATED its instructions ("Goal: bring the reader to the threshold").

    What this does NOT flag: prose that fulfils the goal. A `//goal: reach the threshold`
    producing a passage about a threshold is the system working. Flagging shared
    vocabulary would make orchestration unusable, so only a whole-line verbatim echo or
    an explicit `key:` preamble counts.
    """
    s = (line or "").strip()
    if not s:
        return None
    if is_notation(s):
        return f"orchestration notation reached the prose: {s!r}"
    norm = _normalise(s)
    if norm and norm in values:
        return f"orchestration note restated as prose: {s!r} (echoes `// {values[norm].key}`)"
    head = s.split(":", 1)[0].strip().lower()
    if ":" in s and head in _KNOWN and len(head) + 1 < len(s):
        return f"orchestration key narrated as prose: {s!r}"
    return None


def find_orchestration_leak(text: str, notes: Sequence[OrchestrationNote] = ()) -> List[str]:
    """Every way `//` content has reached the prose. Empty list == clean."""
    values = {_normalise(n.value): n for n in notes if n.value}
    return [r for ln in (text or "").splitlines() if (r := _leak_reason(ln, values))]


def strip_orchestration(
    text: str, notes: Sequence[OrchestrationNote] = ()
) -> Tuple[str, List[str]]:
    """Drop every leaking line. Returns `(clean_text, reasons)`.

    The outbound half of the wall: `find_orchestration_leak` says what went wrong,
    this returns prose that no longer has it in. A passage reduced to nothing by this
    is a refusal at the caller — there was no prose, only restated staging.
    """
    values = {_normalise(n.value): n for n in notes if n.value}
    kept: List[str] = []
    reasons: List[str] = []
    for ln in (text or "").splitlines():
        reason = _leak_reason(ln, values)
        if reason:
            reasons.append(reason)
        else:
            kept.append(ln)
    return "\n".join(kept).strip(), reasons
