"""Rehearsal research adapters (R1) — allowlisted, read-only, side-effect-free.

RESEARCH-ONLY. This module is imported by ``scripts/rehearsal_run.py`` and the
R1 test suite. It deliberately imports NOTHING from ``backend`` and touches no
Mongo/production code path.

R1 ADAPTER SCOPE (hard rule):
    The ONLY allowlisted adapter is a trivial LOCAL, PURE one —
    ``local_file_digest`` — which proves the capture path records provenance
    without invoking any sensory model. SAM / YOLO / SegFormer / DINOv2 /
    FashionCLIP / the semantic provider / any LLM are OUT OF SCOPE for R1 and
    are NOT registered here. Requesting a non-allowlisted adapter raises.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Callable, Dict


class AdapterNotAllowed(Exception):
    """Raised when a non-allowlisted adapter name is requested."""


def local_file_digest(path: str) -> Dict[str, Any]:
    """Pure, local, model-free adapter: digest a file on disk.

    Returns provenance-bearing output with no network, GPU, or model call.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "path": os.path.abspath(path),
    }


# The ALLOWLIST is the single source of truth for what CAPTURE mode may invoke.
# Adding a sensory/model adapter here would violate the R1 invariant.
ALLOWLIST: Dict[str, Callable[..., Any]] = {
    "local_file_digest": local_file_digest,
}

# Static metadata describing each adapter's request boundary and model/device.
# For R1 the only adapter is model-free and runs on the local CPU / filesystem.
ADAPTER_META: Dict[str, Dict[str, Any]] = {
    "local_file_digest": {
        "request_boundary": "local_filesystem_read",
        "model": None,
        "version": "r1.local-pure.1",
        "device": "cpu",
    },
}


def get_adapter(name: str) -> Callable[..., Any]:
    """Return an allowlisted adapter callable or raise ``AdapterNotAllowed``."""
    if name not in ALLOWLIST:
        raise AdapterNotAllowed(
            f"adapter {name!r} is not allowlisted for R1; "
            f"allowed: {sorted(ALLOWLIST)}"
        )
    return ALLOWLIST[name]


def adapter_meta(name: str) -> Dict[str, Any]:
    """Return static provenance metadata for an allowlisted adapter."""
    if name not in ALLOWLIST:
        raise AdapterNotAllowed(
            f"adapter {name!r} is not allowlisted for R1; "
            f"allowed: {sorted(ALLOWLIST)}"
        )
    return dict(ADAPTER_META.get(name, {}))
