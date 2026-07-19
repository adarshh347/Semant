"""
VISION-D · D3 — two semantic scopes + relations-are-not-geometry.

(1) Candidate-bound assertions reference candidate ids; (2) image-global readings do not
pretend to be object masks. Relation proposals cite endpoints + type + confidence and stay
proposals — they can NEVER become geometry parenting or change mask ownership/containment.
Painting may declare automatic object candidates insufficient (→ Differential Grounds).
"""
import asyncio
import copy
import io

import numpy as np
import pytest

from backend.services import semantic_pass as spass
from backend.services import mask_geometry as mg
from backend.services.vision_orchestrator.adapters import SemanticAnnotatorAdapter
from backend.services.semantic_provider import FakeSemanticProvider
from backend.schemas.vision_semantic import SemanticResponse, GlobalReading


@pytest.fixture(autouse=True)
def _clean_cache():
    # these tests build identical packets on purpose (same masks, same image) to probe the
    # scope/relation invariants — so they share a content cache key. Clear the module-level
    # semantic cache between tests so one test's response never leaks into another's read.
    spass._manager.cache.clear()
    yield
    spass._manager.cache.clear()


def _img_bytes():
    from PIL import Image
    im = Image.new("RGB", (80, 60), (100, 100, 100)); buf = io.BytesIO(); im.save(buf, "JPEG")
    return buf.getvalue()


def _region(rid, x, y):
    bits = np.zeros((60, 80), dtype=np.uint8)
    bits[int(y * 60):int(y * 60) + 15, int(x * 80):int(x * 80) + 20] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(bits)}
    mg.canonicalize_geometry(r, provenance={"adapter": "yolo"})
    r.update({"detector": "yolo", "label": "", "actor": "auto"})
    return r


def _adapter(resp):
    return SemanticAnnotatorAdapter(provider=FakeSemanticProvider(resp))


def _post():
    return {"region_annotations": [_region("seg_0", 0.1, 0.1), _region("seg_1", 0.5, 0.5)]}


# ── two scopes are distinct ──────────────────────────────────────────────────
def test_global_reading_is_distinct_from_candidate_claims():
    resp = SemanticResponse(
        candidates=[{"candidate_id": "seg_0", "label": "figure"}],
        global_reading={"composition": "central", "atmosphere": "solemn"})
    sem = asyncio.run(spass.run_semantic(_post(), _img_bytes(), adapter=_adapter(resp)))
    # candidate assertions carry a candidate_id; the global reading carries NONE (it is not a Region).
    assert all("candidate_id" in a for a in sem["assertions"])
    assert sem["global"] is not None and "candidate_id" not in sem["global"]
    assert sem["global"]["composition"] == "central"


def test_global_reading_forbids_geometry():
    # GlobalReading is extra="forbid": it cannot smuggle a mask/box while "reading" the scene.
    import pytest
    with pytest.raises(Exception):
        GlobalReading(composition="x", box={"x": 0})


# ── relations are proposals, never geometry parenting ────────────────────────
def test_relation_does_not_become_parent_or_clip():
    # the VLM proposes "seg_0 is part-of seg_1" — this must NOT set seg_0.parent_id or clip it.
    resp = SemanticResponse(
        candidates=[{"candidate_id": "seg_0", "label": "crown"},
                    {"candidate_id": "seg_1", "label": "head"}],
        relations=[{"from_id": "seg_0", "to_id": "seg_1", "relation": "part-of", "confidence": 0.7}])
    post = _post()
    before = copy.deepcopy(post["region_annotations"])
    sem = asyncio.run(spass.run_semantic(post, _img_bytes(), adapter=_adapter(resp)))
    # the relation is stored as a PROPOSAL, citing its endpoints + type + confidence…
    rel = sem["relations"][0]
    assert rel["from_id"] == "seg_0" and rel["to_id"] == "seg_1" and rel["relation"] == "part-of"
    assert rel["confidence"] == 0.7
    # …and NO region gained a parent_id, and geometry is byte-identical (no clipping).
    assert post["region_annotations"] == before
    for r in post["region_annotations"]:
        assert r.get("parent_id") in (None, "")


# ── painting: candidates can be declared insufficient → Grounds ──────────────
def test_painting_can_declare_candidates_insufficient():
    resp = SemanticResponse(
        candidates=[{"candidate_id": "seg_0", "label": "unclear form", "uncertainty": "dissolving"}],
        needs_better_evidence=["seg_0"],
        global_reading={"scene": "an abstract painting; object masks are the wrong ontology"})
    # needs_better_evidence flows through, and the global reading can say objects don't fit.
    assert resp.needs_better_evidence == ["seg_0"]
    assert "wrong ontology" in resp.global_reading.scene
    from backend.services.evidence_packet import build_prompt
    prompt = build_prompt({"candidates": [{"n": 1, "candidate_id": "seg_0", "auto_label": None,
                                           "detector": "sam2"}], "profile": {"chosen": ["painting"]},
                           "intent": "name"})
    assert "needs_better_evidence" in prompt          # the escape hatch is offered to the VLM
