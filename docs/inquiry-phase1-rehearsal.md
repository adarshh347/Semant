# Running a Phase 1 semantic inquiry locally

Everything you need to perform the HARNESS-002R human rehearsal without reading any backend code.

**Before anything else, the one thing that is not real yet.** Phase 1 runs the whole chain — the
question is read, the pictures are read, the reading is decomposed into claims, you are asked a
question at a real fork, and an answer is composed and bound to what it rests on. Exactly one step
is a stand-in: the **capability**. When the inquiry commissions an instrument to go and look at the
pictures, nothing looks. A fixture returns the *shape* such an instrument would return, with
coordinates derived from a hash of the request text, and it says so on its own face, in its own
payload, and twice more in the interface. Nothing in Phase 1 measures anything, and nothing becomes
evidence.

---

## 1. Run it with no setup at all

You do not need a database, a server, an API key or a browser to see the whole chain.

```bash
cd /path/to/semant
venv/bin/python scripts/inquiry_rehearse.py
```

That runs a consult-mode inquiry over a frozen reading, pauses at the fork, answers it with the
recommended option, and prints every stage, every claim with its verdict, the simulated receipt and
the composed answer.

Useful variants:

| command | what it shows |
|---|---|
| `--mode auto` | no pause at all; the choice is made for you and recorded as `auto_resolved` |
| `--mode consult` | the default: it stops and asks |
| `--answer 2` | choose the second option instead of the recommended one |
| `--reject` | decline every option — nothing is commissioned, and the answer says so |
| `--redirect "look at the thresholds instead"` | answer in your own words |
| `--fixture unrelated-domain` | the same chain over a subject with no vocabulary in common |
| `--json` | the exact body the API serves, for diffing or for reading in an editor |
| `--replay-check` | run the same session twice and prove the two are byte-identical |

`--replay-check` is the one worth running once: it prints how many live model calls a replay made,
and the answer is zero.

## 2. Run it against real images and real models

```bash
venv/bin/python scripts/inquiry_rehearse.py --live \
  --prompt "your question" \
  --image "https://…/one.jpg|a title" \
  --image "https://…/two.jpg"
```

This needs `GROQ_API_KEY` in `.env`. It reaches three roles — the scene theorist, the semantic
compiler and the synthesis composer. If any of them is unreachable the session **says so** and
returns an empty or unavailable stage; it never falls back to a fixture while claiming to be live.

`--live` takes image URLs rather than post ids on purpose: the script does not open the database.

## 3. Run the whole product in a browser

Three terminals, or three background processes.

```bash
# 1 — the API
cd /path/to/semant
venv/bin/uvicorn backend.main:app --reload --port 8000

# 2 — the frontend
cd /path/to/semant/frontend
npm ci          # first time only
npm run dev

# 3 — open it
open http://localhost:5173/inquiry
```

You need:

- **`.env`** at the repo root with `MONGODB_URI`, `API_KEY` and (for real readings) `GROQ_API_KEY`.
  Copy it from wherever you already keep it; the frontend reads `VITE_API_URL` and an API key from
  its own `.env`, same as every other surface.
- **at least one post with an image** in the corpus. The entry screen lists what it finds. If the
  gallery is empty it says so rather than showing an empty grid.

Then: pick one or more images, type a question, choose a mode, and press start.

### Turning the model stages off

To exercise the chain with no provider configured:

```bash
SEMANT_INQUIRY_LIVE_MODELS=0 venv/bin/uvicorn backend.main:app --port 8000
```

The theorist and compiler are then unbound. The session records `skipped` for both, compiles
nothing, and stops with an honest empty. This is worth seeing once — it is what an outage looks
like, and it is deliberately not a working demonstration.

### The deterministic browser rehearsal (use this one first)

The live compiler does not reliably produce a fork. On a long reading it runs out of output budget,
returns a prefix with no observables, and a graph with no observables has no fork in it — so live
mode may take you straight from question to answer with no pause at all. That is reported honestly
by the chain and it is a real Phase 1 finding, but it is not something you can rehearse the *human
turn* against.

So run this instead when what you want to judge is the pause:

```bash
# instead of uvicorn, in terminal 1
venv/bin/python scripts/inquiry_rehearsal_server.py --port 8000
# or the other domain
venv/bin/python scripts/inquiry_rehearsal_server.py --port 8000 --fixture unrelated-domain

# terminal 2 — point the frontend at it
cd frontend && VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

Everything is the real thing — the routes, the session, the state machine, the capability adapter,
the judge, the composer, the persistence — except the two MODEL stages, which are frozen payloads.
It needs no API key and no `GROQ_API_KEY`, and it lists your real corpus so you pick real images.

Every session it produces says what it is: `call_topology: "replay"` and `call_count: 0` on both
receipts, visible under **Show model receipt**. A screenshot taken here cannot be mistaken for a
live reading by anyone who looks.

### The API, if you would rather drive it directly

```bash
API=http://localhost:8000/api/v1/inquiries
KEY="x-api-key: $YOUR_API_KEY"

# start
curl -s -X POST $API -H "$KEY" -H 'content-type: application/json' \
  -d '{"prompt":"your question","image_ids":["<post id>","<post id>"],"mode":"consult"}' | jq .

# read it back
curl -s $API/<session id> -H "$KEY" | jq '.state, .decision_requests'

# answer the open decision
curl -s -X POST $API/<session id>/decisions -H "$KEY" -H 'content-type: application/json' \
  -d '{"decision_id":"<id>","response_id":"r1","action":"select",
       "selected_option_id":"<id>","expected_revision":<n>}' | jq .
```

`expected_revision` is not optional in spirit: without it a reply to a question the session has
already moved past gets applied to a different question. Send the revision you were looking at, and
a stale one comes back as a `409` that keeps your text and hands you the current session.

## 4. What to look at, and what is honest to conclude

The rehearsal directive (HARNESS-002R) has the full inspection list. The four things this build is
most likely to be wrong about:

1. **Is the fork worth asking about?** The pause happens where the compiler declared a genuine
   choice of operationalization. If the two options are not meaningfully different investigations,
   the interruption is not earning itself.
2. **Did your answer change anything you can see?** The decision record names which graph refs it
   affected, and the answer has its own section for what your decision changed.
3. **Is `SIMULATED — not evidence` impossible to miss?** It is beside the receipt, again beside the
   geometry when you expand the payload, in the receipt's own detail line and in its provenance,
   and once more in the note at the top of the answer. If it is still missable, that is the finding.
4. **Is the composed answer more useful than the reading it came from?** It is structured and
   qualified rather than fluent; if it is only more cautious and not more useful, say so.

Four things are **not** in Phase 1 and their absence is not a defect: no SAM, no agent dispatch, no
percept, mark or Atlas edge is written, and no evidence object exists. An inquiry writes exactly one
document — its own history — and re-checks every source post's fingerprint before each write.

## 5. Regenerating the checked-in samples

`contracts/samples/*.json` are the canonical API responses the frontend's parity suite reads. If a
backend field changes, a test tells you they have drifted:

```bash
venv/bin/python scripts/inquiry_contract_sample.py          # rewrite them
venv/bin/python scripts/inquiry_contract_sample.py --check  # CI's version
```

## 6. The tests, if you want to see the guarantees rather than trust them

```bash
venv/bin/python -m pytest backend/tests/test_inquiry_session_*.py -q
cd frontend && npx vitest run src/inquiryWorkbench
cd frontend && npm run audit:honesty        # proves each honesty guard can be made to fail
```
