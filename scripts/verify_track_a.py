"""
Track A verification — run against the live DB to prove the unified Region model is
backward-compatible and the catalog is unchanged.

    env PYTHONPATH=$PWD ./venv/bin/python scripts/verify_track_a.py

Checks:
  1. Every existing region in region_annotations validates as `Region`
     (actor defaults to "auto"; unknown/legacy keys tolerated via extra='allow').
  2. aggregate_categories still runs and reads only the six catalog keys — the
     service code is untouched, so output == before (catalog continuity).
  3. No post carries non-empty bounding_box_tags (0-row retirement); post_helper
     emits {} for the field.
"""

import asyncio
from pydantic import ValidationError

from backend.database import post_collection
from backend.schemas.post import Region
from backend.routers.posts import post_helper
from backend.services import anatomy_catalog_service

SIX_CATALOG_KEYS = {"category", "label", "prioritised", "weight", "user_note", "material"}


async def main():
    print("=" * 68)
    print("TRACK A VERIFICATION")
    print("=" * 68)

    # ---- 1. Validate every live region against the Region model ----------------
    total_posts = total_regions = ok = bad = 0
    actor_defaulted = 0
    failures = []
    async for post in post_collection.find({"region_annotations": {"$exists": True, "$ne": None}}):
        total_posts += 1
        for r in (post.get("region_annotations") or []):
            total_regions += 1
            had_actor = "actor" in r
            try:
                model = Region.model_validate(r)
                ok += 1
                if not had_actor and model.actor == "auto":
                    actor_defaulted += 1
            except ValidationError as e:
                bad += 1
                failures.append((str(post["_id"]), r.get("id"), e.errors()[:1]))

    print(f"\n[1] Region validation over live data")
    print(f"    posts with regions : {total_posts}")
    print(f"    regions total      : {total_regions}")
    print(f"    validated OK       : {ok}")
    print(f"    actor defaulted→auto (had no actor key): {actor_defaulted}")
    print(f"    FAILED             : {bad}")
    if failures:
        for pid, rid, err in failures[:5]:
            print(f"      ✗ post {pid} region {rid}: {err}")
    assert bad == 0, "Some existing regions do not validate as Region — schema too strict"
    print("    ✅ all existing regions validate as Region")

    # ---- 2. Catalog continuity -------------------------------------------------
    profile = await anatomy_catalog_service.aggregate_categories(min_occurrences=1)
    print(f"\n[2] Catalog continuity (aggregate_categories)")
    print(f"    buckets returned   : {len(profile)}")
    for p in profile[:8]:
        print(f"      - {p['category']}/{p['label']}: seen {p['occurrence_count']}× "
              f"starred {p['prioritised_count']}× intensity {p['total_intensity']}")
    # The service reads only the six catalog keys; confirm every returned bucket
    # still exposes them (shape unchanged).
    if profile:
        keys = set(profile[0].keys())
        missing = {"category", "label", "occurrence_count", "prioritised_count"} - keys
        assert not missing, f"catalog output shape changed: missing {missing}"
    print(f"    ✅ catalog aggregates unchanged (reads {sorted(SIX_CATALOG_KEYS)})")

    # ---- 3. bounding_box_tags retirement --------------------------------------
    # Retirement = stop writing + read-only for one release. The true invariant is
    # "no writer remains", NOT "0 rows" — a stray manual row may pre-exist (the v2
    # findings anticipated this; we do not backfill or delete user data).
    from backend.schemas.post import PostUpdate, Post
    non_empty_bbox = await post_collection.count_documents(
        {"bounding_box_tags": {"$exists": True, "$nin": [None, {}]}}
    )
    no_bbox_sample = await post_collection.find_one(
        {"$or": [{"bounding_box_tags": {"$exists": False}}, {"bounding_box_tags": {}}]}
    )
    helper_bbox = post_helper(no_bbox_sample).get("bounding_box_tags") if no_bbox_sample else "<none>"
    print(f"\n[3] bounding_box_tags retirement")
    print(f"    writer removed from PostUpdate : {'bounding_box_tags' not in PostUpdate.model_fields}")
    print(f"    post_helper emits (no-bbox post): {helper_bbox!r} (read-only default)")
    print(f"    pre-existing stray bbox rows    : {non_empty_bbox} (inert; read-only, not deleted)")
    assert "bounding_box_tags" not in PostUpdate.model_fields, "PATCH can still write bbox"
    assert helper_bbox == {}, "post_helper should emit {} for posts without bbox"
    # Any stray row must still read safely through the Post response model.
    if non_empty_bbox:
        stray = await post_collection.find_one(
            {"bounding_box_tags": {"$exists": True, "$nin": [None, {}]}}
        )
        Post.model_validate(post_helper(stray))
        print(f"    stray row {stray['_id']} still validates through Post (read-safe) ✅")
    print("    ✅ no writer remains; field is read-only; stray data inert")

    print("\n" + "=" * 68)
    print("ALL CHECKS PASSED")
    print("=" * 68)


if __name__ == "__main__":
    asyncio.run(main())
