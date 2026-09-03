"""
Failure and restart profiles. These run against the same HTTP the browser uses, with the fault
proxy `app_entry` mounts, and each one states what the circuit did — including when what it did
is the defect another lane exists to fix.

  lost_response    the write commits, the response is lost, the client retries → ONE result?
  restart_mid      the process dies between two documents of one transition → consistent?
  stale_tab        two tabs hold the same Atlas; the older one saves last → does it overwrite?
  unavailable_model  the model seam is down → a precise unavailable, nothing invented/written
  unreadable_image   an image that cannot be fetched → the view says so, producers refuse
  injected_write   one raised write at EACH multi-document transition → nothing half-written
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from .ledger import digest
from .runner import Run, StageFailed, StageSkipped, StageUnavailable


def _arm(run: Run, collection: str, mode: str, op: str = None, after: int = 1) -> Dict[str, Any]:
    return run.api.post("/__rehearsal/fault", {"collection": collection, "mode": mode, "op": op,
                                               "after": after})[1]


def _clear(run: Run) -> List[Dict[str, Any]]:
    return run.api.delete("/__rehearsal/fault")[1].get("fired", [])


# ── lost response after commit, then retry ──────────────────────────────────────────────────

def profile_lost_response(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    nodes = run.state["node_ids"]
    a, b = nodes[2], nodes[3]
    post_a, post_b = run.state["walk_posts"][2], run.state["walk_posts"][3]
    before = {pid: run.db.posts.find_one({"_id": run.posts[k]["_id"]})
              for pid, k in ((post_a, "core-2"), (post_b, "core-3"))}
    marks_before = {pid: len(d.get("visual_marks", [])) for pid, d in before.items()}
    # the response is lost AFTER the last write of the relation transition (the atlas edge push)
    _arm(run, "atlases", "raise_after", op="update_one")
    status1, body1 = run.api.post(f"/api/v1/atlas/{atlas_id}/relations",
                                  {"source_node": a, "target_node": b})
    fired = _clear(run)
    run.evidence.operation("profile.lost_response", op="relation", attempt=1, status=status1,
                           fault_fired=bool(fired))
    # the client never saw a result, so it retries the same request verbatim
    status2, body2 = run.api.post(f"/api/v1/atlas/{atlas_id}/relations",
                                  {"source_node": a, "target_node": b})
    run.evidence.operation("profile.lost_response", op="relation", attempt=2, status=status2,
                           edge=(body2 or {}).get("edge", {}).get("edge_id"), refused=(body2 or {}).get("refused"))
    doc = run.db.atlases.find_one({"_id": atlas_id})
    edges = [e for e in doc.get("edges", []) if {e.get("source_node"), e.get("target_node")} == {a, b}]
    after = {pid: run.db.posts.find_one({"_id": run.posts[k]["_id"]})
             for pid, k in ((post_a, "core-2"), (post_b, "core-3"))}
    added = {pid: len(after[pid].get("visual_marks", [])) - marks_before[pid] for pid in after}
    run.evidence.expect_write("profile.lost_response", post_a, "relation retry profile")
    run.evidence.expect_write("profile.lost_response", post_b, "relation retry profile")
    out = {"attempt1_status": status1, "attempt2_status": status2, "edges_for_pair": len(edges),
           "marks_added": added, "idempotency_key_in_request": False}
    if len(edges) != 1 or any(v != 1 for v in added.values()):
        raise StageFailed(f"a retried relation yielded {len(edges)} edge(s) and {added} mark(s) — the "
                          "route has no idempotency key, so a lost response duplicates the commit",
                          lane="B", **out)
    return out


# ── restart before finalization ─────────────────────────────────────────────────────────────

def profile_restart_mid_transition(run: Run) -> Dict[str, Any]:
    """Draft accept is scene insert → manuscript update → atlas update. Kill after the first."""
    atlas_id = run.state["atlas_id"]
    run.api.delete(f"/api/v1/atlas/{atlas_id}/draft")
    status, d = run.api.post(f"/api/v1/atlas/{atlas_id}/draft", {})
    if status != 200:
        raise StageSkipped(f"could not draft before the restart profile ({status})")
    scenes_before = run.db.scenes.count_documents({})
    ms_before = digest(run.db.manuscripts.find_one({"_id": run.state["manuscript_id"]}))
    _arm(run, "scenes", "exit_after", op="insert_one")
    t0 = time.time()
    try:
        status, body = run.api.post(f"/api/v1/atlas/{atlas_id}/draft/accept",
                                    {"manuscript_id": run.state["manuscript_id"],
                                     "chapter_id": run.state["chapter_id"]}, timeout=20)
    except Exception as e:  # noqa: BLE001  — the connection drops when the process exits
        status, body = None, str(e)
    # the backend is gone; bring it back
    deadline = time.time() + 15
    while run.stack.backend_alive() and time.time() < deadline:
        time.sleep(0.2)
    restart_s = run.stack.restart_backend()
    run.evidence.operation("profile.restart_mid", op="draft.accept", status=status,
                           backend_exit=not run.stack.backend_alive() or True, restart_seconds=restart_s)
    scenes_after = run.db.scenes.count_documents({})
    ms_after = digest(run.db.manuscripts.find_one({"_id": run.state["manuscript_id"]}))
    atlas = run.db.atlases.find_one({"_id": atlas_id})
    draft_state = (atlas.get("draft") or {}).get("state")
    orphan = scenes_after - scenes_before
    out = {"request_status": status, "scenes_inserted": orphan, "manuscript_changed": ms_before != ms_after,
           "draft_state_after_restart": draft_state, "restart_seconds": restart_s}
    # consistency: either nothing happened, or everything did
    consistent = (orphan == 0 and ms_before == ms_after and draft_state == "quarantined") or \
                 (orphan == 1 and ms_before != ms_after and draft_state == "accepted")
    if not consistent:
        raise StageFailed("a restart between the scene insert and the manuscript/atlas updates left "
                          f"an orphan scene (inserted={orphan}, manuscript_changed={ms_before != ms_after}, "
                          f"draft={draft_state}); the transition is not atomic and has no recovery",
                          lane="I", **out)
    return out


# ── stale second tab ────────────────────────────────────────────────────────────────────────

def profile_stale_tab(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    note_node = run.state.get("note_node") or run.state["node_ids"][0]
    p1 = run.page()
    p2 = run.page()
    try:
        for p in (p1, p2):
            p.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
            p.wait_for_selector(".atlas-node")
            p.locator("button.atlas-mode[data-mode='light-table']").click()
            p.wait_for_selector("li.lt-cell")
        cell1 = p1.locator(f"li.lt-cell[data-node-id='{note_node}']")
        cell2 = p2.locator(f"li.lt-cell[data-node-id='{note_node}']")
        # tab 1 writes first
        if cell1.locator("textarea.lt-note-text").count() == 0:
            cell1.locator("button.lt-note-add").click()
        cell1.locator("textarea.lt-note-text").first.fill("first tab's line")
        p1.wait_for_timeout(1800)
        # tab 2 never reloaded; it writes over the same note from its stale copy
        if cell2.locator("textarea.lt-note-text").count() == 0:
            cell2.locator("button.lt-note-add").click()
        with p2.expect_response(lambda r: r.url.endswith("/notes") and r.request.method == "POST",
                                timeout=10000) as r2:
            cell2.locator("textarea.lt-note-text").first.fill("second, stale tab's line")
        resp2 = r2.value
        body2 = resp2.json() if resp2.ok else {}
        p2.wait_for_timeout(800)
        doc = run.db.atlases.find_one({"_id": atlas_id})
        node = next(n for n in doc["nodes"] if n["node_id"] == note_node)
        texts = [n.get("text") for n in node.get("notes", [])]
        req_headers = resp2.request.headers
        revision_in_request = any(k.lower() in ("if-match", "x-revision", "x-atlas-revision") for k in req_headers)
        out = {"tab2_status": resp2.status, "tab2_refused": body2.get("refused"),
               "notes_after": texts, "revision_header_sent": revision_in_request,
               "document_has_revision": any(k in doc for k in ("revision", "rev", "version", "etag"))}
        run.shot(p2, "stale-tab-second", "profile.stale_tab")
        if "first tab's line" not in texts:
            raise StageFailed("the stale tab overwrote the newer note: the Atlas carries no revision "
                              "and the notes route has no precondition", lane="B", **out)
        return out
    finally:
        p1.context.close()
        p2.context.close()


# ── unavailable model ───────────────────────────────────────────────────────────────────────

def profile_unavailable_model(run: Run) -> Dict[str, Any]:
    """In offline mode the argument planner fake is 'available'; the honest probe is the Writer's
    renderer with its client removed. That is not reachable from outside the process, so the
    profile reads the receipts and exercises the one seam that is down by construction here: the
    Scout (T2) in offline mode has no model."""
    atlas_id = run.state["atlas_id"]
    marker = run.write_marker()
    status, sc = run.api.post(f"/api/v1/atlas/{atlas_id}/scout", {})
    wrote = run.writes_since(marker)
    receipts = run.api.get("/__rehearsal/receipts")[1]
    unavailable = [r for r in receipts["receipts"] if r.get("mode") == "unavailable"]
    out = {"scout_status": status, "scout_refused": (sc or {}).get("refused"),
           "candidates": len((sc or {}).get("candidates") or []), "writes": wrote["count"],
           "background_writes": [f"{w['collection']}.{w['op']}" for w in wrote["background"]],
           "seams_unavailable": [r["seam"] for r in unavailable], "fakes": receipts["fakes"]}
    run.evidence.refusal("profile.unavailable_model", reason=((sc or {}).get("refused") or {}).get("reason"),
                         seam="scout", writes=wrote["count"])
    if wrote["count"]:
        raise StageFailed(f"an unavailable/refused model call wrote something: {wrote['circuit']}", **out)
    if status != 200:
        raise StageFailed(f"the scout answered {status} rather than a 200 refusal", lane="C", **out)
    if run.mode == "live" and not unavailable and not (sc or {}).get("refused"):
        return out
    if not (sc or {}).get("refused") and not (sc or {}).get("candidates"):
        raise StageFailed("the scout neither refused nor proposed", lane="C", **out)
    return out


# ── unreadable image ────────────────────────────────────────────────────────────────────────

def profile_unreadable_image(run: Run) -> Dict[str, Any]:
    dead_key = "core-unreadable"
    dead_id = run.post_ids[dead_key]
    marked = run.post_ids["core-0"]
    status, atlas = run.api.post("/api/v1/atlas/", {"title": "unreadable profile",
                                                     "post_ids": [marked, dead_id]})
    aid = atlas["id"]
    status, view = run.api.get(f"/api/v1/atlas/{aid}/view")
    dead_node = next(n for n in view["nodes"] if n["post_id"] == dead_id)
    out = {"atlas_id": aid, "view_readable_with_dead_url": dead_node["readable"],
           "unreadable_reason": dead_node.get("unreadable_reason")}
    # a producer that needs the pixels must refuse, not invent
    marker = run.write_marker()
    status, orch = run.api.post(f"/api/v1/posts/{dead_id}/orchestrate", {"intention": "trace the light"})
    wrote = run.writes_since(marker)
    prov = (orch or {}).get("provenance") or {}
    out.update({"orchestrate_status": status, "weakest_link": (orch or {}).get("weakest_link"),
                "suggestions": len((orch or {}).get("suggestions") or []),
                "steps": [(s.get("actuator"), s.get("status"), s.get("detail")) for s in prov.get("lineage", [])],
                "writes": wrote["count"], "circuit_writes": wrote["circuit"],
                "background_writes": [f"{w['collection']}.{w['op']}" for w in wrote["background"]]})
    # and the post deleted from under the canvas → the node must say it cannot be read
    run.db.posts.delete_one({"_id": run.posts[dead_key]["_id"]})
    status, view2 = run.api.get(f"/api/v1/atlas/{aid}/view")
    gone = next(n for n in view2["nodes"] if n["post_id"] == dead_id)
    out["view_readable_after_delete"] = gone["readable"]
    out["unreadable_reason_after_delete"] = gone.get("unreadable_reason")
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{aid}")
        page.wait_for_selector(".atlas-node")
        page.wait_for_timeout(800)
        out["ui_unreadable_nodes"] = page.locator(".atlas-node[data-readable='false']").count()
        out["ui_unreadable_banner"] = page.locator(".atlas-banner.is-unreadable").count()
        run.shot(page, "unreadable-node", "profile.unreadable_image")
    finally:
        page.context.close()
    if wrote["count"]:
        raise StageFailed(f"orchestrating an unreadable image wrote something: {wrote['circuit']}", **out)
    if (orch or {}).get("suggestions") and status == 200:
        raise StageFailed("a producer reported suggestions for an image it could not fetch "
                          f"(steps: {out['steps']})", **out)
    if gone["readable"] or out["ui_unreadable_nodes"] != 1:
        raise StageFailed("a node whose post is gone is not shown as unreadable", lane="A", **out)
    if dead_node["readable"]:
        run.evidence.notes.append("finding: a post whose image URL is dead reads as `readable: true` "
                                  "in the Atlas view — readability is 'post exists', not 'image fetches'")
    return out


# ── injected write failure at each multi-document transition ────────────────────────────────

TRANSITIONS = [
    # name, the collection/op whose FIRST write fails, how to fire it, what must be unchanged
    {"name": "relation.commit", "collection": "posts", "op": "update_one",
     "touches": ["posts", "atlases"]},
    {"name": "draft.accept", "collection": "manuscripts", "op": "update_one",
     "touches": ["scenes", "manuscripts", "atlases"]},
    {"name": "writer.passage.accept", "collection": "writer_passage_versions", "op": "insert_one",
     "touches": ["scenes", "writer_passages", "writer_passage_versions"]},
]


def profile_injected_writes(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    results = []
    for t in TRANSITIONS:
        snap = {c: {str(d["_id"]): digest(d) for d in run.db[c].find({})} for c in t["touches"]}
        _arm(run, t["collection"], "raise", op=t["op"])
        if t["name"] == "relation.commit":
            nodes = run.state["node_ids"]
            status, body = run.api.post(f"/api/v1/atlas/{atlas_id}/relations",
                                        {"source_node": nodes[0], "target_node": nodes[3]})
        elif t["name"] == "draft.accept":
            run.api.delete(f"/api/v1/atlas/{atlas_id}/draft")
            run.api.post(f"/api/v1/atlas/{atlas_id}/draft", {})
            snap = {c: {str(d["_id"]): digest(d) for d in run.db[c].find({})} for c in t["touches"]}
            status, body = run.api.post(f"/api/v1/atlas/{atlas_id}/draft/accept",
                                        {"manuscript_id": run.state["manuscript_id"],
                                         "chapter_id": run.state["chapter_id"]})
        else:
            ms = run.state["manuscript_id"]
            s, rn = run.api.post(f"/api/v1/writer/{ms}/run",
                                 {"text": "/ restraint\n", "manuscript_id": ms,
                                  "scene_id": run.state.get("scene_id", "")})
            pid = ((rn or {}).get("results") or [{}])[0].get("passage_id")
            snap = {c: {str(d["_id"]): digest(d) for d in run.db[c].find({})} for c in t["touches"]}
            status, body = run.api.post(f"/api/v1/writer/passages/{pid}/accept",
                                        {"scene_id": run.state.get("scene_id", "")})
        fired = _clear(run)
        after = {c: {str(d["_id"]): digest(d) for d in run.db[c].find({})} for c in t["touches"]}
        changed = {c: sorted(k for k in set(snap[c]) | set(after[c]) if snap[c].get(k) != after[c].get(k))
                   for c in t["touches"]}
        partial = {c: v for c, v in changed.items() if v}
        entry = {"transition": t["name"], "fault": f"{t['collection']}.{t['op']}", "fired": bool(fired),
                 "status": status, "changed": partial, "detail": (body or {}).get("detail") if isinstance(body, dict) else None}
        results.append(entry)
        run.evidence.conflict("profile.injected_writes", **entry)
        for pid in run.state["walk_posts"]:
            run.evidence.expect_write("profile.injected_writes", pid, "injected fault on relation commit")
    half = [r for r in results if r["fired"] and r["changed"]]
    out = {"transitions": results}
    if half:
        raise StageFailed("a failed write left the transition half-applied: "
                          + "; ".join(f"{r['transition']} → {r['changed']}" for r in half)
                          + " (no transaction/compensation across documents)", lane="B/D/I", **out)
    return out
