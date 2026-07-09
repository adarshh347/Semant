# Drishya/Darshan — frontend build-surface inventory + open-source harvest map

**Mode:** research + plan. No app code changed.
**Audience:** Adarsh as orchestrator (non-coder director). Plain language; every "feels premium" names the *architectural* cause, not the look.
**Why this doc exists.** The six track findings (A–F) are the **build plan** — they say *what the system becomes*. They deliberately don't enumerate the *frontend subsections* you'll actually sit in front of and build or refurbish, one by one. This doc does that, and then answers the question you raised: **for each subsection, do we build it, or harvest a section from open source and re-fit it to our use case?**
**Scope (per your call):** frontend now in depth; backend covered as a right-sized *terrain map* (§Part 3) with the deep backend-harvest pass deferred to a follow-up.
**Grounding:** frontend read at commit `342a12d` (`frontend/src/`), tracks A–F in `responses/`, licences web-verified July 2026 (sources at end).

---

## The one idea to hold first (the harvest philosophy)

Reframe "build vs buy" through the lens's layers, because *where* a section lives decides *whether* harvesting helps:

- **Foundation & Behaviour sections** (editor engine, annotation geometry, command-palette logic, resizable panes, focus/keyboard, virtualization) are **generic, hard, and solved** by mature open source. Harvesting here is a huge win — it's the "khazana." You are not special at ProseMirror plumbing; don't rebuild it.
- **Structure sections** (your shell, your panel grammar, how the reading strip sits under the image) are **semi-generic** — harvest the *pattern*, not the whole component.
- **Purpose sections** (Aletheia reading, taste graph, pick→comment→remember, `actor` provenance, the felt-meaning loop) are **your bespoke moat** (Track E's wedge). There is nothing to harvest here and you shouldn't try — this is the code that *is* the product.

So the harvest rule is: **adopt at the Foundation, harvest-a-pattern at the Structure, hand-build at the Purpose.** The danger is inverting it — hand-rolling a rich-text editor (Foundation) while thin-wrapping someone's taste model (Purpose). The current code does exactly the first half of that mistake (a hand-rolled divider, a hand-rolled bbox editor, one-TipTap-editor-per-block) — see §Part 2.

Three verdict labels used throughout:
- **ADOPT** — take the dependency wholesale; it *is* the Foundation.
- **HARVEST** — study a specific open-source section, lift the mechanism/structure, re-fit to our contracts (normalized `Region`, `actor`, `block_id`, tokens). Not a dependency; a transplant.
- **BUILD** — bespoke; the moat. Keep it ours.

---

# Part 1 — The frontend build surface (micro-inventory)

Grouped by surface. Each item: **what it is · current state (grounded) · what the tracks demand · layer · verdict** (expanded in Part 2).

## A. The writing studio (Drishya right pane) — *your flagged "big one"*

| # | Subsection | Current state | Tracks demand | Layer | Verdict |
|---|---|---|---|---|---|
| A1 | **Block editor engine** | one **TipTap editor per block** (`RichTextBlock.jsx` 213 LOC, `TipTapEditor.jsx`), Path A (`decisions-log`: "one TipTap per block + shared bubble toolbar") | Path B (single-document editor) flagged as the endgame for slash/inline-AI/drag-reorder | Foundation | **ADOPT/HARVEST** (BlockNote or Novel — §E1) |
| A2 | **Slash command menu** | built: `slashCommand.jsx` (211) + `SlashMenu.jsx` (71), context-aware (structure trio vs AI verbs), floating-ui `strategy:'fixed'` | grow `/draft /write /continue /rewrite`, later `/part` `/lens` (region & reading inserts) | Structure/Behaviour | **KEEP + HARVEST patterns** |
| A3 | **Bubble/selection toolbar** | locked design (bold/italic/underline on selection); TipTap floating-menu dep present | selection→AI verbs (expand/shorten/rewrite) live here | Behaviour | **HARVEST** (TipTap BubbleMenu) |
| A4 | **Inline AI generation** | slash-AI Phase 2 build-noted (`/draft`+`/write`), non-streaming; Phase 3 streaming | writer must receive per-image **context pack** (Track C RAG) — ghost-text/Tab-accept later | Behaviour/Purpose | **BUILD** (glue) + HARVEST (streaming UI) |
| A5 | **`origin` provenance marks** | `origin:'human'\|'sutradhar'` on blocks; `data-origin` hook, unstyled | range-level origin (mixed authorship) as a later TipTap mark | Foundation/Purpose | **BUILD** (bespoke) |
| A6 | **Block gutter: drag-handle + ⋯ menu** | built (Lane 5): drag reorder, per-block overflow | survives into Path B if adopted | Behaviour | **HARVEST** (dnd-kit / BlockNote gives it free) |
| A7 | **Status line (words/min/blocks)** | lifted out of body to footer (Lane 5) | keep | Craft | **KEEP** |
| A8 | **Meta-head (handle + epic chip)** | built (Lane 4), gated to Story tab | provenance home; don't duplicate in topbar | Structure | **KEEP** |

## B. The Visual pane (Drishya left pane) — the annotation + reading surface

| # | Subsection | Current state | Tracks demand | Layer | Verdict |
|---|---|---|---|---|---|
| B1 | **Region overlay (SVG polygons + rects)** | `RegionDetectorModal` renders normalized SVG `viewBox 0 0 100 100`, `non-scaling-stroke` — clean, tokenized, **trapped in a modal** | un-modal into the live pane; one SVG renders auto polygons + creator rects (Track D §2) | Structure | **HARVEST-from-self** (promote modal body) |
| B2 | **Manual bbox editor** | `BoundingBoxEditor.jsx` (421) — **pixel-space** boxes, neon/glass/emoji, PATCHes retired `bounding_box_tags` | **delete**; manual marks become `actor="creator"` normalized regions on the same SVG (Track A/D) | Foundation | **DELETE + rebuild small** |
| B3 | **Parts panel (list synced to shapes)** | modal has it: grouped anchor▸fine, ★ prioritise, • has-note, hover↔highlight | the antidote to on-image clutter with dozens of Fashionpedia parts; + category/attribute filter chips | Structure/Behaviour | **HARVEST-from-self** + extend |
| B4 | **Many-parts reveal (coarse→fine, focus-dims-others, filters)** | partial (`labelVisible`, `is-sel`, `coarse_only`) | load-bearing once Fashionpedia yields dozens (Track B/D) | Behaviour | **BUILD** on harvested overlay |
| B5 | **Reading strip (Aletheia in-pane)** | today a separate right-pane **Unconceal tab**, divorced from image | fold under the image; tap a lens → highlight its `region_ids` (Track C/D) | Structure/Purpose | **BUILD** (bespoke) |
| B6 | **Pick→comment→remember loop** | exists in the modal (select→note→intensity→save); shows saved state weakly | make live + persistent; one-tap-prioritise is the consumer rung (Track D/F) | Purpose | **BUILD** (moat) |
| B7 | **Layer toggle (regions on/off + density)** | dead `Image\|Annotations` tabs set state nothing renders | replace with a real layer control (Track D §2) | Structure | **BUILD** small |

## C. The split shell / app frame

| # | Subsection | Current state | Tracks demand | Layer | Verdict |
|---|---|---|---|---|---|
| C1 | **Resizable split + divider** | hand-rolled div + document mouse listeners; `leftPanelWidth` SSOT; **no keyboard/ARIA/presets**; `allotment` installed but **unused** | real `separator` (APG), collapse/"focus writing" preset, persist width (Lane 2) | Behaviour | **ADOPT** (allotment / react-resizable-panels) |
| C2 | **Panel headers (tabs + actions slot)** | `<h3>`+tabs; pencil in an actions slot | tabs-only + one shared `.panel-actions` slot per pane (Lane 2 Q1) | Structure | **BUILD** small (a primitive) |
| C3 | **Pane-relationship / shared selection** | zero shared state across panes | lift `selectedRegionId`; link region↔block (Lane 2 §4, Track A `block_id`) | Foundation | **BUILD** (moat glue) |

## D. Top chrome / navigation — *mostly done*

| # | Subsection | Current state | Verdict |
|---|---|---|---|
| D1 | Slim rail + disclosure on `/posts/*` | delivered (Lane 1, #19) | **KEEP** |
| D2 | Topbar: overflow ⋯, pencil-to-edit, quiet AI | delivered (Lane 1) | **KEEP** |
| D3 | Command palette (global ⌘K) | **does not exist** | **ADOPT** (`cmdk`) — §F-cross |

## E. The consumer / feed surface — *thin today, big net-new*

| # | Subsection | Current state | Tracks demand | Layer | Verdict |
|---|---|---|---|---|---|
| E1 | **Feed / gallery** | `GalleryPage`, `PostFeedCard`, `TextFeedPage` (basic) | pause-worthy feed that hosts the Aletheia hook (Track F §2) | Structure | **HARVEST** (masonry) + BUILD |
| E2 | **Aletheia-in-feed hook** | none | 1-lens reading + 1 fork, tap-gated, cached-per-image (Track F MVP) | Purpose | **BUILD** (reuse Track C engine) |
| E3 | **Signal capture (dwell/tap/fork)** | none | lightweight `taste_signals` events, batched client-side (Track F §1) | Behaviour/Purpose | **BUILD** (bespoke, thin) |
| E4 | **Taste portfolio ("your eye leans…")** | none (creator persona exists server-side) | audience-facing mirror of accrued taste (Track F §3) | Purpose | **BUILD** (moat) |

## F. Cross-cutting primitives (the Foundation you don't have yet)

| # | Primitive | Current state | Verdict |
|---|---|---|---|
| F1 | **Design tokens** | tokens exist but leaky (`--space-5` undefined bug; 6 hardcoded hex; neon/glass islands) | **BUILD/HARDEN** (Surface pass) — foundation, do before polish |
| F2 | **Button/menu/dialog/toast primitives** | ad hoc; the same control differs across the app | **ADOPT** a headless kit (Radix / shadcn patterns) |
| F3 | **Command palette** | none | **ADOPT** `cmdk` |
| F4 | **Loading / empty / error / edge states** | inconsistent | **BUILD** to a checklist (rubric §3.4) |
| F5 | **Modal/focus-trap, keyboard, a11y** | partial | **ADOPT** (Radix Dialog gives focus-trap free) |

---

# Part 2 — The harvest map (what to lift, from where, and the catch)

## 2.0 How to read a harvest verdict

For each candidate: **the section · the source · licence · what to lift · effort to re-fit · the contract catch** (how it meets our normalized-`Region` / `actor` / `block_id` / token contracts — the thing that makes "just drop it in" naive).

The recurring catch: **open-source annotation/editor tools are built to produce *their* data shape, not ours.** Harvesting is cheap when you take the *mechanism* (how it renders/drag/keys) and expensive when you take the *data model* (which you then have to translate to `Region`). So we harvest mechanisms, and keep our contracts.

## 2.1 The editor — your biggest khazana (deep-dive)

**You are already on TipTap** (`@tiptap/react`, `starter-kit`, `suggestion`, `placeholder`, `floating-menu`). That single fact reshapes the decision: the Notion-style OSS editors worth harvesting are *the same family*, so adoption is a migration, not a rewrite.

| Option | What it is | Licence | Fit to us | Verdict |
|---|---|---|---|---|
| **TipTap (current, Path A: one editor per block)** | ProseMirror wrapper; we hand-assemble blocks | MIT | we already own the integration; but N editors = N ProseMirror instances = the drag-reorder/slash/inline-AI pain the decisions-log flagged | the thing to *migrate off* for the editor body |
| **BlockNote** | **Notion-style block editor built on TipTap+ProseMirror**; blocks, drag-handle, slash menu, selection toolbar **out of the box**; block API (`insertBlocks(block, ref, placement)`) | **MPL-2.0** core (free for commercial/closed); AI/export/multi-column are paid/GPL add-ons | **this is Path B, pre-built.** Its block model = our `insertBlock(block, atIndex)` decision, already solved. Custom blocks = where `/part` (a region) and `/lens` (a reading) plug in as first-class blocks | **ADOPT for the editor body** (strongest single harvest) |
| **Novel** | Notion-style WYSIWYG on TipTap with AI autocomplete (ghost-text/Tab) baked in | MIT (Apache-adjacent components) | thinner than BlockNote; its **value is the inline-AI UX** (ghost text, `++`/`/` flows) we want in A4 | **HARVEST the inline-AI UX**, even if the body is BlockNote/TipTap |
| **Lexical (Meta) / Plate (Slate)** | different engines (not ProseMirror) | MIT | powerful, but **switching engines throws away our TipTap investment** (slash, marks, `origin`) | **reject** — wrong family for us |

**Recommendation (editor):**
1. **Adopt BlockNote as the document body** (Path B) — it gives you drag-reorder, the slash menu, the selection toolbar, block IDs, and a clean `insertBlocks` API for free, all in the ProseMirror/TipTap family you already use. This retires the "N editors per block" tax and the hand-maintained gutter (A6).
2. **Keep your `origin` marks and `/part` `/lens` inserts as custom BlockNote blocks/marks** — this is the moat; BlockNote's custom-block API is exactly the extension point. `actor`/`origin` provenance stays yours.
3. **Harvest Novel's inline-AI interaction** (ghost-text continuation, Tab-to-accept) for A4, wired to Track C's context pack rather than a generic completion.
4. **Sequencing caveat:** this is a Foundation swap → do it in a dedicated slot, not concurrently with a Drishya lane editing the same files (same serialization note as Track D). The `decisions-log` "Path A first, plan Path B" line is effectively *"adopt BlockNote when ready for Path B."*

**The catch to name:** BlockNote stores a block document; your blocks currently carry `origin` and will carry region/reading references. You keep control of serialization — persist BlockNote's JSON but **keep `origin`/`actor` as block attributes you own**, so the taste/provenance contract isn't hostage to the library.

## 2.2 The annotation surface — harvest the mechanism, not the tool

| Section | Source | Licence | What to lift | Catch |
|---|---|---|---|---|
| **Region overlay / polygon+rect rendering** | **your own `RegionDetectorModal`** (Track D calls it "90% of the premium pane") | ours | promote its normalized-SVG renderer into the live pane | none — it's already on our contract; this is the cheapest, highest win |
| **Freehand draw / resize / keyboard nudge of shapes** | **Annotorious** (JS/TS/React image annotation) | **MIT** | the *interaction mechanics* (draw, edit vertices, handles) as a pattern | its data model is W3C Web Annotation, **not** our normalized `Region` — take the mechanics, translate coords to `{x,y,w,h}` 0–1, stamp `actor="creator"`. Don't adopt its store. |
| **Heavy labeling UX (many classes, hotkeys)** | **Label Studio Frontend** / react-image-annotate | Apache-2.0 / MIT | ideas only — filters, class lists at volume | far heavier than we need; a *reference*, not a dependency. Fashionpedia volume is handled by our filter-chips + focus-dims (B4), not a labeling IDE |

**Verdict:** **HARVEST-from-self (B1/B3)** is the main play; **HARVEST Annotorious mechanics (B2 rebuild)** only for the freehand-draw affordance if you keep manual marks (Track A Q2 is still open on whether freehand survives). Everything region-*meaning* (prioritise, note, `region_ids`↔lens) is **BUILD** — the moat.

## 2.3 Shell, panes, palette, feed — the generic Foundation/Structure

| Section | Verdict | Source | Licence | Note |
|---|---|---|---|---|
| **Resizable panes + divider (C1)** | **ADOPT** | `allotment` (already installed, VS-Code-derived) *or* `react-resizable-panels` | MIT / MIT | you already pay for `allotment` and don't use it. Adopt it (keyboard + collapse + persist for free) **or** drop it for `react-resizable-panels` (lighter, nested groups, persisted layouts). Either kills the hand-rolled divider's a11y gap. |
| **Command palette (D3/F3)** | **ADOPT** | `cmdk` | MIT | headless; `Command.Dialog` wraps Radix → focus-trap + Esc-close free. A ⌘K that runs the same verbs as `/` unifies "everyday AI" and navigation. |
| **Button/menu/dialog/toast (F2/F5)** | **ADOPT (patterns)** | Radix primitives / shadcn recipes | MIT | gives focus management, ARIA roles, Esc/outside-click *once*, reused everywhere — the "primitive vs one-off" fix from the rubric. |
| **Feed masonry (E1)** | **HARVEST** | a masonry layout (CSS columns or a small lib) | — | layout only; the *card* (with the Aletheia hook) is BUILD |
| **Drag reorder (A6)** | **HARVEST / free** | `dnd-kit` — or free if BlockNote adopted | MIT | if you adopt BlockNote, reorder comes with it; else `dnd-kit` is the clean harvest |
| **Motion** | **HARVEST** | small spring/transition util | MIT | motion tied to state changes (rubric 3.2); not a design system |

## 2.4 The moat — BUILD, do not harvest (Track E's wedge)

These have **no open-source equivalent** because they *are* the product; harvesting here would mean building someone else's product:
- **Aletheia reading** (context-triggered lenses, evidence-bound, region-tied) — Track C.
- **Pick→comment→remember** and the felt-meaning note — Track D §3.
- **`actor` provenance** (auto/creator/audience) and the **taste graph (Anuraṇana)** join — Track A/F.
- **The reading strip↔region highlight link**, `/part` `/lens` inserts, `origin` marks — the Visual↔Content complementarity.
- **Signal capture → taste portfolio** (Track F) — the two-sided flywheel.

The rubric's "which layer is doing the work?" habit is the guardrail: if a section's value is *felt-meaning*, it's Purpose → BUILD. If its value is *mechanism* (render, drag, key, resize, complete), it's Foundation/Behaviour → ADOPT/HARVEST.

---

# Part 3 — Backend terrain (right-sized; deep harvest pass deferred)

You said backend feels harder "because we depart too much based on use cases." That instinct is **correct, and it's the key to the whole harvest question** — so here's the terrain map that explains *why*, and where OSS still drops in cleanly. (A full backend-harvest analysis is a separate follow-up, per your scope call.)

## 3.1 Why backend harvest is harder than frontend

Frontend sections are mostly **mechanism** (render a polygon, resize a pane, complete text) — generic, so someone already built them. Backend splits into two very different halves:

- **The generic half (harvest-friendly):** model *serving* and *storage* — running Fashionpedia/SAM2/FashionCLIP, storing vectors, doing similarity search. These are standard ML-infra problems with mature, drop-in open source. **Nothing here is special to you.**
- **The bespoke half (build-only):** the *orchestration and meaning* — how detections become a `Region`, how a reading is triggered by context, how signals aggregate into a taste graph, the Aletheia/persona prompts. This is 100% use-case-coupled. **This is why backend "feels hard": the valuable half is, by definition, un-harvestable.** That's not a problem to fix; it's the moat again, on the server.

The trap to avoid is the mirror of the frontend one: **don't hand-roll model serving (generic, hard) while under-investing in the region/taste contracts (bespoke, load-bearing).**

## 3.2 The three clean backend seams (where OSS drops in)

| Seam | What it is | Harvest verdict (headline; deep pass later) |
|---|---|---|
| **Model serving** | run YOLO (have it) + Fashionpedia Mask-RCNN + SAM2 + FashionCLIP | **ADOPT serving infra** — the models are published; the work is *serving* them (GPU endpoint, batching, cold-start). Standard inference-server territory. Track B already phases this (FashionCLIP CPU-first → Fashionpedia/SAM2 GPU). |
| **Vector store** | hold FashionCLIP embeddings; ANN similarity for the taste graph | **ADOPT** — Track A already designed the seam: sidecar `region_embeddings` behind a stable `embedding_id`, so the store is swappable (Atlas Vector Search if on Atlas; else Qdrant/pgvector) **without touching `Region`**. This indirection is exactly what makes the store a harvest, not a rewrite. |
| **The data contract** | one normalized `Region` (Track A), `actor` provenance, `taste_signals` events | **BUILD** — this is the spine everything hangs on; it's yours. But it's *designed to be null-safe and additive*, which is what lets the harvested models/stores plug into it. |

## 3.3 What stays bespoke on the backend (build-only)
`detect-regions` orchestration (which detector wins, dedup/precedence — Track B), the Aletheia prompt/lens-registry (Track C), persona synthesis, the `taste_signals` aggregation and anti-abuse (Track F), the RAG context-pack assembly for the writer (Track C §4). These encode *your* product decisions; there is no library for "how a drape region becomes a felt reading."

## 3.4 The one structural thing to protect
Track A's insulation pattern — **stable pointers (`embedding_id`) and one typed contract (`Region`) with `extra='allow'`** — is what turns the generic backend half into ADOPT instead of BUILD. Keep that discipline: every harvested model writes *into* the contract; every harvested store sits *behind* a pointer. Then swapping FashionCLIP for something better, or Qdrant for Atlas, never reaches the product code. **That is the backend equivalent of "keep `origin`/`actor` as attributes you own" on the editor.**

---

# Part 4 — The harvest decision rubric (reusable)

Run any candidate section through these five questions before adopting:

1. **Which layer is its value?** Mechanism (Foundation/Behaviour) → ADOPT/HARVEST. Meaning (Purpose) → BUILD. *If you can't tell, ask: would a competitor's version look identical? If yes, harvest it.*
2. **Same family?** Does it fit our existing spine (TipTap for editing, normalized SVG for regions, our tokens)? Same-family = migration (cheap). Different engine (Lexical/Slate) = rewrite (reject).
3. **Whose data model wins?** If adopting means storing *their* shape, that's a red flag — harvest the mechanism and keep translating to `Region`/`origin`/`actor`. Never let a library own the moat's data.
4. **Licence.** MIT/Apache = adopt freely. **MPL-2.0 (BlockNote core) = fine for commercial/closed**, but changes to *their* files must be published — so extend via the plugin/custom-block API, don't fork their source. Watch the paid/GPL add-ons (BlockNote AI/export, multi-column): budget or avoid.
5. **Maintenance & escape hatch.** Is it active, and can we leave? Prefer things behind an indirection (a pointer, a custom block, an adapter) so removal is local. The unused `allotment` dep is the cautionary tale — adopt deliberately, not aspirationally.

## Risks / anti-patterns to avoid
- **The "recreate it ourselves" tax.** Re-implementing a harvested section from scratch "to understand it" usually reproduces the bugs the OSS project already fixed (keyboard, a11y, edge cases). Prefer adopt-and-extend over re-type.
- **Harvesting the moat.** Wrapping a taste/aesthetic model as if it were ours dilutes Track E's wedge. The felt-meaning must be built.
- **Dependency drift.** Installing without wiring (allotment) — pay only for what you use.
- **Licence surprise** on the paid tiers (BlockNote AI). Confirm before relying.
- **Contract capture.** Adopting a tool's data model instead of translating to `Region` — the one thing that would make later tracks (B/C/F) fight the frontend.

---

## Recommended first harvests (sequenced, foundation-first)
1. **ADOPT `cmdk`** (⌘K palette) and **a headless primitive kit (Radix/shadcn patterns)** — cheap, no contract risk, fixes the "primitive vs one-off" foundation gap immediately.
2. **Resolve the pane dep (C1):** adopt `allotment` (already installed) or swap to `react-resizable-panels`; delete the hand-rolled divider. One afternoon; big Behaviour/a11y win.
3. **HARVEST-from-self:** promote `RegionDetectorModal`'s SVG renderer into the live Visual pane (Track D) — highest value, on-contract already, no new dependency.
4. **ADOPT BlockNote for the editor body (Path B)** in a dedicated slot — the biggest khazana, but a Foundation swap → serialize it. Keep `origin`/`/part`/`/lens` as custom blocks you own.
5. **BUILD the moat** on top: reading strip↔region link, pick→comment→remember, taste signals. No harvest.

Backend: keep Track A's contract + pointers as designed; treat model-serving and the vector store as ADOPT in the deferred backend pass.

---

## Questions for Adarsh
1. **Editor swap appetite.** Adopt **BlockNote** for the document body (Path B, retires per-block TipTap) — yes, and in a dedicated slot? Or stay Path A and only harvest patterns for now? This is the single biggest call here.
2. **Panes:** adopt the already-installed **`allotment`**, or swap to **`react-resizable-panels`**? (Either kills the hand-rolled divider.)
3. **Manual marks (ties to Track A Q2):** keep a freehand-draw affordance (→ harvest Annotorious mechanics) or drop freehand and make "creator marking" = tap-an-auto-region + comment only? Decides whether B2 is a small rebuild or a delete.
4. **Primitive kit:** OK to standardize on **Radix/shadcn-style headless primitives** for button/menu/dialog/toast, replacing the ad-hoc ones? (Foundation; unblocks consistent a11y.)
5. **Backend deep pass:** want the deferred backend-harvest analysis next (model serving + vector store + serving infra options with cost/latency), or after a round of frontend harvests lands?
6. **Licence comfort:** BlockNote core is MPL-2.0 (fine closed-source; extend via plugins, don't fork). Any legal constraint I should design around (e.g. must-be-MIT-only)?

*Research + plan only — no app code touched. Core takeaway: harvest at the Foundation (editor engine, panes, palette, primitives, model-serving, vector store), harvest-a-pattern at the Structure (region overlay, feed), and build the Purpose (felt-meaning, taste graph, provenance). The editor is your biggest, cleanest harvest — and you're already in its family.*

---

### Sources
- BlockNote — block-based (Notion-style) editor on ProseMirror/TipTap; MPL-2.0 core, paid/GPL add-ons: https://github.com/TypeCellOS/BlockNote · https://www.blocknotejs.org/ · https://tiptap.dev/alternatives/blocknote-vs-tiptap
- Novel — Notion-style TipTap editor with AI autocomplete: https://github.com/steven-tey/novel
- Annotorious — MIT image-annotation library (JS/TS/React): https://annotorious.dev/
- react-image-annotate (UniversalDataTool) / Label Studio Frontend (HumanSignal) — reference labeling UX: https://github.com/UniversalDataTool/react-image-annotate · https://github.com/HumanSignal/awesome-data-labeling
- cmdk — headless command palette (Radix Dialog under the hood): https://github.com/pacocoursey/cmdk
- allotment (VS-Code-derived split views) vs react-resizable-panels: https://github.com/johnwalley/allotment · https://github.com/bvaughn/react-resizable-panels
- Radix Primitives / shadcn Resizable (headless a11y primitives): https://ui.shadcn.com/docs/components/radix/resizable
