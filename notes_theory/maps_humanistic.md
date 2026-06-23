# Maps for Contemplation (Humanistic Complement)

> The humanistic / sensemaking complement to the statistical retrieval methods. The aim of a
> *contemplation map* is to help a reader **think**, not to compute a diagram: a surface that is
> **non-metric** (distance is not the point), **juxtapositional** (meaning lives in the gaps between
> things, not in the things), and **discovery-oriented** (it invites wandering, it does not answer a
> query). This note grounds that idea in four bodies of theory and ends with one buildable proposal
> over RhizomeDB's ~4,000 philosophical passages. Drafted 2026-06-23.

---

## 0. What a "map for contemplation" is

Not a chart that *represents* the corpus, but an *arrangement* the reader thinks **with**. Three commitments:

- **Non-metric.** Position and proximity carry no claim of measured similarity. Nearness is an
  invitation, not a score. (Contrast: a UMAP scatter of embeddings, where x/y *means* something
  metric — that is a striated diagram, see §3.)
- **Juxtapositional.** The unit of meaning is the *pairing* or the *cluster of panels*, and the
  meaning lives in the **interval between them** — the reader supplies the connection.
- **Discovery-oriented.** It is built for *navigation by intensity* (follow what pulls you), not for
  *lookup by coordinate*. It tolerates — even wants — the reader to find nothing and move on.

The four theories below each contribute one face of this: Warburg/Benjamin give the **interval as
thinking-space**; Moretti gives the **macro-pattern abstraction**; Deleuze & Guattari give the
**smooth/striated criterion** for whether a surface is inert or alive; Pirolli–Card and IBIS give the
**sensemaking workflow** that turns wandering into accumulated understanding.

---

## 1. Warburg's *Mnemosyne Atlas* + Benjamin's constellation / *Arcades*

**(a) The idea.** Aby Warburg's unfinished *Bilderatlas Mnemosyne* (1924–29) is ~63 black panels
pinning ~1,000 photographs into clusters with no captions and no linear argument; meaning is produced
by **montage** — by what sits next to what — opening a *Denkraum* ("thought-space," literally room for
thinking) in the **gaps between images**. Walter Benjamin's *Arcades Project* works the same way through
the **dialectical image**: a *constellation* in which a fragment of the past and the now "come together
in a flash," meaning arising from the *configuration* of juxtaposed quotations, not from a thesis
imposed on them.

**(b) What it offers RhizomeDB.** The licence to make the **interval load-bearing**: the map's primary
content is the *adjacency of passages*, and the reader's interpretive act in the gap is the feature, not
a defect. Captionless juxtaposition is exactly the "unexpected-but-not-forced" ethic of constellatory
retrieval — the stars are really there (both passages instantiate a bridge), the figure is disclosed,
not asserted. This is the contemplative surface's *aesthetic*: panels, not a query box.

**(c) Operationalization.** Build **panels** (à la Warburg's plates), not a single global map. Each panel
= 6–12 passages laid out spatially, selected so they share a latent bridge (an embedding neighborhood
*intersected* with a divergence in source author/era, or a shared tag held across distant authors).
Crucially, **show no edges and no labels** inside a panel — only proximity and a deliberate empty
center. Let the reader name the *Denkraum*. The "dialectical image" maps to pairing a passage with its
**most distant** plausible counterpart (high bridge-strength, low surface similarity), not its nearest.

**(d) References.**
- Aby Warburg, *Bilderatlas Mnemosyne* (1924–29, unfinished); reconstructed ed. Roberto Ohrt & Axel
  Heil, *Aby Warburg: Bilderatlas Mnemosyne — The Original* (HKW / Hatje Cantz, 2020). Online: Cornell
  University Library, *Mnemosyne: Meanderings through Aby Warburg's Atlas*.
- Walter Benjamin, *The Arcades Project* (Das Passagen-Werk), trans. Eiland & McLaughlin (Harvard, 1999);
  on the "dialectical image," Convolute N.

---

## 2. Franco Moretti — distant reading (graphs, maps, trees)

**(a) The idea.** In *Graphs, Maps, Trees* (2005) Moretti argues for **distant reading**: deliberately
*not* reading individual texts but abstracting a corpus into **graphs** (quantitative history), **maps**
(geography/geometry), and **trees** (evolutionary morphology), so that macro-patterns invisible to close
reading of any single text become visible across the whole system.

**(b) What it offers RhizomeDB.** Permission to make abstractions that the reader could *never* see by
reading 4,000 passages one at a time — the shape of a *concept's* migration across authors, the
branching of a vocabulary, the geography of where a problem is densest. It is the macro layer beneath the
panels: the atlas needs both the close juxtaposition (§1) and the bird's-eye morphology (§2).

**(c) Operationalization.** From the existing tags/concept-graph: a **graph** of concept co-occurrence
(which philosophemes travel together); a **tree** of a single concept's lineage (cluster passages
mentioning "difference," "rhizome," "trace" and show their genealogical splits as a dendrogram over
author/era metadata); a **map** that uses a non-geographic plane — e.g. an author × era grid colored by
the density of a chosen bridge-concept, so migration becomes legible. These are *entry points* into
panels, not endpoints: clicking a dense cell opens a Warburg panel (§1) for that region.

**(d) References.**
- Franco Moretti, *Graphs, Maps, Trees: Abstract Models for a Literary History* (Verso, 2005).
- Franco Moretti, "Conjectures on World Literature," *New Left Review* 1 (2000) — origin of "distant
  reading." Caveat (well-rehearsed critique): distant reading is thin on hermeneutic depth — hence it must
  remain a *map into* close juxtaposition, never a substitute for it.

---

## 3. Deleuze & Guattari — smooth vs. striated space (RhizomeDB's own idiom)

**(a) The idea.** In *A Thousand Plateaus* (1980, "1440: The Smooth and the Striated"), **striated** space
is gridded, metric, optical, sedentary — movement runs on preset paths between fixed coordinates; **smooth**
space is open, *intensive*, haptic, nomadic — "occupied by intensities and events," **vectorial rather than
metrical**, navigated up-close by gradient and direction, with no global coordinate reference.

**(b) What it offers RhizomeDB.** The exact **diagnostic criterion** for whether a contemplation surface is
inert. A leveled chunk map — fixed grid of cells, a metric scatter, a global coordinate the reader reads
*off* — is **striated**: it tells you where things "are" and closes thought. RhizomeDB wants a **smooth**
surface: no global metric, the reader **rises up at any point and moves to any other** by following
intensity (resonance, pull, bridge-strength), the way one crosses a desert by feel, not by grid. This *is*
the rhizome: any-to-any, non-arborescent, entered from the middle.

**(c) Operationalization.** Concretely, *smooth* means: (i) **no fixed layout** — the map re-centers on
wherever the reader is (egocentric, local horizon of ~7±2 neighbors), never a static global plot; (ii)
**movement by intensity gradient** — edges/neighbors ranked by a *bridge-strength* intensity (real but
unobvious connection) and presented as *directions to walk*, not distances to read; (iii) **no coordinates
shown** — strip axis labels, scores, and similarity numbers from the contemplative view (keep them in a
debug view). Use the embedding only to *generate* candidate neighbors, then **discard the metric** at the
surface so the reader navigates vectorially. (Reserve "striated" tools — the §2 graphs/trees — as an
explicit *overview* mode the reader can toggle into, then dive back out.)

**(d) References.**
- Gilles Deleuze & Félix Guattari, *A Thousand Plateaus: Capitalism and Schizophrenia*, trans. Brian
  Massumi (Minnesota, 1987 [orig. *Mille Plateaux*, 1980]) — plateau 14, "1440: The Smooth and the
  Striated"; and the "Introduction: Rhizome."

---

## 4. Sensemaking (Pirolli & Card) + knowledge/argument cartography (IBIS / gIBIS / Compendium)

**(a) The idea.** Pirolli & Card's **sensemaking loop** models analysis as two nested cycles: a *foraging
loop* (search → filter → read → extract into a "shoebox"/evidence file) and a *sensemaking loop* (organize
evidence into **schemas**, form hypotheses, present) — iterative, non-linear, bottom-up and top-down.
**IBIS** (Issue-Based Information System; Kunz & Rittel, 1970) and its descendants **gIBIS** (Conklin &
Begeman, 1988) and **Compendium** structure understanding of "wicked problems" as a graph of typed nodes:
**Questions/Issues → Ideas/Positions → Arguments (pro/con)**.

**(b) What it offers RhizomeDB.** The **workflow** that turns aimless wandering into accumulated insight —
a "shoebox" where the reader drops passages plucked from panels, and a lightweight scaffold (an Issue, the
positions it gathers) that lets a constellation *become an argument the reader is building* without
collapsing the open juxtaposition into a forced thesis. This is how a contemplation map earns its keep over
time rather than being a one-shot pretty picture.

**(c) Operationalization.** Give every reader a **shoebox** (persistent collection of saved passages drawn
from panels) — the foraging artifact. Offer a single optional structuring gesture per shoebox: pin a
**Question** at the center and let saved passages snap into **Position** clusters around it, with the system
suggesting **pro/con tension pairs** (passages whose bridge-concept matches but whose stances diverge) as
candidate IBIS arguments. Keep it *opt-in and reversible* — the default state stays a smooth, captionless
panel; IBIS is the striated scaffold the reader can erect *when ready to think harder*, then dissolve.

**(d) References.**
- Peter Pirolli & Stuart Card, "The Sensemaking Process and Leverage Points for Analyst Technology as
  Identified Through Cognitive Task Analysis," *Proc. Int'l Conf. on Intelligence Analysis* (2005); Pirolli,
  *Information Foraging Theory* (Oxford, 2007).
- Werner Kunz & Horst W. J. Rittel, "Issues as Elements of Information Systems" (Working Paper 131, 1970).
- Jeff Conklin & Michael L. Begeman, "gIBIS: A Hypertext Tool for Exploratory Policy Discussion," *ACM
  Trans. on Information Systems* 6(4), 1988. Compendium Institute (compendiuminstitute.net); see also
  Conklin, *Dialogue Mapping* (Wiley, 2006).

---

## 5. One buildable proposal — **"Panels": a smooth atlas of constellations**

A single screen with two coupled modes over the existing chunks / embeddings / tags / concept-graph:

1. **Smooth mode (default) — the Warburg panel.** The reader lands on *one panel*: a captionless spatial
   arrangement of 6–12 passages sharing a latent **bridge-concept**, chosen by *embedding-neighborhood ∩
   author/era-divergence* (real but unobvious — §1). No edges, no scores, no axes (§3, smooth). The center
   is left **deliberately empty** — the *Denkraum*. Each passage has a faint **intensity halo** indicating
   pull toward unseen neighbors; clicking one **re-centers** the panel on a fresh constellation around it
   (navigation by gradient, never by global coordinate). The metric is used only to *generate* candidates,
   then hidden.

2. **Striated mode (toggle) — Moretti overview.** One key flips to an abstraction over the *whole* corpus:
   a concept co-occurrence **graph**, a single concept's lineage **tree**, or an author × era density
   **map** (§2). Clicking any region drops the reader *back into* a smooth panel for that region. Overview
   and immersion, deliberately separated and switchable.

3. **Shoebox + optional Issue (sensemaking).** A persistent tray collects passages the reader saves from
   panels (foraging — §4). One opt-in gesture: pin a **Question** and let saved passages cluster into
   **Positions** around it, with suggested **pro/con tension pairs** as candidate IBIS arguments. Reversible;
   the default never leaves smooth space.

**Why this is the right one:** it is fully buildable from assets RhizomeDB already has (chunks, embeddings,
tags, concept-graph), it honors every constraint — non-metric *surface* (metric hidden), juxtapositional
(the empty-centered panel), discovery-oriented (re-centering walk, the right to find nothing) — and it keeps
the statistical machinery as the *engine* while the reader only ever touches a contemplative, smooth atlas.
Minimal first cut: ship **smooth mode alone** (panel + re-centering) — that single screen is the whole thesis.

---

*Sources:* Warburg, *Bilderatlas Mnemosyne* (2020 reconstruction; Cornell online ed.) · Benjamin, *The
Arcades Project* (Harvard, 1999) · Moretti, *Graphs, Maps, Trees* (Verso, 2005) & "Conjectures on World
Literature," *NLR* 1 (2000) · Deleuze & Guattari, *A Thousand Plateaus* (Minnesota, 1987), plateau 14 &
"Rhizome" · Pirolli & Card, "The Sensemaking Process…" (2005); Pirolli, *Information Foraging Theory* (2007)
· Kunz & Rittel (1970); Conklin & Begeman, "gIBIS" (1988); Compendium Institute.
