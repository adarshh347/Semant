"""
ATLAS C4 — plan mode: M2's argument, drawn on the Atlas, and edited back.

C4 owns no argument logic — `plan_argument` and `resolve_corpus` decide everything that matters —
so what is worth pinning here is the SEAM, from both directions:

  the corpus a plan is built over is the nodes, in node order    → §1
  only a BOUND percept gets a connector                          → §2
  a refused claim is struck, with the gate's own reason          → §3
  an edited plan comes back as claims, never as statuses         → §4
  accepting RE-BINDS: the ledger decides, not the client         → §5
  the stored plan is separate from edges and holds no evidence   → §6

Every fixture is SYNTHETIC. No real post, no real caption, no model is called.
"""
from __future__ import annotations

import asyncio
import copy

import pytest

from backend.services import atlas_plan as P
from backend.services import atlas_service as A
from backend.services.director.argument import (
    CHALLENGE, COMPLICATE, QUALIFIED, REFUSED, SUPPORT, SUPPORTED, make_claim, plan_argument)
from backend.services.director.corpus import build_corpus, hydrate_corpus


# ── fixtures ─────────────────────────────────────────────────────────────────

class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class FakeCollection:
    """The same fake the C1 store tests use — declared again rather than imported, because a test
    that breaks when another test file is renamed is a test about the wrong thing."""

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

    async def update_one(self, query, update, upsert=False):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in (query or {}).items()):
                d.update(update.get("$set", {}))
                return _UpdateResult(1, 1)
        return _UpdateResult(0, 0)


def an_atlas(*post_ids):
    """The shape both `atlas_view` and the stored document present: nodes, in order."""
    return {"_id": "atlas_1", "title": "the walk",
            "nodes": [{"node_id": f"n{i}", "post_id": pid, "x": 0.0, "y": 0.0}
                      for i, pid in enumerate(post_ids)]}


def a_post(post_id, *, regions=(), marks=(), grounds=()):
    return {"_id": post_id, "photo_url": f"https://example.invalid/{post_id}.jpg",
            "instagram_handle": f"handle_{post_id}",
            "region_annotations": [{"id": r} for r in regions],
            "visual_marks": [{"id": m} for m in marks],
            "grounds": [{"id": g} for g in grounds], "percepts": []}


def a_memory(*post_ids, **evidence):
    """A hydrated corpus over synthetic posts. `evidence` maps post_id → dict(regions=…, marks=…)."""
    corpus = build_corpus(corpus_id="atlas_1", title="the walk",
                          images=[{"post_id": p, "photo_url": f"u_{p}"} for p in post_ids])
    posts = {p: a_post(p, **evidence.get(p, {})) for p in post_ids}
    return corpus, hydrate_corpus(corpus, posts)


def an_argument(memory, claims, *, thesis="the sequence disperses what the rotunda gathers"):
    return plan_argument(thesis, claims, memory)


# ── 1. the corpus a plan is built over ───────────────────────────────────────

def test_the_corpus_is_the_nodes_in_node_order():
    """Order is evidence. The nodes preserve the corpus's own sequence through every save, so the
    plan is built over what the writer is looking at rather than over how the Atlas was opened."""
    assert P.node_post_ids(an_atlas("p3", "p1", "p2")) == ["p3", "p1", "p2"]


def test_the_corpus_ignores_an_id_repeated_on_two_nodes():
    assert P.node_post_ids(an_atlas("p1", "p2", "p1")) == ["p1", "p2"]


def test_a_connector_can_find_the_node_for_an_image():
    index = P.node_index(an_atlas("p1", "p2"))
    assert index == {"p1": "n0", "p2": "n1"}


def test_a_malformed_node_does_not_break_the_index():
    atlas = {"nodes": [{"node_id": "n0", "post_id": "p1"}, "not a node", {"post_id": "p2"}]}
    assert P.node_index(atlas) == {"p1": "n0"}


# ── 2. only a bound percept gets a connector ─────────────────────────────────

def test_a_bound_percept_draws_a_connector_to_its_image():
    _, memory = a_memory("p1", "p2", p1={"regions": ["r1"]})
    argument = an_argument(memory, [
        make_claim("c0", "the field disperses", [
            ("negative_space", {"image": "p1"}, SUPPORT),
            ("rhythm", {"image": "p2"}, CHALLENGE)])])
    view = P.plan_view(argument, an_atlas("p1", "p2"))

    edges = {(c["claim_id"], c["node_id"]) for c in view["connectors"]}
    assert ("c0", "n0") in edges and ("c0", "n1") in edges
    assert all(c["kind"] == P.EDGE_BINDING for c in view["connectors"])


def test_every_connector_carries_its_function_and_its_epistemic_kind():
    """The two things a line has to say. Without the function it is a wire; without the ceiling a
    reader cannot tell an instrument's report from a semantic guess."""
    _, memory = a_memory("p1", p1={"regions": ["r1"]})
    argument = an_argument(memory, [
        make_claim("c0", "the field disperses",
                   [("negative_space", {"image": "p1"}, CHALLENGE)])])
    (edge,) = P.plan_view(argument, an_atlas("p1"))["connectors"]
    assert edge["function"] == CHALLENGE
    assert edge["epistemic"] == "measured"
    assert edge["actuator"] == "negative_space"
    assert edge["step_id"] == "c0:0:negative_space"


def test_a_refused_percept_draws_no_connector_at_all():
    """RULE 1. A greyed line would still be a line — the shape of a supported argument, with the
    refusal demoted to a caption. The percept is reported in words on the claim instead."""
    _, memory = a_memory("p1")                       # no marks: connect_marks cannot resolve
    argument = an_argument(memory, [
        make_claim("c0", "these two marks relate",
                   [("connect_marks", {"image": "p1"}, SUPPORT)])])
    view = P.plan_view(argument, an_atlas("p1"))

    assert view["connectors"] == []
    (claim,) = view["claims"]
    (percept,) = claim["percepts"]
    assert percept["bound"] is False
    assert "connect_marks" in percept["why"]


def test_a_comparative_percept_gets_no_connector_and_says_it_spans_the_corpus():
    """It relates images to each other and names none of them, so there is no single node to point
    at. Reported on the claim rather than drawn as a line to an image it is not about."""
    _, memory = a_memory("p1", "p2", p1={"marks": ["m1"]}, p2={"marks": ["m2"]})
    argument = an_argument(memory, [
        make_claim("c0", "the two views argue", [("compare_views", {}, CHALLENGE)])])
    view = P.plan_view(argument, an_atlas("p1", "p2"))

    (claim,) = view["claims"]
    (percept,) = claim["percepts"]
    assert percept["bound"] is True                  # it BOUND; it simply has no one endpoint
    assert percept["spans_corpus"] is True
    assert view["connectors"] == []


def test_a_percept_on_an_image_this_atlas_does_not_hold_gets_no_endpoint():
    """The corpus and the canvas would have to disagree for this to happen, and inventing an
    endpoint is exactly how such a disagreement stops being visible."""
    _, memory = a_memory("p1", p1={"regions": ["r1"]})
    argument = an_argument(memory, [
        make_claim("c0", "the field disperses",
                   [("negative_space", {"image": "p1"}, SUPPORT)])])
    view = P.plan_view(argument, {"nodes": [{"node_id": "n9", "post_id": "somewhere_else"}]})
    assert view["connectors"] == []


# ── 3. a refused claim is struck, with the gate's own reason ─────────────────

def test_a_claim_nothing_can_carry_is_struck_and_keeps_its_refusals():
    _, memory = a_memory("p1", "p2", p1={"regions": ["r1"]})
    argument = an_argument(memory, [
        make_claim("c0", "the field disperses",
                   [("negative_space", {"image": "p1"}, CHALLENGE)]),
        make_claim("c1", "these marks relate",
                   [("connect_marks", {"image": "p2"}, SUPPORT)])])
    carried, struck = P.plan_view(argument, an_atlas("p1", "p2"))["claims"]

    assert carried["status"] == SUPPORTED and carried["struck"] is False
    assert struck["status"] == REFUSED and struck["struck"] is True
    assert struck["reason"] == "no_percept_could_be_produced"
    # the refused claim STAYS in the argument, with its evidence path and why it failed
    assert struck["percepts"][0]["why"].startswith("missing_input")


def test_a_qualified_claim_keeps_both_halves_of_its_evidence():
    """`bound` and `unbound` together, for the reason `BoundClaim` keeps them: a row holding only
    what worked makes a qualified claim indistinguishable from a supported one."""
    _, memory = a_memory("p1", p1={"regions": ["r1"]})
    argument = an_argument(memory, [
        make_claim("c0", "the field disperses", [
            ("negative_space", {"image": "p1"}, CHALLENGE),
            ("connect_marks", {"image": "p1"}, SUPPORT)])])
    (claim,) = P.plan_view(argument, an_atlas("p1"))["claims"]

    assert claim["status"] == QUALIFIED
    assert [p["bound"] for p in claim["percepts"]] == [True, False]
    assert claim["achieved_status"] == "measured"


def test_the_view_reports_the_argument_level_refusal_verbatim():
    """An argument with no surviving challenge is refused AT THE ARGUMENT LEVEL, and the surface
    shows that refusal rather than a plan that merely looks short."""
    _, memory = a_memory("p1", p1={"regions": ["r1"]})
    argument = an_argument(memory, [
        make_claim("c0", "the field disperses",
                   [("negative_space", {"image": "p1"}, SUPPORT)])])
    view = P.plan_view(argument, an_atlas("p1"))

    assert view["has_challenge"] is False
    assert view["complete"] is False
    assert [r["reason"] for r in view["refusals"]] == ["no_challenge_step"]


def test_zero_claims_from_an_unreachable_planner_is_not_zero_claims_from_a_read_corpus():
    """The one distinction a surface cannot afford to lose: both are an empty plan, and only one
    of them says anything about the corpus."""
    _, memory = a_memory("p1")
    argument = an_argument(memory, [])
    assert P.plan_view(argument, an_atlas("p1"))["planner_available"] is True
    assert P.plan_view(argument, an_atlas("p1"),
                       planner_available=False)["planner_available"] is False


# ── 4. an edited plan, coming back ───────────────────────────────────────────

def test_an_edited_plan_returns_claims_and_never_statuses():
    """RULE 3. The payload is a browser's view of the plan and carries every field the surface was
    given; a client that could post `status: supported` could write an unevidenced argument."""
    claims, notes, _ = P.claims_from_payload([{
        "claim_id": "c0", "text": "the field disperses", "status": "supported",
        "achieved_status": "visible", "struck": False,
        "percepts": [{"step_id": "c0:0:negative_space", "actuator": "negative_space",
                      "image": "p1", "function": SUPPORT, "bound": True, "params": {}}],
    }])
    (claim,) = claims
    assert claim.claim_id == "c0"
    assert not hasattr(claim, "status")              # a SubClaim is unbound by construction
    assert claim.percepts[0].step.id == "c0:0:negative_space"


def test_an_edited_percept_cannot_smuggle_geometry():
    """The same clamp `groq_planner` applies to a model. A browser is no more entitled to author a
    mask than a language model is, and the discipline should not depend on who is talking."""
    claims, notes, _ = P.claims_from_payload([{
        "claim_id": "c0", "text": "these marks relate",
        "percepts": [{"actuator": "connect_marks", "image": "p1", "function": SUPPORT,
                      "params": {"relation_role": "kinship", "mask": [[0, 0]],
                                 "confidence": 0.99}}],
    }])
    # the one key the actuator declares survives; the two it does not are gone and reported
    assert claims[0].percepts[0].step.params == {"relation_role": "kinship"}
    assert any("disallowed params" in n and "confidence" in n and "mask" in n for n in notes)


def test_an_unknown_function_is_kept_verbatim_to_be_refused():
    """Guard 6, one level on. Coercing it to `support` would let a typo dodge the challenge rule
    and put an unreadable rhetorical job on a real piece of evidence."""
    claims, notes, _ = P.claims_from_payload([{
        "claim_id": "c0", "text": "a claim",
        "percepts": [{"actuator": "rhythm", "image": "p1", "function": "reinforce"}]}])
    assert claims[0].percepts[0].function == "reinforce"
    assert any("unknown function 'reinforce'" in n for n in notes)


def test_a_reworded_claim_is_recorded_as_reworded():
    """M2's known limit, made visible. Binding proves a percept RESOLVES, not that it bears on the
    sentence — so a claim rewritten after its evidence was chosen has widened that gap, and the
    document says so instead of presenting the new wording as though it had been bound."""
    claims, notes, proposed = P.claims_from_payload([{
        "claim_id": "c0", "text": "the rotunda gathers what the sequence disperses",
        "proposed_text": "the sequence disperses",
        "percepts": [{"actuator": "rhythm", "image": "p1", "function": SUPPORT}]}])
    assert proposed == {"c0": "the sequence disperses"}
    assert any("reworded after its evidence was bound" in n for n in notes)


def test_an_unchanged_claim_is_not_reported_as_reworded():
    _, _, proposed = P.claims_from_payload([{
        "claim_id": "c0", "text": "the sequence disperses",
        "proposed_text": "the sequence disperses", "percepts": []}])
    assert proposed == {}


def test_a_reordered_plan_keeps_each_claims_own_id():
    """Renumbering by position would silently rewrite which claim a stored connector refers to."""
    claims, _, _ = P.claims_from_payload([
        {"claim_id": "c2", "text": "third, now first", "percepts": []},
        {"claim_id": "c0", "text": "first, now second", "percepts": []}])
    assert [c.claim_id for c in claims] == ["c2", "c0"]


def test_the_accepted_plan_is_capped_and_says_what_it_dropped():
    rows = [{"claim_id": f"c{i}", "text": f"claim {i}", "percepts": []} for i in range(9)]
    claims, notes, _ = P.claims_from_payload(rows)
    assert len(claims) == P.MAX_CLAIMS
    assert any("kept the first" in n for n in notes)


def test_a_claim_with_no_text_is_dropped_and_reported():
    claims, notes, _ = P.claims_from_payload([{"claim_id": "c0", "text": "   "}])
    assert claims == []
    assert any("carried no text" in n for n in notes)


# ── 5. accepting RE-BINDS: the ledger decides ────────────────────────────────

def test_a_claim_the_client_calls_supported_is_refused_if_nothing_can_carry_it():
    """The crux of rule 3, end to end: parse a payload that asserts success, re-bind it against a
    corpus that cannot produce the evidence, and watch the gate refuse it anyway."""
    _, memory = a_memory("p1")                       # no marks anywhere
    claims, notes, _ = P.claims_from_payload([{
        "claim_id": "c0", "text": "these marks relate", "status": "supported",
        "percepts": [{"actuator": "connect_marks", "image": "p1", "function": SUPPORT}]}])
    argument = plan_argument("a thesis", claims, memory, planner=P.PLANNER_ACCEPTED, notes=notes)
    stored = P.stored_plan(argument, an_atlas("p1"), now="2026-08-03T00:00:00Z")

    assert stored["claims"][0]["status"] == REFUSED
    assert stored["claims"][0]["struck"] is True
    assert stored["connectors"] == []
    assert stored["accepted"] is True
    assert stored["planner"] == P.PLANNER_ACCEPTED


def test_deleting_the_last_challenge_percept_refuses_the_argument_on_accept():
    """The writer is allowed to remove it. What they are not allowed to do is end up with a
    document that looks finished — `plan_argument` refuses the argument and the record says so."""
    _, memory = a_memory("p1", p1={"regions": ["r1"]})
    claims, _, _ = P.claims_from_payload([{
        "claim_id": "c0", "text": "the field disperses",
        "percepts": [{"actuator": "negative_space", "image": "p1", "function": SUPPORT}]}])
    stored = P.stored_plan(plan_argument("a thesis", claims, memory), an_atlas("p1"))

    assert stored["claims"][0]["status"] == SUPPORTED
    assert stored["complete"] is False
    assert [r["reason"] for r in stored["refusals"]] == ["no_challenge_step"]


def test_a_stored_plan_keeps_both_wordings_of_a_reworded_claim():
    _, memory = a_memory("p1", p1={"regions": ["r1"]})
    claims, notes, proposed = P.claims_from_payload([{
        "claim_id": "c0", "text": "the rotunda gathers", "proposed_text": "the field disperses",
        "percepts": [{"actuator": "negative_space", "image": "p1", "function": CHALLENGE}]}])
    stored = P.stored_plan(plan_argument("a thesis", claims, memory),
                           an_atlas("p1"), proposed_text=proposed, notes=notes)

    (claim,) = stored["claims"]
    assert claim["text"] == "the rotunda gathers"
    assert claim["proposed_text"] == "the field disperses"
    assert claim["reworded"] is True


def test_binding_stays_planned_until_something_actually_runs():
    """An accepted plan is what WOULD be produced. Only `confirm_against_chain`, after a real
    chain, may say `confirmed` — and no route here runs one."""
    _, memory = a_memory("p1", p1={"regions": ["r1"]})
    claims, _, _ = P.claims_from_payload([{
        "claim_id": "c0", "text": "the field disperses",
        "percepts": [{"actuator": "negative_space", "image": "p1", "function": CHALLENGE}]}])
    stored = P.stored_plan(plan_argument("a thesis", claims, memory), an_atlas("p1"))
    assert stored["claims"][0]["binding"] == "planned"


def test_a_claim_planned_on_an_unreadable_image_binds_with_a_caveat():
    """M1's distinction, carried up: bound to an image we could not read is not the same as bound
    to an image we read and found empty."""
    corpus = build_corpus(corpus_id="atlas_1",
                          images=[{"post_id": "p1", "photo_url": "u"},
                                  {"post_id": "ghost", "photo_url": ""}])
    memory = hydrate_corpus(corpus, {"p1": a_post("p1", regions=["r1"])})
    claims, _, _ = P.claims_from_payload([{
        "claim_id": "c0", "text": "the light falls",
        "percepts": [{"actuator": "light_field", "image": "ghost", "function": CHALLENGE}]}])
    stored = P.stored_plan(plan_argument("a thesis", claims, memory), an_atlas("p1", "ghost"))

    (claim,) = stored["claims"]
    assert claim["status"] == SUPPORTED
    assert any("could not be read" in c for c in claim["caveats"])


# ── 6. the store: separate from edges, and holding no evidence ───────────────

def test_a_fresh_atlas_has_no_plan_and_no_edges():
    doc = A.new_atlas_doc(atlas_id="a1", corpus_ref=["p1"], post_ids=["p1"])
    assert doc["plan"] is None
    assert doc["edges"] == []


def test_the_plan_round_trips_and_never_lands_in_edges():
    """RULE 2. An edge is a relation somebody produced; a plan is structure somebody proposed. A
    document that stored them in one list would have nothing left to tell them apart with."""
    async def run():
        coll = FakeCollection()
        await A.create_atlas(corpus_ref=["p1"], post_ids=["p1"], atlas_id="a1", collection=coll)
        stored = {"contract_version": 1, "thesis": "t", "claims": [], "connectors": [
            {"edge_id": "c0~s0", "kind": P.EDGE_BINDING, "claim_id": "c0", "node_id": "n0"}]}
        doc = await A.save_plan("a1", stored, collection=coll)
        assert doc["plan"]["connectors"][0]["kind"] == P.EDGE_BINDING
        assert doc["edges"] == []
        again = await A.get_atlas("a1", collection=coll)
        assert again["plan"]["thesis"] == "t"
        return again
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(run())


def test_a_plan_can_be_cleared_without_touching_the_canvas():
    async def run():
        coll = FakeCollection()
        await A.create_atlas(corpus_ref=["p1", "p2"], post_ids=["p1", "p2"],
                             atlas_id="a1", collection=coll)
        await A.save_plan("a1", {"thesis": "t", "claims": []}, collection=coll)
        doc = await A.save_plan("a1", None, collection=coll)
        assert doc["plan"] is None
        assert [n["post_id"] for n in doc["nodes"]] == ["p1", "p2"]
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(run())


def test_saving_a_plan_on_an_atlas_that_does_not_exist_is_not_a_create():
    async def run():
        assert await A.save_plan("nope", {"thesis": "t"}, collection=FakeCollection()) is None
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(run())


def test_the_hydrated_view_carries_the_accepted_plan():
    doc = A.new_atlas_doc(atlas_id="a1", corpus_ref=["p1"], post_ids=["p1"])
    doc["plan"] = {"thesis": "t", "claims": []}
    assert A.atlas_view(doc, {})["plan"]["thesis"] == "t"


def test_an_atlas_made_before_plan_mode_reads_as_having_no_plan():
    doc = A.new_atlas_doc(atlas_id="a1", corpus_ref=["p1"], post_ids=["p1"])
    doc.pop("plan")
    assert A.atlas_view(doc, {})["plan"] is None


def test_a_plan_carrying_evidence_in_its_params_is_refused_outright():
    """The belt to `_clamp_params`' braces. A stored plan holding geometry would put a measurement
    nobody produced on the canvas, wearing a step's name, beside real percepts."""
    with pytest.raises(ValueError, match="carries evidence"):
        P.assert_plan_authors_no_evidence({"claims": [{"percepts": [
            {"step_id": "c0:0:negative_space", "params": {"mask": [[0, 0]]}}]}]})


def test_a_plan_that_only_names_things_passes_the_same_check():
    P.assert_plan_authors_no_evidence({"claims": [{"percepts": [
        {"step_id": "c0:0:negative_space", "params": {"phrase": "the gap"}}]}]})
    P.assert_plan_authors_no_evidence(None)


# ── 7. the three routes, over fakes ──────────────────────────────────────────

@pytest.fixture
def wired(monkeypatch):
    """A minimal app holding only the Atlas routes, with the store, the ledger and the planner
    all faked. Mounted WITHOUT the API-key dependency: what is under test is the route."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import backend.database as db
    import backend.routers.atlas as R
    import backend.services.director.argument_planner as ap

    atlases, posts = FakeCollection(), FakeCollection()
    monkeypatch.setattr(db, "atlas_collection", atlases, raising=False)
    monkeypatch.setattr(R, "post_collection", posts, raising=False)
    # No route test may reach the real API. The default is an UNAVAILABLE planner; the tests that
    # want claims install a stub of their own.
    monkeypatch.setattr(ap.GroqArgumentPlanner, "_get_client", lambda self: None)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/atlas")
    return TestClient(app), atlases, posts, monkeypatch, ap


def _seed(client, posts, ids, *, regions=()):
    for pid in ids:
        posts.docs[pid] = a_post(pid, regions=regions)
    res = client.post("/api/v1/atlas/", json={"title": "the walk", "post_ids": list(ids)})
    assert res.status_code == 201
    return res.json()["id"]


class _StubPlanner:
    """Proposes a fixed decomposition. Stands in for Groq so the route's own behaviour — corpus
    assembly, binding, shaping — is what is being tested rather than a model's mood."""
    name = "stub"

    def __init__(self, claims):
        self._claims = claims
        self.last_notes = ("planner: stub",)
        self.seen = []

    def is_available(self):
        return True

    def propose(self, thesis, memory):
        self.seen.append((thesis, memory))
        return self._claims


def test_planning_needs_a_thesis(wired):
    client, _, posts, _, _ = wired
    atlas_id = _seed(client, posts, ["p1"])
    assert client.post(f"/api/v1/atlas/{atlas_id}/plan", json={"thesis": "  "}).status_code == 422


def test_planning_an_atlas_that_does_not_exist_is_a_404(wired):
    client, _, _, _, _ = wired
    res = client.post("/api/v1/atlas/nope/plan", json={"thesis": "a thesis"})
    assert res.status_code == 404


def test_an_unreachable_planner_returns_an_empty_plan_that_says_so(wired):
    """Not a 500 and not an empty argument presented as a finding. The claim list is empty and
    `planner_available` is false, which are two different sentences on the surface."""
    client, _, posts, _, _ = wired
    atlas_id = _seed(client, posts, ["p1", "p2"])
    body = client.post(f"/api/v1/atlas/{atlas_id}/plan", json={"thesis": "a thesis"}).json()

    assert body["claims"] == [] and body["connectors"] == []
    assert body["planner_available"] is False
    assert any("unavailable" in n for n in body["notes"])


def test_the_route_plans_over_the_atlas_corpus_and_draws_what_binds(wired):
    """The demo, in one request: a multi-image spread, a claim bound to a real percept on a real
    node, and a second claim the gate refuses."""
    client, _, posts, monkeypatch, ap = wired
    atlas_id = _seed(client, posts, ["p1", "p2"], regions=["r1"])
    director = ap.RhetoricalDirector(planner=_StubPlanner([
        make_claim("c0", "the field disperses", [
            ("negative_space", {"image": "p1"}, SUPPORT),
            ("rhythm", {"image": "p2"}, CHALLENGE)]),
        make_claim("c1", "these two marks relate",
                   [("connect_marks", {"image": "p2"}, SUPPORT)])]))
    monkeypatch.setattr(ap, "RhetoricalDirector", lambda: director)

    body = client.post(f"/api/v1/atlas/{atlas_id}/plan",
                       json={"thesis": "the sequence disperses"}).json()

    carried, struck = body["claims"]
    assert carried["status"] == SUPPORTED and struck["struck"] is True
    assert {(c["claim_id"], c["node_id"]) for c in body["connectors"]} == {("c0", "n0"), ("c0", "n1")}
    assert body["has_challenge"] is True
    # proposing does not write: the Atlas still holds no plan
    assert client.get(f"/api/v1/atlas/{atlas_id}").json()["plan"] is None


def test_the_planner_is_handed_the_corpus_in_node_order(wired):
    client, _, posts, monkeypatch, ap = wired
    atlas_id = _seed(client, posts, ["p3", "p1", "p2"])
    planner = _StubPlanner([])
    director = ap.RhetoricalDirector(planner=planner)
    monkeypatch.setattr(ap, "RhetoricalDirector", lambda: director)

    client.post(f"/api/v1/atlas/{atlas_id}/plan", json={"thesis": "a thesis"})
    (_, memory), = planner.seen
    assert list(memory.corpus.post_ids) == ["p3", "p1", "p2"]


def test_accepting_re_binds_and_persists_the_result(wired):
    client, _, posts, _, _ = wired
    atlas_id = _seed(client, posts, ["p1", "p2"], regions=["r1"])
    res = client.post(f"/api/v1/atlas/{atlas_id}/plan/accept", json={
        "thesis": "the sequence disperses",
        "claims": [
            {"claim_id": "c0", "text": "the field disperses", "status": "supported",
             "percepts": [{"actuator": "negative_space", "image": "p1", "function": CHALLENGE}]},
            {"claim_id": "c1", "text": "these two marks relate", "status": "supported",
             "percepts": [{"actuator": "connect_marks", "image": "p2", "function": SUPPORT}]},
        ]})
    plan = res.json()["plan"]

    assert res.status_code == 200
    assert plan["claims"][0]["status"] == SUPPORTED
    # the client called BOTH supported; the gate refuses the one nothing can carry
    assert plan["claims"][1]["status"] == REFUSED
    assert plan["accepted"] is True and plan["accepted_at"]

    stored = client.get(f"/api/v1/atlas/{atlas_id}").json()["plan"]
    assert stored["thesis"] == "the sequence disperses"
    assert stored["planner"] == P.PLANNER_ACCEPTED
    assert client.get(f"/api/v1/atlas/{atlas_id}/view").json()["plan"]["thesis"] \
        == "the sequence disperses"


def test_accepting_nothing_is_refused_rather_than_treated_as_a_clear(wired):
    client, _, posts, _, _ = wired
    atlas_id = _seed(client, posts, ["p1"])
    res = client.post(f"/api/v1/atlas/{atlas_id}/plan/accept",
                      json={"thesis": "a thesis", "claims": []})
    assert res.status_code == 422
    assert "DELETE" in res.json()["detail"]


def test_a_plan_can_be_deleted(wired):
    client, _, posts, _, _ = wired
    atlas_id = _seed(client, posts, ["p1"], regions=["r1"])
    client.post(f"/api/v1/atlas/{atlas_id}/plan/accept", json={
        "thesis": "a thesis",
        "claims": [{"claim_id": "c0", "text": "the field disperses",
                    "percepts": [{"actuator": "negative_space", "image": "p1",
                                  "function": CHALLENGE}]}]})
    assert client.delete(f"/api/v1/atlas/{atlas_id}/plan").json()["plan"] is None
    assert client.get(f"/api/v1/atlas/{atlas_id}").json()["plan"] is None


def test_planning_and_accepting_write_nothing_to_a_post(wired):
    """The C1 invariant, extended to C4: plan mode reads the ledger and never touches it."""
    import hashlib
    import json as _json

    client, _, posts, _, _ = wired
    atlas_id = _seed(client, posts, ["p1", "p2"], regions=["r1"])
    before = hashlib.sha256(
        _json.dumps(posts.docs, sort_keys=True, default=str).encode()).hexdigest()

    client.post(f"/api/v1/atlas/{atlas_id}/plan", json={"thesis": "a thesis"})
    client.post(f"/api/v1/atlas/{atlas_id}/plan/accept", json={
        "thesis": "a thesis",
        "claims": [{"claim_id": "c0", "text": "the field disperses",
                    "percepts": [{"actuator": "negative_space", "image": "p1",
                                  "function": CHALLENGE}]}]})

    after = hashlib.sha256(
        _json.dumps(posts.docs, sort_keys=True, default=str).encode()).hexdigest()
    assert before == after
