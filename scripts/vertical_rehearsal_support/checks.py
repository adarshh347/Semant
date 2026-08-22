"""
Accessibility / real-rendering checks, and the 60-image performance profile.

Performance failure is REPORTED against the declared budgets (`research/rehearsals/vertical/
budgets.json`); it never weakens a correctness stage. Memory is the page's JS heap as Chromium's
CDP reports it after a forced GC, which is the one number that compares run to run.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from .runner import Run, StageFailed

BUDGETS_PATH = Path(__file__).resolve().parents[2] / "research" / "rehearsals" / "vertical" / "budgets.json"


def load_budgets() -> Dict[str, Any]:
    return json.loads(BUDGETS_PATH.read_text())


# ── accessibility + rendering ───────────────────────────────────────────────────────────────

def check_a11y(run: Run) -> Dict[str, Any]:
    atlas_id = run.state["atlas_id"]
    out: Dict[str, Any] = {}
    page = run.page()
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.wait_for_timeout(800)
        # semantic labels the circuit depends on
        labels = {
            "mode group": "div.atlas-modes[role='group'][aria-label]",
            "live status": ".atlas-head-status[aria-live]",
        }
        out["labels"] = {k: page.locator(v).count() > 0 for k, v in labels.items()}
        page.locator("button.atlas-mode[data-mode='plan']").click()
        page.wait_for_selector(".atlas-with-plan")
        out["labels"]["plan/write tabs"] = page.locator("[role='tablist'][aria-label='Plan or write']").count() > 0
        out["labels"]["plan panel"] = page.locator("aside[aria-label='Plan mode']").count() > 0
        out["labels"]["minimap"] = page.locator(".react-flow__minimap svg[role='img'][aria-labelledby]").count() > 0
        page.locator("button.atlas-mode[data-mode='canvas']").click()
        page.wait_for_selector(".atlas-shell[data-mode='canvas']")
        # keyboard traversal: Tab through the mode buttons, Enter switches mode, focus is visible
        page.locator("button.atlas-mode[data-mode='canvas']").focus()
        traversal: List[str] = []
        for _ in range(6):
            page.keyboard.press("Tab")
            traversal.append(page.evaluate(
                "() => { const e = document.activeElement; return (e.tagName||'')+"
                "(e.getAttribute('data-mode')?'[data-mode='+e.getAttribute('data-mode')+']':'')+"
                "(e.getAttribute('aria-label')?'['+e.getAttribute('aria-label')+']':'')+"
                "(e.textContent?':'+e.textContent.trim().slice(0,24):''); }"))
        out["tab_order"] = traversal
        page.locator("button.atlas-mode[data-mode='light-table']").focus()
        page.keyboard.press("Enter")
        page.wait_for_selector(".atlas-shell[data-mode='light-table']", timeout=5000)
        out["keyboard_mode_switch"] = True
        focus_style = page.evaluate(
            "() => { const e = document.querySelector(\"button.atlas-mode[data-mode='light-table']\");"
            " e.focus(); const s = getComputedStyle(e); return {outline: s.outlineStyle, width: s.outlineWidth,"
            " shadow: s.boxShadow}; }")
        out["focus_visible"] = focus_style
        out["focus_ring_present"] = (focus_style.get("outline") not in ("none", "") and
                                     focus_style.get("width") not in ("0px", "")) or \
            (focus_style.get("shadow") not in ("none", ""))
        # Escape closes the Differential and returns focus to the Atlas
        read = page.locator("button.lt-read").first
        read.click()
        page.wait_for_selector("div.atlas-focus[role='dialog'][aria-modal='true']")
        out["dialog_semantics"] = True
        page.keyboard.press("Escape")
        page.wait_for_selector("div.atlas-focus", state="detached")
        out["escape_closes_dialog"] = True
        page.locator("button.atlas-mode[data-mode='plan']").click()
        page.wait_for_selector(".atlas-with-plan .react-flow__edge")
        run.shot(page, "a11y-canvas-light", "a11y")
    finally:
        page.context.close()

    # dark mode: the app's own toggle + data-theme, rendered for real
    page = run.page(color_scheme="dark")
    try:
        page.add_init_script("try { localStorage.setItem('theme', 'dark') } catch (e) {}")
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.locator("button.atlas-mode[data-mode='plan']").click()
        page.wait_for_selector(".atlas-with-plan .react-flow__edge")
        page.wait_for_timeout(600)
        out["data_theme"] = page.evaluate("document.documentElement.getAttribute('data-theme')")
        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        out["dark_body_background"] = bg
        rgb = [int(x) for x in bg.strip("rgba() ").split(",")[:3]] if bg.startswith("rgb") else [255, 255, 255]
        out["dark_background_is_dark"] = sum(rgb) / 3 < 128
        run.shot(page, "a11y-canvas-dark", "a11y")
    finally:
        page.context.close()

    # reduced motion: honoured by CSS (no running animations / transitions on the canvas)
    page = run.page(reduced_motion="reduce")
    try:
        page.goto(f"{run.stack.app_url}/atlas/{atlas_id}")
        page.wait_for_selector(".atlas-node")
        page.locator("button.atlas-mode[data-mode='plan']").click()
        page.wait_for_selector(".atlas-with-plan .react-flow__edge")
        page.wait_for_timeout(400)
        out["reduced_motion_media"] = page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        anim = page.evaluate(
            "() => document.getAnimations ? document.getAnimations().filter(a => a.playState === 'running').length : -1")
        out["running_animations_under_reduced_motion"] = anim
        # React Flow edges: DOM + pixels
        edges = page.locator(".react-flow__edge").count()
        rel = page.locator(".react-flow__edge.atlas-relation").count()
        paths = page.evaluate(
            "() => Array.from(document.querySelectorAll('.react-flow__edge path')).map(p => p.getTotalLength())")
        out["edges"] = {"dom": edges, "relation": rel, "path_lengths": [round(x, 1) for x in paths]}
        shot = run.shot(page, "a11y-edges-reduced-motion", "a11y")
        out["edge_screenshot"] = shot
    finally:
        page.context.close()

    problems = []
    if not all(out["labels"].values()):
        problems.append(f"missing semantic labels: {[k for k, v in out['labels'].items() if not v]}")
    if not out.get("focus_ring_present"):
        problems.append("no visible focus ring on the mode buttons")
    if out.get("data_theme") != "dark" or not out.get("dark_background_is_dark"):
        problems.append("dark mode did not render dark")
    if out.get("running_animations_under_reduced_motion", 0) > 0:
        problems.append(f"{out['running_animations_under_reduced_motion']} animation(s) running under reduced motion")
    if out["edges"]["relation"] < 1 or not any(x > 0 for x in out["edges"]["path_lengths"]):
        problems.append("no React Flow relation edge with a drawn path")
    if problems:
        raise StageFailed("; ".join(problems), lane="A", **out)
    return out


# ── the 60-image performance profile ────────────────────────────────────────────────────────

def _heap_mb(page) -> float:
    cdp = page.context.new_cdp_session(page)
    cdp.send("Performance.enable")
    try:
        cdp.send("HeapProfiler.enable")
        cdp.send("HeapProfiler.collectGarbage")
    except Exception:  # noqa: BLE001
        pass
    m = cdp.send("Performance.getMetrics")["metrics"]
    used = next((x["value"] for x in m if x["name"] == "JSHeapUsedSize"), 0)
    cdp.detach()
    return round(used / (1024 * 1024), 1)


def check_performance(run: Run) -> Dict[str, Any]:
    budgets = load_budgets()
    ids = [run.post_ids[k] for k in run.post_ids if k.startswith("perf-")]
    if len(ids) < 60:
        raise StageFailed(f"the performance corpus has {len(ids)} images, expected 60")
    status, atlas = run.api.post("/api/v1/atlas/", {"title": "sixty", "post_ids": ids[:60]})
    aid = atlas["id"]
    out: Dict[str, Any] = {"atlas_id": aid, "images": 60, "measured": {}, "budgets": budgets["ms"]}
    page = run.page(timeout=90000)
    try:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Performance.enable")
        t0 = time.perf_counter()
        page.goto(f"{run.stack.app_url}/atlas/{aid}")
        page.wait_for_function("document.querySelectorAll('.atlas-node').length >= 60")
        out["measured"]["initial_hydration"] = (time.perf_counter() - t0) * 1000
        page.wait_for_timeout(500)
        out["measured"]["memory_after_hydration_mb"] = _heap_mb(page)
        # Canvas mode has no sized pane on this base (see stage atlas.canvas); pan/zoom are
        # measured on the same renderer in Plan mode, and the report says so.
        from .stages import canvas_geometry, enter_sized_canvas
        if canvas_geometry(page)["pane_h"] <= 100:
            enter_sized_canvas(page)
            out["pan_zoom_measured_in"] = "plan"
        else:
            out["pan_zoom_measured_in"] = "canvas"
        # pan: drag the pane; zoom: wheel. Measured as wall time until the viewport transform settles.
        pane = page.locator(".react-flow__pane")
        box = pane.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        t1 = time.perf_counter()
        page.mouse.move(cx, cy)
        page.mouse.down()
        for i in range(1, 11):
            page.mouse.move(cx + 25 * i, cy + 10 * i)
        page.mouse.up()
        page.wait_for_timeout(50)
        out["measured"]["pan"] = (time.perf_counter() - t1) * 1000
        t2 = time.perf_counter()
        for _ in range(5):
            page.mouse.wheel(0, -200)
        page.wait_for_timeout(50)
        for _ in range(5):
            page.mouse.wheel(0, 200)
        page.wait_for_timeout(50)
        out["measured"]["zoom"] = (time.perf_counter() - t2) * 1000
        frames = page.evaluate("""() => new Promise(res => { let n = 0, t0 = performance.now();
            function f() { n++; if (performance.now() - t0 < 500) requestAnimationFrame(f); else res(n); }
            requestAnimationFrame(f); })""")
        out["measured"]["frames_per_second_idle"] = frames * 2
        t3 = time.perf_counter()
        page.locator("button.atlas-mode[data-mode='light-table']").click()
        page.wait_for_function("document.querySelectorAll('li.lt-cell').length >= 60")
        out["measured"]["mode_switch"] = (time.perf_counter() - t3) * 1000
        cell = page.locator("li.lt-cell").first
        cell.locator("button.lt-note-add").click()
        t4 = time.perf_counter()
        with page.expect_response(lambda r: r.url.endswith("/notes") and r.request.method == "POST",
                                  timeout=15000) as n:
            cell.locator("textarea.lt-note-text").first.fill("sixty")
        out["measured"]["notes_save"] = (time.perf_counter() - t4) * 1000 - 0  # includes the debounce
        out["notes_save_includes_debounce_ms"] = True
        out["notes_save_status"] = n.value.status
        t5 = time.perf_counter()
        page.locator("button.atlas-mode[data-mode='canvas']").click()
        page.wait_for_function("document.querySelectorAll('.atlas-node').length >= 60")
        out["measured"]["mode_switch_back"] = (time.perf_counter() - t5) * 1000
        out["measured"]["memory_after_interaction_mb"] = _heap_mb(page)
        run.shot(page, "perf-sixty", "performance")
        for k, v in out["measured"].items():
            run.evidence.timing("performance", k, v if "mb" not in k else 0, value=v)
    finally:
        page.context.close()
    over = []
    for name, limit in budgets["ms"].items():
        v = out["measured"].get(name)
        if v is not None and v > limit:
            over.append(f"{name} {v:.0f}ms > {limit}ms")
    mem_limit = budgets["memory_mb"]["js_heap_after_interaction"]
    if out["measured"]["memory_after_interaction_mb"] > mem_limit:
        over.append(f"js heap {out['measured']['memory_after_interaction_mb']}MB > {mem_limit}MB")
    out["over_budget"] = over
    for k, v in list(out["measured"].items()):
        out["measured"][k] = round(v, 1)
    if over:
        raise StageFailed("over budget: " + "; ".join(over), lane="A", **out)
    return out
