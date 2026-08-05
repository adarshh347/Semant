# Semant Writer — W4 BUILD DIRECTIVE (assemblage suggestion + compression)
**The Tier-2 capstone. Companion to the W1–W3 directives and
[`GROUNDING.md`](../backend/services/writer/docs/GROUNDING.md) — read those first.
Executable: build W4 only, until its gate (§8) passes. After W4, do not build Tier 3 — see §10.**

> Precondition: W3 gate green on `writer/integration` (@ `74b21f4` or later). W4 is the
> first time the system *proposes something derived from the author's usage*. That makes it
> the most honesty-delicate gate of the four, and — not coincidentally — the one where both
> of Semant's honesty modes appear at once. Read §2 before writing code.

---

## 0. Mission (one paragraph)
Since W1 the system has logged operator usage and co-occurrence; since W3 it has logged
which operators were pulled via `requires`. W4 finally *reads* that corpus. When a cluster
of operators recurs across the author's writing, the system **suggests** naming it — and the
**author authors** the assemblage into a new composite operator. That is the whole gate:
detection is analysis over real logs, naming and meaning come from the human, and nothing
enters the ontology without an explicit commit. "The language starts evolving" becomes real
here — carefully, with the human as the one who names.

## 1. What an assemblage is (v1 — decide now)
An assemblage is a **new composite operator the author authors**, distilled from a recurring
cluster:
- Same `Operator` schema, with `kind: assemblage` and a `members` field recording its
  constituent operators **with versions** as **lineage** (its ancestry — what it was
  distilled from).
- Its `rendering_intent` is **written by the author** (compressing what the cluster means to
  *them* into one intent). The system may draft a strawman, but only from the **members' own
  authored definitions** (the author's words) — never from generic priors about what such a
  cluster "should" mean. The author edits and commits.
- **Rendering an assemblage renders a single span from its own authored intent**, exactly
  like any other operator. `members` are lineage/provenance, not a live blend. This keeps
  sequential composition (one operator, one span) intact and keeps provenance clean.
- If the author wants the assemblage to also pull its members at render time, they add
  `requires` edges (W3) — explicitly, by hand. W4 does **not** auto-wire members as
  `requires`.

The *blended-field* assemblage — where the members jointly condition one fused span and "the
meaning belongs to the whole" — is the genuinely deep version, and it is **Tier 3**,
precisely because fused provenance cannot say which member produced which part of the prose.
That is the audit trail `GROUNDING.md` rests on. Do not build it here.

## 2. The two honesty modes, both present (this is the capstone's whole point)
W4 is the one gate where Semant's evidential and authorial honesty appear together, and
keeping them cleanly separated is the design:

- **The suggestion is EVIDENTIAL.** "Operators A, B, C recurred together across 7 blocks" is
  a claim that rests on **real logged evidence** — the co-occurrence and pulled-operator
  records. So the suggestion must **cite that evidence** (which blocks, how many times),
  exactly the way a mark rests on detector evidence on the vision side. A suggestion that
  cannot cite its evidence is a fabricated pattern and must not be shown. Detection is
  **analysis over logs** (frequency + co-occurrence; optional pgvector similarity over
  operator definitions per the plan's §7) — it is **not** an LLM inventing clusters.
- **The authoring is AUTHORIAL.** The name and the meaning come from the author
  (propose-accept, as `#create` already works in W1: the system drafts a candidate, the
  author edits and commits). The strawman's raw material is the members' own definitions —
  the author's ontology — so it stays grounded; it is not priors deciding what the assemblage
  means.

Say it in one line the build must honor: **the system may propose the cluster because it has
evidence; the system may not decide what the cluster means.**

## 3. Suggestion discipline
- **Threshold, not noise.** Suggest only on genuine recurrence (a documented
  frequency/co-occurrence threshold). A one-off co-occurrence is not an assemblage. Log the
  threshold so it is a tunable, visible fact, not a magic number.
- **Cite the evidence** in the suggestion (the member operators + the blocks/counts it rests
  on). No evidence shown → not shown at all.
- **Propose, never commit.** A suggestion changes nothing in the ontology. *Test:* a surfaced
  suggestion, left alone or dismissed, leaves the ontology byte-identical.
- **Respect dismissal.** A dismissed cluster does not immediately re-nag; record the
  dismissal so the suggester doesn't loop. (Re-surfacing much later on substantially more
  evidence is fine; nagging on the next render is not.)
- **The suggester reads logs; it does not write prose.** It never touches the canon and has
  no route to it — same discipline as the W3 graph. *Test:* assert the suggester calls no
  accept/scene/block path.

## 4. Authoring the assemblage
- The author supplies the **name** and the **rendering_intent** (editing the strawman, or
  writing their own). Commit is explicit.
- On commit: create the composite operator (`kind: assemblage`, `members` with versions as
  lineage, authored intent), version it like any operator, and log the authoring event to
  instrumentation.
- **Ontology wall holds by construction (I5):** members are **operator references** looked up
  in the ontology, not free text — so an assemblage can no more include "like Tolstoy" than a
  `requires` edge could in W3. *Test:* assert a corpus/style string cannot be a member.

## 5. Rendering & provenance
- `/<assemblage>` renders **one span** from its authored intent; provenance names the
  assemblage as **direct**.
- If the author added `requires` edges from the assemblage to its members, those pull at
  render time and appear in provenance marked **pulled-via-requires** (unchanged W3
  behavior).
- `members`-as-lineage is queryable (what was this distilled from?) but is **not** itself a
  render input — lineage records ancestry, it does not silently condition the prose. *Test:*
  an assemblage with lineage but no `requires` edges renders from its own intent only;
  provenance shows the assemblage direct and does not list the members as render inputs.

## 6. What NOT to build (out of scope — most of this is Tier 3)
- **Blended-field assemblage rendering** (members jointly conditioning one fused span) —
  Tier 3.
- **Auto-committed assemblages** (no human naming) — violates propose-not-commit; never.
- **Auto-discovered higher-order operators / operator evolution / auto-mutating definitions**
  — Tier 3.
- **Cross-project assemblages / the semantic genome** — Tier 3; W4 stays project-scoped.
- **Narrative physics / fields / cognitive layers** — Tier 3 metaphors; not buildable until
  operationalized into a measurable (see §10).

## 7. Notes
- Backend: the assemblage is an operator, so reuse the operator registry and `writerService`;
  add read/write only for the suggestion feed and assemblage commit. No new write path to the
  canon.
- This is where **pgvector** (plan §7) may finally earn its place — semantic similarity over
  operator definitions to strengthen cluster detection beyond raw co-occurrence. Optional,
  additive; if used, it informs *detection*, never *meaning*.
- Instrumentation keeps logging (assemblage suggested / dismissed / authored, and assemblage
  usage). That log is the seed corpus for any future Tier-3 work — see §10.

## 8. THE W4 GATE — the demo that proves it
W4 is done when this runs green, live, no manual fixup:

1. Accrue co-occurrence so a cluster (e.g. `interiority` + `threshold` + `hush`) recurs above
   the threshold — via a scripted session over the fixture, or seeded logs.
2. The system surfaces a **suggestion** that **cites its evidence** (the members + the
   blocks/counts). Assert the cited evidence corresponds to real logged records, and that
   **no ontology change has occurred**.
3. **Dismiss** it; assert the ontology is byte-identical and it does not immediately re-nag.
4. Trigger the suggestion again; **author** the assemblage — accept a name, edit the strawman
   `rendering_intent`, commit. Assert a new operator exists with `kind: assemblage`, `members`
   recorded with versions as lineage, and the **author's** intent stored. Assert the strawman
   was synthesized from the members' definitions, not generic text.
5. Attempt to author an assemblage with a **corpus string as a member**; assert rejection
   (members are operator refs; I5 by construction).
6. Render `/<assemblage>`; assert **one span** from its authored intent, provenance names the
   assemblage **direct**, and (with no `requires` edges) the members are **not** listed as
   render inputs — lineage ≠ live blend.
7. Add a `requires` edge from the assemblage to one member; render again; assert that member
   now pulls and shows **pulled-via-requires** (W3 consistency).
8. Across all of the above, **export the manuscript and assert it is byte-identical** —
   assemblage authoring is ontology, never canon (I1/I3).

If step 2's cite-the-evidence check or step 6's lineage-is-not-a-render-input check fails, W4
is not done — those are the evidential-honesty and sequential-composition boundaries, and
they are the point of the capstone.

## 9. Definition of done
- Cluster detection over the real logs with a documented, tunable threshold; suggestions cite
  evidence; suggester has no route to the canon.
- Assemblage = authored composite operator (`kind: assemblage`, versioned `members` as
  lineage, author-written intent); propose-accept enforced; members are operator refs (I5).
- Single-span rendering from authored intent; provenance direct; lineage is not a silent
  render input; `requires` still works if the author adds it.
- Every §8 assertion has a passing test; W1–W3 suites still green; export-leak CI still green
  on `writer/integration`.
- No Tier-3 work; project-scoped; canon untouched by any assemblage activity.

When this holds, **Tier 2 is complete** — merge at the checkpoint. From here the work changes
character (see §10).

## 10. After W4 — the instrument-and-wait posture (read before asking "what's next")
There is no W5. Tier 3 (narrative physics, narrative fields, cognitive layers, operator
evolution, auto-discovered higher-order operators, the semantic genome) is **emergent and
data-gated by construction** — none of it can be discovered until an author has used the
system for real, for months, and a genuine corpus exists. Building any of it speculatively
now would be the one dishonest thing in the whole plan.

So the posture after W4 is deliberate patience:
- **Keep the instrumentation running.** It has been accruing since W1; that log *is* the
  Tier-3 dataset.
- **Use the system as an author** (dogfood it) so the corpus is real writing, not synthetic.
- **A Tier-3 feature becomes buildable only when two things are true:** (a) the metaphor has
  been turned into a concrete *measurable* over the log, and (b) there is enough real usage
  that the measurable shows a stable signal. Until both hold, it stays a metaphor, and
  metaphors don't get committed.
- **The next artifact is not a directive — it's an analysis.** When you want to move on
  Tier 3, the right first step is to read the accumulated instrumentation and ask what real,
  recurring structure it actually shows. That analysis, grounded in the corpus, is what tells
  you which (if any) Tier-3 idea has become engineering. Ask for that when the logs are rich;
  don't ask for a W5.

---
### Appendix — why the capstone is the pattern in miniature
W4 is Semant's whole thesis compressed into one gate: the system earns the right to speak by
pointing at real evidence (the co-occurrence it logged), and then stops — it does not get to
say what the evidence *means*. The author does. Get that division right and the system becomes
a collaborator that notices patterns in your language and hands them back for you to name;
blur it, and it becomes a tool that decides what your recurring images mean on your behalf,
which is exactly the fabrication the whole project exists to refuse. Detection rests on
evidence; meaning stays authorial; the canon stays untouched. That is the entire discipline,
one last time.
