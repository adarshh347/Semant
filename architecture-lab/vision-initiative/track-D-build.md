# Track D — full build spec: the premium unified Visual pane (phased)

**To:** the Darshan / Track D thread (builds on `feat/vision-pipeline`). Tracks under umbrella issue #22.
**Sources:** `responses/track-D-frontend.findings.md`, `architecture-lab/frontend-finetune-plan.md`, and Adarsh's `vault/the orchestrator's writing section/list of updated work.md` (the two screenshots).
**Spirit (Adarsh):** be flexible — do the *full* work on this topic, don't stop at a track boundary. The goal is a Visual pane that feels premium and survives 40 parts + any pane width without mess.
**Rules:** verify UI by SCREENSHOT at multiple pane widths + keyboard; backend/logic by test. Conventional commits on `feat/vision-pipeline`. Every phase ends with a handoff (commits, evidence, flags, next). **Phase 4 edits the shared `PostDetailPage.jsx` → serialize via the pause-slot; pull first, confirm the Drishya thread is paused.**

---

## Phase 1 — the self-contained `RegionSurface` component (NO PostDetailPage edit)
Promote `RegionDetectorModal`'s clean, token-based body into a standalone live component. This is the heart; do it fully.

**Geometry & the "maps" system (the anchor art):**
- **Polygons by default** — render the true segment outline (`r.polygon` already supported); rect only as last-resort fallback when a region has no polygon. **Fix the `preserveAspectRatio="none"` bug** so the SVG overlay tracks the image's *rendered* (letterboxed) box — today polygons drift off the pixels.
- **Three view "maps" the user can toggle**, so 30–40 parts never shout:
  - *Quiet map* (default when many): each region a **low-weight marker** (hairline outline / faint vertex); hover/tap reveals full polygon + label.
  - *Outline map:* exact thin polygon borders for the **active category** or on hover/focus.
  - *Focus mode:* select one → emphasized; **all others fade to near-invisible.**
- **Progressive/lazy reveal:** coarse first, "reveal N more" for fine parts (matches Track B on-tap SAM2).

**The panel (kill "block vibes"):**
- **Foreground the felt unit:** each part is a calm reading row — *part name · its reading · your felt note* — whitespace-grouped, few borders (border-grammar).
- **Demote the taxonomy:** the 6 category tabs (General/Garments/Body/Textures/Materials/Composition) + coarse/mark become a **quiet filter/menu**, not a stacked control wall. Categories stay — as the **filter that splits numerosity** (view one category at a time) — just not as decoration.
- **Bidirectional clickability:** regions clickable on the image AND in the parts list; selecting one highlights the other (the proven pattern generalised).
- **Pick → comment → remember:** select → "how it affects me" note → save to `region_annotations` → shows saved state on return.

**Responsiveness (survive any pane width):**
- Use CSS **container queries** so the component reacts to **its own width**, not the viewport. Narrow → controls collapse (tabs → icon menu; action buttons → Dissect + overflow; parts rows compact); image stays `contain`. Wide → full controls. This fixes the "mess on the left when shrunk."

**Craft & states:**
- **Kill-list:** delete glassmorphism / neon / emoji islands (the old `BoundingBoxEditor` styling, the overlapping "Split→Save / Save all"); keep the token grammar the modal already follows. Clean enough that Track F's one-tap consumer variant falls out of the same surface.
- **Loading / empty / error** states for Dissect (segmentation is slow) — skeleton/progress, never a frozen pane.
- **Keyboard/a11y:** arrow through parts, Enter to select, focus ring on the active polygon.

Verify: screenshots at wide / default / narrow widths + a 40-region case; keyboard walk-through. Component still mounts nowhere real yet (dev harness / story).

## Phase 2 — full-screen / lightbox image mode
Click the image → it fills the viewport with annotations overlaid, **zoom + pan** for detail. Reuses Phase 1's rendering at full size. This is the dedicated "see the image properly" feature (fixes the "image gets cut / feels small" complaint).

## Phase 3 — Aletheia in-pane
Fold Track C's context-triggered reading into the pane as a **calm reading strip**; each lens's `region_ids` **highlight the matching polygons** on the image (reading and geometry co-located). Removes the need for a separate Unconceal tab.

## Phase 4 — mount swap + retire the old systems (EDITS PostDetailPage.jsx — SERIALIZED)
Only after 1–3 are proven. **Coordinate with the Drishya thread via the pause-slot; pull first.**
- Slot-gated swap: replace `BoundingBoxEditor` in the Visual pane with `RegionSurface`.
- Retire the **Unconceal tab** (reading + commentary now live in the pane), and the old `BoundingBoxEditor` / `/crops` / pixel system.
- One focused pass; screenshot the integrated pane in read + edit modes; handoff.

---

## Explicitly NOT Track D (Drishya thread, separate, serialized)
- Split-pane **min-width clamp** (raise from 20% so a pane can't get narrower than usable).
- Writing-pane **measure** (edit-mode expands; read-mode fills the margin with the reading strip, not emptiness).
These touch the shell, not the region component — hand to the Drishya frontend thread.

## If a phase is still too big
Phase 1 is the largest — it may split into **1a geometry + maps** (polygons, view modes, alignment fix, responsiveness) and **1b panel + loop** (felt rows, taxonomy-as-filter, pick→comment→remember, states, a11y). Ship 1a first (the visible win), then 1b.
