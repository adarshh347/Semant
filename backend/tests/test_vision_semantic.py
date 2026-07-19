"""
VISION-D · D0 — semantic contract + provider decision.

The schema must make geometry unrepresentable and reject unknown candidate IDs; the
provider must report an explicit unavailable state (the OpenRouter key is a placeholder).
"""
import pytest
from pydantic import ValidationError

from backend.schemas import vision_semantic as vs
from backend.services import semantic_provider as sp


# ── the schema forbids geometry ──────────────────────────────────────────────
@pytest.mark.parametrize("bad_field", ["box", "polygon", "polygons", "mask_rle", "rle",
                                       "coordinates", "x", "y", "w", "h", "parent_id",
                                       "geometry_rev"])
def test_candidate_rejects_geometry_field(bad_field):
    with pytest.raises(ValidationError):
        vs.CandidateSemantics(candidate_id="seg_0", label="wall", **{bad_field: [[0, 0]]})


def test_response_rejects_geometry_anywhere():
    with pytest.raises(ValidationError):
        vs.SemanticResponse(candidates=[{"candidate_id": "seg_0", "box": {"x": 0}}])
    with pytest.raises(ValidationError):
        vs.SemanticResponse(relations=[{"from_id": "a", "to_id": "b", "relation": "beside",
                                        "polygon": [[0, 0]]}])


def test_valid_semantic_response_parses():
    r = vs.SemanticResponse(
        candidates=[{"candidate_id": "seg_0", "label": "wall", "ranked_alternatives": ["stone"],
                     "confidence": 0.8, "material": "marble"}],
        relations=[{"from_id": "seg_0", "to_id": "seg_1", "relation": "beside", "confidence": 0.5}],
        global_reading={"composition": "central", "atmosphere": "solemn"},
        needs_better_evidence=["seg_2"])
    assert r.candidates[0].label == "wall" and r.schema_version == vs.SCHEMA_VERSION


def test_has_geometry_key_detects_nested():
    assert vs.has_geometry_key({"candidates": [{"candidate_id": "x", "box": {"x": 1}}]}) is True
    assert vs.has_geometry_key({"candidates": [{"candidate_id": "x", "label": "wall"}]}) is False


# ── unknown candidate ids are rejected ───────────────────────────────────────
def test_enforce_candidate_ids_flags_unknown():
    r = vs.SemanticResponse(
        candidates=[{"candidate_id": "seg_0"}, {"candidate_id": "GHOST"}],
        relations=[{"from_id": "seg_0", "to_id": "FARAWAY", "relation": "same"}],
        needs_better_evidence=["seg_9"])
    bad = vs.enforce_candidate_ids(r, {"seg_0", "seg_1"})
    assert set(bad) == {"GHOST", "FARAWAY", "seg_9"}       # a `person` can't adopt distant ids
    assert vs.enforce_candidate_ids(r, {"seg_0", "seg_1", "GHOST", "FARAWAY", "seg_9"}) == []


# ── provider decision + unavailable state ────────────────────────────────────
def test_provider_decision_is_openrouter_gpt4o_mini():
    assert sp.PROVIDER == "openrouter" and sp.MODEL == "openai/gpt-4o-mini"
    assert "google/gemini-2.5-flash-lite" in sp.FALLBACK_MODELS


def test_provider_key_validation_and_unavailable_state(monkeypatch):
    # env-independent: a placeholder/short key → unavailable (never fabricates a reading);
    # a real-looking key → available. Does not depend on the machine's actual .env.
    monkeypatch.setattr(sp.settings, "OPENROUTER_API_KEY", "placeholder")
    p = sp.SemanticProvider()
    assert p.available() is False
    st = p.state()
    assert st["state"] == "unavailable" and "placeholder" in st["reason"].lower()
    res = p.interpret(image_b64="", allowed_ids=["seg_0"], prompt="name it")
    assert res.status == "unavailable" and res.response is None
    monkeypatch.setattr(sp.settings, "OPENROUTER_API_KEY", "sk-or-v1-" + "x" * 40)
    assert sp.SemanticProvider().available() is True


# ── fake provider (deterministic, id-bound) ──────────────────────────────────
def test_fake_provider_binds_to_allowed_ids_and_drops_unknown():
    resp = vs.SemanticResponse(candidates=[{"candidate_id": "seg_0", "label": "figure"},
                                           {"candidate_id": "GHOST", "label": "person"}])
    p = sp.FakeSemanticProvider(resp)
    res = p.interpret(image_b64="x", allowed_ids=["seg_0"], prompt="")
    assert res.status == "ready"
    ids = [c.candidate_id for c in res.response.candidates]
    assert ids == ["seg_0"] and "GHOST" in res.dropped_ids   # ghost id dropped, not honoured


def test_fake_provider_can_be_unavailable():
    p = sp.FakeSemanticProvider(available=False)
    assert p.interpret(image_b64="", allowed_ids=[], prompt="").status == "unavailable"
