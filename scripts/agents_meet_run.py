#!/usr/bin/env python3
"""
WAVE3 — two agents travel across images and meet, and compose what neither knew alone.

    python scripts/agents_meet_run.py                          # the run, on the real corpus
    python scripts/agents_meet_run.py --rule strongest_combined
    python scripts/agents_meet_run.py --rendezvous-node vm_<post>:<region>
    python scripts/agents_meet_run.py --json

α carries containment and β carries boundary contact. Each starts somewhere different, walks a
measured mask-basis crossing into another image, and perceives at the place it arrived — holding
nothing from where it came, because `movement.step` empties the percept field. There they exchange
what each measured HERE, and compose the one claim neither organ can make alone.

## Who does what

    the kernel   grounds crossings from a locus and mints edges     `movement_kernel.run_kernel`
    the graph    holds them                                          an Atlas document
    each agent   reads its OWN horizon, verifies it, and walks       `agents.movement`
    the observer intersects the two horizons and picks a meeting     `agents.meeting.rendezvous`
    the agents   exchange and compose at the shared locus            `agents.dialogue`

The agents never call the kernel, and neither can see the other's horizon. This script plays both
outside parts, and says so: **the travel is earned and the meeting is arranged.** Two agents each
following their own rule would meet by coincidence and essentially never.

## The survey

After the run, the same organs are asked — WITHOUT a position — what a composition would have been
available at each of the other rendezvous the rule passed over. That is a god's-eye reading, it is
computed for the report only, it is never handed to an agent, and it exists so a reader can tell a
meeting that was chosen by the stated rule from one that was chosen because it worked.

READS POSTS, WRITES NONE — every mutating method on the post collection is replaced with a raiser
before the first query, and the posts are hashed before and after on top of that. Nothing is
persisted: no mark committed, no edge stored, no hypothesis written.

Needs the usual `.env` (MONGO_DETAILS) and a built retina index.
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
from backend.services import movement_kernel as mk                       # noqa: E402
from backend.services import nestedness_organ as nest                    # noqa: E402
from backend.services.agents import dialogue as dlg                      # noqa: E402
from backend.services.agents import meeting as mt                        # noqa: E402
from backend.services.agents import movement as mv                       # noqa: E402
from backend.services.agents import organs as agent_organs               # noqa: E402
from backend.services.agents import situated_agent as sa                 # noqa: E402

#: Two loci in TWO DIFFERENT IMAGES with a measured crossing each to a node in a THIRD image
#: neither of them starts in. Found by scouting the corpus rather than assumed: 18 seeds at k=24
#: already put 14 nodes within reach of two different images, and 35 seeds at k=36 put 54 there.
#: Reachability is directional rather than scarce — the destinations concentrate in whichever
#: images resemble the seeds, because the retina proposes by identity similarity. Findings §2.
ALPHA_POST = "695be77ea9ea58f1b6aef5eb"
ALPHA_REGION = "cseg_person_1"
BETA_POST = "695be8baa9ea58f1b6aef609"
BETA_REGION = "cseg_right_shoulder_3"


class WriteAttempted(Exception):
    """A write was attempted against a collection this run may only read."""


def freeze(*collections) -> None:
    """Make writing physically impossible rather than merely unintended."""
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


async def load_graph(atlas_id: str) -> dict:
    if not atlas_id:
        return {"edges": []}
    from backend.services import atlas_service
    doc = await atlas_service.get_atlas(atlas_id) or {}
    return {"edges": [e for e in (doc.get("edges") or []) if isinstance(e, dict)]}


def _label(post: dict, region_id: str) -> str:
    """For the transcript only, never for a decision — and `cseg_*` regions carry no label at all,
    so most of these read as their ids."""
    for region in (post or {}).get("region_annotations") or []:
        if str(region.get("id")) == str(region_id):
            return str(region.get("label") or region.get("category") or region_id)
    return region_id


async def ground_from(agent, posts: dict, *, k: int, movements: int) -> dict:
    """The kernel's crossings from where this agent stands. The writer's half, played by the script.

    The agent is handed the result, never the means: `agents/movement.py` imports no kernel, and a
    test asserts the absence. An agent that grounded the crossing it then walked would be authoring
    the world it reports having travelled through.
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
        "seed_basis": transcript["seed"]["measurement"]["basis"],
    }


def survey(posts: dict, options, limit: int) -> list:
    """What a composition WOULD have been available at each rendezvous the rule passed over.

    A god's-eye reading: it asks both organs about loci no agent went to. Computed after the run,
    for the REPORT only, and never handed to an agent — the same discipline `situated_agent_run`'s
    partiality figure keeps. It exists to answer one question a reader is entitled to ask: was this
    meeting chosen by the stated rule, or chosen because it worked?

    Bounded, and the bound is reported: a survey that looked at eight options and found one is a
    claim about how far it looked.
    """
    out = []
    for option in options[:int(limit)]:
        post = posts.get(option.post_id) or {}
        fields = {}
        for organ_name in (nest.ORGAN, adj.ORGAN):
            try:
                readings = agent_organs.invoke(organ_name, post=post,
                                               region_id=option.region_id, step_id="survey")
            except Exception as exc:                                     # noqa: BLE001
                fields[organ_name] = {"error": repr(exc)[:80], "regions": set()}
                continue
            # `within` ONLY on the containment side, because that is what `dialogue.compose`
            # pairs. A locus that CONTAINS a region and also meets its boundary is not at that
            # region's rim — it is the thing the region is at the rim of, and counting it here
            # would make the survey promise compositions the exchange does not make.
            fields[organ_name] = {"regions": {
                r.other_region_id for r in readings
                if r.admissible and (organ_name != nest.ORGAN or r.direction == "within")}}
        both = fields[nest.ORGAN].get("regions", set()) & fields[adj.ORGAN].get("regions", set())
        out.append({
            "node_id": option.node_id,
            "weakest_leg": option.weakest_leg,
            "combined": option.combined_systematicity,
            "compositions_available": len(both),
            "about": sorted(both),
        })
    return out


async def run(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)
    graph = await load_graph(args.graph_atlas)

    for post_id, region_id, who in ((args.alpha_post, args.alpha_region, "alpha"),
                                    (args.beta_post, args.beta_region, "beta")):
        if post_id not in posts:
            raise SystemExit(f"✗ no post {post_id} for {who}")

    alpha = sa.inhabit(agent_id=args.alpha_id, post_id=args.alpha_post,
                       region_id=args.alpha_region, organ_set=(nest.ORGAN,))
    beta = sa.inhabit(agent_id=args.beta_id, post_id=args.beta_post,
                      region_id=args.beta_region, organ_set=(adj.ORGAN,))

    record: dict = {
        "rule": args.rule, "rule_detail": mt.RENDEZVOUS_RULES[args.rule],
        "posts_loaded": len(posts), "edges_already_in_the_graph": len(graph["edges"]),
        "starts": [], "posts_unchanged": None,
    }

    held_marks: list = []
    for agent in (alpha, beta):
        started = time.perf_counter()
        post = posts[agent.locus.post_id]
        field = sa.perceive(agent, post, now=args.now)
        sa.remember(agent, now=args.now)
        stood = mv.footing(agent)
        grounding = await ground_from(agent, posts, k=args.k, movements=args.movements)
        graph = {"edges": [*graph["edges"], *grounding["edges"]]}
        held_marks = [*held_marks, *grounding["marks"]]
        record["starts"].append({
            "agent_id": agent.id, "organ_set": list(agent.organ_set),
            "node_id": agent.locus.node_id, "label": _label(post, agent.locus.region_id),
            "perceived": len(field), "footing": stood,
            "regions_in_reach": len(post.get("region_annotations") or []),
            "readings": [{"relation": p.reading.relation, "direction": p.reading.direction,
                          "other": p.reading.other_region_id, "basis": p.reading.basis,
                          "epistemic_status": p.epistemic_status,
                          "admissible": p.reading.admissible, "detail": p.reading.detail}
                         for p in field],
            "kernel": {kk: vv for kk, vv in grounding.items() if kk not in ("edges", "marks")},
            "edges_added": len(grounding["edges"]),
            "seconds": round(time.perf_counter() - started, 1),
        })

    # THE TWO HORIZONS, computed independently. Neither agent sees the other's.
    alpha_rows = mv.horizon(alpha, graph, posts, proposed_marks=held_marks)
    beta_rows = mv.horizon(beta, graph, posts, proposed_marks=held_marks)
    record["horizons"] = {alpha.id: mv.horizon_tally(alpha_rows),
                          beta.id: mv.horizon_tally(beta_rows)}
    # And on the durable ledger alone, which has never held a committed movement mark.
    record["ledger_horizons"] = {
        alpha.id: mv.horizon_tally(mv.horizon(alpha, graph, posts)),
        beta.id: mv.horizon_tally(mv.horizon(beta, graph, posts))}
    mv.horizon(alpha, graph, posts, proposed_marks=held_marks)
    mv.horizon(beta, graph, posts, proposed_marks=held_marks)

    options = mt.rendezvous(alpha, beta, alpha_rows, beta_rows)
    options = sorted(options, key=lambda r: (-r.weakest_leg, r.node_id))
    record["rendezvous"] = [r.as_dict() for r in options]

    if args.rendezvous_node:
        chosen = next((r for r in options if r.node_id == args.rendezvous_node), None)
        record["chosen_by"] = "operator"
        if chosen is None:
            record["ended"] = (f"{args.rendezvous_node} is not a node both agents can reach on a "
                               f"measured crossing — it is not a meeting, whoever asked for it")
    else:
        chosen = mt.choose(options, rule=args.rule)
        record["chosen_by"] = f"rule:{args.rule}"

    if chosen is None:
        record.setdefault("ended", "the two horizons do not overlap — no meeting is reachable")
        record["survey"] = survey(posts, options, args.survey)
        mk.assert_posts_unchanged(before, mk.posts_fingerprint(posts))
        record["posts_unchanged"] = True
        return record

    record["chosen"] = chosen.as_dict()
    mv.step(alpha, chosen.alpha, now=args.now)
    mv.step(beta, chosen.beta, now=args.now)
    # ARRIVAL IS EMPTY — recorded, because it is the whole difference between this and a staged
    # meeting and it is invisible once each agent has looked.
    record["on_arrival"] = {a.id: {"percept_field": len(a.percept_field),
                                   "horizon": len(a.horizon)} for a in (alpha, beta)}
    for agent in (alpha, beta):
        sa.perceive(agent, posts[chosen.post_id], now=args.now)
        sa.remember(agent, now=args.now)

    record["meeting"] = mt.meet(alpha, beta, atlas_id=args.atlas_id, now=args.now)

    # THE REFUSAL THAT LOOKS LIKE COOPERATION. β is standing in the same place and has just heard α
    # say it; none of that makes it β's to say.
    record["hearsay"] = None
    alpha_said = (record["meeting"]["exchange"]["alpha"]["said"] or [None])[0]
    if alpha_said:
        claim = {"relation": alpha_said["relation"], "direction": alpha_said["direction"],
                 "other_region_id": alpha_said["other_region_id"]}
        try:
            dlg.say(beta, claim)
            record["hearsay"] = {"claim": claim, "refused": False,
                                 "detail": "NOT REFUSED — an unmeasured claim was admitted"}
        except sa.Hearsay as exc:
            record["hearsay"] = {"claim": claim, "refused": True, "detail": str(exc)}

    record["survey"] = survey(posts, options, args.survey)
    record["survey_bound"] = f"{min(len(options), args.survey)} of {len(options)} rendezvous"

    mk.assert_posts_unchanged(before, mk.posts_fingerprint(posts))
    record["posts_unchanged"] = True
    return record


def _print(record: dict) -> None:
    print("\n" + "=" * 78)
    print("  WAVE3 — two agents move, then meet")
    print("=" * 78)
    print(f"\n  corpus  {record['posts_loaded']} posts carrying regions, "
          f"{record['edges_already_in_the_graph']} movement edge(s) already stored")
    print(f"  rule    {record['rule']} — {record['rule_detail']}")

    for start in record["starts"]:
        print("\n" + "-" * 78)
        print(f"  {start['agent_id'].upper()} starts at {start['node_id']}  "
              f"({start['label']!r})")
        print(f"    body        {', '.join(start['organ_set'])}")
        print(f"    perceived   {start['perceived']} reading(s) of "
              f"{start['regions_in_reach']} regions, "
              f"{start['footing']['admissible_readings']} on masks")
        for reading in start["readings"][:4]:
            flag = "  " if reading["admissible"] else " ~"
            print(f"     {flag}{reading['direction']:>8}  {reading['other']!r:<28} "
                  f"{reading['epistemic_status']:<13} {reading['detail'][:44]}")
        print(f"    footing     {start['footing']['basis']} — "
              f"{start['footing']['detail'][:58]}")
        kernel = start.get("kernel") or {}
        if kernel.get("refused"):
            print(f"    kernel      refused to seed here: {kernel['refused'][:58]}")
        else:
            print(f"    kernel      {kernel.get('candidates')} candidate(s); grounded "
                  f"{start['edges_added']}; refused box_only={kernel.get('box_only')} "
                  f"surface_only={kernel.get('surface_only')}")

    print("\n" + "-" * 78)
    print("  HORIZONS — each agent's own reachable world, computed independently")
    for agent_id, tally in record["horizons"].items():
        ledger = record["ledger_horizons"][agent_id]
        print(f"    {agent_id:<8} visible {tally['visible']}, REACHABLE {tally['reachable']}"
              f"   refused {tally['refused'] or '{}'}")
        print(f"             on the durable ledger: reachable {ledger['reachable']} — "
              f"{ledger['refused']}")

    print(f"\n  RENDEZVOUS — nodes BOTH can reach on a measured crossing: "
          f"{len(record['rendezvous'])}")
    for option in record["rendezvous"][:6]:
        print(f"    {option['node_id']:<52} weakest leg {option['weakest_leg']:.3f}  "
              f"combined {option['combined_systematicity']:.3f}")
    if not record.get("chosen"):
        print(f"\n  ENDED  {record.get('ended')}")
        return

    chosen = record["chosen"]
    print(f"\n  CHOSEN ({record['chosen_by']})  {chosen['node_id']}")
    print("     the meeting is ARRANGED — neither agent can see the other's horizon, and neither")
    print("     has any interest in where the other is. What is EARNED is the travel and")
    print("     everything each agent knows once it gets there.")

    arrival = record.get("on_arrival") or {}
    print("\n  ON ARRIVAL — before either of them looked")
    for agent_id, state in arrival.items():
        print(f"    {agent_id:<8} percept field {state['percept_field']}, "
              f"horizon {state['horizon']}   (a step empties both: arrival is empty)")

    meeting = record["meeting"]
    print(f"\n  THE MEETING at {meeting['node_id']}")
    for journey in meeting["journeys"]:
        print(f"    {journey['agent_id']:<8} {journey['origin_node']}")
        for leg in journey["legs"]:
            print(f"             —[{leg['axis_ref']}, {leg['epistemic_status']}, {leg['basis']}, "
                  f"systematicity {leg['systematicity']}]→")
            print(f"             {leg['to_node']}   cites mark {leg['mark_id']} "
                  f"(ledger: {leg['ledger_status']})")

    exchange = meeting["exchange"]
    print(f"\n  WHAT EACH MEASURED HERE — and only here")
    for side in ("alpha", "beta"):
        said = exchange[side]["said"]
        print(f"    {exchange[side]['id']:<8} {len(said)} utterance(s)")
        for utterance in said[:4]:
            print(f"      {utterance['relation']}/{utterance['direction']:<8} "
                  f"{utterance['other_region_id']!r:<30} {utterance['epistemic_status']:<12} "
                  f"{utterance['detail'][:40]}")
    print(f"    only α sees {len(exchange['only_alpha'])}   "
          f"only β sees {len(exchange['only_beta'])}   both {len(exchange['both'])}")

    print(f"\n  THE EARNED JOINT HYPOTHESIS — {len(meeting['hypotheses'])}")
    for sentence in meeting["legible"]:
        print(f"    {sentence}")
    for h in meeting["hypotheses"][:3]:
        print(f"      {h['hypothesis_id']}  about {h['about_region_id']!r}")
        for contribution in h["rests_on"]:
            print(f"        {contribution['agent_id']:<8} {contribution['organ']:<18} "
                  f"mark {contribution['mark_id']}  {contribution['basis']}")

    print("\n  WHAT EACH AGENT PRIVATELY HOLDS")
    for agent_id, held in meeting["held"].items():
        for entry in held[:2]:
            print(f"    {agent_id:<8} {entry['epistemic_status']:<13} "
                  f"contributed={entry['contributed']} received={entry['received']}")
    print("     interpretive, not measured: half of it arrived by testimony, and walking to the")
    print("     room does not make it the walker's own measurement "
          "(DECISION-testimony-is-interpretive).")

    hearsay = record.get("hearsay")
    if hearsay:
        print(f"\n  HEARSAY, ATTEMPTED — β asked to state α's finding about "
              f"{hearsay['claim']['other_region_id']!r}")
        print(f"    refused: {hearsay['refused']}")
        print(f"    {hearsay['detail'][:200]}")

    print(f"\n  SURVEY (god's-eye, for the report only) — {record.get('survey_bound')}")
    for row in record.get("survey") or []:
        mark = " ←chosen" if row["node_id"] == chosen["node_id"] else ""
        print(f"    {row['node_id']:<52} weakest {row['weakest_leg']:.3f}  "
              f"compositions available {row['compositions_available']}{mark}")

    print(f"\n  posts unchanged: {record['posts_unchanged']}   nothing persisted")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alpha-post", default=ALPHA_POST)
    ap.add_argument("--alpha-region", default=ALPHA_REGION)
    ap.add_argument("--alpha-id", default="alpha")
    ap.add_argument("--beta-post", default=BETA_POST)
    ap.add_argument("--beta-region", default=BETA_REGION)
    ap.add_argument("--beta-id", default="beta")
    ap.add_argument("-k", type=int, default=36, help="retina candidates per locus")
    ap.add_argument("--movements", type=int, default=20,
                    help="grounded crossings the kernel mints per locus")
    ap.add_argument("--rule", default=mt.RENDEZVOUS_MIN, choices=sorted(mt.RENDEZVOUS_RULES))
    ap.add_argument("--rendezvous-node", default="",
                    help="name the meeting node yourself; it must still be one BOTH agents can "
                         "reach on a measured crossing")
    ap.add_argument("--survey", type=int, default=8,
                    help="how many rendezvous to survey for available compositions (report only)")
    ap.add_argument("--graph-atlas", default="atlas_wave2_lane_m",
                    help="atlas whose stored movement edges the agents walk into; '' for none")
    ap.add_argument("--atlas-id", default="atlas_wave3_agents_meet")
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
