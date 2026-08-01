"""
CIRCUIT-002 SURFACE-002 — the corpus run surface, on FAKES (no GPU, no network, no database).

The Groq client is forced offline (deterministic rule-based planning), the produce-field handlers
are faked, and the store is a `FakeCollection`. What is under test is the SURFACE — assembling a
corpus from raw posts, driving the loop over it, the production record, the RunView shape, and the
four guards that make the thing safe to expose to a person:

    ANNOTATION-INDEPENDENT   a post with zero annotations produces a FULL run. This is the whole
                             premise: the actuators produce evidence from pixels, and a demo that
                             only worked on hand-prepared posts would be a demo of the preparation.
    SUGGESTIONS-ONLY         every post document is byte-identical before and after.
    PROVENANCE EVERYWHERE    every produced descriptor and every production record carries the run
                             and the step that made it (PROV-001's join, from the step's side).
    HONEST EMPTINESS         a prompt nothing serves comes back as a run that says so, never as an
                             empty success.

The A3 arc across a request boundary — ask, store, answer, continue — is pinned here too, because
that is the one thing the surface adds to A3 that A3 could not test itself.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest
from bson.objectid import ObjectId

from backend.services import epistemics, run_store
from backend.services.director import loop_controller as lc
from backend.services.director import run_surface as rs
from backend.services.director.capabilities import Resource
from backend.services.director.planner import RuleBasedPlanner
from backend.tests.test_circulation_spine_p1 import FakeCollection, run

_A = ObjectId("507f1f77bcf86cd799439021")
_B = ObjectId("507f1f77bcf86cd799439022")


# ── fixtures: raw posts, faked producers ──────────────────────────────────────

def _raw_post(oid, title="A", regions=None):
    """A post with a PICTURE and nothing else — the annotation-independent starting point."""
    doc = {"_id": oid, "photo_url": f"scratch://{title}.jpg", "title": title,
           "general_tags": ["facade"], "updated_at": "2026-08-01T00:00:00Z"}
    if regions is not None:
        doc["region_annotations"] = regions
    return doc


def _posts(*docs):
    return {str(d["_id"]): d for d in docs}


def _hash(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()


@pytest.fixture(autouse=True)
def _offline_planner(monkeypatch):
    """CI must not depend on the Groq API, and BOTH planners have to be told.

    The step planner and the ARGUMENT planner hold separate clients. Silencing only the first
    left an argue-mode test quietly calling the real API — it passed, on the network, which is
    the failure mode a test suite is least likely to notice about itself.
    """
    import backend.services.director.groq_planner as gp
    import backend.services.director.argument_planner as ap
    import backend.services.director.composition as comp
    monkeypatch.setattr(gp.GroqPlanner, "_get_client", lambda self: None)
    monkeypatch.setattr(ap.GroqArgumentPlanner, "_get_client", lambda self: None)
    monkeypatch.setattr(comp.LLM, "from_service", classmethod(lambda cls: None))


@pytest.fixture
def faked_producers(monkeypatch):
    """The real actuator wiring, with the MODEL boundary faked.

    Deliberately not stubs: the run must go through `RealActuatorRunner`, so PROV-001's step-id
    stamping and the quarantine guard are exercised exactly as they would be in production. Only
    the pixels and the weights are fake.
    """
    import backend.routers.posts as P
    import backend.services.segmentation_service as seg
    import backend.services.dinov2_service as dsvc

    monkeypatch.setattr(seg, "is_available", lambda: True)
    monkeypatch.setattr(seg, "segment_image_bytes",
                        lambda data, **k: [{"id": f"seg_{i}", "geometry_rev": 0,
                                            "box": {"x": 0.1 * i, "y": 0.1, "w": 0.3, "h": 0.3},
                                            "mask_rle": None} for i in range(2)])
    monkeypatch.setattr(dsvc, "is_available", lambda: True)

    async def _fetch(post_id, post):
        return b"\x89PNG-fake"
    monkeypatch.setattr(P, "_fetch_post_image_cached", _fetch)

    made = []

    def _mk(role):
        async def _handler(post_id, post, region, req, run_id):
            sug = epistemics.stamp({
                "producer": role, "type": "brush_field", "role": role,
                "geometry": {"kind": "soft_mask",
                             "strokes": [{"points": [[0.5, 0.5]], "radius": 0.05}]},
                "provenance": {"model": f"fake::{role}", "adapter": role, "run_id": run_id},
                "confidence": 0.61})
            made.append(sug)
            return [sug], "ready", True
        return _handler

    for name in ("material_field", "rhythm", "pressure_zone", "negative_space",
                 "light_field", "shadow_field", "presence_check"):
        monkeypatch.setitem(P._FIELD_PRODUCERS, name, _mk(name))
    return made


def _drive(spec, posts, **kw):
    view, result, engine = rs.drive_run(spec, posts, run_id=kw.pop("run_id", "run_test"),
                                        planner=kw.pop("planner", RuleBasedPlanner()), **kw)
    engine.close()
    return view, result


# ── 1. the governing principle: annotation-independent ────────────────────────

def test_a_post_with_ZERO_annotations_produces_a_full_run(faked_producers):
    """The premise of the whole surface. No regions, no marks, no grounds, no text — a picture and
    a sentence. Anything less than a full run here would mean the engine only works on posts
    somebody prepared by hand, which is a demo of the preparation."""
    posts = _posts(_raw_post(_A))
    assert "region_annotations" not in posts[str(_A)]        # nothing was prepared

    view, result = _drive(rs.RunSpec.of(prompt="read the material of the surface",
                                        image_ids=[str(_A)]), posts)
    d = view.to_dict()

    assert d["status"] == rs.STATUS_COMPLETE
    assert d["rounds"], "a run with no annotations still runs rounds"
    ran = [p for p in d["production_records"] if p["status"] == "ok"]
    assert ran, "the actuators produced evidence from pixels, not from prior annotations"
    assert d["suggestions"], "and left it in the quarantine"
    # evidence that did not exist before the run now does
    assert result.memory.available()[Resource.REGION] > 0


def test_the_corpus_is_assembled_from_raw_images_alone(faked_producers):
    posts = _posts(_raw_post(_A, "A"), _raw_post(_B, "B"))
    view, _ = _drive(rs.RunSpec.of(prompt="read the material", image_ids=[str(_A), str(_B)]), posts)
    corpus = view.to_dict()["corpus"]
    assert [c["post_id"] for c in corpus] == [str(_A), str(_B)]     # the curator's order, kept
    assert all(c["image_url"].startswith("scratch://") for c in corpus)


def test_every_image_in_the_corpus_is_actually_looked_at(faked_producers):
    """The run surface fans a single-image step out across the corpus. Left to `resolve_corpus`'s
    default, an untargeted step goes to the FOCUS image only — correct for a plan a curator wrote,
    and wrong for a run whose premise is a set of images."""
    posts = _posts(_raw_post(_A, "A"), _raw_post(_B, "B"))
    view, _ = _drive(rs.RunSpec.of(prompt="read the material", image_ids=[str(_A), str(_B)]), posts)
    touched = {p["image"] for p in view.to_dict()["production_records"] if p["image"]}
    assert touched == {str(_A), str(_B)}


def test_committed_annotations_are_a_head_start_never_a_requirement(faked_producers):
    """A curator's own regions are folded in as memory — the run may then plan a step that needs
    one straight away. What must never happen is the absence of them blocking anything."""
    prepared = _raw_post(_A, "A", regions=[{"id": "curator_r1", "geometry_rev": 1}])
    view, _ = _drive(rs.RunSpec.of(prompt="read the material", image_ids=[str(_A)]),
                     _posts(prepared))
    assert view.to_dict()["status"] == rs.STATUS_COMPLETE


# ── 2. suggestions-only ───────────────────────────────────────────────────────

def test_a_run_leaves_every_post_byte_identical(faked_producers):
    posts = _posts(_raw_post(_A, "A"), _raw_post(_B, "B"))
    before = {pid: _hash(doc) for pid, doc in posts.items()}

    view, _ = _drive(rs.RunSpec.of(prompt="read the material", image_ids=list(posts)), posts)

    assert view.to_dict()["suggestions"], "it really did produce something"
    for pid, doc in posts.items():
        assert _hash(doc) == before[pid], f"post {pid} was mutated by a run"


def test_nothing_produced_is_a_committed_mark(faked_producers):
    """Everything in the quarantine is a proposal: it carries an epistemic status and a run, and
    none of it has been accepted into a post."""
    posts = _posts(_raw_post(_A))
    view, _ = _drive(rs.RunSpec.of(prompt="read the material", image_ids=[str(_A)]), posts)
    for sug in view.to_dict()["suggestions"]:
        assert sug.get("epistemic_status")               # M5: how it is known, on the item
        assert "id" not in sug or sug.get("id") is None  # not a stored record
    assert not posts[str(_A)].get("visual_marks")


# ── 3. provenance everywhere ──────────────────────────────────────────────────

def test_every_produced_descriptor_carries_its_run_and_step(faked_producers):
    posts = _posts(_raw_post(_A))
    view, _ = _drive(rs.RunSpec.of(prompt="read the material", image_ids=[str(_A)]), posts,
                     run_id="run_prov")
    suggestions = view.to_dict()["suggestions"]
    assert suggestions
    for sug in suggestions:
        prov = sug.get("provenance") or {}
        assert prov.get("run_id") == "run_prov"
        assert prov.get("step_id"), "PROV-001 Seam 1: which STEP made this"


def test_the_production_record_joins_each_step_to_what_it_made(faked_producers):
    posts = _posts(_raw_post(_A))
    view, _ = _drive(rs.RunSpec.of(prompt="read the material", image_ids=[str(_A)]), posts,
                     run_id="run_join")
    records = view.to_dict()["production_records"]
    produced_by_field = [r for r in records if r["actuator"] == "material_field"]
    assert produced_by_field
    rec = produced_by_field[0]
    assert rec["model"] == "fake::material_field"          # what actually ran
    assert rec["adapter"] == "material_field"
    assert rec["latency_ms"] is not None                   # SURFACE-002's seam in execute()
    assert rec["produced"], "the descriptors this step minted, joined by step_id"
    assert all(p["epistemic_status"] for p in rec["produced"])   # M5 tag travels with each item
    assert all(p["ref"].startswith("run_join:") for p in rec["produced"])


def test_a_refused_step_is_on_the_manifest_with_its_reason(faked_producers):
    """A manifest that listed only what ran would make a plan of five steps look like three."""
    posts = _posts(_raw_post(_A))
    # `connect_marks` needs two marks and nothing here provides them.
    planner = _FixedPlanner([("rhythm", {}), ("connect_marks", {"relation_role": "x"})])
    view, _ = _drive(rs.RunSpec.of(prompt="relate them", image_ids=[str(_A)]), posts,
                     planner=planner)
    refused = [r for r in view.to_dict()["production_records"] if r["status"] == "refused"]
    assert refused
    assert refused[0]["actuator"] == "connect_marks"
    assert refused[0]["refusal"]["reason"] == "missing_input"
    assert refused[0]["refusal"]["detail"]


def test_unknown_values_are_null_never_invented(faked_producers):
    """A refused step never reached a dispatch: no model, no adapter, no latency. Writing a zero
    would say 'instant' where the truth is 'never ran'."""
    posts = _posts(_raw_post(_A))
    planner = _FixedPlanner([("rhythm", {}), ("connect_marks", {"relation_role": "x"})])
    view, _ = _drive(rs.RunSpec.of(prompt="relate them", image_ids=[str(_A)]), posts,
                     planner=planner)
    refused = [r for r in view.to_dict()["production_records"] if r["status"] == "refused"][0]
    assert refused["latency_ms"] is None
    assert refused["model"] is None and refused["adapter"] is None
    assert refused["produced"] == []


class _FixedPlanner:
    """A planner that always proposes the same chain — for pinning refusal shapes."""
    name = "fixed"
    last_notes = ()

    def __init__(self, steps):
        from backend.services.director.plan import Step
        self._steps = [Step(actuator=a, params=dict(p), id=f"fixed:{i}:{a}")
                       for i, (a, p) in enumerate(steps)]

    def propose(self, intention, memory):
        return list(self._steps)


# ── 4. honest emptiness ───────────────────────────────────────────────────────

def test_a_prompt_nothing_serves_returns_a_run_that_SAYS_so(faked_producers):
    """Not an empty success. The run reports the reason the loop gave it, and produces nothing."""
    posts = _posts(_raw_post(_A))
    view, _ = _drive(rs.RunSpec.of(prompt="mumble", image_ids=[str(_A)]), posts)
    d = view.to_dict()
    assert d["status"] == rs.STATUS_STOPPED
    assert d["stop_reason"] == lc.STOP_NOTHING_PLANNED
    assert d["suggestions"] == []
    assert d["production_records"] == []


def test_an_unreadable_image_is_reported_not_silently_dropped(faked_producers):
    """'The colonnade has no marks' and 'the colonnade could not be loaded' are different facts."""
    corpus = rs.corpus_from_posts([_raw_post(_A), {"_id": _B, "photo_url": "scratch://B.jpg"}],
                                  corpus_id="c")
    memory = rs.hydrate_run_memory(corpus, _posts(_raw_post(_A)))     # B deliberately absent
    assert any(str(_B) in u for u in memory.unreadable)


# ── 5. the A3 arc across a request boundary ───────────────────────────────────

def test_a_run_that_needs_a_phrase_stops_and_asks(faked_producers):
    posts = _posts(_raw_post(_A))
    view, result = _drive(rs.RunSpec.of(prompt="check whether it is present", image_ids=[str(_A)]),
                          posts)
    d = view.to_dict()
    assert d["status"] == rs.STATUS_AWAITING_ANSWER
    assert d["question"] and d["question"]["missing_param"] == "phrase"
    assert result.resume_state is not None, "and it can be answered later"


def test_the_answer_continues_the_SAME_run_and_the_step_then_runs(faked_producers):
    """The surface's own contribution to A3: the run is rebuilt from what was STORED and carries
    on, so the arc is one receipt rather than two runs."""
    posts = _posts(_raw_post(_A))
    spec = rs.RunSpec.of(prompt="check whether it is present", image_ids=[str(_A)])
    view, result, engine = rs.drive_run(spec, posts, run_id="run_a3", planner=RuleBasedPlanner())
    assert view.status == rs.STATUS_AWAITING_ANSWER

    resumed_view, resumed = rs.resume_run(result, "a cross", engine, spec=spec)
    engine.close()
    d = resumed_view.to_dict()

    assert d["answer"]["accepted"] is True
    assert d["answer"]["text"] == "a cross"
    assert len(d["rounds"]) > len(view.to_dict()["rounds"])          # it EXTENDS
    assert [r["round"] for r in d["rounds"]] == list(range(len(d["rounds"])))
    ran = [p for p in d["production_records"] if p["actuator"] == "presence_check"
           and p["status"] == "ok"]
    assert ran, "the step that was blocked on a phrase ran once the curator supplied one"


def test_an_empty_answer_leaves_the_run_waiting_and_fabricates_nothing(faked_producers):
    posts = _posts(_raw_post(_A))
    spec = rs.RunSpec.of(prompt="check whether it is present", image_ids=[str(_A)])
    view, result, engine = rs.drive_run(spec, posts, run_id="run_a3b", planner=RuleBasedPlanner())
    resumed_view, _ = rs.resume_run(result, "   ", engine, spec=spec)
    engine.close()
    d = resumed_view.to_dict()
    assert d["status"] == rs.STATUS_AWAITING_ANSWER
    assert d["answer"]["accepted"] is False
    assert d["question"] is not None


# ── 6. the store: a run survives between requests ─────────────────────────────

def test_the_store_holds_the_view_and_the_resume_state():
    runs = FakeCollection()
    doc = run(run_store.create_run(run_id="r1", spec={"prompt": "p"}, collection=runs))
    assert doc["status"] == "pending" and doc["resume"] is None

    run(run_store.save_view("r1", {"status": "awaiting_answer", "run_id": "r1"},
                            resume={"intention": "p"}, image_of={"s1": "p1"}, collection=runs))
    stored = run(run_store.get_run("r1", collection=runs))
    assert stored["status"] == "awaiting_answer"
    assert run_store.is_answerable(stored)
    assert stored["image_of"] == {"s1": "p1"}


def test_a_run_that_moved_on_stops_being_answerable():
    """A stale resume state would let a late answer resume a run that has already continued."""
    runs = FakeCollection()
    run(run_store.create_run(run_id="r2", spec={"prompt": "p"}, collection=runs))
    run(run_store.save_view("r2", {"status": "awaiting_answer"}, resume={"intention": "p"},
                            collection=runs))
    run(run_store.save_view("r2", {"status": "complete"}, resume=None, collection=runs))
    stored = run(run_store.get_run("r2", collection=runs))
    assert stored["resume"] is None
    assert not run_store.is_answerable(stored)


def test_the_resume_state_round_trips_through_the_store(faked_producers):
    """The one thing the surface adds to A3: the state is written down, read back, and still
    resumes. This is what makes an answer minutes later the same run."""
    posts = _posts(_raw_post(_A))
    spec = rs.RunSpec.of(prompt="check whether it is present", image_ids=[str(_A)])
    view, result, engine = rs.drive_run(spec, posts, run_id="run_store", planner=RuleBasedPlanner())
    packed = json.loads(json.dumps(result.resume_state.to_dict()))
    engine.close()

    restored = lc.ResumeState.from_dict(packed)
    assert restored.question.missing_param == "phrase"
    assert restored.intention == spec.prompt
    assert [r.index for r in restored.rounds] == [r.index for r in result.rounds]


# ── 7. the shared fixture — the pin both lanes build against ──────────────────

def test_the_run_view_serialises_to_the_shared_fixture():
    """`runViewFixture` is the contract made concrete: Lane B renders from it while Lane A's routes
    are still being built, so the two lanes meet without a rewrite. If this fails, the contract
    moved and BOTH lanes need to know — that is the point of the test, not a nuisance."""
    from backend.tests.fixtures import run_view_fixture as F

    produced = F.fixture_run().to_dict()
    assert F.key_shape(produced) == F.key_shape(F.RUN_VIEW_FIXTURE)
    assert set(produced) == set(F.RUN_VIEW_FIXTURE), "the envelope's keys ARE the contract"
    assert produced["run_id"] == F.RUN_VIEW_FIXTURE["run_id"]
    assert produced["status"] == F.RUN_VIEW_FIXTURE["status"]
    assert produced["corpus"] == F.RUN_VIEW_FIXTURE["corpus"]
    assert produced["stop_reason"] == F.RUN_VIEW_FIXTURE["stop_reason"]


def test_the_fixture_is_generated_by_the_real_assembler_not_hand_written():
    """A hand-written fixture drifts from the code the day after it is written. This one comes out
    of the same `assemble_view` the routes call, over a real loop."""
    from backend.tests.fixtures import run_view_fixture as F
    view = F.fixture_run()
    assert isinstance(view, rs.RunView)
    assert view.production_records and view.suggestions
    assert view.rounds, "a real loop ran to make it"


def test_the_fixture_exercises_a_full_production_record():
    """Lane B is building a transparency panel against this. If the fixture's records were empty
    of models, statuses or produced items, the panel would be designed against a shape that never
    occurs in a real run."""
    from backend.tests.fixtures import run_view_fixture as F
    record = next(r for r in F.RUN_VIEW_FIXTURE["production_records"] if r["status"] == "ok")
    assert record["model"] and record["adapter"] and record["step_id"]
    assert record["image"], "which of the corpus images this step ran on"
    assert record["produced"] and record["produced"][0]["epistemic_status"]
    assert record["produced"][0]["ref"].startswith(F.FIXTURE_RUN_ID)
    assert record["latency_ms"] is not None
    assert record["inputs_used"], "what the step could see, beside what it demonstrably read"


def test_the_committed_json_and_the_python_literal_cannot_disagree():
    """Lane B may import the module or read the file. They are the same document by construction —
    the literal IS the file — and this says so out loud."""
    from backend.tests.fixtures import run_view_fixture as F
    assert F.RUN_VIEW_FIXTURE == F.load_json()
    assert F.RUN_VIEW_FIXTURE["run_id"] == F.FIXTURE_RUN_ID


# ── 8. argue mode: the prompt as a thesis (M2 → M6) ───────────────────────────
#
# The argument planner has NO rule-based fallback, by design: nothing rule-based can decompose a
# thesis without inventing one. So offline, an argue run honestly composes nothing — and that is
# the first test. The second injects a stand-in planner to exercise the composed path.

def test_argue_mode_composes_NOTHING_when_no_argument_could_be_planned(faked_producers):
    """An argue run that could not decompose its thesis is still a run: the evidence it produced
    is real, the article is absent, and the receipt says why rather than shipping an empty draft
    that reads like a modest one."""
    posts = _posts(_raw_post(_A))
    view, _ = _drive(rs.RunSpec.of(prompt="read the material of the surface",
                                   image_ids=[str(_A)], mode=rs.MODE_ARGUE), posts)
    d = view.to_dict()
    assert d["mode"] == "argue"
    assert d["article"] is None
    assert any("argue:" in n for n in d["notes"])
    assert d["suggestions"], "the evidence half of the run is unaffected"


def test_argue_mode_composes_an_article_from_what_the_run_CONFIRMED(faked_producers):
    """M3's rule, carried up to the surface: the article is composed against a chain that actually
    ran (`compose_article(provenance=…)`), never against the plan. An article written from a plan
    would describe evidence that may never have been produced."""
    from backend.services.director import argument as A
    from backend.services.director.composition import LLM

    class _FakeArgumentPlanner:
        """Stands in for the model that decomposes a thesis. It proposes; the gate still judges."""
        name = "fake_argument"
        last_notes = ("planner: fake_argument",)

        def propose(self, thesis, memory):
            return [A.make_claim("c0", "The surface concentrates toward one side.",
                                 [("pressure_zone", {"image": str(_A)}, A.SUPPORT)],
                                 target_status=A.MEASURED),
                    A.make_claim("c1", "The rhythm complicates that reading.",
                                 [("rhythm", {"image": str(_A)}, A.COMPLICATE)],
                                 target_status=A.MEASURED)]

    class _FakeLLM(LLM):
        def __init__(self):
            super().__init__(client=None, model="fake/composer")

        def complete(self, system, user):
            return json.dumps({"prose": "The field gathers toward the left of the frame.",
                               "grounded_in": [], "relevance": [], "qualified": False})

    posts = _posts(_raw_post(_A))
    view, _, engine = rs.drive_run(
        rs.RunSpec.of(prompt="The facade gathers what the ground disperses.",
                      image_ids=[str(_A)], mode=rs.MODE_ARGUE),
        posts, run_id="run_argue", planner=RuleBasedPlanner(),
        argument_planner=_FakeArgumentPlanner(), llm=_FakeLLM())
    engine.close()
    d = view.to_dict()

    assert d["article"] is not None
    assert d["article"]["thesis"] == "The facade gathers what the ground disperses."
    assert "resolved" in d["article"], "M4: citations resolved against the run's own suggestions"
    assert any("composed against a run of" in n for n in d["notes"])


def test_argue_mode_never_turns_a_composition_failure_into_a_failed_run(faked_producers):
    """An explore run that also tried to argue is still a run. A raising composer is a note, and
    the evidence stands."""
    class _Exploding:
        name = "boom"
        last_notes = ()

        def propose(self, thesis, memory):
            raise RuntimeError("the argument planner fell over")

    posts = _posts(_raw_post(_A))
    view, _, engine = rs.drive_run(
        rs.RunSpec.of(prompt="read the material", image_ids=[str(_A)], mode=rs.MODE_ARGUE),
        posts, run_id="run_argue_boom", planner=RuleBasedPlanner(),
        argument_planner=_Exploding())
    engine.close()
    d = view.to_dict()
    assert d["article"] is None
    assert any("did not complete" in n for n in d["notes"])
    assert d["status"] in (rs.STATUS_COMPLETE, rs.STATUS_STOPPED)
    assert d["suggestions"], "the run's evidence is unaffected"
