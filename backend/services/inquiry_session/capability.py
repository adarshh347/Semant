"""
HARNESS-002D §4 — the one place Phase 1 is a simulation, and the wall around it.

WHAT THIS IS. A stand-in for a phrase-localization instrument: given an observable that asks for an
extent or a geometry over a named target, it returns the SHAPE such an instrument would return, so
the chain downstream of a decision is a real chain rather than a diagram. It is the single component
Phase 2 replaces, and the whole point of building it this way is that replacing it changes nothing
else.

WHAT IT IS NOT, ENFORCED RATHER THAN PROMISED:

    execution_mode = fixture      declared on the receipt, checked by the schema
    status         = simulated    a fixture may not claim `live`; the validator refuses it
    usable_as_evidence = false    a fixture that could be promoted is not a stand-in
    one attempt, spent on ATTEMPT a budget spent on success is not a budget
    no actuator, no organ, no agent, no database write, no post touched, no Evidence minted

THE NUMBERS ARE FROM A HASH, AND THE PAYLOAD SAYS SO. Every coordinate here is derived from the
sha256 of the request text — the session id, the observable id, the phrase. Not from an image; not
from anything that ever saw one. That is written into each region as `derived_from`, in the payload
a reader expands, because a plausible-looking box is exactly the thing this entire program exists
not to launder. The receipt carries the same sentence twice more, and the workbench prints it twice
again beside the geometry.

Deterministic on purpose: a replay of the same session produces the same boxes, so a byte-identical
comparison is a real check rather than one that has to exclude this payload.

WHY IT STILL EMITS A REGION AT ALL. Emitting `null` would be safer and would prove less. The
workbench's honesty guarantee is that a plausible-looking payload cannot be read as a measurement,
and a guarantee whose adversary never arrives is untested. The rehearsal gate asks whether
`SIMULATED — not evidence` is impossible to miss; it cannot answer that against an empty payload.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.inquiry_session import CapabilityReceipt, ExecutionMode, ReceiptStatus

from . import ids

PRODUCER = "inquiry_session/capability-v1"

#: What this stand-in stands in FOR. Named after the instrument rather than the topic: a
#: phrase-localizer takes words and returns where they land, and the two classes it produces are
#: the extent of a thing and the geometry of it. It does not serve `pattern`, `scalar_field`,
#: `depth`, `colour`, `semantic_reading` or `external_source`, and an option asking for one of those
#: is left undeclared so the fork pauses for a person — which is correct: choosing a route this
#: phase cannot even simulate is a choice to get nothing.
SERVABLE_CLASSES: Tuple[str, ...] = ("extent", "geometry")

CAPABILITY = "locate_phrase"

SIMULATION_NOTICE = (
    "SIMULATED — not evidence. Produced by a stand-in with no access to any image. Every "
    "coordinate below is derived from a hash of this request's text; nothing was measured, nothing "
    "was seen, and this receipt cannot support any claim.")

WHAT_A_REAL_ONE_WOULD_DO = (
    "A real phrase-localization instrument would read the target phrase against the pixels and "
    "return the extents it found, with a confidence per proposal and an explicit empty when it "
    "found none. Phase 2 replaces this adapter with one; the shape below is what the rest of the "
    "chain is already written against.")


class CapabilityBudgetSpent(RuntimeError):
    """A second invocation was attempted against a one-attempt adapter.

    Raised rather than returned. A second attempt is not a result to record — it is a caller that
    believes it has a budget it does not have, and returning a polite refusal would let a retry
    loop run forever while each individual answer looked reasonable.
    """


def _unit(seed: str, salt: str) -> float:
    """A stable number in [0, 1) from text. Not random — `Math.random` in a replayable system is a
    field that has to be excluded from every comparison, and this one never has to be."""
    digest = hashlib.sha256(f"{seed}\x00{salt}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / float(1 << 32)


def _region(seed: str, index: int) -> Dict[str, Any]:
    x = round(0.08 + 0.5 * _unit(seed, f"x{index}"), 4)
    y = round(0.08 + 0.5 * _unit(seed, f"y{index}"), 4)
    return {
        "kind": "normalised_box",
        "x": x, "y": y,
        "w": round(min(0.9 - x, 0.15 + 0.3 * _unit(seed, f"w{index}")), 4),
        "h": round(min(0.9 - y, 0.15 + 0.3 * _unit(seed, f"h{index}")), 4),
        # In the payload, next to the numbers, where somebody reading the numbers will see it.
        "derived_from": "sha256 of this request's text — not from any image",
        "measured": False,
    }


class LockedFixtureCapability:
    """One declared capability, one attempt, one kind of receipt.

    `attempts_left` guards a loop inside a single advance. It is NOT the firewall — a fresh adapter
    is built per request, so its counter resets. The firewall is the session: the coordinator
    refuses to invoke when a receipt already exists, and that check survives a restart, a redeploy
    and a second process. Both are tested, and the session-scoped one is the one that matters.
    """

    name = "locked_fixture"
    capability = CAPABILITY
    servable_classes: Tuple[str, ...] = SERVABLE_CLASSES
    max_attempts = 1

    def __init__(self, *, max_proposals: int = 3):
        self.max_proposals = max(1, int(max_proposals))
        self.attempts = 0

    @property
    def attempts_left(self) -> int:
        return max(0, self.max_attempts - self.attempts)

    def serves(self, capability_classes: Sequence[str]) -> bool:
        classes = {str(c) for c in capability_classes}
        return bool(classes) and classes <= set(self.servable_classes)

    def invoke(self, *, session_id: str, observable: Mapping[str, Any],
               alternative: Optional[Mapping[str, Any]] = None,
               images: Sequence[Mapping[str, Any]] = (), at: str = "") -> CapabilityReceipt:
        """Spend the attempt and return the receipt. The attempt is spent FIRST.

        A budget decremented after a successful call is not a budget: a failing instrument would be
        retried forever by any loop that read "no output" as "not yet done".
        """
        if self.attempts >= self.max_attempts:
            raise CapabilityBudgetSpent(
                f"this adapter allows {self.max_attempts} attempt and has spent it. A second "
                f"invocation is a caller that believes it has a budget it does not have.")
        self.attempts += 1
        started = time.perf_counter()

        observable_id = str(observable.get("observable_id") or "")
        # THE CHOSEN ALTERNATIVE DECIDES WHAT RUNS, not the observable. An observable declares
        # every class that could bear on its claim — often several, because there is more than one
        # way to make the thing observable — and the fork exists precisely to pick one of them.
        # Reading the observable's union here would refuse a route the person explicitly chose
        # because some OTHER route off the same observable needs an instrument nothing has.
        classes = [str(c) for c in ((alternative or {}).get("capability_classes")
                                    or observable.get("capability_classes") or ())]
        targets = [str(t) for t in (observable.get("targets") or ()) if str(t).strip()]
        receipt_id = ids.receipt_id(session_id, observable_id, self.capability)

        if not self.serves(classes):
            # Not a failure and not an attempt against an instrument: nothing here can produce
            # this, and saying `capability_gap` rather than `empty` is the difference between
            # "there is nothing to run" and "it ran and found nothing".
            return CapabilityReceipt(
                receipt_id=receipt_id, request_ref=observable_id, capability=self.capability,
                execution_mode=ExecutionMode.FIXTURE, status=ReceiptStatus.CAPABILITY_GAP,
                usable_as_evidence=False, attempted=False,
                detail=(f"this adapter stands in for {', '.join(self.servable_classes)} and the "
                        f"observable asks for {', '.join(classes) or '(nothing named)'}. Retrying "
                        f"will not change that — there is nothing to run."),
                provenance=self._provenance(at, observable_id, alternative))

        phrases = targets or [str(observable.get("observable_kind") or "the observable's target")]
        seed = "\x00".join([session_id, observable_id, *phrases])
        proposals: List[Dict[str, Any]] = []
        for index, phrase in enumerate(phrases[: self.max_proposals]):
            proposals.append({
                "proposal_id": f"prop_{index}",
                "phrase": phrase,
                "ground_form": (list(observable.get("ground_forms") or ["region"]) or ["region"])[0],
                "image_refs": [str(i.get("post_id") or "") for i in images],
                "region": _region(seed, index),
                # Null, not a number. A stand-in that reported 0.87 confidence would be inventing
                # the one field a reader uses to decide how much to believe it.
                "confidence": None,
                "simulated": True,
            })

        return CapabilityReceipt(
            receipt_id=receipt_id,
            request_ref=observable_id,
            capability=self.capability,
            execution_mode=ExecutionMode.FIXTURE,
            status=ReceiptStatus.SIMULATED,
            usable_as_evidence=False,
            attempted=True,
            payload={"notice": SIMULATION_NOTICE, "proposals": proposals,
                     "what_a_real_instrument_would_do": WHAT_A_REAL_ONE_WOULD_DO},
            detail=SIMULATION_NOTICE,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            provenance=self._provenance(at, observable_id, alternative))

    def _provenance(self, at: str, observable_id: str,
                    alternative: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        return {
            "producer": PRODUCER,
            "adapter": self.name,
            "requested_at": at,
            "observable_ref": observable_id,
            "chosen_alternative": str((alternative or {}).get("alternative_id") or ""),
            "chosen_label": str((alternative or {}).get("label") or ""),
            "servable_classes": list(self.servable_classes),
            "attempts_allowed": self.max_attempts,
            # Not decoration. This is the sentence a reader of the stored session finds when they
            # go looking for what produced the numbers.
            "notice": SIMULATION_NOTICE,
            "no_image_was_read": True,
            "no_actuator_or_organ_was_called": True,
        }


__all__ = ["PRODUCER", "SERVABLE_CLASSES", "CAPABILITY", "SIMULATION_NOTICE",
           "WHAT_A_REAL_ONE_WOULD_DO", "CapabilityBudgetSpent", "LockedFixtureCapability"]
