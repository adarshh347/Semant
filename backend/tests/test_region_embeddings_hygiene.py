"""
region_embeddings hygiene — the classification rules, and the uniqueness constraint.

The retina lane (#129) found two problems in the live collection while building its index:
scratch rows (`post_id` = `s` / `scratch-in-memory`) that scored **0.97** as the two top
candidates for a real region, and a duplicate `embedding_id` written 1 ms apart by an upsert race
that `embedding_id_idx` was declared non-unique to permit.

The cleanup itself is a one-time script run against Mongo. What is worth pinning in the suite is
everything that decides WHAT gets deleted and everything that keeps the problem from coming back:

  1. the classifier — and specifically its refusal to purge what it merely finds suspicious;
  2. the duplicate tie-break — which of two rows claiming one id survives;
  3. the unique index — that `ensure_indexes` converts a legacy non-unique one rather than
     silently failing, and that a failure is LOUD rather than swallowed.

(3) is the one that matters longest. The original `ensure_indexes` wrapped every `create_index`
in one blanket `except` on the reasoning that an index costs speed, never correctness. That is
true of the other four and false of this one: uniqueness is a constraint, and a constraint that
silently failed to apply is worse than one that was never claimed, because a race nobody believes
possible is a race nobody checks for.
"""
import asyncio
import importlib.util
import pathlib

import pytest
from bson import ObjectId

from backend.services import region_embedding_service as res

# The hygiene script is a `scripts/` tool, not a package module — load it by path.
_SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "region_embeddings_hygiene.py"
_spec = importlib.util.spec_from_file_location("region_embeddings_hygiene", _SCRIPT)
hygiene = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hygiene)


def run(coro):
    return asyncio.run(coro)


LIVE = {"695be8baa9ea58f1b6aef609", "6a60400c1ecd6db1c931eb64"}


def row(post_id, **rest):
    return {"post_id": post_id, "embedding_id": "emb_x", **rest}


# ── 1. the classifier ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sentinel", ["s", "scratch", "scratch-in-memory", "in-memory", "test", ""])
def test_scratch_sentinels_classify_as_scratch(sentinel):
    """These name no picture. They exist because a scratch run was pointed at the live database."""
    assert hygiene.classify(row(sentinel), LIVE) == "scratch"


def test_an_embedding_whose_post_is_gone_is_an_orphan():
    assert hygiene.classify(row("6a647c26b9ccdca830bd38e8"), LIVE) == "orphan"


def test_an_embedding_whose_post_exists_is_live():
    assert hygiene.classify(row("695be8baa9ea58f1b6aef609"), LIVE) == "live"


def test_an_unrecognised_non_objectid_is_suspicious_and_NOT_purged():
    """THE CLAIM that keeps this script honest: it does not delete on a hunch.

    `suspicious` exists so the classifier can be wrong safely. A `post_id` that is neither a
    known sentinel nor a well-formed ObjectId gets reported for a human, never purged — a
    deletion rule grown out of "this looked like junk to me" is how real data disappears while
    everybody reads a clean summary.
    """
    assert hygiene.classify(row("staging-run-42"), LIVE) == "suspicious"
    assert hygiene.classify(row(None), LIVE) == "scratch"        # str(None) → "" → a sentinel

    # and the purge's own selection agrees — suspicious is not in the doomed set
    assert "suspicious" not in ("scratch", "orphan")


def test_the_sentinel_list_is_explicit_not_a_pattern():
    """A heuristic ('short', 'not an ObjectId') would have swept up the suspicious case above.
    Pinning the list means widening it is a decision somebody makes, not a regex drifting."""
    assert "staging-run-42" not in hygiene.SCRATCH_POST_IDS
    assert hygiene.SCRATCH_POST_IDS == frozenset(
        {"s", "scratch", "scratch-in-memory", "in-memory", "test", ""})


# ── 2. the duplicate tie-break ───────────────────────────────────────────────────────────────

def _dup(oid, post_id, stamp):
    from datetime import datetime, timezone
    return {"_id": ObjectId(oid), "embedding_id": "emb_dup", "post_id": post_id,
            "updated_at": datetime(2026, 7, 22, 1, 48, 13, stamp, tzinfo=timezone.utc)}


def test_the_newest_row_survives_a_duplicate_pair():
    """`upsert_embedding` `$set`s `updated_at` on every write, so the newest row reflects the
    most recent state of the region. The real pair differed by 1 ms."""
    older = _dup("6a60215d26a4619f6c28c003", "695be8baa9ea58f1b6aef609", 222000)
    newer = _dup("6a60215d26a4619f6c28c004", "695be8baa9ea58f1b6aef609", 223000)

    assert hygiene._keeper([older, newer], LIVE)["_id"] == newer["_id"]
    assert hygiene._keeper([newer, older], LIVE)["_id"] == newer["_id"]   # order-independent


def test_a_row_pointing_at_a_live_post_beats_a_newer_orphan():
    """Recency is the tie-break, not the rule. An embedding that still points at a real picture
    is the one worth keeping even when a later write left one that does not."""
    live_older = _dup("6a60215d26a4619f6c28c003", "695be8baa9ea58f1b6aef609", 222000)
    orphan_newer = _dup("6a60215d26a4619f6c28c004", "6a647c26b9ccdca830bd38e8", 999000)

    assert hygiene._keeper([live_older, orphan_newer], LIVE)["_id"] == live_older["_id"]


def test_the_tie_break_survives_rows_with_no_timestamps():
    """A row written before the service stamped `updated_at` must not crash the dedupe; the
    ObjectId's own generation time is the fallback."""
    a = {"_id": ObjectId("6a60215d26a4619f6c28c003"), "post_id": "695be8baa9ea58f1b6aef609"}
    b = {"_id": ObjectId("6a60215d26a4619f6c28c004"), "post_id": "695be8baa9ea58f1b6aef609"}
    assert hygiene._keeper([a, b], LIVE)["_id"] in (a["_id"], b["_id"])


# ── 3. the unique index ──────────────────────────────────────────────────────────────────────

class FakeIndexes:
    """A Mongo collection that remembers only what this test needs: its index catalogue."""

    def __init__(self, info=None, create_error=None):
        self.info = dict(info or {})
        self.create_error = create_error
        self.calls = []

    async def index_information(self):
        return dict(self.info)

    async def create_index(self, key, name=None, unique=False, **_kw):
        self.calls.append(("create", name, unique))
        if self.create_error and name == "embedding_id_idx":
            raise self.create_error
        self.info[name] = {"key": [(key, 1)], **({"unique": True} if unique else {})}
        return name

    async def drop_index(self, name):
        self.calls.append(("drop", name, None))
        self.info.pop(name, None)


@pytest.fixture
def fake_collection(monkeypatch):
    def _install(coll):
        monkeypatch.setattr(res, "region_embeddings_collection", coll)
        return coll
    return _install


def test_a_legacy_non_unique_index_is_dropped_and_rebuilt_unique(fake_collection):
    """THE CLAIM: the conversion actually happens on a deployment that already has the old index.

    Mongo will not quietly change an existing index's options — `create_index` with the same name
    and different options raises IndexOptionsConflict. So a version that merely added
    `unique=True` to the existing call would fail on every existing deployment, get swallowed by
    the non-fatal `except`, and leave the constraint unapplied while the code claimed it.
    """
    coll = fake_collection(FakeIndexes({"embedding_id_idx": {"key": [("embedding_id", 1)]}}))

    assert run(res._ensure_unique_embedding_id_index()) is True
    assert coll.info["embedding_id_idx"]["unique"] is True
    assert ("drop", "embedding_id_idx", None) in coll.calls
    assert ("create", "embedding_id_idx", True) in coll.calls


def test_an_already_unique_index_is_left_alone(fake_collection):
    """Idempotent, and specifically it must not drop-and-rebuild on every boot: for the window
    between the drop and the create, `embedding_id` would be unindexed and unconstrained."""
    coll = fake_collection(FakeIndexes(
        {"embedding_id_idx": {"key": [("embedding_id", 1)], "unique": True}}))

    assert run(res._ensure_unique_embedding_id_index()) is True
    assert coll.calls == []


def test_a_fresh_collection_gets_the_unique_index_directly(fake_collection):
    coll = fake_collection(FakeIndexes({}))

    assert run(res._ensure_unique_embedding_id_index()) is True
    assert coll.info["embedding_id_idx"]["unique"] is True
    assert not any(c[0] == "drop" for c in coll.calls)


def test_a_failed_unique_build_reports_false_and_says_so_loudly(fake_collection, capsys):
    """THE CLAIM that the old blanket `except` got wrong. Duplicates still present means the
    build fails; the caller must be able to tell, and a human must be able to read why.

    The other four indexes cost query speed when they fail. This one is a CONSTRAINT: reporting
    success here would leave upserts free to race in new duplicates while everybody believed
    they could not.
    """
    coll = fake_collection(FakeIndexes(
        {"embedding_id_idx": {"key": [("embedding_id", 1)]}},
        create_error=Exception("E11000 duplicate key error"),
    ))

    assert run(res._ensure_unique_embedding_id_index()) is False

    out = capsys.readouterr().out
    assert "🚨" in out
    assert "UNIQUE" in out
    assert "region_embeddings_hygiene.py dedupe" in out    # names the fix, not just the failure
    assert "UNINDEXED" in out                              # and the collateral cost


def test_ensure_indexes_still_creates_the_other_four_and_does_not_raise(fake_collection):
    """Non-fatal at boot is the existing contract and stays. The API must come up either way."""
    coll = fake_collection(FakeIndexes({}))

    run(res.ensure_indexes())

    assert set(coll.info) == {"post_id_idx", "space_idx", "region_id_idx", "embedding_id_idx"}
    assert coll.info["embedding_id_idx"]["unique"] is True
    assert coll.info["post_id_idx"].get("unique") is None


def test_unique_index_ready_lets_a_caller_ask_instead_of_assume(fake_collection):
    """`ensure_indexes` is non-fatal by design, so "it ran at boot" is not evidence the
    constraint holds. This is how something downstream checks."""
    coll = fake_collection(FakeIndexes({"embedding_id_idx": {"key": [("embedding_id", 1)]}}))
    assert run(res.unique_index_ready()) is False

    run(res._ensure_unique_embedding_id_index())
    assert run(res.unique_index_ready()) is True
