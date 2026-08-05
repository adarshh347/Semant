"""
Create / drop throwaway clones of real posts, so UI verification never writes to the
curator's own images.

A clone copies the photo, the regions and the reading from a source post, and is
marked by `photo_public_id` so `drop` can never delete anything else.

    python scripts/ui_fixture_post.py make <source_post_id> [<source_post_id> ...]
    python scripts/ui_fixture_post.py drop

`make` prints one clone id per line, in the order given — a corpus is a SEQUENCE, and a
multi-image surface (the Atlas, the Light Table) has to be verified over one that holds its
order. Every `make` starts from a clean slate: existing fixtures are dropped first, so the
marker never accumulates strays across sessions.

WHY THIS EXISTS AT ALL. Producers write straight through to `post_collection` — `dissect`'s
write is `{"$set": {"region_annotations": ...}}`, a wholesale REPLACE — and there is no trash,
no soft delete, and no per-post history to restore from. A live proof run against a real post
has already destroyed committed evidence that could not be recovered. So: proofs run here, and
when a proof needs something this script does not yet make, EXTEND THIS SCRIPT rather than
reaching for a real post.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson.objectid import ObjectId          # noqa: E402
from backend.database import post_collection  # noqa: E402

MARKER = "ui-fixture-visual-content"


def _clone_of(src: dict) -> dict:
    return {
        "photo_url": src["photo_url"],
        "photo_public_id": MARKER,
        "text_blocks": [],
        "general_tags": [],
        "highlights": [],
        # Deep-copied: the clone must never share region dicts with the source.
        "region_annotations": [dict(r) for r in (src.get("region_annotations") or [])],
        "local_context": dict(src.get("local_context") or {}),
        "domain": dict(src.get("domain") or {}),
    }
    # A clone with the source's handle would feed the source's persona on save.


async def make(source_ids: list) -> None:
    """Clone each source, in order, printing one new id per line.

    Every source is READ and validated before anything is written: a batch that would half-build
    a corpus is worse than one that refuses, because the proof would then run over a partial
    sequence and its order — which is evidence — would be wrong without saying so.
    """
    sources = []
    for source_id in source_ids:
        src = await post_collection.find_one({"_id": ObjectId(source_id)})
        if not src:
            raise SystemExit(f"source post {source_id} not found")
        if not src.get("photo_url"):
            raise SystemExit(f"source post {source_id} has no photo to clone")
        sources.append(src)

    await drop(quiet=True)
    for src in sources:
        res = await post_collection.insert_one(_clone_of(src))
        print(str(res.inserted_id))


async def drop(quiet: bool = False) -> None:
    r = await post_collection.delete_many({"photo_public_id": MARKER})
    if not quiet:
        print(f"dropped {r.deleted_count}")


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "make":
        if len(sys.argv) < 3:
            raise SystemExit(__doc__)
        await make(sys.argv[2:])
    elif sys.argv[1] == "drop":
        await drop()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
