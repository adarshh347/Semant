"""
Create / drop throwaway clones of real posts, so UI verification never writes to the
curator's own images.

A clone copies the photo, the regions and the reading from a source post, and is
marked by `photo_public_id` so `drop` can never delete anything else.

    python scripts/ui_fixture_post.py make <source_post_id> [<source_post_id> ...]
    python scripts/ui_fixture_post.py make <src> <src> <src> --marks 1,1,0
    python scripts/ui_fixture_post.py drop

`make` prints one clone id per line, in the order given — a corpus is a SEQUENCE, and a
multi-image surface (the Atlas, the Light Table) has to be verified over one that holds its
order. Every `make` starts from a clean slate: existing fixtures are dropped first, so the
marker never accumulates strays across sessions.

`--marks` gives each clone synthetic COMMITTED `visual_marks` (default: one each). It exists for
C3: `compare_views` requires two images that each carry a committed mark, and a corpus of clones
with regions but no marks can only ever refuse. The per-clone form — `--marks 1,1,0` — is what
lets one Atlas hold both a pair that can ground a comparison and an image that cannot, so a proof
can show a real relation and an honest refusal side by side. A refusal is a real case worth
proving, which is why `--marks 0` is supported rather than treated as a mistake.

The marks are SYNTHETIC and are never copied from the source: a real curator's marks are exactly
what this script exists to keep out of reach.

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


def _marks_for(spec, clone_index: int) -> int:
    """How many marks clone `i` gets. An int applies to every clone; a list is per clone, and runs
    out to zero rather than wrapping — `--marks 1,1,0` must not silently give a fourth clone a mark
    nobody asked for."""
    if isinstance(spec, int):
        return max(0, spec)
    return max(0, spec[clone_index]) if clone_index < len(spec) else 0


def _clone_of(src: dict, *, marks: int = 0, index: int = 0) -> dict:
    return {
        "visual_marks": [_mark(index, m) for m in range(marks)],
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


async def make(source_ids: list, marks=1) -> None:
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
    for i, src in enumerate(sources):
        res = await post_collection.insert_one(
            _clone_of(src, marks=_marks_for(marks, i), index=i))
        print(str(res.inserted_id))


async def drop(quiet: bool = False) -> None:
    r = await post_collection.delete_many({"photo_public_id": MARKER})
    if not quiet:
        print(f"dropped {r.deleted_count}")


async def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "make":
        args = sys.argv[2:]
        marks = 1
        if "--marks" in args:
            at = args.index("--marks")
            raw = args[at + 1] if at + 1 < len(args) else "1"
            marks = [int(x) for x in raw.split(",")] if "," in raw else int(raw)
            args = args[:at]
        if not args:
            raise SystemExit(__doc__)
        await make(args, marks)
    elif sys.argv[1] == "drop":
        await drop()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
