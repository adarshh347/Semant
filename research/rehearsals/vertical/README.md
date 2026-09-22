# Vertical rehearsal — ATLAS-WRITER-MASS-BUILD-001L

One command drives a real Chromium against the real FastAPI process and a disposable mongod through
the whole Atlas → Writer circuit, and leaves a machine-readable audit behind. The unit suites prove
isolated contracts; this proves that the seams agree.

```text
python scripts/vertical_rehearsal.py                 # offline: deterministic fakes (core CI path)
python scripts/vertical_rehearsal.py --mode live     # whatever declared providers are present
python scripts/vertical_rehearsal.py --both          # the gate: offline, then live
python scripts/vertical_rehearsal.py --list-stages
python scripts/vertical_rehearsal.py --stages walk.save_open,relation --headed --slow 200
```

Needs: `mongod` on PATH (or `SEMANT_VERTICAL_MONGO_URI` pointing at a throwaway server), the venv
with `playwright` (`pip install playwright && playwright install chromium`), and `frontend/node_modules`.

## What one run leaves behind

`runs/<run-id>/` (default `research/rehearsals/vertical/runs/<stamp>-<mode>/`):

| file | what |
|---|---|
| `summary.json` | the audit — stages, the ten assertions with their evidence, ids, receipts, refusals, operations, hash timeline, unexpected mutations with field-level diffs. Schema: `schemas/vertical-summary.schema.json` |
| `report.md` | the same, for a person |
| `screenshots/*.png` | one per visible step, including dark mode, reduced motion and the React Flow edges |
| `hashes-before.json`, `hashes-after.json` | canonical sha256 of every fixture post |
| `corpus.json` | the manifest, the PNG digests, the post ids |
| `logs/` | mongod, backend, vite, harness errors |
| `images/`, `dist/` | the rendered corpus and the production build (not committed) |

Only `summary.json`, `report.md`, `corpus.json` and the hashes are committed for a run worth
keeping; screenshots, builds and logs are ignored (`.gitignore`).

## The stack

- **mongod of its own**, ephemeral port, temp dbpath, deleted on a passing run, preserved (with the
  reopen command printed) on a failing one. `backend/database.py` hard-codes the database name and
  forces TLS on non-SRV URIs unless `PORT` is set, so the backend is started with `PORT` in its env —
  recorded as a stack note, not fixed here.
- **the real `backend.main:app`**, served through `scripts/vertical_rehearsal_support/app_entry.py`,
  which binds deterministic fakes at the model / GPU seams (`SEMANT_VERTICAL_FAKES=all|ml_only|none`),
  mounts loopback-only control routes (`/__rehearsal/receipts`, `/writes`, `/fault`) and wraps the
  motor collection writes so a fault can be injected on the Nth write to a named collection.
- **the real frontend**, a production Vite build served by `vite preview` (`--frontend dev` for the
  dev server; note React StrictMode double-runs effects there).
- **Playwright Chromium**, one context per stage, `prefers-color-scheme` and `prefers-reduced-motion`
  emulated where the check needs them.

## Stages

`walk.save_open` · `atlas.canvas` · `atlas.light_table` · `differential` · `relation` · `plan` · `draft`
· `draft.accept` · `api.target_manuscript` · `writer` · `movement` · `profile.lost_response` ·
`profile.restart_mid` · `profile.stale_tab` · `profile.unavailable_model` · `profile.unreadable_image`
· `profile.injected_writes` · `a11y` · `performance`

A stage is `pass`, `fail` (a domain defect, filed against the lane it names), `unavailable` (the seam
is not on this base; the lane that brings it is named), `skipped`, or `error` (ours). After every
stage every fixture post is re-hashed; a change no accepting stage declared — or a change that
removes or rewrites committed evidence — is an unexpected mutation, printed as a field-level diff.

## The corpus

Synthetic, rendered at run time from `corpus.py` with Pillow, so the repository holds no binaries
and every run sees the same bytes: eight marked images, one unmarked (so a refusal can sit beside a
relation), one whose image URL is dead, and sixty for the performance profile. Marks are the lines
the renderer drew, so the audit knows them by construction. Never a production post.

`--profile real-photo` adds the author's own licensed images from `$SEMANT_VERTICAL_REAL_PHOTOS`
(a directory with `marks.json`: `[{file, title, marks:[...]}]`). Absent → `unavailable`, said so.

## Budgets

`budgets.json` declares the 60-image performance budgets. A breach fails the `performance` stage and
never weakens a correctness stage.
