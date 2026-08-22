"""
The run context every stage is handed, and the one rule the runner enforces over all of them:
after every stage, every fixture post is re-hashed, and a hash that changed without a stage
having said "I will write to this post, because the author accepted X" is an UNEXPECTED MUTATION
— reported as a field-level diff, never absorbed.

Stage outcomes are one of:
  pass         the stage ran through the UI and its assertions held
  fail         it ran and an assertion did not hold (a domain defect, filed against its lane)
  unavailable  the seam it needs does not exist on this base yet (names the lane)
  skipped      deliberately not run in this mode (live-only, profile not selected)
  error        the harness itself broke (a harness defect, ours)
"""
from __future__ import annotations

import json
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .ledger import Evidence, Stopwatch, digest, field_diff

PASS, FAIL, UNAVAILABLE, SKIPPED, ERROR = "pass", "fail", "unavailable", "skipped", "error"


class StageUnavailable(Exception):
    def __init__(self, detail: str, lane: Optional[str] = None):
        super().__init__(detail)
        self.lane = lane


class StageFailed(AssertionError):
    def __init__(self, detail: str, lane: Optional[str] = None, **extra: Any):
        super().__init__(detail)
        self.lane = lane
        self.extra = extra


class StageSkipped(Exception):
    pass


@dataclass
class StageResult:
    name: str
    status: str
    detail: str = ""
    lane: Optional[str] = None
    ms: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    screenshots: List[str] = field(default_factory=list)
    mutations: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail, "lane": self.lane,
                "ms": round(self.ms, 1), "evidence": self.evidence,
                "screenshots": self.screenshots, "mutations": self.mutations}


class Api:
    """The same HTTP the browser uses, for the profile stages and for reading state back."""

    def __init__(self, base: str, api_key: str):
        self.base = base
        self.key = api_key

    def call(self, path: str, data: Any = None, method: Optional[str] = None,
             timeout: float = 120, headers: Optional[Dict[str, str]] = None):
        body = json.dumps(data).encode() if data is not None else None
        h = {"X-API-Key": self.key, "Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=body, headers=h,
                                     method=method or ("POST" if body is not None else "GET"))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw) if raw else None
            except ValueError:
                return e.code, {"raw": raw.decode(errors="replace")}

    def get(self, path, **kw):
        return self.call(path, None, "GET", **kw)

    def post(self, path, data=None, **kw):
        return self.call(path, data if data is not None else {}, "POST", **kw)

    def delete(self, path, **kw):
        return self.call(path, None, "DELETE", **kw)


@dataclass
class Run:
    run_id: str
    run_dir: Path
    mode: str                       # offline | live
    profile: str                    # default | real-photo
    stack: Any
    db: Any                         # pymongo Database
    api: Api
    evidence: Evidence
    posts: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # key → post doc (raw)
    post_ids: Dict[str, str] = field(default_factory=dict)           # key → id
    state: Dict[str, Any] = field(default_factory=dict)              # ids stages hand forward
    results: List[StageResult] = field(default_factory=list)
    browser: Any = None
    headed: bool = False
    slow: int = 0
    _shots: int = 0
    _last_hashes: Dict[str, str] = field(default_factory=dict)

    # ── fixture state ──
    def fixture_post_ids(self) -> List[str]:
        return list(self.post_ids.values())

    #: The collections the circuit owns. Writes elsewhere (the research-agent worker's queue,
    #: vision-run observability, usage instrumentation) are background and are never what a
    #: "writes nothing" assertion is about — but they are still listed, never hidden.
    CIRCUIT_COLLECTIONS = ("posts", "atlases", "corpora", "manuscripts", "scenes", "scene_versions",
                           "writer_passages", "writer_passage_versions", "writer_operators",
                           "writer_readings", "writer_library", "writer_registers", "runs",
                           "curator_proposals", "movement_axes")

    #: The post fields that are the ledger. Anything committed here is evidence the author
    #: accepted; an accepting step may append to them and must never remove or rewrite.
    LEDGER_FIELDS = ("visual_marks", "region_annotations", "grounds", "percepts", "visual_layers")

    def write_marker(self) -> int:
        return self.api.get("/__rehearsal/writes")[1]["count"]

    def writes_since(self, marker: int) -> Dict[str, Any]:
        """`{circuit: [..], background: [..]}` — every write since `marker`, split."""
        body = self.api.get(f"/__rehearsal/writes?since={marker}")[1]
        circuit = [w for w in body["writes"] if w["collection"] in self.CIRCUIT_COLLECTIONS]
        background = [w for w in body["writes"] if w["collection"] not in self.CIRCUIT_COLLECTIONS]
        return {"circuit": circuit, "background": background, "count": len(circuit)}

    def hash_posts(self) -> Dict[str, str]:
        out = {}
        for doc in self.db.posts.find({"photo_public_id": {"$regex": "^vertical-rehearsal"}}):
            out[str(doc["_id"])] = digest(doc)
        return out

    def snapshot_posts(self) -> Dict[str, Dict[str, Any]]:
        return {str(d["_id"]): d for d in
                self.db.posts.find({"photo_public_id": {"$regex": "^vertical-rehearsal"}})}

    # ── browser ──
    def page(self, **kw):
        ctx = self.browser.new_context(viewport={"width": 1440, "height": 900},
                                       reduced_motion=kw.pop("reduced_motion", None),
                                       color_scheme=kw.pop("color_scheme", None))
        page = ctx.new_page()
        page.set_default_timeout(kw.pop("timeout", 30000))
        page.on("dialog", lambda d: d.accept(kw.get("dialog_text", "Rehearsal manuscript")))
        console: List[str] = []
        page.on("console", lambda m: console.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: console.append(f"[pageerror] {e}"))
        page._vr_console = console  # type: ignore[attr-defined]
        return page

    def shot(self, page, name: str, stage: str = "") -> str:
        self._shots += 1
        rel = f"screenshots/{self._shots:03d}-{name}.png"
        path = self.run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=False)
        self.evidence.screenshots.append({"stage": stage, "name": name, "path": rel})
        return rel

    # ── stages ──
    def stage(self, name: str, fn: Callable[["Run"], Optional[Dict[str, Any]]], *,
              expected_post_writes: Optional[Callable[["Run"], List[str]]] = None) -> StageResult:
        """Run one stage and audit the fixture posts afterwards."""
        before_docs = self.snapshot_posts()
        before = {k: digest(v) for k, v in before_docs.items()}
        sw = Stopwatch()
        res = StageResult(name=name, status=PASS)
        shots_before = len(self.evidence.screenshots)
        try:
            ev = fn(self) or {}
            res.evidence = ev
        except StageUnavailable as e:
            res.status, res.detail, res.lane = UNAVAILABLE, str(e), e.lane
        except StageSkipped as e:
            res.status, res.detail = SKIPPED, str(e)
        except KeyError as e:
            # A stage reaching for state an earlier stage never produced is a prerequisite that
            # did not pass, not a harness defect — say which one.
            if str(e).strip("'") in ("atlas_id", "node_ids", "walk_posts", "corpus_id", "manuscript_id",
                                    "chapter_id", "scene_id", "lineage_id", "note_node"):
                res.status = SKIPPED
                res.detail = f"prerequisite missing: no `{str(e).strip(chr(39))}` from an earlier stage"
            else:
                res.status, res.detail = ERROR, f"KeyError: {e}"
        except StageFailed as e:
            res.status, res.detail, res.lane = FAIL, str(e), e.lane
            res.evidence = dict(e.extra)
        except Exception as e:  # noqa: BLE001
            res.status = ERROR
            res.detail = f"{type(e).__name__}: {e}"
            (self.run_dir / "logs").mkdir(exist_ok=True, parents=True)
            with open(self.run_dir / "logs" / "harness-errors.log", "a") as f:
                f.write(f"--- {name}\n{traceback.format_exc()}\n")
        res.ms = sw.ms()
        res.screenshots = [s["path"] for s in self.evidence.screenshots[shots_before:]]

        # the mutation audit
        after_docs = self.snapshot_posts()
        after = {k: digest(v) for k, v in after_docs.items()}
        try:
            allowed = set(expected_post_writes(self) if expected_post_writes else [])
        except KeyError:
            allowed = set()
        for pid in sorted(set(before) | set(after)):
            if before.get(pid) == after.get(pid):
                continue
            diff = field_diff(before_docs.get(pid), after_docs.get(pid))
            entry = {"post_id": pid, "stage": name, "before": before.get(pid),
                     "after": after.get(pid), "expected": pid in allowed, "diff": diff}
            # An accepted step may ADD evidence. Removing or altering something already
            # committed is destructive whatever stage did it, and is reported as unexpected.
            destructive = [d for d in diff
                           if d["kind"] in ("removed", "changed")
                           and d["path"].split(".")[0].split("[")[0] in self.LEDGER_FIELDS]
            if destructive:
                entry["destructive"] = destructive
            res.mutations.append(entry)
            if pid not in allowed:
                self.evidence.unexpected.append(entry)
            elif destructive and after_docs.get(pid) is not None:
                self.evidence.unexpected.append({**entry, "reason":
                                                 "an accepted step removed or altered committed evidence"})
        self.evidence.hash_timeline.append({"stage": name, "hashes": after})
        self.results.append(res)
        print(f"  [{res.status:>11}] {name}  {res.ms/1000:.1f}s"
              + (f"  — {res.detail}" if res.detail else "")
              + (f"  (lane {res.lane})" if res.lane else ""), flush=True)
        return res
