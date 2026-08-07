"""WAVE4.5 — the derived-relation store: the five ways one home would become a second ledger.

The whole risk of unifying is that the unified thing starts to look authoritative. 2,755 relations
in one place, read by every view, is exactly the shape that quietly becomes "what the system knows"
— and 2,742 of them are the organs agreeing with themselves.

  1. DERIVED IS NEVER COMMITTED. Only a mark in a post's own ledger reads `committed`, and no other
     origin can produce that word. §1.
  2. `epistemic` IS RE-DERIVED ON READ. A hand-edited store cannot promote a box-basis relation —
     the scene lane's rule, now guarding four origins instead of one. §1.
  3. THE TRIAGE RULE IS STATED AND MECHANICAL. Queued iff it contradicts another grounded relation;
     never a threshold, never "everything". §2.
  4. A REFUSED CANDIDATE HAS NOWHERE TO COME FROM. The constellation's structural guard, moved to
     the store it now delegates to. §3.
  5. THE GAP IS REPORTED, NOT AVERAGED. `census` counts by origin and by ledger status; one total
     would hide the entire finding. §4.
"""
from __future__ import annotations

import copy

import pytest

from backend.services import derived_relations as store
from backend.services import scene_relations
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
        self.docs = list(copy.deepcopy(list(docs)))

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs])


def _cache(*, basis="mask", supersedes=None):
    """A derived cache in the scene lane's own shape — one nesting, one occlusion."""
    return {
        "cache_version": scene_relations.CACHE_VERSION, "built_at": STAMP,
        "kinds_built": ["nesting", "occlusion"],
        "provenance": {"depth_grid": 192},
        "scenes": {"pA": {"post_id": "pA", "relations": {
            "nesting": [{"kind": "nesting", "axis": "axis_nestedness",
                         "relation": "nested_within", "source": "r_part", "target": "r_whole",
                         "target_post_id": "", "basis": basis, "organ": "nestedness_organ",
                         "detail": "containment 0.98", "numbers": {"nesting_index": 0.95},
                         "supersedes": None}],
            "occlusion": [{"kind": "occlusion", "axis": "axis_occlusion",
                           "relation": "in_front_of", "source": "r_part", "target": "r_whole",
                           "target_post_id": "", "basis": "mask", "organ": "occlusion_organ",
                           "detail": "ordering 0.98", "numbers": {"ordering_separation": 0.98},
                           "supersedes": supersedes or {"kind": "nesting", "source": "r_part",
                                                        "target": "r_whole"}}],
        }}},
    }


def _post(post_id="pA", marks=()):
    return {"_id": post_id, "visual_marks": list(marks), "region_annotations": []}


def _committed_mark(basis="mask", stated=EpistemicStatus.MEASURED.value):
    return {"id": "vm_occ_1", "type": "relation_mark", "role": "in_front_of",
            STATUS_KEY: stated, "label": "r_part in front of r_whole",
            "measurement": {"front_region_id": "r_part", "back_region_id": "r_whole",
                            "basis": basis, "axis": "axis_occlusion"},
            "provenance": {"producer": "occlusion_organ", "committed_by": "adarsh"}}


def _proposal(committed=False):
    return {"proposal_id": "prop_1", "post_id": "pA", "producer": "occlusion_organ",
            "mark": {"id": "vm_occ_1", "role": "in_front_of", "axis": "axis_occlusion",
                     STATUS_KEY: EpistemicStatus.MEASURED.value},
            "subject": {"front_region_id": "r_part", "back_region_id": "r_whole",
                        "claim": "r_part is IN FRONT OF r_whole"},
            "evidence": {"basis": "mask", "ordering_separation": 0.98, "depth_grid": 192,
                         "contradicts": {"relation": "nested_within", "containment": 0.98}},
            "committed_at": STAMP if committed else None,
            "committed_by": "adarsh" if committed else None}


def _atlas(mark_id="vm_nest_x"):
    return {"_id": "atlas_1", "edges": [{
        "edge_id": "e1", "kind": "movement", "mark_id": mark_id,
        "source_node": "vm_pA:r_part", "target_node": "vm_pB:r_far",
        "spans": ["pA", "pB"], "axis_ref": "axis_nestedness",
        "systematicity": 0.6, "weight": 0.25}]}


# ── 1. derived is never committed; status is recomputed ────────────────────

def test_a_derived_relation_reads_proposed_and_never_committed():
    rows = store.from_derived_cache(_cache())
    assert len(rows) == 2
    assert {r["origin"] for r in rows} == {store.ORIGIN_DERIVED}
    assert {r["ledger_status"] for r in rows} == {store.LEDGER_PROPOSED}


def test_only_a_mark_in_a_posts_own_ledger_reads_committed():
    """The one place the word is produced, and every other origin is checked for it."""
    ledger = store.from_ledger({"pA": _post(marks=[_committed_mark()])})
    assert [r["ledger_status"] for r in ledger] == [store.LEDGER_COMMITTED]

    others = [*store.from_derived_cache(_cache()),
              *store.from_proposals([_proposal()]),
              *store.from_atlas([_atlas()], {})]
    assert all(r["ledger_status"] == store.LEDGER_PROPOSED for r in others)


def test_a_hand_edited_store_cannot_promote_a_box_basis_relation():
    """THE SCENE LANE'S RULE, now guarding four origins. The basis is data; the status is a
    conclusion; the conclusion is recomputed on every read."""
    forged = _cache(basis="box")
    forged["scenes"]["pA"]["relations"]["nesting"][0]["epistemic"] = "measured"
    forged["scenes"]["pA"]["relations"]["nesting"][0]["admissible"] = True

    nesting = next(r for r in store.from_derived_cache(forged) if r["kind"] == "nesting")
    assert nesting["epistemic"] == EpistemicStatus.INTERPRETIVE.value
    assert nesting["admissible"] is False


def test_a_committed_mark_whose_stamp_disagrees_with_its_basis_is_flagged_not_silently_fixed():
    """A view has to be able to show that as a contradiction rather than silently preferring one
    of the two answers."""
    rows = store.from_ledger({"pA": _post(marks=[_committed_mark(basis="box")])})
    assert rows[0]["epistemic"] == EpistemicStatus.INTERPRETIVE.value
    assert rows[0]["misstated"] is True

    honest = store.from_ledger({"pA": _post(marks=[_committed_mark(basis="mask")])})
    assert honest[0]["misstated"] is False


def test_an_atlas_edge_with_no_readable_mark_says_so_rather_than_defaulting():
    """`epistemic_for("")` would return `interpretive` — the conservative default — and reporting
    it would be this store making a claim on the edge's behalf. There is no basis to read."""
    rows = store.from_atlas([_atlas()], {})
    assert rows[0]["epistemic"] is None
    assert rows[0]["admissible"] is False and rows[0]["misstated"] is False

    with_mark = store.from_atlas(
        [_atlas()], {"pA": _post(marks=[{**_committed_mark(), "id": "vm_nest_x"}])})
    assert with_mark[0]["epistemic"] == EpistemicStatus.MEASURED.value


def test_the_row_computes_its_conclusions_rather_than_accepting_them():
    import inspect
    params = inspect.signature(store.relation).parameters
    for conclusion in ("epistemic", "admissible", "queued", "misstated", "triage"):
        assert conclusion not in params, f"{conclusion} is passed in, not computed"


# ── 2. the triage rule ─────────────────────────────────────────────────────

def test_a_relation_is_queued_exactly_when_it_contradicts_another():
    rows = store.from_derived_cache(_cache())
    nesting = next(r for r in rows if r["kind"] == "nesting")
    occlusion = next(r for r in rows if r["kind"] == "occlusion")

    assert nesting["queued"] is False and nesting["triage"] == store.TRIAGE_ROUTINE
    assert occlusion["queued"] is True and occlusion["triage"] == store.TRIAGE_CONTRADICTS


def test_the_triage_reports_what_it_skipped_as_well_as_what_it_selected():
    """A triage that reported only its selection would be indistinguishable from one that found
    nothing else — and the skipped count is the fact that justifies having a rule."""
    rows = store.from_derived_cache(_cache())
    result = store.triage(rows)
    assert result["selected_count"] == 1 and result["skipped_count"] == 1
    assert "contradicts another grounded relation" in result["rule"]
    assert "agreeing with themselves" in result["detail"]


def test_the_rule_is_a_property_of_the_relation_and_not_a_threshold():
    """A threshold would be a silent rule — it would move, and nobody reading a queued item could
    tell why it was there. `supersedes` can be read off the relation."""
    import inspect
    body = inspect.getsource(store)
    for numeric in ("MIN_", "_THRESHOLD", "> 0.9", ">= 0.9"):
        assert numeric not in body, f"{numeric} — the triage acquired a threshold"
    assert "supersedes" in inspect.getsource(store.relation)


def test_a_routine_relation_stays_out_of_the_queue_however_strong_it_is():
    strong = _cache()
    strong["scenes"]["pA"]["relations"]["nesting"][0]["numbers"]["nesting_index"] = 0.9999
    nesting = next(r for r in store.from_derived_cache(strong) if r["kind"] == "nesting")
    assert nesting["queued"] is False


# ── 3. a refused candidate has nowhere to come from ────────────────────────

def test_the_store_reads_four_named_origins_and_nothing_that_could_reach_a_candidate():
    """THE CONSTELLATION'S GUARD, moved to the store it now delegates to. It is not a filter — it
    is that a refusal was never written to any of the four, and the day something starts
    persisting candidates the omission has to be a decision rather than an accident."""
    import inspect
    body = inspect.getsource(store.load)
    for named in ("from_ledger", "from_proposals", "from_atlas", "from_derived_cache"):
        assert named in body, named
    for absent in ("retina", "propose_candidates", "run_kernel", "structure_map",
                   "REFUSED", "box_only"):
        assert absent not in body, absent


def test_the_store_writes_nothing():
    from pathlib import Path
    source = Path(store.__file__).read_text()
    for writer in ("insert_one", "update_one", "delete_one", "$push", "$set", "write_cache"):
        assert writer not in source, writer


# ── 4. the gap is reported, not averaged ───────────────────────────────────

def test_the_census_counts_by_origin_and_never_as_one_total():
    """'2,769 relations' would hide the entire point: almost all are rebuildable and none is
    committed."""
    rows = [*store.from_derived_cache(_cache()),
            *store.from_proposals([_proposal()]),
            *store.from_atlas([_atlas()], {})]
    result = store.census(rows)

    assert result["derived"] == 2
    assert result["durable"] == 2
    assert result["committed"] == 0
    assert result["queued_by_triage"] == 2      # the derived occlusion and the filed proposal
    assert set(result["by_origin"]) == {store.ORIGIN_DERIVED, store.ORIGIN_PROPOSAL,
                                        store.ORIGIN_ATLAS}
    assert "by_ledger_status" in result and "by_basis" in result


def test_the_census_carries_the_decision_and_the_rule_in_words():
    """Both are design choices this lane made on numbers. A census that reported only counts would
    leave the next reader to re-derive the reasoning or, more likely, to guess it."""
    result = store.census(store.from_derived_cache(_cache()))
    assert "pure function" in result["decision"]
    assert "5 at grid 32 and 13 at 192" in result["decision"]
    assert "IF AND ONLY IF" in result["triage_rule"]


def test_the_committed_count_moves_only_when_something_is_actually_committed():
    before = store.census(store.from_ledger({"pA": _post()}))
    after = store.census(store.from_ledger({"pA": _post(marks=[_committed_mark()])}))
    assert before["committed"] == 0 and after["committed"] == 1


# ── the loader ─────────────────────────────────────────────────────────────

def _load(**kw):
    import asyncio
    return asyncio.run(store.load(**kw))


def test_the_loader_can_report_the_durable_world_alone():
    """`include_derived=False` is what makes the 14-vs-2755 gap reportable rather than asserted."""
    kw = dict(posts_collection=FakeCollection([_post()]),
              atlas=FakeCollection([_atlas()]),
              proposals=FakeCollection([_proposal()]),
              derived=_cache())

    everything = _load(**kw, include_derived=True)
    durable = _load(**kw, include_derived=False)

    assert len(everything["relations"]) == 4
    assert len(durable["relations"]) == 2
    assert all(r["origin"] != store.ORIGIN_DERIVED for r in durable["relations"])


def test_the_loader_carries_how_the_cache_was_built():
    """A store that did not say what produced it would be a cache pretending to be a fact — and
    the occlusion count is a function of the depth grid, so the parameters ARE part of the claim."""
    loaded = _load(posts_collection=FakeCollection([_post()]),
                   atlas=FakeCollection(), proposals=FakeCollection(), derived=_cache())
    assert loaded["cache"]["built_at"] == STAMP
    assert loaded["cache"]["provenance"]["depth_grid"] == 192
    assert loaded["cache"]["kinds_built"] == ["nesting", "occlusion"]


# ── 5. the route reports both numbers, and the rule beside them ────────────

@pytest.fixture
def wired(monkeypatch):
    """The route, fed the fakes. `real_load` is captured BEFORE patching for the reason the
    constellation lane learned the hard way: `R.derived_relations` IS the service module, so
    patching through it rebinds the function the fake calls."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import backend.routers.relations as R

    real_load = store.load

    async def _load(**kw):
        return await real_load(posts_collection=FakeCollection([_post()]),
                               atlas=FakeCollection([_atlas()]),
                               proposals=FakeCollection([_proposal()]),
                               derived=_cache(),
                               include_derived=kw.get("include_derived", True))
    monkeypatch.setattr(R.derived_relations, "load", _load)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/relations")
    with TestClient(app) as client:
        yield client


def test_the_route_reports_derived_and_durable_apart_and_never_as_one_total(wired):
    body = wired.get("/api/v1/relations/status").json()
    census = body["census"]
    # 2 derived · 2 durable (a filed proposal and an Atlas edge) · 0 committed — the corpus's own
    # shape in miniature, and the third number is the one that matters.
    assert census["derived"] == 2 and census["durable"] == 2 and census["committed"] == 0
    assert "total" not in census, "a single total would erase the finding"


def test_the_route_can_be_asked_for_the_durable_world_alone(wired):
    """The gap reportable rather than asserted: the same endpoint, one flag, two answers."""
    everything = wired.get("/api/v1/relations/status").json()["census"]
    durable = wired.get("/api/v1/relations/status?include_derived=false").json()["census"]
    assert everything["derived"] == 2 and durable["derived"] == 0
    assert durable["durable"] == everything["durable"]


def test_the_route_returns_the_rule_and_the_decision_in_words_not_only_counts(wired):
    """A count without the rule that produced it has to be trusted; with the rule it can be
    checked."""
    body = wired.get("/api/v1/relations/status").json()
    assert "IF AND ONLY IF" in body["rule"]
    assert "pure function" in body["decision"]
    assert body["skipped_count"] >= 1 and "agreeing with themselves" in body["triage_detail"]


def test_a_queued_row_shows_what_it_contradicts(wired):
    """The rule IS the contradiction — a selected row that could not show what it overturns would
    be asking to be taken on faith."""
    queued = wired.get("/api/v1/relations/status").json()["queued"]
    assert queued and all(row["supersedes"] for row in queued)


def test_the_route_carries_the_cache_parameters_with_the_count(wired):
    """5 occlusions at depth grid 32 and 13 at 192. The count means nothing without the grid."""
    cache = wired.get("/api/v1/relations/status").json()["cache"]
    assert cache["provenance"]["depth_grid"] == 192 and cache["built_at"] == STAMP


def test_the_router_has_no_write_path():
    from pathlib import Path
    import backend.routers.relations as R
    source = Path(R.__file__).read_text()
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in source, verb
