# Offline mask investigation research

This isolated research package provides necessary mask geometry/signal checks,
a half-cell equal-distance Lab colour measurement, and a constrained numerical
hypothesis reducer. It does not call an LLM, load segmentation weights, run a
server, authenticate a reviewer, identify objects, or execute proposed actions.

## Dependencies and tests

Use the repository's Python environment with `numpy`, Pydantic v2, and `pytest`.
From the repository root:

```sh
PYTHONPATH=. python -m pytest backend/tests/test_mask_investigation_*.py -q
```

Production API/UI behavior is unchanged.

## Components

- `mask_geometry_gate.inspect_mask`: exact native stride sampling, all
  axis-aligned transitions, minimum two-sided support, global signal screening.
- `mask_interface_measurement.read_interfaces`: every supplied supported
  interface at equal cross/within pair distances 1 and 7 native cells. Reports
  local values and distributions without selecting a winning mask.
- `mask_hypothesis_test`: a supplied, controlled question evaluated against all
  gate-eligible candidates and both scales. Explicit unresolved object referents
  require clarification. Human review remains unrecorded.
- `evidence_feedback.propose_feedback`: reuses that validation, recomputes local
  diagnostics from raw arrays and proposes non-executing review purposes. Keeps
  scale disagreements and means with local exceptions visible. Local excess
  does not falsify a mean-based claim; the original test result is unchanged.

Replay feedback against the stored retrospective fixture (no new inference):

```sh
PYTHONPATH=. python -m research.rehearsals.mask_investigation.evidence_feedback > feedback.json
```

This outputs 20 measured candidates, 34 retained nulls, 24 original numerical
counterexamples, 16 candidates with different mean classifications at the two
scales, and 16 candidate-scale means at or below the threshold with local excess.
All 20 measured candidates contain local excess at both scales. These are
deterministic diagnostics of previously saved data, not new image measurements.
The resulting purposes call for inspecting scale and local variation and
retaining conditional scope. No action, scale search or semantic conclusion is
authorized. Untrusted stored display summaries are not used as evidence for
these diagnostics; raw arrays are validated by the existing reducer first.

## Fixture and limits

`fixtures/source.json` attributes the public-domain Art Institute of Chicago
Monet reproduction and identifies the numerical fixture. The compressed fixture
contains previously computed research measurements, including all 54 candidate
records (20 measured and 34 nulls), not image pixels, private conversations or
model weights. Its compressed SHA-256 is:

`1aea545b353a1ca23df6c3b7d0fa6ba1da10820b6a56dc72922318bfece75393`

This is a retrospective operationalization of inspected results, not a
preregistered experiment or independent semantic ground truth. Passing geometry
or mean thresholds does not establish object identity, perceptual continuity or
philosophical truth. Nulls are not supporting evidence. The masks and colour
measurements share image pixels and are not independent confirmations. Global
signal can miss locally flat interfaces. The controlled numerical proxy is
caller-supplied, not automatically inferred from philosophical language.

Digests detect stale/inconsistent edits, not deliberately fabricated and
rehashed evidence; they are not signatures or authenticated approval. The source
attribution does not confer a software license on this repository.
