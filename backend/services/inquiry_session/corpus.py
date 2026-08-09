"""
HARNESS-002D — post ids in, image refs and fingerprints out. Nothing else.

WHY THIS IS NOT A POST LOADER. There is no shared post-by-id resolver in this repository:
`routers/runs.py::_posts_for` holds the `ObjectId`-then-raw-string idiom privately, and importing a
router into a service to reuse twelve lines would be worse than restating them. What this module
takes from the tree rather than rebuilding is the part that matters — `movement_kernel`'s
`posts_fingerprint` / `assert_posts_unchanged`, the same pair PR #191 used to prove a real Director
execution left its source posts byte-identical.

WHAT IT READS AND WHAT IT REFUSES TO CARRY. An id, a title, a photo url, and a fingerprint of the
whole document. Nothing about region annotations, marks, percepts or grounds reaches the session:
the inquiry's own reading of the images is the scene theorist's job, and a corpus resolver that
handed the frame a region count would be handing a mind that has not seen the pictures a fact about
them.

AN UNREADABLE ID IS KEPT, NOT DROPPED. A post that does not resolve arrives as a `PostRef` with
`readable=False` and a reason. Dropping it would let a session report on two images while the
person believes it read three — the same rule `hydrate_corpus` states for a run.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from bson.errors import InvalidId
from bson.objectid import ObjectId

from backend.schemas.inquiry_session import PostRef
from backend.services.movement_kernel import assert_posts_unchanged, posts_fingerprint


async def _find(posts, raw: str) -> Optional[Mapping[str, Any]]:
    """The repository's own two-step: an ObjectId if the string is one, otherwise the raw key."""
    try:
        doc = await posts.find_one({"_id": ObjectId(raw)})
    except (InvalidId, TypeError):
        doc = None
    if doc is None:
        doc = await posts.find_one({"_id": raw})
    return doc


async def resolve(post_ids: Sequence[str], *, collection=None
                  ) -> Tuple[List[PostRef], Dict[str, Dict[str, Any]]]:
    """Post ids → refs the session carries, plus the raw documents the fingerprint is taken over.

    The documents are returned separately and are NEVER put on the session. They exist for two
    things only: the image url the theorist is handed, and the fingerprint.
    """
    if collection is None:
        from backend.database import post_collection
        collection = post_collection

    refs: List[PostRef] = []
    docs: Dict[str, Dict[str, Any]] = {}
    for raw in post_ids:
        key = str(raw).strip()
        if not key:
            continue
        doc = await _find(collection, key)
        if not doc:
            refs.append(PostRef(post_id=key, readable=False,
                                note="no post with this id; it is recorded rather than dropped so "
                                     "the session cannot report on fewer images than were chosen"))
            continue
        docs[key] = dict(doc)
        refs.append(PostRef(
            post_id=key,
            title=str(doc.get("title") or doc.get("instagram_handle") or "").strip(),
            image_ref=str(doc.get("photo_url") or "").strip(),
            fingerprint=posts_fingerprint({key: doc}).get(key, ""),
            readable=bool(doc.get("photo_url")),
            note="" if doc.get("photo_url") else "this post carries no image; there is nothing for "
                                                 "the scene theorist to read"))
    return refs, docs


def fingerprints_of(refs: Sequence[PostRef]) -> Dict[str, str]:
    return {r.post_id: r.fingerprint for r in refs if r.fingerprint}


async def assert_unchanged(refs: Sequence[PostRef], *, collection=None) -> None:
    """Re-read every readable post and compare. Raises `PostsMutated` on any difference.

    Called before each write rather than once at the end: a session that mutated a post halfway
    through and put it back would pass an end-to-end check and fail this one.
    """
    before = fingerprints_of(refs)
    if not before:
        return
    _, docs = await resolve(list(before), collection=collection)
    assert_posts_unchanged(before, posts_fingerprint(docs))


def image_refs_for(refs: Sequence[PostRef]) -> List[Dict[str, str]]:
    """What the scene theorist is handed: id, title, url. Readable posts only — a theorist given a
    ref with no url would call an image endpoint with an empty string and report the failure as a
    reading that found nothing."""
    return [{"post_id": r.post_id, "title": r.title, "image_ref": r.image_ref}
            for r in refs if r.readable and r.image_ref]


def corpus_context_for(refs: Sequence[PostRef]) -> Dict[str, Any]:
    """What the FRAMER is handed. Ids, titles and a count — and deliberately no url, because the
    frame is the reading of a question by a mind that has not seen the pictures."""
    readable = [r for r in refs if r.readable]
    return {"post_ids": [r.post_id for r in readable],
            "titles": [r.title for r in readable if r.title]}


__all__ = ["resolve", "fingerprints_of", "assert_unchanged", "image_refs_for",
           "corpus_context_for", "assert_posts_unchanged", "posts_fingerprint"]
