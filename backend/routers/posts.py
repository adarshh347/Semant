from fastapi import APIRouter, HTTPException, File, UploadFile, Form, BackgroundTasks
from typing import Dict, Optional, List
import uuid
import os
import math
import json
import random
import re
import httpx  # For fetching images from URLs
import base64
from urllib.parse import urlparse
from io import BytesIO
from backend.services.vision_service import vision_service
from backend.services import segmentation_service
from backend.services import region_embedding_service
from backend.services import anuranana_service
from backend.services.persona_service import persona_service, normalize_handle, normalize_handles, handle_from_source_url
from datetime import datetime, timezone
from bson.objectid import ObjectId
from bson.errors import InvalidId
# shutil(high level file operations) vs os (low level file operations)
import shutil
from backend.schemas.post import Post, PostUpdate, PaginatedPosts, StoryGenerationRequest, AddTagRequest, AddTagAndStoryRequest, StoryFlowRequest, PostSuggestionRequest, VisionChatRequest, VisionRewriteRequest, NodeExpansionRequest, UrlUploadRequest, BrainstormRequest, LocalContextRequest, RegionAnnotationsRequest, RegionDetectRequest, AletheiaReadRequest

from backend.database import post_collection,client
import cloudinary
import cloudinary.uploader
from backend.config import settings
# ... shows three directory below from the main directory(big_project)
import asyncio
import pprint # Make sure pprint is imported for the detailed log
# fake in memory database
# fake_posts_db: Dict[str, Dict] ={}

cloudinary.config(
    cloud_name=settings.CLOUDINARY_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

async def test_connection():
    try:
        await client.admin.command('ping')
        print(f"mongodb connection working ")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")



router= APIRouter()
text_posts_router = APIRouter()
# router= APIRouter() creates a mini subapplication (a collection of endpoints)

# NOTE(TO LEARN): since we are uploading pictures(file type)
# they don't come as normal api request which can be parsed as json and mapped to pydantic model
# they are parsed as FORM-FIELDS+FILE STREAMS (multipart/form-data)
# That format is literally a set of parts—some parts are text fields, some are files.
# therefore we cannot directly inherit from schema here
# @router.get("/")
# def random():
#     return {"check":"great work"}


# mongodb and pydantic schemas are not compatible, so we need to create post_helper

def post_helper(post) -> dict:
    return {
        "id": str(post["_id"]),
        "photo_url": post.get("photo_url"),
        "photo_public_id": post.get("photo_public_id"),
        "updated_at": post.get("updated_at"),  # Use .get() for the timestamp
        "text_blocks": post.get("text_blocks", []), # Fallback to an empty list
        "bounding_box_tags": post.get("bounding_box_tags", {}), # Fallback to an empty dict
        "general_tags": post.get("general_tags", []), # Fallback to an empty list
        "associated_epics": post.get("associated_epics", []), # Fallback to an empty list
        "highlights": post.get("highlights", []),  # NEW: Underlined text collection
        "source_url": post.get("source_url"),
        "instagram_handle": post.get("instagram_handle"),
        "instagram_handles": post.get("instagram_handles"),
        "source_account": post.get("source_account"),
        "local_context": post.get("local_context"),
        "region_annotations": post.get("region_annotations"),
        "domain": post.get("domain"),
        "aletheia_cache": post.get("aletheia_cache"),
    }


def post_handles(post: dict) -> list:
    """All author handles on a post: multi-author field first, then legacy
    singular, then whatever the source_url encodes. Ordered, deduped."""
    return normalize_handles(
        (post.get("instagram_handles") or [])
        + [post.get("instagram_handle") or "",
           handle_from_source_url(post.get("source_url")) or ""]
    )





# --- CORRECTED Create Endpoint ---
@router.post("/", response_model=Post, status_code=201)
async def create_post(
    file: UploadFile = File(...),
    general_tags_str: Optional[str] = Form(None)
):
    public_id = f"posts/{uuid.uuid4()}"
    upload_result = cloudinary.uploader.upload(file.file, public_id=public_id)

    # Corrected to match the new schema
    post_document = {
        "photo_url": upload_result["secure_url"],
        "photo_public_id": upload_result["public_id"],
        "updated_at": datetime.now(timezone.utc),
        "text_blocks": [], # Initialize as empty list
        # bounding_box_tags retired (Track A): no longer initialized; reads emit {}.
        "general_tags": general_tags_str.split(',') if general_tags_str else []
    }

    new_post = await post_collection.insert_one(post_document)
    created_post = await post_collection.find_one({"_id": new_post.inserted_id})
    return post_helper(created_post)

def _image_fetch_headers(image_url: str) -> dict:
    """Browser-like headers for fetching an image. Some CDNs (notably Instagram/
    Facebook) reject hotlinking unless the Referer matches the host site, so pick
    a site-appropriate Referer based on the image host."""
    host = (urlparse(image_url).hostname or "").lower()
    if any(h in host for h in ("cdninstagram.com", "fbcdn.net", "instagram.com")):
        referer = "https://www.instagram.com/"
    elif "pinimg.com" in host or "pinterest.com" in host:
        referer = "https://www.pinterest.com/"
    else:
        referer = image_url
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": referer,
    }


# --- Brainstorm: "Aletheia" interpretive analysis (for Chrome Extension) ---
@router.post("/brainstorm")
async def brainstorm_image(request: BrainstormRequest):
    """
    Interpret an image through the Aletheia lenses (phenomenological / semiotic /
    atmospheric) and pose clickable questions. If `answers` (prior viewer choices)
    are supplied, the reading is refined around them — a back-and-forth dialogue.
    Fetches the image server-side (so hotlink-protected sources like Instagram work)
    and feeds base64 to the vision model. Returns the structured interpretation JSON.
    """
    print(f"--- Brainstorm: {request.image_url} ---")
    # Fetch the image bytes ourselves so referer-protected CDNs work, then send as base64.
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(request.image_url, headers=_image_fetch_headers(request.image_url))
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            if not content_type.startswith("image/"):
                content_type = "image/jpeg"
            b64 = base64.b64encode(resp.content).decode("ascii")
            data_url = f"data:{content_type};base64,{b64}"
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: {str(e)}")

    answers = [a.model_dump() for a in request.answers] if request.answers else None
    result = await vision_service.brainstorm_image(data_url, answers=answers)
    if result is None:
        raise HTTPException(status_code=502, detail="Interpretation unavailable (vision service error or unparseable response).")
    return result


# --- Upload from URL (for Chrome Extension) ---
@router.post("/upload-from-url", response_model=Post, status_code=201)
async def create_post_from_url(request: UrlUploadRequest):
    """
    Upload an image from a URL (used by the Chrome extension).
    Fetches the image and uploads it to Cloudinary.
    """
    is_data_url = request.image_url.startswith("data:")
    print(f"--- Processing URL Upload: {'data-url (video frame / base64)' if is_data_url else request.image_url} ---")
    try:
        public_id = f"posts/{uuid.uuid4()}"
        if is_data_url:
            # Extracted video frame / inline base64 — Cloudinary accepts data URIs directly.
            upload_result = cloudinary.uploader.upload(request.image_url, public_id=public_id)
            print(f"Cloudinary upload successful (data url): {upload_result.get('secure_url')}")
        else:
            # Fetch the image from the URL
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(request.image_url, headers=_image_fetch_headers(request.image_url))
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                print(f"Image fetched. Content-Type: {content_type}, Size: {len(response.content)} bytes")

                if not content_type.startswith("image/"):
                    raise HTTPException(status_code=400, detail=f"URL does not point to an image (content-type: {content_type})")

                print("Uploading to Cloudinary...")
                image_data = BytesIO(response.content)
                upload_result = cloudinary.uploader.upload(image_data, public_id=public_id)
                print(f"Cloudinary upload successful: {upload_result.get('secure_url')}")

    except httpx.HTTPStatusError as e:
        print(f"HTTP fetch error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        print(f"Request error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: {str(e)}")
    except Exception as e:
        print(f"CRITICAL UPLOAD ERROR: {type(e).__name__}: {str(e)}")
        # Check if it's a Cloudinary specific error
        if "Must supply cloud_name" in str(e):
             print("CHECK .ENV: CLOUDINARY_NAME is missing!")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    # Normalize the Instagram handle(s) the extension supplied. Collab posts carry
    # several authors; the first is primary and also fills the legacy singular field.
    handles = normalize_handles(
        (request.instagram_handles or [])
        + ([request.instagram_handle] if request.instagram_handle else [])
    )
    handle = handles[0] if handles else None

    # Create the post document
    try:
        post_document = {
            "photo_url": upload_result["secure_url"],
            "photo_public_id": upload_result["public_id"],
            "updated_at": datetime.now(timezone.utc),
            "text_blocks": [],
            # bounding_box_tags retired (Track A): not initialized.
            "general_tags": request.general_tags or [],
            "source_url": request.source_url or request.image_url,  # page (or image) URL for reference
            "instagram_handle": handle,
            "instagram_handles": handles or None,
            "source_account": request.source_account or None,
        }

        new_post = await post_collection.insert_one(post_document)
        print(f"Post created in MongoDB: {new_post.inserted_id}")

        # Attach this image to its account's persona (create a stub if new) so the
        # combined image+account context is available later.
        for i, h in enumerate(handles):
            try:
                # Account snapshot only describes the page's main author → primary only.
                await persona_service.touch(h, request.source_account if i == 0 else None)
            except Exception as e:
                print(f"Persona touch failed for @{h} (non-fatal): {e}")

        created_post = await post_collection.find_one({"_id": new_post.inserted_id})
        return post_helper(created_post)
    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# below part commented out


@router.post("/bulk-upload", response_model=List[Post], status_code=201)
async def create_multiple_posts(files: List[UploadFile] = File(...)):
    created_posts_docs = []
    for file in files:
        public_id = f"posts/{uuid.uuid4()}"
        upload_result = cloudinary.uploader.upload(file.file, public_id=public_id)

        # Corrected to match the new schema
        post_document = {
            "photo_url": upload_result["secure_url"],
            "photo_public_id": upload_result["public_id"],
            "updated_at": datetime.now(timezone.utc),
            "text_blocks": [],
            # bounding_box_tags retired (Track A): not initialized.
            "general_tags": []
        }
        created_posts_docs.append(post_document)

    result = await post_collection.insert_many(created_posts_docs)

    # Fetch all newly created documents to return them
    created_posts = []
    async for post in post_collection.find({"_id": {"$in": result.inserted_ids}}):
        created_posts.append(post_helper(post))

    return created_posts

@router.get("/abc")
async def get_posts_with_text():
    print("--- DEBUG: Inside /with-text endpoint! ---") # Add a print right at the start
    return {"message": "Test successful"} # Simplest possible return


# --- Unconceal review queue (must be registered before "/{post_id}") ---
@router.get("/unconceal-queue")
async def unconceal_queue(handle: Optional[str] = None, limit: int = 50):
    """
    Images that still lack a local (microscopic) context — the work-list for the
    Unconceal review queue. Optionally scoped to one Instagram account.
    """
    needs_context = {"$or": [{"local_context": {"$exists": False}}, {"local_context": None}]}
    query = needs_context
    if handle:
        h = normalize_handle(handle)
        rx = rf"instagram\.com/{re.escape(h)}(?:[/?#]|$)"
        query = {"$and": [needs_context,
                          {"$or": [{"instagram_handle": h},
                                   {"source_url": {"$regex": rx, "$options": "i"}}]}]}

    total = await post_collection.count_documents(query)
    cursor = post_collection.find(
        query,
        {"photo_url": 1, "instagram_handle": 1, "source_url": 1, "general_tags": 1},
    ).sort("updated_at", -1).limit(limit)
    items = []
    async for p in cursor:
        items.append({
            "id": str(p["_id"]),
            "photo_url": p.get("photo_url"),
            "instagram_handle": p.get("instagram_handle"),
            "general_tags": p.get("general_tags", []),
        })
    return {"items": items, "total": total}


@router.get("/{post_id}", response_model=Post)
async def get_post_by_id(post_id: str):
    try:
        # Try to convert the string to an ObjectId
        obj_id = ObjectId(post_id)
    except InvalidId:
        # If it fails, raise a 400 error for bad input
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    post = await post_collection.find_one({"_id": obj_id})

    if post:
        return post_helper(post)

    raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")


@router.get("/{post_id}/context")
async def get_post_context(post_id: str):
    """
    Combined image + account context for a post: the post itself plus the Darpan
    persona dossier for the Instagram account it came from (if known). This is the
    bundle to feed downstream features that build things from image + context.
    """
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    handles = post_handles(post)
    handle = handles[0] if handles else None
    persona = await persona_service.get_persona(handle) if handle else None
    return {
        "post": post_helper(post),
        "instagram_handle": handle,
        "instagram_handles": handles,
        "persona": persona,  # full dossier + account details, or null if not built yet
    }


@router.post("/{post_id}/local-context")
async def set_local_context(post_id: str, request: LocalContextRequest):
    """
    Attach microscopic context to ONE image — the curator's unconcealment commentary
    plus an optional Aletheia reading — and (optionally) roll it up into the account's
    persona as a curator close-reading. Feeds both the specific image and the persona.
    """
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    local_context = {
        "commentary": (request.commentary or "").strip(),
        "aletheia": request.aletheia,
        "updated_at": datetime.now(timezone.utc),
    }
    await post_collection.update_one({"_id": obj_id}, {"$set": {"local_context": local_context}})

    # Roll up into the persona (microscopic → macroscopic). Collab posts carry
    # several authors — feed every one of them.
    handles = post_handles(post)
    fed = False
    if handles and request.feed_to_persona and (local_context["commentary"] or request.aletheia):
        for h in handles:
            try:
                await persona_service.add_local_context(
                    handle=h,
                    post_id=post_id,
                    image_url=post.get("photo_url"),
                    commentary=local_context["commentary"],
                    aletheia=request.aletheia,
                )
                fed = True
            except Exception as e:
                print(f"Persona local-context roll-up failed for @{h} (non-fatal): {e}")

    updated = await post_collection.find_one({"_id": obj_id})
    return {"post": post_helper(updated), "fed_to_persona": fed, "handle": handles[0] if handles else None}


async def _reading_context_for(post: dict, lens_hint: str = "") -> dict:
    """The context Aletheia's lenses are chosen from (Track C §2).

    Assembled from work already done — Track B's domain router, the regions the
    detectors found, and the lenses that habitually fire for this curator (§6.3's
    prior). No extra model calls. Everything here is optional: a post with no domain,
    no regions and no persona yields an empty context, and the reading falls back to
    the general three lenses — exactly today's behavior.
    """
    regions = post.get("region_annotations") or []
    parts, attributes = [], []
    for region in regions:
        for key in ("part", "label"):
            if region.get(key):
                parts.append(region[key])
        attributes.extend(region.get("attributes") or [])

    persona_lenses = []
    handles = post_handles(post)
    if handles:
        try:
            persona_lenses = await persona_service.recurring_lenses(handles[0])
        except Exception as e:
            print(f"Lens prior unavailable (non-fatal, reading stays impersonal): {e}")

    return {
        "domain": (post.get("domain") or {}).get("label", ""),
        "parts": parts,
        "attributes": attributes,
        "regions": [
            {"id": r.get("id"), "label": r.get("label"), "part": r.get("part"),
             "category": r.get("category")}
            for r in regions if r.get("id")
        ],
        "persona_lenses": persona_lenses,
        "lens_hint": lens_hint,
    }


@router.post("/{post_id}/unconceal-suggest")
async def unconceal_suggest(post_id: str):
    """
    LLM pre-draft for the review queue: run Aletheia on the image and draft a
    first-person unconcealment commentary the curator can edit before saving.
    The reading is context-triggered — its lenses come from the image's domain and
    detected parts, biased (but never closed) by this curator's recurring lenses.
    """
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    image_url = post.get("photo_url")
    # Our images are public Cloudinary URLs, so the vision model can fetch directly.
    context = await _reading_context_for(post)
    aletheia = await vision_service.brainstorm_image(image_url, context=context)
    aletheia = aletheia or {"lenses": [], "concealed": "", "uncertainty": ""}
    aletheia.pop("questions", None)  # the queue note doesn't use the MCQ dialogue

    handle = post.get("instagram_handle") or handle_from_source_url(post.get("source_url")) or ""
    draft = await asyncio.to_thread(llm_service.draft_unconcealment, aletheia, handle)
    return {"aletheia": aletheia, "draft_commentary": draft}


@router.post("/{post_id}/aletheia-read")
async def aletheia_read(post_id: str, request: AletheiaReadRequest):
    """
    Read an image through Aletheia at one of two depths (Track C §5) — one engine,
    two renders:

      · `deep` — the creator's reading: every fired lens with its evidence and the
        regions it rests on, the cross-lens tension, 1–3 perceptual forks.
      · `hook` — the audience's: one distilled lens, one fork. The Écart, the pause
        Darshan opens in the scroll.

    Hook readings are **cached on the post** and served from cache thereafter: the same
    image is read once, not once per viewer, which is what makes a scroll-pause reading
    affordable at audience scale. `refresh: true` recomputes.

    Track C emits the reading and its fork. Recording which fork an audience member taps
    (`actor="audience"`) is Track F's endpoint, not this one.
    """
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    depth = "hook" if (request.depth or "deep").lower() == "hook" else "deep"

    # The hook is identical for every viewer of an image, so it is cached. The deep
    # reading is a dialogue (answers reshape it round by round) and never is.
    cached = (post.get("aletheia_cache") or {}).get("hook")
    if depth == "hook" and cached and not request.refresh and not request.answers:
        return {"aletheia": cached, "depth": depth, "cached": True}

    context = await _reading_context_for(post, lens_hint=request.lens or "")
    answers = [a.model_dump() for a in request.answers] if request.answers else None
    reading = await vision_service.brainstorm_image(
        post.get("photo_url"), answers=answers, context=context, depth=depth,
    )
    if reading is None:
        raise HTTPException(status_code=502, detail="Reading unavailable (vision service error or unparseable response).")

    if depth == "hook" and not answers:
        await post_collection.update_one(
            {"_id": obj_id},
            {"$set": {"aletheia_cache.hook": reading,
                      "aletheia_cache.updated_at": datetime.now(timezone.utc)}},
        )

    return {"aletheia": reading, "depth": depth, "cached": False}


def _clip_box_to_parent(box: dict, parent: dict) -> dict:
    """Pull a fine sub-box inside its parent anchor's box so it can't float off the
    object it belongs to (the vision model's boxes are estimates)."""
    px, py = parent.get("x", 0.0), parent.get("y", 0.0)
    pw, ph = parent.get("w", 1.0), parent.get("h", 1.0)
    # pad the parent a touch so tight collars/cuffs at the edge aren't crushed
    pad = 0.04
    x0, y0 = max(0.0, px - pad), max(0.0, py - pad)
    x1, y1 = min(1.0, px + pw + pad), min(1.0, py + ph + pad)
    bx = min(max(box["x"], x0), x1)
    by = min(max(box["y"], y0), y1)
    bw = min(box["w"], x1 - bx)
    bh = min(box["h"], y1 - by)
    return {"x": round(bx, 4), "y": round(by, 4),
            "w": round(max(bw, 0.01), 4), "h": round(max(bh, 0.01), 4)}


def _match_parent(fine: dict, anchors: list) -> Optional[dict]:
    """Link a fine part to a coarse anchor: prefer label match, else the anchor whose
    box most contains the fine part's centre."""
    plabel = (fine.get("parent_label") or "").lower()
    if plabel:
        for a in anchors:
            if plabel in (a.get("label") or "").lower() or (a.get("label") or "").lower() in plabel:
                return a
    cx = fine["box"]["x"] + fine["box"]["w"] / 2
    cy = fine["box"]["y"] + fine["box"]["h"] / 2
    best, best_area = None, 1e9
    for a in anchors:
        b = a.get("box") or {}
        if b.get("x", 0) <= cx <= b.get("x", 0) + b.get("w", 0) and \
           b.get("y", 0) <= cy <= b.get("y", 0) + b.get("h", 0):
            area = b.get("w", 1) * b.get("h", 1)
            if area < best_area:  # smallest containing anchor wins
                best, best_area = a, area
    return best


@router.post("/{post_id}/detect-regions")
async def detect_regions(post_id: str, request: Optional[RegionDetectRequest] = None):
    """
    Two-stage anatomy. STHŪLA (coarse): local YOLO11-seg gives whole-object instance
    masks (real polygons) as anchors. SŪKṢMA (fine): the Groq vision model then dissects
    those anchors SEMANTICALLY into sub-parts — garments, garment sub-sections, body
    parts, textures — steered by `mode` and the curator's free-text `lens`. The fine
    parts are clipped inside their parent anchor. Curator prioritisation/notes survive
    re-runs. `coarse_only` returns just the anchors (fast).
    """
    req = request or RegionDetectRequest()
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    photo_url = post.get("photo_url")

    # --- Stage 1 · STHŪLA: coarse anchors with real masks (local YOLO11-seg). ---
    anchors, source = None, "segmentation"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
            resp.raise_for_status()
            anchors = await asyncio.to_thread(segmentation_service.segment_image_bytes, resp.content)
    except Exception as e:
        print(f"Segmentation fetch/run failed, will fall back: {e}")
        anchors = None
    if not anchors:
        # No local model / nothing found — the vision detector becomes the anchor source.
        anchors = await vision_service.detect_regions(photo_url)
        source = "vision"
    for a in anchors:
        a.setdefault("depth", 0)

    # --- Stage 2 · SŪKṢMA: fine semantic decomposition (Groq vision). ---
    fine = []
    if not req.coarse_only:
        try:
            fine = await vision_service.decompose_regions(
                photo_url, anchors=anchors, lens=req.lens or "", mode=req.mode or "general"
            )
        except Exception as e:
            print(f"Fine decomposition failed (non-fatal): {e}")
            fine = []
        # Link each fine part to its anchor and pull it inside that anchor's box.
        for f in fine:
            parent = _match_parent(f, anchors)
            if parent:
                f["parent_id"] = parent.get("id")
                f["box"] = _clip_box_to_parent(f["box"], parent.get("box") or {})
            f.setdefault("depth", 1)
            # parent_label was only a transient matching key — drop it (Track A:
            # canonicalize on parent_id; parent_label is not a Region field).
            f.pop("parent_label", None)

    regions = (anchors or []) + fine
    if fine:
        source = f"{source}+sukshma"

    # Preserve any prioritisation/notes the curator already set (match by id).
    existing = {r.get("id"): r for r in (post.get("region_annotations") or [])}
    for r in regions:
        # Provenance defaults (Track A): every detected region is auto-authored.
        r.setdefault("actor", "auto")
        r.setdefault("detector", "vision")
        prev = existing.get(r["id"])
        if prev:
            r["prioritised"] = prev.get("prioritised", False)
            r["weight"] = prev.get("weight", 0)
            r["user_note"] = prev.get("user_note", "")
            # a creator who edited an auto region keeps their authorship.
            if prev.get("actor") == "creator":
                r["actor"] = "creator"
        else:
            r.setdefault("prioritised", False)
            r.setdefault("weight", 0)
            r.setdefault("user_note", "")

    await post_collection.update_one({"_id": obj_id}, {"$set": {"region_annotations": regions}})
    return {"regions": regions, "source": source, "anchor_count": len(anchors or []), "fine_count": len(fine)}


async def _embed_marked_regions(post_id: str) -> int:
    """Track C §6.2 — the felt signal becomes a vector.

    When a curator prioritises a part and writes what it does to them, that region is
    the truest query into their taste graph — but it can only be queried if it has an
    embedding. Regions marked by hand often have none (they were drawn, not detected,
    or enrichment never ran). Embed exactly those: prioritised, noted, unvectorized.

    Runs as a background task after the save responds, and is entirely best-effort —
    FashionCLIP absent, image unfetchable, or a bad crop each just leave the region
    unvectorized, costing it a place in future retrieval and nothing else.
    """
    from backend.services import fashion_clip_service as fc

    if not fc.is_available():
        return 0
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        return 0
    post = await post_collection.find_one({"_id": obj_id})
    if not post or not post.get("photo_url"):
        return 0

    regions = post.get("region_annotations") or []
    pending = [r for r in regions
               if r.get("prioritised") and (r.get("user_note") or "").strip()
               and not r.get("embedding_id")]
    if not pending:
        return 0

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(post["photo_url"], headers=_image_fetch_headers(post["photo_url"]))
            resp.raise_for_status()
            img_bytes = resp.content
    except Exception as e:
        print(f"Anuraṇana: could not fetch image to embed marked regions (non-fatal): {e}")
        return 0

    def _compute():
        img = fc._open_image(img_bytes)
        out = []
        for region in pending:
            vector = fc.embed_image(fc._crop_norm(img, region.get("box")))
            if vector:
                out.append((region["id"], vector))
        return out

    try:
        computed = await asyncio.to_thread(_compute)
    except Exception as e:
        print(f"Anuraṇana: embedding marked regions failed (non-fatal): {e}")
        return 0

    by_id = {rid: vec for rid, vec in computed}
    for region in regions:
        vector = by_id.get(region.get("id"))
        if not vector:
            continue
        embedding_id = region_embedding_service.make_embedding_id(post_id, region["id"])
        await region_embedding_service.upsert_embedding(
            embedding_id, vector, model="fashion-clip", post_id=post_id, region_id=region["id"]
        )
        region["embedding_id"] = embedding_id

    if by_id:
        await post_collection.update_one(
            {"_id": obj_id}, {"$set": {"region_annotations": regions}}
        )
    print(f"Anuraṇana: vectorized {len(by_id)} newly-marked region(s) on post {post_id}")
    return len(by_id)


@router.post("/{post_id}/region-annotations")
async def save_region_annotations(post_id: str, request: RegionAnnotationsRequest,
                                  background: BackgroundTasks = None):
    """
    Save the curator's prioritised regions + per-part 'how it affects me' notes. Also
    rolls the prioritised correspondences up into the account's persona as evidence,
    and (in the background) embeds the newly-marked regions so the felt signal — not
    just the label — accrues in the taste graph.
    """
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    # request.regions is validated against the unified Region model; persist as dicts.
    regions_data = [r.model_dump() for r in request.regions]
    await post_collection.update_one(
        {"_id": obj_id}, {"$set": {"region_annotations": regions_data,
                                   "updated_at": datetime.now(timezone.utc)}}
    )

    # Roll prioritised part-correspondences up to the persona (microscopic →
    # macroscopic). Collab posts carry several authors — feed every one of them.
    handles = post_handles(post)
    fed = False
    if handles and request.feed_to_persona:
        notes = [
            f"{r.get('label', 'part')} — {r.get('user_note', '').strip()}"
            for r in regions_data
            if r.get("prioritised") and (r.get("user_note") or "").strip()
        ]
        if notes:
            for h in handles:
                try:
                    await persona_service.add_region_correspondence(h, post_id, post.get("photo_url"), notes)
                    fed = True
                except Exception as e:
                    print(f"Persona region roll-up failed for @{h} (non-fatal): {e}")

    # Vectorize the parts they just marked — after the response, never blocking the save.
    if background is not None:
        background.add_task(_embed_marked_regions, post_id)

    updated = await post_collection.find_one({"_id": obj_id})
    return {"post": post_helper(updated), "fed_to_persona": fed}


def _compute_region_enrichment(img_bytes: bytes, regions: list, post_id: str) -> dict:
    """CPU-bound FashionCLIP work (runs in a thread). For each region: crop → embed
    (skip if already has embedding_id — immutable/cached) → and, on fashion images,
    a first-cut part/attributes[]. Also routes the whole-image domain. Returns the
    updated regions, the (embedding_id, vector, region_id) triples to persist, the
    domain dict, and counts. Never mutates geometry or detector stamping."""
    from backend.services import fashion_clip_service as fc
    from backend.services.region_embedding_service import make_embedding_id

    # Part/attribute labels only make sense on actual garment regions — not the whole
    # figure, a face, hair, or background. Embeddings, by contrast, are computed for
    # every region (the taste vector is useful regardless of category).
    GARMENT_CATS = {"garment", "garment-detail", "accessory"}

    img = fc._open_image(img_bytes)
    domain = fc.classify_domain(img)
    is_fashion = domain.get("is_fashion")

    to_upsert = []
    embedded = labeled = skipped = 0
    out = []
    for r in regions:
        r = dict(r)  # copy; don't mutate the stored dict in place
        # Cache: an embedding is immutable once computed.
        if r.get("embedding_id"):
            skipped += 1
        else:
            vec = fc.embed_image(fc._crop_norm(img, r.get("box")))
            if vec is not None:
                eid = make_embedding_id(post_id, r.get("id", "reg"))
                r["embedding_id"] = eid
                to_upsert.append((eid, vec, r.get("id")))
                embedded += 1
        # First-cut labels: fashion image AND a garment-category region; never overwrite
        # existing part/attrs (a creator's or a later Fashionpedia pass wins).
        if is_fashion and (r.get("category") or "").lower() in GARMENT_CATS:
            lab = fc.label_region(img, r.get("box"))
            if lab.get("part") and not r.get("part"):
                r["part"] = lab["part"]
                labeled += 1
            if lab.get("attributes") and not r.get("attributes"):
                r["attributes"] = lab["attributes"]
        out.append(r)

    return {"regions": out, "to_upsert": to_upsert, "domain": domain,
            "embedded": embedded, "labeled": labeled, "skipped": skipped}


@router.post("/{post_id}/enrich-regions")
async def enrich_regions(post_id: str):
    """FashionCLIP enrichment (Track B · Phase 1): vectorize existing regions into the
    taste-graph sidecar (setting Region.embedding_id), add a first-cut part/attributes[]
    on fashion regions, and tag the image's domain. Purely additive — does NOT create
    or alter geometry/detector (that's detect-regions' job). Idempotent + cached."""
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    from backend.services import fashion_clip_service as fc
    if not fc.is_available():
        raise HTTPException(status_code=503,
            detail="FashionCLIP unavailable (torch/transformers not installed on this deploy).")

    photo_url = post.get("photo_url")
    regions = post.get("region_annotations") or []
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
            resp.raise_for_status()
            img_bytes = resp.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch image: {e}")

    result = await asyncio.to_thread(_compute_region_enrichment, img_bytes, regions, post_id)

    # Persist vectors OUT of the post doc, in the sidecar (keyed by embedding_id).
    for eid, vec, rid in result["to_upsert"]:
        await region_embedding_service.upsert_embedding(
            eid, vec, model="fashion-clip", post_id=post_id, region_id=rid)

    # Persist the embedding_id pointers + first-cut labels + the domain tag on the post.
    await post_collection.update_one(
        {"_id": obj_id},
        {"$set": {"region_annotations": result["regions"], "domain": result["domain"]}},
    )

    updated = await post_collection.find_one({"_id": obj_id})
    return {
        "post": post_helper(updated),
        "domain": result["domain"],
        "embedded": result["embedded"],
        "labeled": result["labeled"],
        "skipped_cached": result["skipped"],
    }

# More general route comes after
@router.get("/", response_model=PaginatedPosts)
async def get_all_posts(page: int = 1, limit: int = 50, tag: Optional[str] = None):
    query = {}
    if tag:
        # Corrected field name (no space)
        query["general_tags"] = tag

    # Corrected to use the query in count_documents
    total_posts = await post_collection.count_documents(query)
    if total_posts == 0:
        return {"posts": [], "total_pages": 0, "current_page": 1}

    skip = (page - 1) * limit
    posts_cursor = post_collection.find(query).sort("_id", -1).skip(skip).limit(limit)

    posts = []
    async for post in posts_cursor:
        posts.append(post_helper(post))

    total_pages = math.ceil(total_posts / limit)
    return {
        "posts": posts,
        "total_pages": total_pages,
        "current_page": page
    }

@router.patch("/{post_id}", response_model=Post)
async def update_post(post_id: str, post_data: PostUpdate):
    update_data = post_data.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    # CRUCIAL: Always update the 'updated_at' timestamp on any edit
    update_data["updated_at"] = datetime.now(timezone.utc)

    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    result = await post_collection.update_one({"_id": obj_id}, {"$set": update_data})

    if result.modified_count == 1:
        if (updated_post := await post_collection.find_one({"_id": obj_id})) is not None:
            return post_helper(updated_post)

    raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")
# --- Refactored DELETE Endpoint ---
@router.delete("/{post_id}", status_code=204)
async def delete_post(post_id: str):
    # First, retrieve the post to get the photo_url for file deletion
    post_to_delete = await post_collection.find_one({"_id": ObjectId(post_id)})
    if not post_to_delete:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")

    cloudinary.uploader.destroy(post_to_delete["photo_public_id"])

    # Delete the post from the database
    await post_collection.delete_one({"_id": ObjectId(post_id)})
    return



@router.get("/tags/", response_model=List[str])
async def get_all_unique_tags():
    tags = await post_collection.distinct("general_tags")
    return tags

@router.get("/tags/popular", response_model=List[str])
async def get_popular_tags(limit: int = 10):
    """
    Returns the most popular tags (tags that appear in the most posts).
    """
    # Aggregate to count tag occurrences
    pipeline = [
        {"$unwind": "$general_tags"},  # Flatten the tags array
        {"$group": {"_id": "$general_tags", "count": {"$sum": 1}}},  # Count occurrences
        {"$sort": {"count": -1}},  # Sort by count descending
        {"$limit": limit},  # Limit to top N tags
        {"$project": {"_id": 0, "tag": "$_id"}}  # Rename _id to tag
    ]
    
    popular_tags = []
    async for doc in post_collection.aggregate(pipeline):
        if doc.get("tag"):
            popular_tags.append(doc["tag"])
    
    return popular_tags


@router.get("/highlights", response_model=List[Post])
async def get_highlights():
    """
    Fetches the 20 most recently updated posts that have textual content
    (either text blocks or general tags).
    """
    # This query finds documents where EITHER text_blocks OR general_tags is not empty
    query = {
        "$or": [
            {"text_blocks": {"$ne": []}},
            {"general_tags": {"$ne": []}}
        ]
    }

    posts_cursor = post_collection.find(query).sort("updated_at", -1).limit(20)

    highlights = []
    async for post in posts_cursor:
        highlights.append(post_helper(post))

    return highlights


# In backend/routers/posts.py

# In backend/routers/posts.py



from backend.services.llm_service import llm_service
from backend.services.editor_llm_service import editor_llm_service

@router.get("/summary/{tag}")
async def get_tag_summary(tag: str):
    """
    Aggregates text from all posts with the given tag and generates a summary and plot suggestions using LLM.
    """
    # Find all posts that have the specified tag in their general_tags list
    query = {"general_tags": tag}
    posts_cursor = post_collection.find(query)
    
    aggregated_text = []
    
    async for post in posts_cursor:
        # Extract text from text_blocks
        if "text_blocks" in post:
            for block in post["text_blocks"]:
                if "content" in block and block["content"]:
                    aggregated_text.append(block["content"])
                    
    full_text = "\n\n".join(aggregated_text)
    
    # Generate summary and plots
    result = llm_service.generate_summary_and_plots(full_text)
    
    return result

@router.post("/summary/generate_story")
async def generate_story(request: StoryGenerationRequest):
    """
    Generates a long story based on the aggregated text of a tag, a plot suggestion, and user commentary.
    """
    # Find all posts that have the specified tag in their general_tags list
    query = {"general_tags": request.tag}
    posts_cursor = post_collection.find(query)
    
    aggregated_text = []
    exemplar = None  # the most recently-read post under this tag

    async for post in posts_cursor:
        # Extract text from text_blocks
        if "text_blocks" in post:
            for block in post["text_blocks"]:
                if "content" in block and block["content"]:
                    aggregated_text.append(block["content"])
        # A story spans many posts, but a context pack is per-image. Ground on the
        # tag's exemplar: the post whose reading is freshest. Better a story rooted in
        # one image genuinely unconcealed than a blur averaged over all of them.
        lc = post.get("local_context") or {}
        if lc.get("aletheia"):
            stamp = lc.get("updated_at")
            if exemplar is None or (stamp and stamp > (exemplar[0] or stamp)):
                exemplar = (stamp, post)

    full_text = "\n\n".join(aggregated_text)

    context_pack = ""
    if exemplar:
        try:
            pack = await anuranana_service.build_context_pack(exemplar[1])
            context_pack = pack.get("text", "")
        except Exception as e:
            print(f"Anuraṇana pack unavailable for story (non-fatal): {e}")

    # Generate story
    result = await asyncio.to_thread(
        llm_service.generate_story_from_plot,
        aggregated_text=full_text,
        plot_suggestion=request.plot_suggestion,
        user_commentary=request.user_commentary,
        context_pack=context_pack,
    )

    return result

@router.get("/untagged/random", response_model=List[Post])
async def get_random_untagged_posts(limit: int = 5):
    """
    Fetches random posts that have no general_tags or empty general_tags.
    """
    # Query for posts with no general_tags or empty general_tags
    query = {
        "$or": [
            {"general_tags": {"$exists": False}},
            {"general_tags": []},
            {"general_tags": {"$eq": None}}
        ]
    }
    
    # Get all matching posts
    posts_cursor = post_collection.find(query)
    all_posts = []
    async for post in posts_cursor:
        all_posts.append(post_helper(post))
    
    # Randomly select up to 'limit' posts
    if len(all_posts) <= limit:
        return all_posts
    else:
        return random.sample(all_posts, limit)

@router.patch("/{post_id}/add-tag", response_model=Post)
async def add_tag_to_post(post_id: str, request: AddTagRequest):
    """
    Adds a tag to a post's general_tags list. If the tag already exists, does nothing.
    """
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    
    # Get the current post
    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")
    
    # Get current tags or initialize empty list
    current_tags = post.get("general_tags", []) or []
    
    # Add tag if it doesn't exist
    if request.tag not in current_tags:
        current_tags.append(request.tag)
    
    # Update the post
    update_data = {
        "general_tags": current_tags,
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await post_collection.update_one(
        {"_id": obj_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 1 or result.matched_count == 1:
        updated_post = await post_collection.find_one({"_id": obj_id})
        return post_helper(updated_post)
    
    raise HTTPException(status_code=500, detail="Failed to update post")

@router.patch("/{post_id}/add-tag-and-story", response_model=Post)
async def add_tag_and_story_to_post(post_id: str, request: AddTagAndStoryRequest):
    """
    Adds a tag to a post's general_tags list AND adds the story as a text block.
    If the tag already exists, it still adds the story.
    """
    try:
        obj_id = ObjectId(post_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    
    # Get the current post
    post = await post_collection.find_one({"_id": obj_id})
    if not post:
        raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")
    
    # Get current tags or initialize empty list
    current_tags = post.get("general_tags", []) or []
    
    # Add tag if it doesn't exist
    if request.tag not in current_tags:
        current_tags.append(request.tag)
    
    # Get current text blocks or initialize empty list
    current_text_blocks = post.get("text_blocks", []) or []
    
    # Create a new text block for the story
    # Use 'paragraph' type for the story, or you could use a custom type like 'story'
    new_story_block = {
        "id": f"block_{uuid.uuid4()}",
        "type": "paragraph",
        "content": request.story,
        "color": None
    }
    
    # Add the story block to the text blocks
    current_text_blocks.append(new_story_block)
    
    # Update the post with both tag and story
    update_data = {
        "general_tags": current_tags,
        "text_blocks": current_text_blocks,
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await post_collection.update_one(
        {"_id": obj_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 1 or result.matched_count == 1:
        updated_post = await post_collection.find_one({"_id": obj_id})
        return post_helper(updated_post)
    
    raise HTTPException(status_code=500, detail="Failed to update post")

@router.post("/summary/generate_story_flow")
async def generate_story_flow(request: StoryFlowRequest):
    """
    Generates a summarized flow of the story in phrases/keywords (ev1->ev2->ev3 format).
    detail_level: "small" (3-5 events), "med" (5-10 events), "big" (10-15 events)
    """
    result = llm_service.generate_story_flow(request.story, request.detail_level)
    return result

@router.post("/suggestions/generate")
async def generate_post_suggestion(request: PostSuggestionRequest):
    """
    Generates suggestions (short prose or story) based on existing text blocks.
    """
    # Convert Pydantic models to dict for LLM service
    text_blocks_dict = [block.dict() for block in request.text_blocks]
    result = editor_llm_service.generate_post_suggestion(
        text_blocks=text_blocks_dict,
        suggestion_type=request.suggestion_type,
        user_commentary=request.user_commentary or ""
    )
    return result

async def _grounding_for(image_url: str) -> str:
    """The Anuraṇana context pack for whatever post this image belongs to (Track C §4).

    The writing endpoints are handed an `image_url`, not a post id, so we resolve the
    post from the URL — which means grounding switches on with no frontend change
    (the Visual pane is Track D's to touch). Never fatal: an image we don't own, a
    missing reading, or a retrieval error all yield an empty pack, and an empty pack
    makes the writer behave exactly as it did before Track C.
    """
    try:
        pack = await anuranana_service.build_context_pack_for_image(image_url)
        return pack.get("text", "")
    except Exception as e:
        print(f"Anuraṇana context pack unavailable (non-fatal, writing ungrounded): {e}")
        return ""


@router.post("/chat/vision")
async def vision_chat(request: VisionChatRequest):
    """
    Vision-enabled chat that can see the image and understand context.
    Uses Llama 4 Maverick for vision capabilities, grounded in this person's
    reading of the image and their accrued taste (Anuraṇana).
    """
    # Convert Pydantic models to dict for LLM service
    text_blocks_dict = [block.dict() for block in request.text_blocks] if request.text_blocks else []
    conversation_dict = [msg.dict() for msg in request.conversation_history] if request.conversation_history else []
    context_pack = await _grounding_for(request.image_url)

    result = await asyncio.to_thread(
        editor_llm_service.chat_with_vision,
        image_url=request.image_url,
        text_blocks=text_blocks_dict,
        user_message=request.user_message,
        conversation_history=conversation_dict,
        context_pack=context_pack,
    )
    return result

@router.post("/rewrite/vision")
async def vision_rewrite(request: VisionRewriteRequest):
    """
    Rewrites a text block with awareness of the image content, grounded in the
    curator's reading and taste history.
    """
    context_pack = await _grounding_for(request.image_url)
    result = await asyncio.to_thread(
        editor_llm_service.rewrite_with_vision,
        image_url=request.image_url,
        block_content=request.block_content,
        rewrite_instruction=request.rewrite_instruction or "",
        context_pack=context_pack,
    )
    return result

@router.post("/flow/expand-node")
async def expand_flow_node(request: NodeExpansionRequest):
    """
    Generates a detailed literary expansion for a specific story flow node.
    Uses two-stage pipeline: Maverick (vision) -> GPT-OSS (literary refinement),
    grounded in the curator's reading and taste history.

    Called when user clicks on a node in the StoryFlow visualization.
    """
    context_pack = await _grounding_for(request.image_url)
    result = await asyncio.to_thread(
        editor_llm_service.generate_node_expansion,
        node_text=request.node_text,
        image_url=request.image_url,
        story_context=request.story_context,
        context_pack=context_pack,
    )
    return result

