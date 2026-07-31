"""
CIRCUIT-003 M2 — the rhetorical planner: a thesis becomes an argument, or is refused.

Layer 3 plans percepts to EXIST. `Director.plan("trace the light")` yields a chain that will
leave marks behind, and every guarantee it makes is about whether those marks can be produced.
Nothing in it asks what the marks are FOR. An article does: a thesis decomposed into sub-claims,
each carried by percepts with an argumentative function, and every claim either bound to evidence
that can actually be produced or honestly qualified.

This module is that layer, and it is the argument-level twin of the manuscript's cites-nothing
rule: a claim with no producible evidence is not quietly dropped and not quietly asserted — it is
marked, with the refusal that made it so.

    ArgumentFunction  — support | complicate | challenge, on every percept-step
    EpistemicStatus   — visible | measured | sourced | interpretive | uncertain
    SubClaim          — a claim + the percept-steps proposed to carry it (PROPOSED, unbound)
    BoundClaim        — the same claim after `resolve()` judged its steps (BOUND, with lineage)
    ArgumentPlan      — thesis → bound claims + the merged executable plan + argument refusals

THREE RULES, EACH OF WHICH A LATER REFACTOR WILL WANT TO BREAK FIRST.

  1. NO EVIDENCE IS INVENTED TO CARRY A CLAIM. Binding runs the claim's steps through the
     UNMODIFIED `resolve()` / `resolve_corpus()`. A claim whose steps refuse is downgraded — to
     QUALIFIED if some survived, REFUSED if none did. There is no path in this module that adds a
     step, substitutes an easier actuator, or re-prompts for a plan that passes. Searching for a
     chain that runs rather than a chain that is true is the fabrication the whole Director exists
     to prevent, and it would arrive here disguised as helpfulness.

  2. EACH CLAIM STANDS ON ITS OWN EVIDENCE. Claims are bound INDEPENDENTLY, against the corpus as
     it actually is — never against a memory advanced by another claim's steps. If claim B's
     percept needs a region on the rotunda, claim B must plan to find it; borrowing the region
     claim A happened to find would make B look supported by evidence gathered to argue something
     else, and the merged plan would still run. The merged plan is built afterwards, for
     execution; it is not what decides whether a claim is carried.

  3. THE COUNTER-READING IS SEEDED, NEVER SYNTHESIZED. An argument with no `challenge` step is
     refused AT THE ARGUMENT LEVEL rather than repaired by inserting one. A challenge step this
     module wrote would be a counter-reading nobody meant, and M3 would compose prose from it in
     perfect good faith.

PURE MODULE. No database, no fetch, no model, no clock. The Groq-backed decomposition lives in
`argument_planner.py` for the same reason `groq_planner.py` is separate: this one has to stay
importable and testable with nothing installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .capabilities import ACTUATORS, Resource, get as get_actuator, known
from .corpus import (CorpusWorkingMemory, IMAGE_PARAM, REFUSED_IMAGE_SCOPE,
                     REFUSED_UNKNOWN_IMAGE, resolve_corpus)
from .memory import WorkingMemory
from .plan import Plan, RefusedStep, Step, resolve

ARGUMENT_VERSION = 1


# ── the argumentative function ───────────────────────────────────────────────
# What a percept is DOING in the argument, which is not derivable from what it produces. A
# pressure-zone field on the rotunda supports "the rotunda centralizes" and complicates "the
# sequence disperses"; the field is identical and the function is not.

SUPPORT = "support"
COMPLICATE = "complicate"
CHALLENGE = "challenge"

FUNCTIONS: Tuple[str, ...] = (SUPPORT, COMPLICATE, CHALLENGE)

FUNCTION_MEANING: Dict[str, str] = {
    SUPPORT: "evidence the claim rests on",
    COMPLICATE: "evidence that holds while making the claim harder to state simply",
    CHALLENGE: "evidence that would tell against the claim if it came back strong",
}


def known_function(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in FUNCTIONS


# ── the epistemic status ─────────────────────────────────────────────────────

#
# ONE VOCABULARY, TWO ENTRY POINTS. M6 (`backend/services/epistemics.py`) owns this vocabulary and
# the WALL around `sourced`: it stamps the status onto every produced descriptor and refuses to let
# a sourced claim be re-tagged as something the picture shows. M2 reads the same five values one
# level up, on CLAIMS rather than descriptors.
#
# The values are taken FROM M6 when it is importable, and fall back to the identical literals when
# it is not — M2 and M6 were built in parallel branches off the same main, and this module must
# stay importable on either side of that merge. `test_argument_m2.py` pins the two against each
# other, so a divergence fails loudly instead of quietly forking the vocabulary in half.
try:                                                   # pragma: no cover - import shape
    from backend.services.epistemics import EpistemicStatus as _M6Status
    VISIBLE = _M6Status.VISIBLE.value
    MEASURED = _M6Status.MEASURED.value
    SOURCED = _M6Status.SOURCED.value
    INTERPRETIVE = _M6Status.INTERPRETIVE.value
    UNCERTAIN = _M6Status.UNCERTAIN.value
except Exception:                                      # M6 not on this branch yet
    _M6Status = None
    VISIBLE = "visible"              # you can see it in the frame
    MEASURED = "measured"            # an instrument reports it
    SOURCED = "sourced"              # an external source asserts it
    INTERPRETIVE = "interpretive"    # a reading of what was gathered
    UNCERTAIN = "uncertain"          # not established

EPISTEMIC_STATUSES: Tuple[str, ...] = (VISIBLE, MEASURED, SOURCED, INTERPRETIVE, UNCERTAIN)

# A REPORTING order, not a claim about truth. It exists so "the weakest thing this claim rests
# on" is answerable at all — the same reason `ChainProvenance.weakest_link` is a minimum and not
# an average. Four confident measured steps must not bury the interpretive one doing the actual
# argumentative work.
_STRENGTH: Dict[str, int] = {VISIBLE: 4, MEASURED: 3, SOURCED: 2, INTERPRETIVE: 1, UNCERTAIN: 0}

# `sourced` is NOT a rung on that ladder — it is a different KIND of knowing, and the only one
# whose warrant lies outside the picture. Ranking it numerically was the first thing written here
# and it was wrong: it made a rhythm measurement (strength 3) "reach" a claim that aimed to be
# sourced (strength 2), so "Schinkel intended the conversion" came back satisfied by a CPU field
# over a photograph. Nothing measured in the frame can stand in for a source, however strong the
# measurement, so the target is reached only by the kind that actually warrants it.
_KINDS_ONLY_REACHED_BY_THEMSELVES = frozenset({SOURCED})

# What each actuator can epistemically REACH — its ceiling, never a promise. A field producer
# measures; a semantic pass interprets; a relation between two marks is an interpretation of two
# measurements and is recorded as such.
#
# WHAT REACHES `sourced`. Only an actuator that consults something outside the picture. On this
# branch the catalogue has none, so a claim targeting `sourced` is always downgraded — a true
# report about this system's reach rather than a gap in this table. M6's `historical_source` is
# the first that does, and its row is written below so the ceiling is right the moment the two
# branches meet; an actuator absent from the catalogue is simply never looked up.
ACTUATOR_EPISTEMIC_CEILING: Dict[str, str] = {
    # -- outside the image: the ONLY way to reach `sourced` (M6) ---------------
    "historical_source": SOURCED,
    # finders — extent you can point at
    "find_parts": VISIBLE,
    "grounded_sam_find_parts": VISIBLE,
    # fields — an instrument's report over the frame or a region
    "negative_space": MEASURED,
    "material_field": MEASURED,
    "rhythm": MEASURED,
    "pressure_zone": MEASURED,
    "background_recession": MEASURED,
    "atmosphere_field": MEASURED,
    "light_field": MEASURED,
    "shadow_field": MEASURED,
    # readings — verified counts and presences are measurements; a semantic pass is not
    "presence_check": MEASURED,
    "enumerate": MEASURED,
    "semantic_read": INTERPRETIVE,
    # circulation — a distance is measured; a NAMED relation is a reading of one
    "find_similar": MEASURED,
    "connect_marks": INTERPRETIVE,
    "compare_views": INTERPRETIVE,
    "compose_percept": INTERPRETIVE,
    "compose_comparative_percept": INTERPRETIVE,
}


def epistemic_ceiling(actuator: str) -> str:
    """The best status this actuator can reach. UNKNOWN actuators reach `uncertain` — they are
    about to be refused by name, and crediting an invented actuator with a status would put a
    model-authored epistemic claim into a record where a reader might trust it."""
    return ACTUATOR_EPISTEMIC_CEILING.get(actuator, UNCERTAIN)


def weakest_status(statuses: Sequence[str]) -> str:
    """The weakest of several. `uncertain` for an empty set — a claim resting on nothing is not
    strongly anything."""
    known_ones = [s for s in statuses if s in _STRENGTH]
    if not known_ones:
        return UNCERTAIN
    return min(known_ones, key=lambda s: _STRENGTH[s])


def reaches(achieved: str, target: str) -> bool:
    """Did what actually bound reach what the claim aimed for?

    Strength comparison along the ladder, EXCEPT for the kinds that only themselves can warrant.
    A claim aiming at `sourced` is reached only by something sourced — no amount of measuring the
    picture sources a claim about what someone intended.
    """
    if target in _KINDS_ONLY_REACHED_BY_THEMSELVES:
        return achieved == target
    return _STRENGTH.get(achieved, 0) >= _STRENGTH.get(target, 0)


# ── claim status ─────────────────────────────────────────────────────────────

SUPPORTED = "supported"      # every proposed percept-step is carried
QUALIFIED = "qualified"      # some are; the claim stands on less than it asked for
REFUSED = "refused"          # none are; there is no evidence path to this claim

# Why a claim ended up where it did. A closed set, because a caller (M3's composer, M5's UI) has
# to branch on it, and free text that varies with phrasing is not something anyone can branch on.
REASON_ALL_BOUND = "all_percepts_bound"
REASON_PARTIAL = "some_percepts_refused"
REASON_NONE_BOUND = "no_percept_could_be_produced"
REASON_NO_PERCEPTS = "no_percepts_proposed"
REASON_UNKNOWN_FUNCTION = "unknown_argumentative_function"

# BINDING PROVENANCE: is this judged from a PLAN, or from a RUN that actually happened?
BINDING_PLANNED = "planned"      # `resolve()` says the evidence CAN be produced
BINDING_CONFIRMED = "confirmed"  # a chain ran and the evidence WAS produced


@dataclass(frozen=True)
class PerceptStep:
    """One percept proposed to carry a claim, with its argumentative job written on it.

    The `Step` is the ordinary Layer-3 step — same actuator vocabulary, same params, same gate.
    Everything else here is rhetoric, deliberately kept OUTSIDE the step: an actuator must not be
    able to behave differently because a planner said the percept was a challenge, or the
    evidence would be shaped by the argument it is meant to test.
    """
    step: Step
    function: str = SUPPORT
    target_status: str = INTERPRETIVE
    image: Optional[str] = None          # which corpus image, when the corpus has more than one
    note: str = ""                       # why this percept carries this claim, in the planner's words

    @property
    def actuator(self) -> str:
        return self.step.actuator

    @property
    def ceiling(self) -> str:
        return epistemic_ceiling(self.step.actuator)

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step.id, "actuator": self.step.actuator,
                "params": dict(self.step.params), "function": self.function,
                "target_status": self.target_status, "epistemic_ceiling": self.ceiling,
                "image": self.image, "note": self.note}


@dataclass(frozen=True)
class SubClaim:
    """A claim, and the percepts PROPOSED to carry it. Unbound: nothing has judged it yet."""
    claim_id: str
    text: str
    percepts: Tuple[PerceptStep, ...] = ()
    target_status: str = INTERPRETIVE
    note: str = ""

    def functions(self) -> Tuple[str, ...]:
        return tuple(p.function for p in self.percepts)

    def to_dict(self) -> Dict[str, Any]:
        return {"claim_id": self.claim_id, "text": self.text,
                "target_status": self.target_status, "note": self.note,
                "percepts": [p.to_dict() for p in self.percepts]}


@dataclass(frozen=True)
class BoundClaim:
    """A claim after the gate judged its percepts. The lineage, claim → evidence, in one object.

    `bound` and `unbound` are BOTH kept. A record holding only what worked is the one shape that
    makes a qualified claim indistinguishable from a supported one — the reader sees three
    percepts either way and has no way to learn that two more were asked for and refused.
    """
    claim: SubClaim
    status: str
    reason: str
    bound: Tuple[PerceptStep, ...] = ()
    unbound: Tuple[Tuple[PerceptStep, str], ...] = ()    # (percept, why it will not run)
    achieved_status: str = UNCERTAIN
    binding: str = BINDING_PLANNED
    # Things true of this binding that do not change its status but must not be silent. The one
    # that forced this field into existence: a percept planned on an image whose POST COULD NOT BE
    # READ still binds, because the actuator needs only the image itself and the picture is
    # fetched at execution. That is defensible — and it is not the same as binding to an image
    # that was read and found empty. Without a caveat the two are indistinguishable in the record.
    caveats: Tuple[str, ...] = ()

    # ── derived ──
    @property
    def claim_id(self) -> str:
        return self.claim.claim_id

    @property
    def carried(self) -> bool:
        """Is there ANY evidence path to this claim? False is the argument-level refusal."""
        return self.status in (SUPPORTED, QUALIFIED)

    @property
    def downgraded(self) -> bool:
        """Did the evidence fall short of what the claim aimed to be?"""
        return not reaches(self.achieved_status, self.claim.target_status)

    def functions(self) -> Tuple[str, ...]:
        return tuple(p.function for p in self.bound)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.claim.text,
            "status": self.status,
            "reason": self.reason,
            "binding": self.binding,
            "target_status": self.claim.target_status,
            "achieved_status": self.achieved_status,
            "downgraded": self.downgraded,
            "bound": [p.to_dict() for p in self.bound],
            "unbound": [{**p.to_dict(), "why": why} for p, why in self.unbound],
            "functions": list(self.functions()),
            "caveats": list(self.caveats),
        }


# ── argument-level refusals ──────────────────────────────────────────────────

ARGUMENT_NO_CHALLENGE = "no_challenge_step"
ARGUMENT_NO_CLAIMS = "no_claims_proposed"
ARGUMENT_NOTHING_CARRIED = "no_claim_is_carried"


@dataclass(frozen=True)
class ArgumentRefusal:
    """Something wrong with the ARGUMENT, not with any one claim. First-class, like
    `Plan.refused` — an argument plan that reported only per-claim problems would let a thesis
    with no counter-reading and no carried claim look like a working plan with some gaps."""
    reason: str
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {"reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class ArgumentPlan:
    """A thesis, decomposed, bound, and honest about what it cannot carry."""
    thesis: str
    claims: Tuple[BoundClaim, ...] = ()
    plan: Optional[Plan] = None            # the merged, resolved chain — what would actually run
    refusals: Tuple[ArgumentRefusal, ...] = ()
    planner: str = "rule_based"
    notes: Tuple[str, ...] = ()
    version: int = ARGUMENT_VERSION

    # ── derived ──
    @property
    def supported(self) -> Tuple[BoundClaim, ...]:
        return tuple(c for c in self.claims if c.status == SUPPORTED)

    @property
    def qualified(self) -> Tuple[BoundClaim, ...]:
        return tuple(c for c in self.claims if c.status == QUALIFIED)

    @property
    def refused(self) -> Tuple[BoundClaim, ...]:
        return tuple(c for c in self.claims if c.status == REFUSED)

    @property
    def functions_present(self) -> Tuple[str, ...]:
        """Functions on percepts that are actually CARRIED. A challenge step that refused is not
        a counter-reading — it is the absence of one, which is the whole point of checking."""
        out: List[str] = []
        for claim in self.claims:
            for percept in claim.bound:
                if percept.function not in out:
                    out.append(percept.function)
        return tuple(out)

    @property
    def has_challenge(self) -> bool:
        return CHALLENGE in self.functions_present

    @property
    def complete(self) -> bool:
        """Every claim carried, and the counter-reading seeded. A partial argument is honest;
        it is not complete, and nothing downstream should be able to read it as such."""
        return bool(self.claims) and not self.refusals and all(c.carried for c in self.claims)

    @property
    def weakest_status(self) -> str:
        return weakest_status([c.achieved_status for c in self.claims])

    def lineage(self) -> List[Dict[str, Any]]:
        """claim → the percepts carrying it → the actuator and image each rests on.

        The trace M3 composes from and M5 renders. Flat on purpose: a composer asking "what may
        I say, and on what" should not have to walk a tree to find out.
        """
        rows: List[Dict[str, Any]] = []
        for claim in self.claims:
            for percept in claim.bound:
                rows.append({
                    "claim_id": claim.claim_id, "claim": claim.claim.text,
                    "claim_status": claim.status, "step_id": percept.step.id,
                    "actuator": percept.actuator, "image": percept.image,
                    "function": percept.function,
                    "epistemic_ceiling": percept.ceiling,
                    "achieved_status": claim.achieved_status, "bound": True,
                })
            for percept, why in claim.unbound:
                rows.append({
                    "claim_id": claim.claim_id, "claim": claim.claim.text,
                    "claim_status": claim.status, "step_id": percept.step.id,
                    "actuator": percept.actuator, "image": percept.image,
                    "function": percept.function,
                    "epistemic_ceiling": percept.ceiling,
                    "achieved_status": claim.achieved_status, "bound": False, "why": why,
                })
        return rows

    def gaps(self) -> List[Dict[str, str]]:
        """Everything this argument could NOT carry. What a reader must not be able to miss."""
        out: List[Dict[str, str]] = []
        for claim in self.claims:
            for caveat in claim.caveats:
                out.append({"claim_id": claim.claim_id, "claim": claim.claim.text,
                            "status": claim.status, "why": caveat})
            if claim.status == SUPPORTED and not claim.downgraded:
                continue
            out.append({"claim_id": claim.claim_id, "claim": claim.claim.text,
                        "status": claim.status,
                        "why": claim.reason if claim.status != SUPPORTED
                               else f"reached {claim.achieved_status}, aimed for "
                                    f"{claim.claim.target_status}"})
        for refusal in self.refusals:
            out.append({"claim_id": "", "claim": "", "status": "argument_refused",
                        "why": f"{refusal.reason}: {refusal.detail}"})
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "thesis": self.thesis,
            "planner": self.planner,
            "complete": self.complete,
            "has_challenge": self.has_challenge,
            "functions_present": list(self.functions_present),
            "weakest_status": self.weakest_status,
            "claims_total": len(self.claims),
            "claims_supported": len(self.supported),
            "claims_qualified": len(self.qualified),
            "claims_refused": len(self.refused),
            "claims": [c.to_dict() for c in self.claims],
            "refusals": [r.to_dict() for r in self.refusals],
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "lineage": self.lineage(),
            "gaps": self.gaps(),
            "notes": list(self.notes),
        }


# ── binding: the crux ────────────────────────────────────────────────────────

def _resolve_for(steps: Sequence[Step], memory: WorkingMemory, *, intention: str) -> Plan:
    """The ordinary gate, corpus-aware when the memory is. One place, so a claim on a corpus and
    a claim on one image are judged by code that cannot diverge."""
    if isinstance(memory, CorpusWorkingMemory) and memory.corpus is not None:
        return resolve_corpus(steps, memory, intention=intention, planner="argument")
    return resolve(steps, memory, intention=intention, planner="argument")


def _steps_for(claim: SubClaim) -> List[Step]:
    """The claim's percept-steps as ordinary Steps, with the image written into the params.

    The image travels as a step param because that is how M1's `resolve_corpus` reads a target;
    a second mechanism would be a second thing to keep in sync.
    """
    out: List[Step] = []
    for percept in claim.percepts:
        params = dict(percept.step.params or {})
        if percept.image and not params.get(IMAGE_PARAM):
            params[IMAGE_PARAM] = percept.image
        out.append(Step(actuator=percept.step.actuator, params=params,
                        id=percept.step.id, note=percept.step.note or percept.note))
    return out


def bind_claim(claim: SubClaim, memory: WorkingMemory) -> BoundClaim:
    """Judge ONE claim against the evidence that can actually be produced for it.

    The rule this function exists to enforce: a claim is carried only if real percepts resolve
    for it. Nothing here adds a step, swaps an actuator for an easier one, or relaxes a
    requirement. `resolve()` decides, exactly as it decides for every other plan in the system,
    and its refusal — by name, by missing input, by unknown image — becomes the claim's reason.

    A percept whose FUNCTION is not in the vocabulary is unbound even if its step would resolve.
    An invented function is a rhetorical hallucination, and letting it through with a step that
    happens to run would put an unreadable job on a real piece of evidence — worse than a refusal,
    because it looks like it worked.
    """
    if not claim.percepts:
        return BoundClaim(claim=claim, status=REFUSED, reason=REASON_NO_PERCEPTS,
                          achieved_status=UNCERTAIN)

    bad_function = {p.step.id: p for p in claim.percepts if not known_function(p.function)}
    plan = _resolve_for(_steps_for(claim), memory, intention=claim.text)
    survived = {s.id for s in plan.steps}
    why_refused = {r.step.id: f"{r.reason}: {r.detail}" for r in plan.refused}

    bound: List[PerceptStep] = []
    unbound: List[Tuple[PerceptStep, str]] = []
    for percept in claim.percepts:
        if percept.step.id in bad_function:
            unbound.append((percept,
                            f"{REASON_UNKNOWN_FUNCTION}: '{percept.function}' is not one of "
                            f"{', '.join(FUNCTIONS)}"))
            continue
        if percept.step.id in survived:
            bound.append(percept)
        else:
            unbound.append((percept, why_refused.get(
                percept.step.id, "the step was not placed and no reason was recorded")))

    if not bound:
        status, reason = REFUSED, REASON_NONE_BOUND
    elif unbound:
        status, reason = QUALIFIED, REASON_PARTIAL
    else:
        status, reason = SUPPORTED, REASON_ALL_BOUND

    # The claim reaches only as far as the WEAKEST thing carrying it, and never further than the
    # ceiling of the actuators that actually bound. A claim aiming at `measured` whose only bound
    # percept is a semantic read is interpretive, whatever it aimed for.
    achieved = weakest_status([p.ceiling for p in bound])
    return BoundClaim(claim=claim, status=status, reason=reason, bound=tuple(bound),
                      unbound=tuple(unbound), achieved_status=achieved,
                      binding=BINDING_PLANNED, caveats=_caveats_for(bound, memory))


def _caveats_for(bound: Sequence[PerceptStep], memory: WorkingMemory) -> Tuple[str, ...]:
    """What is true of these bindings but does not change the claim's status.

    Today: percepts planned on an image the corpus could NOT read. Such a percept binds — an
    image-only actuator needs nothing that hydration would have supplied, and the picture itself
    is fetched at execution — but "bound to an image we could not read" and "bound to an image we
    read and found empty" are different facts, and M1 went to some trouble to keep them apart at
    the corpus level. Losing the distinction one layer up would undo that.
    """
    if not isinstance(memory, CorpusWorkingMemory):
        return ()
    unreadable = {u.split(":", 1)[1] for u in memory.unreadable if u.startswith("post:")}
    if not unreadable:
        return ()
    hit = sorted({p.image for p in bound if p.image and p.image in unreadable})
    return tuple(f"planned on '{pid}', whose post could not be read; the evidence path is "
                 f"assumed, not verified" for pid in hit)


def bind_claims(claims: Sequence[SubClaim], memory: WorkingMemory) -> List[BoundClaim]:
    """Every claim, judged INDEPENDENTLY against the same memory.

    Independence is rule 2, and it is the whole reason this is a loop over `bind_claim` rather
    than one big resolve: binding claims against a memory advanced by earlier claims' steps would
    let a claim look carried by evidence gathered to argue something else.
    """
    return [bind_claim(claim, memory) for claim in claims]


def merged_plan(claims: Sequence[BoundClaim], memory: WorkingMemory, *,
                thesis: str = "") -> Plan:
    """One executable chain from every claim's BOUND percepts, in claim order.

    Built from bound percepts only — a step that refused for its own claim must not slip into the
    run because some other claim's resolve happened to place it. Duplicate steps (two claims
    wanting the same field on the same image) are collapsed by step id, keeping the first, so the
    chain does not fire one producer twice and count the result as two pieces of evidence.
    """
    steps: List[Step] = []
    seen: set = set()
    for claim in claims:
        for percept in claim.bound:
            params = dict(percept.step.params or {})
            if percept.image and not params.get(IMAGE_PARAM):
                params[IMAGE_PARAM] = percept.image
            key = (percept.step.actuator, params.get(IMAGE_PARAM),
                   tuple(sorted((k, str(v)) for k, v in params.items())))
            if key in seen:
                continue
            seen.add(key)
            steps.append(Step(actuator=percept.step.actuator, params=params,
                              id=percept.step.id, note=percept.step.note))
    return _resolve_for(steps, memory, intention=thesis)


def plan_argument(thesis: str, claims: Sequence[SubClaim], memory: WorkingMemory, *,
                  planner: str = "rule_based", notes: Sequence[str] = (),
                  require_challenge: bool = True) -> ArgumentPlan:
    """Bind every claim, merge what is carried, and refuse the argument if it is not one.

    ARGUMENT-LEVEL REFUSAL, which is the part with no analogue below this layer. A plan refuses
    STEPS; an argument can be made entirely of steps that run and still not be an argument — if
    nothing is carried, or if nobody proposed a way it could be wrong. Both are recorded as
    refusals rather than repaired, because the repair in each case is something this module would
    have to invent.
    """
    bound = bind_claims(claims, memory)
    refusals: List[ArgumentRefusal] = []

    if not bound:
        refusals.append(ArgumentRefusal(
            reason=ARGUMENT_NO_CLAIMS,
            detail=f"nothing was decomposed from '{thesis}'; no claim was proposed"))
    elif not any(c.carried for c in bound):
        refusals.append(ArgumentRefusal(
            reason=ARGUMENT_NOTHING_CARRIED,
            detail=(f"all {len(bound)} claim(s) refused; no percept could be produced for any "
                    f"of them")))

    plan = merged_plan(bound, memory, thesis=thesis)

    if require_challenge:
        carried_functions = {p.function for c in bound for p in c.bound}
        if CHALLENGE not in carried_functions:
            proposed = any(p.function == CHALLENGE for c in bound for p in c.claim.percepts)
            refusals.append(ArgumentRefusal(
                reason=ARGUMENT_NO_CHALLENGE,
                detail=("a challenge percept was proposed but could not be produced; the "
                        "counter-reading has no evidence to stand on"
                        if proposed else
                        "no percept was given the challenge function; nothing in this argument "
                        "could tell against it")))

    return ArgumentPlan(thesis=thesis, claims=tuple(bound), plan=plan,
                        refusals=tuple(refusals), planner=planner, notes=tuple(notes))


# ── confirming a plan against a run that actually happened ───────────────────

def confirm_against_chain(argument: ArgumentPlan, provenance: Any) -> ArgumentPlan:
    """Re-judge every claim against what a RUN actually produced. Plan-time → run-time.

    `resolve()` proves the evidence CAN be produced; only a run proves it WAS. They differ exactly
    when a producer came back empty or a model was down — the case where a claim's status would
    otherwise stay `supported` on the strength of a step that ran and found nothing.

    Downgrade-only, deliberately. A run can take a claim from supported to qualified to refused; it
    can never promote one, because a step that was refused at plan time never ran and no run
    outcome can speak for it. `binding` flips to `confirmed`, so a reader can always tell which
    kind of judgement they are looking at.
    """
    lineage = {r.step_id: r for r in getattr(provenance, "lineage", ())}
    produced_ok = {sid for sid, rec in lineage.items() if getattr(rec, "status", "") == "ok"}

    reconfirmed: List[BoundClaim] = []
    for claim in argument.claims:
        still: List[PerceptStep] = []
        lost: List[Tuple[PerceptStep, str]] = list(claim.unbound)
        for percept in claim.bound:
            record = lineage.get(percept.step.id)
            if record is None:
                lost.append((percept, "planned, but the run has no record of it"))
            elif percept.step.id in produced_ok:
                still.append(percept)
            else:
                lost.append((percept, f"{getattr(record, 'status', 'unknown')}: "
                                      f"{getattr(record, 'detail', '')}".strip(": ")))
        if not still:
            status, reason = REFUSED, REASON_NONE_BOUND
        elif lost:
            status, reason = QUALIFIED, REASON_PARTIAL
        else:
            status, reason = SUPPORTED, REASON_ALL_BOUND
        reconfirmed.append(BoundClaim(
            claim=claim.claim, status=status, reason=reason, bound=tuple(still),
            unbound=tuple(lost), achieved_status=weakest_status([p.ceiling for p in still]),
            binding=BINDING_CONFIRMED,
            # Caveats are re-derived from what SURVIVED: a percept planned on an unreadable image
            # that then ran fine no longer needs the warning, and one that never ran is already
            # reported as unbound.
            caveats=tuple(c for c in claim.caveats
                          if any(p.image and f"'{p.image}'" in c for p in still))))

    refusals = [r for r in argument.refusals if r.reason != ARGUMENT_NO_CHALLENGE]
    carried_functions = {p.function for c in reconfirmed for p in c.bound}
    if any(r.reason == ARGUMENT_NO_CHALLENGE for r in argument.refusals) or \
            CHALLENGE not in carried_functions:
        refusals.append(ArgumentRefusal(
            reason=ARGUMENT_NO_CHALLENGE,
            detail="no challenge percept survived the run; the counter-reading is unevidenced"))
    if reconfirmed and not any(c.carried for c in reconfirmed) and \
            not any(r.reason == ARGUMENT_NOTHING_CARRIED for r in refusals):
        refusals.append(ArgumentRefusal(
            reason=ARGUMENT_NOTHING_CARRIED,
            detail="the run produced no evidence for any claim"))

    return ArgumentPlan(thesis=argument.thesis, claims=tuple(reconfirmed), plan=argument.plan,
                        refusals=tuple(refusals), planner=argument.planner,
                        notes=tuple([*argument.notes, "confirmed against a run"]))


# ── assembling claims by hand (tests, fixtures, and the rule-based path) ─────

def make_claim(claim_id: str, text: str, percepts: Sequence[Any], *,
               target_status: str = INTERPRETIVE, note: str = "") -> SubClaim:
    """A SubClaim from `(actuator, params, function)` tuples or PerceptSteps.

    Step ids are derived from the claim id and position — no clock, no counter — so the same
    decomposition binds identically twice and two runs can be diffed directly. Same replayability
    property `Workflow.to_steps` has, for the same reason.
    """
    out: List[PerceptStep] = []
    for i, spec in enumerate(percepts):
        if isinstance(spec, PerceptStep):
            out.append(spec if spec.step.id
                       else PerceptStep(step=spec.step.with_id(f"{claim_id}:{i}:{spec.actuator}"),
                                        function=spec.function,
                                        target_status=spec.target_status,
                                        image=spec.image, note=spec.note))
            continue
        actuator, params, function = (list(spec) + [{}, SUPPORT])[:3]
        params = dict(params or {})
        image = params.pop(IMAGE_PARAM, None)
        out.append(PerceptStep(
            step=Step(actuator=str(actuator), params=params,
                      id=f"{claim_id}:{i}:{actuator}"),
            function=str(function), target_status=target_status, image=image))
    return SubClaim(claim_id=claim_id, text=text, percepts=tuple(out),
                    target_status=target_status, note=note)
