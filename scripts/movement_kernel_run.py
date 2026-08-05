#!/usr/bin/env python3
"""
WAVE2 Lane M — run the movement kernel on the real corpus.

    python scripts/movement_kernel_run.py                       # dry run, writes nothing
    python scripts/movement_kernel_run.py --persist             # write the axis + edges
    python scripts/movement_kernel_run.py --seed-post <id> --seed-label finial
    python scripts/movement_kernel_run.py --third-post <id>
    python scripts/movement_kernel_run.py --json                # the raw transcript

The experiment: take a nesting MEASURED in one image, carry it to another, record the crossing as
an edge along the nestedness axis, and then place a third image nobody compared — by measuring it,
not by scoring it.

READS POSTS, WRITES NONE. Every post document is hashed before and after and the run fails if a
byte moved. With `--persist` it writes the axis (`movement_axes`) and the edges (`atlases`) through
Lane G, and creates the Atlas if it does not exist. The grounding marks are PROPOSED and printed;
committing one to a post is a curator's act and this script performs none.

Needs the usual `.env` (MONGO_DETAILS) and a built retina index (`scripts/retina_build.py`).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import movement_kernel as mk                        # noqa: E402
from backend.services import nestedness_organ as organ                    # noqa: E402
from backend.services import structure_map as sm                          # noqa: E402

#: The default cast, chosen because it is the hardest honest version of the experiment available
#: in this corpus: A and B are both architecture (a fair crossing), and C is a carved face — a
#: different subject entirely, so a placement there cannot be riding on appearance.
DEFAULT_SEED_POST = "6a5fef58a3ddb6341fd69930"    # temple: golden finial in temple spire
DEFAULT_THIRD_POST = "6a60400c1ecd6db1c931eb64"   # sculpted face: features within a crown
DEFAULT_ATLAS_ID = "atlas_wave2_lane_m"


async def load_posts() -> dict:
    from backend.database import post_collection
    posts = {}
    async for post in post_collection.find({"region_annotations.0": {"$exists": True}}):
        posts[str(post["_id"])] = post
    return posts


def find_region(post: dict, needle: str) -> str:
    """A region id by label substring — for CHOOSING WHAT TO POINT AT, never for a decision.

    The kernel's gates never read a label; this is the human picking a subject, which is the one
    place a word is allowed to matter.
    """
    if not needle:
        return ""
    for region in post.get("region_annotations") or []:
        if needle.lower() in str(region.get("label") or "").lower():
            return str(region.get("id"))
    return ""


async def ensure_atlas(atlas_id: str, post_ids) -> str:
    from backend.services import atlas_service
    doc = await atlas_service.get_atlas(atlas_id)
    if doc is None:
        await atlas_service.create_atlas(
            corpus_ref={"kind": "manual", "post_ids": list(post_ids)},
            post_ids=list(post_ids), title="WAVE2 Lane M — the movement kernel",
            atlas_id=atlas_id)
    return atlas_id


def _print(transcript: dict) -> None:
    seeded = transcript["seed"]
    print("\n" + "=" * 78)
    print("  WAVE2 Lane M — the movement kernel")
    print("=" * 78)

    print(f"\n1. SEED — the organ measures image A")
    print(f"   post      {seeded['post_id']}")
    print(f"   relation  {seeded['labels']['part']!r} nested within {seeded['labels']['whole']!r}")
    m = seeded["measurement"]
    print(f"   measured  {m['detail']}  [basis={m['basis']}]")
    st = seeded["structure"]
    print(f"   skeleton  depth={st['depth']} siblings={st['sibling_count']} "
          f"descendants={st['descendant_count']}")
    print(f"   NOTE      the mark cites {m['outer_region_id']}, the skeleton's parent is "
          f"{st['parent_id']} — {'AGREE' if m['outer_region_id'] == st['parent_id'] else 'DISAGREE'}")

    retina = transcript["retina"]
    print(f"\n2. PROPOSE — the retina (similarity, NOT relations)")
    print(f"   status    {retina['status']}   candidates={len(retina['candidates'])}"
          f"   skipped={len(retina.get('skipped_candidates') or [])}")

    print(f"\n3+4. MAP, then GROUND — structure-mapping, then the organ on image B")
    for c in transcript["considered"]:
        cand = c["candidate"]
        tag = "GROUND" if c["status"] == "grounded" else f"refuse"
        reason = c.get("reason") or ""
        print(f"   [{tag:>6}] {str(cand['post_id'])[-6:]}/{str(cand['region_id']):<12}"
              f" retina={cand.get('score'):<7} {str(c['labels'].get('part'))[:24]:<24} {reason}")
    print(f"   → grounded={len([c for c in transcript['considered'] if c['status']=='grounded'])}"
          f"  surface-only refusals={len(transcript['surface_only_refusals'])}")

    print(f"\n5. THE EDGE — Lane G stores it; the status is DERIVED from the mark")
    for mv in transcript["movements"]:
        e = mv["edge"]
        print(f"   {e['edge_id']}  axis={e['axis_ref']}")
        print(f"     {e['source_node']}  →  {e['target_node']}")
        print(f"     systematicity={e['systematicity']}  weight={e['weight']}  "
              f"spans={e['spans']}")
        print(f"     carries epistemic_status? {'epistemic_status' in e}   "
              f"carries provenance? {'provenance' in e}")
    for both in transcript["hydrated"]:
        a, b = both["as_stored"], both["with_proposed_marks"]
        print(f"   hydrated as stored          live={a['live']} epistemic={a['epistemic']!r}")
        print(f"   hydrated + proposed marks   live={b['live']} epistemic={b['epistemic']!r}")
    persisted = transcript.get("persisted") or {}
    if persisted.get("axis"):
        print(f"   persisted axis={persisted['axis']['axis_id']}")
        for row in persisted["edges"]:
            print(f"     written={row['written']} stored_edge_id={row.get('stored_edge_id')}")
            for drop in row.get("discarded") or []:
                print(f"       DISCARDED BY write_edge: {drop['field']} "
                      f"minted={drop['minted']!r} -> stored={drop['stored']!r}")

    placement = transcript.get("placement")
    if placement:
        print(f"\n6. THE THIRD IMAGE — never compared to either")
        print(f"   post      {placement['post_id']}")
        print(f"   axis says {placement['axis']['status']}"
              f"   ({placement['axis'].get('detail', '')[:60]})")
        print(f"   retina    {(placement['retina'] or {}).get('status')}")
        sm_v = placement.get("structure_map") or {}
        print(f"   maps      {sm_v.get('status')}"
              f"  systematicity={(sm_v.get('systematicity') or {}).get('score')}")
        print(f"   PLACED    {placement['placed']}   by={placement['placed_by']}")
        if placement["placed"]:
            print(f"     {placement['labels'].get('part')!r} within "
                  f"{placement['labels'].get('whole')!r}")
            print(f"     {placement['detail']}  [basis={placement['basis']}]")

    print(f"\n   proposed marks (NOT committed): {len(transcript['proposed_marks'])}")
    for mark in transcript["proposed_marks"]:
        print(f"     {mark['id']}  {mark['epistemic_status']}  post={mark['post_id']}"
              f"  producer={mark['provenance']['producer']}")
    print(f"\n   posts unchanged: {transcript['posts_unchanged']}")
    print()


async def main_async(args) -> int:
    posts = await load_posts()
    print(f"loaded {len(posts)} posts carrying regions")

    post_a = posts.get(args.seed_post)
    if post_a is None:
        print(f"✗ seed post {args.seed_post} not found (or carries no regions)", file=sys.stderr)
        return 2
    third = posts.get(args.third_post) if args.third_post else None

    seed_region = find_region(post_a, args.seed_label) if args.seed_label else ""
    if args.seed_label and not seed_region:
        print(f"✗ no region matching {args.seed_label!r} in {args.seed_post}", file=sys.stderr)
        return 2

    atlas_id = ""
    if args.persist:
        span = {args.seed_post, *(p for p in posts)}
        atlas_id = await ensure_atlas(args.atlas_id, sorted(span))

    try:
        transcript = await mk.run_kernel(
            post_a=post_a, posts=posts, third_post=third,
            region_id=seed_region, third_region_id=args.third_label and
            find_region(third or {}, args.third_label) or "",
            k=args.k, max_movements=args.max_movements,
            atlas_id=atlas_id, persist=bool(args.persist),
            min_systematicity=args.min_systematicity)
    except organ.NestednessRefusal as e:
        print(f"✗ the kernel could not seed: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(transcript, indent=2, default=str))
    else:
        _print(transcript)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed-post", default=DEFAULT_SEED_POST)
    ap.add_argument("--seed-label", default="finial",
                    help="pick the seed region by label substring (choosing the subject, "
                         "never a gate)")
    ap.add_argument("--third-post", default=DEFAULT_THIRD_POST)
    ap.add_argument("--third-label", default="")
    ap.add_argument("--atlas-id", default=DEFAULT_ATLAS_ID)
    ap.add_argument("-k", type=int, default=mk.DEFAULT_K)
    ap.add_argument("--max-movements", type=int, default=1)
    ap.add_argument("--min-systematicity", type=float, default=sm.MIN_SYSTEMATICITY)
    ap.add_argument("--persist", action="store_true",
                    help="write the axis and edges through Lane G (never a post)")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
