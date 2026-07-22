# CIRCUIT-001 · P2C-OS — The Orchestration Session

**Gate kind:** architecture (design + one pure module, no dispatch)
**Status:** design complete · `orchestrationSession.js` implemented, assembly only
**Sibling doc:** `CIRCUIT-001-P2C-MS-manuscript-multimodal-field.md`
**Depends on:** P1C (Percept Packet) · P1D (Circulation Thread) · P1E (dispatch deferred, conditional GO) · P2B (Perceptual Action Grammar)

---

## 0. The name, and what it refuses

**Orchestration Session** — adopted.

It inherits from **Perceptive Orchestration**, already defined in P0.5 as *"the layer at which a percept becomes an operation packet"* and explicitly *"a packing rule — not an agent, not a pipeline, not a queue, and not a place to put intelligence."* The Session is the same discipline widened from one percept to the whole current circuit.

Alternates considered and why they were not taken:

| Name | Why not |
|---|---|
| *Session Mind* / *Working Mind* / *Studio Mind* | "Mind" imputes an interior. A context object has no interior; it is assembled, read once, and discarded. Naming it a mind is how a context object becomes an agent by drift. |
| *Perceptual Session* | It has not perceived anything. It carries records of what the **curator** perceived. The planner's rule holds: *say what you said, never what it saw.* |
| *Chiasmatic Session* | Accurate and the strongest runner-up, but "chiasm" already names the writing-side shell in code. Reusing it would make two different things share one word. |

**What the Session explicitly is not:**

- **Not an agent.** It has no loop, no goals, no memory across posts, and cannot call anything.
- **Not persistent memory.** Working context for the current post and surface. Assembled on demand, thrown away. There is no `orchestration_sessions` collection and this gate does not propose one.
- **Not a mutation path.** It holds *proposals*. Applying one goes through `perceptualActions`' validators and the curator's hand.
- **Not a prompt.** A prompt is prose someone can quietly edit. This is data, so the discipline travels with the request — the same reason `buildPerceptPacket` carries `constraints` as fields (P1C).

> **The model mind is not an autonomous ghost. It is a session-shaped witness to the current image-writing circuit.**
> It may suggest. Semant shapes. The user confirms. Only then does an action enter the circuit.

---

## 1. Why this must exist before any model call

P1D deferred dispatch with a conditional GO for a precise reason: *"dispatch turns an inspectable request into a recorded event, and the circuit cannot yet record events."* `no model reading recorded` is currently a **record** — a true fact about our ledger. It *"becomes a lie the moment a packet is sent."*

The Percept Packet (P1C) solved this for **one percept**. But the interesting model questions are not about one percept in isolation:

- *"Does this passage overreach what its cited grounds show?"* — needs prose **and** grounds.
- *"What have I not looked at?"* — needs marks, run memory, and the captivation prompt.
- *"Give me a counter-reading of this sentence."* — needs the selection, the percept it cites, and its evidence state.

None of these is expressible as a percept packet. The Session is the object that makes them expressible **without** letting a model reach for whatever it likes. It is the boring half again: the packing rule, built and inspectable long before anything is dispatched, and — the rehearsal programme's actual lesson — **able to refuse an invalid request without spending anything**.

---

## 2. Structure — `orchestrationSession`

```jsonc
{
  "session_version": 1,
  "session_id": "os_<base36>",         // process-local. NOT a run_id, NOT persisted.
  "post_id": "…" ,
  "built_at": "2026-07-23T…",

  // ── what is being looked at ──────────────────────────────────────────────
  "image_context": {
    "post_id": "…",
    "has_image": true,
    "dimensions": null,                 // null = NOT REPORTED, never assumed
    "regions_present": 6,
    "grounds_present": 5,
    "percepts_present": 2,
    "unreadable": []                    // e.g. ["image_dimensions"]
  },

  "active_surface": "differential | manuscript | unknown",

  // ── what is selected, right now ──────────────────────────────────────────
  "selections": {
    "region_ids": [], "ground_ids": [], "percept_ids": [],
    "visual_mark_ids": [],              // P2C-OH, absent until visualMarks lands
    "source": "user"                    // who made this selection
  },

  // ── the percept in focus, if one is ──────────────────────────────────────
  "percept_context": {
    "percept_id": "pctx_…",
    "expression": "…",
    "evidence_state": "unknown | ungrounded | detached | partial | intact",
    "packet": { /* buildPerceptPacket output, verbatim, or null */ },
    "thread_summary": "…"               // threadSummary(), or null
  },

  "ground_context": {
    "cited": [ { "ground_id", "ground_type", "label", "role", "present", "detached" } ],
    "roles_named": 2,
    "resolution_assessed": true         // false ⇒ `present`/`detached` mean NOTHING
  },

  // ── the writing ──────────────────────────────────────────────────────────
  "manuscript_context": {
    "block_count": 0,
    "is_editing": false,
    "selection": {
      "kind": "none | text | percept_chip",
      "text": "…",
      "block_id": "…",
      "cited_percept_ids": [], "cited_ground_ids": [],
      "citation_state": "cites_nothing | cites_percepts | not_assessed"
    },
    "model_origin_blocks": [],          // block ids with origin != 'human'
    "external_claims": null             // null = NOT ASSESSED. never []
  },

  // ── memory of asking ─────────────────────────────────────────────────────
  "operation_memory": {
    "recent": [ { "operation", "state", "at" } ],   // projection, not live stages
    "assessed": true,
    "note": "latest is latest; it produced nothing that entered the circuit"
  },

  // ── proposals ────────────────────────────────────────────────────────────
  "proposed_actions": [ /* normalized perceptualActions objects */ ],
  "allowed_actions":  [ "find_parts", "brush_field", … ],   // from ACTION_TYPES ∩ capabilities
  "forbidden_actions": [
    { "type": "challenge_percept", "reason": "a model may not author a challenge" },
    { "type": "ask_model_reading", "reason": "dispatch is not wired in this gate" }
  ],
  "available_tools": [],                // empty ⇒ the model may call nothing

  "user_captivation": {
    "prompt": "…",
    "matched": ["gaze", "light"],
    "note": "the curator's words. Not a perception."
  },

  // ── the discipline, as data ──────────────────────────────────────────────
  "constraints": {
    "image_only": true,
    "mark_external_claims": true,
    "ask_for_contradictions": true,
    "no_identity_claims": true,
    "no_fake_causality": true,
    "distinguish_observed_from_inferred": true,
    "suggestions_are_not_committed_truth": true,
    "user_confirmation_required_for_mutation": true
  },

  "model_io_policy": {
    "output_shape": "perceptual_action_list",
    "must_validate_against": "perceptualActions.normalizeAction",
    "may_mutate": false,
    "may_persist": false,
    "may_author_challenge": false,
    "unknown_fields_rejected": true
  },

  "dispatch_state": "none",             // none | preview_only | sent
  "unreadable": [],                     // everything asked for and not obtained
  "provenance": {
    "assembler": "orchestration/session-v1",
    "planner": "attunement/lexicon-v1",
    "model": null,
    "run_id": null
  }
}
```

### 2.1 The five fields doing the real work

**`unreadable[]`** — the honesty channel, and the field most likely to be dropped by a future refactor. Every context the assembler was asked for and could not obtain is named here. Its existence is what allows a model to be told *"you were not given the image dimensions"* rather than inferring from silence that there were none. This is **absent ≠ none ≠ nominal** (P1C) lifted to the whole session.

**`resolution_assessed`** — mirrors `buildPerceptPacket`'s refusal to report `'intact'` without a resolver. When `false`, `present`/`detached` on every ground carry **no information**. Without this flag a consumer reads a default and believes it.

**`citation_state: 'cites_nothing'`** — a **record**. It is *not* `'unsupported'`, which would be a judgement the system cannot make (P2C-MS §2.1). The vocabulary encodes the distinction so a consumer cannot collapse it.

**`external_claims: null`** — `null` means *not assessed*; `[]` would mean *assessed, found none*. `extract_claims` does not exist, so `null` is the only honest value. A future implementer who "cleans this up" to `[]` converts *we did not look* into *there are none*.

**`dispatch_state`** — defaults to `'none'` and is stated **inside** the session for the same reason `buildPerceptPacket` states `dispatch.sent: false` inside the packet: so it cannot be mistaken for a dispatch record. P2B refuses an action asserting `dispatch.sent === true` rather than correcting it; `validateSession` does the same for `'sent'` without a `provenance.run_id`.

### 2.2 Observed vs inferred, structurally

The split is not a convention here — it is the layout:

| Region | Standing | Rule |
|---|---|---|
| `image_context`, `selections`, `ground_context`, `manuscript_context`, `operation_memory` | **observed** | the system saw this and can point at it |
| `percept_context.evidence_state`, `external_claims` | **judgement** | the system concluded this and owns it |
| `proposed_actions`, `user_captivation.matched` | **proposal / attribution** | *you said* — never *we saw* |
| `constraints`, `model_io_policy`, `forbidden_actions` | **law** | not negotiable by the consumer |

A model handed this object cannot claim it observed a proposal, because proposals do not live in the observed region.

### 2.3 `allowed_actions` is derived, never authored

`sessionAllowedActions()` returns `ACTION_TYPES ∩ capabilities`, minus `forbidden_actions`. It cannot name a type outside `perceptualActions.ACTION_TYPES`.

This is P2B's rule that capabilities *"must be read together with the executor switch so a capability cannot be claimed without an executor behind it"* — and it is the answer to the question this gate really has to settle: **who defines the grammar?** Not the session, not the model, not LangChain. `perceptualActions.js` defines it; everyone else intersects with it.

---

## 3. Relation to industry patterns

The Session is structurally a familiar object: **agent thread context + tool registry + structured output schema.**

| Industry pattern | Session field | Where Semant diverges |
|---|---|---|
| thread / conversation state | `manuscript_context`, `operation_memory` | scoped to one post and thrown away; there is no cross-post memory and none is proposed |
| tool registry | `available_tools`, `allowed_actions` | tools are **perceptual acts on evidence**, not API calls; most require a **human hand** on the image to complete (`needsGeometry`) |
| structured output schema | `model_io_policy.output_shape` | the schema is not for parsing convenience — it is the **refusal surface**. `normalizeAction` returns `null`, not a partial |
| system prompt / guardrails | `constraints` | **data, not prose.** Prose guardrails can be edited by whoever writes the next prompt template |
| RAG context window | `percept_context`, `ground_context` | retrieved units are **citations with roles and resolution state**, not text chunks. A chunk cannot say *"this evidence no longer resolves"* |
| human-in-the-loop approval | `user_confirmation_required_for_mutation` | approval is not a wrapper around the call; it is the **only** path by which anything enters the circuit |

### 3.1 On LangChain / LangGraph

**None is present. None is scaffolded. This gate adds no dependency.**

If one is adopted later, the constraint is one-directional and non-negotiable:

> **LangGraph may orchestrate the calls. It must consume Semant's action grammar. It must never define it.**

Concretely: a graph node may take an `orchestrationSession`, call a model, and return candidate actions — and every one of those candidates passes through `normalizeAction` and `validateAction` before a card renders. A framework's own tool-calling schema is **not** an accepted input format. The moment the grammar is defined by the orchestration library, the vocabulary of perception becomes whatever that library finds convenient to serialise, and `counterforce` — a role that exists precisely because it is *kept, not resolved* — is exactly the kind of concept that gets flattened first.

This is P2B's insurance already paid: *"swapping the planner for a model later changes the **source** of proposals and nothing else."* The Session extends that from one planner to a whole context assembly.

---

## 4. What the module does and does not do

`frontend/src/orchestration/orchestrationSession.js` — **pure. No network. No model. No store. No clock it does not accept.**

| Function | Returns |
|---|---|
| `buildOrchestrationSession(inputs)` | the object above, assembled from supplied inputs only |
| `summarizeSession(session)` | one honest line, degradation-aware, e.g. `manuscript · text selected · cites nothing · 3 suggested acts · nothing sent` |
| `sessionAllowedActions(session)` | `ACTION_TYPES ∩ capabilities` minus forbidden |
| `sessionForModelPreview(session)` | what a model *would* be given — inspectable, **not sent** |
| `validateSession(session)` | `{ valid, errors[], warnings[] }` |

`validateSession` refuses (errors, not corrections):

- `dispatch_state: 'sent'` without `provenance.run_id` — a session cannot claim a dispatch the ledger cannot show
- an `allowed_actions` entry outside `ACTION_TYPES`
- `challenge_percept` in `allowed_actions` while a model is the proposal source
- `model_io_policy.may_mutate === true`
- `external_claims: []` while `extract_claims` is not among available tools — *assessed-and-found-none* asserted without an assessor

It warns (travelling with the object, shown, never hidden) when: `resolution_assessed` is false, `unreadable` is non-empty, or `percept_context.evidence_state` is `'unknown'`.

**Not built, deliberately:** any transport, any model client, any persistence, any `run_id` minting, any autonomous loop.

---

## 5. Open questions this gate does not settle

1. **Where does a real `run_id` come from?** Still P1E's question, still an identity question rather than plumbing. `provenance.run_id` is the seam; nothing mints one.
2. **Should a Session ever be recorded?** The moment one is dispatched, P1D's `no model reading recorded` stops being true. The recording must land **before** the first dispatch, not after.
3. **How does a curator see the Session?** P2C-OH's CVAT lesson: *a provenance field nobody can see or filter on is, in practice, no provenance at all.* `sessionForModelPreview` exists so this can be answered with a disclosure rather than a doc.
4. **Multi-post sessions (Atlas).** Deliberately out of scope. Widening from one post is where a working context quietly becomes memory.

---

*The Session's whole value is what it refuses to carry, and what it admits it does not know.*
