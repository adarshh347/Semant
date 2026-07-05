# Border & Layout Architecture Plan — Post Detail page

Scope: the physical structure of borders, panels, gutters, headers, and inner
subsections on the Post Detail route (`/posts/:postId`). This is an
architecture document, not a styling wishlist. No colors, no typography, no
"beauty" — only where boundaries physically belong.

**One-line diagnosis:** the page is currently built as *nested cards floating on
a canvas* (rounded, bordered, shadowed containers at 5+ nesting depths). It
should be built as a *split-pane workspace*: a small number of large structural
regions, with inner tools that mostly have **no** box of their own.

Files in play:
- `frontend/src/App.jsx` + `App.css` — layout shell, fullscreen wrapper
- `frontend/src/components/NavBar.jsx` + `Navbar.css` — Region 1 (global chrome)
- `frontend/src/components/PostDetailPage.jsx` + `PostDetailPage.css` — Regions 2–7
- `frontend/src/components/BoundingBoxEditor.jsx` + `BoundingBoxEditor.css` — Region 8

### Structural constraint discovered (drives Section D)
`App.jsx` renders `<Navbar/>` and `<main><Outlet/></main>` as **siblings** under
`.app-layout`. The page's `editing-mode` class lives on
`.post-detail-page`, *inside* `<main>`. Therefore **CSS alone cannot compact or
fade the global Drishtikone navbar during editing** — a descendant selector from
`.editing-mode` can never reach an earlier sibling. Compacting Region 1 requires
shared state (an editing flag lifted to `.app-layout`). This is why "collapse the
top chrome" is split below into a P0 part (Region 2, reachable by CSS) and a P1
part (Region 1, needs a state hook).

---

## A. Current border map

Every visible container / border / rounded surface currently rendered, top to
bottom. "Rim" = `box-shadow: 0 0 0 1px` used as a second border.

### Region 1 — Global Drishtikone navbar  (`Navbar.css`)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.navbar-wrap` | none (transparent, sticky) | — | padding `--space-3` + clamp |
| `.navbar` | `1px solid --line` + backdrop blur | `--radius-xl` | **floating rounded pill**, max-width 1600, centered |

### Region 2 — Sutradhar persona/action strip  (`.post-detail-topbar`)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.post-detail-topbar` | `border-bottom 1px --glass-border` + `box-shadow-sm` + `margin-bottom: 2px` | square | full-width glass bar |
| `.post-detail-topbar.compact` | shadow removed, padding reduced | — | editing variant (exists already) |
| `.action-btn` (AI / Edit / Delete) | `1px solid --line` each | `--radius-md` | 3–4 separate bordered buttons |
| `.dirty-pill` | `1px solid --accent` | pill | |

### Region 3 — Workspace shell  (`.post-detail-split`)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.post-detail-split` | **none** | — | transparent, `padding 4/6/6`, `gap --space-5` between panes |

### Region 4 — Left Visual panel  (`.post-detail-left`)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.post-detail-left` | `shadow-sm` + `0 0 0 1px --glass-border` rim | `--radius-lg` | **rounded card** |
| `:focus-within` | rim → `accent-primary` | — | whole panel glows |

### Region 5 — Right Content panel  (`.post-detail-right`)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.post-detail-right` | identical shared rule with left | `--radius-lg` | **rounded card** |
| `.split-divider` | transparent 6px; `::after` handle appears on hover/drag | — | resizable 20–80%, `-0.5rem` negative margin |

### Region 6 — Panel headers  (`.panel-header`)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.panel-header` | `border-bottom 1px --border-subtle` + gradient bg | square | shared by both panes |
| `.panel-tabs` | `1px solid --line` group, `--surface-2` fill | `--radius-md` | **bordered segmented pill wrapping the tabs** |
| `.panel-tab.active` | `--surface-primary` fill + `shadow-sm` | `--radius-sm` | raised chip |

### Region 7 — Inner Content editor areas  (`.content-area`, centered, max-width 56rem / 70rem editing)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.source-account-section` | `1px solid --line` + tinted fill | `--radius-md` | **card row** |
| `.epic-badge-section` | `border-bottom 1px --line` | — | separator only (good) |
| `.epic-link` | `1px` + fill | pill | |
| `.edit-shell-intro` | `border-bottom 1px --line` | — | separator only (good) |
| `.editor-meta` | `border-bottom 1px --line` | — | separator only (good) |
| `.edit-section-head` | `border-bottom 1px --line` | — | separator only (good) |
| `.advanced-editor` | none (gap only) | — | good — just a stack |
| `.rich-text-block` (each block) | `1px solid --border-subtle` + `shadow-sm`; hover `translateY(-2px)`+`shadow-md`; focus-within `accent border + 2px accent ring + shadow-lg` | `--radius-lg` | **every paragraph is a floating card; the focus ring is the "loud orange border" problem** |
| `.add-block-menu` | `1px solid --line` + `--surface-2` | `--radius-lg` | **heavy tray** around 3 buttons |
| `.add-block-btn` | `1px solid --line` each | pill | box-in-box with the tray |
| `.sutradhar-composer` | `1px solid --line` + gradient + inset shadow | `--radius-lg` | **card** |
| `.composer-input` | `1px solid --line` | `--radius-md` | field inside the card |
| `.composer-btn` | `1px solid --line` each | pill | |
| `.tags-card` | `1px solid --line` + `--surface-2` | `--radius-lg` | **card** |
| `.tag-item` | `1px solid --border-medium` + `shadow-sm` each | pill | chips inside the card |
| `.tag-input` | `1px solid --border-medium` | pill | |
| `.edit-actions` (Save/Cancel) | `border-top 1px --line` + gradient fade + backdrop blur, `position: sticky; bottom:0` | — | **floating strip pasted over content** |

Container-nesting depth on the right pane during editing:
`pane (4/5) → content-area → edit-shell → edit-layout → editor-subsection card → input`.
That is **up to 5 bordered/filled boxes deep**. Target depth: 2.

### Region 8 — Inner Visual areas  (`BoundingBoxEditor.css`)
| Element | Border / container | Radius | Notes |
|---|---|---|---|
| `.bbox-editor-wrapper` | none | — | `gap: 0`, fills panel |
| `.bbox-stats-bar` | `border-bottom 1px rgba(255,255,255,.1)` + **hardcoded** `rgba(30,30,30,.9)` | square | annotation stats; not theme-aware |
| `.bbox-editor-container` | none, **hardcoded** `#0a0a0a` | — | image viewport, `overflow: hidden` |
| `.toggle-visibility` / `.view-crops-btn` | button borders | — | eye + crops actions in stats bar |
| `.bbox-tags-list.glassmorphism`, `.bbox-tag-form.glassmorphism` | floating glass overlays over image | rounded | absolutely positioned |

---

## B. Proposed border grammar

Six levels. A container may only draw a boundary if its level *entitles* it to.
Everything not on this list is **borderless and transparent** and relies on
spacing + typographic weight for grouping.

| Level | Region | Boundary treatment | Radius |
|---|---|---|---|
| **L0 — Page background** | `.app-layout--fullscreen`, `.post-detail-split` | none. transparent canvas. | — |
| **L1 — Global chrome** | Region 1 navbar, Region 2 topbar | one **hairline bottom divider** per bar. No rounded pill, no box-shadow, no rim. Chrome reads as a thin functional strip, not a floating object. | square |
| **L2 — Major split panes** | Region 4 Visual, Region 5 Content | **the only elements allowed a full rounded box.** One quiet border (single `1px --line`, drop the rim double-border and the shadow), `--radius-lg`. These are the workspace walls. | `--radius-lg` |
| **L3 — Panel headers** | Region 6 | **structural bottom divider only** (`border-bottom 1px`). No gradient fill. Tabs become underline/segment text, not a bordered pill group. Header is a thin functional rail inside the pane. | square |
| **L4 — Active editor surface** | Region 7 story-block in focus; Region 7 `.content-area` write zone | **at most one** boundary visible at a time. The block in focus gets a **left rule or a single quiet outline**, never a glowing ring + lift + shadow simultaneously. Non-focused blocks have **no** box. | square / `--radius-sm` |
| **L5 — Inline tools & chips** | add-block buttons, composer, tags, source row, stats | **no container box.** Grouping by whitespace + a single optional hairline separator between tool groups. Individual chips/buttons keep their own pill only where they are genuinely interactive targets (tag chips, add-block buttons); the **tray/card around them is removed**. | pill on the control itself only |

Rule of thumb enforced by the grammar:
> A child may not repeat its parent's boundary type. If the parent already has a
> border, the child inside it must be borderless (whitespace-grouped) unless it
> is an individual interactive control (input / button / removable chip).

---

## C. Touch vs gap rules

| Boundary | Decision | Rationale |
|---|---|---|
| Navbar (R1) ↔ topbar (R2) | **touch**, stacked, each a hairline strip | two thin rails read as one chrome zone, not two floating bars |
| Topbar (R2) ↔ workspace (R3) | **hairline divider**, no gap | chrome ends, workspace begins on a clean line |
| Left pane (R4) ↔ Right pane (R5) | **controlled gutter** of `--space-4`, with the existing resizable `.split-divider` centered in it | keep the resize affordance; the panes are peers separated by a precise channel, not touching flush. (Flush-touch is the VS Code model but conflicts with the current rounded-pane look; one tight gutter is the smaller, safer move.) |
| Pane outer edges ↔ shell padding (R3) | **gap** = `--space-4` all around | frames the workspace inside the viewport |
| Panel header (R6) ↔ pane body | **touch**, separated by the L3 bottom divider only | header is part of the pane, not a floating control |
| Story blocks (R7) to each other | **gap** (`--space-5`), **no borders** | rhythm by space, not boxes |
| Add-block / Composer / Tags groups (R7) | **gap** between groups + optional single hairline separator; **no card boxes** | these become inline tool rows in the flow, not trays |
| Save/Cancel footer (R7) ↔ content | **touch** the bottom of the content pane as a sticky rail with one **top hairline**; no gradient, no blur, no free-floating margin | footer belongs to the pane's structure |
| Stats bar (R8) ↔ image viewport | **touch**, hairline divider between | one visual pane, two stacked zones |

**Rounded corners appear only at L2** (the two panes). Everything inside a pane
uses square/internal edges except individual pill controls (buttons, chips,
inputs). No rounded corners on headers, trays, footers, or the stats bar.

---

## D. Editing-mode layout rules

What physically changes when `isEditing` is true. Split by whether CSS can reach it.

**Reachable by CSS today** (descendants of `.post-detail-page.editing-mode`):
| Element | On edit |
|---|---|
| Topbar (R2) | **compress**: reduce to a hairline strip, drop shadow (partly done via `.compact`). Keep all actions, shrink to icon-weight. |
| Left Visual pane (R4) | **recede, stay structural**: drop to ~0.9 opacity + remove its focus-glow; do **not** collapse or hide. Restore on hover/focus (partly done). |
| Panel headers (R6) | **compress** padding to a thin rail (partly done). |
| Right Content pane (R5) | **becomes dominant**: widen `.content-area` (already 70rem), and it is the only surface allowed an active outline (L4). |
| Story blocks (R7) | non-focused blocks lose their card entirely; only the focused block shows the L4 boundary. |
| Support rail — Composer + Tags (R7) | lose their card borders; become a weaker-surface right rail separated from the main column by **one vertical hairline**, not two floating cards. |
| Save/Cancel footer (R7) | appears as the pane's sticky bottom rail (L4/structural), not a blurred floating strip. |

**Needs a state hook (not CSS-only)** → P1:
| Element | Desired | Why blocked |
|---|---|---|
| Global navbar (R1) | compact / fade to a thin bar during editing | it is a **sibling** of the page in `App.jsx`; no descendant selector reaches it. Requires lifting an "editing" flag to `.app-layout` (context, or a class on `<main>`). |

Nothing is destroyed on edit. The hierarchy is achieved by **receding** the
chrome and side rail, and **promoting** the content pane — not by hiding controls.

---

## E. Implementation plan

### P0 — border / layout architecture (structural; mostly CSS in `PostDetailPage.css`)
1. **Collapse the inner card stack (L5).** Remove the container box (border +
   fill + radius) from `.add-block-menu`, `.sutradhar-composer`, `.tags-card`,
   and `.source-account-section`. Keep the individual controls; group by
   whitespace + at most one hairline separator.
2. **De-card the story blocks (L4).** `.rich-text-block`: remove per-block
   border + shadow + hover lift. Replace the focus-within glowing ring with a
   single quiet outline or left rule on the focused block only.
3. **Panes to L2 grammar.** `.post-detail-left/right`: replace `shadow-sm + 0 0 0
   1px` rim with a single `1px --line` border; remove the accent focus-glow on
   the whole pane. Keep `--radius-lg`.
4. **Panel header to L3.** `.panel-header`: drop the gradient fill, keep the
   bottom divider. Convert `.panel-tabs` from a bordered filled pill group to an
   underline/segment control (remove the wrapper border + fill).
5. **Footer to structural rail.** `.edit-actions`: remove gradient + backdrop
   blur; keep a single top hairline; anchor it as the content pane's sticky
   bottom.
6. **Topbar to L1 strip.** `.post-detail-topbar`: remove box-shadow + the 2px
   margin; reduce to a hairline bottom divider in both normal and `.compact`.
7. **Gutter rule.** Normalize `.post-detail-split` gap to `--space-4` and confirm
   the `.split-divider` sits centered in that gutter.

### P1 — interaction / collapse
8. **Global navbar compact-on-edit (R1).** Add an editing flag to `.app-layout`
   (state lifted from the page, or route/context) and a `.app-layout--editing`
   compaction rule in `Navbar.css` / `App.css`.
9. **Support-rail divider.** Replace the two right-column cards with a single
   weak-surface rail + one vertical hairline between the main column and rail.
10. **Focused-block affordance.** Wire the L4 active outline to the actually
    focused block (currently every block reacts to hover/focus).
11. **Independent-scroll contract.** Confirm each pane body scrolls
    independently and headers/footers stay pinned (they mostly do; verify after
    the footer change).

### P2 — polish / material / color (out of this doc's scope, listed for tracking)
12. Theme-aware surfaces for `BoundingBoxEditor` (`.bbox-stats-bar`,
    `.bbox-editor-container` are hardcoded dark).
13. Accent-usage reduction on helper buttons / chips.
14. Motion / transition refinement on the recede/promote states.

### P0 exit check
- No container inside the Content pane draws a border except the pane (L2), the
  header divider (L3), and the single focused editor surface (L4).
- Composer, Tags, Add-block, source row: **zero** card boxes.
- Only two rounded rectangles remain in the workspace: the Visual pane and the
  Content pane.
- Save/Cancel reads as the pane's bottom rail, not a floating strip.

---

## F. File impact

| File | Regions | Change type |
|---|---|---|
| `PostDetailPage.css` | 2,3,4,5,6,7 | **primary** — L1/L2/L3/L4/L5 border rules, gutter, footer, topbar strip (P0 items 1–7) |
| `PostDetailPage.jsx` | 7 | minimal — only if the support rail needs a wrapper element or a class rename for the L5 groups; no logic/state/handler changes |
| `App.jsx` | 1 | P1 item 8 — lift/propagate an `editing` flag to `.app-layout` |
| `App.css` | 1,3 | P1 item 8 — `.app-layout--editing` compaction |
| `Navbar.css` | 1 | L1 grammar + P1 compact-on-edit rule |
| `BoundingBoxEditor.css` | 8 | P0: stats-bar / viewport dividers to L1/L3 grammar; P2: theme-aware surfaces |

No backend, service, or data-flow files are touched. All P0 work is CSS plus (at
most) className / wrapper adjustments in `PostDetailPage.jsx`.
