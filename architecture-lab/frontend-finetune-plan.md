# Frontend finetune plan — region surface + pane responsiveness

Source: `vault/the orchestrator's writing section/list of updated work.md` (2 screenshots) + live code read. Research/plan only.

## Ownership routing (read first — avoids a thread collision)
- **Region surface** (full-screen image, premium panel, anchor "maps") = **Track D's live Visual pane, IN PROGRESS on the Darshan thread.** These are **requirements to inject into Track D Phase 1 now**, NOT to build on the Drishya thread. Building them here would collide on the same component.
- **Pane shell responsiveness + writing-pane measure** = **Drishya frontend** (`PostDetailPage.jsx` shell) — serialized on the shared file via the pause-slot.

## 1. Full-screen image (image feels cut) → Track D
- The `<img>` is `object-fit: contain` (not cut), but a portrait image in a wide pane reads small/awkward, and the SVG overlay's `preserveAspectRatio="none"` **stretches the polygons off the image**.
- Plan: (a) a dedicated **full-screen / lightbox mode** (click image → fills viewport, annotations overlaid, zoom + pan) — the immersive "see the image" feature. (b) **Fix overlay alignment:** the annotation SVG must track the image's *rendered* (letterboxed) box, not `none`, or polygons never line up. (c) In-pane keep `contain` so nothing is cut; full-screen is for detail.

## 2. Premium region panel (kill "block vibes") → Track D
- Your insight: the taxonomy (6 category tabs, coarse/mark) is **backend-oriented**; users feel the **result**, not the machinery.
- Plan: **foreground the felt unit** — each part as a calm reading row (part name · its Aletheia reading · your felt note), premium type rhythm, few borders (border-grammar). **Demote taxonomy** (General/Garments/Body/… tabs, coarse/mark) to a quiet filter/menu, not a stacked block hero. Dissect becomes one clear action, not a control wall.
- On "what replaces categories": don't remove them — **keep categories as a FILTER** (they're how numerosity gets split, §3), just stop making them the decoration.

## 3. Anchor "maps" — 30–40 splits without mess (the big one) → Track D
Polygon rendering already exists; formalize a **multi-map view system**:
- **Exact borders, not rectangles:** default to **polygon outlines** (true segment); rect only as last-resort fallback for a region with no polygon (Track B must supply polygons). Fix the alignment bug (§1).
- **View "maps" (toggle):**
  - *Quiet map* (default when many): each region a **low-weight marker** (faint vertex/dot or hairline outline) so 40 regions don't shout; hover/tap reveals the full polygon + label.
  - *Outline map:* exact thin polygon borders, shown for the **active category** or on hover/focus.
  - *Focus mode:* select one → it's emphasized; **all others fade to near-invisible.**
- **Category-split viewing:** filter by category → only that set renders on image + list → numerosity split → less mess (your "divided sections").
- **Progressive/lazy reveal:** coarse first, "reveal N more" for fine (matches Track B on-tap SAM2).
- **Bidirectional clickability:** regions clickable on the image AND in the synced list; click → select → comment → remember.
This IS Track D's "non-messy reveal of many parts" — inject it as the concrete spec.

## 4. Pane responsiveness (shrink/expand breaks both panes) → split
- At narrow width the region panel **crams and overlaps** (buttons collide, text wraps vertically). Global CSS doesn't adapt to *pane* width (which is independent of the viewport).
- Plan: make each pane's internals responsive to **its own width** via CSS **container queries**, with per-pane breakpoints:
  - Visual pane narrow → controls collapse (tabs → icon menu; action buttons → Dissect + overflow; parts list → compact rows); image stays contain.
  - Content pane narrow → single column, tighter.
- Also **raise the split min-width clamp** — 20% is below the region panel's usable width (that's the mess). Set a min that keeps each pane usable, or a "too narrow → auto-collapse to rail" rule.
- Ownership: **region-component container queries = Track D**; **split-pane min-width clamp = Drishya** (Lane 2 follow-up).

## 5. Writing pane expandable (empty margins) → Drishya
- `.content-area { max-width: 56rem }` (70rem editing), centered → empty side margins when the pane is wide.
- Plan (resolve readability-vs-fill): **EDIT mode → let the writing surface expand** (fluid measure / raise max-width; editing wants room). **READ mode → keep a comfortable measure (~65–75ch) but fill the margin with CONTEXT** (the Aletheia reading strip / a right rail), so the space is purposeful, not empty. Don't just widen text into an unreadable line length.

## More areas to finetune (found)
- **Neon/glassmorphism "Split→Save / Save all"** buttons overlapping the image → clean toolbar (Track D kill-list).
- **SVG `preserveAspectRatio="none"` bug** → polygons misalign; must match the image's rendered box.
- **Dissect loading/empty/error states** (segmentation is slow) → skeleton/progress, not a frozen pane.
- **"No story yet" in a huge empty pane** → ties to §5.
- **Token consistency** → retire the neon manual editor; keep the token-clean surface (Track D kill-list).
- **Keyboard/a11y for regions** → arrow through parts, Enter to select, focus ring on the active polygon.

## Coordination summary
- §1, §2, §3, and the region-component half of §4 → **hand to the Darshan Track D thread as Phase-1 requirements** (it's building this exact component now).
- Split min-width (§4) and writing-pane measure (§5) → **Drishya frontend**, serialized on `PostDetailPage.jsx` via the pause-slot.
- Do NOT build region-surface UI on the Drishya thread — it would collide with Track D.
