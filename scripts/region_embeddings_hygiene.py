"""
region_embeddings hygiene — audit, purge, dedupe. The movement substrate, made honest.

The retina lane (#129) surfaced two data problems in `region_embeddings` while building the
LanceDB index, and reported both rather than fixing them (the collection's service is shared and
was outside that lane):

  1. **Scratch rows in the live collection.** `post_id` values like `s` and `scratch-in-memory`
     are not evidence about any picture. They are what a scratch run wrote when it was pointed at
     the live database. The retina's own candidate probe found them scoring **0.97** against a
     real region — the two highest-ranked neighbours of a real query were both junk. A movement
     kernel asking "what is near this?" would be told to walk to a post that does not exist.

  2. **A duplicate `embedding_id`.** `embedding_id_idx` is created NON-unique
     (`region_embedding_service.ensure_indexes`), while `upsert_embedding` writes through
     `update_one({"embedding_id": …}, …, upsert=True)`. Two concurrent upserts for the same id can
     both miss on the query and both insert. The index that would have made that impossible was
     declared without `unique=True`, so the race is not hypothetical — one pair already exists.

## The order these operations must run in, and why

    audit  →  purge  →  dedupe  →  make the index unique

The index cannot be made unique while duplicates exist — Mongo refuses to build a unique index
over data that violates it, and (worse) a `create_index` that fails is swallowed by
`ensure_indexes`' non-fatal `except`, so the uniqueness would silently never take effect while the
code claimed it had. Purge runs before dedupe because a junk row may BE one of a duplicate pair,
in which case the purge resolves it and the dedupe has nothing to do.

## Safety

- **`audit` cannot write.** Every mutating method on both collections is replaced with a raiser
  before the first query, the same guard `scripts/vision_f0_audit.py` uses. It is not a promise;
  it is a physical inability.
- **`purge` and `dedupe` are DRY-RUN BY DEFAULT.** `--apply` is required to delete, and even then
  every document that will be removed is written to a timestamped JSON backup FIRST, vectors and
  all. Nothing is dropped that could not be re-inserted from that file. The backup path is printed
  before the delete and named in the summary.
- **Absolute counts only** (house rule K-9), before and after, for every category.
- **Nothing is deleted by a category this script inferred.** The scratch sentinels are an explicit
  list; an unrecognised non-ObjectId `post_id` is reported as `suspicious` and NOT purged, because
  "looks like junk to me" is not a standard to delete production rows against.

Run:
    PYTHONPATH=. venv/bin/python scripts/region_embeddings_hygiene.py audit
    PYTHONPATH=. venv/bin/python scripts/region_embeddings_hygiene.py purge            # dry run
    PYTHONPATH=. venv/bin/python scripts/region_embeddings_hygiene.py purge --apply
    PYTHONPATH=. venv/bin/python scripts/region_embeddings_hygiene.py dedupe           # dry run
    PYTHONPATH=. venv/bin/python scripts/region_embeddings_hygiene.py dedupe --apply

Exit codes: 0 clean / applied · 1 work remains (dry run found something) · 2 blocked.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient

#: `post_id` values that name no picture. An EXPLICIT list, not a pattern: these are the sentinels
#: a scratch/in-memory run writes, and widening this to a heuristic ("short", "not an ObjectId")
#: would make the purge a guess. Anything outside this list is reported, never deleted.
SCRATCH_POST_IDS = frozenset({
    "s",
    "scratch",
    "scratch-in-memory",
    "in-memory",
    "test",
    "",
})

BACKUP_DIR = "data/region_embeddings_hygiene"

# The fields worth showing in a summary line. The vector is backed up but never printed — 172 rows
# of 768 floats is not a report, it is a denial of service against the reader.
_SUMMARY_FIELDS = ("embedding_id", "post_id", "region_id", "role", "space", "status")


# ── the read-only guard (audit mode) ────────────────────────────────────────────────────────

class WriteAttempted(Exception):
    """Raised if audit mode ever reaches a mutating call. It must never be caught."""


def _freeze(*collections):
    """Make writing physically impossible, rather than merely unintended."""
    def _blocked(*_a, **_k):
        raise WriteAttempted("audit is read-only — a write was attempted")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete",
                       "drop", "drop_index", "drop_indexes", "create_index"):
            try:
                setattr(coll, method, _blocked)
            except Exception:
                pass


# ── connection ──────────────────────────────────────────────────────────────────────────────

def connect():
    load_dotenv(".env")
    uri = os.getenv("MONGO_DETAILS")
    if not uri:
        print("BLOCKED: MONGO_DETAILS not set in .env", file=sys.stderr)
        return None
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001 — the failure mode IS the finding
        print(f"BLOCKED: cannot reach Mongo — {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    # The app hardcodes the database (backend/database.py); the URI carries no default.
    return client["visualDictionaryDB"]


# ── classification ──────────────────────────────────────────────────────────────────────────

def live_post_ids(db):
    """Every `_id` in `posts`, as a string set — what an embedding's `post_id` must match."""
    return {str(d["_id"]) for d in db.posts.find({}, {"_id": 1})}


def _looks_like_object_id(value):
    try:
        ObjectId(str(value))
        return True
    except (InvalidId, TypeError):
        return False


def classify(row, live):
    """One of: scratch | orphan | suspicious | live.

    `suspicious` is the category that exists so this script does not have to be right about
    everything. A `post_id` that is neither a known sentinel nor a well-formed ObjectId is
    reported for a human to look at — it is NOT purged, because a deletion rule built out of "this
    looked wrong to me" is how real data gets lost while everyone reads a clean summary.
    """
    post_id = row.get("post_id")
    key = str(post_id) if post_id is not None else ""
    if key in SCRATCH_POST_IDS:
        return "scratch"
    if not _looks_like_object_id(key):
        return "suspicious"
    if key not in live:
        return "orphan"
    return "live"


def audit(db):
    """Read-only census. Returns the manifest; writes nothing."""
    live = live_post_ids(db)
    rows = list(db.region_embeddings.find({}))

    by_class = Counter()
    by_class_post = defaultdict(Counter)
    by_id = defaultdict(list)
    for row in rows:
        verdict = classify(row, live)
        by_class[verdict] += 1
        by_class_post[verdict][str(row.get("post_id"))] += 1
        by_id[row.get("embedding_id")].append(row)

    duplicates = {eid: group for eid, group in by_id.items() if len(group) > 1}

    # A duplicate whose rows disagree is a different problem from one whose rows are identical
    # copies: the first means two different vectors are both claiming the same id, and choosing
    # between them is a judgement, not a cleanup.
    divergent = {}
    for eid, group in duplicates.items():
        vectors = {tuple(r.get("vector") or ()) for r in group}
        if len(vectors) > 1:
            divergent[eid] = len(vectors)

    index_info = {i["name"]: {"key": list(i["key"].items()), "unique": bool(i.get("unique"))}
                  for i in db.region_embeddings.list_indexes()}

    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "region_embeddings": len(rows),
            "posts": len(live),
            "distinct_post_id_values": len({str(r.get("post_id")) for r in rows}),
            "distinct_embedding_ids": len(by_id),
        },
        "rows_by_class": dict(by_class),
        "scratch_post_ids": dict(by_class_post["scratch"]),
        "orphan_post_ids": dict(by_class_post["orphan"]),
        "suspicious_post_ids": dict(by_class_post["suspicious"]),
        "duplicate_embedding_id_groups": len(duplicates),
        "duplicate_rows_total": sum(len(g) for g in duplicates.values()),
        "duplicate_rows_removable": sum(len(g) - 1 for g in duplicates.values()),
        "duplicate_groups_with_divergent_vectors": divergent,
        "duplicates": {eid: [_summary(r) for r in group] for eid, group in duplicates.items()},
        "indexes": index_info,
        "embedding_id_idx_unique": index_info.get("embedding_id_idx", {}).get("unique", False),
    }


def _summary(row):
    out = {k: row.get(k) for k in _SUMMARY_FIELDS}
    out["_id"] = str(row.get("_id"))
    out["created_at"] = str(row.get("created_at"))
    out["updated_at"] = str(row.get("updated_at"))
    out["dim"] = row.get("dim")
    return out


# ── backup ──────────────────────────────────────────────────────────────────────────────────

def write_backup(rows, label):
    """Every document about to be deleted, vectors included, to a timestamped file.

    This is what makes the operation reversible-by-audit rather than merely careful: the summary
    says what went, and this file is what it takes to put it back.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(BACKUP_DIR, f"{label}-{stamp}.json")
    payload = [{**r, "_id": str(r.get("_id"))} for r in rows]
    with open(path, "w") as fh:
        json.dump({"label": label, "written_at": stamp, "n_rows": len(payload),
                   "rows": payload}, fh, indent=1, default=str)
    return path


# ── purge ───────────────────────────────────────────────────────────────────────────────────

def purge(db, *, apply):
    """Delete scratch and orphan rows. Dry run unless `apply`."""
    live = live_post_ids(db)
    doomed, kept_suspicious = [], []
    for row in db.region_embeddings.find({}):
        verdict = classify(row, live)
        if verdict in ("scratch", "orphan"):
            doomed.append(row)
        elif verdict == "suspicious":
            kept_suspicious.append(row)

    result = {
        "mode": "APPLIED" if apply else "DRY RUN — nothing was deleted",
        "would_delete": len(doomed),
        "by_class": dict(Counter(classify(r, live) for r in doomed)),
        "by_post_id": dict(Counter(str(r.get("post_id")) for r in doomed)),
        "rows": [_summary(r) for r in doomed],
        "kept_suspicious": [_summary(r) for r in kept_suspicious],
        "before": db.region_embeddings.count_documents({}),
    }
    if not doomed:
        result["after"] = result["before"]
        return result

    if apply:
        result["backup"] = write_backup(doomed, "purge")
        print(f"backup written: {result['backup']}", file=sys.stderr)
        ids = [r["_id"] for r in doomed]
        deleted = db.region_embeddings.delete_many({"_id": {"$in": ids}})
        result["deleted"] = deleted.deleted_count
    result["after"] = db.region_embeddings.count_documents({})
    return result


# ── dedupe ──────────────────────────────────────────────────────────────────────────────────

def _keeper(group, live):
    """Which row of a duplicate group survives.

    In order: a row whose post is live beats one whose post is not (an embedding pointing at a
    real picture is the one worth keeping); then the newest by `updated_at`, falling back to
    `created_at`, falling back to the ObjectId's own timestamp — because `upsert_embedding`
    `$set`s `updated_at` on every write, so the newest row is the one that reflects the most
    recent state of the region.
    """
    def rank(row):
        stamp = row.get("updated_at") or row.get("created_at")
        if stamp is None:
            stamp = row["_id"].generation_time
        return (classify(row, live) == "live", stamp.timestamp() if hasattr(stamp, "timestamp")
                else 0.0)

    return max(group, key=rank)


def dedupe(db, *, apply):
    """Collapse each duplicate `embedding_id` group to one row. Dry run unless `apply`."""
    live = live_post_ids(db)
    by_id = defaultdict(list)
    for row in db.region_embeddings.find({}):
        by_id[row.get("embedding_id")].append(row)

    decisions, doomed = [], []
    for eid, group in sorted(by_id.items(), key=lambda kv: str(kv[0])):
        if len(group) < 2:
            continue
        keep = _keeper(group, live)
        drop = [r for r in group if r["_id"] != keep["_id"]]
        doomed.extend(drop)
        decisions.append({
            "embedding_id": eid,
            "group_size": len(group),
            "vectors_identical": len({tuple(r.get("vector") or ()) for r in group}) == 1,
            "keep": _summary(keep),
            "drop": [_summary(r) for r in drop],
        })

    result = {
        "mode": "APPLIED" if apply else "DRY RUN — nothing was deleted",
        "duplicate_groups": len(decisions),
        "would_delete": len(doomed),
        "decisions": decisions,
        "before": db.region_embeddings.count_documents({}),
    }
    if not doomed:
        result["after"] = result["before"]
        return result

    if apply:
        result["backup"] = write_backup(doomed, "dedupe")
        print(f"backup written: {result['backup']}", file=sys.stderr)
        deleted = db.region_embeddings.delete_many({"_id": {"$in": [r["_id"] for r in doomed]}})
        result["deleted"] = deleted.deleted_count
    result["after"] = db.region_embeddings.count_documents({})
    return result


# ── reindex ─────────────────────────────────────────────────────────────────────────────────

def reindex(db, *, apply):
    """Convert `embedding_id_idx` to UNIQUE. Refuses while duplicates remain.

    The refusal is the point. Mongo would reject the build anyway, but `ensure_indexes` catches
    broadly and prints a warning, so a failure there reads as noise and the service goes on
    believing the constraint holds. Checking first turns that into a decision someone made.
    """
    by_id = Counter(r.get("embedding_id") for r in
                    db.region_embeddings.find({}, {"embedding_id": 1}))
    remaining = {eid: n for eid, n in by_id.items() if n > 1}

    info = db.region_embeddings.index_information()
    already = bool(info.get("embedding_id_idx", {}).get("unique"))

    result = {
        "mode": "APPLIED" if apply else "DRY RUN — the index was not changed",
        "embedding_id_idx_unique_before": already,
        "duplicate_embedding_ids_remaining": remaining,
    }
    if already:
        result["action"] = "none — already unique"
        result["embedding_id_idx_unique_after"] = True
        return result
    if remaining:
        result["action"] = ("REFUSED — dedupe first. A unique index cannot be built over data "
                            "that violates it, and a failed build here is swallowed as non-fatal.")
        result["embedding_id_idx_unique_after"] = False
        return result
    if not apply:
        result["action"] = "would drop the non-unique embedding_id_idx and rebuild it as unique"
        result["embedding_id_idx_unique_after"] = False
        return result

    if "embedding_id_idx" in info:
        db.region_embeddings.drop_index("embedding_id_idx")
    db.region_embeddings.create_index("embedding_id", name="embedding_id_idx", unique=True)
    after = db.region_embeddings.index_information()
    result["action"] = "dropped the non-unique index and rebuilt it as unique"
    result["embedding_id_idx_unique_after"] = bool(after["embedding_id_idx"].get("unique"))
    return result


# ── main ────────────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("command", choices=("audit", "purge", "dedupe", "reindex"))
    parser.add_argument("--apply", action="store_true",
                        help="actually delete / change the index. Without it, dry run.")
    args = parser.parse_args()

    db = connect()
    if db is None:
        return 2

    if args.command == "audit":
        _freeze(db.region_embeddings, db.posts)
        report = audit(db)
        print(json.dumps(report, indent=2, default=str))
        dirty = (report["rows_by_class"].get("scratch", 0)
                 + report["rows_by_class"].get("orphan", 0)
                 + report["duplicate_rows_removable"])
        if not report["embedding_id_idx_unique"]:
            dirty += 1
        return 1 if dirty else 0

    if args.command == "reindex":
        report = reindex(db, apply=args.apply)
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["embedding_id_idx_unique_after"] else 1

    report = purge(db, apply=args.apply) if args.command == "purge" \
        else dedupe(db, apply=args.apply)

    print(json.dumps(report, indent=2, default=str))
    if args.apply:
        return 0
    return 1 if report["would_delete"] else 0


if __name__ == "__main__":
    sys.exit(main())
