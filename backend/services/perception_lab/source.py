"""
PERCEPTUAL-ORGANS-002 Lane F1 — what the laboratory is looking at, and the proof it did not move.

A picture enters the lab as a NORMAL `post_id`. There is no lab-only image table, no second upload
path and no copy: whatever a person selects or uploads becomes a post through the routes that
already exist, and the lab then reads it. That is not a convenience — it is what makes "the lab
changed nothing" a checkable claim about a document the rest of Semant also holds.

TWO HASHES, BECAUSE THERE ARE TWO THINGS THAT COULD MOVE.

    image_digest      `sha256:` of the actual bytes. It goes on `LabSource` and on every artifact's
                      provenance, so a measurement can always be traced to the pixels it was made
                      of, and a façade handed the wrong picture says so rather than measuring it.

    post_fingerprint  `sha256` of the whole post DOCUMENT — marks, regions, grounds, percepts, the
                      lot. Nothing in the lab may change it. It is re-read after every run and the
                      run FAILS if it differs, which is a comparison rather than a promise.

`movement_kernel.posts_fingerprint` computes the second, imported rather than rewritten: two
functions hashing "a post document" are two definitions of what counts as the document, and they
drift on the first field somebody adds.

WHAT THE PROBE IS FOR, AND WHY IT DOES NOT RE-HASH THE IMAGE. Lane D's `source_probe` answers "is
the source still what this session named?" while the run is finishing. Re-downloading the image to
re-hash it would measure the CDN, not the post; and re-hashing the bytes already in hand would be
this module asserting the picture did not move on no evidence at all. So the probe re-reads the
post document. Unchanged, and it returns the digest the session has — the source is still that
source. Changed, and it returns a marker naming the new fingerprint, which the conductor turns into
`source_mutated`, the run into `failed`, and the record into the reason.

READ-ONLY. There is no write to `post_collection` anywhere in this file, and nothing that imports
it has one either.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import unquote, urlparse

from backend.schemas.perception_lab import LabSource
from backend.services.movement_kernel import posts_fingerprint

#: How long a source label may be. Long enough to tell two sculptures apart, short enough that
#: a picker row stays a row.
TITLE_MAX = 90

#: How long the lab waits for a source image. Generous: this is a person pressing "open" on one
#: picture, not a batch, and a timeout here reads to them as "the laboratory is broken".
FETCH_TIMEOUT_SECONDS = 30.0


class SourceUnavailable(RuntimeError):
    """The picture this session would be about cannot be read.

    Not a refusal. A refusal is what the laboratory says about a request it will not perform; this
    is a source that is not there, and there is no session to open on it.
    """


class UnknownPost(LookupError):
    """No such post. Its own type so a route maps it to 404 without matching on a string."""


def image_digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def fingerprint_of(post: Mapping[str, Any]) -> str:
    """The whole post document as one hash, through the kernel's own definition of one."""
    return posts_fingerprint({"post": dict(post)})["post"]


def natural_size(data: bytes) -> Tuple[int, int]:
    """The image's own pixel dimensions, decoded rather than declared.

    A drawn polygon becomes a mask on THIS raster, and every normalized box in the lab is a
    fraction of it. Taking the numbers from a post field that nothing maintains would put a guessed
    raster under a measurement, which `extent.draw` already refuses to do — so they are read from
    the bytes, once, when the session opens.
    """
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
    except Exception as exc:                               # noqa: BLE001 - any decoder failure
        raise SourceUnavailable(
            f"the source image could not be decoded, so the lab has no raster to measure on: "
            f"{exc}") from exc
    if not width or not height:
        raise SourceUnavailable("the source image decoded to a zero-sized raster")
    return int(width), int(height)


def lab_regions(post: Mapping[str, Any]) -> Tuple[Dict[str, Any], ...]:
    """The post's canonical regions, DEEP-COPIED on the way out.

    `mask_geometry.canonicalize_geometry` mutates in place and bumps `geometry_rev`, and
    `extent.reuse` exists precisely to work on these. Handing out the post's own dicts would put a
    corpus-revising call one careless line away; handing out copies means the worst a façade can do
    is revise something nobody will ever read again.
    """
    out: List[Dict[str, Any]] = []
    for raw in (post.get("region_annotations") or []):
        if isinstance(raw, Mapping) and raw.get("id"):
            out.append(_deep(dict(raw)))
    return tuple(out)


def _deep(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep(v) for v in value]
    return value


@dataclass(frozen=True)
class SourceSnapshot:
    """One picture, as the lab holds it for the length of one request.

    `post` is the document as it was READ, kept so the after-hash compares like with like. Nothing
    in the lab writes it back.
    """
    post_id: str
    post: Mapping[str, Any]
    fingerprint: str
    photo_url: str
    image_bytes: bytes
    source: LabSource
    regions: Tuple[Mapping[str, Any], ...]

    @property
    def digest(self) -> str:
        return self.source.image_digest

    def as_client_source(self) -> Dict[str, Any]:
        """The shape Lane E's client interface documents for a Source."""
        return {"id": self.post_id, "post_id": self.post_id, "origin": "post",
                "title": _title(self.post), "photo_url": self.photo_url,
                "image_digest": self.source.image_digest,
                "natural_width": self.source.natural_width,
                "natural_height": self.source.natural_height,
                "region_count": len(self.regions)}


def _title(post: Mapping[str, Any]) -> Optional[str]:
    """A short label a person can tell one picture from another by.

    A TITLE IS NOT A URL, and this is what the F3 rehearsal ran into: most of the corpus has no
    text block, so the fallback returned `source_url` — and a Google image-search URL is four
    hundred characters of base64 that filled the picker and pushed every image off the page. The
    laboratory was unusable for the one job it opens with, choosing a source.

    So the URL is reduced to what a person actually reads in it — the host, and the file if there
    is one — and everything is bounded. A source with no text and no usable URL comes back `None`,
    and the picker says "untitled" rather than being handed something to render badly.
    """
    for block in (post.get("text_blocks") or []):
        text = str((block or {}).get("content") or "").strip() if isinstance(block, Mapping) else ""
        # HTML is what the editor stores; a title made of `<p><span class=…>` is no more readable
        # than a URL. Tags out, whitespace collapsed, and only then is it a label.
        text = re.sub(r"<[^>]+>", " ", text)
        text = " ".join(text.split())
        if text:
            return text[:TITLE_MAX]

    raw = str(post.get("source_url") or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    host = (parsed.hostname or "").removeprefix("www.")
    leaf = (parsed.path or "").rstrip("/").rsplit("/", 1)[-1]
    # A Cloudinary or CDN leaf is a uuid and tells a person nothing; a Wikipedia one is the
    # article. Keep the leaf only when it reads like words rather than like an identifier.
    stem = leaf.rsplit(".", 1)[0] if "." in leaf else leaf
    if leaf and len(leaf) <= 60 and not re.fullmatch(r"[0-9a-f-]{16,}", stem):
        label = f"{host} · {unquote(leaf).replace('_', ' ')}"
    else:
        label = host or None
    return label[:TITLE_MAX] if label else None


def snapshot_from(post: Mapping[str, Any], image_bytes: bytes) -> SourceSnapshot:
    """A post document plus its bytes → everything one sitting needs. Pure: no I/O.

    Split from the fetching so the suite can build a snapshot from a fixture post and a real PNG
    and exercise the entire vertical without a network — which is also what makes "the lab never
    writes to the post" testable at all.
    """
    post_id = str(post.get("_id") or post.get("id") or "")
    if not post_id:
        raise UnknownPost("a lab source needs a post id")
    photo_url = str(post.get("photo_url") or "")
    width, height = natural_size(image_bytes)
    return SourceSnapshot(
        post_id=post_id, post=dict(post), fingerprint=fingerprint_of(post), photo_url=photo_url,
        image_bytes=image_bytes,
        source=LabSource(origin="post", post_id=post_id, image_digest=image_digest(image_bytes),
                         natural_width=width, natural_height=height),
        regions=lab_regions(post))


# ── reading the corpus ───────────────────────────────────────────────────────


def _object_id(post_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId
    try:
        return ObjectId(post_id)
    except (InvalidId, TypeError) as exc:
        raise UnknownPost(f"{post_id!r} is not a post id") from exc


async def read_post(post_id: str, *, collection=None) -> Mapping[str, Any]:
    if collection is None:
        from backend.database import post_collection as collection
    post = await collection.find_one({"_id": _object_id(post_id)})
    if not post:
        raise UnknownPost(post_id)
    return post


async def fetch_image(photo_url: str, *, fetch=None) -> bytes:
    """The bytes behind a post's `photo_url`, with the repository's own hotlink headers.

    `_image_fetch_headers` is imported from `routers.posts` rather than restated: the Referer rules
    it encodes were learned from CDNs rejecting this repository specifically, and a second copy
    would be a second thing to fix the next time one of them changes.
    """
    if not photo_url:
        raise SourceUnavailable("this post has no image")
    if fetch is not None:
        return await fetch(photo_url)
    import httpx
    from backend.routers.posts import _image_fetch_headers
    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True) as c:
            response = await c.get(photo_url, headers=_image_fetch_headers(photo_url))
            response.raise_for_status()
            return response.content
    except Exception as exc:                               # noqa: BLE001 - any transport failure
        raise SourceUnavailable(f"the source image could not be fetched: {exc}") from exc


async def open_source(post_id: str, *, collection=None, fetch=None) -> SourceSnapshot:
    """A post id → the picture, its digest, its raster and its regions. The one way in."""
    post = await read_post(post_id, collection=collection)
    data = await fetch_image(str(post.get("photo_url") or ""), fetch=fetch)
    return snapshot_from(post, data)


async def list_sources(*, limit: int = 30, collection=None) -> List[Dict[str, Any]]:
    """The newest posts, as things a lab session could be opened on.

    NO DIGEST HERE, and `image_digest: null` says so rather than omitting the key. Computing one
    would mean downloading thirty images to draw a list; the digest is what `open_source` produces
    when a person actually chooses one, and a listing that carried a stale or guessed digest would
    be worse than one that admits it has not looked.
    """
    if collection is None:
        from backend.database import post_collection as collection
    cursor = collection.find({"photo_url": {"$ne": None}}).sort("_id", -1).limit(int(limit))
    out: List[Dict[str, Any]] = []
    async for post in cursor:
        out.append({"id": str(post["_id"]), "post_id": str(post["_id"]), "origin": "post",
                    "title": _title(post), "photo_url": post.get("photo_url"),
                    "image_digest": None, "natural_width": None, "natural_height": None,
                    "region_count": len(post.get("region_annotations") or [])})
    return out


# ── the probe the conductor holds ────────────────────────────────────────────

#: What the probe returns when the post moved. Not a digest and not shaped like one — a value that
#: could be mistaken for a digest is a value that could be compared equal to one by accident.
MUTATED = "post-mutated"


def mutation_probe(snapshot: SourceSnapshot, *, collection=None):
    """A callable for `PerceptionConductor.source_probe`. Synchronous, because the conductor is.

    Returns the session's own image digest while the post document is byte-identical to the one the
    session opened on, and `post-mutated:<new fingerprint>` the moment it is not. The conductor
    compares that against `session.source.image_digest`, refuses `source_mutated`, and ends the run
    `failed` — which is the correct outcome for a measurement of an image that moved: not partly
    right, not a refusal, no claim at all.

    A post that has been DELETED under a running session is also a mutation. Reporting it as
    "unchanged" because there is nothing to compare would be the one reading that lets a run pass.
    """
    def probe() -> str:
        if collection is not None:
            found = collection.find_one({"_id": snapshot.post["_id"]})
        else:
            from backend.database import sync_database
            found = sync_database().get_collection("posts").find_one(
                {"_id": snapshot.post["_id"]})
        if not found:
            return f"{MUTATED}:absent"
        current = fingerprint_of(found)
        if current == snapshot.fingerprint:
            return snapshot.source.image_digest
        return f"{MUTATED}:{current[:16]}"
    return probe


__all__ = ["FETCH_TIMEOUT_SECONDS", "MUTATED", "SourceUnavailable", "UnknownPost", "SourceSnapshot",
           "image_digest", "fingerprint_of", "natural_size", "lab_regions", "snapshot_from",
           "read_post", "fetch_image", "open_source", "list_sources", "mutation_probe"]
