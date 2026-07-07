# Track E — Purpose, niche & positioning: findings

**Lens:** Purpose → (Structure/Surface deferred to A/B/C/D). This track fixes *who + why* so the four build tracks don't diverge.
**Method:** grounded the thesis in the actual pipeline (backend `vision_service.py`, `segmentation_service.py`, `anatomy_catalog_service.py`, `schemas/post.py`) + a competitive scan (Are.na, Cosmos, Pinterest, Ximilar-class taggers, academic taste-models). Web sources listed at the end.

---

## Headline

The thesis in `00-brief.md` holds, but it is **two claims bolted together** and only one is truly defensible as the wedge:

1. *Structured aesthetic close-reading* — decompose an image into **felt, meaningful parts** and say **how each affects you** (first-person, phenomenological).
2. *Taste-learning that writes with you* — accrue those readings into a personal **vision-language** that then **generates grounded writing**.

Claim (1) is the **novel, unoccupied niche** — nobody ships part-by-part *felt-meaning* annotation. Claim (2) is the **moat and the demo payoff**, but it only becomes real once (1) has produced a corpus. So the positioning is: **lead with the close-reading act, sell with the taste-loop.** The pipeline already scaffolds both — the gap is that today every intelligence layer is *generic* (fixed 3 lenses, COCO-only geometry, one free-text mode), so the felt-meaning never gets domain-deep enough to be worth accruing. That is exactly what B and C must fix, and E's job is to say **for whom** that depth should be tuned.

---

## 1. Who exactly — primary niche(s)

**Primary: the fashion curator / stylist / fashion-editorial writer.** Lead here.
**Secondary (same machine, later): architecture & interiors.** Photography is a *general fallback*, not a launch niche (reasons below).

### Why fashion is the lead, grounded in the code
- The pipeline is **already deepest here**. Sūkṣma's `garment` mode carries a rich, tailor-grade sub-part vocabulary — "collar, lapel, placket, button row, cuff, sleeve (upper/fore), shoulder seam, yoke, hem, waistband, pleat, drape, fold, pocket, neckline, fastening" (`vision_service.py:644-650`). No other domain has a mode this specific; `composition` and `texture` are one generic paragraph each (`vision_service.py:656-672`). The product's *unfair advantage* is already fashion-shaped.
- Fashion is the one domain where "**why this works, part by part**" is a **daily, paid, unautomated job** (stylist rationale, trend reports, PR/lookbook copy, buyer notes) — high JTBD pressure.
- YOLO gives a usable coarse anchor here: `person` → `figure`, and the bag/tie family → `garment` (`segmentation_service.py:37-44`). A body anchor is exactly the scaffold a garment decomposition needs. In architecture/photography YOLO returns almost nothing useful (COCO has no "cornice" or "leading line"), so those domains lean 100% on the LLM until B adds domain models.
- Taste-accrual is **already fashion-flavoured**: `anatomy_catalog_service` buckets by `(category, label)` and tracks a `materials` set per bucket (`anatomy_catalog_service.py:107-109, 121-131`) — material is a first-class axis, which is a fashion/textile instinct, not a photography one.

### Why architecture is the natural second, not first
Same "elements + materials + light + spatial mood" shape, and it reuses the material axis — but it needs B to add an architectural part-model and C to add architectural lenses. Ship it once the fashion loop is proven; the machinery is identical.

### Why photography is a fallback, not a launch niche
Photography close-reading (composition, light, colour field) is real, but (a) it has **no coarse anchors** — YOLO is useless on an abstract frame, so it degrades to pure-LLM guessing with model-estimated boxes (`vision_service.py:372-403`, "Coordinates are model-estimated"); (b) its audience overlaps the crowded "aesthetic scoring / photo-culling" market (Peakto etc.); (c) "the fold of the fabric, the fall of light" from `00-brief.md` is a *fashion* sentence. Keep photography as the domain-general mode the app falls back to, not the pitch.

**Recommendation:** lead fashion, architecture second, photography as general fallback. (This is a sharpening of the brief's "likely fashion, then architecture, photography" — E confirms it and says *why in code terms*.)

---

## 2. The job-to-be-done

**For the fashion curator:** *"I know this image is good and I need to say **why** — part by part, in words a client/reader/my future self will trust — and I want that articulation to compound into a signature I can write from, instead of evaporating into a Pinterest board."*

Three sub-jobs, in the order the product should serve them:

| Sub-job | What they do today (the pain) | What Darshan makes easy | Pipeline that must deliver it |
|---|---|---|---|
| **Articulate** why an image works, part by part | Stares at a moodboard, writes vague captions ("love this mood"); the *reason* stays tacit | Decompose into garment sub-parts + read each one's felt effect | B (domain parts), C (per-part reading) |
| **Accumulate** a taste corpus | Boards pile up as similarity clusters with no memory of *why* anything was saved | Every part pick → comment → **remembered**; rolls into a "portrait" of what they consistently notice | A (one region model), D (pick→comment→remember), `anatomy_catalog_service` |
| **Generate** copy grounded in real visual detail | Writes lookbook/trend copy from scratch, or gets generic AI captions detached from the actual garment | `/draft` / `/part` / `/lens` writing seeded by *this image's* real parts + *their* taste | C (feed the writer), Sutradhar slash-AI (per `decisions-log`) |

The through-line: **Articulate → Accumulate → Generate.** The brief's five moves map onto exactly this (unify + reveal serve Accumulate; segmentation + Aletheia serve Articulate; catalog + Sutradhar serve Generate).

---

## 3. Differentiator

The competitive field splits into three camps, and Darshan sits in a gap none of them occupy.

| Tool / camp | What it does to an image | Unit of value | First-person felt meaning? | Learns *your* taste? | Writes from it? |
|---|---|---|---|---|---|
| **Pinterest** | similarity feed + boards | the *next* image | No | Only as a recommender signal | No |
| **Are.na** | manual channels, no semantics, deliberate research | the *connection* between blocks | No (you supply all meaning) | No (by design — it's neutral) | No |
| **Cosmos** | AI auto-tags colour/mood/style for search & clusters | *discoverability* of what you saved | No — tags are objective attributes | No — tags describe the image, not you | No |
| **Ximilar / YesPlz / PhotoTag-class** | object + attribute detection (sole, heel, material, type) | catalog *metadata* / SEO keywords | No — product attributes | No | Captions, not authored voice |
| **Aesthetic-scorer / taste-model research** (PAMELA, TASTE datasets) | predicts *whether you'll like* an image (a rating) | a *score* | No — a number, not a reading | Yes, but as a **predictor**, not an articulator | No |
| **Darshan** | decomposes into **meaningful parts** + a **felt reading per part**, accrued into a **vision-language** that **writes** | the *articulated reason* + your evolving taste | **Yes — the core unit** | **Yes — as language you can read & write from** | **Yes — grounded in the actual parts** |

**The one-sentence wedge:** every existing tool answers *"what is in this image"* or *"will you like it"*; Darshan is the only one that answers *"**why** does this move me, part by part — and here it is in my own words."* Object-tagging and taste-scoring are both **reductive to a label/number**; Darshan is **generative of meaning and prose**. That's the novel combination: *felt-meaning per part* + *taste as writable language* + *grounded generation* — three things that each exist in pieces nowhere together.

**Honest caveats (for Adarsh):**
- The felt-reading quality is entirely hostage to the LLM today (Groq llama-4-scout, `vision_service.py:26`) and the *fixed* 3-lens prompt (`ALETHEIA_PROMPT`, `vision_service.py:594-631`). Generic-in → generic-out. C is load-bearing for the whole differentiator.
- "Learns your taste" is currently a **frequency + intensity aggregation** (`anatomy_catalog_service.py:100-136`) plus an LLM "portrait" — real but shallow. It's a defensible v1; don't oversell it as a model.

---

## 4. The killer demo (one end-to-end scenario)

**"One editorial image → a styled, sourced paragraph in the curator's own voice."** Resume/portfolio/pitch-ready, uses only pipeline parts that exist or are on the track roadmap.

1. **In:** curator drops a fashion editorial shot (a figure in a structured coat).
2. **See (coarse):** YOLO anchors the `person`→`figure` and any bag/accessory (`segmentation_service.py`), giving true polygon shapes, not rough rects.
3. **Mark (fine):** Sūkṣma `garment` mode decomposes *within* the anchor — "notched lapel, the drape at the waist, the cuff turn-back, the hem's weight" — each a distinct box with a `material` guess (`vision_service.py:446-527, 644-650`).
4. **Understand (read):** Aletheia — **context-triggered to fashion** (C's job) — reads the picked parts: not "person, coat" but "the lapel's severity vs. the drape's give; the coat performs control while the hem quietly refuses it." Curator taps a part, adds one line of their own felt-meaning; it's **remembered** (`region_annotations`, `POST /local-context`).
5. **Taste signal:** this joins the catalog — the portrait now knows this curator keeps starring *structured tailoring + soft drape tension*, in wool and gabardine (`anatomy_catalog_service.py:149-191`).
6. **Out (write):** in Drishya's editor, `/draft` (or `/part` / `/lens`, per `decisions-log.md:89`) writes a lookbook paragraph **grounded in those exact parts and that taste** — the lapel, the drape, the hem — in the curator's accumulating voice, with `origin: sutradhar` marking who wrote it.

**Why it sells:** the audience *watches meaning get made* — image → parts → felt reading → a paragraph that could ship in a real lookbook, visibly built from the picks, not hallucinated. It demonstrates all four tracks in one 60-second flow and shows the loop closing.

**Minimum bar to demo it:** A (one region object so a pick can be commented + remembered), C (fashion-triggered lenses + the writer actually receives per-image context), D (pick→comment→remember without mess). B and the deep taste-model can be v2 — the demo survives on the existing `garment` mode.

---

## 5. Purpose → requirements map (feeds A/B/C/D)

What each track must deliver for §4 to be real. This is E's hand-off to the parallel tracks.

| Track | Purpose requirement it must satisfy | Concrete "done" for the demo | Grounding / today's gap |
|---|---|---|---|
| **A — data model** | A pick must be *one thing* that can be commented and remembered. Manual + auto marks are the same object. | Single `region` type unifying `bounding_box_tags` (pixel rects, `schemas/post.py:8-12,37`) and `region_annotations` (`schemas/post.py:46`); carries `label, category, box, polygon, material, user_note, prioritised, weight, origin(human|auto)`. Migration path for both. | Two disjoint systems today; `BoundingBox` is int-pixel, regions are normalized-float dicts — they can't merge without A. |
| **B — segmentation** | The parts must be **fashion-meaningful**, not COCO objects. | `garment` mode is the reference standard; formalise its vocabulary; decide YOLO-anchor vs LLM-semantic division of labour; keep architecture as the second vocabulary. | `_category` is COCO-only (`segmentation_service.py:37-44`); fine parts are LLM-estimated boxes (`vision_service.py:547-565`). Domain depth = fashion first. |
| **C — Aletheia** | The reading must be **selected by fashion context**, and it must **feed the writer**. | Lenses chosen by domain+detected parts+mood (retire the fixed Phenomenological/Semiotic/Atmospheric trio); Aletheia output becomes structured context the Sutradhar `/draft` path consumes. | Fixed 3-lens prompt (`vision_service.py:594-631`); Aletheia and the writer are currently unconnected. **Load-bearing track.** |
| **D — frontend** | Many fashion sub-parts must reveal **without mess**, each **pick→comment→remember**. | One Visual-pane surface (retire Unconceal split); progressive coarse→fine reveal; focus-one-dims-others; true polygons; per-part comment box writing to A's model. | Split UI today (`BoundingBoxEditor.jsx` vs `RegionDetectorModal.jsx` / Unconceal branch of `PostDetailPage.jsx`). |
| **(cross) Sutradhar** | Generation must be **grounded in the picked parts + taste**, not free-floating. | `/draft` / `/part` / `/lens` seed from the region model + the catalog portrait; `origin` marks authorship. | Slash-AI direction already LOCKED (`decisions-log.md:60-99`); needs C's context to be grounded. |

**Sequencing (confirming the brief):** E → A (the spine) → B/C/D in parallel → integrate → the loop. C is the differentiator's bottleneck; if one track gets the most attention, it's C.

---

## Questions for Adarsh

1. **Lead niche — confirm fashion?** E recommends fashion first (deepest in code), architecture second, photography as general fallback. Agree, or do you want it to stay domain-general at launch (broader but shallower)?
2. **Positioning line — pick the wedge.** E argues the sellable wedge is *"why does this move me, part by part — in my own words,"* leading with the **close-reading act** and selling with the **taste-loop**. Does that match how you'd pitch it on a resume/portfolio, or do you want taste-learning as the headline?
3. **"Learns your taste" honesty.** Today it's frequency+intensity aggregation + an LLM portrait (real but shallow). Are you comfortable positioning that as v1 "taste-language," with a deeper taste-model as an explicit v2 — or should B/C aim higher before we make the claim?
4. **Demo target.** Is §4 (one fashion image → a sourced lookbook paragraph in the curator's voice) the demo you want to build toward? If the intended showcase is different (e.g. a multi-image taste-portrait, or an architecture piece), say so now — it re-weights A/B/C/D.
5. **Naming.** Brief proposes keeping **Aletheia** (scaled to the context brain) and **Darshan** as the initiative name. Confirm both, given the app itself is mid-rebrand (Drishti vs Nazar, `decisions-log.md:11`).
6. **Umbrella issue is missing.** The handoff references a GitHub issue *"Darshan — vision pipeline initiative (umbrella)"* but it does **not exist** (open issues are #8, #9, #10, #13, #15, #19; related: #8 sukshma, #9 anatomy scaling, #10 annotation UI). Want me to open the umbrella issue (label `architecture`) with the five tracks as checkboxes and link #8/#9/#10 under it? That's workflow hygiene, not app code — happy to do it next.

---

*Sources (competitive scan): Cosmos vs Are.na organization models; Ximilar / YesPlz fashion attribute tagging; academic personalized-taste models (PAMELA, TASTE). Full URLs in the session log. All code claims cite `backend/` files at the lines shown; verified against the working tree on `feat/frontend` (commit 8a95d0d).*
