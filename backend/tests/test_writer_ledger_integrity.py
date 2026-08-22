"""
Semant Writer · ATLAS-WRITER-MASS-BUILD-001D — ledger integrity.

The gate, as behaviour:

  1. twenty simultaneous Accepts of one passage make ONE block and ONE v1;
  2. twenty simultaneous revision Accepts make ONE next version and ONE pointer move;
  3. every injected failure leaves a recoverable, internally consistent state — and the
     retry finishes the job without a duplicate;
  4. a retired operator still resolves old provenance exactly and refuses new invocation;
  5. a unique index over duplicate rows fails LOUDLY with a repair report, discarding none;
  6. after a multi-paragraph render no two canon nodes claim one block identity.

THE FAKE YIELDS. `test_writer_w1.FakeCollection` is synchronous inside its `async def`s, so
twenty gathered coroutines would run one after another and a race could never happen. The
`Yielding` subclass sleeps (0) before every database call, which is the smallest thing that
makes the interleaving real: all twenty read the passage as `quarantined`, all twenty try to
claim it, and the claim is what has to hold.
"""
from __future__ import annotations

import asyncio

import pytest

from backend.services import manuscript_service as ms_svc
from backend.services.writer import instrument
from backend.services.writer import ledger
from backend.services.writer import library as lib
from backend.services.writer import operators as op_svc
from backend.services.writer import passages as psg_svc
from backend.services.writer import readings as rdg
from backend.services.writer import relations as rel_mod
from backend.services.writer import render as render_svc
from backend.services.writer import revisions as rev
from backend.services.writer import studio
from backend.services.writer.render import OK, REFUSED, RenderResult
from backend.tests.test_writer_w1 import FakeCollection, run

PROJECT = "ms_ledger"
N = 20


class Yielding(FakeCollection):
    """The fake, with a scheduling point before every call. See the module docstring."""

    async def insert_one(self, doc):
        await asyncio.sleep(0)
        return await super().insert_one(doc)

    async def find_one(self, query, projection=None):
        await asyncio.sleep(0)
        return await super().find_one(query, projection)

    async def update_one(self, query, update, upsert=False, array_filters=None):
        await asyncio.sleep(0)
        return await super().update_one(query, update, upsert=upsert, array_filters=array_filters)


@pytest.fixture
def store(monkeypatch):
    cols = {name: Yielding() for name in (
        "operators", "passages", "usage", "versions", "readings", "library", "operations",
        "manuscripts", "scenes", "snapshots")}
    monkeypatch.setattr(op_svc, "writer_operator_collection", cols["operators"])
    monkeypatch.setattr(psg_svc, "writer_passage_collection", cols["passages"])
    monkeypatch.setattr(instrument, "writer_usage_collection", cols["usage"])
    monkeypatch.setattr(rev, "writer_passage_version_collection", cols["versions"])
    monkeypatch.setattr(rdg, "writer_reading_collection", cols["readings"])
    monkeypatch.setattr(lib, "writer_library_collection", cols["library"])
    monkeypatch.setattr(ledger, "writer_operation_collection", cols["operations"])
    monkeypatch.setattr(ms_svc, "manuscript_collection", cols["manuscripts"])
    monkeypatch.setattr(ms_svc, "scene_collection", cols["scenes"])
    monkeypatch.setattr(ms_svc, "scene_version_collection", cols["snapshots"])
    ledger.FAILPOINTS.disarm()
    ledger.FAILPOINTS.tripped.clear()
    yield cols
    ledger.FAILPOINTS.disarm()


#: The plan's collection names → this fixture's fakes, for `ensure_indexes`/`integrity_report`.
def _overrides(store):
    return {
        "writer_operator_collection": store["operators"],
        "writer_library_collection": store["library"],
        "writer_passage_collection": store["passages"],
        "writer_passage_version_collection": store["versions"],
        "writer_reading_collection": store["readings"],
        "writer_usage_collection": store["usage"],
        "writer_operation_collection": store["operations"],
        "scene_collection": store["scenes"],
        "scene_version_collection": store["snapshots"],
        "manuscript_collection": store["manuscripts"],
        "writer_register_collection": FakeCollection(),
    }


@pytest.fixture
def indexed(store):
    run(ledger.ensure_indexes(_overrides(store)))
    return store


@pytest.fixture
def book(indexed):
    async def build():
        m = await ms_svc.manuscript_service.create_manuscript("Ledger fixture")
        m = await ms_svc.manuscript_service.add_chapter(m["id"], "One")
        scene = await ms_svc.manuscript_service.add_scene(m["id"], m["chapters"][0]["id"], "Scene")
        return {"manuscript_id": m["id"], "scene_id": scene["id"]}
    return run(build())


def _provenance(*names, intents=()):
    return {
        "operators": [{"name": n, "version": 1, "source": "direct"} for n in names],
        "intents": [{"key": k, "value": v} for k, v in intents],
        "directive": "/ " + " + ".join(names),
    }


def quarantine(text, book, provenance=None):
    result = RenderResult(status=OK, text=text, provenance=provenance or _provenance("threshold"),
                          model="stub")
    return run(psg_svc.passage_store.quarantine(
        PROJECT, result, manuscript_id=book["manuscript_id"], scene_id=book["scene_id"]))


def scene_of(book):
    return run(ms_svc.manuscript_service.get_scene(book["scene_id"]))


def consistent(store):
    """The invariants every test ends on, whatever happened in the middle."""
    report = run(ledger.integrity_report(_overrides(store)))
    assert report["dangling_pointers"] == [], report
    assert report["duplicate_block_ids"] == [], report
    assert report["duplicates"] == {}, report
    return report


# ══ 1. twenty simultaneous Accepts ═══════════════════════════════════════════

def test_twenty_simultaneous_accepts_make_one_block_and_one_v1(book, indexed):
    psg = quarantine("The latch gave.", book)

    async def storm():
        return await asyncio.gather(*[
            psg_svc.passage_store.accept(psg["id"]) for _ in range(N)])
    results = run(storm())

    assert len({r["block_id"] for r in results}) == 1
    assert len({r["lineage_id"] for r in results}) == 1
    assert all(r["version"] == 1 for r in results)
    assert [b["id"] for b in scene_of(book)["blocks"]] == [results[0]["block_id"]]
    assert len(indexed["versions"].docs) == 1
    assert len(indexed["operations"].docs) == 1
    assert run(psg_svc.passage_store.get(psg["id"]))["status"] == psg_svc.ACCEPTED
    accepts = [d for d in indexed["usage"].docs.values() if d["event"] == instrument.ACCEPT]
    assert len(accepts) == 1
    assert consistent(indexed)["stuck_operations"] == []


def test_twenty_simultaneous_dismisses_converge(book, indexed):
    psg = quarantine("The latch gave.", book)

    async def storm():
        return await asyncio.gather(*[
            psg_svc.passage_store.dismiss(psg["id"], "no") for _ in range(N)])
    results = run(storm())
    assert all(r["status"] == psg_svc.DISMISSED for r in results)
    assert scene_of(book)["blocks"] == []
    dismissals = [d for d in indexed["usage"].docs.values() if d["event"] == instrument.DISMISS]
    assert len(dismissals) == 1


def test_accept_and_dismiss_racing_yields_exactly_one_decision(book, indexed):
    psg = quarantine("The latch gave.", book)

    async def race():
        return await asyncio.gather(
            *[psg_svc.passage_store.accept(psg["id"]) for _ in range(10)],
            *[psg_svc.passage_store.dismiss(psg["id"]) for _ in range(10)],
            return_exceptions=True)
    results = run(race())
    status = run(psg_svc.passage_store.get(psg["id"]))["status"]
    assert status in (psg_svc.ACCEPTED, psg_svc.DISMISSED)
    errors = [r for r in results if isinstance(r, Exception)]
    assert errors and all(isinstance(e, psg_svc.PassageError) for e in errors)
    blocks = scene_of(book)["blocks"]
    assert len(blocks) == (1 if status == psg_svc.ACCEPTED else 0)


# ══ 2. twenty simultaneous revision Accepts ══════════════════════════════════

def _commit_v1(book):
    psg = quarantine("The latch gave.", book)
    return run(psg_svc.passage_store.accept(psg["id"]))


def test_twenty_simultaneous_revision_accepts_make_one_v2_and_one_pointer_move(book, indexed):
    v1 = _commit_v1(book)
    psg = quarantine("The latch gave, twice.", book,
                     _provenance("threshold", intents=(("goal", "x"),)))
    moves_before = len(indexed["operations"].docs)

    async def storm():
        return await asyncio.gather(*[
            psg_svc.passage_store.accept_revision(
                psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
                block_id=v1["block_id"]) for _ in range(N)])
    results = run(storm())

    assert all(r["version"]["version"] == 2 for r in results)
    assert len({r["version"]["id"] for r in results}) == 1
    history = run(rev.version_store.history(v1["lineage_id"]))
    assert [v["version"] for v in history] == [1, 2]
    block = scene_of(book)["blocks"][0]
    assert block["version"] == 2 and block["content"] == "The latch gave, twice."
    assert len(scene_of(book)["blocks"]) == 1
    assert len(indexed["operations"].docs) == moves_before + 1
    consistent(indexed)


def test_two_different_re_renders_of_one_lineage_commit_one_v2_and_refuse_the_other(book, indexed):
    v1 = _commit_v1(book)
    a = quarantine("Version A.", book, _provenance("threshold", intents=(("goal", "a"),)))
    b = quarantine("Version B.", book, _provenance("threshold", intents=(("goal", "b"),)))

    async def race():
        return await asyncio.gather(
            psg_svc.passage_store.accept_revision(
                a["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
                block_id=v1["block_id"]),
            psg_svc.passage_store.accept_revision(
                b["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
                block_id=v1["block_id"]),
            return_exceptions=True)
    results = run(race())
    wins = [r for r in results if not isinstance(r, Exception)]
    losses = [r for r in results if isinstance(r, Exception)]
    assert len(wins) == 1 and len(losses) == 1
    assert isinstance(losses[0], rev.RevisionError)
    assert "already has a v2" in str(losses[0])
    history = run(rev.version_store.history(v1["lineage_id"]))
    assert [v["version"] for v in history] == [1, 2]
    # The loser is back in quarantine, with the reason, for the author to re-open.
    loser = next(p for p in (a, b) if p["text"] != wins[0]["version"]["text"])
    loser_doc = run(psg_svc.passage_store.get(loser["id"]))
    assert loser_doc["status"] == psg_svc.QUARANTINED
    assert "already has a v2" in loser_doc["refused"]
    consistent(indexed)


def test_twenty_simultaneous_loop_closures_record_one_outcome(book, indexed):
    v1 = _commit_v1(book)
    psg = quarantine("Again.", book, _provenance("threshold", intents=(("goal", "x"),)))
    out = run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"], in_response_to={"flag_id": "flg_1", "element": "intent:goal"}))
    version_id = out["version"]["id"]
    reading = {"id": "rdg_1", "flags": []}

    async def storm():
        return await asyncio.gather(*[rev.close_loop(version_id, reading) for _ in range(N)])
    results = run(storm())
    assert all(r["loop_outcome"]["outcome"] == rev.CLEARED for r in results)
    closed = [d for d in indexed["usage"].docs.values() if d["event"] == rev.LOOP_CLOSED]
    assert len(closed) == 1
    # A later closure with a different reading does not rewrite the recorded outcome.
    later = run(rev.close_loop(version_id, {"id": "rdg_2", "flags": [{"element": "intent:goal"}]}))
    assert later["loop_outcome"]["outcome"] == rev.CLEARED
    assert later["loop_outcome"]["reading_id"] == "rdg_1"


def test_twenty_simultaneous_adoptions_of_a_pre_w8_block_make_one_lineage(book, indexed):
    """A block committed before W8 has no lineage. Twenty prepares at once adopt it ONCE."""
    blocks = [{"id": "blk_old", "type": "paragraph", "content": "Old prose.", "color": None,
               "origin": "user_confirmed", "provenance": _provenance("threshold")}]
    run(ms_svc.manuscript_service.update_scene(book["scene_id"], {"blocks": blocks}))

    async def storm():
        return await asyncio.gather(*[
            rev.prepare(PROJECT, book["scene_id"], "blk_old") for _ in range(N)])
    results = run(storm())
    assert len({r["lineage_id"] for r in results}) == 1
    assert len(indexed["versions"].docs) == 1
    assert scene_of(book)["blocks"][0]["lineage_id"] == results[0]["lineage_id"]
    assert scene_of(book)["blocks"][0]["version"] == 1
    consistent(indexed)


# ══ 3. failure injection: every seam ═════════════════════════════════════════

ACCEPT_SEAMS = ("accept.claim", "accept.version_insert", "accept.scene_write",
                "accept.passage_mark", "instrument")


@pytest.mark.parametrize("seam", ACCEPT_SEAMS)
def test_an_accept_that_dies_at_any_seam_is_recoverable_and_consistent(book, indexed, seam):
    psg = quarantine("The latch gave.", book)
    ledger.FAILPOINTS.arm(seam)

    if seam == "instrument":
        # Write-behind: the failure is swallowed and the commit is unaffected.
        first = run(psg_svc.passage_store.accept(psg["id"]))
        assert ledger.FAILPOINTS.tripped == ["instrument"]
        assert first["block_id"] in [b["id"] for b in scene_of(book)["blocks"]]
        assert not [d for d in indexed["usage"].docs.values() if d["event"] == instrument.ACCEPT]
        consistent(indexed)
        return

    with pytest.raises(ledger.InjectedFailure):
        run(psg_svc.passage_store.accept(psg["id"]))

    # BETWEEN FAILURE AND RETRY: consistent. Never a block pointing at a missing version;
    # never an `accepted` passage without its block; never prose in canon before the
    # version that accounts for it.
    doc = run(psg_svc.passage_store.get(psg["id"]))
    assert doc["status"] in (psg_svc.QUARANTINED, psg_svc.ACCEPTING)
    assert doc["status"] != psg_svc.ACCEPTED
    report = consistent(indexed)
    if seam != "accept.claim":
        assert doc["status"] == psg_svc.ACCEPTING
        assert len(report["stuck_operations"]) == 1
        assert report["stuck_operations"][0]["step"] == seam.split(".", 1)[1]
    for block in scene_of(book)["blocks"]:
        assert (block["lineage_id"], 1) in {
            (v["lineage_id"], v["version"]) for v in indexed["versions"].docs.values()}

    # THE RETRY FINISHES THE JOB from the same plan: one block, one version, one op.
    again = run(psg_svc.passage_store.accept(psg["id"]))
    assert again["version"] == 1
    assert [b["id"] for b in scene_of(book)["blocks"]] == [again["block_id"]]
    assert len(indexed["versions"].docs) == 1
    assert len(indexed["operations"].docs) == 1
    assert run(psg_svc.passage_store.get(psg["id"]))["status"] == psg_svc.ACCEPTED
    assert consistent(indexed)["stuck_operations"] == []
    if seam != "accept.claim":
        # The ids the first attempt planned are the ids the retry used.
        assert doc["plan"]["block_id"] == again["block_id"]


REVISION_SEAMS = ("accept_revision.claim", "revision.version_insert", "revision.pointer_move",
                  "accept_revision.passage_mark")


@pytest.mark.parametrize("seam", REVISION_SEAMS)
def test_a_revision_that_dies_at_any_seam_is_recoverable_and_consistent(book, indexed, seam):
    v1 = _commit_v1(book)
    psg = quarantine("The latch gave, twice.", book,
                     _provenance("threshold", intents=(("goal", "x"),)))
    kwargs = dict(lineage_id=v1["lineage_id"], scene_id=book["scene_id"], block_id=v1["block_id"])
    ledger.FAILPOINTS.arm(seam)

    with pytest.raises(ledger.InjectedFailure):
        run(psg_svc.passage_store.accept_revision(psg["id"], **kwargs))

    block = scene_of(book)["blocks"][0]
    versions = {(v["lineage_id"], v["version"]) for v in indexed["versions"].docs.values()}
    assert (block["lineage_id"], block["version"]) in versions          # pointer never dangles
    if seam in ("accept_revision.claim", "revision.version_insert"):
        assert block["version"] == 1 and block["content"] == "The latch gave."
    consistent(indexed)

    again = run(psg_svc.passage_store.accept_revision(psg["id"], **kwargs))
    assert again["version"]["version"] == 2
    history = run(rev.version_store.history(v1["lineage_id"]))
    assert [v["version"] for v in history] == [1, 2]
    block = scene_of(book)["blocks"][0]
    assert block["version"] == 2 and block["content"] == "The latch gave, twice."
    assert len(scene_of(book)["blocks"]) == 1
    assert run(psg_svc.passage_store.get(psg["id"]))["status"] == psg_svc.ACCEPTED
    assert consistent(indexed)["stuck_operations"] == []


def test_a_dismiss_that_dies_leaves_the_passage_quarantined_and_retries_cleanly(book, indexed):
    psg = quarantine("The latch gave.", book)
    ledger.FAILPOINTS.arm("dismiss.passage_mark")
    with pytest.raises(ledger.InjectedFailure):
        run(psg_svc.passage_store.dismiss(psg["id"]))
    assert run(psg_svc.passage_store.get(psg["id"]))["status"] == psg_svc.QUARANTINED
    out = run(psg_svc.passage_store.dismiss(psg["id"]))
    assert out["status"] == psg_svc.DISMISSED


def test_a_loop_closure_that_dies_records_nothing_and_retries_cleanly(book, indexed):
    v1 = _commit_v1(book)
    psg = quarantine("Again.", book, _provenance("threshold", intents=(("goal", "x"),)))
    out = run(psg_svc.passage_store.accept_revision(
        psg["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"], in_response_to={"flag_id": "flg_1", "element": "intent:goal"}))
    ledger.FAILPOINTS.arm("loop.close")
    with pytest.raises(ledger.InjectedFailure):
        run(rev.close_loop(out["version"]["id"], {"id": "r", "flags": []}))
    assert run(rev.version_store.get(out["version"]["id"]))["loop_outcome"] is None
    closed = run(rev.close_loop(out["version"]["id"], {"id": "r", "flags": []}))
    assert closed["loop_outcome"]["outcome"] == rev.CLEARED


def test_a_failed_accept_is_resumed_by_a_concurrent_waiter(book, indexed):
    """The winner dies after the scene write; one of the waiting callers finishes it."""
    psg = quarantine("The latch gave.", book)
    ledger.FAILPOINTS.arm("accept.passage_mark")

    async def storm():
        return await asyncio.gather(*[
            psg_svc.passage_store.accept(psg["id"]) for _ in range(5)], return_exceptions=True)
    results = run(storm())
    failed = [r for r in results if isinstance(r, ledger.InjectedFailure)]
    done = [r for r in results if not isinstance(r, Exception)]
    assert len(failed) == 1 and len(done) == 4
    assert len({r["block_id"] for r in done}) == 1
    assert [b["id"] for b in scene_of(book)["blocks"]] == [done[0]["block_id"]]
    assert len(indexed["versions"].docs) == 1
    assert run(psg_svc.passage_store.get(psg["id"]))["status"] == psg_svc.ACCEPTED
    assert consistent(indexed)["stuck_operations"] == []


# ══ idempotency keys ═════════════════════════════════════════════════════════

def test_the_same_idempotency_key_on_a_different_passage_is_a_conflict(book, indexed):
    a = quarantine("A.", book)
    b = quarantine("B.", book)
    run(psg_svc.passage_store.accept(a["id"], idempotency_key="k1"))
    run(psg_svc.passage_store.accept(a["id"], idempotency_key="k1"))     # same: fine
    with pytest.raises(ledger.IdempotencyConflict):
        run(psg_svc.passage_store.accept(b["id"], idempotency_key="k1"))
    assert run(psg_svc.passage_store.get(b["id"]))["status"] == psg_svc.QUARANTINED
    assert len(scene_of(book)["blocks"]) == 1


# ══ 4. retired operators ═════════════════════════════════════════════════════

@pytest.fixture
def ontology(indexed):
    async def build():
        await op_svc.operator_registry.create(
            PROJECT, "threshold", definition="a crossing noticed only after it is behind them",
            rendering_intent="one held moment")
        await op_svc.operator_registry.create(
            PROJECT, "interiority", definition="thought shown as weather",
            relations=[{"target": "threshold", "kind": "requires"}])
        await op_svc.operator_registry.update(
            PROJECT, "threshold", {"definition": "a crossing noticed late"})      # v2
    run(build())
    return indexed


def _stub_model(monkeypatch, reply='{"passage": "The latch gave.", "refusal": ""}'):
    async def fake(system, user):
        return reply, "stub-model"
    monkeypatch.setattr(render_svc, "_call_model", fake)


def test_retiring_keeps_every_version_and_old_provenance_resolves_exactly(ontology):
    book = None
    out = run(op_svc.operator_registry.retire(PROJECT, "threshold", "done with it"))
    assert out["retired"] is True and out["version"] == 2
    assert len(ontology["operators"].docs) == 2                       # nothing deleted
    # Live reads hide it; provenance reads do not.
    assert run(op_svc.operator_registry.get(PROJECT, "threshold")) is None
    assert "threshold" not in run(op_svc.operator_registry.by_name(PROJECT))
    v1 = run(op_svc.operator_registry.resolve_version(PROJECT, "threshold", 1))
    v2 = run(op_svc.operator_registry.resolve_version(PROJECT, "threshold", 2))
    assert v1["definition"] == "a crossing noticed only after it is behind them"
    assert v2["definition"] == "a crossing noticed late"
    resolved = run(op_svc.operator_registry.resolve_provenance(PROJECT, {
        "operators": [{"name": "threshold", "version": 1}]}))
    assert resolved["missing"] == []
    assert resolved["resolved"][0]["definition"] == v1["definition"]
    # And it says what still points at it.
    assert out["references"] == [{"source": "interiority", "target": "threshold",
                                  "kind": "requires", "via": "relation",
                                  "retired_at": out["retired_at"]}]


def test_a_retired_operator_refuses_a_new_render_until_restored(ontology, book, monkeypatch):
    _stub_model(monkeypatch)
    run(op_svc.operator_registry.retire(PROJECT, "threshold"))
    out = run(studio.run_block(PROJECT, "/ threshold\n", manuscript_id=book["manuscript_id"],
                               scene_id=book["scene_id"]))
    entry = out["results"][0]
    assert entry["status"] == REFUSED
    assert "retired" in entry["refusal"] and "restore" in entry["refusal"].lower()
    assert "Define with" not in entry["refusal"]          # not "undefined" — it exists
    # Nothing was quarantined; nothing rendered.
    assert run(psg_svc.passage_store.list(PROJECT)) == []

    restored = run(op_svc.operator_registry.restore(PROJECT, "threshold"))
    assert restored["retired"] is False and restored["version"] == 2  # no bump, no rewrite
    out = run(studio.run_block(PROJECT, "/ threshold\n", manuscript_id=book["manuscript_id"],
                               scene_id=book["scene_id"]))
    assert out["results"][0]["status"] == OK
    assert out["results"][0]["provenance"]["operators"][0]["version"] == 2


def test_a_requires_edge_to_a_retired_operator_is_an_actionable_refusal(ontology, book, monkeypatch):
    _stub_model(monkeypatch)
    run(op_svc.operator_registry.retire(PROJECT, "threshold"))
    out = run(studio.run_block(PROJECT, "/ interiority\n", manuscript_id=book["manuscript_id"],
                               scene_id=book["scene_id"]))
    entry = out["results"][0]
    assert entry["status"] == REFUSED
    assert "`threshold`" in entry["refusal"]
    assert "interiority requires threshold" in entry["refusal"]
    assert "remove the `requires` edge" in entry["refusal"]
    # The edge is still there — history is preserved — and the report names it.
    interiority = run(op_svc.operator_registry.get(PROJECT, "interiority"))
    assert interiority["relations"] == [{"target": "threshold", "kind": "requires"}]
    dangling = run(op_svc.operator_registry.dangling_references(PROJECT))
    assert [(d["source"], d["target"], d["via"]) for d in dangling] == [
        ("interiority", "threshold", "relation")]


def test_nothing_new_may_name_a_retired_operator(ontology):
    run(op_svc.operator_registry.retire(PROJECT, "threshold"))
    # a new edge
    with pytest.raises(rel_mod.RelationError, match="retired"):
        run(op_svc.operator_registry.create(
            PROJECT, "weather", definition="x",
            relations=[{"target": "threshold", "kind": "evokes"}]))
    # a redefinition under the retired name
    with pytest.raises(op_svc.OperatorError, match="restore it"):
        run(op_svc.operator_registry.create(PROJECT, "threshold", definition="again"))
    # an edit
    with pytest.raises(op_svc.OperatorError, match="retired"):
        run(op_svc.operator_registry.update(PROJECT, "threshold", {"definition": "edited"}))
    # an assemblage member
    with pytest.raises(op_svc.OperatorError, match="retired"):
        run(op_svc.operator_registry.create_assemblage(
            PROJECT, "pair", ["threshold", "interiority"],
            rendering_intent="both", definition="the pair"))
    assert len(ontology["operators"].docs) == 2


def test_retire_and_restore_are_idempotent_and_leave_no_version_behind(ontology):
    a = run(op_svc.operator_registry.retire(PROJECT, "threshold"))
    b = run(op_svc.operator_registry.retire(PROJECT, "threshold"))
    assert a["retired_at"] == b["retired_at"]
    run(op_svc.operator_registry.restore(PROJECT, "threshold"))
    c = run(op_svc.operator_registry.restore(PROJECT, "threshold"))
    assert c["version"] == 2 and len(c["history"]) == 1
    events = [d["event"] for d in ontology["usage"].docs.values()]
    assert events.count("operator_retired") == 1 and events.count("operator_restored") == 1


def test_delete_is_retire(ontology):
    assert run(op_svc.operator_registry.delete(PROJECT, "threshold")) is True
    assert run(op_svc.operator_registry.get(PROJECT, "threshold", include_retired=True))["retired"]
    assert run(op_svc.operator_registry.delete(PROJECT, "nobody")) is False


def test_twenty_simultaneous_creates_of_one_name_make_one_operator(indexed):
    async def storm():
        return await asyncio.gather(*[
            op_svc.operator_registry.create(PROJECT, "threshold", definition=f"attempt {i}")
            for i in range(N)], return_exceptions=True)
    results = run(storm())
    wins = [r for r in results if not isinstance(r, Exception)]
    assert len(wins) == 1
    assert all(isinstance(r, op_svc.OperatorError) for r in results if isinstance(r, Exception))
    assert len(indexed["operators"].docs) == 1


# ══ 5. the index migration fails loudly over duplicates ══════════════════════

def test_unique_indexes_refuse_duplicates_loudly_and_discard_nothing(store):
    ops = store["operators"]
    run(ops.insert_one({"_id": "op_1", "project_id": "p", "name": "interiority", "version": 2}))
    run(ops.insert_one({"_id": "op_2", "project_id": "p", "name": "interiority", "version": 3}))
    run(ops.insert_one({"_id": "op_3", "project_id": "p", "name": "threshold", "version": 1}))
    versions = store["versions"]
    run(versions.insert_one({"_id": "v1", "lineage_id": "lin_a", "version": 2}))
    run(versions.insert_one({"_id": "v2", "lineage_id": "lin_a", "version": 2}))

    with pytest.raises(ledger.LedgerIntegrityError) as excinfo:
        run(ledger.ensure_indexes(_overrides(store)))

    report = excinfo.value.report
    dup_ops = report["duplicates"]["writer_operator_collection.uniq_project_name"]
    assert dup_ops["groups"] == [{"key": {"project_id": "p", "name": "interiority"},
                                  "ids": ["op_1", "op_2"], "count": 2}]
    dup_versions = report["duplicates"]["writer_passage_version_collection.uniq_lineage_version"]
    assert dup_versions["groups"][0]["ids"] == ["v1", "v2"]
    # Nothing discarded; the unique index was NOT created over them; the others were.
    assert len(ops.docs) == 3 and len(versions.docs) == 2
    assert "uniq_project_name" not in [i["name"] for i in ops.indexes]
    assert "uniq_lineage_version" not in [i["name"] for i in versions.indexes]
    assert "uniq_author_name" in [i["name"] for i in store["library"].indexes]
    assert "by_project" in [i["name"] for i in versions.indexes]
    # The report reads as a repair instruction and names every row.
    text = str(excinfo.value)
    assert "op_1" in text and "op_2" in text and "v1" in text and "Nothing was discarded" in text
    assert "Repair:" in text
    # Non-strict: the same report, returned instead of raised.
    assert run(ledger.ensure_indexes(_overrides(store), strict=False))["duplicates"]


def test_a_clean_ledger_indexes_every_collection_in_the_plan(store):
    report = run(ledger.ensure_indexes(_overrides(store)))
    assert report["duplicates"] == {}
    assert sorted(report["created"]) == sorted(spec["name"] for spec in ledger.INDEX_PLAN)
    assert {spec["collection"] for spec in ledger.INDEX_PLAN} <= set(ledger.COLLECTION_INVENTORY)


def test_the_index_plan_covers_the_correctness_critical_identities():
    unique = {(s["collection"], tuple(k for k, _ in s["keys"])) for s in ledger.INDEX_PLAN if s["unique"]}
    assert ("writer_operator_collection", ("project_id", "name")) in unique
    assert ("writer_library_collection", ("author", "name")) in unique
    assert ("writer_passage_version_collection", ("lineage_id", "version")) in unique
    assert ("writer_operation_collection", ("idempotency_key",)) in unique


# ══ 6. multi-paragraph identity ══════════════════════════════════════════════

TWO_PARAGRAPHS = "The latch gave before she decided to push.\n\nShe did not look back."


def test_a_multi_paragraph_render_is_one_block_with_paragraphs_inside(book, indexed):
    psg = quarantine(TWO_PARAGRAPHS, book)
    out = run(psg_svc.passage_store.accept(psg["id"]))
    blocks = scene_of(book)["blocks"]
    assert len(blocks) == 1
    assert blocks[0]["id"] == out["block_id"]
    assert ms_svc.block_paragraphs(blocks[0]["content"]) == [
        "The latch gave before she decided to push.", "She did not look back."]
    # The editor's serialisation of the same block reads the same.
    assert ms_svc.block_paragraphs(
        "<p>The latch gave before she decided to push.</p><p>She did not look back.</p>"
    ) == ms_svc.block_paragraphs(blocks[0]["content"])
    # Export keeps both paragraphs, from one block.
    export = run(ms_svc.manuscript_service.export_manuscript(book["manuscript_id"]))["content"]
    assert "push.\n\nShe did not look back." in export
    # One version accounts for the whole of it.
    assert len(indexed["versions"].docs) == 1
    assert consistent(indexed)["duplicate_block_ids"] == []


def test_a_revision_replaces_the_whole_multi_paragraph_block(book, indexed):
    psg = quarantine(TWO_PARAGRAPHS, book)
    v1 = run(psg_svc.passage_store.accept(psg["id"]))
    revised = quarantine("One paragraph now.", book,
                         _provenance("threshold", intents=(("goal", "x"),)))
    run(psg_svc.passage_store.accept_revision(
        revised["id"], lineage_id=v1["lineage_id"], scene_id=book["scene_id"],
        block_id=v1["block_id"]))
    blocks = scene_of(book)["blocks"]
    assert len(blocks) == 1
    assert ms_svc.block_paragraphs(blocks[0]["content"]) == ["One paragraph now."]
    assert blocks[0]["version"] == 2
    # The two-paragraph v1 is still there, whole.
    v1_doc = run(rev.version_store.resolve(v1["lineage_id"], 1))
    assert v1_doc["text"] == TWO_PARAGRAPHS


def test_canon_refuses_two_blocks_claiming_one_identity(book, indexed):
    psg = quarantine(TWO_PARAGRAPHS, book)
    v1 = run(psg_svc.passage_store.accept(psg["id"]))
    scene = scene_of(book)
    split = [dict(scene["blocks"][0], content="<p>first</p>"),
             dict(scene["blocks"][0], content="<p>second</p>")]
    with pytest.raises(ms_svc.BlockIdentityError, match="one block, one identity"):
        run(ms_svc.manuscript_service.update_scene(book["scene_id"], {"blocks": split}))
    assert len(scene_of(book)["blocks"]) == 1
    assert scene_of(book)["blocks"][0]["id"] == v1["block_id"]


def test_the_integrity_report_names_a_scene_where_two_blocks_share_an_id(book, indexed):
    # Written behind the service's back — a restored backup, an old client — and found.
    run(indexed["scenes"].update_one(
        {"_id": book["scene_id"]},
        {"$set": {"blocks": [
            {"id": "blk_dup", "content": "a", "lineage_id": "lin_x", "version": 1},
            {"id": "blk_dup", "content": "b", "lineage_id": "lin_x", "version": 1}]}}))
    report = run(ledger.integrity_report(_overrides(indexed)))
    assert report["ok"] is False
    assert report["duplicate_block_ids"] == [
        {"scene_id": book["scene_id"], "block_id": "blk_dup", "count": 2}]
    assert [(d["lineage_id"], d["version"]) for d in report["dangling_pointers"]] == [
        ("lin_x", 1), ("lin_x", 1)]
    assert "blk_dup" in ledger.format_report(report)


# ══ the invariants this lane must not have bent ══════════════════════════════

def test_an_accepting_passage_is_not_canon_and_is_not_listed_as_quarantined(book, indexed):
    """`accepting` is in flight: it is neither committed nor open to a second decision."""
    psg = quarantine("The latch gave.", book)
    ledger.FAILPOINTS.arm("accept.scene_write")
    with pytest.raises(ledger.InjectedFailure):
        run(psg_svc.passage_store.accept(psg["id"]))
    doc = run(psg_svc.passage_store.get(psg["id"]))
    assert doc["status"] == psg_svc.ACCEPTING and doc["committed"] is False
    assert scene_of(book)["blocks"] == []
    assert run(psg_svc.passage_store.list(PROJECT)) == []
    with pytest.raises(psg_svc.PassageError, match="decision is made once"):
        run(psg_svc.passage_store.dismiss(psg["id"]))


def test_canon_is_written_only_through_manuscript_service():
    import inspect
    for mod in (psg_svc, rev, ledger, op_svc):
        src = inspect.getsource(mod)
        # A mention in prose is allowed; a handle on the collection is not.
        assert "scene_collection." not in src, mod.__name__
        assert "import scene_collection" not in src and ", scene_collection" not in src, mod.__name__


def test_no_version_is_ever_updated_or_deleted_except_its_loop_outcome():
    import inspect
    src = inspect.getsource(rev)
    assert "delete_one" not in src and "delete_many" not in src
    assert src.count("writer_passage_version_collection.update_one") == 1
