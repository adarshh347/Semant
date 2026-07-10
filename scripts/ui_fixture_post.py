"""
Create / drop a throwaway clone of a real post, so UI verification never writes to the
curator's own images.

The clone copies the photo, the regions and the reading from a source post, and is
marked by `photo_public_id` so `drop` can never delete anything else.

    python scripts/ui_fixture_post.py make <source_post_id>   # prints the clone's id
    python scripts/ui_fixture_post.py drop
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson.objectid import ObjectId          # noqa: E402
from backend.database import post_collection  # noqa: E402

MARKER = "ui-fixture-visual-content"


async def make(source_id: str) -> None:
    src = await post_collection.find_one({"_id": ObjectId(source_id)})
    if not src:
        raise SystemExit(f"source post {source_id} not found")
    await drop(quiet=True)
    doc = {
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
    res = await post_collection.insert_one(doc)
    print(str(res.inserted_id))


async def drop(quiet: bool = False) -> None:
    r = await post_collection.delete_many({"photo_public_id": MARKER})
    if not quiet:
        print(f"dropped {r.deleted_count}")


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "make":
        await make(sys.argv[2])
    elif sys.argv[1] == "drop":
        await drop()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
