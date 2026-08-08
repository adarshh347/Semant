#!/usr/bin/env python3
"""
HARNESS-001A — frame a prompt, locally, and look at the result.

    python scripts/inquiry_frame.py "segment every raised hand"
    python scripts/inquiry_frame.py --fold-prompt --corpus corpus.json
    python scripts/inquiry_frame.py "…" --json > frame.json
    python scripts/inquiry_frame.py "…" --model          # the ONLY networked path

READ-ONLY, and the guarantee is structural rather than promised: this script imports
`backend.services.inquiry`, which imports the two JSON contracts and pydantic. It does not import
the database, it constructs no Mongo client, and the deterministic framer it runs by default has
no client to construct. `--model` is the one flag that reaches a network, and without it nothing
does.

It writes nothing anywhere. No post changes, no collection is touched, no run is recorded.

WHAT YOU ARE LOOKING AT. A reading OF A QUESTION. Nothing in the output is a finding: every act
is `proposed`, every attention says "the user said", and the two lists at the bottom are the
honest ones — terms nothing can serve, and meaning the available measurements will not exhaust
even if all of them succeed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.schemas.inquiry import DemandKind, InquiryFrame, InquiryMode  # noqa: E402
from backend.services.inquiry import frame_prompt  # noqa: E402

#: The wave's acceptance rehearsal, kept here so the proof cannot be run on a paraphrase.
FOLD_PROMPT = (
    "Explore the fold-level aesthetic and style relations between Renaissance and Buddha "
    "sculptures, their common way of unfolding sensuality, where they drift apart, and what "
    "hybrid styles they could give birth to."
)

_KIND_LABEL = {
    DemandKind.MEASURABLE: "measurable   (an organ could, once one runs)",
    DemandKind.INTERPRETIVE: "interpretive (a reading about a picture)",
    DemandKind.SOURCED: "sourced      (from outside the picture)",
    DemandKind.IMAGINED: "imagined     (does not exist)",
    DemandKind.UNRESOLVED: "unresolved   (nothing operationalises it)",
}


def _load_corpus(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("corpus metadata must be a JSON object of ids/titles/counts")
    return data


def render(frame: InquiryFrame) -> str:
    out = []
    out.append("─" * 78)
    out.append(f"PROMPT (unchanged)\n  {frame.prompt}")
    out.append("")
    out.append(f"{frame.inquiry_id} · mode={frame.mode.value} · "
               f"requested output: {frame.requested_output or '— none stated'}")
    out.append(f"framed by {frame.provenance.producer} ({frame.provenance.framer_kind})"
               + (f" on {frame.provenance.model}" if frame.provenance.model else ""))
    out.append(f"grammar {frame.provenance.grammar_version} · "
               f"lexicon {frame.provenance.lexicon_version}")
    out.append("")
    out.append(f"CORPUS — ids, titles and counts only, and nothing seen: "
               f"{frame.corpus_context.count} image(s)")
    if frame.corpus_context.post_ids:
        out.append("  " + ", ".join(frame.corpus_context.post_ids))

    out.append("")
    out.append("ATTENTIONS — what the prompt was keyed on. Never what anything saw.")
    for a in frame.attentions or []:
        roles = f"  → {', '.join(a.action_roles)}" if a.action_roles else ""
        out.append(f"  [{a.category}] {a.said}{roles}")
    if not frame.attentions:
        out.append("  — none")

    out.append("")
    out.append("EPISTEMIC DEMANDS — what KIND of knowing each clause asks for.")
    for kind in DemandKind:
        rows = frame.demands_of(kind)
        if not rows:
            continue
        out.append(f"  {_KIND_LABEL[kind]}")
        for d in rows:
            out.append(f"      “{d.term}” in: {d.clause}")

    out.append("")
    out.append("PROPOSED ACTS — grammar-valid, every one of them proposed. Nothing ran.")
    for a in frame.proposed_actions or []:
        out.append(f"  {a['status']:9} {a['type']:18} {a['label']}")
        reason = (a.get("payload") or {}).get("reason")
        if reason:
            out.append(f"            {reason}")
        # The action's own warnings, verbatim — the way a proposal admits its weakness rather
        # than having one phrase guessed for it here.
        for warning in a.get("warnings") or []:
            out.append(f"            ⚠ {warning}")
    if not frame.proposed_actions:
        out.append("  — none. Nothing in the grammar serves this prompt.")

    out.append("")
    out.append("UNRESOLVED — terms nothing available can operationalise.")
    for u in frame.unresolved_terms or []:
        out.append(f"  “{u.term}” — {u.why}")
    if not frame.unresolved_terms:
        out.append("  — none")

    out.append("")
    out.append("SEMANTIC REMAINDER — meaning the measurements will not exhaust.")
    for r in frame.semantic_remainder or []:
        contributing = (f" (contributed to by: {', '.join(r.contributing_measurements)})"
                        if r.contributing_measurements else "")
        out.append(f"  “{r.term}”{contributing}")
        out.append(f"      {r.why}")
    if not frame.semantic_remainder:
        out.append("  — none")

    if frame.refusals:
        out.append("")
        out.append("REFUSED — produced, and not carried. Kept so it is not erased.")
        for r in frame.refusals:
            out.append(f"  [{r.kind.value}] {r.what} — {r.why}")
            for d in r.detail:
                out.append(f"      {d}")

    if frame.notes:
        out.append("")
        out.append("NOTES")
        for n in frame.notes:
            out.append(f"  · {n}")

    out.append("")
    out.append(frame.summary())
    out.append("─" * 78)
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Frame a prompt as an inquiry. Reads words; sees no images; writes nothing.")
    ap.add_argument("prompt", nargs="?", help="the prompt to frame")
    ap.add_argument("--fold-prompt", action="store_true",
                    help="use the wave's acceptance prompt verbatim")
    ap.add_argument("--corpus", help="path to a JSON object of corpus metadata "
                                     "(post_ids / titles / tags / count)")
    ap.add_argument("--mode", choices=[m.value for m in InquiryMode], default="explore")
    ap.add_argument("--model", action="store_true",
                    help="use the model-backed framer. THE ONLY PATH THAT REACHES A NETWORK; "
                         "falls back to the deterministic framer and says so if unavailable")
    ap.add_argument("--json", action="store_true", help="print the frame as JSON")
    args = ap.parse_args()

    prompt = FOLD_PROMPT if args.fold_prompt else args.prompt
    if not prompt:
        ap.error("give a prompt, or --fold-prompt")

    frame = frame_prompt(prompt, _load_corpus(args.corpus),
                         framer="model" if args.model else "deterministic",
                         mode=InquiryMode(args.mode))

    if args.json:
        print(json.dumps(frame.model_dump(mode="json"), indent=2, ensure_ascii=False))
    else:
        print(render(frame))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
