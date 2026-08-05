"""
Create / drop a throwaway manuscript, so Writer verification never touches a real work.

The data-safety analogue of `ui_fixture_post.py`. There are no "real posts" in the Writer
half; the thing that must never be harmed is a manuscript the author cares about. So the
live proof runs ONLY against a manuscript this script made, and `drop` is keyed on a
marker it also wrote — it can never delete anything else, including a manuscript that
merely looks like a fixture.

`drop` clears four things, because a fixture that leaves its ontology behind would let the
next proof run pass on stale operators:
  the manuscript + its scenes/versions, the project's operators, its quarantined
  passages, and its usage events.

    python scripts/writer_fixture_manuscript.py make    # prints "<manuscript_id> <scene_id>"
    python scripts/writer_fixture_manuscript.py drop
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import (                                    # noqa: E402
    manuscript_collection,
    scene_collection,
    scene_version_collection,
    writer_operator_collection,
    writer_passage_collection,
    writer_usage_collection,
)
from backend.services.manuscript_service import manuscript_service  # noqa: E402

#: The only thing `drop` will ever match on.
MARKER = "writer-w1-fixture-manuscript"


async def make() -> None:
    await drop(quiet=True)
    ms = await manuscript_service.create_manuscript(
        "W1 fixture manuscript", synopsis="A scratch manuscript for the W1 live proof."
    )
    # Stamp it before anything else can run against it.
    await manuscript_collection.update_one({"_id": ms["id"]}, {"$set": {"fixture_marker": MARKER}})
    ms = await manuscript_service.add_chapter(ms["id"], "Chapter one")
    chapter_id = ms["chapters"][0]["id"]
    scene = await manuscript_service.add_scene(ms["id"], chapter_id, "Scene one")
    print(f"{ms['id']} {scene['id']}")


async def drop(quiet: bool = False) -> None:
    ids = [doc["_id"] async for doc in manuscript_collection.find({"fixture_marker": MARKER})]
    if not ids:
        if not quiet:
            print("dropped 0 manuscripts")
        return
    await scene_collection.delete_many({"manuscript_id": {"$in": ids}})
    await scene_version_collection.delete_many({"manuscript_id": {"$in": ids}})
    await manuscript_collection.delete_many({"fixture_marker": MARKER})
    # The project id IS the manuscript id in W1 — see schemas/writer.py.
    for pid in ids:
        await writer_operator_collection.delete_many({"project_id": pid})
        await writer_passage_collection.delete_many({"project_id": pid})
        await writer_usage_collection.delete_many({"project_id": pid})
    if not quiet:
        print(f"dropped {len(ids)} manuscript(s) and their operators/passages/usage")


async def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("make", "drop"):
        raise SystemExit(__doc__)
    await (make() if sys.argv[1] == "make" else drop())


if __name__ == "__main__":
    asyncio.run(main())
