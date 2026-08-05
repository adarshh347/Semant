"""
What the test suite needs before it can honestly run — and what it says when it cannot.

THE ONE THING IN HERE. A handful of tests drive a REAL producer: a grounded-SAM segmentation, a
field the loop actually computes once a phrase arrives. Those need the ML stack
(`requirements-ml.txt`: torch, ultralytics, sam2, a git dependency, a CUDA index) — several
gigabytes that turn a one-minute PR gate into a twenty-minute one, for three tests.

So CI installs the light stack and those tests SKIP. The distinction that matters is skip versus
hide: a deselected path in a workflow file is invisible, and a suite that reports "1438 passed"
while silently not running three producer tests is telling a small lie every time it goes green.
A skip is in the summary line, with a reason, where a reader can see the shape of what CI does not
cover.

    @pytest.mark.ml   → runs locally where torch is installed; skipped in CI, out loud.

`torch` is the proxy for the whole stack because everything else in it rides on torch — no test
here needs torchvision without needing torch first.
"""
from __future__ import annotations

import importlib.util

import pytest

#: Is the ML stack importable at all? Checked once, by spec rather than by import, so a suite that
#: does not need torch never pays to load it.
HAS_ML = importlib.util.find_spec("torch") is not None

ML_SKIP_REASON = (
    "needs the ML stack (requirements-ml.txt: torch, ultralytics, sam2). CI installs the light "
    "stack so the gate stays fast; run these locally with the full environment."
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "ml: drives a real producer and needs requirements-ml.txt installed",
    )


def pytest_collection_modifyitems(config, items):
    """Skip the `ml`-marked tests when the stack is absent — never when it is present."""
    if HAS_ML:
        return
    skip = pytest.mark.skip(reason=ML_SKIP_REASON)
    for item in items:
        if "ml" in item.keywords:
            item.add_marker(skip)
