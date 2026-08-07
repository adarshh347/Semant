#!/usr/bin/env python3
"""
WAVE3 — an agent walks the depth axis: stepping to what is in front of where it stands.

    python scripts/depth_movement_run.py                    # the guarded walk
    python scripts/depth_movement_run.py --steps 3
    python scripts/depth_movement_run.py --json

## What is new here

Every crossing an agent has walked so far went BETWEEN images: two pictures that share a shape,
stitched by an analogy the kernel grounded. `in_front_of` is not that. It is a fact about ONE
scene, so a depth step moves the agent **within** a picture — from a region to whatever is measured
to be in front of it, or behind it.

    axis_nestedness   'these two images share a relation'    → crossed_image: True
    axis_occlusion    'this thing is in front of that one'   → crossed_image: False

That is the first dimension of Semant's walked space that is not geometry-by-analogy, and it is why
`crossed_image` was always computed on the trajectory row rather than assumed.

## The division of labour, unchanged

    the organ    measures the occlusion and mints the mark    `occlusion_organ`
    this script  mints the edge and hands over the graph      the writer's part, played here
    the agent    READS it, verifies it, and walks it          `agents/movement.py`

`agents/movement.py` imports no organ that could ground a crossing, and the movement suite asserts
that structurally. An agent that grounded its own crossings would author the world it then reports
having found in.

## The floor this run holds

Only `measured` mask-basis occlusion edges may be walked, and the agent checks that itself off the
mark rather than taking the edge's word. A box-basis occlusion is minted into the graph on purpose
so the run can show it being refused — visible, and not reachable.

READS POSTS, WRITES NONE. Every mutating method on the post collection is replaced with a raiser
before the first query, and every post is hashed before and after on top of that.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import depth_organ as depth                        # noqa: E402
from backend.services import movement_kernel as mk                       # noqa: E402
from backend.services import nestedness_organ as organ                   # noqa: E402
from backend.services import occlusion_organ as occlusion                # noqa: E402
from backend.services.agents import movement as mv                       # noqa: E402
from backend.services.agents import situated_agent as sa                 # noqa: E402
from backend.services.movement_graph import movement_edge_entry, new_movement_edge_id  # noqa: E402

#: The image the founding pathology lives in, and the one the occlusion lane measured.
DEFAULT_POST = "6a5fef58a3ddb6341fd69930"
#: The occlusion lane's subject is `cseg_golden_finial_7`, and an agent CANNOT START THERE: its
#: own nestedness readings from that locus are all box-basis, so the near half of the WAVE2.5
#: ruling refuses the step before the road ahead is even consulted. `--region cseg_golden_finial_7`
#: reproduces that refusal, and it is reported rather than worked around.
DEFAULT_REGION = "cseg_golden_finial_5"

#: The finial is a handful of cells; below this the organ refuses rather than measuring the grid.
DEFAULT_GRID = 192

STEP_ID = "wave3_depth_movement"


def freeze(*collections) -> None:
    """Replace every mutating method with a raiser. Belt as well as braces: the run also hashes."""
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
    """The real model, once per image, through the manager that enforces residency."""
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
        raise SystemExit(
            "✗ depth_anything_v2_small is not available on this box. The organ is pure and its "
            "tests run without weights; this RUN needs the model and refuses rather than "
            "inventing a field.")
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


def _label(post: dict, region_id: str) -> str:
    for region in post.get("region_annotations") or []:
        if str(region.get("id")) == str(region_id):
            return str(region.get("label") or region_id)
    return region_id


def ground_occlusions_from(agent, post: dict, field: dict, *, now: str) -> dict:
    """THE WRITER'S PART. Every occlusion the organ can measure from where the agent stands.

    Returns edges and the marks they cite. Nothing is persisted; the agent is handed the result
    rather than the means to produce it — the same division `agent_movement_run.py` keeps with the
    kernel, and for the same reason.

    A BOX-BASIS edge is minted alongside the measured ones on purpose. "Visible but unreachable" is
    a claim about what happens when something tries, and a run that only counted would never test
    it.
    """
    post_id = str(post["_id"])
    regions = list(post.get("region_annotations") or [])
    here = next((r for r in regions if str(r.get("id")) == agent.locus.region_id), None)
    if here is None:
        return {"edges": [], "marks": [], "measured": 0, "interpretive": 0, "refused": "no region"}

    node_here = f"vm_{post_id}:{agent.locus.region_id}"
    edges, marks, measured, interpretive, coplanar, refused = [], [], 0, 0, 0, 0
    for other in regions:
        other_id = str(other.get("id") or "")
        if not other_id or other_id == agent.locus.region_id:
            continue
        try:
            reading = occlusion.measure(here, other, field)
        except occlusion.OcclusionRefusal:
            refused += 1
            continue
        if reading["relation"] != occlusion.RELATION_IN_FRONT_OF:
            coplanar += 1
            continue

        mark = occlusion.grounding_mark(reading, post_id=post_id, step_id=STEP_ID, now=now)
        marks.append(mark)
        edges.append(movement_edge_entry(
            mark_id=mark["id"], source_node=node_here, target_node=f"vm_{post_id}:{other_id}",
            # ONE post. A depth crossing does not leave the picture, and saying it spans two would
            # be describing a journey the measurement never made.
            spans=[post_id], axis_ref=occlusion.AXIS_OCCLUSION,
            # NO systematicity: an occlusion is not an analogy, and a number here would invite a
            # comparison with the geometric axis that nothing licenses.
            systematicity=None, edge_id=new_movement_edge_id(), now=now))
        if reading["admissible"]:
            measured += 1
        else:
            interpretive += 1

    return {"edges": edges, "marks": marks, "measured": measured, "interpretive": interpretive,
            "coplanar": coplanar, "unreadable": refused, "refused": ""}


async def walk(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)
    if args.post not in posts:
        raise SystemExit(f"✗ no post {args.post} carrying regions")

    agent = sa.inhabit(agent_id=args.agent_id, post_id=args.post, region_id=args.region,
                       organ_set=(organ.ORGAN,))
    record: dict = {"agent_id": agent.id, "policy": args.policy,
                    "rule": mv.POLICIES[args.policy], "legs": [], "steps": 0}

    fields: dict = {}
    held_marks: list = []
    graph: dict = {"atlas_id": "depth_walk", "edges": [], "nodes": []}

    for leg in range(int(args.steps) + 1):
        post = posts[agent.locus.post_id]
        if agent.locus.post_id not in fields:
            print(f"   running depth on {agent.locus.post_id} (grid {args.grid})…",
                  file=sys.stderr)
            fields[agent.locus.post_id] = await depth_field_for(post, grid=args.grid)
        field = fields[agent.locus.post_id]

        started = time.perf_counter()
        percepts = sa.perceive(agent, post, now=args.now)
        sa.remember(agent, now=args.now)
        stood = mv.footing(agent)

        grounded = ground_occlusions_from(agent, post, field, now=args.now)
        graph["edges"].extend(grounded["edges"])
        held_marks.extend(grounded["marks"])

        entries = mv.horizon(agent, graph, posts, proposed_marks=held_marks,
                             axis=occlusion.AXIS_OCCLUSION)
        tally = mv.horizon_tally(entries)

        row = {
            "leg": leg, "node_id": agent.locus.node_id, "post_id": agent.locus.post_id,
            "region_id": agent.locus.region_id,
            "label": _label(post, agent.locus.region_id),
            "perceived": len(percepts), "footing": stood,
            "occlusions": {k: grounded[k] for k in
                           ("measured", "interpretive", "coplanar", "unreadable")},
            "horizon": tally,
            # HOW MUCH THE RULE ACTUALLY CHOOSES. The separation statistic saturates: a pair whose
            # depth distributions do not overlap scores exactly 1.0, and on this corpus most do.
            # Where every reachable row ties at the ceiling, `clearest_ordering` has decided
            # nothing and the tie-break — the destination node id — has decided everything. Better
            # said out loud than discovered later.
            "ordering_saturation": {
                "reachable": tally["reachable"],
                "at_ceiling": sum(1 for r in entries if r.reachable and r.ordering >= 1.0),
                "distinct_scores": len({round(r.ordering, 4) for r in entries if r.reachable}),
            },
            "rows": [r.as_dict() for r in sorted(entries, key=lambda r: -r.ordering)[:6]],
            "seconds": round(time.perf_counter() - started, 2),
        }
        record["legs"].append(row)

        if leg >= int(args.steps):
            break

        chosen = mv.select(entries, policy=args.policy)
        if chosen is None:
            row["ended"] = "nothing reachable from here"
            break

        # WALK AT A REFUSED ONE FIRST. "Visible but unreachable" is a claim about what happens
        # when something tries, and only a raise proves it.
        blocked = next((r for r in entries if not r.reachable), None)
        if blocked is not None:
            try:
                mv.step(agent, blocked, policy=args.policy, now=args.now)
                row["tried_the_refused_one"] = "STEPPED — BUG"
            except mv.Unreachable as exc:
                row["tried_the_refused_one"] = str(exc)

        try:
            entry = mv.step(agent, chosen, policy=args.policy, now=args.now)
        except mv.Unreachable as exc:
            # The NEAR half of the ruling, and a finding rather than a crash: an agent whose own
            # locus rests on estimates may not step, however well-measured the road ahead is.
            row["ended"] = str(exc)
            record["footing_refusal"] = str(exc)
            break
        record["steps"] += 1
        row["stepped"] = {k: entry.get(k) for k in
                          ("to_node", "axis_ref", "relation", "ordering", "mark_id", "basis",
                           "epistemic_status", "ledger_status", "crossed_image", "policy")}

    record["constellation"] = mv.constellation(agent)
    record["posts_unchanged"] = mk.posts_fingerprint(posts) == before
    return record


def _print(record: dict) -> None:
    print("\n" + "=" * 92)
    print("  WAVE3 — an agent walks the depth axis")
    print("=" * 92)
    print(f"\nagent {record['agent_id']}   policy {record['policy']}")
    print(f"rule  {record['rule']}")

    for row in record["legs"]:
        print(f"\nLEG {row['leg']} — {row['node_id']}   ({row['label']!r})")
        print(f"  perceived   {row['perceived']} reading(s); footing "
              f"{row['footing']['basis']} → admissible={row['footing']['admissible']}")
        occ = row["occlusions"]
        print(f"  occlusions  measured {occ['measured']}, interpretive {occ['interpretive']}, "
              f"coplanar {occ['coplanar']}, unreadable {occ['unreadable']}")
        print(f"  horizon     visible {row['horizon']['visible']}, "
              f"REACHABLE {row['horizon']['reachable']}   refused {row['horizon']['refused']}")
        sat = row["ordering_saturation"]
        print(f"  ordering    {sat['at_ceiling']} of {sat['reachable']} reachable rows tie at "
              f"1.0000 ({sat['distinct_scores']} distinct score(s)) — where they all tie, the "
              f"rule\n              has chosen nothing and the destination id has chosen "
              f"everything")
        for r in row["rows"]:
            flag = "→" if r["reachable"] else "×"
            print(f"    {flag} {r['other_node']:<44} {r['relation'] or '-':<12} "
                  f"ordering {r['ordering'] or 0:.4f}  {r['basis']:<5} {r['epistemic'] or '-'}"
                  + ("" if r["reachable"] else f"  [{r['reason']}]"))
        if row.get("tried_the_refused_one"):
            print(f"  TRIED IT    {row['tried_the_refused_one'][:150]}")
        if row.get("stepped"):
            s = row["stepped"]
            print(f"  STEPPED     {s['to_node']}")
            print(f"              {s['axis_ref']} · {s['relation']} · ordering "
                  f"{s['ordering']:.4f} · {s['basis']} · {s['epistemic_status']}")
            print(f"              crossed_image={s['crossed_image']}  "
                  f"ledger={s['ledger_status']}  mark={s['mark_id']}")
        if row.get("ended"):
            print(f"  ENDED       {row['ended']}")

    con = record["constellation"]
    print(f"\nTHE CONSTELLATION — {len(con.get('loci') or [])} loci, "
          f"{len(con.get('steps') or [])} step(s), "
          f"{len(con.get('posts') or [])} image(s)")
    print(f"   {con.get('legible')}")
    print(f"\n   ONE image, {len(con.get('steps') or [])} steps: the depth axis moves an agent")
    print(f"   THROUGH a scene rather than between pictures. Every crossing above has")
    print(f"   crossed_image=False, which no walk before this one could have produced.")

    print(f"\n   posts unchanged: {record['posts_unchanged']}")
    print(f"   nothing persisted — no edge stored, no mark committed, no post touched.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default=DEFAULT_POST)
    ap.add_argument("--region", default=DEFAULT_REGION,
                    help="the locus to start from; needs mask-basis footing to step at all")
    ap.add_argument("--agent-id", default="agent_alpha")
    ap.add_argument("--steps", type=int, default=2)
    ap.add_argument("--grid", type=int, default=DEFAULT_GRID)
    ap.add_argument("--policy", default=mv.POLICY_ORDERING, choices=sorted(mv.POLICIES))
    ap.add_argument("--now", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(walk(args))
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        _print(record)
    ok = record["posts_unchanged"] and record["steps"] > 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
