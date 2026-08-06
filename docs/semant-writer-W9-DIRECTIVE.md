# Semant Writer — W9 BUILD DIRECTIVE (recall & cite — the manuscript's memory of itself)
**Completes the original Track B actuator triad (draft / recall / cite). Companion to the W1–W8 directives and `GROUNDING.md`. Executable: build W9 only, until its gate (§7) passes. Read §2 — the verbatim rule is the load-bearing honesty decision, like the taste wall was for W7.**

> Precondition: W1–W8 merged. W9 adds two actuators — `recall` (surface the author's own prior committed prose by meaning) and `cite` (ground a render in that retrieved canon) — plus their surface. `recall` performs retrieval, not generation; if it ever synthesizes prose, the build is wrong.

---

## 0. Mission (one paragraph)
The render loop composes from the author's declared operators. W9 lets a passage also rest on the author's **own committed manuscript** — the purest grounding in the system, because it isn't just a declared operator, it's accepted prose the author already stood behind. `recall` finds earlier committed passages by meaning; `cite` lets a new render be conditioned on them, with provenance recording which. The one rule that keeps it honest: **recall retrieves verbatim — it never summarizes.** The model may surface what the author wrote; it may never narrate what the author "established."

## 1. Why this is the purest grounding
`GROUNDING.md`: the author's declared ontology is the evidence base. W9 adds the author's own **committed prose** as evidence — and it's purer than an operator, because a committed passage is prose the author accepted into canon, not merely a declaration about prose. Resting a new passage on prior canon is honest by construction. It is the writer's analogue of the vision side grounding on an already-*marked* region rather than raw pixels: the material recall stands on has already passed the Accept gate.

## 2. The verbatim rule (load-bearing — enforce structurally)
The failure mode that would poison this: a `recall` that *summarizes* — "you established the room was cold, the sister estranged." A model summary of prior chapters is fabrication wearing the author's canon: it asserts a settled fact the prose may have left ambiguous, and the author would then write against a version of their book the model invented.

So:
- **`recall` returns verbatim committed spans** — the actual stored text, with each span's location and provenance — ranked by relevance. It has **no generation step**. Retrieval, not narration.
- **There is no "what you established" synthesis anywhere in the recall path.** If the author wants a synthesis of prior material, that is a *render* — quarantined, grounded, author-committed — not a recall. Keep the two apart.
- Enforce at the boundary: the recall path reads stored spans and returns them; it does not call the model to describe them. *A recall that produces text not byte-present in the ledger is a failed build.*

## 3. `cite` — grounding a render in prior canon
- A render may be conditioned on recalled spans: the **verbatim** prior text enters the prompt as grounding ("stay consistent with this established material"), and provenance records `cited: [{passageId, version}, …]`.
- **Cite only committed canon (I3).** The cited spans must be accepted committed versions — never unaccepted/quarantined material, which is transient session memory. Citing an unaccepted render would rest canon on something the author never accepted. Guard it: cite resolves only committed passage versions.
- **I5 unchanged.** The render is still constrained to the author's declared operators; it may now *also* rest on the author's own prior canon. Both are the author's; style-by-reference is still refused. Cite adds grounding, it does not open a bypass.

## 4. Retrieval mechanics
- pgvector over the manuscript's **committed** passages (embed committed prose; index on Accept, keep consistent as W8 versions move — recall targets **current** versions by default; historical versions retrievable only by explicit query).
- **Project-scoped in v1.** Recall searches the author's own manuscript. Cross-manuscript recall ties to the portable-ontology single-author question and is deferred (§8).
- Empty is an honest answer: if nothing relevant exists, recall returns **empty** ("nothing in your manuscript matches"), never a fabricated "you may have established…". This is the retrieval analogue of refusal-as-silence.

## 5. Guards / invariants (each needs a test)
- **Verbatim-not-summary (§2).** *Test:* recall's returned span text is byte-equal to committed prose; assert the recall path has no generation call; a query matching nothing returns empty, not synthesis.
- **Cite only committed canon (I3).** *Test:* attempt to cite a quarantined/unaccepted span → refused/unavailable.
- **Provenance records citations (I4).** *Test:* a cited-and-accepted passage names the passages it rested on and resolves.
- **Canon untouched (I1).** Recall writes no prose; a cited render is quarantined until Accept; recall never auto-inserts prior text into the manuscript. *Test:* export byte-identical across recall/cite; recall produces no committed prose.
- **Ontology wall holds (I5).** A cite-grounded render with a style-by-reference `//voice` still refuses. *Test:* cite + `//voice like X` → refused.

## 6. Surface (ship it with W9)
- A **recall** panel: a query (or an auto-suggested query from the current scene) returns **verbatim** prior spans with their locations; each is clickable to jump to it or mark it as a citation. It never shows a generated summary — only the author's own words.
- A **cite** affordance in the block: mark recalled spans as grounding for the next render; the quarantine card shows which prior passages the render cited.
- **No auto-insertion of prior text into canon** (that would be the model deciding to repeat the author). Citation grounds a *render*; it never copies prose into the manuscript. Read-only w.r.t. canon.

## 7. THE W9 GATE — the demo that proves it
Green, live, real Groq, no manual fixup:

1. Commit several passages. **`recall`** a query → **verbatim** committed spans, ranked, each with location/provenance; assert the returned text is **byte-equal** to committed prose and no generated summary is present.
2. Recall a query matching nothing → **empty** ("nothing matches"), no fabricated synthesis.
3. Render a new passage **citing** recalled spans → it rests on them; provenance records `cited: [X, Y]`; the passage is **quarantined**, not auto-written.
4. Attempt to **cite an unaccepted/quarantined** span → refused (cite only committed canon).
5. **Ontology wall:** a cite-grounded render with a style-by-reference `//voice` still refuses.
6. **Canon untouched:** recall produces no prose; export byte-identical; the cited render commits only on Accept.
7. **Provenance:** a cited-and-accepted passage names the passages it rested on and resolves.
8. **Surface:** the recall panel shows verbatim spans with locations (no summary); the cite affordance grounds a render; no prior text is auto-inserted into canon.

If step 1's byte-equal/no-summary check or step 4's cite-only-committed check fails, W9 is not done — those are the verbatim rule and the two-memory boundary, and they are the point.

## 8. Out of scope (deferred / never)
- **Summarization / "what you established" synthesis in recall** — forbidden; a synthesis is a render, never a recall.
- **Automated contradiction / consistency detection** ("this contradicts chapter 2") — a reading like W7; edges toward emergent; deferred.
- **Cross-manuscript recall** — v1 project-scoped; cross-book recall waits on the single-author scoping question.
- **Auto-citation** — the system deciding to cite without the author; author-driven only.
- **Corpus analysis of recall/citation patterns** — log now, analyze later (data-gated).

## 9. Definition of done
- `recall` returns verbatim committed spans by relevance with no generation step; empty when nothing matches; never summarizes.
- `cite` grounds a render in committed canon only (not session material), constrained still to declared operators (I5); provenance records citations.
- Recall/cite never touch canon (I1); a cited render is quarantined until Accept; no auto-insertion of prior prose.
- pgvector index over committed passages, project-scoped, consistent with W8 versions.
- Editor surface ships (recall panel of verbatim spans, cite affordance, no summary, no auto-insert); every §7 assertion has a passing test; W1–W8 suites still green; export-leak CI still green.
- The W9 gate (§7) passes end to end.

When this holds, the original Track B triad is whole — the author can compose in their language, revise with the lineage kept, see where prose diverges from intent, and now let a passage rest on their own accepted words, with the model always retrieving what they wrote and never inventing what they meant. Merge at the checkpoint.

---
### Appendix — the one line to hold
Recall is where a writing tool most wants to be a research assistant — to hand back a tidy summary of what came before. Refuse it: the summary is the model's account of the author's book, and the author would then write against a canon that isn't theirs. Recall surfaces the author's own sentences, exactly as written, and stops. The model may point at what the author wrote; it may never tell the author what they said.

---

## Build record — how the gate was met (added after the build)

**Where the pieces live.**

| Concern | File |
| --- | --- |
| Recall, ranking, citation resolution | `backend/services/writer/recall.py` |
| Cited grounding in the prompt | `build_render_prompt(..., cited=)` in `render.py` |
| Routes | `POST /{p}/recall`; `cited` on `POST /{p}/run` |
| Surface | `frontend/src/writer/recall/` — `RecallPanel`, `CitedSpans` |
| Suite | `backend/tests/test_writer_w9.py` (37), `Recall.dom.test.jsx` (18) |
| Live gate | `scripts/writer_w9_proof.py` |

### The one substantive deviation: ranking is lexical, not pgvector

§4 specifies pgvector. **This repository has no Postgres and no text-embedding model.** The Writer is Groq-only by W1's constraint and Groq serves no embedding endpoint; the only embedding weights in the tree are FashionCLIP's — image-side, fashion-domain, 77-token limit, behind the ~2GB `requirements-ml.txt` that W1 explicitly excluded. Adding a sentence-transformer would have made the largest dependency in the Writer serve its least load-bearing part.

So ranking is **BM25 over the project's committed prose**, and the choice is narrower than it sounds: **the gate does not turn on it.** What W9 must guarantee is that what comes back is the author's own words, unaltered, or nothing — and that guarantee is independent of how the candidates were ordered. A worse ranker surfaces a less useful paragraph; it cannot surface a paragraph the author never wrote. `score_spans` is isolated exactly so a vector backend replaces it the day there is an honest text-embedding story, without touching the verbatim path. The scan is O(corpus) per query, correct at manuscript scale, and that is the point at which an ANN index earns its keep — not before.

### Three decisions the directive left open

*The recall module imports no model client, and a test enforces it by AST.* §2 says "enforce at the boundary". The strongest available boundary is that there is **nothing in the module to summarise with**: no `llm_service`, no `role_registry`, no prompt. A future edit that adds "just a short gloss" has to first add an import the suite forbids. `verbatim_violations` makes the rule checkable rather than merely intended — both the suite and the live proof run every returned span against the ledger it came from.

*Cite refuses the whole list on one bad reference.* There is no partial success that quietly drops the uncitable reference and grounds on the rest. A citation list the author cannot trust to be complete is not an audit trail.

*The prompt says "stay consistent with", never "continue" or "match the style of".* Committed prose is the author's own voice, and letting it arrive as a style reference would be a bypass of the ontology wall built out of the author's own material — the one form of style-by-reference the existing guard cannot see. The author cited those passages so the new one would not contradict them; that is what the prompt asks for and all it asks for.

### What the live gate showed (real Groq, `openai/gpt-oss-120b`)

All eight steps. Every recalled span byte-equal to its stored document across five queries; the empty query answered "Nothing in your manuscript matches that." with nothing offered in its place; a cited render quarantined with `cited: [lineage@v1]` in provenance and the export unchanged; citing an uncommitted passage refused; and a cited render under `// voice: like Tolstoy` still refused with the reference named — the ontology wall unmoved by the new grounding.

One observation worth carrying into dogfooding: the query `"she"` returned **zero** spans, because a term appearing in every passage carries no BM25 signal. That is correct behaviour and it is also a usable-ranking limitation rather than an honesty one — the kind of thing a vector backend would fix, and the reason the ranker was kept swappable.

### What was deliberately not built

No summarisation anywhere. No auto-citation. No "insert into manuscript" — copying prior prose into the book would be the model deciding to repeat the author, and the citation strip deliberately shows locations rather than prose so that nothing is sitting inline one drag from the page. No contradiction detection (§8 defers it). No cross-manuscript recall. No analysis over the recall/citation corpus.
