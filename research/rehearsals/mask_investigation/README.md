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

The focused suite contains 44 tests. Production API/UI behavior is unchanged.

## Components

- `mask_geometry_gate.inspect_mask`: exact native stride sampling, all
  axis-aligned transitions, minimum two-sided support, global signal screening.
- `mask_interface_measurement.read_interfaces`: every supplied supported
  interface at equal cross/within pair distances 1 and 7 native cells. Reports
  local values and distributions without selecting a winning mask.
- `mask_hypothesis_test`: a supplied, controlled question evaluated against all
  gate-eligible candidates and both scales. Explicit unresolved object referents
  require clarification. Human review remains unrecorded.

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
