"""PERCEPTUAL-ORGANS-002 — the Perception Lab.

Lane A owns only the contract spine in here: `contracts.py` (reads the canonical JSON) and
`definitions.py` (the typed organ/operation registry and the fail-closed resolvers). Lanes B–D add
`extent.py`, `topology.py` and `orchestrator.py` beside them; Lane F mounts the routes.

Nothing in this package dispatches a model, writes to a post, or promotes anything.
"""
