"""
CIRCUIT-003 M2 — the model-backed rhetorical planner: a thesis decomposed into sub-claims.

`groq_planner.GroqPlanner` asks a model for a chain of actuators. This asks it for an ARGUMENT:
sub-claims, and for each one the percepts that would carry it, each percept tagged with what it
is doing rhetorically and on which image of the corpus. Same model, same one-call discipline, one
level up.

THE FOUR GUARDS, carried over verbatim from PLANNER-001 because they are the reason that seam
holds, plus two this level needs:

  1. HALLUCINATIONS ARE NOT FILTERED HERE. An invented actuator name, and an image id this corpus
     does not hold, both pass through untouched so `resolve_corpus()` refuses them BY NAME and by
     `unknown_image`. Dropping them while parsing would produce a tidy argument and hide how often
     the model invents evidence it cannot have — and the refusal rate is the only observable that
     says whether to trust the decomposition at all.

  2. PARAMS ARE CLAMPED TO THE DECLARED VOCABULARY. Every param key not in the actuator's
     `param_keys` is dropped and RECORDED. This is what stops a model from smuggling in geometry,
     masks, region ids or a confidence — evidence it has no way to possess.

  3. NO RE-PROMPT LOOP. Exactly one call per `propose()`. If claims come back unbindable, that is
     reported and the argument stands as qualified or refused. Looping until every claim binds
     would search for an argument that passes rather than one that is true, which at THIS level
     means manufacturing the evidence base for a predetermined conclusion.

  4. FAILURE IS UNAVAILABLE, AND SAID OUT LOUD. No key, no client, API error, unparseable JSON —
     all yield NO claims plus a note saying why. There is deliberately no rule-based fallback:
     decomposing a thesis into sub-claims is not something a keyword table can do, and a fallback
     that invented a plausible decomposition would be the single worst failure mode this module
     has. An empty argument that says "the planner was unavailable" is the honest answer.

  5. THE COUNTER-READING IS ASKED FOR, NOT INSERTED. The prompt requires at least one `challenge`
     percept. If the model does not supply one, `plan_argument` refuses the argument — this module
     never adds the missing challenge itself, because a counter-reading nobody meant is worse than
     an argument that admits it has none.

  6. FUNCTIONS AND STATUSES ARE PASSED THROUGH, NOT COERCED. A function outside
     {support, complicate, challenge} is kept verbatim so binding can refuse the percept by name.
     Silently mapping an unknown function to `support` would let the model dodge guard 5 with a
     typo, and would put an unreadable rhetorical job on a real piece of evidence.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .argument import (CHALLENGE, EPISTEMIC_STATUSES, FUNCTIONS, FUNCTION_MEANING, INTERPRETIVE,
                       PerceptStep, SubClaim, epistemic_ceiling)
from .capabilities import ACTUATORS, known
from .corpus import CorpusWorkingMemory, IMAGE_PARAM
from .groq_planner import DEFAULT_MODEL, _clamp_params
from .memory import WorkingMemory
from .plan import Step

PLANNER_ARGUMENT_GROQ = "argument_groq"

# An argument with more sub-claims than this is not an argument, it is a list. The cap is applied
# after parsing and the overflow is REPORTED, never trimmed silently.
MAX_CLAIMS = 6
# Per claim. A claim needing seven percepts is really several claims.
MAX_PERCEPTS_PER_CLAIM = 5

SYSTEM_PROMPT = (
    "You are a rhetorical planning component inside a visual close-reading tool. You take a "
    "THESIS about a sequence of photographs and decompose it into sub-claims, and for each "
    "sub-claim you name the visual evidence that would carry it. You output JSON and nothing "
    "else.\n\n"
    "Hard rules:\n"
    "- Every percept must name an actuator from the provided list. Never invent one.\n"
    "- Every percept must name an image from the provided corpus, by its id. A claim about the "
    "rotunda must plan its evidence on the rotunda's image.\n"
    "- EXCEPT for actuators whose 'spans_images' is 2: those relate two images to each other and "
    "must NOT name an image at all. Leave their 'image' null. Pinning a comparative actuator to "
    "one image is refused.\n"
    "- You may set only the parameter keys listed for that actuator. Never output geometry, "
    "masks, coordinates, region ids, mark ids, or confidence values — you cannot see the "
    "images and do not possess that information.\n"
    "- Every percept carries a FUNCTION: 'support' (evidence the claim rests on), 'complicate' "
    "(evidence that holds while making the claim harder to state simply), or 'challenge' "
    "(evidence that would tell against the claim if it came back strong).\n"
    "- AT LEAST ONE percept in the whole argument must have the function 'challenge'. An "
    "argument that nothing could contradict is not an argument.\n"
    "- Give each sub-claim a target epistemic status: what KIND of knowing it aims at.\n"
    "- Do not assert that any evidence exists. You are proposing what to look for, not "
    "reporting what was found.\n"
    "- Prefer few strong claims. If the thesis cannot be argued with these actuators on these "
    "images, return an empty list. An empty argument is a valid and useful answer; a "
    "plausible-looking unsupported one is not."
)


def _actuator_catalog() -> List[Dict[str, Any]]:
    """The sensory vocabulary, as data the model must choose from, with what each can
    epistemically REACH. The ceiling is included so a claim aiming at `measured` is planned with
    an instrument rather than a semantic pass — a distinction the model cannot infer from the
    actuator's name and will otherwise get wrong in the direction that flatters the argument."""
    rows: List[Dict[str, Any]] = []
    for name in known():
        a = ACTUATORS[name]
        rows.append({
            "actuator": name,
            "does": a.summary,
            "requires": [r.describe() for r in a.requires],
            "produces": [p.value for p in a.produces],
            "params_you_may_set": list(a.param_keys),
            "epistemic_ceiling": epistemic_ceiling(name),
            "spans_images": a.spans_images,
        })
    return rows


def _corpus_catalog(memory: WorkingMemory) -> List[Dict[str, Any]]:
    """The images this argument may be built on, in sequence order, with what each already holds.

    A planner that cannot see there are zero marks on the colonnade will keep planning relations
    there. Counts come from the per-image packets, so they are what is actually committed — never
    a total that would let one image's evidence flatter another's.
    """
    if not isinstance(memory, CorpusWorkingMemory) or memory.corpus is None:
        return [{"post_id": memory.post_id, "image_ref": memory.image_ref, "position": 0,
                 "counts": {k.value: v for k, v in memory.available().items()}}]
    rows: List[Dict[str, Any]] = []
    for image in memory.corpus.images:
        packet = memory.per_image.get(image.post_id)
        rows.append({
            "post_id": image.post_id,
            "title": image.title,
            "note": image.note,
            "position": image.position,
            "counts": ({k.value: v for k, v in packet.available().items()} if packet else {}),
        })
    return rows


def build_prompt(thesis: str, memory: WorkingMemory) -> str:
    corpus_title = ""
    corpus_why = ""
    if isinstance(memory, CorpusWorkingMemory) and memory.corpus is not None:
        corpus_title = memory.corpus.title
        corpus_why = memory.corpus.why
    return (
        f"THESIS TO ARGUE:\n{thesis}\n\n"
        f"THE CORPUS — an ORDERED sequence of images the argument may draw on:\n"
        f"title: {json.dumps(corpus_title)}\n"
        f"why this sequence: {json.dumps(corpus_why)}\n"
        f"{json.dumps(_corpus_catalog(memory), indent=2)}\n\n"
        f"AVAILABLE ACTUATORS — choose only from these:\n"
        f"{json.dumps(_actuator_catalog(), indent=2)}\n\n"
        f"ARGUMENTATIVE FUNCTIONS:\n{json.dumps(FUNCTION_MEANING, indent=2)}\n\n"
        f"EPISTEMIC STATUSES a claim may aim at:\n{json.dumps(list(EPISTEMIC_STATUSES))}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"claims": [{{"claim": "<one sub-claim, one sentence>", '
        f'"target_status": "<one of the statuses>", '
        f'"note": "<why this sub-claim, one short clause>", '
        f'"percepts": [{{"actuator": "<name from the list>", "image": "<post_id from the '
        f'corpus>", "function": "support|complicate|challenge", "params": {{}}, '
        f'"note": "<why this percept carries this claim>"}}]}}]}}\n'
        f'Return {{"claims": []}} if this thesis cannot be argued with these actuators on these '
        f'images.'
    )


def _normalise_status(raw: Any) -> str:
    """A status outside the vocabulary becomes `interpretive` — the SAFE direction.

    Unlike a function (guard 6, passed through to be refused), an unknown status has no percept
    to refuse: it is an aspiration, not an instruction. Coercing it DOWN to interpretive can only
    make a claim look weaker than the model hoped, never stronger, and the achieved status is
    computed from what actually bound regardless.
    """
    text = str(raw or "").strip().lower()
    return text if text in EPISTEMIC_STATUSES else INTERPRETIVE


def parse_claims(payload: Any) -> Tuple[List[SubClaim], List[str]]:
    """Model JSON → SubClaims, plus notes about anything that had to be corrected.

    Tolerant of SHAPE, strict about CONTENT — the same split `parse_steps` makes. A missing note,
    params as a list, a claim with no percepts: all survivable. An invented actuator, an image the
    corpus does not hold, a function outside the vocabulary: all preserved verbatim, to be refused
    downstream by the gate rather than tidied away here.
    """
    notes: List[str] = []
    if not isinstance(payload, dict):
        return [], ["argument planner returned a non-object payload"]
    raw_claims = payload.get("claims")
    if raw_claims is None and isinstance(payload.get("sub_claims"), list):
        raw_claims = payload["sub_claims"]          # a common near-miss worth absorbing
    if not isinstance(raw_claims, list):
        return [], ["argument planner returned no 'claims' list"]

    claims: List[SubClaim] = []
    for ci, row in enumerate(raw_claims):
        if not isinstance(row, dict):
            notes.append(f"claim {ci} was not an object and was dropped")
            continue
        text = row.get("claim") or row.get("text")
        if not isinstance(text, str) or not text.strip():
            notes.append(f"claim {ci} carried no claim text and was dropped")
            continue
        claim_id = f"c{ci}"
        target = _normalise_status(row.get("target_status"))
        if row.get("target_status") and target != str(row.get("target_status")).strip().lower():
            notes.append(f"claim {ci} named an unknown target status "
                         f"'{row.get('target_status')}'; read as '{target}'")

        raw_percepts = row.get("percepts")
        if not isinstance(raw_percepts, list):
            raw_percepts = []
            notes.append(f"claim {ci} proposed no percepts")
        percepts: List[PerceptStep] = []
        for pi, praw in enumerate(raw_percepts):
            if not isinstance(praw, dict):
                notes.append(f"claim {ci} percept {pi} was not an object and was dropped")
                continue
            name = praw.get("actuator") or praw.get("name")
            if not isinstance(name, str) or not name.strip():
                notes.append(f"claim {ci} percept {pi} named no actuator and was dropped")
                continue
            name = name.strip()
            params, dropped = _clamp_params(name, praw.get("params"))
            if dropped:
                # Recorded, never silent: this is how you find out the model is trying to author
                # geometry, which is the failure that matters most and shows up nowhere else.
                notes.append(f"claim {ci} percept {pi} ('{name}') proposed disallowed params, "
                             f"dropped: {', '.join(dropped)}")
            image = praw.get("image") or praw.get("post_id") or praw.get("image_id")
            function = praw.get("function")
            function = function.strip().lower() if isinstance(function, str) else ""
            if function and function not in FUNCTIONS:
                # Guard 6 — kept verbatim so binding refuses the percept by name.
                notes.append(f"claim {ci} percept {pi} named an unknown function '{function}'; "
                             f"kept verbatim to be refused")
            pnote = praw.get("note")
            percepts.append(PerceptStep(
                step=Step(actuator=name, params=params,
                          id=f"{PLANNER_ARGUMENT_GROQ}:{claim_id}:{pi}:{name}",
                          note=str(pnote) if isinstance(pnote, str) else ""),
                function=function or "",
                target_status=target,
                image=str(image).strip() if isinstance(image, (str, int)) and
                str(image).strip() else None,
                note=str(pnote) if isinstance(pnote, str) else ""))

        if len(percepts) > MAX_PERCEPTS_PER_CLAIM:
            notes.append(f"claim {ci} proposed {len(percepts)} percepts; kept the first "
                         f"{MAX_PERCEPTS_PER_CLAIM}")
            percepts = percepts[:MAX_PERCEPTS_PER_CLAIM]

        note = row.get("note")
        claims.append(SubClaim(claim_id=claim_id, text=text.strip(),
                               percepts=tuple(percepts), target_status=target,
                               note=str(note) if isinstance(note, str) else ""))

    if len(claims) > MAX_CLAIMS:
        notes.append(f"argument planner proposed {len(claims)} claims; kept the first "
                     f"{MAX_CLAIMS}")
        claims = claims[:MAX_CLAIMS]

    if claims and not any(p.function == CHALLENGE for c in claims for p in c.percepts):
        # Reported here, REFUSED by `plan_argument`. Noting it at parse time means the absence is
        # visible even to a caller that only reads the planner's notes — but nothing is inserted.
        notes.append("the argument planner proposed no 'challenge' percept")
    return claims, notes


class GroqArgumentPlanner:
    """Groq decomposes the thesis. The binding still refuses what cannot be carried.

    `client` is injectable so the whole class is testable with no network — the tests pass a fake
    and never touch the API. Shaped like `GroqPlanner` on purpose: one method, `last_notes`, an
    observable `calls` counter that pins the no-loop guard.
    """
    name = PLANNER_ARGUMENT_GROQ

    def __init__(self, client: Any = None, *, model: str = DEFAULT_MODEL):
        self._client = client
        self._client_resolved = client is not None
        self.model = model
        self.last_notes: Tuple[str, ...] = ()
        self.calls: int = 0            # guard 3 is observable: tests assert this is 1

    # ── client ──
    def _get_client(self) -> Any:
        """Lazy real client. Absent key is UNAVAILABLE, not a crash."""
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
        return self._get_client() is not None

    # ── the seam ──
    def propose(self, thesis: str, memory: WorkingMemory) -> List[SubClaim]:
        """One call. No loop. No fallback — an unavailable planner proposes NOTHING and says so.

        The missing fallback is the deliberate part. `GroqPlanner` falls back to a keyword table
        because matching "trace the light" to a chain is something rules can do honestly. Nothing
        rule-based can decompose a thesis into sub-claims, so a fallback here would have to invent
        an argument, which is the one thing this module exists to prevent.
        """
        self.last_notes = ()
        client = self._get_client()
        if client is None:
            self.last_notes = (f"planner: {self.name}",
                               "argument planner unavailable (no client or API key); "
                               "no claims were proposed and none were invented")
            return []
        try:
            self.calls += 1
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": build_prompt(thesis, memory)}],
                model=self.model,
                response_format={"type": "json_object"},
            )
            payload = json.loads(completion.choices[0].message.content)
        except Exception as e:
            self.last_notes = (f"planner: {self.name}",
                               f"argument planner failed: {type(e).__name__}; "
                               f"no claims were proposed and none were invented")
            return []

        claims, notes = parse_claims(payload)
        if not claims:
            # An empty decomposition is a legitimate answer ("this thesis cannot be argued with
            # these actuators on these images"). It is NOT a failure and must not be repaired.
            self.last_notes = tuple([f"planner: {self.name}",
                                     "the argument planner proposed no claims", *notes])
            return []
        self.last_notes = tuple([f"planner: {self.name}", *notes])
        return claims


class RhetoricalDirector:
    """Thesis → decomposition → binding → ArgumentPlan. The Director's argument-level twin.

    Same asymmetry, one level up: the model gets to PROPOSE an argument. It does not get to decide
    whether a claim is carried — `plan_argument` runs every claim's percepts through the same
    `resolve()` that judges every other plan in the system.
    """

    def __init__(self, planner: Optional[Any] = None, *, require_challenge: bool = True):
        self.planner = planner if planner is not None else GroqArgumentPlanner()
        self.require_challenge = require_challenge

    def plan(self, thesis: str, memory: WorkingMemory):
        from .argument import plan_argument
        claims = self.planner.propose(thesis, memory)
        notes = tuple(str(n) for n in getattr(self.planner, "last_notes", ()) or ())
        return plan_argument(thesis, claims, memory,
                             planner=getattr(self.planner, "name", "unknown"),
                             notes=notes, require_challenge=self.require_challenge)
