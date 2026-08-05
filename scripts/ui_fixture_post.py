"""
Create / drop throwaway clones of a real post, so UI verification never writes to the
curator's own images.

Each clone copies the photo, the regions and the reading from a source post, and is
marked by `photo_public_id` so `drop` can never delete anything else.

    python scripts/ui_fixture_post.py make <source_post_id>          # one clone, one mark
    python scripts/ui_fixture_post.py make <source_post_id> 3        # three clones, one mark each
    python scripts/ui_fixture_post.py make <source_post_id> 3 0      # three clones, NO marks
    python scripts/ui_fixture_post.py make <source_post_id> 3 1,1,0  # per clone: 1, 1, then none
    python scripts/ui_fixture_post.py drop

The per-clone form is what makes a MIXED corpus possible in one Atlas — two images that can ground
a comparison and a third that cannot — so a demo can show a real relation and an honest refusal
side by side without ever touching a real post.

WHY CLONES CARRY COMMITTED MARKS (ATLAS C3). `compare_views` requires two images that each carry a
committed mark, so a corpus of clones with regions but no marks can only ever produce a refusal.
That is a real and useful case — it is exactly the honest-refusal half of C3's demo — but proving
the GROUNDED half needs marks, and the rule is to extend this script rather than reach for a real
post that happens to have them. So `make` mints synthetic committed `trace_mark`s: one per clone by
default, `0` for a corpus that must refuse.

The marks are deliberately trivial (a two-point path across the frame) and are SYNTHETIC, never
copied from the source — a real curator's marks are precisely what this script exists to keep out
of reach. They exist so the gate has two things to relate.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson.objectid import ObjectId          # noqa: E402
from backend.database import post_collection  # noqa: E402

MARKER = "ui-fixture-visual-content"

# `trace_mark` roles from the frontend's own vocabulary (`perceptualActions.TRACE_ROLES`), so a
# fixture mark renders like any other rather than tripping the role validator.
_ROLES = ("architectural_axis", "gaze_address", "fall_of_light", "movement", "gesture")


def _mark(clone_index: int, mark_index: int) -> dict:
    """One committed trace mark. Synthetic, and honest about being so."""
    role = _ROLES[(clone_index + mark_index) % len(_ROLES)]
    mark_id = f"vm_fixture_{clone_index}_{mark_index}"
    # Offset per clone so two clones' marks are not identical lines — a comparison between two
    # copies of the same geometry would be a degenerate demo.
    y = 0.25 + 0.12 * ((clone_index + mark_index) % 4)
    return {
        "id": mark_id,
        "type": "trace_mark",
        "role": role,
        "label": f"fixture {role.replace('_', ' ')} {clone_index}",
        "source": "user_confirmed",
        "status": "committed",
        "source_ref": mark_id,
        "geometry": {"kind": "path", "points": [[0.15, round(y, 3)], [0.85, round(y + 0.1, 3)]]},
        "linked_ground_ids": [],
        "warnings": [],
    }


def _marks_for(spec, clone_index: int, count: int) -> int:
    """How many marks clone `i` gets. An int applies to every clone; a comma list is per clone,
    and runs out to zero rather than wrapping — "1,1,0" must not silently give the fourth clone a
    mark it was not asked for."""
    if isinstance(spec, int):
        return max(0, spec)
    return max(0, spec[clone_index]) if clone_index < len(spec) else 0


async def make(source_id: str, count: int = 1, marks_per_post=1) -> None:
    src = await post_collection.find_one({"_id": ObjectId(source_id)})
    if not src:
        raise SystemExit(f"source post {source_id} not found")
    await drop(quiet=True)
    for i in range(max(1, count)):
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
            "visual_marks": [_mark(i, m)
                              for m in range(_marks_for(marks_per_post, i, count))],
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
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        raw = sys.argv[4] if len(sys.argv) > 4 else "1"
        marks = [int(x) for x in raw.split(",")] if "," in raw else int(raw)
        await make(sys.argv[2], count, marks)
    elif sys.argv[1] == "drop":
        await drop()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
