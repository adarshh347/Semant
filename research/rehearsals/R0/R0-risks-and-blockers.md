# R0 — Risks and blockers

## Blockers (must be resolved before the gate that needs them)

| # | Blocker | Affects | Status / mitigation |
|---|---------|---------|---------------------|
| B1 | **Live HTTP server was unstable** in the prior session — `python -m uvicorn …` and `npm run dev` die with exit 144 (empty output). | R4/R5 rendered browser verification | **Partly resolved:** a **programmatic `uvicorn.run` in `scripts/_run_backend.py` DID come up on :8000**; the `-m uvicorn`/`npm` *wrappers* were the failure. Frontend via `node vite` intermittently died. **Action for R4+:** launch backend via the script; launch vite via the same direct-binary pattern and confirm before claiming any rendered result. R0 needs no server. |
| B2 | **Writer vision LLM likely dead** — `editor_llm_service` targets Groq `llama-4-maverick` (vision); Vision D established Groq removed all vision models. | Any rehearsal needing *generated* prose grounded in the image (A5 overreach) | Verify the call live before use; if dead, route through the OpenRouter semantic provider or use authored test prose. **Do not silently repoint** a provider. |
| B3 | **Only ~9 dissected posts / 5 percepts / 0 text mentions** exist. | Fixture realism for A1–A6 | Enough for close-review rehearsals; where a domain (textile, clean cross-cultural pair) is missing, author fixture data with explicit provenance (never fake production records). Do **not** run the 118-post expansion to manufacture fixtures. |

## Risks (program-level; carried in every rehearsal)

- **Premature ontology** — the eloquence of `Passage`/`Embodiment`/`address field` invites turning
  them into schemas. *Guard:* candidate cards + graduation ladder; R0 creates none.
- **Source ventriloquism** — repeating Merleau-Ponty instead of seeing. *Guard:* A3 swaps the
  source; foundry requires a run-without-source pass.
- **Sequence confounding** — attributing an insight to images when order produced it. *Guard:*
  sequence-inversion replays on A3/A6.
- **Analogy collapse / cultural flattening** — similarity → identity/history. *Guard:* A6 is an
  explicit refusal test; state the correspondence dimension, preserve difference.
- **Geometry corruption** — the deepest invariant. *Guard:* rehearsals never write geometry;
  `mask_rle` authoritative; the F byte-level regression posture stands.
- **Confirmation drift** — the harness demonstrating a happy path instead of exposing gaps.
  *Guard:* separate conductor and meta-observer passes (harness §C); a contradiction is a result.
- **Adoption illusion** — treating the *existing* percept→text→recall machinery as proven because
  code exists. *Guard:* it has **0 real uses**; it must be rendered-verified, not assumed.
- **Autonomous scope creep** — agents creating entities / mutating the corpus while "learning."
  *Guard:* bounded packets, stop gates, no merge, no corpus mutation, research writes only to
  `runs/`.

## Non-risks (confirmed safe by A–F + R0)

`mask_rle` authoritative and preserved (F: 41/42 dissected regions recovered, curator identity
byte-stable); semantic/embedding contracts intact; similarity already framed as research (E/F);
detached-ground state persists honestly; per-post rollback + ledger exist. R0 is pure inspection and
changes nothing.
