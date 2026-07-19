"""
VISION-F · F1 — backup, migration ledger, per-post rollback.

Before any corpus mutation, F takes a scoped, hashed snapshot of every post it may touch and its
sidecar embedding rows, drives work through an idempotent/resumable ledger, and can restore any
single post's geometry + assertions + embeddings from the backup — never a global destructive
rollback. The curator IDENTITY hash (Region ids + geometry + notes/priority/weight + semantic
curator decisions + grounds/percepts) is the invariant a restore must reproduce byte-for-byte.

Pure functions + a file-backed ledger, so the mechanics are testable with fakes and the restore
drill runs on a disposable copy before any live row is touched.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from backend.schemas.vision_semantic import SCHEMA_VERSION as SEMANTIC_SCHEMA

BACKUP_SCHEMA = "vision-f-backup-v1"

# the post fields F may mutate (and must therefore back up + be able to restore).
_MUTABLE_FIELDS = ("region_annotations", "semantics", "grounds", "percepts", "domain_profile")


def _ser(v):
    if isinstance(v, dict):
        return {k: _ser(x) for k, x in v.items() if k != "_id"}
    if isinstance(v, list):
        return [_ser(x) for x in v]
    if isinstance(v, datetime):
        return v.isoformat()
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(_ser(obj), sort_keys=True, default=str).encode()).hexdigest()


def curator_identity_hash(post: dict) -> str:
    """A hash of everything that must survive recovery: each Region's id + authoritative geometry
    (mask_rle / polygons / polygon / box / geometry_rev) + curator fields, plus semantic curator
    decisions and grounds/percepts. Independent of transient fields (created_at, descriptions)."""
    regs = []
    for r in (post.get("region_annotations") or []):
        regs.append({
            "id": r.get("id"),
            "mask_rle": r.get("mask_rle"), "polygons": r.get("polygons"),
            "polygon": r.get("polygon"), "box": r.get("box"),
            "geometry_rev": r.get("geometry_rev"),
            "user_note": r.get("user_note"), "prioritised": r.get("prioritised"),
            "weight": r.get("weight"), "label": r.get("label"), "actor": r.get("actor"),
        })
    sem = post.get("semantics") or {}
    sem_curated = [{"candidate_id": a.get("candidate_id"), "status": a.get("status"),
                    "curator_label": a.get("curator_label")}
                   for a in (sem.get("assertions") or [])]
    payload = {"regions": sorted(regs, key=lambda x: str(x["id"])),
               "semantics": sorted(sem_curated, key=lambda x: str(x["candidate_id"])),
               "grounds": post.get("grounds") or [], "percepts": post.get("percepts") or []}
    return _sha(payload)


def curator_only_hash(post: dict) -> str:
    """The curator invariant that must survive a GEOMETRY recovery: Region ids + labels + notes +
    priority/weight + actor, semantic curator decisions, grounds and percepts — but NOT geometry
    (mask/polygon/box/rev). geometry recovery changes geometry on purpose; this hash must not move."""
    regs = [{"id": r.get("id"), "label": r.get("label"), "user_note": r.get("user_note"),
             "prioritised": r.get("prioritised"), "weight": r.get("weight"), "actor": r.get("actor")}
            for r in (post.get("region_annotations") or [])]
    sem = post.get("semantics") or {}
    sem_curated = [{"candidate_id": a.get("candidate_id"), "status": a.get("status"),
                    "curator_label": a.get("curator_label")}
                   for a in (sem.get("assertions") or [])]
    payload = {"regions": sorted(regs, key=lambda x: str(x["id"])),
               "semantics": sorted(sem_curated, key=lambda x: str(x["candidate_id"])),
               "grounds": post.get("grounds") or [], "percepts": post.get("percepts") or []}
    return _sha(payload)


def post_snapshot(post: dict) -> Dict[str, Any]:
    """One immutable, hashed backup record for a post — its mutable fields + identity hash."""
    pid = str(post.get("_id") or post.get("id"))
    doc = {k: _ser(post.get(k)) for k in _MUTABLE_FIELDS}
    doc["photo_url"] = post.get("photo_url"); doc["photo_public_id"] = post.get("photo_public_id")
    doc["source_url"] = post.get("source_url")
    return {"post_id": pid, "doc": doc,
            "identity_hash": curator_identity_hash(post),
            "full_hash": _sha({k: post.get(k) for k in _MUTABLE_FIELDS}),
            "schema": {"backup": BACKUP_SCHEMA, "semantic": SEMANTIC_SCHEMA}}


async def backup_scope(post_ids: Sequence[str], *, post_collection, emb_collection) -> Dict[str, Any]:
    """Snapshot the given posts + all their sidecar embedding rows. Read-only on the corpus."""
    from bson import ObjectId
    posts = []
    embeddings = []
    for pid in post_ids:
        try:
            p = await post_collection.find_one({"_id": ObjectId(pid)})
        except Exception:
            p = await post_collection.find_one({"_id": pid})
        if not p:
            continue
        posts.append(post_snapshot(p))
        async for e in emb_collection.find({"post_id": pid}):
            embeddings.append(_ser(e))
    return {"schema": BACKUP_SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(),
            "post_ids": list(post_ids), "posts": posts, "embeddings": embeddings,
            "n_posts": len(posts), "n_embeddings": len(embeddings)}


def write_backup(backup: Dict[str, Any], path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(backup, f, indent=1, sort_keys=True, default=str)
    return path


def load_backup(path: str) -> Dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def _find_post_backup(backup: Dict[str, Any], post_id: str) -> Optional[Dict[str, Any]]:
    return next((p for p in backup.get("posts", []) if p["post_id"] == post_id), None)


async def restore_post(post_id: str, backup: Dict[str, Any], *, post_collection, emb_collection):
    """Per-post rollback: restore the post's mutable fields and re-materialise its embeddings from
    the backup. Idempotent (deterministic keys + upsert), scoped to ONE post — never global."""
    from bson import ObjectId
    snap = _find_post_backup(backup, post_id)
    if snap is None:
        return {"status": "no_backup", "post_id": post_id}
    try:
        oid = ObjectId(post_id)
    except Exception:
        oid = post_id
    await post_collection.update_one({"_id": oid}, {"$set": snap["doc"]})
    # restore embeddings: delete this post's current rows, re-insert the backed-up ones
    await emb_collection.delete_many({"post_id": post_id})
    rows = [e for e in backup.get("embeddings", []) if str(e.get("post_id")) == post_id]
    for e in rows:
        await emb_collection.update_one({"embedding_id": e["embedding_id"]}, {"$set": e}, upsert=True)
    return {"status": "restored", "post_id": post_id, "embeddings": len(rows)}


# ── migration ledger (file-backed, idempotent, resumable) ────────────────────
STATES = ("planned", "running", "reviewed", "committed", "failed", "rolled_back", "skipped")


class Ledger:
    """One row per (post, job). Persisted to a JSON file so an interrupted migration resumes.
    A `committed` row is never re-run (idempotency), so rerunning produces no duplicate work."""

    def __init__(self, path: str):
        self.path = path
        self.rows: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            self.rows = data.get("rows", {})

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def plan(self, post_id: str, job: str, **meta):
        if post_id not in self.rows:
            self.rows[post_id] = {"post_id": post_id, "job": job, "state": "planned",
                                  "history": [("planned", self._now())], **meta}
        return self.rows[post_id]

    def set_state(self, post_id: str, state: str, **meta):
        assert state in STATES, state
        row = self.rows.setdefault(post_id, {"post_id": post_id, "history": []})
        row["state"] = state
        row["history"] = row.get("history", []) + [(state, self._now())]
        row.update(meta)
        return row

    def state(self, post_id: str) -> Optional[str]:
        return (self.rows.get(post_id) or {}).get("state")

    def is_committed(self, post_id: str) -> bool:
        return self.state(post_id) == "committed"

    def pending(self) -> List[str]:
        return [pid for pid, r in self.rows.items() if r.get("state") not in ("committed", "skipped")]

    def counts(self) -> Dict[str, int]:
        out = {s: 0 for s in STATES}
        for r in self.rows.values():
            out[r.get("state", "planned")] = out.get(r.get("state", "planned"), 0) + 1
        return out

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"rows": self.rows, "saved_at": self._now()}, f, indent=1, default=str)
        return self.path
