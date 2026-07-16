# Narrative studio — the Atlas (structure) + the Codex (long-form)

**Mode:** vision + architecture shaping. No app code.
**The one idea:** everything Chiasm built — `Region → Percept → Mention → Reading`, grounded and cross-linked — was for *one image*. Scale the same primitives to **long-form narrative**. Two new surfaces, one shared spine:
- **Codex** — the Manuscript in long-form: many connected pages/chapters, percept-aware.
- **Atlas** — a structure-first *map* you build (nodes + relations, no prose), then an **agent carves a story from it**.

Both draw on the same grounded objects, so writing (or generating) always **answers to the seen**. This is the deferred "embodiment UX" (Lift / Perceptual Margin / Recall) generalised into a full narrative studio.

> **Naming (proposals, optional):** **Codex** (a bound book of pages) for the long-form work; **Atlas** for the map — after **Aby Warburg's *Bilderatlas Mnemosyne***, the historical precedent for *arranging image-fragments spatially to make meaning*. That is almost exactly this feature; the name carries real lineage (Warburg → Didi-Huberman → us).

---

## Surface A — Codex: the long-form Manuscript
**What it is:** the standalone Manuscript, opened as a multi-page work — a novel/essay/collection — that can pull in images, regions and percepts from *across* the corpus, not one post.

**What's new vs today's Manuscript:**
1. **A Work = ordered/linked Pages.** Each Page is a BlockNote document (the editor we already have). A Codex is a small graph of Pages (chapters + threads), navigable as an outline.
2. **Cross-document Percepts (Study 4 realised).** A percept — "the restrained shoulder drape" from image 12 — can be Mentioned in chapter 3 *and* chapter 7. The Mention join already does many-to-many; it just gains a `document_id`/`page_id`. This is the trigger to **promote Percept from a product-layer composition to a real backend entity** (as the region/percept study flagged).
3. **The perceptual library (Field-as-drawer).** In the Codex, the Field isn't one image — it's a **drawer** of images/regions/percepts you summon and cite. Writing chapter 4, you pull "the drape" in as evidence. (This is the Perceptual Margin, docked.)
4. **Page connections.** Pages reference each other, characters, and percepts → a backlink graph over the novel (Study 2's citation graph, now narrative-scale: "every chapter that touches this motif").

**Backend:** a `Work`/`Page` model (a Page ≈ today's `text_blocks` doc, decoupled from a single image); `Percept` promoted to a table with cross-document identity; `Mention` gains page scope. Everything else (BlockNote, converter, origin, the store) reused.

---

## Surface B — Atlas: structure-first, agentic
**What it is:** you **don't write prose** — you build a **skeleton-map**: nodes and typed relations. Then you tell an agent to **carve the story from the map**. The *arrangement is the prompt.*

**Node types** (all can be grounded): **beat/scene**, **character/entity**, **motif**, **tension**, **percept** (a real region-as-attention, carrying its crop + readings), **reading** (an Aletheia lens). 
**Edge types** (typed relations — reuse + extend PerceptRelation): `precedes`, `causes`, `contrasts_with`, `echoes`, `tension_with`, `intensifies`, `releases`, `part_of`. 
The graph *is* the story's structure before any sentence exists.

**The agentic conversion (the payoff):** an agent reads a sub-graph (nodes + relations + attached percepts/readings) and generates prose, grounded. Operations = the "perceptual verbs" from the earlier brainstorm, at narrative scale:
- *Carve the scene from this beat + these motifs* · *Write the tension between these two nodes* · *Write this thread as escalation / from the centre out* · *Expand this beat into a chapter* · *Suggest the missing beat between A and C.*
Because percept nodes carry real crops + felt-readings + the author's accrued taste (Anuraṇana), the output is **evidence-bound**, in the author's voice — not generic autocomplete. Generated prose lands in a **Codex page**, with Mentions written back (so the map and the manuscript stay linked).

**Backend / agentic shape:** a `graph` model (nodes, edges); a **story agent** = plan (read the sub-graph) → retrieve grounding (percepts, readings, taste via RAG over Anuraṇana) → generate → place into a Page + write Mentions. This is where "good backend and agentic shape" lives — a grounded, structure-driven generation pipeline, not a chat box.

**OSS:** **React Flow (xyflow, MIT)** — the standard node-and-edge canvas; ideal for the Atlas. (tldraw is more freeform but its core needs a **production licence** — flag; use only if you want whiteboard-style freedom and accept that. React Flow is the safe pick.)

---

## How they connect — the pipeline
```
Field (see)  →  Percepts (attention)  →  Atlas (arrange structure)  →  Codex (carve prose)
                         └────────── Anuraṇana (taste + memory) grounds every step ──────────┘
```
- **Chiasm** = one image · read · write. **Atlas + Codex** = many images · structure · long-form. Same primitives, corpus scale.
- The **Atlas is the Perceptual Margin generalised** — the staging ground between perception and prose, now with agentic generation.
- Perception never leaves: a beat can be *pinned to a percept*, so the novel's structure is anchored in things actually seen.

---

## What more can be incorporated
- **Character/entity biographies** — recurring entities with their own history (like Percept biographies): where a character appears, their arc, linked percepts (a costume, a gesture).
- **Motif tracking across the novel** — Anuraṇana already finds recurring visual motifs; extend to narrative ("restraint→release" recurs in ch. 2, 5, 9) → a motif index.
- **Timeline / corkboard view** of the Atlas (Scrivener-like) — reorder scenes spatially or on a timeline.
- **Variant branches** — non-destructive story alternates (`/version` at narrative scale); compare drafts.
- **Agentic structure critique** — the agent proposes missing tension, a flat arc, an unearned turn — co-*architect*, not just co-writer.
- **Export** — a Work → docx/epub/PDF.
- **Collaboration** (Yjs, already in BlockNote's stack) — co-authoring the Atlas + Codex.
- **Taste-grounded voice** — the novel generates in the author's accumulated Anuraṇana signature, the moat of Track E.

---

## Build shape (don't build it all at once)
This is a **later initiative** — after Chiasm + Home/Archive land, and it *subsumes* the deferred Lift/Margin/Recall UX. Sequence it, MVP first:

1. **MVP-Codex:** standalone Manuscript opened as a **2-page Work** with a **perceptual drawer** to cite cross-image percepts. Proves multi-page + cross-document Mentions. (Needs Percept promoted to a real entity — the one real backend step.)
2. **MVP-Atlas:** a **React Flow canvas** with 3 node types (beat · percept · tension) + typed edges, **read-only-to-prose one verb**: "write the tension between these two percept nodes" → a grounded paragraph into a Codex page. Proves the arrangement→agent→prose loop end to end on the smallest slice.
3. **Grow:** more node/edge types, the full verb set, motif/character tracking, timeline, variants, export, collab.

Guard: same discipline as the Percept model — **promote to backend only when a surface needs it**, keep the node/edge graph thin at first, one verb before ten.

---

## OSS / tech
| Need | Pick | Note |
|---|---|---|
| Node-graph canvas (Atlas) | **React Flow / @xyflow/react** | MIT, the standard; nodes+edges+pan/zoom |
| (freeform alt) | tldraw | core needs a **production licence** — flag; only if whiteboard freedom wanted |
| Long-form editor (Codex) | **BlockNote** | already in; multi-page = many documents + an outline |
| Agentic generation | existing LLM services + a **story-agent** orchestrator | plan→retrieve(RAG over Anuraṇana)→generate→place+Mention |
| Collab (later) | **Yjs** | already in BlockNote's stack |
| Export (later) | docx/epub libs | a Work → manuscript file |

---

## Questions for Adarsh
1. **Names:** **Codex** (long-form) + **Atlas** (map, Warburg hook) — keep, or other words?
2. **Sequencing:** confirm this is a *later* initiative (after Chiasm + Home/Archive), and that it **replaces** the separately-planned Lift/Margin/Recall UX (the Atlas subsumes it)?
3. **First slice:** MVP-Codex (multi-page + perceptual drawer) *or* MVP-Atlas (the agentic map→prose loop) first? I lean **MVP-Atlas** — it proves the boldest, most differentiating claim (structure→agent→grounded prose) on the smallest surface.
4. **Percept promotion:** OK to promote `Percept` to a real backend entity when this lands (the cross-document identity forces it)?
5. **Scope of the agent:** co-writer (generate prose) only, or also co-architect (critique/propose structure) — the latter is more novel but bigger.
