"""
ManuscriptService — the sacred manuscript store (WS-0A).

This is the canon layer of the Writing Studio: create/read/update a manuscript, its
chapter/scene hierarchy, immutable version snapshots, and export. It holds ONE
invariant above all others, inherited from the vision app: *the manuscript is
sacred*. Every write here is an explicit, author-owned commit — there is no AI in
this service, and nothing writes to a scene body except an explicit save/restore.

Design notes:
  - The chapter hierarchy lives inside the manuscript doc (ordered chapters, each an
    ordered `scene_ids`), so structure is a single atomic source of truth. Scene docs
    carry `manuscript_id`/`chapter_id` back-pointers only for cascade + integrity.
  - `scene_versions` are immutable. A restore snapshots the current body first, then
    copies the chosen version FORWARD into the live scene — history is never rewritten.
  - Ids are opaque prefixed strings stored as `_id` (no ObjectId in payloads).
"""

import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.database import (
    manuscript_collection,
    scene_collection,
    scene_version_collection,
)


_TAG_RE = re.compile(r"<[^>]+>")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _strip_html(fragment: str) -> str:
    """HTML fragment -> plain text (tags removed, entities decoded, ws collapsed)."""
    text = _TAG_RE.sub(" ", fragment or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _word_count(blocks: List[Dict[str, Any]]) -> int:
    words = 0
    for b in blocks or []:
        text = _strip_html(b.get("content", ""))
        if text:
            words += len(text.split())
    return words


def _out(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Mongo doc -> API shape: `_id` becomes `id`, nothing else touched."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


_MD_PREFIX = {"h1": "# ", "h2": "## ", "h3": "### ", "quote": "> "}


def _blocks_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for b in blocks or []:
        text = _strip_html(b.get("content", ""))
        if not text:
            continue
        lines.append(_MD_PREFIX.get(b.get("type", "paragraph"), "") + text)
    return "\n\n".join(lines)


class ManuscriptService:
    """CRUD + versioning + export for the writing studio's canon."""

    # --- Manuscripts ---

    async def create_manuscript(self, title: str, synopsis: Optional[str] = None,
                                author: Optional[str] = None) -> Dict[str, Any]:
        now = _now()
        doc = {
            "_id": _gen("ms"),
            "title": title or "Untitled manuscript",
            "synopsis": synopsis or "",
            # W5 — whose book this is. Nullable, so every manuscript written before the
            # portable library is valid as it stands, and the single-author guard treats
            # absence as "nobody has said yet" rather than as a violation.
            "author": author or "",
            "chapters": [],          # [{id, title, scene_ids: [...]}]
            "created_at": now,
            "updated_at": now,
        }
        await manuscript_collection.insert_one(doc)
        return _out(doc)

    async def list_manuscripts(self) -> List[Dict[str, Any]]:
        """Light summaries for the shelf — no scene bodies loaded."""
        out: List[Dict[str, Any]] = []
        async for doc in manuscript_collection.find().sort("updated_at", -1):
            chapters = doc.get("chapters", [])
            out.append({
                "id": doc["_id"],
                "title": doc.get("title", ""),
                "synopsis": doc.get("synopsis", ""),
                "chapter_count": len(chapters),
                "scene_count": sum(len(c.get("scene_ids", [])) for c in chapters),
                "updated_at": doc.get("updated_at"),
            })
        return out

    async def get_manuscript(self, manuscript_id: str) -> Optional[Dict[str, Any]]:
        """
        Full manuscript: metadata + hierarchy + a `scenes` map of light scene stubs
        (id, title, word_count, origin_summary, updated_at) so the structure tree
        renders without one request per scene. Bodies are NOT included.
        """
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        if not doc:
            return None
        scenes: Dict[str, Any] = {}
        async for s in scene_collection.find({"manuscript_id": manuscript_id}):
            scenes[s["_id"]] = {
                "id": s["_id"],
                "chapter_id": s.get("chapter_id"),
                "title": s.get("title", ""),
                "word_count": s.get("word_count", 0),
                "updated_at": s.get("updated_at"),
            }
        result = _out(doc)
        result["scenes"] = scenes
        return result

    async def update_manuscript(self, manuscript_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fields = {k: v for k, v in patch.items()
                  if k in ("title", "synopsis", "author") and v is not None}
        if not fields:
            return await self.get_manuscript(manuscript_id)
        fields["updated_at"] = _now()
        res = await manuscript_collection.update_one({"_id": manuscript_id}, {"$set": fields})
        if res.matched_count == 0:
            return None
        return await self.get_manuscript(manuscript_id)

    async def delete_manuscript(self, manuscript_id: str) -> bool:
        res = await manuscript_collection.delete_one({"_id": manuscript_id})
        if res.deleted_count == 0:
            return False
        await scene_collection.delete_many({"manuscript_id": manuscript_id})
        await scene_version_collection.delete_many({"manuscript_id": manuscript_id})
        return True

    # --- Chapters (hierarchy lives in the manuscript doc) ---

    async def add_chapter(self, manuscript_id: str, title: str) -> Optional[Dict[str, Any]]:
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        if not doc:
            return None
        chapter = {"id": _gen("ch"), "title": title or "Untitled chapter", "scene_ids": []}
        chapters = doc.get("chapters", [])
        chapters.append(chapter)
        await manuscript_collection.update_one(
            {"_id": manuscript_id}, {"$set": {"chapters": chapters, "updated_at": _now()}}
        )
        return await self.get_manuscript(manuscript_id)

    async def update_chapter(self, manuscript_id: str, chapter_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        if not doc:
            return None
        chapters = doc.get("chapters", [])
        found = False
        for c in chapters:
            if c.get("id") == chapter_id:
                if patch.get("title") is not None:
                    c["title"] = patch["title"]
                found = True
                break
        if not found:
            return None
        await manuscript_collection.update_one(
            {"_id": manuscript_id}, {"$set": {"chapters": chapters, "updated_at": _now()}}
        )
        return await self.get_manuscript(manuscript_id)

    async def delete_chapter(self, manuscript_id: str, chapter_id: str) -> Optional[Dict[str, Any]]:
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        if not doc:
            return None
        chapters = doc.get("chapters", [])
        target = next((c for c in chapters if c.get("id") == chapter_id), None)
        if target is None:
            return None
        scene_ids = target.get("scene_ids", [])
        chapters = [c for c in chapters if c.get("id") != chapter_id]
        await manuscript_collection.update_one(
            {"_id": manuscript_id}, {"$set": {"chapters": chapters, "updated_at": _now()}}
        )
        if scene_ids:
            await scene_collection.delete_many({"_id": {"$in": scene_ids}})
            await scene_version_collection.delete_many({"scene_id": {"$in": scene_ids}})
        return await self.get_manuscript(manuscript_id)

    async def reorder(self, manuscript_id: str, chapters: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Atomically replace the whole outline. A reorder may move chapters/scenes but
        MUST reference exactly the known ids — it never creates or drops content.
        Returns None if the manuscript is missing; raises ValueError on a bad outline.
        """
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        if not doc:
            return None

        known_chapters = {c["id"] for c in doc.get("chapters", [])}
        known_scenes = set()
        async for s in scene_collection.find({"manuscript_id": manuscript_id}, {"_id": 1}):
            known_scenes.add(s["_id"])

        new_chapters = {c.get("id") for c in chapters}
        new_scenes = [sid for c in chapters for sid in c.get("scene_ids", [])]

        if new_chapters != known_chapters:
            raise ValueError("reorder must reference exactly the existing chapters")
        if set(new_scenes) != known_scenes or len(new_scenes) != len(known_scenes):
            raise ValueError("reorder must reference exactly the existing scenes, once each")

        clean = [
            {"id": c["id"], "title": c.get("title", ""), "scene_ids": list(c.get("scene_ids", []))}
            for c in chapters
        ]
        # keep each scene's chapter_id back-pointer honest after a cross-chapter move
        for c in clean:
            for sid in c["scene_ids"]:
                await scene_collection.update_one({"_id": sid}, {"$set": {"chapter_id": c["id"]}})
        await manuscript_collection.update_one(
            {"_id": manuscript_id}, {"$set": {"chapters": clean, "updated_at": _now()}}
        )
        return await self.get_manuscript(manuscript_id)

    # --- Scenes ---

    async def add_scene(
        self, manuscript_id: str, chapter_id: str, title: str, blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        if not doc:
            return None
        chapters = doc.get("chapters", [])
        chapter = next((c for c in chapters if c.get("id") == chapter_id), None)
        if chapter is None:
            return None
        now = _now()
        blocks = blocks or []
        scene = {
            "_id": _gen("sc"),
            "manuscript_id": manuscript_id,
            "chapter_id": chapter_id,
            "title": title or "Untitled scene",
            "blocks": blocks,
            "word_count": _word_count(blocks),
            "created_at": now,
            "updated_at": now,
        }
        await scene_collection.insert_one(scene)
        chapter.setdefault("scene_ids", []).append(scene["_id"])
        await manuscript_collection.update_one(
            {"_id": manuscript_id}, {"$set": {"chapters": chapters, "updated_at": now}}
        )
        return _out(scene)

    async def get_scene(self, scene_id: str) -> Optional[Dict[str, Any]]:
        return _out(await scene_collection.find_one({"_id": scene_id}))

    async def update_scene(self, scene_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The canonical scene write — this is the author committing to canon."""
        doc = await scene_collection.find_one({"_id": scene_id})
        if not doc:
            return None
        fields: Dict[str, Any] = {}
        if patch.get("title") is not None:
            fields["title"] = patch["title"]
        if patch.get("blocks") is not None:
            fields["blocks"] = patch["blocks"]
            fields["word_count"] = _word_count(patch["blocks"])
        if not fields:
            return _out(doc)
        fields["updated_at"] = _now()
        await scene_collection.update_one({"_id": scene_id}, {"$set": fields})
        # keep the manuscript's updated_at moving so the shelf sorts sensibly
        await manuscript_collection.update_one(
            {"_id": doc["manuscript_id"]}, {"$set": {"updated_at": fields["updated_at"]}}
        )
        return await self.get_scene(scene_id)

    async def delete_scene(self, scene_id: str) -> Optional[Dict[str, Any]]:
        doc = await scene_collection.find_one({"_id": scene_id})
        if not doc:
            return None
        manuscript_id = doc["manuscript_id"]
        await scene_collection.delete_one({"_id": scene_id})
        await scene_version_collection.delete_many({"scene_id": scene_id})
        ms = await manuscript_collection.find_one({"_id": manuscript_id})
        if ms:
            chapters = ms.get("chapters", [])
            for c in chapters:
                if scene_id in c.get("scene_ids", []):
                    c["scene_ids"] = [s for s in c["scene_ids"] if s != scene_id]
            await manuscript_collection.update_one(
                {"_id": manuscript_id}, {"$set": {"chapters": chapters, "updated_at": _now()}}
            )
        return await self.get_manuscript(manuscript_id)

    # --- Version snapshots (immutable) ---

    async def snapshot_scene(self, scene_id: str, label: Optional[str] = None) -> Optional[Dict[str, Any]]:
        scene = await scene_collection.find_one({"_id": scene_id})
        if not scene:
            return None
        version = {
            "_id": _gen("ver"),
            "scene_id": scene_id,
            "manuscript_id": scene["manuscript_id"],
            "label": label or "",
            "title": scene.get("title", ""),
            "blocks": scene.get("blocks", []),
            "word_count": scene.get("word_count", 0),
            "created_at": _now(),
        }
        await scene_version_collection.insert_one(version)
        return _out(version)

    async def list_scene_versions(self, scene_id: str) -> List[Dict[str, Any]]:
        """Snapshot metadata (no bodies), newest first."""
        out: List[Dict[str, Any]] = []
        async for v in scene_version_collection.find({"scene_id": scene_id}).sort("created_at", -1):
            out.append({
                "id": v["_id"],
                "scene_id": v["scene_id"],
                "label": v.get("label", ""),
                "title": v.get("title", ""),
                "word_count": v.get("word_count", 0),
                "created_at": v.get("created_at"),
            })
        return out

    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        return _out(await scene_version_collection.find_one({"_id": version_id}))

    async def restore_version(self, scene_id: str, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Non-destructive restore: snapshot the current body first (so nothing is lost),
        then copy the chosen version FORWARD into the live scene. History is preserved.
        """
        version = await scene_version_collection.find_one({"_id": version_id, "scene_id": scene_id})
        if not version:
            return None
        await self.snapshot_scene(scene_id, label="before restore")
        blocks = version.get("blocks", [])
        await scene_collection.update_one(
            {"_id": scene_id},
            {"$set": {"blocks": blocks, "word_count": _word_count(blocks), "updated_at": _now()}},
        )
        return await self.get_scene(scene_id)

    # --- Export ---

    async def export_manuscript(self, manuscript_id: str, fmt: str = "markdown") -> Optional[Dict[str, Any]]:
        """Assemble the whole work in reading order into a single text payload."""
        doc = await manuscript_collection.find_one({"_id": manuscript_id})
        if not doc:
            return None
        scenes: Dict[str, Any] = {}
        async for s in scene_collection.find({"manuscript_id": manuscript_id}):
            scenes[s["_id"]] = s

        parts: List[str] = []
        title = doc.get("title", "Untitled manuscript")
        parts.append(f"# {title}")
        if doc.get("synopsis"):
            parts.append(f"_{doc['synopsis']}_")
        for chapter in doc.get("chapters", []):
            parts.append(f"## {chapter.get('title', 'Untitled chapter')}")
            for sid in chapter.get("scene_ids", []):
                scene = scenes.get(sid)
                if not scene:
                    continue
                if scene.get("title"):
                    parts.append(f"### {scene['title']}")
                body = _blocks_to_markdown(scene.get("blocks", []))
                if body:
                    parts.append(body)
        content = "\n\n".join(parts) + "\n"
        return {
            "manuscript_id": manuscript_id,
            "title": title,
            "format": "markdown",
            "content": content,
        }


manuscript_service = ManuscriptService()
