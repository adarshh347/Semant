"""
WAVE3 — temperament: choosing by disposition, because the alternatives cannot be ranked.

Depth-movement gave an agent two ways to move whose scores are both in `[0,1]` and are not of the
same thing: a systematicity (a structure-map score) and a separation (an ordering statistic). Any
`max()` over both would invent a common currency. So the agent has a character instead, and the
character picks the KIND while the kind's own rule picks the move.

Two claims carry the lane, and they are the two this file exists for:

  1. **the incommensurable scores never meet** — `movement.select` is only ever handed entries
     sharing one axis, asserted by watching what it receives rather than by reading the code.
  2. **measurement is temperament-invariant** — two characters at one locus measuring one pair
     produce the identical reading. A temperament that changed a measurement would be an agent
     authoring its own evidence.

The rest is the honesty floor: no goals, legible fallback, attention that re-orders and never
filters, and no default character arriving by omission.
"""
import copy

import pytest

from backend.services import adjacency_organ, nestedness_organ, occlusion_organ
from backend.services.agents import movement as mv
from backend.services.agents import situated_agent as sa
from backend.services.agents import temperament as tp
from backend.services.epistemics import STATUS_KEY
from backend.services.movement_graph import movement_edge_entry

POST = "post_scene"
NOW = "2026-08-07T00:00:00Z"


def region(rid, x, y, w, h, *, mask=True):
    out = {"id": rid, "label": rid, "box": {"x": x, "y": y, "w": w, "h": h}}
    if mask:
        import numpy as np

        from backend.services import mask_geometry as mg
        bits = np.zeros((64, 64), np.uint8)
        bits[int(y * 64):int((y + h) * 64), int(x * 64):int((x + w) * 64)] = 1
        out["mask_rle"] = mg.rle_encode_mask(bits)
    return out


NEAR = region("near_part", 0.30, 0.30, 0.10, 0.10)
FRAME = region("frame", 0.05, 0.05, 0.90, 0.90)
SIBLING = region("sibling", 0.50, 0.50, 0.10, 0.10)
FAR = region("far_wall", 0.60, 0.10, 0.20, 0.20)
SCENE = {"_id": POST, "region_annotations": [NEAR, FRAME, SIBLING, FAR], "visual_marks": []}


def occlusion_mark(front, back, *, separation=0.99, mark_id=""):
    return {
        "id": mark_id or f"vm_occ_{front}_{back}", "type": "relation_mark",
        "relation": occlusion_organ.RELATION_IN_FRONT_OF, "axis": occlusion_organ.AXIS_OCCLUSION,
        "post_id": POST, "front_region_id": front, "back_region_id": back,
        "region_ids": [front, back], STATUS_KEY: "measured",
        "measurement": {"basis": "mask", "separation": separation, "separated": True},
        "provenance": {"producer": occlusion_organ.ORGAN, "model": "m", "revision": "r"},
        "at": NOW,
    }


def nesting_mark():
    return nestedness_organ.grounding_mark(nestedness_organ.measure(NEAR, FRAME), post_id=POST)


def edge(axis, source, target, *, mark_id, edge_id, systematicity=None):
    return movement_edge_entry(
        mark_id=mark_id, source_node=f"vm_{POST}:{source}", target_node=f"vm_{POST}:{target}",
        spans=[POST], axis_ref=axis, systematicity=systematicity, edge_id=edge_id, now=NOW)


def graph(*edges):
    return {"atlas_id": "a", "nodes": [], "edges": list(edges)}


def two_axis_world():
    """One locus affording BOTH kinds: a grounded analogy and a grounded depth step."""
    occ = occlusion_mark("near_part", "far_wall", separation=0.99)
    nest = nesting_mark()
    return graph(
        edge(occlusion_organ.AXIS_OCCLUSION, "near_part", "far_wall",
             mark_id=occ["id"], edge_id="e_occ"),
        edge(nestedness_organ.AXIS_NESTEDNESS, "near_part", "frame",
             mark_id=nest["id"], edge_id="e_nest", systematicity=0.62),
    ), [occ, nest]


def standing(temperament=tp.NO_TEMPERAMENT, region_id="near_part"):
    agent = sa.inhabit(agent_id=f"agent_{temperament or 'plain'}", post_id=POST,
                       region_id=region_id, organ_set=(nestedness_organ.ORGAN,),
                       temperament=temperament)
    sa.perceive(agent, SCENE, now=NOW)
    return agent


def horizon_for(agent):
    doc, marks = two_axis_world()
    return mv.horizon(agent, doc, {POST: SCENE}, proposed_marks=marks)


# ── 1. THE INCOMMENSURABLE SCORES NEVER MEET ─────────────────────────────────────────────────

def test_the_two_scores_are_never_put_on_one_scale(monkeypatch):
    """THE CLAIM THE LANE IS FOR, asserted by watching what the ranking function is handed.

    A systematicity of 0.62 and a depth separation of 0.99 are both in `[0,1]` and are not of the
    same thing. Reading the code and believing it would not be a test; this records every call and
    asserts each one saw exactly one axis.
    """
    seen = []
    real = mv.select

    def spy(entries, **kwargs):
        seen.append({str(r.axis_ref) for r in entries})
        return real(entries, **kwargs)

    monkeypatch.setattr(mv, "select", spy)
    monkeypatch.setattr(tp.mv, "select", spy)

    entries = horizon_for(standing("depth_seeker"))
    assert len({r.axis_ref for r in entries}) == 2, "the fixture must offer both kinds"

    tp.choose(entries, temperament="depth_seeker")
    assert seen and all(len(axes) == 1 for axes in seen), seen


def test_the_partition_is_by_axis_and_disjoint():
    """The structural guarantee behind the claim: every group shares a kind, so the only
    comparisons any rule makes are between two measurements of one quantity."""
    groups = tp.by_axis(horizon_for(standing("depth_seeker")))
    assert set(groups) == {occlusion_organ.AXIS_OCCLUSION, nestedness_organ.AXIS_NESTEDNESS}
    for axis, rows in groups.items():
        assert {str(r.axis_ref) for r in rows} == {axis}


def test_raising_a_depth_separation_cannot_steal_a_geometric_agents_move():
    """The behavioural form. If the two numbers were ever compared, a large enough separation would
    pull an analogy-seeker onto the depth axis. It cannot, at any value."""
    doc, marks = two_axis_world()
    agent = standing("analogy_seeker")
    quiet = tp.choose(mv.horizon(agent, doc, {POST: SCENE}, proposed_marks=marks),
                      temperament="analogy_seeker")

    loud = [m for m in marks]
    loud[0] = occlusion_mark("near_part", "far_wall", separation=1.0)
    agent2 = standing("analogy_seeker")
    shouted = tp.choose(mv.horizon(agent2, doc, {POST: SCENE}, proposed_marks=loud),
                        temperament="analogy_seeker")

    assert quiet["chose_kind"] == shouted["chose_kind"] == nestedness_organ.AXIS_NESTEDNESS


def test_lowering_a_systematicity_cannot_steal_a_depth_agents_move():
    """And the converse, so the guarantee is not one-sided."""
    occ = occlusion_mark("near_part", "far_wall")
    for systematicity in (0.99, 0.35):
        doc = graph(
            edge(occlusion_organ.AXIS_OCCLUSION, "near_part", "far_wall",
                 mark_id=occ["id"], edge_id="e_occ"),
            edge(nestedness_organ.AXIS_NESTEDNESS, "near_part", "frame",
                 mark_id=nesting_mark()["id"], edge_id="e_nest", systematicity=systematicity))
        agent = standing("depth_seeker")
        entries = mv.horizon(agent, doc, {POST: SCENE}, proposed_marks=[occ, nesting_mark()])
        chosen = tp.choose(entries, temperament="depth_seeker")
        assert chosen["chose_kind"] == occlusion_organ.AXIS_OCCLUSION


# ── 2. MEASUREMENT IS TEMPERAMENT-INVARIANT ──────────────────────────────────────────────────

def test_two_characters_at_one_locus_measure_the_same_world():
    """THE BRIGHT LINE. An organ measures the same thing whoever is looking. Two characters differ
    in where they GO, never in what is TRUE where they are."""
    depth_seeker = standing("depth_seeker")
    analogy_seeker = standing("analogy_seeker")

    def readings(agent):
        return sorted(
            (p.reading.direction, p.reading.other_region_id, p.reading.basis,
             p.reading.admissible, p.epistemic_status, p.reading.detail)
            for p in agent.percept_field)

    assert readings(depth_seeker) == readings(analogy_seeker)
    assert readings(depth_seeker) == readings(standing(tp.NO_TEMPERAMENT))


def test_the_module_imports_no_organ_and_so_cannot_measure_anything():
    """Structural, not aspirational. A character that could reach an organ could shade a reading,
    and the whole line would be a comment."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(tp.__file__).read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    for forbidden in ("organ", "depth_service", "movement_kernel", "structure_map", "retina"):
        assert not any(forbidden in name for name in imported), (forbidden, imported)


def test_attention_is_a_permutation_and_never_a_filter():
    """Attention is what an agent looks at FIRST, not what it is able to see. A character that
    dropped readings would be deciding what is true of a place, and two agents at one locus would
    then disagree about the world rather than about where to go next."""
    agent = standing("depth_seeker")
    ordered = tp.attend(agent.percept_field, temperament="depth_seeker")
    assert len(ordered) == len(agent.percept_field)
    assert {id(p) for p in ordered} == {id(p) for p in agent.percept_field}


def test_attention_does_not_touch_a_reading():
    agent = standing("depth_seeker")
    before = copy.deepcopy([p.as_dict() for p in agent.percept_field])
    tp.attend(agent.percept_field, temperament="analogy_seeker")
    assert [p.as_dict() for p in agent.percept_field] == before


def test_an_agent_with_no_character_has_its_field_left_alone():
    agent = standing(tp.NO_TEMPERAMENT)
    assert tp.attend(agent.percept_field) == list(agent.percept_field)


# ── 3. no goals ──────────────────────────────────────────────────────────────────────────────

def test_a_temperament_that_names_a_destination_is_refused():
    """A bias over kinds is a way of being; a target is a want, and a want is something to
    confabulate a justification for. The line is not a matter of degree."""
    with pytest.raises(ValueError):
        tp.assert_no_destination({"name": "seeker", "destination": "vm_post:region"})
    with pytest.raises(ValueError):
        tp.assert_no_destination({"name": "seeker", "goal_node_id": "vm_post:region"})


def test_every_declared_temperament_names_only_kinds():
    """The ones this lane ships, held to their own rule."""
    known = {tp.AXIS_NESTEDNESS, tp.AXIS_ADJACENCY, tp.AXIS_OCCLUSION}
    for character in tp.TEMPERAMENTS.values():
        tp.assert_no_destination(character.as_dict())
        assert set(character.prefers) <= known
        assert len(set(character.prefers)) == len(character.prefers)


def test_a_temperament_is_an_order_and_not_a_score():
    """There is no quantity being maximised across kinds — which is what leaves nothing for an
    incommensurable comparison to hide inside."""
    for character in tp.TEMPERAMENTS.values():
        assert isinstance(character.prefers, tuple)
        assert all(isinstance(axis, str) for axis in character.prefers)


# ── 4. declared, legible, and no default character by omission ───────────────────────────────

def test_an_undeclared_character_raises_rather_than_defaulting():
    with pytest.raises(tp.UnknownTemperament):
        tp.resolve("whatever_feels_right")


def test_an_agent_with_no_temperament_behaves_exactly_as_before():
    """NOT a hidden default character. An agent given no disposition falls straight through to the
    caller's policy — what every agent did before this module existed."""
    entries = horizon_for(standing(tp.NO_TEMPERAMENT))
    chosen = tp.choose(entries, temperament=tp.NO_TEMPERAMENT, policy=mv.POLICY_SYSTEMATICITY)
    assert chosen["temperament"] == tp.NO_TEMPERAMENT
    assert chosen["reach"] is mv.select(entries, policy=mv.POLICY_SYSTEMATICITY)


def test_the_choice_records_the_disposition_it_was_made_by():
    chosen = tp.choose(horizon_for(standing("depth_seeker")), temperament="depth_seeker")
    assert chosen["temperament"] == "depth_seeker"
    assert chosen["prefers"][0] == occlusion_organ.AXIS_OCCLUSION
    assert chosen["policy"] == mv.POLICY_ORDERING
    assert "depth_seeker prefers" in chosen["reason"]


def test_the_fallback_is_legible_and_never_invents_the_preferred_kind():
    """A depth-seeker where nothing depth-wise is reachable takes an analogy step and SAYS so."""
    nest = nesting_mark()
    doc = graph(edge(nestedness_organ.AXIS_NESTEDNESS, "near_part", "frame",
                     mark_id=nest["id"], edge_id="e_nest", systematicity=0.62))
    agent = standing("depth_seeker")
    entries = mv.horizon(agent, doc, {POST: SCENE}, proposed_marks=[nest])

    chosen = tp.choose(entries, temperament="depth_seeker")
    assert chosen["chose_kind"] == nestedness_organ.AXIS_NESTEDNESS
    assert chosen["fell_back"] is True
    assert chosen["preferred"] == occlusion_organ.AXIS_OCCLUSION
    assert occlusion_organ.AXIS_OCCLUSION in chosen["unmet"]
    assert "nothing along it is reachable" in chosen["reason"]


def test_nothing_reachable_is_a_stated_outcome_rather_than_a_crash():
    chosen = tp.choose([], temperament="depth_seeker")
    assert chosen["reach"] is None and chosen["available"] == {}
    assert "nothing reachable" in chosen["reason"]


def test_an_unreachable_move_is_never_chosen_by_any_character():
    """The ruling is upstream of the character: a box-basis crossing is refused before any
    disposition is consulted."""
    boxy = occlusion_mark("near_part", "far_wall")
    boxy["measurement"]["basis"] = "box"
    boxy[STATUS_KEY] = "interpretive"
    doc = graph(edge(occlusion_organ.AXIS_OCCLUSION, "near_part", "far_wall",
                     mark_id=boxy["id"], edge_id="e_occ"))
    agent = standing("depth_seeker")
    entries = mv.horizon(agent, doc, {POST: SCENE}, proposed_marks=[boxy])

    assert entries and not entries[0].reachable
    assert tp.choose(entries, temperament="depth_seeker")["reach"] is None


# ── 5. divergence: the demonstration, as a unit ──────────────────────────────────────────────

def test_two_characters_at_one_locus_take_different_kinds_of_move():
    """THE LANE'S DEMONSTRATION. Identical start, identical world, identical measurements — and
    they go different ways, by disposition alone."""
    entries = horizon_for(standing("depth_seeker"))

    depth = tp.choose(entries, temperament="depth_seeker")
    analogy = tp.choose(entries, temperament="analogy_seeker")

    assert depth["chose_kind"] == occlusion_organ.AXIS_OCCLUSION
    assert analogy["chose_kind"] == nestedness_organ.AXIS_NESTEDNESS
    assert depth["reach"].other_node != analogy["reach"].other_node
    assert depth["fell_back"] is False and analogy["fell_back"] is False


def test_the_axis_names_have_not_drifted_from_the_organs():
    """The names are mirrored rather than imported, so a relation-grounding capability stays out of
    the layer that decides where an agent goes. This is the guard that makes that safe."""
    assert tp.AXIS_NESTEDNESS == nestedness_organ.AXIS_NESTEDNESS
    assert tp.AXIS_OCCLUSION == occlusion_organ.AXIS_OCCLUSION
    assert tp.AXIS_ADJACENCY == adjacency_organ.AXIS_ADJACENCY
    # Every relation an organ can emit must map to the kind it belongs to, or an agent's attention
    # would sort readings it cannot place to the back for no stated reason.
    assert tp._RELATION_AXIS[occlusion_organ.RELATION_IN_FRONT_OF] == tp.AXIS_OCCLUSION
    assert tp._RELATION_AXIS[nestedness_organ.RELATION_NESTED_WITHIN] == tp.AXIS_NESTEDNESS
    assert tp._RELATION_AXIS[adjacency_organ.RELATION_MEETS] == tp.AXIS_ADJACENCY


def test_every_kind_has_a_rule_and_an_unknown_kind_falls_back_statedly():
    for axis in (tp.AXIS_NESTEDNESS, tp.AXIS_ADJACENCY, tp.AXIS_OCCLUSION):
        assert tp.RULE_FOR_AXIS[axis] in mv.POLICIES
    assert tp.RULE_FOR_AXIS.get("axis_nobody_declared", tp.DEFAULT_RULE) == tp.DEFAULT_RULE
