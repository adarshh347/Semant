#!/usr/bin/env python3
"""
PERCEPTUAL-FORMS-001D — the synthetic controls the structural Topology forms are tested against.

WHY A SECOND FIXTURE SCRIPT. `perception_lab_topology_fixtures.py` builds scenes for measuring ONE
PAIR: a rectangle inside a rectangle, two rectangles touching. The structural forms are about what
happens when there are five of them and the answers have to compose, so they need scenes whose
STRUCTURE is known in advance rather than scenes whose measurement is:

    forest      basin ⊂ fountain ⊂ court, and niche ⊂ wall. Two roots, one of them three deep,
                and a redundant basin ⊂ court that a transitive reduction must absorb rather than
                drop
    piers       four rectangles in a row, each abutting the next and no others, plus an island
                nothing touches. The nave at Wells, at 40x60
    ambiguous   one rectangle inside two overlapping rectangles that do not contain each other.
                Its parentage is genuinely undecidable and no tree may pick one
    revision    the same two instances at two geometry revisions: apart at rev 0, touching at
                rev 1
    one_pixel   an instance whose containment fraction sits at 0.9574 at rev 0 and 0.9474 at rev
                1, because ONE PIXEL moved. `nestedness_organ.MIN_CONTAINMENT` is 0.95, so the
                relation disappears — and the instance is the same instance, which is the whole
                point of the control

EVERY SCENE IS WRITTEN TWICE. Once as the `extent_set` artifact a topology operation consumes, and
once as the `topology_relation_set` artifact the façade produced FROM it. The second is what these
producers actually read, and committing it means the structural suite reads records rather than
re-running a measurement — so a change in `topology.py` shows up here, in `--check`, as a diff a
person reads, instead of silently changing what the composition suite was testing.

    python scripts/perception_lab_topology_form_fixtures.py            # write them
    python scripts/perception_lab_topology_form_fixtures.py --check    # exit 1 if they drifted

Writes nothing outside `research/perception_lab/fixtures/topology_forms/`. No database, no network,
no model.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.schemas.perception_lab import PerceptualArtifact  # noqa: E402
from backend.services import mask_geometry as mg  # noqa: E402
from backend.services.perception_lab import topology as T  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "research" / "perception_lab" / "fixtures" / "topology_forms"

#: The same 40x60 frame Lane C's controls use. Every measurement below walks every pixel in pure
#: Python, and a scene of five instances is ten pairs.
H, W = 40, 60

DIGEST = "sha256:70909a17c0d5e4b2"
NOW = "2026-08-10T12:00:00Z"


# ── geometry, restated from Lane C's generator rather than imported ──────────
#
# A fixture script that imported another fixture script would make one scene's rectangles depend on
# another scene's helper, and the two sets of controls are meant to be independently readable.


def rect_rle(rects: Sequence[Tuple[int, int, int, int]], h: int = H,
             w: int = W) -> Dict[str, Any]:
    """COCO RLE for a union of half-open rectangles `(x0, x1, y0, y1)`, column-major like the rest
    of this repository's masks."""
    bits = bytearray(h * w)
    for x0, x1, y0, y1 in rects:
        for x in range(x0, x1):
            for y in range(y0, y1):
                bits[x * h + y] = 1
    counts: List[int] = []
    run, value = 0, 0
    for bit in bits:
        if bit == value:
            run += 1
        else:
            counts.append(run)
            run, value = 1, bit
    counts.append(run)
    return {"size": [h, w], "counts": counts}


def instance(instance_id: str, rects: Sequence[Tuple[int, int, int, int]], *,
             region_id: Optional[str] = None,
             geometry_rev: Optional[int] = None) -> Dict[str, Any]:
    rle = rect_rle(rects)
    return {"instance_id": instance_id, "mask_rle": rle,
            "box": mg.rle_bbox_norm(rle) if mg.rle_area(rle) else None,
            "area": round(mg.rle_area(rle) / float(H * W), 6),
            "confidence": None, "naming": None,
            "region_id": region_id, "geometry_rev": geometry_rev}


def named(instance_id: str, rects: Sequence[Tuple[int, int, int, int]], label: str,
          **kw: Any) -> Dict[str, Any]:
    """An instance carrying a LABEL. Used by exactly one control: the two piers a person called the
    same thing, which must stay two nodes."""
    out = instance(instance_id, rects, **kw)
    out["naming"] = {"text": label, "source": "human", "confidence": None,
                     "epistemic_status": "interpretive"}
    return out


def extent_set(artifact_id: str, *, searched: str, instances: List[Dict[str, Any]],
               scope: str = "session") -> Dict[str, Any]:
    return {
        "identity": {
            "artifact_id": artifact_id, "session_id": "labs_topology_forms",
            "run_id": "run_fixture_topology_forms", "step_id": "step_extent",
            "organ_family": "extent", "artifact_kind": "extent_set",
            "operation": "extent.reuse", "identity_scope": scope,
            "identity_refs": [{"region_id": i["region_id"], "geometry_rev": i["geometry_rev"],
                               "scope": "canonical"}
                              for i in instances if i.get("region_id")],
            "input_refs": [], "derived_from": [],
        },
        "measurement": {
            "payload_variant": "extent_set",
            "payload": {"variant": "extent_set", "searched": searched, "instances": instances,
                        "dropped_below_min_area": None, "duplicates": [], "comparison": None},
            "data_ref": None, "coordinate_system": "normalized_xy_topleft",
            "epistemic_status": "measured", "epistemic_basis": "mask",
            "basis_detail": f"synthetic control geometry on a {H}x{W} raster",
        },
        "projection": {"projection_kind": "mask_fill",
                       "hints": {"opacity": 0.35, "palette_role": "figure"}},
        "interpretation": {"label": None, "label_source": "none", "epistemic_status": "uncertain",
                           "notes": "a control scene: rectangles, and no claim about any picture"},
        "lifecycle": {"status": "proposed", "changed_at": NOW,
                      "changed_by": "perception_lab_fixture"},
        "provenance": {"producer_kind": "fixture",
                       "producer": "perception_lab_topology_form_fixtures", "adapter": None,
                       "model": None, "revision": None, "source_image_digest": DIGEST,
                       "started_at": None, "completed_at": None, "duration_ms": None,
                       "device": None, "peak_memory_mb": None},
    }


# ── the scenes ───────────────────────────────────────────────────────────────
#
# Named once so the tests import the same numbers the fixtures were built from. A test that
# hardcoded a coordinate would keep passing after somebody moved a rectangle.

#: basin ⊂ fountain ⊂ court, and niche ⊂ wall. Five instances, ten unordered pairs, two roots.
#: The nesting is three deep on one side so that the transitive reduction has something to reduce:
#: `basin ⊂ court` is measured AND implied, and the tree must hold the nearer holder.
FOREST: Dict[str, Tuple[int, int, int, int]] = {
    "court": (2, 40, 2, 30),
    "fountain": (10, 22, 10, 20),
    "basin": (14, 18, 13, 17),
    "wall": (44, 58, 2, 20),
    "niche": (48, 54, 6, 14),
}

#: Four piers in a row, each abutting the next; an island nothing touches. Two of the piers carry
#: the SAME human label, which is the control for "a label never merges two identities".
PIERS: Dict[str, Tuple[int, int, int, int]] = {
    "pier_1": (4, 16, 4, 28),
    "pier_2": (16, 28, 4, 28),
    "pier_3": (28, 40, 4, 28),
    "pier_4": (40, 52, 4, 28),
    "island": (6, 22, 34, 40),
}

#: One rectangle inside two rectangles that overlap each other and contain neither. `inner` is
#: genuinely in two places and no tree may choose.
AMBIGUOUS: Dict[str, Tuple[int, int, int, int]] = {
    "left_hall": (2, 34, 4, 34),
    "right_hall": (18, 56, 4, 34),
    "inner": (22, 30, 14, 24),
}

#: The same two instances at two revisions: a gap of two columns at rev 0, closed at rev 1.
#: `bar` grows and `post` does not, so exactly one endpoint is revised — which is what makes the
#: transition a transition rather than a re-measurement.
REVISION_A: Dict[str, Tuple[int, int, int, int]] = {
    "bar": (10, 20, 10, 30),
    "post": (22, 30, 10, 30),
}
REVISION_B: Dict[str, Tuple[int, int, int, int]] = {
    "bar": (10, 22, 10, 30),
    "post": (22, 30, 10, 30),
}

#: THE ONE-PIXEL CONTROL. `outer` is 30x20 = 600 px. `inner` is a 10x9 block wholly inside it plus
#: a nub that pokes out of the bottom edge:
#:
#:     rev 0   90 inside + 4 outside = 94 px, containment 90/94 = 0.957447  →  nested
#:     rev 1   90 inside + 5 outside = 95 px, containment 90/95 = 0.947368  →  NOT nested
#:
#: `nestedness_organ.MIN_CONTAINMENT` is 0.95, so one pixel moves the verdict across it. The
#: instance is the same instance at both revisions, and a transition that treated the crossing as
#: an identity change would be inventing an object.
ONE_PIXEL_OUTER = (10, 40, 10, 30)
ONE_PIXEL_CORE = (20, 30, 20, 29)
ONE_PIXEL_NUB_4 = (20, 24, 30, 31)
ONE_PIXEL_NUB_5 = (20, 25, 30, 31)


def scenes() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    out["extent-set.forest.json"] = extent_set(
        "art_forms_forest",
        searched="a control: two nested families, one of them three levels deep",
        instances=[instance(k, [FOREST[k]], region_id=f"reg_{k}", geometry_rev=1)
                   for k in ("court", "fountain", "basin", "wall", "niche")],
        scope="canonical")

    out["extent-set.piers.json"] = extent_set(
        "art_forms_piers",
        searched="a control: four piers in a row and an island nothing touches",
        instances=[named("pier_1", [PIERS["pier_1"]], "pier"),
                   named("pier_2", [PIERS["pier_2"]], "pier"),
                   instance("pier_3", [PIERS["pier_3"]]),
                   instance("pier_4", [PIERS["pier_4"]]),
                   instance("island", [PIERS["island"]])])

    out["extent-set.ambiguous.json"] = extent_set(
        "art_forms_ambiguous",
        searched="a control: one shape inside two overlapping shapes that contain neither",
        instances=[instance(k, [AMBIGUOUS[k]]) for k in ("left_hall", "right_hall", "inner")])

    out["extent-set.revision-0.json"] = extent_set(
        "art_forms_revision", searched="a control: two shapes two columns apart, at revision 0",
        instances=[instance("bar", [REVISION_A["bar"]], region_id="reg_bar", geometry_rev=0),
                   instance("post", [REVISION_A["post"]], region_id="reg_post", geometry_rev=0)],
        scope="canonical")

    out["extent-set.revision-1.json"] = extent_set(
        "art_forms_revision", searched="a control: the same two shapes, the gap closed, revision 1",
        instances=[instance("bar", [REVISION_B["bar"]], region_id="reg_bar", geometry_rev=1),
                   instance("post", [REVISION_A["post"]], region_id="reg_post", geometry_rev=0)],
        scope="canonical")

    out["extent-set.one-pixel-0.json"] = extent_set(
        "art_forms_one_pixel",
        searched="a control: containment at 0.9574, four pixels outside, revision 0",
        instances=[instance("inner", [ONE_PIXEL_CORE, ONE_PIXEL_NUB_4],
                            region_id="reg_inner", geometry_rev=0),
                   instance("outer", [ONE_PIXEL_OUTER], region_id="reg_outer", geometry_rev=0)],
        scope="canonical")

    out["extent-set.one-pixel-1.json"] = extent_set(
        "art_forms_one_pixel",
        searched="a control: containment at 0.9474, five pixels outside, revision 1",
        instances=[instance("inner", [ONE_PIXEL_CORE, ONE_PIXEL_NUB_5],
                            region_id="reg_inner", geometry_rev=1),
                   instance("outer", [ONE_PIXEL_OUTER], region_id="reg_outer", geometry_rev=0)],
        scope="canonical")
    return out


# ── the relation sets the façade measures from them ──────────────────────────


def relation_set(scene: Dict[str, Any], instance_ids: Sequence[str], *, run_id: str,
                 artifact_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run `topology.all_pairs` over a scene and return the artifact it produced.

    THE REAL FAÇADE, not a hand-written relation list. These fixtures exist to prove a composition
    reads what a measurement writes, and a hand-written input would prove it reads what this script
    imagines a measurement writes. `--check` is therefore also a drift alarm on `topology.py`.
    """
    request = T.TopologyRequest(
        operation="topology.all_pairs",
        context=T.LabContext(session_id="labs_topology_forms", run_id=run_id, step_id="step_pairs",
                             source_image_digest=DIGEST, now=NOW, artifact_id=artifact_id),
        inputs=tuple(T.topology_input(role="members",
                                      artifact_id=scene["identity"]["artifact_id"],
                                      instance_id=i) for i in instance_ids),
        parameters=parameters or {"max_regions": 8}, extents=(scene,))
    result = T.run(request)
    if result.refused:
        raise SystemExit(f"the façade refused {artifact_id}: {result.refusal.message}")
    return json.loads(result.artifact.model_dump_json())


def relation_sets(built: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        "relations.forest.json": relation_set(
            built["extent-set.forest.json"],
            ["court", "fountain", "basin", "wall", "niche"],
            run_id="run_forest", artifact_id="art_forms_rel_forest"),
        "relations.piers.json": relation_set(
            built["extent-set.piers.json"],
            ["pier_1", "pier_2", "pier_3", "pier_4", "island"],
            run_id="run_piers", artifact_id="art_forms_rel_piers"),
        "relations.ambiguous.json": relation_set(
            built["extent-set.ambiguous.json"], ["left_hall", "right_hall", "inner"],
            run_id="run_ambiguous", artifact_id="art_forms_rel_ambiguous"),
        "relations.revision-0.json": relation_set(
            built["extent-set.revision-0.json"], ["bar", "post"],
            run_id="run_rev_0", artifact_id="art_forms_rel_rev_0"),
        "relations.revision-1.json": relation_set(
            built["extent-set.revision-1.json"], ["bar", "post"],
            run_id="run_rev_1", artifact_id="art_forms_rel_rev_1"),
        "relations.one-pixel-0.json": relation_set(
            built["extent-set.one-pixel-0.json"], ["inner", "outer"],
            run_id="run_px_0", artifact_id="art_forms_rel_px_0"),
        "relations.one-pixel-1.json": relation_set(
            built["extent-set.one-pixel-1.json"], ["inner", "outer"],
            run_id="run_px_1", artifact_id="art_forms_rel_px_1"),
    }


README = """\
# Structural topology controls (generated)

Synthetic scenes for `backend/services/perception_lab/topology_forms/`, generated by
`scripts/perception_lab_topology_form_fixtures.py`. Do not edit them by hand — edit the script and
re-run it; `backend/tests/test_perception_lab_topology_forms.py` runs `--check` and fails if they
drift.

Each scene is written twice: as the `extent_set` artifact a topology operation consumes, and as the
`topology_relation_set` artifact `topology.all_pairs` measured from it. The structural producers
read the second.

| scene | what it controls |
|---|---|
| `forest` | basin ⊂ fountain ⊂ court, niche ⊂ wall — two roots, one three deep, one redundant edge |
| `piers` | four abutting piers and an island; two piers share a human label and stay two nodes |
| `ambiguous` | one shape inside two overlapping shapes that contain neither |
| `revision-0` / `revision-1` | the same pair two columns apart, then touching: one endpoint revised |
| `one-pixel-0` / `one-pixel-1` | containment 0.957447 → 0.947368 across `MIN_CONTAINMENT` = 0.95 |

The rectangles are half-open `(x0, x1, y0, y1)` on a 40x60 raster, so every answer is known before
the organ runs.
"""


def write(check: bool) -> int:
    built = scenes()
    for name, doc in built.items():
        PerceptualArtifact.model_validate(doc)
    everything = dict(built)
    everything.update(relation_sets(built))
    for name, doc in everything.items():
        PerceptualArtifact.model_validate(doc)

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    drift: List[str] = []
    for name, doc in sorted(everything.items()):
        path = FIXTURE_DIR / name
        text = json.dumps(doc, indent=2, sort_keys=False) + "\n"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                drift.append(name)
        else:
            path.write_text(text, encoding="utf-8")
    readme = FIXTURE_DIR / "README.md"
    if check:
        if not readme.exists() or readme.read_text(encoding="utf-8") != README:
            drift.append("README.md")
    else:
        readme.write_text(README, encoding="utf-8")

    if drift:
        print("drifted: " + ", ".join(sorted(drift)), file=sys.stderr)
        return 1
    print(f"{'checked' if check else 'wrote'} {len(everything)} controls in {FIXTURE_DIR}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the committed controls differ from what this script builds")
    return write(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
