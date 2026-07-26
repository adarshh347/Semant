#!/usr/bin/env python
"""
WEIGHTS-001 — provision every model this repo needs, from `weights.manifest.json`.

Git holds the manifest; the weights live in caches. This script is the bridge, and it is the
answer to "how do I set up a fresh machine" (the Mac, a serverless image, a new contributor).

Design rules:

  · IDEMPOTENT. Re-running fetches nothing. An HF snapshot at a pinned revision is a cache hit;
    a url entry whose sha256 already matches is skipped without a byte of network. This matters
    because the honest way to check "am I provisioned?" is to just run it again.

  · PINNED. Every HF entry names a commit sha, never a branch. `main` is a moving target, and a
    silently-updated backbone means yesterday's marks were produced by a model you can no longer
    identify — which would quietly falsify every provenance receipt we have written.

  · VERIFIED. Direct downloads are checked against sha256 before being accepted. A truncated
    weight file that loads is worse than one that fails.

  · NON-INTERACTIVE. `altered_midas` calls torch.hub.load() without trust_repo, so on a fresh box
    Intrinsic's first load BLOCKS on a y/N prompt — invisible in a container, fatal in CI. We
    pre-seed torch's trusted_list, which is exactly what answering 'y' once does. That is a real
    consent decision, so --trust-hub-repos is OPT-IN and the script says what it will trust.

Usage:
    python scripts/fetch_weights.py                  # provision everything (except trust-gated)
    python scripts/fetch_weights.py --check          # report only, download nothing
    python scripts/fetch_weights.py --only dinov2_vits14 sam21_hiera_tiny
    python scripts/fetch_weights.py --trust-hub-repos  # also pre-seed torch's trusted_list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "weights.manifest.json"

OK, MISS, FAIL, SKIP = "ok", "missing", "failed", "skipped"
_MARK = {OK: "✓", MISS: "·", FAIL: "✗", SKIP: "–"}


def log(status: str, name: str, detail: str = "") -> None:
    print(f"  {_MARK.get(status, '?')} {name:32s} {detail}", flush=True)


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def torch_home() -> Path:
    return Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch"))


# ── kinds ────────────────────────────────────────────────────────────────────

def provision_hf(entry: dict, *, check_only: bool) -> str:
    """snapshot_download at the PINNED revision. A cache hit costs nothing."""
    repo_id, revision = entry["id"], entry.get("revision")
    if not revision or revision.startswith("unpinned"):
        log(FAIL, entry["name"], "no pinned revision in the manifest")
        return FAIL
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        log(FAIL, entry["name"], "huggingface_hub not installed")
        return FAIL

    # `ignore_patterns` scopes the snapshot to the files this codebase actually loads. It is not
    # a size optimisation: a repo shipping variants we never use (ONNX, TF, fp16 forks) will also
    # never satisfy the cache check, so every run would re-attempt a multi-GB download.
    kw = {}
    if entry.get("ignore_patterns"):
        kw["ignore_patterns"] = entry["ignore_patterns"]
    if entry.get("allow_patterns"):
        kw["allow_patterns"] = entry["allow_patterns"]

    # Cache first, ALWAYS. `snapshot_download` without local_files_only contacts the HF API even
    # when every file is already present, which on a warm box turns a no-op re-run into minutes of
    # network round-trips. Since the revision is a pinned commit sha, a local hit is by definition
    # the right bytes — there is nothing a network call could tell us that we don't already know.
    try:
        snapshot_download(repo_id=repo_id, revision=revision, local_files_only=True, **kw)
        log(OK, entry["name"], f"cached @ {revision[:12]}")
        return OK
    except Exception:
        pass                                  # not cached (or incomplete) → fall through

    if check_only:
        log(MISS, entry["name"], f"would fetch @ {revision[:12]} ({entry.get('size_human','?')})")
        return MISS
    try:
        snapshot_download(repo_id=repo_id, revision=revision, **kw)
        log(OK, entry["name"], f"fetched @ {revision[:12]}")
        return OK
    except Exception as e:
        log(FAIL, entry["name"], f"{type(e).__name__}: {e}")
        return FAIL


def provision_url(entry: dict, *, check_only: bool) -> str:
    """Download to `dest` and verify sha256. An already-correct file is left untouched."""
    dest = REPO / entry["dest"]
    want = entry.get("sha256")

    if dest.exists():
        if not want:
            log(OK, entry["name"], f"present (no sha256 to verify) {dest}")
            return OK
        got = sha256_of(dest)
        if got == want:
            log(OK, entry["name"], f"verified {dest}")
            return OK
        log(FAIL, entry["name"], f"SHA MISMATCH at {dest}\n      expected {want}\n      got      {got}")
        return FAIL

    if check_only:
        log(MISS, entry["name"], f"would fetch {entry.get('size_human','?')} → {entry['dest']}")
        return MISS

    try:
        import httpx
    except ImportError:
        log(FAIL, entry["name"], "httpx not installed")
        return FAIL

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    try:
        with httpx.stream("GET", entry["url"], follow_redirects=True, timeout=120.0) as r:
            r.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
        got = sha256_of(tmp)
        if want and got != want:
            tmp.unlink(missing_ok=True)       # never leave a wrong file where a right one goes
            log(FAIL, entry["name"], f"sha256 mismatch after download (got {got[:16]}…)")
            return FAIL
        tmp.replace(dest)                     # atomic: a partial file is never seen as complete
        log(OK, entry["name"], f"downloaded → {entry['dest']}")
        return OK
    except Exception as e:
        tmp.unlink(missing_ok=True)
        log(FAIL, entry["name"], f"{type(e).__name__}: {e}")
        return FAIL


def already_trusted(repos: list[str]) -> list[str]:
    """Which of `repos` torch already trusts — so we never report a need that is already met."""
    tl = torch_home() / "hub" / "trusted_list"
    if not tl.exists():
        return []
    have = set(tl.read_text().split())
    return [r for r in repos if r in have]


def seed_trusted_list(repos: list[str]) -> None:
    """Record repos in torch's trusted_list — exactly what answering 'y' once does.

    Needed because `altered_midas` calls torch.hub.load() without trust_repo: on a fresh,
    non-interactive box Intrinsic's first load raises EOFError on the y/N prompt."""
    tl = torch_home() / "hub" / "trusted_list"
    tl.parent.mkdir(parents=True, exist_ok=True)
    existing = set(tl.read_text().split()) if tl.exists() else set()
    added = [r for r in repos if r not in existing]
    if not added:
        log(OK, "torch trusted_list", "already trusts " + ", ".join(repos))
        return
    with tl.open("a") as fh:
        for r in added:
            fh.write(r + "\n")
    log(OK, "torch trusted_list", "trusted " + ", ".join(added))


def provision_pip_git(entry: dict) -> str:
    """Installed by requirements-ml.txt — the fetcher reports, it never installs into your venv."""
    import importlib.util
    probe = entry.get("import_probe", "intrinsic.pipeline")
    present = importlib.util.find_spec(probe.split(".")[0]) is not None
    if present:
        try:
            __import__(probe)
        except Exception:
            present = False
    if present:
        log(OK, entry["name"], "package importable (checkpoints fetch lazily on first load)")
        return OK
    log(MISS, entry["name"], f"pip install -r requirements-ml.txt  ({entry['id']})")
    return MISS


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only; download nothing")
    ap.add_argument("--only", nargs="*", metavar="NAME", help="limit to these manifest names")
    ap.add_argument("--trust-hub-repos", action="store_true",
                    help="pre-seed torch's trusted_list for hub repos flagged trust_required "
                         "(executes third-party code at load time — opt in deliberately)")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    models = manifest["models"]
    if args.only:
        models = [m for m in models if m["name"] in set(args.only)]
        if not models:
            print(f"no manifest entry matched {args.only}", file=sys.stderr)
            return 2

    print(f"\nweights.manifest.json v{manifest['version']} — {len(models)} model(s)"
          f"{'  [CHECK ONLY]' if args.check else ''}\n")

    results, trust_wanted = {}, []
    for m in models:
        kind = m["kind"]
        if kind == "hf":
            results[m["name"]] = provision_hf(m, check_only=args.check)
        elif kind == "url":
            results[m["name"]] = provision_url(m, check_only=args.check)
        elif kind == "pip-git":
            results[m["name"]] = provision_pip_git(m)
            for repo in m.get("torch_hub_repos", []):
                if repo.get("trust_required"):
                    trust_wanted.append(repo["repo"].replace("/", "_"))
        else:
            log(SKIP, m["name"], f"unknown kind '{kind}'")
            results[m["name"]] = SKIP

    if trust_wanted:
        print()
        missing_trust = [r for r in trust_wanted if r not in already_trusted(trust_wanted)]
        if not missing_trust:
            log(OK, "torch trusted_list", "already trusts " + ", ".join(trust_wanted))
        elif args.trust_hub_repos and not args.check:
            seed_trusted_list(missing_trust)
        else:
            log(MISS, "torch trusted_list",
                "needs " + ", ".join(missing_trust) + "  → re-run with --trust-hub-repos")
            print("      (without it, Intrinsic's first load blocks on an interactive y/N prompt)")

    print("\n  " + "  ".join(f"{_MARK[s]}{n}" for s, n in
                             ((s, sum(v == s for v in results.values()))
                              for s in (OK, MISS, FAIL, SKIP)) if n))
    if any(v == FAIL for v in results.values()):
        print("\n  Some entries FAILED — see above.\n")
        return 1
    if args.check and any(v == MISS for v in results.values()):
        print("\n  Not fully provisioned. Run without --check to fetch.\n")
        return 1
    print("\n  Provisioned.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
