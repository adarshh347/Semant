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
