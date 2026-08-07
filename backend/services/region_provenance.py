"""REGION-PROV-001 — whose mask did the mark measure?

ORGAN-PROVENANCE-001 settled the rule for organs: **an organ that reads an external artifact must
name that artifact.** Chroma names its pixels, depth names its checkpoint and revision. It then
flagged the one thing it could not reach from where it stood:

    the geometry organs read an external artifact too — THE MASK — and a nestedness mark
    says nothing about which segmenter drew the mask it measured

That gap matters because of the weight masks now carry. `nestedness_organ` grounds `measured`
containment on masks and only on masks (DECISION-movement-grounds-only-on-masks), and Lane M's rule
is that a wrong mask is worse than none. A `measured` relation resting on geometry of unrecorded
origin is the last unattributed artifact in the sensorium.

## What the investigation found, which is not what the gap looked like

The field already existed and the drawers already populate it. `mask_geometry.canonicalize_geometry`
has written `geometry_provenance` since VISION-BUILD-001, and every real segmenter passes its maker
into it — SAM-3, SAM-2 auto, SAM-2 refine, YOLO-seg, SegFormer-ADE, SegFormer-clothes. On the real
corpus **392 of 420 masked regions carry an adapter and a model.**

The 28 that did not were not never-recorded. **They were attributed and then overwritten.**
`canonicalize_geometry` assigned `geometry_provenance` wholesale, so any later pass replaced the
drawer — one refine turned a SAM-3 region's maker into `{recovery: vision-f}`, and
`save-region-annotations` re-canonicalizes every region on every save, so a single save of a
dissected post erased sixty makers at once.

So this lane did not add a field. It stopped a field being destroyed (`MAKER_KEYS` carries forward
through re-canonicalization), and it added the reader below — because a value nothing can ask for is
a value nobody checks.

## Nothing here fabricates, and nothing here backfills

A region drawn before this lane, or by a path that never declared, reads `UNKNOWN` — visibly, with
what it *does* say attached, so a reader can tell "nobody recorded this" from "this was drawn by
hand". Existing posts are not rewritten: the stored documents are exactly as they were, and
`test_region_provenance.py` proves it with a hash. Backfilling would mean inventing a maker for a
mask whose maker nobody knows, which is the fabrication this whole floor exists to prevent.

PURE. No database, no network, no model. Regions in, attribution out.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from backend.services.mask_geometry import MAKER_KEYS, rle_is_valid

#: What a region says when nobody recorded who drew it. A STRING that reads as an answer, because
#: the alternative is `None` and a `None` in a report renders as an empty cell — indistinguishable
#: from a column nobody filled in.
UNKNOWN = "unknown-provenance"

#: The `actor` values that mean a person drew this. A human hand IS a maker, and the honest one for
#: a region the author traced — `region_provenance` reports it rather than calling it unknown, which
#: would confuse "nobody recorded this" with "no model was involved".
HUMAN_ACTORS = frozenset({"creator", "audience"})


def maker_of(region: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Who drew this region's geometry. Always answers; never invents.

    Three shapes, and they are deliberately distinguishable:

        {"kind": "model", "adapter": …, "model": …, …}   a segmenter, named
        {"kind": "human", "actor": "creator"}            a person traced it
        {"kind": "unknown", "recorded": {…}}             nobody recorded it — with whatever the
                                                         region DOES say, so the reader can see
                                                         how much is missing rather than a blank

    The unknown case carries `recorded` on purpose. A region whose provenance says
    `{method: derive-polygon, recovery: vision-f}` is not the same as one with no provenance at all,
    and flattening both to a bare "unknown" would lose the only clue about where to look.
    """
    if not region:
        return {"kind": "unknown", "attributed": False, "recorded": {}, "detail": UNKNOWN}

    prov = region.get("geometry_provenance")
    prov = dict(prov) if isinstance(prov, Mapping) else {}
    maker = {k: v for k, v in prov.items() if k in MAKER_KEYS and v not in (None, "")}

    if maker:
        return {"kind": "model", "attributed": True, **maker,
                "method": prov.get("method"),
                "detail": f"drawn by {maker.get('adapter') or maker.get('model')}"
                          + (f" ({maker['model']})" if maker.get("adapter") and maker.get("model")
                             else "")}

    actor = str(region.get("actor") or "")
    if actor in HUMAN_ACTORS:
        return {"kind": "human", "attributed": True, "actor": actor,
                "detail": f"traced by the {actor}"}

    return {"kind": "unknown", "attributed": False, "recorded": prov,
            "detail": (f"{UNKNOWN}: nothing on this region names who drew it"
                       + (f" (it records {sorted(prov)})" if prov else " (it records nothing)"))}


def is_attributed(region: Optional[Mapping[str, Any]]) -> bool:
    """True when this region's geometry can be traced to a maker. Never guesses."""
    return bool(maker_of(region).get("attributed"))


def grounds_a_measured_claim(region: Optional[Mapping[str, Any]]) -> bool:
    """True when this region carries the mask a `measured` relation would ground on.

    Here rather than in a caller because the AUDIT question is specifically about masks: a
    box-only region's geometry can only support `interpretive` (TWO-STATUS-001), so its unattributed
    state is a smaller thing than an unattributed mask's. This is the set worth counting.
    """
    return bool(region) and rle_is_valid(region.get("mask_rle"))


def audit(regions: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Count the attribution of a post's regions. A report, not a gate.

    Deliberately NOT a filter and NOT a refusal. An unattributed mask is a fact about the corpus's
    history, not a reason to refuse a reading somebody already took — and this lane's honesty floor
    is that nothing which grounded before stops grounding. What changes is that the gap is now
    countable, which is the precondition for anyone deciding to close it.
    """
    masked = [r for r in regions or [] if grounds_a_measured_claim(r)]
    attributed = [r for r in masked if is_attributed(r)]
    kinds: Dict[str, int] = {}
    for region in masked:
        kind = str(maker_of(region).get("kind"))
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "regions": len(list(regions or [])),
        "mask_bearing": len(masked),
        "attributed": len(attributed),
        "unattributed": len(masked) - len(attributed),
        "by_kind": kinds,
        "detail": (f"{len(attributed)}/{len(masked)} mask-bearing regions name a maker"
                   if masked else "no mask-bearing regions"),
    }


def trace(mark: Mapping[str, Any], regions: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """An organ mark → who drew the masks it measured. THE POINT OF THE LANE.

    Note what this is NOT: it does not read a provenance field off the mark, because there isn't
    one and there must not be. ORGAN-PROVENANCE-001's anti-theatre rule says a geometry organ's mark
    may not restate its artifact's provenance — the mark cites region ids, the regions carry their
    makers, and the trace is a join. A copy on the mark would be a second place for the truth to
    live and the one that goes stale when a region is re-drawn.
    """
    measurement = mark.get("measurement") or {}
    by_id = {str(r.get("id")): r for r in regions or []}
    wanted = [str(measurement.get(k) or "") for k in
              ("inner_region_id", "outer_region_id", "region_id")]
    return {
        "mark_id": mark.get("id"),
        "producer": (mark.get("provenance") or {}).get("producer"),
        "basis": measurement.get("basis"),
        "regions": [{"region_id": rid, "maker": maker_of(by_id.get(rid))}
                    for rid in wanted if rid],
    }
