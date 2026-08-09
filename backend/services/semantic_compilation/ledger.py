"""
HARNESS-003A §2 — the source ledger: everything the council is allowed to read, addressably.

    the verbatim prompt          -> prompt clauses, with computed spans
    the accepted reading blocks  -> reading units, with their block ids and image refs

NO MODEL RUNS HERE. The ledger is a deterministic transform, and that is the point: it is the one
object every later pass is audited against, so a ledger a model produced would let the same mind
decide both what the sources were and whether it had covered them.

## Why the spans are computed and never asked for

A model asked for character offsets invents them with total confidence, and an invented span
renders in a UI as a highlight over words the person did not write. HARNESS-002A made this call for
claim pointers; the ledger makes it for the whole prompt. The splitter walks the prompt itself, so
`prompt[unit.span[0]:unit.span[1]] == unit.exact_quote` is a property a test can check on any input
rather than a promise about well-behaved output.

## Why splitting is structural rather than linguistic

The boundaries are punctuation a writer typed: sentence terminators, semicolons, dashes, newlines.
Not "whereas", not "but", not a parser's idea of a clause. Two reasons, and the second is the one
that matters:

  · a linguistic splitter is a model of English, and this repository refuses to hardcode a topic —
    hardcoding a grammar is the same mistake one level down;
  · a comma splice left inside one unit is HARMLESS, because the dissector's whole job is to emit
    several atoms from one unit. A boundary invented in the wrong place is not harmless: it cuts a
    quote in half, and the half that survives is a sentence the person did not write.

So the splitter errs toward larger units and lets the council do the semantic work.

## What is NOT in the ledger

Images, urls, post documents, the frame's derived readings, and the scene reading's summary
paragraph. The summary is excluded deliberately: it is the theorist's own restatement of its blocks,
and dissolving both would produce atoms that duplicate each other with nothing saying they are the
same content — which is exactly the `duplicate_of` disposition doing work it should never have had.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (SceneReading, SourceUnit, SourceUnitKind)

from . import ids

PRODUCER = "semantic_compilation/ledger-v1"

#: Boundaries a writer TYPED. `--` and the two dashes are in here because the rehearsal prompt used
#: them as sentence boundaries and a splitter that ignored them would have produced one unit out of
#: three separate observations.
_BOUNDARY = re.compile(r"(?:[.;?!]+|--+|[–—]+|\n+)")

#: A fragment shorter than this is punctuation or a stray token rather than a clause; it is merged
#: into the PREVIOUS unit rather than dropped, because dropping it would lose characters from the
#: prompt and the reassembly test exists to make that impossible.
MIN_CLAUSE_CHARS = 12

#: A ledger longer than this is a transcript. The overflow is REPORTED by the caller, never trimmed
#: silently — a truncated ledger would make the coverage audit pass by having less to cover.
MAX_UNITS = 200


def split_prompt(prompt: str) -> List[Tuple[int, int]]:
    """The prompt's clause spans, as `(start, end)` offsets into the prompt itself.

    Every returned span satisfies `prompt[start:end].strip() == prompt[start:end]` — the offsets
    point at the words and not at the whitespace around them, so a highlight lands on the clause.
    """
    spans: List[Tuple[int, int]] = []
    cursor = 0
    for match in _BOUNDARY.finditer(prompt):
        spans.append((cursor, match.start()))
        cursor = match.end()
    spans.append((cursor, len(prompt)))

    trimmed: List[Tuple[int, int]] = []
    for start, end in spans:
        while start < end and prompt[start].isspace():
            start += 1
        while end > start and prompt[end - 1].isspace():
            end -= 1
        if end > start:
            trimmed.append((start, end))

    # SHORT FRAGMENTS JOIN THE PREVIOUS UNIT rather than becoming units of their own. A three-word
    # aside is not a clause, and making it one gives the dissector a unit it can only ever mark
    # remainder — which reads downstream as an epistemic limit rather than as a splitting artifact.
    merged: List[Tuple[int, int]] = []
    for start, end in trimmed:
        if merged and (end - start) < MIN_CLAUSE_CHARS:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def prompt_units(prompt: str, *, inquiry_id: str) -> List[SourceUnit]:
    """One unit per prompt clause, each quoting the prompt exactly."""
    out: List[SourceUnit] = []
    for ordinal, (start, end) in enumerate(split_prompt(prompt)):
        quote = prompt[start:end]
        out.append(SourceUnit(
            source_unit_id=ids.source_unit_id(inquiry_id, SourceUnitKind.PROMPT_CLAUSE,
                                              "prompt", quote),
            kind=SourceUnitKind.PROMPT_CLAUSE, source_ref="prompt", exact_quote=quote,
            span=(start, end), ordinal=ordinal))
    return out


def reading_units(reading: Optional[SceneReading], *, inquiry_id: str,
                  start_ordinal: int = 0) -> List[SourceUnit]:
    """One unit per accepted reading block. The theorist's summary paragraph is NOT a unit.

    `span` is left unset: a block's text is its own whole string, and an offset into the summary
    would be an offset into a document the block was not taken from.
    """
    out: List[SourceUnit] = []
    for offset, block in enumerate(reading.blocks if reading else ()):
        text = (block.text or "").strip()
        if not text:
            continue
        out.append(SourceUnit(
            source_unit_id=ids.source_unit_id(inquiry_id, SourceUnitKind.READING_BLOCK,
                                              block.block_id, text),
            kind=SourceUnitKind.READING_BLOCK, source_ref=block.block_id, exact_quote=text,
            span=None, image_refs=[str(i) for i in block.image_refs],
            block_kind=block.kind.value, ordinal=start_ordinal + offset))
    return out


def build(prompt: str, reading: Optional[SceneReading], *,
          inquiry_id: str) -> Tuple[List[SourceUnit], List[str]]:
    """The whole ledger, plus the notes a caller should put on the pass receipt.

    De-duplicated by id, so a theorist that emits the same block twice contributes one unit — and
    the count a coverage audit works against is the number of distinct things that were said.
    """
    notes: List[str] = []
    clauses = prompt_units(prompt, inquiry_id=inquiry_id)
    blocks = reading_units(reading, inquiry_id=inquiry_id, start_ordinal=len(clauses))

    seen: Dict[str, SourceUnit] = {}
    collisions = 0
    for unit in [*clauses, *blocks]:
        if unit.source_unit_id in seen:
            collisions += 1
            continue
        seen[unit.source_unit_id] = unit
    units = list(seen.values())

    if collisions:
        notes.append(f"{collisions} source unit(s) repeated content already in the ledger and were "
                     f"merged into one. Two identical paragraphs are one thing that was said.")
    if reading is None:
        notes.append("no scene reading reached the ledger, so it holds the prompt only. Every atom "
                     "will be anchored to the person's own words.")
    elif not blocks:
        notes.append("the scene reading carried no blocks, so the ledger holds the prompt only. A "
                     "reading whose prose was never blocked cannot be dissolved without splitting "
                     "somebody else's paragraph.")
    if len(units) > MAX_UNITS:
        notes.append(f"the ledger holds {len(units)} units; the first {MAX_UNITS} are kept and the "
                     f"rest are reported rather than dissolved.")
        units = units[:MAX_UNITS]
    return units, notes


# ── reading the ledger ───────────────────────────────────────────────────────

def by_id(units: Sequence[SourceUnit]) -> Dict[str, SourceUnit]:
    return {u.source_unit_id: u for u in units}


def user_unit_ids(units: Sequence[SourceUnit]) -> set:
    """The units the person is answerable for. The attribution rule reads this."""
    return {u.source_unit_id for u in units if u.is_user_authored}


def digest_for_prompt(units: Sequence[SourceUnit]) -> List[Dict[str, Any]]:
    """What a dissection pass is shown. Ids, kinds, quotes — and no spans.

    The offsets are deliberately withheld: a model shown them will echo them back, and an echoed
    offset is indistinguishable from a computed one once it is in the payload.
    """
    return [{"source_unit_id": u.source_unit_id, "kind": u.kind.value,
             "source_ref": u.source_ref, "text": u.exact_quote,
             "author": "user" if u.is_user_authored else "scene_theorist",
             **({"block_kind": u.block_kind} if u.block_kind else {}),
             **({"images": list(u.image_refs)} if u.image_refs else {})}
            for u in units]


def reassemble(prompt: str, units: Sequence[SourceUnit]) -> str:
    """The prompt's clauses put back together with the separators between them.

    Exists for the test that proves the splitter loses nothing: every character of the prompt is
    either inside exactly one clause span or is a separator between two of them.
    """
    spans = [u.span for u in units if u.kind is SourceUnitKind.PROMPT_CLAUSE and u.span]
    out: List[str] = []
    cursor = 0
    for start, end in sorted(spans):
        out.append(prompt[cursor:start])
        out.append(prompt[start:end])
        cursor = end
    out.append(prompt[cursor:])
    return "".join(out)


__all__ = ["PRODUCER", "MIN_CLAUSE_CHARS", "MAX_UNITS", "split_prompt", "prompt_units",
           "reading_units", "build", "by_id", "user_unit_ids", "digest_for_prompt", "reassemble"]
