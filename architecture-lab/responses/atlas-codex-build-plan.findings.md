# Atlas + Codex — build plan + supporting OSS

**Mode:** plan. No app code. Builds on `narrative-atlas-vision.findings.md`. **A later initiative** (after front-of-house); this is *how* to build it and *what OSS* helps.

---

## The OSS that makes these buildable (so we don't hand-roll graph/canvas/agent plumbing)

### Atlas (the node/edge skeleton-map)
| Need | Pick | Licence | Role |
|---|---|---|---|
| Node + edge canvas, pan/zoom, custom nodes | **React Flow (@xyflow/react)** | MIT | the core — our beat/percept/tension nodes are custom React nodes; typed edges |
| Auto-layout (arrange the map) | **dagre** (simple trees) / **elkjs** (advanced) / **d3-hierarchy** | MIT | "tidy the map" + tree/graph layouts; React Flow has ready examples |
| Graph state | **Zustand** | MIT | nodes/edges store both the canvas and the agent read from |
| (freeform alt) | tldraw | **prod licence** | only if whiteboard-style; flagged, not recommended |

### Codex (long-form, multi-page)
| Need | Pick | Role |
|---|---|---|
| Editor | **BlockNote** (have it) | each Page is a document; reuse the converter + Mentions |
| Page/outline tree | small custom + **dnd-kit** (have it) | reorder chapters/threads |
| Cross-doc links | the **Mention** join (have it) | gains `page_id`; many-to-many already works |
| Export (later) | docx/epub libs | a Work → a manuscript file |
| Collab (later) | **Yjs** | already in BlockNote's stack |

### The agentic layer (backend — where "good agentic shape" lives)
- Reuse the existing LLM services; add a **story-agent orchestrator**: **plan** (read a sub-graph) → **retrieve grounding** (percepts, readings, taste via RAG over Anuraṇana / `region_embeddings`) → **generate** → **place** into a Codex page + write Mentions.
- OSS to consider for orchestration: a light agent framework (e.g. **LangGraph** / **Pydantic-AI**) *only if* the flow gets multi-step; start with a plain planned pipeline — no framework until the steps justify it.

---

## Data model (minimal → grown)
- **`Percept` → promote to a real backend entity** (cross-document identity forces it; the region/percept study anticipated this). Keeps pointing at `Region`.
- **`Work` / `Page`** — a Work = ordered/linked Pages; a Page ≈ today's blocks doc, decoupled from one image.
- **`Mention`** — gains `page_id`; stays the region/percept↔writing join.
- **`GraphNode` / `GraphEdge`** — the Atlas: nodes (`kind`, refs to percept/reading/beat…), typed edges. Start client-first (Zustand), persist when it needs to survive reloads.
Guard (same as before): promote to backend only when a surface needs it; one node/edge type set before many.

---

## Phased build (MVP-first — prove the boldest claim on the smallest surface)

**Phase 0 — Codex-lite (multi-page Manuscript).** Open the standalone Manuscript as a **2-page Work** with a **perceptual drawer** to cite cross-image percepts. Proves multi-page + cross-document Mentions. (The one backend step: promote `Percept`.)

**Phase 1 — MVP-Atlas (the differentiator).** A **React Flow** canvas with **3 node types** (beat · percept · tension) + typed edges, and **one agent verb**: select two percept nodes + a `tension_with` edge → *"write the tension between these"* → a grounded paragraph lands in a Codex page, Mention written back. This proves **arrange → agent → grounded prose** end to end. Nothing else.

**Phase 2 — grow the Atlas.** More node/edge types, auto-layout (dagre), the fuller verb set (carve scene · expand beat · write as escalation · suggest missing beat), motif/character nodes.

**Phase 3 — grow the Codex.** Page graph + backlinks, timeline/corkboard view, variant branches, export.

**Phase 4 — depth.** Character biographies, motif tracking across the novel, agentic *structure critique* (co-architect), collab.

---

## How it reuses Chiasm (not a rebuild)
Field · Percept · Mention · Reading · BlockNote · the shared store · Anuraṇana — all reused. Atlas adds a graph; Codex adds pages; the agent adds orchestration. The pipeline **Field → Percepts → Atlas → Codex** is the same primitives at corpus scale, and the **Atlas subsumes the deferred Lift/Margin/Recall UX**.

## Recommended first move
**MVP-Atlas (Phase 1)** — it proves the most novel claim (structure → agent → evidence-bound prose) on the smallest slice, and it's the thing no competitor has. Codex-lite (Phase 0) can precede it if you'd rather land the multi-page writer first; I lean Atlas.

## Questions
1. First slice — **MVP-Atlas** (my rec) or **Codex-lite** first?
2. Confirm promoting **Percept to a backend entity** when this starts?
3. Agent scope at MVP — **co-writer** (generate) only; defer **co-architect** (critique)?
4. React Flow confirmed for the canvas (MIT, standard) over tldraw (prod-licence)?
