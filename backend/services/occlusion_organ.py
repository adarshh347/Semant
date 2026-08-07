"""
WAVE3 — occlusion: the relation that measures what WAVE2.5 could only refuse.

## The founding pathology, and why refusing it was never the answer

`cseg_golden_finial_7` scored containment **1.000** and nesting index **0.999** against 'Sky'. The
finial is in *front* of the sky. WAVE2.5 ruled that a `measured` movement grounds only on masks
([[DECISION-movement-grounds-only-on-masks]]) — and that ruling was right, but it is a **route
around** the problem: it removed the basis on which the false claim could be made without ever
saying what is actually true of those two regions.

Nothing in the system could tell *inside* from *in front of*, because nothing measured occlusion
order. `depth_organ` (WAVE3) added the measurement. This module adds the **relation**, so the
finial gets a positive, measured account of its relationship to the sky instead of a refusal.

    box basis     'the finial is contained in the sky, 0.999'   INTERPRETIVE, refused as measured
    mask basis    'the finial is not contained in the sky'      MEASURED  (containment 0.000)
    depth basis   'the finial is IN FRONT OF the sky'           MEASURED  ← this module

The third line is the one that was missing. The first two say what is not the case; only the third
says what is.

## What it measures, and why it is not a difference of means

Depth-Anything gives *relative inverse depth* — larger is nearer, in no units. The obvious test is
a gap between the two regions' mean depths, expressed as a fraction of the frame's range. **That
test was built first and it fails on exactly the case this module exists for.**

Inverse depth compresses distance: everything far crowds toward zero. Measured on the finial image,
the frame's depth runs 0.0000–8.6268, the finial reads 0.3321 and the sky behind it 0.0008 — a
step of 0.332, which is **3.8% of the frame's range** and sits at the 44th percentile of all region
pairs in that picture. A magnitude threshold either calls that coplanar or admits most of the
picture. The founding pathology lives in the regime monocular inverse depth resolves worst.

But the magnitude was never the claim. **`in_front_of` is an ORDERING relation**, and orderings are
answered by an ordering statistic:

    dominance   P(a cell of A reads nearer than a cell of B), ties at half
    separation  max(dominance, 1 - dominance) — 0.5 is no ordering, 1.0 is complete

On the same pair, dominance is **0.9989**: essentially every cell of the finial reads nearer than
essentially every cell of the sky. The two distributions do not overlap. The step is small and the
ORDER is unambiguous, and the order is what occlusion means.

The mean gap is still reported (`depth_gap`, `rank_gap`) — it answers "by how much", which is a
real question and a different one.

## What separates `in_front_of` from `inside`

This is the whole point, so it is worth being exact about what is and is not being claimed.

    in_front_of   the two regions sit at measurably different depths — a discontinuity
    coplanar      they do not. Whatever else is true of them, depth does not separate them.

`coplanar` is deliberately NOT called `inside`. Depth cannot see containment; two regions at the
same depth might be nested, adjacent, or unrelated, and this organ has no way to tell. Naming its
null result `inside` would be exactly the overreach the finial case is made of, in the opposite
direction. Containment is `nestedness_organ`'s to measure. What this module supplies is the second
fact you need to read a containment correctly — and `reconcile_containment` is where the two meet.

## Admissibility

Mask on both sides, whole-frame field, provenance named → `measured`. Anything else →
`interpretive`. A box's depth is *the arithmetic mean of a thing and the thing behind it* (WAVE3's
depth lane measured it: the finial's twin read 1.8358 on its mask and 1.6176 on its box, dragged
from 69% of the frame behind it to 55%). Using that to judge occlusion order would be reading the
pathology as the evidence.

PURE. No database, no network, no model. Two region dicts and a depth field in, a relation out.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence
from uuid import uuid4

from backend.services import depth_organ
from backend.services import nestedness_organ as nestedness
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

ORGAN = "occlusion_organ"
ORGAN_VERSION = 1

#: One region is measurably nearer than the other: a depth discontinuity between them.
RELATION_IN_FRONT_OF = "in_front_of"

#: Depth does not separate them. NOT a claim of containment, adjacency or anything else — see the
#: module docstring on why this is not called `inside`.
RELATION_COPLANAR = "coplanar"

#: The axis this relation instantiates, for a movement graph that later wants to traverse it.
AXIS_OCCLUSION = "axis_occlusion"

#: How cleanly the two cell distributions must be ordered before the pair counts as separated.
#: 0.5 is no ordering at all; 1.0 is no overlap whatsoever.
#:
#: **A FREE PARAMETER, and declared as one** — the discipline
#: [[DECISION-systematicity-floor-is-a-free-parameter]] made binding. Over all region pairs the
#: statistic is a smooth curve with no valley: p25=0.82, p50=0.96, 41% fully separated. 0.95 was
#: picked as legible and arbitrary, in that order, BEFORE the sweep below existed.
#:
#: It then turned out to land in a gap, and the honest version of that is worth stating precisely.
#: On the finial image the 65 mask-basis containments — things genuinely enclosed in other things
#: — order at most **0.9390**, while the finial against the sky orders **0.9987**. The floor falls
#: between the two classes. That is ONE image, 65 pairs against 1, and two classes rather than a
#: distribution: it is a gap, not a valley, and it is not a derivation. What it is good for is
#: saying that the value is not obviously wrong, which is more than the systematicity floor could
#: claim and much less than a principled threshold.
#:
#: `measure()` reports `dominance` on every reading, so a caller who disagrees can re-threshold
#: without re-measuring, and `scripts/occlusion_proof.py` sweeps it rather than assuming it.
MIN_SEPARATION = 0.95

#: How many cells each side needs before an ordering between them means anything. Below this the
#: statistic is computed over so few comparisons that complete separation is unremarkable.
MIN_CELLS_PER_SIDE = depth_organ.MIN_CELLS

#: Mask → measured, box → interpretive. Taken from the nestedness organ rather than restated, so
#: the two relations cannot drift apart about what a basis is worth.
BASIS_EPISTEMIC = nestedness.BASIS_EPISTEMIC
ADMISSIBLE_BASIS = nestedness.ADMISSIBLE_BASIS


class OcclusionRefusal(Exception):
    """The geometry or the field cannot support an occlusion reading at all."""


def _dominance(a_values: Sequence[float], b_values: Sequence[float]) -> float:
    """P(a cell of A reads NEARER than a cell of B), ties counted at half.

    Exact rather than sampled, and `O((|A| + |B|) log |B|)` rather than the quadratic form: the sky
    in the finial picture covers eleven thousand cells, and a pairwise loop against it would make
    a full sweep of one post an afternoon's work.
    """
    from bisect import bisect_left, bisect_right

    ordered = sorted(b_values)
    n = len(ordered)
    if not a_values or not n:
        return 0.5
    total = 0.0
    for value in a_values:
        below = bisect_left(ordered, value)
        equal = bisect_right(ordered, value) - below
        total += below + 0.5 * equal
    return total / (len(a_values) * n)


def epistemic_for(basis: str) -> str:
    return BASIS_EPISTEMIC.get(str(basis), EpistemicStatus.INTERPRETIVE.value)


def is_admissible(measurement: Optional[Mapping[str, Any]]) -> bool:
    """Both ends on masks. A cross-region depth claim is a claim about a PAIR, so the weaker basis
    governs — the same rule, and the same reason, as the WAVE2.5 ruling for containment."""
    if not measurement:
        return False
    return str(measurement.get("basis") or "") == ADMISSIBLE_BASIS


def measure(a: Mapping[str, Any], b: Mapping[str, Any],
            field: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Which of these two regions is in front, and by how much of the frame.

    Reads no label and no embedding. Raises `OcclusionRefusal` when either region cannot be read
    at all — a refusal is a fact about the geometry, not a quiet `coplanar`.
    """
    if a is None or b is None:
        raise OcclusionRefusal("two regions are required")
    a_id, b_id = str(a.get("id") or ""), str(b.get("id") or "")
    if a_id and a_id == b_id:
        raise OcclusionRefusal(
            f"region {a_id!r} against itself — nothing is in front of itself")

    try:
        near_read = depth_organ.measure(a, field)
        far_read = depth_organ.measure(b, field)
        grid = int(field["grid"])
        a_cells, a_basis = depth_organ.region_cells(a, grid)
        b_cells, b_basis = depth_organ.region_cells(b, grid)
    except depth_organ.DepthRefusal as exc:
        raise OcclusionRefusal(f"the depth organ could not read this pair: {exc}") from exc

    if min(len(a_cells), len(b_cells)) < MIN_CELLS_PER_SIDE:
        raise OcclusionRefusal(
            f"one side covers {min(len(a_cells), len(b_cells))} depth cells, below "
            f"{MIN_CELLS_PER_SIDE}. An ordering over that few comparisons is not an ordering "
            f"between two regions, it is an ordering between a handful of grid cells")

    depth_values = list(field["depth"])
    dominance = _dominance([depth_values[i] for i in a_cells],
                           [depth_values[i] for i in b_cells])
    separation = max(dominance, 1.0 - dominance)

    # The weaker basis governs: one mask and one box is a box-basis pair.
    basis = ("mask" if a_basis == "mask" == b_basis else "box")

    rank_gap = near_read["frame_rank"] - far_read["frame_rank"]
    depth_gap = near_read["depth_mean"] - far_read["depth_mean"]
    separated = separation >= MIN_SEPARATION

    if not separated:
        relation, front, back = RELATION_COPLANAR, "", ""
    elif dominance > 0.5:
        relation, front, back = RELATION_IN_FRONT_OF, a_id, b_id
    else:
        relation, front, back = RELATION_IN_FRONT_OF, b_id, a_id

    return {
        "relation": relation,
        "axis": AXIS_OCCLUSION,
        "organ": ORGAN,
        "organ_version": ORGAN_VERSION,
        # Which is nearer, said as ids rather than as a sign, so a reader cannot get it backwards.
        "front_region_id": front,
        "back_region_id": back,
        "a_region_id": a_id,
        "b_region_id": b_id,
        # The fraction of the frame lying between them in depth. Dimensionless on purpose: the
        # model's raw inverse depth has no units and a threshold in it would have none either.
        # THE ORDERING STATISTIC — the claim this relation actually makes.
        "dominance": round(dominance, 6),
        "separation": round(separation, 6),
        # By how much, which is a real question and a different one. Small here even when the
        # ordering is unambiguous, because inverse depth compresses everything distant.
        "rank_gap": round(rank_gap, 6),
        "depth_gap": round(depth_gap, 6),
        "separated": separated,
        "a_cells": len(a_cells),
        "b_cells": len(b_cells),
        "a_depth": near_read["depth_mean"],
        "b_depth": far_read["depth_mean"],
        "a_frame_rank": near_read["frame_rank"],
        "b_frame_rank": far_read["frame_rank"],
        "basis": basis,
        "epistemic": epistemic_for(basis),
        "admissible": basis == ADMISSIBLE_BASIS,
        "thresholds": {"min_separation": MIN_SEPARATION,
                       "min_cells_per_side": MIN_CELLS_PER_SIDE},
        "source": dict(near_read.get("source") or {}),
        "readings": {"a": near_read, "b": far_read},
        "detail": (
            f"{basis} depth {near_read['depth_mean']:.4f} vs {far_read['depth_mean']:.4f} "
            f"(inverse; larger is nearer), the orderings separating {separation:.4f} "
            + (f"— so {front} is IN FRONT OF {back}" if separated else
               "— below the separation floor: depth does not order these two")),
    }


#: The containment reading stands: nothing in the depth field contradicts it.
CONTAINMENT_STANDS = "stands"

#: Nestedness read a containment and depth says the inner region is in FRONT of its supposed
#: container. This is the finial case, named.
CONTAINMENT_SUPERSEDED = "superseded_by_occlusion"

#: Depth could not judge it — no field, unreadable regions, or a box-basis pair. The containment
#: reading is neither confirmed nor corrected, and saying so is the honest result.
CONTAINMENT_UNJUDGED = "unjudged"


def reconcile_containment(containment: Optional[Mapping[str, Any]],
                          occlusion: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Read a nestedness containment against an occlusion measurement. THE RESOLUTION.

    A containment says the inner region's extent falls within the outer's. Depth says whether they
    are at the same distance. Together they separate the two cases a bounding box conflated:

        contained  +  coplanar        →  a genuine nesting. The reading stands.
        contained  +  inner in front  →  the finial case. The extents overlap in the image plane
                                         and the regions are at different distances, so the
                                         containment is a projection artefact, not a nesting.

    The verdict is only `superseded` when BOTH readings are admissible — a measured claim cannot be
    overturned by an estimate, which is the WAVE2.5 ruling applied in the other direction. Where
    depth cannot judge, this returns `unjudged` rather than defaulting to either answer.
    """
    if not containment or not containment.get("nested"):
        return {"verdict": CONTAINMENT_UNJUDGED, "relation": None,
                "detail": "there is no containment reading to reconcile"}

    inner = str(containment.get("inner_region_id") or "")
    outer = str(containment.get("outer_region_id") or "")

    if not occlusion or not occlusion.get("separated"):
        judged = bool(occlusion) and is_admissible(occlusion)
        return {
            "verdict": CONTAINMENT_STANDS if judged else CONTAINMENT_UNJUDGED,
            "relation": nestedness.RELATION_NESTED_WITHIN if judged else None,
            "epistemic": containment.get("epistemic"),
            "detail": (
                f"depth does not separate {inner} from {outer}, so nothing contradicts the "
                f"containment — it stands on its own basis ({containment.get('basis')})"
                if judged else
                "depth could not judge this containment: no admissible occlusion reading"),
        }

    if not (nestedness.is_admissible(containment) and is_admissible(occlusion)):
        return {
            "verdict": CONTAINMENT_UNJUDGED, "relation": None,
            "detail": (
                f"depth orders them (separation {occlusion['separation']:.3f}), but one of the "
                f"two readings rests on box geometry (containment={containment.get('basis')}, "
                f"occlusion={occlusion.get('basis')}). An estimate may propose this correction and "
                f"may not make it — the same rule that refused the original 0.999."),
        }

    if str(occlusion.get("front_region_id")) != inner:
        return {
            "verdict": CONTAINMENT_STANDS,
            "relation": nestedness.RELATION_NESTED_WITHIN,
            "epistemic": containment.get("epistemic"),
            "detail": (f"depth separates them but {outer} is the nearer one, so {inner} is not "
                       f"in front of its container — the containment stands"),
        }

    return {
        "verdict": CONTAINMENT_SUPERSEDED,
        "relation": RELATION_IN_FRONT_OF,
        "epistemic": occlusion.get("epistemic"),
        "front_region_id": inner,
        "back_region_id": outer,
        "detail": (
            f"nestedness measured {inner} contained in {outer} "
            f"(containment {containment.get('containment')}, index {containment.get('nesting_index')}), "
            f"and depth measures {inner} IN FRONT OF {outer} — their depth distributions separate "
            f"{occlusion['separation']:.4f}. The extents overlap in the image plane and the regions are "
            f"at different distances: the containment is a projection artefact. This is the WAVE2.5 "
            f"case, corrected by measurement rather than routed around."),
    }


def new_mark_id() -> str:
    return f"vm_occ_{uuid4().hex[:12]}"


def grounding_mark(measurement: Mapping[str, Any], *, post_id: str,
                   step_id: str = "", now: str = "") -> Dict[str, Any]:
    """The organ's reading as a proposable mark. The ONE place a status is written.

    Derived from the basis, so a box-basis occlusion reading cannot be committed as `measured`
    however large its gap — the discipline `nestedness_organ.grounding_mark` established.
    """
    basis = str(measurement.get("basis") or "")
    return {
        "id": new_mark_id(),
        "type": "relation_mark",
        "relation": measurement.get("relation"),
        "axis": AXIS_OCCLUSION,
        "post_id": str(post_id),
        "front_region_id": measurement.get("front_region_id"),
        "back_region_id": measurement.get("back_region_id"),
        "region_ids": [measurement.get("a_region_id"), measurement.get("b_region_id")],
        STATUS_KEY: epistemic_for(basis),
        "detail": measurement.get("detail"),
        "measurement": {k: measurement.get(k) for k in
                        ("dominance", "separation", "rank_gap", "depth_gap", "a_depth",
                         "b_depth", "a_frame_rank", "b_frame_rank", "separated", "basis",
                         "a_cells", "b_cells", "thresholds")},
        "provenance": {
            # Both producers named: the organ that read it, and the checkpoint that produced the
            # field it read. A mark naming only one leaves the weighted half anonymous.
            "producer": ORGAN,
            "producer_version": ORGAN_VERSION,
            "step_id": str(step_id),
            **{k: v for k, v in (measurement.get("source") or {}).items()},
        },
        "at": str(now),
    }


def find_occlusions(regions: Sequence[Mapping[str, Any]], field: Optional[Mapping[str, Any]], *,
                    min_separation: float = MIN_SEPARATION) -> list:
    """Every measurable occlusion among a post's regions, nearest-pair first.

    Each unordered pair once: `in_front_of` carries its own direction, so measuring both orderings
    would report one fact twice with the ids swapped.
    """
    out, seen = [], set()
    for a in regions or []:
        for b in regions or []:
            if a is b:
                continue
            key = tuple(sorted((str(a.get("id")), str(b.get("id")))))
            if key in seen:
                continue
            seen.add(key)
            try:
                m = measure(a, b, field)
            except OcclusionRefusal:
                continue
            if m["separated"] and m["separation"] >= min_separation:
                out.append(m)
    out.sort(key=lambda m: -m["separation"])
    return out


__all__ = ["ORGAN", "ORGAN_VERSION", "RELATION_IN_FRONT_OF", "RELATION_COPLANAR", "AXIS_OCCLUSION",
           "MIN_SEPARATION", "MIN_CELLS_PER_SIDE", "BASIS_EPISTEMIC", "ADMISSIBLE_BASIS", "OcclusionRefusal",
           "epistemic_for", "is_admissible", "measure", "find_occlusions", "grounding_mark",
           "new_mark_id", "reconcile_containment", "CONTAINMENT_STANDS", "CONTAINMENT_SUPERSEDED",
           "CONTAINMENT_UNJUDGED"]
