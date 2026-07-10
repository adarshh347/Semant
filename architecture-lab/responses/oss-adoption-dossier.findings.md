# Open-source adoption dossier — the picks, evaluated

**Mode:** research only. No app code changed.
**Companion to:** `frontend-subsection-and-harvest-map.findings.md` (which said *what* to adopt/harvest/build). This doc goes deep on *each pick*: what it is, maturity, licence, how it fits **our** contracts (`Region`/`actor`/`block_id`/`origin`, TipTap, tokens), the integration path, and the gotchas.
**Grounding:** current deps read from `frontend/package.json` @ working tree `0eb711e`; licences/versions web-verified July 2026 (sources at end).

## Where we are today (so adoption is judged against reality)
Current frontend deps are deliberately thin: **React 19.1, TipTap 3 (react/starter-kit/suggestion/placeholder/floating-menu), `@floating-ui/dom`, `allotment@1.20.4` (installed, still unused), axios, lucide-react, react-router 7.** No editor-framework, no command palette, no state/data library, no virtualization. Everything else is hand-rolled — including the new `RegionLightbox` zoom/pan (hand-written CSS-transform math) and the ~1,200-line `PostDetailPage` god component. **That's the backdrop: we keep re-implementing solved Foundation/Behaviour code.** Each pick below is scored on whether adopting it retires hand-rolled code we shouldn't own.

Verdict legend: **ADOPT** (take the dep) · **HARVEST** (lift mechanism, keep our data) · **DEFER** (right call, not yet).

---

## Tier 1 — adopt to kill hand-rolled Foundation

### 1. BlockNote — the editor body (Path B, pre-built)  · **ADOPT (flagship)**
- **What:** a Notion-style, block-based React editor **built on ProseMirror + TipTap** — the exact family we're already in. Ships blocks, drag-handle, slash menu, and selection toolbar out of the box.
- **Maturity:** actively developed (2025–26), first-class TypeScript, used widely; Liveblocks/PartyKit integrations exist.
- **Licence:** **MPL-2.0 core** — free in commercial *and* closed-source apps; the only obligation is that edits to *their* files be published. Practically: **extend via the plugin / custom-block API, never fork their source.** Advanced add-ons (AI, PDF/DOCX export, multi-column) are free under GPL for OSS but **paid for closed-source** — budget or avoid those specific modules.
- **Fit to us (high):** BlockNote's block document *is* the "Path B single-document editor" the `decisions-log` flagged as the endgame for slash/inline-AI/drag-reorder. Its block API (`insertBlocks(blocks, ref, placement)`) is our locked `insertBlock(block, atIndex)` decision, already solved. **Custom blocks are React components** — so `/part` (an annotated region) and `/lens` (an Aletheia reading) become first-class custom blocks, and `origin`/`actor` live as block attributes **we own**. AI is via the Vercel AI SDK with RAG/tools — the seam Track C's context-pack plugs into.
- **Integration path:** migrate the document body from N-TipTap-editors-per-block (Path A) to one BlockNote editor; port slash items to BlockNote slash items; keep our marks. **This is a Foundation swap → dedicated slot, serialized against the live Track-D/Drishya edits to `PostDetailPage`.**
- **Gotchas:** (1) persist BlockNote JSON but keep `origin/actor/block_id` as **our** block attrs so provenance isn't hostage to the lib. (2) Avoid the paid AI/export modules — wire our own via the AI SDK seam. (3) It owns the ProseMirror schema — our custom blocks must be declared through its schema API, not raw TipTap extensions.

### 2. react-resizable-panels — the split shell  · **ADOPT (replace allotment)**
- **What:** resizable panel primitive by Brian Vaughn (React DevTools author): `PanelGroup` / `Panel` / `PanelResizeHandle`.
- **Maturity:** v3.x, **supports React 18 & 19**, active.
- **Licence:** MIT.
- **Fit (high):** treats **accessibility (ARIA live announcements, keyboard resize) and persistence (`autoSaveId` → localStorage) as first-class** — exactly the Lane 2 gaps (no keyboard/ARIA on our hand-rolled divider; width not persisted). Also gives collapse/snap + double-click-reset — the "focus the writing" preset Lane 2 wants — for free.
- **Integration path:** replace the hand-rolled `.split-divider` + document mouse listeners + `leftPanelWidth` state with a `PanelGroup`; keep the 20–80% clamp as `minSize/maxSize`; `autoSaveId` persists the ratio.
- **vs allotment (currently installed, unused):** allotment gives the exact VS-Code look and heavier nested-pane polish, but it's v1.x and heavier. **Recommendation: adopt react-resizable-panels and drop the unused `allotment` dep** — better a11y/persistence story, lighter, React-19-explicit. (If you specifically want the VS-Code feel, keep allotment instead — but *use* it or remove it.)
- **Gotcha:** it manages sizes internally; our `selectedRegionId`/edit-narrow preset must drive it via its imperative API, not a competing state.

### 3. cmdk — the command palette (net-new spine)  · **ADOPT**
- **What:** headless ⌘K command-menu primitive; fuzzy filter + keyboard nav; `Command.Dialog` wraps a Radix dialog (focus-trap + Esc-close free).
- **Maturity:** tens of millions of weekly downloads (shadcn's Command wraps it); well-maintained. Uses React 18 hooks (`useId`, `useSyncExternalStore`) — **fine on our React 19**.
- **Licence:** MIT.
- **Fit (high):** a ⌘K that runs the *same verbs as `/`* (jump to any image, run `/draft`/`/lens`, switch lens, toggle regions) is the Linear/Raycast "instant, keyboard-first" feel the rubric names under Behaviour — and it unifies navigation + everyday AI in one primitive.
- **Integration path:** mount `Command.Dialog` at the app root; feed it a registry of actions (routes + slash verbs). Start with navigation, grow into AI verbs.
- **Gotcha:** headless = we style it (good — it inherits our tokens); keep the action registry declarative so palette and slash share one source.

### 4. Radix Primitives (shadcn recipes) — the primitive kit  · **ADOPT (patterns)**
- **What:** headless, accessible primitives — Dialog, DropdownMenu, Popover, Tooltip, Toast — with focus-trap, ARIA roles, Esc/outside-click handled once.
- **Licence:** MIT.
- **Fit (high):** the rubric's Foundation gap 1.2 ("primitive vs one-off") — today the same control differs across the app (modals, the ⋯ overflow, tooltips all hand-rolled). Radix builds each once; reuse everywhere. BlockNote and cmdk already sit on Radix, so this is consistent.
- **Integration path:** replace hand-rolled modal/menu/tooltip/toast incrementally; adopt the shadcn *pattern* (copy-in components) rather than a heavy design-system dep.
- **Gotcha:** style via our tokens, not shadcn's default Tailwind theme, or you import a second visual language.

---

## Tier 2 — harvest the mechanism, keep our data

### 5. Novel — inline-AI writing UX  · **HARVEST**
- **What:** Notion-style TipTap editor with **AI autocomplete (ghost-text, Tab-to-accept)** baked in. MIT.
- **Fit:** even if the body is BlockNote, Novel's **inline-AI interaction** is the reference for our A4 (ghost-text continuation wired to Track C's context pack, not a generic completion). Harvest the interaction pattern, not the whole editor.
- **Gotcha:** don't run two editor frameworks — take the UX, implement on BlockNote/TipTap.

### 6. Annotorious v3 — freehand draw/edit mechanics  · **HARVEST (only if freehand survives)**
- **What:** MIT image-annotation library (JS/TS/React): draw, edit vertices, resize handles.
- **Fit:** *mechanics only.* Its store is W3C Web Annotation, **not** our normalized `Region`. If Track A Q2 keeps a freehand "creator mark," harvest the draw/edit interaction and translate to `{x,y,w,h}` 0–1 + `actor="creator"`. If freehand is dropped (mark = tap-an-auto-region + comment), skip it entirely.
- **Gotcha:** never adopt its data model — that would capture the moat's contract.

### 7. dnd-kit — block/region reorder  · **HARVEST / free-with-BlockNote**
- **What:** `@dnd-kit/react` (0.5.x, actively maintained) — modern, accessible drag-and-drop.
- **Fit:** if you adopt BlockNote, block reorder comes free (skip). Use dnd-kit only for reorder *outside* the editor (e.g. reordering regions/parts) if that surfaces.
- **Licence:** MIT.

### 8. react-zoom-pan-pinch — deep-zoom close-reading  · **HARVEST / optional ADOPT**
- **What:** widely-used zoom/pan/pinch lib (`TransformWrapper`/`TransformComponent`) for `<img>`/`<div>`.
- **Fit:** we **already hand-rolled** zoom/pan in `RegionLightbox` (CSS-transform math). If that stays coupled to the region overlay and works, keep it. But if deep-zoom close-reading grows (zoom to a cuff/hem — "the fold of the fabric"), this lib retires the hand-rolled transform math and adds pinch/touch + bounds for free. See the deep-zoom *use-case* in the feature-map doc.
- **Gotcha:** the overlay SVG must transform in lockstep with the image — the current hand-rolled code already solves this; adopting means re-proving that coupling.

---

## Tier 3 — new Foundation the app doesn't have yet (adopt when the pain lands)

### 9. TanStack Query — server-state  · **ADOPT (high-leverage)**
- **What:** async server-state: caching, request dedup, background refetch, **optimistic updates**, retries. v5, React 19-ready. MIT.
- **Fit (high):** the whole app is hand-written `axios`/`fetch` + `useState` against FastAPI. TanStack Query gives **optimistic updates** (rubric 3.1 — "feels instant"), cache/dedup (perceived speed 3.3), and background freshness — replacing dozens of ad-hoc loading booleans. It's the cleanest single win for "feels fast/alive."
- **Boundary:** server state only. UI flags (modal open, selected tab) stay in `useState`/Zustand.
- **Gotcha:** adopt incrementally per-endpoint; don't boil the ocean.

### 10. Zustand — client-state  · **ADOPT (targeted)**
- **What:** tiny client-state store. MIT.
- **Fit:** the `PostDetailPage` god component (~1,200 LOC) holds ~30 `useState`s. Zustand is the clean home for cross-pane client state — Lane 2's shared `selectedRegionId`, edit-mode flags, active tab — decoupling panes without prop-drilling. Pairs with TanStack Query (server) per the standard split.
- **Gotcha:** keep server data in Query, UI state in Zustand; don't duplicate.

### 11. TanStack Virtual — list virtualization  · **DEFER until volume lands**
- **What:** headless virtualization (render only visible rows). MIT.
- **Fit:** two real future hotspots — the **feed/gallery** (E1) and the **parts panel** once Fashionpedia yields dozens of regions per image (B3/B4). Virtualizing prevents the layout thrash the rubric flags (3.3). Not needed today; adopt when the parts list or feed gets long.

---

## Adoption order (foundation-first, lowest-risk first)
1. **cmdk + Radix primitives** — cheap, no contract risk, immediate a11y/consistency win.
2. **react-resizable-panels** — one afternoon; kills the divider a11y gap; delete unused allotment.
3. **TanStack Query** — incremental per-endpoint; biggest "feels alive" win.
4. **Zustand** — as you decompose the god component.
5. **BlockNote** — the flagship, but a Foundation swap → dedicated, serialized slot.
6. **Harvest** Novel (inline-AI UX), Annotorious (only if freehand stays), react-zoom-pan-pinch (if deep-zoom grows). **Virtual** when lists get long.

## Licence summary (for the record)
MIT: react-resizable-panels, cmdk, Radix, Novel, Annotorious, dnd-kit, react-zoom-pan-pinch, TanStack Query/Virtual, Zustand. **MPL-2.0: BlockNote core** (fine closed-source; extend via plugins; paid AI/export modules for closed-source — avoid or budget).

---
### Sources
- BlockNote — repo / docs / custom blocks / licence: https://github.com/TypeCellOS/BlockNote · https://www.blocknotejs.org/docs/features/custom-schemas/custom-blocks · https://tiptap.dev/alternatives/blocknote-vs-tiptap
- react-resizable-panels (React 18/19, a11y, autoSaveId persistence): https://github.com/bvaughn/react-resizable-panels · https://www.pkgpulse.com/guides/react-resizable-panels-vs-split-js-vs-allotment-2026
- cmdk (headless, Radix dialog under the hood): https://github.com/pacocoursey/cmdk
- Radix Primitives / shadcn: https://ui.shadcn.com/docs/components/radix/resizable
- Novel (TipTap + AI autocomplete): https://github.com/steven-tey/novel
- Annotorious (MIT image annotation): https://annotorious.dev/
- dnd-kit (@dnd-kit/react, maintained): https://github.com/clauderic/dnd-kit
- react-zoom-pan-pinch: https://github.com/BetterTyped/react-zoom-pan-pinch
- TanStack Query (server vs client state): https://tanstack.com/query/latest · https://tanstack.com/query/v4/docs/framework/react/guides/does-this-replace-client-state
- TanStack Virtual: https://tanstack.com/virtual/latest
