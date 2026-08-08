"""HARNESS-001C2 — the pre-registered phrase matrix.

These tests exist to make "pre-registered" checkable rather than asserted. An open-vocabulary
organ can be made to look capable by trying phrases until one lands; the resulting number reads
as a hit-rate and is the outcome of a search. Nothing in a trace tells the two apart afterwards,
so the discipline has to live in a frozen list and a digest over it — and a digest nobody tests
is a digest that silently stops matching.

No model, no GPU, no network anywhere in this file.
"""
from __future__ import annotations

import copy
import json
import os
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import single_actuator_lab as lab                                    # noqa: E402
from single_actuator_lab_support import contract, matrix             # noqa: E402

SUITE_ID = "sam3-fold-phrase-matrix"

#: The pre-registration, pinned. If a phrase is ever added, removed or re-spelled, this test is
#: the thing that has to be edited deliberately — which is exactly the friction that stops a
#: synonym being slipped in after an empty result.
PRE_REGISTERED = {
    "availability_control": ["face"],
    "object_scope": ["robe", "garment", "drapery"],
    "fold_target": ["robe folds", "drapery folds", "folded drapery", "fabric folds", "creases"],
    "replication_control": ["drapery fold"],
    "adversarial_abstraction": ["sensuality"],
    "negative_control": ["bicycle"],
}


@pytest.fixture
def suite():
    return matrix.check_suite(matrix.load_suite(SUITE_ID), source=SUITE_ID)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 1. The committed suite
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_the_committed_suite_validates(suite):
    assert matrix.validate_suite(suite) == []
    assert suite["actuator_lock"] == "concept_segment"
    assert suite["call_budget"] == 1


def test_the_phrase_matrix_is_exactly_what_was_pre_registered(suite):
    got = {f["family"]: list(f["phrases"]) for f in suite["phrase_families"]}
    assert got == PRE_REGISTERED
    assert len(matrix.all_phrases(suite)) == 12


def test_the_declared_locks_match_the_suite_content(suite):
    ok, computed = matrix.locks_match_declaration(suite)
    assert ok, (f"suite lock is stale: declared {suite['lock']}, computed {computed}. "
                f"Run `matrix --plan --freeze` BEFORE collection begins.")


def test_the_lock_moves_when_anything_about_the_phrases_moves(suite):
    """Each of these is a real way a frozen list could be quietly altered."""
    base = matrix.phrase_digest(suite)

    added = copy.deepcopy(suite)
    added["phrase_families"][2]["phrases"].append("cloth folds")
    assert matrix.phrase_digest(added) != base, "adding a synonym did not move the lock"

    respelled = copy.deepcopy(suite)
    respelled["phrase_families"][2]["phrases"][0] = "robe fold"
    assert matrix.phrase_digest(respelled) != base, "re-spelling did not move the lock"

    removed = copy.deepcopy(suite)
    removed["phrase_families"][2]["phrases"].pop()
    assert matrix.phrase_digest(removed) != base, "dropping a phrase did not move the lock"

    # The subtle one: same phrases, different meaning. Moving `bicycle` out of
    # `negative_control` would leave the phrase SET identical while inverting what a hit means.
    remeaning = copy.deepcopy(suite)
    for family in remeaning["phrase_families"]:
        if family["role"] == "negative_control":
            family["role"] = "fold_target"
    assert matrix.phrase_digest(remeaning) != base, "re-roling a phrase did not move the lock"


def test_the_lock_moves_when_a_fixture_is_swapped_under_a_stable_id(suite):
    base = matrix.fixture_digest(suite)
    swapped = copy.deepcopy(suite)
    swapped["fixtures"][0]["sha256"] = "0" * 64
    assert matrix.fixture_digest(swapped) != base


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 2. The fixture census — the claims must match the files
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_every_fixture_exists_and_hashes_to_what_the_suite_claims(suite):
    from PIL import Image
    assert len(suite["fixtures"]) >= 4, "the card asks for the Pietà plus at least three"
    for fixture in suite["fixtures"]:
        path = os.path.join(contract.REPO_ROOT, fixture["path"])
        assert os.path.exists(path), fixture["fixture_id"]
        assert contract.sha256_file(path) == fixture["sha256"], fixture["fixture_id"]
        with Image.open(path) as im:
            assert (im.width, im.height) == (fixture["width"], fixture["height"]), \
                fixture["fixture_id"]
        assert os.path.getsize(path) == fixture["bytes"], fixture["fixture_id"]


def test_every_provenance_claim_cites_a_file_that_exists(suite):
    """A provenance field naming a document nobody can open is decoration.

    This is the check that keeps the census honest about where its statements came from — the
    subject descriptions are quoted from the rehearsal program's own source-notes, not from my
    recognising the sculptures.
    """
    for fixture in suite["fixtures"]:
        source = fixture["provenance"]["source"]
        assert os.path.exists(os.path.join(contract.REPO_ROOT, source)), \
            f"{fixture['fixture_id']}: provenance cites {source}, which does not exist"


def test_tradition_is_claimed_only_where_the_repository_documents_it(suite):
    """The card allows a two-tradition claim only if existing metadata honestly supports it.

    It does not: the 003 notes record no iconographic identification attempted, and the 002
    collage's culture labels are the plate's own captions. So every `documented_tradition` is
    null here, and what is merely visible lives in `observed`. This test pins that, because
    filling the field in later from recognition rather than a source is the exact way a census
    acquires sourced-looking metadata that was never sourced.
    """
    for fixture in suite["fixtures"]:
        prov = fixture["provenance"]
        if prov["documented_tradition"] is not None:
            assert prov["source"], f"{fixture['fixture_id']} claims a tradition with no source"
        assert "observed" in prov


def test_the_control_condition_fixture_is_declared_before_any_result(suite):
    """The Angel of Grief is in the matrix as the untreated counterpart to the Pietà's
    documented grain/texture layer. Declared as `control_condition` in the pre-registration, so
    it cannot later be described as one after the numbers make that convenient."""
    by_id = {f["fixture_id"]: f for f in suite["fixtures"]}
    assert by_id["angel_of_grief"]["role"] == "control_condition"
    assert by_id["pieta"]["role"] == "primary"
    assert by_id["pieta"]["provenance"]["known_confounds"], \
        "the Pietà's documented texture layer is not recorded as a confound"
    assert not by_id["angel_of_grief"]["provenance"]["known_confounds"]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 3. What check_suite refuses
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_a_suite_with_no_availability_control_is_refused(suite):
    broken = copy.deepcopy(suite)
    broken["phrase_families"] = [f for f in broken["phrase_families"]
                                 if f["role"] != matrix.AVAILABILITY]
    with pytest.raises(matrix.SuiteError, match="availability_control"):
        matrix.check_suite(broken)


def test_a_phrase_in_two_families_is_refused(suite):
    broken = copy.deepcopy(suite)
    broken["phrase_families"][1]["phrases"].append("face")
    with pytest.raises(matrix.SuiteError, match="counted twice"):
        matrix.check_suite(broken)


def test_a_fixture_whose_content_moved_is_refused(suite):
    broken = copy.deepcopy(suite)
    broken["fixtures"][0]["sha256"] = "0" * 64
    with pytest.raises(matrix.SuiteError, match="content hash moved"):
        matrix.check_suite(broken)


def test_an_added_family_without_justification_is_refused(suite):
    broken = copy.deepcopy(suite)
    for family in broken["phrase_families"]:
        if family["role"] == "replication_control":
            family.pop("justification", None)
    with pytest.raises(matrix.SuiteError, match="no justification"):
        matrix.check_suite(broken)


def test_the_equivalence_arm_cannot_name_an_unfrozen_phrase(suite):
    broken = copy.deepcopy(suite)
    broken["arms"]["wrapper_equivalence"]["phrases"] = ["cloth folds"]
    with pytest.raises(matrix.SuiteError, match="never froze"):
        matrix.check_suite(broken)


def test_an_unknown_actuator_lock_is_refused(suite):
    broken = copy.deepcopy(suite)
    broken["actuator_lock"] = "segment_the_vibes"
    with pytest.raises(matrix.SuiteError, match="capability table"):
        matrix.check_suite(broken)


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 4. The plan
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_the_plan_enumerates_every_cell_before_anything_runs(suite):
    planned = matrix.plan(suite)
    fixtures = len(suite["fixtures"])
    phrases = len(matrix.all_phrases(suite))
    equivalence = len(suite["arms"]["wrapper_equivalence"]["phrases"])
    assert planned["capture_count"] == fixtures * phrases + fixtures * equivalence == 56
    # One SAM invocation per capture, and a budget of one PER capture — a matrix of 56 cells is
    # 56 budgets of one, never one budget of 56.
    assert planned["sam_invocations_planned"] == planned["capture_count"]
    assert planned["call_budget"] == 1
    assert len({c["run_id"] for c in planned["cells"]}) == planned["capture_count"]


def test_the_wrapper_equivalence_arm_covers_every_fixture(suite):
    """C1 tested wrapper equivalence on one image, and its fold actuator run was EMPTY — an
    equivalence test on an empty result establishes nothing. This arm runs on every fixture."""
    cells = [c for c in matrix.plan_cells(suite) if c["arm"] == "wrapper_equivalence"]
    assert {c["fixture_id"] for c in cells} == {f["fixture_id"] for f in suite["fixtures"]}
    assert all(c["mode"] == "actuator_direct" for c in cells)


def test_planner_samples_are_declared_planning_only_and_grant_no_sam_attempts(suite):
    sampling = suite["planner_sampling"]
    assert sampling["planning_only"] is True
    assert sampling["samples"] >= 5, "one repeat that agreed is not stability"
    assert matrix.plan(suite)["planner_grants_sam_attempts"] is False


def test_the_expected_invariants_are_the_harness_ones(suite):
    inv = suite["expected_invariants"]
    assert inv["invocations_per_capture"] == 1
    assert inv["lock_held"] is True
    assert inv["database_writes"] == 0
    assert inv["source_mutations"] == 0
    assert inv["replay_live_calls"] == 0


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 5. The freeze, once collection has begun
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_locks_pass_before_collection_and_fail_after_an_edit(tmp_path, suite):
    runs = str(tmp_path / "runs")
    # Before collection: nothing has been frozen, so there is nothing to violate.
    assert matrix.assert_locks_unchanged(suite, runs_root=runs) is None

    marker = matrix.begin_collection(suite, runs_root=runs, captured_at="t0")
    assert marker["locks"] == matrix.compute_locks(suite)
    assert matrix.collection_started(suite["suite_id"], runs_root=runs)
    # Unchanged suite still passes.
    assert matrix.assert_locks_unchanged(suite, runs_root=runs) is not None

    edited = copy.deepcopy(suite)
    edited["phrase_families"][2]["phrases"].append("cloth folds")
    edited["lock"] = matrix.compute_locks(edited)      # even re-freezing the declaration
    with pytest.raises(matrix.LockViolation, match="changed after collection began"):
        matrix.assert_locks_unchanged(edited, runs_root=runs)


def test_a_swapped_fixture_after_collection_is_refused(tmp_path, suite):
    runs = str(tmp_path / "runs")
    matrix.begin_collection(suite, runs_root=runs, captured_at="t0")
    swapped = copy.deepcopy(suite)
    swapped["fixtures"][0]["sha256"] = "0" * 64
    swapped["lock"] = matrix.compute_locks(swapped)
    with pytest.raises(matrix.LockViolation, match="fixture set changed"):
        matrix.assert_locks_unchanged(swapped, runs_root=runs)


def test_a_stale_declared_lock_is_refused_even_before_collection(suite):
    stale = copy.deepcopy(suite)
    stale["lock"] = {"phrases_sha256": "0" * 64, "fixtures_sha256": "0" * 64}
    with pytest.raises(matrix.LockViolation, match="do not match its content"):
        matrix.assert_locks_unchanged(stale, runs_root="/nonexistent")


def test_begin_collection_is_written_before_the_first_capture_and_is_idempotent(tmp_path, suite):
    """A run that dies halfway must still leave the evidence that collection had begun —
    otherwise a crashed first attempt looks exactly like a matrix that never started, and the
    phrases become editable again."""
    runs = str(tmp_path / "runs")
    first = matrix.begin_collection(suite, runs_root=runs, captured_at="t0")
    second = matrix.begin_collection(suite, runs_root=runs, captured_at="t1")
    assert first == second
    assert second["collection_started_at"] == "t0"


def test_the_cli_refuses_to_refreeze_after_collection_begins(tmp_path, suite, monkeypatch):
    runs = str(tmp_path / "runs")
    monkeypatch.setattr(contract, "RUNS_ROOT", runs)
    monkeypatch.setattr(matrix.contract, "RUNS_ROOT", runs)
    matrix.begin_collection(suite, runs_root=runs, captured_at="t0")
    with pytest.raises(SystemExit, match="collection has already begun"):
        lab.matrix_plan(SUITE_ID, write=True)


def test_plan_runs_nothing(suite, monkeypatch):
    """`--plan` is the verb you use before you are ready to spend anything."""
    import backend.services.sam3_concept_service as sam

    def _boom(*a, **k):
        raise AssertionError("plan called the organ")

    monkeypatch.setattr(sam, "segment_concept", _boom)
    monkeypatch.setattr(sam, "load", _boom)
    planned = lab.matrix_plan(SUITE_ID)
    assert planned["capture_count"] == 56
