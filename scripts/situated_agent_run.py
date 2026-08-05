#!/usr/bin/env python3
"""
WAVE3 — run the first situated agent against the real corpus.

    python scripts/situated_agent_run.py                          # dry run, writes nothing
    python scripts/situated_agent_run.py --locus-label finial     # choose where it stands
    python scripts/situated_agent_run.py --post <id>
    python scripts/situated_agent_run.py --persist                # write the observations
    python scripts/situated_agent_run.py --json                   # the raw transcript

One agent inhabits one locus in one image, perceives its field through a real organ, records what
it measured into its own episodic memory, and reports a partial view to the shared ledger.

READS POSTS, WRITES NONE — and not on the honour system. Every mutating method on the post
collection is replaced with a raiser before the first query, so a write is physically impossible
rather than merely unintended; the posts are hashed before and after on top of that. With
`--persist` it writes to `agent_observations` and to nothing else. The grounding marks are
PROPOSED and printed; committing one to a post is a curator's act and this script performs none.

Needs the usual `.env` (MONGO_DETAILS). No GPU, no model, no network beyond Mongo — the organ is
pure geometry.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import nestedness_organ as organ                    # noqa: E402
from backend.services.agents import observation as obs_mod                # noqa: E402
from backend.services.agents import organs                                # noqa: E402
from backend.services.agents import situated_agent as sa                  # noqa: E402

#: The same temple this corpus's movement kernel seeds from, so a reader can hold the two runs side
#: by side: the kernel CROSSES from this nesting to another image, and the agent STANDS in it.
DEFAULT_POST = "6a5fef58a3ddb6341fd69930"
DEFAULT_LOCUS_LABEL = "finial"
DEFAULT_ATLAS_ID = "atlas_wave3_situated_agent"


class WriteAttempted(Exception):
    """A write was attempted against a collection this run is only allowed to read."""


def freeze(*collections) -> None:
    """Make writing physically impossible, rather than merely unintended.

    The pattern from `scripts/vision_f0_audit.py`, kept because "this lane writes no posts" is the
    claim most worth making unfalsifiable — an agent that quietly committed its own marks would be
    granting itself the curator's act, which is the one thing the decision reserves.
    """
    def _blocked(*_a, **_k):
        raise WriteAttempted("this run may not write to posts — an agent proposes, it never commits")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                   # noqa: BLE001
                pass


async def load_post(post_id: str) -> dict:
    from backend.database import post_collection
    freeze(post_collection)
    from bson import ObjectId
    query = {"_id": ObjectId(post_id)} if ObjectId.is_valid(post_id) else {"_id": post_id}
    doc = await post_collection.find_one(query)
    return doc or {}


async def any_post_with_regions() -> dict:
    from backend.database import post_collection
    freeze(post_collection)
    return await post_collection.find_one({"region_annotations.2": {"$exists": True}}) or {}


def find_region(post: dict, needle: str) -> str:
    """A region id by label substring — for CHOOSING WHERE THE AGENT STANDS, never for a decision.

    The same allowance `movement_kernel_run.find_region` makes, and the same limit: no gate in the
    agent reads a label. Picking a subject is the one place a word is allowed to matter.
    """
    if not needle:
        return ""
    for region in post.get("region_annotations") or []:
        if needle.lower() in str(region.get("label") or "").lower():
            return str(region.get("id"))
    return ""


def _label(post: dict, region_id: str) -> str:
    for region in post.get("region_annotations") or []:
        if str(region.get("id")) == str(region_id):
            return str(region.get("label") or region.get("category") or region_id)
    return region_id


def _print(transcript: dict, post: dict) -> None:
    agent = transcript["agent"]
    print("\n" + "=" * 78)
    print("  WAVE3 — the first situated agent")
    print("=" * 78)

    print("\n1. INHABIT — a body, and a place to stand")
    print(f"   agent     {agent['id']}")
    print(f"   locus     {agent['node_id']}   ({_label(post, agent['locus']['region_id'])!r})")
    for binding in transcript["bindings"]:
        print(f"   organ     {binding['name']}  [{binding['resolution']}]")
        print(f"             {binding['detail'][:66]}")

    traj = transcript["trajectory"][-1]
    print("\n2. PERCEIVE — what these organs measure FROM HERE")
    print(f"   measured  {traj['measured']} of {traj['regions_in_reach']} regions in the image")
    for row in transcript["percept_field"]:
        other = _label(post, row["other_region_id"])
        arrow = "within" if row["direction"] == "within" else "contains"
        print(f"     {arrow:>8}  {other!r:<28} {row['epistemic_status']:<9} {row['detail']}")
    if not transcript["percept_field"]:
        print("     (nothing — the organs looked from here and measured nothing. That is a fact")
        print("      about this locus, not a failure to look.)")

    gods_eye = transcript.get("gods_eye") or {}
    if gods_eye:
        print("\n   PARTIALITY, MEASURED — the same organ, asked without a position")
        print(f"     the image contains  {gods_eye['total']} measurable nestings")
        print(f"     this agent holds    {gods_eye['agents']}  — every one with its locus as a term")
        print(f"     it cannot see       {gods_eye['unreachable']} nestings between regions it is "
              f"not standing on")
        for row in gods_eye["examples"]:
            print(f"       e.g. {row}")
        print("     that difference is not a gap to close. It is the engine: no agent has the")
        print("     whole, so meaning lives in the exchange between differently-situated views.")

    print("\n3. REMEMBER — episodic, first-person, PRIVATE")
    for row in transcript["memory"]:
        print(f"     {row['epistemic_status']:<9} {row['detail']}  [mark {row['mark_id']}]")
    print("     an agent lives on what its organs measured; it does not wait for a curator")
    print("     to believe its own eyes (DECISION-measured-private-vs-shared-ledger).")

    print("\n4. REPORT — the shared ledger, PROPOSED")
    for row in transcript["observations"]:
        print(f"     {row['observation_id']}  agent={row['agent_id']} from={row['node_id']}")
        print(f"       organ={row['organ']} relation={row['relation']}/{row['direction']} "
              f"source={row['source']}")
        print(f"       carries epistemic_status? {obs_mod.STATUS_KEY in row}   "
              f"cites mark {row['mark_id']}")
    for both in transcript["hydrated"]:
        a, b = both["as_stored"], both["with_proposed_marks"]
        print(f"     hydrated as stored          {a['ledger_status']:<10} live={a['live']}")
        print(f"     hydrated + proposed marks   {b['ledger_status']:<10} live={b['live']}")
    print("     the gap between those two readings is the curator's act this lane does not perform")

    persisted = (transcript.get("persisted") or {}).get("observations") or []
    if persisted:
        print(f"\n   persisted {len(persisted)} observation(s) to `agent_observations`")

    print(f"\n   proposed marks (NOT committed): {len(transcript['proposed_marks'])}")
    for mark in transcript["proposed_marks"]:
        print(f"     {mark['id']}  {mark['epistemic_status']}  post={mark['post_id']}"
              f"  producer={mark['provenance']['producer']}")
    print(f"\n   posts unchanged: {transcript['posts_unchanged']}")
    print()


async def main_async(args) -> int:
    post = await load_post(args.post) if args.post else await any_post_with_regions()
    if not post:
        print(f"✗ no post {args.post or 'with regions'} found", file=sys.stderr)
        return 2

    post_id = str(post["_id"])
    regions = post.get("region_annotations") or []
    print(f"post {post_id} — {len(regions)} regions")

    region_id = find_region(post, args.locus_label) if args.locus_label else ""
    if args.locus_label and not region_id:
        print(f"! no region matching {args.locus_label!r}; falling back to the first region",
              file=sys.stderr)
    region_id = region_id or (str(regions[0].get("id")) if regions else "")
    if not region_id:
        print("✗ this post has no regions — there is nowhere to stand", file=sys.stderr)
        return 2

    try:
        transcript = await sa.run_agent(
            post=post, region_id=region_id, agent_id=args.agent_id,
            organ_set=tuple(args.organ), temperament=args.temperament,
            atlas_id=args.atlas_id, persist=bool(args.persist))
    except organs.OrganRefusal as e:
        print(f"✗ the agent could not perceive: {e}", file=sys.stderr)
        return 1
    except sa.Hearsay as e:
        print(f"✗ refused as hearsay: {e}", file=sys.stderr)
        return 1

    transcript["gods_eye"] = _partiality(post, transcript)

    if args.json:
        print(json.dumps(transcript, indent=2, default=str))
    else:
        _print(transcript, post)
    return 0


def _partiality(post: dict, transcript: dict) -> dict:
    """The same organ, asked WITHOUT a position — and the difference, counted.

    `find_nested_pairs` sweeps the post n² and reports every nesting in the image. That is the
    reading the movement kernel needs and the one an agent must never have. Running both here is
    what turns "the agent's knowledge is partial" from a design intention into a number a reader
    can check: the image contains N, the agent holds M, and the M are exactly the ones with its
    locus as a term.

    Computed for the REPORT ONLY, after the run, and never handed to the agent. If this ever fed
    back into a percept field it would be the god's-eye read arriving through the back door.
    """
    regions = post.get("region_annotations") or []
    everything = organ.find_nested_pairs(regions)
    locus_id = transcript["agent"]["locus"]["region_id"]

    mine = {(row["locus_region_id"], row["other_region_id"])
            for row in transcript["percept_field"]}
    unreachable = [m for m in everything
                   if locus_id not in (m["inner_region_id"], m["outer_region_id"])]
    return {
        "total": len(everything),
        "agents": len(mine),
        "unreachable": len(unreachable),
        "examples": [f"{_label(post, m['inner_region_id'])!r} within "
                     f"{_label(post, m['outer_region_id'])!r}" for m in unreachable[:3]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default=DEFAULT_POST)
    ap.add_argument("--locus-label", default=DEFAULT_LOCUS_LABEL,
                    help="pick the locus region by label substring (choosing where the agent "
                         "stands, never a gate)")
    ap.add_argument("--agent-id", default="agent_alpha")
    ap.add_argument("--organ", action="append", default=[],
                    help=f"repeatable; defaults to {organ.ORGAN}")
    ap.add_argument("--temperament", default="")
    ap.add_argument("--atlas-id", default=DEFAULT_ATLAS_ID)
    ap.add_argument("--persist", action="store_true",
                    help="write the observations to `agent_observations` (never a post)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    args.organ = args.organ or [organ.ORGAN]
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
