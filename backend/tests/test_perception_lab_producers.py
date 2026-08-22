"""
PERCEPTUAL-FORMS-001H — the producer catalogue, and the three absences it refuses to call one.

WHY THIS MODULE EXISTS SEPARATELY FROM THE CAPABILITY SUITE. `capability_catalogue` answers "is
this adapter running here", which is the right question about an adapter and the wrong one about a
form: ten of the nineteen forms have no adapter at all, are computed by pure Python, and are still
unwritable — for a reason that has nothing to do with a model. The old table could not say that.

WHAT IS HELD TO ACCOUNT HERE:

    the three blocks      `deferred_form`, `no_operation` and `capability_unavailable` are three
                          different next actions and never collapse into one word
    the kinds             a topology organ is `code`, a person is `human`, SAM is `model`. Calling
                          arithmetic a model would make somebody ask which checkpoint measured
                          their containment
    the revisions         a model names its pin, a pure producer names its lane revision, a person
                          names neither — and that is the answer rather than a gap
    SAM 3                 configured through `SAM3_WEIGHTS` and never discovered from a cache, and
                          the three ways it can be absent are three different sentences
    the mapping           every producible form names a producer that exists and is importable

PURE. No database, no network, no model loaded, no route.
"""
from __future__ import annotations

import ast
import importlib
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.schemas.perception_lab import CapabilityState
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import producers as P

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = P.catalogue()
BY_FORM = {f["form"]: f for f in CATALOGUE["forms"]}


def test_the_catalogue_covers_all_nineteen_registered_forms():
    assert set(BY_FORM) == set(D.forms())
    assert CATALOGUE["counts"]["registered"] == 19


def test_only_three_forms_can_become_an_artifact_and_the_catalogue_says_which():
    """The fact that surprises people. Sixteen forms are registered, reviewable and renderable and
    cannot be written as artifacts, because an artifact names the operation that produced it and
    no operation declares them."""
    writable = sorted(k for k, f in BY_FORM.items() if f["writable_as_artifact"])
    assert writable == ["extent.hard_mask", "topology.negative_space_field",
                        "topology.pair_relation"]
    assert CATALOGUE["counts"]["writable_as_artifact"] == 3


@pytest.mark.parametrize("form_key", sorted(D.forms()))
def test_every_form_that_cannot_be_written_says_which_absence_it_is(form_key):
    entry = BY_FORM[form_key]
    definition = D.form(form_key)
    if entry["writable_as_artifact"]:
        assert entry["blocked_by"] == []
        return
    assert entry["blocked_by"], form_key
    assert (P.DEFERRED_FORM in entry["blocked_by"]) is (not definition.producible)
    assert (P.NO_OPERATION in entry["blocked_by"]) is (not definition.has_producer)
    assert entry["note"], "a block with no sentence beside it is the table this one replaces"


def test_the_three_blocks_are_three_different_next_actions():
    """`deferred_form` waits for a phase; `no_operation` waits for an operation; the third waits
    for a checkpoint. A surface that showed one word for all three would send every person to the
    same wrong place."""
    deferred = BY_FORM["extent.soft_field"]
    unoperated = BY_FORM["extent.boundary_rings"]
    assert P.DEFERRED_FORM in deferred["blocked_by"]
    assert deferred["blocked_by"] != unoperated["blocked_by"]
    assert unoperated["blocked_by"] == [P.NO_OPERATION]
    assert unoperated["can_be_produced_here"] is True, (
        "producible and unartifactable are two different questions, and this form answers yes "
        "to the first")


def test_a_pure_producer_is_never_reported_as_a_model():
    """Calling arithmetic a model would make somebody ask which checkpoint measured their
    containment, and there is no answer to that question."""
    for organ in ("nestedness_organ", "adjacency_organ", "mask_arithmetic",
                  "distance_transform", "occlusion_organ"):
        entry = P.adapter_identity(organ)
        assert entry.kind is P.CODE, organ
        assert entry.model is None and entry.state is CapabilityState.AVAILABLE
        assert entry.revision == P.TOPOLOGY_REVISION


def test_a_person_is_a_producer_with_no_model_and_no_revision():
    hand = P.adapter_identity("human")
    assert (hand.kind, hand.model, hand.revision) == (P.HUMAN, None, None)
    assert hand.state is CapabilityState.AVAILABLE, "a hand cannot be unavailable"


def test_every_model_producer_names_its_checkpoint_and_its_pin_or_says_why_it_cannot():
    for key in P.MODEL_ADAPTERS:
        entry = P.adapter_identity(key)
        assert entry.kind is P.MODEL, key
        if entry.state is CapabilityState.AVAILABLE:
            assert entry.model, f"{key} is running and does not say what it is"
            assert entry.reason is None
        else:
            assert entry.reason, f"{key} is unavailable and does not say why"
            assert entry.remedy, f"{key} is unavailable and names no next action"


def test_a_pure_producer_carries_the_revision_of_the_lane_that_wrote_it():
    for form_key, (module, function) in P.CODE_PRODUCERS.items():
        entry = [p for p in P.producers_for(form_key) if p.kind is P.CODE
                 and p.key.endswith(function)]
        assert entry, form_key
        assert entry[0].revision == P.CODE_REVISIONS[module]
        assert entry[0].model is None, "a pure derivation has no checkpoint to name"


@pytest.mark.parametrize("form_key, module_and_function", sorted(P.CODE_PRODUCERS.items()))
def test_every_producible_form_names_a_producer_that_exists(form_key, module_and_function):
    """A catalogue entry pointing at a function nobody wrote is a promise, not a producer."""
    module, function = module_and_function
    imported = importlib.import_module(f"backend.services.{module}")
    assert hasattr(imported, function), f"{module}.{function}"
    D.form(form_key)


def test_the_code_producer_table_covers_every_form_this_repository_can_compute():
    """Both directions. A form with a producer this table omits would be unreachable from the
    surface; an entry for a form nobody registered would be a producer of nothing."""
    assert set(P.CODE_PRODUCERS) <= set(D.forms())
    computable = {k for k in D.forms()
                  if k not in ("extent.hard_mask", "extent.soft_field",
                               "topology.pair_relation", "topology.contact_locus",
                               "topology.intersection_area", "topology.clearance_path",
                               "topology.negative_space_field")}
    assert set(P.CODE_PRODUCERS) == computable


# ── SAM 3 is configured, never discovered ────────────────────────────────────


def test_sam3_reads_one_environment_variable_and_looks_in_no_cache():
    """A route that fetched 3.2 GiB mid-request is not a fallback, it is an outage. The service
    reads `SAM3_WEIGHTS` and checks the file exists, and nothing in it reaches for a hub cache —
    read off the source rather than promised in a docstring."""
    source = (REPO_ROOT / "backend" / "services" / "sam3_concept_service.py").read_text("utf-8")
    tree = ast.parse(source)
    reached: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("hf_hub_download", "snapshot_download", "from_pretrained",
                                  "expanduser"):
                reached.append(node.func.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("hf_hub_download", "snapshot_download"):
                reached.append(node.func.id)
    assert reached == [], f"the SAM 3 service reaches for {reached}"
    assert "HF_HOME" not in source and ".cache" not in source


@pytest.mark.parametrize("configured, expect", [
    ("", "is unset"),
    ("/nowhere/sam3.pt", "and nothing is there"),
])
def test_sam3_says_which_of_the_three_absences_it_is(monkeypatch, configured, expect):
    """`unavailable` on its own once sent a person looking for a missing download that was
    already on the disk. Configuration is not capability, and the answer says which."""
    from backend.services import sam3_concept_service as svc
    monkeypatch.setenv(svc.WEIGHTS_ENV, configured)
    entry = P.adapter_identity("sam3_concept")
    assert entry.state is CapabilityState.UNAVAILABLE
    assert expect in entry.reason
    assert svc.WEIGHTS_ENV in entry.remedy
    assert entry.model == svc.CHECKPOINT, "it still says what it would have run"


def test_sam3_absence_is_never_reported_as_an_empty_result():
    """The rule the adapter was written for: a missing checkpoint reported as "no drapery in this
    picture" would be a measurement nobody made, about a picture nobody looked at."""
    entry = P.adapter_identity("sam3_concept")
    assert entry.state in (CapabilityState.AVAILABLE, CapabilityState.UNAVAILABLE)
    if entry.state is CapabilityState.UNAVAILABLE:
        assert "unset" in entry.reason or "nothing is there" in entry.reason \
            or "does not import" in entry.reason


# ── the registry's opinion wins ──────────────────────────────────────────────


def test_a_live_registry_overrides_this_module_and_the_reason_survives():
    """This module asks the service modules, which resolve checkpoints against the process's
    working directory. A route holding a live registry knows what actually answered on this
    machine, and where the two disagree the registry is right."""
    forced = P.producers_for("extent.hard_mask",
                             states={"yolo_sam2_auto": CapabilityState.UNAVAILABLE})
    entry = [p for p in forced if p.key == "yolo_sam2_auto"][0]
    assert entry.state is CapabilityState.UNAVAILABLE
    assert entry.model, "the identity survives the override; only the state changes"


def test_a_model_lane_c_refused_appears_with_its_verdict_and_never_as_available():
    density = BY_FORM["extent.density_field"]
    counter = [p for p in density["producers"] if p["key"] == "density_counter"][0]
    assert counter["state"] == "unavailable"
    assert counter["admission"] == "reject"
    assert "exemplars" in counter["reason"]
    partition = BY_FORM["extent.visible_inferred_partition"]
    deferred = {p["key"]: p["admission"] for p in partition["producers"]
                if p["admission"] is not None}
    assert deferred == {"pix2gestalt": "defer", "amodal_sam": "defer"}


def test_the_catalogue_carries_the_renderers_and_the_absence_sentence_for_every_form():
    """A surface deciding what to draw and what to say when there is nothing reads both from
    here, so neither is retyped beside a component."""
    for form_key, entry in BY_FORM.items():
        definition = D.form(form_key)
        assert [p["kind"] for p in entry["renderer_projections"]] == \
            [p.kind for p in definition.renderer_projections]
        assert entry["absence"]["examined_field"] == definition.absence.examined_field
        assert entry["absence"]["empty_means"] == definition.absence.empty_means


def test_this_module_loads_no_model_to_answer_any_of_it():
    tree = ast.parse((REPO_ROOT / "backend" / "services" / "perception_lab" / "producers.py")
                     .read_text("utf-8"))
    top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = [a.name for n in top_level if isinstance(n, ast.Import) for a in n.names]
    names += [n.module for n in top_level if isinstance(n, ast.ImportFrom) and n.module]
    for banned in ("torch", "ultralytics", "transformers", "backend.database"):
        assert not any(n == banned or n.startswith(banned + ".") for n in names), banned
