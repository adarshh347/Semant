# Chiasm assembly — build spec: converge Field + Manuscript into one workspace

**To:** Claude Code — the **Chiasm integration session** (owns `PostDetailPage.jsx`). **Mode:** build.
**Sources:** `responses/percept-model-digest.findings.md` (the model), `blocknote-migration.build.md` (Manuscript engine), `responses/track-D-frontend.findings.md` (the advanced Field), `vault/Project Context/Names — Chiasm, Field, Manuscript.md` (lexicon), taste spec **v1.3** (plum).
**What Chiasm is:** the convergence of the **advanced Field** (RegionSurface/Overlay/Lightbox + the shared store, on `feat/vision-pipeline`) with **Manuscript** (BlockNote, Path B), joined so a region can travel into the writing. This is the assembly, not new invention — the pieces exist; wire them into one workspace and back the links with a Mention join.

## Locked decisions (baked in — do not re-litigate)
- **Names:** workspace = **Chiasm**, visual pane = **Field**, writer pane = **Manuscript** (rename labels/components as you touch them; route rename `/posts→/chiasm` is a later pass — keep `/posts/*` now).
- **Percept = a product-layer composition, NOT a DB table yet** — a thin client object/store identity around an attended region. Promote to a backend model later.
- **Mention join = the link system now** (many-to-many region↔block). Keep `Region.block_id` / `Highlight.block_id` as the **primary/original** attachment for back-compat, but new `/part`/highlight/write-about-part go through **Mention** records: `{ id, percept_id|region_id, block_id, inline_content_id, form: inline|block, relation_type, actor }`. `inline_content_id` distinguishes multiple refs in one block.
- **Editor:** BlockNote **Mantine** variant, plum tokens. Inline AI on our endpoints, **not `@blocknote/xl-ai`**.
- **PR #34 resolves via Option 2** (re-wire first, no regression) — this spec *is* that re-wire.

## Rules (`workflow-protocol.md`)
- **This session alone edits `PostDetailPage.jsx` and the editor/Field files.** The OSS session (`feat/oss-foundation`) stays out. `git pull` before starting; serialize.
- Verify UI by **screenshot**; verify the links/converter by **data test** (Mention round-trip + `block_id` + `data-*` attrs survive HTML round-trip). Conventional commits; one umbrella issue "Chiasm assembly"; handoff each phase. Stop after each phase for review.

---

## Phase 0 — Converge the branches (no feature work)
Bring the advanced Field onto the Chiasm base: merge/rebase `feat/vision-pipeline`'s Field (`RegionSurface`, `RegionOverlay`, `RegionLightbox`, `regionRef`, the shared store `9ea55c4`, and the `/part`/highlight/write-about-part commits) together with the BlockNote work. Resolve PR #34 keeping BlockNote **and** these features (Option 2). Get a clean tree that builds; nothing wired yet beyond what already worked. **Stop — confirm the base is green.**

## Phase 1 — The shared store: regions + reading → + percepts + mentions
Extend the existing shared store both panes read (`9ea55c4`) so it holds: `regions`, `reading` (Aletheia), and NEW **`percepts`** (a thin `{id, regionId, label, note?, lens?, actor}` created on attention) and **`mentions`** (`{id, perceptId|regionId, blockId, inlineContentId?, form, relationType, actor}`). One source of truth for Field↔Manuscript. Keep it a small store (Zustand-style); no backend table. **Stop.**

## Phase 2 — Field in place
Mount the advanced Field (RegionSurface + Overlay + Lightbox) as the **Field** pane of Chiasm (replacing the old modal/pixel path per Track D). Selecting/attending a region writes a **Percept** into the store (one creator percept per region per post). Verify at multiple pane widths + the lightbox zoom. **Stop.**

## Phase 3 — Manuscript = BlockNote, reading the same store
Complete the BlockNote migration (`blocknote-migration.build.md` Phases 1–5) *against the shared store*: Manuscript renders one `<BlockNoteView>`; the **converter preserves block ids AND the `data-*` reference attrs** (`data-percept-id`, `data-region-id`, `data-mention-id`, `data-inline-type`) through the HTML round-trip — this is the gated test, not incidental. Blocks still emit `data-block-id`. **Stop.**

## Phase 4 — The links, Mention-backed (the Field↔Manuscript intelligence — no regression)
Re-wire, through the store + Mention records (block_id kept primary):
- **`/part`** → a BlockNote **block-form** custom block; stores refs `{perceptId, regionId, mentionId, origin, displayMode}`, writes a Mention `form:"block"`.
- **inline mention** (`@` or light trigger) → BlockNote **inline** custom content, the `[shoulder drape]` chip; writes a Mention `form:"inline"` with an `inline_content_id`.
- **bidirectional highlight** — select a Field region → its mentions highlight in Manuscript; hover a chip → its region illuminates, others dim (drive both from the store, generalising the old `data-block-id` scrollIntoView).
- **write-about-part** → same endpoint, seeds a block `origin:"sutradhar"` + a Mention.
Backend/data unchanged. Verify parity: none of these regress vs the Path-A versions. **Stop.**

## Phase 5 — The split shell
Replace the hand-rolled divider with **react-resizable-panels** for the **Field | Manuscript** split (min/max clamp, collapse preset "focus the writing", persist width via `autoSaveId`). Retire the unused `allotment`. **Stop.**

## Phase 6 — Verify the whole
Screenshots (Chiasm read + edit, light+dark, mobile, lightbox); data tests (Mention round-trip; `block_id` + `data-*` survive save→reload; a region cited in 2 blocks highlights both; a block citing 2 regions resolves both). Delete Path A editor files once parity holds. Handoff.

---

## Explicitly NOT in this assembly (next initiative)
The **embodiment UX** — Lift-the-region-out-of-the-image, the **Perceptual Margin**, Perceptual-Recall-instead-of-autocomplete, perceptual verbs, Percept biographies — is the *soul* but it **sits on this model**. Build it as its own initiative AFTER assembly is green. Also out: PerceptRelation / PerceptReadingLink / PerceptNote as tables, semantic embeddings, cross-post percepts (second/third layers).

## If a phase is too big
Phase 3 (BlockNote) is largest → split 3a converter+body-swap, 3b delete-Path-A. Phase 4 → 4a `/part` block + highlight, 4b inline mention + write-about-part.
