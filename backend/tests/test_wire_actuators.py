"""
CIRCUIT-001 WIRE-001 — real ActuatorRunners.

These run WITHOUT a GPU: the model boundary is faked (services report available, the produce-field
handler is a fake), so what's under test is the WIRING — the runner shape, the availability probe,
and the crux: a real two-step chain (find_parts → material_field) where step 1's REAL region feeds
step 2, because memory evolved and the shared context carried the region data. Data safety is
pinned here too (the post dict is never mutated).
"""
from __future__ import annotations

import pytest

from backend.services.director import real_actuators as ra
from backend.services.director.capabilities import Resource, known
from backend.services.director.execution import OK, EMPTY, UNAVAILABLE, execute
from backend.services.director.memory import build_memory
from backend.services.director.plan import Step, resolve


def _mem(**kw):
    return build_memory(image_ref="img_1", post_id="post_1", **kw)


def _region(i):
    return {"id": f"seg_{i}", "box": {"x": 0.1 + 0.1 * i, "y": 0.1, "w": 0.3, "h": 0.3},
            "geometry_rev": 0, "mask_rle": None}


@pytest.fixture
def faked(monkeypatch):
    """Fake the model boundary: segmentation + dinov2 report available, the image fetch returns
    bytes, and material_field's produce-field handler records the region it was handed."""
    import backend.services.segmentation_service as seg
    import backend.services.dinov2_service as dsvc
    import backend.routers.posts as posts

    monkeypatch.setattr(seg, "is_available", lambda: True)
    monkeypatch.setattr(seg, "segment_image_bytes", lambda data, **k: [_region(0), _region(1)])
    monkeypatch.setattr(dsvc, "is_available", lambda: True)

    async def _fake_fetch(post_id, post):
        return b"\x89PNG-fake-bytes"
    monkeypatch.setattr(posts, "_fetch_post_image_cached", _fake_fetch)

    seen = {"material_region": None, "calls": []}

    async def _fake_material(post_id, post, region, req, run_id):
        seen["material_region"] = region
        seen["calls"].append(req.producer)
        # M5: stamped like a real producer. The quarantine guard refuses an untagged
        # descriptor on every path now, and a fake that skipped the tag would be standing in
        # for a producer that cannot exist.
        from backend.services import epistemics
        sug = epistemics.stamp(
            {"producer": "material_field", "type": "brush_field", "role": "material_field",
             "geometry": {"kind": "soft_mask", "strokes": [{"points": [[0.5, 0.5]], "radius": 0.05}]},
             "provenance": {"model": "dinov2", "adapter": "dinov2_vits14", "run_id": run_id},
             "confidence": 0.42})
        return [sug], "ready", True
    monkeypatch.setitem(posts._FIELD_PRODUCERS, "material_field", _fake_material)
    return seen


# ── 1. shape ─────────────────────────────────────────────────────────────────

def test_real_registry_covers_every_actuator():
    ctx = ra.ExecutionContext(post_id="p", post={"photo_url": "x"})
    reg = ra.real_registry(ctx)
    assert set(reg) == set(known())
    assert all(isinstance(r, ra.RealActuatorRunner) for r in reg.values())
    ctx.close()


def test_unavailable_capability_yields_unavailable(monkeypatch):
    import backend.services.dinov2_service as dsvc
    monkeypatch.setattr(dsvc, "is_available", lambda: False)
    ctx = ra.ExecutionContext(post_id="p", post={"photo_url": "x"})
    runner = ra.real_registry(ctx)["material_field"]        # capability = dinov2 (down)
    res = runner(Step(actuator="material_field", id="s1"), _mem())
    assert res.status == UNAVAILABLE
    assert res.produced == ()
    ctx.close()


def test_an_actuator_with_no_runner_is_honestly_unavailable():
    """WIRE-002 wired the last four, so no REAL actuator is unwired any more — connect_marks, the
    example this test used to use, now runs. The invariant it protects still matters though: an
    actuator the dispatch table does not know must SAY so rather than pretend, because that is what
    keeps the skip logic honest when a future actuator is declared before it is wired."""
    ctx = ra.ExecutionContext(post_id="p", post={"photo_url": "x"})
    runner = ra.RealActuatorRunner("connect_marks", ctx)
    runner.name = "not_yet_wired"                       # declared, no handler
    res = runner(Step(actuator="not_yet_wired", id="s1"), _mem(mark_ids=("m1", "m2")))
    assert res.status == UNAVAILABLE
    assert "no in-process runner" in res.detail
    ctx.close()


def test_every_real_actuator_now_has_a_runner():
    """The other half of the same fact: WIRE-002 closed the gap the test above used to exercise."""
    from backend.services.director.capabilities import known
    assert sorted(set(known()) - set(ra._DISPATCH)) == []


# ── 2. the memory-evolution chain (the crux) ───────────────────────────────────

def test_find_parts_feeds_material_field(faked):
    """find_parts → material_field, end to end: step 1 produces a REAL region, memory evolves so
    step 2's REGION requirement resolves, and the shared context hands step 2 that real region."""
    plan = resolve([Step(actuator="find_parts", id="s1"),
                    Step(actuator="material_field", id="s2")], _mem(), intention="motif and echoes")
    assert [s.actuator for s in plan.steps] == ["find_parts", "material_field"]   # ordered by need

    ctx = ra.ExecutionContext(post_id="post_1", post={"photo_url": "http://x/y.jpg"})
    result = execute(plan, _mem(), ra.real_registry(ctx))

    # both steps ran OK
    statuses = [(r.actuator, r.status) for r in result.provenance.lineage]
    assert statuses == [("find_parts", OK), ("material_field", OK)]

    # THE PROOF: material_field was handed a region find_parts produced — not None, not a projection
    assert faked["material_region"] is not None
    assert faked["material_region"]["id"] in {"seg_0", "seg_1"}

    # memory evolved: a region then a mark now exist
    counts = result.memory.available()
    assert counts[Resource.REGION] >= 1 and counts[Resource.MARK] >= 1

    # the plan's output is quarantined suggestions (find_parts regions + the material mark)
    assert any(s.get("role") == "material_field" for s in ctx.suggestions)
    assert len(ctx.suggestions) >= 2
    ctx.close()


def test_find_parts_produces_region_resource(faked):
    ctx = ra.ExecutionContext(post_id="post_1", post={"photo_url": "http://x/y.jpg"})
    res = ra.real_registry(ctx)["find_parts"](Step(actuator="find_parts", id="s1"), _mem())
    assert res.status == OK
    # WIRE-002: a found part is ALSO a mark — the runner always minted a region_mask per region,
    # and the capability map now declares it, which is what lets a chain find parts and then
    # reason about them.
    assert res.produced == (Resource.REGION, Resource.REGION,
                            Resource.MARK, Resource.MARK)           # two fake regions
    assert len(ctx.regions) == 2
    ctx.close()


def test_material_field_skips_when_find_parts_found_nothing(faked, monkeypatch):
    """If find_parts is EMPTY, material_field's region never arrives → it SKIPS (never runs on
    stale evidence). Refusal propagation, unchanged by WIRE."""
    import backend.services.segmentation_service as seg
    import backend.services.sam2_auto_service as sam
    monkeypatch.setattr(seg, "segment_image_bytes", lambda data, **k: [])
    monkeypatch.setattr(sam, "is_available", lambda: False)   # no SAM2 rescue either

    plan = resolve([Step(actuator="find_parts", id="s1"),
                    Step(actuator="material_field", id="s2")], _mem())
    ctx = ra.ExecutionContext(post_id="post_1", post={"photo_url": "http://x/y.jpg"})
    result = execute(plan, _mem(), ra.real_registry(ctx))

    by = {r.actuator: r.status for r in result.provenance.lineage}
    assert by["find_parts"] == EMPTY
    assert by["material_field"] == "skipped"
    assert faked["material_region"] is None                  # never ran
    ctx.close()


# ── 3. data safety ─────────────────────────────────────────────────────────────

def test_a_plan_run_never_mutates_the_post(faked):
    """Executing a plan produces suggestions only — the post dict is byte-identical after."""
    import copy
    post = {"photo_url": "http://x/y.jpg", "region_annotations": [], "updated_at": "2026-07-26T00:00:00Z"}
    before = copy.deepcopy(post)

    plan = resolve([Step(actuator="find_parts", id="s1"),
                    Step(actuator="material_field", id="s2")], _mem())
    ctx = ra.ExecutionContext(post_id="post_1", post=post)
    execute(plan, _mem(), ra.real_registry(ctx))

    assert post == before                                    # nothing written back
    assert post["updated_at"] == before["updated_at"]
    ctx.close()
