#!/usr/bin/env python3
"""
WAVE3 — do two senses' relations compose, or only coexist? The corpus, asked.

    python scripts/cross_modal_survey.py                  # 3 posts
    python scripts/cross_modal_survey.py --posts 6
    python scripts/cross_modal_survey.py --json

Grounds every measured occlusion relation and every measured chromatic rhyme over a post's masked
regions, then runs the EXISTING composition mechanism over every cross-modal pairing and reports the
distribution of verdicts.

WHAT WOULD MAKE THIS SCRIPT DISHONEST, and what it does instead:

  · reporting `coexistent` as "cross-modal relations do not fuse" — when `dialogue.compose` knows
    exactly ONE composition, so everything else is coexistent by construction. The verdicts say
    "no composition is known" rather than "no relationship exists", and this prints the size of
    the rule table next to the result.
  · reporting a null without showing the question was answerable. It prints how many pairs SHARE A
    SUBJECT: if that were zero, `coexistent` would be trivial rather than a finding.
  · a bounded scan claiming a corpus-wide result. The bound is printed.

READS POSTS AND IMAGES, WRITES NOTHING, MINTS NOTHING. Every mutating method on the post collection
is replaced with a raiser before the first query. No marks are proposed and no hypothesis is stored.

Needs the usual `.env`, network for the images, Pillow, and torch + transformers for the depth
field. On this Mac the depth model runs on MPS.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import chroma_organ as chroma                       # noqa: E402
from backend.services import chromatic_relation as rhyme                  # noqa: E402
from backend.services import cross_modal as cm                            # noqa: E402
from backend.services import depth_organ                                  # noqa: E402
from backend.services import occlusion_organ as occlusion                 # noqa: E402


class WriteAttempted(Exception):
    """A write was attempted against a collection this survey is only allowed to read."""


def freeze(*collections) -> None:
    def _blocked(*_a, **_k):
        raise WriteAttempted("this survey may not write — it asks a question, it proposes nothing")
    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many", "delete_one",
                       "delete_many", "replace_one", "bulk_write", "find_one_and_update"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                   # noqa: BLE001
                pass


async def relations_for(post, *, max_regions: int):
    """Every measured occlusion relation and chromatic rhyme over one post's masked regions."""
    from backend.routers.posts import _image_fetch_headers
    from backend.services import depth_service
    import httpx
    from PIL import Image

    url = str(post.get("photo_url") or "")
    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=_image_fetch_headers(url))
        resp.raise_for_status()
    image = Image.open(io.BytesIO(resp.content)).convert("RGB")

    frame = chroma.image_frame(image, source=url)
    field = depth_organ.depth_field(
        depth_service.estimate(image, grid=32), adapter=depth_organ.SOURCE_ADAPTER,
        model="depth_anything_v2_small", revision=depth_service.REVISION)

    regions = [r for r in (post.get("region_annotations") or []) if r.get("mask_rle")][:max_regions]
    out, counts = [], {"occlusion": 0, "rhyme": 0}
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            for kind, call in (("occlusion", lambda: occlusion.measure(regions[i], regions[j], field)),
                               ("rhyme", lambda: rhyme.measure(regions[i], frame, regions[j], frame))):
                try:
                    m = call()
                except Exception:                               # noqa: BLE001
                    continue
                # MEASURED ONLY. A box-basis reading is an estimate, and asking whether two
                # estimates compose would answer the lane's question with the wrong evidence.
                if m.get("basis") == "mask":
                    out.append(m)
                    counts[kind] += 1
    return out, counts, len(regions)


def report(scanned, relations, counts, survey):
    print("\n" + "=" * 78)
    print("  WAVE3 — cross-modal composition: the corpus, asked")
    print("=" * 78)
    print(f"\nSCANNED (the bound): {scanned} post(s), {counts['regions']} masked regions")
    print(f"   measured occlusion relations : {counts['occlusion']}")
    print(f"   measured chromatic rhymes    : {counts['rhyme']}")
    print(f"   total measured relations     : {len(relations)}")

    print(f"\n1. WAS THE QUESTION ANSWERABLE? — pairs where a depth relation and a chroma relation")
    print(f"   are about THE SAME two regions: {survey['same_subject']}")
    if not survey["same_subject"]:
        print("   ZERO. `coexistent` below would be trivial rather than a finding — the two senses")
        print("   never got a shared subject to compose over. Report it as that, not as a result.")
    else:
        print("   So the question is real: these are pairs where both senses have something to say")
        print("   about one thing, which is the precondition composition needs.")

    print(f"\n2. THE VERDICTS over {survey['cross_modal_attempts']} cross-modal attempts")
    for outcome, n in sorted(survey["outcomes"].items(), key=lambda kv: -kv[1]):
        print(f"   {outcome:<20} {n:>7}")
    print(f"   pairings: {survey['pairings']}")

    print(f"\n3. COMPOSITIONS: {survey['composed']}")
    print(f"   known composition rules in the whole system: {len(cm.KNOWN_COMPOSITIONS)}"
          f"  ({', '.join(c[2] for c in cm.KNOWN_COMPOSITIONS)})")
    if survey["composed"] == 0:
        print("   ZERO — and the honest reading of that zero is printed rather than assumed:")
        print("   every known composition is WITHIN-sense, so a cross-modal zero is what the rule")
        print("   table already implied. What the corpus adds is that the pairs EXIST and still")
        print("   nothing joins them. The structural reason is in `cross_modal`'s docstring:")
        print("   nestedness and adjacency compose because they are partial views of ONE aspect;")
        print("   depth-order and chromatic correspondence are complete answers to DIFFERENT")
        print("   questions about the same pair, so together they are a conjunction.")

    if survey["examples"]:
        e = survey["examples"][0]
        print(f"\n4. ONE SHARED-SUBJECT PAIR, in full")
        print(f"   senses  : {e['senses']}")
        print(f"   subject : {e['subject']}")
        print(f"   outcome : {e['outcome']}")
        print(f"   refusal if asked for a number:")
        print(f"     {e.get('refusal_if_asked_for_a_number', '')[:150]}…")
    print()


async def main_async(args) -> int:
    from backend.database import post_collection

    freeze(post_collection)
    relations, counts = [], {"occlusion": 0, "rhyme": 0, "regions": 0}
    scanned = 0
    async for post in post_collection.find(
            {"photo_url": {"$exists": True, "$ne": ""},
             "region_annotations.3": {"$exists": True}}).limit(args.posts):
        try:
            rels, c, n = await relations_for(post, max_regions=args.max_regions)
        except Exception as exc:                                # noqa: BLE001
            print(f"  skip {post['_id']}: {exc}", file=sys.stderr)
            continue
        scanned += 1
        relations.extend(rels)
        counts["occlusion"] += c["occlusion"]
        counts["rhyme"] += c["rhyme"]
        counts["regions"] += n
        print(f"  {post['_id']}: {n} regions -> {c['occlusion']} occlusion, {c['rhyme']} rhyme",
              file=sys.stderr)

    if not relations:
        print("✗ no measured relations were grounded — nothing to survey", file=sys.stderr)
        return 2

    survey = cm.survey(relations)
    if args.json:
        print(json.dumps({"scanned_posts": scanned, "counts": counts, **survey}, indent=2))
    else:
        report(scanned, relations, counts, survey)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--posts", type=int, default=3)
    ap.add_argument("--max-regions", type=int, default=14,
                    help="regions per post; the relation grounding is quadratic in this")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
