# CIRCUIT-001 P1E — Design report

**DESIGN GATE. NO CODE CHANGED.** No route, schema, field, collection or migration. No model call.
No production data mutated — Mongo was read (`find` / `count_documents`) to check how the existing
reference seam is used in practice.

Full reasoning: `Decisions/CIRCUIT-001-P1E-run-relation-design.md`.
Dispatch itself was deferred earlier in `Decisions/CIRCUIT-001-P1E-percept-packet-dispatch-decision.md`.

---

## 1. The finding that shaped the design

**The reference seam already exists, is already in use, and already carries a generation marker.**

`VisionStageEvent` has `input_refs` / `output_refs` (`vision_run_contracts.py:219-220`), and three of
the four instrumented operations populate them. In the corpus **today**:

```
refine.complete        output_refs: [{"region_id": "refine_a02726c3c5", "geometry_rev": 1}]
find_similar.retrieve  input_refs:  [{"region_id": "seg_0", "space": "visual_identity"}]
```

**`geometry_rev` is already travelling in a ref.** So the run relation is not a new mechanism to
invent — it is an existing one to extend.

Two facts constrain it:

- **`vision_runs` knows nothing about percepts** (`grep percept` over the contracts returns nothing).
  Attaching runs to percepts is a genuinely new relation.
- **The codebase already refuses causal ordering.** `project_run`: *"events keep their stored
  (observation) order; that order is not a causal claim."* P1D's discipline is the house rule, not an
  import.

Corpus: 9 runs — 4 dissect, 3 find_similar, 2 refine. **No `dissect` run populates either ref
field**, which bounds P0 §5 precisely: the seam is not missing; `dissect` does not use it.

## 2. The chosen run relation model

**No product entity carries a run reference. The run records what it observed; the thread finds runs
by query.**

```
input_refs: [{ "percept_id": "pctx_…",
               "grounds": [{ "ground_id": …, "region_id": …,
                             "geometry_rev": 2, "mask_hash": …, "detached": false }],
               "packet_digest": "sha256:…" }]
```

- **Relation name: `observed_run`.** From the percept's side, the run *looked at* it. Non-causal and
  directionally clear.
- **Supersession requires same operation + same percept + same evidence fingerprint.** Different
  evidence is **not** a newer answer — it is a different question, and neither supersedes.
- **Nothing is deleted.** Older runs are retained; the thread shows `last challenge recorded` and,
  expanded, `older challenge`. A run whose fingerprint no longer matches renders
  **`challenge recorded · evidence has changed since`** — a fact, not a verdict.
- **First operation: `challenge`**, reaffirmed.

**One sentence:** *the run is the thing that happened, so the run should remember; the percept should
stay a noticing, not become a ledger.*

## 3. Rejected alternatives

| rejected | why |
|---|---|
| **`run_ids` on Percept** | A stored back-reference is a second copy of a fact the run holds — and this codebase has the precedent: the durable `detached: true` flags, **written by nothing, read by nothing, stale on the first collision**. It would keep asserting a reading after the run was superseded or found to have observed different evidence. |
| **Persisted Percept Packet** | The packet's value is that it is *derived*. Persisting creates a third truth that can disagree with both percept and run. A **snapshot belongs inside the run**. |
| **Run on Mention** | Mentions are reconstructed from markup on every load and their durability is still open. Hanging model provenance off the least durable object inverts the risk. |
| **Run on Ground** | A ground is evidence, not a question — the same argument that kept Ground Roles off the ground record in P1C. |
| **A new result collection** | It is `vision_runs` with a different name. Revisit only if runs prove structurally unable to carry it. |
| **`produced_by`** | Causal, and false in both directions. |

## 4. Why no implementation

Three reasons, and the third is the real one.

1. The gate was explicitly decision-only.
2. Nothing dispatches yet, so there is nothing to attach — the relation has no first instance.
3. **A run's answer cannot be trusted while a reference can silently re-point.** The existing refs
   already store `region_id: "seg_0"` — precisely the collision-capable ordinal `HW-C8` enumerated.
   Implementing the relation now would industrialise the hazard: model output attached to evidence it
   may never have seen, **with provenance that still looks clean.**

**The design's honest limit:** it does not make run answers trustworthy. It records enough to
*detect* that one should not be trusted — which is a lesser and different thing, and is stated as
such in the decision doc §6.

## 5. Recommended next gate — **B: `P1F — Stable evidence identity precondition`**

Not the dispatch prototype.

- It is the **precondition** §4.3 identifies, not a detour.
- It is **already authorized-with-conditions and unscheduled** (`HW-C9-announcement-only-merge-fix`):
  `suppressed_by_id` + `suppressed_by_geometry` counters in the existing `STAGE_MERGE_CURATOR`
  detail, using the **existing `_region_box_iou`**, with a byte-identical-`region_annotations`
  acceptance test. **Three integers and arithmetic that cannot raise.**
- It unblocks three things at once: run-answer trust, the thread's `substitution not assessed` row,
  and Atlas's precondition.
- Worst case is *"the number is always zero"* — which is a result.

**Carry one correction into it:** HW-C9 scoped the counters to the id guard at `posts.py:804`, which
covers **2** exposed curator regions. The **auto→auto** branch at `:809-819` re-points an ordinal onto
a new mask and counts it in `kept_auto` as an ordinary survivor — covering the **51-region** auto
population. **Instrument both; the larger exposure is the uninstrumented one.**

**Not chosen:** A (challenge dispatch) ships the first model reading onto the one hazard the
programme has tracked throughout. C (durable Mention) is correctly ordered *after* B and still blocked
by having **0 text blocks** in the corpus — no evidence yet of how curators actually cite.

## 6. Impact on Atlas and Codex

Both are *about* accumulated relations, so both inherit whatever this decision gets wrong — and they
show it to a reader **who was not there**.

- **Atlas** would compare percepts across images. If a run relation can silently re-point, Atlas
  assembles a history that never happened — and unlike one wrong row, an assembled history reads as a
  *pattern*.
- **Codex** is *"the layer at which change over time is answerable"*. Supersession is therefore its
  core mechanic, and §4's rule — **different evidence is a different question, not a newer answer** —
  is the single most Codex-relevant decision this gate makes. Without it, a Codex timeline would
  quietly overwrite an answer that was true of what was actually there.
- **Neither is unblocked by this.** Both still wait on the durable-citation decision, and now also on
  P1F.

**One thing this design deliberately gives them:** because runs are queried rather than back-
referenced, a future Atlas can ask *"what has been asked of this percept?"* without any product
entity having been reshaped to answer it.
