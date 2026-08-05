"""
CIRCUIT-003 M5 — the epistemic-status layer: system-wide guard, rigorous classification.

M6 seeded the vocabulary and ran `guard` on ONE producer's output, where it was redundant by
construction. These tests are about what changes when it runs on EVERYTHING: the guard stops
being a formality and becomes the single place a claim's stated kind is checked against the
kind its producer is classified as — on every path into the quarantine, for every producer.

The four the build gate names, and where they live:
  every producer's output carries a status from the table  → §1
  guard rejects an improper crossing on ANY producer       → §2
  a `sourced` statement stays sourced everywhere           → §3
  a degraded/uncalibrated producer tags `uncertain`        → §4
"""
from __future__ import annotations

import pytest

from backend.services import epistemics
from backend.services import suggestion_service as ss
from backend.services.epistemics import EpistemicStatus, EpistemicViolation


# ── 1. every producer is classified, and every descriptor carries it ─────────

def test_every_frozen_producer_has_a_classification():
    """The vocabulary of producers and the vocabulary of kinds must not drift. A producer
    absent from the tables falls to `uncertain`, which is safe — but silently safe is how a
    real classification goes missing, so the classification is pinned against the constants.

    ROLES-001 moved the producers whose claim IS their role's own output onto that role's
    `epistemic_ceiling`, so this asks `classified_producers()` rather than reaching into
    `_DEFAULTS`. Same guard, one surface wider — and deliberately NOT
    `default_status_for(p) is not UNCERTAIN`, which would pass for a producer that had fallen
    through unclassified and fail for `external_limit`, which is classified `uncertain` on
    purpose.
    """
    producers = {getattr(ss, name) for name in dir(ss) if name.startswith("PRODUCER_")}
    missing = producers - epistemics.classified_producers()
    assert not missing, f"producers with no epistemic classification: {sorted(missing)}"


def test_the_classification_covers_the_four_families():
    """Extents visible, computed fields measured, readings interpretive, research sourced."""
    d = epistemics.default_status_for
    assert d(ss.PRODUCER_SAM) is EpistemicStatus.VISIBLE
    assert d(ss.PRODUCER_GROUNDED_SAM) is EpistemicStatus.VISIBLE
    assert d(ss.PRODUCER_NEGATIVE_SPACE) is EpistemicStatus.MEASURED
    assert d(ss.PRODUCER_MATERIAL) is EpistemicStatus.MEASURED
    assert d(ss.PRODUCER_ARCHITECTURAL_AXIS) is EpistemicStatus.MEASURED
    assert d(ss.PRODUCER_SEMANTIC) is EpistemicStatus.INTERPRETIVE
    assert d(ss.PRODUCER_PRESENCE_CHECK) is EpistemicStatus.INTERPRETIVE
    assert d("compose_percept") is EpistemicStatus.INTERPRETIVE
    assert d("historical_source") is EpistemicStatus.SOURCED


@pytest.mark.parametrize("descriptor", [
    ss.suggestion_from_refine_region({"id": "r1", "label": "arch"}, run_id="run1"),
    ss._field_descriptor(producer=ss.PRODUCER_NEGATIVE_SPACE, role="negative_space",
                         label="negative space", source_ref="r1",
                         strokes=[{"points": [[0.5, 0.5]], "radius": 0.05}], run_id="run1",
                         adapter="geometry", latency_ms=1.0, confidence=None),
])
def test_real_descriptors_pass_the_widened_guard(descriptor):
    assert epistemics.guard([descriptor]) == [descriptor]
    assert descriptor[epistemics.STATUS_KEY] in [s.value for s in EpistemicStatus]


def test_an_untagged_descriptor_is_refused():
    """Silence is not permitted. An untagged claim reaching review is indistinguishable from a
    confident one to anyone reading the surface."""
    with pytest.raises(EpistemicViolation) as exc:
        epistemics.guard([{"producer": "rhythm", "type": "brush_field"}])
    assert "no epistemic status" in str(exc.value)


# ── 2. the generalized wall: no producer may promote its own claim ───────────

@pytest.mark.parametrize("producer,improper", [
    ("semantic_read", "measured"),        # a reading is not a measurement
    ("semantic_read", "visible"),         # nor an extent
    ("compose_percept", "visible"),
    ("rhythm", "visible"),                # a field is not an extent you can point at
    ("external_limit", "measured"),       # the uncalibrated case cannot promote itself
    ("sam_refine", "measured"),           # even between two image statuses
    ("find_similar", "interpretive"),
])
def test_guard_rejects_an_improper_crossing_on_any_producer(producer, improper):
    """The M6 wall was sourced→visible. M5's is every promotion, on every producer."""
    with pytest.raises(EpistemicViolation) as exc:
        epistemics.guard([{"producer": producer, "type": "brush_field",
                           epistemics.STATUS_KEY: improper}])
    assert producer in str(exc.value)


@pytest.mark.parametrize("producer", ["rhythm", "semantic_read", "sam_refine", "material_field",
                                      "presence_check", "find_similar", "architectural_axis"])
def test_any_producer_may_weaken_its_own_claim(producer):
    """`uncertain` is the one move available, because it is the only one that makes a claim
    weaker. A producer is always entitled to say it is not sure."""
    d = {"producer": producer, "type": "brush_field",
         epistemics.STATUS_KEY: EpistemicStatus.UNCERTAIN.value}
    assert epistemics.guard([d]) == [d]
    assert epistemics.declare(producer, EpistemicStatus.UNCERTAIN) is EpistemicStatus.UNCERTAIN


def test_declare_refuses_a_promotion():
    with pytest.raises(EpistemicViolation):
        epistemics.declare("semantic_read", EpistemicStatus.MEASURED)
    with pytest.raises(EpistemicViolation):
        epistemics.declare("rhythm", EpistemicStatus.VISIBLE)


def test_stamp_cannot_be_used_to_promote():
    """"The producer said so" is not a route around the classification."""
    with pytest.raises(EpistemicViolation):
        epistemics.stamp({"producer": "semantic_read", "type": "region_mask"},
                         status=EpistemicStatus.VISIBLE)


def test_retag_and_guard_agree_on_what_is_legal():
    """Two guards that disagree are one guard plus a hole."""
    for producer in ("rhythm", "semantic_read", "sam_refine", "historical_source"):
        allowed = epistemics.permitted_statuses(producer)
        for status in EpistemicStatus:
            d = {"producer": producer, "type": "brush_field",
                 epistemics.STATUS_KEY: epistemics.default_status_for(producer).value}
            retag_ok = True
            try:
                epistemics.retag(d, status)
            except EpistemicViolation:
                retag_ok = False
            assert retag_ok == (status in allowed), (producer, status)


# ── 3. `sourced` stays sourced, everywhere ──────────────────────────────────

def test_a_sourced_producer_admits_no_alternative_at_all():
    """Not even `uncertain`. A thin quotation is still a quotation; its weakness belongs in
    `confidence`, and moving it to an image status is the crossing the wall exists for."""
    assert epistemics.permitted_statuses("historical_source") == frozenset({EpistemicStatus.SOURCED})
    for status in EpistemicStatus:
        if status is EpistemicStatus.SOURCED:
            continue
        with pytest.raises(EpistemicViolation):
            epistemics.declare("historical_source", status)


def test_the_run_cannot_weaken_a_sourced_claim():
    """`status_for` degrades image producers; a walled one is untouched by both routes."""
    assert epistemics.status_for("historical_source", confidence=0.01, threshold=1.0) \
        is EpistemicStatus.SOURCED
    assert epistemics.status_for("historical_source", degraded=True) is EpistemicStatus.SOURCED


def test_a_sourced_statement_survives_the_widened_guard():
    from backend.services import external_source_service as ess
    doc = ess.SourceDocument(
        text="Schinkel conceived the museum as a civic temple for the citizens of the state.",
        citation=ess.Citation(title="Altes Museum", url="https://en.wikipedia.org/wiki/Altes_Museum",
                              publisher="Wikipedia", source_id="wikipedia:1", revision="1"))
    d = ess.SourcedStatement.from_document(
        doc, "Schinkel conceived the museum as a civic temple for the citizens of the state.",
        confidence=0.7).to_descriptor(run_id="r", provider="wikipedia")
    assert epistemics.guard([d]) == [d]
    assert d[epistemics.STATUS_KEY] == "sourced"


# ── 4. uncertain is real, not decorative ────────────────────────────────────

def test_the_uncalibrated_producer_is_structurally_uncertain():
    """`external_limit` refuses on MIN_PROJECTIVE_SPREAD, which the producer itself labels
    UNCALIBRATED — a synthetic placeholder. A gate that admits it may be wrong does not yield
    a measurement."""
    assert epistemics.default_status_for(ss.PRODUCER_EXTERNAL_LIMIT) is EpistemicStatus.UNCERTAIN
    src = open(ss.__file__, encoding="utf-8").read()
    assert "UNCALIBRATED" in src        # the reason is still declared where the number lives


def test_a_reading_that_only_just_cleared_its_gate_is_uncertain():
    assert epistemics.is_marginal(0.051, 0.05) is True      # cleared by a whisker
    assert epistemics.is_marginal(0.40, 0.05) is False      # cleared comfortably
    assert epistemics.status_for("rhythm", confidence=0.051, threshold=0.05) \
        is EpistemicStatus.UNCERTAIN
    assert epistemics.status_for("rhythm", confidence=0.40, threshold=0.05) \
        is EpistemicStatus.MEASURED


def test_a_missing_confidence_is_not_evidence_of_marginality():
    """Inventing marginality to be safe would put `uncertain` on the deterministic operators
    that never reported a number — the decorative use of the word this rule exists to avoid."""
    assert epistemics.is_marginal(None, 0.05) is False
    assert epistemics.is_marginal(0.5, None) is False
    assert epistemics.status_for("negative_space") is EpistemicStatus.MEASURED


def test_a_degraded_run_tags_uncertain():
    assert epistemics.status_for("material_field", degraded=True) is EpistemicStatus.UNCERTAIN


def test_the_marginal_rule_reaches_the_real_producers():
    """The wiring, not just the helper: a barely-there field comes out `uncertain` and an
    unmistakable one comes out `measured`, from the same producer on the same code path."""
    def rhythm(peak):
        grid = 4
        energy = [0.10] * (grid * grid)
        energy[0] = peak
        return ss.suggestion_from_rhythm({"energy": energy, "grid": grid}, run_id="run1",
                                         threshold=0.0, grid_sample=4)

    # relief = (hi - lo) / hi. With a floor of 0.10, a peak of 0.1075 gives ≈0.070 — above the
    # 0.05 gate (so the producer does not refuse) but inside 2× it (so it is only just there).
    marginal = rhythm(0.1075)
    solid = rhythm(1.0)            # relief ≈ 0.90 → unmistakable
    assert marginal and solid
    assert marginal[epistemics.STATUS_KEY] == "uncertain"
    assert solid[epistemics.STATUS_KEY] == "measured"
    # and both are legal claims for this producer
    assert epistemics.guard([marginal, solid]) == [marginal, solid]


def test_uncertain_is_not_the_universal_answer():
    """A rule that tagged everything `uncertain` would be as useless as one that tagged nothing.
    A comfortable reading from a calibrated producer stays `measured`."""
    d = ss._field_descriptor(
        producer=ss.PRODUCER_RHYTHM, role="rhythm", label="rhythm", source_ref="r1",
        strokes=[{"points": [[0.5, 0.5]], "radius": 0.05}], run_id="run1",
        adapter="cpu_perceptual", latency_ms=1.0, confidence=0.42, threshold=0.05)
    assert d[epistemics.STATUS_KEY] == "measured"
