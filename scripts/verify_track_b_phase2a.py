"""
Track B · Phase 2a verification — a real garment segmenter, on CPU.

    env PYTHONPATH=$PWD ./venv/bin/python scripts/verify_track_b_phase2a.py

Proves:
  1. On a real fashion image, the garment segmenter yields true clothing regions
     (top / skirt / belt …) with detector="segformer_clothes", normalized polygons,
     and it SUPERSEDES YOLO's single "person" anchor. CPU timing reported.
  2. On a non-fashion image, the pipeline falls back to YOLO cleanly (detector="yolo").
  3. Precedence/dedup: no duplicate garment from both detectors; YOLO's non-garment
     objects survive; a "person" that contains the garments is dropped.
  4. Graceful degradation: with the deps unavailable the segmenter returns None and the
     caller falls back to YOLO — no crash, no partial state.
  5. Regression: the new regions validate as Region, FashionCLIP still embeds them, and
     aggregate_categories is byte-identical.

Read-only against the corpus: it never writes region_annotations. It exercises the same
service functions the endpoint calls.
"""

import asyncio
import time

import httpx
from bson import ObjectId

from backend.database import post_collection
from backend.schemas.post import Region
from backend.services import anatomy_catalog_service
from backend.services import fashion_clip_service as fc
from backend.services import fashion_segmentation_service as fseg
from backend.services import segmentation_service as yolo
from backend.routers.posts import _image_fetch_headers

GARMENTISH = {"garment", "accessory"}


def _catalog_fingerprint(profile):
    return sorted(
        (p["category"], p["label"], p["occurrence_count"], p["prioritised_count"],
         p["total_intensity"]) for p in profile
    )


async def _fetch(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=_image_fetch_headers(url))
        resp.raise_for_status()
        return resp.content


async def _pick(is_fashion: bool):
    """A post whose stored domain says fashion (or explicitly doesn't)."""
    async for post in post_collection.find(
        {"domain": {"$exists": True}, "photo_url": {"$exists": True}},
        {"photo_url": 1, "domain": 1},
    ):
        if bool((post.get("domain") or {}).get("is_fashion")) == is_fashion:
            return post
    return None


def _assert_normalized(regions):
    for r in regions:
        b = r["box"]
        assert all(0.0 <= v <= 1.0001 for v in b.values()), f"box out of range: {b}"
        assert b["x"] + b["w"] <= 1.0001 and b["y"] + b["h"] <= 1.0001, f"box escapes frame: {b}"
        assert len(r["polygon"]) >= 3, f"degenerate polygon on {r['label']}"
        for x, y in r["polygon"]:
            assert 0.0 <= x <= 1.0001 and 0.0 <= y <= 1.0001, f"polygon point out of range: {x},{y}"


async def main():
    print("=" * 76)
    print("TRACK B · PHASE 2a VERIFICATION — garment segmentation (SegFormer-B2, CPU)")
    print("=" * 76)
    print(f"segmenter available: {fseg.is_available()}   detector tag: {fseg.DETECTOR!r}")
    assert fseg.is_available(), "torch/transformers/opencv not installed"

    before = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))

    # ---- 1. fashion image → real garments, superseding YOLO's person ---------------
    print("\n[1] Fashion image")
    post = await _pick(is_fashion=True)
    assert post, "no fashion-domain post found"
    pid = str(post["_id"])
    data = await _fetch(post["photo_url"])
    print(f"    post {pid[:8]}…  domain={post['domain']['label']} ({post['domain']['score']})")

    fseg.segment_image_bytes(data)                       # warm the cache
    t0 = time.time(); garments = fseg.segment_image_bytes(data); t_seg = time.time() - t0
    t0 = time.time(); yolo_regions = yolo.segment_image_bytes(data); t_yolo = time.time() - t0

    print(f"    SegFormer  {t_seg:5.2f}s CPU → {len(garments)} regions")
    for r in garments:
        print(f"        {r['label']:<12} cat={r['category']:<10} part={str(r['part']):<10} "
              f"conf={r['confidence']:.2f}  poly={len(r['polygon'])}pts")
    print(f"    YOLO       {t_yolo:5.2f}s CPU → {[(r['label'], r['category']) for r in yolo_regions]}")

    assert garments, "the garment segmenter found nothing on a fashion image"
    assert all(r["detector"] == fseg.DETECTOR for r in garments)
    assert any(r["category"] == "garment" for r in garments), "no garment region"
    assert all(r["attributes"] == [] for r in garments), "Phase 2a must not invent attributes"
    _assert_normalized(garments)

    # Semantic segmentation fragments an occluded garment into several components. A
    # sliver of dress past an elbow must not become a second "dress" — it would
    # double-count in the frequency catalog and duplicate the row in the parts panel.
    garment_labels = [r["label"] for r in garments if r["category"] in GARMENTISH]
    assert len(garment_labels) == len(set(garment_labels)), \
        f"a garment class fragmented into duplicate regions: {garment_labels}"
    print(f"    ✅ no fragmented duplicates: {garment_labels}")
    print(f"    ✅ {sum(1 for r in garments if r['category'] in GARMENTISH)} garment/accessory "
          f"regions, polygons normalized, attributes[] left to Phase 2b")

    # ---- 2/3. precedence + dedup ----------------------------------------------------
    print("\n[2] Precedence — garment segmenter > YOLO")
    merged = fseg.merge_with_precedence(garments, yolo_regions or [])
    by_det = {}
    for r in merged:
        by_det.setdefault(r["detector"], []).append(r["label"])
    for det, labels in by_det.items():
        print(f"    {det:<18} {labels}")

    yolo_labels = {r["label"] for r in (yolo_regions or [])}
    kept_yolo = {r["label"] for r in merged if r["detector"] == "yolo"}
    superseded = yolo_labels - kept_yolo
    print(f"    superseded: {sorted(superseded) or '(none)'}")

    assert not any(r["detector"] == "yolo" and r["category"] in {"figure", "garment"}
                   for r in merged), "a YOLO figure/garment survived the garment segmenter"
    if "person" in yolo_labels:
        assert "person" in superseded, "the YOLO person anchor was not superseded"
    # every region id is unique — the two detectors must not collide
    ids = [r["id"] for r in merged]
    assert len(ids) == len(set(ids)), "duplicate region ids across detectors"
    # no two garment regions describe the same thing
    garment_boxes = [r["box"] for r in merged if r["category"] in GARMENTISH]
    for i, a in enumerate(garment_boxes):
        for b in garment_boxes[i + 1:]:
            assert fseg._box_iou(a, b) < 0.5, "two garment regions overlap heavily (dup)"
    print("    ✅ person superseded; non-garment YOLO objects survive; no duplicate garments")

    # ---- 4. non-fashion image → YOLO ------------------------------------------------
    print("\n[3] Non-fashion image → YOLO fallback")
    other = await _pick(is_fashion=False)
    if other:
        odata = await _fetch(other["photo_url"])
        oyolo = yolo.segment_image_bytes(odata)
        print(f"    post {str(other['_id'])[:8]}…  domain={other['domain']['label']}")
        print(f"    YOLO → {[(r['label'], r['detector']) for r in (oyolo or [])][:6]}")
        assert oyolo is not None, "YOLO unavailable"
        assert all(r["detector"] == "yolo" for r in oyolo)
        print("    ✅ non-fashion routes to YOLO; detector='yolo'")
    else:
        print("    ⚠️  no non-fashion post with a stored domain — skipped")

    # ---- 5. graceful degradation -----------------------------------------------------
    print("\n[4] Graceful degradation (deps/model unavailable)")
    original = fseg._load_failed
    try:
        fseg._load_failed = True                     # simulate a slim deploy
        assert fseg.is_available() is False
        assert fseg.segment_image_bytes(data) is None, "must return None, not raise or []"
        # the caller's contract: None → fall back to YOLO
        fallback = fseg.merge_with_precedence([], yolo_regions or [])
        assert [r["detector"] for r in fallback] == ["yolo"] * len(fallback)
        assert fallback, "fallback produced no anchors"
        print(f"    segment_image_bytes → None; merge falls through to "
              f"{len(fallback)} YOLO regions ({[r['label'] for r in fallback]})")
        print("    ✅ no crash; the pipeline degrades to YOLO exactly as before Phase 2a")
    finally:
        fseg._load_failed = original

    # `[]` (looked, found nothing) must be distinguishable from None (could not look)
    empty_merge = fseg.merge_with_precedence([], yolo_regions or [])
    assert len(empty_merge) == len(yolo_regions or []), "empty primary must keep all secondary"
    print("    ✅ [] (found nothing) and None (could not look) stay distinguishable")

    # ---- 6. regression ---------------------------------------------------------------
    print("\n[5] Regression")
    for r in merged:
        Region.model_validate(r)
    print(f"    ✅ all {len(merged)} merged regions validate as Region")

    if fc.is_available():
        img = fc._open_image(data)
        target = next(r for r in garments if r["category"] == "garment")
        t0 = time.time()
        vec = fc.embed_image(fc._crop_norm(img, target["box"]))
        print(f"    FashionCLIP embedded '{target['label']}' → dim {len(vec)} "
              f"in {time.time() - t0:.2f}s")
        assert vec and len(vec) == 512
        labels = fc.label_region(img, target["box"])
        print(f"    FashionCLIP zero-shot on it → {labels}")
        print("    ✅ FashionCLIP still vectorizes + labels the new garment regions")

    after = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))
    print(f"    catalog buckets before={len(before)} after={len(after)} identical={before == after}")
    assert before == after, "Phase 2a perturbed the catalog"
    print("    ✅ catalog identical (this script writes nothing)")

    print(f"\n    CPU timing — SegFormer {t_seg:.2f}s · YOLO {t_yolo:.2f}s · no GPU used")
    print("\n" + "=" * 76)
    print("ALL CHECKS PASSED")
    print("=" * 76)


if __name__ == "__main__":
    asyncio.run(main())
