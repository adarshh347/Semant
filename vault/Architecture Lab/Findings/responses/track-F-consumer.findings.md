# Track F — Consumer (B2C) taste layer & the creator→brand chain: findings

**Mode:** deep read + plan + web research. No app code changed.
**Lens (Purpose→Structure):** the other four tracks build the *creator's* close-reading engine. Track F asks: what does the **audience** do with it, and how does audience taste become the asset creators and brands pay for — **without asking a consumer to annotate**. The design rule (Adarsh, strategy §5): *the user does something that already feels good; the structure is extracted underneath.*
**Grounding:** line refs current as of `581093d`. Builds on the locked schema (`Region.actor=auto|creator|audience`, `embedding_id` sidecar — Track A), the feed-hook + one-tap fork (Track C §5, `depth="hook"`), the SAM2 async keyframe-video plan (Track B §5), and the locks in `pre-build-decisions.md` (B6 video spike-vs-full, C4 tap-gated + cache-per-image).
**Within locked context:** F is a first-class **parallel** track; **video/reels is in active scope** (Fork 3); `actor="audience"` write path (auth/rate-limit/abuse) is entirely F's; taste graph = **Anuraṇana**; the image hook stays independently shippable.

---

## 0. Headline (up front)

**The audience side is the *same engine, inverted*: where the creator authors a reading, the audience's low-friction reactions to that reading are the taste signal — captured as lightweight events, not Region rows.** Four load-bearing calls:

1. **Don't write Regions for audience taps.** A consumer tapping "the drape moved me" must **not** create a researcher-grade `Region`. Audience signal is a **lightweight event** (`taste_signals`) that *references* an existing `region_id`/`embedding_id` and aggregates into Anuraṇana. `actor="audience"` on a `Region` is reserved for the rare case an audience member marks a genuinely new spot. This keeps consumer friction ≈0 and keeps the creator's curated array clean. **(This is the main thing Track F asks of Track A — §7.)**
2. **The Aletheia-in-feed hook is the MVP and it's nearly free to serve.** Track C already locked it: `depth="hook"` render (1 lens + 1 fork), **tap-gated + cached-per-image** (C4) — compute once per image, reuse for every viewer. So the B2C hook is *one cached LLM call per image*, not per view. Independently shippable without any video work.
3. **The fork tap is the whole flywheel.** The Aletheia MCQ fork (`vision_service.py:594-631`, already generated) is the single best signal: it *feels like play, reads like data*. Each tap is a perceptual choice → a taste-vector nudge in Anuraṇana. It is simultaneously the consumer's delight and the creator/brand's data. One mechanism, both sides.
4. **Video is a signal *upgrade*, not a new product.** SAM2 keyframe-tracking (Track B) makes "which slice of a reel is loved" real — but the signal ladder (dwell/replay/tap) is *identical* to the image ladder, just time-indexed. So ship the **image hook now**, land a **video spike** (B6 rec), and the full async pipeline drops in behind the same `taste_signals` schema. Part-level "which region, which moment" is also a **cleaner** signal than the raw watch-time platforms use (watch-time is confounded by duration bias — web-grounded §5).

---

## 1. Signal ladder — low-friction taste capture (cheapest friction first)

The constraint: **capture sophisticated signal through interaction that costs the user ≈0.** Each rung is *more* signal for *slightly* more friction; the consumer app leans on rungs 1–3, the creator studio is rung 5.

| # | Signal | Friction | What's captured | Maps to | Worth the plumbing? |
|---|---|---|---|---|---|
| **1** | **Dwell** — time paused on an image / lingering on a region | **zero** (passive) | `post_id`, `region_id?` (if a region is under the pointer/zoom), dwell ms | weak vector nudge toward that region's `embedding_id` | **Yes, but debounce.** Standard implicit signal; noisy alone (duration bias — §5). Aggregate, never trust one dwell. |
| **2** | **Region tap / zoom** — tap or pinch-zoom a part | **near-zero** (already exploring) | `region_id`, `embedding_id`, tap/zoom | medium nudge toward that region's taste-vector | **Yes — the sweet spot.** A tap on *a specific part* is far cleaner than a whole-image like: it says *which* part. |
| **3** | **Aletheia fork** — tap one option on a "what pulls your eye?" MCQ | **near-zero** (feels like play) | the fork `prompt` + chosen `option` (+ the lens it maps to) | **strong** signal — a deliberate perceptual choice → lens/attribute preference | **Yes — the flywheel.** Reuses `vision_service.py:594-631`; the single highest signal-per-friction rung. |
| **4** | **Save-with-a-reason-lite** — save + tap ONE chip ("the drape / the mood / the colour") | **low** (one extra tap, optional) | `post_id`, reason-chip (maps to a category/attribute/lens) | strong, labeled signal | **Yes — optional.** A chip, never a text box. Skippable; saving alone still counts (rung 1–2). |
| **5** | **Deep annotation** — full pick→comment→remember (Track D loop) | **high** (researcher-grade) | full `Region` w/ `user_note`, `prioritised`, `weight` | the creator's authored taste | **Creators only.** This is the deep end; consumers never required here. |

**Design rules:**
- **The consumer never leaves the feeling of consuming.** Rungs 1–3 happen *inside* looking at a beautiful reading. No forms, no "annotate this."
- **Everything aggregates; nothing single-shot is trusted.** One dwell is noise; 40 dwells + 5 taps + 3 forks on "drape" across a session is a taste. Signal → vector nudges in Anuraṇana, thresholded.
- **Signal maps to the *same* taste space as creator marks** — because a tap references a real `region_id`/`embedding_id` (FashionCLIP vector), audience taste and creator taste are *comparable in one space*. That comparability is the entire two-sided premise (§3).
- **Cost discipline:** rungs 1–2 are client-side events batched and POSTed periodically (not per-event); rung 3's fork is already computed (cached hook); rung 4 is one field. No per-signal LLM call.

---

## 2. Aletheia-in-feed — the B2C MVP spec

**The hook:** a user pauses on an image (theirs, a creator's, a feed) → taps **"read this deeper"** → a *short, beautiful* reading appears + one perceptual fork. It rewards the pause instead of punishing it with the next scroll — literally the "level up from social media."

**Spec (grounded in what already exists):**
- **Render:** Track C's `depth="hook"` — **1–2 sentence distilled reading + one fork** (not the full lens set). Same engine, same `ALETHEIA_PROMPT`/`brainstorm_image` (`vision_service.py:269-326`), just the stripped render. Fashion-literate lens (silhouette/drape/mood), not the generic 3.
- **Serving (locked C4):** **tap-gated + cache-per-image.** The hook is computed **once per image** on first tap and cached (`local_context.aletheia` already stores the reading, `posts.py:386-391` — the hook is a stored derivative). Every subsequent viewer of that image reuses the cache → **B2C cost ≈ one LLM call per image, ever**, regardless of audience size. This is what makes the hook shippable at consumer scale.
- **Surface (shared engine, different skin):** the hook is the **feed/pause** surface of the *same* reading strip Track D puts under the creator's Visual pane (Track D §4). Creator sees the deep strip in the studio; audience sees the one-lens hook in the feed. Track D keeps the deep surface clean enough that this lite variant **falls out of it** (D7 lock — extract lite later, don't build F's UI inside D).
- **The fork = the capture (rung 3).** The fork rendered with the hook is *the* taste signal. Tap → `taste_signals` event → Anuraṇana. The consumer thinks they're choosing how to see; the graph learns their eye.
- **Independently shippable:** this MVP needs **no video, no Fashionpedia, no SAM2** — just Track C's hook render + the `taste_signals` write path (§7). It's the guardrail deliverable: the image hook ships alone.

**Where it lives relative to the creator studio:** one engine (Aletheia/Track C), two surfaces — `/studio` (deep, creator) and the feed hook (lite, audience). Both write to Anuraṇana; the creator's writes are authored Regions, the audience's are lightweight signals. Neither surface forks the engine.

---

## 3. The taste graph (Anuraṇana) as the bridge

**One schema, three actors** — the structural claim that makes two-sided coherent:

```
   AUDIENCE signal        CREATOR annotation        BRAND query
   (tap/dwell/fork)       (Region + user_note)      (taste vector to match)
        │                        │                        │
   taste_signals event      Region row               vector search
        │  refs region_id/embedding_id                    │
        ▼                        ▼                        ▼
   ┌──────────────────────────────────────────────────────────┐
   │        ANURAṆANA — the taste graph (region_embeddings +   │
   │        taste_signals, joined on embedding_id)             │
   │   part × felt-meaning × FashionCLIP vector × actor        │
   └──────────────────────────────────────────────────────────┘
```

- **Shared vector space (Track A/B/C).** A creator's `user_note` on a drape region and an audience member's fork-tap on the same drape both resolve to the **same FashionCLIP `embedding_id`** — so they're comparable by similarity. This is why audience taste can *match* creator taste (§4): they live in one space, distinguished only by `actor`.
- **`actor` is the only thing that differs.** `auto` = detected geometry; `creator` = authored felt-meaning; `audience` = low-friction reaction. Same object family, one graph — exactly Track A's collapse-to-`actor` decision paying off.
- **The audience "taste portfolio" (why a user values it — *taste given back, not harvested*):** the signals a consumer generates accrue into **their own** readable Anuraṇana — "your eye leans toward asymmetric drape, matte texture, muted palettes; here's the thread across everything you paused on." It's a *mirror of their taste*, returned to them as meaning, not spent invisibly on an ad model. That reciprocity is the trust differentiator (§6) and the reason a consumer opts in at all.
- **Not a persona roll-up.** Audience signal does **not** flow into the creator-persona (`persona_service.add_local_context` etc.) — that's the *creator's* voice. Audience taste is its own portfolio + an aggregate the brand layer queries. Keep them separate stores, one schema.

---

## 4. The creator→brand chain + monetization

**The chain (strategy §2), made concrete on the graph:**
```
 AUDIENCE  ──taste signal──▶  ANURAṆANA  ──enriches──▶  CREATOR taste-signature
 (free)                       (the graph)                (portfolio / studio)
                                   │                          │
                                   └────── BRAND intelligence ─┘
                                     (match creators↔campaigns by aesthetic taste,
                                      trend-with-reason, grounded copy)
```

**What Darshan uniquely sells that like-based platforms cannot:** the **part-level *why*.** Incumbents match creators to brands by follower count + coarse category + engagement. Darshan matches by **aesthetic taste as a vector** — "find creators whose *eye* (drape-forward, muted, editorial) fits this campaign," grounded in *why* each part moves them, not how many followers they have. Web-grounded: the market already pays for automated brand↔creator matchmaking, fashion & lifestyle is its largest segment (32%), and niche creators convert ~3.5× macro — but nobody matches on *part-level felt-meaning*, because that data can't be scraped from likes. It has to be *built*, part by part — which is the moat.

**The three monetization tiers:**

| Tier | Who | What they get | Why they pay |
|---|---|---|---|
| **B2C — free** | audience | Aletheia-in-feed "read deeper"; their own taste portfolio (given back) | free is the flywheel — every read enriches the graph; premium personal archive optional later |
| **B2B-lite — creator sub** | creators | the authoring studio (Track D deep pane), **taste-signature** (FashionCLIP portrait of their eye), grounded-copy generation (Track C RAG), portfolio export | it's their creative instrument *and* their hire-worthy portfolio object |
| **B2B — brand intelligence** | brands / agencies | **creator↔campaign match by aesthetic taste**, trend-with-reason (which parts/attributes are rising *and why*), grounded campaign copy | the real revenue + the resume-credible product; priced per seat / per match / per report |

**Sequencing note:** the brand tier needs the graph to *have data first* — so it layers on after audiences + creators have fed Anuraṇana. B2C-free is the data engine; brand-intelligence is the monetization endpoint. (Consistent with the locked "true parallel build, but brand layer needs graph data" reasoning.)

---

## 5. Video / reels — the SAM2 plan + cost/latency (B6: plan both)

**What it makes possible:** "which *slice* of a reel is loved" — not "this video got 10k views" but "the 3-second moment where the coat flares, the collar turn at 0:12." Part-level + moment-level taste. Web-grounded: replay/rewatch/dwell are the industry-standard implicit signals, but raw **watch-time is confounded by duration bias**; Darshan's **region×moment** signal is *cleaner* — it says which part of which frame, not just "watched long."

**The pipeline (Track B §5, carried forward):**
```
reel ─▶ decode ─▶ sample KEYFRAMES (not every frame)
                        │
              SAM2 prompt on a keyframe (tap or auto-anchor)
                        │  propagate masks forward (memory-bounded tracking)
                        ▼
        tracked region across frames  ◀── attach replay/dwell/tap signal
                        │                    to the REGION, not the whole frame
                        ▼
        taste_signals (time-indexed) ─▶ Anuraṇana (same schema as image)
```

**Cost/latency reality (web-grounded, Track B):** SAM2 ~44 FPS streaming for a simple single object, but **~13 FPS (Large, A40)** and **1.3–1.5 FPS with many prompts**; ~5.5 GB VRAM. → **video is offline/async, GPU-served, keyframe-sampled — never in-request.** GPU-video serving is the heaviest infra in the whole initiative.

**B6 — plan for both (spike now, full pipeline behind it):**
- **Spike this cycle (recommended):** prove **one reel → keyframe → SAM2-track one region → capture one replay signal → land it in `taste_signals`**. De-risks the hard part (tracking + signal attribution) on a hosted SAM2-video endpoint (Replicate/Modal — no fixed GPU bill), *without* building the full async worker. Honors "pull video forward" (Fork 3) while keeping the image hook independently shippable (guardrail).
- **Full async pipeline (immediately after / if Adarsh wants it now):** a background worker (queue → GPU endpoint → mask store → signal aggregation), reel upload/ingest, the replay-signal client instrumentation, and video serving. Heavier; competes with the image MVP for time. Same `taste_signals` schema, so the spike's data model is the full pipeline's data model — no rework.
- **The boundary that protects the MVP:** the **image hook + image signal ladder ship and stand alone**. Video is additive: same hook, same forks, same graph, just time-indexed. If video slips, B2C still works.

---

## 6. Privacy / trust posture — "taste given back, not harvested"

This is the *differentiating promise* vs the platforms Darshan is "a level up" from — and it has to be structural, not a tagline.

- **The data model makes it real:** audience signal accrues into **the user's own taste portfolio** (readable, exportable, theirs) — the *same* Anuraṇana object is what they see. There is no separate hidden profile sold to advertisers; the aggregate the brand tier buys is **taste-pattern intelligence, not identified individuals** (brands match *creators* they can contract, and query *anonymized aggregate* taste trends — never "user X likes Y, here's their ID").
- **User-facing promises:** (1) *your taste is shown back to you* (the portfolio is the product, not a byproduct); (2) *signals are aggregatable and deletable* — `taste_signals` keyed by user/session, a clear "clear my taste" that actually empties the store; (3) *no cross-site tracking, no selling identified behavior*; (4) *opt-in enrichment* — dwell/replay capture is on-by-consent, and the value (better readings, your portfolio) is visible in return.
- **`actor="audience"` write path is F's to harden (locked):** authn (session or account), **rate-limiting** (batch client events, cap per session — prevents signal-stuffing), **abuse/bot resistance** (a flood of fake taps must not poison the graph → thresholded aggregation, anomaly caps, no single-event trust). This is the security surface Track A explicitly left to F.
- **Anonymized-by-default:** consumer signal doesn't require a full account to *feel good* (session-scoped taste works); an account unlocks the *persistent portfolio*. Friction stays ≈0; identity is the upsell, not the toll.

---

## 7. What Track F demands of Track A / C (the integration asks)

**Of Track A (schema/storage):**
1. **A `taste_signals` store — the one genuinely new thing.** Track A gave `actor="audience"` on `Region`, but audience taps should **not** mint Regions. Propose a lightweight sidecar collection: `taste_signals { id, user_or_session, post_id, region_id?, embedding_id?, signal_type: dwell|tap|zoom|fork|save_reason|replay, value, frame_ts?, created_at }`. It references the region/vector, aggregates into Anuraṇana, and never bloats `region_annotations`. **Confirm this lives as its own collection** (my rec), reserving `actor="audience"` Region rows for the rare new-mark case. *(This is the primary A-facing ask.)*
2. **Deletability / keying** — `taste_signals` keyed so "clear my taste" is a real delete (privacy §6).
3. **Video signals reuse the same schema** with `frame_ts` — no new model for video.

**Of Track C (engine):**
1. **The `depth="hook"` render** (1 lens + 1 fork) — already specced in Track C §5; F consumes it. Confirm the hook is a **stored, cached derivative per image** (C4), not recomputed per viewer.
2. **The fork→signal mapping** — each fork option maps to a lens/attribute so a tap is a *typed* signal, not opaque. Track C owns the fork; F owns writing the resulting signal.
3. **Reading the audience portfolio** — the same RAG/aggregation Track C designed over Anuraṇana, read back to the consumer as "your eye." Own-history scope (C3 lock) fits perfectly.

**Of Track B (video):** the SAM2 keyframe-track endpoint (§5) — F consumes its tracked regions and attaches signals.

---

## Questions for Adarsh

1. **`taste_signals` as a separate store (§7.1).** Confirm audience taps become **lightweight events in their own collection** (referencing `region_id`/`embedding_id`), **not** full `Region` rows — reserving `actor="audience"` Regions for the rare audience-creates-a-new-mark case. This is the core F↔A data decision. I strongly recommend the separate store.
2. **Video: spike vs full pipeline this cycle (B6).** My rec: **spike now** (one reel → SAM2-track → one replay signal, hosted endpoint), full async worker immediately after — honors "video forward" while keeping the image hook shippable. Or commit the **full async video pipeline** this cycle (heavier, competes with the image MVP). Your call.
3. **Account gate for the portfolio.** Session-scoped taste (no account) keeps friction ≈0 but the persistent **taste portfolio** needs identity. OK that anonymous/session users get the hook + forks, and an account is the upsell that unlocks the saved portfolio? (My rec — identity as upsell, not toll.)
4. **Signal capture consent default.** Dwell/replay instrumentation: **on-by-consent** (a clear opt-in with visible value) vs on-by-default-with-opt-out. Given the "taste given back, not harvested" promise, I lean **explicit opt-in** — slightly less data, much stronger trust story. Confirm the posture.
5. **Which signals ship in the first B2C cut?** I recommend rungs **2–3 (region tap + Aletheia fork)** as the MVP — highest signal-per-friction, both nearly free to serve — and defer dwell (rung 1, noisy) + save-reason (rung 4) to a fast-follow. Agree, or include dwell from day one?
6. **Brand-tier data boundary.** Confirm brands query **anonymized aggregate taste trends + match to contractable *creators*** — never identified consumer profiles. This is the privacy line that has to hold for the whole "level up, not harvest" thesis; I want it explicit before any brand-facing surface.
7. **Is the audience portfolio its own object, separate from the creator persona (§3)?** I recommend **yes** — audience taste ≠ creator voice; they share the schema but not the store (audience signal must not leak into `persona_service`). Confirm the separation.

*Research + plan only — no app code touched. The audience side is the same engine inverted: the creator's reading is the consumer's delight, and the consumer's low-friction reaction is the creator/brand's asset — all in one taste space (Anuraṇana) distinguished only by `actor`. The image hook ships alone; video is an additive signal upgrade behind the same schema. The one genuinely new build surface is the `taste_signals` store + its hardened `actor="audience"` write path. Sources below.*

---

### Sources
- [Influencer Marketing Platform Market (Grand View Research)](https://www.grandviewresearch.com/industry-analysis/influencer-marketing-platform-market) — ~$34B 2025; fashion & lifestyle largest segment (32%); automated brand↔creator matchmaking a named innovation driver; search & discovery 33.9%
- [Influencer Marketing Platform Market (Fortune Business Insights)](https://www.fortunebusinessinsights.com/influencer-marketing-platform-market-108880) · [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/influencer-marketing-market) — market-size corroboration
- [Relative Advantage Debiasing for Watch-Time Prediction (arXiv 2508.11086)](https://arxiv.org/pdf/2508.11086) — watch-time is confounded by duration bias (why part×moment signal is cleaner)
- [Affect & prediction in short-video recommendation — TikTok's missing half-second (Sage, 2025)](https://journals.sagepub.com/doi/10.1177/14614448251385086) — affect inferred from micro-temporal behaviors (dwell, pauses, replays)
- [User Immersion-aware Short Video Recommendation (ACM TOIS)](https://dl.acm.org/doi/10.1145/3748303) — dwell/immersion as implicit preference signal
- [SAM 2 (arXiv 2408.00714)](https://arxiv.org/html/2408.00714v2) — promptable video segmentation w/ memory (carried from Track B); cost/latency per Track B §5
