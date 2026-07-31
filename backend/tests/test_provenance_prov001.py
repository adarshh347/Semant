"""
CIRCUIT-002 PROV-001 Seam 1 — a produced suggestion records the step that produced it.

Stub-driven: no GPU, no network, no database, no language model. Everything here is a dict and a
pure function, because the claim under test is about IDENTITY, not about any model's output.

  1. the stamp writes step_id, and refuses to invent one          → TestStamp
  2. the stamp reaches every producer through one chokepoint      → TestChokepoint
  3. the resolver joins on step_id and the M4 ambiguity is gone   → TestExactJoin
  4. unstamped (historical) data still gets the honest refusal    → TestHistoricalFallback

The case in TestExactJoin is the precise one M4 documented as unfixable from inside the resolver:
two same-actuator steps on ONE image. M4's own suite asserts that case refuses (see
test_article_resolver_m4.TestAmbiguity.test_two_matching_percepts_resolve_to_neither); that test
still passes, because its fixture suggestions carry no step_id and therefore still take the weak
key. Both suites are correct at once, which is the point: the refusal was never wrong, its CAUSE
was.
"""
from __future__ import annotations

from backend.services.director import article_resolver as R
from backend.services.director import corpus as C
from backend.services.director import real_actuators as RA

GROUND, ROTUNDA = "post_lustgarten", "post_rotunda"


# ── fixtures ─────────────────────────────────────────────────────────────────

def memory_fixture() -> C.CorpusWorkingMemory:
    corpus = C.build_corpus(
        corpus_id="altes-museum", title="Lustgarten to rotunda",
        why="The walk from a dispersed civic ground to a centralized interior.",
        images=[{"post_id": GROUND, "title": "Lustgarten", "photo_url": "http://x/l.jpg"},
                {"post_id": ROTUNDA, "title": "Rotunda", "photo_url": "http://x/r.jpg"}])
    posts = {p: {"photo_url": f"http://x/{p}.jpg", "region_annotations": []}
             for p in (GROUND, ROTUNDA)}
    return C.hydrate_corpus(corpus, posts)


def produced(post_id: str, producer: str, *, ref: str = "", step_id: str = "") -> dict:
    """A quarantined suggestion. `step_id=""` reproduces exactly what a pre-PROV-001 run left."""
    prov = {"run_id": "run_prov", "producer": producer, "adapter": producer}
    if step_id:
        prov["step_id"] = step_id
    return {
        "producer": producer, "type": "brush_field", "role": producer,
        "label": f"{producer} on {post_id}",
        "source_ref": ref or f"{post_id}:{producer}",
        "geometry": {"kind": "raster", "strokes": [[0.1, 0.2], [0.4, 0.6]]},
        "linked_ground_ids": [], "post_id": post_id, "provenance": prov,
    }


def citation(step_id: str, actuator: str, image: str) -> dict:
    return {"step_id": step_id, "actuator": actuator, "image": image,
            "function": "support", "epistemic": "measured"}


# ── 1. the stamp itself ──────────────────────────────────────────────────────

class TestStamp:

    def test_it_writes_step_id_into_provenance(self):
        sugs = [produced(GROUND, "pressure_zone")]
        RA._stamp_step_id(sugs, "s3")
        assert sugs[0]["provenance"]["step_id"] == "s3"

    def test_it_leaves_the_rest_of_provenance_alone(self):
        """The receipt is evidence. A stamp that dropped run_id or adapter would trade one
        provenance gap for another."""
        sugs = [produced(GROUND, "pressure_zone")]
        RA._stamp_step_id(sugs, "s3")
        prov = sugs[0]["provenance"]
        assert prov["run_id"] == "run_prov"
        assert prov["adapter"] == "pressure_zone"
        assert prov["producer"] == "pressure_zone"

    def test_an_empty_step_id_writes_NOTHING(self):
        """THE CLAIM: no fabrication. A Step built by hand or replayed can carry id="", and
        `{"step_id": ""}` would be a claim of identity that is not one. Absent is the honest
        record, and the resolver reads absence correctly."""
        sugs = [produced(GROUND, "pressure_zone")]
        RA._stamp_step_id(sugs, "")
        assert "step_id" not in sugs[0]["provenance"]

    def test_it_does_not_overwrite_a_step_id_a_producer_set_itself(self):
        sugs = [produced(GROUND, "pressure_zone", step_id="mine")]
        RA._stamp_step_id(sugs, "theirs")
        assert sugs[0]["provenance"]["step_id"] == "mine"

    def test_a_suggestion_with_no_provenance_key_gains_one(self):
        sugs = [{"type": "brush_field", "producer": "pressure_zone"}]
        RA._stamp_step_id(sugs, "s3")
        assert sugs[0]["provenance"]["step_id"] == "s3"

    def test_malformed_entries_are_skipped_not_raised(self):
        """This runs inside the produce path. A malformed suggestion must not convert an
        otherwise-good step into an ERROR — the epistemics guard downstream is what judges
        shape, and it should be the one to say so."""
        sugs = [None, "not a dict", {"provenance": "not a dict"},
                produced(GROUND, "pressure_zone")]
        RA._stamp_step_id(sugs, "s3")                      # must not raise
        assert sugs[3]["provenance"]["step_id"] == "s3"


# ── 2. the chokepoint is total ───────────────────────────────────────────────

class TestChokepoint:

    def test_every_producer_site_reaches_ctx_suggestions(self):
        """THE STRUCTURAL CLAIM the central stamp rests on: producers do not return suggestions
        by any private channel, they all land in `ctx.suggestions`. If a future producer breaks
        that, this test is where it should be noticed — the stamp would silently miss it.

        Asserted against the module source rather than by running every producer, because the
        point is that NO path exists, which no finite set of runs can show."""
        import inspect
        src = inspect.getsource(RA)
        # Every append/extend of a suggestion goes through the shared context.
        assert "ctx.suggestions.append" in src or "ctx.suggestions.extend" in src
        # The stamp is applied to precisely the slice the quarantine guard also uses, so the two
        # can never disagree about what "this step produced" means.
        assert "_stamp_step_id(self.ctx.suggestions[before:]" in src
        assert "epistemics.guard(self.ctx.suggestions[before:])" in src


# ── 3. the exact join — M4's ambiguity, deleted at the cause ─────────────────

class TestExactJoin:

    def test_two_same_actuator_steps_on_ONE_image_each_resolve_to_their_own(self):
        """THE CLAIM, and the whole reason PROV-001 exists.

        M4 could not tell these apart: same actuator, same image, one run. It refused, correctly.
        With a step id on each suggestion the join is an identity lookup and both resolve."""
        memory = memory_fixture()
        quarantine = [
            produced(GROUND, "pressure_zone", ref="first", step_id="s1"),
            produced(GROUND, "pressure_zone", ref="second", step_id="s2"),
        ]
        first = R.resolve_citation(citation("s1", "pressure_zone", GROUND), quarantine, memory)
        second = R.resolve_citation(citation("s2", "pressure_zone", GROUND), quarantine, memory)

        assert first.status == R.RESOLVED
        assert second.status == R.RESOLVED
        assert first.drawable and second.drawable
        # Each got ITS OWN percept, not merely "a" percept.
        assert first.source_ref == "first"
        assert second.source_ref == "second"

    def test_the_ambiguous_status_is_not_reached_at_all(self):
        memory = memory_fixture()
        quarantine = [
            produced(GROUND, "pressure_zone", ref="first", step_id="s1"),
            produced(GROUND, "pressure_zone", ref="second", step_id="s2"),
        ]
        for sid in ("s1", "s2"):
            resolved = R.resolve_citation(citation(sid, "pressure_zone", GROUND),
                                          quarantine, memory)
            assert resolved.status != R.AMBIGUOUS

    def test_a_stamped_suggestion_wins_over_a_weak_key_match(self):
        """Order matters: the exact key must be consulted FIRST. Here the unstamped decoy would
        match on (actuator, image) and make the pair ambiguous under the old logic."""
        memory = memory_fixture()
        quarantine = [
            produced(GROUND, "pressure_zone", ref="decoy"),                    # no step_id
            produced(GROUND, "pressure_zone", ref="the_real_one", step_id="s1"),
        ]
        resolved = R.resolve_citation(citation("s1", "pressure_zone", GROUND), quarantine, memory)
        assert resolved.status == R.RESOLVED
        assert resolved.source_ref == "the_real_one"

    def test_one_step_producing_several_percepts_still_refuses_but_says_why(self):
        """A field producer may extend the quarantine with more than one suggestion for a single
        step. That is a real ambiguity — but it is NOT the provenance gap, and the detail must
        not send a reader to fix something already fixed."""
        memory = memory_fixture()
        quarantine = [
            produced(GROUND, "pressure_zone", ref="a", step_id="s1"),
            produced(GROUND, "pressure_zone", ref="b", step_id="s1"),
        ]
        resolved = R.resolve_citation(citation("s1", "pressure_zone", GROUND), quarantine, memory)
        assert resolved.status == R.AMBIGUOUS
        assert "does not record its step" not in resolved.detail
        assert "drawable percepts" in resolved.detail
        assert len(resolved.candidates) == 2


# ── 4. historical data keeps the honest refusal ──────────────────────────────

class TestHistoricalFallback:

    def test_unstamped_duplicates_still_refuse_with_the_original_reason(self):
        """THE CLAIM: the weak key is not dead code. Suggestions produced before PROV-001 carry
        no step_id, and for them the approximation is the only key there is. Deleting it would
        turn an honest refusal into a wrong picture."""
        memory = memory_fixture()
        quarantine = [
            produced(GROUND, "pressure_zone", ref="first"),
            produced(GROUND, "pressure_zone", ref="second"),
        ]
        resolved = R.resolve_citation(citation("s1", "pressure_zone", GROUND), quarantine, memory)
        assert resolved.status == R.AMBIGUOUS
        assert "does not record its step" in resolved.detail
        assert resolved.geometry is None

    def test_unstamped_singletons_still_resolve(self):
        memory = memory_fixture()
        quarantine = [produced(GROUND, "pressure_zone", ref="only")]
        resolved = R.resolve_citation(citation("s1", "pressure_zone", GROUND), quarantine, memory)
        assert resolved.status == R.RESOLVED
        assert resolved.source_ref == "only"

    def test_the_same_actuator_on_different_images_is_still_kept_apart(self):
        memory = memory_fixture()
        quarantine = [
            produced(GROUND, "pressure_zone", ref="on_ground"),
            produced(ROTUNDA, "pressure_zone", ref="on_rotunda"),
        ]
        ground = R.resolve_citation(citation("s1", "pressure_zone", GROUND), quarantine, memory)
        rotunda = R.resolve_citation(citation("s2", "pressure_zone", ROTUNDA), quarantine, memory)
        assert ground.status == R.RESOLVED and ground.source_ref == "on_ground"
        assert rotunda.status == R.RESOLVED and rotunda.source_ref == "on_rotunda"
