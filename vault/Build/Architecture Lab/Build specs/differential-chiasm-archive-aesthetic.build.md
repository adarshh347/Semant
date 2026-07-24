# Aesthetic pass — Differential · Inspector · Chiasm · Archive (redirected focus)

**Per Adarsh:** concentrate the graphic work on the **dense product surfaces** — Differential, Inspector, Chiasm, Archive. **Skip Home / Read / taste tiles.** Step 1 (global eyebrow tick, PR #75) can merge as-is; this replaces the earlier home/read steps.
**Aesthetic only** — icons, glyphs, overlay/empty-state styling, panel motifs. **No data/logic/behaviour change, no fabricated progress.** Reuse & extend the glyph registry `frontend/src/components/brand/glyphs/`. Plum v1.3, `currentColor`/theme-aware, reduced-motion safe.
**Ownership:** these are **Field/editor files** (`differential/*`, `RegionSurface.jsx`, `PostDetailPage.jsx`) — **serialize with any active Chiasm/CIRCUIT session**; `git pull` first; keep the diff presentational (icons + CSS + empty states) to stay low-collision.

## A · Differential — the seeing console (`differential/DifferentialWorkspace.jsx`, `SeeingConsole.jsx`)
- **Tool-rail glyph set** — Select · Brush · Trace · Collect · Connect · Frame · Refine · Read · Similar: one bespoke plum set echoing the mark, replacing the lucide mismatches; active tool keeps the plum-soft chip.
- **Layers panel** (Recall · Suggestions · Evidence · Working): a small lane glyph each; plum slider fills; refined lock + the `sys` tag on Recall.
- **Region-overlay attention treatment** (the signature look): selected/hovered region → plum stroke + soft halo; the dashed contour → a refined plum dash; plain boxes → lighter branded strokes; detached evidence → ghost dash.
- **Untouched pill + lightbulb hint** → small brand glyphs (an eye/untouched mark).

## B · Inspector — the right console (`differential/AttunementPanel.jsx`, `DifferentialWorkspace.jsx:1133/1459`)
- **Section eyebrows** — FIRST ATTENTION · WAYS OF LOOKING · SOURCES · OPERATION MEMORY · INSPECTOR: add the region-tick here (Field file, missed by the shell pass).
- **Act chips** (Map gaze · Brush light · Find parts · Start note · Ask for counter-reading): a tiny glyph per act.
- **Suggest acts** button → keep plum; swap the generic sparkle for the mark/percept glyph.
- **Ways-of-looking chips** (Ordinary · Fashion & body · Built space · Painting & surface · Let it choose) → domain glyphs.
- **Sources badges** (YOLO Segmentation · SAM Refinement) → small model/instrument glyphs.
- **Operation Memory** row → a quiet **operation glyph** + a refined status dot (the state is *real* — "Complete" — so a truthful indicator is fine; **do not animate fake progress**).
- **INSPECTOR empty** ("Nothing under attention…") → a branded waiting motif (a quiet region-mark), not a blank line.

## C · Chiasm — the workspace (`components/RegionSurface.jsx`, `PostDetailPage.jsx`)
- **Parts list** (All parts · person / closed eyes / …): the **star (prioritise)** → a filled **PerceptMark**/region-tick when starred; anchor-vs-fine row glyphs.
- **Quiet · Outline · Focus** view toggles (`RegionSurface.jsx:27–29`) → the three "map" glyphs.
- **Image / Regions tabs**, the **Differential** entry chip, **AI Assistant** button → brand touches.
- **Story empty** ("No story yet · Write the story") → a branded writing-empty motif + refined pencil.
- **Highlights** tab glyph.
- *(Manuscript origin-marks + `/part`·`/lens` chip glyphs = Handoff #A; include if this session also owns `blocknote/*`, else leave for that session.)*

## D · Archive (`pages/GalleryPage.jsx`, `components/ArchiveTimeline.jsx`)
- Archive **grid hover** → plum accent/edge; **timeline scrubber** month/year markers in plum; a branded **empty** state; the archive eyebrow tick.

## Sequence & rules
1. Merge PR #75 (global tick) — done, shell-safe.
2. **B · Inspector** first (highest ratio of dense text → brand; mostly CSS + small glyphs).
3. **A · Differential** tool-rail + overlay treatment (the signature look).
4. **C · Chiasm** parts list + story-empty + toggles.
5. **D · Archive** grid/timeline polish.
Fresh `feat/aesthetic-surfaces` off `main`, isolated worktree; presentational-only; serialize on the Field files; conventional commits, own issue + PR, CI `test` green; screenshot each (light+dark, reduced-motion). Stop after each surface for review.
