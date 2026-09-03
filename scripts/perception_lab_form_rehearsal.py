#!/usr/bin/env python3
"""
PERCEPTUAL-FORMS-001H — the form rehearsal driver.

Drives a RUNNING Perception Lab over HTTP at all three levels — direct form, deterministic recipe,
prompt proposal — records what each produced, and proves the invariants either side of the whole
sitting. It is the machine half of the form gate.

    IT DOES NOT DECIDE A VERDICT, and there is no field in this file that could hold one. Every
    trial row comes out with `human_correct: null`, `human_useful: null` and
    `better_seen_as: null`. A rehearsal driver that scored its own forms would be the laboratory
    reviewing its own work — which is the exact confusion the review / lifecycle / epistemic split
    exists to prevent, and it is why F3's driver was built the same way.

    THE ONE VERDICT A MACHINE MAY ISSUE IS `DEFER`, and only for an absence it can SEE. A model
    with no checkpoint on this machine is an honest missing dependency and the capability probe
    proves it. `RATIFY`, `REPAIR` and `REJECT` are statements about whether a measurement is any
    good, and nothing here has looked at a picture.

    IT TUNES NOTHING. Where a trial refuses, the refusal is the result and is recorded as one.

WHAT IT RECORDS PER FORM, because the gate asks for exactly this list:

    direct operation · producer and model · latency and memory · the canonical artifact (or the
    derivation, and which of the two it was) · two renderings where the form declares two ·
    human correctness · subjective usefulness · whether another form revealed it better ·
    failure or refusal · the source/post mutation proof

THE ORDER IS FIXED AND IS PART OF THE METHOD. Direct forms first, then recipes, then prompts. A
prompt trial run before the direct one would be testing language and the organ at once, and a
disagreement would have two possible causes.

USAGE

    python scripts/perception_lab_form_rehearsal.py preflight --post <post_id>
    python scripts/perception_lab_form_rehearsal.py forms     --post <post_id> [--label sculpture]
    python scripts/perception_lab_form_rehearsal.py recipes   --post <post_id>
    python scripts/perception_lab_form_rehearsal.py prompts   --post <post_id>
    python scripts/perception_lab_form_rehearsal.py report    --out research/perception_lab/rehearsals/

THE CAPABILITY NOTE FROM F3 STILL APPLIES and is recorded in every bundle: `sam2_auto_service`
resolves its checkpoint relative to the backend's working directory, so an availability table
without a CWD beside it is a table about nothing in particular. This driver reads the CWD the
backend reports and writes it down.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.perception_lab_rehearsal import (DEFAULT_BASE, Lab, lab_collection_counts, now,
                                              post_state)

#: Where the bundles land. Inside the repository, beside Lane C's model trials and Lane F's
#: controls, because the finding cites them and the vault is not versioned.
REHEARSALS = Path(__file__).resolve().parents[1] / "research" / "perception_lab" / "rehearsals"

#: The three fields only a person may fill. Written as nulls into every row, so a bundle that
#: reached a gate without a sitting is visibly un-walked rather than silently empty.
HUMAN_FIELDS = ("human_correct", "human_useful", "better_seen_as", "human_notes")


class FormLab(Lab):
    """The routes PERCEPTUAL-FORMS-001H added, on the same stopwatch as the rest."""

    def forms(self):
        return self._call("GET", f"{self.lab}/forms")

    def recipes(self):
        return self._call("GET", f"{self.lab}/recipes")

    def readiness(self, sid: str, key: str):
        return self._call("GET", f"{self.lab}/sessions/{sid}/recipes/{key}/readiness")

    def plan_recipe(self, sid: str, key: str, bindings=None):
        return self._call("POST", f"{self.lab}/sessions/{sid}/recipes/{key}/plans",
                          {"bindings": bindings or {}})

    def derive(self, sid: str, form: str, artifact_ids, parameters=None):
        return self._call("POST", f"{self.lab}/sessions/{sid}/derivations",
                          {"form": form, "artifact_ids": list(artifact_ids),
                           "parameters": parameters or {}})

    def derivations(self, sid: str):
        return self._call("GET", f"{self.lab}/sessions/{sid}/derivations")


def blank_human() -> Dict[str, Any]:
    return {field: None for field in HUMAN_FIELDS}


def write(bundle: Mapping[str, Any], name: str, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(json.dumps(bundle, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


# ── preflight ────────────────────────────────────────────────────────────────


def preflight(lab: FormLab, post_id: str) -> Dict[str, Any]:
    """Every check that must be green before a single trial is believed.

    THE FORM CATALOGUE IS PART OF PREFLIGHT NOW. A rehearsal that started without knowing which
    forms this deployment can write would spend its first hour discovering it one refusal at a
    time, which is what the previous sitting did.
    """
    checks: List[Dict[str, Any]] = []

    status, caps, _ = lab.capabilities()
    checks.append({"check": "backend answers /capabilities", "ok": status == 200,
                   "detail": f"HTTP {status}"})
    checks.append({"check": "the wire is LIVE, not a fixture fallback",
                   "ok": caps.get("execution_identity") == "LIVE",
                   "detail": caps.get("execution_identity")})

    adapters = [a for organ in caps.get("organs", []) for op in organ.get("operations", [])
                for a in op.get("adapters", [])]
    unavailable = [a for a in adapters if a.get("state") != "available"]
    checks.append({
        "check": "every unavailable adapter says WHY and what would change it",
        "ok": all(a.get("reason") and a.get("remedy") for a in unavailable),
        "detail": {a["key"]: a.get("reason") for a in unavailable}})

    status, forms, _ = lab.forms()
    checks.append({"check": "the form catalogue answers", "ok": status == 200,
                   "detail": forms.get("counts")})
    checks.append({
        "check": "every form that cannot be written names which absence it is",
        "ok": all(f["blocked_by"] and f["note"] for f in forms.get("forms", [])
                  if not f["writable_as_artifact"]),
        "detail": {f["form"]: f["blocked_by"] for f in forms.get("forms", [])}})

    status, recipes, _ = lab.recipes()
    checks.append({"check": "the recipe catalogue answers seven studies",
                   "ok": len(recipes.get("recipes", [])) == 7,
                   "detail": [r["key"] for r in recipes.get("recipes", [])]})

    status, source, _ = lab.source(post_id)
    snapshot = (source or {}).get("source") or {}
    checks.append({"check": "the post resolves to a source with a digest and a raster",
                   "ok": bool(snapshot.get("image_digest")),
                   "detail": {k: snapshot.get(k) for k in
                              ("image_digest", "natural_width", "natural_height")}})

    before = post_state(post_id)
    status, opened, _ = lab.open_session(post_id)
    session = (opened or {}).get("session") or {}
    checks.append({"check": "a session opens and the FIRST response carries the real source",
                   "ok": status == 201 and bool(session.get("session_id")),
                   "detail": session.get("session_id")})
    after = post_state(post_id)
    checks.append({"check": "the source post is byte-identical after opening",
                   "ok": before.get("digest") == after.get("digest"),
                   "detail": before.get("digest")})

    return {
        "suite": "preflight", "recorded_at": now(), "post_id": post_id,
        "backend_cwd": caps.get("cwd") or os.environ.get("SEMANT_BACKEND_CWD") or "unrecorded",
        "checks": checks,
        "all_green": all(c["ok"] for c in checks),
        "capabilities": caps, "forms": forms, "recipes": recipes,
        "session_id": session.get("session_id"),
        "ledger_before": before, "ledger_after": after,
        "lab_collections": lab_collection_counts(),
    }


# ── the direct form level ────────────────────────────────────────────────────


def form_trials(lab: FormLab, post_id: str, label: str) -> Dict[str, Any]:
    """One row per form this deployment can produce, in the order the catalogue lists them.

    THE SUBSTRATE IS MEASURED FIRST AND ONCE. Every derivable Extent form reads a hard mask, so
    the sitting opens with one `extent.find_all` and every form after it derives from that same
    artifact. Re-measuring per form would make the rows incomparable — a fusion over one
    segmentation and a hierarchy over another are two pictures.
    """
    before = post_state(post_id)
    _, catalogue, _ = lab.forms()
    _, opened, _ = lab.open_session(post_id)
    sid = opened["session"]["session_id"]

    _, plan, _ = lab.plan_direct(sid, "extent.find_all", {"max_instances": 12})
    _, run, wall = lab.run(sid, plan["plan"]["plan_id"])
    substrate = {
        "trial": "extent.hard_mask · direct operation",
        "form": "extent.hard_mask", "level": "direct_operation",
        "operation": "extent.find_all",
        "outcome": run.get("run", {}).get("outcome"),
        "wall_ms": round(wall),
        "stages": [{"adapter": a.get("adapter"), "state": a.get("state"),
                    "invoked": a.get("invoked"), "duration_ms": a.get("duration_ms"),
                    "detail": a.get("detail")}
                   for a in run.get("run", {}).get("stage_attempts", [])],
        "artifact_ids": run.get("run", {}).get("artifact_ids", []),
        "refusals": run.get("run", {}).get("refusals", []),
        **blank_human(),
    }
    artifacts = run.get("artifacts", [])
    if artifacts:
        provenance = artifacts[0].get("provenance", {})
        substrate["producer"] = provenance.get("producer")
        substrate["adapter"] = provenance.get("adapter")
        substrate["model"] = provenance.get("model")
        substrate["revision"] = provenance.get("revision")
        substrate["device"] = provenance.get("device")
        substrate["peak_memory_mb"] = provenance.get("peak_memory_mb")
        substrate["instances"] = len(
            artifacts[0].get("measurement", {}).get("payload", {}).get("instances", []))

    rows = [substrate]
    artifact_ids = list(substrate.get("artifact_ids") or [])

    # THE TOPOLOGY FORMS NEED RELATIONS, and the first sitting did not measure any — so every one
    # of them came back `missing_extent_inputs`, which is a true refusal and a useless trial. A
    # bounded all-pairs sweep over the extents just measured gives them the same fair chance the
    # Extent forms get from the mask.
    relations = _measure_relations(lab, sid, artifact_ids, _instances(run))
    if relations.get("artifact_ids"):
        rows.append(relations)
        artifact_ids += relations["artifact_ids"]

    derivable = set(catalogue.get("derivable", []))
    for entry in catalogue.get("forms", []):
        form = entry["form"]
        if form == "extent.hard_mask" or form == "topology.pair_relation":
            continue                      # measured above, by the operation that produces it
        if form not in derivable:
            rows.append({
                "trial": f"{form} · not derivable here", "form": form, "level": "direct_form",
                "producible_here": entry["can_be_produced_here"],
                "blocked_by": entry["blocked_by"], "note": entry["note"],
                "producers": entry["producers"], **blank_human()})
            continue
        parameters = dict(DEFAULT_PARAMETERS.get(form, {}))
        if form == "extent.visible_inferred_partition" and substrate.get("instances"):
            # A PARTITION NEEDS A PERSON, and the point of the trial is to show that it says so
            # rather than that it could not find an input. Naming the extent gets it past the
            # input gate to the refusal that matters: nobody painted an inferred part.
            parameters["of"] = f"{artifact_ids[0]}#{_first_instance(run)}"
        status, body, wall = lab.derive(sid, form, artifact_ids, parameters)
        record = (body or {}).get("derivation")
        views = [p["kind"] for p in entry["renderer_projections"]]
        rows.append({
            "trial": f"{form} · direct form", "form": form, "level": "direct_form",
            "http": status, "wall_ms": round(wall),
            "producible_here": entry["can_be_produced_here"],
            "writable_as_artifact": entry["writable_as_artifact"],
            "blocked_by": entry["blocked_by"],
            "producer": (record or {}).get("producer"),
            "producer_kind": (record or {}).get("producer_kind"),
            "producer_revision": (record or {}).get("producer_revision"),
            "model": None,
            "peak_memory_mb": None,
            "record_kind": "derivation" if record else None,
            "derivation_id": (record or {}).get("derivation_id"),
            "ceiling": (record or {}).get("ceiling"),
            "basis": (record or {}).get("basis"),
            "payload_variant": (record or {}).get("payload_variant"),
            "examined": _examined(record),
            "renderings_available": views[:2],
            "refusals": (record or {}).get("refusals") or (body or {}).get("refusals") or [],
            "omitted": (record or {}).get("omitted", []),
            "dropped_parameters": (record or {}).get("dropped_parameters", []),
            **blank_human(),
        })

    after = post_state(post_id)
    return {
        "suite": "forms", "recorded_at": now(), "post_id": post_id, "label": label,
        "session_id": sid, "rows": rows,
        "source_unchanged": before.get("digest") == after.get("digest"),
        "ledger_before": before, "ledger_after": after,
        "lab_collections": lab_collection_counts(),
    }


def _first_instance(run: Mapping[str, Any]) -> str:
    artifacts = run.get("artifacts", [])
    instances = artifacts[0].get("measurement", {}).get("payload", {}).get("instances", []) \
        if artifacts else []
    return instances[0]["instance_id"] if instances else "inst_1"


def _instances(run: Mapping[str, Any]) -> List[str]:
    artifacts = run.get("artifacts", [])
    if not artifacts:
        return []
    payload = artifacts[0].get("measurement", {}).get("payload", {})
    return [i["instance_id"] for i in payload.get("instances", [])]


def _measure_relations(lab: FormLab, sid: str, artifact_ids: List[str],
                       instances: List[str]) -> Dict[str, Any]:
    """A bounded all-pairs sweep, so the topology forms have relations to compose.

    BOUNDED, AND THE BOUND IS RECORDED. `topology.all_pairs` over twelve extents is sixty-six
    pairs; the sweep is capped at the operation's own `max_regions` and the plan says what it was
    clamped to, which is the number a reader should compare the timing against.
    """
    if not artifact_ids or len(instances) < 2:
        return {}
    # MEMBERS ARE INSTANCE-DEEP. `topology.all_pairs` wants at least two extents and every one of
    # these is a mask INSIDE one artifact, so a ref naming only the artifact names one thing and
    # the operation refuses `missing_extent_inputs` — which is what the first sitting recorded,
    # and it was the driver's mistake rather than the organ's.
    chosen = instances[:5]
    lab.select(sid, selected_organ="topology", mode="chain",
               selected_artifact_ids=artifact_ids[:1],
               selected_instance_refs=[{"artifact_id": artifact_ids[0], "instance_id": i}
                                       for i in chosen])
    _, plan, _ = lab.plan_direct(sid, "topology.all_pairs", {"max_regions": 5},
                                 [{"role": "members", "scope": "session",
                                   "artifact_id": artifact_ids[0], "instance_id": i}
                                  for i in chosen])
    plan_body = (plan or {}).get("plan") or {}
    if not plan_body.get("resolved_steps"):
        return {"trial": "topology.pair_relation · direct operation",
                "form": "topology.pair_relation", "level": "direct_operation",
                "operation": "topology.all_pairs", "outcome": "refused",
                "refusals": plan_body.get("refusals", []), "artifact_ids": [], **blank_human()}
    _, run, wall = lab.run(sid, plan_body["plan_id"], confirmed=True)
    body = run.get("run", {})
    provenance = (run.get("artifacts") or [{}])[0].get("provenance", {})
    return {
        "trial": "topology.pair_relation · direct operation",
        "form": "topology.pair_relation", "level": "direct_operation",
        "operation": "topology.all_pairs", "outcome": body.get("outcome"),
        "wall_ms": round(wall), "artifact_ids": body.get("artifact_ids", []),
        "producer": provenance.get("producer"), "adapter": provenance.get("adapter"),
        "model": provenance.get("model"), "revision": provenance.get("revision"),
        "device": provenance.get("device"), "peak_memory_mb": provenance.get("peak_memory_mb"),
        "stages": [{"adapter": a.get("adapter"), "state": a.get("state"),
                    "invoked": a.get("invoked"), "duration_ms": a.get("duration_ms")}
                   for a in body.get("stage_attempts", [])],
        "refusals": body.get("refusals", []), **blank_human(),
    }


def _examined(record: Optional[Mapping[str, Any]]) -> Optional[int]:
    """The count that proves something looked, whichever field this form calls it."""
    payload = (record or {}).get("payload") or {}
    for field in ("rings_traced", "candidates_examined", "regions_examined",
                  "fragments_considered", "cells_partitioned", "pairs_examined",
                  "members_counted", "alternatives_considered"):
        if field in payload:
            return payload[field]
    return None


#: What each form is asked for when nothing but a mask is available. Deliberately MINIMAL: a
#: rehearsal that supplied a hand-made grouping would be rehearsing the person, not the producer,
#: and the empty answer is the one worth recording — it is what a person sees before they decide.
DEFAULT_PARAMETERS: Mapping[str, Mapping[str, Any]] = {
    "extent.fragment_set": {"measure_separation": True},
    "extent.density_field": {"field_shape": [16, 16]},
    "extent.fused_hypothesis": {"groupings": []},
    "extent.hypothesis_set": {"question": "which reading does this picture support?",
                              "readings": []},
    "extent.hierarchy": {"links": []},
}


# ── the recipe level ─────────────────────────────────────────────────────────


def recipe_trials(lab: FormLab, post_id: str, label: str) -> Dict[str, Any]:
    """Every declared study: its readiness, its plan, and what its bounds actually cost."""
    before = post_state(post_id)
    _, catalogue, _ = lab.recipes()
    rows = []

    # ONE SESSION PER STUDY, IN THE MODE THE STUDY DECLARES. A chain study planned into an
    # isolation session is refused `organ_locked` — which is correct, and is a trial of the lock
    # rather than of the study. Both are worth having, so the lock gets its own row below and each
    # study gets a session it can actually run in.
    for recipe in catalogue.get("recipes", []):
        key = recipe["key"]
        _, opened, _ = lab.open_session(post_id, organ=recipe["organ"], mode=recipe["mode"])
        sid = opened["session"]["session_id"]
        _, ready, _ = lab.readiness(sid, key)
        bindings = {step: {name: "the figure" for name in names if name == "concept"}
                    for step, names in (recipe.get("asks_for") or {}).items()}
        status, planned, wall = lab.plan_recipe(sid, key, bindings)
        plan = (planned or {}).get("plan") or {}
        rows.append({
            "trial": f"{key} · recipe", "recipe": key, "level": "recipe",
            "http": status, "wall_ms": round(wall),
            "ready": ready.get("ready"), "reasons": ready.get("reasons", []),
            "declared_operations": len([s for s in recipe["steps"]
                                        if s["kind"] == "operation"]),
            "declared_derivations": len([s for s in recipe["steps"]
                                         if s["kind"] == "derivation"]),
            "bounds": recipe["bounds"],
            "resolved_steps": [{"operation": s["operation"], "adapter": s.get("adapter"),
                                "parameters": s.get("parameters")}
                               for s in plan.get("resolved_steps", [])],
            "refusals": plan.get("refusals", []),
            "requires_confirmation": plan.get("requires_confirmation"),
            "derivations_declared": [d["produces"] for d in (planned or {})
                                     .get("derivations", [])],
            "decision_points": [d["asks"] for d in recipe["decision_points"]],
            "session_mode": recipe["mode"], "session_organ": recipe["organ"],
            "notes": (planned or {}).get("notes", []),
            **blank_human(),
        })

    rows.append(_lock_trial(lab, post_id, catalogue))
    after = post_state(post_id)
    return {
        "suite": "recipes", "recorded_at": now(), "post_id": post_id, "label": label,
        "rows": rows,
        "source_unchanged": before.get("digest") == after.get("digest"),
        "lab_collections": lab_collection_counts(),
    }


def _lock_trial(lab: FormLab, post_id: str, catalogue: Mapping[str, Any]) -> Dict[str, Any]:
    """A chain study planned into an isolation session, deliberately.

    THE POINT IS THAT IT REFUSES. A recipe reaches the same resolver a pressed control does, so
    the organ lock applies to it unchanged — and the only way to show that is to try. A study that
    got through here would mean the recipe route had become a fourth door.
    """
    chain = next((r for r in catalogue.get("recipes", []) if r["mode"] == "chain"), None)
    if chain is None:
        return {}
    _, opened, _ = lab.open_session(post_id, organ="extent", mode="isolation")
    sid = opened["session"]["session_id"]
    _, planned, _ = lab.plan_recipe(sid, chain["key"])
    plan = (planned or {}).get("plan") or {}
    return {
        "trial": f"{chain['key']} · chain study in an ISOLATION session", "level": "recipe",
        "recipe": chain["key"], "session_mode": "isolation", "deliberate_breach": True,
        "resolved_steps": [{"operation": s["operation"]} for s in plan.get("resolved_steps", [])],
        "refusals": [{"code": r["code"], "message": r["message"]}
                     for r in plan.get("refusals", [])],
        "lock_held": any(r["code"] == "organ_locked" for r in plan.get("refusals", [])),
        **blank_human(),
    }


# ── the prompt level, last ───────────────────────────────────────────────────


PROMPTS = (
    "mask every separable thing in this picture",
    "trace the edge of that one",
    "what is inside what",
    "is the shadow part of the figure",
)


def prompt_trials(lab: FormLab, post_id: str, label: str) -> Dict[str, Any]:
    """What the existing conductor makes of a sentence, AFTER direct and recipe are recorded.

    THE ORDER IS THE METHOD. A prompt trial run first would be testing language and the organ at
    once, and a disagreement would have two possible causes. Running it last means every refusal
    here can be read against a direct trial that already worked.
    """
    before = post_state(post_id)
    _, opened, _ = lab.open_session(post_id)
    sid = opened["session"]["session_id"]

    rows = []
    for prompt in PROMPTS:
        status, planned, wall = lab.plan_prompt(sid, prompt)
        plan = (planned or {}).get("plan") or {}
        rows.append({
            "trial": f"prompt · {prompt}", "level": "prompt", "prompt": prompt,
            "http": status, "wall_ms": round(wall),
            "planner": plan.get("planner"),
            "fell_back_from": plan.get("planner_fell_back_from"),
            "proposed": [s["operation"] for s in plan.get("proposed_steps", [])],
            "resolved": [s["operation"] for s in plan.get("resolved_steps", [])],
            "refusals": [{"code": r["code"], "message": r["message"]}
                         for r in plan.get("refusals", [])],
            "dropped_parameters": plan.get("dropped_parameters", []),
            # THE NOTE IS THE ANSWER when nothing matched. The rules table says so in as many
            # words — "an empty proposal is the honest answer; a keyword guess dressed as a plan
            # is not" — and a row that recorded only the empty list would lose it.
            "notes": (planned or {}).get("notes", []),
            "authorized": (planned or {}).get("authorized"),
            # A PROMPT MAY PROPOSE A RECIPE AND NEVER BYPASS IT. There is no route that would let
            # it; this records what it actually reached, which is the only way to show that.
            "reached_a_recipe_route": False,
            **blank_human(),
        })

    after = post_state(post_id)
    return {
        "suite": "prompts", "recorded_at": now(), "post_id": post_id, "label": label,
        "session_id": sid, "rows": rows,
        "source_unchanged": before.get("digest") == after.get("digest"),
        "lab_collections": lab_collection_counts(),
    }


SUITES = {"preflight": None, "forms": form_trials, "recipes": recipe_trials,
          "prompts": prompt_trials}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("suite", choices=sorted(SUITES) + ["all"])
    parser.add_argument("--post", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--out", default=str(REHEARSALS))
    parser.add_argument("--base", default=DEFAULT_BASE)
    args = parser.parse_args(argv)

    lab = FormLab(args.base)
    out = Path(args.out)
    suites = sorted(SUITES) if args.suite == "all" else [args.suite]
    failed = 0
    for name in suites:
        bundle = (preflight(lab, args.post) if name == "preflight"
                  else SUITES[name](lab, args.post, args.label))
        stamp = bundle["recorded_at"].replace(":", "").replace("-", "")[:15]
        path = write(bundle, f"{name}.{args.label or args.post}.{stamp}.json", out)
        green = bundle.get("all_green")
        print(f"{name}: {len(bundle.get('rows', bundle.get('checks', [])))} rows → {path}"
              + ("" if green is None else f"  all_green={green}"))
        if green is False:
            failed = 1
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
