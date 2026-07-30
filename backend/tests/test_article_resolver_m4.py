"""
CIRCUIT-003 M4 — the article resolver: tests.

Stub-driven: no GPU, no network, no database, no language model. The composer is a fake LLM (as in
M3's suite), so a real draft is composed and then resolved against a real quarantine.

  1. A citation resolves to a LIVE percept (geometry + source image)   → TestResolution
  2. An ambiguous citation is refused, never guessed                   → TestAmbiguity
  3. The honest-defect channel survives the join                       → TestDefectChannel
  4. The resolver is read-only                                         → TestReadOnly
"""
from __future__ import annotations

import copy
import json

import pytest

from backend.services.director import argument as A
from backend.services.director import article_resolver as R
from backend.services.director import composition as M
from backend.services.director import corpus as C
from backend.services.director.execution import ChainProvenance, StepRecord

GROUND, FACADE, ROTUNDA = "post_lustgarten", "post_facade", "post_rotunda"
THESIS = "The Altes Museum converts a dispersed civic ground into a centralized interior."


# ── fixtures ─────────────────────────────────────────────────────────────────

def corpus_fixture() -> C.Corpus:
    return C.build_corpus(
        corpus_id="altes-museum", title="Lustgarten to rotunda",
        why="The walk from a dispersed civic ground to a centralized interior.",
        images=[{"post_id": GROUND, "title": "Lustgarten", "photo_url": "http://x/l.jpg"},
                {"post_id": FACADE, "title": "Colonnade", "photo_url": "http://x/f.jpg"},
                {"post_id": ROTUNDA, "title": "Rotunda", "photo_url": "http://x/r.jpg"}])


def posts_fixture() -> dict:
    return {p: {"photo_url": f"http://x/{p}.jpg",
                "region_annotations": [{"id": f"r_{p}",
                                        "box": {"x": .1, "y": .1, "w": .5, "h": .5}}]}
            for p in (GROUND, FACADE, ROTUNDA)}


def memory_fixture() -> C.CorpusWorkingMemory:
    return C.hydrate_corpus(corpus_fixture(), posts_fixture())


def produced(post_id: str, producer: str, *, kind: str = "brush_field",
             ref: str = "", label: str = "") -> dict:
    """A quarantined suggestion as a real producer leaves it — note it carries NO step_id."""
    return {
        "producer": producer, "type": kind, "role": producer,
        "label": label or f"{producer} on {post_id}",
        "source_ref": ref or f"{post_id}:{producer}",
        "geometry": {"kind": "raster", "strokes": [[0.1, 0.2], [0.4, 0.6]]},
        "linked_ground_ids": [], "post_id": post_id,
        "provenance": {"run_id": "run_m4", "producer": producer, "adapter": producer},
    }


def argument_fixture() -> A.ArgumentPlan:
    claims = [
        A.make_claim("c0", "The ground disperses attention.",
                     [("pressure_zone", {"image": GROUND}, A.SUPPORT)],
                     target_status=A.MEASURED),
        A.make_claim("c1", "The colonnade gathers it.",
                     [("rhythm", {"image": FACADE}, A.COMPLICATE)], target_status=A.MEASURED),
        A.make_claim("c2", "The rotunda completes the gathering.",
                     [("pressure_zone", {"image": ROTUNDA}, A.SUPPORT),
                      ("presence_check", {"image": ROTUNDA, "phrase": "a second focus"},
                       A.CHALLENGE)], target_status=A.MEASURED),
    ]
    return A.plan_argument(THESIS, claims, memory_fixture())


def provenance_for(argument) -> ChainProvenance:
    records = [StepRecord(step_id=p.step.id, actuator=p.actuator, status="ok", position=i)
               for i, (c, p) in enumerate([(c, p) for c in argument.claims for p in c.bound])]
    return ChainProvenance(chain_id="run_m4", intention=THESIS, workflow=None,
                           planner="argument", lineage=tuple(records))


class FakeLLM(M.LLM):
    def __init__(self):
        super().__init__(client=None, model="fake/composer")

    def complete(self, system, user):
        ids = [line.strip().split('"')[3] for line in user.splitlines()
               if line.strip().startswith('"id":')]
        return json.dumps({"prose": "The measured field concentrates to one side.",
                           "grounded_in": ids, "relevance": []})


def draft_fixture() -> dict:
    argument = argument_fixture()
    draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                              provenance=provenance_for(argument), run_id="run_m4")
    return draft.to_dict()


def quarantine_fixture() -> list:
    return [produced(GROUND, "pressure_zone"),
            produced(FACADE, "rhythm"),
            produced(ROTUNDA, "pressure_zone"),
            produced(ROTUNDA, "presence_check", kind="trace_mark")]


# ── 1. resolution ────────────────────────────────────────────────────────────

class TestResolution:

    def test_a_citation_resolves_to_a_live_percept(self):
        """THE CLAIM: step_id → the geometry actually produced, on its source image."""
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        assert article.citations
        assert article.drawable

        first = article.drawable[0]
        assert first.status == R.RESOLVED
        assert first.geometry is not None                 # real geometry, not a screenshot
        assert first.geometry["strokes"]
        assert first.image in (GROUND, FACADE, ROTUNDA)
        assert first.image_ref.startswith("http")         # the image it is drawn ON
        assert first.image_title                          # the corpus's own name for it

    def test_every_citation_in_the_draft_is_accounted_for(self):
        draft = draft_fixture()
        article = R.resolve_article(draft, quarantine_fixture(), memory_fixture())
        cited = {c["step_id"] for s in draft["sections"] for c in s["citations"]}
        cited |= {c["step_id"] for c in draft["counter_reading"]["citations"]}
        assert set(article.by_step_id) == cited

    def test_the_counter_readings_citation_resolves_too(self):
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        challenge = [c for c in article.citations if c.function == A.CHALLENGE]
        assert challenge and challenge[0].status == R.RESOLVED

    def test_the_epistemic_tag_and_function_survive_the_join(self):
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        for citation in article.citations:
            assert citation.epistemic in A.EPISTEMIC_STATUSES
            assert citation.function in A.FUNCTIONS

    def test_a_citation_with_no_produced_percept_says_unproduced(self):
        article = R.resolve_article(draft_fixture(), [produced(GROUND, "pressure_zone")],
                                    memory_fixture())
        missing = [c for c in article.citations if c.status == R.UNPRODUCED]
        assert missing
        assert "no produced percept matches" in missing[0].detail
        assert not missing[0].drawable

    def test_a_percept_draft_is_not_drawable_evidence(self):
        """A percept rests on things with extent; it has none. Drawing a box for it would invent
        an extent nobody produced."""
        quarantine = quarantine_fixture() + [
            {"producer": "planner", "type": "percept_draft", "post_id": GROUND,
             "source_ref": "x", "geometry": None,
             "provenance": {"adapter": "compose_percept", "producer": "compose_percept"}}]
        article = R.resolve_article(draft_fixture(), quarantine, memory_fixture())
        assert all(c.geometry_kind != "percept_draft" for c in article.citations)

    def test_the_reopen_payload_names_the_source_image(self):
        """What a click needs: the post to open and the percept to find in it."""
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        reopen = article.drawable[0].to_dict()["reopen"]
        assert reopen["post_id"] in (GROUND, FACADE, ROTUNDA)
        assert reopen["source_ref"]
        assert reopen["step_id"]

    def test_the_article_lists_the_images_it_draws_on(self):
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        assert set(article.images()) <= {GROUND, FACADE, ROTUNDA}

    def test_a_cross_image_relation_resolves_on_either_side(self):
        relation = {"producer": "semantic_read", "type": "relation_mark", "role": "contrast",
                    "label": "dispersed against centred", "source_ref": "g→r",
                    "geometry": {"kind": "derived", "endpoints": ["a", "b"],
                                 "cross_image": True},
                    "corpus": {"corpus_id": "altes-museum", "spans": [GROUND, ROTUNDA]},
                    "provenance": {"adapter": "compare_views", "producer": "compare_views"}}
        citation = {"step_id": "s", "actuator": "compare_views", "image": ROTUNDA,
                    "function": A.SUPPORT, "epistemic": A.INTERPRETIVE}
        resolved = R.resolve_citation(citation, [relation], memory_fixture())
        assert resolved.status == R.RESOLVED
        assert resolved.geometry["cross_image"] is True

    def test_the_resolved_article_serialises_keyed_by_step_id(self):
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        d = article.to_dict()
        assert d["draft"]["sections"]
        assert set(d["resolved"]) == set(article.by_step_id)
        assert d["counts"]["citations"] == len(article.citations)
        assert json.dumps(d)


# ── 2. ambiguity — the failure nothing in the document would catch ──────────

class TestAmbiguity:

    def test_two_matching_percepts_resolve_to_neither(self):
        """THE CLAIM: the resolver refuses to pick. An article that drew the wrong field beside a
        true sentence would be believed by every reader and contradicted by nothing."""
        quarantine = quarantine_fixture() + [
            produced(GROUND, "pressure_zone", ref="a_second_one")]
        article = R.resolve_article(draft_fixture(), quarantine, memory_fixture())
        ambiguous = [c for c in article.citations if c.status == R.AMBIGUOUS]
        assert ambiguous
        assert ambiguous[0].geometry is None              # nothing was chosen
        assert not ambiguous[0].drawable
        assert len(ambiguous[0].candidates) == 2          # both are named

    def test_the_ambiguity_explains_why_it_cannot_be_settled(self):
        quarantine = quarantine_fixture() + [
            produced(GROUND, "pressure_zone", ref="a_second_one")]
        article = R.resolve_article(draft_fixture(), quarantine, memory_fixture())
        ambiguous = next(c for c in article.citations if c.status == R.AMBIGUOUS)
        assert "does not record its step" in ambiguous.detail

    def test_the_same_actuator_on_DIFFERENT_images_is_not_ambiguous(self):
        """pressure_zone runs on the ground and on the rotunda in this argument; the image is what
        keeps them apart, and it is enough."""
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        pressure = [c for c in article.citations if c.actuator == "pressure_zone"]
        assert len(pressure) == 2
        assert all(c.status == R.RESOLVED for c in pressure)
        assert {c.image for c in pressure} == {GROUND, ROTUNDA}


# ── 3. the honest-defect channel survives ───────────────────────────────────

class TestDefectChannel:

    def test_relevance_flags_and_uncited_mentions_reach_the_renderer(self):
        """M3 built these and warned they would die unrendered. The resolver must not be where
        they are lost."""
        argument = argument_fixture()
        c0 = argument.claims[0]

        class FlaggingLLM(M.LLM):
            def __init__(self):
                super().__init__(client=None, model="fake/composer")

            def complete(self, system, user):
                ids = [ln.strip().split('"')[3] for ln in user.splitlines()
                       if ln.strip().startswith('"id":')]
                if c0.claim.text in user:
                    return json.dumps({
                        "prose": "The field concentrates, though it speaks to the Rotunda.",
                        "grounded_in": ids,
                        "relevance": [{"id": ids[0], "bears_on_claim": False,
                                       "why": "it measures concentration, not spread"}]})
                return json.dumps({"prose": "A measured field.", "grounded_in": ids,
                                   "relevance": []})

        draft = M.compose_article(argument, memory_fixture(), llm=FlaggingLLM(),
                                  provenance=provenance_for(argument), run_id="run_m4").to_dict()
        article = R.resolve_article(draft, quarantine_fixture(), memory_fixture())
        section = article.to_dict()["draft"]["sections"][0]
        assert section["relevance_flags"]
        assert section["uncited_mentions"] == [ROTUNDA]
        assert section["qualified"] is True

    def test_qualifications_and_the_counter_reading_survive_verbatim(self):
        draft = draft_fixture()
        article = R.resolve_article(draft, quarantine_fixture(), memory_fixture())
        out = article.to_dict()["draft"]
        assert out["qualifications"] == draft["qualifications"]
        assert out["counter_reading"] == draft["counter_reading"]

    def test_the_draft_is_carried_verbatim_not_rewritten(self):
        draft = draft_fixture()
        article = R.resolve_article(draft, quarantine_fixture(), memory_fixture())
        assert article.to_dict()["draft"] == draft


# ── 4. read-only ─────────────────────────────────────────────────────────────

class TestReadOnly:

    def test_the_resolver_mutates_nothing_it_is_handed(self):
        draft = draft_fixture()
        quarantine = quarantine_fixture()
        memory = memory_fixture()
        draft_before = copy.deepcopy(draft)
        quarantine_before = copy.deepcopy(quarantine)
        memory_before = memory.summary()

        R.resolve_article(draft, quarantine, memory)

        assert draft == draft_before
        assert quarantine == quarantine_before
        assert memory.summary() == memory_before

    def test_the_draft_stays_uncommitted(self):
        article = R.resolve_article(draft_fixture(), quarantine_fixture(), memory_fixture())
        assert article.to_dict()["draft"]["committed"] is False

    def test_the_module_exposes_no_write_path(self):
        assert not [n for n in dir(R)
                    if any(w in n.lower() for w in ("commit", "save", "write", "accept"))]
