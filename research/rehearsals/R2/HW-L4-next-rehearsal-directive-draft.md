# HW-L4 — Next-rehearsal directive (DRAFT)

**PREPARATION ONLY — no rehearsal executed, no model calls made.** Zero VLM, zero LLM, zero Groq,
zero OpenRouter. No database document was mutated; only `find` / `count_documents` queries were
issued. No source code was edited; nothing was staged, committed or pushed. The only writes are this
file and temporary PNGs in the session scratchpad.

**Method.** Every fixture named by HW-S4 was resolved to a full 24-hex ObjectId, its `photo_url`
downloaded, hashed, and **looked at** with an image-rendering read. Annotation state was then read
from Mongo (`post_collection`, `region_embeddings_collection`, `vision_run_collection`). No region
label, tag or `domain_profile` was used as evidence of what any image is — per HW-S4's standing rule.

---

## 1. Visual verification of HW-S4's substitutions

### 1.1 A4 primary — `695be784a9ea58f1b6aef5ec` · **S4 CORRECT** (with three additions)

**What it actually is.** A photograph of a Timurid/Persianate tiled interior — a shallow bay seen
frontally. A tiled semi-dome or squinch occupies the top of the frame. Below it, a central
pointed-arch niche; **inside that niche a small pierced stone jali/grille window through which warm
daylight falls** — the only non-turquoise, non-tiled element in the picture. Two flanking niches
with **stalactite (muqarnas) hoods**, not plain blind arches. A middle register of three large
square framed panels, each with a circular star-medallion. A dado of fine polychrome geometric
tilework (visibly warmer, with red and ochre). A strip of brick/stone floor at the very bottom edge.

**Verdict on S4: correct on every load-bearing property** — it is a photograph, it is architecture
in situ, and it is **genuinely aniconic**: no human, animal or figural motif anywhere in the frame.
This is the only verified non-figurative fixture available to the batch.

Three additions S4 did not record, all of which *improve* the fixture for R8:

1. **The jali window is a competing organiser.** It is a hole in the surface, warm against cold,
   asymmetric in tone, and it sits on the composition's centre axis. So the seed question has a real
   contest in it: the tile grid organises, *or* the one aperture does. An answer either way is
   evidenceable, and a wrong answer is detectable.
2. **The revetment is visibly damaged and patched** — several panels have lost tiles, and the repair
   patches break the pattern's continuity. Pattern *failure* is visible, which gives a refusal or a
   qualification somewhere concrete to land.
3. **Native size is 453 × 680.** Under the 768-px probe cap used by A3 this image is sent **at native
   resolution, unscaled**. See §3 — this directly repairs A3's single biggest recorded weakness.

**Annotation state (verified).** `region_annotations` **0** · `grounds` **0** · `percepts` **0** ·
`text_blocks` **0** · `region_embeddings` **0** · `vision_runs` **0**. **No detached grounds** (none
exist). Completely clean. No prior run has touched it.

**Image stats.** mean luminance 127.9 · mean saturation 0.574 · 7.1 % of pixels below luminance 64 ·
**0.0000 pure-black pixels** (i.e. not a composite plate — the spark-01 confound is absent).

### 1.2 A4 alternate — `695be8eca9ea58f1b6aef60b` · **S4 CORRECT, but do not spend it here**

**What it actually is.** An upward/frontal view into a gilded **muqarnas half-vault** filling a
tiled iwan. **The sky is visible at the top of the frame** — this is an open-air iwan hood, not an
enclosed interior vault as "vault" implies. Flanked by two tall vertical panels of **blue-ground
thuluth calligraphy**, floral spandrels, and a blue tiled dado. Near-perfect bilateral symmetry.

**Two reasons it is the weaker A4 choice**, both of which S4 did not weigh:

- **It contains script.** A probe about "surface pattern" on an image with two large inscription
  panels risks the model answering about *reading* rather than about surface — the same
  category-slip S4 correctly predicted for the drawing fixture (surface → depicted textile).
- **Its symmetry makes the seed question trivially affirmative.** The composition is so exactly
  organised by the ornament that "does the pattern organise the composition?" has no contest in it.
  `695be784` has a contest; this one does not.

**Annotation state (verified).** 0 / 0 / 0 / 0 / 0 embeddings / 0 vision_runs. Clean.
**It is also A6 Pair 2's key image.** Recommending `695be784` for A4 resolves S4's own flagged
double-booking at no cost.

### 1.3 A5 primary — the `695be817` ambiguity, **resolved by bytes**

Both posts exist and are distinct documents with **distinct Cloudinary `photo_url`s**:

| id | photo_url basename | sha256 (16) |
|---|---|---|
| `695be817a9ea58f1b6aef5fa` | `45fd517f-…jpg` | `c5055621ef8782c1` |
| `695be817a9ea58f1b6aef5fb` | `10b6e04a-…jpg` | `c5055621ef8782c1` |

**The downloaded bytes are identical.** They are the same photograph stored twice under two
Cloudinary asset ids from one `source_url` (`…G90kiVxaQAAHqt_`). So the ambiguity is harmless to the
*evidence* but must still be pinned in the manifest, because two post ids means two possible
pre-state records. **I verified `…5fa`.** Use `695be817a9ea58f1b6aef5fa` and record `…5fb` in
`source_notes` as a known byte-identical duplicate import, so the duplication is a recorded corpus
finding rather than an accident.

**What it actually is.** An *Angel of Grief* type funerary monument, in daylight, photographed as a
casual snapshot. A winged marble angel has collapsed **face-down across the lid of a tomb chest**,
both arms flung forward over the chest, head buried in the near arm; the left wing sweeps up and
back across the upper-left of the frame, the right wing droops down behind; **one leg trails down
the left side** of the chest to a stepped hexagonal plinth. The chest front carries Greek-key
fretwork and anthemion/acanthus corner scrolls. Behind: a **colonnaded rotunda** — fluted columns,
a curved rear wall, and above, in the entablature, a **circular inscribed medallion/tondo** with
lettering. Raking low sun from the left.

**Verdict on S4: correct in substance, with two corrections.** (a) The element above is a circular
inscribed medallion, **not a "painted lunette"** — if the authored sentence or the prompt says
"lunette" the model can refuse on the architecture and never reach the emotional leap, which is the
exact failure S4 was trying to avoid with its *nave → rotunda* amendment. (b) It is *both* arms
forward and a *leg* hanging, not "one arm hanging."

**One property that makes it materially better than the blocked Pietà:** it is an untreated snapshot.
The Pietà fixture carries a blended grain/texture layer (a reproduction confound S4 found). This one
has none — it is a plain `depiction`.

**Annotation state (verified, both ids).** `region_annotations` 0 · `grounds` 0 · `percepts` 0 ·
`text_blocks` 0 · `region_embeddings` 0 · `vision_runs` 0, for **both** `…5fa` and `…5fb`. No
detached grounds. Clean and unused.

**Image stats** (`…5fa`): mean luminance 101.7 · mean saturation 0.217 · 27.7 % below luminance 64 ·
0.0000 pure black · native 510 × 680 (also under the 768 cap).

### 1.4 A5 alternates — one is **CORRECT**, one must be **WITHDRAWN**

- **`695be88ea9ea58f1b6aef602` — S4 CORRECT.** A veiled, hooded standing mourner, hands lowered and
  open, before a large **gilded radiating sunburst with an Eye of Providence in a triangle**, set in
  a round-arched aedicula of dark marble, flanked by two draped funerary urns on carved pedestals,
  with porphyry roundels in the spandrels and faint incised gold script behind. S4's warning stands:
  the iconography is so explicit that an overreach here would be *iconographic* as much as
  emotional, confounding R9. Clean (0/0/0/0/0). **Also A6 Pair 3's key image** — leave it free.

- **`695be78fa9ea58f1b6aef5ee` — WITHDRAW. New reuse conflict, missed by S4.**
  S4 lists it as "clean, unconfounded, unused by any prior run." It is clean, but it is **not
  unconfounded**. Its `source_url` is `…G92ZowXWIAApuVR`; A3's committed neighbour
  `695be790a9ea58f1b6aef5ef` is `…G92ZowbXsAAvKRz` — **the same tweet**. I downloaded and looked at
  both: `695be790` is a tight head-and-shoulders close-up of a weathered figure with a photographer
  watermark; `695be78f` is the **full seated view of what is evidently the same sculpture** — same
  streaked weathering, same drapery, same head-back / eyes-closed / mouth-parted expression. Running
  A5 on it would test narrative overreach against the very object A3 has already elicited "ecstasy
  or sorrow" about, and A3's `sparks.md` explicitly **withheld** "the painting and the statue are
  both about grief" as overreach. A5's result could not be separated from that. **Do not use
  `695be78f` in A5, A6, or any later R2 run.** `695be8bea9ea58f1b6aef60a` remains excluded anyway
  (1 `frame` ground).

### 1.5 A6 pair — **S4 PARTLY CORRECT; the visual rhyme is weaker than stated**

- **`695be6bca9ea58f1b6aef5df`** — correct in substance: a small **gilt-bronze Nataraja** on a dark
  plinth at bottom-centre, hit by one hard low spotlight, throwing an enormous shadow of
  figure-plus-*prabhamandala* onto a rough rubble-stone wall. But the shadow's flame ring is **an
  arch open at the bottom, bilaterally symmetric about a dancing figure** — it is not a radial
  circle, and it is figure-centred.
- **`695be803a9ea58f1b6aef5f8`** — correct: the Florence Duomo façade rose window, polychrome
  green/white/pink marble inlay. But the window occupies only the **upper half**; the **lower half is
  densely figurative** — a seated Madonna and Child in a gabled niche plus at least five standing
  saints in colonnetted niches and two bust roundels. S4 recorded "flanked by saints in niches" but
  not that the figures are roughly half the frame.

**Consequences for A6, both new:**
1. The claimed rhyme ("two circular radiating motifs") is real only if you compare a *shadow arch* to
   a *true 24-fold radial oculus*. A weak rhyme makes a refusal cheap and uninformative — A6 wants
   the model to resist a **seductive** analogy, not an easy one.
2. Both images are **figure-dominated**, and spark-06 says the model attends hard to anything
   face-like. Full frames will be answered about the dancer and the Madonna, not about the motifs.
3. Luminance mismatch is extreme: `695be6bc` mean luminance **39.3** (75.8 % of pixels below 64)
   vs `695be803` **136.4**. At any downscale the shadow may simply not be legible — and A3's critique
   already recorded a mis-description caused by downscaling.

**Pair 2 measured, for comparison:** `695be8ec` (lum 92.3, sat 0.376) × `695be815a9ea58f1b6aef5f9`
(lum 72.7, sat 0.479). I looked at `695be815`: an upward view into a Gothic apse/chevet vault, ribs
radiating from a boss into tall jewelled stained-glass lancets, an organ at lower left, and — **not
recorded by S4** — a **suspended figure sculpture** (a hovering angel/majesty with a gilt sunburst)
at mid-left. Any A6 crop from this image must exclude it.

**Annotation state (verified, all A6 candidates).** `695be6bc`, `695be803`, `695be8ec`, `695be815`,
`695be7e4`, `695be88e`: **0 regions, 0 grounds, 0 percepts, 0 text_blocks, 0 region_embeddings, 0
vision_runs** — every one. No detached grounds. S4's finding confirmed exactly: A6 has no region
evidence to compare, and its regions must be authored.

---

## 2. RECOMMENDATION — **run A4 next, then A5, then A6**

### A4 first. Reasons, in order of weight.

1. **A4 is the only decision-free rehearsal of the three.** Its fixture is verified, clean, unused,
   and non-conflicting. A5 needs an authored over-reaching sentence whose *presentation* is an open
   design question (see below). A6 is blocked on five. A4 can be executed the moment the substitution
   is accepted; nothing else can.
2. **It restores the batch's only non-figurative slot and the R0 coverage check.** Runs 002, 002F,
   003 and 004 were all figurative — a comparative plate of heads, a Pietà, a carved figure, a
   painting + a funerary figure + a spire. The batch currently has **no evidence at all** about
   whether Semant's vocabulary works on an image with no body in it. A5 and A6 would both add a
   *fifth* figurative run. A4 is the only fixture that closes this gap.
3. **It repairs A3's worst recorded methodological weakness at zero cost.** A3's `critique.md` §1–2:
   three images cost ~7200 tokens, forcing 256 px and `max_tokens: 380`, and probe 2 consequently
   **mis-described the subject** ("downward" head, "lace"). A4 is a **single image at 453 × 680** —
   under the 768 cap, so it is sent at **native resolution**, costs ~2400 tokens, and leaves roughly
   5000 tokens of headroom for a full answer. A4 is the first R2 rehearsal that can be run without a
   resolution or budget confound. That makes its result unusually trustworthy.
4. **It is the sharpest available test of spark-06, and it de-risks A6.** A3's open question 2 is
   *"is address without a figure a real category, or did the model simply pattern-match a facade?"*
   `695be784` is a **frontal, symmetric, arched, aperture-bearing wall** — precisely the kind of
   surface that would tempt an anthropomorphic reading (a central "face", the jali as an eye) with
   absolutely nothing figural in it. If the model anthropomorphises it, spark-06 goes from n=1 to
   n=2 and A6 *must* be redesigned. If it does not, spark-06 is bounded to facade-like frontality —
   which is the "what would kill it" test spark-06 asks for. **Either outcome is a direct input to
   A6's blocked decisions.** Running A6 before A4 forfeits this.
5. **It can strengthen or kill spark-02 cheaply.** "Detection proposes things, never intervals" has
   never been tested on an image with no things in it. A tile grid is all interval.
6. **Low risk.** No stall is catastrophic — a stall on "the pattern is the composition" is itself the
   result R8 exists to elicit. No cultural claim is required, so no refusal is expected on grounds
   that would confound the reading.

### Why not A5 first.

A5 is *ready as a fixture* but not *ready as a design*. R9 requires an authored over-reaching
sentence to be shown to the model — and A3's spark-06 has just established that a stated proposition
is likely to be **accepted rather than located**. That is structurally the same problem as A6's, and
it means A5 needs the same unresolved decision (how to present an authored claim without the claim
becoming the answer) before it can measure anything. Its expected outcome is also the most
predictable of the three: a model that finds a confrontational gaze in a metal spire will find grief
radiating through a rotunda. Running it second, **after** A4 has told us how strongly this model
projects onto non-figurative material, makes its result interpretable instead of merely confirmatory.

### What A4 would strengthen or kill

| spark | if A4 finds… | effect |
|---|---|---|
| spark-06 anthropomorphism | a face/gaze in an aniconic wall | **strengthened to n=2**; A6 must be redesigned before running |
| spark-06 | no figural reading at all | **bounded**; A6's refusal test becomes credible |
| spark-05 address without a figure | address language applied to ornament | widens spark-05 beyond architecture-with-windows |
| spark-05 | no address language | narrows spark-05 to frontality, as A3's critique suspected |
| spark-02 intervals | the model organises by intervals/rhythm, not things | **strengthened** — first evidence from a thing-less image |
| spark-01 reproduction | n/a | 0.0000 pure-black; not a composite; no bearing |

---

## 3. A4 — Execution note (prepared, NOT executed)

**Family:** R8 Surface Becoming Structure · **Lens:** practice (textile / conservation) ·
**Status: ready to run once the substitution is accepted.** Prepared under this directive.
No A4 model calls have been made.

### Correction to the portfolio (fifth in a row)

R0's A4 row names `6a5b91ec` as an "abstract painting." HW-S4 verified it is a photograph of
**graphite drawings of two human figures** on a clipped sheet under a desk lamp — the label came
entirely from `domain_profile = {label: "painting", score: 0.9837}`. It is figurative, so it
forfeits the batch's only non-figurative slot; the row's own alternative ("or authored textile
fixture") governs. **`6a5b91ecbf74ef485d00399f` is withdrawn from A4.**

### Fixture set

| role | post | what it is | `reproduction_vs_depiction` |
|---|---|---|---|
| **subject** | `695be784a9ea58f1b6aef5ec` | photograph of a Timurid/Persianate turquoise tile revetment: semi-dome, central pointed-arch niche with a pierced jali window, two muqarnas-hooded flanking niches, three medallion panels, polychrome dado | **`depiction`** — a photograph of a building in situ, in daylight/ambient light. Not a plate, not a scan, not a composite: 0.0000 pure-black pixels. |

**Single image.** `image_order: ["img-01"]`, recorded explicitly even though there is one image
(amendment §8 applies unconditionally). **No neighbour and no negative** — A3's critique §3–4 showed
that an under-specified negative costs a call and tests something other than what it was built for,
and A4's whole value is that a single image at native resolution has no resolution confound. If a
second R8 fixture is later wanted, `695be8ec` is the designated partner for an R8 follow-up, **not**
for this run.

### Seed gesture — amended

S4 and the batch plan carry: *"does the surface pattern organise the composition?"*
**Amend to a non-yes/no form:**

> **"what organises this composition, and what in the picture is the evidence for it?"**

Rationale, binding: amendment 1 forbids naming a refusal token because a named option becomes an
attractor. A **yes/no question is the same hazard in weaker form** — it supplies the answer's shape
and, worse, it names *surface pattern* as the candidate organiser, which is exactly the claim under
test. The amended form asks for the organiser and its evidence without nominating either. S4 raised
this same objection against A6's seed; it applies identically here, and A4 is the cheaper place to
prove the rephrasing works.

A **second probe is permitted but not required**: if and only if probe 1 does not mention the tiling
at all, ask *"is there anything in this image that repeats, and what does the repetition do?"* — a
follow-up that still does not assert that repetition organises anything.

### Required manifest fields (pre-decided)

| field | value |
|---|---|
| `rehearsal_id` | `005-surface-becoming-structure` |
| `family` | `R8 Surface Becoming Structure` |
| `mode` | `instrumented` |
| `source_condition` | `present` |
| `image_order` | `["img-01"]` — recorded explicitly |
| `reproduction_vs_depiction` | **per image**: `img-01: depiction`. Per-image is now the schema, per A3. |
| `source_notes.subject_is_aniconic` | true — no human, animal or figural motif in frame; **verified by looking**, not by label |
| `source_notes.competing_organiser` | the warm-lit jali window on the centre axis, and the patched tile losses |
| `source_notes.no_label_evidence` | this fixture has **0 regions**, so no detector label could have contaminated its description |
| provider / model | `groq` / `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| `model_budget` | **2** live VLM calls (1 expected; the second only under the stated condition) |
| `image_call_throttle_s` | **25** (single-image calls; ≥25 s between any two) |
| `max_tokens` | **≥1200** — a single image costs ~2400 of the 8000 TPM ceiling, so there is headroom A3 never had. Do not repeat A3's 380. |
| `probe_resolution` | **native 453 × 680, no downscale** (768-px cap not reached). Record that no downscale occurred. |
| `retry_policy` | no retries except a provider-level failure of the first call (then 1 extra) |
| `no_named_refusal_token` | `true` |
| `no_yes_no_seed` | `true` — new, introduced by this directive |
| `no_iconographic_identification` | `true` — do **not** ask the model to attribute the building; attribution is a curator fact if needed at all |
| `no_production_mutation` | `true` |

### Live call budget and throttle (explicit)

- Groq charges **~2400 tokens per image regardless of pixel size** (A3, measured; shrinking
  384 → 256 px did not reduce it) against an **8000 TPM** ceiling.
- One image + prompt + `max_tokens: 1200` ≈ **3800–4000 tokens** — comfortably inside one minute.
- **Two single-image calls in the same minute would total ~7600–8000 and can 413.** A 413 is
  *unservable*, never transient (A3 spent three of them discovering this). Therefore: **≥25 s
  between calls, and if both probes are used, ≥65 s.**
- Ceiling: **2 live calls.** Do not retry a successful probe to get a nicer answer.

### Expected outcomes (all valid)

- **Candidate SPARK** — a way to say *the pattern is the structure* that is neither a region (the
  pattern has no single extent — it is the whole wall and also every tile) nor a `field` (which
  carries an area, not a rhythm). Plausibly the sharpest test yet of whether Ground types can hold a
  claim about **rhythm and repetition** rather than about a bounded thing.
- **Existing construct sufficient** — **check this seriously and first.** A `field` ground over the
  revetment plus a `relation` between panels may already say everything true here. A2's most useful
  finding was exactly this shape, and A3 was required to make the same check. Do not propose anything
  new until `field` and `relation` have been argued against explicitly in `score.md`.
- **Stall** — if "organises" cannot be evidenced without importing architectural theory. Honest and
  expected-adjacent: R8's failure mode is answering about *depicted content* instead of surface, and
  on this fixture there is barely any depicted content to escape into, so a stall here would be
  informative rather than a null.
- **Refusal** — unprompted only. If the model refuses to say what organises the composition, that is
  a result; **never re-prompt it into compliance.**
- **Anthropomorphism watch (mandatory to record either way).** Record verbatim whether the model
  supplies a face, an eye, a gaze, or any figure for this aniconic wall. Record it as an
  observation whether present or absent — an absence is the evidence that bounds spark-06, and an
  absence recorded only implicitly is worthless.

### Data safety checks (pre- and post-run)

1. Record pre-state for `695be784a9ea58f1b6aef5ec`: counts of `region_annotations`, `grounds`,
   `percepts`, `text_blocks`, region ids (empty), `region_embeddings` (0), `vision_runs` (0).
   Verified today: **all zero.**
2. Read-only access only. Download the image to `fixtures/005-surface-becoming-structure/` and hash
   it (sha256 recorded in the manifest); freeze the original unmodified.
3. Re-verify post-run and diff against pre-state. Any non-zero delta is a stop condition.
4. **Do not dissect.** This post has 0 regions and A4 does not need any. Running SAM2/SegFormer to
   "give it regions" would be a corpus mutation and is out of scope (batch plan: heavy local models
   only with per-rehearsal approval, and A4 does not request it).
5. Do not repair the detached grounds on `695be786` / `695be794`. Neither is involved here.
6. Freeze all observations; prove REPLAY makes **0 adapter / model / socket calls**.
7. Validate `manifest.yaml`, `trace.json`, observations and `instrumented-score.json` against the R1
   schemas; R1 test suite stays green.
8. Record provider, model, latency, token usage and `finish_reason` for every live call, plus
   **whether any downscale was applied** (expected: none).

### Not in scope for A4

No production entity, route, collection, schema or frontend surface. No Passage, Inquiry, Discovery,
Embodiment, Atlas, Codex, Scheduler. No candidate graduation — **SPARK only**. No dissection, no
embedding backfill, no corpus expansion. No repair of detached grounds. A5 and A6 not started.

---

## 4. A6 — the decisions the orchestrator must make before it is runnable

S4 listed three. Visual verification adds two more, and changes the recommended answer to one of
S4's. **All five must be answered before A6 is scheduled.**

### D1. How are the two compared regions authored and presented?

*Options.* (a) Curator-drawn boxes declared in the manifest, full images sent, coordinates described
in the prompt. (b) The two regions **cropped to their own fixture images** and sent as the only two
images, with the boxes still declared in the manifest for provenance. (c) Full images, no boxes, ask
about "the circular motif in each."

**Recommendation: (b), with (a)'s manifest record kept.** My visual check is decisive here: both
Pair-1 images are figure-dominated (a dancing Nataraja; a Madonna and Child plus five saints filling
the lower half of the Duomo frame), and `695be815` contains a suspended angel sculpture. A3 proved
the model answers about whatever figure is in the frame. Option (a) asks the model to attend to a
sub-area it cannot see marked, and (c) invites it to pick its own. Cropping is the only way to make
the *motif* the subject. **New obligation this creates:** a crop is a new reproduction event —
record `reproduction_vs_depiction: depiction` **plus** `crop_provenance` (parent post id, box in
normalised coords, `actor: curator`, crop sha256) per image, and state plainly that the boxes are
**authored and never written to Mongo**.

### D2. May the false analogy be stated in the prompt at all?

*Options.* (a) State it, as the batch plan originally specified. (b) Never state it; ask only *"what,
in each image, would have to be true for these to be the same motif?"* (c) **Two stage:** an
unprompted call first, then a second call that states the analogy, and measure the delta.

**Recommendation: (c) if three live calls are affordable, else (b).** spark-06 makes (a) invalid on
its own — a model that invents eyes in windows will accept an offered analogy, so (a) measures
suggestibility while claiming to measure judgement. But (b) discards the most interesting
measurement available: **the difference between what the model says unprompted and what it says once
tempted** is precisely the quantity A6 exists to find, and (c) is the only design that yields it
while preserving an untainted baseline. Note (c) costs 2 image-bearing calls plus one text-only
follow-up; see D5.

### D3. Is the cultural-difference metadata supplied, or withheld?

*Options.* (a) Supply both attributions as curator facts (Chola Shaiva bronze; Italian Gothic
Christian façade) and require any refusal to cite them. (b) Withhold, and observe whether the model
invents attributions.

**Recommendation: (a) — amendment §8 is binding**: the model may not declare two objects unrelated
without evidence, and letting it invent attributions would produce exactly the iconographic overreach
A3 withheld. **But add a cheap piece of (b) inside stage 1 of D2:** before supplying the facts, ask
what the images do and do not let one say about origin. That records the invention tendency without
ever licensing an invented attribution to stand as evidence.

### D4 *(new — from visual verification)*. Which pair?

*Options.* Pair 1 `695be6bc` × `695be803` (Nataraja shadow × Duomo rose window); Pair 2 `695be8ec` ×
`695be815` (muqarnas × Gothic vault); Pair 3 `695be7e4` × `695be88e` (nimbus × sunburst).

**Recommendation: Pair 2, with Pair 1 reserved as the sequence-inversion partner** — a reversal of
S4's ordering, on evidence S4 did not have. Pair 1's rhyme is weaker than S4 believed (an
arch-shaped, figure-centred *shadow* against a true 24-fold radial oculus), both frames are
figure-dominated, and the luminance gap is extreme (mean 39.3 vs 136.4, with 75.8 % of the Nataraja
image below luminance 64) — at any downscale the shadow may not be legible at all, and A3 already
recorded one mis-description caused by downscaling. Pair 2 is the genuinely seductive rhyme: two
upward views, both radial, both jewel-toned, closely matched in tone (lum 92.3 vs 72.7; sat 0.376 vs
0.479). S4 flagged that this makes Pair 2 more susceptible to F6's colour/material bias — **that is
the feature**, not the confound: A6 is supposed to offer an analogy that similarity itself would
endorse, so that a refusal means something. A refusal against Pair 1 would be cheap.
*Contingent on:* A4 taking `695be784`, which frees `695be8ec`. Both Pair-2 crops must exclude
`695be815`'s suspended figure. **Pair 3 stays available only if A5 uses `695be817…5fa`.**

### D5 *(new)*. What is A6's call budget, and does it have a third image?

A6 is the only two-image rehearsal left, and D2(c) wants a third call. At ~2400 tokens per image
against 8000 TPM: two images + prompt ≈ 5200–5600, leaving `max_tokens` ≈ 700–900. A **third image
would push a single call to ~7200 and force `max_tokens` back to A3's cramped ~380** — reproducing
the exact budget artifact A3's critique named.

**Recommendation:** **no third image; no negative in A6.** Budget **3 live calls**: (1) both crops,
unprompted, `max_tokens ≈ 800`; (2) the same two crops with the analogy stated and the curator
attributions supplied, `max_tokens ≈ 800`; (3) reserved, used only on a provider failure.
**Throttle 65–75 s before every image-bearing call** (two images per call ≈ 5600 tokens; two such
calls inside one minute would 413, and 413 is unservable, not retryable). Record
`source_condition: misleading` and `image_order` explicitly.

**A6 remains BLOCKED until D1–D5 are answered in writing.** It is blocked on decisions, not on data
— every candidate is annotation-clean and verified.

---

## 5. Fixture reuse ledger (re-verified, with one new conflict)

| run / row | post(s) | status |
|---|---|---|
| `002-figure-ground-reversal` (A1) | `695be6c9a9ea58f1b6aef5e0` | **spent** |
| `002F-single-object-followup` | `695be77ea9ea58f1b6aef5eb` (Pietà) | **spent** — blocks A5 as originally written |
| `003-sensory-disagreement` (A2) | `695be786a9ea58f1b6aef5ed` | **spent** · carries 2 detached grounds |
| `004-gesture-and-address` (A3) | `695be8baa9ea58f1b6aef609`, `695be790a9ea58f1b6aef5ef`, `695be843a9ea58f1b6aef5ff` | **spent** |
| A4 as written | `6a5b91ecbf74ef485d00399f` | withdrawn — figurative, mislabelled |
| **A4 recommended** | **`695be784a9ea58f1b6aef5ec`** | **free, clean, verified** |
| A4 alternate | `695be8eca9ea58f1b6aef60b` | free — **reserve for A6 Pair 2; do not spend on A4** |
| **A5 recommended** | **`695be817a9ea58f1b6aef5fa`** | **free, clean, verified** · `…5fb` is a byte-identical duplicate; pin the full id |
| A5 alternate | `695be88ea9ea58f1b6aef602` | free — **reserve for A6 Pair 3** |
| ~~A5 alternate~~ | ~~`695be78fa9ea58f1b6aef5ee`~~ | **NEW CONFLICT — withdraw.** Same tweet (`G92Zow*`) and evidently the same sculpture as A3's committed neighbour `695be790` |
| A5 alternate | `695be8bea9ea58f1b6aef60a` | excluded — carries 1 `frame` ground |
| A6 Pair 1 | `695be6bca9ea58f1b6aef5df` × `695be803a9ea58f1b6aef5f8` | free — demoted to reserve (see D4) |
| **A6 Pair 2 (recommended)** | `695be8eca9ea58f1b6aef60b` × `695be815a9ea58f1b6aef5f9` | free, contingent on A4 taking `695be784` |
| A6 Pair 3 | `695be7e4a9ea58f1b6aef5f5` × `695be88ea9ea58f1b6aef602` | free, contingent on A5 taking `695be817…5fa` |
| excluded corpus-wide | `695be794a9ea58f1b6aef5f1` | 2 detached grounds; do not use |

**Under this directive's recommendations every double-booking S4 flagged is resolved**, and A4, A5
and A6 can each take a distinct, clean, verified fixture set.

### Detached grounds
Re-confirmed against S4's sweep: only `695be786a9ea58f1b6aef5ed` (2) and `695be794a9ea58f1b6aef5f1`
(2) carry detached grounds, both already flagged `detached: true` in situ. **None of A4's, A5's or
A6's recommended fixtures has a ground of any kind** — they have zero grounds, zero percepts, zero
regions, zero embeddings and zero vision_runs. Repair remains out of scope.

---

## 6. Standing amendments carried into every remaining R2 run

1. **Never name a refusal token** in any prompt. Extended by this directive: **never pose the seed as
   a yes/no question either**, and never name the candidate answer inside the question.
2. **Record `reproduction_vs_depiction` per image**, not per run — plus crop provenance where a
   region is cropped out of a parent image (A6).
3. **Token budget is a design constraint, not a footnote.** ~2400 tokens per image regardless of
   pixel size, 8000 TPM ceiling. One image ⇒ `max_tokens` may be generous; two ⇒ ~800; three ⇒ ~380
   and a degraded answer. **413 is unservable and consumes no tokens; 429 is transient; 403 with
   `error code: 1010` is a Cloudflare agent ban.** Throttle ≥25 s between single-image calls and
   65–75 s before any multi-image call.
4. **No fixture description may cite a domain label, region label or tag as evidence of what an
   image is.** Only a look counts. Five portfolio rows have now failed this test.
5. **Record anthropomorphism explicitly, present or absent**, in every remaining run. spark-06 is n=1
   and only systematic recording will move it.
6. **Check whether an existing construct suffices before proposing anything** — `field`, `relation`,
   `frame` — and argue against them in writing. SPARK only; no graduation.

---

## 7. Summary of what this directive asks the orchestrator to approve

1. **Withdraw** `6a5b91ec` from A4; **substitute `695be784a9ea58f1b6aef5ec`**.
2. **Withdraw** `695be77e` from A5 (spent) and **`695be78f` (new conflict)**; **substitute
   `695be817a9ea58f1b6aef5fa`**, full id pinned, `…5fb` recorded as a duplicate.
3. **Amend the A4 seed** from a yes/no form to *"what organises this composition, and what in the
   picture is the evidence for it?"*
4. **Run A4 next** as `005-surface-becoming-structure`, single image, native resolution, 2-call
   ceiling. Then A5. A6 last.
5. **Answer D1–D5** before A6 is scheduled; adopt Pair 2 over Pair 1 unless a reason is recorded.
6. **Amend the A5 authored sentence** to end in *rotunda* (not *nave*), and do not describe the
   entablature element as a *lunette* — it is an inscribed circular medallion.

**Nothing above has been executed. This is a draft for review.**
