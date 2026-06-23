# Maps of Conceptual Order — Emergent Structure & a "What to Study Next" Planner

*RhizomeDB note. Goal: let a conceptual order and a reading plan **emerge** from per-chunk
concept tags and their co-occurrence across ~4,000 philosophical passages — for discovery,
contemplation, analysis, planning. Not a file diagram. Each chunk carries (i) core concept tags
and (ii) a **character** (definitional / argumentative / poetic / exegetical / aporetic …).*

Our raw material is a **chunks × concepts incidence matrix** (which passage discusses which
concepts) plus a per-chunk character label. Four families of method turn that into a navigable,
emergent map. All four operate on exactly this data; they differ in what kind of order they expose.

---

## 1. Formal Concept Analysis (FCA) / Concept Lattices

**(a) What it is.** A mathematical theory (Ganter & Wille) that takes a binary *formal context*
— here, objects = chunks, attributes = concepts — and derives, via a **Galois connection**, the
complete lattice of all "formal concepts": maximal pairs *(set of chunks, set of concepts)* where
every chunk has every concept and vice versa. The result is a partially ordered hierarchy (the
**concept lattice**) of sub-/super-concepts. [Ganter & Wille 1999; Wikipedia; nLab]

**(b) Discovery on this corpus.** The lattice surfaces, with zero tuning, *which exact passage-sets
share which exact concept-sets* and how those bundles nest. A node like
`{being, time, finitude} → {these 14 passages}` sitting **below** `{being, time}` tells you that
finitude is a *specialization move* inside the being-and-time discourse. Joins/meets reveal implied
concept dependencies ("every passage tagged *kenosis* is also tagged *negativity*") and the bare
"top/bottom" extremes. It is the most faithful to the tags: it invents nothing, only reorganizes
what co-occurs into a contemplable hierarchy of shared horizons.

**(c) RhizomeDB application.** Build the incidence directly from concept tags; compute the lattice
(Python `concepts`, or fcatools). Read upward = generalization, downward = specialization — a
literal "constellation" navigator. Filter the context by **character** to get *typed* lattices: a
lattice over only *definitional* chunks gives the corpus's skeletal ontology; one over *aporetic*
chunks shows where concepts collide. **Attribute implications** become study rules ("to grasp X you
will always also meet Y"). Caveat: lattices explode on dense data — threshold rare concepts, or
restrict to a concept neighborhood, to keep it readable.

**(d) References.** Ganter & Wille, *Formal Concept Analysis: Mathematical Foundations*, Springer
1999 — https://link.springer.com/book/10.1007/978-3-642-59830-2 ;
overview — https://en.wikipedia.org/wiki/Formal_concept_analysis ;
https://ncatlab.org/nlab/show/formal+concept+analysis .

---

## 2. Co-occurrence Science Mapping + Community Detection + Betweenness

**(a) What it is.** Project the incidence into a **concept co-occurrence network** (concepts linked
when they appear in the same chunk, weighted by frequency), then partition it with
**Louvain** (Blondel et al. 2008) or **Leiden** (Traag et al. 2019), and rank nodes by
**centrality** — especially **betweenness**, which flags concepts lying on the short paths
*between* clusters: the **bridge concepts**. Tooling lineage: VOSviewer, bibliometrix, CorTexT.
[Blondel 2008; Traag 2019; van Eck & Waltman 2010]

**(b) Discovery on this corpus.** Communities are the corpus's **emergent themes** — clusters of
concepts that travel together — found with no prior taxonomy. Betweenness finds the *hinges*: a
concept like *mediation* or *difference* that bridges otherwise separate clusters is a high-value
study target because understanding it unlocks passage between regions. Leiden specifically protects
such **bridge nodes** from being mis-split, which Louvain can break — worth it here precisely
because bridges are the payload. [Leiden refinement; Wikipedia]

**(c) RhizomeDB application.** One pass over the tags yields the weighted concept graph (cosine /
association-strength normalized, as VOSviewer does). Run Leiden → name each community by its top
concepts = an auto-generated table of themes. Rank by betweenness → a ranked "**bridge concepts to
study**" list. Edge weights can be **character-typed**: an edge built only from *argumentative*
co-occurrences is a line of reasoning; one from *poetic* co-occurrences is a resonance. Compare the
two graphs to see where the corpus argues vs. where it evokes.

**(d) References.** Blondel, Guillaume, Lambiotte, Lefebvre, "Fast unfolding of communities in large
networks," *J. Stat. Mech.* 2008 — https://arxiv.org/abs/0803.0476 ;
Traag, Waltman, van Eck, "From Louvain to Leiden," *Sci. Rep.* 2019 —
https://www.nature.com/articles/s41598-019-41695-z (overview https://en.wikipedia.org/wiki/Leiden_algorithm) ;
van Eck & Waltman, "Software survey: VOSviewer," *Scientometrics* 84 (2010): 523–538 —
https://link.springer.com/article/10.1007/s11192-009-0146-3 .

---

## 3. Callon's Strategic / Thematic Diagram — the direct "What to Study" Planner

**(a) What it is.** From co-word clusters, plot each theme on two axes: **centrality** (x, strength
of a theme's links to *other* themes — its relevance to the whole) and **density** (y, internal
cohesion — the theme's own maturity). The plane splits into four quadrants. [Callon, Courtial &
Laville 1991; Cobo et al. SciMAT 2012]

**(b) Discovery on this corpus.** It classifies every emergent theme into a *strategic posture*,
which is literally a reading agenda:
- **Motor** (high centrality, high density): well-developed *and* central — the corpus's load-bearing engines; study to grasp the whole.
- **Basic / transversal** (high centrality, low density): central but under-developed — gateway concepts you must traverse but that the corpus leaves thin → high-leverage to deepen.
- **Niche** (low centrality, high density): self-contained, mature specialties — study when you want depth in a corner.
- **Emerging or declining** (low centrality, low density): marginal/peripheral — for exploratory or completist reading.

**(c) RhizomeDB application.** Take the Leiden communities from (2), compute Callon centrality &
density per community from the same co-occurrence weights, and render the four-quadrant map. This is
the **planner**: motor themes = read first, basic-transversal = the bridges to consolidate,
niche = optional deep dives, emerging = frontier browsing. Running it separately on
**definitional vs. argumentative** chunk-subsets shows whether a theme is mature *as doctrine* or
mature *as contention* — different reasons to read.

**(d) References.** Callon, Courtial & Laville, "Co-word analysis as a tool...," *Scientometrics* 22
(1991): 155–205 — https://link.springer.com/article/10.1007/BF02019280 ;
Cobo, López-Herrera, Herrera-Viedma & Herrera, "SciMAT: A new science mapping analysis software
tool," *JASIST* 63 (2012) — https://onlinelibrary.wiley.com/doi/abs/10.1002/asi.22688 ;
implemented in bibliometrix/biblioshiny (Aria & Cuccurullo).

---

## 4. Topic Models as a Space — Hierarchical / Dynamic / BERTopic

**(a) What it is.** Treat themes as **regions in a continuous space** rather than discrete clusters.
**BERTopic** (Grootendorst 2022) embeds chunks with a transformer, reduces dimension, clusters with
HDBSCAN, and labels clusters with class-based TF-IDF; it supports **hierarchical** topic merging and
**dynamic** ("topics over time") modeling of theme drift. [Grootendorst 2022]

**(b) Discovery on this corpus.** Topics emerge from *meaning* (embeddings), not just shared tags —
catching themes our discrete concept vocabulary missed, and placing chunks on a smooth landscape you
can browse by proximity. The hierarchy gives coarse→fine theme zoom; the **dynamic** axis (ordered
by author, period, or position in a thinker's development) shows a theme **drifting** — where a
concept enters, peaks, or fades across the corpus's sequence.

**(c) RhizomeDB application.** Embed each chunk; run BERTopic with our concept tags as
**seed/guided topics** or as the labeling vocabulary, so emergent regions stay legible in our terms.
Use the hierarchy as a contemplative zoom; use topics-over-time along a thinker's chronology to map
*conceptual development* (a reading order that follows how ideas mature). **Character** becomes a
metadata facet: see which regions are dense with *poetic* vs. *definitional* passages — i.e., where
the corpus sings vs. where it defines.

**(d) References.** Grootendorst, "BERTopic: Neural topic modeling with a class-based TF-IDF
procedure," 2022 — https://arxiv.org/abs/2203.05794 ;
docs https://maartengr.github.io/BERTopic/ ;
dynamic topics https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html .

---

## Build first: cheapest, highest signal

**Start with #2 (concept co-occurrence + Leiden + betweenness), then immediately #3 (Callon
diagram) on top of it.** They share one cheap input we *already have* — the concept tags — needing
no embeddings, no transformer, no parameter search: build the weighted co-occurrence graph, run
Leiden, rank betweenness, and plot the four quadrants. Within an afternoon that yields (a) emergent
themes, (b) a ranked list of **bridge concepts**, and (c) a motor/basic/niche/emerging **reading
planner** — directly serving discovery and "what to study next." **FCA (#1)** is the natural second
build for rigorous, lossless contemplation of shared horizons; **BERTopic (#4)** comes last, once an
embedding pipeline exists, to catch meaning beyond the tags and to map drift.

Sources:
- https://link.springer.com/book/10.1007/978-3-642-59830-2
- https://en.wikipedia.org/wiki/Formal_concept_analysis
- https://ncatlab.org/nlab/show/formal+concept+analysis
- https://arxiv.org/abs/0803.0476
- https://www.nature.com/articles/s41598-019-41695-z
- https://en.wikipedia.org/wiki/Leiden_algorithm
- https://link.springer.com/article/10.1007/s11192-009-0146-3
- https://link.springer.com/article/10.1007/BF02019280
- https://onlinelibrary.wiley.com/doi/abs/10.1002/asi.22688
- https://arxiv.org/abs/2203.05794
- https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html
