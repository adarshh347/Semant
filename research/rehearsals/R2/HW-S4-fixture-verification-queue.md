# HW-S4 — Fixture verification queue (A4, A5, A6)

**READ-ONLY verification. No rehearsal was executed. No model calls of any kind were made — zero
VLM, zero LLM, zero Groq, zero OpenRouter. No database document was mutated; only `find` queries
were issued. No source code was edited, and nothing was staged, committed or pushed.**

Method: every fixture was resolved to a full ObjectId, its image downloaded to a scratchpad, and
**looked at**. Region labels, `domain_profile`, and tags were read *afterwards*, and only to explain
where the portfolio's wrong descriptions came from. A 127-post contact sheet was built to survey
substitution candidates.

---

## Headline: the pattern holds — this is the fourth and fifth wrong description

A1 ("five-sculpture collage" → composite comparative plate), A2 ("architecture" → carved stone
figure close-up), A3 ("garment" → oil painting) were each wrong because the description was
inherited from a detector. **A4 is wrong for exactly the same reason, and A5 is right about the
subject but wrong about the fixture's availability.** Post `6a5b91ec` carries
`domain_profile = {label: "painting", score: 0.9837}` — that classifier score is the entire origin
of the portfolio's "abstract painting `6a5b91ec`". The image is not a painting and is not abstract.

**Standing rule to add to the batch plan: no fixture row may cite a domain label, a region label, or
a tag as evidence of what an image is. Only a look at the image counts.**

---

## Prefix hazard found while resolving ids

The portfolio addresses fixtures by 7–8 hex prefixes. One of them is **ambiguous**:

- `695be817` resolves to **two** posts — `695be817a9ea58f1b6aef5fa` and `695be817a9ea58f1b6aef5fb`
  — which share an *identical* `source_url` (`…G90kiVxaQAAHqt_`). They are duplicate imports of the
  same photograph. Any run naming `695be817` must give the full 24-hex id.

All other prefixes used here resolve uniquely. Corpus size confirmed: **127 posts**.

---

## A4 — R8 Surface Becoming Structure · fixture `6a5b91ecbf74ef485d00399f`

### Actual visual type
A **photograph of a sheet of drawing paper**, held by a black bulldog clip, shot obliquely in warm
low tungsten light. On the paper are **graphite pencil drawings**: a bride in a jewelled *maang
tikka* and veil holding a vessel, and, upper right, a dancer with arms outstretched. A second sheet
is visible behind. `source_url` is `instagram.com/p/DVB1hLCExUv/?img_index=1`; the only tag is
`carousel`.

Corpus context established by the contact sheet: **roughly eighty of the 127 posts (the whole
`6a5b…` range) are the artist's own sketchbook practice archive** — desk photographs of graphite
figure drawings under warm lamp light. `6a5b91ec` is one of these. It is not an isolated
mislabelling; the portfolio drew a "non-figurative abstract painting" out of a personal drawing
archive.

### Portfolio verdict: **WRONG**
Wrong on medium (photograph of a pencil drawing, not a painting), wrong on the one property the row
*must* have (it is **densely figurative** — two rendered human faces and figures dominate the
frame), and wrong on provenance (an Instagram carousel frame of the vault owner's own practice, not
a work of art). The row's alternative — "or authored textile fixture" — remains open and is now the
governing option.

### Source-gesture fit
The seed *"does the surface pattern organise the composition?"* **does not work on this image.**
There is a defensible surface reading — the raking light across the paper's tooth, graphite
hatching direction, the oblique picture plane — but the composition is organised by **two drawn
faces**, which will capture any probe. Worse, a VLM asked about "surface pattern" here will almost
certainly answer about the *depicted sari and veil textiles inside the drawings*, i.e. about
depicted content, not about surface. That collapses R8 into R8's failure mode before the rehearsal
starts, and it forfeits the portfolio's only **non-figurative** slot, breaking the R0 coverage
check.

### Current annotation state
`region_annotations`: **1** (`seg_0`, `label: null`, detector `sam2`) · `grounds`: **0** ·
`percepts`: **0** · `text_blocks`: **0** · region embeddings: **3**.
**Detached grounds: none** (no grounds exist).

### Amendments needed & readiness
**NEEDS SUBSTITUTION.**

Recommended primary substitute: **`695be784a9ea58f1b6aef5ec`** — a photograph of a Persianate /
Mughal tiled architectural interior: an all-over turquoise faience revetment across a wall, a
pointed-arch niche, two flanking blind arches, framed panels with medallions, and a dado of small
repeating tiles. It is **aniconic — genuinely non-figurative**, and it is the one image in the
corpus where the seed question is literally the subject: the tile grid, the panel borders and the
arch profiles *are* the compositional structure, so "does the surface pattern organise the
composition?" has a real, evidenceable answer either way. Reproduction status: **depiction**
(photograph of a building), unambiguous.

Strong alternative: **`695be8eca9ea58f1b6aef60b`** — an upward view into a gilded **muqarnas** vault
under a tiled iwan. Muqarnas is the paradigm case of the R8 family: ornament that is doing
structural-looking work while carrying no load. If the batch wants R8 at its sharpest rather than
its cleanest, this is the better subject; `695be784` is the safer one because the surface is flat
and the evidence is unambiguous.

Both substitutes have **0 regions, 0 grounds, 0 percepts, 0 embeddings** — a completely clean
fixture, no detached-ground risk, no re-dissection risk. Neither has been used by any prior run.
Record `reproduction_vs_depiction: depiction` per image and note in `source_notes` that the subject
is architecture photographed in situ.

---

## A5 — R9 Narrative Overreach · fixture `695be77` → `695be77ea9ea58f1b6aef5eb`

### Resolution and the conflict
`695be77` resolves **uniquely** to `695be77ea9ea58f1b6aef5eb`. That is **exactly** the post recorded
as the fixture of `runs/002F-single-object-followup/manifest.yaml`
(`source_post_id: "695be77ea9ea58f1b6aef5eb"`), and the frozen fixture image
`fixtures/002F-pieta-single-object/pieta-in-situ.jpg`. **The conflict in the task brief is real and
confirmed.**

### Actual visual type
Michelangelo's **Pietà seen in situ** in its chapel in St Peter's: the marble group on a moulded
plinth over a red-marble altar front, a large inlaid cross on the wall behind, "INRI" on the
entablature above, two small wall lamps, and stepped balustrade and candlesticks in the foreground.
A shaft of light falls from upper left onto the Virgin's head.

One nuance the portfolio does not record and which matters for R9: **the image is heavily
post-processed.** A grain/texture layer is blended over the entire frame, so the chapel walls read
as mottled and painterly rather than as clean architecture. It is a *treated* photograph of a
sculpture in situ — closer to a rendered plate than to a plain record shot.

### Portfolio verdict: **PARTLY correct**
The subject identification ("Pietà, figurative") is **correct** — the first row in this portfolio
whose description survives being looked at. But the row is unusable as written, for two reasons the
portfolio does not know: (1) the fixture is already spent on 002F, and (2) the reproduction category
is a digitally treated photograph, which A1's lesson says must be recorded and which here would sit
uncomfortably next to a rehearsal about unwarranted emotional attribution.

### Source-gesture fit
The seed — reopen the image against the over-reaching sentence *"the figure's grief radiates through
the whole nave"* — **fits this image very well**, and that is precisely the problem. The frame
actually contains the surrounding architecture, so the sentence is *half* supportable: the model can
ground "the nave" in visible walls and cross. The leap to be located is only "grief radiates," not
"nave." That is a good test, but it is a good test the corpus can supply elsewhere without
confounding 002F.

**Reuse would confound the two runs.** 002F's central finding — that a named refusal token
(`NO_GROUND`) acts as an attractor and was emitted while the model simultaneously named depicted
content — was produced against this exact image. Any A5 result on the same image cannot be separated
from carry-over of that probe behaviour, and A5 is itself a stall/refusal-eligible rehearsal. The
batch would lose the ability to say whether a refusal came from the material or from the fixture.

### Current annotation state
`region_annotations`: **3** — `arch_0` (`wall`, `segformer_ade`), `arch_1` (`floor`,
`segformer_ade`), `seg_0` (`person`, `yolo`) · `grounds`: **0** · `percepts`: **0** ·
`text_blocks`: **0** · region embeddings: **8**. **Detached grounds: none.**
(Worth noting for the label-distrust file: YOLO labels the *carved marble group* `person`, and the
scene segmenter labels the chapel `wall`/`floor` — the same out-of-domain pattern that produced A2's
error.)

### Amendments needed & readiness
**NEEDS SUBSTITUTION** — not because the image is wrong, but because it is already spent.

Recommended primary substitute: **`695be817a9ea58f1b6aef5fa`** (use the full id; see the prefix
hazard above) — an *Angel of Grief* type funerary monument: a winged marble figure collapsed
face-down across the top of a tomb chest, one arm hanging, wings spread and drooping, set inside a
colonnaded rotunda with fluted columns and a painted lunette above. This is the corpus's strongest
narrative-overreach subject: grief is *conventionally* legible, the surrounding architecture is
present so the "radiates through the whole X" clause has something to bite on, and the leap from
carved posture to felt emotion is exactly the leap R9 must locate. Amend the authored sentence's
last noun from *nave* to *rotunda* (the setting is a rotunda, not a nave) so that the sentence's
only unsupported move is the emotional one — otherwise the model can refuse on the architecture and
never reach the real overreach.

Alternatives, in order: **`695be88ea9ea58f1b6aef602`** (veiled standing mourner before a gilded
radiating sunburst with an eye-in-triangle, in an arched aedicula — richer iconography, so the
overreach risk is *iconographic* as well as emotional); **`695be78fa9ea58f1b6aef5ee`** (weathered
seated mourning figure, B&W, outdoor cemetery — bare, harder, cleaner);
**`695be8bea9ea58f1b6aef60a`** (kneeling embracing pair, B&W — but this post already carries 1
`frame` ground, so it is not annotation-clean).

`695be817…5fa`, `695be88e…602` and `695be78f…5ee` all have **0 regions, 0 grounds, 0 percepts, 0
embeddings** — clean, unconfounded, unused by any prior run. **Do not use `695be790` or `695be843`**
(committed to A3) and **do not use `695be794`** (carries 2 detached grounds; see below).

---

## A6 — R12 Adversarial Projection · no posts named by the portfolio

### Portfolio verdict: **not a description, so not wrong — but it is unbuildable as specified**
The row asks for "two visually similar but culturally unrelated **regions**." Surveying all 127
posts: **only 10 posts carry any `region_annotations` at all**, and every one of those regions is
either a body/scene label (`person`, `wall`, `floor`, `hair`, `face`), a clothing label from the
fashion segmenter, or an unlabelled SAM2 blob. **There is not a single ornament or motif region
anywhere in the corpus**, on any pair of culturally distinct objects. The only motif-level regions
that exist are the crown/face regions on `695be6c9` — and that post is spent on A1, and its five
heads are all South Asian, i.e. not "culturally unrelated."

So A6 cannot be assembled from existing region evidence. Its regions must be **authored** —
curator-drawn boxes carried in the run manifest with explicit provenance, **never written to
Mongo** (the batch's hard non-scope forbids production mutation, and R0 already sanctions authored
fixture data with provenance).

### Recommended candidate pairs (from the full 127-post contact sheet)

**Pair 1 — strongest, and thematically self-aware.**
`695be6bca9ea58f1b6aef5df` × `695be803a9ea58f1b6aef5f8`.
The first is a small gilt-bronze **Nataraja** on a plinth, lit so that its *prabhamandala* (flaming
arch) throws a vast circular flame-ringed **shadow** across a rough stone wall. The second is the
**rose window** of the Florence Duomo façade — a radial Gothic oculus of stone tracery ringed by
inlaid marble and flanked by saints in niches. Two circular radiating motifs; Chola Shaiva bronze
vs. Italian Gothic Christian architecture; no historical contact.
Seductive false analogy to supply: *"the ring of fire and the rose window are the same cosmic wheel
— both diagram the turning of the world around a still centre."*
The bonus: in the R12 image the circle is **a projection, not the object** — the motif being
compared is literally a shadow cast on a wall. For a rehearsal named *Adversarial Projection* that
is an unusually apt piece of evidence, and it gives the refusal something concrete to name.

**Pair 2 — cleanest visual rhyme.**
`695be8eca9ea58f1b6aef60b` × `695be815a9ea58f1b6aef5f9`.
A gilded **muqarnas vault** under a tiled Persianate iwan vs. the **Sainte-Chapelle-type Gothic
vault** shot straight up, ribs radiating into jewelled stained glass. Both are upward views, both
radially organised, both saturated and jewel-toned. Safavid/Persianate Islamic vs. French Gothic
Christian. False analogy: *"both are the vault of heaven; the same motif rendered in tile and in
glass."* Note this pair is *more* susceptible to F6's colour/material bias — which is either a
feature (it stresses the exact failure mode) or a confound, depending on what A6 wants to prove.

**Pair 3 — the "halo" trap.**
`695be7e4a9ea58f1b6aef5f5` (gilded Hindu deity in profile, hand in *abhaya*, before a large plain
gold nimbus disc) × `695be88ea9ea58f1b6aef602` (veiled Christian mourner before a gilded radiating
sunburst with an eye in a triangle). Two golden radiances behind two sacred figures.
False analogy: *"the aureole and the glory are one motif — divine light behind the holy body."*
Caveat: `695be88e` is also the second-choice A5 substitute; do not commit it to both.

If only one pair is run, **use Pair 1.** Reserve Pair 2 as the sequence-inversion / repeat partner.

### Current annotation state (all A6 candidates)
`695be6bc…5df`, `695be803…5f8`, `695be8ec…60b`, `695be815…5f9`, `695be7e4…5f5`, `695be88e…602`:
**0 `region_annotations`, 0 `grounds`, 0 `percepts`, 0 `text_blocks`, 0 region embeddings** — every
one. No detached grounds anywhere. Completely clean, and completely empty.

### Amendments needed & readiness
**NEEDS SUBSTITUTION (posts must be named for the first time) — and it is CONDITIONALLY BLOCKED
until three things are decided:**

1. **Authored regions.** Two curator-drawn boxes must be defined in the manifest with provenance
   (`actor: curator`, authored, not persisted). Without this A6 has no regions and no comparison.
2. **Curator-supplied cultural-difference metadata**, per amendment §8 — the model may not declare
   two objects unrelated without evidence. Provide the two attributions (Chola Shaiva bronze; Italian
   Gothic Christian façade) as curator facts in the manifest, and require the refusal to cite them.
3. **Amendment 1 compliance** — the seed *"are these the same motif?"* is a yes/no question, and a
   named refusal option must not appear anywhere in the prompt. Ask for the evidence in each region
   and let a refusal be unprompted, as A1's probe 1 was. A yes/no framing is itself an attractor;
   consider rephrasing to *"what, in each region, would have to be true for these to be the same
   motif?"*

Also record `image_order` and `source_condition: misleading` explicitly, and
`reproduction_vs_depiction: depiction` per image (both pairs are photographs of objects/buildings).

---

## Fixture reuse ledger (cross-checked against `runs/*/manifest.yaml`)

| run | post(s) | status |
|---|---|---|
| `002-figure-ground-reversal` (A1) | `695be6c9a9ea58f1b6aef5e0` | spent |
| `002F-single-object-followup` | `695be77ea9ea58f1b6aef5eb` | spent — **collides with A5 as written** |
| `003-sensory-disagreement` (A2) | `695be786a9ea58f1b6aef5ed` | spent |
| `004-gesture-and-address` (A3, prepared) | `695be8baa9ea58f1b6aef609`, `695be790a9ea58f1b6aef5ef`, `695be843a9ea58f1b6aef5ff` | committed |
| A4 as written | `6a5b91ecbf74ef485d00399f` | no reuse conflict — but wrong image |
| A4 proposed | `695be784a9ea58f1b6aef5ec` (alt `695be8ec…60b`) | free |
| A5 proposed | `695be817a9ea58f1b6aef5fa` (alt `695be88e…602`, `695be78f…5ee`) | free |
| A6 proposed | `695be6bc…5df` + `695be803…5f8` (alt pair `695be8ec…60b` + `695be815…5f9`) | free — but `695be8ec` and `695be88e` each appear in two proposals; pick once |

## Corpus-wide detached-ground state (read-only sweep, all 127 posts)

A `region`-type ground whose `region_id` is absent from its post's region ids:

| post | detached ground ids | already flagged in the document? |
|---|---|---|
| `695be786a9ea58f1b6aef5ed` | `gnd_mrqp8tls_0` (`hair` → `fine_3`), `gnd_mrqp8tlt_1` (`face` → `fine_0`) | yes — `detached: true`, reason "region evidence absent after recovery" |
| `695be794a9ea58f1b6aef5f1` | `gnd_mrphxkl1_0`, `gnd_mrpi0b4o_2` | yes — same flag |

**No other post in the corpus has a detached ground, and none of the A4/A5/A6 fixtures or proposed
substitutes has one.** Both affected posts are excluded from all A4–A6 proposals, so nothing here
needs repair (and repair remains out of scope regardless).

## Readiness summary

| row | actual visual type | portfolio verdict | readiness |
|---|---|---|---|
| **A4** | photograph of graphite drawings on a clipped sheet, warm lamplight; figurative | **WRONG** (domain classifier said "painting" 0.9837) | **NEEDS SUBSTITUTION** → `695be784a9ea58f1b6aef5ec` |
| **A5** | digitally textured photograph of Michelangelo's Pietà in situ, St Peter's | **PARTLY correct** (subject right; fixture already spent, treatment unrecorded) | **NEEDS SUBSTITUTION** → `695be817a9ea58f1b6aef5fa`, sentence amended *nave → rotunda* |
| **A6** | n/a — no posts were ever named | not a description; **unbuildable as specified** (no motif regions exist in the corpus) | **BLOCKED** pending authored regions + curator cultural metadata + non-yes/no seed; candidate pairs proposed |

None of A4, A5 or A6 is ready to run as written. **A4 and A5 become READY once the substitutions
above are accepted** — both proposed subjects are annotation-clean and unused. **A6 stays blocked on
a decision, not on data.**
