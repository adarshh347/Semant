# Vertical rehearsal — 20260822-142311-offline

**Gate:** `fail`  ·  mode `offline`  ·  profile `default`  ·  base `4aa08e33f6d6` on `test/atlas-writer-vertical-rehearsal`  ·  fakes `all`

**Lanes still preventing the full pass:** `A`, `B`, `B/D/I`, `D`, `I`, `J/K`

## Assertions

| # | assertion | status | lane | detail | evidence |
|---|---|---|---|---|---|
| A1 | no quarantined prose appears in canon/export | **fail** | D | 1 uncommitted passage(s) checked against every manuscript export by text and every scene block by passage id; 1 leak(s) — the scene block cites a passage that is still `committed: false`: the passage accept wrote the scene before its version insert failed (profile.injected_writes), so an interrupted accept puts quarantined prose into canon | `stage:writer`, `stage:draft`, `db:writer_passages`, `db:manuscripts/export`, `leak:{'manuscript': 'ms_dd2177c8610f', 'scene': 'sc_4f98b67b72cc', 'block': 'blk_2f4079017f1a', 'passage': 'psg_0df296c9802b'}` |
| A2 | no Atlas arrangement/notes contain percept truth | **pass** |  | 3 Atlas document(s) scanned for forbidden node/edge/note keys; 0 offender(s) | `db:atlases`, `stage:atlas.canvas`, `stage:atlas.light_table`, `stage:relation` |
| A3 | every visible live relation/movement/citation hydrates from canonical evidence | **pass** |  | 3 live relation edge(s) re-read from the ledger; 0 without the mark committed in every post it spans. Movement/citation edges: no movement proposal/accept or axis inspection route exists on this base (movement_axes is written by scripts only); the Atlas has no movement mode | `stage:relation`, `stage:movement`, `api:/atlas/{id}/view` |
| A4 | every refusal writes nothing | **pass** |  | 3 refusal(s) captured with the write log read before and after; 0 wrote | `stage:relation`, `stage:profile.unavailable_model`, `stage:draft.accept`, `evidence:refusals` |
| A5 | every retry yields one canonical result | **fail** | B | a retried relation yielded 2 edge(s) and {'6a89b0d6643201f69d0a852c': 2, '6a89b0d6643201f69d0a852d': 2} mark(s) — the route has no idempotency key, so a lost response duplicates the commit | `stage:profile.lost_response` |
| A6 | stale revisions never overwrite | **fail** | B | the stale tab overwrote the newer note: the Atlas carries no revision and the notes route has no precondition | `stage:profile.stale_tab`, `shot:screenshots/021-stale-tab-second.png` |
| A7 | every old Writer version/operator provenance remains resolvable | **pass** |  | 2 version(s) of lineage lin_37cbea88f6eb: [{'version': 1, 'resolves': True, 'operators': 1, 'operators_resolve': True}, {'version': 2, 'resolves': True, 'operators': 1, 'operators_resolve': True}] | `stage:writer`, `db:writer_passage_versions`, `db:writer_operators` |
| A8 | evidence refs survive Atlas → Writer → revision → export | **fail** | I | {"atlas_draft_passages": 3, "scene_blocks": 8, "scene_blocks_with_evidence_refs": 2, "block_keys": ["color", "content", "id", "lineage_id", "origin", "provenance", "type", "version"], "scene_mentions_run_id": false, "writer_versions_with_provenance": 2, "writer_versions": 2, "export_carries_lineage_or_version_refs": false, "export_keys": ["content", "format", "manuscript_id", "title"]} — the markd | `stage:draft`, `stage:draft.accept`, `stage:writer`, `db:scenes`, `db:writer_passage_versions`, `api:/manuscript/{id}/export` |
| A9 | fixture posts change only at explicitly accepted evidence steps | **fail** | B | 19 stage(s) hashed every fixture post; 17 write(s) declared by accepting stages; 1 unexpected | `evidence:hash_timeline`, `evidence:expected_writes`, `evidence:unexpected`, `unexpected:differential:6a89b0d6643201f69d0a852a` |
| A10 | all unexpected mutations are printed as a field-level diff | **pass** |  | 1 unexpected mutation(s), each carried with its path-level diff in summary.json `evidence.unexpected[].diff` and in the report | `evidence:unexpected`, `report:Unexpected mutations` |

## Stages

| stage | status | lane | seconds | detail | screenshots |
|---|---|---|---|---|---|
| `walk.save_open` | **fail** | A | 2.8 | the saved walk cannot be opened from the index: the client's `atlasService.create()` drops `corpus_id` and the route answers 400 (an Atlas needs a corpus: pass post_ids or a run_id); the Atlas was opened over the same walk through the API so the circuit could continue | [001-walk-picked](screenshots/001-walk-picked.png) [002-walk-opened](screenshots/002-walk-opened.png) |
| `atlas.canvas` | **fail** | A | 4.1 | in Canvas mode the React Flow pane renders 1440x0 and a click on a node reaches `.atlas-shell` — the canvas cannot be panned, zoomed, dragged or connected in its own mode; the arrangement save was proven in Plan mode instead | [003-canvas-mode](screenshots/003-canvas-mode.png) [004-canvas-after-drag](screenshots/004-canvas-after-drag.png) |
| `atlas.light_table` | **pass** |  | 3.1 |  | [005-light-table-note](screenshots/005-light-table-note.png) |
| `differential` | **fail** | B | 6.0 | accepting one proposal removed committed evidence from the post: marks ['vm_vr_0_0', 'vm_vr_0_1'], regions [] — the Differential's accept is a wholesale PATCH from the client's store, which did not carry the ledger's committed marks | [006-differential-proposal](screenshots/006-differential-proposal.png) [007-differential-review](screenshots/007-differential-review.png) [008-differential-accepted](screenshots/008-differential-accepted.png) |
| `relation` | **pass** |  | 5.1 |  | [009-relation-drawn](screenshots/009-relation-drawn.png) [010-relation-refused](screenshots/010-relation-refused.png) |
| `plan` | **pass** |  | 1.4 |  | [011-plan-proposed](screenshots/011-plan-proposed.png) [012-plan-accepted](screenshots/012-plan-accepted.png) |
| `draft` | **pass** |  | 1.3 |  | [013-draft-quarantined](screenshots/013-draft-quarantined.png) |
| `draft.accept` | **fail** | I | 1.4 | the UI offers no way to target an existing manuscript or chapter — Accept always opens a new manuscript (the API accepts manuscript_id/chapter_id; see profile `api.target_manuscript`) | [014-draft-accepted](screenshots/014-draft-accepted.png) |
| `api.target_manuscript` | **pass** |  | 0.0 |  |  |
| `writer` | **pass** |  | 2.8 |  | [015-writer-open](screenshots/015-writer-open.png) [016-writer-quarantine](screenshots/016-writer-quarantine.png) [017-writer-alignment](screenshots/017-writer-alignment.png) [018-writer-accepted](screenshots/018-writer-accepted.png) [019-writer-recall](screenshots/019-writer-recall.png) [020-writer-revised](screenshots/020-writer-revised.png) |
| `movement` | **unavailable** | J/K | 0.0 | no movement proposal/accept or axis inspection route exists on this base (movement_axes is written by scripts only); the Atlas has no movement mode |  |
| `profile.lost_response` | **fail** | B | 3.1 | a retried relation yielded 2 edge(s) and {'6a89b0d6643201f69d0a852c': 2, '6a89b0d6643201f69d0a852d': 2} mark(s) — the route has no idempotency key, so a lost response duplicates the commit |  |
| `profile.restart_mid` | **fail** | I | 1.4 | a restart between the scene insert and the manuscript/atlas updates left an orphan scene (inserted=1, manuscript_changed=False, draft=quarantined); the transition is not atomic and has no recovery |  |
| `profile.stale_tab` | **fail** | B | 5.4 | the stale tab overwrote the newer note: the Atlas carries no revision and the notes route has no precondition | [021-stale-tab-second](screenshots/021-stale-tab-second.png) |
| `profile.unavailable_model` | **pass** |  | 2.4 |  |  |
| `profile.unreadable_image` | **pass** |  | 6.2 |  | [022-unreadable-node](screenshots/022-unreadable-node.png) |
| `profile.injected_writes` | **fail** | B/D/I | 0.9 | a failed write left the transition half-applied: draft.accept → {'scenes': ['sc_fd07128d9802']}; writer.passage.accept → {'scenes': ['sc_4f98b67b72cc']} (no transaction/compensation across documents) |  |
| `a11y` | **pass** |  | 6.0 |  | [023-a11y-canvas-light](screenshots/023-a11y-canvas-light.png) [024-a11y-canvas-dark](screenshots/024-a11y-canvas-dark.png) [025-a11y-edges-reduced-motion](screenshots/025-a11y-edges-reduced-motion.png) |
| `performance` | **pass** |  | 3.8 |  | [026-perf-sixty](screenshots/026-perf-sixty.png) |

## Model / provider receipts

- `gpu_producers` → **fake**
- `capability_probes` → **fake**
- `corpus_actuators` → **fake** (fake::<actuator>)
- `groq_planner` → **fake** (rule_based)
- `argument_planner` → **fake** (vertical-rehearsal-fake)
- `composer` → **fake** (fake/composer)
- `manuscript_renderer` → **fake** (fake/manuscript_renderer)
- `alignment_reader` → **fake** (fake/alignment_reader)
- stage `differential` · orchestrate → status=200, auto_ran=True, planner=groq, weakest_link=0.6, suggestions=2, steps=['light_field', 'shadow_field', 'semantic_read']
- stage `plan` · argument_planner → planner=argument_groq, planner_available=True, claims=2, refusals=[]
- stage `draft` · composer → model=fake/composer, run_id=atlas:atlas_e69cfcf495b8:draft, passages=3
- stage `writer` · manuscript_renderer → status=ok, model=fake/manuscript_renderer, run_id=wrun_76ee2453dec2, refusal=
- stage `writer` · alignment_reader → status=aligned, model=fake/alignment_reader, reading_id=rdg_9cd0f9e85e72, flags=0

## Canonical ids captured

- `walk.save_open`: corpus_id=`corpus_9d6b0bbd5e9b`, atlas_id=`atlas_e69cfcf495b8`, contract_version=`1`
- `atlas.canvas`: atlas_updated_at=`2026-08-22T14:23:25.024145+00:00`
- `relation`: edge_id=`edge_4e072c5dd3fa`, mark_id=`vm_rel_3b9783d0236c`, source_ref=`6a89b0d6643201f69d0a852b:vm_vr_1_1→6a89b0d6643201f69d0a852c:vm_vr_2_1`, epistemic=`interpretive`
- `plan`: claim_ids=`['c0']`, planner=`atlas_accepted`, accepted=`True`, has_challenge=`True`
- `draft`: run_id=`atlas:atlas_e69cfcf495b8:draft`, drafted_at=`2026-08-22T14:23:42.733808+00:00`, version=`1`
- `draft.accept`: manuscript_id=`ms_dd2177c8610f`, chapter_id=`ch_8ab690d6a8d6`, scene_id=`sc_4f98b67b72cc`, accepted_at=`2026-08-22T14:23:44.147858+00:00`
- `api.target_manuscript`: scene_id=`sc_c8d755ef6cc1`
- `writer`: passage_id=`psg_ea426113ee18`, lineage_id=`lin_37cbea88f6eb`, block_id=`blk_c14a68c9c5b1`, scene_id=`sc_4f98b67b72cc`, version_id=`ver_b9b3e3e2b8d6`, operator_id=`op_7272a82d454e`, operator_version=`1`
- `writer.revision`: version_ids=`['ver_b9b3e3e2b8d6', 'ver_cc34818f63bf']`, revised_from=`lin_37cbea88f6eb@v1`

## Refusals

- `relation`: reason=same_node, detail=a relation needs two different images; this line starts and ends on one, path=api(same-node), writes=0
- `draft.accept`: reason=already_accepted, status=409
- `profile.unavailable_model`: reason=None, seam=scout, writes=0

## Operations / retries / conflicts

- `differential`: op=accept, method=PATCH, url=http://127.0.0.1:64919/api/v1/posts/6a89b0d6643201f69d0a852a, status=200
- `profile.lost_response`: op=relation, attempt=1, status=500, fault_fired=True
- `profile.lost_response`: op=relation, attempt=2, status=200, edge=edge_e69383ef39ff, refused=None
- `profile.restart_mid`: op=draft.accept, status=None, backend_exit=True, restart_seconds=1.12
- `profile.injected_writes`: transition=relation.commit, fault=posts.update_one, fired=True, status=500, changed={}, detail=None
- `profile.injected_writes`: transition=draft.accept, fault=manuscripts.update_one, fired=True, status=500, changed={'scenes': ['sc_fd07128d9802']}, detail=None
- `profile.injected_writes`: transition=writer.passage.accept, fault=writer_passage_versions.insert_one, fired=True, status=500, changed={'scenes': ['sc_4f98b67b72cc']}, detail=None

## Performance (60 images)

| measure | ms / MB | budget |
|---|---|---|
| initial_hydration | 630.7 | 6000 |
| memory_after_hydration_mb | 5.8 |  |
| pan | 206.8 | 1500 |
| zoom | 335.9 | 1500 |
| frames_per_second_idle | 84 |  |
| mode_switch | 67.1 | 2500 |
| notes_save | 642.2 | 3000 |
| mode_switch_back | 38.7 | 2500 |
| memory_after_interaction_mb | 7.1 |  |

## Hashes

- fixture posts before: 70, after: 69, changed: 5
- per-stage timeline in `summary.json` → `evidence.hash_timeline`

## Unexpected mutations

- stage `differential` · post `6a89b0d6643201f69d0a852a`
    - `grounds[0]` added: `None` → `{"actor":"creator","created_at":"2026-08-22T14:23:33.532Z","detector":null,"ground_type":"field","id":"gnd_mt4gxsws_0","instrument_role":"light_field","label":"…(+61)`
    - `updated_at` changed: `2026-08-22 14:23:18.577000` → `2026-08-22 14:23:34.341000`
    - `visual_layers` added: `None` → `[]`
    - `visual_marks[0].created_at` added: `None` → `2026-08-22T14:23:33.532Z`
    - `visual_marks[0].derived_from` added: `None` → `vm_sug_light_field_brush_field_`
    - `visual_marks[0].epistemic_status` added: `None` → `uncertain`
    - `visual_marks[0].geometry.kind` changed: `path` → `soft_mask`
    - `visual_marks[0].geometry.points` removed: `[[0.12,0.22],[0.88,0.3]]` → `None`
    - `visual_marks[0].geometry.strokes` added: `None` → `[{"points":[[0.5,0.5]],"radius":0.05}]`
    - `visual_marks[0].id` changed: `vm_vr_0_0` → `vm_mt4gxsws_0`
    - `visual_marks[0].label` changed: `fixture gesture line 0` → ``
    - `visual_marks[0].linked_action_ids` added: `None` → `[]`
    - `visual_marks[0].linked_ground_ids[0]` added: `None` → `gnd_mt4gxsws_0`
    - `visual_marks[0].linked_percept_ids` added: `None` → `[]`
    - `visual_marks[0].provenance` added: `None` → `{"adapter":"light_field","latency_ms":null,"matched":[],"model":"fake::light_field","planner":null,"producer":null,"prompt_excerpt":null,"run_id":"wire::b6b7d5f…(+45)`
    - `visual_marks[0].role` changed: `gesture_line` → `light_field`
    - `visual_marks[0].source_ref` removed: `vm_vr_0_0` → `None`
    - `visual_marks[0].style` added: `None` → `{}`
    - `visual_marks[0].type` changed: `trace_mark` → `brush_field`
    - `visual_marks[0].updated_at` added: `None` → `2026-08-22T14:23:33.532Z`
    - `visual_marks[1]` removed: `{"geometry":{"kind":"path","points":[[0.12,0.36],[0.88,0.44]]},"id":"vm_vr_0_1","label":"fixture contour edge 0","linked_ground_ids":[],"role":"contour_edge","s…(+104)` → `None`

## Stack

- boot: {'mongod': 0.79, 'backend': 1.11, 'vite_build': 4.08, 'frontend': 0.26}  · backend restarts: 1
- note: backend started with `PORT` set to disable forced TLS on the local mongod URI (backend/database.py couples TLS to a Render env var)
- note: frontend served from a production Vite build (4.08s)
- note: finding: in Canvas mode the React Flow pane is 1440x0 (the wrapper `<div className={undefined}>` around AtlasCanvas has no flex sizing), so pointer input lands on `.atlas-shell`; gestures are rehearsed in Plan mode, where `.atlas-with-plan` gives the same renderer a height
- note: finding: a post whose image URL is dead reads as `readable: true` in the Atlas view — readability is 'post exists', not 'image fetches'

## Preserved for inspection

- mongod_dbpath: `/var/folders/03/5t7y_fkx52d03zdcmdgnl1x40000gn/T/vertical-rehearsal-mongo-7mbqzysk`
- reopen: `mongod --dbpath /var/folders/03/5t7y_fkx52d03zdcmdgnl1x40000gn/T/vertical-rehearsal-mongo-7mbqzysk --port 64911`
