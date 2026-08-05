"""
WAVE2 Lane M — the movement kernel: carry a way of seeing from one image to another.

The smallest thing that could prove the thesis. Take a relation MEASURED in image A, find where it
also holds in image B, record that crossing as an edge along a named axis — and then use the axis
to place a THIRD image nobody compared to either, for measured reasons. If the third placement
works, the system has authored a retrievable dimension of perception rather than a lookup table of
resemblances.

## The pipeline, and what each stage is allowed to conclude

    seed        the organ MEASURES nesting in A                  → `measured`
    propose     the retina offers candidates in other images     → similarity, NOT a relation
    map         structure-mapping checks the relation is shared  → a hypothesis, not grounding
    ground      the organ MEASURES nesting in B                  → `measured`
    write       Lane G stores the edge, citing the organ's mark  → status DERIVED from the mark
    place       the axis proposes; the organ measures            → `measured`

The ordering is the argument. Each stage may only narrow the search; **only the organ may
conclude**. The retina cannot promote a similarity into a relation because `structure_map` stands
between them; the structure-mapper cannot promote a mapping into a grounding because `_ground`
re-measures on the far image before anything is written; and no stage can write a status onto an
edge, because Lane G refuses to store one and derives it from the mark instead.

## The mark is the grounding, and this lane writes no marks to posts

Lane G's contract: an edge stores `mark_id` and never `epistemic_status`; `hydrate_movement_edge`
reads what kind of knowing it is off the mark, every time. So a `measured` movement requires a
`measured` mark — and the organ mints exactly one, from the measurement it just made.

Those marks are **returned, never committed**. Committing to a post is a curator's act and this
lane performs none, which is the whole meaning of suggestions-only. That has a real and instructive
consequence, reported rather than papered over: an edge whose mark is not in the ledger hydrates as
`live: False`. So `run_kernel` hydrates twice — against the posts as they are, and against the
posts plus its own proposed marks — and reports both. The gap between those two readings is
precisely the human act this lane is not entitled to perform. See the findings note.

## What is persisted

The axis and the edges, through Lane G, into the `atlases` and `movement_axes` collections. Never
a post. `assert_posts_unchanged` hashes every post before and after and raises if a byte moved.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence
from uuid import uuid4

from backend.services import nestedness_organ as organ
from backend.services import structure_map as sm
from backend.services.movement_graph import (INITIAL_WEIGHT, assert_valid_movement_edge,
                                             hydrate_movement_edge, movement_edge_entry, utc_now)
from backend.services.nestedness_organ import AXIS_NESTEDNESS, RELATION_NESTED_WITHIN

KERNEL_STEP_ID = "wave2_lane_m:nestedness"

#: How many retina candidates to consider per seed. Small on purpose: the retina is peripheral
#: vision and this is a kernel. A wide sweep would bury the one thing being demonstrated.
DEFAULT_K = 12

#: Sentinel post ids the hygiene lane purged. Checked anyway — a movement grounded to a post that
#: does not exist is worse than no movement, and the cost of the guard is one set lookup.
SENTINEL_POST_IDS = frozenset({"s", "scratch-in-memory", "scratch", ""})


class PostsMutated(Exception):
    """A post changed during a kernel run. The one thing this lane must never do."""


def posts_fingerprint(posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, str]:
    """A hash per post document — the evidence for 'byte-identical', not the claim."""
    out = {}
    for pid, post in (posts or {}).items():
        blob = json.dumps(post, sort_keys=True, default=str).encode()
        out[str(pid)] = hashlib.sha256(blob).hexdigest()
    return out


def assert_posts_unchanged(before: Mapping[str, str], after: Mapping[str, str]) -> None:
    moved = sorted({p for p in {*before, *after} if before.get(p) != after.get(p)})
    if moved:
        raise PostsMutated(
            f"posts changed during a kernel run: {moved}. This lane produces suggestions and "
            "edges; a mark reaching a post means an accept path ran that nobody authorised.")


def _regions(post: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [dict(r) for r in (post.get("region_annotations") or []) if isinstance(r, Mapping)]


def _region(post: Mapping[str, Any], region_id: str) -> Optional[Dict[str, Any]]:
    for r in _regions(post):
        if str(r.get("id")) == str(region_id):
            return r
    return None


def _label(post: Mapping[str, Any], region_id: str) -> str:
    """A region's label — for the TRANSCRIPT only.

    Never for a decision. Every gate in this kernel runs on geometry and structure; the labels are
    here so a person can read what happened, and if one of them ever reaches a conditional the
    organ has stopped being the thing that concludes.
    """
    r = _region(post, region_id) or {}
    return str(r.get("label") or r.get("category") or region_id)


def _node_id(post_id: str, region_id: str) -> str:
    """The Atlas node a movement endpoint names.

    `region_id` alone is refused by construction: census §4 — `seg_0` / `arch_n` ids are positional
    and unique only within a post, so an endpoint carrying one would be silently repointed by the
    next re-dissect. The pair is the identity.
    """
    return f"vm_{post_id}:{region_id}"


# ── stage 1: seed ────────────────────────────────────────────────────────────

def seed(post: Mapping[str, Any], *, region_id: str = "", min_index: float = 0.0
         ) -> Dict[str, Any]:
    """Find (or verify) a MEASURED nesting in image A. The only way into the pipeline.

    With `region_id`, measures that region against its tightest measurable container and raises if
    there is none. Without one, sweeps the image and takes the strongest nesting it can measure.

    Nothing downstream can run without this: there is no path into `_ground` or `write_edge` that
    does not start from a measurement made here.
    """
    post_id = str(post.get("_id") or post.get("id") or "")
    regions = _regions(post)
    pairs = organ.find_nested_pairs(regions, min_index=min_index)
    if not pairs:
        raise organ.NestednessRefusal(
            f"no measurable nesting in post {post_id} ({len(regions)} regions) — this image cannot "
            "seed a nestedness movement")

    if region_id:
        mine = [m for m in pairs if str(m["inner_region_id"]) == str(region_id)]
        if not mine:
            raise organ.NestednessRefusal(
                f"region {region_id!r} in post {post_id} is not measurably nested in anything")
        part_id = str(region_id)
    else:
        part_id = str(pairs[0]["inner_region_id"])

    structure = sm.relational_structure(regions, part_id, measurements=pairs)

    # THE MEASUREMENT MUST BE THE STRUCTURE'S OWN PARENT, not the highest-scoring pair.
    # These come apart, and the first real run is what showed it: a temple finial scored 0.992
    # against `Sky` (a tiny thing inside a huge one) and 0.800 against `Temple Spire`, so the mark
    # would have cited nesting-in-sky while the skeleton the structure-mapper aligned was
    # nesting-in-spire. An edge whose grounding and whose analogy describe different relations is
    # not a movement, it is two facts stapled together. `relational_structure` picks the TIGHTEST
    # container; the measurement follows it.
    measurement = structure.get("parent_measurement")
    if measurement is None:
        raise organ.NestednessRefusal(
            f"region {part_id!r} in post {post_id} is not measurably nested in anything")
    return {
        "post_id": post_id,
        "region_id": measurement["inner_region_id"],
        "container_id": measurement["outer_region_id"],
        "measurement": measurement,
        "structure": structure,
        "all_measurements": pairs,
        "labels": {"part": _label(post, measurement["inner_region_id"]),
                   "whole": _label(post, measurement["outer_region_id"])},
    }


# ── stage 2: propose (the retina) ────────────────────────────────────────────

def propose(seeded: Mapping[str, Any], *, k: int = DEFAULT_K, store=None,
            retina_module=None) -> Dict[str, Any]:
    """Ask the retina where else to look. Candidates, explicitly not relations.

    Returns the envelope rather than a bare list so a cold or unavailable index stays
    distinguishable from "looked and found nothing" — the retina's own rule, kept here because a
    kernel that read an unbuilt index as "nothing is near this" would report a false negative about
    the corpus.
    """
    from backend.services import retina as _retina
    retina_module = retina_module or _retina

    envelope = retina_module.propose_candidates(
        region_id=str(seeded["region_id"]), post_id=str(seeded["post_id"]),
        k=int(k), exclude_post_id=str(seeded["post_id"]), store=store)

    kept, skipped = [], []
    for c in envelope.get("candidates") or []:
        if str(c.get("post_id")) in SENTINEL_POST_IDS:
            skipped.append({**c, "skipped": "sentinel post id"})
            continue
        kept.append(c)
    return {**envelope, "candidates": kept, "skipped_candidates": skipped}


# ── stage 3+4: map, then ground ──────────────────────────────────────────────

def consider(seeded: Mapping[str, Any], candidate: Mapping[str, Any],
             candidate_post: Mapping[str, Any], *,
             min_systematicity: float = sm.MIN_SYSTEMATICITY) -> Dict[str, Any]:
    """One candidate, all the way to a verdict: mapped-and-grounded, or refused with a reason.

    WHERE THE LANE CARD'S ORDERING BREAKS, and it is worth knowing. The card stages this as
    "structure-map, THEN ground": check the relation is relational, and only then point the
    instrument. That ordering cannot be strict, and the first real run made it obvious — **you
    cannot map a relational skeleton you have not already measured.** Asking whether the far image
    has a `nested_within` relation at all IS a measurement. So what actually happens is:

        measure the far image's skeleton  →  map it against the near one  →  re-measure the
        specific mapped pair, and THAT measurement is the one the mark cites

    The mapping still does the work the card wants from it: a candidate whose skeleton is empty is
    refused as `surface_only` before any pair is singled out, and the organ's own threshold — not
    the mapper — decides whether a containment counts as nesting. What changes is only the claim
    about ordering, which was never true.

    The `ungrounded` branch below is therefore a CONSISTENCY GUARD, not a common path: the
    re-measurement re-derives a pair the sweep already measured as nested, so it can only disagree
    if the organ is non-deterministic or the geometry moved underneath it. It is kept, and tested
    by injection, because an organ that contradicted itself between two calls is exactly the kind
    of thing that must stop a write rather than be averaged away.
    """
    cand_post_id = str(candidate.get("post_id"))
    cand_region_id = str(candidate.get("region_id"))
    regions = _regions(candidate_post)

    # The organ's reading of the FAR image, computed before any mapping so the skeleton the mapper
    # aligns against is made of measurements rather than of assumptions.
    far_pairs = organ.find_nested_pairs(regions)
    target_structure = sm.relational_structure(regions, cand_region_id, measurements=far_pairs)

    verdict = sm.structure_map(seeded["structure"], target_structure,
                               min_systematicity=min_systematicity)
    base = {
        "candidate": dict(candidate),
        "retina_score": candidate.get("score"),
        "target_structure": target_structure,
        "structure_map": verdict,
        "labels": {"part": _label(candidate_post, cand_region_id),
                   "whole": _label(candidate_post, target_structure.get("parent_id") or "")},
    }
    if not sm.mapped(verdict):
        return {**base, "status": "refused", "reason": verdict["reason"],
                "detail": verdict["detail"], "measurement": None, "mark": None}

    # GROUNDING. The mapper said where to point the instrument; this is the instrument.
    inner = _region(candidate_post, cand_region_id)
    outer = _region(candidate_post, target_structure["parent_id"])
    try:
        measurement = organ.measure(inner, outer)
    except organ.NestednessRefusal as e:
        return {**base, "status": "refused", "reason": "ungrounded",
                "detail": f"structure mapped but the organ could not measure it: {e}",
                "measurement": None, "mark": None}
    if not measurement["nested"]:
        return {**base, "status": "refused", "reason": "ungrounded",
                "detail": (f"the organ measured this pair and it is NOT nested "
                           f"({measurement['detail']}) — a mapping is not a grounding"),
                "measurement": measurement, "mark": None}

    return {**base, "status": "grounded", "reason": "", "detail": measurement["detail"],
            "measurement": measurement,
            "mark": organ.measured_mark(measurement, post_id=cand_post_id,
                                        step_id=KERNEL_STEP_ID)}


# ── stage 5: the edge ────────────────────────────────────────────────────────

def movement_from(seeded: Mapping[str, Any], considered: Mapping[str, Any], *,
                  axis_ref: str = AXIS_NESTEDNESS, now: str = "") -> Dict[str, Any]:
    """A grounded crossing → the movement edge Lane G stores, plus the marks it rests on.

    `mark_id` is the FAR mark: the edge's grounding is the measurement that established the
    relation holds over there, which is the thing the crossing actually discovered. The near mark
    is returned alongside because both must be committed for the edge to read as `measured`, and a
    caller handed only one would commit half of what its edge cites.

    Sets no `epistemic_status` and no provenance — Lane G forbids both on an edge and derives them
    from the mark. Sets all six movement fields explicitly, which is Lane G's declare-and-set rule:
    an unset field is dropped by the hydrator and gone.
    """
    if str(considered.get("status")) != "grounded":
        raise ValueError("only a grounded candidate becomes a movement — "
                         f"this one is {considered.get('status')!r} ({considered.get('reason')!r})")

    stamp = now or utc_now()
    near_mark = organ.measured_mark(seeded["measurement"], post_id=seeded["post_id"],
                                    step_id=KERNEL_STEP_ID, now=stamp)
    far_mark = dict(considered["mark"])
    far_mark["created_at"] = far_mark.get("created_at") or stamp

    source_node = _node_id(seeded["post_id"], seeded["region_id"])
    target_node = _node_id(str(considered["candidate"]["post_id"]),
                           str(considered["candidate"]["region_id"]))

    edge = movement_edge_entry(
        mark_id=str(far_mark["id"]),
        source_node=source_node, target_node=target_node,
        spans=[seeded["post_id"], str(considered["candidate"]["post_id"])],
        axis_ref=axis_ref,
        systematicity=sm.systematicity_score(considered["structure_map"]),
        weight=INITIAL_WEIGHT,
        observations=[{
            "epistemic_status": "measured", "at": stamp,
            "run_id": None, "step_id": KERNEL_STEP_ID,
            "detail": considered["measurement"]["detail"],
        }],
        now=stamp)
    assert_valid_movement_edge(edge)
    return {"edge": edge, "near_mark": near_mark, "far_mark": far_mark,
            "source_node": source_node, "target_node": target_node}


def overlay_posts(posts: Mapping[str, Mapping[str, Any]],
                  marks: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Posts as they WOULD be if the proposed marks were committed — in memory, never saved.

    This is how the kernel shows what its edges mean without performing the commit it is not
    entitled to perform. Hydrating against this says `measured`; hydrating against the real posts
    says the mark is not in the ledger. Both are true statements about different worlds, and the
    run reports both rather than picking the flattering one.
    """
    out = {str(pid): dict(post) for pid, post in (posts or {}).items()}
    for mark in marks or []:
        pid = str(mark.get("post_id") or "")
        if pid not in out:
            continue
        out[pid] = {**out[pid], "visual_marks": [*(out[pid].get("visual_marks") or []), dict(mark)]}
    return out


# ── stage 6: the proof — place a third, unseen image ─────────────────────────

def place(third_post: Mapping[str, Any], atlas_doc: Mapping[str, Any], *,
          axis_id: str = AXIS_NESTEDNESS, region_id: str = "",
          posts: Optional[Mapping[str, Mapping[str, Any]]] = None,
          store=None, retina_module=None, seeded: Optional[Mapping[str, Any]] = None,
          min_systematicity: float = sm.MIN_SYSTEMATICITY) -> Dict[str, Any]:
    """THE MILESTONE. Put a never-compared image on the axis, and only for measured reasons.

    Two questions are asked and kept apart, because conflating them is the failure this whole lane
    is arranged against:

      · **the axis** — `retrieve_along_axis` — "what stands in THIS relation to it". Its `unknown`
        (a cold axis) and `empty` (an axis with movements, none touching this candidate) are
        carried through verbatim; collapsing either into `[]` would make an unbuilt axis look like
        a disconnected image.
      · **the organ** — does nesting actually hold in this image? This, and ONLY this, decides
        placement.

    So `placed` is true iff the organ measured it. The axis and the retina are recorded in the
    result as what *proposed* the look; `placed_by` is always the organ, and a test asserts that a
    high retina score cannot place an unmeasured candidate.
    """
    from backend.services.movement_store import retrieve_along_axis

    post_id = str(third_post.get("_id") or third_post.get("id") or "")
    regions = _regions(third_post)
    pairs = organ.find_nested_pairs(regions)

    # What the ORGAN finds, independently of anything proposing it.
    if region_id:
        mine = [m for m in pairs if str(m["inner_region_id"]) == str(region_id)]
        measurement = mine[0] if mine else None
    else:
        measurement = pairs[0] if pairs else None

    candidate_region = str(measurement["inner_region_id"]) if measurement else str(region_id)
    node_id = _node_id(post_id, candidate_region) if candidate_region else ""

    axis_answer = retrieve_along_axis(atlas_doc, axis_id, {"node_id": node_id},
                                      posts=posts or {})

    # `not_asked` rather than None. There being no region to ask about is a FACT about this image,
    # and a bare None would leave a reader unable to tell it from a retina that was asked and said
    # nothing — the same collapse the retina's own envelope exists to prevent, one level up.
    retina_answer: Dict[str, Any] = {
        "status": "not_asked", "candidates": [],
        "reason": "no region in this image stands in a measurable nesting relation, so there is "
                  "no region id to ask the retina about"}
    if candidate_region:
        try:
            from backend.services import retina as _retina
            rm = retina_module or _retina
            retina_answer = rm.propose_candidates(region_id=candidate_region, post_id=post_id,
                                                  k=5, exclude_post_id=post_id, store=store)
        except Exception as e:                        # noqa: BLE001 — a proposal is never required
            # The organ decides placement, so a dead index costs a proposal and never a placement.
            retina_answer = {"status": "error", "reason": str(e), "candidates": []}

    structure = (sm.relational_structure(regions, candidate_region, measurements=pairs)
                 if candidate_region else None)
    mapping = None
    if seeded is not None and structure is not None:
        mapping = sm.structure_map(seeded["structure"], structure,
                                   min_systematicity=min_systematicity)

    placed = bool(measurement and measurement.get("nested"))
    return {
        "post_id": post_id,
        "region_id": candidate_region,
        "node_id": node_id,
        "placed": placed,
        # The one field that says what did the placing. Never the retina, never the axis.
        "placed_by": organ.ORGAN if placed else None,
        "basis": (measurement or {}).get("basis"),
        "measurement": measurement,
        "structure": structure,
        "structure_map": mapping,
        "axis": axis_answer,
        "retina": retina_answer,
        "mark": (organ.measured_mark(measurement, post_id=post_id, step_id=KERNEL_STEP_ID)
                 if placed else None),
        "labels": ({"part": _label(third_post, candidate_region),
                    "whole": _label(third_post, (structure or {}).get("parent_id") or "")}
                   if candidate_region else {}),
        "detail": ((measurement or {}).get("detail") if placed
                   else "the organ measured no nesting in this image — nothing to place"),
    }


async def run_kernel(*, post_a: Mapping[str, Any], posts: Mapping[str, Mapping[str, Any]],
                     third_post: Optional[Mapping[str, Any]] = None,
                     region_id: str = "", third_region_id: str = "",
                     k: int = DEFAULT_K, max_movements: int = 1,
                     atlas_id: str = "", persist: bool = False,
                     store=None, retina_module=None,
                     collection=None, axis_collection=None,
                     min_systematicity: float = sm.MIN_SYSTEMATICITY,
                     now: str = "") -> Dict[str, Any]:
    """The whole kernel, end to end. Returns the run transcript.

    `posts` supplies every document the run may read, keyed by post id — injected rather than
    fetched so the entire pipeline is exercisable with no Mongo, no network and no GPU. The real
    run loads them and hands them in.

    `persist=False` (the default) runs everything and writes nothing: the edge is minted and
    VALIDATED through Lane G's own `assert_valid_movement_edge`, so a dry run proves the same
    contract a stored one would. `persist=True` writes the axis and the edges through Lane G,
    which touches the `atlases` and `movement_axes` collections and no post.

    Posts are hashed before and after regardless. Suggestions-only is a claim this function checks
    rather than makes.
    """
    stamp = now or utc_now()
    before = posts_fingerprint(posts)
    transcript: Dict[str, Any] = {"step_id": KERNEL_STEP_ID, "at": stamp,
                                  "axis_ref": AXIS_NESTEDNESS,
                                  "relation": RELATION_NESTED_WITHIN}

    # ── 1. seed ──
    seeded = seed(post_a, region_id=region_id)
    transcript["seed"] = seeded

    # ── 2. propose ──
    proposal = propose(seeded, k=k, store=store, retina_module=retina_module)
    transcript["retina"] = proposal

    # ── 3+4. map, then ground ──
    considered: List[Dict[str, Any]] = []
    for candidate in proposal.get("candidates") or []:
        cand_post = posts.get(str(candidate.get("post_id")))
        if not cand_post:
            considered.append({"candidate": dict(candidate), "status": "refused",
                               "reason": "unreadable_post",
                               "detail": "the candidate's post was not supplied to this run",
                               "measurement": None, "mark": None})
            continue
        considered.append(consider(seeded, candidate, cand_post,
                                   min_systematicity=min_systematicity))
    transcript["considered"] = considered

    grounded = [c for c in considered if c["status"] == "grounded"]
    transcript["refused"] = [c for c in considered if c["status"] != "grounded"]
    transcript["surface_only_refusals"] = [
        c for c in considered if c.get("reason") == sm.REFUSED_SURFACE_ONLY]

    # ── 5. the edges ──
    movements = [movement_from(seeded, c, now=stamp) for c in grounded[:max(1, int(max_movements))]]
    transcript["movements"] = movements
    proposed_marks = [m for mv in movements for m in (mv["near_mark"], mv["far_mark"])]
    transcript["proposed_marks"] = proposed_marks

    # ── persist: the axis and the edges. Never a post. ──
    transcript["persisted"] = {"axis": None, "edges": [], "atlas_id": str(atlas_id)}
    if persist and movements:
        from backend.services.movement_store import write_axis, write_edge
        axis = await write_axis(
            name="nestedness", relation_kind=RELATION_NESTED_WITHIN, axis_id=AXIS_NESTEDNESS,
            grounded_instances=[mv["edge"]["edge_id"] for mv in movements],
            now=stamp, collection=axis_collection)
        transcript["persisted"]["axis"] = axis
        for mv in movements:
            edge = mv["edge"]
            doc = await write_edge(
                atlas_id, mark_id=edge["mark_id"], source_node=edge["source_node"],
                target_node=edge["target_node"], spans=edge["spans"],
                axis_ref=edge["axis_ref"], systematicity=edge["systematicity"],
                weight=edge["weight"], now=stamp, collection=collection)
            transcript["persisted"]["edges"].append(
                {"written": doc is not None,
                 "minted_edge_id": edge["edge_id"],
                 **_stored_delta(edge, doc)})

    # ── the two readings ──
    transcript["hydrated"] = [hydrate_both_ways(mv["edge"], posts, proposed_marks)
                              for mv in movements]

    # ── 6. the third image ──
    if third_post is not None:
        atlas_doc = ({"edges": [mv["edge"] for mv in movements]}
                     if not persist or not atlas_id
                     else (await _load_atlas(atlas_id, collection)) or
                          {"edges": [mv["edge"] for mv in movements]})
        transcript["placement"] = place(
            third_post, atlas_doc, region_id=third_region_id,
            posts=overlay_posts(posts, proposed_marks), store=store,
            retina_module=retina_module, seeded=seeded,
            min_systematicity=min_systematicity)

    assert_posts_unchanged(before, posts_fingerprint(posts))
    transcript["posts_unchanged"] = True
    return transcript


def _stored_delta(minted: Mapping[str, Any],
                  doc: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """What Lane G actually stored, and what it dropped on the way in.

    `write_edge` does not take a prepared edge — it takes the six values it has parameters for and
    RE-MINTS one. So `edge_id` changes and anything the kernel set that has no parameter
    (`observations`, `valid_from`, `valid_to`) is silently replaced by a fresh default.

    That is reported rather than smoothed over. Lane G's own docstring names silent field-dropping
    as the trap this whole contract exists to avoid ("a re-observed edge came back looking as
    though it had never been measured"), and the same trap is open one level up at its own front
    door. The kernel cannot fix it from here — `movement_store` is not this lane's file — so it
    makes the loss visible instead of writing a transcript that implies the observation survived.
    """
    if doc is None:
        return {"stored_edge_id": None, "discarded": [], "detail": "no such atlas"}
    stored = None
    for edge in reversed(list(doc.get("edges") or [])):
        if str(edge.get("mark_id") or "") == str(minted.get("mark_id") or ""):
            stored = edge
            break
    if stored is None:
        return {"stored_edge_id": None, "discarded": [],
                "detail": "the write returned a document with no edge citing this mark"}
    discarded = []
    for field in ("edge_id", "observations", "valid_from", "valid_to"):
        if minted.get(field) != stored.get(field):
            discarded.append({"field": field, "minted": minted.get(field),
                              "stored": stored.get(field)})
    return {
        "stored_edge_id": str(stored.get("edge_id") or ""),
        "discarded": discarded,
        "detail": ("write_edge re-mints rather than storing the prepared edge; these fields have "
                   "no parameter on its signature" if discarded else "stored as minted"),
    }


async def _load_atlas(atlas_id: str, collection=None) -> Optional[Dict[str, Any]]:
    from backend.services import atlas_service
    return await atlas_service.get_atlas(atlas_id, collection=collection)


def hydrate_both_ways(edge: Mapping[str, Any], posts: Mapping[str, Mapping[str, Any]],
                      marks: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """The edge as the ledger currently reads it, and as it would read with the marks committed.

    The gap between these two is the human act this lane does not perform. Reporting only the
    second would claim a grounding nobody accepted; reporting only the first would hide that the
    measurement was really made.
    """
    return {
        "as_stored": hydrate_movement_edge(edge, posts),
        "with_proposed_marks": hydrate_movement_edge(edge, overlay_posts(posts, marks)),
    }
