"""
CIRCUIT-002 SURFACE-002 — the corpus run surface: (images + a prompt) → a whole run.

SURFACE-001 exposed ONE image, ONE Director pass, ONE plan. This is the keystone that makes the
engine user-drivable: a set of images and a sentence go in; the multi-round loop runs over the
corpus; and what comes back is the produced evidence, the article when the prompt is an argument,
and a full per-actuator PRODUCTION RECORD of what actually happened.

THE GOVERNING PRINCIPLE — ANNOTATION-INDEPENDENT. A run needs raw images and a prompt. Nothing
else. Working memory is hydrated from `photo_url`, never from `region_annotations`: the actuators
PRODUCE every region, mark, ground and percept from pixels, and the prompt carries the intent.
Filled annotations, where a curator has made some, are folded in as extra memory — they are a
head start, never a precondition. A post with zero annotations must produce a full run, and that
is a test (`test_run_surface.py`), not an aspiration. The failure it prevents is a demo that only
works on the three posts somebody prepared by hand.

WHAT THIS MODULE IS NOT. It is not a second engine. Every decision that matters already belongs to
something else and is called, not reimplemented:

    what to do next          `loop_controller.run_loop` (A1/A2/A2-EXT/A3)
    what may run at all      `corpus.resolve_corpus` → `plan.resolve`
    where a step runs        `corpus_execution.routed_registry`
    what a claim may say     `argument` / `composition` / `article_resolver` (M2–M6)
    how an item is known     `epistemics` (M5/M6)

What is genuinely new here is the ASSEMBLY — the RunView envelope, and the ProductionRecord that
widens PROV-001's typed provenance into a manifest a reader can audit step by step.

TWO SEAMS THIS GATE ADDED, both upstream and both small: `run_loop(resolve_fn=…)`, so a corpus
run resolves per-image without the loop learning what a corpus is; and `latency_ms` on
`StepRecord`, because a production record that cannot say how long a model took is not a manifest.

SUGGESTIONS-ONLY, like everything below it. A run accumulates quarantined descriptors in the
execution context. It never accepts a mark and never writes a post — pinned by hashing every post
document before and after.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import corpus as corpus_mod
from . import loop_controller as lc
from .capabilities import is_comparative
from .corpus import (Corpus, CorpusWorkingMemory, build_corpus, hydrate_corpus,
                     resolve_corpus)
from .corpus_execution import (CorpusExecutionContext, build_corpus_context,
                               routed_registry)
from .plan import Step
from .planner import Director
from .questions import Proposal, Question

# ── the two modes ────────────────────────────────────────────────────────────
# EXPLORE looks and reports what it found. ARGUE additionally puts the prompt to the argument
# machinery (M2–M6) and returns a drafted article. The mode changes what is COMPOSED from a run;
# it never changes what the actuators are allowed to produce or claim.
MODE_EXPLORE = "explore"
MODE_ARGUE = "argue"
MODES = (MODE_EXPLORE, MODE_ARGUE)

# ── run lifecycle ────────────────────────────────────────────────────────────
# pending → running → (awaiting_answer ⇄ running) → complete | stopped
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_AWAITING_ANSWER = "awaiting_answer"
STATUS_COMPLETE = "complete"
STATUS_STOPPED = "stopped"

#: Loop stop reasons that mean "this run finished the work it could do" rather than "it hit a
#: wall". Everything else is `stopped` and keeps its honest reason on the receipt.
_COMPLETE_REASONS = (lc.STOP_FIXED_POINT, lc.STOP_NO_NEW_EVIDENCE)


@dataclass(frozen=True)
class RunSpec:
    """What the curator asked for. The prompt is the intention and is fixed for the life of the
    run — the loop re-plans on evolved memory, never on a reworded prompt (A1's boundary)."""
    prompt: str
    image_ids: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    mode: str = MODE_EXPLORE

    @classmethod
    def of(cls, *, prompt: str, image_ids: Sequence[str] = (), tags: Sequence[str] = (),
           mode: str = MODE_EXPLORE) -> "RunSpec":
        return cls(prompt=str(prompt or "").strip(),
                   image_ids=tuple(str(i) for i in (image_ids or ())),
                   tags=tuple(str(t) for t in (tags or ())),
                   mode=mode if mode in MODES else MODE_EXPLORE)

    def to_dict(self) -> Dict[str, Any]:
        return {"prompt": self.prompt, "image_ids": list(self.image_ids),
                "tags": list(self.tags), "mode": self.mode}


# ── corpus assembly, from raw posts ──────────────────────────────────────────

def corpus_from_posts(posts: Sequence[Mapping[str, Any]], *, corpus_id: str,
                      title: str = "", why: str = "") -> Corpus:
    """Post documents → an M1 corpus of RAW images, in the given order.

    `image_ref` is the photo url and nothing else. This is the annotation-independence rule at its
    source: what makes a post part of a run is that it HAS a picture.
    """
    return build_corpus(
        corpus_id=corpus_id, title=title, why=why,
        images=[{"post_id": str(p.get("_id") or p.get("id") or ""),
                 "photo_url": str(p.get("photo_url") or ""),
                 "title": str(p.get("title") or "")} for p in posts])


def hydrate_run_memory(corpus: Corpus, posts: Mapping[str, Mapping[str, Any]], *,
                       phrase: Optional[str] = None) -> CorpusWorkingMemory:
    """The packet the run starts from.

    Delegates to M1's `hydrate_corpus`, which reads whatever committed evidence each post happens
    to carry and records an unreadable post as unreadable rather than as an empty one. A post with
    no annotations yields an empty packet with its image — which is exactly a full, legitimate
    starting point, because the actuators are what produce evidence.
    """
    return hydrate_corpus(corpus, posts, phrase=phrase)


# ── planning across a corpus: fan out, then resolve per image ────────────────

class FanOutPlanner:
    """Wraps any planner so a single-image step is asked of EVERY image in the corpus.

    A DECISION, and it belongs to the run surface rather than to the planner or the resolver. Left
    alone, `resolve_corpus` defaults an untargeted step to the corpus's FOCUS image — correct for a
    plan a curator wrote (an untargeted step means "the one I'm looking at"), and wrong for a run
    whose whole premise is a SET of images: the curator asked about five photographs and would get
    a run that only ever looked at the first.

    Fanning out here, rather than in the resolver, keeps that judgement visible and reversible, and
    leaves `resolve_corpus`'s semantics untouched for every existing caller.

    Comparative actuators are NOT fanned out: their job is to see across images, so they are
    corpus-level by definition and pinning one to an image is refused upstream.

    The stamped `image` param is also what keeps A1-FIX honest across a corpus. A step's signature
    is its actuator plus its params, so a step that gains its image at RESOLVE time would have one
    identity when the planner proposed it and another once the gate had seen it — and the loop's
    closed-door suppression, which matches on that signature, would never recognise a refused step
    coming back. Stamping before the loop sees the step keeps the two identities the same one.
    """
    name = "fan_out"

    def __init__(self, inner: Any, corpus: Corpus):
        self.inner = inner
        self.corpus = corpus
        self.name = f"fan_out({getattr(inner, 'name', 'planner')})"

    @property
    def last_notes(self) -> Tuple[str, ...]:
        return tuple(getattr(self.inner, "last_notes", ()) or ())

    def propose(self, intention: str, memory: Any) -> Proposal:
        proposal = Proposal.of(self.inner.propose(intention, memory))
        images = self.corpus.images
        if not images:
            return proposal
        out: List[Step] = []
        for step in proposal.steps:
            if is_comparative(step.actuator):
                out.append(step)
                continue
            target = corpus_mod.image_target(step)
            if target not in (None, ""):
                out.append(step)                      # the planner named an image; respect it
                continue
            for image in images:
                params = dict(step.params or {})
                params[corpus_mod.IMAGE_PARAM] = image.post_id
                base = step.id or f"{step.actuator}"
                out.append(Step(actuator=step.actuator, params=params,
                                id=f"{base}@{image.post_id}", note=step.note))
        return Proposal(steps=out, question=proposal.question)


class CorpusResolver:
    """The gate a corpus run resolves through, and the bookkeeping that keeps it truthful.

    `resolve_corpus` judges each image against ITS OWN packet — the whole reason a field is not
    planned on the colonnade because the rotunda had a region. But the loop carries ONE merged
    packet forward, and `execute()` advances it with projected ids (`step#kind@n`) that name a step
    rather than an image. Across rounds, that leaves the per-image packets frozen at hydration:
    round 2 would refuse a step needing the region round 1 actually produced.

    So this reconciles before every resolve: each projected id is attributed to the image whose
    step minted it (recorded from the plans this resolver itself returned), the per-image packets
    are advanced, and the merged view is rebuilt from them. Nothing is invented — the totals are
    the loop's own, only their ORIGIN is restored — and `execute()` re-checks against the same
    merged counts either way.
    """

    def __init__(self, corpus: Corpus, base: CorpusWorkingMemory):
        self.corpus = corpus
        self.base = base
        self.per_image: Dict[str, Any] = dict(base.per_image)
        self.origins: Dict[str, str] = dict(base.origins)
        self.image_of: Dict[str, str] = {}          # step id → the image it ran on
        self._seen: set = set()                     # projected ids already attributed

    # -- bookkeeping ------------------------------------------------------
    def note_steps(self, steps: Sequence[Step]) -> None:
        for step in steps:
            target = corpus_mod.image_target(step)
            if target not in (None, "") and step.id:
                self.image_of[str(step.id)] = str(target)

    def _focus(self) -> str:
        return self.base.focus_post_id or (self.corpus.images[0].post_id
                                           if self.corpus.images else "")

    def _image_for_projected(self, projected_id: str) -> str:
        """Which image minted this id. `step#kind@n` — the step is the key, and the step's image
        was recorded when this resolver planned it. An id whose step is unknown (a plan that came
        from somewhere else) is attributed to the focus image, which is where an untargeted step
        would have run."""
        step_id = projected_id.split("#", 1)[0]
        return self.image_of.get(step_id) or self._focus()

    def reconcile(self, memory: Any) -> CorpusWorkingMemory:
        """Give the loop's merged packet its per-image origins back."""
        # The curator's WORDS belong to every image in the run, and must reach the per-image
        # packets — `resolve_corpus` judges a single-image step against ITS packet, so a phrase
        # that lived only on the merged view would leave an answered door still shut. This is
        # exactly what `hydrate_corpus(phrase=…)` does at the start of a run; A3's answer arrives
        # later and has to travel the same road.
        phrase = getattr(memory, "phrase", None)
        attention = getattr(memory, "first_attention", None)
        source = getattr(memory, "phrase_source", None)
        for post_id, packet in list(self.per_image.items()):
            if (packet.phrase, packet.first_attention, packet.phrase_source) != \
                    (phrase, attention, source):
                self.per_image[post_id] = replace(
                    packet, phrase=phrase, first_attention=attention, phrase_source=source)

        buckets = (("region_ids", "region_ids"), ("mark_ids", "mark_ids"),
                   ("ground_ids", "ground_ids"), ("percept_ids", "percept_ids"))
        for attr, _ in buckets:
            for ref in getattr(memory, attr, ()):
                if ref in self._seen or corpus_mod.ORIGIN_SEP in ref:
                    continue                        # hydrated ids already carry their origin
                self._seen.add(ref)
                post_id = self._image_for_projected(ref)
                packet = self.per_image.get(post_id)
                if packet is None:
                    continue
                self.per_image[post_id] = replace(
                    packet, **{attr: tuple([*getattr(packet, attr), ref])})
                self.origins[ref] = post_id
        merged = corpus_mod.merge_memories(
            self.corpus, self.per_image, focus_post_id=self.base.focus_post_id,
            phrase=getattr(memory, "phrase", None), origins=self.origins)
        # `merge_memories` speaks in ids; the curator's own words and where they came from ride
        # along on the packet and must survive a rebuild, or A3's answer would be lost between
        # rounds and its attribution with it.
        return replace(merged, first_attention=getattr(memory, "first_attention", None),
                       phrase_source=getattr(memory, "phrase_source", None),
                       unreadable=tuple(getattr(memory, "unreadable", ()) or merged.unreadable))

    # -- the resolver the loop calls --------------------------------------
    def __call__(self, steps: Sequence[Step], memory: Any, **kwargs: Any):
        merged = self.reconcile(memory)
        plan = resolve_corpus(list(steps), merged, **kwargs)
        self.note_steps(plan.steps)
        self.note_steps([r.step for r in plan.refused])
        return plan


# ── the production record ────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProductionRecord:
    """One executed step, told in full: what it was called with, what ran, what it read, what it
    minted, and how long it took.

    PROV-001 made every suggestion say WHICH RUN and WHICH STEP made it. This is the other half of
    that join, read from the step's side, and it is the transparency the demo turns on: a reader
    can go actuator by actuator and see the model, the params, the epistemic status of each item
    produced, and — where a step did not run — the refusal in the closed vocabulary rather than a
    silence.

    UNKNOWN IS `None`, NEVER A GUESS. A step that never reached a dispatch has no latency; a
    deterministic geometry operator has no model; a quarantined suggestion has no id until someone
    accepts it. Each of those is written as null, because a plausible zero would be a claim.
    """
    step_id: str
    actuator: str
    status: str
    params: Dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    adapter: Optional[str] = None
    image: Optional[str] = None                  # which corpus image the step ran on
    round_index: int = 0
    consumed: Tuple[str, ...] = ()
    produced: Tuple[Dict[str, Any], ...] = ()
    refusal: Optional[Dict[str, str]] = None
    latency_ms: Optional[float] = None
    confidence: Optional[float] = None
    detail: str = ""
    # The COUNTS the step was handed, kept beside `consumed` rather than folded into it: what a
    # step could see and what it demonstrably read are different facts, and a list that quietly
    # meant the first would overstate every record on this page.
    inputs_used: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "actuator": self.actuator, "status": self.status,
                "params": dict(self.params), "model": self.model, "adapter": self.adapter,
                "image": self.image, "round": self.round_index,
                "consumed": list(self.consumed),
                "produced": [dict(p) for p in self.produced],
                "refusal": dict(self.refusal) if self.refusal else None,
                "latency_ms": self.latency_ms, "confidence": self.confidence,
                "detail": self.detail, "inputs_used": dict(self.inputs_used)}


def _suggestion_ref(sug: Mapping[str, Any], run_id: str, step_id: str, n: int) -> Dict[str, Any]:
    """One produced item, as the record reports it.

    `id` is the descriptor's own id where it has one and null where it does not — a quarantined
    suggestion is not a stored record and has no id until it is accepted, and minting one here
    would dress a proposal as a thing. `ref` is a run-local handle so a reader (and a UI) can point
    at the item without that becoming a claim about persistence.
    """
    return {"id": sug.get("id"),
            "ref": f"{run_id}:{step_id}#{n}",
            "kind": sug.get("type") or sug.get("role"),
            "producer": sug.get("producer"),
            "epistemic_status": sug.get("epistemic_status"),
            "confidence": sug.get("confidence")}


def _consumed_ids(params: Mapping[str, Any], produced: Sequence[Mapping[str, Any]]) -> Tuple[str, ...]:
    """The evidence ids this step DEMONSTRABLY read.

    Two sources, both facts rather than inferences: ids the step was explicitly called with, and
    the source a produced descriptor names for itself. A step that read something no one recorded
    contributes nothing here — which is why `inputs_used` sits beside this field carrying what the
    step could see. Guessing the difference is the one thing a manifest may not do.
    """
    out: List[str] = []
    for key in ("region_id", "mark_id", "ground_id", "percept_id", "target"):
        value = params.get(key)
        if isinstance(value, str) and value:
            out.append(value)
        elif isinstance(value, (list, tuple)):
            out.extend(str(v) for v in value if v)
    for sug in produced:
        prov = sug.get("provenance") if isinstance(sug, Mapping) else None
        for key in ("region_id", "source_region_id", "from_region_id"):
            value = (prov or {}).get(key) or (sug.get(key) if isinstance(sug, Mapping) else None)
            if isinstance(value, str) and value:
                out.append(value)
    return tuple(dict.fromkeys(out))


def production_records(rounds: Sequence[Mapping[str, Any]],
                       suggestions: Sequence[Mapping[str, Any]], *,
                       run_id: str = "") -> List[ProductionRecord]:
    """The per-step manifest for a whole run, in the order the steps happened.

    Reads the loop's own round trace (`LoopResult.to_dict()["rounds"]`) — so the manifest cannot
    drift from the receipt — and joins each step to the descriptors PROV-001 stamped with its
    `step_id`. Refused steps appear too: a manifest that only lists what ran would make a plan of
    five steps look like a plan of three.
    """
    by_step: Dict[str, List[Mapping[str, Any]]] = {}
    for sug in suggestions:
        step_id = str(((sug.get("provenance") or {}).get("step_id") or ""))
        if step_id:
            by_step.setdefault(step_id, []).append(sug)

    out: List[ProductionRecord] = []
    for round_doc in rounds:
        index = int(round_doc.get("round", 0))
        chain = round_doc.get("chain") or {}
        for entry in chain.get("lineage", ()):
            step_id = str(entry.get("step_id") or "")
            params = dict(entry.get("params") or {})
            mine = by_step.get(step_id, [])
            out.append(ProductionRecord(
                step_id=step_id, actuator=str(entry.get("actuator") or ""),
                status=str(entry.get("status") or ""), params=params,
                model=entry.get("model"), adapter=entry.get("adapter"),
                image=params.get(corpus_mod.IMAGE_PARAM),
                round_index=index,
                consumed=_consumed_ids(params, mine),
                produced=tuple(_suggestion_ref(s, run_id, step_id, i)
                               for i, s in enumerate(mine)),
                refusal=None,
                latency_ms=entry.get("latency_ms"),
                confidence=entry.get("confidence"),
                detail=str(entry.get("detail") or ""),
                inputs_used=dict(entry.get("inputs_used") or {})))
        # Plan-time refusals: the steps that never became work, with the reason in the closed
        # vocabulary the rest of the system branches on.
        for ref in (round_doc.get("plan") or {}).get("refused", ()):
            out.append(ProductionRecord(
                step_id=str(ref.get("step_id") or ""),
                actuator=str(ref.get("actuator") or ""),
                status="refused", round_index=index,
                refusal={"reason": str(ref.get("reason") or ""),
                         "detail": str(ref.get("detail") or "")}))
    return out


# ── the envelope ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RunView:
    """The whole run, as the contract's one shape. Poll and stream return this; so does an answer.

    Every field is derived from something that already happened. `stop_reason` is the loop's own,
    `rounds` is the loop's own trace, `suggestions` is the execution context's quarantine — the
    envelope adds no judgement of its own, which is what lets a reader trust it as a receipt
    rather than as a summary.
    """
    run_id: str
    status: str
    intention: str
    mode: str = MODE_EXPLORE
    corpus: Tuple[Dict[str, Any], ...] = ()
    rounds: Tuple[Dict[str, Any], ...] = ()
    question: Optional[Dict[str, Any]] = None
    stop_reason: Optional[str] = None
    weakest_link: Optional[float] = None
    suggestions: Tuple[Dict[str, Any], ...] = ()
    production_records: Tuple[Dict[str, Any], ...] = ()
    article: Optional[Dict[str, Any]] = None
    answer: Optional[Dict[str, Any]] = None       # A3: the answer this run was resumed with
    notes: Tuple[str, ...] = ()
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "intention": self.intention,
            "mode": self.mode,
            "corpus": [dict(c) for c in self.corpus],
            "rounds": [dict(r) for r in self.rounds],
            "question": dict(self.question) if self.question else None,
            "stop_reason": self.stop_reason,
            "weakest_link": self.weakest_link,
            "suggestions": [dict(s) for s in self.suggestions],
            "production_records": [dict(p) for p in self.production_records],
            "article": dict(self.article) if self.article else None,
            "answer": dict(self.answer) if self.answer else None,
            "notes": list(self.notes),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def status_for(result: lc.LoopResult) -> str:
    """The run's lifecycle state, read off the loop's honest stop reason.

    `awaiting_answer` is its own state because an answer can still change it. A loop that
    converged or ran out of new evidence is `complete`; everything else — a refusal it could not
    route around, a prompt nothing serves, the round backstop — is `stopped`, and the reason
    travels with it. Nothing is promoted: an empty run never reports as a complete one.
    """
    if result.stop_reason == lc.AWAITING_ANSWER:
        return STATUS_AWAITING_ANSWER
    if result.stop_reason in _COMPLETE_REASONS:
        return STATUS_COMPLETE
    return STATUS_STOPPED


# ── driving a run ────────────────────────────────────────────────────────────

@dataclass
class RunEngine:
    """One run's live machinery: the corpus, its execution context, the resolver's bookkeeping.

    Not persisted and not returned — it exists for the duration of one drive. What survives a run
    is the `RunView` and A3's `ResumeState`, both plain data.
    """
    spec: RunSpec
    run_id: str
    corpus: Corpus
    memory: CorpusWorkingMemory
    ctx: CorpusExecutionContext
    resolver: CorpusResolver
    director: Director
    registry: Dict[str, Any]
    # Argue mode's planner, injectable for the same reason the loop's is: the argument planner has
    # no rule-based fallback by design (nothing rule-based can decompose a thesis without inventing
    # one), so an offline run can only be tested on the honest-empty path unless a caller can hand
    # in a stand-in.
    argument_planner: Any = None

    def close(self) -> None:
        self.ctx.close()


def build_engine(spec: RunSpec, posts: Mapping[str, Mapping[str, Any]], *,
                 run_id: str = "", planner: Any = None, loop: Any = None,
                 registry_for: Optional[Callable[[str], Dict[str, Any]]] = None,
                 image_of: Optional[Mapping[str, str]] = None,
                 memory: Optional[CorpusWorkingMemory] = None,
                 argument_planner: Any = None) -> RunEngine:
    """Assemble everything one run needs from raw posts.

    `registry_for` is the injection that keeps this testable without a GPU: default is M1's routed
    real registry, and a test hands stubs. `image_of` re-seeds the resolver's step→image map when a
    stored run is being resumed, so the second half of a run attributes evidence exactly as the
    first half did.
    """
    ordered = [posts[pid] for pid in _ordered_ids(spec, posts) if pid in posts]
    corpus = corpus_from_posts(ordered, corpus_id=run_id or "corpus",
                               title=spec.prompt[:80], why=spec.prompt)
    base = memory if memory is not None else hydrate_run_memory(corpus, posts)
    ctx = build_corpus_context(corpus, posts, run_id=run_id, loop=loop)
    resolver = CorpusResolver(corpus, base)
    if image_of:
        resolver.image_of.update({str(k): str(v) for k, v in image_of.items()})
    from .groq_planner import GroqPlanner
    inner = planner if planner is not None else GroqPlanner()
    director = Director(FanOutPlanner(inner, corpus))
    registry = routed_registry(ctx, registry_for=registry_for)
    return RunEngine(spec=spec, run_id=run_id, corpus=corpus, memory=base, ctx=ctx,
                     resolver=resolver, director=director, registry=registry,
                     argument_planner=argument_planner)


def _ordered_ids(spec: RunSpec, posts: Mapping[str, Mapping[str, Any]]) -> List[str]:
    """The corpus order: exactly the ids the curator listed, then whatever the tags resolved to.

    The sequence carries the argument (M1), so an explicit list is never re-sorted. Tag-resolved
    posts follow in the order the caller read them, deduplicated against the explicit ones.
    """
    out: List[str] = [pid for pid in spec.image_ids if pid in posts]
    for pid in posts:
        if pid not in out:
            out.append(pid)
    return out


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:12]}"


def drive_run(spec: RunSpec, posts: Mapping[str, Mapping[str, Any]], *,
              run_id: str = "", planner: Any = None, loop: Any = None,
              registry_for: Optional[Callable[[str], Dict[str, Any]]] = None,
              max_rounds: int = 4, llm: Any = None, argument_planner: Any = None,
              now: Optional[str] = None) -> Tuple[RunView, lc.LoopResult, RunEngine]:
    """(images + a prompt) → a whole run. Synchronous; the caller owns the thread.

    Returns the view, the loop result (whose `resume_state` is what an answer resumes from), and
    the engine (so a caller can close its context). Everything it produces is a suggestion.
    """
    run_id = run_id or new_run_id()
    engine = build_engine(spec, posts, run_id=run_id, planner=planner, loop=loop,
                          registry_for=registry_for, argument_planner=argument_planner)
    result = lc.run_loop(spec.prompt, engine.memory, engine.registry,
                         director=engine.director, max_rounds=max_rounds,
                         loop_id=run_id, resolve_fn=engine.resolver)
    view = assemble_view(spec, result, engine, run_id=run_id, llm=llm, now=now)
    return view, result, engine


def resume_run(prior: lc.LoopResult, answer: str, engine: RunEngine, *,
               spec: Optional[RunSpec] = None, max_rounds: int = 4, llm: Any = None,
               now: Optional[str] = None) -> Tuple[RunView, lc.LoopResult]:
    """A3, at the surface: the curator's answer goes back into the SAME run.

    The answer becomes a param on the packet and the loop continues from where it stopped, so the
    returned view's rounds extend the prior trace rather than describing a second run. A refused
    answer comes back with the refusal recorded and the run still awaiting one.
    """
    spec = spec or engine.spec
    result = lc.resume_loop(prior, answer, engine.registry, director=engine.director,
                            max_rounds=max_rounds, resolve_fn=engine.resolver)
    view = assemble_view(spec, result, engine, run_id=engine.run_id, llm=llm, now=now)
    return view, result


def assemble_view(spec: RunSpec, result: lc.LoopResult, engine: RunEngine, *,
                  run_id: str = "", llm: Any = None,
                  now: Optional[str] = None) -> RunView:
    """The loop's result + the quarantine + (in argue mode) the article → the contract's envelope."""
    run_id = run_id or engine.run_id
    trace = result.to_dict()
    suggestions = list(engine.ctx.all_suggestions())
    records = production_records(trace.get("rounds", ()), suggestions, run_id=run_id)

    article: Optional[Dict[str, Any]] = None
    notes: List[str] = []
    if spec.mode == MODE_ARGUE:
        article, article_notes = compose_for_run(spec, result, engine, llm=llm)
        notes.extend(article_notes)

    return RunView(
        run_id=run_id,
        status=status_for(result),
        intention=spec.prompt,
        mode=spec.mode,
        corpus=tuple({"post_id": i.post_id, "image_url": i.image_ref, "title": i.title}
                     for i in engine.corpus.images),
        rounds=tuple(trace.get("rounds", ())),
        question=trace.get("question"),
        stop_reason=result.stop_reason,
        weakest_link=result.weakest_link,
        suggestions=tuple(suggestions),
        production_records=tuple(r.to_dict() for r in records),
        article=article,
        answer=trace.get("answer"),
        notes=tuple(notes),
        updated_at=now,
    )


# ── argue mode: the prompt as a thesis (M2 → M6) ─────────────────────────────

def compose_for_run(spec: RunSpec, result: lc.LoopResult, engine: RunEngine, *,
                    llm: Any = None) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Argue mode: the prompt is put to the argument machinery, and the article is composed from
    what a run CONFIRMED rather than from what a plan hoped for.

    The order is forced by M3's rule and is the whole reason this is not a second engine: an
    argument is planned (M2) against the evidence the loop actually left in memory, its percept
    chain is EXECUTED, and only then is the article composed against that chain's provenance
    (`compose_article(provenance=…)`). Composing from the plan would describe evidence that may
    never have been produced, and would be indistinguishable from an article that was earned.

    A failure anywhere here is a note on the run, never an exception: an explore run that also
    tried to argue is still a run, and the evidence it produced is still real.
    """
    from .argument_planner import RhetoricalDirector
    from .composition import LLM, compose_article
    from .article_resolver import resolve_article

    notes: List[str] = []
    try:
        memory = engine.resolver.reconcile(result.memory)
        director = (RhetoricalDirector(engine.argument_planner)
                    if engine.argument_planner is not None else RhetoricalDirector())
        argument = director.plan(spec.prompt, memory)
        plan = getattr(argument, "plan", None)
        if plan is None or not getattr(plan, "steps", ()):
            notes.append("argue: no percept chain could be planned for this thesis; "
                         "nothing was composed")
            return None, notes

        from .execution import execute
        chain = execute(plan, memory, engine.registry, chain_id=f"{engine.run_id}:argue")
        draft = compose_article(argument, memory, provenance=chain.provenance,
                                llm=llm if isinstance(llm, LLM) else LLM.from_service(),
                                run_id=engine.run_id)
        payload = draft.to_dict()
        resolved = resolve_article(payload, list(engine.ctx.all_suggestions()), memory)
        payload["resolved"] = resolved.to_dict()
        notes.append(f"argue: {len(getattr(argument, 'claims', ()))} claim(s) planned, "
                     f"composed against a run of {len(chain.provenance.lineage)} step(s)")
        return payload, notes
    except Exception as exc:                      # noqa: BLE001 — a note, never a failed run
        notes.append(f"argue: composition did not complete ({type(exc).__name__}); "
                     f"the run's evidence is unaffected")
        return None, notes
