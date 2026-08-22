"""
INTELLIGENCE-001B — the evaluator, and proof that every metric bites.

A metric that cannot be made to fail is not a metric. Most of this file is a mutation table: take a
fixture, break exactly one guarantee, and require the NAMED measurement or the NAMED finding to
move. Red is the cheap part — a broken fixture reddens everything — so each row names its target
and the harness checks that specific one, the same rule `pixelHonesty/classify.mjs` enforces on the
frontend after five mutations there reported success against a suite that did not exist.

TWO GUARDS STAND IN FRONT OF EVERY MUTATION:

  1. THE UNMUTATED FIXTURE MUST HOLD THE HEALTHY VALUE FIRST. Every row declares `before`, and it
     is asserted before the mutation is applied. A mutation that "fixed" a metric already broken
     proves nothing, and this is the assertion that catches it.
  2. THE MUTATION MUST ACTUALLY CHANGE THE RECORD. `_apply` asserts the payload differs afterwards,
     so a row whose edit silently missed its target — a renamed field, a moved list — fails as a
     hole rather than passing because the metric was going to say that anyway.

THE RELATION FIXTURE IS SYNTHETIC, AND SAYS SO. The baseline export contains zero relations, so
"delete all relations" cannot be demonstrated on it — there is nothing to delete. `with_relations`
builds a derived record that has them. It is constructed in this file rather than committed as a
second 300KB fixture so that what was added is visible in the same place it is reasoned about.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.inquiry_intelligence_evaluate import (  # noqa: E402
    METRICS, Measurement, Session, evaluate, sanitize, compare_to_baseline,
    check_expectations, CASES_DIR, FIXTURES_DIR, CONTRACT_CONTRADICTIONS,
)

BASELINE = FIXTURES_DIR / "baseline-rev6.sanitized.json"


@pytest.fixture(scope="module")
def raw() -> Dict[str, Any]:
    return json.loads(BASELINE.read_text())


@pytest.fixture(scope="module")
def case() -> Dict[str, Any]:
    return json.loads((CASES_DIR / "II-01-rich-user-vocabulary.json").read_text())


def ev(payload: Dict[str, Any], case: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return evaluate(payload, case)


def metric(payload: Dict[str, Any], name: str) -> Dict[str, Any]:
    return ev(payload)["metrics"][name]


def value(payload: Dict[str, Any], name: str) -> Any:
    return metric(payload, name)["value"]


def codes(payload: Dict[str, Any], case: Dict[str, Any] | None = None) -> List[str]:
    return [f["code"] for f in ev(payload, case)["diagnosis"]["findings"]]


# ── the fixture is the run it claims to be ──────────────────────────────────

def test_the_baseline_is_the_run_the_lane_says_it_is(raw, case):
    """Every symptom this harness was built to catch, asserted on the real export.

    If any of these drifts, the mutation table below is being run against a different record and
    its `before` values would quietly stop meaning anything.
    """
    e = ev(raw, case)
    m = e["metrics"]
    assert e["session_ref"]["state"] == "complete"
    assert e["case_ref"]["prompt_sha256_matches"] is True
    assert m["claims_total"]["value"] == 20
    assert m["relation_count"]["value"] == 0
    assert m["capability_receipts"]["value"] == 0
    assert m["observables_proposed"]["value"] == 6
    assert m["claims_sourced_only_from_prompt"]["value"] == 11
    assert m["truncated_stages"]["value"] == 4
    assert "compiler" in m["truncated_stages"]["detail"]["stages"]
    assert e["diagnosis"]["semantic_outcome"] == "prompt_dominated"
    assert e["diagnosis"]["outcomes_disagree"] is True


def test_the_evaluator_reports_the_predicted_symptoms(raw, case):
    found = set(codes(raw, case))
    for expected in ("relations_absent", "prompt_dominated", "stage_truncated",
                     "nothing_was_commissioned", "workflow_and_semantics_disagree",
                     "answer_asserts_an_instrument_that_did_not_run"):
        assert expected in found, expected


def test_the_answer_prose_and_its_own_flags_disagree(raw):
    """The predicted symptom, and it is not where it was predicted to be.

    The composer's structured provenance is honest — `measured_anything` and
    `simulated_capability` are both false — and its prose opens "one capability was invoked". The
    receipts are empty and the capability stage's own summary says nothing was commissioned. The
    flags were never the problem; the sentence a person reads was.
    """
    s = Session(json.loads(BASELINE.read_text()))
    prov = s.synthesis["provenance"]
    assert prov["measured_anything"] is False
    assert prov["simulated_capability"] is False
    assert s.capability_receipts == [] and s.evidence == []
    m = metric(s.raw, "synthesis_asserts_capability_without_receipt")
    assert m["value"] == 1
    assert "capability was invoked" in m["detail"][0]["sentence"]
    assert m["warning"], "a prose match must say it is a detector, not a verdict"


# ── null is not zero ────────────────────────────────────────────────────────

def test_a_null_measurement_must_say_what_was_missing():
    with pytest.raises(ValueError, match="say what was missing"):
        Measurement(value=None, kind="count")
    with pytest.raises(ValueError, match="cannot both"):
        Measurement(value=3, kind="count", refused="but also this")


def test_the_four_refusals_on_the_baseline_are_sentences(raw):
    e = ev(raw)
    refused = {k: v for k, v in e["metrics"].items() if v["value"] is None}
    assert set(refused) == {
        "relation_source_completeness", "critic_accepted", "critic_revised", "critic_rejected"}
    for name, m in refused.items():
        assert len(m["refused"]) > 40, f"{name} refused without explaining itself"


def test_relation_completeness_refuses_rather_than_scoring_a_perfect_one(raw):
    """1.0 is the most flattering number in the file and an empty relation set must not earn it."""
    m = metric(raw, "relation_source_completeness")
    assert m["value"] is None
    assert "has not achieved perfect relation hygiene" in m["refused"]


def test_critic_counts_refuse_because_the_contract_has_no_critique_record(raw):
    for name in ("critic_accepted", "critic_revised", "critic_rejected"):
        m = metric(raw, name)
        assert m["value"] is None
        assert "gap in the pipeline, not in the run" in m["refused"]


def test_a_scope_class_is_never_read_as_a_post_id(raw):
    """`image_scope` carries `one_image` and friends. Nothing may index a picture by them."""
    s = Session(raw)
    scopes = {tuple(a.get("image_scope") or []) for a in s.atoms}
    assert ("one_image",) in scopes
    per_image = value(raw, "observations_per_image")
    assert set(per_image) == set(s.declared_post_ids())
    assert "one_image" not in per_image and "not_an_image_question" not in per_image


# ── building a record that has relations ────────────────────────────────────

def with_relations(payload: Dict[str, Any]) -> Dict[str, Any]:
    """A derived record carrying three relations: two cross-image, one within a single image.

    SYNTHETIC AND DERIVED, not a run. It exists because the mutations about relations have nothing
    to bite on otherwise. The endpoints are real claims from the baseline, chosen so that their
    traceable image sets genuinely differ (or genuinely do not), because a fixture whose "cross
    image" relation was not actually cross-image would make the metric pass for the wrong reason.
    """
    out = copy.deepcopy(payload)
    s = Session(out)
    by_images: Dict[str, List[str]] = {}
    for c in s.claims:
        imgs = tuple(sorted(s._claim_images(c)))
        if imgs:
            by_images.setdefault(imgs, []).append(c["claim_id"])

    distinct = [ids for imgs, ids in by_images.items()]
    assert len(distinct) >= 2, "the baseline must offer two differently-imaged claims"
    a, b = distinct[0][0], distinct[1][0]
    same_pair = next((ids for ids in distinct if len(ids) >= 2), None)
    assert same_pair, "the baseline must offer two claims sharing an image set"

    out["graph"]["claim_edges"] = [
        {"edge_id": "edg_cross_1", "kind": "complicates", "from_claim": a, "to_claim": b,
         "why": "a contrast across two images"},
        {"edge_id": "edg_cross_2", "kind": "supports", "from_claim": b, "to_claim": a,
         "why": "an agreement across two images"},
        {"edge_id": "edg_same_1", "kind": "complicates",
         "from_claim": same_pair[0], "to_claim": same_pair[1],
         "why": "a contrast inside one image"},
    ]
    return out


def test_the_synthetic_relation_fixture_is_what_it_claims(raw):
    payload = with_relations(raw)
    assert value(payload, "relation_count") == 3
    assert value(payload, "cross_image_relation_count") == 2
    assert value(payload, "contrast_count") == 2
    assert value(payload, "cross_image_contrast_count") == 1
    assert value(payload, "relation_source_completeness") == 1.0
    assert "relations_absent" not in codes(payload)


# ── the mutation table ──────────────────────────────────────────────────────

def _strip_image_refs(p: Dict[str, Any]) -> Dict[str, Any]:
    for b in p["graph"]["reading"]["blocks"]:
        b["image_refs"] = []
    return p


def _user_hypothesis_becomes_an_image_observation(p: Dict[str, Any]) -> Dict[str, Any]:
    for u in p["graph"]["source_units"]:
        if u.get("source_type") == "prompt_clause":
            u["author"] = "scene_theorist"
    for a in p["graph"]["semantic_atoms"]:
        if a.get("author") == "user":
            a["author"] = "semantic_dissector"
    return p


def _delete_all_relations(p: Dict[str, Any]) -> Dict[str, Any]:
    p["graph"]["claim_edges"] = []
    return p


def _untraceable_relation(p: Dict[str, Any]) -> Dict[str, Any]:
    p["graph"]["claim_edges"].append(
        {"edge_id": "edg_dangling", "kind": "supports",
         "from_claim": "clm_does_not_exist", "to_claim": p["graph"]["claims"][0]["claim_id"],
         "why": "an endpoint nothing resolves"})
    return p


def _measured_without_evidence(p: Dict[str, Any]) -> Dict[str, Any]:
    p["graph"]["claims"][0]["status"] = "measured"
    return p


def _synthesis_claims_a_capability_ran(p: Dict[str, Any]) -> Dict[str, Any]:
    p["synthesis"]["sections"][0]["text"] = (
        "The extent capability was executed across all three images. "
        + p["synthesis"]["sections"][0]["text"])
    return p


def _move_a_post_fingerprint(p: Dict[str, Any]) -> Dict[str, Any]:
    p["posts"][0]["fingerprint"] = "0" * 64
    return p


def _drop_the_rejected_relation_from_the_trail(p: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a critique record while leaving its relation in place.

    The relation stays, the record of somebody having rejected it goes. On today's contract this
    cannot be detected at all, which is the point of the row: it asserts the REFUSAL, not a count.
    """
    p["graph"]["relation_critiques"] = [
        {"relation_ref": "edg_cross_1", "outcome": "accepted", "why": "kept"},
    ]
    return p


def _unread_one_image(p: Dict[str, Any]) -> Dict[str, Any]:
    doomed = Session(p).declared_post_ids()[0]
    for b in p["graph"]["reading"]["blocks"]:
        b["image_refs"] = [r for r in b["image_refs"] if r != doomed]
    return p


def _every_claim_from_the_prompt(p: Dict[str, Any]) -> Dict[str, Any]:
    for c in p["graph"]["claims"]:
        c["source_spans"] = [{"origin": "prompt", "text": p["prompt"], "source_id": "prompt"}]
        c["source_span"] = c["source_spans"][0]
    return p


def _drop_the_execution_scope(p: Dict[str, Any]) -> Dict[str, Any]:
    p["execution_scope"] = {}
    p["graph"]["execution_scope"] = {}
    return p


def _untruncate_every_stage(p: Dict[str, Any]) -> Dict[str, Any]:
    for st in p["stages"]:
        if st.get("outcome") in ("truncated", "thin", "coverage_failed"):
            st["outcome"] = "completed"
    for ps in p["graph"]["passes"]:
        if ps.get("outcome") in ("truncated", "thin", "coverage_failed"):
            ps["outcome"] = "completed"
    return p


#: id, guarantee, base fixture, mutation, and the NAMED thing that must move.
#: `before`/`after` are metric values; `finding` is a diagnosis code that must appear.
MUTATIONS: List[Dict[str, Any]] = [
    dict(id="observations-lose-their-images",
         guarantee="an observation that names no image is counted as one",
         base="baseline", mutate=_strip_image_refs,
         metric="observations_without_image_refs", before=0, after=24,
         finding="no_image_was_cited"),
    dict(id="one-image-goes-unread",
         guarantee="an image the run was given and never mentioned is named",
         base="baseline", mutate=_unread_one_image,
         metric="image_diversity_images_cited", before=3, after=2,
         finding="image_unread"),
    dict(id="the-persons-hypothesis-becomes-an-observation",
         guarantee="a prompt clause reattributed to a model is caught",
         base="baseline", mutate=_user_hypothesis_becomes_an_image_observation,
         metric="prompt_hypotheses_preserved", before=True, after=False,
         finding="attribution_lost"),
    dict(id="every-claim-comes-from-the-prompt",
         guarantee="a run that only restates the question is called prompt-dominated",
         base="baseline", mutate=_every_claim_from_the_prompt,
         metric="claims_with_image_traceability", before=9, after=0,
         finding="no_claim_reaches_an_image"),
    dict(id="all-relations-deleted",
         guarantee="a comparative record with claims and no relations is underperformed",
         base="related", mutate=_delete_all_relations,
         metric="relation_count", before=3, after=0,
         finding="relations_absent"),
    dict(id="a-relation-with-an-endpoint-nothing-resolves",
         guarantee="an untraceable relation is not counted as a sound one",
         base="related", mutate=_untraceable_relation,
         metric="relation_source_completeness", before=1.0, after=0.75,
         finding=None),
    dict(id="a-claim-measured-with-nothing-behind-it",
         guarantee="a status asserting observation with no receipt and no evidence is caught",
         base="baseline", mutate=_measured_without_evidence,
         metric="unsupported_measured_statuses", before=0, after=1,
         finding="measured_without_support"),
    dict(id="the-answer-says-an-instrument-ran",
         guarantee="prose asserting a capability ran with zero receipts is caught",
         base="baseline", mutate=_synthesis_claims_a_capability_ran,
         metric="synthesis_asserts_capability_without_receipt", before=1, after=2,
         finding="answer_asserts_an_instrument_that_did_not_run"),
    dict(id="the-execution-scope-disappears",
         guarantee="an unknown shortfall REFUSES rather than reporting zero unexamined atoms",
         base="baseline", mutate=_drop_the_execution_scope,
         metric="unexamined_atoms", before=87, after=None,
         finding=None),
    dict(id="every-stage-reports-completed",
         guarantee="truncation is read from the record and not inferred from the outcome",
         base="baseline", mutate=_untruncate_every_stage,
         metric="truncated_stages", before=4, after=0,
         finding=None),
]


def _load(base: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    if base == "baseline":
        return copy.deepcopy(raw)
    if base == "related":
        return with_relations(raw)
    raise AssertionError(f"unknown base fixture {base}")


@pytest.mark.parametrize("row", MUTATIONS, ids=[m["id"] for m in MUTATIONS])
def test_every_metric_bites(row, raw):
    before_payload = _load(row["base"], raw)

    # GUARD 1: the unmutated fixture must hold the healthy value.
    observed = value(before_payload, row["metric"])
    assert observed == row["before"], (
        f"{row['id']}: the unmutated fixture already reads {observed!r} for "
        f"{row['metric']}, so this mutation would prove nothing.")

    after_payload = row["mutate"](_load(row["base"], raw))

    # GUARD 2: the mutation must actually have changed the record.
    assert json.dumps(after_payload, sort_keys=True) != json.dumps(before_payload, sort_keys=True), \
        f"{row['id']}: the mutation left the record untouched — it missed its target."

    # THE NAMED METRIC MOVED.
    got = value(after_payload, row["metric"])
    assert got == row["after"], (
        f"{row['id']}: {row['metric']} was expected to move to {row['after']!r} and read {got!r}")

    if row["after"] is None:
        assert metric(after_payload, row["metric"])["refused"], \
            f"{row['id']}: a null must carry its reason"

    # AND THE NAMED FINDING APPEARED.
    if row["finding"]:
        assert row["finding"] in codes(after_payload), (
            f"{row['id']}: the metric moved but `{row['finding']}` was not reported. A number "
            f"nobody surfaces is not a check.")


def test_a_moved_source_post_is_an_error_finding(raw, case):
    """Fingerprints are compared against the CASE, so this one needs the case to bite."""
    clean = ev(copy.deepcopy(raw), case)
    assert clean["inputs"]["fingerprint_changes"] == []
    assert "source_post_moved" not in [f["code"] for f in clean["diagnosis"]["findings"]]

    moved = _move_a_post_fingerprint(copy.deepcopy(raw))
    e = ev(moved, case)
    assert len(e["inputs"]["fingerprint_changes"]) == 1
    finding = next(f for f in e["diagnosis"]["findings"] if f["code"] == "source_post_moved")
    assert finding["severity"] == "error"
    assert "different pixels" in finding["statement"]


def test_removing_a_rejected_relation_cannot_be_detected_today(raw):
    """The mutation the contract cannot catch — asserted as a refusal, not smuggled past.

    With a critique record present the counts become computable. Delete the rejection and the
    remaining record still parses, still counts, and nothing anywhere says a relation was ever
    rejected. This test exists so the gap is a failing expectation somebody can close rather than
    an absence nobody wrote down.
    """
    related = with_relations(raw)
    assert metric(related, "critic_rejected")["value"] is None  # no record at all

    with_trail = _drop_the_rejected_relation_from_the_trail(copy.deepcopy(related))
    assert value(with_trail, "critic_accepted") == 1
    assert value(with_trail, "critic_rejected") == 0
    assert value(with_trail, "relations_accepted_without_critique") == 2

    # And the thing that cannot be seen: whether a rejection was ever there to remove.
    assert "relation_critiques" not in json.loads(BASELINE.read_text()).get("graph", {}), (
        "if the contract ever grows a critique record, this test should be replaced by one that "
        "compares a trail against its own history rather than asserting the absence.")


# ── the report says what it cannot decide ───────────────────────────────────

def test_the_manual_questions_survive_into_the_evaluation(raw, case):
    e = ev(raw, case)
    assert len(e["manual_review"]["questions"]) == len(case["manual_review_questions"])
    assert "outside what this harness can decide" in e["manual_review"]["note"]


def test_shortcuts_nothing_catches_are_printed_in_the_report(raw):
    """Case 4 declares a shortcut with `detected_by: none`. It must reach the report."""
    case4 = json.loads((CASES_DIR / "II-04-generative-relation.json").read_text())
    e = ev(raw, case4)
    unautomated = e["manual_review"]["unautomated_shortcuts"]
    assert len(unautomated) == 1
    assert "averag" in unautomated[0].lower()


def test_every_case_expectation_names_a_metric_that_exists():
    """A manifest cannot claim a check nobody implements."""
    for path in sorted(CASES_DIR.glob("II-*.json")):
        case = json.loads(path.read_text())
        for prop in case["expected_structural_properties"]:
            assert prop["metric"] in METRICS, f"{path.name}: no metric named {prop['metric']}"


def test_an_expectation_on_an_unknown_metric_is_reported_not_ignored(raw):
    fake = {"expected_structural_properties": [
        {"metric": "elegance", "expectation": {"min": 1}, "why": "invented"}]}
    rows = check_expectations({k: v for k, v in
                               ((n, f(Session(raw))) for n, f in METRICS.items())}, fake)
    assert rows[0]["status"] == "unknown_metric"


def test_an_unmeasurable_expectation_is_not_a_failure(raw):
    fake = {"expected_structural_properties": [
        {"metric": "relation_source_completeness", "expectation": {"min": 1.0}, "why": "x"}]}
    rows = check_expectations({k: v for k, v in
                               ((n, f(Session(raw))) for n, f in METRICS.items())}, fake)
    assert rows[0]["status"] == "unmeasurable"
    assert "perfect relation hygiene" in rows[0]["why"]


# ── sanitizing, and comparing ───────────────────────────────────────────────

def test_the_archived_baseline_points_at_its_fixture_rather_than_copying_it():
    """A copy that can drift from the file it was copied from will eventually disagree with it."""
    import hashlib
    d = ROOT / "research/rehearsals/inquiry-intelligence/run-archive/baseline-rev6"
    assert not (d / "session.raw.json").exists(), "the committed example must not duplicate 300KB"
    src = json.loads((d / "session.source.json").read_text())
    assert src["fixture"] == "baseline-rev6"
    assert src["sha256"] == hashlib.sha256(BASELINE.read_bytes()).hexdigest(), (
        "the fixture was edited after this run was archived. That is exactly the mismatch the "
        "digest is here to make visible — re-archive, or explain the change.")


def test_a_live_run_still_archives_the_whole_session(tmp_path, raw, case):
    """No fixture behind it means the archive is the only place that record exists."""
    from scripts.inquiry_intelligence_evaluate import archive
    out = archive(ev(raw, case), raw, case, tmp_path / "live")
    assert (out / "session.raw.json").exists()
    assert not (out / "session.source.json").exists()


def test_the_committed_fixture_carries_no_outbound_url_and_no_secret():
    body = BASELINE.read_text()
    assert "http://" not in body and "https://" not in body
    assert "urn:sanitized:" in body


def test_sanitizing_keeps_the_shape_it_needs_to_demonstrate():
    """`image_ref == image_url` is a real production property; both are digested, not dropped."""
    out = sanitize({"image_refs": [{"post_id": "p", "image_ref": "https://x/y.jpg",
                                    "image_url": "https://x/y.jpg"}],
                    "api_key": "sk-live-secret"})
    entry = out["image_refs"][0]
    assert entry["image_ref"] == entry["image_url"] != "https://x/y.jpg"
    assert entry["image_ref"].startswith("urn:sanitized:")
    assert out["api_key"] == "[redacted]"


def test_a_baseline_comparison_refuses_a_delta_across_a_refusal(raw):
    a = ev(copy.deepcopy(raw))
    b = ev(with_relations(raw))
    cmp = compare_to_baseline(b, a)
    rel = cmp["metrics"]["relation_count"]
    assert rel["baseline"] == 0 and rel["current"] == 3 and rel["delta"] == 3
    hygiene = cmp["metrics"]["relation_source_completeness"]
    assert hygiene["baseline"] is None and hygiene["delta"] is None
    assert "would invent a comparison" in hygiene["note"]


# ── generality ──────────────────────────────────────────────────────────────

def test_the_evaluator_names_no_rehearsal_topic():
    """No folds, no sculpture, no architecture in the logic. The stopword list is checked too."""
    src = (ROOT / "scripts" / "inquiry_intelligence_evaluate.py").read_text().lower()
    import re
    for topic in ("sculpture", "buddha", "museum", "rotunda", "marble", "drapery"):
        assert not re.search(rf"\b{topic}s?\b", src), topic
    # the negative control: the scan can see one
    assert re.search(r"\bsculptures?\b", "these sculptures use folds")


def test_it_survives_a_session_with_nothing_in_it():
    e = ev({"session_id": "empty", "state": "exhausted", "graph": {}})
    assert e["diagnosis"]["semantic_outcome"] == "barren"
    assert e["metrics"]["observations_total"]["value"] is None
    assert e["metrics"]["claims_total"]["value"] == 0  # zero claims IS a measurement


def test_the_contract_contradictions_travel_with_the_harness():
    titles = [t for t, _ in CONTRACT_CONTRADICTIONS]
    assert any("image_scope" in t for t in titles)
    assert any("relation-critique" in t for t in titles)
    for _, body in CONTRACT_CONTRADICTIONS:
        assert len(body) > 60
