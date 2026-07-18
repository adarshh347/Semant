# VISION-EVALSET-001 — evaluation pack (created vs proposed)

**Date:** 2026-07-18 · **Mode:** evaluation documentation + fixtures only. Ran in
parallel with `VISION-CODE-AUDIT-001`. **No** application/backend/frontend code,
package, model checkpoint, model config, or stored post data was changed; no paid API
was called; no post was re-dissected. Two read-only Mongo censuses and seven read-only
Cloudinary fetches (the curator's own assets, snapshotted locally) were the only
non-file actions. The code-audit report was not touched.

A small, hard, Semant-specific corpus to compare **segmentation · mask refinement ·
domain parsing · perceptual analyzers · VLM semantics** on evidence that matters to the
image → Region → Ground → Percept loop — chosen against Semant's real library (heritage
sculpture, painting, devotional prints, portrait photography), not against COCO.

## Isolated files created (all under `architecture-lab/vision-eval-001/`)

```
README.md                    ← this file (deliverable 6)
corpus-manifest.md           ← deliverable 1: images, domains, reasons, slot coverage
targets.yaml                 ← deliverable 2: critical evidence targets (validated YAML)
rubric.md                    ← deliverable 3: 0–3 scoring + hard gates
benchmark-matrix.md          ← deliverable 4: empty comparison scaffold
gaps.md                      ← deliverable 5: fixtures/annotations still needed
fixtures/
  PROVENANCE.md              ← source provenance, dims, domain-guess accuracy
  source/                    ← 7 confirmed real images (staged snapshots)
    a_5sculpt_695be6c9.jpg   b_product_695be786.jpg  c_photo_695be794.jpg
    d_fashion_695be8ba.jpg   e_arch_695be77e.jpg     f_product_695be7fa.jpg
    g_dataset_001.png
  masks/README.md            ← gold-mask layout (empty; see gaps.md §2)
```

Nothing outside this directory was created or modified.

## What was CREATED (real, usable now)

- **7 confirmed images**, each viewed and characterised, staged under `fixtures/source/`
  with full provenance and exact dimensions. They already satisfy **11** corpus slots
  outright and partially cover **5** more, and fully anchor the perceptual group.
- **Authored critical-evidence targets** for all 7 (36 targets total) in `targets.yaml`
  — real, not templates — including the REGION-GEOMETRY-001 five-sculpture regression
  with named per-head separation + sliver sentinels.
- **A complete scoring rubric** (`rubric.md`): 0–3 across Geometry, Semantics,
  Perceptual, Product-circulation, Runtime, plus **7 hard gates** for evidence
  corruption (anchor imprisonment, crushed slivers, label-driven mutation, fabricated
  boundaries, persistence/render drift, wrong coordinate frame, paratext-as-evidence)
  and a lexicographic ranking rule (any hard fail sinks a candidate).
- **A ready-to-fill benchmark matrix** (`benchmark-matrix.md`) with the candidate
  roster keyed to the audit's role map and the gold-subset rows pre-listed.
- **Two evaluation findings that fell out of curation** (already actionable):
  1. `classify_domain` is wrong on **4 of 6** region-posts — heritage sculpture and a
     Vishnu lithograph are both called `product` — corroborating the audit's
     "DomainProfile implicit & unreliable."
  2. The confirmed fixtures **cannot** test the audit's EXIF defect (P0-1): Cloudinary
     bakes orientation on delivery, so the risk lives on the *upload* path only — a
     separate raw fixture is required (`gaps.md` §4).

## What remains PROPOSED (needs you)

- **15 proposed image slots** (10 genuinely open + 5 optional-dedicated) — selection
  criteria + acceptance tests per slot in `gaps.md` §1. Fastest path: I generate a
  read-only **contact sheet** of your 121 untagged posts, you tag post_ids to slots.
- **Gold reference masks** (6–8) — deliberately not minted here (would require running a
  candidate model and human review). Method + storage layout in `gaps.md` §2.
- **Hardware / decision inputs** — VRAM, deploy-target GPU, serverless provider, a
  working Groq vision model id, the Ultralytics AGPL call. These gate the harness and
  the first candidates (`gaps.md` §3, audit §5).
- **One EXIF upload-path fixture** (`gaps.md` §4).

## Stop condition honored
The pack is complete; **no candidate models were run**. Per the brief, the audit + the
hardware decision determine the benchmark harness and the first candidates. Next action
is yours: choose which proposed slots to fill (or ask for the contact sheet), and settle
the hardware inputs.
