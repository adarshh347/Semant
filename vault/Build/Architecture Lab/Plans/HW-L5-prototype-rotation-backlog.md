# HW-L5 · Rotating prototype backlog

**PLANNING ONLY — nothing here is approved for build, and no frontend code was written.**
No `.jsx`, `.js`, `.css`, or `.py` file was created or edited. No build was run, no database was
touched, nothing was staged, committed, or pushed. Code was read only, to check that the items
below are still true after the A2R fix landed.

---

## 0. What this document is, and how it differs from S1, L2 and L3

- **HW-S1** asked *where could circulation intelligence become visible?* → a findings list plus
  five experiments (E1–E5).
- **HW-L3** asked, surface by surface, *what is dull here and does a rotation belong now / later /
  never?* → eight surfaces, two NOWs, seven experiments (L3-X1…X7).
- **HW-L2** asked *what are Atlas and Codex in their narrowest honest form?* → one throwaway mock
  (M1).

**This document asks a fourth question: in what order, and against what dependencies?** It is a
**pull queue**. The orchestrator takes the top unblocked item, runs it, records the result, and the
queue re-sorts. It does not re-discover; where S1/L3/L2 already established a fact I cite the item
id and move on. Where I disagree with them I say so explicitly (§14, kill-list).

**Item ids.** New items are `B-nn`. Where an item is an inherited experiment I keep the original id
in brackets so nothing is silently renamed: `B-03 [L3-X5 / S1-E1]`.

**The governing fact, restated once because every priority below turns on it.** 127 posts, **11
annotated**, **7 percepts**, 26 grounds (11 reference-based, 15 geometry-bearing), 4 detached
grounds on 2 posts, and **exactly 1 `vision_runs` document corpus-wide**. Rehearsal findings are
markdown in the vault and are **not in the database**. More than half of the attractive prototypes
in the ten tracks below would render an empty box today, and I mark each one that would.

**State change since L3 was written.** A2R landed: `recall.js` now takes `lookup` + `{ isResolved }`
built from the real `resolveGround`, and `DifferentialWorkspace.jsx` renders `evidenceNote` beside
the caption (96 frontend tests pass; render-verified on `pctx_mrqp950d_0`). **This retires L3's
first NOW.** The queue below is re-sorted around that, which is the point of having a queue rather
than a list.

**Reversibility criterion used throughout** (inherited from S1 §5, unchanged): no schema change, no
new endpoint, no stored data, no migration, no serialised output — pure derivation from state
already in the client, or a standalone file outside `frontend/src`. Removable by deleting the diff.

---

## 1. Track — Home (`/home`)

**B-11 — the un-deduped Percepts tile, as a screenshot, not a shipped tile.**
`PerceptsTile.jsx:22-32` dedupes region labels case-insensitively before rendering at most 8 chips.
The prototype is L3-X1 **run locally for one session and captured**, not merged: delete the three
dedupe lines (`:25-27`), open the Pietà post's tile, screenshot, revert. It lives in the existing
component for the duration of one session and is undone by `git checkout` of one file.

- **Motivated by:** `CANDIDATE-REGISTER.md` spark-04 (7 regions all `wall`/`floor` on a sculpture)
  plus L3 §2's extension that the dedupe collapses those seven guesses to two chips — *collapse
  hides collapse*. That extension is L3's, not S1's, and it is the only Home finding that is about
  intelligence rather than vocabulary.
- **Must not claim:** nothing, because nothing ships. If it were ever shipped it must not label the
  chips "noticings" or "percepts" — that is the vocabulary error (B-12) and shipping the un-deduped
  tile *while* the word is wrong makes the wrong word louder.
- **Needs more data?** No. One post is sufficient; this is a rendering question, not a rate.
- **Priority: soon.** Cheap, decisive, and it produces an artifact (a screenshot) that settles
  whether label collapse is legible to a human. Not "now" only because B-01–B-02 are cheaper and
  unblock more.

**B-12 — Home vocabulary correction (`percepts` → `parts`).**
`homeData.js:44-50` returns `region_annotations` from a function named `percepts()`; `WeekTile.jsx:28`
and `ContinueTile`/`progressLine` (`homeData.js:70-77`) inherit it. This is a rename across five
components, not a prototype.

- **Motivated by:** S1 §1.1 (the sharpest S1 finding), extended by L3 §2.
- **Must not claim:** it is a *correction*, so it must not be presented as new intelligence, and it
  must not be bundled with any new tile.
- **Needs more data?** No.
- **Priority: later** — and deliberately **not** in the rotation. I agree with L3 that spending the
  rotation budget here buys nothing new. It is a correctness debt that should be paid by whichever
  lane next touches Home for another reason. Queued as maintenance, not as a prototype.

**Home dashboard / evidence-health tile: `never`.** See kill-list K-1.

---

## 2. Track — Chiasm / PostDetail (`/posts/:postId`)

**B-02 [L3-X2] — the silent-at-zero evidence pill in the empty `panel-actions` slot.**
`PostDetailPage.jsx:1041` is a genuinely reserved, genuinely empty slot ("kept for Lane 3 verbs"),
and the page already owns `regionStore` with both `regions` and `grounds`, while `resolveGround`
(`differential/grounds.js:62-85`) is a pure function with an existing test file. The prototype
derives one count — percepts on this post with zero resolving grounds — and renders **nothing at
all** when that count is 0. It is one derived value and one JSX node in a live component, deleted in
one diff.

- **Motivated by:** spark-03 (the register's strongest entry) + `A2R-recall-evidence-honesty.md`
  §"What this does NOT fix", which states that whether **Chiasm's own pane** shows the evidence note
  "was not verified here and should not be assumed". That is a named, unverified gap in a document
  written this cycle — the strongest motivation available on any track.
- **Must not claim:** **a number and a noun, no verb.** No click target, no "repair", no "fix", no
  tooltip offering a next action — the moment it opens something, that something must say what to
  *do*, and that is the unchosen repair fork (D-1). It must never mark the percept, only the
  evidence: "1 percept's evidence not found", never "1 broken percept". It must not appear at zero.
  It must not show a percentage.
- **Needs more data?** No — but it will read `0` on 116 of 127 posts and be invisible on all of
  them. That is the intended behaviour, not a defect.
- **Priority: now.** Highest-value unblocked item in the backlog. It is the one place where a named
  gap from this cycle's own primary lane meets data that is already in the client.

**B-02a — precondition probe: does Chiasm already render `evidenceNote`?**
Before B-02 is written, check by reading the code and one browser session whether the chip→recall
path in Chiasm surfaces A2R's `evidenceNote` or drops it (the element lives in
`DifferentialWorkspace.jsx`). Three sentences of work; no code changes.

- **Motivated by:** A2R names this exact uncertainty.
- **Priority: now**, and it is a **hard dependency of B-02** — if Chiasm already shows the note
  during recall, the pill's justification narrows to the resting state and it may drop to `soon`.

---

## 3. Track — Manuscript / Sutradhar

**B-06 [L3-X3] — derived-only chip dimming, render-time, never serialised.**
`regionRefInline.jsx:62-88` renders the inline chip; `chipAttrs` (`:43-57`) emits four data
attributes and none encode evidence state. The prototype computes a CSS class at render from the
store — exactly the pattern the hover-focus highlight already uses — and **does not touch
`chipAttrs`**. Undone by deleting the class and its CSS rule; the proof of reversibility is that
`blockConvert.test.js` round-trip output is byte-identical.

- **Motivated by:** S1 §2.1.4 (no slot encodes evidence state) + A2R, which fixed the *performance*
  of a dead citation but not its *appearance at rest*. A chip citing `pctx_mrqp950d_0` still renders
  identically to a healthy one until you press ▶.
- **Must not claim:** the mark must never enter `props` or serialised HTML. A stored mark writes a
  snapshot of detachment into durable prose and becomes permanently wrong the moment the region
  returns — and it would silently decide that "unevidenced" is a property of a *sentence*. It must
  not read as an error in the curator's writing. No repair affordance on the chip; that is where a
  "re-point this citation" verb would naturally land and it must not be invited.
- **Needs more data?** No. One detached percept exists and it is the test case.
- **Priority: later.** Blocked behind B-01 (the hydration-race probe) — a false dim inside the
  curator's own prose is the most damaging failure available anywhere in this app, and BlockNote
  re-renders inline content on its own schedule so a transient dim could be sticky.

**Real AI slash commands behind `AI_STUB` (`Manuscript.jsx:77-97`): `never` for this backlog.**
Phase 4 work with its own gate; not circulation intelligence. Removing the dead stubs would be
honest and is maintenance, not a prototype.

**Provenance in the `@` menu subtext: `later`.** Cheap, but it slows the common case (picking a good
part) to serve the rare one. No rehearsal finding motivates it specifically.

---

## 4. Track — Differential workspace

**B-03 [L3-X5 / S1-E1] — RETIRED, replaced by B-03b.**
L3's #1 NOW (the ▶ replay guard) and S1's E1 (honest recall) were **both answered by A2R**, which
took the deeper of the two fixes: `recall.js` now receives `isResolved` from the real
`resolveGround` and reports `unresolvedGroundIds` / `resolvedCount` / `citedCount` with the caption.
Leaving them in a queue would be the queue lying about its own state.

**B-03b — RefPicker resolves before it offers.**
`RefPicker.jsx:26,39-51` builds each percept row's badge as `${p.ground_ids.length} grounds` and
never checks that any resolve; it receives `grounds` but **not** `regions`, so it currently cannot.
The prototype passes `regions` in from `PostDetailPage.jsx` (which already has them) and degrades
the badge only when something fails to resolve — "1 of 2 grounds resolve" / "evidence not found".
One prop and one derived string, deleted in one diff.

- **Motivated by:** S1 §2.1.3 and A2R §"What this does NOT fix", which names `RefPicker` explicitly
  as still offering the detached percept as "2 grounds". This is the *smallest* of A2R's three named
  unfixed surfaces.
- **Must not claim:** degradation-only — a healthy percept's badge must be unchanged, or the mark
  becomes noise. Never "broken", never a warning icon; the neutral register A2R chose
  ("its part was replaced by a re-dissect") already exists and a new alarm vocabulary is a
  regression. No repair suggestion, no "did you mean `arch_2`?" — that fabricates curator intent.
- **Needs more data?** No, but see the kill condition: if the percept picker is never used, the
  badge never fires. S1-E2 flagged this and it is still unmeasured.
- **Priority: soon.** It is the cheapest honest propagation of the A2R fix, and A2R's own document
  asks for it. Sequenced after B-01 because it inherits the same hydration race.

**B-01 — the hydration-race probe (renders nothing).**
`regionStore.js:94-119` loads regions and grounds in the same effect. If grounds land before
regions, *every* region-ground reports detached for a frame. A dev-only counter that logs, per post
load, whether a transient all-detached frame occurs and for how long. Nothing renders; it is a
temporary log deleted with the diff.

- **Motivated by:** this is the single most-named killer across both prior scouts — S1 flagged it
  against E1, L3 flagged it against X2, X3 and X5. **Three independent experiments share one killer
  and nobody has measured it.** That is precisely what a backlog is for and it is why this is the
  first item in the queue.
- **Must not claim:** nothing; it displays nothing.
- **Needs more data?** No.
- **Priority: now.** It is the cheapest item in the backlog and it de-risks three others.

---

## 5. Track — Vision Activity Rail

**B-04 [L3-X6] — count what the rail would have shown, without showing it.**
Instrument `useVisionActivity`'s existing results in a dev-only counter recording, per post visited,
how many of the four operations (`dissect`, `refine`, `semantic_read`, `find_similar`) return a run.
Renders nothing; a temporary log, deleted with the diff.

- **Motivated by:** L3 §7 and S1 §1.2 both conclude the rail's blocker is telemetry density, which
  is currently known only as the number "1 document in the DB" — a figure that says nothing about
  *which* operations record and how often.
- **Must not claim:** nothing rendered. When the density question is eventually answered in prose,
  it must not be stated as a rate over 127 posts.
- **Needs more data?** No — it *produces* the data everything else on this track waits for.
- **Priority: now.** It is an hour of work and it is the gate on B-05, the run stamp, and every
  Codex idea.

**B-05 [S1-E5] — the rail's closed summary distinguishes non-nominal states.**
`VisionActivityRail.jsx:124-133` folds `partial`, `timed_out` and `stale` into `"N recorded"`. The
derivation would belong in `visionActivity.js` to stay unit-tested.

- **Motivated by:** S1 §1.2. Real, and currently **unmeasurable**.
- **Must not claim:** no cross-run causality; the rail's existing scope disclaimer
  (`VisionActivityRail.jsx:152-154`) must survive any copy change.
- **Needs more data?** **Yes, decisively.** With one run corpus-wide the summary reads "nothing
  recorded yet" essentially always, so the experiment cannot be evaluated.
- **Priority: later** — hard-blocked on B-04 returning a non-trivial density.

**Moving, promoting, or default-opening the rail: `never`.** I agree with L3 §7 against the obvious
instinct: promoting it spends the disclosure affordance before there is anything to disclose, and
teaches dismissal. Its placement should be **defended**.

**Cross-post run timeline / history: `never` at this layer.** See kill-list K-2.

---

## 6. Track — Aletheia / semantic read

Two different things share this name and they get opposite verdicts.

**B-13 [L3-X7] — measure the hollow-lens rate, curator-side only, rendering nothing.**
`AletheiaHook.jsx:105-106` filters `region_annotations` by `lens.region_ids`; if a re-dissect
replaced them the filter yields `[]`, the `<svg>` draws zero tappable shapes, and the hint at
`:160-165` never appears. The prototype is the *same one-line filter* run as a read-only probe over
the annotated posts, counting lenses whose ids no longer resolve. It can piggyback on B-01/B-04.

- **Motivated by:** S1 §1.7 and L3 §8. Note honestly: **no rehearsal has measured lens-level
  detachment.** It is inferred from the ground-level mechanism (A2S), never observed. That is the
  whole reason to measure before modelling.
- **Must not claim:** nothing rendered, and **nothing audience-facing ever**. If the rate is
  non-zero, the honest response is still not to display detachment to a viewer — the surface already
  degrades correctly by accident (`:160` gates the hint on `regions.length > 0`).
- **Needs more data?** No — it is a measurement over existing posts. Likely outcome is a rate of
  **zero**, which would be a valuable "no".
- **Priority: soon.** Trivial cost, and a zero result kills an entire speculative model (a
  lens-resolution analogue of `resolveGround`) before anyone builds it.

**Any circulation/rehearsal display on `/read/:postId`: `never`.** The audience gets the reading,
not the workshop. Exposing run ids, stages, adapters or detachment counts to a viewer converts a
reading into a machine report. `AletheiaHook.jsx:219` ("session `abc123…` — an opaque id, not you")
is the model of the register this surface should keep.

**`SemanticReading.jsx` (the curator's assertion panel): no prototype proposed, and that is the
finding.** It already does status, confidence bars, accept/edit/reject/tentative, and a
"needs better evidence → Refine" handoff. S1 §2.3 is right that it is a *model to imitate*, not a
gap. **Nothing motivates a prototype here. Marked `never` for this backlog** — the honest entry on a
well-built surface is "leave it alone".

---

## 7. Track — Atlas prototype

**B-08 [L2-M1] — the "Evidence Ledger" static HTML mock.**
One standalone hand-built HTML file, outside `frontend/src`, wired to nothing, with numbers
transcribed by hand from `R2/evidence/A2S-detached-ground-sweep.json`. Eleven rows, a header saying
"showing 11 of 127", counts with visible denominators, and a Codex panel that mostly says "no record
exists". Deleting the file removes 100% of it; it cannot flicker, cannot race, and no user reaches it.

- **Motivated by:** spark-03 + A2S. But note L2's own honest verdict: **eleven rows is a paragraph,
  not a surface**, and L2 says that is the strongest argument against Atlas in any form.
- **Must not claim:** **36.4%, or any rate, must never appear.** Absolute counts with the
  denominator always visible, or nothing. No edges, no adjacency-implies-relation, no ordering that
  reads as argument. No cross-run causality — co-reference only ("this run and this ground both
  reference `fine_3`"), never "this run detached this ground", even though that is almost certainly
  what happened, because *almost certainly* is not *observed*. It must never mark the curator's
  statement wrong: "the upper head" is not incorrect because its regions were replaced. It must not
  read as a recommendation to prefer geometry-bearing grounds (0 of 15 detached vs 4 of 11) — that
  would push curators to duplicate geometry and break the canonical-representation invariant.
- **Needs more data?** **The mock does not** — that is the point of a mock. Anything downstream of
  it does.
- **Priority: later.** L2's own sequencing note said M1 should follow S1-E1. E1 has now landed via
  A2R, so that gate is *passed* — but a second gate replaced it: the mock tests **presentation of a
  problem**, and we still do not know whether the problem is *felt*. B-02 and B-03b are the cheaper
  ways to find that out, and both must return before the mock is worth drawing.

**Any Atlas route, nav entry, `PlaceholderPage`, node/edge canvas, or feeding endpoint: `never`.**
Naming a stub is a commitment; `/atelier` and `/you` are already stubs and adding more is not free.
The moment anyone proposes an endpoint to feed the mock, the mock should be killed rather than
promoted.

---

## 8. Track — Codex prototype

**B-14 — the "no record exists" panel, as one paragraph inside B-08, never as its own artifact.**
Codex's honest first output is a panel answering one question — *"This percept is unevidenced today.
Was it always? What operation is recorded between then and now?"* — whose answer on this corpus is
almost entirely **"no record exists for this period."** It has no separate prototype; it is a
section of the B-08 mock.

- **Motivated by:** L2 §2 — for `pctx_mrqp950d_0` the re-dissect is **inferred, not observed**;
  there are 0 `vision_runs` for that post and 1 corpus-wide. Nothing else motivates it.
- **Must not claim:** no reconstruction of the pre-instrumentation past, no greyed-out "probable"
  entries, no inference of the re-dissect from region generation names (`fine_*` → `arch_*`) — A2's
  critique already refused that inference and a UI must not un-refuse it. No implied agency: not
  "the system replaced your regions"; when `initiator` is null the honest word is "unknown". No
  narrative of development ("this detail became a principle") — that needs durable Mentions, which
  do not exist.
- **Needs more data?** **Yes, more than any other item.** Its substrate is one document. Codex can
  today speak about grounds and regions (persisted on the post) and cannot speak about citations
  across works at all, because the Mention has no durable form and lives in editor markup
  reconstructed by regex (`perceptMentions.js:154-170`).
- **Priority: later**, and only as B-08's tail. **A standalone Codex prototype is `never`** for this
  cycle: it would be a surface built over one row.

---

## 9. Track — evidence health

**B-07 — corpus evidence-health view (any form).**
"4 of 11 reference grounds detached, 0 of 15 geometry-bearing" is the most striking number the R2
program produced and would make a beautiful panel.

- **Motivated by:** A2S, spark-03. The finding is real.
- **Must not claim:** everything in B-08's list, but the binding one is that **11 is not a sample**.
  A rendered percentage acquires an authority a markdown note does not; the first time someone reads
  "36% of evidence is broken" off a screen it becomes a fact about Semant rather than a fact about
  eleven posts.
- **Needs more data?** **Yes.** See §12 for the specific denominators.
- **Priority: never as a production surface at this corpus size; later as the B-08 mock's summary
  block.** This is L3's §10.8 — "the one I most want to add and will not" — and I agree with it,
  which is why it appears here as a *deferred* track rather than an omitted one. A backlog that
  quietly drops the most attractive idea is not being honest about the temptation.

**B-09 — per-region provenance, actor only.**
`RegionSurface.jsx:486-494`, one muted word per row: "you" vs "detected". `actor` is the **only**
provenance field with demonstrated frontend presence (`RegionOverlay.jsx:21` reads it;
`RegionSurface.jsx:214-223` writes `detector: null` for creator marks).

- **Motivated by:** S1 §1.4 / E3, narrowed by L3 §5 to remove E3's data-availability risk.
- **Must not claim:** it must read as **origin**, never as **score** and never as blame. No
  `confidence` number — spark-04 is explicit that "wall at 0.91 vs figure at 0.44, which do you
  trust?" is a **false choice**: an out-of-domain segmenter is confidently non-answering, not
  disagreeing, and a confidence figure would give the wrong answer institutional weight.
- **Needs more data?** A **data check** first — whether `actor` is populated and varied on stored
  regions. If it is uniformly `'detector'`, every row gains a word and no information.
- **Priority: later**, gated on that check (see §12, DATA-4).

**B-10 — the dissect run stamp.** `RegionSurface.jsx:180-181` discards `run_id` returned by the
backend (`posts.py:875`).

- **Motivated by:** S1 §1.3 / E4.
- **Must not claim:** a run id is an identifier, not an explanation. It must not sit next to any
  wording implying the run *caused* anything.
- **Needs more data?** **Yes** — with 1 run corpus-wide it renders blank on essentially every post.
- **Priority: later.** I side with L3 against S1 here (see K-5): shipping a permanently blank UI
  element to prove a backend point is a bad trade. Gated on B-04.

---

## 10. Track — rehearsal trace viewer

**No prototype is proposed on this track, at any priority, and this is the firmest entry in the
document.**

- **What motivates it: nothing.** S1 §6 searched and found no component, hook, route or data shape
  in `frontend/src` corresponding to the rehearsal program. L3 §10.1 confirms it. The findings are
  markdown on disk under `vault/Build/Architecture Lab/Vision pipeline/rehearsals/` and are **not in
  the database**, so no surface can display them without an ingestion path, a schema, and a decision
  about what a rehearsal *is* as a durable object.
- **Must not claim:** Passage-001's trace is **100% reconstructed with null telemetry throughout**;
  its own `missing-telemetry.md` says it "can support no construct beyond SPARK". Rendering it as
  product history would launder a reconstruction as a record.
- **Priority: never.** `CANDIDATE-REGISTER.md` opens by declaring that nothing in it is "a
  candidate, a decision, an approved design, or a durable object". A viewer would be **invention
  presented as exposure** — the worst failure mode available in this program, because it would give
  research speculation the visual authority of recorded fact.

If the orchestrator ever wants rehearsal findings visible, the honest artifact is a **vault page**,
which already exists and is already read by humans. That is not a frontend track.

---

## 11. The ordered queue

Pull from the top; take the first item whose dependencies are all satisfied. Items in the same
bracket may run in either order.

| # | item | track | cost | depends on | why here |
|---|---|---|---|---|---|
| 1 | **B-01** hydration-race probe | Differential/store | ~1h | — | **Three separate experiments (B-02, B-03b, B-06) name the same killer and nobody has measured it.** Measuring it once is cheaper than each of them discovering it. |
| 2 | **B-04** rail telemetry-density counter | Rail | ~1h | — | Renders nothing; produces the number that gates B-05, B-10 and all of Codex. Currently we know "1 document" and nothing about *which* operations record. |
| 3 | **B-02a** does Chiasm show `evidenceNote`? | Chiasm | ~1h | — | A2R names this as unverified. B-02's justification depends on the answer. Reading, not writing. |
| 4 | **B-02** silent-at-zero evidence pill | Chiasm | ~½ day | B-01, B-02a | The strongest build item: a named unfixed gap from this cycle's own primary lane, over data already in the client, in the one genuinely empty affordance in the app. |
| 5 | **B-03b** RefPicker resolves before offering | Differential | ~2h | B-01 | The cheapest propagation of A2R, requested by A2R itself. Sequenced after B-02 because B-02 tests the *register* ("evidence not found" vs blame) on a smaller surface first. |
| 6 | **B-13** hollow-lens rate probe | Aletheia | ~1h | — | Renders nothing. A zero result kills a whole speculative model (lens-resolution) before anyone builds it. Can be batched with B-01/B-04 if convenient. |
| 7 | **B-11** un-deduped Percepts tile, screenshotted | Home | ~1h | — | Settles whether label collapse is legible to a human. Produces an artifact, not a merge. |
| 8 | **B-08 + B-14** Evidence Ledger mock (incl. Codex panel) | Atlas/Codex | ~½ day | B-02, B-03b | Tests *presentation* of a problem that items 4–5 will have established is *felt*. Building it earlier risks designing a surface for a complaint nobody has. |
| 9 | **B-06** derived-only chip dimming | Manuscript | ~1 day | B-01, B-02 | Highest ontological risk on the list and the most damaging failure mode (a false accusation inside the curator's prose). It goes last among the build items, after the register has been proven on two lower-stakes surfaces. |

**Below the line — not pulled this cycle, listed so the order is explicit when they unblock:**
B-05 (rail summary) after B-04 returns density; B-10 (run stamp) after B-04; B-09 (actor row) after
DATA-4; B-12 (Home vocabulary) as maintenance whenever Home is next touched; B-07 never as a
surface.

### Why this order, argued

**Measurement before rendering.** Items 1, 2, 3 and 6 render **nothing at all**. Four of the top six
produce no pixels. That is not timidity — it is the honest shape of a cycle in which two independent
scouts concluded the correct move was *not to build a surface yet*, and it is the cheapest way to
convert three "killed by:" clauses into facts.

**Shared killers get measured once.** B-01 is first purely because it is a dependency of three
downstream items. A queue's whole advantage over a list is that it can see this.

**Escalating ontological risk.** B-02 asserts a count (smallest commitment on the repair fork).
B-03b degrades a badge at the point of citation. B-06 marks the curator's own durable prose. The
register — "evidence not found", never "broken" — is proven on the cheap surface before it is
carried to the expensive one. If B-02 reads as blame, B-06 must never be attempted.

**The mock is downstream of the fix, not upstream.** L2 sequenced M1 after S1-E1 on the grounds that
E1 answers whether the problem is felt. A2R satisfied E1 mechanically but *not* observationally — it
proved the system misbehaved, not that a curator minded. B-02 and B-03b are the observations. The
mock follows them.

**A2R's own to-do list drives two slots.** A2R names three unfixed surfaces: Chiasm's chip path
(→ B-02a/B-02), `RefPicker` (→ B-03b), Aletheia (→ B-13). All three are in the top six. A backlog
that ignored the primary lane's own stated gaps in favour of new ideas would be discovery cosplaying
as sequencing.

---

## 12. Blocked on data

Each entry says **what specifically must grow, and by how much**, because "more data" is not a gate.

**DATA-1 — telemetry density.** *Blocks:* B-05, B-10, all of B-14/Codex, any run history.
*Current:* **1 `vision_runs` document corpus-wide**, for a post unrelated to the detached ones.
*Needed:* runs recorded for a **majority of dissect operations across at least ~20 posts**, spanning
more than one of the four instrumented operations. The threshold that actually matters is
qualitative: a curator should be able to open the rail on a post they just worked on and see
something. Until then every rail rotation renders "No recorded activity".
*Note:* B-04 does not need this — it **measures** it, which is why it is queued second.

**DATA-2 — annotated corpus size.** *Blocks:* B-07 as a surface, B-08 as anything more than a mock.
*Current:* **11 annotated posts of 127; 7 percepts; 26 grounds (11 reference-based, 15
geometry-bearing); 4 detached grounds on 2 posts.**
*Needed:* enough that a denominator can carry a proportion. I will not invent a number, but the
shape is clear — the reference-vs-geometry contrast (4/11 vs 0/15) needs **both arms in the
double digits with multiple independent posts contributing to each**, otherwise a single
re-dissected post dominates the comparison. Today, two posts produce the entire finding.

**DATA-3 — detachment incidence over time.** *Blocks:* graduating spark-03 past SPARK (the R3 bar is
≥3 fixtures + a transfer test + a negative case).
*Current:* 2 affected posts, one of them uncited.
*Needed:* **≥3 independent fixtures** of detachment arising, plus a negative case (a re-dissect that
does **not** detach anything), plus the transfer test. Note the spark's own kill condition:
detachment becoming rare once dissection stabilises would kill it.

**DATA-4 — region provenance field population.** *Blocks:* B-09.
*Current:* `actor` is the only field with demonstrated frontend presence; `detector` is written
`null` for creator marks; `confidence` was never verified to be stored at all.
*Needed:* a **read-only data check** over stored regions establishing what fraction carry a non-null
`actor`, and whether it varies. If `actor` is uniformly `'detector'`, B-09 dies.

**DATA-5 — lens-level detachment incidence.** *Blocks:* any lens-resolution model.
*Current:* **never measured; inferred only.**
*Needed:* B-13's probe. A rate of zero is the likely and most useful outcome.

**DATA-6 — is the percept picker used at all?** *Blocks:* the *value* (not the build) of B-03b.
*Current:* unknown. S1-E2 flagged it and it was never measured.
*Needed:* any usage signal. If curators never re-cite old percepts after a re-dissect, B-03b's badge
never fires.

---

## 13. Blocked on decision

These wait on an orchestrator judgement, not on data or code.

**D-1 — the repair fork: tombstone vs notify vs neither.** *Blocks:* any affordance attached to any
detachment mark; the wording of B-02, B-03b and B-06; all of B-07/B-08's framing.
Tombstoning old regions so grounds resolve to *something*, versus notifying and letting the curator
re-point, are **different theories of what evidence is**. A2S left it open on purpose; A2R deliberately
did not repair the four detached grounds. HB-002 §8 escalates it: A2R proved the system can *perform*
absent evidence convincingly, which raises the stakes without answering the question. **Every item in
this backlog is designed to be neutral on this fork** — counts and marks only, no verbs — and that
neutrality is what lets them proceed while D-1 is open. The moment any mark acquires a click target,
the fork has been silently chosen.

**D-2 — how loudly should the app admit its own gaps?** *Blocks:* whether B-03b, B-06 and B-13's
follow-through happen at all. HB-002 §8.4 poses it exactly: the A2R fix *could* propagate to Chiasm,
`RefPicker` and Aletheia, and "each is also a decision about how loudly the app should admit its own
gaps." Three quiet marks in three places may add up to something louder than any one of them was
approved to be. This is a judgement about register, and no probe answers it.

**D-3 — is corpus density now the binding constraint on everything?** *Blocks:* the entire Atlas /
Codex / evidence-health cluster. HB-002 §8.2: two independent scouts concluded separately that the
honest move is not to build a surface yet. If the answer is yes, the correct next investment is
**annotating posts and instrumenting the backend**, not prototyping — and items 8 and below in the
queue should be suspended rather than pulled.

**D-4 — does the vocabulary correction (B-12) block anything that names a percept?** If `percepts()`
continues to return `region_annotations` on Home while B-02 counts *real* percepts in Chiasm, the app
holds two definitions of the word simultaneously on two surfaces. That may be tolerable for one
cycle. It is a decision, not an accident, and should be made deliberately.

**D-5 — is a screenshot-only prototype (B-11) an acceptable deliverable?** It produces no merged
code and no artifact in the product. If the orchestrator requires every rotation slot to end in
reviewable code, B-11 should be re-scoped or dropped rather than run and discarded.

---

## 14. Kill-list

Ideas that look attractive and should be explicitly rejected. The first three are argued against
**prior scouts' own proposals** where I disagree; the rest are standing rejections that keep
resurfacing.

**K-1 — a circulation / evidence-health tile on `/home`. Reject.**
Tempting because Home is the most-visited authenticated surface and the most epistemically dull.
Against it: Home is where a **word becomes a fact**. `percepts()` returns `region_annotations`
(`homeData.js:44-50`), and the taste portfolio, the week counters and the progress line all
accumulate as evidence for that definition. Adding accurate machinery on top of an inaccurate claim
fossilises the claim. Also: `homeData.js:14-17` fetches the posts list and never reads
`post.percepts` or `post.grounds`, so resolving anything client-side on Home means loading grounds
and regions for 24 posts to render 8 chips. Both prior scouts reached this and I am hardening it
from "later" to **reject**.

**K-2 — a per-post or cross-post run timeline. Reject, and reject the endpoint that would enable
it.** No list endpoint exists (only `latest` and `by-id`, `posts.py:890,902`), there is **one run**
to list, and P2.2 forbids cross-run causality. The decisive argument is not the missing endpoint —
it is that **adjacency in a timeline is a causal claim regardless of the copy**. Readers will read
sequence as consequence. Within a *single* run, `dependencies` (stage_id strings) may be drawn,
because that is recorded rather than inferred. Across runs, never. And the fact that this is
cheap-to-want and expensive-to-un-imply is exactly why it belongs on a kill-list rather than in a
"later" bucket where it will keep being re-proposed.

**K-3 — S1's E4, the dissect run stamp, at "very small cost" priority. Reject the priority, keep
the item.** S1 rated it very small and implied it was near-term; its defence was that emptiness "is
itself the finding". I side with L3 and go further: **that argument proves the finding does not need
a widget.** A UI element that is permanently blank is not a diagnostic, it is a broken-looking
product feature, and once shipped it creates pressure to fill it — which is pressure toward the
backend endpoint in K-2. B-10 stays in the backlog gated on DATA-1 and must not be pulled before it.

**K-4 — auto-repairing detached grounds by IoU re-match. Reject permanently.**
Silently re-pointing a curator's evidence at a different polygon that happens to overlap
**manufactures provenance** — a forged citation. `grounds.js:12-19` deliberately stores only
`region_id` and degrades rather than guessing. A2R explicitly declined to repair. If it is ever
built it must be curator-confirmed with both shapes shown, never automatic — and that is a build
with a gate, not a prototype, and not on this backlog.

**K-5 — an uncertainty-arbitration UI ("wall at 0.91 or figure at 0.44 — which do you trust?").
Reject.** spark-04 is explicit that this stages a **false choice** between a competent reading and a
confident non-answer. An ADE20K-style segmenter with no sculpture class emits its nearest
architectural labels with no signal that it is out of domain; a confidence number gives that
non-answer institutional weight and teaches the curator the wrong model of what went wrong. This
also kills `confidence` as a rendered field anywhere, which is why B-09 is narrowed to `actor`.

**K-6 — a rehearsal trace viewer, in any form. Reject.** §10. Invention presented as exposure, over
a trace that is 100% reconstructed with null telemetry.

**K-7 — an Atlas node/edge graph over percept↔region↔block. Reject.** The join is client-side only
and Mentions are reconstructed from block markup **by regex at load**
(`perceptMentions.js:154-170`). A graph over a regex-reconstructed, unpersisted join would look
authoritative while being derived. **The join must be real before it is drawn.** Both prior scouts
say this; I add only that the fix is not "draw it carefully", it is "do not draw it".

**K-8 — a live hero on Landing pulling the most recent real region. Reject.**
The most recent real region in this corpus is plausibly `wall` on a sculpture or `tie knot` on a
painting. A live hero would put a detector's out-of-domain failure on the front door as the
product's best example of itself. The mock labels ("the drape") are **more honest about the intent**
than a live pull would be about the state. Additionally, wiring Landing to `region_annotations`
would establish at the most visible point in the app that a detector box is a "noticing" — the
vocabulary error, committed twice, becomes load-bearing.

**K-9 — any percentage, rate, ratio, progress bar or "corpus health: N%" in any interface. Reject
categorically.** **36.4% must never appear.** Absolute counts with the denominator always visible,
or nothing. This is a rule, not a preference, and it applies to the B-08 mock as strictly as to
production.

---

## 15. One line

The queue's first four items render nothing at all, its fifth is a number that is invisible on 116
of 127 posts, and its most attractive idea is on the kill-list — which is the correct shape for a
cycle whose strongest finding was that two independent scouts, working separately, both concluded
the honest move was not to build a surface yet.

---

*Backlog ends. Planning only; nothing here is approved for build, and no frontend code was written.
Every item is a proposal for a reversible experiment, not a decision.*
