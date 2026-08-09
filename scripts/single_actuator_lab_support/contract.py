"""Paths, schemas, manifests, image digests, and the environment receipt.

THE VALIDATOR IS BORROWED, NOT ADDED. `jsonschema` is not installed in this environment and
`scripts/rehearsal_run.py` already vendors a minimal Draft-2020-12 subset for exactly this
reason. Importing that one rather than vendoring a second copy keeps the two research
substrates validating by the same rules — a lab that validated more loosely than the rehearsal
program would eventually accept a manifest the rest of the research memory would reject.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(_HERE)
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)

# `rehearsal_run` does a bare `from rehearsal_adapters import ...`, so `scripts/` has to be
# importable before it is imported. Same trick `backend/tests/test_rehearsal_r1.py` uses.
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import rehearsal_run as _rr  # noqa: E402

ValidationError = _rr.ValidationError

LABS_ROOT = os.path.join(REPO_ROOT, "research", "rehearsals", "labs")
SCHEMA_DIR = os.path.join(LABS_ROOT, "schemas")
MANIFEST_DIR = os.path.join(LABS_ROOT, "manifests")
RUNS_ROOT = os.path.join(LABS_ROOT, "runs")
TEMPLATE_DIR = os.path.join(LABS_ROOT, "templates")

SCHEMA_FILES = {
    "manifest": "single-actuator-manifest.schema.json",
    "trace": "single-actuator-trace.schema.json",
    "score": "single-actuator-score.schema.json",
}

MANIFEST_VERSION = "single-actuator-manifest.v1"
TRACE_VERSION = "single-actuator-trace.v1"
SCORE_VERSION = "single-actuator-score.v1"

MODES = ("organ_direct", "actuator_direct", "prompt_orchestrated", "replay")


# ── schemas ───────────────────────────────────────────────────────────────────────────────────

def load_schema(name: str, schema_dir: str = SCHEMA_DIR) -> Dict[str, Any]:
    if name not in SCHEMA_FILES:
        raise KeyError(f"unknown lab schema {name!r}; known: {sorted(SCHEMA_FILES)}")
    with open(os.path.join(schema_dir, SCHEMA_FILES[name]), "r") as fh:
        return json.load(fh)


def validate(instance: Any, schema_name: str, *, raise_on_error: bool = False,
             schema_dir: str = SCHEMA_DIR) -> List[str]:
    """Validate against a lab schema. Empty list means valid."""
    return _rr.validate(instance, load_schema(schema_name, schema_dir),
                        raise_on_error=raise_on_error)


# ── digests ───────────────────────────────────────────────────────────────────────────────────

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    """A digest of a structure, stable across dict ordering. Used for post invariance."""
    return sha256_bytes(json.dumps(obj, sort_keys=True, default=str).encode("utf-8"))


# ── manifests ─────────────────────────────────────────────────────────────────────────────────

class ManifestError(Exception):
    """A manifest that cannot be trusted to bound a run. Always fatal — a lab that proceeds on
    a manifest it could not verify is not a lab."""


def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, "r") as fh:
        text = fh.read()
    if path.endswith((".yaml", ".yml")):
        import yaml
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: manifest is not a mapping")
    return data


def check_manifest(manifest: Dict[str, Any], *, source: str = "<manifest>") -> Dict[str, Any]:
    """Schema-validate, then check the things a schema cannot express.

    The three extra checks are the lock itself, and each of them has a failure it prevents:

      · a mode that needs a phrase without one would silently become "segment nothing", and SAM 3
        returns something for very nearly any phrase, so the degenerate case is not harmless;
      · a prompt_orchestrated run without a prompt would be a control run wearing an
        orchestration label, which is the exact confusion the arms exist to separate;
      · an actuator_lock the production table has never heard of would lock the lab to a name
        that can never fire, and every run would report an honest-looking zero.
    """
    errors = validate(manifest, "manifest")
    if errors:
        raise ManifestError(f"{source}: " + "; ".join(errors))

    mode = manifest["mode"]
    lock = manifest["actuator_lock"]

    from backend.services.director import capabilities
    if capabilities.get(lock) is None:
        raise ManifestError(
            f"{source}: actuator_lock {lock!r} is not in the production capability table "
            f"({', '.join(sorted(capabilities.known()))})")

    if mode in ("organ_direct", "actuator_direct") and not (manifest.get("control_phrase") or "").strip():
        raise ManifestError(f"{source}: mode {mode!r} requires a control_phrase")
    if mode == "prompt_orchestrated" and not (manifest.get("prompt") or "").strip():
        raise ManifestError(f"{source}: mode 'prompt_orchestrated' requires a prompt")

    image = manifest["image"]
    abs_path = os.path.join(REPO_ROOT, image["path"])
    if not os.path.exists(abs_path):
        raise ManifestError(f"{source}: image not found at {image['path']}")
    return manifest


def resolve_image(manifest: Dict[str, Any]) -> Tuple[str, bytes, str]:
    """(absolute path, bytes, sha256) — with the manifest's checksum ENFORCED.

    A mismatch aborts rather than proceeding with a note. The whole comparison between a control
    run and an orchestrated run rests on them having seen the same pixels; a run against a
    different image than the manifest names is not a weaker result, it is a different experiment
    filed under the wrong name.
    """
    image = manifest["image"]
    abs_path = os.path.join(REPO_ROOT, image["path"])
    with open(abs_path, "rb") as fh:
        data = fh.read()
    digest = sha256_bytes(data)
    declared = (image.get("sha256") or "").strip().lower()
    if declared and declared != digest:
        raise ManifestError(
            f"image checksum mismatch for {image['path']}: manifest says {declared}, "
            f"file is {digest}")
    return abs_path, data, digest


# ── environment receipt ───────────────────────────────────────────────────────────────────────

#: Resolved ONCE per process. Two reasons, and the second is the better one.
#:
#: Cost: `git status --porcelain` ran per capture, so a 56-cell matrix paid it 56 times — around a
#: second and a half each on this tree, which was most of a matrix run and most of the focused
#: test suite.
#:
#: Correctness: the commit cannot change mid-run, and re-measuring `dirty` after the lab has begun
#: writing its own run directories reports the LAB's output as a dirty working tree. What a reader
#: wants from that flag is whether the code under test was clean when the run started, so taking
#: it once, at process start, is the more truthful measurement as well as the cheaper one.
_GIT_RECEIPT: Optional[Tuple[Optional[str], Optional[bool]]] = None


def git_commit() -> Tuple[Optional[str], Optional[bool]]:
    global _GIT_RECEIPT
    if _GIT_RECEIPT is None:
        _GIT_RECEIPT = _git_commit_uncached()
    return _GIT_RECEIPT


def _git_commit_uncached() -> Tuple[Optional[str], Optional[bool]]:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=10)
        if head.returncode != 0:
            return None, None
        status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT,
                                capture_output=True, text=True, timeout=10)
        dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
        return head.stdout.strip(), dirty
    except Exception:
        return None, None


def environment_receipt(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """What ran, on what, with which weights.

    CREDENTIALS AND FULL WEIGHTS PATHS ARE NOT FROZEN. `weights_present` is a boolean and
    `weights_id` is a basename: a checkpoint path is machine-local and routinely contains a
    username, and a trace is a document meant to be read by other people.
    """
    from backend.services import sam3_concept_service as svc

    commit, dirty = git_commit()
    expect = manifest.get("model_expectation") or {}
    weights = svc.weights_path()

    runtime = False
    torch_version = None
    try:
        import torch
        torch_version = getattr(torch, "__version__", None)
        from ultralytics.models.sam import SAM3SemanticPredictor  # noqa: F401
        runtime = True
    except Exception:
        runtime = False

    device = None
    if runtime:
        try:
            device = svc.device()
        except Exception:
            device = None

    return {
        "git_commit": commit,
        "git_dirty": dirty,
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "python": platform.python_version(),
        "device": device,
        "weights_present": weights is not None,
        "weights_id": os.path.basename(weights) if weights else None,
        "runtime_available": runtime,
        "checkpoint": expect.get("checkpoint") or svc.CHECKPOINT,
        "preprocessing_version": expect.get("preprocessing_version") or svc.PREPROCESSING_VERSION,
        "conf": expect.get("conf") if expect.get("conf") is not None else svc.DEFAULT_CONF,
        "imgsz": expect.get("imgsz") if expect.get("imgsz") is not None else svc.DEFAULT_IMGSZ,
        "naming_floor": svc.NAMING_CONFIDENCE_FLOOR,
        "torch_version": torch_version,
        # Filled in AFTER the call by `imgsz_receipt` — see there.
        "imgsz_effective": None,
        "imgsz_note": None,
    }


#: Ultralytics rounds `imgsz` up to a multiple of the model's stride at inference time and
#: announces it in a log line only: a run asking for 1024 is served at 1036. That matters —
#: resolution is one of the few settings that plausibly changes what a segmenter finds, and two
#: runs at different real resolutions would otherwise look identical in the record.
IMGSZ_NOT_EXPOSED = (
    "requested only. Ultralytics rounds imgsz up to a multiple of the model stride inside the "
    "inference call and does not write the rounded value back to predictor.args, so the "
    "effective size cannot be read from this seam. Observed in the SAM 3 runs: a requested "
    "1024 was logged as 1036. Recorded as absent rather than filled in with the request."
)


def imgsz_receipt() -> Tuple[Optional[int], str]:
    """(effective imgsz, note). The effective value is None, and that is the honest answer.

    This function existed briefly reading `predictor.args.imgsz` and reporting it as the
    effective size. It is not: that attribute still holds the REQUEST, so the field agreed with
    `imgsz` every time and looked like a confirmation when it was an echo. A receipt that echoes
    the request under a name meaning "what actually happened" is worse than no receipt, because
    a reader checking whether the rounding occurred would come away believing it had not.
    """
    return None, IMGSZ_NOT_EXPOSED


# ── run directories ───────────────────────────────────────────────────────────────────────────

def run_dir(run_id: str, runs_root: str = RUNS_ROOT) -> str:
    return os.path.join(runs_root, run_id)


def is_frozen(path: str) -> bool:
    """A run directory is frozen once it holds a trace. `capture` refuses to overwrite one."""
    return os.path.exists(os.path.join(path, "trace.json"))


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, sort_keys=False)
        fh.write("\n")


def read_json(path: str) -> Any:
    with open(path, "r") as fh:
        return json.load(fh)
