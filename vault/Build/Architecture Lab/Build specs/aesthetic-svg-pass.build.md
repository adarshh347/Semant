# Aesthetic SVG pass — shell-safe slice + owner handoffs

**Source:** `vault/Concepts/Frontend Analysis/Aesthetic SVG integration map.md`. **Aesthetic only — no data/logic/behaviour change, no fabricated progress.** Reuse & extend the existing glyph registry `frontend/src/components/brand/glyphs/`.

## Shell-safe pass — Claude Code (fresh `feat/aesthetic-pass` off `main`, isolated worktree)
**Rules:** plum v1.3 tokens, `currentColor`/theme-aware, reduced-motion safe, **no Chiasm/editor/Field files** (`PostDetailPage.jsx`, `differential/*`, `blocknote/*` are owned by other sessions — see handoffs). Conventional commits, own issue + PR, CI `test` green. Stop after each step.

1. **The global tell — an eyebrow tick + section divider.** A `<SectionEyebrow>` (a 3–4px region-mark tick before the uppercase label) and a `<SectionDivider>` (hairline + centered region-mark), both in `components/brand/`. Wire the eyebrow into the **shell** eyebrows only: `components/home/*Tile.jsx`, `AletheiaHook.jsx` (kickers), `NotFoundPage/RouteError/PlaceholderPage`, nav, and the Gallery/Feed/Epics/Research/Anatomy/You page heads. **Do NOT touch `PostDetailPage.jsx` eyebrows** (handoff #A). Screenshot; stop.
2. **Home tile section glyphs.** A distinct small glyph per tile (Continue · Archive · Read · Taste · This-week) added to the registry and placed on each `home/*Tile.jsx` eyebrow. Optional very-subtle hero-tile background motif. Screenshot; stop.
3. **Read / Aletheia glyphs.** A **lens** glyph on the reading, a **perceptual-fork** glyph on the "what pulls your eye?" choice, a "read deeper" mark — in `AletheiaHook.jsx`. Screenshot; stop.
4. **Sub-feature page glyphs.** One small mark each for Highlights (underline), Epics (bound pages), Personas/Darpan (mirror), Research (agent), Anatomy (parts catalog), You (taste signature) — on those page heads. Refine `⌘K` + theme-toggle glyphs to match the family. Screenshot; stop.

Verify: light+dark, reduced-motion, build + `test` green, no functional diff.

## Handoff #A — Manuscript (for the session owning `blocknote/*` + `PostDetailPage.jsx`)
Aesthetic-only, uses the glyph registry:
- **Origin provenance mark** — a quiet plum tick on `origin:'sutradhar'` blocks (AI-authored) vs human, in the block gutter.
- **`/part` · `/lens` chip glyphs** — `PerceptMark` (part) + a reading/lens glyph in `partRefBlock.jsx` / `regionRefInline.jsx`.
- **Slash-menu icon set** (structure · AI verbs · refs) as one family; **block-type gutter marks** (paragraph/heading/quote) in the BlockNote side menu.
- **Section-head ticks** on MANUSCRIPT / Story / Tags (`PostDetailPage.css` `section-head/kicker`).

## Handoff #B — Differential / Field (for the session owning `differential/*`)
Aesthetic-only, uses the glyph registry (needs-map has the exact call-sites):
- **Wire the 7 Ground-type glyphs** at the `GROUND_GLYPH` call-sites (region · field · path · boundary · constellation · relation · frame) — one-line swaps.
- **Tool-rail icon set** — Dissect · Refine · Trace · Collect · Connect, one cohesive plum set replacing lucide mismatches.
- **Overlay attention treatment** — selected/hover region → plum stroke + soft halo; detached evidence → dashed ghost stroke.
- **PerceptMark / Reading / Recall glyphs** on the Field eyebrows + reading strip + recall trigger.

## Handoff #C — Orchestration / passage (for the CIRCUIT session, whenever it surfaces)
- A **decorative signal motif** behind the passage (region-marks on a hairline) + small **instrument glyphs** per capability. **Honesty rule: decorative-static, or animate only from real events — never fake a queue.**
