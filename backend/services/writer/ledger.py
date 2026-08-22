"""
Semant Writer — ledger integrity (ATLAS-WRITER-MASS-BUILD-001D).

Three things live here, and they are the three the Writer's canon had been getting by
without:

  THE INDEX PLAN. Every Writer collection, every identity it is keyed by, and which of those
  identities must be UNIQUE for the rest of the code to be telling the truth. `(project_id,
  name)` on an operator is what makes `name@version` in a passage's provenance name ONE
  thing; `(lineage_id, version)` on a passage version is what makes "v2 of this passage"
  mean one body of prose. Until now both were enforced by a read-then-insert in Python,
  which holds exactly until two calls interleave.

  Creating a unique index over rows that already violate it is the one thing this module
  refuses to do quietly. `ensure_indexes` audits first; if duplicates exist it raises with a
  REPAIR REPORT that names every offending row, creates no unique index over them, and
  discards nothing — deciding which of two `interiority v3`s a book's provenance meant is an
  author's decision, not a startup hook's.

  FAILPOINTS. A canonical transition is four or five writes across three collections, and
  the claim this lane makes is that dying between any two of them leaves a state the next
  call can finish. That claim is only worth making if it is TESTED at every seam, so each
  step of Accept, revision Accept, Dismiss and loop closure calls `trip("<step>")` before it
  writes. In production `trip` is a dictionary lookup that finds nothing. In a test it is
  armed, and the seam fails on cue.

  OPERATION RECORDS. Mongo transactions need a replica set; the development database and
  the test fakes are not one, and a protocol that is only safe in one of the two places the
  code runs is not a protocol. So every transition keeps an explicit record — planned ids,
  the step it reached, the error if it died — and resumption reads that record rather than
  re-planning. The record is DERIVED: the versions and the scene blocks are the authority,
  and this only says how they got there. It is also where a client's idempotency key lands,
  so one key maps to one operation.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend import database as db
from backend.database import writer_operation_collection

log = logging.getLogger("semant.writer.ledger")


class LedgerIntegrityError(RuntimeError):
    """The ledger is not in a state a unique index can be declared over. Carries the report."""

    def __init__(self, report: Dict[str, Any]):
        self.report = report
        super().__init__(format_report(report))


class IdempotencyConflict(ValueError):
    """The same idempotency key arrived for a different target. One key, one operation."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── failpoints ───────────────────────────────────────────────────────────────

class InjectedFailure(RuntimeError):
    """Raised by an armed failpoint. Never constructed outside a test."""


class Failpoints:
    """Named seams a test can make fail. Production never arms one."""

    def __init__(self) -> None:
        self._armed: Dict[str, int] = {}
        self.tripped: List[str] = []

    def arm(self, name: str, times: int = 1) -> None:
        self._armed[name] = times

    def disarm(self, name: Optional[str] = None) -> None:
        if name is None:
            self._armed.clear()
        else:
            self._armed.pop(name, None)

    def trip(self, name: str) -> None:
        remaining = self._armed.get(name)
        if not remaining:
            return
        self._armed[name] = remaining - 1
        self.tripped.append(name)
        raise InjectedFailure(f"injected failure at `{name}`")


FAILPOINTS = Failpoints()


def trip(name: str) -> None:
    """Fail here if a test asked for it. A no-op otherwise — one dict lookup."""
    FAILPOINTS.trip(name)


# ── the index plan: every Writer collection and identity ─────────────────────

#: One entry per index. `collection` is the attribute name in `backend.database`, so the
#: plan can be resolved against the real collections or against a test's fakes.
INDEX_PLAN: Tuple[Dict[str, Any], ...] = (
    # The author's ontology. `(project_id, name)` is what `name@version` in provenance
    # resolves through, and it must name exactly one operator — retired or live.
    {"collection": "writer_operator_collection", "name": "uniq_project_name",
     "keys": [("project_id", 1), ("name", 1)], "unique": True},
    # The portable library, keyed by author. Same argument, one level up.
    {"collection": "writer_library_collection", "name": "uniq_author_name",
     "keys": [("author", 1), ("name", 1)], "unique": True},
    # Passage genealogy. Two documents both claiming to be v2 of one lineage would mean
    # "what did this passage say before I revised it?" has two answers.
    {"collection": "writer_passage_version_collection", "name": "uniq_lineage_version",
     "keys": [("lineage_id", 1), ("version", 1)], "unique": True},
    {"collection": "writer_passage_version_collection", "name": "by_project",
     "keys": [("project_id", 1)], "unique": False},
    # Quarantine. Listed by project/scene/status, newest first.
    {"collection": "writer_passage_collection", "name": "by_project_scene_status",
     "keys": [("project_id", 1), ("scene_id", 1), ("status", 1), ("created_at", -1)],
     "unique": False},
    # Operation records. A client idempotency key names ONE operation; the partial filter
    # keeps operations that carried no key out of the uniqueness check.
    {"collection": "writer_operation_collection", "name": "uniq_idempotency_key",
     "keys": [("idempotency_key", 1)], "unique": True,
     "partial": {"idempotency_key": {"$type": "string"}}},
    {"collection": "writer_operation_collection", "name": "by_state",
     "keys": [("state", 1), ("updated_at", -1)], "unique": False},
    # Readings and usage: read by project, never by identity.
    {"collection": "writer_reading_collection", "name": "by_project_scene",
     "keys": [("project_id", 1), ("scene_id", 1), ("read_at", -1)], "unique": False},
    {"collection": "writer_usage_collection", "name": "by_project_at",
     "keys": [("project_id", 1), ("at", -1)], "unique": False},
    # Canon. A scene belongs to one manuscript; a snapshot to one scene.
    {"collection": "scene_collection", "name": "by_manuscript",
     "keys": [("manuscript_id", 1)], "unique": False},
    {"collection": "scene_version_collection", "name": "by_scene_created",
     "keys": [("scene_id", 1), ("created_at", -1)], "unique": False},
)

#: Every collection the Writer reads or writes, with what identifies a row in it. The
#: inventory the plan above was drawn from, kept beside it so the two cannot drift.
COLLECTION_INVENTORY: Dict[str, Dict[str, Any]] = {
    "writer_operator_collection": {"identity": ("project_id", "name"), "versioned": "in place (history[])"},
    "writer_library_collection": {"identity": ("author", "name"), "versioned": "in place (history[])"},
    "writer_passage_collection": {"identity": ("_id",), "state": ("status",)},
    "writer_passage_version_collection": {"identity": ("lineage_id", "version"), "immutable": True},
    "writer_reading_collection": {"identity": ("_id",)},
    "writer_usage_collection": {"identity": ("_id",), "write_behind": True},
    "writer_register_collection": {"identity": ("_id = project_id",)},
    "writer_operation_collection": {"identity": ("_id",), "idempotency": ("idempotency_key",)},
    "manuscript_collection": {"identity": ("_id",)},
    "scene_collection": {"identity": ("_id",), "blocks": ("blocks[].id",)},
    "scene_version_collection": {"identity": ("_id",), "immutable": True},
}


def resolve_collections(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`{attribute name: collection}` — the real ones, or a test's fakes where given."""
    names = {spec["collection"] for spec in INDEX_PLAN} | set(COLLECTION_INVENTORY)
    out = {name: getattr(db, name, None) for name in names}
    out.update(overrides or {})
    return out


async def find_duplicates(collection: Any, keys: Sequence[str]) -> List[Dict[str, Any]]:
    """Rows sharing one value of `keys`, grouped. `[{key: {...}, ids: [...], count}]`.

    Walks the collection in Python rather than aggregating, so the same code audits a real
    collection and a test fake — and so the answer is computed from the rows themselves
    rather than from an index that might be the thing in question.
    """
    groups: Dict[Tuple[Any, ...], List[Any]] = defaultdict(list)
    async for doc in collection.find({}):
        key = tuple(doc.get(k) for k in keys)
        if any(v is None for v in key):
            continue          # a row missing part of the identity is a different finding
        groups[key].append(doc.get("_id"))
    return [
        {"key": dict(zip(keys, key)), "ids": ids, "count": len(ids)}
        for key, ids in groups.items() if len(ids) > 1
    ]


async def ensure_indexes(
    overrides: Optional[Dict[str, Any]] = None, *, strict: bool = True
) -> Dict[str, Any]:
    """Create every index in the plan. Audits before any unique one; never discards a row.

    Returns `{created, skipped, duplicates}`. With `strict` (the default) duplicates raise
    `LedgerIntegrityError` AFTER every non-unique index and every clean unique index has
    been created — so one dirty collection does not leave the others unindexed, and the
    error carries the whole picture rather than the first problem found.
    """
    cols = resolve_collections(overrides)
    report: Dict[str, Any] = {"created": [], "skipped": [], "duplicates": {}}

    for spec in INDEX_PLAN:
        collection = cols.get(spec["collection"])
        if collection is None:
            report["skipped"].append({"index": spec["name"], "reason": "collection unavailable"})
            continue
        if spec["unique"]:
            dupes = await find_duplicates(collection, [k for k, _ in spec["keys"]])
            if dupes:
                report["duplicates"][f"{spec['collection']}.{spec['name']}"] = {
                    "collection": spec["collection"],
                    "keys": [k for k, _ in spec["keys"]],
                    "groups": dupes,
                }
                report["skipped"].append({
                    "index": spec["name"], "reason": f"{len(dupes)} duplicate group(s)"})
                continue
        kwargs: Dict[str, Any] = {"name": spec["name"], "unique": spec["unique"]}
        if spec.get("partial"):
            kwargs["partialFilterExpression"] = spec["partial"]
        await collection.create_index(list(spec["keys"]), **kwargs)
        report["created"].append(spec["name"])

    if report["duplicates"]:
        log.error("writer ledger integrity: %s", format_report(report))
        if strict:
            raise LedgerIntegrityError(report)
    return report


def format_report(report: Dict[str, Any]) -> str:
    """The repair report as a person reads it: which rows, which identity, what to decide."""
    lines = ["Writer ledger: unique index NOT created over duplicate rows. Nothing was discarded."]
    for name, finding in (report.get("duplicates") or {}).items():
        lines.append(f"  {name}  identity={finding['keys']}")
        for group in finding["groups"]:
            lines.append(f"    {group['key']}  ->  {group['count']} rows: {group['ids']}")
    lines.append(
        "  Repair: decide which row each passage's provenance meant, merge the others' history "
        "into it, then re-run ensure_indexes. `scripts/writer_ledger_audit.py` prints this report."
    )
    for stuck in report.get("stuck_operations") or []:
        lines.append(f"  stuck operation {stuck.get('id')}: {stuck.get('kind')} at {stuck.get('step')} — {stuck.get('error')}")
    for finding in report.get("duplicate_block_ids") or []:
        lines.append(f"  scene {finding['scene_id']}: block id {finding['block_id']} appears {finding['count']} times")
    for finding in report.get("dangling_pointers") or []:
        lines.append(
            f"  scene {finding['scene_id']} block {finding['block_id']} points at "
            f"{finding['lineage_id']}@v{finding['version']} which has no version document")
    return "\n".join(lines)


# ── the wider audit: what the indexes cannot see ─────────────────────────────

async def integrity_report(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Everything that would make Writer history unresolvable, in one read-only pass.

    Beyond the duplicates: operations that died mid-way, scenes where two blocks claim one
    id, and blocks whose pointer names a version that does not exist. Reports; repairs
    nothing.
    """
    cols = resolve_collections(overrides)
    report: Dict[str, Any] = {
        "duplicates": {}, "stuck_operations": [], "duplicate_block_ids": [],
        "dangling_pointers": [], "ok": True,
    }

    for spec in INDEX_PLAN:
        if not spec["unique"]:
            continue
        collection = cols.get(spec["collection"])
        if collection is None:
            continue
        dupes = await find_duplicates(collection, [k for k, _ in spec["keys"]])
        if dupes:
            report["duplicates"][f"{spec['collection']}.{spec['name']}"] = {
                "collection": spec["collection"], "keys": [k for k, _ in spec["keys"]],
                "groups": dupes}

    ops = cols.get("writer_operation_collection")
    if ops is not None:
        async for doc in ops.find({"state": {"$in": [FAILED, CLAIMED]}}):
            report["stuck_operations"].append({
                "id": doc.get("_id"), "kind": doc.get("kind"), "step": doc.get("step"),
                "error": doc.get("error"), "target": doc.get("target"),
                "updated_at": doc.get("updated_at")})

    scenes = cols.get("scene_collection")
    versions = cols.get("writer_passage_version_collection")
    if scenes is not None:
        known: set = set()
        if versions is not None:
            async for v in versions.find({}):
                known.add((v.get("lineage_id"), int(v.get("version") or 0)))
        async for scene in scenes.find({}):
            seen: Dict[str, int] = defaultdict(int)
            for block in scene.get("blocks") or []:
                bid = block.get("id")
                if bid:
                    seen[bid] += 1
                lineage, version = block.get("lineage_id"), block.get("version")
                if lineage and version and (lineage, int(version)) not in known:
                    report["dangling_pointers"].append({
                        "scene_id": scene.get("_id"), "block_id": bid,
                        "lineage_id": lineage, "version": version})
            for bid, count in seen.items():
                if count > 1:
                    report["duplicate_block_ids"].append({
                        "scene_id": scene.get("_id"), "block_id": bid, "count": count})

    report["ok"] = not (report["duplicates"] or report["stuck_operations"]
                        or report["duplicate_block_ids"] or report["dangling_pointers"])
    return report


# ── operation records: the compensating protocol's memory ────────────────────

CLAIMED = "claimed"
DONE = "done"
FAILED = "failed"
RESUMING = "resuming"


def operation_id(kind: str, target_id: str) -> str:
    """Deterministic: one target has at most one operation of each kind. That IS the
    idempotency of a retry — the same call finds the same record."""
    return f"wop_{kind}_{target_id}"


async def assert_key_free(idempotency_key: str, kind: str, target_id: str) -> None:
    """A client key names ONE operation. The same key on a different target is a conflict,
    not a second operation — and it is checked before anything is claimed."""
    if not idempotency_key:
        return
    other = await writer_operation_collection.find_one({"idempotency_key": idempotency_key})
    if other and (other.get("target") != target_id or other.get("kind") != kind):
        raise IdempotencyConflict(
            f"idempotency key `{idempotency_key}` was already used for "
            f"{other.get('kind')} on {other.get('target')}; it cannot also name "
            f"{kind} on {target_id}")


async def begin(
    kind: str, target_id: str, *, plan: Dict[str, Any], idempotency_key: str = "",
) -> Optional[Dict[str, Any]]:
    """Open the record for one transition. INSERTED under its deterministic id, so the
    second caller to reach here finds it taken and gets None — it did not begin anything,
    and it should wait for, or resume, the one that did."""
    await assert_key_free(idempotency_key, kind, target_id)
    op_id = operation_id(kind, target_id)
    now = _now()
    doc: Dict[str, Any] = {
        "_id": op_id, "kind": kind, "target": target_id, "plan": dict(plan),
        "state": CLAIMED, "step": "claimed", "error": None,
        "created_at": now, "updated_at": now,
    }
    if idempotency_key:
        doc["idempotency_key"] = idempotency_key
    try:
        await writer_operation_collection.insert_one(doc)
    except Exception as exc:
        if "duplicate" not in str(exc).lower() and type(exc).__name__ != "DuplicateKeyError":
            raise
        return None
    out = dict(doc)
    out["id"] = out.pop("_id")
    return out


async def step(op_id: str, name: str) -> None:
    await writer_operation_collection.update_one(
        {"_id": op_id}, {"$set": {"step": name, "updated_at": _now()}})


async def fail(op_id: str, name: str, error: Exception) -> None:
    await writer_operation_collection.update_one(
        {"_id": op_id},
        {"$set": {"state": FAILED, "step": name, "error": f"{type(error).__name__}: {error}",
                  "updated_at": _now()}})


async def finish(op_id: str, result: Optional[Dict[str, Any]] = None) -> None:
    await writer_operation_collection.update_one(
        {"_id": op_id},
        {"$set": {"state": DONE, "step": "done", "error": None,
                  "result": dict(result or {}), "updated_at": _now()}})


async def get(op_id: str) -> Optional[Dict[str, Any]]:
    doc = await writer_operation_collection.find_one({"_id": op_id})
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


async def claim_resume(op_id: str) -> bool:
    """Take over a FAILED operation. Conditional, so two retries cannot both resume it."""
    res = await writer_operation_collection.update_one(
        {"_id": op_id, "state": FAILED},
        {"$set": {"state": RESUMING, "updated_at": _now()}})
    return res.matched_count > 0
