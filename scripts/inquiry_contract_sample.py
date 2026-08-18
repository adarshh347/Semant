#!/usr/bin/env python3
"""
HARNESS-002D §7 — generate the canonical session responses the frontend is reconciled against.

    python scripts/inquiry_contract_sample.py            # rewrite the checked-in samples
    python scripts/inquiry_contract_sample.py --check    # fail if they have drifted

THE POINT IS THE DIRECTION. Lane C wrote its client against a contract nobody had produced yet, and
Lane D produces it. These files are the BACKEND's output, byte for byte, and the frontend's parity
test reads them — so a field the backend renames breaks a frontend test, which is the only
arrangement in which the two cannot drift apart quietly.

They are checked in, and a backend test regenerates and compares. A sample that could be edited by
hand would be a third opinion about the wire shape.

READ-ONLY AND OFFLINE. Frozen model payloads, a frozen clock, a fixed session id. No network, no
database, no post is read. Every id in the output is content-derived, so running this twice
produces identical bytes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contracts" / "samples"

AT = "2026-08-09T00:00:00+00:00"
#: Fixed rather than minted: the session id is the one clock-derived value in the lane, and a
#: sample whose id changed every run would make the diff useless.
SESSION_IDS = {"awaiting-user": "inqs_sample000001", "complete": "inqs_sample000002",
               "auto-complete": "inqs_sample000003", "dissolution": "inqs_sample000004",
               "scoped": "inqs_sample000005"}


def _build():
    from backend.services.inquiry_session import coordinator, runtime, view
    from backend.services.semantic_compilation import scope as scope_mod
    from backend.services.semantic_compilation import sizing
    from backend.services.inquiry_session.capability import LockedFixtureCapability
    from backend.services.inquiry_session.composer import DeterministicComposer
    from backend.services.inquiry_session.judge import judge
    from backend.tests.fixtures import inquiry_session_fixtures as F

    name = F.FIXTURES[0]

    def stages():
        return F.stages_for(name, capability=LockedFixtureCapability(), judge=judge,
                            composer=DeterministicComposer(), clock=F.frozen_clock(AT))

    def fresh(session_id, mode):
        return coordinator.new_session(prompt=F.prompt_for(name), refs=F.post_refs(name),
                                       mode=mode, session_id=session_id, now=AT)

    servable = tuple(LockedFixtureCapability().servable_classes)
    # THE SAMPLES ARE A REPLAY AND THEY SAY SO. Derived from the same bound stages the run
    # used rather than hardcoded: a sample that asserted its own deployment kind would be the
    # one place in the contract where the badge is a claim instead of a reading.
    deployed = runtime.deployment(stages())
    out = {}

    paused = coordinator.begin(fresh(SESSION_IDS["awaiting-user"], "consult"), stages())
    out["awaiting-user"] = view.session_view(paused, servable_classes=servable, deployment=deployed)

    request = coordinator.machine.from_dict(paused.interaction).open_decision
    answered = coordinator.resume(paused, {
        "response_id": "resp_sample", "session_id": paused.session_id,
        "decision_id": request.decision_id, "expected_revision": paused.revision,
        "kind": "select_option", "option_id": request.options[0].option_id, "at": AT}, stages())
    out["complete"] = view.session_view(answered, servable_classes=servable, deployment=deployed)

    auto = coordinator.begin(fresh(SESSION_IDS["auto-complete"], "auto"), stages())
    out["auto-complete"] = view.session_view(auto, servable_classes=servable, deployment=deployed)

    # ── the v2 sample (HARNESS-003D) ──────────────────────────────────────────
    #
    # The three above are v1 graphs, and every dissolution field on them is legitimately empty. A
    # parity suite reading only those would prove that the client tolerates the ABSENCE of source
    # units, atoms, coverage and pass receipts, which is exactly the assurance Lane C already had
    # and exactly what stopped anybody noticing the backend was not sending them.
    #
    # So this one is the council, driven by the coordinator, over a frozen four-image reading —
    # the shape the live rehearsal runs. It is the sample the consumed-field parity test reads.
    council = F.DISSOLUTION_FIXTURES[0]

    def council_stages():
        return F.dissolution_stages_for(council, capability=LockedFixtureCapability(), judge=judge,
                                        composer=DeterministicComposer(),
                                        clock=F.frozen_clock(AT))

    dissolved = coordinator.begin(
        coordinator.new_session(prompt=F.dissolution_prompt_for(council),
                                refs=F.dissolution_post_refs(council), mode="auto",
                                session_id=SESSION_IDS["dissolution"], now=AT),
        council_stages())
    out["dissolution"] = view.session_view(dissolved, servable_classes=servable,
                                           deployment=runtime.deployment(council_stages()))

    # ── the scoped sample (HARNESS-003F) ──────────────────────────────────────
    #
    # The four above are full-coverage runs, so every scope field on them is legitimately the
    # unbounded answer. A parity suite reading only those would prove that the client tolerates an
    # UNBOUNDED scope — which is the same shape of assurance that let the backend stop sending
    # source units without anybody noticing. So this one is a declared vertical slice that actually
    # bites: fewer relation requests than the partition needs, and a coverage matrix nobody reached.
    #
    # THE NUMBERS ARE DECLARED HERE rather than inherited from the box. A sample whose scope
    # depended on an environment variable would differ between two machines and the drift check
    # would fail for a reason that has nothing to do with the contract. The bounds are this lane's
    # own defaults; the allowance is chosen as the one at which this fixture exercises ALL THREE
    # kinds of exclusion at once — deferred source units, atoms no relation request reached, and a
    # claim nothing was asked about — while still building a claim. A sample where only one kind
    # appeared would let a client that mishandled the other two pass.
    scoped_env = {
        scope_mod.ENABLED_ENV: "1",
        sizing.ALLOWANCE_ENV: "4500",
        scope_mod.MAX_RELATION_BATCHES_ENV: str(scope_mod.DEFAULT_MAX_RELATION_BATCHES),
        scope_mod.MAX_OPERATIONALIZER_BATCHES_ENV: str(
            scope_mod.DEFAULT_MAX_OPERATIONALIZER_BATCHES),
        scope_mod.MAX_RECONCILIATION_ROUNDS_ENV: str(
            scope_mod.DEFAULT_MAX_RECONCILIATION_ROUNDS),
    }
    restore = {k: os.environ.get(k) for k in scoped_env}
    os.environ.update(scoped_env)
    try:
        scoped = coordinator.begin(
            coordinator.new_session(prompt=F.dissolution_prompt_for(council),
                                    refs=F.dissolution_post_refs(council), mode="auto",
                                    session_id=SESSION_IDS["scoped"], now=AT,
                                    execution_scope="vertical_slice"),
            council_stages())
        out["scoped"] = view.session_view(scoped, servable_classes=servable,
                                          deployment=runtime.deployment(council_stages()))
    finally:
        for key, value in restore.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return out


#: The one field a frozen clock cannot make deterministic: it is measured with `perf_counter`
#: around the adapter call. Pinned to a fixed number rather than removed, so the sample still shows
#: the field the workbench renders and the parity test still exercises its normaliser.
PINNED_LATENCY_MS = 0.0


def _pin_latency(value):
    if isinstance(value, dict):
        return {k: (PINNED_LATENCY_MS if k == "latency_ms" and isinstance(v, (int, float))
                    else _pin_latency(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_pin_latency(v) for v in value]
    return value


def render(payload) -> str:
    return json.dumps(_pin_latency(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def samples():
    return {f"inquiry-session.{key}.json": render(body) for key, body in _build().items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if the checked-in samples differ from a fresh build")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    drifted = []
    for filename, body in samples().items():
        path = OUT / filename
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current == body:
            continue
        drifted.append(filename)
        if not args.check:
            path.write_text(body, encoding="utf-8")

    if args.check and drifted:
        print("the checked-in contract samples have drifted from the backend:", file=sys.stderr)
        for name in drifted:
            print(f"  contracts/samples/{name}", file=sys.stderr)
        print("run `python scripts/inquiry_contract_sample.py` and commit the result.",
              file=sys.stderr)
        return 1
    print(f"{'checked' if args.check else 'wrote'} {len(samples())} sample(s) in {OUT}"
          + (f"; updated {', '.join(drifted)}" if drifted and not args.check else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
