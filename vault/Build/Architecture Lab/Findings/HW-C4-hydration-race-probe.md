# HW-C4 · The hydration race, measured (B-01)

**MEASUREMENT ONLY — no code modified, no fix applied.**
No `.jsx`, `.js`, `.css` or `.py` file in `frontend/` or `backend/` was created or edited. Nothing
was staged, committed or pushed. No database was touched and no model was called. The only artifacts
of this lane are this document and three throwaway probe files written to the session scratchpad
(outside the repo), which were executed with the project's own `vitest` binary and are not part of
the test suite.

This is **B-01**, the first item in `HW-L5-prototype-rotation-backlog.md`'s queue: *"regionStore.js:94-119
loads regions and grounds in the same effect. If grounds land before regions, every region-ground
reports detached for a frame."* Two independent scouts (S1 against E1; L3 against X2, X3 and X5)
named this as a killer. It had never been measured. It has now.

---

## 1. Verdict

> ### VERDICT: **REJECTED** — for the specific race that was alleged.
>
> There is **no render pass in which `grounds` is populated while `regions` is still `[]`**. The
> asymmetry both scouts feared cannot occur, because both are set inside one synchronous effect body
> and React batches them into a single commit. Measured: **0 asymmetric passes** across mount,
> post-switch and `StrictMode` double-invocation.
>
> A **weaker, real** phenomenon does exist and should be named honestly rather than folded into the
> rejection: there is exactly **one commit in which the store is uniformly empty** (`regions: 0`,
> `grounds: 0`, `percepts: 0`) while `post` is already non-null and the Chiasm shell is already
> mounted. That is a *collapsed* frame, not a *stale* or *inconsistent* one. It cannot produce a
> false detachment, because with `grounds === []` there is nothing to resolve. Its only visible
> consequence is a possible one-frame "no polygons / no crop" flash on the Field pane. Call this
> **the empty frame**, and keep it distinct from the race, which does not exist.

The practical consequence for the queue: **B-01 is discharged. B-02, B-03b and B-06 are no longer
blocked by the hydration race.** B-06 retains a *separate* residual risk (§7, R-2) that this lane
could only partially address.

---

## 2. The exact code path, in execution order

Entry point is `/posts/:postId` → `PostDetailPage`.

| # | what happens | file:line |
|---|---|---|
| 1 | `const [post, setPost] = useState(null)` | `frontend/src/components/PostDetailPage.jsx:40` |
| 2 | `useRegionState(post, setPost)` is called **before** the `!post` early return, so hook order is stable and the store exists while `post` is null | `PostDetailPage.jsx:92` (comment at `:89-91`) |
| 3 | **Render 1.** `post === null` → the store returns all-empty state; `if (!post) return <Loading/>` short-circuits, so **no consumer mounts** | `PostDetailPage.jsx:875-882` |
| 4 | `useEffect(… , [postId])` fires `fetchPost()` — **one** `GET /api/v1/posts/{postId}` | `PostDetailPage.jsx:183-187`, `:160-170` |
| 5 | Response resolves → `setPost(response.data)`. The single response object carries **both** `region_annotations` and `grounds`; there is no second fetch for either | `PostDetailPage.jsx:163` |
| 6 | **Render 2 — the empty frame.** `post` is non-null, so the provider and every consumer mount, but `useRegionState`'s hydrate effect has not run yet: `regions === []`, `grounds === []`, `percepts === []` | `PostDetailPage.jsx:884-886` |
| 7 | Passive effect runs. `loadedFor.current !== post.id`, so it proceeds and performs **eleven state writes in one synchronous body** | `state/regionStore.js:94-119` |
| 7a | `setRegions(loadedRegions)` — this also assigns `regionsRef.current` **synchronously**, before any re-render | `regionStore.js:98` → `:77-80` |
| 7b | `setGrounds(hydrateGrounds(post.grounds))` — likewise assigns `groundsRef.current` synchronously | `regionStore.js:99` → `:82-85` |
| 7c | `setAletheia`, `setSelectedId(null)`, `setHoveredId(null)`, `setSelectedGroundId(null)`, `setHoveredGroundId(null)`, `setLensRegionIds(null)`, **`setRecall(null)`** | `regionStore.js:100-106` |
| 7d | `setMentions(mentionsFromBlocks(post.text_blocks))`, `setPercepts([...])` | `regionStore.js:112-118` |
| 8 | React 19 auto-batches 7a–7d into **one** re-render | `frontend/package.json:37-38` (`react@^19.1.1`) |
| 9 | **Render 3 — fully hydrated.** `regions`, `grounds`, `percepts`, `mentions` all populated in the same commit | — |
| 10 | A follow-up effect syncs `perceptsRef.current = percepts` **after** commit 9 | `regionStore.js:88` |

Consumers read from this one object:

- `DifferentialWorkspace.jsx:86-93` destructures `regions` **and** `grounds` from the same `store`.
- `DifferentialWorkspace.jsx:438` — `detachedGrounds = grounds.filter(g => resolveGround(g, { regions, grounds })?.detached)` → rendered as the "Detached evidence" inspector block at `:810-819`.
- `recall.js:100` destructures `grounds` and `regions` from the same `store`; `:112-121` builds the script with `isResolved: g => !resolveGround(g, { regions, grounds })?.detached`.
- `RegionSurface.jsx:97` — `const regions = store ? store.regions : regionsInt`; `:322-323` passes `grounds={store.grounds}` and `regions={regions}` to `GroundLayers` — **both from the store**, never one from the store and one from `post`.
- `PostDetailPage.jsx:942-946` gives `RefPicker` `regions` and `grounds` from the same store object.
- `GroundLayers.jsx:249` resolves against the `regions`/`grounds` props it was handed together.

**The structural reason the race cannot happen:** `regions` and `grounds` have exactly one writer
each (`setRegions` / `setGrounds`), both are written in the same effect body at `regionStore.js:98-99`,
there is no independent async source for either, and every consumer takes both from the same
`useMemo` value (`regionStore.js:333-367`). There is no second fetch, no `Suspense` boundary, no
lazy import and no separate grounds endpoint anywhere in the path.

---

## 3. How it was measured

Three probes were written to the scratchpad (not the repo) and run with the project's own
`node_modules/.bin/vitest`, against a scratchpad-local `vitest.config.js` aliasing `@src` to
`frontend/src`. `jsdom` was already present in `node_modules`; `react-dom/client` + React 19's
`act` were used directly, since the repo has no `@testing-library` dependency and none was added.

Each probe renders a harness that calls the **real** `useRegionState` and logs, on *every* render
pass, `(regions.length, grounds.length, percepts.length, detachedCount, regionById-hit,
groundById-hit)` — where `detachedCount` is computed with the **real** `resolveGround`, exactly as
`DifferentialWorkspace.jsx:438` does.

**Probe 1 — mount (post arrives).** Fixture: 2 regions, 2 region-adapter grounds citing them,
1 expression percept citing both grounds.

```
PASSES (null post):   [{regions:0, grounds:0, percepts:0, detached:0, refRegionHit:false, refGroundHit:false}]
PASSES (post arrives):[{regions:0, grounds:0, percepts:0, detached:0, refRegionHit:false, refGroundHit:false},
                       {regions:2, grounds:2, percepts:1, detached:0, refRegionHit:true,  refGroundHit:true }]
ASYMMETRIC PASSES (grounds>0, regions==0): 0
FALSE-DETACH PASSES: []
```

**Probe 2 — post switch (navigation between two annotated posts).**

```
POST-SWITCH PASSES: [{regions:2, grounds:2, detached:0},   ← still post A, both stale together
                     {regions:1, grounds:1, detached:0}]   ← post B, both fresh together
POST-SWITCH FALSE-DETACH: []
```

The intermediate pass holds post A's regions **and** post A's grounds. Stale, but internally
consistent — the failure mode is "you briefly see the previous post", not "you see this post's
evidence marked broken".

**Probe 3 — recall started at the earliest possible instant.** A harness that calls `playRecall`
in a microtask the moment `percepts` becomes non-empty, while logging `player.active`,
`player.unresolvedCount` and `player.evidenceNote` per pass.

```
RECALL PASSES: [{regions:0,grounds:0,active:false,unresolved:0,note:""},
                {regions:0,grounds:0,active:false,unresolved:0,note:""},
                {regions:2,grounds:2,active:false,unresolved:0,note:""}]
RECALL FALSE-UNRESOLVED: []
```

**Probe 4 — `StrictMode` + a deep context consumer.** The app runs under `<React.StrictMode>`
(`frontend/src/main.jsx:99-100`), which double-invokes effects in dev. The provider/consumer shape
of `PostDetailPage` was reproduced (provider at the page, consumer reading via
`useContext(RegionStoreContext)` and the ref-backed `regionById`, i.e. the `partRefBlock.jsx:39-40`
pattern):

```
STRICT PASSES: [{regions:0,grounds:0,refHit:false,detached:0},
                {regions:0,grounds:0,refHit:false,detached:0},
                {regions:1,grounds:1,refHit:true, detached:0},
                {regions:1,grounds:1,refHit:true, detached:0}]
ASYMMETRIC: 0   FALSE DETACH: 0   REF-MISS WHILE REGIONS PRESENT: 0
```

The double-invoked hydrate effect is idempotent because `loadedFor` is a ref that survives
StrictMode's remount (`regionStore.js:75, 95-96`), so the second invocation returns early. The
`refHit` column is the important one: `regionsRef.current` is **never** behind `regions` in a
committed render, because `setRegions` writes the ref before it schedules the state update
(`regionStore.js:78-79`).

---

## 4. Surface-by-surface

| surface | affected by the race? | affected by the empty frame? | how it would manifest |
|---|---|---|---|
| **Home** (`/home`) | **No** | **No** | `homeData.js:44-46` reads `post.region_annotations` off the posts-list response and never touches `regionStore`, `grounds` or `resolveGround`. `PerceptsTile.jsx` has an explicit `isLoading` branch. There is no evidence resolution on Home at all, so there is nothing to be transiently wrong about. |
| **Chiasm / PostDetail** | **No** | **Yes, mildly** | Render 2 mounts the Field pane with `regions === []`. `RegionSurface.jsx:97` yields an empty `visible`, so `RegionOverlay` draws no polygons and the parts list is empty for that commit. Any `/part` evidence block renders its `--empty` crop (`partRefBlock.jsx:25-27`). Next commit fills them in. Manifests as, at worst, a one-frame flash of "an image with no marks". Notably `viewMap`'s initial value is derived from `post.region_annotations` directly (`RegionSurface.jsx:67-68`), so quiet/outline mode is correct even in the empty frame. |
| **Differential** | **No** | **No** | `DifferentialWorkspace` is mounted only when `workspaceMode === 'differential'` (`PostDetailPage.jsx:888-894`), which requires a user action — the store is long since hydrated. Even if it were mounted at render 2, `grounds === []` makes `detachedGrounds` (`:438`) empty and the "Detached evidence" block (`:810`) is gated on `.length > 0`. |
| **RefPicker** | **No** | **Effectively no** | It is rendered only when `refPicker.open` (`PostDetailPage.jsx:938`), i.e. after a `/part` keystroke. It receives `regions` and `grounds` from the same store object (`:942-946`), so B-03b's proposed "does this ground resolve?" badge would read a consistent pair. B-03b is **unblocked** by this finding. |
| **Recall** (`recall.js`) | **No** | **No** | `recall` is explicitly reset to `null` in the hydrate effect (`regionStore.js:105`), and `playRecall` needs a `perceptId` that only exists once `percepts` is populated — which happens in the *same batch* as `regions`. There is no ordering in which recall is active while `regions` is empty. See §5. |
| **Aletheia** (`AletheiaHook.jsx`) | **No** | **No** | It owns its own fetch and reads `post.region_annotations` directly (`:106`) behind an `if (!post)` guard (`:101`). It never calls `resolveGround` and never reads `grounds`. Its known weakness (the hollow lens, B-13/DATA-5) is about *real* detachment, not a transient. |

---

## 5. Can the A2R "Detached evidence" note show a transient FALSE POSITIVE?

**No.** This is the highest-stakes question in the lane and the answer is a clean negative, for four
independent reasons — any one of which alone would be sufficient.

1. **Ordering.** The note is produced by `useRecallPlayer` (`recall.js:164-168`), whose `isResolved`
   closure (`:115-117`) reads `regions` and `grounds` from the same store object destructured at
   `:100`. Those two values are only ever written together (`regionStore.js:98-99`). There is no
   commit in which one is populated and the other is not — measured, 0 occurrences.
2. **Reachability.** `recall` is set to `null` on every hydrate (`regionStore.js:105`). The only
   writer is `playRecall` (`:242-245`), reachable only from a user gesture — the ▶ button in
   Differential, or a percept-chip focus event (`PostDetailPage.jsx:117-124`). Both require
   `percepts` to be populated, which happens in the same batch as `regions`. Probe 3 forced recall
   at the earliest microtask after percepts appeared and produced zero unresolved counts.
3. **Latency gate.** `evidenceNote` is additionally gated on `captionVisible`
   (`recall.js:148, 164`), which requires `elapsed >= expressionStep.at` — at minimum
   `RECALL_TIMING.recede` = **380 ms** after the script was built. A one-commit transient is roughly
   three orders of magnitude too short to survive that gate.
4. **Self-healing memo.** The `script` memo depends on `[percept, groundById, regions, grounds]`
   (`recall.js:120`). If `regions` changed mid-recall, the script would be **rebuilt** and the
   animation restarted from `elapsed = 0` (`:123-135`), which re-runs the 380 ms gate. A note built
   over stale regions could not persist even hypothetically.

The same reasoning covers the *other* "Detached evidence" surface — the Differential inspector list
at `DifferentialWorkspace.jsx:810-819` — which is a pure per-render derivation from a consistent
`(regions, grounds)` pair and is gated on `.length > 0`.

**Corollary for B-02.** The proposed silent-at-zero evidence pill in `PostDetailPage.jsx:1041`
would derive from the same consistent pair. It **cannot** flash an alarm on a healthy post during
load. L3's stated kill condition for X2 — *"if the ordering cannot be guaranteed, kill it"* — is
satisfied: the ordering **is** guaranteed, by construction and by measurement. L3 §3's premise
("if grounds land before regions") is false.

---

## 6. What a fix would be, if one were wanted (NOT APPROVED, and probably unnecessary)

Stated in prose only, as required. **Nothing here is approved and I recommend none of it be built
on the strength of this document alone.**

The only thing worth considering is the *empty frame*, and the minimal treatment is not a store
change at all — it is to let the shell wait one beat: hold the region-bearing panes behind the same
condition that already guards the page, so they mount with data rather than mounting empty and
filling in. That is a rendering-gate decision on `PostDetailPage`, one condition, and it is
reversible by deleting it.

Two alternatives should be explicitly *declined*:

- **Do not** move hydration into `useState` initialisers or a `useSyncExternalStore` derivation to
  eliminate the empty frame. It would remove one frame of flash at the cost of restructuring the
  single most load-bearing piece of client state in the app, and the flash is not a correctness
  problem.
- **Do not** add a `hydrated` / `loading` flag to the store so consumers can suppress detachment
  marks. It looks prudent and is actively harmful: it would introduce a *second* thing that can be
  out of step with `regions`, and it would give future marks a plausible-looking excuse to be
  suppressed when the detachment is real. The current design — one writer, one batch, one memo — is
  the reason the race does not exist, and a flag would weaken exactly that property.

---

## 7. What I could not determine, and what would settle it

**R-1 — is the empty frame actually painted?** Whether React 19 flushes the passive hydrate effect
before or after the browser paints render 2 depends on scheduler priority, and `setPost` originates
in a promise continuation (non-discrete), so a paint between commits 2 and 3 is plausible but not
provable in `jsdom`. A `jsdom` probe measures *commit* order, not *paint* order.
*What would settle it:* one browser session on an annotated post with the network throttled, watching
the Field pane on first load — or a temporary `performance.mark` around the effect. Per
`MEMORY.md`, `server-exit-144` currently blocks rendered verification, which is why this stayed
open. **Stakes: low.** A missing polygon for one frame is a cosmetic flash, not a false claim.

**R-2 — L3's *second*, distinct BlockNote concern (relevant to B-06 only).** L3 §4 argued that
even without the hydration race, "BlockNote re-renders inline content on its own schedule, so a
transient dim could be *sticky*". This lane found strong but not conclusive evidence against it:
`regionRefInline.jsx:63` and `partRefBlock.jsx:39` both read the store through
`useContext(RegionStoreContext)`, which subscribes them to every store change (the context value is
a `useMemo` whose deps include `regions` and `grounds`, `regionStore.js:355-367`). A subscribed
consumer cannot be sticky. What I could not verify in `jsdom` is whether BlockNote's node views
actually render inside the same React tree as the provider in this version — if they were rendered
into a detached root, context would be `null` and the chips' hover-focus highlight would never work
at all. Since that highlight is described as working, the tree is almost certainly shared; but
"almost certainly" is not "observed".
*What would settle it:* one browser session hovering a `/part` chip and confirming the highlight,
plus a re-dissect performed with the editor open, watching whether chip state updates without a
remount. **This does not block B-02 or B-03b. It is the only residual for B-06.**

**R-3 — out-of-order post fetches (found incidentally; out of scope, not a hydration issue).**
`fetchPost` (`PostDetailPage.jsx:160-170`) has no abort controller and no sequence guard, and the
effect that calls it keys on `postId` (`:183-187`). On rapid A→B→A navigation, a late-arriving
response can call `setPost` with the wrong post while the URL shows another. The store then
re-hydrates *consistently* to whatever post it is handed (`loadedFor` at `regionStore.js:95`), so
this cannot produce a false detachment — the page would simply show the wrong post entirely. It is a
real defect and a different lane's problem. **Recorded, not fixed, not measured further.**

**R-4 — `perceptsRef` lags by one commit (noted, benign).** `perceptsRef.current` is synced in a
separate effect (`regionStore.js:88`) rather than synchronously like `regionsRef`/`groundsRef`. So
during render 3 the ref is one commit behind the `percepts` state. Its only readers are
`perceptsForGround` (`:226-228`) and `persistMeta` (`:177`), both invoked from event handlers or an
800 ms debounce, so the lag is never observed. This is an asymmetry in the store's own conventions,
not a bug. Worth a comment if anyone touches that file for another reason.

---

## 8. Effect on the L5 queue

- **B-01 — done.** Verdict REJECTED for the alleged race; the empty frame documented instead.
- **B-02** (Chiasm evidence pill) — hydration-race dependency **discharged**. Its remaining
  dependency, B-02a, is untouched by this lane.
- **B-03b** (RefPicker resolves before it offers) — hydration-race dependency **discharged**.
  `RefPicker` already receives `grounds` from the store at `PostDetailPage.jsx:946`; adding
  `regions` from the same object would be consistent by construction.
- **B-06** (derived-only chip dimming) — hydration-race dependency **discharged**, but its *other*
  stated killer (BlockNote render scheduling, R-2 above) is only partially answered and remains the
  reason B-06 sits last.
- L3 §3's and §4's "killed by: the hydration race" clauses, and S1's identical clause against E1,
  should be treated as **retired**. Three "killed by" clauses converted into one fact, which is
  exactly what the queue put this item first to buy.

---

## 9. One line

The single most-named killer in this cycle does not exist: regions and grounds are written in one
batch by one writer and read as one pair by every consumer, so the "Detached evidence" note cannot
lie during load — what actually happens is one empty commit before the data lands, which is a
cosmetic flash and not a false accusation.

---

*Measurement ends. No code was modified, no fix was applied, nothing was staged or committed. The
probes live in the session scratchpad and are not part of the repository or its test suite.*
