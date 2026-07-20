# Lane 4 — Content pane, view mode: findings

**From:** Claude Code (local, in-repo)
**Mode:** deep read + architecture proposal. No app code changed.
**Lens:** Purpose → Structure → (Surface deferred). Drishya's job: *turn one image into meaning — read, marked, written — while the reader can always trace who saw what and who wrote what.*

Line refs are against the **current** `PostDetailPage.jsx` (1090 lines) — the prompt's numbers predate the Lane 5 second-layer build and have shifted.

---

## 1. Current view-mode tree (with refs)

Everything below lives under the Content panel. `.content-area` (`PostDetailPage.jsx:651`, CSS `PostDetailPage.css:298`) is the scroll container — `flex:1; overflow-y:auto; max-width:56rem; margin:0 auto`.

```
.content-area                                    (651)  scroll container, centered 56rem
│
├── .source-account-section        (654)  ⚠ renders in ALL tabs + both modes
│     img.source-account-avatar     (656)
│     "From @handle · display_name" (658)
│     Link "Open persona →"         (662)
│     — CSS 379: already a compact meta ROW (caption size, border-bottom). Not a heavy band.
│
├── .epic-badge-section            (670)  ⚠ renders in ALL tabs + both modes
│     h5 "Part of Epic"             (671)
│     Link(s) epic.title            (672)
│     — CSS 405: still a full band with its own heading + bottom border.
│
└── { activeRightTab === 'content' } (680)
      │
      ├── isEditing ? .edit-shell > .edit-layout          (683)   ── EDIT MODE
      │     ├── .edit-section  "Story blocks" head          (685)
      │     │     .advanced-editor → RichTextBlock[]         (689)
      │     │     .block-insert (＋ menu: types + Sutradhar)  (714)
      │     └── .edit-section.tags-edit-section  "Tags"      (784)
      │           .tags-card: chips + popular row + input    (788)
      │
      ├── (no blocks) ? .story-empty                        (834)  ── EMPTY STATE
      │     .story-empty-icon / -title / -sub                (835)
      │     .story-empty-actions: "Write the story" | "Draft from image" (841)
      │
      └── else .text-block-item[] + StoryFlow               (853)  ── READING
            .underline-hint (persistent strip)               (857)
            .text-block-item  data-block-id data-origin      (863)  dangerouslySetInnerHTML
            <StoryFlow showGenerateButton>                    (880)

(sibling of .content-area, NOT inside it):
├── .tags-section        (1017)  { !isEditing && tab==='content' }  h4 + ul.tags-list  ── VIEW TAGS
└── .edit-actions        (1029)  { isEditing }  statusline (words/min/blocks) + Save/Cancel
```

**The structural tell:** `.source-account-section` and `.epic-badge-section` sit *above* the `activeRightTab === 'content'` gate (651–678). They render on the **Highlights** and **Unconceal** tabs too, and in **edit** mode — identity chrome bleeding across every view. That is the "metadata as its own section" smell the map named, now located precisely.

---

## 2. One-home-per-item table

| Item | Current home(s) | Serves purpose? | Proposed single home |
|---|---|---|---|
| **Source / @handle** | `.source-account-section` inside `.content-area`, above the tab gate → shows on every tab & mode (654) | Yes — "who saw what" provenance | **Meta-head** of the story column only (gate it behind `tab==='content'`). Coordinate with Lane 1 (topbar persona) so the handle isn't rendered in two chromes. |
| **Epic association** | `.epic-badge-section`, own `<h5>` band, every tab & mode (670) | Weak on this page — navigational, not "meaning of this image" | Demote to a **chip in the same meta-head row** next to the handle (`From @handle · Epic: Title`). One line of identity, not a band. |
| **Tags** | **Two homes:** view = `.tags-section`, sibling *outside* `.content-area`, bottom of pane, read-only `<ul>` (1017). Edit = `.tags-edit-section` *inside* `.edit-layout`, full card with input (784) | Yes — retrieval metadata | **Meta-foot** of the story column, *inside* `.content-area`, one `<TagStrip>` component, mode-switched internals. (settled in §4) |
| **Underline hint** | `.underline-hint` persistent strip above blocks (857) | No — it *instructs*, doesn't serve reading; duplicates the live selection tooltip | Remove the permanent strip; rely on the existing selection tooltip (`showUnderlineTooltip`, positioned at the selection, `handleTextSelection` 114). Optionally a one-time/dismissible caption. (settled in §4) |
| **Story blocks** | View = `.text-block-item` read-only div (863); Edit = `RichTextBlock` TipTap editor (691) | Yes — the core surface | Keep two renderers *but* mount both in one **story-column** slot so meta-head/-foot frame all states identically. A `readOnly` TipTap render could unify later (Path B territory) — not now. |
| **Word / read / block stats** | `.edit-statusline`, edit only (1031) | Status, not content — Lane 5 already lifted it out of the body | Keep as the thin edit status line (LOCKED, Lane 5). No change. |

---

## 3. View/edit duplication list (rendered twice, divergent markup)

1. **Tags — the headline duplication.** View `.tags-section` (`<ul>` of `<li>` chips, *outside* `.content-area`, bottom of pane) vs edit `.tags-edit-section` (card with chips+remove, popular row, text input, *inside* `.edit-layout`). Different DOM, different container, different position in the tree. This split *is* why tags "feel out of place." → one `<TagStrip>` (§4).
2. **The word "Tags" heading.** Rendered twice — `.tags-section h4` (1019) and `.edit-section-head h4` (786). Collapses to one when the strip unifies.
3. **Story blocks renderer.** `.text-block-item` (read-only, `dangerouslySetInnerHTML`, inline color/padding) vs `RichTextBlock` (TipTap). Expected divergence, but note: the read-only view re-implements the block's paint (color/padding at 870–874) separately from the editor's. A single block-render primitive with a `readOnly` flag would remove that drift — flagged, not scheduled (leans Path B).
4. **Identity chrome (source + epic).** Not view/edit-divergent, but *tab*-divergent leakage: it renders under Highlights/Unconceal too. Gating it to `tab==='content'` removes three redundant render sites.

---

## 4. The two questions Lane 5 deferred — settled

### 4a. Tags — ONE home (settles decisions-log Lane 5 Q4)

**Home: a meta-foot at the bottom of the story column, *inside* `.content-area`, one component for both modes.**

Structure:
- Introduce a single `<TagStrip mode={isEditing ? 'edit' : 'view'} …>` rendered as the **last child of the story column**, inside `.content-area`.
  - `mode='view'` → read-only chips (today's `.tags-section` markup, minus the standalone `<h4>` band).
  - `mode='edit'` → chips-with-remove + popular row + add input (today's `.tags-edit-section` internals).
- **Delete** the sibling `.tags-section` block at 1017 (currently outside `.content-area`) and the `.tags-edit-section` block inside `.edit-layout` (784); both are replaced by the one strip in the shared slot.

Why meta-foot, not panel chrome: the Content panel header already carries three tabs (Story/Highlights/Unconceal); tags need an input in edit mode that a header can't hold; and tags are content-adjacent metadata that belong *with* the story, not in navigation. This also creates a clean symmetry — **meta-head** (source/epic identity) frames the top of the story, **meta-foot** (tags) frames the bottom — the same frame in empty, reading, and editing. That symmetry is the structural answer to "tags have no home."

Preserved: tag display, add/remove, popular tags — all move intact into the strip's `edit` branch.

### 4b. Highlights in context (settles Purpose lens #4 / decisions-log "Highlights in context")

The plumbing already exists and I confirmed it end-to-end:
- Highlights are saved **with** `block_id` — `handleAddHighlight` sets `block_id: selectedBlockId` (`PostDetailPage.jsx:152`), captured from the block under the selection (`data-block-id`, 128).
- Reading-mode blocks already render the target: `<div data-block-id={block.id} …>` (866).
- But the Highlights tab renders **orphans** — `.highlight-card` = number + blockquote + remove, no link back (908–925).

**Settle:** make each highlight card a **jump-to-source** control using the existing `block_id → [data-block-id]` link. On activate: set `activeRightTab='content'`, then `document.querySelector('[data-block-id="…"]').scrollIntoView(...)` and briefly flash the block. Structure needed:
- Highlight card gains a jump affordance (the card becomes/contains a button); add a `jumpToBlock(blockId)` handler that switches tab + scrolls.
- **Graceful degradation:** `block_id` can be `null` (older highlights, or a selection spanning blocks) or the target may no longer exist (block deleted). When absent/unresolvable, render the quote with **no** jump affordance — never a dead link.

No data migration, no backend change. Small change, real "trace who wrote what / return to where it lives" payoff.

---

## 5. Empty-state proposal (empty → editing → reading as one surface)

Today these are **three separate DOM subtrees** swapped by flags at the same tree level (edit-shell 683 / story-empty 834 / reading 853), and tags render in *different containers* per state. Entering edit unmounts the hero and mounts the editor; layout jumps.

**Proposal — one story column, three states, shared frame:**
- Wrap all three states in a single `.story-column` inside `.content-area`, framed by **meta-head** (source/epic) above and **meta-foot** (TagStrip) below — identical in every state, so nothing reflows around the transition.
- Treat **empty as the zero-block case of reading**, not a separate hero. It stays left-aligned (CSS already moved it off-center, 461–472); its primary "Write the story" flips `isEditing` in place. Because the second-layer build already **seeds a focused empty block on `startEditing`** (decisions-log LOCKED), entering edit already lands the caret in a live block — the empty→editing transition is already seamless in behavior; this change makes it seamless in *layout* by keeping the same column + frame.
- "Draft from image" stays (it calls `startEditing({seed:false})` then `draftFromImage()`), and will fold into `/draft` when Phase-2 slash-AI lands (already LOCKED direction) — no structural conflict.

Net: empty, editing, and reading become **states of one framed column**, not three trees that swap. Tags/source stop moving between containers, which is the root of the "out of place" feeling.

**Underline hint (prompt Q4):** the persistent `.underline-hint` strip is overhead by Purpose — it instructs rather than serves, and duplicates the transient selection tooltip that already fires on `handleTextSelection`. Recommend removing the permanent strip; keep the contextual tooltip. If discoverability matters, a one-time dismissible caption — not a permanent band.

---

## Questions for Adarsh

1. **Meta-head scope vs Lane 1.** Lane 1 eyes the persona line in the topbar. Should the "From @handle" provenance live (a) only in the content meta-head, (b) only in the topbar, or (c) both with distinct jobs (topbar = navigation, meta-head = provenance)? I need the boundary before I move it, to avoid double-rendering identity.
2. **Epic association — keep on this page at all?** It's navigational, not "meaning of this image." Demote to a chip in the meta-head (my proposal), or drop from Drishya entirely and let Epics be reached elsewhere?
3. **Highlight jump — cross-tab or same-tab?** Jumping from the Highlights tab means switching to the Story tab and scrolling. Acceptable, or would you rather highlights render *inline* beside the story (a margin rail) so there's no tab hop? The rail is a bigger structural change; the tab-hop is the small one.
4. **TagStrip position when editing.** Meta-foot puts tags at the *bottom* of a long editing column — you'd scroll past all blocks to tag. Fine, or should the edit-mode strip be sticky/collapsible so tags stay reachable while writing?
5. **Underline hint — remove outright, or one-time?** Confirm you're OK dropping the permanent strip in favor of the existing selection tooltip (my recommendation), versus keeping a dismissible first-run hint.

*Research only — no app code touched. Awaiting your calls before any build prompt.*
