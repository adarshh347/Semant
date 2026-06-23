# Maps that let a *shape* emerge from the corpus

**Problem.** We have ~4,000 philosophical passage embeddings plus per-chunk concept/character tags. The current "chunk map" is a file/structure diagram (nodes-by-level, parent/child edges) and is useless for *thought*. We want methods where a meaningful topological/geometric space **emerges** from the data itself, supporting human discovery, contemplation, and analysis — regions as themes, loops as conceptual circularities/dialectics, gaps as unexplored territory, density/curvature as contestation.

Four families below. For each: (a) what it is, (b) the *discovery* it enables here, (c) concrete application to our embeddings + tags, (d) references.

---

## 1. Topological Data Analysis (TDA): persistent homology + the Mapper algorithm

**(a) What it is.** TDA studies the *shape* of a point cloud — its connected pieces, loops, and voids — in a way that is robust to noise and coordinate choice. **Persistent homology** tracks which holes (Betti-0 = components, Betti-1 = loops, Betti-2 = voids) appear and persist as you "thicken" the points across scales; long-lived features are real structure. The **Mapper algorithm** (Singh, Mémoli & Carlsson 2007) is the more immediately usable tool: it compresses a high-dimensional cloud into a *readable graph* — choose a "lens"/filter function on the data, cover its range with overlapping bins, cluster the points inside each bin, make each cluster a node, and connect nodes that share points. The output graph is a topological skeleton of the corpus.

**(b) Discovery it enables here.**
- **Connected components** = genuinely separate bodies of thought (e.g., an analytic cluster with no bridge to a mystical cluster). A *thin bridge* between two large lobes is a rare passage that mediates two traditions — a high-value find.
- **Loops (1-cycles)** are the philosophically richest signal: a loop means you can travel A→B→C→…→A through *continuously related* passages and return changed — a **conceptual circularity or dialectic** (thesis→antithesis→synthesis that re-enters the thesis; the hermeneutic circle; being↔becoming). A loop is exactly the structure a tree/parent-child map can *never* show.
- **Flares / Y-branches** = a concept that splits into divergent readings.
- **Voids** = a conceptual "hole": positions that are logically adjacent but never co-occur (an unthought combination).

**(c) Concrete application.**
- Run **Mapper** on the 4,000 embeddings (cosine/Euclidean metric). Good philosophical lenses: (i) the first 1–2 UMAP coordinates, (ii) a tag-density or eccentricity/centrality filter, or (iii) a scalar like "abstractness" or a concept-axis projection. Color nodes by dominant **concept tag** or **character/author tag**, and size by passage count, so the graph reads as a labeled conceptual atlas. Use `KeplerMapper` (scikit-tda) — it emits an interactive HTML graph directly.
- For **persistent homology**: build a Vietoris–Rips filtration on the embeddings with `ripser`/`giotto-tda`, read the Betti-1 barcode; each long bar is a candidate dialectical loop. Then **recover the loop's actual passages** (representative cycles) to read what the circularity *is* in text.
- Tags make this interpretable: a loop whose nodes cycle through tags `freedom → necessity → freedom` is self-documenting.

**(d) References.**
- Singh, Mémoli, Carlsson, *Topological Methods for the Analysis of High Dimensional Data Sets and 3D Object Recognition*, Eurographics SPBG 2007 — original Mapper. https://research.math.osu.edu/tgda/mapperPBG.pdf
- Carlsson, *Topology and Data*, Bull. Amer. Math. Soc. 46(2):255–308, 2009 — the canonical TDA survey. https://www.ams.org/journals/bull/2009-46-02/S0273-0979-09-01249-X/
- KeplerMapper docs (scikit-tda). https://kepler-mapper.scikit-tda.org/
- Hajij et al. (review), *A Comprehensive Review of the Mapper Algorithm … (2007–2025)*, arXiv:2504.09042. https://arxiv.org/abs/2504.09042

---

## 2. Manifold learning / projection: UMAP and t-SNE

**(a) What it is.** Nonlinear dimensionality reduction that lays the high-dimensional cloud onto a 2-D map so neighbors stay neighbors. **t-SNE** preserves *local* neighborhoods aggressively (tight, well-separated blobs). **UMAP** balances local and (somewhat) global structure and is faster, so relative cluster placement is a little more trustworthy.

**(b) Discovery it enables here.** A single contemplable picture: **themes appear as regions**, **transitional passages as isthmuses between regions**, and **empty space as unexplored conceptual territory**. Overlaying tags turns the map into a readable terrain — you can *see* where "ethics" and "metaphysics" bleed into each other, or that one author occupies an island.

**(c) Concrete application.** Run UMAP (cosine metric) on the 4,000 embeddings → 2-D scatter; color by concept tag, shape/border by character/author. This is the **everyday browsing surface** of RhizomeDB and the natural Mapper lens (§1c). Tune `n_neighbors` (small = fine local detail, large = continental structure) and inspect 2–3 settings. Use t-SNE only as a cross-check on local cluster identity.

**Caveats — load-bearing, write them on the UI.**
- **Distances between clusters are not meaningful** (especially t-SNE); gap *width* and cluster *size/density* are largely artifacts. Don't read "these two schools are far apart" off the map.
- Both can **manufacture discrete clusters out of genuinely continuous gradients** — a real risk for thought, which is often a continuum. Treat apparent separations skeptically.
- Hyperparameters change the picture substantially; never trust a single projection. (This is why §1 Mapper — which is *designed* to preserve topology — is the more trustworthy structural claim, with UMAP as the eye-candy front-end.)

**(d) References.**
- McInnes, Healy, Melville, *UMAP: Uniform Manifold Approximation and Projection*, arXiv:1802.03426. https://arxiv.org/abs/1802.03426
- van der Maaten & Hinton, *Visualizing Data using t-SNE*, JMLR 9:2579–2605, 2008. https://www.jmlr.org/papers/v9/vandermaaten08a.html
- Wattenberg, Viégas, Johnson, *How to Use t-SNE Effectively*, Distill 2016. https://distill.pub/2016/misread-tsne/
- Coenen & Pearce, *Understanding UMAP* (Google PAIR). https://pair-code.github.io/understanding-umap/

---

## 3. Gärdenfors' Conceptual Spaces — a *principled* theory of letting a space emerge

**(a) What it is.** A cognitive theory (Gärdenfors, *Conceptual Spaces: The Geometry of Thought*, 2000) where meaning lives in geometry: concepts are built over **quality dimensions** grouped into **domains**, and a natural concept is a **convex region** — if two passages exemplify a concept, anything "between" them should too. This is the theoretical justification for treating an embedding space as a *space of thought* rather than a bag of vectors.

**(b) Discovery it enables here.** It gives a *criterion* for whether an emergent region is a real concept: **convexity**. A tag whose passages form a tight convex blob is a coherent concept; one that's **non-convex or multi-modal is equivocal/contested** — the same word covering two ideas (a fork worth surfacing to the reader). It also licenses **conceptual interpolation**: the midpoint between two passages is a meaningful (possibly unwritten) intermediate position — fuel for contemplation.

**(c) Concrete application.**
- For each concept **tag**, take its passages' embeddings and test region quality: convex-hull tightness, modality (is it one cluster or several?), and a "betweenness" check (are points on the segment between two same-tag passages also same-tag?). **Non-convex tags = contested concepts to flag.**
- Identify candidate **quality dimensions** by finding interpretable directions (PCA within a domain, or "concept-axis" vectors like *sacred↔profane*, *one↔many*) and projecting passages onto them — a small dashboard of philosophical axes rather than a black-box 768-D space.
- Use **prototypes** (region centroids) as the canonical passage for each concept, and region overlap as a measure of conceptual kinship.

**(d) References.**
- Gärdenfors, *Conceptual Spaces: The Geometry of Thought*, MIT Press, 2000. https://mitpress.mit.edu/9780262572194/conceptual-spaces/
- "Conceptual space", Wikipedia (orienting summary; convex regions / quality dimensions / domains). https://en.wikipedia.org/wiki/Conceptual_space
- Bechberger & Kühnberger, *Formalized Conceptual Spaces with a Geometric Representation of Correlations*, arXiv:1801.03929. https://arxiv.org/abs/1801.03929

---

## 4. Geometry of the embedding space — only the *usable* parts

**(a) What it is.** Transformer embeddings are **anisotropic** (vectors crowd into a narrow cone), have an **intrinsic dimensionality** far below their nominal size, and have **locally varying density/curvature**. Raw cosine similarity is distorted by a few "rogue" dimensions that dominate every comparison.

**(b) Discovery it enables here — two genuinely usable payoffs.**
1. **Hygiene (do this first, cheaply):** because of anisotropy + rogue dimensions, untreated similarities are misleadingly high and flat. *Standardizing / removing top dominant directions ("all-but-the-top") makes every downstream map sharper* — directly improves §1–§3.
2. **Where the space is dense/curved = where thought is contested or load-bearing.** Local density (k-NN distances) and local intrinsic-dimension estimates highlight **tight, high-curvature regions** — concepts argued over from many angles, packed with near-synonymous-but-distinct passages — versus sparse frontier regions (isolated, unelaborated ideas). This is a heat-map of *intensity of thought*.

**(c) Concrete application.** Before mapping: estimate global anisotropy, mean-center and optionally drop the top ~1–5 principal directions; estimate intrinsic dimension (TwoNN / MLE) to choose UMAP/Mapper parameters honestly. Then compute a **per-passage local-density (and local-ID) score** and use it as a node-color/heat overlay on the UMAP and Mapper graphs: bright = contested/dense, dark = frontier.

**(d) References.**
- Ethayarajh, *How Contextual are Contextualized Word Representations? …*, EMNLP 2019 (anisotropy). https://aclanthology.org/D19-1006/
- Mu & Viswanath, *All-but-the-Top: Simple and Effective Postprocessing for Word Representations*, ICLR 2018, arXiv:1702.01417. https://arxiv.org/abs/1702.01417
- Timkey & van Schijndel, *All Bark and No Bite: Rogue Dimensions in Transformer Language Models …*, EMNLP 2021, arXiv:2109.04404. https://arxiv.org/abs/2109.04404
- Facco et al., *Estimating the intrinsic dimension of datasets by a minimal neighborhood information* (TwoNN), Sci. Rep. 2017. https://www.nature.com/articles/s41598-017-11873-y

---

## Verdict — what to try first

**Try first: UMAP 2-D projection (§2), colored by concept/character tags.** It is the cheapest single step (a few lines with `umap-learn`), turns the 4,000 embeddings into one contemplable terrain of themes/gaps immediately, *and* produces the lens that Mapper needs next — so it is both the quickest win and the on-ramp to the deeper method. Pair it on day one with the §4.1 hygiene step (mean-center + drop top directions) so the map isn't washed out by anisotropy.

**Then, the highest-value structural payoff: the Mapper graph (§1).** Unlike UMAP it *preserves topology by construction* and can reveal the **loops = dialectics/circularities** that a tree map structurally cannot — the single most novel thing this corpus can show. Use UMAP coords as the lens, color nodes by tag, and recover representative passages for any loop. Persistent-homology barcodes (`ripser`) are a cheap confirmation that a visible loop is real and not an artifact.

Gärdenfors (§3) is the interpretive frame that tells you *which emergent regions are real concepts vs. contested ones* — apply it as analysis once the maps exist, not as a first build step.
