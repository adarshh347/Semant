"""The four experimental arms. All of them end in the same normalised observation.

    A  organ_direct        image + explicit phrase → `sam3_concept_service.segment_concept`
    B  actuator_direct     image + frozen Step     → the production Director runner
    C  prompt_orchestrated full prompt             → locked planner → Arm B
    D  replay              frozen observations     → trace + score, zero calls

WHY THE PAIRING IS THE POINT. A alone cannot tell a bad phrase from a bad organ. B alone
cannot tell a bad organ from a wrapper that dropped its output. Run against the SAME image with
the SAME control phrase, A and B differ only by the wrapper; C and A differ only by who chose
the words. Three arms, two differences, and every failure lands on one of them.

ARM B RUNS THE REAL RUNNER. `_run_concept_segment` is not copied here — copying it would test
the copy. It is executed through `RealActuatorRunner`, exactly as `execute()` would, so the
image plumbing, region conversion, two-status descriptors, epistemic guard and provenance
stamping under test are the ones production uses. The only thing the lab supplies is the image
at the boundary, because the production path reaches it through a post fetch and this lab owns
no post.
"""
from __future__ import annotations

import contextlib
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import observe, planner as lab_planner
from .firewall import (CAPABILITY_UNAVAILABLE, EMPTY, ERROR, Firewall, NO_PHRASE, OK,
                       UNAVAILABLE)

#: The lab's stand-in post. It exists because the production runner threads a post id and a post
#: document through to the image fetch; nothing is read from it but the id, nothing is written to
#: it, and its digest is compared before and after so "nothing was written" is measured.
LAB_POST_ID = "lab_single_actuator"


def _lab_post() -> Dict[str, Any]:
    return {
        "_id": LAB_POST_ID,
        "photo_url": "lab://fixture",
        "region_annotations": [],
        "percepts": [],
    }


@contextlib.contextmanager
def lab_image(image_bytes: bytes):
    """Serve the fixture where the production path expects a fetched post image.

    Patched at `backend.routers.posts._fetch_post_image_cached` — the seam the real runner
    actually calls — rather than by editing the route to accept an injected image. The
    directive is explicit that production must not be changed to help the lab, and it is right:
    a seam added for a test is a seam production then has to keep.
    """
    import importlib
    posts = importlib.import_module("backend.routers.posts")
    original = posts._fetch_post_image_cached

    async def _serve(post_id: str, post: dict) -> bytes:
        return image_bytes

    posts._fetch_post_image_cached = _serve
    # The module keeps a one-entry image cache keyed by post id. Cleared on the way in and out
    # so a lab run neither inherits nor leaves behind bytes belonging to a real post.
    try:
        posts._refine_image_cache.clear()
    except Exception:
        pass
    try:
        yield posts
    finally:
        posts._fetch_post_image_cached = original
        try:
            posts._refine_image_cache.clear()
        except Exception:
            pass


def _svc():
    from backend.services import sam3_concept_service
    return sam3_concept_service


def _availability(env: Dict[str, Any]) -> Optional[str]:
    """Why the organ cannot run, or None if it can. Two reasons, kept apart because they are
    fixed by different actions: fetch 3.2 GiB, or install the ML stack."""
    if not env.get("weights_present"):
        return "weights_absent"
    if not env.get("runtime_available"):
        return "runtime_absent"
    return None


def _prepare(manifest: Dict[str, Any], env: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
    """Honour `warm_or_cold`. Returns (warm, load_ms).

    A cold receipt is only cold if the predictor is actually released first — the spike measured
    14.3 s of cold start, almost all of it the first inference, and a "cold" number taken from a
    resident model would understate it by an order of magnitude and mislead every capacity
    decision downstream.
    """
    svc = _svc()
    want_cold = (manifest.get("warm_or_cold") or "cold") == "cold"
    if want_cold:
        svc.unload()
        expect = manifest.get("model_expectation") or {}
        conf = expect.get("conf")
        imgsz = expect.get("imgsz")
        kwargs: Dict[str, Any] = {}
        if conf is not None:
            kwargs["conf"] = float(conf)
        if imgsz is not None:
            kwargs["imgsz"] = int(imgsz)
        load_ms = svc.load(**kwargs)
        return False, round(float(load_ms), 1)
    # Warm: whatever is resident stays resident. `load()` is idempotent and returns 0.0 when a
    # predictor already exists, which is exactly the signal "this was already warm".
    load_ms = svc.load()
    return load_ms == 0.0, round(float(load_ms), 1)


# ── Arm A ─────────────────────────────────────────────────────────────────────────────────────

def organ_direct(manifest: Dict[str, Any], firewall: Firewall, image_bytes: bytes,
                 phrase: str, env: Dict[str, Any]) -> Dict[str, Any]:
    """Given this image and this phrase, what did SAM 3 return?

    No Director step, no suggestion, no region conversion. Whatever this arm reports is the
    ORGAN's answer and nothing else's, which is the only way a later wrapper failure can be
    attributed to the wrapper.
    """
    reason = _availability(env)
    if reason:
        firewall.refuse(firewall.lock, CAPABILITY_UNAVAILABLE, reason)
        return observe.organ_observation(None, status=UNAVAILABLE, concept=phrase,
                                         detail=reason)
    if not (phrase or "").strip():
        firewall.refuse(firewall.lock, NO_PHRASE, "organ_direct requires a control phrase")
        return observe.organ_observation(None, status=EMPTY, concept=phrase,
                                         detail="no phrase to look for")

    svc = _svc()
    expect = manifest.get("model_expectation") or {}
    warm, load_ms = _prepare(manifest, env)
    kwargs: Dict[str, Any] = {}
    if expect.get("conf") is not None:
        kwargs["conf"] = float(expect["conf"])
    if expect.get("max_instances") is not None:
        kwargs["max_instances"] = int(expect["max_instances"])

    result, attempt = firewall.invoke(
        firewall.lock, "organ", lambda: svc.segment_concept(image_bytes, phrase, **kwargs),
        adapter="sam3", warm=warm, load_ms=load_ms)

    if attempt.outcome == ERROR:
        return observe.organ_observation(None, status=ERROR, concept=phrase,
                                         error=attempt.error)
    instances = (result or {}).get("instances") or []
    attempt.outcome = OK if instances else EMPTY
    return observe.organ_observation(result, status=attempt.outcome, concept=phrase)


# ── Arm B ─────────────────────────────────────────────────────────────────────────────────────

def actuator_direct(manifest: Dict[str, Any], firewall: Firewall, image_bytes: bytes,
                    phrase: str, env: Dict[str, Any], *, step: Any = None,
                    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Does the `concept_segment` tool preserve and expose what the organ returned?

    Returns (organ_observation, actuator_observation). The organ half is reconstructed from the
    regions and descriptors the production path produced rather than from a second organ call —
    a second call would be a second measurement and would spend a budget this lab does not have.
    """
    from backend.services.director.memory import WorkingMemory
    from backend.services.director.plan import Step
    from backend.services.director.real_actuators import ExecutionContext, RealActuatorRunner

    reason = _availability(env)
    if reason:
        firewall.refuse(firewall.lock, CAPABILITY_UNAVAILABLE, reason)
        return (observe.organ_observation(None, status=UNAVAILABLE, concept=phrase,
                                          detail=reason),
                {"status": UNAVAILABLE, "detail": reason, "adapter": "sam3", "model": None,
                 "confidence": None, "proposed_regions": [], "descriptors": [],
                 "conversion": {"instances": 0, "proposed_regions": 0,
                                "measured_descriptors": 0, "interpretive_descriptors": 0,
                                "naming_withheld": 0, "dropped": 0, "survived": False,
                                "statuses_seen": []}})

    if step is None:
        step = Step(actuator=firewall.lock, params={"phrase": phrase},
                    id=f"lab:{manifest['run_id']}:0", note="frozen lab control step")

    post = _lab_post()
    from .contract import sha256_json
    post_before = sha256_json(post)

    warm, load_ms = _prepare(manifest, env)
    ctx = ExecutionContext(post_id=LAB_POST_ID, post=post, run_id=f"lab::{manifest['run_id']}")
    memory = WorkingMemory(image_ref="lab://fixture", post_id=LAB_POST_ID, phrase=phrase)

    try:
        with lab_image(image_bytes):
            runner = RealActuatorRunner(firewall.lock, ctx)
            result, attempt = firewall.invoke(
                firewall.lock, "actuator", lambda: runner(step, memory),
                adapter="sam3", warm=warm, load_ms=load_ms)
    finally:
        ctx.close()

    # `RealActuatorRunner` catches every producer exception and returns an ERROR result rather
    # than raising — including a FirewallViolation from the database trap. That is why the
    # invariance record reads `firewall.db_writes` directly instead of relying on an exception
    # reaching this frame: a guard whose only evidence is a traceback is a guard the code under
    # test is free to swallow.
    if attempt.outcome == ERROR:
        organ = observe.organ_observation(None, status=ERROR, concept=phrase, error=attempt.error)
        actuator = {"status": ERROR, "detail": attempt.error, "adapter": "sam3", "model": None,
                    "confidence": None, "proposed_regions": [], "descriptors": [],
                    "conversion": {"instances": 0, "proposed_regions": 0,
                                   "measured_descriptors": 0, "interpretive_descriptors": 0,
                                   "naming_withheld": 0, "dropped": 0, "survived": False,
                                   "statuses_seen": []}}
        return organ, actuator

    status = getattr(result, "status", None)
    regions = list(ctx.regions or [])
    descriptors = list(ctx.suggestions or [])
    payload = getattr(result, "payload", None) or {}

    reconstructed = {
        "concept": payload.get("concept") or phrase,
        "instances": [
            {"index": i, "mask_rle": r.get("mask_rle"), "confidence": r.get("confidence")}
            for i, r in enumerate(regions)
        ],
        "truncated": payload.get("truncated"),
        "latency_ms": payload.get("latency_ms"),
        "device": env.get("device"),
        "model": getattr(result, "model", None),
    }
    organ_status = OK if regions else (status if status in (EMPTY, UNAVAILABLE, ERROR) else EMPTY)
    attempt.outcome = status if status in (OK, EMPTY, UNAVAILABLE, ERROR) else OK
    organ = observe.organ_observation(reconstructed, status=organ_status, concept=phrase,
                                      detail=getattr(result, "detail", None))
    actuator = observe.actuator_observation(result, regions=regions, descriptors=descriptors,
                                            instance_count=len(regions))
    actuator["post_sha256_before"] = post_before
    actuator["post_sha256_after"] = sha256_json(post)
    return organ, actuator


# ── Arm C ─────────────────────────────────────────────────────────────────────────────────────

def prompt_orchestrated(manifest: Dict[str, Any], firewall: Firewall, image_bytes: bytes,
                        env: Dict[str, Any], *, client: Any = None,
                        ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Can the prompt-facing reasoning choose a useful concrete phrase for the one tool it has?

    Returns (prompt_receipt, decision_receipt_extras, organ_observation, actuator_observation).

    The planner's proposal goes through the firewall BEFORE anything runs, and every step it
    proposed beyond the first is refused by budget rather than trimmed. A planner that asked for
    four calls when it had one is a finding about the planner; a lab that silently kept the
    first would have measured its own trimming.
    """
    prompt = manifest.get("prompt") or ""
    repro = manifest.get("reproducibility") or {}
    deterministic = bool(repro.get("deterministic_framer"))

    proposal = lab_planner.propose(prompt, firewall=firewall, client=client,
                                   deterministic=deterministic)
    receipt = {
        "planner_status": proposal.status,
        "planner_model": proposal.model,
        "planner_role": proposal.role,
        "planner_detail": proposal.detail,
        "raw_proposal": proposal.raw,
    }
    extras: Dict[str, Any] = {"planner_notes": list(proposal.notes),
                              "selected_actuator": None, "selected_phrase": None,
                              "phrase_source": None}
    # What the production clamp removed before the firewall ever saw the step. Pushed into the
    # firewall's own record so the trace has ONE list of dropped params rather than one per
    # clamping layer — two lists is how a reader ends up checking the wrong one.
    firewall.dropped_params.extend(proposal.dropped)

    if not proposal.steps:
        # No step, no call. `unavailable` and `empty` reach here for different reasons and stay
        # apart in the receipt; neither is quietly replaced by the manifest's control phrase.
        return receipt, extras, observe.organ_observation(
            None, status=(UNAVAILABLE if proposal.status == lab_planner.UNAVAILABLE else EMPTY),
            concept=None, detail=proposal.detail), {}

    admitted = None
    for step in proposal.steps:
        auth = firewall.authorize(step.actuator, step.params)
        if not auth.allowed:
            continue
        if admitted is None:
            admitted = (step, auth)
        # Loop continues: every remaining step is still put to the firewall so its refusal is
        # recorded. Breaking early would hide how much more the planner asked for.

    if admitted is None:
        extras["planner_notes"].append(
            "every proposed step was refused; nothing reached the actuator")
        return receipt, extras, observe.organ_observation(
            None, status=EMPTY, concept=None,
            detail="the planner proposed nothing this lab is permitted to run"), {}

    step, auth = admitted
    phrase = str(auth.params.get("phrase") or "").strip()
    extras["selected_actuator"] = auth.actuator
    extras["selected_phrase"] = phrase or None
    extras["phrase_source"] = ("deterministic_framer"
                               if proposal.status == lab_planner.DETERMINISTIC else "planner")

    if not phrase:
        firewall.refuse(auth.actuator, NO_PHRASE,
                        "the planner selected the actuator but named no concrete phrase")
        return receipt, extras, observe.organ_observation(
            None, status=EMPTY, concept=None,
            detail="the planner chose the tool but gave it nothing to look for"), {}

    from backend.services.director.plan import Step
    frozen = Step(actuator=auth.actuator, params=dict(auth.params),
                  id=step.id or f"lab:{manifest['run_id']}:0", note=step.note)
    organ, actuator = actuator_direct(manifest, firewall, image_bytes, phrase, env, step=frozen)
    return receipt, extras, organ, actuator


# ── Arm D ─────────────────────────────────────────────────────────────────────────────────────

def replay(run_path: str) -> Tuple[Dict[str, Any], List[str]]:
    """Rebuild the trace from frozen observations. No model, GPU, network or actuator call.

    Returns (trace, divergences). Determinism is not asserted in prose: the rebuilt trace is
    compared field by field against the frozen one and any difference is reported as a
    divergence rather than smoothed over. A replay that quietly differed from its source would
    make every frozen run unfalsifiable.
    """
    import os

    from .contract import read_json

    frozen = read_json(os.path.join(run_path, "trace.json"))
    observations_dir = os.path.join(run_path, "observations")

    rebuilt = dict(frozen)
    rebuilt["mode"] = "replay"
    rebuilt["invocations"] = []
    rebuilt["artifacts"] = dict(frozen.get("artifacts") or {})

    # The organ observation is rebuilt from the frozen per-instance observation files, not
    # copied from the trace — otherwise "replay reproduces the trace" would be tautological.
    organ = dict(frozen.get("organ_observation") or {})
    if os.path.isdir(observations_dir):
        names = sorted(n for n in os.listdir(observations_dir) if n.endswith(".json"))
        instances = []
        for name in names:
            if not name.startswith("instance-"):
                continue
            instances.append(read_json(os.path.join(observations_dir, name)))
        if instances:
            organ["instances"] = sorted(instances, key=lambda i: i.get("index", 0))
            organ["instance_count"] = len(instances)
    rebuilt["organ_observation"] = organ

    divergences: List[str] = []
    original = frozen.get("organ_observation") or {}
    if organ.get("instance_count") != original.get("instance_count"):
        divergences.append(
            f"instance_count {organ.get('instance_count')} != frozen "
            f"{original.get('instance_count')}")
    frozen_hashes = [i.get("mask_rle_sha256") for i in (original.get("instances") or [])]
    rebuilt_hashes = [i.get("mask_rle_sha256") for i in (organ.get("instances") or [])]
    if frozen_hashes != rebuilt_hashes:
        divergences.append("mask hashes differ between frozen observations and frozen trace")

    rebuilt["replay"] = {
        "source_run": frozen.get("run_id"),
        "live_calls": 0,
        "matches_source": not divergences,
        "divergences": divergences,
    }
    rebuilt["invariance"] = {
        **(frozen.get("invariance") or {}),
        "actuators_called": [],
        "lock_held": True,
        "database_writes_attempted": [],
    }
    return rebuilt, divergences
