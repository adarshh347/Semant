"""
L1 — the curated corpus: a named, ordered walk that outlives the canvas built over it.

C1 wrote the reason this module did not exist yet, and it is worth quoting because it is also the
condition this module has to meet:

    THERE IS NO PERSISTED CORPUS TO POINT AT, so `corpus_ref` names one of the two things that
    actually exist on main: an explicit list of post ids, or a run whose stored spec already names
    them. Inventing a corpus collection would have been a fifth place a corpus can be defined, and
    the one that nothing else reads.

That was right when nothing read it. It stops being right the moment a corpus has to be REUSED —
opened again next week, re-sequenced after a walk you took differently, handed to a sensory pass
and then to a writer as the same object. A list of post ids typed into a picker cannot be any of
those: it is gone the moment the canvas is closed, and the ORDER — which M1 insists is the argument
— survives only as an accident of the order somebody happened to click.

So this is the fifth place, and the debt it owes is to be the one that IS read. `corpus_ref` gains
a third kind that points here; `POST /atlas` resolves a corpus id into the ordered post ids it
already understood; and nothing else changes. M1's `build_corpus` still consumes an ordered tuple
of post ids, exactly as before.

WHAT A CORPUS IS, AND WHAT IT IS NOT.

  It IS: a title, a reason it exists, and an ORDERED list of images, each with the curator's note
  about why it sits where it sits. M1's `CorpusImage.note` was built for this and had nowhere to
  come from — "a corpus that cannot say why the stair follows the colonnade is a folder."

  It is NOT: percept data. Not a canvas. Not a run. A corpus references posts by id and stores
  nothing about what is in them, for the same reason the Atlas document does not: a stale copy of
  a photograph's evidence is worse than no copy, because it looks authoritative.

ORDER IS THE ONLY THING THIS MODULE IS OPINIONATED ABOUT. `reorder` moves an image and renumbers
the rest; it cannot add or drop one, because a reorder that could quietly change the membership of
a walk would let "I moved the stair earlier" become "I removed the rotunda" with no visible
difference. Adding and removing are their own calls.

PURE WHERE IT CAN BE. Shaping is module-level functions with no database and no clock; the async
functions at the bottom are the thin store, injectable for tests.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence
from uuid import uuid4

CORPUS_CONTRACT_VERSION = 1

# How many images one curated corpus may hold. The Atlas's own cap is 60; a corpus is the thing an
# Atlas is opened FROM, so it cannot usefully be larger than one.
MAX_IMAGES = 60

# Refusal reasons, a closed set — a refusal a caller cannot branch on is a string, not a contract.
REFUSED_EMPTY = "no_images"                 # a walk with no images is not a walk
REFUSED_UNKNOWN_IMAGE = "unknown_image"     # asked to move/drop something this corpus does not hold
REFUSED_OUT_OF_RANGE = "position_out_of_range"
REFUSED_TOO_MANY = "too_many_images"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return f"corpus_{uuid4().hex[:12]}"


def _out(doc: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Mongo doc → API shape. Same `_id` → `id` convention as the Atlas and manuscript stores, so
    two collections in one system do not read differently for no reason."""
    if doc is None:
        return None
    out = dict(doc)
    out["id"] = out.pop("_id", None)
    return out


# ── shaping ──────────────────────────────────────────────────────────────────

def clean_image(raw: Any, position: int) -> Optional[Dict[str, Any]]:
    """One entry of the walk: a post id, where it sits, and why.

    Returns None for anything without a post id. A corpus entry that names no image is not an
    empty slot to be filled later — it is a typo, and keeping it would put a hole in the sequence
    that every downstream consumer would have to remember to skip.
    """
    if isinstance(raw, Mapping):
        post_id = str(raw.get("post_id") or raw.get("id") or "").strip()
        note = str(raw.get("note") or "").strip()
    else:
        post_id = str(raw or "").strip()
        note = ""
    if not post_id:
        return None
    return {"post_id": post_id, "position": position, "note": note}


def clean_images(raw: Sequence[Any]) -> List[Dict[str, Any]]:
    """The walk, in the order given, deduplicated while KEEPING that order.

    The same photograph twice is one image in two positions — a corpus this gate does not model,
    and the same call `normalize_corpus_ref` makes. Positions are assigned from the surviving
    order rather than taken from the payload: a client that sent `position` fields could otherwise
    disagree with the array it sent them in, and there would be no way to tell which it meant.
    """
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in raw or []:
        entry = clean_image(item, len(out))
        if entry is None or entry["post_id"] in seen:
            continue
        seen.add(entry["post_id"])
        out.append(entry)
    return out


def new_corpus_doc(*, corpus_id: str, title: str = "", why: str = "",
                   images: Sequence[Any] = (), now: Optional[str] = None) -> Dict[str, Any]:
    """The document a corpus starts as. Pure — no clock it is not handed, no database."""
    stamp = now or utc_now()
    return {
        "_id": corpus_id,
        "contract_version": CORPUS_CONTRACT_VERSION,
        "title": str(title or ""),
        # WHY this sequence exists, in the curator's words. It travels into `Corpus.why` and from
        # there into the argument planner's prompt — the one place a model is told what the walk
        # is FOR, rather than being left to infer it from filenames.
        "why": str(why or ""),
        "images": clean_images(images),
        "created_at": stamp,
        "updated_at": stamp,
    }


def post_ids_of(doc: Mapping[str, Any]) -> List[str]:
    """The ordered post ids — exactly what `build_corpus` and `POST /atlas` already consume."""
    return [str(i.get("post_id")) for i in (doc.get("images") or [])
            if isinstance(i, Mapping) and i.get("post_id")]


def reorder(images: Sequence[Mapping[str, Any]], post_id: str,
            to: int) -> tuple[List[Dict[str, Any]], Optional[Dict[str, str]]]:
    """Move one image to a new position. Returns `(images, refusal)`.

    MEMBERSHIP IS NOT TOUCHED. This cannot add or drop an image, and that is the whole point: a
    reorder that could change what the walk contains would let "I moved the stair earlier" and "I
    removed the rotunda" look identical in the record.
    """
    current = [dict(i) for i in images or []]
    at = next((n for n, i in enumerate(current) if str(i.get("post_id")) == str(post_id)), None)
    if at is None:
        return current, {"reason": REFUSED_UNKNOWN_IMAGE,
                         "detail": f"this corpus holds no image '{post_id}'"}
    if not 0 <= to < len(current):
        return current, {"reason": REFUSED_OUT_OF_RANGE,
                         "detail": f"position {to} is outside a walk of {len(current)}"}
    moved = current.pop(at)
    current.insert(to, moved)
    for n, item in enumerate(current):
        item["position"] = n
    return current, None


def with_note(images: Sequence[Mapping[str, Any]], post_id: str,
              note: str) -> tuple[List[Dict[str, Any]], Optional[Dict[str, str]]]:
    """Set the curator's reason for one image's place in the walk."""
    current = [dict(i) for i in images or []]
    for item in current:
        if str(item.get("post_id")) == str(post_id):
            item["note"] = str(note or "").strip()
            return current, None
    return current, {"reason": REFUSED_UNKNOWN_IMAGE,
                     "detail": f"this corpus holds no image '{post_id}'"}


def without_image(images: Sequence[Mapping[str, Any]],
                  post_id: str) -> tuple[List[Dict[str, Any]], Optional[Dict[str, str]]]:
    """Drop one image and close the gap. An id this corpus does not hold is refused, not ignored —
    a client that thinks it removed something has to be told it did not."""
    current = [dict(i) for i in images or [] if str(i.get("post_id")) != str(post_id)]
    if len(current) == len(images or []):
        return [dict(i) for i in images or []], {
            "reason": REFUSED_UNKNOWN_IMAGE, "detail": f"this corpus holds no image '{post_id}'"}
    for n, item in enumerate(current):
        item["position"] = n
    return current, None


# Keys that would mean a corpus document had begun to hold what the ledger holds. Checked, like
# the Atlas's own guard, because it is easy to break by accident and expensive to notice.
_FORBIDDEN_IMAGE_KEYS = frozenset({
    "geometry", "grounds", "marks", "regions", "percepts", "strokes", "mask", "box",
    "photo_url", "image_url", "image_ref", "epistemic_status", "provenance", "visual_marks",
})


def assert_no_percept_data(doc: Mapping[str, Any]) -> None:
    """Raise if a corpus has started to copy the ledger instead of pointing at it.

    A corpus names images by id and says where each one sits. The moment an entry cached a
    `photo_url`, re-uploading that post would leave the walk pointing at a picture that no longer
    exists, in a document that looks authoritative — the same failure the Atlas document is
    arranged to make impossible.
    """
    for image in doc.get("images") or []:
        if not isinstance(image, Mapping):
            continue
        leaked = sorted(set(image.keys()) & _FORBIDDEN_IMAGE_KEYS)
        if leaked:
            raise ValueError(
                f"corpus image '{image.get('post_id')}' carries percept data: {leaked}. "
                "A corpus references posts by id; it never copies them.")


# ── the store ────────────────────────────────────────────────────────────────

def _collection(collection=None):
    """The corpora collection, injectable. Tests hand a fake; production gets the real one.
    Imported lazily so this module is exercisable with no database configured at all."""
    if collection is not None:
        return collection
    from backend.database import corpus_collection
    return corpus_collection


async def create_corpus(*, title: str = "", why: str = "", images: Sequence[Any] = (),
                        corpus_id: Optional[str] = None, now: Optional[str] = None,
                        collection=None) -> Dict[str, Any]:
    doc = new_corpus_doc(corpus_id=corpus_id or new_id(), title=title, why=why,
                         images=images, now=now)
    assert_no_percept_data(doc)
    await _collection(collection).insert_one(doc)
    return doc


async def get_corpus(corpus_id: str, *, collection=None) -> Optional[Dict[str, Any]]:
    return await _collection(collection).find_one({"_id": str(corpus_id)})


async def list_corpora(*, limit: int = 50, collection=None) -> List[Dict[str, Any]]:
    cursor = _collection(collection).find({}).sort("updated_at", -1).limit(limit)
    return [doc async for doc in cursor]


async def save_images(corpus_id: str, images: Sequence[Mapping[str, Any]], *,
                      now: Optional[str] = None, collection=None) -> Optional[Dict[str, Any]]:
    """Write a new membership/order for the walk. Whole-list, not a patch.

    A walk is one sequence. Patching it entry by entry would let a document end up holding half of
    one order and half of another, with positions computed from neither.
    """
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(corpus_id)})
    if doc is None:
        return None
    stamp = now or utc_now()
    cleaned = [dict(i) for i in images]
    for n, item in enumerate(cleaned):
        item["position"] = n
    updated = {**doc, "images": cleaned, "updated_at": stamp}
    assert_no_percept_data(updated)
    await coll.update_one({"_id": str(corpus_id)},
                          {"$set": {"images": cleaned, "updated_at": stamp}})
    return updated


async def save_meta(corpus_id: str, *, title: Optional[str] = None, why: Optional[str] = None,
                    now: Optional[str] = None, collection=None) -> Optional[Dict[str, Any]]:
    """Retitle, or restate what the walk is for. Membership and order are untouched."""
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(corpus_id)})
    if doc is None:
        return None
    stamp = now or utc_now()
    patch: Dict[str, Any] = {"updated_at": stamp}
    if title is not None:
        patch["title"] = str(title)
    if why is not None:
        patch["why"] = str(why)
    await coll.update_one({"_id": str(corpus_id)}, {"$set": patch})
    return {**doc, **patch}


async def delete_corpus(corpus_id: str, *, collection=None) -> bool:
    """Forget the walk. THE POSTS ARE NOT TOUCHED, and neither is any Atlas opened from it — an
    Atlas resolved its post ids when it was created and keeps them, so deleting a corpus can never
    empty a canvas somebody is still working on."""
    res = await _collection(collection).delete_one({"_id": str(corpus_id)})
    return bool(getattr(res, "deleted_count", 0))
