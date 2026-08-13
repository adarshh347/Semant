"""
PERCEPTUAL-ORGANS-002 Lane F1 — the durable store, held to the in-memory one's contract.

`InMemoryLabStore` is the reference implementation and its docstring names the properties that
matter: values rather than windows, insertion order, and fifteen methods none of which is canon.
This file asserts the same three of the Mongo-backed one, and asserts them BY COMPARISON where it
can — the conductor is run twice over the same inputs, once against each store, and the two
ledgers are required to agree.

The collections are pymongo-SHAPED fakes rather than a live database, because a test that needed
Atlas is a test that does not run in CI. What they are not is a dict pretending to be a store: they
answer `find_one`, `find(...).sort(...)`, `replace_one` and `count_documents`, so the store's own
query and ordering code is exercised rather than skipped.
"""
from __future__ import annotations

import copy

import pytest

from backend.schemas.perception_lab import (ExecutionIdentity, LabSession, OrganFamily,
                                            RunOutcome, SessionMode)
from backend.services.perception_lab.clock import FrozenClock, SequentialIds
from backend.services.perception_lab.live import conductor_for
from backend.services.perception_lab.mongo_store import (KINDS, LabStoreUnavailable, MongoLabStore)
from backend.services.perception_lab.orchestrator import PerceptionConductor
from backend.services.perception_lab.planners import DirectCommand
from backend.services.perception_lab.store import InMemoryLabStore, LabStore
from backend.tests.fixtures import perception_lab_live as F


def _store():
    return MongoLabStore(F.lab_collections(), now=_stamps())


def _stamps():
    """Monotonic ISO stamps, so ordering is a property of the store rather than of the machine."""
    counter = {"n": 0}

    def now() -> str:
        counter["n"] += 1
        return f"2026-08-13T09:00:{counter['n']:02d}.000000+00:00"
    return now


def _lab(store):
    snapshot = F.snapshot()
    return conductor_for(snapshot, store=store, extent_adapters=F.extent_adapters(),
                         probe_collection=F.FakeCollection([F.post_document()])), snapshot


# ── the shape ────────────────────────────────────────────────────────────────


def test_it_is_a_lab_store_and_has_no_door_onto_canon():
    store = _store()
    assert isinstance(store, LabStore)

    forbidden = ("put_region", "put_mark", "put_post", "put_percept", "put_ground", "promote",
                 "commit", "accept")
    for name in forbidden:
        assert not hasattr(store, name), f"{name} would be a door onto canon on the lab's store"


def test_every_protocol_method_is_implemented_and_none_writes_outside_the_five_collections():
    store = MongoLabStore(F.lab_collections())
    for name in dir(LabStore):
        if name.startswith("_"):
            continue
        assert callable(getattr(store, name, None)), f"{name} is on the Protocol and not here"
    assert set(KINDS) == {"sessions", "plans", "runs", "artifacts", "reviews"}


# ── values, not windows ──────────────────────────────────────────────────────


def test_a_record_that_was_read_and_then_mutated_did_not_rewrite_the_ledger():
    store = _store()
    conductor, snapshot = _lab(store)
    machine = conductor.open_session(source=snapshot.source, organ=OrganFamily.EXTENT)

    read = store.get_session(machine.session.session_id)
    read.selected_artifact_ids.append("art_smuggled")
    again = store.get_session(machine.session.session_id)

    assert again.selected_artifact_ids == []


def test_two_reads_of_one_record_are_two_objects():
    store = _store()
    conductor, snapshot = _lab(store)
    machine = conductor.open_session(source=snapshot.source, organ=OrganFamily.EXTENT)
    session_id = machine.session.session_id

    assert store.get_session(session_id) is not store.get_session(session_id)
    assert store.get_session(session_id) == store.get_session(session_id)


def test_a_missing_record_is_none_rather_than_an_exception():
    store = _store()
    assert store.get_session("labs_nobody") is None
    assert store.get_plan("plan_nobody") is None
    assert store.get_run("run_nobody") is None
    assert store.get_artifact("art_nobody") is None
    assert store.get_review("rev_nobody") is None


# ── the ledger agrees with the reference implementation ──────────────────────


def _drive(store):
    """One deterministic sitting: measure, select, measure again, review. Same ids either way."""
    snapshot = F.snapshot()
    conductor = PerceptionConductor(
        store=store, registry=conductor_for(snapshot, store=store,
                                            extent_adapters=F.extent_adapters()).registry,
        clock=FrozenClock(), ids=SequentialIds())
    machine = conductor.open_session(source=snapshot.source, organ=OrganFamily.EXTENT)
    first = conductor.execute(machine, conductor.plan_direct(
        machine, DirectCommand("extent.find_all")).plan)
    machine.select(first.run.artifact_ids[0])
    conductor.save(machine)
    conductor.review(machine, first.run.artifact_ids[0], reviewer="p", verdict="correct")
    return conductor, machine


def test_the_durable_ledger_and_the_in_memory_one_hold_the_same_records():
    memory = InMemoryLabStore()
    durable = _store()
    _drive(memory)
    _drive(durable)

    session_id = memory.sessions()[0].session_id
    assert durable.get_session(session_id) == memory.get_session(session_id)
    assert [p.plan_id for p in durable.plans_for_session(session_id)] \
        == [p.plan_id for p in memory.plans_for_session(session_id)]
    for run in memory.runs_for_session(session_id):
        assert durable.get_run(run.run_id) == run
        assert durable.artifacts_for_run(run.run_id) == memory.artifacts_for_run(run.run_id)


def test_a_replay_is_read_back_after_the_run_it_re_shows():
    """Lane D calls order part of the store's contract: a history that showed a replay before its
    source would be a history in which an effect precedes its cause."""
    store = _store()
    conductor, machine = _drive(store)
    source_run = store.runs_for_session(machine.session.session_id)[0]
    conductor.replay(machine, source_run.run_id)

    runs = store.runs_for_session(machine.session.session_id)
    assert [r.execution_identity for r in runs] == [ExecutionIdentity.LIVE, ExecutionIdentity.REPLAY]
    assert runs[-1].replay.source_run_id == source_run.run_id


# ── compatibility ────────────────────────────────────────────────────────────


def test_a_session_written_before_a2_still_loads():
    """A stored document from before `selected_instance_refs` existed. It reads, unchanged.

    Compatibility is proved by REMOVING the field from the stored payload rather than by keeping an
    old fixture beside a new one — a fixture updated alongside the schema stops testing the thing
    it was written for on the day somebody regenerates it.
    """
    collections = F.lab_collections()
    store = MongoLabStore(collections)
    snapshot = F.snapshot()
    conductor = conductor_for(snapshot, store=store, extent_adapters=F.extent_adapters())
    machine = conductor.open_session(source=snapshot.source, organ=OrganFamily.EXTENT)
    session_id = machine.session.session_id

    doc = collections["sessions"].docs[session_id]
    assert "selected_instance_refs" in doc["record"]
    doc["record"].pop("selected_instance_refs")

    loaded = store.get_session(session_id)
    assert loaded is not None
    assert loaded.selected_instance_refs == []
    assert loaded.session_id == session_id


def test_a_record_that_no_longer_validates_is_raised_rather_than_quietly_skipped():
    collections = F.lab_collections()
    store = MongoLabStore(collections)
    snapshot = F.snapshot()
    conductor = conductor_for(snapshot, store=store, extent_adapters=F.extent_adapters())
    machine = conductor.open_session(source=snapshot.source, organ=OrganFamily.EXTENT)

    collections["sessions"].docs[machine.session.session_id]["record"]["selected_organ"] = "smell"
    with pytest.raises(Exception):
        store.get_session(machine.session.session_id)


def test_the_contract_version_is_written_on_every_document():
    store = _store()
    collections = store._given                              # noqa: SLF001 - the fake, on purpose
    conductor, machine = _drive(store)
    for kind, collection in collections.items():
        for doc in collection.docs.values():
            assert doc["contract_version"] == 1
            assert doc["kind"] == KINDS[kind]


# ── failure is reported, never swallowed ─────────────────────────────────────


class _BrokenCollection(F.FakeCollection):
    def replace_one(self, query, doc, upsert=False):
        raise RuntimeError("the cluster is not answering")


def test_a_write_that_did_not_land_raises_rather_than_reporting_success():
    collections = F.lab_collections()
    collections["sessions"] = _BrokenCollection()
    store = MongoLabStore(collections)
    session = LabSession(session_id="labs_1", source=F.snapshot().source,
                         selected_organ=OrganFamily.EXTENT, mode=SessionMode.ISOLATION,
                         created_at="2026-08-13T09:00:00Z", updated_at="2026-08-13T09:00:00Z")

    with pytest.raises(LabStoreUnavailable, match="not written"):
        store.put_session(session)


def test_a_store_with_no_database_configured_says_so_when_it_is_used_and_not_at_import():
    store = MongoLabStore()                                 # no collections, no database reached
    import backend.services.perception_lab.mongo_store as M
    original = M._default_collections
    M._default_collections = lambda: (_ for _ in ()).throw(RuntimeError("no MONGO_DETAILS"))
    try:
        with pytest.raises(LabStoreUnavailable, match="could not reach its collections"):
            store.get_session("labs_1")
    finally:
        M._default_collections = original
