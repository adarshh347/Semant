"""
PERCEPTUAL-FORMS-001H — who would write each form, on what, and — when nothing can — why not.

THE LAB HAD A CAPABILITY TABLE AND NOT A PRODUCER TABLE, and the difference is what this file is.
`capability_catalogue` answers "is `sam3_concept` running here", which is the right question for an
adapter and the wrong one for a form: `extent.hole_set` has no adapter at all, is computed by pure
Python, and is nonetheless unwritable today for a reason that has nothing to do with a model. A
person choosing a form needs one answer covering both, and it has to be the honest one.

FOUR KINDS OF PRODUCER, and they are not interchangeable:

    model     an adapter that loads weights. Can be absent, and says which weights and which pin
    code     a pure function in this repository. Cannot be absent; its revision is the lane's
    human    a person's hand through `extent.draw`. Cannot be absent, and has no revision
    none     nothing writes this form in this deployment, and the entry says what is missing

THREE REASONS A FORM IS NOT PRODUCIBLE, KEPT APART, because they send a person to three different
places:

    deferred_form          Lane A registered the shape and no phase has enabled it
    no_operation           the form is producible and no operation declares it, so no ARTIFACT of
                           it can exist — an artifact names the operation that produced it
    capability_unavailable the producer is a model and this deployment does not have it

The second is the one that surprises people, and it is the state ten of the nineteen forms are in.
A payload can be computed, reviewed and rendered; it cannot become a `PerceptualArtifact`, because
`ArtifactIdentity.operation` would have to name an operation that never ran. That is the merged
contract's ruling and this lane does not soften it — see `derivations.py` for where those payloads
go instead.

SAM 3 IS CONFIGURED AND NEVER DISCOVERED. `sam3_concept_service.weights_path()` reads
`SAM3_WEIGHTS` and checks the file exists; it does not look in a hub cache, and a test in this
lane reads the service's source to keep it that way. A checkpoint that is on the machine and not
configured is CONFIGURATION, not capability, and this table says which of the two it is — because
"unavailable" with no reason beside it sent a previous rehearsal looking for a missing download
that was already there.

PURE. No database, no network, no route. Imports the adapter modules to read their declared
checkpoint and pin, and calls no model.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import CapabilityState, OrganFamily
from backend.services.perception_lab import definitions as D
from backend.services.perception_lab.extent_composites import admission as A

#: What the four kinds mean on the wire. Spelled rather than derived so a surface can group by it.
MODEL = "model"
CODE = "code"
HUMAN = "human"
NONE = "none"

#: Why a form cannot be written here. Closed, because "unavailable for other reasons" is the
#: category that swallows the ones worth reading.
DEFERRED_FORM = "deferred_form"
NO_OPERATION = "no_operation"
CAPABILITY_UNAVAILABLE = "capability_unavailable"

#: The revision a pure producer carries. Not a model pin — there is no checkpoint — but the thing
#: that changed when its arithmetic did, which is what a reader comparing two payloads needs.
#: What the Topology facade's arithmetic is pinned at. Not a checkpoint — there is none — but the
#: thing that changed when the measurement did.
TOPOLOGY_REVISION = "topology-facade.v1"

CODE_REVISIONS: Mapping[str, str] = {
    "perception_lab.extent_forms": "extent-exact-forms.v1",
    "perception_lab.extent_composites": "extent-composites.v1",
    "perception_lab.topology_forms": "topology-structural-forms.v1",
}


@dataclass(frozen=True)
class Producer:
    """One thing that could write one form here, and everything a person needs before choosing it.

    `revision` IS NOT OPTIONAL DECORATION. Two payloads of one form produced a week apart are
    comparable only if a reader can see whether the thing that produced them changed. A model
    names its checkpoint pin; a pure producer names the lane revision; a person names neither,
    which is itself the answer.
    """
    key: str
    kind: str
    label: str
    state: CapabilityState
    model: Optional[str] = None
    revision: Optional[str] = None
    reason: Optional[str] = None
    remedy: Optional[str] = None
    admission: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.state is CapabilityState.AVAILABLE

    def as_json(self) -> Dict[str, Any]:
        return {"key": self.key, "kind": self.kind, "label": self.label,
                "state": self.state.value, "model": self.model, "revision": self.revision,
                "reason": self.reason, "remedy": self.remedy, "admission": self.admission}


@dataclass(frozen=True)
class FormAvailability:
    """One form, and whether anything here can write it — with the reason it cannot.

    `producible` AND `writable_as_artifact` ARE TWO DIFFERENT QUESTIONS and the whole point of
    this record is that they are asked separately. The first is Lane A's `state`; the second also
    needs an operation to exist. Ten of the nineteen forms answer yes and no.
    """
    form_key: str
    organ: str
    state: str
    producible: bool
    writable_as_artifact: bool
    producers: Tuple[Producer, ...]
    blocked_by: Tuple[str, ...] = ()
    note: str = ""

    @property
    def can_be_produced_here(self) -> bool:
        return self.producible and any(p.available for p in self.producers)

    def as_json(self) -> Dict[str, Any]:
        definition = D.form(self.form_key)
        return {
            "form": self.form_key, "organ": self.organ, "label": definition.label,
            "question": definition.question, "state": self.state,
            "producible": self.producible,
            "writable_as_artifact": self.writable_as_artifact,
            "can_be_produced_here": self.can_be_produced_here,
            "blocked_by": list(self.blocked_by), "note": self.note,
            "producers": [p.as_json() for p in self.producers],
            "renderer_projections": [{"kind": p.kind, "mode": p.mode, "note": p.note}
                                     for p in definition.renderer_projections],
            "accepted_input_forms": list(definition.accepted_input_forms),
            "absence": {"examined_field": definition.absence.examined_field,
                        "empty_means": definition.absence.empty_means},
            "epistemic_ceiling": definition.epistemic_ceiling,
            "carries_hypothesis": definition.carries_hypothesis,
        }


#: Which pure module writes which form. The mapping Lane G's handover declared in prose, here as
#: data, and `test_every_producible_form_names_a_producer_that_exists` holds it total.
CODE_PRODUCERS: Mapping[str, Tuple[str, str]] = {
    "extent.boundary_rings": ("perception_lab.extent_forms", "boundary_rings"),
    "extent.hole_set": ("perception_lab.extent_forms", "hole_set"),
    "extent.fragment_set": ("perception_lab.extent_forms", "fragment_set"),
    "extent.fused_hypothesis": ("perception_lab.extent_composites", "produce_fused_hypothesis"),
    "extent.visible_inferred_partition":
        ("perception_lab.extent_composites", "produce_visible_inferred_partition"),
    "extent.hierarchy": ("perception_lab.extent_composites", "produce_extent_hierarchy"),
    "extent.density_field": ("perception_lab.extent_composites", "produce_density_field"),
    "extent.hypothesis_set": ("perception_lab.extent_composites", "produce_hypothesis_set"),
    "topology.containment_tree": ("perception_lab.topology_forms", "produce_containment_tree"),
    "topology.adjacency_graph": ("perception_lab.topology_forms", "produce_adjacency_graph"),
    "topology.transition": ("perception_lab.topology_forms", "produce_transition"),
    "topology.uncertain_relation_set":
        ("perception_lab.topology_forms", "produce_uncertain_relations"),
}


#: The adapters that cannot be absent, and what kind of thing each one is. `extent.default_adapters`
#: deliberately excludes all three — "an operation with no model behind it cannot be unavailable" —
#: so their absence from that table is the reason they are listed here rather than probed.
NON_MODEL_ADAPTERS: Mapping[str, Tuple[str, str]] = {
    "human": (HUMAN, "a person's hand, through extent.draw"),
    "canonical_region": (CODE, "an existing Region, referenced and never re-derived"),
    "lab_compare": (CODE, "exact mask arithmetic between two extent sets"),
    # ALL FIVE TOPOLOGY ORGANS ARE ARITHMETIC, and calling them `model` was the first thing this
    # table got wrong. `nestedness_organ` has computed containment per pixel since WAVE2 and loads
    # nothing; a producer selector that grouped them with SAM would make a person ask which
    # checkpoint measured their containment, and there is no answer to that question.
    "nestedness_organ": (CODE, "containment, per pixel, on a shared raster"),
    "adjacency_organ": (CODE, "boundary contact, per pixel"),
    "mask_arithmetic": (CODE, "overlap and all-pairs, exact set operations"),
    "distance_transform": (CODE, "separation and negative space, per pixel"),
    "occlusion_organ": (CODE, "depth ordering over a SUPPLIED depth field"),
}

#: Which service module declares each model adapter's identity. The CAPABILITY is asked of the
#: adapter object, never of this table: `extent.py` already knows that `sam2_refine` answers
#: through `refine_session.available()` rather than a module-level `is_available()`, and a second
#: probe written here would be a second opinion that drifts the first time one of them moves.
MODEL_ADAPTERS: Mapping[str, Tuple[str, str]] = {
    "yolo_sam2_auto": ("backend.services.sam2_auto_service",
                       "SAM 2.1 automatic — every separable instance"),
    "sam3_concept": ("backend.services.sam3_concept_service",
                     "SAM 3 — every instance of a named concept"),
    "grounded_sam": ("backend.services.grounding_detector_service",
                     "GroundingDINO — boxes for a named concept"),
    "sam2_refine": ("backend.services.sam2_auto_service",
                    "SAM 2.1 refine — a person's points and boxes"),
}


def adapter_identity(adapter_key: str) -> Producer:
    """One adapter, with its checkpoint, its pin, and the reason it is not running.

    THE REASON IS THE DELIVERABLE. `unavailable` on its own once sent a person looking for a
    missing download that was already on the disk. This separates "the weights are not
    configured" from "the path is configured and nothing is there" from "the runtime does not
    import", and each has a different next action.

    THE CAPABILITY COMES FROM THE ADAPTER OBJECT, which is the thing the resolver will ask. This
    module supplies the identity and the reason; it does not supply a second opinion about whether
    something is running.
    """
    if adapter_key in NON_MODEL_ADAPTERS:
        kind, label = NON_MODEL_ADAPTERS[adapter_key]
        return Producer(key=adapter_key, kind=kind, label=label,
                        state=CapabilityState.AVAILABLE,
                        revision=(TOPOLOGY_REVISION if kind is CODE and adapter_key not in
                                  ("canonical_region", "lab_compare") else None))
    if adapter_key == "sam3_concept":
        return _sam3()
    module_name, label = MODEL_ADAPTERS.get(
        adapter_key, ("", adapter_key))
    return _probe(module_name, label, adapter_key)


def _adapter_state(adapter_key: str) -> Tuple[CapabilityState, Optional[str]]:
    """What the adapter object itself says, and the exception if asking raised.

    Asked through `extent.default_adapters()` so the answer is the one the façade's own
    `_choose_adapter` will get. An adapter absent from that table has nothing that could be
    missing and is available by construction.
    """
    try:
        from backend.services.perception_lab import extent as facade
        table = facade.default_adapters()
    except Exception as exc:
        return CapabilityState.UNAVAILABLE, f"the runtime does not import: {type(exc).__name__}"
    adapter = table.get(adapter_key)
    if adapter is None:
        return CapabilityState.AVAILABLE, None
    try:
        return adapter.capability(), None
    except Exception as exc:                              # a probe that raises is fail-closed
        return CapabilityState.UNAVAILABLE, f"the availability probe raised {type(exc).__name__}"


def _probe(module_name: str, label: str, key: str) -> Producer:
    """A model adapter's identity from its service module, and its state from the adapter object.

    The identity constants are read WITHOUT loading a model — every service in this tree declares
    its checkpoint and its pin at module scope and imports torch lazily. An import failure is
    `unavailable` and says so rather than raising into a capability table: a deployment without
    torch must still be able to read this page and be told, honestly, that nothing is running.
    """
    state, raised = _adapter_state(key)
    checkpoint = revision = None
    if module_name:
        try:
            module = __import__(module_name, fromlist=["*"])
            checkpoint = getattr(module, "CHECKPOINT", None) or getattr(module, "MODEL_TAG", None)
            revision = (getattr(module, "REVISION", None)
                        or getattr(module, "PREPROCESSING_VERSION", None))
        except Exception as exc:                          # the slim deploy has no torch
            return Producer(key=key, kind=MODEL, label=label,
                            state=CapabilityState.UNAVAILABLE,
                            reason=f"the runtime does not import: {type(exc).__name__}",
                            remedy="install the ML stack (requirements-ml.txt) here")
    running = state is CapabilityState.AVAILABLE
    return Producer(
        key=key, kind=MODEL, label=label, model=checkpoint, revision=revision, state=state,
        reason=None if running else (raised or "the adapter reports it is not running here"),
        remedy=None if running else ("check the checkpoint this service resolves and the working "
                                     "directory it resolves it against"))


def _sam3() -> Producer:
    """SAM 3, and the three different absences the old table called one.

    CONFIGURATION IS NOT CAPABILITY. A previous rehearsal recorded a 3.2 GB checkpoint sitting in
    a hub cache while the lab reported the adapter unavailable, which was correct and unreadable:
    the service reads `SAM3_WEIGHTS` and nothing else, on purpose, because a route that fetched
    3.2 GiB mid-request is not a fallback but an outage. So the answer says WHICH absence it is,
    and each of the three has a different next action.
    """
    label = MODEL_ADAPTERS["sam3_concept"][1]
    try:
        from backend.services import sam3_concept_service as svc
    except Exception as exc:
        return Producer(key="sam3_concept", kind=MODEL, label=label,
                        state=CapabilityState.UNAVAILABLE,
                        reason=f"the runtime does not import: {type(exc).__name__}",
                        remedy="install the ML stack on this deployment")
    configured = (os.environ.get(svc.WEIGHTS_ENV) or "").strip()
    resolved = svc.weights_path()
    common = {"key": "sam3_concept", "kind": MODEL, "label": label, "model": svc.CHECKPOINT,
              "revision": svc.PREPROCESSING_VERSION}
    if not configured:
        return Producer(**common, state=CapabilityState.UNAVAILABLE,
                        reason=(f"{svc.WEIGHTS_ENV} is unset. The checkpoint is never discovered "
                                f"from a hub cache, so a copy on this machine is not availability "
                                f"until it is named."),
                        remedy=f"export {svc.WEIGHTS_ENV}=/absolute/path/to/sam3.pt")
    if resolved is None:
        return Producer(**common, state=CapabilityState.UNAVAILABLE,
                        reason=f"{svc.WEIGHTS_ENV} is set to {configured!r} and nothing is there.",
                        remedy=f"point {svc.WEIGHTS_ENV} at a checkpoint that exists")
    state, raised = _adapter_state("sam3_concept")
    if state is not CapabilityState.AVAILABLE:
        return Producer(**common, state=state,
                        reason=(raised or f"the checkpoint at {resolved} exists and the runtime "
                                f"does not import (torch / ultralytics SAM3SemanticPredictor)"),
                        remedy="install the ML stack on this deployment")
    return Producer(**common, state=CapabilityState.AVAILABLE)


def _code_producer(form_key: str) -> Producer:
    module, function = CODE_PRODUCERS[form_key]
    return Producer(key=f"{module}.{function}", kind=CODE,
                    label=f"exact derivation — {function}",
                    state=CapabilityState.AVAILABLE, model=None,
                    revision=CODE_REVISIONS[module])


def producers_for(form_key: str, *, states: Optional[Mapping[str, CapabilityState]] = None
                  ) -> Tuple[Producer, ...]:
    """Everything that could write this form here, model and code and hand alike.

    `states` IS THE REGISTRY'S OPINION AND IT WINS. A route holding a live registry knows which
    adapters answered yes on this machine in this working directory; this module can only ask the
    service modules, which resolve their checkpoints relative to the process's CWD. Where the two
    disagree the registry is right, and where the registry is silent this is the answer.
    """
    definition = D.form(form_key)
    found: List[Producer] = []
    for op_key in definition.produced_by_operations:
        operation = D.operation(op_key)
        for adapter_key in operation.adapters:
            entry = adapter_identity(adapter_key)
            stated = (states or {}).get(adapter_key)
            if stated is not None and stated is not entry.state:
                entry = Producer(**{**entry.__dict__, "state": stated,
                                    "reason": entry.reason if stated is not
                                    CapabilityState.AVAILABLE else None})
            found.append(entry)
        if operation.manual:
            found.append(Producer(key="human", kind=HUMAN, label="a person's hand",
                                  state=CapabilityState.AVAILABLE))
    if form_key in CODE_PRODUCERS:
        found.append(_code_producer(form_key))
    for entry in A.admissions_for(form_key):
        if entry.admits:
            continue
        found.append(Producer(
            key=entry.model_key, kind=MODEL, label=f"{entry.model_key} — {entry.verdict.value}",
            state=CapabilityState.UNAVAILABLE, model=entry.checkpoint, revision=entry.revision,
            reason=entry.finding, admission=entry.verdict.value,
            remedy=("re-check availability and record a verdict"
                    if entry.verdict is A.Verdict.DEFER
                    else "use the route the finding names")))
    seen: Dict[str, Producer] = {}
    for entry in found:
        seen.setdefault(entry.key, entry)
    return tuple(seen.values())


def availability(form_key: str, *,
                 states: Optional[Mapping[str, CapabilityState]] = None) -> FormAvailability:
    """One form's honest answer: can anything here write it, and if not, which absence is it."""
    definition = D.form(form_key)
    found = producers_for(form_key, states=states)
    blocked: List[str] = []
    if not definition.producible:
        blocked.append(DEFERRED_FORM)
    if not definition.has_producer:
        blocked.append(NO_OPERATION)
    if found and not any(p.available for p in found):
        blocked.append(CAPABILITY_UNAVAILABLE)
    note = ""
    if NO_OPERATION in blocked:
        note = ("no operation declares this form, so no artifact of it can exist — an artifact "
                "names the operation that produced it. The payload is computed, recorded as a "
                "derivation, and rendered; it is not promoted.")
    if DEFERRED_FORM in blocked:
        note = (f"registered and deferred. {definition.absence.empty_means}. "
                f"The shape is settled a phase before anything writes it.")
    return FormAvailability(
        form_key=form_key, organ=definition.organ, state=definition.state,
        producible=definition.producible,
        writable_as_artifact=definition.producible and definition.has_producer,
        producers=found, blocked_by=tuple(blocked), note=note)


def catalogue(*, states: Optional[Mapping[str, CapabilityState]] = None) -> Dict[str, Any]:
    """All nineteen, in contract order, as the surface reads them."""
    forms = [availability(key, states=states).as_json() for key in D.forms()]
    return {
        "forms": forms,
        "producer_kinds": [MODEL, CODE, HUMAN, NONE],
        "blocked_reasons": [DEFERRED_FORM, NO_OPERATION, CAPABILITY_UNAVAILABLE],
        "counts": {
            "registered": len(forms),
            "writable_as_artifact": sum(1 for f in forms if f["writable_as_artifact"]),
            "producible_here": sum(1 for f in forms if f["can_be_produced_here"]),
        },
    }


__all__ = ["CAPABILITY_UNAVAILABLE", "CODE", "CODE_PRODUCERS", "CODE_REVISIONS",
           "DEFERRED_FORM", "FormAvailability", "HUMAN", "MODEL", "MODEL_ADAPTERS",
           "NON_MODEL_ADAPTERS", "NO_OPERATION", "NONE", "Producer", "adapter_identity",
           "availability", "catalogue", "producers_for"]
