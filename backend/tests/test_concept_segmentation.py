"""
CONCEPT-SEG-001 (SF-004) — SAM 3 as the first new organ-role.

The claim under test is narrow and it is the whole point: **one SAM 3 result is two claims of
different kinds**, and the system now emits both instead of collapsing them.

    the MASK  is `measured`      — computed off the image signal
    the LABEL is `interpretive`  — it was handed to the model in the prompt

SF-004-R2 §4.3 is why this is not pedantry. On a painting, `shoulder fabric` at confidence
0.27–0.43 returned a clean, well-formed mask — of the BACKGROUND. The geometry was right and the
words were wrong. Under one status a reviewer must take both or bin both, and it is neither.

Sections:
  §1  the two statuses, emitted distinctly, through the wall
  §2  the confidence floor gates the NAMING and never the geometry
  §3  availability, and the fallback that says which producer ran
  §4  propose-never-commit, provenance, and the positional-identity hazard
  §5  the wiring (roster, role, actuator, residency)
"""
from __future__ import annotations

import pytest

from backend.services import epistemics, role_registry, suggestion_service as ss
from backend.services.epistemics import EpistemicStatus
from backend.services.vision_orchestrator.contracts import Capability


def _rle(n: int = 4):
    """A minimal valid canonical RLE. Content is irrelevant here — what is under test is which
    STATUS travels with it, not the geometry codec (`test_mask_geometry` owns that)."""
    return {"size": [n, n], "counts": [n * n]}


def _result(concept="collar", confs=(0.9,)):
    return {
        "concept": concept,
        "instances": [{"index": i, "mask_rle": _rle(), "confidence": c}
                      for i, c in enumerate(confs)],
        "truncated": False, "latency_ms": 5292.0, "device": "mps", "model": "facebook/sam3",
    }


# ── 1. the two statuses ──────────────────────────────────────────────────────

def test_one_instance_emits_two_descriptors_not_one():
    out = ss.suggestions_from_concept_segments([_result()], run_id="r1")
    assert len(out) == 2
    assert {d["producer"] for d in out} == {"concept_segment", "concept_naming"}


def test_the_mask_is_measured_and_the_label_is_interpretive():
    """The finding, as an assertion. Not 'both are marked somehow' — the specific pair."""
    extent, naming = ss.suggestions_from_concept_segments([_result()], run_id="r1")
    assert extent[epistemics.STATUS_KEY] == EpistemicStatus.MEASURED.value
    assert naming[epistemics.STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value


def test_the_extent_carries_the_geometry_and_the_naming_carries_the_words():
    """They are separable because each holds only its own half. The extent has a real mask and
    NO label; the naming has the label and authors no geometry (`region_ref`, the same mode the
    VLM's own namings use — the law that a reading never mints an extent)."""
    extent, naming = ss.suggestions_from_concept_segments([_result("cuff")], run_id="r1")
    assert extent["geometry"]["kind"] == "raster_mask"
    assert extent["geometry"]["mask_rle"] == _rle()
    assert extent["label"] == ""

    assert naming["label"] == "cuff"
    assert naming["geometry"]["kind"] == "region_ref"
    assert "mask_rle" not in naming["geometry"]


def test_the_naming_references_the_extent_it_names():
    """So review can accept one and reject the other and still know which mask was meant."""
    extent, naming = ss.suggestions_from_concept_segments([_result()], run_id="r1")
    assert naming["source_ref"] == extent["source_ref"]


def test_both_descriptors_pass_the_epistemic_wall():
    """The real check. `guard` raises on a claim presenting itself as better-founded than it is,
    so a naming that had leaked out as `measured` would be stopped here rather than in review."""
    out = ss.suggestions_from_concept_segments([_result()], run_id="r1")
    assert epistemics.guard(out) == out


def test_the_naming_may_not_promote_itself_to_measured():
    """The specific crossing this producer makes available for the first time: a label that came
    from a prompt, riding on a mask that really was measured, presenting as the measurement."""
    with pytest.raises(epistemics.EpistemicViolation):
        epistemics.declare("concept_naming", EpistemicStatus.MEASURED)
    assert epistemics.declare("concept_naming", EpistemicStatus.UNCERTAIN) \
        is EpistemicStatus.UNCERTAIN


def test_the_concept_source_is_recorded_without_changing_the_status():
    """Whose interpretation it is changes who is answerable, not what kind of claim it is —
    none of the three sources is the image, so all three are `interpretive`."""
    for source in ("domain_profile", "vlm", "curator"):
        _, naming = ss.suggestions_from_concept_segments(
            [_result()], run_id="r1", concept_source=source)
        assert naming["concept_source"] == source
        assert naming["provenance"]["concept_source"] == source
        assert naming[epistemics.STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value


def test_every_instance_gets_its_own_pair():
    """The headline claim is EXHAUSTIVE segmentation — the spike got eleven serpent heads from
    one prompt — so eleven instances must not collapse into one suggestion."""
    out = ss.suggestions_from_concept_segments(
        [_result("snake hood", confs=(0.92, 0.88, 0.71, 0.55, 0.51))], run_id="r1")
    assert len(out) == 10
    assert sum(1 for d in out if d["producer"] == "concept_segment") == 5


# ── 2. the confidence floor gates the naming, never the geometry ─────────────

def test_a_low_confidence_naming_is_withheld_and_the_measurement_survives():
    """The `shoulder fabric` case. The mask was real; the words were wrong. Dropping the pair
    would discard a good measurement, and keeping the pair would publish a false reading."""
    out = ss.suggestions_from_concept_segments(
        [_result("shoulder fabric", confs=(0.31,))], run_id="r1", naming_floor=0.5)
    assert len(out) == 1
    assert out[0]["producer"] == "concept_segment"
    assert out[0][epistemics.STATUS_KEY] == EpistemicStatus.MEASURED.value


def test_a_withheld_naming_is_recorded_rather_than_silently_dropped():
    out = ss.suggestions_from_concept_segments(
        [_result("shoulder fabric", confs=(0.31,))], run_id="r1", naming_floor=0.5)
    withheld = out[0]["naming_withheld"]
    assert withheld["concept"] == "shoulder fabric"
    assert withheld["confidence"] == 0.31 and withheld["floor"] == 0.5


def test_the_floor_never_fabricates_a_box_when_there_is_no_mask():
    """No mask, no claim. The failure mode being refused is a fallback to the VLM's estimated
    box wearing the measured producer's name."""
    empty = {"concept": "hem", "instances": [{"index": 0, "mask_rle": None, "confidence": 0.9}],
             "model": "facebook/sam3"}
    assert ss.suggestions_from_concept_segments([empty], run_id="r1") == []


def test_no_instances_is_an_answer_and_yields_nothing():
    assert ss.suggestions_from_concept_segments(
        [{"concept": "hem", "instances": []}], run_id="r1") == []
    assert ss.suggestions_from_concept_segments(None, run_id="r1") == []


# ── 3. availability and the honest fallback ──────────────────────────────────

def test_the_service_is_unavailable_without_weights_on_disk(monkeypatch):
    """Availability is the WEIGHTS existing, not the env var being set. A var pointing at a file
    that was never fetched is configuration, not capability — and ~3.2 GiB is not something a
    live route may decide to download."""
    from backend.services import sam3_concept_service as svc
    monkeypatch.delenv(svc.WEIGHTS_ENV, raising=False)
    assert svc.weights_path() is None and svc.is_available() is False
    monkeypatch.setenv(svc.WEIGHTS_ENV, "/nonexistent/sam3.pt")
    assert svc.weights_path() is None and svc.is_available() is False


def test_the_capability_probe_reports_down_when_the_organ_is_absent(monkeypatch):
    from backend.services.director import real_actuators as ra
    from backend.services import sam3_concept_service as svc
    monkeypatch.delenv(svc.WEIGHTS_ENV, raising=False)
    assert ra._capability_available("concept_segmenter") is False


def test_the_sukshma_pass_is_off_by_default_and_opt_in(monkeypatch):
    """OFF is the SF-004-R2 verdict, not caution: 5.3 s per concept warm, 63–67 s per image,
    against 3.3–39.6 s for the single VLM call it would sit behind."""
    from backend.routers import posts
    monkeypatch.delenv(posts.SUKSHMA_CONCEPT_SEGMENT_ENV, raising=False)
    assert posts._sukshma_concept_segmentation_enabled() is False
    monkeypatch.setenv(posts.SUKSHMA_CONCEPT_SEGMENT_ENV, "1")
    assert posts._sukshma_concept_segmentation_enabled() is True


@pytest.mark.asyncio
async def test_the_fallback_leaves_the_vlm_parts_intact_and_names_what_ran(monkeypatch):
    """Requested but unavailable. The VLM's parts stand untouched — a degraded answer that says
    so, never a silent substitution and never an empty result."""
    from backend.routers import posts
    from backend.services import sam3_concept_service as svc
    monkeypatch.delenv(svc.WEIGHTS_ENV, raising=False)
    parts = [{"id": "fine_0", "label": "collar", "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}]
    out, detail = await posts._measure_fine_parts_with_sam3(parts, b"")
    assert out == parts
    assert detail["ran"] is False and detail["reason"] == "weights_absent"


@pytest.mark.asyncio
async def test_the_measuring_pass_attaches_real_masks_to_the_vlm_parts(monkeypatch):
    """The proposed architecture: the VLM names what is in THIS picture, SAM 3 measures where.
    A fixed vocabulary scored 6/18 in the spike's first Gate-2 run; the VLM's own labels 27/35."""
    from backend.routers import posts
    from backend.services import sam3_concept_service as svc

    monkeypatch.setattr(svc, "is_available", lambda: True)
    monkeypatch.setattr(svc, "segment_concepts",
                        lambda img, concepts, **kw: [_result(c) for c in concepts])
    parts = [{"id": "fine_0", "label": "collar", "box": {}},
             {"id": "fine_1", "label": "cuff", "box": {}}]
    out, detail = await posts._measure_fine_parts_with_sam3(parts, b"")
    assert detail["ran"] is True and detail["measured"] == 2
    assert all(p["mask_rle"] == _rle() and p["detector"] == "sam3" for p in out)


@pytest.mark.asyncio
async def test_an_unmeasured_part_keeps_its_estimate_and_is_not_dropped(monkeypatch):
    """27/35, not 35/35. The eight SAM 3 could not measure must still reach the curator as what
    they are — estimates — rather than vanishing because a better organ existed."""
    from backend.routers import posts
    from backend.services import sam3_concept_service as svc

    monkeypatch.setattr(svc, "is_available", lambda: True)
    monkeypatch.setattr(svc, "segment_concepts", lambda img, concepts, **kw: [
        _result("collar"), {"concept": "cuff", "instances": [], "model": "facebook/sam3"}])
    parts = [{"id": "fine_0", "label": "collar", "box": {"x": 0.1}},
             {"id": "fine_1", "label": "cuff", "box": {"x": 0.5}}]
    out, detail = await posts._measure_fine_parts_with_sam3(parts, b"")
    assert detail["measured"] == 1
    assert out[1]["box"] == {"x": 0.5}
    assert "mask_rle" not in out[1] and out[1].get("detector") != "sam3"


@pytest.mark.asyncio
async def test_an_organ_that_raises_degrades_the_pass_and_never_fails_the_route(monkeypatch):
    from backend.routers import posts
    from backend.services import sam3_concept_service as svc

    def _boom(*a, **k):
        raise RuntimeError("mps out of memory")

    monkeypatch.setattr(svc, "is_available", lambda: True)
    monkeypatch.setattr(svc, "segment_concepts", _boom)
    parts = [{"id": "fine_0", "label": "collar", "box": {}}]
    out, detail = await posts._measure_fine_parts_with_sam3(parts, b"")
    assert out == parts and detail["ran"] is False
    assert "mps out of memory" in detail["reason"]


# ── 4. propose-never-commit, provenance, positional identity ─────────────────

def test_nothing_here_writes_a_post():
    """Every descriptor is a quarantined suggestion. There is no post id in them, no accept path
    is reachable from this module, and the geometry rides in the suggestion — never on a region."""
    out = ss.suggestions_from_concept_segments([_result()], run_id="r1")
    for d in out:
        assert "post_id" not in d and "region_annotations" not in d
        assert d["linked_ground_ids"] == []


def test_provenance_carries_the_run_and_the_step():
    """PROV-001. SAM 3's instance ids are POSITIONAL (`fine_N`) — the HW-C6 substitution hazard —
    so identity across re-runs comes from run/step, never from the index."""
    out = ss.suggestions_from_concept_segments([_result()], run_id="r7", step_id="s3")
    for d in out:
        assert d["provenance"]["run_id"] == "r7"
        assert d["provenance"]["step_id"] == "s3"
        assert d["provenance"]["adapter"] == "sam3"
        assert d["provenance"]["model"] == "facebook/sam3"


def test_the_source_ref_is_scoped_to_the_concept_and_labelled_positional():
    """It is `concept|index`, not a bare `fine_N`. Two concepts on one image cannot collide, and
    nothing downstream can mistake the index for a durable identity."""
    out = ss.suggestions_from_concept_segments(
        [_result("collar", confs=(0.9, 0.8)), _result("cuff", confs=(0.9,))], run_id="r1")
    refs = {d["source_ref"] for d in out}
    assert refs == {"collar|0", "collar|1", "cuff|0"}


# ── 5. the wiring ────────────────────────────────────────────────────────────

def test_the_capability_and_roster_entry_exist():
    from backend.services.vision_orchestrator.registry import default_roster
    spec = {s.name: s for s in default_roster()}["sam3"]
    assert spec.capability is Capability.CONCEPT_SEGMENT
    assert spec.model_id == "facebook/sam3"
    # Deferred until weights are on disk, which is what makes a Render deploy degrade honestly.
    assert spec.deferred is True and spec.available is False


def test_the_organ_role_ceiling_covers_only_the_half_it_earned():
    """`measured`, not `visible`. A segmenter's extent is something you can point at; this organ
    was HANDED the words and computed where they land, so the words are not its claim to make."""
    assert role_registry.ceiling_for("sam3") is EpistemicStatus.MEASURED
    assert role_registry.ceiling_for_producer("concept_segment") is EpistemicStatus.MEASURED
    # And the naming is deliberately NOT the organ's — it has no single role, because the concept
    # may come from the dissector, a domain profile, or the curator.
    assert role_registry.ceiling_for_producer("concept_naming") is None
    assert epistemics.default_status_for("concept_naming") is EpistemicStatus.INTERPRETIVE


def test_the_actuator_refuses_without_a_concept():
    """An open-vocabulary finder with nothing to look for is the P8-B fabrication shape — and
    this model will mask SOMETHING for very nearly any phrase."""
    from backend.services.director import capabilities as caps
    from backend.services.director.capabilities import Resource

    act = caps.get("concept_segment")
    assert act is not None
    assert Resource.PHRASE in {r.kind for r in act.requires}
    assert act.authors_geometry is True and act.plural is True
    assert act.capability == "concept_segmenter"


@pytest.mark.asyncio
async def test_the_runner_refuses_an_empty_phrase_before_touching_the_model():
    from backend.services.director import real_actuators as ra
    from backend.services.director.capabilities import get as get_actuator
    from backend.services.director.execution import EMPTY
    from backend.services.director.plan import Step

    step = Step(id="s1", actuator="concept_segment", params={"phrase": "  "})
    res = await ra._run_concept_segment(step, None, None, get_actuator("concept_segment"))
    assert res.status == EMPTY and "needs a concept" in res.detail


def test_the_organ_is_discoverable_by_the_residency_release_path():
    """`model_residency` finds anything in `backend.services` with a module-level `unload()`.
    That module exists because a hand-maintained release list was wrong four times running, so
    the new GPU organ has to be found by discovery, not by being remembered."""
    from backend.services import model_residency, sam3_concept_service  # noqa: F401
    assert callable(getattr(sam3_concept_service, "unload", None))
    tags = {tag for tag, _ in model_residency.imported_releasables()}
    assert "sam3" in tags


def test_the_adapter_implements_the_orchestrator_protocol():
    from backend.services.vision_orchestrator.adapters import Sam3ConceptAdapter
    ad = Sam3ConceptAdapter()
    assert ad.spec.capability is Capability.CONCEPT_SEGMENT
    for method in ("is_available", "load", "unload", "infer"):
        assert callable(getattr(ad, method))


@pytest.mark.asyncio
async def test_the_adapter_refuses_a_job_with_no_concept():
    from backend.services.vision_orchestrator.adapters import Sam3ConceptAdapter
    from backend.services.vision_orchestrator.contracts import CancelToken, JobStatus

    res = await Sam3ConceptAdapter().infer({"image": b""}, CancelToken())
    assert res.status is JobStatus.FAILED
    assert "no concept" in (res.provenance.error or "")


# ── 6. the guarded real run ──────────────────────────────────────────────────
# SKIPPED unless the weights are actually present. It is not a CI test — 3.2 GiB and ~14 s of
# cold start — but it is the only thing that proves the fakes above are shaped like the model.
#
# It already earned its place. The first real run failed with
# `TypeError: Unsupported image type`: every production caller holds BYTES
# (`_fetch_post_image_cached` returns the fetched image and never writes a file) and Ultralytics
# accepts str/Path/PIL/ndarray but not bytes. The spike could not have caught it — it fed file
# paths. `_to_source` is the fix, and this test is what would notice it coming back.

_FIXTURE = ("/Users/merleauponty/projects/semant/vault/Build/Architecture Lab/"
            "Vision pipeline/vision-eval-001/fixtures/source/f_product_695be7fa.jpg")


def _weights_present() -> bool:
    from backend.services import sam3_concept_service as svc
    import os
    return svc.weights_path() is not None and os.path.exists(_FIXTURE)


@pytest.mark.skipif(not _weights_present(),
                    reason="SAM 3 weights (or the local fixture) not present — see SF-004-R2")
def test_guarded_real_run_emits_two_statuses_over_real_geometry():
    """A real image, a real concept, real masks — and the pair of claims per instance.

    Measured 2026-08-02 on an Apple M4 (MPS): `snake hood` on the line engraving returned
    ELEVEN instances at 0.92 → 0.255, the same eleven serpent heads the spike found, each with
    its own RLE at 680×445. Five cleared the 0.50 naming floor, so 11 extents + 5 namings = 16
    descriptors, and `epistemics.guard` passed all of them.

    Local file only. No post is read or written, no database is touched.
    """
    from backend.services import sam3_concept_service as svc

    image = open(_FIXTURE, "rb").read()            # raw bytes — what the route actually holds
    result = svc.segment_concept(image, "snake hood")
    try:
        instances = result["instances"]
        assert instances, "the engraving really does contain serpent heads"
        for inst in instances:
            rle = inst["mask_rle"]
            assert rle["size"][0] > 0 and rle["size"][1] > 0
            assert sum(rle["counts"]) == rle["size"][0] * rle["size"][1]

        sug = ss.suggestions_from_concept_segments(
            [result], run_id="guarded", step_id="s1", concept_source="curator",
            naming_floor=svc.NAMING_CONFIDENCE_FLOOR)
        epistemics.guard(sug)                       # raises on any laundered claim

        extents = [d for d in sug if d["producer"] == "concept_segment"]
        namings = [d for d in sug if d["producer"] == "concept_naming"]
        assert len(extents) == len(instances)       # every measurement survives...
        assert len(namings) <= len(extents)         # ...and only confident namings are proposed
        assert all(d[epistemics.STATUS_KEY] == "measured" for d in extents)
        assert all(d[epistemics.STATUS_KEY] == "interpretive" for d in namings)
        assert all(d["provenance"]["run_id"] == "guarded" for d in sug)
    finally:
        svc.unload()
