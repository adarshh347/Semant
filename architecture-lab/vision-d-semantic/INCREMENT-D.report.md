# VISION-D — Semantic orchestration — increment report

**Branch:** `feat/vision-d-semantic` · **Date:** 2026-07-19 · **Gates:** D0–D5, all PASS.

## The one idea

Turn the VLM into an **interpreter of specialist-produced evidence**, not a geometry
generator. It may name, qualify, relate, question and globally read the candidate masks the
detector / SAM / SegFormer produced — but it can never emit, clip, translate, resize,
parent-by-label or otherwise mutate a pixel. Geometry changes only through the
detector / SAM / Refine path; a semantic read changes assertions only.

## Gate-by-gate

| Gate | What shipped | Commit |
|------|--------------|--------|
| **D0** | Geometry-forbidding semantic contract (Pydantic `extra="forbid"` at every level; `enforce_candidate_ids`; `has_geometry_key`) + evidence-backed provider decision (OpenRouter `gpt-4o-mini`; Groq dropped all vision) | `0a33d66` |
| **D1** | Evidence packet — whole image + numbered mask contact sheet with stable candidate ids, provenance, curator labels, intent | `7673529` |
| **D2** | Semantic pass through the orchestrator's REMOTE slot + safe persistence (`post.semantics`, separate from geometry); content-addressed cache; curator state preserved; **geometry byte-invariant on rerun** | `6f0bdb9` |
| **D3** | Two distinct scopes (candidate-bound vs image-global); relations are endpoint-citing proposals that can never become parenting/containment; painting may declare candidates insufficient → Differential Grounds | `a9111ab` |
| **D4** | Real curator UX (Differential "Read" tool): request/re-read with intent; alternatives / confidence / provenance; accept / edit / reject / tentative; relation proposals; "needs better evidence" launches Refine; loading / cancel / unavailable / timeout / retry states; browser-verified | `56cc564` |
| **D5** | Adversarial regression — geometry smuggling, prompt injection, malformed output, unknown & duplicate ids, timeout, five-sculpture id-binding, ambiguity, source-level no-parent/no-clip; XSS-safe UI; persistence hardened as defense-in-depth | `fb6be2e` |

## Invariants proven

- **Geometry byte-for-byte unchanged** across failed and successful reads and live reruns —
  `region_annotations` sha256 identical (RLE / polygons / bbox / `geometry_rev` untouched).
- **Assertions stored separately** with full provenance and sticky curator state
  (accepted / rejected / overridden / tentative survive reruns; the curator's text is never
  overwritten).
- **The VLM only speaks about ids it was given** — unknown ids are dropped and reported;
  duplicates collapse deterministically.
- **No geometry is representable** end-to-end — the schema forbids it and the persistence path
  references no parenting/clipping helper.

## Verification
- Backend: **161 passed** (D-suite: `test_semantic_pass.py` 7, `test_vision_d3.py` 4,
  `test_vision_d5.py` 10). Frontend `npm run build` clean.
- Live: real `gpt-4o-mini` reads on the Pietà (name/relate/global); browser-verified curator
  flow (accept/edit persisted; live re-read left decisions + geometry intact); XSS-safe.

## Forbidden in D — confirmed absent
No DINOv2, no texture/material heads, no Depth Anything, no FashionCLIP backfills, no
cross-corpus retrieval. (Increment E not started.)

## Known gap
Collage / fashion **in-browser** reads were not exercised — the connected DB has no dissected
collage/fashion post to read. The path is domain-agnostic and the adversarial suite is
domain-independent; a live read for those domains awaits real dissected evidence.
