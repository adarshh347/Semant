"""
PERCEPTUAL-FORMS-001F — the benchmark, and the checks that keep it honest.

FOUR THINGS ARE TESTED HERE, and the second is the one that would be easy to leave out:

  1. THE SCORERS REFUSE. Most of this file is cases where a number would be wrong to produce —
     different rasters, an absent prediction, a contour with no threshold, an annotation with
     several legitimate readings. A benchmark that returns 0.0 for those has invented data.

  2. THE CONSTRUCTED TRUTH AGREES WITH LANE B'S SUBSTRATE. Every control is drawn by placing
     pixels, so its fragment count is a fact about the drawing. `extent_forms` then counts the
     same mask independently, and the two are asserted equal. If they ever part, one of them is
     wrong and the disagreement is the finding — which is precisely what deriving the truth FROM
     the substrate would have hidden.

  3. THE MANIFESTS DO NOT DRIFT. `--check` on the controls and the matrix, run as tests, so a
     script edit that changes a control fails the suite rather than a review.

  4. THE ATLAS SAYS WHAT IT MAY DO. Every entry carries a rights block; nothing claims committed
     bytes; every cross-lane reference resolves and matches Lane C's own digest.

NO ML STACK. Everything here is stdlib plus pydantic, both of which CI installs, so these run on
every pull request. That was a design constraint on the whole lane, not a happy accident.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import perception_lab_form_benchmark as bench  # noqa: E402
import perception_lab_form_scoring as scoring  # noqa: E402

from backend.services.perception_lab.extent_forms.boundary import trace  # noqa: E402
from backend.services.perception_lab.extent_forms.holes import voids_of  # noqa: E402
from backend.services.perception_lab.extent_forms.raster import (  # noqa: E402
    foreground_components,
    raster_of,
)

CONTROLS = json.loads((bench.CONTROLS_DIR / "manifest.json").read_text(encoding="utf-8"))
ATLAS = json.loads(bench.ATLAS_PATH.read_text(encoding="utf-8"))
MATRIX = json.loads(bench.MATRIX_PATH.read_text(encoding="utf-8"))

FULL = {"size": [4, 4], "counts": [0, 16]}
EMPTY = {"size": [4, 4], "counts": [16]}
HALF = {"size": [4, 4], "counts": [0, 8, 8]}          # the first two columns
OTHER_HALF = {"size": [4, 4], "counts": [8, 8]}       # the last two


# ══ 1. the scorers refuse rather than inventing a number ════════════════════

class TestARefusalIsNotAZero:
    def test_a_score_carries_a_value_or_a_reason_and_never_both(self):
        with pytest.raises(ValueError, match="value OR a refusal"):
            scoring.Score("iou", 0.5, refused="also refused")
        with pytest.raises(ValueError, match="value OR a refusal"):
            scoring.Score("iou", None)

    def test_a_metric_outside_the_declared_vocabulary_cannot_be_built(self):
        with pytest.raises(ValueError, match="not a metric this benchmark declares"):
            scoring.Score("vibes", 1.0)

    def test_every_declared_metric_is_a_contract_method_or_a_named_extension(self):
        for metric in scoring.ALL_METRICS:
            assert metric in scoring.COMPARISON_METHODS or metric in scoring.EXTENSIONS
        for name, why in scoring.EXTENSIONS.items():
            assert name not in scoring.COMPARISON_METHODS
            assert len(why) > 40, f"{name} does not say why it could not be a contract method"

    def test_an_absent_prediction_refuses_and_says_it_is_not_a_zero(self):
        score = scoring.mask_iou(FULL, None)
        assert not score.scored
        assert "not a score of zero" in score.refused

    def test_two_rasters_refuse_rather_than_resampling(self):
        score = scoring.mask_iou(HALF, {"size": [8, 8], "counts": [64]})
        assert not score.scored
        assert "Resampling one" in score.refused

    def test_both_empty_scores_one_and_says_why(self):
        # "looked and found nothing, correctly" is a real result the contract has a law about.
        score = scoring.mask_iou(EMPTY, EMPTY)
        assert score.value == 1.0
        assert score.detail["both_empty"] is True

    def test_an_empty_prediction_against_a_real_truth_scores_zero_not_a_refusal(self):
        score = scoring.mask_iou(HALF, EMPTY)
        assert score.value == 0.0          # the producer answered, and was wrong

    def test_aggregate_counts_refusals_apart_from_zeros(self):
        summary = scoring.aggregate([
            scoring.mask_iou(HALF, HALF),        # 1.0
            scoring.mask_iou(HALF, OTHER_HALF),  # 0.0
            scoring.mask_iou(HALF, None),        # refused
        ])
        iou = summary["metrics"]["iou"]
        assert iou["n"] == 3
        assert iou["scored"] == 2
        assert iou["refused"] == 1
        assert iou["mean"] == 0.5              # over the SCORED items only
        assert iou["coverage"] == pytest.approx(2 / 3)
        assert "answers ten of a hundred" in summary["note"]


# ══ 2. no forced collapse ═══════════════════════════════════════════════════

class TestNoForcedCollapse:
    def test_coverage_scores_the_whole_set_and_names_what_was_missed(self):
        legitimate = [{"reading_id": "a", "mask_rle": HALF},
                      {"reading_id": "b", "mask_rle": OTHER_HALF}]
        score = scoring.hypothesis_coverage(legitimate, [{"alternative_id": "x", "mask_rle": HALF}])
        assert score.value == 0.5
        assert score.detail["missed"] == ["b"]
        assert score.detail["collapsed"] is True

    def test_returning_one_of_several_readings_is_not_an_error(self):
        legitimate = [{"reading_id": "a", "mask_rle": HALF},
                      {"reading_id": "b", "mask_rle": OTHER_HALF}]
        score = scoring.hypothesis_coverage(legitimate, [{"alternative_id": "x", "mask_rle": HALF}])
        assert "not an error" in score.detail["note"]

    def test_an_offered_reading_nobody_called_legitimate_is_named_not_ignored(self):
        score = scoring.hypothesis_coverage(
            [{"reading_id": "a", "mask_rle": HALF}],
            [{"alternative_id": "x", "mask_rle": HALF}, {"alternative_id": "y", "mask_rle": OTHER_HALF}])
        assert score.value == 1.0
        assert score.detail["unmatched_offered"] == ["y"]

    def test_ontology_agreement_reports_every_reading_not_only_the_best(self):
        legitimate = [{"reading_id": "body", "label": "figure", "mask_rle": HALF},
                      {"reading_id": "body_shadow", "label": "figure+shadow", "mask_rle": FULL}]
        score = scoring.extent_ontology_agreement(legitimate, HALF)
        assert score.detail["matched_reading"] == "body"
        assert len(score.detail["per_reading"]) == 2
        assert all(r["iou"] is not None for r in score.detail["per_reading"])

    def test_an_annotation_with_several_readings_must_say_so_explicitly(self, tmp_path):
        # The validator's job: a record with three readings and the flag left true tells a scorer
        # it may take the first one.
        record = json.loads(
            (bench.ANNOTATIONS_DIR / "competing-extents.trained.json").read_text(encoding="utf-8"))
        assert len(record["legitimate_readings"]) > 1
        assert record["single_correct_answer"] is False

    def test_every_committed_reading_gives_a_reason(self):
        for path in sorted(bench.ANNOTATIONS_DIR.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            for reading in record["legitimate_readings"]:
                assert reading.get("why"), f"{path.name}: {reading['reading_id']} has no reason"


# ══ 3. visible and inferred are never pooled ════════════════════════════════

class TestVisibleAndInferredStayApart:
    def test_the_result_has_no_mean_and_says_why(self):
        result = scoring.partition_accuracy(
            {"visible": {"mask_rle": HALF}, "inferred": {"mask_rle": OTHER_HALF}},
            {"visible": {"mask_rle": HALF}, "inferred": {"mask_rle": HALF}})
        assert not hasattr(result, "mean")
        assert "not poolable" in result.as_dict()["no_summary_because"]
        assert result.parts["visible"].value == 1.0
        assert result.parts["inferred"].value == 0.0

    def test_a_missing_part_refuses_rather_than_scoring_zero(self):
        # A producer may simply not implement `unknown`. That is not the same as getting it wrong.
        result = scoring.partition_accuracy(
            {"visible": {"mask_rle": HALF}, "unknown": {"mask_rle": OTHER_HALF}},
            {"visible": {"mask_rle": HALF}})
        assert result.parts["visible"].scored
        assert not result.parts["unknown"].scored
        assert "may not implement one" in result.parts["unknown"].refused

    def test_the_parts_are_the_contract_s_own(self):
        assert scoring.PARTITION_PARTS == ("visible", "inferred", "unknown")


# ══ 4. a field is not a mask ════════════════════════════════════════════════

class TestFieldsAreScoredAsFields:
    FIELD = [0.0, 0.25, 0.5, 0.75, 1.0, 1.0, 0.5, 0.0]

    def test_a_contour_refuses_without_a_declared_threshold(self):
        score = scoring.contour_agreement(self.FIELD, self.FIELD)
        assert not score.scored
        assert "level set with" in score.refused

    def test_a_contour_scores_at_a_declared_level(self):
        score = scoring.contour_agreement(self.FIELD, self.FIELD, level=0.5)
        assert score.value == 1.0
        assert score.detail["level"] == 0.5

    def test_calibration_and_l1_are_different_measurements(self):
        # A monotone but badly scaled field matches poorly on L1 and is badly calibrated in a way
        # the L1 number alone does not name.
        squashed = [v * 0.5 for v in self.FIELD]
        l1 = scoring.field_l1(self.FIELD, squashed)
        ece = scoring.field_calibration(self.FIELD, squashed)
        assert l1.value > 0
        assert ece.value > 0
        assert ece.metric == "calibration_error" and l1.metric == "field_l1"
        assert any(b["n"] for b in ece.detail["reliability"])

    def test_a_perfectly_calibrated_field_scores_zero_error(self):
        assert scoring.field_calibration(self.FIELD, self.FIELD).value == pytest.approx(0.0)

    def test_fields_of_different_shapes_refuse(self):
        assert not scoring.field_l1(self.FIELD, self.FIELD[:4]).scored
        assert not scoring.field_calibration(self.FIELD, self.FIELD[:4]).scored


# ══ 5. direction is part of an edge ═════════════════════════════════════════

class TestDirectionIsPartOfTheClaim:
    TRUTH = [{"source": "a", "target": "b", "kind": "contains", "directed": True},
             {"source": "b", "target": "c", "kind": "meets", "directed": False}]

    def test_an_undirected_edge_is_normalised_by_endpoint_order(self):
        flipped = [{"source": "c", "target": "b", "kind": "meets", "directed": False}]
        score = scoring.graph_score([self.TRUTH[1]], flipped)
        assert score.value == 1.0        # one measurement, two spellings

    def test_a_reversed_containment_is_a_wrong_edge(self):
        reversed_edge = [{"source": "b", "target": "a", "kind": "contains", "directed": True}]
        score = scoring.graph_score([self.TRUTH[0]], reversed_edge)
        assert score.value == 0.0

    def test_direction_accuracy_reads_separately_from_recall(self):
        reversed_edge = [{"source": "b", "target": "a", "kind": "contains", "directed": True}]
        score = scoring.direction_accuracy(self.TRUTH, reversed_edge)
        assert score.value == 0.0
        assert score.detail["reversed"] == 1
        assert score.detail["reversed_pairs"] == [{"truth": "a→b", "predicted": "b→a"}]

    def test_direction_refuses_when_the_producer_found_no_directed_edge(self):
        score = scoring.direction_accuracy(self.TRUTH, [self.TRUTH[1]])
        assert not score.scored
        assert "edge recall is the finding" in score.refused

    def test_direction_refuses_when_nothing_in_the_truth_is_directed(self):
        score = scoring.direction_accuracy([self.TRUTH[1]], [self.TRUTH[1]])
        assert not score.scored
        assert "property of this scene" in score.refused


# ══ 6. the other metric families ════════════════════════════════════════════

class TestTheRemainingFamilies:
    def test_boundary_f1_carries_its_tolerance(self):
        score = scoring.boundary_f1(HALF, HALF, tolerance_px=3)
        assert score.detail["tolerance_px"] == 3      # uninterpretable without it

    def test_rings_match_by_vertex_set_so_winding_is_not_an_error(self):
        ring = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        assert scoring.ring_reconstruction([ring], [list(reversed(ring))]).value == 1.0

    def test_a_smoothed_ring_is_not_a_reproduced_ring(self):
        ring = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        smoothed = [[0.01, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        assert scoring.ring_reconstruction([ring], [smoothed]).value == 0.0

    def test_hole_count_carries_the_pairing_that_decided_it(self):
        score = scoring.hole_count_error(2, 3)
        assert score.value == 1.0
        assert score.detail["background_connectivity"] == bench.BACKGROUND_CONNECTIVITY
        assert "Reverse the pairing" in score.detail["note"]

    def test_fragment_scores_keep_precision_and_recall_apart(self):
        truth = [{"mask_rle": HALF}]
        split = [{"mask_rle": HALF}, {"mask_rle": OTHER_HALF}]
        score = scoring.fragment_precision_recall(truth, split)
        assert score.detail["recall"] == 1.0          # found it
        assert score.detail["precision"] == 0.5       # and invented another

    def test_membership_is_scored_pairwise_so_group_names_do_not_matter(self):
        score = scoring.fragment_membership_agreement([["a", "b"], ["c"]], [["x"], ["y"]])
        assert not score.scored                       # different members entirely
        renamed = scoring.fragment_membership_agreement([["a", "b"], ["c"]], [["c"], ["a", "b"]])
        assert renamed.value == 1.0

    def test_evidence_completeness_zeroes_on_an_unregistered_ground_kind(self):
        good = scoring.evidence_completeness(
            {"grounds": [{"kind": "shape_continuity", "detail": "x", "strength": 0.8}]})
        bad = scoring.evidence_completeness(
            {"grounds": [{"kind": "it_felt_right", "detail": "x", "strength": 0.8}]})
        assert good.value > 0.5
        assert bad.value == 0.0
        assert bad.detail["unknown_kinds"] == ["it_felt_right"]

    def test_no_grounds_scores_zero_and_says_the_contract_permits_it(self):
        score = scoring.evidence_completeness({"grounds": []})
        assert score.value == 0.0
        assert "contract permits that" in score.detail["note"]

    def test_verdict_agreement_does_not_take_a_majority_vote(self):
        score = scoring.verdict_agreement(["wrong", "wrong", "unclear"], "wrong")
        assert score.value == pytest.approx(2 / 3)
        assert score.detail["unanimous"] is False
        assert score.detail["distinct_verdicts"] == ["unclear", "wrong"]

    def test_hierarchy_is_scored_over_ancestry_not_parent_links(self):
        truth = [{"node_id": "a", "parent_node_id": None},
                 {"node_id": "c", "parent_node_id": "a"}]
        # an inserted intermediate node keeps the containment entirely right
        with_middle = [{"node_id": "a", "parent_node_id": None},
                       {"node_id": "b", "parent_node_id": "a"},
                       {"node_id": "c", "parent_node_id": "b"}]
        score = scoring.hierarchy_consistency(truth, with_middle)
        assert score.value > 0.3          # a→c survives; a→b is an addition, not a break
        assert ("a", "c") not in score.detail  # detail carries counts, not the pairs themselves

    def test_a_containment_cycle_refuses_rather_than_scoring_badly(self):
        cyclic = [{"node_id": "a", "parent_node_id": "b"},
                  {"node_id": "b", "parent_node_id": "a"}]
        score = scoring.hierarchy_consistency([{"node_id": "a", "parent_node_id": None}], cyclic)
        assert not score.scored
        assert "it is not a tree" in score.refused

    def test_density_count_and_place_fail_separately(self):
        points = [[0.1, 0.1], [0.9, 0.9]]
        right_count_wrong_place = [[0.5, 0.5], [0.5, 0.5]]
        assert scoring.density_count_error(2, 2).value == 0.0
        assert scoring.density_localisation_error(points, right_count_wrong_place).value > 0.3

    def test_localisation_is_symmetric_so_one_central_point_does_not_win(self):
        points = [[0.1, 0.1], [0.9, 0.9]]
        one_central = [[0.5, 0.5]]
        score = scoring.density_localisation_error(points, one_central)
        assert score.detail["truth_to_predicted"] > 0
        assert score.detail["predicted_to_truth"] > 0

    def test_transition_sensitivity_counts_the_false_alarms(self):
        perturbations = [{"id": "bridge", "changes": True},
                         {"id": "grow-away", "changes": False}]
        score = scoring.transition_sensitivity(perturbations, ["bridge", "grow-away"])
        assert score.value == 1.0                       # caught the real one
        assert score.detail["false_alarms"] == ["grow-away"]
        assert score.detail["false_alarm_rate"] == 1.0  # and imagined the other


# ══ 7. the controls' truth is checked against Lane B's substrate ════════════

class TestConstructedTruthAgreesWithTheSubstrate:
    """The check that makes the constructed truth worth having.

    Each count below was decided by placing pixels. `extent_forms` then counts the same mask
    independently. Deriving the truth FROM the substrate would have made this vacuous; asserting
    the two agree means a future change to either is caught by the other.
    """

    @staticmethod
    def _pieces(control_name: str):
        control = CONTROLS["controls"][control_name]
        rle = next(iter(control["instances"].values()))
        return control, foreground_components(raster_of(rle, what=control_name))

    @pytest.mark.parametrize("name,expected", [
        ("solid-mask", 1), ("donut", 1), ("nested-holes", 2), ("disconnected-fragments", 5),
    ])
    def test_the_substrate_finds_the_fragments_that_were_drawn(self, name, expected):
        control, pieces = self._pieces(name)
        assert control["truth"]["fragments"] == expected
        assert len(pieces) == expected

    @pytest.mark.parametrize("name", ["solid-mask", "donut", "nested-holes",
                                      "disconnected-fragments"])
    def test_the_substrate_finds_the_enclosed_voids_that_were_punched(self, name):
        control, pieces = self._pieces(name)
        enclosed = sum(1 for piece in pieces for void in voids_of(piece, trace(piece))
                       if void.enclosed)
        assert enclosed == control["truth"]["holes"]

    @pytest.mark.parametrize("name", ["solid-mask", "donut", "nested-holes",
                                      "disconnected-fragments"])
    def test_the_complement_count_is_recorded_beside_the_hole_count(self, name):
        # A hole count with no convention beside it is not comparable with anything: the substrate
        # counts the unbounded exterior as a complement component and this benchmark does not
        # count it as a hole. Both numbers travel so neither reading is a guess.
        control, pieces = self._pieces(name)
        per_piece = [len(voids_of(piece, trace(piece))) for piece in pieces]
        assert per_piece == control["truth"]["complement_components"]
        assert "enclosed voids only" in control["truth"]["holes_counted_as"]

    def test_the_corner_touching_pair_is_two_pieces_under_the_declared_pairing(self):
        # THE PAIRING CONTROL. A producer that reports four fragments here has assumed
        # 8-connected foreground and will disagree with every count in this benchmark.
        control, pieces = self._pieces("disconnected-fragments")
        assert control["truth"]["foreground_connectivity"] == 4
        assert control["truth"]["background_connectivity"] == 8
        assert len(pieces) == 5

    def test_the_solid_mask_has_one_outer_ring_and_no_inner_one(self):
        _, pieces = self._pieces("solid-mask")
        rings = trace(pieces[0])
        assert sum(1 for r in rings if r.is_outer) == 1
        assert sum(1 for r in rings if not r.is_outer) == 0

    def test_the_donut_has_one_inner_ring(self):
        control, pieces = self._pieces("donut")
        rings = trace(pieces[0])
        assert sum(1 for r in rings if not r.is_outer) == control["truth"]["rings"]["inner"] == 1


# ══ 8. the controls themselves ══════════════════════════════════════════════

class TestTheControls:
    def test_twelve_controls_cover_every_registered_form(self):
        covered = {form for c in bench.CONTROLS for form in c.forms}
        assert len(bench.CONTROLS) == 12
        assert set(bench.FORM_KEYS) - covered == set()

    def test_every_control_names_the_trap_it_exists_to_catch(self):
        for control in bench.CONTROLS:
            assert len(control.the_trap) > 20, f"{control.name} does not say what it catches"
            assert len(control.what) > 10

    def test_the_committed_manifest_matches_what_the_script_draws(self):
        # Drift gate, run as a test: an edit that changes a control fails the suite, not a review.
        assert bench.cmd_controls(_args(check=True)) == 0

    def test_drawing_twice_gives_the_same_bytes(self):
        assert json.dumps(bench.build_controls(), sort_keys=True) == \
               json.dumps(bench.build_controls(), sort_keys=True)

    def test_the_partition_control_has_a_part_nothing_settles(self):
        # A partition with only two parts cannot catch a producer that has nowhere to put what the
        # picture does not decide.
        truth = CONTROLS["controls"]["partition"]["truth"]
        assert set(truth["parts"]) == {"visible", "inferred", "unknown"}
        assert truth["parts"]["unknown"]["area_fraction"] > 0

    def test_the_competing_extents_control_has_no_truth_mask(self):
        truth = CONTROLS["controls"]["competing-extents"]["truth"]
        assert truth["has_single_correct_answer"] is False
        assert "mask" not in truth
        assert len(truth["legitimate_readings"]) == 2

    def test_the_transition_control_carries_a_null_perturbation(self):
        perturbations = CONTROLS["controls"]["one-pixel-transition"]["truth"]["perturbations"]
        real = [p for p in perturbations if p["changes"]]
        null = [p for p in perturbations if not p["changes"]]
        assert real and null
        # the null moves MORE pixels than the real one-pixel change, so a producer cannot pass by
        # thresholding on how much moved
        assert max(p["pixels_changed"] for p in null) > min(p["pixels_changed"] for p in real)

    def test_the_previews_are_text_so_a_change_shows_up_in_a_diff(self):
        for name, control in CONTROLS["controls"].items():
            assert control["preview"], f"{name} has no preview"
            assert all(isinstance(row, str) for row in control["preview"])

    def test_the_soft_field_control_is_coverage_and_says_so(self):
        truth = CONTROLS["controls"]["soft-fringe"]["truth"]
        assert truth["soft_cells"] > 0 and truth["binary_cells"] > 0
        assert "not confidence" in truth["note"]


# ══ 9. the atlas ════════════════════════════════════════════════════════════

class TestTheAtlas:
    def test_it_validates(self):
        assert bench.validate_atlas(ATLAS) == []

    def test_six_primary_works_and_four_adversarial_controls(self):
        roles = [e["role"] for e in ATLAS["entries"]]
        assert roles.count("primary") == 6
        assert roles.count("adversarial") == 4

    def test_no_entry_commits_image_bytes(self):
        for entry in ATLAS["entries"]:
            assert not entry.get("bytes_committed")
            assert entry["access"]["how"] in {"reference_only", "manifest_pointer", "in_repository"}

    def test_every_entry_records_attribution_and_a_retrieval_date(self):
        for entry in ATLAS["entries"]:
            rights = entry["rights"]
            assert rights["attribution"]
            assert rights["retrieved"] == "2026-08-22"

    def test_an_encumbered_entry_says_why_bytes_may_not_be_committed(self):
        for entry in ATLAS["entries"]:
            if entry["rights"]["may_commit_bytes"] is False:
                assert entry["rights"]["why_not"]

    def test_the_two_in_copyright_works_are_marked_and_dated(self):
        in_copyright = {e["slot"]: e for e in ATLAS["entries"]
                        if e["rights"]["artwork_status"] == "in_copyright"}
        assert set(in_copyright) == {"de-chirico-piazza", "gris-cubist-interior"}
        for entry in in_copyright.values():
            assert entry["rights"]["may_commit_bytes"] is False
            assert entry["rights"]["rights_holder"]
            assert "20" in entry["rights"]["artwork_expires"]

    def test_a_public_domain_work_with_an_unfree_reproduction_is_recorded_as_both(self):
        # The distinction the corpus turns on: the PAINTING is out of copyright and the
        # PHOTOGRAPH of it is not, and a manifest that recorded only the first would be wrong in
        # the way that gets a repository a letter.
        entry = next(e for e in ATLAS["entries"] if e["slot"] == "van-steenwyck-courtyard")
        assert entry["rights"]["artwork_status"] == "public_domain_by_age"
        assert entry["rights"]["reproduction_status"] == "not_freely_licensed"
        assert entry["rights"]["may_commit_bytes"] is False

    def test_the_wells_photograph_names_the_photographer_not_the_architect(self):
        entry = next(e for e in ATLAS["entries"] if e["slot"] == "wells-nave")
        assert entry["identity"]["artist"] == "David Iliff (photographer)"
        assert "CC BY-SA 3.0" in entry["rights"]["licence"]
        assert "SHARE-ALIKE IS A REAL OBLIGATION" in " ".join(entry["rights"]["licence_notes"])

    def test_unresolved_identities_say_what_was_found_instead(self):
        for entry in ATLAS["entries"]:
            if not entry["identity"]["resolved"]:
                assert entry["identity"]["identity_notes"]
                assert len(" ".join(entry["identity"]["identity_notes"])) > 100

    def test_the_adversarial_controls_reference_lane_c_by_digest(self):
        lane_c = json.loads(bench.MODEL_TRIAL_CONTROLS.read_text(encoding="utf-8"))["controls"]
        referenced = [e for e in ATLAS["entries"] if e["access"]["how"] == "in_repository"]
        assert len(referenced) == 4
        for entry in referenced:
            name = entry["access"]["source_url"].rsplit("/", 1)[-1].removesuffix(".png")
            assert entry["access"]["digest"] == lane_c[name]["digest"]
            assert (bench.REPO_ROOT / entry["access"]["source_url"]).exists()

    def test_the_four_required_adversarial_cases_are_all_present(self):
        slots = {e["slot"] for e in ATLAS["entries"] if e["role"] == "adversarial"}
        assert slots == {"adversarial-fog", "adversarial-fence-tree",
                         "adversarial-person-behind-table", "adversarial-crowd-plaza"}


# ══ 10. the matrix ══════════════════════════════════════════════════════════

class TestTheMatrix:
    def test_it_validates_and_has_not_drifted(self):
        assert bench.validate_matrix(MATRIX) == []
        assert bench.cmd_matrix(_args(check=True)) == 0

    def test_one_row_per_registered_form(self):
        assert len(MATRIX["rows"]) == len(bench.FORM_KEYS) == 19
        assert {r["form"] for r in MATRIX["rows"]} == set(bench.FORM_KEYS)

    def test_every_row_carries_all_seven_columns_the_build_asks_for(self):
        for row in MATRIX["rows"]:
            for column in ("image", "control", "question", "action", "metrics",
                           "failures", "screenshot"):
                assert row.get(column), f"{row['form']} has no {column}"

    def test_every_question_is_a_question_a_person_would_ask(self):
        for row in MATRIX["rows"]:
            assert row["question"].endswith("?"), row["form"]

    def test_every_image_and_control_resolves(self):
        slots = {e["slot"] for e in ATLAS["entries"]}
        names = {c.name for c in bench.CONTROLS}
        for row in MATRIX["rows"]:
            assert row["image"] in slots
            assert row["control"] in names

    def test_every_metric_is_implemented(self):
        for row in MATRIX["rows"]:
            for metric in row["metrics"]:
                assert metric in scoring.ALL_METRICS
                assert hasattr(scoring, "aggregate")

    def test_the_report_names_where_the_matrix_and_the_registry_disagree(self):
        # These gaps are the deliverable, not a defect: ten metrics this benchmark needs are not
        # in the contract's `comparison_methods`, and each one is a candidate Lane A ticket.
        gaps = bench.metric_gaps(MATRIX)
        using_extensions = [g for g in gaps if g["uses_extensions"]]
        assert using_extensions, "no row reaches for an extension, so the gap report is untested"
        for gap in gaps:
            for metric in gap["uses_extensions"]:
                assert metric in scoring.EXTENSIONS


# ══ 11. the annotations ═════════════════════════════════════════════════════

class TestTheAnnotations:
    def test_they_validate(self):
        assert bench.validate_annotations() == []

    def test_the_schema_has_no_ground_truth_field(self):
        # The absence IS the design. A single correct-answer slot forces the annotator to choose
        # and forces the scorer to mark the rest wrong.
        schema = json.loads(
            (bench.SCHEMAS_DIR / "form-annotation.schema.json").read_text(encoding="utf-8"))
        assert "ground_truth" not in schema["properties"]
        assert "correct_mask" not in schema["properties"]
        assert "legitimate_readings" in schema["required"]

    def test_the_schema_requires_a_reason_for_every_reading(self):
        schema = json.loads(
            (bench.SCHEMAS_DIR / "form-annotation.schema.json").read_text(encoding="utf-8"))
        reading = schema["properties"]["legitimate_readings"]["items"]
        assert "why" in reading["required"]
        assert reading["properties"]["why"]["minLength"] == 1

    def test_two_annotators_disagree_and_the_disagreement_is_recorded(self):
        naive = json.loads(
            (bench.ANNOTATIONS_DIR / "competing-extents.naive.json").read_text(encoding="utf-8"))
        assert naive["disagrees_with"] == ["ann-competing-extents-trained-01"]
        assert naive["annotator"]["expertise"] == "naive"

    def test_the_two_annotators_prefer_different_readings_of_one_picture(self):
        def preferred(name):
            record = json.loads((bench.ANNOTATIONS_DIR / name).read_text(encoding="utf-8"))
            return next(r["reading_id"] for r in record["legitimate_readings"]
                        if r.get("preferred_by_annotator"))
        assert preferred("competing-extents.trained.json") == "body_only"
        assert preferred("competing-extents.naive.json") == "body_and_shadow"

    def test_a_preference_is_never_read_as_truth_by_the_scorer(self):
        record = json.loads(
            (bench.ANNOTATIONS_DIR / "competing-extents.trained.json").read_text(encoding="utf-8"))
        score = scoring.hypothesis_coverage(
            record["legitimate_readings"],
            [{"alternative_id": "x", "mask_rle": record["legitimate_readings"][1]["mask_rle"]}])
        # the producer returned the reading this annotator did NOT prefer, and still scores
        assert score.value == 0.5
        assert score.detail["missed"] == ["body_only"]

    def test_every_verdict_is_from_the_contract_s_closed_set(self):
        allowed = set(bench.CONTRACT["closed_sets"]["review_verdicts"])
        for path in sorted(bench.ANNOTATIONS_DIR.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            for verdict in record.get("utility_verdicts") or []:
                assert verdict["verdict"] in allowed
                assert verdict["why"], "a bare verdict is a feeling"

    def test_a_rejected_ground_is_recorded_rather_than_omitted(self):
        record = json.loads(
            (bench.ANNOTATIONS_DIR / "false-similarity.membership.json").read_text(encoding="utf-8"))
        grounds = record["fragment_membership"][0]["grounds"]
        rejected = [g for g in grounds if g["strength"] == 0.0]
        assert rejected, "the appearance ground was considered and rejected; that is evidence"
        assert "evidence AGAINST" in rejected[0]["detail"]


# ══ 12. the CLI ═════════════════════════════════════════════════════════════

class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _args(**kwargs):
    kwargs.setdefault("check", False)
    return _Args(**kwargs)


class TestTheCli:
    def test_verify_runs_every_check_and_returns_one_status(self, capsys):
        assert bench.cmd_verify(_args()) == 0
        out = capsys.readouterr().out
        for section in ("controls:", "matrix:", "atlas:", "annotations:"):
            assert section in out

    def test_report_lists_the_extensions_and_why_each_exists(self, capsys):
        assert bench.cmd_report(_args()) == 0
        out = capsys.readouterr().out
        assert "forms with a control: 19 of 19" in out
        for name in scoring.EXTENSIONS:
            assert name in out

    @staticmethod
    def _imported_roots(name: str) -> set:
        """The top-level modules a script actually imports, by AST rather than by substring.

        Read this way because the docstrings talk ABOUT torch and numpy — explaining why the lane
        does not use them — and a substring check fails on the file's own explanation.
        """
        import ast
        tree = ast.parse((bench.REPO_ROOT / "scripts" / name).read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
        return roots

    @pytest.mark.parametrize("name", ["perception_lab_form_benchmark.py",
                                      "perception_lab_form_scoring.py"])
    def test_the_scripts_wire_nothing(self, name):
        # No route, no database, no network. A research lane that reached into production would be
        # the one thing this brief forbids outright.
        roots = self._imported_roots(name)
        for forbidden in ("fastapi", "motor", "pymongo", "requests", "urllib", "httpx", "socket"):
            assert forbidden not in roots, f"{name} imports {forbidden}"

    @pytest.mark.parametrize("name", ["perception_lab_form_benchmark.py",
                                      "perception_lab_form_scoring.py"])
    def test_neither_module_needs_the_ml_stack(self, name):
        # `numpy` and `pillow` are in requirements-ml.txt, which CI does not install. A benchmark
        # that only runs where torch is present is a benchmark nobody runs on a pull request.
        roots = self._imported_roots(name)
        for heavy in ("numpy", "PIL", "torch", "scipy", "cv2"):
            assert heavy not in roots, f"{name} imports {heavy}"
