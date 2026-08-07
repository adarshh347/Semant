#!/usr/bin/env python3
"""
WAVE3 — where the society's outcomes actually live in the corpus, and where the fights will be.

    python scripts/society_characterization.py                 # the full sweep
    python scripts/society_characterization.py --posts 4        # a smaller bound
    python scripts/society_characterization.py --no-depth       # skip the model-backed body
    python scripts/society_characterization.py --json

The society (#162) was seen on ONE meeting locus. It produced `composed` and `incommensurable`;
`coexistent` never occurred and nobody had looked for it. This sweep looks — over a stated number
of loci across a stated number of posts — and reports which social outcomes the real corpus
actually produces, where, and how often.

Its second job is to hand the next lane its cases: the pairs where **nestedness says CONTAINED and
depth says the inner region is far NEARER than what supposedly contains it.** Those are where α and
a depth agent will hold a genuine measured contradiction the moment an occlusion relation exists.

## What this measures, and the one thing it deliberately does not

It calls `society.relate` — the pairwise verdict — directly, and **not** `society.convene`.
`convene` requires every member to have WALKED to the locus and perceived there, which is right for
a meeting and wrong for a census: making four agents travel to each of hundreds of loci would take
days and would measure the movement graph's reachability rather than the society's structure. So:

    what this reports    where each outcome LIVES — which loci afford which social structure
    what it does NOT     that any of these meetings were earned

Those are different claims and this script makes only the first.

## The seed set is RANKED, not measured

There is no occlusion relation in this system, by design (#161: "it does not resolve the finial
case"). This script therefore **grounds nothing** and mints no relation. It reports, for every
mask-basis nested pair, the depth separation between the part and its supposed container, in units
of the frame's own depth spread — and ranks by it. A large separation is a **candidate** for
"in front of rather than inside", on a rule stated here and readable by anyone; it is not a
measurement of occlusion, and the ranking rule is mine rather than an organ's.

Both numbers under it are measured: the nesting is the nestedness organ's, and the depths are the
depth organ's, each on the mask substrate.

READS POSTS, WRITES NONE — every mutating method on the post collection is replaced with a raiser
before the first query, and the posts are hashed before and after.

Needs `.env` (MONGO_DETAILS), network for the images, and the depth model for §3 (`--no-depth`
skips it and says so in the report).
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

from backend.services import adjacency_organ as adjacency                # noqa: E402
from backend.services import chroma_organ as chroma                      # noqa: E402
from backend.services import depth_organ as depth                        # noqa: E402
from backend.services import mask_geometry as mg                         # noqa: E402
from backend.services import movement_kernel as mk                       # noqa: E402
from backend.services import nestedness_organ as nest                    # noqa: E402
from backend.services.agents import organs as agent_organs               # noqa: E402
from backend.services.agents import situated_agent as sa                 # noqa: E402
from backend.services.agents import society as soc                       # noqa: E402

#: The four bodies, and which of them the society can carry at once. Named here so the sweep's cast
#: is a value in the report rather than a fact about the loop.
BODIES = {
    "alpha": (nest.ORGAN,),
    "beta": (adjacency.ORGAN,),
    "gamma": (chroma.ORGAN,),
    "delta": (depth.ORGAN,),
}

#: How much of a region must land on the depth grid before it is worth reading. The organ refuses
#: below its own floor; this is the sweep's pre-filter so a refusal per tiny region is not the bulk
#: of the output.
DEPTH_GRID = 32


class WriteAttempted(Exception):
    """A write was attempted against a collection this run may only read."""


def freeze(*collections) -> None:
    def _blocked(*_a, **_k):
        raise WriteAttempted("this is a measurement lane — it reads the corpus and writes nothing")

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


async def fetch_image(photo_url: str, *, attempts: int = 3):
    """The pixels, with retries — because an image this run failed to fetch shrinks the BOUND.

    A first full sweep lost 8 of 20 posts to transient DNS and connect failures, and the honest
    consequence of that is a smaller claim, not a missing row. Retried rather than tolerated, and
    whatever still fails is recorded by post id in the report.
    """
    import io

    import httpx
    from PIL import Image

    from backend.routers.posts import _image_fetch_headers

    last = None
    for attempt in range(int(attempts)):
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
                resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as exc:                                         # noqa: BLE001
            last = exc
            await asyncio.sleep(2.0 * (attempt + 1))
    raise last


async def depth_field_for(image, *, grid: int):
    """A whole-frame depth field through the roster adapter, or a reason it could not be had.

    Through `ModelManager` rather than `depth_service.estimate` directly — the residency the depth
    lane insisted on is only real if this run pays it too.
    """
    from backend.services import depth_service
    from backend.services.vision_orchestrator.adapters import DepthAnythingAdapter
    from backend.services.vision_orchestrator.contracts import CancelToken
    from backend.services.vision_orchestrator.manager import ModelManager
    from backend.services.vision_orchestrator.registry import AdapterRegistry

    adapter = DepthAnythingAdapter()
    if not adapter.is_available():
        raise RuntimeError("depth_anything_v2_small is not available on this box")

    registry = AdapterRegistry()
    registry.register(adapter)
    manager = ModelManager(registry)
    await manager.ensure_loaded(adapter)
    result = await manager.run_adapter(adapter, {"image": image}, priority=0, cancel=CancelToken())
    if not result.ok or result.artifact is None:
        raise RuntimeError(f"the depth adapter returned {result.status}")

    payload = result.artifact.data
    if grid != int(payload.get("grid") or 0):
        payload = await asyncio.to_thread(depth_service.estimate, image, grid=grid)
    return depth.depth_field(
        payload, adapter=adapter.spec.name, model=adapter.spec.model_id,
        revision=getattr(adapter.spec, "revision", "") or depth_service.REVISION,
        preprocessing_version=adapter.spec.preprocessing_version, whole_frame=True)


# ── §1+2: the outcome distribution ──────────────────────────────────────────

def masked_regions(post: dict) -> list:
    """Regions carrying measured geometry. Box-basis loci are excluded from the CENSUS on purpose:
    under WAVE2.5 a box reading is an estimate, and a society built on two estimates would be
    characterising the fallback rather than the sense."""
    return [r for r in (post.get("region_annotations") or [])
            if isinstance(r, dict) and mg.rle_is_valid(r.get("mask_rle"))]


def stand(post: dict, region_id: str, organ_set, *, agent_id: str,
          image=None, depth_field=None):
    """One agent inhabiting one locus, having perceived. `None` when its organ refuses here.

    A refusal is not an empty field: `organs.invoke` raises when the organ could not look at all
    (too few depth cells, too few sampled pixels), and an agent that could not look must not be
    reported as one that looked and found nothing.
    """
    agent = sa.inhabit(agent_id=agent_id, post_id=str(post["_id"]), region_id=region_id,
                       organ_set=organ_set)
    try:
        sa.perceive(agent, post, image=image, depth_field=depth_field)
    except (agent_organs.OrganRefusal, chroma.ChromaRefusal, depth.DepthRefusal,
            nest.NestednessRefusal, adjacency.AdjacencyRefusal):
        return None
    return agent


def _directions(agent) -> dict:
    """Which way this agent's organ faced toward each region it related the locus to.

    `within` (the locus is the part) and `contains` (the locus is the whole) are both measurements
    FROM the locus, and only the first composes with `meets` — a locus that contains a region and
    also touches its boundary is not at that region's rim, it is the thing the region is at the rim
    of. That asymmetry is invisible in a shared-subject count.
    """
    out: dict = {}
    for perception in agent.percept_field:
        out.setdefault(perception.reading.other_region_id, set()).add(perception.reading.direction)
    return out


def census_at(post: dict, region_id: str, *, image=None, depth_field=None) -> dict:
    """Every pair of bodies at one locus → the society's verdict on each.

    `soc.relate` is called directly and `soc.convene` deliberately is not — see the module note.
    """
    agents = {}
    for agent_id, organ_set in BODIES.items():
        if organ_set == (chroma.ORGAN,) and image is None:
            continue
        if organ_set == (depth.ORGAN,) and depth_field is None:
            continue
        agent = stand(post, region_id, organ_set, agent_id=agent_id,
                      image=image, depth_field=depth_field)
        if agent is not None:
            agents[agent_id] = agent

    rows = []
    ids = sorted(agents)
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            verdict = soc.relate(agents[left], agents[right])
            left_dirs, right_dirs = _directions(agents[left]), _directions(agents[right])
            rows.append({
                "left": left, "right": right, "outcome": verdict.outcome,
                "left_organ": agents[left].organ_set[0], "right_organ": agents[right].organ_set[0],
                "left_arity": sorted(soc.arities(agents[left])),
                "right_arity": sorted(soc.arities(agents[right])),
                "shared_subjects": list(verdict.shared_subjects),
                # WHICH WAY EACH ORGAN FACED over the subjects they share. Without this a
                # `coexistent` row carrying eight shared subjects reads as a contradiction; with
                # it, the two sub-kinds separate — see `coexistent_cases`.
                "shared_directions": sorted({
                    f"{ld}+{rd}" for subject in verdict.shared_subjects
                    for ld in left_dirs.get(subject, ())
                    for rd in right_dirs.get(subject, ())}),
                "hypotheses": len(verdict.hypotheses),
            })

    society = soc.Society(members=[agents[a] for a in ids])
    return {
        "post_id": str(post["_id"]), "region_id": region_id,
        "node_id": f"vm_{post['_id']}:{region_id}",
        "bodies": {a: agents[a].organ_set[0] for a in ids},
        "measured": {a: len(agents[a].percept_field) for a in ids},
        "absent": sorted(set(BODIES) - set(ids)),
        "classes": society.classes(), "silent": society.silent(),
        "pairs": rows,
    }


# ── §3: where the fights will be ────────────────────────────────────────────

def separations(post: dict, field, *, limit: int) -> list:
    """For every mask-basis nested pair: how much NEARER is the part than its container?

    THE RULE, stated so it can be argued with:

        separation = (depth_mean(inner) − depth_mean(outer)) / (frame depth spread)

    Depth is inverse — larger is nearer — so a POSITIVE separation means the part sits in front of
    the thing said to contain it. Normalised by the frame's own spread because the model returns
    relative depth in a raw scale, so a bare difference is not comparable between images.

    THIS IS A RANKING, NOT A MEASUREMENT OF OCCLUSION. Nothing here decides that a large separation
    means "in front of rather than inside" — a part genuinely inside a receding container is nearer
    than its container's mean too, and no threshold in this script separates the two cases. What it
    produces is an ordered list of candidates, with both organs' own numbers attached, for the lane
    that will have a relation able to decide.
    """
    regions = {str(r.get("id")): r for r in masked_regions(post)}
    pairs = [m for m in nest.find_nested_pairs(list(regions.values()))
             if m["basis"] == nest.ADMISSIBLE_BASIS]
    if not pairs:
        return []

    grid_depth = list(field["depth"])
    spread = (max(grid_depth) - min(grid_depth)) or 1.0

    # ONE DEPTH READING PER REGION, not per pair. `depth.measure` decodes the region's full-
    # resolution mask onto the grid in pure Python, and the temple post has 45 masked regions in
    # 176 nested pairs — 352 decodes of 45 masks, which is where the first sweep spent most of an
    # hour. A region's depth does not depend on which pair it is being read for, so caching it is
    # not an approximation; `None` caches the refusal too, so a region the organ cannot read is
    # refused once rather than 176 times.
    read: dict = {}

    def depth_of(region_id: str):
        if region_id not in read:
            try:
                read[region_id] = depth.measure(regions[region_id], field)
            except depth.DepthRefusal:
                read[region_id] = None
        return read[region_id]

    out = []
    for m in pairs:
        inner_id, outer_id = str(m["inner_region_id"]), str(m["outer_region_id"])
        inner, outer = depth_of(inner_id), depth_of(outer_id)
        if inner is None or outer is None:
            continue
        if inner["basis"] != "mask" or outer["basis"] != "mask":
            continue
        out.append({
            "post_id": str(post["_id"]),
            "inner_region_id": inner_id, "outer_region_id": outer_id,
            "inner_label": str(regions[inner_id].get("label") or ""),
            "outer_label": str(regions[outer_id].get("label") or ""),
            "nesting_index": m["nesting_index"], "containment": m["containment"],
            "nesting_basis": m["basis"],
            "inner_depth": inner["depth_mean"], "outer_depth": outer["depth_mean"],
            "inner_frame_rank": inner["frame_rank"], "outer_frame_rank": outer["frame_rank"],
            "separation": round((inner["depth_mean"] - outer["depth_mean"]) / spread, 4),
            "frame_spread": round(spread, 6),
        })
    out.sort(key=lambda r: -r["separation"])
    return out[:limit]


# ── the sweep ───────────────────────────────────────────────────────────────

async def sweep(args) -> dict:
    posts = await load_posts()
    before = mk.posts_fingerprint(posts)

    chosen = sorted(posts)[:int(args.posts)] if args.posts else sorted(posts)
    record: dict = {
        "bound": {
            "posts_in_corpus": len(posts),
            "posts_scanned": len(chosen),
            "loci_per_post": int(args.loci),
            "bodies": {a: o[0] for a, o in BODIES.items()},
            "depth": bool(args.depth),
            "note": ("bounds are stated because a sweep that found nothing is a claim about how "
                     "far it looked, not about the corpus"),
        },
        "posts": [], "loci": [], "seed_set": [], "depth_failures": [],
    }

    for post_id in chosen:
        post = posts[post_id]
        started = time.perf_counter()
        regions = masked_regions(post)[:int(args.loci)]
        image = None
        field = None

        url = str(post.get("photo_url") or "")
        if url and (args.depth or args.chroma):
            try:
                image = await fetch_image(url)
            except Exception as exc:                                     # noqa: BLE001
                record["depth_failures"].append(
                    {"post_id": post_id, "stage": "image", "detail": repr(exc)[:120]})
        if image is not None and args.depth:
            try:
                field = await depth_field_for(image, grid=DEPTH_GRID)
            except Exception as exc:                                     # noqa: BLE001
                record["depth_failures"].append(
                    {"post_id": post_id, "stage": "depth", "detail": repr(exc)[:120]})

        for region in regions:
            record["loci"].append(census_at(post, str(region["id"]),
                                            image=image if args.chroma else None,
                                            depth_field=field))
        if field is not None:
            record["seed_set"].extend(separations(post, field, limit=int(args.seeds)))

        record["posts"].append({
            "post_id": post_id, "masked_regions": len(masked_regions(post)),
            "loci_scanned": len(regions), "had_image": image is not None,
            "had_depth": field is not None,
            "seconds": round(time.perf_counter() - started, 1),
        })
        print(f"  {post_id}  loci={len(regions):<3} depth={'y' if field is not None else 'n'}  "
              f"{record['posts'][-1]['seconds']}s", file=sys.stderr)
        # CHECKPOINT after every post. The depth model runs once per image and Atlas has dropped
        # this session's connection mid-sweep before; a run that loses twenty minutes of GPU work
        # to a TLS timeout would tempt whoever reruns it to shrink the bound, and the bound is the
        # claim. Written only when asked, so the default run still touches nothing but the report.
        if args.state:
            with open(args.state, "w") as handle:
                json.dump(record, handle, default=str)

    record["seed_set"].sort(key=lambda r: -r["separation"])
    # THE WHOLE DISTRIBUTION, not only the top of it. A ranked list with the tail cut off cannot be
    # read as evidence that the top is unusual — which is the only thing a candidate list is for.
    seps = sorted(r["separation"] for r in record["seed_set"])
    record["separation_spread"] = ({
        "pairs_ranked": len(seps), "min": seps[0], "max": seps[-1],
        "median": seps[len(seps) // 2],
        "positive": sum(1 for s in seps if s > 0),
        "above_0.20": sum(1 for s in seps if s > 0.20),
    } if seps else {"pairs_ranked": 0})
    record["seed_set"] = record["seed_set"][: int(args.seeds) * 4]
    record["outcomes"] = tally(record["loci"])
    record["coexistent"] = coexistent_cases(record["loci"])

    mk.assert_posts_unchanged(before, mk.posts_fingerprint(posts))
    record["posts_unchanged"] = True
    return record


def tally(loci: list) -> dict:
    """The distribution, and BY BODY PAIR as well as overall — a single count would hide that one
    outcome belongs almost entirely to one kind of pairing."""
    overall = Counter()
    by_pair = {}
    for locus in loci:
        for row in locus["pairs"]:
            overall[row["outcome"]] += 1
            key = " × ".join(sorted((row["left_organ"], row["right_organ"])))
            by_pair.setdefault(key, Counter())[row["outcome"]] += 1
    return {
        "loci": len(loci),
        "pair_verdicts": sum(overall.values()),
        "overall": dict(sorted(overall.items(), key=lambda kv: -kv[1])),
        "by_body_pair": {k: dict(sorted(v.items(), key=lambda kv: -kv[1]))
                         for k, v in sorted(by_pair.items())},
    }


def coexistent_cases(loci: list) -> dict:
    """`coexistent` split by whether the pair could ever have composed anything.

    THE DISTINCTION THAT MATTERS, and the sweep's own finding: two RELATION organs sharing no
    region is the case the card asked for — comparable bodies that measured nothing in common
    HERE. Two FIELD organs (chroma, depth) also come out `coexistent` because the society's arity
    rule makes them comparable, and that is a different animal: they share an arity and have no
    composition rule at all, so "nothing in common here" overstates what could have happened.
    """
    relational, fieldwise = [], []
    for locus in loci:
        for row in locus["pairs"]:
            if row["outcome"] != soc.COEXISTENT:
                continue
            case = {**{k: locus[k] for k in ("post_id", "region_id", "node_id")}, **row}
            # AND THE TWO SUB-KINDS, which the sweep found rather than expected. `disjoint` is what
            # the card described: two organs that related the locus to entirely different regions.
            # `direction` is the other one: they DID relate it to the same regions and still
            # compose nothing, because the nesting ran the wrong way — the locus contains those
            # regions and also meets their boundaries, which is not the same claim as being at
            # their rim, and is exactly why `compose` pairs `within` with `meets` and not
            # `contains`.
            case["why"] = "disjoint" if not row["shared_subjects"] else "direction"
            (relational if row["left_arity"] == [2] and row["right_arity"] == [2]
             else fieldwise).append(case)
    return {
        "relational": relational[:12], "relational_total": len(relational),
        "relational_why": dict(Counter(c["why"] for c in relational)),
        "fieldwise": fieldwise[:4], "fieldwise_total": len(fieldwise),
    }


def _print(record: dict) -> None:
    bound = record["bound"]
    print("\n" + "=" * 78)
    print("  WAVE3 — the society, characterized on the real corpus")
    print("=" * 78)
    print(f"\n  SCAN BOUND   {bound['posts_scanned']} of {bound['posts_in_corpus']} "
          f"region-carrying posts, up to {bound['loci_per_post']} masked loci each")
    print(f"               bodies {bound['bodies']}")
    print(f"               depth model: {'run' if bound['depth'] else 'SKIPPED (--no-depth)'}")
    for failure in record["depth_failures"][:4]:
        print(f"               ! {failure['post_id']} {failure['stage']}: {failure['detail'][:52]}")

    outcomes = record["outcomes"]
    print(f"\n  {outcomes['pair_verdicts']} pair verdicts over {outcomes['loci']} loci")
    print("\n  OUTCOME DISTRIBUTION")
    for outcome, count in outcomes["overall"].items():
        share = 100.0 * count / max(1, outcomes["pair_verdicts"])
        print(f"    {outcome:<18} {count:>6}   {share:5.1f}%")

    print("\n  BY BODY PAIR")
    for pair, counts in outcomes["by_body_pair"].items():
        print(f"    {pair:<44} {counts}")

    cox = record["coexistent"]
    print("\n" + "-" * 78)
    print("  COEXISTENT — comparable, and nothing in common HERE")
    print(f"    relation × relation   {cox['relational_total']}   "
          f"(the case the lane went looking for)   {cox['relational_why']}")
    print(f"    field × field         {cox['fieldwise_total']}   "
          f"(same arity, no composition rule at all — see the findings)")
    print("      disjoint  = they related the locus to entirely different regions")
    print("      direction = same regions, and the nesting ran the wrong way (contains, not")
    print("                  within) — the locus is what those regions are at the rim OF")
    for case in cox["relational"][:6]:
        print(f"      [{case['why']}] {case['node_id']}")
        print(f"        {case['left_organ']} × {case['right_organ']}, "
              f"{len(case['shared_subjects'])} shared subject(s), "
              f"directions {case['shared_directions'] or '[]'}")
    if not cox["relational"]:
        print("      NONE FOUND within the bound above — a claim about how far this looked.")

    print("\n" + "-" * 78)
    print("  THE SEED SET — where a depth agent will contradict a nestedness agent")
    print("    separation = (depth(inner) − depth(outer)) / frame spread; depth is INVERSE, so")
    print("    positive means the part sits IN FRONT OF what is said to contain it.")
    print("    A RANKING, not a measurement of occlusion — no relation exists to decide it yet.")
    spread = record.get("separation_spread") or {}
    if spread.get("pairs_ranked"):
        print(f"    {spread['pairs_ranked']} pairs ranked · separation "
              f"{spread['min']:+.3f} … {spread['max']:+.3f}, median {spread['median']:+.3f} · "
              f"{spread['positive']} positive, {spread['above_0.20']} above +0.20")
    if not record["seed_set"]:
        print("      (no depth field was obtained — nothing to rank)")
    for row in record["seed_set"][:12]:
        print(f"    {row['separation']:+.3f}  {row['post_id'][-8:]}  "
              f"{row['inner_region_id'][:30]:<30} in {row['outer_region_id'][:26]:<26}")
        print(f"            nesting idx {row['nesting_index']:.3f} on masks · depth "
              f"{row['inner_depth']:.3f} vs {row['outer_depth']:.3f} · "
              f"frame behind {row['inner_frame_rank']:.0%} vs {row['outer_frame_rank']:.0%}")

    print(f"\n  posts unchanged: {record['posts_unchanged']}   nothing written")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--posts", type=int, default=0, help="bound on posts scanned; 0 = all")
    ap.add_argument("--loci", type=int, default=12, help="masked loci per post")
    ap.add_argument("--seeds", type=int, default=8, help="ranked pairs kept per post")
    ap.add_argument("--depth", dest="depth", action="store_true", default=True)
    ap.add_argument("--no-depth", dest="depth", action="store_false",
                    help="skip the model-backed body; §3 is then empty and the report says so")
    ap.add_argument("--chroma", dest="chroma", action="store_true", default=True)
    ap.add_argument("--no-chroma", dest="chroma", action="store_false")
    ap.add_argument("--state", default="",
                    help="checkpoint the record to this path after every post, so a dropped "
                         "connection does not cost the depth pass")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    record = asyncio.run(sweep(args))
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        _print(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
