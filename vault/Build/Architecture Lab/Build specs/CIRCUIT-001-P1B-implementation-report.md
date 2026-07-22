# CIRCUIT-001 P1B — Implementation report

**Completes the Differential → Manuscript crossing that P1A began.** Frontend only. **No production
data changed** — verified by API after the browser run (§6).

Follows `CIRCUIT-001-P1A-implementation-report.md`, whose §6.1 and §6.2 named exactly the two gaps
this gate closes.

---

## 1. The bug, as observed

> *"Clicking `Write from this` moves toward Manuscript, but does not reliably open/focus the editor.
> When Manuscript is opened manually afterward, the percept is not attached. The percept is created,
> but the UX feels broken."*

Reproduced and confirmed. The percept was **silently dropped**.

## 2. Root cause — three compounding faults

P1A's handoff was a **call** made in the same tick as a state change:

```js
setWorkspaceMode('chiasm');
insertRef(percept, 'percept');
```

1. **`<Manuscript>` mounts only while `isEditing`** (`PostDetailPage.jsx:1168`). Arriving from
   Differential the curator is normally **not** editing, so `manuscriptRef.current` is `null`.
2. **`insertRef` does `if (!handle) return`** — a **silent no-op**. No error, no queue, no trace. The
   percept was created and then discarded.
3. **React state updates are not synchronous.** Even with editing already on, `setWorkspaceMode` had
   not re-rendered when `insertRef` ran, so the handle could still be missing.

A fourth, smaller fault: `insertRef` read `refBlockIdRef.current`, which is written **only** by the
slash-command flow (`onRefTrigger`), so a crossing that never typed `/` would have landed against a
stale block id from a previous insertion.

**The crossing had to become a REQUEST that survives until the editor exists, not a call.**

## 3. The fix

**New pure module `state/manuscriptHandoff.js`** — the queue as testable state:
`requestHandoff` · `canFlush` · `completeHandoff` · `wasDelivered` · `handoffStatus`.

**`sendPerceptToManuscript`** (`PostDetailPage.jsx`) now: leaves Differential → puts the story tab in
front → **starts editing if needed** (`seed: false`, so no blank paragraph sits above the chip) →
queues the percept → **plays the percept on the image**.

**A flush effect** runs after every render and inserts only when `canFlush` is satisfied — something
pending, editing on, handle present. It inserts through **the same `insertRef` path as `/percept`**
(so the chip cannot drift from the slash command), against `handle.currentBlockId()` rather than the
stale ref, then focuses.

**At-most-once delivery.** `completeHandoff` clears the request and records the id; `wasDelivered`
guards a remount replaying it. A double-click returns the *same state object*, so it cannot even
re-render.

## 4. Keeping the percept visible in the Field

`playRecall(percept.id)` fires on the crossing, so the noticing **performs itself on the image** while
the chip lands in the writing. The curator sees the percept's expression, its grounds light, and —
when evidence has gone — the detached note, all in the pane they are looking at.

A new status line, `.rs-recall-crossed`, reports **"in the writing · N passages"**.

**Derived from the mentions, never from a "sent" flag.** A flag would keep claiming the crossing after
the chip was deleted. This was visible during verification: cancelling the edit made the status
disappear on its own, which is the behaviour a flag could not have produced.

**One honest limit, found during verification and fixed:** a chip inserted into an **empty** document
has no block id to be inserted against (`currentBlockId()` is null before the first block exists), so
the mention records *that* the crossing happened but not *where*. `handoffStatus` now says the true
part — **"in the writing"** without a count — rather than saying nothing. Under-reporting a crossing
that really happened would have been the same class of silence this gate exists to remove.

## 5. Gate 5 — the dead `/part` reference

`focusRegions` set `selectedId` to a dead id **with no existence check**, so `RegionOverlay` dimmed
**every** region and lit none, after the panel had expanded and the pane had scrolled. Confident,
silent, pointing at nothing.

New pure export **`liveRegionIds(ids, regions)`**. A reference resolving **nowhere** is refused and
sets `missingRef`; RegionSurface then says *"That part is no longer in the image."* — **absence, never
cause**, since `focusRegions` knows only that the id does not resolve.

**A lens that has lost only *some* of its parts still shows the rest.** Withholding the whole citation
would hide evidence that is still true.

## 6. Verification

| | |
|---|---|
| **tests** | **144 passing, 11 files** (P1A left 126). **+18**: 12 handoff, 5 `liveRegionIds`, 1 status |
| **build** | `vite build` ✓ |
| **backend** | not run — **no backend file touched** |

**Browser, on `695be786a9ea58f1b6aef5ed`** (2 percepts, 2 detached grounds):

- ✅ `Write from this` is visible on hover — P1A's unconfirmed item, now confirmed.
- ✅ Clicking it left Differential, **opened Manuscript in edit mode**, and **inserted the chip
  automatically**: `✦ the upper head`.
- ✅ The percept **stayed visible on the image**, showing its expression *and*
  *"Detached evidence — none of the 2 cited grounds still resolves."*
- ✅ Cancelling removed the chip and the status line vanished with it.
- ⚠️ **The "in the writing" fallback was added after this run and is unit-tested, not re-verified in
  the browser.**

**Production mutation: NONE.** Block edits are local until an explicit Save/Ctrl+S — there is no block
autosave — and Cancel was used. Confirmed by API afterwards: `text_blocks: 0`, `percepts: 2`,
`grounds: 5`, `updated_at: 2026-07-19T00:46:31.869` — days before this session.

## 7. What remains for P1C

1. **Ground Roles** — *what each ground does for this percept* (anchor, counterforce). A property of
   this percept's **use** of a ground, which is why it cannot live on the Ground record. This is what
   makes a percept a *reading* rather than a list.
2. **Percept Packet builder** (Perceptive Orchestration) — assemble intent + grounds + evidence state
   + manuscript context, **inspectable before sending**. Build the packet before anything sends.
3. **Fuller Circulation Thread** — expandable rows; records and judgements in visibly different
   voices. Currently one derived line.
4. **The two remaining silent recall failures** — a percept absent from the store still lights its
   chip over a no-op; a `/lens` whose regions were replaced shows nothing with its hint suppressed.
5. **Atlas/Codex prep is NOT next.** It needs the durable-citation decision, still untaken.

**Still deliberately absent:** persisted Mentions, `suspect`, `run_id`, and any backend change.
