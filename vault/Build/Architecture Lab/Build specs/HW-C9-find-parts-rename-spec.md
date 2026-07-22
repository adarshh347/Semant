# HW-C9 — Build spec: rename the product label `Dissect` → `Find parts`

**SPEC ONLY — NOT IMPLEMENTED. No source file under `frontend/`, `backend/`, `chrome-extension/`,
`dashboard/`, `showcase/` or `design-system/` was edited, created or deleted by this lane. Nothing
was staged, committed or pushed. No dev server was started. No test suite was run.** Horizon Weave
cycle 9, Lane 4. This lane specifies; a build lane executes at a later gate.

Every `file:line` below was re-read in the working tree on the date in the table. Where the
HW-C8 scout's numbers drifted, the drift is called out. **They did not drift: all twelve
user-visible lines are exactly where the scout put them.**

| | |
|---|---|
| **id** | HW-C9 · executes item **B** of `Findings/HW-C8-ui-increment-scout.md` §B |
| **date** | 2026-07-22 |
| **status** | **Spec written. Not implemented. Not authorized to run.** |
| **change, in one line** | The primary action on the region surface is relabelled **`Find parts`**. The operation stays `dissect` everywhere it is a wire value. |
| **blast radius** | 5 files, all under `frontend/src`. 10 string edits + 2 comment lines. Zero behaviour, zero props, zero network, zero schema. |
| **rests on** | the noun `parts` already being the surface's own word (`RegionSurface.jsx:380, 418, 435, 438, 462, 467`) and the backend rendering `dissect.persist_regions` as **"Saved parts"** (`visionActivity.js:102`) |
| **new fact this lane adds** | **No test asserts on the string `Dissect` or on `OPERATION_LABEL.dissect`.** The scout flagged this as unmeasured (§B4 "Flagged, not measured"). It is now measured. See §2.4. |
| **new correction this lane adds** | `RegionDetectorModal.jsx` is **unmounted, but not unreferenced.** See §1.3. |

*Opus-pass: the file:line verification and the frozen list. Fable-pass: the copy rules and the
sentences in §1.2.*

---

## 0. Why this is the cheapest change in the cycle

Three facts, each verified below, make this a display-layer edit and nothing else:

1. **No URL path contains "dissect".** The route is `POST /{post_id}/detect-regions`
   (`backend/routers/posts.py:634`; called at `frontend/src/components/RegionSurface.jsx:171`).
   Verified by grepping every `*.py`/`*.js`/`*.jsx`/`*.json` in the repo for `dissect` inside a
   path, `fetch(`, `axios` or `@router` string — **zero hits**. §2.3.
2. **No test asserts on the display string.** §2.4.
3. **The word does not exist outside `frontend/src` and `backend/`.** `chrome-extension/`,
   `dashboard/`, `showcase/` and `design-system/` return **0** occurrences, case-insensitive.
   Verified.

One caveat that sharpens fact 1: **`dissect` does travel over the wire — as a query-string
*value*, not a path segment.** `visionActivity.js:36` builds
`…/vision-runs/latest?operation=${operation}` with `operation === 'dissect'`. That value is
frozen (§2.1, row F6). "No route change" is true; "the string never leaves the browser" is not.

---

## 1. The change

### 1.1 The ten strings that change

All ten are user-visible. Six are in the live surface, one is a shared label map, two are prose,
and three are in the unmounted modal (§1.3). Nine of the twelve strings the scout listed change
by a rewritten sentence rather than a substitution — **`Find parts` slots cleanly into exactly
two positions: the button and the label-map value.**

| # | file:line | position | CURRENT | PROPOSED |
|---|---|---|---|---|
| 1 | `frontend/src/components/RegionSurface.jsx:187` | error toast (`setError`, rendered at `:450` with `role="alert"`) | `'Dissection failed — is the backend running?'` | `'Couldn’t find the parts — is the backend running?'` |
| 2 | `frontend/src/components/RegionSurface.jsx:365` | busy status (`role="status"`, live region) | `Dissecting the image…` | `Finding parts…` |
| 3 | `frontend/src/components/RegionSurface.jsx:394` | screen-reader `<label>` for `#rs-mode` | `Dissection vocabulary` | `Part vocabulary` |
| 4 | `frontend/src/components/RegionSurface.jsx:400` | `title=` tooltip on the primary button | `Dissect the image into its parts` | `Find the parts of this image` |
| 5 | `frontend/src/components/RegionSurface.jsx:403` | **the primary button label** (`.rs-primary-label`) | `Dissect` | `Find parts` |
| 6 | `frontend/src/components/RegionSurface.jsx:463` | empty state, second line | `Dissect the image to see its anatomy, then say what each part does to you.` | `Find the parts of this image, then say what each one does to you.` |
| 7 | `frontend/src/differential/visionActivity.js:13` | `OPERATION_LABEL` **value** | `dissect: 'Dissect',` | `dissect: 'Find parts',` |
| 8 | `frontend/src/differential/VisionActivityRail.jsx:153` | rail scope footnote (`.va-scope`) | `Records dissect, refine, semantic read and find similar — not all vision activity.` | `Records Find parts, Refine, Semantic read and Find similar — not all vision activity.` |
| 9 | `frontend/src/differential/DifferentialWorkspace.jsx:815` | detached-Ground explanation | `{g.label \|\| g.ground_type} — its part was replaced by a re-dissect` | `{g.label \|\| g.ground_type} — its part was replaced when the parts were found again` |
| 10a | `frontend/src/components/RegionDetectorModal.jsx:96` | `<h3 className="rd-title">` | `Dissect the image into its parts` | `Find the parts of this image` |
| 10b | `frontend/src/components/RegionDetectorModal.jsx:138` | busy overlay | `Dissecting…` | `Finding parts…` |
| 10c | `frontend/src/components/RegionDetectorModal.jsx:162` | `.rd-detect-btn` label | `Dissect` | `Find parts` |

Rows 10a–10c are **one optional unit** — take all three or none (§1.3).

### 1.2 Where `Find parts` does NOT slot in — the four grammar hazards

This is the part a naive find-and-replace gets wrong. Each of these is a sentence someone must
*write*, not substitute.

**H1 — the error toast (row 1). `Find parts` cannot be a subject.** `Dissection` is a noun and
takes `failed`. `Find parts` is an imperative verb phrase; *"Find parts failed"* is not English.
The replacement changes voice from nominal to personal — `Couldn’t find the parts —` — which also
matches the register of the surface's other failure copy. Do not write *"Finding parts failed"*:
it is grammatical but reads as a system log, and the trailing *"is the backend running?"* already
carries the diagnostic.

**H2 — the sr-only select label (row 3). No verb belongs here at all.** The `<label>` names what
the `#rs-mode` select *is*, not what pressing it does; a screen reader reads it immediately before
the option list `General · Garments · Body · Textures · Materials · Composition`. *"Find parts
vocabulary"* is unreadable aloud. `Part vocabulary` is a noun phrase, which is the correct part of
speech for a label.

> **Collision warning.** `HW-C8` §C4 step 6 also proposes editing this exact line, to
> `Name the parts as`. **Both proposals cannot ship.** If increment C lands first, this row is
> already satisfied and must be skipped; if this spec lands first, C's step 6 becomes a second
> rewrite of a line that no longer says "Dissection". **Whoever executes second must re-read
> `RegionSurface.jsx:394` before editing it.** This spec does not adjudicate which wins.

**H3 — the rail footnote (row 8). Naive substitution produces two "find"s in one clause.**
*"Records find parts, refine, semantic read and find similar"* is actively confusing — a reader
cannot tell where the first item ends. The fix is not a synonym but a **capitalisation change**:
the footnote summarises the four `OPERATION_LABEL` values rendered directly beneath it at
`VisionActivityRail.jsx:28, 39, 54`, so rendering them as capitalised proper labels
(`Find parts, Refine, Semantic read and Find similar`) makes the list parse and makes the footnote
agree with the entries it describes. This is the single worst line for a mechanical replace.

**H4 — `re-dissect` is a noun with no `Find parts` equivalent (row 9).** There is no noun form:
*"a re-find parts"* is impossible and *"a re-finding"* is worse. The clause must be rewritten to a
temporal one — `replaced when the parts were found again` — which preserves the honesty of the
original (the Ground detached because a *later* run replaced its region) without inventing a noun.

**One consequence that is NOT a hazard, but must be understood before row 7 is applied.**
`OPERATION_LABEL[run.operation]` is interpolated into a sentence at
`frontend/src/differential/visionActivity.js:139`:

```
if (s === 'failed') return `${op} didn’t finish.`;
```

After row 7 this renders **"Find parts didn’t finish."** That reads as a name-as-subject, which is
slightly odd — but it is **exactly the shape already shipping** for the sibling operation
`find_similar: 'Find similar'` (`visionActivity.js:16`), which produces "Find similar didn't
finish." on the same line. The precedent exists and is live. **No new copy is authorized at
`:139`.** Leave it.

### 1.3 `RegionDetectorModal.jsx` — the scout's orphan claim, corrected

**The scout wrote that a repo-wide grep "returns only its own definition and its own CSS import".
That is wrong.** Verified: there are **three** non-self references.

| file:line | reference | does it mount the component? |
|---|---|---|
| `frontend/src/components/RegionDetectorModal.jsx:4` | `import './RegionDetectorModal.css'` | self |
| `frontend/_ds-barrel.mjs:13` | `export { default as RegionDetectorModal } from './src/components/RegionDetectorModal.jsx'` | **no** — an auto-generated design-system barrel, header comment: *"named re-exports of every design-system component"* |
| `.design-sync/config.json:34` | `"RegionDetectorModal": "src/components/RegionDetectorModal.jsx"` | **no** — a path map for the `/design-sync` tool |

**The corrected claim: the component is *unmounted*, not *unreferenced*.** No JSX anywhere renders
`<RegionDetectorModal …/>`; the live surface is `RegionSurface`, mounted at
`frontend/src/components/PostDetailPage.jsx:1061` (inside `.image-display`) and at
`frontend/src/pages/RegionSurfaceLab.jsx:98` (dev harness, routed at `frontend/src/main.jsx:47` as
`lab/region-surface/:postId`). Verified by grepping every `.jsx` under `frontend/src`.

**What the spec does about it: rename it, in the same commit, as one unit.** The reasoning is not
consistency for its own sake —

- it is **still bundled** by `_ds-barrel.mjs`, so its strings can surface in the design-system
  build even though the app never mounts it. A stale `Dissect` there is a stale label in a
  shipped artifact, not in dead code;
- leaving it is the state most likely to mislead the *next* reader, who will grep `Dissect`, get
  three hits in a component file, and not know they are inert;
- three string edits in a file nothing renders carry **zero runtime risk** — the strongest
  possible argument for doing it now rather than tracking it.

**It is nonetheless marked optional in §1.1 and separable in §4**, so that a reviewer who
disagrees can drop rows 10a–10c without touching the other seven. **Deletion of the file is not
proposed and not authorized** (§6).

### 1.4 The two comment lines

Two source comments say "Dissect" and are **not rendered**. They are not user-visible and are
therefore not in the table above, but leaving them makes the frozen/free boundary harder to read
for the next person, so this spec authorizes updating **exactly these two and no other comment**:

| file:line | current comment text | proposed |
|---|---|---|
| `frontend/src/components/RegionSurface.jsx:389` | `passes the next Dissect schedules (selective scheduling).` | `passes the next Find parts run schedules (operation `dissect`; selective scheduling).` |
| `frontend/src/components/ProfileControl.jsx:9` | `Changing the profile changes which specialist passes the next Dissect schedules` | `Changing the profile changes which specialist passes the next Find parts run schedules (operation `dissect`)` |

**Every other comment containing "dissect" is frozen** — `grounds.js:17, 64`, `recall.js:31`,
`regionStore.js:165`, `LandingPage.jsx:41, 62`, `VisionActivityRail.jsx:4`, and every comment in
`backend/`. They describe the *operation*, which is not being renamed.

---

## 2. The frozen list — the safety artifact

**Nothing in this section may change. Not one character.** This is the list that makes the rename
survivable: `dissect` is a wire identity persisted in `vision_runs`, and every row below is either
that identity or something keyed by it.

**37 frozen identifiers, plus 68 test lines that assert on them.**

### 2.1 Backend contracts — 16 identifiers

`backend/services/vision_orchestrator/vision_run_contracts.py`. (Note the path: the task brief and
some earlier docs write `backend/services/vision_run_contracts.py`; **the file is one directory
deeper**, under `vision_orchestrator/`. Verified.)

| # | file:line | identifier | value | why frozen |
|---|---|---|---|---|
| F1 | `vision_run_contracts.py:44` | `OPERATION_DISSECT` | `"dissect"` | persisted as `operation` on every `vision_runs` document |
| F2–F15 | `vision_run_contracts.py:48–61` | `STAGE_RECEIVE`, `STAGE_FETCH_IMAGE`, `STAGE_ROUTE_DOMAIN`, `STAGE_SEGMENT_FASHION`, `STAGE_SEGMENT_ARCH`, `STAGE_SEGMENT_GENERAL`, `STAGE_SEGMENT_COARSE`, `STAGE_MERGE_ANCHORS`, `STAGE_FALLBACK_DETECT`, `STAGE_DECOMPOSE_FINE`, `STAGE_MERGE_CURATOR`, `STAGE_CANONICALIZE`, `STAGE_PERSIST`, `STAGE_COMPLETE` | `"dissect.receive"` … `"dissect.complete"` (14) | telemetry stage identity; persisted per event |
| F16 | `vision_run_contracts.py:267` | default arg `operation: str = OPERATION_DISSECT` | — | changes the default operation of every run if touched |

Not frozen-by-this-spec but adjacent and easy to hit by accident: `OPERATION_REFINE` /
`OPERATION_SEMANTIC_READ` / `OPERATION_FIND_SIMILAR` and every `refine.*` / `semantic_read.*` /
`find_similar.*` stage id at `vision_run_contracts.py:64–85`. **This spec renames nothing in that
family either.**

### 2.2 Backend service and router — 1 identifier, 13 call sites

| # | file:line | identifier | why frozen |
|---|---|---|---|
| F17 | `backend/services/vision_run_service.py:316` | `DissectRunRecorder = VisionRunRecorder` | public back-compat alias; exported at `:46`, documented at `:11` and `:217`, used at `backend/routers/posts.py:665` |

Frozen call sites that reference F1/F17 and must not be edited:
`vision_run_service.py:31, 46, 65, 183, 217, 218, 227, 313, 316`;
`backend/routers/posts.py:665, 666, 891, 893`.

**No backend file is edited by this spec at all** (§6). This table exists so that a reviewer can
confirm the diff is empty on the backend side, not because anything here is at risk from a
correctly-scoped change.

### 2.3 The route — 1 identifier

| # | identifier | declared | called |
|---|---|---|---|
| F18 | `POST /{post_id}/detect-regions` | `backend/routers/posts.py:634` | `frontend/src/components/RegionSurface.jsx:171`, `frontend/src/components/RegionDetectorModal.jsx:35` |

**Verified: the string `dissect` appears in no URL path anywhere in the repo.** Grepped every
`.py`, `.js`, `.jsx` and `.json` outside `node_modules`/`.git` for `dissect` co-occurring with a
path literal, `fetch(`, `axios`, `@router` or `/api/` — the only hits are prose comments in
`backend/routers/posts.py` and a Python local variable `dissected` at `posts.py:1482`. Also frozen:
the `mode` / `lens` / `coarse_only` request keys (`RegionSurface.jsx:174–177`) and every
`region_annotations` / `domain_profile` / `vision_runs` field.

### 2.4 Frontend wire values — 19 identifiers

`frontend/src/differential/visionActivity.js`.

| # | file:line | what | why frozen |
|---|---|---|---|
| F19 | `:10` | `OPERATIONS = ['dissect', 'refine', 'semantic_read', 'find_similar']` | wire values; **asserted by a test**, see below |
| F20 | `:13` | the **key** `dissect` in `OPERATION_LABEL` | only the *value* on this line changes (row 7) |
| F21 | `:21` | the **key** `dissect` in `EPISTEMIC` | keyed by wire value. The *value* `'Visual evidence produced.'` is prose and is **also frozen** — it is the honesty line that made `Read parts` unusable |
| F22 | `:29` | the **key** `dissect` in `AFFECTS` (value `'geometry'`) | keyed by wire value |
| F23–F36 | `:90–103` | the 14 `STAGE_LABEL` keys `'dissect.receive'` … `'dissect.complete'` | must match F2–F15 **exactly** or every stage renders through the `humanStage` fallback at `:125–126` |
| F37 | `:36` | `latestUrl` → `?operation=${operation}` | `dissect` travels as a query-string value on every rail fetch |

Also frozen (code, not strings): the three `OPERATION_LABEL[…]` lookups at `visionActivity.js:134,
218, 255` — they key off `run.operation` / `operation`, so they keep working unchanged and must
not be "helped".

### 2.5 Tests that assert on `dissect` — 68 lines, and what would break

**Grepped `backend/tests/` and `frontend/src/**/*.test.*` in full.**

| suite | file | lines containing `dissect` | breaks if the rename is over-applied to… |
|---|---|---|---|
| backend | `backend/tests/test_circulation_spine_p1.py` | 40 | `OPERATION_DISSECT` (`:119, 138`), the literal `"dissect"` (`:138`), stage ids (`:131, 139, 148, 171–173, 245, 255–262, 459–465, 491, 516–518, 548, 562, 570, 576, 615, 652–655, 664, 678`), `DissectRunRecorder` (`:286, 295, 305, 676`), the projected operation (`:454`) |
| backend | `backend/tests/test_circulation_spine_p2_1.py` | 7 | `svc.DissectRunRecorder is svc.VisionRunRecorder` (`:211–212`), `operation="dissect"` round-trip (`:217, 220, 222, 301`) |
| backend | `backend/tests/test_rehearsal_r1.py` | 1 | comment only (`:633`) — cannot break |
| frontend | `frontend/src/differential/visionActivity.test.js` | 17 | **`expect(OPERATIONS).toEqual(['dissect', …])` at `:31`** — the single most brittle assertion; plus `map.dissect.run.operation` (`:49, 88`), stage ids (`:122–123, 170, 174, 265`), `deriveEntry('dissect', …)` (`:126, 168, 201`) |
| frontend | `frontend/src/differential/recall.test.js` | 2 | comments only (`:67, 117`) |
| frontend | `frontend/src/differential/grounds.test.js` | 1 | test *name* only (`:74` `'degrades gracefully when a re-dissect replaced the region'`) |

**The measurement the scout could not make, made:**

> **No test anywhere asserts on the string `Dissect`, on `OPERATION_LABEL`, or on any rendered
> label of the `dissect` operation.**

Verified by grepping `visionActivity.test.js` for `Dissect`, `OPERATION_LABEL` and `label` — the
only label assertions are `'Couldn’t read activity'` (`:96, 103`), `'No recorded activity'`
(`:101, 112, 202`) and **`'Semantic read didn’t finish.'` (`:229`)**, which exercises
`friendlyMessage` through `semantic_read`, **not** `dissect`. Row 7 of §1.1 therefore breaks
nothing. There is no JSX/DOM test for `RegionSurface`, `VisionActivityRail` or
`DifferentialWorkspace` — `frontend/src` contains exactly seven `*.test.*` files
(`differential/{freehandTaper,grounds,recall,visionActivity}.test.js`, `lib/maskGeometry.test.js`,
`state/perceptMentions.test.js`, `components/blocknote/blockConvert.test.js`), none of which mounts
a component. **The tests will not catch a bad label. Only §5's eyes-on step will.**

---

## 3. Copy rules

Stated so a future implementer can apply them without re-deriving §1.

**R1 — The UI surface may say `Find parts`.** Any string a curator can read, hear via a screen
reader, or see in a tooltip is display copy and may use the product label.

**R2 — Telemetry, contracts and operation names stay `dissect`, permanently.** Every value that is
persisted, keyed, sent over the wire, or compared against a backend constant keeps `dissect`. If a
string is a *key*, a *route*, a *query value*, a *stage id* or a *Python/JS identifier*, R1 does
not reach it. **When R1 and R2 disagree about the same line, R2 wins and the line is split** — which
is exactly what row 7 does: the key stays `dissect`, the value becomes `Find parts`.

**R3 — A display name is not a synonym for the operation name, and the code must say so.** The two
diverge from this commit onward, and the divergence must be documented at the point where it is
easiest to get wrong.

**R4 — The register is `parts`, not `dissection`.** The surface's noun is already `parts`
(`RegionSurface.jsx:380, 418, 435, 438, 462, 467`) and the backend already renders
`dissect.persist_regions` as *"Saved parts"* (`visionActivity.js:102`). New copy on this surface
uses `part` / `parts`; it does not reintroduce `dissect`, `dissection`, `anatomy` as a verb, or
`segment` as a curator-facing word.

**R5 — Do not repair the register elsewhere.** `Sūkṣma · fine anatomy`
(`RegionDetectorModal.jsx:95`), `Chiasm`, `Differential`, `Aletheia`, `Unconcealment` and the
`Quiet / Outline / Focus` map switch are all untouched (§6).

### 3.1 The doc sentence, and where it goes

**Two placements, both mandatory, both tiny.**

**(a) A code comment** immediately above `OPERATION_LABEL` at
`frontend/src/differential/visionActivity.js:12` — the exact line where the two names diverge:

> `// DISPLAY NAME ≠ OPERATION NAME. The values below are curator-facing copy and may be`
> `// rewritten freely; the KEYS are wire identities. 'dissect' is persisted as `operation` on`
> `// every vision_runs document, prefixes all fourteen 'dissect.*' stage ids (which must match`
> `// backend/services/vision_orchestrator/vision_run_contracts.py:44-61 exactly), and is sent`
> `// as the ?operation= value by latestUrl() below. Renaming a key here silently empties the`
> `// rail. HW-C9 renamed the label 'Dissect' -> 'Find parts'; the operation did not change.`

**(b) One paragraph** appended to `vault/Build/Architecture Lab/Decisions/` as a new short note,
`HW-C9-display-name-vs-operation-name.md`, so the rule is findable without reading source:

> **`Find parts` is the display name; `dissect` is the operation name. They are permitted to
> differ and, since HW-C9, they do.** The label is curator-facing copy and may be rewritten at any
> time. The operation id `dissect` is a wire identity: it is persisted as `operation` on every
> `vision_runs` document, it prefixes all fourteen `dissect.*` telemetry stage ids, and it travels
> as the `?operation=` query value on the Vision Activity Rail's fetch. **Renaming the operation to
> match the label would orphan every run already recorded.** When a future lane changes the label
> again, it changes §1.1 row 7's *value* and nothing else.

**No other doc is edited by this spec.** In particular `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md` and
the HW-C8 scout finding are all left as written — `CONTEXT.md:266` describes the 2026-06-23
`RegionDetectorModal` state and is a historical record, not live copy.

---

## 4. Rollback

**The revert is one command, and it is total.**

The change must land as **one commit touching exactly five source files plus the two doc
placements** — no unrelated edits, no reformatting, no import reordering. Given that:

```
git revert <sha>          # the whole change, including the doc note
```

**Why it is safe.** The commit contains no migration, no schema edit, no route edit, no backend
edit, and no persisted value. Nothing written to Mongo while `Find parts` was on screen differs by
one byte from what would have been written under `Dissect` — the operation, the stage ids and the
payload keys are identical before and after (§2). **There is no state to unwind, so the revert
cannot leave a half-migrated system.** This is the property that makes the change worth doing
first in the cycle.

**Partial rollback**, if only the orphan rows are contested: revert
`frontend/src/components/RegionDetectorModal.jsx` alone
(`git checkout <sha>^ -- frontend/src/components/RegionDetectorModal.jsx`). Rows 10a–10c are
independent of rows 1–9; nothing imports across them.

**How to verify the revert is complete.** Run these three from the repo root:

| # | command | must return |
|---|---|---|
| RB1 | `grep -rn "Find parts" frontend/src \| wc -l` | **0** |
| RB2 | `grep -rni "dissect" frontend/src \| wc -l` | **59** |
| RB3 | `grep -rni "dissect" backend/ \| wc -l` | **107** |

RB2 and RB3 are the pre-change baselines measured for this spec on 2026-07-22 (§5). **If RB2
returns 59 and RB1 returns 0, the frontend is byte-identical on this axis.** If RB3 ever differs
from 107 the change was out of scope in the first place and the revert is not the whole story —
escalate rather than proceeding.

---

## 5. Verification steps for the implementer

### 5.1 Before touching anything — record the baseline

| # | command | expected today (verified 2026-07-22) |
|---|---|---|
| V1 | `grep -rni "dissect" frontend/src \| wc -l` | **59** |
| V2 | `grep -rni "dissect" frontend/src \| grep -v ".test." \| wc -l` | **38** |
| V3 | `grep -rni "dissect" backend/ \| wc -l` | **107** (59 non-test + 48 test) |
| V4 | `grep -rni "dissect" chrome-extension/ dashboard/ showcase/ design-system/ \| grep -v node_modules \| wc -l` | **0** |
| V5 | `grep -rn "Find parts" frontend/src \| wc -l` | **0** |

**If V1 or V3 disagrees with this table, the tree has moved since the spec was written. Re-verify
§1.1's line numbers before editing.**

### 5.2 After the change — the arithmetic must close

| # | command | expected, full change (incl. rows 10a–10c) | expected, if the orphan is skipped |
|---|---|---|---|
| V6 | `grep -rni "dissect" frontend/src \| wc -l` | **48** | **51** |
| V7 | `grep -rni "dissect" backend/ \| wc -l` | **107** — unchanged | **107** |
| V8 | `grep -rn "Find parts" frontend/src \| wc -l` | **4** | **3** |
| V9 | `git diff --name-only` | exactly the 5 frontend files (+ the new Decisions note) | 4 files |

**Where the 11 removed hits go (V1 59 → V6 48).** `RegionSurface.jsx` 7 → 1 (six strings removed;
the comment at `:389` is rewritten but keeps the word inside backticks — **if you write the
comment without the literal `dissect`, V6 becomes 47; either is acceptable, but say which**).
`VisionActivityRail.jsx` 2 → 1 (`:4` comment stays). `DifferentialWorkspace.jsx` 1 → 0.
`RegionDetectorModal.jsx` 3 → 0. `visionActivity.js` stays at **18** — row 7 changes a value, not
the key, so `:13` still matches the grep. That last fact is the check that the frozen list held.

**V8's four hits are:** `RegionSurface.jsx:403`, `visionActivity.js:13`,
`VisionActivityRail.jsx:153`, `RegionDetectorModal.jsx:162`. Rows 4 and 6 read *"Find the parts"*
and row 2 reads *"Finding parts"* — deliberately, and they do not match V8's literal.

### 5.3 Tests to run

| # | command | expected |
|---|---|---|
| V10 | `cd frontend && npx vitest run` | green. Nothing in §2.5 touches display copy; a failure here means a **key** was renamed |
| V11 | `python -m pytest backend/tests/test_circulation_spine_p1.py backend/tests/test_circulation_spine_p2_1.py` | green. These are the 47 lines that assert on `dissect` as identity. A failure means the backend was edited, which §6 forbids |
| V12 | `cd frontend && npm run build` | succeeds — catches a broken JSX string or an unbalanced quote, which is the realistic failure mode of a copy edit |

**V11 must be run even though no backend file is edited.** It is the cheap proof that the diff
really is frontend-only.

### 5.4 What to look at on screen

Two dev servers are already running; **do not start a third.**

| # | screen | control | expect |
|---|---|---|---|
| V13 | post detail → the region surface (`PostDetailPage.jsx:1061`, inside `.image-display`) | the primary button `.rs-primary` | reads **`Find parts`**; hover tooltip reads **`Find the parts of this image`** |
| V14 | same, on a post with no regions | the empty state `.rs-empty` | *"No parts yet."* then *"Find the parts of this image, then say what each one does to you."* |
| V15 | same, press the button | `.rs-busy` (`role="status"`) | *"Finding parts…"* — and the button label must **not** wrap or clip at narrow pane widths. `Find parts` is 10 characters against `Dissect`'s 7, and `RegionSurface.jsx:402`'s comment says *"the label hides when the pane is cramped; the icon carries it"* — **confirm at a narrow window that it hides cleanly rather than overflowing.** This is the one visual regression the change can actually cause |
| V16 | same, with the backend stopped | `.rs-error` (`role="alert"`) | *"Couldn't find the parts — is the backend running?"* with the `Retry` button intact |
| V17 | Differential workspace → Vision activity rail, expanded | `.va-scope` footnote and the four `.va-op` entries | footnote reads *"Records Find parts, Refine, Semantic read and Find similar — not all vision activity."* and the first entry's label reads **`Find parts`** with its epistemic line **unchanged**: *"Visual evidence produced."* / `geometry` |
| V18 | expand that entry on a post with a recorded run | the stage list | stage names still read *Received request … Saved parts … Complete* — **if any stage renders as raw `dissect.something`, a `STAGE_LABEL` key was broken (F23–F36) and the change must be reverted** |
| V19 | screen reader or devtools accessibility pane, on `#rs-mode` | the `<label class="rs-sr">` | announces **`Part vocabulary`** before the option list |

**V18 is the highest-value check in the list** — it is the only one that would catch an
over-applied rename that the test suite lets through.

---

## 6. What this spec does NOT authorize

- **No route change.** `POST /{post_id}/detect-regions` (`backend/routers/posts.py:634`) and every
  other endpoint stay exactly as they are. No new route, no alias, no redirect.
- **No schema change.** No `vision_runs` field, no `region_annotations` field, no `domain_profile`
  field, no request or response key. The `mode` / `lens` / `coarse_only` payload
  (`RegionSurface.jsx:174–177`) is untouched.
- **No backend edit of any kind.** Not one character under `backend/`. Every identifier in §2.1 and
  §2.2 is frozen, including `OPERATION_DISSECT`, all fourteen `STAGE_*`, and the
  `DissectRunRecorder` alias. `git diff --stat` must show zero backend files (V9).
- **No telemetry or contract rename.** The wire value stays `dissect` in the `OPERATIONS` array,
  in every `EPISTEMIC` / `AFFECTS` / `STAGE_LABEL` key, and in the `?operation=` query value.
- **No test edit.** All 68 lines in §2.5 stay as written. If a test needs changing, the change is
  out of scope and the diff is wrong.
- **No new component, no new file** other than the one Decisions note in §3.1(b). No new page, no
  route entry in `frontend/src/main.jsx`, no modal, no panel.
- **No deletion of `RegionDetectorModal.jsx`**, despite it being unmounted. It is still exported by
  `frontend/_ds-barrel.mjs:13` and mapped in `.design-sync/config.json:34`; removing it is a
  separate decision with its own justification burden.
- **No redesign.** No layout change, no CSS change of any kind — `.rs-primary`, `.rs-busy`,
  `.rs-error`, `.va-scope` and `.rd-detect-btn` keep their existing rules. If V15 shows the longer
  label overflowing, **stop and report it**; do not fix it in this commit.
- **No change to `Chiasm`, `Differential`, `Aletheia`, `Unconcealment`, `Sūkṣma · fine anatomy`,
  the `Quiet / Outline / Focus` map switch, or the `MODES` options**
  (`RegionSurface.jsx:17–24`). The register audit that produced `Find parts` is not a licence to
  touch the rest of the vocabulary.
- **No execution of HW-C8 increment A or C.** In particular `ProfileControl.jsx` is edited only at
  `:9`, a comment (§1.4). C's chip renames are a separate gate, and C's proposed rewrite of
  `RegionSurface.jsx:394` **collides with row 3** — see the warning in §1.2 H2.
- **No commit, no push, no PR from this lane.** This document is a spec.

## 7. What was deliberately NOT done in this lane

- **No source file was edited, created or deleted.** The only file written is this spec.
- **No test suite was run.** §2.5's conclusion — that nothing asserts on the display string — is
  from reading the assertions, not from executing them. V10/V11 exist because reading is not
  running.
- **Nothing was checked in a browser.** Every claim about what appears on screen is derived from
  JSX. §5.4 is therefore mandatory, not decorative — and V15's clipping risk is a *prediction* from
  a character count and a comment at `RegionSurface.jsx:402`, not an observation.
- **The `Find parts` / `Name the parts as` collision at `RegionSurface.jsx:394` was reported, not
  resolved.** It needs whoever sequences increments B and C to decide; this lane may not.
- **No decision was taken on deleting `RegionDetectorModal.jsx`**, only on whether to rename inside
  it.
- **No Mongo query was run**, so nothing here says how many `vision_runs` documents carry
  `operation: "dissect"` today. The frozen list is argued from the code path, not from a count.
