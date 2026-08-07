#!/usr/bin/env python3
"""
WAVE3 — the first non-geometric sense, against the real corpus.

    python scripts/chroma_agent_run.py                      # dry run, writes nothing
    python scripts/chroma_agent_run.py --post <id>
    python scripts/chroma_agent_run.py --locus-region <id>  # stand somewhere exactly
    python scripts/chroma_agent_run.py --json               # the raw transcript

Two agents inhabit ONE locus. One carries geometry (`nestedness_organ`); the other carries
`chroma_organ`, which reads the light. The dialogue lane already showed two GEOMETRIC bodies
differing; this shows the first pair whose fields have no term in common at all — and then declines
to compare them, which is the honest end of this lane rather than a missing feature.

WHAT THIS RUN DEMONSTRATES

  · a warmth field measured on a MASK, `measured`, and the same region read on its BOUNDING BOX,
    `interpretive` — the TWO-STATUS-001 contract exercised by the first organ built on it
  · a `measured` claim about a box reading, REFUSED by the guard
  · the naming ("warm"/"cool") as a SEPARATE producer, rejectable without touching the field
  · the two agents' percept fields side by side, with the shared vocabulary counted (it is nearly
    empty, and that is the finding)
  · `compare_across_senses` raising, because there is no scale on which a warmth mean and a
    nesting index compare and this lane does not invent one

READS POSTS, WRITES NONE — and not on the honour system. Every mutating method on the post
collection is replaced with a raiser before the first query, so a write is physically impossible
rather than merely unintended; the posts are hashed before and after on top of that. The grounding
marks are PROPOSED and printed; committing one is a curator's act and this script performs none.

THE PIXELS ARE FETCHED HERE, never by the organ. `chroma_organ` takes an image it is handed and
opens nothing — an organ that fetched a URL could reach something the caller did not choose, and a
cached `photo_url` is exactly the goes-stale problem `atlas_service` warns about. This script is
the caller, so this script does the fetching, over the same headers `routers/posts.py` uses.

Needs the usual `.env` (MONGO_DETAILS), network for the image, and Pillow. No GPU, no model.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import chroma_organ as chroma                       # noqa: E402
from backend.services import epistemics                                   # noqa: E402
from backend.services import nestedness_organ as nestedness               # noqa: E402
from backend.services.agents import observation as obs_mod                # noqa: E402
from backend.services.agents import organs                                # noqa: E402
from backend.services.agents import situated_agent as sa                  # noqa: E402
from backend.services.epistemics import STATUS_KEY                        # noqa: E402

GEO, CHR = "geo", "chr"


class WriteAttempted(Exception):
    """A write was attempted against a collection this run is only allowed to read."""


def freeze(*collections) -> None:
    """Make writing physically impossible, rather than merely unintended.

    The pattern from `vision_f0_audit`, `situated_agent_run` and `agent_dialogue_run`. A new SENSE
    is the place it matters most: nothing else in the system can read a warmth field, so a wrong
    one committed to a post would have no second opinion available anywhere.
    """
    def _blocked(*_a, **_k):
        raise WriteAttempted(
            "this run may not write to posts — an organ proposes, and committing is a curator's act")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                   # noqa: BLE001
                pass


def _posts():
    from backend.database import post_collection
    freeze(post_collection)
    return post_collection


async def load_post(post_id: str) -> dict:
    from bson import ObjectId
    query = {"_id": ObjectId(post_id)} if ObjectId.is_valid(post_id) else {"_id": post_id}
    return await _posts().find_one(query) or {}


async def any_post_with_a_photo() -> dict:
    return await _posts().find_one(
        {"photo_url": {"$exists": True, "$ne": ""}, "region_annotations.1": {"$exists": True}}) or {}


async def fetch_image(photo_url: str):
    """The pixels. Fetched HERE — see the module note — and handed to the organ as an object."""
    import httpx
    from PIL import Image
    import io

    from backend.routers.posts import _image_fetch_headers

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
        resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def _label(post: dict, region_id: str) -> str:
    for region in post.get("region_annotations") or []:
        if str(region.get("id")) == str(region_id):
            return str(region.get("label") or region.get("category") or region_id)
    return region_id


def pick_locus(post: dict) -> str:
    """A masked region big enough for both organs to say something about.

    Masked, because under WAVE2.5 a box basis makes BOTH readings estimates and the run would then
    demonstrate the contract's weak half twice. Big enough, because `chroma_organ` refuses a region
    that lands on too few sampled pixels — which is a refusal, not a grey field.
    """
    best, best_area = "", 0
    for region in post.get("region_annotations") or []:
        rle = region.get("mask_rle")
        if not rle:
            continue
        try:
            from backend.services import mask_geometry as mg
            area = mg.rle_area(rle)
        except Exception:                                       # noqa: BLE001
            continue
        if area > best_area:
            best, best_area = str(region.get("id")), area
    return best


def _print(t: dict, post: dict) -> None:
    print("\n" + "=" * 78)
    print("  WAVE3 — the first non-geometric sense")
    print("=" * 78)

    locus = t["locus"]
    print(f"\n1. ONE LOCUS, TWO KINDS OF BODY")
    print(f"   post      {locus['post_id']}")
    print(f"   locus     {locus['region_id']}  ({_label(post, locus['region_id'])!r})")
    for aid, organ_set in t["bodies"].items():
        print(f"   {aid:<5}     {', '.join(organ_set)}")

    print("\n2. TWO FIELDS — and they share almost no vocabulary")
    for aid, rows in t["fields"].items():
        print(f"   {aid} measured {len(rows)}:")
        for row in rows:
            other = f" {_label(post, row['other_region_id'])!r}" if row["other_region_id"] else ""
            print(f"      {row['relation']:>14}{other:<24} {row['epistemic_status']:<13} "
                  f"{row['detail'][:88]}")
        if not rows:
            print("      (nothing — a fact about this locus, not a failure to look)")
    print(f"   relations in common:        {t['shared']['relations'] or '—'}")
    print(f"   measurement keys in common: {t['shared']['measurement_keys']}")
    print("   ↑ everything they share is bookkeeping. The dialogue lane's two agents disagreed")
    print("     ABOUT something; these two are not looking at the same kind of thing at all.")

    c = t["chroma"]
    print("\n3. THE SUBSTRATE CONTRACT (TWO-STATUS-001), on the first organ built for it")
    print(f"   on the MASK   warmth {c['mask']['warmth_mean']:+.4f}  chroma "
          f"{c['mask']['chroma_mean']:.4f}  → {c['mask']['status']}")
    print(f"                 {c['mask']['gradient']}")
    print(f"   on the BOX    warmth {c['box']['warmth_mean']:+.4f}  chroma "
          f"{c['box']['chroma_mean']:.4f}  → {c['box']['status']}")
    print(f"   the two differ by {c['delta']:.4f} on the warm/cool axis — a bounding box around a")
    print("   part contains whatever is behind it, so the box reading can be a number about a")
    print("   different subject. That is `interpretive` doing the work it was widened to do.")
    print(f"   the SAME box reading claiming `measured` → {c['refused']}")

    n = t["naming"]
    print("\n4. THE NAMING IS A SECOND PRODUCER")
    print(f"   producer  {n['producer']}   status {n[STATUS_KEY]}")
    print(f"   {n['detail']}")
    print("   reject the word and the field is untouched: the number was measured, the threshold")
    print("   is a convention, and nothing in the picture votes on where warm begins.")

    print("\n5. COMMENSURABILITY — named, reachable, refused")
    print(f"   compare_across_senses(nesting, warmth) → {t['incommensurable'][:150]}…")
    print("   this lane does not invent a common scalar. Two senses coexist at this locus")
    print("   WITHOUT a forced comparison, and relating them is a later lane's whole subject.")

    print(f"\n   proposed marks (NOT committed): {len(t['proposed_marks'])}")
    for mark in t["proposed_marks"]:
        print(f"     {mark['id']}  {mark[STATUS_KEY]:<13} producer={mark['provenance']['producer']}")
    print(f"\n   posts unchanged: {t['posts_unchanged']}")
    print()


async def main_async(args) -> int:
    post = await load_post(args.post) if args.post else await any_post_with_a_photo()
    if not post:
        print(f"✗ no post {args.post or 'with a photo and regions'} found", file=sys.stderr)
        return 2

    post_id = str(post["_id"])
    photo_url = str(post.get("photo_url") or "")
    if not photo_url:
        print(f"✗ post {post_id} has no photo_url — there are no pixels to read, and this organ "
              f"refuses rather than reporting a grey field", file=sys.stderr)
        return 2

    region_id = str(args.locus_region or "") or pick_locus(post)
    if not region_id:
        print("✗ no masked region on this post. A box basis would make BOTH readings estimates "
              "and the run would demonstrate the contract's weak half twice.", file=sys.stderr)
        return 2

    print(f"post {post_id} — {len(post.get('region_annotations') or [])} regions", file=sys.stderr)
    print(f"fetching {photo_url[:90]}…", file=sys.stderr)
    try:
        image = await fetch_image(photo_url)
    except Exception as e:                                      # noqa: BLE001
        print(f"✗ could not fetch the image: {e}", file=sys.stderr)
        return 2
    print(f"image {image.size[0]}×{image.size[1]}", file=sys.stderr)

    frame = chroma.image_frame(image, source=photo_url, whole_frame=True)
    before = sa.posts_fingerprint({post_id: post})

    geo = sa.inhabit(agent_id=GEO, post_id=post_id, region_id=region_id,
                     organ_set=(nestedness.ORGAN,))
    chr_ = sa.inhabit(agent_id=CHR, post_id=post_id, region_id=region_id,
                      organ_set=(chroma.ORGAN,))
    try:
        sa.perceive(geo, post, image=None)
        sa.perceive(chr_, post, image=frame)
    except organs.OrganRefusal as e:
        print(f"✗ an agent could not perceive: {e}", file=sys.stderr)
        return 1
    except chroma.ChromaRefusal as e:
        print(f"✗ the chroma organ refused: {e}", file=sys.stderr)
        return 1

    transcript: dict = {
        "locus": geo.locus.as_dict(),
        "bodies": {geo.id: list(geo.organ_set), chr_.id: list(chr_.organ_set)},
        "fields": {a.id: [p.as_dict() for p in a.percept_field] for a in (geo, chr_)},
    }

    geo_keys = set(geo.percept_field[0].reading.measurement) if geo.percept_field else set()
    chr_keys = set(chr_.percept_field[0].reading.measurement) if chr_.percept_field else set()
    transcript["shared"] = {
        "relations": sorted({p.reading.relation for p in geo.percept_field} &
                            {p.reading.relation for p in chr_.percept_field}),
        "measurement_keys": sorted(geo_keys & chr_keys),
    }

    # The same region read both ways, so the contract is a number rather than a claim.
    region = next(r for r in post["region_annotations"] if str(r.get("id")) == region_id)
    # THIS script fetched the pixels, so THIS script is what can honestly say they are the whole
    # frame and where they came from. The organ refuses a bare image (ORGAN-PROVENANCE-001).
    frame = chroma.image_frame(image, source=photo_url, whole_frame=True)
    by_mask = chroma.measure(region, frame)
    by_box = chroma.measure({"id": region_id, "box": nestedness._box_of(region)}, frame)
    boxed_mark = chroma.grounding_mark(by_box, post_id=post_id)
    try:
        epistemics.guard([{**boxed_mark, STATUS_KEY: "measured"}])
        refused = "NOT REFUSED  <-- BUG"
    except epistemics.EpistemicViolation as e:
        refused = f"REFUSED — {str(e)[:100]}…"

    transcript["chroma"] = {
        "mask": {"warmth_mean": by_mask["warmth_mean"], "chroma_mean": by_mask["chroma_mean"],
                 "status": chroma.epistemic_for(by_mask["basis"]),
                 "gradient": by_mask["gradient"]["detail"]},
        "box": {"warmth_mean": by_box["warmth_mean"], "chroma_mean": by_box["chroma_mean"],
                "status": chroma.epistemic_for(by_box["basis"])},
        "delta": abs(by_mask["warmth_mean"] - by_box["warmth_mean"]),
        "refused": refused,
    }
    transcript["naming"] = chroma.name_of(by_mask)

    try:
        chroma.compare_across_senses(
            geo.percept_field[0].reading.measurement if geo.percept_field else {}, by_mask)
        transcript["incommensurable"] = "NOT REFUSED  <-- BUG"
    except chroma.Incommensurable as e:
        transcript["incommensurable"] = str(e)

    transcript["proposed_marks"] = [*sa.proposed_marks(geo), *sa.proposed_marks(chr_)]
    sa.assert_posts_unchanged(before, sa.posts_fingerprint({post_id: post}))
    transcript["posts_unchanged"] = True

    if args.json:
        print(json.dumps(transcript, indent=2, default=str))
    else:
        _print(transcript, post)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default="", help="a post id; omit to take any post with a photo")
    ap.add_argument("--locus-region", default="",
                    help="stand exactly here. Masked regions only produce a `measured` reading")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
