# Do not edit these files.

They are byte-identical copies of `contracts/*.json` at the repo root, written by
`scripts/contracts_sync.py`. The canonical files are the ones at the root; these exist only
because the Vercel deploy uploads `frontend/` as its source, so the bundle cannot import from
outside this directory tree.

Edit `contracts/…`, then run:

    python scripts/contracts_sync.py

`contracts.parity.test.js` (here) and `test_inquiry_contracts.py` (backend) both fail by name
if these drift from the canonical files.
