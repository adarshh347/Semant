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

import copy
from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.schemas.inquiry_session import PostRef
from backend.services.semantic_compilation.compiler import FrozenSemanticCompiler
from backend.tests.fixtures import semantic_compilation_fixtures as compilation
from backend.tests.fixtures import semantic_dissolution_fixtures as dissolution

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


def stages_for(name: str, *, clock=None, **bound):
    """The whole Phase 1 stage order over one frozen fixture. No network, no database, no clock.

    The framer is the REAL deterministic one — it reads no pixels and reaches nothing, so replacing
    it with a stub would test a chain one link shorter than the one that ships.
    """
    from backend.services.inquiry import get_framer
    from backend.services.inquiry_session.coordinator import Stages
    return Stages(framer=get_framer("deterministic"), theorist=theorist_for(name),
                  compiler=compiler_for(name), clock=clock or frozen_clock(), **bound)


# ── the v2 council, driven by the coordinator (HARNESS-003D) ────────────────
#
# `stages_for` binds the v1 one-call compiler, which is what the 002D fixtures were written against
# and what the checked-in samples exercised until this lane. Production now binds the council, and a
# chain nothing drove end to end over a v2 graph is a chain whose integration was never tested —
# Lane A's pipeline compiled and ran, and Lane D is where it meets a session, a stage ledger and a
# wire projection.

DISSOLUTION_FIXTURES = dissolution.FIXTURES


def dissolution_post_refs(name: str, *, readable: bool = True) -> List[PostRef]:
    return [PostRef(post_id=image["post_id"], title=image.get("title", ""),
                    image_ref=f"https://fixture.invalid/{image['post_id']}.jpg" if readable else "",
                    fingerprint=f"fp_{image['post_id']}", readable=readable)
            for image in dissolution.load(name)["images"]]


def dissolution_post_docs(name: str) -> Dict[str, Dict[str, Any]]:
    return {image["post_id"]: {"_id": image["post_id"], "title": image.get("title", ""),
                               "photo_url": f"https://fixture.invalid/{image['post_id']}.jpg",
                               "region_annotations": [], "visual_marks": []}
            for image in dissolution.load(name)["images"]}


def dissolution_prompt_for(name: str) -> str:
    return dissolution.prompt_for(name)


def dissolution_stages_for(name: str, *, clock=None, **bound):
    """The production stage order with the REAL `DissolutionCompiler` over a frozen council.

    The compiler under test is the production adapter rather than a stand-in for it, so everything
    Lane D added at that seam actually runs: the substage narration, the wall-clock budget it opens,
    the producer attributes 003B's truncation reader consults, and the pass receipts the view
    projects. Only the three minds behind it are frozen — the same substitution `stages_for` makes
    one layer up, at the layer where it proves something different.
    """
    from backend.services.inquiry import get_framer
    from backend.services.inquiry_session.coordinator import Stages
    from backend.services.inquiry_session.dissolution_binding import DissolutionCompiler
    from backend.services.semantic_compilation.theorist import FrozenSceneTheorist

    return Stages(framer=get_framer("deterministic"),
                  theorist=FrozenSceneTheorist(dissolution.load(name)["theorist_payload"]),
                  compiler=DissolutionCompiler(dissolution.council_for(name)),
                  clock=clock or frozen_clock(), **bound)


# ── the fakes a route test needs ────────────────────────────────────────────

def _dig(doc, path):
    cur = doc
    for part in str(path).split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_a, **_k):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()


class _Result:
    def __init__(self, matched):
        self.matched_count = matched
        self.modified_count = matched


class FakeCollection:
    """Flat AND dotted key matching, because the real one does.

    A fake that only did flat keys would pass the compare-and-set test by matching nothing and then
    matching everything, which is the opposite of the guarantee under test.
    """

    def __init__(self, docs=None):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in (docs or ())}
        self.writes = 0

    def _match(self, doc, query):
        return all(_dig(doc, k) == v for k, v in (query or {}).items())

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        self.writes += 1
        return type("R", (), {"inserted_id": doc["_id"]})()

    async def find_one(self, query, projection=None):
        for d in self.docs.values():
            if self._match(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values()
                        if self._match(d, query or {})])

    async def update_one(self, query, update, upsert=False):
        for d in self.docs.values():
            if self._match(d, query):
                d.update(copy.deepcopy(update.get("$set", {})))
                self.writes += 1
                return _Result(1)
        return _Result(0)


def post_collection_for(name: str) -> FakeCollection:
    """The fixture's posts, as documents `corpus.resolve` can find by `_id`."""
    return FakeCollection(list(post_docs(name).values()))


def dissolution_post_collection_for(name: str) -> FakeCollection:
    return FakeCollection(list(dissolution_post_docs(name).values()))


__all__ = ["FIXTURES", "FixtureCompiler", "FakeCollection", "fixture", "post_refs", "post_docs",
           "post_collection_for", "theorist_for", "compiler_for", "prompt_for", "stages_for",
           "topic_nouns", "frozen_clock",
           "DISSOLUTION_FIXTURES", "dissolution_post_refs", "dissolution_post_docs",
           "dissolution_prompt_for", "dissolution_stages_for",
           "dissolution_post_collection_for"]
