"""
The circuit, driven through the actual UI. Each stage is a function of the `Run`; it returns the
evidence it captured, raises `StageFailed` for a domain defect (naming the owning lane) and
`StageUnavailable` when the seam it needs is not on this base yet (naming the lane that brings it).

Selectors are the ones the components render — `aria-label`s, `data-*` attributes and the Writer's
`data-testid`s — never layout classes, so a restyle does not fail the rehearsal and a renamed
control does.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List

from .ledger import digest
from .runner import Run, StageFailed, StageSkipped, StageUnavailable

LANE = {
    "A": "A · atlas lifecycle repair", "B": "B · atlas reliable writes",
    "C": "C · atlas relation workbench", "D": "D · writer ledger integrity",
    "E": "E · production writer shell", "F": "F · operator workbench",
    "G": "G · alignment/revision loop", "H": "H · honest hybrid recall",
    "I": "I · atlas↔writer circulation spine", "J": "J · movement acceptance bridge",
    "K": "K · movement/axis atlas mode",
}

CORE_WALK = ["core-0", "core-1", "core-2", "core-3"]


def _wait_idle(page, ms: int = 400) -> None:
    page.wait_for_timeout(ms)


# ── 1. curated walk: save, reload, open ───────────────────────────────────────────────────────

def stage_walk_save_open(run: Run) -> Dict[str, Any]:
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas")
        page.wait_for_selector("form[aria-label='Open a new Atlas']")
        if page.locator(".atlas-banner.is-error").count():
            raise StageFailed("the Atlas index refused the browser's API key: "
                              + page.locator(".atlas-banner.is-error").inner_text())
        page.wait_for_selector("button.atlas-pick")
        # Pick the walk IN ORDER by the image each button shows — the order is the walk.
        picked: List[str] = []
        for key in CORE_WALK:
            btn = page.locator(f"button.atlas-pick:has(img[src$='/{key}.png'])")
            if btn.count() == 0:
                raise StageFailed(f"fixture image {key} is not offered by the picker")
            btn.first.click()
            picked.append(run.post_ids[key])
        rows = page.locator("li.atlas-order-row")
        page.wait_for_function("n => document.querySelectorAll('li.atlas-order-row').length === n",
                               arg=len(CORE_WALK))
        order = [rows.nth(i).get_attribute("data-order-post") for i in range(rows.count())]
        if order != picked:
            raise StageFailed(f"the picker's order {order} is not the pick order {picked}")
        # Move image 2 earlier then later again: reorder through the controls, not the API.
        page.locator("button[aria-label='Move image 2 earlier']").click()
        page.locator("button[aria-label='Move image 1 later']").click()
        page.locator("input[aria-label='Why image 1 sits here']").fill("the approach")
        page.locator("input.atlas-input").first.fill("the rehearsal walk")
        page.locator("input[placeholder='the approach, in the order a visitor walks it']").fill(
            "the approach, in the order a visitor walks it")
        run.shot(page, "walk-picked", "walk.save_open")
        page.locator("button[data-save-corpus]").click()
        page.wait_for_selector("section[aria-label='Saved walks'] button.atlas-list-item[data-corpus]")
        corpus_id = page.locator("section[aria-label='Saved walks'] button.atlas-list-item[data-corpus]") \
            .first.get_attribute("data-corpus")
        stored = run.db.corpora.find_one({"_id": corpus_id}) or run.db.corpora.find_one({"id": corpus_id})
        if stored is None:
            # the id may be stored under a different key; find by title
            stored = run.db.corpora.find_one({"title": "the rehearsal walk"})
        if stored is None:
            raise StageFailed("the saved walk is not in the `corpora` collection")
        stored_ids = [str(i.get("post_id")) for i in stored.get("images", [])]
        if stored_ids != picked:
            raise StageFailed(f"stored walk order {stored_ids} != picked {picked}")
        if any(k in i for i in stored.get("images", []) for k in ("marks", "geometry", "percepts")):
            raise StageFailed("the stored walk carries percept data")
        # Reload, then open the walk — the object must survive the page.
        page.reload()
        page.wait_for_selector(f"button.atlas-list-item[data-corpus='{corpus_id}']")
        ui_open_error = None
        with page.expect_response(lambda r: r.url.rstrip("/").endswith("/api/v1/atlas") and
                                  r.request.method == "POST", timeout=15000) as created:
            page.locator(f"button.atlas-list-item[data-corpus='{corpus_id}']").click()
        if created.value.status >= 400:
            ui_open_error = {"status": created.value.status,
                             "request_body": created.value.request.post_data,
                             "detail": (created.value.json() or {}).get("detail"),
                             "banner": page.locator(".atlas-error").all_inner_texts()}
            # Open the SAME walk through the seam the UI should have used, so the rest of the
            # circuit can still be rehearsed over a curated Atlas; the defect is reported below.
            status, doc = run.api.post("/api/v1/atlas/", {"corpus_id": corpus_id})
            if status != 201:
                raise StageFailed(f"opening the walk failed in the UI ({ui_open_error}) and via the "
                                  f"API ({status}: {doc})", lane="A")
            page.goto(f"{run.stack.app_url}/atlas/{doc['id']}")
        else:
            page.wait_for_url(re.compile(r"/atlas/[^/]+$"))
        atlas_id = page.url.rstrip("/").rsplit("/", 1)[-1]
        page.wait_for_selector(".atlas-node")
        doc = run.db.atlases.find_one({"_id": atlas_id})
        if doc is None:
            raise StageFailed(f"no atlas document '{atlas_id}' after opening the walk")
        if (doc.get("corpus_ref") or {}).get("kind") != "curated" or \
                doc["corpus_ref"].get("corpus_id") != corpus_id:
            raise StageFailed(f"atlas corpus_ref does not point at the walk: {doc.get('corpus_ref')}")
        node_posts = [n["post_id"] for n in doc["nodes"]]
        if node_posts != picked:
            raise StageFailed(f"atlas nodes {node_posts} are not the walk's order {picked}")
        run.shot(page, "walk-opened", "walk.save_open")
        run.state.update({"corpus_id": corpus_id, "atlas_id": atlas_id,
                          "node_ids": [n["node_id"] for n in doc["nodes"]],
                          "walk_posts": picked})
        run.evidence.record_id("walk.save_open", corpus_id=corpus_id, atlas_id=atlas_id,
                               contract_version=doc.get("contract_version"))
        out = {"corpus_id": corpus_id, "atlas_id": atlas_id, "order": picked,
               "ui_open_error": ui_open_error, "console": page._vr_console[:20]}
        if ui_open_error:
            raise StageFailed("the saved walk cannot be opened from the index: the client's "
                              "`atlasService.create()` drops `corpus_id` and the route answers "
                              f"{ui_open_error['status']} ({ui_open_error['detail']}); the Atlas "
                              "was opened over the same walk through the API so the circuit could "
                              "continue", lane="A", **out)
        return out
    finally:
        page.context.close()


# ── 2. canvas: arrangement save, and the document holds no percept truth ─────────────────────

def stage_atlas_canvas(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    page = run.page()
    try:
        t0 = time.perf_counter()
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.wait_for_function("document.querySelectorAll('.atlas-node img').length > 0")
        hydrate_ms = (time.perf_counter() - t0) * 1000
        run.evidence.timing("atlas.canvas", "hydrate_4_nodes", hydrate_ms)
        # Real rendering: does the React Flow pane actually cover its nodes in Canvas mode?
        geom = canvas_geometry(page)
        run.shot(page, "canvas-mode", "atlas.canvas")
        canvas_mode_pane_ok = geom["pane_h"] > 100 and geom["hit"] != "atlas-shell"
        if not canvas_mode_pane_ok:
            run.evidence.notes.append(
                f"finding: in Canvas mode the React Flow pane is {geom['pane_w']}x{geom['pane_h']} "
                f"(the wrapper `<div className={{undefined}}>` around AtlasCanvas has no flex sizing), "
                f"so pointer input lands on `.{geom['hit']}`; gestures are rehearsed in Plan mode, "
                f"where `.atlas-with-plan` gives the same renderer a height")
            enter_sized_canvas(page)
        before = run.db.atlases.find_one({"_id": atlas_id})
        node = page.locator(".react-flow__node").first
        box = node.bounding_box()
        page.mouse.move(box["x"] + 20, box["y"] + 20)
        page.mouse.down()
        page.mouse.move(box["x"] + 30, box["y"] + 30, steps=3)
        for i in range(1, 10):
            page.mouse.move(box["x"] + 20 + 20 * i, box["y"] + 20 + 15 * i, steps=2)
        page.mouse.up()
        # the save is debounced; wait for the arrangement request to land
        page.wait_for_timeout(1500)
        page.wait_for_function("!document.querySelector('.atlas-status')?.textContent?.includes('saving')",
                               timeout=10000)
        after = run.db.atlases.find_one({"_id": atlas_id})
        moved = [(a["node_id"], a["x"], a["y"]) for a in after["nodes"]] != \
                [(b["node_id"], b["x"], b["y"]) for b in before["nodes"]]
        if not moved:
            raise StageFailed("dragging a node did not change the stored arrangement", lane="A")
        forbidden = {"geometry", "grounds", "marks", "regions", "percepts", "strokes", "mask",
                     "box", "photo_url", "image_url", "epistemic_status", "provenance"}
        leaked = [k for n in after["nodes"] for k in n if k in forbidden]
        if leaked:
            raise StageFailed(f"the Atlas document carries percept truth: {leaked}")
        run.shot(page, "canvas-after-drag", "atlas.canvas")
        run.evidence.record_id("atlas.canvas", atlas_updated_at=str(after.get("updated_at")))
        out = {"hydrate_ms": round(hydrate_ms, 1), "nodes": len(after["nodes"]),
               "arrangement_changed": True, "document_keys": sorted(after.keys()),
               "canvas_mode_geometry": geom, "gestures_rehearsed_in": "canvas" if canvas_mode_pane_ok else "plan"}
        if not canvas_mode_pane_ok:
            raise StageFailed(f"in Canvas mode the React Flow pane renders {geom['pane_w']}x{geom['pane_h']} "
                              f"and a click on a node reaches `.{geom['hit']}` — the canvas cannot be "
                              "panned, zoomed, dragged or connected in its own mode; the arrangement "
                              "save was proven in Plan mode instead", lane="A", **out)
        return out
    finally:
        page.context.close()


def canvas_geometry(page) -> Dict[str, Any]:
    """What the pane measures and what a pointer at the first node's centre would hit."""
    return page.evaluate("""() => {
        const pane = document.querySelector('.react-flow__pane');
        const node = document.querySelector('.react-flow__node');
        const r = pane ? pane.getBoundingClientRect() : {width: 0, height: 0};
        const n = node ? node.getBoundingClientRect() : null;
        const hit = n ? document.elementFromPoint(n.x + n.width / 2, n.y + n.height / 2) : null;
        return {pane_w: Math.round(r.width), pane_h: Math.round(r.height),
                node_w: n ? Math.round(n.width) : 0, node_h: n ? Math.round(n.height) : 0,
                hit: hit ? (hit.className.toString().split(' ')[0] || hit.tagName) : null};
    }""")


def enter_sized_canvas(page) -> None:
    """Plan mode: the same AtlasCanvas inside `.atlas-with-plan`, which has a height."""
    page.locator("button.atlas-mode[data-mode='plan']").click()
    page.wait_for_selector(".atlas-with-plan .react-flow__pane")
    page.wait_for_function("document.querySelector('.react-flow__pane').getBoundingClientRect().height > 100")
    page.wait_for_timeout(600)


# ── 3. light table: notes, and they are the author's words only ──────────────────────────────

def stage_light_table(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        t0 = time.perf_counter()
        page.locator("button.atlas-mode[data-mode='light-table']").click()
        page.wait_for_selector(".atlas-shell[data-mode='light-table'] li.lt-cell")
        run.evidence.timing("atlas.light_table", "mode_switch_to_light_table",
                            (time.perf_counter() - t0) * 1000)
        cells = page.locator("li.lt-cell")
        n = cells.count()
        if n != 4:
            raise StageFailed(f"light table shows {n} cells for a 4-image walk")
        drawn = [cells.nth(i).locator(".lt-cell-count").get_attribute("data-drawn") for i in range(n)]
        first = cells.first
        node_id = first.get_attribute("data-node-id")
        first.locator("button.lt-note-add").click()
        ta = first.locator("textarea.lt-note-text").first
        note_text = "the approach reads as a held breath"
        ta.fill(note_text)
        t1 = time.perf_counter()
        page.wait_for_timeout(1500)
        page.wait_for_function("!document.querySelector('.atlas-status')?.textContent?.includes('saving')",
                               timeout=10000)
        doc = run.db.atlases.find_one({"_id": atlas_id})
        node = next((x for x in doc["nodes"] if x["node_id"] == node_id), None)
        notes = (node or {}).get("notes") or []
        if not any(x.get("text") == note_text for x in notes):
            raise StageFailed("the author note did not reach the Atlas document", lane="A")
        run.evidence.timing("atlas.light_table", "notes_save_roundtrip", (time.perf_counter() - t1) * 1000)
        extra = [k for x in notes for k in x if k not in ("note_id", "text")]
        if extra:
            raise StageFailed(f"a note carries keys beyond note_id/text: {extra}")
        run.shot(page, "light-table-note", "atlas.light_table")
        run.state["note_node"] = node_id
        return {"cells": n, "drawn_counts": drawn, "note_id": notes[0].get("note_id"),
                "note_keys": sorted({k for x in notes for k in x})}
    finally:
        page.context.close()


# ── 4. differential: machine read → proposal → review → accept / return ──────────────────────

def stage_differential(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    key = CORE_WALK[0]
    post_id = run.post_ids[key]
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.locator("button.atlas-mode[data-mode='light-table']").click()
        page.wait_for_selector("li.lt-cell")
        read = page.locator(f"button.lt-read[data-read-post='{post_id}']")
        if read.count() == 0:
            raise StageUnavailable("the Light Table offers no machine read on this image")
        marker = run.write_marker()
        auto_ran = True
        try:
            with page.expect_response(lambda r: "/orchestrate" in r.url, timeout=12000) as resp_info:
                read.click()
            resp = resp_info.value
        except Exception:  # noqa: BLE001 — the one-click read did not reach the Director
            auto_ran = False
            page.wait_for_selector("div.atlas-focus[role='dialog'] .orch-bar")
            intention = page.locator("input.orch-input").input_value()
            run.evidence.notes.append(
                f"finding: the Light Table's one-click machine read put '{intention}' in the "
                "Orchestrate bar but no /orchestrate request completed (the auto-run fires once and "
                "its in-flight request is cancelled by the bar's unmount cleanup); it was run by "
                "pressing Run in the same bar")
            with page.expect_response(lambda r: "/orchestrate" in r.url, timeout=60000) as resp_info:
                page.locator("button.orch-run").click()
            resp = resp_info.value
        body = resp.json() if resp.ok else {"status": resp.status}
        run.evidence.receipt("differential", seam="orchestrate", status=resp.status, auto_ran=auto_ran,
                             planner=(body.get("plan") or {}).get("planner"),
                             weakest_link=body.get("weakest_link"),
                             suggestions=len(body.get("suggestions") or []),
                             steps=[s.get("actuator") for s in (body.get("plan") or {}).get("steps", [])])
        wrote = run.writes_since(marker)
        if wrote["count"]:
            raise StageFailed(f"the machine read wrote {wrote['count']} circuit document(s): "
                              f"{wrote['circuit']}; a proposal must write nothing")
        page.wait_for_selector("div.atlas-focus[role='dialog']")
        dlg = page.locator("div.atlas-focus[role='dialog']")
        if dlg.get_attribute("data-post-id") != post_id:
            raise StageFailed("the Differential opened on a different post than was read")
        page.wait_for_selector(".diff-root")
        _wait_idle(page, 1200)
        run.shot(page, "differential-proposal", "differential")
        suggestions = body.get("suggestions") or []
        if not suggestions:
            raise StageFailed("the Director produced no suggestion to review; nothing to accept. "
                              f"plan={body.get('plan')}")
        # Review → accept. The Differential's accept is a PATCH of the post (no accept route).
        if page.locator(".diff-review-start").count():
            page.locator(".diff-review-start").click()          # several suggestions: review them
            page.wait_for_selector(".diff-review-accept")
            run.shot(page, "differential-review", "differential")
        accept = page.locator(".diff-review-accept")
        if accept.count() == 0:
            accept = page.locator(".diff-primary").filter(has_text=re.compile(r"Accept|Keep"))
        if accept.count() == 0:
            raise StageUnavailable("no accept control is offered for the Director's proposal in "
                                   "the Differential; the proposal was reviewed but could not be "
                                   "accepted through the UI")
        before = run.db.posts.find_one({"_id": run.posts[key]["_id"]})
        with page.expect_response(lambda r: f"/posts/{post_id}" in r.url and
                                  r.request.method in ("PATCH", "POST")) as acc:
            accept.first.click()
        run.evidence.operation("differential", op="accept", method=acc.value.request.method,
                               url=acc.value.url, status=acc.value.status)
        _wait_idle(page, 600)
        after = run.db.posts.find_one({"_id": run.posts[key]["_id"]})
        changed = digest(before) != digest(after)
        if not changed:
            raise StageFailed("accepting the proposal did not write the post")
        run.evidence.expect_write("differential", post_id, "the author accepted a Director proposal")
        run.shot(page, "differential-accepted", "differential")
        # Accepting ADDS evidence. Every mark committed before the accept must still be there.
        before_marks = {m.get("id") for m in before.get("visual_marks") or []}
        after_marks = {m.get("id") for m in after.get("visual_marks") or []}
        lost = sorted(before_marks - after_marks)
        before_regions = {r.get("id") for r in before.get("region_annotations") or []}
        lost_regions = sorted(before_regions - {r.get("id") for r in after.get("region_annotations") or []})
        if lost or lost_regions:
            page.keyboard.press("Escape")
            raise StageFailed(f"accepting one proposal removed committed evidence from the post: "
                              f"marks {lost}, regions {lost_regions} — the Differential's accept is a "
                              "wholesale PATCH from the client's store, which did not carry the "
                              "ledger's committed marks", lane="B",
                              post_id=post_id, lost_marks=lost, lost_regions=lost_regions,
                              accepted_marks=sorted(after_marks - before_marks),
                              method=acc.value.request.method, url=acc.value.url)
        # Return: Escape closes the Differential and leaves the Atlas where it was.
        page.keyboard.press("Escape")
        page.wait_for_selector("div.atlas-focus[role='dialog']", state="detached")
        # Dismiss path: re-read and dismiss, must write nothing.
        marker = run.write_marker()
        read.click()
        page.wait_for_selector("div.atlas-focus[role='dialog'] .orch-bar")
        try:
            with page.expect_response(lambda r: "/orchestrate" in r.url, timeout=8000):
                pass
        except Exception:  # noqa: BLE001
            with page.expect_response(lambda r: "/orchestrate" in r.url, timeout=60000):
                page.locator("button.orch-run").click()
        _wait_idle(page, 800)
        quiet = page.locator(".diff-quiet").filter(has_text=re.compile(r"Dismiss|Cancel|Later|Clear"))
        if quiet.count():
            quiet.first.click()
        page.keyboard.press("Escape")
        _wait_idle(page, 500)
        dismissed = run.writes_since(marker)
        run.evidence.refusal("differential", reason="dismissed_by_author", writes=dismissed["count"])
        return {"post_id": post_id, "suggestions": len(suggestions), "accepted_write": changed,
                "auto_ran": auto_ran, "dismiss_writes": dismissed["count"],
                "added_marks": len(after.get("visual_marks") or []) - len(before.get("visual_marks") or []),
                "added_layers": len(after.get("visual_layers") or []) - len(before.get("visual_layers") or []),
                "console": page._vr_console[:20]}
    finally:
        page.context.close()


# ── 5. explicit relation, and a refusal that writes nothing ──────────────────────────────────

def _drag_handle(page, src_node: str, dst_node: str) -> None:
    src = page.locator(f".react-flow__node:has(.atlas-node[data-post-id='{src_node}'])")
    dst = page.locator(f".react-flow__node:has(.atlas-node[data-post-id='{dst_node}'])")
    handle = src.locator(".react-flow__handle.source").first
    target = dst.locator(".react-flow__handle.target").first
    hb = handle.bounding_box()
    tb = target.bounding_box() if target.count() else dst.bounding_box()
    page.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2)
    page.mouse.down()
    page.mouse.move(hb["x"] + 10, hb["y"] + 10, steps=3)
    page.mouse.move(tb["x"] + tb["width"] / 2, tb["y"] + tb["height"] / 2, steps=20)
    page.wait_for_timeout(200)
    page.mouse.up()


def stage_relation(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        _wait_idle(page, 800)
        if canvas_geometry(page)["pane_h"] <= 100:
            enter_sized_canvas(page)        # see stage_atlas_canvas: Canvas mode has no pane
        a, b = run.post_ids["core-1"], run.post_ids["core-2"]
        before_a = run.db.posts.find_one({"_id": run.posts["core-1"]["_id"]})
        before_b = run.db.posts.find_one({"_id": run.posts["core-2"]["_id"]})
        with page.expect_response(lambda r: r.url.endswith("/relations") and r.request.method == "POST",
                                  timeout=20000) as rel_info:
            _drag_handle(page, a, b)
        rel = rel_info.value.json()
        if rel.get("refused"):
            raise StageFailed(f"relating two marked images was refused: {rel['refused']}", lane="C")
        edge = rel.get("edge") or {}
        page.wait_for_selector(".react-flow__edge.atlas-relation")
        run.shot(page, "relation-drawn", "relation")
        doc = run.db.atlases.find_one({"_id": atlas_id})
        stored = next((e for e in doc.get("edges", []) if e.get("edge_id") == edge.get("edge_id")), None)
        if stored is None:
            raise StageFailed("the relation edge is not in the Atlas document", lane="C")
        forbidden = {"geometry", "label", "role", "epistemic_status", "provenance", "sources", "mask", "points"}
        if forbidden & set(stored):
            raise StageFailed(f"the stored edge carries percept truth: {sorted(forbidden & set(stored))}")
        after_a = run.db.posts.find_one({"_id": run.posts["core-1"]["_id"]})
        after_b = run.db.posts.find_one({"_id": run.posts["core-2"]["_id"]})
        mark_id = stored.get("mark_id")
        in_a = any(m.get("id") == mark_id for m in after_a.get("visual_marks", []))
        in_b = any(m.get("id") == mark_id for m in after_b.get("visual_marks", []))
        if not (in_a and in_b):
            raise StageFailed("the compare_views mark is not committed into both posts", lane="C")
        run.evidence.expect_write("relation", a, "the author drew a relation (compare_views mark)")
        run.evidence.expect_write("relation", b, "the author drew a relation (compare_views mark)")
        # The visible edge hydrates from the ledger: its label is the mark's, not the client's.
        view = run.api.get(f"/api/v1/atlas/{atlas_id}/view")[1]
        hyd = next((e for e in view["edges"] if e.get("edge_id") == edge.get("edge_id")), {})
        if not hyd.get("live") or not hyd.get("source_ref"):
            raise StageFailed(f"the hydrated edge is not live or has no source_ref: {hyd}", lane="C")
        dom_label = (page.locator(".react-flow__edge.atlas-relation").first.text_content() or "").strip()
        run.evidence.record_id("relation", edge_id=edge.get("edge_id"), mark_id=mark_id,
                               source_ref=hyd.get("source_ref"), epistemic=hyd.get("epistemic"))

        # Refusal: an unmarked image cannot be related, and nothing may be written.
        view_before = run.db.atlases.find_one({"_id": atlas_id})
        marker = run.write_marker()
        c = run.post_ids["core-3"]
        # core-3 has marks; use the API's own refusal on an unknown node? No — refuse on the
        # canvas: the same node to itself is refused locally, and an unmarked node by the gate.
        unmarked = run.state.get("unmarked_node_post")
        if unmarked:
            with page.expect_response(lambda r: r.url.endswith("/relations") and r.request.method == "POST",
                                      timeout=20000) as ref_info:
                _drag_handle(page, a, unmarked)
            ref = ref_info.value.json()
            refused = ref.get("refused")
        else:
            refused = None
        if not refused:
            # Fall back to the API for the refusal; the canvas has no unmarked node in this walk.
            status, ref = run.api.post(f"/api/v1/atlas/{atlas_id}/relations",
                                       {"source_node": run.state["node_ids"][0],
                                        "target_node": run.state["node_ids"][0]})
            refused = ref.get("refused")
            refusal_path = "api(same-node)"
        else:
            refusal_path = "ui(unmarked)"
        if not refused:
            raise StageFailed("no refusal could be produced", lane="C")
        page.wait_for_selector(".atlas-banner.is-refused, .react-flow__edge.is-refused", timeout=5000) \
            if refusal_path.startswith("ui") else None
        wrote = run.writes_since(marker)
        view_after = run.db.atlases.find_one({"_id": atlas_id})
        if digest(view_before) != digest(view_after) or wrote["count"]:
            raise StageFailed(f"a refused relation wrote something: {wrote['circuit']}", lane="C")
        run.evidence.refusal("relation", reason=refused.get("reason"), detail=refused.get("detail"),
                             path=refusal_path, writes=wrote["count"])
        run.shot(page, "relation-refused", "relation")
        run.state["edge_id"] = edge.get("edge_id")
        run.state["relation_mark_id"] = mark_id
        return {"edge_id": edge.get("edge_id"), "mark_id": mark_id, "dom_label": dom_label,
                "hydrated": {k: hyd.get(k) for k in ("live", "role", "label", "epistemic", "source_ref")},
                "refusal": refused, "refusal_path": refusal_path}
    finally:
        page.context.close()


# ── 6. plan: propose, edit, accept ───────────────────────────────────────────────────────────

def stage_plan(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.locator("button.atlas-mode[data-mode='plan']").click()
        page.wait_for_selector("aside[aria-label='Plan mode']")
        page.locator("#atlas-thesis").fill("the sequence disperses what the rotunda gathers")
        with page.expect_response(lambda r: r.url.endswith("/plan") and r.request.method == "POST") as p:
            page.locator("aside[aria-label='Plan mode'] button.atlas-go", has_text="Plan").click()
        body = p.value.json()
        if p.value.status != 200:
            raise StageFailed(f"planning answered {p.value.status}: {body}")
        run.evidence.receipt("plan", seam="argument_planner", planner=body.get("planner"),
                             planner_available=body.get("planner_available"),
                             claims=len(body.get("claims") or []), refusals=body.get("refusals"))
        if not body.get("planner_available"):
            raise StageUnavailable("the argument planner is unavailable (no model credential); "
                                   "no claims were proposed and none were invented")
        attempts = 1
        if not body.get("claims") and run.mode == "live":
            # A live model may decompose nothing on one call. Ask once more, through the same
            # button, and record both answers; a second empty answer is the finding.
            attempts = 2
            run.evidence.receipt("plan", seam="argument_planner", attempt=1, claims=0,
                                 notes=body.get("notes"))
            with page.expect_response(lambda r: r.url.endswith("/plan") and r.request.method == "POST") as p2:
                page.locator("aside[aria-label='Plan mode'] button.atlas-go", has_text="Plan").click()
            body = p2.value.json()
        if not body.get("claims"):
            # A live model may decompose nothing (or fail, and say so in its notes). That is an
            # honest empty plan, not a harness timeout — report it with the planner's own words.
            run.shot(page, "plan-empty", "plan")
            raise StageFailed("the planner proposed no claims for the thesis: "
                              f"{body.get('notes') or body.get('refusals') or body}",
                              lane=None, planner=body.get("planner"), notes=body.get("notes"),
                              refusals=body.get("refusals"))
        page.wait_for_selector("li.atlas-claim-row")
        rows = page.locator("li.atlas-claim-row")
        n0 = rows.count()
        proposed = [(rows.nth(i).get_attribute("data-claim-id"), rows.nth(i).get_attribute("data-status"))
                    for i in range(n0)]
        run.shot(page, "plan-proposed", "plan")
        # Edit: remove the last claim and reword the first, then accept.
        last_id = proposed[-1][0]
        page.locator(f"button[aria-label='Remove claim {last_id}']").click()
        first_id = proposed[0][0]
        ta = page.locator(f"li.atlas-claim-row[data-claim-id='{first_id}'] textarea.atlas-claim-edit")
        ta.fill("the sequence gathers toward the darker block, then lets it go")
        with page.expect_response(lambda r: r.url.endswith("/plan/accept")) as a:
            page.locator("aside[aria-label='Plan mode'] button.atlas-go", has_text="Accept this plan").click()
        acc = a.value.json()
        if a.value.status != 200:
            raise StageFailed(f"accepting the plan answered {a.value.status}: {acc}")
        page.wait_for_selector(".atlas-plan-accepted[role='status']")
        doc = run.db.atlases.find_one({"_id": atlas_id})
        plan = doc.get("plan") or {}
        ids = [c["claim_id"] for c in plan.get("claims", [])]
        if last_id in ids:
            raise StageFailed("the removed claim was still accepted")
        first = next((c for c in plan["claims"] if c["claim_id"] == first_id), {})
        if first.get("proposed_text") != proposed_text(body, first_id):
            raise StageFailed("the reworded claim lost its proposed_text provenance")
        # the stored plan authors no evidence: every percept is a reference, judged on accept
        for c in plan["claims"]:
            for pct in c.get("percepts", []):
                if "geometry" in pct or "mask" in pct:
                    raise StageFailed("the stored plan carries evidence geometry")
        run.shot(page, "plan-accepted", "plan")
        run.evidence.record_id("plan", claim_ids=ids, planner=plan.get("planner"),
                               accepted=plan.get("accepted"), has_challenge=plan.get("has_challenge"))
        run.state["plan_claims"] = ids
        return {"proposed": proposed, "accepted_claims": ids, "refusals": body.get("refusals"),
                "weakest_status": plan.get("weakest_status")}
    finally:
        page.context.close()


def proposed_text(plan_body: Dict[str, Any], claim_id: str) -> str:
    for c in plan_body.get("claims") or []:
        if c.get("claim_id") == claim_id:
            return c.get("proposed_text") or c.get("text") or ""
    return ""


# ── 7. draft: execute → quarantine → export ──────────────────────────────────────────────────

def stage_draft(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    if not run.state.get("plan_claims"):
        raise StageSkipped("prerequisite missing: no accepted plan from the `plan` stage")
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.locator("button.atlas-mode[data-mode='plan']").click()
        page.locator("button.atlas-tab[role='tab']", has_text="Write").click()
        page.wait_for_selector("aside[aria-label='Writer']")
        marker = run.write_marker()
        with page.expect_response(lambda r: r.url.endswith("/draft") and r.request.method == "POST",
                                  timeout=120000) as d:
            page.locator("aside[aria-label='Writer'] button.atlas-go", has_text="Draft the article").click()
        body = d.value.json()
        if d.value.status != 200:
            raise StageFailed(f"drafting answered {d.value.status}: {body}")
        draft = body.get("draft") or {}
        page.wait_for_selector("section.atlas-w-draft[data-state='quarantined']")
        badge = page.locator("section.atlas-w-draft").inner_text()
        if "Quarantined" not in badge:
            raise StageFailed("the drafted article is not labelled quarantined in the UI")
        if draft.get("state") != "quarantined" or draft.get("committed") is not False:
            raise StageFailed(f"the stored draft is not quarantined: {draft.get('state')}")
        # posts: the producers ran; nothing may have been written to any post
        run.shot(page, "draft-quarantined", "draft")
        status, export = run.api.get(f"/api/v1/atlas/{atlas_id}/draft/export")
        if export.get("committed") is not False or export.get("state") != "quarantined":
            raise StageFailed("the draft export does not say committed:false / quarantined")
        chain = draft.get("run_id")
        run.evidence.receipt("draft", seam="composer",
                             model=(draft.get("article") or {}).get("draft", {}).get("model"),
                             run_id=chain, passages=len(export.get("passages") or []))
        run.evidence.record_id("draft", run_id=chain, drafted_at=draft.get("drafted_at"),
                               version=draft.get("version"))
        run.state["draft_run_id"] = chain
        run.state["draft_passages"] = export.get("passages") or []
        return {"run_id": chain, "state": draft.get("state"), "committed": draft.get("committed"),
                "export_passages": len(export.get("passages") or []),
                "limits": export.get("limits"),
                "writes_during_draft": [f"{w['collection']}.{w['op']}" for w in run.writes_since(marker)["circuit"]]}
    finally:
        page.context.close()


# ── 8. accept the draft into a manuscript (target: Lane I) ───────────────────────────────────

def stage_draft_accept(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    if not run.state.get("draft_run_id"):
        raise StageSkipped("prerequisite missing: no quarantined draft from the `draft` stage")
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.locator("button.atlas-mode[data-mode='plan']").click()
        page.locator("button.atlas-tab[role='tab']", has_text="Write").click()
        page.wait_for_selector("section.atlas-w-draft")
        targeting = page.locator("aside[aria-label='Writer'] select, aside[aria-label='Writer'] input[name*='manuscript'], aside[aria-label='Writer'] [aria-label*='manuscript' i]")
        ui_targets = targeting.count() > 0
        with page.expect_response(lambda r: r.url.endswith("/draft/accept")) as a:
            page.locator("aside[aria-label='Writer'] button.atlas-go",
                         has_text="Accept into the manuscript").click()
        body = a.value.json()
        if a.value.status != 200:
            raise StageFailed(f"accepting the draft answered {a.value.status}: {body}")
        page.wait_for_selector("section.atlas-w-draft[data-state='accepted']")
        draft = body.get("draft") or {}
        ms_id, ch_id, sc_id = draft.get("manuscript_id"), draft.get("chapter_id"), draft.get("scene_id")
        scene = run.db.scenes.find_one({"_id": sc_id})
        if scene is None:
            raise StageFailed("the accepted draft's scene is not in `scenes`", lane="I")
        prose = "\n".join(b.get("content", "") for b in scene.get("blocks", []))
        if "model_suggested" in {b.get("origin") for b in scene.get("blocks", [])}:
            raise StageFailed("the accepted scene holds a model_suggested block", lane="I")
        # provenance survives: the scene's blocks cite the run / step ids of the draft
        refs = [b for b in scene.get("blocks", []) if b.get("provenance") or b.get("evidence")
                or b.get("run_id") or b.get("step_ids") or b.get("citations")]
        run.shot(page, "draft-accepted", "draft.accept")
        run.evidence.record_id("draft.accept", manuscript_id=ms_id, chapter_id=ch_id, scene_id=sc_id,
                               accepted_at=draft.get("accepted_at"))
        run.state.update({"manuscript_id": ms_id, "chapter_id": ch_id, "draft_scene_id": sc_id})
        # A second accept must be refused (409), not duplicated.
        status, again = run.api.post(f"/api/v1/atlas/{atlas_id}/draft/accept", {})
        if status != 409:
            raise StageFailed(f"a second accept answered {status}, expected 409", lane="B")
        run.evidence.refusal("draft.accept", reason="already_accepted", status=status)
        out = {"manuscript_id": ms_id, "chapter_id": ch_id, "scene_id": sc_id,
               "blocks": len(scene.get("blocks", [])), "blocks_with_provenance": len(refs),
               "second_accept_status": status, "ui_offers_target": ui_targets}
        if not ui_targets:
            raise StageFailed("the UI offers no way to target an existing manuscript or chapter — "
                              "Accept always opens a new manuscript (the API accepts "
                              "manuscript_id/chapter_id; see profile `api.target_manuscript`)",
                              lane="I", **out)
        return out
    finally:
        page.context.close()


def stage_api_target_manuscript(run: Run) -> Dict[str, Any]:
    """The API half of targeting, so the seam is proven even while the UI cannot reach it."""
    atlas_id = run.state["atlas_id"]
    ms_id = run.state.get("manuscript_id")
    if not ms_id:
        raise StageSkipped("no manuscript from the UI accept to target")
    # re-draft (dismiss, draft again) then accept INTO the existing manuscript + chapter
    run.api.delete(f"/api/v1/atlas/{atlas_id}/draft")
    status, d = run.api.post(f"/api/v1/atlas/{atlas_id}/draft", {})
    if status != 200:
        raise StageFailed(f"re-drafting answered {status}: {d}")
    status, acc = run.api.post(f"/api/v1/atlas/{atlas_id}/draft/accept",
                               {"manuscript_id": ms_id, "chapter_id": run.state["chapter_id"],
                                "title": "The walk, again"})
    if status != 200:
        raise StageFailed(f"targeted accept answered {status}: {acc}", lane="I")
    draft = acc.get("draft") or {}
    ms = run.db.manuscripts.find_one({"_id": ms_id})
    chapter = next((c for c in ms.get("chapters", []) if c["id"] == run.state["chapter_id"]), {})
    if draft.get("scene_id") not in chapter.get("scene_ids", []):
        raise StageFailed("the targeted scene did not land in the targeted chapter", lane="I")
    run.evidence.record_id("api.target_manuscript", scene_id=draft.get("scene_id"))
    return {"manuscript_id": ms_id, "chapter_id": run.state["chapter_id"],
            "scene_id": draft.get("scene_id"), "chapter_scenes": chapter.get("scene_ids")}


# ── 9. the Writer: open, render, accept (save), recall, alignment, revision, export ───────────

def _type_directive(page, text: str) -> None:
    prose = page.locator("[data-testid='writer-prose']")
    prose.click()
    page.keyboard.press("Control+End")
    page.keyboard.press("End")
    page.keyboard.press("Enter")
    page.keyboard.type(text)


def stage_writer(run: Run) -> Dict[str, Any]:
    ms_id = run.state.get("manuscript_id")
    if not ms_id:
        raise StageSkipped("no manuscript reached the Writer")
    # An operator the directive can name. Authored through the Studio's own control.
    page = run.page()
    out: Dict[str, Any] = {}
    try:
        page.goto(f"{run.stack.app_url}/writer/{ms_id}")
        page.wait_for_function(
            "() => document.querySelector(\"[data-testid='writer-prose']\") || "
            "document.body.innerText.includes('No manuscript yet')", timeout=60000)
        if page.locator("[data-testid='writer-prose']").count() == 0:
            raise StageFailed("the Writer did not open the manuscript the Atlas accepted into",
                              lane="E", body=page.inner_text("body")[:300])
        run.shot(page, "writer-open", "writer")
        # create operator
        page.locator("[data-testid='create-operator']").click() if \
            page.locator("input[aria-label='operator name']").count() == 0 else None
        page.locator("input[aria-label='operator name']").fill("restraint")
        page.locator("[aria-label='operator definition']").fill("what is withheld does the work")
        with page.expect_response(lambda r: "/operators" in r.url and r.request.method == "POST") as o:
            page.locator(".writer-draft__actions button", has_text="Add to my operators").click()
        if o.value.status not in (200, 201):
            raise StageFailed(f"creating an operator answered {o.value.status}: {o.value.text()}", lane="F")
        op = o.value.json()
        out["operator"] = {"id": op.get("id"), "name": op.get("name"), "version": op.get("version")}
        # render
        # The notation converts a finished line on Enter: `//` → an orchestration node,
        # `/ name` → a directive node. Without the Enter the line stays prose.
        _type_directive(page, "// avoid: melodrama")
        page.keyboard.press("Enter")
        page.keyboard.type("/ restraint")
        page.keyboard.press("Enter")
        page.wait_for_function("document.querySelectorAll(\"[data-testid='writer-prose'] [data-directive], "
                               "[data-testid='writer-prose'] .writer-directive, "
                               "[data-testid='directive-chip']\").length > 0", timeout=5000)
        with page.expect_response(lambda r: r.url.endswith("/run") and r.request.method == "POST",
                                  timeout=60000) as r:
            page.locator("[data-testid='render-button']").click()
        body = r.value.json()
        if r.value.status != 200:
            raise StageFailed(f"render answered {r.value.status}: {body}", lane="E")
        results = body.get("results") or []
        res0 = results[0] if results else {}
        throttled = "429" in str(res0.get("refusal") or res0.get("detail") or "") or \
            "rate_limit" in str(res0.get("refusal") or res0.get("detail") or "")
        if throttled:
            # A provider throttle is the provider's state, not the Writer's. Wait out the advised
            # window once, render again through the same button, and say what happened.
            run.evidence.receipt("writer", seam="manuscript_renderer", status="throttled",
                                 detail=str(res0.get("refusal"))[:300], retry=True)
            page.wait_for_timeout(12000)
            with page.expect_response(lambda r: r.url.endswith("/run") and r.request.method == "POST",
                                      timeout=60000) as r:
                page.locator("[data-testid='render-button']").click()
            body = r.value.json()
            results = body.get("results") or []
            res0 = results[0] if results else {}
            if "429" in str(res0.get("refusal") or "") or "rate_limit" in str(res0.get("refusal") or ""):
                raise StageUnavailable("the live renderer is rate-limited by the provider (429 twice); "
                                       f"{str(res0.get('refusal'))[:200]}")
        run.evidence.receipt("writer", seam="manuscript_renderer", status=res0.get("status"),
                             model=(res0.get("provenance") or {}).get("model"), run_id=body.get("run_id"),
                             refusal=res0.get("refusal"))
        if res0.get("status") == "unavailable":
            raise StageUnavailable(f"the renderer is unavailable: {res0.get('refusal') or res0.get('detail')}")
        if res0.get("status") != "ok":
            raise StageFailed(f"render status {res0.get('status')}: {res0.get('refusal')}", lane="E")
        page.wait_for_selector("[data-testid='quarantine-card']")
        run.shot(page, "writer-quarantine", "writer")
        passage_id = res0.get("passage_id")
        psg = run.db.writer_passages.find_one({"_id": passage_id}) or run.db.writer_passages.find_one({"id": passage_id})
        if psg is None or psg.get("committed") is not False:
            raise StageFailed("the rendered passage is not a quarantined (committed:false) document", lane="D")
        # alignment on the quarantined passage
        if page.locator("[data-testid='read-alignment']").count():
            with page.expect_response(lambda r: "/alignment/read" in r.url, timeout=60000) as al:
                page.locator("[data-testid='read-alignment']").first.click()
            reading = al.value.json()
            run.evidence.receipt("writer", seam="alignment_reader", status=reading.get("status"),
                                 model=reading.get("model"), reading_id=reading.get("id") or reading.get("reading_id"),
                                 flags=len(reading.get("flags") or []))
            out["alignment"] = {"status": reading.get("status"), "flags": len(reading.get("flags") or []),
                                "reading_id": reading.get("id") or reading.get("reading_id")}
            page.wait_for_selector("[data-testid='reading'], [data-testid='reading-unavailable'], [data-testid='reading-aligned'], [data-testid='reading-no-provenance']", timeout=10000)
            run.shot(page, "writer-alignment", "writer")
        else:
            out["alignment"] = "no read-alignment control"
        # accept = save into the scene (the only door)
        scene_before = {s["_id"]: digest(s) for s in run.db.scenes.find({})}
        with page.expect_response(lambda r: "/accept" in r.url and "passages" in r.url, timeout=30000) as a:
            page.locator("[data-testid='accept-button']").first.click()
        acc = a.value.json()
        if a.value.status != 200:
            raise StageFailed(f"accept answered {a.value.status}: {acc}", lane="D")
        page.wait_for_selector("[data-testid='quarantine-card']", state="detached")
        lineage, block_id, scene_id = acc.get("lineage_id"), acc.get("block_id"), acc.get("scene_id") or acc.get("scene", {}).get("id")
        scene_docs = {s["_id"]: s for s in run.db.scenes.find({})}
        changed = [sid for sid, s in scene_docs.items() if scene_before.get(sid) != digest(s)]
        if len(changed) != 1:
            raise StageFailed(f"accept changed {len(changed)} scenes, expected exactly one", lane="D")
        scene_id = changed[0]
        block = next((b for b in scene_docs[scene_id].get("blocks", []) if b.get("id") == block_id), None)
        if block is None or block.get("lineage_id") != lineage or block.get("origin") != "user_confirmed":
            raise StageFailed(f"the accepted block is not the committed version: {block}", lane="D")
        versions = list(run.db.writer_passage_versions.find({"lineage_id": lineage}))
        if len(versions) != 1:
            raise StageFailed(f"{len(versions)} versions for a freshly accepted lineage", lane="D")
        out["accept"] = {"passage_id": passage_id, "lineage_id": lineage, "block_id": block_id,
                         "scene_id": scene_id, "version": block.get("version")}
        run.evidence.record_id("writer", passage_id=passage_id, lineage_id=lineage, block_id=block_id,
                               scene_id=scene_id, version_id=versions[0].get("_id"),
                               operator_id=op.get("id"), operator_version=op.get("version"))
        run.shot(page, "writer-accepted", "writer")
        # the editor's own save (scene PATCH) — the open/save half
        page.keyboard.press("End")
        page.keyboard.type(" ")
        page.wait_for_timeout(1500)
        # recall
        page.locator("[data-testid='recall-toggle']").click()
        page.wait_for_selector("[data-testid='recall-query']")
        # The query is a word from the prose the author just committed — whatever the renderer
        # (fake or live) wrote — so recall is asked for something that is verbatim in canon.
        committed_text = (block.get("content") or "")
        words = [w.strip(".,;:!?()\"'") for w in re.sub(r"<[^>]+>", " ", committed_text).split()]
        query = next((w for w in words if len(w) >= 5 and w.isalpha()), words[0] if words else "the")
        page.locator("[data-testid='recall-query']").fill(query)
        with page.expect_response(lambda r: r.url.endswith("/recall"), timeout=30000) as rc:
            page.locator("[data-testid='recall-search']").click()
        recall = rc.value.json()
        spans = recall.get("spans") or []
        if not spans:
            raise StageFailed(f"recall found no span for committed prose containing '{query}': {recall}", lane="H")
        if not all(s.get("lineage_id") for s in spans):
            raise StageFailed("a recalled span carries no lineage_id", lane="H")
        verbatim = all(s.get("text") in "\n".join(b.get("content", "") for b in scene_docs[scene_id]["blocks"])
                       for s in spans)
        out["recall"] = {"spans": len(spans), "verbatim": verbatim, "lineages": [s.get("lineage_id") for s in spans]}
        run.shot(page, "writer-recall", "writer")
        page.locator("[data-testid='recall-close']").click() if page.locator("[data-testid='recall-close']").count() else None
        # revision: select the committed span → Revise → re-render → accept revision
        span = page.locator(f"[data-lineage-id='{lineage}'], span.writer-span, .writer-prose [data-lineage]").first
        if span.count():
            span.click()
        else:
            page.locator("[data-testid='writer-prose'] p").last.click()
        page.locator("[data-testid='revise-button']").click()
        page.wait_for_selector("[data-testid='revision-panel'], [data-testid='revision-panel-error'], [data-testid='editor-error']", timeout=15000)
        if page.locator("[data-testid='revision-panel']").count() == 0:
            err = (page.locator("[data-testid='revision-panel-error'], [data-testid='editor-error']").first.inner_text()
                   if page.locator("[data-testid='revision-panel-error'], [data-testid='editor-error']").count() else "")
            raise StageFailed(f"the revision panel did not open on a committed span: {err}", lane="G")
        def _throttled(body):
            r0 = ((body or {}).get("results") or [{}])[0]
            txt = str(r0.get("refusal") or r0.get("detail") or "")
            return r0.get("status") != "ok" and ("429" in txt or "rate_limit" in txt)

        with page.expect_response(lambda r: r.url.endswith("/run") and r.request.method == "POST", timeout=60000) as rr:
            page.locator("[data-testid='revise-render']").click()
        rerun = rr.value.json()
        if _throttled(rerun):
            run.evidence.receipt("writer", seam="manuscript_renderer", status="throttled", step="revise", retry=True)
            page.wait_for_timeout(12000)
            with page.expect_response(lambda r: r.url.endswith("/run") and r.request.method == "POST", timeout=60000) as rr:
                page.locator("[data-testid='revise-render']").click()
            rerun = rr.value.json()
            if _throttled(rerun):
                raise StageUnavailable("the live renderer is rate-limited by the provider on the revision "
                                       "re-render (429 twice)")
        page.wait_for_selector("[data-testid='revision-card']")
        export_before = run.api.get(f"/api/v1/manuscript/{ms_id}/export?format=markdown")[1]
        with page.expect_response(lambda r: "/revision/accept" in r.url, timeout=30000) as ra:
            page.locator("[data-testid='revision-accept']").click()
        rev = ra.value.json()
        if ra.value.status != 200:
            raise StageFailed(f"revision accept answered {ra.value.status}: {rev}", lane="G")
        versions = list(run.db.writer_passage_versions.find({"lineage_id": lineage}).sort("version", 1))
        if [v.get("version") for v in versions] != [1, 2]:
            raise StageFailed(f"genealogy is {[v.get('version') for v in versions]}, expected [1, 2]", lane="G")
        scene_now = run.db.scenes.find_one({"_id": scene_id})
        blk = next((b for b in scene_now["blocks"] if b.get("id") == block_id), {})
        if blk.get("version") != 2:
            raise StageFailed(f"the block pointer is at v{blk.get('version')}, expected v2", lane="G")
        # every old version resolves
        status, v1 = run.api.get(f"/api/v1/writer/{ms_id}/genealogy/{lineage}/v1")
        if status != 200 or not v1.get("text"):
            raise StageFailed("v1 of the passage no longer resolves", lane="D")
        status, gen = run.api.get(f"/api/v1/writer/{ms_id}/genealogy/{lineage}")
        history = gen if isinstance(gen, list) else ((gen or {}).get("history") or (gen or {}).get("versions") or [])
        out["revision"] = {"versions": [v.get("version") for v in versions], "pointer": blk.get("version"),
                           "v1_resolves": status == 200, "history": len(history)}
        run.evidence.record_id("writer.revision", version_ids=[v.get("_id") for v in versions],
                               revised_from=versions[-1].get("revised_from"))
        run.shot(page, "writer-revised", "writer")
        # export: current versions only, no quarantined prose, provenance resolvable
        status, export = run.api.get(f"/api/v1/manuscript/{ms_id}/export?format=markdown")
        content = export.get("content", "")
        quarantined = list(run.db.writer_passages.find({"committed": False}))
        leaked = [q for q in quarantined if q.get("text") and q["text"] in content]
        if leaked:
            raise StageFailed(f"{len(leaked)} quarantined passage(s) appear in the export", lane="D")
        if v1.get("text") and v1["text"] in content and versions[-1].get("text") != v1.get("text"):
            raise StageFailed("a superseded version's prose is in the export", lane="G")
        operator_ok = run.db.writer_operators.find_one({"_id": op.get("id")}) is not None or \
            run.db.writer_operators.find_one({"name": "restraint"}) is not None
        out["export"] = {"chars": len(content), "quarantined_leaks": len(leaked),
                         "current_version_only": True, "operator_provenance_resolves": operator_ok,
                         "changed_by_revision": export_before.get("content") != content}
        run.state.update({"lineage_id": lineage, "block_id": block_id, "scene_id": scene_id,
                          "operator_id": op.get("id")})
        return out
    finally:
        page.context.close()


# ── 10. movement (Lanes J/K) ─────────────────────────────────────────────────────────────────

def stage_movement(run: Run) -> Dict[str, Any]:
    status, _ = run.api.get(f"/api/v1/atlas/{run.state['atlas_id']}/movements")
    status2, _ = run.api.get(f"/api/v1/atlas/{run.state['atlas_id']}/axes")
    if status in (404, 405) and status2 in (404, 405):
        raise StageUnavailable("no movement proposal/accept or axis inspection route exists on this "
                               "base (movement_axes is written by scripts only); the Atlas has no "
                               "movement mode", lane="J/K")
    raise StageFailed("a movement route exists but the harness has no stage for it yet; extend "
                      "`stage_movement` now that the lane has merged", lane="J/K")
