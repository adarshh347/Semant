#!/usr/bin/env python3
"""
INTELLIGENCE-001B — run a case, verify the corpus, propose a control set.

RESEARCH-ONLY, AND READ-ONLY AGAINST THE ARCHIVE. Nothing here writes to `posts`, and nothing here
edits the inquiry pipeline: running a case shells out to `scripts/inquiry_rehearse.py`, which
already drives the whole chain and already resolves post ids through `corpus.resolve`. Rebuilding
that here would have produced a second driver to keep in step with the first.

    python scripts/inquiry_intelligence_rehearsal.py --verify-corpus
    python scripts/inquiry_intelligence_rehearsal.py --propose-architecture --limit 12
    python scripts/inquiry_intelligence_rehearsal.py --run --case II-02-sparse-inquiry --live

## Why the architecture control set is proposed by upload time

The archive carries no searchable metadata. Every one of its posts has an empty `general_tags` and
an empty `text_blocks`, so there is no query that means "architecture" — a topic search would be
returning the search string dressed as a result.

What the archive does carry is an ObjectId per post, and an ObjectId begins with a timestamp. The
three canonical sculpture posts sit inside one contiguous block of them, which is what a single
upload session looks like. So `--propose-architecture` clusters by upload gap and prints a contact
sheet of image urls per cluster.

That is a claim about WHEN things were added and about nothing else. It cannot see a building. The
candidates it writes are marked `awaiting_human_confirmation` and the manifest keeps the
architecture corpus empty until a person has looked at the pictures and said which cluster is
which — because a control set assembled from upload timestamps alone would make every cross-domain
result a claim about the scrape.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REHEARSALS = ROOT / "research" / "rehearsals" / "inquiry-intelligence"
CASES_DIR = REHEARSALS / "cases"
RUNS_DIR = REHEARSALS / "run-archive"
CONTROL_DIR = REHEARSALS / "architecture-control"


def _load_manifest() -> Dict[str, Any]:
    return json.loads((CASES_DIR / "manifest.json").read_text())


def _load_case(case_id: str) -> Dict[str, Any]:
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        raise SystemExit(f"no such case: {case_id}")
    return json.loads(path.read_text())


# ── the corpus, read and never written ──────────────────────────────────────

def verify_corpus(corpus_name: str = "sculpture") -> int:
    """Resolve the canonical posts read-only and compare against the recorded fingerprints.

    A moved post is reported and the exit code is non-zero, because every prior evaluation filed
    under this manifest is then about different pixels. It is not repaired here: silently updating
    the manifest to match what the archive now holds would erase the only evidence that anything
    changed.
    """
    from dotenv import load_dotenv
    load_dotenv()
    from backend.services.inquiry_session import corpus as corpus_svc

    manifest = _load_manifest()
    declared = manifest["corpora"][corpus_name]
    want: Dict[str, str] = declared["fingerprints"]
    ids: List[str] = declared["post_ids"]

    refs, _docs = asyncio.run(corpus_svc.resolve(ids))
    found = {r.post_id: (r.fingerprint, r.readable) for r in refs}

    moved, missing, ok = [], [], []
    for pid in ids:
        got = found.get(pid)
        if got is None or not got[1]:
            missing.append(pid)
        elif got[0] != want.get(pid):
            moved.append((pid, want.get(pid), got[0]))
        else:
            ok.append(pid)

    print(f"corpus `{corpus_name}`: {len(ok)} unchanged, {len(moved)} moved, {len(missing)} "
          f"unreadable")
    for pid in ok:
        print(f"  ok      {pid}  {want[pid][:16]}…")
    for pid, exp, got in moved:
        print(f"  MOVED   {pid}\n            manifest {exp}\n            archive  {got}")
    for pid in missing:
        print(f"  MISSING {pid} — did not resolve, or resolved unreadable")
    if moved or missing:
        print("\nThe manifest is NOT updated automatically. Every evaluation filed against it is "
              "about the fingerprints above; rewriting them here would erase the evidence that "
              "anything moved.")
        return 1
    return 0


# ── an architecture control set, proposed rather than declared ──────────────

def _oid_time(oid: str) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(oid[:8], 16), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def propose_architecture(limit: int = 12, gap_minutes: int = 30) -> int:
    """Cluster the archive by upload gap and write a contact sheet for a person to look at.

    NOT A TOPIC SEARCH, and the report says so on its first line. The clusters are upload sessions.
    Which of them is architecture is a question for eyes.
    """
    from dotenv import load_dotenv
    load_dotenv()
    from backend.database import post_collection

    async def read() -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        async for d in post_collection.find({}, {"_id": 1, "photo_url": 1}):
            out.append((str(d["_id"]), str(d.get("photo_url") or "")))
        return out

    rows = sorted(asyncio.run(read()))
    manifest = _load_manifest()
    known = set(manifest["corpora"]["sculpture"]["post_ids"])

    clusters: List[List[Tuple[str, str]]] = []
    prev: Optional[datetime] = None
    for pid, url in rows:
        t = _oid_time(pid)
        if prev is None or t is None or (t - prev).total_seconds() > gap_minutes * 60:
            clusters.append([])
        clusters[-1].append((pid, url))
        prev = t or prev

    clusters = [c for c in clusters if len(c) >= 3]
    clusters.sort(key=len, reverse=True)

    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "awaiting_human_confirmation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "ObjectId timestamp clustering with a "
                  f"{gap_minutes}-minute gap. This groups posts that were UPLOADED together and "
                  "knows nothing about what is in them.",
        "why_not_a_search": "every one of the archive's posts has an empty `general_tags` and an "
                            "empty `text_blocks`, so no query means `architecture`. A topic search "
                            "here would return the search string dressed as a result.",
        "clusters": [
            {
                "cluster_index": i,
                "size": len(c),
                "first_upload": (_oid_time(c[0][0]) or datetime.now(timezone.utc)).isoformat(),
                "contains_canonical_sculpture_posts": sorted(known & {p for p, _ in c}),
                "post_ids": [p for p, _ in c][:limit],
            }
            for i, c in enumerate(clusters[:limit])
        ],
    }
    (CONTROL_DIR / "candidates.json").write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        "# Architecture control set — CANDIDATES, NOT CANONICAL",
        "",
        "**Nothing in this file is a control set yet.** These are upload clusters. The method knows",
        "when posts were added and nothing about what they show, because the archive carries no",
        "tags and no text on any of its posts — there is no query that means *architecture*.",
        "",
        "To make a cluster canonical: look at the images, then add its ids to",
        "`cases/manifest.json` under `corpora.architecture.post_ids` and set its status to",
        "`canonical`. Until then every cross-domain result would be a claim about the scrape.",
        "",
    ]
    for c in payload["clusters"]:
        lines.append(f"## Cluster {c['cluster_index']} — {c['size']} posts, "
                     f"first uploaded {c['first_upload'][:19]}Z")
        if c["contains_canonical_sculpture_posts"]:
            lines.append("")
            lines.append(f"> Contains {len(c['contains_canonical_sculpture_posts'])} of the "
                         f"canonical **sculpture** posts — so this cluster is the sculpture "
                         f"session and is not a control for it.")
        lines.append("")
        urls = {p: u for p, u in rows}
        for pid in c["post_ids"]:
            lines.append(f"- `{pid}` — {urls.get(pid) or '(no url)'}")
        lines.append("")
    (CONTROL_DIR / "contact-sheet.md").write_text("\n".join(lines))

    print(f"{len(clusters)} upload cluster(s) of 3+ posts, from {len(rows)} posts")
    print(f"wrote {CONTROL_DIR / 'candidates.json'}")
    print(f"wrote {CONTROL_DIR / 'contact-sheet.md'}")
    print("\nNOT CANONICAL. These are upload sessions, not subjects. A person has to look.")
    return 0


# ── running a case ──────────────────────────────────────────────────────────

def run_case(case_id: str, *, live: bool, mode: str, scope: str) -> int:
    """Drive one case through `inquiry_rehearse.py`, then evaluate and archive the result."""
    from scripts.inquiry_intelligence_evaluate import evaluate, archive  # noqa: E402

    case = _load_case(case_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = RUNS_DIR / f"{stamp}-{case_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    session_path = out_dir / "session.wire.json"

    cmd = [sys.executable, str(ROOT / "scripts" / "inquiry_rehearse.py"),
           "--mode", mode, "--scope", scope,
           "--prompt", case["prompt"], "--json-out", str(session_path)]
    for pid in case["post_ids"]:
        cmd += ["--post", pid]
    if live:
        cmd.append("--live")

    print(f"running {case_id} ({'live' if live else 'offline'}) …")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    (out_dir / "driver.stdout.txt").write_text(proc.stdout)
    (out_dir / "driver.stderr.txt").write_text(proc.stderr)
    if not session_path.exists():
        print(f"the driver produced no session (exit {proc.returncode}). "
              f"stderr is in {out_dir / 'driver.stderr.txt'}")
        return proc.returncode or 1

    raw = json.loads(session_path.read_text())
    ev = evaluate(raw, case)
    archive(ev, raw, case, out_dir)
    dg = ev["diagnosis"]
    print(f"workflow {dg['workflow_outcome']} · semantic {dg['semantic_outcome']}"
          + ("  <- DISAGREE" if dg["outcomes_disagree"] else ""))
    print(f"archived -> {out_dir}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify-corpus", action="store_true")
    ap.add_argument("--corpus", default="sculpture")
    ap.add_argument("--propose-architecture", action="store_true")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--gap-minutes", type=int, default=30)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--case")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--mode", default="auto", choices=["auto", "consult", "step"])
    ap.add_argument("--scope", default="full", choices=["full", "vertical_slice"])
    args = ap.parse_args(argv)

    if args.verify_corpus:
        return verify_corpus(args.corpus)
    if args.propose_architecture:
        return propose_architecture(args.limit, args.gap_minutes)
    if args.run:
        if not args.case:
            ap.error("--run needs --case")
        return run_case(args.case, live=args.live, mode=args.mode, scope=args.scope)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
