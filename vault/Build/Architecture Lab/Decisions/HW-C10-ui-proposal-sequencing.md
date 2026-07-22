# HW-C10 — Sequencing increments B and C, which collide at `RegionSurface.jsx:394`

**DECISION DOC — NO IMPLEMENTATION. No source file under `frontend/`, `backend/`,
`chrome-extension/`, `dashboard/`, `showcase/` or `design-system/` was edited, created or deleted
by this lane. Nothing was staged, committed or pushed. No dev server was started (two were already
running and were left alone). No test suite was run. No Mongo access. The only file written is this
one.** Horizon Weave cycle 10, Lane 3.

| | |
|---|---|
| **id** | HW-C10 · adjudicates the collision reported-but-not-resolved at `Build specs/HW-C9-find-parts-rename-spec.md` §1.2 H2 and §7 |
| **date** | 2026-07-22 |
| **status** | **Decided.** |
| **decision, in one line** | **B ships first, alone. C does not ship now — and step 6 of C's gate is struck from C permanently, because `RegionSurface.jsx:394` belongs to B's surface, not to C's.** |
| **rests on** | `frontend/src/components/RegionSurface.jsx:363-404, 448-467` and `frontend/src/components/ProfileControl.jsx:1-95` read in full this cycle; `frontend/src/differential/visionActivity.js:8-38`; `backend/services/domain_profiles.py:19-45`; grep baselines re-measured today (§1.3); `Findings/HW-C8-ui-increment-scout.md` §B, §C; `Build specs/HW-C9-find-parts-rename-spec.md` in full |

*Fable-pass: the sequencing judgement (§2), the register argument in §1.2, and §6. Opus-pass: the
file:line verification in §1 and the risk grounding in §3.*

OBSERVED = read in the file at the cited line, this cycle. INFERRED = my reading of what it means.
Kept apart throughout.

---

## 1. The collision — verified, and it is real

### 1.1 The line as it stands today (OBSERVED)

`frontend/src/components/RegionSurface.jsx:392-398`, read in the working tree on 2026-07-22:

```
392                    {/* the taxonomy, demoted: a quiet menu, not a wall */}
393                    <div className="rs-verbs">
394                        <label className="rs-sr" htmlFor="rs-mode">Dissection vocabulary</label>
395                        <select id="rs-mode" className="rs-select" value={mode} disabled={busy}
396                            onChange={e => setMode(e.target.value)}>
397                            {MODES.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
398                        </select>
```

**The line is exactly where both documents put it, and its text is exactly what both documents
quote.** The visible text node is `Dissection vocabulary`. It is a `class="rs-sr"` screen-reader-only
`<label>` bound by `htmlFor="rs-mode"` to the `MODES` select — i.e. it is announced, not seen.

### 1.2 What each proposal would make it

| proposal | source | proposed text at `:394` |
|---|---|---|
| **B** — `Dissect` → `Find parts` | `HW-C9-find-parts-rename-spec.md` §1.1 row 3 | `Part vocabulary` |
| **C** — profile/category vocabulary | `HW-C8-ui-increment-scout.md` §C2 table, §C4 step 6 | `Name the parts as` |

**Both proposals do target this line, verbatim and by number.** B's §1.1 row 3 cites
`RegionSurface.jsx:394` and B's own §1.2 H2 carries a boxed "Collision warning" naming C's step 6.
C's §C2 table row `select sr-label` and C's §C4 step 6 both cite `RegionSurface.jsx:394`. The
collision was not invented by the brief; each document independently reports it.

**But it is a both-touching conflict, not an incompatibility.** This is the finding that decides
the shape of the answer:

1. **The two replacements are not in tension about meaning.** Both correctly identify that this
   `<label>` names a *vocabulary for naming parts* and that the word `Dissection` is the wrong
   register for it. `Part vocabulary` and `Name the parts as` are two acceptable renderings of the
   same judgement. Neither would have to be un-done to accommodate the other.
2. **The rebase is one line and mechanical.** Whichever lands second replaces one text node in one
   JSX element. There is no import, no prop, no handler, no CSS class and no id that either
   proposal moves. `htmlFor="rs-mode"` and `id="rs-mode"` are untouched by both.
3. **The line does not belong to C's subject matter at all.** OBSERVED, `ProfileControl.jsx:70-92`:
   C's actual surface is the `pc` block — eyebrow (`:73`), chips (`:74-79`), `Auto` (`:80-81`),
   `pc-reason` (`:83`), `pc-passes` (`:84-92`). It is a *separate component*, mounted at
   `RegionSurface.jsx:390`, one line above the `rs-verbs` div. C's scout is explicit that the
   `MODES` select is its **Group 3**, a different mechanism from the chips (§C1: "This one really
   is a label vocabulary — it steers *what the parts get called*, not which detector runs").
   **Step 6 is C reaching one component outward to tidy a neighbouring string.** It is the only
   item in C's gate that touches `RegionSurface.jsx` at all.

**INFERRED, and it is the whole resolution:** the collision exists because C annexed a line that is
not C's. Remove step 6 from C and the collision disappears without either proposal losing anything
it was actually for.

### 1.3 Baselines re-measured this cycle (OBSERVED)

B's spec §5.1 records five pre-change numbers. All five still hold today, so B's line numbers have
not drifted and its spec is executable as written:

| check | expected by B §5.1 | measured 2026-07-22 by this lane |
|---|---|---|
| `grep -rni "dissect" frontend/src \| wc -l` | 59 | **59** |
| `grep -rni "dissect" backend/ \| wc -l` | 107 | **107** |
| `grep -rn "Find parts" frontend/src \| wc -l` | 0 | **0** |

`git status --short` shows **zero modified source files** — every entry is under `vault/`,
`audit-bundles/`, `new-planning/` or `scripts/`. The tree is clean on the axis both proposals touch.

### 1.4 One correction carried forward, and one confirmed

- **Confirmed (B's §1.3 correction of C's scout).** `RegionDetectorModal` is referenced outside
  itself in exactly two places: `frontend/_ds-barrel.mjs` and `.design-sync/config.json`. C's scout
  §B1 called the file "dead"; B's spec called it "unmounted, not unreferenced". **B is right.**
  Verified by grep across `*.mjs` and `*.json` outside `node_modules`.
- **Confirmed (C's correction of the brief).** `ProfileControl.jsx:84-91` renders `<span>`
  elements with a `title` and no `onClick`, `onKeyDown` or `aria-pressed`. **The YOLO/SAM row is a
  read-only readout, not a selector.** Verified by reading the component in full.
- **Confirmed (C's capability claim).** `toggle()` (`:58-62`) → `override()` (`:46-56`) →
  `PATCH /{postId}/domain-profile` → `domain_profiles.py:26-33` `PROFILE_PASSES` →
  `passes_for()` (`:36-45`), which unions the adapter roster for the chosen profiles.
  **The chips decide which detector adapters run.** Verified.

---

## 2. The verdict

> **B ships first, alone. C does not ship now.**
>
> `RegionSurface.jsx:394` is assigned to **B**, and becomes `Part vocabulary`. **Step 6 of
> `HW-C8` §C4 is struck from increment C permanently** — not deferred, struck. When C is later
> authorized, its gate is steps 1–5 only, and the sr-label is already correct.
>
> C is **not rejected**. It is **not authorized yet**, on one unmet precondition: the honesty
> decision its own scout demands at §C3.1 has not been taken (§3.2, §5.2).

**Justified from risk and value, not from tidiness.**

**Value.** B fixes the loudest thing in the app: the primary action on the region surface is
labelled with the one clinical word on a pane otherwise built from *parts, anatomy, quiet, focus,
what each part does to you* (`RegionSurface.jsx:380, 418, 435, 438, 462, 463, 467`). Every curator
who opens a post meets that button. C's value is real but narrower and further inside — the chips
sit in a side panel, one component deep, and the words being replaced (`Fashion`, `Architecture`,
`Painting`) are *not wrong*, only cold. **B replaces a word that misdescribes the product. C
replaces words that describe it accurately but stiffly.** That is a genuine gap in value, not a
preference.

**Risk.** B cannot make the UI say anything untrue, because the thing it renames has no hidden
semantics: the button starts a run and the run finds parts. C **can** make the UI say something
untrue, and its own scout says so at §C3.1 — a chip is a capability switch, so a perceptual name
that reads like a view filter would claim that unchosen regions are *hidden* when in fact they
**do not exist** (`domain_profiles.py:26-33`; no adapter ran, so no candidate was ever produced).
That is a class of defect B does not have access to.

**Why not both in one commit.** They are separable, so combining them buys nothing and costs the
property that makes B worth doing first: **B's revert is total and stateless** (§4). Fold C in and
the revert now also un-does a capability-adjacent copy change whose honesty question is unresolved,
and the reviewer of the combined diff must hold two register arguments at once. **A change whose
best property is that it is trivially reversible should not be married to one that is not.**

**Why not C first.** Only one argument favours it — C touches `RegionSurface.jsx` at exactly one
line, so landing C first leaves B a smaller rebase than the reverse. That is tidiness, and it is
outweighed twice: C is blocked on a decision nobody has taken, and B's spec is complete, measured
and executable today (§1.3). **Sequencing on rebase convenience would let the blocked change gate
the unblocked one.**

---

## 3. Risk analysis

### 3.1 Proposal B — risks, grounded in what its spec found

| # | risk | severity | grounding | mitigation, from B's own spec |
|---|---|---|---|---|
| B-1 | **Over-application into a wire identity.** `dissect` is not only a label: 37 identifiers are frozen (`HW-C9` §2), including `OPERATION_DISSECT` and 14 `dissect.*` stage ids that must match `visionActivity.js:90-103` **exactly** or every stage renders through the `humanStage` fallback at `:125-126` | **highest** | OBSERVED `visionActivity.js:10-36`: `OPERATIONS` is a wire array, `EPISTEMIC`/`AFFECTS`/`STAGE_LABEL` are keyed by wire value | row 7 splits the line — key stays `dissect`, value becomes `Find parts`. Caught by V10 (`vitest`, which asserts `OPERATIONS` at `visionActivity.test.js:31`) and by V18 (eyes-on: a raw `dissect.something` in the stage list means a key broke) |
| B-2 | **`?operation=dissect` leaves the browser as a query value.** `latestUrl()` at `visionActivity.js:36` builds `…/vision-runs/latest?operation=${operation}`. "The string never leaves the frontend" is **false** | medium | **OBSERVED this cycle**, `visionActivity.js:35-37`, exact text confirmed | it is a *value*, not a label; frozen as F37. The mitigation is that no row of B touches `OPERATIONS` or the call sites at `:134, 218, 255` |
| B-3 | **No test asserts on any display string, so no test would catch a bad label.** | medium | **OBSERVED this cycle.** Grepping all seven `frontend/src/**/*.test.*` for `Dissect` and `OPERATION_LABEL` returns **one hit, and it is a comment**: `visionActivity.test.js:118` `// 3 — successful Dissect`. Zero assertions | §5 of this doc. The suite proves *keys* survived; only eyes-on proves *copy* is right |
| B-4 | **`RegionDetectorModal` is unmounted but still bundled** by `frontend/_ds-barrel.mjs` and mapped in `.design-sync/config.json`, so a stale `Dissect` there ships in a design-system artifact even though the app never mounts it | low | OBSERVED, two non-self references confirmed (§1.4) | rows 10a–10c, separable; `git checkout <sha>^ -- frontend/src/components/RegionDetectorModal.jsx` reverts them alone |
| B-5 | **Layout regression from a longer label.** `Find parts` is 10 chars against `Dissect`'s 7, and `RegionSurface.jsx:402`'s comment says *"the label hides when the pane is cramped; the icon carries it"* | low | OBSERVED, comment text confirmed at `:402`; `.rs-primary-label` at `:403` | V15 checks it at a narrow window. B §6 forbids fixing it in the same commit — **stop and report** |

**The honest summary of B's risk: it is a copy edit whose only real hazard is a fat-fingered key,
and the test suite already covers exactly that hazard.** What the suite does *not* cover is whether
the new words are the right words — which is a review question, not a test question.

### 3.2 Proposal C — risks, grounded in what its scout found

| # | risk | severity | grounding |
|---|---|---|---|
| C-1 | **A perceptual rename can make the UI say something untrue.** The chips are a real capability switch. Choosing `Built space` schedules `segformer_b0_ade`; *not* choosing it means that adapter never runs and its regions **do not exist** — not "are hidden". `Clothing / Built space / Painted surface` invites reading three lenses onto one set of findings | **highest — and it is a correctness risk, not an aesthetic one** | **OBSERVED this cycle**: `ProfileControl.jsx:58-62` → `:46-56` `PATCH /domain-profile`; `domain_profiles.py:26-33` `PROFILE_PASSES`, `:36-45` `passes_for()` |
| C-2 | **The chips are cumulative, not exclusive; `This image is` reads singular** and suggests a radio group. `aria-pressed` at `:77` is already correct, so the copy would contradict the accessibility tree | medium | OBSERVED `ProfileControl.jsx:58-62` builds a set; `_normalise_chosen` re-adds `general` |
| C-3 | **The YOLO/SAM row is a read-only readout, not selectors** — the brief's premise was wrong and the scout corrected it. It is also the **only** place in the UI where an `unavailable` model is surfaced | medium | **OBSERVED this cycle**, `ProfileControl.jsx:84-91`: `<span>`, `title` only, no handler, state from `GET /vision/capabilities` (`:28-33`, `:68`) |
| C-4 | **After the rename, the two control groups look more alike, not less.** Profile chips (capability) and the `MODES` select (wording) would both read as gentle perceptual words, ~20 lines apart in the same pane. The scout's own mitigation is a separator — **which is a layout change, outside C's gate** | medium | OBSERVED: `ProfileControl` mounted at `RegionSurface.jsx:390`; `rs-verbs` opens at `:393` |
| C-5 | **`Auto → Sense it` hides a network call.** `runAuto()` (`:37-44`) POSTs to `/domain-profile/propose` and re-classifies | low | OBSERVED `ProfileControl.jsx:37-44, 80-81` |

**The honest summary of C's risk: C's diff is mechanically the safest in the cycle — a label map
and a `<details>` — and its *semantic* risk is the highest in the cycle.** Those two facts are
usually correlated and here they are inverted. That inversion is exactly why C must not be
sequenced on diff size.

**C-1 is a precondition, not a caveat.** C's scout wrote (§C3.1) that `pc-reason`
(`ProfileControl.jsx:83`) "must survive the change and should be rewritten to say what will and
will not be looked for — it is the only honesty carrier in the component." **No lane has written
that sentence.** Until someone does, C is a proposal with a known hole in it, and shipping it is
shipping the hole.

---

## 4. Rollback for B — the one being sequenced first

**The revert is one command and it is total.**

```
git revert <sha>
```

B lands as **one commit touching exactly five frontend source files** plus the two doc placements
of its §3.1 — no unrelated edits, no reformatting, no import reordering.

**Why it is stateless.** No migration, no schema edit, no route edit, no backend edit, no persisted
value. Every `vision_runs` document written while `Find parts` was on screen is byte-identical to
one written under `Dissect` — the operation, the fourteen stage ids and the payload keys are the
same before and after (§2 of B's spec, re-verified here at `visionActivity.js:8-38` and
`domain_profiles.py` untouched). **There is no state to unwind, so the revert cannot leave a
half-migrated system.**

**Partial revert**, if only the unmounted-modal rows are contested:

```
git checkout <sha>^ -- frontend/src/components/RegionDetectorModal.jsx
```

Rows 10a–10c are independent of rows 1–9; nothing imports across them.

**How to verify the revert is complete.** From the repo root, all three must hold:

| # | command | must return | why this number |
|---|---|---|---|
| RB1 | `grep -rn "Find parts" frontend/src \| wc -l` | **0** | the new string is gone from the tree |
| RB2 | `grep -rni "dissect" frontend/src \| wc -l` | **59** | **re-measured by this lane today, 2026-07-22** |
| RB3 | `grep -rni "dissect" backend/ \| wc -l` | **107** | **re-measured by this lane today.** Must be 107 both before and after — B never edits `backend/` |
| RB4 | `git diff <sha>^ HEAD -- frontend/ backend/` | **empty** | the strongest check: the revert restored the source byte-for-byte |
| RB5 | `git status --short` | no modified file under `frontend/` or `backend/` | nothing was left behind by hand |

**RB4 is the check that actually closes it.** RB1–RB3 are counts and a count can coincide; an empty
diff cannot. **If RB3 ever differs from 107, the change was out of scope in the first place and the
revert is not the whole story — escalate rather than proceeding.**

---

## 5. Verification owed, given that no test covers display strings

### 5.1 The gap, stated exactly (OBSERVED)

`frontend/src` contains **seven** `*.test.*` files. Grepping every one of them for `Dissect` and
`OPERATION_LABEL` returns **a single hit, and it is a comment**:
`frontend/src/differential/visionActivity.test.js:118` — `// 3 — successful Dissect`.

**There is no assertion, anywhere, on any rendered label of the `dissect` operation.** No test
mounts `RegionSurface`, `VisionActivityRail` or `DifferentialWorkspace`. **A wrong label ships
green.**

### 5.2 What is owed instead — three tiers, all mandatory

**Tier 1 — grep arithmetic (proves scope).** Run before and after; the numbers must close:

| # | command | before | after (full, incl. the unmounted modal) | after (modal skipped) |
|---|---|---|---|---|
| G1 | `grep -rni "dissect" frontend/src \| wc -l` | 59 | 48 | 51 |
| G2 | `grep -rni "dissect" backend/ \| wc -l` | 107 | **107 — unchanged** | 107 |
| G3 | `grep -rn "Find parts" frontend/src \| wc -l` | 0 | 4 | 3 |
| G4 | `git diff --name-only` | — | exactly 5 frontend files + the new Decisions note | 4 files |

G2 is the load-bearing one: **it proves the diff is frontend-only without reading the diff.**

**Tier 2 — the suites (prove no key broke).** `cd frontend && npx vitest run` must be green — a
failure here means a **key** was renamed, not that copy is wrong. `python -m pytest
backend/tests/test_circulation_spine_p1.py backend/tests/test_circulation_spine_p2_1.py` must be
green even though no backend file is edited; it is the cheap proof of that claim.
`cd frontend && npm run build` catches an unbalanced quote, which is the realistic failure mode of
a copy edit.

**Tier 3 — eyes on screen (the only tier that can catch a bad label).** Two dev servers are already
running; **do not start a third.** B's spec §5.4 V13–V19 is the list. Three of them carry the
weight:

- **the stage list on a post with a recorded run** — if any stage renders as raw
  `dissect.something`, a `STAGE_LABEL` key broke (`visionActivity.js:90-103`) and the change must
  be reverted. **This is the highest-value check in the whole verification**, because it is the one
  failure the suite lets through;
- **the rail entry** — label reads `Find parts` while its epistemic line still reads
  *"Visual evidence produced."* / `geometry` (`visionActivity.js:21, 29`). If the epistemic line
  changed, the rename overreached into the honesty copy;
- **the primary button at a narrow pane width** — `.rs-primary-label` must hide cleanly rather than
  overflow (B-5).

And, specific to this decision: **`#rs-mode` announces `Part vocabulary`** in the devtools
accessibility pane. That is the collision line; it is the one string this document reassigned, and
it is sr-only, so it is invisible unless someone deliberately looks.

### 5.3 Should a test be added? — **One should. It must not assert on copy.**

**Do not add a test asserting `OPERATION_LABEL.dissect === 'Find parts'`.** The cost is concrete
and this cycle demonstrates it: a test that pins display copy makes the *next* rename a two-file
change with a red suite in the middle, and it encodes a product decision — which word is on the
button — as a correctness invariant. It is not one. B's own §3 R1 says the label "may be rewritten
freely". **A copy assertion contradicts the rule the change is being made under.** A suite that
goes red because someone improved a sentence trains people to edit tests reflexively, which is how
the assertions that *do* matter get edited too.

**Add instead a key-integrity test — it catches the real hazard and freezes nothing curator-facing.**
One test in `frontend/src/differential/visionActivity.test.js`, asserting structure rather than
text:

- `Object.keys(OPERATION_LABEL)`, `Object.keys(EPISTEMIC)` and `Object.keys(AFFECTS)` each equal
  `OPERATIONS` (`visionActivity.js:10`) — so a renamed key is caught wherever it happens;
- every `STAGE_LABEL` key (`:90-103`) matches `/^(dissect|refine|semantic_read|find_similar)\./`
  and the fourteen `dissect.*` ids are all present — so a key edited into a label is caught before
  it silently degrades every stage to the `humanStage` fallback at `:125-126`.

**Both assert on wire identity, which is genuinely frozen (B §2), and neither asserts on a single
word a curator reads.** That is the correct place to spend a test.

**INFERRED:** this test is worth writing whether or not B ships, and it does not have to ship in
B's commit. It is not a precondition on B — the existing `expect(OPERATIONS).toEqual([...])` at
`visionActivity.test.js:31` already covers the single most likely mistake.

---

## 6. What would overturn this

**To ship C first instead of B:**

1. **A curator is actively misled by a chip today** — someone reports missing regions that were
   never detected because a profile was unchosen. C-1 stops being prospective and becomes a live
   defect, which outranks a register mismatch.
2. **B's baselines have moved.** If G1 ≠ 59 or G2 ≠ 107 when the build lane starts, B's line
   numbers drifted and B is no longer the ready change. Re-verify before sequencing anything.

**To ship neither now:**

3. **The register decision reopens.** If `Find parts` is contested at review, B has no value left
   to trade against even its small risk — the whole point is that the new word is better. Withdraw;
   do not compromise on a third word inside the build lane.
4. **`Find parts` overflows `.rs-primary` and cannot hide cleanly** at narrow widths (B-5). B
   forbids fixing that in the same commit, so a real clipping regression makes B a CSS decision,
   which is a different gate.

**To authorize C (steps 1–5, without step 6):**

5. **The `pc-reason` honesty sentence is written and reviewed** — the one C's own §C3.1 requires,
   stating what will and will not be looked for. This is the single unmet precondition.
6. **A decision is taken on the separator** between the capability chips and the `MODES` select
   (C-4), or an explicit statement that shipping without it is accepted. It is a layout change and
   therefore outside C's gate as written.
7. **Measurement.** No Mongo query has ever been run against `domain_profile`, so nothing is known
   about how many posts carry a non-default profile or which chips get used. C is currently argued
   entirely from code. That measurement would sharpen it and is not blocking, but its absence is
   why C's value is rated "medium" rather than "high".

**To un-strike step 6:**

8. **Nothing.** If C is later authorized and someone still prefers `Name the parts as`, that is a
   fresh one-line copy change with its own justification — not a revival of C's step 6. The point
   of striking it is that the line stops being contested territory, permanently.

---

## 7. What this decision does NOT authorize

- **No implementation of B.** This document sequences B; it does not run it. B's spec remains a
  spec and needs its own build gate.
- **No implementation of C**, in whole or in part, including its steps 1–5.
- **No route change.** `POST /{post_id}/detect-regions`, `PATCH /{postId}/domain-profile`,
  `POST /{postId}/domain-profile/propose`, `GET /vision/capabilities` all stay exactly as they are.
  No new route, no alias, no redirect.
- **No schema change.** No `vision_runs` field, no `region_annotations` field, no `domain_profile`
  field, no request or response key. The `mode` / `lens` / `coarse_only` payload
  (`RegionSurface.jsx:174-177`) is untouched.
- **No backend rename and no backend edit of any kind.** Not one character under `backend/`.
  `OPERATION_DISSECT`, all fourteen `STAGE_*`, `DissectRunRecorder`, `PROFILE_PASSES`
  (`domain_profiles.py:26-33`) and `passes_for` (`:36`) are frozen. G2 must read 107 after B.
- **No redesign.** No layout change, no CSS change, no separator between the two control groups
  (C-4), no `<details>` disclosure, no change to `.rs-primary`, `.rs-busy`, `.rs-error`,
  `.va-scope`, `.pc-passes` or `.rd-detect-btn`.
- **No telemetry or contract rename.** The wire value stays `dissect` in `OPERATIONS`, in every
  `EPISTEMIC` / `AFFECTS` / `STAGE_LABEL` key, and in the `?operation=` query value
  (`visionActivity.js:36`).
- **No test edit**, and specifically **no new test asserting on display copy** (§5.3). The
  key-integrity test proposed there is authorized in shape only, not scheduled.
- **No deletion of `RegionDetectorModal.jsx`**, despite it being unmounted. It is still exported by
  `frontend/_ds-barrel.mjs` and mapped in `.design-sync/config.json`; removing it is a separate
  decision with its own justification burden.
- **No execution of HW-C8 increment A** (the saver's contextual primary). This lane does not touch
  `chrome-extension/` and takes no position on A's place in the order beyond noting that HW-C8's
  recommended B → A → C is untouched by this decision, since striking C's step 6 removes the only
  reason the order mattered.
- **No change to `Chiasm`, `Differential`, `Aletheia`, `Unconcealment`, `Sūkṣma · fine anatomy`,
  the `Quiet / Outline / Focus` map switch, the `MODES` options (`RegionSurface.jsx:17-24`), or the
  `PASS_LABEL` values (`ProfileControl.jsx:16-19`).**
- **No commit, no stage, no push, no PR from this lane.**

## 8. What was deliberately NOT done in this lane

- **No source file was edited, created or deleted.** The only file written is this one.
- **No test suite was run and nothing was built.** §5.1's conclusion — that no test asserts on a
  display string — is from grepping and reading the assertions, not from executing them.
- **Nothing was checked in a browser.** Every claim about what appears on screen is derived from
  JSX. That is precisely why §5.2 Tier 3 is mandatory rather than decorative.
- **No Mongo query was run**, so this lane cannot say how many posts carry a non-default
  `domain_profile` — which is the measurement that would most sharpen C (§6.7).
- **No wording was chosen for C's `pc-reason` honesty line.** It is named as C's precondition and
  left unwritten; writing it here would be taking C's decision under cover of sequencing it.
- **HW-C8 increment A was not re-examined.** It is outside this collision and outside this lane.

---

*Decision doc ends. Status: decided. B sequenced first and alone; C not authorized; C's step 6
struck. No implementation performed. No commit, no stage, no push.*
