# Cognitive Database — Study Guide & Reading List

> Reference notes for the standalone **conceptual-journey / cognitive-database** project
> (complements Semant but independent). Covers embeddings, chunking, retrieval, graph
> structures, databases, schema, the limits of plain LLMs, and the horizons & limits of RAG.
> Compiled 2026-06-18. References verified against current (2025–26) sources where possible.
> arXiv IDs given only where confident; otherwise cited by title/author/year (easily searchable).

---

## How to read this (suggested order)

1. **Foundations** — what an embedding *is* and what RAG originally was (§1 first two items, §3 Lewis).
2. **The limits** — read §6 (LLM limits) and §7 (RAG/chunking limits) *early*. They explain *why* every later technique exists. This is the part you said you care about most.
3. **Chunking** (§2) — because, as you intuited, it silently sets the ceiling on everything.
4. **Retrieval** (§3) — dense/sparse/hybrid/rerank/agentic; how a query actually finds things.
5. **Graph structures** (§4) — the "channel for conceptual travel" layer; the heart of your project.
6. **Databases & schema** (§5) — where it all lives.

Read with one question in mind: *does this technique help or hurt the conceptual journey* — the multi-hop, contradiction-tolerant path between ideas — that is the whole point of your build?

---

## 1. Embeddings — types & what to study

An embedding maps text (or an image) to a vector so that "near in meaning ≈ near in space."
The crucial limitation to internalize: **similarity is a 1-hop neighborhood, not a path.** It tells
you what's adjacent, never what's *reachable by what route*. That gap is exactly why your project
needs a graph layer (§4).

### Families of embeddings
- **Static word vectors** (historical, but read once to understand the lineage): Word2Vec, GloVe.
  One vector per word, no context. Their failure (one vector for "bank") motivates everything after.
  - Mikolov et al., *Efficient Estimation of Word Representations* (Word2Vec), 2013, arXiv:1301.3781
  - Pennington et al., *GloVe*, EMNLP 2014.
- **Contextual / transformer embeddings**: BERT and descendants — the vector for a token depends on
  its sentence. This is the base of modern retrieval.
  - Devlin et al., *BERT*, 2018, arXiv:1810.04805
- **Sentence / passage embeddings** (what you'll actually use for retrieval): one vector per
  chunk, tuned so semantically-similar passages are close.
  - Reimers & Gurevych, *Sentence-BERT*, 2019, arXiv:1908.10084 — **read this one properly.**
  - Wang et al., *E5: Text Embeddings by Weakly-Supervised Contrastive Pre-training*, 2022, arXiv:2212.03533
  - Xiao et al., *C-Pack / BGE embeddings*, 2023, arXiv:2309.07597 (strong open models; BGE-M3 does dense+sparse+ColBERT in one model)
- **Late-interaction / multi-vector embeddings** (ColBERT)** — instead of one vector per chunk,
  keep one vector *per token* and score by fine-grained token-to-token max-similarity. More
  accurate, especially for technical terms (your *dhvani / spanda / pratibhā* problem), at higher
  storage cost. **Very relevant to a philosophy corpus.**
  - Khattab & Zaharia, *ColBERT*, 2020, arXiv:2004.12832
  - Santhanam et al., *ColBERTv2*, 2021, arXiv:2112.01488
- **Matryoshka embeddings** — one model emits vectors you can truncate to fewer dimensions with
  graceful quality loss (store 256-dim for fast first pass, 1024-dim for rerank). Now an industry
  default (Gemini, Voyage, OpenAI v3, Cohere v4, Nomic, Jina).
  - Kusupati et al., *Matryoshka Representation Learning*, 2022, arXiv:2205.13147
- **Multimodal (image↔text) embeddings** — for the Semant tie-in (retrieve theory *from an image*):
  - Radford et al., *CLIP*, 2021, arXiv:2103.00020 (and successors like SigLIP).

### How to pick one (don't trust a single leaderboard)
- **MTEB** is the standard benchmark; learn to read it, but know it's gameable and English-skewed.
  - Muennighoff et al., *MTEB: Massive Text Embedding Benchmark*, 2022, arXiv:2210.07316
  - Live leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- 2025–26 landscape (managed + open): NV-Embed-v2, Qwen3-Embedding, Cohere embed-v4, OpenAI
  text-embedding-3-large, Voyage-3, BGE-M3, Gemini Embedding. Practical comparisons:
  - https://modal.com/blog/mteb-leaderboard-article
  - https://app.ailog.fr/en/blog/guides/choosing-embedding-models
- **For your domain specifically:** general leaderboards are misleading. A model that tops MTEB on
  web text can be mediocre on dense continental-philosophy prose and worse on Sanskrit-derived
  terminology. Build a tiny in-domain eval set (20–30 query→passage pairs you judge by hand) and
  test 3–4 models on *that*. This single habit beats chasing leaderboards.

---

## 2. Chunking — why it quietly decides everything

You're right that chunking sets the horizon. The mechanism: you embed *chunks*, so a chunk is the
smallest thing retrieval can ever return. Cut badly and the connective tissue of an argument is
severed before any model sees it. But note the precise limit (§7): chunking doesn't stop you from
*connecting distant sections* — vector search jumps across the whole corpus freely — it stops you
from preserving the *internal continuity* of an argument and from *composing* hops into a path.

### Strategies, roughly weakest → strongest
1. **Fixed-size / token-window** (e.g., 512 tokens, 50 overlap). Fast, dumb, splits mid-sentence.
2. **Recursive / structural** — split on paragraph → sentence boundaries; respects document
   structure. The sane default.
3. **Semantic chunking** — start a new chunk when embedding similarity between sentences drops
   (topic shift). ~Best accuracy in benchmarks but ~10–14× slower to build.
4. **Proposition / "dense-X" chunking** — decompose text into atomic factual statements and index
   those. Great for facts; risky for philosophy, where meaning lives in the *qualification*, not the
   atom. Use with care.
   - Chen et al., *Dense X Retrieval: What Retrieval Granularity Should We Use?*, 2023, arXiv:2312.06648
5. **Late chunking** — embed the *whole document* first (long-context encoder), then pool token
   embeddings into chunks afterward, so every chunk vector "remembers" the surrounding context.
   Efficient; preserves cross-boundary meaning.
   - Günther et al. (Jina AI), *Late Chunking*, 2024, arXiv:2409.04701
6. **Contextual retrieval (Anthropic)** — prepend an LLM-generated one-line context ("This is from
   Heidegger's *Building Dwelling Thinking*, discussing…") to each chunk *before* embedding.
   Reported ~49% fewer retrieval failures, ~67% with reranking — a bigger gain than upgrading the
   embedding model. **High-leverage and cheap; do this.**
   - Anthropic, *Introducing Contextual Retrieval*, Sept 2024: https://www.anthropic.com/news/contextual-retrieval
7. **Hierarchical / parent-child ("small-to-big")** — embed small chunks for precise matching, but
   feed the LLM the larger parent passage. Best of both.

### Read for comparison
- *Reconstructing Context: Evaluating Advanced Chunking Strategies for RAG*, 2025, arXiv:2504.19754
  (head-to-head of late chunking vs. contextual retrieval).
- Late chunking vs. contextual retrieval, the math: https://medium.com/kx-systems/late-chunking-vs-contextual-retrieval-the-math-behind-rags-context-problem-d5a26b9bbd38
- Practical 2026 playbook: https://www.digitalapplied.com/blog/rag-chunking-strategies-2026-retrieval-quality-playbook

**For a philosophy corpus specifically:** chunk on *argumentative* units (a move, a claim + its
hedge), not byte counts; keep the translator/edition in metadata; prefer late or contextual chunking
so a passage about "care" still knows it sat inside the analysis of temporality.

---

## 3. Retrieval — how a query finds things

### The core methods
- **Sparse / lexical (BM25)** — exact term matching. Old, unbeaten for rare technical terms and
  proper nouns. You will want it precisely because of words like *spanda*.
- **Dense** — embed query and chunks, nearest-neighbor search. Catches paraphrase and meaning.
  - Karpukhin et al., *Dense Passage Retrieval (DPR)*, 2020, arXiv:2004.04906
- **Hybrid (the current standard)** — run both, fuse with **Reciprocal Rank Fusion (RRF)**. Almost
  always beats either alone.
  - Cormack et al., *Reciprocal Rank Fusion*, SIGIR 2009.
- **Reranking (two-stage)** — retrieve ~100 cheaply, then a **cross-encoder** reads each
  (query, chunk) pair jointly and re-scores the top 10. Big accuracy win; the single best
  bang-for-buck add-on after hybrid.
- **Query transforms**:
  - **HyDE** — have the LLM write a *hypothetical answer*, embed *that*, and retrieve with it
    (answer↔answer is closer than question↔answer). Note this is also your bridge from *image* to
    *theory*: generate the lens's draft reading, then retrieve with it.
    - Gao et al., *Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE)*, 2022, arXiv:2212.10496
  - **RAG-Fusion** — generate several query rewrites, retrieve for each, RRF-fuse.
- **The original RAG paper** (read it once for the mental model):
  - Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP*, 2020, arXiv:2005.11401
- **Agentic / self-correcting RAG** — the model decides *whether* and *what* to retrieve, critiques
  results, retries. This is where multi-hop conceptual journeys actually get orchestrated.
  - Asai et al., *Self-RAG*, 2023, arXiv:2310.11511
  - Yan et al., *Corrective RAG (CRAG)*, 2024, arXiv:2401.15884
  - Singh et al., *Agentic RAG: A Survey*, 2025, arXiv:2501.09136
- **Survey to anchor it all**: Gao et al., *Retrieval-Augmented Generation for LLMs: A Survey*,
  2023, arXiv:2312.10997.

### Benchmark / how-to references
- BEIR (zero-shot retrieval benchmark): Thakur et al., 2021, arXiv:2104.08663
- Hybrid + RRF + cross-encoder, explained with code: https://glaforge.dev/posts/2026/02/10/advanced-rag-understanding-reciprocal-rank-fusion-in-hybrid-search/

---

## 4. Graph structures — the channel for conceptual travel

This is your project's core. The reason a graph exists at all: it gives **reachability through named
relations** — the multi-hop *journey* dense similarity structurally cannot compose. Model it as
**stable nodes + plastic, possibly-contradictory edges**, and let the graph *accrete from journeys
taken* rather than be drawn up front (see prior design discussion).

### GraphRAG (text → graph → retrieval)
- **Microsoft GraphRAG** — LLM extracts an entity/relation graph from the corpus, clusters it into
  "communities," summarizes them; great for global/multi-hop "sense-making" questions, expensive to
  build. Read first.
  - Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization*, 2024, arXiv:2404.16130
  - Project hub: https://graphrag.com
- **HippoRAG** — neurobiologically-inspired; builds a KG and runs **Personalized PageRank** to do
  associative, memory-like multi-hop retrieval. Conceptually close to your "journey" intuition.
  - Gutiérrez et al., *HippoRAG*, NeurIPS 2024, arXiv:2405.14831
- **LightRAG** — lighter, dual-level (low-level entities + high-level themes) graph indexing; cheaper
  than Microsoft GraphRAG, good starting codebase.
  - Guo et al., *LightRAG*, 2024, arXiv:2410.05779
- **Surveys / "when is a graph worth it"** (read before committing to the cost):
  - *Graph Retrieval-Augmented Generation: A Survey*, 2024, arXiv:2408.08921
  - *When to use Graphs in RAG: A Comprehensive Analysis*, 2025, arXiv:2506.05690
  - Curated list: https://github.com/DEEP-PolyU/Awesome-GraphRAG

### Knowledge-graph embeddings (representing the graph as vectors)
Useful if you later want "find concepts that relate to X the way Y relates to Z" (analogical
traversal) — relations become geometric operations.
- **TransE** — relation = translation (h + r ≈ t). Simple; weak on many-to-many. Bordes et al., NeurIPS 2013.
- **ComplEx** — complex-valued; models asymmetric relations. Trouillon et al., 2016, arXiv:1606.06357.
- **RotatE** — relation = rotation in complex plane; captures symmetry, inversion, composition.
  Sun et al., 2019, arXiv:1902.10197.
- **DistMult** — bilinear, symmetric-only baseline. Yang et al., 2014, arXiv:1412.6575.
- Survey: Wang et al., *Knowledge Graph Embedding: A Survey of Approaches and Applications*, IEEE TKDE 2017.

### Hypergraphs (relations among >2 concepts — fits philosophy better)
Binary edges distort claims like "embodiment binds *dwelling* + *perception* + *the question of the
subject*." Hyperedges keep the n-ary shape.
- Feng et al., *Hypergraph Neural Networks (HGNN)*, AAAI 2019, arXiv:1809.09401
- Follow citations to HyperGCN, AllSet, hypergraph transformers for the current state.

---

## 5. Databases & schema

### Vector databases (2025–26)
Decision rule from current benchmarks: **already on Postgres → pgvector; otherwise → Qdrant; reach
for Milvus only at very large scale.** You're on MongoDB Atlas, which adds a fourth path.
- **MongoDB Atlas Vector Search** — `$vectorSearch` lives next to your documents; zero new infra if
  you're already on Atlas (you are, for Semant). Best "don't add a database" option.
  https://www.mongodb.com/products/platform/atlas-vector-search
- **pgvector** — vectors inside Postgres; documents + embeddings + SQL filters in one transaction.
  Maxes out ~10–100M vectors. Great if you want a real relational schema for the graph too.
- **Qdrant** — Rust, purpose-built, excellent payload filtering and hybrid; the open-source default
  if you're not tied to Postgres/Mongo.
- **Weaviate** — AI-native, built-in vectorization + some graph features (slower on complex traversal).
- **Milvus / Zilliz** — billion-scale, GPU; overkill until you're huge.
- **LanceDB** — embedded, serverless, file-based; ideal for local/desktop and experiments.
- Comparisons: https://www.firecrawl.dev/blog/best-vector-databases · https://www.zenml.io/blog/vector-databases-for-rag

### Graph databases
- **Neo4j** — the default property-graph DB + Cypher; mature, has vector index + a GraphRAG package.
  Adopt when traversals get deep/hot. Don't start here.
- **Alternatives**: Memgraph (in-memory, fast), Kùzu (embedded, columnar — nice local analog to
  LanceDB), ArangoDB / NetworkX (in-process Python) for prototyping.
- **Pragmatic start:** model the graph as two collections/tables (`concepts`, `edges`) in the DB you
  already run (Mongo or Postgres). A few thousand concepts traverse fine without a graph engine.
  Migrate to Neo4j/Kùzu only when query shape demands it.

### Schema — a minimal sketch for *this* project
Designed around stable nodes / plastic edges / journeys-as-records:
- **Concept (node)** — `id`, `name`, `aliases[]`, `tradition`, `description`, `embedding`,
  `source_refs[]`, `stability` (anchor vs. emergent).
- **Passage (chunk)** — `id`, `text`, `work`, `author`, `translator`, `edition`, `locator`
  (section/page), `embedding`, `concepts[]` (extracted), `context_blurb` (for contextual retrieval).
- **Edge / Claim** — `id`, `source_concept`, `target_concept(s)` (allow n-ary → hyperedge),
  `relation_type` (influences / contrasts / grounds / critiques / co-articulates…),
  `attribution` (which commentator/text asserts it), `confidence`, `polarity`, `provenance_passages[]`,
  `contradicts[]` (link to rival edges — *contradiction is allowed, even encouraged*).
- **Journey (trace)** — `id`, `query`, `path[]` (ordered concept/edge sequence), `disclosure_text`,
  `groundedness_score`, `novelty_score`, `created_at`. The graph grows by saving these.

Key schema principle: **edges carry attribution, not truth.** Never store "X relates to Y"; store
"*per source S*, X relates to Y, polarity p, confidence c." That's what keeps the topology from
ossifying philosophy's plasticity.

---

## 6. Limits of plain LLMs (why you'd build this at all)

Read these to ground the project's *raison d'être* — and to stay honest about what RAG does and
doesn't fix.
- **Hallucination** — the canonical survey: Huang et al., *A Survey on Hallucination in LLMs:
  Principles, Taxonomy, Challenges, and Open Questions*, 2023, arXiv:2311.05232 (now in ACM TOIS).
- **Static / stale parametric knowledge** — the model's facts are frozen at training time and can't
  cite a source. (Covered in the RAG survey, arXiv:2312.10997.)
- **Long-tail blind spots** — LLMs reliably know popular facts and fumble rare ones; obscure
  philosophers / untranslated texts are exactly the long tail.
  - Kandpal et al., *Large Language Models Struggle to Learn Long-Tail Knowledge*, 2022, arXiv:2211.08411
- **Reversal curse** — trained "A is B," models often can't infer "B is A." A concrete demonstration
  that LLM "knowledge" isn't a navigable relational structure — i.e., *not a graph*. Strong
  motivation for an explicit graph layer.
  - Berglund et al., *The Reversal Curse*, 2023, arXiv:2309.12288
- **Lost in the middle** — models use info at the start/end of a long context and miss the middle;
  stuffing more text in the prompt is not a substitute for good retrieval.
  - Liu et al., *Lost in the Middle*, 2023, arXiv:2307.03172
- **No provenance** — a plain LLM can't tell you *which passage* a claim came from. For a
  philosophy/disclosure tool this is fatal; provenance is your anti-bullshit floor.

The honest framing (matches your own): you are **not** building "a more correct philosophy bot."
You're building a machine for *grounded conceptual travel* — routes between ideas that an LLM's
flattened parametric memory can't navigate and that similarity alone can't compose.

---

## 7. Horizons & limits of RAG (and the chunking ceiling)

What RAG buys you, and where it stops — so you know which walls the graph is meant to break.

**What RAG fixes:** stale knowledge, long-tail coverage, provenance/citations, controllability.

**What RAG does *not* fix (its real limits):**
- **Retrieval is the ceiling.** If the right passage isn't retrieved, the generator can't use it —
  and may confidently hallucinate around the gap. Garbage-in still applies.
- **Noisy retrieval can *worsen* output** — irrelevant chunks mislead the model; more context ≠
  better.
  - *When Retrieval Succeeds and Fails: Rethinking RAG for LLMs*, 2025, arXiv:2510.09106
  - Survey: *Mitigating Hallucination in LLMs: RAG, Reasoning, and Agentic Systems*, 2025, arXiv:2510.24476
- **Similarity ≠ relevance ≠ relationship.** Cosine-near isn't always *useful*, and is never a
  *path*. This is the structural wall: **single-vector retrieval is provably limited in which
  combinations of documents it can return** — multi-hop, compositional queries exceed what top-k
  similarity can express. (This is the formal version of your intuition; see the embedding-retrieval
  limitation literature and the GraphRAG surveys in §4.)
- **The chunking ceiling (your question, answered):** chunking does *not* prevent connecting distant
  sections — dense retrieval jumps across the corpus freely. What it prevents is (a) preserving the
  *internal continuity* of a single argument once it's cut, and (b) *composing* one similarity hop
  into the next. You can't chain "dwelling≈care" + "care≈temporality" into the route
  dwelling→care→temporality by similarity alone, because dwelling and temporality may not be near
  *each other*. So the smooth conceptual path you want is **unreachable by chunk-retrieval in
  principle, not just in practice** — which is precisely the gap the graph fills. Better chunking
  (late/contextual) raises the ceiling; only the graph changes the *kind* of thing retrievable from
  "neighbors" to "paths."

**The horizon (where it's heading, = your project):** plain RAG → hybrid + rerank → GraphRAG →
agentic/multi-hop retrieval over an attributed concept graph. The frontier isn't "retrieve a chunk";
it's "traverse a structure." That's the thing you're actually building.

---

## 8. Evaluation (carry forward from the design discussion)

Because this is a creative/disclosive field, eval is **2-axis, not true/false**:
- **Groundedness (the floor):** every leap traces to real passages. Measurable: citation
  faithfulness, "did it invent a connection?" checks. Survives even without truth.
- **Disclosure (the target):** novelty (path a plain LLM wouldn't surface), specificity/"sense"
  (cashes out concretely, isn't vague profundity), generativity (opens further questions — reuse
  Aletheia's `questions` mechanism), resonance (human-rated punctum).
- **The honest test:** A/B grounded vs. ungrounded on the same prompt — does grounding make outputs
  *more surprising AND more concrete*, or just more pretentious?
- Benchmarks worth knowing for the retrieval sub-problem: BEIR (arXiv:2104.08663); for RAG
  end-to-end, RAGAS and the "RAG triad" (faithfulness / answer-relevance / context-relevance).

---

## 9. One-paragraph build order (so the reading has a destination)

Corpus (one philosopher/tradition deep) → late/contextual chunking with rich metadata → hybrid
retrieval (BM25 + dense) + cross-encoder rerank, always citing the passage → concept extraction as a
byproduct → attributed (and contradiction-tolerant) edges, stored in your existing DB → agentic
multi-hop traversal that records **journeys** → the journey log *is* the accreting graph. Add Neo4j /
KG-embeddings / hypergraphs only when query shape demands them, never before.
