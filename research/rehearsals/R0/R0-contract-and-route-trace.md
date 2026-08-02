# R0 — Contract + route trace (one Percept, end to end)

Traced object: **`pctx_mrpi3rjk_0`** on post `695be6c9…` (the five-sculpture collage), chosen
because it is a real, heterogeneous, multi-ground expression Percept whose evidence was recovered
in Vision F.

```yaml
percept:
  id: pctx_mrpi3rjk_0
  kind: expression
  expression: "there is facial geometric relation between gupta and pala faces"
  ground_ids: [gnd_mrpi1jbv_3, gnd_mrpi1jbv_4, gnd_mrpi1jbv_5]
  properties: [material, composition]
  actor: creator
```

## 1 — Canonical evidence (authoritative)

Three `region_annotations` on the post, each with authoritative `mask_rle` (F-recovered from box):
`fine_4` "Pala face", `seg_0` "person", `fine_2` "Gupta face". `mask_rle` is the identity;
polygons/box are derived (`mask_geometry.canonicalize_geometry`). **Invariant holds.**

## 2 — Grounds (evidence body, local)

`post.grounds` holds `gnd_mrpi1jbv_3 → region fine_4`, `…_4 → region seg_0`, `…_5 → region fine_2`
(each `{ground_type:'region', region_id, label, note, actor, detector, created_at}`). Grounds are
indexical — they mean nothing away from their pixels (bridge doc). One ground elsewhere in the
corpus is `field` type (brush strokes) — heterogeneous evidence is real.

## 3 — Percept (first propositional object)

`post.percepts` holds the record above. Composed in **DifferentialWorkspace** (Collect/Connect →
composer → `makeExpressionPercept`). It is the first object with propositional content that could
survive crossing the image boundary.

## 4 — API / storage

- **Write:** `regionStore.persistMeta` → `PATCH /api/v1/posts/{id}` with
  `{grounds: [...], percepts: [...].filter(isExpressionPercept)}` (debounced 800 ms).
  `post.percepts` / `post.grounds` are `Optional[List[dict]]` on `Post`/`PostUpdate`
  (`schemas/post.py`), kept **outside** `region_annotations` (which detect wholesale-replaces).
- **Read:** `GET /api/v1/posts/{id}` → `post_helper` returns grounds/percepts/semantics verbatim.

## 5 — UI surfaces that render or use it

| Surface | Route | Behaviour |
|---------|-------|-----------|
| Differential composer + percept row | `/posts/:postId` (mode) | ▶ per-percept → `playRecall(pctx_)` → `buildRecallScript` (recede → primary ground → supporting → expression) rendered by `GroundLayers` on the RegionSurface stage |
| RefPicker (`kind='percept'`) | `/posts/:postId` (editing) | lists `percepts.filter(startsWith 'pctx_')`; title = expression, badge = ground count; empty → "compose one in Differential" |
| Manuscript chip insert | `/posts/:postId` (editing) | `/percept` slash or `@` → `insertRef` records a Mention `{perceptId: pctx_…, regionIds: <the ground ids>, form:'inline', relationType:'cites'}` and inserts a `regionRef` inline chip `refKind:'percept'`, serialized as `data-percept-id` + `data-region-ids` in the block HTML |
| Chip click / focus | `/posts/:postId` | `perceptId.startsWith('pctx_')` → `regionStore.playRecall(perceptId)`; expands Field pane, scrolls `.rs-stage`; **recall replays on the image** |

## 6 — Mention / Writer

The Mention is **not a backend record**. Its only durable form is the chip's `data-*` attrs inside
`text_blocks` HTML, reconstructed on load by `mentionsFromBlocks()`. For **this** percept there is
**no chip anywhere** — `text_blocks` is empty and no post references any percept/ground id (verified
in Mongo across all 5 percept-bearing posts). So the trace reaches the Writer *only in principle*.

## 7 — Recall / return

`playRecall` re-performs the noticing (recede → grounds → expression) on the stage. There is **no
return packet**: recall carries no source block, question, contextual role, epistemic distance, or
relation — it is a replay, not a round-trip that changes thought.

## Where this Percept's circulation stops (precise)

1. **It never entered text** (0 mentions) — the Writer capability is real but *unexercised*; must be
   render-verified, not assumed.
2. **No contextual role** — even if inserted, the Mention stores `relationType:'cites'` only; no
   evidence/counterpoint/hinge role, no epistemic distance.
3. **No cross-image life** — Atlas is absent; the Percept cannot become a Motif member or cross-work
   relation.
4. **No duration** — Codex is absent; no awareness of the Percept's use across blocks/chapters.
5. **No inquiry memory** — nothing records the question/gesture that produced it or lets a return
   reopen it with that question intact.

## Contract invariants confirmed intact

`mask_rle` authoritative; polygon/bbox/crop derived; semantics never mutate geometry; curator
label/note/decision sticky; similarity = research not truth; a text reference *resolves* evidence
(chip → `focusRegions`/`playRecall`) and **copies no geometry** (it carries ids, not masks).
