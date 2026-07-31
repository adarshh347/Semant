"""
CIRCUIT-003 M2 — the rhetorical planner: honesty tests.

Stub-driven: no GPU, no network, no database, no language model. The Groq-backed decomposition is
exercised with an injected fake client, exactly as `test_groq_planner.py` does — so the guards are
pinned without an API key and this runs unattended in CI.

The five claims this gate exists to prove:

  1. A thesis decomposes into sub-claims, each with bound percept-steps and functions
                                                              → TestDecomposition
  2. A claim whose percepts resolve is SUPPORTED               → TestBinding
  3. A claim whose percepts refuse is QUALIFIED/REFUSED, never fabricated
                                                              → TestNoFabrication
  4. The plan contains at least one `challenge`                → TestCounterSeed
  5. claim → percept lineage is traced                         → TestLineage
"""
from __future__ import annotations

import json

import pytest

from backend.services.director import argument as A
from backend.services.director import argument_planner as AP
from backend.services.director import corpus as C
from backend.services.director.capabilities import Resource
from backend.services.director.memory import build_memory
from backend.services.director.plan import Step

GROUND = "post_ground"          # the Lustgarten: a dispersed civic ground
ROTUNDA = "post_rotunda"        # the rotunda: centralized

THESIS = ("The Altes Museum turns a dispersed civic ground into a centralized interior; "
          "the sequence performs the conversion.")


# ── fixtures ─────────────────────────────────────────────────────────────────

def _region(rid: str) -> dict:
    return {"id": rid, "box": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4}}


def _mark(mid: str, label: str) -> dict:
    return {"id": mid, "label": label, "type": "brush_field", "status": "committed"}


def posts_fixture() -> dict:
    return {
        GROUND: {"photo_url": "http://x/lustgarten.jpg",
                 "region_annotations": [_region("r_lawn")],
                 "visual_marks": [_mark("m_dispersal", "the ground spreads")]},
        ROTUNDA: {"photo_url": "http://x/rotunda.jpg",
                  "region_annotations": [_region("r_dome")],
                  "visual_marks": [_mark("m_centre", "everything turns to the centre")]},
    }


def corpus_fixture() -> C.Corpus:
    return C.build_corpus(
        corpus_id="altes-museum", title="Lustgarten to rotunda",
        why="The walk from a dispersed civic ground to a centralized interior.",
        images=[{"post_id": GROUND, "photo_url": "http://x/lustgarten.jpg",
                 "title": "Lustgarten", "note": "the ground the building addresses"},
                {"post_id": ROTUNDA, "photo_url": "http://x/rotunda.jpg",
                 "title": "Rotunda", "note": "where the walk ends"}])


def hydrated(posts=None) -> C.CorpusWorkingMemory:
    return C.hydrate_corpus(corpus_fixture(), posts if posts is not None else posts_fixture())


def bare_corpus() -> C.CorpusWorkingMemory:
    """A corpus whose images carry NOTHING committed — where claims needing a region refuse."""
    return C.hydrate_corpus(corpus_fixture(),
                            {GROUND: {"photo_url": "a"}, ROTUNDA: {"photo_url": "b"}})


def a_workable_argument():
    """Three claims: two carried, one aimed at evidence the corpus cannot give."""
    return [
        A.make_claim("c0", "The ground disperses attention across the frame.",
                     [("pressure_zone", {"image": GROUND}, A.SUPPORT),
                      ("rhythm", {"image": GROUND}, A.SUPPORT)],
                     target_status=A.MEASURED),
        A.make_claim("c1", "The rotunda gathers it to a centre.",
                     [("pressure_zone", {"image": ROTUNDA}, A.SUPPORT),
                      ("rhythm", {"image": ROTUNDA}, A.CHALLENGE)],
                     target_status=A.MEASURED),
        A.make_claim("c2", "The sequence performs the conversion between them.",
                     [("compare_views", {"relation_role": "contrast"}, A.SUPPORT)],
                     target_status=A.INTERPRETIVE),
    ]


class FakeCompletion:
    def __init__(self, content: str):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class FakeClient:
    """A Groq stand-in. Records every call, so the no-loop guard is observable."""

    def __init__(self, payload, *, raises: bool = False):
        self._payload = payload
        self._raises = raises
        self.calls = []
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise RuntimeError("groq is down")
        content = (self._payload if isinstance(self._payload, str)
                   else json.dumps(self._payload))
        return FakeCompletion(content)


def model_argument(**overrides) -> dict:
    """A well-formed decomposition as the model would return it."""
    payload = {"claims": [
        {"claim": "The ground disperses attention across the frame.",
         "target_status": "measured", "note": "the civic ground",
         "percepts": [
             {"actuator": "pressure_zone", "image": GROUND, "function": "support",
              "params": {}, "note": "where the composition concentrates"},
             {"actuator": "rhythm", "image": GROUND, "function": "complicate", "params": {}}]},
        {"claim": "The rotunda gathers it to a centre.",
         "target_status": "measured",
         "percepts": [
             {"actuator": "pressure_zone", "image": ROTUNDA, "function": "support",
              "params": {}},
             {"actuator": "rhythm", "image": ROTUNDA, "function": "challenge",
              "params": {}, "note": "if the rotunda also reads as rhythmic, the claim weakens"}]},
    ]}
    payload.update(overrides)
    return payload


# ── 1. the vocabulary ────────────────────────────────────────────────────────

class TestVocabulary:

    def test_the_three_argumentative_functions_are_closed(self):
        assert A.FUNCTIONS == (A.SUPPORT, A.COMPLICATE, A.CHALLENGE)
        assert A.known_function("challenge")
        assert not A.known_function("vibes")
        assert not A.known_function(None)

    def test_the_epistemic_statuses_are_the_five(self):
        assert A.EPISTEMIC_STATUSES == (A.VISIBLE, A.MEASURED, A.SOURCED,
                                        A.INTERPRETIVE, A.UNCERTAIN)

    def test_every_actuator_declares_an_epistemic_ceiling(self):
        from backend.services.director.capabilities import known
        for name in known():
            assert A.epistemic_ceiling(name) in A.EPISTEMIC_STATUSES, name

    def test_an_invented_actuator_reaches_nothing(self):
        """Crediting a hallucinated actuator with a status would put a model-authored epistemic
        claim into a record a reader might trust."""
        assert A.epistemic_ceiling("brush_the_vibes") == A.UNCERTAIN

    def test_only_an_actuator_that_leaves_the_image_reaches_sourced(self):
        """The invariant that survives M6's merge. On this branch nothing in the catalogue
        consults an external source, so a claim aiming at `sourced` always downgrades; once M6's
        `historical_source` lands it is the one actuator that may reach it, and no image producer
        ever joins it."""
        from backend.services.director.capabilities import known
        reaching = {n for n in known() if A.epistemic_ceiling(n) == A.SOURCED}
        assert reaching <= {"historical_source"}
        assert A.ACTUATOR_EPISTEMIC_CEILING["historical_source"] == A.SOURCED

    def test_the_epistemic_vocabulary_does_not_fork_from_M6s(self):
        """M2 and M6 were built in parallel branches off the same main and share this vocabulary.
        M6 (`backend/services/epistemics.py`) owns it and walls `sourced`; M2 reads the same five
        values one level up, on claims. This fails loudly if the two ever diverge."""
        assert set(A.EPISTEMIC_STATUSES) == {"visible", "measured", "sourced",
                                             "interpretive", "uncertain"}
        epistemics = pytest.importorskip(
            "backend.services.epistemics",
            reason="M6 is not on this branch yet; the literals above are the pin until it merges")
        assert {s.value for s in epistemics.EpistemicStatus} == set(A.EPISTEMIC_STATUSES)
        # M6 walls `sourced`; M2 independently refuses to let anything else reach it.
        assert {s.value for s in epistemics.WALLED_STATUSES} == set(
            A._KINDS_ONLY_REACHED_BY_THEMSELVES)

    def test_a_claim_reaches_only_as_far_as_its_weakest_evidence(self):
        assert A.weakest_status([A.VISIBLE, A.MEASURED, A.INTERPRETIVE]) == A.INTERPRETIVE
        assert A.weakest_status([]) == A.UNCERTAIN
        assert A.reaches(A.MEASURED, A.INTERPRETIVE)
        assert not A.reaches(A.INTERPRETIVE, A.MEASURED)

    def test_nothing_measured_in_the_frame_can_stand_in_for_a_source(self):
        """`sourced` is a KIND of knowing, not a rung on the strength ladder. Ranking it
        numerically let a CPU field over a photograph satisfy a claim about what someone
        intended — strength 3 'reaching' strength 2."""
        assert not A.reaches(A.MEASURED, A.SOURCED)
        assert not A.reaches(A.VISIBLE, A.SOURCED)
        assert A.reaches(A.SOURCED, A.SOURCED)
        assert A.reaches(A.SOURCED, A.INTERPRETIVE)     # it is still strong for ordinary targets


# ── 2. decomposition ─────────────────────────────────────────────────────────

class TestDecomposition:

    def test_a_thesis_decomposes_into_subclaims_with_percepts_and_functions(self):
        """THE CLAIM: each sub-claim carries percept-steps, each tagged with a sensory mode, an
        image, and an argumentative function."""
        planner = AP.GroqArgumentPlanner(client=FakeClient(model_argument()))
        claims = planner.propose(THESIS, hydrated())

        assert len(claims) == 2
        assert all(c.text and c.percepts for c in claims)
        for claim in claims:
            for percept in claim.percepts:
                assert percept.actuator in AP.known()          # a real sensory mode
                assert percept.image in (GROUND, ROTUNDA)      # on a real corpus image
                assert percept.function in A.FUNCTIONS
                assert percept.target_status in A.EPISTEMIC_STATUSES

    def test_the_prompt_is_constrained_to_the_corpus_and_the_actuator_vocabulary(self):
        client = FakeClient(model_argument())
        AP.GroqArgumentPlanner(client=client).propose(THESIS, hydrated())
        prompt = client.calls[0]["messages"][1]["content"]
        assert GROUND in prompt and ROTUNDA in prompt
        assert "Lustgarten" in prompt                       # the sequence's own titles
        assert "pressure_zone" in prompt and "compare_views" in prompt
        assert "challenge" in prompt                        # the counter-reading is ASKED for
        assert "epistemic_ceiling" in prompt                # so a `measured` claim gets an instrument
        assert "spans_images" in prompt                     # comparative actuators take NO image

    def test_a_comparative_percept_pinned_to_one_image_is_refused_not_unpinned(self):
        """Found by the guarded real run: the model naturally attaches `compare_views` to an
        image. The prompt now says not to; when it does anyway, M1's scope gate refuses it rather
        than this module quietly stripping the pin — the same guard-1 reasoning as a hallucinated
        actuator, and the refusal is how you learn the prompt is being ignored."""
        payload = model_argument(claims=[{
            "claim": "Pressure rises from the ground to the rotunda.", "target_status": "measured",
            "percepts": [{"actuator": "compare_views", "image": GROUND, "function": "support",
                          "params": {"relation_role": "contrast"}}]}])
        claims = AP.GroqArgumentPlanner(client=FakeClient(payload)).propose(THESIS, hydrated())
        assert claims[0].percepts[0].image == GROUND        # kept verbatim
        bound = A.bind_claim(claims[0], hydrated())
        assert bound.status == A.REFUSED
        assert C.REFUSED_IMAGE_SCOPE in bound.unbound[0][1]

    def test_an_unpinned_comparative_percept_binds(self):
        payload = model_argument(claims=[{
            "claim": "Pressure rises from the ground to the rotunda.", "target_status": "measured",
            "percepts": [{"actuator": "compare_views", "image": None, "function": "challenge",
                          "params": {"relation_role": "contrast"}}]}])
        claims = AP.GroqArgumentPlanner(client=FakeClient(payload)).propose(THESIS, hydrated())
        assert claims[0].percepts[0].image is None
        assert A.bind_claim(claims[0], hydrated()).status == A.SUPPORTED

    def test_exactly_one_call_no_reprompt_loop(self):
        """Guard 3. Looping until every claim binds would manufacture the evidence base for a
        predetermined conclusion."""
        client = FakeClient(model_argument())
        planner = AP.GroqArgumentPlanner(client=client)
        planner.propose(THESIS, hydrated())
        assert planner.calls == 1
        assert len(client.calls) == 1

    def test_a_hallucinated_actuator_passes_through_to_be_refused(self):
        """Guard 1. Dropping it while parsing would hide how often the model invents evidence."""
        payload = model_argument(claims=[{
            "claim": "The façade breathes.", "target_status": "measured",
            "percepts": [{"actuator": "brush_the_vibes", "image": GROUND,
                          "function": "support", "params": {}}]}])
        claims = AP.GroqArgumentPlanner(client=FakeClient(payload)).propose(THESIS, hydrated())
        assert claims[0].percepts[0].actuator == "brush_the_vibes"    # verbatim, not filtered

        bound = A.bind_claim(claims[0], hydrated())
        assert bound.status == A.REFUSED
        assert "unknown_actuator" in bound.unbound[0][1]

    def test_an_image_the_corpus_does_not_hold_passes_through_to_be_refused(self):
        payload = model_argument(claims=[{
            "claim": "The crypt is dark.", "target_status": "measured",
            "percepts": [{"actuator": "rhythm", "image": "post_crypt",
                          "function": "support", "params": {}}]}])
        claims = AP.GroqArgumentPlanner(client=FakeClient(payload)).propose(THESIS, hydrated())
        assert claims[0].percepts[0].image == "post_crypt"
        bound = A.bind_claim(claims[0], hydrated())
        assert bound.status == A.REFUSED
        assert C.REFUSED_UNKNOWN_IMAGE in bound.unbound[0][1]

    def test_disallowed_params_are_dropped_and_recorded(self):
        """Guard 2. The model cannot smuggle in geometry it has no way to possess."""
        payload = model_argument(claims=[{
            "claim": "x", "target_status": "measured",
            "percepts": [{"actuator": "rhythm", "image": GROUND, "function": "support",
                          "params": {"mask": [[0, 0]], "confidence": 0.99}}]}])
        planner = AP.GroqArgumentPlanner(client=FakeClient(payload))
        claims = planner.propose(THESIS, hydrated())
        assert claims[0].percepts[0].step.params == {}
        assert any("dropped: confidence, mask" in n for n in planner.last_notes)

    def test_an_unknown_function_is_kept_verbatim_not_coerced_to_support(self):
        """Guard 6. Mapping it to `support` would let the model dodge the challenge rule with a
        typo, and would put an unreadable rhetorical job on real evidence."""
        payload = model_argument(claims=[{
            "claim": "x", "target_status": "measured",
            "percepts": [{"actuator": "rhythm", "image": GROUND, "function": "vibes-with",
                          "params": {}}]}])
        planner = AP.GroqArgumentPlanner(client=FakeClient(payload))
        claims = planner.propose(THESIS, hydrated())
        assert claims[0].percepts[0].function == "vibes-with"
        assert any("unknown function" in n for n in planner.last_notes)

        bound = A.bind_claim(claims[0], hydrated())
        assert bound.status == A.REFUSED
        assert A.REASON_UNKNOWN_FUNCTION in bound.unbound[0][1]

    def test_an_unavailable_planner_proposes_nothing_and_invents_no_argument(self):
        """Guard 4, the one with no fallback. Nothing rule-based can decompose a thesis, so a
        fallback here would have to invent an argument."""
        planner = AP.GroqArgumentPlanner(client=None)
        planner._client_resolved = True                     # no key, no client
        assert planner.propose(THESIS, hydrated()) == []
        assert any("unavailable" in n for n in planner.last_notes)
        assert any("none were invented" in n for n in planner.last_notes)

    def test_a_planner_that_raises_proposes_nothing_and_says_why(self):
        planner = AP.GroqArgumentPlanner(client=FakeClient(None, raises=True))
        assert planner.propose(THESIS, hydrated()) == []
        assert any("failed: RuntimeError" in n for n in planner.last_notes)

    def test_an_empty_decomposition_is_a_legitimate_answer(self):
        planner = AP.GroqArgumentPlanner(client=FakeClient({"claims": []}))
        assert planner.propose(THESIS, hydrated()) == []
        assert any("proposed no claims" in n for n in planner.last_notes)

    def test_the_claim_cap_is_reported_never_trimmed_silently(self):
        payload = {"claims": [{"claim": f"claim {i}", "percepts": []}
                              for i in range(AP.MAX_CLAIMS + 3)]}
        planner = AP.GroqArgumentPlanner(client=FakeClient(payload))
        claims = planner.propose(THESIS, hydrated())
        assert len(claims) == AP.MAX_CLAIMS
        assert any("kept the first" in n for n in planner.last_notes)


# ── 3. claim↔percept binding ─────────────────────────────────────────────────

class TestBinding:

    def test_a_claim_whose_percepts_resolve_is_supported(self):
        """THE CLAIM: real percepts resolve for it, so it is carried."""
        claim = A.make_claim("c0", "The ground disperses attention.",
                             [("pressure_zone", {"image": GROUND}, A.SUPPORT),
                              ("rhythm", {"image": GROUND}, A.SUPPORT)],
                             target_status=A.MEASURED)
        bound = A.bind_claim(claim, hydrated())
        assert bound.status == A.SUPPORTED
        assert bound.reason == A.REASON_ALL_BOUND
        assert len(bound.bound) == 2
        assert bound.unbound == ()
        assert bound.carried

    def test_a_supported_claim_reaches_only_its_weakest_evidence(self):
        """Two measured fields and one semantic read is an INTERPRETIVE claim, whatever it aimed
        for — four confident measurements must not bury the reading doing the argumentative work."""
        claim = A.make_claim("c0", "The ground disperses attention.",
                             [("pressure_zone", {"image": GROUND}, A.SUPPORT),
                              ("semantic_read", {"image": GROUND, "question": "how?"},
                               A.SUPPORT)],
                             target_status=A.MEASURED)
        bound = A.bind_claim(claim, hydrated())
        assert bound.status == A.SUPPORTED
        assert bound.achieved_status == A.INTERPRETIVE
        assert bound.downgraded, "it aimed at measured and reached interpretive"

    def test_a_claim_targeting_sourced_always_downgrades(self):
        claim = A.make_claim("c0", "Schinkel intended the conversion.",
                             [("rhythm", {"image": GROUND}, A.SUPPORT)],
                             target_status=A.SOURCED)
        bound = A.bind_claim(claim, hydrated())
        assert bound.status == A.SUPPORTED          # the percept runs...
        assert bound.achieved_status == A.MEASURED  # ...but it cannot source anything
        assert bound.downgraded

    def test_each_claim_stands_on_its_own_evidence(self):
        """Rule 2. Claim B needs a region on the rotunda; claim A finds one there. B must NOT be
        carried by evidence gathered to argue A."""
        a = A.make_claim("c0", "Parts can be found on the rotunda.",
                         [("find_parts", {"image": ROTUNDA}, A.SUPPORT)])
        b = A.make_claim("c1", "The rotunda's material recurs.",
                         [("material_field", {"image": ROTUNDA}, A.SUPPORT)])   # needs a REGION
        memory = bare_corpus()                       # nothing committed anywhere
        bound = A.bind_claims([a, b], memory)
        assert bound[0].status == A.SUPPORTED
        assert bound[1].status == A.REFUSED, "claim B borrowed claim A's region"
        assert "region" in bound[1].unbound[0][1]

    def test_binding_is_replayable(self):
        """Step ids come from the claim id and position — no clock, no counter — so the same
        decomposition binds identically twice and two runs can be diffed."""
        memory = hydrated()
        first = A.bind_claims(a_workable_argument(), memory)
        second = A.bind_claims(a_workable_argument(), memory)
        assert [c.to_dict() for c in first] == [c.to_dict() for c in second]

    def test_a_single_image_memory_binds_too(self):
        """The corpus is M1's; a claim about one picture is still a claim."""
        claim = A.make_claim("c0", "The frame is rhythmic.",
                             [("rhythm", {}, A.SUPPORT)])
        bound = A.bind_claim(claim, build_memory(image_ref="i", post_id=GROUND))
        assert bound.status == A.SUPPORTED


# ── 4. argument-level refusal — no evidence is invented ─────────────────────

class TestNoFabrication:

    def test_a_claim_whose_percepts_refuse_is_refused_not_fabricated(self):
        """THE CLAIM: nothing manufactures evidence to carry a claim that cannot be carried."""
        claim = A.make_claim("c0", "The rotunda's material recurs across the wall.",
                             [("material_field", {"image": ROTUNDA}, A.SUPPORT)])
        bound = A.bind_claim(claim, bare_corpus())        # no region anywhere
        assert bound.status == A.REFUSED
        assert bound.reason == A.REASON_NONE_BOUND
        assert bound.bound == ()                          # NOTHING was manufactured
        assert bound.achieved_status == A.UNCERTAIN
        assert not bound.carried

    def test_a_partly_refused_claim_is_qualified_and_keeps_what_it_lost(self):
        """A record holding only what worked makes a qualified claim indistinguishable from a
        supported one — the reader sees one percept either way."""
        claim = A.make_claim("c0", "The rotunda gathers attention.",
                             [("pressure_zone", {"image": ROTUNDA}, A.SUPPORT),
                              ("material_field", {"image": ROTUNDA}, A.SUPPORT)])
        bound = A.bind_claim(claim, bare_corpus())
        assert bound.status == A.QUALIFIED
        assert bound.reason == A.REASON_PARTIAL
        assert [p.actuator for p in bound.bound] == ["pressure_zone"]
        assert [p.actuator for p, _ in bound.unbound] == ["material_field"]
        assert bound.carried                              # it can be said, on less

    def test_a_claim_bound_to_an_image_that_could_not_be_read_says_so(self):
        """Found by the guarded real run. An image-only actuator on an unreadable post BINDS —
        it needs nothing hydration would have supplied — but 'we could not read this image' and
        'we read it and it was empty' are different facts, and M1 kept them apart at the corpus
        level. Losing the distinction one layer up would undo that."""
        memory = C.hydrate_corpus(corpus_fixture(), {GROUND: posts_fixture()[GROUND]})
        claim = A.make_claim("c0", "The rotunda is rhythmic.",
                             [("rhythm", {"image": ROTUNDA}, A.SUPPORT)])
        bound = A.bind_claim(claim, memory)
        assert bound.status == A.SUPPORTED          # the path is plausible...
        assert bound.caveats                        # ...but it is not silent
        assert ROTUNDA in bound.caveats[0]
        assert "assumed, not verified" in bound.caveats[0]

    def test_a_readable_but_empty_image_carries_no_caveat(self):
        """The other half of the distinction: read, and genuinely empty."""
        bound = A.bind_claim(
            A.make_claim("c0", "x", [("rhythm", {"image": ROTUNDA}, A.SUPPORT)]), bare_corpus())
        assert bound.status == A.SUPPORTED
        assert bound.caveats == ()

    def test_the_caveat_reaches_the_gaps_a_reader_cannot_miss(self):
        memory = C.hydrate_corpus(corpus_fixture(), {GROUND: posts_fixture()[GROUND]})
        claims = [A.make_claim("c0", "The rotunda is rhythmic.",
                               [("rhythm", {"image": ROTUNDA}, A.CHALLENGE)])]
        argument = A.plan_argument(THESIS, claims, memory)
        assert any("could not be read" in g["why"] for g in argument.gaps())

    def test_a_claim_with_no_percepts_is_refused_by_a_distinct_reason(self):
        """'Nobody proposed evidence' and 'the evidence refused' are different facts."""
        bound = A.bind_claim(A.make_claim("c0", "It is beautiful.", []), hydrated())
        assert bound.status == A.REFUSED
        assert bound.reason == A.REASON_NO_PERCEPTS

    def test_binding_adds_no_step_the_planner_did_not_propose(self):
        """The repair this module refuses to make: adding a finder so a field can run."""
        claim = A.make_claim("c0", "x", [("material_field", {"image": ROTUNDA}, A.SUPPORT)])
        argument = A.plan_argument(THESIS, [claim], bare_corpus(), require_challenge=False)
        assert argument.plan.steps == ()
        proposed = {p.actuator for p in claim.percepts}
        for row in argument.lineage():
            assert row["actuator"] in proposed

    def test_an_argument_carrying_nothing_is_refused_at_the_argument_level(self):
        claims = [A.make_claim("c0", "x", [("material_field", {"image": ROTUNDA}, A.SUPPORT)]),
                  A.make_claim("c1", "y", [("negative_space", {"image": GROUND}, A.CHALLENGE)])]
        argument = A.plan_argument(THESIS, claims, bare_corpus())
        assert not argument.complete
        assert A.ARGUMENT_NOTHING_CARRIED in [r.reason for r in argument.refusals]
        assert argument.refused and not argument.supported

    def test_an_empty_decomposition_is_refused_not_treated_as_a_working_plan(self):
        argument = A.plan_argument(THESIS, [], hydrated())
        assert not argument.complete
        assert A.ARGUMENT_NO_CLAIMS in [r.reason for r in argument.refusals]

    def test_the_merged_plan_contains_only_bound_percepts(self):
        """A step that refused for its own claim must not slip into the run because another
        claim's resolve happened to place it."""
        claims = [A.make_claim("c0", "x", [("pressure_zone", {"image": GROUND}, A.SUPPORT),
                                           ("material_field", {"image": GROUND}, A.SUPPORT)]),
                  A.make_claim("c1", "y", [("rhythm", {"image": GROUND}, A.CHALLENGE)])]
        argument = A.plan_argument(THESIS, claims, bare_corpus())
        assert sorted(s.actuator for s in argument.plan.steps) == ["pressure_zone", "rhythm"]

    def test_two_claims_wanting_the_same_percept_do_not_fire_it_twice(self):
        claims = [A.make_claim("c0", "x", [("rhythm", {"image": GROUND}, A.SUPPORT)]),
                  A.make_claim("c1", "y", [("rhythm", {"image": GROUND}, A.CHALLENGE)])]
        argument = A.plan_argument(THESIS, claims, hydrated())
        assert len(argument.plan.steps) == 1
        # both claims still cite it — the collapse is in the RUN, not in the lineage
        assert len({r["claim_id"] for r in argument.lineage() if r["bound"]}) == 2


# ── 5. the counter-reading seed ──────────────────────────────────────────────

class TestCounterSeed:

    def test_an_argument_with_a_challenge_percept_passes(self):
        argument = A.plan_argument(THESIS, a_workable_argument(), hydrated())
        assert argument.has_challenge
        assert A.CHALLENGE in argument.functions_present
        assert A.ARGUMENT_NO_CHALLENGE not in [r.reason for r in argument.refusals]

    def test_an_argument_with_no_challenge_is_refused_not_repaired(self):
        """Rule 3. A challenge step this module wrote would be a counter-reading nobody meant,
        and M3 would compose prose from it in perfect good faith."""
        claims = [A.make_claim("c0", "x", [("rhythm", {"image": GROUND}, A.SUPPORT)])]
        argument = A.plan_argument(THESIS, claims, hydrated())
        assert not argument.has_challenge
        assert not argument.complete
        refusal = next(r for r in argument.refusals if r.reason == A.ARGUMENT_NO_CHALLENGE)
        assert "no percept was given the challenge function" in refusal.detail
        # and nothing was inserted
        assert [s.actuator for s in argument.plan.steps] == ["rhythm"]

    def test_a_challenge_that_could_not_be_produced_is_not_a_counter_reading(self):
        """The absence of a counter-reading, reported as such — and worded differently from
        never having proposed one, because a curator debugging this needs to know which."""
        claims = [A.make_claim("c0", "x", [("rhythm", {"image": GROUND}, A.SUPPORT)]),
                  A.make_claim("c1", "y", [("material_field", {"image": ROTUNDA}, A.CHALLENGE)])]
        argument = A.plan_argument(THESIS, claims, bare_corpus())
        assert not argument.has_challenge
        refusal = next(r for r in argument.refusals if r.reason == A.ARGUMENT_NO_CHALLENGE)
        assert "could not be produced" in refusal.detail

    def test_the_requirement_can_be_lifted_deliberately_never_by_accident(self):
        claims = [A.make_claim("c0", "x", [("rhythm", {"image": GROUND}, A.SUPPORT)])]
        argument = A.plan_argument(THESIS, claims, hydrated(), require_challenge=False)
        assert not argument.refusals
        assert argument.complete

    def test_the_planner_reports_a_decomposition_that_proposed_no_challenge(self):
        payload = model_argument(claims=[{
            "claim": "x", "target_status": "measured",
            "percepts": [{"actuator": "rhythm", "image": GROUND, "function": "support",
                          "params": {}}]}])
        planner = AP.GroqArgumentPlanner(client=FakeClient(payload))
        planner.propose(THESIS, hydrated())
        assert any("no 'challenge' percept" in n for n in planner.last_notes)


# ── 6. lineage ───────────────────────────────────────────────────────────────

class TestLineage:

    def test_claim_to_percept_lineage_is_traced(self):
        """THE CLAIM: from the plan alone, a reader can walk claim → percept → actuator → image."""
        argument = A.plan_argument(THESIS, a_workable_argument(), hydrated())
        rows = argument.lineage()
        assert rows

        by_claim = {}
        for row in rows:
            by_claim.setdefault(row["claim_id"], []).append(row)
        assert set(by_claim) == {"c0", "c1", "c2"}

        for row in rows:
            assert row["claim"]                      # the claim text travels with the evidence
            assert row["actuator"]
            assert row["function"] in A.FUNCTIONS or not row["bound"]
            assert row["epistemic_ceiling"] in A.EPISTEMIC_STATUSES
            assert "bound" in row

        ground_rows = [r for r in rows if r["image"] == GROUND]
        assert {r["actuator"] for r in ground_rows} == {"pressure_zone", "rhythm"}

    def test_unbound_percepts_appear_in_the_lineage_with_their_reason(self):
        claims = [A.make_claim("c0", "x", [("pressure_zone", {"image": GROUND}, A.SUPPORT),
                                           ("material_field", {"image": GROUND}, A.CHALLENGE)])]
        argument = A.plan_argument(THESIS, claims, bare_corpus())
        unbound = [r for r in argument.lineage() if not r["bound"]]
        assert len(unbound) == 1
        assert unbound[0]["actuator"] == "material_field"
        assert "region" in unbound[0]["why"]

    def test_the_gaps_name_every_claim_that_is_not_fully_carried(self):
        argument = A.plan_argument(THESIS, a_workable_argument(), bare_corpus())
        gaps = argument.gaps()
        assert gaps
        assert {g["status"] for g in gaps} & {A.REFUSED, A.QUALIFIED, "argument_refused"}

    def test_the_whole_argument_serialises(self):
        argument = A.plan_argument(THESIS, a_workable_argument(), hydrated())
        d = argument.to_dict()
        assert d["thesis"] == THESIS
        assert d["claims_total"] == 3
        assert d["has_challenge"] is True
        assert d["lineage"] and d["plan"]["steps"]
        assert json.dumps(d)                          # no un-serialisable object leaked in


# ── 7. plan-time vs run-time: confirming against a real chain ───────────────

class TestConfirmAgainstRun:

    def _argument(self):
        return A.plan_argument(THESIS, a_workable_argument(), hydrated())

    def _provenance(self, statuses):
        from backend.services.director.execution import ChainProvenance, StepRecord
        return ChainProvenance(
            chain_id="ch", intention=THESIS, workflow=None, planner="argument",
            lineage=tuple(StepRecord(step_id=sid, actuator="x", status=st, position=i,
                                     detail="found nothing" if st == "empty" else "")
                          for i, (sid, st) in enumerate(statuses.items())))

    def test_a_plan_time_binding_says_so(self):
        argument = self._argument()
        assert all(c.binding == A.BINDING_PLANNED for c in argument.claims)

    def test_a_step_that_ran_empty_downgrades_the_claim_it_carried(self):
        """`resolve()` proves the evidence CAN be produced; only a run proves it WAS."""
        argument = self._argument()
        statuses = {p.step.id: "ok" for c in argument.claims for p in c.bound}
        c0 = argument.claims[0]
        statuses[c0.bound[0].step.id] = "empty"          # ran honestly, found nothing

        confirmed = A.confirm_against_chain(argument, self._provenance(statuses))
        first = confirmed.claims[0]
        assert first.binding == A.BINDING_CONFIRMED
        assert first.status == A.QUALIFIED
        assert "empty" in first.unbound[0][1]

    def test_a_claim_whose_every_step_came_back_empty_is_refused_after_the_run(self):
        argument = self._argument()
        statuses = {p.step.id: "ok" for c in argument.claims for p in c.bound}
        for percept in argument.claims[0].bound:
            statuses[percept.step.id] = "empty"
        confirmed = A.confirm_against_chain(argument, self._provenance(statuses))
        assert confirmed.claims[0].status == A.REFUSED
        assert confirmed.claims[0].bound == ()

    def test_confirmation_never_promotes_a_claim(self):
        """A step refused at plan time never ran; no run outcome can speak for it."""
        claims = [A.make_claim("c0", "x", [("pressure_zone", {"image": GROUND}, A.SUPPORT),
                                           ("material_field", {"image": GROUND}, A.CHALLENGE)])]
        argument = A.plan_argument(THESIS, claims, bare_corpus())
        assert argument.claims[0].status == A.QUALIFIED
        statuses = {p.step.id: "ok" for c in argument.claims for p in c.bound}
        confirmed = A.confirm_against_chain(argument, self._provenance(statuses))
        assert confirmed.claims[0].status == A.QUALIFIED       # never promoted to supported
        assert len(confirmed.claims[0].unbound) == 1

    def test_a_run_that_loses_the_challenge_loses_the_counter_reading(self):
        argument = self._argument()
        assert argument.has_challenge
        statuses = {p.step.id: "ok" for c in argument.claims for p in c.bound}
        challenge = next(p for c in argument.claims for p in c.bound
                         if p.function == A.CHALLENGE)
        statuses[challenge.step.id] = "unavailable"
        confirmed = A.confirm_against_chain(argument, self._provenance(statuses))
        assert not confirmed.has_challenge
        assert A.ARGUMENT_NO_CHALLENGE in [r.reason for r in confirmed.refusals]


# ── 8. the whole thing, through the Director ────────────────────────────────

class TestRhetoricalDirector:

    def test_a_thesis_becomes_a_bound_argument(self):
        director = AP.RhetoricalDirector(AP.GroqArgumentPlanner(client=FakeClient(
            model_argument())))
        argument = director.plan(THESIS, hydrated())
        assert argument.thesis == THESIS
        assert argument.planner == AP.PLANNER_ARGUMENT_GROQ
        assert len(argument.claims) == 2
        assert argument.has_challenge
        assert all(c.status == A.SUPPORTED for c in argument.claims)
        assert argument.complete

    def test_an_unavailable_planner_yields_a_refused_argument_not_an_invented_one(self):
        planner = AP.GroqArgumentPlanner(client=None)
        planner._client_resolved = True
        argument = AP.RhetoricalDirector(planner).plan(THESIS, hydrated())
        assert argument.claims == ()
        assert not argument.complete
        assert A.ARGUMENT_NO_CLAIMS in [r.reason for r in argument.refusals]
        assert any("unavailable" in n for n in argument.notes)

    def test_the_altes_museum_thesis_binds_some_claims_and_qualifies_an_unsupportable_one(self):
        """The shape the guarded real run reproduces: claims the corpus can carry are carried, and
        one aimed at evidence it cannot give is honestly qualified rather than fabricated."""
        claims = [
            A.make_claim("c0", "The ground disperses attention across the frame.",
                         [("pressure_zone", {"image": GROUND}, A.SUPPORT),
                          ("rhythm", {"image": GROUND}, A.COMPLICATE)],
                         target_status=A.MEASURED),
            A.make_claim("c1", "The rotunda gathers it to a centre.",
                         [("pressure_zone", {"image": ROTUNDA}, A.SUPPORT),
                          ("rhythm", {"image": ROTUNDA}, A.CHALLENGE)],
                         target_status=A.MEASURED),
            A.make_claim("c2", "The stone of the rotunda recurs from the façade.",
                         [("material_field", {"image": ROTUNDA}, A.SUPPORT)],
                         target_status=A.MEASURED),
        ]
        argument = A.plan_argument(THESIS, claims, bare_corpus())
        by_id = {c.claim_id: c for c in argument.claims}
        assert by_id["c0"].status == A.SUPPORTED
        assert by_id["c1"].status == A.SUPPORTED
        assert by_id["c2"].status == A.REFUSED         # no region to measure material over
        assert by_id["c2"].bound == ()                 # and nothing was invented for it
        assert argument.has_challenge
        assert not argument.complete                   # honest, not complete
        assert argument.gaps()
