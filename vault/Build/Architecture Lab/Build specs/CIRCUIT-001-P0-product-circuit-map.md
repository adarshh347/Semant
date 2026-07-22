# CIRCUIT-001 P0 — The product circuit, as it actually is

**READ-ONLY AUDIT. No source file was edited, no production document was read or written by the
synthesis, no route/schema/collection/entity is proposed here, nothing was staged or pushed.**
Three read-only lanes (backend, Differential, writing surfaces) produced the evidence; this document
synthesises it. Every claim carries a `file:line` read in the working tree on 2026-07-22.

`OBSERVED` = read at the cited line · `INFERRED` = a reading · `BUG` = the code does not do what its
own surface claims · `DESIGN` = it does what it intends and the intent is arguable.

> **The framing, in the user's words:** *"We should not build Atlas/Codex as giant nouns. That's how
> systems become theatrical. We should build the Chiasmatic Circuit: the real relations between
> image evidence, percepts, writing, runs, and future comparative/temporal surfaces."*

**The core question:** what must Semant remember, show, and protect so seeing can move through image
evidence → percepts → writing → model runs → future surfaces **without losing truth**?

---

## 0. The answer in one page

The circuit **exists** and its hardest part is **already correct**: grounds and percepts are
deliberately stored outside `region_annotations` so a re-dissect cannot wipe them
(`frontend/src/differential/grounds.js:5-7`, `backend/schemas/post.py:121-123`), and `resolveGround`
degrades rather than throws (`grounds.js:68-85`, pinned by `grounds.test.js:74`). **That is the right
shape and it should be recorded as such before anything else.**

What is broken is not the model of evidence. It is that **the system computes the truth about its own
evidence and then declines to show it.**

The single sharpest fact in the audit: the honesty string
`"Detached evidence — none of the N cited grounds still resolves."` is computed at
`recall.js:164-168` on the shared code path, and has **exactly one render site in the entire
frontend** — `DifferentialWorkspace.jsx:547-549`. The writing surface, which runs the same player
via `RegionSurface.jsx:121`, renders `recallPlayer.caption` at `:330-332` **and drops
`evidenceNote` on the floor**. The percept's expression floats over an emptied image with the
disclaimer written, computed, and discarded.

Three structural facts frame everything downstream:

1. **The Mention is not durable.** It is regex-reconstructed from block HTML on every load
   (`regionStore.js:112` → `perceptMentions.js:154-170`) and the reconstruction loses the percept id,
   the mention id, the form and the relation type. The only durable trace of a citation is the HTML
   attributes on the chip itself. This confirms R0 and is the binding constraint on any future
   cross-image or cross-time surface.
2. **No entity carries a `run_id`.** Not a Region, Ground, Percept, assertion or embedding, anywhere
   in the codebase. `vision_runs` records the *attempt* and never the ids it produced
   (`STAGE_PERSIST` logs `{region_count, matched_count}` only). **9 of the 10 model-invoking routes
   that mutate `posts` write silently.**
3. **The writing leg has no data in it.** Corpus: 421 posts, 57 regions, 26 grounds, 7 percepts,
   2 semantics docs, 2 `vision_runs`, 98 embeddings — and **0 text blocks anywhere**. Every claim
   about the writing surfaces is a claim about code, not about a corpus that exists yet.

---

## 1. The real entities, and their durability class

`OBSERVED` throughout.

| entity | where it lives | class | note |
|---|---|---|---|
| **Region** | `posts.region_annotations`, embedded array · `backend/schemas/post.py:30-73` | **durable** | `box`/`polygons`/`polygon` are **derived** from `mask_rle` |
| **Ground** | `posts.grounds: List[dict]` · `post.py:123` — **no backend schema at all** | **durable but untyped** | `detached` is **recomputed** client-side (`grounds.js:72`); a *different* durable `detached` flag exists in Mongo on 4 grounds that **nothing reads** (HW-C6 finding) |
| **Percept (expression, `pctx_`)** | `posts.percepts: List[dict]` · `post.py:124`, no schema | **durable, untyped** | the only durable object in the relationship model |
| **Percept (attention, `pct_`)** | nowhere | **derived** | rebuilt at load per region with `block_id \|\| user_note \|\| prioritised` (`regionStore.js:113-117`) |
| **Mention** | nowhere | **reconstructed** | regex over block HTML (`perceptMentions.js:154-172`); the `mentions` field exists on 0 posts |
| **TextBlock** | `posts.text_blocks` | **durable** | `content` is an opaque HTML string (`post.py:75-83`); `origin` defaults/guesses `"human"` |
| **Semantics** | `posts.semantics`, untyped dict on write | **durable** | the best-provenanced thing in the system |
| **VisionRun / stage events** | `vision_runs` collection | **durable** | the only first-class documents besides `region_embeddings` |

**Two definitions of "percept" are live in one frontend.** The store's rule is above; Home
reimplements the question and answers it differently — `homeData.js:43-45` returns
`post.region_annotations` verbatim. `homeData.js` never reads `post.percepts` or `post.grounds`.

---

## 2. Durable vs reconstructed vs inferred — the spine

| the thing | stored? | recomputed? | guessed? |
|---|---|---|---|
| a region's geometry | ✅ `mask_rle` | box/polygon derived | — |
| a region's **meaning** (`label`, `category`, `material`, `description`, `part`) | ✅ | — | **destroyed by refine-in-place** — §3.1 |
| a ground's detachment | ⚠️ stored on 4 grounds, **read by nothing** | ✅ the real answer, client-side | — |
| a percept's attention status | — | ✅ every load | — |
| a citation (Mention) | ❌ | ✅ lossily, every load | form/relation/actor **guessed** as `inline`/`cites`/`human` |
| a block's authorship | ✅ `origin` | — | defaults to `"human"`; **4 of 6 write paths omit it**, so model prose reads back as human |
| which model produced a region | ❌ **nowhere** | — | — |
| which run produced anything | ❌ **nowhere** | — | — |

**The pattern worth naming:** the system is good at storing *geometry* and poor at storing
*provenance and relation*. Everything about **where a thing came from** and **what it is attached
to** is either reconstructed or absent.

---

## 3. Where evidence identity can break

Prior findings are **cited, not re-derived**: `HW-C5-positional-id-reattachment-probe.md`,
`HW-C7-actor-carry-audit.md`, `HW-C8-auto-ordinal-curator-region-probe.md`,
`HW-C9-announcement-only-merge-fix.md`.

### 3.1 Refine-in-place destroys meaning while preserving identity `BUG` — **new, not covered by any prior finding**

`posts.py:1233-1243` + `adapters.py:190-204`: a refine keeps the region **id** and discards
`label`, `category`, `material`, `description`, `part`, `attributes`, `embedding_id`, `block_id`.
**Corroborated in the corpus: all 6 creator regions have `label: null`.**

*(Fable-pass.)* This is the inverse of the hazard the program has been tracking for five cycles. HW-C5
found **the id can come to mean something else**; this is **the id staying put while the meaning is
deleted**. A prose chip pointing at that region still renders — with its frozen `data-label`
(`regionRefInline.jsx:85`) — and the label is now the *only* surviving record of what the region was.
**The manuscript becomes the last witness to its own evidence.**

### 3.2 The auto→auto merge re-points an ordinal onto a new mask

`posts.py:809-819, 832`. Counted in `kept_auto` as an ordinary survivor. HW-C9 §2 named this and
declined to act; it covers the **51-region** auto population, versus the 2 curator regions HW-C8
enumerated. **The larger exposure is the one nobody has instrumented.**

### 3.3 The live-but-wrong reference is more dangerous than the dead one

`INFERRED`, and it is the load-bearing statement of the writing lane. A `/part` chip points at
`region_N`, a per-run positional ordinal (`vision_service.py:513`). A dead reference at least draws
nothing. **A re-dissect that happens to produce the same number of regions gives every `/part` chip in
the manuscript a resolving id, a stale label, and a confident highlight of the wrong part — with no
signal anywhere.** There is no version, no `geometry_rev`, no run id and no checksum on any prose
reference.

**The asymmetry, stated plainly: a reference that goes through a Percept degrades; a reference that
goes straight to a region lies.**

### 3.4 The embedding witness can be overwritten

`region_embedding_service.py:58-69, 187-191`: embedding ids embed region ids and **upsert**, so an id
collision overwrites the `mask_hash` witness HW-C8 §4 relied on. 2 of 4 call sites
(`posts.py:975, 1125`) pass no `geometry_rev`/`mask_hash`, leaving **15/98 rows permanently
un-stale-able**; 9 rows are orphaned.

### 3.5 Grounds and Percepts have no schema and one unvalidated writer

`schemas/post.py:123-124` + `posts.py:1609-1623`: a whole-array `$set`. **No `region_id` existence
check, no id uniqueness, no server timestamp.** No optimistic concurrency exists anywhere in the
system: every region write is find→mutate→`$set` whole array, once across a response boundary.

### 3.6 Deletion orphans silently

`DELETE /posts/{id}` (`posts.py:1631-1642`) leaves `region_embeddings` and `vision_runs` behind. **No
cascade.**

---

## 4. Where external claims enter

This is spark-08 / spark-10 territory (`HW-C10-abstraction-as-immunisation.md`).

- **The global semantic reading has no id**, so `enforce_candidate_ids` cannot reach it
  (`semantic_pass.py:104`, `vision_semantic.py:97-114`). **Live instance:** post `6a5b91fb…9a4` has
  `dropped_ids: ["1","2","1","2"]` and **0 assertions**, yet stores a full, confident image-level
  reading. **HW-C10's hazard with production data behind it.**
- **4 of 6 text-block write paths omit `origin`**, so model prose reads back as human.
- **`origin` is rendered as an invisible attribute.** `PostDetailPage.jsx:1194-1206` stamps
  `data-origin`, and `grep -rn "data-origin" frontend/src --include=*.css` returns **zero**. A block
  written by the model reads, on the page, as the curator's own sentence. **One CSS rule from being
  fixed.**
- Region labels and descriptions carry **no model id, no prompt version, no timestamp**.
- Two prompt/telemetry inconsistencies worth recording: `evidence_packet.py:120` tells the VLM it has
  *"the whole image and a CONTACT SHEET"* while `adapters.py:431` sends only the contact sheet; and
  `cache.py:53` claims a geometry revision invalidates the semantic cache while
  `semantic_pass.py:37-39` hashes only `[candidate_id, auto_label]`.

---

## 5. Where model runs are visible and invisible

| | |
|---|---|
| **instrumented operations** | 4 — dissect, refine-confirm, semantic-read, find-similar |
| **model-invoking routes that mutate `posts` silently** | **9 of 10** — incl. `enrich-regions`, `_embed_marked_regions`, `_resolve_is_fashion`, `aletheia-read`, `domain-profile/propose`, every story/phrase generator |
| **`run_id` on any produced entity** | **none, anywhere** |
| **`actual_source` recorded** | only by `dissect` (`posts.py:868-869`); refine/semantic_read/find_similar call `rec.finish()` without it (`:1262, :1421, :1542`) |
| **per-stage `adapter`** (`sam2`, `yolo11_seg`, `segformer_*`, `semantic_pass`) | recorded, derived into `stages[].adapter` (`visionActivity.js:247`) — and **never rendered** (`VisionActivityRail.jsx:79-87`) |
| **`events[].dependencies`** | always `[]` |

**A user cannot tell which model produced three of the four recorded operations**, and cannot tell
anything at all about the nine silent ones.

---

## 6. Where the UI lies, hides, or overstates

Quoted strings, all `OBSERVED`. This is the gate's own phrasing and it is meant literally.

### Differential

| # | file:line | what it does |
|---|---|---|
| D1 | `DifferentialWorkspace.jsx:428-429` | a **failed percept save can render "saved ✓"** — two independent write paths ORed; `regionStore.js:185-188` writes an error into state **nothing renders** |
| D2 | `:731, :732, :734, :747` | a **detached ground is presented as live evidence and offered for reuse** — *"region · evidence"*, chipped `"creator"`, with **"Compose a percept"**. `detachedGrounds` is computed at `:438` and never consulted here |
| D3 | `:815` | asserts a cause the code cannot know — *"its part was replaced by a re-dissect"*. `resolveGround` (`grounds.js:71-72`) only knows the `region_id` is missing. The project's own causal-language guard (`visionActivity.js:164-171`) covers only the Rail |
| D4 | `:169-174` + `grounds.js:44-46` | **a model's word stamped as the curator's** — the detector's label is copied onto a ground stamped `actor:'creator'`, then displayed as "creator" |
| D5 | `:59, :737, :823, :583` | counts that cannot match what is drawn; absent refine confidence renders **"proposed · 0%"** |

### Writing surfaces

| # | file:line | what it does |
|---|---|---|
| W1 | `homeData.js:43-45` → `PerceptsTile.jsx:36,57`, `WeekTile.jsx:23,28` | **Home calls raw detector output "percepts you noticed"**. *"Parts you recently noticed"*, *"N percepts · M words"*. **The tile named "Percepts" is the only surface that cannot display a percept.** `WeekTile` sums all regions on posts touched this week, so one re-dissect can add forty "percepts marked" |
| W2 | `RegionSurface.jsx:330-332` | **the recall caption asserts over emptied evidence** — `evidenceNote` computed and not rendered. **The highest-value finding in the audit: the fix is a conditional render of a value already in hand** |
| W3 | `regionRefInline.jsx:85`, `partRefBlock.jsx:24-35, 54-55` | chips render frozen labels with no resolution state; a missing region yields a **silent blank box** beside a confident *"◈ part"* |
| W4 | `RefPicker.jsx:48, 60-62` | **badges overstate** — cited counts, not resolving counts, while `grounds` is already a prop (`:26`) and the sub-line at `:43-47` silently drops the ids that don't resolve. A fully-detached percept shows an empty sub-line and a confident *"3 grounds"* |
| W5 | `PostDetailPage.jsx:1194-1206` | **AI prose is indistinguishable from curator prose** — see §4 |

**Recall click failures**, all `BUG`: a `/part` chip whose region is gone runs the full choreography —
panel expands, pane scrolls, chip lights — then **dims every region and lights none**
(`regionStore.js:272-277`, `RegionOverlay.jsx:32-33`), with no message. A percept chip whose percept
is absent from the store lights up asserting *"I am being replayed"* over a no-op
(`regionRefInline.jsx:65-67`). A `/lens` chip whose regions were replaced filters to `[]` and the
hint that would explain it is guarded by `regions.length > 0`, so it never appears
(`AletheiaHook.jsx:105-106, 160-165`).

### Profile controls

`ProfileControl.jsx:28-33` fetches `GET /vision/capabilities` and `.catch(() => {})`, then
`:68` `passState = (name) => caps[name]?.state || 'ready'`. **When capabilities is down, every pass
pill renders `ready`.** HW-C8 §C2 identified these pills as *the only place in the UI where an
unavailable model is surfaced at all* — **the only unavailability signal in the product fails open.**
`:64` likewise displays a hard-coded schedule as if recorded.

`P2`: `{reason}` at `:83` — the component's only honesty carrier — renders the raw classifier string
(*"auto: fashion 0.71, …"*). It says what was **guessed**, never what will not be **looked for**.
HW-C10 §3.2 named writing this sentence as increment C's single unmet precondition; **still
unwritten.**

---

## 7. Test coverage reality

**There is no DOM test environment at all** — no jsdom, no happy-dom, no testing-library, vitest
defaults to `node`, and there are **zero component tests** in `frontend/src`.

**Genuinely well covered** (and worth protecting): `blockConvert.test.js` round-trips every reference
attribute including `data-percept-id`, plus a negative control proving the custom spec is
load-bearing; `recall.test.js` pins the A2R contract in five tests; `grounds.test.js` pins
`resolveGround`'s three cases; `perceptMentions.test.js` pins idempotence and
`blockIdsForRegion`.

**Not covered:** every finding in §6 without exception. `evidenceNote`'s absence from the writing
surface is invisible to the suite **by construction**, because no test mounts a component. Mention
reconstruction fidelity is untested *rather than accepted* — no test asserts that `perceptId`,
`mentionId`, `form` or `relationType` survive a round-trip, **because they don't**.

---

## 8. What is already right, and must not be broken

Recorded deliberately, because a P0 that only lists faults invites a rewrite.

1. **Grounds and percepts live outside `region_annotations` on purpose** (`grounds.js:5-7`,
   `post.py:121-123`) so a re-dissect cannot wipe them. This is the correct shape.
2. **`resolveGround` degrades rather than throws** and its three cases are pinned by tests.
3. **The A2R honesty fix is present and intact** — `recall.js:36, 43-46, 84-86, 114-118, 164-168`,
   five tests at `recall.test.js:71-125`. The failure is that it was wired into one surface.
4. **`blockConvert`'s round-trip is rigorous**, including a negative control.
5. **`semantics` is the best-provenanced object in the system** and shows the shape provenance should
   take elsewhere.
6. **`RefPicker`'s ordering docstring** (`:17-21`) — *"the list a person scans should be sorted by
   what they cared about, not by what a model emitted"* — states the product's own principle
   correctly. The badge contradicts it; the principle is right.

---

## 9. The circuit, drawn

```
   image ──dissect──▶ Region ────▶ Ground ────▶ Percept ────▶ Mention ────▶ TextBlock
             │        durable      durable       durable      RECONSTRUCTED   durable
             │        (meaning     (untyped,     (untyped)    (lossy, every   (origin
             │         lost on      unvalidated)               page load)      unrendered)
             │         refine)          │             │              │
             │                          │             │              │
             ▼                          ▼             ▼              ▼
        vision_runs              resolveGround   playRecall     recall click
        (4 of 13 ops)            ✅ correct      ✅ correct     ❌ 4 silent failures
        no run_id on                    │             │
        anything produced               └──▶ evidenceNote ──▶ rendered in 1 of 2 surfaces
```

**Read left to right, the circuit loses provenance at every hop and only announces the loss once.**

---

## 10. What this document does NOT do

- **No entity, field, schema, route, collection, migration or UI is proposed here.** Proposals live
  in `CIRCUIT-001-P0-build-sequence.md`; unresolved forks live in
  `CIRCUIT-001-P0-open-decisions.md`.
- **No production data was repaired, and none should be** on the strength of this map.
- **No claim is made about corpus frequency for the writing leg** — there are 0 text blocks, so every
  writing-surface finding is a claim about code paths, not about observed damage.
- **Nothing was verified in a browser.** Every "what the user sees" claim is derived from JSX and CSS
  reading. Two dev servers were running and were left alone.
- **Prior findings were cited, not re-derived** (HW-C5, C7, C8, C9, C10, S1, S2).
