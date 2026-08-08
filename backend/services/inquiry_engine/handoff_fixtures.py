"""
HARNESS-001B2 — the deterministic world the handoff proofs run in.

Two nested masks, a post to hang them on, and a fake SAM 3 service that returns them. Nothing
here is a fake DIRECTOR result: the fake stops at the model boundary, and everything above it —
`instances_to_regions`, `suggestions_from_concept_segments`, the context writes — is the
production code path, unmodified.

WHY NESTED, SPECIFICALLY. `nestedness_organ` grounds `measured` containment on masks and only on
masks (DECISION-movement-grounds-only-on-masks). Two masks where one lies wholly inside the other
are therefore the smallest world in which a real organ can return a real MEASURED reading — which
is what the vertical proof has to show arriving back at an `EvidenceGoal`. A pair that merely
overlapped would prove the transport and leave the measurement untested.

WHY REAL RLE. `mask_geometry.rle_encode` is the same encoder production uses, and the organ
decodes with the same module. A hand-written `counts` list that happened to be malformed would
fail inside the organ as a refusal, and a refusal is exactly what the proof must not be able to
mistake for a measurement.

PURE. No network, no model, no database, no clock.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services import mask_geometry
from backend.services import sam3_concept_service as _real_sam3

#: Bound HERE, at import, and deliberately not looked up later. The fake replaces
#: `sys.modules["backend.services.sam3_concept_service"]`, so a fake that re-imported the module
#: by name to reach `instances_to_regions` would find ITSELF — an infinite recursion that surfaces
#: as a `RecursionError` inside the runner and is reported as a failed step, i.e. as the very
#: "nothing was captured" this lane exists to distinguish from a real empty.
_instances_to_regions = _real_sam3.instances_to_regions

#: Small enough to encode in pure python instantly, big enough that the inner mask has a real
#: margin inside the outer one rather than sharing an edge with it.
MASK_H = 40
MASK_W = 40

#: The concept the fixture is run with. A phrase is REQUIRED by `_run_concept_segment` — an
#: open-vocabulary finder with nothing to look for cannot be checked — so the proofs must pass one.
CONCEPT = "fold"

#: What the fake service reports itself as, so a reader of a receipt can see at a glance that no
#: checkpoint was involved.
FAKE_MODEL = "fixture/deterministic-sam3"


def _rect_bits(x0: int, y0: int, x1: int, y1: int, h: int = MASK_H, w: int = MASK_W) -> List[int]:
    """A filled axis-aligned rectangle as a row-major 0/1 buffer."""
    bits = [0] * (h * w)
    for row in range(max(0, y0), min(h, y1)):
        for col in range(max(0, x0), min(w, x1)):
            bits[row * w + col] = 1
    return bits


def outer_rle() -> Dict[str, Any]:
    """The containing extent: a large rectangle."""
    return mask_geometry.rle_encode(_rect_bits(4, 4, 36, 36), MASK_H, MASK_W)


def inner_rle() -> Dict[str, Any]:
    """The contained extent, wholly inside `outer_rle` with a margin on every side."""
    return mask_geometry.rle_encode(_rect_bits(12, 12, 24, 24), MASK_H, MASK_W)


def sam_result(concept: str = CONCEPT, *, latency_ms: float = 12.0) -> Dict[str, Any]:
    """Exactly the shape `sam3_concept_service.segment_concept` returns.

    Two instances, the second nested inside the first, each with a real `mask_rle`. `index` is
    POSITIONAL, as production's is — which is the whole reason identity downstream is
    `(post_id, region_id, geometry_rev)` and never the instance number.
    """
    return {
        "concept": concept,
        "model": FAKE_MODEL,
        "latency_ms": latency_ms,
        "truncated": False,
        "instances": [
            {"index": 0, "confidence": 0.91, "mask_rle": outer_rle()},
            {"index": 1, "confidence": 0.84, "mask_rle": inner_rle()},
        ],
    }


def post(post_id: str = "handoff_post_a", *, title: str = "a fixture image",
         regions: Sequence[Mapping[str, Any]] = ()) -> Dict[str, Any]:
    """A committed post with no proposed geometry on it.

    ANNOTATION-INDEPENDENT by default, in the run surface's sense: zero regions is a legitimate
    starting point because the actuators produce the evidence. A caller that wants a committed
    Region to point at passes `regions`.
    """
    return {
        "_id": post_id,
        "id": post_id,
        "title": title,
        "photo_url": f"https://fixture.invalid/{post_id}.jpg",
        "region_annotations": [dict(r) for r in regions],
        "visual_marks": [],
        "text_blocks": [],
    }


def committed_region(region_id: str = "committed_ground_0") -> Dict[str, Any]:
    """A Region already on the post, with a real mask — something a pointer may legitimately
    resolve to without the delta carrying a copy of it."""
    region: Dict[str, Any] = {
        "id": region_id,
        "actor": "user",
        "label": "committed",
        "mask_rle": mask_geometry.rle_encode(_rect_bits(2, 2, 38, 38), MASK_H, MASK_W),
        "proposed": False,
        "geometry_rev": 0,
    }
    # REGION-PROV-001: THE DRAWER DECLARES ITSELF. This fixture cuts a mask, so it names the
    # maker like any other drawing path — a Region whose origin is unrecorded can end up grounding
    # a `measured` claim with nothing left saying whose geometry it was, and the guard in
    # `test_region_provenance.py` refuses exactly that. It caught this fixture, correctly.
    mask_geometry.canonicalize_geometry(region, provenance={
        "adapter": "handoff_fixtures", "model": FAKE_MODEL,
        "method": "fixture-committed-region",
    })
    return region


class FakeSam3Service:
    """Stands in for `sam3_concept_service` at the MODEL boundary and nowhere above it.

    `instances_to_regions` is imported from the real module rather than reimplemented, so the
    Regions the proofs capture are minted by production code — ids, `proposed: True`,
    `geometry_rev`, canonicalised polygons and geometry provenance included. A local copy of that
    function would let the proof pass while production drifted underneath it.
    """

    NAMING_CONFIDENCE_FLOOR = 0.0

    def __init__(self, result: Optional[Dict[str, Any]] = None, *, available: bool = True):
        self._result = result if result is not None else sam_result()
        self._available = available
        self.calls: List[Tuple[Any, str]] = []

    def is_available(self) -> bool:
        return self._available

    def segment_concept(self, image: Any, concept: str, **_: Any) -> Dict[str, Any]:
        self.calls.append((image, concept))
        # A COPY per call. `instances_to_regions` mutates each instance with its `region_id`, so
        # handing back the same dict twice would make the second run look already-resolved.
        result = {**self._result, "concept": concept,
                  "instances": [dict(i) for i in self._result.get("instances") or ()]}
        return result

    @staticmethod
    def instances_to_regions(result: Dict[str, Any], *, prefix: str = "cseg"):
        return _instances_to_regions(result, prefix=prefix)


class EmptySam3Service(FakeSam3Service):
    """Available, ran, and measured nothing. `measured_absence`, not `execution_unavailable`."""

    def segment_concept(self, image: Any, concept: str, **_: Any) -> Dict[str, Any]:
        self.calls.append((image, concept))
        return {"concept": concept, "model": FAKE_MODEL, "latency_ms": 3.0, "instances": []}


class UnavailableSam3Service(FakeSam3Service):
    """The instrument exists and is not running. A different fact from measuring nothing."""

    def __init__(self):
        super().__init__(available=False)

    def segment_concept(self, image: Any, concept: str, **_: Any):
        raise RuntimeError("weights are not on disk")


__all__ = ["MASK_H", "MASK_W", "CONCEPT", "FAKE_MODEL", "outer_rle", "inner_rle", "sam_result",
           "post", "committed_region", "FakeSam3Service", "EmptySam3Service",
           "UnavailableSam3Service"]
