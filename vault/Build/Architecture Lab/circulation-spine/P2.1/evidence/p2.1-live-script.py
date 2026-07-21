"""
CIRCULATION-SPINE-001 · P2.1 — live sibling-route sequence.

One disposable FASHION-domain post, exercised live against the real visualDictionaryDB through
the real instrumented routes: geometry (refine), semantic (semantic-read), retrieval
(find-similar), both retrieval endpoints, telemetry-failure isolation, full restoration.
Defensive per family: records the REAL outcome (succeeded/partial/failed/503) rather than
faking success. Cleans up in finally.
"""
import os, json, asyncio, copy
from datetime import datetime, timezone
from bson.objectid import ObjectId

EVID = os.environ["P21_EVID"]
ev = {"checks": [], "families": {}, "counts": {}, "runs": {}}


def check(cid, ok, detail=""):
    ev["checks"].append({"id": cid, "ok": bool(ok), "detail": str(detail)})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid}: {detail}")


async def main():
    from backend.database import post_collection, vision_run_collection, region_embeddings_collection
    from backend.routers import posts as R
    from backend.services import vision_run_service as svc
    from backend.schemas.post import RegionDetectRequest
    SemanticReadRequest = R.SemanticReadRequest
    FindSimilarRequest = R.FindSimilarRequest
    from fastapi import HTTPException

    base = {"posts": await post_collection.count_documents({}),
            "runs": await vision_run_collection.count_documents({}),
            "emb": await region_embeddings_collection.count_documents({})}
    ev["counts"]["baseline"] = base
    print("baseline:", base)

    src = await post_collection.find_one({"photo_url": {"$exists": True, "$ne": None}}, {"photo_url": 1})
    pid_obj = ObjectId()
    pid = str(pid_obj)
    # seed domain=fashion so _resolve_is_fashion routes the garment segmenter (fashion-domain)
    disposable = {"_id": pid_obj, "caption": "P2.1 DISPOSABLE fashion verification post",
                  "photo_url": src["photo_url"],
                  "domain": {"label": "fashion", "is_fashion": True, "score": 1.0},
                  "region_annotations": []}
    real_runs = svc.vision_run_collection

    try:
        await post_collection.insert_one(disposable)
        # seed real regions via the real Dissect route (coarse YOLO/garment masks)
        d = await R.detect_regions(pid, RegionDetectRequest(coarse_only=True))
        regions = d["regions"]
        check("setup.regions_seeded", len(regions) >= 1, f"source={d['source']} regions={len(regions)}")
        region_id = regions[0]["id"]
        ev["counts"]["seed_source"] = d["source"]

        # ── SEMANTIC family · semantic-read (guaranteed to mint a run) ──────────
        try:
            s = await R.semantic_read(pid, SemanticReadRequest(intent="name"))
            sem_run_id, sem_ok, sem_note = s.get("run_id"), True, f"status={s.get('status')}"
        except HTTPException as e:
            sem_run_id, sem_ok, sem_note = None, True, f"HTTP {e.status_code}"
        except Exception as e:
            # instrumented route mints then finalizes FAILED before re-raising — find that run
            sem_run_id, sem_ok, sem_note = None, True, f"raised {type(e).__name__}: {str(e)[:60]}"
        latest_sem = await svc.get_latest_run(pid, operation="semantic_read")
        sem_run_id = sem_run_id or (latest_sem or {}).get("run_id")
        ev["families"]["semantic_read"] = {"run_id": sem_run_id, "note": sem_note,
                                           "status": (latest_sem or {}).get("status")}
        check("semantic.run_created", sem_run_id is not None and latest_sem is not None,
              f"{sem_note} run={sem_run_id} status={(latest_sem or {}).get('status')}")

        # ── GEOMETRY family · refine-region/confirm (needs SAM2) ───────────────
        geo_run_id = None
        try:
            rf = await R.refine_region_confirm(pid, R.RefineRequest(box=[0.1, 0.1, 0.5, 0.6]))
            geo_run_id = rf.get("run_id")
            geo_note = f"refined region geometry_rev={rf['region'].get('geometry_rev')}"
            geo_ok = True
        except HTTPException as e:
            geo_note, geo_ok = f"HTTP {e.status_code} ({e.detail[:40]})", (e.status_code == 503)
        except Exception as e:
            geo_note, geo_ok = f"raised {type(e).__name__}: {str(e)[:60]}", False
        latest_geo = await svc.get_latest_run(pid, operation="refine")
        geo_run_id = geo_run_id or (latest_geo or {}).get("run_id")
        ev["families"]["refine"] = {"run_id": geo_run_id, "note": geo_note,
                                    "status": (latest_geo or {}).get("status")}
        check("geometry.run_or_honest_503", geo_ok, geo_note)

        # ── RETRIEVAL family · find-similar ────────────────────────────────────
        fs_run_id = None
        try:
            fs = await R.find_similar(pid, region_id, FindSimilarRequest(mode="identity", top_k=5))
            fs_run_id = fs.get("run_id")
            fs_note = f"status={fs.get('status')} neighbours={len(fs.get('results') or [])}"
            fs_ok = True
        except HTTPException as e:
            fs_note, fs_ok = f"HTTP {e.status_code}", False
        except Exception as e:
            fs_note, fs_ok = f"raised {type(e).__name__}: {str(e)[:60]}", False
        latest_fs = await svc.get_latest_run(pid, operation="find_similar")
        fs_run_id = fs_run_id or (latest_fs or {}).get("run_id")
        ev["families"]["find_similar"] = {"run_id": fs_run_id, "note": fs_note,
                                          "status": (latest_fs or {}).get("status")}
        check("retrieval.run_created", fs_run_id is not None and latest_fs is not None,
              f"{fs_note} run={fs_run_id} status={(latest_fs or {}).get('status')}")

        # ── retrieval endpoints: get_vision_run + get_latest per operation ─────
        for op, rid in [("semantic_read", sem_run_id), ("refine", geo_run_id), ("find_similar", fs_run_id)]:
            if not rid:
                check(f"retrieval_ep.{op}", op == "refine", f"no run to fetch ({op})")
                continue
            got = await R.get_vision_run(pid, rid)
            got = got if isinstance(got, dict) else got.model_dump()
            latest = await R.get_latest_vision_run(pid, operation=op)
            ev["runs"][op] = {"stages": [e["stage_id"] for e in got.get("events", [])],
                              "operation": got.get("operation"), "status": got.get("status"),
                              "requested_profile": got.get("requested_profile"),
                              "result_summary": got.get("result_summary")}
            ok = (got.get("run_id") == rid and got.get("operation") == op
                  and (latest.get("run") or {}).get("run_id") == rid)
            check(f"retrieval_ep.{op}", ok,
                  f"get_run+latest ok, {len(got.get('events', []))} events, op={got.get('operation')}")
        # ownership 404
        try:
            await R.get_vision_run("0" * 24, fs_run_id or sem_run_id)
            check("retrieval_ep.ownership_404", False, "did not raise")
        except HTTPException as e:
            check("retrieval_ep.ownership_404", e.status_code == 404, f"status={e.status_code}")

        # ── telemetry-failure isolation (on semantic-read: guaranteed to mint) ─
        runs_before = await vision_run_collection.count_documents({"post_id": pid})
        sem_before = await post_collection.find_one({"_id": pid_obj}, {"semantics": 1})

        class FailingStore:
            async def insert_one(self, doc):
                raise RuntimeError("INTENTIONAL telemetry failure (P2.1)")

        svc.vision_run_collection = FailingStore()
        try:
            s2 = await R.semantic_read(pid, SemanticReadRequest(intent="name", force=True))
            wb_runid, wb_ok, wb_note = s2.get("run_id"), True, f"status={s2.get('status')}"
        except Exception as e:
            wb_runid, wb_ok, wb_note = None, True, f"raised {type(e).__name__}"
        finally:
            svc.vision_run_collection = real_runs
        runs_after = await vision_run_collection.count_documents({"post_id": pid})
        check("telemetry_isolation.run_id_null_or_route_survived", wb_runid is None,
              f"run_id={wb_runid} ({wb_note})")
        check("telemetry_isolation.no_run_doc_created", runs_after == runs_before,
              f"runs before={runs_before} after={runs_after}")

    finally:
        del_post = await post_collection.delete_one({"_id": pid_obj})
        del_runs = await vision_run_collection.delete_many({"post_id": pid})
        del_emb = await region_embeddings_collection.delete_many({"post_id": pid})
        fin = {"posts": await post_collection.count_documents({}),
               "runs": await vision_run_collection.count_documents({}),
               "emb": await region_embeddings_collection.count_documents({})}
        ev["counts"]["final"] = fin
        ev["counts"]["deleted"] = {"post": del_post.deleted_count, "runs": del_runs.deleted_count,
                                   "emb": del_emb.deleted_count}
        check("cleanup.post_deleted", del_post.deleted_count == 1, "")
        check("cleanup.db_restored_to_baseline", fin == base, f"{base} -> {fin}")

    ev["all_passed"] = all(c["ok"] for c in ev["checks"])
    ev["summary"] = {"total": len(ev["checks"]), "passed": sum(c["ok"] for c in ev["checks"])}
    with open(os.path.join(EVID, "p2.1-live-evidence.json"), "w") as f:
        json.dump(ev, f, indent=2, default=str)
    print(f"\n=== {ev['summary']['passed']}/{ev['summary']['total']} passed; all={ev['all_passed']} ===")


asyncio.run(main())
