"""
HARNESS-002D — the integration fixtures, and the one wrapper they need.

WHY A WRAPPER. Lane A's frozen compiler payloads anchor claims to reading blocks by `$BLOCK:<text>`
markers, because block ids are DERIVED FROM CONTENT and cannot be written down when the fixture is
authored. Lane A's loader resolves them against a reading it produced itself. The coordinator
produces its own reading, under the inquiry id the framer minted — so the markers have to be
resolved against THAT reading, at compile time, which is exactly when a real compiler sees it.

`FixtureCompiler` is that: it resolves the markers against `request.reading` and then delegates to
the real `FrozenSemanticCompiler`. It adds no claim, drops none, and changes no vocabulary — a
marker that matches nothing is left alone so the compiler refuses it by name, which is the
behaviour under test rather than a loader failure that would hide it.

PURE. No network, no database, no clock.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.schemas.inquiry_session import PostRef
from backend.services.semantic_compilation.compiler import FrozenSemanticCompiler
from backend.tests.fixtures import semantic_compilation_fixtures as compilation

#: The two integration fixtures. Same coordinator, same state machine, same capability, same
#: composer — the only difference is which frozen payload is read.
FIXTURES = compilation.FIXTURES


class FixtureCompiler:
    """A frozen compiler payload whose reading anchors are bound at compile time."""

    name = "replay"

    def __init__(self, payload: Mapping[str, Any]):
        self._payload = payload

    def compile(self, request: Any):
        bound = compilation.resolve_block_refs(
            dict(self._payload), compilation.block_index(request.reading))
        return FrozenSemanticCompiler(bound).compile(request)


def fixture(name: str) -> Dict[str, Any]:
    return compilation.load(name)


def post_refs(name: str, *, readable: bool = True) -> List[PostRef]:
    """The fixture's images as post refs, with a fingerprint so invariance is checkable."""
    return [PostRef(post_id=image["post_id"], title=image.get("title", ""),
                    image_ref=f"https://fixture.invalid/{image['post_id']}.jpg" if readable else "",
                    fingerprint=f"fp_{image['post_id']}", readable=readable)
            for image in fixture(name)["images"]]


def post_docs(name: str) -> Dict[str, Dict[str, Any]]:
    """Post documents shaped the way `corpus.resolve` reads them."""
    return {image["post_id"]: {"_id": image["post_id"], "title": image.get("title", ""),
                               "photo_url": f"https://fixture.invalid/{image['post_id']}.jpg",
                               "region_annotations": [], "visual_marks": []}
            for image in fixture(name)["images"]}


def theorist_for(name: str):
    from backend.services.semantic_compilation.theorist import FrozenSceneTheorist
    return FrozenSceneTheorist(fixture(name)["theorist_payload"])


def compiler_for(name: str) -> FixtureCompiler:
    return FixtureCompiler(fixture(name)["compiler_payload"])


def prompt_for(name: str) -> str:
    return fixture(name)["prompt"]


def topic_nouns() -> List[str]:
    return compilation.topic_nouns()


def frozen_clock(stamp: str = "2026-08-09T00:00:00+00:00"):
    return lambda: stamp


__all__ = ["FIXTURES", "FixtureCompiler", "fixture", "post_refs", "post_docs", "theorist_for",
           "compiler_for", "prompt_for", "topic_nouns", "frozen_clock"]
