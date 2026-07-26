"""
CIRCUIT-001 WIRE-002 (Part B) — one exhaustive, self-maintaining release path.

THE LEAK, AND WHY IT KEPT HAPPENING. Residency has been released by HAND-MAINTAINED LISTS, and
the list has been wrong four times:

    P6-I    DINOv2 only — Depth and Intrinsic were resident and unreleased
    P8-B    SAM2's `refine_session` sits outside the adapter registry, so the loop could not see it
    P8-C    CLIP added as a producer, not added to the list
    NOW     `sam2_auto_service` (SEG-FIX) and `perspective_service` (TRACE-002) both expose
            `unload()` and are missing from `real_actuators._GPU_UNLOAD_MODULES`; sam2_auto is
            missing from the router's list too, and `find_parts` calls it on every plan

Every one of those is the same mistake: a model was wired in one place and released in another,
and nothing connected the two. Adding a fifth entry to a list fixes today and guarantees a fifth
leak. The list itself is the defect.

SO THIS DISCOVERS INSTEAD OF REMEMBERING. A service that holds a model exposes `unload()`. That
is the existing convention across all eight of them — it was never written down, but it was
followed. Discovery makes it load-bearing: anything in `backend.services` with a module-level
`unload()` is released, automatically, forever. A newly-wired GPU producer needs no registration
step, which is the only kind of step that cannot be forgotten.

WHY `sys.modules` AND NOT A DIRECTORY SCAN. Release only needs to reach services that could be
holding something, and a module that was never imported cannot hold a model. Walking the already-
imported set is therefore exhaustive for the purpose AND free of side effects — a directory scan
would import every service (pulling torch, opening files) as a side effect of trying to free
memory, which is the wrong direction. `discover_all()` does the full import walk, but it exists
for the no-omission TEST, not for the release path.

Non-module state is registered explicitly, because it cannot be discovered: `refine_session` is a
long-lived OBJECT with an async `unload()`, not a module, and it is exactly the door P8-B leaked
through.
"""
from __future__ import annotations

import importlib
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

SERVICES_PREFIX = "backend.services."

# Non-module model state. An entry here is a thing that holds weights but is NOT a service module
# with `unload()`, so discovery cannot see it. Keep this SHORT — every entry is a manual list of
# the kind this module exists to abolish, and each needs a reason.
_EXTRA_RELEASERS: List[Tuple[str, str, str]] = [
    # (tag, module path, attribute) — the SAM2 session P8-B leaked through. It is an object with
    # an async unload(), living outside the adapter registry, so nothing else can find it.
    ("sam21_hiera_tiny", "backend.services.vision_orchestrator.refine_session", "refine_session"),
]


def _module_tag(mod: Any, name: str) -> str:
    """The model name a service reports, for the release receipt."""
    return (getattr(mod, "MODEL_TAG", None)
            or getattr(mod, "ADAPTER", None)
            or name.replace("_service", ""))


def imported_releasables() -> List[Tuple[str, Any]]:
    """Every ALREADY-IMPORTED service module exposing `unload()`, as (tag, module).

    Imports nothing. A service that was never imported cannot be holding a model, so this is
    exhaustive for release while remaining free of import side effects.
    """
    out: List[Tuple[str, Any]] = []
    # snapshot: releasing can import things, and mutating dict during iteration would raise
    for full_name, mod in list(sys.modules.items()):
        if not full_name.startswith(SERVICES_PREFIX) or mod is None:
            continue
        short = full_name[len(SERVICES_PREFIX):]
        if "." in short:                      # sub-packages (vision_orchestrator.*) handled below
            continue
        if callable(getattr(mod, "unload", None)):
            out.append((_module_tag(mod, short), mod))
    return sorted(out, key=lambda t: t[0])


def discover_all() -> List[str]:
    """Every service module exposing `unload()`, IMPORTING each to find out.

    For the no-omission test, not for release: it deliberately does the expensive, side-effecting
    thing that `imported_releasables()` refuses to do. The test asserts the release path would
    cover everything this finds.
    """
    import pkgutil
    import backend.services as services_pkg
    found: List[str] = []
    for info in pkgutil.iter_modules(services_pkg.__path__):
        if info.ispkg:
            continue
        try:
            mod = importlib.import_module(f"{SERVICES_PREFIX}{info.name}")
        except Exception:
            continue                          # a service that cannot import holds no model
        if callable(getattr(mod, "unload", None)):
            found.append(info.name)
    return sorted(found)


async def release_all(*, empty_cache: bool = True) -> List[str]:
    """Release every model this process could be holding. Idempotent. Returns what it freed.

    Each release is independent: one service raising must not strand the others, which is the
    failure the hand-maintained loops already guarded against and the reason each is wrapped.
    """
    released: List[str] = []

    for tag, mod in imported_releasables():
        try:
            result = mod.unload()
            if hasattr(result, "__await__"):   # a service may declare unload() async
                await result
            released.append(tag)
        except Exception:
            pass

    for tag, module_path, attr in _EXTRA_RELEASERS:
        try:
            obj = getattr(importlib.import_module(module_path), attr)
            result = obj.unload()
            if hasattr(result, "__await__"):
                await result
            released.append(tag)
        except Exception:
            pass

    if empty_cache:
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
    return sorted(set(released))


def extra_releaser_tags() -> List[str]:
    return [tag for tag, _m, _a in _EXTRA_RELEASERS]
