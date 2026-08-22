# Inquiry intelligence — automatic evaluation

**INTELLIGENCE-001B.** Research-only. Nothing under this directory is a production entity, route or
collection, and nothing here edits the inquiry pipeline.

## What this harness decides, and what it refuses to

It answers three structural questions about a finished inquiry session:

1. **Did information flow?** Did the prompt reach a reading, the reading reach atoms, the atoms
   reach claims, the claims reach an answer — or did a stage truncate and the chain close anyway?
2. **Did it stay traceable?** Can each observation be tied to an image, each claim to a source,
   each sentence of the answer to a claim?
3. **Did it produce cross-image relations?** A comparative prompt answered with per-image claims
   and no relations has not made the comparison, however good the claims are.

It does **not** decide whether an answer is beautiful, deep, surprising or worth reading. Those
judgements are written down as `manual_review_questions` on every case and are printed in every
report — not because they are unimportant, but because they are the important ones and a proxy
metric standing in for them would be believed.

The same discipline applies inside the metrics. A metric that could not be computed is `null` with
a reason, **never zero**:

    zero  — the flow did the thing zero times
    null  — nothing in the record could say whether it did

A mean over both is a third number that is true of neither.

## Layout

    cases/          four canonical prompts + the versioned corpus manifest
    schemas/        JSON Schema for a case and for an evaluation
    fixtures/       sanitized session records the committed tests read
    run-archive/    one directory per evaluation run
                    (NOT `runs/` — the repository ignores that name globally)
    architecture-control/
                    candidate ids for a cross-domain control set, AWAITING HUMAN CONFIRMATION

## Running it

    # evaluate a session export against a case
    python scripts/inquiry_intelligence_evaluate.py \
        --session <session.json> --case II-01-rich-user-vocabulary --archive

    # import an external export into a committed, sanitized fixture
    python scripts/inquiry_intelligence_evaluate.py \
        --import-baseline ~/Downloads/inquiry-<id>-rev6.json --fixture-name baseline-rev6

    # resolve the canonical corpus read-only and check fingerprints have not moved
    python scripts/inquiry_intelligence_rehearsal.py --verify-corpus

    # search the database read-only for an architecture control set
    python scripts/inquiry_intelligence_rehearsal.py --propose-architecture --limit 12

## The baseline, and why it is the useful case

`fixtures/baseline-rev6.sanitized.json` is a real case-1 run — its prompt is byte-for-byte the
case-1 prompt and its `prompt_sha256` matches. It is the useful fixture precisely because it is a
run that **looks finished and is not**:

    state                complete
    stop_reason          "the chain closed: every claim carries a verdict …"
    compiler stage       truncated
    relation_architect   truncated, 1 call
    coverage_audit       coverage_failed
    claims               20
    claim_edges          0
    capability receipts  0
    evidence             0

A harness that reported "complete" for that run would be automating the exact failure it exists to
catch. `workflow_outcome` and `semantic_outcome` are therefore two separate fields, and the report
says out loud when they disagree.

## The corpus is read, never written

`corpus.resolve` reads; nothing here writes to `posts`. Fingerprints are recorded at manifest time
and re-checked on every evaluation, so a source post that moved shows up as a finding rather than
as a quietly different result.
