# Rehearsal event grammar (R1)

**RESEARCH-ONLY.** This grammar governs `rehearsal-trace.schema.json`. It is a
research vocabulary, not a production state machine, route, or Mongo schema.

## Ordered kinds (typical flow, not enforced order)

```text
RECEIVE → ATTEND → ASK → CALL_ORGAN → OBSERVE → DISAGREE
→ REDIRECT → PROPOSE → HUMAN_TURN → CROSS → RETURN
→ REVISE → SEDIMENT → HARVEST
```

The trace is **append-only** during a run. Events may skip or repeat kinds; the
sequence above is the reference path (the Passage-001 reconstruction follows it).

## Per-event required fields

`event_id, actor, kind, parent_event, source_refs, target_refs, register,
uncertainty, reconstructed, observation_ref, reversibility, cost, provenance,
timestamp` — with `timestamp_null_reason` required whenever `timestamp` is null.

## Actors and registers

- **actor:** `human | fable | opus | system`
- **register:** `evidence` (sensible/grounded) · `reading` (interpretation) ·
  `opening` (unresolved invitation).

## Honesty rules

- A reconstructed event sets `reconstructed: true` and leaves genuinely
  uncaptured fields (`observation_ref`, `cost`, `reversibility`, `timestamp`,
  real image/mask ids) **null** — never guessed.
- An event that references an organ that was never actually run keeps
  `observation_ref: null`; only a CAPTURE-mode call with a frozen observation
  may set it.
- **Percept ids** must name which kind: `pct_*` = attention percept,
  `pctx_*` = expression percept (see `classify_percept_id`).

## Terminal outcomes

A run may end `completed`, `refused`, or `stalled`. Refusals/stalls are **valid
terminal outcomes**, recorded as a terminal event (`terminal: true`,
`outcome: ...`) — not exceptions.
