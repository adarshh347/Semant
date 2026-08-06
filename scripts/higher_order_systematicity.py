#!/usr/bin/env python3
"""
WAVE3 — does higher-order structure beat flat systematicity? Judged by a criterion it cannot read.

    python scripts/higher_order_systematicity.py                 # the sweep and the verdict
    python scripts/higher_order_systematicity.py --rebuild-cache  # re-derive the adjacency cache
    python scripts/higher_order_systematicity.py --json

## Why a NEW criterion was necessary

#155 and #156 judged the systematicity score by asking *"do the two containers also map?"*. This
lane internalizes exactly that — higher-order structure IS container correspondence — so using it
again would score the change against itself. #155 already showed what that costs: a circular
criterion rated `live >= 2` at **+84.5**, and against an external one the same gate scored
**-23.5**, backwards.

There is a second reason, and it qualifies the earlier lanes rather than this one. The containers
criterion is computed by calling `structure_map` one level up — external in its INPUTS (the
parents' counts) but not in its FUNCTIONAL FORM. A rule that favours structure-poor skeletons will
also favour structure-poor parents, so it can validate itself. The fingerprint is visible in the
data: `pearson(structure, containers-map) = -0.20`, and the 894 single-live pairs "validate" at
54.1% against a 30.8% base. Some of that is real; some of it is the criterion agreeing with the
bias it was asked to detect. A criterion that shares a scoring function cannot detect a shared bias.

## The fresh criterion — CONTACT AGREEMENT

    Does each part MEET the boundary of its own container?

Measured by `adjacency_organ`: for the nesting pair (a in A, b in B), is `a` adjacent to its
container, and is `b` adjacent to its container? The criterion holds when BOTH do.

Why this one:

  · **A different organ.** Boundary contact, not containment. `structure_map` never imports
    `adjacency_organ`, never reads a contact fraction, and cannot: a test scans the module.
  · **No shared functional form.** It does not call `structure_map` at any level, so it cannot
    inherit the bias it is judging — the flaw in the containers criterion.
  · **It is a real relational property.** A finial welded to its spire and a finial floating in a
    niche are different KINDS of nesting. Two nestings that are genuinely analogous should agree.
  · **Positive agreement only.** Both-touch, not both-agree — because "neither touches" is a shared
    absence, and crediting that is the exact mistake `present` was introduced to stop.

The criterion is sanity-checked before it is trusted: if `present` cannot separate on it at all,
it is uninformative rather than a better judge, and that is reported instead of a verdict.

READS POSTS, WRITES NONE — except a derived adjacency cache under `data/`, gitignored, rebuildable.
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
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import adjacency_organ as adjacency                 # noqa: E402
from backend.services import nestedness_organ as organ                    # noqa: E402
from backend.services import structure_map as sm                          # noqa: E402

#: Derived, rebuildable, gitignored — the same terms as the retina index. Adjacency walks mask
#: boundaries in Python with no decode cache, so the corpus is ~25 minutes; it is computed once.
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "adjacency_contacts.json"

#: The weights swept. 0.0 is `present` exactly — the null this lane has to beat.
WEIGHTS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0)


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


async def build_contact_cache(posts: dict) -> dict:
    """`{post_id: [[a, b], ...]}` — every measured adjacency, as unordered pairs."""
    out, started = {}, time.perf_counter()
    for pid, post in posts.items():
        regions = list(post.get("region_annotations") or [])
        if len(regions) < 2:
            out[pid] = []
            continue
        rows = adjacency.find_adjacent_pairs(regions)
        out[pid] = sorted({tuple(sorted((str(m["inner_region_id"]), str(m["outer_region_id"]))))
                           for m in rows})
        print(f"   {pid[-6:]}: {len(regions):>4} regions → {len(out[pid]):>4} contacts "
              f"({time.perf_counter() - started:.0f}s)", flush=True)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(out))
    return out


def load_contacts(posts: dict, rebuild: bool = False):
    if not rebuild and CACHE_PATH.exists():
        raw = json.loads(CACHE_PATH.read_text())
        return {pid: {tuple(sorted(pair)) for pair in rows} for pid, rows in raw.items()}
    return None


def touches_its_container(contacts: dict, post_id: str, skeleton) -> bool:
    """Does this region meet the boundary of the container the nestedness organ gave it?

    Read off `adjacency_organ`'s measurements and nothing else. NOTE the geometric risk this
    carries: a part strictly inside a whole shares no boundary with it, so this can be rare by
    construction rather than by analogy. Its base rate is checked before any verdict rests on it.
    """
    parent_id = str(skeleton.get("parent_id") or "")
    if not parent_id:
        return False
    key = tuple(sorted((str(skeleton.get("region_id")), parent_id)))
    return key in (contacts.get(post_id) or set())


def touches_a_sibling(contacts: dict, post_id: str, skeleton) -> bool:
    """Does this region meet another part under the same container?

    A part packed against its neighbours sits differently in its whole from one isolated inside it,
    and that is a property of the NESTING, not of either region alone.
    """
    rid = str(skeleton.get("region_id"))
    post_contacts = contacts.get(post_id) or set()
    return any(tuple(sorted((rid, str(sib)))) in post_contacts
               for sib in (skeleton.get("sibling_ids") or []))


def has_any_contact(contacts: dict, post_id: str, skeleton) -> bool:
    """Does this region meet anything at all? The weakest of the three, kept because a criterion
    with a degenerate base rate proves nothing and this one is the least likely to have one."""
    rid = str(skeleton.get("region_id"))
    return any(rid in pair for pair in (contacts.get(post_id) or set()))


#: The candidate criteria, all measured by `adjacency_organ` and none of them calling
#: `structure_map`. All three are reported: if the verdict depends on which one is chosen, that is
#: itself the finding, and choosing the flattering one afterwards would be the taste-fitting every
#: lane in this sequence has been forbidden.
CRITERIA = (
    ("contact_with_container", touches_its_container),
    ("contact_with_sibling", touches_a_sibling),
    ("any_contact", has_any_contact),
)


def score_pairs(skels: dict, contacts: dict, weights=WEIGHTS) -> list:
    """Every cross-image gate-eligible pair, scored at each weight, with every fresh criterion."""
    keys = [k for k, s in skels.items() if s.get("has_relation")]
    sides = {name: {k: fn(contacts, k[0], skels[k]) for k in keys} for name, fn in CRITERIA}
    rows = []
    for ka in keys:
        source = skels[ka]
        for kb in keys:
            if ka[0] == kb[0]:
                continue
            target = skels[kb]
            base = sm.systematicity(source, target)
            scores = {w: (base["score"] if w == 0.0 else
                          sm.systematicity(source, target, higher_order_weight=w)["score"])
                      for w in weights}
            rows.append({
                "scores": scores,
                "ho_depth": base["higher_order"]["depth"],
                "live": len(base["live"]),
                "structure": (int(source.get("sibling_count") or 0)
                              + int(source.get("descendant_count") or 0)
                              + int(target.get("sibling_count") or 0)
                              + int(target.get("descendant_count") or 0)),
                # THE FRESH CRITERIA — positive agreement only: BOTH sides carry the property.
                # "Neither does" is a shared absence, and crediting that is the exact mistake
                # `present` exists to stop.
                **{name: bool(sides[name][ka] and sides[name][kb]) for name, _ in CRITERIA},
            })
    return rows


def separation(rows, weight, floor, key="contact") -> tuple:
    passed = [r for r in rows if r["scores"][weight] >= floor]
    failed = [r for r in rows if r["scores"][weight] < floor]
    if not passed or not failed:
        return len(passed), 0.0, 0.0, 0.0
    pa = sum(1 for r in passed if r[key]) / len(passed)
    pb = sum(1 for r in failed if r[key]) / len(failed)
    return len(passed), pa, pb, pa - pb


def report(rows) -> dict:
    n = len(rows)
    floor = sm.MIN_SYSTEMATICITY
    names = [name for name, _ in CRITERIA]

    print("\n" + "=" * 88)
    print("  WAVE3 — higher-order systematicity, judged by criteria it cannot read")
    print("=" * 88)

    print(f"\n1. THE FRESH CRITERIA — all measured by adjacency_organ, none calling structure_map")
    print(f"   {n} cross-image gate-eligible pairs\n")
    print(f"   {'criterion':<26} {'base rate':>10}  {'usable?':>8}")
    usable = []
    for name in names:
        base = sum(1 for r in rows if r[name]) / n
        # A criterion that almost never holds, or almost always does, cannot discriminate. That is
        # a validity check on the JUDGE, decided before any score is compared against it.
        ok = 0.02 <= base <= 0.98
        if ok:
            usable.append(name)
        print(f"   {name:<26} {base:>9.1%}  {'yes' if ok else 'DEGENERATE':>8}")
    if not usable:
        print(f"\n   ✗ every candidate criterion is degenerate. No verdict can rest on any of")
        print(f"     them, and that is the honest result rather than a number.")
        return {"usable": [], "sweep": {}, "best_weight": None, "null": None}

    print(f"\n2. IS EACH USABLE CRITERION FIT TO JUDGE? (a check on the judge, not a verdict)")
    print(f"   two ways a criterion fails before it is ever used:\n")
    print(f"   · ENTANGLED — it cannot hold for a pair with no siblings, so it is not independent")
    print(f"     of the sibling COMPONENT the score is built from.")
    print(f"   · INVERTED — `present`, a rule two lanes of evidence back, separates NEGATIVELY on")
    print(f"     it. Then a rise toward zero cannot be read as an improvement: we would not know")
    print(f"     whether the new rule is better or the judge is upside down.\n")
    single_live = [r for r in rows if r["live"] == 1]
    fit = []
    for name in usable:
        _, _, _, sep0 = separation(rows, 0.0, floor, key=name)
        on_single = (sum(1 for r in single_live if r[name]) / len(single_live)) if single_live else 0
        problems = []
        if on_single <= 0.001:
            problems.append("ENTANGLED (never holds for a sibling-less pair)")
        if sep0 < 0:
            problems.append("INVERTED")
        elif abs(sep0) < 0.03:
            problems.append("UNINFORMATIVE")
        if not problems:
            fit.append(name)
        print(f"   {name:<26} present {sep0:+.1%}, holds for {on_single:>5.1%} of single-live "
              f"pairs  {'· '.join(problems) or 'FIT'}")
    if not fit:
        print(f"\n   ✗ NO CRITERION IS FIT TO JUDGE. Every candidate is inverted or entangled, so")
        print(f"     this lane cannot certify an improvement even if one exists. That is a fact")
        print(f"     about the available evidence, and it is the result.")
    informative = fit

    print(f"\n3. THE SWEEP — does higher-order structure beat flat `present`?")
    judges = informative or usable
    header = " ".join(f"{name[:16]:>17}" for name in judges)
    print(f"   {'weight':>7} {'pass':>7} {'rate':>7} {header}")
    table = {name: {} for name in judges}
    for w in WEIGHTS:
        cnt = sum(1 for r in rows if r["scores"][w] >= floor)
        cells = []
        for name in judges:
            _, _, _, sep = separation(rows, w, floor, key=name)
            table[name][w] = sep
            cells.append(f"{sep:>+17.1%}")
        flag = "   <- the null" if w == 0.0 else ""
        print(f"   {w:>7.1f} {cnt:>7} {cnt / n:>6.1%} {' '.join(cells)}{flag}")

    print(f"\n   best weight per judge:")
    agreement = set()
    for name in judges:
        best = max(table[name], key=lambda w: table[name][w])
        agreement.add(best)
        print(f"     {name:<26} best {best} at {table[name][best]:+.1%}   "
              f"null {table[name][0.0]:+.1%}   gain {table[name][best] - table[name][0.0]:+.1%}")
    print(f"   judges agree on the best weight: {len(agreement) == 1}")

    primary = judges[0]
    best = max(table[primary], key=lambda w: table[primary][w])

    print(f"\n4. THE INVERSION — does higher-order kill the depth-only residual?")
    for w in sorted({0.0, best}):
        r = pearson([x["structure"] for x in rows], [x["scores"][w] for x in rows])
        perfect = [x for x in rows if abs(x["scores"][w] - 1.0) < 1e-9 and x["structure"] == 0]
        print(f"   weight {w}: pearson(structure, score) = {r:+.4f}; "
              f"structureless-perfect pairs = {len(perfect)}")

    print(f"\n5. THE 894 SINGLE-LIVE PAIRS — signal, per the standing decision")
    one = [r for r in rows if r["live"] == 1]
    for name in judges:
        print(f"   {name:<26} holds for {sum(1 for r in one if r[name]) / max(1, len(one)):>6.1%} "
              f"of them vs {sum(1 for r in rows if r[name]) / n:.1%} base")
    for w in sorted({0.0, best}):
        passing = sum(1 for r in one if r["scores"][w] >= floor) / max(1, len(one))
        print(f"   weight {w}: {passing:.1%} of them pass the floor")

    print(f"\n6. HOW OFTEN IS THERE HIGHER-ORDER STRUCTURE TO READ?")
    print(f"   shared ancestor rungs: "
          f"{dict(sorted(collections.Counter(r['ho_depth'] for r in rows).items()))}")

    # Independent of any criterion: does the SHAPE of the distribution recover a principled floor?
    # #155 could derive one because `shape` had an atom at 1/3; #156 lost it. Worth asking again
    # even though the term is not being adopted, because it is a fact about the score, not a claim
    # about its quality.
    print(f"\n7. WOULD HIGHER-ORDER RESTORE A PRINCIPLED FLOOR? (distribution only, no criterion)")
    for w in (0.0, 0.5, 1.0):
        scores = sorted(r["scores"][w] for r in rows)
        atoms = collections.Counter(round(s, 6) for s in scores).most_common(3)
        hist = collections.Counter(int(s / 0.05) for s in scores)
        dips = [b for b in range(1, 19)
                if hist.get(b, 0) < hist.get(b - 1, 0) and hist.get(b, 0) < hist.get(b + 1, 0)]
        print(f"   weight {w}: distinct={len(set(scores))} "
              f"top atoms={[(v, f'{c/len(scores):.1%}') for v, c in atoms]}")
        print(f"             interior dips (0.05 bins): {[round(b * 0.05, 2) for b in dips] or 'none'}")
    print(f"   -> a dip is not a valley unless it is deep and stable; read the counts, not the")
    print(f"      word. The floor stays FREE unless one of these is unmistakable.")

    return {"usable": usable, "informative": informative, "primary": primary,
            "sweep": {name: {str(k): v for k, v in t.items()} for name, t in table.items()},
            "best_weight": best, "null": table[primary][0.0],
            "best": table[primary][best]}


async def main_async(args) -> int:
    posts = await load_posts()
    contacts = load_contacts(posts, rebuild=args.rebuild_cache)
    if contacts is None:
        print(f"building the adjacency contact cache (slow, once) → {CACHE_PATH}")
        contacts = {pid: {tuple(sorted(p)) for p in rows}
                    for pid, rows in (await build_contact_cache(posts)).items()}

    skels = {}
    for pid, post in posts.items():
        regions = list(post.get("region_annotations") or [])
        pairs = organ.find_nested_pairs(regions)
        for region in regions:
            rid = str(region.get("id") or "")
            if rid:
                skels[(pid, rid)] = sm.relational_structure(regions, rid, measurements=pairs)

    rows = score_pairs(skels, contacts)
    record = report(rows)

    print(f"\nVERDICT")
    if not record.get("usable"):
        print(f"  NO VERDICT. Every candidate criterion is degenerate on this corpus, so nothing")
        print(f"  external is available to judge the change by. `HIGHER_ORDER_WEIGHT` stays 0.0:")
        print(f"  an unjudged rule is not a better rule.")
    elif not record.get("informative"):
        print(f"  NO VERDICT IS AVAILABLE, and that is the finding.")
        print(f"  Every fresh criterion is either INVERTED (`present` separates negatively on it)")
        print(f"  or ENTANGLED (it cannot hold for a sibling-less pair, so it is not independent")
        print(f"  of a component the score is built from). Higher-order structure therefore")
        print(f"  cannot be certified better, and `HIGHER_ORDER_WEIGHT` stays 0.0.")
        print(f"")
        print(f"  The larger result: the +25.7 that #156 rests on has NO independent")
        print(f"  corroboration. Its criterion calls `structure_map` one level up, and the two")
        print(f"  clean adjacency criteria point the other way. That does not overturn #156 —")
        print(f"  `present` still beat `shape` like-for-like — but it does mean the systematicity")
        print(f"  score has never been validated against anything outside its own family.")
    else:
        null, best = record["null"], record["best"]
        gain = best - null
        print(f"  judged by {record['primary']} (base rate, entanglement and inversion all checked)")
        if gain > 0.01:
            print(f"  Higher-order structure BEATS flat `present`: {best:+.1%} against the null's")
            print(f"  {null:+.1%} at weight {record['best_weight']} — a gain of {gain:+.1%}.")
        else:
            print(f"  Higher-order structure does NOT beat flat `present`: best {best:+.1%}")
            print(f"  against the null's {null:+.1%} ({gain:+.1%}). KEEP `present`. The flat score")
            print(f"  is at its ceiling for this corpus, and `HIGHER_ORDER_WEIGHT` stays 0.0 —")
            print(f"  built, measured, runnable, off. A null result is a result.")
    print()

    if args.json:
        print(json.dumps(record, indent=2, default=str))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebuild-cache", action="store_true",
                    help="re-derive the adjacency contact cache (slow)")
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
