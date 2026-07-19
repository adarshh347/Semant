"""
VISION-C-DOMAIN-PROFILES-001 · C0 — the DomainProfile contract.

Pure/deterministic tests of the multi-label proposal, user override (which always wins),
scheduled-pass mapping, and schema-validity of the persisted profile. Model-backed
scoring (classify_domains) is exercised at the C0 gate via the endpoint.
"""
import pytest

from backend.services import domain_profiles as dp
from backend.services.vision_orchestrator import default_roster
from backend.schemas.post import PostUpdate


def test_propose_is_multilabel_over_gate():
    prof = dp.propose_profile({"fashion": 0.52, "architecture": 0.41, "painting": 0.05})
    assert prof["chosen"] == ["general", "fashion", "architecture"]   # both specialists, not painting
    assert prof["mode"] == "auto" and prof["user_overridden"] is False
    assert prof["proposed"]["fashion"] == 0.52 and prof["proposed"]["painting"] == 0.05
    assert "fashion 0.52" in prof["reason"]
    # scheduled passes cover general + both specialists' primaries + SAM
    passes = prof["scheduled_passes"]
    assert "yolo11n_seg" in passes and "fashionpedia_r50fpn" in passes
    assert "segformer_b0_ade" in passes and "sam21_hiera_tiny" in passes


def test_propose_none_over_gate_is_general_only():
    prof = dp.propose_profile({"fashion": 0.2, "architecture": 0.1, "painting": 0.15})
    assert prof["chosen"] == ["general"]
    assert prof["scheduled_passes"] == dp.passes_for(["general"])
    assert "general only" in prof["reason"]


def test_mixed_fashion_and_architecture():
    prof = dp.propose_profile({"fashion": 0.46, "architecture": 0.44, "painting": 0.10})
    assert "fashion" in prof["chosen"] and "architecture" in prof["chosen"]  # an image can be both


def test_override_by_mode_wins_and_persists_flag():
    auto = dp.propose_profile({"fashion": 0.6, "architecture": 0.05, "painting": 0.02})
    over = dp.apply_override(auto, mode="painting")
    assert over["chosen"] == ["general", "painting"]      # curator forced painting
    assert over["user_overridden"] is True
    assert "sam21_hiera_tiny" in over["scheduled_passes"]
    assert "user override" in over["reason"]


def test_override_by_explicit_chosen_set():
    over = dp.apply_override(None, chosen=["architecture", "fashion", "bogus"])
    assert over["chosen"] == ["general", "architecture", "fashion"]  # bogus dropped, general first
    assert over["user_overridden"] is True


def test_override_auto_reuses_chosen():
    auto = dp.propose_profile({"fashion": 0.5, "architecture": 0.4, "painting": 0.0})
    over = dp.apply_override(auto, mode="auto")
    assert set(over["chosen"]) == {"general", "fashion", "architecture"}
    assert over["user_overridden"] is True


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        dp.apply_override(None, mode="sculpture")


def test_passes_for_general_first_and_deduped():
    passes = dp.passes_for(["fashion", "general", "architecture"])
    assert passes[0] == "yolo11n_seg"                     # general's cheap pass leads
    assert passes.count("sam21_hiera_tiny") == 1          # deduped across profiles


def test_scheduled_passes_are_real_roster_adapters():
    roster = {s.name for s in default_roster()}
    for prof, passes in dp.PROFILE_PASSES.items():
        for pass_name in passes:
            assert pass_name in roster, f"{prof} schedules unknown adapter {pass_name}"


def test_persisted_profile_is_schema_valid():
    prof = dp.propose_profile({"fashion": 0.5, "architecture": 0.4, "painting": 0.05})
    p = PostUpdate(domain_profile=prof)   # must not raise
    assert p.domain_profile["chosen"] == ["general", "fashion", "architecture"]


def test_default_profile_is_general_only():
    d = dp.default_profile()
    assert d["chosen"] == ["general"] and d["user_overridden"] is False
