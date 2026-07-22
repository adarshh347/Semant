"""Foundry Sandbox harness — RESEARCH-ONLY substrate.

This is a THIN WRAPPER over ``scripts/rehearsal_run.py``, not a parallel
universe. It deliberately reuses that module's vendored Draft-2020-12
validator, its JSON/YAML loaders, and the ``rehearsal_adapters`` allowlist,
and it writes observations/traces in the SAME shape the R1/R2 runs use, so a
foundry run is inspectable by the tools that already exist.

Why a separate manifest schema at all: the rehearsal manifest's ``mode`` enum
is ``imaginative|instrumented|prototype|product``. A Foundry Sandbox is a
*standing research declaration* (axis, budget, stop condition, graduation
rule), not a single run's input packet, so it gets its own schema with
``mode: foundry`` and ``research_only: true``.

Hard invariants, enforced here and covered by tests:

  * Builds NO production entity, route, Mongo collection, or UI surface.
  * Imports NOTHING from ``backend``; never touches pymongo/motor/posts.
  * Writes ONLY under ``rehearsals/foundry/runs/<run_id>/``.
  * REPLAY resolves frozen observations ONLY and makes ZERO adapter calls —
    it never even looks up an adapter.
  * CAPTURE is NOT implemented in v1. Live calls require an approved budget
    AND a deliberate future extension; ``max_live_calls > 0`` with
    ``approved: false`` is rejected at validation time.
  * Schema validation is necessary but not sufficient — the semantic guards in
    :func:`validate_sandbox` express what the vendored validator subset cannot
    (``contains``, path denial, cross-field approval gating).

Import-safe: no side effects at import. Exposes importable functions for the
test suite plus a small argparse CLI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:  # importable as a module or runnable as a script
    sys.path.insert(0, _SCRIPTS_DIR)

import rehearsal_adapters  # noqa: E402
import rehearsal_run as rr  # noqa: E402

# --------------------------------------------------------------------------- #
# Paths — everything lives under the vault rehearsal area                      #
# --------------------------------------------------------------------------- #

REPO_ROOT = rr.REPO_ROOT
FOUNDRY_ROOT = os.path.join(rr.REHEARSALS_ROOT, "foundry")
FOUNDRY_SCHEMA_DIR = os.path.join(FOUNDRY_ROOT, "schemas")
FOUNDRY_TEMPLATES_DIR = os.path.join(FOUNDRY_ROOT, "templates")
FOUNDRY_SANDBOXES_DIR = os.path.join(FOUNDRY_ROOT, "sandboxes")
FOUNDRY_RUNS_ROOT = os.path.join(FOUNDRY_ROOT, "runs")

SANDBOX_SCHEMA_FILE = "foundry-sandbox.schema.json"


class FoundryError(Exception):
    """Raised when a foundry invariant is violated."""


# --------------------------------------------------------------------------- #
# Safety baselines                                                             #
# --------------------------------------------------------------------------- #

# Every sandbox manifest's ``forbidden_actions`` must be a SUPERSET of this.
# The vendored validator has no ``contains`` keyword, so this is enforced in
# code. These are the mutations a research sandbox must never perform.
REQUIRED_FORBIDDEN: tuple = (
    "mutate_production_db",
    "create_backend_route",
    "create_mongo_collection",
    "create_product_entity",
    "create_frontend_surface",
    "modify_product_code",
)

# Substrings that mark a path/input as reaching into production. A sandbox that
# declares one of these as an allowed input or a seed is rejected outright —
# research reads fixtures, never the running system.
PRODUCTION_DENY_MARKERS: tuple = (
    "mongodb://",
    "mongodb+srv://",
    "motor",
    "pymongo",
    "backend/routers",
    "backend/models",
    "backend/db",
    "backend/main.py",
    "frontend/src",
    "region_embeddings",
    ".env",
)

# A sandbox may only name adapters that the shared allowlist already exposes.
ALLOWED_ADAPTERS = set(rehearsal_adapters.ALLOWLIST)


# --------------------------------------------------------------------------- #
# Loading + validation                                                         #
# --------------------------------------------------------------------------- #

def load_sandbox_schema(schema_dir: str = FOUNDRY_SCHEMA_DIR) -> Dict[str, Any]:
    """Load the foundry sandbox manifest schema."""
    with open(os.path.join(schema_dir, SANDBOX_SCHEMA_FILE), "r") as fh:
        return json.load(fh)


def load_sandbox(path: str) -> Dict[str, Any]:
    """Load a sandbox manifest from YAML or JSON (reuses the rehearsal loader)."""
    return rr.load_manifest(path)


def _deny_hits(value: str) -> List[str]:
    low = value.lower()
    return [m for m in PRODUCTION_DENY_MARKERS if m in low]


def validate_sandbox(manifest: Dict[str, Any],
                     schema_dir: str = FOUNDRY_SCHEMA_DIR) -> List[str]:
    """Validate a sandbox manifest. Returns a list of error strings (empty = valid).

    Runs the JSON-Schema pass first, then the semantic guards the subset
    validator cannot express. Both passes always run so a caller sees every
    problem at once rather than one per invocation.
    """
    errors: List[str] = list(rr.validate(manifest, load_sandbox_schema(schema_dir)))

    if not isinstance(manifest, dict):
        return errors or ["$: manifest is not an object"]

    # --- research-only invariants (belt AND braces with the schema consts) ---
    if manifest.get("research_only") is not True:
        errors.append("$.research_only: must be exactly true")
    if manifest.get("mode") != "foundry":
        errors.append("$.mode: must be 'foundry'")

    # --- forbidden actions must cover the baseline ---
    declared = manifest.get("forbidden_actions")
    if isinstance(declared, list):
        missing = [f for f in REQUIRED_FORBIDDEN if f not in declared]
        for f in missing:
            errors.append(f"$.forbidden_actions: missing required entry {f!r}")

    # --- adapters must be allowlisted ---
    adapters = manifest.get("adapters")
    if isinstance(adapters, list):
        for a in adapters:
            if a not in ALLOWED_ADAPTERS:
                errors.append(
                    f"$.adapters: {a!r} is not allowlisted; "
                    f"allowed: {sorted(ALLOWED_ADAPTERS)}"
                )

    # --- live calls are approval-gated ---
    budget = manifest.get("model_budget")
    if isinstance(budget, dict):
        max_live = budget.get("max_live_calls")
        if isinstance(max_live, int) and max_live > 0 and budget.get("approved") is not True:
            errors.append(
                "$.model_budget: max_live_calls > 0 requires approved: true "
                "(live model calls need explicit human approval)"
            )
        if isinstance(max_live, int) and max_live > 0 and not adapters:
            errors.append(
                "$.model_budget: max_live_calls > 0 but no adapters are declared"
            )

    # --- replay must be frozen-only ---
    replay = manifest.get("replay_policy")
    if isinstance(replay, dict):
        if replay.get("frozen_observations_only") is not True:
            errors.append("$.replay_policy.frozen_observations_only: must be true")
        if replay.get("adapter_calls_permitted") != 0:
            errors.append("$.replay_policy.adapter_calls_permitted: must be 0")

    # --- no input or seed may reach into production ---
    for field in ("allowed_inputs",):
        for i, item in enumerate(manifest.get(field) or []):
            if isinstance(item, str):
                for hit in _deny_hits(item):
                    errors.append(
                        f"$.{field}[{i}]: production path marker {hit!r} is forbidden"
                    )
    for field in ("seed_images", "seed_text_slices"):
        for i, item in enumerate(manifest.get(field) or []):
            ref = item.get("ref") if isinstance(item, dict) else None
            if isinstance(ref, str):
                for hit in _deny_hits(ref):
                    errors.append(
                        f"$.{field}[{i}].ref: production path marker {hit!r} is forbidden"
                    )

    return errors


def assert_valid_sandbox(manifest: Dict[str, Any],
                         schema_dir: str = FOUNDRY_SCHEMA_DIR) -> None:
    """Raise :class:`FoundryError` unless the manifest is valid."""
    errs = validate_sandbox(manifest, schema_dir)
    if errs:
        raise FoundryError("sandbox manifest invalid: " + "; ".join(errs))


# --------------------------------------------------------------------------- #
# Run scaffolding                                                              #
# --------------------------------------------------------------------------- #

def _manifest_hash(manifest: Dict[str, Any]) -> str:
    blob = json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def run_dir_for(run_id: str, runs_root: str = FOUNDRY_RUNS_ROOT) -> str:
    return os.path.join(runs_root, run_id)


RUN_STATE_FILE = "foundry-run.json"

# The stub set a run carries once summarized. Kept as data so both the
# generator and the tests agree on one list.
SUMMARY_TEMPLATES: Dict[str, str] = {
    "score.md": "score.md",
    "critique.md": "critique.md",
    "sparks.md": "sparks.md",
    "horizon-brief.md": "horizon-brief.md",
    "product-implications.md": "product-implications.md",
}


def init_run(manifest_path: str, run_id: Optional[str] = None,
             runs_root: str = FOUNDRY_RUNS_ROOT,
             schema_dir: str = FOUNDRY_SCHEMA_DIR,
             force: bool = False) -> Dict[str, Any]:
    """Create the folder structure for a sandbox run from its manifest.

    Validates first — an invalid manifest never produces a run directory.
    Refuses to overwrite an initialised run unless ``force`` is set, mirroring
    the rehearsal runner's frozen-run refusal.
    """
    manifest = load_sandbox(manifest_path)
    assert_valid_sandbox(manifest, schema_dir)

    rid = run_id or manifest["sandbox_id"]
    rdir = run_dir_for(rid, runs_root)
    state_path = os.path.join(rdir, RUN_STATE_FILE)
    if os.path.exists(state_path) and not force:
        raise FileExistsError(
            f"run {rid} already initialised at {rdir}; pass force=True to re-init"
        )

    os.makedirs(os.path.join(rdir, "observations"), exist_ok=True)

    state = {
        "run_id": rid,
        "sandbox_id": manifest["sandbox_id"],
        "axis": manifest["axis"],
        "mode": "foundry",
        "research_only": True,
        "status": "initialised",
        "manifest_path": os.path.relpath(os.path.abspath(manifest_path), REPO_ROOT),
        "manifest_sha256": _manifest_hash(manifest),
        "model_budget": manifest["model_budget"],
        "adapters": manifest["adapters"],
        # No wall-clock invention — the rehearsal substrate's honesty rule.
        "created_at": None,
        "created_at_null_reason": "deterministic runner records no wall-clock time",
        "seeds_frozen": False,
        "summarized": False,
    }
    with open(state_path, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    return state


def load_run_state(run_dir: str) -> Dict[str, Any]:
    path = os.path.join(run_dir, RUN_STATE_FILE)
    if not os.path.exists(path):
        raise FileNotFoundError(f"no {RUN_STATE_FILE} in {run_dir}; run `init` first")
    return rr.load_json(path)


# --------------------------------------------------------------------------- #
# Seed freezing                                                                #
# --------------------------------------------------------------------------- #

SEEDS_FILE = "seeds.json"


def _resolve_seed(ref: str) -> str:
    """Resolve a seed ref to an absolute path (repo-relative unless absolute)."""
    return ref if os.path.isabs(ref) else os.path.join(REPO_ROOT, ref)


def freeze_seeds(manifest_path: str, run_dir: str,
                 schema_dir: str = FOUNDRY_SCHEMA_DIR,
                 strict: bool = False) -> Dict[str, Any]:
    """Record content hashes for every declared seed into ``seeds.json``.

    Missing seeds are recorded as ``status: "missing"`` rather than crashing —
    sandboxes are designed before their fixtures exist, and a manifest that
    names a seed the vault does not yet hold is a *known* state worth writing
    down. ``strict=True`` turns a missing seed into an error, which is what a
    pre-execution gate should use.

    Only local files are hashed. Nothing is downloaded and no URL is fetched.
    """
    manifest = load_sandbox(manifest_path)
    assert_valid_sandbox(manifest, schema_dir)

    entries: List[Dict[str, Any]] = []
    for kind in ("seed_images", "seed_text_slices"):
        for item in manifest.get(kind) or []:
            ref = item["ref"]
            path = _resolve_seed(ref)
            entry: Dict[str, Any] = {
                "kind": kind,
                "ref": ref,
                "role": item.get("role"),
                "resolved_path": os.path.relpath(path, REPO_ROOT)
                if path.startswith(REPO_ROOT) else path,
                "sha256": None,
                "size_bytes": None,
                "status": "missing",
            }
            if os.path.isfile(path):
                # Reuse the allowlisted pure adapter — same digest code path the
                # R1 runs use, so hashes are comparable across the program.
                digest = rehearsal_adapters.local_file_digest(path)
                entry["sha256"] = digest["sha256"]
                entry["size_bytes"] = digest["size_bytes"]
                entry["status"] = "present"
            entries.append(entry)

    missing = [e["ref"] for e in entries if e["status"] == "missing"]
    if strict and missing:
        raise FoundryError(f"strict freeze: {len(missing)} seed(s) missing: {missing}")

    payload = {
        "sandbox_id": manifest["sandbox_id"],
        "manifest_sha256": _manifest_hash(manifest),
        "seed_count": len(entries),
        "present_count": sum(1 for e in entries if e["status"] == "present"),
        "missing_count": len(missing),
        "seeds": entries,
        "frozen_at": None,
        "frozen_at_null_reason": "deterministic runner records no wall-clock time",
    }
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, SEEDS_FILE), "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)

    state_path = os.path.join(run_dir, RUN_STATE_FILE)
    if os.path.exists(state_path):
        state = rr.load_json(state_path)
        state["seeds_frozen"] = True
        with open(state_path, "w") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
    return payload


# --------------------------------------------------------------------------- #
# Replay — frozen observations ONLY, zero adapter calls                        #
# --------------------------------------------------------------------------- #

class FoundryReplayResult:
    def __init__(self, run_id: str, status: str, observations: List[str],
                 adapter_calls: int, trace_events: int, run_dir: str):
        self.run_id = run_id
        self.status = status
        self.observations = observations
        self.adapter_calls = adapter_calls
        self.trace_events = trace_events
        self.run_dir = run_dir

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (f"FoundryReplayResult(run_id={self.run_id!r}, status={self.status!r}, "
                f"observations={len(self.observations)}, adapter_calls={self.adapter_calls})")


def replay(run_dir: str, schema_dir: str = rr.SCHEMA_DIR) -> FoundryReplayResult:
    """Reproduce a foundry run from frozen artifacts. Makes ZERO adapter calls.

    This function never resolves an adapter — it does not call
    ``get_adapter``/``adapter_meta`` and does not touch ``ALLOWLIST``. That is
    the guarantee, and it is structural rather than merely intended: there is
    no code path from here to a network, model, or GPU.

    Frozen observations and any trace are validated against the EXISTING
    rehearsal schemas, so foundry artifacts stay inspectable by R1/R2 tooling.
    A run with no observations is valid — a zero-call sandbox is a legitimate
    design, not an incomplete one.
    """
    state = load_run_state(run_dir)

    obs_schema = rr.load_schema("observation", schema_dir)
    observations: List[str] = []
    obs_dir = os.path.join(run_dir, "observations")
    if os.path.isdir(obs_dir):
        for fn in sorted(os.listdir(obs_dir)):
            if not fn.endswith(".json"):
                continue
            obs = rr.load_json(os.path.join(obs_dir, fn))
            errs = rr.validate(obs, obs_schema)
            if errs:
                raise rr.ValidationError(
                    f"frozen observation {fn} invalid: {'; '.join(errs)}"
                )
            observations.append(fn)

    trace_events = 0
    trace_path = os.path.join(run_dir, "trace.json")
    if os.path.exists(trace_path):
        trace = rr.load_json(trace_path)
        errs = rr.validate(trace, rr.load_schema("trace", schema_dir))
        if errs:
            raise rr.ValidationError(f"frozen trace invalid: {'; '.join(errs)}")
        trace_events = len(trace.get("events", []))
        # Every CALL_ORGAN must resolve to a frozen observation, or the run is
        # not replayable and must not be reported as if it were.
        known = {os.path.splitext(f)[0] for f in observations}
        for ev in trace.get("events", []):
            if ev.get("kind") == "CALL_ORGAN":
                ref = ev.get("observation_ref")
                if ref not in known:
                    raise rr.ValidationError(
                        f"trace event {ev.get('event_id')!r} references "
                        f"observation {ref!r} which is not frozen on disk"
                    )

    return FoundryReplayResult(
        run_id=state["run_id"], status="replayed", observations=observations,
        adapter_calls=0, trace_events=trace_events, run_dir=run_dir,
    )


# --------------------------------------------------------------------------- #
# Summarize — generate score / critique / sparks / brief / implications stubs  #
# --------------------------------------------------------------------------- #

def _render(template_text: str, manifest: Dict[str, Any], run_id: str) -> str:
    rubric = manifest.get("scoring_rubric") or {}
    dims = rubric.get("dimensions") or []
    rubric_rows = "\n".join(
        f"| {d.get('name','')} | {d.get('asks','')} | {d.get('scale','')} | _TODO_ |"
        for d in dims
    ) or "| _no dimensions declared_ | | | |"
    stop = manifest.get("stop_condition") or {}
    stop_rows = "\n".join(f"- {s}" for s in (stop.get("stop_when") or [])) or "- _none declared_"

    mapping = {
        "{{SANDBOX_ID}}": str(manifest.get("sandbox_id", "")),
        "{{RUN_ID}}": run_id,
        "{{AXIS}}": str(manifest.get("axis", "")),
        "{{RESEARCH_QUESTION}}": str(manifest.get("research_question", "")),
        "{{RUBRIC_ROWS}}": rubric_rows,
        "{{STOP_ROWS}}": stop_rows,
        "{{BOUNDED_BY}}": str(stop.get("bounded_by", "")),
        "{{MAX_LIVE_CALLS}}": str((manifest.get("model_budget") or {}).get("max_live_calls", "")),
    }
    out = template_text
    for key, val in mapping.items():
        out = out.replace(key, val)
    return out


def summarize(manifest_path: str, run_dir: str,
              templates_dir: str = FOUNDRY_TEMPLATES_DIR,
              schema_dir: str = FOUNDRY_SCHEMA_DIR,
              force: bool = False) -> List[str]:
    """Generate the five reporting stubs into ``run_dir`` from the templates.

    Never overwrites an existing file unless ``force`` — a written score is
    research evidence and the harness must not clobber it.
    """
    manifest = load_sandbox(manifest_path)
    assert_valid_sandbox(manifest, schema_dir)
    state = load_run_state(run_dir)

    written: List[str] = []
    for out_name, tpl_name in sorted(SUMMARY_TEMPLATES.items()):
        tpl_path = os.path.join(templates_dir, tpl_name)
        if not os.path.exists(tpl_path):
            raise FoundryError(f"missing template {tpl_path}")
        out_path = os.path.join(run_dir, out_name)
        if os.path.exists(out_path) and not force:
            continue
        with open(tpl_path, "r") as fh:
            text = fh.read()
        with open(out_path, "w") as fh:
            fh.write(_render(text, manifest, state["run_id"]))
        written.append(out_name)

    state_path = os.path.join(run_dir, RUN_STATE_FILE)
    state["summarized"] = True
    with open(state_path, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    return written


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def _rel(path: str) -> str:
    """Repo-relative when the path is inside the repo, absolute otherwise.

    Tests and ad-hoc runs use a scratch ``--runs-root`` outside the repo, where a
    relative path would render as a wall of ``../``.
    """
    ap = os.path.abspath(path)
    return os.path.relpath(ap, REPO_ROOT) if ap.startswith(REPO_ROOT + os.sep) else ap


def _emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Foundry Sandbox harness (research-only; no live calls in v1)."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate a sandbox manifest")
    v.add_argument("manifest")

    i = sub.add_parser("init", help="create the run folder structure")
    i.add_argument("manifest")
    i.add_argument("--run-id", default=None)
    i.add_argument("--runs-root", default=FOUNDRY_RUNS_ROOT)
    i.add_argument("--force", action="store_true")

    f = sub.add_parser("freeze", help="hash declared seeds into seeds.json")
    f.add_argument("manifest")
    f.add_argument("--run-id", default=None)
    f.add_argument("--runs-root", default=FOUNDRY_RUNS_ROOT)
    f.add_argument("--strict", action="store_true",
                   help="fail if any declared seed is missing")

    r = sub.add_parser("replay", help="replay from frozen observations (zero calls)")
    r.add_argument("run_dir")

    s = sub.add_parser("summarize", help="generate score/critique/sparks/brief stubs")
    s.add_argument("manifest")
    s.add_argument("--run-id", default=None)
    s.add_argument("--runs-root", default=FOUNDRY_RUNS_ROOT)
    s.add_argument("--force", action="store_true")
    return p


def _run_dir_from_args(args: argparse.Namespace) -> str:
    manifest = load_sandbox(args.manifest)
    rid = getattr(args, "run_id", None) or manifest["sandbox_id"]
    return run_dir_for(rid, args.runs_root)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "validate":
        manifest = load_sandbox(args.manifest)
        errs = validate_sandbox(manifest)
        _emit({"manifest": args.manifest, "valid": not errs, "errors": errs})
        return 0 if not errs else 1

    if args.cmd == "init":
        state = init_run(args.manifest, run_id=args.run_id,
                         runs_root=args.runs_root, force=args.force)
        _emit({"initialised": state["run_id"],
               "run_dir": _rel(run_dir_for(state["run_id"], args.runs_root)),
               "state": state})
        return 0

    if args.cmd == "freeze":
        rdir = _run_dir_from_args(args)
        payload = freeze_seeds(args.manifest, rdir, strict=args.strict)
        _emit({"run_dir": _rel(rdir),
               "seed_count": payload["seed_count"],
               "present": payload["present_count"],
               "missing": payload["missing_count"]})
        return 0

    if args.cmd == "replay":
        result = replay(args.run_dir)
        _emit({"run_id": result.run_id, "status": result.status,
               "observations": result.observations,
               "adapter_calls": result.adapter_calls,
               "trace_events": result.trace_events})
        return 0

    if args.cmd == "summarize":
        rdir = _run_dir_from_args(args)
        written = summarize(args.manifest, rdir, force=args.force)
        _emit({"run_dir": _rel(rdir), "written": written})
        return 0

    return 1  # pragma: no cover - argparse enforces the choices


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
