# Semant Writer — W10 BUILD DIRECTIVE (depth registers — the author's cognitive layers)
**The last clean buildable-now DSL gate. Companion to the W1–W9 directives and `GROUNDING.md`. Executable: build W10 only, until its gate (§8) passes. Read §2 — the author's-ladder rule is load-bearing, like the taste wall was for W7 and the verbatim rule for W9.**

> Precondition: W1–W9 merged (W9 with BM25 recall is fine; W10 does not depend on the ranker). W10 adds a **register** attribute to operators, register orchestration at render time, and a depth view of the manuscript. It imposes no taxonomy and generates no interpretation — if it ships a fixed depth ladder or a model "reading at depth," the build is wrong.

---

## 0. Mission (one paragraph)
A sophisticated passage works on several layers at once — the literal surface, the interior, the thematic. W10 makes those layers an explicit, **author-declared** axis: the author names their own registers, tags operators with them, renders a passage foregrounding a chosen register, and views the manuscript by depth. Depth is realized only through the author's register-tagged operators and read only from provenance — Semant never asserts what the layers of meaning *are*, and never decides on its own what a given depth *means*. The ladder is the author's.

## 1. Why this is a DSL feature, not a metaphor
The plan lists "cognitive layers (surface→philosophical)" in the emergent tier, but the *emergent* part is auto-discovering an author's layers from a corpus — that stays deferred. The **mechanism** — letting the author declare depth registers and orchestrate across them — is ordinary DSL design, buildable now. What makes it honest rather than a generic "add more depth" button is that every piece of it routes through the author's own declarations, never the model's notion of depth.

## 2. The author's-ladder rule (load-bearing — enforce, don't assume)
State it in code and defend it:

> **A register is a name the author gives a layer of their own work. Semant imposes no taxonomy of depth; it never renders or reads "at a depth" by consulting its own idea of what that depth means. Depth lives entirely in the author's declared registers and their register-tagged operators — realized at render through those operators, derived at read from provenance, invented at neither.**

Three consequences, each a guard:
- **No imposed taxonomy.** Do **not** ship `surface / psychological / philosophical` as a hardcoded, immutable ladder. The author declares their own register vocabulary (their words, their order). You *may* offer the classic ladder as an **adoptable template** the author edits and commits (propose-accept, like a suggested operator) — never as a default that can't be changed.
- **No fabricated depth at render.** "Render this more philosophically" in a vacuum is the model's idea of philosophical = priors. Depth is realized **only through the author's operators tagged with that register.** If the author asks to render at a register for which they've declared no operators, the render **refuses/notes** ("no operators declared at register X"), exactly like thin orchestration — it never invents the depth.
- **No interpretation at read.** "Read at depth" is a **provenance-derived view** — which committed spans carry which register, because of the register-tagged operators that made them. A generated "here is the philosophical reading of your chapter" is fabrication and is forbidden.

## 3. Registers are author-declared references
- The author declares a **register vocabulary**: a small, ordered, named list (project-scoped, stored like operators; portable later via the W5 mechanism). Order is the author's, not asserted by the system.
- An operator gains an optional **`register`** field whose value must be one of the author's **declared registers** — a reference, not free text (you cannot tag an operator with an undeclared register string, the same way a `requires` target must be a real operator). Editing an operator's register **bumps its version** (it changes the operator's behavior).
- Optional adoptable template (the classic ladder) is offered via propose-accept and is fully editable; it is never the hardcoded default.

## 4. Render-time: `//register` orchestration
- A new `//` intent, `//register <name>` (or a set), foregrounds a register: the render is conditioned to work primarily at that layer, realized by **selecting/weighting the author's operators tagged with that register**. It is orchestration — invisible to output (I6), stripped from surface text like every `//` note.
- The render is still constrained to declared operators (I5, unchanged); `//register` selects among them by the author's tags, it does not add a generic "be deeper" instruction to the prompt.
- **No declared operators at the requested register → honest refusal/note, never fabricated depth** (§2). This is the load-bearing render guard.
- Provenance records the active `//register` alongside the operators (I4).

## 5. Read-time: the depth view
- A view over the manuscript that shows, per committed span, **which registers it operates at** — derived from the registers of the operators in that span's provenance. Read-only, purely derived; **no model call, no interpretation.**
- Filter/annotate the manuscript by register ("show the interior layer") = show the spans whose operators carry that register. Honest because it's provenance, not a reading.
- A span the author typed directly (no operator provenance) simply carries no register — it is not assigned one by inference.

## 6. Interactions
- **W7 alignment (natural, not required):** register can become a declared standard — "you rendered this at register `interior` but it reads purely surface" is a legitimate W7 flag **only if** grounded in a register-tagged operator's intent. Wire it if cheap; do not build a separate register-critique that judges depth by the model's taste.
- **Assemblages (W4) / blends (W6 if built):** members may span registers; an assemblage's register set is derived from its members; a blend across registers is the author's declared composition — fine, no special case.
- **Portability (W5):** register vocabulary is project-scoped in v1; carrying it across books rides the existing single-author portability mechanism later.

## 7. Guards / invariants (each needs a test)
- **No imposed taxonomy.** *Test:* the register vocabulary starts empty/author-set; assert no hardcoded ladder is treated as truth; the template is adoptable and editable, not a fixed default.
- **Grounded register reference.** *Test:* tagging an operator with an undeclared register string is rejected.
- **No fabricated depth (render).** *Test:* `//register X` with no operators tagged X → refusal/note, not a passage inventing depth X.
- **No interpretation (read).** *Test:* the depth view makes no model call; its output is derived from provenance; a hand-typed no-provenance span carries no inferred register.
- **Ontology wall + `//` wall hold.** *Test:* `//register` never appears in surface text (I6); a register-orchestrated render with a style-by-reference `//voice` still refuses (I5).
- **Canon untouched (I1).** *Test:* declaring registers, tagging operators, rendering-at-register, and viewing by depth produce no committed prose except through Accept; export byte-identical.

## 8. THE W10 GATE — the demo that proves it
Green, live, real Groq, no manual fixup:

1. Declare a register vocabulary (the author's own, ordered); assert it stores and that adopting the optional classic template goes through propose-accept and is editable — not a hardcoded default.
2. Tag operators with registers; assert an undeclared register string is rejected and editing an operator's register bumps its version.
3. Render with `//register <name>` → the render foregrounds the author's operators tagged with that register; provenance records the active register; `//register` appears **nowhere** in the surface text (I6); passage quarantined.
4. **No fabricated depth:** `//register <name>` with **no** operators tagged that register → honest refusal/note, **not** a passage inventing that depth.
5. **Read at depth is derived:** the depth view shows which committed spans carry which register from provenance; assert **no model call**; a hand-typed span carries no inferred register.
6. **Ontology wall:** a register-orchestrated render with `//voice like <corpus>` still refuses.
7. **Canon untouched:** across declaring/tagging/rendering/viewing, no committed prose except via Accept; export byte-identical.
8. **Surface:** declare/edit registers, tag operators, render at a register, and the depth view — with no imposed taxonomy and no generated interpretation anywhere.

If step 4's no-fabricated-depth check or step 5's no-interpretation check fails, W10 is not done — those are the two halves of the author's-ladder rule, and they are the point.

## 9. Out of scope (deferred / never)
- **A hardcoded / imposed depth taxonomy** — never; registers are author-declared (a template is adoptable, not a default).
- **Model interpretation of "the meaning at depth X"** — forbidden; read-at-depth is provenance-derived, not a generated reading.
- **Fabricated depth at render** — forbidden; realized only through register-tagged operators.
- **Auto-tagging operators by register** (the model deciding an operator is "psychological") — imposing a taxonomy; author-declared only. A *suggestion* under propose-accept could come later; not in W10.
- **Cross-project register vocabulary** — rides W5 portability later; project-scoped now.
- **Corpus analysis of register usage** — log now, analyze later (data-gated).

## 10. Definition of done
- Author-declared, ordered register vocabulary (project-scoped); optional adoptable template via propose-accept; no hardcoded ladder as truth.
- Operators carry a register that must reference a declared register; editing it bumps the version.
- `//register` orchestration foregrounds a register through the author's register-tagged operators, refuses when none are declared, is stripped from surface text, records to provenance.
- Depth view derived purely from provenance — no model call, no interpretation; hand-typed spans carry no inferred register.
- Ontology/`//` walls and canon-immutability hold; editor surface ships; every §8 assertion has a passing test; W1–W9 suites still green; export-leak CI still green.
- The W10 gate (§8) passes end to end.

When this holds, the author can work their manuscript in the layers they named — rendering to foreground a depth through their own operators, and reading the book by depth from what actually made each span — with Semant never once telling them what depth is or what theirs means. Merge at the checkpoint.

---
### Appendix — the one line to hold
Depth is where a writing tool most wants to sound literary — to offer the four levels of meaning, to tell the author their scene "lacks philosophical weight." Refuse it: those are the model's ladder and the model's taste, and the author didn't set either. W10 gives the author a way to name their own layers and realize them through their own operators, and it gives Semant no opinion about depth at all. The registers are the author's; the model climbs the ladder it's handed and never draws one of its own.

---

## Build record — how the gate was met (added after the build)

**Where the pieces live.**

| Concern | File |
| --- | --- |
| Vocabulary, template, depth view | `backend/services/writer/registers.py` |
| Operator `register` (validated reference, versions on change) | `operators.py` |
| `//register` orchestration key | `dsl.ORCHESTRATION_KEYS` |
| The no-fabricated-depth refusal | `_register_refusal` in `render.py` |
| Persistence | `writer_registers` (one doc per project) |
| Routes | `GET/PUT /{p}/registers`, `GET /registers/template`, `GET /{p}/depth` |
| Surface | `frontend/src/writer/registers/` — `RegisterPanel`, `DepthView` |
| Suite | `backend/tests/test_writer_w10.py` (40), `Registers.dom.test.jsx` (16) |
| Live gate | `scripts/writer_w10_proof.py` |

### Five decisions the directive left open

*The vocabulary starts empty and there is no seeded ladder anywhere.* §2 says the classic ladder may be an adoptable template but never a default. The strongest form of that is a fresh project returning `[]`, `//register` refusing until the author declares something, and `CLASSIC_TEMPLATE` living as a literal that only `propose_template()` reads. The reasoning is worth stating because the temptation is real: an empty list looks unfinished, and `surface / psychological / philosophical` is a perfectly good ladder — but **whatever ships as the default becomes what most authors keep, so the default IS the imposition**, however reasonable it reads.

*`register` is exempt from the style-by-reference heuristic, because it is checked by something stricter.* A register value must name a **declared** register or the render refuses — and declaring a name is precisely the act that grounds it, which is the same remedy the style refusal itself points at (`#create it, in your words`). Leaving `register` in the heuristic would over-refuse on the author's own vocabulary: an author who names a layer `noir` because that is what the layer **is** to them would be told they cannot use their own declared word. The live proof asserts both directions — `//register: noir` renders, `//voice: noir` still refuses.

*The register is stamped into provenance at render time, not looked up later.* Retagging an operator bumps its version, but prose already committed was made at the **old** layer. A depth view that read the current tag would silently rewrite the history of the book's layers every time the author reorganised their ladder. Stamping also makes the view purely derived — it reads provenance and performs no lookups at all.

*Refusing beats proceeding-and-ignoring.* When no operator in a directive carries the requested register, the render refuses rather than dropping the note. Quietly ignoring it is worse: the author would read the result as prose written at their register when nothing about it was. The refusal names the register, says nothing of theirs carries it, and says how to fix it — generative, in the house style.

*A register in use cannot be dropped from the vocabulary.* Removing it would leave operators pointing at a name that no longer means anything — a dangling reference of exactly the kind `requires` edges are validated against. `declare` refuses and names the operators in the way.

### What the live gate showed (real Groq, `openai/gpt-oss-120b`)

All eight steps. A fresh project with no ladder; the author's own three-rung ladder (deliberately not the classic one, so nothing could pass by accidentally agreeing with a default); `//register: interior` rendering with `frost`→`weather` and `withheld`→`interior` stamped per operator and the word "interior" appearing nowhere in the prose; `//register: inheritance` refusing **before the model** with no prose produced; the depth view indexing spans by the layer they were made at, with `inheritance` empty rather than guessed.

### One thing found in review rather than by design

`FakeCollection.update_one` ignored its `upsert` argument, so the very first register declaration in any test silently wrote nothing — an empty ladder that looked like a working one. Twenty-six tests failed at once and pointed straight at it. Worth recording because it is a fake diverging from the real store in the one direction that manufactures false confidence: everything downstream would have "passed" against a vocabulary that was never saved.

### What was deliberately not built

No hardcoded ladder. No model interpretation of what a layer means — the depth view has no model client to reach and a test enforces that by AST. No auto-tagging of operators by register (the model deciding an operator is "psychological" is the imposed taxonomy arriving one object lower down). No ranking between registers: `order` is recorded so the view can show the author's sequence, and a test walks the AST asserting no comparison is ever made on it. The CSS styles every layer identically for the same reason — a visual hierarchy would assert that a later rung is deeper. No cross-project register vocabulary; no analysis of register usage.
