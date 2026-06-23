"""
Darpan — Instagram persona-context service.

Builds and stores a context dossier per Instagram account from:
  1. account details + captions the Alexia extension scrapes off the live page, and
  2. the images we already have from that account (correlated by handle in each
     saved post's `source_url`).

One persona document per handle (the `handle` is the natural key). `synthesize`
runs vision over a few of our images and asks the LLM for the dossier.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson.objectid import ObjectId

from backend.database import persona_collection, post_collection
from backend.services.llm_service import llm_service
from backend.services.vision_service import vision_service


# Instagram reserved path segments that are NOT usernames.
RESERVED = {
    "p", "reel", "reels", "explore", "accounts", "direct", "stories",
    "about", "developer", "legal", "privacy", "tv", "explore", "s",
}


def normalize_handle(raw: str) -> str:
    """Lower-case, strip @, slashes, query — leave a bare username."""
    if not raw:
        return ""
    h = raw.strip().lstrip("@").strip("/")
    h = h.split("/")[0].split("?")[0].split("#")[0]
    return h.lower()


def handle_from_source_url(url: str) -> Optional[str]:
    """Extract an IG username from a saved post's source_url, if present."""
    if not url:
        return None
    m = re.search(r"instagram\.com/([^/?#]+)", url, re.I)
    if not m:
        return None
    seg = m.group(1).lower()
    if seg in RESERVED or not seg:
        return None
    return seg


class PersonaService:

    @staticmethod
    def persona_helper(doc: dict) -> dict:
        return {
            "id": str(doc["_id"]),
            "handle": doc.get("handle", ""),
            "source_url": doc.get("source_url"),
            "account": doc.get("account", {}),
            "captured_captions": doc.get("captured_captions", []),
            "captured_image_urls": doc.get("captured_image_urls", []),
            "matched_image_count": doc.get("matched_image_count", 0),
            "local_contexts": doc.get("local_contexts", []),
            "dossier": doc.get("dossier"),
            "dossier_generated_at": doc.get("dossier_generated_at"),
            "ingest_count": doc.get("ingest_count", 0),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
        }

    async def _matched_posts(self, handle: str) -> List[dict]:
        """Posts in our gallery from this account: by the stored `instagram_handle`
        field (reliable, set on newer saves) OR the handle parsed from source_url."""
        rx = re.compile(rf"instagram\.com/{re.escape(handle)}(?:[/?#]|$)", re.I)
        cursor = post_collection.find(
            {"$or": [{"instagram_handle": handle}, {"source_url": {"$regex": rx}}]},
            {"photo_url": 1, "general_tags": 1, "source_url": 1, "instagram_handle": 1},
        )
        return await cursor.to_list(length=400)

    async def touch(self, handle: str, account: Optional[dict] = None) -> None:
        """
        Lightly register an account when one of its images is saved — create a stub
        persona if none exists (so it appears in Darpan and correlates), and merge a
        fresh account snapshot. Does NOT run the LLM or bump ingest_count.
        """
        handle = normalize_handle(handle)
        if not handle:
            return
        now = datetime.now(timezone.utc)
        existing = await persona_collection.find_one({"handle": handle})
        snapshot = {k: v for k, v in (account or {}).items() if v not in (None, "", [])}

        matched = await self._matched_posts(handle)
        if existing:
            set_fields = {"updated_at": now, "matched_image_count": len(matched)}
            if snapshot:
                set_fields["account"] = {**existing.get("account", {}), **snapshot}
            await persona_collection.update_one({"handle": handle}, {"$set": set_fields})
        else:
            await persona_collection.insert_one({
                "_id": ObjectId(),
                "handle": handle,
                "source_url": None,
                "account": snapshot,
                "captured_captions": [],
                "captured_image_urls": [],
                "matched_image_count": len(matched),
                "dossier": None,
                "dossier_generated_at": None,
                "ingest_count": 0,
                "created_at": now,
                "updated_at": now,
            })

    async def ingest(self, payload: dict) -> dict:
        """Create/merge a persona from a scrape, and correlate our gallery images."""
        handle = normalize_handle(payload.get("handle", ""))
        if not handle:
            raise ValueError("A valid Instagram handle is required.")

        now = datetime.now(timezone.utc)
        existing = await persona_collection.find_one({"handle": handle})

        # Merge account details: prefer newly-scraped non-empty values.
        new_account = {k: v for k, v in (payload.get("account") or {}).items() if v not in (None, "", [])}
        account = {**(existing.get("account", {}) if existing else {}), **new_account}

        # Accumulate captions / image urls (deduped, capped).
        def merge_list(old, new, cap):
            seen, out = set(), []
            for item in (old or []) + (new or []):
                key = (item or "").strip()
                if key and key not in seen:
                    seen.add(key)
                    out.append(key)
            return out[:cap]

        captions = merge_list(
            existing.get("captured_captions") if existing else [],
            payload.get("captured_captions"), 120,
        )
        image_urls = merge_list(
            existing.get("captured_image_urls") if existing else [],
            payload.get("captured_image_urls"), 120,
        )

        matched = await self._matched_posts(handle)

        doc = {
            "handle": handle,
            "source_url": payload.get("source_url") or (existing.get("source_url") if existing else None),
            "account": account,
            "captured_captions": captions,
            "captured_image_urls": image_urls,
            "matched_image_count": len(matched),
            "ingest_count": (existing.get("ingest_count", 0) if existing else 0) + 1,
            "updated_at": now,
        }

        if existing:
            await persona_collection.update_one({"handle": handle}, {"$set": doc})
            fresh = await persona_collection.find_one({"handle": handle})
        else:
            doc["created_at"] = now
            doc["dossier"] = None
            doc["dossier_generated_at"] = None
            doc["_id"] = ObjectId()
            await persona_collection.insert_one(doc)
            fresh = doc

        return self.persona_helper(fresh)

    async def add_local_context(
        self, handle: str, post_id: str, image_url: Optional[str],
        commentary: str, aletheia: Optional[dict],
    ) -> None:
        """
        Roll a single image's microscopic context (curator commentary + Aletheia
        reading) up into the account's persona as a close-reading. Deduped by
        post_id, capped to the most recent 60.
        """
        handle = normalize_handle(handle)
        if not handle:
            return
        await self.touch(handle)  # ensure the persona exists

        # Compact the Aletheia reading into a one-line note.
        al_note = ""
        if aletheia:
            parts = []
            for lens in (aletheia.get("lenses") or [])[:3]:
                if lens.get("reading"):
                    parts.append(f"{lens.get('name', 'Lens')}: {lens['reading']}")
            if aletheia.get("concealed"):
                parts.append(f"Concealed: {aletheia['concealed']}")
            al_note = " · ".join(parts)

        entry = {
            "post_id": post_id,
            "image_url": image_url,
            "commentary": (commentary or "").strip(),
            "aletheia_note": al_note,
            "updated_at": datetime.now(timezone.utc),
        }
        # Replace any prior entry for this post, then append (cap 60).
        await persona_collection.update_one(
            {"handle": handle}, {"$pull": {"local_contexts": {"post_id": post_id}}}
        )
        await persona_collection.update_one(
            {"handle": handle},
            {"$push": {"local_contexts": {"$each": [entry], "$slice": -60}},
             "$set": {"updated_at": datetime.now(timezone.utc)}},
        )

    async def add_region_correspondence(
        self, handle: str, post_id: str, image_url: Optional[str], notes: list,
    ) -> None:
        """
        Roll an image's part-level correspondences (which anatomical/object part
        affected the curator, in their words) up into the persona as a close-reading.
        """
        handle = normalize_handle(handle)
        if not handle or not notes:
            return
        await self.touch(handle)
        entry = {
            "post_id": f"{post_id}#regions",
            "image_url": image_url,
            "commentary": "Parts that moved me — " + "; ".join(notes[:8]),
            "aletheia_note": "",
            "updated_at": datetime.now(timezone.utc),
        }
        await persona_collection.update_one(
            {"handle": handle}, {"$pull": {"local_contexts": {"post_id": entry["post_id"]}}}
        )
        await persona_collection.update_one(
            {"handle": handle},
            {"$push": {"local_contexts": {"$each": [entry], "$slice": -60}},
             "$set": {"updated_at": datetime.now(timezone.utc)}},
        )

    async def synthesize(self, handle: str) -> Optional[dict]:
        """Run vision over a few of our images + LLM to build the dossier."""
        handle = normalize_handle(handle)
        doc = await persona_collection.find_one({"handle": handle})
        if not doc:
            return None

        # Vision-read up to 5 of the images we have from this account.
        matched = await self._matched_posts(handle)
        readings: List[str] = []
        for post in matched[:5]:
            url = post.get("photo_url")
            if not url:
                continue
            try:
                subtitle = await vision_service.generate_image_subtitle(url)
                if subtitle:
                    readings.append(subtitle)
            except Exception as e:
                print(f"Darpan vision read failed: {e}")

        dossier = llm_service.synthesize_persona(
            handle=handle,
            account=doc.get("account", {}),
            captions=doc.get("captured_captions", []),
            image_readings=readings,
            local_contexts=doc.get("local_contexts", []),
        )

        now = datetime.now(timezone.utc)
        await persona_collection.update_one(
            {"handle": handle},
            {"$set": {
                "dossier": dossier,
                "dossier_generated_at": now,
                "matched_image_count": len(matched),
                "updated_at": now,
            }},
        )
        fresh = await persona_collection.find_one({"handle": handle})
        return self.persona_helper(fresh)

    async def get_persona(self, handle: str) -> Optional[dict]:
        doc = await persona_collection.find_one({"handle": normalize_handle(handle)})
        return self.persona_helper(doc) if doc else None

    async def list_personas(self) -> List[dict]:
        cursor = persona_collection.find().sort("updated_at", -1)
        return [self.persona_helper(d) async for d in cursor]

    async def images_for_handle(self, handle: str) -> List[dict]:
        """The gallery posts we have from this account, for the frontend grid."""
        matched = await self._matched_posts(normalize_handle(handle))
        return [
            {"id": str(p["_id"]), "photo_url": p.get("photo_url"), "general_tags": p.get("general_tags", [])}
            for p in matched
        ]


persona_service = PersonaService()
