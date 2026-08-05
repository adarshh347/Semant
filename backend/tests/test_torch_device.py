"""
ATLAS L2 — the one device resolver.

What is worth pinning here is not "cuda when cuda" — that is one line and it is obvious. It is the
three properties that made eight hand-written copies a problem in the first place:

    MPS is consulted at all, on every adapter, not just concept segmentation
    a torch that will not import is a CPU box, never a crash
    the override wins, so a CUDA box can prove its own CPU fallback

The tests fake `torch` in `sys.modules` rather than asking the real one, because a test that
asserted "cuda" would pass on the build box and fail in CI, and a test that asserted "cpu" would
do the reverse. What the resolver DECIDES is testable everywhere; what the hardware IS, is not.
"""
import sys
import types
import unittest
from unittest import mock

from backend.services import torch_device


def _fake_torch(*, cuda: bool, mps: bool = False, has_mps_backend: bool = True):
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: cuda)
    backends = types.SimpleNamespace()
    if has_mps_backend:
        backends.mps = types.SimpleNamespace(is_available=lambda: mps)
    torch.backends = backends
    return torch


def _resolve(torch_mod, **kw):
    with mock.patch.dict(sys.modules, {"torch": torch_mod}):
        return torch_device.resolve(**kw)


class TestResolve(unittest.TestCase):
    def setUp(self):
        # The override is process-wide; a leaked value would silently decide every later test.
        self._env = mock.patch.dict("os.environ", {}, clear=False)
        self._env.start()
        import os
        os.environ.pop(torch_device.ENV_OVERRIDE, None)

    def tearDown(self):
        self._env.stop()

    def test_cuda_wins_when_present(self):
        self.assertEqual(_resolve(_fake_torch(cuda=True)), "cuda")

    def test_indexed_gives_an_ordinal_for_ultralytics(self):
        self.assertEqual(_resolve(_fake_torch(cuda=True), indexed=True), "cuda:0")

    def test_mps_is_reached_when_there_is_no_cuda(self):
        """The whole point of centralising: before this, seven adapters could never say 'mps'."""
        self.assertEqual(_resolve(_fake_torch(cuda=False, mps=True)), "mps")

    def test_mps_is_never_indexed(self):
        self.assertEqual(_resolve(_fake_torch(cuda=False, mps=True), indexed=True), "mps")

    def test_cpu_when_neither(self):
        self.assertEqual(_resolve(_fake_torch(cuda=False, mps=False)), "cpu")

    def test_a_torch_without_the_mps_backend_is_not_an_error(self):
        """Older torch has no `backends.mps` at all. `getattr(..., None)`, not a try/except that
        would also swallow a real availability failure."""
        self.assertEqual(_resolve(_fake_torch(cuda=False, has_mps_backend=False)), "cpu")

    def test_a_torch_that_will_not_import_is_a_cpu_box(self):
        # Touching `.cuda` raises — the shape a half-installed or ABI-broken torch actually has.
        # A module subclass, because `types.ModuleType` itself is immutable and cannot carry one.
        class Broken(types.ModuleType):
            @property
            def cuda(self):
                raise OSError("libcuda.so.1: cannot open shared object file")

        self.assertEqual(_resolve(Broken("torch")), "cpu")


class TestOverride(unittest.TestCase):
    def test_the_override_beats_a_present_card(self):
        """How a CUDA box proves its CPU fallback still works — the L2 gate's `--device cpu`."""
        with mock.patch.dict("os.environ", {torch_device.ENV_OVERRIDE: "cpu"}):
            self.assertEqual(_resolve(_fake_torch(cuda=True)), "cpu")

    def test_the_override_is_not_validated(self):
        """Deliberate. This module has no business deciding which accelerator names are real."""
        with mock.patch.dict("os.environ", {torch_device.ENV_OVERRIDE: "xpu:1"}):
            self.assertEqual(_resolve(_fake_torch(cuda=True)), "xpu:1")

    def test_an_empty_override_does_not_count_as_one(self):
        """An unset var and a var set to "" reach here identically from a shell; treating "" as a
        device would resolve to the empty string and fail deep inside `.to()`."""
        with mock.patch.dict("os.environ", {torch_device.ENV_OVERRIDE: "  "}):
            self.assertEqual(_resolve(_fake_torch(cuda=True)), "cuda")


class TestEveryAdapterAsksTheSameQuestion(unittest.TestCase):
    """The regression that matters: an adapter that goes back to deciding for itself.

    Asserted by BEHAVIOUR — each `_device()` is made to answer 'mps' by faking a torch with no
    CUDA — rather than by grepping for the import. A source-text assertion would pass for a module
    that imported `resolve` and then ignored it."""

    ADAPTERS = ("clip_presence_service", "depth_service", "sam2_auto_service",
                "grounding_detector_service", "dinov2_service", "perspective_service",
                "intrinsic_service")

    def test_every_private_device_reaches_mps(self):
        import importlib
        fake = _fake_torch(cuda=False, mps=True)
        for name in self.ADAPTERS:
            mod = importlib.import_module(f"backend.services.{name}")
            with mock.patch.dict(sys.modules, {"torch": fake}):
                self.assertEqual(mod._device(), "mps", f"{name} still decides for itself")

    def test_concept_segmentation_keeps_its_ordinal(self):
        from backend.services import sam3_concept_service as svc
        with mock.patch.dict(sys.modules, {"torch": _fake_torch(cuda=True)}):
            self.assertEqual(svc.device(), "cuda:0")


if __name__ == "__main__":
    unittest.main()
