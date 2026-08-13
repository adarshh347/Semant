"""
HARNESS-002A — the contract is canonical, and the Python enums are how Python reads it.

The whole reason `contracts/semantic-inquiry-graph.v1.json` exists rather than a module of Python
constants is that more than one consumer will eventually need the vocabulary. That only pays off if
a divergence is loud, so every closed set is pinned here IN ORDER — set equality would let a
reordered `claim_kinds` pass while a UI rendering them in contract order silently rearranged
itself.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.schemas.inquiry import DemandKind
from backend.schemas.semantic_compilation import (READABLE_SCHEMA_VERSIONS, SCHEMA_VERSION,
                                                  SCHEMA_VERSION_V1, SCHEMA_VERSION_V2,
                                                  AtomKind, AtomAuthor, BatchBoundaryReason,
                                                  DispositionKind, ItemDispositionKind,
                                                  DissolutionPass, PassOutcome, SourceUnitKind,
                                                  CallTopology, CapabilityClass,
                                                  ClaimEdgeKind, ClaimKind, ClaimStatus,
                                                  CompilerRefusalKind, DecisionKind,
                                                  FORBIDDEN_INITIAL_STATUSES, GroundForm,
                                                  ImageScope, ReadingBlockKind, SourceType,
                                                  _FORBIDDEN_DEMANDS, _REQUIRED_DEMANDS)
from backend.services.inquiry.contracts import ContractError
from backend.services.semantic_compilation import contracts, ids


def _values(enum_cls) -> tuple:
    return tuple(m.value for m in enum_cls)


def test_the_contract_loads_and_declares_the_version_this_code_enforces():
    data = contracts.graph_contract()
    assert data["schema_version"] == SCHEMA_VERSION == "semantic-inquiry-graph.v2"


@pytest.mark.parametrize("set_name,enum_cls", [
    ("claim_kinds", ClaimKind),
    ("claim_edge_kinds", ClaimEdgeKind),
    ("epistemic_demands", DemandKind),
    ("claim_statuses", ClaimStatus),
    ("image_scopes", ImageScope),
    ("source_types", SourceType),
    ("capability_classes", CapabilityClass),
    ("ground_forms", GroundForm),
    ("reading_block_kinds", ReadingBlockKind),
    ("decision_kinds", DecisionKind),
    ("refusal_kinds", CompilerRefusalKind),
    ("call_topologies", CallTopology),
])
def test_every_closed_set_matches_its_enum_in_order(set_name, enum_cls):
    assert contracts.closed_set(set_name) == _values(enum_cls), (
        f"{set_name} in the contract and {enum_cls.__name__} in Python have diverged")


def test_the_claim_kinds_are_exactly_the_thirteen_the_master_plan_pins():
    assert contracts.closed_set("claim_kinds") == (
        "entity", "attribute", "spatial_relation", "topology", "pattern_or_sequence", "field",
        "hierarchy", "comparison", "historical_or_sourced", "causal_hypothesis", "interpretation",
        "generative_rule", "unknown")


def test_the_demand_vocabulary_is_lane_As_and_is_not_respelled():
    """`DemandKind` comes from `backend.schemas.inquiry`. A second five-value enum meaning the same
    thing is how `measurable` quietly becomes `measured` one lane over."""
    assert DemandKind.__module__ == "backend.schemas.inquiry"
    assert contracts.closed_set("epistemic_demands") == _values(DemandKind)


def test_the_two_forbidden_initial_statuses_are_absent_from_the_status_enum():
    """Absent rather than present-and-refused. An enum that can express a measured claim is one a
    parser can be talked into constructing."""
    assert contracts.closed_set("forbidden_initial_statuses") == FORBIDDEN_INITIAL_STATUSES
    for forbidden in FORBIDDEN_INITIAL_STATUSES:
        assert forbidden not in _values(ClaimStatus)
        with pytest.raises(ValueError):
            ClaimStatus(forbidden)


def test_the_id_prefixes_are_the_ones_ids_py_mints():
    assert contracts.id_prefixes() == ids.PREFIXES


def test_the_demand_constraints_table_matches_the_contract():
    declared = contracts.graph_contract()["demand_constraints"]
    for kind, forbidden in _FORBIDDEN_DEMANDS.items():
        row = declared[kind.value]
        assert sorted(row["forbidden_demands"]) == sorted(d.value for d in forbidden)
        assert row["why"].strip()
    for kind, required in _REQUIRED_DEMANDS.items():
        row = declared[kind.value]
        assert sorted(row["required_demands"]) == sorted(d.value for d in required)
    assert declared["comparison"]["forbidden_image_scopes"] == [ImageScope.ONE_IMAGE.value]


def test_every_capability_class_is_described_and_nothing_extra_is():
    described = contracts.capability_class_info()
    assert sorted(described) == sorted(_values(CapabilityClass))
    for name, row in described.items():
        assert row["asks_for"].strip(), name
        assert row["typical_grounds"], name
        for ground in row["typical_grounds"]:
            assert ground in _values(GroundForm)


def test_the_two_classes_that_can_never_settle_a_measurement_say_so_in_the_contract():
    described = contracts.capability_class_info()
    assert "never_settles" in described["semantic_reading"]
    assert "never_settles" in described["external_source"]
    for name, row in described.items():
        if name in {"semantic_reading", "external_source"}:
            continue
        assert "never_settles" not in row, f"{name} claims it can never settle a measurement"


def test_the_laws_are_uniquely_identified_and_each_says_why():
    laws = contracts.laws()
    assert len(laws) >= 10
    assert len({law["id"] for law in laws}) == len(laws)
    for law in laws:
        assert law["kind"] in {"error", "allow"}
        assert law["message"].strip() and law["why"].strip()


def test_an_undeclared_closed_set_raises_rather_than_returning_nothing():
    """An empty vocabulary permits nothing, which downstream reads as 'the model proposed nothing
    valid' rather than 'the code asked for a set that does not exist'."""
    with pytest.raises(ContractError):
        contracts.closed_set("colours_of_the_sky")


# ── the geometry scan ────────────────────────────────────────────────────────

def test_the_forbidden_geometry_keys_are_lowercase_and_cover_the_obvious_authorings():
    keys = contracts.forbidden_geometry_keys()
    assert keys == frozenset(k.lower() for k in keys)
    for expected in ("mask_rle", "bbox", "polygon", "region_id", "confidence", "coordinates"):
        assert expected in keys


def test_the_geometry_scan_reaches_a_key_buried_inside_a_model_payload():
    """A model told not to output a box at the top level puts one inside `claims[0].evidence` on the
    next attempt. A shallow check passes it."""
    payload = {"claims": [{"text": "a column stands centrally",
                           "evidence": {"bbox": [0, 0, 10, 10]}}]}
    assert contracts.geometry_keys_in(payload) == ["bbox"]


def test_the_geometry_scan_finds_nothing_in_an_honest_reading():
    payload = {"reading": "the vaulting gathers toward the centre",
               "blocks": [{"kind": "organization", "text": "a radial arrangement"}]}
    assert contracts.geometry_keys_in(payload) == []


def test_the_geometry_scan_reports_several_keys_sorted_and_deduplicated():
    payload = {"a": {"mask_rle": 1, "confidence": 0.9},
               "b": [{"confidence": 0.4}, {"region_id": "r1"}]}
    assert contracts.geometry_keys_in(payload) == ["confidence", "mask_rle", "region_id"]


def test_the_geometry_scan_survives_a_self_referential_payload():
    """A cycle cannot come from a model's JSON, but a test handing one in should get a refusal
    rather than a stack overflow."""
    payload: dict = {"blocks": []}
    payload["blocks"].append(payload)
    assert contracts.geometry_keys_in(payload) == []


def test_unknown_values_reports_the_model_s_invention_verbatim():
    assert contracts.unknown_values(["extent", "bounding_box"], "capability_classes") == \
        ["bounding_box"]
    assert contracts.unknown_values(["extent", "depth"], "capability_classes") == []


# ── the module keeps no clock and no dice ────────────────────────────────────

def test_ids_imports_nothing_that_could_make_two_replays_differ():
    """A structural scan, plus its own negative control below. `ids.py` may import hashlib, re and
    typing and nothing else: `random`, `time`, `uuid` and `datetime` each break replay, and each is
    the sort of import that arrives in a helper nobody re-reads."""
    source = Path(ids.__file__).read_text(encoding="utf-8")
    imported = {n.name.split(".")[0] for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Import) for n in node.names}
    imported |= {(node.module or "").split(".")[0] for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.ImportFrom)}
    assert imported <= {"__future__", "hashlib", "re", "typing"}, sorted(imported)


def test_that_scan_can_fail(tmp_path):
    """The negative control [[FINDING-wave4-pixel-audit-ci]] asks for: a scan that matches nothing
    is indistinguishable from a scan pointed at the wrong file."""
    decoy = tmp_path / "decoy.py"
    decoy.write_text("import uuid\nimport hashlib\n", encoding="utf-8")
    imported = {n.name.split(".")[0]
                for node in ast.walk(ast.parse(decoy.read_text(encoding="utf-8")))
                if isinstance(node, ast.Import) for n in node.names}
    assert not imported <= {"__future__", "hashlib", "re", "typing"}


# ── v2, and what it may not break ────────────────────────────────────────────

@pytest.mark.parametrize("set_name,enum_cls", [
    ("source_unit_kinds", SourceUnitKind),
    ("atom_kinds", AtomKind),
    ("atom_authors", AtomAuthor),
    ("coverage_dispositions", DispositionKind),
    ("dissolution_passes", DissolutionPass),
    ("pass_outcomes", PassOutcome),
    ("batch_boundary_reasons", BatchBoundaryReason),
    ("item_dispositions", ItemDispositionKind),
])
def test_every_v2_closed_set_is_pinned_in_order(set_name, enum_cls):
    assert contracts.closed_set(set_name) == _values(enum_cls)


def test_v1_is_still_on_disk_and_still_loadable():
    """A stored v1 graph is explained by v1's vocabulary. Deleting the file would leave every
    session written before this lane described by a contract that no longer exists."""
    v1 = contracts.graph_contract_v1()
    assert v1["schema_version"] == SCHEMA_VERSION_V1
    assert SCHEMA_VERSION_V1 in READABLE_SCHEMA_VERSIONS


def test_v2_is_a_superset_of_v1_rather_than_a_rewrite():
    """Checked against the file, not promised in prose. A v1 value quietly dropped would make every
    stored graph carrying it unreadable by the code that claims to read v1."""
    v1, v2 = contracts.graph_contract_v1(), contracts.graph_contract()
    for name, members in (v1["closed_sets"]).items():
        assert name in v2["closed_sets"], f"v2 dropped the closed set {name!r}"
        missing = [m for m in members if m not in v2["closed_sets"][name]]
        assert not missing, f"v2 dropped {missing} from {name!r}"
    for name, prefix in (v1["id_prefixes"]).items():
        assert v2["id_prefixes"].get(name) == prefix, f"v2 changed the {name!r} id prefix"


def test_v2_declares_the_laws_v1_had_and_the_ones_the_ledger_needs():
    v1_ids = {law["id"] for law in contracts.graph_contract_v1()["laws"]}
    v2_ids = {law["id"] for law in contracts.laws()}
    assert v1_ids <= v2_ids, f"v2 dropped the law(s) {sorted(v1_ids - v2_ids)}"
    for required in ("every-source-unit-has-exactly-one-disposition", "every-atom-is-anchored",
                     "a-user-statement-stays-the-users", "the-architect-does-not-look",
                     "a-parsed-response-is-not-a-successful-one", "one-repair-and-no-silent-retry"):
        assert required in v2_ids


def test_the_atom_vocabulary_maps_onto_the_claim_vocabulary_completely():
    """Every atom kind has a default claim kind, and every default is a real claim kind. A gap here
    would strand a whole category of atom with nothing the architect could build from it."""
    mapping = contracts.atom_kind_to_claim_kind()
    assert set(mapping) == {k.value for k in AtomKind}
    assert set(mapping.values()) <= set(contracts.closed_set("claim_kinds"))


def test_the_id_prefixes_in_the_contract_are_the_ones_the_minter_uses():
    assert contracts.id_prefixes() == ids.PREFIXES
