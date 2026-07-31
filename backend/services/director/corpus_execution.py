"""
CIRCUIT-003 M1 — running a plan that spans a corpus.

`execution.execute()` runs a plan against ONE memory with ONE registry of runners. A corpus plan
needs neither of those to change: a step targeting the colonnade must reach the colonnade's
producers with the colonnade's image bytes, and a comparative step must see across all of them.
This module supplies the two pieces that makes possible, and then calls the EXISTING `execute()`.

    CorpusExecutionContext — one per-image `ExecutionContext` per image, sharing one event loop,
                             one run id, and one comparative quarantine
    routed_registry        — a runner per actuator that reads the step's `image` param and
                             dispatches to that image's registry; comparative actuators get the
                             corpus context itself

WHAT IS REUSED, WHICH IS ALMOST EVERYTHING. Refusal propagation, the pre-dispatch requirement
re-check, skip-with-a-named-blocker, chain provenance, weakest-link — none of it is re-implemented
here, because none of it needs to know how many images there are. `execute()` is handed a
`CorpusWorkingMemory` (a `WorkingMemory`) and a dict of runners (the `ActuatorRunner` shape), and
cannot tell it is running across five photographs rather than one.

RESIDENCY. One event loop for the whole corpus, shared by every per-image context, for the same
reason WIRE-001 used one per plan: `ModelManager`'s semaphores bind to a loop, and a second loop
would rebind them mid-run. Models still load and unload one at a time; a five-image corpus does
not hold five models, it holds at most one.

DATA SAFETY, UNCHANGED. Every context is quarantine-only. Nothing here writes to a post, commits
a region, or accepts a mark — for five posts now instead of one, which is five times the reason
to keep it that way.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

from .capabilities import is_comparative, known
from .corpus import Corpus, CorpusWorkingMemory, image_target
from .execution import ActuatorResult, ActuatorRunner, ChainResult, UNAVAILABLE, execute
from .memory import WorkingMemory
from .plan import Step
from .real_actuators import ExecutionContext, RealActuatorRunner, real_registry


@dataclass
class CorpusExecutionContext(ExecutionContext):
    """What the runners share across one CORPUS run.

    A subclass of `ExecutionContext` rather than a new type: a comparative runner is handed this,
    a single-image runner is handed a plain one, and neither has to branch on which. Its own
    `post_id`/`post`/`regions`/`suggestions` are the FOCUS image's, so anything that treats it as
    an ordinary context sees a coherent single-image view rather than a merged blur.

    `contexts` holds one real context per image. `comparative` is a separate quarantine for
    suggestions that span images — a relation joining the façade to the rotunda is evidence about
    the SEQUENCE, and filing it under either post would make it read, later, as something found in
    that photograph.
    """
    corpus: Optional[Corpus] = None
    contexts: Dict[str, ExecutionContext] = field(default_factory=dict)
    comparative: List[Dict[str, Any]] = field(default_factory=list)

    # ── the cross-image accessors the runners duck-type against ──────────────
    def marks_by_image(self) -> Dict[str, List[Dict[str, Any]]]:
        """Quarantined marks per image, in CORPUS ORDER.

        Order matters here and not merely for tidiness: with no explicit refs, `compare_views`
        takes one mark from each of the first two images that carry any, and "first two" has to
        mean first in the sequence the curator built, not first in whatever order a dict happened
        to be filled.
        """
        from .real_actuators import _quarantined_marks
        out: Dict[str, List[Dict[str, Any]]] = {}
        for post_id in self.ordered_post_ids():
            ctx = self.contexts.get(post_id)
            out[post_id] = _quarantined_marks(ctx) if ctx is not None else []
        return out

    def image_ref_for(self, post_id: str) -> str:
        if self.corpus is not None:
            image = self.corpus.by_post_id(str(post_id))
            if image is not None:
                return image.image_ref or image.post_id
        ctx = self.contexts.get(str(post_id))
        if ctx is not None:
            return str((ctx.post or {}).get("photo_url") or post_id)
        return str(post_id)

    def record_comparative(self, suggestion: Dict[str, Any]) -> None:
        self.comparative.append(suggestion)

    # ── plumbing ─────────────────────────────────────────────────────────────
    def ordered_post_ids(self) -> List[str]:
        if self.corpus is not None and self.corpus.images:
            ordered = [i.post_id for i in self.corpus.images if i.post_id in self.contexts]
            ordered.extend(p for p in self.contexts if p not in ordered)
            return ordered
        return list(self.contexts)

    def context_for(self, post_id: Optional[str]) -> ExecutionContext:
        """The per-image context a targeted step runs in. Falls back to the focus context, which
        is where an untargeted step belongs — `resolve_corpus` writes the target onto every
        single-image step it plans, so a step arriving here without one was never planned."""
        if post_id and str(post_id) in self.contexts:
            return self.contexts[str(post_id)]
        return self

    def all_suggestions(self) -> List[Dict[str, Any]]:
        """Everything the run produced, per-image first (in corpus order) then comparative.

        Each per-image suggestion is tagged with the post it was produced on. Without that tag a
        merged list of five images' suggestions is unusable — every consumer would have to guess
        which picture a region belongs to, and would guess the focus image.
        """
        out: List[Dict[str, Any]] = []
        for post_id in self.ordered_post_ids():
            ctx = self.contexts.get(post_id)
            if ctx is None:
                continue
            for sug in ctx.suggestions:
                if isinstance(sug, dict) and not sug.get("post_id"):
                    sug = {**sug, "post_id": post_id}
                out.append(sug)
        out.extend(self.comparative)
        return out

    def close(self) -> None:
        """Close the per-image contexts first, then this one. Only the owner of the loop closes
        it — every per-image context borrows it, so they must not."""
        for ctx in self.contexts.values():
            if ctx is not self:
                ctx.close()
        super().close()


def build_corpus_context(corpus: Corpus, posts: Mapping[str, Mapping[str, Any]], *,
                         run_id: str = "", loop: Any = None,
                         focus_post_id: Optional[str] = None) -> CorpusExecutionContext:
    """One execution context per image, all sharing this corpus context's loop and run id.

    Committed regions seed each image's real-data bridge, exactly as the single-post orchestrate
    route does — a step needing a region can use one the curator already has, and `find_parts`
    still runs on that image when the plan asks for it.

    An image whose post could not be read gets NO context. Its steps then find no runner and are
    reported UNAVAILABLE by the existing machinery, which is the honest outcome: a missing picture
    is a gap in the walk, not an image with nothing in it.
    """
    images = corpus.images
    focus = focus_post_id or (images[0].post_id if images else "")
    focus_post = dict(posts.get(focus) or {})
    root = CorpusExecutionContext(post_id=focus, post=focus_post, run_id=run_id, loop=loop,
                                  corpus=corpus)
    for image in images:
        post = posts.get(image.post_id)
        if post is None:
            continue
        ctx = ExecutionContext(post_id=image.post_id, post=dict(post), run_id=root.run_id,
                               loop=root.loop)
        ctx.regions = list((post.get("region_annotations") or []))
        root.contexts[image.post_id] = ctx
    return root


# ── routing: the step's image decides which context runs it ──────────────────

class RoutedRunner:
    """One actuator, dispatched to the right image's runners.

    Holds the `ActuatorRunner` shape (`(Step, WorkingMemory) → ActuatorResult`), so `execute()`
    cannot tell it from a `StubActuator` or a `RealActuatorRunner` — which is exactly why the
    corpus needs no changes in `execution.py`.

    A comparative actuator is NOT routed to an image: it is run against the corpus context itself,
    because its whole job is to see across the images that the per-image contexts each see one of.
    """

    def __init__(self, name: str, cctx: CorpusExecutionContext,
                 registry_for: Callable[[str], Dict[str, ActuatorRunner]]):
        self.name = name
        self.cctx = cctx
        self._registry_for = registry_for
        self._comparative = is_comparative(name)

    def __call__(self, step: Step, memory: WorkingMemory) -> ActuatorResult:
        if self._comparative:
            return RealActuatorRunner(self.name, self.cctx)(step, memory)
        target = image_target(step)
        post_id = str(target) if target not in (None, "") else self.cctx.post_id
        if post_id not in self.cctx.contexts:
            # An image with no context (its post could not be read) must SAY so. Returning
            # unavailable puts it through the same skip-with-a-named-blocker path as a model
            # being down, so anything depending on this step reports the real cause.
            return ActuatorResult(status=UNAVAILABLE, produced=(), adapter=self.name,
                                  detail=f"no execution context for image '{post_id}'")
        runner = self._registry_for(post_id).get(self.name)
        if runner is None:
            return ActuatorResult(status=UNAVAILABLE, produced=(), adapter=self.name,
                                  detail=f"no runner for '{self.name}' on image '{post_id}'")
        return runner(step, memory)


def routed_registry(cctx: CorpusExecutionContext, *,
                    registry_for: Optional[Callable[[str], Dict[str, ActuatorRunner]]] = None
                    ) -> Dict[str, RoutedRunner]:
    """A routed runner for every known actuator. The corpus counterpart of `real_registry`.

    `registry_for(post_id)` supplies that image's runners — real ones by default. It is injectable
    so a corpus can be run entirely on stubs (no GPU, no network, no database), which is what lets
    the corpus path be exercised unattended in the same way the single-image path already is.
    """
    cache: Dict[str, Dict[str, ActuatorRunner]] = {}

    def _default(post_id: str) -> Dict[str, ActuatorRunner]:
        if post_id not in cache:
            cache[post_id] = real_registry(cctx.contexts[post_id])
        return cache[post_id]

    resolver = registry_for or _default
    return {name: RoutedRunner(name, cctx, resolver) for name in known()}


def run_corpus_plan(plan, memory: CorpusWorkingMemory, cctx: CorpusExecutionContext, *,
                    registry_for: Optional[Callable[[str], Dict[str, ActuatorRunner]]] = None,
                    chain_id: str = "corpus") -> ChainResult:
    """Execute a resolved corpus plan. Returns the ChainResult; the produced suggestions are in
    `cctx.all_suggestions()`.

    Deliberately thin. Everything that decides whether a step runs, skips, or is reported as a gap
    is `execute()`'s, unchanged — this only decides WHERE each step runs.
    """
    return execute(plan, memory, routed_registry(cctx, registry_for=registry_for),
                   chain_id=chain_id)
