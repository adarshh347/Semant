# Pre-build decision sheet — consolidated open questions + suggested answers

**Purpose:** one place to greenlight the build. Every open question from the closed research tracks (A done, B, C, D) with a **suggested answer**. Track F's questions fold in when it lands.
**Legend:** **[confirm]** = safe technical default, the track's own recommendation, low risk to accept · **[judgment]** = genuinely your call, trade-off worth a beat.
Mark each ✅ (accept) or ✏️ (override), then it's a build-ready contract.

---

## Track B — segmentation / model stack

1. **GPU serving path** — **[confirm]** → **Serverless/hosted first** (Replicate / Modal / HF Inference); self-host only when volume justifies. Matches the Track-A "don't buy infra ahead of data" call (77 regions today). ✅ suggested.
2. **Fashion segmenter** — **[confirm]** → **Fashionformer first (SOTA seg+attr), Attribute-Mask-RCNN as simpler-to-serve fallback, benchmark both on real Drishya posts.** Don't lock without the bench. ✅
3. **Non-fashion domains this cycle** — **[judgment]** → **SAM2 + LLM naming only** for architecture/photography; no dedicated models until fashion is proven. One deep domain first. (Consistent with the locked fashion wedge.) ✅ suggested.
4. **Dedup/precedence** — **[confirm]** → **Fashionpedia > SAM2(tap) > YOLO** for garments; keep overlapping detections only if IoU < τ; `detector` records provenance. Lives in Track B (per Track A Q6). ✅
5. **SAM2 laziness** — **[confirm]** → **On-demand (tap / "reveal more"), never dense-on-upload.** The main cost lever; also shapes Track D's reveal UX. ✅
6. **Video scope this cycle** — **[judgment]** → **Ship the image loop + a video *spike*** (prove keyframe→SAM2-track + one replay signal on a single reel) **this cycle; full async video worker immediately after.** This honors your "pull video forward" lock (Fork 3) — the spike de-risks now — while keeping the guardrail that the image loop stays independently shippable. *If you want the full async pipeline built this cycle, that's also consistent with Fork 3, just heavier and it competes with the image MVP for time.* **← your call: spike (rec) vs full pipeline now.**
7. **Atmosphere is image-global** — **[confirm]** → **Yes.** Mood/atmosphere stays an Aletheia image-level reading, not a boxed region. Keeps the Visual pane clean. ✅

## Track C — Aletheia / taste-vector / RAG

1. **Lens registry — config vs generated** — **[confirm]** → **Fixed domain→lens registry, LLM instantiates it** (legible, stable, UI-labelable). Free-invention is more surprising but breaks hover-links. ✅
2. **Personalization strength** — **[judgment]** → **Feed the persona's recurring lenses as a prior, but cap its weight and always keep one "wildcard" lens that ignores history** (avoid the always-reads-for-drape echo chamber). ✅ suggested — tune the cap later.
3. **Retrieval scope** — **[judgment]** → **Own-history first; cross-curator catalog opt-in only** (richer but risks homogenizing voice / leaking others' notes). ✅ suggested.
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

---

## The genuinely-your-call shortlist (the rest are safe confirms)
- **B6** — video: spike this cycle (rec) vs full async pipeline now.
- **C2 / C3** — how personal the reading gets; own-history vs cross-curator retrieval.
- **D2** — keep lightweight freehand creator marks, or tap-only.
- **D6** — the `PostDetailPage.jsx` serialization mechanism with the Drishya thread.

Everything else is a low-risk technical default you can accept in a batch. Once these are marked, the build has a complete contract (pending Track F + the integration synthesis).
