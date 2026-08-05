"""
One answer to "which device does this model run on".

Eight services used to answer it themselves. Seven of them said, verbatim:

    return "cuda" if torch.cuda.is_available() else "cpu"

...and the eighth (`sam3_concept_service`) was the only one that had ever heard of MPS. That is
the failure mode this module exists for: not that any single copy was wrong, but that the answer
could only ever be *improved in one place at a time*. A box that needs MPS gets concept
segmentation and nothing else — six adapters silently fall to CPU and the surface reports honest,
slow, correct results, which is the hardest kind of wrong to notice.

ORDER: CUDA, then MPS, then CPU. Note that the order is very nearly unobservable — no machine has
both, so cuda-first and mps-first differ only on hardware that does not exist. What matters is
that MPS is *consulted at all*, everywhere, which before this it was not. The order is written
cuda-first because that is what the one implementation that considered both already did, and
because a CUDA box is where this codebase's heavy work actually happens.

`SEMANT_TORCH_DEVICE` overrides everything, unvalidated and on purpose. It is how you prove the
CPU fallback still works on a box that has a card — the L2 sensory gate's `--device cpu` runs
through it — and validating it would mean this module deciding that some future accelerator name
is illegitimate.

Probing is deliberately cheap and re-run per call rather than cached: `torch.cuda.is_available()`
is memoised inside torch, and a cache here would outlive the one case where the answer legitimately
changes — a process that sets the override between calls.
"""
from __future__ import annotations

import os

ENV_OVERRIDE = "SEMANT_TORCH_DEVICE"


def resolve(*, indexed: bool = False) -> str:
    """The device this process should put a model on: ``cuda`` / ``mps`` / ``cpu``.

    `indexed=True` returns ``cuda:0`` instead of ``cuda`` — some libraries (Ultralytics) want an
    explicit ordinal. Never raises: a torch that will not import is a CPU box as far as anything
    calling this is concerned.
    """
    override = os.environ.get(ENV_OVERRIDE, "").strip()
    if override:
        return override
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda:0" if indexed else "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def is_accelerated() -> bool:
    """Is the resolved device something other than the CPU?

    Callers that want to say "this will be slow" in a refusal should ask this rather than
    re-deriving it, which is how the duplication started the first time.
    """
    return not resolve().startswith("cpu")
