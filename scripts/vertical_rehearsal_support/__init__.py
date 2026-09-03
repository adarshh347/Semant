"""
ATLAS-WRITER-MASS-BUILD-001L — the vertical rehearsal harness.

One command (`scripts/vertical_rehearsal.py`) drives a real browser against a real FastAPI
process and a disposable mongod through the whole Atlas → Writer circuit, and leaves a
machine-readable audit behind. Nothing in this package is imported by the running app; the
backend is started as a subprocess through `app_entry`, which mounts the real `backend.main:app`
and binds deterministic fakes only at the model / GPU seams.

Layout:
  corpus.py     the fixed synthetic corpus (images rendered at run time, marks known by construction)
  stack.py      mongod + image server + backend + Vite, started and torn down as one unit
  app_entry.py  the backend entry the harness actually serves (fakes + fault injection + receipts)
  ledger.py     canonical hashes, field-level diffs, the evidence record
  stages.py     the browser-driven stages, failure profiles, a11y and performance
  report.py     summary.json + the Markdown report
"""
