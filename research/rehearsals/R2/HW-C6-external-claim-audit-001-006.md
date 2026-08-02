# HW-C6 — Retro-audit: what an external-claim ledger WOULD contain for runs 000–006

**AUDIT ONLY — no run artifact modified, no backfill performed, no model calls made.**
No `score.md`, `sparks.md`, `critique.md`, manifest, observation or trace was written or edited.
No DB read or write. No source edit. Nothing staged, committed or pushed. The frozen observations,
the fixtures and the vault documents were **read only**. This document is the audit's single write.

| | |
|---|---|
| **id** | HW-C6 · lane 3 of the coordinated 5-lane cycle |
| **date** | 2026-07-21 |
| **audits against** | `Decisions/HW-C5-external-claim-convention.md` (status: **Proposed**) |
| **first voluntary adopter (reference)** | `runs/007-anthropomorphism-ab/score.md` §External claims |
| **scope** | runs `000`, `001`, `002`, `002F`, `003`, `004`, `005`, `006` |
| **evidence base** | `runs/*/observations/*.json` → `output.answer_text` (verbatim), plus each run's own `score.md` / `critique.md` / `sparks.md` / `manifest.yaml`, plus direct reading of the fixtures |
| **recommendation, in one line** | **Do not retro-fill the runs.** This document is the retro-fill, in the only form that does not damage the evidence. But **§C2 must be settled before the convention meets its next run.** |

A methodological note that governs everything below: **claims the model merely echoed from its own
prompt are not model-supplied claims.** A1's "Gupta" and "Pala" and A3's "This is a painting" were
put there by the curator. Every row in this audit was checked against the prompt text in the same
observation before being recorded.

---

## 000-passage-001 — LEDGER NOT APPLICABLE

**No model output exists.** The run directory contains `manifest.yaml`, `source.md`, `sparks.md`,
`missing-telemetry.md`, `trace.json` — and **no `score.md` and no `observations/` directory at
all**. `manifest.yaml` records `mode: "imaginative"`, `reconstructed: true`. `missing-telemetry.md`
states plainly: *"No SAM / SAM2 / YOLO / SegFormer / DINOv2 / FashionCLIP / semantic-provider / VLM
call was ever run… no frozen observation exists under `observations/`."*

| verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|
| — | — | — | — | — |

**Is the absence meaningful?** **Neither.** It is *inapplicable*. The ledger records what a model
said; here there is no speaker. Recording this run as "empty" would be an error of exactly the kind
HW-C5 §2 warns about in the other direction — it would enter a negative into the evidence base for
spark-08 that no model ever had the chance to produce. **If a retro-fill were ever performed, run
000 must be marked `n/a`, never `none`.**

---

## 001-eyes-of-stone — LEDGER NOT APPLICABLE (and this run is untracked)

**Status check first:** the run is present on disk and is **untracked user-owned content**
(`git status` → `?? vault/Build/Architecture Lab/Vision pipeline/rehearsals/runs/001-eyes-of-stone/`).
It was read and not modified.

`manifest.yaml` sets `mode: "imaginative"` with `constraints.no_model_calls: true` and
`no_iconographic_identification: true`. There are no observations. `score.md` is prose authored by
`conducted_by: "human+codex"` — it is the *rehearsal's* voice, not a captured model observation, and
the convention's ledger has no jurisdiction over it.

The tempting rows are the cultural attributions in the prose — *"Pala and Chola sacred embodiments,
and Cambodian sculptural histories"*. **These are not model importations.** `manifest.yaml` marks
every such fixture `metadata_status: "user-supplied Pala context; exact metadata unverified"` (and
likewise Chola, Cambodian), and `source-notes.md` says *"Material names in filenames follow broad
user context and appearance; catalog verification is absent."* They are **curator-supplied**, and
the run then spends a whole section (*"Cultural refusal"*) declining to convert them into meaning.
Under HW-C5 §5 this is the `source_pressures` case — the inverse of the ledger's case — and the doc
is explicit that the two must not be collapsed.

**Is the absence meaningful?** **Inapplicable**, but with a note worth keeping: 001's
`sparks.md` carries a *"Deliberately withheld"* list (*"universal spirituality/serenity across
faces; automatic patina or ritual-touch detection; generated restoration bodies for fragments"*).
That is the same instinct the ledger formalises, aimed at the rehearsal's own speech rather than
the model's. It shows the practice predates the convention — it does not supply evidence about
model behaviour.

---

## 002-figure-ground-reversal (A1) — LEDGER: none

Both probes read. Every proper noun in the answers (`Gupta`, `Pala`) is **echoed from the prompt**.

| verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|
| *(none)* | | | | |

Nearest thing to a row, and rejected: obs1's *"visually separate the two distinct artistic
styles"*. This asserts a stylistic difference — but the fixture is a **labelled comparative plate**
carrying white in-frame captions ("Solanki", "Gupta", "Pala", "Amaravati", "Gandhara"), so the
attribution is *in the frame*, not outside it, and the two named schools came from the prompt. Not
an external claim.

**Is the absence meaningful — or merely not looked for?** **Meaningfully empty, with a caveat, and
it is the strongest kind of negative in the set.** Two independent reasons:

1. **The frame contained readable attributional text and the model did not touch it.** Five school
   names were legible in the plate. A model disposed to attribute had free material and used none.
2. **The prompts were narrowly guarded** — a 20-px strip, then a bounding-box demand. Neither asked
   what the image *is*. So the empty ledger is partly a property of the question.

Reason 1 survives the caveat in reason 2; reason 2 means A1 cannot be counted as a *free* negative
under HW-C5 §6.1's overturn test. **Count it as a guarded negative, not an open one.**

---

## 002F-single-object-followup (A1F) — LEDGER: 2 rows, and the most valuable negative in the set

Fixture: Michelangelo's Pietà photographed in situ (`fixtures/002F-pieta-single-object/pieta-in-situ.jpg`).

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "layered stone or marble panels in deep browns, grays, and muted blues" (`002F-single-object-followup-obs1`) | other (material) | `frame-silent` | — | no |
| 2 | "It appears aged and weathered, with subtle variations in tone that suggest depth and **historical patina**" (`obs1`) | other (material/duration) | `frame-silent` | — | no — hedged ("appears", "suggest") but never marked as unsettleable by the image |

**Row 2 is not a nuisance row.** Run 001's own `score.md` argues at length that *"From these files
alone, a dark patch might be age, soil, conservation, lighting, compression, coating, or capture…
The photograph does not expose a trustworthy history merely because it looks old."* A "historical
patina" claim is precisely the thing the program has already decided a photograph cannot settle.

**What is absent, and it matters more than what is present:** on the **most recognisable sculpture
in Western art**, in situ, the model volunteered **no title, no artist, no institution, no date**.
Compare A5, where a far less famous monument produced all four.

**Is the absence meaningful — or merely not looked for?** **Both, and they must be separated.**

- *Not previously looked for*: rows 1–2 were quoted approvingly in `002F/score.md` as evidence that
  the negative space is "pointable"; nobody examined them as claims. So the ledger was never run.
- *Meaningful*: the attribution-shaped absence is real evidence, because the fixture maximised the
  opportunity. It is the **best natural control for spark-08 already sitting in the tree** — same
  genre as A5 (famous marble sculpture, in situ, architectural setting, single photograph), same
  model, different question. **The one thing it does not control is the question**, which is
  exactly the variable §D identifies as decisive.

---

## 003-sensory-disagreement (A2) — LEDGER: 3 rows

The known instance is confirmed: the model *did* make material and period claims.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "The material appears to be a dark, weathered stone, such as **basalt or granite**, characterized by its rough texture and deep brownish-black color" (`003-sensory-disagreement-obs2`) | other (material) | `frame-silent` | — | no — hedged ("appears", "such as"), but the response never says the image cannot settle material |
| 2 | "the sculpted body of a figure, **likely from an ancient stone carving**" (`003-sensory-disagreement-obs1`) | date (period) | `frame-silent` | — | no |
| 3 | "the seamless transition of texture, lighting, and form… **indicating they are carved from a single block**" (`obs1`) | other (fabrication) | `frame-silent` | — | no — asserted as the answer, with "the consistent materiality and directional lighting further **confirm** it" |

**No culture, school, region, artist, date or institution was named.** Row 2 is the only temporal
claim and it is a genre-level hedge ("ancient"), not a dating.

**Is the absence meaningful — or merely not looked for?** **Not looked for, on the material axis;
partly meaningful on the attribution axis.**

- `003/score.md` **quotes row 1 verbatim** — *"dark, weathered stone, such as basalt or granite"* —
  and uses it as corroboration that the region is a sculpture rather than a wall. It was read as
  *evidence for the rehearsal's own finding* and never examined as a claim the frame cannot settle.
  This is the clearest instance in the audit of the ledger's stated purpose: **the material was
  already on the page and nobody was looking at it in this way.**
- Row 3 is load-bearing for A2 and unexamined. "Carved from a single block" is a claim about
  fabrication that a photograph cannot settle (a joint can be invisible), and A2's headline result —
  *"ONE surface"* — leans on it as one of three converging routes. `critique.md` §3 gets close
  (*"the probes were easy… neither probe was designed to fail"*) but never names the epistemic
  status of the claim.
- On attribution: the fixture is an anonymous close-up with no legible text and the prompts asked
  what is *physically present*. So the attribution-shaped absence is real but **guarded**, like A1.

---

## 004-gesture-and-address (A3) — LEDGER: 3 rows, **including one `frame-contradicts`**

Both probes checked, as instructed.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "the downward tilt of the head and the obscuring **lace veil** create a barrier" (`004-gesture-and-address-obs2`, on IMAGE 1) | other (in-frame material) | **`frame-contradicts`** | `fixtures/004-gesture-and-address/subject-painting-bound-face.jpg` — the fabric is an opaque heavy bow bound across the mouth, not lace, and the head is thrown **back**, not down. **Settled contemporaneously by the run's own author**: `004/critique.md` §1 — *"The head in this painting is thrown back, not down, and the fabric is a heavy bow, not lace."* Independently re-verified from the fixture in this audit. | no |
| 2 | "The **building's** facade is structured as a monumental, frontal face with **windows that function as eyes**… creates a direct, imposing gaze" (`obs2`, on IMAGE 3) | other (identity + anthropomorphism) | `frame-silent` | — | no |
| 3 | "The heavy, dark bow and veil-like cloth act as a visual barrier, suggesting concealment or **mourning**" (`004-gesture-and-address-obs1`) | other (interpretive attribution) | `frame-silent` | — | no |

**No title, artist, date, place or institution in either probe** — notable because the subject
painting carries a **visible artist's signature in the lower-left corner** of the fixture, which the
model neither read nor used.

Notes on the two judgement calls:

- **Row 1 is genuinely settled**, and it is the *second* `frame-contradicts` in the corpus after
  A5's inscription. It is also a different species: A5 quoted text that does not exist; A3
  mis-described a material that does. Both are claims *about what the frame contains* that the
  frame falsifies. That A3's author caught it at the time, in `critique.md`, means this row is
  **not** a hindsight artefact — it is the one retro-row in this audit with contemporaneous
  provenance.
- **Row 2 is deliberately `frame-silent`, following 007's precedent.** 007's ledger recorded
  "glowing eyes"/"face-like frontality" on this same stimulus as `frame-silent`; the fixture
  (re-read here at 768 px) is a dark tower with real illuminated fixtures and real window-like
  openings, so "building" and "windows" are not falsified. Consistency with the adopter matters
  more than a marginal upgrade. **But see §C3: this is one of two rows in the audit where a
  different reader could argue `frame-contradicts`, which is HW-C5 §6 overturn condition 3.**

**Is the absence meaningful — or merely not looked for?** **The attribution absence is meaningful
and unusually well-attested; the ledger itself was never run.** `critique.md` shows the author
adversarially re-reading the model's descriptions against the pixels — the exact discipline the
ledger encodes — but doing it as prose about accuracy, not as a record of claim-status. Rows 2 and
3 were noticed and *used* (row 2 is the basis of spark-06) and never classified.

---

## 005-surface-becoming-structure (A4) — LEDGER: 3 rows

Both known instances confirmed verbatim, plus one nobody recorded at the time.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "This disagreement is intentional — it's **a classic Islamic architectural device** to demarcate zones of ornamentation and structure" (`005-surface-becoming-structure-obs2`) | attribution (cultural/period) | `frame-silent` | — | no |
| 2 | "**The central mihrab niche** and flanking arched panels are structurally defined first" (`005-surface-becoming-structure-obs1`) | other (function/religious identification) | `frame-silent` | — | no |
| 3 | "the clear vertical and horizontal divisions created by arches, **pilasters, and cornices**" (`obs1`) | other (imported classical-order vocabulary) | `frame-silent` | — | no |

Row 1 was requested unprompted in a probe about a dividing line; row 2 was requested unprompted in
a probe about composition. `manifest.yaml` sets `no_iconographic_identification: true` and neither
prompt mentions culture, period, religion or tradition.

**Row 2 is new to this audit.** `005/score.md` §"Where the model overreached anyway" records **only
row 1**. "Mihrab" is a stronger claim than "Islamic device": it names what the niche is *for*
(a qibla-indicating prayer niche). Read at native resolution, the central niche in
`fixtures/005-surface-becoming-structure/turquoise-tile-revetment.jpg` is pierced by an openwork
lattice window — which sits awkwardly with the identification. **I have still recorded it
`frame-silent`, not `frame-contradicts`,** because falsifying it requires a definitional premise
about mihrabs imported from outside, and HW-C5 §4.1/§4.3 forbid making the ledger depend on
external knowledge. See §C3.

**Is the absence meaningful — or merely not looked for?** **This run is the one pre-convention case
where a partial ledger was genuinely run.** `score.md` has a dedicated overreach section and
`critique.md` explicitly credits it (*"The model's cultural overreach was recorded rather than
quietly used"*). A4's ledger is therefore *contemporaneous evidence*, not hindsight — for row 1.
Rows 2 and 3 show what a partial pass misses: the author caught the claim that *announced itself*
as a cultural aside and missed the one folded into a noun phrase inside an otherwise on-task
sentence. **That is a finding about the ledger as an instrument: attributions embedded in
referring expressions are the ones prose misses.**

---

## 006-narrative-overreach (A5) — LEDGER: 7 rows, 2 `frame-contradicts`

All four known instances **verified verbatim against `006-narrative-overreach-obs1`**. Three further
rows are added that HW-C5 §3.3's worked example does not carry.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "a close-up view of the famous marble sculpture **\"The Angel of Gethsemane\"** (also known as *The Mourning Angel*), located in the **Gethsemane Chapel** at the **National Cathedral in Washington, D.C.**" (`obs1`) | name + place | `frame-silent` | — | **contradicted** — same response: *"While widely known as 'The Angel of Gethsemane,' the photo alone doesn't label it — so without prior knowledge, one might not know its name"* |
| 2 | "The sculpture was created by **Paul Manship**" (`obs1`) | attribution | `frame-silent` | — | **contradicted** — same response: *"No signature or plaque is visible in the frame, so we cannot determine the sculptor or year from the image alone."* |
| 3 | "in **1921**" (`obs1`) | date | `frame-silent` | — | **contradicted** — same sentence as #2 |
| 4 | "**Inscription visible in background**: In the top portion of the image, part of an inscription reads *\"…THE LORD IS MY LIGHT AND MY SALVATION…\"* — **confirming** the religious context and location within a Christian cathedral" (`obs1`) | quotation | **`frame-contradicts`** | `fixtures/006-narrative-overreach/_medallion-x6.png` — **re-verified in this audit by direct reading**: a coloured figural mosaic tondo inside a Greek-key border, with a fragmentary **non-English** lettering band (legible fragments include `…EN TE NED…`, `…GISTIS…`). The quoted English phrase appears nowhere in the frame. | no |
| 5 | "The white marble, realistic anatomy, and dramatic drapery are characteristic of **early 20th-century neoclassical sculpture, matching Manship's known work**" (`obs1`) | attribution (period + reference to unshown material) | `frame-silent` | — | no. *Cites a body of work the model was not shown, as corroboration for #2.* |
| 6 | "slumped over **a tomb or sarcophagus**" (`006-narrative-overreach-obs2`) | other (function) | `frame-silent` | — | no |
| 7 | "This is clearly visible in **multiple cropped views**, especially the close-up of the face and upper body" · "a domed ceiling (**visible in the top crop**)" (`obs2`) | other (claim about material not shown) | **`frame-contradicts`** \* | `006-narrative-overreach/observations/006-narrative-overreach-obs2.json` — the frozen request carries **exactly one image**; `006/critique.md` records the same. No crops were sent. | no |

\* **Row 7 stretches the definition and the stretch is reportable.** HW-C5 §3.2 defines
`frame-contradicts` as *"the pixels falsify it"*. Row 7 is falsified not by pixels but by the run's
**frozen request record**. It is settled just as hard — arguably harder — but by a third authority
the convention does not name. See §C4.

**Row 1's `contradicted` value is stronger than the worked example records.** §3.3 marks #1 as
`speaker-flagged: no`. The frozen text shows the model flagged the *name* too, in the same
response's limits section. All three of the attribution cluster's components are `contradicted`,
not two.

**Is the absence meaningful?** No absence here. A5 is the motivating case and it survives verbatim
verification intact.

---

## A. Summary table

| run | mode | model calls | external claims | `frame-contradicts` | empty ledger meaningful? |
|---|---|---|---|---|---|
| **000**-passage-001 | imaginative, reconstructed | **0** — no `observations/` at all | **n/a** | — | **Inapplicable.** No speaker. Must never be scored as `none`. |
| **001**-eyes-of-stone | imaginative, `no_model_calls: true` | **0** | **n/a** | — | **Inapplicable.** Cultural labels present but curator-supplied (`source_pressures` case, HW-C5 §5). |
| **002** (A1) | instrumented | 2 | **0** | no | **Meaningful but guarded.** In-frame attributional captions available and unused — but both prompts were narrowly scoped. |
| **002F** (A1F) | instrumented | 2 | **2** (material/patina) | no | **n/a — non-empty.** Its *attribution*-shaped absence is the audit's best natural control for spark-08 (the Pietà, unnamed). |
| **003** (A2) | instrumented | 2 | **3** (material, period, fabrication) | no | **n/a — non-empty.** Row 1 was quoted in `score.md` as corroboration and never examined as a claim. |
| **004** (A3) | instrumented | 2 | **3** | **yes — 1** ("lace veil"; settled contemporaneously in `critique.md` §1) | **n/a — non-empty.** Attribution absence meaningful; a visible signature went unread. |
| **005** (A4) | instrumented | 2 | **3** | no | **n/a — non-empty.** The only run with a *contemporaneous partial* ledger (1 of 3 rows). |
| **006** (A5) | instrumented | 2 | **7** | **yes — 2** (fabricated inscription; hallucinated stimulus) | **n/a — non-empty.** Motivating case; verified verbatim. |
| *(007, reference)* | instrumented | 2 | 3 | no | first voluntary adopter — ledger written contemporaneously |

**Aggregate: 6 instrumented runs, 6 non-empty ledgers under a strict reading, 0 fully empty.**

---

## B. Is a retro-fill worth doing? — **No. Recommend against.**

Stating the case for it first, honestly, because it is not weak.

**For.** The frozen observations are immutable and content-hashed. A ledger derived from them is
*reproducible* — any later reader gets the same rows from the same text, which is more than can be
said for a contemporaneous prose judgement. The material is not lost, the derivation is cheap
(this audit: one reading pass, zero model calls, zero cost), and it produces exactly the index
HW-C5 §5 says is missing — *"no way to ask 'in which runs did the model import outside-frame
material, and in which did it not'"*.

**Against, and this decides it.**

1. **HW-C5 forbids it twice, on purpose.** §6: retrofitting A5's ledger into `006/score.md` *"is
   not authorized by this doc; §3.3's worked example lives here… precisely so that the run's own
   artifacts stay as they were written."* §7: *"No backfill. Runs 001–006 are not amended."* A
   lane cannot grant itself the authorization the decision withheld.
2. **Hindsight contamination is real and it is asymmetric.** I read these observations already
   knowing what A5 found and what shape to look for. That inflates the positives — I found three
   rows (005 #2, 006 #5, 006 #7) that the runs' own authors, reading the same text hours after
   producing it, did not see — while doing **nothing at all** for the negatives. And the negatives
   are the entire reason HW-C5 §2 argued for adopting early. A retro-filled negative is not
   evidence that nobody was looking; it is evidence that *I* looked, later, primed. **The one
   thing a retro-fill cannot manufacture is the property that motivated the convention.**
3. **Editing the six `score.md` files would destroy an interpretable fact.** 007 is currently
   legible as *the first voluntary adopter* — an adoption event with a date. Backfill six earlier
   runs and that reading disappears; the tree then shows a uniform practice with no origin, and
   the convention's own §6.1 self-correction story ("three consecutive empty ledgers would kill
   it") becomes unreadable because the ledgers were not written when the runs were.
4. **Cost.** Producing the content: already paid, it is this document. Applying it: six file
   edits, each of which converts a frozen artifact into an amended one and each of which needs a
   provenance stanza saying *when and by whom* — six stanzas whose sole content is "this row is
   hindsight". That is more ceremony than the rows are worth.

**Recommendation.** Keep the retro-fill **external**: this file, dated, attributed, explicitly
marked as hindsight, deriving every row from a hashed observation. If cross-run indexability is
wanted, add a **one-line pointer to this file** from `R2/CANDIDATE-REGISTER.md` §spark-08 — not a
row in any `score.md`. The runs stay as written.

---

## C. Consequences for the convention itself (the audit's real product)

### C1 — The `contradicted` column and the two-status split both survive contact

`contradicted` fired exactly once (A5, three rows) and would have been **unrecordable** under any
taxonomy that made speaker-flagging a status value. HW-C5 §3.2's reasoning holds. Likewise no row
in six runs required an external lookup to place — §4.3 is enforceable in practice, and §6's
overturn condition 2 was not triggered.

### C2 — **The overturn test is currently untriggerable, and this must be settled before the next run**

HW-C5 §6.1 says the convention dies if **three consecutive runs produce empty ledgers**. This audit
finds that under a strict reading of §3.2, **the ledger is almost never empty**. Every instrumented
run in the corpus carries a low-grade band of unrequested, unflagged, frame-unsettleable claims —
*"basalt or granite"*, *"marble panels"*, *"historical patina"*, *"ancient stone carving"*,
*"white marble"*, *"carved from a single block"*, *"pilasters and cornices"*. These are true
external claims by the letter of the definition: unrequested, outside what the frame settles, never
flagged. They are also **not the phenomenon spark-08 is about**, and if they populate every ledger
the overturn condition can never fire and the ledger becomes noise that hides its own signal.

This is a scope question the convention does not answer, and it has exactly two honest resolutions:

- **(a) Strict.** Record them. Then §6.1's "three empty ledgers" must be restated as *"three
  consecutive runs with no `name`/`attribution`/`date`/`place`/`quotation` row"* — i.e. the
  overturn test keys on the **kind** column, which already exists and already separates them.
- **(b) Narrow.** Define the ledger's scope as identity-reaching claims only, and let material and
  period hedges stay in prose. Simpler, but it discards the row that this audit shows was most
  invisible to contemporaneous reading (A2's "basalt or granite", quoted approvingly as evidence).

**(a) is the smaller change and needs no new column.** Either way the choice must be made *before*
a run applies the convention, or the first three ledgers will not be comparable.

### C3 — Two arguable `frame-contradicts` in six runs; §6 condition 3 is close

HW-C5 §6.3 says the convention should collapse to one status if *"whether the frame refutes a claim
is itself arguable."* This audit hit that twice: **A3's "building's facade… windows that function
as eyes"** (recorded `frame-silent` for consistency with 007) and **A4's "the central mihrab
niche"** (recorded `frame-silent` because falsifying it needs an imported definition). Neither was
settled by a crop the way A5's inscription was.

The distinction that keeps the status alive is worth stating: **A5's inscription and A3's "lace"
were both settled by looking at pixels and needing nothing else.** The two arguable cases both
require a premise from outside the picture. **Proposed clarifying rule, if the orchestrator wants
one: `frame-contradicts` requires that the falsification be statable using only the picture and no
external premise.** Under that rule the corpus has 2 clean `frame-contradicts` and 0 arguable ones,
and §6.3 is not triggered.

### C4 — A third settling authority exists that the convention does not name

A5 stage 2's *"multiple cropped views"* / *"the top crop"* is falsified by the **frozen request
record** (one image sent), not by the pixels. It is as hard a settlement as a crop and is a
distinct failure — the model hallucinating its own **stimulus** rather than the world. `critique.md`
already flags it as a *"new failure mode for the corpus"*. The ledger has nowhere to put it except
by stretching `frame-contradicts`. **A `stimulus-contradicts` value, or an explicit note in §3.2
that the request record counts as frame evidence, would close this.** It is cheap and it is the
only shape-level gap the audit found.

---

## D. The pattern across runs — **it clusters by QUESTION, not by fixture**

This is the audit's main cross-run finding and it is fairly clean.

**Identity-reaching claims (title / artist / date / institution / quoted inscription) appear in
exactly one run out of six — the only run asked an open "what is this?" question.**

| run | fixture recognisability | question shape | identity claims |
|---|---|---|---|
| 002 | labelled comparative plate, **captions legible** | "what is the space *between* X and Y doing?" | **0** |
| 002F | **Michelangelo's Pietà, in situ** — maximal | "what is the space *beside* the figures doing?" | **0** |
| 003 | anonymous carved figure, no text | "is this one surface or two?" / "what is physically present?" | **0** |
| 004 | painting **with a visible signature** | "where does this gesture's address go?" | **0** |
| 005 | recognisable Timurid-type revetment | "does the pattern or the structure organise this?" | **0** (but 2 cultural/functional rows) |
| **006** | Angel-of-Grief-type monument | **"what is happening in this photograph?"** | **5** |

Fixture fame does **not** predict the behaviour: 002F is the most famous object in the corpus and
produced nothing, while 006's monument type is far less universally known and produced a title, a
sculptor, a date, an institution and a fabricated inscription. What separates them is that A5 asked
an **open, unbounded, identity-inviting question** and every other run asked a **bounded relational
or spatial one**.

Three secondary patterns:

1. **This is the same shape as 007's result, on a different behaviour.** 007 settled that
   anthropomorphism here is *question-conditional*, not image-driven. This audit finds attribution
   behaves the same way. Two independent behaviours, both prompt-conditional, on the same model —
   that is a stronger and more general reading than either run alone supports, and it is
   **suggestive, not established**, because it rests on an uncontrolled cross-run comparison rather
   than an A/B.
2. **Cultural attribution sits between the two.** A4 got none from a composition question (probe 1
   still slipped "mihrab" in as a *referring expression*) and one explicit device-attribution from
   probe 2, whose "what decides it?" tail invites explanation. **Explanation-demanding questions
   pull attribution; description-demanding questions do not.**
3. **Speaker-flagging is prompt-conditional too.** `contradicted` occurs only in A5 — and A5 is the
   only run whose prompt asked for limits (*"what the photograph does not let you say"*). No other
   run gave the model an occasion to flag anything. **A run's `speaker-flagged` column is close to
   uninformative unless the prompt solicits limits**, which is worth recording next to the column
   rather than discovering per-run.

**The cheapest available next test follows directly**: re-run **002F's Pietà** — already fixtured,
already hashed — under A5's stage-1 prompt verbatim. Same model, same famous-marble genre, one
variable (the question). It is spark-08's *"two further monuments"* test at a fraction of the cost
and with a control the original proposal lacks. *(Noted, not requested — this lane authorizes
nothing.)*

---

## E. What this audit could NOT determine

1. **Whether any `frame-silent` claim is true.** No external lookup was performed (HW-C5 §4.1/§4.3).
   A5's title, sculptor, date and institution remain unasserted and unrefuted; "basalt or granite",
   "mihrab" and "Islamic architectural device" likewise. Whether A5's attribution is confabulated or
   retrieved-and-misapplied is **unchanged** — still `006/sparks.md` unresolved-question 1.
2. **Whether the four empty-of-attribution ledgers would have stayed empty under an A5-shaped
   question.** Untested. Every one of those runs used a bounded prompt, so §D's pattern is an
   observational correlation across runs that differ in fixture *and* question, not an isolated
   variable. It is exactly as strong as A4's spark-06 narrowing was before 007's A/B — i.e. it is
   the kind of claim the A6 gate was right to dispute.
3. **Whether the low-grade material band (§C2) is the same phenomenon as A5's attribution or a
   different one.** They differ in salience, hedging and consequence; the audit cannot say whether
   they share a mechanism, and the ledger as specified cannot distinguish them except by `kind`.
4. **Anything about model behaviour from runs 000 and 001.** No model ran. They contribute two
   `n/a` cells and nothing more; treating them as negatives would corrupt the count.
5. **Whether the two arguable `frame-contradicts` cases (§C3) are the start of a trend.** Two in six
   is either §6.3's overturn signal or ordinary boundary friction. n is too small.
6. **Whether a contemporaneous ledger would have caught what this one caught.** A4's partial pass —
   the only contemporaneous data point — caught 1 of 3 rows. That is one observation and cannot
   support a rate.
7. **Cross-model generality.** Every instrumented run used `qwen/qwen3.6-27b` at
   `reasoning_effort: "none"`. Nothing here says anything about any other model.

---

## F. Provenance

| | |
|---|---|
| method | direct read of `runs/*/observations/*.json` (`output.answer_text`), each run's `score.md` / `critique.md` / `sparks.md` / `manifest.yaml`, and direct visual reading of `fixtures/005-…/turquoise-tile-revetment.jpg`, `fixtures/006-…/angel-of-grief-rotunda.jpg`, `fixtures/006-…/_medallion-x6.png`, `fixtures/004-…/subject-painting-bound-face.jpg`, `fixtures/007-…/probe-768.jpg` |
| model calls | **0** |
| DB access | **none** |
| artifacts modified | **none** — this file is the audit's only write |
| git | nothing staged, committed or pushed |
| authorizes | **nothing.** No schema change, no production entity, no backfill, no prompt change, no graduation. spark-08 remains a SPARK at n=1. |
| open items for the orchestrator | **§C2** (ledger scope vs the overturn test) — needs deciding before the next run applies the convention; **§C3** (clarifying rule for `frame-contradicts`); **§C4** (`stimulus-contradicts`) |
