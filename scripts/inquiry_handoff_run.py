#!/usr/bin/env python3
"""
HARNESS-001B2 §6 — the local proof: a real frame in, one bounded handoff out.

    python scripts/inquiry_handoff_run.py --fixture nested --summary
    python scripts/inquiry_handoff_run.py --fixture fold --summary
    python scripts/inquiry_handoff_run.py --fixture fold --live-sam3 --summary

DETERMINISTIC BY DEFAULT. No database, no network, no clock — the timestamp is the fixture's own and
SAM 3 is replaced by a fixture returning two known nested masks. Two default runs are byte-identical
apart from the fields `--exclude-env` names, which are the ones that measure the machine rather than
the run (`latency_ms`, `device`, and the model tag when a real model answered).

`--live-sam3` runs the SAME path with the real service. If the weights are not on disk the run says
so and stops — it does NOT fall back to the fixture and call the result live. That substitution is
the one thing the directive names outright, and it would be undetectable in the output.

The output is the whole chain: the frame, the goals, the world delta, the projection, the mission's
events and evidence, and the stop reason.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.schemas import inquiry as schema_inquiry                  # noqa: E402
from backend.services import mask_geometry as mg                       # noqa: E402
from backend.services import nestedness_organ as nest                  # noqa: E402
from backend.services import sam3_concept_service as sam3              # noqa: E402
from backend.services.inquiry import frame_prompt                      # noqa: E402
from backend.services.inquiry_engine import engine as eng              # noqa: E402
from backend.services.inquiry_engine.frame import accept               # noqa: E402
from backend.services.inquiry_engine.goals import (KIND_MISSION, KIND_PREPARATION,  # noqa: E402
                                                   AgentMission, PreparationTask)
from backend.services.inquiry_engine.handoff import (evidence_provenance,           # noqa: E402
                                                     run_handoff)
from backend.services.inquiry_engine.production import ProductionDirectorAdapter    # noqa: E402

STAMP = "2026-08-08T00:00:00+00:00"
N = 16
INNER = (5, 11, 6, 12)
OUTER = (2, 14, 2, 15)

#: Fields that measure the MACHINE rather than the run. Excluded from the replay comparison because
#: a wall-clock reading differing between two runs is not a difference in what the run decided.
#:
#: Deliberately only two. Lane A's own rule for its byte-stability helper applies here word for
#: word: *"A byte-stability check must exclude exactly these and nothing else — excluding more would
#: let a real drift hide inside the exclusion list."* An earlier version of this list also carried
#: `model`, `at` and the timestamps, all of which are stable in a fixture run and would have been
#: three places for a real difference to hide.
ENV_FIELDS = ("latency_ms", "device")

#: Lane A's own declaration of what changes on every framing of one prompt — imported rather than
#: restated, so a field it adds later is either stable or deliberately volatile THERE, and never
#: quietly excluded by a copy that drifted.
VOLATILE_FIELDS = schema_inquiry.VOLATILE_FIELDS

#: Everything the replay comparison drops by KEY, and the two reasons are kept apart on purpose: one
#: set is about the machine, the other about the identity of a framing.
EXCLUDED_FIELDS = (*ENV_FIELDS, *VOLATILE_FIELDS)

#: Ids minted per record by production, matched by VALUE PREFIX rather than by key.
#:
#: `nestedness_organ.new_mark_id` is uuid-backed and correctly so — census §4: a positional id would
#: be repointed by the next re-dissect — and the same is true of an agent's percept and ground ids.
#: Excluding the KEY `id` would have been the easy move and the wrong one: a proposed region's id is
#: `cseg_fold_0`, deterministic, and load-bearing for the whole identity rule, so dropping every
#: `id` would hide exactly the drift this replay is meant to catch. Matching the declared prefixes
#: excludes what is genuinely minted and nothing else.
MINTED_ID_PREFIXES = ("vm_nest_", "apc_", "agnd_", "aobs_")

PROMPTS = {
    "nested": ("Segment every fold in this sculpture and tell me which one sits inside which, "
               "measured on the masks."),
    "fold": ("Explore the fold-level aesthetic and style relations between Renaissance and Buddha "
             "sculptures, their common way of unfolding sensuality, where they drift apart, and "
             "what hybrid styles they could give birth to."),
}


def _rle(x0: int, x1: int, y0: int, y1: int) -> Dict[str, Any]:
    bits = [0] * (N * N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * N + x] = 1
    return mg.rle_encode(bits, N, N)


def _posts() -> Dict[str, Dict[str, Any]]:
    return {"post_renaissance": {"_id": "post_renaissance",
                                 "photo_url": "https://example.invalid/renaissance.jpg",
                                 "title": "Pietà, marble", "region_annotations": []},
            "post_buddha": {"_id": "post_buddha",
                            "photo_url": "https://example.invalid/buddha.jpg",
                            "title": "Seated Buddha, Gandhara schist",
                            "region_annotations": []}}


def _install_fixture_sam3() -> None:
    """Replace ONLY the model. `_run_concept_segment`, `instances_to_regions`, the suggestion
    conversion and the context writes are all the production ones."""
    def _segment_concept(image, concept, **kwargs):
        return {"concept": concept, "device": "fixture", "model": "sam3-fixture",
                "latency_ms": 0.0, "truncated": False,
                "instances": [{"mask_rle": _rle(*INNER), "confidence": 0.91, "index": 0},
                              {"mask_rle": _rle(*OUTER), "confidence": 0.84, "index": 1}]}

    sam3.segment_concept = _segment_concept            # type: ignore[assignment]
    sam3.load = lambda **_: None                       # type: ignore[assignment]
    sam3.is_available = lambda: True                   # type: ignore[assignment]

    import backend.routers.posts as posts_router

    async def _fetch(post_id, post):
        return b"fixture-bytes"
    posts_router._fetch_post_image_cached = _fetch     # type: ignore[assignment]


def _scrub(value: Any, fields=EXCLUDED_FIELDS) -> Any:
    """The run with what cannot be stable removed, and nothing else.

    Three classes, each named and each for a different reason — the machine (`ENV_FIELDS`), the
    identity of a framing (Lane A's `VOLATILE_FIELDS`), and per-record minted ids
    (`MINTED_ID_PREFIXES`, by value). Printed under `--exclude-env` so a reader can see exactly what
    was dropped rather than trusting that the comparison was fair.
    """
    if isinstance(value, dict):
        return {k: _scrub(v, fields) for k, v in value.items() if k not in fields}
    if isinstance(value, list):
        return [_scrub(v, fields) for v in value]
    if isinstance(value, str) and value.startswith(MINTED_ID_PREFIXES):
        return f"<minted:{value.split('_')[0]}>"
    return value


def run(fixture: str, *, live: bool) -> Dict[str, Any]:
    if not live:
        _install_fixture_sam3()
    elif not sam3.is_available():
        return {"fixture": fixture, "live": True, "available": False,
                "detail": ("SAM 3 weights are not on this machine (`sam3_concept_service."
                           "is_available()` is False: weights on disk AND the runtime importing). "
                           "This run stops rather than substituting the fixture — a fake reported "
                           "as live would be undetectable in this output."),
                "stop_reason": "execution_unavailable"}

    posts = _posts()
    prompt = PROMPTS[fixture]

    # 1. a REAL frame — Lane A's deterministic framer, no network.
    frame = frame_prompt(prompt, {"post_ids": list(posts),
                                  "titles": [p["title"] for p in posts.values()]})
    accepted = accept(frame.model_dump())

    # 2. the goal hierarchy, from that frame.
    ids = eng._Ids(run_id="handoff")
    inquiry, goals, notes = eng.derive(accepted, ids=ids, post_id="post_renaissance")

    # 3. the preparation the fold/extent goal resolves to, and the mission that will read it.
    target = next((g for g in goals if g.need == "extent_of_a_named_thing"), None)
    phrase = (target.phrase if target else "fold") or "fold"
    task = PreparationTask(id="pt_concept", kind=KIND_PREPARATION, actuator="concept_segment",
                           params={"phrase": phrase}, post_ids=("post_renaissance",),
                           title="concept_segment", parent_goal_id=target.id if target else "")
    mission = AgentMission(id="am_nested", kind=KIND_MISSION, post_id="post_renaissance",
                           region_id="", organ_set=(nest.ORGAN,),
                           question="what does the fold sit inside?",
                           parent_goal_id=target.id if target else "")

    handoff = run_handoff(task, mission, posts,
                          run_id="handoff", inquiry_id=frame.inquiry_id,
                          evidence_goal_id=target.id if target else "eg_none",
                          director=ProductionDirectorAdapter(), phrase=phrase, now=STAMP)

    return {
        "fixture": fixture,
        "live": live,
        "prompt": prompt,
        "frame": {"inquiry_id": frame.inquiry_id, "mode": accepted.mode,
                  "attentions": list(accepted.attentions),
                  "demands": [d.to_dict() for d in accepted.epistemic_demands],
                  "unresolved_terms": [t.to_dict() for t in accepted.unresolved_terms],
                  "adjustments": list(accepted.adjustments)},
        "goals": [inquiry.to_dict(), *(g.to_dict() for g in goals)],
        "notes": list(notes),
        "handoff": handoff.to_dict(),
        "evidence_provenance": evidence_provenance(handoff),
        "stop_reason": (handoff.reasons[0] if handoff.reasons
                        else ("satisfied" if handoff.usable else "no_new_evidence")),
    }


def _summary(payload: Dict[str, Any]) -> str:
    if payload.get("available") is False:
        return f"live SAM 3: UNAVAILABLE\n{payload['detail']}"
    handoff = payload["handoff"] or {}
    delta = handoff.get("delta") or {}
    mission = handoff.get("mission") or {}
    lines = [
        f"fixture      {payload['fixture']}  (live={payload['live']})",
        f"inquiry      {payload['frame']['inquiry_id']}",
        f"goals        {len(payload['goals'])}",
        f"delta        {sum(len(p['proposed_regions']) for p in delta.get('per_post', []))} "
        f"proposed region(s), "
        f"{sum(len(p['suggestions']) for p in delta.get('per_post', []))} descriptor(s)",
        f"projected    {', '.join(handoff.get('projected_post_ids') or []) or 'none'}",
        f"locus        {handoff.get('locus', {}).get('post_id')}/"
        f"{handoff.get('locus', {}).get('region_id')}",
        f"perceptions  {len(mission.get('perceptions') or [])}",
        f"marks        {len(mission.get('marks') or [])}",
        f"usable       {handoff.get('usable')}",
        f"reasons      {', '.join(handoff.get('reasons') or []) or 'none'}",
        f"stop         {payload['stop_reason']}",
        f"posts        {'unchanged' if handoff.get('posts_unchanged') else 'MUTATED'}",
    ]
    for mark in (mission.get("marks") or []):
        lines.append(f"  mark       {mark.get('epistemic_status')} "
                     f"{(mark.get('measurement') or {}).get('basis')} "
                     f"{mark.get('label')}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("--fixture", choices=sorted(PROMPTS), default="nested")
    parser.add_argument("--live-sam3", action="store_true",
                        help="use the real SAM 3 service; reports UNAVAILABLE rather than "
                             "substituting the fixture")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--exclude-env", action="store_true",
                        help=f"print the run without {list(EXCLUDED_FIELDS)} — the form two "
                             f"default runs must match byte for byte")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    payload = run(args.fixture, live=args.live_sam3)
    shown = _scrub(payload) if args.exclude_env else payload
    text = json.dumps(shown, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(_summary(payload) if args.summary else text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
