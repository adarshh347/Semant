# Inquiry workbench — the fields this UI consumes

*HARNESS-002 Lane C → Lane D. Companion to `canonical-session.json`.*

This is the whole list. Every field below is read by `inquiryContract.js` and reaches the DOM;
nothing else in a payload is looked at. A test (`handoff.test.js`) fails if a normaliser starts
reading a field that is not named here, so this document cannot quietly go stale — that being the
usual fate of a handoff doc, and the reason the check exists rather than a promise to keep it
updated.

**Lane D's job is to generate this payload from the backend and add parity coverage.** It is not
to reconcile two ontologies: there is no second schema here. This surface holds normalisers and a
list, and the Pydantic model on the other side remains the single definition.

## Reading the tables

- **required** — the UI needs it to render the row at all.
- **enumerated** — normalised to `{value, known}`. An unrecognised value renders as *unknown* with
  the raw string kept visible. It is never mapped onto a neighbour.
- **tri-state** — `true` / `false` / `null`, where null means *the backend did not say*. Gates test
  `=== true`, so null and false both fail closed while rendering differently.
- **null ≠ 0** — a missing number renders as an em dash. `0` is a real value and survives.

---

## Session envelope

| field | shape | notes |
|---|---|---|
| `schema_version` | string | read, not enforced |
| `session_id` | string | **required** — the id every later write is addressed to |
| `inquiry_id` | string | |
| `revision` | number \| null | **the concurrency token.** Sent back as `expected_revision`. Null means absent, and no `expected_revision` is then sent at all — never 0 |
| `state` | **enumerated** | `framing · reading · compiling · awaiting_user · ready · executing · judging · composing · complete · exhausted · refused · error` |
| `mode` | **enumerated** | `auto · consult · step` |
| `graph` | object | below |
| `posts[]` | array | **what was actually read** — `post_id`, `title`, `image_ref`, `fingerprint`, `readable`, `note`. `readable: false` renders as "could not be read", never as a post that was read |
| `frame` | object \| null | the framer's output, rendered raw. It never sees pixels |
| `decision_requests[]` | array | below |
| `decision_records[]` | array | below |
| `capability_receipts[]` | array | below |
| `evidence[]` | array | below |
| `synthesis` | object \| null | null renders as "no answer yet", not as an empty answer |
| `stages[]` | array | **the machinery ledger** — below. Sent since HARNESS-002D; read since 003C |
| `verdicts[]` | array | the judge's conclusions — below |
| `gaps[]` | string[] | what nothing could serve |
| `why_paused` | object \| null | rendered raw when present |
| `provenance` | object | session-level producer and schema identity |
| `trace[]` | array | below |
| `stop_reason` | string | rendered in plain language when a session ends short |
| `error` | string | rendered in the session header when present |

An unrecognised `state` keeps the client polling. It is the only conservative reading: a client
older than the server must not declare a session finished because it did not know the word.

## Graph (`graph`)

| field | shape | notes |
|---|---|---|
| `schema_version`, `graph_id`, `inquiry_id` | string | |
| `prompt` | string | **byte-identical.** Never trimmed or re-cased — the source spans index into this exact string |
| `image_refs[]` | array | `post_id`, `title`, `image_ref`, `image_url` |
| `reading` | object | below |
| `claims[]` | array | below |
| `claim_edges[]` | array | `edge_id`, `from_claim` (or `from`), `to_claim` (or `to`), `relation`, `note` |
| `observables[]` | array | below |
| `semantic_remainder[]` | array | `remainder_id`, `text`, `why_unresolved`, `claim_refs[]` |
| `refusals[]` | array | `refusal_id`, `reason`, `detail`, `refs[]` |
| `provenance` | object | rendered as key/value rows |

### `graph.reading`

| field | shape | notes |
|---|---|---|
| `text` | string | **required** |
| `blocks[]` | array | `block_id`, `kind`, `text`, `image_refs[]`. Sent since HARNESS-002D and read since 003C — these are what the dissector consumes, so a ledger showing claims without them starts the chain half-way |
| `status` | string | **capped at `interpretive`.** A reading that arrives claiming `measured` is rendered as interpretive AND the original is shown beside it. Do not send a status stronger than `interpretive · imagined · uncertain · unresolved` — it will be reported as a defect, visibly |
| `source`, `model` | string | shown in the collapsed model receipt |
| `provenance` | object | |

### `graph.claims[]`

| field | shape | notes |
|---|---|---|
| `claim_id` (or `id`) | string | **required** |
| `text` | string | **required** |
| `claim_kind` (or `kind`) | **enumerated** | the thirteen forms from the plan |
| `status` | **enumerated** | `measured · visible · sourced · interpretive · imagined · proposed · unresolved` |
| `subject`, `predicate`, `object` | string | shown as a triple when inspected |
| `source_span` | object \| null | `origin`, `text`, `start`, `end`. `origin: 'prompt'` renders "from your question", `'reading'` renders "from the reading" — the difference decides who is responsible for the claim |
| `image_scope[]` | string[] | |
| `epistemic_demand` | string | "to support this: …" |
| `confidence` | number \| null | labelled as the **model's own** confidence. Upgrades nothing |
| `author` | **enumerated** | `user · system · model`. `user` renders "your direction" |

A claim's `measured`/`visible` status does not by itself produce a support row — that comes from
`evidence[]`.

### `graph.observables[]`

| field | shape | notes |
|---|---|---|
| `observable_id` (or `id`) | string | **required** |
| `claim_ref` (or `claim_id`) | string | the claim it serves |
| `observable_kind` (or `kind`) | string | open string, underscores rendered as spaces |
| `target` | string | |
| `image_scope[]` | string[] | |
| `ground_forms[]` | string[] | rendered as tags |
| `capability_classes[]` | string[] | rendered as tags. **Classes, not tool names** |
| `alternatives[]` | array | `alternative_id`, `label`, `capability_class`, `consequence`, `available` (**tri-state** — `false` prints "not available", `null` prints "availability not stated", and the two are not the same) |
| `success_condition`, `ambiguity_condition`, `refusal_condition` | string | shown under "Conditions" |
| `residual_interpretation` | string | what stays interpretive even if every measurement succeeds |
| `availability` | **enumerated** | `available · unavailable · capability_gap` — three different rows with three different treatments |
| `gap_reason` | string | appended to the availability sentence |

## Dissolution (HARNESS-003A, rendered forward)

Rendered where present and silent where absent. Lane A is building these in parallel; a surface
that showed "0 atoms" as a defect would report an unmerged lane as a failure of the run.

| field | shape | notes |
|---|---|---|
| `graph.source_units[]` | array | `source_unit_id`, `source_type` (**enumerated**: `prompt_clause · reading_block`), `source_ref`, `exact_quote`, `image_refs[]` |
| `graph.semantic_atoms[]` | array | `atom_id`, `source_unit_ids[]`, `text`, `unit_kind` (**enumerated**, nine forms), `subject`/`predicate`/`object`, `image_scope[]`, `epistemic_ceiling` (**enumerated**), `author` (**enumerated** — `user` renders "your direction"), `provenance` |
| `graph.coverage[]` | array | `source_unit_id`, `disposition` (**enumerated**: `represented_by · duplicate_of · semantic_remainder · refused`), `refs[]`, `reason` |

**Every source unit needs exactly one disposition.** A unit with none is rendered as **lost**, not
as a remainder, and the coverage row is flagged — a remainder is a decision, and a unit nobody
accounted for is a unit the compiler dropped. The two must not read alike.

## Verdicts (`verdicts[]`)

| field | shape | notes |
|---|---|---|
| `verdict_id` | string | |
| `claim_ref` | string | |
| `outcome` | **enumerated** | `supported_by_evidence · partially_supported · interpretive_only · unresolved · contradicted · not_investigated` |
| `why` | string | |
| `evidence_refs[]`, `receipt_refs[]` | string[] | |

`interpretive_only` and `not_investigated` never render alike: one says the claim was examined and
nothing measured bears on it, the other says nobody asked. A reader deciding how much to trust an
answer needs both.

## Decisions

### `decision_requests[]`

| field | shape | notes |
|---|---|---|
| `decision_id` (or `id`) | string | **required** |
| `session_id` | string | |
| `kind` | **enumerated** | `choose_operationalization · choose_scope · resolve_ambiguity · authorial_action · review_evidence · choose_direction` |
| `question` | string | **required** — the focused heading |
| `why_now` | string | what changes downstream |
| `affected_refs[]` | string[] | claim and observable ids; they are highlighted in the panels below |
| `options[]` | array | `option_id`, `label`, `consequence`, `recommended`. **`consequence` is load-bearing** — it is previewed before submit, and an option without one renders "no consequence was described" |
| `allow_free_text` | boolean | when false, no amendment box is offered |
| `blocking` | boolean | |
| `answered` | boolean | the UI treats the first unanswered request as the open one |

### `decision_records[]` — automatic and human, one list

| field | shape | notes |
|---|---|---|
| `record_id` (or `id`) | string | |
| `decision_id` | string | |
| `decider` | **enumerated** | `user · system · model`. `system` renders "Semant chose, without asking" |
| `action` | **enumerated** | `select · reject · skip · redirect · amend` |
| `question`, `selected_option_id`, `selected_label` | string | |
| `free_text` | string | rendered under "your direction" — never as a finding |
| `rationale` | string | **send one for every automatic choice.** Auto mode means no interruption, not invisible agency |
| `affected_refs[]` | string[] | |
| `at` | ISO string \| null | |
| `revision` | number \| null | |

### What the UI POSTs to `/decisions`

```json
{
  "decision_id": "dec_…",
  "response_id": "res_…",
  "action": "select | reject | skip | redirect | amend",
  "selected_option_id": "opt_…",
  "free_text": "…",
  "expected_revision": 3
}
```

`selected_option_id` and `free_text` are **omitted when empty**, never sent as `""`.
`expected_revision` is omitted when the session carried no revision.

`response_id` is **minted once per decision and reused on every retry**, including after a 409.
Lane D should treat a repeat of the same `response_id` as a duplicate rather than a second
decision — otherwise a response that in fact landed before a conflict gets applied twice, and an
append-only history records two decisions where a person made one.

A **409** must carry `{"detail": "...", "session": {...}}` where possible. The UI refreshes from
the rejection body without a second read, keeps the person's selection, and distinguishes two
cases by what the refreshed session says: if the decision is still open it invites a resubmit; if
it has been answered elsewhere it explains that instead and invites nothing.

## Capability receipts (`capability_receipts[]`)

| field | shape | notes |
|---|---|---|
| `receipt_id` (or `id`) | string | **required** |
| `request_ref` | string | the observable it answers |
| `capability` | string | |
| `execution_mode` | **enumerated** | `fixture · live`. **`fixture` forces the outcome to `simulated`** whatever `status` says |
| `status` | **enumerated** | `live · simulated · empty · unavailable · refused · capability_gap` |
| `usable_as_evidence` | **tri-state** | never defaulted true. A missing field is not permission |
| `attempted` | **tri-state** | **the field that separates `empty` from `unavailable`.** Please always send it |
| `payload` | object | rendered as JSON under an expander |
| `detail` | string | |
| `latency_ms` | number \| null | null renders as an em dash, never `0 ms` |
| `provenance` | object | |

A receipt with `execution_mode: "fixture"` carries a permanent **SIMULATED — not evidence** label
adjacent to its payload and again beside the geometry when expanded. It supports no claim and
satisfies no criterion, and it will not do so even if `usable_as_evidence: true` arrives with it.

## Evidence (`evidence[]`)

| field | shape | notes |
|---|---|---|
| `evidence_id` (or `id`) | string | **required** |
| `claim_refs[]` | string[] | the claims it serves |
| `observable_ref`, `receipt_ref` | string | |
| `kind` | string | |
| `epistemic_status` | **enumerated** | the claim-status vocabulary. **This is the only source of a `measured` or `visible` badge in the whole UI** |
| `summary` | string | |
| `usable_as_evidence` | **tri-state** | must be exactly `true` to count |
| `execution_mode` | **enumerated** | `fixture` disqualifies the object regardless of the flag above |
| `verdict` | object \| null | `verdict_id`, `outcome` (**enumerated**: `supports · complicates · refutes · inconclusive`), `note`. Null renders "no verdict", not "inconclusive" |
| `provenance` | object | |

Disqualified objects are **shown, not hidden** — under "Returned, but not evidence", with the
reason. An evidence list that is empty because everything was simulated looks identical to one
where nothing was ever requested, and those are opposite facts for a reader deciding whether to
trust the answer.

## Synthesis (`synthesis`)

| field | shape | notes |
|---|---|---|
| `synthesis_id` (or `id`) | string | |
| `note` | string | |
| `sections[]` | array | below |

### `synthesis.sections[]`

| field | shape | notes |
|---|---|---|
| `section_id` (or `id`) | string | **required** |
| `heading`, `text` | string | |
| `claim_refs[]`, `evidence_refs[]`, `refusal_refs[]` | string[] | expanded under "What supports this" — three separate lists, not one "sources" |
| `status` | **enumerated** | claim-status vocabulary |
| `user_authored` | boolean | renders "your direction" |

`evidence_refs` pointing at disqualified objects produce **no** support row; the section then says
"no measurement supports this section" rather than showing the object.

## Stage attempts (`stages[]`) — HARNESS-003C

The backend has sent this list since HARNESS-002D and the client dropped it, which is the 002R
rehearsal's fourth tree cause. It is read now, in **both** shapes: today's `StageEvent`
(`event_id`/`stage`/`outcome`/`at`/`revision`/`detail`/`input_refs`/`output_refs`) and Lane B's
richer forward one. Neither is required to be complete.

| field | shape | notes |
|---|---|---|
| `attempt_id` / `event_id` | string | either spelling |
| `stage` | **enumerated** | `framer · theorist · compiler · steward · capability · judge · composer` |
| `outcome` | **enumerated** | the union of both servers: `queued · started · completed · thin · truncated · empty · unavailable · refused · skipped · error · interrupted`. `skipped` is today's and absent from Lane B's list; `queued`/`thin`/`truncated`/`interrupted` are the reverse. **`thin` and `truncated` never wear `completed`'s treatment** — that is what this phase is for |
| `sequence`, `revision` | number \| null | |
| `at` | ISO \| null | today's single timestamp; still places the event in time |
| `queued_at`, `started_at`, `completed_at` | ISO \| null | Lane B's three |
| `duration_ms` | number \| null | **never rendered as 0 when absent.** An em dash. Elapsed time is a DIFFERENT word on screen and a different field underneath — it is this client counting from `started_at`, and a stage that never said when it started shows neither |
| `input_refs[]`, `output_refs[]` | string[] | |
| `input_count`, `output_count` | number \| null | read where declared, **derived from the refs otherwise**, and null for a stage that reported neither |
| `actor.role` / `role` | string | |
| `actor.model` / `model` | string | |
| `actor.provider` / `provider` | string | |
| `actor.execution_mode` / `execution_mode` | **enumerated** | `fixture · live` |
| `call_topology` | string | e.g. `per_image_then_synthesis`, rendered with underscores as spaces |
| `planned_calls`, `actual_calls` | number \| null | **"4 image readings plus one synthesis planned" renders only from `planned_calls`.** A count this surface derived from the image list would be a guess wearing your authority |
| `calls[]` | array | `call_id`, `label`, `started_at`, `duration_ms`, `finish_reason`, `outcome` |
| `image_index`, `image_total` | number \| null | 0-based index on the wire; the renderer adds the one |
| `substage` | string | e.g. `cross-image synthesis` |
| `finish_reason` | string | rendered beside the stage, not buried in a receipt. `length` is the single most consequential value the live runs produced |
| `refusal_summary` / `error_summary` / `gap_summary` | string | first non-empty is shown |
| `provenance` | object | |

No progress percentage and no estimated completion is rendered from any of this, and none should
be sent: the inquiry does not know how long a model call takes, so a bar would be inventing a
denominator and an ETA a rate.

## Trace (`trace[]`)

| field | shape | notes |
|---|---|---|
| `event_id` (or `id`) | string | |
| `at` | ISO string \| null | null renders nothing, never an invented timestamp |
| `actor` | string | the role name |
| `actor_kind` | **enumerated** | `user · system · model` — distinguishable at a glance without reading the reason |
| `transition` | string | e.g. `ready → executing` |
| `reason` | string | |
| `refs[]` | string[] | causal references |
| `revision` | number \| null | |

## Fixtures, and what each is for

All exported from `../inquiryFixtures.js`. `canonical-session.json` is `completedFixture()`,
serialised — the realistic Phase-1 target.

| fixture | what it exercises |
|---|---|
| `compilingFixture` | mid-flight, nothing blocked |
| `consultFixture` | paused at an operationalization fork |
| `respondedFixture` | after a user selection, one fixture receipt |
| `completedFixture` | **canonical** — synthesis, citations, remainder |
| `autoFixture` | a recorded automatic choice |
| `outcomesFixture` | empty · unavailable · refused · capability_gap · simulated, together |
| `measuredEvidenceFixture` | the Phase-2 shape: a live usable evidence object |
| `simulatedEvidenceFixture` | an evidence-shaped object minted from a fixture receipt |
| `unknownFutureFixture` | unrecognised state, claim kind, status and execution mode |
| `conflictSessionFixture` | 409 stale — decision still open |
| `duplicateSessionFixture` | 409 duplicate — decision answered elsewhere |
| `otherDomainFixture` | an unrelated domain through identical types |

## Not consumed

Anything not listed above. Extra fields are ignored without error, so Lane D may send more than
this — but nothing unlisted will appear on screen, and adding a field to the payload is not the
same as surfacing it.
