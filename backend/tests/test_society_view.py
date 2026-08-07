"""WAVE4 — the society view: the claims, and the two lies a meeting surface would tell.

The cognition view's failures were about a walk. A meeting has its own, and both are worse because
what is being rendered is a CLAIM rather than a reading:

  1. IT SHOWS A JOINT HYPOTHESIS AS MEASURED. Two agents agreeing is the most persuasive thing this
     system produces, and a `MEASURED` default on a response model is how `proposed` becomes
     `measured` without anybody writing the word. §1.
  2. IT PUTS A NUMBER ON AN INCOMMENSURABLE PAIR. `CompatibilityLeak` at the pixel level: a
     cross-sense magnitude on screen is the same fabrication as one in a service, and a surface is
     where "just show something comparable" is most tempting. §2.

§3 is the wholly-received refusal — the society lane's own finding, which a viewer would naturally
render as a held belief with a caveat. §4 is the route's shape.
"""
from __future__ import annotations

import pytest

from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services.agents import society as soc

N = 16


def _rle(x0, x1, y0, y1):
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


# ── 1. a joint hypothesis is proposed, on the wire too ────────────────────

def test_the_hypothesis_view_has_no_status_field_that_could_default():
    """THE SERIALIZER TRAP, at the worst place in the system for it.

    FastAPI builds the response from the model, so a field the handler never sets is filled from
    its default and rendered as though it were data. A `MEASURED` default here would render a
    `proposed` joint claim as a measurement — the exact fabrication
    `dialogue.hydrate_hypothesis` has no code path to produce.
    """
    from backend.routers.society import HypothesisView

    assert HypothesisView.model_fields["ledger_status"].is_required(), \
        "ledger_status may not have a default — that is how `proposed` becomes `measured`"
    forbidden = [n for n in HypothesisView.model_fields if n == "epistemic_status"]
    assert not forbidden, "a joint hypothesis carries no epistemic status; it is a composition"


def test_the_view_takes_its_status_from_the_hydrator_and_never_recomputes_it():
    """The hydrator is where this system records that a composition stays `proposed` however many
    of its marks are committed. A second place deciding it is a second place that can stop."""
    import pathlib

    from backend.routers import society as routes

    source = pathlib.Path(routes.__file__).read_text()
    assert "hydrate_hypothesis" in source
    assert '"measured"' not in source and "EpistemicStatus.MEASURED" not in source


def test_a_composed_hypothesis_carries_contributed_and_received_per_mark():
    """A joint claim presented as one voice would hide which half each agent is entitled to. The
    `rests_on` rows ride through the view so the surface can show the split."""
    from backend.routers.society import _hypothesis_view

    hypothesis = {
        "hypothesis_id": "ahyp_1", "claim": "nested_at_boundary", "post_id": "pA",
        "agent_ids": ["alpha", "beta"], "about_region_id": "whole",
        "rests_on": [
            {"agent_id": "alpha", "organ": "nestedness_organ", "mark_id": "m1",
             "relation": "nested_within", "basis": "mask", "detail": "d"},
            {"agent_id": "beta", "organ": "adjacency_organ", "mark_id": "m2",
             "relation": "meets", "basis": "mask", "detail": "d"},
        ],
    }
    view = _hypothesis_view(hypothesis, {"pA": {"_id": "pA", "visual_marks": []}})

    assert view["ledger_status"] == "proposed"
    assert len(view["rests_on"]) == 2
    assert {r["agent_id"] for r in view["rests_on"]} == {"alpha", "beta"}
    assert "not a measurement" in view["detail_ledger"]


def test_committing_every_cited_mark_does_not_make_the_view_measured():
    """The one-line failure the dialogue lane exists to prevent, re-asserted at the surface. Only
    the mark count moves."""
    from backend.routers.society import _hypothesis_view

    marks = [{"id": "m1", "epistemic_status": "measured"},
             {"id": "m2", "epistemic_status": "measured"}]
    hypothesis = {
        "hypothesis_id": "ahyp_1", "claim": "nested_at_boundary", "post_id": "pA",
        "agent_ids": ["alpha", "beta"], "about_region_id": "whole",
        "rests_on": [{"agent_id": "alpha", "organ": "o", "mark_id": "m1", "basis": "mask",
                      "relation": "r", "detail": "d"},
                     {"agent_id": "beta", "organ": "o", "mark_id": "m2", "basis": "mask",
                      "relation": "r", "detail": "d"}],
    }
    committed = _hypothesis_view(hypothesis, {"pA": {"_id": "pA", "visual_marks": marks}})
    assert committed["marks_live"] == "2/2"
    assert committed["ledger_status"] == "proposed"


# ── 2. incommensurable renders as incommensurable ────────────────────────

def test_an_incommensurable_verdict_carries_a_refusal_and_no_number():
    """`CompatibilityLeak` at the pixel level. The verdict a geometry agent and a chroma agent
    produce is a REFUSAL — `compare_across_senses`' own words — and there is nothing numeric on it
    for a surface to render as a similarity."""
    verdict = soc.PairVerdict("geo", "chr", soc.INCOMMENSURABLE,
                              "there is no common scale between these senses")
    row = verdict.as_dict()

    assert row["outcome"] == soc.INCOMMENSURABLE
    assert row["detail"]
    for forbidden in ("score", "similarity", "distance", "magnitude", "strength", "closeness"):
        assert not [k for k in row if forbidden in k], forbidden
    assert not any(isinstance(v, (int, float)) and not isinstance(v, bool)
                   for v in row.values()), f"a bare number on an incommensurable verdict: {row}"


def test_the_meeting_view_exposes_no_cross_sense_number_anywhere():
    """Scanned over the whole response model rather than one field: a surface renders what it is
    handed, so the guarantee has to be about the payload, not about one component's discipline."""
    from backend.routers.society import MeetingView

    for name in MeetingView.model_fields:
        for forbidden in ("similarity", "score", "distance", "affinity"):
            assert forbidden not in name, f"MeetingView.{name} would invite a comparable number"


def test_the_route_never_calls_compare_across_senses_for_a_value():
    """It may only ever be called for its REFUSAL — which `society.refuse_comparison` already does
    and raises `CompatibilityLeak` if it ever answers. A second caller here could pass a number on."""
    import pathlib

    from backend.routers import society as routes

    source = pathlib.Path(routes.__file__).read_text()
    assert "compare_across_senses" not in source


# ── 3. the wholly-received refusal is a refusal ──────────────────────────

def test_a_wholly_received_belief_is_refused_and_not_quietly_held():
    """THE SOCIETY LANE'S OWN FINDING, and the thing a viewer would naturally render as a held
    belief with a caveat. γ stood in the room while α and β composed; a belief it contributed
    nothing to is not weakened evidence, it is hearsay however many agents stand behind it."""
    from backend.routers.society import RefusalToHoldView

    assert RefusalToHoldView.model_fields["reason"].is_required(), \
        "a refusal whose reason can default is a blank"
    row = RefusalToHoldView(agent_id="gamma", hypothesis_id="ahyp_1", claim="c",
                            reason=soc.WHOLLY_RECEIVED, detail="contributed no mark")
    assert row.reason == "wholly_received"


def test_held_and_refused_are_separated_by_the_societys_own_helpers():
    """Not re-derived in the route: `held_beliefs` and `refusals_to_hold` are where the split is
    decided, and a second implementation is a second place for a refusal to become a holding."""
    import pathlib

    from backend.routers import society as routes

    source = pathlib.Path(routes.__file__).read_text()
    assert "soc.held_beliefs" in source and "soc.refusals_to_hold" in source


# ── 4. the route's shape ─────────────────────────────────────────────────

def test_the_route_is_read_only():
    import pathlib

    from backend.routers import society as routes

    source = pathlib.Path(routes.__file__).read_text()
    for write in ("insert_one", "update_one", "replace_one", "delete_one", "bulk_write",
                  "find_one_and_update"):
        assert write not in source, f"the society routes call {write} — they must not"
    assert "@router.post" not in source and "@router.put" not in source


def test_the_meeting_is_walked_rather_than_staged():
    """`convene` refuses a group that did not travel, and shortcutting that by placing agents at
    the locus would stage the very thing this surface exists to show honestly."""
    import pathlib

    from backend.routers import society as routes

    source = pathlib.Path(routes.__file__).read_text()
    assert "cognition.walk" in source, "the members must WALK to the meeting"
    assert "soc.convene" in source, "and be convened by the society module's own guard"


def test_a_group_that_could_not_meet_is_a_conflict_not_an_empty_meeting():
    """"Nobody travelled far enough" and "they met and nothing composed" are different findings,
    and a surface that rendered them alike would lose the one that is about the graph."""
    import pathlib

    from backend.routers import society as routes

    source = pathlib.Path(routes.__file__).read_text()
    assert "status_code=409" in source
    assert "NotTravelled" in source and "NotASociety" in source


def test_the_bodies_route_serves_the_declared_group():
    from fastapi.testclient import TestClient

    from backend.main import app

    body = TestClient(app).get("/api/v1/society/bodies").json()
    assert len(body) >= 3
    organs = {row["organ"] for row in body}
    assert len(organs) >= 3, "a society needs more than one kind of body"
    assert any(row.get("character") for row in body)


def test_the_default_group_can_produce_all_three_outcomes():
    """The bodies are chosen so ONE meeting shows the whole partition: two geometry organs that can
    compose, and one sensory organ that cannot be about the same thing as either."""
    from backend.routers.society import DEFAULT_BODIES

    organs = [b["organ"] for b in DEFAULT_BODIES]
    assert "nestedness_organ" in organs and "adjacency_organ" in organs
    assert "chroma_organ" in organs, "without a sense there is no incommensurable pair to show"
    assert len(set(organs)) == len(organs), "three copies of one world is not a society"
