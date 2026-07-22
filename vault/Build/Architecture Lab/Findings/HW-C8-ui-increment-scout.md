# HW-C8 — Three UI increments: saver primary action, the "Dissect" label, profile controls

**READ-ONLY scout. No source file under `frontend/`, `chrome-extension/`, `backend/`,
`dashboard/`, `showcase/` or `design-system/` was edited, created or deleted. Nothing was staged,
committed or pushed. No dev server was started. No Mongo access.** Horizon Weave cycle 8, Lane 4.
This lane proposes; a build lane implements.

OBSERVED = read in the file at the cited line. INFERRED = my reading of what it means. Kept apart
throughout.

---

## A. The saver's primary action

### A1. What the code actually does today

The whole saver overlay is **one file**: `chrome-extension/content.js` (1531 lines), styled by
`chrome-extension/content.css` (434 lines). There is no React, no build step, no component tree.
`frontend/` has no saver/hover/overlay surface at all — the only frontend "Aletheia" surfaces are
`frontend/src/components/AletheiaHook.jsx` and `frontend/src/pages/UnconcealQueuePage.jsx`, which
are in-app reading views, not the in-page saver.

**The presence ladder (OBSERVED).** `content.js:22-31` declares it and `:153` holds the state:
`presence` ∈ `'none' | 'whisper' | 'ready'`.

| rung | trigger | what is on screen | file:line |
|---|---|---|---|
| none | default / muted / pointer left | nothing | `content.js:552-557` |
| whisper | pointer dwells `DWELL_MS = 420` ms on an *eligible* image | ONE glyph button, `aria-label` "Read this image with Alexia" | `content.js:503-510`, `:132-141` |
| ready | **click the whisper** | the four-button toolbar | `content.js:521-527`, `:601` |

This is exactly the "click to expand, then pick among tiny buttons" the brief names. The expand
step is `whisper.addEventListener('click', … promoteToReady())` at `content.js:601` — the *only*
route to the toolbar.

**OBSERVED discrepancy.** The comments at `content.js:25-26` and `:130` both say the toolbar can
also be summoned "by the shortcut". There is exactly one `keydown` listener in the file,
`content.js:206-207`, and it only toggles mute (`Alt+Shift+S`). **No summon shortcut exists.** The
whisper click is the sole path. Any plan that assumes a keyboard escape hatch is wrong.

**The four buttons (OBSERVED).** All built by the same factory `toolbarButton(name, label, svg)` at
`content.js:72-79`; all share one class `.ss-tb-btn`; all appended once at `:97-100`.

| ref | label | created | click handler | what it does |
|---|---|---|---|---|
| `brainstormBtn` | `Read` | `:85` | `:1223` → `brainstormImage()` `:792` | POST `/api/v1/posts/brainstorm`, opens the **Aletheia** panel |
| `saveBtn` | `Save` | `:81` | `:1222` → `saveImage()` `:604` | POST `/api/v1/posts/upload-from-url` |
| `splitBtn` | `Split` | `:89` | `:1224` → `queueSplit(currentVideo)` `:841` | queues a video → frame capture job |
| `sweepBtn` | `Save all` | `:93` | `:1225` → `sweepCarousel()` `:1160` | walks the carousel, collects every slide |

Sizing (OBSERVED, `content.css:63-83`): `padding: 7px 12px`, `font-size: 12px`, `svg 14×14`. The
brief's "tiny buttons" is accurate — these are ~28px-tall pills in a 3px-padded pill bar
(`content.css:43-59`).

**Visibility is already contextual — but by hiding, not by promoting (OBSERVED).**
`setToolbarMode(type)` at `content.js:455-463` and `showTarget` at `:465-488`:

| hovered thing | `Read` | `Save` | `Split` | `Save all` |
|---|---|---|---|---|
| video / reel | hidden `:457` | hidden `:458` | shown `:459` | hidden `:462` |
| single image | shown | shown | hidden `:459` | hidden `:480` |
| carousel image | shown | shown | hidden | **shown** `:480` |

So a video hover already shows exactly one button, and a carousel hover already shows three. What
is missing is not the *knowledge* — it is **hierarchy**: nothing is visually primary.

### A2. Is content type already known? — **YES, at the exact decision point. This is the finding.**

**OBSERVED.** `showTarget(el, type)` receives `type` as an argument (`content.js:465`) and computes
carousel-ness on its own line inside the same function:

```
content.js:465   function showTarget(el, type) {
content.js:472       setToolbarMode(type);              // type === 'video' | 'image'
content.js:480       sweepBtn.style.display = findCarousel(el) ? '' : 'none';
```

`type` is resolved upstream by the pointer resolver `onPointerMove` at `content.js:559-590`, which
already runs a three-way discrimination — real `<video>` under the cursor (`videoAtPointStack`,
`:302`), a `pointer-events:none` reel video covering a poster `<img>` (`videoCoversImage`, `:347`),
or a plain photo. `findCarousel(img)` at `content.js:391-405` is a synchronous DOM walk
(`<li>` → `<ul>` track + a chevron pager within 5 ancestors) that is **already being called on every
image hover** at `:480`.

**Therefore: no detection to write, no plumbing to add.** The mapping the brief asks for —

| hovered | primary |
|---|---|
| single image | `Save` |
| carousel | `Save all` |
| video / reel | `Split` |

— is computable from `type` and `findCarousel(el)` **inside `showTarget`, lines 465-488, using only
values that function already has in hand.** Feasibility for A is decided by this fact.

**One caveat, OBSERVED.** `findCarousel` is called only in the `type === 'image'` branch and only
when `!sweeping` (`content.js:476-481`). A carousel hover during an in-flight sweep keeps the old
button state deliberately, so the "Reading N…" progress text at `:1193` stays legible. A primary-slot
rewrite must preserve that guard or it will stomp live progress.

### A3. What "Read with Aletheia" maps to

**OBSERVED.** The `Read` button (`brainstormBtn`, `content.js:85`) → `brainstormImage()` `:792` →
`runBrainstorm()` `:767` → `POST ${API_BASE}/api/v1/posts/brainstorm` (URL built at `:17`) with
`{image_url, source_url, answers}` → renders into the `.sharirasutra-panel` (`:104`) whose header
reads kicker **"Aletheia"** / title **"Unconcealment"** (`content.js:646-647`). The panel shows
lenses with intensity bars (`:705-721`), multiple-choice "Look closer" questions that refine the
reading round by round (`:723-743`, `chooseAnswer` `:785`), and `Concealed` / `Uncertain` footers
(`:749-760`).

So "Read with Aletheia" is a **live product surface**, not a stub — and it is the one action that is
already named with the app's own vocabulary while the button says the generic "Read".

**OBSERVED naming split, worth a decision before any label churn.** The extension carries two names
at once: `manifest.json:3` `"Alexia — Image & Video Saver"`, `manifest.json:4` "Alexia & Aletheia,
unconcealers"; the whisper's `aria-label` says **Alexia** (`content.js:135`) but the panel it opens
says **Aletheia** (`content.js:646`); the tray kicker says Alexia (`content.js:1047`). INFERRED:
Alexia = the collector (save/split/sweep), Aletheia = the reader. That division is coherent and
should be *stated* rather than fixed by renaming — the secondary menu is the natural place to say
"Read with Aletheia" in full.

### A4. Proposal

Two moderately sized buttons in the bar; everything else moves into a menu.

```
[  ▣ Save all  ] [ ⋯ ]        ← carousel hover
[  ▣ Save     ] [ ⋯ ]         ← single image
[  ▣ Split    ] [ ⋯ ]         ← video / reel
```

The `⋯` menu contains, per context:

| context | menu items |
|---|---|
| carousel | **Save this** (`saveImage`), **Read with Aletheia** (`brainstormImage`) |
| single image | **Read with Aletheia** |
| video / reel | *(empty today — `Read` and `Save` are hidden for video at `:457-458`; either leave the menu button out, or unhide `Read` for reels, which is a behaviour change and therefore out of the smallest gate)* |

Sizing: raise `.ss-tb-btn` padding for the primary slot only, keep the ink-bar/no-fill discipline the
CSS comment at `content.css:62` sets out ("Every action shares the same quiet shape … no fills").
The secondary `⋯` stays at today's size.

### A5. Feasibility

| question | answer | evidence |
|---|---|---|
| is the type known at the decision point? | **yes, both of them** | `content.js:465` (`type`), `:480` (`findCarousel`) |
| do the actions need rewiring? | **no** — reuse the four existing handlers verbatim | `content.js:1222-1225` |
| is there a menu/popover precedent in the extension? | **no** — must be built | no popover class in `content.css`; nearest is the tray `.ss-tray` `:113` |
| does state feedback complicate it? | **yes — this is the real hazard** | see below |

**The hazard, OBSERVED.** Progress/success/failure is written by mutating a *specific button ref's*
`<span>` text, at eleven sites: `saveBtn` `:613, 624, 629`; `splitBtn` `:847, 855, 861, 875`;
`sweepBtn` `:1193, 1201, 1207`; plus the resets at `:475, 478, 484`. If the redesign collapses these
into one shared "primary" element, **every one of those writers has to be re-pointed**, and the
carousel case writes to `sweepBtn` from inside an async loop (`:1193`) while the pointer may have
moved on. That is what turns a small change into a large one.

**INFERRED, and this is the design key:** keep all four button objects alive and change only *where
they are parented*. `showTarget` reparents the contextual one into a `.ss-tb-primary` slot and the
rest into the menu. Every existing `textContent` writer keeps targeting its own live element and
needs **zero** edits.

### A6. Smallest implementation gate

**Touches: `chrome-extension/content.js` and `chrome-extension/content.css` only.**

1. `content.js` — after `:100`, replace the flat `appendChild` sequence with two containers inside
   `toolbar`: a primary slot and a `⋯` toggle owning a `.ss-tb-menu` div. The four buttons are still
   constructed exactly as at `:81-95`, unchanged.
2. `content.js:455-488` — `setToolbarMode` / `showTarget` gain ~10 lines: pick the primary from
   (`type`, `findCarousel(el)`), move that node into the primary slot, move the others into the
   menu, hide the `⋯` when the menu would be empty. Preserve the `if (!sweeping)` guard at `:476`
   and the pre-position ordering comment at `:479` (sweep visibility is decided *before*
   `positionToolbar`, because it changes bar width — `:486`).
3. `content.js:559-590` — extend the "pointer is over our own chrome" allowlist at `:567-570` to
   include the menu node, or the menu will dismiss itself on hover.
4. Close the menu wherever the toolbar hides: `hideToolbar()` `:490-499` and `applyMuted()` `:171-183`.
5. `content.css` — one new `.ss-tb-primary` size modifier and one `.ss-tb-menu` popover block,
   both `!important`-guarded like the rest of the file (it runs on hostile third-party CSS).

**Explicitly NOT touched by this gate:** the four click handlers (`:1222-1225`); every
`textContent` state writer; `saveImage` / `brainstormImage` / `queueSplit` / `sweepCarousel`; the
dwell/whisper ladder (`:501-557`); eligibility (`isEligibleImage`); the tray and queue
(`:815-1160`); the Aletheia panel (`:636-800`); `manifest.json`; `popup.js`; every backend endpoint.

**Deliberately deferred, not part of the gate:** unhiding `Read` for reels (a behaviour change);
adding a summon shortcut (the comments promise one, `:25`, `:130` — but adding it is new
functionality); resolving the Alexia/Aletheia naming split.

---

## B. Renaming `Dissect`

### B1. What the code actually does today

**Group 1 — USER-VISIBLE strings. These are the whole rename surface.**

| file:line | string | note |
|---|---|---|
| `frontend/src/components/RegionSurface.jsx:187` | `'Dissection failed — is the backend running?'` | error toast |
| `RegionSurface.jsx:365` | `Dissecting the image…` | busy status |
| `RegionSurface.jsx:394` | `Dissection vocabulary` | screen-reader label on the `#rs-mode` select |
| `RegionSurface.jsx:400` | `title="Dissect the image into its parts"` | primary-button tooltip |
| `RegionSurface.jsx:403` | `Dissect` | **the primary button label** |
| `RegionSurface.jsx:463` | `Dissect the image to see its anatomy, then say what each part does to you.` | empty state |
| `frontend/src/differential/visionActivity.js:13` | `dissect: 'Dissect'` | `OPERATION_LABEL` — the rail's display name |
| `frontend/src/differential/VisionActivityRail.jsx:153` | `Records dissect, refine, semantic read and find similar — not all vision activity.` | rail footnote |
| `frontend/src/differential/DifferentialWorkspace.jsx:815` | `its part was replaced by a re-dissect` | detached-Ground explanation |
| `frontend/src/components/RegionDetectorModal.jsx:96` | `Dissect the image into its parts` | **orphan file — see below** |
| `RegionDetectorModal.jsx:138` | `Dissecting…` | orphan |
| `RegionDetectorModal.jsx:162` | `Dissect` | orphan |

**OBSERVED: `RegionDetectorModal.jsx` is dead.** A repo-wide grep for `RegionDetectorModal` across
`frontend/` and `backend/` returns only its own definition and its own CSS import. Nothing mounts
it. The live surface is `RegionSurface`, mounted at
`frontend/src/components/PostDetailPage.jsx:1061` and `frontend/src/pages/RegionSurfaceLab.jsx:98`.
Renaming inside the orphan is cosmetic; deleting it is a separate decision and not proposed here.

**OBSERVED: the extension has zero occurrences of "dissect".** So does `dashboard/`, `showcase/`
and `design-system/`. The rename is confined to `frontend/src/`.

**Group 2 — NOT user-visible. Must not change.**

| file:line | what | why frozen |
|---|---|---|
| `backend/services/vision_orchestrator/vision_run_contracts.py:44` | `OPERATION_DISSECT = "dissect"` | persisted in `vision_runs` |
| `vision_run_contracts.py:48-61` | `STAGE_RECEIVE … STAGE_COMPLETE`, all `"dissect.*"` | telemetry stage identity |
| `frontend/src/differential/visionActivity.js:10` | `OPERATIONS = ['dissect', …]` | wire values |
| `visionActivity.js:21, 29` | `EPISTEMIC` / `AFFECTS` **keys** | keyed by wire value (the *values* are prose and contain no "dissect") |
| `visionActivity.js:90-103` | `STAGE_LABEL` **keys** `'dissect.receive'` … | must match backend constants exactly |
| `frontend/src/differential/recall.js:31`, `grounds.js:17,64`, `frontend/src/state/regionStore.js:165` | source comments | not rendered |
| `frontend/src/pages/LandingPage.jsx:41, 62` | source comments | not rendered |

**OBSERVED: there is no route to change.** The endpoint is `POST /{post_id}/detect-regions`
(`RegionSurface`'s caller; `RegionDetectorModal.jsx:35` shows the same path). The word "dissect"
appears in **no** URL path anywhere in the repo. This removes the single biggest risk the brief
worried about.

### B2. The register these labels sit in

**OBSERVED vocabulary of the surrounding surfaces:**

- **Chiasm** — the writing/reading workspace. `PostDetailPage.jsx:888` "swaps in over the parked
  (still-mounted) Chiasm shell"; `frontend/src/components/home/ContinueTile.jsx:38`
  "Continue in Chiasm"; `frontend/src/pages/LandingPage.jsx:248` "Chiasm — the crossing.";
  slash-menu group `'Chiasm'` at `Manuscript.jsx:105-123`.
- **Differential** — `PostDetailPage.jsx:1050` a single `◈ Differential` button, tooltip
  "Open Differential — construct Percepts from this image".
- **Aletheia / Unconcealment** — `content.js:646-647`; `UnconcealQueuePage.jsx:88` "Aletheia drafts
  a reading for each image".
- **Sūkṣma · fine anatomy** — `RegionDetectorModal.jsx:94` (orphan, but it set the register).

**And the word the live surface already uses everywhere is `parts`** (OBSERVED, `RegionSurface.jsx`):
`:380` "N/M parts", `:418` "Mark a part", `:435` "Filter parts by category", `:438` "All parts",
`:462` "No parts yet.", `:467` `aria-label="Parts of the image"`. Backend agrees:
`visionActivity.js:102` renders `dissect.persist_regions` as **"Saved parts"**.

So the noun is settled and shared. Only the verb is wrong.

### B3. Recommendation — **`Find parts`**

**One line: the surface already calls them "parts" in six places; "Find parts" is the verb that
matches the noun the app already speaks, is honest about what the operation produces, and needs no
glossary for a first-time user.**

The argument, and the rejections, are grounded rather than aesthetic:

- **`Read parts` — reject, it would lie.** `visionActivity.js:19-31` draws a deliberate honesty
  line: `dissect` → *"Visual evidence produced."* / affects **geometry**; `semantic_read` →
  *"Interpretation only — geometry unchanged."* / affects **interpretation**. Labelling the geometry
  operation "Read" collides head-on with the operation that is genuinely the reading one, and
  Semant's own telemetry copy is written specifically to keep them apart. This is the strongest
  single argument in the set.
- **`Map image` — reject, the word is taken.** `RegionSurface.jsx:371-378` renders a control group
  literally commented "map switch", class `rs-maps`, `MAPS = [Quiet, Outline, Focus]`
  (`RegionSurface.jsx:30-34`). "Map" already names *how the parts are drawn*. Reusing it for *finding*
  them puts two different meanings a few pixels apart.
- **`Unfold` — reject, on legibility not on register.** It is the best-sounding candidate and sits
  well beside Chiasm and Unconcealment, but a first-time user pressing "Unfold" cannot predict that
  an image gains labelled outlines. The brief asks for both, and "Unfold" only delivers one.
- **`Open` — reject.** It is the most overloaded verb in any UI; on a surface with panels, a
  lightbox, an overflow menu and a modal, it will read as "open something".
- **`Dissect` — the mismatch is real.** It is the only clinical word on a surface otherwise built
  from *parts, anatomy, quiet, focus, felt unit, what each part does to you*
  (`RegionSurface.jsx:463`). "Dissect the image to see its anatomy, then say what each part does to
  you" contains the whole problem in one sentence: it opens surgical and ends phenomenological.

`Find parts` is quiet, is a verb phrase a novice parses instantly, does not claim interpretation, and
inherits the noun the rest of the pane already uses. In the activity rail it reads honestly:
*Find parts · Visual evidence produced · geometry*.

Secondary derived strings: `Finding parts…` (busy), `Could not find parts — is the backend
running?` (error), `Part vocabulary` (the `#rs-mode` sr-label), `Find the parts of this image`
(tooltip), and for the empty state *"Find the parts of this image, then say what each one does to
you."*

### B4. Feasibility and smallest gate

Pure string substitution. No behaviour, no props, no network, no schema.

**Touches:**
- `frontend/src/components/RegionSurface.jsx` — six strings: `:187, 365, 394, 400, 403, 463`.
- `frontend/src/differential/visionActivity.js` — **one value only**, `:13`
  `dissect: 'Dissect'` → `'Find parts'`. The key stays `dissect`.
- `frontend/src/differential/VisionActivityRail.jsx:153` — the prose footnote.
- `frontend/src/differential/DifferentialWorkspace.jsx:815` — "replaced by a re-dissect" →
  "replaced when the parts were found again".
- optional, cosmetic: `RegionDetectorModal.jsx:96, 138, 162` (orphan).

**Must NOT change:** `visionActivity.js:10` `OPERATIONS`; the `EPISTEMIC`/`AFFECTS`/`STAGE_LABEL`
**keys** (`:21, 29, 90-103`); every `STAGE_*` and `OPERATION_DISSECT` in
`backend/services/vision_orchestrator/vision_run_contracts.py:44-61`; the `/detect-regions` route;
the `mode` / `lens` / `coarse_only` payload keys; every DB field. The backend operation stays
`dissect` end to end — this is a display-layer change and nothing else.

**Check before merging (OBSERVED risk):** `frontend/src/differential/visionActivity.test.js`,
`recall.test.js` and `grounds.test.js` exist and reference `dissect`. Whether any of them asserts on
`OPERATION_LABEL.dissect` was not verified in this lane — a build lane must run the suite. Flagged,
not measured.

---

## C. Profile / category controls

### C1. What the code actually does today — and one correction to the brief

**OBSERVED: the chips live in `frontend/src/components/ProfileControl.jsx`**, rendered inside the
region pane at `RegionSurface.jsx:390`. There are **three** distinct control vocabularies in that
pane, not one, and they do genuinely different things.

**Group 1 — the profile chips (`ProfileControl.jsx:70-82`).**

| control | file:line | what it really switches |
|---|---|---|
| `General` | `:74` — a `<button>` that is **`disabled` and permanently `is-on`** | always-scheduled cheap pass |
| `Fashion` / `Architecture` / `Painting` | `:75-79`, from `SPECIALISTS` at `:14` | toggles membership in `domain_profile.chosen` |
| `Auto` | `:80-81` → `runAuto()` `:37-44` | `POST /{postId}/domain-profile/propose` — re-runs classification |

`toggle()` `:58-62` → `override()` `:46-56` → `PATCH /{postId}/domain-profile` with `{chosen}`.
Server-side, `backend/services/domain_profiles.py:36-44` `passes_for()` maps the chosen set to
adapter names via `PROFILE_PASSES` at `:26-33`:

| profile | scheduled adapters | `domain_profiles.py` |
|---|---|---|
| general | `yolo11n_seg`, `sam21_hiera_tiny` | `:27` |
| fashion | `fashionpedia_r50fpn`, `sam21_hiera_tiny` | `:28` |
| architecture | `segformer_b0_ade`, `sam21_hiera_tiny` | `:29` |
| painting | `sam21_hiera_tiny`, `segformer_b0_ade` | `:32` |

**So the chips choose which detectors run. They change what can be found.** That is a capability
switch, not a filter, not a label vocabulary.

**Group 2 — the "YOLO/SAM model selectors". CORRECTION: they are not selectors.**

**OBSERVED, `ProfileControl.jsx:84-91`:** the `pc-passes` row renders `<span>` elements, not
buttons. They have no `onClick`, no `aria-pressed`, no handler of any kind. They read
`profile.scheduled_passes` (`:64`) through `PASS_LABEL` (`:16-19`, mapping `yolo11n_seg`→`YOLO`,
`segformer_b0_ade`→`SegFormer-ADE`, `sam21_hiera_tiny`→`SAM`, `fashionpedia_r50fpn`→`Fashionpedia`,
`segformer_clothes`→`Garments`) and append a state from `GET /vision/capabilities` (`:28-33`,
`passState` `:68`) — `ready` / `deferred` / `unavailable` (`:89`).

**They are a read-only consequence display: "here is what the profile you picked will actually
run, and whether it is available."** The brief's premise that the user is picking models is
factually wrong. This changes the recommendation materially — there is nothing to "hide behind
advanced", because nothing is selectable. What exists is an honest status readout, and it is the
*only* place in the UI where an unavailable model is surfaced at all.

**Group 3 — the subdivision `MODES` select (`RegionSurface.jsx:17-24`, rendered `:393-398`).**
`General · Garments · Body · Textures · Materials · Composition`, sr-labelled "Dissection
vocabulary". This is sent as `mode` on `/detect-regions` and, per
`backend/services/vision_service.py:532-543, 582`, selects a `MODE_FOCUS` prompt vocabulary
(`vision_service.py:747` "fine semantic decomposition vocabularies (one per mode)") for the VLM's
fine pass. **This one really is a label vocabulary** — it steers *what the parts get called*, not
which detector runs.

Two of these three groups sit within ~20 lines of each other in the same pane, both presented as
rows of small controls, and nothing on screen tells the user that one changes capability and the
other changes wording.

### C2. Proposal — a quieter vocabulary, with the capability honesty kept

Rename the chips from *what the domain is called* to *what the image is*, and let the existing
`pc-reason` line (`ProfileControl.jsx:83`, currently rendering the server's
`"auto: fashion 0.71, architecture 0.12 …"`) carry the honesty.

| group | current | proposed | file:line |
|---|---|---|---|
| eyebrow | `Profile` | `This image is` | `ProfileControl.jsx:73` |
| chip | `General` | `Anything` (still always on, still disabled) | `:74` |
| chip | `Fashion` | `Clothing` | `:78` via `SPECIALISTS` `:14` |
| chip | `Architecture` | `Built space` | `:78` |
| chip | `Painting` | `Painted surface` | `:78` |
| button | `Auto` | `Sense it` | `:80-81` |
| passes row | bare pills, always visible | same pills under a collapsed `What will look` disclosure | `:84-92` |
| pass labels | `YOLO`, `SAM`, `SegFormer-ADE`, `Fashionpedia`, `Garments` | **unchanged** | `:16-19` |
| select sr-label | `Dissection vocabulary` | `Name the parts as` | `RegionSurface.jsx:394` |
| select options | `General … Composition` | unchanged | `RegionSurface.jsx:17-24` |

**`Fashion → Clothing`, not `Garments`, deliberately.** `Garments` is already taken twice: it is a
`MODES` option (`RegionSurface.jsx:19`) and a `PASS_LABEL` value (`ProfileControl.jsx:18`,
`segformer_clothes`). Using it a third time, for a different mechanism, in the same pane, would
create a genuine three-way collision.

**On the YOLO/SAM controls specifically: keep them, keep their names, collapse them by default.**
Renaming `YOLO` to something perceptual would be the one change here that is straightforwardly
dishonest — these strings name real model artifacts and are the user's only signal when a model is
`unavailable` (`ProfileControl.jsx:86-90`). Hiding them entirely removes that signal. A disclosure
that is closed at rest and reads "What will look · 2 ready" satisfies "quieter" without deleting
information.

### C3. Where a rename would MISLEAD — stated plainly

1. **The chips are not a view filter, and a perceptual name will imply they are.** Choosing
   `Built space` schedules `segformer_b0_ade` (`domain_profiles.py:29`); *not* choosing it means
   that model never runs and its regions **do not exist**, not "are hidden". If a user reads
   `Clothing / Built space / Painted surface` as three lenses onto the same findings, the label has
   lied about behaviour. Mitigation: the `pc-reason` line must survive the change and should be
   rewritten to say what will and will not be looked for — it is the only honesty carrier in the
   component.
2. **The chips are cumulative, not exclusive.** `toggle()` `:58-62` and `_normalise_chosen`
   (`domain_profiles.py:103-109`) build a *set*; `general` is always re-added. `This image is` reads
   singular and may suggest a radio group. `aria-pressed` is already correct (`:77`); the copy must
   match it.
3. **`Auto → Sense it` hides a network call.** `runAuto()` `:37-44` POSTs and re-classifies. A
   softer verb should not make it look free or local.
4. **A quieter chip row makes the two groups look even more alike.** After the rename, the profile
   chips and the `MODES` select will both read as gentle perceptual words while one changes what can
   be found and the other only changes wording. INFERRED: the pane may need a one-line separator
   before this is shipped, and that is a layout change — outside the gate below and worth its own
   decision.
5. **`General` is a disabled always-on chip** (`:74`). Renaming it to `Anything` while it stays
   unclickable is fine, but it should carry a tooltip; today's is "Always on — the cheap general
   pass", which is accurate and should be preserved in softer words rather than dropped.

### C4. Smallest implementation gate

**Touches: `frontend/src/components/ProfileControl.jsx`, `frontend/src/components/ProfileControl.css`,
and one sr-only string in `frontend/src/components/RegionSurface.jsx:394`.**

1. `ProfileControl.jsx` — add a display-name map beside `PASS_LABEL` (`:16`), e.g.
   `{fashion:'Clothing', architecture:'Built space', painting:'Painted surface'}`, and use it in the
   chip body at `:78` **in place of `s[0].toUpperCase() + s.slice(1)` only**. `SPECIALISTS` at `:14`
   and every value posted by `toggle()` `:58-62` stay `'fashion' | 'architecture' | 'painting'`.
2. `:73` eyebrow string; `:74` `General` label + tooltip; `:80-81` `Auto` label + tooltip.
3. `:84-92` — wrap the existing `pc-passes` map in a `<details>` (or a `useState` disclosure),
   default closed, summary showing the count and any non-`ready` state. The `<span>` rows,
   `PASS_LABEL`, `passState` and the `title` attribute at `:87` are all left as-is.
4. `:83` — keep `pc-reason`; reword the copy only.
5. `ProfileControl.css` — one disclosure block.
6. `RegionSurface.jsx:394` — the sr-only label string.

**Explicitly NOT touched:** `backend/services/domain_profiles.py` in any respect —
`PROFILE_PASSES` `:26-33`, `passes_for` `:36`, `PROFILES` `:19`, `SPECIALISTS` `:20`,
`ROUTER_VERSION` `:21`, `DEFAULT_GATE` `:22`; the `PATCH /{postId}/domain-profile` payload
(`ProfileControl.jsx:49-52`); `POST /{postId}/domain-profile/propose`;
`GET /vision/capabilities`; `PASS_LABEL` values; the `MODES` options themselves
(`RegionSurface.jsx:17-24`); the `mode` value sent to `/detect-regions`; every persisted
`domain_profile` field.

---

## Combined ranking — value / risk

| | increment | value | risk | ratio | why |
|---|---|---|---|---|---|
| **1** | **B — `Dissect` → `Find parts`** | high | **very low** | **best** | pure display strings in 4 files; no route contains "dissect"; backend constants untouched; fully reversible in one revert. Fixes the loudest register mismatch in the app. Only unknown is whether a `differential/*.test.js` asserts on `OPERATION_LABEL`. |
| **2** | **A — contextual primary in the saver** | **highest raw value** | medium | good | the type is already in hand at `content.js:465` and `:480`, so there is no detection work — the entire risk sits in the eleven state-label writers, and reparenting the four existing buttons instead of merging them removes that risk. One file plus its CSS, on a surface with no test coverage and hostile host pages. |
| **3** | **C — profile vocabulary** | medium | medium | lowest | mechanically the safest diff (a label map plus a `<details>`), but the only one that can make the UI *say something untrue*: these chips change which detectors run. Needs the honesty decision in §C3.1 made before code, and the brief's "YOLO/SAM selectors" premise corrected first — they are read-only status pills. |

**Recommended order: B, then A, then C.** B is a warm-up that costs nothing and settles the
vocabulary A's menu copy ("Read with Aletheia") and C's chips will both live beside.

## What is NOT authorized

- **No broad redesign.** Not the presence ladder (`content.js:501-557`), not the tray/queue
  (`:815-1160`), not the Aletheia panel (`:636-800`), not the region pane layout.
- **No new frontend surface.** No new page, route entry in `frontend/src/main.jsx`, modal or panel.
  The `⋯` menu in A is a child of the existing toolbar element, not a new surface.
- **No route change.** `/detect-regions`, `/domain-profile`, `/domain-profile/propose`,
  `/vision/capabilities`, `/posts/brainstorm`, `/posts/upload-from-url` all stay exactly as they are.
- **No schema change.** No `domain_profile` field, no `region_annotations` field, no
  `vision_runs` field, no request/response key.
- **No telemetry constant change.** `OPERATION_DISSECT` and every `STAGE_*` in
  `backend/services/vision_orchestrator/vision_run_contracts.py:44-81` are frozen, as are the
  `'dissect.*'` keys in `frontend/src/differential/visionActivity.js:90-103`.
- **No backend edit of any kind** for any of A, B or C.
- **No deletion of `RegionDetectorModal.jsx`**, despite it being unreferenced. That is a separate
  decision with its own justification burden.

## What was deliberately NOT done in this lane

- **No source file was edited, created or deleted.** Every finding above is an observation of the
  tree as found.
- **Nothing was staged, committed or pushed.** No dev server was started; the two already running
  were left alone.
- **The frontend test suite was not run.** The `visionActivity.test.js` / `recall.test.js` /
  `grounds.test.js` risk in §B4 is flagged from a filename grep, not from a run.
- **Nothing was verified in a browser.** Every claim about what is on screen is derived from source,
  not from a rendered page. Button sizes are read from `content.css:63-83`, not measured.
- **`RegionDetectorModal.jsx` was read but treated as orphaned** on the strength of a repo-wide
  grep. If a dynamic import exists somewhere this lane did not look, that conclusion is wrong.
- **The Alexia / Aletheia naming split was reported, not resolved.** It is a brand decision.
- **No Mongo query was run**, so nothing here says how many posts actually carry a non-default
  `domain_profile`, or which profiles users pick in practice. That measurement would sharpen C and
  is not in this lane.
