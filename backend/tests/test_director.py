"""
CIRCUIT-001 ORCH-001 — the capability map and the working-memory packet.

No model, no GPU, no network, no database: this layer is a table plus a frozen dataclass,
which is what lets the whole Director be tested unattended.
"""
from __future__ import annotations

from backend.services.director import capabilities as caps
from backend.services.director.capabilities import Resource
from backend.services.director.memory import build_memory


# ── fixtures ─────────────────────────────────────────────────────────────────

def bare_memory(**kw):
    """An image and nothing else — the hardest case for a planner."""
    return build_memory(image_ref="img_1", post_id="post_1", **kw)


def rich_memory(*, regions=2, marks=3, **kw):
    return build_memory(
        image_ref="img_1", post_id="post_1",
        region_ids=tuple(f"reg_{i}" for i in range(regions)),
        mark_ids=tuple(f"mark_{i}" for i in range(marks)),
        **kw)


# ── 1. the capability map ────────────────────────────────────────────────────

class TestCapabilityMap:

    def test_field_producer_names_match_the_live_registry(self):
        """The map must not drift from the runtime it describes.

        This is the pin that makes the whole table trustworthy: if a producer is renamed in
        `posts.py` and not here, the planner would emit a name the endpoint cannot dispatch,
        and nothing else in this suite would notice.
        """
        from backend.routers.posts import _FIELD_PRODUCERS
        for name in caps.FIELD_PRODUCER_ACTUATORS:
            assert name in _FIELD_PRODUCERS, f"'{name}' is not a live field producer"
            assert name in caps.ACTUATORS

    def test_every_actuator_requires_something(self):
        # An actuator with no requirements can fire on an empty packet — that is exactly the
        # blind call this layer exists to prevent.
        for name, a in caps.ACTUATORS.items():
            assert a.requires, f"'{name}' declares no inputs"

    def test_readings_never_produce_marks(self):
        """P8-D's distinction, enforced at Layer 3.

        If a reading produced MARK, a mark-hungry step could be satisfied by a sentence —
        the exact laundering P8-D was built to prevent, reintroduced by the planner.
        """
        for name in ("presence_check", "enumerate", "semantic_read"):
            produces = caps.ACTUATORS[name].produces
            assert Resource.MARK not in produces
            assert Resource.READING in produces

    def test_connect_marks_needs_two(self):
        req = [r for r in caps.ACTUATORS["connect_marks"].requires if r.kind is Resource.MARK]
        assert req[0].min_count == 2, "a relation between a thing and itself is not a relation"

    def test_unknown_actuator_returns_none_not_a_default(self):
        assert caps.get("brush_the_vibes") is None

    def test_producers_of_finds_the_finders(self):
        assert "find_parts" in caps.producers_of(Resource.REGION)
        assert "compose_percept" in caps.producers_of(Resource.PERCEPT)


# ── 2. working memory ────────────────────────────────────────────────────────

class TestWorkingMemory:

    def test_counts_derive_from_contents(self):
        m = rich_memory(regions=2, marks=3)
        a = m.available()
        assert a[Resource.IMAGE] == 1
        assert a[Resource.REGION] == 2
        assert a[Resource.MARK] == 3

    def test_blank_phrase_does_not_satisfy_a_phrase_requirement(self):
        """A whitespace phrase is not a phrase — otherwise P8-B's fabrication returns."""
        assert bare_memory(phrase="   ").available()[Resource.PHRASE] == 0
        assert bare_memory(phrase="a cross").available()[Resource.PHRASE] == 1

    def test_evolve_returns_a_new_packet_and_leaves_the_old_one_intact(self):
        m = bare_memory()
        m2 = m.evolve((Resource.REGION,), step_id="s1")
        assert m.available()[Resource.REGION] == 0      # the snapshot still tells the truth
        assert m2.available()[Resource.REGION] == 1

    def test_projected_ids_cannot_be_mistaken_for_records(self):
        m = bare_memory().evolve((Resource.MARK,), step_id="s1")
        assert "#" in m.mark_ids[0]

    def test_readings_add_nothing_to_the_evidence_layer(self):
        m = bare_memory().evolve((Resource.READING,), step_id="s1")
        assert m.mark_ids == () and m.region_ids == ()

    def test_unreadable_is_distinct_from_empty(self):
        """'No marks' and 'could not read the marks' must never collapse."""
        m = bare_memory().with_unreadable("marks: db timeout")
        assert m.available()[Resource.MARK] == 0
        assert m.unreadable == ("marks: db timeout",)
        assert "marks: db timeout" in m.summary()["unreadable"]

    def test_constraints_travel_as_data(self):
        m = bare_memory()
        assert m.constraints["no_fabrication_on_refusal"] is True
        assert m.constraints["image_only"] is True
