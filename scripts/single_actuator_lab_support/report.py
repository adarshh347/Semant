"""`review.md` and `compare` — the two documents a human actually reads.

The review sheet exists to be FILLED IN. Its judgement slots are empty and marked `pending`,
because the alternative — pre-filling them from the automated signals and inviting a reviewer to
correct what looks already decided — is how a confidence score becomes a correctness claim by
social pressure rather than by anyone deciding it should.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

DEFAULT_QUESTIONS = (
    "Did the mask land on the thing the phrase named? (correct / partial / misbound / ambiguous / absent)",
    "Were ALL visible instances found, or only some?",
    "Is the boundary clean, loose, or simply wrong?",
    "If the result was empty: is the concept truly absent, or was it missed?",
)


def _fmt(value: Any, dash: str = "—") -> str:
    if value is None:
        return dash
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_fmt(v) for v in value) if value else dash
    return str(value)


def render_review(trace: Dict[str, Any], score: Dict[str, Any], manifest: Dict[str, Any],
                  out_path: str) -> str:
    """The manual-review sheet for one run."""
    organ = trace.get("organ_observation") or {}
    decision = trace.get("decision_receipt") or {}
    prompt = trace.get("prompt_receipt") or {}
    env = trace.get("environment") or {}
    measured = score["measured"]
    verdict = score["verdict"]
    artifacts = trace.get("artifacts") or {}
    questions = list((manifest.get("review") or {}).get("questions") or DEFAULT_QUESTIONS)

    lines: List[str] = []
    lines.append(f"# Review — `{trace['run_id']}`")
    lines.append("")
    lines.append(f"*{manifest.get('title') or trace['lab_id']} · mode `{trace['mode']}` · "
                 f"locked to `{trace['actuator_lock']}` · expected `{score['expected_condition']}`*")
    if manifest.get("why"):
        lines.append("")
        lines.append(f"> {manifest['why']}")
    lines.append("")

    lines.append("## What was asked")
    lines.append("")
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append(f"| prompt | {_fmt(prompt.get('original_prompt'))} |")
    lines.append(f"| control phrase | `{_fmt(prompt.get('control_phrase'))}` |")
    lines.append(f"| phrase actually used | `{_fmt(decision.get('selected_phrase'))}` |")
    lines.append(f"| phrase source | {_fmt(decision.get('phrase_source'))} |")
    lines.append(f"| planner | {_fmt(prompt.get('planner_model'))} "
                 f"({_fmt(prompt.get('planner_status'))}) |")
    lines.append(f"| image | `{manifest['image']['path']}` |")
    lines.append("")

    refused = decision.get("refused_actions") or []
    if refused:
        lines.append("### Refused, and recorded rather than filtered")
        lines.append("")
        for r in refused:
            lines.append(f"- `{_fmt(r.get('actuator'))}` → **{r.get('reason')}** — "
                         f"{r.get('detail') or ''}")
        lines.append("")
    dropped = decision.get("dropped_params") or []
    if dropped:
        lines.append("### Parameters dropped")
        lines.append("")
        for d in dropped:
            lines.append(f"- `{d.get('actuator')}`: {', '.join(d.get('keys') or [])}")
        lines.append("")

    lines.append("## What the harness measured")
    lines.append("")
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append(f"| availability | {measured['availability']} |")
    lines.append(f"| device / model | {_fmt(env.get('device'))} / {_fmt(env.get('checkpoint'))} |")
    lines.append(f"| invocations | {measured['invocation_count']} of budget "
                 f"{measured['call_budget']} |")
    lines.append(f"| lock held | {_fmt(measured['lock_held'])} |")
    lines.append(f"| cold / warm | {_fmt(measured['cold_or_warm'])} |")
    lines.append(f"| latency | {_fmt(measured['latency_ms'])} ms "
                 f"(load {_fmt(measured['load_ms'])} ms) |")
    lines.append(f"| organ status | **{_fmt(organ.get('status'))}** |")
    lines.append(f"| instances | {measured['instance_count']}"
                 f"{' (truncated)' if organ.get('truncated') else ''} |")
    lines.append(f"| mask areas (px) | {_fmt(measured['mask_area_px'])} |")
    lines.append(f"| max pairwise IoU | {_fmt(measured['max_pairwise_iou'])} |")
    lines.append(f"| all masks well-formed | {_fmt(measured['all_masks_well_formed'])} |")
    conv = measured.get("conversion_survival")
    if conv:
        lines.append(f"| conversion | {conv.get('instances')} instance(s) → "
                     f"{conv.get('measured_descriptors')} measured + "
                     f"{conv.get('interpretive_descriptors')} interpretive descriptor(s), "
                     f"{conv.get('naming_withheld')} naming withheld, "
                     f"{conv.get('dropped')} dropped |")
        lines.append(f"| two-status preserved | {_fmt(measured.get('two_status_preserved'))} |")
    lines.append(f"| invariants held | {_fmt(measured['invariants_held'])} |")
    if measured["violations"]:
        for v in measured["violations"]:
            lines.append(f"| **violation** | {v} |")
    lines.append("")

    lines.append("## Attribution")
    lines.append("")
    lines.append(f"**{verdict['attribution']}** — {verdict['attribution_detail']}")
    lines.append("")
    lines.append(f"Harness: **{verdict['harness']}**. "
                 f"Semantic correctness: **{verdict['semantic_correctness']}**.")
    lines.append("")
    lines.append("> Nothing above establishes that a mask is of the thing the words named. "
                 "A confidence, a plausible area and a well-formed RLE are all compatible with "
                 "a mask of the background — SF-004-R2 measured exactly that. That question is "
                 "settled below, by a person, or not at all.")
    lines.append("")

    if artifacts.get("overlay"):
        lines.append(f"![overlay]({os.path.basename(artifacts['overlay'])})")
        lines.append("")
    if artifacts.get("contact_sheet"):
        lines.append(f"![contact sheet]({os.path.basename(artifacts['contact_sheet'])})")
        lines.append("")

    lines.append("## Manual review — TO BE FILLED IN")
    lines.append("")
    lines.append(f"- protocol: **{score['review']['protocol']}**  ·  "
                 f"gold mask present: **{_fmt(score['review']['gold_mask_present'])}**  ·  "
                 f"status: **{score['review']['status']}**")
    lines.append("")
    for q in questions:
        lines.append(f"- [ ] {q}")
        lines.append("      > ")
    lines.append("")
    lines.append("```text")
    lines.append("concept_binding :          # correct | partial | misbound | ambiguous | absent")
    lines.append("coverage        :          # all_instances | some_instances | none | not_applicable")
    lines.append("boundary_quality:          # clean | loose | wrong")
    lines.append("false_positives :")
    lines.append("false_negatives :")
    lines.append("empty_means     :          # true_absence | missed_detection | undetermined")
    lines.append("reviewer        :")
    lines.append("reviewed_at     :")
    lines.append("notes           :")
    lines.append("```")
    lines.append("")
    lines.append("When filled in, copy these into `score.json` under `review`, set "
                 "`review.status` to `complete`, and set `verdict.semantic_correctness` to "
                 "`established_by_review` or `refuted_by_review`. The harness will never write "
                 "those fields itself.")
    lines.append("")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write("\n".join(lines))
    return out_path


# ── compare ───────────────────────────────────────────────────────────────────────────────────

def compare(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Read several runs against each other. Returns the comparison as data.

    It declares NO semantic correctness. Two runs agreeing on a phrase means the planner picked
    what a human would have picked; it does not mean either mask is right, and a compare step
    that concluded otherwise would launder agreement into truth.
    """
    rows: List[Dict[str, Any]] = []
    for entry in runs:
        trace, score = entry["trace"], entry["score"]
        organ = trace.get("organ_observation") or {}
        decision = trace.get("decision_receipt") or {}
        manifest = trace.get("manifest") or {}
        rows.append({
            "pair_with": manifest.get("pair_with"),
            "control_phrase": manifest.get("control_phrase"),
            "run_id": trace["run_id"],
            "mode": trace["mode"],
            "expected_condition": score["expected_condition"],
            "phrase": decision.get("selected_phrase"),
            "phrase_source": decision.get("phrase_source"),
            "organ_status": organ.get("status"),
            "instances": organ.get("instance_count"),
            "latency_ms": score["measured"]["latency_ms"],
            "cold_or_warm": score["measured"]["cold_or_warm"],
            "attribution": score["verdict"]["attribution"],
            "semantic_correctness": score["verdict"]["semantic_correctness"],
            "review_status": score["review"]["status"],
            "harness": score["verdict"]["harness"],
            "image_sha256": (trace.get("invariance") or {}).get("image_sha256_before"),
            "mask_hashes": [i.get("mask_rle_sha256") for i in (organ.get("instances") or [])],
        })

    images = {r["image_sha256"] for r in rows if r["image_sha256"]}
    same_image = len(images) <= 1
    phrases = {r["phrase"] for r in rows if r["phrase"]}

    findings: List[str] = []
    if not same_image:
        findings.append(
            "these runs are NOT on the same image, so nothing here attributes a difference to "
            "the phrase rather than to the picture")

    # ATTRIBUTION FOLLOWS THE DECLARED PAIR, and only the declared pair.
    #
    # The first version compared every orchestrated run against every direct run in the set. On
    # the real matrix that produced, from one orchestrated run, both "the PHRASE failed" (paired
    # against `face`, which found three) and "this points at the ORGAN" (paired against
    # `drapery fold`, which found none) — two contradictory attributions of the same run,
    # differing only in which unrelated concept it happened to be lined up beside. A comparison
    # across different concepts is not a control; `pair_with` is in the manifest precisely so
    # the pairing is declared before the numbers are known rather than discovered among them.
    by_id = {r["run_id"]: r for r in rows}

    def _pair_for(row):
        declared = row.get("pair_with")
        return by_id.get(declared) if declared else None

    for o in [r for r in rows if r["mode"] == "prompt_orchestrated"]:
        c = _pair_for(o)
        if c is None:
            findings.append(
                f"{o['run_id']}: no paired control in this set (declared "
                f"{o.get('pair_with') or 'none'}), so its result is not attributable to the "
                f"phrase rather than the organ")
            continue
        if not same_image:
            continue
        if o["organ_status"] == "empty" and c["organ_status"] == "ok":
            findings.append(
                f"{o['run_id']}: the organ succeeded on the paired control phrase "
                f"'{c['phrase']}' and measured nothing on the orchestrated phrase "
                f"'{o['phrase']}' — the PHRASE failed, not the organ")
        elif o["organ_status"] == "ok" and c["organ_status"] == "empty":
            findings.append(
                f"{o['run_id']}: the orchestrated phrase '{o['phrase']}' measured something "
                f"the paired control phrase '{c['phrase']}' did not")
        elif o["organ_status"] == "empty" and c["organ_status"] == "empty":
            findings.append(
                f"{o['run_id']}: the orchestrated phrase '{o['phrase']}' and its paired control "
                f"'{c['phrase']}' both measured nothing — this points at the ORGAN or at true "
                f"absence, and only review separates those two")

    # organ vs actuator: same phrase, same image, so any difference is the wrapper.
    organ_rows = [r for r in rows if r["mode"] == "organ_direct"]
    for a in [r for r in rows if r["mode"] == "actuator_direct"]:
        if not same_image:
            break
        for g in organ_rows:
            if g["phrase"] != a["phrase"]:
                continue
            if g["instances"] != a["instances"]:
                findings.append(
                    f"{a['run_id']} vs {g['run_id']}: the organ measured {g['instances']} "
                    f"instance(s) and the actuator surfaced {a['instances']} on the same "
                    f"phrase '{g['phrase']}' — the WRAPPER is the difference")
            elif g["mask_hashes"] != a["mask_hashes"]:
                findings.append(
                    f"{a['run_id']} vs {g['run_id']}: same instance count on '{g['phrase']}' "
                    f"but different masks — the wrapper altered geometry it was only meant to "
                    f"carry")

    # Phrases that behave differently on ONE image are a fact about the phrase, not the picture.
    if same_image:
        direct = [r for r in rows if r["mode"] in ("organ_direct", "actuator_direct")]
        found = sorted({r["phrase"] for r in direct if r["organ_status"] == "ok"})
        missed = sorted({r["phrase"] for r in direct if r["organ_status"] == "empty"})
        if found and missed:
            findings.append(
                f"on one image, these phrases measured something — {', '.join(repr(p) for p in found)} "
                f"— and these measured nothing — {', '.join(repr(p) for p in missed)}. The "
                f"picture is the same in every case, so the difference is carried entirely by "
                f"the wording")

    unreviewed = [r["run_id"] for r in rows
                  if r["semantic_correctness"] == "not_established"
                  and r["review_status"] == "pending"]
    if unreviewed:
        findings.append(
            f"semantic correctness is not established for {len(unreviewed)} run(s) "
            f"({', '.join(unreviewed)}); no comparison below is a claim that any mask is right")

    # Deduplicated, order preserved. A finding repeated six times reads as six pieces of
    # evidence and is one.
    seen: set = set()
    deduped = [f for f in findings if not (f in seen or seen.add(f))]

    return {
        "runs": rows,
        "same_image": same_image,
        "phrases": sorted(phrases),
        "phrases_agree": len(phrases) <= 1 if phrases else None,
        "findings": deduped,
    }


def render_compare(comparison: Dict[str, Any]) -> str:
    lines = ["# Single-actuator lab — comparison", ""]
    lines.append("| run | mode | expected | phrase | source | organ | inst | latency | attribution |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in comparison["runs"]:
        lines.append(
            f"| `{r['run_id']}` | {r['mode']} | {r['expected_condition']} | "
            f"`{_fmt(r['phrase'])}` | {_fmt(r['phrase_source'])} | **{_fmt(r['organ_status'])}** | "
            f"{_fmt(r['instances'])} | {_fmt(r['latency_ms'])} ms | {r['attribution']} |")
    lines.append("")
    lines.append(f"Same image across all runs: **{_fmt(comparison['same_image'])}**  ·  "
                 f"phrases: {', '.join(f'`{p}`' for p in comparison['phrases']) or '—'}")
    lines.append("")
    if comparison["findings"]:
        lines.append("## What this attributes")
        lines.append("")
        for f in comparison["findings"]:
            lines.append(f"- {f}")
        lines.append("")
    lines.append("> Semantic correctness is never concluded here. Agreement between a planner's "
                 "phrase and a human's control phrase says the planner chose well; it says "
                 "nothing about whether either mask is of the thing named.")
    lines.append("")
    return "\n".join(lines)
