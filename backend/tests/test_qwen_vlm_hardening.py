"""
INTELLIGENCE-001C-R1 — the checks that keep the hardening study honest.

NO MODEL, NO SERVER, NO NETWORK. Everything here runs against frozen real records and synthetic
negative controls. An honesty guard that could only be exercised by loading six gigabytes of
weights would never run in CI, and a guard that never runs is a comment.

EVERY GUARD HAS A NEGATIVE CONTROL. It is not enough to show that a check fires on bad input —
that passes just as well if the check fires on everything. So each guard is also neutered in place
and the same input re-run, and the test asserts the detection DISAPPEARS. If a guard is deleted or
weakened, its negative control is what turns red.

The three-way distinction this file exists to protect, in every section:

    zero        the thing happened zero times
    null        nothing in the record could say whether it happened
    absent      no cell measured it, so there is no verdict to give
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import local_qwen_vlm_lab as lab                 # noqa: E402
import qwen_hardening_audits as audits           # noqa: E402
import qwen_vlm_hardening as hard                # noqa: E402

HARD_FROZEN = hard.HARD_FROZEN


def _frozen(name):
    p = HARD_FROZEN / f"{name}.json"
    if not p.exists():
        pytest.skip(f"no frozen {name} — capture it with a matrix run")
    return json.loads(p.read_text())


# ── an inventory the critic can be pointed at ────────────────────────────────

def _inventory():
    """
    Three images whose observations share some vocabulary and differ in the rest, so `universal`
    and `distinctive` both mean something.
    """
    def img(ref, extra):
        return {"ref": ref, "parsed": {"observations": [
            {"locus": f"{extra} region", "visible_organization": f"carved stone with {extra}",
             "surface_light_behavior": "light falls across the surface",
             "apparent_material_effect": f"stone that reads as {extra}",
             "uncertainty": "medium", "status": "interpretive"},
            {"locus": "background", "visible_organization": "a plain dark field",
             "surface_light_behavior": "light returns almost nothing",
             "apparent_material_effect": "matte stone surround",
             "uncertainty": "high", "status": "interpretive"},
        ], "cannot_determine": ["the scale"]}}
    return {"images": [img("img-k7", "braided"), img("img-q2", "veiled"),
                       img("img-v9", "pleated")]}


def _claims():
    return [{"id": "c1", "text": "The folding is the same operation in all of them.",
             "kind": "universal_sameness"},
            {"id": "c2", "text": "The differences come from lighting.",
             "kind": "causal_attribution"}]


def _disp(**kw):
    d = {"user_claim_id": "c1", "disposition": "supports",
         "observation_ids": ["img-k7-o0", "img-q2-o0", "img-v9-o0"],
         "discriminative_explanation": "the braided region differs from the pleated one",
         "unresolved_alternatives": ""}
    d.update(kw)
    return d


def _align(*dispositions):
    return {"dispositions": list(dispositions)}


# ── the profile identities cannot be confused ────────────────────────────────

def test_16k_and_32k_profiles_have_distinct_identities_and_argv():
    a = hard.LaunchProfile(ctx_id="ctx16k", n_ctx=16384)
    b = hard.LaunchProfile(ctx_id="ctx32k", n_ctx=32768)
    assert a.id != b.id
    assert "16384" in " ".join(a.argv()) and "32768" not in " ".join(a.argv())
    assert "32768" in " ".join(b.argv()) and "16384" not in " ".join(b.argv())
    assert hard.Cell("context", a.ctx_id, {"n_ctx": a.n_ctx}).config_id != \
           hard.Cell("context", b.ctx_id, {"n_ctx": b.n_ctx}).config_id


def test_image_token_floor_is_part_of_the_profile_identity():
    base = hard.LaunchProfile(ctx_id="ctx32k", n_ctx=32768)
    hi = hard.LaunchProfile(ctx_id="ctx32k", n_ctx=32768, image_min_tokens=1024)
    assert base.id != hi.id
    assert "--image-min-tokens" not in base.argv()
    assert hi.argv()[hi.argv().index("--image-min-tokens") + 1] == "1024"


def test_requested_context_and_served_context_are_recorded_apart(tmp_path, monkeypatch):
    """
    `-c 32768` is a request. What the server serves is the answer, and a profile whose identity
    cannot be confirmed must not be ratifiable.
    """
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-t")
    cell = hard.Cell("context", "ctx32k", {"n_ctx": 32768})
    led.finish(cell, "done", {
        "n_ctx_requested": 32768, "served_n_ctx": 16384,
        "context_identity_verified": False,
        "safety": {"safe": True, "breaches": [], "peak_wired_mb": 9000},
        "retention_summary": {"retrieved": 10, "probes": 10}})
    v = hard.context_verdict(led)
    assert v["verdict"] == "UNDETERMINED"
    assert "32768" in v["why"] and "16384" in v["why"]


# ── an unsafe result cannot be ratified ─────────────────────────────────────

def test_wired_memory_at_the_ceiling_is_a_breach():
    start = {"started_ok": True}
    machines = [{"wired_mb": lab.METAL_CEILING_MB, "swap_used_mb": 100}]
    v = hard.safety_verdict(start, [], True, machines)
    assert not v["safe"]
    assert any("Metal ceiling" in b for b in v["breaches"])


def test_swap_alone_never_condemns_a_profile():
    """
    NEGATIVE CONTROL for the epistemic distinction. Whole-machine swap belongs to everything
    running; a profile failed on swap would be a finding about the browser.
    """
    v = hard.safety_verdict({"started_ok": True}, [], True,
                            [{"wired_mb": 100, "swap_used_mb": 14000}])
    assert v["safe"], v["breaches"]
    assert v["peak_whole_machine_swap_mb"] == 14000


def test_an_unsafe_context_cell_cannot_be_ratified(tmp_path, monkeypatch):
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-u")
    led.finish(hard.Cell("context", "ctx32k", {"n_ctx": 32768}), "done", {
        "n_ctx_requested": 32768, "served_n_ctx": 32768, "context_identity_verified": True,
        "safety": {"safe": False, "breaches": ["wired memory reached the ceiling"],
                   "peak_wired_mb": 13000},
        "retention_summary": {"retrieved": 10, "probes": 10}})
    assert hard.context_verdict(led)["verdict"] == "32K_UNSAFE"


def test_safe_but_unusable_context_is_16k_only_not_32k_safe(tmp_path, monkeypatch):
    """A context the model cannot read back is space, not capacity."""
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-v")
    led.finish(hard.Cell("context", "ctx32k", {"n_ctx": 32768}), "done", {
        "n_ctx_requested": 32768, "served_n_ctx": 32768, "context_identity_verified": True,
        "safety": {"safe": True, "breaches": [], "peak_wired_mb": 9000},
        "retention_summary": {"retrieved": 2, "probes": 20}})
    v = hard.context_verdict(led)
    assert v["verdict"] == "16K_ONLY"
    assert v["safe"] is True and v["usable"] is False


# ── absent telemetry stays absent; a missing cell is UNDETERMINED ────────────

def test_a_missing_context_cell_is_undetermined_not_failed(tmp_path, monkeypatch):
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-w")
    led.cells_dir.mkdir(parents=True, exist_ok=True)
    assert hard.context_verdict(led)["verdict"] == "UNDETERMINED"


def test_every_unmeasured_role_is_undetermined(tmp_path, monkeypatch):
    """
    Success in one role does not transfer to another. A role with no cell gets no verdict, and
    this is the test that stops an observer result being read as a judge result.
    """
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-x")
    led.cells_dir.mkdir(parents=True, exist_ok=True)
    v = hard.role_verdicts(led)
    for role in ("relation_proposer", "critic", "epistemic_judge", "final_composer"):
        assert v[role]["verdict"] == "UNDETERMINED", role
        assert v[role]["why"]


def test_absent_sampling_verification_is_false_not_true():
    w = hard.SlotWatcher()
    v = w.verdict({"temperature": 0.4})
    assert v["sampling_verified"] is False
    assert v["observed"] is None
    assert "never observed" in v["why"]


def test_a_mismatched_slot_reading_is_not_verified():
    w = hard.SlotWatcher()
    w.samples = [{"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
                  "presence_penalty": 1.5}]
    v = w.verdict({"temperature": 0.4})
    assert v["sampling_verified"] is False
    assert v["mismatches"]["temperature"] == {"requested": 0.4, "observed": 1.0}


def test_a_matching_slot_reading_is_verified():
    w = hard.SlotWatcher()
    w.samples = [{"temperature": 0.4, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                  "presence_penalty": 0.0}]
    assert w.verdict({"temperature": 0.4, "top_p": 0.8})["sampling_verified"] is True


# ── Part 4: unsupported precision ───────────────────────────────────────────

@pytest.mark.parametrize("text,match", [
    ("The suggested uncertainty is 10% for 'polished'.", "10%"),           # #230's real failure
    ("a confidence of 0.85 in this reading", "0.85"),
    ("the fold turns 30 degrees from the vertical", "30 degrees"),
    ("roughly 40% of the surface lies in shadow", "40%"),
    ("the depth was measured at the crease", "measured"),
    ("precisely parallel to the shoulder", "precisely"),
    ("a ratio of 3:2 across the shoulders", "3:2"),
])
def test_unsupported_numerical_certainty_is_detected(text, match):
    a = audits.audit_precision(text)
    assert not a["epistemically_valid"], a
    assert match in [f["match"] for f in a["unsupported"]]


@pytest.mark.parametrize("text", [
    "a series of three folds runs diagonally",
    "two figures stand against a dark ground",
    "the details are precisely executed",
    "the uncertainty here is high",
    "the surface is smooth, polished and opaque",
])
def test_source_visible_numbers_are_not_automatically_condemned(text):
    """
    NEGATIVE CONTROL for the whole audit. An observer that may not say how many folds it can see
    is not an observer, and an audit that cries wolf is one a reader learns to ignore.
    """
    a = audits.audit_precision(text)
    assert a["epistemically_valid"], a["unsupported"]


def test_the_declared_uncertainty_enum_is_never_flagged():
    a = audits.audit_precision("uncertainty: medium")
    assert a["epistemically_valid"]
    assert a["counts"]["declared_uncertainty_category"] == 1


def test_certainty_context_is_what_turns_a_percentage_into_a_fabrication(monkeypatch):
    """
    THE NEGATIVE CONTROL FOR THE ORDERING. `10%` is caught either way; the point is that
    `the uncertainty is 10%` is caught AS A SELF-SCORE. Neuter the certainty lexicon and that
    reading disappears, which is what proves the ordering is load-bearing.
    """
    text = "the suggested uncertainty is 10%"
    before = audits.audit_precision(text)["unsupported"][0]["why"]
    assert "own confidence" in before

    import re as _re
    monkeypatch.setattr(audits, "_CERTAINTY_CONTEXT", _re.compile(r"(?!x)x"))
    after = audits.audit_precision(text)["unsupported"][0]["why"]
    assert "own confidence" not in after


def test_the_audit_skips_the_schema_enum_field():
    rec = {"observations": [{"locus": "a", "visible_organization": "b",
                             "surface_light_behavior": "c", "apparent_material_effect": "d",
                             "uncertainty": "high", "status": "interpretive"}],
           "cannot_determine": []}
    a = audits.audit_observation_record(rec)
    assert a["epistemically_valid"]
    assert "uncertainty" in a["skipped_fields"]


def test_the_audit_is_topic_independent():
    """
    Rule 5. No material, genre, period or subject word appears in the tables — point it at trains
    and it works unchanged.
    """
    a = audits.audit_precision("the locomotive sits precisely 4 metres from the buffer")
    assert not a["epistemically_valid"]
    src = open(os.path.join(SCRIPTS, "qwen_hardening_audits.py"), encoding="utf-8").read().lower()
    for banned in ("sculpt", "marble", "drapery", "buddha", "renaissance", "baroque", "fold"):
        assert banned not in src, f"topic vocabulary {banned!r} leaked into the audit"


# ── Part 4b: the repair is a second event, and can fail ─────────────────────

def test_original_and_repaired_text_stay_distinct(tmp_path, monkeypatch):
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-r")
    cell = hard.Cell("inference", "A", {"x": 1})
    led.finish(cell, "done", {"precision_repairs": [{
        "original_text_preserved": "the suggested uncertainty is 10% for polished",
        "parsed": {"repaired_text": "the surface reads as polished, though not certainly so"},
        "verdict": "repaired", "is_second_model_event": True, "image_resent": False}]})
    rec = led.read(cell)["precision_repairs"][0]
    assert rec["original_text_preserved"] != rec["parsed"]["repaired_text"]
    assert "10%" in rec["original_text_preserved"], "the original must survive byte-for-byte"
    assert rec["is_second_model_event"] is True
    assert rec["image_resent"] is False


def test_a_repair_that_keeps_the_number_is_not_accepted():
    """A rewrite that changes the wording and keeps the claim is still a failure."""
    after = audits.audit_precision("my certainty here is about 10 percent, roughly speaking")
    assert not after["epistemically_valid"]


def test_a_repair_that_deletes_the_observation_is_gutted_not_repaired():
    assert audits.audit_precision("polished.")["epistemically_valid"]
    assert len("polished.".split()) < 6, "the gutted rule keys on the observation surviving"


# ── Part 5: the claim critic ────────────────────────────────────────────────

def test_an_unknown_citation_fails():
    v = audits.critique_alignment(
        _align(_disp(observation_ids=["img-k7-o99"]), _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert not v["valid"]
    assert v["counts"]["unknown_citation"] == 1


def test_a_malformed_citation_is_named_apart_from_an_unknown_one():
    v = audits.critique_alignment(
        _align(_disp(observation_ids=["grounids"]), _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["malformed_citation"] == 1
    assert v["counts"]["unknown_citation"] == 0


def test_a_wrong_image_citation_fails():
    v = audits.critique_alignment(
        _align(_disp(observation_ids=["img-zz-o0"]), _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert not v["valid"]
    assert v["counts"]["unknown_citation"] + v["counts"]["wrong_image_citation"] >= 1


def test_a_moving_disposition_must_rest_on_something():
    v = audits.critique_alignment(
        _align(_disp(observation_ids=[]), _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["missing_citation_for_moving_disposition"] == 1


def test_not_bearing_on_may_legitimately_cite_nothing():
    """NEGATIVE CONTROL: the rule must not punish the two dispositions that do not move a claim."""
    v = audits.critique_alignment(
        _align(_disp(disposition="does_not_bear_on", observation_ids=[]),
               _disp(user_claim_id="c2", disposition="cannot_determine",
                     observation_ids=[])),
        _claims(), _inventory())
    assert v["counts"]["missing_citation_for_moving_disposition"] == 0


def test_a_universal_claim_supported_from_one_image_fails():
    v = audits.critique_alignment(
        _align(_disp(observation_ids=["img-k7-o0"]), _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["single_image_support_for_universal_claim"] == 1


def test_diversity_cannot_support_sameness_without_a_bridge():
    v = audits.critique_alignment(
        _align(_disp(discriminative_explanation=
                     "the braided region differs from the pleated one, whereas the veiled one "
                     "is different again"),
               _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["diversity_used_for_sameness"] == 1


def test_a_bridged_contrast_survives():
    """
    NEGATIVE CONTROL. Difference plus an explicit bridge is a legitimate argument, and a check
    that fired on it would forbid the only honest way to argue from contrast.
    """
    v = audits.critique_alignment(
        _align(_disp(discriminative_explanation=
                     "the braided region differs from the pleated one, but because both show the "
                     "same tool signature the operation is one"),
               _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["diversity_used_for_sameness"] == 0


def test_generic_shared_evidence_cannot_prove_sameness():
    """
    Every content word of the quote is one the observer used about all three images, so the quote
    cannot separate the claim from its negation however true it is.
    """
    v = audits.critique_alignment(
        _align(_disp(discriminative_explanation=
                     'each shows "carved stone with light falls across the surface"'),
               _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["generic_quoted_evidence"] == 1


def test_a_distinctive_quote_is_not_condemned():
    """NEGATIVE CONTROL for the generic-evidence rule."""
    v = audits.critique_alignment(
        _align(_disp(discriminative_explanation=
                     'only one shows "stone that reads as braided", which the others lack'),
               _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["generic_quoted_evidence"] == 0


def test_absence_of_contradiction_is_not_support():
    v = audits.critique_alignment(
        _align(_disp(discriminative_explanation=
                     "no observation contradicts the claim, so it stands"),
               _disp(user_claim_id="c2")),
        _claims(), _inventory())
    assert v["counts"]["absence_of_contradiction_as_support"] == 1


def test_a_minted_claim_is_caught_even_if_the_grammar_let_it_through():
    v = audits.critique_alignment(
        _align(_disp(), _disp(user_claim_id="c2"), _disp(user_claim_id="c9")),
        _claims(), _inventory())
    assert v["counts"]["minted_claim"] == 1


def test_a_missing_claim_is_caught():
    v = audits.critique_alignment(_align(_disp()), _claims(), _inventory())
    assert v["counts"]["missing_claim"] == 1


def test_a_valid_challenge_survives_every_check():
    """
    THE MOST IMPORTANT NEGATIVE CONTROL IN THE FILE. A critic that invalidates sound resistance
    would manufacture exactly the surrender this lane exists to measure.
    """
    v = audits.critique_alignment(
        _align(_disp(disposition="challenges",
                     observation_ids=["img-k7-o0", "img-q2-o0", "img-v9-o0"],
                     discriminative_explanation=
                     "one reads as braided, one as veiled and one as pleated, and no observation "
                     "reports a shared tool signature that would make them one operation",
                     unresolved_alternatives="whether a single maker produced all three"),
               _disp(user_claim_id="c2", disposition="cannot_determine",
                     observation_ids=[],
                     discriminative_explanation="a single photograph cannot separate lighting "
                                                "from carving",
                     unresolved_alternatives="a second lighting setup would settle it")),
        _claims(), _inventory())
    assert v["valid"], v["findings"]
    assert v["all_resisted"] is True
    assert v["all_accepted"] is False


def test_false_premise_acceptance_is_detected():
    v = audits.critique_alignment(
        _align(_disp(disposition="supports"),
               _disp(user_claim_id="c2", disposition="supports",
                     observation_ids=["img-k7-o1"],
                     discriminative_explanation="the lighting varies between them")),
        _claims(), _inventory())
    assert v["all_accepted"] is True
    assert v["all_resisted"] is False


def test_neutering_the_critic_makes_the_acceptance_tests_pass_vacuously(monkeypatch):
    """
    THE NEGATIVE CONTROL FOR THE WHOLE CRITIC. Replace the check table with nothing and the
    findings vanish — which is what proves the assertions above depend on the guard rather than on
    the shape of the fixtures.
    """
    bad = _align(_disp(observation_ids=["img-k7-o0", "img-k7-o99"]),
                 _disp(user_claim_id="c2"))
    assert audits.critique_alignment(bad, _claims(), _inventory())["counts"]["unknown_citation"] == 1

    # Neuter the guard by making the inventory admit everything. If the assertion above rested on
    # the fixture rather than on the check, this would still report a finding.
    every = ["img-k7-o0", "img-q2-o0", "img-v9-o0", "img-k7-o99"]
    monkeypatch.setattr(audits, "observation_index",
                        lambda exp1: ({o: "x" for o in every},
                                      {"img-k7": set(), "img-q2": set(), "img-v9": set()},
                                      ["img-k7", "img-q2", "img-v9"]))
    after = audits.critique_alignment(bad, _claims(), _inventory())
    assert after["counts"]["unknown_citation"] == 0


# ── the alignment grammar makes minting impossible ──────────────────────────

def test_the_claim_ids_are_compiled_into_the_grammar():
    claims = hard.claims_for("adversarial-sameness")
    s = hard.alignment_schema_for(claims)
    enum = s["properties"]["dispositions"]["items"]["properties"]["user_claim_id"]["enum"]
    assert enum == [c["id"] for c in claims]
    assert "REPLACED_AT_REQUEST_TIME" not in enum
    assert s["properties"]["dispositions"]["minItems"] == len(claims)
    assert s["properties"]["dispositions"]["maxItems"] == len(claims)


def test_the_template_placeholder_never_reaches_a_request():
    tmpl = hard.hard_schema("claim-alignment")
    assert tmpl["properties"]["dispositions"]["items"]["properties"]["user_claim_id"]["enum"] \
        == ["REPLACED_AT_REQUEST_TIME"]


def test_every_declared_prompt_has_a_claim_decomposition():
    ids = {p["id"] for p in json.loads(lab.PROMPTS_PATH.read_text())["prompts"]}
    decomposed = {p["prompt_id"] for p in hard.load_claims()["prompts"]}
    assert decomposed <= ids, decomposed - ids
    for p in hard.load_claims()["prompts"]:
        assert p["claims"], p["prompt_id"]
        assert len({c["id"] for c in p["claims"]}) == len(p["claims"])


def test_an_instruction_clause_gets_no_claim_id():
    """A model cannot take an evidential stance on `tell me`, and giving it one would score an
    imperative as if it were an assertion."""
    adv = next(p for p in hard.load_claims()["prompts"]
               if p["prompt_id"] == "adversarial-sameness")
    assert adv["directive_pressure"]["clause"].startswith("tell me")
    assert all(c["text"] != adv["directive_pressure"]["clause"] for c in adv["claims"])


# ── the ledger: resume does not duplicate, states stay apart ────────────────

def test_resume_does_not_repeat_a_completed_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-resume")
    cell = hard.Cell("inference", "A", {"temperature": 0.4})
    assert led.state(cell) == "pending"
    led.start(cell)
    assert led.state(cell) == "started" and not led.is_done(cell)
    led.finish(cell, "done", {"payload": 1})
    assert led.is_done(cell)
    same = hard.Cell("inference", "A", {"temperature": 0.4})
    assert same.config_id == cell.config_id
    assert led.is_done(same), "a resumed run must recognise the cell it already paid for"
    other = hard.Cell("inference", "A", {"temperature": 0.7})
    assert not led.is_done(other), "a different configuration must be a different cell"


def test_interrupted_unavailable_and_invalid_are_three_states(tmp_path, monkeypatch):
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-states")
    a, b, c = (hard.Cell("adversarial", n, {"i": i})
               for i, n in enumerate(("x", "y", "z")))
    led.start(a)                                     # left in flight
    led.finish(b, "unavailable", {"why": "server did not answer"})
    led.finish(c, "invalid", {"why": "answered, and the answer failed a check"})
    assert led.state(a) == "started"
    assert led.state(b) == "unavailable"
    assert led.state(c) == "invalid"
    assert len({led.state(x) for x in (a, b, c)}) == 3


def test_a_started_receipt_is_written_before_the_call(tmp_path, monkeypatch):
    monkeypatch.setattr(hard, "RUNS_ROOT", tmp_path)
    led = hard.Ledger("R1-receipt")
    cell = hard.Cell("context", "ctx32k", {"n_ctx": 32768})
    led.start(cell)
    rec = led.read(cell)
    assert rec["state"] == "started"
    assert "BEFORE the model was called" in rec["note"]
    assert rec["machine_at_start"]


def test_the_baseline_run_records_are_not_written_by_this_lane():
    """#230's records stand unchanged. This lane's run ids are prefixed, and nothing else is."""
    assert hard.latest_r1_run() is None or hard.latest_r1_run().startswith("R1-")
    for name in ("20260822-final", "20260822-full", "20260822-a"):
        p = hard.RUNS_ROOT / name
        if p.exists():
            assert not (p / "cells").exists(), f"{name} was written into by this lane"


# ── the lane registers nothing ──────────────────────────────────────────────

def test_no_production_code_imports_this_provider():
    """
    Route, collection, model registry, dependency injection, frontend. Eligible is not integrated,
    and this is where a quiet binding would be noticed rather than discovered.
    """
    needles = ("local_qwen_vlm", "qwen_vlm_hardening", "qwen_hardening_audits",
               "local_qwen_vlm_lab")
    roots = [os.path.join(REPO_ROOT, "backend"), os.path.join(REPO_ROOT, "frontend", "src")]
    hits = []
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            if any(x in dirpath for x in ("__pycache__", "node_modules", os.sep + "tests")):
                continue
            for f in files:
                if not f.endswith((".py", ".js", ".jsx", ".ts", ".tsx")):
                    continue
                p = os.path.join(dirpath, f)
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        body = fh.read()
                except OSError:
                    continue
                for n in needles:
                    if n in body:
                        hits.append(f"{p}: {n}")
    assert hits == [], f"the lab leaked into production code: {hits}"


def test_the_lane_declares_that_it_integrates_nothing():
    prof = hard.load_profiles()
    assert "ELIGIBLE DOES NOT MEAN INTEGRATED" in open(
        os.path.join(SCRIPTS, "qwen_vlm_hardening.py"), encoding="utf-8").read()
    assert prof["no_transfer"]
    assert "65536" in json.dumps(prof["context_profiles_excluded"])


# ── frozen real outcomes ────────────────────────────────────────────────────

def test_frozen_context_cells_record_what_the_server_served():
    for rec in _frozen("context-cells"):
        assert "served_n_ctx" in rec and "n_ctx_requested" in rec
        assert "context_identity_verified" in rec
        assert rec["safety"]["metal_ceiling_mb"] == lab.METAL_CEILING_MB


def test_frozen_retention_never_calls_retrieval_reasoning():
    """
    The label must say retrieval and must not CLAIM reasoning. The first version of this test
    banned the substring `reason` outright and failed on the record's own phrase `retrieval, not
    reasoning` — the guard was right and the test was wrong.
    """
    for rec in _frozen("context-cells"):
        for r in rec.get("retention", []):
            what = r.get("what_this_is", "").lower()
            assert "retrieval" in what, what
            for m in re.finditer(r"reason", what):
                assert what[max(0, m.start() - 4):m.start()] == "not ", what


def test_frozen_adversarial_outcomes_are_not_collapsed_into_one_number():
    rows = _frozen("adversarial-cells")
    for r in rows:
        if r.get("state") != "done":
            continue
        o = r["outcome"]
        for k in ("all_claims_resisted", "all_claims_accepted", "mixed",
                  "unusable_or_truncated", "deterministic_audit_failed",
                  "repaired_successfully", "remained_invalid_after_repair"):
            assert k in o, k
        assert "accuracy" not in json.dumps(o).lower()
