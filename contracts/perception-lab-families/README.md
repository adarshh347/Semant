# Perception Lab family slots

Six fixed slots are registered in `backend/services/perception_lab/families/registry.py`
and `frontend/src/perceptionLab/families/registry.js`. A family owns exactly its
`<family>.py`, `<family>.jsx`, and `<family>.json` files. The central registries already
reference all six slots. Replace one unavailable module with a complete declaration;
do not edit the other five or regenerate the shared record schemas.

The backend module exports `MODULE: FamilyModule`. It declares forms, operations,
producer functions, bounded prompt intents, and admitted dependency/model manifests.
A producer returns `ProducedField(metadata, values, valid, producer_revision)`.
The shared bridge prepares the original image, validates the typed field, saves it
through `DataRef`, and invokes learned producers under the cross-process lease.

The frontend module exports `SLOT` with the same family/form/operation keys, display
views, bounded prompt intents, and a `Panel` component that calls the existing Lab
planning client. `available` stays false until the complete family is ready. The
registries reject duplicate keys and malformed declarations.

The synthetic, explicitly FIXTURE-only payload in
`frontend/src/perceptionLab/fields/fixtures/foundation-field.v1.json` demonstrates
the accepted `sample_grid` manifest and a display derivative. Its `measurement_hash`
covers canonical metadata, numeric bytes, and validity bits. `DataRef.digest` covers
the compressed asset bytes, preserving the existing Lab export rule.

Generate or check only the owned family file:

```sh
python scripts/perception_family_contract.py colour
python scripts/perception_family_contract.py colour --check
```

The core record shape remains `research/perception_lab/schemas/perceptual-artifact.schema.json`.
The six per-family JSON files are independent declarations, not new artifact stores.
