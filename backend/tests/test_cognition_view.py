"""WAVE4 — the lived-cognition view: the claims, and the three ways a viewing surface lies.

A surface is a new place for this system to become dishonest, and the failures are specific:

  1. IT HIDES REFUSALS — renders what was found and leaves the rest blank. An agent hemmed in by
     eleven refused crossings then looks identical to one standing in an empty world, and the most
     informative thing it had to say is the thing that did not render. §1.
  2. IT NARRATES AN ARRIVAL — fills the destination in from the post or the graph. `movement.step`
     empties the percept field on purpose; a view that repopulated it would show the agent a world
     it had not looked at. §2.
  3. IT LETS TEMPERAMENT TOUCH THE READING — the bright line the temperament lane drew. Two
     characters at one locus must produce byte-identical measurements and visibly different routes,
     and a surface is exactly where those could quietly become one thing. §3.

§4 is the route: read-only, and the un-defaulted status fields the curator lane's serializer trap
made compulsory.
"""
from __future__ import annotations

import pytest

from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services.agents import cognition
from backend.services.agents import movement as mv
from backend.services.agents import situated_agent as sa
from backend.services.agents import temperament as tp

N = 16
STAMP = "2026-08-07T00:00:00+00:00"


def _rle(x0, x1, y0, y1):
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


def _post(pid):
    return {"_id": pid, "region_annotations": [
        {"id": "part", "label": "part", "mask_rle": _rle(4, 12, 4, 12)},
        {"id": "whole", "label": "whole", "mask_rle": _rle(0, 16, 0, 16)},
    ]}


def _marks(posts):
    out = []
    for pid, post in posts.items():
        for m in nest.find_nested_pairs(post["region_annotations"]):
            out.append(nest.grounding_mark(m, post_id=pid))
    return out


def _graph(edges):
    return {"_id": "atlas_view", "edges": edges}


def _edge(edge_id, source, target, spans, mark_id, *, axis="axis_nestedness", syst=0.7,
          relation="nested_within"):
    """Built with `movement_graph`'s OWN entry builder rather than hand-rolled.

    A hand-rolled dict was the first version and it produced an empty horizon everywhere, because
    `is_movement_edge` keys on `kind` and the fixture had none — so the tests were exercising a
    shape nothing in production has. Using the real builder is the same discipline the organ audit
    settled on for marks.
    """
    from backend.services import movement_graph as mgraph

    return mgraph.movement_edge_entry(
        mark_id=mark_id, source_node=source, target_node=target, spans=list(spans),
        axis_ref=axis, systematicity=syst, weight=1.0, edge_id=edge_id)


def _world():
    """Two pictures, one grounded crossing between them, and the marks that foot it."""
    posts = {"pA": _post("pA"), "pB": _post("pB")}
    marks = _marks(posts)
    by_post = {}
    for m in marks:
        by_post.setdefault(m["post_id"], []).append(m)
    graph = _graph([_edge("e_cross", "vm_pA:part", "vm_pB:part", ["pA", "pB"],
                          by_post["pA"][0]["id"])])
    return posts, graph, marks


def _agent(temperament="", post_id="pA", region="part"):
    return sa.inhabit(agent_id=f"a_{temperament or 'plain'}", post_id=post_id,
                      region_id=region, organ_set=(nest.ORGAN,), temperament=temperament)


# ── 1. refusals are information ────────────────────────────────────────────

def test_a_refused_crossing_renders_with_its_reason_and_never_as_a_blank():
    """THE POINT OF THE SURFACE. A blank says "nothing here"; a refusal says "something here I
    could not stand on, and here is the word for why"."""
    posts, _graph_, marks = _world()
    # an edge whose mark measures a different pair — refused, and refused for a nameable reason
    graph = _graph([_edge("e_bad", "vm_pA:part", "vm_pB:part", ["pA", "pB"], "vm_nonexistent")])
    agent = _agent()
    sa.perceive(agent, posts["pA"], now=STAMP)
    entries = mv.horizon(agent, graph, posts, proposed_marks=marks)

    view = cognition.horizon_at(entries)
    assert view["refused"], "the fixture must actually produce a refusal"
    row = view["refused"][0]
    assert row["reason"] and row["gloss"] and row["about"]
    assert row["gloss"] != row["reason"], "the gloss must be a sentence, not the constant again"


def test_the_two_families_of_refusal_stay_apart():
    """`movement` keeps "the edge cannot be walked" and "the traveller cannot leave" separate for
    the reason Lane M keeps `box_only` and `surface_only` apart. A single refused count would hide
    which world the refusals are about, and the view would become a progress bar."""
    assert cognition.refusal_about(mv.UNFOOTED_BOX) == cognition.ABOUT_THE_TRAVELLER
    assert cognition.refusal_about(mv.UNFOOTED_UNPERCEIVED) == cognition.ABOUT_THE_TRAVELLER
    for reason in (mv.UNREACHABLE_CLOSED, mv.UNREACHABLE_NO_MARK, mv.UNREACHABLE_INTERPRETIVE,
                   mv.UNREACHABLE_MISSTATED, mv.UNREACHABLE_ELSEWHERE):
        assert cognition.refusal_about(reason) == cognition.ABOUT_THE_EDGE


def test_every_movement_refusal_reason_has_a_gloss():
    """A reason the surface cannot render is a reason that becomes a blank in the one place it
    matters. Enumerated off `movement`'s own constants so a seventh reason fails here."""
    declared = {v for k, v in vars(mv).items()
                if k.startswith(("UNREACHABLE_", "UNFOOTED_")) and isinstance(v, str)}
    missing = declared - set(cognition.REFUSAL_GLOSS)
    assert not missing, f"no gloss for {sorted(missing)} — it would render as an unexplained blank"


def test_the_tally_counts_the_families_separately():
    posts, _g, marks = _world()
    graph = _graph([_edge("e_bad", "vm_pA:part", "vm_pB:part", ["pA", "pB"], "vm_nope"),
                    _edge("e_closed", "vm_pA:part", "vm_pB:whole", ["pA", "pB"], "vm_nope2")])
    agent = _agent()
    sa.perceive(agent, posts["pA"], now=STAMP)
    tally = cognition.horizon_at(mv.horizon(agent, graph, posts, proposed_marks=marks))["tally"]
    assert set(tally) == {"reachable", "refused_edge", "refused_traveller"}
    assert tally["refused_edge"] + tally["refused_traveller"] >= 1


def test_a_station_where_nothing_was_reachable_still_records_its_horizon():
    """The most informative kind of stop. A view that only recorded successful steps would render
    an agent that looked and found every road refused as a walk that simply ended."""
    posts, _g, marks = _world()
    graph = _graph([_edge("e_bad", "vm_pA:part", "vm_pB:part", ["pA", "pB"], "vm_nope")])
    walk = cognition.walk(_agent(), graph, posts, marks=marks, steps=2, now=STAMP)

    assert walk["stations"], "a walk with no reachable edge still has a station"
    first = walk["stations"][0]
    assert first["horizon"]["refused"]
    assert "ended" in first and first["ended"]["reason"], \
        "a walk that stops must say why, not merely stop"


# ── 2. no narrated arrival ────────────────────────────────────────────────

def test_a_step_says_it_arrived_with_an_empty_field():
    """`movement.step` empties the percept field because everything the agent knew was knowledge
    from where it stood. The view states that rather than omitting it — an omission invites the
    reader to assume a destination was seen."""
    posts, graph, marks = _world()
    walk = cognition.walk(_agent(), graph, posts, marks=marks, steps=1, now=STAMP)
    assert walk["steps"], "the fixture must produce a step"
    step = walk["steps"][0]
    assert step["arrived_with"] == 0
    assert "empty field" in step["arrival_detail"]


def test_the_destination_is_only_populated_after_the_agent_perceives_there():
    """The second station's readings exist because the agent LOOKED, not because the view filled
    them in from the post."""
    posts, graph, marks = _world()
    walk = cognition.walk(_agent(), graph, posts, marks=marks, steps=1, now=STAMP)
    assert len(walk["stations"]) == 2
    assert walk["stations"][1]["node_id"] != walk["stations"][0]["node_id"]
    assert walk["stations"][1]["perceptions"], "it perceived on arrival"


def test_an_intra_image_step_is_rendered_as_movement_within_one_picture():
    """THE HONEST TOUCH the depth lane earned. A step within one scene is a real move, and
    rendering it as a cross-image analogy would misdescribe what the agent did."""
    within = cognition.step_view({"from_node": "vm_pA:part", "to_node": "vm_pA:whole",
                                  "crossed_image": False})
    between = cognition.step_view({"from_node": "vm_pA:part", "to_node": "vm_pB:part",
                                   "crossed_image": True})
    assert within["kind"] == "within one picture" and within["crossed_image"] is False
    assert between["kind"] == "between pictures" and between["crossed_image"] is True


def test_a_perception_carries_the_organs_status_and_the_view_names_none_of_its_own():
    posts, graph, marks = _world()
    walk = cognition.walk(_agent(), graph, posts, marks=marks, steps=0, now=STAMP)
    rows = walk["stations"][0]["perceptions"]
    assert rows
    for row in rows:
        assert row["epistemic"] in {"measured", "interpretive", "uncertain", "visible"}
        assert row["basis"] in {"mask", "box"}
        assert row["expression"], "the organ's own sentence, not one composed here"


# ── 3. temperament biases the route, never the reading ───────────────────

def test_two_characters_at_one_locus_measure_identically_and_go_elsewhere():
    """THE BRIGHT LINE, as something you can look at. This is the claim a viewing surface is most
    likely to quietly break, because showing "what this character saw" is such a natural thing to
    build."""
    posts, _g, marks = _world()
    graph = _graph([
        _edge("e_analogy", "vm_pA:part", "vm_pB:part", ["pA", "pB"], _marks(posts)[0]["id"],
              axis="axis_nestedness", syst=0.6),
        _edge("e_depth", "vm_pA:part", "vm_pA:whole", ["pA"], _marks(posts)[0]["id"],
              axis="axis_occlusion", syst=0.0, relation="in_front_of"),
    ])
    walks = [cognition.walk(_agent(name), graph, posts, marks=marks, steps=1, now=STAMP)
             for name in ("depth_seeker", "analogy_seeker")]

    comparison = cognition.compare(walks)
    assert comparison["measurements_identical"] is True, \
        "temperament reached into an organ — the one thing it must never do"
    assert walks[0]["first_signature"] == walks[1]["first_signature"]


def test_the_signature_carries_nothing_about_who_measured_it():
    """Otherwise `measurements_identical` would be comparing agent ids and always be False."""
    posts, _g, _m = _world()
    a, b = _agent("depth_seeker"), _agent("analogy_seeker")
    for agent in (a, b):
        sa.perceive(agent, posts["pA"], now=STAMP)
    assert cognition.signature(a) == cognition.signature(b)
    assert not any("depth_seeker" in str(row) for row in cognition.signature(a))


def test_attention_order_cannot_smuggle_a_difference_into_the_signature():
    """`temperament.attend` reorders a field. The signature is sorted so that reordering — which is
    a real thing temperament does — cannot read as a different measurement."""
    posts, _g, _m = _world()
    agent = _agent("depth_seeker")
    sa.perceive(agent, posts["pA"], now=STAMP)
    before = cognition.signature(agent)
    agent.percept_field = list(reversed(tp.attend(agent.percept_field,
                                                  temperament="depth_seeker")))
    assert cognition.signature(agent) == before


def test_the_character_is_rendered_with_what_it_prefers():
    posts, graph, marks = _world()
    walk = cognition.walk(_agent("depth_seeker"), graph, posts, marks=marks, steps=0, now=STAMP)
    assert walk["temperament"] == "depth_seeker"
    assert walk["character"]["prefers"][0] == "axis_occlusion"
    assert "before moving between pictures" in walk["character"]["detail"]


def test_an_agent_with_no_temperament_renders_as_having_none():
    """NOT a hidden default character. An agent nobody gave a disposition falls through to the
    caller's policy, and the view says so rather than naming one."""
    posts, graph, marks = _world()
    walk = cognition.walk(_agent(), graph, posts, marks=marks, steps=0, now=STAMP)
    assert walk["temperament"] is None and walk["character"] is None


# ── 4. the route ─────────────────────────────────────────────────────────

def test_the_walk_view_is_json_safe_and_tallies_what_it_shows():
    import json

    posts, graph, marks = _world()
    walk = cognition.walk(_agent(), graph, posts, marks=marks, steps=1, now=STAMP)
    json.dumps(walk)                                   # raises if anything is not serialisable

    tally = walk["tally"]
    assert tally["stations"] == len(walk["stations"])
    assert tally["steps"] == len(walk["steps"])
    assert tally["within_one_picture"] + tally["between_pictures"] == tally["steps"]
    assert tally["refused"] == sum(len(s["horizon"]["refused"]) for s in walk["stations"])


def test_the_refusal_row_model_has_no_optional_reason():
    """The curator lane's serializer trap, one surface later: a field the handler never sets is
    filled from its default and rendered as though it were data. A refusal whose reason could
    default is the blank this lane exists to prevent."""
    from backend.routers.cognition import RefusalRow

    for required in ("reason", "about", "gloss", "to_node", "detail"):
        assert RefusalRow.model_fields[required].is_required(), \
            f"{required} may not have a default — that is how a refusal becomes a blank"


def test_the_routes_are_read_only():
    """Three reads, no writes. A persisted walk would be a second record of where an agent went
    that can disagree with its own trajectory."""
    from backend.routers import cognition as routes

    source = __import__("pathlib").Path(routes.__file__).read_text()
    for write in ("insert_one", "update_one", "replace_one", "delete_one", "bulk_write",
                  "find_one_and_update"):
        assert write not in source, f"the cognition routes call {write} — they must not"
    assert "@router.post" not in source and "@router.put" not in source


def test_an_undeclared_temperament_is_refused_rather_than_defaulted():
    from fastapi.testclient import TestClient

    from backend.main import app

    response = TestClient(app).get("/api/v1/cognition/walk",
                                   params={"post_id": "p", "temperament": "brave"})
    assert response.status_code == 400
    assert "no temperament named" in response.json()["detail"]
    assert "brave" in response.json()["detail"]


def test_the_temperaments_route_serves_the_declared_characters():
    from fastapi.testclient import TestClient

    from backend.main import app

    body = TestClient(app).get("/api/v1/cognition/temperaments").json()
    assert {c["name"] for c in body} == set(tp.TEMPERAMENTS)
    for row in body:
        assert row["prefers"] and row["detail"]
