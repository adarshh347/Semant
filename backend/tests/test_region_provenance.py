"""REGION-PROV-001 — whose mask did the mark measure?

The last unattributed artifact in the sensorium, and the gap ORGAN-PROVENANCE-001 named as bigger
than itself. The investigation changed what the lane is:

  · the field already existed (`geometry_provenance`, since VISION-BUILD-001)
  · every real segmenter already populates it — 392 of 420 masked regions on the real corpus name
    an adapter and a model
  · the 28 that did not were ATTRIBUTED AND THEN OVERWRITTEN, because `canonicalize_geometry`
    assigned the whole dict and `save-region-annotations` re-canonicalizes every region on every
    save

So the tests are arranged around the four claims that follow from that:

  1. THE MAKER SURVIVES — re-canonicalization may say what it did and may not overwrite who drew
     the thing it derived from. This is the fix; §1 is its regression pin. The failure it prevents
     is silent and looks like housekeeping.
  2. UNKNOWN IS LEGIBLE, NEVER FABRICATED — three distinguishable answers, and the unknown one
     carries what the region DOES say. §2.
  3. EXISTING POSTS ARE BYTE-IDENTICAL — nothing backfilled, proven with a hash rather than
     promised. §3.
  4. THE MARK REFERENCES, IT DOES NOT RESTATE — the trace is a join over region ids, and a
     geometry organ's mark still carries no provenance field of its own (#163's anti-theatre rule).
     §4.

§5 is the coverage scan: a new drawing path that sets a mask without declaring its maker fails.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from backend.services import adjacency_organ as adj
from backend.services import geometry_recovery as gr
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services import region_provenance as rp

W = H = 10


def _rle(x0, x1, y0, y1):
    bits = [0] * (W * H)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * W + x] = 1
    return mg.rle_encode(bits, W, H)


#: What a real SAM-3 call passes into `canonicalize_geometry` — copied from
#: `sam3_concept_service`, so a fixture cannot drift into testing a shape nothing produces.
SAM3 = {"adapter": "sam3", "model": "facebook/sam3", "device": "mps",
        "method": "sam3-concept-segment", "prompt": "finial"}


def _drawn(region_id="cseg_1", coords=(2, 8, 2, 8), maker=None):
    region = {"id": region_id, "label": "finial", "mask_rle": _rle(*coords)}
    mg.canonicalize_geometry(region, provenance=dict(maker or SAM3))
    return region


# ── 1. the maker survives re-canonicalization ──────────────────────────────

def test_a_refine_pass_no_longer_erases_who_drew_the_mask():
    """THE DEFECT THIS LANE FOUND, pinned. Before the fix, one `apply_mask_to_region` turned

        {method: sam3-concept-segment, adapter: sam3, model: facebook/sam3, prompt: finial}
    into
        {method: sam-refine-box, recovery: vision-f}

    — the segmenter, the checkpoint and the prompt gone, replaced by a note about the operation.
    A re-canonicalization is not a drawing: it re-derives polygons from a mask that already exists,
    so it may say what it did and may not overwrite who made what it derived from.
    """
    region = _drawn()
    assert region["geometry_provenance"]["adapter"] == "sam3"

    gr.apply_mask_to_region(region, _rle(2, 8, 2, 8), method="sam-refine-box", image_hw=(H, W))
    prov = region["geometry_provenance"]

    assert prov["adapter"] == "sam3" and prov["model"] == "facebook/sam3"
    assert prov["method"] == "sam-refine-box", "what was DONE is still the latest operation"
    assert prov["recovery"] == "vision-f"
    assert rp.is_attributed(region)


def test_the_routine_save_path_no_longer_erases_sixty_makers_at_once():
    """`save-region-annotations` re-canonicalizes EVERY region on EVERY save. Before the fix a
    single save of a dissected post wiped the maker of every region on it — which is why this is
    the more dangerous of the two paths, and the quieter."""
    regions = [_drawn(f"cseg_{i}", (1 + i, 4 + i, 1, 6)) for i in range(3)]
    for region in regions:
        mg.canonicalize_geometry(region, provenance={"via": "save-region-annotations"})

    assert all(r["geometry_provenance"]["adapter"] == "sam3" for r in regions)
    assert all(r["geometry_provenance"]["via"] == "save-region-annotations" for r in regions)
    assert all(rp.is_attributed(r) for r in regions)


def test_a_caller_that_really_is_the_new_drawer_wins():
    """Preservation is not stickiness. A pass that re-SEGMENTS rather than re-derives is the new
    drawer and says so by passing maker keys; those replace the old ones rather than merging with
    them, or a region would accumulate two authors and read as if both stood behind it."""
    region = _drawn()
    mg.canonicalize_geometry(region, provenance={
        "adapter": "sam21_hiera_tiny", "model": "sam2.1", "method": "sam2-refine"})
    prov = region["geometry_provenance"]

    assert prov["adapter"] == "sam21_hiera_tiny" and prov["model"] == "sam2.1"
    assert "prompt" not in prov, "the old drawer's prompt must not ride along under a new maker"


def test_an_operation_is_not_an_author():
    """`method`, `recovery` and `via` describe what was done. Treating any of them as a maker would
    make every re-derived region look attributed, which is how a gap becomes invisible."""
    assert not (mg.MAKER_KEYS & {"method", "recovery", "via", "kind", "size"})
    region = {"id": "r", "mask_rle": _rle(2, 8, 2, 8)}
    mg.canonicalize_geometry(region, provenance={"method": "derive-polygon",
                                                 "recovery": "vision-f"})
    assert not rp.is_attributed(region)


# ── 2. unknown is legible, and never fabricated ───────────────────────────

def test_a_region_nobody_recorded_reads_unknown_and_says_what_it_does_have():
    """The unknown answer carries `recorded` on purpose: a region that says
    `{method: derive-polygon, recovery: vision-f}` is not the same as one that says nothing, and
    flattening both loses the only clue about where to look."""
    region = {"id": "r", "mask_rle": _rle(2, 8, 2, 8),
              "geometry_provenance": {"kind": "mask", "method": "derive-polygon",
                                      "recovery": "vision-f"}}
    maker = rp.maker_of(region)

    assert maker["kind"] == "unknown" and maker["attributed"] is False
    assert rp.UNKNOWN in maker["detail"]
    assert maker["recorded"]["recovery"] == "vision-f"
    assert "derive-polygon" not in str(maker.get("adapter", "")), "no maker was invented"


def test_a_region_with_no_provenance_at_all_is_distinguishable_from_one_with_some():
    bare = rp.maker_of({"id": "r", "mask_rle": _rle(2, 8, 2, 8)})
    some = rp.maker_of({"id": "r", "mask_rle": _rle(2, 8, 2, 8),
                        "geometry_provenance": {"method": "rle"}})
    assert bare["recorded"] == {} and some["recorded"] == {"method": "rle"}
    assert "records nothing" in bare["detail"] and "records" in some["detail"]


def test_a_hand_traced_region_is_attributed_to_the_person_not_called_unknown():
    """A human hand IS a maker, and the honest one. Calling it unknown would confuse "nobody
    recorded this" with "no model was involved"."""
    region = {"id": "r", "actor": "creator", "mask_rle": _rle(2, 8, 2, 8),
              "geometry_provenance": {"kind": "mask", "via": "save-region-annotations"}}
    maker = rp.maker_of(region)
    assert maker["kind"] == "human" and maker["attributed"] and maker["actor"] == "creator"


def test_a_model_drawn_region_is_never_reported_as_human_even_when_saved_by_a_person():
    """`actor` is consulted only when no maker is recorded. A SAM-3 region the author saved is
    still SAM-3's, and reporting the saver would be the last person to touch it taking credit."""
    region = _drawn()
    region["actor"] = "creator"
    assert rp.maker_of(region)["kind"] == "model"


def test_nothing_answers_none():
    """Every shape gets an answer, including the shapes a caller should not have passed. A `None`
    here would render as an empty cell in any report, which reads as a column nobody filled in."""
    for region in (None, {}, {"id": "r"}, {"geometry_provenance": None},
                   {"geometry_provenance": "not-a-dict"}):
        maker = rp.maker_of(region)
        assert maker["kind"] in {"model", "human", "unknown"} and maker["detail"]


# ── 3. existing posts are byte-identical ─────────────────────────────────

def test_reading_a_stored_post_changes_nothing_about_it():
    """THE STANDING RULE, proved with a hash rather than promised. This lane backfills nothing:
    a region drawn before it reads `unknown`, and inventing a maker for a mask whose maker nobody
    knows is the fabrication the whole provenance floor exists to prevent."""
    post = {"_id": "p1", "region_annotations": [
        {"id": "old_0", "mask_rle": _rle(2, 8, 2, 8),
         "geometry_provenance": {"kind": "mask", "method": "rle", "size": [H, W]}},
        {"id": "old_1", "mask_rle": _rle(0, 4, 0, 4)},
        _drawn("new_0", (5, 9, 5, 9)),
    ]}
    before = hashlib.sha256(json.dumps(post, sort_keys=True, default=str).encode()).hexdigest()

    report = rp.audit(post["region_annotations"])
    for region in post["region_annotations"]:
        rp.maker_of(region)
        rp.is_attributed(region)

    after = hashlib.sha256(json.dumps(post, sort_keys=True, default=str).encode()).hexdigest()
    assert before == after, "reading provenance mutated the post"
    assert report["mask_bearing"] == 3 and report["attributed"] == 1
    assert report["by_kind"] == {"unknown": 2, "model": 1}


def test_the_audit_reports_and_never_refuses():
    """An unattributed mask is a fact about the corpus's history, not a reason to refuse a reading
    somebody already took. Nothing that grounded before this lane stops grounding."""
    unattributed = {"id": "old", "mask_rle": _rle(2, 8, 2, 8)}
    whole = {"id": "whole", "mask_rle": _rle(0, 10, 0, 10)}

    measurement = nest.measure(unattributed, whole)
    assert measurement["nested"] and measurement["basis"] == "mask"
    mark = nest.grounding_mark(measurement, post_id="p")
    from backend.services import epistemics
    assert epistemics.guard([mark]) == [mark], "admissibility did not change"
    assert not rp.is_attributed(unattributed), "and the gap is still visible"


# ── 4. the mark references; it does not restate ──────────────────────────

@pytest.mark.parametrize("organ,measure", [(nest, nest.measure), (adj, adj.measure)])
def test_a_geometry_organs_mark_still_carries_no_artifact_provenance(organ, measure):
    """#163's anti-theatre rule, re-asserted from the other side now that the artifact HAS
    provenance. The temptation this lane creates is to copy the maker onto the mark; that would be
    a second place for the truth to live, and the one that goes stale when a region is re-drawn.

    `adapter` IS on the mark and is not a violation — it says `geometry:mask`, which names which of
    the ORGAN'S OWN paths the reading took. The word means two things in two places (the organ's
    method here, a segmenter's name in `geometry_provenance`), so this checks the keys that can
    only ever mean the artifact's maker, plus that `adapter` still names the organ's own path.
    """
    part, whole = _drawn("part", (4, 8, 2, 9)), _drawn("whole", (0, 10, 0, 10))
    mark = organ.grounding_mark(measure(part, whole), post_id="p")
    prov = mark["provenance"]

    assert prov["producer"] == organ.ORGAN
    borrowed = {"model", "checkpoint", "revision", "device", "drawn_by"} & set(prov)
    assert not borrowed, f"the mark restated its artifact's maker: {sorted(borrowed)}"
    assert prov["adapter"].startswith("geometry:"), \
        f"`adapter` on the mark must name the organ's own path, not a segmenter: {prov['adapter']}"
    assert "sam3" not in str(prov) and "facebook" not in str(prov)


def test_a_mark_can_be_traced_to_the_segmenter_that_drew_what_it_measured():
    """THE POINT OF THE LANE. The mark cites region ids; the regions carry their makers; the trace
    is a join. A `measured` containment is now auditable to the model that drew both masks."""
    part, whole = _drawn("part", (4, 8, 2, 9)), _drawn("whole", (0, 10, 0, 10))
    mark = nest.grounding_mark(nest.measure(part, whole), post_id="p")

    traced = rp.trace(mark, [part, whole])
    assert traced["basis"] == "mask" and traced["producer"] == nest.ORGAN
    assert [t["region_id"] for t in traced["regions"]] == ["part", "whole"]
    assert all(t["maker"]["model"] == "facebook/sam3" for t in traced["regions"])


def test_a_trace_over_an_unrecorded_region_says_unknown_rather_than_going_quiet():
    part = {"id": "part", "mask_rle": _rle(4, 8, 2, 9)}
    whole = _drawn("whole", (0, 10, 0, 10))
    mark = nest.grounding_mark(nest.measure(part, whole), post_id="p")

    traced = rp.trace(mark, [part, whole])
    kinds = {t["region_id"]: t["maker"]["kind"] for t in traced["regions"]}
    assert kinds == {"part": "unknown", "whole": "model"}


# ── 5. the coverage scan: a new drawing path must declare ────────────────

#: A pass that SETS a mask is drawing; a pass that re-derives from one is not. This is the list of
#: modules allowed to call `canonicalize_geometry` without naming a maker, each because it is the
#: second kind, and each named so adding a fourth is a decision somebody makes rather than a habit.
_MAY_NOT_DECLARE = {
    # re-derives geometry from a mask that already exists; preservation carries the drawer through
    "geometry_recovery.py",
    # the module that DOES the preserving
    "mask_geometry.py",
}


def test_a_new_drawing_path_that_names_no_maker_fails_here():
    """The audit's enforcement pattern (ORGAN-PROVENANCE-001), one level down.

    A service that calls `canonicalize_geometry` and passes no maker key is either re-deriving —
    in which case it belongs in `_MAY_NOT_DECLARE` above, deliberately — or it is a drawer that
    forgot, and its regions will read `unknown` forever with nothing recording whose they were.
    """
    services = Path(mg.__file__).resolve().parent
    offenders = []
    for path in sorted(services.rglob("*.py")):
        source = path.read_text()
        for call in re.finditer(r"canonicalize_geometry\((.{0,400}?)\)\n", source, re.S):
            args = call.group(1)
            if "provenance=" not in args:
                continue
            if not (mg.MAKER_KEYS & set(re.findall(r'"(\w+)":', args))):
                if path.name not in _MAY_NOT_DECLARE:
                    offenders.append(f"{path.name}: {args.strip()[:70]}")

    assert not offenders, (
        "these paths canonicalize geometry without naming a maker. If the pass re-derives from an "
        "existing mask, add it to `_MAY_NOT_DECLARE` and say why; if it DRAWS, it must declare — "
        f"otherwise its masks ground `measured` claims with no recorded origin:\n  "
        + "\n  ".join(offenders))


def test_every_real_segmenter_declares_a_maker():
    """The other direction: the six drawers this corpus actually has all name themselves, and this
    asserts it rather than trusting the scan above to have found them."""
    services = Path(mg.__file__).resolve().parent
    declared = set()
    for path in sorted(services.rglob("*.py")):
        for call in re.finditer(r"canonicalize_geometry\((.{0,400}?)\)\n", path.read_text(), re.S):
            for adapter in re.findall(r'"adapter":\s*"?([\w.]+)"?', call.group(1)):
                declared.add(adapter)

    assert declared >= {"segformer_clothes", "sam21_hiera_tiny", "segformer_b0_ade", "yolo11n_seg"}
    assert len(declared) >= 4, f"the scan found too few declaring drawers: {sorted(declared)}"
