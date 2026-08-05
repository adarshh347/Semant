"""
SF-001B — shape census of `post.percepts` and `post.grounds`. STRICTLY READ-ONLY.

Answers the load-bearing question SF-001A §1/C-2 opened: `post.percepts` is minted client-side by
`makeExpressionPercept` (frontend/src/state/perceptMentions.js:61-84) as an EXPRESSION percept
(`pctx_…`, kind='expression'), while the director's `percept_draft` (real_actuators.py:780-795 and
the comparative one at :534-554) becomes a MARK. Two objects, one name, no declared relation.

If ANY persisted percept row carries percept_draft-shaped keys (`type='percept_draft'`,
`draft_text`, `function`), then some accept path has written a PROPOSAL into the DURABLE field and
SF-002 must separate two objects before it types one. If none do, the two lineages are clean and
SF-002 types a single object (the expression percept).

Also censuses `post.grounds` by `ground_type` against the seven declared in
frontend/src/differential/grounds.js:22-24 — SF-001A §2 argues Ground is a discriminated union,
and this measures how many of the seven actually occur.

This script performs NO writes: it opens no update/insert/delete call, and uses a read-only
projection. It prints ABSOLUTE COUNTS ONLY (house rule K-9: no rates, no unmeasured figures).

Run: PYTHONPATH=. venv/bin/python scripts/sf001b_percept_ground_census.py
"""
import json
import os
import sys
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient

# SF-002 Part 0 — the classifier this census defined now lives in `backend.services
# .percept_lineage`, so the census, SF-002's guard test and its validation replay share ONE
# definition of "which percept is this?" instead of three copies that can drift apart. The
# behaviour is unchanged; this file simply stopped being its only home.
from backend.services.percept_lineage import classify_percept_row as classify_percept  # noqa: E402

# The seven declared ground types — grounds.js:22-24. Anything outside this set is reported
# separately rather than silently bucketed, because an undeclared type is itself a finding.
DECLARED_GROUND_TYPES = [
    "region", "field", "path", "boundary", "constellation", "relation", "frame",
]


def main():
    load_dotenv(".env")
    uri = os.getenv("MONGO_DETAILS")
    if not uri:
        print("BLOCKED: MONGO_DETAILS not set in .env", file=sys.stderr)
        return 2

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001 — the failure mode IS the finding when auth is down
        print(f"BLOCKED: cannot reach Mongo — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    # The app hardcodes the database (backend/database.py:49 `client.visualDictionaryDB`);
    # the connection string carries no default, so name it explicitly rather than guess.
    posts = client["visualDictionaryDB"].get_collection("posts")

    # `$nin: [[], None]` not `$ne` twice — a dict literal with two `$ne` keys silently keeps
    # only the last, which would have counted empty arrays as non-empty.
    nonempty = lambda f: {f: {"$exists": True, "$nin": [[], None]}}  # noqa: E731
    total_posts = posts.count_documents({})
    posts_with_percepts = posts.count_documents(nonempty("percepts"))
    posts_with_grounds = posts.count_documents(nonempty("grounds"))

    percept_kinds = Counter()
    ground_types = Counter()
    undeclared_ground_types = Counter()
    percept_rows = 0
    ground_rows = 0
    draft_examples = []          # the rows that would falsify the "two clean lineages" reading
    percept_key_union = Counter()
    ground_roles_rows = 0

    cursor = posts.find({}, {"_id": 1, "percepts": 1, "grounds": 1})
    for doc in cursor:
        for p in (doc.get("percepts") or []):
            percept_rows += 1
            kind = classify_percept(p)
            percept_kinds[kind] += 1
            if isinstance(p, dict):
                for k in p:
                    percept_key_union[k] += 1
                if "ground_roles" in p:
                    ground_roles_rows += 1
            if kind == "draft" and len(draft_examples) < 5:
                draft_examples.append({"post_id": str(doc["_id"]),
                                       "keys": sorted(p.keys()) if isinstance(p, dict) else None})
        for g in (doc.get("grounds") or []):
            ground_rows += 1
            gt = g.get("ground_type") if isinstance(g, dict) else None
            ground_types[gt] += 1
            if gt not in DECLARED_GROUND_TYPES:
                undeclared_ground_types[gt] += 1

    out = {
        "measured_at_collection": "posts",
        "total_posts": total_posts,
        "posts_with_nonempty_percepts": posts_with_percepts,
        "posts_with_nonempty_grounds": posts_with_grounds,
        "percept_rows_total": percept_rows,
        "percept_rows_by_shape": dict(percept_kinds),
        "percept_rows_carrying_ground_roles": ground_roles_rows,
        "percept_key_frequency": dict(percept_key_union.most_common()),
        "draft_shaped_examples": draft_examples,
        "ground_rows_total": ground_rows,
        "ground_rows_by_type": {t: ground_types.get(t, 0) for t in DECLARED_GROUND_TYPES},
        "ground_rows_undeclared_type": dict(undeclared_ground_types),
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
