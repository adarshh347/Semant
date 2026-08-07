"""
WAVE3 — the depth axis as a way to move: an agent steps to what is in front of where it stands.

Every crossing an agent had walked until now went BETWEEN images — two pictures stitched by an
analogy the kernel grounded. `in_front_of` is a fact about ONE scene, so a depth step moves the
agent **within** a picture. That is the first dimension of Semant's walked space that is not
geometry-by-analogy, and most of what is pinned here is the consequences of that difference.

  1. **a mark's ends, whatever it calls them.** Containment names an `inner`/`outer`; occlusion
     names a `front`/`back`. The reachability check has to read both without widening into "any
     mark will do" — it still demands that the mark name an end of this very crossing.
  2. **the depth axis needs its own rule.** An occlusion edge carries no systematicity, so under
     the default policy it scores 0.0 and an agent would never take a depth step while any
     geometric edge was reachable. That is incommensurability, not a bug, and the fix is a named
     rule rather than a default.
  3. **the ruling holds on the new axis.** Box-basis occlusion is visible-and-unreachable, and the
     agent's own footing is checked before the road ahead is consulted.
  4. **arrival is still empty**, and the trajectory says which KIND of crossing it was.

The corpus walk lives in `scripts/depth_movement_run.py`; it needs Mongo and the depth model.
"""
import asyncio

import pytest

from backend.services import nestedness_organ as nestedness
from backend.services import occlusion_organ as occlusion
from backend.services.agents import movement as mv
from backend.services.agents import situated_agent as sa
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


def post_with(*regions, marks=()):
    return {"_id": POST, "region_annotations": list(regions), "visual_marks": list(marks)}


def occlusion_mark(front, back, *, basis="mask", separation=0.99, status=None):
    """An occlusion organ mark, in the shape `occlusion_organ.grounding_mark` produces."""
    return {
        "id": f"vm_occ_{front}_{back}", "type": "relation_mark",
        "relation": occlusion.RELATION_IN_FRONT_OF, "axis": occlusion.AXIS_OCCLUSION,
        "post_id": POST, "front_region_id": front, "back_region_id": back,
        "region_ids": [front, back],
        STATUS_KEY: status or occlusion.epistemic_for(basis),
        "measurement": {"basis": basis, "separation": separation, "dominance": separation,
                        "separated": True},
        "provenance": {"producer": occlusion.ORGAN, "producer_version": 1,
                       "model": "Depth-Anything-V2-Small-hf", "revision": "abc"},
        "at": NOW,
    }


def occlusion_edge(front, back, *, mark_id, edge_id="edge_occ_1"):
    return movement_edge_entry(
        mark_id=mark_id, source_node=f"vm_{POST}:{front}", target_node=f"vm_{POST}:{back}",
        spans=[POST], axis_ref=occlusion.AXIS_OCCLUSION, systematicity=None,
        edge_id=edge_id, now=NOW)


def graph(*edges):
    return {"atlas_id": "a", "nodes": [], "edges": list(edges)}


#: A scene: a near part inside a frame, so the agent has mask-basis nestedness footing where it
#: stands, and something else in the picture for it to be in front of.
NEAR = region("near_part", 0.30, 0.30, 0.10, 0.10)
FRAME = region("frame", 0.05, 0.05, 0.90, 0.90)
SIBLING = region("sibling", 0.50, 0.50, 0.10, 0.10)
FAR = region("far_wall", 0.60, 0.10, 0.20, 0.20)
BOXY = region("fine_0", 0.70, 0.70, 0.10, 0.10, mask=False)

SCENE = post_with(NEAR, FRAME, SIBLING, FAR, BOXY)


def standing_agent(region_id="near_part", post=None):
    """An agent that has looked, so it has footing — the near half of the ruling."""
    agent = sa.inhabit(agent_id="agent_alpha", post_id=POST, region_id=region_id,
                       organ_set=(nestedness.ORGAN,))
    sa.perceive(agent, post or SCENE, now=NOW)
    return agent


# ── 1. a mark's ends, whatever vocabulary it uses ────────────────────────────────────────────

def test_an_occlusion_marks_ends_are_read_though_it_names_them_differently():
    """Containment has an `inner`/`outer`; occlusion has a `front`/`back`. Neither name would be
    honest for the other — a thing in front of another is not inside it, which is the whole subject
    of the occlusion lane — so the reachability check reads the vocabulary the mark actually uses."""
    mark = occlusion_mark("near_part", "far_wall")
    nodes = mv.measured_nodes(mark)
    assert nodes == {f"vm_{POST}:near_part", f"vm_{POST}:far_wall"}


def test_a_containment_marks_ends_are_still_read():
    """The generalisation must not lose the case it started from."""
    measurement = nestedness.measure(NEAR, FRAME)
    mark = nestedness.grounding_mark(measurement, post_id=POST, step_id="s")
    assert f"vm_{POST}:near_part" in mv.measured_nodes(mark)


def test_widening_the_vocabulary_did_not_widen_the_test():
    """THE CHECK THAT IS EASY TO LOSE. Every other property of a misapplied mark is impeccable:
    well-formed, mask-basis, honestly stamped, and about a different pair. A mark measuring two
    regions this crossing does not touch is still not evidence about it."""
    elsewhere = occlusion_mark("sibling", "far_wall")
    edge = occlusion_edge("near_part", "frame", mark_id=elsewhere["id"])
    agent = standing_agent()
    entries = mv.horizon(agent, graph(edge), {POST: SCENE}, proposed_marks=[elsewhere])
    assert [r.reason for r in entries] == [mv.UNREACHABLE_ELSEWHERE]


def test_a_mark_naming_no_regions_at_all_measures_nothing():
    assert mv.measured_nodes({"post_id": POST, "measurement": {}}) == set()
    assert mv.measured_nodes(None) == set()


# ── 2. the depth axis needs its own rule ─────────────────────────────────────────────────────

def test_an_occlusion_edge_carries_no_systematicity():
    """An occlusion is not an analogy. A structure-map score here would invite a comparison with
    the geometric axis that nothing licenses."""
    edge = occlusion_edge("near_part", "far_wall", mark_id="m")
    assert edge["systematicity"] is None


def test_the_default_policy_would_never_take_a_depth_step():
    """The incommensurability, as a test rather than a warning. Under `strongest_systematicity` an
    occlusion edge scores 0.0, so any geometric edge outranks it — which is why the depth axis gets
    a named rule instead of a quiet default."""
    mark = occlusion_mark("near_part", "far_wall")
    depth_edge = occlusion_edge("near_part", "far_wall", mark_id=mark["id"], edge_id="edge_occ")
    nesting_mark = nestedness.grounding_mark(nestedness.measure(NEAR, FRAME), post_id=POST)
    nesting_edge = movement_edge_entry(
        mark_id=nesting_mark["id"], source_node=f"vm_{POST}:near_part",
        target_node=f"vm_{POST}:frame", spans=[POST], axis_ref=nestedness.AXIS_NESTEDNESS,
        systematicity=0.6, edge_id="edge_nest", now=NOW)

    agent = standing_agent()
    entries = mv.horizon(agent, graph(depth_edge, nesting_edge), {POST: SCENE},
                         proposed_marks=[mark, nesting_mark])
    assert all(r.reachable for r in entries)

    by_systematicity = mv.select(entries, policy=mv.POLICY_SYSTEMATICITY)
    assert by_systematicity.axis_ref == nestedness.AXIS_NESTEDNESS

    by_ordering = mv.select(entries, policy=mv.POLICY_ORDERING)
    assert by_ordering.axis_ref == occlusion.AXIS_OCCLUSION


def test_the_ordering_policy_reads_the_measurement_and_not_a_preference():
    """Like the other two rules it is a property of the GRAPH — it consults no label, no embedding
    and no history of where this agent has been."""
    close = occlusion_mark("near_part", "sibling", separation=0.96)
    close["id"] = "vm_occ_close"
    clear = occlusion_mark("near_part", "far_wall", separation=0.999)
    clear["id"] = "vm_occ_clear"
    agent = standing_agent()
    entries = mv.horizon(
        agent,
        graph(occlusion_edge("near_part", "sibling", mark_id=close["id"], edge_id="e1"),
              occlusion_edge("near_part", "far_wall", mark_id=clear["id"], edge_id="e2")),
        {POST: SCENE}, proposed_marks=[close, clear])
    assert mv.select(entries, policy=mv.POLICY_ORDERING).other_node == f"vm_{POST}:far_wall"


def test_a_geometric_crossing_reports_no_ordering_rather_than_zero():
    """A containment does not order its ends, and a 0.0 here would read as one that orders them
    badly. `None` says the question was not asked."""
    mark = nestedness.grounding_mark(nestedness.measure(NEAR, FRAME), post_id=POST)
    edge = movement_edge_entry(
        mark_id=mark["id"], source_node=f"vm_{POST}:near_part", target_node=f"vm_{POST}:frame",
        spans=[POST], axis_ref=nestedness.AXIS_NESTEDNESS, systematicity=0.6, edge_id="e", now=NOW)
    agent = standing_agent()
    row = mv.horizon(agent, graph(edge), {POST: SCENE}, proposed_marks=[mark])[0]
    assert row.ordering == 0.0
    assert row.as_dict()["ordering"] is None
    assert row.as_dict()["relation"] == nestedness.RELATION_NESTED_WITHIN


def test_the_policy_is_a_value_a_reader_can_look_up():
    assert mv.POLICY_ORDERING in mv.POLICIES
    assert "depth axis" in mv.POLICIES[mv.POLICY_ORDERING]


# ── 3. the ruling holds on the new axis ──────────────────────────────────────────────────────

def test_a_box_basis_occlusion_is_visible_and_unreachable():
    """The WAVE2.5 ruling on the depth axis. A box's depth is the mean of a thing and the thing
    behind it, so an occlusion read off boxes is the pathology offered as evidence for itself —
    and the occlusion lane measured it losing the ordering outright (0.9987 → 0.7773)."""
    mark = occlusion_mark("near_part", "fine_0", basis="box")
    edge = occlusion_edge("near_part", "fine_0", mark_id=mark["id"])
    agent = standing_agent()
    row = mv.horizon(agent, graph(edge), {POST: SCENE}, proposed_marks=[mark])[0]

    assert row.reachable is False
    assert row.reason == mv.UNREACHABLE_INTERPRETIVE
    with pytest.raises(mv.Unreachable):
        mv.step(agent, row, policy=mv.POLICY_ORDERING, now=NOW)


def test_an_occlusion_mark_stamped_above_its_basis_is_refused():
    """Per MEASUREMENT, not per producer: a box mark wearing `measured` is the projection artefact
    in the strongest word the vocabulary has."""
    mark = occlusion_mark("near_part", "fine_0", basis="box", status="measured")
    edge = occlusion_edge("near_part", "fine_0", mark_id=mark["id"])
    agent = standing_agent()
    row = mv.horizon(agent, graph(edge), {POST: SCENE}, proposed_marks=[mark])[0]
    assert row.reason == mv.UNREACHABLE_MISSTATED


def test_an_agent_on_box_footing_may_not_take_a_depth_step_either():
    """The NEAR half of the ruling, checked before the road ahead is consulted. On the real corpus
    this is why `cseg_golden_finial_7` — the occlusion lane's own subject — cannot be a starting
    point: every nestedness reading from that locus is an estimate."""
    boxy_scene = post_with(BOXY, region("frame2", 0.05, 0.05, 0.9, 0.9, mask=False))
    agent = sa.inhabit(agent_id="a", post_id=POST, region_id="fine_0",
                       organ_set=(nestedness.ORGAN,))
    sa.perceive(agent, boxy_scene, now=NOW)

    mark = occlusion_mark("fine_0", "frame2")
    row = mv.horizon(agent, graph(occlusion_edge("fine_0", "frame2", mark_id=mark["id"])),
                     {POST: boxy_scene}, proposed_marks=[mark])[0]
    assert row.reachable is True                    # the road is fine
    with pytest.raises(mv.Unreachable) as excinfo:  # the traveller is not
        mv.step(agent, row, policy=mv.POLICY_ORDERING, now=NOW)
    assert mv.UNFOOTED_BOX in str(excinfo.value)


# ── 4. the step itself, and what it records ──────────────────────────────────────────────────

def test_a_depth_step_does_not_leave_the_picture():
    """THE NEW TOPOLOGICAL FACT. Every crossing before this one went between images; this one
    moves the agent through a scene. `crossed_image` was always computed rather than assumed,
    which is why it can say so."""
    mark = occlusion_mark("near_part", "far_wall")
    agent = standing_agent()
    row = mv.horizon(agent, graph(occlusion_edge("near_part", "far_wall", mark_id=mark["id"])),
                     {POST: SCENE}, proposed_marks=[mark])[0]

    entry = mv.step(agent, row, policy=mv.POLICY_ORDERING, now=NOW)
    assert entry["crossed_image"] is False
    assert entry["to_node"] == f"vm_{POST}:far_wall"
    assert agent.locus.post_id == POST and agent.locus.region_id == "far_wall"


def test_the_step_records_which_kind_of_crossing_it_was():
    """A depth step and an analogy step are both steps and they are not the same event. The
    trajectory says which, off the mark rather than by this lane's own assertion."""
    mark = occlusion_mark("near_part", "far_wall", separation=0.987)
    agent = standing_agent()
    row = mv.horizon(agent, graph(occlusion_edge("near_part", "far_wall", mark_id=mark["id"])),
                     {POST: SCENE}, proposed_marks=[mark])[0]
    entry = mv.step(agent, row, policy=mv.POLICY_ORDERING, now=NOW)

    assert entry["axis_ref"] == occlusion.AXIS_OCCLUSION
    assert entry["relation"] == occlusion.RELATION_IN_FRONT_OF
    assert entry["ordering"] == 0.987
    assert entry[STATUS_KEY] == "measured"          # copied off the mark, never named here
    assert entry["ledger_status"] == "proposed"     # and the other reading, on the same row
    assert entry["mark_id"] == mark["id"]


def test_the_agent_still_arrives_knowing_nothing():
    """No narrated arrival, on the new axis too. An agent that kept its field would arrive holding
    sentences about the place it just left, wearing the new locus's name — and on THIS axis it
    would be sentences about the same picture, which is exactly when nobody would notice."""
    mark = occlusion_mark("near_part", "far_wall")
    agent = standing_agent()
    assert agent.percept_field
    row = mv.horizon(agent, graph(occlusion_edge("near_part", "far_wall", mark_id=mark["id"])),
                     {POST: SCENE}, proposed_marks=[mark])[0]
    mv.step(agent, row, policy=mv.POLICY_ORDERING, now=NOW)
    assert agent.percept_field == []
    assert agent.horizon == []


def test_the_walk_is_legible_as_a_depth_walk():
    """The constellation reads as one image and several loci — a shape no previous walk could
    produce, because every crossing before this one changed the picture."""
    mark = occlusion_mark("near_part", "far_wall")
    agent = standing_agent()
    row = mv.horizon(agent, graph(occlusion_edge("near_part", "far_wall", mark_id=mark["id"])),
                     {POST: SCENE}, proposed_marks=[mark])[0]
    mv.step(agent, row, policy=mv.POLICY_ORDERING, now=NOW)
    sa.perceive(agent, SCENE, now=NOW)
    sa.remember(agent, now=NOW)

    constellation = mv.constellation(agent)
    assert constellation["posts"] == [POST]
    assert len(constellation["steps"]) == 1
    assert occlusion.AXIS_OCCLUSION in constellation["legible"]


def test_the_movement_module_still_cannot_ground_its_own_crossings():
    """The line the whole package is built on, re-checked now that a second relation feeds it.
    `movement.py` may read an occlusion mark and may not produce one — an agent that grounded its
    own crossings would author the world it then reports having found in."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(mv.__file__).read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    for forbidden in ("movement_kernel", "structure_map", "occlusion_organ", "depth_organ",
                      "depth_service"):
        assert not any(forbidden in name for name in imported), forbidden


def test_the_run_script_plays_the_writers_part_and_the_agent_does_not():
    """The division of labour, asserted where it could rot: the script mints edges and marks, and
    the module it hands them to imports nothing that could."""
    import ast
    import pathlib

    script = pathlib.Path(mv.__file__).parents[3] / "scripts" / "depth_movement_run.py"
    tree = ast.parse(script.read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                 for a in n.names}
    assert any("occlusion_organ" in name for name in imported)
    assert any("movement_graph" in name for name in imported)


def test_asyncio_is_not_needed_to_walk():
    """The horizon and the step are pure. Only fetching posts and running the model is async, and
    neither belongs to the agent."""
    assert not asyncio.iscoroutinefunction(mv.horizon)
    assert not asyncio.iscoroutinefunction(mv.step)
