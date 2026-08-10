"""
PERCEPTUAL-ORGANS-002A2 — the canonical selected-instance identity, proved once.

The defect this repairs is not a missing feature. It is a DISAGREEMENT that no test could see:
the frontend emitted `instance_id` on an input ref, the Python schema forbade unknown keys and
rejected it, Extent refused every multi-instance refinement rather than reaching one, Topology
froze a local field of its own, and the conductor could not bind "that mask". Four lanes, four
private answers, and nothing red anywhere.

So this file is organised around the disagreement rather than around the field:

  1. COMPATIBILITY — every record written before the field reads back unchanged, and an
     artifact-level reference still means the whole artifact.
  2. THE SHAPE — a bare instance, and an instance beside a canonical region, cannot be built.
  3. RESOLUTION — one instance inside a multi-instance artifact resolves; a missing one and one
     belonging to another artifact refuse, and neither falls back to the container.
  4. THE FOLLOW-UP LAW — "that mask" resolves only through what the session declared, and a
     deselection takes it away.
  5. PARITY — the JavaScript's own answers about nine reference shapes, rebuilt here.
  6. MUTATION — each gate above, disabled, and the test that should then fail.

Regenerate the JS-authored fixture with:
    UPDATE_PARITY_FIXTURES=1 npx vitest run src/perceptionLab/contract
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from backend.schemas.perception_lab import (IdentityScope, InputRef, InstanceRef, LabSession,
                                            LabSource, OrganFamily, SessionMode)
from backend.services.perception_lab import extent as E
from backend.services.perception_lab import topology as T
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.planners.base import bind_many, bind_pair, bind_single
from backend.services.perception_lab.session import SessionMachine, SessionView, declared_ids

REPO_ROOT = Path(__file__).resolve().parents[2]
JS_REFS_FIXTURE = REPO_ROOT / "contracts" / "fixtures" / "perception-lab" / "js-instance-refs.json"

SOURCE = LabSource(origin="upload", image_digest="sha256:aa11bb22cc33dd44",
                   natural_width=800, natural_height=600)
AT = "2026-08-11T09:00:00Z"


def session(**over: Any) -> LabSession:
    base: Dict[str, Any] = dict(
        session_id="labs_1", source=SOURCE, selected_organ=OrganFamily.EXTENT,
        mode=SessionMode.ISOLATION, created_at=AT, updated_at=AT)
    base.update(over)
    return LabSession(**base)


def machine(**over: Any) -> SessionMachine:
    return SessionMachine(session(**over), clock=FrozenClock(AT), ids=SequentialIds())


# ── 1. compatibility: nothing written before this field changed meaning ──────


def test_an_artifact_level_ref_is_unchanged_and_still_means_the_whole_artifact():
    ref = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a")
    assert ref.instance_id is None
    assert ref.names_one_instance is False
    assert ref.reference == "art_a", "the composite is only used when there IS an instance"


def test_a_record_written_before_the_field_existed_reads_back_identically():
    """The literal pre-A2 payload — no `instance_id` key at all — round-trips to itself."""
    pre_a2 = {"role": "base", "scope": "session", "artifact_id": "art_a", "region_id": None,
              "geometry_rev": None}
    ref = InputRef.model_validate(pre_a2)
    dumped = ref.model_dump(mode="json")
    assert dumped["instance_id"] is None
    assert {k: v for k, v in dumped.items() if k != "instance_id"} == pre_a2


def test_a_session_written_before_the_field_existed_still_validates():
    pre_a2 = session().model_dump(mode="json")
    pre_a2.pop("selected_instance_refs")
    assert LabSession.model_validate(pre_a2).selected_instance_refs == []


def test_every_committed_fixture_and_the_replay_record_still_read():
    """A historical corpus is not a corpus if a schema change quietly excludes half of it."""
    directory = REPO_ROOT / "contracts" / "fixtures" / "perception-lab"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    from backend.schemas.perception_lab import RECORD_MODELS
    seen = 0
    for record, names in manifest["records"].items():
        for name in names:
            doc = json.loads((directory / name).read_text(encoding="utf-8"))
            RECORD_MODELS[record].model_validate(doc)
            seen += 1
    assert seen >= 20, "the corpus shrank; a compatibility proof over three files proves little"


# ── 2. the shape: two combinations that cannot be built at all ───────────────


def test_a_bare_instance_identity_cannot_validate():
    with pytest.raises(ValidationError):
        InputRef(role="base", scope=IdentityScope.SESSION, instance_id="inst_2")


def test_an_instance_beside_a_canonical_region_cannot_validate():
    with pytest.raises(ValidationError):
        InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="reg_7",
                 geometry_rev=3, instance_id="inst_2")


def test_an_instance_ref_record_cannot_hold_one_half_of_itself():
    for bad in ({"artifact_id": "art_a"}, {"instance_id": "inst_2"},
                {"artifact_id": "", "instance_id": "inst_2"}):
        with pytest.raises(ValidationError):
            InstanceRef(**bad)


def test_a_session_refuses_an_instance_whose_artifact_it_has_not_selected():
    with pytest.raises(ValidationError):
        session(selected_artifact_ids=["art_a"],
                selected_instance_refs=[InstanceRef(artifact_id="art_b", instance_id="inst_1")])


# ── 3. resolution: which extent, exactly ─────────────────────────────────────


def _extent_artifact(instance_ids: List[str], artifact_id: str = "art_a") -> Any:
    """A minimal contract-valid `extent_set` holding the named instances."""
    from backend.schemas.perception_lab import (ArtifactIdentity, ArtifactInterpretation,
                                                ArtifactKind, ArtifactLifecycle,
                                                ArtifactMeasurement, ArtifactProjection,
                                                ArtifactProvenance, Box, CoordinateSystem,
                                                EpistemicBasis, EpistemicStatus, ExtentInstance,
                                                ExtentSetPayload, LabelSource, LifecycleState,
                                                PerceptualArtifact, ProducerKind, ProjectionKind)
    return PerceptualArtifact(
        identity=ArtifactIdentity(
            artifact_id=artifact_id, session_id="labs_1", run_id="run_1", step_id="step_1",
            organ_family=OrganFamily.EXTENT, artifact_kind=ArtifactKind.EXTENT_SET,
            operation="extent.find_all", identity_scope=IdentityScope.SESSION),
        measurement=ArtifactMeasurement(
            payload_variant="extent_set",
            payload=ExtentSetPayload(
                variant="extent_set", searched="every separable instance",
                instances=[ExtentInstance(instance_id=i,
                                          box=Box(x=0.1, y=0.1, w=0.2, h=0.2))
                           for i in instance_ids]),
            coordinate_system=CoordinateSystem.NORMALIZED_XY_TOPLEFT,
            epistemic_status=EpistemicStatus.INTERPRETIVE, epistemic_basis=EpistemicBasis.BOX,
            basis_detail="boxes, for a resolution test that measures nothing"),
        projection=ArtifactProjection(projection_kind=ProjectionKind.NONE),
        interpretation=ArtifactInterpretation(label=None, label_source=LabelSource.NONE,
                                              epistemic_status=EpistemicStatus.UNCERTAIN),
        lifecycle=ArtifactLifecycle(status=LifecycleState.PROPOSED, changed_at=AT,
                                    changed_by="test"),
        provenance=ArtifactProvenance(producer_kind=ProducerKind.ADAPTER, producer="test",
                                      adapter="test", source_image_digest=SOURCE.image_digest))


def _resolve_extent_ref(ref: InputRef, artifact: Any):
    from backend.schemas.perception_lab import ResolvedStep
    step = ResolvedStep(step_id="step_1", organ=OrganFamily.EXTENT, operation="extent.refine",
                        parameters={}, input_refs=[ref], authorized_by="resolver")
    ctx = E.ExtentContext(session_id="labs_1", run_id="run_1", image_bytes=b"",
                          source_image_digest=SOURCE.image_digest, natural_width=800,
                          natural_height=600,
                          artifacts={artifact.identity.artifact_id: artifact},
                          now=lambda: AT)
    return E._resolve_refs(step, ctx)


def test_one_instance_inside_a_multi_instance_artifact_resolves():
    art = _extent_artifact(["inst_1", "inst_2", "inst_3"])
    ref = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a",
                   instance_id="inst_2")
    resolved, refusals = _resolve_extent_ref(ref, art)
    assert refusals == []
    assert resolved["base"][0][0].instance_id == "inst_2"


def test_an_instance_the_artifact_does_not_hold_refuses_and_does_not_fall_back():
    art = _extent_artifact(["inst_1", "inst_2"])
    ref = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a",
                   instance_id="inst_9")
    resolved, refusals = _resolve_extent_ref(ref, art)
    assert resolved == {}, "falling back to the whole artifact would answer a different question"
    assert refusals[0].code.value == "unknown_reference"
    assert refusals[0].missing == ["art_a#inst_9"]
    assert refusals[0].detail["available"] == ["inst_1", "inst_2"]


def test_an_instance_belonging_to_another_artifact_refuses():
    """`inst_2` exists — in `art_b`. Naming it under `art_a` is not a near miss, it is a
    different mask, and a set that happened to hold an `inst_2` of its own would answer with
    the wrong one."""
    art = _extent_artifact(["inst_1"], artifact_id="art_a")
    ref = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a",
                   instance_id="inst_2")
    _resolved, refusals = _resolve_extent_ref(ref, art)
    assert refusals[0].missing == ["art_a#inst_2"]


def test_topology_endpoints_cite_exactly_the_instances_the_step_named():
    directory = REPO_ROOT / "research" / "perception_lab" / "fixtures" / "topology"
    scene = json.loads((directory / "extent-set.scene.json").read_text(encoding="utf-8"))
    art_id = scene["identity"]["artifact_id"]
    request = T.TopologyRequest(
        operation="topology.containment",
        context=T.LabContext(session_id="labs_1", run_id="run_1", step_id="step_1",
                             source_image_digest=SOURCE.image_digest, now=AT),
        inputs=(T.topology_input("source", art_id, "inst_inner"),
                T.topology_input("target", art_id, "inst_outer")),
        extents=(scene,))
    result = T.run(request)
    relation = result.artifact.measurement.payload.relations[0]
    assert (relation.source.instance_id, relation.target.instance_id) == \
        ("inst_inner", "inst_outer")
    assert [r.instance_id for r in result.artifact.identity.input_refs] == \
        ["inst_inner", "inst_outer"], "the receipt names the masks, not merely their container"


# ── 4. the follow-up law: "that mask" and what takes it away ─────────────────


def test_that_mask_resolves_only_through_a_declared_instance_pair():
    view = SessionView.of(session(
        selected_artifact_ids=["art_a"], active_artifact_id="art_a",
        selected_instance_refs=[InstanceRef(artifact_id="art_a", instance_id="inst_2")]))
    bound = bind_single(view, "base")
    assert (bound[0].artifact_id, bound[0].instance_id) == ("art_a", "inst_2")

    # And an instance the session did NOT declare is not known, even though its artifact is.
    stranger = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a",
                        instance_id="inst_3")
    assert view.knows(stranger) is False
    assert view.unknown(stranger) == "art_a#inst_3"
    assert view.knows(InputRef(role="base", scope=IdentityScope.SESSION,
                               artifact_id="art_a")) is True


def test_a_pair_question_can_be_about_two_masks_inside_one_artifact():
    """The question A2 made askable. Before it, both endpoints had to be whole sets."""
    view = SessionView.of(session(
        selected_artifact_ids=["art_a"], active_artifact_id="art_a",
        selected_instance_refs=[InstanceRef(artifact_id="art_a", instance_id="inst_1"),
                                InstanceRef(artifact_id="art_a", instance_id="inst_2")]))
    left, right = bind_pair(view, ("source", "target"))
    assert (left.artifact_id, left.instance_id) == ("art_a", "inst_1")
    assert (right.artifact_id, right.instance_id) == ("art_a", "inst_2")


def test_an_artifact_with_no_selected_instance_still_binds_as_the_whole_set():
    view = SessionView.of(session(selected_artifact_ids=["art_a", "art_b"],
                                  active_artifact_id="art_a"))
    assert [(r.artifact_id, r.instance_id) for r in bind_many(view, "members", 8)] == \
        [("art_a", None), ("art_b", None)]


def test_deselecting_the_instance_prevents_the_next_prompt_from_reusing_it():
    m = machine()
    m.select("art_a")
    m.select_instance("art_a", "inst_2")
    assert bind_single(m.view(), "base")[0].instance_id == "inst_2"

    m.deselect_instance("art_a", "inst_2")
    widened = bind_single(m.view(), "base")[0]
    assert widened.instance_id is None, "un-narrowing returns to the whole set"
    assert widened.artifact_id == "art_a", "the artifact stays selected; only the narrowing goes"
    assert m.view().knows(InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a",
                                   instance_id="inst_2")) is False


def test_deselecting_the_artifact_takes_its_instances_with_it():
    m = machine()
    m.select_instance("art_a", "inst_2")
    assert m.session.selected_artifact_ids == ["art_a"], "selecting an instance selects its set"
    m.deselect("art_a")
    assert m.session.selected_instance_refs == []
    assert bind_single(m.view(), "base") == ()
    assert declared_ids(m.session) == ()


def test_clearing_the_selection_clears_the_instances_too():
    m = machine()
    m.select_instance("art_a", "inst_1", "inst_2")
    m.clear_selection()
    assert m.session.selected_instance_refs == []


def test_a_declared_instance_is_listed_as_a_pair_a_person_can_type_back():
    m = machine()
    m.select_instance("art_a", "inst_2")
    assert "art_a#inst_2" in declared_ids(m.session)


# ── 5. parity: the JavaScript's nine answers, rebuilt here ───────────────────


def _js_cases():
    if not JS_REFS_FIXTURE.exists():                            # pragma: no cover - dev ergonomics
        pytest.skip(f"{JS_REFS_FIXTURE.name} not generated yet — run the vitest suite")
    return json.loads(JS_REFS_FIXTURE.read_text(encoding="utf-8"))


def test_python_agrees_with_the_frontend_about_every_reference_shape():
    """THE CHECK WHOSE ABSENCE WAS THE BUG.

    The frontend committed what it believes each of nine references is — malformed or not, known
    to the session or not, and what it is called. Every answer is rebuilt here from `InputRef`,
    `SessionView.knows` and `InputRef.reference`. A frontend that starts emitting a shape this
    schema will not accept now fails a Python test rather than a request in production.
    """
    data = _js_cases()
    js_session = data["session"]
    view = SessionView.of(session(
        selected_artifact_ids=list(js_session["selected_artifact_ids"]),
        active_artifact_id=js_session["active_artifact_id"],
        active_region_ids=list(js_session["active_region_ids"]),
        selected_instance_refs=[InstanceRef(**r) for r in js_session["selected_instance_refs"]]))

    assert data["cases"], "an empty answer sheet proves nothing"
    for case in data["cases"]:
        name = case["name"]
        try:
            ref = InputRef.model_validate(case["ref"])
        except ValidationError:
            assert case["problems"], f"{name}: Python refused a shape JavaScript admitted"
            continue
        assert not case["problems"], f"{name}: JavaScript refused a shape Python admitted"
        assert ref.reference == case["reference"], f"{name}: the two runtimes name it differently"
        assert view.knows(ref) is case["known"], \
            f"{name}: the two runtimes disagree about whether the session declared it"


def test_the_frontends_own_export_shape_validates_here():
    """The session block the JavaScript wrote, through the Python model, unmodified."""
    js_session = _js_cases()["session"]
    built = session(selected_artifact_ids=list(js_session["selected_artifact_ids"]),
                    active_artifact_id=js_session["active_artifact_id"],
                    active_region_ids=list(js_session["active_region_ids"]),
                    selected_instance_refs=[InstanceRef(**r)
                                            for r in js_session["selected_instance_refs"]])
    assert [r.model_dump(mode="json") for r in built.selected_instance_refs] == \
        js_session["selected_instance_refs"]


# ── 6. mutation: each gate, disabled, and what should then fail ──────────────


def test_the_shape_gate_is_what_refuses_a_bare_instance():
    """Without the `instance_id and not artifact_id` clause, the exactly-one rule alone lets a
    bare instance through — it names neither artifact nor region, so it dies for a DIFFERENT
    reason, and a test that only checked "it raised" would not notice the clause being deleted."""
    with pytest.raises(ValidationError) as caught:
        InputRef(role="base", scope=IdentityScope.SESSION, instance_id="inst_2")
    assert "exactly one of artifact_id / region_id" in str(caught.value), (
        "the bare-instance case is currently caught by the exactly-one rule; if that message "
        "changes, the instance clause needs its own reachable case")

    # The clause's OWN reachable case: an artifact-less ref cannot be built, so the clause is
    # exercised by a region ref instead — and that one it catches by name.
    with pytest.raises(ValidationError) as region_case:
        InputRef(role="regions", scope=IdentityScope.CANONICAL, region_id="reg_7",
                 geometry_rev=3, instance_id="inst_2")
    assert "an instance ref names the artifact that holds it" in str(region_case.value)


def test_the_session_gate_is_what_stops_a_deselected_mask_coming_back():
    """The mutation: a session assembled directly, with the instance left behind after its
    artifact went. If `LabSession` did not refuse this, `deselect` maintaining the invariant
    would be the only thing standing between a person and a reference they removed."""
    with pytest.raises(ValidationError) as caught:
        session(selected_artifact_ids=[],
                selected_instance_refs=[InstanceRef(artifact_id="art_a", instance_id="inst_2")])
    assert "deselection that did not take" in str(caught.value)


def test_the_reference_gate_is_what_stops_an_undeclared_instance():
    """The mutation: knows() with the instance clause removed would return True here, because the
    ARTIFACT is declared. That is the exact hole — a set being selected licensing every mask in
    it — and it is what makes "deselect that mask" a gesture with an effect."""
    view = SessionView.of(session(selected_artifact_ids=["art_a"], active_artifact_id="art_a"))
    with_instance = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a",
                             instance_id="inst_2")
    without = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a")
    assert view.knows(without) is True
    assert view.knows(with_instance) is False, \
        "selecting a set does not declare every mask inside it"


def test_the_extent_gate_is_what_stops_a_silent_widening():
    """The mutation: `_resolve_refs` without the instance check would resolve the ref to the whole
    artifact and the refinement would then refuse for AMBIGUITY — a different code, a different
    remedy, and a person told to name an extent they already named."""
    art = _extent_artifact(["inst_1", "inst_2"])
    ref = InputRef(role="base", scope=IdentityScope.SESSION, artifact_id="art_a",
                   instance_id="inst_9")
    _resolved, refusals = _resolve_extent_ref(ref, art)
    assert refusals[0].code.value == "unknown_reference"
    assert refusals[0].code.value != "invalid_parameters"
