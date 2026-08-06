"""
WAVE2 Lane M — structure-mapping: the guard that makes a movement more than a resemblance.

Gentner's distinction, and the reason this module exists at all. An **attribute** is a property of
one object — RED(x), ROUND(x). A **relation** holds between two — INSIDE(x, y). Analogy is the
mapping of *relations*; shared attributes are mere appearance. Her example is the one this lane
lives on: the solar system and the atom are analogous because ORBITS(planet, sun) maps onto
ORBITS(electron, nucleus), and nothing about a planet looks like an electron.

The retina answers "what looks like this" — DINOv2 proximity, which is pure attribute. If the
kernel wrote an edge for every candidate the retina liked, it would be building a graph of
resemblances and calling it perception. **This module is what stands between them.** A candidate
passes only when the RELATION holds on the far side, and a candidate that is merely similar is
refused by name (`REFUSED_SURFACE_ONLY`), which is the refusal the lane card asks for.

## Systematicity, and why the retina score is not a parameter here

Gentner's systematicity principle: a mapping supported by a connected system of relations is a
better analogy than an isolated shared predicate. A part inside a whole that is itself inside
something, alongside sibling parts, is a *system*; a lone pair is a coincidence with two elements.
So the score here is computed from relational structure — chain depth, siblings, descendants —
and from nothing else.

`systematicity()` does not take the retina's similarity score as an argument. That is deliberate
and structural, not an oversight: a function that cannot see a number cannot be swayed by it. It
is the same discipline `retina.store` uses when it makes a cross-space comparison impossible
rather than discouraged, and `movement_graph.strengthen` uses when it refuses to move a weight on
anything but a measurement.

## The floor, audited (WAVE3)

`MIN_SYSTEMATICITY` was set to a bare `0.34` in WAVE2 with the note "a stated, tunable floor" and
never checked. It is the line between *a feature coincided* and *a structure genuinely maps*, so it
fabricates in both directions if wrong, and it was worth auditing rather than inheriting.
`scripts/systematicity_floor_audit.py` scored all **129,564** cross-image gate-eligible pairs in the
corpus. Three findings, all now encoded above:

  1. **There is no valley.** The distribution is a smooth unimodal hump peaking at 0.50–0.55; the
     bins flanking 1/3 hold 1,264 and 1,590 pairs. **The magnitude of the floor is a free
     parameter** and is now declared as one (`SYSTEMATICITY_EPSILON`) rather than implied to be a
     measurement.
  2. **The shape of the rule is principled.** 2,178 pairs (1.68%) score exactly 1/3 — an atom, not
     a smear — and sitting just above it is precisely the stated intent: more than one component's
     worth of agreement. `MIN_SYSTEMATICITY` is now derived from `ONE_COMPONENT_SHARE` so the
     number and its reason cannot drift apart again.
  3. **The floor is defensible, and is not the best rule available.** Against a held-out criterion
     the gate never reads — *do the two CONTAINERS also map?*, a system extending past the pair —
     it separates by **+20.3 points** (36.2% vs 15.9%). Real work. But `_alignment` pays full marks
     for 0-vs-0, so pairs with no siblings and no descendants on either side average **0.842**, the
     highest bucket in the corpus, while the score *falls* as real structure rises (pearson −0.14).
     Averaging over only the live components (`aggregation="present"`) removes that inversion and
     lifts the separation to **+25.7 points**.

(3) is offered runnable and is **not** the default. Reshaping what grounds is a decision to take
deliberately, with its own before/after, not as a side effect of an audit that was asked to
characterise a threshold. What this lane changes is what you can SEE: every verdict now carries
`live`, `earned` and `absence_share`, so `insystematic` reports what it is made of.

**One floor does not cover two organs.** `relational_structure` is nesting-shaped — it hard-codes
`RELATION_NESTED_WITHIN`, and it picks the immediate parent by `scale_ratio`, a field only the
nestedness organ sets. Run it over `adjacency_organ`'s output and it still returns a skeleton, but
"parent" then means *the neighbour that happened to sort first* and the three components no longer
measure three independent things. The floor is calibrated on nesting and says nothing about
adjacency; a relation-specific floor is owed before adjacency movement is built on this gate.

## What this module does NOT do

It does not measure. It reads the relational skeleton the organ's measurements imply and asks
whether two skeletons align. **Alignment is not grounding** — a mapped candidate still has to be
measured by the organ on the far image before anything is written, and `movement_kernel` enforces
that ordering. A structure-map on its own is a hypothesis about where to point the instrument.

PURE. No database, no network, no model, no organ. Region dicts in, a mapping verdict out.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.services.nestedness_organ import RELATION_NESTED_WITHIN

#: A mapping was found: the relation holds on both sides and the roles correspond.
MAPPED = "mapped"

#: The candidate stands in NO instance of the relation. This is the surface-only refusal — the
#: retina liked how it looked and there is no structure underneath.
REFUSED_SURFACE_ONLY = "surface_only"

#: The source itself carries no relation to map FROM. Distinct from `surface_only`: the failure is
#: on the near side, and reporting it as a candidate's fault would send someone hunting the wrong
#: image.
REFUSED_NO_SOURCE_RELATION = "no_source_relation"

#: The relation holds but in the opposite direction — the candidate CONTAINS its correspondent
#: rather than being contained by it. Refused rather than silently re-oriented: "the finial is in
#: the spire" and "the spire is in the finial" are different claims, and quietly flipping one into
#: the other is how a graph starts asserting things nobody measured.
REFUSED_INVERTED = "inverted"

#: What one component's worth of agreement is worth, given three components averaged. The floor
#: exists to sit just above this: a mapping whose entire agreement is one component is one shared
#: predicate with nothing holding it up — a coincidence with two elements rather than a system.
#: This is the only principled quantity in the floor.
ONE_COMPONENT_SHARE = 1.0 / 3.0

#: How far above `ONE_COMPONENT_SHARE` to stand. **A FREE PARAMETER, and declared as one.**
#:
#: WAVE3 audited the score distribution over all 129,564 cross-image gate-eligible pairs in the
#: corpus (`scripts/systematicity_floor_audit.py`). There is **no valley** near the floor: the
#: distribution is a smooth unimodal hump peaking at 0.50–0.55, and the bins on either side of
#: 1/3 hold 1,264 and 1,590 pairs. Nothing in the data selects this number. What the data does
#: show is a real atom — 2,178 pairs (1.68%) score exactly 1/3 — and the floor's one defensible
#: job is to sit above it. Any epsilon does that; this one is arbitrary and small.
#:
#: So the SHAPE of the rule is principled and the MAGNITUDE is not, and both facts now live in
#: the code rather than in someone's memory of a lane.
SYSTEMATICITY_EPSILON = 0.00667

#: Below this a mapping is one shared predicate with nothing holding it up. DERIVED, so the
#: rationale cannot drift away from the number the way it did between WAVE2 and WAVE3.
#:
#: It is defensible, and measured to be so. Against a held-out criterion this gate never reads —
#: do the two CONTAINERS also map, a system extending past the pair itself? — it separates by
#: **+20.3 points**: 36.2% of the pairs it admits have mapping containers, against 15.9% of the
#: pairs it refuses. That is real work, not a line nobody vouched for.
MIN_SYSTEMATICITY = round(ONE_COMPONENT_SHARE + SYSTEMATICITY_EPSILON, 5)

#: How the three components are combined.
#:
#:   `shape`    all three averaged, 0-vs-0 counted as perfect agreement. The WAVE2 rule and still
#:              the default — silently changing what grounds is not this lane's to do.
#:   `present`  averaged over components where at least one side HAS structure. Absence abstains
#:              instead of agreeing.
#:
#: `present` measures better on both audited criteria (see the module docstring) and is offered
#: RUNNABLE rather than adopted, the way #150 kept `ranking="identity"` runnable.
AGGREGATION_SHAPE = "shape"
AGGREGATION_PRESENT = "present"
AGGREGATIONS = (AGGREGATION_SHAPE, AGGREGATION_PRESENT)


def _alignment(a: float, b: float) -> float:
    """How well two structural counts agree, in [0,1].

    `min/max`, with 0/0 = 1.0 — two parts that both bottom out (neither contains anything) DO
    share that structure, and scoring their agreement as zero would penalise the commonest real
    match in the corpus. Both-absent is agreement, not absence of evidence.
    """
    a, b = float(a), float(b)
    if a <= 0 and b <= 0:
        return 1.0
    hi = max(a, b)
    return (min(a, b) / hi) if hi > 0 else 1.0


def relational_structure(regions: Sequence[Mapping[str, Any]], region_id: str, *,
                         measurements: Optional[Sequence[Mapping[str, Any]]] = None
                         ) -> Dict[str, Any]:
    """The relational skeleton around one region: what holds it, what it holds, how deep, how many.

    Built from MEASUREMENTS, not from labels or boxes directly — `measurements` is the organ's
    output over this image (`find_nested_pairs`). So the skeleton only ever contains relations
    something actually measured, and this module never has to decide what counts as inside.
    """
    rid = str(region_id)
    pairs = list(measurements or [])
    containers = [m for m in pairs if str(m.get("inner_region_id")) == rid]
    contained = [m for m in pairs if str(m.get("outer_region_id")) == rid]

    # The immediate container is the SMALLEST thing that holds it — the tightest true parent, not
    # the whole frame. Ordering by scale_ratio descending puts the snuggest fit first.
    containers.sort(key=lambda m: -float(m.get("scale_ratio") or 0.0))
    parent = containers[0] if containers else None
    parent_id = str(parent.get("outer_region_id")) if parent else ""

    siblings = ([str(m.get("inner_region_id")) for m in pairs
                 if str(m.get("outer_region_id")) == parent_id
                 and str(m.get("inner_region_id")) != rid] if parent_id else [])

    return {
        "region_id": rid,
        "relation": RELATION_NESTED_WITHIN,
        "parent_id": parent_id,
        "parent_measurement": dict(parent) if parent else None,
        # Chain depth: how many distinct things measurably contain it. The temple's finial sits in
        # the spire which sits in the structure — depth 2 — and that nesting-of-nesting is exactly
        # the higher-order structure systematicity is about.
        "depth": len({str(m.get("outer_region_id")) for m in containers}),
        "sibling_ids": sorted(set(siblings)),
        "sibling_count": len(set(siblings)),
        "descendant_ids": sorted({str(m.get("inner_region_id")) for m in contained}),
        "descendant_count": len({str(m.get("inner_region_id")) for m in contained}),
        "has_relation": bool(parent_id),
        "region_count": len(regions or []),
    }


#: The three components, and the skeleton field each reads. Named once so the decomposition and
#: the score cannot disagree about what they are made of.
COMPONENTS = (("depth", "depth"), ("siblings", "sibling_count"),
              ("descendants", "descendant_count"))


def systematicity(source: Mapping[str, Any], target: Mapping[str, Any], *,
                  aggregation: str = AGGREGATION_SHAPE) -> Dict[str, Any]:
    """How much connected relational structure the two skeletons share, in [0,1].

    Three components, each an alignment of a structural count:

        depth       nesting-of-nesting — a part in a whole that is itself in a whole
        siblings    the container holds other parts too: a system, not a lone pair
        descendants the part is itself a whole for something: structure below as well as above

    NO SURFACE TERM, and no way to add one: this function is handed two skeletons and never sees a
    region, an embedding or a similarity score. That is the guarantee, stated as a signature.

    ## What `absence_share` is for

    `_alignment` scores 0-vs-0 as 1.0, and averaging over all three components therefore pays full
    marks for a component neither side has. WAVE3 measured what that costs: pairs with NO siblings
    and NO descendants on either side average **0.842**, the highest bucket in the corpus, while
    every other level of structure sits between 0.44 and 0.57 — the score falls as real structure
    rises (pearson −0.14). The rule meant to reward systems rewards structural poverty.

    So every result now carries the decomposition: which components had something to compare
    (`live`), which actually agreed (`earned`), and what fraction of the score came from shared
    absence (`absence_share`). A consumer can tell a system from a shared nothing without
    recomputing anything, and `insystematic` stops being a bare number.

    `aggregation="present"` averages only the live components — absence abstains rather than
    agreeing. It is measurably better on both audited criteria and it is NOT the default, because
    reshaping what grounds is a decision to take deliberately and not as a side effect of an audit.
    """
    if aggregation not in AGGREGATIONS:
        raise ValueError(f"aggregation must be one of {AGGREGATIONS}, got {aggregation!r}")

    values, live_flags = {}, {}
    for name, field in COMPONENTS:
        a = float(source.get(field, 0) or 0)
        b = float(target.get(field, 0) or 0)
        values[name] = _alignment(a, b)
        # "Live" means there was something to compare, on at least one side. Absence on BOTH is
        # not disagreement — it is the absence of evidence, which is why it gets its own name.
        live_flags[name] = not (a <= 0 and b <= 0)

    live = [n for n, is_live in live_flags.items() if is_live]
    earned = [n for n in live if values[n] > 0]
    absent_total = sum(values[n] for n, is_live in live_flags.items() if not is_live)

    shape = sum(values.values()) / 3.0
    present = (sum(values[n] for n in live) / len(live)) if live else 1.0
    score = shape if aggregation == AGGREGATION_SHAPE else present

    return {
        "score": round(score, 6),
        "aggregation": aggregation,
        "components": {n: round(v, 6) for n, v in values.items()},
        # The same pair read the other way, always present, so the two rules can be compared on
        # any live result without re-deriving one from the other.
        "shape_score": round(shape, 6),
        "present_score": round(present, 6),
        "live": sorted(live),
        "earned": sorted(earned),
        # How much of `shape_score` is agreement about nothing being there. 0.667 means two of the
        # three components agreed only in that neither side had any.
        "absence_share": round(absent_total / 3.0, 6),
        "source_shape": {k: source.get(k) for k in ("depth", "sibling_count", "descendant_count")},
        "target_shape": {k: target.get(k) for k in ("depth", "sibling_count", "descendant_count")},
    }


def structure_map(source: Mapping[str, Any], target: Mapping[str, Any], *,
                  min_systematicity: float = MIN_SYSTEMATICITY,
                  aggregation: str = AGGREGATION_SHAPE) -> Dict[str, Any]:
    """Map one relational skeleton onto another. The guard, as a verdict.

    Returns `{status, reason, detail, systematicity, correspondences, …}`. `status` is `mapped`
    only when the relation genuinely holds on both sides; otherwise a named refusal.

    THE CORRESPONDENCES ARE THE ANALOGY. `inner_A ↔ inner_B` and `outer_A ↔ outer_B` — and nothing
    in this function ever compared what those four regions look like. A circle in a square maps to
    an arch in a facade here for the same reason it does in Gentner: the mapping is over the
    relation, and the fillers are free to be unalike.
    """
    if not source.get("has_relation"):
        return {"status": "refused", "reason": REFUSED_NO_SOURCE_RELATION,
                "detail": (f"the source region {source.get('region_id')!r} stands in no measured "
                           "nesting relation — there is nothing here to map from"),
                "systematicity": None, "correspondences": []}

    if not target.get("has_relation"):
        # The refusal this lane exists to make. The retina proposed it on appearance; there is no
        # relational structure underneath, so it is a resemblance and not a movement.
        return {"status": "refused", "reason": REFUSED_SURFACE_ONLY,
                "detail": (f"candidate region {target.get('region_id')!r} is contained by nothing "
                           "the organ could measure — this is a surface match, not a relation"),
                "systematicity": None, "correspondences": []}

    if str(target.get("parent_id")) == str(source.get("region_id")) or \
            str(source.get("parent_id")) == str(target.get("region_id")):
        return {"status": "refused", "reason": REFUSED_INVERTED,
                "detail": ("the two regions are the two ends of ONE nesting relation, not two "
                           "instances of it — mapping a relation onto itself proves nothing"),
                "systematicity": None, "correspondences": []}

    sys_score = systematicity(source, target, aggregation=aggregation)
    if sys_score["score"] < float(min_systematicity):
        return {"status": "refused", "reason": "insystematic",
                # The refusal names what it is made of. A bare "0.31 < 0.34" tells a reader
                # nothing about whether the relation is thin or the floor is arbitrary; the
                # components, what was live, and how much came from shared absence do.
                "detail": (f"systematicity {sys_score['score']:.3f} < {min_systematicity} — the "
                           "relation holds on both sides but sits in no shared system of relations "
                           f"(agreed on {sys_score['earned'] or 'nothing'}; "
                           f"{sys_score['absence_share']:.3f} of the shape score was shared "
                           f"absence)"),
                "systematicity": sys_score, "correspondences": []}

    return {
        "status": MAPPED,
        "reason": "",
        "detail": (f"nested_within maps: {source.get('region_id')}→{target.get('region_id')} "
                   f"inside {source.get('parent_id')}→{target.get('parent_id')}, "
                   f"systematicity {sys_score['score']:.3f}"),
        "systematicity": sys_score,
        # Gentner's mapping, made explicit: which element of the base corresponds to which of the
        # target, and in what role.
        "correspondences": [
            {"role": "part", "source": str(source.get("region_id")),
             "target": str(target.get("region_id"))},
            {"role": "whole", "source": str(source.get("parent_id")),
             "target": str(target.get("parent_id"))},
        ],
        "relation": RELATION_NESTED_WITHIN,
    }


def is_surface_only(verdict: Mapping[str, Any]) -> bool:
    """Was this refused for being a resemblance with no relation under it?"""
    return str(verdict.get("reason") or "") == REFUSED_SURFACE_ONLY


def mapped(verdict: Mapping[str, Any]) -> bool:
    return str(verdict.get("status") or "") == MAPPED


def systematicity_score(verdict: Mapping[str, Any]) -> Optional[float]:
    """The score a mapped verdict carries, for `write_edge(systematicity=…)`. None when refused —
    an unmapped candidate has no score, and 0.0 would be a measurement of nothing."""
    sys_score = verdict.get("systematicity")
    if not isinstance(sys_score, Mapping):
        return None
    return float(sys_score.get("score"))
