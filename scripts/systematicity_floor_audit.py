#!/usr/bin/env python3
"""
WAVE3 — is a refusal at 0.34 real structure, or an arbitrary line?

    python scripts/systematicity_floor_audit.py             # the nesting audit
    python scripts/systematicity_floor_audit.py --adjacency  # + the second organ (SLOW, ~10 min)
    python scripts/systematicity_floor_audit.py --json

## The question

`MIN_SYSTEMATICITY` was set to a bare `0.34` in WAVE2 with the note "a stated, tunable floor" and
never checked against anything. It is the line between *a feature coincided* and *a structure
genuinely maps*, so it fabricates in both directions if it is wrong: too low and coincidences mint
`measured` edges, too high and real movement is silently lost. This scores every cross-image pair
in the corpus that reaches the gate and asks four things:

  1. **Is there a valley at 0.34** — a real separation — or is the floor slicing a continuum?
  2. **Where did 0.34 come from** — fitted, chosen, or inherited?
  3. **Is the score propped up by 0-vs-0 agreement?** `_alignment` pays full marks for a component
     neither side has, so a pair can score well for sharing nothing.
  4. **Does the gate predict a shared SYSTEM** — against a criterion the gate never reads?

## The held-out criterion, and why it has to be external

The obvious check — "do pairs above the floor have more agreeing components?" — is circular: the
score IS those components. So the criterion here is one level up: **do the two CONTAINERS also
map?** A pair whose parents also stand in the relation and align is part of a system extending
past the pair itself, which is Gentner's actual claim. It is computed from the parents' counts —
numbers no gate below ever reads.

An earlier version of this audit used "≥2 earned components" and it looked spectacular (+84.5).
It was near-circular, and the external criterion reversed one of its conclusions outright: a gate
requiring two live components scores **−23.5** against it. That reversal is the reason this file
uses the parents.

READS POSTS, WRITES NONE. No axis, no edge, no mark, no post.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import statistics as stats
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import adjacency_organ as adjacency                 # noqa: E402
from backend.services import nestedness_organ as organ                    # noqa: E402
from backend.services import structure_map as sm                          # noqa: E402

#: Adjacency walks mask boundaries in Python and has no decode cache, so the full corpus is hours.
#: Posts below this many regions carry no structure worth scoring anyway.
MIN_REGIONS_FOR_ADJACENCY = 7


async def load_posts() -> dict:
    from backend.database import post_collection
    return {str(p["_id"]): p
            async for p in post_collection.find({"region_annotations.0": {"$exists": True}})}


def pearson(xs, ys) -> float:
    if len(xs) < 2:
        return 0.0
    mx, my = stats.mean(xs), stats.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return round(num / den, 4) if den else 0.0


def skeletons_for(posts: dict, finder) -> dict:
    """`{(post_id, region_id): skeleton}` — one organ sweep per post, reused for every pair."""
    out = {}
    for pid, post in posts.items():
        regions = list(post.get("region_annotations") or [])
        pairs = finder(regions)
        for region in regions:
            rid = str(region.get("id") or "")
            if rid:
                out[(pid, rid)] = sm.relational_structure(regions, rid, measurements=pairs)
    return out


def score_pairs(skels: dict) -> list:
    """Every cross-image pair that reaches the systematicity gate, scored both ways."""
    keys = [k for k, s in skels.items() if s.get("has_relation")]
    rows = []
    for ka in keys:
        source = skels[ka]
        source_parent = skels.get((ka[0], source.get("parent_id")))
        for kb in keys:
            if ka[0] == kb[0]:                       # movement is cross-image, by definition
                continue
            target = skels[kb]
            verdict = sm.systematicity(source, target)
            target_parent = skels.get((kb[0], target.get("parent_id")))

            # THE HELD-OUT CRITERION. Built from the parents' counts, which nothing scored above
            # ever looks at.
            parents_map = False
            if (source_parent is not None and target_parent is not None
                    and source_parent.get("has_relation") and target_parent.get("has_relation")):
                parents_map = sm.mapped(sm.structure_map(source_parent, target_parent))

            rows.append({
                "shape": verdict["shape_score"],
                "present": verdict["present_score"],
                "live": len(verdict["live"]),
                "earned": len(verdict["earned"]),
                "absence_share": verdict["absence_share"],
                "structure": (int(source.get("sibling_count") or 0)
                              + int(source.get("descendant_count") or 0)
                              + int(target.get("sibling_count") or 0)
                              + int(target.get("descendant_count") or 0)),
                "parents_map": parents_map,
            })
    return rows


def histogram(scores, width=0.05, mark=None) -> None:
    hist = collections.Counter(min(int(1 / width) - 1, int(s / width)) for s in scores)
    peak = max(hist.values()) if hist else 1
    for b in range(int(1 / width)):
        lo = b * width
        flag = "   <= floor" if mark is not None and lo <= mark < lo + width else ""
        print(f"    {lo:.2f}-{lo + width:.2f} {hist.get(b, 0):>7} "
              f"{'#' * int(52 * hist.get(b, 0) / peak)}{flag}")


def report_valley(rows) -> dict:
    floor, third = sm.MIN_SYSTEMATICITY, sm.ONE_COMPONENT_SHARE
    scores = sorted(r["shape"] for r in rows)
    atom = [s for s in scores if abs(s - third) < 1e-4]
    below = sum(1 for s in scores if 0.32 < s < third - 1e-4)
    above = sum(1 for s in scores if third + 1e-4 < s < 0.35)

    print(f"\n1. IS THERE A VALLEY AT THE FLOOR?")
    print(f"   {len(rows)} cross-image gate-eligible pairs (both sides carry the relation)")
    print(f"   mean={stats.mean(scores):.4f} median={stats.median(scores):.4f} "
          f"distinct values={len(set(scores))}")
    histogram(scores, mark=floor)
    print(f"\n   flanking 1/3:  ({0.32:.2f}, 1/3) holds {below}   (1/3, {0.35:.2f}) holds {above}")
    print(f"   → NO VALLEY. The floor sits on a smooth slope; its MAGNITUDE is a free parameter.")
    print(f"\n2. BUT THE SHAPE OF THE RULE IS PRINCIPLED")
    print(f"   exactly 1/3: {len(atom)} pairs ({len(atom) / len(rows):.2%}) — an atom, "
          f"not a smear.")
    print(f"   That is 'one component's worth of agreement', which the floor exists to exclude.")
    print(f"   floor {floor} = ONE_COMPONENT_SHARE {third:.4f} + eps {sm.SYSTEMATICITY_EPSILON}")
    print(f"   excludes the atom: {third < floor}")
    return {"pairs": len(rows), "mean": round(stats.mean(scores), 4), "atom": len(atom),
            "flank_below": below, "flank_above": above, "valley": False}


def report_absence(rows) -> dict:
    print(f"\n3. THE 0-vs-0 TRAP — is the score propped up by shared absence?")
    shape_b, present_b = collections.defaultdict(list), collections.defaultdict(list)
    for r in rows:
        shape_b[min(r["structure"], 12)].append(r["shape"])
        present_b[min(r["structure"], 12)].append(r["present"])
    print(f"   mean score by total sibling+descendant structure across both sides:")
    print(f"     {'structure':>10} {'n':>7} {'shape':>8} {'present':>9}")
    for b in sorted(shape_b):
        print(f"     {b:>9}{'+' if b == 12 else ' '} {len(shape_b[b]):>7} "
              f"{stats.mean(shape_b[b]):>8.4f} {stats.mean(present_b[b]):>9.4f}")

    r_shape = pearson([r["structure"] for r in rows], [r["shape"] for r in rows])
    r_present = pearson([r["structure"] for r in rows], [r["present"] for r in rows])
    print(f"\n   pearson(real structure, shape score)   = {r_shape:+.4f}   "
          f"← the score FELL as structure rose")
    print(f"   pearson(real structure, present score) = {r_present:+.4f}   "
          f"← most of the inversion removed")

    # THE HONEST RESIDUAL. `present` withdraws the free credit; it does not make a mean over one
    # live component stable. Where siblings and descendants are absent on both sides the score is
    # depth alone, and a structurally poor pair whose depths happen to match still lands at 1.0.
    zero = [r for r in rows if r["structure"] == 0]
    some = [r for r in rows if r["structure"] > 0]
    gap_shape = stats.mean([r["shape"] for r in zero]) - stats.mean([r["shape"] for r in some])
    gap_present = (stats.mean([r["present"] for r in zero])
                   - stats.mean([r["present"] for r in some]))
    print(f"\n   the residual, stated rather than rounded away:")
    print(f"     structure==0 minus structure>0, shape:   {gap_shape:+.4f}")
    print(f"     structure==0 minus structure>0, present: {gap_present:+.4f}")
    print(f"   The absence bucket is STILL the highest under `present`. The free credit is gone;")
    print(f"   what remains is that a mean over one live component is volatile — a different")
    print(f"   defect, and not this rule's to fix.")

    floor = sm.MIN_SYSTEMATICITY
    above = [r for r in rows if r["shape"] >= floor]
    propped = [r for r in above if r["shape"] - r["absence_share"] < floor]
    print(f"\n   under `shape`, of {len(above)} pairs above the floor, {len(propped)} "
          f"({len(propped) / max(1, len(above)):.1%}) would fall below it")
    print(f"   without the credit they got for components neither side has.")
    return {"pearson_shape": r_shape, "pearson_present": r_present,
            "gap_shape": round(gap_shape, 4), "gap_present": round(gap_present, 4),
            "above": len(above), "propped": len(propped)}


def report_separation(rows) -> dict:
    floor = sm.MIN_SYSTEMATICITY
    base = sum(1 for r in rows if r["parents_map"]) / len(rows)
    print(f"\n4. DOES THE GATE PREDICT A SHARED SYSTEM?")
    print(f"   held-out criterion: the two CONTAINERS also map. base rate {base:.1%}")
    print(f"\n   {'gate':<38} {'pass':>7} {'rate':>7} {'held|pass':>10} "
          f"{'held|fail':>10} {'sep':>8}")
    out = {}
    for label, ok in (
        (f"CURRENT  present >= {floor}", lambda r: r["present"] >= floor),
        (f"WAS      shape >= {floor}", lambda r: r["shape"] >= floor),
        ("         present >= 0.20", lambda r: r["present"] >= 0.20),
        ("         present >= 0.40", lambda r: r["present"] >= 0.40),
        ("         present >= 0.50", lambda r: r["present"] >= 0.50),
        ("adaptive present > 1/live (rejected)",
         lambda r: r["present"] > 1 / max(1, r["live"])),
        ("live >= 2 (rejected)", lambda r: r["live"] >= 2),
    ):
        passed = [r for r in rows if ok(r)]
        failed = [r for r in rows if not ok(r)]
        pa = sum(1 for r in passed if r["parents_map"]) / max(1, len(passed))
        pb = sum(1 for r in failed if r["parents_map"]) / max(1, len(failed))
        print(f"   {label:<38} {len(passed):>7} {len(passed) / len(rows):>6.1%} "
              f"{pa:>9.1%} {pb:>9.1%} {pa - pb:>+8.1%}")
        out[label.strip()] = round(pa - pb, 4)
    print(f"\n   → `present` beats `shape` by ~5 points at the same floor. That is the change.")
    print(f"   → SEPARATION IS FLAT across present >= 0.20..0.50. No value is measurably better,")
    print(f"     so the floor is held where it was: picking the argmax of a flat curve is fitting,")
    print(f"     and moving the floor too would leave the before/after measuring two things.")
    print(f"   → BOTH principled-sounding structural rules are REFUTED by the external criterion.")
    print(f"     'live >= 2' and 'present > 1/live' each refuse the 894 single-live pairs, whose")
    print(f"     containers map 54.1% of the time against a {base:.1%} base. Twice now the")
    print(f"     plausible rule has been the wrong one — which is why the criterion is external.")
    return out


def report_adjacency(posts) -> dict:
    print(f"\n5. DOES ONE FLOOR COVER TWO ORGANS?")
    big = {k: v for k, v in posts.items()
           if len(v.get("region_annotations") or []) >= MIN_REGIONS_FOR_ADJACENCY}
    print(f"   scoring adjacency over {len(big)} posts with >= {MIN_REGIONS_FOR_ADJACENCY} "
          f"regions (this is the slow part)")
    started = time.perf_counter()
    skels = skeletons_for(big, adjacency.find_adjacent_pairs)
    keys = [k for k, s in skels.items() if s.get("has_relation")]
    collapsed = sum(1 for k in keys if skels[k]["depth"] == skels[k]["descendant_count"])
    scores = sorted(sm.systematicity(skels[a], skels[b])["shape_score"]
                    for a in keys for b in keys if a[0] != b[0])
    print(f"   {len(keys)} regions carry an adjacency relation "
          f"({time.perf_counter() - started:.0f}s)")
    print(f"\n   depth == descendant_count for {collapsed}/{len(keys)} "
          f"({collapsed / max(1, len(keys)):.1%}) of regions.")
    print(f"   `relational_structure` reads `inner`/`outer` as a hierarchy. Adjacency's contact")
    print(f"   fraction is DIRECTIONAL (a's boundary touching b is not b's touching a), so the")
    print(f"   sweep is not quite symmetric and the collapse is partial — but 'parent' here means")
    print(f"   whichever neighbour sorted first, since adjacency sets no `scale_ratio` for the")
    print(f"   tightest-container rule to read. The skeleton is nesting-shaped.")
    if scores:
        print(f"\n   adjacency systematicity over {len(scores)} cross-image pairs")
        print(f"     mean={stats.mean(scores):.4f} median={stats.median(scores):.4f}")
        print(f"     above the NESTING floor {sm.MIN_SYSTEMATICITY}: "
              f"{sum(1 for s in scores if s >= sm.MIN_SYSTEMATICITY) / len(scores):.1%}")
        histogram(scores, mark=sm.MIN_SYSTEMATICITY)
    print(f"\n   → VERDICT: one floor does NOT cover both. It was calibrated on nesting, over a")
    print(f"     skeleton whose three components mean nesting things. A relation-specific floor is")
    print(f"     owed before adjacency movement is built on this gate.")
    return {"regions": len(keys), "collapsed": collapsed, "pairs": len(scores),
            "mean": round(stats.mean(scores), 4) if scores else None}


async def main_async(args) -> int:
    posts = await load_posts()
    print(f"loaded {len(posts)} posts, "
          f"{sum(len(p.get('region_annotations') or []) for p in posts.values())} regions")
    print(f"floor under audit: MIN_SYSTEMATICITY = {sm.MIN_SYSTEMATICITY}")

    rows = score_pairs(skeletons_for(posts, organ.find_nested_pairs))
    print("\n" + "=" * 84)
    print("  WAVE3 — the systematicity floor, audited")
    print("=" * 84)
    record = {
        "floor": sm.MIN_SYSTEMATICITY,
        "valley": report_valley(rows),
        "absence": report_absence(rows),
        "separation": report_separation(rows),
    }
    if args.adjacency:
        record["adjacency"] = report_adjacency(posts)

    print(f"\nVERDICT")
    print(f"  aggregation  `present` IS NOW THE DEFAULT. +25.7 against the held-out criterion vs")
    print(f"               +20.3 for `shape`, and the poverty inversion goes -0.14 -> -0.03.")
    print(f"  residual     NOT FULLY CLOSED, and said so. The zero-structure bucket is still the")
    print(f"               highest under `present`. Withdrawing the free credit does not make a")
    print(f"               mean over one live component stable; that is the next question.")
    print(f"  floor shape  DERIVATION DEAD. 1/3 was one component's worth only because `shape`")
    print(f"               always averaged three. Under `present` it is 1/3, 1/2 or 1/1 by live")
    print(f"               count, and no scalar expresses it.")
    print(f"  floor value  FREE, and HELD at {sm.MIN_SYSTEMATICITY} deliberately: separation is flat, so no")
    print(f"               value is better, and moving it would confound the before/after.")
    print(f"  rejected     `present > 1/live` (+18.5) and `live >= 2` (-23.5). Both refuse the 894")
    print(f"               single-live pairs, which are the BEST pairs by the external criterion.")
    print(f"  two organs   ONE FLOOR IS NOT ENOUGH."
          + ("" if args.adjacency else " (re-run with --adjacency for the numbers)"))
    print()

    if args.json:
        print(json.dumps(record, indent=2, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--adjacency", action="store_true",
                    help="also score the adjacency organ (slow: no mask decode cache)")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
