# Creative horizons — OSS *projects* to harvest ideas from

**Mode:** discovery. Beyond tooling *libraries*, these are whole open-source *products* adjacent to each Semant surface. Harvest the **model/pattern/interaction** (mostly study-and-reimplement, not drop-in deps). Licence caveats flagged.

---

## ★ Top creative unlocks (do these read first)
1. **PixPlot** (Yale DH) — a WebGL scene that lays out **thousands of images by visual similarity** (CNN embeddings → UMAP/TSNE), pannable like a map. **You already compute FashionCLIP embeddings** → this turns the Archive "Wall" into a **taste-map**: your collection clusters by look, you pan a landscape of it, and Percepts/Anuraṇana become *visible terrain*. The single most on-brand creative harvest. (Open source.)
2. **AFFiNE** — "Notion + Miro": docs **and** an edgeless canvas in one app, CRDT collab. This is literally the **Atlas + Codex fusion** — study how it lets you switch between writing a document and arranging on a canvas without them being separate tools. (Open source.)
3. **immich** — the polished self-hosted photo archive: its **timeline scrubber** flies through 40k+ photos instantly, plus map + CLIP natural-language search. The exact UX for your "reach the old ones fast." (Open source.)
4. **Langflow / Flowise** — visual **LLM node canvases**: drag nodes, wire them, *run* the flow. This is the **agentic Atlas** execution model — arrange a graph, an agent carves prose from it. Study the node→run pipeline. (Permissive OSS; n8n is Fair-Code — flag.)

---

## By surface

### Archive (browse thousands)
| Project | Harvest | Caveat |
|---|---|---|
| **immich** | timeline scrubber, map view, CLIP text search, "memories" | study UX; it's a full app, not a component |
| **PhotoPrism** | AI labels, search at 100k+, places/colors facets | facet/search model |
| **PixPlot** | **similarity map of thousands** (WebGL) → the taste-map Wall | reimplement on your embeddings |
| **Collection Space Navigator** | multi-dim dataset browsing UI (academic) | interaction ideas |

### Home
| Project | Harvest | Caveat |
|---|---|---|
| **AFFiNE / AppFlowy / Anytype** | knowledge-home dashboards, block/widget composition, local-first feel | model, not code |
| self-hosted dashboards (Homepage, Dashy) | glanceable widget arrangement patterns | infra-flavored; ideas only |

### Atlas (skeleton-map, agentic)
| Project | Harvest | Caveat |
|---|---|---|
| **AFFiNE** | edgeless canvas ↔ docs fusion, blocks-on-canvas | the fusion model |
| **Langflow / Flowise** | node-graph → runnable LLM pipeline; node/port UX | the agentic execution pattern |
| **Excalidraw** | delightful freeform canvas, hand-feel | MIT; canvas UX |
| **Obsidian Canvas / Logseq** | linking notes on a spatial board; graph view | Obsidian not OSS; ideas |

### Codex (long-form novel)
| Project | Harvest | Caveat |
|---|---|---|
| **Manuskript** | **Scrivener-like corkboard**, Snowflake method, scene cards | conceptual model |
| **bibisco** | **character interviews, strand/thread tracking**, premise, locations | the novel-*architecture* model — maps onto Atlas nodes |
| **Plottr** | **visual timeline, character arcs, series** | timeline/arc UX |
| **novelWriter** | files + metadata, **cross-referencing between documents** | the "docs-as-graph" idea = Codex page graph |

### Chiasm / Percept (image ↔ writing, annotation)
| Project | Harvest | Caveat |
|---|---|---|
| **Recogito (Pelagios)** | **semantic annotation of images *and* texts with tags + relations** — humanities precedent for exactly Chiasm's linked reading | the annotation+relation model |
| **Hypothesis** | web annotation, anchoring, threads | anchoring model |
| **Annotorious** (lib) | draw/edit mechanics (already noted) | mechanics only |

---

## What each unlocks for us, concretely
- **PixPlot → the Archive taste-map + Percept clustering.** Reuse `region_embeddings`; images and percepts laid on a similarity landscape = Anuraṇana made spatial. Doubles as a browse mode *and* a taste-visualization.
- **immich scrubber → "reach old images fast"** (the archive Jump mode), proven at scale.
- **AFFiNE → how Atlas and Codex coexist** — one workspace, canvas and prose, not two rooms. Validates the fusion, shows the pitfalls.
- **Langflow → the agent-node model** — how "arrange nodes → run" feels; informs the Atlas "carve" verbs and node/port design.
- **bibisco/Plottr → the Codex story model** — strands, character arcs, corkboard, timeline map onto Atlas node/edge types (character, thread, beat) so we don't reinvent narrative structure from scratch.
- **Recogito → validation of Chiasm** — a scholarly tool already does image↔text semantic annotation with relations; confirms the shape and offers UX to borrow.

## How to use this (not a shopping list)
These are **study-and-harvest-the-model**, not adopt-the-app. For each: read how they solve the interaction, take the *pattern*, reimplement on our stack (plum, our Region/Percept/Mention spine). The only near-drop-in candidates are the *libraries* under them (React Flow for Langflow-style canvas; a WebGL/regl layer for PixPlot-style maps). Watch licences: **n8n Fair-Code, tldraw prod-licence** → avoid as deps; AFFiNE/immich/PixPlot/Recogito are for *ideas*.

## Questions
1. **PixPlot taste-map** — worth prototyping as the Archive "Wall" mode (it uses embeddings you already have)? I think it's the standout unlock.
2. **AFFiNE study** before Atlas/Codex — want me to distill its canvas↔doc fusion into concrete do/don'ts for our build?
3. Any surface here you want a **deep single-project teardown** on (e.g. immich's scrubber, bibisco's strand model)?
