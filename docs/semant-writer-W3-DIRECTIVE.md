# Semant Writer — W3 BUILD DIRECTIVE (operator relations + the operator graph)
**Companion to the W1 and W2 directives and
[`GROUNDING.md`](../backend/services/writer/docs/GROUNDING.md). Read those first.
Executable: build W3 only, until its gate (§8) passes. Do not start W4.**

> Precondition: W2 gate green on `writer/integration` (@ `9d4c7b6` or later). W3 makes the
> author's ontology **visible, editable, and load-bearing on rendering**. It touches the
> render actuator for the first time since W1 — carefully, because that is where the
> honesty guards live.

---

## 0. Mission (one paragraph)
Until now the operator `relations` field has existed and stayed empty. W3 fills it: **typed
edges between operators**, an **editable graph view** built on the Atlas's React Flow
surface, and — the part that matters — **one edge type that feeds rendering**. The author's
ontology stops being a flat list and becomes a structure they can see and shape. The honesty
constraint is precise and non-negotiable: relations may pull *author-defined operators* into
a render (grounded by construction), but every pulled operator must appear in
**provenance**, and no edge may ever pull anything the author did not define. The graph
makes the ontology legible; it must not make it dishonest.

## 1. Prerequisite (do this first — it's small, and W3 makes it matter)
W2 flagged it: **Render re-runs every directive in the document**, so a second Render
re-renders directives whose cards were already accepted. Correct for "run the block," but
W3's `requires` edges make each render pull more, so re-running the whole document compounds
and starts producing duplicate quarantine cards for already-satisfied directives.

Add a **block scope** before building relations:
- A directive whose render was **accepted** is *satisfied*; Render skips satisfied
  directives unless the author explicitly re-runs that one (a "re-render" affordance on the
  committed span).
- A directive whose card was **dismissed** or never rendered is *pending*; Render targets
  pending directives.
- Keep "run the whole block" available as an explicit action, but make the default **render
  only pending directives**.

This is a render-loop concern, not a graph concern — it stays entirely inside the existing
actuator/studio path. Ship it and its test before touching relations. *Test:* accept one of
two directives' cards, Render again, assert only the pending directive produces a new card.

## 2. The edge types — and which one is load-bearing
Store typed edges on the operator (the `relations` field). Define the vocabulary, but be
strict about what affects rendering **in v1**:

| Edge | Meaning | Feeds render in v1? |
|---|---|---|
| `requires` | This operator needs another operator's meaning present to render honestly | **YES — the only one.** |
| `precedes` | Ordering hint (A tends to come before B) | No — advisory in the graph; does **not** auto-reorder directives. |
| `evokes` / `amplifies` / `contrasts` | Semantic/associative structure | No — ontology structure for the graph and for W4's assemblage detection. Rendering-inert in v1. |

Why only `requires` feeds render: the other edges describe *relationships between
operators*, and auto-acting on them (e.g. letting `amplifies` blend two operators into one
span) is the **blended-field composition** that §5/§6 of the plan reserve for Tier 3. v1
stays **sequential — one operator, one span**. `requires` is the sole exception because it
conditions *the same span* with grounding the author has already declared; it never spawns
an extra span.

## 3. How `requires` feeds rendering (the honesty-critical part)
When `/A` is rendered and `A requires B`:
1. **Pull B's definition into A's render prompt as grounding context** for that one span. B
   is author-defined, so nothing ungrounded enters — the ontology wall (I5) holds by
   construction, because a `requires` target is an **operator reference, not free text**;
   you cannot `requires "like Tolstoy"`, so style-by-reference cannot sneak in through an
   edge.
2. **Resolve transitively** — if `B requires C`, C is pulled too.
3. **Detect and reject cycles** — `A requires B`, `B requires A` must be refused at edit
   time (you cannot create the edge) *and* defended at render time (resolution must
   terminate). A cycle is a structural error, surfaced with a reason, never a silent
   infinite pull.
4. **Record every pulled operator in provenance** (I4), marked as **pulled-via-requires**,
   distinct from **directly-invoked**. This is the load-bearing rule: the author typed only
   `/A`, so if the passage reads the way it does partly because of B and C, the provenance
   must say so — otherwise the audit trail lies by omission. A render whose provenance names
   only the directly-typed operators when others were pulled is a failed render.

`requires` conditions one span; it does not reorder, does not add spans, does not blend.
Keep it that narrow.

## 4. The graph surface
Reuse the Atlas's **React Flow (`@xyflow/react`)** surface — the exact MIT component already
in the repo. Do not add a new graph library.

- **Nodes** = operators (name + version; click to inspect definition, examples, negative
  examples — the read view from W2 is enough).
- **Edges** = typed relations, visually distinguished by type; `requires` should read as
  clearly different from the associative edges since it alone affects rendering.
- **Editable**: the author adds/removes/retypes edges directly. This is direct authoring of
  their own ontology, not a model proposal — so edits **commit directly**, but **bump the
  operator version** (relations are part of the operator's versioned identity), and log to
  instrumentation.
- The graph is a **view over the ledger**; it is not a second writer to the manuscript and
  has nothing to do with the canon. Editing the ontology never touches committed prose.

## 5. Invariants at the graph/relation layer (each needs a test)
- **I5 (ontology wall) →** a `requires` target is an operator reference; undefined targets
  are rejected at edit time. *Test:* attempt `requires` on an undefined operator name, assert
  rejection; assert you cannot enter free-text/corpus style as an edge target at all.
- **I4 (provenance) →** pulled operators appear in provenance, marked pulled-vs-direct.
  *Test:* `A requires B`; render `/A`; assert provenance names both, B marked pulled.
- **I1/I3 (canon untouched) →** editing the graph never alters or commits manuscript prose.
  *Test:* edit edges, assert manuscript export byte-identical.
- **Termination →** `requires` cycles rejected at edit time and defended at render time.
  *Test:* both the edit-time rejection and a render-time guard against a pre-existing cycle
  in data.
- **Sequential composition preserved →** a non-`requires` edge does not change a render.
  *Test:* add `A evokes B`; render `/A`; assert B is absent from prompt and provenance.

## 6. What NOT to build (out of scope)
- **Assemblage suggestion / compression** — that is W4. W3 logs co-occurrence (already
  flowing) and lays the graph it will use, but suggests nothing.
- **Any associative edge feeding rendering** — `evokes`/`amplifies`/`contrasts` are inert on
  render in v1. Acting on them is blended-field composition = Tier 3.
- **Auto-discovered edges / operator evolution** — Tier 3. In W3 the author draws every edge
  by hand.
- **Cross-project ontology / the semantic genome** — Tier 3; the graph stays project-scoped.

## 7. Notes
- Backend: relations already live on the operator schema; add read/write only as the graph
  needs (fetch the operator set with relations for the graph; persist edge edits with a
  version bump). Reuse `writerService` — no second service, no new write path to the canon.
- The render change is confined to the actuator's prompt-construction + provenance assembly.
  Do not refactor the W1/W2 loop around it; extend it.
- Instrumentation: log relation edits and, per render, the set of pulled operators — this is
  exactly the structure W4's assemblage detection will read.

## 8. THE W3 GATE — the demo that proves it
W3 is done when this runs green, live, no manual fixup:

1. **Block scope (from §1):** two directives in a doc; accept one card; Render again; assert
   only the pending directive yields a new card.
2. Open the **graph**; see operators as nodes with versions. Add `interiority requires
   threshold` via the graph; assert it persists and bumps `interiority`'s version.
3. Render `/interiority` alone; assert `threshold`'s definition entered the prompt and
   **provenance names both**, with `threshold` marked **pulled-via-requires**; both are
   author-defined (grounded).
4. Attempt to add `threshold requires interiority` (a cycle); assert it is **rejected with a
   reason** at edit time.
5. Add `interiority evokes threshold` on a fresh pair; render; assert the evokes edge **does
   not** change prompt or provenance (rendering-inert).
6. Attempt `requires` targeting an undefined operator; assert rejection. Confirm you cannot
   enter a corpus/style string as an edge target.
7. Edit several edges; **export the manuscript and assert it is byte-identical** to before
   (canon untouched, I1/I3).

If step 3's provenance-marks-pulled check or step 5's inertness check fails, W3 is not done —
those are I4 and the sequential-composition boundary, and they are the point.

## 9. Definition of done
- Block scope shipped (§1) with its test; default Render targets pending directives only.
- Typed relations stored and versioned; graph editable on the reused React Flow surface; no
  new graph lib, no second write path.
- `requires` feeds rendering with transitive resolution, cycle rejection (edit-time +
  render-time), and provenance marking pulled vs direct; all other edges rendering-inert.
- I5/I4/I1/I3/termination/sequential-composition each have a passing test; W1+W2 suites
  still green; export-leak CI still green on `writer/integration`.
- The W3 gate (§8) passes end to end.
- No W4/Tier-3 work; graph project-scoped; canon untouched by anything in this gate.

When this holds, merge at the checkpoint and open W4 (assemblage suggestion + compression) —
the Tier-2 capstone, where the co-occurrence and pulled-operator logs you've been accruing
since W1 finally get read, and the system *suggests* a name while the **author authors** the
assemblage.

---
### Appendix — the line W3 must not cross
W3 is the first time the ontology *acts on its own* — one operator reaching for another. That
is exactly where a writing tool would start quietly composing on the author's behalf. The
discipline that keeps this Semant: `requires` pulls only what the author declared, records
everything it pulled, and never blends or reorders. The moment an edge lets the model bring
something to the page the author didn't put in the ontology — a corpus, a blend, an inferred
association acted on without being named — the grounding decision is broken. Draw the graph;
let `requires` ground a span; keep everything else inert until the author, in W4, names it
themselves.
