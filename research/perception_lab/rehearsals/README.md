# Perception Lab — form rehearsal bundles

PERCEPTUAL-FORMS-001H. What `scripts/perception_lab_form_rehearsal.py` writes when it drives a
running laboratory. One bundle per suite per image; the finding cites them by filename.

**Every human field in every row is `null`.** `human_correct`, `human_useful`, `better_seen_as` and
`human_notes` are the four a machine must not fill, and a bundle that reached a gate without a
sitting is visibly un-walked rather than silently empty. The one verdict this driver's evidence
can settle on its own is `DEFER`, and only for an absence the capability probe can see.

## The suites, in the order they must be run

| suite | what it establishes |
|---|---|
| `preflight` | the wire is LIVE, every unavailable adapter says why, the form and recipe catalogues answer, the post is byte-identical after a session opens |
| `forms` | one row per form: the direct operation, the producer and model, latency, the record it produced, what it examined, what it refused, what it left out |
| `recipes` | one session per study in the mode that study declares — plus one deliberate chain-study-in-an-isolation-session, to show the organ lock holds against a recipe |
| `prompts` | last, always. A prompt trial run before the direct one would test language and the organ at once |

## Reading a row

`examined` is whichever counter the form declares — `rings_traced`, `candidates_examined`,
`fragments_considered`, `pairs_examined`. It is what proves something looked, and an empty answer
beside a non-zero count is a measurement rather than an absence.

`refusals: ["form_not_producible"]` beside a payload is not a failure. Four of the five composite
forms are `deferred` in the merged contract; the payload is computed so the shape can be reviewed,
and the verdict travels with it so nothing writes one.

`record_kind: "derivation"` on every derived row is the fact this phase turns on: no operation
declares any of the twelve, so none of them can become a `PerceptualArtifact`.

## Regenerating

```
# the backend must be started from a directory that has models/, with SAM3_WEIGHTS set
export SAM3_WEIGHTS=/absolute/path/to/sam3.pt
python -m uvicorn backend.main:app --port 5008

python scripts/perception_lab_form_rehearsal.py preflight --post <id> --label <name>
python scripts/perception_lab_form_rehearsal.py forms     --post <id> --label <name>
python scripts/perception_lab_form_rehearsal.py recipes   --post <id> --label <name>
python scripts/perception_lab_form_rehearsal.py prompts   --post <id> --label <name>
```
