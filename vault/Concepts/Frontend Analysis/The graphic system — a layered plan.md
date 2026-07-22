# The graphic system — a layered plan

**The reframe:** Semant's graphics are mostly **data visualization of perceptual objects**, not ornament. So the plan is a stack from *no-data brand* → *fully data-driven viz*, and **each data-driven graphic is gated by whether its data contract exists** (cross-ref the Contract Atlas). "Do we need more data types to build the graphic side?" — **yes, for the lower layers.**

## The six layers

### L1 · Identity (no data) — DONE
Logo/mark ("The Ground"), favicon, wordmark, social card, `SemantMark`/`SemantLogo`/`MarkLoader`. Pure SVG. Shipped in `feat/brand-svg` (PR #61).

### L2 · Domain glyphs (no data) — small, buildable now
A unified icon set for Semant's *concepts*: Ground's **7 types** (region · field · path · boundary · constellation · relation · frame), Percept (`◈→<PerceptMark/>`), Mention, Reading, Recall, Dissect, Refine. Today these are **divergent** — unicode `GROUND_GLYPH` vs a lucide tool-rail name the same 7 types differently. **One SVG set unifies both.** Approach: hand-built SVG components. Data: none.

### L3 · State graphics (no data) — buildable now
Empty / loading / error / 404 — branded hand-drawn plum line motifs (the region-mark language, not clip-art). Approach: SVG + `MarkLoader`. Data: none.

### L4 · Data visualization of perceptual objects — THE SUBSTANCE (gated by data)
| Graphic | What it renders | Data contract | Ready? | Approach |
|---|---|---|---|---|
| **Region / mask overlay** | `mask_rle`→polygons on the image | `Region.mask_rle` (authoritative) | ✅ exists (RegionOverlay) | SVG overlay (have it) — polish only |
| **The Field** | grounds + percepts placed in image space | `post.grounds`/`percepts` (untyped List[dict]) | ✅ exists, ⚠ untyped | SVG (have it) |
| **Percept-lineage graph** | Percept ↔ Ground ↔ Mention, transformations | Mention (in-markup), lineage (partial) | ⚠ partial/untyped | **React Flow** (MIT) |
| **Taste / embedding map** (Anuraṇana) | thousands of regions/percepts clustered by similarity | `region_embeddings` (FashionCLIP) | ✅ **embeddings exist** — biggest sleeping asset | **WebGL/regl** (PixPlot pattern) |
| **Taste portfolio / signature** | a person's motifs/attributes over time | `taste_signals` collection | ✅ exists | **Recharts / visx** |
| **Domain-profile viz** | multi-label confidence (fashion/arch/painting) | `domain_profile.proposed{}` | ✅ exists | tiny SVG/Recharts |
| **Passage / orchestration timeline** | run stages, per-model timing/status | **a run/telemetry contract** | ❌ **ABSENT** (P0 finding) | blocked until a `vision_runs` store exists |
| **Atlas / Codex graphs** (future) | narrative node graphs | Atlas/Codex objects | ❌ absent (prose-only) | React Flow, later |

### L5 · Dynamic / runtime graphics (event-driven) — Invariant-9 bound
Dissect **perceptual-scan** (region marks resolving), **Passage-Rail** stage-pulse, **Recall** replay. These animate from *real* runtime state — **must reflect true events or stay decorative-static; never fabricate progress.** The passage-rail viz is **blocked** on the same missing run contract (L4). Approach: SVG + Motion/CSS, wired to real data.

### L6 · Editorial / marketing — DONE/partial
Pitch-page diagrams (operable Percept · unit thesis · protocol · transposition), landing See·Read·Write cards (already bespoke SVGs). Approach: hand-SVG + the plum system.

## The gating truth (why "more data types" matters)
The viz layer is only as truthful as the contract beneath it:
- **Ready now** (data exists): region overlays, the Field, the **taste/embedding map** (embeddings are computed!), taste portfolio, domain-profile, glyphs, states.
- **Present but untyped** (build with care, consider typing first): Percept-lineage — Ground/Percept/Mention are `List[dict]`/in-markup (Contract Atlas); a clean graph benefits from typing them.
- **Absent — needs a new data type before any honest graphic** (Invariant 9): the **passage/orchestration timeline** needs a `vision_runs`/telemetry contract (P0's smallest-P1); **Atlas/Codex** graphs need those objects to exist at all.

## Approaches / OSS by graphic kind
- Brand + glyphs + states + overlays → **hand-built SVG** (+ Motion for animation).
- Node/lineage/Atlas graphs → **React Flow** (`@xyflow/react`, MIT).
- Similarity/embedding map → **WebGL/regl** (PixPlot pattern) over `region_embeddings`.
- Portfolios/profiles/metrics → **Recharts / visx**.
- Motion → **Motion** (ex-framer) + CSS; reduced-motion safe.

## Sequence (buildable-first, honesty-gated)
1. **L2 glyphs + L3 states** (shell-safe, now) — unify the Ground-type set, brand the empty/loading/error.
2. **L4 ready-data viz** — polish region overlays; ship the **taste/embedding map** (highest-value unlock, data exists) + taste portfolio + domain-profile.
3. **Type the circulation objects** (Ground/Percept/Mention) → then the **Percept-lineage graph** (L4) and the L5 recall/scan with a firm contract.
4. **Introduce the run/telemetry contract** (P0 P1) → *then* the passage/orchestration graphics (L5) truthfully.
5. **Atlas/Codex graphs** — only after those surfaces exist.

**One-line doctrine:** build the brand and glyphs freely; build the data-viz only as fast as the data types beneath it become real — and never animate progress the backend can't prove.
