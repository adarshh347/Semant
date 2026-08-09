"""
HARNESS-002D — the routes: ask, read, answer, and the nine ways an answer is refused.

Every test here drives HTTP. The coordinator is exercised through the same door a browser uses, so
a projection that works in Python and not on the wire fails here rather than in a rehearsal.
"""
from __future__ import annotations

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import inquiries as R
from backend.services.inquiry_session import corpus, store
from backend.tests.fixtures import inquiry_session_fixtures as F

FIXTURE = "cross-image-comparison"


@pytest.fixture
def wired(monkeypatch):
    """A minimal app holding only the inquiry routes, with every boundary faked.

    Mounted WITHOUT the API-key dependency: what is under test is the route, and an auth wrapper it
    does not own would only be re-testing `require_api_key`.
    """
    posts = F.post_collection_for(FIXTURE)
    sessions = F.FakeCollection()

    monkeypatch.setattr(store, "_collection", lambda collection=None: sessions)

    async def _resolve(post_ids, *, collection=None):
        return await _real_resolve(post_ids, collection=posts)

    _real_resolve = corpus.resolve
    monkeypatch.setattr(corpus, "resolve", _resolve)

    stages = {"mode": "fixture"}

    def _stages():
        return F.stages_for(FIXTURE, **{k: v for k, v in stages.items() if k != "mode"})

    monkeypatch.setattr(R, "_stages", _stages)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/inquiries")
    with TestClient(app) as client:
        yield client, posts, sessions


def _start(client, mode="consult", **over):
    body = {"prompt": F.prompt_for(FIXTURE), "mode": mode,
            "image_ids": [r.post_id for r in F.post_refs(FIXTURE)]}
    body.update(over)
    return client.post("/api/v1/inquiries", json=body)


def _open_decision(session):
    return next((d for d in session["decision_requests"] if not d["answered"]), None)


def _answer(client, session, *, option_index=0, response_id="r1", **over):
    decision = _open_decision(session)
    body = {"decision_id": decision["decision_id"], "response_id": response_id,
            "action": "select", "selected_option_id": decision["options"][option_index]["option_id"],
            "expected_revision": session["revision"]}
    body.update(over)
    return client.post(f"/api/v1/inquiries/{session['session_id']}/decisions", json=body)


# ── creation ─────────────────────────────────────────────────────────────────

def test_a_question_and_some_pictures_become_a_session_that_stops_at_a_fork(wired):
    client, _, sessions = wired
    res = _start(client)
    assert res.status_code == 200, res.text
    session = res.json()

    assert session["session_id"].startswith("inqs_")
    assert session["state"] == "awaiting_user"
    assert session["graph"]["claims"], "the fixture compiles claims; the route lost them"
    assert _open_decision(session) is not None
    assert session["session_id"] in sessions.docs


def test_the_prompt_survives_the_round_trip_byte_for_byte(wired):
    client, _, _ = wired
    prompt = "  Whitespace, an em—dash, and a \"quote\" that must not be tidied.  "
    session = _start(client, prompt=prompt).json()
    # `.strip()` is the route's ONE normalisation and it is applied before anything reads it, so
    # every source span in the graph indexes into the stripped string.
    assert session["prompt"] == prompt.strip()
    assert session["graph"]["prompt"] == prompt.strip()


def test_an_inquiry_with_no_question_or_no_pictures_is_refused_rather_than_started(wired):
    client, _, _ = wired
    assert _start(client, prompt="   ").status_code == 422
    assert _start(client, image_ids=[]).status_code == 422


def test_an_unknown_mode_names_the_ones_that_exist(wired):
    client, _, _ = wired
    res = _start(client, mode="whatever")
    assert res.status_code == 422
    assert "consult" in res.text and "auto" in res.text


def test_post_ids_that_resolve_to_nothing_stop_the_inquiry_before_any_model_runs(wired):
    client, _, sessions = wired
    res = _start(client, image_ids=["not-a-post", "also-not"])
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "no_readable_post"
    assert not sessions.docs, "a session was persisted for an inquiry that could not read anything"


def test_both_spellings_of_the_selection_are_read_and_neither_is_load_bearing(wired):
    client, _, _ = wired
    ids = [r.post_id for r in F.post_refs(FIXTURE)]
    a = _start(client, image_ids=ids, post_ids=[]).json()
    b = _start(client, image_ids=[], post_ids=ids).json()
    assert [p["post_id"] for p in a["posts"]] == [p["post_id"] for p in b["posts"]]


def test_the_same_id_repeated_under_both_names_selects_one_post(wired):
    client, _, _ = wired
    ids = [r.post_id for r in F.post_refs(FIXTURE)]
    session = _start(client, image_ids=ids, post_ids=ids).json()
    assert [p["post_id"] for p in session["posts"]] == ids


# ── reading ──────────────────────────────────────────────────────────────────

def test_a_session_reads_back_identically_to_the_body_that_created_it(wired):
    client, _, _ = wired
    created = _start(client).json()
    fetched = client.get(f"/api/v1/inquiries/{created['session_id']}").json()
    assert fetched == created


def test_an_unknown_session_is_a_404_and_not_an_empty_session(wired):
    client, _, _ = wired
    assert client.get("/api/v1/inquiries/inqs_nothing").status_code == 404


def test_a_director_run_id_cannot_be_read_as_an_inquiry(wired):
    """The discriminator, at the route. Without it a run document would load, find no session
    payload, and produce a validation error that reads as a corrupt inquiry."""
    client, _, sessions = wired
    sessions.docs["run_1"] = {"_id": "run_1", "status": "running", "view": {}}
    assert client.get("/api/v1/inquiries/run_1").status_code == 404


def test_the_listing_carries_only_inquiries(wired):
    client, _, sessions = wired
    _start(client)
    sessions.docs["run_1"] = {"_id": "run_1", "status": "running", "view": {}}
    listed = client.get("/api/v1/inquiries").json()["sessions"]
    assert [s["session_id"] for s in listed] and "run_1" not in [s["session_id"] for s in listed]


# ── the answer, and the same session resuming ────────────────────────────────

def test_answering_resumes_the_same_session_at_a_higher_revision(wired):
    client, _, _ = wired
    session = _start(client).json()
    before = session["revision"]

    res = _answer(client, session)
    assert res.status_code == 200, res.text
    after = res.json()

    assert after["session_id"] == session["session_id"], "answering minted a new session"
    assert after["revision"] > before
    assert _open_decision(after) is None
    assert after["decision_records"], "a settled fork left no record"


def test_the_pre_answer_trace_is_a_byte_identical_prefix_of_the_one_after(wired):
    """Append-only, checked rather than asserted. A history that could be rewritten by an answer
    would make every earlier claim about what happened unfalsifiable."""
    client, _, _ = wired
    session = _start(client).json()
    before = copy.deepcopy(session["trace"])
    after = _answer(client, session).json()["trace"]

    assert len(after) >= len(before)
    assert after[:len(before)] == before


def test_the_stage_ledger_is_also_append_only(wired):
    client, _, _ = wired
    session = _start(client).json()
    before = copy.deepcopy(session["stages"])
    after = _answer(client, session).json()["stages"]
    assert after[:len(before)] == before


def test_a_settled_record_names_who_chose_and_what_they_chose(wired):
    client, _, _ = wired
    session = _start(client).json()
    decision = _open_decision(session)
    chosen = decision["options"][0]

    record = _answer(client, session).json()["decision_records"][0]
    assert record["decider"] == "user"
    assert record["action"] == "select_option"
    assert record["selected_option_id"] == chosen["option_id"]
    assert record["selected_label"] == chosen["label"]
    assert record["rationale"], "a settled fork with no reason is a fork nobody can review"


def test_a_free_text_answer_is_kept_verbatim_on_the_record(wired):
    client, _, _ = wired
    session = _start(client).json()
    words = "Neither of these — look at the thresholds instead."
    after = _answer(client, session, action="redirect", selected_option_id="",
                    free_text=words).json()
    assert after["decision_records"][0]["free_text"] == words


# ── auto mode ────────────────────────────────────────────────────────────────

def test_auto_mode_does_not_interrupt_and_still_records_the_fork_it_reached(wired):
    """Auto mode means no interruption, not no decisions.

    With NO capability adapter bound — which is this commit's state — every option is undeclared,
    so the honest outcome is `unresolved` with the policy's reason attached, not a silent choice.
    The `auto_resolved` case arrives with the adapter, and has its own test there.
    """
    client, _, _ = wired
    session = _start(client, mode="auto").json()

    assert session["state"] != "awaiting_user"
    assert _open_decision(session) is None
    records = session["decision_records"]
    assert records, "an uninterrupted session with no decisions in it is invisible agency"
    assert records[0]["decider"] == "policy"
    assert records[0]["outcome"] == "unresolved"
    assert records[0]["rationale"], "nobody chose, and nothing says why"


# ── the conflicts ────────────────────────────────────────────────────────────

def test_a_stale_revision_is_a_409_that_keeps_the_persons_words(wired):
    client, _, _ = wired
    session = _start(client).json()
    res = _answer(client, session, expected_revision=session["revision"] - 1,
                  free_text="the words I typed")
    assert res.status_code == 409
    body = res.json()["detail"]
    assert body["error"] == "stale_revision"
    assert body["recoverable"] is True
    assert body["submitted"]["free_text"] == "the words I typed"
    assert body["session"]["session_id"] == session["session_id"]


def test_a_retried_post_is_a_duplicate_and_says_nothing_was_lost(wired):
    client, _, _ = wired
    session = _start(client).json()
    answered = _answer(client, session, response_id="same").json()

    again = client.post(f"/api/v1/inquiries/{session['session_id']}/decisions",
                        json={"decision_id": _open_decision(session)["decision_id"],
                              "response_id": "same", "action": "select",
                              "selected_option_id": _open_decision(session)["options"][0]["option_id"],
                              "expected_revision": session["revision"]})
    assert again.status_code == 409
    body = again.json()["detail"]
    assert body["error"] == "duplicate_response"
    assert body["recoverable"] is True
    assert body["session"]["revision"] == answered["revision"]


def test_a_response_written_for_another_session_is_applied_to_neither(wired):
    """The path names the session, so a client that believed otherwise would otherwise have its
    belief silently corrected into agreement with the URL."""
    client, _, _ = wired
    session = _start(client).json()
    decision = _open_decision(session)
    res = client.post(f"/api/v1/inquiries/{session['session_id']}/decisions", json={
        "decision_id": decision["decision_id"], "response_id": "r1", "action": "select",
        "selected_option_id": decision["options"][0]["option_id"],
        "expected_revision": session["revision"],
        "session_id": "inqs_somebody_elses"})
    assert res.status_code == 409
    body = res.json()["detail"]
    assert body["error"] == "wrong_session"
    assert body["actual"] == "inqs_somebody_elses"
    # Not applied to the session it WAS posted to, either.
    assert _open_decision(client.get(f"/api/v1/inquiries/{session['session_id']}").json())


def test_an_unsolicited_answer_lands_nowhere_and_is_told_so(wired):
    client, _, _ = wired
    session = _start(client, mode="auto").json()
    res = client.post(f"/api/v1/inquiries/{session['session_id']}/decisions", json={
        "decision_id": "dec_nothing", "response_id": "r1", "action": "select",
        "selected_option_id": "alt_something", "expected_revision": session["revision"]})
    assert res.status_code == 409
    assert res.json()["detail"]["error"] == "no_decision_open"


def test_the_four_recoverable_conflicts_have_four_distinct_bodies(wired):
    """Distinct CODES, distinct advice, distinct recoverability — not one 'conflict' for all."""
    client, _, _ = wired
    bodies = []

    stale = _answer(client, _start(client).json(), expected_revision=0)
    bodies.append(stale.json()["detail"])

    session = _start(client).json()
    _answer(client, session, response_id="dup")
    dup = client.post(f"/api/v1/inquiries/{session['session_id']}/decisions",
                      json={"decision_id": _open_decision(session)["decision_id"],
                            "response_id": "dup", "action": "select",
                            "selected_option_id": _open_decision(session)["options"][0]["option_id"],
                            "expected_revision": session["revision"]})
    bodies.append(dup.json()["detail"])

    auto = _start(client, mode="auto").json()
    unsolicited = client.post(f"/api/v1/inquiries/{auto['session_id']}/decisions",
                              json={"decision_id": "dec_none", "response_id": "r",
                                    "action": "select", "selected_option_id": "alt_x",
                                    "expected_revision": auto["revision"]})
    bodies.append(unsolicited.json()["detail"])

    elsewhere = _start(client).json()
    wrong = _answer(client, elsewhere, session_id="inqs_elsewhere")
    bodies.append(wrong.json()["detail"])

    assert [r.status_code for r in (stale, dup, unsolicited, wrong)] == [409, 409, 409, 409]
    codes = [b["error"] for b in bodies]
    assert sorted(codes) == ["duplicate_response", "no_decision_open", "stale_revision",
                             "wrong_session"]
    assert len({b["detail"] for b in bodies}) == len(bodies), "two conflicts give one explanation"


def test_an_option_that_is_not_on_the_request_is_a_422_and_not_a_409(wired):
    """The distinction that costs most if lost: 409 means try again, 422 means never this way."""
    client, _, _ = wired
    session = _start(client).json()
    res = _answer(client, session, selected_option_id="alt_invented")
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "unknown_option"


def test_a_preference_has_nowhere_to_put_a_kind_of_knowing(wired):
    """Lane B refuses a response whose provenance carries a status. This route goes one further:
    the wire model has no provenance field at all, so the status is dropped at the door and cannot
    reach the object Lane B would have to check. A refusal that can never fire is the goal here —
    the conflict stays typed for callers that build a response in Python."""
    client, _, sessions = wired
    session = _start(client).json()
    decision = _open_decision(session)
    res = client.post(f"/api/v1/inquiries/{session['session_id']}/decisions", json={
        "decision_id": decision["decision_id"], "response_id": "r1", "action": "select",
        "selected_option_id": decision["options"][0]["option_id"],
        "expected_revision": session["revision"],
        "provenance": {"epistemic_status": "measured"}})
    assert res.status_code == 200

    stored = sessions.docs[session["session_id"]]["session"]["interaction"]
    assert stored["responses"], "the answer was not recorded at all"
    assert all(not r.get("provenance") for r in stored["responses"]), \
        "a person's preference arrived carrying a kind of knowing"


# ── nothing is accepted ──────────────────────────────────────────────────────

def test_a_whole_inquiry_leaves_every_source_post_byte_identical(wired):
    client, posts, _ = wired
    before = copy.deepcopy(posts.docs)
    session = _start(client).json()
    _answer(client, session)
    assert posts.docs == before
    assert posts.writes == 0, "an inquiry wrote to the corpus it was reading"


def test_the_only_document_an_inquiry_writes_is_its_own_history(wired):
    client, _, sessions = wired
    session = _start(client).json()
    _answer(client, session)
    assert set(sessions.docs) == {session["session_id"]}
    assert all(d["kind"] == store.KIND for d in sessions.docs.values())


def test_a_mutated_post_stops_the_write_rather_than_being_recorded(wired):
    client, posts, _ = wired
    session = _start(client).json()
    first = next(iter(posts.docs))
    posts.docs[first]["title"] = "edited underneath the inquiry"
    res = _answer(client, session)
    assert res.status_code == 500
    assert res.json()["detail"]["error"] == "posts_mutated"


def test_no_evidence_object_exists_anywhere_in_phase_one(wired):
    client, _, _ = wired
    session = _start(client).json()
    after = _answer(client, session).json()
    assert after["evidence"] == []
