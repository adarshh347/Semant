#!/usr/bin/env python3
"""
WAVE4 — the corpus census: the measured state of the world.

    python scripts/corpus_census.py                 # the reckoning
    python scripts/corpus_census.py --json          # the same, as data
    python scripts/corpus_census.py --export data/corpus_census.json

Four relation kinds are now derived across the corpus, four organs measure it, and a curator
surface exists to commit what they propose. Nobody has ever written down, in one place and in
numbers, **what this system has actually derived and how little of it is settled.** This is that
document's instrument.

## What a census must not do

It must not read as a scoreboard. Three disciplines, each of which this script would otherwise
break by being convenient:

  · **DERIVED IS NOT COMMITTED.** Every relation here is a PROPOSAL. `scene_relations` stores no
    status precisely so that one cannot be edited into existence, and `hydrate` re-derives it on
    every read; the census reports `ledger_status` beside `epistemic` for exactly that reason. A
    row that said "1112 nestings" without saying "0 committed" would describe a settled world that
    does not exist.
  · **EVERY COUNT IS BOUNDED.** A census that stops at N posts is a claim about N posts. Extent,
    caps and grid are printed beside the numbers rather than in a footnote, because a bound that
    is not next to the count is a bound nobody reads.
  · **A NULL IS AN ANSWER WITH A CAUSE.** `kinds_absent` (nobody ever derived this) and
    `kinds_none_here` (it was derived and found nothing) are different facts, and collapsing them
    is the single easiest way to make an absence look like a failure — or a failure look like an
    absence. Every zero below is labelled with which it is.

READS ONLY. The derived cache, the atlas, the curator queue and the posts. Every mutating method on
every collection it touches is replaced with a raiser before the first query, so the reckoning
cannot alter the thing it is counting.

Needs the usual `.env`. The cache must have been built (`scripts/scene_relations_build.py`);
if it has not, the census says so rather than reporting zeros.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import scene_relations as scene                      # noqa: E402
from backend.services.epistemics import STATUS_KEY                         # noqa: E402

#: The four kinds, in the order they were built. Named so a fifth appears as a gap in this list
#: rather than as a quietly missing row.
#: Taken from the cache's own vocabulary, not from the organ module names — the cache says
#: `nesting`, the organ is `nestedness_organ`, and a census keyed on the wrong one reports zero for
#: the largest kind in the corpus while looking perfectly healthy. (It did, once, before this
#: comment existed.)
KINDS = ("nesting", "adjacency", "occlusion", "rhyme")

#: Why each kind can legitimately be zero. A null with no explanation is indistinguishable from a
#: bug, and these are the explanations the earlier lanes actually earned.
NULL_CAUSES: Dict[str, str] = {
    "rhyme": ("MIN_RHYME is 0.8 and the corpus-wide distribution of shape correlation has p75 "
              "≈ +0.26 with no valley — 0.36% of cross-image pairs clear the floor at all, and "
              "the rhyme sweep is capped at 8 posts × 24 regions. A zero here is the floor doing "
              "what the permutation null said it should, not a broken organ"),
    "occlusion": ("an occlusion needs both regions masked, a whole-frame depth field, and "
                  "dominance ≥ 0.95. Most region pairs in one scene are not ordered that cleanly"),
}


class WriteAttempted(Exception):
    """A write was attempted against a collection this census may only read."""


def freeze(*collections) -> None:
    def _blocked(*_a, **_k):
        raise WriteAttempted("the census may not write — it counts, it does not change")
    for coll in collections:
        for method in ("update_one", "update_many", "insert_one", "insert_many", "delete_one",
                       "delete_many", "replace_one", "bulk_write", "find_one_and_update"):
            try:
                setattr(coll, method, _blocked)
            except Exception:                                   # noqa: BLE001
                pass


# ── the derived world ───────────────────────────────────────────────────────

def derived(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Every derived relation, counted by kind × basis × epistemic. Reports its own bound."""
    status = scene.cache_status(payload)
    scenes = payload.get("scenes") or {}

    by_kind: Dict[str, Counter] = {k: Counter() for k in KINDS}
    basis_of: Dict[str, Counter] = {k: Counter() for k in KINDS}
    epistemic_of: Dict[str, Counter] = {k: Counter() for k in KINDS}
    ledger_of: Counter = Counter()
    superseded = 0
    unknown_kinds: Counter = Counter()

    for post_id, sc in scenes.items():
        # `relations` is a MAP of kind → rows, not a flat list. Iterating it as a list silently
        # yielded the kind STRINGS and counted nothing.
        for kind, rows in (sc.get("relations") or {}).items():
            kind = str(kind)
            if kind not in by_kind:
                unknown_kinds[kind] += len(rows or [])
                continue
            for rel in rows or []:
                # DERIVED ON READ, exactly as the route does. The cache stores no status, so the
                # census asks the same function the surface asks rather than reading a field that
                # could have been edited into existence.
                hydrated = scene.hydrate(rel)
                by_kind[kind][post_id] += 1
                basis_of[kind][str(rel.get("basis") or "")] += 1
                epistemic_of[kind][str(hydrated.get("epistemic") or "")] += 1
                ledger_of[str(hydrated.get("ledger_status") or "")] += 1
                if rel.get("supersedes"):
                    superseded += 1

    rows = []
    for kind in KINDS:
        total = sum(by_kind[kind].values())
        built = kind in (status.get("kinds_built") or [])
        rows.append({
            "kind": kind,
            "total": total,
            "posts_with_any": len(by_kind[kind]),
            "basis": dict(basis_of[kind]),
            "epistemic": dict(epistemic_of[kind]),
            # THE DISTINCTION THE HONESTY FLOOR TURNS ON.
            "null_kind": (None if total else ("none_here" if built else "absent")),
            "null_cause": (None if total else
                           (NULL_CAUSES.get(kind, "derived over the bound below and found none")
                            if built else "this kind was never derived — the cache did not build it")),
        })

    return {
        "cache": status,
        "kinds": rows,
        "ledger": dict(ledger_of),
        "superseded": superseded,
        "unknown_kinds": dict(unknown_kinds),
        "bound": {
            "scenes_in_cache": status.get("scenes"),
            "kinds_built": status.get("kinds_built"),
            "caps": status.get("caps"),
            "provenance": status.get("provenance"),
        },
    }


# ── what was committed ──────────────────────────────────────────────────────

async def coverage(payload: Dict[str, Any]) -> Dict[str, Any]:
    """How much of the corpus the cache actually covers — and THE GAP THIS LANE FOUND.

    `scene_relations` records `built_at` and `kinds_built`, and nothing that distinguishes a
    COMPLETED build from a CRASHED one. The build that produced the first version of this census
    died partway on an `httpx.ConnectError` fetching an image, and the cache it left behind is
    structurally identical to a finished one: same version, same `kinds_built`, a `built_at`
    stamp, and simply fewer scenes.

    Nothing in the cache says so. The only signal is arithmetic — scenes cached against posts that
    have regions to derive from — so the census computes it rather than trusting the file to
    confess. A census over a crashed build reported as a census is exactly the "measured state of
    the world" that would be wrong in the one direction that matters: it would understate.
    """
    from backend.database import post_collection

    freeze(post_collection)
    derivable = 0
    async for _ in post_collection.find({"region_annotations.1": {"$exists": True}}):
        derivable += 1

    cached = len(payload.get("scenes") or {})
    return {
        "posts_with_derivable_geometry": derivable,
        "scenes_cached": cached,
        "coverage": (round(cached / derivable, 3) if derivable else None),
        "complete": bool(derivable and cached >= derivable),
        "detail": (
            "the cache covers every derivable post" if derivable and cached >= derivable else
            f"the cache holds {cached} of {derivable} derivable posts. The cache records no "
            f"completion flag, so a partial build looks exactly like a finished one — this "
            f"shortfall is the only evidence, and every count below is bounded by it"),
    }


async def committed() -> Dict[str, Any]:
    """What a curator has actually accepted. Expected ≈ 0 — and that is the discipline, not a gap."""
    from backend.database import atlas_collection, curator_proposal_collection, post_collection

    freeze(atlas_collection, curator_proposal_collection, post_collection)

    marks = regions = posts = 0
    async for post in post_collection.find({"region_annotations.0": {"$exists": True}}):
        posts += 1
        regions += len(post.get("region_annotations") or [])
        marks += len(post.get("visual_marks") or [])

    atlases = edges = 0
    async for atlas in atlas_collection.find({}):
        atlases += 1
        edges += len(atlas.get("edges") or [])

    queued = accepted = 0
    try:
        async for proposal in curator_proposal_collection.find({}):
            queued += 1
            if proposal.get("committed"):
                accepted += 1
    except Exception:                                           # noqa: BLE001
        queued = accepted = -1                                  # the collection may not exist yet

    return {
        "posts_with_regions": posts,
        "regions": regions,
        # THE NUMBER THE WHOLE CENSUS EXISTS TO PUT BESIDE THE OTHERS.
        "committed_marks_on_posts": marks,
        "atlases": atlases,
        "atlas_edges": edges,
        "curator_queue": queued,
        "curator_committed": accepted,
        "detail": ("committed marks are what a human accepted onto a post's ledger. Every relation "
                   "in the derived section above is a PROPOSAL and none of them is here."),
    }


# ── the reckoning ───────────────────────────────────────────────────────────

def _print(census: Dict[str, Any]) -> None:
    d, c, cov = census["derived"], census["committed"], census["coverage"]
    cache = d["cache"]

    print("\n" + "=" * 78)
    print("  WAVE4 — the corpus census: the measured state of the world")
    print("=" * 78)

    print("\nTHE BOUND — every number below is a claim about exactly this much")
    print(f"   cache built    {cache.get('built_at') or '(never)'}")
    print(f"   scenes cached  {cache.get('scenes')}")
    print(f"   kinds built    {', '.join(cache.get('kinds_built') or []) or '(none)'}")
    print(f"   caps           {cache.get('caps')}")
    print(f"   coverage       {cov['scenes_cached']}/{cov['posts_with_derivable_geometry']} "
          f"derivable posts"
          + ("" if cov["complete"] else "   ⚠ INCOMPLETE"))
    if not cov["complete"]:
        print(f"     {cov['detail']}")
    if cache.get("missing") or cache.get("stale"):
        print("   ⚠ THE CACHE IS MISSING OR STALE — the zeros below are about the cache, not the")
        print("     corpus. Run scripts/scene_relations_build.py before reading this as a census.")

    print("\n1. WHAT WAS DERIVED — by kind, basis and epistemic status")
    print(f"   {'kind':<12} {'total':>7} {'posts':>6}   basis / epistemic")
    for row in d["kinds"]:
        basis = " ".join(f"{k}={v}" for k, v in sorted(row["basis"].items())) or "—"
        epi = " ".join(f"{k}={v}" for k, v in sorted(row["epistemic"].items())) or "—"
        print(f"   {row['kind']:<12} {row['total']:>7} {row['posts_with_any']:>6}   {basis} | {epi}")
        if row["null_kind"]:
            label = ("DERIVED AND FOUND NONE" if row["null_kind"] == "none_here"
                     else "NEVER DERIVED")
            print(f"      ↳ zero — {label}: {row['null_cause']}")

    print("\n2. WHAT WAS COMMITTED — and this is the point of the census")
    print(f"   posts with regions        {c['posts_with_regions']}")
    print(f"   regions                   {c['regions']}")
    print(f"   COMMITTED marks on posts  {c['committed_marks_on_posts']}")
    print(f"   atlases / edges           {c['atlases']} / {c['atlas_edges']}")
    print(f"   curator queue / accepted  {c['curator_queue']} / {c['curator_committed']}")
    print(f"   ledger status of derived  {d['ledger']}")
    print("   Every relation above is PROPOSED. Suggestions-only is not a stage this system is")
    print("   waiting to leave — it is the discipline, visible here as a number.")

    if d["superseded"]:
        print(f"\n3. RECLASSIFIED — {d['superseded']} relation(s) supersede an earlier reading")
        print("   A relation that replaced another says so and names what it replaced, rather than")
        print("   the earlier one silently disappearing.")

    if d["unknown_kinds"]:
        print(f"\n   ⚠ kinds in the cache this census does not know: {d['unknown_kinds']}")
        print("     A fifth kind is a gap in KINDS, not a row to quietly drop.")
    print()


async def main_async(args) -> int:
    payload = scene.load_cache()
    census = {
        "derived": derived(payload),
        "coverage": await coverage(payload),
        "committed": await committed(),
    }
    if args.export:
        path = os.path.abspath(args.export)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(census, fh, indent=2, default=str)
        print(f"exported {path}", file=sys.stderr)
    if args.json:
        print(json.dumps(census, indent=2, default=str))
    else:
        _print(census)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--export", default="", help="write the census to a JSON file")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
