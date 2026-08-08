#!/usr/bin/env python3
"""
HARNESS-001B2 — drive the whole handoff locally and look at it.

    python scripts/inquiry_handoff_run.py --fixture nested --summary
    python scripts/inquiry_handoff_run.py --fixture fold --summary
    python scripts/inquiry_handoff_run.py --fixture fold --live-sam3 --summary
    python scripts/inquiry_handoff_run.py --fixture nested --json

    prompt → InquiryFrame → goals → real Director execution → PreparedWorldDelta
           → ephemeral world → real situated mission → organ measurement → stop reason

DEFAULT IS DETERMINISTIC AND OFFLINE, and structurally so rather than by promise: the default
run replaces `sam3_concept_service` with the fixture and `_fetch_post_image_cached` with a
constant, so there is no checkpoint to load and no URL to fetch. It opens no database — the posts
are built in memory by `handoff_fixtures`.

`--live-sam3` is the ONLY flag that reaches a real model, and it says so in the receipt. If the
weights are not on disk it reports that and does not substitute a fake.

TWO DEFAULT RUNS ARE BYTE-IDENTICAL apart from `VOLATILE` and `MINTED_ID_PREFIXES`, which is
checked by `test_inquiry_handoff_vertical.py` rather than asserted here.

NOTHING IS COMMITTED. Every Region stays `proposed`, no post is written, and the source posts are
fingerprinted before and after.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.inquiry import frame_prompt                       # noqa: E402
from backend.services.inquiry_engine import handoff_fixtures as fx      # noqa: E402
from backend.services.inquiry_engine.adapters import SimulatorAdapter   # noqa: E402
from backend.services.inquiry_engine.frame import accept                # noqa: E402
from backend.services.inquiry_engine.goals import AgentMission, PreparationTask  # noqa: E402
from backend.services.inquiry_engine.production import ProductionDirectorAdapter  # noqa: E402
from backend.services.inquiry_engine.projection import run_handoff      # noqa: E402

#: Two named worlds. `nested` is the smallest one in which an organ can measure containment;
#: `fold` is the same geometry under the wave's own concept, so the receipt reads against the
#: acceptance prompt.
FIXTURES = {
    "nested": {"concept": "nested form",
               "prompt": "Where does one form sit inside another in these sculptures?"},
    "fold": {"concept": "fold",
             "prompt": ("Explore the fold-level aesthetic and style relations between "
                        "Renaissance and Buddha sculptures, their common way of unfolding "
                        "sensuality, where they drift apart, and what hybrid styles they could "
                        "give birth to.")},
}

POST_A = "handoff_post_a"
POST_B = "handoff_post_b"
RUN_ID = "run_handoff_local"
NOW = "2026-08-08T12:00:00Z"

#: The only FIELDS allowed to differ between two default runs.
VOLATILE = ("inquiry_id", "framed_at", "latency_ms", "prompt_sha256")

#: The only VALUES allowed to differ: identities minted from a uuid at the moment of making.
#: `nestedness_organ.new_mark_id`, `situated_agent`'s percept and region-ground ids, and
#: `agents.observation`'s observation ids are all `uuid4`-derived by construction, in
#: `backend/services/agents/`, which this lane does not own.
#:
#: They are excluded BY PREFIX rather than by stripping every `id` key, and the difference
#: matters: `cseg_fold_0` is also an `id`, and it is a Region identity that must be compared. A
#: filter that dropped all ids would let two runs disagree about WHICH REGION was measured and
#: still call the run reproducible.
MINTED_ID_PREFIXES = ("vm_", "apc_", "agnd_", "aobs_")


@contextmanager
def _fixture_services(concept: str):
    """Replace the model and the network for the duration of one run, and PUT THEM BACK.

    The restoration is not tidiness. This module is imported by
    `test_inquiry_handoff_vertical.py`, and an unrestored
    `sys.modules["backend.services.sam3_concept_service"]` leaks the fake into every test that
    runs after it in the same process. That is not hypothetical: it broke five of Lane C's SAM 3
    lab tests, which pass alone and failed once this script had run — nothing of theirs was wrong,
    the module they probe had simply been replaced underneath them. A script that is also a
    library has to clean up after itself.
    """
    name = "backend.services.sam3_concept_service"
    service = fx.FakeSam3Service(fx.sam_result(concept))
    posts_mod = importlib.import_module("backend.routers.posts")
    had_module = name in importlib.sys.modules
    previous_module = importlib.sys.modules.get(name)
    previous_fetch = posts_mod._fetch_post_image_cached

    async def _bytes(post_id, post):
        return b"fixture-image-bytes"

    importlib.sys.modules[name] = service
    posts_mod._fetch_post_image_cached = _bytes
    try:
        yield service
    finally:
        if had_module:
            importlib.sys.modules[name] = previous_module
        else:
            importlib.sys.modules.pop(name, None)
        posts_mod._fetch_post_image_cached = previous_fetch


def _live_sam3_status() -> Tuple[bool, str]:
    """Is a real SAM 3 actually available? Reported, never assumed, never substituted."""
    try:
        service = importlib.import_module("backend.services.sam3_concept_service")
    except Exception as exc:                                   # noqa: BLE001
        return False, f"sam3_concept_service did not import: {type(exc).__name__}: {exc}"
    try:
        if service.is_available():
            return True, f"weights present; model {getattr(service, 'CHECKPOINT', 'unknown')}"
        return False, ("SAM3_WEIGHTS are not on disk. Reported as unavailable rather than "
                       "substituted — a fake called live would be the one lie this script "
                       "cannot afford.")
    except Exception as exc:                                   # noqa: BLE001
        return False, f"availability probe raised {type(exc).__name__}: {exc}"


def run(fixture: str = "nested", *, live_sam3: bool = False,
        both_posts: bool = False) -> Dict[str, Any]:
    spec = FIXTURES[fixture]
    concept = spec["concept"]

    live_ok, live_detail = (False, "not requested")
    if live_sam3:
        live_ok, live_detail = _live_sam3_status()
    # The fixture services are scoped to this run and restored afterwards. `--live-sam3` with real
    # weights installs nothing at all.
    services = nullcontext() if (live_sam3 and live_ok) else _fixture_services(concept)
    with services:
        return _run_inside(fixture, spec, concept, live_sam3, live_ok, live_detail,
                           both_posts)


def _run_inside(fixture: str, spec, concept: str, live_sam3: bool, live_ok: bool,
                live_detail: str, both_posts: bool) -> Dict[str, Any]:
    post_ids = [POST_A, POST_B] if both_posts else [POST_A]
    posts = {pid: fx.post(pid) for pid in post_ids}

    # ── the prompt becomes an inquiry (Lane A), which becomes goals (Lane B) ──
    frame = frame_prompt(spec["prompt"], {"post_ids": post_ids,
                                          "titles": [f"fixture {p}" for p in post_ids]})
    accepted = accept(frame.model_dump())

    task = PreparationTask(id="pt_1", parent_goal_id="eg_1",
                           title=f"measure '{concept}'", actuator="concept_segment",
                           params={"phrase": concept}, post_ids=tuple(post_ids))
    mission = AgentMission(id="am_1", parent_goal_id="eg_1", organ_set=("nestedness_organ",),
                           question="what contains what, from where I stand?", budget=0)

    adapter = ProductionDirectorAdapter()
    _result, delta = adapter.prepare_world(task, posts, run_id=RUN_ID, inquiry_id=frame.inquiry_id,
                                           evidence_goal_id="eg_1", now=NOW)
    outcome = run_handoff(delta, posts, simulator=SimulatorAdapter(), mission=mission,
                          run_id=RUN_ID, inquiry_id=frame.inquiry_id, evidence_goal_id="eg_1",
                          now=NOW)

    stop_reason = ("an organ measured from prepared geometry" if outcome.dispatched
                   else outcome.reason)
    return {
        "fixture": fixture,
        "concept": concept,
        "live_sam3": {"requested": live_sam3, "used": bool(live_sam3 and live_ok),
                      "detail": live_detail},
        "frame": {"inquiry_id": frame.inquiry_id, "prompt": frame.prompt,
                  "mode": frame.mode.value,
                  "attentions": list(accepted.attentions),
                  "epistemic_demands": list(accepted.epistemic_demands),
                  "unresolved_terms": list(accepted.unresolved_terms),
                  "semantic_remainder": list(accepted.semantic_remainder),
                  "proposed_actions": [a.type for a in accepted.proposed_actions]},
        "goals": {"preparation": task.id, "mission": mission.id,
                  "organ_set": list(mission.organ_set)},
        "world_delta": delta.to_dict(),
        "projection": outcome.world.to_dict() if outcome.world is not None else None,
        "mission": outcome.to_dict(),
        "stop_reason": stop_reason,
        "posts_unchanged": bool(delta.posts_unchanged and outcome.posts_unchanged),
    }


def _strip_volatile(payload: Any) -> Any:
    """The receipt with the volatile fields and minted identities removed, for comparing runs."""
    if isinstance(payload, dict):
        return {k: _strip_volatile(v) for k, v in payload.items() if k not in VOLATILE}
    if isinstance(payload, list):
        return [_strip_volatile(v) for v in payload]
    if isinstance(payload, str) and payload.startswith(MINTED_ID_PREFIXES):
        return "<minted>"
    return payload


def summarise(receipt: Dict[str, Any]) -> str:
    out: List[str] = []
    frame = receipt["frame"]
    delta = receipt["world_delta"]
    mission = receipt["mission"]

    out.append("─" * 78)
    out.append(f"FIXTURE {receipt['fixture']} · concept {receipt['concept']!r}")
    live = receipt["live_sam3"]
    out.append(f"SAM 3: {'LIVE' if live['used'] else 'deterministic fixture'} — {live['detail']}")
    out.append("")
    out.append(f"PROMPT\n  {frame['prompt']}")
    out.append(f"  → {len(frame['attentions'])} attention(s), "
               f"{len(frame['epistemic_demands'])} demand(s), "
               f"{len(frame['unresolved_terms'])} unresolved, "
               f"{len(frame['semantic_remainder'])} left over")
    out.append("")
    out.append("WORLD DELTA — what preparation ADDED. Not a ledger.")
    out.append(f"  availability: {delta['availability']}")
    for post in delta["per_post"]:
        out.append(f"  post {post['post_id']}")
        for region in post["proposed_regions"]:
            out.append(f"      region {region['id']}  proposed={region['proposed']}  "
                       f"rev={region.get('geometry_rev')}  mask={'yes' if region.get('mask_rle') else 'no'}")
        for descriptor in post["suggestions"]:
            geometry = descriptor.get("geometry") or {}
            ref = (geometry.get("mask_ref") or geometry.get("region_ref") or {})
            out.append(f"      {descriptor['epistemic_status']:12} {descriptor['producer']:17}"
                       f" → {ref.get('region_id')}")
    if delta["refusals"]:
        out.append("  refusals:")
        for refusal in delta["refusals"]:
            out.append(f"      [{refusal.get('reason')}] {refusal.get('detail')}")

    out.append("")
    out.append("MISSION — a body, standing on prepared geometry.")
    out.append(f"  dispatched: {mission['dispatched']}  locus: "
               f"{mission['locus']['post_id']}/{mission['locus']['region_id']}")
    for mark in mission["organ_marks"]:
        measurement = mark.get("measurement") or {}
        out.append(f"  {mark.get('epistemic_status')} · {mark['provenance']['producer']} · "
                   f"basis={measurement.get('basis')}")
        out.append(f"      {mark.get('label')}")
        out.append(f"      {measurement.get('detail')}")
    if not mission["organ_marks"]:
        out.append(f"  no organ measurement — {mission['reason']}: {mission['detail']}")

    out.append("")
    out.append(f"STOP REASON  {receipt['stop_reason']}")
    out.append(f"LEDGER       every region proposed; posts unchanged: "
               f"{receipt['posts_unchanged']}")
    out.append("─" * 78)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Drive the prepared-world → situated-mission handoff.")
    ap.add_argument("--fixture", choices=sorted(FIXTURES), default="nested")
    ap.add_argument("--both-posts", action="store_true",
                    help="run the same concept on two posts, to show ids cannot collide")
    ap.add_argument("--live-sam3", action="store_true",
                    help="use the real SAM 3 if its weights are on disk. THE ONLY NETWORKED/GPU "
                         "PATH; reports unavailability rather than substituting a fake")
    ap.add_argument("--summary", action="store_true", help="human-readable receipt")
    ap.add_argument("--json", action="store_true", help="the whole receipt as JSON")
    args = ap.parse_args()

    receipt = run(args.fixture, live_sam3=args.live_sam3, both_posts=args.both_posts)
    if args.json:
        print(json.dumps(receipt, indent=2, ensure_ascii=False, default=str))
    else:
        print(summarise(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
