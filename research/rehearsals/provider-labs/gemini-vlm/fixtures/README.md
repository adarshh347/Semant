# Frozen responses

Canned Gemini response bodies, used by `backend/tests/test_gemini_vlm_lab.py` through
`FrozenTransport`. The suite reaches no network and needs no key.

**The model names in here are deliberately fake** — `models/fixture-model-a`, not a real product
name. A fixture that carried the real catalogue would be one copy-paste away from being read as
a census of the account, which is the exact confusion `census.json` exists to prevent. The real
catalogue comes from the account, or it is `not_observed`.

Every file is a *response*, exactly as the API shapes one. They are not edited to be convenient:
`generate-schema-violation.json` really is well-formed JSON that breaks the contract, and
`generate-not-json.json` really is prose where JSON was demanded, because those are the two ways
a structured-output promise fails in practice and the lab has to tell them apart.
