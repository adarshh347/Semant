# Semant Writer — W5 BUILD DIRECTIVE (portable ontology — the semantic-genome mechanism)
**The first layer past Tier 2. Companion to the W1–W4 directives,
[`GROUNDING.md`](../backend/services/writer/docs/GROUNDING.md), and the dogfooding guide —
read those first. Executable: build W5 only, until its gate (§9) passes.**

> A note on "no W5": the earlier guidance said there was no W5, and for the *emergent*
> Tier-3 ideas that remains true — auto-discovered operators, operator evolution, a language
> that mutates across books on its own, are data-gated and unbuilt. W5 is not one of those.
> It is the buildable **mechanism** the emergent layer will one day need: lifting operators
> and assemblages from project-scoped to a reusable cross-manuscript library. It earns a gate
> number because it is engineering with a real honesty problem to solve, not a guess about
> structure that doesn't exist yet.

---

## 0. Mission (one paragraph)
Today an operator or assemblage lives inside one manuscript. W5 gives the author a
**library** above project scope: promote an operator you defined in Book A, import it into
Book B, and render with it there — grounded, because it is still *your* declared language.
The honesty spine holds and even widens: the evidence base becomes the author's cross-project
ontology. The whole gate turns on two guardrails — the library is **single-author** (importing
someone else's operator would render your canon in a voice you didn't declare, which is the
priors violation sourced from another human), and **provenance pins the exact operator version
forever**, so nothing that portability touches makes an existing passage's audit trail
unresolvable.

## 1. The core design decision (build it this way; flag if you'd change it)
When an operator is imported into a project, is it a **copy** or a **live reference**? Build
**copy** — specifically a **linked copy**:

- **Import = copy the operator into the project**, stamped with `library_ref` lineage (source
  library operator id + the exact version imported). The project copy is **independently
  versioned** thereafter.
- **Project edits stay local.** Editing an imported operator in Book B never mutates the
  library or Book A. No spooky action at a distance.
- **Publishing back is explicit.** The author may `publish` a project operator's improvements
  to the library (creates a new library version), and may `pull` a newer library version into
  a project (author-reviewed, propose-accept). Neither happens automatically.

Why not a live shared reference: a live reference means editing the operator while writing
Book B silently changes the ontology under Book A. Committed prose is immutable so the canon
is safe, but Book A's *declared meaning* would shift without the author ever revisiting Book
A — and "the language evolves across books on its own" is exactly the **emergent** behavior
that is data-gated and deliberately deferred (§8). The linked-copy model gives you the
portable library today and leaves the live-evolution model as a future the mechanism can
support, without pretending the emergence now.

*This is the load-bearing choice of W5. If you want live-shared-reference semantics instead,
stop and confirm — it changes the honesty analysis in §5 and the whole gate.*

## 2. The library
- A store **above project scope**, in the ledger (its own collection), keyed by **author**,
  independent of any manuscript.
- Holds operators and assemblages with **full immutable version history** — old versions are
  never discarded, because committed passages across every book point at exact versions and
  must always resolve.
- Starts **empty**. Nothing auto-migrates. The author populates it by **promoting** operators
  they want to reuse. Existing project operators stay project-scoped until promoted.
- Optional, additive: index library operators with **pgvector** (plan §7) for "find an
  operator like this across my books" when importing. Search UX only — it informs discovery,
  never meaning.

## 3. The four operations (all explicit, all author-committed — propose-accept)
- **Promote** — copy a project operator up into the library (records source-project lineage +
  version). The project keeps working unchanged.
- **Import** — copy a library operator down into a project as a linked copy (records
  `library_ref`). Grounded on render because it is the author's own declaration.
- **Publish** — push a project operator's current state to the library as a new version
  (records that it came from this project). Does not touch other projects.
- **Pull** — bring a newer library version into a project, author-reviewed. Never automatic.

None of these is a canon write. All are ontology writes, logged to instrumentation.

## 4. Transitive closure (relations & assemblages must come along)
Operators carry `requires` edges (W3); assemblages carry `members` (W4) — both are operator
references. Import/promote must handle the closure:
- Importing an operator that `requires` others **brings the required operators too**
  (transitive), or **refuses with a named missing dependency** — never imports an operator
  whose declared context is absent, because rendering it would reach for a referent that isn't
  there.
- Importing an assemblage **brings its members** (they are operator refs). Same transitive
  rule.
- Mirror W3's discipline: resolve transitively, detect cycles, and never leave a dangling
  reference.

## 5. Honesty invariants for portability (each needs a test)
- **I5 (ontology wall), widened + guarded.** The evidence base is now the author's
  *cross-project* ontology — still their own declarations, so grounded. **Guardrail:
  single-author.** An operator's `author` must match the manuscript's author at render; a
  foreign-authored operator **refuses** (rendering your canon in a voice another person
  declared is the priors violation with a human source). *Test:* render with an operator whose
  `author` ≠ the manuscript author → refusal.
- **I4 (provenance), made durable.** Every committed passage's provenance pins operator
  `name@version@scope` and must resolve **forever**, across promote/import/edit/publish.
  Imported-operator provenance also names its `library_ref` source. *Test (mandatory):* every
  pre-existing W1–W4 provenance record still resolves to its exact operator version after the
  library exists; an imported operator's render names its library lineage.
- **I1/I3 (canon untouched).** Promote/import/publish/pull are ontology writes; they never
  alter or commit manuscript prose. *Test:* manuscript export byte-identical across a full
  session of library operations.
- **Propose-accept.** No library change propagates into any project without an explicit author
  action. *Test:* publish a new library version; assert no project's operator changed until an
  explicit pull.
- **No spooky action.** Editing an imported operator in one project changes neither the
  library nor any other project. *Test:* edit in Book B; assert library and Book A
  byte-identical.

## 6. Migration (do no harm to what exists)
- Existing project-scoped operators/assemblages **stay where they are**; nothing is
  force-lifted.
- The library is additive: a new collection, new `library_ref`/lineage fields on operators
  (nullable), new endpoints. No change to the render/Accept contract.
- **The migration must not break a single existing provenance record** — this is the first
  thing to verify (§5, I4 test) and the thing most likely to bite. Version resolution has to
  keep working for every passage already committed in W1–W4 fixtures.

## 7. Notes
- Backend: new library collection + promote/import/publish/pull endpoints; add `library_ref`
  and cross-project lineage to the operator schema (nullable, so existing data is valid).
  Reuse `writerService` and the operator registry — no second service, no new write path to
  the canon.
- The render actuator changes only to (a) enforce the single-author guard and (b) resolve
  operator versions across scopes. Do not refactor the loop around portability; extend it.
- Instrumentation: log promote/import/publish/pull and the library lineage of any operator
  used in a render — this is the seed data for the eventual cross-project analysis.

## 8. Out of scope (still emergent / deferred — do not build)
- **Live shared references / auto-propagating edits** (Model B in §1) — the emergent
  living-language behavior; data-gated.
- **Cross-AUTHOR / community libraries** — raises "whose ontology is the evidence base?", a
  distinct and larger honesty question. **Single-author only** in W5.
- **Auto-discovery of what to promote, or auto-import** — that is operator-evolution,
  data-gated.
- **Blended-field composition** — a different sophisticated layer; unaffected here, still
  sequential.

## 9. THE W5 GATE — the demo that proves it
W5 is done when this runs green, live, no manual fixup:

1. **Provenance durability first:** with the library schema in place, assert every
   pre-existing W1–W4 provenance record still resolves to its exact operator version. (If this
   fails, stop — the migration broke the audit trail.)
2. **Promote** `interiority` from Book A to the library; assert it appears with author +
   version + source-project lineage, and Book A still renders it unchanged.
3. Open a second manuscript, **Book B**; **import** `interiority`; assert a linked copy with
   `library_ref`, independently versioned.
4. Render `/interiority` in Book B; assert it renders **grounded** (author's own declaration),
   provenance naming the operator version **and** its library lineage.
5. **Edit** `interiority` in Book B; assert the library entry and Book A's copy are
   **byte-identical** (no spooky action).
6. **Publish** Book B's improved `interiority`; assert a **new library version**; assert Book A
   unchanged until an explicit **pull**, then pull into Book A and assert it updates only on
   that action.
7. Import an operator that `requires` another (and an assemblage with members); assert
   **transitive import** brings the closure, or refuses with a named missing dependency.
8. **Single-author guard:** simulate a foreign-authored library entry; attempt to render with
   it; assert **refusal**.
9. **Canon untouched:** export both manuscripts byte-identical across all of the above.

If step 1's provenance-durability check or step 8's single-author refusal fails, W5 is not
done — those are I4-across-scope and I5-across-authors, and they are the point.

## 10. Definition of done
- Library store keyed by author with immutable version history; promote/import/publish/pull
  all explicit and logged; linked-copy semantics (no spooky action).
- Transitive closure on import/promote for `requires` and assemblage `members`; no dangling
  references; cycles handled.
- I5-single-author, I4-durable-provenance, I1/I3-canon-untouched, propose-accept, and
  no-spooky-action each have a passing test; W1–W4 suites still green; export-leak CI still
  green.
- Migration adds only nullable fields + a new collection; no existing provenance record
  broken; render/Accept contract unchanged.
- The W5 gate (§9) passes end to end.
- No emergent/cross-author/auto work; single-author; canon untouched.

When this holds, the author has a portable language — the same declared voice usable across
every book, grounded everywhere it's used. Merge at the checkpoint. The *evolution* of that
language across projects remains the emergent, data-gated future the dogfooding corpus will
eventually inform.

---
### Appendix — the line W5 must not cross
Portability is safe exactly as long as everything in the library is the author's own
declaration and every passage can still name the exact version that made it. The moment an
operator from another person's hand can render your canon, or an edit in one book silently
redefines another, the grounding decision is broken — the first by sourcing meaning the author
didn't declare, the second by moving the evidence under prose the author already committed.
Single-author, linked copies, pinned versions, explicit sync. Build the library the author can
carry between books; leave the library that changes itself for when there's a corpus to prove
it should.
