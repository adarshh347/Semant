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

#: Below this a mapping is one shared predicate with nothing holding it up. Not a hard truth — it
#: is a stated, tunable floor, and every result carries its own score so a caller can disagree.
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


def systematicity(source: Mapping[str, Any], target: Mapping[str, Any]) -> Dict[str, Any]:
    """How much connected relational structure the two skeletons share, in [0,1].

    Three components, each an alignment of a structural count, averaged:

        depth       nesting-of-nesting — a part in a whole that is itself in a whole
        siblings    the container holds other parts too: a system, not a lone pair
        descendants the part is itself a whole for something: structure below as well as above

    NO SURFACE TERM, and no way to add one: this function is handed two skeletons and never sees a
    region, an embedding or a similarity score. That is the guarantee, stated as a signature.
    """
    depth = _alignment(source.get("depth", 0), target.get("depth", 0))
    siblings = _alignment(source.get("sibling_count", 0), target.get("sibling_count", 0))
    descendants = _alignment(source.get("descendant_count", 0), target.get("descendant_count", 0))
    score = round((depth + siblings + descendants) / 3.0, 6)
    return {
        "score": score,
        "components": {"depth": round(depth, 6), "siblings": round(siblings, 6),
                       "descendants": round(descendants, 6)},
        "source_shape": {k: source.get(k) for k in ("depth", "sibling_count", "descendant_count")},
        "target_shape": {k: target.get(k) for k in ("depth", "sibling_count", "descendant_count")},
    }


def structure_map(source: Mapping[str, Any], target: Mapping[str, Any], *,
                  min_systematicity: float = MIN_SYSTEMATICITY) -> Dict[str, Any]:
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

    sys_score = systematicity(source, target)
    if sys_score["score"] < float(min_systematicity):
        return {"status": "refused", "reason": "insystematic",
                "detail": (f"systematicity {sys_score['score']:.3f} < {min_systematicity} — the "
                           "relation holds on both sides but sits in no shared system of relations"),
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
