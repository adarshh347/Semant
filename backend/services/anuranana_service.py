"""
Anuraṇana (अनुरणन — the after-resonance, the echo that lingers once the bell stops):
the taste graph, and the context pack it feeds the pen. Darshan Track C · §4.

The gap this closes: the inline writer (`editor_llm_service.chat_with_vision` /
`rewrite_with_vision` / `generate_node_expansion`) and story generation were called with
`image_url` + `text_blocks` only. They never saw the Aletheia reading, never saw which
parts moved the curator, never saw a line of their accrued taste. The intelligence
existed; the pen was blind to it. `build_context_pack` assembles what the pen should
have been standing on all along:

    [IMAGE READING]          this image's lenses, evidence, tension, what it conceals
    [PARTS THAT MOVED THEM]  prioritised regions — label/part and the curator's own note
    [YOUR TASTE HISTORY]     top-k FashionCLIP-retrieved past regions + the notes on them
    [VOICE]                  the persona dossier's tone / vocabulary / devices
    [THE ASK]                the user's actual request

**Context engineering, not context dumping.** RAG degrades under prompt saturation, and
LLMs attend poorly to evidence buried mid-prompt ("lost in the middle"). So the pack is
small, ranked, hard-capped, labelled so the model can find each part, and front-and-back
loaded: the reading opens it, the ask closes it, retrieved material sits in the middle
where a miss costs least.

**Retrieval is own-history-only** (Adarsh's lock). The top-k never leaves this curator's
own posts, because a `user_note` is an intimate thing — "how it affects me" — and another
person's should never surface inside your writing prompt. Ownership is resolved here;
the sidecar itself is handle-blind and simply takes the post ids it's given.

**No GPU, no model load.** Retrieval queries with vectors *already stored* by Track B's
enrichment, so the pack builds even where torch/transformers aren't installed. Every
section degrades independently: no reading, no vectors, no persona, or no notes each
just drop their section, and an empty pack reproduces today's behavior exactly.
"""

from typing import List, Optional, Sequence

from backend.database import post_collection
from backend.services import region_embedding_service
from backend.services.persona_service import (
    persona_service, normalize_handles, handle_from_source_url,
)

# Caps. Each exists to keep the pack from saturating the prompt; tune together.
MAX_LENSES = 4
MAX_REGION_NOTES = 6
MAX_RETRIEVED = 5
MAX_QUERY_VECTORS = 3      # prioritised regions we search from
NOTE_CHARS = 180           # a felt-note is a sentence, not an essay
MIN_SIMILARITY = 0.5       # below this, a "similar" region isn't similar


def _handles(post: dict) -> List[str]:
    """Author handles on a post. Mirrors the router's `post_handles`, resolved here so
    the service layer never imports a router."""
    return normalize_handles(
        (post.get("instagram_handles") or [])
        + [post.get("instagram_handle") or "",
           handle_from_source_url(post.get("source_url")) or ""]
    )


def _clip(text: str, limit: int = NOTE_CHARS) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _area(region: dict) -> float:
    box = region.get("box") or {}
    try:
        return float(box.get("w", 0)) * float(box.get("h", 0))
    except (TypeError, ValueError):
        return 0.0


def _region_name(region: dict) -> str:
    return (region.get("label") or region.get("part")
            or region.get("category") or "part").strip()


async def _own_post_ids(handles: Sequence[str]) -> List[str]:
    """Every post authored by these handles — the retrieval scope. Uncapped, so a
    prolific curator's history is searched whole. Empty when the post has no handle,
    which correctly yields no taste history rather than everyone's."""
    ids: List[str] = []
    for handle in handles:
        ids.extend(await persona_service.matched_post_ids(handle))
    return list(dict.fromkeys(ids))


def _query_regions(regions: Sequence[dict]) -> List[dict]:
    """Which regions we search the taste graph *from*. The parts the curator marked as
    mattering are the truest query; absent any, fall back to the largest embedded
    regions so a never-annotated image still retrieves something."""
    embedded = [r for r in regions if r.get("embedding_id")]
    prioritised = [r for r in embedded if r.get("prioritised")]
    pool = prioritised or sorted(embedded, key=_area, reverse=True)
    return pool[:MAX_QUERY_VECTORS]


async def _retrieve_taste_history(
    post_id: str, regions: Sequence[dict], own_post_ids: Sequence[str], top_k: int,
) -> List[dict]:
    """Top-k past regions of this curator's that resemble this image's salient parts,
    carrying the notes they wrote on them. Only regions with a `user_note` survive: an
    unnoted region has a vector but no felt meaning, and it is the meaning we're after.
    """
    query_regions = _query_regions(regions)
    if not query_regions or not own_post_ids:
        return []

    best: dict = {}  # (post_id, region_id) -> hit, keeping the strongest score
    for qr in query_regions:
        stored = await region_embedding_service.get_embedding(qr["embedding_id"])
        if not stored or not stored.get("vector"):
            continue
        hits = await region_embedding_service.search_similar(
            stored["vector"], post_ids=own_post_ids, exclude_post_id=post_id,
            top_k=top_k * 2, min_score=MIN_SIMILARITY,
        )
        for hit in hits:
            key = (hit["post_id"], hit["region_id"])
            if key not in best or hit["score"] > best[key]["score"]:
                best[key] = {**hit, "queried_from": _region_name(qr)}

    if not best:
        return []

    # Hydrate: the vectors told us *which* regions; the posts hold what was felt there.
    wanted_posts = {pid for pid, _ in best}
    notes: List[dict] = []
    for pid in wanted_posts:
        obj_id = _to_object_id(pid)
        if obj_id is None:      # a malformed post_id in the sidecar; skip, never query {_id: None}
            continue
        doc = await post_collection.find_one({"_id": obj_id}, {"region_annotations": 1})
        if not doc:
            continue
        by_id = {r.get("id"): r for r in (doc.get("region_annotations") or [])}
        for (hit_pid, rid), hit in best.items():
            if hit_pid != pid:
                continue
            region = by_id.get(rid)
            if not region or not (region.get("user_note") or "").strip():
                continue
            notes.append({
                "name": _region_name(region),
                "note": _clip(region["user_note"]),
                "score": hit["score"],
                "queried_from": hit["queried_from"],
                "post_id": pid,
            })

    return sorted(notes, key=lambda n: -n["score"])[:top_k]


def _to_object_id(pid: str):
    from bson import ObjectId
    from bson.errors import InvalidId
    try:
        return ObjectId(pid)
    except (InvalidId, TypeError):
        return None


def _render_reading(aletheia: Optional[dict]) -> str:
    if not aletheia:
        return ""
    lines = []
    domain = (aletheia.get("domain") or "").strip()
    if domain:
        lines.append(f"domain: {domain}")
    for lens in (aletheia.get("lenses") or [])[:MAX_LENSES]:
        reading = _clip(lens.get("reading"), 220)
        if not reading:
            continue
        line = f"- {lens.get('name', 'Lens')} ({lens.get('intensity', 0)}): {reading}"
        if lens.get("evidence"):
            line += f"  [seen in: {_clip(lens['evidence'], 90)}]"
        lines.append(line)
    if aletheia.get("tension"):
        lines.append(f"- tension: {_clip(aletheia['tension'], 200)}")
    if aletheia.get("concealed"):
        lines.append(f"- concealed: {_clip(aletheia['concealed'], 200)}")
    return "\n".join(lines)


def _render_region_notes(regions: Sequence[dict]) -> str:
    marked = [r for r in regions
              if r.get("prioritised") and (r.get("user_note") or "").strip()]
    marked.sort(key=lambda r: -(r.get("weight") or 0))
    return "\n".join(
        f"- {_region_name(r)}: \"{_clip(r['user_note'])}\""
        for r in marked[:MAX_REGION_NOTES]
    )


def _render_taste_history(notes: Sequence[dict]) -> str:
    return "\n".join(
        f"- {n['name']} (like this image's {n['queried_from']}): \"{n['note']}\""
        for n in notes
    )


def _render_voice(dossier: Optional[dict]) -> str:
    voice = (dossier or {}).get("voice") or {}
    bits = [f"{k}: {_clip(voice.get(k), 120)}"
            for k in ("tone", "vocabulary", "devices") if (voice.get(k) or "").strip()]
    return " | ".join(bits)


async def build_context_pack(
    post: dict, ask: str = "", top_k: int = MAX_RETRIEVED,
) -> dict:
    """
    Assemble the writer's ground: this image's reading, the parts that moved the
    curator, their nearest past correspondences, and their voice.

    Returns `{"text", "sections", "retrieved", "stats"}`. `text` is the block to inject
    into a prompt and is `""` when nothing was found — callers treat an empty pack as
    "write as you did before", so every writing path degrades to today's behavior.
    """
    regions = post.get("region_annotations") or []
    post_id = str(post.get("_id") or post.get("id") or "")
    aletheia = (post.get("local_context") or {}).get("aletheia")

    # The reading may carry a domain of its own; else fall back to Track B's router.
    if aletheia and not aletheia.get("domain"):
        aletheia = {**aletheia, "domain": (post.get("domain") or {}).get("label", "")}

    handles = _handles(post)
    dossier = None
    if handles:
        persona = await persona_service.get_persona(handles[0])
        dossier = (persona or {}).get("dossier")

    own_ids = await _own_post_ids(handles)
    retrieved = await _retrieve_taste_history(post_id, regions, own_ids, top_k)

    sections = {
        "reading": _render_reading(aletheia),
        "region_notes": _render_region_notes(regions),
        "taste_history": _render_taste_history(retrieved),
        "voice": _render_voice(dossier),
    }

    # Front-loaded: the reading. Back-loaded: the ask. Retrieved material sits between,
    # where the "lost in the middle" cost falls on the least critical evidence.
    blocks = []
    if sections["reading"]:
        blocks.append("[IMAGE READING — how this image was unconcealed]\n" + sections["reading"])
    if sections["region_notes"]:
        blocks.append("[PARTS THAT MOVED THEM — their own words]\n" + sections["region_notes"])
    if sections["taste_history"]:
        blocks.append("[THEIR TASTE HISTORY — how they've felt about parts like these before]\n"
                      + sections["taste_history"])
    if sections["voice"]:
        blocks.append("[VOICE — write as this person writes]\n" + sections["voice"])
    if blocks and ask:
        blocks.append("[THE ASK]\n" + _clip(ask, 500))

    return {
        "text": "\n\n".join(blocks),
        "sections": sections,
        "retrieved": retrieved,
        "stats": {
            "post_id": post_id,
            "handle": handles[0] if handles else None,
            "own_posts_searched": len(own_ids),
            "query_regions": len(_query_regions(regions)),
            "retrieved_count": len(retrieved),
            "has_reading": bool(sections["reading"]),
            "has_voice": bool(sections["voice"]),
        },
    }


async def build_context_pack_for_image(image_url: str, ask: str = "") -> dict:
    """
    Same pack, resolved from an image URL. The writing endpoints (`/chat/vision`,
    `/rewrite/vision`, `/flow/expand-node`) are handed an `image_url`, not a post id —
    so we look the post up by it. An unknown image yields an empty pack, never an error:
    the writer must keep working on images that aren't ours.
    """
    if not image_url:
        return {"text": "", "sections": {}, "retrieved": [], "stats": {}}
    post = await post_collection.find_one({"photo_url": image_url})
    if not post:
        return {"text": "", "sections": {}, "retrieved": [], "stats": {"post_id": None}}
    return await build_context_pack(post, ask=ask)
