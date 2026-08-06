#!/usr/bin/env python3
"""
WAVE3 — the before/after this lane exists to produce.

    python scripts/retina_density_proof.py              # both runs, the delta, the concrete pair
    python scripts/retina_density_proof.py --json        # the raw record
    python scripts/retina_density_proof.py -k 48         # widen the mask-seeded proposal

## What is being proved

#143 left the movement kernel in a state where it grounded NOTHING through the retina — not because
the mechanism was broken but because the two ends had drifted apart:

    the retina could propose only VLM boxes     (the only rows the index had)
    the kernel could ground only on masks       (the WAVE2.5 ruling)

Every proposal was therefore inadmissible by construction. `retina_density.py` closed that by
embedding the 365 masked regions the index was missing. This script measures whether it worked, and
it does so by RUNNING THE KERNEL, not by inspecting the index.

Two runs, deliberately:

  · **the box seed** (`fine_0`, k=12) — the exact shape of #143's run. It must STILL ground nothing.
    Density does not repeal the ruling: a box-basis seed is an estimate on the near side, so no
    amount of retrieval can make the crossing measured. If this run ever grounds, the ruling leaks.
  · **the mask seed** (`cseg_golden_finial_5`) — the run that was not previously possible. Every
    `cseg_*` region had zero embeddings before this lane, so the retina could not return one, so a
    mask-vs-mask crossing could not be proposed at all, let alone grounded.

## What it does not prove

That the groundings are *correct*. It proves they are MEASURED — mask on both endpoints, the organ
consulted, systematicity above the floor. Whether a golden finial nested in a temple spire is a
useful thing to say about a marble wall panel is a curator's question, and this script commits
nothing: `persist=False` throughout, posts hashed before and after.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import mask_geometry as mg                          # noqa: E402
from backend.services import movement_kernel as mk                        # noqa: E402
from backend.services import structure_map as sm                          # noqa: E402

#: The cast #143 ran, kept verbatim so the two numbers are comparable.
SEED_POST = "6a5fef58a3ddb6341fd69930"      # temple: a golden finial in a temple spire

#: The VLM box #143 could seed on — `find_region('finial')` resolves to this, because every
#: `cseg_*` region carries an EMPTY label and so cannot be picked by word at all.
BOX_SEED = "fine_0"

#: Its masked twin. Same subject, measured geometry.
MASK_SEED = "cseg_golden_finial_5"

#: #143's measured result, for the row above the line. Not recomputed here — it cannot be: the
#: index it ran against no longer exists.
#: `surface_only` was 0 there and the three classes account for all 12 candidates, which is how
#: you can tell the run was retrieval-starved rather than structurally empty.
BEFORE = {"grounded": 0, "box_only": 7, "insystematic": 5, "surface_only": 0, "candidates": 12,
          "mask_carrying_candidates": 0, "source": "PR #143, box seed, k=12"}


async def load_posts() -> dict:
    from backend.database import post_collection
    posts = {}
    async for post in post_collection.find({"region_annotations.0": {"$exists": True}}):
        posts[str(post["_id"])] = post
    return posts


def _masked_ids(post) -> set:
    return {str(r.get("id")) for r in (post.get("region_annotations") or [])
            if mg.rle_is_valid(r.get("mask_rle"))}


def tally(transcript: dict, posts: dict) -> dict:
    """The four numbers the card asks for, plus what the retina actually offered."""
    considered = transcript["considered"]
    reasons = Counter(c.get("reason") or "" for c in considered if c["status"] != "grounded")
    candidates = transcript["retina"].get("candidates") or []
    mask_carrying = sum(
        1 for c in candidates
        if str(c.get("region_id")) in _masked_ids(posts.get(str(c.get("post_id"))) or {}))
    return {
        "candidates": len(candidates),
        "mask_carrying_candidates": mask_carrying,
        "grounded": sum(1 for c in considered if c["status"] == "grounded"),
        "box_only": reasons.get(mk.REFUSED_BOX_ONLY, 0),
        "insystematic": reasons.get("insystematic", 0),
        "surface_only": reasons.get(sm.REFUSED_SURFACE_ONLY, 0),
        "other_refusals": {k: v for k, v in reasons.items()
                           if k not in (mk.REFUSED_BOX_ONLY, "insystematic",
                                        sm.REFUSED_SURFACE_ONLY)},
    }


async def run(posts: dict, region_id: str, k: int) -> dict:
    started = time.perf_counter()
    transcript = await mk.run_kernel(
        post_a=posts[SEED_POST], posts=posts, third_post=None,
        region_id=region_id, k=k, max_movements=1, atlas_id="", persist=False)
    counts = tally(transcript, posts)
    seed = transcript["seed"]
    return {
        "region_id": region_id,
        "k": k,
        "seconds": round(time.perf_counter() - started, 1),
        "seed_basis": seed["measurement"]["basis"],
        "seed_detail": seed["measurement"]["detail"],
        "seed_admissible": seed["measurement"].get("admissible"),
        "counts": counts,
        "posts_unchanged": transcript["posts_unchanged"],
        "grounded": [
            {"post_id": str(c["candidate"]["post_id"]),
             "region_id": str(c["candidate"]["region_id"]),
             "retina_score": c["candidate"].get("score"),
             "basis": (c.get("measurement") or {}).get("basis"),
             "detail": c.get("detail"),
             "systematicity": ((c.get("structure_map") or {}).get("systematicity") or {}).get(
                 "score"),
             "epistemic_status": (c.get("mark") or {}).get("epistemic_status")}
            for c in transcript["considered"] if c["status"] == "grounded"],
    }


async def retrievability() -> dict:
    """The one index fact worth stating: `cseg_*` regions are now reachable at all."""
    from backend.database import region_embeddings_collection
    identity = await region_embeddings_collection.count_documents({"role": "identity"})
    cseg = await region_embeddings_collection.count_documents(
        {"role": "identity", "region_id": {"$regex": "^cseg_"}})
    return {"identity_rows": identity, "cseg_identity_rows": cseg}


def _line(label: str, c: dict) -> str:
    return (f"   {label:<26} grounded={c['grounded']:<4} box_only={c['box_only']:<4} "
            f"insystematic={c['insystematic']:<4} surface_only={c['surface_only']:<4} "
            f"(masks {c['mask_carrying_candidates']}/{c['candidates']} proposed)")


def report(rows: dict) -> None:
    box, mask, index = rows["box_seed"], rows["mask_seed"], rows["index"]

    print("\n" + "=" * 92)
    print("  WAVE3 — retina density: the before/after")
    print("=" * 92)

    print(f"\nTHE INDEX")
    print(f"   identity rows {index['identity_rows']}, of which {index['cseg_identity_rows']} are "
          f"cseg_* (masked)")
    print(f"   before this lane: 140 identity rows, 0 of them cseg_* — no masked region was "
          f"retrievable at all")

    print(f"\nTHE DELTA")
    print(_line(f"BEFORE  {BOX_SEED} k=12", BEFORE) + f"   [{BEFORE['source']}]")
    print(_line(f"AFTER   {BOX_SEED} k={box['k']}", box["counts"]))
    print(_line(f"AFTER   {MASK_SEED[:22]} k={mask['k']}", mask["counts"]))

    print(f"\n   the box seed still grounds nothing, and that is the ruling working, not a "
          f"failure:")
    print(f"     seed basis={box['seed_basis']} admissible={box['seed_admissible']} — "
          f"{box['seed_detail']}")
    print(f"   the mask seed grounds because the near side is measured geometry:")
    print(f"     seed basis={mask['seed_basis']} admissible={mask['seed_admissible']} — "
          f"{mask['seed_detail']}")

    if mask["grounded"]:
        g = mask["grounded"][0]
        print(f"\nONE CONCRETE PAIR — proposed and grounded, neither possible before")
        print(f"   {SEED_POST}/{MASK_SEED}")
        print(f"     →  {g['post_id']}/{g['region_id']}")
        print(f"   retina score  {g['retina_score']}   (a candidate — NOT a relation)")
        print(f"   organ         {g['detail']}  [basis={g['basis']}]")
        print(f"   systematicity {g['systematicity']}  (floor {sm.MIN_SYSTEMATICITY})")
        print(f"   mark          {g['epistemic_status']}")
        print(f"   the target region is cseg_* — it had NO embedding before this lane, so the "
              f"140-row")
        print(f"   index could not return it, and a crossing to it could not be proposed.")
        if len(mask["grounded"]) > 1:
            print(f"\n   {len(mask['grounded']) - 1} further mask-vs-mask groundings in the same "
                  f"run:")
            for g in mask["grounded"][1:6]:
                print(f"     {str(g['post_id'])[-6:]}/{g['region_id']:<28} "
                      f"sys={g['systematicity']:<9} {g['detail']}")
    else:
        print(f"\n✗ no grounding on the mask seed — the lane has not cleared its gate.")

    print(f"\n   posts unchanged: box_seed={box['posts_unchanged']} "
          f"mask_seed={mask['posts_unchanged']}")
    print(f"   nothing persisted: no axis, no edge, no mark committed. Suggestions only.\n")


async def main_async(args) -> int:
    posts = await load_posts()
    print(f"loaded {len(posts)} posts carrying regions")
    rows = {
        "index": await retrievability(),
        "box_seed": await run(posts, BOX_SEED, 12),
        "mask_seed": await run(posts, MASK_SEED, args.k),
    }
    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        report(rows)

    ok = (rows["mask_seed"]["counts"]["grounded"] > 0
          and rows["box_seed"]["counts"]["grounded"] == 0
          and rows["box_seed"]["posts_unchanged"] and rows["mask_seed"]["posts_unchanged"])
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", type=int, default=48, help="candidates for the mask-seeded run")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
