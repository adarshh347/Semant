# Structural & Analogical Retrieval — Research Survey

> Background reading for RhizomeDB's **structural-HyDE** path. The core wager: embedding
> similarity finds lexical/topical neighbours, but the connections worth having are
> *structural / analogical* and lexically distant. Instead of embedding a passage's surface
> text, an LLM names the passage's **underlying structure** (the move / problem / shape of
> thought), and retrieval runs on that abstraction — so structurally-kindred passages that
> share no vocabulary become reachable.
>
> This note surveys the computational lineage that already tries to do this, and pulls out
> what is concretely usable. Drafted 2026-06-20. Every reference below was web-verified.

---

## 1. Analogy mining over text & research papers (purpose / mechanism)

**What it is.** A line of work (Hope, Chan, Kittur, Shahaf and collaborators) that finds
analogies in large, messy text repositories by decomposing each document into a **purpose**
("what problem is solved") and a **mechanism** ("how it is solved"), learned as separate
vectors. Analogies are then retrieved by **near-purpose, far-mechanism** (same goal, different
means) — exactly the relation that breaks fixation and feels like a genuine cross-domain
insight rather than a duplicate.

**How it applies to RhizomeDB.** This is the closest existing analogue to structural-HyDE and
the single most transferable idea. Rather than one monolithic "structure" string per passage,
have the LLM emit a *factored* structural signature — at minimum **{problem/tension it stages,
move/operation it performs}**, optionally **{domain it speaks from}**. Then retrieval can be
asymmetric and tunable: match on *move* while deliberately maximising distance on *domain/
vocabulary* (Deleuze-on-difference ↔ a thermodynamics passage that performs the same move).
The "near X, far Y" knob is precisely the dial that separates "real but unobvious" from
"forced" — it gives the constellatory ethic an operational control surface. Their follow-up
adds user-selected "core aspect" retrieval (highlight the part of a passage you care about,
retrieve same-aspect/different-domain) — a natural interaction model for an exploratory tool.

**References.**
- Hope, Chan, Kittur, Shahaf, *Accelerating Innovation Through Analogy Mining*, KDD 2017
  (Best Paper). arXiv:1706.05585.
- Chan, Chang, Hope, Shahaf, Kittur, *SOLVENT / Analogy Search Engine: Finding Analogies in
  Cross-Domain Research Papers*, arXiv:1812.06974.
- Kang, Mysore, Huang, Chang, Prein, McCallum, Kittur, Olivetti, *Augmenting Scientific
  Creativity with Retrieval across Knowledge Domains*, NAACL/In2Writing 2022. arXiv:2206.01328.
- Hope et al., *Scaling up analogical innovation with crowds and AI*, PNAS 2019.

---

## 2. Structure-mapping theory (Gentner) and its computational descendants

**What it is.** Gentner's structure-mapping theory (1983) frames analogy as alignment of
*relational structure*, not shared attributes: a base maps to a target by matching the
**system of relations** (and prefers deep, interconnected relational systems — the
"systematicity principle"), explicitly ignoring surface features. Its implementation, the
Structure-Mapping Engine (SME; Falkenhainer, Forbus, Gentner 1989), works over structured
predicate-logic representations and can therefore connect very distant domains that share a
relational skeleton.

**How it applies to RhizomeDB.** SME is the theoretical license for the whole project: it is
the formal statement that "the connection worth having is relational, and surface vocabulary is
noise." Two concrete uses. (a) *As a vocabulary/target for the LLM's structure string*: prompt
the LLM to name a passage's structure as a small **relational schema** (entities + the relations
that bind them + a higher-order relation that is the "point"), not just a free-text gist —
systematicity says the higher-order relation is what should dominate the match. (b) *As a
re-ranker*: after embedding-based structural-HyDE returns candidates, an LLM can do a
lightweight SME-style alignment check (do the two passages actually share a relational mapping,
and is it deep or shallow?) to filter forced matches. Modern descendants show LLMs can perform
this alignment: **structure abduction** (infer the shared structure that makes two systems
analogous) and **flexible analogy mapping** are both LLM-tractable now.

**References.**
- Gentner, *Structure-Mapping: A Theoretical Framework for Analogy*, Cognitive Science, 1983.
- Falkenhainer, Forbus, Gentner, *The Structure-Mapping Engine: Algorithm and Examples*,
  Artificial Intelligence, 1989.
- Gentner & Markman, *Structure Mapping in Analogy and Similarity*, American Psychologist, 1997.
- Yuan, Chen et al., *Beneath Surface Similarity: LLMs Make Reasonable Scientific Analogies
  after Structure Abduction* (SCAR benchmark, 400 analogies / 13 fields), EMNLP Findings 2023.
  arXiv:2305.12660.
- Sultan & Shahaf, *FAME: Flexible, Scalable Analogy Mappings Engine*, arXiv:2311.01860.

---

## 3. LLM analogical reasoning: benchmarks & relational knowledge bases

**What it is.** A recent wave testing and equipping LLMs for analogy beyond word-pair
proportions (A:B::C:D), at the level of *systems* and *stories*: knowledge bases of relational
analogies, story-level analogy derivation, and long-context/abstract analogy benchmarks.

**How it applies to RhizomeDB.** Two uses. (a) These resources are *evaluation scaffolding* —
SCAR, StoryAnalogy and AnaloBench give you ready ways to sanity-check whether your structure
strings actually capture structure (does the system retrieve known analogous pairs and reject
surface-matched distractors?). (b) **AnalogyKB**-style mining (harvest concept pairs sharing a
relation from knowledge graphs) suggests a way to *seed or audit the concept graph*: relations,
not just concepts, can be first-class nodes, letting the graph express "these two passages are
joined by the same *move*" rather than only "the same *topic*."

**References.**
- Yuan et al., *ANALOGYKB: Unlocking Analogical Reasoning of Language Models with a Million-scale
  Knowledge Base*, ACL 2024. arXiv:2305.05994.
- Jiayang et al., *StoryAnalogy: Deriving Story-level Analogies from LLMs*, EMNLP 2023.
  arXiv:2310.12874.
- Ye et al., *AnaloBench: Benchmarking the Identification of Abstract and Long-context
  Analogies*, arXiv:2402.12370.

---

## 4. Metaphor detection & cross-domain mapping in NLP

**What it is.** NLP work grounded in Conceptual Metaphor Theory (Lakoff & Johnson): a metaphor
projects structure from a **source domain** onto a **target domain**. Beyond binary
metaphor/literal detection, recent work tries to *identify the mapping itself* — which source
domain is lent to which target — using contextual transformer embeddings.

**How it applies to RhizomeDB.** Philosophical prose is metaphor-dense, and a passage's
operative metaphor is often *its* structure (e.g. "the fold," "the rhizome," "ground/abyss").
A metaphor-mapping pass can enrich the structure string: naming the **source→target projection**
a passage runs gives a compact, lexically-detached signature that two distant passages can share
(both run a CONTAINER schema, both run GROUND-as-support-then-withdrawal). This is a cheaper,
more linguistically-grounded handle on "shape of thought" than full relational schemas, and it
composes well with §1's factored signature (the metaphor *is* often the mechanism).

**References.**
- Lakoff & Johnson, *Metaphors We Live By*, 1980 (theory base).
- Sánchez-Martínez et al. (eds.), *Meta4XNLI: A Cross-lingual Parallel Corpus for Metaphor
  Detection and Interpretation*, Computational Linguistics (MIT Press), 2026.
- *Towards Multimodal Metaphor Understanding: A Chinese Dataset and Model for Metaphor Mapping
  Identification*, arXiv:2501.02434 (explicit source→target mapping task).
- Turney, *Similarity of Semantic Relations* (Latent Relational Analysis), Computational
  Linguistics, 2006. arXiv:cs/0608100 — early surface-free relational similarity.

---

## 5. Conceptual blending & case-based reasoning

**What it is.** *Conceptual blending* (Fauconnier & Turner): two input mental spaces project
into a blended space with emergent structure, organised by a shared **generic space**.
*Case-based reasoning* (CBR): solve a new problem by retrieving and adapting structurally
similar past cases. The two connect computationally — amalgams from CBR have been used to
*automate discovery of the generic space* in a formal blending framework.

**How it applies to RhizomeDB.** Marginal-but-suggestive rather than core. The **generic space**
is the formal name for RhizomeDB's "bridge concept": the abstraction both passages instantiate
that licenses putting them in a constellation. Confais/Schorlemmer's computational blending
framework gives a principled recipe for *computing* that shared generic structure from two
inputs — useful if you ever want the system to **name the bridge** between a surfaced pair
(not just rank the pair), which is the constellatory output you actually want to show a user.
CBR-RAG patterns (retrieve structurally-similar prior cases, hybrid embeddings) are a practical
template if passages are ever indexed as reusable "moves."

**References.**
- Fauconnier & Turner, *The Way We Think: Conceptual Blending and the Mind's Hidden
  Complexities*, 2002.
- Confalonieri, Schorlemmer et al., *A Computational Framework for Conceptual Blending*,
  Artificial Intelligence, 2018 (Elsevier).
- Wiratunga et al., *CBR-RAG: Case-Based Reasoning for Retrieval Augmented Generation in LLMs*,
  ICCBR 2024. arXiv:2404.04302.

---

## 6. HyDE & abstraction-/hypothesis-based retrieval

**What it is.** HyDE (Gao, Ma, Lin, Callan 2022): instead of embedding the *query*, an LLM
generates a **hypothetical answer document**, and *that* is embedded to find the neighbourhood
of real documents — query and corpus are mapped into the same "document-shaped" space, fixing
the query/document asymmetry of zero-shot dense retrieval. Step-Back Prompting (Zheng et al.
2024) is the abstraction cousin: derive a higher-level question/principle from the specific
query, then retrieve/reason on the abstraction.

**How it applies to RhizomeDB.** Structural-HyDE *is* a HyDE variant — but a crucial inversion.
Classic HyDE generates a hypothetical *document* (still surface-text, still lexical). Your move
is to generate a hypothetical *structure* and retrieve on **structure-to-structure** similarity,
deliberately discarding the surface the classic method keeps. Two design notes fall out of the
HyDE literature: (a) HyDE works because the generated artifact and the corpus live in the **same
embedding space** — so RhizomeDB must index passages by their *structure strings too*, not embed
a structure-query against surface-text passages (asymmetry would reintroduce lexical bias). (b)
HyDE's known failure mode is hallucinated specifics; Step-Back's abstraction discipline is the
antidote — pushing the generated structure *up* the abstraction ladder (the move, not the
example) both kills hallucinated detail and is exactly what makes lexically-distant matches
possible. The "near-purpose/far-mechanism" knob from §1 is the retrieval-time complement.

**References.**
- Gao, Ma, Lin, Callan, *Precise Zero-Shot Dense Retrieval without Relevance Labels* (HyDE),
  ACL 2023. arXiv:2212.10496.
- Zheng et al. (Google DeepMind), *Take a Step Back: Evoking Reasoning via Abstraction in LLMs*,
  ICLR 2024. arXiv:2310.06117.

---

## 7. Indian aesthetics (rasa, dhvani, sphoṭa, chamatkāra) — what computationally exists

**What it is — and the honest state of the evidence.** These are theories of *suggested,
non-literal* meaning and aesthetic resonance: **dhvani** (Ānandavardhana) — the most poetically
effective meaning is *suggested*, not stated; **rasa** — the aesthetic "flavour" evoked in the
reader; **sphoṭa** (Bhartṛhari) — meaning grasped as an instantaneous integral whole, distinct
from the sequence of sounds (dhvani in his sense) that manifests it; **chamatkāra** — the
relish/wonder of aesthetic surprise. **Computational work directly formalising these is very
sparse.** What exists is almost entirely *rasa-as-sentiment*: treating rasa as an extended
emotion-classification target over text, dance, or music. There is, to my finding, **no
published computational model of dhvani-as-suggestion, sphoṭa-as-holistic-meaning, or
chamatkāra-as-surprise** as retrieval or resonance mechanisms — this is open ground, not a
solved area.

**How it applies to RhizomeDB.** These are better read as *design vocabulary and evaluation
targets* than as importable algorithms — but they name precisely what RhizomeDB is reaching for.
**Dhvani** is the thesis that the connection worth surfacing is *suggested, never stated* — i.e.
exactly the "real but unobvious; neither passage names it" criterion. **Chamatkāra** is the
right name for the *target signal*: a good constellation produces aesthetic surprise (wonder at
an unforced-yet-apt juxtaposition) — a more precise objective than recommender-style
"unexpectedness × diversity," and a candidate human-eval rubric ("did this pairing produce
chamatkāra?"). **Sphoṭa** cautions against over-decomposing: the *point* of a passage is grasped
as a whole, which argues for keeping a holistic structure string alongside any factored schema.
The sparsity is itself an opportunity: a formal/computational treatment of dhvani-as-suggested-
resonance would be a genuine contribution, not a re-implementation.

**References.**
- Ānandavardhana, *Dhvanyāloka* (c. 9th c.); Bhartṛhari, *Vākyapadīya* (sphoṭa) — primary
  sources.
- Saroja, Gopalakrishnan et al., *Aesthetics of Sanskrit Poetry from the Perspective of
  Computational Linguistics: A Case Study Analysis on Śikṣāṣṭaka*, arXiv:2308.07081 (rare
  explicit attempt to bring rasa/dhvani into computational linguistics; case-study scope).
- Broad literature exists on *rasa as a sentiment/emotion-classification label* (text, dance,
  music); none formalises dhvani/sphoṭa/chamatkāra as a retrieval mechanism — reported honestly
  as a gap.

---

## Most actionable for RhizomeDB now

**1. Factor the structure string into "problem / move," and make retrieval asymmetric
(near-move, far-domain).** This is the cheapest, highest-leverage change. Rather than one opaque
structure string per passage, have the LLM emit a small factored signature — at minimum
*{tension it stages, move/operation it performs}*, plus a *domain/vocabulary* tag. Index passages
by these fields and retrieve with the "near-purpose, far-mechanism" dial from the analogy-mining
line (§1): match strongly on *move*, push for *distance* on domain/vocabulary. That dial is the
operational form of the constellatory ethic — it is literally the knob between "real-but-unobvious"
and "forced," and it is proven to surface genuine cross-domain analogies (KDD'17 / NAACL'22).

**2. Keep structural-HyDE symmetric and abstraction-disciplined, then add an SME-style
re-rank.** From the HyDE/Step-Back literature (§6): embed *structure-against-structure* (index
the corpus by structure strings too — do not match a structure-query against surface text, or
lexical bias returns), and push the generated structure *up* the abstraction ladder to kill
hallucinated specifics. Then, on the top-k, run a lightweight LLM **structure-abduction /
alignment** check (§2–3): "is there a real shared relational mapping here, and is it deep?" —
this is your forced-match filter and your bridge-namer in one. Use **chamatkāra** (§7) as the
human-eval target for whether a surfaced pair actually lands.
