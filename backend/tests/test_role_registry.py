"""
ROLES-001 — the role registry: organs and thinkers, model-agnostic.

The build gate is one claim, and §2 is the whole proof of it:

    swapping a thinker role's model in config changes which model every relevant call site
    uses, with NO code edit.

Everything else here defends that claim from the two ways it could quietly stop being true:
the indirection changing behaviour (§1, §4), and a literal creeping back to a call site (§3).
"""
from __future__ import annotations

import pathlib
import re

import pytest

from backend.services import epistemics, role_registry
from backend.services.epistemics import EpistemicStatus
from backend.services.role_registry import RoleKind


@pytest.fixture(autouse=True)
def _clean_bindings():
    """Bindings are process-global by design. Leaking one into the next test would make this
    file's own results depend on ordering, which is exactly the failure it exists to catch."""
    role_registry.reset_bindings()
    yield
    role_registry.reset_bindings()


# ── 1. the indirection is behaviour-neutral ──────────────────────────────────

#: The eight literals that lived at call sites before this change, verbatim, with the call site
#: each came from. This is the "no behaviour change" pin: with no override in play, every one of
#: them must still be what the call site uses.
_SHIPPED = {
    "dissector": "qwen/qwen3.6-27b",
    "writer_vision": "qwen/qwen3.6-27b",
    "writer_literary": "openai/gpt-oss-120b",
    "archivist": "openai/gpt-oss-120b",
    "story_segmenter": "llama-3.3-70b-versatile",
    "semantic_annotator": "openai/gpt-4o-mini",
    "step_planner": "openai/gpt-oss-120b",
    "argument_planner": "openai/gpt-oss-120b",
}


def test_defaults_are_exactly_the_literals_that_were_replaced():
    for role, model in _SHIPPED.items():
        assert role_registry.model_for(role) == model, role


def test_every_call_site_still_reports_its_original_model():
    """The other half of the same claim, read from the SERVICES rather than the registry — a
    registry that agrees with itself proves nothing."""
    from backend.services.editor_llm_service import editor_llm_service
    from backend.services.llm_service import llm_service
    from backend.services.semantic_provider import SemanticProvider
    from backend.services.director.groq_planner import GroqPlanner
    from backend.services.director.argument_planner import GroqArgumentPlanner

    assert llm_service.model == "openai/gpt-oss-120b"
    assert editor_llm_service.literary_model == "openai/gpt-oss-120b"
    assert editor_llm_service.vision_model == "qwen/qwen3.6-27b"
    assert SemanticProvider().model == "openai/gpt-4o-mini"
    assert GroqPlanner().model == "openai/gpt-oss-120b"
    assert GroqArgumentPlanner().model == "openai/gpt-oss-120b"


def test_a_service_with_no_client_still_names_no_model():
    """`vision_service` and `story_block_service` reported None with no API key, and several
    callers read that to say what answered. A property that always resolves would have quietly
    made a keyless deploy claim a model it cannot call."""
    from backend.services.story_block_service import StoryBlockService
    from backend.services.vision_service import VisionService

    vs = VisionService()
    vs.client = None
    assert vs.vision_model is None

    sb = StoryBlockService()
    sb.client = None
    assert sb.model is None


# ── 2. the model-agnosticism proof ───────────────────────────────────────────

#: role → (import path, attribute chain) for every thinker whose binding is observable from a
#: call site. `(module, attr)` where attr is read off a freshly built object or the singleton.
_CALL_SITES = [
    ("archivist", lambda: __import__(
        "backend.services.llm_service", fromlist=["llm_service"]).llm_service.model),
    ("writer_literary", lambda: __import__(
        "backend.services.editor_llm_service", fromlist=["editor_llm_service"]
    ).editor_llm_service.literary_model),
    ("writer_vision", lambda: __import__(
        "backend.services.editor_llm_service", fromlist=["editor_llm_service"]
    ).editor_llm_service.vision_model),
    ("semantic_annotator", lambda: __import__(
        "backend.services.semantic_provider", fromlist=["SemanticProvider"]
    ).SemanticProvider().model),
    ("step_planner", lambda: __import__(
        "backend.services.director.groq_planner", fromlist=["GroqPlanner"]).GroqPlanner().model),
    ("argument_planner", lambda: __import__(
        "backend.services.director.argument_planner", fromlist=["GroqArgumentPlanner"]
    ).GroqArgumentPlanner().model),
]


@pytest.mark.parametrize("role,read", _CALL_SITES, ids=[r for r, _ in _CALL_SITES])
def test_rebinding_a_role_in_config_moves_its_call_site(role, read, monkeypatch):
    """THE BUILD GATE. Set the env var; the call site follows. No code is edited, no module is
    reloaded, and the SINGLETONS — constructed at import, long before the override existed —
    follow too, which is the case a `self.model = …` in `__init__` would have failed."""
    monkeypatch.setenv(role_registry.env_var_for(role), "acme/rebound-1")
    assert read() == "acme/rebound-1"


def test_rebinding_the_dissector_moves_the_sukshma_call_site(monkeypatch):
    """Read off the module singleton constructed at import time. Kept separate from the
    parametrized set because `vision_service` gates on a live client."""
    from backend.services.vision_service import vision_service
    if vision_service.client is None:
        pytest.skip("no GROQ_API_KEY in this environment — vision_service reports no model")
    monkeypatch.setenv(role_registry.env_var_for("dissector"), "acme/rebound-1")
    assert vision_service.vision_model == "acme/rebound-1"


def test_two_roles_sharing_a_default_move_independently(monkeypatch):
    """`dissector` and `writer_vision` ship the same string. That was a coincidence nobody could
    see when both were literals; rebinding one must not drag the other, or the registry has
    merely relocated the coupling instead of removing it."""
    from backend.services.editor_llm_service import editor_llm_service

    monkeypatch.setenv(role_registry.env_var_for("writer_vision"), "acme/writer-eyes")
    assert editor_llm_service.vision_model == "acme/writer-eyes"
    assert role_registry.model_for("dissector") == "qwen/qwen3.6-27b"


def test_in_process_bind_outranks_the_environment(monkeypatch):
    monkeypatch.setenv(role_registry.env_var_for("archivist"), "from/env")
    assert role_registry.model_for("archivist") == "from/env"
    role_registry.bind("archivist", "from/bind")
    assert role_registry.model_for("archivist") == "from/bind"
    role_registry.unbind("archivist")
    assert role_registry.model_for("archivist") == "from/env"


def test_an_empty_env_var_is_not_a_binding(monkeypatch):
    """An exported-but-blank var is the shape of a misconfigured deploy, not a request to bind
    the empty string as a model name."""
    monkeypatch.setenv(role_registry.env_var_for("archivist"), "   ")
    assert role_registry.model_for("archivist") == "openai/gpt-oss-120b"


def test_an_explicit_model_argument_still_wins():
    """A caller pinning a model for one construction is not the same thing as the role's
    binding, and `FakeSemanticProvider` depends on it."""
    from backend.services.semantic_provider import SemanticProvider
    assert SemanticProvider(model="pinned/one").model == "pinned/one"


def test_an_unknown_role_refuses_rather_than_resolving_to_none():
    with pytest.raises(KeyError):
        role_registry.model_for("no_such_role")
    with pytest.raises(KeyError):
        role_registry.bind("no_such_role", "x")
    assert role_registry.get("no_such_role") is None


def test_fallbacks_are_rebindable_too(monkeypatch):
    """A role moved to another provider takes its alternates with it, or the first failure
    lands back on the old catalogue."""
    assert role_registry.fallbacks_for("semantic_annotator") == [
        "google/gemini-2.5-flash-lite", "qwen/qwen3-vl-8b-instruct"]
    monkeypatch.setenv("SEMANT_ROLE_SEMANTIC_ANNOTATOR_FALLBACKS", "a/one, b/two")
    assert role_registry.fallbacks_for("semantic_annotator") == ["a/one", "b/two"]


# ── 3. no literal creeps back to a call site ─────────────────────────────────

#: The shape of a hosted-model id: `vendor/name` with a digit or a known family word. Narrow on
#: purpose — a broad pattern would flag every path string in the codebase and get deleted.
_MODEL_LITERAL = re.compile(
    r"[\"'](?:openai|qwen|google|meta-llama|anthropic|mistralai|deepseek)/[a-z0-9][\w.\-]*[\"']"
    r"|[\"']llama-\d[\w.\-]*[\"']", re.I)

#: Where a model id is allowed to appear. The registry holds the thinker bindings; the vision
#: roster holds the organ specs.
_LITERAL_ALLOWED = {
    "backend/services/role_registry.py",
    "backend/services/vision_orchestrator/registry.py",
}

#: An ORGAN WEIGHT PIN is not a thinker binding, and this is the distinction the scan has to
#: respect rather than paper over. `CHECKPOINT = "openai/clip-vit-base-patch32"` in
#: `clip_presence_service` sits next to `REVISION = "3d74acf…"` and is governed by WEIGHTS-001:
#: it names a file and the exact commit it came from, passed to every `from_pretrained` so the
#: pin is ENFORCED at load. Making that "rebindable by env var" would break reproducibility,
#: which is the opposite of what it is for. A thinker's `openai/gpt-oss-120b` is a catalogue
#: entry with no commit and no local file — swapping it is the whole point.
_WEIGHT_PIN = re.compile(r"^\s*_?(?:CHECKPOINT|MODEL_NAME|_MODEL_NAME|REVISION)\s*[:=]")


def test_no_thinker_model_literal_survives_at_a_call_site():
    """The regression this whole module exists to prevent, checked at the source level. A new
    service that hardcodes `openai/gpt-oss-120b` passes every behavioural test in this file and
    silently re-creates the problem — only reading the source catches it."""
    root = pathlib.Path(__file__).resolve().parents[2]
    offenders = []
    for path in sorted((root / "backend").rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in _LITERAL_ALLOWED or "/tests/" in rel:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            # A literal inside a comment or a docstring line is documentation of a decision
            # (`semantic_provider`'s provider write-up names three models on purpose), not a
            # binding. Only executable lines can bind.
            if stripped.startswith("#") or stripped.startswith("·"):
                continue
            if _WEIGHT_PIN.match(line):
                continue
            if _MODEL_LITERAL.search(line):
                offenders.append(f"{rel}:{i}: {stripped[:100]}")
    assert not offenders, "model ids bound outside the role registry:\n" + "\n".join(offenders)


# ── 4. the epistemic ceiling travels with the role ───────────────────────────

#: `epistemics._DEFAULTS` EXACTLY as it stood before ROLES-001, transcribed. The point of a
#: verbatim copy rather than a derivation is that it is independent evidence: if the split
#: between the role ceilings and the remaining defaults is wrong anywhere, this disagrees.
_PRE_CHANGE_DEFAULTS = {
    "sam_refine": EpistemicStatus.VISIBLE,
    "florence_find_parts": EpistemicStatus.VISIBLE,
    "grounded_sam_find_parts": EpistemicStatus.VISIBLE,
    "find_similar": EpistemicStatus.VISIBLE,
    "negative_space": EpistemicStatus.MEASURED,
    "material_field": EpistemicStatus.MEASURED,
    "rhythm": EpistemicStatus.MEASURED,
    "pressure_zone": EpistemicStatus.MEASURED,
    "recession": EpistemicStatus.MEASURED,
    "shading": EpistemicStatus.MEASURED,
    "fall_of_light": EpistemicStatus.MEASURED,
    "architectural_axis": EpistemicStatus.MEASURED,
    "external_limit": EpistemicStatus.UNCERTAIN,
    "semantic_read": EpistemicStatus.INTERPRETIVE,
    "presence_check": EpistemicStatus.INTERPRETIVE,
    "enumerate": EpistemicStatus.INTERPRETIVE,
    "connect_marks": EpistemicStatus.INTERPRETIVE,
    "compose_percept": EpistemicStatus.INTERPRETIVE,
    "planner": EpistemicStatus.INTERPRETIVE,
    "historical_source": EpistemicStatus.SOURCED,
}


@pytest.mark.parametrize("producer,status", sorted(
    _PRE_CHANGE_DEFAULTS.items(), key=lambda kv: kv[0]))
def test_every_producer_classifies_exactly_as_it_did_before(producer, status):
    assert epistemics.default_status_for(producer) is status


def test_an_unclassified_producer_still_falls_to_uncertain():
    assert epistemics.default_status_for("newly_wired_thing") is EpistemicStatus.UNCERTAIN
    assert epistemics.default_status_for(None) is EpistemicStatus.UNCERTAIN


def test_the_two_tables_partition_rather_than_shadow_each_other():
    """A producer in both would mean the split is half-done, and whichever table lost would go
    stale invisibly — the exact drift ROLES-001 removed."""
    from_roles = {p for r in role_registry.ROLES.values() for p in r.producers}
    overlap = from_roles & set(epistemics._DEFAULTS)
    assert not overlap, f"classified twice: {sorted(overlap)}"


def test_a_role_backed_producer_takes_its_status_from_the_role():
    """The mechanism, not just the outcome: move the ceiling, the producer moves with it."""
    assert epistemics.default_status_for("sam_refine") is EpistemicStatus.VISIBLE
    assert role_registry.ceiling_for_producer("sam_refine") is EpistemicStatus.VISIBLE
    assert role_registry.ceiling_for("sam21_hiera_tiny") is EpistemicStatus.VISIBLE
    # and a producer no role claims returns None — "ask `_DEFAULTS`", not "refused".
    assert role_registry.ceiling_for_producer("negative_space") is None


def test_the_m5_rule_holds_across_every_role():
    """The rule the ceilings encode: a thinker interprets and may never claim to have measured;
    an organ that measures may never claim to have read."""
    for role in role_registry.thinkers():
        assert role.epistemic_ceiling is EpistemicStatus.INTERPRETIVE, role.name
    for role in role_registry.organs():
        assert role.epistemic_ceiling is not EpistemicStatus.INTERPRETIVE or \
            role.capability == "semantic_annotate", role.name


def test_a_role_may_weaken_its_claim_but_never_promote_it():
    """The ceiling is a CEILING — `permitted_statuses` still allows `uncertain` beneath it and
    nothing above it. Checked through the guard so the two cannot drift."""
    assert epistemics.permitted_statuses("sam_refine") == frozenset(
        {EpistemicStatus.VISIBLE, EpistemicStatus.UNCERTAIN})
    with pytest.raises(epistemics.EpistemicViolation):
        epistemics.declare("semantic_read", EpistemicStatus.MEASURED)
    assert epistemics.declare("semantic_read", EpistemicStatus.UNCERTAIN) \
        is EpistemicStatus.UNCERTAIN


# ── 5. organs are not retyped ────────────────────────────────────────────────

def test_every_roster_adapter_is_a_role_and_no_role_invents_one():
    """The organ half is GENERATED from `default_roster()`. Re-listing it would have created the
    second table this module exists to abolish, and it would fall behind on the first adapter
    added — so the generation is pinned rather than trusted."""
    from backend.services.vision_orchestrator.registry import default_roster
    roster = {s.name for s in default_roster()}
    organs = {r.name for r in role_registry.organs()}
    assert organs == roster


def test_an_organ_role_points_back_at_its_roster_entry():
    from backend.services.vision_orchestrator.registry import default_roster
    specs = {s.name: s for s in default_roster()}
    for role in role_registry.organs():
        spec = specs[role.name]
        assert role.adapter == spec.name
        assert role.capability == spec.capability.value
        assert role.default_model == spec.model_id


def test_kinds_partition_the_registry():
    assert len(role_registry.ROLES) == \
        len(role_registry.organs()) + len(role_registry.thinkers())
    assert all(r.kind in (RoleKind.ORGAN, RoleKind.THINKER)
               for r in role_registry.ROLES.values())


def test_describe_reports_the_live_binding_and_flags_a_rebind(monkeypatch):
    """"Which model actually answered" is the first question asked of any surprising output, and
    a process on an env override is otherwise indistinguishable from one on defaults."""
    rows = {r["role"]: r for r in role_registry.describe()}
    assert rows["archivist"]["rebound"] is False
    monkeypatch.setenv(role_registry.env_var_for("archivist"), "acme/other")
    rows = {r["role"]: r for r in role_registry.describe()}
    assert rows["archivist"]["model"] == "acme/other"
    assert rows["archivist"]["rebound"] is True
    assert rows["archivist"]["env_var"] == "SEMANT_ROLE_ARCHIVIST_MODEL"
