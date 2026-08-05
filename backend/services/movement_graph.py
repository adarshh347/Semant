"""
WAVE2 Lane G — movement edges and axes, as an EXTENSION of the Atlas, not a second graph.

The graph substrate already existed when this lane started. C3 built first-class relation edges in
`atlases.edges` — `{edge_id, kind, mark_id, source_node, target_node, spans, created_at}`, uuid
ids, and a real committed mark behind every one. So this module adds a `kind`, not a collection.
Opening a parallel edge store would have been the two-copy drift PROV-001 exists to fight, one
level up.

## The one rule everything here obeys: ids and endpoints, never percept truth

C3's discipline (`atlas_relation.edge_entry`, `atlas_service.assert_no_percept_data`) is that an
edge names a relation and says which two nodes it runs between; what the relation *says* — its
role, its label, what kind of knowing it is, whose run produced it — belongs to the ledger and is
read back by `hydrate_edge` on every view. `_FORBIDDEN_EDGE_KEYS` enforces it on every save path.

The first draft of this lane's card asked for `epistemic_status` and `provenance {run_id, step_id}`
ON the movement edge, *and* for "the two-copy drift must not reappear". Those are the same
contradiction: `assert_no_percept_data` would have raised on the first save, and weakening it to
let the write through would have created exactly the disagreement-with-the-ledger the guard was
built to prevent. **A movement edge's grounding IS its `mark_id`.** Measured-vs-interpretive and
run/step are read from that mark. The guard is untouched by this lane.

## What a movement edge therefore stores

The C3 spine, plus the fields that are genuinely the GRAPH's own state and exist nowhere in the
ledger — because they are facts about the edge across time, not facts about the relation:

    axis_ref        which discovered dimension this movement runs along
    systematicity   structure-map score: how much shared structure the relation carries
    weight          concentration — Hebbian, and only measurement moves it
    valid_from      when it began to hold
    valid_to        when a contradiction ended it (None while live)
    observations[]  the re-observation log the weight is derived from

None of those is a copy of anything. The mark cannot hold them: one mark is one relation, while
the weight is the graph's answer to "how often has this been re-measured", accumulated across runs
the mark knows nothing about.

## The declare-and-set rule, and why it applies to exactly those six

`post.percepts`/`post.grounds` go through `SoftFieldModel`, whose serializer emits only
`__pydantic_fields_set__` — a declared-but-unset field is dropped. Atlas edges are plain dicts
`$push`ed by `atlas_service.add_edge`, so nothing Pydantic-shaped drops them there; but
`hydrate_edge` rebuilds the view from a FIXED key list, and a field missing from that list is
dropped on the way out just as surely. So every movement field is **explicitly set at mint time**
(never left to a default) and **named in the hydrator's passthrough**. `movement_edge_entry` sets
all six unconditionally, including the ones whose honest value is `None`.

## Only measurement moves a weight

`strengthen` refuses anything but a `measured` observation. Agreement — two thinkers concurring, a
curator nodding, a second interpretive reading — does not move the number, because a graph that
strengthens on agreement is a graph that learns what it already believes. This is the honesty floor
in its stigmergic form, and `test_movement_graph_laneg.py` pins it.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import uuid4

from backend.services.atlas_service import assert_no_percept_data
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

MOVEMENT_CONTRACT_VERSION = 1

#: The `kind` that marks an atlas edge as a movement. Sits beside C3's `relation` in the same
#: array; a reader branches on `kind`, exactly as C4's connectors are told apart by `binding`.
EDGE_MOVEMENT = "movement"

#: The six fields this lane adds. Named once, because three places must agree about them: the
#: minter (sets them all), the hydrator (passes them through), and the round-trip test (diffs them).
MOVEMENT_FIELDS: Tuple[str, ...] = (
    "axis_ref", "systematicity", "weight", "valid_from", "valid_to", "observations",
    # The two clocks the dynamics read. They are here because the first version of this module
    # wrote `last_measured_at` in `strengthen` WITHOUT declaring it — so the store carried it and
    # the hydrator dropped it, and a re-observed edge came back looking as though it had never
    # been measured. That is the declare-and-set trap this lane exists to name, caught by its own
    # round-trip test. Anything the dynamics write belongs on this tuple.
    "last_measured_at", "decayed_at",
)

#: What a fresh, once-measured movement is worth. Not 1.0: a single observation is a beginning, and
#: an edge that arrives at full strength has nowhere to grow and decays from a lie.
INITIAL_WEIGHT = 0.25

#: Hebbian increment per measured re-observation, applied toward the ceiling rather than added to
#: the total — so the tenth confirmation moves the number less than the second, which is what
#: "concentration" means and what stops a busy pair of images dominating the graph.
STRENGTHEN_RATE = 0.35
MAX_WEIGHT = 1.0

#: Slow evaporation. A day's half-life means a movement nobody re-measures for a week is at ~1% and
#: prunes; one re-measured daily holds. Slow enough that the graph is not a leaderboard of this
#: morning, fast enough that a one-off correlation genuinely fades — which is the "living" property
#: this lane is for.
DECAY_HALF_LIFE_SECONDS = 86_400.0

#: Below this an edge is noise. Pruning removes the ATLAS's reference; the mark in the ledger is
#: never touched, exactly as `atlas_service.remove_edge` promises.
PRUNE_FLOOR = 0.01

#: Why an edge stopped holding. A closed set, so a reader can branch (the rule `plan.py`,
#: `atlas_service` and `atlas_relation` all keep).
CONTRADICTION_KIND = "contradiction"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_axis_id() -> str:
    return f"axis_{uuid4().hex[:12]}"


def new_movement_edge_id() -> str:
    """Minted once, uuid-backed — never positional.

    Census §4: `fine_i` / `arch_n` / `cseg_*` region ids are positional and not even globally
    unique (the retina takes `region_id` WITH `post_id` for that reason). An edge keyed on one
    would be repointed by the next re-dissect, silently, which is the HW-C6 substitution hazard
    with a graph on top of it.
    """
    return f"edge_mv_{uuid4().hex[:12]}"


def new_contradiction_id() -> str:
    return f"contra_{uuid4().hex[:12]}"


# ── time, as a number the dynamics can use ───────────────────────────────────

def _parse(ts: Any) -> Optional[datetime]:
    """An ISO-8601 string → aware datetime, or None. Never raises: a malformed stamp must not take
    down a keeper tick that is otherwise doing useful work on every other edge."""
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if not isinstance(ts, str) or not ts.strip():
        return None
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def elapsed_seconds(since: Any, now: Any) -> float:
    """Seconds between two stamps, floored at zero.

    Floored because a clock that went backwards must not *strengthen* an edge. Decay is the only
    thing time is allowed to do here, so an impossible interval does nothing rather than something
    inverted.
    """
    a, b = _parse(since), _parse(now)
    if a is None or b is None:
        return 0.0
    return max(0.0, (b - a).total_seconds())


# ── the movement edge ────────────────────────────────────────────────────────

def is_movement_edge(edge: Any) -> bool:
    return isinstance(edge, Mapping) and str(edge.get("kind") or "") == EDGE_MOVEMENT


def movement_edge_entry(*, mark_id: str, source_node: str, target_node: str,
                        spans: Sequence[str], axis_ref: str,
                        systematicity: Optional[float] = None,
                        weight: float = INITIAL_WEIGHT,
                        observations: Optional[Sequence[Mapping[str, Any]]] = None,
                        valid_from: str = "", valid_to: Optional[str] = None,
                        edge_id: str = "", now: str = "") -> Dict[str, Any]:
    """One movement, as the Atlas document stores it.

    THE C3 SPINE IS BUILT HERE RATHER THAN IMPORTED, and that is not duplication: this asserts the
    same seven keys in the same shapes, so `test_movement_graph_laneg` can diff a movement edge
    against `atlas_relation.edge_entry`'s output and prove the two are one row type. Reusing the
    function would have made that test vacuous.

    Every movement field is set explicitly — including `valid_to=None`, whose honest value on a
    live edge is "nothing ended it". A default left unwritten is a field the hydrator has no reason
    to carry and the next reader has no reason to expect.

    NO `epistemic_status`, NO `provenance`, NO `run_id`/`step_id`. They are `_FORBIDDEN_EDGE_KEYS`
    and they are the ledger's: `hydrate_movement_edge` reads them off `mark_id`.
    """
    if not str(mark_id or "").strip():
        raise ValueError(
            "a movement edge needs the mark that grounds it — an edge with no mark is a "
            "relation nobody measured, which is the fabrication this lane refuses to persist")
    if not str(axis_ref or "").strip():
        raise ValueError(
            "a movement edge needs an axis — a movement along no dimension is not retrievable, "
            "and an unretrievable edge is weight with nothing to say")
    stamp = now or utc_now()
    return {
        # ── the C3 spine, byte-identical in shape to `atlas_relation.edge_entry` ──
        "edge_id": edge_id or new_movement_edge_id(),
        "kind": EDGE_MOVEMENT,
        "mark_id": str(mark_id),
        "source_node": str(source_node),
        "target_node": str(target_node),
        "spans": [str(p) for p in spans],
        "created_at": stamp,
        # ── the graph's own state; nothing below exists anywhere in the ledger ──
        "axis_ref": str(axis_ref),
        "systematicity": systematicity,
        "weight": float(weight),
        "valid_from": valid_from or stamp,
        "valid_to": valid_to,
        "observations": [dict(o) for o in (observations or [])],
        # The edge exists because a measurement grounded it, so mint time IS the first
        # measurement and the decay clock starts here.
        "last_measured_at": stamp,
        # Nothing has evaporated yet. Set explicitly, like `valid_to`: absent is a field the
        # hydrator has no reason to carry.
        "decayed_at": None,
    }


def assert_valid_movement_edge(edge: Mapping[str, Any]) -> None:
    """Raise unless this is a well-formed `atlases.edges` row that happens to be a movement.

    The reconciliation proof, as an assertion rather than a claim: it runs C3's own guard over a
    one-edge document, so a movement edge is checked by the SAME code every relation edge is
    checked by. If this lane ever drifts into carrying percept truth, this raises before the write.
    """
    if not is_movement_edge(edge):
        raise ValueError(f"not a movement edge: kind={edge.get('kind')!r}")
    missing = [k for k in ("edge_id", "mark_id", "source_node", "target_node", "spans",
                           "created_at", *MOVEMENT_FIELDS) if k not in edge]
    if missing:
        raise ValueError(
            f"movement edge '{edge.get('edge_id')}' is missing {missing}. Every movement field is "
            "set at mint time — an unset one is dropped by the hydrator and gone.")
    assert_no_percept_data({"nodes": [], "edges": [dict(edge)]})


# ── hydration: the edge says nothing; the mark says everything ───────────────

def hydrate_movement_edge(edge: Mapping[str, Any],
                          posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """One stored movement + the posts → what a reader (and Lane M) actually gets.

    `atlas_relation.hydrate_edge` does the ledger half — `live`, `role`, `label`, `epistemic`,
    `sources`, `source_ref`, or the "no longer in the ledger" record when the mark is gone. This
    adds the movement half and derives the two things Lane M needs that neither half states
    outright: `axis_ref` (already on the edge) and the run/step the grounding mark was produced
    under, read from `MarkProvenance` rather than stored a second time.

    A movement whose mark has been uncommitted keeps `live: False` and keeps its weight. The weight
    is a record of measurements that really happened; deleting it because the relation was later
    withdrawn would rewrite history rather than record it. What it loses is its claim, which is
    exactly the right thing to lose.
    """
    from backend.services.atlas_relation import hydrate_edge

    out = hydrate_edge(edge, posts)
    for key in MOVEMENT_FIELDS:
        out[key] = edge.get(key)
    out["kind"] = EDGE_MOVEMENT
    out["live_now"] = is_live(edge)

    mark = _find_mark(posts, edge.get("spans") or [], edge.get("mark_id") or "")
    provenance = dict((mark or {}).get("provenance") or {})
    # DERIVED, NEVER STORED. PROV-001 Seam 2 proved these survive the wholesale PATCH on the mark
    # (`test_mark_provenance_prov001`), so reading them here is reading the defended copy. `None`
    # means the mark itself carries none — a curator's own mark has no producer — and a synthesized
    # id would be the fabrication that test's `test_a_curators_mark_gets_no_invented_run_or_step`
    # exists to forbid.
    out["run_id"] = provenance.get("run_id")
    out["step_id"] = provenance.get("step_id")
    return out


def _find_mark(posts: Mapping[str, Mapping[str, Any]], spans: Sequence[str],
               mark_id: str) -> Optional[Dict[str, Any]]:
    for pid in spans:
        for mark in (posts.get(str(pid)) or {}).get("visual_marks") or []:
            if isinstance(mark, Mapping) and str(mark.get("id")) == str(mark_id):
                return dict(mark)
    return None


def edge_epistemic_status(edge: Mapping[str, Any],
                          posts: Mapping[str, Mapping[str, Any]]) -> Optional[str]:
    """What kind of knowing this movement is — read off the mark, every time.

    Returns None when the mark is gone or never carried a status. None is not "uncertain": it is
    "this edge cannot currently tell you", which a caller must handle rather than fill in.
    """
    mark = _find_mark(posts, edge.get("spans") or [], edge.get("mark_id") or "")
    if mark is None:
        return None
    return str(mark.get(STATUS_KEY) or "") or None


# ── dynamics: only measurement moves a weight ────────────────────────────────

def observation(*, status: str, at: str = "", run_id: str = "", step_id: str = "",
                detail: str = "") -> Dict[str, Any]:
    """One re-observation of a movement, as the log records it.

    `run_id`/`step_id` here are NOT a copy of the mark's provenance and the difference is the whole
    justification for the field: the mark's provenance says which run first produced the relation;
    an observation says which run RE-MEASURED it, later, and the graph is the only place that fact
    lives.
    """
    return {"epistemic_status": str(status), "at": at or utc_now(),
            "run_id": str(run_id) or None, "step_id": str(step_id) or None,
            "detail": str(detail)}


def is_measured(obs: Mapping[str, Any]) -> bool:
    return str(obs.get("epistemic_status") or "") == EpistemicStatus.MEASURED.value


def strengthen(edge: Mapping[str, Any], obs: Mapping[str, Any]) -> Dict[str, Any]:
    """Hebbian reinforcement — and ONLY on a measured re-observation.

    Returns a NEW edge; nothing here mutates in place, so a keeper that crashes mid-tick leaves the
    document it read exactly as it found it.

    An interpretive observation is still LOGGED, and that asymmetry is deliberate: the record that
    two thinkers agreed is worth keeping, and it is worth keeping somewhere that cannot be mistaken
    for evidence. So it lands in `observations` and leaves `weight` alone. A graph that strengthens
    on agreement learns what it already believes, which is the failure this whole program is
    arranged against.

    An edge a contradiction already closed (`valid_to` set) does not re-strengthen. Reopening it
    silently would let a later measurement erase a recorded contradiction; the honest move is a new
    edge, so both facts survive.
    """
    out = dict(edge)
    out["observations"] = [*(edge.get("observations") or []), dict(obs)]
    if not is_measured(obs) or edge.get("valid_to") is not None:
        return out
    current = float(edge.get("weight") or 0.0)
    # Toward the ceiling, not added to it: saturating, so confirmation number ten is worth less
    # than number two.
    out["weight"] = round(current + (MAX_WEIGHT - current) * STRENGTHEN_RATE, 6)
    out["last_measured_at"] = obs.get("at") or utc_now()
    # A fresh measurement restarts the decay clock: the new weight is the weight AS OF this
    # observation, so any evaporation already applied is spent and must not be re-applied from
    # an older mark.
    out["decayed_at"] = None
    return out


def decay(edge: Mapping[str, Any], *, now: str = "",
          half_life_seconds: float = DECAY_HALF_LIFE_SECONDS) -> Dict[str, Any]:
    """Exponential evaporation since the last measurement.

    Computed from a timestamp rather than accumulated per tick, deliberately: a keeper that ran
    twice in a minute, or not at all for a day, must arrive at the same number. Tick-counted decay
    makes the graph's shape a function of the scheduler's health, which is the kind of hidden
    dependency that is impossible to debug six months later.

    `decayed_at` is what makes that true, and the first version of this function did not have it —
    it decayed from `last_measured_at` every call while writing the lowered weight back, so two
    passes in one minute halved the edge twice. Its own test caught it. Decaying from `decayed_at`
    composes exactly (0.5^(a/H) · 0.5^(b/H) = 0.5^((a+b)/H)), so repeated passes and one late pass
    land on the same number.
    """
    stamp = now or utc_now()
    since = (edge.get("decayed_at") or edge.get("last_measured_at")
             or edge.get("valid_from") or edge.get("created_at"))
    seconds = elapsed_seconds(since, stamp)
    if seconds <= 0 or half_life_seconds <= 0:
        return dict(edge)
    out = dict(edge)
    out["weight"] = round(float(edge.get("weight") or 0.0)
                          * math.pow(0.5, seconds / half_life_seconds), 6)
    out["decayed_at"] = stamp
    return out


def invalidate(edge: Mapping[str, Any], *, reason: str, mark_id: str = "",
               run_id: str = "", step_id: str = "",
               now: str = "") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A contradiction ends a movement. Returns `(closed_edge, contradiction_node)`.

    THE EDGE IS CLOSED, NOT DELETED. `valid_to` is set and the weight drops to the floor, so the
    edge stops being retrieved while the fact that it once held — and the fact that something
    contradicted it — both survive. Deleting the row would leave the graph unable to say why it no
    longer believes something, and "we never thought that" is a different claim from "we thought
    that until this contradicted it".

    The contradiction is returned as its own node for the caller to persist. It is not written
    here, and not folded into the edge, because it is evidence in its own right: something
    measured, at a time, that disagreed.
    """
    stamp = now or utc_now()
    closed = dict(edge)
    closed["valid_to"] = stamp
    closed["weight"] = 0.0
    contradiction = {
        "contradiction_id": new_contradiction_id(),
        "kind": CONTRADICTION_KIND,
        "edge_id": str(edge.get("edge_id") or ""),
        "axis_ref": str(edge.get("axis_ref") or ""),
        "reason": str(reason),
        # The mark that carries the contradicting measurement, if one does. Same rule as the edge:
        # this node names it and never copies what it says.
        "mark_id": str(mark_id) or None,
        "run_id": str(run_id) or None,
        "step_id": str(step_id) or None,
        "at": stamp,
    }
    closed["observations"] = [*(edge.get("observations") or []),
                              {"epistemic_status": EpistemicStatus.MEASURED.value, "at": stamp,
                               "run_id": str(run_id) or None, "step_id": str(step_id) or None,
                               "detail": f"contradicted: {reason}",
                               "contradiction_id": contradiction["contradiction_id"]}]
    return closed, contradiction


def is_live(edge: Mapping[str, Any], *, now: str = "") -> bool:
    """Live = never closed, and not yet evaporated below the floor."""
    if edge.get("valid_to") is not None:
        return False
    return float(edge.get("weight") or 0.0) >= PRUNE_FLOOR


def should_prune(edge: Mapping[str, Any]) -> bool:
    return float(edge.get("weight") or 0.0) < PRUNE_FLOOR


def keeper_tick(edges: Sequence[Mapping[str, Any]], *, now: str = "",
                half_life_seconds: float = DECAY_HALF_LIFE_SECONDS
                ) -> Dict[str, List[Dict[str, Any]]]:
    """Apply decay to every movement edge and separate the ones that have faded out.

    Returns `{"kept": [...], "pruned": [...], "untouched": [...]}` — three lists rather than a
    mutated one, so a caller can report what it dropped instead of a count silently going down.
    C3's relation edges land in `untouched`: this keeper has no opinion about them.

    PRUNING REMOVES THE ATLAS'S REFERENCE, NEVER THE LEDGER'S MARK — `atlas_service.remove_edge`'s
    rule, inherited. A faded movement means the graph stopped finding it worth traversing, not that
    the comparison never happened.
    """
    kept: List[Dict[str, Any]] = []
    pruned: List[Dict[str, Any]] = []
    untouched: List[Dict[str, Any]] = []
    for edge in edges or []:
        if not is_movement_edge(edge):
            untouched.append(dict(edge))
            continue
        decayed = decay(edge, now=now, half_life_seconds=half_life_seconds)
        (pruned if should_prune(decayed) else kept).append(decayed)
    return {"kept": kept, "pruned": pruned, "untouched": untouched}


# ── the axis: a first-class node, referenced by many edges ───────────────────

def new_axis(*, name: str, relation_kind: str, axis_id: str = "",
             grounded_instances: Optional[Sequence[str]] = None,
             now: str = "") -> Dict[str, Any]:
    """A discovered dimension — nestedness, enclosure, recession — as its own record.

    Its own collection rather than an array on one Atlas, for the reason that decided every other
    shape in this lane: an axis discovered while reading one corpus is referenced by movements on
    other corpora, and an axis embedded in a document would be COPIED to be reused. The copy is the
    drift. `axis_ref` points here from anywhere.

    NO STORED `epistemic_status`. An axis is exactly as grounded as the movements that instantiate
    it, so a stored status would be a second copy of a fact derived from `grounded_instances` — the
    same mistake as a status on the edge, one level further out. `axis_status` computes it.
    """
    stamp = now or utc_now()
    return {
        "axis_id": axis_id or new_axis_id(),
        "name": str(name),
        "relation_kind": str(relation_kind),
        "grounded_instances": [str(i) for i in (grounded_instances or [])],
        "created_at": stamp,
        "contract_version": MOVEMENT_CONTRACT_VERSION,
    }


def axis_status(axis: Mapping[str, Any], edges: Sequence[Mapping[str, Any]],
                posts: Mapping[str, Mapping[str, Any]]) -> Optional[str]:
    """The axis's epistemic status, DERIVED from the movements that instantiate it.

    `measured` only if at least one live movement along it rests on a measured mark; otherwise
    `interpretive` if any live movement rests on an interpretive one; otherwise None — an axis
    nothing currently grounds cannot tell you what kind of knowing it is, and saying `uncertain`
    would be a claim where the honest answer is silence.

    Takes the strongest rather than the weakest deliberately: an axis with one measured instance
    among ten readings HAS been measured at least once, and that is the fact a retrieval wants.
    The count is available to any caller that wants to weigh it.
    """
    axis_id = str(axis.get("axis_id") or "")
    statuses = {edge_epistemic_status(e, posts)
                for e in edges or []
                if is_movement_edge(e) and str(e.get("axis_ref") or "") == axis_id and is_live(e)}
    if EpistemicStatus.MEASURED.value in statuses:
        return EpistemicStatus.MEASURED.value
    if EpistemicStatus.INTERPRETIVE.value in statuses:
        return EpistemicStatus.INTERPRETIVE.value
    return None


def hydrate_axis(axis: Mapping[str, Any], edges: Sequence[Mapping[str, Any]],
                 posts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """The stored axis + what currently grounds it. Assembled at read time, like everything else."""
    out = dict(axis)
    axis_id = str(axis.get("axis_id") or "")
    live = [e for e in edges or []
            if is_movement_edge(e) and str(e.get("axis_ref") or "") == axis_id and is_live(e)]
    out["epistemic_status"] = axis_status(axis, edges, posts)
    out["live_movements"] = len(live)
    out["total_weight"] = round(sum(float(e.get("weight") or 0.0) for e in live), 6)
    return out
