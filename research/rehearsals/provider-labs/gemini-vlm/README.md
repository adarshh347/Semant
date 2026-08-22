# Gemini free-tier VLM lab — INTELLIGENCE-001D

A laboratory, not an integration. It asks whether the currently available Gemini free tier is a
hosted VLM worth putting beside local Qwen and the Groq theorist, and it answers with recorded
calls rather than with a citation.

**Nothing here is wired into Semant.** No production inquiry service imports
`scripts/gemini_vlm_lab.py`; no route calls it; no Director actuator wraps it. Everything it
writes lands under this directory.

## What it produces, and what that is worth

Every record this lab writes is an **interpretive reading**. A VLM naming a quality has read an
image, not measured it. The call schema pins `measured` to the constant `false`, and a second
in-code guard refuses to write a record that says otherwise — so promoting a reading to a
measurement takes a reviewed edit to a schema, which is the conversation that ought to happen.

Two agreeing models are a fact about models. Nothing here becomes measured through agreement.

## The three things kept apart

| | what it is | where it comes from |
|---|---|---|
| a user hypothesis | a claim that arrived before any image was opened | `prompts.json` — `rich` and `adversarial` carry one, and say so |
| an interpretive reading | what the model says it sees | every `outcome.text` / `outcome.json` in a run |
| a measurement | something an organ measured, by a method you can name | **this lab produces none** |

## Layout

```
prompts.json          the four canonical prompts, verbatim, marked for whether they assert
corpus.json           the three post ids → URLs, image digests, post fingerprints (read-only)
corpus/               cached image bytes — gitignored; the digest is what is committed
census/census.json    what THIS account offers, or `skipped` and why
runs/<stamp>/         manifest.json + calls/*.json, one file per call
schemas/              the call record, the census, and the three response schemas
fixtures/             frozen responses for the test suite; fake model names on purpose
```

## Running it

```
export GEMINI_API_KEY=...          # the only way in; there is no --api-key flag
python scripts/gemini_vlm_lab.py corpus          # resolve the three posts, read-only
python scripts/gemini_vlm_lab.py census          # ask the account what it offers
python scripts/gemini_vlm_lab.py run-all         # six experiments, smallest first
python scripts/gemini_vlm_lab.py census --from-run <run_id>   # promote what a call proved
python scripts/gemini_vlm_lab.py replay --run <run_id>        # re-read; reaches no network
```

With no key the tooling still runs end to end: the corpus resolves, the census records
`skipped` with the reason, and every experiment writes an `unavailable` record. A run directory
missing four of its six experiments would be indistinguishable from one where four calls were
quietly dropped, so nothing is skipped — it is recorded as not having happened.

## The census records what it read, and nothing else

The models endpoint reports the model list, the context limit and the output limit. It does
**not** report RPM, TPM or daily caps — those are on the account dashboard, which is
authoritative and which this program cannot read. So every quota in `census.json` is a
`{value, source}` pair, and the honest default is `{"value": null, "source": "not_observed"}`.

Filling those in from documentation would produce a file identical in shape to one read off the
console, with no way to tell them apart — and the first time the free tier changed, the lab would
keep reporting last year's ceiling with complete confidence.

Image support and JSON-schema support work the same way. `supportedGenerationMethods:
["generateContent"]` is not a claim that images are accepted, so both stay `null` until
`census --from-run` promotes them on the evidence of a call that actually sent an image or
actually held a schema — and the promoted row names the `call_id` that did it.

## The six experiments

Small calls first, so a quota ceiling is hit by the cheapest call that could hit it. `run-all`
stops on a 429 and records the delay the tier asked for: that is a finding about the free tier,
and continuing past it would bury it under identical errors.

1. `text_minimal` — a one-word completion. Proves the plumbing and the usage metadata.
2. `image_one` — one image, prose.
3. `json_strict` — one image, under `visual-observation.schema.json`.
4. `image_three` — the whole corpus at once.
5. `hypothesis_alignment` — four calls, one per canonical prompt, over the *same* three images,
   so the only thing that varies is the prompt.
6. `relation_proposal` — relations over the observations this run recorded, with no image
   re-sent. A reading of a reading, and recorded as one.

Experiment 5 never asks the model whether it agrees. It asks what the prompt *assumed*, then what
is visible that bears on it, image by image — because a model asked to agree will agree, and the
agreement would then sit in the same directory as the observations and read like one.
`refused` and `not_answerable_from_images` are first-class verdicts.

## Discipline

- **The key** lives in `GEMINI_API_KEY`, goes into an `x-goog-api-key` header, and is scrubbed
  out of every error string before anything is written. It never enters a URL, because a URL is
  a thing that gets logged, pasted into a bug and copied into a report. There is deliberately no
  way to pass it as an argument.
- **The corpus is read.** The lab has no write path to the posts collection — not a guarded one,
  none — and the test suite checks that by name so no later edit can quietly acquire one. Each
  call records the post fingerprints before and after.
- **Identity is never inferred.** `mode` names the transport that was configured. Replay's
  transport *raises* if anything reaches for the network.
- **One call per experiment.** No retry, no reformat-and-ask-again. A lab that retried until the
  JSON parsed would measure how long it takes to get lucky and report perfect compliance.
- **The topic is data.** Folds and sculpture appear in `prompts.json` and nowhere else. The
  instructions the lab itself sends would read identically over weather photographs — an
  instrument with one rehearsal's vocabulary compiled into it could not report that the rehearsal
  had failed.
