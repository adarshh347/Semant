#!/usr/bin/env python3
"""
HARNESS-001B §8 — the local proof: one frame in, one JSON `InquiryRun` out.

    python scripts/inquiry_goal_run.py --frame control
    python scripts/inquiry_goal_run.py --frame fold
    python scripts/inquiry_goal_run.py --frame fold --summary

FIXTURE / REPLAY BY DEFAULT. No database, no model, no network, no clock — the timestamp is the
fixture's own, so two runs of the same frame produce byte-identical JSON. That is what makes this a
replay rather than a demo, and it is why the output can be diffed in a review.

`--live` is where real infrastructure would be reached, and the rule the directive states is the one
this script keeps: **unavailable infrastructure produces an explicit event, never a fake green run.**
With no actuator registry the Director adapter's steps come back UNAVAILABLE from
`execution.execute` — the existing honest path — and the run stops `execution_unavailable` with the
reason on the record. Nothing is stubbed in to make the output look fuller.

The end of this lane is NOT article generation. There is no prose in this output and there is no
place to put any: what it emits is the first causal history in which global preparation and embodied
investigation appear as one chain.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.inquiry_engine import fixtures                      # noqa: E402
from backend.services.inquiry_engine.adapters import (DirectorAdapter,    # noqa: E402
                                                      FakeDirectorAdapter, SimulatorAdapter)
from backend.services.inquiry_engine.engine import run_inquiry            # noqa: E402
from backend.services.inquiry_engine.events import InquiryRun             # noqa: E402

#: What a fixture Director hands back for the fold frame, so the measurable half of that inquiry has
#: something real to be evaluated against. It is a DESCRIPTOR carrying its own stamped status — the
#: shape a real `concept_segment` suggestion has — and not a fabricated measurement: nothing here
#: invents geometry, and the descriptor is what a curator would be shown to accept or reject.
_FOLD_SUGGESTION: Dict[str, Any] = {
    "id": None,                       # a quarantined suggestion has no id until it is accepted
    "type": "region_mask",
    "role": "fold",
    "producer": "concept_segment",
    "epistemic_status": "measured",
    "label": "fold",
    "provenance": {"producer": "concept_segment", "adapter": "fixture:concept_segment"},
}


def _director(frame_name: str, live: bool):
    """The Director half. Live gets the real adapter with NO registry, which is the honest empty."""
    if live:
        # No registry on purpose: `execution.execute` records `no runner registered` as UNAVAILABLE
        # per step. A stub registry here would make an unwired environment look like a working one.
        return DirectorAdapter()
    if frame_name == "fold":
        return FakeDirectorAdapter(suggestions=[_FOLD_SUGGESTION], ran=True, available=True)
    return FakeDirectorAdapter(ran=False, available=False)


def _summary(run: InquiryRun) -> str:
    lines = [f"run          {run.run_id}",
             f"outcome      {run.outcome}  ({run.stop_reason})",
             f"rounds       {run.rounds}",
             f"events       {len(run.events)}",
             f"evidence     {len(run.evidence)}",
             "goals:"]
    for goal in run.goals:
        lines.append(f"  {goal.status:<21} {goal.kind:<12} {goal.title[:56]}")
    if run.gaps:
        lines.append("capability gaps:")
        for gap in run.gaps:
            lines.append(f"  {gap.need}")
            for unmet in gap.unmet:
                lines.append(f"      unmet: {unmet}")
    for note in run.notes:
        lines.append(f"note         {note}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("--frame", choices=sorted(fixtures.FRAMES), default="control",
                        help="which committed fixture frame to run")
    parser.add_argument("--live", action="store_true",
                        help="use the real Director adapter (unavailable infrastructure is "
                             "reported as an event, never stubbed around)")
    parser.add_argument("--summary", action="store_true",
                        help="print a human summary instead of the JSON run")
    parser.add_argument("--out", default="", help="write the JSON run to this path")
    args = parser.parse_args(argv)

    if args.frame == "control":
        posts, graph, marks = fixtures.control_world()
        run = run_inquiry(fixtures.control_frame(), posts=posts, now=fixtures.STAMP,
                          post_id="post_renaissance", region_id="finial",
                          graph=graph, proposed_marks=marks,
                          director=_director("control", args.live),
                          simulator=SimulatorAdapter())
    else:
        run = run_inquiry(fixtures.fold_frame(), posts=fixtures.fold_world(),
                          now=fixtures.STAMP, post_id="post_renaissance", region_id="drapery",
                          director=_director("fold", args.live),
                          simulator=SimulatorAdapter())

    payload = json.dumps(run.to_dict(), indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    if args.summary:
        print(_summary(run))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
