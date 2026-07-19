"""
VISION-F · F2 — capability readiness guard.

Proves an action whose capability is unavailable is downgraded to a planned SKIP (never a partial
write), and available actions pass through.
"""
from backend.services import vision_capabilities as cap


FULL = {"geometry": True, "yolo": True, "sam": True, "segformer": True,
        "fashion_segmenter": True, "semantic_provider": True, "dinov2": True, "fashionclip": True}


def test_available_action_runs():
    r = cap.resolve_action("rerun_profile_general", FULL)
    assert r["runnable"] and r["action"] == "rerun_profile_general"


def test_unavailable_capability_becomes_skip_not_a_write():
    down = {**FULL, "sam": False}
    r = cap.resolve_action("sam_refine", down)
    assert r["action"] == "skip" and r["runnable"] is False and "sam" in r["reason"]
    # a general rerun also needs SAM → also skipped
    assert cap.resolve_action("rerun_profile_general", down)["action"] == "skip"


def test_retain_box_never_needs_a_capability():
    assert cap.resolve_action("retain_box", {})["runnable"] is True     # honest retention always runs


def test_semantic_and_embed_gate_on_their_providers():
    down = {**FULL, "semantic_provider": False, "dinov2": False}
    assert cap.resolve_action("semantic_refresh", down)["action"] == "skip"
    assert cap.resolve_action("embed_dinov2", down)["action"] == "skip"


def test_plan_skips_marks_each_item():
    down = {**FULL, "segformer": False}
    plan = [{"post_id": "p1", "action": "rerun_profile_architecture"},
            {"post_id": "p2", "action": "derive_from_polygon"},
            {"post_id": "p3", "action": "retain_box"}]
    out = {o["post_id"]: o for o in cap.plan_skips(plan, down)}
    assert out["p1"]["action"] == "skip"                    # segformer down → arch rerun skipped
    assert out["p2"]["runnable"] and out["p3"]["runnable"]  # geometry + retain still run
