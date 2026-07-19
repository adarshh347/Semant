"""
VISION-C · C4 — painting profile.

No universal painting segmentor is invented. The painting profile makes SAM-prompted
individuation primary (object-mask workflow) and leans on Differential Grounds
(Field/Path/Boundary/Constellation/Relation/Frame — shipped in Differential v1) as the
non-object workflow, so "no useful automatic objects" is a valid outcome, not a failure.
"""
from backend.services import domain_profiles as dp
from backend.services.vision_orchestrator import default_roster


def test_painting_profile_makes_sam_primary_no_forced_object_detector():
    prof = dp.apply_override(None, mode="painting")
    assert "painting" in prof["chosen"]
    # SAM (prompted individuation) is scheduled; there is NO fashion/dedicated-object
    # parser forced onto a painting.
    assert "sam21_hiera_tiny" in prof["scheduled_passes"]
    assert "fashionpedia_r50fpn" not in prof["scheduled_passes"]


def test_painting_passes_reference_real_adapters_only():
    roster = {s.name for s in default_roster()}
    for name in dp.PROFILE_PASSES["painting"]:
        assert name in roster            # sam + optional segformer scene proposals


def test_painting_never_requires_auto_objects():
    # the profile contract carries a chosen set + passes; it never asserts that regions
    # must exist. "No objects" leaves the curator the Grounds path (Differential v1),
    # which is object-independent — a painting may begin from the gesture.
    prof = dp.apply_override(None, mode="painting")
    assert isinstance(prof["scheduled_passes"], list)
    assert prof["chosen"] == ["general", "painting"]     # general stays a cheap fallback
    # nothing in the contract forces an object mask to be produced.
    assert "requires_regions" not in prof
