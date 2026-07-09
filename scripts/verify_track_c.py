"""
Track C verification — context-triggered lenses, the Anuraṇana context pack, and the
grounding of the pen. Runs in-process against the live DB (no HTTP, no LLM, no GPU).

    env PYTHONPATH=$PWD ./venv/bin/python scripts/verify_track_c.py

Proves:
  1. Retrieval is OWN-HISTORY-ONLY. Another curator's region — with a byte-identical
     vector, so it ties for nearest — never reaches your context pack. Tested in both
     directions, because a scoping bug that leaks one way often reads fine the other.
  2. The pack is assembled and bounded: the reading, the parts that moved them, their
     taste history, their voice; caps honoured; the current post excluded from its own
     history.
  3. The pen is grounded: ground_prompt front-loads the pack and leaves the ask at the
     tail — and an empty pack is a strict no-op, so every writing path degrades to its
     pre-Track-C behavior.
  4. Lenses are context-triggered and the prior can never close the reading (wildcard).
  5. The reading is evidence-bound and cannot cite a region that isn't on the post.
  6. Regression: aggregate_categories is byte-identical before vs after.

Fixtures are created and deleted by this script. It never mutates a real post.
"""

import asyncio
import math
from datetime import datetime, timezone

from bson import ObjectId

from backend.database import post_collection, region_embeddings_collection
from backend.services import anuranana_service as an
from backend.services import lens_registry as lr
from backend.services import region_embedding_service as res
from backend.services import anatomy_catalog_service
from backend.services.editor_llm_service import ground_prompt, GROUNDING_PREAMBLE
from backend.services.vision_service import vision_service

OWNER = "trackc_owner_fixture"
OTHER = "trackc_other_fixture"
OWN_NOTE = "the give of the silk undoes the structure"
OTHER_NOTE = "PRIVATE — THIS MUST NEVER REACH ANOTHER CURATOR'S PROMPT"

_created_posts: list = []


def _fake_vector(seed: int, dim: int = 512) -> list:
    """A deterministic L2-normalized vector. Retrieval math is what's under test here,
    so we don't need FashionCLIP loaded — and this keeps the script CPU/dep-free."""
    raw = [math.sin(seed * 0.7 + i * 0.013) for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm for v in raw]


def _catalog_fingerprint(profile):
    return sorted(
        (p["category"], p["label"], p["occurrence_count"], p["prioritised_count"],
         p["total_intensity"]) for p in profile
    )


def _region(rid, label, *, note="", prioritised=False, embedding_id=None, category="garment"):
    return {
        "id": rid, "actor": "creator" if note else "auto", "detector": "vision",
        "box": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4}, "label": label,
        "category": category, "material": "", "description": "", "part": None,
        "attributes": [], "embedding_id": embedding_id, "depth": 0, "parent_id": None,
        "prioritised": prioritised, "weight": 3 if prioritised else 0,
        "user_note": note, "block_id": None,
    }


async def _make_post(handle: str, regions: list, *, aletheia=None) -> str:
    doc = {
        "photo_url": f"https://example.invalid/{handle}-{len(_created_posts)}.jpg",
        "photo_public_id": f"fixture_{handle}_{len(_created_posts)}",
        "text_blocks": [], "general_tags": [], "instagram_handle": handle,
        "region_annotations": regions, "updated_at": datetime.now(timezone.utc),
    }
    if aletheia:
        doc["local_context"] = {"commentary": "", "aletheia": aletheia,
                                "updated_at": datetime.now(timezone.utc)}
    result = await post_collection.insert_one(doc)
    _created_posts.append(result.inserted_id)
    return str(result.inserted_id)


async def _vectorize(post_id: str, region_id: str, seed: int) -> str:
    eid = res.make_embedding_id(post_id, region_id)
    await res.upsert_embedding(eid, _fake_vector(seed), model="fashion-clip",
                               post_id=post_id, region_id=region_id)
    return eid


def _capture_writer_payloads(context_pack: str) -> list:
    """Run chat_with_vision against a stubbed Groq client and return every text payload
    that would have gone over the wire — one per pipeline stage. Proves the pack crosses
    the service boundary rather than merely existing, and costs no API call.

    chat_with_vision makes two calls with different message shapes: stage 1 (vision)
    sends a list of content parts, stage 2 (literary refinement) sends a plain string.
    Both are captured, because stage 2 is where voice is decided — grounding only stage 1
    would let the refinement sand the person's voice back off.
    """
    from backend.services import editor_llm_service as els

    captured: list = []

    class _Completions:
        def create(self, *, messages, **kw):
            for message in messages:
                content = message.get("content")
                if isinstance(content, str):
                    captured.append(content)
                elif isinstance(content, list):
                    captured.extend(p["text"] for p in content if p.get("type") == "text")
            reply = type("M", (), {"content": "a long enough answer " * 12})()
            return type("R", (), {"choices": [type("C", (), {"message": reply})()]})()

    class _Client:
        chat = type("Chat", (), {"completions": _Completions()})()

    service = els.EditorLLMService()
    service.client = _Client()
    service.chat_with_vision(
        image_url="https://example.invalid/x.jpg", text_blocks=[],
        user_message="describe the fabric", context_pack=context_pack,
    )
    return captured


READING = {
    "domain": "fashion",
    "lenses": [
        {"name": "Drape", "reading": "the silk's slack fall softens the hard shoulder line",
         "intensity": 78, "evidence": "loose vertical folds below the waist seam",
         "region_ids": ["reg_cur_1"]},
        {"name": "Silhouette", "reading": "the outline is severe, almost architectural",
         "intensity": 61, "evidence": "the squared shoulder", "region_ids": []},
    ],
    "tension": "Silhouette reads severe; Drape reads tender — the image holds both",
    "concealed": "whatever the turned-away face is doing",
    "uncertainty": "the fabric could be a heavy viscose rather than silk",
}


async def build_fixtures():
    """Two curators. Identical vectors on their noted regions, so ONLY the ownership
    scope can separate them — if scoping is broken, the other's note wins on a tie."""
    # The other curator's past: a perfect vector match carrying a private note.
    other_past = await _make_post(OTHER, [_region("reg_oth_1", "hem", note=OTHER_NOTE, prioritised=True)])
    eid = await _vectorize(other_past, "reg_oth_1", seed=1)
    await post_collection.update_one({"_id": ObjectId(other_past)},
                                     {"$set": {"region_annotations.0.embedding_id": eid}})

    # The owner's past: the same vector, their own note.
    own_past = await _make_post(OWNER, [_region("reg_own_1", "sleeve", note=OWN_NOTE, prioritised=True)])
    eid = await _vectorize(own_past, "reg_own_1", seed=1)
    await post_collection.update_one({"_id": ObjectId(own_past)},
                                     {"$set": {"region_annotations.0.embedding_id": eid}})

    # The owner's current image: same vector again, plus a reading. Its own region must
    # not appear in its own taste history.
    current = await _make_post(OWNER, [
        _region("reg_cur_1", "bodice", note="this is the current image's own note", prioritised=True),
    ], aletheia=READING)
    eid = await _vectorize(current, "reg_cur_1", seed=1)
    await post_collection.update_one({"_id": ObjectId(current)},
                                     {"$set": {"region_annotations.0.embedding_id": eid}})

    return current, own_past, other_past


async def cleanup():
    for oid in _created_posts:
        await region_embeddings_collection.delete_many({"post_id": str(oid)})
        await post_collection.delete_one({"_id": oid})


async def main():
    print("=" * 74)
    print("TRACK C VERIFICATION — context-triggered lenses · Anuraṇana · grounded pen")
    print("=" * 74)

    before = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))
    current_id, own_past_id, other_past_id = await build_fixtures()
    print(f"\nfixtures: current={current_id[:8]}… own_past={own_past_id[:8]}… other_past={other_past_id[:8]}…")
    print(f"          all three regions carry the SAME vector (cos=1.0) — only ownership separates them")

    # ---- 1. own-history-only ------------------------------------------------------
    print("\n[1] Retrieval scope (the privacy invariant)")
    post = await post_collection.find_one({"_id": ObjectId(current_id)})
    pack = await an.build_context_pack(post, ask="Write an opening about the fabric.")
    history = pack["sections"]["taste_history"]
    print(f"    own posts searched : {pack['stats']['own_posts_searched']}")
    print(f"    retrieved          : {pack['stats']['retrieved_count']}")
    for note in pack["retrieved"]:
        print(f"      · {note['name']} (cos={note['score']}) \"{note['note'][:48]}…\"")

    assert OTHER_NOTE not in pack["text"], "LEAK: another curator's felt-note reached the pack"
    assert not any(n["post_id"] == other_past_id for n in pack["retrieved"]), "LEAK: other curator's region retrieved"
    assert OWN_NOTE in history, "own past note missing from taste history"
    assert not any(n["post_id"] == current_id for n in pack["retrieved"]), "the post retrieved itself"
    print("    ✅ own note present; other curator's identical-vector note absent; self excluded")

    # symmetry — the other curator gets THEIRS, not the owner's
    other_post = await post_collection.find_one({"_id": ObjectId(other_past_id)})
    other_pack = await an.build_context_pack(other_post)
    assert OWN_NOTE not in other_pack["text"], "LEAK: owner's note reached the other curator"
    print("    ✅ symmetric: the other curator's pack never contains the owner's note")

    # ---- 2. the pack is assembled and bounded ------------------------------------
    print("\n[2] Context pack")
    assert pack["stats"]["has_reading"], "reading section missing"
    assert "Drape" in pack["text"] and "loose vertical folds" in pack["text"], "evidence not carried"
    assert READING["tension"] in pack["text"], "cross-lens tension not carried"
    assert "[PARTS THAT MOVED THEM" in pack["text"], "region notes section missing"
    assert len(pack["retrieved"]) <= an.MAX_RETRIEVED
    assert all(len(n["note"]) <= an.NOTE_CHARS + 1 for n in pack["retrieved"]), "note not truncated"
    order = [pack["text"].index(h) for h in ("[IMAGE READING", "[THE ASK]")]
    assert order == sorted(order), "reading must lead and the ask must close"
    print(f"    sections present   : {[k for k,v in pack['sections'].items() if v]}")
    print(f"    caps               : retrieved<={an.MAX_RETRIEVED}, note<={an.NOTE_CHARS} chars")
    print("    ✅ reading leads, ask closes, caps honoured")

    # ---- 3. the pen is grounded, and degrades ------------------------------------
    print("\n[3] Grounding the pen")
    base = "Analyze this image.\n\nUSER REQUEST: write the opening"
    assert ground_prompt(base, "") == base, "empty pack must be a strict no-op"
    grounded = ground_prompt(base, pack["text"])
    assert grounded.startswith(GROUNDING_PREAMBLE) and grounded.rstrip().endswith("write the opening")
    assert OWN_NOTE in grounded and OTHER_NOTE not in grounded
    unowned = await an.build_context_pack_for_image("https://example.invalid/not-ours.jpg")
    assert unowned["text"] == "" and ground_prompt(base, unowned["text"]) == base
    print("    ✅ pack front-loaded, ask back-loaded; unknown image → empty pack → writer unchanged")

    # The claim is that the pack reaches the MODEL, not merely a prompt string. Stub the
    # Groq client and read back what would have gone over the wire, stage by stage.
    payloads = _capture_writer_payloads(pack["text"])
    grounded_stages = [p for p in payloads if GROUNDING_PREAMBLE in p]
    assert len(payloads) >= 2, f"expected both pipeline stages to fire, saw {len(payloads)}"
    assert len(grounded_stages) >= 2, (
        f"pack reached only {len(grounded_stages)} of {len(payloads)} stages — "
        "stage 2 decides voice and must be grounded too")
    assert any(OWN_NOTE in p for p in grounded_stages), "the felt-note never reached the model"
    assert any("USER REQUEST: describe the fabric" in p for p in payloads), "the ask was lost"
    assert not any(OTHER_NOTE in p for p in payloads), "LEAK: other curator's note sent to the model"
    ungrounded = _capture_writer_payloads("")
    assert not any(GROUNDING_PREAMBLE in p for p in ungrounded), "empty pack still injected a preamble"
    print(f"    ✅ pack present in both user prompts sent to the model "
          f"(vision + literary-refine); the {len(payloads) - len(grounded_stages)} system "
          f"messages carry none, as they should; empty pack sends none")

    # ---- 4. context-triggered lenses + the wildcard -------------------------------
    print("\n[4] Lens selection")
    general, _ = lr.select_lenses()
    assert general == lr.GENERAL_LENSES
    fashion, prov = lr.select_lenses(domain="fashion", attributes=["draped", "flowing", "pleated"])
    assert "Drape" in fashion
    habit = ["Era", "Styling-logic", "Mood/Story"]
    biased, prov2 = lr.select_lenses(domain="fashion", attributes=["draped", "flowing"],
                                     persona_lenses=habit, prior_strength=1.0)
    assert "Drape" in biased, "a habitual lens displaced one the image evidenced"
    assert any(l not in habit for l in biased), "echo chamber: every lens came from history"
    hook, _ = lr.select_lenses(domain="fashion", depth="hook")
    print(f"    no context : {general}")
    print(f"    fashion    : {fashion}  (triggered: {prov['triggered']})")
    print(f"    w/ prior   : {biased}  (wildcard: {prov2['wildcard']})")
    print(f"    hook       : {hook}")
    assert len(hook) == 1
    print("    ✅ domain triggers lenses; evidence outranks habit; wildcard keeps it open")

    # The prior is data-gated: it must be completely inert on a thin corpus.
    ramp = [(n, lr.prior_strength(n)) for n in (0, 1, 2, 3, 6, 9, 12, 40)]
    print(f"    prior ramp : {[(n, round(s,2)) for n, s in ramp]}")
    assert lr.prior_strength(0) == 0.0 and lr.prior_strength(2) == 0.0, "cold start biases"
    assert lr.prior_strength(40) == 1.0 and 0 < lr.prior_strength(7) < 1, "ramp not monotone"
    cold, cold_prov = lr.select_lenses(domain="fashion", attributes=["draped", "flowing"],
                                       persona_lenses=habit, prior_strength=0.0)
    none_at_all, _ = lr.select_lenses(domain="fashion", attributes=["draped", "flowing"])
    assert cold == none_at_all, f"zero-strength prior still steered selection: {cold} vs {none_at_all}"
    assert cold_prov["prior_applied"] == [] and cold_prov["prior_strength"] == 0.0
    print("    ✅ at zero strength a heavy prior is inert — identical to having no persona")

    # ---- 5. evidence-bound reading, no phantom regions ---------------------------
    print("\n[5] Reading schema")
    raw = ('{"lenses":[{"name":"Drape","reading":"r","intensity":150,'
           '"evidence":"folds","region_ids":["reg_cur_1","reg_HALLUCINATED"]}],'
           '"tension":"t","questions":[{"prompt":"p","options":["a","b"]}],'
           '"concealed":"c","uncertainty":"u"}')
    parsed = vision_service._parse_aletheia(raw, valid_region_ids={"reg_cur_1"})
    assert parsed["lenses"][0]["region_ids"] == ["reg_cur_1"], "phantom region id survived"
    assert parsed["lenses"][0]["intensity"] == 100, "intensity not clamped"
    assert parsed["tension"] == "t" and parsed["lenses"][0]["evidence"] == "folds"
    legacy = vision_service._parse_aletheia('{"lenses":[{"name":"L","reading":"r","intensity":5}],"concealed":"c"}')
    assert legacy["lenses"][0]["region_ids"] == [] and legacy["tension"] == ""
    print("    ✅ evidence+tension parsed; hallucinated region id dropped; legacy JSON still parses")

    # ---- 6. catalog regression ----------------------------------------------------
    await cleanup()
    after = _catalog_fingerprint(await anatomy_catalog_service.aggregate_categories(min_occurrences=1))
    print("\n[6] Catalog regression (after fixture cleanup)")
    print(f"    buckets before={len(before)} after={len(after)} identical={before == after}")
    assert before == after, "aggregate_categories changed — Track C perturbed the catalog"
    print("    ✅ catalog buckets identical")

    print("\n" + "=" * 74)
    print("ALL CHECKS PASSED")
    print("=" * 74)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BaseException:
        asyncio.run(cleanup())   # never leave fixtures in the user's DB
        raise
