# HW-L2 — Atlas / Codex prototype brief

**PROTOTYPE BRIEF — research-only, no implementation authorized, Atlas and Codex do not exist in
code.** Every "Atlas" string in the repository is MongoDB Atlas (`backend/database.py`), Atlas
Vector Search (`region_embedding_service.py`), or the doc title "P0.5 Contract Atlas"
(`vision_run_contracts.py` module docstring). "Codex" has zero code hits. This brief proposes one
throwaway frontend mock for **later** approval and nothing else. No source file was edited, no
schema, route, or collection is proposed, no database was touched, nothing was committed.

Extends `vault/Concepts/HW-S2-atlas-codex-conceptual-scout.md` (the conceptual scout) — that
document's inventory, prohibitions, and dangers are assumed, not restated. Read it first.

Marking convention used throughout: **[EXISTS]** = verified in a file I read or a sweep already
run · **[SUPPORTED]** = an inference the evidence carries · **[SPEC]** = speculation, mine, not
established by any rehearsal.

---

## 0. What this brief is trying to change

HW-S2 ended by saying Atlas's centre of gravity has moved from *narrative arrangement* to
*comparative honesty across images*, and Codex's from *long-form container* to *the layer at which
change over time is answerable*. That is a conclusion, not a direction. This brief takes the next
step only: it asks what the **narrowest honest version of each** would be if it were ever built,
and what it would have to refuse to say.

The framing discipline throughout: HW-S1 drew the dividing line and it is the right one —
**existing surfaces answer "is what I'm looking at real?"; Atlas answers "what has happened across
everything?"** Everything below that fails that test belongs in `RegionSurface`, `RefPicker`, or
the recall path, not in a new surface. HW-S1's E1–E5 already own that territory and this brief does
not compete with them.

---

## 1. Atlas as a comparative EVIDENCE-HEALTH surface

**Not** a Warburg plate wall. **Not** a node/edge canvas. **Not** "the arrangement is the prompt."
Those remain prose (HW-S2 §5 danger 2 — the typed-edge vocabulary is self-confirming and untested
against a single fixture).

The narrow version: **a read-only comparative view of the corpus's evidence health, one row per
annotated post.** Its unit is not a beat or a motif; it is *a curator statement and the state of
what backs it*.

### What comparison does this enable that no current surface does?

Concretely, and each grounded:

- **[EXISTS]** Detachment is modelled (`grounds.js:68-85 resolveGround`) and rendered in exactly
  one place: `DifferentialWorkspace.jsx:803-812`, a list inside one workspace mode of one post
  (HW-S1 §0). There is no surface anywhere that compares *two posts*. A2S had to be a Python script
  (`scripts/detached_ground_sweep.py`) precisely because the app cannot ask its own corpus a
  question.
- **[EXISTS]** The clean contrast — 4 of 11 reference-based grounds detached, **0 of 15**
  geometry-bearing — is invisible to the person whose evidence it is. A curator choosing between
  drawing a `field` and adapting a region gets no signal that one of those choices has historically
  survived re-dissection and the other has not.
- **[EXISTS]** Two affected posts (`695be786`, `695be794`) were found only because the sweep was
  *corrected* to count uncited detached grounds; the first version hid an entire post (A2S method
  notes). Nothing in the product performs even the uncorrected version of that count.
- **[SUPPORTED]** The comparison Atlas uniquely enables is therefore: **"which of my statements are
  still backed, and does that correlate with how I made them?"** No per-post surface can answer a
  question whose subject is the set of posts.

### What it must NOT be, stated as design constraints, not aspirations

- Not authoritative. **[EXISTS]** The Infrastructure Lexicon already supplies the word:
  a Percept-usage summary "could be a **materialized view** rather than the authoritative source."
  A derived view over data that can silently rot must never become the place truth is stored
  (HW-S2 §5 danger 3).
- Not a graph. **[EXISTS]** The percept↔mention join is reconstructed by regex from BlockNote markup
  at load (`perceptMentions.js:154-170`, per HW-S1 §4.4). Drawing a graph over a regex-derived,
  unpersisted join makes a derived artifact look authoritative.
- Not a place to repair. A2S deliberately left tombstone-vs-notify open; a surface that shows
  detachment and offers a fix has silently chosen (HW-S2 §5 danger 5).

### Is the corpus large enough to justify this surface?

**No, and I will not pretend otherwise.** 11 annotated posts, 7 percepts, 26 grounds, 11 of them
reference-based. An "evidence health across the corpus" view is, today, **a table with eleven rows,
two of which are interesting.** That is not a surface; it is a paragraph. This is the single
strongest argument against building Atlas in any form right now, and it is stronger than any
argument for it. The mock in §7 exists to test whether the *presentation problem* is real, at a
scale where a table of eleven rows is adequate — not to ship a dashboard.

---

## 2. Codex as a temporal / accountability layer

**Not** a multi-page editor. **Not** Works and Pages and backlinks and a Scrivener clone. HW-S2 is
right that the container is the least interesting and most imitable part, and R0's prohibition
("no Atlas, Codex, or cross-image structure") is not lifted by anything here.

The narrow version: **the layer that can answer "what happened to this piece of evidence, and
when?" — and, crucially, that can say "I do not know" for the period before instrumentation.**

### What question about change-over-time would it answer?

One question, precisely: **"This percept is unevidenced today. Was it always? If not, what
operation was recorded between then and now?"**

Note carefully what that question does *not* ask. It does not ask *why*. It does not ask *what
caused it*. It asks what is recorded, and in what order those records were observed.

- **[EXISTS]** For `pctx_mrqp950d_0` — the curator's own words, "the upper head" — the answer today
  is *unknowable*. A2's critique states it: the re-dissect that stranded `fine_0`/`fine_3` is
  **inferred, not observed**; there are 0 `vision_runs` for that post.
- **[EXISTS]** Corpus-wide there is **1** `vision_runs` document. The telemetry that would answer
  this question began after the events it would explain.
- **[SUPPORTED]** Therefore Codex's honest first output on the existing corpus is almost entirely
  the sentence **"no record exists for this period."** That is not a failure of the idea; it is the
  idea working. A temporal layer whose first act is to admit the past is unrecoverable is more
  trustworthy than one that reconstructs it.
- **[SPEC]** Whether curators find "no record exists" useful, or merely irritating, is untested.
  That is the one thing a mock could cheaply learn.

### The dependency Codex does not have

**[EXISTS]** Codex's every interesting claim — cross-page citation, "which chapters embody
restraint" — is a query over Mentions, and the Mention has no durable form (R0; HW-S1 §4.4).
R2.0 verified the percept→chip→recall loop works once, in a browser, **unsaved**. So the temporal
layer can today speak about *grounds and regions* (which are persisted on the post) and about
*vision_runs* (one document), and cannot speak about *citations across works* at all.

That asymmetry should govern any prototype: **Codex may look backward at evidence; it may not yet
look sideways at prose.**

---

## 3. What evidence each would show — from data that exists today

Only sources I verified. Nothing here requires a new field, and I flag every case where it would
require a new *endpoint*, which is a backend change and therefore out of scope.

| Source | Status | Atlas could show | Codex could show |
|---|---|---|---|
| `post.grounds` (26 corpus-wide) | **[EXISTS]**, persisted | per-post ground counts split by type; the reference-vs-geometry contrast | ground `created_at` — `makeGround` stamps it (`grounds.js:48`) |
| `resolveGround` detachment | **[EXISTS]**, pure client fn | which grounds resolve, per post | nothing temporal — detachment carries no timestamp |
| `post.percepts` (7) | **[EXISTS]** | which percepts are fully / partly / not evidenced | — |
| `post.region_annotations` | **[EXISTS]** | region generation (`fine_*` vs `arch_*` vs `seg_*` vs `refine_*`) | the *generation label itself* is the only surviving trace of a re-dissect on the affected posts |
| `vision_runs` (**1** doc) | **[EXISTS]** | essentially nothing — n=1 | `operation`, `status`, `actual_source`, `created_at`/`completed_at`, `events[]` with `stage_id`/`observed_at`/`latency_ms`, `telemetry_degraded` — all real fields on `VisionRunOut` |
| stage events | **[EXISTS]** in contract | — | stage list in **observation order**; `dependencies` are stage_id strings and are the *only* sanctioned causal representation, within one run |
| rehearsal traces on disk | **[EXISTS]** — 6 `trace.json` under `rehearsals/runs/` | — | nothing, without invention: **[EXISTS]** HW-S1 §6 confirms there is no frontend concept of rehearsals at all, and Passage-001's trace is 100% reconstructed with null telemetry |

Three hard limits that bound every row above:

1. **[EXISTS]** There is **no list/history endpoint** for vision runs — only
   `GET /{post_id}/vision-runs/latest?operation=` and `GET …/{run_id}`
   (`backend/routers/posts.py:890,902`). Any timeline is a backend change, not a frontend
   experiment. This alone disqualifies a "run history" prototype.
2. **[EXISTS]** `run_id` is returned by the dissect route and discarded by the client at
   `RegionSurface.jsx:181`. Nothing in the app has ever displayed one.
3. **[EXISTS]** Rehearsal traces live in the vault, not the database, and are research artifacts of
   a program that explicitly forbids production surfaces. Showing them in the product would be
   invention, not exposure.

**Consequence, stated plainly:** of the two, only **Atlas has enough data to render anything at
all**, and only barely. Codex's substrate is one document.

---

## 4. What each MUST NOT CLAIM

Firm, specific, and non-negotiable for any future prototype.

### Both surfaces

1. **No cross-run causality, ever.** **[EXISTS]** P2.2's contract: "Each operation is a standalone
   block — never a step in one invented chain, never a causal arrow… Shared region ids read as
   'Referenced …', never 'caused by' / 'followed from'." A prototype may say *"this run and this
   ground reference region `fine_3`."* It may **not** say *"this run detached this ground"* — even
   though that is almost certainly what happened on `695be786`, because *almost certainly* is not
   *observed*, and A2's own critique says so.
2. **No implied completeness.** With 11 annotated posts, any total, percentage, ratio, progress
   bar, or "corpus health: 82%" is a fabricated baseline. **[EXISTS]** A2S pre-empted this: "with
   n = 11 the percentage should not be quoted as a corpus property." **36.4% must never appear in
   an interface.** Absolute counts with the denominator always visible, or nothing.
3. **No authority over the curator's own words.** A percept is a curator statement. The surface may
   report the state of the *evidence cited by* that statement. It may never mark the statement
   itself wrong, stale, invalid, low-quality, or in need of revision. "The upper head" is not
   incorrect because its regions were replaced; the system lost the regions.
4. **No claim about the past before instrumentation.** For every event predating the circulation
   spine, the only honest output is "not recorded." No reconstruction, no inference-presented-as-
   history, no greyed-out "probable" entries.
5. **No completeness claim about operations either.** **[EXISTS]** Only four operations are
   instrumented (`dissect`, `refine`, `semantic_read`, `find_similar`). A timeline of those must
   not read as a timeline of everything that happened to a post.

### Atlas specifically

6. **No claim that a durability difference is a recommendation.** **[EXISTS]** A2S: "durability is
   only one axis"; the region adapter's reference semantics are deliberate. Showing 0/15 vs 4/11
   next to each other and letting it read as *"draw fields instead"* would push curators toward
   duplicating geometry, breaking the canonical-representation invariant (HW-S2 §5 danger 6).
7. **No arrangement semantics.** No edges, no adjacency-implies-relation, no ordering that reads as
   argument. A sorted table is a sorted table; a canvas where proximity means kinship is a claim.
8. **No claim to cover the corpus.** 116 of 127 posts carry no annotation. A view showing 11 rows
   must say it is showing 11 of 127, every time.

### Codex specifically

9. **No narrative of development.** "This detail became a principle" is the aspiration
   (`semant-rehearsal-aspiration.md`) and it is exactly the sentence the data cannot support — it
   requires durable Mentions across a long work, and Mentions live in editor markup.
10. **No implied agency.** Not "the system replaced your regions." A run record has an `initiator`
    field, populated opportunistically; when it is null the honest word is "unknown," not a guess.

---

## 5. How detached evidence appears — the honest presentation problem

This is the hardest requirement in the brief and the one most likely to be got wrong.

**Three states must be visually distinct, and none may read as curator error:**

- **intact** — every cited ground resolves;
- **partly detached** — some resolve;
- **fully unevidenced** — none resolve (today: exactly one percept, `pctx_mrqp950d_0`).

**[EXISTS]** Today all three render identically almost everywhere. HW-S1 traced the exact chain:
`recall.js:27-66` builds its script from `store.groundById`, a raw lookup, not `resolveGround`; so
a detached ground becomes a full recall step; `GroundLayers.jsx:166` returns `null`; the image
recedes, **nothing is drawn**, and the expression caption plays anyway. `RefPicker.jsx:39-51`
offers the percept as "2 grounds" without checking that either resolves. The chip markup
(`regionRefInline.jsx:43-57`) has no attribute that could carry evidence state.

That is worse than silence: it is **confident display of absent evidence**.

Four presentation rules, each with its reason:

1. **Degradation-only marking.** HW-S1 §4.7 is right: marking healthy percepts turns the mark into
   noise. Silence when everything resolves; a mark only when something does not. This also keeps
   the change reversible — deleting it returns to today's behaviour exactly.
2. **The mark must name the *evidence*, not the *statement*.** Wording like "evidence not found"
   or "2 of 2 grounds no longer resolve" is honest. "Broken percept", "invalid", "needs fixing",
   or a red error triangle attributes a fault to the curator. **[SUPPORTED]** HB-001 §8 names this
   as "the one place where a wrong call does lasting damage to curator trust."
3. **It must not read as an error the curator caused, nor as an error at all.** Use a neutral
   register — the same register the Vision Activity Rail already uses for absence vs unreadability
   (`visionActivity.js:47-63`, which discriminates the two and is tested). **[EXISTS]** That
   vocabulary exists and is the correct precedent; a new alarm vocabulary would be a regression.
4. **Never repair, never suggest a repair target.** No "did you mean `arch_2`?" — that fabricates
   curator intent. A2S left the fork open on purpose; a UI affordance closes it silently.

**[SPEC]** My own uncertainty, stated: I do not know whether curators experience the empty recall
as a failure or simply do not notice. HW-S1's E1 is the experiment that would find out, and it is
a *better first move than anything in this brief*. If E1 shows curators already notice unaided,
spark-03 weakens and Atlas's central justification weakens with it.

---

## 6. Displaying run_id / vision_runs / rehearsal traces without inventing causality

**What is honest:**

- **Co-reference.** "This run's `output_refs` mention region `fine_3`. This ground cites region
  `fine_3`." Two facts, one shared identifier, no arrow between them. This is exactly P2.2's
  "Referenced …" wording and it is the only sanctioned form.
- **Co-occurrence in observed order.** Stage events within a single run may be listed in the order
  they were observed, because `project_run` states that stored order "is not a causal claim" and
  `dependencies` (stage_id strings) carry causality explicitly where it is actually known. Within
  one run, `dependencies` may be drawn as edges — that is recorded, not inferred.
- **Absence.** "No run recorded for this post." True for 126 of 127 posts. Saying it is more
  informative than an empty panel.
- **Degraded telemetry.** `telemetry_degraded` is a real boolean on the run document; a run whose
  own instrumentation failed should say so rather than present as complete.
- **Staleness.** `project_run` computes `stale` and `staleness_seconds` from real timestamps. A
  stalled run must never render as live or as finished.

**What would be dishonest, plainly:**

- Drawing an arrow, line, or ordering **between two runs**. There is one run; even with a thousand,
  sequence is not cause.
- Any phrasing with a causal verb across records: *caused, resulted in, led to, broke, detached,
  triggered, because of, after which*. Even "after" is dishonest when the timestamps come from
  different clocks or one side has no timestamp at all.
- Rendering a rehearsal trace as product history. **[EXISTS]** Passage-001's trace is 100%
  reconstructed with null telemetry throughout; its own `missing-telemetry.md` says it "can support
  no construct beyond SPARK." Presenting it in the app would launder a reconstruction as a record.
- Inferring the re-dissect on `695be786` from the region generation names. It is the most plausible
  reading in the whole corpus and it is still an inference — A2's critique already refused it, and a
  UI must not un-refuse it.
- A progress or health bar over 1 run, or over 11 posts.
- Filling `initiator`, `actual_source`, `latency_ms`, or `provenance` with defaults when absent.
  **[EXISTS]** Invariant 8 in `vision_run_contracts.py`: "unknown telemetry is absent, not guessed."
  The interface owes the same discipline.

---

## 7. ONE low-risk prototype option, for later approval

**M1 — "Evidence Ledger": a static, hand-built HTML mock. One page. Not wired to anything.**

Not a route, not a component, not in `frontend/src`. A single standalone file rendering the eleven
annotated posts with **data transcribed by hand from the existing A2S evidence JSON**
(`R2/evidence/A2S-detached-ground-sweep.json`, which already exists and is already read-only). No
fetch, no API, no build integration, no state. It is a picture of a surface, not a surface.

Why a mock and not HW-S1's E1–E5: those are real code changes to real components and they belong to
the frontend lane. This lane was asked what Atlas and Codex *are*, and the honest answer is that
they are unbuilt ideas whose central risk is **presentation**, not implementation. A mock tests
presentation at zero implementation cost.

```
┌─ EVIDENCE LEDGER ─────────────────── showing 11 of 127 posts ──────────────┐
│  (11 posts carry any grounds or percepts; 116 carry none)                  │
│                                                                            │
│  post          statements   evidence cited          region generation      │
│  ───────────────────────────────────────────────────────────────────────── │
│  695be786      1 percept    ·· 2 of 2 not found     arch_0…5, refine_c64…  │
│                "the upper head"                                            │
│                   ↳ cites region fine_3 — not found among current regions  │
│                   ↳ cites region fine_0 — not found among current regions  │
│                   ↳ also on this post: frame, frame, field (all resolve)   │
│                                                                            │
│  695be794      0 percepts   ·· 2 grounds not found   seg_0                 │
│                   ↳ no statement cites them                                │
│                                                                            │
│  695be7xx      1 percept    ✓ all cited evidence resolves    …             │
│  … 8 further posts, all resolving …                                        │
│                                                                            │
│  ── how evidence was made (counts, not a rate; n is small) ──              │
│     grounds citing a region       11   ·  4 not found                      │
│     grounds carrying own geometry 15   ·  0 not found                      │
│     ⓘ These are counts over 26 grounds. Not a rate. Not a recommendation.  │
│                                                                            │
│  ── what is recorded about change ──                                       │
│     vision_runs in the database: 1, for a different post.                  │
│     For these posts, no operation was recorded. The instrumentation began   │
│     after these changes. Nothing here explains why evidence is not found.   │
└────────────────────────────────────────────────────────────────────────────┘
```

Note what the sketch deliberately does: neutral dot marker (`··`) not a warning icon; "not found"
not "broken"; the curator's words quoted verbatim and never annotated; counts with denominators;
an explicit refusal to explain; the 11-of-127 denominator in the header; and the Codex section
present but almost entirely an admission of ignorance — which is its honest first form.

- **Cost.** Half a day at most. One HTML file, hand-transcribed numbers, no dependencies.
- **What it would prove.** (a) Whether "evidence not found" reads as *the system lost something*
  or as *you did something wrong* — the §5 risk, tested cheaply on a real person. (b) Whether a
  comparative view of eleven rows is informative or is obviously just a paragraph, which would
  settle §1's own objection empirically. (c) Whether the Codex panel's honest emptiness is
  tolerable or reads as a broken feature.
- **What would kill it.** Any of: the curator reading the marks as blame despite the wording (then
  the presentation problem is harder than a mock can solve, and nothing should be built until it is
  solved); eleven rows being self-evidently too few to be worth a surface (then the answer is grow
  the corpus, per HB-001 §8.3, not build Atlas); HW-S1's E1 landing first and showing curators
  already notice detachment unaided (then spark-03 weakens and this whole direction loses its
  motivation); or anyone proposing an endpoint to feed it (that is the moment it stops being a mock
  and it should be killed rather than promoted).
- **Why it is reversible.** It is one file, outside the app, wired to nothing, with no schema, no
  endpoint, no stored data, no migration, and no import from `frontend/src`. Deleting the file
  removes 100% of it. It cannot flicker, cannot race, cannot mislead a user in production because
  no user reaches it.
- **Sequencing note.** M1 should come **after** HW-S1's E1, not before. E1 answers whether the
  problem is felt; M1 only explores how to present a problem E1 has confirmed. Building M1 first
  risks designing a surface for a complaint nobody has.

---

## 8. What this brief does NOT authorize

- **Any implementation.** No `.jsx`, `.js`, `.py`, `.css` file may be created or edited on the
  strength of this document. The mock in §7 is a *proposal for later approval*, not an approval.
- **Any backend work.** No collection, no route, no schema, no field, no index, no read model.
  Specifically: **no vision-runs list/history endpoint** — its absence is a fact this brief relies
  on to keep prototypes bounded, and building it would remove that bound.
- **Promoting Percept to a durable backend entity.** Still forbidden by `R1-R2-recommendation.md`;
  still contraindicated at n=7 with 1 fully unevidenced (HW-S2 §5 danger 1). The `pct_…`/`pctx_…`
  identity collision remains unresolved.
- **Making the Mention durable.** It is the dependency both Atlas and Codex need and it has one
  unsaved rendered observation behind it (R2.0). Not a small gap, not authorized here.
- **Any repair, tombstone, auto-repoint, or IoU re-match of detached grounds.** The fork is
  deliberately open. This brief does not close it and no prototype may imply a preferred branch.
- **Any Atlas node/edge vocabulary.** `precedes`, `causes`, `contrasts_with`, `echoes`, and the
  rest remain untested prose.
- **Any artifact/depiction marker in production.** A1F narrowed it to reproductions; its *location*
  is unknown; it belongs in rehearsal manifests, where it already is.
- **Any surfacing of rehearsal traces in the product.**
- **Quoting 36.4%, or any rate, anywhere.**
- **A route, a nav entry, or a `PlaceholderPage` named Atlas or Codex.** Naming a stub is a
  commitment; `/atelier` and `/you` are already stubs and adding more is not free.
- **Any candidate graduation.** The R3 bar is ≥3 fixtures plus a transfer test plus a negative
  case. Nothing here meets it. Everything above remains SPARK-adjacent speculation.
- **Any commit, push, merge, or database mutation.**

---

## 9. One line

The honest prototype of Atlas is a table of eleven rows that refuses to explain itself, and the
honest prototype of Codex is a panel that says "no record exists" — and the fact that both are so
small is the finding, not an obstacle to be designed around.
