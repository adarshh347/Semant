"""
HARNESS-002B — replay, the nine conflicts, and the things this layer must not be able to do.

Every test here is a way this layer would lie while every component underneath it stayed honest.
That is what makes them boundary tests: none of the modules below is wrong in any of these
scenarios, and the composition would be.

The structural scans at the end each have a paired NEGATIVE CONTROL proving the scan can fail. A
scan that matches nothing is indistinguishable from a scan pointed at the wrong directory, and this
repository has paid for that four times — most recently for a skip guarded on `find_spec` of a
module name that never existed, which would have skipped for the life of the repository.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from backend.schemas.inquiry_interaction import (STATUS_KEYS, EventKind, InteractionMode,
                                                 SessionState)
from backend.services.inquiry_interaction import conflicts as cf
from backend.services.inquiry_interaction import fixtures as fx
from backend.services.inquiry_interaction import machine as m
from backend.services.inquiry_interaction import policy as pol
from backend.services.inquiry_interaction import steward as stw
from backend.services.inquiry_interaction.policy import DeliberationPolicy

STAMP = fx.STAMP
LATER = "2026-01-01T00:05:00+00:00"


def steward(mode=InteractionMode.CONSULT):
    return stw.DeliberationSteward(policy=DeliberationPolicy(mode=mode))


def paused(mode=InteractionMode.CONSULT, candidates=None):
    st = steward(mode)
    state = m.open_session(session_id="inqs_1", mode=mode, at=STAMP, graph=fx.survey_graph())
    state = m.advance(state, SessionState.COMPILING, at=STAMP)
    return m.offer(state, candidates or [fx.survey_scope_candidate()], steward=st, at=STAMP), st


def answer(state, **over):
    base = {"response_id": "rsp_1", "session_id": state.session_id,
            "decision_id": state.open_decision_id, "expected_revision": state.revision,
            "kind": "select_option", "option_id": "opt_eastern", "at": LATER}
    base.update(over)
    return m.read_response(base)


# ── 1. replay ────────────────────────────────────────────────────────────────

def _full_session():
    """One consult session carrying a refused candidate, a pause, an answer, an amendment and a
    close — the ordinary shape, and most of the event vocabulary."""
    mode = InteractionMode.CONSULT
    st = steward(mode)
    state = m.open_session(session_id="inqs_1", mode=mode, at=STAMP, graph=fx.survey_graph())
    state = m.advance(state, SessionState.COMPILING, at=STAMP)
    state = m.offer(state, [{"id": "cnd_bad", "kind": "not_a_kind"}, *fx.survey_batch()],
                    steward=st, at=STAMP)
    state = m.respond(state, answer(state), steward=st, at=LATER)                    # select
    state = m.respond(state, answer(state, response_id="rsp_2", kind="amend", option_id="",
                                    free_text="southern wells only",
                                    amendment_target="clm_nitrate"), steward=st, at=LATER)
    state = m.advance(state, SessionState.READY, at=LATER)
    state = m.close(state, SessionState.COMPLETE, at=LATER)
    return state


def test_a_whole_session_replays_from_its_events_to_a_byte_identical_state():
    """The required proof. Nothing in an event payload is a snapshot of the state — each carries
    the semantic content of what it did — so a log that carried its own answer would pass this
    comparison while proving nothing about whether the events were sufficient."""
    state = _full_session()
    assert m.to_dict(m.replay(state.events)) == m.to_dict(state)


@pytest.mark.parametrize("mode", [InteractionMode.AUTO, InteractionMode.CONSULT,
                                  InteractionMode.STEP])
def test_replay_holds_in_every_mode(mode):
    st = steward(mode)
    state = m.open_session(session_id="inqs_1", mode=mode, at=STAMP, graph=fx.survey_graph())
    state = m.advance(state, SessionState.COMPILING, at=STAMP)
    state = m.offer(state, fx.survey_batch(), steward=st, at=STAMP)
    while state.state is SessionState.AWAITING_USER:
        state = m.respond(state, answer(state, response_id=f"rsp_{state.revision}",
                                        kind="reject_all", option_id=""), steward=st, at=LATER)
    assert m.to_dict(m.replay(state.events)) == m.to_dict(state)


class _AddsAnOption:
    """A formatter that always oversteps, so `formatter_refused` is reachable on demand."""
    name = "a_model_formatter"

    def format(self, draft, *, candidate):
        return {"options": [{"option_id": "opt_invented", "label": "x", "consequence": "y"}]}


def test_replay_covers_every_event_kind_the_machine_can_emit():
    """The negative control for the replay proof: if the exercised session used four of the eleven
    event kinds, 'replay is exact' would be a claim about four of them.

    So every kind is reached, across three sessions rather than one — three because
    `decision_unresolved` needs auto mode, `formatter_refused` needs a model formatter, and
    `response_refused` needs a caller that chose to record a refusal. Each is replayed too; a kind
    exercised and not replayed would satisfy this test while breaking the one above.
    """
    emitted = {e.kind for e in _full_session().events}

    auto_steward = steward(InteractionMode.AUTO)
    auto = m.close(m.offer(m.advance(m.open_session(session_id="inqs_2",
                                                    mode=InteractionMode.AUTO, at=STAMP,
                                                    graph=fx.survey_graph()),
                                     SessionState.COMPILING, at=STAMP),
                           fx.survey_batch(), steward=auto_steward, at=STAMP),
                   SessionState.COMPLETE, at=LATER)
    emitted |= {e.kind for e in auto.events}
    assert EventKind.DECISION_UNRESOLVED in emitted

    overstepping = stw.DeliberationSteward(policy=DeliberationPolicy(mode=InteractionMode.CONSULT),
                                           formatter=_AddsAnOption())
    formatted = m.offer(m.advance(m.open_session(session_id="inqs_1",
                                                 mode=InteractionMode.CONSULT, at=STAMP),
                                  SessionState.COMPILING, at=STAMP),
                        [fx.survey_scope_candidate()], steward=overstepping, at=STAMP)
    emitted |= {e.kind for e in formatted.events}

    noted = m.note_refusal(auto, cf.StaleRevision("late", expected=3, actual=1).as_refusal(at=LATER),
                           at=LATER)
    emitted |= {e.kind for e in noted.events}

    missing = sorted(k.value for k in set(EventKind) - emitted)
    assert not missing, f"never exercised, so replay says nothing about them: {missing}"

    for state in (auto, formatted, noted):
        assert m.to_dict(m.replay(state.events)) == m.to_dict(state)


def test_a_session_round_trips_through_plain_json_with_no_field_loss():
    state = _full_session()
    blob = json.dumps(m.to_dict(state))
    assert m.to_dict(m.from_dict(json.loads(blob))) == m.to_dict(state)


def test_two_identical_sessions_are_byte_identical_with_handed_timestamps():
    """No clock, no uuid, no database — so the only way two runs of one script could differ is a
    real difference, and the comparison needs no exclusion list at all."""
    assert m.to_dict(_full_session()) == m.to_dict(_full_session())


def test_replay_refuses_a_fragment_rather_than_inventing_the_beginning():
    state = _full_session()
    with pytest.raises(m.SessionMisuse, match="does not start at the beginning"):
        m.replay(state.events[1:])
    with pytest.raises(m.SessionMisuse, match="empty event list"):
        m.replay([])


# ── 2. the nine conflicts, each distinct ─────────────────────────────────────

def test_a_response_for_another_session_is_refused_before_anything_is_revealed():
    state, st = paused()
    with pytest.raises(cf.WrongSession) as exc:
        m.respond(state, answer(state, session_id="inqs_other"), steward=st, at=LATER)
    assert exc.value.code == cf.CONFLICT_WRONG_SESSION


def test_a_stale_revision_is_recoverable_and_says_so():
    """The one conflict where the right advice is 'do the same thing again'. Collapsing it into a
    mismatch would tell a person to retry a thing that will never work — or not to retry the one
    thing that would."""
    state, st = paused()
    with pytest.raises(cf.StaleRevision) as exc:
        m.respond(state, answer(state, expected_revision=state.revision - 1), steward=st, at=LATER)
    assert exc.value.recoverable is True
    assert exc.value.expected == state.revision and exc.value.actual == state.revision - 1


def test_a_duplicate_response_is_refused_as_a_duplicate_and_not_as_a_failure():
    state, st = paused(candidates=fx.survey_batch())
    once = m.respond(state, answer(state), steward=st, at=LATER)
    with pytest.raises(cf.DuplicateResponse) as exc:
        m.respond(once, answer(once, expected_revision=once.revision), steward=st, at=LATER)
    assert exc.value.recoverable is True


def test_an_answer_to_a_session_waiting_for_nothing_lands_nowhere():
    st = steward(InteractionMode.AUTO)
    state = m.advance(m.open_session(session_id="inqs_1", mode=InteractionMode.AUTO, at=STAMP),
                      SessionState.COMPILING, at=STAMP)
    with pytest.raises(cf.NoDecisionOpen):
        m.respond(state, m.read_response(
            {"response_id": "rsp_1", "session_id": "inqs_1", "decision_id": "dec_x",
             "expected_revision": state.revision, "kind": "reject_all", "at": LATER}),
            steward=st, at=LATER)


def test_an_answer_to_a_different_decision_is_not_reported_as_a_stale_revision():
    """Both would be 'try again' if collapsed, and only one of them is."""
    state, st = paused()
    with pytest.raises(cf.DecisionMismatch) as exc:
        m.respond(state, answer(state, decision_id="dec_somethingelse"), steward=st, at=LATER)
    assert exc.value.recoverable is False


def test_an_option_that_is_not_on_the_request_is_refused_by_name():
    state, st = paused()
    with pytest.raises(cf.UnknownOption) as exc:
        m.respond(state, answer(state, option_id="opt_whatever"), steward=st, at=LATER)
    assert exc.value.actual == "opt_whatever"
    assert set(exc.value.expected) == {"opt_eastern", "opt_district"}


def test_free_text_on_a_fork_that_does_not_take_it_is_refused():
    raw = dict(fx.survey_scope_candidate(), allow_free_text=False)
    state, st = paused(candidates=[raw])
    with pytest.raises(cf.FreeTextNotAllowed):
        m.respond(state, answer(state, free_text="actually, the western wells"), steward=st,
                  at=LATER)


@pytest.mark.parametrize("key", sorted(STATUS_KEYS))
def test_a_response_that_tries_to_assign_an_epistemic_status_is_its_own_conflict(key):
    """Refused at the door and typed, rather than left to the schema — the integration lane needs
    to tell this apart from a malformed body without pattern-matching a validation message."""
    with pytest.raises(cf.EpistemicStatusAttempted) as exc:
        m.read_response({"response_id": "rsp_1", "session_id": "inqs_1", "decision_id": "dec_1",
                         "expected_revision": 1, "kind": "reject_all", "at": LATER,
                         "provenance": {key: "measured"}})
    assert exc.value.code == cf.CONFLICT_EPISTEMIC_STATUS_ATTEMPTED


def test_a_malformed_response_is_not_reported_as_a_concurrency_conflict():
    """The negative control for the one above: a parse failure and a stale tab are different
    things, and a client told 'conflict' for a schema error would retry forever."""
    with pytest.raises(cf.ResponseMalformed):
        m.read_response({"response_id": "rsp_1", "session_id": "inqs_1", "decision_id": "dec_1",
                         "expected_revision": 1, "kind": "select_option", "at": LATER})


@pytest.mark.parametrize("mode", [InteractionMode.AUTO, InteractionMode.CONSULT,
                                  InteractionMode.STEP])
@pytest.mark.parametrize("raw", [fx.survey_ledger_candidate, fx.inventory_author_candidate],
                         ids=["accept_to_ledger", "author_action"])
def test_a_gate_cannot_be_settled_without_the_person_in_any_mode(mode, raw):
    """Reachable from exactly one direction, and it exists so that it is: an auto-mode loop
    draining its pending decisions is a reasonable thing to write for every kind except these
    two."""
    state, st = paused(mode, [raw()])
    assert state.state is SessionState.AWAITING_USER
    with pytest.raises(cf.GateBypass) as exc:
        m.resolve_without_user(state, option_id=state.open_decision.options[0].option_id,
                               reason="auto loop", steward=st, at=LATER)
    assert exc.value.code == cf.CONFLICT_GATE_BYPASS


def test_a_non_gate_pause_can_be_settled_without_the_person_by_a_surrounding_loop():
    """The negative control for the gate rule. If `resolve_without_user` refused everything, the
    test above would prove nothing about gates in particular."""
    state, st = paused(InteractionMode.STEP)
    resumed = m.resolve_without_user(state, option_id="opt_eastern",
                                     reason="the surrounding loop is in auto", steward=st,
                                     at=LATER)
    assert resumed.state is SessionState.COMPILING
    assert resumed.records[-1].outcome == m.OUTCOME_AUTO_RESOLVED
    assert resumed.records[-1].actor.value == "policy"
    assert m.to_dict(m.replay(resumed.events)) == m.to_dict(resumed)


def test_every_declared_conflict_code_has_a_type_that_can_actually_be_raised():
    """A code in the contract with no reachable type is a refusal the integration lane would map
    and never see."""
    raised = {cf.WrongSession, cf.StaleRevision, cf.DuplicateResponse, cf.NoDecisionOpen,
              cf.DecisionMismatch, cf.UnknownOption, cf.FreeTextNotAllowed,
              cf.EpistemicStatusAttempted, cf.GateBypass}
    assert {c.code for c in raised} == set(cf.CONFLICT_CODES)
    contract = pol.contract()["closed_sets"]["conflict_codes"]
    assert set(contract) == set(cf.CONFLICT_CODES)


def test_a_conflict_is_not_a_value_error():
    """A caller writing `except ValueError` around a parse would swallow a stale revision as
    though it were malformed input, and the client would be told to fix a request that was
    perfectly well formed and merely late."""
    assert not issubclass(cf.InteractionConflict, ValueError)
    assert issubclass(cf.StaleRevision, cf.InteractionConflict)


def test_a_refused_response_leaves_no_trace_unless_the_caller_records_one():
    """Both halves. A rejected answer that left no trace would make the session look as though it
    had never been offered one; a session that recorded every refusal automatically could be grown
    by anything that can reach the endpoint."""
    state, st = paused()
    before = len(state.events)
    with pytest.raises(cf.StaleRevision) as exc:
        m.respond(state, answer(state, expected_revision=99), steward=st, at=LATER)
    assert len(state.events) == before                      # the state is untouched

    noted = m.note_refusal(state, exc.value.as_refusal(at=LATER), at=LATER)
    assert noted.refusals[-1].code == cf.CONFLICT_STALE_REVISION
    assert noted.revision == state.revision                 # a refusal is not a turn


# ── 3. append-only ───────────────────────────────────────────────────────────

def test_nothing_in_the_machine_can_remove_or_rewrite_an_earlier_entry():
    """Structural. Every transition is a function returning a new state, and a session's history
    only ever grows — so this is checkable by comparing prefixes rather than by trusting the
    absence of a delete method."""
    st = steward()
    states = [m.advance(m.open_session(session_id="inqs_1", mode=InteractionMode.CONSULT,
                                       at=STAMP, graph=fx.survey_graph()),
                        SessionState.COMPILING, at=STAMP)]
    states.append(m.offer(states[-1], fx.survey_batch(), steward=st, at=STAMP))
    states.append(m.respond(states[-1], answer(states[-1]), steward=st, at=LATER))
    states.append(m.respond(states[-1], answer(states[-1], response_id="rsp_2", kind="skip",
                                               option_id=""), steward=st, at=LATER))
    for earlier, later in zip(states, states[1:]):
        head = [e.model_dump(mode="json") for e in later.events[:len(earlier.events)]]
        assert head == [e.model_dump(mode="json") for e in earlier.events]
        assert len(later.events) > len(earlier.events)
        for name in ("requests", "records", "responses", "amendments"):
            before = [x.model_dump(mode="json") for x in getattr(earlier, name)]
            after = [x.model_dump(mode="json") for x in getattr(later, name)]
            assert after[:len(before)] == before


def test_a_transition_does_not_mutate_the_state_it_was_handed():
    state, st = paused()
    snapshot = m.to_dict(state)
    m.respond(state, answer(state), steward=st, at=LATER)
    assert m.to_dict(state) == snapshot


def test_the_graph_snapshot_is_byte_identical_after_a_session_that_amended_it_three_times():
    """The mutation-safety gate, at this lane's scale. Amendments stand BESIDE the graph."""
    graph = fx.survey_graph()
    original = json.dumps(graph, sort_keys=True)
    st = steward(InteractionMode.STEP)
    state = m.advance(m.open_session(session_id="inqs_1", mode=InteractionMode.STEP, at=STAMP,
                                     graph=graph), SessionState.COMPILING, at=STAMP)
    state = m.offer(state, fx.survey_batch(), steward=st, at=STAMP)
    for i, target in enumerate(["clm_nitrate", "clm_drainage", "obs_series"]):
        state = m.respond(state, answer(state, response_id=f"rsp_{i}", kind="amend", option_id="",
                                        free_text=f"a person's note on {target}",
                                        amendment_target=target), steward=st, at=LATER)
    assert len(state.amendments) == 3
    assert json.dumps(state.graph.snapshot, sort_keys=True) == original
    assert json.dumps(graph, sort_keys=True) == original


# ── 4. structural scans, each with its negative control ──────────────────────

PACKAGE = pathlib.Path(m.__file__).parent


def _modules():
    return sorted(PACKAGE.glob("*.py"))


def test_no_module_in_this_package_touches_a_collection_or_the_database():
    forbidden = ("backend.database", "insert_one", "update_one", "delete_one", "find_one",
                 "get_collection", "motor")
    scanned = 0
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        scanned += 1
        for token in forbidden:
            assert token not in source, f"{path.name} references {token!r}"
    assert scanned >= 7, f"the scan only saw {scanned} module(s) — it is pointed somewhere wrong"


def test_no_module_in_this_package_names_a_topic():
    """The board's rule: no production branch names Ottoman, Pantheon, Ajanta, sculpture, fold or
    nestedness as a special topic. `fixtures.py` is exempt because a fixture's whole job is to have
    a subject; the point is that no POLICY reads one."""
    scanned = 0
    for path in _modules():
        if path.name == "fixtures.py":
            continue
        source = path.read_text(encoding="utf-8").lower()
        scanned += 1
        for word in ("ottoman", "pantheon", "ajanta", "sculpture", "nestedness", "drapery"):
            assert word not in source, f"{path.name} names the topic {word!r}"
    assert scanned >= 6, f"the scan only saw {scanned} module(s) — it is pointed somewhere wrong"


def test_that_database_scan_can_actually_fail():
    """The negative control. `run_store` DOES write to a collection."""
    from backend.services import run_store
    source = pathlib.Path(run_store.__file__).read_text(encoding="utf-8")
    assert "insert_one" in source and "update_one" in source


def test_no_module_in_this_package_reads_a_clock():
    """Every timestamp is handed in. A session that read a clock could not be replayed, and the
    byte-comparison would have to exclude the field it exists to check."""
    forbidden = ("datetime.now", "utcnow", "time.time", "uuid4", "uuid1", "random.")
    scanned = 0
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        scanned += 1
        for token in forbidden:
            assert token not in source, f"{path.name} reads {token!r}"
    assert scanned >= 7


def test_that_clock_scan_can_actually_fail():
    """The negative control. `run_store.utc_now` really does read one."""
    from backend.services import run_store
    source = pathlib.Path(run_store.__file__).read_text(encoding="utf-8")
    assert "datetime.now" in source


def test_no_module_in_this_package_reaches_a_language_model():
    """The formatter is a Protocol. Whoever binds a model supplies it; this package never calls
    one, which is why the deterministic path is what CI runs."""
    scanned = 0
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        scanned += 1
        for token in ("import groq", "from groq", "llm_service", "openai", "anthropic", "httpx",
                      "import requests", "requests.post", "requests.get"):
            assert token not in source, f"{path.name} reaches a model: {token!r}"
    assert scanned >= 7


def test_that_model_scan_can_actually_fail():
    """The negative control. `llm_service` really does reach one."""
    from backend.services import llm_service
    source = pathlib.Path(llm_service.__file__).read_text(encoding="utf-8")
    assert "groq" in source.lower()


#: The branch this guard was written to police. HARNESS-002D had to add it.
#:
#: The check below compares the WHOLE diff against `origin/main` to Lane B's write set. That was
#: right while Lane B was unmerged and its branch was the only thing that diff could contain. Once
#: it merged, `origin/main` moved to include it and the diff became "everything the current branch
#: changed" — so the guard started failing on every later branch in the repository, for the correct
#: reason that no other lane's work is inside Lane B's write set.
#:
#: A lane-ownership assertion that outlives its lane is a tripwire pointed at whoever comes next.
#: Scoping it to its own branch keeps the guarantee exactly where it means something and removes it
#: everywhere it never did. Nothing about what Lane B is allowed to touch has changed.
_THIS_LANES_BRANCH = "feat/inquiry-deliberation"


def test_this_lane_does_not_edit_another_lanes_files():
    """The board's ownership boundary, asserted rather than remembered. Lane B owns four paths;
    everything else in the tree is someone else's to change.

    Only meaningful ON Lane B's branch — see `_THIS_LANES_BRANCH`.
    """
    import subprocess
    root = pathlib.Path(__file__).resolve().parents[2]
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            cwd=root, capture_output=True, text=True)
    if branch.returncode != 0:
        pytest.skip(f"git unavailable: {branch.stderr.strip()[:120]}")
    if branch.stdout.strip() != _THIS_LANES_BRANCH:
        pytest.skip(f"this guard polices {_THIS_LANES_BRANCH!r}; HEAD is "
                    f"{branch.stdout.strip()!r}, whose write set is somebody else's to declare")
    diff = subprocess.run(["git", "diff", "--name-only", "origin/main...HEAD"],
                          cwd=root, capture_output=True, text=True)
    if diff.returncode != 0:                    # no git, or a detached checkout — say so, skip
        pytest.skip(f"git diff unavailable: {diff.stderr.strip()[:120]}")
    # `splitlines`, not `split`: a path containing a space would become two paths, and
    # each half would look like a file outside the lane.
    touched = [f for f in diff.stdout.splitlines() if f.strip()]
    if not touched:
        pytest.skip("no diff against origin/main — nothing to check ownership of")
    allowed = ("contracts/inquiry-interaction.v1.json",
               "backend/schemas/inquiry_interaction.py",
               "backend/services/inquiry_interaction/",
               "backend/tests/test_inquiry_interaction_")
    stray = [f for f in touched if not f.startswith(allowed)]
    assert not stray, f"outside this lane's write set: {stray}"


def test_no_router_or_frontend_file_is_reachable_from_this_package():
    """Phase-1 boundary: routes, persistence and UI are the integration lane's. A stray import
    here would make this package impossible to merge before them."""
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        for token in ("fastapi", "APIRouter", "HTTPException", "backend.routers",
                      "backend.main"):
            assert token not in source, f"{path.name} reaches the transport layer: {token!r}"


def test_the_recommended_session_store_is_stated_rather_than_left_to_a_reader():
    """A recommendation only in prose is one a persistence lane can miss — the goal engine's
    lesson, carried forward."""
    import backend.services.inquiry_interaction as pkg
    assert pkg.RECOMMENDED_SESSION_STORE == "runs"
    assert pkg.RECOMMENDED_SESSION_STORE_MODULE == "backend.services.run_store"
    from backend.services.inquiry_engine import RECOMMENDED_RUN_STORE
    # The same store as its sibling object, deliberately. Two session stores would reproduce
    # exactly the drift the previous wave removed.
    assert pkg.RECOMMENDED_SESSION_STORE == RECOMMENDED_RUN_STORE
