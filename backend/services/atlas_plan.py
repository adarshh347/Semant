"""
ATLAS C4 — Plan mode: M2's argument, drawn on the Atlas.

C1 put a corpus on one surface. This gate asks M2's rhetorical planner what ARGUMENT that corpus
could carry, and renders the answer as structure a writer can see and change: an ordered list of
sub-claims, each connected to the image whose evidence would carry it, each connector tagged with
what the percept is doing rhetorically and what kind of knowing it can reach.

A SHAPING LAYER, NOT A SECOND PLANNER. Nothing here decomposes a thesis, judges a claim, or decides
whether evidence binds. `RhetoricalDirector` does all of that, through the unmodified
`resolve_corpus()` gate, exactly as it does everywhere else. This module turns an `ArgumentPlan`
into something a canvas can draw, and turns an edited canvas back into `SubClaim`s so the planner
can judge it again. It is the translation, and it is deliberately dumb about arguments.

THREE RULES THIS MODULE ENFORCES, each of which is easy to break and expensive to notice.

  1. ONLY A BOUND PERCEPT GETS A CONNECTOR. A line from a claim to an image says "this claim would
     rest on evidence from this photograph". A percept that `resolve_corpus` refused would not rest
     on anything, so drawing its line — greyed, dashed, however apologetically — would put the
     shape of a supported argument on the canvas and leave the refusal as a caption nobody reads.
     Refused percepts are listed IN the claim, in words, with the gate's own reason.

  2. A BINDING IS NOT A RELATION. C3's edges run image↔image and each one is a real `compare_views`
     percept. C4's connectors run claim→image and assert only that a step resolved. They are kept
     in `plan`, never in `edges`, and they carry a different `kind` so nothing downstream can
     mistake one for the other. The moment a proposed binding got written into `edges`, the Atlas
     would hold a relation nobody produced.

  3. ACCEPTING RE-BINDS; IT DOES NOT RECORD WHAT THE CLIENT CLAIMS. The accept payload carries
     claims and percepts — never statuses. Every accepted plan is re-judged by `plan_argument`
     against the corpus as it is at accept time, so a stored `supported` was earned twice and a
     writer who deletes the only challenge percept gets an argument-level refusal rather than a
     tidy document. Params are clamped to each actuator's declared vocabulary on the way in, for
     the same reason `groq_planner` clamps the model's: a client is no more entitled to author
     geometry than a language model is.

WHAT AN EDIT MAY AND MAY NOT DO. A writer may reorder claims, drop a claim, drop a percept, and
reword a claim. A reworded claim keeps `proposed_text` beside its new `text` in the stored plan —
M2's binding proves a percept RESOLVES, not that it bears on the sentence, and a claim rewritten
after its evidence was chosen has quietly widened that gap. Showing both texts costs one field and
is the only way a later reader can see it happened.

PURE. No database, no network, no clock. The route does the I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.director.argument import (
    EPISTEMIC_STATUSES, FUNCTIONS, INTERPRETIVE, PerceptStep, SubClaim)
from backend.services.director.capabilities import is_comparative
from backend.services.director.corpus import IMAGE_PARAM
from backend.services.director.groq_planner import _clamp_params
from backend.services.director.plan import Step

PLAN_CONTRACT_VERSION = 1

# What a connector IS, written on every one of them. C3 will mint `relation` edges between images;
# these are `binding` edges between a claim and an image. A single shared word here would be the
# whole confusion, so the two vocabularies never meet.
EDGE_BINDING = "binding"

# A claim the plan proposes but nothing carries. Rendered struck through, with the gate's reason —
# it stays in the argument because a thesis whose third claim could not be evidenced is a fact
# about the corpus, and deleting it would leave a shorter argument that looks complete.
STRUCK_STATUS = "refused"

# How many claims one accepted plan may hold. Same cap as `argument_planner.MAX_CLAIMS`, applied on
# the way IN as well, because the accept route takes a client payload rather than a model's.
MAX_CLAIMS = 6
MAX_PERCEPTS_PER_CLAIM = 5

# The planner name a re-bound, writer-edited plan is recorded under. Distinct from
# `argument_groq` because the two are different provenances: one is what a model proposed, the
# other is what a person kept, and a document that called them both `argument_groq` would lose the
# only record of who chose the claims.
PLANNER_ACCEPTED = "atlas_accepted"


# ── the corpus the Atlas spans ───────────────────────────────────────────────

def node_post_ids(doc_or_view: Mapping[str, Any]) -> List[str]:
    """The Atlas's images, in NODE ORDER, which is the corpus order.

    Order is the argument (M1) and the node list preserves it through every arrangement save
    (`merge_nodes` re-emits the document's own order). Reading the corpus off the nodes rather than
    off `corpus_ref.post_ids` is deliberate: the nodes are what the writer is looking at.
    """
    out: List[str] = []
    for node in doc_or_view.get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        pid = str(node.get("post_id") or "")
        if pid and pid not in out:
            out.append(pid)
    return out


def node_index(doc_or_view: Mapping[str, Any]) -> Dict[str, str]:
    """post_id → node_id, for pointing a connector at the picture on the canvas.

    First node wins if an Atlas somehow holds one image twice — a connector must name exactly one
    endpoint, and picking the later one would move a claim's line on a document nobody edited.
    """
    out: Dict[str, str] = {}
    for node in doc_or_view.get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        pid = str(node.get("post_id") or "")
        nid = str(node.get("node_id") or "")
        if pid and nid:
            out.setdefault(pid, nid)
    return out


# ── the plan, as the canvas draws it ─────────────────────────────────────────

def _image_of(percept: PerceptStep) -> Optional[str]:
    """Which image this percept is planned on — from the step params if the planner put it there,
    from the PerceptStep otherwise. `_steps_for` writes one into the other before resolving, and a
    reader here should not have to know which end of that it is looking at."""
    param = (percept.step.params or {}).get(IMAGE_PARAM)
    return str(param) if param not in (None, "") else (percept.image or None)


def connector(claim_id: str, percept: PerceptStep, nodes: Mapping[str, str]) -> Optional[Dict[str, Any]]:
    """One bound percept → the line from its claim to its image, or None when there is no line.

    Returns None in two honest cases, and they are different:
      · a COMPARATIVE percept (`spans_images == 2`) is planned across the corpus and names no
        image, so there is no single node to point at. It is reported on the claim itself instead.
      · a percept whose image this Atlas does not hold. `resolve_corpus` would normally have
        refused it as `unknown_image`, so reaching here means the corpus and the canvas disagree —
        and inventing an endpoint would hide exactly that.
    """
    if is_comparative(percept.actuator):
        return None
    post_id = _image_of(percept)
    node_id = nodes.get(str(post_id)) if post_id else None
    if not node_id:
        return None
    return {
        "edge_id": f"{claim_id}~{percept.step.id}",
        "kind": EDGE_BINDING,
        "claim_id": claim_id,
        "step_id": percept.step.id,
        "node_id": node_id,
        "post_id": str(post_id),
        "actuator": percept.actuator,
        "function": percept.function,
        "epistemic": percept.ceiling,
        "note": percept.note or percept.step.note or "",
    }


def _percept_row(percept: PerceptStep, *, bound: bool, why: str = "",
                 nodes: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    post_id = _image_of(percept)
    comparative = is_comparative(percept.actuator)
    return {
        "step_id": percept.step.id,
        "actuator": percept.actuator,
        "params": dict(percept.step.params or {}),
        "function": percept.function,
        "known_function": percept.function in FUNCTIONS,
        "target_status": percept.target_status,
        "epistemic": percept.ceiling,
        "image": str(post_id) if post_id else None,
        "node_id": (nodes or {}).get(str(post_id)) if post_id else None,
        # A comparative percept relates images to each other. Said in a field rather than inferred
        # from a null image, because "across the corpus" and "the planner named no image" look
        # identical in the data and mean opposite things.
        "spans_corpus": comparative,
        "bound": bool(bound),
        "why": why,
        "note": percept.note or percept.step.note or "",
    }


def claim_rows(argument: Any, nodes: Mapping[str, str]) -> List[Dict[str, Any]]:
    """The argument as an ordered list of claims, each with its percepts and its verdict.

    Both halves are kept — `bound` and `unbound` — for the reason `BoundClaim` keeps them: a row
    holding only what worked makes a qualified claim indistinguishable from a supported one.
    """
    rows: List[Dict[str, Any]] = []
    for order, claim in enumerate(argument.claims):
        bound = [_percept_row(p, bound=True, nodes=nodes) for p in claim.bound]
        unbound = [_percept_row(p, bound=False, why=why, nodes=nodes) for p, why in claim.unbound]
        rows.append({
            "claim_id": claim.claim_id,
            "order": order,
            "text": claim.claim.text,
            # Equal at proposal time; they diverge only when a writer rewords a bound claim.
            "proposed_text": claim.claim.text,
            "note": claim.claim.note,
            "status": claim.status,
            "reason": claim.reason,
            "binding": claim.binding,
            "target_status": claim.claim.target_status,
            "achieved_status": claim.achieved_status,
            "downgraded": claim.downgraded,
            "struck": claim.status == STRUCK_STATUS,
            "caveats": list(claim.caveats),
            "functions": sorted({p.function for p in claim.bound}),
            "percepts": bound + unbound,
        })
    return rows


def plan_view(argument: Any, atlas: Mapping[str, Any], *,
              accepted: bool = False, planner_available: bool = True,
              notes: Sequence[str] = ()) -> Dict[str, Any]:
    """Everything the canvas needs to draw the plan, and nothing it does not.

    `argument.to_dict()` travels alongside the shaped rows rather than being replaced by them. The
    shaped view is for drawing; the raw plan is the record, and a surface that could only show the
    prettified version would be one refactor away from the record and the drawing disagreeing.
    """
    nodes = node_index(atlas)
    rows = claim_rows(argument, nodes)
    connectors = [c for claim in argument.claims for c in
                  (connector(claim.claim_id, p, nodes) for p in claim.bound) if c]
    return {
        "contract_version": PLAN_CONTRACT_VERSION,
        "thesis": argument.thesis,
        "planner": argument.planner,
        "accepted": bool(accepted),
        # ZERO CLAIMS MEANS TWO DIFFERENT THINGS and the surface has to be able to tell them
        # apart: "the planner is not reachable" and "the planner read this corpus and found no
        # argument in it". They are identical in the claim list and opposite in what a writer
        # should do next, so the reachability is its own field rather than a note to be parsed.
        "planner_available": bool(planner_available),
        # Straight from M2. `complete` means every claim carried AND a counter-reading was seeded;
        # it is never softened on the way to the surface.
        "complete": argument.complete,
        "has_challenge": argument.has_challenge,
        "weakest_status": argument.weakest_status,
        "claims": rows,
        "connectors": connectors,
        "refusals": [r.to_dict() for r in argument.refusals],
        "gaps": argument.gaps(),
        "notes": [*argument.notes, *notes],
        "counts": {
            "claims": len(argument.claims),
            "supported": len(argument.supported),
            "qualified": len(argument.qualified),
            "refused": len(argument.refused),
            "connectors": len(connectors),
        },
    }


# ── an edited plan, coming back ──────────────────────────────────────────────

def _normalise_status(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    return text if text in EPISTEMIC_STATUSES else INTERPRETIVE


def claims_from_payload(raw_claims: Any) -> Tuple[List[SubClaim], List[str], Dict[str, str]]:
    """The writer's edited plan → SubClaims to re-bind. Returns `(claims, notes, proposed_text)`.

    STATUSES ARE NOT READ. The payload may carry them — it is the view this client was handed —
    and every one is discarded. `plan_argument` decides what is carried, from the corpus, on every
    accept. A client that could post `status: supported` would be able to write an unevidenced
    argument into the document with one curl.

    Params are clamped and unknown actuators are passed through, the same two guards
    `argument_planner.parse_claims` applies to the model's output, because at this point the
    payload's provenance is a browser and the discipline should not depend on who is talking.
    """
    notes: List[str] = []
    proposed: Dict[str, str] = {}
    if not isinstance(raw_claims, list):
        return [], ["the accepted plan carried no claims list"], proposed

    claims: List[SubClaim] = []
    for ci, row in enumerate(raw_claims):
        if not isinstance(row, Mapping):
            notes.append(f"claim {ci} was not an object and was dropped")
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            notes.append(f"claim {ci} carried no text and was dropped")
            continue
        # The claim keeps the id it was proposed under. A reordered plan must still be traceable
        # back to the decomposition it came from, and renumbering by position would silently
        # rewrite which claim a stored connector refers to.
        claim_id = str(row.get("claim_id") or f"c{ci}").strip() or f"c{ci}"
        target = _normalise_status(row.get("target_status"))

        was = str(row.get("proposed_text") or "").strip()
        if was and was != text:
            proposed[claim_id] = was
            notes.append(f"{claim_id} was reworded after its evidence was bound; the binding "
                         f"proves the percepts resolve, not that they bear on the new wording")

        percepts: List[PerceptStep] = []
        for pi, praw in enumerate(row.get("percepts") or []):
            if not isinstance(praw, Mapping):
                notes.append(f"{claim_id} percept {pi} was not an object and was dropped")
                continue
            name = str(praw.get("actuator") or "").strip()
            if not name:
                notes.append(f"{claim_id} percept {pi} named no actuator and was dropped")
                continue
            params, dropped = _clamp_params(name, dict(praw.get("params") or {}))
            if dropped:
                notes.append(f"{claim_id} percept {pi} ('{name}') carried disallowed params, "
                             f"dropped: {', '.join(dropped)}")
            image = praw.get("image")
            function = praw.get("function")
            function = function.strip().lower() if isinstance(function, str) else ""
            if function and function not in FUNCTIONS:
                notes.append(f"{claim_id} percept {pi} named an unknown function '{function}'; "
                             f"kept verbatim to be refused")
            step_id = str(praw.get("step_id") or "").strip() or f"{claim_id}:{pi}:{name}"
            note = praw.get("note")
            percepts.append(PerceptStep(
                step=Step(actuator=name, params=params, id=step_id,
                          note=str(note) if isinstance(note, str) else ""),
                function=function or "",
                target_status=target,
                image=str(image).strip() if isinstance(image, (str, int)) and str(image).strip()
                else None,
                note=str(note) if isinstance(note, str) else ""))

        if len(percepts) > MAX_PERCEPTS_PER_CLAIM:
            notes.append(f"{claim_id} carried {len(percepts)} percepts; kept the first "
                         f"{MAX_PERCEPTS_PER_CLAIM}")
            percepts = percepts[:MAX_PERCEPTS_PER_CLAIM]

        claims.append(SubClaim(claim_id=claim_id, text=text, percepts=tuple(percepts),
                               target_status=target,
                               note=str(row.get("note") or "")))

    if len(claims) > MAX_CLAIMS:
        notes.append(f"the accepted plan carried {len(claims)} claims; kept the first {MAX_CLAIMS}")
        claims = claims[:MAX_CLAIMS]
    return claims, notes, proposed


def stored_plan(argument: Any, atlas: Mapping[str, Any], *,
                proposed_text: Optional[Mapping[str, str]] = None,
                notes: Sequence[str] = (), now: str = "") -> Dict[str, Any]:
    """What an accepted plan looks like in the Atlas document — C5's seed.

    The whole shaped view, plus the reworded-claim record and a timestamp. Stored as data rather
    than as a reference to a run because there is no run: a plan is what WOULD be produced, and
    `binding: planned` on every claim says so. Only `confirm_against_chain` — after something
    actually executes — may say otherwise.
    """
    view = plan_view(argument, atlas, accepted=True, notes=notes)
    proposed_text = proposed_text or {}
    for row in view["claims"]:
        was = proposed_text.get(row["claim_id"])
        if was:
            row["proposed_text"] = was
            row["reworded"] = True
    view["accepted_at"] = now
    return view


# Params the stored plan must never carry, whatever a client sent. `_clamp_params` already drops
# everything an actuator does not declare, so this is the belt to that braces — checked, like
# `assert_no_percept_data`, because a discipline nobody can violate by accident is worth the lines.
_FORBIDDEN_PARAM_KEYS = frozenset({
    "geometry", "mask", "box", "points", "polygon", "bbox", "confidence", "score",
    "region_id", "mark_id", "ground_id", "percept_id",
})


def assert_plan_authors_no_evidence(plan: Optional[Mapping[str, Any]]) -> None:
    """Raise if a stored plan has begun to carry evidence rather than propose it.

    A plan names actuators and images. The moment one of its params held geometry, the Atlas would
    hold a measurement nobody produced, wearing a step's name — and it would render on the canvas
    beside real percepts with nothing distinguishing it.
    """
    if not plan:
        return
    for row in plan.get("claims") or []:
        for percept in (row or {}).get("percepts") or []:
            leaked = sorted(set((percept.get("params") or {}).keys()) & _FORBIDDEN_PARAM_KEYS)
            if leaked:
                raise ValueError(
                    f"plan step '{percept.get('step_id')}' carries evidence in its params: "
                    f"{leaked}. A plan proposes what to look for; it never reports what was found.")
