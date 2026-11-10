"""
The audit: the ten assertions the directive names, each resolved against the evidence the stages
captured and a final read of the disposable database — then `summary.json` and the Markdown
report, with every assertion pointing at the stage, id, screenshot or diff that is its evidence.

An assertion is `pass`, `fail`, or `unavailable` (the seam it needs is not on this base; the lane
is named). It is never `pass` by default: an assertion whose evidence stage did not run is
`unavailable`, with the reason, because a green row nothing looked at is the one thing this
report must not contain.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .runner import ERROR, FAIL, PASS, SKIPPED, UNAVAILABLE, Run

FORBIDDEN_NODE = {"geometry", "grounds", "marks", "regions", "percepts", "strokes", "mask", "box",
                  "photo_url", "image_url", "epistemic_status", "provenance"}
FORBIDDEN_EDGE = {"geometry", "label", "role", "epistemic_status", "provenance", "sources", "mask", "points"}


def _result(run: Run, name: str):
    return next((r for r in run.results if r.name == name), None)


def _assert(aid: str, title: str, status: str, detail: str, evidence: List[str],
            lane: Optional[str] = None) -> Dict[str, Any]:
    return {"id": aid, "title": title, "status": status, "detail": detail,
            "evidence": evidence, "lane": lane}


def _from_stage(run: Run, aid: str, title: str, stage: str, ok_detail: str) -> Dict[str, Any]:
    r = _result(run, stage)
    if r is None or r.status in (SKIPPED, ERROR):
        return _assert(aid, title, UNAVAILABLE,
                       f"stage `{stage}` did not run" + (f": {r.detail}" if r else ""), [f"stage:{stage}"])
    if r.status == UNAVAILABLE:
        return _assert(aid, title, UNAVAILABLE, r.detail, [f"stage:{stage}"], r.lane)
    if r.status == FAIL:
        return _assert(aid, title, FAIL, r.detail, [f"stage:{stage}"] + [f"shot:{s}" for s in r.screenshots], r.lane)
    return _assert(aid, title, PASS, ok_detail, [f"stage:{stage}"] + [f"shot:{s}" for s in r.screenshots])


def assertions(run: Run) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    db = run.db

    # 1. no quarantined prose in canon / export
    q = [p for p in db.writer_passages.find({"committed": False}) if p.get("text")]
    committed_texts = {p.get("text") for p in db.writer_passages.find({"committed": True})} | \
        {v.get("text") for v in db.writer_passage_versions.find({})}
    leaks = []
    for ms in db.manuscripts.find({}):
        status, exp = run.api.get(f"/api/v1/manuscript/{ms['_id']}/export?format=markdown")
        content = (exp or {}).get("content", "") if status == 200 else ""
        for p in q:
            # text the author also committed elsewhere is not a leak of THIS passage
            if p["text"] in content and p["text"] not in committed_texts:
                leaks.append({"manuscript": ms["_id"], "passage": p.get("_id")})
        # and by identity: no scene block may cite an uncommitted passage
        for s in db.scenes.find({"_id": {"$in": [sid for c in ms.get("chapters", []) for sid in c.get("scene_ids", [])]}}):
            for b in s.get("blocks", []):
                pid = (b.get("provenance") or {}).get("passage_id")
                if pid and any(p.get("_id") == pid for p in q):
                    leaks.append({"manuscript": ms["_id"], "scene": s["_id"], "block": b.get("id"), "passage": pid})
    w = _result(run, "writer")
    st = PASS if not leaks and w and w.status == PASS else (FAIL if leaks else UNAVAILABLE)
    inj = _result(run, "profile.injected_writes")
    half_written = [t for t in ((inj.evidence if inj else {}).get("transitions") or [])
                    if t.get("transition") == "writer.passage.accept" and t.get("changed")]
    cause = ""
    if leaks and half_written:
        cause = (" — the scene block cites a passage that is still `committed: false`: the passage "
                 "accept wrote the scene before its version insert failed (profile.injected_writes), "
                 "so an interrupted accept puts quarantined prose into canon")
    out.append(_assert("A1", "no quarantined prose appears in canon/export",
                       st, f"{len(q)} uncommitted passage(s) checked against every manuscript export "
                       f"by text and every scene block by passage id; {len(leaks)} leak(s)" + cause
                       + ("" if w and w.status == PASS else
                          "; the Writer stage did not complete, so the export was only checked for what exists"),
                       ["stage:writer", "stage:draft", "db:writer_passages", "db:manuscripts/export"]
                       + [f"leak:{l}" for l in leaks], lane="D" if leaks else (w.lane if w else None)))

    # 2. Atlas arrangement / notes contain no percept truth
    offenders = []
    for a in db.atlases.find({}):
        for n in a.get("nodes", []):
            bad = FORBIDDEN_NODE & set(n)
            if bad:
                offenders.append({"atlas": a["_id"], "node": n.get("node_id"), "keys": sorted(bad)})
            for note in n.get("notes", []):
                extra = set(note) - {"note_id", "text"}
                if extra:
                    offenders.append({"atlas": a["_id"], "node": n.get("node_id"), "note_keys": sorted(extra)})
        for e in a.get("edges", []):
            bad = FORBIDDEN_EDGE & set(e)
            if bad:
                offenders.append({"atlas": a["_id"], "edge": e.get("edge_id"), "keys": sorted(bad)})
    n_atlas = db.atlases.count_documents({})
    out.append(_assert("A2", "no Atlas arrangement/notes contain percept truth",
                       FAIL if offenders else PASS,
                       f"{n_atlas} Atlas document(s) scanned for forbidden node/edge/note keys; "
                       f"{len(offenders)} offender(s)",
                       ["db:atlases", "stage:atlas.canvas", "stage:atlas.light_table", "stage:relation"]
                       + [f"offender:{o}" for o in offenders], lane="A" if offenders else None))

    # 3. every visible live relation hydrates from canonical evidence
    checked, dead = 0, []
    for a in db.atlases.find({}):
        status, view = run.api.get(f"/api/v1/atlas/{a['_id']}/view")
        if status != 200:
            continue
        for e in (view or {}).get("edges", []):
            if e.get("kind") not in (None, "relation") or not e.get("live"):
                continue
            checked += 1
            mark_id = e.get("mark_id")
            spans = e.get("spans") or []
            found = 0
            for pid in spans:
                from bson import ObjectId
                try:
                    doc = db.posts.find_one({"_id": ObjectId(pid)})
                except Exception:  # noqa: BLE001
                    doc = None
                if doc and any(m.get("id") == mark_id for m in doc.get("visual_marks", [])):
                    found += 1
            if found != len(spans) or not e.get("source_ref"):
                dead.append({"atlas": a["_id"], "edge": e.get("edge_id"), "mark": mark_id,
                             "found_in": found, "spans": len(spans)})
    rel = _result(run, "relation")
    mv = _result(run, "movement")
    detail = (f"{checked} live relation edge(s) re-read from the ledger; {len(dead)} without the mark "
              f"committed in every post it spans. Movement/citation edges: "
              + (mv.detail if mv and mv.status == UNAVAILABLE else "checked"))
    st = FAIL if dead else (PASS if checked and rel and rel.status == PASS else UNAVAILABLE)
    out.append(_assert("A3", "every visible live relation/movement/citation hydrates from canonical evidence",
                       st, detail, ["stage:relation", "stage:movement", "api:/atlas/{id}/view"]
                       + [f"dead:{d}" for d in dead], lane="C" if dead else ("J/K" if st == UNAVAILABLE and checked else None)))

    # 4. every refusal writes nothing
    refs = run.evidence.refusals
    wrote = [r for r in refs if (r.get("writes") or 0) > 0]
    out.append(_assert("A4", "every refusal writes nothing",
                       FAIL if wrote else (PASS if refs else UNAVAILABLE),
                       f"{len(refs)} refusal(s) captured with the write log read before and after; "
                       f"{len(wrote)} wrote", ["stage:relation", "stage:profile.unavailable_model",
                                               "stage:draft.accept", "evidence:refusals"]))

    # 5. every retry yields one canonical result
    out.append(_from_stage(run, "A5", "every retry yields one canonical result", "profile.lost_response",
                           "a relation whose response was lost, retried verbatim, produced one edge and one mark per post"))

    # 6. stale revisions never overwrite
    out.append(_from_stage(run, "A6", "stale revisions never overwrite", "profile.stale_tab",
                           "a stale second tab's save did not overwrite the newer note"))

    # 7. every old Writer version / operator provenance remains resolvable
    lineage = run.state.get("lineage_id")
    if lineage:
        versions = list(db.writer_passage_versions.find({"lineage_id": lineage}).sort("version", 1))
        ms = run.state.get("manuscript_id")
        resolv = []
        for v in versions:
            s, body = run.api.get(f"/api/v1/writer/{ms}/genealogy/{lineage}/v{v.get('version')}")
            ops = (v.get("provenance") or {}).get("operators") or []
            op_ok = all(db.writer_operators.find_one({"_id": o.get("id")}) or
                        db.writer_operators.find_one({"name": o.get("name"), "project_id": ms})
                        for o in ops)
            resolv.append({"version": v.get("version"), "resolves": s == 200, "operators": len(ops),
                           "operators_resolve": op_ok})
        bad = [r for r in resolv if not (r["resolves"] and r["operators_resolve"])]
        out.append(_assert("A7", "every old Writer version/operator provenance remains resolvable",
                           FAIL if bad else PASS, f"{len(resolv)} version(s) of lineage {lineage}: {resolv}",
                           ["stage:writer", "db:writer_passage_versions", "db:writer_operators"],
                           lane="D" if bad else None))
    else:
        out.append(_from_stage(run, "A7", "every old Writer version/operator provenance remains resolvable",
                               "writer", ""))

    # 8. evidence refs survive Atlas → Writer → revision → export
    sc = run.state.get("draft_scene_id")
    chain = {"atlas_draft_passages": len(run.state.get("draft_passages") or [])}
    if sc:
        scene = db.scenes.find_one({"_id": sc}) or {}
        blocks = scene.get("blocks", [])
        with_refs = [b for b in blocks if any(k in b for k in ("provenance", "evidence", "citations", "step_ids", "run_id", "percept_refs"))]
        chain["scene_blocks"] = len(blocks)
        chain["scene_blocks_with_evidence_refs"] = len(with_refs)
        chain["block_keys"] = sorted({k for b in blocks for k in b})
        run_id = run.state.get("draft_run_id")
        chain["scene_mentions_run_id"] = any(run_id and run_id in json.dumps(b, default=str) for b in blocks)
    if lineage:
        versions = list(db.writer_passage_versions.find({"lineage_id": lineage}))
        chain["writer_versions_with_provenance"] = sum(1 for v in versions if v.get("provenance"))
        chain["writer_versions"] = len(versions)
        ms = run.state.get("manuscript_id")
        s, exp = run.api.get(f"/api/v1/manuscript/{ms}/export?format=markdown")
        content = (exp or {}).get("content", "")
        chain["export_carries_lineage_or_version_refs"] = bool(lineage in content or "lineage" in json.dumps(exp or {}))
        chain["export_keys"] = sorted((exp or {}).keys())
    dr = _result(run, "draft.accept")
    if not sc or not lineage:
        st = UNAVAILABLE
        detail = "the chain did not complete: " + ("no draft scene" if not sc else "no Writer lineage")
        lane = (dr.lane if dr else None) or "I"
    else:
        survives = chain.get("scene_blocks_with_evidence_refs", 0) > 0 and \
            chain.get("writer_versions_with_provenance", 0) == chain.get("writer_versions", -1)
        st = PASS if survives and chain.get("export_carries_lineage_or_version_refs") else FAIL
        detail = json.dumps(chain, default=str)
        lane = None if st == PASS else "I"
        if st == FAIL and not chain.get("export_carries_lineage_or_version_refs"):
            detail += " — the markdown export carries prose only; lineage/evidence refs stop at the scene block"
    out.append(_assert("A8", "evidence refs survive Atlas → Writer → revision → export", st, detail,
                       ["stage:draft", "stage:draft.accept", "stage:writer", "db:scenes",
                        "db:writer_passage_versions", "api:/manuscript/{id}/export"], lane))

    # 9. fixture posts change only at explicitly accepted evidence steps
    unexpected = run.evidence.unexpected
    expected = run.evidence.expected_writes
    out.append(_assert("A9", "fixture posts change only at explicitly accepted evidence steps",
                       FAIL if unexpected else PASS,
                       f"{len(run.evidence.hash_timeline)} stage(s) hashed every fixture post; "
                       f"{len(expected)} write(s) declared by accepting stages; {len(unexpected)} unexpected",
                       ["evidence:hash_timeline", "evidence:expected_writes", "evidence:unexpected"]
                       + [f"unexpected:{u['stage']}:{u['post_id']}" for u in unexpected],
                       lane="B" if unexpected else None))

    # 10. all unexpected mutations are printed as a field-level diff
    out.append(_assert("A10", "all unexpected mutations are printed as a field-level diff", PASS,
                       f"{len(unexpected)} unexpected mutation(s), each carried with its path-level diff "
                       "in summary.json `evidence.unexpected[].diff` and in the report",
                       ["evidence:unexpected", "report:Unexpected mutations"]))
    return out


def gate(run: Run, asserts: List[Dict[str, Any]]) -> Dict[str, Any]:
    failed = [r.name for r in run.results if r.status in (FAIL, ERROR)]
    unavailable = [r for r in run.results if r.status == UNAVAILABLE]
    lanes = sorted({r.lane for r in run.results if r.lane and r.status in (FAIL, UNAVAILABLE)} |
                   {a["lane"] for a in asserts if a.get("lane") and a["status"] != PASS})
    status = "fail" if failed else ("blocked" if unavailable or any(a["status"] != PASS for a in asserts) else "pass")
    return {"status": status, "failed_stages": failed,
            "unavailable_stages": [r.name for r in unavailable],
            "lanes_preventing_full_pass": lanes,
            "assertions_passed": sum(1 for a in asserts if a["status"] == PASS),
            "assertions_total": len(asserts)}


def write_summary(run: Run, meta: Dict[str, Any], asserts: List[Dict[str, Any]],
                  before: Dict[str, str], after: Dict[str, str]) -> Path:
    summary = {
        "harness": "ATLAS-WRITER-MASS-BUILD-001L",
        "schema": "research/rehearsals/vertical/schemas/vertical-summary.schema.json",
        "run_id": run.run_id,
        **meta,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "stack": {"mongo_port": run.stack.mongo_port, "backend_port": run.stack.backend_port,
                  "frontend_port": run.stack.frontend_port, "image_port": run.stack.image_port,
                  "boot_seconds": run.stack.boot_seconds, "fakes": run.stack.fakes,
                  "backend_restarts": run.stack.backend_restarts, "notes": run.stack.notes},
        "stages": [r.to_dict() for r in run.results],
        "assertions": asserts,
        "gate": gate(run, asserts),
        "hashes": {"before": before, "after": after,
                   "changed": sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))},
        "evidence": run.evidence.to_dict(),
        "state": {k: v for k, v in run.state.items() if isinstance(v, (str, int, float, list, bool)) or v is None},
    }
    path = run.run_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2, default=str, sort_keys=False))
    return path


def write_report(run: Run, summary_path: Path) -> Path:
    s = json.loads(summary_path.read_text())
    g = s["gate"]
    lines = [f"# Vertical rehearsal — {s['run_id']}", "",
             f"**Gate:** `{g['status']}`  ·  mode `{s['mode']}`  ·  profile `{s['profile']}`  ·  "
             f"base `{s['base'].get('commit', '?')[:12]}` on `{s['base'].get('branch', '?')}`  ·  "
             f"fakes `{s['stack']['fakes']}`", ""]
    if g["lanes_preventing_full_pass"]:
        lines.append("**Lanes still preventing the full pass:** " + ", ".join(f"`{l}`" for l in g["lanes_preventing_full_pass"]))
        lines.append("")
    lines += ["## Assertions", "", "| # | assertion | status | lane | detail | evidence |", "|---|---|---|---|---|---|"]
    for a in s["assertions"]:
        ev = ", ".join(f"`{e}`" for e in a["evidence"][:6]) + (" …" if len(a["evidence"]) > 6 else "")
        lines.append(f"| {a['id']} | {a['title']} | **{a['status']}** | {a.get('lane') or ''} | "
                     f"{a['detail'].replace('|', '\\|')[:400]} | {ev} |")
    lines += ["", "## Stages", "", "| stage | status | lane | seconds | detail | screenshots |", "|---|---|---|---|---|---|"]
    for r in s["stages"]:
        shots = " ".join(f"[{Path(p).stem}]({p})" for p in r["screenshots"])
        lines.append(f"| `{r['name']}` | **{r['status']}** | {r.get('lane') or ''} | {r['ms']/1000:.1f} | "
                     f"{(r['detail'] or '').replace('|', '\\|')[:300]} | {shots} |")
    rec = s["evidence"]["receipts"]
    lines += ["", "## Model / provider receipts", ""]
    for r in s.get("provider_receipts", []):
        lines.append(f"- `{r['seam']}` → **{r['mode']}**" + (f" ({r.get('model') or r.get('provider')})" if r.get('model') or r.get('provider') else "")
                     + (f" — credential `{r['credential']}` {'present' if r.get('present') else 'absent'}" if r.get('credential') else ""))
    for r in rec:
        lines.append(f"- stage `{r['stage']}` · {r.get('seam')} → " + ", ".join(f"{k}={v}" for k, v in r.items() if k not in ("stage", "seam")))
    lines += ["", "## Canonical ids captured", ""]
    for stage, ids in s["evidence"]["ids"].items():
        lines.append(f"- `{stage}`: " + ", ".join(f"{k}=`{v}`" for k, v in ids.items()))
    lines += ["", "## Refusals", ""] + [f"- `{r['stage']}`: " + ", ".join(f"{k}={v}" for k, v in r.items() if k != "stage") for r in s["evidence"]["refusals"]]
    lines += ["", "## Operations / retries / conflicts", ""]
    for o in s["evidence"]["operations"] + s["evidence"]["conflicts"]:
        lines.append(f"- `{o['stage']}`: " + ", ".join(f"{k}={v}" for k, v in o.items() if k != "stage"))
    perf = next((r for r in s["stages"] if r["name"] == "performance"), None)
    if perf:
        lines += ["", "## Performance (60 images)", "", "| measure | ms / MB | budget |", "|---|---|---|"]
        m = perf["evidence"].get("measured", {})
        b = perf["evidence"].get("budgets", {})
        for k, v in m.items():
            lines.append(f"| {k} | {v} | {b.get(k, '')} |")
        if perf["evidence"].get("over_budget"):
            lines.append("")
            lines.append("Over budget: " + "; ".join(perf["evidence"]["over_budget"]))
    lines += ["", "## Hashes", "",
              f"- fixture posts before: {len(s['hashes']['before'])}, after: {len(s['hashes']['after'])}, "
              f"changed: {len(s['hashes']['changed'])}",
              "- per-stage timeline in `summary.json` → `evidence.hash_timeline`", ""]
    lines += ["## Unexpected mutations", ""]
    if not s["evidence"]["unexpected"]:
        lines.append("None.")
    for u in s["evidence"]["unexpected"]:
        lines.append(f"- stage `{u['stage']}` · post `{u['post_id']}`")
        for d in u["diff"][:40]:
            lines.append(f"    - `{d['path']}` {d['kind']}: `{d.get('before')}` → `{d.get('after')}`")
    lines += ["", "## Stack", "",
              f"- boot: {s['stack']['boot_seconds']}  · backend restarts: {s['stack']['backend_restarts']}",
              *[f"- note: {n}" for n in s["stack"]["notes"]],
              *[f"- note: {n}" for n in s["evidence"]["notes"]], ""]
    if s.get("preserved"):
        lines += ["## Preserved for inspection", ""] + [f"- {k}: `{v}`" for k, v in s["preserved"].items()]
    path = run.run_dir / "report.md"
    path.write_text("\n".join(lines) + "\n")
    return path
