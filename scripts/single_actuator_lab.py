#!/usr/bin/env python3
"""HARNESS-001C — the single-actuator orchestration laboratory. CLI.

    python scripts/single_actuator_lab.py capture  --manifest <yaml>
    python scripts/single_actuator_lab.py replay   --run <run-dir>
    python scripts/single_actuator_lab.py compare  --runs <run-a> <run-b> [<run-c>]
    python scripts/single_actuator_lab.py validate --run <run-dir> | --manifest <yaml>

RESEARCH ONLY. Writes to `research/rehearsals/labs/runs/<run_id>/` and nowhere else. It defines
no production entity, route or collection, and the running app does not import it.

`capture` REFUSES TO OVERWRITE A FROZEN RUN. A run directory holding a trace is evidence, and
evidence that can be silently replaced by a later run under the same name is not evidence. Use a
new run id; the manifest carries one.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from single_actuator_lab_support import arms, contract, observe, report, scoring, visuals  # noqa: E402
from single_actuator_lab_support.firewall import Firewall  # noqa: E402


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ── capture ───────────────────────────────────────────────────────────────────────────────────

def capture(manifest_path: str, *, runs_root: str = contract.RUNS_ROOT,
            planner_client: Any = None, force: bool = False,
            deterministic: Optional[bool] = None) -> Dict[str, Any]:
    """Run one manifest and freeze everything it produced."""
    manifest = contract.check_manifest(contract.load_manifest(manifest_path),
                                       source=manifest_path)
    if deterministic is not None:
        repro = dict(manifest.get("reproducibility") or {})
        repro["deterministic_framer"] = bool(deterministic)
        manifest["reproducibility"] = repro

    run_path = contract.run_dir(manifest["run_id"], runs_root)
    if contract.is_frozen(run_path) and not force:
        raise SystemExit(
            f"refusing to overwrite the frozen run at {run_path}. Use a new run_id — a frozen "
            f"run is evidence, and evidence that can be replaced under the same name is not.")

    mode = manifest["mode"]
    if mode == "replay":
        raise SystemExit("mode 'replay' is not captured; use `replay --run <run-dir>`")

    image_path, image_bytes, digest_before = contract.resolve_image(manifest)
    env = contract.environment_receipt(manifest)

    firewall = Firewall(manifest["actuator_lock"],
                        call_budget=int(manifest.get("call_budget", 1)),
                        allowed_params=manifest.get("allowed_params"))

    prompt_receipt: Dict[str, Any] = {
        "original_prompt": manifest.get("prompt"),
        "prompt_sha256": (contract.sha256_bytes(manifest["prompt"].encode("utf-8"))
                          if manifest.get("prompt") else None),
        "control_phrase": manifest.get("control_phrase"),
        "planner_role": None,
        "planner_model": None,
        "planner_status": "not_applicable",
        "planner_detail": None,
        "raw_proposal": None,
    }
    decision: Dict[str, Any] = {
        "catalogue_shown": firewall.catalogue(),
        "selected_actuator": None,
        "selected_phrase": None,
        "phrase_source": None,
        "refused_actions": [],
        "dropped_params": [],
        "planner_notes": [],
    }
    actuator_observation: Optional[Dict[str, Any]] = None

    with firewall:                       # database writes instrumented for the whole capture
        if mode == "organ_direct":
            phrase = manifest["control_phrase"]
            decision.update({"selected_actuator": firewall.lock, "selected_phrase": phrase,
                             "phrase_source": "control"})
            organ = arms.organ_direct(manifest, firewall, image_bytes, phrase, env)

        elif mode == "actuator_direct":
            phrase = manifest["control_phrase"]
            decision.update({"selected_actuator": firewall.lock, "selected_phrase": phrase,
                             "phrase_source": "control"})
            organ, actuator_observation = arms.actuator_direct(
                manifest, firewall, image_bytes, phrase, env)

        elif mode == "prompt_orchestrated":
            receipt, extras, organ, actuator_observation = arms.prompt_orchestrated(
                manifest, firewall, image_bytes, env, client=planner_client)
            prompt_receipt.update(receipt)
            decision.update({k: v for k, v in extras.items() if k != "planner_notes"})
            decision["planner_notes"] = extras.get("planner_notes") or []
            actuator_observation = actuator_observation or None
        else:                                                  # unreachable via the schema
            raise SystemExit(f"unknown mode {mode!r}")

        repeats = int(manifest.get("repeat_count", 1) or 1)
        if repeats > 1:
            organ["repeats"] = _repeat(manifest, image_bytes, env, organ, repeats)

    env["imgsz_effective"], env["imgsz_note"] = contract.imgsz_receipt()

    receipts = firewall.receipts()
    decision["refused_actions"] = receipts["refused_actions"]
    decision["dropped_params"] = receipts["dropped_params"]

    # Read from disk again, deliberately, rather than trusting the bytes still in memory: the
    # claim is that the file did not change, and the in-memory copy cannot witness that.
    digest_after = contract.sha256_file(image_path)
    rles = [r for r in (organ.get("_rles") or []) if isinstance(r, dict)]
    organ["max_pairwise_iou"] = observe.max_pairwise_iou(rles) if len(rles) > 1 else None
    if organ.get("repeats"):
        organ["repeat_stability"] = _stability(organ)

    trace: Dict[str, Any] = {
        "schema_version": contract.TRACE_VERSION,
        "lab_id": manifest["lab_id"],
        "run_id": manifest["run_id"],
        "mode": mode,
        "actuator_lock": manifest["actuator_lock"],
        "captured_at": _now(),
        "manifest": manifest,
        "environment": env,
        "prompt_receipt": prompt_receipt,
        "decision_receipt": decision,
        "invocations": receipts["invocations"],
        "organ_observation": organ,
        "actuator_observation": actuator_observation,
        "invariance": {
            "image_sha256_before": digest_before,
            "image_sha256_after": digest_after,
            "image_unchanged": digest_before == digest_after,
            "actuators_called": firewall.actuators_called,
            "lock_held": firewall.lock_held,
            "database_writes_attempted": receipts["database_writes_attempted"],
            "post_mutated": bool(actuator_observation
                                 and actuator_observation.get("post_sha256_before")
                                 != actuator_observation.get("post_sha256_after")),
            "post_sha256_before": (actuator_observation or {}).get("post_sha256_before"),
            "post_sha256_after": (actuator_observation or {}).get("post_sha256_after"),
        },
        "artifacts": {"overlay": None, "contact_sheet": None, "review": None,
                      "observations": []},
    }

    _freeze(trace, manifest, run_path, image_path)
    score = scoring.build_score(trace, manifest)
    contract.validate(trace, "trace", raise_on_error=True)
    contract.validate(score, "score", raise_on_error=True)
    contract.write_json(os.path.join(run_path, "trace.json"), trace)
    contract.write_json(os.path.join(run_path, "score.json"), score)
    report.render_review(trace, score, manifest, os.path.join(run_path, "review.md"))
    return {"trace": trace, "score": score, "run_path": run_path}


def _repeat(manifest: Dict[str, Any], image_bytes: bytes, env: Dict[str, Any],
            first: Dict[str, Any], repeats: int) -> List[Dict[str, Any]]:
    """Re-issue the SAME frozen call, each through its own budget-1 firewall.

    A repeat is not a second chance. The call is byte-identical to the first, no planner runs,
    and each repeat gets a fresh firewall so the budget of one is never widened — what is being
    measured is whether the organ is deterministic, not whether a different attempt does better.
    Phrase stability is a different question and is answered by `compare` across separate
    orchestrated runs, because repeating a PLANNER call inside one capture would break the
    one-call discipline that makes Arm C readable.
    """
    out: List[Dict[str, Any]] = []
    phrase = first.get("concept")
    for n in range(2, repeats + 1):
        fw = Firewall(manifest["actuator_lock"], call_budget=1,
                      allowed_params=manifest.get("allowed_params"))
        warm_manifest = dict(manifest, warm_or_cold="warm")
        obs = arms.organ_direct(warm_manifest, fw, image_bytes, phrase, env)
        out.append({
            "repeat": n,
            "status": obs["status"],
            "instance_count": obs["instance_count"],
            "latency_ms": obs.get("latency_ms"),
            "mask_hashes": [i["mask_rle_sha256"] for i in obs["instances"]],
            "invocations": fw.receipts()["invocations"],
        })
    return out


def _stability(organ: Dict[str, Any]) -> Dict[str, Any]:
    first = [i["mask_rle_sha256"] for i in organ.get("instances") or []]
    repeats = organ.get("repeats") or []
    all_hashes = [first] + [r["mask_hashes"] for r in repeats]
    return {
        "repeats": len(all_hashes),
        "identical_mask_hashes": all(h == first for h in all_hashes),
        "instance_counts": [len(h) for h in all_hashes],
        "min_pairwise_iou": None,
        # Null and it stays null: phrase stability requires repeated PLANNER calls, and this
        # lab runs the planner exactly once per capture. `compare` answers it across runs.
        "phrase_stable": None,
    }


def _freeze(trace: Dict[str, Any], manifest: Dict[str, Any], run_path: str,
            image_path: str) -> None:
    """Write the observations, the overlay and the contact sheet. The masks live HERE, once."""
    organ = trace["organ_observation"]
    raw = organ.pop("_rles", [])
    os.makedirs(os.path.join(run_path, "observations"), exist_ok=True)
    names: List[str] = []
    for inst, rle in zip(organ.get("instances") or [], raw):
        name = f"instance-{inst['index']:03d}.json"
        contract.write_json(os.path.join(run_path, "observations", name), inst)
        names.append(f"observations/{name}")
    if raw:
        contract.write_json(os.path.join(run_path, "observations", "masks.json"),
                            {"concept": organ.get("concept"), "masks": raw})
        names.append("observations/masks.json")
    trace["artifacts"]["observations"] = names

    if raw:
        instances = [dict(i, mask_rle=r) for i, r in zip(organ["instances"], raw)]
        overlay = visuals.render_overlay(image_path, instances,
                                         os.path.join(run_path, "overlay.png"))
        sheet = visuals.render_contact_sheet(image_path, instances,
                                             os.path.join(run_path, "contact-sheet.png"))
        trace["artifacts"]["overlay"] = "overlay.png" if overlay else None
        trace["artifacts"]["contact_sheet"] = "contact-sheet.png" if sheet else None
    trace["artifacts"]["review"] = "review.md"


# ── replay ────────────────────────────────────────────────────────────────────────────────────

def replay(run_path: str, *, out_path: Optional[str] = None) -> Dict[str, Any]:
    """Rebuild trace and score from frozen observations. Zero live calls, enforced.

    The firewall is constructed in replay mode and entered for the whole rebuild, so any
    invocation raises rather than being merely absent by good behaviour.
    """
    frozen = contract.read_json(os.path.join(run_path, "trace.json"))
    manifest = frozen.get("manifest") or {}
    fw = Firewall(frozen["actuator_lock"], call_budget=int(manifest.get("call_budget", 1)),
                  replay=True)
    with fw:
        trace, divergences = arms.replay(run_path)

    score = scoring.build_score(trace, dict(manifest, mode="replay"))
    score["mode"] = "replay"
    contract.validate(trace, "trace", raise_on_error=True)
    contract.validate(score, "score", raise_on_error=True)
    target = out_path or run_path
    if target != run_path:
        contract.write_json(os.path.join(target, "trace.json"), trace)
        contract.write_json(os.path.join(target, "score.json"), score)
    return {"trace": trace, "score": score, "divergences": divergences,
            "live_calls": len(fw.attempts)}


# ── compare / validate ────────────────────────────────────────────────────────────────────────

def compare(run_paths: List[str]) -> Dict[str, Any]:
    runs = [{"trace": contract.read_json(os.path.join(p, "trace.json")),
             "score": contract.read_json(os.path.join(p, "score.json"))} for p in run_paths]
    return report.compare(runs)


def validate_run(run_path: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    trace_path = os.path.join(run_path, "trace.json")
    score_path = os.path.join(run_path, "score.json")
    if os.path.exists(trace_path):
        out["trace"] = contract.validate(contract.read_json(trace_path), "trace")
    if os.path.exists(score_path):
        out["score"] = contract.validate(contract.read_json(score_path), "score")
    manifest = (contract.read_json(trace_path).get("manifest")
                if os.path.exists(trace_path) else None)
    if manifest:
        out["manifest"] = contract.validate(manifest, "manifest")
    return out


def validate_manifest(path: str) -> List[str]:
    try:
        contract.check_manifest(contract.load_manifest(path), source=path)
        return []
    except contract.ManifestError as e:
        return [str(e)]


# ── main ──────────────────────────────────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_cap = sub.add_parser("capture", help="run one manifest and freeze it")
    p_cap.add_argument("--manifest", required=True)
    p_cap.add_argument("--runs-root", default=contract.RUNS_ROOT)
    p_cap.add_argument("--force", action="store_true",
                       help="overwrite a frozen run (you almost certainly want a new run_id)")
    p_cap.add_argument("--deterministic-framer", dest="deterministic", action="store_true",
                       default=None,
                       help="Arm C: use the frozen prompt→phrase mapping instead of a live "
                            "planner. The trace records that it did.")

    p_rep = sub.add_parser("replay", help="rebuild a run from frozen observations, zero calls")
    p_rep.add_argument("--run", required=True)
    p_rep.add_argument("--out")

    p_cmp = sub.add_parser("compare", help="read runs against each other")
    p_cmp.add_argument("--runs", nargs="+", required=True)
    p_cmp.add_argument("--json", action="store_true")

    p_val = sub.add_parser("validate", help="schema-check a run or a manifest")
    p_val.add_argument("--run")
    p_val.add_argument("--manifest")

    args = parser.parse_args(argv)

    if args.command == "capture":
        out = capture(args.manifest, runs_root=args.runs_root, force=args.force,
                      deterministic=args.deterministic)
        score = out["score"]
        print(f"{out['run_path']}")
        print(f"  mode        {score['mode']}  ·  expected {score['expected_condition']}")
        print(f"  organ       {out['trace']['organ_observation']['status']}  ·  "
              f"{score['measured']['instance_count']} instance(s)")
        print(f"  phrase      {out['trace']['decision_receipt']['selected_phrase']!r} "
              f"({out['trace']['decision_receipt']['phrase_source']})")
        print(f"  calls       {score['measured']['invocation_count']}/"
              f"{score['measured']['call_budget']}  ·  lock held "
              f"{score['measured']['lock_held']}")
        print(f"  attribution {score['verdict']['attribution']}")
        print(f"  correctness {score['verdict']['semantic_correctness']} "
              f"(review {score['review']['status']})")
        return 0

    if args.command == "replay":
        out = replay(args.run, out_path=args.out)
        print(f"replayed {args.run}: live calls {out['live_calls']}, "
              f"divergences {len(out['divergences'])}")
        for d in out["divergences"]:
            print(f"  ! {d}")
        return 1 if out["divergences"] or out["live_calls"] else 0

    if args.command == "compare":
        comparison = compare(args.runs)
        if args.json:
            import json
            print(json.dumps(comparison, indent=2))
        else:
            print(report.render_compare(comparison))
        return 0

    if args.command == "validate":
        if args.manifest:
            errors = validate_manifest(args.manifest)
            print(f"{args.manifest}: {'OK' if not errors else 'INVALID'}")
            for e in errors:
                print(f"  ! {e}")
            return 1 if errors else 0
        if args.run:
            results = validate_run(args.run)
            bad = False
            for name, errors in results.items():
                print(f"{name}: {'OK' if not errors else 'INVALID'}")
                for e in errors:
                    print(f"  ! {e}")
                bad = bad or bool(errors)
            return 1 if bad else 0
        print("validate needs --run or --manifest")
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
