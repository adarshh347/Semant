#!/usr/bin/env python3
"""
HARNESS-002D — drive one whole inquiry from the command line and look at what it did.

    python scripts/inquiry_rehearse.py                          # consult, paused then answered
    python scripts/inquiry_rehearse.py --mode auto              # no pause at all
    python scripts/inquiry_rehearse.py --fixture unrelated-domain
    python scripts/inquiry_rehearse.py --answer 2               # pick the second option
    python scripts/inquiry_rehearse.py --reject                 # decline every option
    python scripts/inquiry_rehearse.py --replay-check           # prove a replay is byte-identical
    python scripts/inquiry_rehearse.py --json > session.json

    python scripts/inquiry_rehearse.py --live --image URL --image URL --prompt "…"

WHAT THIS IS FOR. The whole Phase 1 chain, in one process, with no server, no database and no
browser — so the consult and auto paths are repeatable rather than something somebody once did by
hand. `--replay-check` runs the same session twice and compares, which is the proof that a frozen
replay reproduces a session exactly.

OFFLINE BY DEFAULT AND READ-ONLY ALWAYS. Without `--live` nothing reaches a network. Nothing here
opens the database in any mode: fixture mode uses frozen posts, and `--live` takes image URLs on
the command line for the same reason `semantic_compile.py` does — resolving a post id would mean
opening the corpus this script promises not to touch.

WHAT YOU ARE LOOKING AT. Nothing in the output is a finding. Every claim is at most interpretive,
the single capability receipt is a declared SIMULATION whose coordinates come from a hash of the
request text, and no evidence object exists anywhere in Phase 1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.schemas.inquiry_session import canonical  # noqa: E402
from backend.services.inquiry_session import coordinator, view  # noqa: E402
from backend.services.inquiry_session.capability import LockedFixtureCapability  # noqa: E402
from backend.services.inquiry_session.composer import (DeterministicComposer,  # noqa: E402
                                                       ModelSynthesisComposer)
from backend.services.inquiry_session.judge import judge, tally  # noqa: E402
from backend.tests.fixtures import inquiry_session_fixtures as F  # noqa: E402

AT = "2026-08-09T00:00:00+00:00"


def build(args) -> coordinator.Stages:
    common = dict(capability=LockedFixtureCapability(), judge=judge)
    if not args.live:
        return F.stages_for(args.fixture, clock=F.frozen_clock(AT),
                            composer=DeterministicComposer(), **common)

    from backend.services.inquiry import get_framer
    from backend.services.semantic_compilation.compiler import ModelSemanticCompiler
    from backend.services.semantic_compilation.theorist import ModelSceneTheorist
    return coordinator.Stages(framer=get_framer("deterministic"),
                              theorist=ModelSceneTheorist(), compiler=ModelSemanticCompiler(),
                              composer=ModelSynthesisComposer(), **common)


def posts_for(args):
    from backend.schemas.inquiry_session import PostRef
    if not args.live:
        return F.post_refs(args.fixture)
    refs = []
    for index, spec in enumerate(args.image):
        url, _, title = spec.partition("|")
        refs.append(PostRef(post_id=f"img_{index}", title=title.strip(),
                            image_ref=url.strip(), fingerprint="", readable=bool(url.strip())))
    return refs


def drive(args, stages, *, session_id: Optional[str] = None):
    """One session, from the prompt to wherever it honestly stops."""
    prompt = args.prompt or F.prompt_for(args.fixture)
    session = coordinator.new_session(prompt=prompt, refs=posts_for(args), mode=args.mode,
                                      session_id=session_id, now=AT if not args.live else None)
    session = coordinator.begin(session, stages)
    if not session.awaiting_user:
        return session, None

    request = coordinator.machine.from_dict(session.interaction).open_decision
    if args.reject:
        answer = {"kind": "reject_all"}
    elif args.redirect:
        answer = {"kind": "redirect", "free_text": args.redirect}
    else:
        index = max(1, min(args.answer, len(request.options))) - 1
        answer = {"kind": "select_option", "option_id": request.options[index].option_id}
    payload = {"response_id": "resp_rehearsal", "session_id": session.session_id,
               "decision_id": request.decision_id, "expected_revision": session.revision,
               "at": stages.clock(), **answer}
    return coordinator.resume(session, payload, stages), request


# ── printing ─────────────────────────────────────────────────────────────────

def show(session, request, args) -> None:
    out = sys.stdout
    print(f"\nsession   {session.session_id}   {session.mode} mode", file=out)
    print(f"question  {session.prompt}", file=out)
    print(f"images    {', '.join(p.post_id for p in session.posts)}", file=out)

    print("\nstages", file=out)
    for event in session.stages:
        print(f"  {event.stage.value:11} {event.outcome.value:12} {event.detail}", file=out)

    reading = (session.graph.get("reading") or {})
    if reading.get("text"):
        print(f"\nreading   [{reading.get('status')}] {reading['text'][:220]}…", file=out)

    claims = session.graph.get("claims") or []
    print(f"\nclaims    {len(claims)}", file=out)
    for claim in claims:
        verdict = session.verdict_for(claim["claim_id"])
        print(f"  {claim['claim_kind']:22} {claim['status']:13} "
              f"{(verdict.outcome.value if verdict else '—'):20} {claim['text'][:70]}", file=out)

    if request is not None:
        print(f"\nthe fork  {request.question}", file=out)
        print(f"          why now: {request.why_now}", file=out)
        for option in request.options:
            mark = "*" if option.recommended else " "
            print(f"        {mark} {option.label}  "
                  f"[reversible={option.reversible}]  {option.consequence[:60]}", file=out)

    records = (coordinator.machine.from_dict(session.interaction).records
               if coordinator.has_interaction(session) else [])
    for record in records:
        print(f"\ndecided   {record.outcome} by {record.actor.value}: {record.reason}", file=out)

    for receipt in session.capability_receipts:
        print(f"\nreceipt   {receipt.capability} · mode={receipt.execution_mode.value} · "
              f"status={receipt.status.value} · usable_as_evidence="
              f"{receipt.usable_as_evidence} · attempted={receipt.attempted}", file=out)
        for proposal in receipt.payload.get("proposals") or []:
            print(f"          “{proposal['phrase']}” → {proposal['region']}", file=out)

    print(f"\nverdicts  {tally(session.verdicts)}", file=out)
    print(f"evidence  {len(session.evidence)} object(s)", file=out)

    if session.synthesis:
        print(f"\nanswer    {session.synthesis.note}\n", file=out)
        for section in session.synthesis.sections:
            print(f"  [{section.status}] {section.heading}", file=out)
            print(f"      {section.text[:400]}", file=out)
            print(f"      claims={len(section.claim_refs)} evidence={len(section.evidence_refs)} "
                  f"decisions={len(section.decision_refs)}\n", file=out)

    print(f"state     {session.state}   revision {session.revision}", file=out)
    if session.stop_reason:
        print(f"stopped   {session.stop_reason}", file=out)


def replay_check(args) -> int:
    """Run the same session twice and compare. The proof that a frozen replay reproduces exactly."""
    if args.live:
        print("--replay-check is offline only: two live calls are two different readings.",
              file=sys.stderr)
        return 2

    first, _ = drive(args, build(args), session_id="inqs_replay")
    calls_first = _model_calls(first)
    second, _ = drive(args, build(args), session_id="inqs_replay")

    a, b = canonical(first), canonical(second)
    if a == b:
        print(f"REPLAY IDENTICAL — {args.fixture} · {args.mode} · "
              f"{len(json.dumps(a))} bytes compared, volatile fields excluded by name")
        print(f"                   live model calls on replay: {calls_first}")
        return 0

    print("REPLAY DIFFERED. The two runs are not the same session.", file=sys.stderr)
    for line in _diff(a, b)[:40]:
        print(f"  {line}", file=sys.stderr)
    return 1


def _model_calls(session) -> int:
    """How many times a live provider was reached. Zero on a replay, and it is printed rather than
    promised: a replay that quietly called a model would still be byte-identical if the model were
    deterministic, and nothing in the output would say so."""
    receipts = [(session.graph.get("provenance") or {}).get("theorist"),
                (session.graph.get("provenance") or {}).get("compiler")]
    return sum(int((r or {}).get("call_count") or 0) for r in receipts
               if (r or {}).get("call_topology") not in ("replay", "unavailable", None))


def _diff(a: Any, b: Any, path: str = "$") -> List[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            if key not in a:
                out.append(f"{path}.{key}: only in the second run")
            elif key not in b:
                out.append(f"{path}.{key}: only in the first run")
            else:
                out += _diff(a[key], b[key], f"{path}.{key}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: {len(a)} vs {len(b)} item(s)"]
        return [line for i, (x, y) in enumerate(zip(a, b)) for line in _diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixture", default=F.FIXTURES[0], choices=list(F.FIXTURES))
    parser.add_argument("--mode", default="consult", choices=["auto", "consult", "step"])
    parser.add_argument("--prompt", default="")
    parser.add_argument("--image", action="append", default=[],
                        help="live only: an image URL, optionally 'URL|title'")
    parser.add_argument("--answer", type=int, default=1, help="which option to choose (1-based)")
    parser.add_argument("--reject", action="store_true", help="decline every option")
    parser.add_argument("--redirect", default="", help="answer in your own words instead")
    parser.add_argument("--live", action="store_true", help="reach the real models")
    parser.add_argument("--replay-check", action="store_true")
    parser.add_argument("--json", action="store_true", help="the wire body, as the routes serve it")
    args = parser.parse_args()

    if args.live and not args.image:
        parser.error("--live needs at least one --image URL")
    if args.replay_check:
        return replay_check(args)

    stages = build(args)
    session, request = drive(args, stages)
    if args.json:
        json.dump(view.session_view(
            session, servable_classes=coordinator.servable_classes(stages)),
            sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        show(session, request, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
