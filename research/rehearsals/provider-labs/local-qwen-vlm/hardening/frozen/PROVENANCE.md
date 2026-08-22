# Frozen cells — INTELLIGENCE-001C-R1

Real cells from runs: R1-20260822, R1-20260822-dflt, captured on the
machine that ran the lane. Kept so `backend/tests/test_qwen_vlm_hardening.py` can
exercise the guards with no model loaded and no server running.

Cells marked `invalid` are kept deliberately. In this run three inference cells recorded
`image_min_tokens: null` while being answered by a server still launched at the 1024
floor — the numbers are real, the label was wrong, and deleting them would discard
evidence to tidy up a harness bug. `ServerControl.ensure()` is the fix.
