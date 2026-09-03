# `local_qwen_vlm` — a visual-observation laboratory

INTELLIGENCE-001C. A 6.58 GB GGUF sits on this machine, answers on `http://127.0.0.1:8081/v1`,
costs nothing and has no allowance window. Every rehearsal Semant has run so far waited on a
metered remote provider — HARNESS-003F's own script sleeps forty-five minutes between two calls
because the account had not recovered. So the question is worth asking precisely:

> **is this thing good enough to be the eye that is always there?**

**This lab binds nothing.** No production inquiry service, route, registry or dependency is
touched. `local_qwen_vlm` is a provider identity recorded in run records; nothing in `backend/`
resolves that string, and a test asserts it stays that way. A lane that ended by wiring the
theorist to a 9B quantisation on a 16 GB laptop would have skipped the measurement it existed to
take.

## There is a follow-up, and it changed two of these answers

**INTELLIGENCE-001C-R1** lives in [`hardening/`](hardening/README.md) and re-asked the questions
this lab left open. Two of its results revise what is written below:

- **32k is ratified.** This lab ran at 32768 without comparing it to anything. R1 measured it
  against 16k and against a retention benchmark: served 32768 verified, peak wired 9 305 MB under
  a 12 713 MB ceiling, **20/20 retrieval** at four prompt sizes by five depths. `32K_SAFE`.
- **Do not raise the image-token floor.** This lab recommended trying `--image-min-tokens 1024`
  before grounding work. On this corpus that costs **2× latency and buys nothing** — spatial
  density and lexical variety both fall slightly. The recommendation stands only for large images,
  which R1 did not test.

R1 also found that the false-premise failure is worse than measured here: **0 of 24 repeats**
resisted every claim once the claim set was fixed. This lab's 1-in-8 was measured on a moving
target, because the model split the prompt itself and the split changed between runs.

## Running it

```bash
cd "/Users/merleauponty/ml models/qwen 9b q5km" && VISION=1 CTX=32768 ./serve.sh   # elsewhere
python scripts/local_qwen_vlm_lab.py resolve       # the three posts, read-only, once
python scripts/local_qwen_vlm_lab.py all           # census + experiments 1-5 + the gates
python scripts/local_qwen_vlm_lab.py freeze        # capture the responses for the test suite
```

Individual stages: `census`, `observe`, `align`, `compare`, `reliability --trials N`,
`rehearsal-prompts`, `restart`, `gates`.

## What is in here

| path | what it is |
|---|---|
| `corpus.json` | the three post ids, their Cloudinary URLs, and the **sha256 of the bytes**. Resolved with every mutating method on the posts collection replaced by a raiser first. |
| `prompts.json` | the four canonical rehearsal prompts, each carrying its provenance. |
| `schemas/` | the three response grammars. Sent to llama-server as `response_format.json_schema`. |
| `runs/<id>/` | one record per stage. Every number in them is one the server reported. |
| `frozen/` | real responses, kept so `backend/tests/test_local_qwen_vlm_lab.py` can exercise the audits with no model loaded. |
| `image-cache/` | the fetched JPEGs. **Gitignored** — no image bytes enter the repository. |

## The three separations, and how each is enforced

Not by asking the model nicely. Each is structural.

**A person's hypothesis is not an image observation.** Enforced by *order and blindness*.
Experiment 1 never sees the person's words. Experiment 2 never sees the image — it is handed its
own frozen observations as text. It cannot invent a new visual observation because there is
nothing in front of it to look at. Asking a model not to look while showing it the picture is a
wish; taking the picture away is a mechanism.

**An interpretive reading is not a measurement.** The observation schema's `status` is a
one-value enum, so `measured` is not a token the sampler's grammar can emit. The prose is audited
separately anyway, because a field can read `interpretive` while the sentence beside it says
*approximately thirty degrees*.

**Recognising a thing is not the repository knowing what it is.** The attribution audit is built
out of *grammar*, not out of a topic word list — `attributed to`, `possibly representing`, a
century, a date, a capitalised proper noun mid-sentence. It contains no term from any rehearsal
topic, which is both what rule 5 requires and what makes it still work on a corpus of trains.

## Honesty rules this harness keeps

- **Telemetry the server did not report is `null`.** Rates come from llama-server's own `timings`
  block. Wall-clock measured by the client is named `client_wall_ms` so nobody reads it as
  throughput.
- **RSS is not the footprint.** Under `-ngl 99` on Metal the weights live in buffers that stop
  being attributed to the process — this lane watched RSS read 7415 MB and then 141 MB while
  throughput never changed. `wired_mb` from `vm_stat` is recorded beside it and the record carries
  the caveat.
- **No per-process VRAM figure is produced**, because on unified memory there is no honest one.
- **A gate with no evidence is `UNDETERMINED`,** never `FAIL`. A missing experiment must not be
  able to look like a bad model.
- **`unavailable` is a result.** A server that does not answer produces a record saying so, with
  every field absent rather than zero.
- **The image bytes are anchored.** The harness refuses to run if a fetched JPEG's sha256 no
  longer matches the manifest, because otherwise a silent re-encode upstream turns a changed
  observation into a finding about the model.

## The corpus

Three posts, resolved read-only. All three carry **no tags, no text blocks, no annotations and no
handle** — bare uploads. That is worth saying out loud: the prompt-blind pass is genuinely blind,
because there is nothing in the record that could have leaked a vocabulary into it even by
accident.
