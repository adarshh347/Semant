# Perception Lab record schemas (generated)

JSON Schema (draft 2020-12) for the five Perception Lab records, generated from
`backend/schemas/perception_lab.py` by `scripts/perception_lab_schemas.py`.

Do not edit them. Edit the Pydantic models, then run:

    python scripts/perception_lab_schemas.py

`backend/tests/test_perception_lab_contracts.py` runs `--check` and fails by name if these drift.

The canonical VOCABULARY — organ families, operations, closed sets, refusal codes, laws — is
`contracts/perception-lab.v1.json`, not these files. These are record SHAPES only.
