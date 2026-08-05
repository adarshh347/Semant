"""
ATLAS L1 — the corpus routes: name a walk, order it, reopen it.

Six endpoints over one thin document (`corpus_store`). The curation flow C1 was built route-ready
for, made real.

    POST   /api/v1/corpora                    title + why + ordered images → the new corpus
    GET    /api/v1/corpora                    the recent walks, so a curator can find one again
    GET    /api/v1/corpora/{id}               the stored document
    GET    /api/v1/corpora/{id}/view          the same, hydrated from the ledger for rendering
    PATCH  /api/v1/corpora/{id}               retitle, restate, reorder, re-note, add, drop
    DELETE /api/v1/corpora/{id}               forget the walk; the posts are untouched

WHY `GET {id}` AND `GET {id}/view` ARE TWO ENDPOINTS. The same reason the Atlas keeps them apart:
the first returns exactly what is stored, so what a corpus does and does not contain is inspectable
by `curl` rather than asserted in a comment. The second assembles the drawable view — thumbnails,
titles, how much each image already carries — from the posts at read time, which is where percept
truth is allowed to appear.

READ-ONLY WITH RESPECT TO EVIDENCE, WITHOUT EXCEPTION. Nothing here writes to a post, creates a
percept, or touches the ledger. A corpus is an ORDERING of images somebody already has; curating
one cannot change what any of them shows. This file has no post write in it and a test greps for
that.

ORDER IS THE ARGUMENT, and it is the reason `PATCH` distinguishes a reorder from a membership
change rather than accepting a new list and diffing it. "I moved the stair earlier" and "I removed
the rotunda" would look identical in a whole-list write, and only one of them is a thing a curator
would want to do by accident.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from bson.errors import InvalidId
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.database import post_collection
from backend.services import corpus_store as C

router = APIRouter()


class CorpusImageIn(BaseModel):
    post_id: str
    note: str = ""          # why this image sits where it sits, in the curator's words


class CreateCorpusRequest(BaseModel):
    title: str = ""
    why: str = ""           # what this SEQUENCE is for — travels into the planner's prompt
    images: List[CorpusImageIn] = Field(default_factory=list)


class PatchCorpusRequest(BaseModel):
    """Every field optional; each one is a different gesture, and they do not overlap."""
    title: Optional[str] = None
    why: Optional[str] = None
    images: Optional[List[CorpusImageIn]] = None    # replace the whole walk
    move: Optional[str] = None                      # post_id to move…
    to: Optional[int] = None                        # …to this position
    note_for: Optional[str] = None                  # post_id whose note to set…
    note: Optional[str] = None                      # …to this text
    add: Optional[List[CorpusImageIn]] = None       # append to the end of the walk
    remove: Optional[str] = None                    # post_id to drop


async def _posts_for(post_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """post id → post document. An id that resolves to nothing is simply absent from the map; the
    view renders it as an image that could not be read rather than dropping it from the walk."""
    out: Dict[str, Dict[str, Any]] = {}
    for raw in post_ids:
        doc = None
        try:
            doc = await post_collection.find_one({"_id": ObjectId(raw)})
        except (InvalidId, TypeError):
            doc = None
        if doc is None:
            doc = await post_collection.find_one({"_id": raw})
        if doc:
            out[str(raw)] = doc
    return out


async def _or_404(corpus_id: str) -> Dict[str, Any]:
    doc = await C.get_corpus(corpus_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"no corpus '{corpus_id}'")
    return doc


def _view(doc: Dict[str, Any], posts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The stored walk + what the ledger currently says about each image.

    Assembled at READ time, every time. An image whose post cannot be read stays IN the walk and
    says so — "this image has no percepts" and "this image could not be loaded" are different facts
    about a corpus, and a walk that quietly shortened itself would be lying about its own extent.
    """
    images = []
    for entry in doc.get("images") or []:
        pid = str(entry.get("post_id"))
        post = posts.get(pid)
        row = {"post_id": pid, "position": entry.get("position"), "note": entry.get("note") or ""}
        if post is None:
            row.update({"readable": False, "image_ref": "", "title": "", "committed": 0,
                        "unreadable_reason": f"post:{pid} could not be read"})
        else:
            row.update({
                "readable": True,
                "image_ref": str(post.get("photo_url") or ""),
                "title": str(post.get("instagram_handle") or post.get("domain") or ""),
                # A count, not a summary: what this image already carries, so a curator can see
                # which parts of the walk have been looked at and which have not.
                "committed": (len(post.get("region_annotations") or [])
                              + len(post.get("visual_marks") or [])
                              + len(post.get("grounds") or [])),
                "unreadable_reason": None,
            })
        images.append(row)
    out = C._out(doc) or {}
    out["images"] = images
    out["unreadable"] = [i["post_id"] for i in images if not i["readable"]]
    return out


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_corpus(body: CreateCorpusRequest):
    """Name a walk. The ORDER of `images` is the walk's order and is kept exactly."""
    images = [i.model_dump() for i in body.images]
    if not images:
        raise HTTPException(status_code=400,
                            detail="a corpus needs at least one image — a walk with none is not "
                                   "a walk, and an empty one would refuse everywhere downstream")
    if len(images) > C.MAX_IMAGES:
        raise HTTPException(status_code=400,
                            detail=f"a corpus holds at most {C.MAX_IMAGES} images "
                                   f"(asked for {len(images)})")
    doc = await C.create_corpus(title=body.title, why=body.why, images=images)
    return C._out(doc)


@router.get("")
@router.get("/")
async def list_corpora(limit: int = 50):
    docs = await C.list_corpora(limit=max(1, min(limit, 200)))
    return {"corpora": [C._out(d) for d in docs]}


@router.get("/{corpus_id}")
async def get_corpus(corpus_id: str):
    """The STORED document, verbatim — ids and order, no percept data."""
    return C._out(await _or_404(corpus_id))


@router.get("/{corpus_id}/view")
async def get_corpus_view(corpus_id: str):
    """The walk, hydrated from the ledger — what a curation surface draws."""
    doc = await _or_404(corpus_id)
    return _view(doc, await _posts_for(C.post_ids_of(doc)))


@router.patch("/{corpus_id}")
async def patch_corpus(corpus_id: str, body: PatchCorpusRequest):
    """Retitle, restate, reorder, re-note, add or drop. Refusals travel WITH the change.

    A gesture that names an image this corpus does not hold does not fail the request — the other
    parts of the patch apply and the client is told which one it asked about that is not here. Same
    discipline as the Atlas's arrangement save, and for the same reason: a curator adjusting four
    things should not lose three of them because the fourth was stale.
    """
    doc = await _or_404(corpus_id)
    refused: List[Dict[str, str]] = []
    images = list(doc.get("images") or [])

    if body.images is not None:
        images = C.clean_images([i.model_dump() for i in body.images])
    if body.add:
        images = C.clean_images(images + [i.model_dump() for i in body.add])
    if body.remove:
        images, why = C.without_image(images, body.remove)
        if why:
            refused.append(why)
    if body.move is not None and body.to is not None:
        images, why = C.reorder(images, body.move, body.to)
        if why:
            refused.append(why)
    if body.note_for is not None:
        images, why = C.with_note(images, body.note_for, body.note or "")
        if why:
            refused.append(why)

    if len(images) > C.MAX_IMAGES:
        raise HTTPException(status_code=400,
                            detail=f"a corpus holds at most {C.MAX_IMAGES} images")

    if images != list(doc.get("images") or []):
        updated = await C.save_images(corpus_id, images)
        doc = updated if updated is not None else doc
    if body.title is not None or body.why is not None:
        updated = await C.save_meta(corpus_id, title=body.title, why=body.why)
        doc = updated if updated is not None else doc

    return {"corpus": C._out(doc), "refused": refused}


@router.delete("/{corpus_id}")
async def delete_corpus(corpus_id: str):
    """Forget the walk. The posts are untouched, and so is any Atlas opened from it — a canvas
    resolved its post ids when it was created and keeps them."""
    await _or_404(corpus_id)
    return {"deleted": await C.delete_corpus(corpus_id), "id": corpus_id}
