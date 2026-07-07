# Lane 2 — The split shell: findings

**Mode:** deep read + architecture proposal. No app code changed.
**Reading frame:** the four-layer lens (Foundation → Structure → Behaviour → Craft). Lane 2 lives mostly in **Structure**, but the biggest finding is a **Foundation** (data-contract) problem, and the divider is a **Behaviour** gap. For every "this feels right / would feel right" call below, the *architectural cause* is named, not the look.

Files read: `frontend/src/components/PostDetailPage.jsx`, `PostDetailPage.css`, `BoundingBoxEditor.jsx`, `RegionDetectorModal.jsx`, `package.json`. Line numbers are current as of commit `afa9ee0` (they drifted from the prompt after the Lane 4/5/1 edits).

---

## 1. Current shell tree (with file+line refs)

```
.post-detail-split            PostDetailPage.jsx:702   CSS:175  (flex row, overflow:hidden, gap:--space-2, ref=containerRef)
├── .post-detail-left         :704   CSS:190   width = `${leftPanelWidth}%`  (inline style)
│   ├── .panel-header         :705   CSS:215   <h3>Visual</h3> + .panel-tabs
│   │   └── .panel-tab ×2      :709,:715        Image · Annotations   (activeLeftTab)
│   └── .image-display        :725   CSS:310   overflow:hidden → <BoundingBoxEditor post onUpdate/>
│
├── .split-divider            :730   CSS:335   bare <div>, onMouseDown=handleMouseDown, title only
│
└── .post-detail-right        :737   CSS:191   width = `${100 - leftPanelWidth}%`
    ├── .panel-header         :738   CSS:215   <h3>Content</h3> + .panel-header-actions
    │   └── .panel-header-actions :740 CSS:246  .panel-tabs (Story · Highlights · Unconceal) + .panel-edit-btn (pencil, :765)
    └── .content-area         :779   CSS:364   overflow-y:auto, max-width:56rem, margin:0 auto  ← the one scroller
        ├── Story tab         :781            .story-column (meta-head + blocks/editor)
        ├── Highlights tab    :940            highlight cards → jumpToBlock()
        └── Unconceal tab     :966            Aletheia + commentary + .uncon-anatomy (region_annotations)
```

Divider state model (`PostDetailPage.jsx`):
- `leftPanelWidth` (default **45**, :41) is the **single source of truth**. Both panes derive width from it inline (`leftPanelWidth%` / `100 - leftPanelWidth%`). Good — one number, no drift.
- Drag: `handleMouseDown` (:239) flips `isDraggingRef`; a `useEffect` (:247) attaches `document` mousemove/up listeners; clamp **20–80%** (:252). Clean, but see Behaviour gaps below.

---

## 2. Pane-relationship map — shared data, wired separately

The two panes describe the **same image** but share **zero runtime state**. Every "connection" you'd expect is absent because each sub-tool owns its own local selection and its own slice of `post`.

| Underlying thing | Left pane (Visual) | Right pane (Content) | Wired together? |
|---|---|---|---|
| **Image regions** | `post.bounding_box_tags` — an **object** `{tagName: {x,y,w,h}}`, edited in `BoundingBoxEditor`; selection = local `selectedTag` (BoundingBoxEditor.jsx:15) | `post.region_annotations` — an **array** `[{id,label,box,depth,prioritised,weight,user_note}]`, edited in `RegionDetectorModal` (opened from Unconceal→Anatomy); selection = local `selectedId` (RegionDetectorModal.jsx:20) | **No.** Two schemas, two editors, two selection states, for the same pixels. |
| **Tags** | keys of `bounding_box_tags` double as the visual tag vocabulary | text-side `editedTags` / `TagStrip` is a separate list | **No** (tags home deferred to Lane 4) |
| **Highlights ↔ story** | — | highlight stores `block_id` (:170); `jumpToBlock` scrolls the Story via `data-block-id` (:208–219) | **Yes** — the *only* place linkage is actually built |
| **Box select → content** | selecting a box does nothing | — | **No** |
| **Anatomy part → image / story** | naming a part in Anatomy does nothing on the image | — | **No** |

**The headline finding (Foundation, not Structure):** `bounding_box_tags` and `region_annotations` are **two parallel data architectures for one concept** — "parts of this image." This is the repo's already-flagged open item ("Region duplication … merge-or-keep"), and it is the real reason the panes can't complement each other. You cannot cleanly link a selection across panes while the thing being selected has two incompatible shapes and two id spaces. This is textbook *"does the data model support the experience we want?"* — and today it blocks it. Figma hit the identical wall with two parameter systems and resolved it by **unifying the data model first** (one shared definition everything references), *then* unifying runtime behaviour — the correct order here too. See Figma, *A Tale of Two Parameter Architectures*.

**The one bright spot to imitate:** highlights ↔ story is exactly the pattern the rest of the shell lacks — a durable id (`block_id`) stored on one object that points into another, with a `scrollIntoView` bridge and graceful degrade when the id is stale (:943, `canJump`). Every cross-pane link proposed below is just this pattern generalised.

---

## Answers to the five questions

### Q1 — Header pattern (Structure)
Today: `<h3>Visual</h3>` / `<h3>Content</h3>` + a tab group, in a `space-between` header (CSS:215).

The h3 is **near-redundant**: the tabs (Image·Annotations / Story·Highlights·Unconceal) already tell you what each pane is. "Visual"/"Content" is a category label the tabs imply. What the h3 *does* earn its keep for is (a) a stable identity anchor and (b) a left-anchored slot so the tabs don't float alone. It carries no information the tabs don't.

**Proposed header = tabs-only, with a defined actions slot.** Drop the h3 as a title; if a pane label is ever needed it becomes a quiet inline kicker, not a heading. Structure:
```
.panel-header  →  [ .panel-tabs (left) ............ .panel-actions (right) ]
```
Panel-level actions attach to a single right-aligned `.panel-actions` slot (the pencil already does this via `.panel-header-actions`, :740). This gives one predictable home for per-pane verbs (pencil on Content; e.g. "detect regions"/eye-toggle could move here on Visual instead of living in `BoundingBoxEditor`'s inner stats bar). *Why this feels cleaner:* it makes the header a **consistent primitive** (tabs left, actions right) reused by both panes — the "same control in the same place everywhere" property, not a visual tweak.

### Q2 — Do the panes complement each other? (Foundation → Structure)
No — see the map above. They reference the same image regions, tags, and (potentially) highlights but are wired as isolated tools with local selection state. To make them complement each other you must **lift selection out of the leaf components** and, first, **unify the region data model**. Concrete linkage options in §4.

### Q3 — Divider behaviour (Behaviour)
- **`leftPanelWidth` as SSOT: yes, keep it.** One number driving both widths is the right model; don't split it into two.
- **Only drag, no presets — a gap.** There is no collapse/expand, no reset, no "focus the writing" preset. Add fixed presets on top of the same SSOT (double-click divider → reset to 45; a preset that collapses Visual to a rail while writing). These are just setter calls to `leftPanelWidth` — cheap, no new state.
- **Reconcile the `isEditing` claim.** The prompt says editing "already nudges widths" — it actually **does not touch `leftPanelWidth`.** Entering edit only **dims** the left pane (`.editing-mode .post-detail-left { opacity: .82 }`, CSS:300) and widens the *inner* `.content-area` max-width 56→70rem (CSS:374). So the split ratio is unchanged; the pane is visually de-emphasised, not resized. **Decide one mechanism:** either editing drives a width preset (Visual actually narrows — honest use of the SSOT) **or** it only de-emphasises and the ratio holds. Today it half-implies the first while doing the second. Recommend: on entering edit, apply a *preset* (e.g. Visual→30%) via `leftPanelWidth`, and drop the opacity trick — one source of truth, one behaviour.

### Q4 — Touch vs gap (Structure/Craft)
Currently **two bordered, rounded cards with a `--space-2` gap** (CSS:182,199) **plus** a 10px transparent divider carrying a 1px `::after` line floating in that gap (CSS:335,347). That's two separators doing one job: the card borders *and* a hairline. Recommend **one grammar: two panes that share a single divider line** (cards meet at the divider; the divider *is* the boundary and the drag affordance). Drop either the inter-pane gap or the divider line so the seam reads as one thing. *Why:* a single, consistent boundary primitive reads as "one workspace split in two," where border+gap+line reads as "two unrelated boxes" — which is precisely the disconnected feel this lane exists to fix. (Surface/colour deferred; this is about *how many* boundary elements exist, which is structural.)

### Q5 — Scroll ownership (Behaviour) — verified sound
- **Right pane:** `.content-area` is the sole scroller (`overflow-y:auto`, `scrollbar-gutter:stable`, CSS:364). Its two ancestors (`.post-detail-right`, the pane) are `overflow:hidden` columns; `.panel-header` is `flex-shrink:0`. So the header stays put and only the content scrolls. Correct.
- **Left pane:** `.image-display` is `overflow:hidden` (CSS:310) — the image fits, never scrolls. Correct for an image, but note the Annotations tag-list inside `BoundingBoxEditor` will clip if long (its own concern → Lane 3).
- **Page/topbar:** `.post-detail-split` is `overflow:hidden` and `flex:1` under a fixed topbar — the page itself doesn't scroll. Good.
- **One thing that fights it:** `.content-area` has `max-width:56rem; margin:0 auto`, so the **scrollbar sits at the centered content edge, not the pane edge** — the scroll region is narrower than the pane. Fine for reading rhythm, but if a future preset narrows the pane, verify the centered column + stable gutter don't produce a double inset. Flag, not a blocker.

---

## 3. Proposed shell (leanest structure)

```
.post-detail-split                 (flex row · SSOT: leftPanelWidth · overflow:hidden)
├── .pane.pane--visual             width: leftPanelWidth%
│   ├── .panel-header  →  .panel-tabs (Image · Annotations)      .panel-actions →
│   └── .pane-body                 (BoundingBoxEditor)           scroll:auto if needed
│
├── .split-divider                 role="separator" tabindex=0
│                                   aria-valuenow=leftPanelWidth aria-valuemin=20 aria-valuemax=80
│                                   aria-controls=pane--visual  aria-label="Resize panels"
│                                   keys: ←/→ nudge · Home/End = min/max · dblclick = reset(45)
│
└── .pane.pane--content            width: 100 - leftPanelWidth%
    ├── .panel-header  →  .panel-tabs (Story · Highlights · Unconceal)   .panel-actions → pencil
    └── .content-area              (overflow-y:auto — the scroller)
```
Changes vs today: h3 titles → tabs-only; one shared `.panel-actions` slot per pane; divider becomes a real focusable separator; a single boundary grammar; presets ride the existing SSOT. No tab is removed; resize still works.

---

## 4. Linkage options (make the panes complement each other)

Ordered foundation-first. All three generalise the proven highlight↔block pattern.

**Option A — Unify the region model first (Foundation; prerequisite for real linking).**
Merge `bounding_box_tags` + `region_annotations` into one region collection with a stable `id`, `box`, `label`, and optional `block_id`. Both editors read/write the same shape.
*Effort:* high (backend + data migration + touches BoundingBoxEditor & RegionDetectorModal). *Risk:* high — it's a data-contract change; **must be co-decided with Lane 3 (Visual) and Lane 6 (Unconceal)**, which own those editors. *Payoff:* unlocks A2/B cleanly; without it, cross-pane selection means maintaining a fragile id-mapping between two schemas.

**Option B — Link region → story block (Structure; additive, low risk).**
Give a region an optional `block_id` (exactly like highlights) so a part can point at the paragraph that discusses it. Selecting a part scrolls the Story (`scrollIntoView`), and a story block can show "has a linked region." Reuses `jumpToBlock` wholesale.
*Effort:* medium. *Risk:* low — additive field, degrades gracefully when null (copy the `canJump` guard). *Best first slice* if Option A is deferred, and it works on whichever region model survives.

**Option C — Lift selection to a shared `selectedRegionId` (Structure/Behaviour).**
Hoist selection out of `BoundingBoxEditor` (`selectedTag`) and `RegionDetectorModal` (`selectedId`) into `PostDetailPage`; pass down as props. Selecting a box highlights the matching part and vice-versa; the shell becomes one workspace with one focus.
*Effort:* medium *if* Option A is done first; **high/fragile if not** (you'd be syncing selection across two id spaces). *Risk:* medium. This is the Figma "layers panel ↔ canvas share one selection" model — but Figma could only do it because both sides read one data model.

**Recommended sequence:** decide A with Lanes 3/6 → ship B as the first visible link (cheap, proves the pattern) → then C once regions are unified. Don't attempt C before A.

---

## 5. Foundation aside — the dead `allotment` dependency
`allotment@1.20.4` (a resizable split-pane primitive) is in `package.json` but **not imported anywhere** — only a stray `.allotment-sash` rule lingers in `App.css:494`. The divider is hand-rolled instead, and the hand-rolled version is what's missing keyboard, ARIA, min/max, collapse, and persistence. Two clean options: (a) **adopt `allotment`** for the split and get separator a11y + collapse + persistence for free (it removes the bespoke drag `useEffect`), or (b) **remove the unused dep** and harden the hand-rolled divider to the APG spec. Either way, resolve the "primitive vs one-off" ambiguity — right now you pay for a primitive and ship the one-off.

---

## Questions for Adarsh
1. **Region model:** merge `bounding_box_tags` + `region_annotations` into one (Option A), or keep them separate and only bridge with `block_id` (Option B)? This is the gating call — Lanes 3 and 6 need it too.
2. **Editing & the divider:** when you enter edit mode, should the Visual pane actually **narrow** (a width preset on the SSOT) or just **de-emphasise** (today's opacity dim)? Pick one.
3. **Divider presets:** want a "focus the writing" collapse (Visual → rail) and double-click-to-reset, in addition to drag?
4. **Panel titles:** OK to drop the "Visual"/"Content" `<h3>`s in favour of tabs-only + a right-aligned actions slot?
5. **`allotment`:** adopt it as the split primitive, or remove it and harden the hand-rolled divider to the APG window-splitter spec?

---

### Sources
- W3C WAI-ARIA APG — Window Splitter Pattern: https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/
- Figma — A Tale of Two Parameter Architectures (unify the data model, then the runtime): https://www.figma.com/blog/a-tale-of-two-parameter-architectures/
- Figma — Improving Performance in the Layers Panel (selection as shared/derived state): https://www.figma.com/blog/improving-performance-in-the-layers-panel/
