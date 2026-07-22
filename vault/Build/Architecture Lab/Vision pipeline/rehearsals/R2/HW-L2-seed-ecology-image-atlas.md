# HW-L2 — Seed Ecology Image Atlas

**READ-ONLY inventory. Every classification below was made by LOOKING at the image (contact
sheets rendered and viewed, plus targeted zooms). No model calls, no VLM, no LLM, no writes to
Mongo, no source edits. Detector/region labels were deliberately ignored.**

Lane 2 of the 6-lane cycle. Corpus: 127 posts in `post_collection`, all images fetched
successfully (127/127) and viewed as 6 contact sheets + 2 zoom sheets.

---

## 0. Shape of the corpus (verified)

| block | count | what it actually is |
|---|---|---|
| `695be…` | 45 | curated art/architecture reference images (the real fixture pool) |
| `6a5ac…` | 2 | Mona Lisa; Trevi Fountain detail |
| `6a5b9013` | 1 | photo of a *wall/table grid of pencil sketchbook pages* (the archive's own cover shot) |
| `6a5b…` (rest) | 79 | **the vault owner's own sketchbook archive** — CONFIRMED by looking |

The ~80-post `6a5b` claim is **true**. Every one of those 79 images is a warm-lamp-lit
photograph of an open sketchbook / spiral pad on a cluttered desk (brass lamps, candles, pencil
cups, an iPad, an owl figurine, Kashmiri lacquer trays). Content is graphite/charcoal portrait
and figure study — Indian mythological/period faces, jewellery, crowns, drapery, anatomy plates,
Loomis head construction, ellipse drills. Several carry burned-in Instagram tutorial captions
("Cover the entire shadow shape", "focus on working with shapes"). They are teaching-carousel
frames, not reference art.

**Provenance duplication:** the 79 sketchbook posts come from only **10 Instagram carousel URLs**
(`source_url` repeated 3–12 times each). They are same-session, same-lighting, same-subject
siblings. Not byte-identical, but as fixtures they are near-redundant.

**Byte-identical duplicate found (1 pair):**
`695be817a9ea58f1b6aef5fa` == `695be817a9ea58f1b6aef5fb` — md5 `b313b891754ecb85b95cda60b688cf0e`,
same `source_url` (`pbs.twimg.com/media/G90kiVxaQAAHqt_`). Image: *Angel of Grief* slumped over a
tomb chest inside a colonnade. **Use only one; the other must be excluded from any sampling
frame.** This is the same failure that already bit the program once.

**Annotation state overall:** only 11 posts carry any grounds; only 8 carry any percepts-or-more.
Regions exist on 9 posts total (and 4 stray regions scattered across 4 sketchbook posts). 116 of
127 posts are entirely unannotated. Grounds exist on 4 *sketchbook* posts (`6a5b9059`,
`6a5b922b`, `6a5b923e`, `6a5b9273`) — those are almost certainly noise and should not be read as
signal.

**Fixtures already committed / in flight (do not reassign):**
`695be6c9` (002), `695be77e` (002F), `695be786` (003), `695be8ba` + `695be790` + `695be843` (004),
`695be784` (A4, running now).

Notation below: `(regions/grounds/percepts)`.

---

## 1. architecture

**Available repo examples**
- `695be720` — modern sandstone monumental gateway (torana-style) over a wet granite plaza, heavy cloud. (0/0/0)
- `695be724` — domed stupa-like monument facade, stepped plinth, two tiny human figures at the base giving scale. (0/0/0)
- `695be72c` — night panorama of a monumental park: colonnade of pillars, multiple domes, reflecting water, storm-blue sky. (0/0/0)
- `695be803` — Florence Duomo facade detail: rose window, polychrome marble banding, saints in niches. (0/0/0)
- `695be815` — fisheye up-view into a gothic vault, ribs converging, stained glass. (0/0/0)
- `695be82d` — up-view into a domed interior with a marble sculpture group in the foreground and blue skylights. (0/0/0)
- `695be896` — St Peter's dome behind Ponte Sant'Angelo at dusk, bridge statues in silhouette. (0/0/0)
- `695be843` — dark inverted-ziggurat megastructure, lamp clusters on its flanks, no figure anywhere. (0/0/0) *[in 004]*
- `695be84d` — old B/W photo of an ornate carved pillar standing in situ. (0/0/0)
- `695be7f5` — woodblock/anime print: Japanese street seen from above, blue tiled roofs, raking light. (0/0/0)

**Missing the user should bring**
- A *plan-and-elevation-free ordinary building*: a housing block, a stairwell, a corridor — something with no ceremonial charge. Every architectural image here is a monument, which biases the model toward reverent language before it has looked.
- A **building under construction or scaffolded** — architecture caught mid-becoming, so the model cannot fall back on "completed masterpiece" framing.
- An **interior with people using it** (station concourse, market hall). Right now architecture and crowd never co-occur.

**Supports** R1 Open Constellation, R8 Surface Becoming Structure, R12 Adversarial Projection, R4 (vault/void).

**Hallucination risks — HIGH.** This is the single most exposed family. `695be843` is the
recorded case: a figureless metal/concrete structure that the model read as having "windows that
function as eyes… a confrontational gaze". The corpus makes it worse — bilaterally symmetric
facades (`695be724`, `695be803`, `695be843`, `695be8ec`) are exactly the stimulus that triggers
face-pareidolia. Second risk is **source overreach**: the model will want to name buildings
("St Peter's", "the Duomo") and then import art-historical narrative it did not see.

**Verdict: READY NOW** — and it should be run *early*, because it is the family that already
produced a documented failure and the evidence is sitting in the repo.

---

## 2. sculpture

The corpus's overwhelming centre of gravity. ~25 of the 47 non-sketchbook posts are sculpture.

**Available repo examples**
- `695be6bc` — small gilt bronze Nataraja on a blue plinth, lit so it throws a huge black shadow of itself onto a rough stone wall. (0/0/0)
- `695be6d3` — dancing female figure in a museum vitrine, dark gallery, glass reflections. (0/0/0)
- `695be6d9` — dark stone stele, seated deity ringed by attendants, on a black plinth. (0/0/0)
- `695be6fe` — sandstone torso with halo/nimbus on a museum plinth, plain lilac ground. (0/0/0)
- `695be70c` — two standing bronze figures cut out on pure white, catalogue style. (0/0/0)
- `695be7cd` — three veiled marble figures under a carved floral wreath, cropped so the veils dominate. (0/0/0)
- `695be7e4` — gilt/painted deity holding a disc against a gold nimbus, tight crop. (0/0/0)
- `695be8ab` — Winged Victory of Samothrace on the Louvre stair. (0/0/0)
- `695be8b0` — B/W reclining ecstatic figure pierced by an arrow, cloth cascading, black ground. (1/6/2)
- `695be8b3` — dense baroque relief panel packed with small figures and ornament. (0/0/0)
- `695be8b7` — a large angel wing arched over a reclining tomb figure, very low key. (0/0/0)
- `695be8be` — B/W: kneeling man cradling a slumped body. (0/1/0)
- `695be8a0` — chiaroscuro winged putto head emerging from black. (0/0/0)
- `695be84f` — contemporary sculpture: a female figure dissolving/glitching into stacked cubes. (0/0/0)
- `6a5ac932` — Trevi Fountain figure group detail. (0/0/0)
- plus the cemetery cluster (see *ruin/decay*) and the taken fixtures `695be6c9`, `695be786`, `695be790`.

**Missing the user should bring**
- **Abstract / non-figurative sculpture** (Brancusi, Chillida, a Richard Serra plate). There is not one. Every sculpture here has a body in it, so R4 and R12 can never be tested against sculpture-without-a-face.
- **A sculpture from behind, or a fragment with no head.** Almost every crop here privileges a face.
- A **sculpture in a non-reverent setting** — a park bench statue, a shop mannequin, a garden gnome. The corpus is uniformly museum/church/cemetery, which pre-loads solemnity.

**Supports** R1, R2 Sensitisation-and-Return, R7 Gesture and Address, R8, R9 Narrative Overreach.

**Hallucination risks — HIGH but of a different kind.** Not pareidolia; **emotional narration**.
`695be8b0` and the cemetery heads invite the model to assert grief, ecstasy, longing as if
observed. Also strong **iconographic overreach**: it will name Nataraja, Victory, Bernini and then
narrate provenance. And the R0 record already shows region labels on carved stone come back as
`wall`/`floor` — so region evidence in this family is actively untrustworthy, not merely thin.

**Verdict: READY NOW.** Deepest, best-lit, most varied family in the repo.

---

## 3. painting

**Available repo examples**
- `6a5ac8ca` — the Mona Lisa. (0/0/0)
- `695be8ba` — oil painting detail: a neck and shoulder above a black fur-and-lace collar. (16/1/0) *[004 — the fixture whose regions said `dress`/`scarf`/`tie knot`]*
- `695be6ea` — colonial-era sepia aquatint of a rock-cut temple courtyard with a carved elephant. (0/0/0)
- `695be7fa` — old engraving on aged paper: a deity seated on a coiled serpent. (1/0/0)
- `695be7e0` — watercolour manga illustration, a couple reclining on a bed with a cake plate. (0/0/0)
- `695be822` — digital illustration: a colossal enthroned Athena in a hypostyle hall, two tiny worshippers on the floor. (0/0/0)
- `695be7f5` — woodblock/anime print of Japanese rooftops. (0/0/0)

**Missing the user should bring** — this family is thin and skewed.
- **A modern/abstract painting** (Rothko, Twombly, a colour field). Nothing here post-dates figurative realism.
- **An unambiguous full-canvas painting with visible brushwork and a frame**, so paint-as-material is legible. `695be8ba` is a crop; the Mona Lisa is a reproduction so canonical the model will answer from memory rather than from the pixels.
- **A painting the model cannot possibly name.** Every painting here is either famous or generic. A genuinely unknown canvas is the only way to separate looking from recall.

**Supports** R2, R5 Sensory Disagreement, R9, R12.

**Hallucination risks — SEVERE, and structurally different.** The Mona Lisa is a *recall trap*:
the model will produce an essay without looking. R0 has already recorded the inverse error —
`domain_profile` calling a pencil drawing "painting" at 0.98. So domain confidence in this family
is provably unreliable in both directions. Any painting rehearsal must be scored on whether the
description is *falsifiable from the crop*.

**Verdict: NEEDS USER-SUPPLIED MATERIAL.** Usable for one adversarial-recall rehearsal now, but
not for honest sensitisation work until an unfamous, unmistakably painted canvas exists.

---

## 4. textile / garment

**Available repo examples** — all *carved* textile; no actual cloth in the corpus.
- `695be7cd` — three veiled marble figures; the veil is the subject, the bodies are inferred through it. Outstanding image. (0/0/0)
- `695be88e` — memorial figure fully shrouded in a veil inside an arched niche under a carved sunburst. (0/0/0)
- `695be8b0` — the arrow-pierced reclining figure: the cloth cascade occupies most of the frame. (1/6/2)
- `695be786` — heavy carved jewellery, girdles and beadwork on stone bodies. (7/5/2) *[003 — taken]*
- `695be8ba` — the black fur-and-lace collar in an oil painting. (16/1/0) *[004 — taken]*
- Sketchbook: dozens of drawn saris, veils, brocade blouses (e.g. `6a5b9275`, `6a5b9277`).

**Missing the user should bring — this is a real hole.**
- **An actual photograph of actual fabric**: a folded textile, a loom, a rack of clothing, a worn garment on a body. There is *zero* photographed cloth in 127 posts.
- **A flat textile with pattern but no body** — a rug, a printed length, an embroidery sample. Needed to separate "textile" from "drapery on a figure".
- **Garment as worn, casually** — a person in ordinary clothes.

**Supports** R8 (the strongest fit in the whole atlas — stone that reads as cloth), R5, R4.

**Hallucination risks — MODERATE, but a specific one.** The R0 record shows the annotator already
emits `dress` / `scarf` / `tie knot` for an oil-painting crop, i.e. it hallucinates garment
vocabulary from tonal shapes. Expect confident naming of fabric type ("silk", "linen") that no
pixel supports. Anthropomorphism risk is low here — the bodies are already present.

**Verdict: NEEDS USER-SUPPLIED MATERIAL** for textile-as-textile.
**READY NOW** narrowly for *carved drapery* (`695be7cd` is the single best unclaimed fixture in
the corpus for R8).

---

## 5. object / design

**Available repo examples — the weakest family.**
- `695be70c` — two bronze figures cut out on white; reads as catalogue/object photography even though the subject is sculpture. (0/0/0)
- `695be6bc` — the Nataraja bronze *as an object on a plinth* under a display light. (0/0/0)
- Sketchbook desk-scapes (`6a5b9069`, `6a5b9078`, `6a5b9080`) contain real designed objects — brass lanterns, an owl figurine, pencil cases, an iPad — but always incidentally, in low warm light, behind the sketchbook.

**Missing the user should bring — almost everything.**
- **A single manufactured object on a neutral ground**: a chair, a kettle, a tool, a phone. Nothing like this exists.
- **A product/packaging shot** and, separately, **a worn/used everyday object** (a scuffed shoe, a chipped mug). The contrast between design intent and use-wear is what makes this family interesting.
- **An object whose function is not guessable from its shape** — the sharpest possible test of narrative overreach.

**Supports** R9, R12, R1.

**Hallucination risks — HIGH by absence.** With no clean object fixtures, any object rehearsal
would run on sculpture-in-a-vitrine, and the model will import ritual/aesthetic register into what
should be plain description. Given `695be843`, a symmetric manufactured object is also prime
anthropomorphism bait.

**Verdict: NEEDS USER-SUPPLIED MATERIAL.** Do not attempt an object rehearsal on current stock.

---

## 6. photograph

Here "photograph" means *the photograph as the artefact* — where framing, grain, exposure and the
photographer's decision are the subject, not merely the transport.

**Available repo examples**
- `695be6df` — B/W: a sari-clad woman seated at the foot of an eroded rock-cut cliff relief. Human scale against stone; a deliberate, composed photograph. (0/0/0)
- `695be6cc` — sepia archival photograph of a rock-cut relief panel, plate-camera flatness. (0/0/0)
- `695be84d` — old B/W plate of a carved pillar in situ. (0/0/0)
- `695be78f`, `695be790`, `695be793`, `695be794` — the cemetery B/W set; strongly authored photographs (contrast, crop, bare-tree bokeh) as much as records of statues. (0/0/0 except `793` 0/1/0, `794` 1/5/0)
- `695be7db` — the glitter-silhouette: unambiguously a *made photograph*, not a record of anything. (0/0/0)
- `695be8ec` — mirrored/kaleidoscopic composite of a tiled iwan against open sky; a manipulated photograph. (0/0/0)

**Missing the user should bring**
- **A documentary/street photograph of people** — no such image exists in the corpus.
- **A snapshot**: badly framed, flash-lit, banal. Every photograph here is authored, so the model has no chance to distinguish photographic intention from photographic accident.
- **A photograph of a photograph** (a print on a table, an album page) — the reflexive case.

**Supports** R2, R5, R4, R12.

**Hallucination risks — MODERATE-HIGH, specifically *medium blindness*.** The R0 record already
has `domain_profile` mislabelling a drawing as a painting; the archival sepia plates
(`695be6cc`, `695be84d`) will very likely be read as prints or paintings. Second risk: the model
narrates the *photographer's intent* ("the artist wanted us to feel…") — source overreach with
no source.

**Verdict: READY NOW.** `695be6df` and `695be7db` are both unclaimed and excellent.

---

## 7. ritual / religious

The corpus's second dominant lens; it overlaps sculpture and architecture almost completely.

**Available repo examples**
- `695be6bc` — Nataraja bronze + its shadow (devotional object, gallery-lit). (0/0/0)
- `695be6d9` — deity stele with attendant register. (0/0/0)
- `695be7e4` — gilt deity with disc and gold nimbus. (0/0/0)
- `695be7fa` — engraving of the deity on the serpent couch. (1/0/0)
- `695be822` — colossal enthroned Athena with worshippers dwarfed at her feet. (0/0/0)
- `695be815`, `695be82d`, `695be803`, `695be896` — church interiors/exteriors. (0/0/0)
- `695be784` — the turquoise tile revetment (mosque/shrine interior). *[A4 — taken]*
- `695be77e` — Pietà in situ. *[002F — taken]*
- `695be724` — stupa-form monument. (0/0/0)

**Missing the user should bring**
- **A rite in progress, with participants** — an aarti, a procession, a congregation. Every religious image here is *empty of worshippers*, so ritual can only be inferred from architecture, never observed as action.
- **A humble/domestic shrine** — a home altar, a roadside niche. The corpus is entirely monumental, which makes "religion" and "grandeur" inseparable.
- **A religious image from a tradition the model is likely to misidentify.**

**Supports** R7 (gesture and address), R9, R12, R2.

**Hallucination risks — SEVERE, the worst for *source* overreach.** The model will confidently
assign iconography, deity names, sect, period and doctrinal meaning from silhouette alone — and
the R0 record shows that even a five-panel comparative plate of labelled heads was misread as a
"collage". Doctrinal claims here are unfalsifiable from pixels, which is exactly why the family
must be run with a hard "what did you actually see" gate.

**Verdict: READY NOW,** with a mandatory anti-attribution constraint in the prompt.

---

## 8. ruin / decay

**Available repo examples** — a genuinely strong, coherent set.
- `695be793` — B/W extreme close-up of a stone face eroded almost past recognition; features have become weather. (0/1/0)
- `695be790` — B/W weathered cemetery head, lichen bloom across the cheek. (0/0/0) *[004 — taken]*
- `695be794` — B/W cemetery statue, head thrown back, surface pitted and streaked. (1/5/0)
- `695be78f` — B/W seated draped mourner among bare winter trees, stained stone. (0/0/0)
- `695be6df` — the eroded rock-cut cliff with the seated woman. (0/0/0)
- `695be6ea` — the aquatint of the rock-cut courtyard, romanticised ruin. (0/0/0)
- `695be84d` — the isolated carved pillar, weathered, in situ. (0/0/0)
- `695be84f` — the figure dissolving into cubes: *simulated* decay, a useful control against the real thing. (0/0/0)

**Missing the user should bring**
- **Non-monumental decay**: rust, peeling paint, a rotting fence, mould on a wall. All decay here is *noble* decay on carved stone; the model has no chance to describe entropy without elegy.
- **A before/after or intact-vs-damaged pair** of the same subject.
- **Fresh damage** (a break, a crack, graffiti) as opposed to slow weathering.

**Supports** R8 (strongest fit alongside textile), R4, R2, R5.

**Hallucination risks — MODERATE-HIGH.** The eroded faces are literal pareidolia substrate: at
`695be793`'s level of erosion the model will assert expression ("anguished", "weeping") from
noise. Also strong **elegiac drift** — decay images pull the model into mourning register, which
is R9 territory. The `695be84f` control is valuable precisely because a fake dissolution should
*not* read as time.

**Verdict: READY NOW.** Second-best-provisioned family after sculpture.

---

## 9. diagram / map / plan

**Available repo examples — thin, and every one is a trap.**
- `695be6c9` — the five-head comparative plate with printed period labels (Solanki/Gupta/Pala/Amaravati/Gandhara). A genuine *diagram* of stylistic difference. (10/3/1) *[002 — taken; already misread once as a "collage"]*
- `695be82b` — Ugetsu Monogatari film title card: white brush calligraphy over an engraved landscape. Text-as-image. (0/0/0)
- `6a5b9013` — a photographed grid of many sketchbook pages: an *accidental* contact sheet. (0/0/0)
- Sketchbook instructional pages: `6a5b9076` (an annotated ribcage/spine anatomy plate), `6a5b907b` (ellipse and spine-construction drills), `6a5b9088` (a Loomis head-construction diagram with proportion guides). These are real diagrams — arguably the family's best unclaimed material.

**Missing the user should bring**
- **An actual map** (any kind) and **an actual architectural plan/section**. Neither exists.
- **A chart or schematic with a legend** — a wiring diagram, a timetable, an org chart.
- **A hybrid**: an annotated photograph, or a plan overlaid on a site view.

**Supports** R1, R5 (a diagram is a picture that refuses sensory reading), R9, R12.

**Hallucination risks — HIGH and already realised.** The 002 failure is exactly this family: the
model read a labelled comparative plate as a "collage", i.e. it treated a diagram's structure as
decorative arrangement. Expect it to **read printed labels as objects in the scene**, and to
invent legend semantics. Anthropomorphism risk is low; **structure-blindness** risk is the highest
in the atlas.

**Verdict: NEEDS USER-SUPPLIED MATERIAL** for map/plan.
Note: `6a5b9088` (Loomis head construction) is a legitimate, free diagram fixture available *now*
and is the one genuinely valuable non-sketchbook use of the sketchbook block.

---

## 10. non-figurative surface

**Available repo examples**
- `695be784` — turquoise/cobalt tile revetment, panels of geometric and vegetal tilework, no figure. (0/0/0) *[A4 — taken]*
- `695be8ec` — mirrored composite of a tiled iwan with muqarnas cells and open sky at the top; pure pattern, bilaterally doubled. (0/0/0)
- `695be843` — the megastructure: at close reading it is a field of ribs, louvres and lamp housings — a *surface*, which is why it was misread as a face. (0/0/0) *[004]*
- `695be8b3` — the baroque relief read as ornament rather than narrative (borderline: figures are present but subordinated to pattern). (0/0/0)
- `695be7cd` — the veil field, if read as folds rather than figures. (0/0/0)

**Missing the user should bring**
- **A truly subject-less surface**: concrete, water, sand, bark, a plaster wall, a stain. There is not one image in the corpus without a made object in it.
- **A repeating pattern with a break/defect in it** — the single best test of whether the model reports what is there or completes the pattern.
- **A surface at ambiguous scale** (macro texture that could be a landscape).

**Supports** R4 Figure/Ground Reversal (its natural home), R8, R5, R12.

**Hallucination risks — HIGHEST anthropomorphism exposure of all 12 families.** `695be843` is the
proof: given a figureless surface the model *manufactured* a face and a gaze. `695be8ec` is even
more dangerous — deliberate mirror symmetry is the classic pareidolia trigger. Expect invented
figures, invented centres, and invented "presence". This family is where R12 Adversarial
Projection should be aimed first.

**Verdict: NEEDS USER-SUPPLIED MATERIAL** for a *clean* non-figurative surface —
but **READY NOW** to run R12 adversarially on `695be8ec`, which is unclaimed and is the strongest
available anthropomorphism probe outside the already-used `695be843`.

---

## 11. crowd / assembly

**Available repo examples — effectively none.**
- `695be8b3` — a dense baroque relief of many carved figures. A crowd in stone, not a crowd of people. (0/0/0)
- `695be6c9` — five heads assembled on a plate; an assembly of *objects*. (10/3/1) *[taken]*
- `695be822` — an illustration with two tiny worshippers before a colossus; two people is not a crowd, but it is the only human plurality in the whole corpus. (0/0/0)
- `695be724` — two indistinct people at the base of a monument, for scale. (0/0/0)
- `695be6df` — one woman. (0/0/0)

**In 127 posts there is not a single photograph of more than two living people.**

**Missing the user should bring**
- **A photograph of an actual crowd**: a market, a platform, a protest, a procession, a queue.
- **A small assembly with visible relations** — a family group, a meeting, a class — where address and attention between people is legible.
- A crowd where **individual faces are unresolvable**, to test whether the model invents them.

**Supports** R7 (gesture and address — its natural home), R1, R9, R12.

**Hallucination risks — untestable, therefore unknown.** That is itself the risk: an entire
failure mode (inventing individual identity, intent and relation inside a mass of people) has
never been probed. Given the demonstrated tendency to invent a gaze where there is no figure, a
crowd of real but unresolved figures should be expected to produce heavy invention.

**Verdict: SHOULD WAIT.** No amount of prompt design can substitute for the missing material,
and it would be dishonest to run R7 on carved crowds and call the result a crowd finding.

---

## 12. boundary / threshold

**Available repo examples** — better than expected; the corpus is quietly rich here.
- `695be720` — a gateway standing free on a plaza: a threshold you can walk around. (0/0/0)
- `695be6bc` — the Nataraja and its shadow: object/shadow, lit/unlit, the sharpest boundary image in the corpus. (0/0/0)
- `695be7db` — the glitter silhouette: the body exists *only* as the boundary between orange field and starfield. (0/0/0)
- `695be77e` — the Pietà behind a shaft of light in near-darkness: light as threshold. *[002F — taken]*
- `695be6d3` — the vitrine: glass as a boundary, with reflections asserting it. (0/0/0)
- `695be8ec` — the tiled iwan opening to real sky: built surface meeting the actual outside. (0/0/0)
- `695be88e` — the veiled figure inside an arched niche: two nested thresholds (veil, arch). (0/0/0)
- `695be8ab` — Winged Victory at the top of a stair, i.e. placed at a transition. (0/0/0)

**Missing the user should bring**
- **A mundane threshold**: a doorway, a turnstile, a fence, a checkpoint, a border. Every threshold here is either sacred or accidental.
- **A threshold with a person crossing it**, so the boundary is enacted rather than implied.
- **A liminal edge in nature** — shoreline, treeline, horizon. There is no landscape at all in the corpus.

**Supports** R4 (the pair of `695be6bc` and `695be7db` is a near-ideal figure/ground set), R2, R8, R5.

**Hallucination risks — MODERATE.** The specific risk is **allegorical inflation**: the model
reads a doorway as "a passage between worlds" without prompting. `695be6bc` is also a shadow-
pareidolia case — the shadow is *larger and more legible* than the object, and the model may
describe the shadow's anatomy as if it were the sculpture's.

**Verdict: READY NOW.** `695be6bc` and `695be7db` are both unclaimed and are the two best R4
fixtures in the repo.

---

## Summary table

| # | family | verdict | best unclaimed fixture |
|---|---|---|---|
| 1 | architecture | **READY NOW** | `695be724`, `695be815` |
| 2 | sculpture | **READY NOW** | `695be8b0`, `695be7cd`, `695be84f` |
| 3 | painting | **NEEDS USER-SUPPLIED MATERIAL** | `695be7fa` (weak) |
| 4 | textile / garment | **NEEDS MATERIAL** (ready for *carved* drapery) | `695be7cd` |
| 5 | object / design | **NEEDS USER-SUPPLIED MATERIAL** | — none |
| 6 | photograph | **READY NOW** | `695be6df`, `695be7db` |
| 7 | ritual / religious | **READY NOW** (anti-attribution gate required) | `695be7e4`, `695be822` |
| 8 | ruin / decay | **READY NOW** | `695be793`, `695be794` |
| 9 | diagram / map / plan | **NEEDS MATERIAL** (one diagram usable now) | `6a5b9088` |
| 10 | non-figurative surface | **NEEDS MATERIAL** (R12 runnable now) | `695be8ec` |
| 11 | crowd / assembly | **SHOULD WAIT** | — none |
| 12 | boundary / threshold | **READY NOW** | `695be6bc`, `695be7db` |

Six READY NOW, five NEEDS MATERIAL, one SHOULD WAIT.

---

## The single most important gap

**A photograph of ordinary people in ordinary space — a street, a platform, a market, a room with
three or more people in it, taken without artistic intent.**

One such image would unlock more than any other single addition, for four converging reasons:

1. It is the **only** way to run R7 Gesture and Address honestly. Gesture between living people is
   the family's whole subject and the corpus contains zero instances of it.
2. It fills **crowd/assembly** outright (currently the only SHOULD WAIT) and materially strengthens
   **photograph**, **boundary/threshold** and **architecture** (which has no inhabited interior).
3. It is the correct **control** for the anthropomorphism failure. The recorded defect is that the
   model projects gaze and confrontation onto things with no face. Until it is shown a scene with
   real faces and real address, there is no baseline against which the projection can be measured —
   only the failure, never the contrast.
4. It breaks the corpus's uniform register. Every one of the 127 images is museum, monument,
   cemetery, church, or the user's own lamp-lit desk. The model is never asked to describe
   something *unremarkable*, and reverence is currently indistinguishable from perception.

Second priority, well behind: a genuinely non-figurative surface (concrete, water, bark) — the
clean R12 substrate that `695be843` was only an accidental stand-in for.

---

## Honest note on corpus size

127 posts is a misleading number. The real accounting:

| bucket | count | usable as rehearsal fixtures? |
|---|---|---|
| curated art/architecture reference (`695be…`) | 45 | yes |
| Mona Lisa + Trevi (`6a5ac…`) | 2 | marginal — Mona Lisa is a recall trap |
| sketchbook archive (`6a5b…`) | 80 | essentially no |
| **byte-identical duplicate** (`695be817…f5fb`) | −1 | must be excluded |
| **already claimed** (002, 002F, 003, 004 ×3, A4) | −7 | taken |

**Genuinely available, unclaimed, non-duplicate fixture stock: 39 images.**
(45 − 1 duplicate − 7 claimed, + 2 from the `6a5ac` pair = 39.)

Of the 80 sketchbook posts, they collapse to **10 distinct source carousels**, and within each
carousel the frames are the same book, the same desk, the same lamp, minutes apart. Their real
fixture value is roughly **3–5 images**: the anatomy plate (`6a5b9076`), the ellipse/construction
drills (`6a5b907b`), the Loomis head-construction sheet (`6a5b9088`), the archive-grid photo
(`6a5b9013`), and perhaps one hand-in-frame drawing-in-progress shot (`6a5b9224`) for R7. The
remaining ~75 are personal practice material and should be excluded from any sampling frame, not
because they are poor images but because sampling them will silently return near-duplicates and
inflate confidence in whatever the batch concludes.

Annotation depth is the harder constraint: **116 of 127 posts have no grounds at all**, and the
grounds that exist on 4 sketchbook posts are almost certainly noise. Any rehearsal design that
assumes existing region/ground evidence will be working from ~8 real posts, of which 7 are already
claimed. **In practice, R2 breadth work must be prepared to run on unannotated images.**

---

*Lane 2 complete. Report written; scope closed here per the coordination rule.*
