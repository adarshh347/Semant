"""
WAVE4 — a scene's relations, as a derived cache and as the shape a read route serves.

## Why a cache, and why that is not a second ledger

The corpus contains **no committed relations**. Every lane through WAVE3 was suggestions-only, so a
`visual_marks` scan turns up three `region_mask` entries and nothing else. A scene view therefore
has nothing to read — and a route that measured on demand would be worse, because
`adjacency_organ` walks mask boundaries in Python with no decode cache and occlusion needs a GPU
model load.

So `scripts/scene_relations_build.py` derives them once, on the same terms as the retina index:
gitignored, rebuildable, stamped with what produced it.

**The cache is not evidence.** Two rules keep it from becoming one:

  · `hydrate` RE-DERIVES `epistemic` from the recorded basis every time it is read, so a
    hand-edited cache cannot promote a box-basis relation to `measured`. The basis is data; the
    status is a conclusion, and the conclusion is recomputed.
  · `ledger_status` is `proposed` for everything in the cache, always. A relation becomes
    `committed` by appearing in a post's own ledger, which only the curator surface writes. The two
    sources are merged on read and never conflated.

## The four kinds a scene carries

    nesting      A is inside B                    nestedness_organ   within one image
    adjacency    A's edge lies against B's        adjacency_organ    within one image
    occlusion    A is in front of B               occlusion_organ    within one image
    rhyme        A's warmth field rhymes with B's chromatic_relation ACROSS images

The fourth is the one that points out of the scene, and the view has to draw it differently for
that reason: it is the only relation on the page whose far end is not on the page.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from backend.services import region_provenance
from backend.services.agents.observation import LEDGER_PROPOSED
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

#: Bumped when the cached SHAPE changes. A cache written by an older layout is ignored rather than
#: half-read — a stale relation is worse than none, because it is silently wrong.
CACHE_VERSION = 1

CACHE_FILENAME = "scene_relations.json"

#: `proposed` until a human commits, and there is no other value this module can produce. The
#: curator surface owns the transition and this one owns nothing.
LEDGER_COMMITTED = "committed"

#: Rhyme is cross-image and quadratic in regions, so the build caps both sides. A cap that is not
#: reported reads as "these are all the rhymes there are", so `cache_status` carries it.
RHYME_REGION_CAP = 24
RHYME_POST_CAP = 8

#: What a basis is worth. Taken from the organs' shared table rather than restated, so a scene
#: cannot come to disagree with the ruling about what a box supports.
BASIS_EPISTEMIC = {"mask": EpistemicStatus.MEASURED.value,
                   "box": EpistemicStatus.INTERPRETIVE.value}


def epistemic_for(basis: str) -> str:
    """The status a basis supports. Derived on every read — never stored, never trusted."""
    return BASIS_EPISTEMIC.get(str(basis or ""), EpistemicStatus.INTERPRETIVE.value)


def cache_path() -> Path:
    override = os.environ.get("SCENE_RELATIONS_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / CACHE_FILENAME


def row(*, kind: str, axis: str, relation: str, source: str, target: str, basis: str,
        detail: str, organ: str, numbers: Optional[Mapping[str, Any]] = None,
        target_post_id: str = "", supersedes: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """One relation, as the cache stores it.

    NOTE what is absent: no `epistemic_status`, no `ledger_status`. Both are conclusions and both
    are re-derived by `hydrate`. Storing them would make the cache a place where a status could be
    edited into existence.
    """
    return {
        "kind": str(kind), "axis": str(axis), "relation": str(relation),
        "source": str(source), "target": str(target),
        "target_post_id": str(target_post_id or ""),
        "basis": str(basis), "detail": str(detail), "organ": str(organ),
        "numbers": dict(numbers or {}),
        "supersedes": dict(supersedes) if supersedes else None,
    }


def write_cache(payload: Mapping[str, Any]) -> Path:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), default=str))
    os.replace(tmp, path)          # atomic: a half-written cache is never readable
    return path


def load_cache() -> Dict[str, Any]:
    """The cache, or an empty one. Never raises — an unbuilt cache is a build step nobody has run,
    not a broken read, and the route says which."""
    path = cache_path()
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"cache_version": CACHE_VERSION, "built_at": "", "scenes": {},
                "kinds_built": [], "provenance": {}, "missing": True}
    if not isinstance(payload, dict) or payload.get("cache_version") != CACHE_VERSION:
        return {"cache_version": CACHE_VERSION, "built_at": "", "scenes": {},
                "kinds_built": [], "provenance": {}, "stale": True}
    payload.setdefault("scenes", {})
    return payload


def cache_status(payload: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """What the cache is, so a thin scene can be read against how much was actually derived."""
    data = dict(payload if payload is not None else load_cache())
    return {
        "built_at": data.get("built_at") or "",
        "kinds_built": list(data.get("kinds_built") or []),
        "scenes": len(data.get("scenes") or {}),
        "missing": bool(data.get("missing")),
        "stale": bool(data.get("stale")),
        "provenance": dict(data.get("provenance") or {}),
        "caps": {"rhyme_regions_per_post": RHYME_REGION_CAP, "rhyme_posts": RHYME_POST_CAP},
    }


def committed_relations(post: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Relations a curator actually accepted, read off the post's own ledger.

    Empty on this corpus, and that is the finding rather than a gap: nothing has ever been
    committed. The view renders the emptiness rather than hiding it, which is the only way the
    difference between `proposed` and `committed` is visible at all.
    """
    out = []
    for mark in (post.get("visual_marks") or []):
        if str(mark.get("type") or "") != "relation_mark":
            continue
        measurement = dict(mark.get("measurement") or {})
        basis = str(measurement.get("basis") or "")
        out.append({
            "kind": "committed", "axis": str(mark.get("axis") or ""),
            "relation": str(mark.get("relation")
                            or measurement.get("relation") or ""),
            "source": str(mark.get("front_region_id")
                          or measurement.get("inner_region_id") or ""),
            "target": str(mark.get("back_region_id")
                          or measurement.get("outer_region_id") or ""),
            "target_post_id": "", "basis": basis,
            "detail": str(mark.get("detail") or ""),
            "organ": str((mark.get("provenance") or {}).get("producer") or ""),
            "numbers": {k: v for k, v in measurement.items() if isinstance(v, (int, float))},
            "supersedes": None,
            "mark_id": str(mark.get("id") or ""),
            # THE ONE PLACE `committed` IS SAID, and it is said because the mark is IN the ledger.
            "ledger_status": LEDGER_COMMITTED,
            "stated_status": str(mark.get(STATUS_KEY) or ""),
        })
    return out


def hydrate(relation: Mapping[str, Any]) -> Dict[str, Any]:
    """One cached relation → what a reader gets. Where the two statuses are decided.

    `epistemic` is RE-DERIVED from the basis rather than read from the record, so a cache someone
    edited cannot promote a box-basis relation to `measured`. `ledger_status` defaults to
    `proposed` and is only ever `committed` for a relation that came out of a post's own ledger.

    `misstated` exists for the third case: a committed mark whose own stamp does not match what its
    basis supports. The view must be able to show that as a contradiction rather than silently
    preferring one of the two answers.
    """
    out = dict(relation)
    basis = str(out.get("basis") or "")
    supported = epistemic_for(basis)
    out["epistemic"] = supported
    out["ledger_status"] = str(out.get("ledger_status") or LEDGER_PROPOSED)
    stated = str(out.get("stated_status") or "")
    out["misstated"] = bool(stated and stated != supported)
    out["admissible"] = supported == EpistemicStatus.MEASURED.value
    return out


def scene_for(post: Mapping[str, Any], payload: Optional[Mapping[str, Any]] = None
              ) -> Dict[str, Any]:
    """Everything one picture carries: its regions, who drew them, and its relations.

    Regions come with `maker` because a `measured` relation on a mask nobody can attribute is a
    measurement resting on geometry of unknown origin — ORGAN-PROVENANCE-001's point, carried into
    the view so it is visible rather than merely recorded.
    """
    data = dict(payload if payload is not None else load_cache())
    post_id = str(post.get("_id") or "")
    entry = dict((data.get("scenes") or {}).get(post_id) or {})
    cached = entry.get("relations") or {}

    regions = []
    for region in (post.get("region_annotations") or []):
        maker = region_provenance.maker_of(region)
        regions.append({
            "id": str(region.get("id") or ""),
            "label": str(region.get("label") or ""),
            "box": region.get("box"),
            "has_mask": bool(region.get("mask_rle")),
            # The mask's OUTLINE, not its RLE. A COCO run-length encoding is large and not
            # drawable in a browser without decoding it; `polygons` is the same shape the existing
            # `RegionOverlay` already renders, in the same normalized coordinates. `has_mask`
            # stays, so a region whose mask exists but whose outline is missing is still legible
            # as masked rather than silently becoming a box.
            "polygons": region.get("polygons") or ([region["polygon"]]
                                                   if region.get("polygon") else []),
            "maker": maker,
        })

    relations = []
    for kind in ("nesting", "adjacency", "occlusion", "rhyme"):
        for item in (cached.get(kind) or []):
            relations.append(hydrate(item))
    for item in committed_relations(post):
        relations.append(hydrate(item))

    tallies: Dict[str, Any] = {"by_kind": {}, "by_epistemic": {}, "by_ledger": {}}
    for item in relations:
        for key, value in (("by_kind", item["kind"]), ("by_epistemic", item["epistemic"]),
                           ("by_ledger", item["ledger_status"])):
            tallies[key][value] = tallies[key].get(value, 0) + 1

    return {
        "post_id": post_id,
        "photo_url": str(post.get("photo_url") or ""),
        "regions": regions,
        "relations": relations,
        "tallies": tallies,
        "provenance_audit": region_provenance.audit(post.get("region_annotations") or []),
        "cache": cache_status(data),
        # THE TWO ABSENCES, KEPT APART. "Nobody has derived this kind" and "this kind was derived
        # and this picture has none of it" are different claims, and a view that showed them alike
        # would be reporting a gap in the build as a fact about the scene.
        #
        # Got this backwards on the first render: the temple scene said "occlusion not derived"
        # when occlusion HAD been derived corpus-wide and that picture simply has none — the 13
        # are on four other posts. `kinds_built` is what settles it.
        "kinds_absent": sorted(k for k in ("nesting", "adjacency", "occlusion", "rhyme")
                               if k not in (data.get("kinds_built") or [])),
        "kinds_none_here": sorted(k for k in ("nesting", "adjacency", "occlusion", "rhyme")
                                  if k in (data.get("kinds_built") or [])
                                  and not (cached.get(k) or [])),
    }


__all__ = ["CACHE_VERSION", "CACHE_FILENAME", "LEDGER_COMMITTED", "RHYME_REGION_CAP",
           "RHYME_POST_CAP", "BASIS_EPISTEMIC", "epistemic_for", "cache_path", "row",
           "write_cache", "load_cache", "cache_status", "committed_relations", "hydrate",
           "scene_for"]
