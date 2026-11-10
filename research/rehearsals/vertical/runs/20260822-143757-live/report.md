# Vertical rehearsal — 20260822-143757-live

**Gate:** `fail`  ·  mode `live`  ·  profile `default`  ·  base `4aa08e33f6d6` on `test/atlas-writer-vertical-rehearsal`  ·  fakes `ml_only`

**Lanes still preventing the full pass:** `A`, `B`, `B/D/I`, `D`, `I`, `J/K`

## Assertions

| # | assertion | status | lane | detail | evidence |
|---|---|---|---|---|---|
| A1 | no quarantined prose appears in canon/export | **fail** | D | 1 uncommitted passage(s) checked against every manuscript export by text and every scene block by passage id; 2 leak(s) — the scene block cites a passage that is still `committed: false`: the passage accept wrote the scene before its version insert failed (profile.injected_writes), so an interrupted accept puts quarantined prose into canon | `stage:writer`, `stage:draft`, `db:writer_passages`, `db:manuscripts/export`, `leak:{'manuscript': 'ms_db60326a3307', 'passage': 'psg_fc6b6401f679'}`, `leak:{'manuscript': 'ms_db60326a3307', 'scene': 'sc_be4e278d9bf4', 'block': 'blk_37e305b2a8e4', 'passage': 'psg_fc6b6401f679'}` |
| A2 | no Atlas arrangement/notes contain percept truth | **pass** |  | 2 Atlas document(s) scanned for forbidden node/edge/note keys; 0 offender(s) | `db:atlases`, `stage:atlas.canvas`, `stage:atlas.light_table`, `stage:relation` |
| A3 | every visible live relation/movement/citation hydrates from canonical evidence | **pass** |  | 3 live relation edge(s) re-read from the ledger; 0 without the mark committed in every post it spans. Movement/citation edges: no movement proposal/accept or axis inspection route exists on this base (movement_axes is written by scripts only); the Atlas has no movement mode | `stage:relation`, `stage:movement`, `api:/atlas/{id}/view` |
| A4 | every refusal writes nothing | **pass** |  | 3 refusal(s) captured with the write log read before and after; 0 wrote | `stage:relation`, `stage:profile.unavailable_model`, `stage:draft.accept`, `evidence:refusals` |
| A5 | every retry yields one canonical result | **fail** | B | a retried relation yielded 2 edge(s) and {'6a89b46e90a051a7c96de06c': 2, '6a89b46e90a051a7c96de06d': 2} mark(s) — the route has no idempotency key, so a lost response duplicates the commit | `stage:profile.lost_response` |
| A6 | stale revisions never overwrite | **fail** | B | the stale tab overwrote the newer note: the Atlas carries no revision and the notes route has no precondition | `stage:profile.stale_tab`, `shot:screenshots/021-stale-tab-second.png` |
| A7 | every old Writer version/operator provenance remains resolvable | **pass** |  | 2 version(s) of lineage lin_4c78a4876958: [{'version': 1, 'resolves': True, 'operators': 1, 'operators_resolve': True}, {'version': 2, 'resolves': True, 'operators': 1, 'operators_resolve': True}] | `stage:writer`, `db:writer_passage_versions`, `db:writer_operators` |
| A8 | evidence refs survive Atlas → Writer → revision → export | **fail** | I | {"atlas_draft_passages": 3, "scene_blocks": 12, "scene_blocks_with_evidence_refs": 2, "block_keys": ["color", "content", "id", "lineage_id", "origin", "provenance", "type", "version"], "scene_mentions_run_id": false, "writer_versions_with_provenance": 2, "writer_versions": 2, "export_carries_lineage_or_version_refs": false, "export_keys": ["content", "format", "manuscript_id", "title"]} — the mark | `stage:draft`, `stage:draft.accept`, `stage:writer`, `db:scenes`, `db:writer_passage_versions`, `api:/manuscript/{id}/export` |
| A9 | fixture posts change only at explicitly accepted evidence steps | **fail** | B | 19 stage(s) hashed every fixture post; 17 write(s) declared by accepting stages; 1 unexpected | `evidence:hash_timeline`, `evidence:expected_writes`, `evidence:unexpected`, `unexpected:differential:6a89b46e90a051a7c96de06a` |
| A10 | all unexpected mutations are printed as a field-level diff | **pass** |  | 1 unexpected mutation(s), each carried with its path-level diff in summary.json `evidence.unexpected[].diff` and in the report | `evidence:unexpected`, `report:Unexpected mutations` |

## Stages

| stage | status | lane | seconds | detail | screenshots |
|---|---|---|---|---|---|
| `walk.save_open` | **fail** | A | 4.4 | the saved walk cannot be opened from the index: the client's `atlasService.create()` drops `corpus_id` and the route answers 400 (an Atlas needs a corpus: pass post_ids or a run_id); the Atlas was opened over the same walk through the API so the circuit could continue | [001-walk-picked](screenshots/001-walk-picked.png) [002-walk-opened](screenshots/002-walk-opened.png) |
| `atlas.canvas` | **fail** | A | 4.4 | in Canvas mode the React Flow pane renders 1440x0 and a click on a node reaches `.atlas-shell` — the canvas cannot be panned, zoomed, dragged or connected in its own mode; the arrangement save was proven in Plan mode instead | [003-canvas-mode](screenshots/003-canvas-mode.png) [004-canvas-after-drag](screenshots/004-canvas-after-drag.png) |
| `atlas.light_table` | **pass** |  | 2.8 |  | [005-light-table-note](screenshots/005-light-table-note.png) |
| `differential` | **fail** | B | 17.1 | accepting one proposal removed committed evidence from the post: marks ['vm_vr_0_0', 'vm_vr_0_1'], regions [] — the Differential's accept is a wholesale PATCH from the client's store, which did not carry the ledger's committed marks | [006-differential-proposal](screenshots/006-differential-proposal.png) [007-differential-review](screenshots/007-differential-review.png) [008-differential-accepted](screenshots/008-differential-accepted.png) |
| `relation` | **pass** |  | 4.4 |  | [009-relation-drawn](screenshots/009-relation-drawn.png) [010-relation-refused](screenshots/010-relation-refused.png) |
| `plan` | **pass** |  | 5.4 |  | [011-plan-proposed](screenshots/011-plan-proposed.png) [012-plan-accepted](screenshots/012-plan-accepted.png) |
| `draft` | **pass** |  | 6.4 |  | [013-draft-quarantined](screenshots/013-draft-quarantined.png) |
| `draft.accept` | **fail** | I | 2.3 | the UI offers no way to target an existing manuscript or chapter — Accept always opens a new manuscript (the API accepts manuscript_id/chapter_id; see profile `api.target_manuscript`) | [014-draft-accepted](screenshots/014-draft-accepted.png) |
| `api.target_manuscript` | **pass** |  | 7.8 |  |  |
| `writer` | **pass** |  | 18.1 |  | [015-writer-open](screenshots/015-writer-open.png) [016-writer-quarantine](screenshots/016-writer-quarantine.png) [017-writer-alignment](screenshots/017-writer-alignment.png) [018-writer-accepted](screenshots/018-writer-accepted.png) [019-writer-recall](screenshots/019-writer-recall.png) [020-writer-revised](screenshots/020-writer-revised.png) |
| `movement` | **unavailable** | J/K | 0.0 | no movement proposal/accept or axis inspection route exists on this base (movement_axes is written by scripts only); the Atlas has no movement mode |  |
| `profile.lost_response` | **fail** | B | 9.3 | a retried relation yielded 2 edge(s) and {'6a89b46e90a051a7c96de06c': 2, '6a89b46e90a051a7c96de06d': 2} mark(s) — the route has no idempotency key, so a lost response duplicates the commit |  |
| `profile.restart_mid` | **fail** | I | 22.3 | a restart between the scene insert and the manuscript/atlas updates left an orphan scene (inserted=1, manuscript_changed=False, draft=quarantined); the transition is not atomic and has no recovery |  |
| `profile.stale_tab` | **fail** | B | 7.2 | the stale tab overwrote the newer note: the Atlas carries no revision and the notes route has no precondition | [021-stale-tab-second](screenshots/021-stale-tab-second.png) |
| `profile.unavailable_model` | **pass** |  | 2.3 |  |  |
| `profile.unreadable_image` | **pass** |  | 14.5 |  | [022-unreadable-node](screenshots/022-unreadable-node.png) |
| `profile.injected_writes` | **fail** | B/D/I | 7.9 | a failed write left the transition half-applied: draft.accept → {'scenes': ['sc_b1b7e2697557']}; writer.passage.accept → {'scenes': ['sc_be4e278d9bf4']} (no transaction/compensation across documents) |  |
| `a11y` | **pass** |  | 18.0 |  | [023-a11y-canvas-light](screenshots/023-a11y-canvas-light.png) [024-a11y-canvas-dark](screenshots/024-a11y-canvas-dark.png) [025-a11y-edges-reduced-motion](screenshots/025-a11y-edges-reduced-motion.png) |
| `performance` | **skipped** |  | 0.0 | performance profile runs offline; pass --perf-in-live |  |

## Model / provider receipts

- `gpu_producers` → **fake**
- `capability_probes` → **fake**
- `corpus_actuators` → **fake** (fake::<actuator>)
- `groq_planner` → **live** (groq) — credential `GROQ_API_KEY` present
- `argument_planner` → **live** (groq) — credential `GROQ_API_KEY` present
- `composer` → **live** (groq) — credential `GROQ_API_KEY` present
- `manuscript_renderer` → **live** (groq) — credential `GROQ_API_KEY` present
- `alignment_reader` → **live** (groq) — credential `GROQ_API_KEY` present
- `semantic_annotator` → **live** (openrouter) — credential `OPENROUTER_API_KEY` present
- stage `differential` · orchestrate → status=200, auto_ran=True, planner=groq, weakest_link=0.6, suggestions=1, steps=['light_field']
- stage `plan` · argument_planner → planner=argument_groq, planner_available=True, claims=2, refusals=[]
- stage `draft` · composer → model=openai/gpt-oss-120b, run_id=atlas:atlas_750fc8a9cfa4:draft, passages=3
- stage `writer` · manuscript_renderer → status=ok, model=openai/gpt-oss-120b, run_id=wrun_45d65ea22c62, refusal=
- stage `writer` · alignment_reader → status=aligned, model=openai/gpt-oss-120b, reading_id=rdg_cd59b0dd7e05, flags=0

## Canonical ids captured

- `walk.save_open`: corpus_id=`corpus_ff4ddaffb0d6`, atlas_id=`atlas_750fc8a9cfa4`, contract_version=`1`
- `atlas.canvas`: atlas_updated_at=`2026-08-22T14:38:49.194980+00:00`
- `relation`: edge_id=`edge_7059a6ec143d`, mark_id=`vm_rel_808fd2b44523`, source_ref=`6a89b46e90a051a7c96de06b:vm_vr_1_1→6a89b46e90a051a7c96de06c:vm_vr_2_1`, epistemic=`interpretive`
- `plan`: claim_ids=`['c0']`, planner=`atlas_accepted`, accepted=`True`, has_challenge=`False`
- `draft`: run_id=`atlas:atlas_750fc8a9cfa4:draft`, drafted_at=`2026-08-22T14:39:26.116970+00:00`, version=`1`
- `draft.accept`: manuscript_id=`ms_db60326a3307`, chapter_id=`ch_4fb595e281d9`, scene_id=`sc_be4e278d9bf4`, accepted_at=`2026-08-22T14:39:28.332003+00:00`
- `api.target_manuscript`: scene_id=`sc_34c0f89ec7f4`
- `writer`: passage_id=`psg_3f153af5223d`, lineage_id=`lin_4c78a4876958`, block_id=`blk_e7ade883561e`, scene_id=`sc_be4e278d9bf4`, version_id=`ver_77f373c521ea`, operator_id=`op_a5adf39fbdf5`, operator_version=`1`
- `writer.revision`: version_ids=`['ver_77f373c521ea', 'ver_fe2c926bed44']`, revised_from=`lin_4c78a4876958@v1`

## Refusals

- `relation`: reason=same_node, detail=a relation needs two different images; this line starts and ends on one, path=api(same-node), writes=0
- `draft.accept`: reason=already_accepted, status=409
- `profile.unavailable_model`: reason=None, seam=scout, writes=0

## Operations / retries / conflicts

- `differential`: op=accept, method=PATCH, url=http://127.0.0.1:50808/api/v1/posts/6a89b46e90a051a7c96de06a, status=200
- `profile.lost_response`: op=relation, attempt=1, status=500, fault_fired=True
- `profile.lost_response`: op=relation, attempt=2, status=200, edge=edge_05cd868f1c6d, refused=None
- `profile.restart_mid`: op=draft.accept, status=None, backend_exit=True, restart_seconds=6.63
- `profile.injected_writes`: transition=relation.commit, fault=posts.update_one, fired=True, status=500, changed={}, detail=None
- `profile.injected_writes`: transition=draft.accept, fault=manuscripts.update_one, fired=True, status=500, changed={'scenes': ['sc_b1b7e2697557']}, detail=None
- `profile.injected_writes`: transition=writer.passage.accept, fault=writer_passage_versions.insert_one, fired=True, status=500, changed={'scenes': ['sc_be4e278d9bf4']}, detail=None

## Performance (60 images)

| measure | ms / MB | budget |
|---|---|---|

## Hashes

- fixture posts before: 70, after: 69, changed: 5
- per-stage timeline in `summary.json` → `evidence.hash_timeline`

## Unexpected mutations

- stage `differential` · post `6a89b46e90a051a7c96de06a`
    - `grounds[0]` added: `None` → `{"actor":"creator","created_at":"2026-08-22T14:39:08.518Z","detector":null,"ground_type":"field","id":"gnd_mt4hhucm_0","instrument_role":"light_field","label":"…(+61)`
    - `updated_at` changed: `2026-08-22 14:38:38.004000` → `2026-08-22 14:39:09.335000`
    - `visual_layers` added: `None` → `[]`
    - `visual_marks[0].created_at` added: `None` → `2026-08-22T14:39:08.517Z`
    - `visual_marks[0].derived_from` added: `None` → `vm_sug_light_field_brush_field_`
    - `visual_marks[0].epistemic_status` added: `None` → `uncertain`
    - `visual_marks[0].geometry.kind` changed: `path` → `soft_mask`
    - `visual_marks[0].geometry.points` removed: `[[0.12,0.22],[0.88,0.3]]` → `None`
    - `visual_marks[0].geometry.strokes` added: `None` → `[{"points":[[0.5,0.5]],"radius":0.05}]`
    - `visual_marks[0].id` changed: `vm_vr_0_0` → `vm_mt4hhucl_0`
    - `visual_marks[0].label` changed: `fixture gesture line 0` → ``
    - `visual_marks[0].linked_action_ids` added: `None` → `[]`
    - `visual_marks[0].linked_ground_ids[0]` added: `None` → `gnd_mt4hhucm_0`
    - `visual_marks[0].linked_percept_ids` added: `None` → `[]`
    - `visual_marks[0].provenance` added: `None` → `{"adapter":"light_field","latency_ms":null,"matched":[],"model":"fake::light_field","planner":null,"producer":null,"prompt_excerpt":null,"run_id":"wire::bb8e86f…(+38)`
    - `visual_marks[0].role` changed: `gesture_line` → `light_field`
    - `visual_marks[0].source_ref` removed: `vm_vr_0_0` → `None`
    - `visual_marks[0].style` added: `None` → `{}`
    - `visual_marks[0].type` changed: `trace_mark` → `brush_field`
    - `visual_marks[0].updated_at` added: `None` → `2026-08-22T14:39:08.517Z`
    - `visual_marks[1]` removed: `{"geometry":{"kind":"path","points":[[0.12,0.36],[0.88,0.44]]},"id":"vm_vr_0_1","label":"fixture contour edge 0","linked_ground_ids":[],"role":"contour_edge","s…(+104)` → `None`

## Stack

- boot: {'mongod': 1.08, 'backend': 6.62, 'vite_build': 32.45, 'frontend': 1.55}  · backend restarts: 1
- note: backend started with `PORT` set to disable forced TLS on the local mongod URI (backend/database.py couples TLS to a Render env var)
- note: frontend served from a production Vite build (32.45s)
- note: finding: in Canvas mode the React Flow pane is 1440x0 (the wrapper `<div className={undefined}>` around AtlasCanvas has no flex sizing), so pointer input lands on `.atlas-shell`; gestures are rehearsed in Plan mode, where `.atlas-with-plan` gives the same renderer a height
- note: finding: a post whose image URL is dead reads as `readable: true` in the Atlas view — readability is 'post exists', not 'image fetches'

## Preserved for inspection

- mongod_dbpath: `/var/folders/03/5t7y_fkx52d03zdcmdgnl1x40000gn/T/vertical-rehearsal-mongo-uc2fjk89`
- reopen: `mongod --dbpath /var/folders/03/5t7y_fkx52d03zdcmdgnl1x40000gn/T/vertical-rehearsal-mongo-uc2fjk89 --port 50800`
