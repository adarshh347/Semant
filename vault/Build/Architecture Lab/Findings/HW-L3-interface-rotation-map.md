# HW-L3 · Interface rotation map

**READ-ONLY rotation map. Research-only. NOTHING here is approved for build.**
No frontend or backend source was edited, nothing was run, no data mutated, nothing staged or
committed. Every "EXISTS" claim carries a `file:line` I actually read. Every rotation is a
**proposal against a specific dullness**, not a plan.

**Relation to HW-S1.** S1 asked *"where could circulation intelligence become visible?"* and
produced a findings list. This map asks a different question, **surface by surface**: *what is
dull here now, what could rotate into this frame, and does it belong now / later / never?*
Where a fact was already established by S1 I cite it in one line and move on
(`Findings/HW-S1-frontend-opportunity-scout.md`).

**The governing constraint on every verdict below.** The corpus is 127 posts, 11 annotated,
**7 percepts, 26 grounds, and exactly 1 `vision_runs` document**. Half the appealing rotations
in this map would render an empty box. I mark those explicitly rather than proposing surfaces
that would be blank in production. Rehearsal findings live on disk
(`vault/Build/Architecture Lab/Vision pipeline/rehearsals/`) and are **not in the database** —
so no surface can display them without a new ingestion path that does not exist.

---

## 0. The surface inventory, as actually routed

`frontend/src/main.jsx:31-91`. Seven surfaces are in scope; two more are noted and dismissed.

| surface | entry | file |
|---|---|---|
| Landing | `/` | `pages/LandingPage.jsx` |
| Home (bento) | `/home` | `pages/HomePage.jsx` + `components/home/*` |
| Chiasm (PostDetail) | `/posts/:postId` | `components/PostDetailPage.jsx` |
| Manuscript (Sutradhar) | inside Chiasm right pane | `components/blocknote/Manuscript.jsx` |
| Field / RegionSurface | inside Chiasm left pane | `components/RegionSurface.jsx` |
| Differential workspace | mode switch from Chiasm | `differential/DifferentialWorkspace.jsx` |
| Vision Activity Rail | inside Differential inspector | `differential/VisionActivityRail.jsx` |
| Aletheia hook | `/read/:postId` | `components/AletheiaHook.jsx` |

Two surfaces named in the brief resolve to something else: **"Sutradhar"** is not a separate
surface — it is the brand word in the Chiasm topbar (`PostDetailPage.jsx:959-960`) and the
`origin: 'sutradhar'` block provenance (`Manuscript.jsx:75-97`); the editor is Manuscript.
**"semantic-read"** is two different things: the *audience* reading (`AletheiaHook`) and the
*curator* assertion panel (`differential/SemanticReading.jsx`), which is the best-behaved
epistemic UI in the app and is treated below as a model rather than a gap.

---

## 1. Landing — `/`

### current dull/static parts
Entirely static by design. `LandingPage.jsx:50-54` hard-codes `HERO_REGIONS` as three
CSS-percentage boxes labelled "the neckline" / "the drape" / "the patterned hem". Nothing on
`/` touches live data at all. (S1 §1.6 established this.)

### what could rotate in
A live hero: the most recently marked *real* region, cropped from a real post, with its real
label. It would make the promise ("Semant marks parts of images") demonstrably true rather
than mocked.

### verdict — **NEVER** (for circulation intelligence)
Not "later". A marketing hero is a *composed claim*, and it should stay composed. The R2
label-collapse finding is decisive against the live version: the most recent real region in
this corpus is plausibly `wall` on a sculpture or `tie knot` on a painting
(`R2/CANDIDATE-REGISTER.md` spark-04). A live hero would put a detector's out-of-domain
failure on the front door as the product's best example of itself. The mock labels
("the drape") are *more honest about the intent* than a live pull would be about the state.

### risk of premature ontology
Low, and that is the point — but there is a subtler one. Wiring Landing to `region_annotations`
would establish, at the most visible point in the app, that **a detector box is a
"noticing"**. That is exactly the vocabulary error Home already commits (§2). Doing it twice
makes it load-bearing.

### ONE reversible experiment
**None proposed.** I am declining to propose one here. Any experiment on Landing measures
marketing conversion, not epistemic honesty, and the two would compete. This is the one
surface where the correct move is to leave it alone.

---

## 2. Home — `/home`

### current dull/static parts
Home is not visually dull — `HomePage.jsx:30-38` is a seven-tile motion bento. It is
**epistemically** dull: every tile is a count derived client-side from the posts list, and one
of the counts is mislabelled.

- `homeData.js:44-50` — `percepts(post)` returns `post.region_annotations`. This is the sharp
  finding and S1 §1.1 owns it; I extend rather than restate.
- `PerceptsTile.jsx:22-32` flattens those regions, **dedupes by lowercased label**
  (`:25-27`) and shows at most 8 under the eyebrow "Parts you recently noticed"
  (`:36`). The dedupe is the part S1 did not note and it is load-bearing here: on the Pietà
  post whose 7 regions are all `wall`/`floor`, the dedupe collapses seven detector guesses to
  **two chips** — which makes the failure *look tidy*. Collapse hides collapse.
- `WeekTile.jsx:23,28` sums the same array and prints it as "percepts".
- `TasteTile.jsx:23-28` reads `leans.parts` from `/api/v1/taste/portfolio` — i.e. the
  audience's *taps on region labels*. Taste is therefore a lean toward `wall` and `floor` with
  no path back to whether those labels were ever true.
- `ContinueTile` / `homeData.js:58-60` — `isInProgress` is `perceptCount > 0 || wordCount > 0`,
  so a post that was auto-dissected and never touched by a human reads as "in progress".

### what could rotate in
1. **Vocabulary correction** — call `region_annotations` *parts*, reserve *percepts* for
   `post.percepts`. Not new intelligence; the precondition for any.
2. **A degradation-only honesty mark** on the Percepts tile: a chip whose percept has no
   resolving ground is shown dimmed or omitted.
3. **Corpus-level evidence health** ("4 of 11 grounds detached") — the R2 headline number.

### verdict — **LATER**, and only #1 is close
#1 (vocabulary) is a *correctness fix*, not a rotation, and I would not spend the "rotation"
budget on it. #2 cannot run: Home fetches the posts list (`homeData.js:14-17`) and never reads
`post.percepts` or `post.grounds` (S1 §6) — resolving a ground client-side on Home would mean
loading grounds + regions for 24 posts to render 8 chips. #3 needs a corpus aggregate endpoint
that does not exist, over a corpus of 7 percepts.

### risk of premature ontology
Specific and serious: **Home is where a word becomes a fact.** If `percept` continues to mean
"detector box" on the most-visited authenticated surface, then the taste portfolio
(`TasteTile.jsx:23`), the week counters (`WeekTile.jsx:28`) and the progress line
(`homeData.js:70-77`) all accumulate as evidence for that definition. Later, when the real
Percept (`pctx_…`, an expression over grounds) needs a home on Home, the word will be
taken — and the migration will be a rename across five components plus whatever the taste
backend has already learned. Committing a *dashboard* here is worse: a "circulation" tile
would fossilise the claim that counts of detector output measure curatorial work.

### ONE reversible experiment
**L3-X1 — the un-deduped Percepts tile.** Remove the label dedupe at `PerceptsTile.jsx:25-27`
for a single session and observe what the tile actually shows.
- **Shows:** whether label collapse is visible to the curator when not hidden by dedupe.
  Prediction: the Pietà renders as seven near-identical `wall`/`floor` chips, and that ugliness
  is the true state.
- **Reversible:** deleting three lines; no schema, no endpoint, no stored data.
- **Cost:** under an hour.
- **Killed by:** if the un-deduped tile is merely noisy across *all* posts (i.e. every post
  produces repetitive labels, in-domain or not), then the display is not diagnosing collapse,
  it is just showing raw output — and the dedupe was right. That outcome kills it.

---

## 3. Chiasm — `/posts/:postId` (PostDetailPage)

### current dull/static parts
Chiasm is the two-pane shell: Field left (`PostDetailPage.jsx:1010-1069`), Manuscript right
(`:1087-1173`). Its own chrome carries almost no state.

- `PostDetailPage.jsx:1023-1041` — the left panel header is two tabs (Image / Regions) plus a
  single `◈ Differential` button. The `panel-actions` slot is explicitly commented as "kept for
  Lane 3 verbs" (`:1041`) and is otherwise empty. **This is the one genuinely reserved,
  genuinely empty affordance in the app.**
- `:1296` — the edit statusline. `:964-980` — topbar actions are save/dirty/overflow only.
- The dirty pill (`:966-967`) is the *only* state signal in the topbar.
- Dead code (S1 §1.5): `onAiCommand` / `onRefCommand` built at `:714-720`, never passed at
  `:1167-1173`; `runAiSlashCommand` (`:606-619`) unreachable.

### what could rotate in
The empty `panel-actions` slot is the obvious candidate for a **per-post evidence-health
pill** — "9 parts · 3 grounds · 1 unevidenced" — a single quiet line that Chiasm currently
cannot show because the counts live only inside Differential's inspector footer
(`DifferentialWorkspace.jsx:815-819`), which is a *different mode* the curator has to enter.

### verdict — **NOW** (for exactly one thing: the unevidenced count)
This is my strongest "now", and it is deliberately narrow. Justification: the data is already
in the client on this route. `PostDetailPage` owns `regionStore`, which owns `grounds`
(`state/regionStore.js:347`), and `resolveGround` (`differential/grounds.js:62-85`) is a pure
function already imported by Differential (`DifferentialWorkspace.jsx:15,438`). No fetch, no
endpoint, no schema. The number is small enough to be true (7 percepts corpus-wide) and the
finding it surfaces is the register's strongest entry (spark-03).

Against my own recommendation, twice:
- **First argument against:** the count will be `0` on 116 of 127 posts and *invisible* on
  those — so the feature is only ever seen by someone already deep in annotation, who is
  arguably the person who least needs telling. The honest reply is that this is a *virtue*
  (degradation-only, per S1 §4.7), not a defence of the value.
- **Second argument against:** Chiasm is the *writing* surface. Putting an evidence-health
  count in its chrome imports a Differential concern into a room whose whole design intent is
  calm (`PostDetailPage.jsx:1041-1043` comment: "Chiasm's resting state stays calm; no
  permanent tool rail here"). A pill that is silent at zero respects that; a pill that always
  shows counts violates it. If it cannot be built silent-at-zero, it should not be built.

### risk of premature ontology
Moderate and nameable. A count of "unevidenced percepts" **asserts that unevidenced is a
state a percept can be in** — which is exactly the fork R2 refused to choose
(`CANDIDATE-REGISTER.md` spark-03: tombstoning vs. notifying "are different theories of what
evidence is"). A *count* is the smallest commitment on that fork — it notifies without
implying repair. But it must not acquire a click target, because the moment it opens
something, that something has to say what to *do*, and that is the fork. **The rule: a number
and a noun, no verb.**

### ONE reversible experiment
**L3-X2 — the silent-at-zero evidence pill in `panel-actions`.**
- **Where:** `PostDetailPage.jsx:1041-1053`, deriving from `regionStore.grounds` +
  `regionStore.regions` through `resolveGround`.
- **Shows:** whether a curator who is told, in the writing room, that one of their percepts
  rests on nothing, goes and looks. Today nothing tells them anywhere except inside a
  Differential list they must switch modes to see (`DifferentialWorkspace.jsx:803-812`).
- **Reversible:** pure derivation, one JSX node, deletable in one diff.
- **Cost:** small — half a day with a test, since `grounds.test.js` already covers
  `resolveGround`.
- **Killed by:** the hydration race. `regionStore` loads regions and grounds in the same effect
  (`state/regionStore.js:94-119`); if grounds land before regions, *every* region-ground reports
  detached for a frame and the pill flashes an alarm on a healthy post. A pill that cries wolf
  during load is strictly worse than silence — if the ordering cannot be guaranteed, kill it.
  (S1 flagged the same race against its E1; it is the single most likely killer in this map.)

---

## 4. Manuscript / the BlockNote editor

### current dull/static parts
- `Manuscript.jsx:77-97` — `AI_STUB`: three slash items ("wires in Phase 4") whose only effect
  is inserting an empty `origin: 'sutradhar'` paragraph (`:91-95`). Live, listed in the menu,
  and inert. (S1 §1.5.)
- `Manuscript.jsx:50-73` — the `@` mention path lists `store.regions` by
  `r.label || 'part'` with subtext `category · material`. **A curator picking a part to cite
  is shown the detector's label and nothing else** — no actor, no confidence, no indication
  that `wall` came from a scene segmenter that has no sculpture class.
- `regionRefInline.jsx:43-57` — `chipAttrs` emits `data-region-ids`, `data-percept-id`,
  `data-mention-id`, `data-label`. **No slot encodes evidence state**, so no chip can style a
  dead citation (S1 §2.1.4).
- `partRefBlock.jsx` — the block-form evidence crop; same absence.

### what could rotate in
1. A chip that dims or marks itself when the percept it cites has no resolving ground.
2. Provenance in the `@` menu subtext — `actor` at minimum, since it is the one field the app
   already reads anywhere (`RegionOverlay.jsx:21`).
3. Real AI commands behind the dead stubs.

### verdict — **LATER**, with #3 being a different program entirely
#1 is genuinely valuable and genuinely blocked in a way S1 understated: the chip is
**inline content inside a BlockNote document that round-trips to stored HTML**
(`blockConvert.js`). Any evidence state must be *derived at render from the store*, never
stored in `props`, or the first save writes a *snapshot of detachment into the manuscript*
and it becomes permanently wrong the moment the region returns. The chip does read the store
already (`Manuscript.jsx:237-240` comment describes exactly this pattern for hover focus), so
the mechanism exists — but this is fiddly enough that it should follow, not lead.

#2 is cheap and I still say later: the `@` menu is a *pick list*, and adding a provenance line
to every row makes the common case (picking a good part) slower to serve the rare case.

#3 is not circulation intelligence at all. Removing the dead stubs would be honest; wiring them
is Phase 4 work with its own gate.

### risk of premature ontology
The highest in this map, and specifically: **the manuscript is durable prose.** Everything else
in the app is a view; a chip is a *thing the curator wrote*. If a detachment mark ever lands in
`chipAttrs` as a stored prop, then evidence state becomes part of the document's text, and
Semant has silently decided that "unevidenced" is a property of a *sentence* rather than of a
*percept*. That is a far bigger commitment than the count in §3, and it is unrecoverable from
saved documents. Second-order: marking chips at all establishes the chip as the place
citations get judged, which is where a future "repair this citation" verb would land — and
repair is the fork R2 refused.

### ONE reversible experiment
**L3-X3 — derived-only chip dimming, render-time, never serialised.**
- **Where:** `regionRefInline.jsx` render path only (`:62-88`), reading the store the same way
  the hover-focus highlight already does; **`chipAttrs` (`:43-57`) untouched.**
- **Shows:** whether a curator re-reading their own passage notices a citation has died. Today
  a chip citing `pctx_mrqp950d_0` — "the upper head", fully unevidenced per spark-03 — renders
  identically to a healthy one.
- **Reversible:** it is a CSS class computed at render. Nothing enters `text_blocks`; deleting
  the diff restores exactly the prior document bytes. **The round-trip test
  (`blockConvert.test.js`) is the guard: if the experiment changes any serialised output, it
  has already failed.**
- **Cost:** small-to-medium (~1 day) — most of it is proving serialisation is untouched.
- **Killed by:** the same hydration race as §3, plus a worse one — BlockNote re-renders inline
  content on its own schedule, so a transient dim could be *sticky*. If the mark can appear on
  a healthy chip even once, kill it: a false accusation inside the curator's own prose is the
  most damaging failure available anywhere in this app.

---

## 5. Field / RegionSurface (the left pane of Chiasm)

*Not in the brief's list, but it sits between Chiasm and Differential and carries the most
dullness per pixel, so it is mapped.*

### current dull/static parts
- `RegionSurface.jsx:474-497` — each part row is: star toggle, `regionName(r)`, optional lens
  reading, optional note. **No actor, detector, confidence, depth or geometry_rev.** A
  hallucinated `wall` and a hand-drawn part present identically (S1 §1.4).
- `RegionSurface.jsx:167-190` — `detect()` POSTs `/detect-regions` and reads
  `data.regions || []` at `:180-181`. The backend returns a `run_id` on the dissect path
  (`backend/routers/posts.py:875`, and additively at `:1266`, `:1425`, `:1546`); the client
  discards it. During the call the entire feedback is `"Dissecting the image…"` (`:363-367`).
- `RegionSurface.jsx:378-382` — the counts strip: `12/40 parts · 3★`. The only summary line,
  and it counts geometry, never provenance.
- `:460-464` — the empty state says "No parts yet. Dissect the image to see its anatomy", which
  frames detector output as *anatomy*: the strongest ontological claim in the UI copy.

### what could rotate in
The run stamp (S1 §2.2 / E4) and per-row provenance (S1 E3) both belong here. I extend S1 with
one thing it did not check: **whether the fields exist**. S1 explicitly could not verify that
stored regions carry `confidence` or `detector`, and flagged a data check as a precondition. I
can add that `RegionSurface.jsx:214-223` writes `detector: null` for creator marks, and
`RegionOverlay.jsx:21` reads only `actor` — so `actor` is the *only* field with demonstrated
frontend presence. **Any provenance row beyond `actor` is speculative until a data check runs,
and this map does not run one (read-only, no DB access).**

### verdict — **LATER for provenance rows; NOW for nothing**
S1 rated the run stamp "very small cost". I disagree with sequencing it now, and this is my
second argument against my own side: with **one `vision_runs` document corpus-wide**, a run
stamp renders empty on essentially every post. S1's defence — "that emptiness is itself the
finding" — is true for a *diagnostic*, but this would ship as a *UI element*, and shipping a
permanently blank UI element to prove a backend point is a bad trade. Get instrumentation
density first. The finding is already recorded in R2; it does not need a widget to be known.

### risk of premature ontology
Rendering `detector` + `confidence` on a row invites the curator to *arbitrate* — "wall at
0.91 vs figure at 0.44, which do you trust?" — and spark-04 is explicit that this is a **false
choice**: an out-of-domain segmenter is confidently non-answering, not disagreeing. A
confidence number next to `wall` would give the wrong answer institutional weight. If provenance
lands here it must read as *origin* ("scene segmenter", "you drew this"), never as *score*.

### ONE reversible experiment
**L3-X4 — actor-only provenance, one word per row.**
- **Where:** `RegionSurface.jsx:486-494`, rendering only `r.actor` (the one field with proven
  presence) as a muted word: "you" vs "detected".
- **Shows:** whether distinguishing hand-drawn from detected changes how curators treat labels
  — the minimum viable version of S1's E3, with the data-availability risk removed.
- **Reversible:** one span, one derived string, no fetch.
- **Cost:** very small (hours).
- **Killed by:** if `actor` is absent or uniformly `'detector'` on stored regions, every row
  gains a word and no information. Also killed if it reads as blame rather than origin —
  "detected" must not imply "suspect", since most detected parts are fine.

---

## 6. Differential workspace

### current dull/static parts
Differential is the *least* dull surface — it already has the tray, the composer, the grounds
list, the percepts list, the detached list, and `SemanticReading.jsx` (which does confidence
bars and accept/reject properly, `:23-26`, `:141-144`). Its dullness is **positional**, not
absent:

- `DifferentialWorkspace.jsx:803-812` — the Detached-evidence block is a plain `<p>` per
  ground: `"{label} — its part was replaced by a re-dissect"`. **No action, no count in the
  footer, no relation to the percepts that depend on it.** It sits *below* Grounds and
  Percepts, so the list that tells you something is broken is beneath the lists showing the
  broken things.
- `:788-801` — the Percepts list gives every percept a ▶ replay button with **no check that
  anything will render**. This is spark-03's sharpest instance and it is here, not in recall.js.
- `:815-819` — the counts footer is `parts · grounds · percepts`. It has room for a fourth term
  and does not use it.
- `recall.js:83-89` — `useRecallPlayer` builds the script with `groundById`, the **raw** store
  lookup (`state/regionStore.js:214-216`), not `resolveGround`. S1 §2.1.1 established the
  consequence; I confirm the call site: `buildRecallScript(percept, groundById)` at
  `recall.js:86`. A detached ground becomes a full `kind: 'ground'` step (`recall.js:48-59`),
  the image recedes, nothing draws, the caption asserts. **Confident display of absent
  evidence**, exactly as spark-03 §"Corroborating finding" feared.

### verdict — **NOW**, for the replay guard specifically
This is the one place where the intelligence, the data, and the harm are all already present
and co-located. `resolveGround` is imported in this very file (`:15`) and already used at
`:438` to build `detachedGrounds`. Making the ▶ button refuse a zero-resolvable percept is a
few lines in a file that already knows the answer.

Arguing against myself: the population is **one known percept** (`pctx_mrqp950d_0`) plus a
second post with 2 detached uncited grounds. A guard for a single instance is not a feature,
it is a bug fix wearing a feature's clothes. I accept that framing — and it is *why* it is
"now": as a bug fix it needs no ontology at all, whereas anything larger does.

### risk of premature ontology
Low *if* it stays a refusal and high if it becomes an offer. "This percept's evidence is gone"
is a statement of fact. "Re-point it?" is the fork. Auto-repair by IoU is explicitly the thing
both S1 (§4.3) and the register (spark-03) warn manufactures provenance — a silently
re-pointed ground is a *forged citation*. The guard must therefore have **no affordance
attached**, which is an unusual discipline to hold in a workspace where every other row has
buttons.

### ONE reversible experiment
**L3-X5 — the replay guard.**
- **Where:** `DifferentialWorkspace.jsx:788-801`; derive per-percept resolvability from the
  same `resolveGround` call already at `:438` and disable ▶ with a title explaining why.
  (Note: fixing `recall.js:86` to take the resolving lookup is the *deeper* fix and is
  strictly larger — it changes a pure function with an existing test file. The guard at the
  button is the reversible slice.)
- **Shows:** whether the silent empty replay is experienced as a failure, and how often the
  guard fires in real use.
- **Reversible:** one derived set, one `disabled` attribute. No change to `recall.js`, so
  `recall.test.js` stays green untouched — which is the reversibility proof.
- **Cost:** small (half a day).
- **Killed by:** the hydration race again (a disabled ▶ during load), **or** by discovering the
  ▶ button is never used — in which case the guard protects nobody and the real question is
  why replay is unused.

---

## 7. Vision Activity Rail

### current dull/static parts
The rail is well-built and honest — absence vs unreadability discriminated
(`VisionActivityRail.jsx:22-44`), no causal language, raw errors behind a disclosure
(`:91-96`), scope disclaimed in the body (`:152-154`). Its dullness is that **it is almost
always empty and cannot say so from outside itself**:

- `:102` — starts collapsed.
- `:124-133` — the closed summary folds every non-nominal state into `"N recorded"`. A
  `partial` or `timed_out` run is indistinguishable from success until opened. (S1 §1.2.)
- `DifferentialWorkspace.jsx:821-829` — mounted **below** the counts footer, at the bottom of
  the inspector, in one mode of one surface. This is its only mount in the app (S1 §0).
- `:113` — `const now = Date.now()` is computed in render and fed into the `useMemo` deps at
  `:114-122`, so age text recomputes on every render. Cosmetic, but it means the memo never
  memoises.

### verdict — **NEVER move it, LATER for the summary line**
"Never" is deliberate and is my sharpest disagreement with the obvious instinct. The rail
should **not** be promoted, opened by default, or mounted on other surfaces. With one
`vision_runs` document corpus-wide, promoting it means every curator, on every post, opens a
panel to read four rows of *"No recorded activity"* (`:40`). That teaches people the feature
is broken and trains them to dismiss it permanently — spending the disclosure affordance
before there is anything to disclose. S1 reached the same conclusion (§4.6); I go further:
this is not "later", the *placement* is correct and should be defended.

The summary line (S1's E5) is genuinely "later" and must be sequenced **after** telemetry
density, for the reason S1 itself gives: it is unmeasurable while the answer is always
"nothing recorded yet".

### risk of premature ontology
The rail already made its ontological commitments carefully and correctly — four named
operations (`visionActivity.js` `OPERATIONS`), a scope disclaimer at `:152-154`, no
cross-run causality per P2.2. **The risk here is undoing that.** The temptation once telemetry
gets dense will be a run *history*: a vertical timeline per post. That would (a) require a
list endpoint that does not exist (only `latest` and `by-id`, `backend/routers/posts.py:890,902`)
and (b) place separate runs in visual sequence, which readers *will* read causally — the exact
thing P2.2 forbids. Adjacency in a timeline **is** a causal claim, whether or not the copy says so.

### ONE reversible experiment
**L3-X6 — count what the rail would have shown, without showing it.**
- **Where:** nothing rendered. Instrument `useVisionActivity`'s existing results
  (`differential/useVisionActivity.js`) in a dev-only console/counter to record, per post
  visited, how many of the four operations return a run.
- **Shows:** the actual telemetry density, which is the blocker for every other rail idea and
  is currently known only as "1 document in the DB" — a number that says nothing about *which*
  operations record and how often.
- **Reversible:** it renders nothing; it is a temporary log, deleted with the diff.
- **Cost:** trivial (an hour).
- **Killed by:** if it confirms density stays near zero across normal use, then **every** rail
  rotation is dead for this cycle and the work is backend instrumentation. That is a
  successful experiment with a negative result — the cheapest useful outcome in this map.

---

## 8. Aletheia / `/read/:postId`

### current dull/static parts
- `AletheiaHook.jsx:105-106` — `cited = new Set(lens?.region_ids || [])`, then
  `post.region_annotations.filter(r => cited.has(r.id))`. If a re-dissect replaced the cited
  regions, this yields `[]`; the `<svg>` at `:116-131` renders zero tappable shapes and the
  hint at `:160-165` (gated on `regions.length > 0`) never appears. **The audience sees a
  confident reading paragraph (`:143`) over an untappable image and is told nothing.** This is
  lens-level detachment, with no model support anywhere — `resolveGround` has no lens analogue
  (S1 §1.7, §6).
- `:101` — every failure collapses to `'Loading…'` or a single error string; a failed reading
  and a slow one look alike.
- `:192-215` — the portfolio: `signals · images` and up to five chips per group. The chips are
  region *labels*, so the audience's "taste" is a lean toward `wall`, `floor`, `tie knot`.
- `:219` — "session `abc123…` — an opaque id, not you". The single most epistemically careful
  line of copy in the whole frontend, and a good model.

### verdict — **NEVER** (for circulation/rehearsal intelligence), **but the bug is real**
Sharp distinction. The audience must **never** be shown run ids, stages, adapters, detachment
counts or rehearsal findings. That is the curator's workshop; exposing it to a viewer converts
a reading into a machine report and destroys the Écart the surface exists to open
(`AletheiaHook.jsx:11-25`). The rotation verdict is never.

The *failure* is a different matter: a reading over an image with nothing to tap is a broken
promise (the hint literally says "Tap a part of the image the reading rests on", `:161-163`).
The correct fix is **not to display detachment** but to **not offer the tap** — and that is
already what happens (`:160`). So the surface degrades quietly and correctly by accident.
What it lacks is any way for the *curator* to know a public reading has gone hollow.

### risk of premature ontology
Two, both serious. (1) Building a **lens-resolution model** to power an audience-facing mark
would create a second, parallel notion of "evidence resolves" alongside `resolveGround`, on a
different entity (`aletheia.lenses[].region_ids` vs `Ground.region_id`), before the first one's
repair fork is settled. Two theories of detachment is worse than one unresolved. (2) The
`RefPicker` mirror (`RefPicker.jsx:53-64`, badge `${l.region_ids.length} parts`) would need the
same model, so the commitment lands in two places at once.

### ONE reversible experiment
**L3-X7 — measure the hollow-lens rate, on the curator's side only.**
- **Where:** no audience-facing change. A dev-only check that, for each post with an
  `aletheia` block, counts lenses whose `region_ids` no longer resolve against
  `region_annotations` — the same one-line filter as `AletheiaHook.jsx:106`, run as a probe.
- **Shows:** whether lens-level detachment is real and at what rate, which is the *only*
  thing that would justify inventing a lens-resolution model. Right now this is inferred from
  the ground-level mechanism, never measured.
- **Reversible:** measurement only; nothing rendered, nothing stored.
- **Cost:** trivial, and it can piggyback on the same probe as L3-X6.
- **Killed by:** a rate of zero — which would mean lenses are regenerated with regions and the
  whole concern is theoretical. That is the likely outcome and would be a valuable "no".

---

## 9. Verdict table

Ordered by how ready the surface is, most ready first.

| # | surface | dullness | verdict | one-line justification |
|---|---|---|---|---|
| 1 | Differential — ▶ replay guard | offers replay of nothing (`DifferentialWorkspace.jsx:788-801`, `recall.js:86`) | **NOW** | data, harm and `resolveGround` are all already in the file; it is a bug fix, so it needs no ontology |
| 2 | Chiasm — `panel-actions` slot | reserved and empty (`PostDetailPage.jsx:1041`) | **NOW (narrow)** | a silent-at-zero count; a number and a noun, no verb |
| 3 | Vision Activity Rail — placement | collapsed, bottom of one inspector | **NEVER move** | 1 run corpus-wide; promoting it teaches people to dismiss it |
| 4 | Vision Activity Rail — summary line | folds `partial`/`timed_out` into "N recorded" (`:124-133`) | **LATER** | unmeasurable until telemetry density exists |
| 5 | RegionSurface — provenance rows | no actor/detector/confidence (`:474-497`) | **LATER** | only `actor` has proven frontend presence; confidence would stage a false choice (spark-04) |
| 6 | RegionSurface — run stamp | `run_id` discarded (`:180-181`) | **LATER** | would render blank on ~every post; instrument the backend first |
| 7 | Manuscript — chip evidence mark | `chipAttrs` has no slot (`regionRefInline.jsx:43-57`) | **LATER** | must be derived-only; a stored mark writes detachment into durable prose |
| 8 | Home — vocabulary | `percepts()` returns `region_annotations` (`homeData.js:44-50`) | **LATER (fix, not rotation)** | correctness precondition; spending the rotation budget here buys nothing new |
| 9 | Home — evidence health / dashboard | counts only | **NEVER (as a dashboard)** | 7 percepts; a tile would fossilise "detector box = noticing" |
| 10 | Aletheia — any circulation display | hollow lens renders silently (`:105-106,160`) | **NEVER** | the audience must not be shown the workshop; measure the bug, don't display it |
| 11 | Landing | static mock (`LandingPage.jsx:50-54`) | **NEVER** | a live hero would put `wall`-on-a-sculpture on the front door |
| 12 | Manuscript — AI stubs | inert menu items (`Manuscript.jsx:77-97`) | **out of scope** | Phase 4 work, not circulation intelligence |

Two of the three cheapest items in this map (L3-X6, L3-X7) **render nothing at all**. That is
the honest shape of a cycle where the corpus is 7 percepts and 1 run.

---

## 10. What should NOT rotate anywhere yet, and why

**1. Rehearsal findings.** There is no frontend concept of a rehearsal anywhere in
`frontend/src` (S1 §6, confirmed). More decisively: the findings are markdown on disk under
`vault/Build/Architecture Lab/Vision pipeline/rehearsals/` and are **not in the database**.
Surfacing them means an ingestion path, a schema, and a decision about what a rehearsal *is* as
a durable object — precisely what `CANDIDATE-REGISTER.md` declares out of bounds ("Nothing here
is a candidate, a decision, an approved design, or a durable object"). Any UI would be
invention presented as exposure.

**2. Any of the six sparks, as a feature.** None meets the R3 graduation bar (≥3 fixtures +
transfer test + negative case). spark-03 is the strongest and even it is 4-of-11 on a corpus
where "36.4 % is not a rate". spark-05 rests on one subject judged at 256 px where the model
mis-described it. Building from a spark converts a research note into a product commitment
without the gate.

**3. Cross-run history, timelines, or anything sequential over runs.** No list endpoint exists
(`backend/routers/posts.py:890,902`), there is one run to list, and P2.2 forbids presenting
cross-run causality. Visual sequence *is* a causal claim regardless of copy.

**4. Auto-repair of detached grounds.** Re-pointing a curator's evidence at a different polygon
that happens to overlap **manufactures provenance**. `grounds.js:12-19` deliberately stores only
`region_id` and degrades rather than guessing. If ever built: curator-confirmed, both shapes
shown, never automatic — and that is a build with a gate, not an experiment.

**5. Any uncertainty-arbitration UI.** "Wall or figure — which do you trust?" presents a false
choice between a competent reading and a confident non-answer (spark-04). Out-of-domain
collapse is not channel disagreement, and a UI that asks the curator to adjudicate it teaches
the wrong model of what went wrong.

**6. An Atlas or graph view.** The percept↔region↔block edges are client-side only and
Mentions are reconstructed from block markup by regex at load
(`state/perceptMentions.js:154-170`). A graph over a regex-reconstructed, unpersisted join
would look authoritative while being derived. The join must be real before it is drawn.

**7. Anything on the audience surface.** Covered in §8: the viewer gets the reading, not the
machinery.

**8. — the one I most want to add and will not.** A "corpus evidence health" view showing
"4 of 11 grounds detached, 0 of 15 geometry-bearing". It is the most striking number the R2
program produced and it would make a beautiful panel. Against it: **11 is not a sample.** The
register says so in its own words. A rendered percentage acquires authority that a markdown
note does not; the first time someone reads "36 % of evidence is broken" off a screen, it
becomes a fact about Semant rather than a fact about eleven posts. Ship the number when the
denominator can carry it.

---

*Map ends. Read-only; nothing here is approved for build. Every "NOW" is a proposal for a
reversible experiment, not a decision.*
