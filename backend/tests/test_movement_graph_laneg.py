"""
WAVE2 Lane G — movement edges and axes.

The claims under test, in the order they matter:

  1. a movement edge IS an `atlases.edges` row                     → TestReconciliation
  2. it stores no percept truth, and derives it instead            → TestDerivedNotStored
  3. every declared field survives the store round trip            → TestRoundTripReplay
  4. only measurement moves a weight                               → TestDynamics
  5. a contradiction closes an edge and is recorded, not erased    → TestContradiction
  6. the keeper evaporates and prunes without touching the ledger  → TestKeeper
  7. an axis is first-class, and its status is derived             → TestAxis
  8. the stigmergic API distinguishes "cold" from "unrelated"      → TestStigmergicAPI

Stub-driven: no database, no network, no model. Every boundary here is a dict, because every claim
is about SHAPE and DISCIPLINE rather than about anything a model produced.
"""
from __future__ import annotations

import asyncio
import copy

import pytest

from backend.services import atlas_relation as R
from backend.services import atlas_service as A
from backend.services import movement_graph as MG
from backend.services import movement_store as MS


def run(coro):
    # House style (`test_atlas_c1`): sync tests driving the async service through `asyncio.run`,
    # with the collection injected. NOT `get_event_loop().run_until_complete` — that reuses a loop
    # another module may already have closed, which passes in isolation and fails in the suite.
    return asyncio.run(coro)


# ── fakes ────────────────────────────────────────────────────────────────────

class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count, self.modified_count = matched, modified


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()


class FakeCollection:
    """Enough Mongo for this lane: `$set`, `$push` and upsert. `$push` is not optional — the whole
    reason `add_edge` appends rather than replacing is that two writers must not drop each other's
    edge, and a fake that turned it into a `$set` would test the bug rather than the fix."""

    def __init__(self):
        self.docs = {}

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        return type("R", (), {"inserted_id": doc["_id"]})()

    async def find_one(self, query, projection=None):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in (query or {}).items()):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values()])

    async def update_one(self, query, update, upsert=False):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in (query or {}).items()):
                d.update(copy.deepcopy(update.get("$set", {})))
                for key, value in (update.get("$push") or {}).items():
                    d.setdefault(key, []).append(copy.deepcopy(value))
                return _UpdateResult(1, 1)
        if upsert:
            doc = {**{k: v for k, v in (query or {}).items()},
                   **copy.deepcopy(update.get("$set", {}))}
            self.docs[doc.get("_id")] = doc
            return _UpdateResult(0, 1)
        return _UpdateResult(0, 0)


# ── fixtures ─────────────────────────────────────────────────────────────────

MEASURED_MARK = "vm_rel_measured01"
INTERPRETIVE_MARK = "vm_rel_interp001"


def a_mark(mark_id, status, *, run_id="run_7", step_id="s3"):
    """A committed relation mark, as C3 leaves it in both posts' `visual_marks`."""
    return {"id": mark_id, "type": "relation_mark", "role": "prepares",
            "label": "the façade prepares the rotunda", "epistemic_status": status,
            "source": "user_confirmed", "status": "committed", "cross_image": True,
            "provenance": {"run_id": run_id, "step_id": step_id,
                           "producer": "semantic_read", "adapter": "compare_views"}}


def posts_with(*marks):
    return {"p1": {"_id": "p1", "visual_marks": list(marks)},
            "p2": {"_id": "p2", "visual_marks": list(marks)}}


def an_edge(**kw):
    params = dict(mark_id=MEASURED_MARK, source_node="n1", target_node="n2",
                  spans=["p1", "p2"], axis_ref="axis_nestedness",
                  now="2026-08-05T00:00:00+00:00")
    params.update(kw)
    return MG.movement_edge_entry(**params)


# ── 1. reconciliation: a movement IS an atlas edge ───────────────────────────

class TestReconciliation:

    def test_the_spine_is_the_same_seven_keys_c3_writes(self):
        """Not "similar to" — the same key set, so one array holds both kinds."""
        movement = an_edge()
        relation = R.edge_entry(mark_id="vm_rel_x", source_node="n1", target_node="n2",
                                spans=["p1", "p2"])
        spine = set(relation.keys())
        assert spine <= set(movement.keys())
        for key in spine - {"kind", "edge_id", "created_at", "mark_id"}:
            assert type(movement[key]) is type(relation[key])

    def test_the_kind_is_what_tells_them_apart(self):
        assert an_edge()["kind"] == MG.EDGE_MOVEMENT == "movement"
        assert R.edge_entry(mark_id="m", source_node="a", target_node="b",
                            spans=[])["kind"] == R.EDGE_RELATION

    def test_it_passes_the_atlas_guard_that_every_edge_passes(self):
        """`assert_no_percept_data` is run over a document holding the movement — the same
        function, not a copy of its rules."""
        A.assert_no_percept_data({"nodes": [], "edges": [an_edge()]})
        MG.assert_valid_movement_edge(an_edge())

    def test_an_edge_with_no_mark_is_refused(self):
        """A movement with nothing behind it is the fabrication this lane must not persist."""
        with pytest.raises(ValueError, match="mark"):
            an_edge(mark_id="")

    def test_an_edge_with_no_axis_is_refused(self):
        with pytest.raises(ValueError, match="axis"):
            an_edge(axis_ref="")

    def test_edge_ids_are_minted_not_positional(self):
        """Census §4: `fine_i`-style positional ids are repointed by the next re-dissect."""
        ids = {MG.new_movement_edge_id() for _ in range(50)}
        assert len(ids) == 50
        assert all(i.startswith("edge_mv_") for i in ids)


# ── 2. derived, never stored twice ───────────────────────────────────────────

class TestDerivedNotStored:

    def test_the_edge_carries_no_epistemic_status_and_no_provenance(self):
        """The corrected Lane G rule. These are `_FORBIDDEN_EDGE_KEYS`, and they are the mark's."""
        edge = an_edge()
        for forbidden in ("epistemic_status", "provenance", "run_id", "step_id",
                          "role", "label", "sources"):
            assert forbidden not in edge

    def test_the_guard_would_have_caught_it_if_we_had_stored_them(self):
        """The contradiction in this lane's first card, made concrete: had the edge carried a
        status, the FIRST save would have raised."""
        with pytest.raises(ValueError, match="percept data"):
            A.assert_no_percept_data(
                {"nodes": [], "edges": [{**an_edge(), "epistemic_status": "measured"}]})
        with pytest.raises(ValueError, match="percept data"):
            A.assert_no_percept_data(
                {"nodes": [], "edges": [{**an_edge(), "provenance": {"run_id": "r"}}]})

    def test_status_is_read_off_the_mark(self):
        posts = posts_with(a_mark(MEASURED_MARK, "measured"))
        assert MG.edge_epistemic_status(an_edge(), posts) == "measured"

    def test_a_stale_edge_cannot_disagree_with_the_ledger(self):
        """Change the mark; the edge's answer changes with it. This is the property the whole
        reference-not-copy rule buys, asserted rather than assumed."""
        edge = an_edge()
        measured = posts_with(a_mark(MEASURED_MARK, "measured"))
        reinterpreted = posts_with(a_mark(MEASURED_MARK, "interpretive"))
        assert MG.hydrate_movement_edge(edge, measured)["epistemic"] == "measured"
        assert MG.hydrate_movement_edge(edge, reinterpreted)["epistemic"] == "interpretive"

    def test_run_and_step_are_derived_from_mark_provenance(self):
        posts = posts_with(a_mark(MEASURED_MARK, "measured", run_id="run_42", step_id="s9"))
        hydrated = MG.hydrate_movement_edge(an_edge(), posts)
        assert (hydrated["run_id"], hydrated["step_id"]) == ("run_42", "s9")

    def test_an_uncommitted_relation_leaves_the_edge_saying_so(self):
        """`hydrate_edge`'s rule, inherited: gone from the ledger is a fact, not an absence."""
        hydrated = MG.hydrate_movement_edge(an_edge(), {"p1": {"visual_marks": []}})
        assert hydrated["live"] is False
        assert hydrated["missing_reason"]
        assert hydrated["run_id"] is None and hydrated["step_id"] is None

    def test_a_withdrawn_relation_keeps_its_measured_weight(self):
        """The weight records measurements that really happened; withdrawal removes the claim,
        not the history."""
        edge = MG.strengthen(an_edge(), MG.observation(status="measured"))
        hydrated = MG.hydrate_movement_edge(edge, {"p1": {"visual_marks": []}})
        assert hydrated["live"] is False
        assert hydrated["weight"] > MG.INITIAL_WEIGHT

    def test_the_hydrator_carries_every_movement_field(self):
        """A key list is a silent dropper — this is the assertion that keeps the three lists
        (minter, hydrator, this test) agreeing."""
        hydrated = MG.hydrate_movement_edge(an_edge(), posts_with(a_mark(MEASURED_MARK, "measured")))
        for field in MG.MOVEMENT_FIELDS:
            assert field in hydrated

    def test_hydrate_edges_routes_a_movement_to_its_own_hydrator(self):
        """Mixed array, one call — a movement hydrated as a relation would lose six fields and
        nothing would fail."""
        doc = {"edges": [an_edge(), R.edge_entry(mark_id=INTERPRETIVE_MARK, source_node="n1",
                                                 target_node="n2", spans=["p1", "p2"])]}
        posts = posts_with(a_mark(MEASURED_MARK, "measured"),
                           a_mark(INTERPRETIVE_MARK, "interpretive"))
        out = R.hydrate_edges(doc, posts)
        assert out[0]["kind"] == "movement" and out[0]["axis_ref"] == "axis_nestedness"
        assert out[1]["kind"] == "relation" and "axis_ref" not in out[1]


# ── 3. the round trip ────────────────────────────────────────────────────────

class TestRoundTripReplay:
    """Construct → save → reload → diff. Nothing dropped, nothing invented."""

    def test_every_declared_field_survives_the_store(self):
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1", "p2"], post_ids=["p1", "p2"], collection=coll))
        edge = an_edge(systematicity=0.72)
        run(MS.write_edge(doc["_id"], mark_id=edge["mark_id"], source_node="n1", target_node="n2",
                          spans=["p1", "p2"], axis_ref="axis_nestedness", systematicity=0.72,
                          collection=coll))
        reloaded = run(A.get_atlas(doc["_id"], collection=coll))
        stored = [e for e in reloaded["edges"] if e["kind"] == "movement"][0]

        for field in MG.MOVEMENT_FIELDS:
            assert field in stored, f"{field} was dropped by the store"
        assert stored["systematicity"] == 0.72
        assert stored["weight"] == MG.INITIAL_WEIGHT
        assert stored["valid_to"] is None          # explicitly set, not merely absent
        assert stored["observations"] == []

    def test_nothing_was_invented_on_the_way_through(self):
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1", "p2"], post_ids=["p1", "p2"], collection=coll))
        run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1", target_node="n2",
                          spans=["p1", "p2"], axis_ref="axis_nestedness", collection=coll))
        reloaded = run(A.get_atlas(doc["_id"], collection=coll))
        stored = [e for e in reloaded["edges"] if e["kind"] == "movement"][0]
        expected = set(MG.MOVEMENT_FIELDS) | {"edge_id", "kind", "mark_id", "source_node",
                                              "target_node", "spans", "created_at"}
        assert set(stored.keys()) == expected

    def test_a_re_observed_edge_keeps_its_clocks(self):
        """The regression. `strengthen` writes `last_measured_at` and clears `decayed_at`; the
        first version of this module declared neither, so the store carried them and the hydrator
        dropped them — and a re-measured edge came back looking as if it never had been. Anything
        the dynamics write must be on `MOVEMENT_FIELDS`."""
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], collection=coll))
        run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1", target_node="n2",
                          spans=["p1", "p2"], axis_ref="axis_nestedness", collection=coll))
        stored = run(A.get_atlas(doc["_id"], collection=coll))["edges"][0]
        strengthened = MG.strengthen(
            stored, MG.observation(status="measured", at="2026-08-09T00:00:00+00:00"))

        hydrated = MG.hydrate_movement_edge(strengthened,
                                            posts_with(a_mark(MEASURED_MARK, "measured")))
        assert hydrated["last_measured_at"] == "2026-08-09T00:00:00+00:00"
        assert set(strengthened.keys()) - set(stored.keys()) == set(), \
            "strengthen invented a field nobody declared — it will be dropped"

    def test_two_writers_do_not_drop_each_others_edge(self):
        """`$push`, not read-modify-`$set`. The loss this codebase has already suffered once."""
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1", "p2"], post_ids=["p1", "p2"], collection=coll))
        for axis in ("axis_a", "axis_b"):
            run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1",
                              target_node="n2", spans=["p1", "p2"], axis_ref=axis,
                              collection=coll))
        reloaded = run(A.get_atlas(doc["_id"], collection=coll))
        assert {e["axis_ref"] for e in reloaded["edges"]} == {"axis_a", "axis_b"}


# ── 4. dynamics ──────────────────────────────────────────────────────────────

class TestDynamics:

    def test_a_measured_reobservation_strengthens(self):
        before = an_edge()
        after = MG.strengthen(before, MG.observation(status="measured"))
        assert after["weight"] > before["weight"]

    def test_agreement_does_not_strengthen(self):
        """The honesty floor in stigmergic form. A graph that strengthens on agreement learns
        what it already believes."""
        before = an_edge()
        after = MG.strengthen(before, MG.observation(status="interpretive"))
        assert after["weight"] == before["weight"]

    def test_but_the_agreement_is_still_recorded(self):
        """Logged where it cannot be mistaken for evidence — absent would lose a real fact."""
        after = MG.strengthen(
            an_edge(), MG.observation(status="interpretive", detail="a second reading concurred"))
        assert len(after["observations"]) == 1
        assert after["observations"][0]["epistemic_status"] == "interpretive"

    def test_strengthening_saturates(self):
        """The tenth confirmation is worth less than the second — that is what concentration
        means, and what stops one busy pair dominating the graph."""
        edge = an_edge()
        deltas = []
        for _ in range(6):
            after = MG.strengthen(edge, MG.observation(status="measured"))
            deltas.append(after["weight"] - edge["weight"])
            edge = after
        assert deltas == sorted(deltas, reverse=True)
        assert edge["weight"] <= MG.MAX_WEIGHT

    def test_time_decays_an_unmeasured_edge(self):
        edge = MG.strengthen(an_edge(), MG.observation(status="measured",
                                                       at="2026-08-05T00:00:00+00:00"))
        later = MG.decay(edge, now="2026-08-06T00:00:00+00:00")     # one half-life
        assert later["weight"] == pytest.approx(edge["weight"] / 2, rel=1e-3)

    def test_decay_is_computed_from_time_not_counted_per_tick(self):
        """Two keeper passes in a minute and one pass a minute later must agree, or the graph's
        shape becomes a function of the scheduler's health."""
        edge = MG.strengthen(an_edge(), MG.observation(status="measured",
                                                       at="2026-08-05T00:00:00+00:00"))
        once = MG.decay(edge, now="2026-08-06T00:00:00+00:00")
        twice = MG.decay(MG.decay(edge, now="2026-08-06T00:00:00+00:00"),
                         now="2026-08-06T00:00:00+00:00")
        assert once["weight"] == twice["weight"]

    def test_a_clock_that_went_backwards_does_not_strengthen(self):
        edge = MG.strengthen(an_edge(), MG.observation(status="measured",
                                                       at="2026-08-05T12:00:00+00:00"))
        earlier = MG.decay(edge, now="2026-08-05T00:00:00+00:00")
        assert earlier["weight"] == edge["weight"]


# ── 5. contradiction ─────────────────────────────────────────────────────────

class TestContradiction:

    def test_a_contradiction_closes_the_edge_and_drops_the_weight(self):
        edge = MG.strengthen(an_edge(), MG.observation(status="measured"))
        closed, _ = MG.invalidate(edge, reason="the enclosure runs the other way",
                                  now="2026-08-06T00:00:00+00:00")
        assert closed["valid_to"] == "2026-08-06T00:00:00+00:00"
        assert closed["weight"] == 0.0
        assert MG.is_live(closed) is False

    def test_the_contradiction_is_returned_as_its_own_node(self):
        """Evidence in its own right: something measured, at a time, that disagreed."""
        _, node = MG.invalidate(an_edge(), reason="contradicted by a measured re-read",
                                mark_id="vm_contra", run_id="run_9", step_id="s2")
        assert node["kind"] == MG.CONTRADICTION_KIND
        assert node["contradiction_id"].startswith("contra_")
        assert node["mark_id"] == "vm_contra"
        assert (node["run_id"], node["step_id"]) == ("run_9", "s2")

    def test_the_edge_is_closed_not_deleted(self):
        """"We never thought that" is a different claim from "we thought that until this
        contradicted it"."""
        edge = an_edge()
        closed, node = MG.invalidate(edge, reason="r")
        assert closed["edge_id"] == edge["edge_id"]
        assert closed["created_at"] == edge["created_at"]
        assert any(o.get("contradiction_id") == node["contradiction_id"]
                   for o in closed["observations"])

    def test_a_closed_edge_does_not_silently_reopen(self):
        """A later measurement must not erase a recorded contradiction — the honest move is a new
        edge, so both facts survive."""
        closed, _ = MG.invalidate(an_edge(), reason="r")
        after = MG.strengthen(closed, MG.observation(status="measured"))
        assert after["weight"] == 0.0
        assert after["valid_to"] is not None
        assert len(after["observations"]) == len(closed["observations"]) + 1


# ── 6. the keeper ────────────────────────────────────────────────────────────

class TestKeeper:

    def test_it_prunes_what_has_faded_and_keeps_what_has_not(self):
        fresh = MG.strengthen(an_edge(axis_ref="axis_fresh"),
                              MG.observation(status="measured", at="2026-08-05T00:00:00+00:00"))
        stale = MG.strengthen(an_edge(axis_ref="axis_stale"),
                              MG.observation(status="measured", at="2026-07-01T00:00:00+00:00"))
        result = MG.keeper_tick([fresh, stale], now="2026-08-05T01:00:00+00:00")
        assert [e["axis_ref"] for e in result["kept"]] == ["axis_fresh"]
        assert [e["axis_ref"] for e in result["pruned"]] == ["axis_stale"]

    def test_it_has_no_opinion_about_c3_relation_edges(self):
        relation = R.edge_entry(mark_id="vm_rel_x", source_node="n1", target_node="n2",
                                spans=["p1"])
        result = MG.keeper_tick([relation], now="2027-01-01T00:00:00+00:00")
        assert result["untouched"] == [relation]
        assert result["kept"] == [] and result["pruned"] == []

    def test_a_dry_run_reports_without_removing(self):
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], collection=coll))
        run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1", target_node="n2",
                          spans=["p1", "p2"], axis_ref="axis_old", weight=0.001,
                          now="2026-07-01T00:00:00+00:00", collection=coll))
        report = run(MS.keeper_pass(doc["_id"], now="2026-08-05T00:00:00+00:00", dry_run=True,
                                    collection=coll))
        assert report["pruned"] == 1 and report["dry_run"] is True
        assert len(run(A.get_atlas(doc["_id"], collection=coll))["edges"]) == 1

    def test_a_real_pass_removes_the_atlas_reference_only(self):
        """The ledger is never touched — `remove_edge`'s rule, inherited."""
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], collection=coll))
        run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1", target_node="n2",
                          spans=["p1", "p2"], axis_ref="axis_old", weight=0.001,
                          now="2026-07-01T00:00:00+00:00", collection=coll))
        run(MS.keeper_pass(doc["_id"], now="2026-08-05T00:00:00+00:00", collection=coll))
        assert run(A.get_atlas(doc["_id"], collection=coll))["edges"] == []


# ── 7. the axis ──────────────────────────────────────────────────────────────

class TestAxis:

    def test_an_axis_is_minted_once_and_is_its_own_record(self):
        axis = MG.new_axis(name="nestedness", relation_kind="contains")
        assert axis["axis_id"].startswith("axis_")
        assert axis["name"] == "nestedness"

    def test_an_axis_stores_no_epistemic_status(self):
        """Same rule as the edge, one level out: an axis is exactly as grounded as the movements
        that instantiate it, so a stored status would be a second copy."""
        assert "epistemic_status" not in MG.new_axis(name="n", relation_kind="k")

    def test_the_status_is_derived_from_what_grounds_it(self):
        axis = MG.new_axis(name="nestedness", relation_kind="contains", axis_id="axis_nestedness")
        posts = posts_with(a_mark(MEASURED_MARK, "measured"))
        assert MG.axis_status(axis, [an_edge()], posts) == "measured"

    def test_an_axis_nothing_grounds_says_nothing(self):
        """None is "cannot currently tell you" — `uncertain` would be a claim."""
        axis = MG.new_axis(name="n", relation_kind="k", axis_id="axis_lonely")
        assert MG.axis_status(axis, [], {}) is None

    def test_one_measured_instance_among_readings_makes_it_measured(self):
        axis = MG.new_axis(name="n", relation_kind="k", axis_id="axis_nestedness")
        edges = [an_edge(mark_id=INTERPRETIVE_MARK), an_edge(mark_id=MEASURED_MARK)]
        posts = posts_with(a_mark(MEASURED_MARK, "measured"),
                           a_mark(INTERPRETIVE_MARK, "interpretive"))
        assert MG.axis_status(axis, edges, posts) == "measured"

    def test_writing_the_same_axis_twice_is_idempotent(self):
        """Two rows for `nestedness` would split every retrieval along it, silently."""
        coll = FakeCollection()
        run(MS.write_axis(name="nestedness", relation_kind="contains", axis_id="axis_n",
                          collection=coll))
        run(MS.write_axis(name="nestedness", relation_kind="contains", axis_id="axis_n",
                          collection=coll))
        assert len(run(MS.list_axes(collection=coll))) == 1

    def test_the_view_reports_what_currently_grounds_it(self):
        axis = MG.new_axis(name="n", relation_kind="k", axis_id="axis_nestedness")
        doc = {"edges": [an_edge()]}
        view = MS.axis_view(axis, doc, posts_with(a_mark(MEASURED_MARK, "measured")))
        assert view["live_movements"] == 1
        assert view["epistemic_status"] == "measured"


# ── 8. the stigmergic API ────────────────────────────────────────────────────

class TestStigmergicAPI:

    def test_neighbours_are_undirected_but_report_direction(self):
        doc = {"edges": [an_edge()]}
        posts = posts_with(a_mark(MEASURED_MARK, "measured"))
        assert MS.read_neighbours(doc, "n1", posts=posts)[0]["direction"] == "outgoing"
        assert MS.read_neighbours(doc, "n2", posts=posts)[0]["direction"] == "incoming"

    def test_neighbours_come_back_heaviest_first(self):
        light = an_edge(axis_ref="axis_a")
        heavy = MG.strengthen(an_edge(axis_ref="axis_b"), MG.observation(status="measured"))
        out = MS.read_neighbours({"edges": [light, heavy]}, "n1",
                                 posts=posts_with(a_mark(MEASURED_MARK, "measured")))
        assert [e["axis_ref"] for e in out] == ["axis_b", "axis_a"]

    def test_a_cold_axis_and_an_unrelated_candidate_are_different_answers(self):
        """The retina's rule, inherited: collapsing both into `[]` is how a cold index starts
        looking like an isolated node."""
        posts = posts_with(a_mark(MEASURED_MARK, "measured"))
        cold = MS.retrieve_along_axis({"edges": []}, "axis_nestedness", {"node_id": "n1"},
                                      posts=posts)
        unrelated = MS.retrieve_along_axis({"edges": [an_edge()]}, "axis_nestedness",
                                           {"node_id": "n99"}, posts=posts)
        assert cold["status"] == "unknown"
        assert unrelated["status"] == "empty" and unrelated["axis_movements"] == 1

    def test_retrieval_returns_hydrated_movements(self):
        out = MS.retrieve_along_axis({"edges": [an_edge()]}, "axis_nestedness",
                                     {"node_id": "n1"},
                                     posts=posts_with(a_mark(MEASURED_MARK, "measured")))
        assert out["status"] == "ok"
        assert out["movements"][0]["epistemic"] == "measured"

    def test_a_subscriber_is_notified_and_can_unsubscribe(self):
        MS._reset_subscribers()
        seen = []
        stop = MS.subscribe("edge/*", lambda topic, payload: seen.append(topic))
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], collection=coll))
        run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1", target_node="n2",
                          spans=["p1", "p2"], axis_ref="axis_nestedness", collection=coll))
        stop()
        run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1", target_node="n2",
                          spans=["p1", "p2"], axis_ref="axis_nestedness", collection=coll))
        assert seen == ["edge/axis_nestedness"]

    def test_a_raising_subscriber_cannot_fail_the_write(self):
        """A reader that breaks must not break the writer — the whole point of stigmergy is that
        the writer does not depend on who is listening."""
        MS._reset_subscribers()

        def boom(topic, payload):
            raise RuntimeError("subscriber is broken")

        MS.subscribe("*", boom)
        coll = FakeCollection()
        doc = run(A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], collection=coll))
        assert run(MS.write_edge(doc["_id"], mark_id=MEASURED_MARK, source_node="n1",
                                 target_node="n2", spans=["p1", "p2"],
                                 axis_ref="axis_nestedness", collection=coll)) is not None
        MS._reset_subscribers()
