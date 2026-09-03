"""
PERCEPTUAL-ORGANS-002 Lane F1 — the world one live-vertical test runs in.

THE ONLY THING FAKED IS THE SEGMENTER, and that is deliberate. Everything else in these fixtures is
the real thing: a real PNG decoded by PIL, a real post document hashed by `movement_kernel`, the
real Extent façade with its real gates, the real Topology organs computing real containment over
real RLE masks, the real resolver, the real conductor, and a store that behaves like pymongo.

The extent adapter is a `FakeSegmenter` because a test that downloaded SAM would not be run, and a
suite nobody runs proves nothing. It is not a stub: it produces genuine COCO RLE masks on the
fixture's own raster, so the geometry Topology measures is geometry, and a containment relation
that comes back is one somebody actually computed.

`FakeCollection` is a synchronous, pymongo-SHAPED collection — `find_one`, `replace_one`,
`find(...).sort(...)`, `count_documents` — because `MongoLabStore` is synchronous and a fake with
the async shape would let the store be written against an interface production does not have.
"""
from __future__ import annotations

import copy
import io
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from backend.schemas.perception_lab import (CapabilityState, EpistemicBasis, EpistemicStatus,
                                            InstanceNaming, LabelSource)
from backend.services import mask_geometry as mg
from backend.services.perception_lab.extent import AdapterOutput

#: The fixture raster. Small enough that an RLE is readable in a failure message and large enough
#: that the organs' own area floors do not reject everything on it.
WIDTH, HEIGHT = 64, 48

POST_ID = "64b7f1a2c3d4e5f60718293a"


# ── the picture ──────────────────────────────────────────────────────────────


def png_bytes(width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """A real PNG, encoded once per call and deterministic.

    Two flat bands rather than noise: the digest is stable across machines, so a test can assert
    that `LabSource.image_digest` is a `sha256:` of THESE bytes and not of whatever a random
    generator produced this morning.
    """
    from PIL import Image
    image = Image.new("RGB", (width, height), (30, 30, 40))
    for y in range(height // 2, height):
        for x in range(width):
            image.putpixel((x, y), (200, 190, 170))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _rect_rle(x0: int, y0: int, x1: int, y1: int) -> Dict[str, Any]:
    """A filled rectangle as a COCO RLE on the fixture raster, through the repository's encoder."""
    bits = bytearray(WIDTH * HEIGHT)
    for y in range(max(0, y0), min(HEIGHT, y1)):
        for x in range(max(0, x0), min(WIDTH, x1)):
            bits[y * WIDTH + x] = 1
    return mg.rle_encode(bits, HEIGHT, WIDTH)


#: An outer rectangle and one strictly inside it, so `topology.containment` has something true to
#: find, plus a third that touches the outer one's edge for `topology.adjacency`.
OUTER = _rect_rle(4, 4, 44, 40)
INNER = _rect_rle(12, 12, 30, 30)
BESIDE = _rect_rle(44, 4, 60, 40)

SHAPES: Tuple[Tuple[str, Dict[str, Any]], ...] = (("outer", OUTER), ("inner", INNER),
                                                  ("beside", BESIDE))


def _box_of(rle: Dict[str, Any]) -> Dict[str, float]:
    box = mg.rle_bbox_norm(rle)
    return {"x": box["x"], "y": box["y"], "w": box["w"], "h": box["h"]}


# ── the post ─────────────────────────────────────────────────────────────────


def post_document(post_id: str = POST_ID, *, regions: Optional[List[Dict[str, Any]]] = None
                  ) -> Dict[str, Any]:
    """A post exactly as `post_collection` holds one, with two canonical regions on it.

    The regions are here so `extent.reuse` has something real to reference and so the after-hash
    has something that could plausibly change. Nothing in the lab writes them.
    """
    from bson import ObjectId
    return {
        "_id": ObjectId(post_id),
        "photo_url": "https://example.invalid/fixture.png",
        "text_blocks": [{"id": "b1", "type": "paragraph", "content": "a fixture picture"}],
        "region_annotations": regions if regions is not None else [
            {"id": "seg_0", "actor": "detector", "detector": "sam2", "geometry_rev": 3,
             "mask_rle": copy.deepcopy(OUTER), "box": _box_of(OUTER), "label": "outer field"},
            {"id": "seg_1", "actor": "creator", "detector": None, "geometry_rev": 1,
             "mask_rle": copy.deepcopy(INNER), "box": _box_of(INNER), "label": "inner disc"},
        ],
        "visual_marks": [],
        "grounds": [],
        "percepts": [],
    }


def snapshot(post: Optional[Mapping[str, Any]] = None, data: Optional[bytes] = None):
    from backend.services.perception_lab.source import snapshot_from
    return snapshot_from(post if post is not None else post_document(),
                         data if data is not None else png_bytes())


# ── the only fake ────────────────────────────────────────────────────────────


class FakeSegmenter:
    """One Extent adapter, producing real masks on the fixture raster.

    `capability()` is answerable so the suite can prove the three states stay apart: `available`
    runs, `unavailable` refuses BEFORE the call with `capability_unavailable`, and an adapter that
    runs and finds nothing returns `empty` — three answers the underlying services conflate into
    one `None`, which is the conflation the Extent façade exists to undo.
    """

    def __init__(self, key: str = "yolo_sam2_auto", *, instances: int = 2,
                 state: CapabilityState = CapabilityState.AVAILABLE,
                 raises: Optional[Exception] = None):
        self.key = key
        self._instances = instances
        self._state = state
        self._raises = raises
        self.calls: List[Tuple[str, Mapping[str, Any]]] = []

    def capability(self) -> CapabilityState:
        return self._state

    def measure(self, step, ctx, params: Mapping[str, Any]) -> AdapterOutput:
        self.calls.append((step.operation, dict(params)))
        if self._raises is not None:
            raise self._raises
        concept = params.get("concept")
        limit = int(params.get("max_instances") or self._instances)
        chosen = SHAPES[:max(0, min(self._instances, limit))]
        instances = [
            {"instance_id": f"{step.step_id}_{name}", "mask_rle": copy.deepcopy(rle),
             "box": _box_of(rle), "area": mg.rle_area(rle) / float(WIDTH * HEIGHT),
             "confidence": 0.9 - 0.1 * n, "region_id": None, "geometry_rev": None,
             "naming": {"text": str(concept), "source": LabelSource.PROMPT.value,
                        "epistemic_status": EpistemicStatus.INTERPRETIVE.value,
                        "confidence": 0.71} if concept else None}
            for n, (name, rle) in enumerate(chosen)]
        return AdapterOutput(
            instances=tuple(instances), basis=EpistemicBasis.MASK,
            status=EpistemicStatus.MEASURED,
            basis_detail=f"{self.key} instance masks on the source raster",
            model=f"fixture/{self.key}", revision="fixture-1", device="cpu", duration_ms=11,
            peak_memory_mb=32.0, detail=f"{len(instances)} extents")


def extent_adapters(**overrides) -> Dict[str, Any]:
    """The four loadable Extent adapters, faked. The other three have no model and are not here —
    `extent.default_adapters()` omits them for the same reason."""
    table = {key: FakeSegmenter(key) for key in
             ("yolo_sam2_auto", "sam3_concept", "grounded_sam", "sam2_refine")}
    table.update(overrides)
    return table


# ── a pymongo-shaped collection ──────────────────────────────────────────────


class FakeCollection:
    """Synchronous, in a dict, with the four methods the store and the probe actually call.

    `find` returns a cursor object with `.sort()` so the store's ordering code is exercised rather
    than skipped — the branch that guards a cursor without `sort` exists for other fakes, and a
    fixture that used it would leave the real path untested.
    """

    def __init__(self, docs: Optional[Iterable[Mapping[str, Any]]] = None):
        self.docs: Dict[Any, Dict[str, Any]] = {}
        for doc in docs or ():
            self.docs[doc["_id"]] = copy.deepcopy(dict(doc))
        self.writes = 0

    # -- reads --

    def find_one(self, query: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        for doc in self.docs.values():
            if _matches(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query: Mapping[str, Any]) -> "FakeCursor":
        return FakeCursor([copy.deepcopy(d) for d in self.docs.values() if _matches(d, query)])

    def count_documents(self, query: Mapping[str, Any]) -> int:
        return sum(1 for d in self.docs.values() if _matches(d, query))

    # -- writes --

    def replace_one(self, query: Mapping[str, Any], doc: Mapping[str, Any], upsert: bool = False):
        self.writes += 1
        self.docs[doc["_id"]] = copy.deepcopy(dict(doc))
        return type("Result", (), {"matched_count": 1, "upserted_id": doc["_id"]})()


class FakeCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def sort(self, spec, direction=None) -> "FakeCursor":
        """Both spellings pymongo accepts: a list of pairs, and `sort("_id", -1)`."""
        pairs = [(spec, direction if direction is not None else 1)] \
            if isinstance(spec, str) else list(spec)
        for key, way in reversed(pairs):
            self._docs.sort(key=lambda d: str(_dotted(d, key) or ""), reverse=way < 0)
        return self

    def limit(self, n: int) -> "FakeCursor":
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class AsyncFakeCollection(FakeCollection):
    """The same store with the `motor` shape, for the two handlers that read the corpus.

    `share_with` makes a SYNCHRONOUS view onto the very same documents, because the lab reads the
    corpus through `motor` and probes it through pymongo, and a fixture with two copies would let
    a mutation be visible to one and not the other — which is precisely the bug the probe exists
    to catch.
    """

    def sync_view(self) -> "FakeCollection":
        view = FakeCollection()
        view.docs = self.docs
        return view

    async def find_one(self, query):                        # type: ignore[override]
        return FakeCollection.find_one(self, query)

    def find(self, query):                                  # type: ignore[override]
        return AsyncFakeCursor([copy.deepcopy(d) for d in self.docs.values()
                                if _matches(d, query)])


class AsyncFakeCursor(FakeCursor):
    def __aiter__(self):
        async def _gen():
            for doc in self._docs:
                yield doc
        return _gen()


def _dotted(doc: Mapping[str, Any], path: str) -> Any:
    current: Any = doc
    for part in path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _matches(doc: Mapping[str, Any], query: Mapping[str, Any]) -> bool:
    for key, expected in query.items():
        found = _dotted(doc, key)
        if isinstance(expected, Mapping) and "$ne" in expected:
            if found == expected["$ne"]:
                return False
            continue
        if found != expected:
            return False
    return True


def lab_collections() -> Dict[str, FakeCollection]:
    """The lab's own collections. Six since PERCEPTUAL-FORMS-001H: a derivation is not an artifact
    and never becomes one, so it is a sixth collection rather than a discriminator on the fifth."""
    return {kind: FakeCollection() for kind in
            ("sessions", "plans", "runs", "artifacts", "reviews", "derivations")}


__all__ = ["WIDTH", "HEIGHT", "POST_ID", "OUTER", "INNER", "BESIDE", "SHAPES", "png_bytes",
           "post_document", "snapshot", "FakeSegmenter", "extent_adapters", "FakeCollection",
           "FakeCursor", "AsyncFakeCollection", "lab_collections"]
