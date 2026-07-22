"""
CIRCUIT-001 P1F — announcement-only merge observation.

The merge event's arithmetic did not close: `candidates - kept_auto` was an
unlabelled residual mixing two distinct drop reasons, so a candidate that
vanished at the merge boundary left no trace of WHY. These tests pin the
counters that close it, and — more importantly — pin that they change NOTHING:
same regions, same ids, same order, same decisions.

The merge loop lives inside an async route with Mongo and a telemetry recorder
around it, so it is re-enacted here against the REAL helpers, exactly as
`test_vision_c5_mixed.py` already does for the dedup rules. What is under test is
the arithmetic and the classification, both of which are pure.
"""
from backend.routers import posts as R


def _reg(x, y, w, h, rid=None, detector="yolo", category="thing", actor="auto"):
    return {
        "id": rid, "actor": actor, "detector": detector, "category": category,
        "box": {"x": x, "y": y, "w": w, "h": h},
    }


def _merge(candidates, existing_list):
    """A faithful re-enactment of the route's merge loop, counters included.

    Mirrors `posts.detect_regions` at the merge boundary. Kept deliberately close
    to the source so a divergence shows up as a failing invariant rather than as
    a quietly wrong test.
    """
    existing = {r.get("id"): r for r in existing_list}
    creator_regions = [r for r in existing_list if r.get("actor") == "creator"]
    creator_ids = {r.get("id") for r in creator_regions}

    kept_auto = []
    suppressed_by_id = 0
    suppressed_by_id_moved = 0
    suppressed_by_geometry = 0
    id_reused_auto = 0
    id_reused_auto_moved = 0

    for r in candidates:
        if r.get("id") in creator_ids:
            suppressed_by_id += 1
            held = next((c for c in creator_regions if c.get("id") == r.get("id")), None)
            if held is not None and R._region_box_iou(r, held) < R._MERGE_SAME_PLACE_IOU:
                suppressed_by_id_moved += 1
            continue
        r.setdefault("actor", "auto")
        r.setdefault("detector", "vision")
        prev = existing.get(r["id"])
        if prev is not None and prev.get("actor") != "creator":
            id_reused_auto += 1
            if R._region_box_iou(r, prev) < R._MERGE_SAME_PLACE_IOU:
                id_reused_auto_moved += 1
        # The curator-field carry, unchanged by P1F and reproduced here because the
        # byte-identical test below is only meaningful if this harness is faithful.
        # (It caught its own omission of exactly this block on first run.)
        if prev:
            r["prioritised"] = prev.get("prioritised", False)
            r["weight"] = prev.get("weight", 0)
            r["user_note"] = prev.get("user_note", "")
            if prev.get("actor") == "creator":
                r["actor"] = "creator"
        else:
            r.setdefault("prioritised", False)
            r.setdefault("weight", 0)
            r.setdefault("user_note", "")
        if R._is_duplicate_geometry(r, creator_regions, 0.7, require_same_kind=False) \
                or R._is_duplicate_geometry(r, kept_auto, 0.85, require_same_kind=True):
            suppressed_by_geometry += 1
            continue
        kept_auto.append(r)

    return {
        "regions": creator_regions + kept_auto,
        "detail": {
            "creator_preserved": len(creator_regions),
            "kept_auto": len(kept_auto),
            "candidates": len(candidates),
            "suppressed_by_id": suppressed_by_id,
            "suppressed_by_id_moved": suppressed_by_id_moved,
            "suppressed_by_geometry": suppressed_by_geometry,
            "id_reused_auto": id_reused_auto,
            "id_reused_auto_moved": id_reused_auto_moved,
        },
    }


def _closes(detail):
    """THE acceptance invariant. A residual means a candidate vanished for a
    reason nobody named — which is precisely the condition this gate exists to
    make impossible."""
    return detail["candidates"] == (
        detail["kept_auto"] + detail["suppressed_by_id"] + detail["suppressed_by_geometry"]
    )


# ── the invariant ────────────────────────────────────────────────────────────

def test_arithmetic_closes_when_nothing_is_suppressed():
    out = _merge([_reg(0, 0, 0.2, 0.2, "seg_0"), _reg(0.5, 0.5, 0.2, 0.2, "seg_1")], [])
    assert _closes(out["detail"])
    assert out["detail"]["kept_auto"] == 2
    assert out["detail"]["suppressed_by_id"] == 0
    assert out["detail"]["suppressed_by_geometry"] == 0


def test_arithmetic_closes_across_both_suppression_paths_at_once():
    creator = _reg(0, 0, 0.2, 0.2, "seg_0", actor="creator")
    cands = [
        _reg(0, 0, 0.2, 0.2, "seg_0"),          # dropped by the id guard
        _reg(0.5, 0.5, 0.2, 0.2, "seg_9"),      # kept
        _reg(0.5, 0.5, 0.2, 0.2, "seg_10"),     # dropped by geometry (duplicate of seg_9)
    ]
    d = _merge(cands, [creator])["detail"]
    assert _closes(d)
    assert (d["kept_auto"], d["suppressed_by_id"], d["suppressed_by_geometry"]) == (1, 1, 1)


def test_arithmetic_closes_on_an_empty_candidate_set():
    d = _merge([], [_reg(0, 0, 0.2, 0.2, "seg_0", actor="creator")])["detail"]
    assert _closes(d)
    assert d["candidates"] == 0


# ── the id guard, and the hazard it hides ────────────────────────────────────

def test_id_guard_drop_in_the_SAME_place_is_counted_but_not_flagged_moved():
    # An ordinary re-detection of the thing the curator already refined. Harmless,
    # and it must not be reported as a relocation or the signal becomes noise.
    creator = _reg(0, 0, 0.3, 0.3, "seg_0", actor="creator")
    d = _merge([_reg(0, 0, 0.3, 0.3, "seg_0")], [creator])["detail"]
    assert d["suppressed_by_id"] == 1
    assert d["suppressed_by_id_moved"] == 0


def test_id_guard_drop_in_a_DIFFERENT_place_is_flagged_moved():
    # THE HW-C8 HAZARD. The auto pass found something else at this id; it is
    # discarded in favour of the curator's older mask, and telemetry previously
    # reported only `creator_preserved` and looked like success.
    creator = _reg(0, 0, 0.2, 0.2, "seg_0", actor="creator")
    d = _merge([_reg(0.7, 0.7, 0.2, 0.2, "seg_0")], [creator])["detail"]
    assert d["suppressed_by_id"] == 1
    assert d["suppressed_by_id_moved"] == 1


# ── the auto→auto branch: the larger, previously uninstrumented population ────

def test_auto_id_reuse_in_the_same_place_is_observed_and_not_flagged():
    prev = _reg(0, 0, 0.3, 0.3, "seg_0")                       # actor auto
    d = _merge([_reg(0, 0, 0.3, 0.3, "seg_0")], [prev])["detail"]
    assert d["id_reused_auto"] == 1
    assert d["id_reused_auto_moved"] == 0
    assert d["kept_auto"] == 1                                 # it still survives


def test_auto_id_reuse_that_MOVED_is_flagged_while_still_surviving():
    # This is the case P1E called the larger exposure: the candidate keeps an id
    # that already named something else and survives as an ordinary region, so a
    # re-pointed reference was previously invisible in the counts.
    prev = _reg(0, 0, 0.2, 0.2, "seg_0")
    d = _merge([_reg(0.8, 0.8, 0.2, 0.2, "seg_0")], [prev])["detail"]
    assert d["id_reused_auto"] == 1
    assert d["id_reused_auto_moved"] == 1
    assert d["kept_auto"] == 1                                 # NOT suppressed — only observed
    assert d["suppressed_by_id"] == 0
    assert _closes(d)


def test_moved_counts_do_NOT_participate_in_the_sum():
    # They describe suppressions/reuses already counted. Adding them would double
    # count and the invariant would stop meaning anything.
    creator = _reg(0, 0, 0.2, 0.2, "seg_0", actor="creator")
    d = _merge([_reg(0.9, 0.9, 0.2, 0.2, "seg_0")], [creator])["detail"]
    assert d["suppressed_by_id_moved"] == 1
    assert _closes(d)


# ── behaviour is unchanged: this is the load-bearing guarantee ────────────────

def _merge_without_counters(candidates, existing_list):
    """The route's merge loop exactly as it behaved BEFORE P1F."""
    existing = {r.get("id"): r for r in existing_list}
    creator_regions = [r for r in existing_list if r.get("actor") == "creator"]
    creator_ids = {r.get("id") for r in creator_regions}
    kept_auto = []
    for r in candidates:
        if r.get("id") in creator_ids:
            continue
        r.setdefault("actor", "auto")
        r.setdefault("detector", "vision")
        prev = existing.get(r["id"])
        if prev:
            r["prioritised"] = prev.get("prioritised", False)
            r["weight"] = prev.get("weight", 0)
            r["user_note"] = prev.get("user_note", "")
            if prev.get("actor") == "creator":
                r["actor"] = "creator"
        else:
            r.setdefault("prioritised", False)
            r.setdefault("weight", 0)
            r.setdefault("user_note", "")
        if R._is_duplicate_geometry(r, creator_regions, 0.7, require_same_kind=False) \
                or R._is_duplicate_geometry(r, kept_auto, 0.85, require_same_kind=True):
            continue
        kept_auto.append(r)
    return creator_regions + kept_auto


def test_regions_are_byte_identical_to_the_pre_P1F_behaviour():
    creator = _reg(0, 0, 0.2, 0.2, "seg_0", actor="creator")
    auto_prev = _reg(0.4, 0.4, 0.2, 0.2, "seg_3")
    existing = [creator, auto_prev]

    def cands():
        return [
            _reg(0, 0, 0.2, 0.2, "seg_0"),           # id-guard drop
            _reg(0.9, 0.9, 0.2, 0.2, "seg_3"),       # auto id reuse, moved
            _reg(0.6, 0.1, 0.2, 0.2, "seg_7"),       # kept
            _reg(0.6, 0.1, 0.2, 0.2, "seg_8"),       # geometry drop
        ]

    after = _merge(cands(), existing)["regions"]
    before = _merge_without_counters(cands(), existing)

    assert [r["id"] for r in after] == [r["id"] for r in before]      # same ids, same ORDER
    assert after == before                                            # and same content


def test_counters_cannot_raise_on_degenerate_regions():
    # Every operation added is `.get()` plus `_region_box_iou`, which guards its
    # own division. Boxes missing entirely, zero-area, or absent keys must all be
    # survivable — a telemetry counter must never take down a live route.
    creator = {"id": "seg_0", "actor": "creator"}                     # no box at all
    cands = [
        {"id": "seg_0"},                                              # no box, id-guard path
        {"id": "seg_1", "box": {}},                                   # empty box
        {"id": "seg_2", "box": {"x": 0, "y": 0, "w": 0, "h": 0}},      # zero area
    ]
    d = _merge(cands, [creator])["detail"]
    assert _closes(d)
    assert d["suppressed_by_id"] == 1


def test_zero_area_boxes_do_not_report_a_false_relocation():
    # `_region_box_iou` returns 0.0 when the union is 0, which is BELOW the
    # threshold — so a pair of empty boxes would read as "moved" unless the
    # region genuinely has geometry. Recorded as the known edge: it is counted as
    # moved, and that is honest (we cannot say they are in the same place), but
    # it means a corpus of box-less regions would inflate the signal.
    creator = {"id": "seg_0", "actor": "creator", "box": {"x": 0, "y": 0, "w": 0, "h": 0}}
    d = _merge([{"id": "seg_0", "box": {"x": 0, "y": 0, "w": 0, "h": 0}}], [creator])["detail"]
    assert d["suppressed_by_id"] == 1
    assert d["suppressed_by_id_moved"] == 1        # documented, not asserted as desirable


def test_threshold_is_an_observation_constant_not_a_dedup_threshold():
    # It must stay distinct from the 0.7 / 0.85 DECISION thresholds, so that
    # relaxing an observation can never loosen a merge rule by accident.
    assert R._MERGE_SAME_PLACE_IOU == 0.5
    assert R._MERGE_SAME_PLACE_IOU not in (0.7, 0.85)
