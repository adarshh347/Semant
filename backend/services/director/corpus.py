"""
CIRCUIT-003 M1 — the corpus: an ORDERED set of images the ledger spans.

Everything above Layer 3 has been single-image. A post has regions, marks, grounds and percepts;
`WorkingMemory` is "what the Director knows about ONE image"; `resolve()` plans against that one
packet. That is the right shape for looking at a picture and the wrong shape for the thing the
benchmark actually walks: Lustgarten → façade → colonnade → stair → rotunda, where the reading
that matters — a dispersed civic ground against a centralized rotunda — is not IN any one of the
five photographs. It is the relation between two of them.

So this module adds the container that relation needs, and adds it BESIDE the single-image path
rather than through it:

    Corpus              — an ordered set of images/posts, with the order load-bearing
    CorpusWorkingMemory — a merged packet whose IMAGE count is the number of images
    hydrate_corpus      — per-image packets built by the UNCHANGED `build_memory`, then merged
    resolve_corpus      — tiered planning: per-image steps, then comparative steps

WHY ADDITIVE, LITERALLY. `build_memory` is untouched and still returns exactly what it returned
before; `resolve()` is untouched and is what actually does the resolving here, called once per
image and once for the comparative tier. `CorpusWorkingMemory` is a SUBCLASS of `WorkingMemory`,
so anything that already takes a packet — `execute()`, the loop controller, a planner — takes a
corpus packet without knowing the word corpus. The single-post `POST /{post_id}/orchestrate` path
does not change by one line, which matters because several other lanes are built on it.

THE ONE MECHANISM WORTH READING TWICE. A corpus packet reports `IMAGE: n` where the single-image
packet hardcodes 1. That single override is what makes a comparative actuator refusable by the
EXISTING gate: `compare_views` declares `2× image`, an ordinary requirement, so asking it of one
photograph is refused by `resolve()` with no corpus-aware branch anywhere in `plan.py`. Nothing
here re-implements the refusal logic, which is the only way the two paths cannot drift apart on
what "honest" means.

ORDER IS EVIDENCE. The images are a sequence, not a set. A stair read before the rotunda and a
stair read after it are different readings, so `Corpus.images` is a tuple, positions are stable,
and a step may target an image by position as well as by id.

PURE MODULE. No database, no fetch, no clock. `hydrate_corpus` is handed post documents that
somebody else read — same discipline as `memory.py`, and the reason this whole layer is testable
without Mongo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .capabilities import Resource, get as get_actuator, is_comparative
from backend.services import cross_image

from .memory import DEFAULT_CONSTRAINTS, WorkingMemory, build_memory
from .plan import Plan, RefusedStep, Step, resolve

CORPUS_VERSION = 1

# Refusal reason codes this module adds to `plan.py`'s closed set. Additive: the existing three
# keep their exact meanings, and a caller branching on them is unaffected by these two, which can
# only ever appear on a plan produced by `resolve_corpus`.
REFUSED_UNKNOWN_IMAGE = "unknown_image"      # the step named an image this corpus does not hold
REFUSED_IMAGE_SCOPE = "image_scope"          # a comparative step was pinned to a single image

# The step param naming which image a step works on. A post id, or an integer position in the
# corpus order (0-based) — positions are supported because a plan written against "the third
# view" should survive the corpus being re-hydrated with fresh post documents.
IMAGE_PARAM = "image"

# How a merged mark id records where it came from. Namespacing rather than a bare id because two
# posts can and do carry marks with the same local id, and a merged packet that silently collapsed
# them would under-count the evidence a comparative step is resting on.
ORIGIN_SEP = "::"


def namespaced(post_id: str, local_id: str) -> str:
    return f"{post_id}{ORIGIN_SEP}{local_id}"


def split_namespaced(ref: str) -> Tuple[Optional[str], str]:
    """(post_id, local_id) for a merged id; (None, ref) for anything else. Never raises —
    a ref that was never namespaced is a legitimate input, not an error."""
    if ORIGIN_SEP in ref:
        head, _, tail = ref.partition(ORIGIN_SEP)
        return head, tail
    return None, ref


# ── the model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CorpusImage:
    """One image in the sequence, and where it sits.

    `position` is stored rather than derived from list index so that a CorpusImage handed around
    on its own still knows where it stood. `note` is the curator's reason for including it — the
    sequence carries an argument, and a corpus that cannot say why the stair follows the colonnade
    is a folder."""
    post_id: str
    image_ref: str = ""
    position: int = 0
    title: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"post_id": self.post_id, "image_ref": self.image_ref,
                "position": self.position, "title": self.title, "note": self.note}


@dataclass(frozen=True)
class Corpus:
    """An ordered set of images/posts that one ledger spans.

    Frozen, like everything else at this layer: a corpus a plan was resolved against has to stay
    truthful after the run, or the recorded plan describes a walk nobody took.
    """
    corpus_id: str
    title: str = ""
    why: str = ""                                   # what this sequence is FOR
    images: Tuple[CorpusImage, ...] = ()
    version: int = CORPUS_VERSION

    # ── lookup ──
    @property
    def post_ids(self) -> Tuple[str, ...]:
        return tuple(i.post_id for i in self.images)

    def at(self, position: int) -> Optional[CorpusImage]:
        if 0 <= position < len(self.images):
            return self.images[position]
        return None

    def by_post_id(self, post_id: str) -> Optional[CorpusImage]:
        return next((i for i in self.images if i.post_id == str(post_id)), None)

    def resolve_target(self, target: Any) -> Optional[CorpusImage]:
        """An `image` param → the image it names, or None if this corpus does not hold it.

        Accepts a post id or a 0-based position (int, or a string of digits — a plan that
        round-tripped through JSON should not become unresolvable). None is a REFUSAL upstream,
        never a fallback to the first image: quietly retargeting a step at a different photograph
        is precisely the kind of silent substitution this layer exists to make impossible.
        """
        if target is None or target == "":
            return None
        if isinstance(target, bool):                # bool is an int in python; not a position
            return None
        if isinstance(target, int):
            return self.at(target)
        text = str(target)
        found = self.by_post_id(text)
        if found is not None:
            return found
        if text.lstrip("-").isdigit():
            return self.at(int(text))
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"corpus_id": self.corpus_id, "title": self.title, "why": self.why,
                "version": self.version, "images": [i.to_dict() for i in self.images]}


def build_corpus(*, corpus_id: str, title: str = "", why: str = "",
                 images: Sequence[Any] = ()) -> Corpus:
    """Assemble a corpus. `images` may be post-id strings, dicts, or CorpusImages.

    Positions are assigned from the given order — the caller's sequence IS the argument, and
    renumbering it here would silently rewrite the claim.
    """
    out: List[CorpusImage] = []
    for i, item in enumerate(images):
        if isinstance(item, CorpusImage):
            out.append(replace(item, position=i))
        elif isinstance(item, Mapping):
            out.append(CorpusImage(
                post_id=str(item.get("post_id") or item.get("id") or ""),
                image_ref=str(item.get("image_ref") or item.get("photo_url") or ""),
                position=i, title=str(item.get("title") or ""),
                note=str(item.get("note") or "")))
        else:
            out.append(CorpusImage(post_id=str(item), position=i))
    return Corpus(corpus_id=corpus_id, title=title, why=why, images=tuple(out))


# ── the merged packet ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CorpusWorkingMemory(WorkingMemory):
    """What the Director knows about a CORPUS, at one moment.

    A `WorkingMemory` subclass on purpose, not a parallel type. `execute()`, `resolve()`, the loop
    controller and every planner take a `WorkingMemory`; making this one of those means the whole
    Layer-3 machine spans a corpus without a single `isinstance` check anywhere in it. `evolve()`
    and `with_unreadable()` are inherited unchanged — both go through `dataclasses.replace`, which
    preserves the subclass and its extra fields.

    The inherited id tuples hold the MERGED, namespaced ids (`post_id::mark_id`), so a count is
    still a count of real distinct evidence and `origins` can always say which picture each piece
    came from. `per_image` keeps the untouched single-image packets — a step aimed at one image is
    checked against the packet for THAT image, never against the union, or a plan would happily
    schedule a field on the colonnade because the rotunda had a region.
    """
    corpus: Optional[Corpus] = None
    per_image: Dict[str, WorkingMemory] = field(default_factory=dict)
    focus_post_id: Optional[str] = None
    # merged id → post id, for every hydrated (committed) piece of evidence.
    origins: Dict[str, str] = field(default_factory=dict)

    # ── derived view ─────────────────────────────────────────────────────────
    def available(self) -> Dict[Resource, int]:
        """The single override that makes comparison refusable by the existing gate.

        Everything is inherited except IMAGE, which the single-image packet hardcodes to 1. Here
        it is the number of images actually hydrated — so `2× image` is satisfied by a two-image
        corpus and refused by a one-image corpus, through `resolve()`, with no new refusal code.
        """
        counts = super().available()
        counts[Resource.IMAGE] = max(1, len(self.image_refs))
        return counts

    @property
    def image_refs(self) -> Tuple[str, ...]:
        if self.corpus is None:
            return (self.image_ref,) if self.image_ref else ()
        return tuple(i.image_ref or i.post_id for i in self.corpus.images)

    @property
    def post_ids(self) -> Tuple[str, ...]:
        return self.corpus.post_ids if self.corpus else tuple(self.per_image.keys())

    def memory_for(self, post_id: Optional[str]) -> WorkingMemory:
        """The single-image packet for one image — what a targeted step is checked against.

        Falls back to the merged packet when the image is unknown, which never happens on a
        resolved plan (`resolve_corpus` refuses an unknown image before it gets here) and is a
        safe answer if someone calls this directly: the merged packet over-reports nothing that
        would let a step fire blind, because `execute()` re-checks at dispatch either way.
        """
        if post_id and post_id in self.per_image:
            return self.per_image[post_id]
        return self

    def marks_on(self, post_id: str) -> Tuple[str, ...]:
        """The committed mark ids on ONE image, un-namespaced. What "hydrate all its images'
        marks" is actually asserted against."""
        packet = self.per_image.get(post_id)
        return packet.mark_ids if packet else ()

    def origin_of(self, merged_id: str) -> Optional[str]:
        """Which image a merged id came from. Prefers the recorded map, falls back to the
        namespace — a ref that arrived from outside is still traceable."""
        if merged_id in self.origins:
            return self.origins[merged_id]
        post_id, _ = split_namespaced(merged_id)
        return post_id

    def images_represented(self, merged_ids: Sequence[str]) -> Tuple[str, ...]:
        """The DISTINCT images a set of refs touches, in corpus order.

        The question a comparative claim has to be able to answer about itself: two marks that
        both came from the façade are not a comparison across the sequence, however different
        they look.
        """
        seen = {self.origin_of(m) for m in merged_ids}
        seen.discard(None)
        ordered = [p for p in self.post_ids if p in seen]
        ordered.extend(sorted(p for p in seen if p not in self.post_ids))
        return tuple(ordered)

    def summary(self) -> Dict[str, Any]:
        base = super().summary()
        base["corpus"] = {
            "corpus_id": self.corpus.corpus_id if self.corpus else None,
            "title": self.corpus.title if self.corpus else "",
            "images": list(self.post_ids),
            "focus": self.focus_post_id,
            "per_image_counts": {
                pid: {k.value: v for k, v in packet.available().items()}
                for pid, packet in self.per_image.items()},
        }
        return base


# ── hydration ────────────────────────────────────────────────────────────────

def _ids(items: Any) -> List[str]:
    """Committed ids off a post document. Same shape the single-post orchestrate route uses."""
    return [str(x.get("id")) for x in (items or [])
            if isinstance(x, dict) and x.get("id")]


def memory_from_post(post: Mapping[str, Any], *, post_id: str,
                     image_ref: str = "", phrase: Optional[str] = None,
                     first_attention: Optional[str] = None,
                     unreadable: Sequence[str] = ()) -> WorkingMemory:
    """One post document → one single-image packet, via the UNCHANGED `build_memory`.

    Extracted here (rather than added to memory.py) so the corpus path and the single-post route
    read a post the same way without the route having to change.
    """
    return build_memory(
        image_ref=image_ref or str(post.get("photo_url") or post_id), post_id=post_id,
        region_ids=_ids(post.get("region_annotations")),
        # THE CROSS-IMAGE GUARD (C3). A `compare_views` relation is committed into both posts it
        # spans, so it is in this post's `visual_marks` — and counting it here would let a single
        # image's packet claim a mark that is really about the SEQUENCE. That matters most for
        # `compare_views` itself, whose two-image requirement is checked against these counts: a
        # relation counted as native evidence would help satisfy the requirement for producing
        # another relation, and the gate would be grading its own output.
        mark_ids=_ids(cross_image.native_marks(post.get("visual_marks"))),
        ground_ids=_ids(post.get("grounds")),
        percept_ids=_ids(post.get("percepts")),
        phrase=phrase, first_attention=first_attention, unreadable=unreadable)


def hydrate_corpus(corpus: Corpus, posts: Mapping[str, Mapping[str, Any]], *,
                   phrase: Optional[str] = None, first_attention: Optional[str] = None,
                   focus_post_id: Optional[str] = None,
                   constraints: Optional[Dict[str, Any]] = None) -> CorpusWorkingMemory:
    """Every image's committed evidence, in one packet, with per-image packets kept intact.

    `posts` maps post_id → the post document somebody already read. An image the caller could NOT
    read is NOT silently dropped: it gets an empty packet and its id is recorded in `unreadable`,
    because "the colonnade has no marks" and "the colonnade could not be loaded" are different
    facts and a comparison built on the second one while believing the first is exactly the
    failure this layer keeps refusing to allow.
    """
    per_image: Dict[str, WorkingMemory] = {}
    origins: Dict[str, str] = {}
    regions: List[str] = []
    marks: List[str] = []
    grounds: List[str] = []
    percepts: List[str] = []
    unreadable: List[str] = []

    for image in corpus.images:
        post = posts.get(image.post_id)
        if post is None:
            per_image[image.post_id] = build_memory(
                image_ref=image.image_ref or image.post_id, post_id=image.post_id,
                unreadable=(f"post:{image.post_id}",))
            unreadable.append(f"post:{image.post_id}")
            continue
        packet = memory_from_post(post, post_id=image.post_id, image_ref=image.image_ref,
                                  phrase=phrase, first_attention=first_attention)
        per_image[image.post_id] = packet
        for local, bucket in ((packet.region_ids, regions), (packet.mark_ids, marks),
                              (packet.ground_ids, grounds), (packet.percept_ids, percepts)):
            for lid in local:
                merged = namespaced(image.post_id, lid)
                origins[merged] = image.post_id
                bucket.append(merged)
        unreadable.extend(packet.unreadable)

    first = corpus.images[0] if corpus.images else None
    focus = focus_post_id or (first.post_id if first else None)
    return CorpusWorkingMemory(
        image_ref=(first.image_ref or first.post_id) if first else "",
        post_id=focus,
        region_ids=tuple(regions), mark_ids=tuple(marks),
        ground_ids=tuple(grounds), percept_ids=tuple(percepts),
        phrase=phrase, first_attention=first_attention,
        constraints={**DEFAULT_CONSTRAINTS, **(constraints or {})},
        unreadable=tuple(unreadable),
        corpus=corpus, per_image=per_image, focus_post_id=focus, origins=origins)


def merge_memories(corpus: Corpus, per_image: Mapping[str, WorkingMemory], *,
                   focus_post_id: Optional[str] = None,
                   phrase: Optional[str] = None,
                   origins: Optional[Mapping[str, str]] = None) -> CorpusWorkingMemory:
    """Re-merge per-image packets that have already been advanced.

    Used by `resolve_corpus` after projecting each image's own steps forward: the comparative tier
    must be planned against what the per-image tier WILL have produced, or "find the parts on both,
    then compare them" would be refused for want of marks that the same plan is about to make.
    """
    regions: List[str] = []
    marks: List[str] = []
    grounds: List[str] = []
    percepts: List[str] = []
    unreadable: List[str] = []
    origin_map: Dict[str, str] = dict(origins or {})

    for image in corpus.images:
        packet = per_image.get(image.post_id)
        if packet is None:
            continue
        for local, bucket in ((packet.region_ids, regions), (packet.mark_ids, marks),
                              (packet.ground_ids, grounds), (packet.percept_ids, percepts)):
            for lid in local:
                merged = lid if ORIGIN_SEP in lid else namespaced(image.post_id, lid)
                origin_map.setdefault(merged, image.post_id)
                bucket.append(merged)
        unreadable.extend(packet.unreadable)

    first = corpus.images[0] if corpus.images else None
    focus = focus_post_id or (first.post_id if first else None)
    return CorpusWorkingMemory(
        image_ref=(first.image_ref or first.post_id) if first else "",
        post_id=focus,
        region_ids=tuple(regions), mark_ids=tuple(marks),
        ground_ids=tuple(grounds), percept_ids=tuple(percepts),
        phrase=phrase, unreadable=tuple(dict.fromkeys(unreadable)),
        corpus=corpus, per_image=dict(per_image), focus_post_id=focus, origins=origin_map)


# ── planning across the corpus ───────────────────────────────────────────────

def image_target(step: Step) -> Any:
    """The raw `image` param off a step, or None. One place, so the key cannot drift."""
    return (step.params or {}).get(IMAGE_PARAM)


def _targeted(step: Step, post_id: str) -> Step:
    """The same step, with its target written in. A resolved corpus plan carries the image on
    every step, so a reader of the plan (or the executor's router) never has to infer it."""
    params = dict(step.params or {})
    params[IMAGE_PARAM] = post_id
    return Step(actuator=step.actuator, params=params, id=step.id, note=step.note)


def resolve_corpus(steps: Sequence[Step], memory: CorpusWorkingMemory, *,
                   intention: str = "", workflow: Optional[str] = None,
                   planner: str = "rule_based") -> Plan:
    """Order what can run across a corpus; refuse what cannot. The corpus counterpart of `resolve`.

    TIERED, and the tiers are the whole idea:

      IMAGE TIER — a step naming an image (or any single-image step, which defaults to the
      corpus's focus image) is resolved against THAT image's own packet, by calling the ordinary
      `resolve()` once per image. Per-image ordering, per-image refusal, per-image everything —
      identical semantics to the single-post path, because it IS the single-post path.

      COMPARATIVE TIER — a step whose actuator spans images is resolved once, against the merged
      packet PROJECTED FORWARD by what the image tier is going to produce. That projection is what
      lets "find the parts on the façade, find the parts on the rotunda, then compare them"
      resolve, while "compare them" on its own against two bare images is still refused for want
      of marks.

    Comparative steps always come last. Not a scheduling convenience — a comparison of things that
    have not been found yet is not a comparison, and there is no ordering of the two tiers that
    makes it one.
    """
    corpus = memory.corpus
    if corpus is None or not corpus.images:
        # No corpus: this is a single-image packet wearing a corpus type. Defer entirely to the
        # existing gate rather than inventing a degenerate one-image corpus.
        return resolve(steps, memory, intention=intention, workflow=workflow, planner=planner)

    by_image: Dict[str, List[Step]] = {i.post_id: [] for i in corpus.images}
    comparative_steps: List[Step] = []
    pre_refused: List[RefusedStep] = []
    focus = memory.focus_post_id or corpus.images[0].post_id

    for step in steps:
        target = image_target(step)
        actuator = get_actuator(step.actuator)
        if actuator is None:
            # Unknown actuators are `resolve()`'s job, and it words the refusal. Route it to the
            # focus image so exactly one gate reports it, in exactly the existing wording.
            by_image.setdefault(focus, []).append(step)
            continue
        if is_comparative(step.actuator):
            if target is not None and target != "":
                pre_refused.append(RefusedStep(
                    step=step, reason=REFUSED_IMAGE_SCOPE,
                    detail=(f"'{step.actuator}' relates across images; it cannot be pinned to "
                            f"one ({target})")))
                continue
            comparative_steps.append(step)
            continue
        if target is None or target == "":
            by_image.setdefault(focus, []).append(_targeted(step, focus))
            continue
        image = corpus.resolve_target(target)
        if image is None:
            pre_refused.append(RefusedStep(
                step=step, reason=REFUSED_UNKNOWN_IMAGE,
                detail=(f"corpus '{corpus.corpus_id}' holds no image '{target}'")))
            continue
        by_image.setdefault(image.post_id, []).append(_targeted(step, image.post_id))

    # -- image tier: the ordinary gate, once per image, in corpus order --------
    ordered: List[Step] = []
    refused: List[RefusedStep] = list(pre_refused)
    projected: Dict[str, WorkingMemory] = {}
    reordered = False

    for image in corpus.images:
        packet = memory.memory_for(image.post_id)
        image_steps = by_image.get(image.post_id) or []
        if not image_steps:
            projected[image.post_id] = packet
            continue
        sub = resolve(image_steps, packet, intention=intention, workflow=workflow,
                      planner=planner)
        ordered.extend(sub.steps)
        refused.extend(sub.refused)
        reordered = reordered or sub.reordered
        # Project this image's own packet forward by what its steps will leave behind, so the
        # comparative tier plans against the evidence this plan is about to create.
        advanced = packet
        for s in sub.steps:
            a = get_actuator(s.actuator)
            if a is not None:
                advanced = advanced.evolve(a.projected_produces(), step_id=s.id or s.actuator)
        projected[image.post_id] = advanced

    # -- comparative tier: one gate, against the projected merged packet -------
    notes: List[str] = []
    if comparative_steps:
        merged = merge_memories(corpus, projected, focus_post_id=focus, phrase=memory.phrase,
                                origins=memory.origins)
        sub = resolve(comparative_steps, merged, intention=intention, workflow=workflow,
                      planner=planner)
        ordered.extend(sub.steps)
        refused.extend(sub.refused)
        reordered = reordered or sub.reordered
        notes.append(f"{len(sub.steps)} comparative step(s) planned across "
                     f"{len(corpus.images)} image(s)")

    # Refusals in REQUESTED order, matching `resolve()`'s own contract — a curator reading a
    # corpus plan's problems should see them in the order they asked for the steps, not tier by
    # tier, and certainly not image by image.
    position = {id(s): i for i, s in enumerate(steps)}
    refused.sort(key=lambda r: position.get(id(r.step), len(position)))

    requested_ids = [s.id for s in steps if any(o.id == s.id for o in ordered)]
    reordered = reordered or requested_ids != [s.id for s in ordered]

    return Plan(intention=intention, steps=tuple(ordered), refused=tuple(refused),
                workflow=workflow, planner=planner, reordered=reordered, notes=tuple(notes))


def corpus_steps(*specs: Any, prefix: str = "corpus") -> List[Step]:
    """(actuator, params) pairs → Steps with deterministic ids. The corpus counterpart of
    `Workflow.to_steps` — same replayability property, no clock, no counter."""
    out: List[Step] = []
    for i, spec in enumerate(specs):
        if isinstance(spec, Step):
            out.append(spec if spec.id else spec.with_id(f"{prefix}:{i}:{spec.actuator}"))
            continue
        actuator, params = (spec if isinstance(spec, (tuple, list)) else (spec, {}))
        out.append(Step(actuator=str(actuator), params=dict(params or {}),
                        id=f"{prefix}:{i}:{actuator}"))
    return out
