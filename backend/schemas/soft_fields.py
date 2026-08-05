"""SF-002 — the soft-field schema: a typed-but-open home for `post.grounds` and `post.percepts`.

Track A's move (`Region`) and PROV-001's move (`Mark`) applied one level up, to meaning. The
perceptual layer becomes visible to the database, the writers and the curator — **without dropping
a single key the frontend currently mints.**

## The governing risk, stated once

`post.percepts` and `post.grounds` were `Optional[List[dict]]`, and the PATCH path is wholesale
(`update_post`, `backend/routers/posts.py`). The moment they become typed models, **every key the
model fails to declare is silently deleted on the next save.** That is exactly how
`TextBlock.origin` was lost and exactly what `Mark` (`backend/schemas/post.py`) was built to
prevent. So this module's success criterion is not "there is a schema" — it is **"a round-trip
drops nothing."** `backend/tests/test_soft_field_roundtrip_sf002.py` is where that is proved, and
`scripts/sf002_softfield_replay.py` is where it is proved against the live corpus.

## Why `SoftFieldModel` re-implements `exclude_unset` in a serializer

The obvious answer to the risk above is `extra="allow"` plus `exclude_unset=True` on the write
path — which `update_post` already passes. That is necessary and it is not sufficient, because of
the loop these objects actually travel:

    regionStore PATCHes  →  update_post $sets  →  response_model=Post serializes  →
    onPostChange(data)   →  the store hydrates from it  →  the next autosave PATCHes it BACK

The response half runs through FastAPI's `response_model`, which does **not** apply
`exclude_unset`. A declared-but-absent Optional field is emitted as `null` there, the client
hydrates the null, and the next autosave writes it. Nothing is dropped — but a key the curator
never wrote is now durable, on every row, forever. `ground_roles` is the sharp case:
`perceptMentions.js` omits it entirely when empty *precisely so* a percept with no roles stays
byte-identical to one written before roles existed, and a model that emits `ground_roles: null`
breaks that on the read path no matter how careful the write path is.

So these models declare fields **without gaining the power to invent them**: the serializer emits
only what was actually set (declared fields that arrived, plus every `extra`). A `Percept` is a
carrier that can *name* what must not be dropped, not an author that fills in blanks. Absence
survives the round trip as absence, which is the only way "drops nothing" can also mean "adds
nothing."

The corollary, worth stating because it is unusual: constructing one of these in Python and
dumping it will NOT emit defaults. That is intended. If a producer wants a field on the record it
must set it — the schema will not quietly speak on its behalf.

## What is deliberately NOT here

- **No draft fields on `Percept`** (`draft_text`, `function`, `epistemic_ceiling`). Those belong to
  `percept_draft`/`PerceptStep` — the *proposal*. SF-002 v1 listed them and v2.1 corrected it;
  putting them here re-merges the two objects `backend/services/percept_lineage.py` keeps apart.
- **No `provenance` block on `Percept`.** The percept derives provenance through `ground_ids`
  (PROV-001's parity decision). A second authored copy is the drift
  `groundProvenanceParity.test.js` exists to catch.
- **No `detached` on `Ground`.** SF-001A Q3 settled it with code: `detached` is derived state,
  written by `geometry_recovery.py`, read by nothing (every consumer recomputes through
  `resolveGround`), and already stripped as a machine annotation by `vision_recovery.py`. Typing
  it would promote an inert stale copy into defended contract. The rule this carries forward:
  **derived state is never a durability class.**
- **No `epistemic_status` / `confidence` on `Ground`.** `makeGround` does not mint them. Declaring
  fields nothing writes is fabrication in schema form. See "the deferred question" at the foot of
  this module for the SF-004 case that will eventually want them, and why a single collapsed
  status is the wrong shape for it.
- **No per-type geometry.** The authoritative ground contract lives in
  `frontend/src/differential/grounds.js` and stays there. `Mark` refuses to restate
  `visualMarks.js`; so does `Ground`. `extra="allow"` carries `region_id`, `strokes`, `points`,
  `band_width`, `whole`, `evidence_ids`, `member_ids`, `relation_label` and whatever comes next.
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Tag, model_serializer


class SoftFieldModel(BaseModel):
    """A carrier that declares fields without gaining the power to invent them.

    `extra="allow"` so an undeclared key rides through untouched, and a serializer that emits only
    what was actually set so a declared-but-absent key stays absent — on the read path as well as
    the write path. See the module docstring for why the read path is the one that bites.
    """
    model_config = ConfigDict(extra="allow")

    @model_serializer(mode="wrap")
    def _emit_only_what_was_set(self, handler):
        # `__pydantic_fields_set__` holds the declared fields that arrived AND every extra key, so
        # this drops exactly the defaults nobody wrote and nothing else.
        data = handler(self)
        was_set = self.__pydantic_fields_set__
        return {k: v for k, v in data.items() if k in was_set}


# ── Percept ─────────────────────────────────────────────────────────────────────────────────
# ONE object, and the field is exactly uniform. SF-001B §4.1 measured all 12 persisted rows: every
# one an expression percept, key set exactly `makeExpressionPercept`'s seven unconditional keys
# plus `ground_roles` on the single row that has roles. Zero draft-shaped, zero drift, zero partial
# rows. The "separate two objects before typing either" branch is closed.

class Percept(SoftFieldModel):
    """The curator's durable act of noticing, as `makeExpressionPercept` mints it.

    `frontend/src/state/perceptMentions.js` is the producer and the contract; this declares what
    must not be dropped in transit. The percept rests on grounds and **has no extent of its own** —
    `geometry` is absent here not by oversight but as the claim that a percept borrows the extent
    of what it rests on.
    """

    id: str                                     # `pctx_<t36>_<n36>` — the mint, and the identity
    kind: str = "expression"                    # the discriminator; the wire value never changes
    expression: str = ""                        # the sentence the curator wrote
    ground_ids: List[str] = []                  # what it rests on — and how it derives provenance
    properties: List[str] = []                  # the composer's toggled property chips
    actor: str = "creator"                      # creator | audience — never a producer name
    # An ISO-8601 string, NOT a `datetime`. Coercing it would re-serialize to a different
    # spelling of the same instant, and a round trip that rewrites bytes is a round trip that
    # changed the record. The type declares "this key exists", not "this key is mine to reformat".
    created_at: Optional[str] = None

    # CIRCUIT-001 P1C — { ground_id: role }: what each cited ground DOES for this reading.
    # OMITTED-WHEN-EMPTY, and that is load-bearing: `perceptMentions.js` writes it only when
    # non-empty so a percept with no roles is byte-identical to one written before roles existed.
    # `SoftFieldModel`'s serializer is what keeps that true through the read path.
    ground_roles: Optional[Dict[str, str]] = None

    # SF-002 §4 orthogonal choice 2 — the minimum "malleable, interactive" needs: a stable identity
    # (above) plus curator state, so a percept can be edited, forked and annotated AS AN OBJECT.
    # Nothing writes these yet; they are declared so the first writer does not have to invent them,
    # and — because of the serializer — a percept that has never been curated carries neither key.
    status: Optional[str] = None                # proposed | accepted | rejected | overridden
    curator_label: Optional[str] = None


# ── Ground ──────────────────────────────────────────────────────────────────────────────────
# A discriminated union, not a flat model. SF-002 v1's flat `Ground` described the REGION ADAPTER —
# 22 of 43 corpus rows. The other 21 carry shapes it does not declare: `frame` 17 (whole + evidence
# _ids), `field` 2 (strokes), `path` 2 (points). Typing grounds flat would leave roughly half the
# corpus undeclared, and undeclared is what gets dropped. (SF-001B §4.2.) That `frame` is the
# SECOND most common type is the part worth remembering: it was invisible in the design discussion,
# and it is not a region pointer at all.

# The seven declared types. Authoritative source: `frontend/src/differential/grounds.js`
# (GROUND_TYPES) — this is a mirror for dispatch, never a second contract.
GROUND_TYPES = ("region", "field", "path", "boundary", "frame", "constellation", "relation")


class GroundBase(SoftFieldModel):
    """The spine `makeGround` stamps on every ground, whatever its type.

    Everything past this — `region_id`, `strokes`, `points`, `band_width`, `whole`, `evidence_ids`,
    `member_ids`, `relation_label` — rides `extra="allow"` and stays defined in `grounds.js`. Two
    copies of a geometry contract is one more thing to drift, which is the failure this schema
    exists to close, not to reproduce.
    """

    id: str                                     # `gnd_<t36>_<n36>` — the identity compositions cite
    ground_type: str                            # the discriminator; narrowed per variant below
    actor: Optional[str] = None                 # creator | auto | audience
    detector: Optional[str] = None              # which model, when actor is `auto`
    label: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[str] = None            # ISO-8601 string — see `Percept.created_at`


# Spatial primitives — these occupy the image directly.
class RegionGround(GroundBase):
    """The Region ADAPTER: a reference, never a duplication. Geometry stays on the Region, so a
    re-dissect degrades the ground gracefully instead of leaving it holding stale coordinates."""
    ground_type: Literal["region"] = "region"


class FieldGround(GroundBase):
    """Its own geometry: brushed `strokes`. Not a region pointer."""
    ground_type: Literal["field"] = "field"


class PathGround(GroundBase):
    """Its own geometry: `points`."""
    ground_type: Literal["path"] = "path"


class BoundaryGround(GroundBase):
    """Its own geometry: `points` + `band_width`. Zero rows in the corpus — supported, not dead."""
    ground_type: Literal["boundary"] = "boundary"


class FrameGround(GroundBase):
    """The whole image as evidence (`whole: true` + `evidence_ids`). 17 rows — the second most
    common type, and the one the flat model missed entirely."""
    ground_type: Literal["frame"] = "frame"


# Compositions — these reference members BY ID and are resolved recursively (`resolveGround`).
class ConstellationGround(GroundBase):
    """`member_ids` + optional raw `points`. Zero rows — supported, not dead."""
    ground_type: Literal["constellation"] = "constellation"


class RelationGround(GroundBase):
    """`member_ids` + `relation_label`. Zero rows — supported, not dead."""
    ground_type: Literal["relation"] = "relation"


class UndeclaredGround(GroundBase):
    """A ground whose `ground_type` this module does not know.

    Not a hypothetical tidiness: `grounds.js` is the authoritative contract, and the whole point of
    not restating it here is that it may grow an eighth type without asking Python's permission. A
    strict union would turn that ordinary frontend change into a 500 on every post holding one —
    trading the silent-drop hazard this schema closes for a loud-unread one, which is worse.

    So an unrecognised type validates, carries every key on `extra`, and round-trips untouched. It
    is reported rather than dropped: `scripts/sf002_softfield_replay.py` counts these, and one
    appearing in the corpus is a finding, exactly as it was in SF-001B's census.
    """
    ground_type: Optional[str] = None


_GROUND_VARIANTS = {
    "region": RegionGround, "field": FieldGround, "path": PathGround,
    "boundary": BoundaryGround, "frame": FrameGround,
    "constellation": ConstellationGround, "relation": RelationGround,
}


def _ground_tag(value: Any) -> str:
    """Route a row to its variant, and everything unrecognised to `UndeclaredGround`.

    A callable discriminator rather than a plain field discriminator, because a plain one rejects
    what it does not recognise and this must not. Fail OPEN on identity, never on the read.
    """
    ground_type = (value.get("ground_type") if isinstance(value, dict)
                   else getattr(value, "ground_type", None))
    return ground_type if ground_type in _GROUND_VARIANTS else "other"


Ground = Annotated[
    Union[
        Annotated[RegionGround, Tag("region")],
        Annotated[FieldGround, Tag("field")],
        Annotated[PathGround, Tag("path")],
        Annotated[BoundaryGround, Tag("boundary")],
        Annotated[FrameGround, Tag("frame")],
        Annotated[ConstellationGround, Tag("constellation")],
        Annotated[RelationGround, Tag("relation")],
        Annotated[UndeclaredGround, Tag("other")],
    ],
    Discriminator(_ground_tag),
]


# ── the deferred question this schema must not foreclose (SF-002 Part 4) ─────────────────────
#
# SF-004-R2 §5.3/§6 hands SF-002 a live question it is not this lane's job to answer: **a SAM-3
# ground carries two epistemic statuses on one object.** The mask is `measured` — a real
# segmentation of real pixels. The concept label attached to that mask is `interpretive`, and
# §4.3 observed the label being flatly wrong at low confidence while the mask underneath it was
# perfectly good. One `epistemic_status` field on the ground cannot say that. It would have to
# pick, and either choice launders one half of the object through the other: `measured` dresses a
# guessed label as a measurement, `interpretive` throws away the one honest thing SAM 3 produced.
#
# Per-attribute epistemics is SF-002 Option B, and it is deferred by SEQUENCING, not rejected —
# the merge rule (two producers asserting the same attribute with different statuses) is real
# design and it is only FORCED once a second producer exists. SAM 3 will force it.
#
# What this lane owes is that the schema does not foreclose it, and the shape above is what pays
# that debt: `extra="allow"` leaves room for an attribute list to arrive additively, and the spine
# carries **no single collapsed status** for it to have to contradict. Adding
# `epistemic_status: str` to `GroundBase` now would be the one change that makes Option B a
# migration instead of an addition — a field every row already carries, that every reader already
# trusts, and that says the wrong thing about exactly the producer B exists to serve.
#
# Recorded, not resolved. It becomes a decision when a producer asserts a measured attribute
# beside an interpretive one.
