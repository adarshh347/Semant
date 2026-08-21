"""
PERCEPTUAL-ORGANS-002 Lane A — the organ registry, and the four things that fail closed.

`contracts.py` reads the file. `backend/schemas/perception_lab.py` types the records. This module
is the middle: the typed `OrganDefinition` / `OperationDefinition` registry, and the resolvers a
runtime calls before it is allowed to run anything.

FOUR GATES, and they are separate functions because they refuse for four different reasons and a
person needs to be told which:

    check_organ_lock       that operation exists, in another organ   → organ_locked
    resolve_parameters     drop the undeclared, clamp the bounded    → invalid_parameters
    check_inputs           the declared inputs did not resolve       → missing_extent_inputs
                                                                       missing_depth_artifact
    check_capability       the adapter is not running here           → capability_unavailable

WHAT "FAIL CLOSED" MEANS HERE, precisely. `operation()` on an unknown key RAISES rather than
returning a stub, and `resolve_parameters` returns a refusal rather than a half-built parameter
dict. The reason is the one `grammar.normalize_action` gives: a caller that gets an object back
may hand it to a runner, and a half-valid command treated as real is the failure the registry
exists to prevent.

WHAT IS NOT HERE. No adapter is called, no capability is probed, no organ algorithm is touched.
`check_capability` is handed a table by its caller — Lane A cannot know what is loadable on a
machine it is not running on, and inventing an answer would be exactly the fabricated capability
this contract refuses in the deferred organs.

PURE. No database, no network, no model, no clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (CapabilityState, InputRef, OrganFamily, RefusalCode,
                                            RefusalRecord, SessionMode)
from backend.services.perception_lab.contracts import ContractError, lab_contract

#: The law ids in `contracts/perception-lab.v1.json` that THIS runtime enforces. The parity test
#: asserts it covers every declared law, so adding a law to the contract fails the Python suite
#: until Python claims it — and the JavaScript suite until JavaScript does.
ENFORCED_LAWS: Tuple[str, ...] = (
    "organ_registry_is_closed",
    "only_two_organs_are_enabled",
    "isolation_organ_lock",
    "planner_proposes_resolver_authorizes",
    "topology_declares_extent_inputs",
    "occlusion_declares_depth",
    "depth_is_declared_not_produced",
    "no_default_fabricates_evidence",
    "identity_is_not_rendering",
    "interpretation_is_not_review",
    "three_axes_never_substitute",
    "measurement_is_never_sourced",
    "basis_ceiling_is_the_existing_ruling",
    "replay_cannot_recompute",
    "empty_is_not_refused_is_not_unavailable",
    "references_resolve_through_ids",
    "an_instance_is_named_with_its_artifact",
    # PERCEPTUAL-FORMS-001A — the form grammar
    "forms_and_operations_are_two_registries",
    "every_form_declares_what_it_needs",
    "form_state_gates_what_may_be_written",
    "partition_caps_the_status_independently_of_basis",
    "inference_is_never_visible",
    "a_form_is_never_its_renderer",
    "every_form_can_say_it_looked",
    "grouping_is_not_fusion",
    "a_hypothesis_is_not_curated_by_confidence",
    "a_transition_cites_both_revisions",
    "a_conditional_relation_keeps_its_condition",
    "a_pointed_at_raster_carries_its_digest",
    "old_records_remain_readable",
)


class UnknownOrgan(KeyError):
    """A family nobody registered. There is no fallback organ."""


class UnknownOperation(KeyError):
    """A key outside every organ's closed registry. There is no fallback operation."""


# ── the typed registry ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParameterDefinition:
    """One typed parameter, and the bound it is clamped to rather than refused for.

    `default` is ALWAYS None, and the contract test asserts it. A default here would be this file
    answering a question the person did not answer, and the answer would then be recorded on the
    run as though someone had chosen it.
    """
    name: str
    type: str
    required: bool
    description: str
    enum: Tuple[str, ...] = ()
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    max_length: Optional[int] = None
    max_items: Optional[int] = None
    clamp: bool = False
    default: None = None


@dataclass(frozen=True)
class InputDefinition:
    """One declared input, in the role the operation consumes it as.

    `required` and `required_for_execution` are two different fields because occlusion needs both:
    a depth field is optional to PLAN (a person may compose the request before they have one) and
    required to RUN. Collapsing them would either hide the dependency at plan time or make the
    request unspeakable.
    """
    role: str
    kind: str
    artifact_kinds: Tuple[str, ...]
    min: int
    max: int
    required: bool
    refusal_when_missing: RefusalCode
    scope: Tuple[str, ...]
    description: str
    required_for_execution: bool = False


@dataclass(frozen=True)
class OperationDefinition:
    key: str
    organ: str
    label: str
    question: str
    summary: str
    manual: bool
    requires_confirmation: bool
    adapters: Tuple[str, ...]
    parameters: Tuple[ParameterDefinition, ...]
    inputs: Tuple[InputDefinition, ...]
    produces: Tuple[str, ...]
    epistemic: Mapping[str, Any]
    refusals: Tuple[str, ...]
    render_projections: Tuple[str, ...]
    must_not_invoke: Tuple[str, ...]
    relation_kinds: Tuple[str, ...] = ()
    dependency_declaration: Optional[Mapping[str, Any]] = None
    notes: Tuple[str, ...] = ()

    def parameter(self, name: str) -> Optional[ParameterDefinition]:
        return next((p for p in self.parameters if p.name == name), None)

    def input_for(self, role: str) -> Optional[InputDefinition]:
        return next((i for i in self.inputs if i.role == role), None)


@dataclass(frozen=True)
class OrganDefinition:
    """One perceptual question, and everything a runtime may do about it.

    A DISABLED organ carries the first three fields and empties everything else. That emptiness is
    the deliverable: a deferred organ that declared adapters would be a capability catalogue
    entry a person could click, and clicking it would be the first lie the laboratory told.
    """
    family: str
    label: str
    question: str
    enabled: bool
    availability: str
    epistemic_ceiling: Optional[str]
    produces_artifact_kinds: Tuple[str, ...]
    consumes_artifact_kinds: Tuple[str, ...]
    declares_artifact_kinds: Tuple[str, ...]
    render_projections: Tuple[str, ...]
    manual_tools: Tuple[str, ...]
    prompt_examples: Tuple[str, ...]
    adapters: Tuple[Mapping[str, Any], ...]
    operations: Tuple[OperationDefinition, ...]
    notes: Tuple[str, ...] = ()
    deferred_note: Optional[str] = None

    def operation(self, key: str) -> Optional[OperationDefinition]:
        return next((o for o in self.operations if o.key == key), None)


def _parameter(raw: Mapping[str, Any]) -> ParameterDefinition:
    if raw.get("default") is not None:
        raise ContractError(
            f"parameter {raw.get('name')!r} declares a non-null default. Nothing in this contract "
            f"answers a question the person did not answer.")
    return ParameterDefinition(
        name=str(raw["name"]), type=str(raw["type"]), required=bool(raw["required"]),
        description=str(raw.get("description", "")),
        enum=tuple(str(v) for v in raw.get("enum", ())),
        minimum=raw.get("minimum"), maximum=raw.get("maximum"),
        max_length=raw.get("max_length"), max_items=raw.get("max_items"),
        clamp=bool(raw.get("clamp", False)), default=None)


def _input(raw: Mapping[str, Any]) -> InputDefinition:
    return InputDefinition(
        role=str(raw["role"]), kind=str(raw["kind"]),
        artifact_kinds=tuple(str(v) for v in raw.get("artifact_kinds", ())),
        min=int(raw["min"]), max=int(raw["max"]), required=bool(raw["required"]),
        refusal_when_missing=RefusalCode(str(raw["refusal_when_missing"])),
        scope=tuple(str(v) for v in raw.get("scope", ())),
        description=str(raw.get("description", "")),
        required_for_execution=bool(raw.get("required_for_execution", False)))


def _operation(organ_family: str, raw: Mapping[str, Any]) -> OperationDefinition:
    return OperationDefinition(
        key=str(raw["key"]), organ=organ_family, label=str(raw["label"]),
        question=str(raw["question"]), summary=str(raw["summary"]),
        manual=bool(raw["manual"]), requires_confirmation=bool(raw["requires_confirmation"]),
        adapters=tuple(str(v) for v in raw.get("adapters", ())),
        parameters=tuple(_parameter(p) for p in raw.get("parameters", ())),
        inputs=tuple(_input(i) for i in raw.get("inputs", ())),
        produces=tuple(str(v) for v in raw.get("produces", ())),
        epistemic=dict(raw.get("epistemic", {})),
        refusals=tuple(str(v) for v in raw.get("refusals", ())),
        render_projections=tuple(str(v) for v in raw.get("render_projections", ())),
        must_not_invoke=tuple(str(v) for v in raw.get("must_not_invoke", ())),
        relation_kinds=tuple(str(v) for v in raw.get("relation_kinds", ())),
        dependency_declaration=raw.get("dependency_declaration"),
        notes=tuple(str(v) for v in raw.get("notes", ())))


@lru_cache(maxsize=None)
def _registry() -> Tuple[Dict[str, OrganDefinition], Dict[str, OperationDefinition]]:
    organs: Dict[str, OrganDefinition] = {}
    operations: Dict[str, OperationDefinition] = {}
    for raw in lab_contract()["organs"]:
        family = str(raw["family"])
        ops = tuple(_operation(family, o) for o in raw.get("operations", ()))
        for op in ops:
            if op.key in operations:
                raise ContractError(f"operation {op.key!r} is declared twice")
            operations[op.key] = op
        organs[family] = OrganDefinition(
            family=family, label=str(raw["label"]), question=str(raw["question"]),
            enabled=bool(raw["enabled"]), availability=str(raw["availability"]),
            epistemic_ceiling=raw.get("epistemic_ceiling"),
            produces_artifact_kinds=tuple(str(v) for v in raw.get("produces_artifact_kinds", ())),
            consumes_artifact_kinds=tuple(str(v) for v in raw.get("consumes_artifact_kinds", ())),
            declares_artifact_kinds=tuple(str(v) for v in raw.get("declares_artifact_kinds", ())),
            render_projections=tuple(str(v) for v in raw.get("render_projections", ())),
            manual_tools=tuple(str(v) for v in raw.get("manual_tools", ())),
            prompt_examples=tuple(str(v) for v in raw.get("prompt_examples", ())),
            adapters=tuple(dict(a) for a in raw.get("adapters", ())),
            operations=ops, notes=tuple(str(v) for v in raw.get("notes", ())),
            deferred_note=raw.get("deferred_note"))
    return organs, operations


def organs() -> Mapping[str, OrganDefinition]:
    """All eight, in contract order. Six of them are registered and disabled."""
    return _registry()[0]


def operations() -> Mapping[str, OperationDefinition]:
    """Every declared operation across every organ. Thirteen, in this phase."""
    return _registry()[1]


def organ(family: str) -> OrganDefinition:
    try:
        return _registry()[0][str(family)]
    except KeyError:
        raise UnknownOrgan(
            f"{family!r} is not a registered organ family. The eight are "
            f"{sorted(_registry()[0])}, and there is no fallback.") from None


def operation(key: str) -> OperationDefinition:
    try:
        return _registry()[1][str(key)]
    except KeyError:
        raise UnknownOperation(
            f"{key!r} is not a declared operation. Unknown keys are `unsupported_operation`, "
            f"never a best guess at what was meant.") from None


def enabled_organs() -> Tuple[OrganDefinition, ...]:
    return tuple(o for o in _registry()[0].values() if o.enabled)


def is_enabled(family: str) -> bool:
    return organ(family).enabled


def producible_artifact_kinds() -> frozenset:
    """What an ENABLED organ can mint. `depth_field` is deliberately not in here."""
    return frozenset(k for o in enabled_organs() for k in o.produces_artifact_kinds)


def operations_for(family: str) -> Tuple[OperationDefinition, ...]:
    return organ(family).operations


# ── gate 1: the organ lock ───────────────────────────────────────────────────


def check_organ_lock(op_key: str, *, selected_organ: str,
                     mode: SessionMode) -> Optional[RefusalRecord]:
    """Refuse an operation that belongs to another organ.

    `unsupported_operation` and `organ_locked` are two refusals because they mean two things to a
    person. The first says "there is no such thing"; the second says "there is, and this session
    is not the place to ask for it — switch to chain mode, or select that organ."
    """
    owner = operations().get(op_key)
    if owner is None:
        return RefusalRecord(
            code=RefusalCode.UNSUPPORTED_OPERATION, organ=OrganFamily(selected_organ),
            operation=op_key,
            message=_message("unsupported_operation", operation=op_key, organ=selected_organ),
            missing=[], remedy="choose a declared operation of this organ")
    if owner.organ == selected_organ:
        return None
    if mode is SessionMode.CHAIN:
        # Chain mode permits the crossing. It does NOT permit it silently — the plan carrying this
        # step must set `requires_confirmation`, which `LabPlan` enforces.
        return None
    return RefusalRecord(
        code=RefusalCode.ORGAN_LOCKED, organ=OrganFamily(selected_organ), operation=op_key,
        message=_message("organ_locked", operation=op_key, organ=selected_organ,
                         operation_organ=owner.organ),
        missing=[], remedy=f"switch to chain mode and confirm, or select the {owner.organ} organ",
        detail={"operation_organ": owner.organ})


# ── gate 2: parameters — drop the undeclared, clamp the bounded ──────────────


@dataclass(frozen=True)
class ParameterResolution:
    """What the resolver made of a planner's parameters.

    Three outputs rather than one, because the three tell a reader three different things: what
    will actually run, what a planner tried to smuggle in, and where a person's number met a
    bound. A resolver that returned only `clean` would make the second invisible, and the second
    is the one worth watching.
    """
    clean: Dict[str, Any] = field(default_factory=dict)
    dropped: List[Tuple[str, str]] = field(default_factory=list)
    clamped: List[Tuple[str, Any, Any, str]] = field(default_factory=list)
    refusal: Optional[RefusalRecord] = None

    @property
    def ok(self) -> bool:
        return self.refusal is None


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "enum": lambda v: isinstance(v, str),
    "string_list": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
    "point_list": lambda v: isinstance(v, list) and all(
        isinstance(x, (list, tuple)) and len(x) == 2 for x in v),
    "box": lambda v: isinstance(v, dict) and {"x", "y", "w", "h"} <= set(v),
    "mask_rle": lambda v: isinstance(v, dict) and {"size", "counts"} <= set(v),
}


def resolve_parameters(op_key: str, params: Mapping[str, Any]) -> ParameterResolution:
    """Clamp a planner's parameters to the operation's declaration.

    UNDECLARED KEYS ARE DROPPED AND RECORDED, not refused. This is `grammar._clamp_params`'s rule
    and it is here for the same reason: a model planner that tried to hand the runner a `mask_rle`
    or a `region_id` it invented should be VISIBLE having tried, and refusing the whole plan would
    replace that record with a shrug.

    A DECLARED KEY OF THE WRONG TYPE REFUSES. That is not a smuggling attempt, it is a caller that
    does not know what it is asking for, and clamping a string into an integer bound would be this
    module inventing the value.
    """
    op = operation(op_key)
    declared = {p.name: p for p in op.parameters}
    clean: Dict[str, Any] = {}
    dropped: List[Tuple[str, str]] = []
    clamped: List[Tuple[str, Any, Any, str]] = []

    for name, value in params.items():
        spec = declared.get(name)
        if spec is None:
            dropped.append((name, f"{op_key} declares no parameter {name!r}"))
            continue
        if value is None:
            dropped.append((name, "null is absence, and absence is not a value to record"))
            continue
        if not _TYPE_CHECKS[spec.type](value):
            return ParameterResolution(dropped=dropped, clamped=clamped,
                                       refusal=_invalid(op, f"{name!r} is not a {spec.type}"))
        if spec.type == "enum" and value not in spec.enum:
            return ParameterResolution(
                dropped=dropped, clamped=clamped,
                refusal=_invalid(op, f"{name!r} must be one of {list(spec.enum)}"))
        if spec.type == "string" and spec.max_length and len(value) > spec.max_length:
            return ParameterResolution(
                dropped=dropped, clamped=clamped,
                refusal=_invalid(op, f"{name!r} exceeds {spec.max_length} characters"))
        if spec.type in ("string_list", "point_list") and spec.max_items \
                and len(value) > spec.max_items:
            if not spec.clamp:
                return ParameterResolution(
                    dropped=dropped, clamped=clamped,
                    refusal=_invalid(op, f"{name!r} exceeds {spec.max_items} items"))
            clamped.append((name, len(value), spec.max_items, f"max_items={spec.max_items}"))
            value = value[:spec.max_items]
        if spec.type in ("integer", "number"):
            bounded, bound = _apply_bounds(spec, value)
            if bound is not None:
                if not spec.clamp:
                    return ParameterResolution(
                        dropped=dropped, clamped=clamped,
                        refusal=_invalid(op, f"{name!r} is outside {bound}"))
                clamped.append((name, value, bounded, bound))
                value = bounded
        clean[name] = value

    for name, spec in declared.items():
        if spec.required and name not in clean:
            return ParameterResolution(
                dropped=dropped, clamped=clamped,
                refusal=_invalid(op, f"{name!r} is required"))

    return ParameterResolution(clean=clean, dropped=dropped, clamped=clamped)


def _bound_label(value: Any) -> str:
    """Format a bound the way JavaScript would.

    `"minimum": 0.0` in the contract arrives here as `0.0` and in the browser as `0`, so an
    f-string would put `minimum=0.0` in a Python refusal and `minimum=0` in the JavaScript one —
    the same law, said two ways, to the same person. The parity loop caught exactly that, which is
    what the loop is for.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _apply_bounds(spec: ParameterDefinition, value: Any) -> Tuple[Any, Optional[str]]:
    if spec.minimum is not None and value < spec.minimum:
        return (type(value)(spec.minimum), f"minimum={_bound_label(spec.minimum)}")
    if spec.maximum is not None and value > spec.maximum:
        return (type(value)(spec.maximum), f"maximum={_bound_label(spec.maximum)}")
    return (value, None)


def _invalid(op: OperationDefinition, detail: str) -> RefusalRecord:
    return RefusalRecord(
        code=RefusalCode.INVALID_PARAMETERS, organ=OrganFamily(op.organ), operation=op.key,
        message=_message("invalid_parameters", operation=op.key, detail=detail),
        missing=[], remedy="read the operation's parameter declarations", detail={"why": detail})


# ── gate 3: inputs ───────────────────────────────────────────────────────────


def check_inputs(op_key: str, refs: Sequence[InputRef], *,
                 for_execution: bool) -> Optional[RefusalRecord]:
    """Refuse when a declared input did not resolve, with the code that input declares.

    `for_execution` is the occlusion case in one boolean. At plan time a missing depth field is
    fine — the person is composing. At run time it is `missing_depth_artifact`, and the difference
    between those two moments is the difference between a laboratory that lets you think and one
    that pretends it can find a depth field on its own.
    """
    op = operation(op_key)
    by_role: Dict[str, int] = {}
    for ref in refs:
        by_role[ref.role] = by_role.get(ref.role, 0) + 1

    for spec in op.inputs:
        count = by_role.get(spec.role, 0)
        needed = spec.required or (for_execution and spec.required_for_execution)
        if count == 0 and needed:
            return RefusalRecord(
                code=spec.refusal_when_missing, organ=OrganFamily(op.organ), operation=op.key,
                message=_message(spec.refusal_when_missing.value, operation=op.key),
                missing=[spec.role],
                remedy=spec.description,
                detail={"role": spec.role, "artifact_kinds": list(spec.artifact_kinds),
                        "min": spec.min, "max": spec.max})
        if count and count < spec.min:
            return RefusalRecord(
                code=spec.refusal_when_missing, organ=OrganFamily(op.organ), operation=op.key,
                message=f"{op.key} needs at least {spec.min} {spec.role} inputs; {count} resolved",
                missing=[spec.role], remedy=spec.description,
                detail={"role": spec.role, "min": spec.min, "resolved": count})
        if count > spec.max:
            return RefusalRecord(
                code=RefusalCode.INVALID_PARAMETERS, organ=OrganFamily(op.organ),
                operation=op.key,
                message=f"{op.key} accepts at most {spec.max} {spec.role} inputs; {count} given",
                missing=[], remedy=spec.description,
                detail={"role": spec.role, "max": spec.max, "given": count})

    unknown_roles = sorted(set(by_role) - {s.role for s in op.inputs})
    if unknown_roles:
        return _invalid(op, f"{op.key} declares no input role {unknown_roles}")
    return None


# ── gate 4: capability ───────────────────────────────────────────────────────


def check_capability(op_key: str, *, adapter: Optional[str],
                     states: Mapping[str, CapabilityState]) -> Optional[RefusalRecord]:
    """Refuse when the adapter this operation would use is not running here.

    The table comes from the CALLER. Lane A has no way to know what is loadable on the machine the
    lab runs on, and an adapter this file declared `available` would be exactly the fabricated
    capability the six deferred organs exist to avoid. An adapter the caller has no opinion about
    is `unknown_until_runtime`, and that is not a refusal — it is a caller that has not looked yet.
    """
    op = operation(op_key)
    candidates = (adapter,) if adapter else op.adapters
    if not candidates:
        return None
    usable = [a for a in candidates
              if states.get(a, CapabilityState.UNKNOWN_UNTIL_RUNTIME)
              is not CapabilityState.UNAVAILABLE]
    if usable:
        return None
    return RefusalRecord(
        code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=OrganFamily(op.organ), operation=op.key,
        message=_message("capability_unavailable", adapter=", ".join(candidates)),
        missing=list(candidates),
        remedy="choose another adapter, or run where the model lives",
        detail={"adapters": list(candidates)})


# ── PERCEPTUAL-FORMS-001A: the form registry, and its two gates ──────────────
#
# A FORM IS WHAT WAS PERCEIVED. AN OPERATION IS WHAT WAS ASKED FOR. Two registries, because they
# have different arities in both directions: one operation may produce several forms, several
# operations may produce one form, and — the case this phase depends on — a form may be registered
# with NO operation producing it, so that a payload shape can be frozen and reviewed a phase
# before anything computes it.
#
# THE TWO GATES ARE SEPARATE FUNCTIONS for the same reason the other four are: they refuse for two
# different reasons and a person needs to be told which.
#
#     check_input_forms       the artifact resolved; it is the wrong ANSWER  → unsupported_form
#     check_form_producible   the form is real, declared, and deferred       → form_not_producible


@dataclass(frozen=True)
class RendererProjection:
    """One drawing a form supports, and whether the payload contains it.

    `mode` is the whole point. `direct` means the record holds the shape and a reader draws what
    was measured; `derived` means the reader must COMPUTE it, and therefore must stamp it as its
    own work. A renderer is never the measurement, and this field is where a runtime finds out
    which of the two it is holding.
    """
    kind: str
    mode: str
    note: str = ""

    @property
    def is_direct(self) -> bool:
        return self.mode == "direct"


@dataclass(frozen=True)
class FormAbsence:
    """What an empty answer in this form means, and the field that proves something looked."""
    examined_field: str
    empty_means: str
    may_not_be_confused_with: Tuple[str, ...] = ()


@dataclass(frozen=True)
class FormDefinition:
    """One canonical perceptual form — everything a runtime needs before it may write one."""
    key: str
    organ: str
    label: str
    question: str
    state: str
    artifact_kind: str
    payload_variant: str
    produced_by_operations: Tuple[str, ...]
    accepted_input_forms: Tuple[str, ...]
    producer_classes: Tuple[str, ...]
    admissible_bases: Tuple[str, ...]
    admissible_partitions: Tuple[str, ...]
    epistemic_ceiling: str
    carries_hypothesis: bool
    renderer_projections: Tuple[RendererProjection, ...]
    manual_tools: Tuple[str, ...]
    comparison_methods: Tuple[str, ...]
    required_provenance: Tuple[str, ...]
    absence: FormAbsence
    test_obligations: Tuple[str, ...]
    notes: Tuple[str, ...] = ()

    @property
    def producible(self) -> bool:
        """`deferred` forms are designed and unwritable. That is not a bug; it is the state."""
        return self.state != "deferred"

    @property
    def has_producer(self) -> bool:
        """Whether any operation declares this form's kind — which is what decides today.

        Sixteen of the nineteen answer False, and that is the real gate: an artifact names the
        operation that produced it, so a form no operation declares has no artifact whatever its
        state says. `producible` is the further question of whether it ever could.
        """
        return bool(self.produced_by_operations)

    def projection(self, kind: str) -> Optional[RendererProjection]:
        return next((p for p in self.renderer_projections if p.kind == kind), None)

    def accepts(self, form_key: str) -> bool:
        return form_key in self.accepted_input_forms


class UnknownForm(KeyError):
    """A form key nobody registered. There is no fallback form."""


def _form(raw: Mapping[str, Any]) -> FormDefinition:
    absence = raw["absence"]
    return FormDefinition(
        key=str(raw["key"]), organ=str(raw["organ"]), label=str(raw["label"]),
        question=str(raw["question"]), state=str(raw["state"]),
        artifact_kind=str(raw["artifact_kind"]), payload_variant=str(raw["payload_variant"]),
        produced_by_operations=tuple(str(v) for v in raw.get("produced_by_operations", ())),
        accepted_input_forms=tuple(str(v) for v in raw.get("accepted_input_forms", ())),
        producer_classes=tuple(str(v) for v in raw["producer_classes"]),
        admissible_bases=tuple(str(v) for v in raw["admissible_bases"]),
        admissible_partitions=tuple(str(v) for v in raw["admissible_partitions"]),
        epistemic_ceiling=str(raw["epistemic_ceiling"]),
        carries_hypothesis=bool(raw["carries_hypothesis"]),
        renderer_projections=tuple(
            RendererProjection(kind=str(p["kind"]), mode=str(p["mode"]), note=str(p.get("note", "")))
            for p in raw["renderer_projections"]),
        manual_tools=tuple(str(v) for v in raw.get("manual_tools", ())),
        comparison_methods=tuple(str(v) for v in raw.get("comparison_methods", ())),
        required_provenance=tuple(str(v) for v in raw["required_provenance"]),
        absence=FormAbsence(
            examined_field=str(absence["examined_field"]),
            empty_means=str(absence["empty_means"]),
            may_not_be_confused_with=tuple(
                str(v) for v in absence.get("may_not_be_confused_with", ()))),
        test_obligations=tuple(str(v) for v in raw["test_obligations"]),
        notes=tuple(str(v) for v in raw.get("notes", ())))


@lru_cache(maxsize=None)
def _form_registry() -> Dict[str, FormDefinition]:
    out: Dict[str, FormDefinition] = {}
    for raw in lab_contract()["perceptual_forms"]:
        definition = _form(raw)
        if definition.key in out:
            raise ContractError(f"form {definition.key!r} is declared twice")
        if not definition.producer_classes:
            raise ContractError(
                f"form {definition.key!r} declares no producer class. A form nothing could ever "
                f"write is a word in a registry.")
        if not definition.renderer_projections:
            raise ContractError(
                f"form {definition.key!r} declares no renderer projection. A measurement nobody "
                f"can look at cannot be reviewed, and an unreviewable measurement is a rumour.")
        if not definition.test_obligations:
            raise ContractError(
                f"form {definition.key!r} declares no test obligation. A law nothing fails on is "
                f"a comment.")
        out[definition.key] = definition
    for definition in out.values():
        for accepted in definition.accepted_input_forms:
            if accepted not in out:
                raise ContractError(
                    f"form {definition.key!r} accepts {accepted!r}, which is not a registered "
                    f"form.")
    return out


def forms() -> Mapping[str, FormDefinition]:
    """All nineteen, in contract order. Nine of them are registered and deferred."""
    return _form_registry()


def form(key: str) -> FormDefinition:
    """FAIL CLOSED. An unknown key raises rather than returning a stub, for the same reason
    `operation()` does: a caller that got an object back might render a control for it."""
    try:
        return _form_registry()[str(key)]
    except KeyError:
        raise UnknownForm(
            f"{key!r} is not a registered perceptual form. The nineteen are "
            f"{sorted(_form_registry())}, and there is no fallback.") from None


def forms_for(family: str) -> Tuple[FormDefinition, ...]:
    """Every form of one organ, deferred ones included — they are the point of the registry."""
    organ(family)                       # raises UnknownOrgan on a family nobody registered
    return tuple(f for f in _form_registry().values() if f.organ == family)


def producible_forms() -> Tuple[FormDefinition, ...]:
    return tuple(f for f in _form_registry().values() if f.producible)


def form_for_artifact_kind(kind: str) -> Optional[FormDefinition]:
    """The form a kind carries, or None for `refusal` and `depth_field`, which carry none."""
    return next((f for f in _form_registry().values() if f.artifact_kind == str(kind)), None)


#: How the four obtainable statuses order, read from the records module's single declaration
#: rather than retyped. A second ordering here would be a second chance to disagree.
def _rank(status: str) -> int:
    from backend.schemas.perception_lab import STATUS_ORDER, EpistemicStatus  # local: cycle
    return STATUS_ORDER[EpistemicStatus(status)]


def derived_ceiling(form_key: str, *, basis: str, partition: str,
                    input_statuses: Sequence[str] = ()) -> str:
    """The strongest status a claim in this form may carry, given everything that caps it.

    THREE CAPS, AND THE THIRD IS WHY THIS FUNCTION EXISTS. The basis ceiling and the partition
    ceiling are both properties of the record and are enforced by the schema. The third — that an
    `exact_derivation` is never stronger than the weakest artifact it derived FROM — needs the
    inputs in hand, which a validator looking at one record does not have. So the composing
    runtime asks here, and records the answer.

    Passing no input statuses is not the same as passing strong ones: it means the caller is not
    composing, and only the two record-local ceilings apply.
    """
    definition = form(form_key)
    if basis not in definition.admissible_bases:
        raise ContractError(
            f"form {form_key!r} is measured from {list(definition.admissible_bases)}, not from "
            f"{basis!r}")
    if partition not in definition.admissible_partitions:
        raise ContractError(
            f"form {form_key!r} admits the partitions {list(definition.admissible_partitions)}, "
            f"not {partition!r}")
    grammar = lab_contract()["form_grammar"]
    caps = [lab_contract()["epistemics"]["basis_ceilings"][basis],
            grammar["epistemic_partitions"]["ceilings"][partition],
            definition.epistemic_ceiling]
    if partition in ("exact_derivation", "interpretive_grouping"):
        caps.extend(input_statuses)
    return min(caps, key=_rank)


# ── gate 5: the input form ───────────────────────────────────────────────────


def check_input_forms(form_key: str, supplied: Sequence[str], *,
                      operation_key: Optional[str] = None) -> Optional[RefusalRecord]:
    """Refuse a supplied artifact whose FORM the consuming form does not read.

    This is not `unknown_reference`. The artifact resolved perfectly well — it is simply the wrong
    kind of answer, and telling a person "no such artifact" when what they supplied was a soft
    field where a hard mask was wanted would send them looking for a selection bug that is not
    there.

    A form that accepts nothing accepts nothing: it is a direct measurement of the image, and
    handing it an artifact is a request nobody can satisfy.
    """
    definition = form(form_key)
    wrong = [s for s in supplied if not definition.accepts(str(s))]
    if not wrong:
        return None
    return RefusalRecord(
        code=RefusalCode.UNSUPPORTED_FORM, organ=OrganFamily(definition.organ),
        operation=operation_key,
        message=_message("unsupported_form",
                         operation=operation_key or definition.key,
                         form=", ".join(str(w) for w in wrong),
                         accepted=", ".join(definition.accepted_input_forms) or "no artifact"),
        missing=list(definition.accepted_input_forms),
        remedy="supply one of the declared input forms, or ask the question the supplied form "
               "can answer",
        detail={"form": definition.key, "supplied": [str(w) for w in wrong],
                "accepted": list(definition.accepted_input_forms)})


# ── gate 6: may this form be written at all ──────────────────────────────────


def check_form_producible(form_key: str, *,
                          operation_key: Optional[str] = None) -> Optional[RefusalRecord]:
    """Refuse an attempt to WRITE a form that is registered and deferred.

    The same discipline `depth_field` is held to. A payload shape agreed in advance is what stops
    the lane that finally implements fog from inventing its own field record; a state that let it
    be written today would make the registry claim the laboratory can already see something it
    cannot.
    """
    definition = form(form_key)
    if definition.producible:
        return None
    return RefusalRecord(
        code=RefusalCode.FORM_NOT_PRODUCIBLE, organ=OrganFamily(definition.organ),
        operation=operation_key,
        message=_message("form_not_producible", form=definition.key),
        missing=[definition.key],
        remedy="wait for the phase that enables it, or produce a form that exists",
        detail={"form": definition.key, "state": definition.state})


# ── messages ─────────────────────────────────────────────────────────────────


def _message(code: str, **fields: Any) -> str:
    """The contract's template, filled. Templates live in the contract so both runtimes say the
    same sentence to the same person."""
    template = lab_contract()["messages"].get(code)
    if template is None:
        raise ContractError(f"no message template for {code!r}")
    try:
        return template.format(**fields)
    except KeyError as exc:
        raise ContractError(f"message {code!r} needs field {exc}") from None


__all__ = [
    "ENFORCED_LAWS", "UnknownOrgan", "UnknownOperation", "ParameterDefinition",
    "InputDefinition", "OperationDefinition", "OrganDefinition", "ParameterResolution",
    "organs", "operations", "organ", "operation", "enabled_organs", "is_enabled",
    "producible_artifact_kinds", "operations_for", "check_organ_lock", "resolve_parameters",
    "check_inputs", "check_capability",
    # PERCEPTUAL-FORMS-001A
    "UnknownForm", "RendererProjection", "FormAbsence", "FormDefinition", "forms", "form",
    "forms_for", "producible_forms", "form_for_artifact_kind", "derived_ceiling",
    "check_input_forms", "check_form_producible",
]
