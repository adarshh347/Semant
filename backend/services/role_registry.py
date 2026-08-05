"""
ROLES-001 — the role registry: organs and thinkers, declared the same way.

WHAT A ROLE IS. A role is a JOB the system needs done, named independently of whoever does
it. `dissector` is a role; `qwen/qwen3.6-27b` is the thing currently bound to it. The whole
point of the separation is that the second half can change without the first half moving.

WHY THIS MODULE EXISTS. Half the system already worked this way and half did not.

  · ORGANS were already roles. `vision_orchestrator` declares every model that looks at
    pixels as an `AdapterSpec(name, capability, resource, model_id, revision, …)` behind one
    `Adapter` protocol, with `ModelManager` deciding residency. Swapping YOLO for something
    else is an entry in `default_roster()`. Nothing at a call site names a checkpoint.

  · THINKERS were not. Every LLM/VLM model id was a literal at the point of use, and there
    were eight of them in seven files:

        llm_service.model                     = "openai/gpt-oss-120b"
        editor_llm_service.literary_model     = "openai/gpt-oss-120b"
        editor_llm_service.vision_model       = "qwen/qwen3.6-27b"
        vision_service.vision_model           = "qwen/qwen3.6-27b"
        story_block_service.model             = "llama-3.3-70b-versatile"
        semantic_provider.MODEL               = "openai/gpt-4o-mini"
        director.groq_planner.DEFAULT_MODEL   = "openai/gpt-oss-120b"
        director.argument_planner             = (imports DEFAULT_MODEL)

    Two of those share a string by coincidence rather than by decision, which is the tell: a
    literal cannot record whether two call sites use the same model because they must, or
    because nobody ever asked. Rebinding one job meant grepping for a string and hoping.

THIS MODULE IS THE ONE PLACE. Every role — organ and thinker alike — is declared here with
its default binding, and every call site asks `model_for(role)` instead of naming a model.
Rebinding is then an env var, not an edit: `SEMANT_ROLE_DISSECTOR_MODEL=…`.

THE CEILING TRAVELS WITH THE ROLE (CIRCUIT-003 M5). `epistemics._DEFAULTS` was a second table
keyed on producer name, and it encoded the same fact from the other end: a measuring organ's
output is `measured`, a semantic thinker's is `interpretive`. Two tables saying one thing drift.
So the ceiling is declared on the role, the producers a role stands behind are named on the
role, and `epistemics.default_status_for()` reads it from here. `_DEFAULTS` keeps only the
producers no role owns — and those are exactly the interesting ones (see `external_limit`).

WHAT A ROLE IS NOT. It is not a scheduler, not a client, and not a loader. It holds no weights,
opens no socket, and imports no model library. It is a table plus an env lookup, which is what
makes it importable from `epistemics` (pure) and from a slim deploy with no torch.

BINDING PRECEDENCE, highest first:
    1. `bind(role, model)`      — an in-process override. For tests and for a future admin surface.
    2. `SEMANT_ROLE_<NAME>_MODEL` — the environment. This is the "config change, no code edit" path.
    3. `Role.default_model`     — what ships.

Resolution is LIVE, not captured at import: `model_for()` re-reads the environment on every
call. A service that caches the answer in `__init__` would make the env var a lie for any
process that had already started, so the services expose it as a property instead.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from backend.services.epistemics import EpistemicStatus
from backend.services.vision_orchestrator.contracts import AdapterSpec, Capability
from backend.services.vision_orchestrator.registry import default_roster


class RoleKind(str, Enum):
    """The two halves of the system, and the only distinction that changes what a role may claim.

    ORGAN — it looks at the picture. Its output is an extent or a number, and the strongest
    thing it may say is `visible` or `measured`.

    THINKER — it reads, plans, composes or writes. It never authors geometry, and the strongest
    thing it may say is `interpretive`: a naming is an opinion even when the extent it names is
    something you can point at.
    """
    ORGAN = "organ"
    THINKER = "thinker"


#: The env var that rebinds a role. One convention, derived — never a per-role constant, so a
#: role added later is rebindable the moment it is declared.
ENV_PREFIX = "SEMANT_ROLE_"
ENV_SUFFIX = "_MODEL"


def env_var_for(role_name: str) -> str:
    return f"{ENV_PREFIX}{role_name.upper()}{ENV_SUFFIX}"


@dataclass(frozen=True)
class Role:
    """One job, and what is currently bound to it.

    `default_model` is the binding as it ships — None for a role whose executable is chosen by
    the adapter itself (a checkpoint path, not a catalogue name) or for a pure-python role.

    `epistemic_ceiling` is the strongest status this role's output may carry. It is a CEILING,
    not a stamp: `epistemics.permitted_statuses` already lets any producer weaken its own claim
    to `uncertain`, and that asymmetry is what makes this a ceiling rather than a label.

    `producers` names the `suggestion_service` producer strings this role stands behind. It is
    the join between this table and the epistemic guard, and it is EXPLICIT rather than derived
    because the mapping is genuinely not one-to-one: `dinov2_vits14` backs both `material_field`
    (a measurement it computes) and `find_similar` (a real extent it merely retrieves), and
    those are different kinds of claim from one organ.

    `capability` / `adapter` are set on organ roles only — they point back at the
    `vision_orchestrator` roster entry that executes the role, so the two tables cannot name
    different things.
    """
    name: str
    kind: RoleKind
    summary: str
    epistemic_ceiling: EpistemicStatus
    default_model: Optional[str] = None
    producers: Tuple[str, ...] = ()
    capability: Optional[str] = None      # organ: the Capability enum value
    adapter: Optional[str] = None         # organ: the AdapterSpec name in default_roster()
    provider: Optional[str] = None        # thinker: which API the model id is addressed to
    fallback_models: Tuple[str, ...] = ()

    @property
    def env_var(self) -> str:
        return env_var_for(self.name)


# ── thinkers ─────────────────────────────────────────────────────────────────
# Every model literal that used to live at a call site, moved here and named by the JOB it
# does. Two roles sharing a `default_model` is now a visible fact rather than a coincidence
# nobody could see, and either can be rebound without touching the other.

_THINKERS: List[Role] = [
    Role(
        name="dissector",
        kind=RoleKind.THINKER,
        summary="Reads an image and proposes its parts (STHŪLA anchors, SŪKṢMA fine parts).",
        # INTERPRETIVE and not MEASURED, deliberately, and this is the role the SAM 3 work is
        # aimed at: the boxes this thinker returns are ESTIMATED from a language model's reading
        # of the picture, not computed off the signal. It emits no `mask_rle` and it must not —
        # calling its output `measured` is precisely the fabrication the epistemic wall exists
        # to stop.
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="qwen/qwen3.6-27b",
        provider="groq",
    ),
    Role(
        name="writer_vision",
        kind=RoleKind.THINKER,
        summary="Looks at the image for the writing path — stage 1 of the two-stage editor.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        # Same string as `dissector` today. A separate role because the jobs are separate:
        # rebinding the part-finder to a stronger VLM should not silently change the prose.
        default_model="qwen/qwen3.6-27b",
        provider="groq",
    ),
    Role(
        name="writer_literary",
        kind=RoleKind.THINKER,
        summary="Refines raw reading into prose — stage 2 of the two-stage editor.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="openai/gpt-oss-120b",
        provider="groq",
    ),
    Role(
        name="archivist",
        kind=RoleKind.THINKER,
        summary="Summarizes a body of text and proposes plots across the corpus.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="openai/gpt-oss-120b",
        provider="groq",
    ),
    Role(
        name="story_segmenter",
        kind=RoleKind.THINKER,
        summary="Divides a long story into coherent blocks.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="llama-3.3-70b-versatile",
        provider="groq",
    ),
    Role(
        name="semantic_annotator",
        kind=RoleKind.THINKER,
        summary="Names and relates already-found candidates under a geometry-forbidding schema.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="openai/gpt-4o-mini",
        provider="openrouter",
        fallback_models=("google/gemini-2.5-flash-lite", "qwen/qwen3-vl-8b-instruct"),
        producers=("semantic_read",),
    ),
    Role(
        name="step_planner",
        kind=RoleKind.THINKER,
        summary="Turns a curator's intention into a chain of actuator calls.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="openai/gpt-oss-120b",
        provider="groq",
        # `planner` is the producer string the Director stamps on percept drafts.
        producers=("planner",),
    ),
    Role(
        name="argument_planner",
        kind=RoleKind.THINKER,
        summary="Decomposes a thesis into sub-claims, each with the evidence it would need.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="openai/gpt-oss-120b",
        provider="groq",
    ),
    Role(
        name="relation_scout",
        kind=RoleKind.THINKER,
        # ATLAS T2. Note what this summary does NOT say: it proposes PAIRS, never relations. The
        # ceiling is `interpretive` because that is the strongest thing any thinker may reach, but
        # a candidate is weaker still — it asserts nothing at all until `compare_views` has ground
        # it. The role is declared here so the Scout's model is rebindable like every other
        # thinker's, and so nothing has to invent a second table of who-uses-which-model.
        summary="Proposes which pairs of images on an Atlas might repay comparison, and why.",
        epistemic_ceiling=EpistemicStatus.INTERPRETIVE,
        default_model="openai/gpt-oss-120b",
        provider="groq",
    ),
]


# ── organs ───────────────────────────────────────────────────────────────────
# Generated from the `vision_orchestrator` roster rather than retyped. The roster is already
# the specialist-role registry; re-listing it here would create exactly the second table this
# module exists to abolish, and it would fall behind on the first adapter added.

#: What a capability is entitled to claim. The rule from M5, applied to the whole roster at once:
#: a segmenter puts an extent on the image you can point at; a feature/depth/perceptual pass
#: computes a number off the signal; a cloud VLM is reading, not looking.
_CAPABILITY_CEILINGS: Dict[Capability, EpistemicStatus] = {
    Capability.SEGMENT: EpistemicStatus.VISIBLE,
    Capability.MASK_REFINE: EpistemicStatus.VISIBLE,
    Capability.FASHION_PARSE: EpistemicStatus.VISIBLE,
    Capability.ARCH_PARSE: EpistemicStatus.VISIBLE,
    Capability.PAINTING_PROPOSE: EpistemicStatus.VISIBLE,
    Capability.GROUNDING: EpistemicStatus.VISIBLE,
    Capability.DOMAIN_ROUTE: EpistemicStatus.MEASURED,
    Capability.EMBED: EpistemicStatus.MEASURED,
    Capability.FEATURE: EpistemicStatus.MEASURED,
    Capability.PERCEPTUAL: EpistemicStatus.MEASURED,
    Capability.DEPTH: EpistemicStatus.MEASURED,
    Capability.SHADING: EpistemicStatus.MEASURED,
    Capability.SEMANTIC_ANNOTATE: EpistemicStatus.INTERPRETIVE,
    Capability.EXTERNAL_SOURCE: EpistemicStatus.SOURCED,
}

#: Which producers each roster adapter stands behind. Only the pairings where the producer's
#: claim IS the organ's own output belong here; a producer that merely uses an organ keeps its
#: own entry in `epistemics._DEFAULTS`. `find_similar` is the worked example — it runs on
#: `dinov2_vits14`, whose ceiling is `measured`, but what it hands back is a real extent on
#: another image, so it is `visible` and is deliberately absent from this map.
_ADAPTER_PRODUCERS: Dict[str, Tuple[str, ...]] = {
    "sam21_hiera_tiny": ("sam_refine",),
    "florence2_base": ("florence_find_parts",),
    "grounding_dino_tiny": ("grounded_sam_find_parts",),
    # `negative_space` is deliberately NOT here. It is `measured` like these two, but it is a
    # mask complement in pure python — its actuator declares `capability=None` — so filing it
    # under the OpenCV analyzer would be a tidy-looking lie about what computed it.
    "cpu_perceptual": ("rhythm", "pressure_zone"),
    "dinov2_vits14": ("material_field",),
    "depth_anything_v2_small": ("recession",),
    "intrinsic_ordinal_shading": ("shading", "fall_of_light"),
}


def _organ_role(spec: AdapterSpec) -> Role:
    return Role(
        name=spec.name,
        kind=RoleKind.ORGAN,
        summary=f"{spec.capability.value} — {spec.model_id}",
        epistemic_ceiling=_CAPABILITY_CEILINGS.get(spec.capability, EpistemicStatus.UNCERTAIN),
        default_model=spec.model_id,
        producers=_ADAPTER_PRODUCERS.get(spec.name, ()),
        capability=spec.capability.value,
        adapter=spec.name,
    )


def _build() -> Dict[str, Role]:
    roles: Dict[str, Role] = {}
    for spec in default_roster():
        role = _organ_role(spec)
        # `fashion_clip` and `fashion_clip_router` are two roles over one checkpoint, and both
        # are in the roster under distinct names, so no collision handling is needed. A collision
        # would mean the roster itself has a duplicate name, which is a bug there, not here.
        roles[role.name] = role
    for role in _THINKERS:
        roles[role.name] = role
    return roles


ROLES: Dict[str, Role] = _build()


# ── binding ──────────────────────────────────────────────────────────────────

#: In-process overrides. Deliberately module-level and mutable: this is the seam a test (or a
#: future admin surface) uses to rebind without touching the environment of the whole process.
_BINDINGS: Dict[str, str] = {}


def bind(role_name: str, model_id: str) -> None:
    """Override a role's binding for this process. Highest precedence."""
    if role_name not in ROLES:
        raise KeyError(f"unknown role '{role_name}'")
    _BINDINGS[role_name] = model_id


def unbind(role_name: str) -> None:
    _BINDINGS.pop(role_name, None)


def reset_bindings() -> None:
    _BINDINGS.clear()


def get(role_name: str) -> Optional[Role]:
    """A role, or None. None is a refusal upstream, never a default — the same discipline
    `director.capabilities.get` uses, and for the same reason: a role name that does not exist
    is a bug, and returning a permissive stub would hide it."""
    return ROLES.get(role_name)


def model_for(role_name: str) -> Optional[str]:
    """The model currently bound to a role. Re-read on every call, never cached.

    Raises on an unknown role. That is not defensive noise: every caller of this function is a
    call site that used to hold a literal, and a typo'd role name silently resolving to None
    would turn "which model runs" into "no model runs" without a word.
    """
    role = ROLES.get(role_name)
    if role is None:
        raise KeyError(f"unknown role '{role_name}'")
    if role_name in _BINDINGS:
        return _BINDINGS[role_name]
    env = os.environ.get(role.env_var)
    if env and env.strip():
        return env.strip()
    return role.default_model


def fallbacks_for(role_name: str) -> List[str]:
    """A thinker's alternates, in order. Rebindable as a comma-separated env var so a role can
    be moved to a different provider without a code edit — the fallbacks have to move with it
    or the first failure lands back on the old catalogue."""
    role = ROLES.get(role_name)
    if role is None:
        raise KeyError(f"unknown role '{role_name}'")
    env = os.environ.get(f"{ENV_PREFIX}{role_name.upper()}_FALLBACKS")
    if env and env.strip():
        return [m.strip() for m in env.split(",") if m.strip()]
    return list(role.fallback_models)


# ── the epistemic join ───────────────────────────────────────────────────────

def ceiling_for(role_name: str) -> EpistemicStatus:
    """The strongest status a role's output may carry. An unknown role gets `uncertain` —
    never a flattering guess, matching `epistemics.default_status_for`."""
    role = ROLES.get(role_name)
    return role.epistemic_ceiling if role else EpistemicStatus.UNCERTAIN


def _producer_index() -> Dict[str, EpistemicStatus]:
    idx: Dict[str, EpistemicStatus] = {}
    for role in ROLES.values():
        for producer in role.producers:
            idx[producer] = role.epistemic_ceiling
    return idx


_PRODUCER_CEILINGS: Dict[str, EpistemicStatus] = _producer_index()


def ceiling_for_producer(producer: Optional[str]) -> Optional[EpistemicStatus]:
    """The ceiling a producer inherits from the role behind it, or None if no role claims it.

    None means "ask `epistemics._DEFAULTS`" — it is not a refusal. The two tables partition the
    producer vocabulary rather than shadowing each other, and the partition is tested.
    """
    return _PRODUCER_CEILINGS.get(str(producer or ""))


# ── observability ────────────────────────────────────────────────────────────

def thinkers() -> List[Role]:
    return [r for r in ROLES.values() if r.kind is RoleKind.THINKER]


def organs() -> List[Role]:
    return [r for r in ROLES.values() if r.kind is RoleKind.ORGAN]


def describe() -> List[Dict[str, object]]:
    """Every role with its LIVE binding and whether that binding is the shipped default.

    `rebound` is the field worth having: a process running on an env override looks identical to
    one running on defaults unless something says so, and "which model actually answered" is the
    first question asked of any output that surprises someone.
    """
    out: List[Dict[str, object]] = []
    for name in sorted(ROLES):
        role = ROLES[name]
        bound = model_for(name)
        out.append({
            "role": name,
            "kind": role.kind.value,
            "summary": role.summary,
            "model": bound,
            "default_model": role.default_model,
            "rebound": bound != role.default_model,
            "epistemic_ceiling": role.epistemic_ceiling.value,
            "capability": role.capability,
            "adapter": role.adapter,
            "provider": role.provider,
            "producers": list(role.producers),
            "env_var": role.env_var,
        })
    return out
