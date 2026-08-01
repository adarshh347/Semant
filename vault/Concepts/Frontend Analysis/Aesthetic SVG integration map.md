# Aesthetic SVG integration map — where the brand touches every section

**Scope: aesthetic only** — iconography, section motifs, decorative marks in the plum region-mark language. **No functional/data change.** The L2 glyph registry already exists (`components/brand/glyphs/` — groundGlyphs, registry, PerceptMark) from the graphic-system work; most is **unwired**. This map says *where to wire it and what else to add*, section by section, grounded in real spots.

**The unifying tell (do this once, everywhere):** every uppercase **eyebrow / kicker / section-head** gets a tiny **region-mark tick** before the label (a 3–4px plum glyph). It appears on home tiles, panel headers, Field, Read, 404 — so every section reads as *Semant* at a glance. Spots found: `home/*Tile.jsx (eyebrow)`, `PostDetailPage.css (kicker/section-head/panel-header)`, `AletheiaHook.jsx (kicker)`, `NotFoundPage/RouteError/PlaceholderPage (eyebrow)`.

---

## 1 · Manuscript — the article-writing section (the one you named)
Surface: `components/blocknote/{Manuscript,partRefBlock,regionRefInline}.jsx`, `PostDetailPage.jsx` (Story tab, slash, origin, TAGS).
- **Section markers:** a region-mark tick before "MANUSCRIPT", the Story/Tags heads (`PostDetailPage.css section-head/kicker`).
- **Origin provenance mark (signature move):** a small, quiet glyph distinguishing **`origin: sutradhar`** (AI-authored) blocks from human ones — a plum hairline tick in the block gutter. Aesthetic trace of "who wrote this," not a control.
- **Block-type gutter glyphs:** subtle paragraph / heading / quote marks in the block side-menu (BlockNote side menu) — plum, low-weight.
- **`/part` & `/lens` inline chips** (`regionRefInline`, `partRefBlock`): refine the chip with the **PerceptMark** (`/part`) and a **Reading/lens glyph** (`/lens`) — brand the chip, not its behaviour.
- **Slash-menu icons:** one small set for the three groups (structure · AI verbs · refs) so the menu reads as a family.
- **Tags strip:** a quiet tag glyph; keep it a thin bottom strip (per taste spec).

## 2 · Differential / Field — "better differential icons"
Surface: `differential/DifferentialWorkspace.jsx` (tool rail Refine/Trace/Connect/Collect + `GROUND_GLYPH`), overlays.
- **Wire the 7 Ground-type glyphs** (registry already built) at the `GROUND_GLYPH` call-sites: region · field · path · boundary · constellation · relation · frame — replacing the ASCII/unicode. *(Field-file edit → coordinate with the Field-owning session; the swaps are one-liners in the needs-map.)*
- **Tool-rail icon set:** Dissect · Refine · Trace · Collect · Connect as one cohesive plum set (echoing the mark), replacing lucide mismatches.
- **PerceptMark** on percept panels/chips (`.diff-eyebrow "Percept"/"Percepts"`).
- **Overlay aesthetics:** selected/hover region → a plum stroke + soft halo (the signature attention treatment); detached-evidence → a dashed ghost stroke.
- **Reading / Recall glyphs** on the reading strip and the recall trigger.

## 3 · Orchestration / passage / instruments (aesthetic patterns — decorative only)
Surface: the CIRCUIT seeing-console / passage / instrument panels, `Threads.jsx`, run/provenance chips.
- **Passage "signal" motif:** the stage lane rendered as a row of region-marks on a hairline — a **decorative** ribbon behind the passage. **Honesty rule stays:** if it animates, it must reflect real events; otherwise keep it static/decorative — never fake a queue moving.
- **Instrument glyphs:** a small icon per capability (segment · refine · embed · semantic · depth) so the instrument panel reads as a set of "sensory organs."
- **Run / provenance chip glyph:** a tiny run mark on provenance badges (aesthetic stamp).
- **Message-queue texture:** a quiet lane/tick pattern as a background for the passage area — pure texture, low-contrast.

## 4 · Home dashboard
Surface: `components/home/*Tile.jsx`.
- Region-mark tick on each tile eyebrow; a distinct small **section glyph** per tile (Continue · Archive · Read · Taste · This-week); an optional very-subtle background motif on the hero tile. (ContinueTile already a "door" — motif only.)

## 5 · Read / feed (Aletheia hook)
Surface: `AletheiaHook.jsx` (kickers).
- **Lens glyph** on the reading; a **perceptual-fork glyph** on the "what pulls your eye?" choice; a "read deeper" mark; kicker ticks.

## 6 · Nav / chrome / global
- Mark + wordmark (done). Add: **section-divider motif** (a hairline with a centered region-mark), refined **⌘K** and **theme-toggle** glyphs to match the family, and the eyebrow-tick globally.

## 7 · Sub-features / small spots (the "and all")
- **Highlights** → a highlight/underline glyph. **Epics** → a collection/bound-pages glyph. **Personas (Darpan)** → a persona/mirror glyph. **Research** → an agent glyph. **Anatomy** → a catalog/parts glyph. **You/taste** → a taste-signature glyph + motif chips. **Upload** → keep ink pill (no icon needed) or a small intake mark.

---

## How to sequence (aesthetic pass)
1. **Global tell first** — the eyebrow/kicker region-mark tick everywhere + section-divider motif. One small change, whole-app cohesion.
2. **Manuscript** — origin-mark, `/part`·`/lens` chip glyphs, slash-menu icon set, block-type gutter marks.
3. **Differential** — wire the Ground-type + tool-rail glyph sets, overlay attention treatment *(coordinate: Field-owned files)*.
4. **Home / Read / sub-features** — per-section glyphs.
5. **Orchestration/passage** — decorative signal motif + instrument glyphs *(honesty rule: real events or static)*.

**Ownership:** #1, #4, #5 (partial), home/read/sub-features are shell-safe (any brand session). The Manuscript (#2) and Differential (#3) touch editor/Field files → coordinate with the sessions that own them. Everything here is **aesthetic** — no data, no logic, no fake progress.
