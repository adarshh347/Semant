"""
VISION-F · F4 — dependent semantic staleness (curator decisions preserved).

Proves a semantic assertion is marked stale ONLY when its referenced evidence (mask) changed, an
assertion about unchanged evidence stays valid, and marking never drops the curator's decision.
(The embedding-refresh resume/no-duplicate behaviour is proved live in scripts/vision_f4_refresh
and by the E6 indexing tests.)
"""
from backend.services import geometry_recovery as gr
from backend.services import mask_geometry as mg
import numpy as np


def _region(rid, y1):
    b = np.zeros((40, 40), np.uint8); b[5:y1, 5:30] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(b)}
    mg.canonicalize_geometry(r, provenance={"a": "t"})
    return r


def _post():
    return {"region_annotations": [_region("seg_0", 30), _region("seg_1", 25)],
            "semantics": {"assertions": [
                {"candidate_id": "seg_0", "label": "wall", "status": "accepted", "curator_label": "apse wall"},
                {"candidate_id": "seg_1", "label": "floor", "status": "proposed"}]}}


def test_unchanged_evidence_keeps_assertions_valid():
    post = _post()
    prior = {r["id"]: (__import__("backend.services.region_embedding_service",
             fromlist=["mask_hash"]).mask_hash(r["mask_rle"])) for r in post["region_annotations"]}
    assert gr.stale_semantic_assertions(post, prior) == []       # nothing changed → nothing stale


def test_changed_mask_marks_only_that_assertion_stale():
    post = _post()
    from backend.services.region_embedding_service import mask_hash
    prior = {r["id"]: mask_hash(r["mask_rle"]) for r in post["region_annotations"]}
    # recover seg_0's geometry (a different mask) — seg_1 untouched
    post["region_annotations"][0] = _region("seg_0", 38)
    stale = gr.stale_semantic_assertions(post, prior)
    assert stale == ["seg_0"]                                    # only the changed-evidence assertion


def test_marking_preserves_curator_decisions():
    post = _post()
    from backend.services.region_embedding_service import mask_hash
    prior = {r["id"]: mask_hash(r["mask_rle"]) for r in post["region_annotations"]}
    post["region_annotations"][0] = _region("seg_0", 38)         # seg_0 evidence changed
    gr.mark_stale_semantic_assertions(post, prior)
    a0 = post["semantics"]["assertions"][0]
    assert a0["evidence_stale"] is True                          # flagged for a re-read…
    assert a0["status"] == "accepted" and a0["curator_label"] == "apse wall"   # …decision preserved
    assert post["semantics"]["assertions"][1]["evidence_stale"] is False
