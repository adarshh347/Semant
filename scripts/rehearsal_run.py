"""Deterministic rehearsal runner (R1) — RESEARCH-ONLY substrate.

This module builds NO production entity, route, or Mongo collection. It writes
ONLY to a ``runs/`` directory on disk. It imports NOTHING from ``backend`` and
never touches ``pymongo``/``motor``/``posts``/``region_embeddings``.

Two strictly separated execution paths:

  * CAPTURE — may invoke ONE allowlisted, model-free adapter
    (``local_file_digest``) and freeze the full observation to
    ``runs/<id>/observations/``.
  * REPLAY  — uses ONLY frozen observations; makes NO network / model / GPU /
    adapter call and reproduces the event trace deterministically.

It is import-safe (no side effects at import) and exposes both importable
functions (for tests) and a small argparse CLI.

Because ``jsonschema`` is not installed in this environment, a MINIMAL,
self-contained Draft-2020-12 validator (subset) is vendored below rather than
adding a dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:  # yaml is available in this venv; keep import local-safe regardless
    import yaml  # type: ignore
except Exception:  # pragma: no cover - defensive
    yaml = None  # type: ignore

from rehearsal_adapters import (  # noqa: E402
    ALLOWLIST,
    AdapterNotAllowed,
    adapter_meta,
    get_adapter,
)

# --------------------------------------------------------------------------- #
# Paths                                                                        #
# --------------------------------------------------------------------------- #

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The rehearsal research home moved into the vault Build space (AGENTS.md: docs live in
# vault/Build/Architecture Lab; top-level architecture-lab is retired and must not be recreated).
REHEARSALS_ROOT = os.path.join(
    REPO_ROOT, "vault", "Build", "Architecture Lab", "Vision pipeline", "rehearsals"
)
SCHEMA_DIR = os.path.join(REHEARSALS_ROOT, "schemas")
DEFAULT_RUNS_ROOT = os.path.join(REHEARSALS_ROOT, "runs")

SCHEMA_FILES = {
    "manifest": "rehearsal-manifest.schema.json",
    "trace": "rehearsal-trace.schema.json",
    "candidate": "candidate-card.schema.json",
    "observation": "frozen-observation.schema.json",
}


# --------------------------------------------------------------------------- #
# Vendored minimal JSON-Schema validator (Draft 2020-12 subset)               #
# --------------------------------------------------------------------------- #

class ValidationError(Exception):
    """Raised by :func:`validate` when ``raise_on_error`` is set."""


_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    # bool is a subclass of int in Python — exclude it from number/integer.
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
}


def _check_type(value: Any, type_spec: Any) -> bool:
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    return any(_TYPE_CHECKS.get(t, lambda _v: False)(value) for t in types)


def _resolve_ref(ref: str, root: Dict[str, Any]) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValidationError(f"unsupported $ref (only local refs): {ref!r}")
    node: Any = root
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[token]
    return node


def _validate(value: Any, schema: Any, root: Dict[str, Any], path: str,
              errors: List[str]) -> None:
    if schema is True or schema == {}:
        return
    if schema is False:
        errors.append(f"{path}: schema is false; nothing is valid")
        return
    if "$ref" in schema:
        _validate(value, _resolve_ref(schema["$ref"], root), root, path, errors)
        # fall through: sibling keywords are allowed in 2020-12

    if "const" in schema and value != schema["const"]:
        # distinguish None const from mismatch cleanly
        if not (schema["const"] is None and value is None):
            errors.append(f"{path}: {value!r} != const {schema['const']!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")

    if "type" in schema and not _check_type(value, schema["type"]):
        errors.append(f"{path}: {type(value).__name__} not of type {schema['type']}")
        return  # further keyword checks assume the type held

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string shorter than minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: {value!r} does not match pattern {schema['pattern']!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: array shorter than minItems {schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(value):
                _validate(item, schema["items"], root, f"{path}[{i}]", errors)

    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required property {req!r}")
        props = schema.get("properties", {})
        for key, subschema in props.items():
            if key in value:
                _validate(value[key], subschema, root, f"{path}.{key}", errors)
        addl = schema.get("additionalProperties", True)
        if addl is False:
            extra = set(value) - set(props)
            for key in sorted(extra):
                errors.append(f"{path}: additional property {key!r} not allowed")

    for combiner in ("allOf",):
        for i, sub in enumerate(schema.get(combiner, [])):
            _validate(value, sub, root, path, errors)
    if "anyOf" in schema:
        if not any(_is_valid(value, sub, root) for sub in schema["anyOf"]):
            errors.append(f"{path}: does not match anyOf")
    if "oneOf" in schema:
        matches = sum(1 for sub in schema["oneOf"] if _is_valid(value, sub, root))
        if matches != 1:
            errors.append(f"{path}: matched {matches} oneOf branches (want 1)")

    if "if" in schema:
        if _is_valid(value, schema["if"], root):
            if "then" in schema:
                _validate(value, schema["then"], root, path, errors)
        elif "else" in schema:
            _validate(value, schema["else"], root, path, errors)


def _is_valid(value: Any, schema: Any, root: Dict[str, Any]) -> bool:
    errs: List[str] = []
    _validate(value, schema, root, "$", errs)
    return not errs


def validate(instance: Any, schema: Dict[str, Any],
             raise_on_error: bool = False) -> List[str]:
    """Validate ``instance`` against ``schema``; return a list of error strings.

    An empty list means valid. When ``raise_on_error`` is True, raises
    :class:`ValidationError` on the first failure.
    """
    errors: List[str] = []
    _validate(instance, schema, schema, "$", errors)
    if errors and raise_on_error:
        raise ValidationError("; ".join(errors))
    return errors


# --------------------------------------------------------------------------- #
# Loading helpers                                                             #
# --------------------------------------------------------------------------- #

def load_schema(name: str, schema_dir: str = SCHEMA_DIR) -> Dict[str, Any]:
    """Load one of the four research schemas by short name."""
    if name not in SCHEMA_FILES:
        raise KeyError(f"unknown schema {name!r}; known: {sorted(SCHEMA_FILES)}")
    with open(os.path.join(schema_dir, SCHEMA_FILES[name]), "r") as fh:
        return json.load(fh)


def load_all_schemas(schema_dir: str = SCHEMA_DIR) -> Dict[str, Dict[str, Any]]:
    return {name: load_schema(name, schema_dir) for name in SCHEMA_FILES}


def load_manifest(path: str) -> Dict[str, Any]:
    """Load a manifest from YAML or JSON."""
    with open(path, "r") as fh:
        text = fh.read()
    if path.endswith((".yaml", ".yml")):
        if yaml is None:  # pragma: no cover
            raise RuntimeError("PyYAML unavailable; cannot parse YAML manifest")
        return yaml.safe_load(text)
    return json.loads(text)


def load_json(path: str) -> Any:
    with open(path, "r") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Percept-id classification (pct_ attention vs pctx_ expression)              #
# --------------------------------------------------------------------------- #

def classify_percept_id(percept_id: Any) -> str:
    """Classify a percept id string.

    Returns ``"expression_percept"`` for ``pctx_*`` ids, ``"attention_percept"``
    for ``pct_*`` (but not ``pctx_``) ids, and ``"unknown"`` for anything
    ambiguous or bare. Raises ``TypeError`` for non-strings.
    """
    if not isinstance(percept_id, str):
        raise TypeError(f"percept id must be a string, got {type(percept_id).__name__}")
    if percept_id.startswith("pctx_") and len(percept_id) > len("pctx_"):
        return "expression_percept"
    if percept_id.startswith("pct_") and len(percept_id) > len("pct_"):
        return "attention_percept"
    return "unknown"


# --------------------------------------------------------------------------- #
# Run outcome                                                                  #
# --------------------------------------------------------------------------- #

class RunResult:
    def __init__(self, rehearsal_id: str, mode: str, status: str,
                 trace: Dict[str, Any], run_dir: str,
                 observations: Optional[List[str]] = None,
                 adapter_calls: int = 0, score_ref: Optional[str] = None):
        self.rehearsal_id = rehearsal_id
        self.mode = mode
        self.status = status
        self.trace = trace
        self.run_dir = run_dir
        self.observations = observations or []
        self.adapter_calls = adapter_calls
        self.score_ref = score_ref

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (f"RunResult(id={self.rehearsal_id!r}, mode={self.mode!r}, "
                f"status={self.status!r}, adapter_calls={self.adapter_calls}, "
                f"observations={len(self.observations)})")


def _run_dir(runs_root: str, rehearsal_id: str) -> str:
    return os.path.join(runs_root, rehearsal_id)


def _is_frozen(run_dir: str) -> bool:
    """A run dir is 'frozen' once it holds a trace.json."""
    return os.path.exists(os.path.join(run_dir, "trace.json"))


# --------------------------------------------------------------------------- #
# Observation capture / freeze                                                 #
# --------------------------------------------------------------------------- #

def _content_hash(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def capture_observation(adapter_name: str, observation_id: str,
                        provenance: str, **kwargs: Any) -> Dict[str, Any]:
    """Invoke ONE allowlisted adapter and build a frozen-observation dict.

    Raises ``AdapterNotAllowed`` for any non-allowlisted adapter name. Records
    only what the adapter actually returns; unavailable telemetry stays null.
    """
    adapter = get_adapter(adapter_name)  # raises if not allowlisted
    meta = adapter_meta(adapter_name)
    output = adapter(**kwargs)
    # Telemetry is recorded ONLY when the adapter actually measured it. A pure
    # local digest measures neither latency nor cost, and those stay null rather
    # than being invented; a remote model call reports both, and the observation
    # carries the real numbers through.
    measured = output if isinstance(output, dict) else {}
    usage = measured.get("usage")
    body = {
        "observation_id": observation_id,
        "adapter": adapter_name,
        "request_boundary": meta.get("request_boundary", "unknown"),
        "model": measured.get("model") or meta.get("model"),
        "version": meta.get("version"),
        "device": meta.get("device"),
        "cost": {"token_usage": usage} if isinstance(usage, dict) else None,
        "latency_ms": measured.get("latency_ms"),
        "output": output,
        "uncertainty": None,
        "provenance": provenance,
        "captured_at": None,   # deterministic runner: no wall-clock invention
    }
    body["content_hash"] = _content_hash(body)
    return body


# --------------------------------------------------------------------------- #
# Trace assembly                                                               #
# --------------------------------------------------------------------------- #

def _new_trace(rehearsal_id: str, reconstructed: bool = False) -> Dict[str, Any]:
    return {
        "rehearsal_id": rehearsal_id,
        "reconstructed": reconstructed,
        "status": "in_progress",
        "score_ref": None,
        "events": [],
    }


def append_event(trace: Dict[str, Any], **fields: Any) -> Dict[str, Any]:
    """Append (append-only) a fully-formed event onto a trace."""
    trace["events"].append(fields)
    return fields


def make_terminal_event(event_id: str, actor: str, outcome: str,
                        reason: str, parent_event: Optional[str]) -> Dict[str, Any]:
    """Build a terminal event recording a refusal / stall as a valid outcome."""
    return {
        "event_id": event_id,
        "actor": actor,
        "kind": "HARVEST",
        "parent_event": parent_event,
        "source_refs": [],
        "target_refs": [],
        "register": "opening",
        "uncertainty": None,
        "reconstructed": False,
        "observation_ref": None,
        "reversibility": "n/a",
        "cost": None,
        "provenance": f"runner:terminal:{outcome}",
        "timestamp": None,
        "timestamp_null_reason": "deterministic runner records no wall-clock time",
        "terminal": True,
        "outcome": outcome,
        "note": reason,
    }


# --------------------------------------------------------------------------- #
# The runner                                                                   #
# --------------------------------------------------------------------------- #

def run(manifest_path: str, mode: str, runs_root: str = DEFAULT_RUNS_ROOT,
        force_new_id: bool = False, capture_targets: Optional[List[str]] = None,
        refuse_reason: Optional[str] = None, schema_dir: str = SCHEMA_DIR,
        probes: Optional[List[Dict[str, Any]]] = None) -> RunResult:
    """Execute a rehearsal run in ``capture`` or ``replay`` mode.

    * Validates the manifest against the manifest schema.
    * REPLAY: reads the frozen ``trace.json`` (+ frozen observations) and
      reproduces the trace deterministically, invoking NO adapter.
    * CAPTURE: may invoke the allowlisted adapter on ``capture_targets`` and
      freezes each observation; refuses to overwrite a frozen run dir unless
      ``force_new_id`` is set.
    * ``probes`` (R2) is the general form of ``capture_targets``: a list of
      ``{"adapter": name, "kwargs": {...}}`` dicts naming ANY allowlisted
      adapter. ``capture_targets`` remains the R1 shorthand for
      ``local_file_digest``. Probes run after targets and continue the same
      event/observation numbering.
    * A ``refuse_reason`` ends the run in status ``refused`` WITHOUT raising.

    Never writes to Mongo / posts / region_embeddings / any production schema.
    """
    if mode not in ("capture", "replay"):
        raise ValueError(f"mode must be 'capture' or 'replay', got {mode!r}")

    schemas = load_all_schemas(schema_dir)
    manifest = load_manifest(manifest_path)
    errs = validate(manifest, schemas["manifest"])
    if errs:
        raise ValidationError(f"manifest invalid: {'; '.join(errs)}")

    rehearsal_id = manifest["rehearsal_id"]
    run_dir = _run_dir(runs_root, rehearsal_id)
    score_ref = _score_ref_for(run_dir)

    if mode == "replay":
        return _run_replay(rehearsal_id, run_dir, schemas, score_ref)

    return _run_capture(
        manifest, rehearsal_id, run_dir, runs_root, schemas, score_ref,
        force_new_id=force_new_id, capture_targets=capture_targets or [],
        refuse_reason=refuse_reason, probes=probes or [],
    )


def _score_ref_for(run_dir: str) -> Optional[str]:
    src = os.path.join(run_dir, "source.md")
    if os.path.exists(src):
        return f"{os.path.relpath(src, REPO_ROOT)}#passage-score"
    return None


def _run_replay(rehearsal_id: str, run_dir: str,
                schemas: Dict[str, Any], score_ref: Optional[str]) -> RunResult:
    trace_path = os.path.join(run_dir, "trace.json")
    if not os.path.exists(trace_path):
        raise FileNotFoundError(
            f"replay requires a frozen trace at {trace_path}"
        )
    trace = load_json(trace_path)
    errs = validate(trace, schemas["trace"])
    if errs:
        raise ValidationError(f"frozen trace invalid: {'; '.join(errs)}")

    # Load — but never re-execute — any frozen observations.
    obs_dir = os.path.join(run_dir, "observations")
    observations: List[str] = []
    if os.path.isdir(obs_dir):
        for fn in sorted(os.listdir(obs_dir)):
            if fn.endswith(".json"):
                obs = load_json(os.path.join(obs_dir, fn))
                oerrs = validate(obs, schemas["observation"])
                if oerrs:
                    raise ValidationError(
                        f"frozen observation {fn} invalid: {'; '.join(oerrs)}"
                    )
                observations.append(fn)

    # REPLAY makes ZERO adapter calls by construction.
    return RunResult(
        rehearsal_id=rehearsal_id, mode="replay", status=trace.get("status", "completed"),
        trace=trace, run_dir=run_dir, observations=observations,
        adapter_calls=0, score_ref=score_ref,
    )


def _run_capture(manifest: Dict[str, Any], rehearsal_id: str, run_dir: str,
                 runs_root: str, schemas: Dict[str, Any],
                 score_ref: Optional[str], force_new_id: bool,
                 capture_targets: List[str],
                 refuse_reason: Optional[str],
                 probes: Optional[List[Dict[str, Any]]] = None) -> RunResult:
    if _is_frozen(run_dir) and not force_new_id:
        raise FileExistsError(
            f"run dir {run_dir} already holds a frozen trace.json; "
            f"pass force_new_id=True to write under a fresh id"
        )
    if _is_frozen(run_dir) and force_new_id:
        rehearsal_id = _fresh_id(runs_root, rehearsal_id)
        run_dir = _run_dir(runs_root, rehearsal_id)

    os.makedirs(os.path.join(run_dir, "observations"), exist_ok=True)
    trace = _new_trace(rehearsal_id, reconstructed=False)
    trace["score_ref"] = score_ref

    # A refusal is a valid terminal outcome — record it, do not raise.
    if refuse_reason is not None:
        term = make_terminal_event(
            event_id=f"{rehearsal_id}-e0", actor="system", outcome="refused",
            reason=refuse_reason, parent_event=None,
        )
        append_event(trace, **term)
        trace["status"] = "refused"
        _write_trace(run_dir, trace, schemas)
        return RunResult(
            rehearsal_id=rehearsal_id, mode="capture", status="refused",
            trace=trace, run_dir=run_dir, observations=[], adapter_calls=0,
            score_ref=score_ref,
        )

    adapter_calls = 0
    observations: List[str] = []
    parent: Optional[str] = None
    # RECEIVE the initiating act as the first event.
    recv = {
        "event_id": f"{rehearsal_id}-e0", "actor": manifest["initiating_act"]["actor"],
        "kind": "RECEIVE", "parent_event": None, "source_refs": [], "target_refs": [],
        "register": "opening", "uncertainty": None, "reconstructed": False,
        "observation_ref": None, "reversibility": "reversible", "cost": None,
        "provenance": "runner:capture:receive", "timestamp": None,
        "timestamp_null_reason": "deterministic runner records no wall-clock time",
    }
    append_event(trace, **recv)
    parent = recv["event_id"]

    # R1 shorthand targets first, then R2 general probes — one shared code path so
    # both produce identical observation/event structure.
    steps: List[Tuple[str, Dict[str, Any], List[str]]] = [
        ("local_file_digest", {"path": t}, [t]) for t in capture_targets
    ]
    for probe in (probes or []):
        name = probe["adapter"]
        kwargs = dict(probe.get("kwargs", {}))
        steps.append((name, kwargs, list(probe.get("source_refs", []))))
    throttles = [0.0] * len(capture_targets) + [
        float(p.get("sleep_before_s") or 0.0) for p in (probes or [])
    ]

    for i, (adapter_name, kwargs, source_refs) in enumerate(steps):
        # Rate-limit throttle. CAPTURE-only: replay never reaches this code, so the
        # frozen run stays instantaneous and deterministic.
        if throttles[i] > 0:
            time.sleep(throttles[i])
        obs_id = f"{rehearsal_id}-obs{i}"
        obs = capture_observation(
            adapter_name, obs_id,
            provenance=f"capture:{rehearsal_id}:{adapter_name}", **kwargs,
        )
        oerrs = validate(obs, schemas["observation"])
        if oerrs:
            raise ValidationError(f"captured observation invalid: {'; '.join(oerrs)}")
        obs_fn = f"{obs_id}.json"
        with open(os.path.join(run_dir, "observations", obs_fn), "w") as fh:
            json.dump(obs, fh, indent=2, sort_keys=True)
        observations.append(obs_fn)
        adapter_calls += 1

        ev = {
            "event_id": f"{rehearsal_id}-e{i + 1}", "actor": "system",
            "kind": "CALL_ORGAN", "parent_event": parent, "source_refs": source_refs,
            "target_refs": [], "register": "evidence", "uncertainty": None,
            "reconstructed": False, "observation_ref": obs_id,
            "reversibility": "reversible", "cost": None,
            "provenance": "runner:capture:call_organ", "timestamp": None,
            "timestamp_null_reason": "deterministic runner records no wall-clock time",
        }
        append_event(trace, **ev)
        parent = ev["event_id"]

    trace["status"] = "completed"
    _write_trace(run_dir, trace, schemas)
    return RunResult(
        rehearsal_id=rehearsal_id, mode="capture", status="completed",
        trace=trace, run_dir=run_dir, observations=observations,
        adapter_calls=adapter_calls, score_ref=score_ref,
    )


def _fresh_id(runs_root: str, base_id: str) -> str:
    n = 1
    while os.path.exists(_run_dir(runs_root, f"{base_id}-v{n}")):
        n += 1
    return f"{base_id}-v{n}"


def _write_trace(run_dir: str, trace: Dict[str, Any],
                 schemas: Dict[str, Any]) -> None:
    errs = validate(trace, schemas["trace"])
    if errs:
        raise ValidationError(f"refusing to write invalid trace: {'; '.join(errs)}")
    with open(os.path.join(run_dir, "trace.json"), "w") as fh:
        json.dump(trace, fh, indent=2, sort_keys=True)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deterministic rehearsal runner (R1, research-only)."
    )
    p.add_argument("manifest", help="path to a rehearsal manifest (.yaml/.json)")
    p.add_argument("--mode", choices=["capture", "replay"], required=True)
    p.add_argument("--runs-root", default=DEFAULT_RUNS_ROOT)
    p.add_argument("--force-new-id", action="store_true",
                   help="capture into a fresh id instead of overwriting a frozen run")
    p.add_argument("--capture-target", action="append", default=[],
                   help="file to digest via local_file_digest (capture mode; repeatable)")
    p.add_argument("--refuse-reason", default=None,
                   help="end the run in status 'refused' with this reason (no raise)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run(
        manifest_path=args.manifest, mode=args.mode, runs_root=args.runs_root,
        force_new_id=args.force_new_id, capture_targets=args.capture_target,
        refuse_reason=args.refuse_reason,
    )
    print(json.dumps({
        "rehearsal_id": result.rehearsal_id,
        "mode": result.mode,
        "status": result.status,
        "adapter_calls": result.adapter_calls,
        "observations": result.observations,
        "score_ref": result.score_ref,
        "run_dir": os.path.relpath(result.run_dir, REPO_ROOT),
        "events": len(result.trace.get("events", [])),
    }, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
