# CIRCUIT-001 · P2C-MS — Manuscript as a Multimodal Field

**Gate kind:** product architecture (design-first, one bounded code slice)
**Status:** design complete · first slice implemented (Passage Inspector, read-only)
**Depends on:** P0.5 (Chiasmatic Network) · P1 (circuit spec) · P1 addendum (percept/ground depth) · P1B (handoff) · P1C (Percept Packet) · P1D (Circulation Thread) · P2 (Seeing Console) · P2B (Perceptual Action Grammar)
**Sibling doc:** `CIRCUIT-001-P2C-OS-orchestration-session.md`
**Parallel track:** `CIRCUIT-001-P2C-OH-open-harvest-perceptual-instruments.md` (renderer mechanics)

---

## 0. The sentence this gate exists to make false

> *"The Manuscript is where you write about the image."*

That sentence describes a text box next to a picture. It is what the Manuscript is today, and it is why P2 closed with the observation that **the crossing is one-directional**: a percept can be carried into the writing, and the writing cannot answer back in the same register.

Differential made perception **manipulable** — grounds are cited, roles are named, marks are armed, acts are proposed and refusable.

The Manuscript must make language **perceptually accountable and generative**:

- **accountable** — a sentence can be asked what it rests on, and can answer honestly, including *"nothing"*.
- **generative** — a sentence can act back on the image: become a percept, arm a mark, request a counter-reading.

The Manuscript is not a document that *mentions* the circuit. It is a **surface of the circuit**, on equal footing with the Field.

### 0.1 What "multimodal" means here, precisely

Not "you can paste images into the editor." Every image editor does that and none of them make writing accountable.

It means: **the objects of perception and the objects of language occupy one field and can manipulate one another.** A percept chip is not an illustration of a sentence; it is a citation the sentence can be interrogated through. A sentence is not a caption on a mark; it is a thing a mark can be made *from*.

The load-bearing asymmetry to preserve: **prose is the curator's. Perception is cited.** The Manuscript never generates the curator's sentence for them without asking, and never claims a sentence is supported when it is not.

### 0.2 Inherited law (not re-litigated here)

Everything below is subordinate to rules already paid for in earlier gates:

| Law | Origin |
|---|---|
| Nothing enters the circuit without saying where it came from; nothing leaves without being able to return | P0.5 §1.2 |
| **Record vs judgement** must render in visibly different voices | P1D |
| **Absent ≠ none ≠ nominal** — unknown is stated, never assumed healthy | P1C |
| **Degradation-only display** — nothing renders when evidence is healthy | P1 |
| **Never assert a cause** — *"no longer resolves"*, never *"was replaced by"* | P1 |
| **A model may never author a challenge** | P2B |
| **Arming is not drawing**; nothing is written by arming | P2B |
| **A UI must never silently no-op** — a dead Apply is worse than no Apply | P2B |
| **Derived, never flagged** — a stored flag acquires a truth that can disagree with the circuit | P1B |
| **Vocabularies are candidates, not taxonomies** — optional everywhere, retirable | P1 addendum |
| The handoff **carries, it does not endorse** | P1B §A.6 |

---

## 1. Manuscript objects — the field's inhabitants

Today the Manuscript has exactly three object kinds: **text**, the `regionRef` inline chip, and the `partRef` block. Provenance lives in a side-channel `metaRef` keyed by block id, because BlockNote's default schema strips unknown props.

The object model below is the target. **Only the first four rows exist today.** Naming a row is not scheduling it — the point of writing the whole model now is that each new object arrives into a shape already designed to be cited, degraded, and returned from, rather than being bolted on as a special case.

### 1.1 The catalogue

| # | Object | Exists? | Carrier | What it is | Can be cited by | Can act on |
|---|---|---|---|---|---|---|
| 1 | **plain text** | ✅ | BlockNote inline text | The curator's prose. The default and the privileged case. | — | everything |
| 2 | **sentence / selection** | ⚠️ derived | live DOM/editor selection | *Not stored.* A transient addressable span. The unit that asks and acts. | — | image, percept, model |
| 3 | **paragraph / passage** | ✅ | `text_blocks[]` entry, `id` + `content` HTML + `origin` + `color` | The stored unit. Already carries `origin` provenance. | mentions | image, percept, model |
| 4 | **percept chip** | ✅ | inline `regionRef` (`refKind: 'percept'`) with `data-percept-id`, `data-mention-id`, `data-region-ids` | A living citation. Recall plays from it. | — | image (recall), Differential |
| 5 | **ground reference** | ❌ | inline `regionRef` (`refKind: 'ground'`) | Cite a *piece of evidence* directly, not a whole noticing. Needed when prose is about a fold, not about a reading of a fold. | percept | image |
| 6 | **field reference** | ❌ | inline, `field_role` carried | Cite a brushed atmosphere/light/pressure field. A `brush_field` mark once committed (P2C-OH `visual_mark`). | percept | image |
| 7 | **trace reference** | ❌ | inline, `trace_role` carried | Cite a directional mark — gaze address, architectural axis, fall of light. | percept | image |
| 8 | **relation reference** | ❌ | inline, `relation_role` carried | Cite a relation *between* marks (similarity, contrast, tension). Geometry derived, **never stored** (P2C-OH rule). | percept | image |
| 9 | **model draft** | ⚠️ partial | block `origin: 'sutradhar'` in the meta side-channel; **unstyled** | Model-produced prose. Today it is structurally recorded and visually indistinguishable from the curator's own sentence. §4 fixes this. | — | — (must be accepted first) |
| 10 | **external claim** | ❌ | inline span, `data-claim="external"` | A statement the frame cannot settle — an identity, a date, an attribution. Marked, **not forbidden** (P1C `mark_external_claims`). | — | — |
| 11 | **action block** | ❌ | block, holding a `perceptualActions` action object | A staged act living *in the writing*: armed, previewed, never auto-applied. | — | image, percept, model |
| 12 | **recall target** | ⚠️ derived | derived from a percept chip's `perceptId` | The addressable "play this back on the image" affordance. Exists as behaviour, not as an object. | — | image |

### 1.2 Three structural rules for the catalogue

**R1 — Every reference object is one inline kind, discriminated by `refKind`.**
Rows 4–8 are the *same* carrier with different `refKind` values and different resolvable id namespaces (`pctx_`, `gnd_`, `vm_`). This is deliberate: one parse path, one round-trip test, one degradation path. Adding a new citable object must not add a new markup shape.

**R2 — A reference stores an id and a label, never a copy of what it points at.**
The chip carries `data-label` for the case where the target is gone — so a detached citation still *reads*, while reporting that it no longer resolves. It must never carry the target's geometry, expression, or role, because a copy is a second truth that can silently disagree.

**R3 — Provenance must migrate out of the side-channel.**
`metaRef` (a `Map` keyed by block id, restored on serialise) is a known fragility: it survives serialisation but not a block-id change, and it cannot address anything smaller than a block. Rows 9 and 10 need **inline-level** origin. This is a precondition for §4, not a nicety.

---

## 2. Sentence as action source

A sentence is the smallest unit a curator actually commits to. It should be able to answer eight questions. **Each answer must distinguish record from judgement, and must be able to say "not assessed."**

| # | The question | Answer kind | Derivable today? | Derived from |
|---|---|---|---|---|
| 1 | **What do I cite?** | record | ✅ | chips inside the selection range → `mentionsFromBlocks` / live inline content |
| 2 | **What percepts support me?** | record | ✅ | `perceptId` on each cited chip → `store.percepts` |
| 3 | **What grounds / fields / traces do I rely on?** | record | ✅ (grounds only) | percept `ground_ids` → `post.grounds`; fields/traces await rows 6–7 |
| 4 | **What here is external?** | **judgement** | ❌ | needs row 10. Until then the honest answer is **`external claims not assessed`** (P1D's exact phrase) |
| 5 | **What is unsupported?** | **judgement** | ⚠️ weak | a sentence with zero chips cites nothing — that is a *record*. Calling it "unsupported" is a *judgement* and is only sound once row 10 exists |
| 6 | **What should be recalled on the image?** | record | ✅ | the percept chips in range, in document order |
| 7 | **Should I become a percept?** | proposal | ✅ (preview) | `compose_percept` seeded with the sentence **verbatim** — P2B's rule |
| 8 | **Should I return to Differential?** | proposal | ✅ (preview) | `send_sentence_to_differential` |

### 2.1 The trap this table exists to avoid

The tempting design is a green tick on supported sentences and a red flag on unsupported ones. **This must not be built.** Reasons, in order of severity:

1. **It inverts degradation-only display.** P1's rule is that a healthy state renders *nothing*. Nine badges per paragraph is how honesty stops being read.
2. **"Unsupported" is not a fact the system possesses.** A sentence with no chip may be perfectly grounded in a curator's looking and simply uncited. The system knows *"cites nothing"*. It does not know *"rests on nothing."* Rendering the second when it knows only the first is exactly the fake causality P1 forbids.
3. **It would make citation performative.** A curator who is scored on citations will cite to clear the score, and the mention graph stops recording where attention actually went.

The sanctioned rendering: **the inspector answers when asked**, and volunteers only a real degradation (a cited percept whose grounds no longer resolve). Silence means *not asked*, never *verified*.

### 2.2 Selection is transient and must stay transient

A selection is not persisted, is not a Mention, and gets no id. It is assembled on focus and discarded. The moment a selection acquires storage it becomes a competing citation model beside Mentions, and P0-open-decisions §4 has not yet decided even whether *Mentions* should be durable — the corpus still has **0 text blocks**, so there is no evidence yet of how curators actually cite.

---

## 3. Percept chip as living citation

Today the chip does two things: it lights when its percept is being recalled, and clicking it emits `semant:region-focus`, which `PostDetailPage` routes to `playRecall`. Everything the Percept Workshop knows about that percept — roles, evidence state, packet, thread — is unreachable from the writing.

The chip should open into a panel with this exact order. **The order is the argument**: what it says, then what it rests on, then what is wrong *only if something is*, then where it lives, then what can be done.

| Section | Content | Voice | Source | Show when |
|---|---|---|---|---|
| **expression** | the percept's sentence | record | `percept.expression` | always |
| **cited grounds** | count + label list, in citation order | record | `groundRoleList(percept, grounds, resolve)` | always (incl. *"cites no grounds"*) |
| **ground roles** | role per ground; `counterforce` visually distinct | record | `ground_roles` map (P1C) | only when roles are named |
| **evidence / degradation** | *"none of the 2 cited grounds still resolves"* | **judgement** | `packet.evidence` | **only when degraded or unknown** |
| **manuscript mentions** | *"in the writing · N passages"* | record | derived from mentions, never a flag | always |
| **recall** | *"recalled 2× this session"* — and it must say *this session* | record | session-local counter | when > 0 |
| **packet preview** | the packet as it would be asked, incl. `dispatch: {sent:false}` | record | `buildPerceptPacket` | on disclosure |
| **circulation thread** | records then judgements, labelled | both | `buildCirculationThread` | on disclosure |

### 3.1 Chip actions

| Action | Wired today | Behaviour |
|---|---|---|
| **recall image** | ✅ | `playRecall(perceptId)` — already the click behaviour |
| **revise in Differential** | ⚠️ | leave Manuscript, focus this percept in the Workshop. The **return leg** of P1B's crossing, and the single most valuable unbuilt affordance in this gate |
| **challenge support** | preview | `challenge_percept`. **`source` must be `user`** — P2B refuses a model-authored challenge outright |
| **start passage** | preview | `start_manuscript`, `cited_percept_refs: [id]`, `insertion_mode: 'unsaved'` |
| **compare** | preview | `compare_passage` — requires a **grain** (spark-10: `abstraction-as-immunisation`) |
| **show packet** | ✅ (in Workshop) | disclose the packet, unsent |

### 3.2 The chip must not become a percept editor

Editing the expression from the writing would let a sentence's citation silently change under it. Revision belongs in Differential, where the grounds are visible. The chip's job is to **open**, not to **own**.

---

## 4. Model draft as a distinct origin

This is the gate's sharpest requirement, and today's state is a live hazard: `aiSlashItems` seeds a block with `props: { origin: 'sutradhar' }`, the meta side-channel preserves it through serialisation — and **`.text-block-item[data-origin]` has no styling**. A model-written passage currently reads as the curator's own sentence.

### 4.1 Requirements

1. **Origin styling.** Visually distinct, and **quiet** — P2B's rule: *"a mark of authorship, not a warning badge."* The distinction is **who wrote this**, never **is this true**. A model's sentence is not labelled false; Semant has no calibrated basis for that.
2. **Accept / revise / dismiss.** Three explicit outcomes. **Accept must rewrite `origin` from `sutradhar` to a value that records the lineage** — the P2C-OH borrowing from Label Studio: `user_confirmed` should be a *derived fact from a parent link*, not a flag someone must remember to set. Proposed carrier: `origin: 'human'` + `derived_from: <draft_id>`.
3. **Visible source context.** What the draft was given: the percept ids, the ground ids, the prompt excerpt, the constraint set. If the draft was produced without seeing the image, that must be stated — a model that read only text must not appear to have looked.
4. **Used percepts / grounds, if available.** Only if the generator reported them. If it did not, the honest field is **absent**, not empty — *"sources not reported"*, never an empty list implying none were used.
5. **Unsupported / external-claim flags, if known.** Same rule: `null` ≠ `[]`.
6. **No autosave without confirmation.** Already true structurally (block edits are local until Save/Ctrl+S) and must survive: a model draft must never enter `text_blocks` on a timer.

### 4.2 The quarantine, restated for prose

P2C-OH's Workflow G puts model marks on a `suggestion` layer: never counted in evidence totals, never citable by a percept, never recallable. **The prose equivalent:** an unaccepted model draft must not be counted in `mention_count`, must not satisfy *"in the writing"*, and must not appear in a packet's `manuscript.context`. Otherwise a model's own sentence becomes evidence that the percept was committed to — the circuit citing itself.

---

## 5. Visual reference in text — the object model

Rows 5–8 of §1.1 in one shape. Design now, build later; the point is that they arrive as one kind.

```jsonc
// inline reference — the single citable carrier
{
  "ref_kind": "percept | ground | field | trace | relation | collection",
  "ref_id":   "pctx_… | gnd_… | vm_… | col_…",
  "label":    "the upper head",       // for reading when the target is gone (R2)
  "mention_id": "men_…",              // the edge, when one is recorded
  "role": null,                        // field_role | trace_role | relation_role, when the kind carries one
  "resolves": null                     // null = NOT ASSESSED. never defaulted to true
}
```

- **`resolves: null` is the whole discipline in one field.** `resolveGround` knows only that an id does not resolve; without a resolver in context the answer is *unknown*, exactly as `buildPerceptPacket` refuses to report `'intact'` without one.
- **`role` is a property of the citation, not of the target.** P1C's hardest-won rule: the same ground is an anchor in one noticing and a counterforce in another. Writing a role onto the target means the last curator to speak wins.
- **`collection`** is named for completeness (Atlas's future comparative set) and is explicitly the least-designed row.

---

## 6. Return path to Differential

P1B built the outbound leg — percept → chip → recall, at-most-once, through the same `insertRef` path as `/percept`. The return leg does not exist. **This is the gate's most important structural finding**: the circuit's governing rule is that nothing may leave without being able to return, and the writing currently cannot return anything.

Six return actions, all **staged**, none auto-applied:

| Action | Carries | Lands as | Notes |
|---|---|---|---|
| **map this sentence** | selection text | `map_sentence_to_image` | proposes *where to look*, never derives geometry — the planner has no access to the image |
| **brush this phrase** | phrase + inferred `field_role` | `brush_field` (armed) | arming only; the mark is the curator's hand |
| **trace this relation** | phrase + `trace_role` | `trace_direction` (armed) | same |
| **create percept from this sentence** | selection **verbatim** | `compose_percept` | P2B: seed with the curator's own words, never a paraphrase |
| **revise cited percept** | `percept_id` | focus in Workshop | the chip's return leg (§3.1) |
| **ask for counter-reading** | `percept_id` + grain | `challenge_percept` | **`source: 'user'` always.** A model may not author this |

**The arming contract carries over unchanged.** A returned action switches the tool and holds the role/label in `stagedMark`. Leaving the tool abandons it. Nothing is written. The stage says so.

---

## 7. Embedded action types

The thirteen actions this gate names. Six map onto P2B's existing nine; seven are new and **must be added to `ACTION_TYPES` with specs before any of them renders an Apply button** — `normalizeAction` returns `null` for an unknown type, which is the correct failure and would make them silently invisible.

| Action | Target | P2B status | Maps to |
|---|---|---|---|
| `insert_percept_chip` | manuscript | ⚠️ exists as behaviour, not as an action | P1B handoff / `/percept` |
| `recall_percept` | image | ⚠️ exists as behaviour | `playRecall` |
| `map_sentence_to_image` | image | **new** | — |
| `create_percept_from_sentence` | percept | **new** | thin wrapper on `compose_percept` |
| `challenge_sentence` | percept | **new** | sibling of `challenge_percept` |
| `extract_claims` | manuscript | **new** | precondition for §1.1 row 10 |
| `mark_external_claim` | manuscript | **new** | writes row 10 |
| `draft_description` | manuscript | ✅ | `start_manuscript` · `mode: description` |
| `draft_critique` | manuscript | ✅ | `mode: art_critique` |
| `draft_philosophical_note` | manuscript | ✅ | `mode: philosophical_note` |
| `draft_script` | manuscript | ✅ | `mode: youtube_script` |
| `revise_with_percepts` | manuscript | **new** | — |
| `send_sentence_to_differential` | image | **new** | — |
| `compare_passage` | manuscript | **new** | must require a **grain** |

### 7.1 Staging law

**Every action above is staged and previewed before mutation. Without exception.**

Three P2B rules are load-bearing here and are restated because this gate's actions are the first that originate *in prose*, where a curator is in a flow state and least likely to read a dialog:

1. **`normalizeAction` returns `null`, never a partial object.** A half-valid action rendered as a card is precisely the failure the grammar exists to prevent.
2. **`requiresConfirmation` is set by the spec, never by the caller.** A Manuscript surface must not be able to declare its own action safe.
3. **No dead Apply.** An action without an executor renders *"Preview only — execution path not wired yet"* and no button. An Apply that quietly does nothing teaches the curator that the whole panel is theatre.

Additionally, from P2B's dispatch discipline: any of these actions asserting `payload.dispatch.sent === true` must be **refused, not corrected** — silently resetting the flag is how a dispatch happens.

---

## 8. What this gate built

**One slice: the Passage Inspector, read-only.** See `CIRCUIT-001-P2C-MS-report.md` for files, tests, and verification.

It answers §2's questions 1, 2, 3, 6 (records, all derivable today), reports §2 q4/q5 as **not assessed**, opens §3's chip panel down to the packet, and renders §6/§7's actions as **preview-only cards with no Apply**.

It does not: persist anything, call any model, create a Mention, alter the editor schema, or touch the `/percept` slash flow or the P1B handoff.

## 9. What remains unbuilt

Ordered by what unblocks the most.

1. **Inline provenance** (§1.2 R3) — precondition for §4 and for rows 9–10. The `metaRef` side-channel cannot address below a block.
2. **Model draft styling + accept/revise/dismiss** (§4) — the live hazard: `origin: 'sutradhar'` is already written and already invisible.
3. **The return leg** (§6) — "revise in Differential" from a chip. Smallest useful piece of the circuit's governing rule.
4. **Seven new action types** (§7) with specs, validators, and warnings.
5. **Rows 5–8** — ground/field/trace/relation references. Blocked on P2C-OH's `visual_mark` module landing.
6. **`extract_claims` / `mark_external_claim`** — until these exist, §2 q4 and q5 must keep answering *not assessed*, and must not be softened into a green tick.
7. **Durable Mentions** — still branch (b) of `P0-open-decisions` §4, and correctly still deferred: the corpus has 0 text blocks, so there is no evidence of how curators cite.

---

*The Manuscript stops being a place where the image is described, and becomes a place where the image can be argued with — and can argue back.*
