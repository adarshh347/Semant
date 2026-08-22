"""
PERCEPTUAL-FORMS-001H — producing a form directly, and the promotion that has nowhere to happen.

WHAT THIS MODULE HOLDS TO. Twelve forms can be computed from records this laboratory already
holds. None of them can become an artifact, because no operation declares them and
`ArtifactIdentity.operation` is required. So a derivation is a sixth record kind with its own
store, and the tests below are about the three things that could quietly go wrong:

    the payload      every derivable form produces one that validates as the variant it claims
    the honesty      a deferred form carries its verdict; an unresolvable input refuses; an
                     undeclared parameter is dropped and RECORDED; a hypothesis is never invented
    the door         nothing here can promote anything, and the proof is the import graph and the
                     store's public surface rather than a sentence

PURE. No database, no network, no model, no adapter, no image.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.schemas.perception_lab import (EpistemicStatus, PerceptualArtifact, RefusalCode)
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab import derivations as DV
from backend.services.perception_lab import producers as PR
from backend.services.perception_lab.derivation_store import (InMemoryDerivationStore,
                                                              MongoDerivationStore)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "research" / "perception_lab" / "fixtures" / "topology_forms"
CONTROLS = json.loads(
    (REPO_ROOT / "research" / "perception_lab" / "benchmarks" / "controls" / "manifest.json")
    .read_text("utf-8"))["controls"]

FOREST = "art_forms_forest"


def artifact(name: str) -> PerceptualArtifact:
    return PerceptualArtifact.model_validate(
        json.loads((FIXTURES / f"{name}.json").read_text("utf-8")))


def derive(form_key: str, *, artifacts=None, parameters=None, name: str = "extent-set.forest"):
    supplied = artifacts if artifacts is not None else [artifact(name)]
    digest = supplied[0].provenance.source_image_digest
    return DV.derive(form_key, session_id="labs_h", artifacts=supplied, parameters=parameters,
                     source_image_digest=digest, derivation_id=f"der_{form_key}",
                     now="2026-08-22T09:00:00Z")


LINKS = {"links": [{"child": f"{FOREST}#court"},
                   {"child": f"{FOREST}#fountain", "parent": f"{FOREST}#court"},
                   {"child": f"{FOREST}#basin", "parent": f"{FOREST}#fountain"}]}
GROUPING = {"groupings": [{"id": "one_thing",
                           "members": [f"{FOREST}#fountain", f"{FOREST}#basin"],
                           "grounds": [{"kind": "shape_continuity", "detail": "one basin",
                                        "attributed_to": "geometry"}]}]}
READINGS = {"question": "is the basin part of the fountain?",
            "readings": [{"id": "a", "weight": 0.5, "members": [f"{FOREST}#fountain"]},
                         {"id": "b", "weight": 0.5,
                          "members": [f"{FOREST}#fountain", f"{FOREST}#basin"]}]}
PARAMETERS = {
    "extent.boundary_rings": None, "extent.hole_set": None,
    "extent.fragment_set": {"measure_separation": False},
    "extent.hierarchy": LINKS, "extent.fused_hypothesis": GROUPING,
    "extent.density_field": {"field_shape": [4, 4]},
    "extent.hypothesis_set": READINGS,
}
EXTENT_FORMS = sorted(PARAMETERS)


# ── every implemented form can be produced directly ──────────────────────────


@pytest.mark.parametrize("form_key", EXTENT_FORMS)
def test_every_extent_form_this_deployment_computes_produces_a_valid_payload(form_key):
    record = derive(form_key, parameters=PARAMETERS[form_key])
    definition = D.form(form_key)
    assert record.payload is not None, form_key
    assert record.payload_variant == definition.payload_variant
    from backend.schemas import perception_lab as S
    model = S.FORM_PAYLOAD_MODELS[definition.payload_variant]
    assert model.model_validate(record.payload).variant == definition.payload_variant


def test_the_twelve_derivable_forms_are_the_ones_the_producer_catalogue_names():
    """Two tables, one answer. A form the catalogue advertises and the runtime cannot compute
    would be a control that does nothing when pressed."""
    assert set(DV.derivable_forms()) == set(PR.CODE_PRODUCERS)
    assert set(DV.PRODUCERS) == set(DV.DECLARED)


def test_no_derivable_form_can_become_an_artifact_and_every_record_says_so():
    """The fact this whole record kind exists for. An artifact names the operation that produced
    it, and no operation declares any of these."""
    for form_key in EXTENT_FORMS:
        record = derive(form_key, parameters=PARAMETERS[form_key])
        assert record.writable_as_artifact is False, form_key
        assert not D.form(form_key).has_producer


def test_a_deferred_form_carries_its_payload_and_its_verdict():
    record = derive("extent.density_field", parameters={"field_shape": [4, 4]})
    assert record.producible is False
    assert record.payload is not None
    assert [r.code for r in record.refusals] == [RefusalCode.FORM_NOT_PRODUCIBLE]


def test_an_experimental_form_is_producible_and_still_not_an_artifact():
    record = derive("extent.hierarchy", parameters=LINKS)
    assert record.producible is True and record.writable_as_artifact is False
    assert record.refusals == []


# ── the person's decisions, and what happens without them ────────────────────


def test_nothing_here_invents_a_grouping():
    """A fusion with no proposed members is an empty hypothesis set with its count intact — the
    honest answer to "nobody grouped anything", and not the same as "no grouping was
    supportable"."""
    record = derive("extent.fused_hypothesis", parameters={"groupings": []})
    assert record.payload["hypotheses"] == []
    assert record.payload["fragments_considered"] == 5
    assert record.payload["alternatives_retained"] is True


def test_nothing_here_paints_an_inferred_region():
    record = derive("extent.visible_inferred_partition",
                    parameters={"of": f"{FOREST}#court", "parts": []})
    assert record.payload is None
    assert any(r.code is RefusalCode.MISSING_EXTENT_INPUTS for r in record.refusals)


def test_a_hypothesis_set_with_one_reading_is_refused_rather_than_resolved():
    record = derive("extent.hypothesis_set",
                    parameters={"question": "q",
                                "readings": [{"id": "a", "weight": 1.0,
                                              "members": [f"{FOREST}#court"]}]})
    assert record.payload["alternatives"] == []
    assert any(r.code is RefusalCode.UNSUPPORTED_FORM for r in record.refusals)


def test_a_grounding_from_an_unadmitted_model_never_reaches_the_payload():
    record = derive("extent.fused_hypothesis", parameters={"groupings": [{
        "id": "smuggled", "members": [f"{FOREST}#fountain", f"{FOREST}#basin"],
        "grounds": [{"kind": "appearance_continuity", "detail": "cosine 0.98",
                     "attributed_to": "model:pix2gestalt"}]}]})
    assert record.payload["hypotheses"] == []
    assert [o["reason"] for o in record.omitted] == ["ground_not_admitted", "no_ground_supplied"]


# ── parameters are dropped and recorded, never carried ───────────────────────


def test_an_undeclared_parameter_is_dropped_and_recorded_rather_than_carried():
    """The discipline `resolver.resolve` applies to a planner's proposal, applied to a person's
    form. A model that one day proposes a derivation gets the same treatment, and the attempt
    stays visible."""
    record = derive("extent.fragment_set",
                    parameters={"measure_separation": False, "mask_rle": {"size": [2, 2]},
                                "promote": True})
    assert sorted(p.name for p in record.dropped_parameters) == ["mask_rle", "promote"]
    assert record.parameters == {"measure_separation": False}
    assert all("does not declare it" in p.reason for p in record.dropped_parameters)


def test_every_instance_being_box_only_is_a_different_refusal_from_no_extent_set_at_all():
    """One sends a person to their selection and the other to the adapter that measured it."""
    doc = json.loads((FIXTURES / "extent-set.forest.json").read_text("utf-8"))
    for instance in doc["measurement"]["payload"]["instances"]:
        instance["mask_rle"] = None
        instance["box"] = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    doc["measurement"]["epistemic_basis"] = "box"
    doc["measurement"]["epistemic_status"] = "interpretive"
    with pytest.raises(DV.DerivationRefused) as caught:
        derive("extent.boundary_rings", artifacts=[PerceptualArtifact.model_validate(doc)])
    assert caught.value.refusal.missing == ["mask_rle"]
    assert "carries only a box" in caught.value.refusal.message


def test_a_box_only_instance_is_not_traced_and_is_not_silently_absent():
    doc = json.loads((FIXTURES / "extent-set.forest.json").read_text("utf-8"))
    doc["measurement"]["payload"]["instances"][0]["mask_rle"] = None
    doc["measurement"]["payload"]["instances"][0]["box"] = {"x": 0.1, "y": 0.1,
                                                           "w": 0.2, "h": 0.2}
    record = derive("extent.boundary_rings",
                    artifacts=[PerceptualArtifact.model_validate(doc)])
    assert [p.name for p in record.dropped_parameters] == [f"{FOREST}#court"]
    assert "no mask to derive from" in record.dropped_parameters[0].reason


# ── inputs that do not resolve refuse ────────────────────────────────────────


def test_a_form_with_no_supplied_input_refuses_and_names_the_form_it_reads():
    with pytest.raises(DV.DerivationRefused) as caught:
        derive("extent.hole_set", artifacts=[artifact("relations.forest")])
    refusal = caught.value.refusal
    assert refusal.code is RefusalCode.MISSING_EXTENT_INPUTS
    assert refusal.missing == list(D.form("extent.hole_set").accepted_input_forms)


def test_a_transition_needs_two_revisions_and_says_so():
    with pytest.raises(DV.DerivationRefused) as caught:
        derive("topology.transition", artifacts=[artifact("relations.revision-0")])
    assert "two revisions" in caught.value.refusal.message


def test_a_form_this_deployment_does_not_compute_is_refused_by_name():
    with pytest.raises(DV.DerivationRefused) as caught:
        derive("extent.soft_field")
    assert caught.value.refusal.code is RefusalCode.UNSUPPORTED_FORM


# ── the topology side ────────────────────────────────────────────────────────


def test_a_containment_tree_is_derived_from_relations_the_facade_measured():
    record = derive("topology.containment_tree", artifacts=[artifact("relations.forest")])
    assert record.payload["variant"] == "topology_containment_tree"
    assert record.payload["nodes"]
    assert record.organ.value == "topology"


def test_an_adjacency_graph_is_derived_from_the_same_relations():
    record = derive("topology.adjacency_graph", artifacts=[artifact("relations.piers")])
    assert record.payload["variant"] == "topology_adjacency_graph"
    assert record.producible is True


# ── nothing here promotes anything ───────────────────────────────────────────


def test_a_derivation_record_has_no_lifecycle_field_to_climb():
    """`PerceptualArtifact` carries one because an artifact can be kept, promoted or discarded.
    A derivation has no such ladder, and a `lifecycle` field would be the first rung."""
    fields = set(DV.LabDerivation.model_fields)
    for forbidden in ("lifecycle", "promoted", "canonical", "region_id", "post_id"):
        assert forbidden not in fields
    assert DV.LabDerivation.model_config["extra"] == "forbid"


def test_the_derivation_store_has_three_methods_and_none_of_them_is_canon():
    surface = {m for m in dir(InMemoryDerivationStore) if not m.startswith("_")}
    assert surface == {"put", "get", "for_session"}
    assert {m for m in dir(MongoDerivationStore) if not m.startswith("_")} == surface


def test_neither_module_can_reach_a_post_a_region_or_the_conductor():
    for name in ("derivations", "derivation_store"):
        path = REPO_ROOT / "backend" / "services" / "perception_lab" / f"{name}.py"
        tree = ast.parse(path.read_text("utf-8"))
        imported: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for banned in ("backend.routers", "backend.services.posts",
                       "backend.services.perception_lab.orchestrator",
                       "backend.services.perception_lab.adapters", "torch"):
            assert not any(i == banned or i.startswith(banned + ".") for i in imported), \
                f"{name} reaches {banned}"
    # NAMES, NOT PROSE. A docstring saying "nothing here promotes" is not a promotion, and a
    # substring search that cannot tell the two apart is a test that fails on its own writing.
    for module in (DV, __import__("backend.services.perception_lab.derivation_store",
                                  fromlist=["*"])):
        assert not [n for n in dir(module) if "promot" in n.lower()]


def test_the_lab_store_gained_no_door():
    """`LabStore` still has fifteen methods. A derivation gets its own store precisely so the
    conductor is not handed one it must not walk through."""
    from backend.services.perception_lab.store import LabStore
    methods = {m for m in dir(LabStore) if not m.startswith("_")}
    assert len(methods) == 15
    assert not any("derivation" in m for m in methods)


# ── the store round-trips ────────────────────────────────────────────────────


class FakeCollection:
    def __init__(self) -> None:
        self.documents: Dict[str, Dict[str, Any]] = {}

    def replace_one(self, query, document, upsert=False):
        self.documents[query["_id"]] = copy.deepcopy(document)

    def find_one(self, query):
        return copy.deepcopy(self.documents.get(query["_id"]))

    def find(self, query):
        found = [copy.deepcopy(d) for d in self.documents.values()
                 if d["session_id"] == query["session_id"]]

        class _Cursor(list):
            def sort(self, spec):
                return self
        return _Cursor(found)


def test_a_derivation_read_back_is_the_derivation_that_was_written():
    record = derive("extent.hole_set")
    for store in (InMemoryDerivationStore(), MongoDerivationStore(FakeCollection())):
        store.put(record)
        assert store.get(record.derivation_id) == record
        assert store.for_session("labs_h") == (record,)
        assert store.get("der_nobody") is None


def test_what_is_read_out_is_a_value_and_not_a_window_onto_state():
    store = InMemoryDerivationStore()
    store.put(derive("extent.hole_set"))
    first = store.get("der_extent.hole_set")
    first.parameters["mutated"] = True
    assert store.get("der_extent.hole_set").parameters == {}
