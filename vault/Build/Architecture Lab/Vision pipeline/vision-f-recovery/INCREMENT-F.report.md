# VISION-F — Recovery, backfill & full circulation — increment report

**Branch:** `feat/vision-f-recovery` (off `main` after PR #55) · **Date:** 2026-07-20 ·
**Gates:** F0–F7. **Representative batch executed & reviewed; corpus-wide expansion presented, not run.**

## The mandate

Turn the A–E vision architecture into a trustworthy corpus-level system: audit and repair legacy
visual evidence, run controlled jobs in dependency order (audit → backup → plan → repair → review →
refresh → index → circulation), preserve every curator identity, and prove full circulation — with
mutation gated on backup + dry-run + explicit approval, and no silent corpus backfill.

## Commits per gate

| Gate | Commit | Summary |
|------|--------|---------|
| **F0** | `ce26f35` | Read-only corpus audit + smoke test (zero writes) |
| **F1** | `739ccf8` | Scoped backup, migration ledger, per-post rollback (restore drill) |
| **F2** | `cdb0c3b` | Live capability matrix + unavailable→skip guard |
| **F3** | `976bd80`, `7784e59` | Representative-batch geometry recovery (approved, staged) |
| **F4** | `53a8d4c` | Dependent semantic + embedding refresh (resumable, no duplicates) |
| **F5** | `ff7a0b4` | Full-circulation acceptance through real routes (6 fixtures) |
| **F6** | `f442fca` | Retrieval quality after recovery (identity @5 55%→68%) |
| **F7** | *(this)* | Expansion decision — presented, not run |

## Audit & mutation manifests

- **Audit** (`F0-audit/manifest.json`, sha256 `7c209e64…`, zero writes): 127 posts, 9 dissected /
  118 undissected, 42 regions = **15 mask / 9 polygon / 18 box**, **0 coordinate-corruption**
  fingerprints, 4 detached grounds, 1 semantics post (Pietà, 2 curated). Live re-evaluation
  overturned the old "many corrupted posts" assumption — the surface was **legacy geometry**, not
  damage.
- **Mutation ledger** (`F1-backup/ledger.json`): `{committed: 6→(4 recover + 2 detach), skipped: 2,
  planned: 3}` after the representative batch.

## Backup / restore evidence

`F1-backup/backup-manifest.json` (sha256 `8044f365…`): 9 posts + 97 embeddings snapshot, per-post
identity hashes. Restore drill on a **disposable copy**: a destructively-wrecked post was restored
to its exact curator identity byte-for-byte; a second restore duplicated nothing; **live corpus
verified untouched**. Per-post rollback is available for every mutated post.

## Before/after identity & geometry traces

| post | before | after | curator-only hash |
|------|--------|-------|-------------------|
| `695be6c9` five-sculpture | 0 masks (9 box + 1 poly) | **10/10 masks** (9 SAM + 1 derive) | `03fdc725…` **preserved** |
| `695be8ba` fashion | 0 masks (9 box + 7 poly) | **16/16 masks** | `1484f0dc…` **preserved** |
| `695be786` architecture | 7 masks, 2 orphan grounds | 7 masks + **2 detached flagged** | `7be93710…` preserved |
| `695be794` figurative | 1 mask, 2 orphan grounds | 1 mask + **2 detached flagged** | `10e75ab9…` preserved |
| `6a5b91ec` / `695be77` | canonical | unchanged (skipped) | — / Pietà **2 curated preserved** |

All Region ids stable; `geometry_rev` bumped only where geometry changed; old geometry saved for
rollback; **no slivers / anchor prison**, registration holds (`F3-evidence/sculpture_recovered_masks.png`).

## Preserved curator / Percept / Mention counts + hashes

Corpus-wide: **5 creator regions, 2 curated assertions, 24 grounds, 5 percepts** — all preserved;
the only intentional curator-visible change is **4 grounds flagged `detached`** (visible, not
deleted; excluded from the curator invariant as recovery metadata). Every mutated post's
curator-only hash is unchanged (table above).

## Runtime / resource / failure measurements

- Capability matrix (F2): YOLO 826 ms, SAM 884 ms, SegFormer 1293 ms, DINOv2 1821 ms loads (all
  unloaded); semantic structured output ready; ModelManager cancel honoured.
- Recovery: SAM box-refine ~12 s/box (full-res mask→polygon extraction dominates), 0 failures.
- Refresh (F4): 2 posts / 26 regions re-embedded in **~13 s, peak 107 MiB VRAM**, 0 failures,
  storage flat (rows replaced in place, 97→97).

## Browser evidence

F5 exercised all 6 acceptance fixtures through the **real product routes in-process** (mask recall,
find-similar, exact masked crops, cross-post neighbour Pietà→fashion, curator preservation) with
correct geometry-revision semantics. **Live screenshot capture was blocked this session** (post-
reboot environment kills long-lived server processes; app startup proven healthy). The UI rendering
these routes was **browser-verified earlier this session** — E5 Find-similar on this five-sculpture
post (`../vision-e-embeddings/E5-evidence/find-similar-panel.png`) and the D4 semantic UX; the
recovered masks now flow through those verified surfaces.

## Retrieval comparison vs E

Identity **same-label@5 55% → 68%** (+13 pt), context @1 18% → 32%; mask pooling (37/38 vectors)
isolates evidence better than box crops. Unchanged: same-image bias (cross-post@1 4/38 — corpus
density). OpenCLIP/fusion **stay deferred**.

## Remaining unresolved / detached evidence

- **4 detached grounds** (2 posts) flagged, awaiting curator reattach-or-remove.
- **3 remaining dissected posts** (1 box-legacy region) — trivial recovery, not yet run (approval).
- **118 undissected posts** — expansion, not run (F7 decision below).

## Recommendation on wider backfill

**Do not run the 118-post expansion as an automatic corpus-wide backfill.** Compute is cheap
(~50 min, ~3.6 MB) but the binding cost is **~551 regions of curator review** the quality gate
requires. Stage expansion in **bounded, curator-reviewed batches through the same ledger**, stop on
threshold breaches. Finish the 3 remaining dissected posts first (trivial). No new models.

## Post-F horizon
Increment **G**: bounded reviewed corpus dissection (review is the gate, not compute); revisit
OpenCLIP / score-fusion only against a genuinely multi-domain corpus; address same-image bias and
per-domain material/colour de-biasing.

## Forbidden in F — confirmed absent
No new specialist models, no DTD/MINC heads, no Depth Anything, no automatic Motifs/Relations, no
Atlas construction, no unrelated UI redesign, **no silent corpus-wide backfill**.

**Not merged — awaiting review.**
