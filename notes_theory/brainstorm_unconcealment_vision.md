# Brainstorm / Unconcealment — Vision & Research Notes

> Theory note for the Chrome-extension "Brainstorm" feature and the longer-term
> phenomenological-image direction of Semant / Sharirasutra.
> Drafted 2026-06-18.

## 0. The core intent (stated plainly)

When a person scrolls Twitter / Instagram and an image *enchants* them, the
enchantment is mostly **concealed** — felt but not known. The current extension
only *saves*. The new direction is to help the viewer **unconceal**: to make the
working of the image on them perceptible, so the scroll stops being passive
consumption and becomes an encounter.

The philosophical name for this is Heidegger's *aletheia* — truth as
**unconcealment**, the thing emerging from hiddenness. The feature is a small
machine for aletheia applied to the feed image. The *mood* we are cultivating is
Jane Bennett's **enchantment**: openness to the captivating in everyday life,
against the disenchantment of the scroll.

The key design commitment: **disclosure, not captioning.** Not "what is depicted"
but "how it appears, what it does to me, and what it withholds."

---

## 1. The interpretive lenses (you have 3 — here are more)

Your three (anatomical, phenomenological, narrative) are good. Each lens should be
a distinct *voice* grounded in a real tradition, not a generic LLM paraphrase.
A fuller palette to choose / rotate from:

| Lens | Root tradition | What it asks of the image |
|---|---|---|
| **Anatomical** | structure / morphology | What are the parts, the body, the construction? |
| **Phenomenological** | Merleau-Ponty | How does it appear to a *lived body*? weight, texture, temperature, the "viscosity of syrup" |
| **Narrative** | story | What happened just before / after this frame? |
| **Semiotic** | Barthes | Denotation vs **connotation**; **studium** (cultural reading) vs **punctum** (the wounding detail) |
| **Compositional / formal** | art analysis | line, light, colour, balance, gaze-vectors, where the eye is led |
| **Affective** | valence–arousal models | What mood does it induce? what is the emotional temperature? |
| **Atmospheric** | Böhme's *atmospheres* | What is the *Stimmung*, the spatial mood it radiates? |
| **Mythic / archetypal** | Jung, Campbell | symbols, archetypes, the image's deep pattern |
| **Material / "earth"** | Heidegger | the medium that resists disclosure — grain, pixels, surface |
| **Auratic** | Benjamin | uniqueness vs reproduction; does this feed-image still have *presence*? |
| **Temporal / the "that-has-been"** | Barthes' *noeme* | the image as evidence that *this was*; traces of time, mortality |
| **Ethical / the gaze** | Berger, Sontag, Mulvey | who looks, who is looked-at, what power runs through it |
| **Cross-modal / synaesthetic** | — | what sound, smell, taste does it evoke? |
| **Counterfactual / concealed** | Heidegger (concealment) | what is *outside the frame*? what does it withhold? |

Design note: lenses should be **allowed to disagree**. The anatomical and the
phenomenological reading of the same image contradicting each other is itself a
disclosure. (See "Town Hall Debate" prompting in §3.)

---

## 2. Feature / UX ideas beyond the bar-descriptions

The multi-bar realtime UI is the right surface. Ideas to deepen it:

1. **The punctum prompt.** Don't only *describe* — turn it back on the viewer.
   The tool surfaces a detail and asks *"what here pierces you?"* This is the
   anti-doomscroll move: active unconcealment instead of passive reception. The
   punctum is *personal and cannot be predicted by the model* — so the UX should
   invite it rather than assert it.
2. **"What is concealed" panel.** Explicitly name what the image withholds /
   what lies outside the frame. Concealment is the precondition of unconcealment.
3. **Render the model's uncertainty** as part of the reading — the "earth that
   resists." Confidence/ambiguity shown, not hidden. Honest disclosure includes
   the limits of disclosure.
4. **Slow-looking / dwell mode.** A counter to the scroll: the longer you look,
   the more layers reveal. Reward attention, not clicks.
5. **Save the *encounter*, not just the image.** Persist: the post + which lens
   enchanted you + your one-line note + your punctum. Over time this becomes a
   **phenomenological journal** of your perceptual life.
6. **Cross-modal evocation.** Generate the sound / smell / texture the image
   implies; optionally a few seconds of ambient audio.
7. **Re-auratization.** Reframe the infinitely-reproduced feed image as
   "this one, now, for you" — restoring a sliver of Benjamin's aura.
8. **Personal lexicon growth.** Your existing `phrase_learning` collection becomes
   an evolving *personal aesthetic vocabulary* — the system learns *your* punctum
   patterns, your recurring words.
9. **Resonance.** "This rhymes with an image that enchanted you 3 weeks ago."
   (Requires semantic memory — §4.)

---

## 3. Context engineering — the technical heart

This is the answer to *"not just immediate LLM output."* The output is the
surface; the durable value is **context that accretes over time.**

**(a) From one prompt to multi-lens orchestration.**
Each lens = a *worker*; an *evaluator/merger* composes the bars. This is exactly
Anthropic's orchestrator-worker + evaluator-optimizer pattern (see refs). Maps
cleanly onto your existing `vision_service` / `llm_service` / `editor_llm_service`
split.

**(b) Perspective / persona prompting per lens** — with care. Research shows
persona prompting steers viewpoint but can amplify bias and stereotype and reduce
diversity; treat lenses as *framings*, not as impersonations of real groups.
**Town Hall Debate prompting** (personas argue, critique, vote) is a good fit for
letting lenses disagree productively.

**(c) Retrieval-augmented interpretation (RAG over a theory corpus).**
This is the single biggest lever against generic LLM mush. Ground each lens in a
curated corpus — Barthes, Berger, Merleau-Ponty, Sontag, Benjamin, art-historical
formal-analysis texts — so a phenomenological reading actually *echoes
phenomenology* instead of improvising. Directly answers "not just what the LLM
spits out."

**(d) Multimodal semantic memory.**
Embed every encountered image (CLIP-style cross-modal embeddings) and store the
vectors **in MongoDB Atlas Vector Search**, alongside your existing `posts`. You're
already on Atlas; `$vectorSearch` + auto-embeddings (Voyage AI) makes this
low-friction. This powers *resonance* across images and turns tag-filtering into
true semantic retrieval.

**(e) A multimodal knowledge graph — the long-memory.**
Nodes = images, lenses, motifs, *your reactions*. Edges = resonance,
contradiction, recurrence. This is the structure that lets the system build an
**atlas of your enchantment** over months — context that is not immediate, that
the LLM alone could never hold.

**(f) Memory tiers** (Anthropic context-engineering model):
- *Ephemeral* — this image, this overlay.
- *Session* — this scroll.
- *Long-term* — your evolving aesthetic self (the graph + lexicon + journal).

**(g) Personalization profile.**
A P-MLLM–style aesthetic profile conditions the reading, so the lenses speak to
*your* perceptual history rather than a generic viewer.

---

## 4. The long-term arc (phased)

The shift is: **description tool → phenomenological companion** that, over time,
maps your perceptual life. Suggested phases:

1. **Multi-lens overlay** (immediate) — the brainstorm button with disagreeing
   lenses and the "what is concealed" panel.
2. **Encounter capture** — save image + lens + note + punctum → personal journal.
3. **Semantic memory** — embeddings in Atlas Vector Search → cross-image resonance.
4. **Knowledge graph** — motifs / reactions / recurrence → your atlas of enchantment.
5. **RAG-grounded lenses** — the curated theory corpus + personalization profile.
6. **Longitudinal self-disclosure** — patterns in *what enchants you* over time;
   the project's deepest payoff and its true differentiator.

The throughline: the LLM is the lens-grinder; the lasting artifact is the slowly
accreting **semantic + phenomenological memory** of one person's encounters with
images.

---

## 5. Reading list

### Humanities / image theory
- **Roland Barthes, *Camera Lucida*** — studium vs **punctum**, the *noeme*
  ("that-has-been"). The conceptual spine of the whole feature.
  https://en.wikipedia.org/wiki/Camera_Lucida_(book)
- **Martin Heidegger, *The Origin of the Work of Art*** — *aletheia* /
  unconcealment, world vs earth, concealment as precondition.
  https://en.wikipedia.org/wiki/The_Origin_of_the_Work_of_Art
- **Maurice Merleau-Ponty, *Phenomenology of Perception* / *Eye and Mind*** —
  embodied, multisensory vision; the lived body behind the gaze.
  https://philarchive.org/archive/PERIAO  ·  "Aesthetics of the Invisible":
  https://www.tandfonline.com/doi/full/10.1080/20539320.2024.2418881
- **Walter Benjamin, *The Work of Art in the Age of Mechanical Reproduction*** —
  **aura**, reproduction, presence; acutely relevant to feed images.
  https://en.wikipedia.org/wiki/The_Work_of_Art_in_the_Age_of_Mechanical_Reproduction
- **Susan Sontag, *On Photography*** — the ethics of looking and accumulating images.
- **Jane Bennett, *The Enchantment of Modern Life*** — wonder in the everyday;
  the *mood* this whole project is trying to restore.
  https://press.princeton.edu/books/paperback/9780691088136/the-enchantment-of-modern-life
- **John Berger, *Ways of Seeing*** — canonical primer on the gaze and visual
  literacy (no single canonical URL; widely available).
- **Gernot Böhme, *Atmosphere* / aesthetics of atmospheres** — the "atmospheric" lens.

### Technical / AI
- **Multimodal LLMs Can Reason about Aesthetics in Zero-Shot** (arXiv 2501.09012)
  — perception + emotion + cultural context woven into evaluative narratives.
  https://arxiv.org/html/2501.09012v3
- **CognArtive: LLMs for Automating Art Analysis** (arXiv 2502.04353)
  — decoding aesthetic elements / formal analysis. https://arxiv.org/html/2502.04353v1
- **AesBench** (arXiv 2401.08276) — benchmark for MLLM aesthetic perception.
  https://arxiv.org/pdf/2401.08276
- **Profile-aware MLLM for personalized aesthetics (P-MLLM)** (arXiv 2604.17233)
  — user-profile-conditioned reading. https://arxiv.org/html/2604.17233v1
- **Evaluating LLMs' capacity to interpret emotions in images** (PMC)
  — valence/arousal from visual stimuli.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12133009/
- **Persona Prompting** (overview) https://www.emergentmind.com/topics/persona-prompting-pp
  and the **perspectivism / annotator-persona** caveats (arXiv 2508.17164)
  https://arxiv.org/html/2508.17164 — read for the bias warnings before shipping lenses.
- **Multimodal knowledge graphs** — survey list
  https://github.com/ZihengZZH/awesome-multimodal-knowledge-graph ·
  multi-modal search over KGs https://hypermode.com/blog/multi-modal-search-knowledge-graphs
- **Agentic RAG: A Survey** (arXiv 2501.09136) https://arxiv.org/abs/2501.09136
- **Anthropic — Building Effective Agents**
  https://www.anthropic.com/research/building-effective-agents
- **Anthropic — Effective Context Engineering for AI Agents**
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- **MongoDB Atlas Vector Search** https://www.mongodb.com/products/platform/atlas-vector-search
  · Voyage AI / auto-embeddings
  https://www.mongodb.com/company/blog/technical/scaling-vector-search-mongodb-atlas-quantization-voyage-ai-embeddings
