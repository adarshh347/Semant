# Semant Writer — W8 BUILD DIRECTIVE (revision & passage genealogy)
**The layer that closes the write → diagnose → revise loop. Pairs directly with W7. Companion to the W1–W5 + W7 directives and `GROUNDING.md`. Executable: build W8 only, until its gate (§7) passes.**

> Precondition: W1–W5 + library surface + W7 merged. W8 makes *revision* first-class: a committed passage can be re-rendered under changed declarations into a new version, with the lineage retained and every revision author-committed. It extends provenance (a temporal axis) and the version resolver. It must never mutate a committed version in place — if it edits existing prose rather than creating a new version, the build is wrong.

---

## 0. Mission (one paragraph)
Today the manuscript only supports first-draft Accept. Real writing is revision, and W7 just made *why* you'd revise visible (an alignment flag). W8 is the honest act of revising: take a committed passage, change the operators or `//` orchestration behind it, re-render, and — on Accept — record a **new version** while keeping the old one. The manuscript tracks the **genealogy**: how this paragraph evolved, and *what intent changed* at each step. The model never edits prose in place and never silently "improves" — it proposes a re-render constrained to the author's changed declarations, the author commits, and every version stays auditable.

## 1. Immutable versions, a moving pointer (the canon rule)
- Every committed passage is an **immutable version**. Revising **creates a new version**; it never rewrites an existing one.
- The manuscript holds a **current pointer** per passage; Accept of a revision moves the pointer forward. **All prior versions are retained** — never mutated, never deleted.
- "Canon is sacred" now means: no committed version is ever altered, and any historical version resolves forever with its original provenance. The pointer moves; history is immutable.

## 2. Revision provenance (the temporal axis of I4)
A revised passage version records, on top of its normal operator/`//` provenance:
- `revised_from: passageId@vN` — its immediate parent version.
- **the declaration diff** — what the author changed between versions (which `//` intents / operators were added, removed, or re-versioned). The genealogy must show not just *that* the text changed but *why* — what intent changed to cause it.
- if the revision was prompted by a W7 alignment flag: `in_response_to: flagId` (citing the operator/intent that flag rested on).

I4 asked "why does this paragraph read the way it does"; W8 extends it to "how did it *become* what it is." The audit trail is now a history, not a snapshot.

## 3. No silent improvement (the guard that keeps revision honest)
The failure mode to forbid: the model "polishing" beyond what the author changed. A re-render is constrained to the author's declared operators + orchestration (I5, unchanged) — it may realize the *changed* declarations, and nothing more. It does not introduce undeclared style "to make it better."
- The re-render prompt is built from the (possibly changed) declared set only — same author's-ontology wall as the render loop.
- If the author revises under an **unchanged** declaration set, the re-render must not inject new flourish; the prompt is materially the same, so no new intent enters. *Test:* re-render under an identical declared set; assert the prompt/constraints are the declared set only, with no added "improve/polish" instruction anywhere.
- Style-by-reference and every existing guard apply to revisions exactly as to first renders.

## 4. Model proposes, author commits (I1, on the revision)
- A revision is a **quarantined re-render** — nothing replaces the current version until Accept.
- **Dismiss** leaves the current version standing; no new version is created.
- No auto-revision, no "revise all," no batch fix. One passage, author-driven, one commit.

## 5. Interactions
- **W7 (the loop):** a W7 flag's only forward action was "author-driven re-render" — W8 *is* that action, made first-class. Revising from a flag records `in_response_to`, and (optionally) re-running the alignment reading on the new version shows whether the divergence cleared — which feeds the §5-W7 calibration signal (did revision actually resolve it?). Close the loop in the audit trail.
- **Version resolver (W5):** must resolve **historical passage versions**, not just the current one. Extend it; add a test that a superseded version still resolves with its original provenance.
- **Blended composition (W6, if built):** a revision of a blended span carries blended provenance per W6 — composes cleanly, no special case.
- **Export:** the manuscript export is **current versions only**. Historical versions live in the ledger's version history — queryable, never in the exported prose. Keep the export clean.

## 6. Editor surface (ship it with W8)
- A **revise** affordance on a committed span: shows the current operators/`//` orchestration, lets the author adjust them, and re-renders → a **quarantined revision card** showing the new text, a **diff against the current version**, and **what changed in the declarations**. Accept moves the pointer; Dismiss keeps the current version.
- A **history / genealogy view** on a span: its versions in order, what changed each time, and any W7-flag links. Read-only.
- **No** auto-revise, **no** "revise all," **no** rewrite-in-place, **no** silent polish affordance anywhere.

## 7. THE W8 GATE — the demo that proves it
Green, live, real Groq, no manual fixup:

1. Commit a passage (v1). **Revise** under a changed `//` intent → a **quarantined** revision; assert it is not applied and current is still v1.
2. **Accept** it → v2 exists, current pointer = v2; **v1 is retained and still resolves with its original provenance**; v2's provenance records `revised_from v1` + the declaration diff.
3. **Dismiss** a revision → current unchanged, no version created.
4. **No silent improvement:** revise under an **unchanged** declaration set; assert the re-render is constrained to the declared set only, with no "improve/polish" instruction present anywhere in the prompt.
5. **Canon immutability:** assert no prior version is ever mutated or deleted; **export = current versions only**, historical versions absent from the exported prose.
6. **W7 loop:** revise in response to a W7 flag; assert the genealogy records the flag link; re-run the alignment reading on v2 and assert the loop is closed in the audit trail (flag cleared or still-present recorded).
7. **Resolver:** assert a superseded historical version still resolves with its original provenance.
8. **Surface:** the revise card shows the declaration diff; the history view shows the genealogy; no auto/batch/rewrite-in-place/polish affordance; dismiss leaves canon and ontology unchanged; export byte-identical to the set of current versions.

If step 4's no-silent-improvement check or step 5's immutability/export check fails, W8 is not done — those are the line between honest revision and a model quietly rewriting the author's book.

## 8. Out of scope (deferred / never)
- **Auto-revision / "improve this" / batch fix** — never; author-driven only.
- **In-place editing of a committed version** — never; versions are immutable.
- **Branching/merging passage versions** (git-like prose branches) — deferred; linear genealogy in v1.
- **Corpus analysis of revision patterns** — log the genealogy and the W7-loop outcomes, build no analysis on them yet (data-gated).

## 9. Definition of done
- Immutable passage versions with a moving current pointer; revising creates a version, never mutates one; all history retained and resolvable.
- Revision provenance records parent, declaration diff, and any W7-flag link; the resolver handles historical versions.
- No-silent-improvement guard (re-render constrained to the declared set, no polish instruction); propose-accept on every revision; no auto/batch revision.
- Export is current-versions-only; historical versions never appear in exported prose.
- Editor surface ships (revise card with declaration diff, read-only genealogy view); every §7 assertion has a passing test; W1–W7 suites still green; export-leak CI still green.
- The W8 gate (§7) passes end to end.

When this holds, the author has the full honest loop: compose in their language (render), see where it diverges from their intent (W7 alignment), and revise into a new version whose whole lineage stays auditable — with the model never once editing the book on its own. Merge at the checkpoint.

---
### Appendix — the one line to hold
Revision is where a writing tool most wants to be helpful — to smooth a sentence, tighten a line, improve what it wasn't asked to. Refuse it in code and review: the re-render realizes the author's *changed declarations* and nothing else, and every version it produces is the author's to accept. The model may re-render under a new intent; it may never decide, on its own, that the prose should be better. The pointer moves only when the author moves it, and no version it leaves behind is ever touched again.

---

## Build record — how the gate was met (added after the build)

**Where the pieces live.**

| Concern | File |
| --- | --- |
| Version store, lineage, declaration diff, loop closure | `backend/services/writer/revisions.py` |
| The revision door (same guards as first Accept) | `PassageStore.accept_revision` in `passages.py` |
| Persistence | `writer_passage_versions` (append-only) |
| Routes | `GET /{p}/revision/{scene}/{block}`, `POST /{p}/revision/accept`, `GET /{p}/genealogy/{lineage}`, `GET …/v{n}`, `POST /{p}/revision/{version}/close-loop` |
| Surface | `frontend/src/writer/revision/` — `RevisionPanel`, `RevisionCard`, `PassageGenealogy`, `DeclarationDiff` |
| Suite | `backend/tests/test_writer_w8.py` (35), `Revision.dom.test.jsx` (17), 7 editor-integration tests |
| Live gate | `scripts/writer_w8_proof.py` |

**Four decisions the directive left open, and how they were settled.**

*The current pointer is the scene block, not a field beside it.* §1 says the manuscript holds a pointer per passage; putting it on the block is what makes §5's export rule true **by construction**. `export_manuscript` walks scene blocks, a block holds exactly one version, so a superseded version has no route into exported prose — there is no filter to remember to apply. Same shape as W2 putting the export rules in the ProseMirror schema rather than in CSS.

*The prior version's text is never in the re-render prompt.* §3 asks that a revision under an unchanged declaration set not inject new flourish. The weak reading is to instruct the model not to; this project has already measured what a prompt-only wall is worth. The strong reading, built here: a revision is a **fresh render under the declared set**, so the prompt is byte-identical to the first render's — asserted with `==`, a fact about the code rather than a hope about behaviour. Handing the model "here is what you wrote, here are the new instructions" is precisely the sentence that produces a tightened verb the author never asked for. The author still sees both versions side by side; the model, which is the party that must not be improving anything, does not.

*The re-render goes through the ordinary run path.* There is no revise-and-render endpoint and no such service method. The panel composes the author's declarations back into a plain block (`// avoid: …` + `/ operator(…)`) and calls the same route the Render button calls. A second render path is where a polish instruction eventually gets added, because it would have no first-render caller to break.

*The loop matches on the declared ELEMENT, not the flag id.* A new reading mints new flag ids, so asking "is `flg_abc` still here?" would answer *cleared* every time and the calibration signal would congratulate itself unconditionally. What survives a revision is the element the flag rested on (`intent:avoid`, `operator:restraint:intent`), so that is what is looked for again — and `still_present` is written down as plainly as `cleared`.

**A fifth question the directive did not raise: prose committed before W8 existed.** Adoption records the block's current text as version 1 from its own provenance, and invents nothing earlier. A plausible synthetic history here would be the audit-trail equivalent of hollow filler.

**What the live gate showed (real Groq, `openai/gpt-oss-120b`).** All eight steps. One result is worth recording because it first read as a failure: the model rendered v1 and v2 with heavily shared wording, and an early version of the proof asserted "v1's opening is absent from the export" — which failed on prose that was entirely correct. The fix was to the *check*, not the code: §7's property is an **equality** (the export is the set of current versions), not an absence, because two versions of one passage share an author, an ontology, and often an opening clause. The proof now asserts the equality and prints an honest note when the two versions overlap textually.

**What was deliberately not built.** No rewrite-in-place anywhere. No restore/revert button on the genealogy — restoring would move the pointer with no authoring act behind it; the honest route back to v1's prose is to declare it again and render, which produces a new version with a diff that explains itself. No auto-revise, no "revise all". No analysis over the revision corpus: §8 says log it and analyse later.
