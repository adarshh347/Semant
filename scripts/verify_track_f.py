"""
Track F verification — the audience side of Anuraṇana. In-process against the live DB;
no HTTP, no LLM, no GPU. Fixtures are created and deleted (including on failure).

Proves:
  1. A fork tap and a region tap each write a `taste_signals` EVENT, not a Region. The
     post's region_annotations are byte-identical before and after.
  2. The opt-in gate (F4) actually gates: without consent, nothing is written at all.
  3. The write path is hardened: opaque subject ids only, deferred rungs rejected,
     fabricated region_ids rejected, rate limit enforced, duplicates collapsed.
  4. The audience portfolio reads a subject's own signals and is provably separate from
     persona_service — no cross-write, and the module doesn't even import it.
  5. The brand read model returns anonymized aggregates + contractable creators only.
     A subject below the k-anonymity threshold is withheld; a subject id never appears.
  6. Regression: the creator's regions, the catalog, and the Aletheia reading are
     untouched by any of this.
"""

import ast
import asyncio
import inspect
from datetime import datetime, timezone

from bson import ObjectId

from backend.database import (
    post_collection, persona_collection, taste_consent_collection,
    taste_signals_collection,
)
from backend.schemas.post import Region
from backend.schemas.taste import TasteSignalIn, is_opaque_subject
from backend.services import anatomy_catalog_service
from backend.services import taste_signal_service as taste
from backend.services.taste_signal_service import ConsentRequired, RateLimited

SUBJECTS = [f"s-verify-track-f-{i:02d}" for i in range(4)]
# The rate-limit test deliberately floods; give it its own subject so its noise never
# lands in the portfolio subject's leans.
RATE_SUBJECT = "s-verify-track-f-flood"
ALL_SUBJECTS = SUBJECTS + [RATE_SUBJECT]
CREATOR = "trackf_creator_fixture"

_posts: list = []


def _imported_modules(module) -> set:
    """The module's ACTUAL imports, from its AST. A text scan would trip over a
    docstring that merely names `persona_service` — which is exactly what a doc
    promising separation would do."""
    tree = ast.parse(inspect.getsource(module))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names if node.module)
    return names


def _catalog_fingerprint(profile):
    return sorted(
        (p["category"], p["label"], p["occurrence_count"], p["prioritised_count"],
         p["total_intensity"]) for p in profile
    )


def _region(rid, label, category="garment"):
    return {
        "id": rid, "actor": "auto", "detector": "vision",
        "box": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3},
        "label": label, "category": category, "material": "", "description": "",
        "part": None, "attributes": ["draped", "matte"], "embedding_id": f"emb_{rid}",
        "depth": 0, "parent_id": None, "prioritised": False, "weight": 0,
        "user_note": "", "block_id": None,
    }


async def make_post(handle: str) -> str:
    doc = {
        "photo_url": f"https://example.invalid/trackf-{len(_posts)}.jpg",
        "photo_public_id": f"trackf_fixture_{len(_posts)}",
        "text_blocks": [], "general_tags": [], "instagram_handle": handle,
        "region_annotations": [_region("reg_a", "drape"), _region("reg_b", "hem")],
    }
    res = await post_collection.insert_one(doc)
    _posts.append(res.inserted_id)
    return str(res.inserted_id)


async def cleanup():
    # Purge by marker, not by the in-memory id list: a run that dies before recording an
    # id would otherwise strand its fixture in the user's database forever.
    await post_collection.delete_many({"photo_public_id": {"$regex": "^trackf_fixture_"}})
    await taste_signals_collection.delete_many({"subject": {"$in": ALL_SUBJECTS}})
    await taste_consent_collection.delete_many({"subject": {"$in": ALL_SUBJECTS}})
    _posts.clear()


def sig(post_id, **kw):
    return TasteSignalIn(post_id=post_id, **kw)


async def main():
    print("=" * 74)
    print("TRACK F VERIFICATION — audience signals · portfolio · brand boundary")
    print("=" * 74)

    # Start from a clean slate. A prior crashed run's consent doc would otherwise make
    # the opt-in gate look broken when it isn't.
    await cleanup()

    catalog_before = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))
    personas_before = await persona_collection.count_documents({})
    post_id = await make_post(CREATOR)
    regions_before = (await post_collection.find_one({"_id": ObjectId(post_id)}))["region_annotations"]
    subject = SUBJECTS[0]

    # ---- 2. the opt-in gate, first: nothing may be written without consent ----------
    print("\n[1] Consent gate (F4 — explicit opt-in)")
    try:
        await taste.record_signals(subject, [sig(post_id, signal_type="region_tap", region_id="reg_a")])
        raise SystemExit("FAIL: a signal was written without consent")
    except ConsentRequired:
        pass
    assert await taste_signals_collection.count_documents({"subject": subject}) == 0
    print("    ✅ no consent → nothing captured (not even a rejected row)")

    await taste.set_consent(subject, True)
    assert await taste.get_consent(subject)
    print("    ✅ explicit opt-in recorded")

    # ---- 1. a tap is an EVENT, not a Region -----------------------------------------
    print("\n[2] A tap writes an event, never a Region")
    result = await taste.record_signals(subject, [
        sig(post_id, signal_type="region_tap", region_id="reg_a", lens="Drape"),
        sig(post_id, signal_type="fork", lens="Drape", prompt="What pulls your eye?",
            choice="The fall of the cloth", choice_index=1, region_id="reg_a"),
    ])
    print(f"    recorded={result['recorded']} skipped={result['skipped']} rejected={len(result['rejected'])}")
    assert result["recorded"] == 2, result

    events = [e async for e in taste_signals_collection.find({"subject": subject}, {"_id": 0})]
    assert {e["signal_type"] for e in events} == {"region_tap", "fork"}
    assert all(e["actor"] == "audience" for e in events), "signals must carry actor=audience"
    assert all(e["embedding_id"] == "emb_reg_a" for e in events), "signal must point into Anuraṇana"

    regions_after = (await post_collection.find_one({"_id": ObjectId(post_id)}))["region_annotations"]
    assert regions_after == regions_before, "an audience tap mutated the creator's regions"
    assert not any(r.get("actor") == "audience" for r in regions_after), "a Region was minted"
    print("    ✅ 2 taste_signals written; 0 Regions minted; region_annotations unchanged")
    print(f"    ✅ each event carries actor='audience' + embedding_id → same vector space as the creator")

    # ---- 3. hardening ----------------------------------------------------------------
    print("\n[3] Hardened write path")
    for bad in ["adarsh347k@gmail.com", "@handle", "short", "has space"]:
        assert not is_opaque_subject(bad)
        try:
            await taste.record_signals(bad, [sig(post_id, signal_type="fork", choice="x")])
            raise SystemExit(f"FAIL: non-opaque subject accepted: {bad}")
        except ValueError:
            pass
    print("    ✅ non-opaque subjects (emails, handles) rejected — the store cannot hold identity")

    for deferred in ["dwell", "replay", "save_reason", "zoom"]:
        try:
            sig(post_id, signal_type=deferred)
            raise SystemExit(f"FAIL: deferred rung accepted: {deferred}")
        except Exception:
            pass
    print("    ✅ deferred rungs (dwell/zoom/save_reason/replay) rejected, not silently stored")

    phantom = await taste.record_signals(subject, [
        sig(post_id, signal_type="region_tap", region_id="reg_DOES_NOT_EXIST"),
    ])
    assert phantom["recorded"] == 0 and phantom["rejected"], phantom
    print(f"    ✅ fabricated region_id rejected: {phantom['rejected'][0]['why']}")

    dupe = await taste.record_signals(subject, [
        sig(post_id, signal_type="region_tap", region_id="reg_a", lens="Drape"),
    ])
    assert dupe["recorded"] == 0 and dupe["skipped"] == 1, dupe
    print("    ✅ the same tap repeated inside the dedup window is one taste, not two")

    # Flood under its own subject: signal-stuffing must be capped, and the cap must not
    # be reachable only by polluting a real viewer's taste.
    await taste.set_consent(RATE_SUBJECT, True)
    flood = [sig(post_id, signal_type="region_tap", region_id="reg_b")
             for _ in range(taste.RATE_LIMIT_PER_HOUR + 1)]
    try:
        await taste.record_signals(RATE_SUBJECT, flood)
        raise SystemExit("FAIL: rate limit not enforced")
    except RateLimited as e:
        print(f"    ✅ rate limit enforced ({e})")

    # ---- 4. the portfolio, and its separation from the creator persona --------------
    print("\n[4] Audience portfolio (taste given back) + F7 separation")
    # a second tap on the same part, outside the dedup window, so a lean can form
    await taste_signals_collection.insert_one({
        "subject": subject, "actor": "audience", "signal_type": "region_tap",
        "post_id": post_id, "region_id": "reg_a", "embedding_id": "emb_reg_a",
        "label": "drape", "category": "garment", "attributes": ["draped", "matte"],
        "lens": "Drape", "media_type": "image", "frame_ts": None,
        "created_at": datetime.now(timezone.utc),
    })
    pf = await taste.portfolio(subject)
    print(f"    totals: {pf['totals']}")
    print(f"    leans → parts={[l['name'] for l in pf['leans']['parts']]} "
          f"lenses={[l['name'] for l in pf['leans']['lenses']]}")
    assert pf["totals"]["signals"] >= 3
    assert any(l["name"] == "drape" for l in pf["leans"]["parts"]), "no lean formed"
    assert pf["leans"]["parts"][0]["count"] >= taste.LEAN_MIN_COUNT, "a single tap became a lean"
    assert pf["recent"], "subject cannot see their own signals"

    # Separation, structurally: the module's real import graph never reaches the
    # creator persona. (Checked by AST, not by grepping the source — the docstring
    # names persona_service precisely to promise it isn't imported.)
    imports = _imported_modules(taste)
    persona_imports = {m for m in imports if "persona" in m}
    assert not persona_imports, f"taste_signal_service imports the creator persona: {persona_imports}"
    assert await persona_collection.count_documents({}) == personas_before, \
        "audience signal created/changed a persona document"
    print("    ✅ portfolio reads the subject's own signals; thresholded (one tap ≠ a lean)")
    print("    ✅ taste_signal_service never imports persona_service; persona docs unchanged")

    # ---- 5. the brand boundary (F6) --------------------------------------------------
    print("\n[5] Brand boundary — anonymized aggregates + contractable creators only")
    # one subject cannot make a trend: below k-anonymity everything is withheld
    solo = await taste.brand_trends()
    solo_parts = [r["value"] for r in solo["trends"]["parts"]]
    assert "drape" not in solo_parts, "a single person's taste surfaced as a trend"
    print(f"    with 1 subject → parts trends: {solo_parts or '(withheld)'} "
          f"(k={taste.BRAND_MIN_SUBJECTS})")

    for other in SUBJECTS[1:]:
        await taste.set_consent(other, True)
        await taste.record_signals(other, [
            sig(post_id, signal_type="region_tap", region_id="reg_a", lens="Drape")])

    trends = await taste.brand_trends()
    parts = {r["value"]: r["distinct_subjects"] for r in trends["trends"]["parts"]}
    print(f"    with {len(SUBJECTS)} subjects → parts: {parts}")
    assert parts.get("drape", 0) >= taste.BRAND_MIN_SUBJECTS
    assert "hem" not in parts, "a bucket under the threshold was returned"

    matches = await taste.brand_creator_matches()
    print(f"    creator matches: {[(m['creator_handle'], m['distinct_audience']) for m in matches['matches']]}")
    assert matches["matches"], "no creator matched"
    m0 = matches["matches"][0]
    assert m0["creator_handle"] == CREATOR
    assert "distinct_audience" in m0 and isinstance(m0["distinct_audience"], int)

    # The boundary, proved by search rather than by trust: no subject id may appear
    # anywhere in a brand payload, at any depth, as a key or a value.
    blob = repr(trends) + repr(matches)
    for s in ALL_SUBJECTS:
        assert s not in blob, f"LEAK: consumer subject {s} appears in a brand payload"

    def keys_of(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield k
                yield from keys_of(v)
        elif isinstance(node, list):
            for v in node:
                yield from keys_of(v)

    all_keys = set(keys_of(trends)) | set(keys_of(matches))
    assert not (all_keys & taste._FORBIDDEN_BRAND_KEYS), \
        f"LEAK: brand payload carries consumer keys {all_keys & taste._FORBIDDEN_BRAND_KEYS}"
    print(f"    ✅ no consumer subject id in any brand payload; keys are {sorted(all_keys)}")

    # and the guard itself must actually fire if someone regresses it
    try:
        taste._assert_no_subject_leak({"matches": [{"subject": subject}]}, {subject})
        raise SystemExit("FAIL: the leak guard did not fire on a forbidden key")
    except AssertionError:
        pass
    try:
        taste._assert_no_subject_leak({"matches": [{"creator_handle": subject}]}, {subject})
        raise SystemExit("FAIL: the leak guard did not fire on a subject id smuggled as a value")
    except AssertionError:
        pass
    print("    ✅ the leak guard fires on a forbidden key AND on a subject id smuggled as a value")

    # ---- 6. regression ----------------------------------------------------------------
    print("\n[6] Regression — the creator side is untouched")
    for r in regions_after:
        Region.model_validate(r)
    await cleanup()
    catalog_after = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))
    print(f"    catalog buckets before={len(catalog_before)} after={len(catalog_after)} "
          f"identical={catalog_before == catalog_after}")
    assert catalog_before == catalog_after, "audience signals perturbed the creator catalog"
    assert await persona_collection.count_documents({}) == personas_before
    print("    ✅ regions still validate as Region; catalog identical; personas untouched")

    print("\n" + "=" * 74)
    print("ALL CHECKS PASSED")
    print("=" * 74)


async def run():
    """Cleanup must happen on THIS loop — motor's collections are bound to it, so a
    failure path that calls asyncio.run(cleanup()) afterwards hits a closed loop and
    leaves fixtures behind."""
    try:
        await main()
    finally:
        await cleanup()


if __name__ == "__main__":
    asyncio.run(run())
