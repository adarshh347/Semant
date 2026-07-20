# Workflow log — Drishya frontend rework

Two tracks of documentation, kept in step:

1. **This file** — a plain chronological log of every step we take, newest at the bottom.
2. **GitHub issues** (repo `adarshh347/Semant`) — one issue per lane/decision, holding the fuller record. Drafts live in `architecture-lab/issues/` and are pushed with `gh`.

## Issue format (use for every lane)
- **Expected** — what Adarsh + Claude (desktop) agreed the lane should achieve.
- **Claude Code response & promises** — what the CLI said it analysed and would do.
- **Delivered (verified)** — what the code actually shows, checked against the promise.
- **Gaps / deferred / new demands** — misses, things deferred to another lane, and new Purpose-level demands that surfaced.
- **Decisions** — what is now LOCKED for the build.

## Log

- **Set up lab.** Created `architecture-lab/` with README, `00-architecture-map.md`, six lane prompts, `07-purpose-lens.md` (Purpose → Structure → Surface), and `decisions-log.md`. Page named **Drishya**.
- **Lane 5 research.** Claude Code traced the edit mode, produced `responses/lane-5-writing-studio.findings.md`, asked 6 questions.
- **Lane 5 decisions locked.** All 6 answers + Path A first + `origin` field + delete dead code → `decisions-log.md`.
- **Lane 5 build.** Claude Code implemented bubble toolbar, gutter (drag + ⋯ menu), unified insert menu with Sutradhar compose, position-aware `insertBlock`, status line in footer, drag-reorder, `origin` on every block. Build passes / HMR live.
- **Lane 5 verification (this step).** Claude (desktop) read the shipped code. Verdict + gaps recorded in `issues/lane-5.md` (GitHub issue #13). See that file.
- **Lane 1 research.** Running in a parallel session (top chrome). Findings → `responses/lane-1-top-chrome.findings.md`.
- **Lane 5 review (deep).** Claude (desktop) read shipped code; found extra issues (blocks 80px tall, gutter reads as mystery boxes, `activeBlockId` not cleared on delete, empty-edit dead end, `origin` stored but not surfaced, duplicate headings, id collision risk). Wrote `lane-5-second-layer.build.md`.
- **Inline AI locked.** Slash commands + inline generation chosen over chatbot-style. Wrote `purpose-inline-ai.design.md` (research-first). Decisions logged.
- **gh note.** Repo has no `architecture` label yet — create it once (`gh label create architecture …`) or omit `--label`.
- **Issues opened.** #13 Lane 5 rework (verification), #14 Lane 5 second-layer cleanup, #15 Purpose — inline AI & slash commands. All labelled `architecture`. `architecture` label created in repo.
- **Next:** run #14 (build, alone — edits editor files) then #15 (research, parallel-safe).

- **Lane 5 second-layer build.** Claude Code implemented `lane-5-second-layer.build.md`: content-driven block height (min-height 80px→1.7em), gutter controls given a visible resting chip, decorative "Writing studio" intro removed, single-column collapse (`.edit-main-column`/`.edit-side-column` unwrapped; Tags parked as a quiet end-of-column block, still deferred to Lane 4), `activeBlockId` cleared to a neighbour on delete, focused empty paragraph seeded on empty-story edit, `origin` surfaced as `data-origin` on edit + view blocks (unstyled hook), and `Date.now()` id-collision fixed with a monotonic counter. AI composer left untouched per the Coordinate caveat (slash-command work will replace it). Structure+sizing only; every capability intact; `npx vite build` passes. Verdict + evidence in `issues/lane-5.md`.
