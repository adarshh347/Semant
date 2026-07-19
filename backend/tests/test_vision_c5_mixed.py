"""
VISION-C · C5 — mixed-domain scheduling + candidate-merge safety.

Covers the gate's non-UI invariants: selective scheduling (chosen profiles → passes),
geometry-only dedup (no duplicate masks; a wall and a person at the same spot stay
separate), and no anchor prison. The creator-preservation + profile-control UX are
verified in the browser; the merge helpers are unit-tested here.
"""
from backend.services import domain_profiles as dp
from backend.routers import posts as R


# ── selective scheduling: only the chosen profiles' passes ───────────────────
def test_mixed_fashion_architecture_schedules_both_not_everything():
    prof = dp.propose_profile({"fashion": 0.6, "architecture": 0.55, "painting": 0.02})
    assert set(prof["chosen"]) == {"general", "fashion", "architecture"}
    passes = prof["scheduled_passes"]
    assert "fashionpedia_r50fpn" in passes and "segformer_b0_ade" in passes
    # painting was below gate → its (extra) segformer scene proposal isn't added twice,
    # and nothing schedules a painting-only pass here.
    assert "yolo11n_seg" in passes                      # general always
    assert passes.count("sam21_hiera_tiny") == 1        # deduped across profiles


def test_general_only_image_runs_minimal():
    prof = dp.propose_profile({"fashion": 0.1, "architecture": 0.1, "painting": 0.1})
    assert prof["scheduled_passes"] == ["yolo11n_seg", "sam21_hiera_tiny"]   # not every model


# ── geometry-only dedup (no duplicate masks; kinds stay separate) ────────────
def _reg(x, y, w, h, detector="yolo", category="figure"):
    return {"box": {"x": x, "y": y, "w": w, "h": h}, "detector": detector, "category": category}


def test_duplicate_same_kind_is_dropped():
    a = _reg(0.1, 0.1, 0.4, 0.4, "yolo", "figure")
    dup = _reg(0.11, 0.11, 0.4, 0.4, "yolo", "figure")   # near-identical, same detector
    assert R._is_duplicate_geometry(dup, [a], 0.85, require_same_kind=True) is True


def test_wall_and_person_same_spot_are_not_duplicates():
    wall = _reg(0.0, 0.0, 1.0, 1.0, "segformer_ade", "surface")
    person = _reg(0.3, 0.2, 0.4, 0.7, "yolo", "figure")   # overlaps the wall region
    # different kind → NOT a duplicate; both are separate evidence.
    assert R._is_duplicate_geometry(person, [wall], 0.85, require_same_kind=True) is False


def test_auto_dropped_when_overlapping_a_creator_region():
    creator = _reg(0.3, 0.3, 0.3, 0.3, "sam2", "figure")
    auto = _reg(0.31, 0.31, 0.3, 0.3, "yolo", "figure")   # same object the curator refined
    # against creator regions we drop the auto regardless of kind (creator wins).
    assert R._is_duplicate_geometry(auto, [creator], 0.7, require_same_kind=False) is True


def test_box_iou():
    a = _reg(0, 0, 0.4, 0.4)
    assert R._region_box_iou(a, _reg(0, 0, 0.4, 0.4)) == 1.0
    assert R._region_box_iou(a, _reg(0.5, 0.5, 0.4, 0.4)) == 0.0


# ── no anchor prison: five separate masks stay five (from B2, re-asserted) ────
def test_five_masks_stay_separate_under_dedup():
    kept = []
    for i in range(5):
        r = _reg(i * 0.2, 0.2, 0.15, 0.6, "yolo", "figure")
        if not R._is_duplicate_geometry(r, kept, 0.85, require_same_kind=True):
            kept.append(r)
    assert len(kept) == 5                                # none collapsed into another
