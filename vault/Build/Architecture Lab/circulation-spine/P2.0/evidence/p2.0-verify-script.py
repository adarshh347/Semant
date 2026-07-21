"""
CIRCULATION-SPINE-001 · P2.0 — live backend verification.

Short-lived, in-process (no long-lived uvicorn — sidesteps the exit-144 blocker). Runs the
REAL detect_regions route + the REAL read handlers against the REAL visualDictionaryDB, using
a DISPOSABLE real post (seeded with a known creator region). Everything is cleaned up in a
finally block so the DB returns to its prior state.

Checks: (V1) persistent run creation, (V2) both retrieval routes + ownership 404,
(V3) actual stage correspondence, (V4) authoritative geometry equivalence,
(V5) write-behind under an intentionally failing telemetry store.
"""
import os, json, asyncio, copy
from datetime import datetime, timezone
from bson.objectid import ObjectId

EVID = os.environ["P2_EVID"]
results = []          # (id, ok, detail)
ev = {"started": None, "checks": [], "counts": {}, "run_id": None,
      "disposable_post_id": None, "source": None, "stages": []}


def check(cid, ok, detail=""):
    results.append((cid, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid}: {detail}")
    ev["checks"].append({"id": cid, "ok": bool(ok), "detail": detail})


FORBIDDEN = {"mask_rle", "mask", "rle", "polygon", "polygons", "bbox", "box",
             "region_annotations", "regions", "segmentation", "contours", "points"}


def has_geometry(x):
    if isinstance(x, dict):
        return any(str(k).lower() in FORBIDDEN for k in x) or any(has_geometry(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return any(has_geometry(v) for v in x)
    return False


async def main():
    from backend.database import post_collection, vision_run_collection
    from backend.routers import posts as R
    from backend.services import vision_run_service as svc
    from backend.schemas.post import RegionDetectRequest
    from fastapi import HTTPException

    ev["started"] = datetime.now(timezone.utc).isoformat()
    base_posts = await post_collection.count_documents({})
    base_runs = await vision_run_collection.count_documents({})
    ev["counts"]["baseline_posts"] = base_posts
    ev["counts"]["baseline_runs"] = base_runs
    print(f"baseline: posts={base_posts} vision_runs={base_runs}")

    # a real, fetchable image URL from an existing post (read-only)
    src = await post_collection.find_one({"photo_url": {"$exists": True, "$ne": None}}, {"photo_url": 1})
    photo_url = src["photo_url"]

    SEED_MASK = {"size": [64, 64], "counts": "P20_SEED_RLE"}
    disposable_id = ObjectId()
    disposable = {
        "_id": disposable_id,
        "caption": "P2.0 DISPOSABLE verification post — safe to delete",
        "photo_url": photo_url,
        "region_annotations": [{
            "id": "p20_creator", "actor": "creator", "detector": "sam2",
            "box": {"x": 0.70, "y": 0.70, "w": 0.20, "h": 0.20},
            "mask_rle": copy.deepcopy(SEED_MASK),
            "user_note": "p2.0 keep me", "prioritised": True, "weight": 7,
            "geometry_provenance": {"via": "refine"},
        }],
    }
    pid = str(disposable_id)
    ev["disposable_post_id"] = pid
    real_run_coll = svc.vision_run_collection            # save to restore after V5

    try:
        await post_collection.insert_one(disposable)
        check("setup.disposable_post_created",
              await post_collection.count_documents({"_id": disposable_id}) == 1,
              f"post_id={pid}")

        # ── V1 · persistent run creation (real route, real Mongo) ──────────────
        resp = await R.detect_regions(pid, RegionDetectRequest(coarse_only=True))
        run_id = resp.get("run_id")
        ev["run_id"] = run_id
        ev["source"] = resp.get("source")
        check("V1.route_returned_run_id", bool(run_id), f"run_id={run_id}")
        raw = await vision_run_collection.find_one({"_id": ObjectId(run_id)})
        ev["retrieved_run_doc"] = copy.deepcopy(raw)     # captured live, before cleanup
        check("V1.run_doc_persisted_in_mongo", raw is not None,
              f"status={raw.get('status') if raw else None} events={len(raw.get('events', [])) if raw else 0}")
        check("V1.run_scoped_to_post", raw and raw.get("post_id") == pid, f"post_id={raw.get('post_id') if raw else None}")
        check("V1.run_operation_is_dissect", raw and raw.get("operation") == "dissect",
              f"operation={raw.get('operation') if raw else None}")
        check("V1.run_terminal_status", raw and raw.get("status") in ("succeeded", "partial"),
              f"status={raw.get('status') if raw else None}, reason={raw.get('terminal_reason') if raw else None}")

        # ── V2 · both retrieval routes + ownership 404 ─────────────────────────
        got = await R.get_vision_run(pid, run_id)          # GET /vision-runs/{run_id}
        got = got if isinstance(got, dict) else got.model_dump()
        check("V2.get_run_route", got.get("run_id") == run_id and got.get("post_id") == pid,
              f"returned run_id={got.get('run_id')}")
        check("V2.get_run_has_events", len(got.get("events", [])) == len(raw.get("events", [])),
              f"events={len(got.get('events', []))}")
        latest = await R.get_latest_vision_run(pid)        # GET /vision-runs/latest
        lrun = latest.get("run")
        check("V2.get_latest_route", lrun and lrun.get("run_id") == run_id,
              f"latest run_id={lrun.get('run_id') if lrun else None}")
        try:
            await R.get_vision_run("0" * 24, run_id)       # wrong post → must 404
            check("V2.ownership_404", False, "did not raise")
        except HTTPException as e:
            check("V2.ownership_404", e.status_code == 404, f"status={e.status_code}")

        # ── V3 · actual stage correspondence ───────────────────────────────────
        stages = [e["stage_id"] for e in raw["events"]]
        statuses = {e["stage_id"]: e["status"] for e in raw["events"]}
        ev["stages"] = stages
        source = resp["source"]
        check("V3.receive_fetch_route_present",
              all(s in stages for s in ["dissect.receive", "dissect.fetch_image", "dissect.route_domain"]),
              f"stages={stages}")
        check("V3.decompose_absent_when_coarse_only", "dissect.decompose_fine" not in stages,
              "coarse_only=True → no fine stage")
        check("V3.persist_stage_succeeded", statuses.get("dissect.persist_regions") == "succeeded",
              f"persist status={statuses.get('dissect.persist_regions')} (real post exists → matched)")
        check("V3.complete_present", "dissect.complete" in stages, "")
        # segment stages correspond to the source string bits
        src_ok = (("segformer_clothes" in source) == ("dissect.segment.fashion" in stages)) and \
                 (("segformer_ade" in source) == ("dissect.segment.architecture" in stages))
        general_ok = ("dissect.segment.general" in stages) or ("dissect.fallback.detect" in stages)
        check("V3.segment_stages_match_source", src_ok and general_ok,
              f"source={source!r} segment_stages={[s for s in stages if 'segment' in s or 'fallback' in s]}")

        # ── V4 · authoritative geometry equivalence ────────────────────────────
        post_after = await post_collection.find_one({"_id": disposable_id})
        persisted = post_after.get("region_annotations") or []
        returned = resp["regions"]
        check("V4.persisted_equals_returned", persisted == returned,
              f"persisted={len(persisted)} returned={len(returned)} equal={persisted == returned}")
        cre = next((r for r in persisted if r.get("id") == "p20_creator"), None)
        check("V4.creator_region_survived", cre is not None and cre.get("actor") == "creator",
              f"found={cre is not None}")
        check("V4.creator_mask_rle_unchanged", cre and cre.get("mask_rle") == SEED_MASK,
              f"mask_rle={cre.get('mask_rle') if cre else None}")
        check("V4.creator_curator_fields_preserved",
              cre and cre.get("user_note") == "p2.0 keep me" and cre.get("weight") == 7 and cre.get("prioritised") is True,
              f"note={cre.get('user_note') if cre else None} weight={cre.get('weight') if cre else None}")
        auto_masks = [r for r in persisted if r.get("id") != "p20_creator" and r.get("mask_rle")]
        check("V4.auto_regions_carry_authoritative_mask_rle", len(auto_masks) >= 1,
              f"{len(auto_masks)} auto region(s) with mask_rle (real YOLO geometry)")
        # geometry must NEVER be inside telemetry events
        leak = any(has_geometry(e.get("detail")) or has_geometry(e.get("input_refs")) or
                   has_geometry(e.get("output_refs")) for e in raw["events"])
        check("V4.no_geometry_in_events", not leak, "no mask/box/polygon key in any event payload")

        # ── V5 · write-behind under an intentionally failing telemetry store ────
        runs_for_post_before = await vision_run_collection.count_documents({"post_id": pid})

        class FailingStore:
            async def insert_one(self, doc):
                raise RuntimeError("INTENTIONAL telemetry store failure (P2.0 write-behind test)")

        svc.vision_run_collection = FailingStore()         # only telemetry fails; post write stays REAL
        try:
            resp2 = await R.detect_regions(pid, RegionDetectRequest(coarse_only=True))
        finally:
            svc.vision_run_collection = real_run_coll       # restore immediately

        check("V5.route_survived_telemetry_failure", "regions" in resp2 and resp2.get("run_id") is None,
              f"run_id={resp2.get('run_id')} (None) regions={len(resp2.get('regions', []))}")
        post_wb = await post_collection.find_one({"_id": disposable_id})
        check("V5.real_region_persist_still_happened",
              bool(post_wb.get("region_annotations")) and
              any(r.get("id") == "p20_creator" for r in post_wb["region_annotations"]),
              f"regions persisted={len(post_wb.get('region_annotations', []))}, creator preserved")
        runs_for_post_after = await vision_run_collection.count_documents({"post_id": pid})
        check("V5.no_run_doc_created_on_failure", runs_for_post_after == runs_for_post_before,
              f"runs for post before={runs_for_post_before} after={runs_for_post_after}")

    finally:
        # ── restore: delete disposable post + all its runs; verify DB baseline ──
        del_post = await post_collection.delete_one({"_id": disposable_id})
        del_runs = await vision_run_collection.delete_many({"post_id": pid})
        fin_posts = await post_collection.count_documents({})
        fin_runs = await vision_run_collection.count_documents({})
        ev["counts"]["final_posts"] = fin_posts
        ev["counts"]["final_runs"] = fin_runs
        ev["counts"]["deleted_disposable_post"] = del_post.deleted_count
        ev["counts"]["deleted_runs"] = del_runs.deleted_count
        check("cleanup.disposable_post_deleted", del_post.deleted_count == 1, "")
        check("cleanup.db_restored_to_baseline", fin_posts == base_posts and fin_runs == base_runs,
              f"posts {base_posts}->{fin_posts}, runs {base_runs}->{fin_runs}")

    ev["finished"] = datetime.now(timezone.utc).isoformat()
    ev["all_passed"] = all(ok for _, ok, _ in results)
    ev["summary"] = {"total": len(results), "passed": sum(1 for _, ok, _ in results if ok),
                     "failed": sum(1 for _, ok, _ in results if not ok)}
    with open(os.path.join(EVID, "p2.0-verification-evidence.json"), "w") as f:
        json.dump(ev, f, indent=2, default=str)
    # the actual vision_runs document retrieved live from real Mongo (before cleanup)
    with open(os.path.join(EVID, "p2.0-retrieved-run.json"), "w") as f:
        json.dump({"note": "raw vision_runs doc retrieved live from visualDictionaryDB, before cleanup",
                   "run": ev.get("retrieved_run_doc")}, f, indent=2, default=str)
    print(f"\n=== {ev['summary']['passed']}/{ev['summary']['total']} checks passed; "
          f"all_passed={ev['all_passed']} ===")


asyncio.run(main())
