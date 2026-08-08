"""The score, and the one sentence the lab exists to be able to say.

TWO HALVES THAT NEVER TOUCH. `measured` is everything a machine can settle. `review` is
everything only a human or a gold mask can. This module writes the first and leaves the second
null, and `verdict.semantic_correctness` stays `not_established` until a reviewer fills it in.

That is not conservatism for its own sake. SF-004-R2 §4.3 measured the exact failure: on a
painting, `shoulder fabric` at confidence 0.27–0.43 returned a clean, well-formed mask OF THE
BACKGROUND. Every automated signal available — valid RLE, plausible area, sane bounds, a
confidence — said yes. The extent was measured correctly and the words were simply wrong, and
no amount of geometry could have told anyone so. A scorer that inferred correctness from those
signals would have certified it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import observe
from .contract import SCORE_VERSION

# Attribution codes — the closed set from the directive, plus the two the harness itself needs.
ORGAN_SUCCEEDED = "organ_succeeded"
ORGAN_EMPTY = "organ_returned_empty"
ORGAN_UNAVAILABLE = "organ_unavailable"
ORGAN_ERROR = "organ_error"
WRAPPER_DROPPED = "wrapper_dropped_data"
PHRASE_FAILED = "prompt_phrase_failed"
PLANNER_UNAVAILABLE = "planner_unavailable"
PLANNER_NOTHING = "planner_proposed_nothing"
NEGATIVE_AS_EXPECTED = "negative_control_empty_as_expected"
EMPTY_AMBIGUOUS = "empty_ambiguous_pending_review"
HARNESS_VIOLATION = "harness_violation"


def _availability(env: Dict[str, Any]) -> str:
    if not env.get("weights_present"):
        return "weights_absent"
    if not env.get("runtime_available"):
        return "runtime_absent"
    return "available"


def _violations(trace: Dict[str, Any]) -> List[str]:
    """Named, not counted. Each of these is a fact about the run that belongs in the report as
    a sentence, and a count would let three different failures share one number."""
    out: List[str] = []
    inv = trace.get("invariance") or {}
    if not inv.get("image_unchanged"):
        out.append("the source image changed during the run")
    if not inv.get("lock_held"):
        called = ", ".join(inv.get("actuators_called") or []) or "nothing"
        out.append(f"actuator leakage: the lock is {trace.get('actuator_lock')!r} but "
                   f"{called} reached an instrument")
    if inv.get("database_writes_attempted"):
        writes = ", ".join(f"{w.get('collection')}.{w.get('method')}"
                           for w in inv["database_writes_attempted"])
        out.append(f"database write attempted: {writes}")
    if inv.get("post_mutated"):
        out.append("the lab post document was mutated")
    budget = None
    for call in trace.get("invocations") or []:
        budget = call.get("call_budget") or budget
    if budget and len(trace.get("invocations") or []) > budget:
        out.append(f"call budget of {budget} exceeded: "
                   f"{len(trace['invocations'])} invocations recorded")
    return out


def _attribution(trace: Dict[str, Any], measured: Dict[str, Any], expected: str,
                 ) -> tuple[str, str]:
    """WHICH LAYER produced this outcome. The whole point of the lab, in one enum member."""
    if measured["violations"]:
        return HARNESS_VIOLATION, "; ".join(measured["violations"])

    prompt = trace.get("prompt_receipt") or {}
    organ = trace.get("organ_observation") or {}
    actuator = trace.get("actuator_observation") or None
    decision = trace.get("decision_receipt") or {}
    status = organ.get("status")
    mode = trace.get("mode")

    if mode == "prompt_orchestrated":
        if prompt.get("planner_status") in ("unavailable", "error"):
            return PLANNER_UNAVAILABLE, (
                f"no phrase was produced because the planner was {prompt.get('planner_status')}"
                f" — the control phrase was deliberately NOT substituted, so this run says "
                f"nothing about the organ")
        if not decision.get("selected_phrase"):
            return PLANNER_NOTHING, (
                "the planner saw one tool and did not produce a concrete phrase for it")

    if status == "unavailable":
        return ORGAN_UNAVAILABLE, organ.get("detail") or "the organ could not run"
    if status == "error":
        return ORGAN_ERROR, organ.get("error") or "the organ raised"

    if status == "empty":
        if expected == "negative":
            return NEGATIVE_AS_EXPECTED, (
                f"'{organ.get('concept')}' is not in this picture and the organ returned "
                f"nothing, which is the pass condition for a negative control")
        if mode == "prompt_orchestrated":
            return PHRASE_FAILED, (
                f"the organ ran on the planner's phrase '{organ.get('concept')}' and measured "
                f"nothing; whether the phrase or the organ is at fault is settled by the paired "
                f"control run, not by this one")
        return EMPTY_AMBIGUOUS, (
            f"the organ measured no instance of '{organ.get('concept')}'. Whether that is true "
            f"absence or a missed detection is a review question, not a measured one")

    if actuator is not None and actuator.get("conversion"):
        conversion = actuator["conversion"]
        if conversion.get("dropped"):
            return WRAPPER_DROPPED, (
                f"the organ measured {conversion.get('instances')} instance(s) and "
                f"{conversion.get('measured_descriptors')} measured descriptor(s) reached the "
                f"quarantine — the wrapper lost {conversion['dropped']}")

    return ORGAN_SUCCEEDED, (
        f"the organ measured {organ.get('instance_count')} instance(s) of "
        f"'{organ.get('concept')}'. Whether those instances ARE that concept is not established "
        f"here")


def build_score(trace: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    env = trace.get("environment") or {}
    organ = trace.get("organ_observation") or {}
    actuator = trace.get("actuator_observation") or None
    decision = trace.get("decision_receipt") or {}
    prompt = trace.get("prompt_receipt") or {}
    invocations = trace.get("invocations") or []
    inv = trace.get("invariance") or {}
    review_cfg = manifest.get("review") or {}
    expected = manifest.get("expected_condition", "open")

    instances = organ.get("instances") or []
    first = invocations[0] if invocations else {}

    planner_valid: Optional[bool] = None
    if trace.get("mode") == "prompt_orchestrated":
        requested = [r for r in (decision.get("refused_actions") or [])
                     if r.get("reason") in ("not_the_locked_actuator", "unknown_actuator",
                                            "call_budget_exhausted")]
        planner_valid = (prompt.get("planner_status") in ("ok", "deterministic_framer", "empty")
                         and not requested)

    violations = _violations(trace)

    measured: Dict[str, Any] = {
        "availability": _availability(env),
        "planner_valid": planner_valid,
        "actuator_leakage": not inv.get("lock_held", True),
        "planner_requested_unlocked": sorted(
            {r["actuator"] for r in (decision.get("refused_actions") or [])
             if r.get("actuator") and r.get("reason") in ("not_the_locked_actuator",
                                                          "unknown_actuator")}),
        "invocation_count": len(invocations),
        "call_budget": int(manifest.get("call_budget", 1)),
        "budget_respected": len(invocations) <= int(manifest.get("call_budget", 1)),
        "lock_held": bool(inv.get("lock_held", True)),
        "cold_or_warm": ("warm" if first.get("warm") else "cold") if invocations else None,
        "latency_ms": first.get("latency_ms") if invocations else None,
        "load_ms": first.get("load_ms") if invocations else None,
        "instance_count": int(organ.get("instance_count") or 0),
        "truncated": organ.get("truncated"),
        "mask_area_px": [int(i.get("area_px") or 0) for i in instances],
        "mask_area_fraction": [i["area_fraction"] for i in instances
                               if i.get("area_fraction") is not None],
        "mask_bounds": [i.get("bounds") for i in instances if i.get("bounds")],
        "max_pairwise_iou": organ.get("max_pairwise_iou"),
        "all_masks_well_formed": all(i.get("well_formed") for i in instances) if instances else True,
        "conversion_survival": (actuator or {}).get("conversion"),
        "two_status_preserved": observe.two_status_preserved(actuator),
        "repeat_stability": organ.get("repeat_stability"),
        "invariants_held": not violations,
        "violations": violations,
    }

    attribution, detail = _attribution(trace, measured, expected)
    gold = bool((review_cfg.get("gold_mask_path") or "").strip())
    protocol = review_cfg.get("protocol", "human_visual")

    return {
        "schema_version": SCORE_VERSION,
        "lab_id": trace["lab_id"],
        "run_id": trace["run_id"],
        "mode": trace["mode"],
        "expected_condition": expected,
        "measured": measured,
        "review": {
            # `pending` even when the harness is perfectly happy. The harness cannot review.
            "status": "not_required" if protocol == "none_required" else "pending",
            "protocol": protocol,
            "concept_binding": None,
            "coverage": None,
            "boundary_quality": None,
            "false_positives": None,
            "false_negatives": None,
            "iou_vs_gold": None,
            "gold_mask_present": gold,
            "empty_means": None,
            "reviewer": None,
            "reviewed_at": None,
            "notes": "",
        },
        "verdict": {
            "harness": "violated" if violations else "clean",
            # The only value the harness may write by itself. A reviewer editing score.json
            # moves it; nothing computed here ever does.
            "semantic_correctness": "not_established",
            "attribution": attribution,
            "attribution_detail": detail,
        },
        "pair": {
            "paired_run": manifest.get("pair_with"),
            "control_phrase": manifest.get("control_phrase"),
            "orchestrated_phrase": decision.get("selected_phrase"),
            "phrases_agree": None,
        } if manifest.get("pair_with") else None,
    }
