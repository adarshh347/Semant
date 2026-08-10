"""
PERCEPTUAL-ORGANS-002 Lane D — the model arm, behind the identical resolver.

The same seam `ModelInquiryFramer` and `GroqPlanner` sit in, at organ scale. A language model reads
the person's sentence and proposes typed commands from a closed catalogue; every one of them then
meets the five gates that a pressed button meets. The model translates intent. It does not see the
image, does not author geometry, does not choose the organ, and does not decide that anything ran.

THE GUARDS, carried over from `inquiry/model.py` because they are the reason that seam holds:

  1. HALLUCINATIONS ARE NOT FILTERED AWAY. An operation key outside the registry is not dropped
     while parsing — `StepBuilder` turns it into `unsupported_operation` with the invented name in
     `detail`. The refusal rate is the only observable that says whether to trust this arm at all,
     and a parser that skipped the bad row would report zero forever.

  2. AN INVENTED ID IS PROPOSED AND THEN REFUSED, NOT QUIETLY DROPPED. A model that answers "those
     two" with `art_whatever` gets an `InputRef` built for it and the resolver refuses
     `unknown_reference` naming the id. Dropping the ref here would turn a fabricated identity
     into a `missing_extent_inputs` — the wrong diagnosis, and one that blames the person.

  3. NO RE-PROMPT LOOP. Exactly one call per `plan()`, and `calls` is public so a test can pin it.
     Looping until something resolves would search for a plan that validates rather than one that
     is what was asked for.

  4. UNAVAILABLE IS SAID OUT LOUD. No client, no key, an API error, unparseable JSON — all fall
     back to the deterministic planner, and the plan then reads `planner: rules` with
     `planner_fell_back_from: model`. A rules fallback wearing the model's name is the specific
     dishonesty the phase gate looks for, and `LabPlan` gives it a field so that it cannot be
     told by omission.

  5. AN EMPTY MODEL RESULT IS NOT A FAILURE. A model that proposes nothing has answered, and it
     does NOT trigger the fallback. Falling back there would overrule its honest silence with a
     keyword guess and then report the guess as the model's reading.

WHAT IS ABSENT FROM THE CATALOGUE RATHER THAN FORBIDDEN IN THE PROMPT. `extent.draw` and
`extent.reuse` — the two operations whose parameters are geometry and canonical identity. Listing
an operation and then telling a model not to use it invites exactly one attempt; not listing it
means the only way to reach it is to invent the name, which guard 1 catches by name.

PURE apart from the injected client. No database, no image, no clock.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Tuple

from backend.schemas.perception_lab import (IdentityScope, InputRef, OrganFamily, PlannerIdentity,
                                            RefusalCode, RefusalRecord)
from backend.services import role_registry
from backend.services.perception_lab.clock import IdFactory, SequentialIds
from backend.services.perception_lab.contracts import operation_index
from backend.services.perception_lab.definitions import (_message as contract_message,
                                                         enabled_organs, operation)
from backend.services.perception_lab.planners.base import StepBuilder
from backend.services.perception_lab.planners.rules import RulesPlanner
from backend.services.perception_lab.resolver import Proposal
from backend.services.perception_lab.session import SessionView

#: Unregistered on purpose. Lane D does not edit the shared role table, so `_model_name` asks
#: `role_registry.get` — which returns None for an unknown role — rather than `model_for`, which
#: raises. Lane F registers the role if it wants one; until then the caller injects the model or
#: the planner is unavailable and says so.
ROLE = "perception_lab_planner"
PRODUCER = "perception_lab/model-planner-v1"

#: The operations a model may never propose, because their parameters are a person's hand or a
#: canonical revision. Absent from the catalogue entirely — see the module docstring.
WITHHELD: Tuple[str, ...] = ("extent.draw", "extent.reuse")

#: The declared parameter types that ARE geometry. A planner may not supply one whatever operation
#: it names — see `_strip_geometry`, which is the guard the resolver structurally cannot be.
GEOMETRY_TYPES: Tuple[str, ...] = ("mask_rle", "box", "point_list")

#: More steps than this is a model writing an experiment rather than reading a request. The
#: overflow is REPORTED and the surplus dropped, never silently trimmed.
MAX_STEPS = 4

SYSTEM_PROMPT = (
    "You are the planning component of a perceptual laboratory. You are given a person's PROMPT, "
    "the organ their session is locked to, and the artifact ids that session has selected. YOU "
    "CANNOT SEE THE IMAGE and you never will. You output JSON and nothing else.\n\n"
    "Your job is to translate the request into typed commands. It is not to answer the question, "
    "and it is not to describe anything.\n\n"
    "Hard rules:\n"
    "- Use ONLY operation keys from the provided catalogue. Never invent one, and never rename "
    "one.\n"
    "- Set only the parameter names the catalogue lists for that operation, with the types and "
    "value ranges it declares.\n"
    "- Never output a mask, an RLE, a polygon, a bounding box, coordinates, an area, or a "
    "confidence value. You do not possess that information and no operation you may propose "
    "accepts it from you.\n"
    "- Cite ONLY artifact ids from the SELECTED IDS list. If the person says 'that mask' or "
    "'those two' and the list is empty, propose the operation with no inputs and say so in "
    "`notes`. Never invent an id, and never guess which artifact was meant.\n"
    "- You may propose an operation belonging to the other organ. The laboratory decides whether "
    "the session permits it; that decision is not yours and you must not avoid the proposal to "
    "make it go away.\n"
    "- If nothing in the catalogue serves the prompt, return an empty `steps` list. An empty "
    "list is a valid and useful answer; a plausible-looking wrong operation is not."
)


def _catalogue() -> List[Dict[str, Any]]:
    """The operation vocabulary, as data the model chooses from rather than prose it paraphrases.

    Structured for `groq_planner`'s reason: an operation key is a closed set and should be typed
    as one, because prose invites paraphrase and a paraphrased key is a hallucination that merely
    looks like a typo.
    """
    rows: List[Dict[str, Any]] = []
    for organ in enabled_organs():
        for op in organ.operations:
            if op.key in WITHHELD or op.manual:
                continue
            rows.append({
                "operation": op.key,
                "organ": organ.family,
                "asks": op.question,
                "summary": op.summary,
                "parameters": [
                    {"name": p.name, "type": p.type, "required": p.required,
                     **({"one_of": list(p.enum)} if p.enum else {}),
                     **({"minimum": p.minimum} if p.minimum is not None else {}),
                     **({"maximum": p.maximum} if p.maximum is not None else {})}
                    for p in op.parameters],
                "inputs": [{"role": i.role, "min": i.min, "max": i.max, "required": i.required,
                            "accepts": list(i.artifact_kinds)} for i in op.inputs],
            })
    return rows


def build_prompt(prompt: str, session: SessionView) -> str:
    return (
        f"THE PERSON'S PROMPT, verbatim:\n{prompt}\n\n"
        f"THE SESSION:\n"
        f"  selected organ: {session.selected_organ.value}\n"
        f"  mode: {session.mode.value}\n"
        f"  SELECTED IDS, in order — the only ids you may cite:\n"
        f"{json.dumps(list(session.artifact_ids), indent=2)}\n\n"
        f"AVAILABLE OPERATIONS — choose only from these:\n{json.dumps(_catalogue(), indent=2)}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"steps": [{{"operation": "<key from the catalogue>", "parameters": {{}}, '
        f'"inputs": [{{"role": "<role from that operation>", "artifact_id": "<id from SELECTED '
        f'IDS>"}}], "why": "<one clause, why this operation>"}}], "notes": ["<anything you could '
        f'not do, one clause each>"]}}\n'
        f"Return empty lists rather than inventing content for any field."
    )


class ModelPlanner:
    """A model proposes. The registry still refuses what it may not name, and the resolver still
    authorizes what it may not authorize."""

    name = "model"
    identity = PlannerIdentity.MODEL

    def __init__(self, client: Any = None, *, model: Optional[str] = None,
                 fallback: Optional[Any] = None, ids: Optional[IdFactory] = None):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        self._ids = ids if ids is not None else SequentialIds()
        self.fallback = fallback if fallback is not None else RulesPlanner(self._ids)
        self.calls: int = 0                      # guard 3 is observable
        self.last_notes: Tuple[str, ...] = ()

    @property
    def model(self) -> Optional[str]:
        if self._model is not None:
            return self._model
        role = role_registry.get(ROLE)
        return role_registry.model_for(ROLE) if role is not None else None

    def _get_client(self) -> Any:
        """Lazy real client. An absent key is UNAVAILABLE, not a crash."""
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        try:
            from groq import Groq

            from backend.config import settings
            self._client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        except Exception:
            self._client = None
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None and self.model is not None

    # -- the seam --

    def plan(self, request: str, session: SessionView) -> Proposal:
        client = self._get_client()
        if client is None:
            return self._fall_back(request, session,
                                   "the model planner is unavailable (no client or API key)")
        if self.model is None:
            return self._fall_back(request, session,
                                   f"no model is bound to the '{ROLE}' role")
        try:
            self.calls += 1
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": build_prompt(request, session)}],
                model=self.model,
                response_format={"type": "json_object"})
            payload = json.loads(completion.choices[0].message.content)
        except Exception as exc:
            return self._fall_back(request, session,
                                   f"the model planner failed: {type(exc).__name__}")

        # Cleared on the success path too: `last_notes` is documented as an observable of the LAST
        # planning call, and one fallback followed by one success would otherwise keep reporting
        # the stale fallback reason forever.
        self.last_notes = (f"planner: {self.name} ({self.model})",)
        return self._assemble(payload, session)

    def _fall_back(self, request: str, session: SessionView, why: str) -> Proposal:
        """Deterministic planning, and the proposal SAYS it was deterministic.

        `planner` becomes `rules` and `fell_back_from` becomes `model`. Not a note a reader might
        miss and not a flag on the model's own identity: two fields, one of which is the truth
        about what ran and the other of which is the truth about what was asked for.
        """
        proposal = self.fallback.plan(request, session)
        notes = (why, "fell back to the deterministic planner, which reads a closed phrase table "
                      "and no model at all") + tuple(proposal.notes)
        self.last_notes = notes[:2]
        return Proposal(planner=PlannerIdentity.RULES, steps=proposal.steps,
                        fell_back_from=PlannerIdentity.MODEL, refusals=proposal.refusals,
                        prerequisites=proposal.prerequisites, notes=notes)

    # -- parsing: tolerant of shape, strict about content --

    def _assemble(self, payload: Any, session: SessionView) -> Proposal:
        builder = StepBuilder(session.selected_organ, self._ids)
        if not isinstance(payload, Mapping):
            builder.note("the planner returned a non-object payload; nothing in it was used")
            payload = {}

        rows = payload.get("steps")
        rows = [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []
        if len(rows) > MAX_STEPS:
            builder.note(f"the planner proposed {len(rows)} steps; kept the first {MAX_STEPS}. "
                         f"A laboratory request is one question, not an experiment.")
            rows = rows[:MAX_STEPS]

        for row in rows:
            op_key = _text(row.get("operation")) or _text(row.get("key"))
            if not op_key:
                continue
            withheld = _withheld_refusal(op_key, session)
            if withheld is not None:
                builder.refuse(withheld)
                continue
            refs, bad = _inputs(row.get("inputs"), session)
            for ref in bad:
                builder.refuse(ref)
            supplied = row.get("parameters") if isinstance(row.get("parameters"), Mapping) else {}
            parameters, drawn = _strip_geometry(op_key, supplied)
            if drawn is not None:
                builder.refuse(drawn)
            builder.propose(op_key,
                            parameters=parameters,
                            input_refs=refs,
                            # The rationale is the MODEL'S, quoted as its reason for proposing —
                            # never rewritten here into a sentence that sounds like a finding.
                            rationale=_text(row.get("why")) or "the model planner proposed this")

        for note in payload.get("notes", []) if isinstance(payload.get("notes"), list) else []:
            if _text(note):
                builder.note(f"the planner said: {_text(note)}")

        if not builder.steps and not builder.refusals:
            builder.note("the planner proposed no operation. That is a valid answer and it was "
                         "NOT replaced by a deterministic guess.")
        return Proposal(planner=self.identity, steps=tuple(builder.steps),
                        refusals=tuple(builder.refusals), notes=tuple(builder.notes))


def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _strip_geometry(op_key: str, supplied: Mapping[str, Any]
                    ) -> Tuple[Dict[str, Any], Optional[RefusalRecord]]:
    """Remove every DECLARED parameter whose type is geometry, and say which were removed.

    THE RESOLVER CANNOT CATCH THIS ONE, which is the point. `resolve_parameters` drops undeclared
    keys, so a model that invents `mask_rle` on `extent.find_all` is already handled. But
    `extent.refine` DECLARES `points` and `box` — a person clicks them — so a model supplying them
    hands the resolver perfectly valid parameters, and nothing downstream can tell that they came
    from a component which has never seen the image. Geometry is refused by WHO SUPPLIED IT, and
    only this file knows that.

    The step still goes through without them, which is `inquiry/model.py` guard 2 exactly: the
    useful half of the request survives and the attempt is recorded rather than hidden. A refine
    with no points is a re-proposal for the same subject, which is a real operation; a refine with
    invented points is a measurement of a place nobody looked at.
    """
    if operation_index().get(op_key) is None:
        # An undeclared key has no parameter types to consult. It is about to be refused by name
        # in `StepBuilder.propose` (guard 1), and a second refusal here would report one
        # invention twice.
        return dict(supplied), None
    types = {p.name: p.type for p in operation(op_key).parameters}
    kept = {k: v for k, v in supplied.items() if types.get(k) not in GEOMETRY_TYPES}
    removed = sorted(set(supplied) - set(kept))
    if not removed:
        return kept, None
    detail = (f"a prompt planner may not supply {', '.join(removed)}. Those parameters are "
              f"geometry, and this planner has not seen the image")
    return kept, RefusalRecord(
        code=RefusalCode.INVALID_PARAMETERS, organ=OrganFamily(operation(op_key).organ),
        operation=op_key,
        message=contract_message("invalid_parameters", operation=op_key, detail=detail),
        missing=[], remedy="point at it with the manual tool; the Direct arm carries what you drew",
        detail={"removed": removed, "supplied_by": PRODUCER, "why": detail})


def _withheld_refusal(op_key: str, session: SessionView) -> Optional[RefusalRecord]:
    """Refuse a MANUAL operation named by a planner, before the step is built.

    WITHHOLDING IT FROM THE CATALOGUE IS NOT ENOUGH, and finding that out is why this function
    exists. `extent.draw` declares `mask_rle` and `polygon` as real parameters, so a model that
    names the operation anyway hands the resolver geometry the resolver has every reason to
    accept — it is declared, it is well typed, and nothing downstream can tell that a component
    which has never seen the image is what produced it. The catalogue stops the honest model; this
    stops the one that guessed the name.

    A CONTRADICTION, RECORDED. The right code for this is "only a person may author that", which
    `inquiry` spells `RefusalKind.HUMAN_ACTION_REQUIRED`. The lab's nine refusal codes have no
    such member, and Lane D does not widen a Lane A closed set. `invalid_parameters` is the
    truthful remainder — the operation exists and what is refused is this planner's attempt to
    supply its parameters — and the gap is in the handoff notes for Lane F.
    """
    if op_key not in WITHHELD:
        owner = operation_index().get(op_key)
        if owner is None or not operation(op_key).manual:
            return None
    detail = (f"a prompt planner may not author {op_key}. It is performed by a person, and its "
              f"parameters are their hand rather than a proposal about an image nothing here "
              f"has seen")
    return RefusalRecord(
        code=RefusalCode.INVALID_PARAMETERS, organ=session.selected_organ, operation=op_key,
        message=contract_message("invalid_parameters", operation=op_key, detail=detail),
        missing=[],
        remedy="use the manual tool for this operation; the Direct arm carries what you drew",
        detail={"withheld_from": PRODUCER, "why": detail})


def _inputs(raw: Any, session: SessionView) -> Tuple[Tuple[InputRef, ...], List[RefusalRecord]]:
    """Model rows into input refs, keeping every fabrication visible.

    An `artifact_id` the session never declared is BUILT ANYWAY and the resolver refuses it by
    name — guard 2. A `region_id` is refused here instead, because `InputRef` requires a
    `geometry_rev` beside it and a model has no revision to cite; constructing one would invent
    the identity the revision exists to pin.
    """
    refs: List[InputRef] = []
    refusals: List[RefusalRecord] = []
    rows = [r for r in raw if isinstance(r, Mapping)] if isinstance(raw, list) else []
    for row in rows:
        role = _text(row.get("role"))
        artifact_id = _text(row.get("artifact_id"))
        region_id = _text(row.get("region_id"))
        if not role:
            continue
        if artifact_id:
            refs.append(InputRef(role=role, scope=IdentityScope.SESSION, artifact_id=artifact_id))
            continue
        if region_id:
            refusals.append(RefusalRecord(
                code=RefusalCode.UNKNOWN_REFERENCE, organ=session.selected_organ,
                message=contract_message("unknown_reference", reference=region_id),
                missing=[region_id],
                remedy="a canonical region is cited by id AND geometry_rev; a planner has no "
                       "revision to cite, so regions enter a plan through the Direct arm",
                detail={"reference": region_id, "role": role, "supplied_by": PRODUCER}))
    return tuple(refs), refusals


__all__ = ["ModelPlanner", "ROLE", "PRODUCER", "WITHHELD", "MAX_STEPS", "SYSTEM_PROMPT",
           "build_prompt"]
