#!/usr/bin/env python3
"""
WAVE3 — one agent walks from one image to another along a measured axis.

    python scripts/agent_movement_run.py                      # the walk, on the real corpus
    python scripts/agent_movement_run.py --steps 3            # try to go further
    python scripts/agent_movement_run.py --policy heaviest    # the other stated rule
    python scripts/agent_movement_run.py --json               # the raw transcript

The first being in this system whose world is larger because it moved. It inhabits a masked region
in the temple image, perceives through its organ, reads the movement edges reaching its node,
refuses the ones it cannot prove, walks one into a different photograph, and perceives there.

## Who does what, and why the loop is here rather than in the agent

    the kernel   grounds crossings from a locus and mints edges     `movement_kernel.run_kernel`
    the graph    holds them                                         an Atlas document
    the agent    reads its horizon, verifies it, and walks          `agents.movement`

The agent never calls the kernel — `backend/services/agents/movement.py` does not import it, and a
test asserts the absence. So this script plays the part a background writer would play in a running
system: at every locus the agent reaches, it asks the kernel to ground what it can FROM there, adds
those edges to the graph, and then hands the graph to the agent. An agent that grounded its own
crossings would be authoring the world it reports having found in.

## Two worlds, reported side by side

Nothing in this corpus has ever committed a movement mark, so against the DURABLE LEDGER alone the
agent's horizon is empty and it cannot move at all. It moves on the live/private view —
`DECISION-measured-private-vs-shared-ledger`: an agent acts on what its organs measured and does
not wait for a curator to believe its own eyes. Both readings are printed for every horizon, and
the gap between them is the human act this run does not perform.

READS POSTS, WRITES NONE — and not on the honour system: every mutating method on the post
collection is replaced with a raiser before the first query, and the posts are hashed before and
after on top of that. `persist=False` throughout; no mark is committed, no edge is stored.

Needs the usual `.env` (MONGO_DETAILS) and a built retina index — the kernel proposes through it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import movement_kernel as mk                       # noqa: E402
from backend.services import nestedness_organ as organ                   # noqa: E402
from backend.services.agents import movement as mv                       # noqa: E402
from backend.services.agents import situated_agent as sa                 # noqa: E402

#: The temple, and the MASKED finial — the seed the density lane proved groundable (21 measured
#: crossings at k=48). Its VLM twin `fine_0` is a box and grounds nothing, which is the ruling
#: working rather than a coverage problem; `--locus-region fine_0` reproduces that if you want it.
SEED_POST = "6a5fef58a3ddb6341fd69930"
SEED_REGION = "cseg_golden_finial_5"


class WriteAttempted(Exception):
    """A write was attempted against a collection this run may only read."""


def freeze(*collections) -> None:
    """Make writing physically impossible rather than merely unintended.

    The pattern `situated_agent_run.py` and `vision_f0_audit.py` both use. Worth repeating here
    because movement is where an unearned claim is easiest to leave behind: the run touches two
    images instead of one, and a mark quietly committed at the destination would look exactly like
    a measurement the agent had earned by going there.
    """
    def _blocked(*_a, **_k):
        raise WriteAttempted("this run may not write — an agent proposes; it never commits")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                            # noqa: BLE001
                pass


async def load_graph(atlas_id: str) -> dict:
    """The movement edges the corpus ALREADY holds — the graph the agent walks into.

    The agent reads a graph; it does not read only what this run happened to mint. There is exactly
    one such Atlas today and it holds Lane M's single pre-ruling crossing, between two VLM boxes,
    whose mark nobody committed — so it is a road on the map that no agent can take, which is
    precisely the case `visible-but-unreachable` exists to make legible.
    """
    if not atlas_id:
        return {"edges": []}
    from backend.services import atlas_service
    doc = await atlas_service.get_atlas(atlas_id) or {}
    return {"edges": [e for e in (doc.get("edges") or []) if isinstance(e, dict)]}


async def load_posts() -> dict:
    from backend.database import post_collection
    freeze(post_collection)
    posts = {}
    async for post in post_collection.find({"region_annotations.0": {"$exists": True}}):
        posts[str(post["_id"])] = post
    return posts


def _label(post: dict, region_id: str) -> str:
    """A region's label, FOR THE TRANSCRIPT ONLY — never for a decision.

    Every gate in this run is geometry: the organ measures, the kernel grounds, the agent verifies
    a mark against its basis. The words are here so a person can read what happened, and a `cseg_`
    region carries an empty label on purpose, so most of them read as their ids.
    """
    for region in (post or {}).get("region_annotations") or []:
        if str(region.get("id")) == str(region_id):
            return str(region.get("label") or region.get("category") or region_id)
    return region_id


async def ground_from(agent, posts: dict, *, k: int, movements: int) -> dict:
    """Ask the KERNEL what crossings it can ground from where the agent is standing.

    This is the writer's half of a stigmergic graph, played by the script. It returns the edges and
    the marks they cite; nothing is persisted, and the agent is handed the result rather than the
    means to produce it.

    A refusal here is a finding, not an error: "no crossing could be grounded from this locus" is a
    true and interesting statement about a place, and the walk ending there is the honest outcome.
    """
    post = posts[agent.locus.post_id]
    try:
        transcript = await mk.run_kernel(
            post_a=post, posts=posts, third_post=None, region_id=agent.locus.region_id,
            k=k, max_movements=movements, atlas_id="", persist=False)
    except organ.NestednessRefusal as exc:
        return {"edges": [], "marks": [], "refused": str(exc), "considered": 0}

    grounded = transcript.get("movements") or []
    marks = [m for mv_ in grounded for m in (mv_["near_mark"], mv_["far_mark"])]
    considered = transcript.get("considered") or []
    return {
        "edges": [mv_["edge"] for mv_ in grounded],
        "marks": marks,
        "refused": "",
        "considered": len(considered),
        "candidates": len((transcript.get("retina") or {}).get("candidates") or []),
        "retina_status": (transcript.get("retina") or {}).get("status"),
        "box_only": len(transcript.get("box_only_refusals") or []),
        "surface_only": len(transcript.get("surface_only_refusals") or []),
        "seed_basis": transcript["seed"]["measurement"]["basis"],
    }


async def walk(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)
    if args.post not in posts:
        raise SystemExit(f"✗ no post {args.post} carrying regions")

    agent = sa.inhabit(agent_id=args.agent_id, post_id=args.post, region_id=args.locus_region,
                       organ_set=(organ.ORGAN,))
    record: dict = {
        "agent_id": agent.id, "policy": args.policy, "rule": mv.POLICIES[args.policy],
        "posts_loaded": len(posts), "legs": [], "steps": 0,
    }

    graph = await load_graph(args.graph_atlas)
    record["edges_already_in_the_graph"] = len(graph["edges"])
    held_marks: list = []

    for leg in range(int(args.steps) + 1):
        started = time.perf_counter()
        post = posts[agent.locus.post_id]
        field = sa.perceive(agent, post, now=args.now)
        sa.remember(agent, now=args.now)
        stood = mv.footing(agent)

        row: dict = {
            "leg": leg,
            "node_id": agent.locus.node_id,
            "post_id": agent.locus.post_id,
            "region_id": agent.locus.region_id,
            "label": _label(post, agent.locus.region_id),
            "regions_in_reach": len(post.get("region_annotations") or []),
            "perceived": len(field),
            "admissible_readings": stood["admissible_readings"],
            "footing": stood,
            "readings": [{
                "direction": p.reading.direction,
                "other": _label(post, p.reading.other_region_id),
                "other_region_id": p.reading.other_region_id,
                "epistemic_status": p.epistemic_status,
                "basis": p.reading.basis,
                "admissible": p.reading.admissible,
                "detail": p.reading.detail,
            } for p in field],
        }

        if leg == int(args.steps):
            # The budget is spent — but the agent has already perceived here, at the top of this
            # iteration. Arriving without looking would leave the final locus a place it is
            # standing and knows nothing about, which is the narrated arrival this lane refuses.
            row["step"] = None
            row["ended"] = ("the step budget ran out here — this is a limit on the run, not on "
                            "the world. Whether anything is reachable from this locus is a "
                            "question `--steps` decided not to ask")
            row["seconds"] = round(time.perf_counter() - started, 1)
            record["legs"].append(row)
            break

        grounding = await ground_from(agent, posts, k=args.k, movements=args.movements)
        graph = {"edges": [*graph["edges"], *grounding["edges"]]}
        held_marks = [*held_marks, *grounding["marks"]]
        row["kernel"] = {kk: vv for kk, vv in grounding.items() if kk not in ("edges", "marks")}
        row["kernel"]["edges_added"] = len(grounding["edges"])

        # THE TWO WORLDS. The ledger's horizon is computed first and reported even though it is
        # always empty today, because an empty durable horizon is the measured state of this corpus
        # and a run that only showed the private one would be quietly overlaying its own evidence
        # and calling the result "the graph".
        ledger_rows = mv.horizon(agent, graph, posts)
        row["ledger_horizon"] = mv.horizon_tally(ledger_rows)

        rows = mv.horizon(agent, graph, posts, proposed_marks=held_marks)
        row["horizon"] = mv.horizon_tally(rows)
        row["horizon_rows"] = [r.as_dict() for r in rows]
        row["seconds"] = round(time.perf_counter() - started, 1)

        chosen = mv.select(rows, policy=args.policy)
        if chosen is None:
            row["step"] = None
            row["ended"] = ("no reachable movement from here — every crossing this locus can see "
                            "is one the kernel refused, or one whose measurement nobody can read")
            # TRY THE ROAD ANYWAY, so the refusal is a raised exception in the transcript rather
            # than a number in a tally. "Visible but unreachable" is a claim about what happens
            # when something walks at it, and a run that only counted would never have tested it.
            if rows:
                try:
                    mv.step(agent, rows[0], policy=args.policy, now=args.now)
                    row["refused_step"] = "NOT REFUSED — an unreachable movement was walked"
                except mv.Unreachable as exc:
                    row["refused_step"] = str(exc)
            record["legs"].append(row)
            break

        row["step"] = mv.step(agent, chosen, policy=args.policy, now=args.now)
        row["step_to_label"] = _label(posts.get(chosen.destination().post_id) or {},
                                      chosen.destination().region_id)
        record["legs"].append(row)
        record["steps"] += 1

    record["constellation"] = mv.constellation(agent)
    record["trajectory"] = list(agent.trajectory)
    record["memory"] = list(agent.memory)
    record["observations"] = sa.report(agent, atlas_id=args.atlas_id, now=args.now)
    record["proposed_marks"] = len(held_marks)

    mk.assert_posts_unchanged(before, mk.posts_fingerprint(posts))
    record["posts_unchanged"] = True
    return record


def _print(record: dict) -> None:
    print("\n" + "=" * 78)
    print("  WAVE3 — agent movement: a world that grew because something moved")
    print("=" * 78)
    print(f"\n  agent   {record['agent_id']}")
    print(f"  rule    {record['policy']} — {record['rule']}")
    print(f"  corpus  {record['posts_loaded']} posts carrying regions")
    print(f"  graph   {record['edges_already_in_the_graph']} movement edge(s) already stored")

    for row in record["legs"]:
        print("\n" + "-" * 78)
        print(f"  LEG {row['leg']} — {row['node_id']}   ({row['label']!r})")
        print(f"    perceived   {row['perceived']} reading(s) of "
              f"{row['regions_in_reach']} regions in the image, "
              f"{row['admissible_readings']} on masks")
        for reading in row["readings"][:6]:
            flag = "  " if reading["admissible"] else " ~"
            print(f"     {flag}{reading['direction']:>8}  {reading['other']!r:<28} "
                  f"{reading['epistemic_status']:<13} {reading['detail']}")
        if row.get("footing"):
            print(f"    footing     {row['footing']['basis']} — {row['footing']['detail'][:60]}")

        kernel = row.get("kernel") or {}
        if kernel:
            if kernel.get("refused"):
                print(f"    kernel      refused to seed here: {kernel['refused'][:60]}")
            else:
                print(f"    kernel      {kernel.get('candidates', 0)} candidate(s) from the retina "
                      f"({kernel.get('retina_status')}), seed basis {kernel.get('seed_basis')}")
                print(f"                grounded {kernel['edges_added']} crossing(s); refused "
                      f"box_only={kernel.get('box_only', 0)} "
                      f"surface_only={kernel.get('surface_only', 0)}")

        ledger, private = row.get("ledger_horizon") or {}, row.get("horizon") or {}
        if private:
            print(f"    horizon     visible {private['visible']}, REACHABLE "
                  f"{private['reachable']}   refused {private['refused'] or '{}'}")
            print(f"                on the durable ledger: reachable {ledger.get('reachable')} — "
                  f"{ledger.get('refused')}")
            print("                nobody has committed a movement mark in this corpus, so the")
            print("                shared record affords no step at all. The agent moves on what")
            print("                its organs measured "
                  "(DECISION-measured-private-vs-shared-ledger).")

        step = row.get("step")
        if step:
            print(f"    STEP        {step['from_node']}")
            print(f"           —[{step['axis_ref']}, {step['epistemic_status']}, "
                  f"{step['basis']}, systematicity {step['systematicity']}]→")
            print(f"                {step['to_node']}   ({row.get('step_to_label')!r})")
            print(f"                crossed into another image: {step['crossed_image']}")
            print(f"                cites mark {step['mark_id']}   "
                  f"ledger says: {step['ledger_status']}")
        elif row.get("ended"):
            print(f"    ENDED       {row['ended']}")
        if row.get("refused_step"):
            print("    TRIED IT    walking the top visible movement anyway:")
            print(f"                {row['refused_step'][:300]}")

    world = record["constellation"]
    print("\n" + "=" * 78)
    print("  THE CONSTELLATION — the map this agent drew by walking it")
    print("=" * 78)
    print(f"\n  {world['legible']}")
    print(f"\n  loci {len(world['loci'])} across {len(world['posts'])} post(s); "
          f"{len(world['steps'])} measured step(s)")
    for locus in world["loci"]:
        print(f"    {locus['node_id']:<52} {locus['readings']} reading(s) of "
              f"{locus['regions_in_reach']} regions")
    print(f"\n  episodic memory   {len(record['memory'])} entries, private, "
          f"carrying what the organ said")
    print(f"  observations      {len(record['observations'])} proposed to the shared ledger, "
          f"carrying no status at all")
    print(f"  proposed marks    {record['proposed_marks']} — NOT committed")
    print(f"  posts unchanged   {record['posts_unchanged']}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default=SEED_POST)
    ap.add_argument("--locus-region", default=SEED_REGION,
                    help="the region the agent stands on. A MASKED one, or the walk cannot start: "
                         "a measured crossing needs measured geometry at the near end too")
    ap.add_argument("--agent-id", default="agent_alpha")
    ap.add_argument("--steps", type=int, default=2, help="how many crossings to attempt")
    ap.add_argument("-k", type=int, default=24, help="retina candidates per locus")
    ap.add_argument("--movements", type=int, default=8,
                    help="how many grounded crossings the kernel mints per locus")
    ap.add_argument("--policy", default=mv.POLICY_SYSTEMATICITY, choices=sorted(mv.POLICIES))
    ap.add_argument("--atlas-id", default="atlas_wave3_agent_movement",
                    help="the atlas the agent's observations point at")
    ap.add_argument("--graph-atlas", default="atlas_wave2_lane_m",
                    help="the atlas whose stored movement edges the agent walks into; '' for none")
    ap.add_argument("--now", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(walk(args))
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        _print(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
