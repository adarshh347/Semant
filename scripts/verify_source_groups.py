"""
Verification — Source Groups Phase 1, backend half (end-to-end over the live HTTP API).

Simulates what the extension sends: several reel frames uploaded through
`POST /posts/upload-from-url`, each carrying a `source_group` with a shared group_id, an
incrementing sequence_index, and a monotonic t_ms — then reads them back through
`GET /posts/{id}/siblings` and asserts:

  * every frame persisted the SAME group_id and group_type='reel'
  * siblings come back ordered by sequence_index (and t_ms as the finer axis)
  * t_ms is monotonic along that order
  * a single save (group_type='single', no group_id) persists no group and is its own
    sibling group of one — the graceful no-group path
  * an intentionally shuffled upload order still returns ordered (ordering is the
    endpoint's job, not the insertion order's)

Uploads are tiny data-URL images tagged with a marker; every post created is deleted
again at the end (which also destroys its Cloudinary asset), even on failure.

    python scripts/verify_source_groups.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000/api/v1/posts"
# a real 1x1 png as a data URL — Cloudinary accepts data URIs directly, no fetch
PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0"
       "lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
MARKER = "verify-source-groups"

ok = 0
fail = 0
created_ids = []


def check(label, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {label}")
    else:
        fail += 1
        print(f"  FAIL  {label}" + (f"\n          {detail}" if detail else ""))


async def upload(client, source_group):
    body = {
        "image_url": PNG,
        "source_url": f"https://example.invalid/{MARKER}",
        "general_tags": [MARKER],
    }
    if source_group is not None:
        body["source_group"] = source_group
    r = await client.post(f"{BASE}/upload-from-url", json=body)
    r.raise_for_status()
    post = r.json()
    created_ids.append(post["id"])
    return post


async def main():
    global fail
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # --- a reel of 5 frames, uploaded OUT OF ORDER on purpose ----------------
            gid = f"grp_{uuid.uuid4()}"
            # (sequence_index, t_ms) — a 5-frame reel; t_ms strictly increasing with index
            frames = [
                {"group_id": gid, "group_type": "reel", "sequence_index": 0, "sequence_total": 5, "t_ms": 100},
                {"group_id": gid, "group_type": "reel", "sequence_index": 1, "sequence_total": 5, "t_ms": 300},
                {"group_id": gid, "group_type": "reel", "sequence_index": 2, "sequence_total": 5, "t_ms": 550},
                {"group_id": gid, "group_type": "reel", "sequence_index": 3, "sequence_total": 5, "t_ms": 780},
                {"group_id": gid, "group_type": "reel", "sequence_index": 4, "sequence_total": 5, "t_ms": 990},
            ]
            upload_order = [2, 0, 4, 1, 3]  # deliberately scrambled
            posts = {}
            for i in upload_order:
                p = await upload(client, frames[i])
                posts[i] = p

            print("[1] every frame persisted the group")
            persisted = [p.get("source_group") for p in posts.values()]
            check("all frames carry a source_group", all(persisted), str(persisted))
            check("all share ONE group_id",
                  len({sg["group_id"] for sg in persisted}) == 1, str({sg["group_id"] for sg in persisted}))
            check("all are group_type='reel'",
                  all(sg["group_type"] == "reel" for sg in persisted))
            check("sequence_total persisted",
                  all(sg.get("sequence_total") == 5 for sg in persisted))

            print("\n[2] the siblings endpoint returns the group ordered")
            any_id = posts[3]["id"]  # ask from a frame in the MIDDLE, not the first uploaded
            r = await client.get(f"{BASE}/{any_id}/siblings")
            r.raise_for_status()
            data = r.json()
            sibs = data["siblings"]
            check("group_id echoed", data.get("group_id") == gid, str(data.get("group_id")))
            check("count is the whole reel", data.get("count") == 5, str(data.get("count")))
            idxs = [s["source_group"]["sequence_index"] for s in sibs]
            tms = [s["source_group"]["t_ms"] for s in sibs]
            check("returned in sequence_index order (despite scrambled upload)",
                  idxs == [0, 1, 2, 3, 4], str(idxs))
            check("t_ms is monotonic along that order",
                  all(tms[i] < tms[i + 1] for i in range(len(tms) - 1)), str(tms))

            print("\n[3] a single save is the graceful no-group path")
            single = await upload(client, {"group_type": "single"})
            check("a single save persists NO group",
                  single.get("source_group") is None, str(single.get("source_group")))
            r = await client.get(f"{BASE}/{single['id']}/siblings")
            r.raise_for_status()
            sd = r.json()
            check("siblings of a single: group_id is null", sd.get("group_id") is None, str(sd.get("group_id")))
            check("siblings of a single: it is its own group of one",
                  sd.get("count") == 1 and sd["siblings"][0]["id"] == single["id"], str(sd.get("count")))

            print("\n[4] a legacy post (no source_group field at all) still answers")
            legacy = await upload(client, None)
            check("an upload with no source_group persists none",
                  legacy.get("source_group") is None)
            r = await client.get(f"{BASE}/{legacy['id']}/siblings")
            r.raise_for_status()
            ld = r.json()
            check("legacy post is gracefully its own group",
                  ld.get("group_id") is None and ld.get("count") == 1)

            print("\n[5] two different reels do not bleed into each other")
            gid2 = f"grp_{uuid.uuid4()}"
            other = await upload(client, {"group_id": gid2, "group_type": "reel",
                                          "sequence_index": 0, "sequence_total": 1, "t_ms": 0})
            r = await client.get(f"{BASE}/{posts[0]['id']}/siblings")
            r.raise_for_status()
            check("reel A's siblings exclude reel B",
                  other["id"] not in [s["id"] for s in r.json()["siblings"]])

        finally:
            print("\n[cleanup] deleting fixtures")
            async with httpx.AsyncClient(timeout=60.0) as c2:
                for pid in created_ids:
                    try:
                        await c2.delete(f"{BASE}/{pid}")
                    except Exception as e:
                        print(f"  (could not delete {pid}: {e})")
            # prove nothing survived
            async with httpx.AsyncClient(timeout=60.0) as c3:
                leftover = 0
                for pid in created_ids:
                    rr = await c3.get(f"{BASE}/{pid}")
                    if rr.status_code == 200:
                        leftover += 1
                check("all fixtures removed", leftover == 0, f"{leftover} still present")

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
