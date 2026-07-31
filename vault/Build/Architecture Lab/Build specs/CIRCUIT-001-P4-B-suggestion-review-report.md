# CIRCUIT-001 P4-B — Suggestion Review UX report

**Production-intent. Executed.** Reviewing model output is now fast, editable, and honest: a
review surface that cycles suggestions one at a time, edit-before-accept (Label Studio), the SAM
preview on the suggestion layer, and bulk semantics where **accept-all is a rhythm, never a silent
batch**. Built in an isolated worktree against Lane A4's landed modules; nothing A4 owns was
modified.

| | |
|---|---|
| **id** | CIRCUIT-001 P4-B · the review UX on P3-A circulation + P3-B instruments |
| **worktree** | `../semant-p4-review` · branch `feat/circuit-p4-review` · base `bf42bef` (origin/main, with #68 P3-A + #69 P3-B merged) |
| **dependency** | **none added** — no konva, no fabric, no tldraw |
| **tests** | **682 green** (was 662 at base; +20 across 2 files) · production build clean · lint clean |
| **verified live** | offline harness `/lab/differential` with a **20-suggestion fixture batch** — reviewed, edited two (role + label), accepted five, dismissed the rest; JS-verified every transition |
| **contract** | v2 (A4's v3 had not landed on main at branch time — checked; drove everything with `fixture`-source suggestions, the P3-B idiom) |

The rule this gate serves: **acceptance must stay a decision** — fast, never automatic.

---

## 1. The review surface (2a)

A new **`SuggestionReview`** inspector section (no new panel framework) replaces the flat
one-at-a-time Accept/Dismiss list. When the model proposes marks, the quarantine header shows the
count and a **Review N** button (a lone suggestion still gets quick Accept/Dismiss inline). Entering
review opens the surface:

- **one suggestion at a time, reviewed IN ORDER** — a position badge (`3 / 20`), `‹ ›` and keyboard
  **n / p** to cycle (wrap-around), **a** accept, **d** dismiss, **Esc** leave. Review keys take
  precedence over the tool shortcuts while reviewing (but yield to the reshape handles when a
  geometry edit is open).
- each row shows **`markDisplay`'s honest descriptor** — provenance label, `status_label`
  (“Suggested mark”), `role_label`, the **producer** (`provenance.model`), and citability
  (“not yet citable”). A decision is never made blind.

Keyboard verified live: `1/20 →(n,n) 3/20 →(p) 2/20 →(a) 2/19` — accept drops the suggestion from
the queue and lands on the next.

## 2. Edit-before-accept (2b) — the Label Studio pattern, live

A suggestion can be **edited before acceptance** and the original is preserved un-edited in lineage:

- **role** via the mark-family role picker (`ROLE_VOCABULARY[type]`), **label** via an input, and
  **geometry** via the existing stage handles — a special `__suggestion__` edit target whose
  `keepEdit` STAGES the points into `review.edit` rather than committing to a ground. Editing a
  field-of-strokes offers no shape handles (honest — strokes are not point-editable).
- accept calls Lane A4's **`acceptSuggestion(suggestion, edits)`**, which mints a NEW
  `user_confirmed` mark carrying the edits, `derived_from` the suggestion, `status: committed`. The
  suggestion is returned **byte-identical** (proven: `structuredClone` deep-equal, input un-mutated).
- **Why the edits keep the geometry KIND:** `acceptSuggestion` promotes to `model_refined` (which
  `canCiteMark` rejects) only when a geometry edit CHANGES the kind. Role/label/same-kind-point edits
  stay `user_confirmed` and **citable** — so editing to improve a mark never quietly makes it
  uncitable. The surface’s “Edited — accepting mints **your** version, with the model’s proposal
  preserved in lineage” note makes this legible. A kind-change → `model_refined` is covered by test
  as the documented boundary.

## 3. SAM prompting on the suggestion layer (2c)

The refine flow’s ~70%-built plumbing (foreground/background point prompts via
`addPoint(x, y, label)` where `1`=fg/`0`=bg; box via `setBoxPrompt`; correction round = add/remove
points, auto re-preview; `confirm()` persists) is unchanged — **no change to the service call**. The
one UI move: the mask **preview no longer rides RegionOverlay’s ad-hoc `rs-proposal`**. It renders on
the **suggestion layer** as a distinct dashed teal mask (`RefineProposalGhost`), visibly the model’s
and uncitable, gated on the suggestion layer’s visibility control (P3-B 2d). RegionOverlay keeps only
the fg/bg point + box PROMPT. Correction happens under the preview; Accept persists via the existing
`confirmRefine` (which already mints a `region_mask` with lineage, P3-B Debt 3).

## 4. Bulk honesty (2d) — the load-bearing rule

**Accept-all is deliberately NOT a button.** There is no function anywhere — not in the quarantine
(`acceptAll`/`acceptSuggestions` are `undefined`), not in the workspace, not in the surface — that
commits more than one suggestion per call. `acceptSuggestion` mints exactly one; the workspace’s
`acceptCurrentSuggestion` accepts exactly the current one and advances. **Accepting many is the
a-rhythm: one press, one glance, per mark** — the surface says so (“Accept all = press **a** through
each — a glance per mark”). This is the whole point: a silent accept-all launders a batch and trains
the blind acceptance the quarantine exists to prevent.

**Dismiss-all IS one button** — refusal needs no ceremony. A **dismiss reason** (wrong place / not
real / duplicate / too coarse) is one optional keystroke, skippable, recorded when given.

Live-verified on the 20-batch: 5 accepted (2 edited), 15 dismissed via the one button, review exited
clean — `0 parts · 5 grounds · 0 percepts` (the accepted field suggestions promoted to grounds).

## 5. Provenance in review (2e)

Every review row carries `summarizeProvenance` (“Model suggestion — not accepted”) + producer +
citability, via `markDisplay`. After accept, the committed mark’s lineage is visible on its ground’s
inspector chip (the existing `hasModelInvolvement`/`summarizeProvenance` surface). Cross-reload
run-linked provenance is A4’s territory: the mark provenance shape has a `run_id` slot but
`validateMark` still **rejects** a non-null `run_id` (no causal run claims yet), so review shows
**fixture provenance** (`planner-x`) — the honest state until A4’s producers land. (See P4F.)

## 6. Tests (+20, total 682)

- **`p4Review.test.js`** — edit-before-accept lineage (edits ride into a citable `user_confirmed`
  derived mark; suggestion byte-identical; kind-change → uncitable `model_refined` boundary);
  **no batch-accept exists** (quarantine + workspace + surface grep-proof; two accepts → two distinct
  marks); dismissed → dismissed/uncitable/unpersisted/dropped-from-pending; `markDisplay` provenance
  descriptor; review-keyboard + `__suggestion__` staging + SAM-ghost routing + P4F wiring guards.
- **`suggestionReview.dom.test.jsx`** — the surface renders the honest descriptor (2e); role/label
  stage via callbacks; “Adjust shape” shows only for editable geometry; the edited note; accept /
  dismiss / next / prev fire; **a Dismiss-all button but NO accept-all control** (2d); optional reason
  chips. Plus `RefineProposalGhost` renders a distinct dashed mask from polygons and nothing without a
  proposal (2c).

Full suite **682 green**; production build clean; lint clean.

## 7. Live verification (offline harness)

`/lab/differential` seeds a **20-suggestion fixture batch** (10 trace + 10 brush, varied roles).
Exercised end-to-end; every state transition JS-verified.

| # | screenshot | shows |
|---|---|---|
| 01 | `01-batch-entry-20.jpg` | “MODEL SUGGESTIONS · 20” + **Review 20** button; the suggestion ghosts on the stage |
| 02 | `02-review-surface.jpg` | the review surface **1 / 20**: provenance chip, role_label · producer · citability, the role picker, label, Adjust shape, ‹ Accept Dismiss ›, reason chips, and the bulk row |
| 03 | `03-edit-before-accept.jpg` | an **edited** suggestion (2 / 19): the staged role, and the honesty note “accepting mints **your** version… preserved in lineage” |

Verified transitions (JS): keyboard cycle `n/p`; accept advances and drops from queue; edit stages
role + label; 5 accepts (2 edited) + Dismiss-all(15) → review exits clean, 0 pending, 5 grounds. The
Chrome extension disconnected before a final console snapshot; no errors surfaced during the run and
the earlier session on this harness was console-clean. Build + full suite are green.

## 8. `// P4F:` markers

| where | gap | what P4F (or Lane A4) should do |
|---|---|---|
| `DifferentialWorkspace.jsx` `dismissCurrentSuggestion` | `dismissSuggestion` takes **no reason param** | the dismiss reason currently rides as an additive session field (`dismiss_reason`) on the dismissed (non-persisted) mark. When A4 adds `dismissSuggestion(suggestion, { reason })` (or a reason field on the mark), route through it so a dismissal’s reason is first-class and can inform the producer. |
| provenance in review | run-linked provenance not live | `validateMark` still rejects a non-null `run_id`. When A4 lands run-linked provenance, the review row’s producer/provenance should read the run identity, and the post-accept inspector should show it across reload (verify against reload then). |
| ground-provenance chip | the workspace re-derives it locally | P3-A added `store.groundProvenance(groundOrId)`; a later gate could route the ground inspector chip through it rather than re-deriving (noted by A3 too). Not blocking. |

## 9. Ownership & parallel safety

Modified only owned files: `DifferentialWorkspace.jsx` (+css), `SuggestionReview.jsx` (new),
`pages/DifferentialLab.jsx` (dev harness), and tests. **Not touched:** `visualMarks.js`,
`suggestionQuarantine.js`, `markStaging.js`, `regionStore.js`, `useMaskRefine.js` (service side),
`recall.js`, blocknote/*, backend/, the contract doc — all called at their origin/main signatures.
Lane A4’s producer PR runs in parallel; if it collides on the Differential surface a small **P4F
reconcile** in the main tree resolves it (the shape of every prior lane merge).
</content>
