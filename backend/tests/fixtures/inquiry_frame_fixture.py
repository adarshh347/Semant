"""
HARNESS-001A — the acceptance frame, generated from the real framer and pinned as JSON.

Same pattern as `run_view_fixture`: the `.py` GENERATES the fixture from a real framing, the
`.json` beside it is the committed copy, and a test pins them together. Two consumers read the
committed copy:

  · `test_inquiry_frame.py` — asserts the framer still produces it;
  · `frontend/src/differential/contracts.parity.test.js` — takes its `proposed_actions` and runs
    every one through the REAL JavaScript validator.

That second reader is the point of committing it at all. It is the only way to check that a
Python-built act is accepted by the JS grammar without writing a third validator in the middle,
and a third validator is exactly what the shared contract exists to prevent.

Regenerate after an intentional change:

    python -m backend.tests.fixtures.inquiry_frame_fixture
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from backend.schemas.inquiry import InquiryMode
from backend.services.inquiry import DeterministicFramer

FIXTURE_PATH = Path(__file__).with_suffix(".json")

#: The wave's acceptance rehearsal, byte for byte. Every lane uses this sentence.
FOLD_PROMPT = (
    "Explore the fold-level aesthetic and style relations between Renaissance and Buddha "
    "sculptures, their common way of unfolding sensuality, where they drift apart, and what "
    "hybrid styles they could give birth to."
)

#: Metadata only — ids and titles. There is nothing here that could be a fact about a picture,
#: and that is the shape of everything this mind is ever handed about a corpus.
FOLD_CORPUS: Dict[str, Any] = {
    "post_ids": ["fixture_renaissance_01", "fixture_buddha_01"],
    "titles": ["Pietà, marble", "Seated Buddha, Gandhara schist"],
    "tags": ["sculpture", "drapery"],
}

#: Frozen so the fixture is reproducible. `framed_at` and `inquiry_id` are the two fields that
#: would otherwise change on every generation, and both are excluded by `canonical()`.
FROZEN_NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)


def build() -> Dict[str, Any]:
    """The acceptance frame, from the real deterministic framer. No network, no store.

    `now` is frozen so regenerating an unchanged framer rewrites the file byte for byte. Without
    it the id and the timestamp would move on every generation, and a fixture that always shows a
    diff is a fixture nobody reads the diff of.
    """
    frame = DeterministicFramer().frame(FOLD_PROMPT, FOLD_CORPUS, mode=InquiryMode.EXPLORE,
                                        now=FROZEN_NOW)
    return frame.model_dump(mode="json")


def load() -> Dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def write() -> Path:
    FIXTURE_PATH.write_text(
        json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return FIXTURE_PATH


if __name__ == "__main__":  # pragma: no cover - a maintenance entry point
    print(f"wrote {write()}")
