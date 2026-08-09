"""
HARNESS-003B — the driver: return before the work, checkpoint through it, survive being killed.

THE TEST THIS FILE IS ARRANGED AROUND is `test_the_post_returns_while_a_stage_is_still_blocked`. It
holds a stage open on a barrier and asserts the POST has already come back. Every other proof here
is downstream of that one: if the request still waited for the chain, nothing about progress,
checkpoints or streams would be observable at all — which is exactly the state 002R found.

Nothing here reads a wall clock for anything it asserts on. Stage timestamps come from a controlled
clock so a duration is a comparison rather than a measurement of how busy the test machine was.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import inquiries as R
from backend.schemas.inquiry_session import SemanticInquirySession, StageName
from backend.schemas.inquiry_stage import StageAttemptOutcome
from backend.services.inquiry_session import corpus, driver, steps, store
from backend.services.inquiry_session.capability import LockedFixtureCapability
from backend.services.inquiry_session.composer import DeterministicComposer
from backend.services.inquiry_session.judge import judge
from backend.tests.fixtures import inquiry_session_fixtures as F

FIXTURE = "cross-image-comparison"
BOUNDARIES = ("awaiting_user", "complete", "exhausted", "refused", "error")


class Clock:
    """A clock that advances only when something asks it to.

    Handed to `Stages`, so every `queued_at`/`started_at`/`completed_at` in these tests is a
    controlled value. A duration measured against the wall would be a measurement of the CI
    machine's load, and the one thing it could never fail on is the case this lane cares about —
    an unknown duration reported as zero.
    """

    def __init__(self, step_ms: int = 1000):
        self.ticks = 0
        self.step_ms = step_ms

    def __call__(self) -> str:
        self.ticks += 1
        total_ms = self.ticks * self.step_ms
        return f"2026-01-01T00:{total_ms // 60000:02d}:{(total_ms // 1000) % 60:02d}" \
               f".{total_ms % 1000:03d}+00:00"


@pytest.fixture
def wired(monkeypatch):
    """The inquiry routes with every boundary faked and a controlled clock on the stages."""
    posts = F.post_collection_for(FIXTURE)
    sessions = F.FakeCollection()
    monkeypatch.setattr(store, "_collection", lambda collection=None: sessions)

    _real_resolve = corpus.resolve

    async def _resolve(post_ids, *, collection=None):
        return await _real_resolve(post_ids, collection=posts)

    monkeypatch.setattr(corpus, "resolve", _resolve)

    state = {"clock": Clock(), "gate": None, "entered": threading.Event()}

    def _stages():
        built = F.stages_for(FIXTURE, capability=LockedFixtureCapability(), judge=judge,
                             composer=DeterministicComposer())
        if state["gate"] is not None:
            built = _gated(built, state["gate"], state["entered"])
        return built.__class__(**{**built.__dict__, "clock": state["clock"]})

    monkeypatch.setattr(R, "_stages", _stages)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/inquiries")
    with TestClient(app) as client:
        yield client, sessions, state
    driver._TASKS.clear()


def _gated(stages, gate: threading.Event, entered: threading.Event):
    """Wrap the theorist so it blocks until the test lets it go."""
    inner = stages.theorist

    class _Held:
        def __init__(self):
            self.last_finish_reason = ""
            self.truncated_calls = 0

        def read(self, *args, **kwargs):
            entered.set()
            assert gate.wait(timeout=10), "the gated stage was never released"
            return inner.read(*args, **kwargs)

    return stages.__class__(**{**stages.__dict__, "theorist": _Held()})


def _post(client, mode="consult"):
    return client.post("/api/v1/inquiries", json={
        "prompt": F.prompt_for(FIXTURE), "mode": mode,
        "image_ids": [r.post_id for r in F.post_refs(FIXTURE)]})


def _settle(client, session_id, tries=400):
    for _ in range(tries):
        body = client.get(f"/api/v1/inquiries/{session_id}").json()
        if body.get("state") in BOUNDARIES:
            return body
        time.sleep(0.005)
    raise AssertionError(f"{session_id} never settled; last state {body.get('state')!r}")


# ── 1. the POST returns before the work ──────────────────────────────────────

def test_the_post_returns_while_a_stage_is_still_blocked(wired):
    """THE LANE'S CENTRAL PROOF. The theorist is held open; the POST has already answered.

    A deliberately blocked stage rather than a slow one, because a timing threshold would pass on a
    fast machine whatever the architecture did. The gate is the assertion: the response exists
    while the stage provably has not returned.
    """
    client, _, state = wired
    gate, entered = threading.Event(), threading.Event()
    state["gate"], state["entered"] = gate, entered

    started = time.monotonic()
    res = _post(client)
    first_response_ms = (time.monotonic() - started) * 1000.0

    assert res.status_code == 202, res.text
    session_id = res.json()["session_id"]

    assert entered.wait(timeout=5), "the driver never entered the theorist"
    assert not gate.is_set(), "the gate is still shut — the stage has not returned"

    # And the session is READABLE while that stage is held.
    mid = client.get(f"/api/v1/inquiries/{session_id}").json()
    assert mid["state"] not in BOUNDARIES
    running = [s for s in mid["stages"] if s["outcome"] == "started"]
    assert running and running[0]["stage"] == "theorist", (
        f"a blocked stage must be visible as `started`; got {[s['stage'] for s in mid['stages']]}")

    gate.set()
    final = _settle(client, session_id)
    assert final["state"] == "awaiting_user"
    # Reported rather than asserted against a threshold: the gate above is the proof, and a
    # millisecond bound here would only ever fail on a loaded machine.
    print(f"\nfirst-response latency with a blocked theorist: {first_response_ms:.1f} ms")


def test_the_framer_is_already_done_while_the_theorist_is_held(wired):
    """The negative control for the test above. If NOTHING had run behind the response, a POST that
    returned quickly would prove only that the handler did nothing at all."""
    client, _, state = wired
    gate, entered = threading.Event(), threading.Event()
    state["gate"], state["entered"] = gate, entered

    session_id = _post(client).json()["session_id"]
    assert entered.wait(timeout=5)
    mid = client.get(f"/api/v1/inquiries/{session_id}").json()
    framer = [s for s in mid["stages"] if s["stage"] == "framer"]
    assert framer and framer[0]["outcome"] == "completed", (
        "the framer runs before the theorist; work is happening behind the response")
    gate.set()
    _settle(client, session_id)


# ── 2. checkpoints survive a reload ──────────────────────────────────────────

def test_every_checkpoint_is_in_the_store_and_not_only_in_memory(wired):
    """Nothing in this process is the sole record. The stage ledger is read back from the document
    itself, not from the session object the driver was holding."""
    client, sessions, state = wired
    gate, entered = threading.Event(), threading.Event()
    state["gate"], state["entered"] = gate, entered

    session_id = _post(client).json()["session_id"]
    assert entered.wait(timeout=5)

    stored = SemanticInquirySession.model_validate(sessions.docs[session_id]["session"])
    assert steps.status_of(stored, StageName.FRAMER) == "done"
    assert steps.status_of(stored, StageName.THEORIST) == "running"
    assert stored.checkpoint > 0

    gate.set()
    _settle(client, session_id)
    after = SemanticInquirySession.model_validate(sessions.docs[session_id]["session"])
    assert after.checkpoint > stored.checkpoint
    assert steps.status_of(after, StageName.THEORIST) == "done"


def test_a_stage_that_completed_is_never_re_entered(wired):
    """Idempotence, read from the store. `plan` is asked the same question twice about the same
    document and must not offer a stage whose attempt is already terminal."""
    client, sessions, _ = wired
    session_id = _post(client).json()["session_id"]
    _settle(client, session_id)

    stored = SemanticInquirySession.model_validate(sessions.docs[session_id]["session"])
    entered = [s.stage.value for s in stored.stages]
    assert entered.count("theorist") == 1
    assert entered.count("compiler") == 1
    assert steps.plan(stored).stage is None


# ── 3. a duplicate schedule enters a stage once ──────────────────────────────

def test_scheduling_the_same_session_twice_does_not_run_a_stage_twice(wired):
    client, sessions, state = wired
    gate, entered = threading.Event(), threading.Event()
    state["gate"], state["entered"] = gate, entered

    session_id = _post(client).json()["session_id"]
    assert entered.wait(timeout=5)

    # A second POST for the same body mints a different session (the id carries a clock), so the
    # duplicate is scheduled directly — the shape a second worker or a retried job would take.
    stages = R._stages()

    async def _second():
        return await driver.drive(session_id, stages, driver_id="drv_second")

    report = client.portal.call(_second) if hasattr(client, "portal") else None
    if report is not None:
        assert report.claimed is False
        assert "another driver holds this session" in report.reason

    gate.set()
    _settle(client, session_id)
    stored = SemanticInquirySession.model_validate(sessions.docs[session_id]["session"])
    assert [s.stage.value for s in stored.stages].count("theorist") == 1


def test_a_lease_is_a_compare_and_set_on_the_document(wired):
    """Not a registry in this process. A registry is correct in one worker and silently wrong in
    two, and the second worker is the one that would make a second model call."""
    client, sessions, _ = wired
    session_id = _post(client).json()["session_id"]
    _settle(client, session_id)

    async def _race():
        first = await driver.claim(session_id, "drv_a", at="2026-01-01T00:00:00+00:00")
        second = await driver.claim(session_id, "drv_b", at="2026-01-01T00:00:01+00:00")
        return first, second

    first, second = client.portal.call(_race)
    assert first is not None, "the first claim must take the lease"
    assert second is None, "the second claim must be refused while the first holds it"


# ── 4. a crash is visible and is not silently retried ────────────────────────

def _crashed_session(client, sessions, state):
    """A session whose theorist attempt is `started` and whose driver never came back."""
    gate, entered = threading.Event(), threading.Event()
    state["gate"], state["entered"] = gate, entered
    session_id = _post(client).json()["session_id"]
    assert entered.wait(timeout=5)
    stored = SemanticInquirySession.model_validate(sessions.docs[session_id]["session"])
    gate.set()
    _settle(client, session_id)
    return session_id, stored


def test_an_interrupted_stage_is_visible_and_is_not_re_run(wired):
    """A `started` attempt with no terminal successor is the crash signature. Reopening it records
    `interrupted` and STOPS — a model call is not idempotent, and re-entering one would charge
    twice for a result the session may already have had."""
    client, sessions, state = wired
    _, crashed = _crashed_session(client, sessions, state)

    assert steps.interrupted_stages(crashed) == ("theorist",)
    assert steps.plan(crashed).stage is None, "a dangling attempt must stop the chain"
    assert "may have happened" in steps.plan(crashed).reason

    reopened = steps.reopen(crashed, at="2026-01-01T01:00:00+00:00")
    theorist = [a for a in reopened.stages if a.stage is StageName.THEORIST]
    assert theorist[-1].outcome is StageAttemptOutcome.INTERRUPTED
    assert "not repeated" in theorist[-1].summary
    # The evidence a reader needs about whether the call landed: how long the process was inside it.
    assert theorist[-1].started_at == theorist[0].started_at or theorist[-1].started_at is not None
    assert steps.plan(reopened).stage is None


def test_a_reopened_session_settles_to_error_rather_than_to_a_quiet_exhausted(wired):
    """An abandoned inquiry is not a finished one. Reporting it as `exhausted` would put a crash in
    the same box as a prompt that decomposed into nothing."""
    client, sessions, state = wired
    _, crashed = _crashed_session(client, sessions, state)
    reopened = steps.reopen(crashed, at="2026-01-01T01:00:00+00:00")
    settled = steps.settle(reopened, R._stages())
    assert settled.state == "error"


# ── 5. duration is measured or absent, never zero ────────────────────────────

def test_a_stage_duration_uses_the_handed_clock(wired):
    client, sessions, _ = wired
    session_id = _post(client).json()["session_id"]
    _settle(client, session_id)
    stored = SemanticInquirySession.model_validate(sessions.docs[session_id]["session"])

    measured = [a for a in stored.stages if a.duration_ms is not None]
    assert measured, "no stage recorded a duration at all"
    for attempt in measured:
        assert attempt.started_at and attempt.completed_at
        # The clock advances 1000ms per read, so a real elapsed value is a multiple of it — a
        # duration read from the wall would be some arbitrary sub-millisecond number.
        assert attempt.duration_ms >= 1000.0, (
            f"{attempt.stage.value} reports {attempt.duration_ms}ms; the controlled clock advances "
            f"1000ms per read, so this came from somewhere else")


def test_an_unmeasured_duration_stays_null_through_the_projection(wired):
    """The null-duration law where a person actually looks.

    Exercised on a v1 session, which is the real population of unmeasured attempts: every stage
    written before HARNESS-003B recorded no clocks at all. A projection substituting 0 for those
    would render the entire history of this system as a sequence of instantaneous stages.
    """
    client, sessions, _ = wired
    session_id = _post(client).json()["session_id"]
    _settle(client, session_id)

    # Rewrite the stored document as a v1 one, exactly as it would have been persisted before this
    # lane — the v1 field names, and none of the timing fields that did not exist.
    doc = sessions.docs[session_id]
    doc["session"]["schema_version"] = "semantic-inquiry-session.v1"
    doc["session"]["stages"] = [
        {"event_id": s["attempt_id"], "stage": s["stage"],
         "outcome": s["outcome"] if s["outcome"] in
                    ("started", "completed", "empty", "unavailable", "refused", "skipped", "error")
                    else "completed",
         "at": s["queued_at"], "revision": s["revision"], "detail": s["summary"],
         "input_refs": s["input_refs"], "output_refs": s["output_refs"]}
        for s in doc["session"]["stages"]]

    view = client.get(f"/api/v1/inquiries/{session_id}").json()
    assert view["stages"], "the v1 session must still open"
    for stage in view["stages"]:
        assert stage["duration_ms"] is None, (
            f"{stage['stage']} was written before durations existed and reports "
            f"{stage['duration_ms']}ms")
        assert stage["started_at"] is None and stage["completed_at"] is None
        assert stage["provenance"]["upgraded_from"].startswith("semantic-inquiry-session.v1")
    # And the counts an old attempt never carried are ABSENT rather than zero.
    assert all(s["input_counts"] == {} and s["output_counts"] == {} for s in view["stages"])


def test_a_v1_session_still_opens_with_its_history_intact(wired):
    """The compatibility reader, end to end. The stages a v1 session recorded are all still there
    and still say what they said — a bumped envelope that refused them would lose every session
    written before this lane."""
    client, sessions, _ = wired
    session_id = _post(client).json()["session_id"]
    settled = _settle(client, session_id)
    before = [(s["stage"], s["outcome"]) for s in settled["stages"]]

    doc = sessions.docs[session_id]
    doc["session"]["schema_version"] = "semantic-inquiry-session.v1"
    doc["session"]["stages"] = [
        {"event_id": s["attempt_id"], "stage": s["stage"], "outcome": s["outcome"],
         "at": s["queued_at"], "revision": s["revision"], "detail": s["summary"],
         "input_refs": s["input_refs"], "output_refs": s["output_refs"]}
        for s in settled["stages"]]

    reopened = client.get(f"/api/v1/inquiries/{session_id}").json()
    assert [(s["stage"], s["outcome"]) for s in reopened["stages"]] == before
    assert reopened["state"] == settled["state"]


# ── 6. GET and the stream agree ──────────────────────────────────────────────

def _frames(body: str):
    """Every `data:` frame in a completed SSE body.

    The stream is read to COMPLETION rather than iterated and broken out of. Breaking out mid-body
    leaves the generator parked in its `asyncio.sleep` while the test thread tries to close the
    response, and TestClient deadlocks — an artefact of the harness rather than of the stream, but
    one that hangs a suite for as long as anybody lets it.
    """
    import json as _json
    return [_json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def test_the_stream_and_the_poll_serve_the_same_session_at_the_same_revision(wired):
    """Parity. A client that cannot hold a stream open must not get a different, thinner truth."""
    client, _, _ = wired
    session_id = _post(client).json()["session_id"]
    settled = _settle(client, session_id)

    frames = _frames(client.get(f"/api/v1/inquiries/{session_id}/events").text)
    assert frames, "the stream sent nothing"
    streamed = frames[-1]
    polled = client.get(f"/api/v1/inquiries/{session_id}").json()
    assert streamed == polled, "the stream and the poll disagree about the same session"
    assert streamed["revision"] == settled["revision"]


def test_the_stream_reports_stage_transitions_while_the_work_proceeds(wired):
    """started → terminal, observed through the stream rather than reconstructed after it closed.

    The gate is what makes this deterministic: released from a separate thread once the stream is
    already open, so the frames must contain the in-flight state. Without it the fixture chain
    finishes before the first tick and the stream would legitimately have one frame to send.
    """
    client, _, state = wired
    gate, entered = threading.Event(), threading.Event()
    state["gate"], state["entered"] = gate, entered
    session_id = _post(client).json()["session_id"]
    assert entered.wait(timeout=5), "the driver never entered the theorist"

    threading.Timer(0.9, gate.set).start()
    frames = _frames(client.get(f"/api/v1/inquiries/{session_id}/events").text)

    seen = [{(s["stage"], s["outcome"]) for s in f["stages"]} for f in frames]
    assert seen, "the stream sent nothing"
    assert ("theorist", "started") in seen[0], (
        f"the first frame must show the blocked stage running, not an empty ledger; got {seen[0]}")
    assert any(("theorist", "completed") in frame for frame in seen), (
        "the stream never showed the theorist finishing")
    assert frames[-1]["state"] in BOUNDARIES, "the stream closed before a boundary"


def test_the_stream_stays_open_through_the_working_states(wired):
    """The old stop list was written when the handler returned finished sessions. A stream opened
    during work would have closed on the first state it did not recognise — the exact window it
    exists to show."""
    working = set(R._WORKING_STATES)
    stops = set(R._STREAM_STOPS_AT)
    assert not (working & stops), f"a working state is also a stop: {sorted(working & stops)}"
    from backend.schemas.inquiry_interaction import SessionState
    assert working | stops == {s.value for s in SessionState}, (
        "every declared session state must be either a working state or a stop; an unclassified "
        "one would close the stream by falling through")


# ── 7. an answer cannot race a running stage ─────────────────────────────────

def test_an_answer_posted_while_a_stage_runs_is_refused_and_not_lost(wired):
    client, _, state = wired
    gate, entered = threading.Event(), threading.Event()
    state["gate"], state["entered"] = gate, entered
    session_id = _post(client).json()["session_id"]
    assert entered.wait(timeout=5)

    res = client.post(f"/api/v1/inquiries/{session_id}/decisions",
                      json={"decision_id": "dec_whatever", "action": "select",
                            "selected_option_id": "opt_x"})
    assert res.status_code == 409
    body = res.json()["detail"]
    assert body["error"] == "session_busy"
    assert body["recoverable"] is True
    # The person's words come back untouched, exactly as the nine typed conflicts already do.
    assert body["submitted"]["selected_option_id"] == "opt_x"

    gate.set()
    _settle(client, session_id)


# ── 8. only inquiry documents move ───────────────────────────────────────────

def test_the_driver_writes_nothing_but_the_session_document(wired):
    client, sessions, _ = wired
    session_id = _post(client).json()["session_id"]
    _settle(client, session_id)
    assert set(sessions.docs) == {session_id}
    assert sessions.docs[session_id]["kind"] == "semantic_inquiry"


# ── 9. substage progress: the declared floor, and the injected observer ──────

def test_the_theorist_attempt_reports_the_selected_image_count_without_being_told(wired):
    """THE FLOOR. Whatever a stage says about its own insides, the coordinator holds the count of
    what it selected and the topology the stage declared — so 002R's opaque four-image wait is
    reportable even against a theorist that never learns to narrate."""
    client, sessions, _ = wired
    session_id = _post(client).json()["session_id"]
    _settle(client, session_id)

    view = client.get(f"/api/v1/inquiries/{session_id}").json()
    theorist = next(s for s in view["stages"] if s["stage"] == "theorist")
    assert theorist["input_counts"]["images"] == len(F.post_refs(FIXTURE))
    assert theorist["call_topology"], "the declared topology must reach the ledger"
    assert theorist["actual_calls"] is not None
    assert any(sub["total"] == len(F.post_refs(FIXTURE)) for sub in theorist["substages"]), (
        f"the selected-image floor is missing; got {theorist['substages']}")


def test_a_stage_that_declares_it_wants_an_observer_is_given_one(wired, monkeypatch):
    """The seam Lane D binds. Opt-in by DECLARATION — `wants_substage_observer = True` — rather
    than by introspecting the callee's signature, which would silently start feeding an observer to
    any stage that grew a `**kwargs`."""
    client, sessions, state = wired
    reported = []

    def _stages():
        built = F.stages_for(FIXTURE, capability=LockedFixtureCapability(), judge=judge,
                             composer=DeterministicComposer())
        inner = built.theorist

        class _Narrating:
            wants_substage_observer = True
            last_finish_reason = ""
            truncated_calls = 0

            def read(self, prompt, images, *, on_substage, **kw):
                for i, image in enumerate(images, start=1):
                    on_substage(f"reading image {i}", index=i, total=len(images),
                                refs=[image.post_id])
                    reported.append(i)
                return inner.read(prompt, images, **kw)

        return built.__class__(**{**built.__dict__, "theorist": _Narrating(),
                                  "clock": state["clock"]})

    monkeypatch.setattr(R, "_stages", _stages)
    session_id = _post(client).json()["session_id"]
    _settle(client, session_id)

    assert reported == list(range(1, len(F.post_refs(FIXTURE)) + 1))
    view = client.get(f"/api/v1/inquiries/{session_id}").json()
    theorist = next(s for s in view["stages"] if s["stage"] == "theorist")
    labels = [sub["label"] for sub in theorist["substages"]]
    assert "reading image 1" in labels and f"reading image {len(reported)}" in labels
    assert all(sub["total"] == len(reported) for sub in theorist["substages"]
               if sub["label"].startswith("reading image"))


def test_a_stage_that_declares_nothing_is_not_handed_an_observer(wired):
    """The negative control. The default fixture theorist takes no `on_substage` keyword, and would
    raise if the coordinator guessed that it did."""
    client, _, _ = wired
    stages = R._stages()
    from backend.services.inquiry_session import coordinator as C
    assert C._wants_observer(stages.theorist) is False
    session_id = _post(client).json()["session_id"]
    assert _settle(client, session_id)["state"] == "awaiting_user"


def test_the_coordinator_never_imports_a_compiler_internal_to_find_progress():
    """Structural. A stage runner that knew what a scene theorist was made of could not be reused
    for the next stage, and would break every time that lane refactored."""
    import ast
    import pathlib as _p

    from backend.services.inquiry_session import coordinator as C
    tree = ast.parse(_p.Path(C.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    internals = {m for m in imported
                 if m.startswith("backend.services.semantic_compilation.")
                 and m.rsplit(".", 1)[-1] in ("theorist", "compiler")}
    assert not internals, f"the coordinator reaches into a stage's implementation: {internals}"
