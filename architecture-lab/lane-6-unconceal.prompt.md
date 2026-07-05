# Lane 6 — The Unconceal tab: anatomy + Aletheia + commentary

**To:** Claude Code (local, in this repo)
**Mode:** deep read + architecture proposal. **Do not edit any app code.** Write findings only.

## Why this lane exists
Unconceal is "a world in itself": three separate tools stacked in one long scroll, and its Anatomy overlaps with the Visual pane's Annotations. This lane decides its internal structure and resolves the duplication.

## Files to read
- `frontend/src/components/PostDetailPage.jsx` unconceal branch (~865–949):
  - `.unconceal-intro`.
  - `.uncon-anatomy` — `.uncon-block-head` (kicker + "Detect parts" btn) + part chips OR empty; opens `RegionDetectorModal`.
  - `.uncon-aletheia` — head + "Read the image" btn + `.uncon-lens` list (name, intensity, bar, reading) + concealed/uncertain foots.
  - `.uncon-commentary` — kicker + textarea.
  - `.uncon-actions` — feed-to-persona checkbox + "Attach context" + saved timestamp.
- State + handlers: `aletheia`, `runAletheia` (~402), `saveLocalContext` (~417), `showAnatomy`, `region_annotations`.
- `frontend/src/components/RegionDetectorModal.jsx` — the anatomy detector it launches.
- Compare with Lane 3: `BoundingBoxEditor` also marks image regions (`bounding_box_tags`). **These are two systems for marking parts of an image.**
- `frontend/src/components/PostDetailPage.css` — all `.uncon-*` rules.

## Questions to answer (architecture only)
1. **Three tools, one scroll.** Anatomy, Aletheia, and Commentary each have their own head/kicker and stack vertically. Propose the optimal internal structure — steps? accordion? sub-tabs? a two-part "machine reading (Aletheia + Anatomy) vs your reading (Commentary)" split? Structural only.
2. **The big duplication.** `bounding_box_tags` (Visual pane, Lane 3) and `region_annotations` / Anatomy (here) both mark parts of the image but are separate data and separate UI. Map both: their data shape, where each is created, where each is shown. Then recommend: merge into one region system, or keep separate with a clear reason. This is the most important question in this lane.
3. **Where does Anatomy belong?** Given the duplication, should "Detect parts" live in the Visual pane (with annotations) rather than inside a Content tab? Weigh both placements structurally.
4. **Save model.** `.uncon-actions` saves commentary + aletheia + feed toggle together. Is this one save the right unit, or should machine-reading and human-commentary save separately? Structural note.
5. **Intro band.** `.unconceal-intro` is an explanatory paragraph section. Keep, shrink to chrome, or drop structurally?

## Hard constraints
- Structure only. No colour/font/spacing.
- Keep Aletheia reading, anatomy detection, commentary, feed toggle, and save all working.
- No app code — a plan.

## Output contract → write to `responses/lane-6-unconceal.findings.md`
- **Current Unconceal tree** — with file+line refs.
- **Region-systems comparison** — `bounding_box_tags` vs `region_annotations`: data, creation point, display point, overlap.
- **Merge-or-keep recommendation** — with the reason and the rough code surface it touches.
- **Proposed Unconceal structure** — leanest internal layout for the three tools.
- **Questions for Adarsh.**
