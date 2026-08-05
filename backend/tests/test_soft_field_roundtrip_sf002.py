"""SF-002 Part 3 — the drop-nothing guard. This is the deliverable that matters.

`post.grounds` and `post.percepts` just stopped being `List[dict]`. The PATCH path is wholesale
(`update_post` `$set`s the whole array), so **every key the model fails to declare is silently
deleted on the next save** — which is precisely how `TextBlock.origin` was lost, and precisely
what `Mark` was built to prevent. Success for this lane is therefore not "there is a schema" but
**"a round-trip drops nothing"**, and that has to be demonstrated, not asserted.

The loop these objects actually travel, and which of these tests covers each leg:

    regionStore PATCHes           →  §1 the write path: what lands in Mongo
    update_post $sets             →
    response_model=Post serializes→  §2 the read path: what comes back
    onPostChange → hydrate        →
    the next autosave PATCHes back→  §3 the full loop, twice round, still identical

§2 is the leg the directive did not name and the one that bites: FastAPI's `response_model` does
NOT apply `exclude_unset`, so an ordinary Optional field would be emitted as `null`, hydrated by
the client, and written back on the next autosave. Nothing dropped — and yet a key the curator
never wrote is now durable on every row. `ground_roles` is the case that makes it concrete.

Fixtures are minted the way the frontend mints them: one ground per LIVE type (SF-001B §4.2 —
region 22, frame 17, field 2, path 2), the three zero-row types alongside, one percept WITH
`ground_roles` and one WITHOUT.

Mirrors `frontend/src/differential/groundProvenanceParity.test.js` in intent: pin the invariant at
the seam where it would actually break, not near it.
"""
import json

from bson.objectid import ObjectId

from backend.routers import posts as R
from backend.schemas.post import Post, PostUpdate
from backend.schemas.soft_fields import GROUND_TYPES, UndeclaredGround
from backend.tests.test_circulation_spine_p1 import FakeCollection, run

_OID = ObjectId("507f1f77bcf86cd799439011")


# ── the fixtures: exactly what `makeGround` / `makeExpressionPercept` mint ───────────────────

def _spine(gid, ground_type, **rest):
    """The seven keys `makeGround` stamps on every ground, plus the per-type variant."""
    return {
        "id": gid, "ground_type": ground_type, "actor": "creator", "detector": None,
        "label": "", "note": "", "created_at": "2026-08-01T10:00:00.000Z", **rest,
    }


# One per LIVE type first — these are the 43 rows the corpus actually holds.
GROUND_REGION = _spine("gnd_r", "region", region_id="reg_a", label="the shoulder")
GROUND_FRAME = _spine("gnd_fr", "frame", whole=True, evidence_ids=["vm_1", "vm_2"])
GROUND_FIELD = _spine("gnd_f", "field", strokes=[[0.11, 0.22], [0.33, 0.44]])
GROUND_PATH = _spine("gnd_p", "path", points=[[0.1, 0.2], [0.5, 0.6]])
LIVE_GROUNDS = [GROUND_REGION, GROUND_FRAME, GROUND_FIELD, GROUND_PATH]

# …and the three with zero rows. Supported in the frontend, not dead — a schema that only got the
# live four right would be a schema that breaks the first time somebody draws a boundary.
GROUND_BOUNDARY = _spine("gnd_b", "boundary", points=[[0.1, 0.1], [0.9, 0.9]], band_width=0.02)
GROUND_CONSTELLATION = _spine("gnd_c", "constellation", member_ids=["gnd_r", "gnd_f"],
                              points=[[0.4, 0.4]])
GROUND_RELATION = _spine("gnd_rel", "relation", member_ids=["gnd_r", "gnd_p"],
                         relation_label="echoes")
ALL_GROUNDS = LIVE_GROUNDS + [GROUND_BOUNDARY, GROUND_CONSTELLATION, GROUND_RELATION]

# `makeExpressionPercept`'s seven unconditional keys. SF-001B §4.1: all 12 corpus rows, exactly.
PERCEPT_BARE = {
    "id": "pctx_m1_0", "kind": "expression", "expression": "the light pools where the wool folds",
    "ground_ids": ["gnd_r", "gnd_f"], "properties": ["light", "weight"], "actor": "creator",
    "created_at": "2026-08-01T10:00:03.000Z",
}
# …plus `ground_roles` on the one row that has roles. Note there is no `ground_roles` key at all
# on PERCEPT_BARE — its ABSENCE is half of what these tests protect.
PERCEPT_WITH_ROLES = {
    "id": "pctx_m1_1", "kind": "expression", "expression": "the two folds answer each other",
    "ground_ids": ["gnd_r", "gnd_p"], "properties": [],
    "ground_roles": {"gnd_r": "anchor", "gnd_p": "counterpoint"},
    "actor": "creator", "created_at": "2026-08-01T10:00:04.000Z",
}
ALL_PERCEPTS = [PERCEPT_BARE, PERCEPT_WITH_ROLES]


def _seed():
    posts = FakeCollection()
    posts.docs[_OID] = {"_id": _OID, "photo_url": "http://x/y.jpg",
                        "photo_public_id": "posts/xyz"}
    return posts


def _identical(actual, expected, what):
    """Byte-identity, and say WHICH key moved when it is not — a bare `assert a == b` over eight
    nested dicts is a failure message nobody can act on."""
    assert len(actual) == len(expected), f"{what}: row count moved"
    for got, want in zip(actual, expected):
        dropped = set(want) - set(got)
        invented = set(got) - set(want)
        assert not dropped, f"{what} {want['id']}: DROPPED {sorted(dropped)}"
        assert not invented, f"{what} {want['id']}: INVENTED {sorted(invented)}"
        assert got == want, f"{what} {want['id']}: values changed"
    # And the whole thing, serialized, so nothing structural hides inside an equal-comparing value.
    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)


# ── 1. the write path — what the wholesale PATCH lands in Mongo ──────────────────────────────

def test_patch_writes_every_ground_type_byte_identically(monkeypatch):
    """THE CLAIM: all seven declared types survive the typed write with no key touched."""
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)

    run(R.update_post(str(_OID), PostUpdate(grounds=ALL_GROUNDS)))

    _identical(posts.docs[_OID]["grounds"], ALL_GROUNDS, "ground")


def test_patch_writes_percepts_with_and_without_ground_roles_byte_identically(monkeypatch):
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)

    run(R.update_post(str(_OID), PostUpdate(percepts=ALL_PERCEPTS)))

    stored = posts.docs[_OID]["percepts"]
    _identical(stored, ALL_PERCEPTS, "percept")
    # Said explicitly because it is the whole point of the `ground_roles` design:
    assert "ground_roles" not in stored[0]
    assert stored[1]["ground_roles"] == {"gnd_r": "anchor", "gnd_p": "counterpoint"}


def test_the_schema_invents_no_curator_state_on_a_percept_nobody_curated(monkeypatch):
    """`status` and `curator_label` are declared so the first writer need not invent them. A
    percept that has never been curated must still carry NEITHER key — a declared field that
    appears as `null` on every row is a schema authoring a fact nobody stated."""
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)

    run(R.update_post(str(_OID), PostUpdate(percepts=[PERCEPT_BARE])))

    stored = posts.docs[_OID]["percepts"][0]
    assert "status" not in stored
    assert "curator_label" not in stored


def test_an_undeclared_ground_type_round_trips_instead_of_failing_the_read(monkeypatch):
    """`grounds.js` is the authoritative contract and may grow an eighth type without asking
    Python. That must not become a 500 on every post holding one — the silent-drop hazard traded
    for a loud-unread one is not an improvement. It validates, it keeps its keys, and it is
    reportable as the finding it is."""
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)
    exotic = _spine("gnd_x", "tesseract", corners=[[0, 0, 0, 0]])

    run(R.update_post(str(_OID), PostUpdate(grounds=[exotic])))
    _identical(posts.docs[_OID]["grounds"], [exotic], "ground")

    parsed = Post.model_validate({"id": "1", "photo_url": "u", "photo_public_id": "p",
                                  "grounds": [exotic]})
    assert isinstance(parsed.grounds[0], UndeclaredGround)


def test_a_ground_carries_no_detached_flag_it_was_not_given(monkeypatch):
    """`detached` is DERIVED state — written by geometry_recovery, read by nothing, recomputed by
    `resolveGround` on every consumer. SF-002 refuses to type it (derived state is never a
    durability class), and refusing to type it must not mean silently deleting a stale copy that
    already exists either: it rides `extra` untouched, and the single source of truth stays
    `resolveGround`."""
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)
    stale = dict(GROUND_REGION, detached=True, detached_reason="region replaced")

    run(R.update_post(str(_OID), PostUpdate(grounds=[stale])))

    assert posts.docs[_OID]["grounds"][0] == stale
    # …and a ground that never had one does not acquire one.
    run(R.update_post(str(_OID), PostUpdate(grounds=[GROUND_REGION])))
    assert "detached" not in posts.docs[_OID]["grounds"][0]


def test_a_partial_patch_leaves_the_other_soft_field_alone(monkeypatch):
    """exclude_unset still holds: a percepts-only save must not wipe a curator's grounds."""
    posts = _seed()
    posts.docs[_OID]["grounds"] = ALL_GROUNDS
    monkeypatch.setattr(R, "post_collection", posts)

    run(R.update_post(str(_OID), PostUpdate(percepts=ALL_PERCEPTS)))

    _identical(posts.docs[_OID]["grounds"], ALL_GROUNDS, "ground")


# ── 2. the read path — what `response_model=Post` sends back ─────────────────────────────────

def _through_response_model(stored):
    """Exactly what FastAPI does with `response_model=Post`: validate the handler's dict, then
    serialize WITHOUT exclude_unset. This is the leg where an ordinary Optional leaks a null."""
    return Post.model_validate(stored).model_dump(mode="json")


def test_the_response_model_adds_nothing_to_a_percept_or_a_ground(monkeypatch):
    """THE CLAIM, and the one the directive did not name: the read is byte-identical too.

    If this fails, nothing is lost — but `ground_roles: null` (or `status: null`) reaches the
    client, the store hydrates it, and the next autosave makes it durable on every row. A schema
    that quietly rewrites the corpus by being read is not an honest carrier.
    """
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)
    run(R.update_post(str(_OID), PostUpdate(grounds=ALL_GROUNDS, percepts=ALL_PERCEPTS)))

    served = _through_response_model(R.post_helper(posts.docs[_OID]))

    _identical(served["grounds"], ALL_GROUNDS, "ground")
    _identical(served["percepts"], ALL_PERCEPTS, "percept")


def test_a_created_at_string_is_not_reformatted_by_the_round_trip(monkeypatch):
    """`created_at` is typed `str`, not `datetime`, on purpose: coercion would re-spell the same
    instant and a round trip that rewrites bytes is a round trip that changed the record."""
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)
    stamps = ["2026-08-01T10:00:03.000Z", "2026-08-01T10:00:03.4Z", "2026-08-01T15:30:03+05:30"]
    rows = [dict(PERCEPT_BARE, id=f"pctx_{i}", created_at=s) for i, s in enumerate(stamps)]

    run(R.update_post(str(_OID), PostUpdate(percepts=rows)))
    served = _through_response_model(R.post_helper(posts.docs[_OID]))

    assert [p["created_at"] for p in posts.docs[_OID]["percepts"]] == stamps
    assert [p["created_at"] for p in served["percepts"]] == stamps


# ── 3. the full loop — read fed back as the next write, which is what actually happens ───────

def test_two_full_save_reload_save_cycles_change_nothing(monkeypatch):
    """THE CLAIM at the level the user experiences it: opening a post and letting the autosave
    fire must not mutate the record. `regionStore` hydrates from the PATCH response and writes it
    back on the next edit, so any asymmetry between read and write compounds every session. Two
    cycles, because a drift that is idempotent after one pass would hide in a single one.
    """
    posts = _seed()
    monkeypatch.setattr(R, "post_collection", posts)

    payload = {"grounds": ALL_GROUNDS, "percepts": ALL_PERCEPTS}
    for _ in range(2):
        served = _through_response_model(run(R.update_post(str(_OID), PostUpdate(**payload))))
        # what the client hydrated becomes what the client saves next
        payload = {"grounds": served["grounds"], "percepts": served["percepts"]}

    _identical(posts.docs[_OID]["grounds"], ALL_GROUNDS, "ground")
    _identical(posts.docs[_OID]["percepts"], ALL_PERCEPTS, "percept")


# ── 4. the schema says what it says, and refuses what it refuses ─────────────────────────────

def test_the_percept_declares_no_draft_fields_and_no_provenance_block():
    """SF-002 v2.1/PROV-001, held as code. `draft_text`/`function`/`epistemic_ceiling` belong to
    the PROPOSAL (`percept_draft`/`PerceptStep`); a `provenance` block would be a second authored
    copy of what the percept already derives through `ground_ids`. Declaring either would
    re-merge two objects that are deliberately two."""
    from backend.schemas.soft_fields import Percept

    declared = set(Percept.model_fields)
    assert declared.isdisjoint({"draft_text", "function", "epistemic_ceiling", "provenance"})
    assert declared == {"id", "kind", "expression", "ground_ids", "properties", "actor",
                        "created_at", "ground_roles", "status", "curator_label"}


def test_the_ground_declares_no_detached_and_no_collapsed_epistemic_status():
    """`detached` is derived state (SF-001A Q3). A single `epistemic_status` is the field that
    would make SF-002 Option B a migration instead of an addition — a SAM-3 ground's mask is
    `measured` while its label is `interpretive`, and one field would have to launder one through
    the other. Deferred by sequencing; the schema must not foreclose it."""
    from backend.schemas.soft_fields import GroundBase

    declared = set(GroundBase.model_fields)
    assert declared.isdisjoint({"detached", "detached_reason", "epistemic_status", "confidence"})
    assert declared == {"id", "ground_type", "actor", "detector", "label", "note", "created_at"}


def test_all_seven_declared_ground_types_are_reachable():
    """The three with zero corpus rows are supported in the frontend, not dead. A union that only
    got the live four right would break the first time somebody draws a boundary."""
    parsed = Post.model_validate({"id": "1", "photo_url": "u", "photo_public_id": "p",
                                  "grounds": [_spine(f"gnd_{t}", t) for t in GROUND_TYPES]})
    assert [g.ground_type for g in parsed.grounds] == list(GROUND_TYPES)
    assert not any(isinstance(g, UndeclaredGround) for g in parsed.grounds)


# ── 5. vision_recovery parity — the restore still reproduces the curator byte-for-byte ───────
#
# `grounds` and `percepts` are in `_MUTABLE_FIELDS`, and the curator identity hash is the
# invariant a restore must reproduce. The recovery module reads raw Mongo dicts and never touches
# these models — but it does not have to for this to break: if a save through the typed models
# moved a single byte, a backup taken before the save and the post after it would no longer hash
# alike, and a restore drill would report a corruption that never happened.

def test_a_save_through_the_typed_models_does_not_move_the_curator_identity_hash(monkeypatch):
    from backend.services import vision_recovery as VR

    posts = _seed()
    before = dict(posts.docs[_OID], grounds=ALL_GROUNDS, percepts=ALL_PERCEPTS)
    posts.docs[_OID] = dict(before)
    monkeypatch.setattr(R, "post_collection", posts)

    identity = VR.curator_identity_hash(before)
    curator_only = VR.curator_only_hash(before)
    snapshot = VR.post_snapshot(before)

    # a full save of exactly what was already there — the autosave a curator triggers by editing
    # anything else on the post
    run(R.update_post(str(_OID), PostUpdate(grounds=ALL_GROUNDS, percepts=ALL_PERCEPTS)))
    after = posts.docs[_OID]

    assert VR.curator_identity_hash(after) == identity
    assert VR.curator_only_hash(after) == curator_only
    assert VR.post_snapshot(after)["full_hash"] == snapshot["full_hash"]


def test_a_restored_backup_still_validates_through_the_typed_models():
    """The other direction: what `restore_post` `$set`s back must be readable. A backup written
    before SF-002 holds plain dicts, and the typed models have to accept them unchanged or a
    rollback would resurrect a post the API can no longer serve."""
    from backend.services import vision_recovery as VR

    legacy = {"_id": _OID, "photo_url": "http://x/y.jpg", "photo_public_id": "posts/xyz",
              "grounds": ALL_GROUNDS, "percepts": ALL_PERCEPTS}
    restored_doc = VR.post_snapshot(legacy)["doc"]

    served = _through_response_model({**restored_doc, "id": str(_OID)})

    _identical(served["grounds"], ALL_GROUNDS, "ground")
    _identical(served["percepts"], ALL_PERCEPTS, "percept")
