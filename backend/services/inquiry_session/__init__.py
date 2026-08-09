"""
HARNESS-002D — the Phase 1 production vertical: one inquiry, prompt to answer.

    POST prompt + selected posts + mode
      -> persisted session
      -> InquiryFrame                 (HARNESS-001A, words only)
      -> scene reading                (HARNESS-002A, pixels, interpretive)
      -> semantic inquiry graph       (HARNESS-002A)
      -> auto decision OR a typed pause  (HARNESS-002B)
      -> the same session resumes from the answer
      -> exactly one SIMULATED capability receipt
      -> claim verdicts, then a claim-bound provisional answer

THIS PACKAGE COMPOSES. It contains no prompt, no claim taxonomy, no capability algorithm, no
pause policy and no UI formatting — every one of those belongs to a merged lane, and a copy here
would be a second opinion that drifts. What it owns is the ORDER, the budget, the persistence and
the wire shape.

    store.py        an additive adapter over the runs collection, discriminated
    ids.py          content-derived ids, so a replay is a comparison
    corpus.py       post ids → image refs and the fingerprints that prove nothing moved
    capability.py   the locked fixture adapter — one attempt, never evidence
    judge.py        a verdict per claim, and a receipt that cannot produce a supported one
    composer.py     a claim-bound answer, refused if a reference does not resolve
    candidates.py   Lane A's forks, read as Lane B's, with reversibility declared narrowly
    coordinator.py  the stage order and the budget
    runtime.py      which implementation this deployment binds behind each seam
    view.py         the projection the workbench reads

PHASE 1 IS SIMULATED AT EXACTLY ONE POINT, and it is named: `capability.py` returns a receipt with
`execution_mode=fixture`, `status=simulated`, `usable_as_evidence=false`. Nothing else in the chain
is a stand-in — the frame, the reading, the compilation, the deliberation and the composition are
the real merged implementations, live or replayed.
"""
from __future__ import annotations

from backend.schemas.inquiry_session import (SCHEMA_VERSION, SemanticInquirySession, canonical)

from . import candidates, coordinator, corpus, ids, runtime, store, view

__all__ = ["SCHEMA_VERSION", "SemanticInquirySession", "canonical", "candidates", "coordinator",
           "corpus", "ids", "runtime", "store", "view"]
