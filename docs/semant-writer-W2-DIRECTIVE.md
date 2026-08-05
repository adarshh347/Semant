# Semant Writer — W2 BUILD DIRECTIVE (the literary editor surface)
**Companion to `semant-writer-DIRECTIVE.md` (W1). Read that and
[`GROUNDING.md`](../backend/services/writer/docs/GROUNDING.md) first. This directive is
executable: build W2 only, until its gate (§7) passes green. Do not start W3.**

> Precondition: the W1 gate is green on `writer/integration` (rebased onto `origin/main`,
> `manuscript_renderer` role declared, all six invariants guarded + tested). If any of that
> is not true, stop and fix W1 first. W2 builds *on top of* the W1 loop — it does not
> modify it.

---

## 0. Mission (one paragraph)
W1 proved the loop headlessly: parse a block → render a quarantined passage constrained to
the author's ontology → Accept into the canon, with provenance, refusal, and no `//` leak.
**W2 gives that loop a body the author actually writes in** — a literary editor where `//`
orchestration and `/` directives are first-class, visually distinct objects, quarantined
renders appear inline as cards you Accept or Dismiss, and accepted prose flows into the
manuscript with real literary cadence. W2 is **almost entirely frontend.** The backend
contract from W1 is stable; touch it only to add read endpoints the editor needs. The point
of W2 is the *surface*, and the surface must not weaken a single invariant.

## 1. Scope — and the hard boundary
**In scope:** the TipTap/ProseMirror editor, the two-tier cadence, focus mode, wide margins,
inline operator chips, the visual `/` vs `//` distinction, inline quarantine cards
(Accept/Dismiss/provenance), and the refusal card (with the `#create` on-ramp from
`GROUNDING.md`).

**Out of scope — do not build, do not stub beyond a link:** the operator graph and typed
relations (W3), assemblage suggestion (W4), blended-field composition, and everything in
Tier 3. Operator chips may *link toward* a future graph view, but W2 ships no graph.

**The boundary that matters:** W2 does **not** re-implement rendering, quarantine, Accept,
the ontology wall, or the parser. It calls the existing `studio.run_block` / render actuator
/ Accept gate through `writerService`. If you find yourself writing a second code path that
produces or commits prose in the frontend, stop — that is a second door to the canon, and
the canon has one owner (`manuscript_service`, via the W1 Accept gate). The editor is a
**view over the ledger**, not a writer to it.

## 2. Why TipTap, not BlockNote (settled — do not revisit)
Build on **TipTap / ProseMirror.** This is a deliberate override of
`writing-studio-plan.md`'s BlockNote default. BlockNote's Notion-block feel is exactly the
wrong register for a literary surface, and the two-tier cadence plus custom
`//`/`/`/quarantine nodes need schema and block/line control that BlockNote fights.
(BlockNote remains fine for the *argument* article surface in `frontend/src/atlas/`; this is
the *literary* surface and it is TipTap.) Do not introduce a second rich-text framework.

## 3. The editor's four node types (ProseMirror schema)
The schema is where the invariants become structural rather than cosmetic. Define these
nodes and enforce their serialization rules **in the schema**, not in CSS:

1. **`manuscript` blocks** — committed prose. `paragraph` + a distinct `soft_break` so the
   surface carries the **two-tier cadence** (soft line break within a beat vs. paragraph
   break between beats — the literary spacing, not uniform block gaps). This is the only
   node type that serializes into the exported/printed manuscript.
2. **`orchestration` node** (the `//` layer) — the author's private reasoning (`//goal`,
   `//arc`, `//priority`, `//avoid`, `//voice`). Rendered in a distinct, quiet register
   (margin/ghost styling). **Schema rule: it MUST NOT serialize into the manuscript
   export.** This is I6 enforced structurally — the `//`-leak guard now lives at the
   document-model layer, not just the render boundary.
3. **`directive` inline node** (the `/` layer) — rendered as an **operator chip** (name +
   version, click to inspect its definition). Invoking directives calls the existing loop.
4. **`quarantined_passage` node** — an inline **card** holding an unaccepted render: the
   proposed prose, its **provenance** (operators + versions, active `//` intents, model,
   scene), and **Accept / Dismiss** affordances. **Schema rule: `committed=false` content
   MUST NOT serialize into the manuscript export until Accept transforms it into
   `manuscript` blocks.** This is I1 enforced structurally.

## 4. The invariants, restated at the surface (each needs a UI test)
W1 guards the loop; W2 must guard the *view*, or the surface silently reintroduces what the
loop forbids.

- **I1 (propose/commit) →** quarantined passages render as visibly *unaccepted* cards;
  nothing enters `manuscript` nodes without an explicit Accept click that routes through the
  W1 Accept gate. *Test:* render in the editor, assert manuscript export unchanged until
  Accept.
- **I2 (refusal is an answer) →** a refusal renders as a **card with its reason**, never as
  an empty result, a spinner that never resolves, or filler prose. Style-by-reference
  refusals render the `#create` on-ramp inline. *Test:* trigger a refusal in the editor,
  assert a reason is shown and no prose card appears.
- **I4 (provenance) →** every accepted span is inspectable — click it, see which operators
  (with versions) and `//` intents produced it. *Test:* accept a passage, assert its
  provenance is retrievable from the committed node.
- **I6 (`//` never on the page) →** the schema rule in §3.2 is the guard. *Test (mandatory,
  in CI):* put a distinctive token in a `//goal`, render and Accept the passage, **export the
  manuscript, assert the token is absent.** This is the W1 CI test moved up to the document
  model.

If any invariant cannot hold at the surface, the surface feature is out of scope until it
can.

## 5. Editor experience requirements
- **Two-tier cadence** working: soft break vs paragraph break produce visibly different
  spacing, and both round-trip through the ledger correctly.
- **Focus mode** and **wide margins** — the surface should feel like a place to write prose,
  not a form. (This is a real requirement, not polish; the whole pitch of W2 is that the loop
  now feels like writing.)
- **Operator chips inline** for `/` directives, showing name + version; clicking inspects the
  operator definition (read-only view is fine in W2).
- **Visual `/` vs `//` distinction** unmistakable at a glance — the author must never confuse
  "this conditions generation, invisible" with "this renders, visible."
- **`#create` reachable from the editor** so a refusal's on-ramp is one action, not a context
  switch.

## 6. Frontend/backend notes
- Upgrade `frontend/src/writer/WriterStudio.jsx` into the TipTap editor; **reuse
  `writerService.js`** for all backend calls — do not add a second service.
- Backend: add only **read** endpoints the editor needs (fetch manuscript for display, fetch
  operator list for chips/inspection). The **render** and **Accept** endpoints already exist
  from W1 — reuse them unchanged. No new write path.
- Instrumentation (`instrument.py`) already logs usage/co-occurrence; the editor just keeps
  feeding the same events. **Build nothing on that data** — it accrues for Tier 2/3, which
  are not now.

## 7. THE W2 GATE — the demo that proves the surface
W2 is done when this runs green in the actual editor, no manual fixup:

1. Open the editor on the fixture manuscript. Confirm **focus mode + wide margins**, and that
   committed prose shows the **two-tier cadence** correctly.
2. Type a block: two `//` lines (a `//goal` and a `//avoid`) rendered in the quiet `//`
   register, then two `/` directives shown as **operator chips** with versions.
3. Render. A **quarantined card** appears inline with the proposed prose and full
   **provenance**; nothing has entered the manuscript.
4. **Accept.** The prose flows into the manuscript as `manuscript` blocks with correct
   cadence; click the new span and see its provenance. **Export the manuscript and assert the
   `//goal`/`//avoid` text is absent** (I6 at the document model).
5. Feed a `//voice like Tolstoy` line and render. A **refusal card** appears with its reason
   and the inline **`#create` on-ramp**; no prose card, nothing written.
6. Dismiss a different quarantined render; assert it leaves no trace in the ledger (I3 at the
   surface).

If step 4's export-leak check or step 5's refusal card fails, W2 is not done — those are I6
and I2 at the surface, and they are the point of doing this in the schema rather than in CSS.

## 8. Definition of done
- TipTap editor shipped in `frontend/src/writer/`, reusing `writerService`; no second
  rich-text framework, no second write path to the canon.
- The four node types exist with their **schema-enforced** serialization rules; the
  `//`-leak test runs against the **export**, in CI.
- I1, I2, I4, I6 each have a surface-level test (plus I3's dismiss-leaves-no-trace); W1's
  backend tests still green.
- The **W2 gate in §7 passes** end to end, including the refusal card and the export-leak
  assertion.
- Two-tier cadence, focus mode, wide margins present and working.
- No W3/W4/Tier-3 work; no new backend write path; backend render/Accept contract unchanged.

When this holds, merge to `main` at the checkpoint and open W3 (operator relations + the
React Flow graph, reusing the Atlas surface).

---
### Appendix — the register to hold
W1 proved the loop is honest. W2's job is to make the honest loop **feel like writing** — so
that when the author accepts a passage, it reads like their own second mind handing it back,
and when it refuses, the refusal feels like an honest collaborator saying "tell me what you
mean" rather than a tool erroring out. If the editor makes the loop feel like filling in a
form, the surface has failed even with every test green. Build for the feeling of prose;
enforce the invariants in the schema so the feeling never costs the honesty.
