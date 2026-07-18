# DIFF-UX-GATE-001 — evidence report + repair brief

**Date:** 2026-07-18. **Surface:** Differential workspace (rendered build, real pointer
gestures). **Trigger:** human evidence — "Select/Brush/other tools not meaningfully
usable; action visibility poor; **Brush gesture moves the image instead of painting**."

## Why automated verification missed this

The increment A–E checks used CDP synthetic mouse events (`Input.dispatchMouseEvent`)
and screenshots. Those do not initiate the browser's **native HTML5 image drag**, so the
brush appeared to paint. A real human press-drag on the `<img>` fires `dragstart`, and the
native drag hijacks the gesture. **Synthetic-event tests are insufficient for gesture
arbitration — only real drags expose it.** (Gate item 10.)

## Failures (reproduced in the rendered build)

**F1 — Brush/Trace native-drag hijack. Severity: critical.**
- Repro: Differential → Brush → press-drag on the image.
- Evidence: `img.draggable === true`; a `dragstart` listener fires **true** during the
  brush stroke. No `preventDefault` on pointerdown; `user-drag`/`user-select` computed
  `auto`.
- Expected: the drag paints a Soft Field. Actual: the browser starts a native image drag
  (ghost image follows the cursor); the pointer-move stream is suppressed.
- Boundary: the stage `<img>` + stage pointer handlers own this. Gate items 1, 2, 10.

**F2 — Drawn marks below the perceptual floor. Severity: critical.**
- Repro: brush a stroke; inspector reads "1 stroke" but nothing is visible on the image.
- Cause: partly F1 (only 1–2 points register, so a single soft stamp paints), partly the
  wash falls to zero-alpha at the stamp edge and reads as nothing on a dark image.
- Expected: a visible wash where you painted. Actual: no perceptible mark. Gate items 1, 5.

**F3 — All drawing tools ride the same stage → same hijack.** Trace (Path/Boundary) drags
the image too. Severity: high. Gate items 1, 2.

**Not-failed (checked):** Select completes — clicking a region gathers it with a visible
dashed selection box + inspector row. Its outlines are faint (quiet map) but the action
and its feedback work. Persistence/state tests remain green.

## Root causes

- **A — native browser gestures hijack the stage.** No `draggable=false`, no `dragstart`
  prevention, no `preventDefault` on drawing pointerdown, no `user-select/user-drag` guard.
- **B — feedback below the perceptual floor.** Once A is fixed the full stroke registers,
  but the wash still needs to read on a real (dark) image; the brush cursor and region
  targetability also want a nudge.

## Single repair brief

1. `<img draggable={false}>`; `onDragStart={preventDefault}` on the stage; CSS
   `user-select:none` + `-webkit-user-drag:none` on stage/img.
2. `preventDefault()` on pointerdown for drawing tools (keep pointer capture through the
   whole stroke).
3. Raise Soft-Field legibility: stronger draft wash + a defined stamp so a stroke reads on
   dark pixels; keep ≤ the 0.35 wash ceiling for committed grounds.
4. Re-verify with **real drags** (not synthetic): brush paints, trace draws, image never
   moves; then the full gate checklist.
