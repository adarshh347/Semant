# Darshan decisions — Track A locks + strategy forks (detailed)

**Status:** Track A's 7 questions **answered/locked** (Adarsh delegated: "whatever seems fitting"). The 6 strategy forks are **framed in detail with a recommendation each, pending Adarsh's pick** (these remain his call).
Keep Darshan decisions here for now (the main `decisions-log.md` has the other thread's uncommitted edits); promote to `decisions-log.md` once that tree is clean.

---

## Part 1 — Track A's 7 questions: LOCKED

Answers chosen to unblock the build with the lowest risk. Rationale from `responses/track-A-datamodel.findings.md` (the merge is near-free: **0 rows of `bounding_box_tags` in prod**).

1. **Field name → keep `region_annotations`. LOCKED.** Renaming to `regions` is cosmetically nicer but touches the catalog `$exists` queries + every consumer for no functional gain. Keep the name; zero catalog churn.

2. **Retire `bounding_box_tags` outright → YES, hard-deprecate. LOCKED.** 0 rows to migrate. Remove from `PostUpdate`, stop initializing it on create/upload/bulk, keep it read-only emitting `{}` for one release, then delete the field + `BoundingBox` model. No backfill.

3. **Type strictness → strict Pydantic `Region`, but `extra='allow'`. LOCKED.** Closes the "client sends anything, we persist it" gap at the region-save endpoint, while `extra='allow'` lets Track B/C evolve producer shapes (new attributes, embeddings) without a schema war. Best of both.

4. **Manual write path → route through the existing full-array `POST /region-annotations`. LOCKED (v1).** Consistent with the auto path; least rewrite of `BoundingBoxEditor`. A per-region upsert endpoint is a **later optimization** if full-array saves get heavy — noted, not now.

5. **`block_id` on the schema now → YES, include the optional field. LOCKED.** Null-safe, unwritten for now; locks the region→story contract so Lane 2's "a part points at the paragraph that discusses it" and the `/part` slash-insert build later without a schema change.

6. **Two auto detectors, one array → Track A guarantees shared shape + `detector` provenance; dedup/precedence is Track B's problem. LOCKED.** Track A's job is one shape; when Track B makes segmentation domain-aware and YOLO+Fashionpedia+vision overlap, Track B owns the precedence/merge rules.

7. **`parent_label` → drop it, canonicalize on `parent_id`. LOCKED.** The router already resolves `parent_id` server-side; the raw model string is redundant.

### Plus — v2 graph-ready additive fields (LOCKED into the schema)
Because the project is now two-sided (see strategy), the unified `Region` also carries (all additive, null-safe):
- `part: Optional[str]` — Fashionpedia apparel-part slot (distinct from coarse `category`).
- `attributes: List[str] = []` — Fashionpedia fine-grained attribute vocab (294).
- `embedding_id: Optional[str]` — pointer to the FashionCLIP taste-vector (vector stored out-of-row).
- `actor: str` — who created the mark: `auto | creator | audience` (so a one-tap audience signal and a creator annotation share one schema). **RESOLVED in v2 (Part 1b Q1): collapse to this single `actor` field; `source` dropped.** `detector` carries auto-provenance.

**Net unified `Region` (v2):**
```python
class Region(BaseModel):
    id: str
    actor: str = "auto"            # auto | creator | audience   (who marked it)
    detector: Optional[str] = None # yolo | fashionpedia | sam2 | vision  (auto provenance)
    label: str = ""                # catalog-critical
    category: str = "other"        # coarse vocab (catalog-critical)
    part: Optional[str] = None     # Fashionpedia apparel-part slot
    attributes: List[str] = []     # Fashionpedia fine attributes
    box: RegionBox                 # normalized 0–1, top-left
    polygon: Optional[List[List[float]]] = None
    confidence: Optional[float] = None
    material: str = ""             # catalog-critical
    description: str = ""
    depth: int = 0                 # 0 anchor · 1 fine
    parent_id: Optional[str] = None
    prioritised: bool = False      # catalog-critical
    weight: int = 0                # catalog-critical (summed iff prioritised)
    user_note: str = ""            # catalog-critical
    embedding_id: Optional[str] = None  # FashionCLIP taste-vector pointer
    block_id: Optional[str] = None      # region → story link (optional)
```
Six catalog keys preserved verbatim → `anatomy_catalog_service` keeps working unchanged.

---

## Part 2 — The 6 strategy forks (RESOLVED 2026-07-08)

**Adarsh's calls (LOCKED):**

| Fork | Decision | vs my rec |
|---|---|---|
| 1 — Sequencing | **True parallel** — creator + audience built together | (I'd recommended creator-first; Adarsh chose the more ambitious parallel path) |
| 2 — Track F official | **Yes** | matches |
| 3 — Video/reels | **Pull video forward** — reel-slicing is central, invest this cycle | (I'd recommended image-first; Adarsh wants video now) |
| 4 — Model depth | **Phased full-stack** (FashionCLIP → Fashionpedia → SAM2) | matches |
| 5 — Pitch framing | **Keep both balanced** (dual B2B + B2C headline) | (I'd leaned consumer-vision-led; Adarsh wants both) |
| 6 — Name taste graph | **Rasa** (desi) + **Palette** (English) locked; cooler upgrade candidates under review (see below) | Ruchi dropped (food-brand clash) |

**What this combination means (honest note):** parallel + video-forward + balanced-pitch is the **most ambitious and highest-surface-area** path — it maximizes the vision but front-loads the most build, the heaviest infra (GPU video serving early), and the widest message. It's a deliberate bet on scope over speed-to-demo. The tracks below are re-weighted accordingly: **Track F is now parallel (not "after A/C")**, and **video moves from Phase-later into active scope**. Guardrail: keep the image loop shippable on its own so video slippage can't sink the whole MVP.

Detailed framing of each fork (stakes/options/tradeoffs) is preserved below for the record.

---

Each: **what's at stake · the options · recommendation · what it changes downstream.** ★ = my original recommendation; the **LOCKED** line is Adarsh's actual call.

### Fork 1 — Emphasis & sequencing: who do we build for first?
**At stake:** how fast we get a *showable, credible* thing, and how much surface area we carry at once. The engine (parts → reading → taste-vector) is shared no matter what; this fork is about which *surface* we finish first.
- **A. Creator-first, audience-ready, brand-monetized ★** — finish the creator loop (image → Fashionpedia parts → felt reading → taste signature → grounded editorial piece), *design* A/C so the audience surface plugs in, monetize via brands once the graph has data. Fastest to the portfolio/resume demo; de-risks the engine before consumer polish.
- **B. Audience-first (B2C lead)** — build the "read this image deeper" consumer app first. Flashier, bigger reach story — but it *still* needs the same engine, so you pay the engine cost with less to show early, and consumer UX polish is expensive.
- **C. True parallel** — creator + audience together. Fastest to a two-sided story, but doubles the build surface and the risk while the engine is still unproven.
**Recommendation:** **A.** The creator demo is the credibility artifact *and* the engine test; audience + brand layer on the same spine without a rewrite.
**LOCKED → C (True parallel).** Build creator + audience together. Downstream: Track F runs in parallel with B/C/D (not after); Track D designs the creator surface *and* the stripped consumer variant together; the graph-ready schema (Track A-v2) must land first so both sides share it from day one.

### Fork 2 — Make Track F (B2C) official now?
**At stake:** whether the consumer/chain research becomes a first-class, tracked workstream or stays an idea.
- **A. Yes — make it official ★** — it's research-only and parallel-safe; formalizing it means it gets a findings doc + an umbrella checkbox and doesn't get lost. Costs nothing now.
- **B. Hold** — keep it as strategy prose until the creator engine is proven, to stay focused.
**Recommendation:** **A**, but *sequence its research after A/C findings* (it depends on the graph-ready schema + the reading engine). Official, not urgent.
**LOCKED → A (official) + parallel** (per Fork 1). Track F is now a first-class parallel track, not a follow-on. Still gated on Track A-v2's schema landing so it builds on the shared graph.

### Fork 3 — How far into video/reels this cycle?
**At stake:** the reel-slicing / "which part of a video is loved" capability is genuinely differentiated for B2C, but video (SAM2-video, streaming masks, replay signals) is the heaviest thing in the plan.
- **A. Image-first, video Phase-later ★** — scope video in Track F, build the image MVP now, add video when the image loop is proven. Keeps the MVP shippable.
- **B. Pull video forward** — treat reel-slicing as central to the consumer hook and invest now. Bigger wow, but heavy infra (GPU video serving) and it blocks the simpler image MVP.
**Recommendation:** **A.** Video is a Phase-2 multiplier, not the wedge. The image "read deeper" hook already delivers the "level up from social media" feeling at a fraction of the cost.
**LOCKED → B (Pull video forward).** Reel-slicing is treated as central this cycle. Downstream: model-plan Phase 4 (SAM2-video + replay signals) moves into active scope; Track F must produce a concrete video plan (GPU-video serving, cost/latency, replay-signal capture) now, not later. Guardrail retained: image loop stays independently shippable.

### Fork 4 — Model adoption depth (ties to Track B)
**At stake:** technical credibility vs deploy weight. Real fashion CV models read far stronger (resume/portfolio) than "a GPT wrapper," but they need GPU-ish serving.
- **A. Phased full-stack ★** — FashionCLIP now (light, no training, gives taste-vectors + better labels immediately), then Fashionpedia segmentation, then SAM2. Each phase earns its keep; ends with a genuinely credible stack.
- **B. Light first** — FashionCLIP labels + the current LLM only; defer the heavy segmenters. Ships faster, but the "domain-deep felt reading per part" — the whole differentiator — stays shallow until you add them anyway.
**Recommendation:** **A**, explicitly phased (FashionCLIP → Fashionpedia → SAM2). You get an early win (vectors) and a credible endpoint without a big-bang deploy.
**LOCKED → A (phased full-stack).** Track B builds the benchmark + deploy/cost/fallback plan around this staging. Note: with video pulled forward (Fork 3), SAM2 gets both its image *and* video roles budgeted together.

### Fork 5 — Which side leads the pitch (headline framing)?
**At stake:** the *story* you tell (investor / resume / portfolio / landing). One engine, but the headline shapes perception.
- **A. Consumer vision headline, brand-intelligence as proof ★** — lead with "a level up from social media / the taste-and-story layer," back it with the B2B taste-intelligence business as the monetization proof. Emotionally resonant *and* commercially credible.
- **B. B2B taste-intelligence headline** — lead with the brand/creator business (revenue-credible, defensible, resume-strong for an AI/data role), consumer as the reach/flywheel. Safer for investor/enterprise framing, less inspiring as a story.
- **C. Keep both balanced** — dual pitch; risks a diffuse "what is it" message.
**Recommendation:** **A** for a portfolio/landing/vision context; note that for a pure *investor/enterprise* deck, **B** may convert better. Pick per audience — but the landing/motive page leads with **A** (the motive narratives already do).
**LOCKED → C (keep both balanced).** Dual B2B+B2C headline. Downstream: `motive-narratives.md` keeps both the consumer manifesto *and* an equally-weighted brand/creator-intelligence cut — add a B2B-facing motive section so the two are balanced rather than consumer-led. Watch for message diffusion; keep one shared sentence on top ("the taste-and-story layer") so "both" doesn't read as "unclear."

### Fork 6 — Name the taste graph?
**At stake:** the taste graph (parts × felt-meaning × vectors) is becoming the center of gravity — the thing users own and brands buy. A name makes it a product object, not plumbing.
- **A. Yes, name it ★** — proposal: **Ruchi** (रुचि — taste / discernment / delight), fitting the Sanskrit family (Darshan, Aletheia*, Sūkṣma, Drishya, Sutradhar). The user's *Ruchi* = their taste graph/portfolio.
- **B. Not yet** — leave it unnamed until the app rebrand (Drishti vs Nazar) settles, to avoid naming sprawl.
**Recommendation:** **A** — "Ruchi" as a working name for the taste graph; cheap, on-theme, and gives the B2C "taste given back to you" surface a noun. Veto freely.
(*Aletheia is the one Greek name in an otherwise Sanskrit set — flagged earlier; still open.)
**LOCKED → Rasa (desi) + Palette (English)**, replacing Ruchi (dropped — clashes with the Ruchi food brand). **Upgrade candidates under active review** (Adarsh wants something less clichéd than Rasa / less flat than Palette), drawn from Kashmiri Śaiva aesthetics (Utpaladeva/Abhinavagupta) and phenomenology (Merleau-Ponty/Heidegger/Ihde):
- **Dhvani** (ध्वनि) — resonance / the *suggested* meaning beyond the literal (Ānandavardhana→Abhinavagupta). Maps precisely to a *felt-meaning* layer. Short, sonorous, uncommon as a brand. ★ top desi upgrade.
- **Pratibhā** (प्रतिभा) — the flash of aesthetic/creative intuition (Abhinavagupta's signature contribution). "Your Pratibha" = your eye's genius. Familiar as a name (± for market).
- **Camatkāra** (चमत्कार) — aesthetic *rapture/relish*, the flash of taste (Utpala ties it to vimarśa). Meaning-richest; 4 syllables → least market-practical.
- **Vimarśa** (विमर्श) — the reflective power that recognizes & relishes taste. Deep, distinctive; harder to spell/say.
- **Pratyabhijñā** (प्रत्यभिज्ञा) — *recognition* (Utpaladeva's core: instantaneous self-recognition of what's already yours). Too long as a name — but ideal as a **tagline** ("your taste, recognized").
- English/phenomenology: **Attunement** (Heidegger's Stimmung — how you're tuned to the world; accessible, elegant, taste-apt) · **Chiasm** (Merleau-Ponty — the intertwining of seer & seen; edgy, ownable, abstract) · **The Clearing** (Heidegger's Lichtung — where things come into appearance).
- **Ihde note:** his vocabulary (multistability, mediation, hermeneutic relation, amplification–reduction) is stronger as **positioning language** than as a name — Darshan is precisely a *hermeneutic-relation* technology (you read the world *through* it) with an *amplification* structure (it amplifies the felt-meaning the scroll reduces). Use for copy; not a product noun.

**Deeper tier (Adarsh: the above are also anthology clichés — go deeper; bring in Ānandavardhana):**

*Sanskrit poetics (Ānandavardhana / Abhinavagupta) — beyond dhvani:*
- **Vyañjanā** (व्यञ्जना) — the *third semantic power*, suggestion itself: the function that produces dhvani, beyond abhidhā (denotation) and lakṣaṇā (indication). Dhvani is the *result*; vyañjanā is the *engine*. Precise, technical, ownable.
- **Anuraṇana** (अनुरणन) — Abhinavagupta's metaphor for suggestion as the *after-resonance, the echo that lingers once the bell stops*. Gorgeous for a taste layer that keeps ringing. Uncommon.
- **Pratīyamāna** (प्रतीयमान) — "that which is *implied/suggested*," the meaning beyond the literal (vs vācya). Conceptually exact; 5 syllables → hard as a market name.

*Kashmiri Śaiva metaphysics (Utpaladeva) — beyond spanda/vimarśa:*
- **Saṃvit** (संविद्) — the integral *mirror-consciousness* in which every appearance arises. The graph = your saṃvit, the aware field that holds your images. Short, deep, very ownable. ★ strong.
- **Ābhāsa** (आभास) — the *shining-appearance / manifestation*; every image is an ābhāsa arising in saṃvit. The image *as* felt manifestation. Short, deep.
- **Sphurattā** (स्फुरत्ता) — the *luminous throb/scintillation* of awareness (deeper than spanda). The shimmer of noticing.
- **Unmeṣa** (उन्मेष) — the *opening/unfolding of the eye* (awareness flashing open). Evocative, ownable.

*Phenomenology — beyond flesh/chiasm/aletheia:*
- **Écart** (Merleau-Ponty) — the *divergence/gap* ("thickness of flesh") between seer and seen that *holds open* the space where perception happens. One sharp ownable word; the generative gap.
- **Institution / Stiftung** (Merleau-Ponty, from Husserl) — the *founding and sedimenting of meaning over time*. The single most conceptually-exact term for an *accruing* taste graph — though "institution" reads heavy in English.
- **Verweilen** (Heidegger) — *tarrying / lingering / the while*: the artwork gathers a "for-a-while," makes us *dwell*. Perfect meaning for "a level up from the scroll" — but German/hard.
- **Ihde as framing, not name:** *epistemology engine*, *visualism / visual hermeneutics*, *variational method* — Darshan is a **visual-hermeneutic engine** (reading meaning *through* the image). Positioning copy, not a noun.

**Current front-runners (deeper tier):** desi — **Saṃvit** (the aware mirror-field) or **Anuraṇana** (the lingering resonance); phenomenology — **Écart** (the generative gap) or **Institution/Stiftung** (the sediment of taste). Awaiting Adarsh's pick; Rasa/Palette remain the safe fallback.
Threads into app naming (Drishti vs Nazar) in `decisions-log.md`.

---

## Part 1b — Track A-v2's 5 questions: LOCKED (2026-07-08)

The v2 pass (findings @ `0687d15`) posed 5 new questions (the v1 seven stay locked, Part 1). Adarsh's calls:

1. **Actor collapse → YES, drop `source`. LOCKED.** One field `actor: auto|creator|audience`; `actor` subsumes `source`, keeping both invites illegal pairs, zero migration (`source` never shipped, legacy regions default `actor="auto"`). `detector` carries auto-provenance.

2. **Embedding store → sidecar Mongo `region_embeddings` collection NOW; external vector DB only when scale demands. LOCKED.** Standing up Qdrant/Pinecone for 77 regions is ops overhead with no payoff. `embedding_id` is the abstraction that lets you swap later without touching `Region` — start in-datastore, add Atlas Vector Search when retrieval latency/scale actually bites. Don't buy infra ahead of data.

3. **`part` vs `category` → keep SEPARATE. LOCKED.** `category` is the coarse, catalog-critical vocab `aggregate_categories` buckets on — must stay stable. `part` is the fine Fashionpedia slot. Merging conflates two granularities and perturbs the catalog. Two fields.

4. **Catalog bucket on `attributes` → NO, wait for the vector catalog; don't touch the frequency catalog. LOCKED.** 294-vocab attributes are high-cardinality; exact-match buckets fragment. They belong in FashionCLIP-space via similarity, not label counts. Keep the `(category, label)` catalog as-is. **→ FLAG for Track C:** attributes power vector retrieval there; this is strictly Track C's call to implement.

5. **`actor="audience"` write path → entirely Track F's. LOCKED.** Track A guarantees the null-safe field + schema; the audience-ingest endpoint plus its auth/rate-limit/abuse handling are Track F's. Clean boundary.

**Net:** the v2 `Region` schema in Part 1 (and `responses/track-A-datamodel.findings.md` §v2.2) is now fully locked — `source` field is removed in favour of `actor`; `part`/`attributes`/`embedding_id`/`block_id` all null-safe; FashionCLIP vectors live out-of-row in `region_embeddings` keyed by `embedding_id`.

---

## Part 3 — What's still blocking a build
- ~~Adarsh picks Forks 1–6~~ **DONE** (locked above). Track A's 7 also locked.
- ~~**Track A-v2 extension pass** must land first~~ **DONE** — findings @ `0687d15`, all 5 v2 questions locked (Part 1b). The graph-ready, two-sided `Region` schema is now the settled shared spine for creator + audience.
- Then B / C / D / F proceed **in parallel** (Fork 1). B budgets SAM2 for image **and** video (Forks 3+4); F produces the concrete video plan now (Fork 3).
- Umbrella GitHub issue created (still missing) with A–F checkboxes.
- Reconcile these locks into the main `decisions-log.md` once the other thread's tree is clean.
