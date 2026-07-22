# Track C — Aletheia deepening → native context intelligence: findings

**Mode:** deep read + plan + web research. No app code changed.
**Lens (Purpose→Structure):** Drishya's act is *unconcealing an image and writing from what you felt*. Aletheia is the reading; the taste graph is the memory; the writer is the pen. Today the three are **disconnected** — the reading is generic, it's compacted to one line before it reaches the persona, and the inline writer sees **none** of it. Track C makes the reading *context-triggered*, and makes it (plus the taste vector) the **retrievable ground** the writer stands on.
**Grounding:** line refs current as of `e350127`. Cross-verified by direct read of `vision_service.py` (`brainstorm_image` `:269-326`, `_parse_aletheia` `:328-369`, `ALETHEIA_PROMPT` `:594-631`, answers-refinement `:290-303`), `schemas/post.py` (`LocalContextRequest` `:123-129`, `BrainstormRequest` `:136-139`, `local_context` `:45`), `routers/posts.py` (`set_local_context` `:371-412`, `unconceal_suggest` `:415-438`), `persona_service.py` (`add_local_context` `:189-229`, `add_region_correspondence` `:231-256`, `synthesize` `:258-284`), `llm_service.py` (`synthesize_persona` `:578-620`, `generate_story_from_plot` `:85`), `editor_llm_service.py` (`chat_with_vision` `:140`, `generate_node_expansion` `:267`, `rewrite_with_vision` `:347`).
**Consumes** (locked): Track B's domain tag (FashionCLIP router), `Region.part/attributes[]`, and the call that **atmosphere/mood is image-global → it lives here in Aletheia, not as a region** (`track-B` §6). **Writes to**: `local_context.aletheia` + the taste graph (Anuraṇana) via `embedding_id` (Track A sidecar).
**Within locked context:** context-triggered fashion-literate lenses; FashionCLIP = taste vector; RAG over the taste graph grounds the writer; two readings (deep creator + feed hook); LLM re-roled to reading/story only.

---

## 0. Headline (up front)

**Aletheia scales from a fixed 3-lens reader into the native intelligence that (a) reads each image through lenses its own context selects, and (b) becomes the retrievable ground — reading + region felt-notes + taste vectors — that makes the inline writer image-specific and taste-true.** Four moves:

1. **Context-triggered lenses.** Replace the hard-coded Phenomenological/Semiotic/Atmospheric trio (`ALETHEIA_PROMPT:613-621`) with a **lens set chosen from the image's context** — domain (Track B router), detected `part`/`attributes[]` (Track A), and mood. Fashion gets silhouette/drape/era-reference/styling-logic/mood-story; other domains get their own. The 3 generic lenses become the *fallback* when context is thin.
2. **Deeper reading schema — evidence-bound, region-tied.** A reading is "deep" when each claim **points at a named part** and **discloses its uncertainty**. Add `region_id`/`part` anchors and a per-lens `evidence` field so a lens claim ("the drape softens the severity") is tied to the actual region the writer can then cite.
3. **RAG over the taste graph (Anuraṇana).** The single biggest gap: the inline writer (`editor_llm_service.py:140,267,347`) today grounds **only** on `image_url` + `text_blocks` — it never sees the reading, the region notes, or the person's accrued taste. Inject a **compact, ranked context pack**: this image's reading + prioritised region notes + top-k FashionCLIP-retrieved past correspondences. Retrieval over `region_embeddings` = the taste graph made queryable.
4. **Two readings, one engine.** Same call, two renders: the **deep creator reading** (all lenses, evidence, forks) and a **short feed-hook reading** (1–2 sentences + one perceptual fork) — the "Aletheia-in-feed" B2C moment whose taps double as `actor="audience"` taste signal (feeds Track F).

**Naming:** **Aletheia stays** as the reading engine. **Anuraṇana** = the taste graph / RAG store it writes into and retrieves from; **Écart** = the reading act itself (the pause Darshan opens in the scroll). See §8.

---

## 1. Current-Aletheia map (what exists, grounded)

**The reading.** `brainstorm_image(image_url, answers?)` (`vision_service.py:269-326`) → one Groq `llama-4-scout` vision call on `ALETHEIA_PROMPT` (`:594-631`), temp 0.65, `max_tokens=1100`. The prompt **hard-codes exactly three lenses** — Phenomenological, Semiotic, Atmospheric (`:613-621`) — each with a 1–2 sentence `reading` + `intensity` 0–100; plus 1–3 MCQ `questions` (perceptual forks), a `concealed` line, and `uncertainty`. `_parse_aletheia` (`:328-369`) normalizes and caps ≤5 lenses / ≤3 questions.

**The refinement.** Prior viewer choices (`answers`, `BrainstormRequest.answers` `schema:136-139`) are folded back into the prompt (`:290-303`): "let these choices reshape the lenses… ask FEWER, deeper questions." A real round-by-round dialogue — but **stateless** (answers must be re-sent; nothing accrues except via local_context below).

**The storage.** `POST /posts/{id}/local-context` → `set_local_context` (`posts.py:371-412`) stores `local_context = {commentary, aletheia, updated_at}` on the post (`:386-391`; field `schema:45`). `LocalContextRequest` (`schema:123-129`) = `{commentary, aletheia, feed_to_persona}`. `unconceal_suggest` (`posts.py:415-438`) pre-drafts a first-person commentary from a fresh Aletheia run.

**The roll-up (macroscopic).** `add_local_context` (`persona_service.py:189-229`) **compacts the whole reading to one string** — `aletheia_note` = 3 lens readings + `concealed` joined by " · " (`:204-212`) — deduped by `post_id`, capped 60. `add_region_correspondence` (`:231-256`) rolls prioritised region notes up as "Parts that moved me — …". `synthesize_persona` (`llm_service:578-620`) later feeds `local_contexts[:20]` close-readings into the Darpan dossier (`:610-621`).

**The writing (the disconnect).** The inline slash AI — `chat_with_vision` (`editor_llm_service:140`), `generate_node_expansion` (`:267`), `rewrite_with_vision` (`:347`) — is called with **`image_url` + `text_blocks` + user text only**. Story generation `generate_story_from_plot` (`llm_service:85`) uses `aggregated_text` but not the reading or regions. **No writing path ingests `local_context.aletheia`, the region felt-notes, or the taste catalog.** The intelligence exists; the pen never sees it.

### The four gaps Track C closes
| Gap | Evidence | Fix |
|---|---|---|
| **Lenses are fixed & generic** | 3 hard-coded lenses `ALETHEIA_PROMPT:613-621` | Context-triggered lens selection (§2) |
| **Claims aren't grounded in parts** | reading is free text; no region link in schema | Evidence-bound, region-tied reading (§3) |
| **Reading never reaches the writer** | `editor_llm_service` grounds on image+blocks only `:140,267,347` | RAG context pack injected (§4) |
| **Reading is lossy into memory** | compacted to one `aletheia_note` string `:204-212`; no vector | Structured store + FashionCLIP vectors (§4, §6) |

---

## 2. Context-trigger design — lenses chosen by the image

**Mechanism (two-stage, cheap):**

**Stage 1 — assemble the context header** (no extra model calls; reuse Track B outputs already computed at detect-time):
- `domain` — from the FashionCLIP router (Track B §3): fashion | architecture | photography | general.
- `parts` — the salient `Region.label/part/category` (top-k by area/prioritised).
- `attributes` — the union of `Region.attributes[]` (Fashionpedia 294-vocab) present.
- `mood_seed` — a cheap FashionCLIP zero-shot against a small mood prompt set (serene/severe/nostalgic/playful/opulent…), OR left to the LLM if CLIP mood is weak.

**Stage 2 — select the lens set** from a **domain→lens registry** (config, not hard-code), then let the LLM *instantiate* the chosen lenses over this image:

| Domain | Lens set (replaces the fixed 3) |
|---|---|
| **fashion** | Silhouette · Drape/Material · Era/Reference · Styling-logic · Mood/Story |
| **architecture** | Structure/Line · Material/Texture · Light/Shadow · Scale/Space · Atmosphere |
| **photography** | Composition/Frame · Light · Subject/Gesture · Colour · Atmosphere |
| **general (fallback)** | Phenomenological · Semiotic · Atmospheric *(today's three)* |

- **Trigger rules:** domain picks the base set; **detected parts/attributes bias which lenses fire and what they attend to** (e.g. many `drape`/`fold` attributes → Drape lens gets priority + higher expected intensity; a strong `era` attribute → Era/Reference lens activates). The `lens` free-text intention already in `RegionDetectRequest` (Track B) can pin a lens too.
- **How it's implemented:** `ALETHEIA_PROMPT` becomes a **template with a `{lens_registry}` + `{context_header}` slot** (same pattern Track B uses for `SOOKSHMA_PROMPT` `{focus}` `vision_service:495,682`). The model is told *which* lenses to use and *what context grounds them*, so it reads specifically instead of defaulting to generic three. **Atmosphere/mood stays a lens here** (image-global, per Track B §6) — it is Aletheia's, never a region.
- **Graceful degradation:** no domain / thin context → fall back to the general 3-lens set (today's behavior) — nothing regresses when Track B isn't wired yet.

---

## 3. Deeper reading schema — evidence-bound, region-tied

A reading is *deep* (not generic) when: (a) each lens claim is **specific to this image**, (b) it is **anchored to a named part**, (c) lenses may **disagree** (tension is signal, already encouraged `ALETHEIA_PROMPT:606`), and (d) it **discloses uncertainty** (already present as `uncertainty`/`concealed`). Extend the schema to *enforce* the anchoring:

```jsonc
{
  "domain": "fashion",                     // from Track B router (context provenance)
  "lenses": [
    {
      "name": "Drape",
      "reading": "the silk's slack fall softens the jacket's hard shoulder line",
      "intensity": 78,                      // 0-100 (kept; drives UI bars)
      "region_ids": ["seg_2", "fine_5"],   // NEW: parts this claim is grounded in
      "evidence": "loose vertical folds below the waist seam"  // NEW: what in the image
    }
  ],
  "tension": "Silhouette reads severe; Drape reads tender — the image holds both",  // NEW: cross-lens
  "questions": [ {"prompt": "...", "options": ["...","..."]} ],  // kept: perceptual forks
  "concealed": "...",                       // kept
  "uncertainty": "..."                      // kept
}
```

- **`region_ids` + `evidence` per lens** are the deepening: they turn a floating claim into one the writer can *cite* ("as the drape at the hem shows…") and the UI can *highlight* (lens ↔ region link — the Track D hover). This is the felt-meaning-per-part the whole thesis rests on.
- **`tension`** names the cross-lens disagreement explicitly (today it's only implied). One line; high narrative value for Sutradhar.
- **Backwards-compatible:** `region_ids/evidence/tension/domain` are additive; when absent the reading renders exactly as today. `_parse_aletheia` gains null-safe parsing of the new keys (cap region_ids to real ids present on the post).
- **Storage:** the richer object still lands in `local_context.aletheia` (`posts.py:386`) — no new field, just a richer dict (the field is untyped `schema:45`, so this is free). The persona roll-up should stop *flattening to one string* and keep the lens/region structure (§6).

---

## 4. Context-engineering / RAG plan — Anuraṇana feeds the writer

**The target:** make the inline writer (`editor_llm_service:140,267,347`) and story generation (`llm_service:85`) produce prose grounded in *this image + this person's accrued taste*, instead of image+blocks alone.

**What's stored (the graph, Anuraṇana):**
1. **Per-image reading** — the richer `local_context.aletheia` (§3), structured (not one-line).
2. **Per-region felt-notes** — `Region.user_note` + `label/part/attributes` for prioritised regions (already saved via `region-annotations`; `add_region_correspondence:231`).
3. **Taste vectors** — FashionCLIP `embedding_id` → `region_embeddings` sidecar (Track A/B). This is what makes the graph *queryable* rather than count-based.
4. **Persona dossier** — the existing Darpan synthesis (`synthesize_persona:578`) as the coarse voice/aesthetic profile.

**What's retrieved (per writing request):**
- **Local, always:** this post's reading (lenses+evidence+tension) + its prioritised region notes. Zero retrieval cost — it's on the post.
- **Global, vector:** embed the current image/region (FashionCLIP) → **top-k similar past regions/images** from `region_embeddings` (the person's own history first; optionally the catalog). Return their `user_note` + label — "here's how you've felt about drape like this before." This is the taste-grounding, done as **multi-vector retrieval**: retrieve on compact vectors, inject the raw notes ([LangChain multi-vector pattern](https://www.langchain.com/blog/semi-structured-multi-modal-rag)).
- **Coarse, cached:** the persona `voice{tone,vocabulary,devices}` (from the dossier) for style.

**What's injected (the context pack — compact & ranked, not a dump):**
```
[IMAGE READING]   domain; 2-4 fired lenses w/ evidence; the tension line; concealed
[PARTS THAT MOVED THEM]  prioritised regions: label/part — user_note
[YOUR TASTE HISTORY]     top-k retrieved: "drape → 'the give of it undoes the structure'" ×N
[VOICE]           tone / vocabulary / devices (from persona)
[THE ASK]         user's slash command + current block/selection
```
- **Discipline (grounded in the research):** RAG degrades under **prompt saturation** and the **"lost-in-the-middle"** effect — LLMs attend poorly to mid-prompt evidence ([RAGFlow 2025 review](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)). So the pack is **small, ranked, front-and-back-loaded** (reading + ask at the salient ends), top-k tight (≤5 retrieved notes), and **structured with labels** so the model can find each part. This is *context engineering*, not "stuff everything in."
- **Personalization stages** map cleanly ([Personalized-RAG survey](https://github.com/Applied-Machine-Learning-Lab/Awesome-Personalized-RAG-Agent)): pre-retrieval = the reading as query expansion; retrieval = FashionCLIP similarity + persona rerank; generation = inject the taste notes + voice.
- **Where it plugs in:** a new `build_context_pack(post_id, block, command)` helper the writing endpoints call before their LLM request — additive, no rewrite of the editors; they just receive a richer system/context block. The reading + regions are free (on the post); only the vector top-k touches the sidecar.

**Result:** `/draft`, `/continue`, `/part`, `/rewrite` stop writing generic captions and start writing *from what this image is and how this person sees* — the "detached AI captions" gap named in strategy §3b.

---

## 5. Two readings, one engine

Same Aletheia call, two render depths (a `depth` param, cheap):

| | **Deep reading (creator)** | **Feed-hook reading (audience)** |
|---|---|---|
| Trigger | Unconceal tab / explicit run | scroll pause on an image ("read deeper") |
| Content | all fired lenses + evidence + region links + tension + 1–3 forks | **1–2 sentence** distilled reading + **one** perceptual fork |
| Cost | full `max_tokens`, all lenses | tight tokens, 1 lens distilled → cheap/fast |
| Output use | grounds writing (§4), accrues to persona | the B2C hook; **the fork tap = `actor="audience"` signal** |
| Signal captured | curator commentary + prioritised regions | which fork chosen + dwell (→ Track F) |

- **The fork is the bridge:** the existing MCQ mechanism (`ALETHEIA_PROMPT:620`, forks already generated) is *already* the low-friction taste-capture strategy §5 asked for — a tap that "feels like play, reads like data." The feed-hook render surfaces one fork; the tap writes an `actor="audience"` region/preference signal into Anuraṇana. **Track C produces the reading + fork; Track F owns the audience-ingest endpoint** (locked boundary, Track A Q5).
- **One engine, no divergence:** both come from the same lens-selection + prompt; the feed hook is just the deep reading with `depth="hook"` (fewer lenses, hard token cap, one fork). Keeps creator and audience on the same intelligence — the whole two-sided premise.

---

## 6. Feedback loop — answers + commentary → persona (and vectors)

Today: viewer `answers` reshape the *current* reading only (`vision_service:290-303`); curator commentary + a **flattened** reading roll into the persona (`add_local_context:204-212`); regions roll up as notes (`add_region_correspondence:231`). Three upgrades:

1. **Keep the structure on roll-up.** Stop compacting the reading to one `aletheia_note` string (`persona_service:204-212`) — store the fired-lens names + intensities + region links so the persona (and later RAG) can retrieve *which lenses consistently fire* for this person, not just prose. (The catalog already does frequency; this adds the reading dimension.)
2. **Answers/commentary → taste vectors.** When a curator prioritises a region + writes a note, or an audience taps a fork, embed the associated region (FashionCLIP) and write/annotate its `embedding_id` — so the *felt* signal, not just the label, accrues in Anuraṇana. This is what upgrades the persona from "what they photograph" to "what moves them, in vector space."
3. **Persona → next reading (closing the loop).** Feed the persona's recurring lenses/aesthetic back into the *lens-selection* (§2) as a prior — "this curator reads for drape and era" biases which lenses fire next time. The reading gets *personal*, not just contextual. (Guardrail: a prior, not a straitjacket — always allow the image to surprise; disclose when the prior is driving.)

Net: **look → read → mark → write → accrue → read better.** The loop the brief names, now with a vector spine.

---

## 7. Attributes-in-catalog call (Track A Q4, delegated to me)

**Decision: do NOT bucket the frequency catalog on `attributes[]`. Serve attributes via vector similarity (Anuraṇana), not label counts.** Keep the current `(category, label)` aggregation in `anatomy_catalog_service` exactly as-is.

Why:
- **Cardinality.** 294 Fashionpedia attributes × combinations → exact-match buckets **fragment badly** (each region carries several attributes; the cross-product explodes the bucket space and every bucket ends up tiny). The frequency catalog's value is *concentration* ("neckline moves them 12×"); attributes would dilute it.
- **Right tool.** Attributes are a **semantic space**, not a tally. "Asymmetric + draped + matte" is meaningful by *similarity*, which is exactly what FashionCLIP vectors give. Bucketing throws that structure away.
- **Consistency with locks.** Matches Track A's "keep the six-key catalog stable" and Track B's "vectors supersede attribute-counting." The catalog stays the coarse, legible profile; **Anuraṇana (vector retrieval) is where attributes earn their keep** — powering the RAG top-k (§4) and taste-match (Track F).
- **Escape hatch:** if a *specific* high-value attribute facet is wanted in the legible catalog later (e.g. "materials"), add it as a **deliberate, curated facet** — not blanket 294-way bucketing. (Materials already aggregate via the `material` field.)

So: `attributes[]` are stored on the region (Track A), embedded/retrieved via FashionCLIP (Track B/C), and **surfaced through similarity, never counted**. Flagged and decided here per the delegation.

---

## 8. Naming — Aletheia stays; its relations

- **Aletheia stays** the name of the **reading engine** (the unconcealment act's intelligence). It scales up (context-triggered, evidence-bound, feeds the writer) — same name, deeper faculty. This matches the brief's §6 ("keep Aletheia… it graduates from a 3-lens reader to the context brain") and the "confirm Aletheia scales up" ask. *Caveat noted in `decisions-darshan:123`: it's the one Greek name in a Sanskrit set — cosmetic, non-blocking.*
- **Anuraṇana** (अनुरणन — the after-resonance, the echo that lingers) = the **taste graph / RAG store** Aletheia writes into and retrieves from — the accruing felt-overtone of a person's looking. This is the store §4 queries.
- **Écart** (Merleau-Ponty — the divergence that holds perception open) = the **reading act itself / the pause Darshan opens in the scroll** — i.e. *what Aletheia performs* on the feed-hook (§5). This resolves the open sub-question in `decisions-darshan:155` toward the **split assignment** (Anuraṇana = the graph, Écart = the reading-pause) — recommended, since it gives the two concepts distinct homes: Écart is the moment, Anuraṇana is what it leaves behind. **Adarsh to confirm the assignment** (Q6).

---

## 9. Feed-forward & boundaries

- **To the writer (Sutradhar / slash AI):** the context pack (§4) — this is Track C's main deliverable to the build.
- **To Track D (frontend):** the lens↔region links (`region_ids` §3) enable hover-highlight; the feed-hook render + single fork is the B2C surface to design; two-readings `depth` param.
- **To Track F (consumer):** the feed-hook reading + fork; Track C emits the reading + fork, **Track F owns the audience-ingest endpoint** and its auth/rate-limit/abuse (locked, Track A Q5).
- **From Track B:** domain tag, `part/attributes[]`, region geometry, `embedding_id`. From **Track A:** the schema + `region_embeddings` sidecar.
- **Not Track C's:** geometry/detection (Track B), the embedding *storage* mechanism (Track A), the audience endpoint (Track F), dedup/precedence (Track B).

---

## Questions for Adarsh

1. **Lens registry — config vs generated?** I propose a small **fixed domain→lens registry** (§2 table) the LLM instantiates, so lenses are legible/stable and the UI can label them. The alternative is letting the LLM freely *invent* lenses per image (more surprising, less consistent, harder to build hover-links on). I lean fixed-registry + LLM instantiation. Agree?
2. **How personal should the reading get?** §6.3 feeds the persona's recurring lenses back as a *prior* on lens-selection. Powerful (readings get personal) but risks an echo chamber (always reading for drape). Cap the prior's weight / always keep a "wildcard" lens that ignores history? I recommend yes (keep it surprising). Your call on how strong the personalization is.
3. **Retrieval scope for the writer's taste-grounding (§4).** Top-k from **this person's own history only** (safest, most personal), or also the **cross-curator catalog** (richer, but risks homogenizing voice / leaking others' notes)? I lean own-history-first, catalog opt-in. Confirm.
4. **Feed-hook cost.** The B2C "read deeper on scroll pause" is an LLM call per pause — cheap per call, but at audience scale it adds up. Acceptable to gate it (only on a deliberate tap, cache per image so the *same* image's hook is computed once and reused for all viewers)? I recommend cache-per-image + tap-gated, not auto-on-every-pause. (Ties to Track F cost.)
5. **Persona roll-up richness (§6.1).** OK to stop flattening the reading to one line and store the structured lens/region data in the persona (bigger persona docs, richer retrieval)? Or keep the persona lean and rely on per-post `local_context` for the detail? I lean structured-but-capped.
6. **Écart / Anuraṇana assignment (§8).** Confirm the split: **Anuraṇana = the taste graph** (what accrues), **Écart = the reading act / the pause** (what Aletheia performs). And confirm **Aletheia stays** as the engine name despite the Greek-in-Sanskrit-set caveat.
7. **Attributes-in-catalog (§7).** Confirm my delegated call: attributes serve via **vector similarity only**, the frequency catalog stays `(category, label)`, no 294-way bucketing.

*Research + plan only — no app code touched. This plans Aletheia's deepening (context-triggered, evidence-bound reading) and its promotion to the native intelligence: the RAG context pack over Anuraṇana that finally connects the reading to the pen. The one real build dependency is Track B's domain tag + FashionCLIP embeddings; everything degrades gracefully to today's behavior without them. Sources below.*

---

### Sources
- [From RAG to Context — 2025 year-end review (RAGFlow)](https://ragflow.io/blog/rag-review-2025-from-rag-to-context) — prompt saturation, lost-in-the-middle, context engineering
- [Multi-Vector Retriever for RAG on tables/text/images (LangChain)](https://www.langchain.com/blog/semi-structured-multi-modal-rag) — retrieve on vectors, inject raw
- [Awesome Personalized-RAG-Agent survey (GitHub)](https://github.com/Applied-Machine-Learning-Lab/Awesome-Personalized-RAG-Agent) — personalization across pre-retrieval/retrieval/generation
- [Principled Context Engineering for RAG (arXiv 2511.17908)](https://arxiv.org/pdf/2511.17908) — context engineering as a field
- [FashionCLIP (HF)](https://huggingface.co/patrickjohncyh/fashion-clip) — the taste-vector model (per Track B / model-integration-plan)
