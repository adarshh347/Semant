"""
Simulation Engine · Lane 3 — the Retina: the LanceDB store.

The physical layer, and nothing else. It knows about vectors, ids and *spaces*; it knows
nothing about percepts, grounds, marks or Mongo. Feed it rows, ask it for neighbours.

WHY A TABLE PER SPACE, and not one table with a `space` column. Two reasons, and the first
is the whole point:

  1. **Space discipline becomes physics.** `region_embedding_service.cosine_same_space`
     RAISES rather than score two different vector spaces; that guard is the project's oldest
     honesty rule. A vector database has no such guard — it will happily ANN-search whatever
     is in the table. So the refusal is re-expressed as *structure*: a space is a table, a
     search names exactly one table, and there is no query that spans two. A DINOv2 identity
     vector cannot be scored against a FashionCLIP one because they are not in the same file.
  2. Arrow needs a fixed vector width per column anyway (384-d DINOv2, 512-d FashionCLIP),
     so one mixed table was never on the table.

WHY A MANIFEST. `manifest.json` beside the `.lance` directories records what each table holds
— its space, model, role, dim, row count, content fingerprint, and what the build SKIPPED and
why. Table names are slugged-and-hashed and therefore not decodable, so something has to hold
the mapping; and a rebuild that silently indexed 900 of 1000 regions would otherwise report
full coverage. The skip ledger is not diagnostics, it is the coverage claim.

DERIVED, NEVER AUTHORITATIVE. Every row here is a copy of a `region_embeddings` document.
Deleting the whole directory costs a rebuild and nothing else. Nothing writes back.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from array import array
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

#: The manifest schema version. Bump when the row schema changes in a way that makes an
#: existing index unreadable — `load_manifest` then reports it as stale rather than trusting it.
MANIFEST_VERSION = 1

MANIFEST_FILENAME = "manifest.json"

#: Environment override for where the index lives. Deliberately read straight from the
#: environment rather than added to `backend.config.Settings`: the retina is a rebuildable
#: local cache, not application configuration, and this lane does not edit shared files.
DB_PATH_ENV = "RETINA_DB_PATH"


class RetinaError(Exception):
    """Base for every refusal this lane makes."""


class RetinaUnavailable(RetinaError):
    """LanceDB is not installed, or the index directory cannot be opened.

    Raised — never swallowed into an empty candidate list. "I could not look" and "I looked
    and there is nothing near this" are different facts, and a caller deciding where an agent
    may move must be able to tell them apart.
    """


# ── optional dependency ──────────────────────────────────────────────────────
# lancedb pulls pyarrow (~90 MB of wheels). The import is guarded so that a checkout without
# it still imports the backend, boots the API, and runs every other test; only the retina's
# own entry points fail, loudly.
try:                                            # pragma: no cover - import shape
    import lancedb as _lancedb
    import pyarrow as _pa
    _IMPORT_ERROR = ""
except Exception as e:                          # pragma: no cover - import shape
    _lancedb = None
    _pa = None
    _IMPORT_ERROR = f"{type(e).__name__}: {e}"


def is_available() -> bool:
    """Is the retina's backing store importable? False means every entry point will raise."""
    return _lancedb is not None


def unavailable_reason() -> str:
    """Why the retina cannot be used, or '' when it can."""
    if is_available():
        return ""
    return f"lancedb not installed ({_IMPORT_ERROR}) — `pip install lancedb`"


def require_available() -> None:
    """Raise unless the store can be used. Every entry point calls this first."""
    if not is_available():
        raise RetinaUnavailable(unavailable_reason())


_require = require_available          # internal alias, kept short at the call sites


def default_db_path() -> Path:
    """Where the index lives: `$RETINA_DB_PATH`, else `<repo>/data/retina`.

    Under `data/` (gitignored) because the index is derived — it is rebuilt from Mongo, never
    restored from git, and a 57 MB memory-mapped artefact has no business in a public repo.
    """
    override = os.environ.get(DB_PATH_ENV)
    if override:
        return Path(override).expanduser().resolve()
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "data" / "retina"


# ── row schema ───────────────────────────────────────────────────────────────
#: The provenance every indexed row carries, copied verbatim from its `region_embeddings`
#: document. A candidate must be self-describing — a caller has to be able to see WHICH model,
#: checkpoint and geometry revision proposed it without a second round-trip to Mongo.
PROVENANCE_FIELDS = (
    "embedding_id", "post_id", "region_id", "role", "space",
    "model", "checkpoint", "route", "source_content_hash", "mask_hash",
)

_STRING_DEFAULTS = {f: "" for f in PROVENANCE_FIELDS}


def arrow_schema(dim: int):
    """The Arrow schema for one space's table. `dim` fixes the vector width — which is exactly
    why a space cannot share a table with a differently-shaped one."""
    _require()
    fields = [_pa.field(name, _pa.string()) for name in PROVENANCE_FIELDS]
    fields += [
        _pa.field("dim", _pa.int32()),
        _pa.field("geometry_rev", _pa.int32()),      # nullable: absent means "not recorded"
        _pa.field("normalized", _pa.bool_()),
        _pa.field("vector", _pa.list_(_pa.float32(), dim)),
    ]
    return _pa.schema(fields)


def make_row(doc: Dict[str, Any], vector: Sequence[float]) -> Dict[str, Any]:
    """One `region_embeddings` document → one index row. Strings are coerced to '' rather than
    left null so that SQL filters (`post_id != '…'`) behave predictably on every column."""
    row: Dict[str, Any] = {f: str(doc.get(f) or "") for f in PROVENANCE_FIELDS}
    rev = doc.get("geometry_rev")
    row["dim"] = int(len(vector))
    row["geometry_rev"] = int(rev) if isinstance(rev, (int, float)) else None
    row["normalized"] = bool(doc.get("normalized", True))
    row["vector"] = [float(x) for x in vector]
    return row


def table_name_for(space: str) -> str:
    """A filesystem-safe, collision-free table name for a space key.

    Space keys look like `dinov2_vits14|identity|dino-v1|384`. The slug keeps it readable on
    disk; the hash suffix keeps it injective, since slugging is lossy (two different keys can
    slug identically) and a collision would silently merge two incomparable spaces into one
    table — the exact failure this whole design exists to prevent.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", (space or "").lower()).strip("_")[:48] or "space"
    digest = hashlib.sha1((space or "").encode()).hexdigest()[:8]
    return f"sp_{slug}_{digest}"


def row_digest(row: Dict[str, Any]) -> bytes:
    """A 32-byte content hash of one row: its provenance fields and the raw float32 bytes of
    its vector. A changed vector moves it even when nothing else about the row moves."""
    h = hashlib.sha256()
    for f in PROVENANCE_FIELDS:
        h.update(str(row.get(f) or "").encode())
        h.update(b"\x00")
    h.update(array("f", [float(x) for x in row.get("vector") or []]).tobytes())
    return h.digest()


class Fingerprint:
    """An order-independent, streaming content hash of a set of rows — XOR of the row digests.

    This is how idempotence is *proved* rather than asserted: rebuild twice from the same
    source and the fingerprints must match.

    XOR (rather than hashing a sorted concatenation) so the same value comes out whether the
    rows arrive all at once or in cursor batches — a 100k-row rebuild must not have to hold
    every vector in memory to describe what it built. The trade is that XOR cancels duplicates,
    which is sound here for one reason only: `embedding_id` is the source's primary key and the
    build de-duplicates on it explicitly, so a set of rows never contains the same row twice.
    """

    __slots__ = ("_acc", "count")

    def __init__(self):
        self._acc = bytearray(32)
        self.count = 0

    def add(self, row: Dict[str, Any]) -> None:
        digest = row_digest(row)
        for i, b in enumerate(digest):
            self._acc[i] ^= b
        self.count += 1

    def hexdigest(self) -> str:
        return bytes(self._acc).hex()


def fingerprint_rows(rows: Iterable[Dict[str, Any]]) -> str:
    """`Fingerprint` over a whole collection at once."""
    fp = Fingerprint()
    for row in rows:
        fp.add(row)
    return fp.hexdigest()


def _existing_tables(db) -> List[str]:
    """The tables physically present, across lancedb's paginated and plain list shapes."""
    out: List[str] = []
    token = None
    while True:
        try:
            res = db.list_tables(page_token=token) if token else db.list_tables()
        except TypeError:                                   # older/plain signature
            res = db.list_tables()
        if isinstance(res, (list, tuple)):
            out.extend(res)
            break
        out.extend(list(getattr(res, "tables", []) or []))
        token = getattr(res, "page_token", None)
        if not token:
            break
    return out


def sql_literal(value: str) -> str:
    """A single-quoted SQL literal with quotes escaped. Ids are internal (`emb_…`, `seg_0`),
    but they are still concatenated into a filter string, and an id is not a place to find out
    that assumption was wrong."""
    return "'" + str(value).replace("'", "''") + "'"


_sql_literal = sql_literal            # internal alias


class RetinaStore:
    """A handle on one on-disk retina index.

    Cheap to construct (the connection is lazy) and safe to hold: LanceDB is embedded and
    memory-mapped, so there is no pool, no server and nothing to close.
    """

    def __init__(self, path: Optional[os.PathLike] = None):
        self.path = Path(path).expanduser().resolve() if path else default_db_path()
        self._db = None

    # ── connection ───────────────────────────────────────────────────────────
    @property
    def db(self):
        _require()
        if self._db is None:
            self.path.mkdir(parents=True, exist_ok=True)
            self._db = _lancedb.connect(str(self.path))
        return self._db

    # ── manifest ─────────────────────────────────────────────────────────────
    @property
    def manifest_path(self) -> Path:
        return self.path / MANIFEST_FILENAME

    def load_manifest(self) -> Dict[str, Any]:
        """The manifest, or an empty one. A manifest from a future/older schema version is
        treated as absent — better to report "not built" and rebuild than to answer queries
        against a mapping we cannot vouch for."""
        try:
            data = json.loads(self.manifest_path.read_text())
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("manifest_version") != MANIFEST_VERSION:
            return {}
        return data

    def write_manifest(self, manifest: Dict[str, Any]) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        payload = dict(manifest)
        payload["manifest_version"] = MANIFEST_VERSION
        self.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))

    def spaces(self) -> Dict[str, Dict[str, Any]]:
        """`{space_key: {table, dim, model, role, rows, fingerprint}}` from the manifest."""
        return dict(self.load_manifest().get("spaces") or {})

    def space_entry(self, space: str) -> Optional[Dict[str, Any]]:
        return self.spaces().get(space)

    # ── writing ──────────────────────────────────────────────────────────────
    def writer(self, space: str, dim: int) -> "SpaceWriter":
        """A writer that replaces one space's table, batch by batch."""
        return SpaceWriter(self, space, dim)

    def write_space(self, space: str, rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace one space's table with exactly these rows. Returns the manifest entry.
        Sugar over `SpaceWriter` for callers small enough to hold everything at once."""
        if not rows:
            raise ValueError(f"refusing to write an empty table for space {space!r}")
        dims = {len(r.get("vector") or []) for r in rows}
        if len(dims) != 1:
            raise ValueError(f"space {space!r} has mixed vector widths {sorted(dims)} — "
                             f"that is two spaces wearing one name")
        w = self.writer(space, dims.pop())
        w.add(rows)
        return w.finish()

    def prune(self, keep: Iterable[str], previously: Iterable[str] = ()) -> List[str]:
        """Drop tables this store wrote that the new build no longer contains.

        Only ever drops names the PREVIOUS manifest claimed as ours. A table we did not write
        is left alone — this directory is ours by convention, not by ownership, and silently
        deleting a stranger's data is not a hygiene operation.
        """
        keep_set = set(keep)
        present = set(_existing_tables(self.db))
        dropped = []
        for name in sorted(set(previously) - keep_set):
            if name in present:
                self.db.drop_table(name, ignore_missing=True)
                dropped.append(name)
        return dropped

    # ── reading ──────────────────────────────────────────────────────────────
    def open_space(self, space: str):
        """The LanceDB table for a space, or None when the space is not indexed."""
        entry = self.space_entry(space)
        if not entry:
            return None
        try:
            return self.db.open_table(entry["table"])
        except (ValueError, FileNotFoundError):
            return None                      # manifest points at a table that is gone

    def count(self, space: str) -> int:
        table = self.open_space(space)
        return int(table.count_rows()) if table is not None else 0

    def lookup(self, space: str, *, where: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Rows matching a filter, with no vector search — how a query BY ID finds its own
        vector before going looking for neighbours."""
        table = self.open_space(space)
        if table is None:
            return []
        return table.search().where(where).limit(limit).to_list()

    def lookup_embedding_id(self, space: str, embedding_id: str) -> Optional[Dict[str, Any]]:
        hits = self.lookup(space, where=f"embedding_id = {_sql_literal(embedding_id)}", limit=1)
        return hits[0] if hits else None

    def lookup_region(self, space: str, region_id: str,
                      post_id: Optional[str] = None, limit: int = 16) -> List[Dict[str, Any]]:
        """Every row for a region id, optionally narrowed to one post.

        Plural on purpose: `region_id` is 'seg_0'-style and unique only WITHIN a post, so this
        can legitimately match many regions in many posts. Resolving that is the caller's job.
        """
        clauses = [f"region_id = {_sql_literal(region_id)}"]
        if post_id:
            clauses.append(f"post_id = {_sql_literal(post_id)}")
        return self.lookup(space, where=" AND ".join(clauses), limit=limit)

    def search(self, space: str, vector: Sequence[float], *, k: int,
               where: Optional[str] = None) -> List[Dict[str, Any]]:
        """Nearest rows in ONE space by cosine distance, nearest first.

        `where` is applied as a PRE-filter: LanceDB's default post-filter trims the ANN result
        set after the fact and would quietly return fewer than k. Under-returning looks
        identical to "there is nothing else near this", which is the one thing a candidate
        generator must never fake.
        """
        table = self.open_space(space)
        if table is None:
            return []
        query = table.search(list(vector)).metric("cosine")
        if where:
            query = query.where(where, prefilter=True)
        return query.limit(max(1, int(k))).to_list()

    # ── introspection ────────────────────────────────────────────────────────
    def size_bytes(self) -> int:
        """Bytes on disk for the whole index (the deliverable's 'index size' note)."""
        total = 0
        for p in self.path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                continue
        return total

    def tables_on_disk(self) -> List[str]:
        return sorted(_existing_tables(self.db))


class SpaceWriter:
    """Replaces one space's table, batch by batch, while folding the content fingerprint.

    `mode="overwrite"` on creation rather than an incremental upsert: a rebuild is defined as
    "make the index equal the source", and replacing the table is the only version of that with
    no residue — no tombstones, no rows for embeddings Mongo no longer has. Batches after the
    first append into that fresh table.

    Rows are sorted by `embedding_id` within each batch. That is cosmetic (LanceDB does not
    care, and the fingerprint is order-independent by construction) but it makes the on-disk
    layout of a rebuild from the same source byte-comparable batch for batch, which is
    pleasant when you are trying to see whether anything actually changed.
    """

    __slots__ = ("store", "space", "dim", "table", "_fp", "_model", "_role", "_created")

    def __init__(self, store: RetinaStore, space: str, dim: int):
        _require()
        if int(dim) <= 0:
            raise ValueError(f"space {space!r} has zero-width vectors")
        self.store = store
        self.space = space
        self.dim = int(dim)
        self._fp = Fingerprint()
        self._model = ""
        self._role = ""
        self._created = False
        self.table = None

    def _ensure_table(self):
        if not self._created:
            self.table = self.store.db.create_table(
                table_name_for(self.space), schema=arrow_schema(self.dim), mode="overwrite")
            self._created = True
        return self.table

    def add(self, rows: Sequence[Dict[str, Any]]) -> int:
        """Append a batch. Rejects a row whose width disagrees with the space — a mixed-width
        space is two spaces wearing one name, and merging them is the failure this design
        exists to prevent."""
        batch = list(rows)
        if not batch:
            return 0
        for row in batch:
            width = len(row.get("vector") or [])
            if width != self.dim:
                raise ValueError(
                    f"space {self.space!r} is {self.dim}-d but row "
                    f"{row.get('embedding_id')!r} is {width}-d")
        batch.sort(key=lambda r: str(r.get("embedding_id") or ""))
        table = self._ensure_table()
        table.add(batch)
        for row in batch:
            self._fp.add(row)
            self._model = self._model or str(row.get("model") or "")
            self._role = self._role or str(row.get("role") or "")
        return len(batch)

    def compact(self) -> None:
        """Fold the batch appends into one fragment and drop the versions this rebuild
        superseded.

        Lance is a versioned format: `mode="overwrite"` writes a NEW version and leaves the old
        one on disk. Without this, rebuilding an index that is logically identical still doubles
        its size on disk each time — the fingerprints match while the directory grows, which is
        idempotence in the ledger and a leak in the filesystem. On a 16 GB laptop that is the
        difference between a cache and a problem.

        Non-fatal: hygiene, never correctness. A failure here leaves a larger index, not a
        wrong one, and must not fail a build that otherwise succeeded.
        """
        if not self._created:
            return
        try:
            self.table.optimize(cleanup_older_than=timedelta(seconds=0), delete_unverified=True)
        except Exception as e:                                   # pragma: no cover - hygiene
            print(f"⚠️ retina: compaction skipped for {self.space!r} (non-fatal): {e}")

    def finish(self, *, compact: bool = True) -> Dict[str, Any]:
        """The manifest entry for what was written."""
        if not self._created:
            raise ValueError(f"refusing to write an empty table for space {self.space!r}")
        if compact:
            self.compact()
        return {
            "table": table_name_for(self.space),
            "space": self.space,
            "dim": self.dim,
            "rows": self._fp.count,
            "model": self._model,
            "role": self._role,
            "fingerprint": self._fp.hexdigest(),
        }
