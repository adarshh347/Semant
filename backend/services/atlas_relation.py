"""
ATLAS C3 — relation edges: a drawn line IS a comparative percept, or it is nothing.

C1 put a corpus on one surface and left `edges` empty, saying so out loud: empty is "none drawn",
not "no relations found". This gate is what fills it. A writer drags from one image to another;
that gesture invokes M1's `compare_views`; and what comes back is either a real named relation —
rendered AS the edge, wearing its own epistemic chip and both provenance sources — or a refusal
rendered on the attempted edge with nothing persisted anywhere.

A SURFACE OVER `compare_views`, WHICH IS NOT TOUCHED. No comparison logic lives here. The actuator,
its two-image requirement, its refusals and its provenance are M1's and are used exactly as they
are. What this module does is assemble the two-image corpus the gesture names, hand the runner the
marks the writer is actually pointing at, and translate the outcome into something a canvas can
draw.

THE SEAM THAT MAKES THAT POSSIBLE, and the one design note worth reading twice. `compare_views`
finds its marks through `ctx.marks_by_image()` — a duck-typed lookup (`real_actuators._marks_by_image`)
whose default answers with the marks a RUN produced. That is right for a run and wrong for the
Atlas: the percepts on this canvas are COMMITTED ones, already in the ledger, drawn by the curator
weeks ago. So `CommittedMarksContext` answers the same question with committed marks. Nothing is
seeded into `ctx.suggestions`, which stays what its docstring promises — the plan's OUTPUT — so a
committed mark can never come back out of this looking like something the model just produced.

WHAT AN EDGE STORES: IDS AND ENDPOINTS. C1's rule is that the Atlas document holds arrangement and
references, never percept truth, and an edge obeys it exactly as a node does. `edge_entry` records
a mark id, the two node ids, the two post ids and a timestamp — no role, no label, no geometry, no
epistemic status. Every one of those is hydrated from the ledger at read time by `hydrate_edge`,
which is what makes a stale Atlas harmless: uncommit the relation and the edge says the relation is
gone rather than continuing to display a claim nobody holds any more.

A RELATION IS NOT A BINDING. C4's plan mode draws claim→image connectors that live in `plan` and
assert that a percept WOULD resolve. These run image↔image, live in `edges`, and assert that a
comparison WAS produced and committed. Two different words for two different acts, kept in two
different fields, so nothing downstream can read one as the other.

PURE WHERE IT CAN BE. Shaping, refusal translation and hydration are module-level functions with no
database and no clock. The two async functions at the bottom are the ledger write and its guard.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services.director.corpus import Corpus, build_corpus, hydrate_corpus, resolve_corpus
from backend.services.director.corpus_execution import (CorpusExecutionContext,
                                                        build_corpus_context, run_corpus_plan)
from backend.services.director.plan import Step

RELATION_CONTRACT_VERSION = 1

# What a C3 edge IS, written on every one of them. C4's connectors carry `binding`; nothing may
# ever carry both, and a reader that sees this word knows a real percept stands behind the line.
EDGE_RELATION = "relation"

# The actuator this gate wraps. Named once so a test can pin that C3 invokes M1's comparison and
# has not grown one of its own.
RELATE_ACTUATOR = "compare_views"

# The step id the gesture plans under. Stable, so two draws of the same pair are diffable.
RELATE_STEP_ID = "atlas_c3:relate"

# Refusal reasons this module can return, as a closed set — a refusal a caller cannot branch on is
# a string, not a contract (the same rule `plan.py` and `atlas_service.py` keep).
REFUSED_SAME_NODE = "same_node"              # a relation from an image to itself is not a relation
REFUSED_UNKNOWN_NODE = "unknown_node"        # the gesture named a node this Atlas does not hold
REFUSED_UNREADABLE = "unreadable_image"      # an endpoint's post could not be read
REFUSED_NOT_PLANNED = "gate_refused"         # `resolve_corpus` would not place the step
REFUSED_NOT_PRODUCED = "produced_nothing"    # the step ran and came back with no relation


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_edge_id() -> str:
    return f"edge_{uuid4().hex[:12]}"


def new_mark_id() -> str:
    """The id the committed relation carries in BOTH posts.

    One relation, one id, deliberately. Writing the same comparison into two `visual_marks` lists
    under two different ids would make one fact look like two findings, and the Atlas edge that
    referenced only one of them would leave the other orphaned in the ledger for ever.
    """
    return f"vm_rel_{uuid4().hex[:12]}"


# ── the context that lets `compare_views` see committed evidence ─────────────

class CommittedMarksContext(CorpusExecutionContext):
    """A corpus context whose `marks_by_image()` answers with COMMITTED marks.

    The one override, and the whole reason C3 needs no change inside `compare_views`. The base
    class answers with `_quarantined_marks(ctx)` — what this run produced — which on a canvas of
    committed percepts is always empty, so every comparison would refuse with "no marks" while the
    writer looks at two marks they drew themselves.

    `committed` is populated by `build_relation_context` from the post documents. `suggestions`
    is untouched: it remains the plan's output, so `all_suggestions()` returns the relation this
    run produced and nothing that was already in the ledger.
    """

    def __init__(self, *args, **kwargs):
        committed = kwargs.pop("committed", None)
        super().__init__(*args, **kwargs)
        self.committed: Dict[str, List[Dict[str, Any]]] = {
            str(k): list(v or []) for k, v in (committed or {}).items()}

    def marks_by_image(self) -> Dict[str, List[Dict[str, Any]]]:
        """Committed marks per image, in CORPUS ORDER — plus anything this run has produced.

        Corpus order for the same reason the base class keeps it: with no explicit refs,
        `compare_views` takes one mark from each of the first two images that carry any, and
        "first two" has to mean first in the sequence the writer built.

        Run output is appended rather than ignored so a chain that produced a mark and then
        compared it still works through this context — C3 only ever plans one step, but a context
        that silently dropped produced marks would be a trap for whoever plans two.
        """
        base = super().marks_by_image()
        out: Dict[str, List[Dict[str, Any]]] = {}
        for post_id in self.ordered_post_ids():
            out[post_id] = [*self.committed.get(str(post_id), []), *base.get(post_id, [])]
        return out


def committed_marks(post: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The marks a post actually holds, as `compare_views` expects to see them.

    Quarantined marks are excluded by the same rule `atlas_service._committed` uses: a
    `model_suggested` descriptor is a proposal, and a relation resting on one would be a comparison
    between two things nobody has accepted.
    """
    out: List[Dict[str, Any]] = []
    for mark in (post or {}).get("visual_marks") or []:
        if not isinstance(mark, Mapping):
            continue
        if str(mark.get("source") or "user") == "model_suggested":
            continue
        out.append(dict(mark))
    return out


def build_relation_corpus(pairs: Sequence[Tuple[str, Mapping[str, Any]]], *,
                          corpus_id: str = "", title: str = "") -> Corpus:
    """The two images this gesture spans, in the order they were drawn.

    Drawn order is source→target, and it is kept: `compare_views` records a left and a right, and
    "the façade prepares the rotunda" is not the same claim as its reverse.
    """
    return build_corpus(
        corpus_id=corpus_id or f"atlas_rel_{uuid4().hex[:8]}", title=title,
        why="two images a writer drew a relation between",
        images=[{"post_id": str(pid), "photo_url": str((post or {}).get("photo_url") or ""),
                 "title": str((post or {}).get("instagram_handle")
                              or (post or {}).get("domain") or "")}
                for pid, post in pairs])


def build_relation_context(corpus: Corpus, posts: Mapping[str, Mapping[str, Any]], *,
                           run_id: str = "", loop: Any = None) -> CommittedMarksContext:
    """`build_corpus_context`'s work, then the one thing C3 adds: the committed marks."""
    base = build_corpus_context(corpus, posts, run_id=run_id, loop=loop)
    ctx = CommittedMarksContext(
        post_id=base.post_id, post=base.post, run_id=base.run_id, loop=base.loop,
        corpus=corpus,
        committed={pid: committed_marks(posts.get(pid)) for pid in corpus.post_ids})
    ctx.contexts = base.contexts
    ctx.regions = base.regions
    return ctx


# ── refusals, in one shape ───────────────────────────────────────────────────

def refusal(reason: str, detail: str, *, source_node: str = "",
            target_node: str = "") -> Dict[str, Any]:
    """One shape for every way this can fail, so the surface renders them the same way.

    A refusal is a RETURN VALUE here, never an exception and never a 4xx: the gesture was
    well-formed and the answer is that the comparison cannot be grounded. Losing that distinction
    would turn "these two images share no evidence to compare" into "your request was malformed".
    """
    return {"reason": reason, "detail": detail,
            "source_node": source_node, "target_node": target_node}


def refusal_from_plan(plan: Any, *, source_node: str = "",
                      target_node: str = "") -> Optional[Dict[str, Any]]:
    """The gate's own words, if it would not place the step.

    `resolve_corpus` refuses by name and by missing input, and its `detail` already reads as a
    sentence ("'compare_views' needs 2× mark and nothing in this plan provides it"). It is passed
    through verbatim rather than reworded: the gate is the authority on why it refused, and a
    friendlier paraphrase would be this module inventing a reason.
    """
    for refused in getattr(plan, "refused", ()) or ():
        if getattr(refused, "step", None) is not None and refused.step.id == RELATE_STEP_ID:
            return refusal(REFUSED_NOT_PLANNED,
                           f"{getattr(refused, 'reason', 'refused')}: "
                           f"{getattr(refused, 'detail', '')}".strip(': '),
                           source_node=source_node, target_node=target_node)
    if not getattr(plan, "steps", ()):
        return refusal(REFUSED_NOT_PLANNED,
                       "the gate placed no step for this comparison",
                       source_node=source_node, target_node=target_node)
    return None


def refusal_from_result(result: Any, produced: Sequence[Mapping[str, Any]], *,
                        source_node: str = "", target_node: str = "") -> Optional[Dict[str, Any]]:
    """Why a step that WAS planned still produced no relation.

    This is the case `resolve()` cannot catch and the one that matters most in practice: the plan
    proved two images COULD carry marks, and at dispatch one of them did not. `compare_views`
    returns `EMPTY` with its own count ("needs marks on 2 images; 1 image(s) carry any"), and that
    sentence is what the writer needs to see on the line they just drew.
    """
    if produced:
        return None
    # The actuator's own sentence, off the chain provenance ("needs marks on 2 images; 1 image(s)
    # carry any"). That count is the thing the writer can act on, so it is worth reaching for
    # rather than reporting a generic failure — the fallback below exists only for the case where
    # a runner recorded nothing at all.
    detail = ""
    lineage = getattr(getattr(result, "provenance", None), "lineage", ()) or ()
    for record in lineage:
        if getattr(record, "step_id", "") == RELATE_STEP_ID:
            detail = f"{getattr(record, 'status', '')}: {getattr(record, 'detail', '')}".strip(': ')
            break
    return refusal(REFUSED_NOT_PRODUCED,
                   detail or "the comparison ran and named no relation",
                   source_node=source_node, target_node=target_node)


# ── the edge: references, never percept truth ────────────────────────────────

def edge_entry(*, mark_id: str, source_node: str, target_node: str,
               spans: Sequence[str], edge_id: str = "", now: str = "") -> Dict[str, Any]:
    """What the Atlas document stores for one relation.

    IDS AND ENDPOINTS ONLY. No role, no label, no epistemic status, no geometry — every one of
    those is the ledger's and is read back by `hydrate_edge`. An edge that cached the relation's
    label could disagree with the ledger about what was named, silently, months later, in a
    document that looks authoritative; this one cannot disagree because it makes no claim.
    """
    return {
        "edge_id": edge_id or new_edge_id(),
        "kind": EDGE_RELATION,
        "mark_id": str(mark_id),
        "source_node": str(source_node),
        "target_node": str(target_node),
        "spans": [str(p) for p in spans],
        "created_at": now or utc_now(),
    }


def find_mark(posts: Mapping[str, Mapping[str, Any]], spans: Sequence[str],
              mark_id: str) -> Optional[Dict[str, Any]]:
    """The committed relation an edge names, from either post that should hold it."""
    for pid in spans:
        for mark in (posts.get(str(pid)) or {}).get("visual_marks") or []:
            if isinstance(mark, Mapping) and str(mark.get("id")) == str(mark_id):
                return dict(mark)
    return None


def hydrate_edge(edge: Mapping[str, Any],
                 posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """One stored edge + the posts → what the canvas draws.

    A relation that is no longer in the ledger does NOT vanish from the canvas. It renders as an
    edge that says so — the same discipline as `hydrate_node`'s unreadable image, and for the same
    reason: "this relation was never drawn" and "this relation was drawn and has since been
    uncommitted" are different facts about the corpus, and a canvas that showed the second as the
    first would be lying by omission about what a writer once claimed.
    """
    out = {k: edge.get(k) for k in
           ("edge_id", "kind", "mark_id", "source_node", "target_node", "spans", "created_at")}
    out["kind"] = out.get("kind") or EDGE_RELATION
    mark = find_mark(posts, edge.get("spans") or [], edge.get("mark_id") or "")
    if mark is None:
        out.update({"live": False, "role": "", "label": "", "epistemic": "",
                    "sources": [], "source_ref": "",
                    "missing_reason": "the relation this edge names is no longer in the ledger"})
        return out
    provenance = mark.get("provenance") or {}
    out.update({
        "live": True,
        "role": str(mark.get("role") or ""),
        "label": str(mark.get("label") or ""),
        # M5's word for what kind of knowing this is. Read from the mark, never decided here.
        "epistemic": str(mark.get("epistemic_status") or ""),
        "source_ref": str(mark.get("source_ref") or ""),
        # Both sides, which is what makes a cross-image claim checkable at all.
        "sources": list(provenance.get("sources") or []),
        "missing_reason": None,
    })
    return out


def hydrate_edges(doc: Mapping[str, Any],
                  posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [hydrate_edge(e, posts) for e in (doc.get("edges") or []) if isinstance(e, Mapping)]


# The edge-purity check lives in `atlas_service.assert_no_percept_data` alongside the node one, so
# it runs on EVERY save path that already existed rather than only on the routes C3 added. Named
# here too because this is the module a reader comes to for what an edge is.
from backend.services.atlas_service import assert_no_percept_data  # noqa: E402


# ── the gesture ──────────────────────────────────────────────────────────────

def relate(pairs: Sequence[Tuple[str, Mapping[str, Any]]], *,
           source_node: str, target_node: str,
           relation_role: str = "", left_ref: str = "", right_ref: str = "",
           run_id: str = "", loop: Any = None,
           registry_for: Any = None) -> Dict[str, Any]:
    """Invoke M1's `compare_views` over the two images a writer joined.

    Returns `{"relation": <suggestion>}` or `{"refused": {...}}` — never both, never neither. The
    caller commits; this function writes nothing, so a refusal costs nothing and a success can
    still be rejected upstream.

    Every judgement here belongs to somebody else: `resolve_corpus` decides whether the step may
    be placed, `compare_views` decides whether a relation can be named, and `epistemics.stamp`
    (inside the actuator) decides what kind of knowing it is. What this function owns is the
    corpus of exactly two, the committed-marks context, and the translation of either outcome
    into one shape.
    """
    posts = {str(pid): dict(post or {}) for pid, post in pairs}
    corpus = build_relation_corpus(pairs)
    memory = hydrate_corpus(corpus, posts)

    params: Dict[str, Any] = {}
    if relation_role:
        params["relation_role"] = relation_role
    if left_ref:
        params["left_ref"] = left_ref
    if right_ref:
        params["right_ref"] = right_ref

    step = Step(actuator=RELATE_ACTUATOR, params=params, id=RELATE_STEP_ID,
                note="a relation a writer drew on the Atlas")
    plan = resolve_corpus([step], memory, intention="name the relation between these two images",
                          planner="atlas_c3")

    refused = refusal_from_plan(plan, source_node=source_node, target_node=target_node)
    if refused is not None:
        return {"refused": refused}

    ctx = build_relation_context(corpus, posts, run_id=run_id, loop=loop)
    try:
        result = run_corpus_plan(plan, memory, ctx, registry_for=registry_for,
                                 chain_id="atlas_c3")
        produced = [s for s in ctx.all_suggestions()
                    if isinstance(s, Mapping) and s.get("type") == "relation_mark"]
        refused = refusal_from_result(result, produced,
                                      source_node=source_node, target_node=target_node)
        if refused is not None:
            return {"refused": refused}
        return {"relation": dict(produced[-1])}
    finally:
        ctx.close()


def committed_relation(relation: Mapping[str, Any], *, mark_id: str = "",
                       now: str = "") -> Dict[str, Any]:
    """The produced relation → the mark that goes into the ledger.

    The gesture IS the commitment. A writer dragging one specific percept onto another specific
    percept has done the deciding a review step would otherwise ask for, so the relation is
    committed rather than quarantined — which is why `source` becomes `user_confirmed` and not
    `model_suggested`. What the model contributed (the wording of the relation, when it named one)
    stays visible in `provenance`, so the record never pretends a person wrote the phrase.

    `cross_image` and `spans` ride along untouched. M1 keeps cross-image relations out of any one
    post's quarantine precisely so a comparison never reads as something found in one photograph;
    a mark that lands in a post's list must therefore carry, in its own data, the fact that it does
    not belong to that frame alone.
    """
    stamp = now or utc_now()
    mark = dict(relation)

    # WHAT KIND OF KNOWING THIS IS, from M5's own function and not from a judgement made here.
    # `_run_compare_views` is the one relation minter that does not call `epistemics.stamp` — its
    # siblings `connect_marks` and `compose_percept` both do — so a comparative relation reaches
    # the quarantine with no status and would render with an empty chip. Fixing that inside the
    # actuator is another gate's business; what C3 does is call the SAME public API on the way to
    # the ledger. `stamp` refuses to overwrite an existing status, so the day `compare_views`
    # starts stamping its own output this call silently becomes a no-op rather than a conflict.
    #
    # The status follows the descriptor's `producer` (`semantic_read`, the frozen relation minter)
    # → `interpretive`. A named relation between two marks is a reading of two measurements, which
    # is exactly what `ACTUATOR_EPISTEMIC_CEILING` says `compare_views` can reach.
    from backend.services import epistemics
    epistemics.stamp(mark)

    mark["id"] = mark_id or new_mark_id()
    mark["source"] = "user_confirmed"
    mark["status"] = "committed"
    mark["created_at"] = mark.get("created_at") or stamp
    mark["updated_at"] = stamp
    provenance = dict(mark.get("provenance") or {})
    provenance["committed_by"] = "atlas_c3_draw"
    mark["provenance"] = provenance
    return mark


async def commit_relation_to_posts(mark: Mapping[str, Any], post_ids: Sequence[str], *,
                                   collection=None) -> List[str]:
    """Append the committed relation to each endpoint post's `visual_marks`. Returns the ids written.

    `$push`, and NOTHING ELSE. Never `{"$set": {"visual_marks": [...]}}`: that is a REPLACE, and a
    replace on this field has already destroyed committed regions in this codebase — a producer
    wrote back a list assembled from stale state and twenty-four regions became twenty-two, with no
    backup that covered it. An append cannot do that. It is also why this does not read the array
    first: there is no read to go stale.

    THE SAME MARK ID IN BOTH POSTS. One relation is one fact. Two ids for it would leave the Atlas
    edge referencing one of them and the other orphaned in the ledger, and a later reader counting
    relations would find two where a writer drew one.
    """
    posts = collection
    if posts is None:
        from backend.database import post_collection as posts

    from bson.errors import InvalidId
    from bson.objectid import ObjectId

    written: List[str] = []
    for raw in post_ids:
        query: Dict[str, Any]
        try:
            query = {"_id": ObjectId(str(raw))}
            if await posts.count_documents(query, limit=1) == 0:
                query = {"_id": str(raw)}
        except (InvalidId, TypeError):
            query = {"_id": str(raw)}
        res = await posts.update_one(query, {"$push": {"visual_marks": dict(mark)}})
        if getattr(res, "matched_count", 0):
            written.append(str(raw))
    return written
