#!/usr/bin/env python3
"""
WAVE3 — two agents, one locus, against the real corpus.

    python scripts/agent_dialogue_run.py                     # dry run, writes nothing
    python scripts/agent_dialogue_run.py --post <id>
    python scripts/agent_dialogue_run.py --locus-region <id> # stand somewhere exactly
    python scripts/agent_dialogue_run.py --scan 40           # search for a locus at a rim
    python scripts/agent_dialogue_run.py --persist           # write the joint hypotheses
    python scripts/agent_dialogue_run.py --json              # the raw transcript

Two situated agents with DIFFERENT ORGAN-SETS inhabit the SAME locus. α carries containment, β
carries boundary contact. Each measures its own field, they state to each other only what their own
organs measured, and where the two views compose into a claim neither made alone it is posted to the
blackboard as `proposed`.

The run also SHOWS ONE REFUSAL: β is asked to state α's finding — true, about the right place, and
still hearsay, because no organ of β's measured it.

READS POSTS, WRITES NONE — and not on the honour system. Every mutating method on the post
collection is replaced with a raiser before the first query, so a write is physically impossible
rather than merely unintended; the posts are hashed before and after on top of that. With
`--persist` it writes to `agent_hypotheses` and to nothing else. The grounding marks are PROPOSED
and printed; committing one is a curator's act and this script performs none.

Both organs are pure geometry and both are SLOW on full-resolution masks — `adjacency_organ` walks
every boundary pixel's 8-neighbourhood in Python. `--scan` is therefore bounded and says how far it
got; a scan that found nothing is a fact about how far it looked, and the output says so rather
than reporting an empty result as an answer.

Needs the usual `.env` (MONGO_DETAILS). No GPU, no model, no network beyond Mongo.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import adjacency_organ as adjacency                 # noqa: E402
from backend.services import nestedness_organ as nestedness               # noqa: E402
from backend.services.agents import dialogue as dlg                       # noqa: E402
from backend.services.agents import organs                                # noqa: E402
from backend.services.agents import situated_agent as sa                  # noqa: E402
from backend.services.epistemics import STATUS_KEY                        # noqa: E402

DEFAULT_ATLAS_ID = "atlas_wave3_dialogue"
ALPHA, BETA = "alpha", "beta"


class WriteAttempted(Exception):
    """A write was attempted against a collection this run is only allowed to read."""


def freeze(*collections) -> None:
    """Make writing physically impossible, rather than merely unintended.

    The pattern from `scripts/vision_f0_audit.py` and `scripts/situated_agent_run.py`. It matters
    more here, not less: two agents that agree are the most persuasive thing this system can
    produce, and an agreement that quietly committed its own marks would be the graph learning what
    it already believed.
    """
    def _blocked(*_a, **_k):
        raise WriteAttempted(
            "this run may not write to posts — agents propose, and committing is a curator's act")

    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many",
                       "delete_one", "delete_many", "replace_one", "bulk_write",
                       "find_one_and_update", "find_one_and_replace", "find_one_and_delete"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                   # noqa: BLE001
                pass


def _posts():
    from backend.database import post_collection
    freeze(post_collection)
    return post_collection


async def load_post(post_id: str) -> dict:
    from bson import ObjectId
    query = {"_id": ObjectId(post_id)} if ObjectId.is_valid(post_id) else {"_id": post_id}
    return await _posts().find_one(query) or {}


def _masked(post: dict) -> list:
    return [r for r in (post.get("region_annotations") or []) if r.get("mask_rle")]


def _label(post: dict, region_id: str) -> str:
    for region in post.get("region_annotations") or []:
        if str(region.get("id")) == str(region_id):
            return str(region.get("label") or region.get("category") or region_id)
    return region_id


def composable_locus(post: dict) -> str:
    """A region this post's two organs BOTH relate to some third region — i.e. a rim.

    Only mask-carrying regions are considered, and that is the WAVE2.5 ruling doing its work rather
    than a convenience: a box basis makes both readings estimates, and a composition over two
    estimates presented as a joint finding would be firmer-sounding than either half.

    Returns "" when this post affords no composition. That is a fact about the picture — most parts
    sit well inside their wholes or well outside — and not a failure of the run.
    """
    regions = _masked(post)
    for a in regions:
        nested, meets = set(), set()
        for b in regions:
            if a is b:
                continue
            try:
                m = nestedness.measure(a, b)
                if m["nested"] and nestedness.is_admissible(m):
                    nested.add(str(b.get("id")))
            except Exception:                                   # noqa: BLE001
                pass
            try:
                m = adjacency.measure(a, b)
                if m["adjacent"] and adjacency.is_admissible(m):
                    meets.add(str(b.get("id")))
            except adjacency.AdjacencyRefusal:
                pass
        if nested & meets:
            return str(a.get("id"))
    return ""


async def scan_for_a_rim(limit: int) -> tuple:
    """Walk posts until one affords a composition. Bounded, and it reports the bound.

    A scan that reported "no rim in the corpus" after looking at ten images would be a claim about
    the corpus made from an absence of looking — the same error the organs refuse when they raise
    instead of returning a zero.
    """
    seen = 0
    cursor = _posts().find({"region_annotations.1": {"$exists": True}}).limit(int(limit))
    async for post in cursor:
        seen += 1
        region_id = composable_locus(post)
        print(f"  scanned {seen:>3}  {str(post['_id'])}  "
              f"{len(_masked(post))} masked region(s)  "
              f"{'← rim at ' + region_id if region_id else ''}", file=sys.stderr)
        if region_id:
            return post, region_id, seen
    return {}, "", seen


def _refusal(alpha: sa.SituatedAgent, beta: sa.SituatedAgent) -> dict:
    """Ask β to state α's finding. It is true, it is about the right place — and it is hearsay.

    Shown in the run rather than only in a test, because this is the failure the whole lane is
    arranged against and it is the one that looks most like cooperation.
    """
    if not alpha.percept_field:
        return {}
    reading = alpha.percept_field[0].reading
    claim = {"relation": reading.relation, "direction": reading.direction,
             "other_region_id": reading.other_region_id}
    try:
        dlg.say(beta, claim)
    except sa.Hearsay as e:
        return {"claim": claim, "refused": True, "detail": str(e)}
    return {"claim": claim, "refused": False,
            "detail": "NOT REFUSED — β had an organ behind α's claim, so this is not a hearsay test"}


def _print(transcript: dict, post: dict, refusal: dict) -> None:
    print("\n" + "=" * 78)
    print("  WAVE3 — two agents, one locus, first grounded dialogue")
    print("=" * 78)

    locus = transcript["locus"]
    print("\n1. TWO BODIES, ONE PLACE")
    print(f"   locus     {locus['post_id']}:{locus['region_id']}  "
          f"({_label(post, locus['region_id'])!r})")
    for a in transcript["agents"]:
        print(f"   {a['id']:<9} {', '.join(a['organ_set'])}")
    print("   same locus, different organs — so any difference between their fields is a fact")
    print("   about their BODIES, and `exchange` refuses a pair where it would not be.")

    print("\n2. PERCEIVE — two worlds at one place")
    for agent_id, rows in transcript["fields"].items():
        print(f"   {agent_id} measured {len(rows)}:")
        for row in rows:
            flag = "  " if row["admissible"] else " ~"
            print(f"    {flag}{row['relation']:>14}  {_label(post, row['other_region_id'])!r:<24}"
                  f" {row['epistemic_status']:<13} {row['detail']}")
        if not rows:
            print("     (nothing — a fact about this locus, not a failure to look)")

    ex = transcript["exchange"]
    print("\n3. EXCHANGE — ephemeral, agent↔agent, nothing stored")
    for side in ("alpha", "beta"):
        for u in ex[side]["said"]:
            print(f"   {ex[side]['id']} said: {u['relation']}/{u['direction']} "
                  f"{_label(post, u['other_region_id'])!r} — {u['detail']} [{u['epistemic_status']}]")
    print(f"   only α sees: {[_label(post, r) for r in ex['only_alpha']]}")
    print(f"   only β sees: {[_label(post, r) for r in ex['only_beta']]}")
    print(f"   both:        {[_label(post, r) for r in ex['both']]}")
    print("   the regions that differ are not one agent's error. Containment cannot see a")
    print("   neighbour outside the whole and contact cannot see a part deep inside it — the")
    print("   blindness is the shape of the body, and it is the first thing neither knew alone.")

    if refusal:
        print("\n4. REFUSED — hearsay, and it looks exactly like cooperation")
        print(f"   β was asked to state: {refusal['claim']}")
        print(f"   refused: {refusal['refused']}")
        print(f"   {refusal['detail'][:150]}")
        print("   α measured it, it is TRUE, and β stands in the same place. None of that makes")
        print("   it β's to say: a claim without an organ of the SPEAKER behind it is hearsay.")

    print("\n5. COMPOSE — the joint hypothesis, and it is `proposed`")
    if not transcript["hypotheses"]:
        print("   (none — the two views did not compose here)")
    for h, both in zip(transcript["hypotheses"], transcript["hydrated"]):
        print(f"   {h['hypothesis_id']}  claim={h['claim']}  about="
              f"{_label(post, h['about_region_id'])!r}")
        print(f"     agents {h['agent_ids']}   carries an epistemic_status? "
              f"{STATUS_KEY in h}")
        for c in h["rests_on"]:
            print(f"       rests on  {c['agent_id']:<7} {c['organ']:<18} basis={c['basis']:<5} "
                  f"mark {c['mark_id']}")
        a, b = both["as_stored"], both["with_proposed_marks"]
        print(f"     as stored                  {a['ledger_status']:<10} marks live {a['marks_live']}")
        print(f"     with BOTH marks committed  {b['ledger_status']:<10} marks live {b['marks_live']}")
        print("     ↑ the mark count moves; the status does not, and there is no branch that")
        print("       could move it. Committing the inputs makes them durable — the composition")
        print("       is still a reading over two measurements, and agreement is not grounding.")

    print("\n6. HELD — privately, by each agent")
    for agent_id, held in (transcript.get("held") or {}).items():
        for e in held:
            print(f"   {agent_id}: {e[STATUS_KEY]:<13} contributed={e['contributed']} "
                  f"received={e['received']}")
    if transcript.get("held"):
        print("   `interpretive`, NOT `measured` — this lane departs from its card here. The")
        print("   private-vs-ledger decision entitles an agent to believe what ITS OWN organs")
        print("   measured; half of this arrived by testimony, and holding that as `measured`")
        print("   would be hearsay with one extra step — the step that makes it invisible.")

    persisted = (transcript.get("persisted") or {}).get("hypotheses") or []
    if persisted:
        print(f"\n   persisted {len(persisted)} hypothesis(es) to `agent_hypotheses`")

    print(f"\n   proposed marks (NOT committed): {len(transcript['proposed_marks'])}")
    for mark in transcript["proposed_marks"]:
        print(f"     {mark['id']}  {mark[STATUS_KEY]}  "
              f"producer={mark['provenance']['producer']}")
    print(f"\n   posts unchanged: {transcript['posts_unchanged']}")
    print()


async def main_async(args) -> int:
    scanned = 0
    if args.post:
        post = await load_post(args.post)
        if not post:
            print(f"✗ no post {args.post} found", file=sys.stderr)
            return 2
        region_id = str(args.locus_region or "") or composable_locus(post)
    else:
        print(f"scanning up to {args.scan} post(s) for a locus at a rim…", file=sys.stderr)
        post, region_id, scanned = await scan_for_a_rim(args.scan)
        if not post:
            print(f"✗ no locus affording a composition in the {scanned} post(s) scanned. That is a "
                  f"claim about how far this run looked, not about the corpus — raise --scan.",
                  file=sys.stderr)
            return 2

    post_id = str(post["_id"])
    regions = post.get("region_annotations") or []
    print(f"post {post_id} — {len(regions)} regions, {len(_masked(post))} masked", file=sys.stderr)

    if args.locus_region and not any(str(r.get("id")) == args.locus_region for r in regions):
        print(f"✗ no region {args.locus_region!r} in this post", file=sys.stderr)
        return 2
    if not region_id:
        print("✗ this post affords no composition: no masked region sits at another's rim. Most "
              "parts sit well inside their wholes or well outside — that is a fact about the "
              "picture, not a failure of the run. Try --scan or another --post.", file=sys.stderr)
        return 2

    alpha_organs = tuple(args.alpha_organ) or (nestedness.ORGAN,)
    beta_organs = tuple(args.beta_organ) or (adjacency.ORGAN,)

    try:
        transcript = await dlg.run_dialogue(
            post=post, region_id=region_id,
            alpha_organs=alpha_organs, beta_organs=beta_organs,
            alpha_id=ALPHA, beta_id=BETA,
            atlas_id=args.atlas_id, persist=bool(args.persist))
    except organs.OrganRefusal as e:
        print(f"✗ an agent could not perceive: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"✗ these two could not converse: {e}", file=sys.stderr)
        return 1

    # Re-inhabited for the refusal demonstration, so asking β an illegitimate question can never
    # perturb the fields the transcript above already reported.
    alpha = sa.inhabit(agent_id=ALPHA, post_id=post_id, region_id=region_id,
                       organ_set=alpha_organs)
    beta = sa.inhabit(agent_id=BETA, post_id=post_id, region_id=region_id, organ_set=beta_organs)
    for agent in (alpha, beta):
        sa.perceive(agent, post)
    refusal = _refusal(alpha, beta)
    transcript["refused_hearsay"] = refusal
    transcript["scanned_posts"] = scanned

    if args.json:
        print(json.dumps(transcript, indent=2, default=str))
    else:
        _print(transcript, post, refusal)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default="", help="a post id; omit to scan for one")
    ap.add_argument("--scan", type=int, default=25,
                    help="how many posts to search for a locus at a rim. Bounded on purpose, and "
                         "the bound is reported: both organs are pure Python over mask pixels")
    ap.add_argument("--locus-region", default="",
                    help="stand exactly here (a region id). Masked regions only produce a "
                         "`measured` reading — WAVE2.5")
    ap.add_argument("--alpha-organ", action="append", default=[],
                    help=f"repeatable; defaults to {nestedness.ORGAN}")
    ap.add_argument("--beta-organ", action="append", default=[],
                    help=f"repeatable; defaults to {adjacency.ORGAN}")
    ap.add_argument("--atlas-id", default=DEFAULT_ATLAS_ID)
    ap.add_argument("--persist", action="store_true",
                    help="write the joint hypotheses to `agent_hypotheses` (never a post)")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
