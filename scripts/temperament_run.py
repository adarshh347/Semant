#!/usr/bin/env python3
"""
WAVE3 — two agents, one locus, two characters: they diverge without disagreeing.

    python scripts/temperament_run.py                    # the divergence
    python scripts/temperament_run.py --steps 2
    python scripts/temperament_run.py --json

## What this shows

Depth-movement gave an agent two ways to leave a locus whose scores cannot be compared: a
systematicity (a structure-map score) and a depth separation (an ordering statistic), both in
`[0,1]` and not of the same thing. Ranking them would invent a common currency.

So two agents start at the SAME region of the SAME picture, with the same organs and the same
graph, and differ only in **who they are**:

    depth_seeker      prefers axis_occlusion   → moves THROUGH the scene
    analogy_seeker    prefers axis_nestedness  → moves BETWEEN pictures

They measure the same world — the run prints both percept fields and compares them — and they go
different ways. That difference is character, not disagreement.

## The bright line, checked rather than asserted

The run compares the two agents' readings at the shared locus field by field and prints whether
they are identical. If a temperament ever shaded a measurement, this is where it would show.

READS POSTS, WRITES NONE. Every mutating method on the post collection is replaced with a raiser
before the first query, and every post is hashed before and after.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import depth_organ as depth                        # noqa: E402
from backend.services import movement_kernel as mk                       # noqa: E402
from backend.services import nestedness_organ as nestedness              # noqa: E402
from backend.services import occlusion_organ as occlusion                # noqa: E402
from backend.services.agents import movement as mv                       # noqa: E402
from backend.services.agents import situated_agent as sa                 # noqa: E402
from backend.services.agents import temperament as tp                    # noqa: E402
from backend.services.movement_graph import movement_edge_entry, new_movement_edge_id  # noqa: E402

DEFAULT_POST = "6a5fef58a3ddb6341fd69930"
DEFAULT_REGION = "cseg_golden_finial_5"
DEFAULT_GRID = 192
STEP_ID = "wave3_temperament"


def freeze(*collections) -> None:
    blocked = ("insert_one", "insert_many", "update_one", "update_many", "replace_one",
               "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
               "find_one_and_delete", "bulk_write")

    def _raise(*_a, **_k):
        raise AssertionError("this run is read-only — a write was attempted")

    for collection in collections:
        for name in blocked:
            if hasattr(collection, name):
                setattr(collection, name, _raise)


async def load_posts() -> dict:
    from backend.database import post_collection
    freeze(post_collection)
    return {str(p["_id"]): p
            async for p in post_collection.find({"region_annotations.0": {"$exists": True}})}


async def depth_field_for(post: dict, *, grid: int) -> dict:
    import httpx
    from PIL import Image

    from backend.routers.posts import _image_fetch_headers
    from backend.services import depth_service
    from backend.services.vision_orchestrator.adapters import DepthAnythingAdapter
    from backend.services.vision_orchestrator.contracts import CancelToken
    from backend.services.vision_orchestrator.manager import ModelManager
    from backend.services.vision_orchestrator.registry import AdapterRegistry

    url = str(post.get("photo_url") or "")
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=_image_fetch_headers(url))
        resp.raise_for_status()
    image = Image.open(io.BytesIO(resp.content)).convert("RGB")

    adapter = DepthAnythingAdapter()
    if not adapter.is_available():
        raise SystemExit("✗ depth_anything_v2_small is unavailable; this run needs the model.")
    registry = AdapterRegistry()
    registry.register(adapter)
    manager = ModelManager(registry)
    await manager.ensure_loaded(adapter)
    result = await manager.run_adapter(adapter, {"image": image}, priority=0, cancel=CancelToken())
    payload = result.artifact.data
    if grid != int(payload.get("grid") or 0):
        payload = await asyncio.to_thread(depth_service.estimate, image, grid=grid)
    return depth.depth_field(
        payload, adapter=adapter.spec.name, model=adapter.spec.model_id,
        revision=getattr(adapter.spec, "revision", "") or depth_service.REVISION,
        preprocessing_version=adapter.spec.preprocessing_version, whole_frame=True)


def ground_occlusions(agent, post, field, *, now):
    """The writer's part for the depth axis: every occlusion measurable from this locus."""
    post_id = str(post["_id"])
    regions = list(post.get("region_annotations") or [])
    here = next((r for r in regions if str(r.get("id")) == agent.locus.region_id), None)
    edges, marks = [], []
    if here is None:
        return edges, marks
    for other in regions:
        other_id = str(other.get("id") or "")
        if not other_id or other_id == agent.locus.region_id:
            continue
        try:
            reading = occlusion.measure(here, other, field)
        except occlusion.OcclusionRefusal:
            continue
        if reading["relation"] != occlusion.RELATION_IN_FRONT_OF:
            continue
        mark = occlusion.grounding_mark(reading, post_id=post_id, step_id=STEP_ID, now=now)
        marks.append(mark)
        edges.append(movement_edge_entry(
            mark_id=mark["id"], source_node=f"vm_{post_id}:{agent.locus.region_id}",
            target_node=f"vm_{post_id}:{other_id}", spans=[post_id],
            axis_ref=occlusion.AXIS_OCCLUSION, systematicity=None,
            edge_id=new_movement_edge_id(), now=now))
    return edges, marks


async def ground_analogies(agent, posts, *, k, now):
    """And the writer's part for the geometric axis: what the kernel grounds from this locus."""
    try:
        transcript = await mk.run_kernel(
            post_a=posts[agent.locus.post_id], posts=posts, third_post=None,
            region_id=agent.locus.region_id, k=k, max_movements=4, atlas_id="", persist=False)
    except nestedness.NestednessRefusal:
        return [], []
    movements = transcript.get("movements") or []
    marks = [m for mvt in movements for m in (mvt["near_mark"], mvt["far_mark"])]
    return [mvt["edge"] for mvt in movements], marks


def field_signature(agent) -> list:
    """What this agent measured here, in a form two agents can be compared field by field."""
    return sorted(
        [p.reading.direction, p.reading.other_region_id, p.reading.basis,
         bool(p.reading.admissible), p.epistemic_status, p.reading.detail]
        for p in agent.percept_field)


async def run(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)
    post = posts[args.post]

    print(f"   running depth on {args.post} (grid {args.grid})…", file=sys.stderr)
    field = await depth_field_for(post, grid=args.grid)

    record = {"post_id": args.post, "region_id": args.region, "agents": [], "legs": []}

    # ONE graph, ONE world. Both characters are handed the same edges and the same marks; the only
    # difference between them is who they are.
    seed = sa.inhabit(agent_id="seed", post_id=args.post, region_id=args.region,
                      organ_set=(nestedness.ORGAN,))
    occ_edges, occ_marks = ground_occlusions(seed, post, field, now=args.now)
    nest_edges, nest_marks = await ground_analogies(seed, posts, k=args.k, now=args.now)
    graph = {"atlas_id": "temperament", "nodes": [], "edges": occ_edges + nest_edges}
    marks = occ_marks + nest_marks
    record["world"] = {"occlusion_edges": len(occ_edges), "analogy_edges": len(nest_edges),
                       "marks": len(marks)}

    agents = {}
    for name in args.temperaments:
        agent = sa.inhabit(agent_id=f"agent_{name}", post_id=args.post, region_id=args.region,
                           organ_set=(nestedness.ORGAN,), temperament=name)
        sa.perceive(agent, post, now=args.now)
        sa.remember(agent, now=args.now)
        agents[name] = agent
        record["agents"].append({"id": agent.id, "temperament": name,
                                 "prefers": tp.resolve(name).prefers,
                                 "detail": tp.resolve(name).detail})

    signatures = {name: field_signature(agent) for name, agent in agents.items()}
    first = next(iter(signatures.values()))
    record["measurements_identical"] = all(sig == first for sig in signatures.values())
    record["readings_each"] = {name: len(sig) for name, sig in signatures.items()}

    for name, agent in agents.items():
        entries = mv.horizon(agent, graph, posts, proposed_marks=marks)
        chosen = tp.choose(entries, temperament=name)
        leg = {
            "temperament": name, "node_id": agent.locus.node_id,
            "available": chosen["available"], "chose_kind": chosen["chose_kind"],
            "policy": chosen["policy"], "fell_back": chosen["fell_back"],
            "reason": chosen["reason"],
            "attention": [str(getattr(p.reading, "direction", "")) for p in
                          tp.attend(agent.percept_field, temperament=name)],
        }
        if chosen["reach"] is not None:
            entry = mv.step(agent, chosen["reach"], policy=chosen["policy"], now=args.now)
            leg["stepped_to"] = entry["to_node"]
            leg["axis_ref"] = entry["axis_ref"]
            leg["crossed_image"] = entry["crossed_image"]
            leg["relation"] = entry.get("relation")
            leg["mark_id"] = entry["mark_id"]
        record["legs"].append(leg)

    destinations = {leg.get("stepped_to") for leg in record["legs"]}
    record["diverged"] = len(destinations) > 1
    record["posts_unchanged"] = mk.posts_fingerprint(posts) == before
    return record


def _print(record: dict) -> None:
    print("\n" + "=" * 92)
    print("  WAVE3 — two agents, one locus, two characters")
    print("=" * 92)
    print(f"\nlocus  vm_{record['post_id']}:{record['region_id']}")
    world = record["world"]
    print(f"world  {world['occlusion_edges']} occlusion edge(s), "
          f"{world['analogy_edges']} analogy edge(s), {world['marks']} mark(s) — "
          f"ONE graph, handed to both")

    print(f"\nTHE BRIGHT LINE — do they measure the same world?")
    print(f"   readings each: {record['readings_each']}")
    print(f"   MEASUREMENTS IDENTICAL: {record['measurements_identical']}")
    print(f"   Temperament biases selection and attention. It does not touch an organ, so two")
    print(f"   characters at one locus read the same world and differ only in where they go.")

    for agent in record["agents"]:
        print(f"\n{agent['temperament']}  ({agent['id']})")
        print(f"   prefers  {' → '.join(agent['prefers'])}")
        print(f"   {agent['detail']}")

    print(f"\nTHE CHOICE")
    for leg in record["legs"]:
        print(f"\n   {leg['temperament']}")
        print(f"     available   {leg['available']}")
        print(f"     chose kind  {leg['chose_kind']}   by {leg['policy']!r}"
              + ("   (FELL BACK)" if leg["fell_back"] else ""))
        print(f"     because     {leg['reason']}")
        if leg.get("stepped_to"):
            print(f"     STEPPED     {leg['stepped_to']}")
            print(f"                 {leg['axis_ref']} · {leg.get('relation')} · "
                  f"crossed_image={leg['crossed_image']}")

    print(f"\nDIVERGED: {record['diverged']}")
    if record["diverged"]:
        print(f"   Same locus, same organs, same graph, same measurements — different "
              f"destinations.")
        print(f"   The difference is character, and nothing else.")
    print(f"\n   posts unchanged: {record['posts_unchanged']}")
    print(f"   nothing persisted — no edge stored, no mark committed, no post touched.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default=DEFAULT_POST)
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--temperaments", nargs="+", default=["depth_seeker", "analogy_seeker"])
    ap.add_argument("-k", type=int, default=24)
    ap.add_argument("--grid", type=int, default=DEFAULT_GRID)
    ap.add_argument("--now", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(run(args))
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        _print(record)
    ok = record["posts_unchanged"] and record["measurements_identical"] and record["diverged"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
