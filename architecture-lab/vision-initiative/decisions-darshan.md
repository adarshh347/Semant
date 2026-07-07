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
- `actor: str` — who created the mark: `auto | creator | audience` (so a one-tap audience signal and a creator annotation share one schema). Keep `source: manual|auto` too, or fold both into `actor` — **Track A-v2 to pick the cleanest single field** (see updated prompt).

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

## Part 2 — The 6 strategy forks, framed in detail (Adarsh to decide)

Each: **what's at stake · the options · recommendation · what it changes downstream.** My recommendation is marked ★; the call is yours.

### Fork 1 — Emphasis & sequencing: who do we build for first?
**At stake:** how fast we get a *showable, credible* thing, and how much surface area we carry at once. The engine (parts → reading → taste-vector) is shared no matter what; this fork is about which *surface* we finish first.
- **A. Creator-first, audience-ready, brand-monetized ★** — finish the creator loop (image → Fashionpedia parts → felt reading → taste signature → grounded editorial piece), *design* A/C so the audience surface plugs in, monetize via brands once the graph has data. Fastest to the portfolio/resume demo; de-risks the engine before consumer polish.
- **B. Audience-first (B2C lead)** — build the "read this image deeper" consumer app first. Flashier, bigger reach story — but it *still* needs the same engine, so you pay the engine cost with less to show early, and consumer UX polish is expensive.
- **C. True parallel** — creator + audience together. Fastest to a two-sided story, but doubles the build surface and the risk while the engine is still unproven.
**Recommendation:** **A.** The creator demo is the credibility artifact *and* the engine test; audience + brand layer on the same spine without a rewrite.
**Changes downstream:** sets build order after A lands (B/C tracks → creator demo → then Track F). If B or C is chosen, Track F gets pulled forward and D must design consumer-first.

### Fork 2 — Make Track F (B2C) official now?
**At stake:** whether the consumer/chain research becomes a first-class, tracked workstream or stays an idea.
- **A. Yes — make it official ★** — it's research-only and parallel-safe; formalizing it means it gets a findings doc + an umbrella checkbox and doesn't get lost. Costs nothing now.
- **B. Hold** — keep it as strategy prose until the creator engine is proven, to stay focused.
**Recommendation:** **A**, but *sequence its research after A/C findings* (it depends on the graph-ready schema + the reading engine). Official, not urgent.
**Changes downstream:** adds Track F to the umbrella issue; a B2C findings pass gets scheduled.

### Fork 3 — How far into video/reels this cycle?
**At stake:** the reel-slicing / "which part of a video is loved" capability is genuinely differentiated for B2C, but video (SAM2-video, streaming masks, replay signals) is the heaviest thing in the plan.
- **A. Image-first, video Phase-later ★** — scope video in Track F, build the image MVP now, add video when the image loop is proven. Keeps the MVP shippable.
- **B. Pull video forward** — treat reel-slicing as central to the consumer hook and invest now. Bigger wow, but heavy infra (GPU video serving) and it blocks the simpler image MVP.
**Recommendation:** **A.** Video is a Phase-2 multiplier, not the wedge. The image "read deeper" hook already delivers the "level up from social media" feeling at a fraction of the cost.
**Changes downstream:** Track F documents the video boundary; model-plan Phase 4 stays later.

### Fork 4 — Model adoption depth (ties to Track B)
**At stake:** technical credibility vs deploy weight. Real fashion CV models read far stronger (resume/portfolio) than "a GPT wrapper," but they need GPU-ish serving.
- **A. Phased full-stack ★** — FashionCLIP now (light, no training, gives taste-vectors + better labels immediately), then Fashionpedia segmentation, then SAM2. Each phase earns its keep; ends with a genuinely credible stack.
- **B. Light first** — FashionCLIP labels + the current LLM only; defer the heavy segmenters. Ships faster, but the "domain-deep felt reading per part" — the whole differentiator — stays shallow until you add them anyway.
**Recommendation:** **A**, explicitly phased (FashionCLIP → Fashionpedia → SAM2). You get an early win (vectors) and a credible endpoint without a big-bang deploy.
**Changes downstream:** Track B builds the benchmark + deploy/cost/fallback plan around this staging.

### Fork 5 — Which side leads the pitch (headline framing)?
**At stake:** the *story* you tell (investor / resume / portfolio / landing). One engine, but the headline shapes perception.
- **A. Consumer vision headline, brand-intelligence as proof ★** — lead with "a level up from social media / the taste-and-story layer," back it with the B2B taste-intelligence business as the monetization proof. Emotionally resonant *and* commercially credible.
- **B. B2B taste-intelligence headline** — lead with the brand/creator business (revenue-credible, defensible, resume-strong for an AI/data role), consumer as the reach/flywheel. Safer for investor/enterprise framing, less inspiring as a story.
- **C. Keep both balanced** — dual pitch; risks a diffuse "what is it" message.
**Recommendation:** **A** for a portfolio/landing/vision context; note that for a pure *investor/enterprise* deck, **B** may convert better. Pick per audience — but the landing/motive page leads with **A** (the motive narratives already do).
**Changes downstream:** shapes `motive-narratives.md` emphasis and which demo you feature.

### Fork 6 — Name the taste graph?
**At stake:** the taste graph (parts × felt-meaning × vectors) is becoming the center of gravity — the thing users own and brands buy. A name makes it a product object, not plumbing.
- **A. Yes, name it ★** — proposal: **Ruchi** (रुचि — taste / discernment / delight), fitting the Sanskrit family (Darshan, Aletheia*, Sūkṣma, Drishya, Sutradhar). The user's *Ruchi* = their taste graph/portfolio.
- **B. Not yet** — leave it unnamed until the app rebrand (Drishti vs Nazar) settles, to avoid naming sprawl.
**Recommendation:** **A** — "Ruchi" as a working name for the taste graph; cheap, on-theme, and gives the B2C "taste given back to you" surface a noun. Veto freely.
(*Aletheia is the one Greek name in an otherwise Sanskrit set — flagged earlier; still open.)
**Changes downstream:** cosmetic; threads into naming in `decisions-log.md`.

---

## Part 3 — What's still blocking a build
- Adarsh picks Forks 1–6 above (Track A's 7 are locked).
- Track A findings get a **v2 extension pass** (the pre-revamp findings don't yet include `part/attributes/embedding_id/actor` — the updated Track A prompt now asks for them).
- Umbrella GitHub issue created (still missing) with A–F checkboxes.
