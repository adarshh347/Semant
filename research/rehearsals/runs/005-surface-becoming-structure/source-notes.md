# 005 — Source notes

## The subject

Post `695be784a9ea58f1b6aef5ec`, read **read-only** from the live `visualDictionaryDB`. Image
downloaded once from `photo_url` and frozen locally.

- `fixtures/005-surface-becoming-structure/turquoise-tile-revetment.jpg`
- 453 × 680 JPEG, 150 535 bytes
- `sha256: b3d660ce9bdcae48c50c64410423ace3f8fa9887aebdd65e13fe91da52716f16`

**`reproduction_vs_depiction: depiction`.** A photograph of an actual tiled interior — not a plate,
scan, collage, or reproduction of another artwork. No grain or texture overlay detected, unlike the
post-processed Pietà used by run 002F.

**What it actually shows, from looking:** a revetted niche with a semi-domed head; three arched
recesses, the central one holding a small lattice window that is the only warm-lit element in the
frame; three square panels below, each centred on a circular rosette medallion; and a fine
star-and-cross dado band along the base, above a paved floor. Predominantly turquoise, aniconic
throughout. The tilework is visibly damaged and patched in places, especially at the upper left.

**Metadata status:** no title, no description, no catalogue data. Culture and period are **not**
established anywhere in this rehearsal. The model volunteered "a classic Islamic architectural
device" and "the central mihrab niche"; both were unrequested, are unverified, and are load-bearing
on nothing here. `no_iconographic_identification: true` was set in the manifest.

## Why this fixture

Portfolio row A4 required a **non-figurative** subject. Its original nominee (`6a5b91ec`) turned
out to be a photographed **pencil drawing of figures** — the fourth portfolio fixture description
found to be inherited detector output (its `domain_profile` reads "painting" at 0.98). This
substitute restores the batch's only aniconic slot: runs 002, 002F, 003 and 004 were all figurative.

**Clean slate:** 0 regions, 0 grounds, 0 percepts, 0 embeddings, 0 vision_runs. Nothing
pre-annotated to bias the reading — unlike run 003, where the persisted `wall`/`floor` labels were
themselves the subject.

**Native resolution.** At 453 × 680 the image sits under the 768 px probe cap, so A4 ran
**unscaled**. This deliberately repairs A3's confound, where a three-image call forced a 256 px
downscale and the model then mis-described its own subject.

## Pre-registration

The manifest recorded, **before any probe ran**, three competing organisers visible in the image:
the warm-lit lattice window on the centre axis; the dado band's change to a finer pattern system;
and the damage/patching. It also recorded in advance that a **stall was a live possibility**,
because pattern and built form announce many of the same divisions here.

This ordering matters: the finding cannot have been retrofitted. It also means the reading was
primed toward the dado line — see `critique.md` §5.

## Reproducing the measurement

The 149 % edge-density jump at y ≈ 0.765 is model-free and recomputable from the frozen fixture:
convert to greyscale, take `|diff|` along the x axis as an edge-density proxy, average it over 34
equal horizontal bands, and find the largest relative change between adjacent bands. Bands at
y = 0.735 / 0.765 / 0.794 give 18.00 / 44.87 / 44.93.

## No text source

No theoretical text loaded. `source_pressures` is empty **by choice**: R8 concerns the relation
between ornament and composition, and the archive's available texts on surface and material are
weighted toward phenomenology, which would have supplied the answer rather than tested it. Run 004
set the precedent that an empty `source_pressures` with a stated reason is a legitimate result.

## Model

`qwen/qwen3.6-27b` on Groq, `reasoning_effort: "none"`. **2 live calls**, 35 s apart, no retries, no
provider failures. Both `finish_reason: "stop"`, no `<think>` leakage. Raw text frozen verbatim; no
JSON parsing attempted, so probe 2's unrequested markdown scaffolding and ✅ block caused no harm.

Neither prompt mentioned faces, eyes, gaze, or bodies — this is what made A4 a valid test of
spark-06.

## Honesty notes

- Probe 2's question offered exactly two options and named the pattern option second; its
  *location* is independently confirmed by measurement, its *attribution* is not.
- Probe 2 described the dado band as separating the wall from the floor; there are two lines there,
  not one.
- The spark-06 correction rests on a **negative** result — weaker than a positive one.
- No production document was written at any point.
