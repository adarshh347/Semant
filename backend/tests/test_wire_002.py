"""
CIRCUIT-001 WIRE-002 — the remaining actuators, and a residency path that cannot leak.

Fake/stub-driven: no GPU, no network, no database. Every model service is monkeypatched, so this
runs unattended in CI.

Part A proves the four new runners exist, are shaped like the protocol, and — the crux — that
WORKING MEMORY EVOLVES ACROSS A FULL CHAIN, so a later step is fed by an earlier one rather than
merely being scheduled after it.

Part B proves the release path is exhaustive BY CONSTRUCTION, and that no model-holding service
can be omitted from it.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.services.director import real_actuators as ra
from backend.services.director.capabilities import ACTUATORS, Resource, known
from backend.services.director.execution import EMPTY, OK, SKIPPED, UNAVAILABLE, execute
from backend.services.director.memory import build_memory
from backend.services.director.plan import Step, resolve


def mem(**kw):
    return build_memory(image_ref="img_1", post_id="post_1", **kw)


def steps(*specs):
    return [Step(actuator=a, params=p, id=f"s{i}:{a}") for i, (a, p) in enumerate(specs)]


# ── Part A: every actuator has a runner ──────────────────────────────────────

class TestEveryActuatorIsWired:

    def test_no_actuator_is_left_without_an_in_process_runner(self):
        """WIRE-001 left four unwired; the Director could plan them and never run them."""
        assert sorted(set(known()) - set(ra._DISPATCH)) == []

    @pytest.mark.parametrize("name", ["semantic_read", "find_similar",
                                      "connect_marks", "compose_percept"])
    def test_the_four_newly_wired_have_handlers(self, name):
        assert name in ra._DISPATCH
        assert asyncio.iscoroutinefunction(ra._DISPATCH[name])

    @pytest.mark.parametrize("name", ["semantic_read", "find_similar",
                                      "connect_marks", "compose_percept"])
    def test_each_runner_has_the_ActuatorRunner_shape(self, name):
        ctx = ra.ExecutionContext(post_id="p", post={})
        try:
            runner = ra.RealActuatorRunner(name, ctx)
            assert callable(runner)
            assert runner.actuator is not None
        finally:
            ctx.close()

    def test_a_runner_that_raises_is_a_failed_step_not_a_crash(self, monkeypatch):
        ctx = ra.ExecutionContext(post_id="p", post={})
        try:
            async def boom(*a, **k):
                raise RuntimeError("provider exploded")
            monkeypatch.setitem(ra._DISPATCH, "rhythm", boom)
            monkeypatch.setattr(ra, "_capability_available", lambda c: True)
            res = ra.RealActuatorRunner("rhythm", ctx)(Step(actuator="rhythm", id="s"), mem())
            assert res.status == "error"
            assert "RuntimeError" in res.detail
        finally:
            ctx.close()


class TestRunnerRefusals:

    def test_connect_marks_refuses_when_the_marks_did_not_actually_arrive(self):
        """resolve() proved two marks WOULD exist; this proves two marks DO exist. They differ
        exactly when an upstream step returned empty, which is the case worth catching."""
        ctx = ra.ExecutionContext(post_id="p", post={})
        try:
            ctx.suggestions = [{"type": "region_mask", "label": "only one"}]
            res = asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
                ra._run_connect_marks(Step(actuator="connect_marks", id="s"), mem(), ctx,
                                      ACTUATORS["connect_marks"]))
            assert res.status == EMPTY
            assert "needs 2 marks" in res.detail
        finally:
            ctx.close()

    def test_compose_percept_refuses_with_nothing_gathered(self):
        ctx = ra.ExecutionContext(post_id="p", post={})
        try:
            res = ctx.loop.run_until_complete(
                ra._run_compose_percept(Step(actuator="compose_percept", id="s"), mem(), ctx,
                                        ACTUATORS["compose_percept"]))
            assert res.status == EMPTY
        finally:
            ctx.close()

    def test_readings_do_not_count_as_marks_for_connect(self):
        """A presence_reading is a sentence, not evidence — P8-D's rule, held at the chain."""
        ctx = ra.ExecutionContext(post_id="p", post={})
        try:
            ctx.suggestions = [{"type": "presence_reading"}, {"type": "count_reading"}]
            assert ra._quarantined_marks(ctx) == []
        finally:
            ctx.close()


# ── Part A: the crux — memory evolution across a FULL chain ──────────────────

class FakeRunner:
    """A stand-in that produces what the capability map says, in the quantity given."""

    def __init__(self, name, count=1, status=OK):
        self.name, self.count, self.status = name, count, status
        self.calls = []
        self.saw = []

    def __call__(self, step, memory):
        from backend.services.director.execution import ActuatorResult
        self.calls.append(step)
        self.saw.append(memory.available())
        act = ACTUATORS[self.name]
        if self.status != OK:
            return ActuatorResult(status=self.status, produced=(), adapter=self.name)
        produced = tuple(r for r in act.produces for _ in range(self.count))
        return ActuatorResult(status=OK, produced=produced, confidence=0.8,
                              model=f"fake::{self.name}", adapter=self.name)


def registry(**counts):
    reg = {n: FakeRunner(n, counts.get(n, 1)) for n in known()}
    return reg


class TestRichChainOne:
    """(1) hold two interpretations against each other:
    find_parts → compose_percept ×2 → connect_marks."""

    SPEC = (("find_parts", {}), ("compose_percept", {"draft_text": ""}),
            ("compose_percept", {"draft_text": ""}),
            ("connect_marks", {"relation_role": "contrast"}))

    def test_the_chain_resolves_whole(self):
        plan = resolve(steps(*self.SPEC), mem(), intention="two interpretations")
        assert [s.actuator for s in plan.steps] == \
               ["find_parts", "compose_percept", "compose_percept", "connect_marks"]
        assert plan.complete is True

    def test_it_executes_end_to_end_because_earlier_steps_feed_later_ones(self):
        plan = resolve(steps(*self.SPEC), mem(), intention="two interpretations")
        reg = registry(find_parts=3)
        result = execute(plan, mem(), reg)
        assert [r.status for r in result.provenance.lineage] == [OK, OK, OK, OK]
        assert result.complete is True

    def test_each_step_SAW_what_the_one_before_produced(self):
        """The proof that matters. Not 'it ran fourth' — 'it ran on three marks that did not
        exist when the plan was written'."""
        plan = resolve(steps(*self.SPEC), mem(), intention="two interpretations")
        reg = registry(find_parts=3)
        execute(plan, mem(), reg)
        assert reg["find_parts"].saw[0][Resource.MARK] == 0          # started with nothing
        assert reg["compose_percept"].saw[0][Resource.MARK] == 3      # fed by find_parts
        assert reg["compose_percept"].saw[0][Resource.REGION] == 3
        assert reg["connect_marks"].saw[0][Resource.MARK] == 3        # still there, ≥2 required
        assert reg["compose_percept"].saw[1][Resource.PERCEPT] == 1   # saw the first percept

    def test_the_whole_chain_lands_in_the_final_memory(self):
        plan = resolve(steps(*self.SPEC), mem(), intention="two interpretations")
        result = execute(plan, mem(), registry(find_parts=3))
        counts = result.memory.available()
        assert counts[Resource.REGION] == 3
        assert counts[Resource.PERCEPT] == 2
        assert counts[Resource.GROUND] == 1          # connect_marks produced the relation

    def test_a_finder_that_finds_ONE_makes_connect_marks_skip_honestly(self):
        """The plural projection is optimistic on purpose; reality is still checked at dispatch."""
        plan = resolve(steps(*self.SPEC), mem(), intention="two interpretations")
        reg = registry(find_parts=1)
        result = execute(plan, mem(), reg)
        by = {r.actuator: r for r in result.provenance.lineage}
        assert by["connect_marks"].status == SKIPPED
        assert "2× mark" in by["connect_marks"].detail
        assert reg["connect_marks"].calls == []       # never even attempted
        assert result.complete is False


class TestRichChainTwo:
    """(2) find the motif and its echoes: find_parts → find_similar → connect_marks."""

    SPEC = (("find_parts", {}), ("find_similar", {}),
            ("connect_marks", {"relation_role": "motif_echo"}))

    def test_the_chain_resolves_whole(self):
        plan = resolve(steps(*self.SPEC), mem(), intention="motif and echoes")
        assert [s.actuator for s in plan.steps] == ["find_parts", "find_similar", "connect_marks"]
        assert plan.complete is True

    def test_find_similar_is_seeded_by_find_parts_and_feeds_connect_marks(self):
        plan = resolve(steps(*self.SPEC), mem(), intention="motif and echoes")
        reg = registry(find_parts=2, find_similar=4)
        result = execute(plan, mem(), reg)
        assert [r.status for r in result.provenance.lineage] == [OK, OK, OK]
        assert reg["find_similar"].saw[0][Resource.MARK] == 2         # the seed existed
        assert reg["connect_marks"].saw[0][Resource.MARK] == 6        # 2 found + 4 neighbours
        assert result.complete is True

    def test_a_bare_image_with_no_finder_still_refuses_connect_marks(self):
        plan = resolve(steps(("connect_marks", {"relation_role": "x"})), mem())
        assert plan.steps == ()
        assert "2× mark" in plan.refused[0].detail

    def test_an_unavailable_finder_skips_the_whole_rest_of_the_chain(self):
        plan = resolve(steps(*self.SPEC), mem(), intention="motif and echoes")
        reg = registry()
        reg["find_parts"] = FakeRunner("find_parts", status=UNAVAILABLE)
        result = execute(plan, mem(), reg)
        assert [r.status for r in result.provenance.lineage] == [UNAVAILABLE, SKIPPED, SKIPPED]
        assert reg["find_similar"].calls == []
        assert reg["connect_marks"].calls == []

    def test_chain_provenance_spans_every_real_step(self):
        plan = resolve(steps(*self.SPEC), mem(), intention="motif and echoes")
        result = execute(plan, mem(), registry(find_parts=2), chain_id="ch_wire2")
        d = result.provenance.to_dict()
        assert d["chain_id"] == "ch_wire2"
        assert len(d["lineage"]) == 3
        assert all(link["model"] for link in d["lineage"])
        assert d["weakest_link"] == pytest.approx(0.8)


class TestPluralProjection:

    def test_finders_are_plural_and_field_producers_are_not(self):
        for n in ("find_parts", "grounded_sam_find_parts", "find_similar"):
            assert ACTUATORS[n].plural is True, n
        for n in ("rhythm", "light_field", "compose_percept"):
            assert ACTUATORS[n].plural is False, n

    def test_a_plural_producer_projects_two_of_each(self):
        assert ACTUATORS["find_parts"].projected_produces().count(Resource.MARK) == 2
        assert ACTUATORS["rhythm"].projected_produces() == ACTUATORS["rhythm"].produces

    def test_find_parts_declares_the_marks_it_actually_mints(self):
        """It always minted a region_mask per region; declaring only REGION made every
        find-then-reason chain unresolvable."""
        assert Resource.MARK in ACTUATORS["find_parts"].produces
        assert Resource.REGION in ACTUATORS["find_parts"].produces


# ── Part B: residency that cannot leak ───────────────────────────────────────

class TestExhaustiveUnload:

    def test_discovery_finds_every_service_that_holds_a_model(self):
        from backend.services import model_residency as mr
        found = mr.discover_all()
        # the four that leaked historically, plus the two that were leaking when this gate opened
        for expected in ("dinov2_service", "depth_service", "intrinsic_service",
                         "clip_presence_service", "sam2_auto_service", "perspective_service"):
            assert expected in found, f"{expected} holds a model and must be discoverable"

    def test_NO_model_holding_service_can_be_omitted(self):
        """The no-omission assertion. Every service exposing `unload()` must be reachable by the
        release path — so a newly-wired GPU producer is freed without anyone remembering to add it.

        This is the test that makes a fifth leak impossible: it fails the moment a service holds a
        model the release path cannot see."""
        import importlib
        from backend.services import model_residency as mr
        for name in mr.discover_all():
            importlib.import_module(f"backend.services.{name}")   # as a real run would have
        reachable = {mod.__name__.split(".")[-1] for _tag, mod in mr.imported_releasables()}
        missing = set(mr.discover_all()) - reachable
        assert missing == set(), f"unreleasable model services: {sorted(missing)}"

    def test_a_service_that_HOLDS_a_model_must_expose_unload(self):
        """The structural assertion — the one that actually ends the leak.

        The no-omission test above only covers services that ADVERTISE `unload()`. That is not
        enough: four services (segmentation_service — which `find_parts` calls on every plan —
        plus the architecture, fashion-parse and fashion-clip services) each held a module-level
        `_model` and advertised nothing, so discovery could not see them and 32 MiB survived a
        full `release_all()`. Measured, not theorised.

        So: holding a model is what obliges you to expose a release, and this test enforces it by
        inspecting for the holding rather than trusting the advertisement. A new service that
        caches a model and forgets `unload()` fails here, which is the only place it can fail
        before it fails as a leak."""
        import importlib
        import pkgutil
        import backend.services as services_pkg
        offenders = []
        for info in pkgutil.iter_modules(services_pkg.__path__):
            if info.ispkg:
                continue
            try:
                mod = importlib.import_module(f"backend.services.{info.name}")
            except Exception:
                continue
            holds = [g for g in vars(mod)
                     if g.startswith("_")
                     and g.lower().lstrip("_").startswith(
                         ("model", "net", "predictor", "yolo", "sam", "pipe"))]
            if holds and not callable(getattr(mod, "unload", None)):
                offenders.append((info.name, sorted(holds)[:3]))
        assert offenders == [], (
            "these services cache a model but expose no unload(), so nothing can free them: "
            f"{offenders}")

    def test_the_four_that_were_silently_holding_are_now_releasable(self):
        from backend.services import model_residency as mr
        found = mr.discover_all()
        for name in ("segmentation_service", "architecture_segmentation_service",
                     "fashion_clip_service", "fashion_segmentation_service"):
            assert name in found, f"{name} held a model with no way to release it"

    def test_non_module_model_state_is_covered_too(self):
        """`refine_session` is an OBJECT, not a module — the door P8-B leaked through, and the one
        thing discovery genuinely cannot see."""
        from backend.services import model_residency as mr
        assert "sam21_hiera_tiny" in mr.extra_releaser_tags()

    def test_release_all_frees_the_two_that_were_leaking_when_this_gate_opened(self):
        import importlib
        from backend.services import model_residency as mr
        for n in ("sam2_auto_service", "perspective_service"):
            importlib.import_module(f"backend.services.{n}")
        released = asyncio.run(mr.release_all())
        assert "sam2.1_hiera_tiny" in released      # SEG-FIX's auto proposer, used by find_parts
        assert "geocalib_pinhole" in released       # TRACE-002's deferred adapter

    def test_release_is_idempotent(self):
        from backend.services import model_residency as mr
        asyncio.run(mr.release_all())
        asyncio.run(mr.release_all())               # must not raise

    def test_one_failing_service_cannot_strand_the_others(self, monkeypatch):
        from backend.services import model_residency as mr
        from backend.services import dinov2_service
        def boom():
            raise RuntimeError("stuck")
        monkeypatch.setattr(dinov2_service, "unload", boom)
        released = asyncio.run(mr.release_all())
        assert "dinov2_vits14" not in released
        assert len(released) >= 1                   # the rest still went

    def test_the_hand_maintained_list_is_gone_from_both_paths(self):
        """The list itself was the defect; a test that only checked its CONTENTS would pass
        happily the next time someone forgot to append to it."""
        import inspect
        from backend.routers import posts
        assert not hasattr(ra, "_GPU_UNLOAD_MODULES")
        src = inspect.getsource(posts.produce_field_unload)
        assert "model_residency" in src
        assert "dinov2_service" not in src          # no roster left to fall behind

    def test_both_release_paths_are_the_same_path(self):
        import inspect
        assert "model_residency" in inspect.getsource(ra.unload_models)
