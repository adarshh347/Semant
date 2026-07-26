"""
CIRCUIT-001 FIX-UI-001 (G4) — backend↔frontend producer parity.

DIAGNOSE-UI-001 §3: a backend producer whose emitted `provenance.producer` is not in the frontend
`PRODUCERS` vocabulary is dropped SILENTLY at intake (`normalizeMark → null → filter(Boolean)`),
so a real model suggestion vanishes and its Accept button never renders (that was the
`architectural_axis` / `external_limit` bug). The two vocabularies live in two languages and drift
silently. This test makes the drift a CI failure instead.

The assertion is one-directional: every backend MARK-producer's emitted name must be in the
frontend `PRODUCERS`. Frontend-only names (`planner`, `fixture`) are allowed extras. Readings
(`presence_check`, `enumerate`) are excluded — their descriptors are `*_reading` and the frontend
hooks filter them out BEFORE intake (`useProduceField`/`useOrchestrate`), so they never reach the
`PRODUCERS` gate.

Mirrors the cross-file pin in `test_director.py::TestCapabilityMap`.
"""
import re
from pathlib import Path

from backend.services import suggestion_service as ss

# The two producers whose descriptor `type` is a *_reading (presence_reading / count_reading).
# The frontend excludes exactly these before intake, so parity must exclude them too. If a NEW
# reading producer is added, add it here (the failure message will point you here).
READING_PRODUCERS = {ss.PRODUCER_PRESENCE_CHECK, ss.PRODUCER_ENUMERATE}

# Route keys in `_FIELD_PRODUCERS` are NOT the emitted producer names — DIAGNOSE flagged this.
# `background_recession`/`atmosphere_field` both emit `recession`; `light_field`/`shadow_field`
# both emit `shading`. Parity keys on the EMITTED name, never the route key.
ROUTE_ONLY_KEYS = {"background_recession", "atmosphere_field", "light_field", "shadow_field"}


def _backend_mark_producers() -> set:
    """Every `PRODUCER_* = "..."` value in suggestion_service, minus the readings — i.e. the
    emitted `provenance.producer` of every producer that mints a MARK."""
    values = {v for k, v in vars(ss).items()
              if k.startswith("PRODUCER_") and isinstance(v, str)}
    return values - READING_PRODUCERS


def _frontend_producers() -> set:
    """Parse the `PRODUCERS` array from visualMarks.js. Line comments are stripped first — they
    contain apostrophes (e.g. "shading's") that would otherwise corrupt literal extraction."""
    path = Path(__file__).resolve().parents[2] / "frontend/src/differential/visualMarks.js"
    text = path.read_text()
    m = re.search(r"export const PRODUCERS = \[(.*?)\];", text, re.S)
    assert m, "could not locate `export const PRODUCERS = [...]` in visualMarks.js"
    block = re.sub(r"//[^\n]*", "", m.group(1))          # drop line comments
    return set(re.findall(r"['\"]([a-z0-9_]+)['\"]", block))


def test_every_backend_mark_producer_is_in_frontend_PRODUCERS():
    mark_producers = _backend_mark_producers()
    frontend = _frontend_producers()
    missing = sorted(mark_producers - frontend)
    assert not missing, (
        f"backend mark producers absent from frontend PRODUCERS (visualMarks.js): {missing}. "
        "A suggestion from these producers is DROPPED silently at intake and its Accept button "
        "never renders. Add each to the PRODUCERS array (or, if it is a reading, to "
        "READING_PRODUCERS in this test)."
    )


def test_route_keys_are_not_mistaken_for_emitted_producer_names():
    """Guard the DIAGNOSE distinction: the produce-field route keys must NOT be treated as the
    parity set — the emitted names (recession/shading) are what the frontend validates."""
    mark_producers = _backend_mark_producers()
    assert ROUTE_ONLY_KEYS.isdisjoint(mark_producers)
    assert "recession" in mark_producers and "shading" in mark_producers


def test_readings_are_excluded_and_do_not_need_frontend_producers():
    """presence_check / enumerate emit *_reading descriptors that the frontend filters before
    intake — so they are correctly outside the parity set even though they are real producers."""
    frontend = _frontend_producers()
    assert ss.PRODUCER_PRESENCE_CHECK not in _backend_mark_producers()
    assert ss.PRODUCER_ENUMERATE not in _backend_mark_producers()
    # (they may legitimately be absent from the frontend vocabulary)
    assert ss.PRODUCER_PRESENCE_CHECK not in frontend
