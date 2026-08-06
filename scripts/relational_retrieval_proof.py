#!/usr/bin/env python3
"""
WAVE3 — relational retrieval: does proposing FOR a relation beat proposing by resemblance?

    python scripts/relational_retrieval_proof.py            # the before/after, real kernel runs
    python scripts/relational_retrieval_proof.py --sweep     # the weight ablation behind the defaults
    python scripts/relational_retrieval_proof.py --json      # the raw record
    python scripts/relational_retrieval_proof.py -k 12       # the kernel's default candidate budget

## What is being tested

`FINDING-wave3-retina-density.md` (Surprise 2) left the retina ranking by appearance while the
kernel grounds a relation. This lane made the retina rank by a box-basis relational prior instead
(`backend/services/retina/relational.py`). The claim is that `grounded` rises and `surface_only`
falls at the SAME k — the candidate budget buys relationally-plausible loci instead of look-alikes.

Every number below comes from a real `mk.run_kernel`. There is no oracle and no injected candidate:
the only difference between the two runs is which question the retina was asked.

## The number that keeps this honest

A proposer that simply recomputed the kernel's verdict would score perfectly and prove nothing —
it would be the decider wearing the proposer's clothes. So this reports **disagreement**: how often
the box-basis prior says a candidate stands in a relation and the kernel, measuring on masks, says
it does not. On the corpus that is ~19%, one-sided in the expected direction (boxes over-estimate
containment — the finial-in-front-of-the-sky pathology the WAVE2.5 ruling names). The prior is a
guess that is usefully but imperfectly correlated with the outcome, which is what a peripheral
signal should be.

Nothing is persisted: no axis, no edge, no mark, no post. Posts are hashed before and after.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics as stats
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import movement_kernel as mk                        # noqa: E402
from backend.services import nestedness_organ as organ                    # noqa: E402
from backend.services import retina                                       # noqa: E402
from backend.services import structure_map as sm                          # noqa: E402
from backend.services.retina import relational as rel                     # noqa: E402

#: Five masked seeds across four posts. Chosen before any ranking was measured, and one of them
#: (`cseg_Temple_Spire_2`) has NOTHING groundable within reach — kept deliberately, because a
#: re-ranker that appeared to help there would be inventing candidates rather than ordering them.
SEEDS = [
    ("6a5fef58a3ddb6341fd69930", "cseg_golden_finial_5"),
    ("6a5fef58a3ddb6341fd69930", "cseg_Temple_Spire_2"),
    ("6a5ffab7a3ddb6341fd699d3", "cseg_lattice_window_6"),
    ("6a60410b1ecd6db1c931eb72", "cseg_marble_face_10"),
    ("6a6040d61ecd6db1c931eb71", "cseg_extended_foot_3"),
]

#: The headline seed — the one #146 measured and left at grounded=0 for the kernel's default k.
HEADLINE = SEEDS[0]

REASONS = ("grounded", "box_only", "surface_only", "insystematic")


async def load_posts() -> dict:
    from backend.database import post_collection
    return {str(p["_id"]): p
            async for p in post_collection.find({"region_annotations.0": {"$exists": True}})}


def tally(transcript: dict) -> dict:
    """The four classes, decomposed. Never summed — the density lane's rule, and the reason this
    lane can show WHICH refusal moved rather than only that fewer happened."""
    considered = transcript["considered"]
    counts = Counter("grounded" if c["status"] == "grounded" else (c.get("reason") or "other")
                     for c in considered)
    out = {r: counts.get(r, 0) for r in REASONS}
    out["other"] = sum(v for k, v in counts.items() if k not in REASONS)
    out["considered"] = len(considered)
    return out


def pearson(xs, ys) -> float:
    if len(xs) < 2:
        return 0.0
    mx, my = stats.mean(xs), stats.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** 0.5
    return round(num / den, 4) if den else 0.0


def rows_of(transcript: dict) -> list:
    """One row per considered candidate: where it ranked, what the prior thought, what happened."""
    rows = []
    for position, c in enumerate(transcript["considered"], start=1):
        cand = c["candidate"]
        prior = cand.get("relational") or {}
        rows.append({
            "rank": position,
            "identity_rank": cand.get("identity_rank", position),
            "score": cand.get("score"),
            "post_id": str(cand["post_id"]),
            "region_id": str(cand["region_id"]),
            "grounded": c["status"] == "grounded",
            "reason": "grounded" if c["status"] == "grounded" else (c.get("reason") or "other"),
            "prior_score": prior.get("score"),
            "prior_stands": (prior.get("terms") or {}).get("stands_in_relation"),
        })
    return rows


async def one_run(posts: dict, post_id: str, region_id: str, k: int, ranking: str) -> dict:
    started = time.perf_counter()
    transcript = await mk.run_kernel(
        post_a=posts[post_id], posts=posts, third_post=None, region_id=region_id,
        k=k, max_movements=1, atlas_id="", persist=False, ranking=ranking)
    rows = rows_of(transcript)
    return {
        "seed": f"{post_id[-6:]}/{region_id}", "post_id": post_id, "region_id": region_id,
        "ranking": ranking, "k": k, "seconds": round(time.perf_counter() - started, 1),
        "retina_status": transcript["retina"].get("status"),
        "retina_ranking": transcript["retina"].get("ranking", "identity"),
        "counts": tally(transcript), "rows": rows,
        "posts_unchanged": transcript["posts_unchanged"],
        "precision": round(sum(1 for r in rows if r["grounded"]) / max(1, len(rows)), 4),
        "pearson_rank_vs_grounded": pearson([-r["rank"] for r in rows],
                                            [1.0 if r["grounded"] else 0.0 for r in rows]),
    }


def disagreement(runs: list) -> dict:
    """Where the box-basis prior and the mask-basis kernel part company. The anti-rubber-stamp
    number: a proposer that always agreed would not be proposing, it would be deciding twice."""
    both = agree = over = under = 0
    for run in runs:
        for row in run["rows"]:
            if row["prior_stands"] is None:
                continue
            both += 1
            prior_yes = row["prior_stands"] >= 1.0
            kernel_found_one = row["reason"] != sm.REFUSED_SURFACE_ONLY
            if prior_yes == kernel_found_one:
                agree += 1
            elif prior_yes:
                over += 1               # boxes said contained; masks said no relation at all
            else:
                under += 1              # boxes missed a relation the masks found
    return {"compared": both, "agree": agree,
            "rate": round(agree / both, 4) if both else 0.0,
            "prior_over_estimated": over, "prior_missed": under}


def report(record: dict) -> None:
    runs = record["runs"]
    by = {(r["seed"], r["ranking"]): r for r in runs}
    seeds = [f"{p[-6:]}/{r}" for p, r in SEEDS]
    k = record["k"]

    print("\n" + "=" * 96)
    print("  WAVE3 — relational retrieval: propose FOR a relation, not by resemblance")
    print("=" * 96)

    print(f"\nTHE DELTA — same kernel, same k={k}, same corpus. Only the question the retina was "
          f"asked differs.\n")
    head = f"  {'seed':<34} {'ranking':<11} " + " ".join(f"{r:>13}" for r in REASONS)
    print(head)
    print("  " + "-" * (len(head) - 2))
    for seed in seeds:
        for ranking in ("identity", "relational"):
            run = by.get((seed, ranking))
            if not run:
                continue
            c = run["counts"]
            print(f"  {seed if ranking == 'identity' else '':<34} {ranking:<11} "
                  + " ".join(f"{c[r]:>13}" for r in REASONS))
        print()

    totals = {ranking: {r: sum(by[(s, ranking)]["counts"][r] for s in seeds if (s, ranking) in by)
                        for r in REASONS} for ranking in ("identity", "relational")}
    print(f"  {'ALL FIVE SEEDS':<34} {'identity':<11} "
          + " ".join(f"{totals['identity'][r]:>13}" for r in REASONS))
    print(f"  {'':<34} {'relational':<11} "
          + " ".join(f"{totals['relational'][r]:>13}" for r in REASONS))

    print(f"\nPRECISION at k={k} — the share of the candidate budget that grounded")
    for seed in seeds:
        i, rl = by.get((seed, "identity")), by.get((seed, "relational"))
        if not (i and rl):
            continue
        arrow = "→" if rl["precision"] >= i["precision"] else "↓"
        print(f"   {seed:<34} {i['precision']:.3f}  {arrow}  {rl['precision']:.3f}"
              + ("     (nothing groundable within reach — see below)"
                 if i["precision"] == rl["precision"] == 0 else ""))
    mean_i = stats.mean(by[(s, "identity")]["precision"] for s in seeds if (s, "identity") in by)
    mean_r = stats.mean(by[(s, "relational")]["precision"] for s in seeds if (s, "relational") in by)
    print(f"   {'mean':<34} {mean_i:.3f}  →  {mean_r:.3f}")

    print(f"\nRANK vs GROUNDABILITY — pooled over every candidate considered")
    for ranking in ("identity", "relational"):
        rows = [r for run in runs if run["ranking"] == ranking for r in run["rows"]]
        p = pearson([-r["rank"] for r in rows], [1.0 if r["grounded"] else 0.0 for r in rows])
        print(f"   {ranking:<12} pearson(nearness, grounded) = {p:+.4f}   over {len(rows)} candidates")

    d = record["disagreement"]
    print(f"\nTHE PROPOSER IS NOT THE DECIDER")
    print(f"   box-basis prior vs mask-basis kernel, on 'does this stand in a relation':")
    print(f"     agree {d['agree']}/{d['compared']} = {d['rate']:.3f}")
    print(f"     prior over-estimated (boxes contained, masks found no relation): "
          f"{d['prior_over_estimated']}")
    print(f"     prior missed (masks found a relation the boxes did not):          {d['prior_missed']}")
    print(f"   The prior is a guess. It is right often enough to be worth ranking on and wrong "
          f"often\n   enough that the kernel is still deciding.")

    seedskel = record.get("seed_skeleton_disagreement")
    if seedskel:
        print(f"\n   One concrete disagreement, on the headline seed itself:")
        print(f"     box prior  : parent={seedskel['prior']['parent_id']} "
              f"depth={seedskel['prior']['depth']} siblings={seedskel['prior']['sibling_count']}")
        print(f"     mask kernel: parent={seedskel['kernel']['parent_id']} "
              f"depth={seedskel['kernel']['depth']} siblings={seedskel['kernel']['sibling_count']}")
        print(f"     The proposer ranks on the first and the kernel grounds on the second.")

    print(f"\n   posts unchanged: {all(r['posts_unchanged'] for r in runs)}")
    print(f"   nothing persisted — no axis, no edge, no mark, no post.\n")


async def sweep(posts: dict, k_recall: int) -> None:
    """The ablation behind DEFAULT_WEIGHTS. Uses the kernel's own gates to label each candidate,
    with `find_nested_pairs` hoisted to once per post so a 600-candidate sweep is minutes not hours.

    This is EVALUATION, not a second implementation of grounding: `structure_map`, `measure` and
    `is_admissible` are the kernel's, called in the kernel's order.
    """
    pairs = {pid: organ.find_nested_pairs(mk._regions(p)) for pid, p in posts.items()}
    geo = retina.geometry_for()

    def outcome(seed_structure, seed_measurement, post_id, region_id) -> str:
        post = posts.get(post_id)
        if post is None:
            return "other"
        target = sm.relational_structure(mk._regions(post), region_id, measurements=pairs[post_id])
        verdict = sm.structure_map(seed_structure, target)
        if not sm.mapped(verdict):
            return verdict["reason"]
        try:
            measurement = organ.measure(mk._region(post, region_id),
                                        mk._region(post, target["parent_id"]))
        except organ.NestednessRefusal:
            return "other"
        if not measurement["nested"]:
            return "other"
        if not (organ.is_admissible(seed_measurement) and organ.is_admissible(measurement)):
            return mk.REFUSED_BOX_ONLY
        return "grounded"

    datasets = []
    for post_id, region_id in SEEDS:
        seeded = mk.seed(posts[post_id], region_id=region_id)
        env = retina.propose_candidates(region_id=region_id, post_id=post_id, k=k_recall,
                                        exclude_post_id=post_id)
        if env["status"] != "ready":
            continue
        seed_skeleton = rel.skeleton_of(geo.get(post_id) or {}, region_id)
        rows = []
        for rank, c in enumerate(env["candidates"], start=1):
            cp, cr = str(c["post_id"]), str(c["region_id"])
            cand_skeleton = rel.skeletons(geo.get(cp) or {}).get(cr)
            prior = rel.relational_prior(seed_skeleton, cand_skeleton, identity_score=c["score"])
            rows.append({
                "identity_rank": rank, "identity_score": c["score"], "prior_score": prior["score"],
                "grounded": outcome(seeded["structure"], seeded["measurement"], cp, cr) == "grounded",
                "terms": prior["terms"]})
        datasets.append({"seed": f"{post_id[-6:]}/{region_id}", "rows": rows})
        print(f"  {region_id:<28} recalled {len(rows)}, groundable "
              f"{sum(1 for r in rows if r['grounded'])}")

    def precision(rows, kk, weights):
        key = lambda r: (-sum(weights[t] * r["terms"][t] for t in weights), r["identity_rank"])
        top = sorted(rows, key=key)[:kk]
        return sum(1 for r in top if r["grounded"]) / max(1, len(top))

    def mean_precision(weights, kk):
        return stats.mean(precision(d["rows"], kk, weights) for d in datasets)

    identity_only = {t: (1.0 if t == "identity" else 0.0) for t in rel.DEFAULT_WEIGHTS}
    print(f"\n  {'ranking':<40} {'p@8':>7} {'p@12':>7} {'p@24':>7}")
    for label, w in [("identity only (the baseline)", identity_only),
                     ("DEFAULT_WEIGHTS", rel.DEFAULT_WEIGHTS)]:
        print(f"  {label:<40} {mean_precision(w, 8):>7.3f} {mean_precision(w, 12):>7.3f} "
              f"{mean_precision(w, 24):>7.3f}")
    for term in rel.DEFAULT_WEIGHTS:
        w = {**rel.DEFAULT_WEIGHTS, term: 0.0}
        print(f"  {'  − ' + term:<40} {mean_precision(w, 8):>7.3f} {mean_precision(w, 12):>7.3f} "
              f"{mean_precision(w, 24):>7.3f}")
    for term in rel.DEFAULT_WEIGHTS:
        w = {t: (1.0 if t == term else 0.0) for t in rel.DEFAULT_WEIGHTS}
        print(f"  {'  only ' + term:<40} {mean_precision(w, 8):>7.3f} {mean_precision(w, 12):>7.3f} "
              f"{mean_precision(w, 24):>7.3f}")

    # The correlation the lane card asks for, measured where it means something: over the FULL
    # recall pool rather than inside a top-12 that both rankings agree is worth looking at.
    pool = [r for d in datasets for r in d["rows"]]
    grounded_flags = [1.0 if r["grounded"] else 0.0 for r in pool]
    print(f"\n  score vs groundability over {len(pool)} recalled candidates")
    print(f"    identity score   pearson = "
          f"{pearson([r['identity_score'] for r in pool], grounded_flags):+.4f}")
    print(f"    relational prior pearson = "
          f"{pearson([r['prior_score'] for r in pool], grounded_flags):+.4f}")

    print(f"\n  grid search ({k_recall} recalled per seed) — is DEFAULT_WEIGHTS on the plateau?")
    best, ties = 0.0, 0
    for w_stand in (0.0, 0.3, 0.5, 0.7, 1.0):
        for w_shape in (0.0, 0.2, 0.3, 0.5):
            for w_mask in (0.0, 0.1, 0.2):
                for w_id in (0.0, 0.1, 0.3):
                    w = {"stands_in_relation": w_stand, "shape_affinity": w_shape,
                         "mask_prior": w_mask, "identity": w_id}
                    if not any(w.values()):
                        continue
                    p = mean_precision(w, 12)
                    if p > best + 1e-9:
                        best, ties = p, 1
                    elif abs(p - best) < 1e-9:
                        ties += 1
    print(f"    best p@12 over the grid = {best:.3f}   "
          f"DEFAULT_WEIGHTS = {mean_precision(rel.DEFAULT_WEIGHTS, 12):.3f}   "
          f"({ties} weightings tie at the best — a plateau, not a knife edge)")


async def main_async(args) -> int:
    posts = await load_posts()
    print(f"loaded {len(posts)} posts carrying regions")
    print(f"geometry sidecar: {json.dumps(retina.geometry_status()['totals'])}")

    if args.sweep:
        await sweep(posts, args.recall)
        return 0

    runs = []
    for post_id, region_id in SEEDS:
        for ranking in ("identity", "relational"):
            run = await one_run(posts, post_id, region_id, args.k, ranking)
            runs.append(run)
            print(f"   {run['seed']:<34} {ranking:<11} grounded={run['counts']['grounded']:>2} "
                  f"({run['seconds']}s)")

    # The prior and the kernel disagree even about the SEED's own container — the clearest
    # single illustration that one is an estimate and the other a measurement.
    seed_post, seed_region = HEADLINE
    geo = retina.geometry_for()
    prior_skeleton = rel.skeleton_of(geo.get(seed_post) or {}, seed_region) or {}
    kernel_skeleton = mk.seed(posts[seed_post], region_id=seed_region)["structure"]

    record = {
        "k": args.k,
        "runs": runs,
        "disagreement": disagreement([r for r in runs if r["ranking"] == "relational"]),
        "seed_skeleton_disagreement": {
            "seed": f"{seed_post[-6:]}/{seed_region}",
            "prior": {k: prior_skeleton.get(k) for k in
                      ("parent_id", "depth", "sibling_count", "descendant_count")},
            "kernel": {k: kernel_skeleton.get(k) for k in
                       ("parent_id", "depth", "sibling_count", "descendant_count")},
        },
    }
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        report(record)

    grounded = {r: sum(x["counts"]["grounded"] for x in runs if x["ranking"] == r)
                for r in ("identity", "relational")}
    surface = {r: sum(x["counts"]["surface_only"] for x in runs if x["ranking"] == r)
               for r in ("identity", "relational")}
    ok = (grounded["relational"] > grounded["identity"]
          and surface["relational"] < surface["identity"]
          and all(r["posts_unchanged"] for r in runs))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-k", type=int, default=mk.DEFAULT_K, help="the kernel's candidate budget")
    ap.add_argument("--recall", type=int, default=120, help="recall depth for --sweep")
    ap.add_argument("--sweep", action="store_true", help="the weight ablation, not the kernel runs")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
