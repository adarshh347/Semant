# Lane 5 — Writing studio (edit mode): findings

**From:** Claude Code (local, in-repo)
**Mode:** deep read + architecture proposal. **No app code was edited.**
**Scope honored:** structure only — no colour/font/spacing/copy decisions.

Traced files: `PostDetailPage.jsx` (edit branch 620–768, add paths 262–399,
AI sidebar 980–999, footer 964–976, state 40–65), `RichTextBlock.jsx` (full),
`MultiBlockEditor.jsx` (full), `PostDetailPage.css` (block rules 570–1010,
1310–1523). MultiBlockEditor usage confirmed by repo-wide grep.

---

## Current editor tree

`.edit-shell` (JSX 623) — the whole edit view, one child of the Content pane.

```
.edit-shell                                         PostDetailPage.jsx:623
├─ .edit-shell-intro                                :624   ── chrome/heading band
│  ├─ .edit-shell-heading                           :625
│  │  ├─ span.subsection-kicker  "Writing studio"   :626   (decorative label)
│  │  └─ h4  "Shape the story quietly…"             :627   (decorative sentence)
│  └─ .editor-meta                                  :629   ── 3 count pills
│     ├─ span  <words>                              :630
│     ├─ span  <min read>                           :631
│     └─ span  <blocks>                             :632
│
└─ .edit-layout   (CSS grid, 2 columns)             :636   css:570 (1.7fr / 0.8fr)
   ├─ .edit-main-column                             :637
   │  ├─ .edit-section                              :638
   │  │  ├─ .edit-section-head > h4 "Story blocks"  :639
   │  │  └─ .advanced-editor                        :642   ── the block list
   │  │     └─ RichTextBlock × N                     :644   (one per block)
   │  │
   │  └─ .editor-tools-section  "Add block"         :659   ── ADD PATH #1
   │     ├─ .subsection-heading (kicker + <p>)       :660
   │     └─ .add-block-menu                          :664
   │        ├─ button.add-block-btn  Paragraph       :665  → addBlock('paragraph')
   │        ├─ button.add-block-btn  Heading         :668  → addBlock('h1')
   │        └─ button.add-block-btn  Quote           :671  → addBlock('quote')
   │
   └─ .edit-side-column  (sticky rail)              :678
      ├─ .sutradhar-composer                        :679   ── ADD PATH #2
      │  ├─ .composer-head (heading + <p>)           :680
      │  ├─ .composer-row  [Draft from image]        :687  → draftFromImage()
      │  ├─ .composer-row  [input + Write]           :698  → writeFromPrompt()
      │  ├─ p.composer-hint                          :716
      │  └─ p.composer-error (conditional)           :717
      │
      └─ .tags-edit-section                         :720
         ├─ .edit-section-head > h4 "Tags"          :721
         └─ .tags-card                              :724
            ├─ .tags-container (chips + remove)      :725
            ├─ .popular-tags-row (conditional)       :739
            └─ .tag-input-row (input + Add)          :754
```

Save/Cancel is **not** inside `.edit-shell`. `.edit-actions` (JSX 966) is a
sibling of the whole content area at pane level — a true pane footer. Good;
leave it structurally where it is.

### Inside a single `RichTextBlock` (RichTextBlock.jsx)

Each block mounts **its own TipTap editor instance** (`useEditor`, line 66) and
renders three stacked layers:

```
.rich-text-block                                    RichTextBlock.jsx:83
├─ MenuBar → .block-toolbar                          :11   ── ALWAYS-ON, per block
│  ├─ toolbar-btn  H1        :12
│  ├─ toolbar-btn  Paragraph :20
│  ├─ .toolbar-divider       :28
│  ├─ toolbar-btn  Bold      :29
│  ├─ toolbar-btn  Italic    :37
│  ├─ toolbar-btn  Underline :45
│  └─ toolbar-btn  Quote     :53
├─ EditorContent            :86
└─ .block-controls          :87                       ── ALWAYS-ON, per block
   ├─ .block-actions-left    :88
   │  ├─ .block-move-group    :90   → Move up :91 / Move down :100  (2 btns)
   │  └─ .color-picker        :111  → 6 swatches (colorOptions :81)  (6 btns)
   └─ .delete-block-btn       :123  (1 btn)
```

**Controls that multiply per block:** 6 format buttons (+1 divider) + 2 move
buttons + 6 colour swatches + 1 delete = **15 interactive controls per block**.
At the "ten blocks" case in the map that is **~150 controls** and **10
independent TipTap editor instances** stacked down one column. This is the core
architectural weight of the lane: the toolbar is bound to the block because the
*editor* is bound to the block.

---

## Multiplication table

| Control | Rendered per block today? | Root cause | Proposed single/shared home |
|---|---|---|---|
| Format toolbar (H1, P, Bold, Italic, Underline, Quote) | **Yes** — `.block-toolbar`, always on, ×N (RichTextBlock.jsx:11) | Each block owns a TipTap instance; MenuBar binds to it | **One** shared toolbar at the top of the canvas, acting on the *active* block's editor. Optionally a bubble toolbar on selection. Either way: 1 instance, not N. |
| Colour swatches (6) | **Yes** — `.color-picker`, always on, ×N (RichTextBlock.jsx:111) | Same per-block binding | Move off the block. A single on-demand colour control (in the shared toolbar or the block's overflow menu) that targets the active block. Capability preserved. |
| Move up / Move down | **Yes** — `.block-move-group`, always on, ×N (RichTextBlock.jsx:90) | Reorder handled per block via `moveBlock` (PostDetailPage.jsx:321) | Replace with **one** hover/drag affordance per block (drag handle in the block gutter) or a single per-block overflow menu. Not two always-visible arrow buttons. |
| Delete | **Yes** — `.delete-block-btn`, always on, ×N (RichTextBlock.jsx:123) | Per-block button | Fold into the same per-block overflow (⋯) menu / hover control. One affordance, revealed on hover/active. |
| TipTap editor instance | **Yes** — `useEditor` ×N (RichTextBlock.jsx:66) | Structural: one editor per block | Structural keep (needed for reorder), **but** register each block's editor with the parent so a single toolbar can target the focused one (see active-block model below). |
| "Add block" type buttons | Once (not per block) — `.add-block-menu` (JSX 664) | — | Converge with insertion API (see add-content map). |

---

## Add-content map (the three insertion paths)

All three paths end at the **same operation: append a block to the end of
`editedBlocks`.** None inserts at a position; none targets the active block.

| # | Entry point | Handler | Where it lands | Content source |
|---|---|---|---|---|
| 1 | `.add-block-menu` buttons — Paragraph / Heading / Quote (JSX 665–673) | `addBlock(type)` — PostDetailPage.jsx:274 | `setEditedBlocks(cur => [...cur, newBlock])` — **append** | Empty, seeded HTML (`<h1>`/`<blockquote>`/`''`) |
| 2 | `.sutradhar-composer` — "Draft from image" / "Write" (JSX 690, 709) | `draftFromImage()` :362 and `writeFromPrompt()` :380 | both `setEditedBlocks(b => [...b, …])` — **append** | AI paragraph from `epicService` |
| 3 | AI sidebar `ChatbotPanel` — `onAddBlock` (JSX 987) | `handleSuggestionSelect(suggestion)` :303 | `setEditedBlocks([...editedBlocks, newBlock])` — **append** | AI chat suggestion, as paragraph |

**Convergence recommendation — one insertion pathway, three sources.**

- Keep all three *sources* — they are genuinely different (manual scaffold, quick
  AI compose, full AI conversation). Do **not** remove any capability.
- Converge the *mechanism*: introduce a single `insertBlock(block, atIndex)`
  helper (replacing the three ad-hoc `[...blocks, x]` spreads). All three sources
  call it. This immediately buys position-aware insertion — a block can land at
  the caret / after the active block instead of always at the bottom, which is
  the main UX defect of the current "always append" design.
- Converge the *manual* surface: Path #1 ("Add block" section) is the natural
  home for an inline insertion affordance (a `+` between blocks / at the end)
  rather than a fixed section at the bottom of the main column. The Sutradhar
  composer (Path #2) can live as one option inside that same insertion surface
  (blank / heading / quote / **draft-with-AI**), so manual and quick-AI adds
  share one place.
- Keep the AI sidebar (Path #3) as a **separate** full assistant — it does more
  than insert — but route its insert through the same `insertBlock` API so all
  three obey one insertion model.

---

## Proposed editor structure (leanest tree)

Single column. One shared toolbar. Blocks carry no always-on furniture. Side
tools stop being a permanent second column in a ~45%-wide pane.

```
.edit-shell
├─ (meta counts — words / min / blocks) → move OUT of the body into the pane
│   chrome / topbar. They are status, not content. (see Q2)
│
├─ .edit-toolbar   ── ONE shared, sticky formatting bar
│     H1 · P · Quote · | · Bold · Italic · Underline · | · Colour ▾
│     acts on the ACTIVE block's editor (state below). Optionally a
│     selection/bubble variant instead of/along with the fixed bar.
│
├─ .edit-canvas   ── the block list, single column
│     └─ block row × N
│          ├─ [gutter] drag handle + ⋯ overflow (move / colour / delete)
│          │            revealed on hover or when active — NOT always on
│          └─ EditorContent   (block's own TipTap instance, focus-reported up)
│          └─ inline "+" insertion affordance between/after blocks (Path #1/#2)
│
└─ side tools → collapsible, not a fixed rail:
      ├─ Sutradhar composer  → an option inside the "+" insertion surface,
      │                         or a small drawer toggled from the toolbar
      └─ Tags                → pane-level metadata footer / collapsible panel,
                               ONE home shared with view mode (defer exact
                               placement to Lane 4 — flagged as the cross-lane
                               "tags have no single home" issue)
```

**Active-block model (the one real state change this requires):**

- `selectedBlockId` state **already exists** (PostDetailPage.jsx:50) but is only
  used for view-mode highlights (set at :126). Reuse the same idea for edit mode:
  hold an `activeBlockId` + a ref/map of block-id → editor instance in
  PostDetailPage.
- `RichTextBlock` gains an `onFocus(block.id, editor)` callback; on focus it
  registers its editor and sets `activeBlockId`.
- The shared `.edit-toolbar` reads the active editor from that map and calls
  `activeEditor.chain().focus().toggle…().run()` — the exact chains that live in
  MenuBar today (RichTextBlock.jsx:12–60), lifted up one level.
- Colour: same target — colour control calls `handleBlockColorChange(activeBlockId, …)`
  (handler already exists at :268). Move/delete stay per-block but move into the
  hover/overflow affordance instead of an always-on row.

Net structural result: **N always-on toolbars → 1**; **N×6 always-on swatches →
1 on-demand control**; **N×(2 move + 1 delete) always-on → 1 hover affordance per
block**; **3 append-only add paths → 1 position-aware insertion API with 3
sources**; **2-column narrow-pane layout → 1 column + collapsible tools.** No
capability removed.

---

## Dead-code note — `MultiBlockEditor.jsx`

**Confirmed dead.** Repo-wide grep for `MultiBlockEditor` returns only its own
definition/export (`MultiBlockEditor.jsx:1,4,51`) — **zero imports** anywhere in
`src/`. It is a legacy `<textarea>`-based block editor (add heading/paragraph/
quote, delete) fully superseded by `RichTextBlock` + TipTap. It also declares its
own local `addBlock`/`deleteBlock`, unrelated to the live handlers in
PostDetailPage. **Recommendation: delete the file.** (Deletion is a build prompt,
not this research round — flagging only.)

Note: the CSS classes it uses (`.multi-block-editor`, `.text-block`) and the
`.text-block-item[data-block-id]` selector the highlight code queries at
PostDetailPage.jsx:120 are a separate, view-mode concern — do not conflate them
with the dead component when it's removed.

---

## Off-theme flag (for a later, non-architecture lane)

Per the constraint, noting without acting: the 6 colour swatches are hardcoded
hex (`RichTextBlock.jsx:81` — `#fef3c7`, `#dcfce7`, …) and the block-color guard
compares against a literal `'#2a2a2a'` (`:84`). These bypass the token system.
Flagging for the colour lane, not this one.

---

## Questions for Adarsh

1. **Toolbar shape.** For the single shared formatting toolbar, do you want a
   **fixed bar at the top of the canvas** (always visible, targets the active
   block) or a **bubble toolbar that appears only on text selection** (less
   chrome, but hidden until you select)? Or both? This decides how much the
   active-block state has to do.

2. **Where do the meta counts (words / min / blocks) belong?** I want to lift
   them out of the edit body into the pane chrome (they're status, not content).
   Is the post topbar / a thin status line acceptable, or do you want them to
   stay a visible row inside the editor?

3. **Two AI surfaces — keep both?** Path #2 (Sutradhar composer: draft-from-image
   + write-from-prompt) and Path #3 (full AI sidebar chat) overlap. Fold the
   composer into the inline insertion menu and keep the sidebar as the "deep"
   assistant? Or keep the composer as its own visible surface in edit mode?

4. **Tags home.** Tags live in the side column in edit mode but at the pane
   bottom in view mode (the Lane 4 "no single home" issue). Do you want Lane 5 to
   assume a single shared tags home and just reference it, or leave tags exactly
   where they are for now and let Lane 4 own that decision?

5. **Per-block controls affordance.** Preference for how move/delete/colour are
   revealed per block: a **drag handle + ⋯ overflow menu** in a left gutter, or a
   **hover toolbar** on the block? Both remove the always-on row; the choice
   affects the block DOM.

6. **Insertion position.** Confirm you want the new single `insertBlock` to be
   **position-aware** (insert after the active block / at caret). Today all three
   paths only append to the end — moving to positional insert is a small behaviour
   change, not just a refactor, so I want explicit sign-off before a build prompt
   assumes it.

Stopping here per the lane rules — not moving to another lane.
