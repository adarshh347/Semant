#!/usr/bin/env python3
"""
HARNESS-003A §8 — dissolve a question and a reading, and look at what became of every paragraph.

    python scripts/semantic_dissolve.py                              # the rehearsal fixture
    python scripts/semantic_dissolve.py --fixture unrelated-weave    # the control
    python scripts/semantic_dissolve.py --coverage                   # the ledger, unit by unit
    python scripts/semantic_dissolve.py --replay-check               # prove a replay is identical
    python scripts/semantic_dissolve.py --json > graph.json

    python scripts/semantic_dissolve.py --live --prompt "…" --image URL --image URL

WHAT THIS IS FOR. The 002R rehearsal could not answer "what happened to that paragraph". This
prints the answer: one row per source unit, what it said, and whether it was represented, a
duplicate, remainder or refused — plus every pass's model, call count, finish reason and duration.

READ-ONLY. This script imports the compilation package and two JSON contracts. It constructs no
Mongo client and reads no post. `--live` takes image URLs on the command line for the same reason
`semantic_compile.py` does: resolving a post id means opening the database this script promises not
to touch.

WHAT YOU ARE LOOKING AT. Nothing in the output is a finding. Every atom is at most a reading of
what a source unit says, every claim is at most `interpretive`, and every observable is a REQUEST
for a capability class with nothing behind it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.schemas.semantic_compilation import (PassOutcome,  # noqa: E402
                                                  SemanticInquiryGraph, canonical)
from backend.services import role_registry  # noqa: E402
from backend.services.inquiry import frame_prompt  # noqa: E402
from backend.services.semantic_compilation import dissolution, to_image_refs  # noqa: E402
from backend.services.semantic_compilation.base import CompilationRequest  # noqa: E402
from backend.services.semantic_compilation.theorist import ModelSceneTheorist  # noqa: E402
from backend.tests.fixtures import semantic_dissolution_fixtures as fixtures  # noqa: E402

ROLES = ("scene_theorist", "semantic_dissector", "relation_architect",
         "epistemic_operationalizer")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _image_spec(spec: str, index: int) -> Dict[str, str]:
    url, _, title = spec.partition("|")
    return {"post_id": f"img_{index}", "title": title.strip(), "image_ref": url.strip()}


# ── live ─────────────────────────────────────────────────────────────────────

def run_live(prompt: str, image_specs: List[str], *, max_images: int) -> SemanticInquiryGraph:
    """Prompt + image urls → a real reading → a real dissolution. Four roles, four receipts."""
    images = to_image_refs([_image_spec(spec, i) for i, spec in enumerate(image_specs)])
    corpus = {"post_ids": [i.post_id for i in images],
              "titles": [i.title for i in images if i.title]}
    frame = frame_prompt(prompt, corpus)

    for role in ROLES:
        print(f"{role:26} {role_registry.model_for(role)}", file=sys.stderr)

    theorist = ModelSceneTheorist(max_images=max_images)
    print(f"\nreading {len(images)} image(s)…", file=sys.stderr)
    result = theorist.read(prompt, images, inquiry_id=frame.inquiry_id, corpus=corpus, now=_now())
    receipt = result.reading.provenance
    print(f"  {receipt.call_topology.value} · {receipt.call_count} call(s) · "
          f"{len(result.reading.blocks)} block(s) · finish_reason="
          f"{receipt.finish_reason or 'not reported'}", file=sys.stderr)

    print("dissolving…", file=sys.stderr)
    return dissolution.dissolve(
        CompilationRequest(prompt=prompt, inquiry_id=frame.inquiry_id,
                           inquiry_frame=frame.model_dump(mode="json"), reading=result.reading,
                           images=tuple(images), corpus=corpus, now=_now(),
                           inherited_refusals=result.refusals, inherited_notes=result.notes),
        dissolution.live_council())


# ── printing ─────────────────────────────────────────────────────────────────

def show(graph: SemanticInquiryGraph) -> None:
    out = sys.stdout
    print(f"\nprompt    {graph.prompt}", file=out)
    print(f"schema    {graph.schema_version}   graph {graph.graph_id}", file=out)

    print(f"\npasses", file=out)
    for p in graph.passes:
        bits = [f"{p.call_count} call(s)"]
        if p.finish_reasons:
            bits.append("finish=" + ",".join(p.finish_reasons))
        if p.duration_ms is not None:
            bits.append(f"{p.duration_ms:.0f} ms")
        if p.completion_tokens is not None:
            bits.append(f"{p.completion_tokens} out-tok")
        mark = " " if p.outcome is PassOutcome.COMPLETED else "!"
        print(f" {mark} {p.pass_name.value:28} {p.outcome.value:16} {' · '.join(bits)}", file=out)
        print(f"     {p.detail}", file=out)

    print(f"\nledger    {len(graph.source_units)} source unit(s) · "
          f"{len(graph.semantic_atoms)} atom(s) · {len(graph.claims)} claim(s) · "
          f"{len(graph.claim_edges)} relation(s) · {len(graph.observables)} observable(s) · "
          f"{len(graph.decision_candidates)} fork(s) · {len(graph.semantic_remainder)} remainder",
          file=out)

    kinds: Dict[str, int] = {}
    for atom in graph.semantic_atoms:
        kinds[atom.unit_kind.value] = kinds.get(atom.unit_kind.value, 0) + 1
    print("atoms     " + " · ".join(f"{k} {n}" for k, n in sorted(kinds.items())), file=out)
    users = [a for a in graph.semantic_atoms if a.author.value == "user"]
    print(f"          {len(users)} attributed to the person, "
          f"{len(graph.semantic_atoms) - len(users)} to the dissector", file=out)

    if graph.observables:
        print("\nobservables", file=out)
        for o in graph.observables:
            print(f"  {o.observable_kind:44} "
                  f"{', '.join(c.value for c in o.capability_classes)}", file=out)
            if o.remains_interpretive:
                print(f"     still a reading: {o.remains_interpretive}", file=out)

    for d in graph.decision_candidates:
        print(f"\nfork      {d.question}", file=out)
        print(f"          why now: {d.why_now}", file=out)
        for option in d.options:
            print(f"        {'*' if option.recommended else ' '} {option.label}", file=out)

    if graph.semantic_remainder:
        print("\nremainder", file=out)
        for r in graph.semantic_remainder:
            print(f"  {r.term} — {r.why}", file=out)

    if graph.refusals:
        print(f"\nrefusals  {len(graph.refusals)}", file=out)
        for r in graph.refusals[:12]:
            print(f"  {r.kind.value:32} {r.what[:60]}", file=out)

    print(f"\n{graph.notes[-1] if graph.notes else '(no notes)'}", file=out)


def show_coverage(graph: SemanticInquiryGraph) -> None:
    """One row per source unit. The question 002R could not answer."""
    print(f"\n{'author':15} {'disposition':16} {'atoms':>5}  source unit", file=sys.stdout)
    for row in dissolution.coverage_table(graph):
        print(f"{row['author']:15} {row['disposition']:16} {len(row['atoms']):>5}  "
              f"{row['quote'][:78]}", file=sys.stdout)
        for atom in row["atoms"]:
            print(f"{'':38}└ [{atom['unit_kind']:19}] {atom['text'][:60]}", file=sys.stdout)
        if row["disposition"] != "represented_by" and row["reason"]:
            print(f"{'':38}  {row['reason'][:80]}", file=sys.stdout)


def replay_check(name: str) -> int:
    first = fixtures.dissolve_fixture(name)
    second = fixtures.dissolve_fixture(name)
    if canonical(first) == canonical(second):
        # LIVE means a provider answered. A replayed pass still increments its own call counter —
        # that is the pass's accounting, not a network fact — so counting `call_count` here would
        # report four live calls for a run that made none.
        live = sum(p.call_count for p in first.passes if p.provider)
        replayed = sum(p.call_count for p in first.passes if not p.provider)
        print(f"REPLAY IDENTICAL — {name} · {len(json.dumps(canonical(first)))} bytes compared · "
              f"{live} live call(s), {replayed} replayed")
        return 0
    print(f"REPLAY DIFFERED — {name}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixture", default=fixtures.FIXTURES[0], choices=list(fixtures.FIXTURES))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--image", action="append", default=[],
                        help="live only: an image URL, optionally 'URL|title'")
    parser.add_argument("--max-images", type=int, default=6)
    parser.add_argument("--replay-check", action="store_true")
    parser.add_argument("--coverage", action="store_true", help="the ledger, unit by unit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.replay_check:
        return replay_check(args.fixture)
    if args.live:
        if not args.image:
            parser.error("--live needs at least one --image URL")
        if not args.prompt:
            parser.error("--live needs a --prompt")
        graph = run_live(args.prompt, args.image, max_images=args.max_images)
    else:
        graph = fixtures.dissolve_fixture(args.fixture)

    if args.json:
        json.dump(graph.model_dump(mode="json", by_alias=True), sys.stdout, indent=2,
                  ensure_ascii=False)
        print()
        return 0
    show(graph)
    if args.coverage:
        show_coverage(graph)
    return 0 if graph.passes and graph.passes[-1].outcome is PassOutcome.COMPLETED else 3


if __name__ == "__main__":
    raise SystemExit(main())
