"""WAVE4 — the constellation: the four ways a graph view would draw a world that is not there.

A node-link diagram is the most persuasive thing this system can render — a line between two dots
reads as a fact, and nobody checks a line. Each of these guards a claim that would still produce a
convincing picture if it failed:

  1. ONLY PERSISTED RELATIONS ARE EDGES. A candidate the kernel refused was never written down, so
     it cannot appear — and the guard is that this module reads three named sources and nothing
     else, not that it filters. §1.
  2. WITHIN-IMAGE AND BETWEEN-IMAGE ARE DIFFERENT KINDS. `span` is DERIVED from the endpoints, so a
     caller cannot declare an occlusion a crossing. #169 made that distinction real; a view that
     blurred it would draw moves no agent can make. §2.
  3. THE BOUND IS PART OF THE ANSWER. A neighbourhood of six nodes is a claim about how far this
     walked. §3.
  4. STATUS IS DERIVED, NEVER DEFAULTED. `epistemic` off the mark, `ledger_status` off the ledger,
     and `None` means "cannot tell you" rather than `uncertain`. §4.
"""
from __future__ import annotations

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import constellation as C
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

STAMP = "2026-08-07T00:00:00+00:00"


# ── fakes ───────────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, _n):
        return self

    def __aiter__(self):
        async def _gen():
            for doc in self._docs:
                yield doc
        return _gen()


class FakeCollection:
    def __init__(self, docs=()):
        self.docs = {i: copy.deepcopy(d) for i, d in enumerate(docs)}

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values()])

    async def find_one(self, query, projection=None):
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in (query or {}).items()):
                return copy.deepcopy(doc)
        return None


def _post(post_id, *, marks=(), regions=()):
    return {"_id": post_id, "visual_marks": list(marks),
            "region_annotations": [{"id": r, "label": f"{r}-label"} for r in regions]}


def _proposal(pid, post_id, front, back, *, committed=False, epistemic="measured"):
    return {
        "proposal_id": pid, "kind": "occlusion_supersedes_containment",
        "producer": "occlusion_organ", "post_id": post_id,
        "mark_id": f"vm_occ_{pid}",
        "mark": {"id": f"vm_occ_{pid}", "type": "relation_mark", "role": "in_front_of",
                 "axis": "axis_occlusion", STATUS_KEY: epistemic},
        "subject": {"front_region_id": front, "back_region_id": back,
                    "claim": f"{front} is IN FRONT OF {back}"},
        "evidence": {"ordering_separation": 0.98, "separation_floor": 0.95,
                     "depth_grid": 192, "basis": "mask",
                     "contradicts": {"relation": "nested_within", "containment": 0.98}},
        "committed_at": STAMP if committed else None,
        "committed_by": "adarsh" if committed else None,
    }


def _atlas(edge_id, a_post, a_region, b_post, b_region, *, mark_id="vm_nest_x"):
    return {"_id": "atlas_1", "edges": [{
        "edge_id": edge_id, "kind": "movement", "mark_id": mark_id,
        "source_node": C.node_id_for(a_post, a_region),
        "target_node": C.node_id_for(b_post, b_region),
        "spans": [a_post, b_post], "axis_ref": "axis_nestedness",
        "systematicity": 0.6, "weight": 0.25,
    }]}


# ── 1. only persisted relations are edges ──────────────────────────────────

def test_the_view_reads_the_one_store_rather_than_naming_its_own_sources():
    """WAVE4.5 MOVED THIS GUARD, and the move is the lane.

    This function used to read three sources itself and was asserted to read exactly those three.
    It now reads `derived_relations`, the one home — so the guard that matters ("a refused
    candidate has nowhere to come from") belongs on the store, and is asserted there. What is left
    to check here is that this view no longer holds its own opinion about where relations live.
    """
    import inspect
    body = inspect.getsource(C.load_edges)
    assert "derived_relations" in body
    for named_here in ("edges_from_ledger", "edges_from_proposals", "edges_from_atlas"):
        assert named_here not in body, f"{named_here} — the view is naming a source again"
    for absent in ("retina", "propose_candidates", "run_kernel", "structure_map"):
        assert absent not in body, absent


def test_a_filed_proposal_is_an_edge_and_carries_its_evidence():
    edges = C.edges_from_proposals([_proposal("p1", "pA", "r_part", "r_whole")])
    assert len(edges) == 1
    edge = edges[0]
    assert edge["relation"] == "in_front_of" and edge["source"] == C.SOURCE_PROPOSAL
    assert edge["ledger_status"] == C.LEDGER_PROPOSED
    assert edge["evidence"]["ordering_separation"] == 0.98
    assert edge["evidence"]["depth_grid"] == 192


def test_a_committed_proposal_reads_committed():
    edges = C.edges_from_proposals([_proposal("p1", "pA", "r_part", "r_whole", committed=True)])
    assert edges[0]["ledger_status"] == C.LEDGER_COMMITTED


def test_a_proposal_missing_its_subject_is_dropped_rather_than_half_drawn():
    """A line with one end is not a relation. Better absent than drawn to nowhere."""
    broken = _proposal("p1", "pA", "", "r_whole")
    assert C.edges_from_proposals([broken]) == []


def test_the_view_writes_nothing():
    """Read-only, structurally: no write path exists in either module to misuse."""
    from pathlib import Path

    import backend.routers.constellation as R
    for module in (C, R):
        source = Path(module.__file__).read_text()
        for writer in ("insert_one", "update_one", "delete_one", "$push", "$set",
                       "commit_relation_to_posts"):
            assert writer not in source, f"{writer} in {module.__name__}"


# ── 2. within-image and between-image are different kinds ──────────────────

def test_span_is_derived_from_the_endpoints_and_not_passed_in():
    """#169 made the distinction real: an occlusion moves THROUGH a picture, a nesting BETWEEN
    them. A caller able to declare an occlusion a crossing could draw a move no agent can make."""
    within = C.edges_from_proposals([_proposal("p1", "pA", "r_part", "r_whole")])[0]
    assert within["span"] == C.SPAN_WITHIN

    across = C.edges_from_atlas([_atlas("e1", "pA", "r_a", "pB", "r_b")], {})[0]
    assert across["span"] == C.SPAN_BETWEEN

    import inspect
    assert "span" not in inspect.signature(C._edge).parameters


def test_an_occlusion_is_directed_and_a_nesting_edge_is_not():
    """`in_front_of` has a near end; the stored movement edge does not orient a traversal. A
    renderer drawing an arrow needs to know which, and guessing would invent a direction."""
    within = C.edges_from_proposals([_proposal("p1", "pA", "r_part", "r_whole")])[0]
    assert within["directed"] is True
    assert within["front_node"] == C.node_id_for("pA", "r_part")

    across = C.edges_from_atlas([_atlas("e1", "pA", "r_a", "pB", "r_b")], {})[0]
    assert across["directed"] is False and across["front_node"] == ""


def test_the_tally_keeps_the_two_spans_apart():
    """One 'edges: 6' would hide the distinction the whole view is for."""
    edges = [
        *C.edges_from_proposals([_proposal("p1", "pA", "r1", "r0"),
                                 _proposal("p2", "pA", "r2", "r0")]),
        *C.edges_from_atlas([_atlas("e1", "pA", "r0", "pB", "rB")], {}),
    ]
    walk = C.reach(C.node_id_for("pA", "r0"), edges, depth=2)
    assert walk["tally"]["by_span"] == {C.SPAN_WITHIN: 2, C.SPAN_BETWEEN: 1}
    assert walk["tally"]["images"] == 2


# ── 3. the bound is part of the answer ─────────────────────────────────────

def test_the_walk_stops_at_its_depth_and_records_the_hop_of_every_node():
    chain = [
        *C.edges_from_proposals([_proposal("p1", "pA", "r1", "r0"),
                                 _proposal("p2", "pA", "r2", "r1"),
                                 _proposal("p3", "pA", "r3", "r2")]),
    ]
    seed = C.node_id_for("pA", "r0")
    one = C.reach(seed, chain, depth=1)
    assert {n["region_id"] for n in one["nodes"]} == {"r0", "r1"}
    two = C.reach(seed, chain, depth=2)
    assert {n["region_id"] for n in two["nodes"]} == {"r0", "r1", "r2"}
    assert {n["region_id"]: n["hop"] for n in two["nodes"]}["r2"] == 2


def test_the_bound_is_stated_on_the_result_and_not_only_in_the_parameter():
    walk = C.reach("vm_pA:r0", [], depth=2)
    assert walk["depth"] == 2
    assert "2 hop(s)" in walk["bound_detail"]
    assert "never written down" in walk["bound_detail"]


def test_the_depth_is_clamped_rather_than_honoured_without_limit():
    """A full-graph hairball is not legible, which is the card's own reasoning. The ceiling means a
    caller cannot ask for one by accident."""
    assert C.reach("vm_pA:r0", [], depth=99)["depth"] == C.MAX_DEPTH
    assert C.reach("vm_pA:r0", [], depth=-3)["depth"] == 0


def test_edges_between_already_reached_nodes_are_kept():
    """Without them a neighbourhood renders as a tree and reads as sparser than it is."""
    edges = C.edges_from_proposals([
        _proposal("p1", "pA", "r1", "r0"),
        _proposal("p2", "pA", "r2", "r0"),
        _proposal("p3", "pA", "r2", "r1"),   # closes the triangle; not needed to reach anything
    ])
    walk = C.reach(C.node_id_for("pA", "r0"), edges, depth=1)
    assert len(walk["edges"]) == 3


def test_a_locus_with_nothing_persisted_is_a_lone_node_and_says_so():
    walk = C.reach("vm_pA:r_alone", [], depth=2)
    assert [n["node_id"] for n in walk["nodes"]] == ["vm_pA:r_alone"]
    assert walk["edges"] == [] and walk["tally"]["edges"] == 0


# ── 4. status is derived, never defaulted ──────────────────────────────────

def test_an_atlas_edge_whose_mark_is_in_no_ledger_cannot_say_what_it_knows():
    """THE THIRD STATE. `None` is not `uncertain` — that is a producer's word for a claim it
    declines to vouch for, and this is an edge with nothing to read a status off at all."""
    edge = C.edges_from_atlas([_atlas("e1", "pA", "r_a", "pB", "r_b")], {})[0]
    assert edge["epistemic"] is None
    assert edge["ledger_status"] == C.LEDGER_PROPOSED
    assert "cannot say what kind of knowing" in edge["detail"]


def test_an_atlas_edge_reads_its_marks_status_once_that_mark_is_committed():
    mark = {"id": "vm_nest_x", STATUS_KEY: EpistemicStatus.MEASURED.value,
            "measurement": {"basis": "mask"}}
    posts = {"pA": _post("pA", marks=[mark]), "pB": _post("pB")}
    edge = C.edges_from_atlas([_atlas("e1", "pA", "r_a", "pB", "r_b")], posts)[0]
    assert edge["epistemic"] == EpistemicStatus.MEASURED.value
    assert edge["ledger_status"] == C.LEDGER_COMMITTED
    assert edge["basis"] == "mask"


def test_a_committed_relation_mark_on_a_post_becomes_an_edge():
    """Empty on the corpus today, and the path exists so the first curator commit appears here
    without another lane."""
    mark = {"id": "vm_occ_1", "type": "relation_mark", "role": "in_front_of",
            STATUS_KEY: EpistemicStatus.MEASURED.value,
            "measurement": {"front_region_id": "r_part", "back_region_id": "r_whole",
                            "basis": "mask", "axis": "axis_occlusion"},
            "provenance": {"committed_by": "adarsh"}}
    edges = C.edges_from_ledger({"pA": _post("pA", marks=[mark])})
    assert len(edges) == 1
    assert edges[0]["source"] == C.SOURCE_LEDGER
    assert edges[0]["ledger_status"] == C.LEDGER_COMMITTED
    assert edges[0]["span"] == C.SPAN_WITHIN and edges[0]["directed"] is True


def test_a_non_relation_mark_is_not_an_edge():
    """`region_mask` and `field_mark` relate nothing. Three of them sit on this corpus today."""
    for kind in ("region_mask", "field_mark"):
        mark = {"id": "m", "type": kind, "measurement": {"region_id": "r"}}
        assert C.edges_from_ledger({"pA": _post("pA", marks=[mark])}) == []


def test_a_node_id_that_cannot_be_rebuilt_is_refused():
    """Verified by reconstruction, not by splitting: a walk must not claim to have reached a place
    the rest of the system would call by another name."""
    assert C.parse_node_id("vm_pA:r0") == ("pA", "r0")
    for junk in ("", "pA:r0", "vm_pA", "vm_:r0", "vm_pA:"):
        assert C.parse_node_id(junk) is None


# ── the route ──────────────────────────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    posts = FakeCollection([_post("pA", regions=["r0", "r1", "r2"]),
                            _post("pB", regions=["rB"])])
    atlas = FakeCollection([_atlas("e1", "pA", "r0", "pB", "rB")])
    proposals = FakeCollection([_proposal("p1", "pA", "r1", "r0"),
                                _proposal("p2", "pA", "r2", "r0")])

    import backend.routers.constellation as R

    # THE ORIGINAL, CAPTURED BEFORE PATCHING. `R.constellation` IS the service module, so patching
    # `load_edges` through it rebinds the very function the fake calls — the first attempt
    # recursed until the stack ran out. Bind the real one first and the fake becomes an injection
    # rather than a cycle.
    real_load = C.load_edges

    async def _load(**_kw):
        return await real_load(posts_collection=posts, atlas=atlas, proposals=proposals)
    monkeypatch.setattr(R.constellation, "load_edges", _load)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/constellation")
    with TestClient(app) as client:
        yield client


def test_the_route_returns_a_neighbourhood_with_both_spans(wired):
    body = wired.get("/api/v1/constellation?node=vm_pA:r0&depth=2").json()
    assert body["seed"] == "vm_pA:r0" and body["depth"] == 2
    assert body["tally"]["by_span"] == {C.SPAN_WITHIN: 2, C.SPAN_BETWEEN: 1}
    assert sorted(body["images"]) == ["pA", "pB"]
    assert body["sources"]["curator_proposals"] == 2
    assert body["sources"]["atlas_movement_edges"] == 1
    assert body["sources"]["ledger_relation_marks"] == 0


def test_the_route_carries_the_region_label_but_never_gates_on_it(wired):
    body = wired.get("/api/v1/constellation?node=vm_pA:r0&depth=1").json()
    labels = {n["region_id"]: n["label"] for n in body["nodes"]}
    assert labels["r0"] == "r0-label"


def test_the_route_refuses_something_that_is_not_a_locus_id(wired):
    resp = wired.get("/api/v1/constellation?node=not-a-locus&depth=1")
    assert resp.status_code == 400
    assert "vm_<post_id>:<region_id>" in resp.json()["detail"]


def test_the_seeds_route_reports_where_anything_is_filed(wired):
    body = wired.get("/api/v1/constellation/seeds").json()
    assert body["total"] >= 4
    assert body["seeds"][0]["node_id"] == "vm_pA:r0", "busiest first"
    assert body["seeds"][0]["degree"] == 3
    assert "FILED" in body["detail"]


def test_the_response_model_defaults_no_status(wired):
    """The curator lane's trap, one layer out: a `ledger_status: str = 'committed'` would render
    every un-derived edge as settled and nobody would have written the word."""
    from backend.routers.constellation import EdgeView

    for field in ("epistemic", "ledger_status", "span", "directed"):
        assert EdgeView.model_fields[field].is_required(), field
