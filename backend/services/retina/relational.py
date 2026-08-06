"""
Relational re-ranking — propose candidates likely to STAND IN a relation, not ones that look alike.

## The problem this exists for

Identity kNN answers "what resembles this?". The movement kernel asks "what stands in the same
relation as this?". Those are different questions, and on the real corpus the first is not merely a
weak proxy for the second — it is slightly *anti*-correlated with it. Measured on the finial-5 seed
at k=48 (`FINDING-wave3-retina-density.md`, Surprise 2):

    precision@8  = 0/8      the eight nearest neighbours by appearance ground NOTHING
    precision@12 = 0/12     nor do the twelve — and 12 is the kernel's default k
    pearson(identity score, grounded) = -0.16

An agent spending its whole candidate budget on the nearest twelve grounds nothing at all. Not
because the corpus is thin — 21 of 48 ground once you look further out — but because the ranking
is pointed at the wrong question.

## What a relational prior is, and what it is not

Groundability is decided by geometry the retina never sees: whether the candidate region sits inside
something in its OWN image, and whether that shape of nesting resembles the seed's. Both are
readable from extents. So this module ranks on extents.

**Boxes, on purpose.** Every number here is computed from bounding boxes — an estimate of an extent,
never a measurement of one. That is not a shortcut, it is the WAVE2.5 ruling applied where it was
written to apply: box-basis geometry "may PROPOSE a candidate (peripheral signal) but must never
mint a measured edge" (`DECISION-movement-grounds-only-on-masks.md`). Proposing is precisely what
this does. The kernel re-reads every proposal on masks and is free to disagree — and it does; the
disagreement rate is reported by `scripts/relational_retrieval_proof.py` and is the evidence that
the retina has not quietly become the kernel.

So: nothing here carries an `epistemic_status`, every prior is stamped `kind: "prior"` and
`basis: "box"`, and no function in this file returns a verdict. A relational score is a *ranking*
signal — a better answer to "where should I look next", still not an answer to "what is true".

## Why the thresholds are copied and not imported

`MIN_CONTAINMENT` / `MAX_SCALE_RATIO` here hold the same values as `nestedness_organ`'s, and
`_alignment` computes the same min/max ratio as `structure_map`'s. Both are duplicated deliberately
rather than imported.

The retina must not depend on the organ or the mapper, because it is not entitled to their
authority. If the kernel later retunes what counts as nesting, the retina's *guess* about where to
look should not silently change with it — the proposer and the decider drifting apart is visible as
a falling hit rate, whereas a proposer wired to always agree with the decider is a rubber stamp that
reports 100% and has stopped being evidence. This is duplication that must NOT be assumed to agree,
which is the kind that is safe.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

#: Everything this module emits. A prior is a guess about where to look, ranked.
PRIOR_KIND = "prior"

#: The only geometry a proposer may use, under the WAVE2.5 ruling.
PRIOR_BASIS = "box"

NOT_A_MEASUREMENT = (
    "Relational priors are box-basis estimates used to ORDER candidates. A box is an estimate of "
    "an extent; only a mask is a measurement of one. Nothing here decides whether a relation "
    "holds — the kernel measures on masks and may disagree with every one of these."
)

#: Mirrors `nestedness_organ.MIN_CONTAINMENT` / `MAX_SCALE_RATIO` by value, never by import. See
#: the module docstring for why that duplication is the safe kind.
MIN_CONTAINMENT = 0.95
MAX_SCALE_RATIO = 0.75
MIN_AREA = 1e-6

#: How wide to cast the identity net before re-ranking. The re-rank can only reorder what recall
#: handed it, so a multiplier of 1 is a no-op dressed as a feature.
DEFAULT_RECALL_MULTIPLIER = 4

#: What the ranking is made of. Stated as data so the weighting is arguable rather than buried in
#: an expression, and CHECKED against the corpus rather than fitted to it — a 180-point grid sweep
#: over 5 seeds × 120 recalled candidates found these already on the best plateau, so nothing here
#: was tuned to the measurement (`scripts/relational_retrieval_proof.py --sweep` reproduces it).
#:
#:   stands_in_relation  the candidate sits inside something in its own image — the thing
#:                       `surface_only` refuses for. Weighted to dominate.
#:   shape_affinity      how alike the two nesting SHAPES are (depth / siblings / descendants).
#:                       A prior for systematicity, computed the same way and trusted less.
#:   mask_prior          candidate and its box-basis parent both carry masks, so the pair could
#:                       clear admissibility. Matters more the deeper recall goes: past the first
#:                       few dozen neighbours the pool fills with unmasked VLM boxes.
#:   identity            the original appearance score, kept small rather than dropped — a bad
#:                       primary signal and a reasonable tie-break. Zeroing it would leave
#:                       structurally identical candidates ordered arbitrarily.
#:
#: ABLATION, mean precision@12 across the 5 seeds (identity-only baseline: 0.217):
#:
#:     DEFAULT                0.617        − shape_affinity      0.417
#:     − stands_in_relation   0.617        − mask_prior          0.483
#:                                         − identity            0.583
#:
#: `stands_in_relation` earns NOTHING on this corpus — removing it changes not one ranking. It is
#: kept anyway, and this is not sentiment: at 0.50 it outweighs every other term combined, so it
#: guarantees a relation-bearing candidate outranks one with no relation at all. Shape affinity
#: happens to produce that ordering here, but it need not — `_alignment` scores 0-vs-0 as perfect
#: agreement, so a seed with no descendants gives every relation-less candidate a free 1/3, and a
#: genuinely nested candidate with a mismatched shape can score below it. The guard is currently
#: unexercised. It is not redundant; it is un-hit, and those are different.
DEFAULT_WEIGHTS = {
    "stands_in_relation": 0.50,
    "shape_affinity": 0.30,
    "mask_prior": 0.10,
    "identity": 0.10,
}


# ── box arithmetic (local, so this module has no dependency that could grow into one) ────────

def _area(box: Mapping[str, Any]) -> float:
    return max(0.0, float(box.get("w") or 0.0)) * max(0.0, float(box.get("h") or 0.0))


def _overlap_fraction(inner: Mapping[str, Any], outer: Mapping[str, Any]) -> float:
    """Fraction of `inner`'s area that falls inside `outer`. 0 when `inner` is degenerate."""
    ix, iy = float(inner.get("x") or 0.0), float(inner.get("y") or 0.0)
    ox, oy = float(outer.get("x") or 0.0), float(outer.get("y") or 0.0)
    x0, y0 = max(ix, ox), max(iy, oy)
    x1 = min(ix + float(inner.get("w") or 0.0), ox + float(outer.get("w") or 0.0))
    y1 = min(iy + float(inner.get("h") or 0.0), oy + float(outer.get("h") or 0.0))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    area = _area(inner)
    return ((x1 - x0) * (y1 - y0) / area) if area > 0 else 0.0


def _contains(inner: Mapping[str, Any], outer: Mapping[str, Any]) -> Optional[Dict[str, float]]:
    """Does `outer` plausibly hold `inner`? The prior's one geometric judgement.

    Returns the two factors when it does and None when it does not, so a caller can see WHY —
    `containment` and `scale_ratio` are the same two numbers the organ reports, computed on boxes
    and therefore an estimate of them.
    """
    a_in, a_out = _area(inner), _area(outer)
    if a_in < MIN_AREA or a_out < MIN_AREA:
        return None
    containment = min(1.0, max(0.0, _overlap_fraction(inner, outer)))
    scale_ratio = min(1.0, max(0.0, a_in / a_out if a_out > 0 else 1.0))
    if containment < MIN_CONTAINMENT or scale_ratio > MAX_SCALE_RATIO:
        return None
    return {"containment": round(containment, 6), "scale_ratio": round(scale_ratio, 6)}


# ── the skeleton, box-basis ──────────────────────────────────────────────────────────────────

def skeletons(post_geometry: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Every region in one post → its box-basis nesting skeleton, in one n² sweep.

    Computed for the whole post at once because the sweep is shared: the same pair decides one
    region's parent and another's descendant, and doing it per candidate would redo it n times.
    On the corpus's largest post (68 regions) this is ~4.6k float comparisons — microseconds, and
    no mask is decoded.
    """
    ids = list(post_geometry)
    boxes = {rid: post_geometry[rid].get("box") or {} for rid in ids}
    containers: Dict[str, List[Dict[str, Any]]] = {rid: [] for rid in ids}
    descendants: Dict[str, List[str]] = {rid: [] for rid in ids}

    for inner in ids:
        for outer in ids:
            if inner == outer:
                continue
            fit = _contains(boxes[inner], boxes[outer])
            if fit is None:
                continue
            containers[inner].append({"region_id": outer, **fit})
            descendants[outer].append(inner)

    out: Dict[str, Dict[str, Any]] = {}
    for rid in ids:
        # The tightest container first — the same choice `relational_structure` makes, and for the
        # same reason: the immediate parent is the smallest thing that holds it, not the frame.
        mine = sorted(containers[rid], key=lambda c: -c["scale_ratio"])
        parent = mine[0] if mine else None
        parent_id = parent["region_id"] if parent else ""
        siblings = sorted(set(descendants.get(parent_id, [])) - {rid}) if parent_id else []
        out[rid] = {
            "region_id": rid,
            "basis": PRIOR_BASIS,
            "kind": PRIOR_KIND,
            "parent_id": parent_id,
            "parent_fit": parent,
            "depth": len({c["region_id"] for c in mine}),
            "sibling_count": len(siblings),
            "descendant_count": len(set(descendants[rid])),
            "has_relation": bool(parent_id),
            "has_mask": bool(post_geometry[rid].get("has_mask")),
            "parent_has_mask": bool(post_geometry.get(parent_id, {}).get("has_mask"))
                               if parent_id else False,
        }
    return out


def skeleton_of(post_geometry: Mapping[str, Mapping[str, Any]], region_id: str
                ) -> Optional[Dict[str, Any]]:
    return skeletons(post_geometry).get(str(region_id))


# ── scoring ──────────────────────────────────────────────────────────────────────────────────

def _alignment(a: Any, b: Any) -> float:
    """min/max, with 0/0 = 1. Two regions that both bottom out DO share that shape.

    The same arithmetic `structure_map` uses, written out rather than imported — see the module
    docstring. The retina is guessing at what the mapper will say; it must not be wired to agree.
    """
    a, b = float(a or 0), float(b or 0)
    if a <= 0 and b <= 0:
        return 1.0
    hi = max(a, b)
    return (min(a, b) / hi) if hi > 0 else 1.0


def shape_affinity(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """How alike the two nesting shapes are, in [0,1] — the prior for systematicity.

    Sees no vector, no label and no score: it is handed two skeletons, exactly like the mapper it
    is guessing at. What it does NOT share with the mapper is authority — this number orders a
    shortlist and never gates anything.
    """
    depth = _alignment(seed.get("depth"), candidate.get("depth"))
    siblings = _alignment(seed.get("sibling_count"), candidate.get("sibling_count"))
    descendants = _alignment(seed.get("descendant_count"), candidate.get("descendant_count"))
    return {"score": round((depth + siblings + descendants) / 3.0, 6),
            "components": {"depth": round(depth, 6), "siblings": round(siblings, 6),
                           "descendants": round(descendants, 6)}}


def relational_prior(seed: Mapping[str, Any], candidate: Optional[Mapping[str, Any]],
                     *, identity_score: float = 0.0,
                     weights: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
    """One candidate's ranking score, and every term that produced it.

    `candidate` is None when the region has no cached geometry — an unlocatable region, or a
    sidecar older than the corpus. It scores on identity alone and says so in `terms`, rather than
    being dropped: the retina not knowing where something sits is not evidence about the region.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    known = candidate is not None
    stands = 1.0 if (known and candidate.get("has_relation")) else 0.0
    affinity = shape_affinity(seed, candidate) if known else {"score": 0.0, "components": {}}
    mask_prior = 1.0 if (known and candidate.get("has_mask")
                         and candidate.get("parent_has_mask")) else 0.0
    identity = max(0.0, min(1.0, float(identity_score or 0.0)))

    terms = {"stands_in_relation": stands, "shape_affinity": affinity["score"],
             "mask_prior": mask_prior, "identity": identity}
    score = sum(w.get(k, 0.0) * v for k, v in terms.items())
    return {
        "kind": PRIOR_KIND,
        "basis": PRIOR_BASIS,
        "score": round(score, 6),
        "terms": terms,
        "weights": {k: w.get(k, 0.0) for k in terms},
        "shape_components": affinity["components"],
        "geometry_known": known,
        "parent_id": (candidate or {}).get("parent_id", ""),
        "note": NOT_A_MEASUREMENT,
    }


# ── the re-rank ──────────────────────────────────────────────────────────────────────────────

def rerank(candidates: Sequence[Mapping[str, Any]], *, seed_skeleton: Mapping[str, Any],
           geometry: Mapping[str, Mapping[str, Any]],
           weights: Optional[Mapping[str, float]] = None) -> List[Dict[str, Any]]:
    """Reorder a shortlist by relational prior. REORDERS — never drops.

    Every candidate handed in comes back out, each carrying a `relational` block and its
    `identity_rank` from before the sort, so the move is auditable rather than merely different.
    Dropping here would make the retina a filter, and a filter is a decision; the only narrowing in
    the pipeline stays where it has always been — the caller's `k`.
    """
    skeleton_cache: Dict[str, Dict[str, Any]] = {}

    def _skeletons_for(post_id: str) -> Dict[str, Any]:
        if post_id not in skeleton_cache:
            skeleton_cache[post_id] = skeletons(geometry.get(post_id) or {})
        return skeleton_cache[post_id]

    scored: List[Dict[str, Any]] = []
    for rank, candidate in enumerate(candidates, start=1):
        post_id, region_id = str(candidate.get("post_id")), str(candidate.get("region_id"))
        cand_skeleton = _skeletons_for(post_id).get(region_id)
        prior = relational_prior(seed_skeleton, cand_skeleton,
                                 identity_score=candidate.get("score") or 0.0, weights=weights)
        scored.append({**candidate, "identity_rank": rank, "relational": prior})

    # Ties broken by the identity rank they arrived with: a stable, stated fallback beats whatever
    # order the vector store happened to return.
    scored.sort(key=lambda c: (-c["relational"]["score"], c["identity_rank"]))
    for position, candidate in enumerate(scored, start=1):
        candidate["relational_rank"] = position
    return scored


__all__ = ["PRIOR_KIND", "PRIOR_BASIS", "NOT_A_MEASUREMENT", "DEFAULT_WEIGHTS",
           "DEFAULT_RECALL_MULTIPLIER", "MIN_CONTAINMENT", "MAX_SCALE_RATIO",
           "skeletons", "skeleton_of", "shape_affinity", "relational_prior", "rerank"]
