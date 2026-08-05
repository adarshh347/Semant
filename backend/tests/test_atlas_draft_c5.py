"""
ATLAS C5 — the writer: an accepted plan becomes drafted prose, quarantined, then a manuscript.

C5 owns no composition logic — `compose_article` writes every sentence and `resolve_article` joins
every citation — so what is pinned here is the SEAM and the DISCIPLINE:

  a plan that cannot be drafted from says why, before any producer runs   → §1
  drafting RE-BINDS the stored plan; a stale `supported` is not trusted   → §2
  the whole path: accepted plan → executed chain → prose → live percepts  → §3
  the stored draft is quarantined, and the guard refuses anything else    → §4
  what Accept carries into the manuscript, and what it refuses to carry   → §5
  a refusal reaches the reader as a limit, never as a finding             → §6

Every fixture is SYNTHETIC. No real post, no real model, no GPU: the chain runs on
`StubActuator`s through `run_corpus_plan`'s injectable registry, and the composer is a `FakeLLM`.
"""
from __future__ import annotations

import copy
import json
import re

import pytest

from backend.services import atlas_draft as D
from backend.services import atlas_service as A
from backend.services.director import composition as M
from backend.services.director.argument import CHALLENGE, SUPPORT, make_claim, plan_argument
from backend.services.director.corpus import build_corpus, hydrate_corpus
from backend.services.director.corpus_execution import build_corpus_context, run_corpus_plan
from backend.services.director.execution import StubActuator


# ── fixtures ─────────────────────────────────────────────────────────────────

class _UpdateResult:
    def __init__(self, matched, modified):
        self.matched_count = matched
        self.modified_count = modified


class FakeCollection:
    """Declared again rather than imported, for the reason C4's file gives: a test that breaks when
    another test file is renamed is a test about the wrong thing."""

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


def a_post(post_id, *, regions=()):
    return {"_id": post_id, "photo_url": f"https://example.invalid/{post_id}.jpg",
            "instagram_handle": f"handle_{post_id}",
            "region_annotations": [{"id": r} for r in regions],
            "visual_marks": [], "grounds": [], "percepts": []}


def a_memory(*post_ids, **evidence):
    corpus = build_corpus(corpus_id="atlas_1", title="the walk",
                          images=[{"post_id": p, "photo_url": f"u_{p}"} for p in post_ids])
    posts = {p: a_post(p, **evidence.get(p, {})) for p in post_ids}
    return corpus, hydrate_corpus(corpus, posts), posts


def an_atlas(*post_ids, plan=None, draft=None):
    doc = {"_id": "atlas_1", "title": "the walk",
           "nodes": [{"node_id": f"n{i}", "post_id": pid, "x": 0.0, "y": 0.0}
                     for i, pid in enumerate(post_ids)]}
    if plan is not None:
        doc["plan"] = plan
    if draft is not None:
        doc["draft"] = draft
    return doc


def a_stored_plan(*, claims=None, thesis="the sequence disperses what the rotunda gathers"):
    """C4's stored-plan shape, reduced to the fields C5 reads."""
    return {"thesis": thesis, "accepted": True, "claims": claims if claims is not None else [
        {"claim_id": "c0", "text": "the field disperses", "status": "supported", "struck": False,
         "percepts": [{"step_id": "c0:0:negative_space", "actuator": "negative_space",
                       "function": SUPPORT, "image": "p1", "bound": True, "params": {}}]}]}


class FakeLLM(M.LLM):
    """A composer stand-in that grounds its prose in whatever evidence the prompt offered.

    It reads the ids back out of the prompt rather than being handed them, so the intersection
    guard (M3's rule 2) is exercised for real: a stand-in that returned ids nobody offered would
    be testing the guard, and one handed the right answer would be testing nothing.
    """

    def __init__(self, prose="The field concentrates toward one side of the frame.",
                 ground=True, relevance=None):
        super().__init__(client=None, model="fake/composer")
        self.prose = prose
        self.ground = ground
        self.relevance = relevance or []
        self.prompts = []

    def complete(self, system, user):
        self.prompts.append(user)
        # The evidence rows are rendered with `json.dumps(..., indent=2)`, so each id sits on its
        # own line. The response template's `"<evidence id>"` placeholder is skipped.
        ids = [i for i in re.findall(r'"id":\s*"([^"]+)"', user) if not i.startswith("<")]
        return json.dumps({"prose": self.prose, "grounded_in": ids if self.ground else [],
                           "relevance": self.relevance, "qualified": False,
                           "thesis": self.prose})


def stub_registry_for(name_to_stub=None):
    """Every actuator on every image, stubbed. No GPU, no network, no database."""
    def _for(_post_id):
        from backend.services.director.capabilities import known
        return {name: (name_to_stub or {}).get(name) or StubActuator(name) for name in known()}
    return _for


def compose_over(atlas, memory, corpus, posts, *, llm=None, registry_for=None):
    """The route's own path, minus FastAPI: re-bind, execute, compose, resolve."""
    argument, notes = D.argument_from_stored_plan(atlas, memory)
    cctx = build_corpus_context(corpus, posts, run_id="atlas:test:draft")
    try:
        chain = run_corpus_plan(argument.plan, memory, cctx,
                                registry_for=registry_for or stub_registry_for(),
                                chain_id="atlas:test:draft")
        article = D.compose_from_chain(argument, memory, provenance=chain.provenance,
                                       suggestions=cctx.all_suggestions(),
                                       run_id="atlas:test:draft", llm=llm or FakeLLM())
    finally:
        cctx.close()
    return argument, article, notes


# ── 1. a plan that cannot be drafted from says why ───────────────────────────

def test_an_atlas_with_no_plan_is_blocked_before_any_producer_runs():
    assert D.draft_blocker(an_atlas("p1")) == D.BLOCK_NO_PLAN


def test_an_atlas_with_no_images_is_blocked_ahead_of_its_plan():
    """Most-fundamental-first. An Atlas spanning nothing cannot be fixed by editing the plan, so
    reporting the plan's emptiness would send the writer to the wrong surface."""
    assert D.draft_blocker(an_atlas(plan=a_stored_plan())) == D.BLOCK_NO_IMAGES


def test_a_plan_of_nothing_but_struck_claims_is_a_refusal_already_delivered():
    plan = a_stored_plan(claims=[{"claim_id": "c0", "text": "x", "struck": True, "percepts": []}])
    assert D.draft_blocker(an_atlas("p1", plan=plan)) == D.BLOCK_ALL_REFUSED


def test_a_plan_with_no_claims_is_blocked():
    assert D.draft_blocker(an_atlas("p1", plan=a_stored_plan(claims=[]))) == D.BLOCK_NO_CLAIMS


def test_a_drafable_plan_reports_no_blocker():
    assert D.draft_blocker(an_atlas("p1", plan=a_stored_plan())) is None


def test_every_blocker_has_a_sentence_a_writer_can_read():
    for reason in (D.BLOCK_NO_PLAN, D.BLOCK_NO_IMAGES, D.BLOCK_NO_CLAIMS, D.BLOCK_ALL_REFUSED):
        assert D.blocker_text(reason) != reason and D.blocker_text(reason).endswith(".")


# ── 2. drafting re-binds; the stored statuses are trusted by nobody ──────────

def test_drafting_rebinds_the_stored_plan_against_the_corpus_as_it_is_now():
    """The plan says `supported`. The image it named has since lost the evidence that carried it.
    The re-bind is what makes the prose describe the corpus rather than the memory of one."""
    _, memory, _ = a_memory("p1")                      # no regions: nothing to carry a claim
    plan = a_stored_plan(claims=[{
        "claim_id": "c0", "text": "the field disperses", "status": "supported", "struck": False,
        "percepts": [{"step_id": "c0:0:find_parts", "actuator": "find_parts",
                      "function": SUPPORT, "image": "p1", "bound": True, "params": {}}]}])
    argument, _ = D.argument_from_stored_plan(an_atlas("p1", plan=plan), memory)

    assert argument is not None
    # Re-judged, not read back: whatever the document said, the status is the gate's answer now.
    assert argument.claims[0].status != "supported" or argument.claims[0].binding != "confirmed"


def test_a_stored_plan_whose_claims_cannot_be_rebuilt_returns_no_argument_and_says_so():
    _, memory, _ = a_memory("p1")
    argument, notes = D.argument_from_stored_plan(
        an_atlas("p1", plan={"thesis": "t", "claims": ["not a claim"]}), memory)
    assert argument is None
    assert any("no claims" in n for n in notes)


# ── 3. the whole path: plan → executed chain → prose → live percepts ─────────

def test_an_accepted_plan_becomes_prose_resting_on_percepts_that_really_ran():
    corpus, memory, posts = a_memory("p1", "p2", p1={"regions": ["r1"]})
    plan = a_stored_plan(claims=[{
        "claim_id": "c0", "text": "the field disperses", "status": "supported", "struck": False,
        "percepts": [{"step_id": "c0:0:negative_space", "actuator": "negative_space",
                      "function": SUPPORT, "image": "p1", "bound": True, "params": {}}]}])
    _, article, _ = compose_over(an_atlas("p1", "p2", plan=plan), memory, corpus, posts)

    draft = article["draft"]
    assert draft["sections"], "an executed, bound claim should have composed a section"
    assert draft["sections"][0]["prose"]
    # Every cited step resolved to something a renderer can draw or honestly refuse to.
    assert article["counts"]["citations"] >= 1
    assert set(article["resolved"]) == {c["step_id"] for c in draft["sections"][0]["citations"]}


def test_a_cited_percept_resolves_to_live_geometry_on_its_own_source_image():
    """The C5 promise: a sentence's evidence is a LIVE percept, drawn from its own geometry on its
    own image, reopenable there. Not a screenshot, and not a citation that merely looks like one."""
    corpus, memory, posts = a_memory("p1", p1={"regions": ["r1"]})
    argument, _ = D.argument_from_stored_plan(an_atlas("p1", plan=a_stored_plan()), memory)
    cctx = build_corpus_context(corpus, posts, run_id="r")
    chain = run_corpus_plan(argument.plan, memory, cctx, registry_for=stub_registry_for(),
                            chain_id="r")
    # The shape a real producer mints: a drawable type, the post it ran on, and the step that
    # made it stamped on the provenance (PROV-001's exact join).
    produced = [{
        "type": "brush_field", "producer": "negative_space", "post_id": "p1",
        "source_ref": "sug_1", "label": "the open field",
        "geometry": {"kind": "brush_field", "cells": [[0, 0, 0.4]]},
        "provenance": {"step_id": "c0:0:negative_space", "adapter": "negative_space"},
    }]
    article = D.compose_from_chain(argument, memory, provenance=chain.provenance,
                                   suggestions=produced, run_id="r", llm=FakeLLM())
    cctx.close()

    citation = article["resolved"]["c0:0:negative_space"]
    assert citation["status"] == "resolved" and citation["drawable"] is True
    assert citation["geometry"] == {"kind": "brush_field", "cells": [[0, 0, 0.4]]}
    assert citation["image_ref"], "a live percept must know the image it is drawn on"
    assert citation["reopen"] == {"post_id": "p1", "source_ref": "sug_1",
                                  "step_id": "c0:0:negative_space"}


def test_a_citation_with_no_produced_percept_is_admitted_rather_than_drawn_empty():
    corpus, memory, posts = a_memory("p1", p1={"regions": ["r1"]})
    _, article, _ = compose_over(an_atlas("p1", plan=a_stored_plan()), memory, corpus, posts)
    citation = article["resolved"]["c0:0:negative_space"]
    assert citation["status"] == "unproduced" and citation["drawable"] is False
    assert citation["detail"], "an unresolved citation must say why, not just fail to draw"


def test_the_composed_article_is_never_committed():
    corpus, memory, posts = a_memory("p1", p1={"regions": ["r1"]})
    _, article, _ = compose_over(an_atlas("p1", plan=a_stored_plan()), memory, corpus, posts)
    assert article["draft"]["committed"] is False


def test_an_unavailable_producer_leaves_a_claim_uncomposed_rather_than_narrated():
    """The failure this whole layer exists for: a producer that came back empty must not end up
    behind a fluent paragraph. It reaches the reader as an uncomposed claim."""
    corpus, memory, posts = a_memory("p1", p1={"regions": ["r1"]})
    down = stub_registry_for({"negative_space": StubActuator("negative_space", unavailable=True)})
    _, article, _ = compose_over(an_atlas("p1", plan=a_stored_plan()), memory, corpus, posts,
                                 registry_for=down)

    draft = article["draft"]
    composed = [s for s in draft["sections"] if s.get("prose")]
    assert not composed or draft["uncomposed"], (
        "a claim whose producer was down must not read as a composed section")


# ── 4. the stored draft is quarantined ───────────────────────────────────────

def test_a_stored_draft_is_quarantined_and_says_so():
    stored = D.stored_draft({"draft": {"thesis": "t", "committed": False}}, thesis="t",
                            run_id="r", now="2026-08-05T00:00:00Z")
    assert stored["state"] == D.DRAFT_QUARANTINED
    assert stored["committed"] is False
    D.assert_draft_is_quarantined(stored)


def test_the_guard_refuses_a_draft_that_claims_to_be_committed():
    stored = D.stored_draft({"draft": {"thesis": "t"}}, run_id="r")
    stored["committed"] = True
    with pytest.raises(ValueError, match="never be `committed`"):
        D.assert_draft_is_quarantined(stored)


def test_the_guard_refuses_a_draft_whose_inner_composition_says_it_is_committed():
    stored = D.stored_draft({"draft": {"thesis": "t", "committed": True}}, run_id="r")
    stored["committed"] = False                   # the outer flag lies; the inner one is checked
    with pytest.raises(ValueError, match="stopped calling itself a proposal"):
        D.assert_draft_is_quarantined(stored)


def test_the_guard_refuses_a_draft_stored_in_any_state_but_quarantined():
    stored = D.stored_draft({"draft": {"thesis": "t"}}, run_id="r")
    stored["state"] = D.DRAFT_ACCEPTED
    with pytest.raises(ValueError, match="must be 'quarantined'"):
        D.assert_draft_is_quarantined(stored)


def test_saving_a_draft_leaves_the_plan_and_the_nodes_alone():
    async def run():
        coll = FakeCollection()
        await coll.insert_one(an_atlas("p1", "p2", plan=a_stored_plan()))
        stored = D.stored_draft({"draft": {"thesis": "t"}}, run_id="r")
        doc = await A.save_draft("atlas_1", stored, collection=coll)
        assert doc["draft"]["state"] == D.DRAFT_QUARANTINED
        assert doc["plan"]["thesis"]                       # C4's seed survives C5's write
        assert [n["post_id"] for n in doc["nodes"]] == ["p1", "p2"]

        cleared = await A.save_draft("atlas_1", None, collection=coll)
        assert cleared["draft"] is None and cleared["plan"]["thesis"]
    import asyncio
    asyncio.run(run())


# ── 5. what Accept carries into the manuscript ───────────────────────────────

def an_article(**draft):
    base = {"thesis": "the sequence disperses", "thesis_prose": "An opening.", "sections": [],
            "uncomposed": [], "qualifications": [], "counter_reading": None, "committed": False}
    base.update(draft)
    return {"draft": base, "resolved": {}, "counts": {}}


def test_a_composed_section_crosses_with_the_step_ids_it_rests_on():
    """The citation is the paragraph's provenance, not decoration. Dropping it here is where
    evidence-bound prose would quietly become ordinary prose."""
    article = an_article(sections=[{
        "claim_id": "c0", "claim": "the field disperses", "prose": "One paragraph.\n\nAnother.",
        "epistemic": "measured", "function": SUPPORT,
        "citations": [{"step_id": "c0:0:negative_space"}], "caveats": [], "qualified": False}])
    section = [p for p in D.passages(article) if p["kind"] == "section"][0]
    assert section["paragraphs"] == ["One paragraph.", "Another."]
    assert section["cites"] == ["c0:0:negative_space"]
    assert section["epistemic"] == "measured"


def test_a_sections_caveats_cross_with_it():
    """A section that admitted something on the canvas admits it in the manuscript, or Accept was
    a way of laundering the admission."""
    article = an_article(sections=[{
        "claim_id": "c0", "claim": "c", "prose": "P.", "citations": [],
        "caveats": ["rhythm does not bear on this claim"], "qualified": True}])
    section = [p for p in D.passages(article) if p["kind"] == "section"][0]
    assert section["caveats"] == ["rhythm does not bear on this claim"]
    assert section["qualified"] is True


def test_a_grounded_counter_reading_crosses_and_an_ungrounded_one_does_not():
    grounded = an_article(counter_reading={"grounded": True, "prose": "But the rotunda.",
                                           "citations": [{"step_id": "c1:0:rhythm"}]})
    assert any(p["kind"] == "counter" for p in D.passages(grounded))

    absent = an_article(counter_reading={"grounded": False, "absence_detail": "none produced",
                                         "absence_reason": M.COUNTER_NOT_PRODUCED})
    assert not any(p["kind"] == "counter" for p in D.passages(absent))


def test_the_text_blocks_carry_the_citation_without_putting_it_in_the_prose():
    blocks = D.passages_to_text_blocks([
        {"kind": "section", "heading": "the field disperses", "paragraphs": ["One."],
         "cites": ["c0:0:negative_space"], "caveats": []}])
    assert blocks[0]["type"] == "heading"
    assert 'data-cites="c0:0:negative_space"' in blocks[1]["content"]
    assert "One." in blocks[1]["content"]


def test_text_blocks_escape_prose_that_contains_markup():
    blocks = D.passages_to_text_blocks([
        {"kind": "section", "heading": "", "paragraphs": ["<script>alert(1)</script>"],
         "cites": [], "caveats": []}])
    assert "<script>" not in blocks[0]["content"]
    assert "&lt;script&gt;" in blocks[0]["content"]


# ── 6. a refusal reaches the reader as a limit, never as a finding ──────────

def test_a_qualification_crosses_as_a_limit_and_not_as_body_text():
    article = an_article(
        sections=[{"claim_id": "c0", "claim": "c", "prose": "P.", "citations": [], "caveats": []}],
        qualifications=[{"claim_id": "c1", "status": "refused",
                         "prose": "The corpus could not carry the second claim."}])
    items = D.passages(article)
    kinds = [p["kind"] for p in items]
    assert kinds[-1] == "limits", "limits come last; a limit beside a finding reads as a finding"
    assert "could not carry" in items[-1]["paragraphs"][0]
    assert not any("could not carry" in " ".join(p["paragraphs"])
                   for p in items if p["kind"] == "section")


def test_an_uncomposed_claim_crosses_as_a_limit_saying_why_it_was_not_written():
    article = an_article(uncomposed=[{"claim_id": "c1", "claim": "the rotunda gathers",
                                      "reason": M.SECTION_CITES_NOTHING, "detail": "d"}])
    lines = D.limit_lines(article)
    assert any("the rotunda gathers" in line and "not written" in line for line in lines)


def test_an_ungrounded_counter_reading_is_stated_as_an_absence():
    article = an_article(counter_reading={"grounded": False,
                                          "absence_detail": "the challenge percept never arrived",
                                          "absence_reason": M.COUNTER_NOT_PRODUCED})
    assert "never arrived" in " ".join(D.limit_lines(article))


def test_a_draft_that_composed_nothing_yields_no_passages_to_accept():
    """Nothing to accept is not an empty manuscript — the route refuses, and this is what it
    branches on."""
    article = an_article(thesis="", thesis_prose="")
    assert D.passages(article) == []
