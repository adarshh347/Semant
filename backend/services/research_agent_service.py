"""
Research Article Agent.

A background agent that, per run:
  1. reads the gallery's tag landscape,
  2. consults Sankalpa (the reader's inferred will),
  3. chooses a topic,
  4. gathers + captions gallery images,
  5. composes a research article with the images woven into the prose.

Runs are a Mongo-backed queue (`agent_runs`) drained by a single asyncio worker
started at app startup, so generation truly happens in the background and the
client polls run progress. Blocking LLM/vision calls are pushed off the event
loop with `asyncio.to_thread` so the API stays responsive while the agent works.
"""

import asyncio
import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson.objectid import ObjectId
from pymongo import ReturnDocument

from backend.database import (
    agent_run_collection,
    post_collection,
    research_article_collection,
)
from backend.services.llm_service import llm_service
from backend.services.vision_service import vision_service
from backend.services.sankalpa_service import sankalpa_service


MAX_IMAGES = 6          # images gathered + captioned per article
POLL_SECONDS = 2        # worker idle poll interval


# ----------------------------------------------------------------------
# Document helpers
# ----------------------------------------------------------------------

def run_helper(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "status": doc.get("status", "pending"),
        "steps": doc.get("steps", []),
        "article_id": doc.get("article_id"),
        "topic_override": doc.get("topic_override"),
        "error": doc.get("error"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def article_helper(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", "Untitled"),
        "topic": doc.get("topic", ""),
        "angle": doc.get("angle", ""),
        "abstract": doc.get("abstract", ""),
        "status": doc.get("status", "ready"),
        "source_tags": doc.get("source_tags", []),
        "sections": doc.get("sections", []),
        "steering_questions": doc.get("steering_questions", []),
        "rationale": doc.get("rationale", ""),
        "will_snapshot": doc.get("will_snapshot", ""),
        "run_id": doc.get("run_id"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


class ResearchAgentService:
    """Background research-article generation + run/article reads."""

    # --- Run queue API (called by the router) -------------------------

    async def enqueue_run(
        self,
        topic: Optional[str] = None,
        source_tags: Optional[List[str]] = None,
        angle: Optional[str] = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        run_doc = {
            "_id": ObjectId(),
            "status": "pending",
            "steps": [],
            "article_id": None,
            "topic_override": topic,
            "source_tags_override": source_tags,
            "angle_override": angle,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        await agent_run_collection.insert_one(run_doc)
        return run_helper(run_doc)

    async def get_run(self, run_id: str) -> Optional[dict]:
        try:
            doc = await agent_run_collection.find_one({"_id": ObjectId(run_id)})
            return run_helper(doc) if doc else None
        except Exception:
            return None

    async def list_runs(self, limit: int = 20) -> List[dict]:
        cursor = agent_run_collection.find().sort("created_at", -1).limit(limit)
        return [run_helper(d) async for d in cursor]

    async def get_article(self, article_id: str) -> Optional[dict]:
        try:
            doc = await research_article_collection.find_one({"_id": ObjectId(article_id)})
            return article_helper(doc) if doc else None
        except Exception:
            return None

    async def list_articles(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        total = await research_article_collection.count_documents({})
        skip = (page - 1) * limit
        cursor = (
            research_article_collection.find()
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        articles = [article_helper(d) async for d in cursor]
        return {
            "articles": articles,
            "total_pages": math.ceil(total / limit) if total else 0,
            "current_page": page,
            "total_count": total,
        }

    # --- Step bookkeeping ---------------------------------------------

    async def _step(self, run_id, label: str, status: str = "done", detail: str = ""):
        await agent_run_collection.update_one(
            {"_id": run_id},
            {
                "$push": {"steps": {
                    "label": label,
                    "status": status,
                    "detail": detail,
                    "ts": datetime.now(timezone.utc),
                }},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    # --- Gallery reads ------------------------------------------------

    async def _tag_landscape(self, top: int = 25) -> List[Dict[str, Any]]:
        """Popular gallery tags with image counts, via aggregation."""
        pipeline = [
            {"$match": {"general_tags": {"$exists": True, "$ne": []}}},
            {"$unwind": "$general_tags"},
            {"$group": {"_id": "$general_tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": top},
        ]
        out = []
        async for row in post_collection.aggregate(pipeline):
            out.append({"tag": row["_id"], "count": row["count"]})
        return out

    async def _gather_images(self, source_tags: List[str]) -> List[Dict[str, Any]]:
        """Pick gallery images for the article: tag-scoped first, random fallback."""
        images: List[dict] = []
        if source_tags:
            cursor = post_collection.find(
                {"general_tags": {"$in": source_tags}, "photo_url": {"$exists": True}}
            ).limit(40)
            images = await cursor.to_list(length=40)

        if len(images) < MAX_IMAGES:
            cursor = post_collection.find({"photo_url": {"$exists": True}}).limit(60)
            pool = await cursor.to_list(length=60)
            seen = {str(i["_id"]) for i in images}
            for p in pool:
                if str(p["_id"]) not in seen:
                    images.append(p)
                    seen.add(str(p["_id"]))

        if len(images) > MAX_IMAGES:
            images = random.sample(images, MAX_IMAGES)
        return images

    async def _aggregate_context(self, source_tags: List[str]) -> str:
        """Pull any existing text from tagged posts as grounding for the article."""
        if not source_tags:
            return ""
        query = {
            "general_tags": {"$in": source_tags},
            "text_blocks": {"$exists": True, "$not": {"$size": 0}},
        }
        cursor = post_collection.find(query).limit(20)
        texts = []
        async for post in cursor:
            for block in post.get("text_blocks", []):
                content = (block.get("content") or "").strip()
                if content:
                    texts.append(content)
        return "\n\n".join(texts)

    # --- The pipeline -------------------------------------------------

    async def _run_pipeline(self, run_doc: dict):
        run_id = run_doc["_id"]
        try:
            # 1. Gallery landscape
            await self._step(run_id, "Reading the gallery", status="running")
            landscape = await self._tag_landscape()
            landscape_str = "\n".join(f"{t['tag']} — {t['count']}" for t in landscape) or "(no tags yet)"
            await self._step(run_id, "Reading the gallery", detail=f"{len(landscape)} tags")

            # 2. Consult Sankalpa
            await self._step(run_id, "Consulting Sankalpa", status="running")
            profile = await sankalpa_service.get_profile()
            portrait = sankalpa_service.portrait(profile)
            await self._step(run_id, "Consulting Sankalpa", detail=profile.get("reading", "")[:120])

            # 3. Choose topic
            await self._step(run_id, "Choosing a topic", status="running")
            recent = await self._recent_topics()
            override = run_doc.get("topic_override")
            if override:
                topic = override
                angle = run_doc.get("angle_override") or "phenomenological"
                source_tags = run_doc.get("source_tags_override") or [t["tag"] for t in landscape[:4]]
                rationale = "Reader-specified topic."
            else:
                pick = await asyncio.to_thread(
                    llm_service.pick_research_topic, landscape_str, portrait, recent
                )
                topic = pick.get("topic", "The image and its silence")
                angle = run_doc.get("angle_override") or pick.get("angle", "phenomenological")
                source_tags = run_doc.get("source_tags_override") or pick.get("source_tags", []) or [t["tag"] for t in landscape[:4]]
                rationale = pick.get("rationale", "")
            await self._step(run_id, "Choosing a topic", detail=topic)

            # 4. Gather + caption images
            await self._step(run_id, "Gathering images", status="running")
            posts = await self._gather_images(source_tags)
            captioned = []
            for idx, post in enumerate(posts):
                url = post.get("photo_url")
                try:
                    caption = await vision_service.generate_image_subtitle(url)
                except Exception:
                    caption = ""
                captioned.append({
                    "index": idx,
                    "post_id": str(post["_id"]),
                    "url": url,
                    "caption": caption or "An image from the gallery.",
                })
            await self._step(run_id, "Gathering images", detail=f"{len(captioned)} images captioned")

            # 5. Compose
            await self._step(run_id, "Composing the article", status="running")
            context_text = await self._aggregate_context(source_tags)
            composed = await asyncio.to_thread(
                llm_service.compose_research_article,
                topic, angle, portrait,
                [{"index": c["index"], "caption": c["caption"]} for c in captioned],
                context_text,
            )
            article = await self._persist_article(
                run_id, composed, captioned, topic, angle, source_tags, rationale, portrait
            )
            await self._step(run_id, "Composing the article", detail=article["title"])

            # Done
            await agent_run_collection.update_one(
                {"_id": run_id},
                {"$set": {
                    "status": "done",
                    "article_id": article["id"],
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
        except Exception as e:
            print(f"❌ Research agent run failed: {e}")
            await self._step(run_id, "Failed", status="error", detail=str(e))
            await agent_run_collection.update_one(
                {"_id": run_id},
                {"$set": {"status": "failed", "error": str(e),
                          "updated_at": datetime.now(timezone.utc)}},
            )

    async def _recent_topics(self, n: int = 8) -> List[str]:
        cursor = research_article_collection.find({}, {"topic": 1, "title": 1}).sort("created_at", -1).limit(n)
        return [d.get("topic") or d.get("title", "") async for d in cursor]

    async def _persist_article(
        self, run_id, composed, captioned, topic, angle, source_tags, rationale, portrait
    ) -> dict:
        by_index = {c["index"]: c for c in captioned}
        used = set()
        sections = []
        for raw in composed.get("sections", []):
            img = None
            ix = raw.get("image_index")
            if isinstance(ix, int) and ix in by_index and ix not in used:
                c = by_index[ix]
                img = {"post_id": c["post_id"], "url": c["url"], "caption": c["caption"]}
                used.add(ix)
            sections.append({
                "section_id": f"sec_{uuid.uuid4().hex[:10]}",
                "heading": (raw.get("heading") or "").strip(),
                "content": (raw.get("content") or "").strip(),
                "image": img,
            })

        # Surface any strong unused images as a closing plate so nothing is wasted.
        leftover = [by_index[i] for i in by_index if i not in used][:2]

        questions = []
        for q in composed.get("steering_questions", [])[:3]:
            opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()][:4]
            prompt = str(q.get("prompt", "")).strip()
            if prompt and opts:
                questions.append({"prompt": prompt, "options": opts})

        now = datetime.now(timezone.utc)
        doc = {
            "_id": ObjectId(),
            "title": composed.get("title", topic),
            "topic": topic,
            "angle": angle,
            "abstract": composed.get("abstract", ""),
            "status": "ready",
            "source_tags": source_tags,
            "sections": sections,
            "leftover_images": [
                {"post_id": c["post_id"], "url": c["url"], "caption": c["caption"]} for c in leftover
            ],
            "steering_questions": questions,
            "rationale": rationale,
            "will_snapshot": portrait,
            "run_id": str(run_id),
            "feedback": [],
            "created_at": now,
            "updated_at": now,
        }
        await research_article_collection.insert_one(doc)
        return article_helper(doc)

    # --- Feedback ingestion (delegates will-update to Sankalpa) --------

    async def record_feedback(self, article_id: str, signals: List[Dict[str, Any]]) -> Optional[dict]:
        article = await self.get_article(article_id)
        if not article:
            return None
        # Persist raw signals on the article for provenance.
        await research_article_collection.update_one(
            {"_id": ObjectId(article_id)},
            {"$push": {"feedback": {"$each": [
                {**s, "ts": datetime.now(timezone.utc)} for s in signals
            ]}},
             "$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        # Fold into the will profile.
        profile = await sankalpa_service.ingest(signals, article)
        return profile


research_agent_service = ResearchAgentService()


# ----------------------------------------------------------------------
# Background worker — single-consumer queue drain
# ----------------------------------------------------------------------

_worker_task: Optional[asyncio.Task] = None


async def _worker_loop():
    print("🛰️  Research agent worker started.")
    while True:
        try:
            claimed = await agent_run_collection.find_one_and_update(
                {"status": "pending"},
                {"$set": {"status": "running", "updated_at": datetime.now(timezone.utc)}},
                sort=[("created_at", 1)],
                return_document=ReturnDocument.AFTER,
            )
            if claimed:
                await research_agent_service._run_pipeline(claimed)
            else:
                await asyncio.sleep(POLL_SECONDS)
        except asyncio.CancelledError:
            print("🛰️  Research agent worker stopping.")
            break
        except Exception as e:
            print(f"⚠️ Worker loop error: {e}")
            await asyncio.sleep(POLL_SECONDS * 2)


def start_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())
    return _worker_task
