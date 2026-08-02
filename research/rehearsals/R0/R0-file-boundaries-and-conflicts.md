# R0 — File boundaries and conflicts

## Worktrees (declared before any edit)

```text
/home/adarsh-yadav/Documents/projects/semant                [feat/rehearsal-research-r0]  ← THIS work
/home/adarsh-yadav/Documents/projects/semant-home-archive   [feat/archive-threads]        ← DO NOT TOUCH
/home/adarsh-yadav/Documents/projects/semant-oss            [feat/oss-foundation]         ← DO NOT TOUCH
```

The two sibling worktrees are separate branches (archive-threads UX, OSS foundation). R0 and the
whole rehearsal program stay inside the main worktree; **no file in the sibling worktrees is read or
written.**

## R0 write boundary (this gate)

R0 writes **only**:

```text
architecture-lab/rehearsals/R0/*.md      # the ten R0 reports (this folder)
architecture-lab/rehearsals/README.md    # optional pointer
```

Nothing else. No `backend/`, no `frontend/`, no schema, no Mongo, no route. (`scripts/_run_backend.py`
already exists untracked from the prior session as a server-launch helper — see risks; it is not part
of R0 and will not be committed under this gate unless you want the launcher kept.)

## Future research boundary (R1+, proposed — not created in R0)

```text
architecture-lab/rehearsals/{protocols,fixtures,runs,candidates,evaluations,skills,decisions,schemas}/
scripts/rehearsal_*.py        # deterministic runner + trace recorder (R1), read-only adapters
backend/tests/test_rehearsal_*.py   # only if the runner has pure logic worth unit-testing
```

The runner **imports** production services read-only; it **defines no production entity** and adds
**no route**. If a graduated candidate ever needs a product schema (R5+), that lands under normal
`backend/`/`frontend/` review as its own increment — never smuggled through the research folder.

## Untracked / user-owned files present (must be preserved, not committed as mine)

`git status` shows these untracked/modified paths that are **user-owned** and must be left alone:

- `new-planning/` — the Rehearsal Research Program document set (12 files). **User-authored source
  material.** Do not modify; do not claim authorship. (May reference it read-only.)
- `vault/…` — Obsidian notes incl. `passage rehearsals/PASSAGE-REHEARSAL-001.md`, many pasted
  images, and a modified `vault/the stories and the motives/plan.md`. **User-owned.** Untouched.
- `scripts/_run_backend.py` — prior-session server launcher (untracked).

R0 commits touch **only** `architecture-lab/rehearsals/`. Everything under `new-planning/` and
`vault/` is left exactly as found.

## Likely future conflicts to flag now

1. **`differential/DifferentialWorkspace.jsx`** is the single busiest file (Select/Brush/Trace/
   Collect/Connect/Frame/Refine/Read/Similar tools + inspector). Any prototype (R4) that adds an
   inquiry layer or context-breathing will edit it; it must be treated as a high-contention file and
   changed in small, reviewable diffs.
2. **`blocknote/Manuscript.jsx` + `PostDetailPage.jsx`** own the chip/Mention/RefPicker wiring. A
   Writer-side prototype touches both; the `data-*` chip contract (`blockConvert.test.js`) is a
   regression fence — extend, don't fork.
3. **`state/regionStore.js`** is the shared Field↔Manuscript store; percept/ground/recall all pass
   through it. A prototype that adds contextual role or a return packet will pressure it.
4. **`schemas/post.py`** — any *graduated* durable field (role, embodiment, inquiry) would be an
   additive `Post` field; must follow the E/F additive-versioned pattern and never reshape
   `region_annotations`.

None of these are edited in R0. They are named so R1+ packets set explicit, minimal file boundaries.
