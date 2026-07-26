"""
CIRCUIT-001 TRACE-002 — monocular perspective calibration. DEFERRED, wiring shipped.

Supplies the per-pixel UP-VECTOR field that `external_limit` traces: where gravity points at
each point in the image, from which the local horizon follows by a 90° rotation.

────────────────────────────────────────────────────────────────────────────────
INSTALL VERDICT (probed 2026-07-26, before any code was written — the Intrinsic rule)
────────────────────────────────────────────────────────────────────────────────

PerspectiveFields (jinlinyi/PerspectiveFields) — REJECTED on three independent grounds, any
one of which is sufficient:

  1. LICENCE. "Adobe Research License Terms": research-only, non-commercial. That is not a
     packaging inconvenience, it is a rule about what the software may be used for, and it
     does not become acceptable by being technically easy.
  2. TORCH. Its documented install pins `pytorch=1.10.0` + `cudatoolkit=11.3`. This project
     runs torch 2.13.0+cu130. Satisfying that pin means demolishing the GPU stack every other
     producer on this lane depends on.
  3. DELIVERY. GitHub-only, plus a pinned `pyequilib==0.3.0`.

GeoCalib (cvg/GeoCalib) — the better candidate, and the one this adapter is written against:

  + Apache-2.0. Permissive, no use restriction.
  + Every dependency ALREADY SATISFIED here: torch 2.13.0, torchvision 0.28.0, kornia 0.8.3,
    opencv. Nothing new to install, which is the unusual and pleasant part.
  − Still `pip install git+https://github.com/cvg/GeoCalib` — a custom repo, not PyPI.
  − Weights come via torch.hub from GitHub release v1.0: `geocalib-pinhole.tar`, 116.1 MB.
    That is a NON-HF checkpoint, so WEIGHTS-001's mechanism — a pinned HF commit enforced at
    `from_pretrained` — cannot reach it. It is the "torch-hub repos unpinned" gap already on
    record, arriving as an actual dependency instead of a note.

Both halves of the gate's defer condition are therefore met (custom repo AND non-standard
checkpoint), so the weights are DEFERRED and the wiring is shipped. `is_available()` returns
False until `SEMANT_ENABLE_GEOCALIB=1` is set, exactly as Florence-2 is parked. See
`activation_cost()` for the precise, ordered steps.

The producer never has to know any of this: it asks `up_vector_field()` and gets None, which it
reports as `unavailable` — the same answer a GPU-less machine would give.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

# GeoCalib is loaded through torch.hub, which addresses a repo + ref rather than an HF revision.
# Pinning the COMMIT is possible (`cvg/GeoCalib:<sha>`) and is done here, because torch.hub's
# default is the branch tip — i.e. whatever the authors pushed this morning.
REPO = "cvg/GeoCalib"
REVISION = "97b8968e7798a66bf04fcf791fb535624241bda7"     # main @ 2026-06-28, pinned deliberately
WEIGHTS = "pinhole"                                        # v1.0 geocalib-pinhole.tar · 116.1 MB
MODEL_TAG = "geocalib_pinhole"
ADAPTER = "geocalib"
PREPROCESSING_VERSION = "geocalib-pinhole-v1"
LICENSE = "Apache-2.0"

# Opt-in, like SEMANT_FLORENCE_TRUST_REMOTE_CODE. Absent → this service is honestly unavailable
# rather than half-loading something that is not installed.
ENABLED = os.environ.get("SEMANT_ENABLE_GEOCALIB", "") == "1"

_model = None
_load_failed = False


def activation_cost() -> Dict[str, Any]:
    """Exactly what turning this on requires. Machine-readable so a gate can assert on it."""
    return {
        "package": {
            "install": "pip install 'git+https://github.com/cvg/GeoCalib@"
                       f"{REVISION}#egg=geocalib'",
            "on_pypi": False,
            "new_dependencies": [],          # torch/torchvision/kornia/opencv already present
            "license": LICENSE,
        },
        "weights": {
            "delivery": "torch.hub → GitHub release v1.0",
            "artifact": "geocalib-pinhole.tar",
            "size_mib": 116.1,
            "hf_hosted": False,
            "manifest_pinnable_by_revision": False,
            "note": "WEIGHTS-001 enforces HF commit pins at from_pretrained; a torch.hub "
                    "artifact cannot be pinned that way. Pin the REPO commit and checksum the "
                    "tar, or mirror it to HF and switch this adapter to from_pretrained.",
        },
        "env": {"SEMANT_ENABLE_GEOCALIB": "1"},
        "residency": "GPU. Must be added to /produce-field/unload (already wired) and "
                     "sequenced by ModelManager like every other GPU adapter.",
        "calibration_required": (
            "MIN_PROJECTIVE_SPREAD in suggestion_service is UNCALIBRATED. It was set on "
            "synthetic fields because no real up-vector field can be produced until this "
            "installs. Measure frontal vs receding real images and re-set it before trusting "
            "the refusal, exactly as architectural_axis was calibrated on 18 corpus images."
        ),
        "rejected_alternative": {
            "name": "PerspectiveFields",
            "reasons": ["Adobe Research License Terms (non-commercial)",
                        "pins torch 1.10.0 / cudatoolkit 11.3 against this project's 2.13.0+cu130",
                        "GitHub-only with pinned pyequilib==0.3.0"],
        },
    }


def is_available() -> bool:
    """False until the package is installed AND the opt-in flag is set.

    Both conditions, not either: a machine that happens to have geocalib importable should not
    silently start loading 116 MB of weights inside an unrelated request."""
    if not ENABLED or _load_failed:
        return False
    try:
        import torch  # noqa: F401
        import importlib.util
        return importlib.util.find_spec("geocalib") is not None
    except Exception:
        return False


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load() -> None:
    global _model, _load_failed
    if _model is not None or _load_failed:
        return
    try:
        import torch
        model = torch.hub.load(f"{REPO}:{REVISION}", "GeoCalib",
                               weights=WEIGHTS, trust_repo=True)
        _model = model.to(_device()).eval()
    except Exception as e:  # pragma: no cover — deferred until installed
        _load_failed = True
        print(f"⚠️ GeoCalib load failed (non-fatal, producer reports unavailable): {e}")


def unload() -> None:
    """Free the model. GPU-resident when active, so it belongs in the unload list."""
    global _model
    _model = None
    try:
        import torch, gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def up_vector_field(image, *, grid: int = 16) -> Optional[Dict[str, Any]]:
    """Image → a per-cell up-vector field, or None if the model cannot run.

    Returns ``{"up_x": [...], "up_y": [...], "grid": n, "model", "adapter", "revision",
    "preprocessing_version"}`` — ``up_x``/``up_y`` row-major over an ``n × n`` lattice, each the
    image-space direction of the scene's vertical at that cell (y down, matching every other
    converter here).

    None means "could not look". A model that ran and found a degenerate frame still returns a
    field; judging whether that frame is projective belongs to the producer."""
    if not is_available():
        return None
    _load()
    if _model is None:
        return None
    try:  # pragma: no cover — deferred until installed
        import torch
        from geocalib import utils as gc_utils          # noqa: F401  (import shape pinned at activation)
        rgb = image.convert("RGB")
        with torch.no_grad():
            result = _model.calibrate(_to_tensor(rgb).to(_device()))
        up = result["up_field"] if "up_field" in result else result.get("up")
        up_x, up_y = _lattice(up, grid)
        return {"up_x": up_x, "up_y": up_y, "grid": grid,
                "model": MODEL_TAG, "adapter": ADAPTER, "revision": REVISION,
                "preprocessing_version": PREPROCESSING_VERSION}
    except Exception as e:  # pragma: no cover
        print(f"⚠️ GeoCalib inference failed (non-fatal): {e}")
        return None


def _to_tensor(rgb):  # pragma: no cover — deferred
    import numpy as np
    import torch
    arr = np.asarray(rgb).astype("float32") / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1)


def _lattice(up, grid: int) -> Tuple[List[float], List[float]]:  # pragma: no cover — deferred
    """Downsample a (2, H, W) up-vector map to a grid×grid row-major pair of lists."""
    import torch
    import torch.nn.functional as F
    t = up if up.dim() == 4 else up.unsqueeze(0)
    small = F.interpolate(t, size=(grid, grid), mode="bilinear", align_corners=False)[0]
    ux = small[0].reshape(-1).tolist()
    uy = small[1].reshape(-1).tolist()
    return [float(v) for v in ux], [float(v) for v in uy]
