"""
HARNESS-002A §3 — the scene theorist reads pixels and is still a thinker.

Every test is a way the reading could become a measurement, or a way an absent reading could become
a plausible one. No test here touches a network: the live class takes an injected client, and the
replay class takes a frozen payload.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from backend.schemas.semantic_compilation import (CallTopology, CompilerRefusalKind, ImageRef,
                                                  ReadingBlock, ReadingBlockKind)
from backend.services import role_registry
from backend.services.semantic_compilation import contracts
from backend.services.semantic_compilation import theorist as theorist_module
from backend.services.semantic_compilation.theorist import (ROLE, FrozenSceneTheorist,
                                                            ModelSceneTheorist, build_prompt,
                                                            build_synthesis_prompt)

INQUIRY = "inq_000000000001"
PROMPT = "How do these interiors organise themselves, and what could follow from both?"
IMAGES = [ImageRef(post_id="p1", title="one", image_ref="https://x.invalid/1.jpg"),
          ImageRef(post_id="p2", title="two", image_ref="https://x.invalid/2.jpg")]

CLEAN_PAYLOAD = {
    "reading": "Both interiors gather their parts toward a centre, though by different means.",
    "blocks": [
        {"kind": "part", "text": "a tall central void", "images": ["p1"]},
        {"kind": "organization", "text": "the surrounding parts step down in scale",
         "images": ["p1"]},
        {"kind": "comparison", "text": "one centres by height, the other by enclosure",
         "images": ["p1", "p2"]},
        {"kind": "historical_association", "text": "the stepping recalls an earlier convention"},
        {"kind": "tension", "text": "the centring is undercut by an off-axis opening"},
        {"kind": "hypothesis", "text": "a third could centre by light alone"},
    ],
}


class FakeClient:
    """A Groq-shaped client. Records every request so the call topology can be asserted."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests = []
        self.chat = self

    @property
    def completions(self):
        return self

    finish_reason = "stop"

    def create(self, **kwargs):
        self.requests.append(kwargs)
        payload = self._responses.pop(0) if self._responses else {}
        if isinstance(payload, BaseException):
            raise payload
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return type("C", (), {"choices": [type("M", (), {
            "message": type("X", (), {"content": text})(),
            "finish_reason": self.finish_reason})()]})()


class TruncatingClient(FakeClient):
    """A client whose calls stop on the output budget but still return parseable JSON."""
    finish_reason = "length"


# ── the role ─────────────────────────────────────────────────────────────────

def test_the_four_new_roles_are_thinkers_with_an_interpretive_ceiling():
    for name in ("scene_theorist", "semantic_compiler", "deliberation_steward",
                 "synthesis_composer"):
        role = role_registry.get(name)
        assert role is not None, name
        assert role.kind is role_registry.RoleKind.THINKER, name
        assert role.epistemic_ceiling.value == "interpretive", name
        assert role.capability is None and role.adapter is None, name
        assert role.producers == (), f"{name} claims to stand behind a producer of geometry"


def test_each_new_role_is_separately_rebindable():
    """They share model strings today. Sharing a string is not sharing a decision — that is the
    whole argument ROLES-001 makes, and it only holds if each can move alone."""
    try:
        role_registry.bind("scene_theorist", "some/other-vlm")
        assert role_registry.model_for("scene_theorist") == "some/other-vlm"
        assert role_registry.model_for("semantic_compiler") != "some/other-vlm"
    finally:
        role_registry.unbind("scene_theorist")


def test_the_theorist_is_bound_to_a_vision_capable_model_and_the_compiler_is_not_required_to_be():
    assert role_registry.model_for("scene_theorist") == role_registry.model_for("dissector")
    assert role_registry.get("scene_theorist").default_model != \
        role_registry.get("semantic_compiler").default_model


# ── the prompt ───────────────────────────────────────────────────────────────

def test_the_prompt_reaches_the_model_verbatim_and_labelled_as_the_person_s():
    built = build_prompt(PROMPT, IMAGES)
    assert PROMPT in built
    assert "verbatim" in built
    assert "Do not answer it" in built


def test_the_block_kinds_are_sent_as_a_closed_set_rather_than_described():
    built = build_prompt(PROMPT, IMAGES)
    for kind in contracts.closed_set("reading_block_kinds"):
        assert f'"{kind}"' in built


def test_the_synthesis_prompt_says_the_images_are_not_being_shown_again():
    built = build_synthesis_prompt(PROMPT, [(IMAGES[0], "a reading"), (IMAGES[1], "another")])
    assert "SEPARATELY" in built
    assert "not being shown them again" in built


# ── replay ───────────────────────────────────────────────────────────────────

def test_a_frozen_payload_parses_into_a_reading_with_every_block_kind():
    result = FrozenSceneTheorist(CLEAN_PAYLOAD).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.available
    assert result.reading.status == "interpretive"
    assert result.reading.source == "scene_theorist"
    assert {b.kind for b in result.reading.blocks} == set(ReadingBlockKind)
    assert result.refusals == ()


def test_a_replayed_reading_is_byte_identical_across_two_runs():
    a = FrozenSceneTheorist(CLEAN_PAYLOAD).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    b = FrozenSceneTheorist(CLEAN_PAYLOAD).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert a.reading.model_dump(mode="json") == b.reading.model_dump(mode="json")


def test_the_replay_receipt_hashes_what_it_replayed_and_says_no_call_was_made():
    result = FrozenSceneTheorist(CLEAN_PAYLOAD).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    receipt = result.reading.provenance
    assert receipt.role == ROLE
    assert receipt.call_topology is CallTopology.REPLAY
    assert receipt.call_count == 0
    assert len(receipt.raw_response_sha256) == 1
    assert "no network call was made" in " ".join(receipt.notes)


# ── geometry is refused, not stripped ────────────────────────────────────────

def test_a_block_carrying_a_bounding_box_is_dropped_and_named():
    payload = {"reading": "a reading",
               "blocks": [{"kind": "part", "text": "a central void", "bbox": [0, 0, 4, 4]},
                          {"kind": "part", "text": "an outer wall"}]}
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert [b.text for b in result.reading.blocks] == ["an outer wall"]
    kinds = [r.kind for r in result.refusals]
    assert CompilerRefusalKind.GEOMETRY_IN_A_READING in kinds
    assert "bbox" in result.refusals[0].what
    assert "a central void" in " ".join(result.refusals[0].detail)


def test_the_dropped_block_is_recorded_rather_than_silently_cleaned_up():
    """A stripped key is a model authoring geometry, silently. The count of these is the observable
    that says whether the reading prompt is holding."""
    payload = {"blocks": [{"kind": "part", "text": "x", "mask_rle": {"size": [4, 4]}},
                          {"kind": "part", "text": "y", "confidence": 0.9}]}
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.reading.blocks == []
    assert len([r for r in result.refusals
                if r.kind is CompilerRefusalKind.GEOMETRY_IN_A_READING]) == 2


def test_geometry_nested_deep_inside_a_block_is_still_found():
    payload = {"blocks": [{"kind": "part", "text": "x",
                           "detail": {"where": {"polygon": [[0, 0], [1, 1]]}}}]}
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.reading.blocks == []
    assert result.refusals[0].what == "polygon"


def test_geometry_at_the_top_level_is_refused_and_the_prose_survives():
    payload = {"reading": "a reading", "region_id": "r1",
               "blocks": [{"kind": "part", "text": "a central void"}]}
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.reading.text == "a reading"
    assert [b.text for b in result.reading.blocks] == ["a central void"]
    assert result.refusals[0].kind is CompilerRefusalKind.GEOMETRY_IN_A_READING
    assert result.refusals[0].what == "region_id"


def test_a_reading_block_has_nowhere_for_a_coordinate_to_land():
    """The refusal is the RECORD; the allowlist is the wall. Even with the refusal deleted, a
    `ReadingBlock` declares four fields and none of them is a place to put a number about pixels."""
    declared = set(ReadingBlock.model_fields)
    assert declared == {"block_id", "kind", "text", "image_refs"}
    assert not declared & contracts.forbidden_geometry_keys()


# ── invented kinds and dangling images ───────────────────────────────────────

def test_an_invented_block_kind_is_refused_by_name_rather_than_coerced():
    payload = {"blocks": [{"kind": "vibe", "text": "it feels grand"},
                          {"kind": "part", "text": "a column"}]}
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert [b.text for b in result.reading.blocks] == ["a column"]
    refused = result.refusals[0]
    assert refused.kind is CompilerRefusalKind.UNKNOWN_READING_BLOCK_KIND
    assert refused.what == "vibe"


def test_an_image_the_corpus_does_not_hold_is_dropped_and_the_block_is_kept():
    payload = {"blocks": [{"kind": "part", "text": "a column", "images": ["p1", "p9"]}]}
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.reading.blocks[0].image_refs == ["p1"]
    assert result.refusals[0].kind is CompilerRefusalKind.DANGLING_REFERENCE
    assert result.refusals[0].what == "p9"


def test_identical_blocks_are_merged_and_their_image_references_unioned():
    payload = {"blocks": [{"kind": "part", "text": "a column", "images": ["p1"]},
                          {"kind": "part", "text": "A  Column ", "images": ["p2"]}]}
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert len(result.reading.blocks) == 1
    assert result.reading.blocks[0].image_refs == ["p1", "p2"]
    assert "merged" in " ".join(result.notes)


# ── silence is an empty reading ──────────────────────────────────────────────

def test_a_non_object_payload_produces_an_empty_reading_and_a_named_refusal():
    result = FrozenSceneTheorist("I am afraid I cannot help with that").read(
        PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.reading.text == ""
    assert result.reading.blocks == []
    assert not result.available
    assert result.refusals[0].kind is CompilerRefusalKind.UNPARSEABLE_MODEL_OUTPUT


def test_an_empty_but_valid_payload_is_kept_as_an_empty_reading_and_says_so():
    result = FrozenSceneTheorist({"reading": "", "blocks": []}).read(
        PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.available          # the model answered; it answered with nothing
    assert "NOT replaced by a default" in " ".join(result.notes)


def _canned_readings_in(source: str) -> list:
    """Module-level names bound to a mapping that has the shape of a reading.

    A canned reading has to be WRITTEN somewhere to be returned, and in this package the only shape
    that could be returned is a payload with `blocks` or `reading` in it. Scanning for the shape
    rather than for a naming convention is what makes the scan hard to route around by renaming.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        keys = {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
        if keys & {"blocks", "reading"}:
            found.extend(t.id for t in node.targets if isinstance(t, ast.Name))
    return found


def test_no_module_in_this_package_holds_a_canned_reading():
    """The structural half of 'silence is an empty graph'. If a default reading existed anywhere,
    an unavailable theorist would eventually return it and nobody could tell it apart from a real
    one. The module's only prose about pictures is the SYSTEM prompt — instructions to a model."""
    package = Path(theorist_module.__file__).parent
    for path in sorted(package.glob("*.py")):
        assert _canned_readings_in(path.read_text(encoding="utf-8")) == [], path.name


def test_that_scan_can_fail():
    """The negative control. A scan that matches nothing is indistinguishable from a scan pointed
    at the wrong directory."""
    assert _canned_readings_in(
        'FALLBACK = {"reading": "the interior is grand", "blocks": []}\n') == ["FALLBACK"]


# ── the live path, with an injected client ───────────────────────────────────

def test_an_unavailable_theorist_returns_an_empty_reading_and_refuses_out_loud():
    theorist = ModelSceneTheorist(client=None)
    theorist._client_resolved = True          # no key, no client, no network
    result = theorist.read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert not result.available
    assert result.reading.provenance.call_topology is CallTopology.UNAVAILABLE
    assert result.reading.provenance.call_count == 0
    assert result.refusals[0].kind is CompilerRefusalKind.READING_UNAVAILABLE
    assert result.reading.text == ""


def test_no_images_means_no_call_and_a_state_of_its_own():
    """`text_only` rather than `unavailable`: 'there was no scene' and 'the model was down' are
    different facts and a caller should be able to branch on which."""
    theorist = ModelSceneTheorist(client=FakeClient(CLEAN_PAYLOAD))
    result = theorist.read(PROMPT, [], inquiry_id=INQUIRY)
    assert theorist.calls == 0
    assert result.reading.provenance.call_topology is CallTopology.TEXT_ONLY
    assert result.refusals[0].what == "no images"


def test_one_image_is_one_call_and_is_genuinely_a_single_joint_view():
    client = FakeClient(CLEAN_PAYLOAD)
    theorist = ModelSceneTheorist(client=client)
    result = theorist.read(PROMPT, IMAGES[:1], inquiry_id=INQUIRY)
    assert theorist.calls == 1
    assert result.reading.provenance.call_topology is CallTopology.SINGLE_JOINT_CALL
    parts = client.requests[0]["messages"][1]["content"]
    assert [p["type"] for p in parts] == ["text", "image_url"]
    assert parts[1]["image_url"]["url"] == "https://x.invalid/1.jpg"


def test_two_images_are_two_looks_and_a_synthesis_that_never_saw_them_together():
    client = FakeClient(CLEAN_PAYLOAD, CLEAN_PAYLOAD,
                        {"reading": "across them, the centring differs",
                         "blocks": [{"kind": "comparison", "text": "one is taller"}]})
    theorist = ModelSceneTheorist(client=client)
    result = theorist.read(PROMPT, IMAGES, inquiry_id=INQUIRY)

    assert theorist.calls == 3
    assert result.reading.provenance.call_topology is CallTopology.PER_IMAGE_THEN_SYNTHESIS
    assert result.reading.provenance.call_count == 3
    # Every image-bearing request carried EXACTLY ONE image.
    image_parts = [[p for p in r["messages"][1]["content"] if p.get("type") == "image_url"]
                   for r in client.requests if isinstance(r["messages"][1]["content"], list)]
    assert [len(p) for p in image_parts] == [1, 1]
    # The synthesis call is text only.
    assert isinstance(client.requests[2]["messages"][1]["content"], str)
    assert "not from a second look" in result.reading.text


def test_a_block_from_a_single_image_call_is_stamped_with_that_image():
    client = FakeClient({"reading": "r1", "blocks": [{"kind": "part", "text": "a void"}]},
                        {"reading": "r2", "blocks": [{"kind": "part", "text": "a wall"}]},
                        {"reading": "", "blocks": []})
    result = ModelSceneTheorist(client=client).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    by_text = {b.text: b.image_refs for b in result.reading.blocks}
    assert by_text["a void"] == ["p1"]
    assert by_text["a wall"] == ["p2"]


def test_one_failed_image_leaves_the_others_read_and_the_absence_named():
    client = FakeClient(RuntimeError("boom"),
                        {"reading": "r2", "blocks": [{"kind": "part", "text": "a wall"}]},
                        {"reading": "", "blocks": []})
    result = ModelSceneTheorist(client=client).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert [b.text for b in result.reading.blocks] == ["a wall"]
    assert any(r.what == "p1" and r.kind is CompilerRefusalKind.READING_UNAVAILABLE
               for r in result.refusals)


def test_every_image_failing_is_unavailable_rather_than_an_empty_reading():
    client = FakeClient(RuntimeError("boom"), RuntimeError("boom"))
    result = ModelSceneTheorist(client=client).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert not result.available
    assert len(result.refusals) == 2


def test_a_bounded_sweep_names_the_images_it_did_not_read():
    images = [ImageRef(post_id=f"p{i}", image_ref=f"https://x.invalid/{i}.jpg") for i in range(5)]
    client = FakeClient(*([{"reading": "r", "blocks": []}] * 5))
    theorist = ModelSceneTheorist(client=client, max_images=2)
    result = theorist.read(PROMPT, images, inquiry_id=INQUIRY)
    assert theorist.calls == 3                     # two images, one synthesis
    assert "p2, p3, p4" in " ".join(result.notes)


def test_the_receipt_does_not_pretend_the_url_is_an_image_fingerprint():
    client = FakeClient(CLEAN_PAYLOAD)
    result = ModelSceneTheorist(client=client).read(PROMPT, IMAGES[:1], inquiry_id=INQUIRY)
    assert result.reading.provenance.image_sha256 == {}
    assert "no image bytes passed through this process" in \
        " ".join(result.reading.provenance.notes)


def test_the_reasoning_block_is_suppressed_the_way_vision_service_documents():
    client = FakeClient(CLEAN_PAYLOAD)
    ModelSceneTheorist(client=client).read(PROMPT, IMAGES[:1], inquiry_id=INQUIRY)
    assert client.requests[0]["reasoning_effort"] == "none"
    assert client.requests[0]["response_format"] == {"type": "json_object"}


def test_unparseable_json_from_a_live_call_is_a_refusal_and_not_a_retry():
    """No re-prompt loop, for PLANNER-001's reason: looping until something parses searches for an
    answer that validates rather than one that is true."""
    client = FakeClient("not json at all")
    theorist = ModelSceneTheorist(client=client)
    result = theorist.read(PROMPT, IMAGES[:1], inquiry_id=INQUIRY)
    assert theorist.calls == 1
    assert not result.available
    assert result.refusals[0].kind is CompilerRefusalKind.READING_UNAVAILABLE


def test_a_reading_cut_off_by_the_output_budget_says_so_on_its_receipt():
    """A reading that stopped on the budget and still parsed is a SHORT reading, and a short
    reading is indistinguishable from a picture with little in it unless something says which.
    Found by the live rehearsal, not by reading the adapter."""
    theorist = ModelSceneTheorist(client=TruncatingClient(CLEAN_PAYLOAD))
    result = theorist.read(PROMPT, IMAGES[:1], inquiry_id=INQUIRY)
    assert theorist.truncated_calls == 1
    assert theorist.last_finish_reason == "length"
    notes = " ".join(result.reading.provenance.notes)
    assert "stopped on the output budget" in notes
    assert "not evidence that there was little to see" in notes


def test_a_reading_that_finished_normally_carries_no_truncation_note():
    theorist = ModelSceneTheorist(client=FakeClient(CLEAN_PAYLOAD))
    result = theorist.read(PROMPT, IMAGES[:1], inquiry_id=INQUIRY)
    assert theorist.truncated_calls == 0
    assert "output budget" not in " ".join(result.reading.provenance.notes)


@pytest.mark.parametrize("payload", [CLEAN_PAYLOAD, {"blocks": []}, "junk"])
def test_no_reading_ever_carries_a_status_other_than_interpretive(payload):
    result = FrozenSceneTheorist(payload).read(PROMPT, IMAGES, inquiry_id=INQUIRY)
    assert result.reading.status == "interpretive"
