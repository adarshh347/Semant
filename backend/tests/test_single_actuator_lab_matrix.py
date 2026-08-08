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
# This directory too, so the C1 fakes can be reused rather than copied. Two FakeSams that drifted
# apart would let the matrix tests pass against a stub the lab tests no longer describe.
TESTS = os.path.dirname(os.path.abspath(__file__))
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)

import single_actuator_lab as lab                                    # noqa: E402
from single_actuator_lab_support import contract, matrix             # noqa: E402
from test_single_actuator_lab import FakePlanner, FakeSam, _mask     # noqa: E402

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


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Belt and braces: no test in this file may reach a planner API.

    Passing a fake client is the per-test discipline, and discipline is what gets forgotten. This
    empties the key so a test that omits one records `planner_unavailable` instead of quietly
    calling out — which is how five real API calls per test hid behind a suite that merely looked
    slow (3% CPU, two minutes of wall clock, and nothing in the output saying why).
    """
    from backend.config import settings
    monkeypatch.setattr(settings, "GROQ_API_KEY", "", raising=False)


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


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 6. The runner — on fakes, no model anywhere
# ══════════════════════════════════════════════════════════════════════════════════════════════

#: Every runner test passes this. `run_live` with `planner_client=None` resolves a REAL Groq
#: client from settings, and a developer `.env` with a live key would make the focused suite
#: call the network five times per test — found by a profile showing 3% CPU and two minutes of
#: wall clock. A test that reaches the internet is not a fast test and is not a hermetic one.
_NO_NETWORK = FakePlanner({"steps": [{"actuator": "concept_segment",
                                      "params": {"phrase": "folded drapery"}}]})


@pytest.fixture
def tiny_suite(tmp_path, suite):
    """A two-fixture, four-phrase suite over real checked-in images, so the runner is exercised
    end to end without 56 captures. The fixtures and their hashes are real; only the size of the
    matrix is reduced."""
    small = copy.deepcopy(suite)
    small["suite_id"] = "tiny-suite"
    small["fixtures"] = small["fixtures"][:2]
    small["phrase_families"] = [
        {"family": "availability_control", "role": "availability_control", "phrases": ["face"]},
        {"family": "fold_target", "role": "fold_target", "phrases": ["robe folds", "creases"]},
        {"family": "negative_control", "role": "negative_control", "phrases": ["bicycle"]},
    ]
    small["arms"]["wrapper_equivalence"]["phrases"] = ["face"]
    small["lock"] = matrix.compute_locks(small)
    path = tmp_path / "tiny-suite.yaml"
    import yaml
    path.write_text(yaml.safe_dump(small))
    return small, str(tmp_path)


@pytest.fixture
def sam(monkeypatch):
    def _install(fake):
        import backend.services.sam3_concept_service as real
        for name in ("weights_path", "is_available", "device", "load", "unload",
                     "segment_concept"):
            monkeypatch.setattr(real, name, getattr(fake, name))
        from single_actuator_lab_support import arms as arms_mod
        monkeypatch.setattr(arms_mod, "_svc", lambda: real)
        original = contract.environment_receipt
        monkeypatch.setattr(contract, "environment_receipt",
                            lambda m: {**original(m), "runtime_available": True,
                                       "weights_present": True, "device": "cpu"})
        return real
    return _install


def test_the_runner_captures_every_cell_with_its_own_budget_of_one(tmp_path, tiny_suite, sam):
    small, suites_dir = tiny_suite
    sam(FakeSam([{"index": 0, "mask_rle": _mask(680, 544, 10, 60, 10, 60), "confidence": 0.8}]))
    runs = str(tmp_path / "runs")

    out = matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")
    cells = out["cells"]
    assert len(cells) == 2 * 4 + 2 * 1 == 10
    assert all(c["status"] == "captured" for c in cells)

    for cell in cells:
        trace = contract.read_json(os.path.join(cell["run_path"], "trace.json"))
        assert len(trace["invocations"]) == 1
        assert trace["invocations"][0]["call_budget"] == 1
        assert trace["invariance"]["lock_held"] is True
        assert trace["invariance"]["database_writes_attempted"] == []
        assert trace["invariance"]["image_unchanged"] is True


def test_an_empty_cell_is_never_retried(tmp_path, tiny_suite, sam):
    """The matrix's most important observation is that a frozen phrase returns nothing. A runner
    that re-issued on empty would convert that into a sampling artifact, invisibly."""
    small, _ = tiny_suite
    fake = FakeSam([])
    sam(fake)
    runs = str(tmp_path / "runs")
    out = matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")
    assert fake.calls == len(out["cells"]) == 10, "a cell was called more than once"
    assert all(c["organ_status"] == "empty" for c in out["cells"])


def test_a_second_live_run_skips_frozen_cells_rather_than_spending_again(tmp_path, tiny_suite,
                                                                        sam):
    small, _ = tiny_suite
    fake = FakeSam([])
    sam(fake)
    runs = str(tmp_path / "runs")
    matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")
    first = fake.calls
    again = matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t1")
    assert fake.calls == first, "a resumed collection re-spent a budget on a frozen cell"
    assert all(c["status"] == "already_frozen" for c in again["cells"])


def test_the_first_capture_is_cold_and_the_rest_are_warm(tmp_path, tiny_suite, sam):
    """Measured, not declared: `warm` is read off what the loader actually reported."""
    small, _ = tiny_suite
    sam(FakeSam([]))
    runs = str(tmp_path / "runs")
    out = matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")
    warmth = []
    for cell in out["cells"]:
        trace = contract.read_json(os.path.join(cell["run_path"], "trace.json"))
        warmth.append(trace["invocations"][0]["warm"])
    assert warmth[0] is False and all(warmth[1:]), warmth


def test_the_runner_refuses_when_the_frozen_phrases_moved(tmp_path, tiny_suite, sam):
    small, _ = tiny_suite
    sam(FakeSam([]))
    runs = str(tmp_path / "runs")
    matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")

    edited = copy.deepcopy(small)
    edited["phrase_families"][1]["phrases"].append("cloth folds")
    edited["lock"] = matrix.compute_locks(edited)
    with pytest.raises(matrix.LockViolation, match="changed after collection began"):
        matrix.run_live(edited, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t1")


def test_cell_manifests_carry_the_full_manifest_contract(tiny_suite):
    """A matrix cell is not a lighter kind of run: its synthesised manifest validates against the
    same schema and goes through the same firewall as a hand-written one."""
    small, _ = tiny_suite
    for cell in matrix.plan_cells(small):
        manifest = matrix.cell_manifest(small, cell, warm=True)
        assert contract.validate(manifest, "manifest") == [], cell["run_id"]


def test_a_fold_target_cell_is_declared_open_not_positive(tiny_suite):
    """Whether local fold geometry is findable is the QUESTION. Declaring it positive would write
    the hoped-for answer into the record meant to settle it."""
    small, _ = tiny_suite
    conditions = {c["role"]: matrix.cell_manifest(small, c, warm=True)["expected_condition"]
                  for c in matrix.plan_cells(small)}
    assert conditions["fold_target"] == "open"
    assert conditions["availability_control"] == "positive"
    assert conditions["negative_control"] == "negative"


# ── planner sampling ──────────────────────────────────────────────────────────────────────────

def test_planner_samples_spend_no_sam_attempts(tmp_path, tiny_suite, sam):
    """Structural, not promised: `sample_planner` calls authorize and never invoke."""
    small, _ = tiny_suite
    fake = FakeSam([{"index": 0, "mask_rle": _mask(680, 544, 5, 40, 5, 40), "confidence": 0.9}])
    sam(fake)
    runs = str(tmp_path / "runs")
    client = FakePlanner({"steps": [{"actuator": "concept_segment",
                                     "params": {"phrase": "folded drapery"}}]})
    out = matrix.sample_planner(small, client=client, runs_root=runs, now="t0")
    assert fake.calls == 0, "a planner sample called the organ"
    assert out["total_sam_invocations"] == 0
    assert len(out["samples"]) == small["planner_sampling"]["samples"] >= 5
    assert all(s["sam_invocations"] == 0 for s in out["samples"])
    assert client.calls == len(out["samples"]), "one call per sample, no re-prompt loop"


def test_a_planner_receipt_cannot_masquerade_as_an_organ_empty(tmp_path, tiny_suite, sam):
    """A planning-only receipt has no organ observation and says what kind of thing it is."""
    small, _ = tiny_suite
    sam(FakeSam([]))
    runs = str(tmp_path / "runs")
    out = matrix.sample_planner(small, client=FakePlanner({"steps": []}), runs_root=runs)
    for sample in out["samples"]:
        assert sample["kind"] == "planning_only"
        assert "organ_observation" not in sample
        assert "instance_count" not in sample
    assert out["planning_only"] is True


def test_planner_reach_beyond_the_lock_is_refused_and_recorded(tmp_path, tiny_suite, sam):
    small, _ = tiny_suite
    sam(FakeSam([]))
    runs = str(tmp_path / "runs")
    client = FakePlanner({"steps": [
        {"actuator": "semantic_read", "params": {"question": "compare the traditions"}},
        {"actuator": "concept_segment", "params": {"phrase": "drapery folds"}}]})
    out = matrix.sample_planner(small, client=client, runs_root=runs)
    for sample in out["samples"]:
        assert sample["refused_out_of_lock"] == ["semantic_read"]
        assert sample["selected_phrase"] == "drapery folds"
        assert sample["sam_invocations"] == 0


# ── replay ────────────────────────────────────────────────────────────────────────────────────

def test_every_matrix_cell_replays_with_zero_live_calls(tmp_path, tiny_suite, sam, monkeypatch):
    small, suites_dir = tiny_suite
    fake = FakeSam([{"index": 0, "mask_rle": _mask(680, 544, 8, 50, 8, 50), "confidence": 0.7}])
    sam(fake)
    runs = str(tmp_path / "runs")
    matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")
    spent = fake.calls

    for cell in matrix.plan_cells(small):
        run_path = contract.run_dir(cell["run_id"], runs)
        out = lab.replay(run_path)
        assert out["live_calls"] == 0
        assert out["divergences"] == []
    assert fake.calls == spent, "replay called the organ"


# ══════════════════════════════════════════════════════════════════════════════════════════════
# 7. Scoring — structure only, and the refusals that keep it that way
# ══════════════════════════════════════════════════════════════════════════════════════════════

def _collect(tmp_path, small, sam_fake, sam, phrase_results=None):
    """Run a tiny matrix whose organ answer depends on the phrase, so a response CURVE exists."""
    runs = str(tmp_path / "runs")
    real = sam(sam_fake)
    if phrase_results is not None:
        def _by_phrase(image, concept, **kw):
            sam_fake.calls += 1
            return {"concept": concept, "instances": phrase_results.get(concept, []),
                    "truncated": False, "latency_ms": 1.0, "device": "cpu",
                    "model": "facebook/sam3"}
        real.segment_concept = _by_phrase
    matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")
    return runs


def test_the_availability_gate_blocks_attribution_where_the_control_failed(tmp_path, tiny_suite,
                                                                          sam):
    """The card requires it: a failed availability control prevents phrase-failure attribution.

    Without the gate, a fixture the organ simply does not work on contributes a column of zeroes
    that reads exactly like a phrase-robustness finding.
    """
    small, _ = tiny_suite
    fixtures = [f["fixture_id"] for f in small["fixtures"]]
    mask = _mask(680, 544, 5, 40, 5, 40)
    # `face` works on the first fixture only. Nothing else works anywhere.
    hits = {"face": [{"index": 0, "mask_rle": mask, "confidence": 0.8}]}

    runs = str(tmp_path / "runs")
    real = sam(FakeSam([]))
    working = small["fixtures"][0]["sha256"]

    def _gated(image, concept, **kw):
        # Keyed on the IMAGE, not on a call counter: the organ's behaviour really does depend on
        # the picture, and a counter-based fake silently mis-assigns the moment plan order
        # changes — which it did, making a wrapper cell look like a mismatch.
        on_working_fixture = contract.sha256_bytes(bytes(image)) == working
        instances = hits.get(concept, []) if on_working_fixture else []
        return {"concept": concept, "instances": instances, "truncated": False,
                "latency_ms": 1.0, "device": "cpu", "model": "facebook/sam3"}

    real.segment_concept = _gated
    matrix.run_live(small, lab.capture, planner_client=_NO_NETWORK, runs_root=runs, now="t0")

    out = matrix.report(small, runs_root=runs)
    gate = out["availability"]
    assert gate[fixtures[0]]["demonstrated"] is True
    assert gate[fixtures[1]]["demonstrated"] is False

    by_fixture = {(c["fixture_id"], c["phrase"]): c for c in out["cells"] if c.get("collected")}
    # On the fixture where the control worked, an empty IS a phrase-conditioned empty.
    assert by_fixture[(fixtures[0], "creases")]["attribution"] == matrix.PHRASE_CONDITIONED_EMPTY
    # On the fixture where it did not, the same empty is NOT attributable to the phrase.
    ungated = by_fixture[(fixtures[1], "creases")]
    assert ungated["attribution"] == matrix.NOT_ESTABLISHED
    assert "availability control did not succeed" in ungated["attribution_detail"]
    # And the gated-out fixture is excluded from the curve rather than counted as zeroes.
    assert fixtures[1] in out["response_curve"]["gated_out"]


def test_a_failed_availability_control_is_reported_as_instrument_not_phrase(tmp_path, tiny_suite,
                                                                           sam):
    small, _ = tiny_suite
    runs = _collect(tmp_path, small, FakeSam([]), sam)
    out = matrix.report(small, runs_root=runs)
    controls = [c for c in out["cells"] if c["role"] == matrix.AVAILABILITY and c["collected"]]
    assert controls
    for control in controls:
        assert control["attribution"] == matrix.INSTRUMENT_UNAVAILABLE


def test_the_response_curve_counts_hits_and_claims_nothing_about_them(tmp_path, tiny_suite, sam):
    small, _ = tiny_suite
    mask = _mask(680, 544, 5, 60, 5, 60)
    runs = _collect(tmp_path, small, FakeSam([]), sam, phrase_results={
        "face": [{"index": 0, "mask_rle": mask, "confidence": 0.9}],
        "robe folds": [{"index": 0, "mask_rle": mask, "confidence": 0.4}],
    })
    out = matrix.report(small, runs_root=runs)
    curve = out["response_curve"]

    assert curve["by_phrase"]["face"]["hit_rate"] == 1.0
    assert curve["by_phrase"]["robe folds"]["hit_rate"] == 1.0
    assert curve["by_phrase"]["creases"]["hit_rate"] == 0.0
    assert curve["by_phrase"]["bicycle"]["hit_rate"] == 0.0
    assert curve["by_family"]["fold_target"]["cells_with_instances"] == 2

    # A perfect hit-rate is still not a correctness claim, anywhere.
    assert out["review"]["semantic_correctness"] == "not_established"
    assert out["bounded_decision"]["value"] == matrix.NOT_ESTABLISHED
    for cell in out["cells"]:
        if cell.get("collected"):
            assert cell["semantic_correctness"] == "not_established"


def test_scoring_code_can_never_write_a_review_only_attribution(tmp_path, tiny_suite, sam):
    """`instrument_class_gap` is the conclusion this lane most wants and exactly the one it may
    not reach: a pile of phrase-conditioned empties is evidence of absence only after a human
    confirms the target was there to be found."""
    small, _ = tiny_suite
    mask = _mask(680, 544, 5, 60, 5, 60)
    runs = _collect(tmp_path, small, FakeSam([]), sam, phrase_results={
        "face": [{"index": 0, "mask_rle": mask, "confidence": 0.9}]})
    out = matrix.report(small, runs_root=runs)

    # Every fold target came back empty on every fixture, with the gate open. That is the exact
    # shape that tempts an instrument-class conclusion.
    folds = [c for c in out["cells"] if c["role"] == "fold_target" and c["collected"]]
    assert folds and all(c["organ_status"] == "empty" for c in folds)
    assert all(c["attribution"] == matrix.PHRASE_CONDITIONED_EMPTY for c in folds)

    written = {c["attribution"] for c in out["cells"]}
    assert not (written & matrix.REVIEW_ONLY), f"scoring wrote a review-only attribution: {written}"
    assert out["bounded_decision"]["value"] == matrix.NOT_ESTABLISHED
    assert set(out["bounded_decision"]["may_not_be_derived_by_machine"]) == matrix.REVIEW_ONLY


def test_semantic_correctness_is_not_reachable_from_any_measured_signal(tmp_path, tiny_suite,
                                                                       sam):
    """Maximum confidence, large clean masks, perfect agreement across every fixture."""
    small, _ = tiny_suite
    big = _mask(680, 544, 2, 670, 2, 530)
    runs = _collect(tmp_path, small, FakeSam([]), sam, phrase_results={
        p: [{"index": 0, "mask_rle": big, "confidence": 1.0}]
        for p in matrix.all_phrases(small)})
    out = matrix.report(small, runs_root=runs)
    assert out["response_curve"]["by_family"]["fold_target"]["hit_rate"] == 1.0
    assert out["review"]["semantic_correctness"] == "not_established"
    assert out["review"]["cells_reviewed"] == 0
    assert out["bounded_decision"]["value"] == matrix.NOT_ESTABLISHED


def test_wrapper_equivalence_keys_on_fixture_hash_phrase_and_model(tmp_path, tiny_suite, sam):
    small, _ = tiny_suite
    mask = _mask(680, 544, 5, 60, 5, 60)
    runs = _collect(tmp_path, small, FakeSam([]), sam, phrase_results={
        "face": [{"index": 0, "mask_rle": mask, "confidence": 0.9}]})
    eq = matrix.report(small, runs_root=runs)["wrapper_equivalence"]
    assert eq["equivalent"] is True
    assert eq["mismatches"] == []
    assert eq["informative_pairs"] >= 1, "equivalence rested only on empty pairs"
    for pair in eq["pairs"]:
        assert pair["identical_masks"] is True


def test_equivalence_over_only_empty_pairs_says_it_established_nothing(tmp_path, tiny_suite,
                                                                      sam):
    """C1's fold actuator run was empty, so its equivalence claim rested on comparing two
    nothings. The report now says so rather than reporting `equivalent: true`."""
    small, _ = tiny_suite
    runs = _collect(tmp_path, small, FakeSam([]), sam)
    eq = matrix.report(small, runs_root=runs)["wrapper_equivalence"]
    assert eq["informative_pairs"] == 0
    assert "establishes nothing" in eq["established_by"]


def test_a_wrapper_that_loses_an_instance_is_caught(tiny_suite):
    """Constructed rather than captured: the production wrapper does not currently lose
    anything, and a test that only ever sees agreement cannot show the check works."""
    records = [
        {"mode": "organ_direct", "collected": True, "image_sha256": "a" * 64, "phrase": "face",
         "model": "facebook/sam3", "instances": 3, "mask_hashes": ["h1", "h2", "h3"],
         "fixture_id": "f", "run_id": "o"},
        {"mode": "actuator_direct", "collected": True, "image_sha256": "a" * 64, "phrase": "face",
         "model": "facebook/sam3", "instances": 2, "mask_hashes": ["h1", "h2"],
         "fixture_id": "f", "run_id": "a", "conversion": {"dropped": 1}},
    ]
    eq = matrix.wrapper_equivalence(records)
    assert eq["equivalent"] is False
    assert "organ measured 3 and the actuator surfaced 2" in eq["mismatches"][0]["reason"]


def test_unrelated_fixtures_cannot_influence_each_others_attribution(tiny_suite):
    """Two cells sharing a phrase but not a picture are not the same input."""
    records = [
        {"mode": "organ_direct", "collected": True, "image_sha256": "a" * 64, "phrase": "face",
         "model": "facebook/sam3", "instances": 3, "mask_hashes": ["h1"], "fixture_id": "f1",
         "run_id": "o1"},
        {"mode": "actuator_direct", "collected": True, "image_sha256": "b" * 64, "phrase": "face",
         "model": "facebook/sam3", "instances": 0, "mask_hashes": [], "fixture_id": "f2",
         "run_id": "a2", "conversion": None},
    ]
    eq = matrix.wrapper_equivalence(records)
    # No counterpart on the SAME image, so this is reported as unpaired rather than as a loss.
    assert eq["pairs"] == []
    assert "no organ_direct counterpart" in eq["mismatches"][0]["reason"]


def test_planner_stability_distinguishes_identical_from_divergent():
    identical = {"samples": [{"selected_phrase": "folded drapery",
                              "selected_actuator": "concept_segment",
                              "refused_out_of_lock": [], "model": "m"} for _ in range(5)],
                 "total_sam_invocations": 0}
    assert matrix.planner_stability(identical)["verdict"] == "byte_identical"

    lexical = {"samples": [{"selected_phrase": p, "selected_actuator": "concept_segment",
                            "refused_out_of_lock": [], "model": "m"}
                           for p in ("folded drapery", "drapery folds", "folded drapery",
                                     "robe folds", "folded drapery")],
               "total_sam_invocations": 0}
    out = matrix.planner_stability(lexical)
    assert out["verdict"] == "lexically_different"
    assert out["distribution"]["folded drapery"] == 3

    divergent = {"samples": [{"selected_phrase": "folded drapery",
                              "selected_actuator": "concept_segment",
                              "refused_out_of_lock": ["semantic_read"], "model": "m"}],
                 "total_sam_invocations": 0}
    assert matrix.planner_stability(divergent)["verdict"] == "capability_divergent"

    assert matrix.planner_stability(None)["verdict"] == "not_collected"


def test_the_report_records_the_invariant_totals(tmp_path, tiny_suite, sam):
    small, _ = tiny_suite
    runs = _collect(tmp_path, small, FakeSam([]), sam)
    inv = matrix.report(small, runs_root=runs)["invariants"]
    assert inv["captures"] == inv["invocations"] == 10
    assert inv["lock_held"] is True
    assert inv["database_writes"] == 0
    assert inv["source_mutations"] == 0
    assert inv["violations"] == []


def test_the_rendered_report_refuses_in_words_too(tmp_path, tiny_suite, sam):
    small, _ = tiny_suite
    runs = _collect(tmp_path, small, FakeSam([]), sam)
    text = lab.render_matrix_report(matrix.report(small, runs_root=runs))
    assert "not_established" in text
    assert "is not a claim that any instance is the thing the phrase named" in text
    assert "instrument_class_gap" in text
