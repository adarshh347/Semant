# Specialist-model trials — PERCEPTUAL-FORMS-001C

Evidence for which specialist models, if any, should produce the four `deferred` Extent forms
Lane A registered: `extent.soft_field`, `extent.fused_hypothesis`,
`extent.visible_inferred_partition` and `extent.density_field`.

**This is a measurement lane, not an integration lane.** Nothing here is wired into a production
registry, route or service. Every candidate adapter lives inside
`scripts/perception_lab_model_trials.py`, loads its own weights, records what it did and releases
them.

## Reproducing

    python scripts/perception_lab_model_trials.py controls --check   # the corpus has not drifted
    python scripts/perception_lab_model_trials.py list               # candidates and licences
    python scripts/perception_lab_model_trials.py run-all             # everything resident
    python scripts/perception_lab_model_trials.py matrix              # the verdict table

The four resident candidates need no download. ViTMatte needs one flag and about 103 MB:

    python scripts/perception_lab_model_trials.py run --candidate vitmatte_small --allow-download

The trimap-band sweep that produced the soft-field finding:

    python scripts/perception_lab_model_trials.py run --candidate vitmatte_small \
        --control soft-fog --control hair-veil --trimap-band 70

## What is here

| path | what |
|---|---|
| `controls/` | ten synthetic control images and `manifest.json` with their ground truth |
| `runs/` | one JSON record per trial — checkpoint, licence, device, latency, memory, digests, verdicts |
| `previews/` | a rendered strip per trial, so a person can look at what the numbers say |
| `FINDINGS.md` | the ADOPT / EXPERIMENTAL / DEFER / REJECT matrix and the instructions for Lane G |

**No weights.** Not one byte of a checkpoint is committed. Every record names its checkpoint, its
revision where one was resolved, its licence and its size; the weights live in the Hugging Face
cache and in `models/`, both gitignored.

## Why the controls are synthetic

Because the ground truth has to be known **before** the model runs. `soft-fog` has an exact alpha
at every pixel because that alpha is what drew it; `fence-tree` knows its fragments are one thing
because it cut them from one blob; `occluder-table` knows exactly which pixels are hidden because
it covered them. A model evaluated on a photograph can only be compared with another model's
opinion.

They are also lawful by construction — every pixel is computed by the generator, so nothing here
carries someone else's rights.

These are the **disposable controls that come first**. The Lane F corpus of real works
(Steenwyck, de Chirico, Wells, the Cubist interior, van Delen, the Dutch still life) is the actual
test and does not exist yet. A candidate that fails here never needs to meet a painting.

## The two verdicts, and why they are separate

Every trial answers two different questions and records them apart:

- **`form_contract.satisfies`** — can the declared payload be built from this output *without
  lying about what the numbers are*? A schema question, answered by Lane A's own Pydantic models.
- **`fidelity.tracks_truth`** — do the numbers match the control's known ground truth? A schema
  has never seen the picture and cannot ask this; only a control can.

A candidate that validates and does not track is the dangerous case: it produces a well-formed
record a reader would believe. `sam2_logits.soft-fog` is exactly that, and it is why the matrix
has two columns.
