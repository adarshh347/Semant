#!/usr/bin/env python3
"""
PERCEPTUAL-ORGANS-002 F3 — the rehearsal driver.

Drives a RUNNING Perception Lab over HTTP, records what every trial produced, and proves the
invariants either side of the whole sitting. It is the machine half of the human gate: it performs
the trials, times them, and preserves the evidence, so that the only thing left for a person to do
at the laboratory is the one thing a machine must not do here — say whether the measurement is any
good.

    IT DOES NOT DECIDE A VERDICT. There is no field in this file that could hold one. Every trial
    row comes out with `human_verdict: null`, and the finding is written against those nulls until
    a person fills them in. A rehearsal driver that scored its own organ would be the laboratory
    reviewing its own work, which is the exact confusion the review/lifecycle/epistemic split
    exists to prevent.

    IT TUNES NOTHING. No threshold, no prompt, no parameter is chosen here to make an image come
    out better. Where a trial refuses, the refusal is the result and is recorded as one.

WHY OVER HTTP AND NOT IN PROCESS. Because the thing under rehearsal is the laboratory a person
uses, and that is the routes. An in-process driver would exercise the conductor while leaving the
wire, the envelopes and the identity badges untested — and those are where a rehearsal's evidence
actually comes from.

WHY IT IS NOT IN `research/rehearsals/`. That tree is a research-only substrate whose whole
discipline is importing nothing from `backend` and touching no database. This driver does the
opposite by design: it reads posts to hash them, and it calls a live backend. Putting it there
would break the firewall that makes that tree worth having.

USAGE

    # 1. start the backend from a directory that HAS models/ (see the capability note below)
    #    2. then:
    python scripts/perception_lab_rehearsal.py preflight  --post <post_id>
    python scripts/perception_lab_rehearsal.py extent     --post <post_id> [--label sculpture]
    python scripts/perception_lab_rehearsal.py topology   --post <post_id>
    python scripts/perception_lab_rehearsal.py orchestration --post <post_id>
    python scripts/perception_lab_rehearsal.py report     --out evidence/

A CAPABILITY NOTE WORTH READING BEFORE ANY RESULT IS BELIEVED. `sam2_auto_service` resolves its
checkpoint as `os.path.join(os.getcwd(), "models", …)` — CWD-relative. So the same machine reports
`yolo_sam2_auto` on SAM 2.1 or on YOLO11-seg depending on where the process was started, and the
receipt names which one ran. Every capability table this driver writes therefore records the
backend's working directory beside it, because an availability table without one is a table about
nothing in particular.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

DEFAULT_BASE = os.environ.get("SEMANT_API", "http://127.0.0.1:5008") + "/api/v1"
TIMEOUT_S = 900


# ── the wire ─────────────────────────────────────────────────────────────────


class Lab:
    """The routes, and a stopwatch on the outside of each one."""

    def __init__(self, base: str = DEFAULT_BASE, api_key: Optional[str] = None):
        self.lab = f"{base}/perception-lab"
        self.base = base
        self.key = api_key or os.environ.get("API_KEY") or None
        self.calls: List[Dict[str, Any]] = []

    def _call(self, method: str, url: str, body=None) -> Tuple[int, Any, float]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["X-API-Key"] = self.key
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as response:
                payload = json.loads(response.read() or b"{}")
                status = response.status
        except urllib.error.HTTPError as exc:
            payload = json.loads(exc.read() or b"{}")
            status = exc.code
        elapsed = (time.time() - started) * 1000.0
        self.calls.append({"method": method, "url": url, "status": status, "ms": round(elapsed)})
        return status, payload, elapsed

    # -- reads --
    def capabilities(self):
        return self._call("GET", f"{self.lab}/capabilities")

    def source(self, post_id: str):
        return self._call("GET", f"{self.lab}/sources/{post_id}")

    def history(self, sid: str):
        return self._call("GET", f"{self.lab}/sessions/{sid}/history")

    def export(self, sid: str):
        return self._call("GET", f"{self.lab}/sessions/{sid}/export")

    # -- writes --
    def open_session(self, post_id: str, organ="extent", mode="isolation"):
        return self._call("POST", f"{self.lab}/sessions",
                          {"post_id": post_id, "selected_organ": organ, "mode": mode})

    def select(self, sid: str, **update):
        return self._call("PATCH", f"{self.lab}/sessions/{sid}", update)

    def plan_direct(self, sid: str, operation: str, parameters=None, input_refs=None):
        return self._call("POST", f"{self.lab}/sessions/{sid}/plans", {
            "planner": "direct",
            "commands": [{"operation": operation, "parameters": parameters or {},
                          "input_refs": input_refs or []}]})

    def plan_prompt(self, sid: str, prompt: str, planner="rules"):
        return self._call("POST", f"{self.lab}/sessions/{sid}/plans",
                          {"planner": planner, "prompt": prompt})

    def run(self, sid: str, plan_id: str, confirmed=False, ticket=None):
        return self._call("POST", f"{self.lab}/sessions/{sid}/runs",
                          {"plan_id": plan_id, "confirmed": confirmed, "run_ticket": ticket})

    def cancel(self, sid: str, ticket: str):
        return self._call("POST", f"{self.lab}/sessions/{sid}/runs/cancel",
                          {"run_ticket": ticket})

    def replay(self, sid: str, run_id: str):
        return self._call("POST", f"{self.lab}/sessions/{sid}/replays", {"run_id": run_id})

    def review(self, sid: str, artifact_id: str, verdict: str, notes=""):
        return self._call("POST", f"{self.lab}/sessions/{sid}/reviews",
                          {"artifact_id": artifact_id, "verdict": verdict, "notes": notes})


# ── the invariants, hashed either side ───────────────────────────────────────


def post_state(post_id: str) -> Dict[str, Any]:
    """The whole post document, hashed, plus the counts a promotion would move.

    Imported lazily and locally so this file is runnable with no database for the parts that do
    not need one. `fingerprint_of` is the lab's own, which is `movement_kernel.posts_fingerprint` —
    one definition of what counts as the document, not a second one written here.

    THROUGH THE LAB'S SYNCHRONOUS HANDLE, not through `motor`. A motor client binds to the first
    event loop it is used on, and this function is called twice in one process — before the sitting
    and after it. The second call on a second loop raises `attached to a different loop`, which is
    a driver bug that would read as a database failure at exactly the moment the invariant was
    being checked. `sync_database()` is the door the lab store already uses, and it has no loop.
    """
    from bson import ObjectId
    from backend.database import sync_database
    from backend.services.perception_lab.source import fingerprint_of

    doc = sync_database().get_collection("posts").find_one({"_id": ObjectId(post_id)})
    if doc is None:
        raise SystemExit(f"no post {post_id}")
    return {
        "post_id": post_id,
        "fingerprint": fingerprint_of(doc),
        "ledger": {k: len(doc.get(k) or []) for k in
                   ("region_annotations", "visual_marks", "grounds", "percepts", "visual_layers")},
    }


def lab_collection_counts() -> Dict[str, int]:
    from backend.services.perception_lab.mongo_store import MongoLabStore
    return MongoLabStore().counts()


# ── reading a run into a row ─────────────────────────────────────────────────


def instances_of(artifact: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return list(((artifact.get("measurement") or {}).get("payload") or {}).get("instances") or [])


def row_for(trial: str, body: Mapping[str, Any], wall_ms: float,
            **extra) -> Dict[str, Any]:
    """One trial, as a row of the performance table.

    `human_verdict` is present and null. It is not omitted, because a table without the column
    reads as a table that did not need one — and the whole point of this lane is that it does.
    """
    run = body.get("run") or {}
    artifacts = body.get("artifacts") or []
    first = artifacts[0] if artifacts else {}
    attempts = run.get("stage_attempts") or []
    payload = (first.get("measurement") or {}).get("payload") or {}
    instances = instances_of(first)
    provenance = first.get("provenance") or {}
    return {
        "trial": trial,
        "session_id": run.get("session_id"),
        "run_id": run.get("run_id"),
        "plan_id": run.get("requested_plan_id"),
        "artifact_ids": run.get("artifact_ids") or [],
        "execution_identity": run.get("execution_identity"),
        "outcome": run.get("outcome"),
        "adapter": (attempts[-1].get("adapter") if attempts else None),
        "model": provenance.get("model"),
        "revision": provenance.get("revision"),
        "device": provenance.get("device"),
        "invoked": (attempts[-1].get("invoked") if attempts else None),
        # THE OUTER CLOCK AND THE INNER ONE, both, and labelled. `wall_ms` is this driver's
        # stopwatch around the HTTP call; `run_duration_ms` is the conductor's around the stages;
        # `stage_duration_ms` is the observer's around the one call. A rehearsal that reported one
        # number could not tell a slow model from a slow route.
        "wall_ms": round(wall_ms),
        "run_duration_ms": run.get("duration_ms"),
        "stage_duration_ms": (attempts[-1].get("duration_ms") if attempts else None),
        "extent_count": len(instances) if instances else None,
        "pairs_examined": payload.get("pairs_examined"),
        "relation_count": len(payload.get("relations") or []) if payload.get("relations") is not None else None,
        "epistemic_status": (first.get("measurement") or {}).get("epistemic_status"),
        "epistemic_basis": (first.get("measurement") or {}).get("epistemic_basis"),
        "identity_scope": (first.get("identity") or {}).get("identity_scope"),
        "lifecycle": (first.get("lifecycle") or {}).get("status"),
        "dropped_below_min_area": payload.get("dropped_below_min_area"),
        "duplicates": len(payload.get("duplicates") or []) if payload.get("duplicates") is not None else None,
        "naming_withheld": sum(1 for i in instances if not i.get("naming")),
        "refusals": [{"code": r.get("code"), "message": r.get("message"),
                      "missing": r.get("missing"), "remedy": r.get("remedy")}
                     for r in (run.get("refusals") or [])],
        "source_unchanged": body.get("source_unchanged"),
        "stage_detail": (attempts[-1].get("detail") if attempts else None),
        # The one column no machine may fill.
        "human_verdict": None,
        "human_notes": None,
        **extra,
    }


def plan_row(trial: str, plan: Mapping[str, Any], wall_ms: float, **extra) -> Dict[str, Any]:
    """A plan that was proposed and never run — a refusal trial, or a composition check."""
    return {
        "trial": trial,
        "plan_id": plan.get("plan_id"),
        "planner": plan.get("planner"),
        "planner_fell_back_from": plan.get("planner_fell_back_from"),
        "selected_organ": plan.get("selected_organ"),
        "mode": plan.get("mode"),
        "proposed": [s.get("operation") for s in (plan.get("proposed_steps") or [])],
        "resolved": [s.get("operation") for s in (plan.get("resolved_steps") or [])],
        "adapters": [s.get("adapter") for s in (plan.get("resolved_steps") or [])],
        "requires_confirmation": plan.get("requires_confirmation"),
        "refusals": [{"code": r.get("code"), "message": r.get("message"),
                      "missing": r.get("missing")} for r in (plan.get("refusals") or [])],
        "dropped_parameters": plan.get("dropped_parameters") or [],
        "clamped_parameters": plan.get("clamped_parameters") or [],
        "wall_ms": round(wall_ms),
        "human_verdict": None,
        "human_notes": None,
        **extra,
    }


# ── evidence ─────────────────────────────────────────────────────────────────


class Evidence:
    def __init__(self, out: str):
        self.dir = out
        os.makedirs(out, exist_ok=True)
        self.rows: List[Dict[str, Any]] = []
        self.notes: List[str] = []

    def add(self, row: Dict[str, Any]) -> Dict[str, Any]:
        self.rows.append(row)
        detail = row.get("outcome") or (
            "refused at plan" if row.get("refusals") else "planned")
        print(f"  {row['trial']:34} {str(detail):11} "
              f"{row.get('wall_ms', '')}ms "
              f"{row.get('adapter') or ''} "
              f"{('extents=' + str(row['extent_count'])) if row.get('extent_count') is not None else ''}"
              f"{('pairs=' + str(row['pairs_examined'])) if row.get('pairs_examined') is not None else ''}")
        for r in row.get("refusals") or []:
            print(f"       ↳ {r['code']}: {(r['message'] or '')[:110]}")
        return row

    def note(self, text: str) -> None:
        self.notes.append(text)
        print(f"  · {text}")

    def write(self, name: str, payload: Any) -> str:
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)
        return path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = ["Lab", "Evidence", "post_state", "lab_collection_counts", "row_for", "plan_row",
           "instances_of", "now"]


# ── the trials ───────────────────────────────────────────────────────────────


def extent_trials(lab: Lab, ev: Evidence, post_id: str, label: str) -> Dict[str, Any]:
    """The nine Extent trials, in the order a person would walk them.

    Each one either measures or refuses, and both are results. `extent.refine` on a machine without
    SAM 2.1 refuses `capability_unavailable` and that row is as much evidence as a successful one —
    it is the difference between "the model is not here" and "there is nothing there", which is the
    single distinction this organ was built to keep.
    """
    print(f"\n── EXTENT · {label} · {post_id} ──")
    status, opened, ms = lab.open_session(post_id, organ="extent", mode="isolation")
    sid = opened["session"]["session_id"]
    source = opened["source"]
    ev.note(f"session {sid} on {source['natural_width']}×{source['natural_height']} "
            f"digest {source['image_digest'][:26]}…")

    def direct(trial, operation, parameters=None, refs=None, confirmed=False):
        _, plan, pms = lab.plan_direct(sid, operation, parameters, refs)
        record = plan["plan"]
        if not record["resolved_steps"]:
            return ev.add(plan_row(trial, record, pms, image=label)), None
        started = time.time()
        _, body, _ = lab.run(sid, record["plan_id"], confirmed=confirmed, ticket=f"t_{trial}")
        return ev.add(row_for(trial, body, (time.time() - started) * 1000, image=label)), body

    # 1 · Direct find_all — the baseline every other number is read against.
    first_row, first = direct("extent.find_all · direct", "extent.find_all")

    # 2 · the Prompt equivalent, deterministic arm. The claim being tested is that the two arms
    #     reach ONE runner, so the measurement should match even though the ids will not.
    _, plan, pms = lab.plan_prompt(sid, "what is in this picture?", planner="rules")
    ev.add(plan_row("extent.find_all · prompt(rules) plan", plan["plan"], pms, image=label))
    prompted = None
    if plan["plan"]["resolved_steps"]:
        started = time.time()
        _, prompted, _ = lab.run(sid, plan["plan"]["plan_id"], ticket="t_prompt")
        ev.add(row_for("extent.find_all · prompt(rules)", prompted,
                       (time.time() - started) * 1000, image=label))

    # 3 · the model arm. With no key it falls back to rules AND SAYS SO, which is the field that
    #     separates a laboratory from a demo.
    _, model_plan, pms = lab.plan_prompt(sid, "mask every instance", planner="model")
    ev.add(plan_row("prompt(model) plan", model_plan["plan"], pms, image=label))

    # 4 · named segmentation. sam3_concept absent routes to grounded_sam, and the receipt names it.
    direct("extent.find_named · 'drapery'", "extent.find_named", {"concept": "drapery"})

    # 5 & 6 · refinement, point and box, on ONE named instance.
    base_id = None
    instance_id = None
    if first and first.get("artifacts"):
        base_id = first["artifacts"][0]["identity"]["artifact_id"]
        held = instances_of(first["artifacts"][0])
        if held:
            instance_id = held[0]["instance_id"]
            lab.select(sid, selected_artifact_ids=[base_id], active_artifact_id=base_id,
                       selected_instance_refs=[{"artifact_id": base_id,
                                                "instance_id": instance_id}])
            ref = [{"role": "base", "scope": "session", "artifact_id": base_id,
                    "instance_id": instance_id}]
            direct("extent.refine · point", "extent.refine",
                   {"mode": "add", "points": [[0.5, 0.5]]}, ref)
            direct("extent.refine · box", "extent.refine",
                   {"mode": "add", "box": {"x": 0.3, "y": 0.3, "w": 0.3, "h": 0.3}}, ref)

    # 7 · the manual fallback. A person's hand, and the record says `human` with no adapter.
    direct("extent.draw · manual polygon", "extent.draw",
           {"tool": "polygon", "polygon": [[0.30, 0.30], [0.62, 0.30], [0.62, 0.66], [0.30, 0.66]]})

    # 8 · the repeated identical run. Two identical inputs, and the question is whether the organ
    #     answers the same thing twice.
    repeat_row, repeat = direct("extent.find_all · repeat", "extent.find_all")

    # 9 · A/B comparison of the two identical runs, measured per pixel rather than by eye.
    if first and repeat and first.get("artifacts") and repeat.get("artifacts"):
        left = first["artifacts"][0]["identity"]["artifact_id"]
        right = repeat["artifacts"][0]["identity"]["artifact_id"]
        lab.select(sid, selected_artifact_ids=[left, right], active_artifact_id=right,
                   selected_instance_refs=[])
        direct("extent.compare · repeat stability", "extent.compare", {}, [
            {"role": "left", "scope": "session", "artifact_id": left},
            {"role": "right", "scope": "session", "artifact_id": right}])

    # 10 · the selected-instance follow-up: "that mask", resolved only through what was declared.
    if base_id and instance_id:
        lab.select(sid, selected_artifact_ids=[base_id], active_artifact_id=base_id,
                   selected_instance_refs=[{"artifact_id": base_id, "instance_id": instance_id}])
        _, follow, pms = lab.plan_prompt(sid, "refine that mask", planner="rules")
        ev.add(plan_row("follow-up · 'refine that mask'", follow["plan"], pms, image=label,
                        declared_instance=f"{base_id}#{instance_id}"))

    return {"session_id": sid, "source": source, "base_artifact": base_id,
            "base_instance": instance_id}


def topology_trials(lab: Lab, ev: Evidence, post_id: str, label: str) -> Dict[str, Any]:
    """The seven Topology operations, over instances a person would have selected by hand.

    The endpoints are chosen by AREA — the two largest extents — rather than by which pair happens
    to produce a relation. Choosing endpoints by their answer is the one thing that would make
    every number below meaningless.
    """
    print(f"\n── TOPOLOGY · {label} · {post_id} ──")
    _, opened, _ = lab.open_session(post_id, organ="extent", mode="isolation")
    sid = opened["session"]["session_id"]
    _, plan, _ = lab.plan_direct(sid, "extent.find_all")
    started = time.time()
    _, body, _ = lab.run(sid, plan["plan"]["plan_id"], ticket="t_topo_extents")
    ev.add(row_for("extent.find_all · for topology", body, (time.time() - started) * 1000,
                   image=label))
    if not body.get("artifacts"):
        ev.note("no extents came back, so there is nothing for topology to relate. "
                "This is a measured absence, not a topology failure.")
        return {"session_id": sid}

    artifact = body["artifacts"][0]
    art_id = artifact["identity"]["artifact_id"]
    held = sorted(instances_of(artifact), key=lambda i: -(i.get("area") or 0))
    if len(held) < 2:
        ev.note(f"only {len(held)} extent(s); a relation needs two endpoints.")
        return {"session_id": sid}
    a, b = held[0]["instance_id"], held[1]["instance_id"]
    ev.note(f"endpoints chosen by area: {a} (area {held[0].get('area')}) and "
            f"{b} (area {held[1].get('area')})")

    lab.select(sid, selected_organ="topology", mode="chain",
               selected_artifact_ids=[art_id], active_artifact_id=art_id,
               selected_instance_refs=[{"artifact_id": art_id, "instance_id": a},
                                       {"artifact_id": art_id, "instance_id": b}])

    def pair(trial, operation, roles=("source", "target"), extra_params=None, confirmed=False):
        refs = [{"role": roles[0], "scope": "session", "artifact_id": art_id, "instance_id": a},
                {"role": roles[1], "scope": "session", "artifact_id": art_id, "instance_id": b}]
        _, p, pms = lab.plan_direct(sid, operation, extra_params or {}, refs)
        record = p["plan"]
        if not record["resolved_steps"]:
            return ev.add(plan_row(trial, record, pms, image=label))
        started = time.time()
        _, out, _ = lab.run(sid, record["plan_id"],
                            confirmed=confirmed or record["requires_confirmation"],
                            ticket=f"t_{operation}")
        row = row_for(trial, out, (time.time() - started) * 1000, image=label,
                      endpoints=[f"{art_id}#{a}", f"{art_id}#{b}"])
        relations = ((out.get("artifacts") or [{}])[0].get("measurement") or {}).get("payload") or {}
        row["relations"] = [{
            "kind": r.get("kind"), "directed": r.get("directed"), "basis": r.get("basis"),
            "epistemic_status": r.get("epistemic_status"),
            "source": (r.get("source") or {}).get("instance_id"),
            "target": (r.get("target") or {}).get("instance_id"),
            "measurements": r.get("measurements"),
        } for r in (relations.get("relations") or [])]
        return ev.add(row)

    pair("topology.containment", "topology.containment")
    pair("topology.adjacency", "topology.adjacency")
    pair("topology.overlap", "topology.overlap")
    pair("topology.disjoint", "topology.disjoint")
    # `occlusion` needs a prepared depth field, and this deployment has no organ that makes one.
    # The refusal IS the trial: `missing_depth_artifact`, not an empty relation set.
    pair("topology.occlusion · no depth", "topology.occlusion", confirmed=True)

    # negative space takes `figure`, and all_pairs takes `members` — one role, several instances.
    figure = [{"role": "figure", "scope": "session", "artifact_id": art_id, "instance_id": a}]
    _, p, pms = lab.plan_direct(sid, "topology.negative_space", {}, figure)
    if p["plan"]["resolved_steps"]:
        started = time.time()
        _, out, _ = lab.run(sid, p["plan"]["plan_id"],
                            confirmed=p["plan"]["requires_confirmation"], ticket="t_negspace")
        ev.add(row_for("topology.negative_space", out, (time.time() - started) * 1000, image=label))
    else:
        ev.add(plan_row("topology.negative_space", p["plan"], pms, image=label))

    # BOUNDED ALL-PAIRS OVER THE TOP FIVE, not over the two the pair trials used.
    #
    # The pair trials name two endpoints because a person naming two is the supported gesture. But
    # choosing those two BY AREA reliably picks the two biggest extents, which on a real photograph
    # are usually far apart — every pair relation then comes back `disjoint`, truthfully and
    # uselessly. A sweep is the honest way for a machine to find whether ANY nested or touching
    # pair exists in the set, without a driver choosing endpoints by their answer, which is the one
    # thing that would make every number here meaningless.
    sweep = [i["instance_id"] for i in held[:5]]
    members = [{"role": "members", "scope": "session", "artifact_id": art_id, "instance_id": i}
               for i in sweep]
    lab.select(sid, selected_artifact_ids=[art_id], active_artifact_id=art_id,
               selected_instance_refs=[{"artifact_id": art_id, "instance_id": i} for i in sweep])
    _, p, pms = lab.plan_direct(sid, "topology.all_pairs", {}, members)
    if p["plan"]["resolved_steps"]:
        started = time.time()
        _, out, _ = lab.run(sid, p["plan"]["plan_id"],
                            confirmed=p["plan"]["requires_confirmation"], ticket="t_allpairs")
        row = row_for("topology.all_pairs · bounded", out, (time.time() - started) * 1000,
                      image=label, members=sweep)
        relations = ((out.get("artifacts") or [{}])[0].get("measurement") or {}).get("payload") or {}
        row["relations"] = [{
            "kind": r.get("kind"), "directed": r.get("directed"), "basis": r.get("basis"),
            "epistemic_status": r.get("epistemic_status"),
            "source": (r.get("source") or {}).get("instance_id"),
            "target": (r.get("target") or {}).get("instance_id"),
            "measurements": r.get("measurements"),
        } for r in (relations.get("relations") or [])]
        ev.add(row)
    else:
        ev.add(plan_row("topology.all_pairs · bounded", p["plan"], pms, image=label))

    return {"session_id": sid, "artifact": art_id, "endpoints": [a, b]}


def orchestration_trials(lab: Lab, ev: Evidence, post_id: str, label: str) -> Dict[str, Any]:
    """The conductor's own trials: what it refuses, what it re-shows, what it will not cross."""
    print(f"\n── ORCHESTRATION · {label} · {post_id} ──")
    _, opened, _ = lab.open_session(post_id, organ="extent", mode="isolation")
    sid = opened["session"]["session_id"]

    # An invented reference. The whole follow-up law in one request.
    _, p, pms = lab.plan_direct(sid, "extent.refine", {"mode": "add", "points": [[0.5, 0.5]]},
                                [{"role": "base", "scope": "session",
                                  "artifact_id": "art_nobody_ever_made",
                                  "instance_id": "inst_7"}])
    ev.add(plan_row("invented reference", p["plan"], pms, image=label))

    # A cross-organ request in ISOLATION. The lock is the session's, and the refusal names it.
    _, p, pms = lab.plan_prompt(sid, "what is inside what?", planner="rules")
    ev.add(plan_row("cross-organ in isolation", p["plan"], pms, image=label))

    # The same request in CHAIN — permitted, and it asks first.
    lab.select(sid, mode="chain")
    _, p, pms = lab.plan_prompt(sid, "what is inside what?", planner="rules")
    ev.add(plan_row("cross-organ in chain", p["plan"], pms, image=label))

    # An unavailable capability, named. Nothing is substituted without a receipt.
    lab.select(sid, mode="isolation", selected_organ="extent")
    _, p, pms = lab.plan_direct(sid, "extent.find_named",
                                {"concept": "drapery", "adapter": "sam3_concept"})
    ev.add(plan_row("unavailable adapter, named explicitly", p["plan"], pms, image=label))

    # Cancellation, where practical: a ticket nobody is holding.
    _, out, cms = lab.cancel(sid, "tkt_nothing_in_flight")
    ev.add({"trial": "cancel · nothing in flight", "wall_ms": round(cms),
            "cancelled": out.get("cancelled"), "note": out.get("note"),
            "human_verdict": None, "human_notes": None})

    # Replay: a real run, re-shown, with the model-call counter read either side of it.
    _, p, _ = lab.plan_direct(sid, "extent.find_all")
    started = time.time()
    _, live, _ = lab.run(sid, p["plan"]["plan_id"], ticket="t_replay_source")
    ev.add(row_for("replay · the live run first", live, (time.time() - started) * 1000,
                   image=label))
    if live.get("run"):
        started = time.time()
        _, shown, _ = lab.replay(sid, live["run"]["run_id"])
        row = row_for("replay · re-shown", shown, (time.time() - started) * 1000, image=label)
        row["replay_of"] = (shown.get("run") or {}).get("replay")
        row["any_stage_invoked"] = any(a.get("invoked")
                                       for a in (shown.get("run") or {}).get("stage_attempts") or [])
        row["artifact_ids_identical"] = (
            (shown.get("run") or {}).get("artifact_ids") == live["run"]["artifact_ids"])
        ev.add(row)
    return {"session_id": sid}


# ── preflight ────────────────────────────────────────────────────────────────


def preflight(lab: Lab, ev: Evidence, post_id: str) -> Dict[str, Any]:
    """Everything that must be true before a person is asked to spend an hour here."""
    print("\n── PREFLIGHT ──")
    checks: List[Dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        print(f"  [{'ok ' if ok else 'NO '}] {name}" + (f"  {detail}" if detail else ""))
        return ok

    status, caps, _ = lab.capabilities()
    check("backend answers /capabilities", status == 200, f"HTTP {status}")
    # LIVE IS THE REGISTRY'S OWN ANSWER, not a string this driver hoped for. A backend wired to
    # fakes would say FIXTURE here, which is the whole point of the field.
    check("the wire is LIVE, not a fixture fallback",
          caps.get("execution_identity") == "LIVE", caps.get("execution_identity"))
    states = caps.get("states") or {}
    check("both live organs are enabled",
          {o["family"] for o in caps.get("organs", []) if o["enabled"]} == {"extent", "topology"})
    for name, state in sorted(states.items()):
        print(f"        {name:22} {state}")
    unavailable = sorted(n for n, s in states.items() if s == "unavailable")
    if unavailable:
        ev.note(f"UNAVAILABLE, and shown as such rather than substituted: {', '.join(unavailable)}")

    status, src, _ = lab.source(post_id)
    ok = status == 200 and (src.get("source") or {}).get("image_digest")
    check("a real post resolves to a source with a digest and a raster", ok,
          f"{src.get('source', {}).get('natural_width')}×{src.get('source', {}).get('natural_height')} "
          f"{str(src.get('source', {}).get('image_digest'))[:26]}…")

    before = post_state(post_id)
    lab_before = lab_collection_counts()
    check("post read for hashing", True, before["fingerprint"][:24] + "…")

    status, opened, _ = lab.open_session(post_id)
    sid = (opened.get("session") or {}).get("session_id")
    check("a session opens and the FIRST response carries the real source",
          status == 201 and bool(sid) and bool((opened.get("source") or {}).get("image_digest")),
          sid)

    _, plan, _ = lab.plan_direct(sid, "extent.find_all")
    started = time.time()
    _, body, _ = lab.run(sid, plan["plan"]["plan_id"], ticket="preflight")
    smoke = ev.add(row_for("preflight smoke · extent.find_all", body,
                           (time.time() - started) * 1000))
    check("a live run reaches a real adapter and produces a measurement",
          smoke["execution_identity"] == "LIVE" and smoke["invoked"] is True,
          f"{smoke['outcome']} · {smoke['adapter']} · {smoke['model']} · {smoke['device']}")

    status, again, _ = lab.history(sid)
    check("the session reopens with its whole ledger",
          status == 200 and len(again.get("runs") or []) == 1
          and len(again.get("artifacts") or []) == 1)

    after = post_state(post_id)
    lab_after = lab_collection_counts()
    check("THE SOURCE POST IS BYTE-IDENTICAL",
          before["fingerprint"] == after["fingerprint"], after["fingerprint"][:24] + "…")
    check("THE PERCEPTUAL LEDGER IS UNTOUCHED", before["ledger"] == after["ledger"],
          json.dumps(after["ledger"]))
    ev.note(f"the lab's OWN collections did move, which is where the writing goes: "
            f"{ {k: lab_after[k] - lab_before[k] for k in lab_after} }")

    return {"checks": checks, "capabilities": caps, "session_id": sid,
            "post_before": before, "post_after": after,
            "lab_counts_before": lab_before, "lab_counts_after": lab_after,
            "backend_cwd_note": "capability depends on the backend's CWD; see the module docstring"}


# ── CLI ──────────────────────────────────────────────────────────────────────


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("suite", choices=["preflight", "extent", "topology", "orchestration",
                                          "all"])
    parser.add_argument("--post", required=True, help="an ordinary Semant post id")
    parser.add_argument("--label", default="", help="what this image is, for the evidence rows")
    parser.add_argument("--out", default="evidence", help="where the evidence JSON is written")
    parser.add_argument("--base", default=DEFAULT_BASE)
    args = parser.parse_args(argv)

    lab = Lab(args.base)
    ev = Evidence(args.out)
    label = args.label or args.post
    started_at = now()
    before = post_state(args.post)
    result: Dict[str, Any] = {}

    if args.suite in ("preflight", "all"):
        result["preflight"] = preflight(lab, ev, args.post)
    if args.suite in ("extent", "all"):
        result["extent"] = extent_trials(lab, ev, args.post, label)
    if args.suite in ("topology", "all"):
        result["topology"] = topology_trials(lab, ev, args.post, label)
    if args.suite in ("orchestration", "all"):
        result["orchestration"] = orchestration_trials(lab, ev, args.post, label)

    after = post_state(args.post)
    invariants = {
        "post_fingerprint_before": before["fingerprint"],
        "post_fingerprint_after": after["fingerprint"],
        "post_byte_identical": before["fingerprint"] == after["fingerprint"],
        "ledger_before": before["ledger"],
        "ledger_after": after["ledger"],
        "ledger_unchanged": before["ledger"] == after["ledger"],
        # A promotion would move a lifecycle to `promoted` or mint a canonical scope. Both are read
        # off the artifacts this sitting actually produced rather than asserted.
        "no_promoted_lifecycle": all(r.get("lifecycle") != "promoted" for r in ev.rows),
        "every_artifact_session_scoped": all(
            r.get("identity_scope") in (None, "session") for r in ev.rows),
        "no_fixture_run_wore_live": all(
            not (r.get("execution_identity") == "LIVE" and r.get("invoked") is False
                 and r.get("outcome") == "ready")
            for r in ev.rows),
    }
    print("\n── INVARIANTS ──")
    for key, value in invariants.items():
        if isinstance(value, bool):
            print(f"  [{'ok ' if value else 'NO '}] {key}")

    bundle = {
        "what_this_is": "PERCEPTUAL-ORGANS-002 F3 rehearsal evidence. `human_verdict` is null on "
                        "every row until a person fills it in; nothing here scores itself.",
        "suite": args.suite, "post_id": args.post, "label": label,
        "started_at": started_at, "finished_at": now(),
        "trials": ev.rows, "notes": ev.notes, "invariants": invariants,
        "http_calls": lab.calls, **result,
    }
    name = f"rehearsal-{args.suite}-{args.post}.json"
    print(f"\nevidence → {ev.write(name, bundle)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
