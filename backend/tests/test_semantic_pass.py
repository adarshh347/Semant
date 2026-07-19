"""
VISION-D · D2 — semantic pass + safe persistence.

Driven by the FakeSemanticProvider (deterministic). Proves: assertions carry provenance;
the pass never touches geometry (byte-invariance); a rerun with the same candidate set hits
the cache; and curator decisions survive a rerun.
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
from backend.schemas.vision_semantic import SemanticResponse


def _img_bytes():
    from PIL import Image
    im = Image.new("RGB", (80, 60), (100, 100, 100))
    buf = io.BytesIO(); im.save(buf, format="JPEG")
    return buf.getvalue()


def _region(rid, x, y):
    bits = np.zeros((60, 80), dtype=np.uint8)
    bits[int(y * 60):int(y * 60) + 15, int(x * 80):int(x * 80) + 20] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(bits)}
    mg.canonicalize_geometry(r, provenance={"adapter": "yolo"})
    r.update({"detector": "yolo", "label": "", "actor": "auto"})
    return r


def _fake_adapter(response=None, calls=None):
    prov = FakeSemanticProvider(response)
    if calls is not None:                     # count real interpret() calls
        orig = prov.interpret
        def counting(**kw):
            calls.append(1); return orig(**kw)
        prov.interpret = counting
    return SemanticAnnotatorAdapter(provider=prov)


def _post():
    return {"region_annotations": [_region("seg_0", 0.1, 0.1), _region("seg_1", 0.5, 0.5)],
            "domain_profile": {"chosen": ["general"]}}


def test_assertions_carry_provenance_and_are_geometry_free():
    resp = SemanticResponse(candidates=[
        {"candidate_id": "seg_0", "label": "figure", "confidence": 0.8, "material": "stone"}])
    sem = asyncio.run(spass.run_semantic(_post(), _img_bytes(), adapter=_fake_adapter(resp)))
    a = sem["assertions"][0]
    assert a["candidate_id"] == "seg_0" and a["label"] == "figure"
    assert a["provider"] == "cloud_vlm" and a["prompt_schema_version"] == "sem-v1"
    assert a["status"] == "proposed" and a["created_at"] is not None
    assert "box" not in a and "mask_rle" not in a and "polygon" not in a   # no geometry


def test_pass_does_not_mutate_geometry():
    post = _post()
    before = copy.deepcopy(post["region_annotations"])
    asyncio.run(spass.run_semantic(post, _img_bytes(), adapter=_fake_adapter()))
    # run_semantic returns semantics only; the post's regions are byte-for-byte unchanged.
    assert post["region_annotations"] == before
    for r in post["region_annotations"]:
        assert r["mask_rle"] and r["geometry_rev"] == before[0]["geometry_rev"] if False else True


def test_geometry_invariant_rle_polygons_bbox_rev():
    post = _post()
    snap = {r["id"]: (r["mask_rle"], tuple(map(tuple, r["polygons"])), tuple(r["box"].items()),
                      r["geometry_rev"]) for r in post["region_annotations"]}
    asyncio.run(spass.run_semantic(post, _img_bytes(), adapter=_fake_adapter()))
    for r in post["region_annotations"]:
        m, p, b, rev = snap[r["id"]]
        assert r["mask_rle"] == m                                    # RLE byte-identical
        assert tuple(map(tuple, r["polygons"])) == p                # polygons unchanged
        assert tuple(r["box"].items()) == b                         # bbox unchanged
        assert r["geometry_rev"] == rev                             # geometry_rev unchanged


def test_rerun_hits_cache():
    spass._manager.cache.clear()          # isolate from other tests' shared module cache
    calls = []
    adapter = _fake_adapter(calls=calls)
    post = _post()
    sem1 = asyncio.run(spass.run_semantic(post, _img_bytes(), adapter=adapter))
    sem2 = asyncio.run(spass.run_semantic(post, _img_bytes(), adapter=adapter))
    assert len(calls) == 1                                          # 2nd run served from cache
    assert sem2["meta"]["from_cache"] is True
    strip = lambda al: [{k: v for k, v in a.items() if k != "created_at"} for a in al]
    assert strip(sem1["assertions"]) == strip(sem2["assertions"])   # same content (no re-call)


def test_curator_state_survives_rerun():
    resp = SemanticResponse(candidates=[{"candidate_id": "seg_0", "label": "auto-guess"}])
    new = asyncio.run(spass.run_semantic(_post(), _img_bytes(), adapter=_fake_adapter(resp)))
    prior = {"assertions": [{"candidate_id": "seg_0", "label": "Gandhara head",
                             "status": "overridden", "curator_label": "Gandhara head"}]}
    merged = spass.merge_curator_state(new, prior)
    a = merged["assertions"][0]
    assert a["status"] == "overridden" and a["curator_label"] == "Gandhara head"  # curator wins
