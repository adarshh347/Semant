# Workflow protocol — commits, issues, PRs (Claude Code owns this)

Adarsh should not have to manage git hygiene, issues, or PRs by hand. Claude Code keeps the trail in order automatically, every session.

## Branch & PR
- Feature work stays on the current working branch (`feat/frontend`).
- Keep **one open PR** ("Drishya frontend rework") from `feat/frontend` into the base branch. Push after each session so the PR stays current. Don't wait for "everything" to be done.
- The PR description links every relevant issue; use `Closes #NN` for issues a change fully finishes.

## Commit rules (do this without being asked)
1. After completing a task or a checklist item, **stage only the files you changed** and commit. Never end a session with a dirty tree — commit it or state explicitly why not.
2. **Conventional Commits**, referencing the issue: `type(drishya): short summary (#NN)`.
   - types: `feat`, `fix`, `refactor`, `docs`, `chore`.
   - examples: `fix(drishya): make one-line blocks hug their text (#14)`, `feat(drishya): slash menu for block types (#15)`.
3. Keep commits small and logical (one concern each), not one giant blob.
4. Architecture-lab docs commit as `docs(arch-lab): …`.
5. **Do not stage stray/unreviewed paths** — e.g. `android/`, `.idea/`, build output. If something new appears untracked, decide whether it belongs in `.gitignore` and say so; don't blind-add it.

## Issue rules
1. Every lane/phase has a GitHub issue (label `architecture`). Update its checklist / Delivered table **in the same session** you do the work.
2. If you discover a new problem, add it to the relevant issue (or note that a new one is needed) — don't let findings live only in chat.
3. When an issue is fully done and verified, reference it with `Closes #NN` in the commit or PR.

## Verification rule
- **UI, sizing, and layout fixes are verified by rendering + screenshot, not by reading CSS/JSX.** A rule can be correct in source and still wrong on screen (e.g. an undefined token, a stale cascade). Capture the state before claiming a visual fix is done.

## Handoff line
End each session with: what changed, which commits, which issues updated, and what's next — one short paragraph.
