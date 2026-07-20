# Region & Percept — a staged study of the architecture

**How to read this:** one idea at a time. This installment covers the **map** (so you see the whole landscape once, lightly) and then goes deep on **Study 1 only**. The rest are named but not unpacked — say "next" and I'll expand one. Not everything at once, on purpose.

---

## The map — five frontiers the Region/Percept split opens
Each is a possibility the *separation* creates. Awareness only; depth comes later, one at a time.

1. **Decoupling as resilience** — Region = frozen visual ground; Percept = meaning around it. Geometry can change (SAM2 remask) without disturbing thought. *(Study 1 — below.)*
2. **The citation graph** — Mentions make region↔writing many-to-many → backlinks, "every passage that interprets this part," an Obsidian-for-images. *(Study 2.)*
3. **Two retrieval spaces** — a *visual* embedding (Region: "looks alike") and a *semantic* embedding (Percept: "noticed in similar language") → hybrid search. *(Study 3.)*
4. **Percept as a corpus object** — the same attended part recurs across posts → cross-image memory, the tangible form of Anuraṇana. *(Study 4.)*
5. **Percepts as the context substrate** — the perceptual graph becomes the retrievable ground the writer/AI stands on → context engineering over *seen fragments*, not documents. *(Study 5.)*

Keep the whole map in view, but we only *build* left-to-right, and we only *study* one node at a time.

---

## Study 1 — Decoupling as resilience (the foundational move)

**The claim:** splitting Region from Percept is not bookkeeping — it's what lets the system *change underneath* without breaking meaning above. This is the single most important architectural property, so we start here.

### What is coupled today
Right now a mark tends to carry everything at once: a `Region` row holds geometry *and* the note *and* (via `block_id`) its one link to writing. So the visual object and the intellectual object are the same row. That means every time the *meaning* grows (a second note, a comparison, a citation), you either add a nullable field to `Region` or you're stuck. And every time the *geometry* changes (a better mask), you risk disturbing the meaning attached to it.

### The decoupling
```
Percept (meaning: label, note, lens, tags, status)      ← changes often, human-paced
   │  points to
   ▼
Region (geometry: polygon, box, detector, embedding)    ← changes rarely, machine-paced
```
Two objects, two *rates of change*, two *owners*. The Region is the stable referent; the Percept is the mutable interpretation. The link is a pointer, not a merge.

### Why this is the load-bearing property (three concrete payoffs)
1. **Geometry can improve silently.** Fashionpedia gives a rough box today; SAM2 gives a clean mask next month. If meaning lived *on* the region row, re-detection would either orphan the note or force a migration. With the split, SAM2 rewrites `Region.polygon` and the Percept — its label, its readings, its place in your essay — never notices. *The ground can shift; the building stands.*
2. **Meaning can multiply without schema churn.** One drape, three readings ("restraint," "release," "ceremony") = three Percepts (or three notes under one), zero new columns on Region. New intellectual moves become new *rows in relationship tables*, never new nullable fields on the ground object. This is the exact opposite of the god-object trajectory (`Region { polygon, note, block_id, reading, related, comparison, ai_text, taps... }`) that eventually collapses under its own optionality.
3. **Two clocks, two scaling strategies.** Regions are many (40+/image), machine-produced, embedding-heavy → they scale like a *detection pipeline* (batch, cache, sidecar the vectors). Percepts are few (the handful you attend to), human-produced, meaning-heavy → they scale like *documents* (edited, versioned, queried). Conflating them forces one storage/caching strategy on two very different workloads. Splitting lets each scale on its own terms.

### The architectural position (where this leaves us)
- `Region` becomes a **closed** object — you stop adding fields to it. Its job is fixed: *where is this, what produced it, what does it look like.* That stability is a feature.
- `Percept` starts as a **product-layer composition** (a thin identity in the shared store, no table) — cheap, reversible — and is promoted to a real model only when the second layer (relations, notes-as-rows) needs persistence. You buy the decoupling *now* without paying for a schema *yet*.
- The pointer direction matters: **Percept → Region**, never the reverse. The ground doesn't know who's looking at it; the observers know what they're looking at. (This is also why a Region can carry many Percepts later without any change to Region.)

### The one-line principle to protect
> **Region is the stable visual referent; Percept is the interpretation that points at it. Meaning changes at human speed, geometry at machine speed, and neither is allowed to break the other.**

That property — *change underneath without breaking above* — is what every later frontier (the citation graph, the two embedding spaces, the corpus memory) quietly depends on. Get this one right and the rest have somewhere solid to stand.

---

### Next
Say **"next"** for **Study 2 — the citation graph** (what Mentions make possible: backlinks, "who interprets this part," the many-to-many mechanics and how they scale). One at a time.

---

## Study 2 — the citation graph (what Mentions make possible)

**The claim:** the moment the link between a region and the writing becomes its own object (a **Mention**), the relationship stops being a *field* and becomes a *graph* — and graphs answer questions a foreign key never can. This is the "Obsidian-for-images" frontier, and Phase 1 just laid its foundation.

### From field to graph — what actually changed
A field points one way and holds one value:
```
Region.block_id → "block-47"        (one seat, one direction, no meaning)
```
A Mention is a **typed, directional edge with identity**:
```
Mention { id, perceptId, blockId, inlineContentId, form, relationType, actor }
```
Because it has an id, it can be counted, ranked, reversed, and queried. Because it has a `relationType`, the graph knows not just *that* a part is referenced but *how* — cited, described, interpreted, compared, contrasted, questioned, synthesized. Because it has `inlineContentId`, it's precise even when one sentence names two parts.

### The four capabilities this unlocks (concrete)
1. **Backlinks — the reverse question.** A field answers "what block is this region attached to?" A graph answers the far more useful reverse: *"which passages mention this part, and how?"* From a shoulder drape you can now list every place it's cited, interpreted, or contrasted. This is the first real power of a Percept "biography" (Study 4) — and it's just an index over Mentions keyed by region, which `blockIdsForRegion` already is.
2. **Typed retrieval.** "Show me the blocks that *interpret* this part" vs "the ones that merely *cite* it." "Find every place I set up a *contrast*." The `relationType` turns the graph into something you can filter by intellectual move, not just presence.
3. **One identity, many embodiments — kept in sync.** The same Percept can be an inline chip in one sentence, a full evidence block later, and a margin object — three Mentions, one identity. Rename the percept once and every appearance updates, because they resolve *through* the percept, not by duplicated text. (This is transclusion, the thing that makes Notion/Obsidian feel alive — here for image fragments.)
4. **Attention as a signal.** A part mentioned in seven passages is load-bearing; one mentioned once is a footnote. Counting edges gives you a cheap, honest measure of what a piece is *actually about* — usable for ranking, for "jump to the most-discussed part," for surfacing a spine you didn't consciously plan.

### Why it scales (the reassuring part)
- **Mentions grow with writing, not with detection.** Regions scale with the image (40+ per photo, machine-made); Mentions scale with *what you choose to write about* — bounded, human-paced, small. The expensive axis (regions) and the graph axis (mentions) grow independently.
- **Two indexes cover everything:** by `regionId` (backlinks) and by `blockId` (what this block cites). That's a classic join table with two b-tree indexes when it moves to the backend — nothing exotic.
- **Idempotent, deterministic edges** (Phase 1's deterministic ids) mean re-hydration and re-saves never duplicate an edge. The graph is safe to rebuild from the document at any time — which is exactly how `mentionsFromBlocks()` reconstructs it with zero migration.
- **Graceful degradation:** `block_id` stays primary, so even a Mention-less link still highlights. The graph is an *enrichment* over a floor that already works — never a single point of failure.

### The architectural position
The Mention table is **the seam where Field and Manuscript meet as data**, not just as UI. Today it lives in the shared store (product-layer, correct for now). When it earns a backend home, it becomes: a `mentions` join table + one read endpoint (`GET /regions/{id}/mentions` = backlinks) + one on-save reconciler (diff a document's inline refs → upsert/retire edges). Everything above it — Percept biographies (Study 4), Perceptual Recall (Study 5) — is a *query over this graph*. Which is why building it now, thin and correct, is the highest-leverage move: it's the substrate the interesting features read from.

### The one principle to protect
> **The link is a first-class, typed, directional object — not a foreign key.** Meaning lives in the connections between parts and prose; connections need identity to be counted, reversed, filtered, and kept in sync. A field can hold *a* link; only a graph can hold a *practice* of attention.

Caveat to hold: the seven `relationType` values are a fine enum, but don't build UI for all seven at once — start with `cites` (inline) and `interprets` (block), add types when a feature needs them. The graph's power is in *existing*, not in being fully exposed on day one.

### Next
Say **"next"** for **Study 3 — two retrieval spaces** (why a Region's *visual* embedding and a Percept's *semantic* embedding answer different questions, and how hybrid search over both becomes Anuraṇana's engine).
