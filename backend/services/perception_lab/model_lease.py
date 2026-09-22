"""Exclusive cross-process lease for learned-model Lab calls on this machine.

fcntl owns the lock. The JSON receipt is advisory and is never used to decide that a
live process may be displaced. Existing servers outside this protocol need coordination.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LEASE_PATH = Path(os.environ.get("SEMANT_MODEL_LEASE_PATH", "/private/tmp/semant-perception-model.lease"))


class ModelLeaseBusy(RuntimeError):
    pass


@contextmanager
def learned_model_lease(*, family: str, timeout: float = 0, path: Path = LEASE_PATH):
    if not family or timeout < 0:
        raise ValueError("family and nonnegative timeout are required")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise ModelLeaseBusy(f"learned-model lease is held: {path}") from exc
                time.sleep(min(.1, max(0, deadline - time.monotonic())))
        receipt = {"pid": os.getpid(), "family": family, "worktree": str(Path.cwd()),
                   "started_at": datetime.now(timezone.utc).isoformat()}
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(json.dumps(receipt, sort_keys=True).encode())
            handle.flush()
            os.fsync(handle.fileno())
            yield receipt
        finally:
            handle.seek(0)
            handle.truncate()
            handle.flush()
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
