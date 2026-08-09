"""
HARNESS-003A §8 — loading the two frozen dissolution fixtures, and the three markers they need.

WHY THE FIXTURES LIVE ON THE TEST SIDE. No production source may contain a fixture's topic nouns, so
a fixture module under `backend/services/semantic_compilation/` would violate the rule by existing.
The frozen payloads are JSON here; this loader names no topic at all.

## Why there are markers, and why there are three of them

Every id in this lane is derived from content plus the inquiry id. None of them can be written down
when a fixture is authored, and hardcoding one would rot the moment a word changed:

    $UNIT:<n>       the nth source unit of the ledger, in ledger order. Ordinal rather than text
                    because a unit's identity is its exact quote, and repeating a whole clause of
                    the person's prompt inside the fixture would create a second copy of the source
                    that could drift from the first.
    $ATOM:<ref>     the atom the dissector emitted under its own local `ref`. Resolved AFTER the
                    dissection runs, because the atom id depends on the text, the kind and the
                    anchors the parser actually accepted.
    $CLAIM:<ref>    the claim the architect emitted under its own local `ref`. Same reason, one
                    pass later.

An unresolvable marker is left ALONE rather than removed. It then arrives at the next pass as an id
that does not exist and is refused there by name — which is the behaviour under test, not a loader
failure that would hide it.

## What this loader may not do

It may not repair a fixture. If a fixture's coverage omits a source unit, the pipeline reports
`coverage_failed`, and that is a fixture the tests can assert on rather than a bug in the loader.

PURE. No network, no database, no clock.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (ClaimNode, ModelReceipt, SceneReading,
                                                  SemanticAtom, SourceUnit)
from backend.services.semantic_compilation import ids, ledger as ledger_mod
from backend.services.semantic_compilation.architect import FrozenRelationArchitect
from backend.services.semantic_compilation.base import CompilationRequest, to_image_refs
from backend.services.semantic_compilation.dissector import FrozenSemanticDissector
from backend.services.semantic_compilation.dissolution import Council
from backend.services.semantic_compilation.operationalizer import FrozenEpistemicOperationalizer
from backend.services.semantic_compilation.theorist import FrozenSceneTheorist

FIXTURE_DIR = Path(__file__).resolve().parent / "semantic_dissolution"

#: The rehearsal shape, and a control that shares no noun, no cue and no capability pattern with it.
FIXTURES: Tuple[str, ...] = ("fold-rehearsal", "unrelated-weave")

UNIT_MARKER = "$UNIT:"
ATOM_MARKER = "$ATOM:"
CLAIM_MARKER = "$CLAIM:"

#: Frozen so a replay is a comparison. Every fixture run uses it; nothing in the lane reads a clock.
FROZEN_NOW = "2026-08-10T00:00:00+00:00"
FROZEN_INQUIRY = "inq_fixture0001"


def load(name: str) -> Dict[str, Any]:
    path = FIXTURE_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"no dissolution fixture named {name!r}; have {list(FIXTURES)}")
    return json.loads(path.read_text(encoding="utf-8"))


def topic_nouns() -> List[str]:
    """Every topic noun both fixtures declare. The generality scan's input."""
    words: List[str] = []
    for name in FIXTURES:
        for word in load(name).get("topic_nouns") or ():
            if word not in words:
                words.append(str(word))
    return words


def prompt_for(name: str) -> str:
    return load(name)["prompt"]


def images_for(name: str):
    return to_image_refs(load(name)["images"])


def reading_for(name: str, *, inquiry_id: str = FROZEN_INQUIRY) -> SceneReading:
    """The frozen theorist output, through the production theorist parser.

    Built by `FrozenSceneTheorist` rather than by hand, so the block ids the ledger anchors to are
    the ones the real parser mints — a fixture that constructed `ReadingBlock`s directly would test
    a reading the theorist could not produce.
    """
    result = FrozenSceneTheorist(load(name)["theorist_payload"]).read(
        prompt_for(name), images_for(name), inquiry_id=inquiry_id, now=FROZEN_NOW)
    return result.reading


def ledger_for(name: str, *, inquiry_id: str = FROZEN_INQUIRY) -> List[SourceUnit]:
    units, _ = ledger_mod.build(prompt_for(name), reading_for(name, inquiry_id=inquiry_id),
                                inquiry_id=inquiry_id)
    return units


# ── resolving the markers ────────────────────────────────────────────────────

def _walk(value: Any, replace) -> Any:
    if isinstance(value, Mapping):
        return {k: _walk(v, replace) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk(v, replace) for v in value]
    if isinstance(value, str):
        return replace(value)
    return value


def resolve_units(payload: Any, units: Sequence[SourceUnit]) -> Any:
    """`$UNIT:<n>` → the nth source unit's id, 1-based, in ledger order.

    An index past the end is LEFT ALONE, so it reaches the dissector as an anchor that is not in
    the ledger and is refused there by name.
    """
    def replace(text: str) -> str:
        if not text.startswith(UNIT_MARKER):
            return text
        raw = text[len(UNIT_MARKER):].strip()
        if not raw.isdigit():
            return text
        index = int(raw) - 1
        return units[index].source_unit_id if 0 <= index < len(units) else text
    return _walk(payload, replace)


def resolve_refs(payload: Any, marker: str, by_ref: Mapping[str, str]) -> Any:
    """`$ATOM:<ref>` / `$CLAIM:<ref>` → the id the pass minted for that local ref."""
    def replace(text: str) -> str:
        if not text.startswith(marker):
            return text
        return by_ref.get(text[len(marker):].strip(), text)
    return _walk(payload, replace)


# ── the passes, bound to one fixture ─────────────────────────────────────────

class _FixtureDissector(FrozenSemanticDissector):
    """The frozen dissector, with `$UNIT:` bound against the ledger it is actually handed.

    Resolved at dissolve time rather than at load time: the ledger depends on the inquiry id, and a
    fixture bound at load would be bound to whichever inquiry happened to load it first.
    """

    def __init__(self, payloads: Sequence[Any]):
        super().__init__(payloads)
        self._raw = [copy.deepcopy(p) for p in payloads]

    def dissolve(self, units, *, prompt, inquiry_id, attempt=1):
        self._frozen = [resolve_units(p, units) for p in self._raw]
        self._served = 0
        return super().dissolve(units, prompt=prompt, inquiry_id=inquiry_id, attempt=attempt)


def refs_by_text(payload_rows: Sequence[Any], produced: Sequence[Any], *,
                 id_attr: str) -> Dict[str, str]:
    """A fixture's local `ref` → the id the pass actually minted, matched on TEXT.

    ONE MECHANISM FOR BOTH MARKERS, and text is the link for the same reason the label was the link
    between a decision option and an observable alternative in HARNESS-002D: the fixture wrote the
    text, the parser keyed the id on it, and nothing else crosses the pass boundary.

    Reaching into a pass for its private local-ref table would be the alternative, and it would mean
    changing a production signature to suit a fixture. A ref whose text matched nothing is simply
    absent here, so its marker stays unresolved and is refused downstream by name.
    """
    by_text = {ids.normalise(getattr(o, "text", "")): getattr(o, id_attr) for o in produced}
    out: Dict[str, str] = {}
    for row in payload_rows or ():
        if not isinstance(row, Mapping):
            continue
        ref, text = str(row.get("ref") or ""), ids.normalise(row.get("text"))
        if ref and text in by_text:
            out[ref] = by_text[text]
    return out


def council_for(name: str, *, inquiry_id: str = FROZEN_INQUIRY) -> Council:
    """A `Council` whose three passes resolve their markers as the pipeline reaches them.

    The architect and the operationalizer are LAZY: each binds its markers at the moment it is
    called, once the ids it references exist. Anything else would have to run the pipeline twice.
    """
    data = load(name)
    dissector = _FixtureDissector(data["dissector_payloads"])
    dissection_rows = [row for payload in data["dissector_payloads"]
                       for row in (payload.get("atoms") or [])]

    class _LazyArchitect(FrozenRelationArchitect):
        def __init__(self):
            super().__init__({})

        def assemble(self, atoms, units, *, inquiry_id, attempt=1):
            self._frozen = resolve_refs(copy.deepcopy(data["architect_payload"]), ATOM_MARKER,
                                        refs_by_text(dissection_rows, atoms, id_attr="atom_id"))
            return super().assemble(atoms, units, inquiry_id=inquiry_id, attempt=attempt)

    class _LazyOperationalizer(FrozenEpistemicOperationalizer):
        def __init__(self):
            super().__init__({})

        def operationalize(self, claims, edges, *, inquiry_id, attempt=1):
            self._frozen = resolve_refs(
                copy.deepcopy(data["operationalizer_payload"]), CLAIM_MARKER,
                refs_by_text(data["architect_payload"].get("claims"), claims, id_attr="claim_id"))
            return super().operationalize(claims, edges, inquiry_id=inquiry_id, attempt=attempt)

    return Council(dissector=dissector, architect=_LazyArchitect(),
                   operationalizer=_LazyOperationalizer(), repairer=None)


def request_for(name: str, *, inquiry_id: str = FROZEN_INQUIRY) -> CompilationRequest:
    return CompilationRequest(
        prompt=prompt_for(name), inquiry_id=inquiry_id,
        reading=reading_for(name, inquiry_id=inquiry_id),
        images=tuple(images_for(name)), now=FROZEN_NOW)


def dissolve_fixture(name: str, *, inquiry_id: str = FROZEN_INQUIRY):
    """The whole production pipeline over one frozen fixture. What every test here drives."""
    from backend.services.semantic_compilation.dissolution import dissolve
    return dissolve(request_for(name, inquiry_id=inquiry_id),
                    council_for(name, inquiry_id=inquiry_id))


__all__ = ["FIXTURE_DIR", "FIXTURES", "UNIT_MARKER", "ATOM_MARKER", "CLAIM_MARKER", "FROZEN_NOW",
           "FROZEN_INQUIRY", "load", "topic_nouns", "prompt_for", "images_for", "reading_for",
           "ledger_for", "resolve_units", "resolve_refs", "refs_by_text", "council_for",
           "request_for", "dissolve_fixture"]
