"""
INTELLIGENCE-002C — loading the two frozen cross-domain samples.

WHY THE SAMPLES LIVE ON THE TEST SIDE. The lane's generality rule is that no production source may
contain a sample's topic nouns. A fixture module inside `backend/services/inquiry_intelligence/`
would violate that rule by existing, so the frozen inputs are JSON under
`backend/tests/fixtures/intelligence_composer/` and this loader — which names no topic at all — is
what the tests share.

WHY A DIRECTORY OF ITS OWN, BESIDE 001A's. `inquiry_intelligence_fixtures.py` and its
`inquiry_intelligence/` directory belong to INTELLIGENCE-001A: four whole small inquiries, typed
against `backend/schemas/inquiry_intelligence.py` and validated at load. These two files are a
different thing — UNTYPED upstream payloads, deliberately including malformed ones, whose entire
purpose is to reach the composer without having been validated first. Putting them in 001A's
directory would either break its loader's guarantee that everything there parses, or force these
samples through a validation that would reject exactly the nine dishonesties they exist to carry.
Two directories, two loaders, and neither has to know about the other.

WHY THE JSON IS THE COMPOSER'S INPUT AND NOT A RECORDED OUTPUT. There is nothing frozen here that
the composer produced. Each file is a plausible set of UPSTREAM outputs — a map, some readings,
some plans, some relations, some critiques, some evidence — and every assertion in the suite is
about what the composer does with them. A frozen output would let a wrong composer stay green by
having its wrongness recorded alongside it.

WHY THE FIELD NAMES ARE NOT UNIFORM ACROSS THE TWO FILES. They very nearly are, and where they
differ it is deliberate: `composer._field` reads a mapping or an object, and the samples exist
partly to hold that seam open until INTELLIGENCE-001A's typed models land and are dropped in
without a composer edit.

PURE. No network, no database, no clock. `now` is passed through to the composer, which has no
clock of its own.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.services.inquiry_intelligence.composer import CompositionRequest, Composition, compose

FIXTURE_DIR = Path(__file__).resolve().parent / "intelligence_composer"

#: The two frozen inputs. The first is the wave's rehearsal shape; the second shares no noun, no
#: capability and no refusal kind with it and runs the identical production path.
FIXTURES: Tuple[str, ...] = ("moorings", "proofs")

#: The keys of a sample that are commentary rather than input. Everything else in the file is fed
#: to `CompositionRequest` by name, so a key added to a sample and forgotten in the loader fails
#: loudly here rather than being silently ignored at the seam under test.
COMMENTARY_KEYS: Tuple[str, ...] = ("name", "topic", "why_this_fixture", "topic_nouns")


def load(name: str) -> Dict[str, Any]:
    path = FIXTURE_DIR / "{}.json".format(name)
    if not path.exists():
        raise FileNotFoundError("no sample named {!r}; have {}".format(name, list(FIXTURES)))
    return json.loads(path.read_text(encoding="utf-8"))


def topic_nouns() -> List[str]:
    """Every topic noun both samples declare. The generality scan's input."""
    words: List[str] = []
    for name in FIXTURES:
        for word in load(name).get("topic_nouns") or ():
            if word not in words:
                words.append(str(word))
    return words


def request_for(name: str, *, now: Optional[str] = None, **overrides: Any) -> CompositionRequest:
    """The sample as a `CompositionRequest`, with any field replaceable by keyword.

    The overrides are what the negative controls are built from: a test that wants to know whether
    a refusal is derived rather than remembered removes the thing that causes it and asserts the
    refusal goes with it.
    """
    sample = load(name)
    payload = {k: v for k, v in sample.items() if k not in COMMENTARY_KEYS}
    payload["now"] = now
    payload.update(overrides)
    return CompositionRequest(**payload)


def compose_fixture(name: str, *, now: Optional[str] = None, **overrides: Any) -> Composition:
    """The whole replay. ONE production path, two subjects; the only difference between the two
    calls is which JSON file is read."""
    return compose(request_for(name, now=now, **overrides))


__all__ = ["FIXTURE_DIR", "FIXTURES", "COMMENTARY_KEYS", "load", "topic_nouns", "request_for",
           "compose_fixture"]
