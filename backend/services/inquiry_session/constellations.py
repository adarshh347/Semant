"""Preserve intent and inspect structural survival. No model or canonical artifact writes."""
from hashlib import sha256

from backend.schemas.inquiry_interaction import graph_hash
from backend.schemas.semantic_constellation import (
    AlternativeInput, Candidate, GraphPin, Inspection, SemanticConstellation,
    SemanticConstellations, SourceAnchor, PreservationJudgment,
)
from backend.services.semantic_compilation import ids as semantic_ids
from . import ids


def latest(session):
    rows = {}
    for row in session.semantic_constellations.history if session.semantic_constellations else ():
        rows[row.constellation_id] = row
    return rows


def compiler_entered(session):
    return bool(session.graph) or any(s.stage.value == "compiler" and s.outcome.value != "queued"
                                      for s in session.stages)


def preparation_paused(session):
    ext = session.semantic_constellations
    return bool(ext and ext.preparation in ("prompt", "compiler"))


def source_options(session):
    reading = session.reading.get("reading") or session.graph.get("reading") or {}
    return [{"origin": "user_prompt", "source_id": "prompt", "text": session.prompt,
             "author": "user", "image_refs": [p.post_id for p in session.posts]},
            *[{"origin": "model_reading", "source_id": b["block_id"], "text": b["text"],
               "author": "scene_theorist", "image_refs": b.get("image_refs", [])}
              for b in reading.get("blocks", [])]]


def validate_anchors(session, inputs):
    sources = {(s["origin"], s["source_id"]): s for s in source_options(session)}
    result = []
    for anchor in inputs:
        source = sources.get((anchor.origin, anchor.source_id))
        start, end = anchor.span
        if not source or source["text"][start:end] != anchor.exact_text:
            raise ValueError("exact source anchor does not resolve against stored text")
        result.append(SourceAnchor(**anchor.model_dump(), author=source["author"],
                                   source_sha256=sha256(source["text"].encode()).hexdigest(),
                                   image_refs=source["image_refs"]))
    return result


def _append(session, row):
    ext = session.semantic_constellations or SemanticConstellations()
    return session.model_copy(update={"semantic_constellations": ext.model_copy(
        update={"history": [*ext.history, row]})})


def _revise(row, *, at, actor, reason, **changes):
    return SemanticConstellation.model_validate({**row.model_dump(), **changes,
        "revision": row.revision + 1, "previous_revision": row.revision,
        "revised_at": at, "revision_actor": actor, "revision_reason": reason})


def capture(session, thought, *, at, constellation_id="", expected_revision=0):
    rows = latest(session)
    old = rows.get(constellation_id)
    if (constellation_id and old is None) or expected_revision != (old.revision if old else 0):
        raise ValueError("stale or unknown constellation revision")
    if thought.authorship.kind == "model" and not thought.confirmed_by:
        raise ValueError("this pilot requires a human-authored or human-confirmed question")
    anchors = validate_anchors(session, thought.anchors)
    cid = constellation_id or ids.constellation_id(session.session_id, len(rows) + 1)
    alternatives = [AlternativeInput(**{**a.model_dump(), "alternative_id": a.alternative_id or
        semantic_ids.alternative_id(session.inquiry_id or session.session_id, cid, a.text)})
        for a in thought.alternatives]
    if len({a.alternative_id for a in alternatives}) != len(alternatives):
        raise ValueError("alternative IDs must be distinct")
    changes = {**thought.model_dump(), "anchors": anchors, "alternatives": alternatives,
               "status": "reviewed" if thought.confirmed_by else "proposed"}
    # Any edit after compiler entry is retrospective. The earlier capture stays in history.
    timing = "retrospective" if compiler_entered(session) else "before_compilation"
    if old:
        row = _revise(old, at=at, actor=thought.confirmed_by or thought.authorship.actor,
                      reason="edit", **changes, timing=timing,
                      captured_checkpoint=session.checkpoint, inspection=None,
                      confirmed_claim_refs=[], rejected_claim_refs=[], confirmed_edge_refs=[],
                      rejected_edge_refs=[], membership_reviewed_by=None,
                      judgment=PreservationJudgment())
    else:
        row = SemanticConstellation(**changes, constellation_id=cid, session_id=session.session_id,
            inquiry_id=session.inquiry_id, revision=1, created_at=at, revised_at=at,
            revision_actor=thought.confirmed_by or thought.authorship.actor, revision_reason="capture",
            captured_checkpoint=session.checkpoint, timing=timing)
    session = _append(session, row)
    return reconcile(session, at=at) if session.graph else session


def inspect(session, row):
    graph = session.graph
    units = {u["source_unit_id"]: u for u in graph.get("source_units", [])}
    atoms = {a["atom_id"]: a for a in graph.get("semantic_atoms", [])}
    claims = {c["claim_id"]: c for c in graph.get("claims", [])}
    problems, selected = set(), set()
    if graph.get("inquiry_id") != session.inquiry_id:
        raise ValueError("graph belongs to a different inquiry")
    for anchor in row.anchors:
        source = next((s for s in source_options(session)
                       if s["origin"] == anchor.origin and s["source_id"] == anchor.source_id), None)
        if not source or sha256(source["text"].encode()).hexdigest() != anchor.source_sha256:
            problems.add(f"source_changed_or_missing:{anchor.source_id}")
            continue
        matched = set()
        for uid, unit in units.items():
            if unit.get("source_ref") != anchor.source_id:
                continue
            if anchor.origin == "user_prompt" and unit.get("kind") == "prompt_clause":
                span = unit.get("span")
                if span and session.prompt[span[0]:span[1]] == unit.get("exact_quote") \
                        and max(span[0], anchor.span[0]) < min(span[1], anchor.span[1]):
                    matched.add(uid)
            elif anchor.origin == "model_reading" and unit.get("kind") == "reading_block":
                source = next((s for s in source_options(session)
                               if s["origin"] == anchor.origin and s["source_id"] == anchor.source_id), None)
                if source and unit.get("exact_quote") == source["text"].strip():
                    matched.add(uid)
        selected.update(matched)
        if not matched:
            problems.add(f"anchor_without_source_unit:{anchor.source_id}:{anchor.span}")

    # Walk each root independently: a visited node terminates cycles, but cannot poison another
    # root's ancestry cache. This also handles a diamond with one missing branch honestly.
    candidates = []
    for cid in sorted(claims):
        atom_refs, ancestors, source_refs = set(), set(), set()
        pending = [(cid, ())]
        visited = set()
        while pending:
            current, path = pending.pop()
            if current in path:
                problems.add("inference_cycle:" + "->".join((*path, current)))
                continue
            if current in visited:
                continue
            visited.add(current)
            claim = claims.get(current)
            if claim is None:
                problems.add(f"missing_claim:{current}")
                continue
            if current != cid:
                ancestors.add(current)
            for ref in claim.get("atom_refs", []):
                atom = atoms.get(ref)
                if atom is None:
                    problems.add(f"missing_atom:{current}:{ref}")
                    continue
                atom_refs.add(ref)
                for uid in atom.get("source_unit_ids", []):
                    if uid not in units:
                        problems.add(f"missing_source_unit:{ref}:{uid}")
                    else:
                        source_refs.add(uid)
            pending.extend((parent, (*path, current)) for parent in claim.get("inferred_from", []))
        if source_refs & selected:
            candidates.append(Candidate(claim_ref=cid, reason="source_atom_lineage",
                source_unit_refs=sorted(source_refs), atom_refs=sorted(atom_refs),
                inference_refs=sorted(ancestors),
                image_refs=sorted({i for uid in source_refs for i in units[uid].get("image_refs", [])})))
    primary = {c.claim_ref for c in candidates}
    used_atoms = {ref for candidate in candidates for ref in candidate.atom_refs}
    for uid in sorted(selected):
        anchored = {aid for aid, atom in atoms.items() if uid in atom.get("source_unit_ids", [])}
        if not anchored:
            problems.add(f"source_unit_without_atom:{uid}")
        for aid in sorted(anchored - used_atoms):
            problems.add(f"atom_without_claim:{aid}")
    neighbours = {}
    valid_edges = []
    for edge in graph.get("claim_edges", []):
        a, b = edge["from_claim"], edge["to_claim"]
        if a not in claims or b not in claims:
            problems.add(f"missing_edge_endpoint:{edge['edge_id']}")
            continue
        valid_edges.append(edge)
        for neighbour, other in ((a, b), (b, a)):
            if other in primary and neighbour not in primary:
                neighbours.setdefault(neighbour, []).append(edge["edge_id"])
    candidates.extend(Candidate(claim_ref=cid, reason="immediate_graph_neighbour",
                                via_edge_refs=sorted(refs)) for cid, refs in sorted(neighbours.items()))
    all_ids = {c.claim_ref for c in candidates}
    if not candidates:
        problems.add("zero_matching_claims")
    if not units:
        problems.add("source_ledger_not_recorded")
    return Inspection(graph=GraphPin(graph_id=graph.get("graph_id", ""), graph_hash=graph_hash(graph),
        schema_version=graph.get("schema_version", ""), inquiry_id=session.inquiry_id,
        session_revision=session.revision, checkpoint=session.checkpoint),
        source_unit_refs=sorted(selected), candidates=candidates, candidate_count=len(candidates),
        candidate_edge_refs=sorted(e["edge_id"] for e in valid_edges
                                   if e["from_claim"] in all_ids and e["to_claim"] in all_ids),
        narrowing_required=len(candidates) > 8, missing_links=sorted(problems))


def reconcile(session, *, at):
    """Bind once, as a new revision. Old inspections are never rebound to another graph."""
    if not session.graph:
        return session
    for row in latest(session).values():
        if row.inspection is None:
            row = _revise(row, at=at, actor="semantic_constellation/lineage-v1", reason="inspection",
                          inquiry_id=session.inquiry_id, inspection=inspect(session, row))
            session = _append(session, row)
    return session


def review(session, cid, body, *, at):
    row = latest(session).get(cid)
    if not row or row.revision != body.expected_constellation_revision:
        raise ValueError("stale or unknown constellation revision")
    inspection = row.inspection
    if not inspection or body.graph_hash != inspection.graph.graph_hash \
            or body.graph_hash != graph_hash(session.graph):
        raise ValueError("inspection graph is absent or stale; old references remain pinned")
    candidates = {c.claim_ref for c in inspection.candidates}
    edges = set(inspection.candidate_edge_refs)
    for accepted, rejected, available in (
        (body.confirmed_claim_refs, body.rejected_claim_refs, candidates),
        (body.confirmed_edge_refs, body.rejected_edge_refs, edges),
    ):
        if set(accepted) & set(rejected) or not (set(accepted) | set(rejected)) <= available:
            raise ValueError("membership references must be disjoint candidates in the pinned graph")
    for edge in session.graph.get("claim_edges", []):
        if edge["edge_id"] in body.confirmed_edge_refs and not \
                {edge["from_claim"], edge["to_claim"]} <= set(body.confirmed_claim_refs):
            raise ValueError("confirm both endpoints before confirming an internal relation")
    judgment = PreservationJudgment(**{**body.judgment.model_dump(),
        "assessed_by": body.actor if body.judgment.value != "not_assessed" else None,
        "at": at if body.judgment.value != "not_assessed" else None})
    row = _revise(row, at=at, actor=body.actor, reason="human_review", judgment=judgment,
        membership_reviewed_by=body.actor, **{k: getattr(body, k) for k in (
            "confirmed_claim_refs", "rejected_claim_refs", "confirmed_edge_refs", "rejected_edge_refs")})
    return _append(session, row)


def continue_preparation(session):
    ext = session.semantic_constellations
    if not ext or ext.preparation not in ("prompt", "compiler"):
        raise ValueError("this session is not paused for thought preparation")
    if not any(r.status == "reviewed" and r.timing == "before_compilation"
               for r in latest(session).values()):
        raise ValueError("save and confirm a thought before continuing")
    phase = "reading" if ext.preparation == "prompt" else "released"
    return session.model_copy(update={"semantic_constellations": ext.model_copy(
        update={"preparation": phase})})


def projection(session):
    ext = session.semantic_constellations
    current_hash = graph_hash(session.graph) if session.graph else None
    return {"recorded": ext is not None, "schema_version": "semantic-constellations.v1",
        "preparation": ext.preparation if ext else "not_requested",
        "paused": preparation_paused(session),
        "history": [r.model_dump(mode="json") for r in ext.history] if ext else [],
        "current": [{**r.model_dump(mode="json"),
                     "graph_stale": bool(r.inspection and r.inspection.graph.graph_hash != current_hash)}
                    for r in latest(session).values()],
        "sources": source_options(session)}
