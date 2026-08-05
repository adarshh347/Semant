"""
WAVE2 Lane M — the movement kernel.

Proves the one experiment the lane exists for: a relation MEASURED in one image is carried to
another, grounded there by the same instrument, recorded as an edge along a named axis, and then
used to place a third image nobody compared — for measured reasons.

The refusals matter as much as the crossing, so they are pinned individually: a candidate the
retina liked but that stands in no relation is refused as `surface_only`; a candidate that maps
but cannot be measured never becomes a `measured` edge; and a candidate with a perfect similarity
score is not placed unless the organ measured it.

Everything runs on synthetic geometry with a fake retina — no Mongo, no network, no GPU, no model.
The real-corpus run lives in `scripts/movement_kernel_run.py` and its transcript is in the findings
note; what is pinned here is the mechanism.
"""
import asyncio
import copy

import numpy as np
import pytest

from backend.services import mask_geometry as mg
from backend.services import movement_kernel as mk
from backend.services import nestedness_organ as organ
from backend.services import structure_map as sm
from backend.services.epistemics import STATUS_KEY, EpistemicStatus
from backend.services.movement_graph import MOVEMENT_FIELDS, is_movement_edge


# ── fixture geometry ─────────────────────────────────────────────────────────

def _box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def _region(rid, box, label=""):
    return {"id": rid, "box": _box(*box), "label": label or rid}


def _post(pid, regions):
    return {"_id": pid, "region_annotations": list(regions), "visual_marks": []}


#: Image A — a part inside a whole inside a frame. depth 2, one sibling, no descendants.
POST_A = _post("post_a", [
    _region("a_frame", (0.05, 0.05, 0.90, 0.90), "frame"),
    _region("a_whole", (0.20, 0.20, 0.50, 0.50), "spire"),
    _region("a_part", (0.30, 0.30, 0.10, 0.10), "finial"),
    _region("a_sibling", (0.50, 0.50, 0.10, 0.10), "boss"),
])

#: Image B — the same relational skeleton, deliberately different geometry and different sizes.
#: Nothing about B's part resembles A's; that is the point of a structure map.
POST_B = _post("post_b", [
    _region("b_frame", (0.02, 0.02, 0.96, 0.96), "facade"),
    _region("b_whole", (0.55, 0.10, 0.35, 0.60), "minaret"),
    _region("b_part", (0.60, 0.15, 0.08, 0.08), "dome"),
    _region("b_sibling", (0.70, 0.40, 0.09, 0.09), "balcony"),
])

#: Image S — ONE region, contained by nothing. Whatever it looks like, there is no relation here.
POST_S = _post("post_s", [_region("s_only", (0.10, 0.10, 0.80, 0.80), "sky")])

#: Image C — the third image, never compared to anything. Real nesting, its own geometry.
POST_C = _post("post_c", [
    _region("c_whole", (0.10, 0.10, 0.70, 0.70), "crown"),
    _region("c_part", (0.30, 0.30, 0.12, 0.12), "eyebrow"),
    _region("c_sibling", (0.50, 0.30, 0.12, 0.12), "eye"),
])

#: Image D — geometry that MAPS (it has a container) but whose pair the organ measures as not
#: nested: the "part" is nearly as big as its container.
POST_D = _post("post_d", [
    _region("d_whole", (0.10, 0.10, 0.60, 0.60), "block"),
    _region("d_part", (0.11, 0.11, 0.58, 0.58), "almost-the-same-block"),
    _region("d_sibling", (0.12, 0.12, 0.10, 0.10), "speck"),
])

POSTS = {p["_id"]: p for p in (POST_A, POST_B, POST_S, POST_C, POST_D)}


class FakeRetina:
    """A retina that proposes exactly what a test wants — including things it should not get.

    Stands in for the real index so the kernel's gates are exercised on candidates chosen to
    probe them, rather than on whatever DINOv2 happened to put nearby.
    """

    DEFAULT_K = 12
    DEFAULT_ROLE = "identity"

    def __init__(self, candidates):
        self.candidates = list(candidates)
        self.calls = []

    def propose_candidates(self, **kwargs):
        self.calls.append(dict(kwargs))
        exclude = str(kwargs.get("exclude_post_id") or "")
        out = [dict(c) for c in self.candidates if str(c["post_id"]) != exclude]
        return {"status": "ready" if out else "empty", "candidates": out[:int(kwargs.get("k", 12))],
                "grounded": False, "kind": "candidates", "note": "candidates are not relations",
                "space": "test", "reason": ""}


def _cand(post_id, region_id, score):
    return {"post_id": post_id, "region_id": region_id, "score": score,
            "embedding_id": f"emb_{post_id}_{region_id}", "kind": "candidate",
            "role": "identity", "space": "test", "model": "test", "checkpoint": "",
            "route": "", "dim": 8, "geometry_rev": 1}


def _run(**kwargs):
    base = dict(post_a=POST_A, posts=copy.deepcopy(POSTS), persist=False)
    base.update(kwargs)
    return asyncio.run(mk.run_kernel(**base))


# ── the organ: it measures, and it reads no labels ───────────────────────────

def test_the_organ_measures_containment_and_scale():
    m = organ.measure(_region("i", (0.4, 0.4, 0.1, 0.1)), _region("o", (0.2, 0.2, 0.6, 0.6)))
    assert m["containment"] == 1.0
    assert m["scale_ratio"] == pytest.approx(0.01 / 0.36, rel=1e-3)
    assert m["nesting_index"] == pytest.approx(1.0 * (1 - 0.01 / 0.36), rel=1e-3)
    assert m["nested"] is True and m["basis"] == "box"


def test_a_region_is_not_nested_within_itself():
    """`containment` alone would say yes — a thing is entirely inside itself. The scale factor is
    what makes the index 0, and the id check refuses before it gets that far."""
    with pytest.raises(organ.NestednessRefusal, match="itself"):
        organ.measure(_region("x", (0.2, 0.2, 0.3, 0.3)), _region("x", (0.2, 0.2, 0.3, 0.3)))
    same = organ.measure(_region("x", (0.2, 0.2, 0.3, 0.3)), _region("y", (0.2, 0.2, 0.3, 0.3)))
    assert same["nesting_index"] == 0.0 and same["nested"] is False


def test_a_disjoint_pair_is_measured_and_reported_as_not_nested():
    """Measured-and-negative is a result. It is not a refusal, and the two must stay distinct."""
    m = organ.measure(_region("i", (0.85, 0.85, 0.1, 0.1)), _region("o", (0.1, 0.1, 0.3, 0.3)))
    assert m["containment"] == 0.0 and m["nested"] is False and m["nesting_index"] == 0.0


def test_geometry_with_neither_mask_nor_box_is_refused_not_scored():
    with pytest.raises(organ.NestednessRefusal, match="no geometry"):
        organ.measure({"id": "i"}, _region("o", (0.1, 0.1, 0.5, 0.5)))


def _ring_post():
    """A container shaped like a ring, and a part sitting in its hole.

    THE DIAGNOSIS OF THE REAL RUN'S WORST FINDING, as geometry. On the live corpus a temple finial
    measured as nested inside `Sky`, because in a 2D projection a bounding box cannot tell
    'inside' from 'in front of' — and a sky mask has a hole exactly where the temple is. This is
    that case in miniature: the boxes say contained, the masks say not a single shared pixel.
    """
    ring = np.zeros((40, 40), np.uint8)
    ring[5:35, 5:35] = 1
    ring[12:28, 12:28] = 0                       # the hole the part sits in
    part = np.zeros((40, 40), np.uint8)
    part[16:24, 16:24] = 1
    outer = {"id": "ring", "mask_rle": mg.rle_encode_mask(ring),
             "box": _box(5 / 40, 5 / 40, 30 / 40, 30 / 40)}
    inner = {"id": "in_hole", "mask_rle": mg.rle_encode_mask(part),
             "box": _box(16 / 40, 16 / 40, 8 / 40, 8 / 40)}
    return inner, outer


def test_masks_refuse_the_containment_boxes_would_have_granted():
    """The box basis is a systematic over-estimate, and this is what it costs."""
    inner, outer = _ring_post()
    by_mask = organ.measure(inner, outer)
    assert by_mask["basis"] == "mask"
    assert by_mask["containment"] == 0.0 and by_mask["nested"] is False

    boxed = ({k: v for k, v in inner.items() if k != "mask_rle"},
             {k: v for k, v in outer.items() if k != "mask_rle"})
    by_box = organ.measure(*boxed)
    assert by_box["basis"] == "box"
    assert by_box["containment"] == 1.0 and by_box["nested"] is True   # the false positive


def test_mismatched_mask_rasters_fall_back_to_boxes_and_say_so():
    """Resampling one mask onto the other's grid would invent boundary pixels and then measure
    them — the measurement would be of the resampler."""
    inner, outer = _ring_post()
    small = np.zeros((20, 20), np.uint8)
    small[8:12, 8:12] = 1
    inner = {**inner, "mask_rle": mg.rle_encode_mask(small)}
    m = organ.measure(inner, outer)
    assert m["basis"] == "box" and "no shared mask raster" in m["basis_detail"]


def test_the_organs_mark_is_the_only_place_measured_is_written():
    m = organ.measure(_region("i", (0.4, 0.4, 0.1, 0.1)), _region("o", (0.2, 0.2, 0.6, 0.6)))
    mark = organ.measured_mark(m, post_id="post_a", step_id="s1")
    assert mark[STATUS_KEY] == EpistemicStatus.MEASURED.value
    assert mark["provenance"]["producer"] == organ.ORGAN
    assert mark["provenance"]["adapter"] == "geometry:box"
    assert mark["measurement"]["nesting_index"] == m["nesting_index"]


# ── structure mapping: relations, never appearances ──────────────────────────

def _structure(post, region_id):
    regions = post["region_annotations"]
    return sm.relational_structure(regions, region_id,
                                   measurements=organ.find_nested_pairs(regions))


def test_a_relation_maps_across_completely_unalike_geometry():
    """Gentner's point, as a test. A's part and B's part share no size, no position and no shape;
    the mapping holds because `nested_within` holds on both sides."""
    verdict = sm.structure_map(_structure(POST_A, "a_part"), _structure(POST_B, "b_part"))
    assert sm.mapped(verdict)
    roles = {c["role"]: (c["source"], c["target"]) for c in verdict["correspondences"]}
    assert roles["part"] == ("a_part", "b_part")
    assert roles["whole"] == ("a_whole", "b_whole")


def test_a_candidate_with_no_relation_is_refused_as_surface_only():
    """THE REFUSAL THIS LANE EXISTS TO MAKE. `s_only` is contained by nothing, so however much it
    resembles the seed, there is no relation to carry."""
    verdict = sm.structure_map(_structure(POST_A, "a_part"), _structure(POST_S, "s_only"))
    assert verdict["status"] == "refused"
    assert sm.is_surface_only(verdict)
    assert verdict["systematicity"] is None


def test_a_source_with_no_relation_is_refused_on_its_own_terms():
    """Distinct from `surface_only`: the failure is on the NEAR side, and blaming the candidate
    would send someone hunting the wrong image."""
    verdict = sm.structure_map(_structure(POST_S, "s_only"), _structure(POST_B, "b_part"))
    assert verdict["reason"] == sm.REFUSED_NO_SOURCE_RELATION


def test_the_two_ends_of_one_relation_do_not_map_onto_each_other():
    verdict = sm.structure_map(_structure(POST_A, "a_part"), _structure(POST_A, "a_whole"))
    assert verdict["reason"] == sm.REFUSED_INVERTED


def test_systematicity_cannot_see_a_similarity_score():
    """The guarantee is the signature: `systematicity` takes two skeletons and nothing else, so no
    retina score can reach it. Pinned because the temptation to 'just blend in' the similarity is
    exactly how this stops being structure-mapping."""
    import inspect
    params = list(inspect.signature(sm.systematicity).parameters)
    assert params == ["source", "target"]
    score = sm.systematicity(_structure(POST_A, "a_part"), _structure(POST_B, "b_part"))
    assert 0.0 <= score["score"] <= 1.0
    assert set(score["components"]) == {"depth", "siblings", "descendants"}


# ── the kernel, end to end ───────────────────────────────────────────────────

def test_the_kernel_carries_a_measured_relation_from_one_image_to_another():
    t = _run(region_id="a_part",
             retina_module=FakeRetina([_cand("post_b", "b_part", 0.71)]))
    assert t["seed"]["measurement"]["nested"] is True
    assert len(t["movements"]) == 1
    edge = t["movements"][0]["edge"]
    assert is_movement_edge(edge)
    assert edge["axis_ref"] == organ.AXIS_NESTEDNESS
    assert edge["source_node"] == "vm_post_a:a_part"
    assert edge["target_node"] == "vm_post_b:b_part"
    assert edge["spans"] == ["post_a", "post_b"]
    assert 0.0 < float(edge["systematicity"]) <= 1.0


def test_the_seed_mark_and_the_mapped_skeleton_name_the_same_container():
    """A regression on the first real run's bug. The finial scored higher against `Sky` than
    against `Temple Spire`, so the mark cited nesting-in-sky while the structure-mapper aligned
    nesting-in-spire — an edge whose grounding and whose analogy described different relations."""
    t = _run(region_id="a_part", retina_module=FakeRetina([_cand("post_b", "b_part", 0.7)]))
    seeded = t["seed"]
    assert seeded["measurement"]["outer_region_id"] == seeded["structure"]["parent_id"]
    assert seeded["structure"]["parent_id"] == "a_whole"          # the tightest, not the largest


def test_a_surface_only_candidate_produces_no_edge():
    t = _run(region_id="a_part", retina_module=FakeRetina([
        _cand("post_s", "s_only", 0.99),          # the highest score in the run
        _cand("post_b", "b_part", 0.31),
    ]))
    refused = {str(c["candidate"]["post_id"]): c for c in t["refused"]}
    assert refused["post_s"]["reason"] == sm.REFUSED_SURFACE_ONLY
    assert t["surface_only_refusals"]
    # the only edge is the low-scoring one that had structure under it
    assert [e["edge"]["target_node"] for e in t["movements"]] == ["vm_post_b:b_part"]


def test_a_containment_below_the_organs_threshold_grounds_nothing():
    """`d_part` sits inside `d_whole` and fills 93% of it. The organ measures that and calls it
    not nested, so the far skeleton is empty and the candidate never reaches an edge.

    The refusal reads `surface_only`, and that is not a mislabel: from the far image's own
    measurements this region IS contained by nothing that counts. The ORGAN's threshold, not the
    mapper's opinion, is what emptied the skeleton.
    """
    t = _run(region_id="a_part", retina_module=FakeRetina([_cand("post_d", "d_part", 0.95)]))
    assert t["movements"] == []
    (refusal,) = t["refused"]
    assert refusal["reason"] == sm.REFUSED_SURFACE_ONLY
    assert refusal["mark"] is None
    # …and the organ really did measure the pair; it is not that nobody looked.
    direct = organ.measure(_region("d_part", (0.11, 0.11, 0.58, 0.58)),
                           _region("d_whole", (0.10, 0.10, 0.60, 0.60)))
    assert direct["containment"] == 1.0 and direct["nested"] is False
    assert direct["scale_ratio"] > organ.MAX_SCALE_RATIO


def test_an_organ_that_contradicts_itself_stops_the_write(monkeypatch):
    """The `ungrounded` consistency guard, exercised by injection.

    It is not a common path — the grounding step re-measures a pair the sweep already measured as
    nested, so the two can only disagree if the organ is non-deterministic. That is precisely when
    a write must stop rather than be averaged away, so the branch is kept and pinned.
    """
    real_measure = organ.measure
    seen = {"n": 0}

    def flaky(inner, outer):
        result = real_measure(inner, outer)
        # Let the sweep run honestly, then contradict it on the single re-measurement.
        if result.get("nested") and str(inner.get("id")) == "b_part":
            seen["n"] += 1
            if seen["n"] > 1:
                return {**result, "nested": False,
                        "detail": "contradicted on re-measurement"}
        return result

    monkeypatch.setattr(organ, "measure", flaky)
    t = _run(region_id="a_part", retina_module=FakeRetina([_cand("post_b", "b_part", 0.9)]))
    assert t["movements"] == []
    (refusal,) = t["refused"]
    assert refusal["reason"] == "ungrounded"
    assert refusal["measurement"]["nested"] is False
    assert refusal["mark"] is None


def test_an_unreadable_candidate_post_is_refused_not_skipped():
    t = _run(region_id="a_part", retina_module=FakeRetina([_cand("post_missing", "x", 0.9)]))
    assert t["movements"] == []
    assert t["refused"][0]["reason"] == "unreadable_post"


def test_sentinel_post_ids_are_never_grounded_to():
    """The hygiene lane purged them; a movement grounded to a post that does not exist is worse
    than no movement, so the guard stays."""
    t = _run(region_id="a_part", retina_module=FakeRetina([
        _cand("scratch-in-memory", "auto_0", 0.99), _cand("post_b", "b_part", 0.3)]))
    assert [c["post_id"] for c in t["retina"]["skipped_candidates"]] == ["scratch-in-memory"]
    assert [e["edge"]["target_node"] for e in t["movements"]] == ["vm_post_b:b_part"]


# ── what the edge may and may not carry ──────────────────────────────────────

def test_the_edge_carries_no_epistemic_status_and_no_provenance():
    """Lane G's contract: those are `_FORBIDDEN_EDGE_KEYS`, derived from the mark at read time.
    `movement_from` runs `assert_valid_movement_edge`, which is C3's own guard, so a drift into
    carrying percept truth raises before any write."""
    t = _run(region_id="a_part", retina_module=FakeRetina([_cand("post_b", "b_part", 0.7)]))
    edge = t["movements"][0]["edge"]
    assert "epistemic_status" not in edge and "provenance" not in edge
    assert "run_id" not in edge and "step_id" not in edge
    assert all(f in edge for f in MOVEMENT_FIELDS)        # declare-and-set: all six, explicitly


def test_the_edges_status_is_measured_only_once_its_mark_is_in_the_ledger():
    """The gap this lane does not close, pinned as behaviour rather than left as prose.

    As stored, the edge cites a mark nobody committed, and it says so. Overlaid with the proposed
    marks it reads `measured`. Both are true about different worlds; the kernel reports both.
    """
    t = _run(region_id="a_part", retina_module=FakeRetina([_cand("post_b", "b_part", 0.7)]))
    (both,) = t["hydrated"]
    assert both["as_stored"]["live"] is False
    assert both["as_stored"]["epistemic"] == ""
    assert both["with_proposed_marks"]["live"] is True
    assert both["with_proposed_marks"]["epistemic"] == EpistemicStatus.MEASURED.value


def test_the_kernel_writes_nothing_to_any_post():
    posts = copy.deepcopy(POSTS)
    before = mk.posts_fingerprint(posts)
    t = asyncio.run(mk.run_kernel(post_a=POST_A, posts=posts, third_post=POST_C,
                                  region_id="a_part", persist=False,
                                  retina_module=FakeRetina([_cand("post_b", "b_part", 0.7)])))
    assert t["posts_unchanged"] is True
    assert mk.posts_fingerprint(posts) == before
    assert all(not p.get("visual_marks") for p in posts.values())
    assert t["proposed_marks"]                            # they exist, and they stayed outside


def test_a_mutated_post_is_caught_rather_than_reported_as_clean():
    """The guard has to be able to fail, or it is decoration."""
    before = mk.posts_fingerprint({"p": {"a": 1}})
    with pytest.raises(mk.PostsMutated, match="accept path"):
        mk.assert_posts_unchanged(before, mk.posts_fingerprint({"p": {"a": 2}}))


# ── the proof: the third image ───────────────────────────────────────────────

def test_the_third_image_is_placed_by_the_organ():
    t = _run(region_id="a_part", third_post=POST_C,
             retina_module=FakeRetina([_cand("post_b", "b_part", 0.7)]))
    placement = t["placement"]
    assert placement["placed"] is True
    assert placement["placed_by"] == organ.ORGAN
    assert placement["measurement"]["nested"] is True
    assert placement["region_id"] == "c_part"
    assert sm.mapped(placement["structure_map"])


def test_a_perfect_similarity_score_cannot_place_an_unmeasured_image():
    """THE ASSERTION THE LANE CARD ASKS FOR, EXPLICITLY. `post_s` is handed a retina score of 1.0
    and has no measurable nesting; it is not placed. Proposal and placement are different acts."""
    t = _run(region_id="a_part", third_post=POST_S,
             retina_module=FakeRetina([_cand("post_b", "b_part", 0.7),
                                       _cand("post_s", "s_only", 1.0)]))
    placement = t["placement"]
    assert placement["placed"] is False
    assert placement["placed_by"] is None
    assert placement["measurement"] is None
    assert placement["mark"] is None
    # There was no measurably nested region to ask the retina ABOUT, and the envelope says exactly
    # that rather than returning a bare None a reader could mistake for "asked, found nothing".
    assert placement["retina"]["status"] == "not_asked"
    assert "nothing to ask" in placement["retina"]["reason"] or \
           "no region id" in placement["retina"]["reason"]


def test_a_cold_axis_and_an_untouched_candidate_stay_different_facts():
    """Lane G's envelope, carried through rather than flattened. `unknown` is 'nothing has ever
    moved along this axis'; `empty` is 'things have, none touching this candidate'."""
    cold = mk.place(POST_C, {"edges": []}, posts={})
    assert cold["axis"]["status"] == "unknown"

    t = _run(region_id="a_part", third_post=POST_C,
             retina_module=FakeRetina([_cand("post_b", "b_part", 0.7)]))
    assert t["placement"]["axis"]["status"] == "empty"
    assert t["placement"]["axis"]["axis_movements"] == 1


def test_the_kernel_reports_what_lane_g_discarded_on_the_way_in():
    """`write_edge` does not store a prepared edge — it re-mints one from the six values it has
    parameters for. So `edge_id` changes and `observations` is replaced by a fresh `[]`.

    Lane G's own docstring names silent field-dropping as the trap its contract exists to avoid;
    the same trap is open at its front door. This lane cannot fix it (`movement_store` is not its
    file) so it reports the loss instead of printing a transcript that implies the grounding
    observation survived.
    """
    minted = {"edge_id": "edge_mv_minted", "mark_id": "vm_nest_1",
              "observations": [{"epistemic_status": "measured", "detail": "index 0.83"}],
              "valid_from": "T0", "valid_to": None}
    stored_doc = {"edges": [
        {"edge_id": "edge_mv_other", "mark_id": "vm_nest_other", "observations": []},
        {"edge_id": "edge_mv_stored", "mark_id": "vm_nest_1", "observations": [],
         "valid_from": "T0", "valid_to": None},
    ]}
    delta = mk._stored_delta(minted, stored_doc)
    assert delta["stored_edge_id"] == "edge_mv_stored"
    dropped = {d["field"] for d in delta["discarded"]}
    assert dropped == {"edge_id", "observations"}
    assert "no parameter on its signature" in delta["detail"]


def test_a_faithfully_stored_edge_reports_nothing_discarded():
    """The report has to be able to come back clean, or it is noise rather than a signal."""
    minted = {"edge_id": "e1", "mark_id": "m1", "observations": [], "valid_from": "T0",
              "valid_to": None}
    delta = mk._stored_delta(minted, {"edges": [dict(minted)]})
    assert delta["discarded"] == [] and delta["detail"] == "stored as minted"


def test_a_write_that_found_no_atlas_is_reported_not_assumed():
    assert mk._stored_delta({"mark_id": "m1"}, None)["detail"] == "no such atlas"


def test_placement_survives_a_retina_that_is_unavailable():
    """The organ is the one that decides, so a dead index must cost a proposal and not the
    placement."""
    class Broken:
        DEFAULT_K, DEFAULT_ROLE = 12, "identity"
        def propose_candidates(self, **kwargs):
            raise RuntimeError("index not built")

    placement = mk.place(POST_C, {"edges": []}, retina_module=Broken())
    assert placement["placed"] is True and placement["placed_by"] == organ.ORGAN
    assert placement["retina"]["status"] == "error"
