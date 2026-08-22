"""
INTELLIGENCE-001C — the checks that keep the local-VLM lab honest.

NO MODEL IS LOADED HERE. Every response these tests read came off the local Qwen3.5-9B on the
machine that ran the lane and was frozen into `research/rehearsals/provider-labs/local-qwen-vlm/
frozen/`. That is the point: an audit is only worth anything if it is exercised against what the
model ACTUALLY said, and a fixture written by hand to make an assertion pass would be the lab
grading its own homework.

FOUR THINGS ARE TESTED, and the third is the one that would be easiest to leave out:

  1. THE GRAMMAR CANNOT SAY `measured`. The observation schema's `status` is a one-value enum, so
     the token is absent from the sampler's grammar rather than discouraged by a sentence in a
     system prompt. A schema edit that widened it would fail here.

  2. THE AUDITS BITE, AND ONLY WHERE THEY SHOULD. Each guarantee gets a plausible lie that must be
     caught AND the real sentence that must not be. Both halves matter: the first version of the
     attribution audit flagged `shadows created by the drapery`, and an audit that cries wolf on
     good output is one a reader learns to ignore.

  3. THE BLINDNESS IS STRUCTURAL. Experiments 2, 3 and 5 assert `saw_an_image is False` on the
     frozen records. The separation between a person's hypothesis and an image observation is
     enforced by the request body carrying no image part — not by the instruction above it — and
     these tests are what would notice if someone ever "helpfully" added the picture back.

  4. ABSENT TELEMETRY STAYS ABSENT. A response with no `timings` block yields `None` rates, and a
     gate with no evidence is UNDETERMINED rather than FAIL. A missing experiment must not be
     able to look like a bad model.

STDLIB AND PYTEST ONLY. No torch, no network, no server — these run on every pull request.
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

import local_qwen_vlm_lab as lab  # noqa: E402

FROZEN = lab.FROZEN_DIR


def _frozen(name):
    p = FROZEN / f"{name}.json"
    if not p.exists():
        pytest.skip(f"no frozen {name} — run `local_qwen_vlm_lab.py freeze` after a lab run")
    return json.loads(p.read_text())


# ── 1. the grammar cannot say `measured` ─────────────────────────────────────

def test_observation_status_is_a_one_value_enum():
    """
    `interpretive` and nothing else. This is the enforcement, not the documentation: the value is
    compiled into the GBNF llama-server derives from the schema, so `measured` is not a token the
    sampler can emit.
    """
    schema = lab.load_schema("observation")
    status = schema["properties"]["observations"]["items"]["properties"]["status"]
    assert status["enum"] == ["interpretive"]


def test_schema_rejects_a_measured_status():
    schema = lab.load_schema("observation")
    obj = {
        "image_ref": "img-k7",
        "observations": [{
            "locus": "the drapery",
            "visible_organization": "diagonal folds",
            "surface_light_behavior": "highlights along the ridges",
            "apparent_material_effect": "heavy opaque cloth",
            "uncertainty": "medium",
            "status": "measured",
        }],
        "cannot_determine": [],
    }
    errs = lab.validate(obj, schema)
    assert any("status" in e and "measured" in e for e in errs), errs


def test_schema_rejects_an_extra_field_and_a_missing_one():
    schema = lab.load_schema("observation")
    assert lab.validate({"image_ref": "img-k7", "observations": []}, schema)          # missing
    assert lab.validate({"image_ref": "img-k7", "observations": [], "cannot_determine": [],
                         "confidence": 0.9}, schema)                                  # extra


def test_alignment_keeps_both_kinds_of_not_knowing():
    """
    `does_not_bear_on` (the observations are about something else) and `cannot_determine` (they
    are about the right thing and do not settle it) are different findings. A schema with one of
    them would force the model to misreport which.
    """
    stances = (lab.load_schema("alignment")["properties"]["claims"]["items"]
               ["properties"]["stance"]["enum"])
    assert "does_not_bear_on" in stances and "cannot_determine" in stances
    assert set(stances) == {"supports", "complicates", "challenges",
                            "does_not_bear_on", "cannot_determine"}


# ── 2. the audits bite, and only where they should ───────────────────────────

@pytest.mark.parametrize("text,what", [
    ("attributed to the workshop of Canova", "an attribution phrase"),
    ("carved by Bernini", "an authorship phrase"),
    ("made by Rodin in his later years", "a named maker"),
    ("possibly representing a river god", "an identification hedge"),
    ("a 19th-century piece", "a century"),
    ("circa 1860", "a date"),
    ("known as The Veiled Lady", "a title"),
])
def test_attribution_audit_bites(text, what):
    hits = lab.audit_text(text)["attribution_claims"]
    assert what in [h["what"] for h in hits], f"{text!r} was not caught: {hits}"


@pytest.mark.parametrize("text,what", [
    ("the fold turns approximately 30 degrees from the vertical", "a dimension"),
    ("about 40% of the surface is in shadow", "a percentage"),
    ("the depth was measured at the crease", "the word measured"),
    ("the highlight sits exactly on the ridge", "a precision claim"),
    ("a ratio of 3 to 2 across the shoulders", "a stated ratio"),
    ("calibrated against the reference chart", "a calibration claim"),
])
def test_measurement_audit_bites(text, what):
    hits = lab.audit_text(text)["measurement_claims"]
    assert what in [h["what"] for h in hits], f"{text!r} was not caught: {hits}"


@pytest.mark.parametrize("text", [
    # Every one of these is real output from the lane's first blind pass, and every one was a
    # FALSE POSITIVE of an earlier version of the audit. They are the regression.
    "the central V-shape created by the drape",
    "deep indentations of the folds create strong shadows created by the drapery",
    "a style of carving that keeps the transitions loose",
    "the material appears smooth, polished, and opaque",
    "Moderate confidence in this reading",
])
def test_audit_does_not_cry_wolf(text):
    a = lab.audit_text(text)
    assert a["clean"], f"{text!r} was flagged: {a}"


def test_case_matters_where_the_pattern_depends_on_it():
    """
    The audit's first table was matched case-insensitively throughout, so `[A-Z]` matched anything
    and `style of carving` read as a workshop attribution. Patterns that mean a proper noun are
    case-sensitive now, and this is what says so.
    """
    assert lab.audit_text("in the manner of Canova")["attribution_claims"]
    assert not lab.audit_text("in the manner of carving used here")["attribution_claims"]


def test_proper_noun_finder_survives_serialised_json():
    """
    The audited text is usually a serialised object, where a value opens after `":` rather than
    after a full stop. Without that, every field-initial capital read as a named entity — the
    first run reported `Moderate` and `Whether` as proper nouns.
    """
    blob = json.dumps({"locus": "Moderate depth", "grounds": "Whether it is stone is unclear"})
    assert lab.find_proper_nouns(blob) == []
    assert "Canova" in lab.find_proper_nouns(json.dumps({"grounds": "It resembles Canova"}))


def test_the_frozen_blind_observations_are_clean():
    """
    The audit, run over what the model really said. Not a tautology: the same model volunteered
    `possibly representing Venus or Aphrodite` in this lane's free-prose census probe, and the
    delta between that and this is the finding the schema and system prompt bought.
    """
    rec = _frozen("experiment-1-observe")
    for img in rec["images"]:
        a = lab.audit_text(json.dumps(img["parsed"], ensure_ascii=False))
        assert a["clean"], (f"{img['ref']} carried {a['measurement_claims']} "
                            f"{a['attribution_claims']}")


def test_every_frozen_observation_is_interpretive():
    rec = _frozen("experiment-1-observe")
    seen = {o["status"] for img in rec["images"]
            for o in (img["parsed"] or {}).get("observations", [])}
    assert seen == {"interpretive"}, seen


# ── 3. the blindness is structural ───────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "experiment-2-align-rich-tactile-philosophy",
    "experiment-3-compare",
    "experiment-5-canonical-prompts",
])
def test_the_passes_that_judge_hypotheses_never_saw_an_image(name):
    """
    THE LOAD-BEARING TEST OF THE LANE. The alignment and comparison passes are handed the frozen
    observations as prose and no picture at all, so they CANNOT produce a new visual observation —
    there is nothing in front of them to look at. If somebody ever adds the image back for
    convenience, this is what stops it being a silent change.
    """
    assert _frozen(name)["saw_an_image"] is False


def test_the_alignment_cited_observations_that_exist():
    rec = _frozen("experiment-2-align-rich-tactile-philosophy")
    assert rec["hallucinated_observation_ids"] == []
    assert rec["cited_observation_ids"], "an alignment that cited nothing has not been grounded"


def test_the_comparison_invented_no_references():
    rec = _frozen("experiment-3-compare")
    assert rec["invented_refs"] == []
    for c in rec["parsed"]["comparisons"]:
        assert set(c["refs"]) <= set(rec["refs"])


def test_reference_tokens_cannot_be_guessed():
    """
    `A`, `B`, `C` would let a model that tracked nothing return a correct-looking reference by
    accident, and the ref-correctness gate would read that as competence.
    """
    for t in lab.REF_TOKENS:
        assert len(t) >= 5 and "-" in t
    assert len(set(lab.REF_TOKENS)) == len(lab.REF_TOKENS)


def test_novelty_separates_reasoning_from_invention():
    """
    A model narrating its own reasoning is not a model inventing a picture. The first alignment
    pass reported twenty-six novel terms and every one of them was `claim`, `states`, `explicitly`
    — which made a clean run look like a dirty one.
    """
    n = lab.novelty("The observations explicitly state a claim about the surface.",
                    "the surface is polished")
    assert n["novel_substantive_count"] == 0, n["novel_substantive"]
    assert n["novel_discourse"]

    invented = lab.novelty("There is gilded bronze along the plinth.", "the surface is polished")
    assert "bronze" in invented["novel_substantive"]


def test_stemming_stops_a_variant_reading_as_an_invention():
    assert lab.novelty("the surface is reflecting light", "the surface reflects light"
                       )["novel_substantive_count"] == 0


# ── 4. absent telemetry stays absent ─────────────────────────────────────────

def test_a_fenced_json_block_is_reported_as_fenced():
    """
    The census found `response_format: json_object` returning a ```json fence on this build. A
    harness that stripped the fence silently would have recorded that mode as reliable, so the
    stripping is done AND reported.
    """
    obj, note = lab.parse_json('```json\n{"a": 1}\n```')
    assert obj == {"a": 1}
    assert note == "fenced"
    assert lab.parse_json('{"a": ')[0] is None
    assert lab.parse_json(None) == (None, "no content")


def test_gate_with_no_evidence_is_undetermined_not_failed(tmp_path, monkeypatch):
    """
    A missing experiment must not be able to look like a bad model. Three answers, not two.
    """
    monkeypatch.setattr(lab, "RUNS_DIR", tmp_path)
    (tmp_path / "empty").mkdir()

    class A:
        run = "empty"
    lab.cmd_gates(A())
    verdicts = {g["name"]: g["verdict"]
                for g in json.loads((tmp_path / "empty" / "gates.json").read_text())["gates"]}
    assert set(verdicts.values()) == {"UNDETERMINED"}, verdicts


def test_frozen_calls_never_carry_an_invented_rate():
    """
    Every rate in the records is llama-server's own `timings` figure. Where the server reported
    nothing the field is absent — never a number the client computed with a stopwatch and then
    presented as the server's throughput.
    """
    rec = _frozen("experiment-4-reliability")
    for t in rec["trials"]:
        for k in ("prompt_per_second", "predicted_per_second"):
            assert t[k] is None or isinstance(t[k], float)
        assert t["latency_ms"] is None or isinstance(t["latency_ms"], float)


def test_machine_state_never_claims_a_per_process_vram_figure():
    st = lab.machine_state(None)
    assert "vram" not in json.dumps(st).lower()
    assert "rss_caveat" in st, "RSS without its caveat reads as the footprint, and is not"


# ── the corpus is read-only, and anchored ────────────────────────────────────

def test_the_corpus_resolver_refuses_to_write():
    with pytest.raises(RuntimeError, match="read-only"):
        lab._refuse("insert_one")()


def test_the_corpus_manifest_anchors_the_bytes():
    """
    An observation in this lab is about THOSE bytes. Without the digest a Cloudinary re-encode
    would turn a changed observation into a finding about the model.
    """
    if not lab.CORPUS_PATH.exists():
        pytest.skip("corpus not resolved on this machine")
    doc = json.loads(lab.CORPUS_PATH.read_text())
    assert doc["bytes_in_git"] is False
    for img in doc["images"]:
        if img.get("found"):
            assert len(img["sha256"]) == 64
            assert img["photo_url"].startswith("https://")


def test_the_lab_binds_nothing():
    """
    `local_qwen_vlm` names a measurement subject. If it ever becomes a registered provider that
    is a decision made where the production contract lives, and this test is where it gets
    noticed rather than discovered.
    """
    assert lab.PROVIDER_IDENTITY == "local_qwen_vlm"
    backend = os.path.join(REPO_ROOT, "backend")
    hits = []
    for root, _dirs, files in os.walk(backend):
        if "__pycache__" in root or os.sep + "tests" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                with open(p, encoding="utf-8", errors="replace") as fh:
                    if "local_qwen_vlm" in fh.read():
                        hits.append(p)
    assert hits == [], f"the lab identity leaked into production code: {hits}"


# ── the four canonical prompts ───────────────────────────────────────────────

def test_every_canonical_prompt_declares_where_it_came_from():
    """
    Only the first exists verbatim in the tree. The other three are authored, and each says so —
    the precedent is HARNESS-003F, which authored its control prompt for the same reason and
    declared it rather than presenting an invention as a recovered artefact.
    """
    doc = json.loads(lab.PROMPTS_PATH.read_text())
    ids = [p["id"] for p in doc["prompts"]]
    assert ids == ["rich-tactile-philosophy", "sparse-material-perception",
                   "adversarial-sameness", "generative-fourth-sculpture"]
    for p in doc["prompts"]:
        assert p["provenance"].startswith(("verbatim:", "authored for this lab"))
        assert p["text"].strip()


def test_the_verbatim_prompt_still_matches_its_source():
    """
    A drift guard. If the contract sample's prompt changes, prompt 1 is no longer verbatim and the
    word in its provenance has become false.
    """
    src = os.path.join(REPO_ROOT, "contracts", "samples", "inquiry-session.scoped.json")
    if not os.path.exists(src):
        pytest.skip("contract sample not present")
    with open(src, encoding="utf-8") as fh:
        expected = json.load(fh)["prompt"]
    doc = json.loads(lab.PROMPTS_PATH.read_text())
    got = next(p for p in doc["prompts"] if p["id"] == "rich-tactile-philosophy")["text"]
    assert got == expected


# ── rule 11: the identity is on every record ─────────────────────────────────

def test_every_record_carries_its_execution_identity(tmp_path, monkeypatch):
    """
    Replay / fixture / live / local / provider identities must remain explicit. The stamp is
    applied by `write_record` rather than by each caller, because an identity that depends on
    somebody remembering to add it is the one that goes missing on the record where it mattered.
    """
    monkeypatch.setattr(lab, "RUNS_DIR", tmp_path)
    lab.write_record("r", "thing", {"experiment": "whatever"})
    rec = json.loads((tmp_path / "r" / "thing.json").read_text())
    assert rec["provider"] == "local_qwen_vlm"
    assert rec["execution_mode"] == "local_live"
    assert rec["replayed"] is False
    assert rec["binds_anything"] is False
    assert rec["experiment"] == "whatever"


def test_the_stamp_cannot_overwrite_a_records_own_field():
    """A payload that already names its provider keeps its own value; the stamp fills gaps."""
    import inspect
    src = inspect.getsource(lab.write_record)
    assert "**payload," in src, "the payload must be spread LAST or the stamp silently wins"


def test_a_wrong_level_reference_is_not_called_a_hallucination():
    """
    The clean run's comparison pass returned `img-k7-o3` — a real OBSERVATION id used where an
    IMAGE ref was required. It compared two loci and labelled it a comparison of two pictures.
    That is a category error, and calling it an invention would describe a fluent, well-formed,
    wrongly-scoped answer as a fabrication. Both fail the reference gate; they are counted apart.
    """
    rec = _frozen("experiment-3-compare")
    assert "wrong_level_refs" in rec, "the two mistakes are being reported as one number again"
    for r in rec["wrong_level_refs"]:
        assert r not in rec["refs"]
        assert any(r.startswith(ref) for ref in rec["refs"]), \
            f"{r} is not an observation id of a known image — it is an invention"
    assert not set(rec["wrong_level_refs"]) & set(rec["invented_refs"])
