# BlockNote — adoption & migration plan for Drishya's writing studio

**Mode:** research + plan. No app code changed.
**Question answered:** what BlockNote brings, whether it's the best OSS pick on **features / aesthetics / latency**, and the concrete migration.
**Grounding:** current editor read @ `0eb711e` — `RichTextBlock.jsx` (one TipTap editor per block), `slashCommand.jsx` (STRUCTURE + AI + REF `/part` `/lens` via TipTap Suggestion + a `RegionRef` mark), `PostDetailPage.jsx` block model (`text_blocks: {id, type, content:HTML, origin:'human'|'sutradhar', color}`, hand-built `insertBlock/makeBlock`, drag-reorder, per-block gutter). BlockNote features/licence web-verified July 2026 (sources at end).

---

## TL;DR verdict

**Yes — BlockNote is the best OSS pick for *our* situation, on all three axes, with one honest caveat.**
- **Features:** it ships, out of the box, ~everything we hand-built or planned — blocks, slash menu, drag handle + side menu, formatting/bubble toolbar, tables/media, **custom blocks as React components**, and a clean block API. Best-in-class for the *Notion-style block editor* shape specifically.
- **Aesthetics:** ships a polished Notion-like UI, fully themeable via **CSS variables** to our tokens — best look-out-of-the-box of the candidates (Lexical/Plate are unstyled toolkits you design yourself).
- **Latency:** it's **one ProseMirror document**, which directly fixes our real performance problem — today we mount **N TipTap editors, one per block** (Path A). That N→1 change is a bigger latency win than any engine micro-benchmark.
- **Caveat:** Lexical (Meta) has the best *raw-engine* performance at extreme document scale, and if we wanted to leave the ProseMirror family it'd be the pick. We don't — our docs are editorial-length, and Lexical costs ~weeks to rebuild the block UX BlockNote gives free while throwing away our TipTap investment. So BlockNote is the right *trade*, not a compromise.

---

## 1. What BlockNote brings (mapped to what we currently hand-maintain)

| Capability | Today (hand-built) | BlockNote gives | Net |
|---|---|---|---|
| **Block model** | `text_blocks[]` + `makeBlock`/`insertBlock` in `PostDetailPage` | a real block document + `insertBlocks(blocks, ref, placement)` | delete our block plumbing |
| **One editor vs many** | **N TipTap editors** (`RichTextBlock` per block) | **one** ProseMirror document | the core latency + consistency win |
| **Slash menu** | `slashCommand.jsx` (211 LOC, Suggestion + floating-ui) | extensible slash menu API (add custom items) | port items, drop the plumbing |
| **Drag reorder + block gutter** | hand-built drag handlers + `⠿`/⋯ gutter | **side menu**: `＋` + drag handle (⠿) + drag-handle menu, free | delete our gutter/drag code |
| **Formatting / bubble toolbar** | TipTap `BubbleMenu` in `RichTextBlock` | formatting toolbar (bubble or static) | adopt |
| **Block types** | paragraph/heading/quote via chained transforms | paragraph, headings, lists, code, **tables, images, video, audio** | more, for free |
| **Block background colour** | 6 hardcoded hex swatches (off-theme, flagged) | block props incl. background colour | re-theme via props to tokens |
| **`/part` (a region), `/lens` (a reading)** | REF commands + `RegionRef` mark (partly built) | **custom blocks / inline content** (React components) | rebuild as custom blocks — cleaner, first-class |
| **`origin: human\|sutradhar`** | field on each block + `data-origin` hook | **custom block prop** we define | keep ours, as a block attribute |
| **Inline AI** | slash AI → non-streaming endpoints → `sutradhar` block | block-insertion API + AI SDK seam (for streaming later) | build on our endpoints (not the paid AI module) |
| **Collaboration / comments** | none | Yjs collab + comments (liberally licensed) | future two-sided/multiplayer option |

**The point:** most of `RichTextBlock.jsx`, `slashCommand.jsx`, and the block/drag/gutter code in `PostDetailPage` becomes *deletable*. What we keep is the moat — `/part`, `/lens`, `origin/actor` — now expressed as **custom blocks we own** through BlockNote's schema API.

---

## 2. Is it the best? — honest comparison

| Editor | Engine | Notion-block UX out of box | Aesthetics OOTB | Raw latency | Same family as us (TipTap)? | Cost to reach our UX |
|---|---|---|---|---|---|---|
| **BlockNote** | ProseMirror/TipTap | **yes** (slash, drag, side menu, custom blocks) | **polished, themeable via CSS vars** | one PM doc; great for editorial length | **yes** (migration, not rewrite) | **~1–2 hr to stand up**; days to port our bits |
| **Lexical** (Meta) | own (immutable state) | no (toolkit; build blocks yourself) | unstyled | **best at extreme scale** | no (leaves ProseMirror) | ~weeks (Lexical + dnd-kit custom build) |
| **Plate** | Slate | partial (plugins, headless) | unstyled | good | no (Slate family) | weeks |
| **Novel** | TipTap | partial (Notion-ish + AI ghost-text) | opinionated | one PM doc | yes | medium — but thinner than BlockNote |
| **TipTap raw (today, Path A)** | ProseMirror | we hand-build all of it | our CSS | **worst here** (N editors) | yes | ongoing maintenance tax |
| **Editor.js** | own (JSON blocks) | yes (blocks) | plain | ok | no | medium, but weaker rich-text/marks |

**Reading it:**
- **Best block UX + aesthetics + DX for our shape → BlockNote**, decisively. It's the only one that gives the Notion block experience *and* stays in our TipTap family *and* ships a themeable look.
- **Best raw performance → Lexical**, but that edge only matters at document scales we don't have, and the price is weeks of rebuilding block UX + leaving ProseMirror. Not worth it here.
- **Novel** is the runner-up *within* our family — lighter, great inline-AI UX — but we'd hand-build the block/drag/custom-block layer BlockNote gives free. So: **adopt BlockNote for the body, harvest Novel's ghost-text for inline AI.**

---

## 3. The latency truth (why BlockNote is faster *for us* regardless of benchmarks)

Our current latency cost isn't the engine — it's **Path A: one `useEditor()` TipTap/ProseMirror instance per block**. A story with 20 blocks mounts 20 editors, 20 sets of extensions, 20 Suggestion plugins, 20 bubble menus. That's memory + input-latency + inconsistent selection across blocks. **BlockNote collapses this to a single document with one plugin stack** — the N→1 win. So even though Lexical may edge ProseMirror in synthetic benchmarks, moving *from our Path A to BlockNote* is a large, concrete latency improvement, and it's the change actually available to us. (This is also exactly what the `decisions-log` meant by "Path A first, plan Path B" — BlockNote *is* the Path B.)

---

## 4. Aesthetics / styling path (we are NOT on Tailwind — important)

BlockNote themes via **CSS variables** (`bn-` prefixed classes; light/dark themes built in). It ships three flavours: **Mantine** (self-contained styling), **shadcn** (expects Tailwind), and **headless**.

- **We use plain CSS + design tokens, no Tailwind** → **do not use `@blocknote/shadcn`.** Use **`@blocknote/mantine`** (self-contained, then override its CSS variables to our `--accent`/`--surface`/`--radius`/`--font` tokens) **or headless** if we want full control of the chrome. Recommendation: **Mantine variant, themed to our tokens** — fastest to a coherent look; go headless only if the Mantine chrome fights our grammar.
- Our token system becomes the theme source: map `bn-colors-*` / editor CSS vars → our tokens once, and BlockNote inherits our light/dark automatically.

---

## 5. What stays ours (the moat — do not hand to the library)
- **`/part` and `/lens`** → BlockNote **custom blocks** (or inline content) rendered by our React components, pulling from `Region` / `local_context.aletheia`. This is a *cleaner* home than the current `RegionRef` mark.
- **`origin` / `actor` provenance** → a **custom block prop** we define on every block; we control serialization so provenance is never hostage to BlockNote's format.
- **Inline AI** → build on **our** endpoints (`/chat/vision`, `/rewrite/vision`, `/flow/expand-node`) via BlockNote's block-insertion API. **Avoid `@blocknote/xl-ai`** (the AI module is in the paid/GPL "advanced" tier — closed-source use needs a subscription). Harvest Novel's ghost-text *interaction*, wire it to our streaming endpoint in Phase 3.
- **Highlights ↔ block links** (`Highlight.block_id` ↔ `data-block-id`) and **`Region.block_id`** must survive the migration (see §6 Phase 1).

---

## 6. Migration plan (strangler, not big-bang)

**Phase 0 — Spike (isolated).** Stand up BlockNote (`@blocknote/core` + `@blocknote/react` + `@blocknote/mantine`) in a lab route like the existing `RegionSurfaceLab`. Prove: our tokens theme it; a custom block renders; slash items register. ~1–2 hr. No `PostDetailPage` edits.

**Phase 1 — The converter (the real work).** Build `text_blocks (HTML + id + origin + color)` ⇄ BlockNote document:
- import: HTML → BlockNote blocks (`tryParseHTMLToBlocks`), **preserving each block's `id`** so `Highlight.block_id` and `Region.block_id` links keep resolving; carry `origin`/`color` into block props.
- export on save: BlockNote → our `text_blocks` shape (`blocksToHTMLLossy` or store BlockNote JSON alongside). **Decide the storage format** (keep HTML for back-compat vs store BlockNote JSON — Q1). This phase protects the highlight/region cross-links; get it right before touching the UI.

**Phase 2 — Swap the body (dedicated, serialized slot).** Replace the `editedBlocks.map(RichTextBlock)` render with one `<BlockNoteView>`. Port slash items (STRUCTURE/AI/REF) to BlockNote slash items; adopt its formatting toolbar + side menu; **delete** the hand-built gutter/drag/`insertBlock`/`makeBlock`. Because this edits `PostDetailPage.jsx` — the file the live Track-D/Drishya build also touches — **serialize it: `git pull`, no concurrent lane on that file, land as its own commit(s).**

**Phase 3 — Custom blocks for the moat.** Implement `/part` and `/lens` as BlockNote custom blocks; add `origin/actor` as block props with our serialization. Retire the `RegionRef` TipTap mark.

**Phase 4 — Inline AI.** Wire slash-AI verbs to our endpoints via BlockNote's insertion API (non-streaming first), then harvest Novel's ghost-text for streaming (Phase 3 of the AI roadmap). Not `xl-ai`.

**Phase 5 — Delete Path A.** Remove `RichTextBlock.jsx`, `TipTapEditor.jsx`, `slashCommand.jsx`, `SlashMenu.jsx`, `regionRef.js`, and the block/drag state in `PostDetailPage`. Confirm no other importers. This is the payoff: net LOC deleted.

---

## 7. Risks & gotchas
- **Data migration is the crux, not the UI.** HTML-per-block → BlockNote doc must **preserve block ids** or highlights/region links break. Phase 1 is the risky part; test with real posts (highlights + region `block_id`).
- **Serialization ownership.** Keep `origin/actor/block_id` as **our** block attributes; don't let BlockNote's JSON be the only source of provenance.
- **Licence line.** Core is MPL-2.0 (fine, closed-source OK; extend via API, don't fork their files). **The AI module (`xl-ai`), exports, multi-column are the paid/GPL tier** — build inline AI ourselves; avoid those modules.
- **No Tailwind** → Mantine or headless variant, not shadcn.
- **Serialize the `PostDetailPage` edit** against the active Drishya/Track-D build (shared file).
- **Custom-block API is BlockNote's schema, not raw TipTap** — `/part`/`/lens` must be declared through BlockNote's schema, a small relearn from the current Suggestion/mark approach.

---

## Questions for Adarsh
1. **Storage format:** keep persisting `text_blocks` as HTML (max back-compat; convert on load/save) or migrate storage to **BlockNote JSON** (cleaner, but a one-time data migration + touches the backend `TextBlock` shape)? I lean keep-HTML first, revisit later.
2. **Styling variant:** **Mantine themed to our tokens** (fastest coherent look) or **headless** (full control, more work)? I lean Mantine first.
3. **Slot & sequencing:** OK to run the BlockNote swap as its own serialized slot *after* the current Visual-pane (Track D) build settles, since both edit `PostDetailPage`?
4. **Inline AI:** confirm we build inline AI on our existing endpoints (not `@blocknote/xl-ai`) to stay clear of the paid tier?
5. **Spike first?** Want me to spec the Phase 0 lab spike in detail (exact packages, a token-theme mapping, one custom `/part` block) as the next artifact?

*Research + plan only — no app code touched. Verdict: BlockNote is the best OSS fit on features, aesthetics, and (for our N-editor reality) latency; adopt it for the document body, keep `/part`/`/lens`/`origin` as custom blocks we own, build inline AI on our endpoints, and migrate via a converter-first strangler with the data-model step (block-id preservation) as the real risk.*

---
### Sources
- BlockNote — features (blocks, side menu, slash, tables, custom blocks): https://www.blocknotejs.org/docs/features/blocks · https://www.blocknotejs.org/docs/react/components/side-menu · https://www.blocknotejs.org/docs/features/custom-schemas/custom-blocks
- BlockNote — theming via CSS variables; Mantine vs shadcn vs headless: https://www.blocknotejs.org/docs/styling-theming/themes · https://www.blocknotejs.org/docs/getting-started/mantine · https://www.blocknotejs.org/docs/getting-started/shadcn
- BlockNote vs Lexical vs Plate (architecture, performance, setup time): https://velt.dev/blog/best-rich-text-editors-react-comparison · https://eddyter.com/blogs/build-notion-style-block-editor-react-2026
- Lexical (Meta; immutable state, performance): https://lexical.dev/
