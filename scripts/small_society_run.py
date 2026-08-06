#!/usr/bin/env python3
"""
WAVE3 — three agents travel, meet, and one of them cannot compare notes.

    python scripts/small_society_run.py                        # the run, on the real corpus
    python scripts/small_society_run.py --rendezvous-node vm_<post>:<region>
    python scripts/small_society_run.py --rule strongest_combined
    python scripts/small_society_run.py --json

Three situated beings, three bodies, three starting images. Each walks one measured mask-basis
crossing to a node all three can reach; each perceives there holding nothing from where it came.
Then the society is read pairwise:

    α (containment)  ×  β (boundary contact)   →  composes: the locus is at R's RIM
    α                ×  γ (warmth)             →  incommensurable, and the refusal is #158's own
    β                ×  γ                      →  incommensurable

The heterogeneity is the point. Some pairs compose; some can only coexist; and the difference
between "we found nothing in common here" and "there is nothing we could have in common" is the
first structure in this project that belongs to a group rather than to a pair.

## Who does what

    the kernel    grounds crossings from each locus and mints edges   `movement_kernel`
    each agent    reads its OWN horizon, verifies it, and walks       `agents.movement`
    the observer  intersects THREE horizons and picks a meeting       `agents.society`
    the society   relates every pair and refuses what it must         `agents.society`

The meeting is arranged and the travel is earned — the same division move-and-meet named, and
three horizons agree on far less than two, which this run reports rather than asserts.

## Pixels

γ reads light, so it needs the image at both its start and the meeting locus. The pixels are
FETCHED HERE and handed to the organ (`chroma_agent_run` makes the same choice for the same
reason): an organ that opened a URL could reach something the caller did not choose.

READS POSTS, WRITES NONE — every mutating method on the post collection is replaced with a raiser
before the first query, and the posts are hashed before and after. Nothing is persisted.

Needs the usual `.env` (MONGO_DETAILS), a built retina index, and network for the two images.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import adjacency_organ as adj                      # noqa: E402
from backend.services import chroma_organ as chroma                      # noqa: E402
from backend.services import movement_kernel as mk                       # noqa: E402
from backend.services import nestedness_organ as nest                    # noqa: E402
from backend.services.agents import movement as mv                       # noqa: E402
from backend.services.agents import situated_agent as sa                 # noqa: E402
from backend.services.agents import society as soc                       # noqa: E402

#: Three masked loci in THREE DIFFERENT IMAGES, each with a measured crossing to a node in a
#: FOURTH image none of them starts in. Scouted rather than assumed, and each start was checked
#: for footing WITH ITS OWN ORGAN — a body cannot step from ground it never measured, and the
#: three bodies do not measure the same ground.
MEMBERS = (
    ("alpha", "695be6c9a9ea58f1b6aef5e0", "cseg_Amaravati_face_5", (nest.ORGAN,)),
    ("beta", "695be8baa9ea58f1b6aef609", "cseg_right_shoulder_3", (adj.ORGAN,)),
    ("gamma", "695be77ea9ea58f1b6aef5eb", "cseg_person_1", (chroma.ORGAN,)),
)


class WriteAttempted(Exception):
    """A write was attempted against a collection this run may only read."""


def freeze(*collections) -> None:
    def _blocked(*_a, **_k):
        raise WriteAttempted("this run may not write — agents propose; they never commit")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                            # noqa: BLE001
                pass


async def load_posts() -> dict:
    from backend.database import post_collection
    freeze(post_collection)
    return {str(p["_id"]): p async for p in post_collection.find(
        {"region_annotations.0": {"$exists": True}})}


async def fetch_image(photo_url: str):
    """The pixels, fetched here and handed in — never fetched by the organ."""
    import io

    import httpx
    from PIL import Image

    from backend.routers.posts import _image_fetch_headers

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
        resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


class Pixels:
    """Images by post id, fetched once each, and only for the posts that actually need them.

    A geometry agent is handed `None` and must be: an organ that quietly accepted an image it does
    not read would make the run's cost invisible and the dependency untraceable.
    """

    def __init__(self, posts: dict):
        self._posts = posts
        self._cache: dict = {}

    async def of(self, post_id: str):
        if post_id in self._cache:
            return self._cache[post_id]
        url = str((self._posts.get(post_id) or {}).get("photo_url") or "")
        image = await fetch_image(url) if url else None
        self._cache[post_id] = image
        return image


def _needs_pixels(agent) -> bool:
    return chroma.ORGAN in agent.organ_set


async def ground_from(agent, posts: dict, *, k: int, movements: int) -> dict:
    """The kernel's crossings from where this agent stands. The writer's half, played by the script.

    Note what this means for γ: **every movement edge in this corpus is grounded on nestedness**,
    so the chroma agent walks a road measured by an organ it does not have — and could not have,
    since a chromatic relation does not exist. Move-and-meet named this; it is sharper here,
    because γ cannot even read the relation its own road was grounded on. What γ verifies for
    itself is the ground it stands on (`movement.footing`, through its own organ), not the road.
    """
    try:
        transcript = await mk.run_kernel(
            post_a=posts[agent.locus.post_id], posts=posts, third_post=None,
            region_id=agent.locus.region_id, k=k, max_movements=movements,
            atlas_id="", persist=False)
    except nest.NestednessRefusal as exc:
        return {"edges": [], "marks": [], "refused": str(exc)}

    grounded = transcript.get("movements") or []
    return {
        "edges": [m["edge"] for m in grounded],
        "marks": [mk_ for m in grounded for mk_ in (m["near_mark"], m["far_mark"])],
        "refused": "",
        "candidates": len((transcript.get("retina") or {}).get("candidates") or []),
        "box_only": len(transcript.get("box_only_refusals") or []),
        "surface_only": len(transcript.get("surface_only_refusals") or []),
    }


async def run(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)
    pixels = Pixels(posts)
    record: dict = {"rule": args.rule, "rule_detail": soc.GROUP_RULES[args.rule],
                    "posts_loaded": len(posts), "starts": []}

    agents = []
    graph: dict = {"edges": []}
    held_marks: list = []
    for agent_id, post_id, region_id, organ_set in MEMBERS:
        if post_id not in posts:
            raise SystemExit(f"✗ no post {post_id} for {agent_id}")
        agent = sa.inhabit(agent_id=agent_id, post_id=post_id, region_id=region_id,
                           organ_set=organ_set)
        started = time.perf_counter()
        image = await pixels.of(post_id) if _needs_pixels(agent) else None
        field = sa.perceive(agent, posts[post_id], now=args.now, image=image)
        sa.remember(agent, now=args.now)
        stood = mv.footing(agent)
        grounding = await ground_from(agent, posts, k=args.k, movements=args.movements)
        graph = {"edges": [*graph["edges"], *grounding["edges"]]}
        held_marks = [*held_marks, *grounding["marks"]]
        agents.append(agent)
        record["starts"].append({
            "agent_id": agent.id, "organ_set": list(agent.organ_set),
            "node_id": agent.locus.node_id, "perceived": len(field),
            "footing": stood, "edges_added": len(grounding["edges"]),
            "kernel": {kk: vv for kk, vv in grounding.items() if kk not in ("edges", "marks")},
            "readings": [{"relation": p.reading.relation, "other": p.reading.other_region_id,
                          "basis": p.reading.basis, "epistemic_status": p.epistemic_status,
                          "expression": p.reading.expression, "detail": p.reading.detail}
                         for p in field[:4]],
            "seconds": round(time.perf_counter() - started, 1),
        })

    horizons = {a.id: mv.horizon(a, graph, posts, proposed_marks=held_marks) for a in agents}
    record["horizons"] = {aid: mv.horizon_tally(rows) for aid, rows in horizons.items()}

    options = sorted(soc.rendezvous_all(agents, horizons),
                     key=lambda r: (-r.weakest_leg, r.node_id))
    record["rendezvous"] = [r.as_dict() for r in options]
    # HOW THIN THE COMMON WORLD IS, reported rather than asserted. Move-and-meet predicted a
    # three-way intersection "gets emptier fast"; these are the two numbers that say by how much.
    record["pairwise_rendezvous"] = {
        f"{a.id}+{b.id}": len([r for r in horizons[a.id] if r.reachable and r.other_node in
                               {x.other_node for x in horizons[b.id] if x.reachable}])
        for i, a in enumerate(agents) for b in agents[i + 1:]}

    if args.rendezvous_node:
        chosen = next((r for r in options if r.node_id == args.rendezvous_node), None)
        record["chosen_by"] = "operator"
    else:
        chosen = soc.choose_group(options, rule=args.rule)
        record["chosen_by"] = f"rule:{args.rule}"

    if chosen is None:
        record["ended"] = ("the three horizons do not all overlap — there is no node every member "
                           "can reach on a measured crossing, which is a fact about how thin this "
                           "corpus's grounded graph is and not a failure of the meeting")
        mk.assert_posts_unchanged(before, mk.posts_fingerprint(posts))
        record["posts_unchanged"] = True
        return record

    record["chosen"] = chosen.as_dict()
    for agent in agents:
        mv.step(agent, chosen.legs[agent.id], now=args.now)
    record["on_arrival"] = {a.id: {"percept_field": len(a.percept_field),
                                   "horizon": len(a.horizon)} for a in agents}

    meeting_image = await pixels.of(chosen.post_id)
    for agent in agents:
        sa.perceive(agent, posts[chosen.post_id], now=args.now,
                    image=meeting_image if _needs_pixels(agent) else None)
        sa.remember(agent, now=args.now)

    society = soc.convene(agents, atlas_id=args.atlas_id, now=args.now)
    record["society"] = society.as_dict()
    record["held"] = soc.hold_all(society, now=args.now)
    record["hypotheses"] = society.hypotheses()

    # THE THREE-WAY OUTCOME: two composed it, and every non-contributor is asked.
    record["put_to"] = [
        soc.put_to(agent, hypothesis)
        for hypothesis in society.hypotheses()
        for agent in agents if agent.id not in [str(a) for a in hypothesis["agent_ids"]]
    ]

    mk.assert_posts_unchanged(before, mk.posts_fingerprint(posts))
    record["posts_unchanged"] = True
    return record


def _print(record: dict) -> None:
    print("\n" + "=" * 78)
    print("  WAVE3 — the first small society: three move, meet, and one cannot compare notes")
    print("=" * 78)
    print(f"\n  corpus  {record['posts_loaded']} posts carrying regions")
    print(f"  rule    {record['rule']} — {record['rule_detail']}")

    for start in record["starts"]:
        print("\n" + "-" * 78)
        print(f"  {start['agent_id'].upper()}  {start['node_id']}")
        print(f"    body        {', '.join(start['organ_set'])}")
        print(f"    perceived   {start['perceived']} reading(s), footing "
              f"{start['footing']['basis']} ({start['footing']['admissible_readings']} on masks)")
        for reading in start["readings"][:3]:
            print(f"      {reading['relation']:<14} {reading['epistemic_status']:<12} "
                  f"{reading['expression'][:52]}")
        kernel = start.get("kernel") or {}
        print(f"    kernel      {kernel.get('candidates')} candidate(s); grounded "
              f"{start['edges_added']}; box_only={kernel.get('box_only')} "
              f"surface_only={kernel.get('surface_only')}")

    print("\n" + "-" * 78)
    print("  HORIZONS — each agent's own reachable world")
    for agent_id, tally in record["horizons"].items():
        print(f"    {agent_id:<8} visible {tally['visible']}, REACHABLE {tally['reachable']}")
    print("\n  WHERE THE COMMON WORLD THINS")
    for pair, count in record["pairwise_rendezvous"].items():
        print(f"    {pair:<20} {count} shared reachable node(s)")
    print(f"    all three            {len(record['rendezvous'])}")

    if not record.get("chosen"):
        print(f"\n  ENDED  {record.get('ended')}")
        return

    chosen = record["chosen"]
    print(f"\n  CHOSEN ({record['chosen_by']})  {chosen['node_id']}   "
          f"weakest leg {chosen['weakest_leg']:.3f}")
    print("     arranged, not sought — no agent can see another's horizon, and none has an")
    print("     interest in where the others are. The travel is what is earned.")

    print("\n  ON ARRIVAL — before any of them looked")
    for agent_id, state in (record.get("on_arrival") or {}).items():
        print(f"    {agent_id:<8} percept field {state['percept_field']}, "
              f"horizon {state['horizon']}")

    society = record["society"]
    print(f"\n  THE SOCIETY at {society['node_id']}")
    for member in society["members"]:
        print(f"    {member['id']:<8} {', '.join(member['organ_set']):<18} "
              f"measured {member['measured']:<3} arities {member['arities']}")
    print(f"\n  COMPARABILITY CLASSES  {society['classes']}")
    if society.get("silent"):
        print(f"    silent (no evidence either way): {society['silent']}")

    print("\n  EVERY PAIR")
    for verdict in society["verdicts"]:
        print(f"    {verdict['left']:<7} × {verdict['right']:<7} {verdict['outcome'].upper()}")
        print(f"        {verdict['detail'][:110]}")

    print(f"\n  WHAT THE SOCIETY PROPOSED — {len(record['hypotheses'])}")
    for h in record["hypotheses"]:
        print(f"    {h['hypothesis_id']}  {h['claim']} about {h['about_region_id']!r}")
        for contribution in h["rests_on"]:
            print(f"      {contribution['agent_id']:<8} {contribution['organ']:<18} "
                  f"mark {contribution['mark_id']}  {contribution['basis']}")

    print("\n  WHO MAY HOLD IT")
    for agent_id, rows in (record.get("held") or {}).items():
        beliefs = soc.held_beliefs(rows)
        refused = soc.refusals_to_hold(rows)
        if beliefs:
            row = beliefs[0]
            print(f"    {agent_id:<8} holds {len(beliefs)}  {row['epistemic_status']:<13} "
                  f"contributed={row['contributed']} received={row['received']}")
        for row in refused[:1]:
            print(f"    {agent_id:<8} REFUSED {len(refused)}  [{row['reason']}]")
            print(f"             {row['detail'][:100]}")

    print("\n  PUT TO THE OTHERS — the outcome two agents cannot produce")
    for answer in record.get("put_to") or []:
        print(f"    {answer['agent_id']:<8} {answer['answer'].upper():<9} "
              f"[{answer['reason']}]  {answer['detail'][:78]}")

    print(f"\n  posts unchanged: {record['posts_unchanged']}   nothing persisted")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", type=int, default=36, help="retina candidates per locus")
    ap.add_argument("--movements", type=int, default=20)
    ap.add_argument("--rule", default=soc.GROUP_WEAKEST, choices=sorted(soc.GROUP_RULES))
    ap.add_argument("--rendezvous-node", default="",
                    help="name the meeting node yourself; it must still be one ALL THREE can "
                         "reach on a measured crossing")
    ap.add_argument("--atlas-id", default="atlas_wave3_small_society")
    ap.add_argument("--now", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(run(args))
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        _print(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
