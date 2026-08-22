"""
PERCEPTUAL-FORMS-001G — which models are allowed near which composite form, and why not.

LANE C RAN THE TRIALS. THIS FILE IS THE GATE THEY BUY. `research/perception_lab/model_trials/`
holds eighteen recorded runs against controls whose answers were known in advance, and
`FINDINGS.md` turns them into seven verdicts. A verdict written in prose is a verdict a later lane
reads past, so the seven live here as data, every candidate is checked before it may contribute
anything, and a test parses `FINDINGS.md` and fails when the two disagree.

FOUR VERDICTS, AND THE TWO THAT REFUSE REFUSE FOR DIFFERENT REASONS:

    ADOPT                    measured, and good enough to be relied on. Nothing holds this yet
    ADOPT_AS_EXPERIMENTAL    measured, useful, and with a named thing still unmeasured
    REJECT                   run against the control and found wanting. It is HERE and it is wrong
    DEFER                    never run: no weights, or no hardware. Nothing is known about it

REJECT AND DEFER ARE NOT THE SAME NO, and collapsing them would lose the only distinction that
tells a person what to do next. `sam2_logits` was rejected for `extent.soft_field` because it
reported five per cent of the true softness on the one control that is genuinely boundary-less —
running it again changes nothing. `amodal_sam` is deferred because no checkpoint was published;
running it is exactly what would change something. Both come back as refusals, and the refusal
says which.

THE ROLE IS PART OF THE ADMISSION. Two of the adopted candidates are admitted as ONE GROUND AMONG
SEVERAL and not as producers, which is a different permission entirely: DINOv2 affinity measures
how alike two fragments LOOK, and Lane C's `false-twins` control is the committed proof of what
happens when that is allowed to decide — three identical discs, one confident group, one wrong
answer. So `sole_ground_forbidden` is a field on the admission rather than a convention, and
`grounds.py` enforces it where the hypothesis is assembled.

NOTHING HERE LOADS A MODEL. This module holds verdicts and refuses; it does not import torch, it
does not call an adapter, and it cannot be made to. The lane that writes a ViTMatte adapter asks
this gate first; this gate never asks the adapter anything.

NO SILENT SUBSTITUTION. `producer_for` returns the admitted producer or a typed refusal, and there
is no second candidate it falls back to. A form whose only producer is deferred stays unproduced
and says so — an unrequested different model answering the question is the failure mode this whole
file exists to prevent, because its output would look exactly like the one that was asked for.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (GroundKind, OrganFamily, RefusalCode, RefusalRecord)

ORGAN = OrganFamily.EXTENT

#: Where the evidence for every verdict below is committed, so a reader can check the ruling
#: rather than take it. Repeated in the refusal detail for the same reason.
EVIDENCE_ROOT = "research/perception_lab/model_trials"
FINDINGS = f"{EVIDENCE_ROOT}/FINDINGS.md"


class Verdict(str, Enum):
    """Lane C's four. `ADOPT` is declared and currently held by nothing, which is the state."""
    ADOPT = "adopt"
    ADOPT_AS_EXPERIMENTAL = "adopt_as_experimental"
    REJECT = "reject"
    DEFER = "defer"

    @property
    def admits(self) -> bool:
        return self in (Verdict.ADOPT, Verdict.ADOPT_AS_EXPERIMENTAL)


class Role(str, Enum):
    """What an admitted candidate is admitted TO DO. Not the same permission twice."""
    PRODUCER = "producer"      # it may write the form's payload
    GROUND = "ground"          # it may contribute one `Ground` inside somebody else's hypothesis


class ModelNotAdmitted(Exception):
    """A typed no, in flight. `.refusal` is the record; the message is only for a traceback."""

    def __init__(self, refusal: RefusalRecord) -> None:
        super().__init__(refusal.message)
        self.refusal = refusal


@dataclass(frozen=True)
class Admission:
    """One candidate, one form, one verdict — with the pin a later integrator will need."""
    model_key: str
    form_key: str
    verdict: Verdict
    role: Role
    finding: str
    checkpoint: Optional[str] = None
    revision: Optional[str] = None
    licence: Optional[str] = None
    ground_kinds: Tuple[GroundKind, ...] = ()
    sole_ground_forbidden: bool = False
    deferred_because: Optional[str] = None

    @property
    def admits(self) -> bool:
        return self.verdict.admits

    @property
    def key(self) -> Tuple[str, str]:
        return self.model_key, self.form_key

    def __str__(self) -> str:
        return f"{self.model_key} for {self.form_key}"


#: LANE C'S SEVEN, VERBATIM IN SUBSTANCE. `test_the_admission_table_is_lane_c_s_and_not_a_second
#: _opinion` parses the matrix in FINDINGS.md and fails on any disagreement, so this is a
#: transcription rather than a judgement — and a transcription that drifts is caught.
ADMISSIONS: Tuple[Admission, ...] = (
    Admission(
        model_key="vitmatte_small", form_key="extent.soft_field",
        verdict=Verdict.ADOPT_AS_EXPERIMENTAL, role=Role.PRODUCER,
        checkpoint="hustvl/vitmatte-small-composition-1k", revision=None, licence="Apache-2.0",
        finding=("recovers true coverage to 0.010-0.016 mean alpha error and invents no fringe "
                 "on a crisp edge; three things stay unmeasured, which is why it is "
                 "experimental")),
    Admission(
        model_key="sam2_logits", form_key="extent.soft_field",
        verdict=Verdict.REJECT, role=Role.PRODUCER,
        checkpoint="facebook/sam2.1-hiera-tiny", licence="Apache-2.0",
        finding=("reports 5% of the true softness on the one control that is genuinely "
                 "boundary-less. sigmoid(logit) is a mask confidence, not a coverage")),
    Admission(
        model_key="dinov2_affinity", form_key="extent.fused_hypothesis",
        verdict=Verdict.ADOPT_AS_EXPERIMENTAL, role=Role.GROUND,
        checkpoint="facebook/dinov2-small",
        revision="ed25f3a31f01632728cabb09d1542f84ab7b0056", licence="Apache-2.0",
        ground_kinds=(GroundKind.APPEARANCE_CONTINUITY,), sole_ground_forbidden=True,
        finding=("ranks two lookalikes above four true fragments on `false-twins`; it measures "
                 "resemblance, not unity, and may never be the only ground")),
    Admission(
        model_key="depth_anything_v2_small", form_key="extent.fused_hypothesis",
        verdict=Verdict.ADOPT_AS_EXPERIMENTAL, role=Role.GROUND,
        checkpoint="depth-anything/Depth-Anything-V2-Small-hf", licence="Apache-2.0",
        ground_kinds=(GroundKind.OCCLUSION_HYPOTHESIS, GroundKind.DEPTH_CONTINUITY),
        sole_ground_forbidden=True,
        finding=("supplies the occlusion ordering a fusion claim needs, and is never an Extent "
                 "measurement: no depth is written into any Extent form")),
    Admission(
        model_key="pix2gestalt", form_key="extent.visible_inferred_partition",
        verdict=Verdict.DEFER, role=Role.PRODUCER, licence="OpenRAIL-M, undecided",
        deferred_because="resources",
        finding=("22-28 GB VRAM against a 10 GB budget. Not downloaded, not run, not integrated "
                 "- deferred on resources, not failed on merit")),
    Admission(
        model_key="amodal_sam", form_key="extent.visible_inferred_partition",
        verdict=Verdict.DEFER, role=Role.PRODUCER, deferred_because="no_weights",
        finding=("a SAM adapter that would fit the budget; no public checkpoint found on "
                 "2026-08-22. Re-check, then measure the hallucinated-structure rate")),
    Admission(
        model_key="density_counter", form_key="extent.density_field",
        verdict=Verdict.REJECT, role=Role.PRODUCER, licence="research-use only",
        finding=("DAVE and GeCo need exemplars and carry research-use terms, and the form does "
                 "not need a model at all: counts from an existing extent set are exact")),
)

_BY_KEY: Mapping[Tuple[str, str], Admission] = {a.key: a for a in ADMISSIONS}


def admissions_for(form_key: str) -> Tuple[Admission, ...]:
    """Every candidate Lane C considered for one form, admitted or not.

    THE REFUSED ONES ARE PART OF THE ANSWER. A form with no admitted producer and two deferred
    candidates is in a different position from a form nobody ever looked for a model for, and a
    function that returned only the admitted ones would make those two look identical.
    """
    return tuple(a for a in ADMISSIONS if a.form_key == str(form_key))


def _refuse(admission: Optional[Admission], *, model_key: str, form_key: str,
            role: Role) -> RefusalRecord:
    """The typed no, with the verdict, the reason and where the evidence is.

    `capability_unavailable` IS THE NEAREST OF THE ELEVEN AND IT IS NOT AN EXACT FIT. Its sense is
    "the adapter is not running here", and two of these three refusals are about a model that runs
    perfectly and was measured to be wrong for this form. The alternative codes are worse:
    `unsupported_operation` says the key was never declared, and `invalid_parameters` sends a
    person to check their numbers. So the code is the nearest one and `detail.verdict` carries the
    precise version — see the lane report.
    """
    if admission is None:
        return RefusalRecord(
            code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=ORGAN,
            message=(f"{model_key!r} was never put to {form_key!r} by Lane C, so nothing is known "
                     f"about it. An unevaluated model is not a permitted one: its output would "
                     f"look exactly like an evaluated model's."),
            missing=[model_key],
            remedy=f"run the candidate against the controls and record a verdict in {FINDINGS}",
            detail={"form": form_key, "model": model_key, "verdict": None,
                    "considered": [a.model_key for a in admissions_for(form_key)],
                    "evidence": EVIDENCE_ROOT})
    if admission.verdict is Verdict.DEFER:
        return RefusalRecord(
            code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=ORGAN,
            message=(f"{admission} is deferred ({admission.deferred_because}) and was never run. "
                     f"{admission.finding}"),
            missing=[admission.model_key],
            remedy=("re-check availability, run it against the control, and record the verdict "
                    "before integrating it"),
            detail={"form": form_key, "model": model_key, "verdict": admission.verdict.value,
                    "deferred_because": admission.deferred_because,
                    "finding": admission.finding, "evidence": EVIDENCE_ROOT})
    if admission.verdict is Verdict.REJECT:
        return RefusalRecord(
            code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=ORGAN,
            message=(f"{admission} was rejected. {admission.finding}"),
            missing=[admission.model_key],
            remedy=("use the route the finding names, or re-open the verdict with new "
                    "measurements against the same controls"),
            detail={"form": form_key, "model": model_key, "verdict": admission.verdict.value,
                    "finding": admission.finding, "evidence": EVIDENCE_ROOT})
    return RefusalRecord(
        code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=ORGAN,
        message=(f"{admission} is admitted as a {admission.role.value} and was asked to act as a "
                 f"{role.value}. {admission.finding}"),
        missing=[admission.model_key],
        remedy=f"use it in the role it was admitted for, or measure it in the role you want",
        detail={"form": form_key, "model": model_key, "verdict": admission.verdict.value,
                "admitted_role": admission.role.value, "requested_role": role.value,
                "finding": admission.finding, "evidence": EVIDENCE_ROOT})


def admitted(model_key: str, form_key: str, *, role: Role) -> Admission:
    """The admission, or a raised `ModelNotAdmitted` carrying the typed refusal.

    RAISES RATHER THAN RETURNING NONE, on the grounds `definitions.operation()` gives: a caller
    that gets an object back may hand it onward, and a model that was refused and treated as
    admitted is precisely the thing this gate exists to stop.
    """
    admission = _BY_KEY.get((str(model_key), str(form_key)))
    if admission is None or not admission.admits or admission.role is not role:
        raise ModelNotAdmitted(_refuse(admission, model_key=str(model_key),
                                       form_key=str(form_key), role=role))
    return admission


def producer_for(form_key: str) -> Admission:
    """The one model admitted to WRITE this form, or a refusal naming every candidate and verdict.

    THERE IS NO FALLBACK AND THAT IS THE FEATURE. Three of the five composite forms have no
    admitted producer at all: `extent.visible_inferred_partition` has two deferred candidates,
    `extent.density_field` has one rejected one, and neither should quietly be answered by
    something else. A substituted producer's output is shaped exactly like the requested one's,
    so the substitution would be invisible in the artifact and visible only in the wrongness.
    """
    candidates = [a for a in admissions_for(form_key) if a.role is Role.PRODUCER]
    admitted_ones = [a for a in candidates if a.admits]
    if len(admitted_ones) == 1:
        return admitted_ones[0]
    if not candidates:
        raise ModelNotAdmitted(_refuse(None, model_key="(any)", form_key=str(form_key),
                                       role=Role.PRODUCER))
    if not admitted_ones:
        raise ModelNotAdmitted(RefusalRecord(
            code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=ORGAN,
            message=(f"no model is admitted to produce {form_key!r}. "
                     + "; ".join(f"{a.model_key}: {a.verdict.value}" for a in candidates)
                     + ". Nothing is substituted, because a substituted producer's output is "
                       "shaped exactly like the requested one's."),
            missing=[a.model_key for a in candidates],
            remedy="produce this form by hand or from a fixture, or admit a model for it",
            detail={"form": str(form_key), "evidence": EVIDENCE_ROOT,
                    "verdicts": {a.model_key: a.verdict.value for a in candidates}}))
    raise ModelNotAdmitted(RefusalRecord(
        code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=ORGAN,
        message=(f"{len(admitted_ones)} models are admitted to produce {form_key!r} and this "
                 f"lane will not choose between them. A choice made here would be invisible in "
                 f"the artifact."),
        missing=[a.model_key for a in admitted_ones],
        remedy="name the model explicitly",
        detail={"form": str(form_key), "admitted": [a.model_key for a in admitted_ones]}))


def ground_admission(model_key: str, kind: GroundKind, form_key: str) -> Admission:
    """The admission for a candidate contributing ONE ground of a named kind.

    THE KIND IS CHECKED, NOT ONLY THE MODEL. Depth Anything is admitted for occlusion ordering and
    depth continuity; a `Ground` claiming `shape_continuity` on its authority would be a depth
    model asserting geometry, which is the seam Lane C's rules close. So an admitted model in the
    wrong kind is refused as firmly as an unadmitted one.
    """
    admission = admitted(model_key, form_key, role=Role.GROUND)
    if kind not in admission.ground_kinds:
        raise ModelNotAdmitted(RefusalRecord(
            code=RefusalCode.CAPABILITY_UNAVAILABLE, organ=ORGAN,
            message=(f"{admission} is admitted for "
                     f"{sorted(k.value for k in admission.ground_kinds)} and this ground claims "
                     f"{kind.value}. A model vouching for a kind of evidence it does not measure "
                     f"is the seam every one of Lane C's rules closes."),
            missing=[admission.model_key],
            remedy="attribute this ground to the thing that measured it",
            detail={"form": form_key, "model": model_key, "requested_kind": kind.value,
                    "admitted_kinds": [k.value for k in admission.ground_kinds],
                    "evidence": EVIDENCE_ROOT}))
    return admission


__all__ = ["ADMISSIONS", "Admission", "EVIDENCE_ROOT", "FINDINGS", "ModelNotAdmitted", "ORGAN",
           "Role", "Verdict", "admissions_for", "admitted", "ground_admission", "producer_for"]
