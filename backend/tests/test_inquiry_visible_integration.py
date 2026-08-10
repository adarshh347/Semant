"""
HARNESS-003D — the integration lane: the council, driven, persisted, projected and watchable.

Every other suite in this repository proves one lane. This one proves the SEAMS between three of
them, and it drives HTTP for the same reason `test_inquiry_session_routes` does: a projection that
works in Python and not on the wire fails here rather than in a rehearsal.

What was disconnected before this lane, and is asserted connected here:

    the council could not be reached        `runtime` bound the v1 one-call compiler
    the council could not be watched        no observer reached the compiler stage
    the dissolution could not be read       `graph_view` sent no units, atoms, coverage or passes
    the compilation had no actor            v2 leaves `provenance.compiler` null, and the stage
                                            projection only knew how to read that receipt
    a replay looked like a live run         nothing on the wire said which

The fixture is the FOLD REHEARSAL — the person's own 002R prompt and its four images — replayed
through frozen council payloads. A replay proves integration and may not ratify semantic usefulness;
that is what the live gate is for, and this suite says so rather than standing in for it.
"""
from __future__ import annotations

import asyncio
import threading
import time
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import inquiries as R
from backend.schemas.inquiry_stage import StageName
from backend.services.inquiry_session import coordinator, corpus, runtime, store, view
from backend.services.inquiry_session.capability import LockedFixtureCapability
from backend.services.inquiry_session.composer import DeterministicComposer
from backend.services.inquiry_session.dissolution_binding import DissolutionCompiler
from backend.services.inquiry_session.judge import judge
from backend.tests.fixtures import inquiry_session_fixtures as F

#: The 002R rehearsal's own prompt and corpus, and a control that shares no noun with it. Both are
#: run through the same code path, which is the only form the generality claim can take.
FOLD = "fold-rehearsal"
CONTROL = "unrelated-weave"

_BOUNDARIES = ("awaiting_user", "complete", "exhausted", "refused", "error")


@pytest.fixture
def wired(monkeypatch):
    """The inquiry routes with the REAL `DissolutionCompiler` over a frozen council.

    The compiler under test is production's adapter rather than a stand-in, so the observer seam,
    the wall-clock budget, the producer attributes and the pass receipts all run. Only the three
    minds behind it are frozen.
    """
    def _wire(fixture):
        posts = F.dissolution_post_collection_for(fixture)
        sessions = F.FakeCollection()
        monkeypatch.setattr(store, "_collection", lambda collection=None: sessions)

        real_resolve = corpus.resolve

        async def _resolve(post_ids, *, collection=None):
            return await real_resolve(post_ids, collection=posts)

        monkeypatch.setattr(corpus, "resolve", _resolve)

        def _stages():
            return F.dissolution_stages_for(
                fixture, capability=LockedFixtureCapability(), judge=judge,
                composer=DeterministicComposer(), clock=coordinator.utc_now)

        monkeypatch.setattr(R, "_stages", _stages)

        app = FastAPI()
        app.include_router(R.router, prefix="/api/v1/inquiries")
        return TestClient(app), posts, sessions

    return _wire


def _start(client, fixture, mode="consult", **over):
    body = {"prompt": F.dissolution_prompt_for(fixture), "mode": mode,
            "image_ids": [r.post_id for r in F.dissolution_post_refs(fixture)]}
    body.update(over)
    return client.post("/api/v1/inquiries", json=body)


def _settled(client, res, *, tries=600):
    session_id = res.json()["session_id"]
    body = res.json()
    for _ in range(tries):
        body = client.get(f"/api/v1/inquiries/{session_id}").json()
        if body.get("state") in _BOUNDARIES:
            return body
        time.sleep(0.005)
    raise AssertionError(f"session {session_id} never reached a boundary; "
                         f"last state {body.get('state')!r}")


def _run(wired, fixture=FOLD, mode="auto"):
    client, posts, sessions = wired(fixture)
    with client:
        return _settled(client, _start(client, fixture, mode=mode)), client, posts, sessions


def _stage(session, name):
    return next((s for s in session["stages"] if s["stage"] == name), None)


# ── the binding: the council is what /inquiry actually runs ──────────────────

def test_the_production_runtime_binds_the_council(monkeypatch):
    """The first of the four handoffs. Until this lane, `/inquiry` reached the v1 one-call compiler
    that 002R's rehearsal failed on, and the merged council was unreachable from the product."""
    monkeypatch.delenv("SEMANT_INQUIRY_COMPILER", raising=False)
    monkeypatch.setenv("SEMANT_INQUIRY_LIVE_MODELS", "1")
    assert isinstance(runtime.build_stages().compiler, DissolutionCompiler)


def test_the_legacy_compiler_is_reachable_on_purpose_and_never_by_fallback(monkeypatch):
    """v1 stays RUNNABLE, not merely readable — a stored v1 session's shape can be reproduced. It
    is selected by name and nothing selects it on an error."""
    from backend.services.semantic_compilation.compiler import ModelSemanticCompiler

    monkeypatch.setenv("SEMANT_INQUIRY_LIVE_MODELS", "1")
    monkeypatch.setenv("SEMANT_INQUIRY_COMPILER", "legacy")
    assert isinstance(runtime.build_stages().compiler, ModelSemanticCompiler)
    monkeypatch.setenv("SEMANT_INQUIRY_COMPILER", "something-nobody-declared")
    assert isinstance(runtime.build_stages().compiler, DissolutionCompiler)


# ── the whole chain, over the rehearsal's own prompt ─────────────────────────

def test_the_fold_rehearsal_runs_end_to_end_through_the_council(wired):
    session, *_ = _run(wired)
    graph = session["graph"]

    assert session["state"] == "complete"
    assert graph["schema_version"].endswith("v2"), graph["schema_version"]
    # Every object in the chain, and each is a count rather than a key check: an empty array is
    # what the wire sent before this lane and it satisfied every normaliser on the other side.
    assert len(graph["source_units"]) > 0
    assert len(graph["semantic_atoms"]) > 0
    assert len(graph["coverage"]) == len(graph["source_units"])
    assert len(graph["claims"]) > 0
    assert len(graph["observables"]) > 0
    assert len(graph["semantic_remainder"]) > 0
    assert len(graph["passes"]) >= 5


def test_the_unrelated_domain_control_runs_the_same_code_path(wired):
    """The generality claim, in the only form it can take: two fixtures that share no noun, one
    pipeline. A chain that had learned the rehearsal would produce less here."""
    session, *_ = _run(wired, CONTROL)
    graph = session["graph"]
    assert session["state"] == "complete"
    assert len(graph["source_units"]) > 0
    assert len(graph["semantic_atoms"]) > 0
    assert len(graph["claims"]) > 0
    assert [p["outcome"] for p in graph["passes"]] == ["completed"] * len(graph["passes"])


def test_the_persons_own_clauses_stay_theirs_through_the_wire(wired):
    """The one attribution nothing downstream could detect if it were wrong, checked at the edge.

    Derived from the anchors by the backend rather than read from the model's answer — so this
    asserts the DERIVATION survived the projection, not that a model behaved.
    """
    session, *_ = _run(wired)
    graph = session["graph"]
    clauses = {u["source_unit_id"] for u in graph["source_units"]
               if u["kind"] == "prompt_clause"}
    mine = [a for a in graph["semantic_atoms"] if a["author"] == "user"]

    assert mine, "no atom was attributed to the person on their own prompt"
    for atom in mine:
        assert set(atom["source_unit_ids"]) <= clauses
    for atom in graph["semantic_atoms"]:
        if set(atom["source_unit_ids"]) <= clauses and atom["source_unit_ids"]:
            assert atom["author"] == "user", atom["atom_id"]


# ── the second handoff: typed adequacy, live rather than pinned ──────────────

def test_a_typed_coverage_ledger_is_read_by_the_stage_that_consumes_it(wired):
    """003B's `declared_adequacy` counted nothing on a TYPED graph and reported `complete` for a
    ledger that might be all refusals. Production stored the dump, so it was never live — it was
    one edit away. Reconciled in this lane; this is the live half of the proof."""
    from backend.services.inquiry_session import outcomes
    from backend.tests.fixtures import semantic_dissolution_fixtures as D

    graph = D.dissolve_fixture(FOLD)
    typed = outcomes.declared_adequacy(graph)
    dumped = outcomes.declared_adequacy(graph.model_dump(mode="json", by_alias=True))

    assert typed.declared and dumped.declared
    assert (typed.complete, typed.uncovered) == (dumped.complete, dumped.uncovered)


# ── the third: the council's activity reaches the persisted stage stream ────

def test_the_compiler_stage_carries_the_councils_own_progress(wired):
    session, *_ = _run(wired)
    compiler = _stage(session, "compiler")

    labels = [s["label"] for s in compiler["substages"]]
    assert len(labels) > 5, labels
    # One event per pass entered and per pass left, plus one per dissector batch. Reported only at
    # the end, a stage that sat silent for four minutes is indistinguishable from one that hung.
    assert any("source units" in label for label in labels)
    assert any("batch" in label for label in labels)
    assert any("atoms" in label for label in labels)
    assert any("claims" in label for label in labels)
    # Every event is timed by the coordinator's clock. The council has none — nothing in that
    # package reads one, which is what makes a replay a byte comparison — so a substage minted
    # inside it would carry no `at`, and a progress list with no times has no order.
    assert all(s["at"] for s in compiler["substages"])


def test_the_compiler_stage_names_the_council_rather_than_reporting_no_producer(wired):
    """v2 leaves `provenance.compiler` null on purpose. The stage projection only knew that route,
    so a live five-pass council reported no model, no provider and no calls — which is exactly what
    an UNBOUND compiler looks like."""
    session, *_ = _run(wired)
    compiler = _stage(session, "compiler")

    assert compiler["call_topology"] == "council_passes"
    assert compiler["model"], "the compiler stage named no model for a council that used one"
    assert compiler["actual_calls"] and compiler["actual_calls"] > 0
    assert session["graph"]["provenance"]["compiler"] is None


def test_the_compiler_counts_line_names_the_dissolution(wired):
    """`31 reading blocks in → 4 claims out` was the whole story while one call did everything. A
    ledger and a dissection sit between them now, and a counts line that skipped them would put the
    phase's central artifact outside the sentence a person reads."""
    session, *_ = _run(wired)
    compiler = _stage(session, "compiler")

    for noun in ("source units", "atoms", "claims", "observables", "reading blocks"):
        assert noun in compiler["counts_line"], compiler["counts_line"]


def test_a_replay_reports_no_waiting_rather_than_zero(wired):
    """Nothing paced a replay. `waited_ms: 0` would say a pacer answered and reported no wait, and
    a rehearsal that could not tell those apart would report an unpaced run as one that never hit
    the limit — the null-duration law, one field over."""
    session, *_ = _run(wired)
    compiler = _stage(session, "compiler")

    assert "waited_ms" not in compiler["provenance"]
    assert "capacity_limited" not in compiler["provenance"]
    for received in session["graph"]["passes"]:
        assert received["waited_ms"] is None
        assert received["capacity_waits"] == []


# ── the fourth: it is all readable on the wire ──────────────────────────────

def test_the_dissolution_is_projected_through_the_canonical_session_view(wired):
    """`graph_view` sent none of these until this lane. Lane C wrote the normalisers against a shape
    nobody had produced, so the phase's central artifact was `disconnected_artifact` exactly."""
    session, *_ = _run(wired)
    graph = session["graph"]

    unit = graph["source_units"][0]
    # BOTH SPELLINGS. Lane A named the field `kind`; Lane C's normaliser reads `source_type`.
    assert unit["kind"] == unit["source_type"]
    assert unit["exact_quote"] and unit["source_unit_id"]

    atom = graph["semantic_atoms"][0]
    assert atom["text"] and atom["unit_kind"] and atom["source_unit_ids"]
    assert atom["epistemic_ceiling"] == "interpretive"

    entry = graph["coverage"][0]
    assert entry["source_unit_id"] and entry["disposition"]

    received = graph["passes"][0]
    assert received["pass_name"] and received["outcome"]


def test_the_coverage_summary_is_the_backends_arithmetic_over_its_own_ledger(wired):
    session, *_ = _run(wired)
    graph = session["graph"]
    summary = graph["coverage_summary"]

    assert summary["source_units"] == len(graph["source_units"])
    assert summary["disposed"] == len(graph["coverage"])
    assert summary["lost_count"] == 0 and summary["lost"] == []
    assert summary["complete"] is True
    assert summary["user_units"] + summary["reading_units"] == summary["source_units"]


def test_a_lost_source_unit_is_its_own_number_and_never_a_remainder():
    """The check most likely to be quietly softened later. A unit with no entry is one the compiler
    DROPPED; a remainder is a decision with a reason. Those two must not read alike, and the
    summary is where a surface would be tempted to fold them together."""
    summary = view.coverage_summary({
        "source_units": [{"source_unit_id": "u1", "kind": "prompt_clause"},
                         {"source_unit_id": "u2", "kind": "reading_block"}],
        "coverage": [{"source_unit_id": "u1", "disposition": "semantic_remainder"}]})

    assert summary["lost"] == ["u2"] and summary["lost_count"] == 1
    assert summary["by_disposition"] == {"semantic_remainder": 1}
    # A remainder is DISPOSED of and NOT represented. Three different numbers, three facts.
    assert summary["disposed"] == 1
    assert summary["represented"] == 0
    assert summary["complete"] is False


def test_a_v1_graph_declares_no_coverage_check_rather_than_failing_one():
    """`complete: False` on a v1 graph would accuse a compilation of failing a check it never made."""
    assert view.coverage_summary({})["complete"] is None


# ── the deployment badge ────────────────────────────────────────────────────

def test_every_response_says_what_produced_it(wired):
    client, _, _ = wired(FOLD)
    with client:
        created = _start(client, FOLD)
        assert created.status_code == 202
        # ON THE 202, before any stage has run. A badge that only appeared once the session
        # finished would leave the whole watched window unlabelled — which is the window a
        # screenshot is most likely to be taken in.
        assert created.json()["deployment"]["kind"] == "replay"
        assert created.json()["deployment"]["declared"] is True
        assert _settled(client, created)["deployment"]["kind"] == "replay"


def test_a_live_binding_badges_live_and_reports_reachability_separately(monkeypatch):
    """A live-bound deployment whose provider is down is still LIVE — it will produce `unavailable`
    stages and say so. Collapsing it into `fixture` would tell a reader that frozen payloads were
    used when nothing was used at all."""
    monkeypatch.setenv("SEMANT_INQUIRY_LIVE_MODELS", "1")
    monkeypatch.delenv("SEMANT_INQUIRY_COMPILER", raising=False)
    stages = runtime.build_stages()
    badge = runtime.deployment(stages)

    assert badge["kind"] == "live"
    assert badge["stages"] == {"theorist": "live", "compiler": "live"}
    assert badge["reachable"] in (True, False)


def test_a_deployment_with_no_model_bound_badges_fixture(monkeypatch):
    monkeypatch.setenv("SEMANT_INQUIRY_LIVE_MODELS", "0")
    badge = runtime.deployment(runtime.build_stages())
    assert badge["kind"] == "fixture"
    assert badge["stages"] == {"theorist": "unbound", "compiler": "unbound"}


def test_the_weaker_claim_wins_when_one_stage_is_frozen():
    """A live theorist with a frozen compiler is a REPLAY. What the person reads is not all live,
    and a badge naming the stronger half would be true about one stage and misleading about the
    session — the same rule the workbench applies to a fixture receipt claiming to be usable."""
    from backend.services.semantic_compilation.theorist import ModelSceneTheorist

    mixed = coordinator.Stages(theorist=ModelSceneTheorist(),
                               compiler=F.compiler_for(F.FIXTURES[0]))
    assert runtime.deployment(mixed)["kind"] == "replay"


def test_a_view_built_without_stages_says_nobody_asked_and_never_live():
    """`undeclared` is not a fourth kind of deployment — it is the absence of the answer. A missing
    key reads to every client as 'not implemented yet' and renders as nothing, which puts a replay
    and a live run back on one screen."""
    badge = runtime.deployment(None)
    assert badge["kind"] == "undeclared" and badge["declared"] is False
    session = coordinator.new_session(prompt="a question", refs=[], mode="auto")
    assert view.session_view(session)["deployment"]["kind"] == "undeclared"
    assert view.session_view(session)["deployment"]["declared"] is False


# ── picker / upload: an uploaded post is a normal selected post id ──────────

def test_an_uploaded_post_is_an_ordinary_selected_post(wired):
    """The picker's reconciliation, asserted where it matters rather than in the form.

    A freshly uploaded post reaches the route as an id like any other, is fingerprinted like any
    other, and is re-checked before every write like any other. There is no upload path through
    this API and there must not be one: a second shape for "an image I just made" would be a second
    thing that can drift from the corpus guarantee.
    """
    client, posts, _ = wired(FOLD)
    fresh = {"_id": "post_just_uploaded", "title": "",
             "photo_url": "https://fixture.invalid/post_just_uploaded.jpg",
             "region_annotations": [], "visual_marks": []}
    posts.docs[fresh["_id"]] = fresh

    with client:
        selected = [r.post_id for r in F.dissolution_post_refs(FOLD)] + [fresh["_id"]]
        session = _settled(client, _start(client, FOLD, mode="auto", image_ids=selected))

    ids = [p["post_id"] for p in session["posts"]]
    assert fresh["_id"] in ids
    uploaded = next(p for p in session["posts"] if p["post_id"] == fresh["_id"])
    assert uploaded["readable"] is True
    assert uploaded["fingerprint"], "an uploaded post was not fingerprinted like the others"


def test_the_create_route_returns_the_real_prompt_and_never_a_substitute(wired):
    """The directive's fifth build item. A replay deployment replays the MODELS, not the question —
    a rehearsal in which the surface showed a different prompt from the one that was typed would be
    testing a question nobody asked."""
    client, _, _ = wired(FOLD)
    typed = "a question nobody's fixture contains, typed by a person just now"
    with client:
        created = _start(client, FOLD, prompt=typed)
        assert created.status_code == 202
        body = created.json()
        assert body["prompt"] == typed
        assert body["graph"]["prompt"] in (typed, "")   # graph is empty until the compiler runs
        settled = _settled(client, created)

    assert settled["prompt"] == typed
    assert settled["graph"]["prompt"] == typed


# ── what a person can see while it runs ─────────────────────────────────────

def test_the_session_is_readable_while_the_council_is_still_working(wired):
    """002R's first finding, at the layer this lane added. The driver checkpoints around every
    stage, so a `GET` mid-run returns a document that MOVES rather than one that appears at the
    end — and now the compiler's own passes move inside it."""
    client, _, _ = wired(FOLD)
    seen = []
    with client:
        created = _start(client, FOLD, mode="auto")
        session_id = created.json()["session_id"]
        for _ in range(600):
            body = client.get(f"/api/v1/inquiries/{session_id}").json()
            seen.append((body["state"], len(body["stages"])))
            if body["state"] in _BOUNDARIES:
                break
            time.sleep(0.005)

    # The ledger grew while the person was watching. One frame means the whole chain happened
    # between two polls, which proves nothing about whether it COULD be watched.
    assert len({n for _, n in seen}) > 1, seen


def test_progress_reaches_the_store_while_the_stage_is_still_inside_its_call(wired):
    """The decision's `may not look frozen`, as a gate rather than a latency threshold.

    A threshold test would pass on a slow machine whatever the architecture did. So the compiler is
    HELD inside its call — its observer blocks on an event this test controls — and the assertion is
    that a `GET` issued while it is provably still in there already shows the council's progress.
    Before this lane the same `GET` returned `compiler · started` and nothing else, which is the
    same screen a hung process produces.
    """
    client, _, _ = wired(FOLD)
    reached = threading.Event()
    release = threading.Event()
    real_compile = DissolutionCompiler.compile

    def held(self, request, *, on_substage=None):
        def gated(label, **fields):
            if on_substage is not None:
                on_substage(label, **fields)
            # Hold once, AFTER the first event has been reported, so what the GET below observes is
            # a stage that has published progress and has not finished.
            if not reached.is_set():
                reached.set()
                release.wait(10)

        return real_compile(self, request, on_substage=gated)

    with client:
        with mock.patch.object(DissolutionCompiler, "compile", held):
            created = _start(client, FOLD, mode="auto")
            session_id = created.json()["session_id"]
            assert reached.wait(10), "the compiler never reported any progress"

            watching = client.get(f"/api/v1/inquiries/{session_id}").json()
            compiler = _stage(watching, "compiler")
            release.set()

        settled = _settled(client, created)

    assert compiler is not None, "the compiler stage was not in the ledger while it was running"
    assert compiler["outcome"] == "started", compiler["outcome"]
    assert compiler["substages"], "a stage held inside its call published no progress"
    assert compiler["substages"][0]["label"]
    # And the durable record still carries everything, not just what the tap flushed: the ledger
    # and the tap are fed together rather than as alternatives.
    assert len(_stage(settled, "compiler")["substages"]) > len(compiler["substages"])


def test_a_progress_write_that_loses_its_acknowledgement_cannot_cost_a_stage_its_result(wired):
    """The defect the first live fold rehearsal found, at the cost of a twenty-minute compilation.

    Atlas dropped this driver's connection mid-write, twice. A progress flush's write therefore
    LANDED and its acknowledgement did not, so the live tap went on believing a checkpoint it no
    longer held — and every later compare-and-set of its own was refused, the terminal one
    included. The council's graph was discarded and the session sat at `compiler · started` for
    good, with `SessionWriteFailed` saying "something else advanced it first". Something else was
    the driver's own progress tap.

    Reproduced rather than described: one flush applies its write and then raises as a dropped
    connection does. The assertion is that the compilation SURVIVED — the driver holds the lease,
    so a refused write can only be its own tap, and re-reading is the honest repair rather than a
    second writer being tolerated.
    """
    client, _, sessions = wired(FOLD)

    real_update = sessions.update_one
    armed, dropped = [], []

    async def loses_one_ack(query, update, upsert=False):
        result = await real_update(query, update, upsert=upsert)
        # The write is applied FIRST, then the reply is lost. A failure before the write would have
        # been no failure at all; THIS is the shape that desynchronises a caller from the truth.
        if armed and not dropped and "session.checkpoint" in query:
            dropped.append(query["session.checkpoint"])
            raise ConnectionError("connection closed")
        return result

    sessions.update_one = loses_one_ack

    real_compile = DissolutionCompiler.compile

    def reports_on_the_way_in(self, request, *, on_substage=None):
        # Armed only once the compiler is inside its call, so the write that loses its reply is a
        # PROGRESS flush rather than one of the driver's own.
        armed.append(True)
        if on_substage is not None:
            on_substage("the council is starting", outcome="started")
        return real_compile(self, request, on_substage=on_substage)

    with client:
        with mock.patch.object(DissolutionCompiler, "compile", reports_on_the_way_in):
            settled = _settled(client, _start(client, FOLD, mode="auto"))

    assert dropped, "no write lost its acknowledgement, so nothing was under test"
    compiler = _stage(settled, "compiler")
    assert compiler["outcome"] == "completed", compiler["outcome"]
    assert settled["state"] in _BOUNDARIES, settled["state"]
    # and the graph the council spent the whole stage building is in the document
    assert settled["graph"]["semantic_atoms"], "the compilation was written and then lost"
    assert settled["graph"]["passes"]


def test_an_answer_over_no_claim_is_not_a_closed_chain(wired):
    """The live fold rehearsal ended COMPLETE with `0 claims · 0 observables` on the same screen.

    Its stop reason read "the chain closed: every claim carries a verdict" — vacuously true, since
    there were no claims, and the exact sentence a person reads as success. The relation architect
    had failed on a 413 and every section the composer wrote rested on nothing.

    `exhausted` is the honest state, and `exhausted_reason` already names the stage that came up
    short. The composer is left alone: writing a "nothing to say" answer is its job, and the
    session's own state is where that gets called what it is.
    """
    client, _, _ = wired(FOLD)
    real_compile = DissolutionCompiler.compile

    def compiles_no_claim(self, request, *, on_substage=None):
        graph = real_compile(self, request, on_substage=on_substage)
        return graph.model_copy(update={"claims": [], "observables": []})

    with client:
        with mock.patch.object(DissolutionCompiler, "compile", compiles_no_claim):
            settled = _settled(client, _start(client, FOLD, mode="auto"))

    assert settled["graph"]["claims"] == []
    assert settled["state"] == "exhausted", settled["state"]
    assert "the chain closed" not in (settled["stop_reason"] or "")
    # and the reason names the stage rather than reporting a healthy chain
    assert settled["stop_reason"]


def test_the_stage_stream_reports_every_stage_the_chain_entered(wired):
    session, *_ = _run(wired)
    entered = [s["stage"] for s in session["stages"]]
    for stage in (StageName.FRAMER, StageName.THEORIST, StageName.COMPILER, StageName.STEWARD,
                  StageName.CAPABILITY, StageName.JUDGE, StageName.COMPOSER):
        assert stage.value in entered, entered


# ── the phase's declared absences, still absent ─────────────────────────────

def test_nothing_was_measured_and_the_corpus_did_not_move(wired):
    """Phase 1's one guarantee. A comparison rather than an assurance: the fingerprints are
    re-checked before every write, and this asserts the run ended with them intact."""
    session, client, posts, _ = _run(wired)

    assert session["evidence"] == []
    assert all(r["execution_mode"] == "fixture" for r in session["capability_receipts"])
    assert all(r["usable_as_evidence"] is not True for r in session["capability_receipts"])
    for post in session["posts"]:
        assert post["fingerprint"]
    # No post document was written by the inquiry — `FakeCollection` counts its own writes.
    assert posts.writes == 0
