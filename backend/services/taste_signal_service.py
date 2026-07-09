"""
Taste signals (Darshan Track F) — the audience write path, the portfolio read model,
and the brand aggregate, with the privacy boundary enforced in code rather than in a
comment.

Three surfaces over one store:

  · **Audience write** — a tap becomes a `taste_signals` event referencing an existing
    region/embedding. Gated on explicit opt-in (F4), rate-limited, deduped, and
    validated against the post's real regions so a fabricated `region_id` can't enter
    the graph. No PII: a subject is an opaque session/account id.

  · **Audience read (the portfolio)** — "taste given back, not harvested." A subject
    sees their own eye reflected back, and can delete it. This module never imports
    `persona_service`: audience taste is not creator voice, and F7 makes that a
    structural separation, not a promise.

  · **Brand read** — anonymized aggregate taste trends plus *contractable creator*
    matches. Never identified consumer profiles. Two mechanisms hold that line:
    k-anonymity (a bucket below `BRAND_MIN_SUBJECTS` distinct subjects is dropped,
    not returned) and `_assert_no_subject_leak`, which inspects every brand payload
    before it leaves and raises rather than shipping a consumer identifier.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from bson import ObjectId
from bson.errors import InvalidId

from backend.database import (
    post_collection, taste_consent_collection, taste_signals_collection,
)
from backend.schemas.taste import (
    ACCEPTED_SIGNALS, SIGNAL_FORK, SIGNAL_REGION_TAP, is_opaque_subject,
)

# Abuse limits. A flood of fake taps must not poison Anuraṇana, so the write path caps
# volume and the read paths never trust a single event.
RATE_LIMIT_PER_HOUR = 300
DEDUP_WINDOW_SECONDS = 30      # the same tap repeated is one taste, not many

# k-anonymity for the brand tier. A taste trend backed by fewer than this many distinct
# people is not a trend — it is a person, and brands do not get people.
BRAND_MIN_SUBJECTS = 3
# Aggregation threshold for the portfolio: nothing single-shot is trusted as a "lean".
LEAN_MIN_COUNT = 2


class ConsentRequired(PermissionError):
    """Raised when a subject has not explicitly opted in (F4)."""


class RateLimited(RuntimeError):
    """Raised when a subject exceeds the hourly signal cap."""


async def ensure_indexes() -> None:
    """Index what the read paths filter on. Non-fatal: a failure costs speed, not
    correctness, and must not take the API down at boot."""
    try:
        await taste_signals_collection.create_index("subject", name="subject_idx")
        await taste_signals_collection.create_index("post_id", name="post_idx")
        await taste_signals_collection.create_index("created_at", name="created_idx")
        await taste_consent_collection.create_index(
            "subject", name="consent_subject_unique", unique=True)
    except Exception as e:
        print(f"⚠️ taste_signals index creation skipped (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Consent (F4 — explicit opt-in)
# ---------------------------------------------------------------------------
async def get_consent(subject: str) -> bool:
    doc = await taste_consent_collection.find_one({"subject": subject}, {"_id": 0})
    return bool(doc and doc.get("opted_in"))


async def set_consent(subject: str, opted_in: bool) -> dict:
    now = datetime.now(timezone.utc)
    await taste_consent_collection.update_one(
        {"subject": subject},
        {"$set": {"subject": subject, "opted_in": bool(opted_in), "updated_at": now}},
        upsert=True,
    )
    return {"subject": subject, "opted_in": bool(opted_in), "updated_at": now}


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------
def _to_object_id(pid: str) -> Optional[ObjectId]:
    try:
        return ObjectId(pid)
    except (InvalidId, TypeError):
        return None


async def _regions_of(post_id: str) -> Dict[str, dict]:
    """The post's real regions, by id. A signal may only reference one of these."""
    obj_id = _to_object_id(post_id)
    if obj_id is None:
        return {}
    doc = await post_collection.find_one({"_id": obj_id}, {"region_annotations": 1})
    if not doc:
        return {}
    return {r["id"]: r for r in (doc.get("region_annotations") or []) if r.get("id")}


async def _rate_check(subject: str, incoming: int) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = await taste_signals_collection.count_documents(
        {"subject": subject, "created_at": {"$gte": since}}
    )
    if recent + incoming > RATE_LIMIT_PER_HOUR:
        raise RateLimited(
            f"signal cap reached ({RATE_LIMIT_PER_HOUR}/hour); {recent} already recorded"
        )


async def _is_duplicate(subject: str, doc: dict) -> bool:
    since = datetime.now(timezone.utc) - timedelta(seconds=DEDUP_WINDOW_SECONDS)
    return bool(await taste_signals_collection.find_one({
        "subject": subject, "post_id": doc["post_id"], "region_id": doc.get("region_id"),
        "signal_type": doc["signal_type"], "choice": doc.get("choice"),
        "created_at": {"$gte": since},
    }))


async def record_signals(subject: str, signals: List) -> dict:
    """
    Persist a batch of audience reactions. Returns `{recorded, skipped, rejected}`.

    Every signal is checked against the post's actual regions: a `region_id` that isn't
    on the post is rejected, not stored. Anuraṇana is a graph of real parts, and letting
    a client invent nodes in it would be the cheapest possible way to poison it.
    """
    if not is_opaque_subject(subject):
        raise ValueError("subject must be an opaque session/account id")
    if not await get_consent(subject):
        raise ConsentRequired("taste capture requires explicit opt-in")
    if not signals:
        return {"recorded": 0, "skipped": 0, "rejected": []}

    await _rate_check(subject, len(signals))

    now = datetime.now(timezone.utc)
    region_cache: Dict[str, Dict[str, dict]] = {}
    docs, rejected, skipped = [], [], 0

    for sig in signals:
        if sig.signal_type not in ACCEPTED_SIGNALS:      # belt-and-braces; schema also gates
            rejected.append({"post_id": sig.post_id, "why": "signal_type not accepted"})
            continue

        if sig.post_id not in region_cache:
            region_cache[sig.post_id] = await _regions_of(sig.post_id)
        regions = region_cache[sig.post_id]
        if not regions:
            rejected.append({"post_id": sig.post_id, "why": "unknown post or no regions"})
            continue

        region = None
        if sig.region_id:
            region = regions.get(sig.region_id)
            if region is None:
                rejected.append({"post_id": sig.post_id, "region_id": sig.region_id,
                                 "why": "region not on this post"})
                continue
        elif sig.signal_type == SIGNAL_REGION_TAP:
            rejected.append({"post_id": sig.post_id, "why": "region_tap needs a region_id"})
            continue

        doc = {
            "subject": subject,               # opaque; the only identity in this store
            "actor": "audience",
            "signal_type": sig.signal_type,
            "post_id": sig.post_id,
            "region_id": sig.region_id,
            # The pointer into Anuraṇana — this is what makes an audience tap and a
            # creator's note comparable in one vector space.
            "embedding_id": (region or {}).get("embedding_id"),
            "label": (region or {}).get("label"),
            "category": (region or {}).get("category"),
            "attributes": (region or {}).get("attributes") or [],
            "lens": sig.lens,
            "prompt": sig.prompt,
            "choice": sig.choice,
            "choice_index": sig.choice_index,
            "media_type": sig.media_type,     # video-ready; unused by the image loop
            "frame_ts": sig.frame_ts,
            "created_at": now,
        }

        if await _is_duplicate(subject, doc):
            skipped += 1
            continue
        docs.append(doc)

    if docs:
        await taste_signals_collection.insert_many(docs)
    return {"recorded": len(docs), "skipped": skipped, "rejected": rejected}


# ---------------------------------------------------------------------------
# Audience read — the portfolio ("taste given back")
# ---------------------------------------------------------------------------
def _rank(counter: Dict[str, int], min_count: int = 1) -> List[dict]:
    return [{"name": k, "count": v}
            for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
            if v >= min_count]


async def portfolio(subject: str) -> dict:
    """
    This subject's own eye, read back to them. Aggregated, never single-shot: a lean
    needs `LEAN_MIN_COUNT` signals behind it, because one tap is noise and a pattern of
    taps is a taste.

    Deliberately does not touch `persona_collection` — audience taste never becomes
    creator voice (F7).
    """
    if not is_opaque_subject(subject):
        raise ValueError("subject must be an opaque session/account id")

    parts, categories, attributes, lenses = {}, {}, {}, {}
    posts, embedding_ids, total = set(), set(), 0
    recent: List[dict] = []

    cursor = taste_signals_collection.find({"subject": subject}, {"_id": 0}).sort("created_at", -1)
    async for sig in cursor:
        total += 1
        posts.add(sig["post_id"])
        if sig.get("embedding_id"):
            embedding_ids.add(sig["embedding_id"])
        if sig.get("label"):
            parts[sig["label"]] = parts.get(sig["label"], 0) + 1
        if sig.get("category"):
            categories[sig["category"]] = categories.get(sig["category"], 0) + 1
        for attr in sig.get("attributes") or []:
            attributes[attr] = attributes.get(attr, 0) + 1
        if sig.get("lens"):
            lenses[sig["lens"]] = lenses.get(sig["lens"], 0) + 1
        if len(recent) < 20:
            recent.append({k: sig.get(k) for k in
                           ("signal_type", "post_id", "region_id", "label", "lens",
                            "choice", "created_at")})

    return {
        "subject": subject,
        "totals": {"signals": total, "images": len(posts),
                   "taste_vectors": len(embedding_ids)},
        # `leans` are what the person is told about themselves — thresholded.
        "leans": {
            "parts": _rank(parts, LEAN_MIN_COUNT),
            "categories": _rank(categories, LEAN_MIN_COUNT),
            "attributes": _rank(attributes, LEAN_MIN_COUNT),
            "lenses": _rank(lenses, LEAN_MIN_COUNT),
        },
        # everything they've generated, so "see and delete your own signals" is honest
        "recent": recent,
    }


async def delete_subject(subject: str, *, drop_consent: bool = True) -> dict:
    """"Clear my taste" — a real delete, not a flag. The store is keyed by subject
    precisely so this can be honest."""
    if not is_opaque_subject(subject):
        raise ValueError("subject must be an opaque session/account id")
    res = await taste_signals_collection.delete_many({"subject": subject})
    consent_removed = 0
    if drop_consent:
        c = await taste_consent_collection.delete_many({"subject": subject})
        consent_removed = c.deleted_count
    return {"deleted_signals": res.deleted_count, "consent_removed": consent_removed}


# ---------------------------------------------------------------------------
# Brand read — anonymized aggregates + contractable creators only (F6)
# ---------------------------------------------------------------------------
_FORBIDDEN_BRAND_KEYS = {"subject", "subjects", "subject_id", "session", "user",
                         "user_id", "email"}


def _assert_no_subject_leak(payload, known_subjects: Optional[set] = None) -> None:
    """The brand boundary, enforced rather than promised.

    Walks a brand payload and raises if it carries a consumer identifier — by key, or
    by value against the exact subject ids that fed this very aggregate (the callers
    hold those sets already, so the check is precise rather than a pattern guess; a
    pattern would flag `creator_handle`, which is public and contractable and belongs
    here).

    This runs on every brand response, so a future edit that starts projecting
    `subject` fails loudly instead of quietly shipping.
    """
    subjects = known_subjects or set()

    def walk(node, path="$"):
        if isinstance(node, dict):
            for k, v in node.items():
                if k.lower() in _FORBIDDEN_BRAND_KEYS:
                    raise AssertionError(f"brand payload leaks consumer identity at {path}.{k}")
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str) and node in subjects:
            raise AssertionError(f"brand payload leaks a consumer subject id at {path}")

    walk(payload)


async def _distinct_subject_buckets(group_key: str, match: dict) -> Dict[str, set]:
    """Bucket → the set of distinct subjects behind it. The sets are used only to size
    the bucket and to apply k-anonymity; they are never returned."""
    buckets: Dict[str, set] = {}
    async for sig in taste_signals_collection.find(match, {"_id": 0}):
        if group_key == "attributes":
            keys = sig.get("attributes") or []
        else:
            value = sig.get(group_key)
            keys = [value] if value else []
        for key in keys:
            buckets.setdefault(key, set()).add(sig["subject"])
    return buckets


async def brand_trends(min_subjects: int = BRAND_MIN_SUBJECTS) -> dict:
    """
    Anonymized aggregate taste trends: which parts, categories, attributes and lenses
    are rising, and *how many distinct people* stand behind each — never who.

    A bucket backed by fewer than `min_subjects` people is dropped entirely rather than
    returned with a small count, because a count of one is a person.
    """
    out = {}
    all_subjects: set = set()
    for key in ("label", "category", "attributes", "lens"):
        buckets = await _distinct_subject_buckets(key, {})
        for subs in buckets.values():
            all_subjects |= subs
        rows = [{"value": name, "distinct_subjects": len(subs)}
                for name, subs in buckets.items() if len(subs) >= min_subjects]
        rows.sort(key=lambda r: (-r["distinct_subjects"], r["value"]))
        out["parts" if key == "label" else key] = rows

    suppressed = {
        "min_distinct_subjects": min_subjects,
        "note": "buckets below the threshold are withheld, not shown with small counts",
    }
    payload = {"trends": out, "k_anonymity": suppressed}
    _assert_no_subject_leak(payload, all_subjects)
    return payload


async def brand_creator_matches(
    parts: Optional[List[str]] = None, limit: int = 10,
    min_subjects: int = BRAND_MIN_SUBJECTS,
) -> dict:
    """
    Match a campaign's aesthetic to **contractable creators** — the only people a brand
    is ever shown. Scored by how much audience taste has accrued on the parts of images
    that creator authored.

    `parts` optionally narrows to a campaign's aesthetic (e.g. ["drape", "hem"]); absent,
    the strongest overall taste concentration wins. Creators below the k-anonymity
    threshold are withheld: a creator whose match is driven by one person's taps is not
    a match, and surfacing them would also be a way to fingerprint that one person.
    """
    wanted = {p.lower() for p in (parts or [])}

    # signal → the post it lands on → that post's creator handle.
    handle_cache: Dict[str, Optional[str]] = {}
    scores: Dict[str, Dict[str, object]] = {}

    async for sig in taste_signals_collection.find({}, {"_id": 0}):
        label = (sig.get("label") or "").lower()
        if wanted and label not in wanted:
            continue
        pid = sig["post_id"]
        if pid not in handle_cache:
            obj_id = _to_object_id(pid)
            doc = await post_collection.find_one({"_id": obj_id}, {"instagram_handle": 1}) if obj_id else None
            handle_cache[pid] = (doc or {}).get("instagram_handle")
        handle = handle_cache[pid]
        if not handle:
            continue
        entry = scores.setdefault(handle, {"signals": 0, "_subjects": set(), "_parts": {}})
        entry["signals"] += 1
        entry["_subjects"].add(sig["subject"])
        if sig.get("label"):
            entry["_parts"][sig["label"]] = entry["_parts"].get(sig["label"], 0) + 1

    matches = []
    all_subjects: set = set()
    for handle, entry in scores.items():
        all_subjects |= entry["_subjects"]
        distinct = len(entry["_subjects"])
        if distinct < min_subjects:
            continue                      # withheld, per the boundary
        matches.append({
            # A creator handle is contractable and public. This is the only identity
            # a brand payload ever carries.
            "creator_handle": handle,
            "signal_count": entry["signals"],
            "distinct_audience": distinct,   # a COUNT, never the people
            "top_parts": _rank(entry["_parts"])[:5],
        })
    matches.sort(key=lambda m: (-m["distinct_audience"], -m["signal_count"]))

    payload = {
        "matches": matches[:limit],
        "campaign_parts": sorted(wanted) or None,
        "k_anonymity": {"min_distinct_subjects": min_subjects},
        "boundary": "anonymized aggregates + contractable creators only; "
                    "no identified consumer profiles are ever returned",
    }
    _assert_no_subject_leak(payload, all_subjects)
    return payload
