"""
HARNESS-001A — the attunement lexicon, read in Python.

The twin of the cue-matching half of `frontend/src/differential/attunementPlanner.js`, reading the
same `contracts/attunement-lexicon.v1.json`. Matching is character-for-character the same rule:
lowercase, substring, longest-cue-wins.

WHAT THIS MODULE IS NOT. It is not a perceiver. Nothing here looks at a picture, and nothing here
may be phrased as though it had. Every hit it returns is attributed to the PROMPT — "the user said
'fold'" — and the phrasing is not a stylistic preference: the moment a cue hit is described as a
detection, a keyword table has started reporting on an image it never opened.

THE BLOCKS, and why some are backend-only:

  · `lexicon`, `writing_cues`, `sides`   read by both runtimes. Frozen by the sculpture fixture.
  · `inquiry_cues`                       the shape of a QUESTION over a corpus — comparison,
                                         distinction, speculation. The frontend planner proposes
                                         marks on ONE image and has no use for them.
  · `demand_cues`                        what KIND of knowing a clause asks for.
  · `output_cues`, `corpus_terms`,       the rest of what framing needs and marking does not.
    `known_unresolved`, `remainder_rules`

Adding a backend-only block cannot change what the panel suggests, which is the property that let
the lexicon be shared at all without a frontend behaviour change.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import lexicon_contract

_L = lexicon_contract()

SCHEMA_VERSION: str = _L["schema_version"]

LEXICON: Tuple[Mapping[str, Any], ...] = tuple(_L["lexicon"])
WRITING_CUES: Tuple[Mapping[str, Any], ...] = tuple(_L["writing_cues"])
SIDES: Tuple[Mapping[str, Any], ...] = tuple(_L["sides"])
SIDE_WINDOW: int = int(_L["matching"]["side_window"])

INQUIRY_CUES: Tuple[Mapping[str, Any], ...] = tuple(_L["inquiry_cues"])
DEMAND_CUES: Tuple[Mapping[str, Any], ...] = tuple(_L["demand_cues"])
OUTPUT_CUES: Tuple[Mapping[str, Any], ...] = tuple(_L["output_cues"])
HUMAN_ONLY_REQUESTS: Tuple[Mapping[str, Any], ...] = tuple(_L["human_only_requests"])
CORPUS_TERMS: Tuple[str, ...] = tuple(_L["corpus_terms"])
KNOWN_UNRESOLVED: Tuple[Mapping[str, Any], ...] = tuple(_L["known_unresolved"])
REMAINDER_RULES: Mapping[str, Any] = _L["remainder_rules"]

FIELD_COLOURS: Mapping[str, str] = _L["field_colours"]
GROUND_ROLE_SUGGESTIONS: Mapping[str, str] = _L["ground_role_suggestions"]
LABEL_TEMPLATES: Mapping[str, Any] = _L["labels"]
SCULPTURE_FIXTURE: str = _L["fixtures"]["sculpture"]

_UNRESOLVED = _L["unresolved"]
UNRESOLVED_MIN_LENGTH: int = int(_UNRESOLVED["min_length"])
UNRESOLVED_MAX_TERMS: int = int(_UNRESOLVED["max_terms"])
STOPWORDS: frozenset = frozenset(_UNRESOLVED["stopwords"])

#: Letters, optionally hyphen-joined, so "fold-level" is one token. Splitting it would report
#: "level" on its own, which is a word the person never used in that sense.
_TOKEN = re.compile(r"[a-z]+(?:-[a-z]+)*")

#: Clause boundaries. A demand must carry the clause it came from, and a clause is what a reader
#: would point at — not the whole prompt, and not a five-word window.
_CLAUSE = re.compile(r"[,;:.!?\n]")


def _norm(text: Any) -> str:
    return str(text or "").lower()


def _word_cue_present(haystack: str, cue: str) -> bool:
    r"""`\bcue\b`, for the cues the contract lists under `word_cues`.

    Substring matching is right for the prefix cues the lexicon depends on ('illuminat' must
    catch 'illuminated'). It is wrong for a short cue that lives inside unrelated words: 'lit'
    fires inside "sensuality", 'gather' inside "together", 'arm' inside "warm". Each of those
    makes the frame say the user said a word they did not say.
    """
    return re.search(rf"\b{re.escape(_norm(cue))}\b", haystack) is not None


def match_cues(text: str, cues: Sequence[str],
               word_cues: Sequence[str] = ()) -> List[str]:
    """Which cues actually appear, longest-first so a longer phrase wins its substring.

    Identical to `matchCues` in the JS planner, including the drop rule: a cue contained by
    another matched cue is removed, so 'fold' does not also report itself when 'folding' matched.
    """
    haystack = _norm(text)
    present = [c for c in cues if c in haystack]
    present += [c for c in word_cues if _word_cue_present(haystack, c)]
    present.sort(key=len, reverse=True)
    return [c for c in present if not any(o != c and c in o for o in present)]


def all_hits(text: str, cues: Sequence[str]) -> List[str]:
    """Every cue present, WITHOUT the longest-wins drop.

    Used only for coverage — deciding whether a word in the prompt was accounted for by anything.
    'fold-level' is covered by the cue 'fold' even when the reported match is 'folding', and
    reporting it as an unresolved term because of a display rule would be a lie about what the
    lexicon knows.
    """
    haystack = _norm(text)
    return [c for c in cues if c in haystack]


def detect_cues(prompt: str) -> List[Dict[str, Any]]:
    """Every image-lexicon entry the prompt fires, in lexicon order (stable output)."""
    hits: List[Dict[str, Any]] = []
    for entry in LEXICON:
        matched = match_cues(prompt, entry["cues"], entry.get("word_cues", ()))
        if matched:
            hits.append({"key": entry["key"], "matched": matched,
                         "proposes": list(entry.get("proposes", ()))})
    return hits


def detect_inquiry_cues(prompt: str) -> List[Dict[str, Any]]:
    """Every inquiry-shape entry the prompt fires. Backend-only, in contract order."""
    hits: List[Dict[str, Any]] = []
    for entry in INQUIRY_CUES:
        matched = match_cues(prompt, entry["cues"], entry.get("word_cues", ()))
        if matched:
            hits.append({"key": entry["key"], "matched": matched,
                         "proposes": list(entry.get("proposes", ())),
                         "category": entry.get("attention_category", entry["key"]),
                         "why": entry.get("why", "")})
    return hits


def detect_writing_mode(prompt: str) -> Optional[str]:
    """The manuscript mode the prompt asks for, or None. Most specific wins over 'description'."""
    for entry in WRITING_CUES:
        if match_cues(prompt, entry["cues"], entry.get("word_cues", ())):
            return str(entry["mode"])
    return None


def detect_requested_output(prompt: str) -> Optional[str]:
    """The artefact the person asked for, or None. First match in contract order wins.

    None is a real answer and the common one: most prompts say what to look at without saying what
    to produce, and guessing 'article' from silence would put a deliverable in the frame that
    nobody requested.
    """
    for entry in OUTPUT_CUES:
        if match_cues(prompt, entry["cues"], entry.get("word_cues", ())):
            return str(entry["output"])
    return None


def detect_demands(prompt: str) -> List[Dict[str, Any]]:
    """Which KINDS of knowing the prompt asks for, and on which words.

    Returns one row per (kind, matched cue), each carrying the clause it was found in — the
    directive's requirement that a demand carry its clause, not a bare word. A word can only
    contribute to one kind: the cue lists are disjoint by construction, and a term that genuinely
    belongs to two kinds is a lexicon bug worth seeing rather than a merge worth performing.
    """
    out: List[Dict[str, Any]] = []
    for entry in DEMAND_CUES:
        for cue in match_cues(prompt, entry["cues"], entry.get("word_cues", ())):
            out.append({"kind": str(entry["kind"]), "term": cue,
                        "clause": clause_containing(prompt, cue),
                        "why": str(entry.get("why", ""))})
    return out


def detect_corpus_terms(prompt: str) -> List[str]:
    """Words naming what the corpus IS. Not unresolved, and not anything visible in a picture."""
    return match_cues(prompt, CORPUS_TERMS)


def detect_known_unresolved(prompt: str) -> List[Dict[str, str]]:
    """Declared-unoperationalisable phrases present in the prompt, with the declared reason.

    DECLARED, not inferred, and the distinction is the honest part: these are phrases somebody
    decided nothing can serve, written down with why. The general mechanism — a salient word no
    cue covered — is `leftover_terms`.
    """
    lowered = _norm(prompt)
    return [{"term": str(row["phrase"]), "why": str(row["why"])}
            for row in KNOWN_UNRESOLVED if str(row["phrase"]).lower() in lowered]


def detect_human_only_requests(prompt: str) -> List[Dict[str, Any]]:
    """Acts the prompt ASKS FOR that only a person may author.

    The request is returned so a framer can record it. Recording rather than erasing is the whole
    behaviour: somebody asked for a counter-reading, and a frame that simply omitted the act would
    make the asking disappear along with it.
    """
    out: List[Dict[str, Any]] = []
    for entry in HUMAN_ONLY_REQUESTS:
        matched = match_cues(prompt, entry["cues"], entry.get("word_cues", ()))
        if matched:
            out.append({"action": str(entry["action"]), "matched": matched,
                        "why": str(entry.get("why", ""))})
    return out


def clause_containing(prompt: str, cue: str) -> str:
    """The clause the cue sits in, verbatim from the prompt (original case, trimmed)."""
    text = str(prompt or "")
    at = _norm(text).find(_norm(cue))
    if at < 0:
        return text.strip()
    start = 0
    end = len(text)
    for match in _CLAUSE.finditer(text):
        if match.start() < at:
            start = match.end()
        elif match.start() >= at + len(cue):
            end = match.start()
            break
    return text[start:end].strip()


def side_hint_for(prompt: str, cue: str) -> str:
    """The side words nearest a cue, as a plain phrase, or ''.

    A HINT and nothing else: no geometry is derived from it and it never becomes a box.
    """
    text = _norm(prompt)
    cue_l = _norm(cue)
    at = text.find(cue_l)
    if at < 0:
        return ""
    window = text[max(0, at - SIDE_WINDOW):min(len(text), at + len(cue_l) + SIDE_WINDOW)]
    found = [str(side["key"]) for side in SIDES
             if any(c in window for c in side["cues"])]
    return " / ".join(found) if found else ""


def _every_cue() -> List[str]:
    """Every cue string in every block — the coverage vocabulary."""
    cues: List[str] = []
    for block in (LEXICON, WRITING_CUES, INQUIRY_CUES, DEMAND_CUES, OUTPUT_CUES):
        for entry in block:
            cues.extend(entry["cues"])
            cues.extend(entry.get("word_cues", ()))
    cues.extend(CORPUS_TERMS)
    for entry in HUMAN_ONLY_REQUESTS:
        cues.extend(entry["cues"])
        cues.extend(entry.get("word_cues", ()))
    for row in KNOWN_UNRESOLVED:
        cues.append(str(row["phrase"]))
    return cues


_COVERAGE_CUES: Tuple[str, ...] = tuple(_every_cue())


def leftover_terms(prompt: str) -> List[str]:
    """Salient words of the prompt that NO cue in any block accounted for.

    The general unresolved mechanism, and deliberately blunt. A term is salient when it is at
    least `min_length` characters and is not a stopword; it is accounted for when any cue that
    fired is a substring of it or it is a substring of any cue that fired.

    Being blunt is the point. A prompt full of vocabulary nothing knows should produce a frame
    that says so in as many words, rather than an empty proposal list a reader has to interpret.
    """
    covered = [c for c in all_hits(prompt, _COVERAGE_CUES)]
    out: List[str] = []
    for token in _TOKEN.findall(_norm(prompt)):
        if len(token) < UNRESOLVED_MIN_LENGTH or token in STOPWORDS or token in out:
            continue
        if any(cue in token or token in cue for cue in covered):
            continue
        out.append(token)
        if len(out) >= UNRESOLVED_MAX_TERMS:
            break
    return out


def remainder_for(term: str) -> Optional[Mapping[str, Any]]:
    """The named remainder rule for a term, or None.

    A rule says which measurements CONTRIBUTE to a meaning and states that they do not exhaust
    it. `sensuality` is the worked example and the reason the block exists: fold geometry bears
    on it, and the moment 'bears on' is allowed to become 'is', an interpretation has been
    promoted to a measurement by nothing more than a decomposition.
    """
    lowered = str(term or "").lower()
    for row in REMAINDER_RULES.get("named", ()):
        if str(row["term"]).lower() in lowered or lowered in str(row["term"]).lower():
            return row
    return None


def always_remainder_kinds() -> Tuple[str, ...]:
    return tuple(REMAINDER_RULES.get("always_remainder_kinds", ()))


def remainder_why_for_kind(kind: str) -> str:
    return str(REMAINDER_RULES.get("why_by_kind", {}).get(kind, ""))


def label_from_cue(matched_cue: str, role: str, hint: str) -> str:
    """The label a proposed act carries, built from the contract's templates."""
    side = f" ({hint})" if hint else ""
    rule = LABEL_TEMPLATES.get(role) or LABEL_TEMPLATES["default"]
    out = str(rule["template"]).replace("{cue}", matched_cue).replace("{side}", side)
    collapse = rule.get("collapse")
    if isinstance(collapse, (list, tuple)) and len(collapse) == 2:
        out = out.replace(collapse[0], collapse[1], 1)
    return out
