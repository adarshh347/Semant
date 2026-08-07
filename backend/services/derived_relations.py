"""WAVE4.5 — one honest home for grounded relations, and the decision about where they live.

## The situation this resolves

The constellation lane counted the **durable** world and found fourteen edges. The scene lane's
cache holds **2,755**. Both numbers are right, and the gap is not an accounting error — it is two
different answers to a question nobody had asked out loud:

```
DERIVED (rebuildable)                     2755      nesting 1112 · adjacency 1630 · occlusion 13
                                                    2156 mask-basis · 599 box-basis
PERSISTED (durable)                         14      13 filed proposals · 1 Atlas movement edge
COMMITTED (a human accepted it)              0
```

## THE DECISION: derive the many, commit the few, and the reason is not queue size

The obvious argument for deriving is that 2,755 items would swamp a curator. True, and it is the
weaker argument. The real one:

**A derived relation is a pure function of its inputs** — the regions, the organs' thresholds, the
depth grid. Persisting one makes a second copy of a fact that is still being computed elsewhere,
and the two disagree the moment a parameter moves. That is not hypothetical: the occlusion count is
**5 at depth grid 32 and 13 at 192** (#168). Persist at one grid and you hold durable rows that the
organs would no longer produce, with nothing to tell a reader which is current.

That is PROV-001's two-copy drift at corpus scale, and the same reasoning that keeps
`epistemic_status` off a movement edge and off an agent's observation: **do not store a
conclusion you can recompute.**

So:

    the many    DERIVED into this store — rebuildable, stamped with what produced it, and never
                presented as durable. Rebuild after a threshold change and it is simply correct.
    the few     COMMITTED to the ledger by a person, through the curator surface, and only after
                being queued by the triage rule below.

## THE TRIAGE RULE, which turned out to be already in force

What is worth a human's attention? **A relation that contradicts another grounded relation.**
Routine agreement is not a curator's business: `cseg_stone_texture_4 nested_within
cseg_wall_surface_0` is measured, true, and nothing anybody needs to accept.

Measured on the corpus, the rule selects exactly the rows that carry `supersedes`:

```
carry `supersedes`   13   (all occlusions — each overturning a nesting)
do not             2742   (1112 nesting, 1630 adjacency)
                          → 0.47% of the derived world is worth queueing
```

**Those thirteen are precisely the thirteen already in the curator's queue.** The occlusion lane
applied this rule without stating it, and nothing else has ever been filed. This module states it,
makes it mechanical, and pins it — so the next producer does not have to guess, and so a lane that
starts filing routine agreement fails a test rather than quietly flooding the queue.

## The four origins, kept apart

A reader of this store must always be able to tell where a relation came from, because the four are
four different amounts of settled:

    derived     this store's rebuildable cache — a measurement nobody has filed
    proposal    filed in the curator's queue, awaiting a human
    atlas       a movement edge on an Atlas, whose own status comes off the mark it cites
    ledger      committed to a post's `visual_marks` by a person

`epistemic` is **re-derived from the recorded basis on every read** — the scene lane's rule, kept
whole. A hand-edited store cannot promote a box-basis relation to `measured`, because the basis is
data and the status is a conclusion, and the conclusion is recomputed.

`ledger_status` is `committed` only for the `ledger` origin. Nothing else in this module can
produce that word.

## What cannot enter

A candidate the retina proposed and the kernel refused. Not by a filter — by there being nowhere
for one to come from: this reads four named sources and a refusal was never written to any of them.
The constellation lane's structural scan-guard is preserved as a test over this module.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.services import scene_relations
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

#: Where a relation came from. Four values, never collapsed — see the module note.
ORIGIN_DERIVED = "derived"
ORIGIN_PROPOSAL = "proposal"
ORIGIN_ATLAS = "atlas"
ORIGIN_LEDGER = "ledger"

#: The two ledger states. Mirrored from `curator` so a reader of either surface does not have to
#: learn two words for one thing.
LEDGER_PROPOSED = "proposed"
LEDGER_COMMITTED = "committed"

#: Whether a relation is worth a curator's attention. ONE RULE, stated, and it is the one the
#: occlusion lane was already applying: a relation earns review by CONTRADICTING another grounded
#: relation. Everything else is the organs agreeing with themselves.
TRIAGE_CONTRADICTS = "contradicts_another_grounded_relation"
TRIAGE_ROUTINE = "routine"

TRIAGE_RULE = (
    "A derived relation is queued for a curator IF AND ONLY IF it contradicts another grounded "
    "relation — it carries `supersedes`. On this corpus that is 13 of 2,755 (0.47%): every "
    "occlusion, each overturning a nesting, and no nesting or adjacency at all. Routine agreement "
    "is not a curator's business, and a threshold would be a silent rule; this one is a property "
    "of the relation itself and can be checked by reading it."
)

DECISION = (
    "Derive the many, commit the few. A derived relation is a pure function of the regions, the "
    "organs' thresholds and the depth grid — the occlusion count is 5 at grid 32 and 13 at 192 — "
    "so persisting one makes a second copy of a fact still being computed elsewhere, and the two "
    "disagree the moment a parameter moves. Rebuildable is not a weaker kind of durable here; it "
    "is the only kind that cannot go stale without saying so."
)


def epistemic_for(basis: str) -> str:
    """The status a basis supports. Asked of `scene_relations` rather than restated, so this store
    cannot come to disagree with the ruling about what a box supports."""
    return scene_relations.epistemic_for(basis)


# ── the unified row ─────────────────────────────────────────────────────────

def relation(*, origin: str, kind: str, axis: str, relation_name: str,
             source_node: str, target_node: str, basis: str, organ: str,
             numbers: Optional[Mapping[str, Any]] = None,
             supersedes: Optional[Mapping[str, Any]] = None,
             stated_status: str = "", ledger_status: str = "",
             ref: str = "", detail: str = "") -> Dict[str, Any]:
    """One relation, in the one shape every view reads.

    NOTE what is computed rather than passed: `epistemic` from the basis, `queued` from the triage
    rule, `admissible` from the epistemic. All three are conclusions, and a store that let a caller
    supply them would be a place where a status could be edited into existence.

    `misstated` is the third case the scene lane found and must stay visible: a committed mark
    whose own stamp does not match what its basis supports. A view has to be able to show that as a
    contradiction rather than silently preferring one of the two answers.
    """
    supported = epistemic_for(basis)
    ledger = str(ledger_status or (LEDGER_COMMITTED if origin == ORIGIN_LEDGER
                                   else LEDGER_PROPOSED))
    return {
        "origin": str(origin),
        "kind": str(kind),
        "axis": str(axis),
        "relation": str(relation_name),
        "source_node": str(source_node),
        "target_node": str(target_node),
        "basis": str(basis),
        "organ": str(organ),
        "numbers": dict(numbers or {}),
        "supersedes": dict(supersedes) if supersedes else None,
        "ref": str(ref),
        "detail": str(detail),
        # ── the conclusions, recomputed every read ──
        "epistemic": supported,
        "ledger_status": ledger,
        "admissible": supported == EpistemicStatus.MEASURED.value,
        "misstated": bool(stated_status and stated_status != supported),
        "queued": bool(supersedes),
        "triage": TRIAGE_CONTRADICTS if supersedes else TRIAGE_ROUTINE,
    }


def node_id_for(post_id: str, region_id: str) -> str:
    """`vm_<post>:<region>` — the construction the kernel, the agents and the constellation all
    use. Two names for one place would split every traversal that touched it."""
    return f"vm_{post_id}:{region_id}"


# ── the four origins ────────────────────────────────────────────────────────

def from_derived_cache(payload: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    """The rebuildable cache → relations. The many.

    Rhyme is the one kind whose far end is in another image, so its target node is built from
    `target_post_id`; everything else is within its own scene.
    """
    data = dict(payload if payload is not None else scene_relations.load_cache())
    out: List[Dict[str, Any]] = []
    for post_id, scene in (data.get("scenes") or {}).items():
        for kind, rows in (scene.get("relations") or {}).items():
            for row in rows or []:
                far_post = str(row.get("target_post_id") or "") or str(post_id)
                out.append(relation(
                    origin=ORIGIN_DERIVED, kind=str(kind),
                    axis=str(row.get("axis") or ""),
                    relation_name=str(row.get("relation") or ""),
                    source_node=node_id_for(str(post_id), str(row.get("source") or "")),
                    target_node=node_id_for(far_post, str(row.get("target") or "")),
                    basis=str(row.get("basis") or ""),
                    organ=str(row.get("organ") or ""),
                    numbers=row.get("numbers"),
                    supersedes=row.get("supersedes"),
                    detail=str(row.get("detail") or "")))
    return out


def from_proposals(proposals: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The curator's queue → relations. The few, awaiting a human."""
    out: List[Dict[str, Any]] = []
    for proposal in proposals or []:
        subject = dict(proposal.get("subject") or {})
        evidence = dict(proposal.get("evidence") or {})
        mark = dict(proposal.get("mark") or {})
        post_id = str(proposal.get("post_id") or "")
        front, back = str(subject.get("front_region_id") or ""), str(subject.get("back_region_id") or "")
        if not (post_id and front and back):
            continue
        out.append(relation(
            origin=ORIGIN_PROPOSAL, kind="occlusion",
            axis=str(mark.get("axis") or "axis_occlusion"),
            relation_name=str(mark.get("role") or "in_front_of"),
            source_node=node_id_for(post_id, front), target_node=node_id_for(post_id, back),
            basis=str(evidence.get("basis") or ""),
            organ=str(proposal.get("producer") or ""),
            numbers={k: evidence.get(k) for k in
                     ("ordering_separation", "separation_floor", "ordering_ceiling", "depth_grid")
                     if k in evidence},
            supersedes=evidence.get("contradicts"),
            stated_status=str(mark.get(STATUS_KEY) or ""),
            ledger_status=(LEDGER_COMMITTED if proposal.get("committed_at") else LEDGER_PROPOSED),
            ref=str(proposal.get("proposal_id") or ""),
            detail=str(subject.get("claim") or "")))
    return out


def from_atlas(atlas_docs: Sequence[Mapping[str, Any]],
               posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Atlas movement edges → relations. Status derived from the cited mark, as Lane G requires.

    A movement whose mark nobody committed has `basis: ""` — there is nothing to read one off — and
    so `epistemic_for` returns `interpretive`, which would be a claim this edge is not entitled to
    make. `epistemic` is therefore set to `None` for that case: "this cannot tell you", which a
    reader must handle rather than fill in.
    """
    out: List[Dict[str, Any]] = []
    for doc in atlas_docs or []:
        for edge in doc.get("edges") or []:
            if not isinstance(edge, Mapping) or str(edge.get("kind") or "") != "movement":
                continue
            mark = _find_mark(posts, edge.get("spans") or [], str(edge.get("mark_id") or ""))
            measurement = dict((mark or {}).get("measurement") or {})
            row = relation(
                origin=ORIGIN_ATLAS, kind="nesting",
                axis=str(edge.get("axis_ref") or ""), relation_name="nested_within",
                source_node=str(edge.get("source_node") or ""),
                target_node=str(edge.get("target_node") or ""),
                basis=str(measurement.get("basis") or ""),
                organ="movement_kernel",
                numbers={"systematicity": edge.get("systematicity"),
                         "weight": edge.get("weight")},
                stated_status=str((mark or {}).get(STATUS_KEY) or ""),
                ledger_status=(LEDGER_COMMITTED if mark else LEDGER_PROPOSED),
                ref=str(edge.get("edge_id") or ""),
                detail=("the movement kernel grounded this crossing" if mark else
                        "the movement kernel grounded this crossing and the mark it cites is in "
                        "no ledger — so this relation cannot say what kind of knowing it is"))
            if mark is None:
                # NOT `interpretive`. There is no basis to read, and reporting the conservative
                # default would be this store making a claim on the edge's behalf.
                row["epistemic"] = None
                row["admissible"] = False
                row["misstated"] = False
            out.append(row)
    return out


def from_ledger(posts: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Committed relation marks → relations. The only fully-settled ones there are.

    Empty on this corpus, and that emptiness is the finding rather than a gap: nothing has been
    committed. The path exists so the first curator commit appears in every view at once.
    """
    out: List[Dict[str, Any]] = []
    for post_id, post in (posts or {}).items():
        for mark in post.get("visual_marks") or []:
            if not isinstance(mark, Mapping) or str(mark.get("type") or "") != "relation_mark":
                continue
            measurement = dict(mark.get("measurement") or {})
            a = str(measurement.get("front_region_id") or measurement.get("inner_region_id") or "")
            b = str(measurement.get("back_region_id") or measurement.get("outer_region_id") or "")
            if not (a and b):
                continue
            out.append(relation(
                origin=ORIGIN_LEDGER, kind=str(measurement.get("kind") or "committed"),
                axis=str(measurement.get("axis") or ""),
                relation_name=str(mark.get("role") or ""),
                source_node=node_id_for(post_id, a), target_node=node_id_for(post_id, b),
                basis=str(measurement.get("basis") or ""),
                organ=str((mark.get("provenance") or {}).get("producer") or ""),
                numbers={k: v for k, v in measurement.items() if isinstance(v, (int, float))},
                stated_status=str(mark.get(STATUS_KEY) or ""),
                ledger_status=LEDGER_COMMITTED,
                ref=str(mark.get("id") or ""),
                detail=str(mark.get("label") or "")))
    return out


def _find_mark(posts: Mapping[str, Mapping[str, Any]], spans: Sequence[str],
               mark_id: str) -> Optional[Dict[str, Any]]:
    for post_id in spans:
        for mark in (posts.get(str(post_id)) or {}).get("visual_marks") or []:
            if isinstance(mark, Mapping) and str(mark.get("id")) == str(mark_id):
                return dict(mark)
    return None


# ── the store ───────────────────────────────────────────────────────────────

async def load(*, posts_collection=None, atlas=None, proposals=None,
               derived: Optional[Mapping[str, Any]] = None,
               include_derived: bool = True) -> Dict[str, Any]:
    """Every grounded relation this system holds, from all four origins, in one shape.

    THE THREE NAMED SOURCES THE CONSTELLATION READ ARE NOW FOUR, IN ONE PLACE — and the fourth is
    the one that was missing: the derived cache the scene view had built and nothing else could
    see. That is why the constellation counted fourteen edges while 2,755 had been measured.

    `include_derived=False` gives the durable world alone, which is what makes the gap reportable
    rather than merely stated.
    """
    if posts_collection is None:
        from backend.database import post_collection as posts_collection
    if atlas is None:
        from backend.database import atlas_collection as atlas
    if proposals is None:
        from backend.database import curator_proposal_collection as proposals

    posts: Dict[str, Dict[str, Any]] = {}
    async for post in posts_collection.find({}):
        posts[str(post["_id"])] = post

    atlas_docs = [doc async for doc in atlas.find({})]
    filed = [doc async for doc in proposals.find({})]

    rows = [*from_ledger(posts), *from_proposals(filed), *from_atlas(atlas_docs, posts)]
    if include_derived:
        rows = [*from_derived_cache(derived), *rows]

    return {"relations": rows, "posts": posts,
            "cache": scene_relations.cache_status(derived)}


def census(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The 14-vs-2755 gap, counted rather than asserted — and the decision that resolves it.

    Reported BY ORIGIN and BY LEDGER STATUS, never as one total: "2,769 relations" would hide the
    entire point, which is that almost all of them are rebuildable and none of them is committed.
    """
    by_origin: Dict[str, int] = {}
    by_kind: Dict[str, int] = {}
    by_basis: Dict[str, int] = {}
    by_ledger: Dict[str, int] = {}
    for row in rows:
        for key, table in (("origin", by_origin), ("kind", by_kind),
                           ("basis", by_basis), ("ledger_status", by_ledger)):
            value = str(row.get(key) or "")
            table[value] = table.get(value, 0) + 1

    derived = [r for r in rows if r.get("origin") == ORIGIN_DERIVED]
    durable = [r for r in rows if r.get("origin") != ORIGIN_DERIVED]
    queued = [r for r in rows if r.get("queued")]

    return {
        "derived": len(derived),
        "durable": len(durable),
        "committed": sum(1 for r in rows if r.get("ledger_status") == LEDGER_COMMITTED),
        "queued_by_triage": len(queued),
        "queued_share": (round(100.0 * len(queued) / len(rows), 2) if rows else 0.0),
        "by_origin": dict(sorted(by_origin.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "by_basis": dict(sorted(by_basis.items())),
        "by_ledger_status": dict(sorted(by_ledger.items())),
        "decision": DECISION,
        "triage_rule": TRIAGE_RULE,
    }


def triage(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Which relations a curator should be shown, by the stated rule, with the rest counted.

    The `skipped` count is not decoration. A triage that reported only what it selected would be
    indistinguishable from one that found nothing else — and 2,742 routine relations is the fact
    that justifies having a rule at all.
    """
    selected = [r for r in rows if r.get("queued")]
    return {
        "rule": TRIAGE_RULE,
        "selected": selected,
        "selected_count": len(selected),
        "skipped_count": len(rows) - len(selected),
        "detail": (f"{len(selected)} of {len(rows)} relations contradict another grounded "
                   f"relation and are worth a human's attention. The other "
                   f"{len(rows) - len(selected)} are the organs agreeing with themselves."),
    }
