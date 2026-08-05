"""
SF-002 Part 3 — validation replay of the typed soft-field models over the LIVE corpus.
STRICTLY READ-ONLY.

Fixtures prove the models handle the shapes we *believe* exist. This proves they handle the shapes
that *do*. Every percept row and every ground row in `visualDictionaryDB.posts` is validated
through `backend.schemas.soft_fields` and serialized back, and the result is compared to the
original key for key. The claim under test is the one the whole lane rests on:

    a round-trip drops nothing — and invents nothing.

Both halves matter. A dropped key is the `TextBlock.origin` failure: silent data loss on the next
wholesale PATCH. An INVENTED key (a declared-but-absent Optional emitted as `null`) is the quieter
twin: nothing is lost, but the client hydrates the null and the next autosave makes it durable on
every row, so the schema rewrites the corpus merely by being read. This script reports both, plus
any row that fails validation outright — which, on a read path served by `response_model=Post`,
would be a 500 on the whole post rather than a bad field.

This script performs NO writes. It opens no insert/update/delete call and reads through a
projection, per the discipline of the SF-001B census it follows. It prints ABSOLUTE COUNTS ONLY
(house rule K-9: a figure is measured or it is absent). Counts are whatever the corpus holds THIS
session — SF-001B's numbers (12 percepts, 43 grounds, 451 posts, measured 2026-08-01) are printed
alongside for comparison, never substituted for a live reading.

Exit codes: 0 clean · 1 a discrepancy was measured · 2 blocked (could not read).

Run: PYTHONPATH=. venv/bin/python scripts/sf002_softfield_replay.py
"""
import json
import os
import sys
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient

from backend.schemas.soft_fields import GROUND_TYPES, Ground, Percept
from backend.services.percept_lineage import classify_percept_row

from pydantic import TypeAdapter, ValidationError

# SF-001B, measured 2026-08-01. Printed for comparison ONLY. If the live counts differ, the live
# ones are the finding and these are history — never the other way round.
SF001B = {"total_posts": 451, "percept_rows": 12, "ground_rows": 43,
          "ground_rows_by_type": {"region": 22, "frame": 17, "field": 2, "path": 2,
                                  "boundary": 0, "constellation": 0, "relation": 0}}

_GROUND = TypeAdapter(Ground)


def replay(row, adapter_or_model):
    """Validate one row and serialize it back. Returns (verdict, detail).

    `mode="json"` because that is what `response_model=Post` does on the way to the client, and
    the client's next autosave is what makes any difference durable.
    """
    try:
        if isinstance(adapter_or_model, TypeAdapter):
            obj = adapter_or_model.validate_python(row)
            out = adapter_or_model.dump_python(obj, mode="json")
        else:
            obj = adapter_or_model.model_validate(row)
            out = obj.model_dump(mode="json")
    except ValidationError as exc:
        return "invalid", {"errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]}

    dropped = sorted(set(row) - set(out))
    invented = sorted(set(out) - set(row))
    changed = sorted(k for k in set(row) & set(out) if row[k] != out[k])
    if dropped or invented or changed:
        return "differs", {"dropped": dropped, "invented": invented, "changed": changed}
    return "identical", None


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

    # The app hardcodes the database (backend/database.py `client.visualDictionaryDB`); the
    # connection string carries no default, so name it explicitly rather than guess.
    posts = client["visualDictionaryDB"].get_collection("posts")

    percept_verdicts, ground_verdicts = Counter(), Counter()
    percept_shapes, ground_type_counts = Counter(), Counter()
    percept_rows = ground_rows = 0
    posts_with_percepts = posts_with_grounds = 0
    undeclared_types = Counter()
    findings = []                 # every row that was not byte-identical, with WHY

    total_posts = posts.count_documents({})
    for doc in posts.find({}, {"_id": 1, "percepts": 1, "grounds": 1}):
        pid = str(doc["_id"])

        rows = doc.get("percepts") or []
        if rows:
            posts_with_percepts += 1
        for row in rows:
            percept_rows += 1
            percept_shapes[classify_percept_row(row)] += 1
            verdict, detail = replay(row, Percept)
            percept_verdicts[verdict] += 1
            if verdict != "identical":
                findings.append({"field": "percepts", "post_id": pid,
                                 "row_id": (row or {}).get("id"), "verdict": verdict, **detail})

        rows = doc.get("grounds") or []
        if rows:
            posts_with_grounds += 1
        for row in rows:
            ground_rows += 1
            gtype = row.get("ground_type") if isinstance(row, dict) else None
            ground_type_counts[gtype] += 1
            if gtype not in GROUND_TYPES:
                undeclared_types[gtype] += 1
            verdict, detail = replay(row, _GROUND)
            ground_verdicts[verdict] += 1
            if verdict != "identical":
                findings.append({"field": "grounds", "post_id": pid,
                                 "row_id": (row or {}).get("id"), "verdict": verdict, **detail})

    clean = (not findings
             and percept_verdicts["invalid"] == 0 and ground_verdicts["invalid"] == 0)

    out = {
        "mode": "READ-ONLY validation replay (projection read; no insert/update/delete)",
        "measured": {
            "total_posts": total_posts,
            "posts_with_nonempty_percepts": posts_with_percepts,
            "posts_with_nonempty_grounds": posts_with_grounds,
            "percept_rows_total": percept_rows,
            "percept_rows_by_shape": dict(percept_shapes),
            "percept_replay": dict(percept_verdicts),
            "ground_rows_total": ground_rows,
            "ground_rows_by_type": {t: ground_type_counts.get(t, 0) for t in GROUND_TYPES},
            "ground_rows_undeclared_type": dict(undeclared_types),
            "ground_replay": dict(ground_verdicts),
        },
        "sf001b_measured_2026_08_01": SF001B,
        "dropped_keys": sum(len(f.get("dropped", [])) for f in findings),
        "invented_keys": sum(len(f.get("invented", [])) for f in findings),
        "changed_values": sum(len(f.get("changed", [])) for f in findings),
        "validation_failures": percept_verdicts["invalid"] + ground_verdicts["invalid"],
        "findings": findings,
        "verdict": "CLEAN — a round-trip drops nothing and invents nothing" if clean
                   else "DISCREPANCY — see findings",
    }
    print(json.dumps(out, indent=2, default=str))
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
