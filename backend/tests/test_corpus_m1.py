"""
CIRCUIT-003 M1 — multi-image corpus + cross-image comparative percept.

Stub-driven end to end: no GPU, no network, no database, no language model. The corpus fixture is
a two-image stand-in for the sequence the benchmark actually walks (a dispersed civic ground, then
a centralized rotunda), which is enough to exercise every claim M1 makes — a third image adds
images, not mechanisms.

The three facts this gate exists to prove, and where each is asserted:

  1. A comparative relation references REAL marks on TWO images  → TestCompareViews
  2. A corpus hydrates ALL its images' committed marks           → TestHydration
  3. Cross-image provenance traces BOTH sources                  → TestCrossImageProvenance

Plus the two that keep it honest rather than merely working: comparison is REFUSED on a single
image (TestRefusalOnOneImage), and the single-post path is untouched (TestSinglePostPathUnchanged).
"""
from __future__ import annotations

import pytest

from backend.services.director import capabilities as caps
from backend.services.director import corpus as C
from backend.services.director import real_actuators as ra
from backend.services.director.corpus_execution import (CorpusExecutionContext,
                                                        build_corpus_context, run_corpus_plan)
from backend.services.director.execution import EMPTY, OK, SKIPPED, UNAVAILABLE, stub_registry
from backend.services.director.capabilities import Resource
from backend.services.director.memory import build_memory
from backend.services.director.plan import Step, resolve

GROUND = "post_ground"          # the Lustgarten: a dispersed civic ground
ROTUNDA = "post_rotunda"        # the rotunda: centralized


# ── fixtures: post documents and a two-image corpus ──────────────────────────

def _mark(mid: str, label: str) -> dict:
    return {"id": mid, "label": label, "type": "brush_field", "status": "committed"}


def _region(rid: str) -> dict:
    return {"id": rid, "box": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4}}


def posts_fixture() -> dict:
    return {
        GROUND: {
            "photo_url": "http://x/lustgarten.jpg",
            "region_annotations": [_region("r_lawn"), _region("r_steps")],
            "visual_marks": [_mark("m_dispersal", "the ground spreads"),
                             _mark("m_low_horizon", "a low horizon")],
            "grounds": [], "percepts": [],
        },
        ROTUNDA: {
            "photo_url": "http://x/rotunda.jpg",
            "region_annotations": [_region("r_dome")],
            "visual_marks": [_mark("m_centre", "everything turns to the centre")],
            "grounds": [], "percepts": [],
        },
    }


def corpus_fixture() -> C.Corpus:
    return C.build_corpus(
        corpus_id="altes-museum",
        title="Lustgarten to rotunda",
        why="The walk from a dispersed civic ground to a centralized interior.",
        images=[{"post_id": GROUND, "photo_url": "http://x/lustgarten.jpg",
                 "title": "Lustgarten", "note": "the ground the building addresses"},
                {"post_id": ROTUNDA, "photo_url": "http://x/rotunda.jpg",
                 "title": "Rotunda", "note": "where the walk ends"}])


def hydrated() -> C.CorpusWorkingMemory:
    return C.hydrate_corpus(corpus_fixture(), posts_fixture())


def suggestion(post_id: str, ref: str, label: str) -> dict:
    """A quarantined mark as a producer would leave it — what a comparative step must cite."""
    return {"producer": "rhythm", "type": "brush_field", "role": "rhythm", "label": label,
            "source_ref": ref, "geometry": {"kind": "raster"}, "linked_ground_ids": [],
            "provenance": {"run_id": "run_x", "producer": "rhythm", "post_id": post_id}}


def loaded_context(*, both: bool = True) -> CorpusExecutionContext:
    """A corpus context whose per-image quarantines already hold real marks — the state a run
    reaches after each image's finder has actually produced something."""
    cctx = build_corpus_context(corpus_fixture(), posts_fixture(), run_id="run_x")
    cctx.contexts[GROUND].suggestions.append(
        suggestion(GROUND, "sug_dispersal", "the ground spreads"))
    if both:
        cctx.contexts[ROTUNDA].suggestions.append(
            suggestion(ROTUNDA, "sug_centre", "everything turns to the centre"))
    return cctx


# ── 1. the corpus model ──────────────────────────────────────────────────────

class TestCorpusModel:

    def test_the_order_is_the_argument(self):
        """A corpus is a SEQUENCE. Positions come from the caller's order and are not renumbered,
        because the order carries the claim (ground, then rotunda — not the reverse)."""
        corpus = corpus_fixture()
        assert corpus.post_ids == (GROUND, ROTUNDA)
        assert [i.position for i in corpus.images] == [0, 1]
        assert corpus.at(1).post_id == ROTUNDA

    def test_an_image_is_addressable_by_id_and_by_position(self):
        corpus = corpus_fixture()
        assert corpus.resolve_target(ROTUNDA).post_id == ROTUNDA
        assert corpus.resolve_target(1).post_id == ROTUNDA
        assert corpus.resolve_target("1").post_id == ROTUNDA      # survived a JSON round-trip

    def test_an_image_this_corpus_does_not_hold_is_none_not_the_first_one(self):
        """None is a refusal upstream. Silently retargeting a step at a different photograph is
        the exact substitution this layer exists to make impossible."""
        assert corpus_fixture().resolve_target("post_elsewhere") is None
        assert corpus_fixture().resolve_target(9) is None


# ── 2. hydration — the corpus carries every image's committed evidence ───────

class TestHydration:

    def test_a_corpus_hydrates_all_its_images_committed_marks(self):
        """THE CLAIM: hydrating a corpus loads every image's marks, not the focus image's."""
        memory = hydrated()
        assert memory.marks_on(GROUND) == ("m_dispersal", "m_low_horizon")
        assert memory.marks_on(ROTUNDA) == ("m_centre",)
        assert memory.available()[Resource.MARK] == 3          # 2 + 1, none lost, none doubled
        assert memory.available()[Resource.REGION] == 3

    def test_every_merged_id_still_knows_which_image_it_came_from(self):
        memory = hydrated()
        assert memory.origin_of(C.namespaced(ROTUNDA, "m_centre")) == ROTUNDA
        assert set(memory.images_represented(memory.mark_ids)) == {GROUND, ROTUNDA}

    def test_ids_that_collide_across_posts_are_not_collapsed(self):
        """Mark ids are minted per post, so two images sharing one is the normal case. A merged
        packet that collapsed them would under-count exactly the evidence a comparison rests on."""
        posts = posts_fixture()
        posts[ROTUNDA]["visual_marks"] = [_mark("m_dispersal", "a different mark, same id")]
        memory = C.hydrate_corpus(corpus_fixture(), posts)
        assert memory.available()[Resource.MARK] == 3
        assert len(set(memory.mark_ids)) == 3

    def test_the_image_count_is_the_number_of_images(self):
        """The one override that makes comparison refusable by the EXISTING gate."""
        assert hydrated().available()[Resource.IMAGE] == 2
        assert build_memory(image_ref="i", post_id=GROUND).available()[Resource.IMAGE] == 1

    def test_an_unreadable_post_is_named_never_read_as_an_empty_image(self):
        """'The rotunda has no marks' and 'the rotunda could not be loaded' are different facts,
        and a comparison built on the second while believing the first is the failure mode."""
        memory = C.hydrate_corpus(corpus_fixture(), {GROUND: posts_fixture()[GROUND]})
        assert f"post:{ROTUNDA}" in memory.unreadable
        assert memory.marks_on(ROTUNDA) == ()
        assert memory.available()[Resource.MARK] == 2          # only what was actually read


# ── 3. the capability declaration ────────────────────────────────────────────

class TestComparativeCapabilities:

    def test_the_comparative_actuators_are_declared_and_discoverable(self):
        assert set(caps.comparative()) == {"compare_views", "compose_comparative_percept"}
        assert caps.is_comparative("compare_views")
        assert not caps.is_comparative("connect_marks")

    def test_compare_views_needs_two_images_and_two_marks(self):
        act = caps.ACTUATORS["compare_views"]
        by_kind = {r.kind: r.min_count for r in act.requires}
        assert by_kind[Resource.IMAGE] == 2, "a comparison of one picture is not a comparison"
        assert by_kind[Resource.MARK] == 2

    def test_connect_marks_is_left_exactly_as_it_was(self):
        """M1 adds a sibling; it does not widen the single-image relation half the suite pins."""
        act = caps.ACTUATORS["connect_marks"]
        assert act.spans_images == 1
        assert {r.kind for r in act.requires} == {Resource.MARK}

    def test_the_comparative_percept_rests_on_a_named_relation(self):
        act = caps.ACTUATORS["compose_comparative_percept"]
        by_kind = {r.kind: r.min_count for r in act.requires}
        assert by_kind[Resource.GROUND] == 1
        assert by_kind[Resource.IMAGE] == 2
        assert act.produces == (Resource.PERCEPT,)

    def test_both_are_wired_to_an_in_process_runner(self):
        assert sorted(set(caps.known()) - set(ra._DISPATCH)) == []


# ── 4. planning across the corpus ────────────────────────────────────────────

class TestCorpusPlanning:

    def test_a_step_can_target_a_specific_image(self):
        memory = hydrated()
        plan = C.resolve_corpus(C.corpus_steps(
            ("rhythm", {"image": ROTUNDA}),
            ("rhythm", {"image": GROUND})), memory, intention="read both")
        assert [s.params["image"] for s in plan.steps] == [GROUND, ROTUNDA]   # corpus order
        assert not plan.refused

    def test_an_untargeted_step_lands_on_the_focus_image_and_says_so(self):
        plan = C.resolve_corpus(C.corpus_steps(("rhythm", {})), hydrated())
        assert plan.steps[0].params["image"] == GROUND       # focus = first in the sequence

    def test_a_step_naming_an_image_the_corpus_lacks_is_refused_by_name(self):
        plan = C.resolve_corpus(C.corpus_steps(("rhythm", {"image": "post_elsewhere"})),
                                hydrated())
        assert plan.steps == ()
        assert plan.refused[0].reason == C.REFUSED_UNKNOWN_IMAGE
        assert "post_elsewhere" in plan.refused[0].detail

    def test_a_targeted_step_is_checked_against_ITS_image_not_the_union(self):
        """The refusal that a merged-counts-only corpus would lose: the rotunda has a region, the
        third image does not, and a field on the third must not resolve on the rotunda's."""
        corpus = C.build_corpus(corpus_id="c", images=[GROUND, ROTUNDA, "post_bare"])
        memory = C.hydrate_corpus(corpus, {**posts_fixture(), "post_bare": {"photo_url": "b"}})
        plan = C.resolve_corpus(C.corpus_steps(
            ("negative_space", {"image": "post_bare"})), memory)     # needs a REGION
        assert plan.steps == ()
        assert plan.refused[0].reason == "missing_input"
        assert "region" in plan.refused[0].detail

    def test_a_comparative_step_is_planned_after_the_per_image_steps_that_feed_it(self):
        """'Find the parts on both, then compare them' resolves: the comparative tier is planned
        against the merged packet PROJECTED FORWARD by what the image tier will produce."""
        corpus = corpus_fixture()
        bare = {GROUND: {"photo_url": "a"}, ROTUNDA: {"photo_url": "b"}}   # no committed marks
        memory = C.hydrate_corpus(corpus, bare)
        plan = C.resolve_corpus(C.corpus_steps(
            ("compare_views", {"relation_role": "contrast"}),          # asked for FIRST
            ("find_parts", {"image": GROUND}),
            ("find_parts", {"image": ROTUNDA})), memory, intention="compare the two")
        assert [s.actuator for s in plan.steps] == ["find_parts", "find_parts", "compare_views"]
        assert not plan.refused
        assert plan.reordered

    def test_a_comparative_step_cannot_be_pinned_to_one_image(self):
        plan = C.resolve_corpus(C.corpus_steps(
            ("compare_views", {"image": GROUND, "relation_role": "contrast"})), hydrated())
        assert plan.steps == ()
        assert plan.refused[0].reason == C.REFUSED_IMAGE_SCOPE

    def test_the_full_comparative_chain_resolves_in_order(self):
        plan = C.resolve_corpus(C.corpus_steps(
            ("compose_comparative_percept", {"draft_text": "x"}),
            ("compare_views", {"relation_role": "contrast"})), hydrated())
        assert [s.actuator for s in plan.steps] == ["compare_views",
                                                    "compose_comparative_percept"]
        assert not plan.refused


# ── 5. refusal on a single image — the honesty half ──────────────────────────

class TestRefusalOnOneImage:

    def test_comparison_is_refused_on_a_single_post_by_the_existing_gate(self):
        """No corpus-aware branch in `plan.py` does this: a single-image packet reports IMAGE: 1,
        and `2× image` is an ordinary unmet requirement."""
        plan = resolve([Step(actuator="compare_views", id="s1",
                             params={"relation_role": "contrast"})],
                       build_memory(image_ref="i", post_id=GROUND,
                                    mark_ids=("m1", "m2", "m3")))
        assert plan.steps == ()
        assert plan.refused[0].reason == "missing_input"
        assert "image" in plan.refused[0].detail

    def test_a_one_image_corpus_refuses_comparison_too(self):
        memory = C.hydrate_corpus(C.build_corpus(corpus_id="one", images=[GROUND]),
                                  {GROUND: posts_fixture()[GROUND]})
        plan = C.resolve_corpus(C.corpus_steps(("compare_views", {})), memory)
        assert plan.steps == ()
        assert plan.refused[0].reason == "missing_input"

    def test_the_runner_refuses_at_dispatch_when_only_one_image_produced_marks(self):
        """The plan proved two images would carry marks; this proves they DO. They differ exactly
        when one image's finder came back empty — and a same-image consolation pair there would be
        a well-formed relation answering a question nobody asked."""
        cctx = loaded_context(both=False)
        try:
            res = cctx.loop.run_until_complete(ra._run_compare_views(
                Step(actuator="compare_views", id="s1", params={"relation_role": "contrast"}),
                hydrated(), cctx, caps.ACTUATORS["compare_views"]))
            assert res.status == EMPTY
            assert "2 images" in res.detail
            assert cctx.comparative == []
        finally:
            cctx.close()

    def test_a_single_post_context_cannot_produce_a_cross_image_relation(self):
        ctx = ra.ExecutionContext(post_id=GROUND, post=posts_fixture()[GROUND])
        try:
            ctx.suggestions.append(suggestion(GROUND, "a", "one"))
            ctx.suggestions.append(suggestion(GROUND, "b", "two"))
            res = ctx.loop.run_until_complete(ra._run_compare_views(
                Step(actuator="compare_views", id="s1", params={"relation_role": "contrast"}),
                build_memory(image_ref="i", post_id=GROUND), ctx,
                caps.ACTUATORS["compare_views"]))
            assert res.status == EMPTY          # two marks, but one picture
        finally:
            ctx.close()


# ── 6. the cross-image comparative relation ─────────────────────────────────

class TestCompareViews:

    def test_a_comparative_relation_references_real_marks_on_two_images(self):
        """THE CLAIM: the relation cites marks that actually exist, on two different images."""
        cctx = loaded_context()
        try:
            res = cctx.loop.run_until_complete(ra._run_compare_views(
                Step(actuator="compare_views", id="s1", params={"relation_role": "contrast"}),
                hydrated(), cctx, caps.ACTUATORS["compare_views"]))
            assert res.status == OK
            assert res.produced == (Resource.GROUND,)

            rel = cctx.comparative[0]
            assert rel["type"] == "relation_mark"
            assert rel["role"] == "contrast"
            assert rel["geometry"]["cross_image"] is True
            assert rel["geometry"]["endpoints"] == [f"{GROUND}:sug_dispersal",
                                                    f"{ROTUNDA}:sug_centre"]
            assert sorted(rel["corpus"]["spans"]) == sorted([GROUND, ROTUNDA])

            # the refs are REAL: each names a mark actually in that image's quarantine
            by_image = cctx.marks_by_image()
            for src in rel["provenance"]["sources"]:
                refs = [m["source_ref"] for m in by_image[src["post_id"]]]
                assert src["mark_ref"] in refs
        finally:
            cctx.close()

    def test_explicit_refs_choose_the_two_sides(self):
        cctx = loaded_context()
        try:
            cctx.contexts[ROTUNDA].suggestions.append(
                suggestion(ROTUNDA, "sug_other", "another mark on the rotunda"))
            res = cctx.loop.run_until_complete(ra._run_compare_views(
                Step(actuator="compare_views", id="s1",
                     params={"relation_role": "contrast", "left_ref": "sug_dispersal",
                             "right_ref": "sug_other"}),
                hydrated(), cctx, caps.ACTUATORS["compare_views"]))
            assert res.status == OK
            assert cctx.comparative[0]["geometry"]["endpoints"][1] == f"{ROTUNDA}:sug_other"
        finally:
            cctx.close()

    def test_the_relation_role_stays_inside_the_frozen_vocabulary(self):
        """A model that invents a relation name cannot put an unknown role on a mark."""
        cctx = loaded_context()
        try:
            cctx.loop.run_until_complete(ra._run_compare_views(
                Step(actuator="compare_views", id="s1",
                     params={"relation_role": "totally vibes with"}),
                hydrated(), cctx, caps.ACTUATORS["compare_views"]))
            assert cctx.comparative[0]["role"] == "address_relation"   # the frozen default
        finally:
            cctx.close()

    def test_a_comparative_suggestion_is_filed_under_neither_post(self):
        """A relation joining the two belongs to the sequence. Filing it on one image's pile would
        make it read, to every later reader, as something found in that photograph."""
        cctx = loaded_context()
        try:
            before = {p: len(c.suggestions) for p, c in cctx.contexts.items()}
            cctx.loop.run_until_complete(ra._run_compare_views(
                Step(actuator="compare_views", id="s1", params={"relation_role": "contrast"}),
                hydrated(), cctx, caps.ACTUATORS["compare_views"]))
            assert {p: len(c.suggestions) for p, c in cctx.contexts.items()} == before
            assert len(cctx.comparative) == 1
        finally:
            cctx.close()


# ── 7. the comparative percept, and provenance that traces both sources ─────

class TestCrossImageProvenance:

    def _run_chain(self, cctx):
        cctx.loop.run_until_complete(ra._run_compare_views(
            Step(actuator="compare_views", id="s1", params={"relation_role": "contrast"}),
            hydrated(), cctx, caps.ACTUATORS["compare_views"]))
        return cctx.loop.run_until_complete(ra._run_compose_comparative_percept(
            Step(actuator="compose_comparative_percept", id="s2",
                 params={"draft_text": "The ground disperses what the rotunda gathers."}),
            hydrated(), cctx, caps.ACTUATORS["compose_comparative_percept"]))

    def test_cross_image_provenance_traces_both_sources(self):
        """THE CLAIM: from the percept alone, a reader can reach the evidence on BOTH images."""
        cctx = loaded_context()
        try:
            res = self._run_chain(cctx)
            assert res.status == OK
            percept = cctx.comparative[-1]
            sources = percept["provenance"]["sources"]
            assert [s["post_id"] for s in sources] == [GROUND, ROTUNDA]
            assert [s["image_ref"] for s in sources] == ["http://x/lustgarten.jpg",
                                                         "http://x/rotunda.jpg"]
            assert [s["mark_ref"] for s in sources] == ["sug_dispersal", "sug_centre"]
            assert [s["position"] for s in sources] == [0, 1]      # where each stood in the walk
        finally:
            cctx.close()

    def test_the_percept_rests_on_the_named_relation_and_says_which(self):
        cctx = loaded_context()
        try:
            self._run_chain(cctx)
            relation, percept = cctx.comparative[0], cctx.comparative[1]
            assert percept["type"] == "percept_draft"
            assert percept["provenance"]["rests_on"] == relation["source_ref"]
            assert relation["source_ref"] in percept["ground_refs"]
            assert f"{GROUND}:sug_dispersal" in percept["ground_refs"]
            assert f"{ROTUNDA}:sug_centre" in percept["ground_refs"]
            assert percept["geometry"] is None          # a percept has no extent
        finally:
            cctx.close()

    def test_a_comparative_percept_refuses_without_a_relation_to_rest_on(self):
        """A sentence about two photographs that was not grounded in a relation somebody named is
        a comparison in grammar only, and looks identical to one that was earned."""
        cctx = loaded_context()
        try:
            res = cctx.loop.run_until_complete(ra._run_compose_comparative_percept(
                Step(actuator="compose_comparative_percept", id="s1",
                     params={"draft_text": "a confident sentence"}),
                hydrated(), cctx, caps.ACTUATORS["compose_comparative_percept"]))
            assert res.status == EMPTY
            assert "no cross-image relation" in res.detail
        finally:
            cctx.close()

    def test_a_same_image_relation_does_not_satisfy_the_comparative_percept(self):
        """`connect_marks` produces a relation too. It is not a cross-image one, and a comparative
        percept resting on it would claim a span it never had."""
        cctx = loaded_context()
        try:
            cctx.comparative.append({"type": "relation_mark", "source_ref": "a→b",
                                     "geometry": {"kind": "derived"},      # no cross_image
                                     "corpus": {"spans": [GROUND]}})
            res = cctx.loop.run_until_complete(ra._run_compose_comparative_percept(
                Step(actuator="compose_comparative_percept", id="s1",
                     params={"draft_text": "x"}),
                hydrated(), cctx, caps.ACTUATORS["compose_comparative_percept"]))
            assert res.status == EMPTY
        finally:
            cctx.close()


# ── 8. a whole corpus plan, executed ────────────────────────────────────────

class TestCorpusExecution:

    def test_a_step_runs_on_the_image_it_targets(self):
        """The router's whole job: the colonnade's step reaches the colonnade's producers."""
        cctx = build_corpus_context(corpus_fixture(), posts_fixture(), run_id="run_x")
        try:
            registries = {GROUND: stub_registry(), ROTUNDA: stub_registry()}
            plan = C.resolve_corpus(C.corpus_steps(
                ("rhythm", {"image": ROTUNDA})), hydrated(), intention="read the rotunda")
            chain = run_corpus_plan(plan, hydrated(), cctx,
                                    registry_for=lambda pid: registries[pid])
            assert chain.provenance.lineage[0].status == OK
            assert registries[ROTUNDA]["rhythm"].calls, "the rotunda's runner never fired"
            assert not registries[GROUND]["rhythm"].calls, "it fired on the wrong image"
        finally:
            cctx.close()

    def test_a_stub_two_image_corpus_produces_and_traces_a_comparative_percept(self):
        """END TO END on stubs: per-image finders leave real marks, the comparison relates across
        them, and the percept rests on that comparison — with both sources traceable."""
        cctx = build_corpus_context(corpus_fixture(), posts_fixture(), run_id="run_x")
        try:
            def registry_for(post_id):
                # A finder that leaves a REAL quarantined mark on its own image, so the
                # comparative step has something to actually cite rather than a projected count.
                reg = stub_registry()
                real = reg["find_parts"]

                def _finder(step, memory, _post_id=post_id, _stub=real):
                    result = _stub(step, memory)
                    cctx.contexts[_post_id].suggestions.append(
                        suggestion(_post_id, f"sug_{_post_id}", f"a part of {_post_id}"))
                    return result
                reg["find_parts"] = _finder
                return reg

            memory = C.hydrate_corpus(corpus_fixture(),
                                      {GROUND: {"photo_url": "http://x/lustgarten.jpg"},
                                       ROTUNDA: {"photo_url": "http://x/rotunda.jpg"}})
            plan = C.resolve_corpus(C.corpus_steps(
                ("find_parts", {"image": GROUND}),
                ("find_parts", {"image": ROTUNDA}),
                ("compare_views", {"relation_role": "contrast"}),
                ("compose_comparative_percept",
                 {"draft_text": "The ground disperses what the rotunda gathers."})),
                memory, intention="the walk from ground to rotunda")
            assert [s.actuator for s in plan.steps] == [
                "find_parts", "find_parts", "compare_views", "compose_comparative_percept"]
            assert not plan.refused

            chain = run_corpus_plan(plan, memory, cctx, registry_for=registry_for)
            statuses = [r.status for r in chain.provenance.lineage]
            assert statuses == [OK, OK, OK, OK], chain.provenance.gaps()
            assert chain.provenance.complete

            percept = cctx.comparative[-1]
            assert percept["type"] == "percept_draft"
            assert sorted(percept["corpus"]["spans"]) == sorted([GROUND, ROTUNDA])
            assert [s["post_id"] for s in percept["provenance"]["sources"]] == [GROUND, ROTUNDA]

            # every produced suggestion is attributable to a picture
            for sug in cctx.all_suggestions():
                assert sug.get("post_id") or sug.get("corpus", {}).get("spans")
        finally:
            cctx.close()

    def test_a_comparison_whose_upstream_finder_came_back_empty_is_reported_not_faked(self):
        cctx = build_corpus_context(corpus_fixture(), posts_fixture(), run_id="run_x")
        try:
            def registry_for(post_id):
                reg = stub_registry(empty=("find_parts",) if post_id == ROTUNDA else ())
                if post_id == GROUND:
                    real = reg["find_parts"]

                    def _finder(step, memory, _stub=real):
                        result = _stub(step, memory)
                        cctx.contexts[GROUND].suggestions.append(
                            suggestion(GROUND, "sug_ground", "a part of the ground"))
                        return result
                    reg["find_parts"] = _finder
                return reg

            memory = C.hydrate_corpus(corpus_fixture(),
                                      {GROUND: {"photo_url": "a"}, ROTUNDA: {"photo_url": "b"}})
            plan = C.resolve_corpus(C.corpus_steps(
                ("find_parts", {"image": GROUND}),
                ("find_parts", {"image": ROTUNDA}),
                ("compare_views", {"relation_role": "contrast"}),
                ("compose_comparative_percept", {"draft_text": "x"})), memory)
            chain = run_corpus_plan(plan, memory, cctx, registry_for=registry_for)

            by_actuator = {r.actuator: r for r in chain.provenance.lineage}
            assert by_actuator["compare_views"].status in (EMPTY, SKIPPED)
            assert cctx.comparative == []                       # nothing invented
            assert not chain.provenance.complete
            assert chain.provenance.gaps()
        finally:
            cctx.close()

    def test_an_image_whose_post_could_not_be_read_gets_no_context_and_says_so(self):
        cctx = build_corpus_context(corpus_fixture(), {GROUND: posts_fixture()[GROUND]},
                                    run_id="run_x")
        try:
            assert ROTUNDA not in cctx.contexts
            plan = C.resolve_corpus(C.corpus_steps(("rhythm", {"image": ROTUNDA})), hydrated())
            chain = run_corpus_plan(plan, hydrated(), cctx,
                                    registry_for=lambda pid: stub_registry())
            record = chain.provenance.lineage[0]
            assert record.status == UNAVAILABLE
            assert ROTUNDA in record.detail
        finally:
            cctx.close()


# ── 9. the single-image path is untouched ───────────────────────────────────

class TestSinglePostPathUnchanged:

    def test_build_memory_still_reports_one_image(self):
        memory = build_memory(image_ref="i", post_id=GROUND, mark_ids=("m1", "m2"))
        assert memory.available()[Resource.IMAGE] == 1
        assert type(memory).__name__ == "WorkingMemory"

    def test_connect_marks_still_resolves_on_a_single_post(self):
        plan = resolve([Step(actuator="connect_marks", id="s1",
                             params={"relation_role": "motif_echo"})],
                       build_memory(image_ref="i", post_id=GROUND, mark_ids=("m1", "m2")))
        assert [s.actuator for s in plan.steps] == ["connect_marks"]
        assert not plan.refused

    def test_a_corpus_packet_is_a_working_memory_everywhere_it_is_handed_around(self):
        """The reason `execute()`, the loop controller and every planner need no corpus branch."""
        from backend.services.director.memory import WorkingMemory
        memory = hydrated()
        assert isinstance(memory, WorkingMemory)
        evolved = memory.evolve((Resource.MARK,), step_id="s1")
        assert isinstance(evolved, C.CorpusWorkingMemory)       # survives `replace`
        assert evolved.available()[Resource.IMAGE] == 2         # and keeps its corpus
        assert evolved.available()[Resource.MARK] == 4

    def test_resolve_corpus_on_a_packet_with_no_corpus_defers_to_the_ordinary_gate(self):
        memory = C.CorpusWorkingMemory(image_ref="i", post_id=GROUND, mark_ids=("m1", "m2"))
        plan = C.resolve_corpus([Step(actuator="connect_marks", id="s1",
                                      params={"relation_role": "motif_echo"})], memory)
        assert [s.actuator for s in plan.steps] == ["connect_marks"]
