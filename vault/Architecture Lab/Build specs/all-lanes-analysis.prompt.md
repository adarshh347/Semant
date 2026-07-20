# All-lanes analysis — one pass, through the Purpose lens

**To:** Claude Code (local, in this repo)
**Mode:** deep read + architecture proposal across ALL lanes. **Do not edit any app code.** Research and plan only.

You already did Lane 5 well. Now do the whole page in one pass. Keep the Lane 5 findings you wrote; refine only if the cross-cutting view changes something.

## Read first
- `architecture-lab/00-architecture-map.md` — the map.
- `architecture-lab/07-purpose-lens.md` — the three axes (Purpose → Structure → Surface) and the page's new name **Drishya**. **Apply this lens to every component.**
- Each lane prompt: `lane-1` … `lane-6`. Follow each one's "Output contract."

## Do this
1. Work through **all six lanes**. For each, produce its findings file in `responses/` exactly as that lane's output contract specifies:
   - `responses/lane-1-top-chrome.findings.md`
   - `responses/lane-2-split-shell.findings.md`
   - `responses/lane-3-visual-annotation.findings.md`
   - `responses/lane-4-content-view.findings.md`
   - `responses/lane-5-writing-studio.findings.md` (already exists — update if needed)
   - `responses/lane-6-unconceal.findings.md`
2. In **every** lane, add a short **Purpose check**: for each major component, does it serve Drishya's purpose (read / mark / write / trace meaning)? Mark anything that is overhead or misplaced.
3. Cover these cross-lane questions explicitly (they live in `07-purpose-lens.md`):
   - **Block `origin` model** (human vs sutradhar): every place a block is created, and what it takes to tag origin. (Lane 5 / Lane 4)
   - **Editor-model decision:** lay out Path A (per-block editors + one shared toolbar) vs Path B (single-document editor with block nodes), each with effort, risk, and what it unlocks (origin marking, drag-reorder, inline AI). (Lane 5)
   - **Add-path + assistant convergence:** the three insertion paths and whether the inline composer and AI sidebar should be one surface. (Lane 5)
   - **Highlights in context:** use the existing `block_id` to link a highlight back to its place. (Lane 4)
   - **Region duplication:** `bounding_box_tags` vs `region_annotations` — merge or keep, with reason. (Lane 3 / Lane 6)
4. Write a **synthesis** to `responses/00-synthesis.md` containing:
   - **The 3–5 biggest decisions** Adarsh must make before any building (editor model, region merge, navbar collapse, tags' single home, block origin).
   - A **dependency order**: which fixes unblock others (e.g. block model before content restructuring).
   - A **do-no-harm list**: capabilities that must survive every change.
   - The **rename note**: `PostDetailPage` → `DrishyaPage` is planned for a later build pass, not this one — list the files/symbols it will touch so we know the blast radius.

## Hard constraints
- **Architecture + Purpose only. No Surface work** — no colour, font, or spacing decisions. You may *flag* Surface items (emoji icons, glassmorphism, 6 hardcoded hex swatches) in a short "Surface backlog" list for later, but do not act on them.
- **No app-code edits.** Every output is a plan.
- Preserve every existing capability. When you propose removing or merging, say what replaces the capability.
- Use real file+line references. Don't hand-wave.

## When done
Stop. Summarize in chat: the six findings files + the synthesis, and the top decisions waiting on Adarsh. Do not start building.
