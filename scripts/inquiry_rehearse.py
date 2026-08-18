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
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.schemas.inquiry_session import canonical  # noqa: E402
from backend.services.inquiry_session import coordinator, runtime, view  # noqa: E402
from backend.services.inquiry_session.capability import LockedFixtureCapability  # noqa: E402
from backend.services.inquiry_session.composer import DeterministicComposer  # noqa: E402
from backend.services.inquiry_session.judge import judge, tally  # noqa: E402
from backend.tests.fixtures import inquiry_session_fixtures as F  # noqa: E402

AT = "2026-08-09T00:00:00+00:00"


def build(args) -> coordinator.Stages:
    """Offline: the frozen stage order. Live: THE PRODUCTION BINDING, and nothing else.

    HARNESS-003D. This used to construct its own live stage order — framer, theorist,
    `ModelSemanticCompiler`, composer — which was the same list `runtime.build_stages()` produced
    on the day it was written and stopped being so the moment 003A's council was bound. A rehearsal
    that assembles its own approximation of production rehearses the approximation: it would have
    reported a healthy v1 compilation for a deployment whose `/inquiry` runs five passes.

    So `--live` calls the one function a route calls. The capability stays the locked fixture in
    both, because Phase 1's single capability is a declared simulation in production too.
    """
    common = dict(capability=LockedFixtureCapability(), judge=judge)
    if not args.live:
        return F.stages_for(args.fixture, clock=F.frozen_clock(AT),
                            composer=DeterministicComposer(), **common)
    return runtime.build_stages(**common)


#: One event loop for the whole process, and it is not an optimisation.
#:
#: `motor` binds its client to the loop it first runs in, so a second `asyncio.run` — which builds
#: and closes a fresh loop each time — raises `RuntimeError: Event loop is closed` from inside the
#: driver, several frames from the call that caused it. This script reads the archive twice, before
#: and after, which is exactly the shape that trips it.
_LOOP: Optional[Any] = None


def _await(coro):
    global _LOOP
    if _LOOP is None:
        _LOOP = asyncio.new_event_loop()
    return _LOOP.run_until_complete(coro)


def posts_for(args):
    """The images this rehearsal reads.

    THREE SOURCES, and the third is the one HARNESS-003F added. `--post` resolves REAL post ids
    through the same `corpus.resolve` the route uses, so the refs carry the repository's own
    fingerprints — which is what makes "no post moved" a comparison this script can perform rather
    than a sentence it prints. `--image` keeps working for a URL nobody has archived, and its refs
    carry no fingerprint because there is no document to take one over.

    003E's finding had to record its four post ids in prose because the rehearsal held its session
    in process and read URLs; this is the repair for that, one lane later.
    """
    from backend.schemas.inquiry_session import PostRef
    if not args.live:
        return F.post_refs(args.fixture)
    refs = []
    if args.post:
        from backend.services.inquiry_session import corpus
        resolved, _docs = _await(corpus.resolve(args.post))
        refs.extend(resolved)
    for index, spec in enumerate(args.image):
        url, _, title = spec.partition("|")
        refs.append(PostRef(post_id=f"img_{index}", title=title.strip(),
                            image_ref=url.strip(), fingerprint="", readable=bool(url.strip())))
    return refs


def fingerprints(refs) -> Dict[str, str]:
    """Every selected post's fingerprint, read from the archive RIGHT NOW.

    Taken before and after the run and compared, because §8 asks for both and because the one
    guarantee that has to hold whether or not anything else did is that nothing moved. A ref with no
    fingerprint (a bare `--image` URL) is not in this map: there is no document behind it to move.
    """
    ids = [r.post_id for r in refs if r.fingerprint]
    if not ids:
        return {}
    from backend.services.inquiry_session import corpus
    fresh, _docs = _await(corpus.resolve(ids))
    return {r.post_id: r.fingerprint for r in fresh}


def drive(args, stages, *, session_id: Optional[str] = None):
    """One session, from the prompt to wherever it honestly stops."""
    prompt = args.prompt or F.prompt_for(args.fixture)
    session = coordinator.new_session(prompt=prompt, refs=posts_for(args), mode=args.mode,
                                      session_id=session_id, now=AT if not args.live else None,
                                      execution_scope=args.scope)
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

def _show_plan(plan: Optional[Dict[str, Any]], out) -> None:
    """How the pass was cut into sendable requests, and what that cost in coverage. HARNESS-003E.

    NOTHING AT ALL for a pass that was never partitioned, because the ledger and the audit make no
    request and a plan on them reading `1 batch` would report a partition that never happened.

    The unexamined pairs print IN FULL with their reasons. A pair nobody compared is a relation
    nobody looked for, and a transcript that gave a count would be reporting the size of a gap
    instead of where it is.
    """
    if not isinstance(plan, dict):
        return
    batches = plan.get("batches") or []
    pairs = plan.get("pairs") or []
    rounds = plan.get("rounds") or []
    sizes = [int(b.get("estimated_prompt_tokens") or 0) + int(b.get("requested_completion_tokens")
                                                              or 0) for b in batches]
    unsendable = [b for b in batches if b.get("sendable") is False]
    print(f"      plan   {len(batches)} batch(es) over {plan.get('total_items')} "
          f"{plan.get('unit')}(s) · largest request ~{max(sizes) if sizes else 0} of "
          f"{batches[0].get('allowance_tokens') if batches else '—'} allowed", file=out)
    for batch in batches:
        print(f"        · {str(batch.get('batch_id')):18} "
              f"{len(batch.get('primary_refs') or []):3} primary, "
              f"{len(batch.get('context_refs') or []):3} context  "
              f"~{int(batch.get('estimated_prompt_tokens') or 0)}+"
              f"{int(batch.get('requested_completion_tokens') or 0)}  "
              f"{batch.get('boundary_reason')}"
              f"{'  UNSENDABLE' if batch.get('sendable') is False else ''}", file=out)
    if unsendable:
        print(f"      {len(unsendable)} batch(es) were too large to send and were refused before "
              f"transport", file=out)

    examined = sum(1 for p in pairs if p.get("examined"))
    if pairs:
        print(f"      pairs  {examined} of {len(pairs)} batch pair(s) compared across "
              f"{len(rounds)} round(s)", file=out)
    else:
        print("      pairs  one batch, so there was nothing across to compare", file=out)
    for entry in rounds:
        print(f"        · {str(entry.get('round_id')):18} groups "
              f"{len(entry.get('group_ids') or [])}  {entry.get('outcome')}  "
              f"+{entry.get('added_edges')} edge(s), +{entry.get('added_claims')} claim(s), "
              f"{entry.get('duplicate_claims')} duplicate(s)", file=out)
    for pair in [p for p in pairs if not p.get("examined")]:
        print(f"        · NEVER COMPARED  {pair.get('left_batch_id')} / "
              f"{pair.get('right_batch_id')} — {pair.get('reason')}", file=out)

    kinds: Dict[str, int] = {}
    for entry in plan.get("dispositions") or []:
        key = str(entry.get("disposition"))
        kinds[key] = kinds.get(key, 0) + 1
    if kinds:
        print("      became " + " · ".join(f"{k} {v}" for k, v in sorted(kinds.items())), file=out)
    if plan.get("duplicate_map"):
        print(f"      merged {len(plan['duplicate_map'])} duplicate claim(s)", file=out)


def _show_council(session, out) -> None:
    """The five passes, what became of every source unit, and where the wall clock went.

    HARNESS-003D. A v1 graph has none of this and prints none of it — an absent council is not a
    council that produced nothing, and a transcript that showed `0 passes` for a one-call compiler
    would report the version as a failure.

    `sends` is printed apart from `calls` wherever they differ. They differ only when the provider
    refused for capacity and the SAME bytes went again, so the gap is a fact about the account's
    allowance and never about the compiler having asked more.
    """
    graph = session.graph or {}
    passes = graph.get("passes") or []
    units = graph.get("source_units") or []
    if not passes and not units:
        return

    print(f"\ncouncil   {len(passes)} pass(es)", file=out)
    waited_total = 0.0
    for receipt in passes:
        calls = receipt.get("call_count")
        sends = receipt.get("transport_attempts")
        waited = receipt.get("waited_ms")
        waited_total += float(waited or 0)
        line = (f"  {str(receipt.get('pass_name')):27.27} {str(receipt.get('outcome')):15.15}"
                f" {(receipt.get('duration_ms') or 0) / 1000:7.1f}s"
                f"  {calls if calls is not None else '—'} call(s)")
        if sends is not None and sends != calls:
            line += f", {sends} send(s)"
        if waited:
            line += f", waited {waited / 1000:.1f}s"
        print(line, file=out)
        if receipt.get("detail"):
            print(f"      {str(receipt['detail'])[:100]}", file=out)
        for wait in receipt.get("capacity_waits") or []:
            taken = wait.get("taken")
            secs = wait.get("seconds")
            head = (f"waited {secs:.1f}s" if taken and secs is not None
                    else "STOPPED WAITING" if taken is False else "waited")
            print(f"      · {head:18} {wait.get('source')}  {wait.get('detail') or ''}", file=out)
        _show_plan(receipt.get("batch_plan"), out)

    atoms = graph.get("semantic_atoms") or []
    coverage = graph.get("coverage") or []
    disposed = {c.get("source_unit_id") for c in coverage}
    lost = [u.get("source_unit_id") for u in units if u.get("source_unit_id") not in disposed]
    kinds: Dict[str, int] = {}
    for c in coverage:
        kinds[str(c.get("disposition"))] = kinds.get(str(c.get("disposition")), 0) + 1

    print(f"\ncoverage  {len(disposed)} of {len(units)} source unit(s) disposed of · "
          f"{len(atoms)} atom(s)", file=out)
    for disposition, count in sorted(kinds.items()):
        print(f"  {disposition:24} {count}", file=out)
    # LOST IS ITS OWN NUMBER. A unit nothing said anything about is not a remainder — a remainder is
    # a decision — and a transcript that folded them together would hide the only coverage failure
    # the audit can actually catch.
    print(f"  {'lost (no disposition)':24} {len(lost)}"
          f"{'  ' + ', '.join(lost) if lost else ''}", file=out)
    if waited_total:
        print(f"\nwaiting   {waited_total / 1000:.1f}s spent waiting for provider capacity",
              file=out)


def _show_scope(session, out) -> None:
    """What this run was ALLOWED to investigate. HARNESS-003F.

    Printed beside the deployment badge and above everything the run produced, for the reason the
    surface prints it there: a bounded run produces FEWER claims and observables, so a reader who
    meets the result before the bound reads a short transcript as a finding about the images.

    NOTHING AT ALL on a full-coverage run — an unbounded run has nothing to declare and a block
    saying so on every transcript would be noise that trains a reader to skip the one that matters.
    """
    record = (session.graph or {}).get("execution_scope") or {}
    mode = str(record.get("mode") or session.execution_scope or "full")
    if mode == "full":
        return
    print(f"\nscope     SCOPED LIVE REHEARSAL — this run investigated a declared subset. "
          f"It is not a complete reading.", file=out)
    if not record:
        print("          the run did not reach a compilation, so nothing recorded what it "
              "selected. It is still a slice.", file=out)
        return
    print(f"          full_coverage {record.get('full_coverage')} · purpose "
          f"{record.get('purpose')} · sized against {record.get('allowance_tokens')} tokens/min "
          f"by {record.get('selection_producer')}", file=out)
    sel, dfr = record.get("selected_source_unit_ids", []), record.get("deferred_source_unit_ids", [])
    atoms, atoms_out = record.get("selected_atom_ids", []), record.get("atoms_not_investigated", [])
    claims, claims_out = record.get("selected_claim_ids", []), record.get("claims_not_investigated", [])
    print(f"          units  {len(sel):3} selected, {len(dfr):3} deferred", file=out)
    print(f"          atoms  {len(atoms) - len(atoms_out):3} investigated of {len(atoms):3}",
          file=out)
    print(f"          claims {len(claims) - len(claims_out):3} investigated of {len(claims):3}",
          file=out)
    for label, sent, allowed in (
            ("relation requests   ", record.get("relation_batches_sent"),
             record.get("relation_batches_allowed")),
            ("operationalization  ", record.get("operationalizer_batches_sent"),
             record.get("operationalizer_batches_allowed")),
            ("cross-batch rounds  ", record.get("reconciliation_rounds_sent"),
             record.get("reconciliation_rounds_allowed"))):
        cap = "no limit" if allowed is None else f"{allowed} permitted"
        print(f"          {label} {sent} sent, {cap}", file=out)
    # IN FULL. A count is the size of the gap; this is where it is, and it is the half of the
    # record a person actually reads before concluding that nothing was there.
    exclusions = record.get("exclusions") or []
    print(f"          {len(exclusions)} thing(s) not investigated:", file=out)
    for entry in exclusions:
        print(f"            · {str(entry.get('kind')):14} {str(entry.get('ref')):22} "
              f"{str(entry.get('reason'))[:110]}", file=out)
    for note in (record.get("notes") or []):
        print(f"          note: {note}", file=out)


def show(session, request, args, *, stages=None) -> None:
    out = sys.stdout
    print(f"\nsession   {session.session_id}   {session.mode} mode", file=out)
    print(f"question  {session.prompt}", file=out)
    print(f"images    {', '.join(p.post_id for p in session.posts)}", file=out)

    # WHAT PRODUCED THIS, first and not in a receipt three panels down. A transcript of a replay is
    # indistinguishable from a transcript of a live run to anyone who does not go looking.
    if stages is not None:
        badge = runtime.deployment(stages)
        print(f"deployed  {badge['kind'].upper()}   {badge['detail']}", file=out)

    _show_scope(session, out)

    # TWO CLOCKS, SAID OUT LOUD. A stage's duration is the difference between the timestamps it was
    # handed; `wall` below is the process's monotonic clock. On a host that suspends mid-run they
    # disagree — this lane's live fold rehearsal reported a compiler stage of 6,181.6s inside a run
    # whose `wall` said 4,395.1s, and nothing in the transcript said the two numbers were measured
    # differently. A reader chasing that gap looks for a bug in the pacer.
    print("\nstages    (durations from the stamps the stage was handed — wall-clock, so a host "
          "that suspends is counted)", file=out)
    for event in session.stages:
        took = "" if event.duration_ms is None else f" {event.duration_ms / 1000:6.1f}s"
        print(f"  {event.stage.value:11} {event.outcome.value:12}{took}  {event.detail}", file=out)
        for sub in event.substages:
            sub_took = "" if sub.duration_ms is None else f" {sub.duration_ms / 1000:6.1f}s"
            print(f"     · {sub.label:52.52} {sub.outcome:11}{sub_took}", file=out)

    _show_council(session, out)

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
    parser.add_argument("--post", action="append", default=[],
                        help="live only: a real post id, resolved through the archive so the run "
                             "carries the repository's own fingerprints")
    parser.add_argument("--scope", default="full", choices=["full", "vertical_slice"],
                        help="HARNESS-003F: the declared execution scope. `vertical_slice` also "
                             "needs SEMANT_INQUIRY_SCOPED_REHEARSAL_ENABLED=1")
    parser.add_argument("--answer", type=int, default=1, help="which option to choose (1-based)")
    parser.add_argument("--reject", action="store_true", help="decline every option")
    parser.add_argument("--redirect", default="", help="answer in your own words instead")
    parser.add_argument("--live", action="store_true", help="reach the real models")
    parser.add_argument("--replay-check", action="store_true")
    parser.add_argument("--json", action="store_true", help="the wire body, as the routes serve it")
    parser.add_argument("--json-out", default="",
                        help="also write the wire body here, keeping the transcript on stdout")
    args = parser.parse_args()

    if args.live and not (args.image or args.post):
        parser.error("--live needs at least one --image URL or --post id")
    if args.replay_check:
        return replay_check(args)

    stages = build(args)
    # BEFORE AND AFTER, over the archive rather than over the session's own copy. The session's
    # refs were read at the start; re-reading the documents is what makes this a comparison against
    # the world instead of against a number the run is carrying around with it.
    before = fingerprints(posts_for(args)) if args.live else {}
    began = time.monotonic()
    session, request = drive(args, stages)
    elapsed = time.monotonic() - began
    after = fingerprints(session.posts) if args.live else {}

    # BOTH, WHEN ASKED FOR BOTH. `--json` REPLACED the transcript, which meant a live rehearsal that
    # wanted the readable account and the canonical record had to be run twice — and at an 8000 TPM
    # allowance a second run of a four-image inquiry is half an hour of waiting to produce bytes the
    # first run already held. HARNESS-003E, and it cost this lane the fold run's own record to
    # notice.
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(view.session_view(
            session, servable_classes=coordinator.servable_classes(stages),
            deployment=runtime.deployment(stages)), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"canonical session written to {args.json_out}", file=sys.stderr)

    if args.json:
        # The SAME body the route serves, deployment badge included. A rehearsal transcript that
        # omitted it would be a session record that cannot say what produced it.
        json.dump(view.session_view(
            session, servable_classes=coordinator.servable_classes(stages),
            deployment=runtime.deployment(stages)),
            sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        show(session, request, args, stages=stages)
        print(f"wall      {elapsed:.1f}s end to end, on the process's MONOTONIC clock — which does "
              f"not tick while the host is suspended, so a stage duration above it is not a "
              f"contradiction", file=sys.stdout)
        if before or after:
            moved = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            print(f"\nposts     {len(before)} fingerprinted before, {len(after)} after — "
                  f"{'NOTHING MOVED' if not moved else f'{len(moved)} CHANGED: {moved}'}",
                  file=sys.stdout)
            for post_id in sorted(before):
                print(f"            {post_id}  {before[post_id]}", file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
