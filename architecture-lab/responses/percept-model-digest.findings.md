# The Percept model — digested for Semant's architecture

**What this is:** a translation of the ChatGPT "Percept / Mention / Relation" brainstorm into *our* codebase and the four-layer lens — what each idea means, what we already have, what's genuinely new, and what to build now vs defer. No app code.

---

## 0. The one load-bearing idea
> **A region should not merely be *linked* to text — it should have an identity that *travels*.** One stable identity, many embodiments: a shape in the **Field**, a chip in the **Manuscript**, an evidence block, a margin object, a memory in **Anuraṇana**.

Everything else is machinery for that. It's the line between "Notion + image analysis bolted together" and a new medium where a visible fragment crosses into thought and stays alive on both sides. And note: **the "crossing" is literally what Chiasm means** — the Perceptual Margin below is the chiasm made spatial.

---

## 1. The core move: split **Region** (ground) from **Percept** (attention)
| | Owns | Created | In our code |
|---|---|---|---|
| **Region** | geometry, polygon/box, detector, `part`, `attributes`, `embedding_id`, `parent_region_id` — the **visual ground truth** | by machines, for *every* detectable fragment (40+) | **already exists** (`schemas/post.py`) |
| **Percept** | the *attention* object built around a region: `label`, `description`, `tags`, `primary_lens`, `status`, `actor` | only when something **enters attention** (remember / note / `/part` / mentioned / Aletheia-promoted / audience threshold) | **new** (start as a product-layer composition, not a table) |

Why it matters to us: today the temptation is to keep bolting fields onto `Region` (note, block_id, reading, comparisons…). That's the "god object" the lens warns against. **Freeze `Region` as the visual ground; grow meaning as separate objects around it.** When SAM2 later remasks a region, the Percept still points at the same thing — geometry improves without disturbing meaning. (This is Track A's "don't let the region carry every relationship," made concrete.)

Not every Region gets a Percept. `Region` = everything the system can distinguish; `Percept` = what entered intellectual attention. One Region *can* carry multiple Percepts (three readings of one drape); v1 rule can be **one creator Percept per region per post** (`unique(region_id, actor)`), with readings/notes multiplying beneath it.

---

## 2. Why `block_id` isn't the final link — the **Mention** join
Today: `Region.block_id` / `Highlight.block_id` = **one region → one block.** Reality:
- one region appears in **many** blocks (intro, comparison, conclusion, an AI block, a later essay)
- one block discusses **many** regions (drape + open back + neckline)

→ **many-to-many**, which a single field can't hold. The link becomes its own object:

```
PerceptMention { id, percept_id, document_id, block_id, inline_content_id, form: inline|block, relation_type: cites|describes|interprets|compares|contrasts|questions|synthesizes, actor }
```

`inline_content_id` is needed because one block can hold several inline refs (`The [shoulder drape] contrasts with the [open back]`) — `block_id` alone can't tell them apart.

**This is not abstract — it's exactly the PR #34 / BlockNote-Phase-3 question we're in.** "`/part` in many blocks, a block about many parts" is precisely why the current bidirectional-highlight (built on `block_id`) needs a join behind it. Keep `block_id` as the *primary/original* attachment during migration; make the Mention join the real system.

---

## 3. The rest of the relationship family (later layers — don't build all now)
- **PerceptRelation** (percept↔percept: `contrasts_with`, `part_of`, `echoes`, `intensifies`…) — the *interpretive* graph. **Distinct from `Region.parent_region_id`**, which is *anatomical/spatial* (detector-derived). Spatial hierarchy ≠ interpretive relation — different fields, on purpose.
- **PerceptReadingLink** (percept↔Aletheia reading: `evidence_for`, `challenges`, `extends`) — formalizes what we half-have (per-lens `region_ids` in `lens_registry`/`local_context.aletheia`). Lets `/lens` insert a reading while preserving which parts support it.
- **PerceptNote** — a lightweight provisional observation (our `user_note`, promoted). "Note = provisional; Mention = placed in authored writing."
- **Percept embeddings** — later: a *semantic/interpretive* vector (from note + reading + prose) beside the Region's *visual* vector. Visual embedding answers "looks similar"; semantic embedding answers "noticed in similar language" → the Anuraṇana query *"where do I keep noticing restraint-becoming-release."*

---

## 4. Provenance chain — keep `actor` and `origin` distinct (we already do)
`Region.actor` (auto/creator/audience — who produced the signal) ≠ block `origin` (human/sutradhar — who authored the prose). The full chain is valuable:
```
Region.actor=auto  →  Percept.actor=creator  →  Mention.actor=human  →  TextBlock.origin=sutradhar
(detector found it) (creator promoted it)    (human placed it)      (Sutradhar wrote about it)
```
We already have both fields; the brainstorm just says don't collapse them. Agreed.

---

## 5. What this means for BlockNote persistence
- Custom blocks/inline store **references, not copies**: `{ perceptId, regionId, mentionId, origin, displayMode }`. Never embed the polygon/notes/readings in the block — that creates stale copies.
- HTML round-trip must **preserve the `data-*` attributes** (`data-percept-id`, `data-region-id`, `data-mention-id`, `data-inline-type`). This is a specific, testable requirement on the **Phase-1 converter gate** — `blocksToHTMLLossy` must not drop these as "incidental decoration."

---

## 6. The UX layer (Structure/Behaviour) — the product's soul, built *on* the model
Five verbs frame the Studio: **NOTICE → LIFT → PLACE → RELATE → RECALL.**
- **Lift** — click a region and its clipped contour (SVG `clipPath`) rises from the image as a draggable Percept (its silhouette *is* its identity) — dramatizes "I admit this detail into thought."
- **The Perceptual Margin** — a *transient* staging space between Field and Manuscript (not a permanent 3rd pane) where percepts gather, arrange, compare before entering prose. The bridge. (= Chiasm made spatial.)
- **Two embodiments** — inline mention (prose rhythm; `@`/light trigger) vs evidence block (sustained attention; `/part`).
- **Bidirectional attention** — hover a chip → its region illuminates, others dim, sibling mentions reveal; click a region → cycle its mentions in the text.
- **Perceptual Recall, not autocomplete** — near the cursor, surface *relevant percepts* (Tab to insert evidence), then generate language. "Retrieve the world the language answers to," not "guess more sentence."
- **Ground this claim** — select prose → propose supporting regions → evidence-bound interpretation.
- **Perceptual verbs** — Bring evidence · Compare these parts · Find tension · Show the parent whole · Ground this claim · Weave selected parts · Find where this recurs — verbs that act across image↔region↔reading↔memory↔prose, not generic Continue/Rewrite.
- **Percept biographies** — a part accumulates history across posts ("seen in 4 images, mentioned in 7 passages, recurring interest: restraint→softness") — makes Anuraṇana tangible.

---

## 7. Orchestrator's honest assessment
**Strong, coherent, and mostly additive.** It doesn't fight our stack — Region/actor/embeddings/readings already exist; this adds a *relationship layer* on top plus a *UX bridge*. The genuinely new pieces are: the **Percept** as a distinct attention-object, the **Mention** join, the later relation/reading/note joins + semantic embeddings, and the Margin/lift/recall UX.

**The trap is premature complexity** — building all nine tables and the Margin at once. Guard it with the brainstorm's own layering:
- **Adopt now (minimal, and it's what Chiasm assembly needs anyway):** `Region` (have it) + **Percept** (product-layer composition first — a thin object/store, not a DB migration) + **Mention** join (region↔block many-to-many; keep `block_id` as primary during migration). This directly backs the `/part`/highlight/write-about-part features being merged in PR #34.
- **Second layer (after the bridge feels good):** `PerceptNote`, `PerceptRelation`, `PerceptReadingLink`.
- **Third layer (Anuraṇana depth):** cross-post percepts, semantic embeddings, taste patterns.

**Sequencing:** the UX (Lift, Margin, Recall) is the soul but *sits on the data model* — don't build the Margin before the Mention join exists. So: Chiasm assembly (Field + Manuscript + Mention-backed links) → then Lift/Margin/Recall as their own phase.

---

## How it changes the Chiasm assembly
Back the Field↔Manuscript links with a **Mention join**, not just `Region.block_id`:
1. `Region` stays the frozen visual ground.
2. `Percept` = a product-layer identity around an attended region (thin; not a table yet).
3. A **Mention** record for every appearance (inline or block) — many-to-many; `block_id` kept as the primary attachment for back-compat.
4. The **shared store** both panes read (already built, `9ea55c4`) extends from "regions + reading" to "regions + percepts + mentions."
5. BlockNote custom blocks/inline store references + `data-*` attrs the converter preserves.
Then Lift / Margin / Perceptual-Recall / perceptual-verbs land as the next phase — the actual invention.

## Decisions for Adarsh
1. **Percept now as a product-layer composition** (no DB table yet) vs a real backend model from the start? (Rec: composition first — keep momentum, promote to a table when the second layer lands.)
2. **Mention join now** (region↔block many-to-many, `block_id` kept as primary) — confirm we introduce it as the backing for `/part`/highlight rather than extending `block_id`? (Rec: yes — it's the correct backing for the exact feature we're merging.)
3. **Build order:** Chiasm assembly (Mention-backed links) → then the Lift/Margin/Recall UX as its own initiative? (Rec: yes — model before bridge.)
4. Anything here you want to *cut* as over-scope (e.g. spatial-arrangement→prose, biographies) vs keep on the roadmap?
