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

## Agreement is agreement about things that exist (WAVE3)

`_alignment` scores 0-vs-0 as 1.0 — and until WAVE3 the score averaged all three components, so a
component NEITHER side had was paid full marks. The floor audit
(`scripts/systematicity_floor_audit.py`, 129,564 cross-image gate-eligible pairs) measured what
that cost, and it was an inversion rather than a rounding error:

    mean score by total sibling+descendant structure across both sides
      structure =  0    n =   894    0.842      <- the highest bucket in the corpus
      structure =  4    n =  2830    0.572
      structure = 11    n =  4230    0.444
    pearson(real structure, score) = -0.14      the score FELL as structure rose

**The rule meant to reward systems rewarded structural poverty**, and 45.6% of everything that
passed the floor depended on credit for components neither side had. Two regions agreeing that
neither of them contains anything is not a shared system of relations; it is a shared absence, and
Gentner's principle is about the relations that are *there*.

So the default aggregation is now `present`: **a component counts toward agreement only where at
least one side has structure.** Absence abstains instead of agreeing. Measured against a held-out
criterion the gate never reads — *do the two CONTAINERS also map?*, a system extending past the
pair itself — this raises separation from **+20.3 to +25.7 points** and takes the inversion from
−0.14 to −0.03. `shape` stays runnable so the thing it replaced remains measurable.

Honest about the residual: −0.03 is **not zero**. The inversion is 79% removed, not eliminated.

### The floor did not survive the change, and is now free

WAVE3's floor lane derived `MIN_SYSTEMATICITY` as `ONE_COMPONENT_SHARE + eps` — a real derivation,
valid only for `shape`, where there were always exactly three components. Under `present` the mean
is over the LIVE components, so "one component's worth" is 1/3, 1/2 or 1/1 depending on how many
were live, and no scalar expresses it. The adaptive rule that would — `score > 1/live` — was
measured and is **worse** (+18.5 vs +25.7): it refuses all 894 single-live pairs, whose containers
map 54.1% of the time against a 30.8% base rate. See `MIN_SYSTEMATICITY` for why the number is held
where it is anyway.

**One floor still does not cover two organs.** `relational_structure` is nesting-shaped — it
hard-codes `RELATION_NESTED_WITHIN`, and it picks the immediate parent by `scale_ratio`, a field
only the nestedness organ sets. Run it over `adjacency_organ`'s output and it still returns a
skeleton, but "parent" then means *the neighbour that happened to sort first*, and where that
organ's directional contact measure comes out symmetric, `depth` and `descendant_count` stop being
independent counts. A relation-specific floor is owed before adjacency movement is built here.

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

#: How the three components are combined.
#:
#:   `present`  averaged over the components where at least one side HAS structure. Absence
#:              abstains rather than agreeing. THE DEFAULT since WAVE3.
#:   `shape`    all three averaged, 0-vs-0 counted as perfect agreement. The WAVE2 rule, kept
#:              runnable so the change it replaced stays measurable rather than remembered.
#:
#: The switch is justified in the module docstring and by `scripts/systematicity_floor_audit.py`,
#: not by taste: `shape` made structural poverty outscore structure, and `present` does not.
AGGREGATION_SHAPE = "shape"
AGGREGATION_PRESENT = "present"
AGGREGATIONS = (AGGREGATION_PRESENT, AGGREGATION_SHAPE)

#: The default. Named rather than repeated at three call sites, so switching it is one edit and
#: every signature agrees about what it was.
DEFAULT_AGGREGATION = AGGREGATION_PRESENT

#: What one component's worth of agreement came to under `shape`: three components, always three,
#: so one of them was always exactly a third. **Dead as a derivation** — kept because it is what
#: `AGGREGATION_SHAPE` still means and because the arithmetic below is the clearest statement of
#: why it does not survive.
ONE_COMPONENT_SHARE = 1.0 / 3.0

#: Retained for `AGGREGATION_SHAPE` only: the epsilon that put the WAVE2 floor above the 1/3 atom.
SYSTEMATICITY_EPSILON = 0.00667

#: Below this a mapping does not clear the bar. **A FREE PARAMETER, with no derivation left.**
#:
#: WAVE3's floor audit derived this from `ONE_COMPONENT_SHARE + SYSTEMATICITY_EPSILON` — a real
#: derivation, and one that died with the aggregation it assumed. Under `present` the score is a
#: mean over the LIVE components, so "one component's worth" is no longer a single number:
#:
#:     live = 3  →  1/3 = 0.333     49.2% of pairs
#:     live = 2  →  1/2 = 0.500     50.1% of pairs
#:     live = 1  →  1/1 = 1.000      0.7% of pairs
#:
#: No scalar expresses "more than one predicate" across all three, and the adaptive rule that
#: does — `score > 1/live` — was MEASURED and is worse: **+18.5 points** against the held-out
#: criterion versus +25.7 for this flat floor. It refuses all 894 single-live pairs, and those
#: pairs' containers map 54.1% of the time against a 30.8% base rate. They are the best pairs in
#: the corpus and the principled-sounding rule throws every one of them away. That is the second
#: time in two lanes that the plausible structural rule lost to the external criterion.
#:
#: So the value is held at what it was, deliberately and for a stated reason:
#:
#:   · separation is FLAT across 0.15–0.60 (+25.7 to +29.6, non-monotonic). Nothing selects a
#:     value, and picking the argmax of a flat noisy curve is fitting.
#:   · holding it constant isolates the aggregation change. Move both and the before/after
#:     measures two things at once and attributes neither.
#:
#: It is now an OPERATING POINT — it says how much of the corpus the gate admits (56.2% under
#: `present`, against 73.4% under `shape`) and nothing about where truth begins.
MIN_SYSTEMATICITY = 0.34


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
                  aggregation: str = DEFAULT_AGGREGATION) -> Dict[str, Any]:
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
                  aggregation: str = DEFAULT_AGGREGATION) -> Dict[str, Any]:
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
