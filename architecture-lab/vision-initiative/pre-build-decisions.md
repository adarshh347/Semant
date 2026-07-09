# Pre-build decision sheet — consolidated open questions + suggested answers

**Purpose:** one place to greenlight the build. Every open question from the closed research tracks (A done, B, C, D) with a **suggested answer**. Track F's questions fold in when it lands.
**Legend:** **[confirm]** = safe technical default, the track's own recommendation, low risk to accept · **[judgment]** = genuinely your call, trade-off worth a beat.
Mark each ✅ (accept) or ✏️ (override), then it's a build-ready contract.

---

## Track B — segmentation / model stack

1. **GPU serving path** — **✅ SETTLED → Serverless-first** (Replicate / Modal / Runpod, pay-per-call). Decided by hardware reality, not preference: neither the 4GB GPU nor the M4 (Apple MPS broken for SAM2) can serve the heavy models; AWS free tier is CPU-only. See `infra-hardware-plan.md`. Self-host never; AWS credits for CPU deploy + a capped experiment budget.
2. **Fashion segmenter** — **[confirm]** → **Fashionformer first (SOTA seg+attr), Attribute-Mask-RCNN as simpler-to-serve fallback, benchmark both on real Drishya posts.** Don't lock without the bench. ✅
3. **Non-fashion domains this cycle** — **[judgment]** → **SAM2 + LLM naming only** for architecture/photography; no dedicated models until fashion is proven. One deep domain first. (Consistent with the locked fashion wedge.) ✅ suggested.
4. **Dedup/precedence** — **[confirm]** → **Fashionpedia > SAM2(tap) > YOLO** for garments; keep overlapping detections only if IoU < τ; `detector` records provenance. Lives in Track B (per Track A Q6). ✅
5. **SAM2 laziness** — **[confirm]** → **On-demand (tap / "reveal more"), never dense-on-upload.** The main cost lever; also shapes Track D's reveal UX. ✅
6. **Video scope this cycle** — **[judgment]** → **Ship the image loop + a video *spike*** (prove keyframe→SAM2-track + one replay signal on a single reel) **this cycle; full async video worker immediately after.** This honors your "pull video forward" lock (Fork 3) — the spike de-risks now — while keeping the guardrail that the image loop stays independently shippable. *If you want the full async pipeline built this cycle, that's also consistent with Fork 3, just heavier and it competes with the image MVP for time.* **← your call: spike (rec) vs full pipeline now.**
7. **Atmosphere is image-global** — **[confirm]** → **Yes.** Mood/atmosphere stays an Aletheia image-level reading, not a boxed region. Keeps the Visual pane clean. ✅

## Track C — Aletheia / taste-vector / RAG

1. **Lens registry — config vs generated** — **[confirm]** → **Fixed domain→lens registry, LLM instantiates it** (legible, stable, UI-labelable). Free-invention is more surprising but breaks hover-links. ✅
2. **Personalization strength** — **✅ SETTLED → Prior + wildcard, data-gated.** Persona's recurring lenses bias lens-selection, one wildcard slot always ignores history (echo-chamber guardrail). **Refinement (from the build):** scale the prior's strength by accrued-data volume — cold-start ≈ 0 (so it never biases on today's thin corpus), ramping as the persona fills. Builds the mechanism once; it self-activates as taste accrues. Subsumes the "no prior yet" option's honesty concern without a second pass.
3. **Retrieval scope** — **✅ SETTLED → Own history ONLY** (revised from "own-first + opt-in"). The Track C build surfaced the concrete cost: cross-curator retrieval would inject another person's intimate `user_note` into your writing prompt — a direct violation of "taste given back, not harvested," and it homogenizes voice. Own-only is safest/most-personal for v1; resolve ownership via the post's `instagram_handle`. Any future widening retrieves over *embeddings/structure* only, never others' `user_note`, and behind explicit consent.
4. **Feed-hook cost** — **[confirm]** → **Tap-gated + cache-per-image** (compute the hook once per image, reuse for every viewer), not auto-on-every-pause. Controls B2C LLM cost. ✅
5. **Persona roll-up richness** — **[confirm]** → **Structured-but-capped** (store the lens/region structure, not a flattened line; cap doc size). Richer retrieval without unbounded growth. ✅
6. **Écart / Anuraṇana + Aletheia name** — **[judgment]** → **LOCK the split** (see below): **Anuraṇana = the taste graph**, **Écart = the reading act / the pause**, **Aletheia stays** the engine name. ✅ (recorded in `decisions-darshan.md`).
7. **Attributes-in-catalog** — **[confirm]** → **Vector similarity only**, frequency catalog stays `(category, label)`, no 294-way bucketing (cardinality would fragment it). ✅

## Track D — unified Visual pane

1. **Un-modal vs modal** — **[confirm]** → **Fully in-pane**; promote `RegionDetectorModal`'s body into the live Visual pane, detection as an async in-pane action. The whole "dynamic surface" premise. ✅
2. **Manual marks survive?** — **[judgment]** → **Keep a lightweight freehand draw** for what detection misses (`actor="creator"`), but the *primary* creator action becomes **tap-an-auto-region + comment.** Don't delete freehand entirely; demote it. ✅ suggested (biggest scope lever — override to "tap-only" if you want D leaner).
3. **Save cadence** — **[confirm]** → **Autosave-on-blur, debounced.** If full-array saves get chatty on the live pane, revisit the per-region upsert endpoint Track A flagged (Q4). ✅
4. **Reading-strip placement** — **[judgment]** → **A calm strip under the image** (keeps reading↔region co-located; per-lens `region_ids` highlight parts). Side panel fits more lenses but breaks co-location. ✅ suggested.
5. **`/crops` + pixel system** — **[confirm]** → **Retire both** (Track A retires `bounding_box_tags`; blast-radius found no other reader — reconfirm at build). ✅
6. **Build serialization on `PostDetailPage.jsx`** — **[judgment]** → **Dedicated build slot: the Drishya thread pauses edits to `PostDetailPage.jsx`, Darshan `git pull`s latest, makes its scoped edit (remove Unconceal tab, swap editor mount, un-modal detection), commits + pushes, then the UI thread resumes.** This is *the* build-time coordination point (D overlaps Lanes 1/2/3 exactly). **← confirm the mechanism (pause vs branch-and-merge-order).**
7. **Consumer variant scope now?** — **[confirm]** → **Later.** Keep D's deep surface clean enough that Track F extracts the one-tap lite variant; don't build F's UI inside D. ✅

## Track F — consumer / B2C / chain / video

1. **`taste_signals` separate store** — **[confirm]** → **Yes.** Audience taps become lightweight events in their own collection (referencing `region_id`/`embedding_id`), **not** full `Region` rows; `actor="audience"` Regions reserved for the rare audience-creates-a-mark case. The core F↔A decision — keeps consumer friction ≈0 and the creator array clean. ✅
2. **Video: spike vs full pipeline** — **[judgment]** → **Spike now, full async worker immediately after** (same call as B6; same schema either way, so no rework). ✅ suggested. **← your call.**
3. **Account gate** — **[confirm]** → **Anonymous/session users get the hook + forks; an account is the upsell that unlocks the saved taste portfolio.** Identity as upsell, not toll. ✅
4. **Consent default** — **[judgment]** → **Explicit opt-in** for dwell/replay instrumentation (clear opt-in with visible value). Slightly less data, much stronger "taste given back, not harvested" trust story. ✅ suggested. **← your call.**
5. **First signals cut** — **[confirm]** → **Rungs 2–3 (region tap + Aletheia fork)** as the MVP — highest signal-per-friction, both nearly free to serve; defer dwell (noisy) + save-reason to fast-follow. ✅
6. **Brand-tier data boundary** — **[judgment]** → **Brands query anonymized aggregate taste trends + match to contractable *creators* only — never identified consumer profiles.** This is *the* privacy line the whole "level up, not harvest" thesis rests on; lock it explicitly before any brand-facing surface. ✅ suggested — **confirm, it's load-bearing.**
7. **Audience portfolio separate from creator persona** — **[confirm]** → **Yes.** Shares the schema, separate store; audience signal must not leak into `persona_service`. ✅

---

## The genuinely-your-call shortlist (the rest are safe confirms)
- **B6 / F2** — video: spike this cycle (rec) vs full async pipeline now.
- **C2 / C3** — how personal the reading gets; own-history vs cross-curator retrieval.
- **D2** — keep lightweight freehand creator marks, or tap-only.
- **D6** — the `PostDetailPage.jsx` serialization mechanism with the Drishya thread.
- **F4** — signal-capture consent: explicit opt-in (rec) vs on-by-default-opt-out.
- **F6** — the brand-tier privacy boundary (anonymized aggregates + creator match only).

Everything else is a low-risk technical default you can accept in a batch. Once these are marked, the build has a complete contract. **All six tracks (A–F) are now researched; this sheet is the full pre-build gate.**
