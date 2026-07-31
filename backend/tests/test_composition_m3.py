"""
CIRCUIT-003 M3 — argument composition: honesty tests.

Stub-driven: no GPU, no network, no database, no language model. The composer's Groq seam is an
injected `LLM` whose `complete()` returns canned JSON, so every guard is pinned offline.

The claims this gate exists to prove:

  1. Composition happens only from CONFIRMED/bound rows; a gaps() claim is never asserted
                                                        → TestConfirmFirst, TestQualifications
  2. A downgraded claim's prose is qualified with its caveat        → TestEpistemicInProse
  3. A sourced claim is attributed, never written as visible        → TestEpistemicInProse
  4. The counter-reading is grounded in a real challenge percept, or honestly absent
                                                                    → TestCounterReading
  5. No free-association beyond the bound percepts                  → TestCitesNothing
  6. The draft is quarantined, not committed                        → TestQuarantine
"""
from __future__ import annotations

import json

import pytest

from backend.services.director import argument as A
from backend.services.director import composition as M
from backend.services.director import corpus as C
from backend.services.director.execution import ChainProvenance, StepRecord

GROUND, FACADE, ROTUNDA = "post_lustgarten", "post_facade", "post_rotunda"

THESIS = ("The Altes Museum converts a dispersed civic ground into a centralized interior; "
          "the sequence performs the conversion.")


# ── fixtures ─────────────────────────────────────────────────────────────────

def posts_fixture() -> dict:
    return {
        GROUND: {"photo_url": "http://x/lustgarten.jpg",
                 "region_annotations": [{"id": "r_lawn",
                                         "box": {"x": .1, "y": .5, "w": .8, "h": .4}}]},
        FACADE: {"photo_url": "http://x/facade.jpg",
                 "region_annotations": [{"id": "r_col",
                                         "box": {"x": .2, "y": .2, "w": .6, "h": .6}}]},
        ROTUNDA: {"photo_url": "http://x/rotunda.jpg",
                  "region_annotations": [{"id": "r_dome",
                                          "box": {"x": .3, "y": .1, "w": .4, "h": .8}}]},
    }


def corpus_fixture() -> C.Corpus:
    return C.build_corpus(
        corpus_id="altes-museum", title="Lustgarten to rotunda",
        why="The walk from a dispersed civic ground to a centralized interior.",
        images=[{"post_id": GROUND, "title": "Lustgarten", "photo_url": "http://x/l.jpg"},
                {"post_id": FACADE, "title": "Colonnade", "photo_url": "http://x/f.jpg"},
                {"post_id": ROTUNDA, "title": "Rotunda", "photo_url": "http://x/r.jpg"}])


def memory_fixture() -> C.CorpusWorkingMemory:
    return C.hydrate_corpus(corpus_fixture(), posts_fixture())


def argument_fixture(**kw) -> A.ArgumentPlan:
    """Three claims: ground (support), colonnade (complicate), rotunda (support + challenge)."""
    claims = [
        A.make_claim("c0", "The ground disperses attention across the frame.",
                     [("pressure_zone", {"image": GROUND}, A.SUPPORT)],
                     target_status=A.MEASURED),
        A.make_claim("c1", "The colonnade begins to gather that dispersal.",
                     [("rhythm", {"image": FACADE}, A.COMPLICATE)],
                     target_status=A.MEASURED),
        A.make_claim("c2", "The rotunda completes the gathering.",
                     [("pressure_zone", {"image": ROTUNDA}, A.SUPPORT),
                      ("presence_check", {"image": ROTUNDA, "phrase": "a second focus"},
                       A.CHALLENGE)],
                     target_status=A.MEASURED),
    ]
    return A.plan_argument(THESIS, claims, memory_fixture(), **kw)


def provenance_for(argument: A.ArgumentPlan, *, statuses=None) -> ChainProvenance:
    """A chain in which every bound step ran OK, unless overridden."""
    overrides = statuses or {}
    records = []
    for i, (claim, percept) in enumerate(
            [(c, p) for c in argument.claims for p in c.bound]):
        status = overrides.get(percept.step.id, "ok")
        records.append(StepRecord(step_id=percept.step.id, actuator=percept.actuator,
                                  status=status, position=i,
                                  detail="found nothing" if status == "empty" else ""))
    return ChainProvenance(chain_id="run_m3", intention=THESIS, workflow=None,
                           planner="argument", lineage=tuple(records))


class FakeLLM(M.LLM):
    """A composer stand-in. `replies` maps a substring of the prompt → the JSON payload."""

    def __init__(self, default=None, replies=None, raises: bool = False):
        super().__init__(client=None, model="fake/composer")
        self._default = default if default is not None else {
            "prose": "The field concentrates toward one side of the frame.",
            "grounded_in": [], "relevance": [], "qualified": False}
        self._replies = replies or {}
        self._raises = raises
        self.prompts = []

    def complete(self, system, user):
        self.prompts.append((system, user))
        if self._raises:
            raise RuntimeError("composer is down")
        for needle, payload in self._replies.items():
            if needle in user:
                return json.dumps(payload) if not isinstance(payload, str) else payload
        payload = self._default
        # By default, ground the prose in whatever evidence ids the prompt actually offered.
        if isinstance(payload, dict) and not payload.get("grounded_in"):
            ids = [row["id"] for row in _ids_in(user)]
            payload = {**payload, "grounded_in": ids}
        return json.dumps(payload)


def _ids_in(prompt: str):
    """The evidence rows the prompt actually offered — how the fake grounds itself honestly."""
    out = []
    for line in prompt.splitlines():
        line = line.strip()
        if line.startswith('"id":'):
            out.append({"id": line.split('"')[3]})
    return out


# ── 1. confirm before composing ──────────────────────────────────────────────

class TestConfirmFirst:

    def test_nothing_is_composed_without_a_run(self):
        """Rule 1. An article written from a plan describes producers that may never have run,
        and would be indistinguishable from one written from a run."""
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM())
        assert draft.sections == ()
        assert not draft.grounded
        assert any("no run was supplied" in n for n in draft.notes)

    def test_composing_from_a_run_marks_the_claims_confirmed(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        assert draft.sections
        assert any("confirmed against a run" in n for n in draft.notes)

    def test_a_claim_whose_evidence_came_back_empty_is_not_composed(self):
        """THE CLAIM: composition happens from what a run PRODUCED, not what merely resolved."""
        argument = argument_fixture()
        c0 = argument.claims[0]
        prov = provenance_for(argument, statuses={c0.bound[0].step.id: "empty"})
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(), provenance=prov)

        assert "c0" not in [s.claim_id for s in draft.sections]
        # ...and it reaches the reader as a limit, not silently
        assert "c0" in [q.claim_id for q in draft.qualifications]

    def test_a_run_that_produced_nothing_composes_no_sections(self):
        argument = argument_fixture()
        prov = provenance_for(argument, statuses={
            p.step.id: "empty" for c in argument.claims for p in c.bound})
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(), provenance=prov)
        assert draft.sections == ()
        assert not draft.grounded
        assert draft.qualifications

    def test_confirmation_can_be_waived_only_deliberately(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  require_confirmation=False)
        assert draft.sections
        assert any("WITHOUT run confirmation" in n for n in draft.notes)


# ── 2. cites-nothing, at prose level ─────────────────────────────────────────

class TestCitesNothing:

    def test_a_section_citing_nothing_is_refused_not_published(self):
        """Rule 2. Prose resting on nothing is what this layer exists to prevent."""
        argument = argument_fixture()
        llm = FakeLLM(default={"prose": "The building is a civic temple.",
                               "grounded_in": ["not_a_real_step"], "relevance": []})
        draft = M.compose_article(argument, memory_fixture(), llm=llm,
                                  provenance=provenance_for(argument))
        assert draft.sections == ()
        assert {u.reason for u in draft.uncomposed} == {M.SECTION_CITES_NOTHING}
        assert not draft.grounded

    def test_citations_the_model_did_not_have_are_dropped_and_recorded(self):
        argument = argument_fixture()
        c0 = argument.claims[0]
        real = c0.bound[0].step.id
        llm = FakeLLM(replies={c0.claim.text: {
            "prose": "The field concentrates to one side.",
            "grounded_in": [real, "borrowed_from_another_claim"], "relevance": []}})
        section = M.compose_section(c0, memory_fixture(), llm)
        assert [c.step_id for c in section.citations] == [real]
        assert section.dropped_citations == ("borrowed_from_another_claim",)

    def test_a_section_that_names_an_uncited_image_is_flagged(self):
        """Rule 3. The failure that reads best and checks worst: fluent, plausible, resting on
        nothing — 'the colonnade prepares the rotunda' in a section evidenced only on the ground."""
        argument = argument_fixture()
        c0 = argument.claims[0]                     # evidenced on the Lustgarten only
        llm = FakeLLM(replies={c0.claim.text: {
            "prose": "The dispersal here already anticipates the Rotunda's concentration.",
            "grounded_in": [c0.bound[0].step.id], "relevance": []}})
        section = M.compose_section(c0, memory_fixture(), llm)
        assert section.uncited_mentions == (ROTUNDA,)

    def test_a_complicating_section_may_name_the_image_it_complicates(self):
        """Found by the guarded run, which flagged its own §2. A `complicate` section is handed
        the prior claim and told to make it harder to state simply — it will name that claim's
        image, correctly, every time. Flagging it would fire on every complication in every
        article, and a warning that fires on everything is one a reader learns to skip."""
        argument = argument_fixture()
        c1 = argument.claims[1]                      # the complicating claim, on the colonnade
        llm = FakeLLM(replies={c1.claim.text: {
            "prose": "This rhythm complicates the dispersal measured on the Lustgarten.",
            "grounded_in": [c1.bound[0].step.id], "relevance": []}})
        section = M.compose_section(c1, memory_fixture(), llm, function=A.COMPLICATE,
                                    prior_claim=argument.claims[0].claim.text,
                                    prior_images=(GROUND,))
        assert section.uncited_mentions == ()

    def test_a_complicating_section_naming_a_THIRD_image_is_still_flagged(self):
        """The exemption is the prior section's images only — it is not a general licence."""
        argument = argument_fixture()
        c1 = argument.claims[1]
        llm = FakeLLM(replies={c1.claim.text: {
            "prose": "This rhythm anticipates the Rotunda, complicating the Lustgarten's spread.",
            "grounded_in": [c1.bound[0].step.id], "relevance": []}})
        section = M.compose_section(c1, memory_fixture(), llm, function=A.COMPLICATE,
                                    prior_claim=argument.claims[0].claim.text,
                                    prior_images=(GROUND,))
        assert section.uncited_mentions == (ROTUNDA,)

    def test_the_exemption_reaches_only_one_section_back(self):
        """§3 may name what §2 cited; it may not silently reach back to §1's image."""
        argument = argument_fixture()
        llm = FakeLLM()
        M.compose_article(argument, memory_fixture(), llm=llm,
                          provenance=provenance_for(argument))
        # §3's permitted set is §2's images (the colonnade), not §1's (the ground)
        section3 = M.compose_section(
            argument.claims[2], memory_fixture(),
            FakeLLM(replies={argument.claims[2].claim.text: {
                "prose": "The centre gathers what the Lustgarten spread.",
                "grounded_in": [argument.claims[2].bound[0].step.id], "relevance": []}}),
            prior_images=(FACADE,))
        assert section3.uncited_mentions == (GROUND,)

    def test_a_section_citing_only_its_own_image_is_not_flagged(self):
        argument = argument_fixture()
        c0 = argument.claims[0]
        llm = FakeLLM(replies={c0.claim.text: {
            "prose": "Across the Lustgarten the measured field spreads evenly.",
            "grounded_in": [c0.bound[0].step.id], "relevance": []}})
        section = M.compose_section(c0, memory_fixture(), llm)
        assert section.uncited_mentions == ()

    def test_the_prompt_offers_only_this_claims_evidence(self):
        """No free-association, enforced at the input as well as the output: the composer is
        never shown the other claims' percepts."""
        argument = argument_fixture()
        llm = FakeLLM()
        M.compose_article(argument, memory_fixture(), llm=llm,
                          provenance=provenance_for(argument))
        c0_prompt = next(u for _s, u in llm.prompts if argument.claims[0].claim.text in u)
        assert argument.claims[0].bound[0].step.id in c0_prompt
        for other in argument.claims[1].bound + argument.claims[2].bound:
            assert other.step.id not in c0_prompt

    def test_every_citation_on_the_draft_is_a_real_bound_percept(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        real = {p.step.id for c in argument.claims for p in c.bound}
        assert {c.step_id for c in draft.citations} <= real


# ── 3. the epistemic status reaches the prose ────────────────────────────────

class TestEpistemicInProse:

    def test_a_downgraded_claim_is_qualified_with_its_caveat(self):
        """THE CLAIM: a claim that aimed higher than its evidence reads as qualified."""
        claim = A.make_claim("c0", "The ground is visibly dispersed.",
                             [("pressure_zone", {"image": GROUND}, A.SUPPORT)],
                             target_status=A.VISIBLE)      # aims visible, gets measured
        argument = A.plan_argument(THESIS, [claim], memory_fixture(),
                                   require_challenge=False)
        assert argument.claims[0].downgraded
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        section = draft.sections[0]
        assert section.qualified
        assert any("aimed to be 'visible'" in c for c in section.caveats)

    def test_the_caveat_is_carried_into_the_prompt_the_composer_sees(self):
        claim = A.make_claim("c0", "The ground is visibly dispersed.",
                             [("pressure_zone", {"image": GROUND}, A.SUPPORT)],
                             target_status=A.VISIBLE)
        argument = A.plan_argument(THESIS, [claim], memory_fixture(),
                                   require_challenge=False)
        llm = FakeLLM()
        M.compose_article(argument, memory_fixture(), llm=llm,
                          provenance=provenance_for(argument))
        assert "QUALIFICATIONS you must carry" in llm.prompts[0][1]
        assert "only 'measured'" in llm.prompts[0][1]

    def test_the_kind_of_knowing_travels_with_every_piece_of_evidence(self):
        argument = argument_fixture()
        llm = FakeLLM()
        M.compose_article(argument, memory_fixture(), llm=llm,
                          provenance=provenance_for(argument))
        assert '"kind_of_knowing"' in llm.prompts[0][1]
        assert "'sourced' came from outside the picture" in llm.prompts[0][0]

    def test_a_sourced_percept_is_attributed_never_written_as_visible(self):
        """THE CLAIM: a sourced claim carries its citation into the prose."""
        claim = A.make_claim(
            "c0", "Schinkel intended a civic temple.",
            [A.PerceptStep(
                step=type(argument_fixture().claims[0].bound[0].step)(
                    actuator="historical_source", params={"source": "Schinkel, 1823"},
                    id="c0:0:historical_source"),
                function=A.SUPPORT, target_status=A.SOURCED, image=GROUND)],
            target_status=A.SOURCED)
        citation = M._citation_for(claim.percepts[0], _fake_bound(claim), memory_fixture())
        assert citation.is_sourced
        assert citation.attribution == "Schinkel, 1823"
        rows = M._evidence_rows([citation])
        assert rows[0]["kind_of_knowing"] == A.SOURCED
        assert rows[0]["attributed_to"] == "Schinkel, 1823"

    def test_a_sourced_percept_with_no_source_is_qualified_as_unattributed(self):
        """A quotation with no quoter. It is not silently promoted to something the image shows."""
        claim = A.make_claim(
            "c0", "Schinkel intended a civic temple.",
            [A.PerceptStep(
                step=type(argument_fixture().claims[0].bound[0].step)(
                    actuator="historical_source", params={}, id="c0:0:historical_source"),
                function=A.SUPPORT, target_status=A.SOURCED, image=GROUND)],
            target_status=A.SOURCED)
        bound = _fake_bound(claim)
        llm = FakeLLM(default={"prose": "Schinkel described a civic temple.",
                               "grounded_in": ["c0:0:historical_source"], "relevance": []})
        section = M.compose_section(bound, memory_fixture(), llm)
        assert section.qualified
        assert any("names no source" in c for c in section.caveats)

    def test_a_sections_epistemic_tag_is_its_weakest_citation(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        assert draft.sections[0].epistemic == A.MEASURED
        assert draft.epistemic == A.MEASURED


def _fake_bound(claim: A.SubClaim) -> A.BoundClaim:
    """A BoundClaim carrying the claim's percepts as if they had all bound and been confirmed."""
    return A.BoundClaim(claim=claim, status=A.SUPPORTED, reason=A.REASON_ALL_BOUND,
                        bound=claim.percepts, achieved_status=A.SOURCED,
                        binding=A.BINDING_CONFIRMED)


# ── 4. the relevance guard ───────────────────────────────────────────────────

class TestRelevanceGuard:

    def test_a_percept_that_does_not_bear_on_the_claim_is_surfaced_not_narrated(self):
        """Rule 4, addressing M2's flagged limit. A mis-bound percept must READ as the mismatch it
        is instead of being narrated into a fluent non-sequitur."""
        argument = argument_fixture()
        c0 = argument.claims[0]
        llm = FakeLLM(replies={c0.claim.text: {
            "prose": "The measured field is present, though it speaks to texture, not dispersal.",
            "grounded_in": [c0.bound[0].step.id],
            "relevance": [{"id": c0.bound[0].step.id, "bears_on_claim": False,
                           "why": "it measures concentration, not spread"}]}})
        section = M.compose_section(c0, memory_fixture(), llm)
        assert section.relevance_flags
        assert section.relevance_flags[0]["actuator"] == "pressure_zone"
        assert section.qualified, "a flagged percept must not leave the section unqualified"
        assert any("does not bear on this claim" in c for c in section.caveats)

    def test_a_relevant_percept_leaves_the_section_unqualified(self):
        argument = argument_fixture()
        c0 = argument.claims[0]
        llm = FakeLLM(replies={c0.claim.text: {
            "prose": "The field spreads evenly across the frame.",
            "grounded_in": [c0.bound[0].step.id],
            "relevance": [{"id": c0.bound[0].step.id, "bears_on_claim": True,
                           "why": "it is the measurement of spread"}]}})
        section = M.compose_section(c0, memory_fixture(), llm)
        assert section.relevance_flags == ()
        assert not section.qualified

    def test_the_composer_is_asked_about_relevance_explicitly(self):
        argument = argument_fixture()
        llm = FakeLLM()
        M.compose_section(argument.claims[0], memory_fixture(), llm)
        system, user = llm.prompts[0]
        assert "does not actually bear on the claim" in system
        assert '"bears_on_claim"' in user

    def test_the_draft_notes_that_a_relevance_flag_was_raised(self):
        argument = argument_fixture()
        ids = {p.step.id for c in argument.claims for p in c.bound}
        llm = FakeLLM(default={
            "prose": "Something was measured.", "grounded_in": [],
            "relevance": [{"id": i, "bears_on_claim": False, "why": "unrelated"} for i in ids]})
        draft = M.compose_article(argument, memory_fixture(), llm=llm,
                                  provenance=provenance_for(argument))
        assert any("not bearing on its claim" in n for n in draft.notes)


# ── 5. the counter-reading ───────────────────────────────────────────────────

class TestCounterReading:

    def test_it_is_composed_from_a_real_challenge_percept(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        counter = draft.counter_reading
        assert counter.grounded
        assert counter.prose
        assert [c.function for c in counter.citations] == [A.CHALLENGE]
        assert counter.citations[0].actuator == "presence_check"

    def test_a_challenge_percept_is_not_also_a_body_section(self):
        """It reads AGAINST the argument; narrating it as support would invert its function."""
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        for section in draft.sections:
            assert A.CHALLENGE not in [c.function for c in section.citations]

    def test_no_challenge_proposed_is_stated_honestly_and_never_invented(self):
        claim = A.make_claim("c0", "The ground disperses attention.",
                             [("pressure_zone", {"image": GROUND}, A.SUPPORT)])
        argument = A.plan_argument(THESIS, [claim], memory_fixture(),
                                   require_challenge=False)
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        counter = draft.counter_reading
        assert not counter.grounded
        assert counter.prose == ""                       # nothing fabricated
        assert counter.absence_reason == M.COUNTER_NONE_PROPOSED
        assert "untested, not confirmed" in counter.absence_detail

    def test_a_challenge_that_could_not_be_produced_is_worded_differently(self):
        """M2's distinction, carried into the prose layer: a curator needs to know whether nobody
        proposed a counter-reading or whether one was proposed and its evidence never arrived."""
        claims = [A.make_claim("c0", "The ground disperses attention.",
                               [("pressure_zone", {"image": GROUND}, A.SUPPORT)]),
                  A.make_claim("c1", "Unless a second focus exists.",
                               [("material_field", {"image": GROUND}, A.CHALLENGE)])]
        bare = C.hydrate_corpus(corpus_fixture(),
                                {p: {"photo_url": "x"} for p in (GROUND, FACADE, ROTUNDA)})
        argument = A.plan_argument(THESIS, claims, bare)
        draft = M.compose_article(argument, bare, llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        counter = draft.counter_reading
        assert not counter.grounded
        assert counter.absence_reason == M.COUNTER_NOT_PRODUCED
        assert "none is offered here rather than one being supplied" in counter.absence_detail

    def test_a_challenge_lost_at_run_time_loses_the_counter_reading(self):
        argument = argument_fixture()
        challenge = next(p for c in argument.claims for p in c.bound
                         if p.function == A.CHALLENGE)
        prov = provenance_for(argument, statuses={challenge.step.id: "unavailable"})
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(), provenance=prov)
        assert not draft.counter_reading.grounded
        assert draft.counter_reading.prose == ""

    def test_the_counter_reading_is_told_not_to_defend_the_argument(self):
        argument = argument_fixture()
        llm = FakeLLM()
        M.compose_counter_reading(argument, memory_fixture(), llm, thesis=THESIS)
        system = llm.prompts[-1][0]
        assert "Do not defend the argument" in system
        assert "do not conclude that the argument survives" in system


# ── 6. qualifications — gaps() is never asserted ─────────────────────────────

class TestQualifications:

    def test_a_refused_claim_becomes_a_limit_never_a_section(self):
        """THE CLAIM: what the corpus could not carry is stated as a limit, never as a finding."""
        claims = [A.make_claim("c0", "The ground disperses attention.",
                               [("pressure_zone", {"image": GROUND}, A.CHALLENGE)]),
                  A.make_claim("c1", "The rotunda's stone recurs from the colonnade.",
                               [("material_field", {"image": ROTUNDA}, A.SUPPORT)])]
        bare = C.hydrate_corpus(corpus_fixture(),
                                {p: {"photo_url": "x"} for p in (GROUND, FACADE, ROTUNDA)})
        argument = A.plan_argument(THESIS, claims, bare)
        assert argument.claims[1].status == A.REFUSED

        draft = M.compose_article(argument, bare, llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        assert "c1" not in [s.claim_id for s in draft.sections]
        qual = next(q for q in draft.qualifications if q.claim_id == "c1")
        assert "could not establish" in qual.prose
        assert "left open rather than argued" in qual.prose

    def test_a_qualification_never_says_what_the_claim_would_have_shown(self):
        """Qualification prose is templated, not model-written, on purpose: asked to write 'we
        could not establish X', a language model will explain what X would have shown — and the
        explanation asserts the very claim the qualification exists to withhold."""
        claims = [A.make_claim("c0", "The rotunda's stone recurs.",
                               [("material_field", {"image": ROTUNDA}, A.SUPPORT)])]
        bare = C.hydrate_corpus(corpus_fixture(),
                                {p: {"photo_url": "x"} for p in (GROUND, FACADE, ROTUNDA)})
        argument = A.plan_argument(THESIS, claims, bare, require_challenge=False)
        llm = FakeLLM()
        draft = M.compose_article(argument, bare, llm=llm, provenance=provenance_for(argument))
        assert draft.qualifications
        # the composer was never asked to write the refused claim
        assert not any("The rotunda's stone recurs" in u for _s, u in llm.prompts)

    def test_a_partly_carried_claim_says_what_it_lost(self):
        claims = [A.make_claim("c0", "The rotunda gathers attention.",
                               [("pressure_zone", {"image": ROTUNDA}, A.SUPPORT),
                                ("material_field", {"image": ROTUNDA}, A.SUPPORT)])]
        bare = C.hydrate_corpus(corpus_fixture(),
                                {p: {"photo_url": "x"} for p in (GROUND, FACADE, ROTUNDA)})
        argument = A.plan_argument(THESIS, claims, bare, require_challenge=False)
        draft = M.compose_article(argument, bare, llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        qual = next(q for q in draft.qualifications if q.claim_id == "c0")
        assert "material_field could not be produced" in qual.prose
        assert "stands only on what did" in qual.prose

    def test_an_argument_level_refusal_reaches_the_reader(self):
        claims = [A.make_claim("c0", "The ground disperses attention.",
                               [("pressure_zone", {"image": GROUND}, A.SUPPORT)])]
        argument = A.plan_argument(THESIS, claims, memory_fixture())   # no challenge
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        assert any(q.why == A.ARGUMENT_NO_CHALLENGE for q in draft.qualifications)
        assert any("This argument is incomplete" in q.prose for q in draft.qualifications)


# ── 7. the model is absent ───────────────────────────────────────────────────

class TestNoModel:

    def test_no_language_model_composes_no_prose(self):
        """Rule 5. A template sentence would be a claim nobody made, wearing the shape of one
        somebody did."""
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=None,
                                  provenance=provenance_for(argument))
        assert draft.sections == ()
        assert {u.reason for u in draft.uncomposed} == {M.SECTION_NO_MODEL}
        assert all("no prose was invented" in u.detail for u in draft.uncomposed)

    def test_a_composer_that_raises_is_an_uncomposed_section_not_a_crash(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(raises=True),
                                  provenance=provenance_for(argument))
        assert draft.sections == ()
        assert {u.reason for u in draft.uncomposed} == {M.SECTION_NO_PROSE}

    def test_the_qualifications_still_reach_the_reader_with_no_model(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=None,
                                  provenance=provenance_for(argument))
        assert draft.uncomposed                      # nothing was silently dropped


# ── 8. structure and quarantine ──────────────────────────────────────────────

class TestStructure:

    def test_sections_realize_their_argumentative_function(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        by_claim = {s.claim_id: s for s in draft.sections}
        assert by_claim["c0"].function == A.SUPPORT
        assert by_claim["c1"].function == A.COMPLICATE
        assert by_claim["c2"].function == A.SUPPORT

    def test_a_complicating_section_is_shown_the_claim_it_complicates(self):
        """The §4-complicates-§3 move: without the prior claim, 'complicate' has nothing to act
        on and degenerates into another support paragraph."""
        argument = argument_fixture()
        llm = FakeLLM()
        M.compose_article(argument, memory_fixture(), llm=llm,
                          provenance=provenance_for(argument))
        c1_prompt = next(u for _s, u in llm.prompts if argument.claims[1].claim.text in u)
        assert "THE PRIOR CLAIM YOU ARE COMPLICATING" in c1_prompt
        assert argument.claims[0].claim.text in c1_prompt

    def test_the_opening_rests_on_what_the_body_establishes(self):
        argument = argument_fixture()
        llm = FakeLLM()
        draft = M.compose_article(argument, memory_fixture(), llm=llm,
                                  provenance=provenance_for(argument))
        assert draft.thesis_prose
        opening = llm.prompts[-1][1]
        assert "WHAT THE BODY ACTUALLY ESTABLISHES" in opening
        for section in draft.sections:
            assert section.claim in opening

    def test_the_draft_serialises(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        d = draft.to_dict()
        assert d["thesis"] == THESIS
        assert d["sections"] and d["counter_reading"]["grounded"]
        assert json.dumps(d)


class TestQuarantine:

    def test_the_draft_is_a_quarantined_suggestion_never_committed(self):
        """THE CLAIM: propose-never-commit. Mirrors the visual circuit's `model_suggested`."""
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument), run_id="run_m3")
        assert draft.committed is False
        sug = draft.to_suggestion()
        assert sug["status"] == M.STATUS_MODEL_SUGGESTED
        assert sug["producer"] == M.PRODUCER_COMPOSE_ARTICLE
        assert sug["type"] == M.ARTICLE_DRAFT_TYPE
        assert sug["geometry"] is None            # an article has no extent
        assert sug["provenance"]["run_id"] == "run_m3"
        assert sug["provenance"]["model"] == "fake/composer"

    def test_the_suggestion_cites_only_real_bound_percepts(self):
        argument = argument_fixture()
        draft = M.compose_article(argument, memory_fixture(), llm=FakeLLM(),
                                  provenance=provenance_for(argument))
        real = {p.step.id for c in argument.claims for p in c.bound}
        assert set(draft.to_suggestion()["cites"]) <= real

    def test_composition_writes_nothing(self):
        """Data safety, asserted rather than assumed: the module exposes no commit path."""
        assert not [n for n in dir(M) if "commit" in n.lower() and n != "committed"]
        argument = argument_fixture()
        memory = memory_fixture()
        before = memory.summary()
        M.compose_article(argument, memory, llm=FakeLLM(), provenance=provenance_for(argument))
        assert memory.summary() == before          # the packet is untouched
