# CIRCUIT-001 P1C — Implementation report

**Ground Roles + Percept Packet builder.** Frontend only. **No production data changed** — verified
by API after the browser run (§7), including that **no role wrote itself onto `post.grounds`**.

Follows `CIRCUIT-001-P1B-implementation-report.md` §7, which named all four items this gate delivers.
Design basis: `CIRCUIT-001-P1-percept-ground-depth-addendum.md` §§1–2.

---

## 1. What changed

| area | file | what |
|---|---|---|
| **Ground Roles** | `differential/groundRoles.js` **(new)** | vocabulary + pure accessors |
| **Percept Packet** | `differential/perceptPacket.js` **(new)** | pure builder, nothing sends |
| percept record | `state/perceptMentions.js` | `ground_roles` carried, omitted when empty |
| roles UI | `differential/DifferentialWorkspace.{jsx,css}` | composer role chips, row summary, packet disclosure |
| recall honesty | `differential/recall.js`, `components/blocknote/regionRefInline.jsx`, `components/RegionSurface.jsx` | absent-percept case |
| lens honesty | `state/regionStore.js`, `components/AletheiaHook.jsx` | partial + wholly-dead lens |
| tests | 3 files added/extended | +33 |

---

## 2. How Ground Roles are represented

A map on the **percept**, keyed by ground id:

```js
{ id: 'pctx_a', expression: '…', ground_ids: ['gnd_1','gnd_2'],
  ground_roles: { gnd_1: 'anchor', gnd_2: 'counterforce' } }
```

**The key is omitted entirely when no role is named**, so a percept written before P1C is
byte-identical to one whose roles were all cleared. Roles ride the percept record the curator already
saves — **no new entity, no collection, no migration, no backend change.**

Vocabulary: **ten roles, five offered up-front** (`anchor`, `support`, `counterforce`, `threshold`,
`field`), the rest available to the data layer and a later, roomier surface —
`rhythm`, `atmosphere`, `aperture`, `trace`, `external-limit`. Adding one is a one-line change and
requires no migration.

**Optional everywhere.** A percept with no roles is complete, and nothing in the circuit may refuse
one for lacking them. `setGroundRole` refuses a role on a ground the percept does not cite, and
refuses a key outside the vocabulary.

## 3. Why a role belongs to the percept's use, not the ground record

**Because the same ground is an anchor in one noticing and a counterforce in another.**

A ground says *"this part of the image"*. A role says *"and here is what it is doing in what I am
claiming"* — which is a property of the claim. Writing it to `post.grounds` would let the second
percept overwrite the first's reading: the evidence record would start carrying an interpretation,
and **the last curator to speak would win.**

It is also what makes a percept a **reading** rather than a list. *"The arch and the shadow"* is two
grounds. *"The arch, held against the shadow"* is a percept.

Pinned by test: assigning a role leaves the grounds array byte-identical, and two percepts hold
opposite roles for the same ground simultaneously. Confirmed in production data too — §7.

## 4. What the Percept Packet contains

`buildPerceptPacket(percept, ctx)` → a plain, JSON-serialisable object. **Pure. No fetch, no route,
no persistence, no `run_id`, and nothing is dispatched.**

| field | notes |
|---|---|
| `intent` | `read` · `challenge` · `compare` · `revise` · `transfer`. Defaults to `read`; an unknown verb falls back rather than passing through |
| `percept` | id, expression, properties, actor, `has_roles` |
| `source.post_id` | the image it rests on |
| `grounds[]` | ground id, type, label, **role**, `present`, and `detached` *only when a resolver was injected* |
| `evidence` | `cited` / `resolving` / `detached` / `state` / `note` |
| `manuscript` | citing block ids, mention count, and the text of those blocks — cheap context only, nothing fetched |
| `constraints` | `image_only` · `mark_external_claims` · `ask_for_contradictions` · `no_identity_claims` |
| `dispatch` | `{ sent: false, run_id: null }` — said in the packet so it cannot be mistaken for a dispatch record |

**Two design points worth keeping.**

**Without a resolver, `evidence.state` is `'unknown'` — never `'intact'`.** Absent is not nominal.
This is the same discipline the Circulation Thread uses for *"not recorded"* versus *"none"*.

**Constraints travel as data, not prose.** Each default is a lesson the rehearsals paid for:
`ask_for_contradictions` exists because of spark-10 — and the packet does **not** pretend it is
sufficient, since arm E supplied three real contradictions that bore on nothing. Omitting the demand
guarantees the failure; including it only makes it visible.

*The packet is the rehearsal **manifest** discipline moved into the product: freeze what is asked, on
what evidence, under what constraints, and be able to inspect — or refuse — it before spending
anything.*

## 5. UI changes

**Composer:** a role row per cited ground, five chips each. Click a named role again to clear it.
No required field, no blocking, no model call, no taxonomy panel.

**Percept row:** the named roles in one italic line (`anchor, counterforce`), and a **collapsed
`<details>` packet disclosure** — summary line plus the pretty-printed JSON, bounded to 11rem and
scrollable.

**Kept quiet:** roles are an affordance, so the unnamed state must not look unfinished; the packet is
collapsed by default because it is for a curator who wants to look, not something the surface pushes
forward.

## 6. Recall failures closed (P1B §7 items 3–4)

**Absent percept.** `regionRefInline` lit a chip on an id *match alone*, so prose asserted *"I am
being replayed right now"* over a no-op whenever the percept was missing from the store. The chip now
requires the percept to exist, and `recallPlayer.perceptMissing` drives a quiet
*"This noticing is no longer available."*

**Dead lens.** `AletheiaHook`'s explanatory hint was guarded by `regions.length > 0`, so when a lens
cited only replaced regions it showed **zero shapes and no hint** — the reading standing unchanged
over an image it could no longer point at. Now: *"The parts this reading points at are no longer in
the image."*

**Partial lens.** `focusRegions` now distinguishes *some* from *none*: the live parts are still shown
**and** the loss is named (`someLive: true`). Withholding the whole citation would hide evidence that
is still true; showing it silently would overstate what the citation covers.

All three state **absence, never cause** — `focusRegions` and `resolveGround` know only that an id
does not resolve.

## 7. Verification

| | |
|---|---|
| **tests** | **177 passing, 13 files** (P1B left 144). **+33**: 14 roles, 16 packet, 3 recall/lens |
| **build** | `vite build` ✓ |
| **backend** | not run — **no backend file touched** |
| **console** | no errors |

**Browser, read-only, on `695be786a9ea58f1b6aef5ed`:**
- Packet summaries render live: the degraded percept reads
  *"read · none of the 2 cited grounds still resolves · no roles named · not yet in the writing"*;
  the healthy one *"read · cites 1 ground · no roles named · not yet in the writing"*.
- Expanding shows real packet JSON — `packet_version: 1`, `intent: "read"`,
  `"id": "pctx_mrqp950d_0"`, `has_roles: false`.

**Production mutation: NONE.** `percepts: 2`, `grounds: 5`, `text_blocks: 0`,
`updated_at: 2026-07-19T00:46:31.869` — days before this session. **And `any ground_roles on
grounds? False`**, which is the design rule confirmed against live data rather than only in a test.

## 8. What remains for P1D

1. **Richer Circulation Thread** — expandable rows; records and judgements in visibly different
   voices. Still one derived line per percept.
2. **Model operation integration** — the packet exists and nothing sends it. P1D would add dispatch,
   and **that is where `run_id` becomes unavoidable**: the thread's *"no model reading recorded"* is
   currently honest precisely because no entity carries one.
3. **The durable Mention decision** — still branch (b) from `CIRCUIT-001-P0-open-decisions.md` §4:
   reconstruction made lossless, persistence deferred. The corpus still has **0 text blocks**, so
   there is still no evidence of how curators actually cite.
4. **Atlas/Codex prep** — blocked on (3), unchanged.

**Also open, smaller:** roles do not yet travel into the manuscript chip's markup — the packet reads
them from the percept, which is sufficient for orchestration, but a chip cannot currently show what
its grounds do. Worth doing only if a surface needs it.

**Still deliberately absent:** persisted Mentions, `suspect`, `run_id`, any backend change, and any
model call.
