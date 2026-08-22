# Run records — which harness version wrote each

Three runs are kept. They are not interchangeable, and this file exists so nobody reads a stale
derived field as a fact about the model.

| run | what it is |
|---|---|
| `20260822-final` | **the record.** Every stage written by the harness as committed. `frozen/` is copied from here and the tests read it. |
| `20260822-full` | the first complete run. Its RAW responses are evidence — in particular its experiment 5, where the adversarial prompt came back `supports` on all four claims. Three of its DERIVED fields predate later fixes (see below). |
| `20260822-a` | the exploratory run. Kept only for its experiment 5, the third adversarial sample. Its derived fields predate every fix below. |

## What changed after `20260822-a` and `20260822-full` were written

Each was a harness defect found by real output, and each is a commit of its own:

1. **The audit cried wolf.** Case-insensitive matching made `[A-Z]` match anything, so
   `shadows created by the drapery` read as authorship and `style of carving` as a workshop
   attribution; and the proper-noun finder split on sentence punctuation while the audited text is
   serialised JSON, so `Moderate` and `Whether` read as named entities. The `audit` blocks in the
   two earlier runs are therefore **over-reported**.
2. **The digest taught a citation format the checker rejected.** Observations were displayed as
   `[img-k7-o0]`; the model cited `"[img-k7-o0]"`; the checker compared raw strings and called all
   eleven valid citations hallucinations. `hallucinated_observation_ids` in the earlier runs may
   contain bracketed ids that are **valid references**, not fabrications.
3. **Invented and wrong-level refs were one number.** `20260822-full`'s experiment 3 lists
   `img-k7-o3` under `invented_refs`. It is a real observation id used where an image ref was
   required — a level confusion, not a fabrication. Later runs split the two.
4. **`precisely` alone counted as a measurement.** An adverb of manner is a claim about craft. It
   is now reported under `precision_language` and does not count.
5. **The reliability record kept counts without the text.** `20260822-full` says one trial wrote
   measurement grammar and cannot say which. `20260822-final` carries `measurement_matches` and
   the parsed observation, which is how the fabricated `10%` uncertainty in its trial 6 could be
   read at all.

Nothing was rewritten. The raw model output in every record is exactly what the server returned.

## A bug that left useful evidence

`20260822-final` carries **two** stability probes. `probe-stability-rich-tactile-philosophy.json`
was not intended: `all` passes one argument namespace through every subcommand, so the stability
step inherited the alignment step's `--prompt-id` and measured the rich prompt while printing the
adversarial one's heading. The bug is fixed (the option has its own attribute name now) and the
record is kept, because six repeats of the rich prompt is a real second stability sample and
deleting it would be discarding evidence to tidy up a mistake.
