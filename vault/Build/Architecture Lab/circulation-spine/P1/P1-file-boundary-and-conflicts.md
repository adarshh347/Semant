# P1 — File Boundary & Conflicts

## Exact diff (vs `main@99e92b3`)

```
 backend/database.py                                         |   9 +   (1 collection handle)
 backend/main.py                                             |   3 +   (1 startup index hook)
 backend/routers/posts.py                                    | ~130 +  (instrument route + 2 GET endpoints)
 backend/services/vision_orchestrator/vision_run_contracts.py| new     (import-safe contract)
 backend/services/vision_run_service.py                      | new     (persistence + recorder)
 backend/tests/test_circulation_spine_p1.py                  | new     (28 tests)
 architecture-lab/circulation-spine/P1/*.md                  | new     (these reports)
```

Scope guard (`git status` grep for `frontend|scheduler|planner|atlas|codex|rehearsal|
PostDetailPage|DifferentialWorkspace|RegionSurface`): **clean — nothing forbidden touched.**
`contracts.py` is **imported only, never modified** (confirmed by Fable review; not in
`git diff --name-only`).

## Reused, not modified

- `backend/services/vision_orchestrator/contracts.py` — `JobStatus` imported verbatim as
  the status vocabulary; `Provenance.as_dict()` shape referenced for event payloads. No
  edit, no Scheduler/planner import. `adopted`

## Explicitly NOT touched (out-of-scope list honoured)

Passage Rail / any frontend · WebSocket/SSE · Scheduler migration · new adapters · model
concurrency · cancellation · Atlas · Codex · cross-image percept circulation · Ground/Percept
migration · server-side `pct_` guard · Mention redesign · rehearsal runner/schemas · corpus
expansion · CUDA config · model-provider swap · region geometry behaviour ·
`PostDetailPage.jsx` · `DifferentialWorkspace.jsx` · `RegionSurface.jsx`.

## Branch / worktree safety

- Implemented in a **dedicated worktree** `…/semant-circulation-p1` on a fresh branch
  `feat/circulation-spine-001-p1` cut from `main@99e92b3` (verified current production
  baseline, not the audit's assumed commit). `implemented`
- **Did not** implement on `feat/rehearsal-research-r1` (the session's checked-out branch),
  nor touch the `semant-home-archive` / `semant-oss` worktrees.
- **Collision check:** on `main`'s lineage no other active branch is ahead on
  `backend/routers/posts.py` (all sit at `24d0a52`). The archive/oss branches modify
  `posts.py` on a *separate* lineage (`9e4b5b6`) — not combined here. No silent merge.

## Drift check vs the P0/P0.5 audit

The audit bundles were produced against `feat/rehearsal-research-r1 @ 97b7a51`; `posts.py`
there and on `main@99e92b3` are the **same blob** (`24d0a52`). Every audited seam
(`detect_regions` at ~:630, the coarse `try/except`→vision fallback, the non-fatal fine
`try/except`, the C5 merge, the single `region_annotations` `$set`) is present and unchanged.
**Drift: LOW** — no drift report required; the audited seams remain valid.

## Repo-state conflicts encountered & resolved

1. **Canonical audit bundles absent from the repo** → user supplied the three zips in
   `audit-bundles/`; read and reconciled against live code.
2. **`architecture-lab/` retirement** noted in the r1-branch CLAUDE.md does **not** apply to
   a `main`-based branch: `main`'s tree still has top-level `architecture-lab/` and no
   `vault/Build/Architecture Lab/`. So the direction's literal report path
   `architecture-lab/circulation-spine/P1/` is correct here and is used as-is.

## Untracked-file safety (parallel repo tidy)

The only tidy applied was renaming the untracked, unreferenced folder `"audit bundles "`
(trailing space) → `audit-bundles/` in the *main* worktree — zero git impact, no code
reference (grep-verified). All `vault/` and `new-planning/` content was left strictly
untouched. `.gitignore` and `scripts/_run_backend.py` decisions were deferred to the user.
