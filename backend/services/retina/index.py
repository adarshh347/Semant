"""
Simulation Engine · Lane 3 — the Retina: seeding the index from `region_embeddings`.

Mongo is the source of truth; this builds the derived copy. `index_rebuild()` streams every
usable evidence vector out of the sidecar, buckets it by vector space, and replaces that
space's LanceDB table with it.

WHAT "REBUILD" MEANS. Make the index equal the source. Not merge, not top-up: every space it
touches is replaced outright, and tables the previous manifest claimed which no longer have a
source are dropped. So a rebuild after a re-segmentation leaves no rows pointing at geometry
that no longer exists — the index cannot drift away from Mongo by accumulating, only by being
old, and being old is a fact the manifest records with a timestamp.

WHAT IT REFUSES TO INDEX, and why it says so out loud. A vector is skipped when it is
unfinished (`status != ready`), missing, non-finite, or all-zero (cosine is undefined at the
origin — there is no "direction of nothing" to be near). Every skip is counted BY REASON in
the report and the manifest. A build that quietly indexed 900 of 1000 regions and reported
success would be claiming a coverage it does not have, and every downstream "there is nothing
near this" would inherit the lie. The skip ledger is the coverage claim, not diagnostics.

LEGACY ROWS. FashionCLIP vectors predating VISION-E carry no `space` field. They are NOT
folded into a spaced table on a guess about which checkpoint made them; they get their own
`legacy|{model}|{dim}` space. This reproduces `spaces_comparable` exactly — two unspaced rows
are comparable to each other, an unspaced row is never comparable to a spaced one — and since
a space is a table here, that rule is again enforced by the filesystem rather than by care.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Sequence

from backend.services.retina import store as st
from backend.services.retina.store import RetinaError, RetinaStore, RetinaUnavailable

#: How many rows are held per space before being flushed to disk. The whole point is that a
#: rebuild's memory is bounded by (spaces x batch), not by the size of the collection.
DEFAULT_BATCH_ROWS = 2000

#: The fields the rebuild reads. Everything else in a `region_embeddings` document — the
#: preprocessing/crop versions, the error text, the stale reason — is Mongo's business.
SOURCE_PROJECTION = {
    "_id": 0, "embedding_id": 1, "vector": 1, "model": 1, "checkpoint": 1, "dim": 1,
    "role": 1, "space": 1, "post_id": 1, "region_id": 1, "geometry_rev": 1,
    "source_content_hash": 1, "mask_hash": 1, "route": 1, "normalized": 1, "status": 1,
}

#: The reasons a source row does not become an index row. Enumerated so the report always has
#: the same keys and "zero skipped for this reason" is visibly different from "never checked".
SKIP_REASONS = (
    "no_embedding_id",   # unkeyed row — nothing could ever look it up
    "not_ready",         # status is pending/error: the vector is not finished being made
    "no_vector",         # no vector stored (a pointer with nothing behind it)
    "bad_vector",        # non-numeric, NaN or infinite components
    "zero_vector",       # all-zero: cosine has no direction at the origin
    "dim_mismatch",      # the row's own `dim` disagrees with its vector — a corrupt record
    "dim_conflict",      # width disagrees with the rest of its space
    "duplicate",         # the same embedding_id twice in one build
)

#: How many skipped rows are named in the report. A count tells you coverage is short; an
#: example tells you where to look.
SKIP_EXAMPLE_CAP = 10


def space_of(doc: Dict[str, Any]) -> str:
    """The space key a stored vector belongs to.

    `doc['space']` when VISION-E wrote it. Otherwise a synthetic `legacy|{model}|{dim}` — NOT
    a reconstructed `space_key`, because the checkpoint/preprocessing version that would go in
    it is exactly what a legacy row does not record, and guessing it would assert a
    comparability nobody measured.
    """
    space = doc.get("space")
    if space:
        return str(space)
    model = str(doc.get("model") or "unknown")
    dim = len(doc.get("vector") or [])
    return f"legacy|{model}|{dim}"


def is_legacy_space(space: str) -> bool:
    return str(space).startswith("legacy|")


def _vector_problem(doc: Dict[str, Any]) -> Optional[str]:
    """The reason this document's vector cannot be indexed, or None when it can."""
    vec = doc.get("vector")
    if not vec:
        return "no_vector"
    total = 0.0
    for x in vec:
        try:
            f = float(x)
        except (TypeError, ValueError):
            return "bad_vector"
        if not math.isfinite(f):
            return "bad_vector"
        total += f * f
    if total <= 0.0:
        return "zero_vector"
    declared = doc.get("dim")
    if isinstance(declared, int) and declared > 0 and declared != len(vec):
        return "dim_mismatch"
    return None


async def iter_region_embeddings(*, limit: Optional[int] = None,
                                 spaces: Optional[Sequence[str]] = None
                                 ) -> AsyncIterator[Dict[str, Any]]:
    """Stream `region_embeddings` documents. Imported lazily so the retina's query path — which
    touches no database at all — never drags a Mongo connection in behind it.

    Deliberately unsorted: the fingerprint is order-independent by construction, so paying for
    a sort over the whole collection would buy nothing.
    """
    from backend.database import region_embeddings_collection

    query: Dict[str, Any] = {}
    if spaces:
        query["space"] = {"$in": list(spaces)}
    cursor = region_embeddings_collection.find(query, SOURCE_PROJECTION)
    if limit:
        cursor = cursor.limit(int(limit))
    async for doc in cursor:
        yield doc


async def _as_async_iter(source) -> AsyncIterator[Dict[str, Any]]:
    """Accept either an async cursor or a plain iterable of documents, so a test can drive a
    real rebuild from a fixture list with no Mongo and no network."""
    if hasattr(source, "__aiter__"):
        async for doc in source:
            yield doc
    else:
        for doc in source:
            yield doc


async def index_rebuild(
    *,
    store: Optional[RetinaStore] = None,
    source: Optional[Iterable[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
    spaces: Optional[Sequence[str]] = None,
    batch_rows: int = DEFAULT_BATCH_ROWS,
    compact: bool = True,
) -> Dict[str, Any]:
    """Rebuild the retina from the embedding sidecar. Returns the build report.

    `source` overrides the Mongo cursor (a list of documents is fine) — that is the seam the
    tests build a real LanceDB index through without a database.

    `limit` truncates the scan and `spaces` narrows it to named spaces. Both produce a PARTIAL
    index, and both are recorded as such in the manifest: a query answered from a truncated
    index is answered from a fraction of the corpus, and the caller has to be able to find that
    out. A partial rebuild merges into the previous manifest rather than replacing it, so
    reindexing one space does not un-index the others.
    """
    st._require()
    started = time.perf_counter()
    store = store or RetinaStore()
    previous = store.load_manifest()
    partial = bool(spaces) or bool(limit)

    if source is None:
        source = iter_region_embeddings(limit=limit, spaces=spaces)

    writers: Dict[str, st.SpaceWriter] = {}
    buffers: Dict[str, List[Dict[str, Any]]] = {}
    seen_ids: set = set()
    skipped = {reason: 0 for reason in SKIP_REASONS}
    skipped_examples: List[Dict[str, str]] = []
    scanned = 0

    def _skip(reason: str, doc: Dict[str, Any]) -> None:
        skipped[reason] += 1
        if len(skipped_examples) < SKIP_EXAMPLE_CAP:
            skipped_examples.append({
                "embedding_id": str(doc.get("embedding_id") or ""),
                "post_id": str(doc.get("post_id") or ""),
                "region_id": str(doc.get("region_id") or ""),
                "reason": reason,
            })

    def _flush(space: str) -> None:
        rows = buffers.get(space)
        if rows:
            writers[space].add(rows)
            buffers[space] = []

    async for doc in _as_async_iter(source):
        scanned += 1
        embedding_id = str(doc.get("embedding_id") or "")
        if not embedding_id:
            _skip("no_embedding_id", doc)
            continue
        if str(doc.get("status", "ready") or "ready") != "ready":
            _skip("not_ready", doc)
            continue
        if embedding_id in seen_ids:
            _skip("duplicate", doc)
            continue
        problem = _vector_problem(doc)
        if problem:
            _skip(problem, doc)
            continue

        space = space_of(doc)
        if spaces and space not in set(spaces):
            continue                                  # narrowed build; not a skip, not in scope
        vector = doc["vector"]
        if space not in writers:
            writers[space] = store.writer(space, len(vector))
            buffers[space] = []
        if len(vector) != writers[space].dim:
            _skip("dim_conflict", doc)                # a space cannot hold two vector widths
            continue

        seen_ids.add(embedding_id)
        buffers[space].append(st.make_row(doc, vector))
        if len(buffers[space]) >= batch_rows:
            _flush(space)

    built: Dict[str, Dict[str, Any]] = {}
    for space in list(writers):
        _flush(space)
        entry = writers[space].finish(compact=compact)
        entry["legacy"] = is_legacy_space(space)
        built[space] = entry

    # A narrowed rebuild keeps the spaces it did not visit; a full one replaces the lot.
    manifest_spaces = dict(previous.get("spaces") or {}) if spaces else {}
    manifest_spaces.update(built)

    dropped = store.prune(
        keep={e["table"] for e in manifest_spaces.values()},
        previously={e.get("table") for e in (previous.get("spaces") or {}).values() if e},
    )

    elapsed = round(time.perf_counter() - started, 3)
    total_rows = sum(int(e.get("rows") or 0) for e in manifest_spaces.values())
    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source": "region_embeddings",
        "spaces": manifest_spaces,
        "partial": partial,
        "truncated": bool(limit) and scanned >= int(limit),
        "scanned": scanned,
        "indexed": len(seen_ids),
        "skipped": skipped,
        "skipped_examples": skipped_examples,
        "build_seconds": elapsed,
        "rows": total_rows,
    }
    store.write_manifest(manifest)

    return {
        "status": "ready" if total_rows else "empty",
        "path": str(store.path),
        "spaces": manifest_spaces,
        "dropped_tables": dropped,
        "partial": partial,
        "truncated": manifest["truncated"],
        "built_at": manifest["built_at"],
        "totals": {
            "scanned": scanned,
            "indexed": len(seen_ids),
            "skipped": sum(skipped.values()),
            "spaces": len(manifest_spaces),
            "rows": total_rows,
            "build_seconds": elapsed,
            "index_bytes": store.size_bytes(),
        },
        "skipped": skipped,
        "skipped_examples": skipped_examples,
    }


def index_status(store: Optional[RetinaStore] = None) -> Dict[str, Any]:
    """What the retina currently holds — for the status route and the build note.

    Never raises on an unavailable/unbuilt index: "not built" is a legitimate state to report,
    and this is the call you make precisely to find out which state you are in.
    """
    if not st.is_available():
        return {"status": "unavailable", "reason": st.unavailable_reason(),
                "path": str(st.default_db_path()), "spaces": {}}
    store = store or RetinaStore()
    manifest = store.load_manifest()
    if not manifest:
        return {"status": "not_built", "reason": "no manifest — run index_rebuild()",
                "path": str(store.path), "spaces": {}}

    spaces = dict(manifest.get("spaces") or {})
    live = {}
    for space, entry in spaces.items():
        e = dict(entry)
        e["rows_on_disk"] = store.count(space)     # 0 means the manifest outlived its table
        live[space] = e
    return {
        "status": "ready" if manifest.get("rows") else "empty",
        "path": str(store.path),
        "built_at": manifest.get("built_at"),
        "source": manifest.get("source"),
        "partial": bool(manifest.get("partial")),
        "truncated": bool(manifest.get("truncated")),
        "spaces": live,
        "totals": {
            "spaces": len(spaces),
            "rows": int(manifest.get("rows") or 0),
            "scanned": int(manifest.get("scanned") or 0),
            "indexed": int(manifest.get("indexed") or 0),
            "skipped": sum((manifest.get("skipped") or {}).values()),
            "build_seconds": manifest.get("build_seconds"),
            "index_bytes": store.size_bytes(),
        },
        "skipped": manifest.get("skipped") or {},
        "skipped_examples": manifest.get("skipped_examples") or [],
    }


__all__ = ["index_rebuild", "index_status", "iter_region_embeddings", "space_of",
           "is_legacy_space", "RetinaError", "RetinaUnavailable", "SKIP_REASONS"]
