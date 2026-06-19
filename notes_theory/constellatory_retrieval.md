# Constellatory Retrieval

> The core retrieval idea for the standalone cognitive-database project. Retrieval that
> surfaces **unexpected-but-not-forced** connections between distant parts of a theory corpus
> (e.g. a Deleuze paragraph ↔ a passage in Heidegger), offered as *invitations to explore*
> rather than answers. Drafted 2026-06-18.

---

## 0. The one-line definition

**Constellatory retrieval** = retrieval whose output is a *juxtaposition*, not an *answer* —
it discloses a latent connection between distant passages by arranging them around a shared
bridge concept, where the connection is real (both passages genuinely instantiate it) but
unobvious (neither names it prominently), and where the system is permitted to find **nothing**.

It is **aletheia applied to retrieval**: Semant unconceals what an image does to you; this
unconceals the connections sleeping in a body of theory. The retrieval *is* the unconcealment.

## 1. Why the name

- **Constellation** (Benjamin / Adorno): meaning arising from the *configuration* of juxtaposed
  elements without subsuming them under a single concept. A constellation is not arbitrary (the
  stars are really there) and not forced (the figure is disclosed, not imposed). That is exactly
  the line this retrieval must walk. **Primary name.**
- **Resonance** — simpler, user-facing verb ("this resonates with…"); already used in the vision notes.
- **Rhizomatic** (Deleuze & Guattari) — apt for the *graph topology* (non-arborescent, any-to-any)
  but dangerous as the retrieval *ethic*: "anything connects to anything" is the forced-connection
  failure mode. Use for the data structure, not the policy.

Recommendation: build under **constellatory**; use **resonance** as the user-facing verb.

## 2. What it is NOT (the category distinction)

- **NOT lookup search** — "the answer lies somewhere, fetch it." (Plain RAG.)
- It is closer to **exploratory search** (Marchionini) and to **serendipity** in recommender
  systems (novelty × diversity × unexpectedness) — but more radical: those assume the connection
  pre-exists and needs surfacing; constellatory retrieval *produces a juxtaposition that may never
  have been made before*. Past discovery, into disclosure.

## 3. The central tension — and how to hold it

**Unexpected but not forced.** These pull apart, and most systems collapse to one pole:
- Toward *unexpected* → apophenia: everything connects to everything at enough abstraction.
- Toward *not forced* → trivial top-k similarity: only the neighbors you'd have guessed.

The whole engineering problem is staying in the narrow band between **triviality** and
**arbitrariness**. Reframing that makes it tractable: **condition retrieval on the trajectory,
not on a query.** "The flow of the theory at the moment" = the connection grows from *where you
currently are* in conceptual space, not from a fixed question. So it must be **traversal, not
lookup** — which is why the concept graph / journey record is load-bearing, not decorative.

## 4. Mechanisms (how to actually produce it)

1. **Mid-distance retrieval** — *the most important, most implementable knob.* Retrieve from the
   **annulus**: the middle band of similarity. Not the nearest (banal), not random (noise). The
   spark lives at a specific distance. Implement as a similarity *window* `[lo, hi]`, not top-k.
2. **Bridge-concept retrieval** — A↔C connect through an intermediate concept B that *neither text
   names prominently*. Extract each passage's concepts, find a concept structurally shared with the
   other corpus, return the passage that most strongly instantiates it. (This is where the concept
   graph earns its existence.)
3. **Cross-corpus constraint** — force the *juxtaposition* deliberately ("from where we are in
   Deleuze, search only the Heidegger sub-corpus") but let the *content* of the match be organic.
   You choose to look across a boundary; you don't choose what you find.
4. **Surprise-adjusted ranking** — score by `relevance × unexpectedness`, not relevance alone.
   Penalize passages that co-occur with the source everywhere (expected); reward those that don't
   but still share the bridge (surprising + grounded).
5. **Trajectory conditioning** — the query vector is a function of the accumulated journey (recent
   passages + bridges traversed), so each new connection emerges "of the moment."

## 5. The "not forced" safeguards (the integrity of the whole thing)

1. **The system MUST be allowed to return nothing.** A retriever that *always* finds a profound
   connection is lying. The willingness to say "no genuine resonance here right now" is what makes
   the connections it *does* offer trustworthy. Build the **null result** in from day one.
2. **Groundedness floor.** Every proposed connection points to the actual passages on both sides
   and names the bridge concept. Never "Deleuze and Heidegger agree" — always "*these two passages*
   both move through *this concept*; here they are; judge for yourself."
3. **Offer as a question, not an assertion.** "Does this turn in Deleuze resonate with Heidegger's
   account of X?" (= reuse the Aletheia `questions` mechanism.) Makes it an *invitation to explore*,
   hands final validation to the flow of thought, not the model.

## 6. v0 retrieval-policy spec (buildable on a plain RAG stack)

No new infrastructure — this is a **ranking/policy layer** over ingest→embed→vector-store.

```
INPUT:  source_passage (or current journey context), target_corpus filter
1. q = embed(source_passage)                       # or embed(journey context)
2. candidates = vector_search(q,
        corpus = OTHER_PHILOSOPHER,                 # §4.3 cross-corpus
        k = 200)
3. band = [c for c in candidates if lo <= sim(q,c) <= hi]   # §4.1 mid-distance window
4. for c in band: bridge = extract_shared_concept(source_passage, c)   # §4.2
       drop c if bridge is None
5. rank band by  sim(q,c) * surprise(c)            # §4.4  surprise = 1 - expectedness
6. take top n (n small, e.g. 3)
7. if band empty OR best score < THRESHOLD: return NULL  # §5.1 allow nothing
8. for each kept c: LLM articulates the bridge, citing BOTH passages,
       phrased as a QUESTION (§5.3), with provenance (§5.2)
OUTPUT: 0–3 constellation cards {source, target, bridge_concept, citations, question}
```

**Tunables to learn empirically:** the `[lo, hi]` similarity window (start ~0.55–0.78 cosine,
adjust by feel), `THRESHOLD` for the null result, `surprise` definition (start: inverse corpus
co-occurrence of the bridge concept), `n`.

**Evaluation** (2-axis, per the study guide): groundedness (does each side really instantiate the
bridge? citation-faithful?) × disclosure (novelty: would plain top-k have surfaced this? specificity:
does the bridge cash out concretely? generativity: does the question open further paths?). Honest
test: A/B constellatory vs. plain top-k on the same source — *more surprising AND more concrete*, or
just more pretentious?

## 7. Migration path (plain RAG → constellatory)

See `notes_theory/cognitive_db_study_guide.md` §9 for the full build order. In short:
plain retrieve-answer (validate pipeline) → add cross-corpus + mid-distance window (the cheapest
big step) → add concept extraction + bridge filter → add surprise ranking + null result →
add trajectory conditioning (journeys) → the journey log becomes the accreting concept graph.
