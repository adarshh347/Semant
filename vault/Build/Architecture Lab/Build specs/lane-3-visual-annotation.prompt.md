# Lane 3 — Inside the Visual pane: stats bar, image, bounding boxes, tag list

**To:** Claude Code (local, in this repo)
**Mode:** deep read + architecture proposal. **Do not edit any app code.** Write findings only.

## Why this lane exists
The image is the point of the left pane, but it's sandwiched between a stats strip on top and a tag list on the bottom, and each drawn box carries heavy furniture. This lane finds the optimal structure for the annotation tool so the picture can breathe.

## Files to read
- `frontend/src/components/BoundingBoxEditor.jsx` (full) — `.bbox-editor-wrapper` → `.bbox-stats-bar` (emoji stats, View Crops, eye toggle) → `.bbox-editor-container` (img + overlay boxes) → `.bbox-tag-form.glassmorphism` → `.bbox-tags-list.glassmorphism`.
- Per-box overlay: `.bounding-box` with `.bbox-label`, `.corner-badges` (2 buttons), `.bbox-tooltip`, and eight `.resize-handle`s (lines ~304–369).
- `frontend/src/components/BoundingBoxEditor.css` (full) — especially `.glassmorphism`, `.bbox-stats-bar`, `.bbox-tags-list`, `.resize-handle`.
- How it's mounted: `PostDetailPage.jsx` lines ~549–551 (`.image-display` → `BoundingBoxEditor`), and the `Image / Annotations` tabs (~533–546) — note the tabs exist but `BoundingBoxEditor` renders the same thing regardless of tab.

## Questions to answer (architecture only)
1. **Two chrome strips around the image.** The stats bar (count, coverage %, View Crops, visibility eye) sits above; the tags list sits below. Which of these are essential to keep on-screen at all times vs on-demand? Propose one consolidated, quiet chrome (or move the tag list into the `Annotations` tab, which currently does nothing).
2. **The unused tab split.** `Image` vs `Annotations` tabs both render the same `BoundingBoxEditor`. Propose what each tab *should* structurally contain (e.g. Image = clean view, Annotations = the box list + management), so the tabs earn their place.
3. **Per-box furniture.** Each box always carries label + 2 corner buttons + tooltip + 8 handles. Propose the minimum: what shows always vs only when a box is selected/hovered. Keep draw, resize, delete working.
4. **Style island.** `.glassmorphism` and emoji icons (🏷️ 📊 ✂️ 👁️ ✏️ 🗑️) appear here but nowhere else. Flag every instance. (We won't restyle now, but note them for consistency later — the *structural* question is whether the tag form/list should be separate glass panels at all.)
5. **Emoji-as-icon.** List each emoji used as a control icon; note that the rest of the app uses lucide-react icons. Structural note only.

## Hard constraints
- Structure only. No colour/font/spacing decisions (but you may flag the style island for a later lane).
- Keep drawing, resizing, deleting, and the visibility toggle fully working.
- No app code — a plan.

## Output contract → write to `responses/lane-3-visual-annotation.findings.md`
- **Current Visual-pane tree** — every wrapper from `.bbox-editor-wrapper` down, with file+line refs.
- **Essential vs on-demand table** — element | always visible? | proposed home.
- **Tab proposal** — what Image vs Annotations should each hold.
- **Per-box minimal spec** — what furniture survives and when it appears.
- **Consistency flags** — emoji + glassmorphism instances (for later).
- **Questions for Adarsh.**
