"""
PERCEPTUAL-ORGANS-002 Lane F1 — the Perception Lab routes.

    GET   /capabilities                            organs, operations, adapter states
    GET   /sources                                 posts a session could be opened on
    GET   /sources/{post_id}                       one post as a lab source, with its digest
    POST  /sessions                                a post_id → a live session, immediately
    GET   /sessions                                the newest sittings, thin
    GET   /sessions/{sid}                          one sitting
    GET   /sessions/{sid}/history                  its plans, runs, artifacts and reviews
    PATCH /sessions/{sid}                          organ, mode, selection, active references
    POST  /sessions/{sid}/plans                    propose — Direct or Prompt
    POST  /sessions/{sid}/runs                     execute a resolved plan. The only door to an adapter
    POST  /sessions/{sid}/runs/cancel              pull a ticket, where the run is in this process
    POST  /sessions/{sid}/replays                  re-show a stored run. Nothing is called
    POST  /sessions/{sid}/reviews                  a person's verdict
    PATCH /sessions/{sid}/artifacts/{aid}/lifecycle   kept / rejected, inside the lab
    GET   /sessions/{sid}/export                   the canonical session bundle

PLAIN `def`, NOT `async def`, AND THAT IS THE ARCHITECTURE. The lab loads SAM and runs distance
transforms; the store is a synchronous `LabStore`. FastAPI runs a plain handler in its threadpool,
so a segmentation that takes four seconds never holds the event loop — the same reasoning
`routers/retina.py` states for LanceDB. The two handlers that must reach `motor` (opening a
session, listing sources) are `async def` and hand their result to a plain worker.

PLANNING AND RUNNING ARE TWO REQUESTS, and no route collapses them. `POST /plans` proposes,
resolves and stores something to LOOK at; `POST /runs` is a second, explicit act naming a plan id.
A single "do this" endpoint would delete the moment the whole laboratory is built around.

WHAT NO ROUTE HERE CAN DO. Write a post, a region, a mark, a Ground or a percept. There is no
import of `post_collection` for anything but READING a source, no promotion endpoint, and no
parameter anywhere that turns `kept` into canon. The source's fingerprint is taken before the run
and re-read during it, so "the post did not change" is a comparison this router performs.

EVERY BODY CARRIES `execution_identity`. It is read off the registry, so it says `LIVE` when the
lab is wired to real organs and `FIXTURE` when a test wired it to fakes, and neither the URL nor
this file gets a vote.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.perception_lab import (ExecutionIdentity, InputRef, LabSource,
                                            LifecycleState, OrganFamily, ReviewCorrection,
                                            ReviewVerdict, SessionMode)
from backend.services.perception_lab import derivations, live, producers, recipes
from backend.services.perception_lab import source as src
from backend.services.perception_lab.derivation_store import (DerivationStoreUnavailable,
                                                             MongoDerivationStore)
from backend.services.perception_lab.clock import SystemClock, UuidIds
from backend.services.perception_lab.mongo_store import LabStoreUnavailable, MongoLabStore
from backend.services.perception_lab.orchestrator import ConfirmationRequired, NothingToRun
from backend.services.perception_lab.planners import DirectCommand
from backend.services.perception_lab.resolver import IsolationBreach
from backend.services.perception_lab.session import SessionMachine

router = APIRouter()

#: Overridable in tests, and the ONLY seam that decides which world a request runs in. A test
#: replaces `_store` and `_open_source`; nothing else in this file knows a database exists.
_CLOCK = SystemClock()


def _derivation_store() -> MongoDerivationStore:
    """The sixth collection. A separate store because a derivation is not an artifact and the
    conductor must not be handed a door to it — see `derivation_store.py`."""
    return MongoDerivationStore()


def _store():
    return MongoLabStore()


async def _open_source(post_id: str) -> src.SourceSnapshot:
    return await src.open_source(post_id)


async def _list_sources(limit: int):
    return await src.list_sources(limit=limit)


def _conductor(snapshot: src.SourceSnapshot, store):
    return live.conductor_for(snapshot, store=store)


# ── bodies ───────────────────────────────────────────────────────────────────


class OpenSession(BaseModel):
    """A post, an organ, and a mode. Nothing about what to measure — that is a later request."""
    post_id: str = Field(..., description="an ordinary Semant post id; the lab creates none")
    selected_organ: str = OrganFamily.EXTENT.value
    mode: str = SessionMode.ISOLATION.value


class UpdateSession(BaseModel):
    """Every field is optional and `None` means UNTOUCHED, not cleared.

    Clearing the active artifact is its own boolean because `active_artifact_id: null` in JSON is
    indistinguishable from an absent key, and a person un-selecting "that mask" must not be
    silently ignored.
    """
    selected_organ: Optional[str] = None
    mode: Optional[str] = None
    selected_artifact_ids: Optional[List[str]] = None
    selected_instance_refs: Optional[List[Dict[str, str]]] = None
    active_artifact_id: Optional[str] = None
    active_region_ids: Optional[List[str]] = None
    clear_active: bool = False


class PlanCommand(BaseModel):
    operation: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    input_refs: List[Dict[str, Any]] = Field(default_factory=list)


class ProposePlan(BaseModel):
    """One arm, named. `direct` takes commands; `rules` and `model` take a sentence.

    The arms are separate fields rather than one polymorphic blob because the Direct arm exists to
    establish an organ WITHOUT testing language, and a shape that could carry a sentence into it is
    a shape somebody eventually puts a sentence in.
    """
    planner: str = "direct"
    prompt: Optional[str] = None
    commands: List[PlanCommand] = Field(default_factory=list)


class ExecutePlan(BaseModel):
    plan_id: str
    confirmed: bool = False
    #: The client's own id for the run it is about to start, so it has something to cancel by. The
    #: run's id is minted inside `execute` and does not exist when somebody wants to stop it.
    run_ticket: Optional[str] = None


class CancelRun(BaseModel):
    run_ticket: str
    reason: str = "cancelled by the person"


class Replay(BaseModel):
    run_id: str


class RunRecipe(BaseModel):
    """What a person supplies when they choose a study: the words and hands it asks them for.

    `bindings` FILLS ONLY WHAT THE RECIPE ASKED FOR. A concept is somebody's word and a drawn mask
    is their hand; `recipes.commands` refuses a binding for anything else, because a caller that
    can overwrite a fixed parameter can turn one study into another while it still reports the
    first study's name.
    """
    model_config = ConfigDict(extra="forbid")
    bindings: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class Derive(BaseModel):
    """One form, the artifacts it reads, and the decisions only a person can make."""
    model_config = ConfigDict(extra="forbid")
    form: str = Field(min_length=1)
    artifact_ids: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SubmitReview(BaseModel):
    artifact_id: str
    verdict: str
    reviewer: str = "person"
    notes: Optional[str] = None
    corrections: List[Dict[str, Any]] = Field(default_factory=list)


class SetLifecycle(BaseModel):
    status: str
    changed_by: str = "person"


# ── plumbing ─────────────────────────────────────────────────────────────────


def _envelope(body: Mapping[str, Any], identity: ExecutionIdentity) -> Dict[str, Any]:
    return {"execution_identity": identity.value, **dict(body)}


def _machine(store, session_id: str) -> SessionMachine:
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"error": "unknown_session",
                                                     "session_id": session_id})
    # WITH AN ID FACTORY, because a prompt turn is minted here. A machine without one raises
    # rather than inventing an id, which is the right failure and a terrible route.
    return SessionMachine(session, clock=_CLOCK, ids=UuidIds())


def _refs(raw: List[Dict[str, Any]]) -> List[InputRef]:
    """Client dicts → canonical `InputRef`s, validated HERE rather than deeper.

    A malformed ref is a 422 about the request, not an `unknown_reference` about the laboratory —
    they send a person to two different places, and the contract's refusal vocabulary is for the
    second.
    """
    out: List[InputRef] = []
    for item in raw:
        try:
            out.append(InputRef.model_validate(dict(item)))
        except Exception as exc:                           # noqa: BLE001 - pydantic
            raise HTTPException(status_code=422, detail={"error": "invalid_input_ref",
                                                         "ref": item, "why": str(exc)}) from exc
    return out


def _enum(kind, value: str, what: str):
    try:
        return kind(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "error": f"unknown_{what}", "value": value,
            "allowed": [m.value for m in kind]}) from exc


# ── the catalogue and the corpus ─────────────────────────────────────────────


#: A stand-in source for the catalogue's registry. The registry needs a runtime to build bridges
#: with, and the catalogue only ever asks those bridges `capability()` — which reads no image and
#: cannot: `LabRuntime.image_bytes` is empty here. `origin: fixture` rather than `post`, because
#: this names nothing in the corpus and a `post` origin with no post id is a lie the schema would
#: rightly refuse.
_CATALOGUE_SOURCE = LabSource(origin="fixture", image_digest="sha256:" + "0" * 64,
                              natural_width=1, natural_height=1)


@router.get("/capabilities")
def capabilities() -> Dict[str, Any]:
    """What this deployment can do, adapter by adapter. Never a guess — see `capability_catalogue`.

    Needs no session and touches no store: a person deciding whether to open the lab at all should
    not have to open it first.
    """
    registry = live.live_registry(live.LabRuntime(source=_CATALOGUE_SOURCE))
    return _envelope(live.capability_catalogue(registry), live.identity_of(registry))


# ── PERCEPTUAL-FORMS-001H: forms, recipes and derivations ────────────────────
#
# THREE LEVELS, THREE ROUTES, AND THE THIRD ALREADY EXISTED. A person may produce one form
# directly (`/derivations`), run a bounded study over several (`/recipes/{key}/plans`), or ask in
# words (`/plans`, unchanged). The prompt arm reaches the same resolver it always did and gains
# nothing here: a recipe it proposes is planned through the recipe route like any other, so
# "prompt may propose and never bypass" is a property of there being no fourth route rather than
# a rule the conductor follows.


@router.get("/forms")
def form_catalogue() -> Dict[str, Any]:
    """All nineteen forms, with who could write each one here and why nothing can.

    Needs no session, for the reason `/capabilities` needs none: a person deciding whether a form
    is worth opening should not have to open a session first. The states come from a live
    registry, so an adapter that is not running on THIS machine in THIS working directory is
    reported as it actually is.
    """
    registry = live.live_registry(live.LabRuntime(source=_CATALOGUE_SOURCE))
    states = dict(registry.capabilities())
    body = producers.catalogue(states=states)
    body["derivable"] = list(derivations.derivable_forms())
    return _envelope(body, live.identity_of(registry))


@router.get("/recipes")
def recipe_catalogue() -> Dict[str, Any]:
    """The seven deterministic studies, as declared. No session, no state, no readiness."""
    return _envelope({"recipes": [_recipe_json(r) for r in recipes.recipes().values()],
                      "stop_outcomes": list(recipes.stop_outcomes())},
                     ExecutionIdentity.LIVE)


def _recipe_json(recipe: Any) -> Dict[str, Any]:
    """One study, projected. Every field a surface needs and nothing it could execute from.

    THE STEPS ARE HERE AND THE COMMANDS ARE NOT. A surface draws the sequence; only
    `/recipes/{key}/plans` turns it into direct acts, through the same Direct planner and the same
    resolver a pressed control uses. A projection carrying ready-made commands would be a second
    place a study could be executed from.
    """
    return {
        "key": recipe.key, "label": recipe.label, "question": recipe.question,
        "organ": recipe.organ.value, "mode": recipe.mode.value,
        "required_forms": list(recipe.required_forms),
        "prerequisites": list(recipe.prerequisites),
        "bounds": dict(recipe.bounds),
        "expected_renderers": list(recipe.expected_renderers),
        "fixtures": list(recipe.fixtures),
        "asks_for": {k: list(v) for k, v in recipe.asks_for.items()},
        "steps": [{"id": s.id, "kind": s.kind, "why": s.why, "operation": s.operation,
                   "parameters": dict(s.parameters or {}), "produces": s.produces,
                   "reads": list(s.reads), "asks_for": list(s.asks_for)}
                  for s in recipe.steps],
        "stop_conditions": [{"when": c.when, "outcome": c.outcome, "reason": c.reason}
                            for c in recipe.stop_conditions],
        "decision_points": [{"at": d.at, "asks": d.asks, "why_a_person": d.why_a_person,
                             "options": list(d.options)} for d in recipe.decision_points],
    }


@router.get("/sessions/{session_id}/recipes/{key}/readiness")
def recipe_readiness(session_id: str, key: str) -> Dict[str, Any]:
    """Every reason this study cannot run here, gathered BEFORE anything is planned.

    Four of the seven cannot write their final record today. A runtime that discovered that at the
    last step would have spent every model call first.
    """
    store = _guarded(_store)
    machine = _machine(store, session_id)
    try:
        recipe = recipes.recipe(key)
    except recipes.RecipeError as exc:
        raise HTTPException(status_code=404, detail={"error": "unknown_recipe",
                                                     "why": str(exc)}) from exc
    registry = live.live_registry(live.LabRuntime(source=machine.session.source))
    readiness = recipes.check(recipe, machine.view(), capabilities=dict(registry.capabilities()))
    return _envelope({
        "recipe": recipe.key, "ready": readiness.ready,
        "reasons": list(readiness.reasons),
        "unproducible_forms": list(readiness.unproducible_forms),
        "unavailable_operations": list(readiness.unavailable_operations),
        "mode_conflict": readiness.mode_conflict,
    }, live.identity_of(registry))


@router.post("/sessions/{session_id}/recipes/{key}/plans", status_code=201)
async def plan_recipe(session_id: str, key: str, body: RunRecipe) -> Dict[str, Any]:
    """A study, expanded into direct acts and put through the same resolver as a pressed control.

    NOTHING RUNS HERE. The plan comes back for a person to look at, and a chain study comes back
    with `requires_confirmation` set, exactly as a hand-composed chain does.
    """
    store = _guarded(_store)
    machine = _machine(store, session_id)
    try:
        recipe = recipes.recipe(key)
    except recipes.RecipeError as exc:
        raise HTTPException(status_code=404, detail={"error": "unknown_recipe",
                                                     "why": str(exc)}) from exc
    snapshot = await _resolve(str(machine.session.source.post_id))

    def _plan() -> Dict[str, Any]:
        conductor = _conductor(snapshot, store)
        identity = live.identity_of(conductor.registry)
        try:
            commands = recipes.commands(recipe, machine.view(), body.bindings)
        except recipes.RecipeError as exc:
            raise HTTPException(status_code=422, detail={
                "error": "invalid_binding", "recipe": recipe.key, "why": str(exc)}) from exc
        resolution = conductor.plan_direct(machine, *commands)
        _guarded(store.put_session, machine.session)
        return _envelope({"plan": live.record_json(resolution.plan),
                          "recipe": _recipe_json(recipe),
                          "derivations": [{"id": s.id, "produces": s.produces,
                                           "reads": list(s.reads), "why": s.why}
                                          for s in recipes.derivations(recipe)],
                          "notes": list(resolution.notes),
                          "authorized": resolution.authorized,
                          "session": live.session_json(machine.session)}, identity)

    return await run_in_threadpool(_plan)


@router.post("/sessions/{session_id}/derivations", status_code=201)
def create_derivation(session_id: str, body: Derive) -> Dict[str, Any]:
    """Compute one form from artifacts this session already holds. REACHES NO ADAPTER.

    A derivation is not a run: nothing is invoked, no image is opened and no model is loaded, so
    there is no stage attempt to record and no wall clock worth reporting as a measurement. What
    comes back is the payload, the producibility verdict, the ceiling and every omission — and a
    record that has nowhere to be promoted to.
    """
    store = _guarded(_store)
    machine = _machine(store, session_id)
    held = {a.identity.artifact_id: a for a in _guarded(store.artifacts_for_session, session_id)}
    missing = [a for a in body.artifact_ids if a not in held]
    if missing:
        raise HTTPException(status_code=404, detail={
            "error": "unknown_artifact", "artifact_ids": missing,
            "why": "a derivation reads artifacts this session recorded, and never fetches one"})
    supplied = [held[a] for a in body.artifact_ids]
    try:
        record = derivations.derive(
            body.form, session_id=session_id, artifacts=supplied,
            parameters=dict(body.parameters or {}),
            source_image_digest=machine.session.source.image_digest,
            derivation_id=f"der_{uuid4().hex[:12]}",
            now=datetime.now(timezone.utc).isoformat())
    except derivations.DerivationRefused as refused:
        # A REFUSAL IS A 201 WITH THE REFUSAL IN IT, the same ruling `/plans` makes. The refusal is
        # the answer — which input did not resolve and what would satisfy it — and a 4xx would
        # leave a client with a status code where the laboratory's reply should be.
        return _envelope({"derivation": None,
                          "refusals": [refused.refusal.model_dump(mode="json")]},
                         ExecutionIdentity.LIVE)
    _guarded(_derivation_store().put, record)
    return _envelope({"derivation": record.model_dump(mode="json"), "refusals": []},
                     ExecutionIdentity.LIVE)


@router.get("/sessions/{session_id}/derivations")
def list_derivations(session_id: str) -> Dict[str, Any]:
    """Every form derived in this session, in the order they were computed."""
    store = _guarded(_store)
    _machine(store, session_id)
    found = _guarded(_derivation_store().for_session, session_id)
    return _envelope({"derivations": [d.model_dump(mode="json") for d in found]},
                     ExecutionIdentity.LIVE)


@router.get("/sources")
async def sources(limit: int = 30) -> Dict[str, Any]:
    """Posts a lab session could be opened on. `image_digest: null` — nobody has looked yet."""
    found = await _list_sources(max(1, min(int(limit), 100)))
    return _envelope({"sources": found}, ExecutionIdentity.LIVE)


@router.get("/sources/{post_id}")
async def source_detail(post_id: str) -> Dict[str, Any]:
    """One post as a lab source, with the digest and raster a session would run on."""
    snapshot = await _resolve(post_id)
    return _envelope({"source": snapshot.as_client_source()}, ExecutionIdentity.LIVE)


async def _resolve(post_id: str) -> src.SourceSnapshot:
    try:
        return await _open_source(post_id)
    except src.UnknownPost as exc:
        raise HTTPException(status_code=404,
                            detail={"error": "unknown_post", "post_id": post_id}) from exc
    except src.SourceUnavailable as exc:
        raise HTTPException(status_code=503, detail={"error": "source_unavailable",
                                                     "post_id": post_id,
                                                     "why": str(exc)}) from exc


# ── sessions ─────────────────────────────────────────────────────────────────


@router.post("/sessions", status_code=201)
async def open_session(body: OpenSession) -> Dict[str, Any]:
    """A post id → a durable session, with the real source in the FIRST response.

    The digest, the raster and the region count are in the body before anything else happens,
    because a laboratory whose first screen says "loading" cannot be told apart from one that has
    not read the picture at all.
    """
    organ = _enum(OrganFamily, body.selected_organ, "organ")
    mode = _enum(SessionMode, body.mode, "mode")
    snapshot = await _resolve(body.post_id)

    def _open() -> Dict[str, Any]:
        store = _store()
        conductor = _conductor(snapshot, store)
        machine = conductor.open_session(source=snapshot.source, organ=organ, mode=mode)
        return _envelope({"session": live.session_json(machine.session),
                          "source": snapshot.as_client_source()},
                         live.identity_of(conductor.registry))

    return await run_in_threadpool(_guarded, _open)


@router.get("/sessions")
def list_sessions(limit: int = 20) -> Dict[str, Any]:
    """The newest sittings, thin. Enough to re-open one, not enough to render it."""
    store = _guarded(_store)
    rows = [{"session_id": s.session_id, "post_id": s.source.post_id,
             "selected_organ": s.selected_organ.value, "mode": s.mode.value,
             "runs": len(s.run_ids), "reviews": len(s.review_ids),
             "created_at": s.created_at, "updated_at": s.updated_at}
            for s in _guarded(store.sessions)]
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return _envelope({"sessions": rows[:max(1, min(int(limit), 100))]}, ExecutionIdentity.LIVE)


@router.get("/sessions/{session_id}")
def read_session(session_id: str) -> Dict[str, Any]:
    store = _guarded(_store)
    machine = _machine(store, session_id)
    return _envelope({"session": live.session_json(machine.session)}, ExecutionIdentity.LIVE)


@router.get("/sessions/{session_id}/history")
def read_history(session_id: str) -> Dict[str, Any]:
    """The sitting's whole ledger. What re-opening a session restores."""
    store = _guarded(_store)
    machine = _machine(store, session_id)
    return _envelope(live.history_json(store, machine.session), ExecutionIdentity.LIVE)


@router.patch("/sessions/{session_id}")
def update_session(session_id: str, body: UpdateSession) -> Dict[str, Any]:
    """Organ, mode, selection, active references — through `SessionMachine`, never by assignment.

    The machine owns the invariants the follow-up law rests on: deselecting an artifact drops the
    instances inside it and clears it from `active`. A route that wrote the fields directly would
    let a person's deselection be recorded and disobeyed.
    """
    store = _guarded(_store)
    machine = _machine(store, session_id)
    if body.selected_organ is not None:
        _enum(OrganFamily, body.selected_organ, "organ")
    if body.mode is not None:
        _enum(SessionMode, body.mode, "mode")
    try:
        live.apply_selection(
            machine, organ=body.selected_organ, mode=body.mode,
            selected_artifact_ids=body.selected_artifact_ids,
            active_artifact_id=body.active_artifact_id,
            selected_instance_refs=body.selected_instance_refs,
            active_region_ids=body.active_region_ids, clear_active=body.clear_active)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_selection",
                                                     "why": str(exc)}) from exc
    _guarded(store.put_session, machine.session)
    return _envelope({"session": live.session_json(machine.session)}, ExecutionIdentity.LIVE)


# ── planning ─────────────────────────────────────────────────────────────────


@router.post("/sessions/{session_id}/plans", status_code=201)
async def propose_plan(session_id: str, body: ProposePlan) -> Dict[str, Any]:
    """Propose, resolve, store, return. NOTHING RUNS HERE and no adapter is reached.

    A plan carrying only refusals is a 201 with the refusals in it, not a 4xx. The refusals are the
    answer — which law said no and what would satisfy it — and an error status would leave a client
    with a status code where the laboratory's reply should be.
    """
    store = _guarded(_store)
    machine = _machine(store, session_id)
    snapshot = await _resolve(str(machine.session.source.post_id))

    def _plan() -> Dict[str, Any]:
        conductor = _conductor(snapshot, store)
        identity = live.identity_of(conductor.registry)
        try:
            if body.planner == "direct":
                commands = [DirectCommand(operation=c.operation, parameters=dict(c.parameters),
                                          input_refs=tuple(_refs(c.input_refs)))
                            for c in body.commands]
                if not commands:
                    raise HTTPException(status_code=422, detail={
                        "error": "no_command",
                        "why": "the Direct arm is a control press; it needs at least one"})
                resolution = conductor.plan_direct(machine, *commands)
            else:
                if not (body.prompt or "").strip():
                    raise HTTPException(status_code=422, detail={
                        "error": "no_prompt", "why": f"the {body.planner} arm reads a sentence"})
                resolution = conductor.plan_prompt(machine, body.prompt, planner=body.planner)
        except KeyError as exc:
            raise HTTPException(status_code=422, detail={"error": "unknown_planner",
                                                         "why": str(exc)}) from exc
        except IsolationBreach as exc:
            # NOT a refusal and not a 422. The resolver authorized outside the locked organ, which
            # is the laboratory failing at its own job; a person cannot fix it and there is no
            # message worth showing them.
            raise HTTPException(status_code=500, detail={"error": "isolation_breach",
                                                         "why": str(exc)}) from exc
        _guarded(store.put_session, machine.session)
        return _envelope({"plan": live.record_json(resolution.plan),
                          "notes": list(resolution.notes),
                          "authorized": resolution.authorized,
                          "session": live.session_json(machine.session)}, identity)

    return await run_in_threadpool(_plan)


# ── running ──────────────────────────────────────────────────────────────────


@router.post("/sessions/{session_id}/runs", status_code=201)
async def execute_plan(session_id: str, body: ExecutePlan) -> Dict[str, Any]:
    """Run an authorized plan. THE ONLY ROUTE IN THIS FILE THAT REACHES AN ADAPTER.

    A run that refused, found nothing or could not reach its adapter is a 201 with the outcome in
    it: `refused`, `empty` and `unavailable` are three answers, and an HTTP error code for any of
    them would collapse them into one.
    """
    store = _guarded(_store)
    machine = _machine(store, session_id)
    plan = _guarded(store.get_plan, body.plan_id)
    if plan is None or plan.session_id != session_id:
        raise HTTPException(status_code=404, detail={"error": "unknown_plan",
                                                     "plan_id": body.plan_id})
    snapshot = await _resolve(str(machine.session.source.post_id))

    def _run() -> Dict[str, Any]:
        conductor = _conductor(snapshot, store)
        identity = live.identity_of(conductor.registry)
        token = live.CANCELS.open(body.run_ticket)
        try:
            execution = conductor.execute(machine, plan, confirmed=body.confirmed, cancel=token)
        except ConfirmationRequired as exc:
            # 409, not 422. The request was well formed; the plan carries a decision a person has
            # to make, and the client's job is to ask them and send it again with `confirmed`.
            raise HTTPException(status_code=409, detail={
                "error": "confirmation_required", "plan_id": plan.plan_id,
                "prerequisites": list(plan.prerequisites), "why": str(exc)}) from exc
        except NothingToRun as exc:
            raise HTTPException(status_code=422, detail={"error": "nothing_to_run",
                                                         "plan_id": plan.plan_id,
                                                         "why": str(exc)}) from exc
        finally:
            live.CANCELS.close(body.run_ticket)
        body_out = live.execution_json(execution)
        body_out["session"] = live.session_json(machine.session)
        body_out["source_unchanged"] = (
            execution.run.source_digest_after == execution.run.source_digest_before)
        return _envelope(body_out, identity)

    return await run_in_threadpool(_run)


@router.post("/sessions/{session_id}/runs/cancel")
def cancel_run(session_id: str, body: CancelRun) -> Dict[str, Any]:
    """Pull a ticket. HONEST ABOUT ITS REACH: `cancelled: false` means no run of that ticket is
    in flight in THIS process, which is a different sentence from "the run has stopped".

    Cancellation is cooperative all the way down — nothing can interrupt a model mid-forward-pass.
    What the laboratory guarantees is that no FURTHER stage is invoked once the flag is set, and
    the run records which stages were skipped and why.
    """
    reached = live.CANCELS.cancel(body.run_ticket, body.reason)
    return _envelope({"cancelled": reached, "run_ticket": body.run_ticket,
                      "note": ("no run with that ticket is in flight in this process. A run on "
                               "another worker cannot be reached from here, and saying so is the "
                               "only honest answer.") if not reached else None},
                     ExecutionIdentity.LIVE)


@router.post("/sessions/{session_id}/replays", status_code=201)
def replay_run(session_id: str, body: Replay) -> Dict[str, Any]:
    """Re-show a stored run. NO REGISTRY IS BUILT AND NO SOURCE IS FETCHED.

    The conductor here is constructed with a SEALED registry rather than the live one, so the
    structural guard Lane D wrote holds at the route as well: there is nothing in reach of this
    handler that could invoke an adapter, and the returned run is `REPLAY` with every `invoked`
    false.
    """
    from backend.services.perception_lab.orchestrator import PerceptionConductor
    from backend.services.perception_lab.replay import SealedAdapterRegistry

    store = _guarded(_store)
    machine = _machine(store, session_id)
    conductor = PerceptionConductor(store=store, registry=SealedAdapterRegistry(), clock=_CLOCK)
    execution = conductor.replay(machine, body.run_id)
    return _envelope(live.execution_json(execution), ExecutionIdentity.REPLAY)


# ── a person's verdict, and the lab's own curation ───────────────────────────


@router.post("/sessions/{session_id}/reviews", status_code=201)
def submit_review(session_id: str, body: SubmitReview) -> Dict[str, Any]:
    """What a person thought. IT CHANGES NO LIFECYCLE AND NO EPISTEMIC STATUS.

    Saying `correct` does not make a box-basis containment `measured` and does not make the
    artifact `kept`. Three decisions, three deciders, and this route makes exactly one of them.
    """
    store = _guarded(_store)
    machine = _machine(store, session_id)
    verdict = _enum(ReviewVerdict, body.verdict, "verdict")
    try:
        corrections = [ReviewCorrection.model_validate(dict(c)) for c in body.corrections]
    except Exception as exc:                               # noqa: BLE001 - pydantic
        raise HTTPException(status_code=422, detail={"error": "invalid_correction",
                                                     "why": str(exc)}) from exc
    from backend.services.perception_lab.orchestrator import PerceptionConductor
    conductor = PerceptionConductor(store=store, clock=_CLOCK)
    try:
        review = conductor.review(machine, body.artifact_id, reviewer=body.reviewer,
                                  verdict=verdict, notes=body.notes, corrections=corrections)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": "unknown_artifact",
                                                     "artifact_id": body.artifact_id}) from exc
    return _envelope({"review": live.record_json(review),
                      "session": live.session_json(machine.session)}, ExecutionIdentity.LIVE)


@router.patch("/sessions/{session_id}/artifacts/{artifact_id}/lifecycle")
def set_lifecycle(session_id: str, artifact_id: str, body: SetLifecycle) -> Dict[str, Any]:
    """`kept` or `rejected`, inside the laboratory's own ledger. NOT PROMOTION.

    `promoted` is refused with a 422 that says why: promotion is a separate confirmed act with
    revision checks, and it is not implemented in this lane. A lifecycle endpoint that reached it
    would be that act wearing a smaller name.
    """
    store = _guarded(_store)
    _machine(store, session_id)
    status = _enum(LifecycleState, body.status, "lifecycle_state")
    try:
        artifact = live.set_lifecycle(store, artifact_id, status,
                                      changed_by=body.changed_by, at=_CLOCK.now_iso())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "promotion_is_not_a_lifecycle_edit",
                                                     "why": str(exc)}) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": "unknown_artifact",
                                                     "artifact_id": artifact_id}) from exc
    return _envelope({"artifact": live.record_json(artifact)}, ExecutionIdentity.LIVE)


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str) -> Dict[str, Any]:
    """The canonical bundle: the five record types, as they are held. A copy, never a promotion."""
    store = _guarded(_store)
    machine = _machine(store, session_id)
    return live.export_json(store, machine.session, identity=ExecutionIdentity.LIVE)


# ── the one failure mode every handler shares ────────────────────────────────


def _guarded(call, *args):
    """Store failures become 503, and are never swallowed.

    The lab's store is not write-behind observability: a session that reports itself saved and is
    not would send a person back to a laboratory that has forgotten them.
    """
    try:
        return call(*args)
    except (LabStoreUnavailable, DerivationStoreUnavailable) as exc:
        raise HTTPException(status_code=503, detail={"error": "lab_store_unavailable",
                                                     "why": str(exc)}) from exc
