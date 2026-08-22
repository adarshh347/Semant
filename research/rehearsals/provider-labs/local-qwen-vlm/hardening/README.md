# `local-qwen-vlm/hardening` — INTELLIGENCE-001C-R1

The follow-up study to the merged lab. It answers four bounded questions and **registers nothing**.

> **`32K_SAFE`** · **observer `ELIGIBLE_FOR_PROMPT_BLIND_OBSERVATION`** · **aligner `RESEARCH_ONLY`**
> · everything else `UNDETERMINED`

| | |
|---|---|
| `profiles.json` | the matrix, declared before any of it ran. A result from a configuration not in here is not part of the study. |
| `claims.json` | each prompt decomposed once into fixed claim ids. The methodological repair — see below. |
| `schemas/` | retention (retrieval, never reasoning), claim-alignment (the enum is injected per prompt), repair (a second model event, no image). |
| `frozen/` | real cells, so the tests exercise the guards with no model loaded. |
| `../runs/R1-*` | the run records; `report.json` holds the decision table. |

## Running it

```bash
python scripts/qwen_vlm_hardening.py matrix --dry-run          # cells and call count, starts nothing
python scripts/qwen_vlm_hardening.py matrix --profiles context
python scripts/qwen_vlm_hardening.py matrix --image-floor default
python scripts/qwen_vlm_hardening.py progress                  # resumable state
python scripts/qwen_vlm_hardening.py report --also-run R1-…-dflt
```

Every cell writes a **started receipt before** the call and checkpoints the response on arrival, so
an interrupted matrix resumes without repeating a completed call. `interrupted`, `unavailable` and
`invalid` are three states; a missing cell is `UNDETERMINED` and is never scored as a model failure.

## Why the claim set is fixed

In #230 the model split the user's prompt itself and the split moved between runs — two claims in
one, five in another — so `3 of 3 challenges` and `4 of 4 supports` were not answering the same
question. One run also manufactured a claim the person never made. Here the ids are compiled into
the response grammar as an enum, so a minted claim is not a token the sampler can emit and a
missing one cannot satisfy the array length. The **stance** may vary between repeats — that is the
thing being measured. **What was claimed** may not.

## What this lane got wrong

Kept in the record rather than tidied away, because each would have become a finding about the
model:

- A **latency story refuted by its own control** — throughput drift on this box, not sampling policy.
- A **harness bug the control exposed**: the inference group reused whatever server was healthy, so
  cells recorded a floor the server was not serving. Three cells are marked `invalid` with the
  evidence; `ServerControl.ensure()` is the fix.
- **`choose_image_floor` is still wrong and still stands.** It picks the highest *safe* floor, chosen
  before Part 2 found that raising the floor helps nothing. Changing it after the fact would be
  moving the matrix to fit the data; `--image-floor` exists instead and both floors are reported.
