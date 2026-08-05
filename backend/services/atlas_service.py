"""
ATLAS C1 — the Atlas document: arrangement, and nothing else.

The Atlas is the multi-image general case of the Chiasm: a pan/zoom canvas where the images of a
corpus coexist, their committed percepts show as overlays, and (later gates) the relations between
them are drawn as first-class edges and a writer node drafts on the same surface.

WHAT THIS MODULE IS FOR, AND WHAT IT DELIBERATELY IS NOT. It is a THIN persistence layer over
infrastructure that already exists. The corpus is M1's (`director/corpus.py`); the percepts are the
ledger's; the comparative relation is `compare_views`; the plan is M2's; the prose is M3's. None of
that is re-implemented here and none of it is imported here. This module stores *where things sit*.

THE ONE INVARIANT WORTH READING TWICE. **The Atlas document holds no percept data.** A node carries
a `post_id` and four numbers. Every overlay a curator sees is hydrated from the post document at
read time by `atlas_view`. That is not a storage optimisation — it is what makes a stale Atlas
document harmless. A canvas that had COPIED a percept could disagree with the ledger about what was
seen, and would do so silently, months later, in a document that looks authoritative. This one
cannot disagree because it makes no claim: `assert_no_percept_data` is a real function and a test
calls it on every stored document.

SPATIAL POSITION ASSERTS NOTHING. Two nodes side by side are a writer thinking, not a relation
claimed. Nothing in this module derives meaning from adjacency, and nothing downstream may either —
only a drawn edge (a real `compare_views` percept, C3) asserts a relation. `edges` stays empty at
C1 rather than being seeded from proximity, which is the tempting and wrong shortcut.

THERE IS NO PERSISTED CORPUS TO POINT AT, so `corpus_ref` names one of the two things that actually
exist on main: an explicit list of post ids (what `POST /runs` itself takes), or a run whose stored
spec already names them. Either resolves to an ordered tuple of post ids, which is what M1's
`build_corpus` consumes. Inventing a corpus collection would have been a fifth place a corpus can
be defined, and the one that nothing else reads.

PURE WHERE IT CAN BE. Every shaping decision — the default grid, merging an arrangement, building
the view — is a module-level function with no database and no clock, so the interesting behaviour
is testable without Mongo. The async functions at the bottom are the thin store.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services import cross_image

CONTRACT_VERSION = 1

# How a corpus can be named. Both resolve to an ordered tuple of post ids; neither invents one.
CORPUS_POSTS = "posts"      # the curator listed the images
CORPUS_RUN = "run"          # the images a stored run spanned

# The default grid a fresh Atlas lays its images out on, in canvas units. Generous gaps because the
# first gesture on a new canvas is almost always to drag things apart, and a tight grid reads as an
# arrangement somebody chose.
NODE_W = 420
NODE_H = 320
GRID_COLS = 3
GRID_GAP_X = 120
GRID_GAP_Y = 140

# Sources that mean "a person put this here, or vouched for it". A `model_suggested` mark is
# quarantined and has no business on a post document — but if one ever lands there, the Atlas shows
# committed evidence only and SAYS how many it withheld, rather than quietly drawing a suggestion
# as though a curator had accepted it.
COMMITTED_SOURCES = frozenset({"user", "user_confirmed", "model_refined", "system",
                               "imported", "fixture"})
QUARANTINED_SOURCE = "model_suggested"

# Refusal reasons this module can return. A closed set, like `plan.py`'s — a refusal a caller
# cannot branch on is a string, not a contract.
REFUSED_UNKNOWN_NODE = "unknown_node"       # the arrangement named a node this Atlas does not hold
REFUSED_BAD_POSITION = "bad_position"       # a coordinate that is not a finite number
REFUSED_BAD_NOTE = "bad_note"               # a note with no text, or text that is not text
REFUSED_TOO_MANY_NOTES = "too_many_notes"   # past the per-node ceiling; the surplus is dropped

# T1 — author notes. The writer's freehand one-liners under an image: "the light does the arguing
# here", "compare with the rotunda". Deliberately small.
#
# WHAT A NOTE IS NOT, and this is the whole design. A note is NOT a percept, NOT evidence, NOT
# citable, and it never enters the ledger — it lives in THIS document, next to the arrangement,
# because it is the same kind of thing as where a picture sits: the writer's own thinking aid. It
# carries no epistemic status, because the five-way vocabulary describes how well something is
# GROUNDED, and a note claims nothing to ground. Giving it `uncertain` would be worse than giving
# it nothing: it would enter the epistemic system at the bottom rung rather than staying outside it.
#
# The two lanes never merge. A machine read may only produce a quarantined percept proposal, and
# may never write here; a note may never be promoted into a percept. Neither direction has code.
MAX_NOTES_PER_NODE = 12
MAX_NOTE_CHARS = 280


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "atlas") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _out(doc: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Mongo doc → API shape: `_id` becomes `id`, nothing else touched. Same convention as
    `manuscript_service`, so the two stores do not read differently for no reason."""
    if doc is None:
        return None
    out = dict(doc)
    out["id"] = out.pop("_id", None)
    return out


# ── the corpus reference ─────────────────────────────────────────────────────

def normalize_corpus_ref(raw: Any) -> Dict[str, Any]:
    """Whatever the caller sent → the canonical `{kind, post_ids, run_id}`.

    Tolerant of a bare list (the common case: "these five images"), which is why it exists as a
    function rather than a schema default. Duplicate post ids are collapsed while KEEPING ORDER —
    order is evidence in M1, and the same photograph twice is one image in two positions, which is
    a corpus this gate does not model.
    """
    kind = CORPUS_POSTS
    run_id = None
    raw_ids: Sequence[Any] = ()

    if isinstance(raw, Mapping):
        kind = str(raw.get("kind") or CORPUS_POSTS)
        run_id = raw.get("run_id") or None
        raw_ids = raw.get("post_ids") or raw.get("image_ids") or ()
    elif isinstance(raw, (list, tuple)):
        raw_ids = raw

    seen: Dict[str, None] = {}
    for pid in raw_ids:
        text = str(pid).strip()
        if text:
            seen.setdefault(text, None)

    if kind not in (CORPUS_POSTS, CORPUS_RUN):
        kind = CORPUS_POSTS
    return {"kind": kind, "post_ids": list(seen.keys()),
            "run_id": str(run_id) if run_id else None}


def post_ids_from_run(run_doc: Optional[Mapping[str, Any]]) -> List[str]:
    """The images a stored run spanned, in the run's own order.

    Prefers the run's VIEW (what the run actually resolved to, after tags expanded and unreadable
    ids were dropped) over its spec (what was asked for). A corpus assembled from the request would
    put a node on the canvas for an image the run could never read.
    """
    if not run_doc:
        return []
    view = run_doc.get("view") or {}
    corpus = view.get("corpus") or []
    ids = [str(i.get("post_id")) for i in corpus
           if isinstance(i, Mapping) and i.get("post_id")]
    if ids:
        return list(dict.fromkeys(ids))
    spec = run_doc.get("spec") or {}
    return list(dict.fromkeys(str(i) for i in (spec.get("image_ids") or []) if i))


# ── the arrangement ──────────────────────────────────────────────────────────

def _finite(value: Any) -> Optional[float]:
    """A coordinate, or None if it is not a real number. `float('nan')` is not a position, and
    storing one would put a node somewhere React Flow cannot draw and nobody can drag back."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def default_nodes(post_ids: Sequence[str], *, cols: int = GRID_COLS) -> List[Dict[str, Any]]:
    """A fresh Atlas's opening arrangement: the corpus in reading order, on a grid.

    Reading order, not a clever layout — the sequence a curator built IS an argument (M1's "order
    is evidence"), and a canvas that opened with the images auto-clustered by similarity would be
    asserting a relation before anyone drew one.
    """
    out: List[Dict[str, Any]] = []
    per_row = max(1, int(cols))
    for i, pid in enumerate(post_ids):
        row, col = divmod(i, per_row)
        out.append({
            "node_id": f"n{i}",
            "post_id": str(pid),
            "x": float(col * (NODE_W + GRID_GAP_X)),
            "y": float(row * (NODE_H + GRID_GAP_Y)),
            "w": float(NODE_W),
            "h": float(NODE_H),
            # T1: the author-notes slot, empty. Present from the start so "no notes yet" and "an
            # older document that predates notes" are the same shape to every reader.
            "notes": [],
        })
    return out


def merge_nodes(existing: Sequence[Mapping[str, Any]],
                incoming: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply an arrangement to the nodes an Atlas holds. Returns `(nodes, refused)`.

    POSITION ONLY. `post_id` is never taken from the incoming payload — a save that could
    repoint a node at a different photograph would let the canvas quietly relabel evidence, and
    the drag gesture this serves has no business changing which image a node is.

    An unknown `node_id` is REFUSED and reported, not created. A canvas that silently accreted
    nodes from whatever a client posted would drift from its corpus with nothing saying so.
    """
    by_id = {str(n.get("node_id")): dict(n) for n in existing}
    refused: List[Dict[str, Any]] = []

    for patch in incoming or []:
        if not isinstance(patch, Mapping):
            continue
        node_id = str(patch.get("node_id") or "")
        target = by_id.get(node_id)
        if target is None:
            refused.append({"node_id": node_id, "reason": REFUSED_UNKNOWN_NODE,
                            "detail": "this Atlas holds no such node"})
            continue
        moved = dict(target)
        bad: List[str] = []
        for key in ("x", "y", "w", "h"):
            if key not in patch:
                continue
            value = _finite(patch.get(key))
            if value is None:
                bad.append(key)
                continue
            moved[key] = value
        if bad:
            refused.append({"node_id": node_id, "reason": REFUSED_BAD_POSITION,
                            "detail": f"not a finite number: {', '.join(bad)}"})
            continue
        by_id[node_id] = moved

    # Preserve the document's own node order — it is the corpus order, and a save should not
    # reshuffle the sequence because a client happened to send two nodes.
    ordered = [by_id[str(n.get("node_id"))] for n in existing]
    return ordered, refused


# ── the author notes (T1) ────────────────────────────────────────────────────

def new_note_id() -> str:
    return f"note_{uuid4().hex[:10]}"


def clean_note(raw: Any) -> Optional[Dict[str, str]]:
    """A note as this document is willing to store it: `{note_id, text}` and nothing else.

    WHITELISTED, NOT SANITISED. Every other key a client sends is DROPPED rather than inspected —
    a note that arrived carrying `geometry`, `epistemic_status` or `source` would be a percept
    wearing a note's name, and the way to make that impossible is to build the stored dict from
    two known fields instead of editing the incoming one. `assert_no_percept_data` then has
    nothing to find, because nothing else was ever copied across.

    Empty text is not a note. A blank slot is how a curator DELETES one, and storing it would
    leave an invisible row that reappears as a stray empty line on the next load.
    """
    if isinstance(raw, str):
        raw = {"text": raw}
    if not isinstance(raw, Mapping):
        return None
    text = raw.get("text")
    if not isinstance(text, str):
        return None
    text = text.strip()[:MAX_NOTE_CHARS]
    if not text:
        return None
    note_id = str(raw.get("note_id") or "").strip() or new_note_id()
    return {"note_id": note_id, "text": text}


def merge_notes(existing: Sequence[Mapping[str, Any]],
                incoming: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Apply author notes to the nodes an Atlas holds. Returns `(nodes, refused)`.

    NOTES ONLY, and the mirror of `merge_nodes`'s discipline: this touches no coordinate and
    `merge_nodes` touches no note, so neither gesture can quietly perform the other. The slot is
    replaced wholesale — the client sends the node's full list, exactly as a drag sends the node's
    full position — which is what makes editing and deleting one save path instead of three.

    An unknown node is refused and reported, never created; a note past the ceiling is dropped and
    SAID, because a curator who typed a thirteenth one and saw it vanish silently would reasonably
    conclude the whole slot is unreliable.
    """
    by_id = {str(n.get("node_id")): dict(n) for n in existing}
    refused: List[Dict[str, Any]] = []

    for patch in incoming or []:
        if not isinstance(patch, Mapping):
            continue
        node_id = str(patch.get("node_id") or "")
        target = by_id.get(node_id)
        if target is None:
            refused.append({"node_id": node_id, "reason": REFUSED_UNKNOWN_NODE,
                            "detail": "this Atlas holds no such node"})
            continue

        raw_notes = patch.get("notes")
        if raw_notes is None or not isinstance(raw_notes, (list, tuple)):
            refused.append({"node_id": node_id, "reason": REFUSED_BAD_NOTE,
                            "detail": "notes must be a list"})
            continue

        cleaned: List[Dict[str, str]] = []
        dropped = 0
        for item in raw_notes:
            note = clean_note(item)
            if note is None:
                dropped += 1
                continue
            cleaned.append(note)

        if dropped:
            refused.append({"node_id": node_id, "reason": REFUSED_BAD_NOTE,
                            "detail": f"{dropped} note{'' if dropped == 1 else 's'} had no text"})

        if len(cleaned) > MAX_NOTES_PER_NODE:
            refused.append({
                "node_id": node_id, "reason": REFUSED_TOO_MANY_NOTES,
                "detail": f"an image holds at most {MAX_NOTES_PER_NODE} notes; "
                          f"{len(cleaned) - MAX_NOTES_PER_NODE} not saved"})
            cleaned = cleaned[:MAX_NOTES_PER_NODE]

        updated = dict(target)
        updated["notes"] = cleaned
        by_id[node_id] = updated

    ordered = [by_id[str(n.get("node_id"))] for n in existing]
    return ordered, refused


# ── the document ─────────────────────────────────────────────────────────────

def new_atlas_doc(*, atlas_id: str, corpus_ref: Any, post_ids: Sequence[str],
                  title: str = "", now: Optional[str] = None) -> Dict[str, Any]:
    """The document an Atlas starts as. Pure — no clock it is not handed, no database."""
    stamp = now or utc_now()
    return {
        "_id": atlas_id,
        "contract_version": CONTRACT_VERSION,
        "title": str(title or ""),
        "corpus_ref": normalize_corpus_ref(corpus_ref),
        "nodes": default_nodes(post_ids),
        # C3 fills this with the ids of real comparative percepts. Empty is not "no relations
        # found" — it is "none drawn", and the distinction is the whole reason edges are explicit.
        "edges": [],
        # C4's accepted argument. Null until a writer accepts one. Kept SEPARATE from `edges` on
        # purpose: an edge is a relation somebody produced, a plan is structure somebody proposed,
        # and a document that stored them in one list would have no way left to tell them apart.
        "plan": None,
        # C5's writer node. Null until a draft exists; a draft is a quarantined suggestion.
        "draft": None,
        "created_at": stamp,
        "updated_at": stamp,
    }


# Keys that would mean the document had started copying percept truth. Checked, not commented —
# a discipline nobody can violate by accident is worth twelve lines.
_FORBIDDEN_NODE_KEYS = frozenset({
    "geometry", "grounds", "marks", "regions", "percepts", "strokes", "mask", "box",
    "photo_url", "image_url", "epistemic_status", "provenance",
})


# T1: what a note may contain. A whitelist, not a blacklist — the guard on the notes slot is
# stricter than the guard on the node, because a note is free text a client composes and is
# therefore the most inviting place for percept data to arrive wearing a disguise.
_ALLOWED_NOTE_KEYS = frozenset({"note_id", "text"})


# The same rule for C3's relation edges. An edge names a committed relation by id and says which
# two nodes it runs between; what the relation SAYS — its role, its label, what kind of knowing it
# is — belongs to the ledger and is read back at view time. An edge that cached the label could
# disagree with the ledger about what was named, in a document that looks authoritative.
_FORBIDDEN_EDGE_KEYS = frozenset({
    "geometry", "label", "role", "epistemic_status", "provenance", "sources", "mask", "points",
})


def assert_no_percept_data(doc: Mapping[str, Any]) -> None:
    """Raise if an Atlas document has begun to hold what the ledger holds.

    The Atlas stores arrangement and references. The moment a node carries geometry, this document
    can disagree with the ledger about what was seen — and a disagreement nobody is told about is
    worse than either answer. `photo_url` is on the list for the same reason: a cached image URL is
    a copy of the post's truth that goes stale when the post is re-uploaded.

    T1 extends the same check to the author-notes slot. Notes are the one place in this document
    where free-form content lives, so they are the one place a percept could plausibly be smuggled
    in — a note carrying `box` or `epistemic_status` would be evidence in a slot that renders as
    "not evidence", which is the exact confusion the two-lane rule exists to prevent.
    """
    for node in doc.get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        leaked = sorted(set(node.keys()) & _FORBIDDEN_NODE_KEYS)
        if leaked:
            raise ValueError(
                f"Atlas node '{node.get('node_id')}' carries percept data: {leaked}. "
                "The Atlas references the ledger by id; it never copies it.")

        for note in node.get("notes") or []:
            if not isinstance(note, Mapping):
                raise ValueError(
                    f"Atlas node '{node.get('node_id')}' has a note that is not a note.")
            extra = sorted(set(note.keys()) - _ALLOWED_NOTE_KEYS)
            if extra:
                raise ValueError(
                    f"Atlas node '{node.get('node_id')}' has an author note carrying {extra}. "
                    "An author note is {note_id, text} — it is not evidence and never becomes a "
                    "percept.")

    # C3 extends the same discipline to relation edges. An edge names a committed relation by id
    # and says which two nodes it runs between; what the relation SAYS is the ledger's and is read
    # back at view time. An edge that cached the label could disagree with the ledger about what
    # was named, silently, in a document that looks authoritative.
    for edge in doc.get("edges") or []:
        if not isinstance(edge, Mapping):
            continue
        leaked = sorted(set(edge.keys()) & _FORBIDDEN_EDGE_KEYS)
        if leaked:
            raise ValueError(
                f"Atlas edge '{edge.get('edge_id')}' carries percept data: {leaked}. "
                "An edge references the relation by id; it never copies it.")


# ── the view: the document, hydrated from the ledger at read time ────────────

def _committed(items: Any) -> Tuple[List[Dict[str, Any]], int]:
    """(committed items, how many quarantined ones were withheld).

    The count is returned rather than dropped so the surface can say "3 suggestions not shown"
    instead of showing a shorter list that looks complete.
    """
    kept: List[Dict[str, Any]] = []
    withheld = 0
    for item in items or []:
        if not isinstance(item, Mapping):
            continue
        source = str(item.get("source") or "user")
        if source == QUARANTINED_SOURCE:
            withheld += 1
            continue
        kept.append(dict(item))
    return kept, withheld


def hydrate_node(node: Mapping[str, Any],
                 post: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """One node + the post document somebody already read → what the canvas draws.

    An image that could NOT be read is not dropped from the canvas. It renders as a node that says
    so — the same discipline as `hydrate_corpus`'s `unreadable`, and for the same reason: "this
    image has no percepts" and "this image could not be loaded" are different facts, and a canvas
    that showed the second as the first would be lying by omission about the corpus's extent.
    """
    out = {k: node.get(k) for k in ("node_id", "post_id", "x", "y", "w", "h")}
    # T1: the author's own notes travel with the node, in both modes. They come from THIS document
    # rather than the post, which is the whole point — an unreadable image still carries whatever
    # the writer said about it, because a note is about the writer's thinking, not the ledger's
    # contents. They are cleaned on the way in, and re-cleaned here so a document written by an
    # older build cannot render anything but `{note_id, text}`.
    out["notes"] = [n for n in (clean_note(x) for x in node.get("notes") or []) if n]
    if post is None:
        out.update({"readable": False, "image_ref": "", "title": "",
                    "grounds": [], "regions": [], "marks": [], "percepts": [],
                    "relations": [], "withheld": 0,
                    "unreadable_reason": f"post:{node.get('post_id')} could not be read"})
        return out

    grounds, w1 = _committed(post.get("grounds"))
    committed_marks, w2 = _committed(post.get("visual_marks"))
    regions, _ = _committed(post.get("region_annotations"))
    percepts, w3 = _committed(post.get("percepts"))

    # THE CROSS-IMAGE GUARD (C3). A `compare_views` relation is committed into BOTH posts it
    # spans, so it is sitting right here in `visual_marks` — and it is not a finding about this
    # photograph. It is split out rather than dropped: a writer looking at the rotunda should be
    # able to learn it has been related to the façade, but the node's overlays and its caption
    # count must answer "what does THIS picture show", and the answer excludes it.
    marks, relations = cross_image.split_marks(committed_marks)

    out.update({
        "readable": True,
        "image_ref": str(post.get("photo_url") or ""),
        "title": str(post.get("instagram_handle") or post.get("domain") or ""),
        "grounds": grounds,
        "regions": regions,
        "marks": marks,
        "percepts": percepts,
        # Named separately and never added into any total on this node — a relation that spans
        # two images belongs to the sequence, not to either frame.
        "relations": relations,
        "withheld": w1 + w2 + w3,
        "unreadable_reason": None,
    })
    return out


def atlas_view(doc: Mapping[str, Any],
               posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """The stored arrangement + the ledger's current answer for each image.

    Assembled at READ time, every time. This is what makes the reference-not-copy rule pay: accept
    a percept in the Differential and the next load of the Atlas shows it, with nothing to migrate
    and no cache to invalidate.
    """
    nodes = [hydrate_node(n, posts.get(str(n.get("post_id")))) for n in doc.get("nodes") or []]
    unreadable = [n["post_id"] for n in nodes if not n["readable"]]
    return {
        "id": doc.get("_id") or doc.get("id"),
        "contract_version": doc.get("contract_version", CONTRACT_VERSION),
        "title": doc.get("title") or "",
        "corpus_ref": doc.get("corpus_ref") or normalize_corpus_ref(None),
        "nodes": nodes,
        "edges": list(doc.get("edges") or []),
        # C4. Absent on an Atlas created before plan mode, and `None` reads the same as "no plan
        # accepted yet" — which is what it is.
        "plan": doc.get("plan"),
        "draft": doc.get("draft"),
        "unreadable": unreadable,
        "updated_at": doc.get("updated_at"),
    }


# ── the store ────────────────────────────────────────────────────────────────

def _collection(collection=None):
    """The atlases collection, injectable. Tests hand a fake; production gets the real one.
    Imported lazily so this module can be exercised with no database configured at all."""
    if collection is not None:
        return collection
    from backend.database import atlas_collection
    return atlas_collection


async def create_atlas(*, corpus_ref: Any, post_ids: Sequence[str], title: str = "",
                       atlas_id: Optional[str] = None, now: Optional[str] = None,
                       collection=None) -> Dict[str, Any]:
    doc = new_atlas_doc(atlas_id=atlas_id or new_id(), corpus_ref=corpus_ref,
                        post_ids=post_ids, title=title, now=now)
    assert_no_percept_data(doc)
    await _collection(collection).insert_one(doc)
    return doc


async def get_atlas(atlas_id: str, *, collection=None) -> Optional[Dict[str, Any]]:
    return await _collection(collection).find_one({"_id": str(atlas_id)})


async def save_arrangement(atlas_id: str, nodes: Sequence[Mapping[str, Any]], *,
                           now: Optional[str] = None,
                           collection=None) -> Optional[Dict[str, Any]]:
    """Move nodes. Returns `{doc, refused}`, or None if there is no such Atlas.

    Refusals travel WITH the save rather than aborting it: dragging four nodes when one of them
    has gone stale should move the three that are real and say what happened to the fourth, not
    discard the gesture.
    """
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(atlas_id)})
    if doc is None:
        return None
    merged, refused = merge_nodes(doc.get("nodes") or [], nodes)
    stamp = now or utc_now()
    await coll.update_one({"_id": str(atlas_id)},
                          {"$set": {"nodes": merged, "updated_at": stamp}})
    doc = dict(doc)
    doc["nodes"] = merged
    doc["updated_at"] = stamp
    assert_no_percept_data(doc)
    return {"doc": doc, "refused": refused}


async def save_notes(atlas_id: str, notes: Sequence[Mapping[str, Any]], *,
                     now: Optional[str] = None,
                     collection=None) -> Optional[Dict[str, Any]]:
    """Save author notes. Returns `{doc, refused}`, or None if there is no such Atlas.

    The same shape and the same debounced idiom as `save_arrangement`, and deliberately a SEPARATE
    write: notes and positions travel on different routes so that neither request can perform the
    other's gesture. It is also the only write in the Atlas that stores something a person typed,
    which is why `assert_no_percept_data` runs before it is handed back.
    """
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(atlas_id)})
    if doc is None:
        return None
    merged, refused = merge_notes(doc.get("nodes") or [], notes)
    stamp = now or utc_now()
    doc = dict(doc)
    doc["nodes"] = merged
    doc["updated_at"] = stamp
    # Checked BEFORE the write, not after: a document that should not exist should not reach the
    # database and then be reported as a problem.
    assert_no_percept_data(doc)
    await coll.update_one({"_id": str(atlas_id)},
                          {"$set": {"nodes": merged, "updated_at": stamp}})
    return {"doc": doc, "refused": refused}


async def add_edge(atlas_id: str, edge: Mapping[str, Any], *,
                   now: Optional[str] = None, collection=None) -> Optional[Dict[str, Any]]:
    """Record a drawn relation (C3). Appends; never rewrites the list.

    `$push`, deliberately, and not a read-modify-`$set` of the whole array. Two writers drawing
    edges on the same Atlas at once would each have read the list before the other wrote, and the
    second `$set` would silently drop the first edge — the same class of loss that a wholesale
    array replace has already caused in this codebase once.
    """
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(atlas_id)})
    if doc is None:
        return None
    stamp = now or utc_now()
    entry = dict(edge)
    # Guarded BEFORE the write, on the document as it will be, so a bad edge never lands.
    assert_no_percept_data({**doc, "edges": [*(doc.get("edges") or []), entry]})
    await coll.update_one({"_id": str(atlas_id)},
                          {"$push": {"edges": entry}, "$set": {"updated_at": stamp}})
    doc = dict(doc)
    doc["edges"] = [*(doc.get("edges") or []), entry]
    doc["updated_at"] = stamp
    return doc


async def remove_edge(atlas_id: str, edge_id: str, *, now: Optional[str] = None,
                      collection=None) -> Optional[Dict[str, Any]]:
    """Take a relation off the canvas.

    THE LEDGER IS NOT TOUCHED. The committed relation stays exactly where it is; what is removed
    is this Atlas's reference to it. The Atlas never owned the percept, so it has no business
    deleting one — and a canvas gesture that quietly destroyed committed evidence is precisely the
    irreversible act this whole architecture is arranged to prevent.
    """
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(atlas_id)})
    if doc is None:
        return None
    stamp = now or utc_now()
    kept = [e for e in (doc.get("edges") or [])
            if not (isinstance(e, Mapping) and str(e.get("edge_id")) == str(edge_id))]
    await coll.update_one({"_id": str(atlas_id)},
                          {"$set": {"edges": kept, "updated_at": stamp}})
    doc = dict(doc)
    doc["edges"] = kept
    doc["updated_at"] = stamp
    return doc


async def save_plan(atlas_id: str, plan: Optional[Mapping[str, Any]], *,
                    now: Optional[str] = None, collection=None) -> Optional[Dict[str, Any]]:
    """Store the accepted argument plan (C4), or clear it with `None`.

    The plan is a WHOLE replacement rather than a merge. An argument is one structure — claims in
    an order, each bound or refused together — and patching it field by field would let a document
    end up holding half of one decomposition and half of another, with a `complete` flag computed
    from neither.

    Nothing about a post is touched here. The plan names images by post id and actuators by name;
    the ledger is not written, no percept is created, and no suggestion is accepted.
    """
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(atlas_id)})
    if doc is None:
        return None
    stamp = now or utc_now()
    stored = dict(plan) if plan else None
    await coll.update_one({"_id": str(atlas_id)},
                          {"$set": {"plan": stored, "updated_at": stamp}})
    doc = dict(doc)
    doc["plan"] = stored
    doc["updated_at"] = stamp
    assert_no_percept_data(doc)
    return doc


async def save_draft(atlas_id: str, draft: Optional[Mapping[str, Any]], *,
                     now: Optional[str] = None, collection=None) -> Optional[Dict[str, Any]]:
    """Store the quarantined article draft (C5), or clear it with `None`.

    A whole replacement, for the same reason the plan is: an article is one structure, and half of
    one composition beside half of another would carry an `epistemic` computed from neither.

    WHY THIS MAY HOLD GEOMETRY WHEN A NODE MAY NOT. `assert_no_percept_data` forbids a node from
    carrying geometry because a node REFERENCES a committed percept, and a copy of the ledger can
    silently disagree with it. A draft carries geometry for the opposite reason: the percepts its
    sentences rest on are the draft's OWN quarantined suggestions, produced by the run that
    composed it and committed nowhere. There is no ledger row for them to drift from. Dropping
    them would leave an article whose live percepts could never be drawn again — the export would
    show prose with empty figures beside it, which is precisely the unfalsifiable document this
    circuit exists to refuse.

    Nothing about a post is touched here. No percept is committed, no suggestion accepted.
    """
    coll = _collection(collection)
    doc = await coll.find_one({"_id": str(atlas_id)})
    if doc is None:
        return None
    stamp = now or utc_now()
    stored = dict(draft) if draft else None
    await coll.update_one({"_id": str(atlas_id)},
                          {"$set": {"draft": stored, "updated_at": stamp}})
    doc = dict(doc)
    doc["draft"] = stored
    doc["updated_at"] = stamp
    assert_no_percept_data(doc)
    return doc


async def list_atlases(*, limit: int = 20, collection=None) -> List[Dict[str, Any]]:
    cursor = _collection(collection).find({}).sort("created_at", -1).limit(limit)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        out.append(doc)
    return out
