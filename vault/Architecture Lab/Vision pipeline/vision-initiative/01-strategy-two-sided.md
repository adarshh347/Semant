# Darshan strategy v2 — the two-sided taste-and-story layer

**Status:** strategy update / direction proposal. Research + planning only — no app code.
**Extends:** `track-E-purpose.findings.md` (fashion wedge) + `responses/fashion-market-research.md` (market + open-source stack). This doc absorbs Adarsh's July 8 direction: (1) each aspect needs a *concrete* plan, not a slogan; (2) the project is now explicitly **B2B *and* B2C**; (3) the positioning is **"A level up from social media" — a taste-and-story layer** over the Instagram/TikTok/YouTube-dominated culture, for **both creators and audience**.
**Companion docs written this pass:** `model-integration-plan.md` (the concrete model stack), `motive-narratives.md` (landing/motive copy), `track-F-consumer.prompt.md` (the new B2C track).

---

## 0. The one-paragraph thesis (sharpened)

Social platforms made fashion and entertainment **infinitely creatable and consumable** — and in doing so flattened artforms into dopamine food scrolled past. Darshan is **the layer that treats that culture as artform again**: it reads an image (or a reel) *part by part*, says *why it works and how it feels*, and accrues that into a **taste-and-story graph** that is (a) a creative instrument for the people who make fashion/entertainment, and (b) a richer, more intelligent way to *engage* for the people who love it. The same engine serves two sides — **creators author with it, audiences read and express taste through it** — and the two sides feed each other. Nobody else builds this: incumbents answer *"what is it"* (tagging) and *"what's trending"* (forecasting); Darshan answers **"why does this move me, and what's my story."**

---

## 1. Why the project became two-sided (and why that's a feature, not scope-creep)

Track E correctly narrowed the *creator* wedge to fashion. Adarsh's new input adds the missing half: the **audience**. This isn't drift — it's the natural shape of the domain, because in fashion/entertainment **taste is the product on both sides**:

- The **creator** needs to *articulate* taste (moodboard-with-reasoning, grounded copy, a signature).
- The **audience** already *expresses* taste constantly (saves, dwell, replays) but on today's platforms that expression is **thrown away as a like** — reduced to a number that feeds an ad model, never returned to the user as meaning.

Darshan's core act — *structured felt-meaning per part* — is the one mechanism that serves both: it gives creators a language to write in, and gives audiences a way to **see more deeply and have their taste taken seriously**. The bridge between them is a **taste graph** (§4), which is exactly what the emerging "taste-as-a-vector / taste-score for users, creators and brands" thesis is circling — but which no one has grounded in *part-level felt-meaning* rather than coarse behavioural history.

**The strategic caution (kept honest):** two-sided is powerful but doubles surface area. §7 proposes we *build creator-first, design audience-ready* — the B2C surface reuses the same engine and can lag, but the data spine (Track A) and the reading engine (Track C) must be built so the audience side plugs in without a rewrite.

---

## 2. The value chain: user → influencer → brand (the flywheel)

Adarsh's "user–influencer–marketing/ad/fashion-company chain" is the monetization spine. Made concrete:

```
  AUDIENCE (B2C)                CREATORS (B2B-lite)            BRANDS / AGENCIES (B2B)
  express taste, low-friction   author with taste,             buy taste + story intelligence
  (tap, dwell, "read deeper")   build a signature/portfolio    (creator-fit, trend-with-reason,
        │                              │                         grounded campaign copy)
        │  taste signal                │  authored readings        ▲
        ▼                              ▼                           │
  ┌──────────────────────────────────────────────────────────────┴───────┐
  │           THE TASTE-AND-STORY GRAPH  (parts × felt-meaning × vectors)  │
  │  every read/annotation/pick, from either side, accrues here           │
  └───────────────────────────────────────────────────────────────────────┘
```

The flywheel: audiences reading deeply produce **fine-grained taste signal** → that signal makes creators' taste-signatures and the trend-with-reason layer **richer than any like-based dataset** → creators produce grounded, resonant work → brands pay for the intelligence *and* for matching creators to campaigns by **aesthetic taste, not just follower count** (the market already pays for this — Vamp's CAST aesthetic-match, Linqia/CreatorIQ/Upfluence affinity-match; niche creators convert 3.5× macro). More resonant work pulls more audience engagement → more signal.

**Why this is defensible:** the graph is built from *why*, part by part — a data asset that cannot be reconstructed from scraping likes. It compounds. That is the moat Track E asked for, now with a business shape.

**Monetization, roughly (for Adarsh to weigh, §8):**
- **B2C:** free "read deeper" hook (Aletheia-in-feed), premium taste-portfolio / personal archive.
- **B2B-lite (creators):** subscription for the authoring studio, taste-signature, grounded-copy generation, portfolio export.
- **B2B (brands/agencies):** the intelligence layer — trend-with-reason, creator-taste matching, grounded campaign copy. This is where the real revenue and the resume/portfolio credibility live.

---

## 3. The taste-and-story layer, defined concretely

Adarsh asked: *what comprises it, how it benefits fashion creatives, what new factor it brings.* Precise answer.

### 3a. What it is made of (four accruing objects)
1. **Parts** — a Fashionpedia-grade decomposition of an image/frame into meaningful regions (garment + 19 apparel parts + 294 attributes + material; plus arbitrary regions via SAM2 for drape/texture/atmosphere). *Track A schema + Track B models.*
2. **Felt-reading** — per-part phenomenological meaning ("the lapel's severity vs. the drape's give"): fashion-literate Aletheia lenses, not generic ones. *Track C.*
3. **Taste-vector** — a FashionCLIP embedding per part/image, so taste is a **queryable vector space**, not just label counts. This is the upgrade from today's frequency-aggregation catalog. *Track C + model plan.*
4. **Story** — the authored/generated prose grounded in 1–3, with `origin` provenance. *Sutradhar slash-AI, already locked.*

The **catalog/persona** (today `anatomy_catalog_service`) becomes the graph that indexes all four across images and people.

### 3b. How it benefits fashion creatives (the three jobs, now concrete)
- **Moodboard-with-reasoning** → kills moodboard drift: references annotated part-by-part with felt reasons cohere into a *brief/story with a through-line*, not an archive. (The #1 documented creative-direction pain.)
- **Grounded editorial/PR copy** → `/draft`, `/part`, `/lens` write lookbook/trend/PR copy citing *this* garment's real parts in *your* accruing voice — beating generic detached AI captions (the "most sought-after but detached" gap).
- **A taste signature / portfolio artifact** → the FashionCLIP-backed "portrait of your eye": a designer's identity, a student's story-engine (fashion education grades exactly this), a hire-worthy portfolio object.

### 3c. The genuinely new factor (the sentence that isn't a slogan)
**Every existing tool turns an image into a *label* (tagging), a *number* (aesthetic score / like), or a *forecast* (trend). Darshan turns it into *articulated felt-meaning that is simultaneously writable (story) and queryable (taste-vector)*.** That triple — meaning + prose + vector, grounded at the *part* level — exists nowhere together. It is what lets the same object serve a creator's pen, an audience's eye, and a brand's targeting.

---

## 4. The taste graph (the bridge object)

The graph is the thing that makes two-sided coherent. Structurally it is the existing catalog, upgraded on three axes:

| Axis | Today (`anatomy_catalog_service`) | v2 (this strategy) |
|---|---|---|
| Unit | `(category, label)` buckets, frequency + intensity | Fashionpedia `(category, part, attributes[], material)` + a **FashionCLIP vector** per region |
| Whose | one curator's `region_annotations` | multi-party: audience taps, creator annotations, brand queries — same schema, `source`/actor tag |
| Query | LLM "portrait" paragraph | vector similarity (find images/creators/audiences by taste), RAG for grounded writing, taste-match scores |

This is where the "taste score for users, creators, and brands" concept lands — but grounded in *part-level felt-meaning*, which is the differentiator. **Track A must not preclude this** (its `Region` schema already has room; add an optional `embedding` ref and an `actor`/`source` distinction — see §6/Track A addendum).

---

## 5. The B2C surface & low-friction taste capture (the hard constraint)

Adarsh's key insight: *users must not be made to do researcher-grade annotation — that's good for a corpus, bad for a consumer.* So the audience side captures **sophisticated signal through low-friction interaction**. The design rule: **the user does something that already feels good; the structure is extracted underneath.**

Signal ladder, cheapest-friction first:
1. **Implicit / zero-effort** — dwell time per image, which regions they zoom/tap, which *slices of a reel* they replay or rewatch, scroll-back. (Dwell + replay is the industry-standard implicit taste signal.) SAM2 makes "which part of which frame" technically real (§model-plan).
2. **One-tap forks** — Aletheia already asks perceptual MCQs ("what pulls your eye?"); each tap is a *taste fork*, not a survey. This is the single best mechanism we already have — it feels like play, reads like data. (`vision_service.py:594-631` already generates these.)
3. **Save-with-a-reason lite** — saving is universal; offer an *optional* one-tap reason ("the drape / the mood / the colour") — a chip, not a text box.
4. **Deep (opt-in, creators)** — full part annotation + written felt-meaning. Only power users / creators go here.

**The consumer hook is Aletheia-in-feed:** "read this image deeper." A user paused on an image gets a short, beautiful reading + a fork or two. It rewards the pause instead of punishing it with the next dopamine hit — literally the "level up from social media." Every tap enriches the graph.

**The reel/video extension** (Adarsh's "what reels are sliced off, what parts of videos are liked"): this needs a *video* capability (SAM2 video + moment/segment signals). It is real but heavier; §7 sequences it as a **later phase**, and Track F scopes it explicitly so it doesn't bloat the image-first MVP.

---

## 6. Track refurnishing — what changes, per track

Concrete deltas. Each track's prompt gets an addendum pointing here + to `model-integration-plan.md`.

| Track | Was | Now (delta) |
|---|---|---|
| **A — data model** | unify two region systems into one `Region` | **+ make the schema graph-ready & two-sided:** optional `embedding` (FashionCLIP ref), `attributes[]` (Fashionpedia), `actor`/`source` distinction (curator vs audience vs auto) so audience taps and creator notes share one shape. Still merge-first; these are additive fields. |
| **B — segmentation** | domain-aware parts beyond COCO | **+ adopt the concrete stack:** Fashionpedia ontology + Attribute-Mask-RCNN (or DeepFashion2 seg) as the fashion part-model; SAM2 for arbitrary regions (drape/texture/atmosphere) **and the video/reel path**; FashionCLIP as the semantic labeler + vectorizer. See model plan. This is the biggest technical upgrade. |
| **C — Aletheia** | context-triggered lenses feeding the writer | **+ taste-vector + RAG:** FashionCLIP embeddings become the taste vector; RAG over the taste graph grounds the writer in *this image + this person's history*. Lenses become fashion-literate (silhouette, drape, era/reference, styling logic, mood/story). Also produces the **consumer-facing short reading** (the feed hook), not only the deep creator reading. |
| **D — frontend (creator)** | non-messy reveal, pick→comment→remember | Unchanged in intent, **more load-bearing:** Fashionpedia yields *many* parts/attributes, so progressive category-filtered reveal is essential. Add: the surface must render both the *deep* (creator) and be the design source for the *lite* (audience) interactions. |
| **E — purpose** | fashion creative wedge | **Confirmed + widened to two-sided:** creator wedge stays the tip; audience layer + brand chain are the platform. Positioning line = "the taste-and-story layer / a level up from social media." |
| **F — consumer (NEW)** | — | **B2C surface, low-friction taste capture, the creator→brand chain, and the video/reel path.** New prompt written (`track-F-consumer.prompt.md`). Research-only like the rest. |

**Sequencing unchanged at the core:** E → A (spine) → B/C/D in parallel → integrate. **F depends on A + C** (needs the graph-ready schema and the reading engine) and should be researched *after* A/C findings land, or in parallel as pure research. The video/reel sub-part of F is explicitly a later build phase.

---

> **LOCKED 2026-07-08 (Adarsh, `decisions-darshan.md`):** the posture below was my *recommendation* (creator-first). Adarsh chose the more ambitious path — **true parallel** (creator + audience together), **video pulled forward** (reel-slicing central this cycle), **phased full-stack models**, **balanced B2B+B2C pitch**. So: Track A-v2 lands first as the shared spine, then **B/C/D/F run in parallel**, video is in active scope, and the guardrail below (keep the image loop independently shippable) becomes essential rather than optional. §7 kept for the reasoning.

## 7. Build posture — recommended (superseded by the locked parallel path above)

1. **Prove the creator loop first** (Track E's demo): one fashion image → Fashionpedia-grade parts → felt reading per part → taste signature → grounded editorial piece. This is the portfolio/resume artifact and validates the whole engine.
2. **Design the audience surface against the same engine** from day one (Track A schema + Track C reading must be audience-plug-ready). Ship Aletheia-in-feed + one-tap forks as the B2C MVP once the engine is real.
3. **Layer the brand intelligence** (taste-match, trend-with-reason, grounded campaign copy) on the accrued graph — this is the revenue + the most impressive B2B story, and it needs the graph to have data first.
4. **Video/reel** is Phase-later: SAM2-video + replay signals. Real, credible, heavy — scope in Track F, don't let it block the image MVP.

This ordering means **no track has to be thrown away** to add the audience: A and C are built graph-ready now; F consumes them later.

---

## 8. Open decisions for Adarsh (the genuinely-his forks)

1. **Emphasis & sequence — creator-first vs audience-first vs parallel?** I recommend **creator-first, audience-ready, brand-monetized** (§7): it yields the portfolio demo fastest and de-risks the engine before adding B2C surface. Confirm, or do you want the consumer app to lead (bigger, flashier, but needs the engine anyway)?
2. **Add Track F now?** I've drafted it. Research-only, parallel-safe. OK to make it official (and open its umbrella checkbox)?
3. **How far into video/reel this cycle?** I recommend scoping it in Track F but **building image-first**; video is Phase-later. Agree, or is the reel-slicing central enough to pull forward?
4. **Model adoption depth (ties to Track B).** Adopt the full stack (Fashionpedia model + SAM2 + FashionCLIP) — heavier deploy, real credibility — vs a lighter "FashionCLIP-labels + LLM" path first? I lean full-stack for the resume/credibility payoff, phased.
5. **B2B vs B2C as the pitch you lead with** (resume/investor/portfolio framing). The engine is one; the *story you tell* can foreground the consumer "level up from social media" vision or the brand "taste intelligence" business. Which is the headline?
6. **Taste-graph as a named product object?** The graph (§4) is becoming the center of gravity. Worth naming it (it's the thing brands buy and users own)? Ties to the Darshan/Aletheia naming still open in `decisions-log.md`.

*Grounding: all code refs verified against `feat/frontend` (Track A findings @ `77a145a`). Market/model claims sourced in `fashion-market-research.md` + this pass's searches (taste-as-vector, SAM2 video, influencer-intelligence market, Fashionpedia model availability) — URLs in the session log.*
