# R0 — Reality map

**Gate:** R0 (read-only). **Branch:** `feat/rehearsal-research-r0` off merged `main`
(`99e92b3`, PR #56 merged — verified). **No app changes, no data changes.**

Classification: **production-real** (user hits it on a real route) · **stranded** (works but only
via a stub/legacy seam) · **lab-only** · **placeholder** (UI, no logic) · **theoretical**
(prose/comment only) · **absent**.

## Capability inventory

| Capability | Status | Where / evidence |
|-----------|--------|------------------|
| Region + canonical `mask_rle` geometry | **production-real** | `mask_geometry.py`; A–F; F recovery raised legacy box/polygon → masks (41/42 dissected) |
| SAM refine · domain profiles · YOLO/SegFormer/DINOv2/FashionCLIP · ModelManager | **production-real** | orchestrator adapters; F2 matrix all green |
| Semantic (VLM) reading, geometry-forbidden | **production-real** | `semantic_provider` (OpenRouter gpt-4o-mini), `POST /{id}/semantic-read` |
| Embeddings + similarity retrieval (Find similar) | **production-real** | E0–E6; `region_embedding_service`, `retrieval_service`, `find_similar_service`; Differential **Similar** tool |
| Ground types (region/field/path/boundary/frame + constellation/relation) | **production-real, single-image** | `differential/grounds.js`; persisted `post.grounds` |
| Percept — **expression** (`pctx_…`, expression + ground_ids + properties) | **production-real** | composed in `DifferentialWorkspace`; persisted `post.percepts` (5 exist corpus-wide) |
| Percept — **attention** (`pct_{actor}_{regionId}`, one/region) | **stranded/ephemeral** | `perceptMentions.js` "thin client composition, NOT a DB table"; reconstructed from markup |
| Mention (region/percept ↔ block join) | **implemented but not durable** | no backend table; only `data-*` attrs in `text_blocks` HTML, rebuilt by `mentionsFromBlocks()` |
| Writer (BlockNote Manuscript) | **production-real** | `blocknote/Manuscript.jsx`, right pane of `/posts/:postId` when editing |
| Insert Region/Lens/**Percept** chip via slash + `@` | **production-real but UNEXERCISED** | `refSlashItems` + `RefPicker`; **0 percept mentions in any post** (Mongo) |
| Chip click → mask highlight (`focusRegions`) | **production-real** | `PostDetailPage` `onFocus`/`chipClickRef` → `RegionSurface` overlay |
| Percept chip click → **recall** animation on image | **production-real but unexercised** | `recall.js` `buildRecallScript`/`useRecallPlayer` → `GroundLayers` on the stage |
| AI "write about this part" (server-grounded) | **production-real** | `epicService` + `editor_llm_service` + Anuraṇana grounding; from the **Visual pane**, not the slash menu |
| Manuscript slash "AI" Draft/Continue/Rewrite | **placeholder** | `AI_STUB`, inserts empty block, "wires in Phase 4" |
| TipTap Path-A editor | **stranded/dead** | "RichTextBlock is no longer rendered"; refs kept only to resolve |
| **Atlas** (cross-image structure) | **theoretical** | prose only (`MotivePage`, `architecture-lab/differential-atlas-codex-bridge.md` "Mode: concept"); no route/collection/component |
| **Codex** (narrative duration/diagnostics) | **absent** | zero code hits anywhere |
| History / event / **inquiry** / session state | **absent** | no event log / attention trace / inquiry collection; undo is BlockNote in-memory only |
| `agent_run_collection` | **production-real, unrelated** | research-article job queue only |
| Anatomy catalog | **production-real, unrelated** | `AnatomyPage` ↔ `anatomy_catalog` |
| Dev harnesses | **lab-only** | `/lab/{blocknote,manuscript,region-surface,refine}` (unlinked) |

## The circulation circuit, and where it actually stops

```text
canonical mask (real) → Ground (real) → expression Percept (real, in Mongo)
  → [chip into Writer]  CAPABILITY REAL, but 0 real uses — unexercised
  → chip click → recall on image  CAPABILITY REAL, unexercised
  → contextual ROLE (evidence/counterpoint/hinge)   ✗ not stored (mention = 'cites' only)
  → cross-image structure (Atlas)                    ✗ ABSENT
  → narrative duration (Codex)                       ✗ ABSENT
  → return-with-question/role/relation packet        ✗ ABSENT (recall replays; carries no inquiry)
  → investigative history / passage record           ✗ ABSENT
```

**Two honest readings of the stop:**
1. **Adoption/verification gap, not a code gap** for Percept→text→recall: the machinery exists and
   is wired on the real route, but no one has driven a real percept through it (0 mentions). This
   must be *rendered-verified*, not assumed working.
2. **Structural absence** for everything past the single image: contextual role, Atlas, Codex,
   return-packet, and inquiry history genuinely do not exist. These are where new work (if any)
   would live — but only after rehearsals prove which are needed.

## Bearing on the program's central question

The program asks whether a Percept-under-contextual-use needs an **Embodiment**, whether history
needs a **Passage/Inquiry**, and which earn persistence. R0 finds:
- The **Mention already carries** region/percept + block + inlineContentId + `relationType` — but
  **no contextual role, no active-Grounds set, no recall pose, no epistemic distance**. Whether
  Mention can *absorb* those (vs a new PerceptEmbodiment) is an open, testable question — exactly
  what R2/R3 rehearsals and the foundry must decide, not R0.
- **No inquiry/history object exists at all** — so a Passage/Inquiry has nothing to extend; it
  would be genuinely new. Its necessity is unproven and must come from rehearsal failure.
- **Nothing about geometry, curator identity, or provenance is at risk** in R0 — all invariants
  hold; F preserved them.
