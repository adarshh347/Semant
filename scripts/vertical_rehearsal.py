#!/usr/bin/env python
"""
ATLAS-WRITER-MASS-BUILD-001L — the vertical rehearsal.

    python scripts/vertical_rehearsal.py                 # offline: deterministic fakes, core CI path
    python scripts/vertical_rehearsal.py --mode live     # whatever declared providers are present
    python scripts/vertical_rehearsal.py --both          # the gate: offline, then live
    python scripts/vertical_rehearsal.py --list-stages

One command: a disposable mongod, the real backend (through `app_entry`, fakes bound at the model /
GPU seams only), the real Vite frontend, a real Chromium, and the whole circuit driven through the
UI. Leaves `summary.json`, `report.md`, screenshots, timings and before/after hashes in the run
directory (`research/rehearsals/vertical/runs/<run-id>/` by default).

Exit code: 0 when the gate passes, 2 when it is blocked by a lane that has not merged (every stage
that ran passed; the unavailable ones name their lane), 1 on a failed stage or assertion, 3 on a
harness error before any stage ran. A missing provider credential in live mode is a precise
`unavailable`, never a pass.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.vertical_rehearsal_support import checks, corpus as C, profiles, report, stages  # noqa: E402
from scripts.vertical_rehearsal_support.ledger import Evidence  # noqa: E402
from scripts.vertical_rehearsal_support.runner import Api, Run, StageSkipped  # noqa: E402
from scripts.vertical_rehearsal_support.stack import Stack  # noqa: E402

RUNS_ROOT = ROOT / "research" / "rehearsals" / "vertical" / "runs"

STAGES = [
    ("walk.save_open", stages.stage_walk_save_open, None),
    ("atlas.canvas", stages.stage_atlas_canvas, None),
    ("atlas.light_table", stages.stage_light_table, None),
    ("differential", stages.stage_differential, lambda r: [r.post_ids["core-0"]]),
    ("relation", stages.stage_relation,
     lambda r: [r.post_ids["core-1"], r.post_ids["core-2"]]),
    ("plan", stages.stage_plan, None),
    ("draft", stages.stage_draft, None),
    ("draft.accept", stages.stage_draft_accept, None),
    ("api.target_manuscript", stages.stage_api_target_manuscript, None),
    ("writer", stages.stage_writer, None),
    ("movement", stages.stage_movement, None),
    ("profile.lost_response", profiles.profile_lost_response,
     lambda r: [r.state["walk_posts"][2], r.state["walk_posts"][3]]),
    ("profile.restart_mid", profiles.profile_restart_mid_transition, None),
    ("profile.stale_tab", profiles.profile_stale_tab, None),
    ("profile.unavailable_model", profiles.profile_unavailable_model, None),
    ("profile.unreadable_image", profiles.profile_unreadable_image,
     lambda r: [r.post_ids["core-unreadable"]]),      # the harness deletes that post on purpose
    ("profile.injected_writes", profiles.profile_injected_writes,
     lambda r: list(r.state.get("walk_posts", []))),
    ("a11y", checks.check_a11y, None),
    ("performance", checks.check_performance, None),
]


def git_meta() -> dict:
    def _g(*a):
        try:
            return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""
    return {"commit": _g("rev-parse", "HEAD"), "branch": _g("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_g("status", "--porcelain", "--", "backend", "frontend/src", "scripts"))}


def run_once(args, mode: str) -> int:
    run_id = args.run_id or f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{mode}"
    run_dir = Path(args.out) if args.out else RUNS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== vertical rehearsal · {run_id} · mode={mode} profile={args.profile} → {run_dir}", flush=True)
    started = datetime.now(timezone.utc).isoformat()

    # the corpus
    # Performance rows FIRST: the Atlas index lists the 24 newest posts by `_id`, and ObjectIds
    # are minted in this order, so the core walk must be minted last to be offered.
    rows = C.perf_manifest(60) + C.core_manifest()
    profile_rows = None
    if args.profile == "real-photo":
        profile_rows = C.real_photo_profile()
        if profile_rows is None:
            print("  real-photo profile requested but SEMANT_VERTICAL_REAL_PHOTOS is unset or has no "
                  "marks.json — the profile is `unavailable`; running the synthetic corpus.", flush=True)
        else:
            rows += profile_rows
    images_dir = run_dir / "images"
    digests = C.render_all([r for r in rows if "source_file" not in r], images_dir)
    for r in rows:
        if "source_file" in r:
            import shutil
            shutil.copy(r["source_file"], images_dir / f"{r['key']}.png")

    fakes = "all" if mode == "offline" else ("ml_only" if not args.real_ml else "none")
    if mode == "live":
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    stack = Stack(run_dir=run_dir, keep=args.keep, fakes=fakes, frontend_mode=args.frontend)
    failed = True
    preserved = {}
    run = None
    try:
        stack.start(images_dir)
        print(f"  stack up: {stack.boot_seconds}  api={stack.api_url} app={stack.app_url}", flush=True)
        from pymongo import MongoClient
        db = MongoClient(stack.mongo_uri).visualDictionaryDB
        # The Atlas index lists the 24 most recently updated posts; the core walk must be among
        # them, so the performance corpus is stamped a day older.
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        docs = [C.post_document(r, stack.image_url,
                                now=now - (timedelta(days=1) if r["key"].startswith("perf-") else timedelta(0)))
                for r in rows]
        db.posts.insert_many(docs)
        api = Api(stack.api_url, stack.api_key)
        run = Run(run_id=run_id, run_dir=run_dir, mode=mode, profile=args.profile, stack=stack, db=db,
                  api=api, evidence=Evidence(), headed=args.headed, slow=args.slow)
        run.posts = {r["key"]: d for r, d in zip(rows, docs)}
        run.post_ids = {r["key"]: str(d["_id"]) for r, d in zip(rows, docs)}
        run.state["unmarked_node_post"] = None
        receipts = api.get("/__rehearsal/receipts")[1]
        before = run.hash_posts()
        (run_dir / "hashes-before.json").write_text(json.dumps(before, indent=1))
        (run_dir / "corpus.json").write_text(json.dumps(
            {"rows": rows, "png_sha256": digests, "post_ids": run.post_ids,
             "profile": args.profile, "real_photo_available": profile_rows is not None}, indent=1, default=str))

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            run.browser = p.chromium.launch(headless=not args.headed, slow_mo=args.slow)
            only = set(args.stages.split(",")) if args.stages else None
            skip = set(args.skip.split(",")) if args.skip else set()
            for name, fn, expected in STAGES:
                if (only and name not in only) or name in skip:
                    run.stage(name, lambda r: (_ for _ in ()).throw(StageSkipped("not selected")))
                    continue
                if mode == "live" and name == "performance" and not args.perf_in_live:
                    run.stage(name, lambda r: (_ for _ in ()).throw(StageSkipped("performance profile runs offline; pass --perf-in-live")))
                    continue
                run.stage(name, fn, expected_post_writes=expected)
                if not stack.backend_alive():
                    print("  backend is down; restarting before the next stage", flush=True)
                    stack.restart_backend()
            run.browser.close()

        after = run.hash_posts()
        (run_dir / "hashes-after.json").write_text(json.dumps(after, indent=1))
        asserts = report.assertions(run)
        meta = {"mode": mode, "profile": args.profile, "started_at": started, "base": git_meta(),
                "provider_receipts": receipts.get("receipts", []),
                "corpus": {"images": len(rows), "png_sha256": digests,
                           "real_photo_profile": "ran" if profile_rows else ("unavailable" if args.profile == "real-photo" else "not requested")},
                "timings_ms": run.evidence.timings}
        g = report.gate(run, asserts)
        failed = g["status"] == "fail"
        preserved = stack.stop(failed=failed)
        meta["preserved"] = preserved
        summary = report.write_summary(run, meta, asserts, before, after)
        rep = report.write_report(run, summary)
        print(f"\n  gate: {g['status']}  assertions {g['assertions_passed']}/{g['assertions_total']}  "
              f"lanes blocking: {g['lanes_preventing_full_pass'] or 'none'}")
        print(f"  summary: {summary}\n  report:  {rep}", flush=True)
        return {"pass": 0, "blocked": 2, "fail": 1}[g["status"]]
    except Exception as e:  # noqa: BLE001
        import traceback
        (run_dir / "logs").mkdir(exist_ok=True, parents=True)
        (run_dir / "logs" / "harness-fatal.log").write_text(traceback.format_exc())
        print(f"  harness error: {type(e).__name__}: {e}", flush=True)
        if run is not None and run.results:
            try:
                after = run.hash_posts()
            except Exception:  # noqa: BLE001
                after = {}
            asserts = report.assertions(run) if stack.backend_alive() else []
            meta = {"mode": mode, "profile": args.profile, "started_at": started, "base": git_meta(),
                    "provider_receipts": [], "corpus": {}, "harness_error": f"{type(e).__name__}: {e}"}
            preserved = stack.stop(failed=True)
            meta["preserved"] = preserved
            summary = report.write_summary(run, meta, asserts, before, after)
            report.write_report(run, summary)
        else:
            preserved = stack.stop(failed=True)
        print(f"  preserved: {preserved}", flush=True)
        return 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["offline", "live"], default="offline")
    ap.add_argument("--both", action="store_true", help="the gate: offline, then live")
    ap.add_argument("--profile", choices=["default", "real-photo"], default="default")
    ap.add_argument("--stages", help="comma-separated stage names to run (others are skipped)")
    ap.add_argument("--skip", help="comma-separated stage names to skip")
    ap.add_argument("--keep", action="store_true", help="preserve the mongod dbpath after a passing run")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--slow", type=int, default=0, help="slow_mo in ms")
    ap.add_argument("--frontend", choices=["dev", "preview"], default="preview",
                    help="preview = the production Vite build served by `vite preview` (the gate's "
                         "Vite build); dev = the dev server (faster start, React StrictMode on)")
    ap.add_argument("--out", help="run directory (default research/rehearsals/vertical/runs/<run-id>)")
    ap.add_argument("--run-id")
    ap.add_argument("--real-ml", action="store_true", help="live mode: do not fake GPU producers either")
    ap.add_argument("--perf-in-live", action="store_true")
    ap.add_argument("--list-stages", action="store_true")
    args = ap.parse_args(argv)
    if args.list_stages:
        for name, fn, _ in STAGES:
            print(f"{name:28s} {(fn.__doc__ or '').strip().splitlines()[0] if fn.__doc__ else ''}")
        return 0
    if args.both:
        a = run_once(args, "offline")
        b = run_once(args, "live")
        return max(a, b)
    return run_once(args, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
