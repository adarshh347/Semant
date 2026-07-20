# R1 — Existing circulation probe (expression-Percept → Writer chip → recall)

**Declared probe level:** A (unsaved interaction — insert a chip into local editor state, trigger
recall, capture rendered evidence, discard without persistence). Level B (persistence on an
isolated fixture) was not attempted.

**Result: NOT rendered-verified — hard infrastructure blocker. Reported honestly, not fabricated.**

## The blocker (B1, now worse than at R0)

Every long-lived server process launched in this session dies immediately with **exit 144** and no
output:
- `python -m uvicorn` — dies.
- programmatic `uvicorn.run` via `scripts/_run_backend.py` — **now dies too** (it briefly worked
  ~an hour earlier this session; the environment then killed even the process that *was* serving on
  `:8000`).
- `npm run dev` and direct `node vite` on `:5199` — die.
- Only rhizomedb's `:5173`, launched by a persistent external process outside this session, stays up.

Short-lived processes (Python scripts, pytest, vitest) run fine. The conclusion: the post-reboot
environment terminates long-lived, port-binding servers this session. A rendered browser probe of
the React UI is therefore **impossible right now**, through no fault of the app (imports clean,
startup indexes build in ~1 s, in-process ASGI requests succeed).

Per the failure-and-safety doctrine ("server unable to remain alive for browser verification →
degraded or stopped runs, not fabricated success") this probe is **stopped**, not passed. No earlier
screenshot is substituted for current rendered verification.

## What WAS verified (logic only — NOT a substitute for rendered proof)

The chip→recall data path's **pure logic** is exercised by the existing frontend unit suite
(short-lived vitest, ran clean — **56 tests passed**):

| suite | proves |
|-------|--------|
| `differential/recall.test.js` (6) | `buildRecallScript` emits the staged timeline (recede → primary ground → supporting → expression); constellation/relation expansion; reduced-motion jump-to-final |
| `state/perceptMentions.test.js` (17) | Percept/Mention helpers; deterministic ids; `mentionsFromBlocks` reconstructs mentions from block markup (the Mention's only durable form) |
| `components/blocknote/blockConvert.test.js` (18) | **lossless** `text_blocks ⇄ BlockNote` incl. every `data-*` chip attr (`data-percept-id`, `data-region-ids`, `data-mention-id`) survives import→export |
| `differential/grounds.test.js` (15) | Ground make/resolve/bbox for the evidence a percept cites |

This confirms the interaction's **logic** is sound end-to-end at the unit level. It does **not**
confirm the slash-menu insertion, the RefPicker, the chip render, the click handler, or the recall
animation actually render and fire in a browser — that is exactly what a rendered probe must show,
and it remains **unverified**.

## Production-safety statement

Because no server or browser ran and no write was issued, **no curator-owned production post was
touched.** The five-sculpture post `695be6c9` (which carries the real `pctx_mrpi3rjk_0` expression
percept and 0 text mentions) is unchanged. This is trivially true here — but it also means the
level-A "insert then discard" behaviour that would normally need proving was not exercised.

## Recommendation

- The rendered probe must be **re-run in a session where servers stay alive**, or **by the user
  locally** (servers run fine on the user's machine; the ready fixture is `/posts/695be6c9…` →
  enter edit mode → `/percept` slash → insert `pctx_mrpi3rjk_0` chip → click → observe recall on the
  image; do **not** save, to keep it level A).
- Until then, R1 records the interaction as **logic-verified, rendered-unverified**, and R2 should
  carry the rendered probe as its first obligation before any new interaction is trialed.
- This is a legitimate R1 outcome: a blocked probe honestly reported is worth more than a fabricated
  green.
