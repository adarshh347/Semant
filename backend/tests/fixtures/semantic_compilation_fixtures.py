"""
HARNESS-002A §6 — loading the two frozen cross-domain fixtures.

WHY THE FIXTURES LIVE ON THE TEST SIDE. The directive's generality rule is that no production source
may contain a fixture's topic nouns. A fixture module inside
`backend/services/semantic_compilation/` would violate it by existing, so the frozen model outputs
are JSON under `backend/tests/fixtures/semantic_compilation/` and this loader — which names no
topic at all — is what the tests and the rehearsal script share.

WHY `$BLOCK:` EXISTS. A claim anchors to a reading block by the block's id, and block ids are
DERIVED FROM CONTENT: they cannot be written down when the fixture is authored, and hardcoding one
would silently rot the moment a word in the block changed. So a fixture writes
`"source_id": "$BLOCK:<the block's exact text>"` and this loader resolves it against the reading the
theorist actually produced. An unresolvable marker is left ALONE rather than removed, so it arrives
at the compiler as a reading-block id that does not exist and is refused there by name — which is
the behaviour under test, not a loader failure that would hide it.

PURE. No network, no database, no clock. `inquiry_frame` is a real `InquiryFrame` produced by Lane
A's deterministic framer and frozen; `test_semantic_compilation_generality.py` re-frames the prompt
and asserts it still matches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

FIXTURE_DIR = Path(__file__).resolve().parent / "semantic_compilation"

#: The two frozen outputs. The first is the wave's rehearsal shape; the second shares no noun, no
#: cue and no capability with it and runs the identical production path.
FIXTURES: Tuple[str, ...] = ("cross-image-comparison", "unrelated-domain")

BLOCK_MARKER = "$BLOCK:"


def load(name: str) -> Dict[str, Any]:
    path = FIXTURE_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"no fixture named {name!r}; have {list(FIXTURES)}")
    return json.loads(path.read_text(encoding="utf-8"))


def topic_nouns() -> List[str]:
    """Every topic noun both fixtures declare. The generality scan's input."""
    words: List[str] = []
    for name in FIXTURES:
        for word in load(name).get("topic_nouns") or ():
            if word not in words:
                words.append(str(word))
    return words


def resolve_block_refs(payload: Any, blocks: Mapping[str, str]) -> Any:
    """Replace `$BLOCK:<text>` with the block id whose text matches, recursively.

    `blocks` maps normalised block text to block id. An unmatched marker is returned unchanged: a
    loader that quietly dropped it would remove exactly the dangling-anchor case the compiler is
    supposed to refuse.
    """
    if isinstance(payload, Mapping):
        return {k: resolve_block_refs(v, blocks) for k, v in payload.items()}
    if isinstance(payload, list):
        return [resolve_block_refs(v, blocks) for v in payload]
    if isinstance(payload, str) and payload.startswith(BLOCK_MARKER):
        return blocks.get(_norm(payload[len(BLOCK_MARKER):]), payload)
    return payload


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def block_index(reading: Any) -> Dict[str, str]:
    return {_norm(b.text): b.block_id for b in (reading.blocks if reading else ())}


def compiler_payload(fixture: Mapping[str, Any], reading: Any) -> Dict[str, Any]:
    """The frozen compiler output with its block anchors bound to this reading."""
    return resolve_block_refs(dict(fixture["compiler_payload"]), block_index(reading))


def images(fixture: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [dict(i) for i in fixture.get("images") or ()]


def frozen_frame(fixture: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    frame = fixture.get("inquiry_frame")
    return dict(frame) if isinstance(frame, Mapping) else None


def read_fixture(name: str, *, now: Optional[str] = None,
                 theorist_payload: Optional[Any] = None):
    """Replay the frozen reading. Returns `(fixture, ReadingResult)`."""
    from backend.services.semantic_compilation import to_image_refs
    from backend.services.semantic_compilation.theorist import FrozenSceneTheorist

    fixture = load(name)
    payload = fixture["theorist_payload"] if theorist_payload is None else theorist_payload
    refs = to_image_refs(images(fixture))
    result = FrozenSceneTheorist(payload).read(
        fixture["prompt"], refs, inquiry_id=fixture["inquiry_id"],
        corpus=fixture.get("corpus"), now=now)
    return fixture, result


def compile_fixture(name: str, *, now: Optional[str] = None,
                    theorist_payload: Optional[Any] = None,
                    compiler_payload_override: Optional[Any] = None):
    """The whole replay: frozen reading → frozen compilation → graph.

    ONE production path, two subjects. This function contains no topic knowledge; the only
    difference between the two fixtures is which JSON file it reads.
    """
    from backend.services.semantic_compilation import to_image_refs
    from backend.services.semantic_compilation.base import CompilationRequest
    from backend.services.semantic_compilation.compiler import FrozenSemanticCompiler

    fixture, result = read_fixture(name, now=now, theorist_payload=theorist_payload)
    payload = (compiler_payload(fixture, result.reading) if compiler_payload_override is None
               else resolve_block_refs(compiler_payload_override, block_index(result.reading)))
    request = CompilationRequest(
        prompt=fixture["prompt"], inquiry_id=fixture["inquiry_id"],
        inquiry_frame=frozen_frame(fixture) or {}, reading=result.reading,
        images=tuple(to_image_refs(images(fixture))), corpus=dict(fixture.get("corpus") or {}),
        now=now, inherited_refusals=result.refusals, inherited_notes=result.notes)
    return fixture, FrozenSemanticCompiler(payload).compile(request)


__all__ = ["FIXTURE_DIR", "FIXTURES", "BLOCK_MARKER", "load", "topic_nouns", "resolve_block_refs",
           "block_index", "compiler_payload", "images", "frozen_frame", "read_fixture",
           "compile_fixture"]
