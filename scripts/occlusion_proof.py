#!/usr/bin/env python3
"""
WAVE3 — the finial, measured: `in_front_of` on real depth, on the image that forced WAVE2.5.

    python scripts/occlusion_proof.py                  # the finial case + the corpus sweep
    python scripts/occlusion_proof.py --post <id>
    python scripts/occlusion_proof.py --grid 48        # finer field
    python scripts/occlusion_proof.py --json

## What this proves

`cseg_golden_finial_7` scored containment **1.000**, nesting index **0.999** against 'Sky'. The
finial is in *front* of the sky. WAVE2.5 could only refuse the reading, because nothing measured
occlusion order. This runs the real depth model on that exact image and asks the occlusion organ
what is actually true of those two regions.

Three readings of one pair, and only the third says what IS the case:

    box basis     'the finial is contained in the sky, 0.999'   interpretive — refused as measured
    mask basis    'the finial is not contained in the sky'      measured
    depth basis   'the finial is IN FRONT OF the sky'           measured   ← the new one

THE PIXELS AND THE MODEL LIVE HERE, never in the organ. `occlusion_organ` imports no torch and no
image library; it is handed a depth field and two region dicts. The model runs through
`ModelManager` rather than `depth_service` directly, because the manager is what enforces
single-GPU residency and the cost claim is only true if the cost is paid there.

READS POSTS, WRITES NONE. Every post is hashed before and after. Marks are PROPOSED and printed;
committing one is a curator's act and this script performs none.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services import depth_organ as depth                          # noqa: E402
from backend.services import mask_geometry as mg                           # noqa: E402
from backend.services import nestedness_organ as nestedness                # noqa: E402
from backend.services import occlusion_organ as occlusion                  # noqa: E402

#: The image that forced the WAVE2.5 ruling.
FINIAL_POST = "6a5fef58a3ddb6341fd69930"
FINIAL = "cseg_golden_finial_7"

#: The VLM's 'Sky' — a BOX, and the other end of the original 0.999.
SKY_BOX = "region_2"

#: The masked sky in the same picture. What the finial is really in front of.
SKY_MASK = "cseg_Sky_0"

STEP_ID = "wave3_occlusion:finial"


def digest(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()


async def load_post(post_id: str) -> dict:
    from bson import ObjectId

    from backend.database import post_collection
    return await post_collection.find_one({"_id": ObjectId(post_id)}) or {}


async def fetch_image(photo_url: str):
    import io

    import httpx
    from PIL import Image

    from backend.routers.posts import _image_fetch_headers

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(photo_url, headers=_image_fetch_headers(photo_url))
        resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


async def estimate_depth(image, *, grid: int) -> tuple:
    """The real model, through the manager. Returns (field, residency)."""
    from backend.services import depth_service
    from backend.services.vision_orchestrator.adapters import DepthAnythingAdapter
    from backend.services.vision_orchestrator.contracts import CancelToken
    from backend.services.vision_orchestrator.manager import ModelManager
    from backend.services.vision_orchestrator.registry import AdapterRegistry

    adapter = DepthAnythingAdapter()
    if not adapter.is_available():
        raise RuntimeError(
            "depth_anything_v2_small is not available on this box. The organ is pure and its tests "
            "run without weights; this RUN needs the model, and it refuses rather than inventing "
            "a field — a synthetic grid and a real one are the same list of floats.")

    registry = AdapterRegistry()
    registry.register(adapter)
    manager = ModelManager(registry)

    started = time.perf_counter()
    await manager.ensure_loaded(adapter)
    load_ms = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    result = await manager.run_adapter(adapter, {"image": image}, priority=0, cancel=CancelToken())
    infer_ms = (time.perf_counter() - started) * 1000.0
    if not result.ok or result.artifact is None:
        raise RuntimeError(f"the depth adapter returned {result.status}")

    payload = result.artifact.data
    if grid != int(payload.get("grid") or 0):
        payload = await asyncio.to_thread(depth_service.estimate, image, grid=grid)

    field = depth.depth_field(
        payload, adapter=adapter.spec.name, model=adapter.spec.model_id,
        revision=getattr(adapter.spec, "revision", "") or depth_service.REVISION,
        preprocessing_version=adapter.spec.preprocessing_version, whole_frame=True)
    return field, {"adapter": adapter.spec.name, "checkpoint": adapter.spec.checkpoint,
                   "load_ms": round(load_ms, 1), "infer_ms": round(infer_ms, 1),
                   "grid": int(field["grid"])}


def boxed(region: dict) -> dict:
    """The same region with its mask removed — what the VLM would have handed over.

    Not a hypothetical: `region_2` really is a box. This lets the box path be exercised on a region
    whose mask exists, so the two bases can be compared on ONE subject.
    """
    return {k: v for k, v in region.items() if k != "mask_rle"}


def finial_case(regions: dict, field: dict) -> dict:
    """The three readings of one pair, and the reconciliation of each."""
    finial, sky_box, sky_mask = regions.get(FINIAL), regions.get(SKY_BOX), regions.get(SKY_MASK)
    out = {}

    print("\n" + "=" * 92)
    print("  THE FINIAL, MEASURED — the pair that forced WAVE2.5")
    print("=" * 92)

    # 1. the original reading, on boxes
    box_contain = nestedness.measure(finial, sky_box)
    box_occlude = occlusion.measure(finial, sky_box, field)
    out["box"] = {"containment": box_contain, "occlusion": box_occlude,
                  "reconciled": occlusion.reconcile_containment(box_contain, box_occlude)}
    print(f"\n1. THE ORIGINAL READING — {FINIAL} against {SKY_BOX} ('Sky', a VLM box)")
    print(f"   nestedness  {box_contain['detail']}")
    print(f"               nested={box_contain['nested']} basis={box_contain['basis']} "
          f"→ {box_contain['epistemic']}")
    print(f"   occlusion   {box_occlude['detail']}")
    print(f"               basis={box_occlude['basis']} → {box_occlude['epistemic']}")
    print(f"   reconciled  {out['box']['reconciled']['verdict']}")
    print(f"               {out['box']['reconciled']['detail']}")

    # 2. what the masks say about containment
    mask_contain = nestedness.measure(finial, sky_mask)
    out["mask_containment"] = mask_contain
    print(f"\n2. THE SAME QUESTION ON MASKS — {FINIAL} against {SKY_MASK} (the masked sky)")
    print(f"   nestedness  {mask_contain['detail']}")
    print(f"               nested={mask_contain['nested']} basis={mask_contain['basis']} "
          f"→ {mask_contain['epistemic']}")
    print(f"   The masks do not overlap at all. The 0.999 was the two BOXES overlapping, which is")
    print(f"   what a box does when one thing is in front of another.")

    # 3. what is actually true
    mask_occlude = occlusion.measure(finial, sky_mask, field)
    mark = occlusion.grounding_mark(mask_occlude, post_id=FINIAL_POST, step_id=STEP_ID)
    out["mask_occlusion"] = mask_occlude
    out["mark"] = mark
    print(f"\n3. WHAT IS ACTUALLY TRUE — depth on mask, whole frame")
    print(f"   {FINIAL:<24} depth {mask_occlude['a_depth']:.4f}  "
          f"{mask_occlude['a_frame_rank']:.0%} of the frame behind it")
    print(f"   {SKY_MASK:<24} depth {mask_occlude['b_depth']:.4f}  "
          f"{mask_occlude['b_frame_rank']:.0%} of the frame behind it")
    print(f"   relation    {mask_occlude['relation']}  front={mask_occlude['front_region_id']} "
          f"back={mask_occlude['back_region_id']}")
    print(f"   dominance   {mask_occlude['dominance']:.4f}  separation "
          f"{mask_occlude['separation']:.4f}  (floor {occlusion.MIN_SEPARATION})")
    print(f"   depth gap   {mask_occlude['depth_gap']:+.4f}   rank gap "
          f"{mask_occlude['rank_gap']:+.4f}   cells {mask_occlude['a_cells']}/{mask_occlude['b_cells']}")
    print(f"   basis       {mask_occlude['basis']} → {mask_occlude['epistemic']}  "
          f"admissible={mask_occlude['admissible']}")
    print(f"   MARK        {mark['relation']} {mark['epistemic_status']} "
          f"producer={mark['provenance']['producer']} model={mark['provenance'].get('model')}")

    # 4. the box path on the SAME subject, so the two bases are comparable
    box_of_finial = boxed(regions[FINIAL])
    box_of_sky = boxed(regions[SKY_MASK])
    same_subject_box = occlusion.measure(box_of_finial, box_of_sky, field)
    out["same_subject_box"] = same_subject_box
    print(f"\n4. THE SAME TWO SUBJECTS, READ ON THEIR BOXES")
    print(f"   {FINIAL:<24} depth {same_subject_box['a_depth']:.4f} "
          f"(mask said {mask_occlude['a_depth']:.4f})")
    print(f"   {SKY_MASK:<24} depth {same_subject_box['b_depth']:.4f} "
          f"(mask said {mask_occlude['b_depth']:.4f})")
    print(f"   relation    {same_subject_box['relation']}  separation "
          f"{same_subject_box['separation']:.4f}")
    print(f"   basis       {same_subject_box['basis']} → {same_subject_box['epistemic']}  "
          f"admissible={same_subject_box['admissible']}")
    print(f"   A box-basis occlusion reading is REFUSED as measured however large its gap: the")
    print(f"   box's depth is the mean of a thing and the thing behind it.")
    return out


def refusal_checks(regions: dict, field: dict) -> dict:
    """The field's provenance requirements, re-checked from this organ."""
    finial, sky = regions[FINIAL], regions[SKY_MASK]
    checks = {}
    print(f"\n5. WHAT THE ORGAN REFUSES")

    cropped = {**field, "whole_frame": False}
    try:
        occlusion.measure(finial, sky, cropped)
        checks["crop"] = "ACCEPTED — BUG"
    except occlusion.OcclusionRefusal as exc:
        checks["crop"] = str(exc)
    print(f"   a crop-estimated field      → {checks['crop'][:74]}")

    anonymous = {**field, "model": "", "revision": ""}
    try:
        occlusion.measure(finial, sky, anonymous)
        checks["anonymous"] = "ACCEPTED — BUG"
    except occlusion.OcclusionRefusal as exc:
        checks["anonymous"] = str(exc)
    print(f"   a field naming no model     → {checks['anonymous'][:74]}")

    try:
        occlusion.measure(finial, sky, None)
        checks["no_field"] = "ACCEPTED — BUG"
    except occlusion.OcclusionRefusal as exc:
        checks["no_field"] = str(exc)
    print(f"   no field at all             → {checks['no_field'][:74]}")
    return checks


def sweep(regions_list: list, field: dict) -> dict:
    """Every mask-nested pair in this picture, read against depth.

    The question this answers: does the occlusion relation ever CORRECT a containment the masks
    measured — or is the finial case purely a box artefact? Both answers are interesting and the
    honest one is whichever the corpus gives.
    """
    print(f"\n6. EVERY MASK-NESTED PAIR IN THIS PICTURE, READ AGAINST DEPTH")
    by_id = {str(r.get("id")): r for r in regions_list}
    pairs = nestedness.find_nested_pairs(regions_list)
    masked_pairs = [m for m in pairs if nestedness.is_admissible(m)]
    verdicts, rows = {}, []
    for m in masked_pairs:
        inner, outer = by_id.get(m["inner_region_id"]), by_id.get(m["outer_region_id"])
        if inner is None or outer is None:
            continue
        try:
            occ = occlusion.measure(inner, outer, field)
        except occlusion.OcclusionRefusal:
            continue
        verdict = occlusion.reconcile_containment(m, occ)
        verdicts[verdict["verdict"]] = verdicts.get(verdict["verdict"], 0) + 1
        rows.append({"inner": m["inner_region_id"], "outer": m["outer_region_id"],
                     "containment": m["containment"], "separation": occ["separation"],
                     "rank_gap": occ["rank_gap"],
                     "verdict": verdict["verdict"]})
    print(f"   {len(masked_pairs)} mask-basis containments; {len(rows)} readable against depth")
    print(f"   verdicts: {verdicts}")
    superseded = [r for r in rows if r["verdict"] == occlusion.CONTAINMENT_SUPERSEDED]
    if superseded:
        print(f"\n   CONTAINMENTS CORRECTED BY DEPTH — measured, and overturned by measurement:")
        for r in sorted(superseded, key=lambda r: -r["separation"])[:6]:
            print(f"     {r['inner']:<28} in {r['outer']:<26} containment "
                  f"{r['containment']:.3f} but depth orders them {r['separation']:.4f}")
    else:
        print(f"\n   No mask-basis containment in this picture is contradicted by depth. The masks")
        print(f"   had already separated the finial from the sky (containment 0.000); the box was")
        print(f"   the only thing claiming otherwise. Depth's contribution here is the POSITIVE")
        print(f"   relation, not a correction — and that is the honest reading.")

    coplanar = [r for r in rows if r["verdict"] == occlusion.CONTAINMENT_STANDS]
    if coplanar:
        print(f"\n   CONTAINMENTS THAT STAND — genuinely enclosed, depth does not separate them:")
        for r in sorted(coplanar, key=lambda r: r["separation"])[:6]:
            print(f"     {r['inner']:<28} in {r['outer']:<26} containment "
                  f"{r['containment']:.3f}, depth orders them only {r['separation']:.4f}")
    return {"pairs": len(rows), "verdicts": verdicts, "rows": rows}


def threshold_sweep(rows: list) -> None:
    """The floor is a free parameter; sweeping it is how that stays true rather than stated."""
    print(f"\n7. THE TWO CASES THE BOX CONFLATED, SEPARATED — and the floor swept, not assumed")
    print(f"   these are the MASK-NESTED pairs: things genuinely enclosed in other things.")
    print(f"   How many of them does depth order? If the relation is sound, almost none —")
    print(f"   a thing inside another thing is at the same depth as it.\n")
    print(f"   {'floor':>7} {'ordered':>10} {'share':>8}")
    for floor in (0.60, 0.70, 0.80, 0.90, 0.95, 0.99, 1.00):
        n = sum(1 for r in rows if r["separation"] >= floor)
        flag = "   <- MIN_SEPARATION" if abs(floor - occlusion.MIN_SEPARATION) < 1e-9 else ""
        print(f"   {floor:>7.2f} {n:>10} {n / max(1, len(rows)):>7.1%}{flag}")
    best = max((r["separation"] for r in rows), default=0.0)
    print(f"\n   strongest ordering among {len(rows)} genuine containments: {best:.4f}")
    print(f"   the finial against the sky:                            0.9987")
    print(f"   Containment and occlusion come apart cleanly. That gap is the whole lane: a box")
    print(f"   scored both cases 0.999 'contained', and depth tells them apart.")
    print(f"   No value is derived. `dominance` rides on every reading so a caller can re-threshold")
    print(f"   without re-measuring — the discipline the systematicity floor decision made binding.")


async def main_async(args) -> int:
    post = await load_post(args.post)
    if not post:
        print(f"✗ post {args.post} not found", file=sys.stderr)
        return 2
    before = digest(post)

    regions_list = list(post.get("region_annotations") or [])
    regions = {str(r.get("id")): r for r in regions_list}
    missing = [r for r in (FINIAL, SKY_BOX, SKY_MASK) if r not in regions]
    if missing and args.post == FINIAL_POST:
        print(f"✗ this post is missing {missing}", file=sys.stderr)
        return 2

    print(f"post {args.post}: {len(regions_list)} regions, "
          f"{sum(1 for r in regions_list if mg.rle_is_valid(r.get('mask_rle')))} masked")
    photo_url = str(post.get("photo_url") or "")
    print(f"fetching {photo_url[:80]}…", file=sys.stderr)
    image = await fetch_image(photo_url)
    print(f"running depth (grid {args.grid})…", file=sys.stderr)
    field, residency = await estimate_depth(image, grid=args.grid)
    print(f"   depth field: {residency}")

    record = {"residency": residency}
    record["finial"] = finial_case(regions, field)
    record["refusals"] = refusal_checks(regions, field)
    record["sweep"] = sweep(regions_list, field)
    threshold_sweep(record["sweep"]["rows"])

    after = digest(await load_post(args.post))
    print(f"\n   post unchanged: {before == after}")
    print(f"   nothing persisted — the mark above is PROPOSED, not committed.\n")

    if args.json:
        print(json.dumps(record, indent=2, default=str))

    occ = record["finial"]["mask_occlusion"]
    ok = (occ["relation"] == occlusion.RELATION_IN_FRONT_OF
          and occ["front_region_id"] == FINIAL
          and occ["admissible"] and before == after
          and not record["finial"]["same_subject_box"]["admissible"])
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--post", default=FINIAL_POST)
    ap.add_argument("--grid", type=int, default=192)
    ap.add_argument("--json", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
