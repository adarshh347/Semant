"""
WAVE2.5 — give the nested corpus measured masks, so the nestedness organ stops grounding on boxes.

    python scripts/nested_corpus_masks.py                    # dry run: measure, write nothing
    python scripts/nested_corpus_masks.py --persist          # append the measured regions
    python scripts/nested_corpus_masks.py --post <id>        # one post
    python scripts/nested_corpus_masks.py --json             # the raw record

## Why this is a data lane and not a code lane

`nestedness_organ.measure` ALREADY prefers a per-pixel mask intersection, already falls back to
boxes, and already records `basis: "mask" | "box"` with a `basis_detail` saying the fallback
over-estimates. The ring-shaped container is already a passing regression test (mask 0.0 vs box
1.0). Nothing in the grounding path needed building.

What was missing is masks. Measured before this ran: **59 of 144 regions** across the 20
region-carrying posts had a `mask_rle`, and the two posts the movement kernel seeds and places on
had **0 of 14** and **1 of 18**. So every real measurement took the box path — which is why a
golden finial in front of the sky scored 0.992 "nested in Sky". A box cannot tell *inside* from
*in front of*; the sky's box contains everything under it.

## Why it ADDS regions instead of attaching masks to existing ones

The first version of this script tried to attach each measured mask to the VLM region carrying the
same label. It does not work, and the reason is worth recording rather than tuning around.

Those regions are `fine_N` boxes the VLM **estimated**. SAM 3 returns a **measurement**. For the
finial: the estimate is `x 0.47–0.53, y 0.02–0.06`, the measurement `x 0.461–0.477, y 0.032–0.089`
at confidence 0.851 — plausibly the same finial, overlapping about 20%. Matching by IoU attached
3 of 14; by containment, 2 of 14. Every threshold that raises the count also raises the chance of
welding a mask onto the wrong region — and a wrong mask is worse than no mask, because the organ
then measures it on the mask basis and reports it as the STRONGER evidence.

So no identity is asserted at all. SAM 3's instances are appended as their own **proposed**
regions, through the existing `instances_to_regions`, each carrying its own measured mask and an
EMPTY label — the concept belongs on the naming descriptor, never on the measured region. The
VLM's own regions are left untouched, byte for byte. Nothing here decides that a `cseg` region and
a `fine_N` region are the same thing; that is a curator's call, and this script does not make it.

## Concept source

The vocabulary is the labels the VLM already wrote on THIS image's regions. SF-004-R2 measured why:
a fixed vocabulary scored 6/18 because it asked a neck close-up for `cuff` and `placket`, while
the VLM's own per-image labels scored 27/35. The concepts have to come from something that has
looked at this picture.

## Honesty

The MASK is measured; the concept that prompted it stays interpretive and stays off the region.
Every appended region is `proposed: True` — nothing is committed, and a curator accepting one is a
separate act this script does not perform. Existing regions are compared before and after and the
run fails if any of them moved.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))

#: Region ids this script appends all start here (`instances_to_regions`' default prefix), which is
#: what makes a re-run idempotent: a concept whose regions are already present is not re-segmented.
CSEG_PREFIX = "cseg"


def regions_fingerprint(regions: List[Dict[str, Any]]) -> str:
    """A hash of the regions this script did NOT write, so their immobility is checkable."""
    keep = [r for r in regions if not str(r.get("id") or "").startswith(CSEG_PREFIX + "_")]
    return hashlib.sha256(
        json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:16]


async def load_posts(only: str = "") -> Dict[str, Dict[str, Any]]:
    from backend.database import post_collection
    query: Dict[str, Any] = {"region_annotations.0": {"$exists": True}}
    if only:
        from bson.objectid import ObjectId
        try:
            query["_id"] = ObjectId(only)
        except Exception:
            query["_id"] = only
    return {str(p["_id"]): p async for p in post_collection.find(query)}


def concepts_of(post: Dict[str, Any]) -> List[str]:
    """The VLM's own labels on this image, deduplicated, in the order they appear."""
    seen, out = set(), []
    for region in post.get("region_annotations") or []:
        if not isinstance(region, dict):
            continue
        if str(region.get("id") or "").startswith(CSEG_PREFIX + "_"):
            continue                            # never re-ask for a concept this script produced
        label = str(region.get("label") or "").strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            out.append(label)
    return out


async def measure_post(post: Dict[str, Any], *, svc, posts_router) -> Dict[str, Any]:
    """Segment every concept this image names. Returns a record; writes nothing."""
    post_id = str(post["_id"])
    regions = [r for r in (post.get("region_annotations") or []) if isinstance(r, dict)]
    existing = {str(r.get("id") or "") for r in regions}
    concepts = concepts_of(post)
    record: Dict[str, Any] = {
        "post_id": post_id, "regions": len(regions),
        "already_masked": sum(1 for r in regions if r.get("mask_rle")),
        "concepts": len(concepts), "measured": 0, "instances": 0,
        "refused": [], "new_regions": [],
    }
    if not concepts:
        return record

    try:
        image = await posts_router._fetch_post_image(post)
    except Exception as exc:                       # noqa: BLE001 — an unreadable image is a finding
        record["refused"].append({"reason": "image_unreadable", "detail": repr(exc)})
        return record

    for concept in concepts:
        try:
            result = await asyncio.to_thread(svc.segment_concept, image, concept)
        except Exception as exc:                   # noqa: BLE001 — degrade, never fail the sweep
            record["refused"].append({"concept": concept, "reason": "organ_raised",
                                      "detail": repr(exc)})
            continue

        if not (result.get("instances") or []):
            # "That concept is not in this picture" is an answer, not a failure.
            record["refused"].append({"concept": concept, "reason": "no_instance_measured"})
            continue

        minted = svc.instances_to_regions(result)
        fresh = [r for r in minted if str(r.get("id")) not in existing]
        if not fresh:
            record["refused"].append({"concept": concept, "reason": "already_present"})
            continue

        record["measured"] += 1
        record["instances"] += len(fresh)
        record["new_regions"].extend(fresh)
        existing.update(str(r.get("id")) for r in fresh)
    return record


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persist", action="store_true",
                    help="append the measured regions; without it nothing is written")
    ap.add_argument("--post", default="", help="one post id")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from backend.services import sam3_concept_service as svc
    from backend.routers import posts as posts_router

    if not svc.is_available():
        print("SAM 3 is unavailable — set SAM3_WEIGHTS to the checkpoint on disk.\n"
              "Nothing was measured and nothing was written.")
        return 2

    posts = await load_posts(args.post)
    print(f"loaded {len(posts)} posts carrying regions   (device={svc.device()})")

    before = {pid: regions_fingerprint(p.get("region_annotations") or [])
              for pid, p in posts.items()}
    records = []
    for pid, post in posts.items():
        record = await measure_post(post, svc=svc, posts_router=posts_router)
        records.append(record)
        if record["concepts"]:
            print(f"  {pid}  regions={record['regions']:>3}  masked={record['already_masked']:>3}"
                  f"  concepts={record['concepts']:>3}  measured={record['measured']:>3}"
                  f"  new_masked_regions={record['instances']:>4}"
                  f"  refused={len(record['refused']):>3}")

    total_new = sum(r["instances"] for r in records)
    total_refused = sum(len(r["refused"]) for r in records)
    print(f"\nmeasured {total_new} masked regions across "
          f"{sum(1 for r in records if r['instances'])} post(s); refused {total_refused} concept(s)")

    if not args.persist:
        print("DRY RUN — nothing written. Re-run with --persist to append them.")
        if args.json:
            print(json.dumps([{k: v for k, v in r.items() if k != "new_regions"}
                              for r in records], indent=2, default=str))
        return 0

    from backend.database import post_collection
    from bson.objectid import ObjectId

    written = 0
    for record in records:
        if not record["new_regions"]:
            continue
        post = posts[record["post_id"]]
        # APPEND. The existing list is carried through untouched and the new regions go on the
        # end — `$push`-shaped semantics through a `$set` of the one field, so no other field of
        # the post can be disturbed by this write.
        post["region_annotations"] = [*(post.get("region_annotations") or []),
                                      *record["new_regions"]]
        try:
            query: Dict[str, Any] = {"_id": ObjectId(record["post_id"])}
        except Exception:
            query = {"_id": record["post_id"]}
        await post_collection.update_one(
            query, {"$set": {"region_annotations": post["region_annotations"]}})
        written += 1
        print(f"  appended {len(record['new_regions'])} masked regions to {record['post_id']}")

    # The claim that matters: nothing that was already there moved.
    after = await load_posts(args.post)
    moved = [pid for pid, p in after.items()
             if regions_fingerprint(p.get("region_annotations") or []) != before.get(pid)]
    if moved:
        print(f"REFUSED TO CLAIM SUCCESS: pre-existing regions changed on {moved}")
        return 1
    print(f"\nappended to {written} post(s); every pre-existing region is byte-identical")
    if args.json:
        print(json.dumps([{k: v for k, v in r.items() if k != "new_regions"}
                          for r in records], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
