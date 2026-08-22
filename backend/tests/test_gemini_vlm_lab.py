"""
INTELLIGENCE-001D — the Gemini lab, proved on frozen responses.

NO NETWORK, NO KEY, NO DATABASE. Every call in this suite goes through `FrozenTransport`, which
hands back a canned response body from `research/rehearsals/provider-labs/gemini-vlm/fixtures/`
and records what it was asked for. Nothing here is evidence that Gemini works; it is evidence
that the LAB records honestly, which has to come first — a lab that measured a good provider
badly and one that measured a bad provider well look identical from the outside.

WHAT IS ACTUALLY UNDER TEST, in the order it would hurt to get wrong:

  1. The key never reaches a URL, a record, or an error string. It travels in a header, and the
     redactor scrubs it out of anything on its way to disk.
  2. Identity is never inferred. `mode` says which transport was configured; replay's transport
     RAISES rather than reaching the network.
  3. Nothing is recorded as measured. Both the schema and a second in-code guard refuse it, and
     the non-vacuity tests below doctor a record to prove both actually fire.
  4. `ok` / `empty` / `refused` / `error` / `unavailable` stay five different findings.
  5. A structured-output promise is CHECKED, not trusted: the lab validates what came back
     against the schema it sent, and reports a well-formed-but-wrong payload as invalid.
  6. Exactly one call per experiment. No retry, no reformat-and-ask-again.
  7. Quotas are never invented. A census with no dashboard reading says `not_observed`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys

import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import gemini_vlm_lab as lab                                             # noqa: E402

FIXTURES = lab.FIXTURE_DIR
FAKE_KEY = "AIza-not-a-real-key-0000000000000000000"


# ── helpers ───────────────────────────────────────────────────────────────────────────────────

def fixture(name):
    with open(os.path.join(FIXTURES, f"{name}.json"), "r") as fh:
        return fh.read().encode("utf-8")


def response(name, status=200, headers=None):
    return lab.Response(status=status, headers=headers or {}, body=fixture(name))


def client_for(*names, status=200, headers=None, key=FAKE_KEY):
    """A client wired to a scripted transport. `names` are fixture basenames, in call order."""
    responses = [response(n, status=status, headers=headers) for n in names]
    transport = lab.FrozenTransport(responses)
    return lab.GeminiClient(transport=transport, key=key), transport


@pytest.fixture
def image_row(tmp_path):
    """A corpus row whose bytes are on disk and whose digest matches them."""
    data = b"\xff\xd8\xff\xe0not-a-real-jpeg-but-it-has-a-digest"
    path = tmp_path / "img.jpg"
    path.write_bytes(data)
    return {
        "post_id": "6a6041b81ecd6db1c931eb7a",
        "resolved": True,
        "photo_url": "https://example.invalid/img.jpg",
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "mime_type": "image/jpeg",
        "cached_at": os.path.relpath(str(path), lab.REPO_ROOT),
    }


def _keys_of(node):
    """Every property NAME in a schema, at any depth. A substring search over the serialised
    schema would trip on the prose in `description`, which is where these keywords are discussed."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _keys_of(v)
    elif isinstance(node, list):
        for v in node:
            yield from _keys_of(v)


def one_call(client, **kw):
    kw.setdefault("call_id", "t")
    kw.setdefault("experiment", "text_minimal")
    kw.setdefault("model", "fixture-model-a")
    kw.setdefault("text_parts", ["hello"])
    kw.setdefault("check_corpus", False)
    return lab.call(client, **kw)


# ── 1. the key ────────────────────────────────────────────────────────────────────────────────

class TestKeyNeverEscapes:

    def test_the_key_travels_in_a_header_and_never_in_the_url(self):
        client, transport = client_for("generate-ok-text")
        one_call(client)
        sent = transport.calls[0]
        assert sent["headers"]["x-goog-api-key"] == FAKE_KEY
        assert FAKE_KEY not in sent["url"]
        assert "key=" not in sent["url"]

    def test_the_key_is_scrubbed_out_of_an_error_body_that_echoes_it(self, tmp_path):
        # A provider that quotes the failing request back inside a 400 would otherwise write the
        # secret into the run record — which is a file, in a repo, that gets read and copied.
        echo = json.dumps({"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                     "message": f"bad request for key {FAKE_KEY}"}}).encode()
        transport = lab.FrozenTransport([lab.Response(status=400, body=echo)])
        client = lab.GeminiClient(transport=transport, key=FAKE_KEY)
        rec = one_call(client)
        assert rec["outcome"]["status"] == "error"
        assert FAKE_KEY not in json.dumps(rec)
        assert "***REDACTED***" in rec["outcome"]["error_message"]

    def test_the_fingerprint_identifies_the_key_without_carrying_it(self):
        fp = lab.key_fingerprint(FAKE_KEY)
        assert fp and len(fp) == 12
        assert fp not in FAKE_KEY and FAKE_KEY not in fp
        assert lab.key_fingerprint(FAKE_KEY) == fp          # stable
        assert lab.key_fingerprint(None) is None

    def test_there_is_no_way_to_pass_a_key_on_the_command_line(self):
        # Deliberate: a --api-key flag would put the secret in shell history and in `ps`.
        help_text = lab.build_parser().format_help()
        assert "--api-key" not in help_text
        assert "--key" not in help_text


# ── 2. identity ───────────────────────────────────────────────────────────────────────────────

class TestIdentityIsNeverInferred:

    def test_a_fixture_run_is_recorded_as_fixture_not_as_live(self):
        client, _ = client_for("generate-ok-text")
        assert one_call(client)["mode"] == "fixture"

    def test_replays_transport_refuses_to_reach_the_network(self):
        with pytest.raises(RuntimeError, match="refusing"):
            lab.RefusingTransport().request("GET", "https://example.invalid", {}, None)

    def test_replay_validates_every_frozen_record_and_makes_no_call(self, tmp_path):
        client, _ = client_for("generate-ok-text")
        run_dir, records = lab.run_experiments(
            ["text_minimal"], client=client, model="fixture-model-a",
            runs_root=str(tmp_path))
        assert len(records) == 1
        replayed = lab.replay(run_dir)
        assert [r["call_id"] for r in replayed] == [r["call_id"] for r in records]

    def test_replay_catches_a_record_edited_after_the_fact(self, tmp_path):
        client, _ = client_for("generate-ok-text")
        run_dir, _ = lab.run_experiments(["text_minimal"], client=client,
                                         model="fixture-model-a", runs_root=str(tmp_path))
        path = os.path.join(run_dir, "calls", "01-text_minimal.json")
        rec = lab.read_json(path)
        rec["outcome"]["text"] = "something the model never said"
        lab.write_json(path, rec)
        with pytest.raises(lab.ValidationError, match="content hash"):
            lab.replay(run_dir)


# ── 3. nothing here is a measurement ──────────────────────────────────────────────────────────

class TestNothingIsMeasured:

    def test_every_record_is_stamped_interpretive(self):
        client, _ = client_for("generate-ok-text")
        rec = one_call(client)
        assert rec["epistemic"] == {"status": "interpretive", "measured": False,
                                    "supported_by_capability": None,
                                    "prompt_carries_user_claim": None, "note": None}

    def test_the_guard_refuses_a_record_that_claims_measurement(self):
        client, _ = client_for("generate-ok-text")
        rec = one_call(client)
        rec["epistemic"]["measured"] = True
        with pytest.raises(lab.ValidationError, match="measurement"):
            lab.assert_not_measured(rec)

    def test_the_guard_refuses_a_record_that_names_a_supporting_capability(self):
        client, _ = client_for("generate-ok-text")
        rec = one_call(client)
        rec["epistemic"]["supported_by_capability"] = "extent.soft_field"
        with pytest.raises(lab.ValidationError, match="capability"):
            lab.assert_not_measured(rec)

    def test_the_schema_also_refuses_it_independently_of_the_guard(self):
        # Two locks, because the schema is only consulted where someone remembered to consult it.
        client, _ = client_for("generate-ok-text")
        rec = one_call(client)
        rec["epistemic"]["measured"] = True
        assert lab.validate(rec, "gemini-call")

    def test_write_call_refuses_the_doctored_record(self, tmp_path):
        client, _ = client_for("generate-ok-text")
        rec = one_call(client)
        rec["epistemic"]["measured"] = True
        with pytest.raises(lab.ValidationError):
            lab.write_call(str(tmp_path), rec)
        assert not os.path.exists(os.path.join(str(tmp_path), "calls", "t.json"))


# ── 4. a user hypothesis is not an observation ────────────────────────────────────────────────

class TestPromptsCarryTheirOwnClaims:

    def test_the_four_canonical_prompts_are_present_and_byte_frozen(self):
        prompts = lab.load_prompts()
        assert set(prompts) == {"rich", "sparse", "adversarial", "generative"}
        # Frozen against the directive's text. If a prompt is reworded the comparison across
        # runs is broken, and this should be the thing that says so.
        digests = {pid: hashlib.sha256(p["text"].encode("utf-8")).hexdigest()[:16]
                   for pid, p in prompts.items()}
        assert digests == {
            "rich": "c6a6897bfd7ac769",
            "sparse": "329e7fd81c385e1d",
            "adversarial": "2064b55d8fdabc1c",
            "generative": "e248e203b98d283f",
        }

    def test_the_two_prompts_that_assert_something_are_marked_as_asserting_it(self):
        prompts = lab.load_prompts()
        assert prompts["rich"]["carries_claim"] is True
        assert prompts["adversarial"]["carries_claim"] is True
        assert prompts["sparse"]["carries_claim"] is False
        assert prompts["generative"]["carries_claim"] is False
        assert prompts["rich"]["claim"] and prompts["sparse"]["claim"] is None

    def test_a_record_says_whether_its_prompt_arrived_carrying_a_conclusion(self):
        prompts = lab.load_prompts()
        client, _ = client_for("generate-ok-text")
        assert one_call(client, prompt=prompts["rich"])["epistemic"][
            "prompt_carries_user_claim"] is True
        client, _ = client_for("generate-ok-text")
        assert one_call(client, prompt=prompts["sparse"])["epistemic"][
            "prompt_carries_user_claim"] is False

    def test_the_alignment_instruction_never_asks_the_model_whether_it_agrees(self):
        text = lab.ALIGNMENT_INSTRUCTION.lower()
        assert "not being asked whether you agree" in text
        assert "refused" in text and "not_answerable_from_images" in text

    def test_no_rehearsal_topic_is_compiled_into_anything_the_lab_sends(self):
        # Rule 5. Folds and sculpture live in prompts.json, which is data. The instructions the
        # lab itself sends would read identically over weather photographs — an instrument with
        # one rehearsal's vocabulary inside it could not report that the rehearsal failed.
        topic = ("fold", "sculpt", "veil", "drapery", "garment", "skin", "erotic", "metallic",
                 "tactile", "ajanta")
        for name in ("PROBE_TEXT", "OBSERVATION_INSTRUCTION", "ALIGNMENT_INSTRUCTION",
                     "RELATION_INSTRUCTION"):
            sent = getattr(lab, name).lower()
            assert not [w for w in topic if w in sent], f"{name} carries rehearsal vocabulary"


# ── 5. five outcomes, kept apart ──────────────────────────────────────────────────────────────

class TestOutcomesAreNotCollapsed:

    def test_a_normal_answer_is_ok_with_its_usage_metadata(self):
        client, _ = client_for("generate-ok-text")
        rec = one_call(client)
        assert rec["outcome"]["status"] == "ok"
        assert rec["outcome"]["text"] == "ready"
        assert rec["outcome"]["finish_reason"] == "STOP"
        assert rec["telemetry"]["usage"]["total_token_count"] == 8
        assert rec["telemetry"]["model_version_reported"] == "fixture-model-a-001"

    def test_no_candidates_is_empty_and_not_an_error(self):
        client, _ = client_for("generate-empty")
        rec = one_call(client)
        assert rec["outcome"]["status"] == "empty"
        assert rec["outcome"]["safety_blocked"] is False

    def test_a_blocked_prompt_is_refused_and_not_an_error(self):
        client, _ = client_for("generate-safety-block")
        rec = one_call(client)
        assert rec["outcome"]["status"] == "refused"
        assert rec["outcome"]["finish_reason"] == "SAFETY"
        assert rec["outcome"]["safety_blocked"] is True

    def test_a_safety_finish_reason_is_refused_even_with_a_candidate_present(self):
        client, _ = client_for("generate-finish-safety")
        rec = one_call(client)
        assert rec["outcome"]["status"] == "refused"
        assert rec["outcome"]["safety_blocked"] is True

    def test_a_429_records_the_delay_the_tier_asked_for(self):
        client, _ = client_for("error-429", status=429)
        rec = one_call(client)
        assert rec["outcome"]["status"] == "error"
        assert rec["outcome"]["error_type"] == "RESOURCE_EXHAUSTED"
        assert rec["telemetry"]["rate_limited"] is True
        assert rec["telemetry"]["retry_after_s"] == 27.0

    def test_a_retry_after_header_is_preferred_when_the_provider_sends_one(self):
        client, _ = client_for("error-429", status=429, headers={"retry-after": "13"})
        assert one_call(client)["telemetry"]["retry_after_s"] == 13.0

    def test_a_500_is_an_error_and_is_not_rate_limited(self):
        client, _ = client_for("error-500", status=500)
        rec = one_call(client)
        assert rec["outcome"]["status"] == "error"
        assert rec["telemetry"]["rate_limited"] is False

    def test_a_transport_that_raises_is_an_error_not_a_crash(self):
        class Exploding:
            mode = "fixture"
            def request(self, *a, **k):
                raise TimeoutError("read timed out")
        client = lab.GeminiClient(transport=Exploding(), key=FAKE_KEY)
        rec = one_call(client)
        assert rec["outcome"]["status"] == "error"
        assert rec["outcome"]["error_type"] == "TimeoutError"

    def test_no_key_records_unavailable_rather_than_skipping_the_experiment(self):
        rec = lab.unavailable_record("01-text_minimal", "text_minimal", model=None)
        assert rec["outcome"]["status"] == "unavailable"
        assert rec["endpoint"] == "(not called)"
        assert not lab.validate(rec, "gemini-call")


# ── 6. a structured-output promise is checked, not trusted ────────────────────────────────────

class TestStructuredOutputIsVerified:

    def test_a_conforming_payload_validates(self):
        client, _ = client_for("generate-ok-observation")
        rec = one_call(client, response_schema=lab.load_schema("visual-observation"),
                       validate_with="visual-observation")
        assert rec["outcome"]["json_valid_against_schema"] is True
        assert rec["outcome"]["schema_errors"] == []
        assert rec["outcome"]["json"]["observations"][0]["image_index"] == 0

    def test_well_formed_json_that_breaks_the_contract_is_reported_invalid(self):
        # This is the case that would pass unnoticed if the lab trusted the request. The payload
        # parses, has the right top-level keys, and is missing the fields that make it an
        # observation rather than an adjective.
        client, _ = client_for("generate-schema-violation")
        rec = one_call(client, response_schema=lab.load_schema("visual-observation"),
                       validate_with="visual-observation")
        assert rec["outcome"]["json_valid_against_schema"] is False
        assert any("visible_evidence" in e for e in rec["outcome"]["schema_errors"])

    def test_prose_where_json_was_demanded_is_reported_as_not_json(self):
        client, _ = client_for("generate-not-json")
        rec = one_call(client, response_schema=lab.load_schema("visual-observation"),
                       validate_with="visual-observation")
        assert rec["outcome"]["json_valid_against_schema"] is False
        assert "not JSON" in rec["outcome"]["schema_errors"][0]

    def test_the_schema_is_sent_and_recorded_as_sent(self):
        schema = lab.load_schema("visual-observation")
        client, transport = client_for("generate-ok-observation")
        rec = one_call(client, response_schema=schema, validate_with="visual-observation")
        body = transport.calls[0]["body"]
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["responseSchema"] == schema
        assert rec["request"]["response_schema_sent"] == schema

    def test_the_schemas_sent_stay_inside_the_subset_that_endpoint_accepts(self):
        # `$schema`, `$defs` and `additionalProperties` are rejected by generateContent. The
        # three response schemas are therefore written without them — which is why they live in
        # separate files from `gemini-call.schema.json`, which is ours and uses all three.
        for name in ("visual-observation", "hypothesis-alignment", "relation-proposal"):
            schema = lab.load_schema(name)
            for key in _keys_of(schema):
                assert key not in ("$schema", "$defs", "$ref", "additionalProperties",
                                   "oneOf", "allOf"), f"{name} carries {key}"


# ── 7. exactly one call ───────────────────────────────────────────────────────────────────────

class TestOneCallNoRetry:

    def test_a_successful_experiment_makes_exactly_one_call(self):
        client, transport = client_for("generate-ok-text")
        one_call(client)
        assert len(transport.calls) == 1 and client.calls == 1

    def test_a_429_is_not_retried(self):
        client, transport = client_for("error-429", status=429)
        one_call(client)
        assert len(transport.calls) == 1

    def test_a_schema_violation_is_not_re_asked(self):
        client, transport = client_for("generate-schema-violation")
        one_call(client, response_schema=lab.load_schema("visual-observation"),
                 validate_with="visual-observation")
        assert len(transport.calls) == 1

    def test_run_all_stops_at_the_rate_limit_instead_of_burning_the_quota(self, tmp_path,
                                                                         monkeypatch):
        monkeypatch.setattr(lab, "load_corpus", lambda: [])
        client, transport = client_for("error-429", "generate-ok-text", status=429)
        run_dir, records = lab.run_experiments(
            ["text_minimal", "image_one"], client=client, model="fixture-model-a",
            runs_root=str(tmp_path))
        assert len(records) == 1
        assert len(transport.calls) == 1
        manifest = lab.read_json(os.path.join(run_dir, "manifest.json"))
        assert manifest["stopped_because"] == "rate_limited"


# ── 8. the corpus is read, never written, and never substituted ───────────────────────────────

class TestCorpusDiscipline:

    def test_an_image_whose_bytes_no_longer_match_the_manifest_is_not_sent(self, image_row,
                                                                          tmp_path):
        path = os.path.join(lab.REPO_ROOT, image_row["cached_at"])
        with open(path, "wb") as fh:
            fh.write(b"a completely different picture")
        with pytest.raises(lab.ValidationError, match="does not match the manifest digest"):
            lab.corpus_bytes(image_row)

    def test_a_record_carries_image_digests_and_never_image_bytes(self, image_row):
        client, transport = client_for("generate-ok-observation")
        rec = one_call(client, image_rows=[image_row])
        assert rec["request"]["image_parts"] == [
            {"post_id": image_row["post_id"], "sha256": image_row["sha256"],
             "mime_type": "image/jpeg", "bytes": image_row["bytes"]}]
        blob = json.dumps(rec)
        b64 = transport.calls[0]["body"]["contents"][0]["parts"][1]["inline_data"]["data"]
        assert b64 not in blob                     # the bytes went out; they did not go on disk

    def test_the_before_and_after_fingerprints_are_recorded(self, image_row, monkeypatch):
        monkeypatch.setattr(lab, "corpus_fingerprints",
                            lambda ids: {i: "fp-" + i for i in ids})
        client, _ = client_for("generate-ok-observation")
        rec = one_call(client, image_rows=[image_row], check_corpus=True)
        assert rec["corpus_invariant"]["unchanged"] is True

    def test_a_post_that_changed_under_the_call_is_reported_not_swallowed(self, image_row,
                                                                         monkeypatch):
        seen = {"n": 0}
        def drifting(ids):
            seen["n"] += 1
            return {i: f"fp-{seen['n']}" for i in ids}
        monkeypatch.setattr(lab, "corpus_fingerprints", drifting)
        client, _ = client_for("generate-ok-observation")
        rec = one_call(client, image_rows=[image_row], check_corpus=True)
        assert rec["corpus_invariant"]["unchanged"] is False

    def test_the_lab_has_no_write_path_to_the_posts_collection(self):
        # Rule 10, checked structurally rather than trusted: there is no update, no insert, no
        # delete anywhere in the file, so no future edit can quietly acquire one without this
        # failing first.
        with open(os.path.join(SCRIPTS, "gemini_vlm_lab.py"), "r") as fh:
            source = fh.read()
        for forbidden in ("update_one", "update_many", "insert_one", "insert_many",
                          "delete_one", "delete_many", "replace_one", "find_one_and"):
            assert forbidden not in source, f"the lab acquired a write path: {forbidden}"


# ── 9. the census invents nothing ─────────────────────────────────────────────────────────────

class TestCensusHonesty:

    def test_with_no_key_the_census_is_skipped_and_says_so(self, monkeypatch):
        monkeypatch.delenv(lab.KEY_ENV, raising=False)
        census = lab.take_census(lab.GeminiClient(transport=lab.FrozenTransport([]), key=None))
        assert census["mode"] == "skipped"
        assert lab.KEY_ENV in census["skipped_reason"]
        assert census["models"] == []
        assert not lab.validate(census, "gemini-census")

    def test_a_successful_models_call_still_leaves_every_quota_not_observed(self):
        # The endpoint does not report RPM/TPM/RPD. Filling them from documentation would produce
        # a file indistinguishable from one read off the dashboard.
        client, _ = client_for("models-list")
        census = lab.take_census(client)
        assert census["mode"] == "fixture"
        assert [m["name"] for m in census["models"]] == ["models/fixture-model-a",
                                                         "models/fixture-embedder"]
        assert census["models"][0]["input_token_limit"] == 1048576
        assert census["models"][0]["observed_from"] == "models_endpoint"
        for quota in ("rpm", "tpm", "rpd", "tpd"):
            assert census["quotas"][quota] == {
                "value": None, "unit": None, "source": "not_observed",
                "note": census["quotas"][quota]["note"]}
        assert census["data_use"]["source"] == "not_observed"
        assert not lab.validate(census, "gemini-census")

    def test_image_and_json_support_stay_null_until_a_call_proves_them(self):
        client, _ = client_for("models-list")
        census = lab.take_census(client)
        assert census["models"][0]["image_input"] is None
        assert census["models"][0]["json_mode"] is None

    def test_a_run_promotes_them_and_names_the_call_that_did_it(self, tmp_path, image_row,
                                                                monkeypatch):
        monkeypatch.setattr(lab, "load_corpus", lambda: [image_row])
        monkeypatch.setattr(lab, "corpus_fingerprints", lambda ids: {i: "fp" for i in ids})
        client, _ = client_for("models-list")
        census = lab.take_census(client)

        run_client, _ = client_for("generate-ok-observation")
        run_dir, _ = lab.run_experiments(["json_strict"], client=run_client,
                                         model="fixture-model-a", runs_root=str(tmp_path))
        census = lab.census_from_run(census, run_dir)
        row = census["models"][0]
        assert row["image_input"] is True
        assert row["image_input_evidence"] == "03-json_strict"
        assert row["json_mode"] is True
        assert row["observed_from"] == "live_call"
        assert census["usage_metadata"]["reported"] is True
        assert not lab.validate(census, "gemini-census")

    def test_a_failing_payload_does_not_promote_json_support(self, tmp_path, image_row,
                                                             monkeypatch):
        monkeypatch.setattr(lab, "load_corpus", lambda: [image_row])
        monkeypatch.setattr(lab, "corpus_fingerprints", lambda ids: {i: "fp" for i in ids})
        client, _ = client_for("models-list")
        census = lab.take_census(client)
        run_client, _ = client_for("generate-schema-violation")
        run_dir, _ = lab.run_experiments(["json_strict"], client=run_client,
                                         model="fixture-model-a", runs_root=str(tmp_path))
        census = lab.census_from_run(census, run_dir)
        assert census["models"][0]["json_mode"] is None
        assert census["models"][0]["image_input"] is True      # the image still went and landed

    def test_choose_model_refuses_to_guess_when_no_census_exists(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lab, "CENSUS_PATH", str(tmp_path / "absent.json"))
        with pytest.raises(SystemExit, match="does not guess"):
            lab.choose_model(None)

    def test_no_model_name_is_hard_coded_in_the_lab(self):
        with open(os.path.join(SCRIPTS, "gemini_vlm_lab.py"), "r") as fh:
            source = fh.read()
        assert "gemini-1" not in source and "gemini-2" not in source
        assert "gemini-3" not in source and "flash" not in source.lower()


# ── 10. the experiments, end to end on fixtures ───────────────────────────────────────────────

class TestTheSixExperiments:

    def test_the_order_is_smallest_first(self):
        assert lab.EXPERIMENTS == ("text_minimal", "image_one", "json_strict", "image_three",
                                   "hypothesis_alignment", "relation_proposal")

    def test_hypothesis_alignment_asks_all_four_prompts_over_the_same_images(self, tmp_path,
                                                                            image_row,
                                                                            monkeypatch):
        monkeypatch.setattr(lab, "load_corpus", lambda: [image_row, image_row, image_row])
        monkeypatch.setattr(lab, "corpus_fingerprints", lambda ids: {i: "fp" for i in ids})
        client, transport = client_for(*(["generate-ok-observation"] * 4))
        _run_dir, records = lab.run_experiments(["hypothesis_alignment"], client=client,
                                                model="fixture-model-a",
                                                runs_root=str(tmp_path))
        assert [r["prompt_id"] for r in records] == ["rich", "sparse", "adversarial",
                                                     "generative"]
        boundaries = {tuple(sorted(p["sha256"] for p in r["request"]["image_parts"]))
                      for r in records}
        assert len(boundaries) == 1              # same evidence; only the prompt varied
        assert len(transport.calls) == 4

    def test_relation_proposal_relates_what_this_run_actually_recorded(self, tmp_path,
                                                                      image_row, monkeypatch):
        monkeypatch.setattr(lab, "load_corpus", lambda: [image_row])
        monkeypatch.setattr(lab, "corpus_fingerprints", lambda ids: {i: "fp" for i in ids})
        client, transport = client_for("generate-ok-observation", "generate-ok-observation")
        _run_dir, records = lab.run_experiments(["json_strict", "relation_proposal"],
                                                client=client, model="fixture-model-a",
                                                runs_root=str(tmp_path))
        listing = transport.calls[1]["body"]["contents"][0]["parts"][1]["text"]
        assert "a taut, evenly lit surface" in listing
        assert not transport.calls[1]["body"]["contents"][0]["parts"][2:]   # no images re-sent

    def test_relation_proposal_with_nothing_to_relate_is_empty_not_invented(self, tmp_path,
                                                                           monkeypatch):
        monkeypatch.setattr(lab, "load_corpus", lambda: [])
        client, transport = client_for()
        _run_dir, records = lab.run_experiments(["relation_proposal"], client=client,
                                                model="fixture-model-a", runs_root=str(tmp_path))
        assert records[0]["outcome"]["status"] == "empty"
        assert transport.calls == []

    def test_a_whole_keyless_run_is_nine_unavailable_records_not_a_crash(self, tmp_path,
                                                                        monkeypatch):
        monkeypatch.delenv(lab.KEY_ENV, raising=False)
        monkeypatch.setattr(lab, "load_corpus", lambda: [])
        client = lab.GeminiClient(transport=lab.FrozenTransport([]), key=None)
        run_dir, records = lab.run_experiments(list(lab.EXPERIMENTS), client=client,
                                               model="(no model)", runs_root=str(tmp_path))
        assert len(records) == 9                 # six experiments; the fifth is four prompts
        assert {r["outcome"]["status"] for r in records} == {"unavailable"}
        assert "key ABSENT — no call was made" in lab.report(run_dir)
        for rec in records:
            assert not lab.validate(rec, "gemini-call")

    def test_the_report_says_out_loud_that_none_of_it_is_a_measurement(self, tmp_path):
        client, _ = client_for("generate-ok-text")
        run_dir, _ = lab.run_experiments(["text_minimal"], client=client,
                                         model="fixture-model-a", runs_root=str(tmp_path))
        text = lab.report(run_dir)
        assert "INTERPRETIVE" in text
        assert "None of it is a measurement" in text
        assert "source posts altered: no" in text
