"""
HARNESS-002D §6 — the provisional answer, with every sentence bound to what it rests on.

WHAT THE COMPOSER IS ALLOWED TO SEE. Claims, verdicts, evidence refs, the person's decisions and
amendments, gaps, refusals and semantic remainder. That is the whole input, and the omission is
load-bearing: it never receives the source posts, the image urls, or the scene reading's prose.

A composer handed the pictures would perform a second, unrecorded visual reading and write its
findings into an answer whose claims all trace to somewhere else — and nothing downstream could
tell that sentence apart from one the compiler produced. A composer handed the reading's prose
would paraphrase it back, and a paraphrase of an interpretive paragraph reads exactly like a
synthesis of a claim graph while resting on nothing that was ever decomposed. So the input is the
STRUCTURED RECORD only. What survived the decomposition is what may be written about.

EVERY SECTION NAMES WHAT IT RESTS ON. Claim refs, evidence refs — possibly empty — an epistemic
rendering, and the decisions that shaped it. A section with no evidence is perfectly legitimate;
most of Phase 1 is. What it may not do is fail to SAY so, which is what stops fluent prose from
reading as a finding, and the schema refuses a `measured` or `visible` section that cites nothing.

AN UNKNOWN REFERENCE REFUSES THE WHOLE COMPOSITION. Not the section — the composition. A synthesis
in which one sentence points at a claim that does not exist is a synthesis whose bindings cannot be
trusted anywhere, and dropping the bad section would leave a plausible answer built by a producer
that has just been shown to invent references.

TWO IMPLEMENTATIONS, ONE CONTRACT. `DeterministicComposer` composes from the record with no model
at all and is fully capable — Lane B's `DeterministicFormatter` pattern. `ModelSynthesisComposer`
binds the merged `synthesis_composer` role and is held to exactly the same reference check, so a
model cannot buy itself a weaker standard by being a model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.inquiry_session import (SemanticInquirySession, Synthesis, SynthesisSection,
                                             sha256_of)
from backend.services import role_registry
from backend.services.inquiry_interaction import machine, projections

from . import ids

ROLE = "synthesis_composer"
PRODUCER = "inquiry_session/composer-v1"

#: The renderings a section may declare. `measured` and `visible` are reachable only with an
#: evidence ref, and the schema — not this list — is what enforces that.
RENDERINGS = ("measured", "visible", "sourced", "interpretive", "imagined", "unresolved")

#: On every answer this phase produces, in the answer itself rather than in a footer somewhere.
PHASE_NOTE = (
    "Phase 1: one capability was invoked and it was a declared SIMULATION. Nothing in this answer "
    "was measured from any image. Every statement below is a reading of the question and the "
    "pictures, or a record of what would have to be observed for it to become more than that.")

MAX_SECTIONS = 12
MAX_SECTION_CHARS = 1600


class CompositionRefused(Exception):
    """A composition naming something that does not exist. Carries every bad reference at once, so
    a producer is told all of what it invented rather than one thing per round trip."""

    def __init__(self, detail: str, *, unknown: Sequence[str] = ()) -> None:
        super().__init__(detail)
        self.detail = detail
        self.unknown = list(unknown)


# ── what a composer may see ──────────────────────────────────────────────────

@dataclass(frozen=True)
class CompositionRequest:
    """The whole input. There is no field here that could carry an image or a reading's prose."""
    session_id: str
    prompt: str
    revision: int
    claims: Tuple[Mapping[str, Any], ...] = ()
    verdicts: Tuple[Mapping[str, Any], ...] = ()
    evidence: Tuple[Mapping[str, Any], ...] = ()
    decisions: Tuple[Mapping[str, Any], ...] = ()
    amendments: Tuple[Mapping[str, Any], ...] = ()
    remainder: Tuple[Mapping[str, Any], ...] = ()
    refusals: Tuple[Mapping[str, Any], ...] = ()
    gaps: Tuple[str, ...] = ()
    receipts: Tuple[Mapping[str, Any], ...] = ()

    def claim(self, claim_id: str) -> Optional[Mapping[str, Any]]:
        return next((c for c in self.claims if str(c.get("claim_id")) == claim_id), None)

    def verdict_for(self, claim_id: str) -> str:
        return next((str(v.get("outcome") or "") for v in self.verdicts
                     if str(v.get("claim_ref")) == claim_id), "")

    def known_refs(self) -> Dict[str, set]:
        return {
            "claim_refs": {str(c.get("claim_id")) for c in self.claims},
            "evidence_refs": {str(e.get("evidence_id")) for e in self.evidence},
            "refusal_refs": ({str(r.get("refusal_id")) for r in self.refusals}
                             | {str(r.get("remainder_id")) for r in self.remainder}),
            "decision_refs": {str(d.get("decision_id")) for d in self.decisions}
                             | {str(a.get("amendment_id")) for a in self.amendments},
        }


def request_for(session: SemanticInquirySession) -> CompositionRequest:
    """The session, narrowed to what a composer may read. The narrowing IS the guarantee."""
    graph = session.graph if isinstance(session.graph, dict) else {}
    decisions: List[Mapping[str, Any]] = []
    amendments: List[Mapping[str, Any]] = []
    if session.interaction:
        state = machine.from_dict(session.interaction)
        decisions = [d for d in projections.decisions(state) if d["settled"]]
        amendments = projections.amendments(state)

    return CompositionRequest(
        session_id=session.session_id,
        prompt=session.prompt,
        revision=session.revision,
        claims=tuple(c for c in (graph.get("claims") or ()) if isinstance(c, Mapping)),
        verdicts=tuple(v.model_dump(mode="json") for v in session.verdicts),
        evidence=tuple(e for e in session.evidence if isinstance(e, Mapping)),
        decisions=tuple(decisions),
        amendments=tuple(amendments),
        remainder=tuple(_with_ids(graph)),
        refusals=tuple(r for r in session.refusals if isinstance(r, Mapping)),
        gaps=tuple(str(g) for g in session.gaps),
        receipts=tuple(r.model_dump(mode="json") for r in session.capability_receipts),
    )


def _with_ids(graph: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Lane A's remainder items carry no id; the view mints one and so does this, the same way."""
    inquiry_id = str(graph.get("inquiry_id") or "")
    out = []
    for item in graph.get("semantic_remainder") or ():
        if isinstance(item, Mapping):
            row = dict(item)
            row["remainder_id"] = ids.remainder_id(inquiry_id, str(item.get("term") or ""))
            out.append(row)
    return out


# ── the reference check both implementations are held to ─────────────────────

def validate(sections: Sequence[SynthesisSection], request: CompositionRequest) -> None:
    known = request.known_refs()
    unknown: List[str] = []
    for section in sections:
        for field_name, allowed in known.items():
            for ref in getattr(section, field_name):
                if ref not in allowed:
                    unknown.append(f"{section.section_id}.{field_name}={ref}")
    if unknown:
        raise CompositionRefused(
            f"the composition names {len(unknown)} reference(s) that do not exist on this session. "
            f"The whole composition is refused rather than the offending sections: a synthesis in "
            f"which one sentence points at nothing is a synthesis whose bindings cannot be trusted "
            f"anywhere.", unknown=unknown)


# ── the deterministic composer ───────────────────────────────────────────────

#: Verdict → how a section about those claims renders. The judge already decided what each claim
#: rests on; this table does not re-decide it, it names it.
_RENDERING = {
    "supported_by_evidence": "measured",
    "partially_supported": "measured",
    "interpretive_only": "interpretive",
    "unresolved": "unresolved",
    "contradicted": "unresolved",
    "not_investigated": "unresolved",
}

_DEMAND_RENDERING = {"sourced": "sourced", "imagined": "imagined"}


class DeterministicComposer:
    """A full answer from the structured record, with no model and no clock.

    Not a stub. Every binding a model composer would have to produce is produced here, and the
    reference check is the same one — which is what makes the model version an addition rather than
    a replacement, and what lets a deployment with no provider still answer honestly.
    """

    name = "deterministic"
    model = None

    def compose(self, session: SemanticInquirySession, *, at: str = "") -> Optional[Synthesis]:
        request = request_for(session)
        sections = self.sections(request)
        validate(sections, request)
        if not sections:
            return None
        return Synthesis(
            synthesis_id=ids.synthesis_id(request.session_id, request.revision),
            note=PHASE_NOTE,
            sections=sections,
            remainder_refs=[str(r.get("remainder_id")) for r in request.remainder],
            provenance={"producer": PRODUCER, "composer": self.name, "model": None,
                        "composed_at": at, "prompt_sha256": sha256_of(request.prompt),
                        "simulated_capability": bool(request.receipts),
                        "measured_anything": False})

    # ── the sections ──

    def sections(self, request: CompositionRequest) -> List[SynthesisSection]:
        out: List[SynthesisSection] = []
        for build in (self._readings, self._sourced, self._proposed, self._unsettled,
                      self._what_you_decided, self._what_you_added, self._remainder,
                      self._refused):
            section = build(request)
            if section is not None:
                out.append(section)
        return out[:MAX_SECTIONS]

    def _section(self, request: CompositionRequest, *, heading: str, lines: Sequence[str],
                 status: str, claim_refs: Sequence[str] = (), evidence_refs: Sequence[str] = (),
                 refusal_refs: Sequence[str] = (), decision_refs: Sequence[str] = (),
                 user_authored: bool = False) -> Optional[SynthesisSection]:
        text = " ".join(line.strip() for line in lines if line and line.strip())
        if not text:
            return None
        text = text[:MAX_SECTION_CHARS]
        return SynthesisSection(
            section_id=ids.section_id(request.session_id, heading, text),
            heading=heading, text=text, status=status,
            claim_refs=list(claim_refs), evidence_refs=list(evidence_refs),
            refusal_refs=list(refusal_refs), decision_refs=list(decision_refs),
            user_authored=user_authored)

    def _claims_where(self, request: CompositionRequest, predicate) -> List[Mapping[str, Any]]:
        return [c for c in request.claims if predicate(c)]

    def _readings(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        claims = self._claims_where(
            request, lambda c: request.verdict_for(str(c.get("claim_id"))) == "interpretive_only"
            and str(c.get("epistemic_demand")) not in _DEMAND_RENDERING)
        if not claims:
            return None
        return self._section(
            request, heading="What can be said, as a reading",
            status="interpretive", claim_refs=[str(c["claim_id"]) for c in claims],
            lines=["These are readings of the pictures rather than measurements of them, and they "
                   "are not the weaker for it — nothing measurable would settle them.",
                   *[f"· {str(c.get('text') or '').strip()}" for c in claims]])

    def _sourced(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        claims = self._claims_where(
            request, lambda c: str(c.get("epistemic_demand")) == "sourced")
        if not claims:
            return None
        return self._section(
            request, heading="What is attributed to something outside the pictures",
            status="sourced", claim_refs=[str(c["claim_id"]) for c in claims],
            lines=["Nothing in this session consulted a source, so each of these stands as an "
                   "attribution awaiting one, not as an established fact.",
                   *[f"· {str(c.get('text') or '').strip()}" for c in claims]])

    def _proposed(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        claims = self._claims_where(
            request, lambda c: str(c.get("epistemic_demand")) == "imagined")
        if not claims:
            return None
        return self._section(
            request, heading="What is proposed rather than found",
            status="imagined", claim_refs=[str(c["claim_id"]) for c in claims],
            lines=["Put forward by the compilation as something that could follow. Nothing tested "
                   "any of it, and nothing in the pictures asserts it.",
                   *[f"· {str(c.get('text') or '').strip()}" for c in claims]])

    def _unsettled(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        claims = self._claims_where(
            request, lambda c: request.verdict_for(str(c.get("claim_id")))
            in ("unresolved", "not_investigated", "contradicted"))
        if not claims:
            return None
        invoked = [r for r in request.receipts if r.get("attempted")]
        return self._section(
            request, heading="What nothing here settled",
            status="unresolved", claim_refs=[str(c["claim_id"]) for c in claims],
            lines=[("One operational route was selected and invoked, and what came back was a "
                    "declared simulation — it proves the route ran and nothing else."
                    if invoked else
                    "No instrument was invoked against any of these."),
                   "Each of the following is open, and none of it is reported as absent:",
                   *[f"· {str(c.get('text') or '').strip()}" for c in claims]])

    def _what_you_decided(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        if not request.decisions:
            return None
        lines = ["A choice was made about how this inquiry proceeded. It changed which "
                 "investigation was commissioned; it is not itself a finding about the pictures."]
        for decision in request.decisions:
            who = "you" if str(decision.get("by")) == "user" else "Semant, without asking"
            lines.append(f"· {decision.get('question')} — {who}: "
                         f"{decision.get('reason') or decision.get('outcome')}")
        return self._section(request, heading="What your decision changed", status="unresolved",
                             decision_refs=[str(d["decision_id"]) for d in request.decisions],
                             lines=lines)

    def _what_you_added(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        """The person's own words, attributed and carrying no kind of knowing."""
        if not request.amendments:
            return None
        return self._section(
            request, heading="What you added", status="unresolved", user_authored=True,
            decision_refs=[str(a["amendment_id"]) for a in request.amendments],
            lines=["Your words, standing beside what they reference rather than replacing it. "
                   "They change what is pursued; they do not change how anything is known.",
                   *[f"· “{str(a.get('text') or '').strip()}”" for a in request.amendments]])

    def _remainder(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        if not request.remainder and not request.gaps:
            return None
        lines = ["What would still not be settled even if every requested measurement succeeded."]
        lines += [f"· {str(r.get('term') or '').strip()} — {str(r.get('why') or '').strip()}"
                  for r in request.remainder]
        lines += [f"· {gap}" for gap in request.gaps]
        return self._section(request, heading="What measurement would not exhaust",
                             status="interpretive",
                             refusal_refs=[str(r["remainder_id"]) for r in request.remainder],
                             lines=lines)

    def _refused(self, request: CompositionRequest) -> Optional[SynthesisSection]:
        if not request.refusals:
            return None
        return self._section(
            request, heading="What was refused on the way here", status="unresolved",
            refusal_refs=[str(r.get("refusal_id")) for r in request.refusals
                          if r.get("refusal_id")],
            lines=["Produced and not kept. A refusal is a decision with grounds, and the count is "
                   "the only observable that says whether a producer can be trusted.",
                   *[f"· {r.get('kind') or r.get('reason')}: {r.get('why') or r.get('detail')}"
                     for r in request.refusals]])


# ── the model composer ───────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You compose a provisional answer from a structured record of an inquiry. You are given "
    "claims, verdicts, decisions, remainder and refusals — never any image and never the prose "
    "anything was read from. Write only about what is in the record.\n\n"
    "Return JSON: {\"sections\": [{\"heading\": str, \"text\": str, \"status\": one of "
    f"{list(RENDERINGS)}, \"claim_refs\": [str], \"evidence_refs\": [str], "
    "\"refusal_refs\": [str], \"decision_refs\": [str]}]}\n\n"
    "Rules you may not break:\n"
    "· Every ref must appear verbatim in the record you were given. Inventing one refuses the "
    "whole composition.\n"
    "· `measured` and `visible` require a non-empty evidence_refs. If evidence_refs is empty the "
    "status is `interpretive`, `sourced`, `imagined` or `unresolved`.\n"
    "· A capability receipt is not evidence. It records that a route was invoked, not that "
    "anything was found.\n"
    "· A person's decision changed what was pursued. It is never a visual finding.\n"
    "· Interpretive statements may be intelligent. Do not flatten them into apology.")


def build_prompt(request: CompositionRequest) -> str:
    """The whole prompt. Deliberately assembled from the record, so a reader can see that no image
    reference and no reading text is anywhere in it."""
    payload = {
        "question": request.prompt,
        "claims": [{"claim_id": c.get("claim_id"), "text": c.get("text"),
                    "claim_kind": c.get("claim_kind"), "epistemic_demand": c.get("epistemic_demand"),
                    "verdict": request.verdict_for(str(c.get("claim_id")))}
                   for c in request.claims],
        "evidence": [{"evidence_id": e.get("evidence_id")} for e in request.evidence],
        "decisions": [{"decision_id": d.get("decision_id"), "question": d.get("question"),
                       "by": d.get("by"), "outcome": d.get("outcome"), "reason": d.get("reason")}
                      for d in request.decisions],
        "amendments": [{"amendment_id": a.get("amendment_id"), "text": a.get("text")}
                       for a in request.amendments],
        "remainder": [{"remainder_id": r.get("remainder_id"), "term": r.get("term"),
                       "why": r.get("why")} for r in request.remainder],
        "refusals": [{"refusal_id": r.get("refusal_id"), "kind": r.get("kind"),
                      "why": r.get("why")} for r in request.refusals],
        "gaps": list(request.gaps),
        "capability_receipts": [{"receipt_id": r.get("receipt_id"),
                                 "execution_mode": r.get("execution_mode"),
                                 "status": r.get("status"),
                                 "usable_as_evidence": r.get("usable_as_evidence")}
                                for r in request.receipts],
    }
    return json.dumps(payload, ensure_ascii=False, indent=1)


class ModelSynthesisComposer:
    """The merged `synthesis_composer` role, held to the deterministic composer's standard.

    UNAVAILABLE IS A STATE, NOT A FALLBACK. With no client, this returns `None` and the coordinator
    records the stage as producing nothing. It does not quietly hand over to the deterministic
    composer and call the result a model composition — that substitution is structurally the same
    lie as calling a simulated receipt evidence, one layer up.
    """

    name = "model"

    def __init__(self, client: Any = None, *, model: Optional[str] = None):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        self.calls = 0
        self.last_error = ""

    @property
    def model(self) -> Optional[str]:
        return self._model if self._model is not None else role_registry.model_for(ROLE)

    def _get_client(self) -> Any:
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        try:
            from groq import Groq

            from backend.config import settings
            self._client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        except Exception:
            self._client = None
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    def compose(self, session: SemanticInquirySession, *, at: str = "") -> Optional[Synthesis]:
        request = request_for(session)
        if not self.is_available():
            self.last_error = "the synthesis composer is unavailable (no client or API key)"
            return None

        user_prompt = build_prompt(request)
        try:
            self.calls += 1
            completion = self._get_client().chat.completions.create(
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user_prompt}],
                model=self.model,
                response_format={"type": "json_object"})
            raw = completion.choices[0].message.content or ""
            finish = str(getattr(completion.choices[0], "finish_reason", "") or "")
            payload = json.loads(raw)
        except Exception as exc:                        # noqa: BLE001
            self.last_error = f"the synthesis composer failed: {type(exc).__name__}"
            return None

        sections = self.read_sections(payload, request)
        validate(sections, request)                     # the same check, no exemption
        if not sections:
            return None
        return Synthesis(
            synthesis_id=ids.synthesis_id(request.session_id, request.revision),
            note=PHASE_NOTE, sections=sections,
            remainder_refs=[str(r.get("remainder_id")) for r in request.remainder],
            provenance={"producer": PRODUCER, "composer": self.name, "model": self.model,
                        "provider": getattr(role_registry.get(ROLE), "provider", None),
                        "composed_at": at,
                        "prompt_sha256": sha256_of(user_prompt), "finish_reason": finish,
                        "truncated": finish == "length",
                        "simulated_capability": bool(request.receipts),
                        "measured_anything": False})

    def read_sections(self, payload: Mapping[str, Any],
                      request: CompositionRequest) -> List[SynthesisSection]:
        rows = payload.get("sections") if isinstance(payload, Mapping) else None
        sections: List[SynthesisSection] = []
        for row in (rows or [])[:MAX_SECTIONS]:
            if not isinstance(row, Mapping):
                continue
            text = str(row.get("text") or "").strip()[:MAX_SECTION_CHARS]
            if not text:
                continue
            heading = str(row.get("heading") or "").strip()
            status = str(row.get("status") or "interpretive")
            if status not in RENDERINGS:
                # An unrecognised rendering is corrected DOWNWARD, never up, and the correction is
                # visible in the text rather than silent.
                status = "unresolved"
            sections.append(SynthesisSection(
                section_id=ids.section_id(request.session_id, heading, text),
                heading=heading, text=text, status=status,
                claim_refs=[str(r) for r in (row.get("claim_refs") or [])],
                evidence_refs=[str(r) for r in (row.get("evidence_refs") or [])],
                refusal_refs=[str(r) for r in (row.get("refusal_refs") or [])],
                decision_refs=[str(r) for r in (row.get("decision_refs") or [])],
                user_authored=False))
        return sections


__all__ = ["ROLE", "PRODUCER", "RENDERINGS", "PHASE_NOTE", "MAX_SECTIONS", "CompositionRefused",
           "CompositionRequest", "request_for", "validate", "DeterministicComposer",
           "ModelSynthesisComposer", "SYSTEM_PROMPT", "build_prompt"]
