#!/usr/bin/env python3
"""
HARNESS-002A §7 — compile a question and a reading into a graph, locally, and look at the result.

    python scripts/semantic_compile.py --fixture cross-image-comparison
    python scripts/semantic_compile.py --fixture unrelated-domain --json > graph.json
    python scripts/semantic_compile.py --fixture cross-image-comparison --replay-check
    python scripts/semantic_compile.py --prompt "…" --image URL --image URL --live

READ-ONLY, and the guarantee is structural rather than promised. This script imports
`backend.services.semantic_compilation`, which imports two JSON contracts and pydantic. It does not
import the database, constructs no Mongo client, and reads no post. Images are supplied as URLs on
the command line, so there is no path from here to the corpus at all — which is also why `--live`
does not take post ids: resolving one would mean opening the database this script promises not to.

`--live` is the only flag that reaches a network. Without it nothing does. If the role's model is
unavailable, live mode SAYS SO and returns an empty reading or an empty graph; it never falls back
to a fixture while claiming to be live.

WHY THIS IMPORTS FROM `backend/tests/fixtures/`. The frozen model outputs live on the test side
because no production source may contain a fixture's topic nouns — see
`test_semantic_compilation_generality.py`. The loader they share names no topic itself.

WHAT YOU ARE LOOKING AT. Nothing in the output is a finding. Every claim is at most `interpretive`,
every observable is a REQUEST for a capability class with nothing behind it yet, and the two lists
at the bottom are the honest ones — what a person would have to decide, and what measurement will
not exhaust even if all of it succeeds.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.schemas.semantic_compilation import (CallTopology, SemanticInquiryGraph,  # noqa: E402
                                                  canonical)
from backend.services import role_registry  # noqa: E402
from backend.services.inquiry import frame_prompt  # noqa: E402
from backend.services.semantic_compilation import to_image_refs  # noqa: E402
from backend.services.semantic_compilation.base import CompilationRequest  # noqa: E402
from backend.services.semantic_compilation.compiler import ModelSemanticCompiler  # noqa: E402
from backend.services.semantic_compilation.theorist import ModelSceneTheorist  # noqa: E402
from backend.tests.fixtures import semantic_compilation_fixtures as fixtures  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── live ─────────────────────────────────────────────────────────────────────

def run_live(prompt: str, image_specs: List[str], *, max_images: int) -> SemanticInquiryGraph:
    """Prompt + image urls → a real reading → a real compilation. Two roles, two receipts.

    The frame is produced by Lane A's DETERMINISTIC framer, not a model: it is the prompt-only
    half of the input and this script does not need a third live call to demonstrate the seam.
    """
    images = to_image_refs([_image_spec(spec, index) for index, spec in enumerate(image_specs)])
    corpus = {"post_ids": [i.post_id for i in images],
              "titles": [i.title for i in images if i.title]}
    frame = frame_prompt(prompt, corpus)

    theorist = ModelSceneTheorist(max_images=max_images)
    print(f"scene_theorist   role model: {role_registry.model_for('scene_theorist')} · "
          f"{'available' if theorist.is_available() else 'UNAVAILABLE'}", file=sys.stderr)
    result = theorist.read(prompt, images, inquiry_id=frame.inquiry_id, corpus=corpus, now=_now())
    print(f"                 topology: {result.reading.provenance.call_topology.value} · "
          f"{result.reading.provenance.call_count} call(s)", file=sys.stderr)

    compiler = ModelSemanticCompiler()
    print(f"semantic_compiler role model: {role_registry.model_for('semantic_compiler')} · "
          f"{'available' if compiler.is_available() else 'UNAVAILABLE'}", file=sys.stderr)
    return compiler.compile(CompilationRequest(
        prompt=prompt, inquiry_id=frame.inquiry_id, inquiry_frame=frame.model_dump(mode="json"),
        reading=result.reading, images=tuple(images), corpus=corpus, now=_now(),
        inherited_refusals=result.refusals, inherited_notes=result.notes))


def _image_spec(spec: str, index: int) -> Dict[str, Any]:
    """`URL` or `URL|title` or `post_id|title|URL`. A url is required; there is nothing to read
    without one, and this script will not go looking for one in a database."""
    parts = [p.strip() for p in str(spec).split("|")]
    if len(parts) >= 3:
        return {"post_id": parts[0], "title": parts[1], "image_ref": parts[2]}
    if len(parts) == 2:
        return {"post_id": f"img_{index}", "title": parts[1], "image_ref": parts[0]}
    return {"post_id": f"img_{index}", "title": "", "image_ref": parts[0]}


# ── rendering ────────────────────────────────────────────────────────────────

def render(graph: SemanticInquiryGraph) -> str:
    out: List[str] = ["─" * 78, f"PROMPT (unchanged)\n  {graph.prompt}", ""]
    out.append(f"{graph.graph_id} · inquiry {graph.inquiry_id} · "
               f"{len(graph.image_refs)} image(s)")
    out.append(f"compiled by {graph.provenance.producer} ({graph.provenance.compiler_kind})")

    for label, receipt in (("reading ", graph.provenance.theorist),
                           ("compile ", graph.provenance.compiler)):
        if receipt is None:
            out.append(f"{label} — none")
            continue
        state = "parsed" if receipt.parsed else f"UNAVAILABLE: {receipt.refusal or 'no reason'}"
        out.append(f"{label} {receipt.role} · {receipt.model or '— no model'} · "
                   f"{receipt.call_topology.value} · {receipt.call_count} call(s) · {state}")

    reading = graph.reading
    out.append("")
    out.append("READING — a vision model's provisional reading. INTERPRETIVE, never evidence.")
    if reading and reading.text:
        for line in _wrap(reading.text):
            out.append(f"  {line}")
    if reading and reading.blocks:
        out.append("")
        for block in reading.blocks:
            where = f" [{', '.join(block.image_refs)}]" if block.image_refs else ""
            out.append(f"  {block.kind.value:22} {block.text}{where}")
    if not reading or (not reading.text and not reading.blocks):
        out.append("  — nothing was read, and nothing was invented in its place")

    out.append("")
    out.append("CLAIMS — atomic, typed, anchored. Nothing here has been established.")
    for claim in graph.claims:
        out.append(f"  {claim.claim_kind.value:22} {claim.epistemic_demand.value:12} "
                   f"{claim.status.value:12} {claim.text}")
        anchors = ", ".join(f"{s.source_type.value}:{s.source_id}" for s in claim.sources)
        out.append(f"      ← {anchors}"
                   + (f"  (from {', '.join(claim.inferred_from)})" if claim.inferred_from else ""))
    if not graph.claims:
        out.append("  — none")

    if graph.claim_edges:
        out.append("")
        out.append("RELATIONS")
        for edge in graph.claim_edges:
            out.append(f"  {edge.from_claim} —{edge.kind.value}→ {edge.to_claim}"
                       + (f"   {edge.why}" if edge.why else ""))

    out.append("")
    out.append("OBSERVABLES — what would have to be produced. A capability CLASS, never a tool.")
    for observable in graph.observables:
        out.append(f"  {observable.observable_id} → {observable.claim_id}   "
                   f"{observable.observable_kind}")
        out.append(f"      needs {', '.join(c.value for c in observable.capability_classes)}"
                   f"  as {', '.join(g.value for g in observable.ground_forms) or '— unstated'}"
                   f"  over {observable.image_scope.value}")
        if observable.remains_interpretive:
            out.append(f"      still a reading afterwards: {observable.remains_interpretive}")
        for alternative in observable.alternatives:
            mark = "★" if alternative.recommended else "·"
            out.append(f"      {mark} {alternative.label}"
                       + (f" — {alternative.consequence}" if alternative.consequence else ""))
    if not graph.observables:
        out.append("  — none requested")

    out.append("")
    out.append("DECISIONS A PERSON WOULD CHANGE THE INQUIRY BY ANSWERING")
    for decision in graph.decision_candidates:
        out.append(f"  [{decision.kind.value}] {decision.question}")
        out.append(f"      why now: {decision.why_now}")
        out.append(f"      affects: {', '.join(decision.affected_refs) or '—'}")
        for option in decision.options:
            out.append(f"      {'★' if option.recommended else '·'} {option.label}"
                       + (f" — {option.consequence}" if option.consequence else ""))
    if not graph.decision_candidates:
        out.append("  — none. Uncertainty alone is not a reason to interrupt somebody.")

    out.append("")
    out.append("SEMANTIC REMAINDER — meaning the requested measurements will not exhaust.")
    for item in graph.semantic_remainder:
        contributing = ", ".join(c.value for c in item.contributing_capability_classes)
        out.append(f"  “{item.term}”" + (f"  (contributed to by: {contributing})"
                                         if contributing else "  (nothing contributes)"))
        for line in _wrap(item.why, 68):
            out.append(f"      {line}")
    if not graph.semantic_remainder:
        out.append("  — none")

    if graph.refusals:
        out.append("")
        out.append("REFUSED — produced, and not carried. Kept so it is not erased.")
        for r in graph.refusals:
            out.append(f"  [{r.kind.value}] {r.what}")
            for line in _wrap(r.why, 68):
                out.append(f"      {line}")

    if graph.notes:
        out.append("")
        out.append("NOTES")
        for note in graph.notes:
            for index, line in enumerate(_wrap(note, 72)):
                out.append(("  · " if index == 0 else "    ") + line)

    out.append("")
    out.append(graph.summary())
    out.append("─" * 78)
    return "\n".join(out)


def _wrap(text: str, width: int = 74) -> List[str]:
    words, lines, current = str(text or "").split(), [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


# ── entry ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compile a prompt and a visual reading into a semantic inquiry graph. "
                    "Reads no post, touches no database, writes nothing.")
    ap.add_argument("--fixture", choices=list(fixtures.FIXTURES),
                    help="replay a frozen model output. No network.")
    ap.add_argument("--prompt", help="a prompt to compile live (requires --live and --image)")
    ap.add_argument("--image", action="append", default=[], metavar="URL[|title[|…]]",
                    help="an image url. Repeatable. Urls only — this script does not read posts.")
    ap.add_argument("--live", action="store_true",
                    help="use the live scene theorist and semantic compiler. THE ONLY PATH THAT "
                         "REACHES A NETWORK; reports unavailable rather than substituting a "
                         "fixture.")
    ap.add_argument("--max-images", type=int, default=6,
                    help="bound on the per-image reading sweep")
    ap.add_argument("--replay-check", action="store_true",
                    help="compile a fixture twice and report whether the two are byte-identical")
    ap.add_argument("--json", action="store_true", help="print the graph as JSON")
    args = ap.parse_args()

    if args.replay_check:
        if not args.fixture:
            ap.error("--replay-check replays a fixture; give --fixture")
        first = fixtures.compile_fixture(args.fixture, now="2026-01-01T00:00:00+00:00")[1]
        second = fixtures.compile_fixture(args.fixture, now="2099-12-31T23:59:59+00:00")[1]
        identical = canonical(first) == canonical(second)
        print(f"{args.fixture}: two compilations, different clocks — "
              f"byte-identical under `canonical`: {identical}")
        print(f"  {first.summary()}")
        return 0 if identical else 1

    if args.live:
        if not args.prompt:
            ap.error("--live needs --prompt")
        if not args.image:
            ap.error("--live needs at least one --image URL. A scene reading needs a scene, and "
                     "this script will not look one up in a database.")
        graph = run_live(args.prompt, args.image, max_images=args.max_images)
    elif args.fixture:
        graph = fixtures.compile_fixture(args.fixture, now=_now())[1]
    else:
        ap.error("give --fixture NAME, or --live with --prompt and --image")
        return 2

    if args.json:
        print(json.dumps(graph.model_dump(mode="json", by_alias=True), indent=2,
                         ensure_ascii=False))
    else:
        print(render(graph))

    # An exit code a caller can branch on: the compiler not answering is not the same as the
    # compiler answering with nothing, and a script that returned 0 for both would hide it.
    receipt = graph.provenance.compiler
    if receipt is not None and receipt.call_topology is CallTopology.UNAVAILABLE:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
