# CIRCUIT-001 P5-B — The Passage Rail report

**Production-intent. Executed.** The rail CS-001 asked for and P0 forbade as fabrication now
exists — because the fabrication objection is dead. Runs are real (`vision_runs`), events are
appended by real producers, provenance carries model + latency + run_id, and typed read routes
(`GET /{post_id}/vision-runs/latest`, `…/{run_id}`) return them. This rail renders ONLY what those
records hold: a **witness, not a narrator** (Invariant 9). Built in an isolated worktree against
Lane A4's landed producers; nothing outside the owned files was touched.

| | |
|---|---|
| **id** | CIRCUIT-001 P5-B · the passage rail on P4 real runs + P3-A circulation |
| **worktree** | `../semant-p5-rail` · branch `feat/circuit-p5-rail` · base `62d80e8` (origin/main, #72 P4-A + #73 P4-B merged) |
| **dependency** | **none added** — the poll is TanStack Query's `refetchInterval` (already shipped); no konva, no tldraw |
| **tests** | **730 green** (was 706 at base; +24 across 2 new files) · production build clean · lint clean |
| **verified live** | offline harness `/lab/differential` with a seeded fixture `VisionRunOut` + the P4-B 20-suggestion batch — run timeline, two-source interleave, and tap-to-highlight all exercised; **zero app console errors** |
| **new files** | `PassageRail.jsx`, `passageRail.js` (pure), `PassageRail.css`, `passageRail.test.js`, `PassageRail.dom.test.jsx` |

The rule this gate serves: **the rail is a witness, not a narrator. If it wasn't recorded, it
isn't shown.**

---

## 1. What the rail shows (2a/2b)

A collapsible **Passage** section in the Differential tool column, mounted under the Seeing
console. When open it shows, for the operation under the curator's hand:

- **a scope line** bounding the claim (Inv 12): *"The latest {operation} run for this image, and
  this session's own circulation. If it wasn't recorded, it isn't shown."*
- **the run's REAL events in stored (arrival) order** — each row: `RUN` badge · humanized stage ·
  status · model (where `provenance.model` recorded) · adapter · latency. Order is observation,
  not causation (the contract is explicit that stored order is *not* a causal claim), so it is
  rendered as a **sequence, never a percentage**.
- a **terminal outcome + provenance line**: outcome · real elapsed time · asked-by · ran-on ·
  (terminal reason). Duration is `completed_at − started_at`, or `—` when either stamp is missing.
- **2b — tap to highlight.** Tapping a run event (or the run header) resolves, via a read-only
  store lookup (`acceptedMarksForRun`), the marks that run produced and the curator accepted, and
  **highlights** them through the existing recall channel (`playMarkRecall`, P3-A). Tapping a
  session accept row highlights that one mark. Highlight *is* recall — so it reappears in the rail
  as a live recall event, a closed loop. No mutation, no new link, no new entity.

## 2. What the rail REFUSES to show, mapped to the anti-spec (2c)

Every honesty hotspot (P0.5 §4.3 "what the Thread must never do" + CIRCULATION-SPINE Invariants
8/9/12/13 + the P2.2R integration review's found failure modes) is made **structurally
impossible** — the derivation lives in pure `passageRail.js` so the JSX cannot invent a state:

| the lie it could tell | where it was named | why it can't happen here |
|---|---|---|
| **fake progress** (a bar, a percent) | Inv 9; brand-svg §Passage Rail | nothing records a fraction; the rail renders an event **sequence**. A test greps that no `role=progressbar`, `<progress>`, `<meter>`, computed `%` width, or `@keyframes` exists; a DOM test asserts no `[role=progressbar]` node. |
| **guessed telemetry** | Inv 8 | absent `latency_ms`/`model`/duration stay `null` → the view renders **"—"**. Proven by unit + DOM test (a stage with no latency shows "—"). |
| **claiming live forever** | Inv 13 | a stalled `running` doc is **not live** (`isRunLive` false): the poll stops and the rail says *"No events for Ns"* in real seconds. It never animates waiting. |
| **a failed read read as "nothing recorded"** | P2.2R R0 (the surface "lies by omission exactly when it fails") | unreadable (`isError && !run`) → *"read failure, not an empty record"*; a failed **refresh** that still holds the last real run → *"showing the last read of this run"* and keeps it — a poll blip never erases a record. Absence (`{run: null}`) → *"nothing recorded yet"*. Three distinct states, each tested. |
| **order-as-causation** | P0.5 §4.3 | events render in stored order, labelled a sequence; no row asserts one thing produced another. |
| **a judgement in a record's register** | P0.5 §4.3 | backend `RUN` events and local `THIS SESSION` events wear two visibly different source badges and voices (2d); a distinct-badge-count DOM test pins it. |
| **a suggestion rendered as evidence** | contract §4 | suggestion-producing runs (`refine`, `semantic_read`) carry a **"suggestion run"** tag; the rail renders run telemetry + *accepted* marks only, never a pending suggestion's geometry as evidence. |
| **a cancel it can't honour** | (no cancel path exists) | there is no cancel/stop control anywhere; greped absent. |

## 3. The poll lifecycle (2a/2c)

One TanStack `useQuery` per operation reads `vision-runs/latest`. The entire anti-idle-poll rule
is one line:

```js
refetchInterval: (query) => (isRunLive(query.state.data) ? POLL_MS : false)
```

- **live** (`running`/`pending` & not stale) → re-read every 3.5 s.
- **terminal, stalled, or absent** → `false`: the poll **stops**. No idle loop, no spinner
  implying activity the record does not show.
- the operation follows the tool under the hand (`refine → refine`, `similar → find_similar`,
  `read → semantic_read`, else `dissect`), so a SAM suggest run is watched while the curator is in
  Refine, and the primary dissect passage is watched at rest.
- a failed background refetch sets `isError` but **keeps** the last successful `data` — the rail
  shows the last real run under a "couldn't refresh" note rather than blanking it.

## 4. The two-source timeline (2d)

Two sources, two styles, **one list, never one clock**:

- **backend RUN events** — records, from the run doc.
- **local SESSION events** — this session's real circulation, read-only from the store:
  **accepts** (a `user_confirmed` mark deriving from a suggestion, carrying its producer + run_id)
  and the **live recall** performance. There is *no recorded recall history*, so the rail shows
  only the live one and **invents none** (see P5F).

They are merged by best-available timestamp and each row is tagged with its `source`; a missing
time sinks to the end rather than claiming a moment. Because the two clocks are genuinely
different (backend observation time vs. local `Date.now()`), the rail states it outright —
*"Run events and this session's events keep separate clocks."* — rather than laundering them into
one false chronology.

## 5. Tests (+24, total 730)

- **`passageRail.test.js`** (16) — live/terminal/stalled gating (a stale run is not live);
  arrival-order events with absent fields staying `null`; real-or-null duration; suggestion-run
  labelling; session-event derivation (accept + live recall, no invented history);
  `acceptedMarksForRun` link; four-state honest summary; and source-grep guards that the JSX has
  **no** progressbar/meter/keyframes/cancel and that the poll gates on `isRunLive`.
- **`PassageRail.dom.test.jsx`** (8) — mounts the rail over a fixture `VisionRunOut` (cache
  preseeded for synchronous render): real events render, absent telemetry shows "—", **no
  progressbar node**, the two source badges are distinct, tapping a run row and a session row fire
  the read-only highlight callbacks, a suggestion run self-labels, an absent run says "nothing
  recorded", and **a failed refresh keeps the last real run** (P2.2R R0).

Full suite **730 green**; production build clean; lint clean; no dependency added.

## 6. Live verification (offline harness)

The backend is blocked (server-exit-144), so a live SAM run against a real server was not
exercisable. The offline `/lab/differential` harness stands in **honestly**: it is a fixture
producer (the pattern P4-B established), seeding one real-shaped `VisionRunOut` into the query
cache — the rail's rendering path is identical to a live run doc, and against a real backend the
seed is never reached. The offline backend fetch fails, which exercises the *stale-read* honesty
path for free.

| # | screenshot | shows |
|---|---|---|
| 01 | `01-run-timeline-populated.png` | the run timeline: five real stage events in order, `sam21_hiera_tiny` where recorded, **"—" on the stage with no recorded latency** (Inv 8), terminal outcome `Complete · 5.4 s · curator · live`, and the **"Couldn't refresh — showing the last read"** stale-read note (the offline poll failed but the real run is kept) |
| 02 | `02-two-source-timeline.png` | after accepting two P4-B suggestions: **two `THIS SESSION` accept rows** (distinct plum badges, italic) interleaved above the `RUN` events, and the **"keep separate clocks"** honesty line |
| 03 | `03-tap-highlight-recall.png` | tapping a `THIS SESSION` accept row performs the mark's recall — a live **`Recalling`** session row appears and the stage highlights the mark (the closed loop) |

Console: **zero app errors** across load, expand, two accepts, and the tap-highlight (the only
console output is an unrelated browser extension). The failed backend fetch is caught by
react-query with no console spam.

## 7. `// P5F:` markers

| where | gap | what P5F (or Lane A5) should do |
|---|---|---|
| `PassageRail` mount | v1 lives inside the Differential tool column | spanning **Field ↔ Manuscript** is a recorded future promotion; A5 owns the `PostDetailPage` seams. The rail is already source-agnostic (it takes `postId` + store reads), so promotion is a mount move, not a rewrite. |
| poll scope | one `latest` poll per operation, following the active tool | a **cross-operation runs-list endpoint** would let the rail show the single most-recent run across all operations regardless of tool, without following the hand or fetching four. Marked at the `passageOperation` derivation. |
| `highlightRunMarks` | one recall channel highlights only the FIRST accepted mark of a run | a store `focusMarks(ids)` would let a run event highlight **every** mark it produced at once. Marked in `DifferentialWorkspace.jsx`. |
| recall history | the store keeps only the LIVE recall, no log | the rail shows the live recall and invents no past ones. A recorded session recall log (or a store `recallHistory`) would let the timeline show past recalls; deliberately not faked here. |

## 8. Ownership & parallel safety

Modified only owned files: `PassageRail.jsx` / `passageRail.js` / `.css` (new),
`DifferentialWorkspace.jsx` (mount + two read-only handlers + one destructure add:
`playMarkRecall`), `pages/DifferentialLab.jsx` (dev harness fixture seed), and the two test files.
**Not touched:** backend, `visualMarks.js`/`suggestionQuarantine.js`/`markStaging.js`,
`regionStore.js`, `visionActivity.js` (imported at its origin signatures only), `recall.js`,
blocknote/*, `PostDetailPage`, the contract doc. Lane A5's crossing PR runs in parallel; if it
collides on the Differential surface a small **P5F reconcile** in the main tree resolves it — the
shape of every prior lane merge.
