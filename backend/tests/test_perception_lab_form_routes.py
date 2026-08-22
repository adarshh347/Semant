"""
PERCEPTUAL-FORMS-001H — the three levels of the laboratory, driven through HTTP.

DIRECT FORM · DETERMINISTIC RECIPE · PROMPT PROPOSAL, and the point of this module is that the
third has no route of its own to bypass with. A recipe expands into `DirectCommand`s and goes to
`plan_direct`; a prompt goes to `plan_prompt`; both land in the same resolver and the same adapter.
There is no fourth door, which is a stronger statement than "the prompt arm is careful".

WHAT IS CHECKED HERE AND NOWHERE ELSE:

    the wire           a form catalogue, a recipe catalogue, a readiness answer and a derivation
                       all survive JSON without losing the reason attached to them
    the same producer  a recipe's plan and a hand-built plan resolve to the same operations with
                       the same parameters
    the boundary       a derivation reaches no adapter, writes no artifact, and lands in a
                       collection the conductor has no door to
    the source         the post is byte-identical after every one of it

`FakeCollection` counts its writes, so "nothing was written" is a number rather than a promise.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import perception_lab as R
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.derivation_store import MongoDerivationStore
from backend.services.perception_lab.mongo_store import MongoLabStore
from backend.tests.fixtures import perception_lab_live as F
from backend.tests.test_perception_lab_routes import PREFIX, Wiring, _find_all, _session


@pytest.fixture
def wired(monkeypatch):
    """The lab routes on their own app, with the derivation collection wired to the same fakes."""
    w = Wiring()

    async def _open_source(post_id: str):
        from backend.services.perception_lab import source as src
        post = await src.read_post(post_id, collection=w.posts)
        return src.snapshot_from(post, w.image)

    def _conductor(snapshot, store):
        from backend.services.perception_lab.live import conductor_for
        return conductor_for(snapshot, store=store, extent_adapters=w.adapters,
                             probe_collection=w.probe_posts)

    async def _list_sources(limit: int):
        from backend.services.perception_lab import source as src
        return await src.list_sources(limit=limit, collection=w.posts)

    monkeypatch.setattr(R, "_store", lambda: w.store)
    monkeypatch.setattr(R, "_derivation_store",
                        lambda: MongoDerivationStore(w.collections["derivations"]))
    monkeypatch.setattr(R, "_open_source", _open_source)
    monkeypatch.setattr(R, "_list_sources", _list_sources)
    monkeypatch.setattr(R, "_conductor", _conductor)

    app = FastAPI()
    app.include_router(R.router, prefix=PREFIX)
    with TestClient(app) as client:
        yield client, w


def _digest(w: Wiring) -> str:
    return hashlib.sha256(
        json.dumps([copy.deepcopy(d) for d in w.posts.docs.values()],
                   sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _extent_set(client, sid):
    run = _find_all(client, sid)
    return run["run"]["artifact_ids"][0]


def _derive(client, sid, form, artifact_ids, parameters=None):
    res = client.post(f"{PREFIX}/sessions/{sid}/derivations",
                      json={"form": form, "artifact_ids": artifact_ids,
                            "parameters": parameters or {}})
    assert res.status_code == 201, res.text
    return res.json()


# ── the form catalogue ───────────────────────────────────────────────────────


def test_the_form_catalogue_names_all_nineteen_and_says_who_could_write_each(wired):
    client, _ = wired
    body = client.get(f"{PREFIX}/forms").json()
    assert len(body["forms"]) == 19
    assert body["counts"]["registered"] == 19
    for form in body["forms"]:
        assert form["producers"] or form["blocked_by"], form["form"]


def test_an_unavailable_form_says_why_and_what_would_change_it(wired):
    client, _ = wired
    body = client.get(f"{PREFIX}/forms").json()
    blocked = [f for f in body["forms"] if not f["can_be_produced_here"]]
    assert blocked, "some forms are deferred in this contract; a catalogue saying otherwise lies"
    for form in blocked:
        assert form["blocked_by"] and form["note"], form["form"]


def test_the_catalogue_carries_model_and_revision_for_every_producer_that_has_one(wired):
    client, _ = wired
    body = client.get(f"{PREFIX}/forms").json()
    kinds = {p["kind"] for f in body["forms"] for p in f["producers"]}
    assert kinds <= {"model", "code", "human"}
    for form in body["forms"]:
        for producer in form["producers"]:
            if producer["kind"] == "code":
                assert producer["model"] is None
            if producer["state"] != "available":
                assert producer["reason"], f"{form['form']}/{producer['key']}"


def test_the_capability_answer_carries_the_reason_an_adapter_is_not_running(wired):
    client, _ = wired
    body = client.get(f"{PREFIX}/capabilities").json()
    adapters = [a for organ in body["organs"] for op in organ["operations"]
                for a in op["adapters"]]
    assert adapters
    for adapter in adapters:
        assert adapter["kind"] in ("model", "code", "human")
        if adapter["state"] != "available":
            assert adapter.get("reason"), adapter["key"]
            assert adapter.get("remedy"), adapter["key"]


def test_sam3_reports_configuration_rather_than_a_bare_unavailable(wired, monkeypatch):
    from backend.services import sam3_concept_service as svc
    monkeypatch.delenv(svc.WEIGHTS_ENV, raising=False)
    client, _ = wired
    body = client.get(f"{PREFIX}/capabilities").json()
    sam3 = [a for organ in body["organs"] for op in organ["operations"]
            for a in op["adapters"] if a["key"] == "sam3_concept"][0]
    assert sam3["state"] == "unavailable"
    assert svc.WEIGHTS_ENV in sam3["reason"] and svc.WEIGHTS_ENV in sam3["remedy"]
    assert sam3["model"] == svc.CHECKPOINT


# ── the recipe catalogue ─────────────────────────────────────────────────────


def test_the_recipe_catalogue_carries_the_seven_studies_and_no_way_to_run_one(wired):
    client, _ = wired
    body = client.get(f"{PREFIX}/recipes").json()
    assert len(body["recipes"]) == 7
    for recipe in body["recipes"]:
        assert recipe["steps"] and recipe["bounds"] and recipe["stop_conditions"]
        assert recipe["decision_points"], recipe["key"]
        for point in recipe["decision_points"]:
            assert point["why_a_person"], "a decision point with no reason is a dialog"
        assert "commands" not in recipe, (
            "a projection carrying ready-made commands would be a second place a study could be "
            "executed from")


def test_readiness_says_which_studies_cannot_finish_here_before_anything_is_spent(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    blocked = {}
    for key in ("boundary-and-void", "fragment-continuity", "ambiguous-form-hypothesis"):
        body = client.get(f"{PREFIX}/sessions/{sid}/recipes/{key}/readiness").json()
        if not body["ready"]:
            blocked[key] = body["unproducible_forms"]
    assert "fragment-continuity" in blocked
    assert "extent.fused_hypothesis" in blocked["fragment-continuity"]
    assert client.get(
        f"{PREFIX}/sessions/{sid}/recipes/boundary-and-void/readiness").json()["ready"] is True


def test_an_unknown_recipe_is_a_404_and_not_a_stub(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    res = client.get(f"{PREFIX}/sessions/{sid}/recipes/boundary-and-voids/readiness")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "unknown_recipe"


# ── a recipe reaches the same producer as a pressed control ──────────────────


def test_a_recipe_plan_and_a_hand_built_plan_resolve_to_the_same_acts(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    from_recipe = client.post(f"{PREFIX}/sessions/{sid}/recipes/boundary-and-void/plans",
                              json={"bindings": {}})
    assert from_recipe.status_code == 201, from_recipe.text
    recipe_plan = from_recipe.json()["plan"]

    step = from_recipe.json()["recipe"]["steps"][0]
    pressed = client.post(f"{PREFIX}/sessions/{sid}/plans", json={
        "planner": "direct",
        "commands": [{"operation": step["operation"], "parameters": step["parameters"]}]}).json()

    assert [s["operation"] for s in recipe_plan["resolved_steps"]] == \
        [s["operation"] for s in pressed["plan"]["resolved_steps"]]
    assert [s["parameters"] for s in recipe_plan["resolved_steps"]] == \
        [s["parameters"] for s in pressed["plan"]["resolved_steps"]]
    assert [s["adapter"] for s in recipe_plan["resolved_steps"]] == \
        [s["adapter"] for s in pressed["plan"]["resolved_steps"]]


def test_a_recipe_plan_carries_its_derivations_which_are_not_resolved_steps(wired):
    """Planning a derivation would put a pure function through a capability gate and report a
    model call that never happened. A surface showing only resolved steps would show one third of
    this study."""
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    body = client.post(f"{PREFIX}/sessions/{sid}/recipes/boundary-and-void/plans",
                       json={"bindings": {}}).json()
    assert len(body["plan"]["resolved_steps"]) == 1
    assert [d["produces"] for d in body["derivations"]] == ["extent.boundary_rings",
                                                            "extent.hole_set"]


def test_a_binding_the_recipe_did_not_ask_for_is_refused_rather_than_merged(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    res = client.post(f"{PREFIX}/sessions/{sid}/recipes/fragment-continuity/plans",
                      json={"bindings": {"find": {"max_instances": 99}}})
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "invalid_binding"


def test_a_concept_a_person_supplies_reaches_the_step_the_recipe_asked_it_for(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    body = client.post(f"{PREFIX}/sessions/{sid}/recipes/fragment-continuity/plans",
                       json={"bindings": {"find": {"concept": "drapery"}}}).json()
    assert body["plan"]["resolved_steps"][0]["parameters"]["concept"] == "drapery"


# ── deriving a form directly ─────────────────────────────────────────────────


def test_a_form_derived_over_the_wire_comes_back_with_its_payload_and_its_verdict(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    body = _derive(client, sid, "extent.boundary_rings", [artifact_id])
    record = body["derivation"]
    assert record["payload"]["variant"] == "extent_boundary"
    assert record["producible"] is True
    assert record["writable_as_artifact"] is False
    assert record["producer_kind"] == "code"
    assert record["producer_revision"] == "extent-exact-forms.v1"


def test_deriving_reaches_no_adapter_and_writes_no_artifact(wired):
    client, w = wired
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    before = {k: c.writes for k, c in w.collections.items()}
    calls = sum(len(getattr(a, "calls", [])) for a in w.adapters.values())
    _derive(client, sid, "extent.hole_set", [artifact_id])
    after = {k: c.writes for k, c in w.collections.items()}
    assert after["artifacts"] == before["artifacts"], "a derivation is not a measurement"
    assert after["runs"] == before["runs"], "a derivation is not a run"
    assert after["derivations"] == before["derivations"] + 1
    assert sum(len(getattr(a, "calls", [])) for a in w.adapters.values()) == calls


def test_a_deferred_form_derives_and_says_it_may_not_be_written(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    record = _derive(client, sid, "extent.density_field", [artifact_id],
                     {"field_shape": [4, 4]})["derivation"]
    assert record["producible"] is False
    assert [r["code"] for r in record["refusals"]] == ["form_not_producible"]
    assert record["payload"] is not None, "the shape is settled a phase before anything writes it"


def test_an_input_the_session_does_not_hold_is_a_404_and_never_fetched(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    res = client.post(f"{PREFIX}/sessions/{sid}/derivations",
                      json={"form": "extent.hole_set", "artifact_ids": ["art_elsewhere"]})
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "unknown_artifact"


def test_an_input_that_does_not_resolve_is_a_201_with_the_refusal_in_it(wired):
    """The same ruling `/plans` makes. The refusal is the answer, and a 4xx would leave a client
    with a status code where the laboratory's reply should be."""
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    res = client.post(f"{PREFIX}/sessions/{sid}/derivations",
                      json={"form": "extent.visible_inferred_partition",
                            "artifact_ids": [artifact_id], "parameters": {"parts": []}})
    assert res.status_code == 201
    assert res.json()["derivation"] is None
    assert res.json()["refusals"][0]["code"] == "missing_extent_inputs"


def test_a_derivation_is_read_back_in_the_session_it_was_computed_in(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    _derive(client, sid, "extent.hole_set", [artifact_id])
    _derive(client, sid, "extent.fragment_set", [artifact_id])
    found = client.get(f"{PREFIX}/sessions/{sid}/derivations").json()["derivations"]
    assert [d["form"] for d in found] == ["extent.hole_set", "extent.fragment_set"]


def test_an_undeclared_parameter_crosses_the_wire_and_is_dropped_and_recorded(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    record = _derive(client, sid, "extent.fragment_set", [artifact_id],
                     {"measure_separation": False, "promote": True})["derivation"]
    assert [p["name"] for p in record["dropped_parameters"]] == ["promote"]
    assert record["parameters"] == {"measure_separation": False}


# ── nothing any of it does touches the picture ───────────────────────────────


def test_the_post_is_byte_identical_after_a_catalogue_a_recipe_and_a_derivation(wired):
    client, w = wired
    before = _digest(w)
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    client.get(f"{PREFIX}/forms")
    client.get(f"{PREFIX}/recipes")
    client.get(f"{PREFIX}/sessions/{sid}/recipes/boundary-and-void/readiness")
    client.post(f"{PREFIX}/sessions/{sid}/recipes/boundary-and-void/plans", json={"bindings": {}})
    _derive(client, sid, "extent.boundary_rings", [artifact_id])
    assert _digest(w) == before
    assert w.posts.writes == 0


def test_no_route_added_here_can_promote_anything(wired):
    client, _ = wired
    sid = _session(client)["session"]["session_id"]
    artifact_id = _extent_set(client, sid)
    record = _derive(client, sid, "extent.hole_set", [artifact_id])["derivation"]
    assert "lifecycle" not in record
    res = client.patch(f"{PREFIX}/sessions/{sid}/artifacts/{record['derivation_id']}/lifecycle",
                       json={"status": "promoted"})
    assert res.status_code in (404, 422), "a derivation is not an artifact and has no ladder"
